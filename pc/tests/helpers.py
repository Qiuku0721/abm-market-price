from datetime import datetime, timezone
from types import SimpleNamespace


def iso(ts: float) -> str:
    # fromtimestamp().isoformat() 已含 +00:00 偏移，勿再拼接
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def make_record(name="M80 5.56x45", price=320, captured_at="2025-09-06T12:34:56+08:00"):
    return {
        "bullet_name": name,
        "price": price,
        "currency": "Koen",
        "market_type": "market",
        "captured_at": captured_at,
        "source": "list_scan",
        "snapshot_id": None,
    }


def make_record_obj(*args, **kwargs):
    """供直接调用 db.add_records 的测试使用（其期望属性对象而非 dict）。"""
    return SimpleNamespace(**make_record(*args, **kwargs))
