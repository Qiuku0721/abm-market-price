from datetime import datetime

from app.stats import latest_with_delta

from .helpers import iso, make_record_obj as make_record


def test_delta_up_down_none(db):
    base = datetime(2025, 9, 6, 4, 0, 0).timestamp()
    db.add_records("dev-1", None, [
        make_record(name="A", price=100, captured_at=iso(base)),
        make_record(name="A", price=110, captured_at=iso(base + 60)),  # +10
        make_record(name="B", price=200, captured_at=iso(base)),
        make_record(name="B", price=150, captured_at=iso(base + 60)),  # -50
        make_record(name="C", price=99, captured_at=iso(base)),        # 仅一条，无前值
    ])

    d = latest_with_delta(db)
    assert d["A"]["price"] == 110 and d["A"]["delta"] == 10 and d["A"]["delta_pct"] == 10.0
    assert d["B"]["price"] == 150 and d["B"]["delta"] == -50 and d["B"]["delta_pct"] == -25.0
    assert d["C"]["delta"] is None
