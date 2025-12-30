"""
StyleSpec: 可执行排版规范（强约束 JSON）。
本文件用 Pydantic 定义数据结构，并可导出 JSON Schema 供前端/接口校验。

设计目标：
- 足够表达论文排版的确定性规则（页边距、样式表、编号绑定、禁用直接格式等）
- 不把"写 docx 的 OOXML 细节"暴露给 AI/用户
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


Alignment = Literal["left", "center", "right", "justify"]
LineSpacingRule = Literal["single", "1.5", "double", "exact"]


class MarginMM(BaseModel):
    top: float = Field(..., ge=0)
    bottom: float = Field(..., ge=0)
    left: float = Field(..., ge=0)
    right: float = Field(..., ge=0)
    binding: float = Field(0, ge=0, description="装订线（gutter）mm")


class PageSpec(BaseModel):
    size: Literal["A4"] = "A4"
    margins_mm: MarginMM
    header_mm: float = Field(0, ge=0)
    footer_mm: float = Field(0, ge=0)


class FontMapping(BaseModel):
    # Word 对中文字体一般用 eastAsia；英文用 ascii/hAnsi
    eastAsia: str
    ascii: str
    hAnsi: str


class StyleParagraph(BaseModel):
    alignment: Alignment = "justify"
    line_spacing_rule: LineSpacingRule = "single"
    line_spacing: Optional[float] = Field(
        None, description="当 rule=exact 时表示 pt；否则可为空"
    )
    # Spacing can be expressed either in points (pt) or in lines.
    # If both are provided, *_lines takes precedence.
    space_before_pt: float = Field(0, ge=0)
    space_after_pt: float = Field(0, ge=0)
    space_before_lines: Optional[float] = Field(
        None, ge=0, description="段前间距（行），例如 0.5 表示半行"
    )
    space_after_lines: Optional[float] = Field(
        None, ge=0, description="段后间距（行），例如 0.5 表示半行"
    )
    first_line_indent_chars: float = Field(0, ge=0, description="首行缩进（字符数）")
    hanging_indent_chars: float = Field(0, ge=0, description="悬挂缩进（字符数）")
    keep_with_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False
    widows_control: bool = True


class StyleRun(BaseModel):
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size_pt: float = Field(..., gt=0)
    font: FontMapping


class StyleDef(BaseModel):
    """
    一个可复用"段落样式"定义。
    注意：我们把字体/字号等放在 StyleRun 里，段落属性放在 StyleParagraph 里。
    """
    style_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    based_on: Optional[str] = None
    is_heading: bool = False
    outline_level: Optional[int] = Field(
        None, ge=0, le=8, description="heading/outlining level"
    )
    run: StyleRun
    paragraph: StyleParagraph


class NumberingLevel(BaseModel):
    level: int = Field(..., ge=0, le=8)
    style_id: str
    start: int = Field(1, ge=1)
    fmt: Literal["decimal"] = "decimal"
    lvl_text: str = Field(..., description="例如 %1．%2")
    suffix: Literal["space", "tab", "nothing"] = "space"


class NumberingSpec(BaseModel):
    abstract_num_id: int = Field(1, ge=1)
    num_id: int = Field(1, ge=1)
    levels: List[NumberingLevel]


class ForbiddenDirectFormatting(BaseModel):
    font: bool = True
    size: bool = True
    bold: bool = True
    italic: bool = True
    underline: bool = True
    color: bool = True


class StructureSpec(BaseModel):
    """
    结构约束：例如必须出现 摘要/关键词/Abstract/Key words/致谢/参考文献 等一级标题。
    """
    required_h1_titles: List[str] = Field(default_factory=list)
    toc_max_level: int = Field(3, ge=1, le=8)


PageNumFormat = Literal["romanUpper", "romanLower", "decimal"]


class PageNumberingSpec(BaseModel):
    """页面页码规则（可选）。

    说明：Word 的页码格式/起始页需要分节（sectPr）来实现；渲染器会插入分节符并通过 OOXML 后处理设置。
    """

    enabled: bool = True
    front_format: PageNumFormat = "romanUpper"
    front_start: int = Field(1, ge=1)
    main_format: PageNumFormat = "decimal"
    main_start: int = Field(1, ge=1)
    show_in_footer: bool = True
    footer_alignment: Alignment = "center"


class StyleSpec(BaseModel):
    meta: Dict[str, str] = Field(default_factory=dict)
    page: PageSpec
    styles: Dict[str, StyleDef]
    numbering: Optional[NumberingSpec] = None
    structure: StructureSpec = Field(default_factory=StructureSpec)
    forbidden_direct_formatting: ForbiddenDirectFormatting = Field(
        default_factory=ForbiddenDirectFormatting
    )
    page_numbering: Optional[PageNumberingSpec] = None

    # Small, deterministic content-normalization switches (optional):
    # They help enforce school templates without letting AI touch OOXML.
    auto_prefix_abstract_keywords: bool = False
    auto_number_figures_tables: bool = False

    @field_validator("styles")
    @classmethod
    def _style_ids_must_match_keys(cls, v: Dict[str, StyleDef]):
        for k, s in v.items():
            if k != s.style_id:
                raise ValueError(f"styles key '{k}' must equal style_id '{s.style_id}'")
        return v

    def to_schema(self) -> dict:
        return self.model_json_schema()
