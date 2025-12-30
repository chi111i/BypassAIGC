"""
Patch: 确定性修复动作集合。
"""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class PatchAction(BaseModel):
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class Patch(BaseModel):
    actions: List[PatchAction] = Field(default_factory=list)
