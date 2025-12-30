"""
word_formatter 数据模型层
"""

from .ast import DocumentAST, DocumentMeta, HeadingBlock, ParagraphBlock
from .stylespec import StyleSpec, StyleDef, PageSpec
from .validation import ValidationReport, Violation
from .patch import Patch, PatchAction

__all__ = [
    "DocumentAST",
    "DocumentMeta",
    "HeadingBlock",
    "ParagraphBlock",
    "StyleSpec",
    "StyleDef",
    "PageSpec",
    "ValidationReport",
    "Violation",
    "Patch",
    "PatchAction",
]
