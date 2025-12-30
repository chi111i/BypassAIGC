"""
Fixer: ValidationReport -> Patch -> docx_bytes

Deterministic repair based on validation violations.
"""
from __future__ import annotations

from typing import List

from lxml import etree

from ..models.patch import Patch, PatchAction
from ..models.stylespec import StyleSpec
from ..models.validation import ValidationReport, Violation
from ..utils.ooxml import DocxPackage


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W_NS}


def _qn(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NSMAP[prefix]}}}{local}"


def _mm_to_twips(mm: float) -> int:
    return int(round(mm / 25.4 * 1440))


def build_patch_from_report(report: ValidationReport) -> Patch:
    """
    Generate a deterministic Patch from ValidationReport.

    Only violations with FixSuggestion are converted to actions.
    """
    actions: List[PatchAction] = []
    for v in report.violations:
        if v.suggestion:
            actions.append(PatchAction(
                action=v.suggestion.action,
                params=v.suggestion.params,
            ))
    return Patch(actions=actions)


def apply_patch(docx_bytes: bytes, patch: Patch, spec: StyleSpec) -> bytes:
    """
    Apply Patch actions to docx_bytes and return fixed bytes.
    """
    pkg = DocxPackage.from_bytes(docx_bytes)
    doc_root = pkg.read_xml("word/document.xml")
    body = doc_root.find("w:body", namespaces=NSMAP)

    for act in patch.actions:
        if act.action == "set_page_margins":
            _apply_set_page_margins(doc_root, act.params, spec)
        elif act.action == "set_paragraph_style":
            _apply_set_paragraph_style(doc_root, act.params)
        elif act.action == "clear_direct_run_formatting":
            _apply_clear_direct_formatting(doc_root, act.params)
        elif act.action == "insert_toc_field":
            _apply_insert_toc(doc_root, act.params)

    pkg.write_xml("word/document.xml", doc_root)
    return pkg.to_bytes()


def _find_sectpr(doc_root: etree._Element) -> etree._Element | None:
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


def _apply_set_page_margins(doc_root: etree._Element, params: dict, spec: StyleSpec) -> None:
    sectPr = _find_sectpr(doc_root)
    if sectPr is None:
        return
    pgMar = sectPr.find("w:pgMar", namespaces=NSMAP)
    if pgMar is None:
        pgMar = etree.SubElement(sectPr, _qn("w:pgMar"))

    exp = spec.page.margins_mm
    mapping = {
        "top": exp.top,
        "bottom": exp.bottom,
        "left": exp.left,
        "right": exp.right,
        "gutter": exp.binding,
        "header": spec.page.header_mm,
        "footer": spec.page.footer_mm,
    }
    for k in params.keys():
        if k == "target":
            continue
        if k in mapping:
            pgMar.set(_qn(f"w:{k}"), str(_mm_to_twips(mapping[k])))
        elif k in params and isinstance(params[k], (int, float)):
            pgMar.set(_qn(f"w:{k}"), str(int(params[k])))


def _apply_set_paragraph_style(doc_root: etree._Element, params: dict) -> None:
    idx = params.get("paragraph_index")
    style_id = params.get("style_id", "Body")
    if idx is None:
        return
    all_paras = doc_root.findall(".//w:p", namespaces=NSMAP)
    if idx < 0 or idx >= len(all_paras):
        return
    p = all_paras[idx]
    pPr = p.find("w:pPr", namespaces=NSMAP)
    if pPr is None:
        pPr = etree.Element(_qn("w:pPr"))
        p.insert(0, pPr)
    pStyle = pPr.find("w:pStyle", namespaces=NSMAP)
    if pStyle is None:
        pStyle = etree.SubElement(pPr, _qn("w:pStyle"))
    pStyle.set(_qn("w:val"), style_id)


def _apply_clear_direct_formatting(doc_root: etree._Element, params: dict) -> None:
    idx = params.get("paragraph_index")
    if idx is None:
        return
    all_paras = doc_root.findall(".//w:p", namespaces=NSMAP)
    if idx < 0 or idx >= len(all_paras):
        return
    p = all_paras[idx]

    forbidden_tags = {"rFonts", "sz", "szCs", "b", "bCs", "i", "iCs", "u", "color"}
    for rpr in p.findall(".//w:rPr", namespaces=NSMAP):
        for child in list(rpr):
            local = etree.QName(child).localname
            if local in forbidden_tags:
                rpr.remove(child)


def _apply_insert_toc(doc_root: etree._Element, params: dict) -> None:
    max_level = params.get("max_level", 3)
    body = doc_root.find("w:body", namespaces=NSMAP)
    if body is None:
        return

    ps = body.findall("w:p", namespaces=NSMAP)
    insert_idx = 0
    for i, p in enumerate(ps):
        pPr = p.find("w:pPr", namespaces=NSMAP)
        if pPr is not None:
            pStyle = pPr.find("w:pStyle", namespaces=NSMAP)
            if pStyle is not None and pStyle.get(_qn("w:val")) in {"H1", "FrontHeading"}:
                insert_idx = i
                break

    toc_p = etree.Element(_qn("w:p"))
    toc_pPr = etree.SubElement(toc_p, _qn("w:pPr"))
    toc_pStyle = etree.SubElement(toc_pPr, _qn("w:pStyle"))
    toc_pStyle.set(_qn("w:val"), "FrontHeading")

    toc_r = etree.SubElement(toc_p, _qn("w:r"))
    toc_fld = etree.SubElement(toc_r, _qn("w:fldSimple"))
    toc_fld.set(_qn("w:instr"), f'TOC \\o "1-{max_level}" \\h \\z \\u')

    body.insert(insert_idx, toc_p)


def fix_docx(docx_bytes: bytes, report: ValidationReport, spec: StyleSpec) -> bytes:
    """
    Convenience function: build patch from report and apply it.
    """
    patch = build_patch_from_report(report)
    if not patch.actions:
        return docx_bytes
    return apply_patch(docx_bytes, patch, spec)
