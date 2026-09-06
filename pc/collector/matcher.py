"""名称归一化匹配 + 价格解析（与手机端同一套启发式）。"""

from __future__ import annotations

import re

from .ocr import OcrLine

_PRICE_MAX = 10_000_000
_DIGITS = re.compile(r"\d+")


def normalize(text: str) -> str:
    """归一化：全角转半角、大小写、×/*→x、去空白，用于模糊匹配。"""
    s = text.replace("\u3000", " ")
    s = "".join(
        chr(ord(c) - 0xFF10 + 0x30) if "\uFF10" <= c <= "\uFF19" else c for c in s
    )
    return s.lower().replace("×", "x").replace("*", "x")


def compact(text: str) -> str:
    """压缩：归一化后再去掉所有空白，做子串匹配。"""
    return re.sub(r"\s+", "", normalize(text))


def clean_bullet_name(text: str, calibers: list[str] | tuple[str, ...]) -> str:
    """清洗 OCR 得到的子弹名：以已知口径子串为锚，去掉名称开头混入的杂质数字。

    例：'27.62x39毫米PSO子弹'（口径 '7.62x39毫米'）→ '7.62x39毫米PSO子弹'。
    """
    t = re.sub(r"\s+", "", (text or "").strip())
    if not t:
        return ""
    low = t.lower()
    for cal in calibers:
        key = compact(cal)
        if key:
            idx = low.find(key)
            if idx >= 0:
                t = t[idx:]
                break
    return t.strip().strip("，,。、·:：*—")


def match_lines(lines: list[OcrLine], pending: set[str]) -> list[tuple[str, OcrLine]]:
    """在 OCR 行中找清单名称（子串匹配，容忍断行缺失的除外）。"""
    found: list[tuple[str, OcrLine]] = []
    seen: set[str] = set()
    for line in lines:
        text = compact(line.text)
        for name in pending:
            key = compact(name)
            if len(key) >= 2 and key in text and name not in seen:
                seen.add(name)
                found.append((name, line))
    return found


def parse_price(snippet: str) -> int | None:
    """从价格格片段解析价格：取最后一段数字。"""
    nums = [int(m) for m in _DIGITS.findall(snippet) if int(m) > 0]
    return nums[-1] if nums else None


def vertical_overlap_ratio(a: OcrLine, top: int, bottom: int) -> float:
    ov = max(0, min(a.bottom, bottom) - max(a.top, top))
    h = max(1, a.height)
    return ov / h
