"""标准子弹名清单 + OCR 名称纠错（采集入库 / 网页展示 / 历史批量修复共用）。

用法：normalize_bullet_name(ocr_name) -> 标准子弹名。
策略：清前缀杂质 → 精确匹配（大小写/空白归一）→ 按口径缩小候选后，仅在"型号段"内做模糊匹配。
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# 左栏口径顺序（用于去掉名称前缀杂质 & 按口径缩小匹配范围）
CALIBERS = [
    "7.62x39毫米", "7.62x54毫米", "5.56x45毫米", "9x19毫米",
    "7.62x51毫米", "5.7x28毫米", "9x39毫米", "5.45x39毫米", "12.7x99毫米",
    ".44口径", ".45口径", "7.62x25毫米", ".338口径", "5.8x42毫米",
]

# 标准子弹名（游戏内口径分组，权威清单）
STANDARD_BULLETS: list[str] = [
    "7.62x39毫米LP子弹", "7.62x39毫米US子弹", "7.62x39毫米PS子弹",
    "7.62x39毫米HP子弹", "7.62x39毫米T45M子弹", "7.62x39毫米BP子弹", "7.62x39毫米AP子弹",
    "7.62x54毫米T46M子弹", "7.62x54毫米LPS子弹", "7.62x54毫米7BT1子弹",
    "7.62x54毫米7N37子弹", "7.62x54毫米SNB子弹",
    "5.56x45毫米M193子弹", "5.56x45毫米FMJ狩猎弹", "5.56x45毫米M855子弹",
    "5.56x45毫米HP狩猎弹", "5.56x45毫米M855A1子弹", "5.56x45毫米M995子弹",
    "9x19毫米PSO子弹", "9x19毫米Pst子弹", "9x19毫米AP6.3子弹",
    "9x19毫米达姆弹", "9x19毫米7N31子弹",
    "7.62x51毫米UN子弹", "7.62x51毫米BPZ子弹", "7.62x51毫米M80子弹",
    "7.62x51毫米M62子弹", "7.62x51毫米M61子弹",
    "5.7x28毫米SS197SR子弹", "5.7x28毫米R37.X子弹", "5.7x28毫米L191子弹",
    "5.7x28毫米R37.F子弹", "5.7x28毫米SS190子弹", "5.7x28毫米SS198子弹",
    "9x39毫米SP5子弹", "9x39毫米SP6子弹", "9x39毫米7N9子弹", "9x39毫米7N12子弹",
    "5.45x39毫米PRS子弹", "5.45x39毫米PS子弹", "5.45x39毫米PP子弹",
    "5.45x39毫米HP子弹", "5.45x39毫米BP子弹", "5.45x39毫米BS子弹",
    "12.7x99毫米M2子弹",
    ".44口径LFNP子弹", ".44口径SJHP子弹", ".44口径JSP子弹",
    ".45口径FMJ子弹", ".45口径HS子弹", ".45口径AP子弹",
    "7.62x25毫米PT子弹", "7.62x25毫米LRN子弹", "7.62x25毫米AKBS子弹", "7.62x25毫米Pst子弹",
    ".338口径UPZ子弹", ".338口径FMJ子弹", ".338口径AP子弹",
    "5.8x42毫米DBP87子弹", "5.8x42毫米DVP88子弹", "5.8x42毫米DVC12子弹",
]

_TAIL = re.compile(r"(子弹|狩猎弹)$")


def _halfwidth(s: str) -> str:
    """全角字符转半角，并将 OCR 常见的乘号/星号统一为字母 x（口径锚用的是 'x'）。"""
    s = "".join(chr(ord(c) - 0xFEE0) if "\uFF01" <= c <= "\uFF5E" else c for c in s)
    return s.replace("×", "x").replace("＊", "*")


def _norm(s: str) -> str:
    return _halfwidth(re.sub(r"\s+", "", (s or "").lower()))


def _strip_prefix(name: str) -> tuple[str, bool]:
    """去掉名称开头被 OCR 混入的杂质数字（以口径为锚）。返回 (清洗后文本, 是否匹配到口径)。"""
    t = _halfwidth(re.sub(r"\s+", "", (name or "").strip()))
    if not t:
        return "", False
    low = t.lower()
    for c in CALIBERS:
        i = low.find(c.lower())
        if i >= 0:
            return t[i:], True
    return (name or "").strip(), False


def _model(name: str) -> str:
    """提取型号段：去掉口径前缀与「子弹/狩猎弹」后缀。"""
    nt = _norm(name)
    for c in CALIBERS:
        if c.lower() in nt:
            nt = nt.replace(c.lower(), "", 1)
            break
    return _TAIL.sub("", nt)


def normalize_bullet_name(name) -> str:
    """把 OCR 识别名归一到标准子弹名（清前缀 + 精确 + 型号段模糊匹配）。"""
    t, found = _strip_prefix(name)
    if not t:
        return name
    if not found:
        # 非子弹清单里的名称（如自定义项）：保持原样，不动空格
        return (name or "").strip()

    nt = _norm(t)
    for std in STANDARD_BULLETS:
        if _norm(std) == nt:
            return std

    cal = next((c for c in CALIBERS if c.lower() in nt), "")
    cands = [s for s in STANDARD_BULLETS if cal and cal.lower() in _norm(s)] if cal else STANDARD_BULLETS
    mt = _model(t)
    best, best_r = None, 0.0
    for s in cands:
        r = SequenceMatcher(None, mt, _model(s)).ratio()
        if r > best_r:
            best, best_r = s, r
    # 仅当型号段足够相近才采用标准名，避免误配
    if best and best_r >= 0.6:
        return best
    return t
