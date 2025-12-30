"""
DocumentAST: 结构化内容表示（确定性编译输入）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


InlineType = Literal["text", "bold", "italic", "underline", "superscript", "subscript", "code"]


class Inline(BaseModel):
    type: InlineType
    text: str


BlockType = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "figure",
    "page_break",
    "section_break",
    "bibliography",
]


class HeadingBlock(BaseModel):
    type: Literal["heading"] = "heading"
    level: int = Field(..., ge=1, le=8)
    text: str


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: Optional[str] = None
    inlines: Optional[List[Inline]] = None

    @field_validator("text")
    @classmethod
    def _text_or_inlines(cls, v, info):
        # allow None if inlines provided
        return v


class ListItem(BaseModel):
    inlines: List[Inline]


class ListBlock(BaseModel):
    type: Literal["list"] = "list"
    ordered: bool = False
    items: List[ListItem]


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    rows: List[List[str]]
    caption: Optional[str] = None


class FigureBlock(BaseModel):
    type: Literal["figure"] = "figure"
    path: str
    caption: Optional[str] = None


class PageBreakBlock(BaseModel):
    type: Literal["page_break"] = "page_break"


class SectionBreakBlock(BaseModel):
    type: Literal["section_break"] = "section_break"
    kind: Literal["next_page"] = "next_page"


class BibliographyBlock(BaseModel):
    type: Literal["bibliography"] = "bibliography"
    items: List[str]


Block = Union[
    HeadingBlock,
    ParagraphBlock,
    ListBlock,
    TableBlock,
    FigureBlock,
    PageBreakBlock,
    SectionBreakBlock,
    BibliographyBlock,
]


class DocumentMeta(BaseModel):
    title_cn: Optional[str] = None
    title_en: Optional[str] = None
    author: Optional[str] = None
    major: Optional[str] = None
    tutor: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class DocumentAST(BaseModel):
    meta: DocumentMeta = Field(default_factory=DocumentMeta)
    blocks: List[Block]
