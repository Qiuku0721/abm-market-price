"""财报生成：整点小时财报 / 晚间当日财报 + 基于经济学的次日前瞻建议。

预测采用可解释的规则模型（非黑盒）：结合「价格在当日区间的位置（均值回归）、
日内动量、振幅（波动/价差空间）、活跃度」给每种子弹打分，得出"次日前瞻买入/谨慎"信号。
仅用于游戏内倒卖参考，非投资建议。
"""

from __future__ import annotations

import statistics as st
from typing import Any


def _agg(db, start: int, end: int) -> list[dict]:
    rows = db.conn.execute(
        """
        SELECT bullet_name,
               MAX(price) AS high, MIN(price) AS low, COUNT(*) AS n,
               (SELECT price FROM price_records p2
                 WHERE p2.bullet_name = p.bullet_name
                   AND p2.captured_epoch >= ? AND p2.captured_epoch <= ?
                 ORDER BY p2.captured_epoch ASC LIMIT 1) AS open_p,
               (SELECT price FROM price_records p3
                 WHERE p3.bullet_name = p.bullet_name
                   AND p3.captured_epoch >= ? AND p3.captured_epoch <= ?
                 ORDER BY p3.captured_epoch DESC LIMIT 1) AS close_p
        FROM price_records p
        WHERE captured_epoch >= ? AND captured_epoch <= ?
        GROUP BY bullet_name
        """,
        (start, end, start, end, start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def _metrics(r: dict) -> dict | None:
    hi, lo, op, cl, n = r["high"], r["low"], r["open_p"], r["close_p"], r["n"]
    if not hi or not lo:
        return None
    mid = (hi + lo) / 2 or 1.0
    return {
        "high": hi, "low": lo, "open": op, "close": cl, "count": n,
        "pos": (cl - lo) / (hi - lo) if hi > lo else 0.5,   # 0=当日最低 1=当日最高
        "mom": (cl - op) / op if op else 0.0,               # 时段动量
        "spread": (hi - lo) / mid,                          # 振幅
    }


def _summarize(db, start: int, end: int) -> list[dict]:
    out = []
    for r in _agg(db, start, end):
        m = _metrics(r)
        if m:
            out.append({**r, **m})
    return out


def _reasons(item: dict) -> list[str]:
    rs = []
    if item["pos"] <= 0.4:
        rs.append("处于当日价格区间低位")
    if item["mom"] > 0.02:
        rs.append("当日呈上涨动量")
    elif item["mom"] < -0.02:
        rs.append("当日呈下跌动量")
    if item["spread"] >= 0.06:
        rs.append("日内振幅大、具备价差空间")
    if item["count"] >= 10:
        rs.append("交易活跃、数据可信")
    # 均值回归视角
    if item["pos"] <= 0.35 and item["mom"] > 0:
        rs.append("低位回升，均值回归更倾向反弹")
    if item["pos"] >= 0.8 and item["mom"] < 0:
        rs.append("高位滞涨，短期回落风险")
    return rs or ["数据充分，按既有波动跟踪"]


def gen_hourly(db, start: int, end: int, period_str: str) -> dict | None:
    infos = _summarize(db, start, end)
    if not infos:
        return None
    up = max(infos, key=lambda x: x["mom"])
    down = min(infos, key=lambda x: x["mom"])
    vol = max(infos, key=lambda x: x["spread"])
    records = sum(i["count"] for i in infos)
    content = "\n".join([
        f"# 小时财报 · {period_str}",
        f"- 采集 {len(infos)} 种子弹，共 {records} 条记录",
        f"- 涨幅居前：{up['bullet_name']}（{up['mom'] * 100:+.1f}%）",
        f"- 跌幅居前：{down['bullet_name']}（{down['mom'] * 100:+.1f}%）",
        f"- 波动最大：{vol['bullet_name']}（振幅 {vol['spread'] * 100:.0f}%）",
        "",
    ])
    return {
        "kind": "hourly", "period_key": period_str, "title": f"小时财报 {period_str}",
        "content": content,
        "stats": {"period": period_str, "n_bullets": len(infos), "n_records": records,
                  "top": up["bullet_name"], "worst": down["bullet_name"], "vol": vol["bullet_name"]},
    }


def gen_daily(db, start: int, end: int, period_str: str) -> dict | None:
    infos = _summarize(db, start, end)
    if not infos:
        return None
    counts = [i["count"] for i in infos]
    base = st.median(counts) or 1

    for i in infos:
        i["score"] = (
            0.30 * (1 - i["pos"])
            + 0.25 * min(i["spread"] / 0.15, 1.0)
            + (0.20 if i["mom"] > 0.02 else 0.05 if i["mom"] > 0 else -0.05)
            + 0.10 * min(i["count"] / base, 1.0)
        )

    ranked = sorted(infos, key=lambda x: -x["score"])
    buys = ranked[:3]
    cautions = ranked[-3:]
    records = sum(i["count"] for i in infos)

    lines = [
        f"# 当日财报 · {period_str}",
        f"- 共采集 {len(infos)} 种子弹，{records} 条记录",
        "",
        "## 明日投资前瞻（倒卖参考）",
        "> 依据：价格区间位置（均值回归）、日内动量、振幅（价差空间）、成交活跃度综合打分。",
    ]
    lines.append("\n**⭐ 建议关注买入：**")
    for b in buys:
        lines.append(f"- {b['bullet_name']}（分数 {b['score']:.2f}）：" + "；".join(_reasons(b)))
    lines.append("\n**⚠ 谨慎 / 考虑规避：**")
    for c in cautions:
        lines.append(f"- {c['bullet_name']}（分数 {c['score']:.2f}）：" + "；".join(_reasons(c)))
    lines.append("\n*规则模型仅供游戏内倒卖参考，不构成投资建议。*")
    content = "\n".join(lines)

    return {
        "kind": "daily", "period_key": period_str, "title": f"当日财报 {period_str}",
        "content": content,
        "stats": {"period": period_str, "n_bullets": len(infos), "n_records": records,
                  "recommend": [b["bullet_name"] for b in buys],
                  "caution": [c["bullet_name"] for c in cautions]},
    }


def generate(db, kind: str, start: int, end: int, period_str: str) -> dict | None:
    """生成并入库；返回报告 dict（已存在则返回既有报告）。"""
    from .database import Database  # noqa: F401

    fn = gen_hourly if kind == "hourly" else gen_daily
    report = fn(db, start, end, period_str)
    if not report:
        return None
    inserted = db.insert_report(report["kind"], report["period_key"],
                                report["title"], report["content"], report["stats"])
    if not inserted:
        return db.latest_report(kind)
    return report
