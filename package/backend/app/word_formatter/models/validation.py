"""
ValidationReport: docx 规则验收输出。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["info", "warning", "error"]


class Location(BaseModel):
    paragraph_index: Optional[int] = None
    text_snippet: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)


class FixSuggestion(BaseModel):
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class Violation(BaseModel):
    violation_id: str
    severity: Severity = "error"
    message: str
    location: Location = Field(default_factory=Location)
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    suggestion: Optional[FixSuggestion] = None


class ValidationSummary(BaseModel):
    ok: bool
    errors: int = 0
    warnings: int = 0
    infos: int = 0


class ValidationReport(BaseModel):
    summary: ValidationSummary
    violations: List[Violation] = Field(default_factory=list)
