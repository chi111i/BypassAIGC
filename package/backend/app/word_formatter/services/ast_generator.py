"""
Text/Markdown → DocumentAST（确定性解析为主；AI 可插拔）。

支持：
- Markdown（推荐）：# / ## / ###，列表、表格、图片语法（可选）
- 轻量标题：行首 1、1.1、1.1.1 识别为标题层级
- AI 辅助：识别纯文本中的段落类型（标题/摘要/正文等）
"""
from __future__ import annotations

import re
import json
from typing import Any, Dict, List, Optional, Tuple

import mistune

from ..models.ast import (
    BibliographyBlock,
    DocumentAST,
    DocumentMeta,
    FigureBlock,
    HeadingBlock,
    Inline,
    ListBlock,
    ListItem,
    ParagraphBlock,
    PageBreakBlock,
    SectionBreakBlock,
    TableBlock,
)


_FRONT_MATTER_RE = re.compile(r"^\s*---\s*$", re.M)


def _parse_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    """
    支持非常轻量的 YAML front matter（不依赖 pyyaml）：
    ---
    key: value
    key2: value2
    ---
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: Dict[str, str] = {}
    i = 1
    while i < len(lines):
        if lines[i].strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return meta, body
        if ":" in lines[i]:
            k, v = lines[i].split(":", 1)
            meta[k.strip()] = v.strip()
        i += 1
    # no closing ---; treat as normal text
    return {}, text


def _inlines_from_children(children: List[Dict[str, Any]]) -> List[Inline]:
    inlines: List[Inline] = []
    for ch in children:
        t = ch.get("type")
        if t == "text":
            inlines.append(Inline(type="text", text=ch.get("raw", "") or ch.get("text", "")))
        elif t == "strong":
            txt = "".join(_collect_text(ch))
            inlines.append(Inline(type="bold", text=txt))
        elif t == "emphasis":
            txt = "".join(_collect_text(ch))
            inlines.append(Inline(type="italic", text=txt))
        elif t == "inline_code":
            inlines.append(Inline(type="code", text=ch.get("raw", "") or ch.get("text", "")))
        elif t == "linebreak":
            inlines.append(Inline(type="text", text="\n"))
        else:
            # fallback as text
            txt = "".join(_collect_text(ch))
            if txt:
                inlines.append(Inline(type="text", text=txt))
    return inlines


def _collect_text(node: Dict[str, Any]) -> List[str]:
    if "raw" in node and isinstance(node["raw"], str):
        return [node["raw"]]
    if "text" in node and isinstance(node["text"], str):
        return [node["text"]]
    out: List[str] = []
    for c in node.get("children", []) or []:
        out.extend(_collect_text(c))
    return out


def parse_markdown_to_ast(text: str) -> DocumentAST:
    meta_dict, body = _parse_front_matter(text)
    meta = DocumentMeta(
        title_cn=meta_dict.get("title_cn"),
        title_en=meta_dict.get("title_en"),
        author=meta_dict.get("author"),
        major=meta_dict.get("major"),
        tutor=meta_dict.get("tutor"),
        extra={k: v for k, v in meta_dict.items() if k not in {"title_cn", "title_en", "author", "major", "tutor"}},
    )

    md = mistune.create_markdown(renderer="ast", plugins=["strikethrough", "table"])
    nodes = md(body)

    blocks: List[Any] = []

    for n in nodes:
        t = n.get("type")
        if t == "heading":
            level = int(n.get("level", 1))
            txt = "".join(_collect_text(n))
            blocks.append(HeadingBlock(level=level, text=txt))
        elif t == "paragraph":
            children = n.get("children", []) or []

            # page/section break markers
            plain_text = "".join(_collect_text(n)).strip()
            if plain_text in {"<!-- pagebreak -->", "<!--PAGEBREAK-->", "[[PAGEBREAK]]", "\\f"}:
                blocks.append(PageBreakBlock())
                continue
            if plain_text in {"<!-- sectionbreak -->", "<!--SECTIONBREAK-->", "[[SECTIONBREAK]]"}:
                blocks.append(SectionBreakBlock(kind="next_page"))
                continue

            # image-only paragraph -> figure block
            if len(children) == 1 and children[0].get("type") == "image":
                img = children[0]
                blocks.append(FigureBlock(path=img.get("src") or "", caption=img.get("alt") or None))
                continue

            inlines = _inlines_from_children(children)
            # collapse plain text if possible
            plain = "".join(i.text for i in inlines) if all(i.type == "text" for i in inlines) else None
            blocks.append(ParagraphBlock(text=plain, inlines=None if plain is not None else inlines))
        elif t == "list":
            ordered = bool(n.get("ordered", False))
            items: List[ListItem] = []
            for item in n.get("children", []) or []:
                # item: {'type': 'list_item', 'children': [...]}
                # collect paragraphs inside
                texts: List[Inline] = []
                for c in item.get("children", []) or []:
                    if c.get("type") == "paragraph":
                        texts.extend(_inlines_from_children(c.get("children", []) or []))
                if not texts:
                    texts = [Inline(type="text", text="".join(_collect_text(item)))]
                items.append(ListItem(inlines=texts))
            blocks.append(ListBlock(ordered=ordered, items=items))
        elif t == "table":
            rows: List[List[str]] = []
            header = n.get("header", []) or []
            if header:
                rows.append([ "".join(_collect_text(cell)) for cell in header ])
            for row in n.get("cells", []) or []:
                rows.append([ "".join(_collect_text(cell)) for cell in row ])
            blocks.append(TableBlock(rows=rows))
        elif t == "image":
            # Mistune 在 paragraph 中出现 image；这里不一定到达
            path = n.get("src") or ""
            caption = n.get("alt") or None
            blocks.append(FigureBlock(path=path, caption=caption))
        else:
            # fallback: try extract as paragraph
            txt = "".join(_collect_text(n)).strip()
            if txt:
                blocks.append(ParagraphBlock(text=txt))

    # bibliography convenience: if存在一级标题"参考文献"，后续以 [n] 开头的段落合并为 bibliography block
    blocks2: List[Any] = []
    in_ref = False
    bib_items: List[str] = []
    for b in blocks:
        if isinstance(b, HeadingBlock) and b.level == 1 and b.text.strip() in {"参考文献", "References"}:
            in_ref = True
            blocks2.append(b)
            continue
        if in_ref and isinstance(b, ParagraphBlock):
            text = (b.text or "").strip()
            if re.match(r"^\[\d+\]", text):
                bib_items.append(text)
                continue
            if bib_items:
                blocks2.append(BibliographyBlock(items=bib_items))
                bib_items = []
            blocks2.append(b)
            in_ref = False
            continue
        blocks2.append(b)
    if bib_items:
        blocks2.append(BibliographyBlock(items=bib_items))

    return DocumentAST(meta=meta, blocks=blocks2)


_HEADING_NUM_RE = re.compile(r"^\s*(\d+)([\.．](\d+))*([\.．](\d+))*\s+(.+)$")


def parse_plaintext_heuristic(text: str) -> DocumentAST:
    """
    非 Markdown 输入的兜底：按行扫描：
    - 1 / 1.1 / 1.1.1 / 1．1．1 开头的行 → heading
    - 空行分段 → paragraph
    """
    meta, body = _parse_front_matter(text)
    lines = body.splitlines()
    blocks: List[Any] = []
    para_buf: List[str] = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            t = "\n".join(para_buf).strip()
            if t:
                blocks.append(ParagraphBlock(text=t))
            para_buf = []

    for line in lines:
        if not line.strip():
            flush_para()
            continue
        if line.strip() in {"[[PAGEBREAK]]", "---pagebreak---"}:
            flush_para()
            blocks.append(PageBreakBlock())
            continue
        if line.strip() in {"[[SECTIONBREAK]]", "---sectionbreak---"}:
            flush_para()
            blocks.append(SectionBreakBlock(kind="next_page"))
            continue
        m = _HEADING_NUM_RE.match(line)
        if m:
            flush_para()
            # count levels by number of separators
            prefix = line.split()[0]
            sep_count = prefix.count(".") + prefix.count("．")
            level = min(1 + sep_count, 3)
            title = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else line.strip()
            blocks.append(HeadingBlock(level=level, text=title))
        else:
            para_buf.append(line)
    flush_para()

    dm = DocumentMeta(
        title_cn=meta.get("title_cn"),
        title_en=meta.get("title_en"),
        author=meta.get("author"),
        major=meta.get("major"),
        tutor=meta.get("tutor"),
        extra={k: v for k, v in meta.items() if k not in {"title_cn", "title_en", "author", "major", "tutor"}},
    )
    return DocumentAST(meta=dm, blocks=blocks)


# ============ AI 辅助识别功能 ============

# 论文结构关键词识别规则
STRUCTURE_PATTERNS = {
    "title_cn": [
        r"^[\u4e00-\u9fa5]{2,50}$",  # 纯中文标题
    ],
    "title_en": [
        r"^[A-Z][a-zA-Z\s\-:]+$",  # 英文标题
    ],
    "abstract_cn": [
        r"^摘\s*要[:：]?",
        r"^内容摘要[:：]?",
    ],
    "abstract_en": [
        r"^abstract[:：]?",
        r"^summary[:：]?",
    ],
    "keywords_cn": [
        r"^关键词[:：]?",
        r"^关键字[:：]?",
    ],
    "keywords_en": [
        r"^key\s*words[:：]?",
        r"^keywords[:：]?",
    ],
    "heading_1": [
        r"^第[一二三四五六七八九十]+章",
        r"^[一二三四五六七八九十]+、",
        r"^\d+[\s\.]",
    ],
    "heading_2": [
        r"^[（\(][一二三四五六七八九十]+[）\)]",
        r"^\d+\.\d+[\s\.]?",
    ],
    "heading_3": [
        r"^\d+\.\d+\.\d+[\s\.]?",
    ],
    "reference": [
        r"^参考文献",
        r"^references",
    ],
    "acknowledgement": [
        r"^致\s*谢",
        r"^谢\s*辞",
        r"^acknowledgement",
    ],
}


def identify_paragraph_type(text: str) -> str:
    """
    使用规则识别段落类型。
    返回: heading_1, heading_2, heading_3, abstract_cn, abstract_en,
          keywords_cn, keywords_en, reference, acknowledgement, body
    """
    text = text.strip()
    if not text:
        return "body"

    text_lower = text.lower()

    for para_type, patterns in STRUCTURE_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, text_lower if "en" in para_type.lower() else text, re.IGNORECASE):
                return para_type

    return "body"


async def ai_identify_paragraph_types(
    paragraphs: List[str],
    ai_service: Any,
    model: str = None
) -> List[Dict[str, str]]:
    """
    使用 AI 识别段落类型。

    参数:
        paragraphs: 段落文本列表
        ai_service: AI 服务实例
        model: 使用的模型（可选）

    返回:
        [{"text": "段落文本", "type": "heading_1|body|abstract|..."}]
    """
    # 构建识别提示词
    prompt = """你是一个论文结构识别专家。请分析以下段落，判断每个段落的类型。

可选的段落类型：
- title_cn: 中文论文标题
- title_en: 英文论文标题
- abstract_cn: 中文摘要内容
- abstract_en: 英文摘要内容
- keywords_cn: 中文关键词
- keywords_en: 英文关键词
- heading_1: 一级标题（章标题）
- heading_2: 二级标题（节标题）
- heading_3: 三级标题
- body: 正文段落
- reference: 参考文献条目
- acknowledgement: 致谢内容
- figure_caption: 图片标题
- table_caption: 表格标题

请以 JSON 数组格式返回，每个元素包含 "index" 和 "type" 字段。
只返回 JSON，不要其他文字。

待分析的段落：
"""

    for i, para in enumerate(paragraphs[:50]):  # 限制数量避免过长
        prompt += f"\n[{i}] {para[:200]}"  # 限制每段长度

    try:
        messages = [
            {"role": "system", "content": "你是一个专业的论文结构识别助手，只返回JSON格式结果。"},
            {"role": "user", "content": prompt}
        ]

        response = await ai_service.complete(messages)

        # 解析 AI 返回的 JSON
        result = json.loads(response)

        # 构建返回结果
        identified = []
        for i, para in enumerate(paragraphs):
            para_type = "body"
            for item in result:
                if item.get("index") == i:
                    para_type = item.get("type", "body")
                    break
            identified.append({"text": para, "type": para_type})

        return identified

    except Exception as e:
        # AI 识别失败时回退到规则识别
        return [{"text": para, "type": identify_paragraph_type(para)} for para in paragraphs]


def parse_plaintext_with_ai_types(
    text: str,
    paragraph_types: List[Dict[str, str]]
) -> DocumentAST:
    """
    根据 AI 识别的段落类型构建 DocumentAST。

    参数:
        text: 原始文本
        paragraph_types: AI 识别的段落类型列表

    返回:
        DocumentAST
    """
    meta = DocumentMeta()
    blocks: List[Any] = []

    for item in paragraph_types:
        para_text = item["text"].strip()
        para_type = item["type"]

        if not para_text:
            continue

        # 提取元数据
        if para_type == "title_cn":
            meta.title_cn = para_text
            blocks.append(HeadingBlock(level=1, text=para_text))
        elif para_type == "title_en":
            meta.title_en = para_text
            blocks.append(HeadingBlock(level=1, text=para_text))
        elif para_type in ("abstract_cn", "abstract_en"):
            # 摘要作为标题 + 正文
            if "摘要" in para_text[:10] or "abstract" in para_text[:20].lower():
                blocks.append(HeadingBlock(level=1, text="摘要" if "cn" in para_type else "Abstract"))
                # 去掉标题部分
                content = re.sub(r"^(摘\s*要|abstract)[:：\s]*", "", para_text, flags=re.IGNORECASE)
                if content:
                    blocks.append(ParagraphBlock(text=content))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        elif para_type in ("keywords_cn", "keywords_en"):
            # 关键词作为标题 + 正文
            if "关键词" in para_text[:10] or "关键字" in para_text[:10] or "keyword" in para_text[:20].lower():
                blocks.append(HeadingBlock(level=1, text="关键词" if "cn" in para_type else "Key words"))
                content = re.sub(r"^(关键词|关键字|key\s*words)[:：\s]*", "", para_text, flags=re.IGNORECASE)
                if content:
                    blocks.append(ParagraphBlock(text=content))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        elif para_type == "heading_1":
            blocks.append(HeadingBlock(level=1, text=para_text))
        elif para_type == "heading_2":
            blocks.append(HeadingBlock(level=2, text=para_text))
        elif para_type == "heading_3":
            blocks.append(HeadingBlock(level=3, text=para_text))
        elif para_type == "reference":
            if "参考文献" in para_text or "references" in para_text.lower():
                blocks.append(HeadingBlock(level=1, text="参考文献"))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        elif para_type == "acknowledgement":
            if "致谢" in para_text or "谢辞" in para_text or "acknowledgement" in para_text.lower():
                blocks.append(HeadingBlock(level=1, text="致谢"))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        else:
            # body 或未知类型
            blocks.append(ParagraphBlock(text=para_text))

    return DocumentAST(meta=meta, blocks=blocks)
