"""
docx 校验器（确定性）：output.docx → ValidationReport
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from lxml import etree

from ..models.stylespec import StyleSpec
from ..models.validation import FixSuggestion, Location, ValidationReport, ValidationSummary, Violation
from ..utils.ooxml import DocxPackage


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W_NS}


def _qn(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NSMAP[prefix]}}}{local}"


def _twips_to_mm(twips: int) -> float:
    return twips / 1440 * 25.4


def _mm_to_twips(mm: float) -> int:
    return int(round(mm / 25.4 * 1440))


def _get_text(p: etree._Element) -> str:
    return "".join(p.xpath(".//w:t/text()", namespaces=NSMAP)).strip()


def _get_p_style(p: etree._Element) -> Optional[str]:
    pPr = p.find("w:pPr", namespaces=NSMAP)
    if pPr is None:
        return None
    pStyle = pPr.find("w:pStyle", namespaces=NSMAP)
    if pStyle is None:
        return None
    return pStyle.get(_qn("w:val"))


def _find_sectpr(doc_root: etree._Element) -> Optional[etree._Element]:
    body = doc_root.find("w:body", namespaces=NSMAP)
    if body is None:
        return None
    sectPr = body.find("w:sectPr", namespaces=NSMAP)
    if sectPr is not None:
        return sectPr
    ps = body.findall("w:p", namespaces=NSMAP)
    if not ps:
        return None
    last_ppr = ps[-1].find("w:pPr", namespaces=NSMAP)
    if last_ppr is None:
        return None
    return last_ppr.find("w:sectPr", namespaces=NSMAP)


def _has_toc_field(doc_root: etree._Element) -> bool:
    for fld in doc_root.findall(".//w:fldSimple", namespaces=NSMAP):
        instr = fld.get(_qn("w:instr")) or ""
        if "TOC" in instr:
            return True
    return False


def _find_all_sectpr(doc_root: etree._Element) -> List[etree._Element]:
    body = doc_root.find("w:body", namespaces=NSMAP)
    if body is None:
        return []
    sect_prs = body.findall(".//w:sectPr", namespaces=NSMAP)
    seen = set()
    out = []
    for s in sect_prs:
        sid = id(s)
        if sid in seen:
            continue
        seen.add(sid)
        out.append(s)
    return out


def _docx_has_page_field(pkg: DocxPackage) -> bool:
    for name, content in pkg.files.items():
        if not name.startswith("word/footer") or not name.endswith(".xml"):
            continue
        try:
            root = etree.fromstring(content)
        except Exception:
            continue
        for fld in root.findall(".//w:fldSimple", namespaces=NSMAP):
            instr = fld.get(_qn("w:instr")) or ""
            if "PAGE" in instr:
                return True
    return False


_DIRECT_RPR_TAGS = {
    "rFonts": "font",
    "sz": "size",
    "szCs": "size",
    "b": "bold",
    "bCs": "bold",
    "i": "italic",
    "iCs": "italic",
    "u": "underline",
    "color": "color",
}


def _check_run_direct_formatting(p: etree._Element, forbid: Dict[str, bool]) -> List[Tuple[str, str]]:
    violations: List[Tuple[str, str]] = []
    for rpr in p.findall(".//w:rPr", namespaces=NSMAP):
        for child in list(rpr):
            local = etree.QName(child).localname
            if local in _DIRECT_RPR_TAGS:
                kind = _DIRECT_RPR_TAGS[local]
                if forbid.get(kind, False):
                    violations.append((kind, local))
    return violations


def validate_docx(docx_bytes: bytes, spec: StyleSpec) -> ValidationReport:
    pkg = DocxPackage.from_bytes(docx_bytes)
    doc_root = pkg.read_xml("word/document.xml")

    violations: List[Violation] = []

    # 1) margins
    sectPr = _find_sectpr(doc_root)
    if sectPr is None:
        violations.append(Violation(
            violation_id="layout.sectpr_missing",
            severity="error",
            message="未找到 sectPr（无法读取页边距/页面设置）",
        ))
    else:
        pgMar = sectPr.find("w:pgMar", namespaces=NSMAP)
        if pgMar is None:
            violations.append(Violation(
                violation_id="layout.pgmar_missing",
                severity="error",
                message="未找到 pgMar（无法读取页边距）",
            ))
        else:
            exp = spec.page.margins_mm
            checks = {
                "top": exp.top,
                "bottom": exp.bottom,
                "left": exp.left,
                "right": exp.right,
                "gutter": exp.binding,
                "header": spec.page.header_mm,
                "footer": spec.page.footer_mm,
            }
            for k, exp_mm in checks.items():
                val = pgMar.get(_qn(f"w:{k}"))
                if val is None:
                    continue
                act_twips = int(val)
                exp_twips = _mm_to_twips(exp_mm)
                if abs(act_twips - exp_twips) > 10:
                    violations.append(Violation(
                        violation_id=f"layout.margin_{k}",
                        severity="error",
                        message=f"页边距/页面距离不符合规范：{k}",
                        expected={"mm": exp_mm, "twips": exp_twips},
                        actual={"mm": round(_twips_to_mm(act_twips), 2), "twips": act_twips},
                        suggestion=FixSuggestion(action="set_page_margins", params={"target": "section0", k: exp_twips}),
                    ))

    # paragraphs
    paragraphs = doc_root.findall(".//w:body/w:p", namespaces=NSMAP)
    all_paras = doc_root.findall(".//w:p", namespaces=NSMAP)

    # 2) structure: required H1 titles must exist
    h1_titles = set()
    for p in paragraphs:
        text = _get_text(p)
        style = _get_p_style(p) or ""
        if style in {"H1", "FrontHeading"} and text:
            h1_titles.add(text.strip())
    for req in spec.structure.required_h1_titles:
        if req not in h1_titles:
            violations.append(Violation(
                violation_id="structure.required_section_missing",
                severity="warning",
                message=f"缺少必需的一级标题：{req}",
                expected=req,
                actual=list(sorted(h1_titles)),
            ))

    # 3) style existence + 4) direct formatting
    spec_style_ids = set(spec.styles.keys())
    forbid = {
        "font": spec.forbidden_direct_formatting.font,
        "size": spec.forbidden_direct_formatting.size,
        "bold": spec.forbidden_direct_formatting.bold,
        "italic": spec.forbidden_direct_formatting.italic,
        "underline": spec.forbidden_direct_formatting.underline,
        "color": spec.forbidden_direct_formatting.color,
    }

    for idx, p in enumerate(all_paras):
        style = _get_p_style(p)
        text = _get_text(p)
        if style and style not in spec_style_ids and style not in {"Normal", "DefaultParagraphFont"}:
            violations.append(Violation(
                violation_id="style.unknown_style",
                severity="warning",
                message=f"段落使用了未知样式：{style}",
                location=Location(paragraph_index=idx, text_snippet=text[:80]),
                expected=sorted(spec_style_ids),
                actual=style,
                suggestion=FixSuggestion(action="set_paragraph_style", params={"paragraph_index": idx, "style_id": "Body"}),
            ))

        df = _check_run_direct_formatting(p, forbid)
        if df:
            kinds = sorted({k for k, _ in df})
            violations.append(Violation(
                violation_id="style.direct_formatting_forbidden",
                severity="error",
                message=f"检测到禁止的直接格式覆盖：{', '.join(kinds)}",
                location=Location(paragraph_index=idx, text_snippet=text[:80], detail={"kinds": kinds}),
                expected="use paragraph styles only",
                actual=kinds,
                suggestion=FixSuggestion(action="clear_direct_run_formatting", params={"paragraph_index": idx}),
            ))

    # 5) TOC field
    if spec.structure.toc_max_level > 0:
        if not _has_toc_field(doc_root):
            violations.append(Violation(
                violation_id="field.toc_missing",
                severity="warning",
                message="未检测到目录 TOC 字段（若需要目录，请插入 TOC 域）",
                suggestion=FixSuggestion(action="insert_toc_field", params={"max_level": spec.structure.toc_max_level}),
            ))

    # summary
    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    infos = sum(1 for v in violations if v.severity == "info")
    summary = ValidationSummary(ok=(errors == 0), errors=errors, warnings=warnings, infos=infos)
    return ValidationReport(summary=summary, violations=violations)
