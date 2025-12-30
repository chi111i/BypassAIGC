"""
reference.docx 生成器：StyleSpec → 可复用模板

实现方式：
1) 先生成一个最小 docx（python-docx）
2) 通过 OOXML patch:
   - 写入/更新 word/styles.xml（自定义样式 + 段落/字符属性）
   - 写入/更新 word/numbering.xml（多级编号）
   - 将编号绑定到 H1/H2/H3 样式（style.pPr.numPr + lvl.pStyle）
"""
from __future__ import annotations

import io
import random
from typing import Optional

from docx import Document
from docx.shared import Mm
from lxml import etree

from ..models.stylespec import StyleSpec
from ..utils.ooxml import DocxPackage


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W_NS}


def _qn(tag: str) -> str:
    # tag like 'w:style'
    prefix, local = tag.split(":")
    return f"{{{NSMAP[prefix]}}}{local}"


def _mm_to_twips(mm: float) -> int:
    # 1 inch = 25.4 mm = 1440 twips
    return int(round(mm / 25.4 * 1440))


def _pt_to_half_points(pt: float) -> int:
    return int(round(pt * 2))


def _chars_to_100(chars: float) -> int:
    return int(round(chars * 100))


def _rand_hex(n: int = 8) -> str:
    return "".join(random.choice("0123456789ABCDEF") for _ in range(n))


def generate_reference_docx(spec: StyleSpec) -> bytes:
    # 1) base doc
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Mm(spec.page.margins_mm.top)
    section.bottom_margin = Mm(spec.page.margins_mm.bottom)
    section.left_margin = Mm(spec.page.margins_mm.left)
    section.right_margin = Mm(spec.page.margins_mm.right)
    section.gutter = Mm(spec.page.margins_mm.binding)
    section.header_distance = Mm(spec.page.header_mm)
    section.footer_distance = Mm(spec.page.footer_mm)
    # ensure at least one paragraph
    doc.add_paragraph("")

    buf = io.BytesIO()
    doc.save(buf)
    pkg = DocxPackage.from_bytes(buf.getvalue())

    # 2) patch styles.xml
    styles_root = pkg.read_xml("word/styles.xml")
    _patch_styles_xml(styles_root, spec)
    pkg.write_xml("word/styles.xml", styles_root)

    # 3) patch numbering.xml (optional)
    if spec.numbering:
        try:
            numbering_root = pkg.read_xml("word/numbering.xml")
        except KeyError:
            numbering_root = etree.Element(_qn("w:numbering"), nsmap=NSMAP)
        _patch_numbering_xml(numbering_root, spec)
        pkg.write_xml("word/numbering.xml", numbering_root)

    return pkg.to_bytes()


def patch_reference_docx(spec: StyleSpec, base_docx_bytes: bytes) -> bytes:
    """Patch an existing reference.docx using the deterministic spec."""
    pkg = DocxPackage.from_bytes(base_docx_bytes)
    # patch page margins in document.xml (sectPr/pgMar)
    try:
        doc_root = pkg.read_xml("word/document.xml")
        _patch_document_pgmar(doc_root, spec)
        pkg.write_xml("word/document.xml", doc_root)
    except Exception:
        pass

    # patch styles.xml
    styles_root = pkg.read_xml("word/styles.xml")
    _patch_styles_xml(styles_root, spec)
    pkg.write_xml("word/styles.xml", styles_root)

    # patch numbering.xml
    if spec.numbering:
        try:
            numbering_root = pkg.read_xml("word/numbering.xml")
        except KeyError:
            numbering_root = etree.Element(_qn("w:numbering"), nsmap=NSMAP)
        _patch_numbering_xml(numbering_root, spec)
        pkg.write_xml("word/numbering.xml", numbering_root)

    return pkg.to_bytes()


def _patch_document_pgmar(doc_root: etree._Element, spec: StyleSpec) -> None:
    """Ensure pgMar matches spec on the last sectPr."""
    body = doc_root.find("w:body", namespaces=NSMAP)
    if body is None:
        return
    sectPr = body.find("w:sectPr", namespaces=NSMAP)
    if sectPr is None:
        ps = body.findall("w:p", namespaces=NSMAP)
        if not ps:
            return
        pPr = ps[-1].find("w:pPr", namespaces=NSMAP)
        if pPr is None:
            pPr = etree.SubElement(ps[-1], _qn("w:pPr"))
        sectPr = pPr.find("w:sectPr", namespaces=NSMAP)
        if sectPr is None:
            sectPr = etree.SubElement(pPr, _qn("w:sectPr"))
    pgMar = sectPr.find("w:pgMar", namespaces=NSMAP)
    if pgMar is None:
        pgMar = etree.SubElement(sectPr, _qn("w:pgMar"))
    exp = spec.page.margins_mm
    pgMar.set(_qn("w:top"), str(_mm_to_twips(exp.top)))
    pgMar.set(_qn("w:bottom"), str(_mm_to_twips(exp.bottom)))
    pgMar.set(_qn("w:left"), str(_mm_to_twips(exp.left)))
    pgMar.set(_qn("w:right"), str(_mm_to_twips(exp.right)))
    pgMar.set(_qn("w:gutter"), str(_mm_to_twips(exp.binding)))
    pgMar.set(_qn("w:header"), str(_mm_to_twips(spec.page.header_mm)))
    pgMar.set(_qn("w:footer"), str(_mm_to_twips(spec.page.footer_mm)))


def _ensure_child(parent: etree._Element, tag: str) -> etree._Element:
    child = parent.find(tag, namespaces=NSMAP)
    if child is None:
        child = etree.SubElement(parent, _qn(tag))
    return child


def _find_style(styles_root: etree._Element, style_id: str) -> Optional[etree._Element]:
    for st in styles_root.findall("w:style", namespaces=NSMAP):
        if st.get(_qn("w:styleId")) == style_id:
            return st
    return None


def _alignment_to_w(val: str) -> str:
    return {"left": "left", "center": "center", "right": "right", "justify": "both"}[val]


def _line_to_twips(rule: str, size_pt: Optional[float]) -> tuple:
    if rule == "single":
        return 240, "auto"
    if rule == "1.5":
        return 360, "auto"
    if rule == "double":
        return 480, "auto"
    # exact
    pt_val = float(size_pt or 12.0)
    return int(round(pt_val * 20)), "exact"


def _patch_styles_xml(styles_root: etree._Element, spec: StyleSpec) -> None:
    for style_id, s in spec.styles.items():
        st = _find_style(styles_root, style_id)
        if st is None:
            st = etree.SubElement(styles_root, _qn("w:style"))
            st.set(_qn("w:type"), "paragraph")
            st.set(_qn("w:customStyle"), "1")
            st.set(_qn("w:styleId"), style_id)
            name_el = etree.SubElement(st, _qn("w:name"))
            name_el.set(_qn("w:val"), style_id)
            aliases = st.find("w:aliases", namespaces=NSMAP)
            if aliases is None:
                aliases = etree.SubElement(st, _qn("w:aliases"))
            aliases.set(_qn("w:val"), s.name)
            based_on = etree.SubElement(st, _qn("w:basedOn"))
            based_on.set(_qn("w:val"), "Normal")
            etree.SubElement(st, _qn("w:qFormat"))

        # name
        name_el = st.find("w:name", namespaces=NSMAP)
        if name_el is None:
            name_el = etree.SubElement(st, _qn("w:name"))
        name_el.set(_qn("w:val"), style_id)
        aliases = st.find("w:aliases", namespaces=NSMAP)
        if aliases is None:
            aliases = etree.SubElement(st, _qn("w:aliases"))
        aliases.set(_qn("w:val"), s.name)

        # pPr / rPr
        ppr = st.find("w:pPr", namespaces=NSMAP)
        if ppr is None:
            ppr = etree.SubElement(st, _qn("w:pPr"))
        rpr = st.find("w:rPr", namespaces=NSMAP)
        if rpr is None:
            rpr = etree.SubElement(st, _qn("w:rPr"))

        # paragraph: alignment, spacing, ind, keep, outline
        jc = _ensure_child(ppr, "w:jc")
        jc.set(_qn("w:val"), _alignment_to_w(s.paragraph.alignment))

        spacing = _ensure_child(ppr, "w:spacing")
        line, line_rule = _line_to_twips(s.paragraph.line_spacing_rule, s.paragraph.line_spacing)
        spacing.set(_qn("w:line"), str(line))
        spacing.set(_qn("w:lineRule"), line_rule)

        if s.paragraph.space_before_lines is not None:
            spacing.set(_qn("w:beforeLines"), str(int(round(s.paragraph.space_before_lines * 100))))
            spacing.set(_qn("w:before"), "0")
        else:
            spacing.attrib.pop(_qn("w:beforeLines"), None)
            spacing.set(_qn("w:before"), str(int(round(s.paragraph.space_before_pt * 20))))

        if s.paragraph.space_after_lines is not None:
            spacing.set(_qn("w:afterLines"), str(int(round(s.paragraph.space_after_lines * 100))))
            spacing.set(_qn("w:after"), "0")
        else:
            spacing.attrib.pop(_qn("w:afterLines"), None)
            spacing.set(_qn("w:after"), str(int(round(s.paragraph.space_after_pt * 20))))

        ind = _ensure_child(ppr, "w:ind")
        if s.paragraph.first_line_indent_chars > 0:
            ind.set(_qn("w:firstLineChars"), str(_chars_to_100(s.paragraph.first_line_indent_chars)))
            if _qn("w:firstLine") in ind.attrib:
                del ind.attrib[_qn("w:firstLine")]
        else:
            if _qn("w:firstLineChars") in ind.attrib:
                del ind.attrib[_qn("w:firstLineChars")]
        if s.paragraph.hanging_indent_chars > 0:
            ind.set(_qn("w:hangingChars"), str(_chars_to_100(s.paragraph.hanging_indent_chars)))
        else:
            if _qn("w:hangingChars") in ind.attrib:
                del ind.attrib[_qn("w:hangingChars")]

        def _toggle(tag: str, enabled: bool):
            el = ppr.find(tag, namespaces=NSMAP)
            if enabled:
                if el is None:
                    etree.SubElement(ppr, _qn(tag))
            else:
                if el is not None:
                    ppr.remove(el)

        _toggle("w:keepNext", s.paragraph.keep_with_next)
        _toggle("w:keepLines", s.paragraph.keep_lines)
        _toggle("w:pageBreakBefore", s.paragraph.page_break_before)

        wc = ppr.find("w:widowControl", namespaces=NSMAP)
        if wc is None:
            wc = etree.SubElement(ppr, _qn("w:widowControl"))
        wc.set(_qn("w:val"), "1" if s.paragraph.widows_control else "0")

        if s.outline_level is not None:
            out = _ensure_child(ppr, "w:outlineLvl")
            out.set(_qn("w:val"), str(s.outline_level))
        else:
            out = ppr.find("w:outlineLvl", namespaces=NSMAP)
            if out is not None:
                ppr.remove(out)

        # run: fonts, size, bold, italic, underline
        rfonts = _ensure_child(rpr, "w:rFonts")
        rfonts.set(_qn("w:ascii"), s.run.font.ascii)
        rfonts.set(_qn("w:hAnsi"), s.run.font.hAnsi)
        rfonts.set(_qn("w:eastAsia"), s.run.font.eastAsia)
        rfonts.set(_qn("w:cs"), s.run.font.hAnsi)

        sz = _ensure_child(rpr, "w:sz")
        sz.set(_qn("w:val"), str(_pt_to_half_points(s.run.size_pt)))
        szcs = _ensure_child(rpr, "w:szCs")
        szcs.set(_qn("w:val"), str(_pt_to_half_points(s.run.size_pt)))

        def _run_toggle(tag: str, enabled: bool):
            el = rpr.find(tag, namespaces=NSMAP)
            if enabled:
                if el is None:
                    etree.SubElement(rpr, _qn(tag))
            else:
                if el is not None:
                    rpr.remove(el)

        _run_toggle("w:b", s.run.bold)
        _run_toggle("w:i", s.run.italic)
        if s.run.underline:
            u = _ensure_child(rpr, "w:u")
            u.set(_qn("w:val"), "single")
        else:
            u = rpr.find("w:u", namespaces=NSMAP)
            if u is not None:
                rpr.remove(u)

    # bind numbering to heading styles
    if spec.numbering:
        num_id = spec.numbering.num_id
        for lvl in spec.numbering.levels:
            style_id = lvl.style_id
            st = _find_style(styles_root, style_id)
            if st is None:
                continue
            ppr = st.find("w:pPr", namespaces=NSMAP)
            if ppr is None:
                ppr = etree.SubElement(st, _qn("w:pPr"))
            numPr = ppr.find("w:numPr", namespaces=NSMAP)
            if numPr is None:
                numPr = etree.SubElement(ppr, _qn("w:numPr"))
            ilvl = numPr.find("w:ilvl", namespaces=NSMAP)
            if ilvl is None:
                ilvl = etree.SubElement(numPr, _qn("w:ilvl"))
            ilvl.set(_qn("w:val"), str(lvl.level))
            nid = numPr.find("w:numId", namespaces=NSMAP)
            if nid is None:
                nid = etree.SubElement(numPr, _qn("w:numId"))
            nid.set(_qn("w:val"), str(num_id))


def _patch_numbering_xml(numbering_root: etree._Element, spec: StyleSpec) -> None:
    assert spec.numbering is not None
    abstract_id = spec.numbering.abstract_num_id
    num_id = spec.numbering.num_id

    # remove existing abstractNum with same id
    for an in list(numbering_root.findall("w:abstractNum", namespaces=NSMAP)):
        if an.get(_qn("w:abstractNumId")) == str(abstract_id):
            numbering_root.remove(an)

    abstract = etree.SubElement(numbering_root, _qn("w:abstractNum"))
    abstract.set(_qn("w:abstractNumId"), str(abstract_id))
    nsid = etree.SubElement(abstract, _qn("w:nsid"))
    nsid.set(_qn("w:val"), _rand_hex(8))
    mlt = etree.SubElement(abstract, _qn("w:multiLevelType"))
    mlt.set(_qn("w:val"), "hybridMultilevel")

    for lvl in spec.numbering.levels:
        lvl_el = etree.SubElement(abstract, _qn("w:lvl"))
        lvl_el.set(_qn("w:ilvl"), str(lvl.level))
        start = etree.SubElement(lvl_el, _qn("w:start"))
        start.set(_qn("w:val"), str(lvl.start))
        numFmt = etree.SubElement(lvl_el, _qn("w:numFmt"))
        numFmt.set(_qn("w:val"), lvl.fmt)
        lvlText = etree.SubElement(lvl_el, _qn("w:lvlText"))
        lvlText.set(_qn("w:val"), lvl.lvl_text)
        suff = etree.SubElement(lvl_el, _qn("w:suff"))
        suff.set(_qn("w:val"), lvl.suffix)
        lvlJc = etree.SubElement(lvl_el, _qn("w:lvlJc"))
        lvlJc.set(_qn("w:val"), "left")
        pStyle = etree.SubElement(lvl_el, _qn("w:pStyle"))
        pStyle.set(_qn("w:val"), lvl.style_id)

        ppr = etree.SubElement(lvl_el, _qn("w:pPr"))
        ind = etree.SubElement(ppr, _qn("w:ind"))
        ind.set(_qn("w:left"), "0")
        ind.set(_qn("w:hanging"), "0")

        style = spec.styles.get(lvl.style_id)
        if style:
            rpr = etree.SubElement(lvl_el, _qn("w:rPr"))
            rfonts = etree.SubElement(rpr, _qn("w:rFonts"))
            rfonts.set(_qn("w:ascii"), style.run.font.ascii)
            rfonts.set(_qn("w:hAnsi"), style.run.font.hAnsi)
            rfonts.set(_qn("w:eastAsia"), style.run.font.eastAsia)
            rfonts.set(_qn("w:cs"), style.run.font.hAnsi)
            sz = etree.SubElement(rpr, _qn("w:sz"))
            sz.set(_qn("w:val"), str(_pt_to_half_points(style.run.size_pt)))
            szcs = etree.SubElement(rpr, _qn("w:szCs"))
            szcs.set(_qn("w:val"), str(_pt_to_half_points(style.run.size_pt)))

    # remove existing num with same id
    for num in list(numbering_root.findall("w:num", namespaces=NSMAP)):
        if num.get(_qn("w:numId")) == str(num_id):
            numbering_root.remove(num)

    num = etree.SubElement(numbering_root, _qn("w:num"))
    num.set(_qn("w:numId"), str(num_id))
    abs_id = etree.SubElement(num, _qn("w:abstractNumId"))
    abs_id.set(_qn("w:val"), str(abstract_id))
