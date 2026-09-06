"""统计计算：最新价 + 相对前一观测的涨跌。"""

from __future__ import annotations

from .database import Database


def latest_with_delta(db: Database) -> dict:
    """{bullet_name: {…, prev_price, delta, delta_pct}}，无前值的项 delta 为 null。"""
    latest = db.latest()
    prev_map = {r["bullet_name"]: r for r in db.previous_prices()}
    out: dict[str, dict] = {}
    for r in latest:
        name = r["bullet_name"]
        item = dict(r)
        prev = prev_map.get(name)
        if prev and prev["price"]:
            item["prev_price"] = prev["price"]
            item["delta"] = r["price"] - prev["price"]
            item["delta_pct"] = round((r["price"] - prev["price"]) / prev["price"] * 100, 2)
        else:
            item["prev_price"] = None
            item["delta"] = None
            item["delta_pct"] = None
        out[name] = item
    return out
