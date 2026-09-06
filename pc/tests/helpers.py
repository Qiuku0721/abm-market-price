from datetime import datetime


def iso(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).isoformat() + "+00:00"


def make_record(name="M80 5.56x45", price=320, captured_at="2025-09-06T12:34:56+08:00"):
    return {
        "bullet_name": name,
        "price": price,
        "currency": "Koen",
        "market_type": "market",
        "captured_at": captured_at,
        "source": "list_scan",
    }
