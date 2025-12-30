"""
中文字号/字体辅助。
"""
from __future__ import annotations

from typing import Dict

CHINESE_SIZE_TO_PT: Dict[str, float] = {
    "初号": 42.0,
    "小初": 36.0,
    "一号": 26.0,
    "小一": 24.0,
    "二号": 22.0,
    "小二": 18.0,
    "三号": 16.0,
    "小三": 15.0,
    "四号": 14.0,
    "小四": 12.0,
    "五号": 10.5,
    "小五": 9.0,
    "六号": 7.5,
    "小六": 6.5,
}

DEFAULT_CHINESE_FONTS = {
    "songti": "SimSun",  # 宋体
    "heiti": "SimHei",   # 黑体
    "fangsong": "FangSong",  # 仿宋
    "kaiti": "KaiTi",    # 楷体
}

DEFAULT_ENGLISH_FONTS = {
    "times": "Times New Roman",
}


def pt(size_name: str) -> float:
    if size_name not in CHINESE_SIZE_TO_PT:
        raise KeyError(f"unknown Chinese size name: {size_name}")
    return CHINESE_SIZE_TO_PT[size_name]
