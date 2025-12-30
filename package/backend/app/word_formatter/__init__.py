"""
AI Word Formatter - AI 论文精确排版模块

核心功能：
1. AI 辅助识别段落类型（标题/正文/摘要等）
2. 确定性 OOXML 排版处理
3. AI 根据用户要求生成规范模板

设计理念：
- AI 仅用于"理解与结构化"（规范解析、内容识别）
- 排版与验收走确定性流程
"""

from .models.ast import DocumentAST
from .models.stylespec import StyleSpec
from .models.validation import ValidationReport
from .models.patch import Patch
from .routes import router

__all__ = [
    "DocumentAST",
    "StyleSpec",
    "ValidationReport",
    "Patch",
    "router",
]
