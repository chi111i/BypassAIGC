"""
规范生成器（Spec Generator）

功能：
1. 内置论文规范（通用中文论文格式）
2. 自定义 JSON 导入与校验
3. AI 根据用户要求生成规范模板
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..models.stylespec import (
    FontMapping,
    ForbiddenDirectFormatting,
    MarginMM,
    NumberingLevel,
    NumberingSpec,
    PageNumberingSpec,
    PageSpec,
    StructureSpec,
    StyleDef,
    StyleParagraph,
    StyleRun,
    StyleSpec,
)
from ..utils.chinese import DEFAULT_CHINESE_FONTS, DEFAULT_ENGLISH_FONTS, pt


def _font(ch: str, en: str) -> FontMapping:
    return FontMapping(eastAsia=ch, ascii=en, hAnsi=en)


def build_generic_spec(first_line_indent: bool = True) -> StyleSpec:
    """
    构建通用中文论文格式规范。

    参数:
        first_line_indent: 正文是否首行缩进2字符（默认True）

    返回:
        StyleSpec 对象
    """
    page = PageSpec(
        size="A4",
        margins_mm=MarginMM(top=25, bottom=20, left=25, right=20, binding=5),
        header_mm=15,
        footer_mm=15,
    )

    # fonts
    song = DEFAULT_CHINESE_FONTS["songti"]
    hei = DEFAULT_CHINESE_FONTS["heiti"]
    fang = DEFAULT_CHINESE_FONTS["fangsong"]
    kai = DEFAULT_CHINESE_FONTS["kaiti"]
    times = DEFAULT_ENGLISH_FONTS["times"]

    # styles
    styles = {}

    def add_style(
        style_id: str,
        name: str,
        ch_font: str,
        en_font: str,
        size_pt: float,
        bold: bool = False,
        align: str = "justify",
        before: float = 0,
        after: float = 0,
        before_lines: float | None = None,
        after_lines: float | None = None,
        first_indent_chars: float = 0,
        keep_with_next: bool = False,
        is_heading: bool = False,
        outline_level: int | None = None,
    ):
        styles[style_id] = StyleDef(
            style_id=style_id,
            name=name,
            based_on=None,
            is_heading=is_heading,
            outline_level=outline_level,
            run=StyleRun(
                bold=bold,
                italic=False,
                underline=False,
                size_pt=size_pt,
                font=_font(ch_font, en_font),
            ),
            paragraph=StyleParagraph(
                alignment=align,
                line_spacing_rule="single",
                line_spacing=None,
                space_before_pt=before,
                space_after_pt=after,
                space_before_lines=before_lines,
                space_after_lines=after_lines,
                first_line_indent_chars=first_indent_chars,
                hanging_indent_chars=0,
                keep_with_next=keep_with_next,
                keep_lines=False,
                page_break_before=False,
                widows_control=True,
            ),
        )

    # Front matter headings
    add_style("FrontHeading", "Front Matter Heading", hei, times, pt("四号"), bold=False, align="center", before=0, after=0)
    add_style("TitleCN", "Title CN", hei, times, pt("三号"), bold=False, align="center", before=0, after=12)
    add_style("TitleEN", "Title EN", times, times, pt("三号"), bold=False, align="center", before=0, after=12)
    add_style("MetaLine", "Meta Line", song, times, pt("小四"), bold=False, align="center", before=0, after=0)

    # Abstract body
    add_style("AbstractBody", "Abstract Body", song, times, pt("五号"), bold=False, align="justify", before=0, after=0, first_indent_chars=0)
    add_style("KeywordsBody", "Keywords Body", song, times, pt("五号"), bold=False, align="justify", before=0, after=0, first_indent_chars=0)

    # Main body
    body_indent = 2 if first_line_indent else 0
    add_style("Body", "Body", song, times, pt("小四"), bold=False, align="justify", before=0, after=0, first_indent_chars=body_indent)

    # Lists
    add_style("ListBullet", "List Bullet", song, times, pt("小四"), bold=False, align="justify", before=0, after=0, first_indent_chars=0)
    add_style("ListNumber", "List Number", song, times, pt("小四"), bold=False, align="justify", before=0, after=0, first_indent_chars=0)

    # Page number
    add_style("PageNumber", "Page Number", song, times, pt("五号"), bold=False, align="center", before=0, after=0, first_indent_chars=0)

    # Headings with numbering
    add_style(
        "H1", "Heading Level 1", fang, times, pt("四号"),
        bold=False, align="left", before=0, after=0,
        before_lines=0.5, after_lines=0.5, first_indent_chars=0,
        keep_with_next=True, is_heading=True, outline_level=0,
    )
    add_style("H2", "Heading Level 2", hei, times, pt("小四"), bold=False, align="left", before=0, after=0, first_indent_chars=0, keep_with_next=True, is_heading=True, outline_level=1)
    add_style("H3", "Heading Level 3", fang, times, pt("小四"), bold=False, align="left", before=0, after=0, first_indent_chars=0, keep_with_next=True, is_heading=True, outline_level=2)

    # Captions & table
    add_style("FigureCaption", "Figure Caption", hei, times, pt("小五"), bold=False, align="center", before=6, after=6)
    add_style("TableTitle", "Table Title", hei, times, pt("小五"), bold=False, align="center", before=6, after=6)
    add_style("TableText", "Table Text", song, times, pt("六号"), bold=False, align="center", before=0, after=0)

    # References
    add_style("Reference", "Reference", song, times, pt("五号"), bold=False, align="justify", before=0, after=0, first_indent_chars=0)

    numbering = NumberingSpec(
        abstract_num_id=1,
        num_id=1,
        levels=[
            NumberingLevel(level=0, style_id="H1", start=1, fmt="decimal", lvl_text="%1", suffix="space"),
            NumberingLevel(level=1, style_id="H2", start=1, fmt="decimal", lvl_text="%1．%2", suffix="space"),
            NumberingLevel(level=2, style_id="H3", start=1, fmt="decimal", lvl_text="%1．%2．%3", suffix="space"),
        ],
    )

    structure = StructureSpec(
        required_h1_titles=["摘要", "Abstract", "引言", "致谢", "参考文献"],
        toc_max_level=3,
    )

    spec = StyleSpec(
        meta={"name": "Generic_CN", "version": "1.0", "notes": "通用中文论文格式规范"},
        page=page,
        styles=styles,
        numbering=numbering,
        structure=structure,
        forbidden_direct_formatting=ForbiddenDirectFormatting(),
        page_numbering=PageNumberingSpec(
            enabled=True,
            front_format="romanUpper",
            front_start=1,
            main_format="decimal",
            main_start=1,
            show_in_footer=True,
            footer_alignment="center"
        ),
        auto_prefix_abstract_keywords=True,
        auto_number_figures_tables=True,
    )
    return spec


def builtin_specs() -> Dict[str, StyleSpec]:
    """获取所有内置规范"""
    return {
        "Generic_CN": build_generic_spec(first_line_indent=True),
        "Generic_CN_NoIndent": build_generic_spec(first_line_indent=False),
    }


# ============ AI 生成规范模板功能 ============

AI_SPEC_GENERATION_PROMPT = """你是一个论文排版专家。请根据用户的要求生成论文排版规范模板。

用户要求：
{requirements}

请生成一个 JSON 格式的规范模板，包含以下字段：

{{
    "meta": {{
        "name": "规范名称",
        "version": "1.0",
        "notes": "规范说明"
    }},
    "page": {{
        "size": "A4",
        "margins_mm": {{
            "top": 页边距上(mm),
            "bottom": 页边距下(mm),
            "left": 页边距左(mm),
            "right": 页边距右(mm),
            "binding": 装订线(mm，默认0)
        }},
        "header_mm": 页眉距离(mm),
        "footer_mm": 页脚距离(mm)
    }},
    "styles": {{
        "Body": {{
            "style_id": "Body",
            "name": "正文",
            "is_heading": false,
            "run": {{
                "bold": false,
                "italic": false,
                "underline": false,
                "size_pt": 字号(pt),
                "font": {{
                    "eastAsia": "中文字体名",
                    "ascii": "英文字体名",
                    "hAnsi": "英文字体名"
                }}
            }},
            "paragraph": {{
                "alignment": "justify",
                "line_spacing_rule": "single|1.5|double|exact",
                "first_line_indent_chars": 首行缩进字符数
            }}
        }},
        // 其他样式...
    }},
    "structure": {{
        "required_h1_titles": ["摘要", "Abstract", "引言", "致谢", "参考文献"],
        "toc_max_level": 3
    }}
}}

常用中文字号对应表：
- 初号: 42pt, 小初: 36pt
- 一号: 26pt, 小一: 24pt
- 二号: 22pt, 小二: 18pt
- 三号: 16pt, 小三: 15pt
- 四号: 14pt, 小四: 12pt
- 五号: 10.5pt, 小五: 9pt
- 六号: 7.5pt, 小六: 6.5pt

常用中文字体：
- 宋体: SimSun
- 黑体: SimHei
- 仿宋: FangSong
- 楷体: KaiTi

常用英文字体：
- Times New Roman

请只返回 JSON，不要其他文字。确保 JSON 格式正确。
"""


async def ai_generate_spec(
    requirements: str,
    ai_service: Any,
    model: str = None
) -> StyleSpec:
    """
    使用 AI 根据用户要求生成规范模板。

    参数:
        requirements: 用户的规范要求描述
        ai_service: AI 服务实例
        model: 使用的模型（可选）

    返回:
        StyleSpec 对象
    """
    prompt = AI_SPEC_GENERATION_PROMPT.format(requirements=requirements)

    messages = [
        {"role": "system", "content": "你是一个专业的论文排版规范生成助手，只返回标准JSON格式。"},
        {"role": "user", "content": prompt}
    ]

    try:
        response = await ai_service.complete(messages)

        # 尝试解析 JSON
        # 移除可能的 markdown 代码块标记
        json_str = response.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        spec_dict = json.loads(json_str.strip())

        # 验证并构建 StyleSpec
        spec = StyleSpec.model_validate(spec_dict)
        return spec

    except json.JSONDecodeError as e:
        raise ValueError(f"AI 返回的规范格式不正确: {e}")
    except Exception as e:
        raise ValueError(f"生成规范失败: {e}")


def validate_custom_spec(spec_json: str) -> StyleSpec:
    """
    验证用户自定义的 JSON 规范。

    参数:
        spec_json: JSON 字符串

    返回:
        StyleSpec 对象

    抛出:
        ValueError: 如果 JSON 格式不正确或规范无效
    """
    try:
        spec_dict = json.loads(spec_json)
        spec = StyleSpec.model_validate(spec_dict)
        return spec
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {e}")
    except Exception as e:
        raise ValueError(f"规范验证失败: {e}")


def export_spec_to_json(spec: StyleSpec) -> str:
    """
    将规范导出为 JSON 字符串。

    参数:
        spec: StyleSpec 对象

    返回:
        格式化的 JSON 字符串
    """
    return spec.model_dump_json(indent=2, exclude_none=True)


def get_spec_schema() -> dict:
    """获取 StyleSpec 的 JSON Schema"""
    return StyleSpec.model_json_schema()
