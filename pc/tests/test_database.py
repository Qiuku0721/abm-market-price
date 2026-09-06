from datetime import datetime

from app.database import parse_epoch

from .helpers import iso, make_record_obj as make_record


def test_parse_epoch_variants():
    assert parse_epoch("2025-09-06T12:34:56+08:00") is not None
    assert parse_epoch("2025-09-06T04:34:56Z") is not None
    assert parse_epoch("bad-time") is None
    assert parse_epoch("") is None


def test_add_records_accept_dedup_reject(db):
    ok = make_record(price=320, captured_at="2025-09-06T12:34:56+08:00")
    dup = make_record(price=320, captured_at="2025-09-06T12:35:10+08:00")  # 同分钟同价
    changed = make_record(price=333, captured_at="2025-09-06T12:35:40+08:00")  # 同分钟不同价
    bad = make_record(captured_at="not-a-time")

    r1 = db.add_records("dev-1", "127.0.0.1", [ok, dup, changed, bad])
    assert r1["accepted"] == 3
    assert r1["duplicates"] == 0
    assert r1["rejected"] == [{"index": 3, "reason": "bad captured_at"}]

    # 原样重放 → 全部判重
    r2 = db.add_records("dev-1", "127.0.0.1", [ok, dup, changed])
    assert r2["accepted"] == 0
    assert r2["duplicates"] == 3

    # 其他设备同数据不算重复
    r3 = db.add_records("dev-2", "127.0.0.1", [ok])
    assert r3["accepted"] == 1


def test_bullets_autoadd_and_manage(db):
    db.add_records("dev-1", None, [make_record(), make_record(name="M855 5.56x45", price=400)])
    names = {b["name"] for b in db.bullets()}
    assert names == {"M80 5.56x45", "M855 5.56x45"}

    assert db.add_bullet("M80 5.56x45") is False  # 已存在
    assert db.add_bullet("M995 5.56x45") is True
    db.set_bullet_active("M995 5.56x45", False)
    state = {b["name"]: b["active"] for b in db.bullets()}
    assert state["M995 5.56x45"] == 0
    assert db.delete_bullet("M995 5.56x45") is True
    assert db.delete_bullet("不存在的") is False


def test_latest_previous_trend(db):
    base = datetime(2025, 9, 6, 4, 0, 0).timestamp()
    db.add_records("dev-1", None, [
        make_record(price=300, captured_at=iso(base + 0)),
        make_record(price=310, captured_at=iso(base + 120)),
        make_record(price=305, captured_at=iso(base + 240)),
        make_record(name="M855 5.56x45", price=400, captured_at=iso(base + 60)),
    ])

    latest = db.latest()
    by_name = {r["bullet_name"]: r for r in latest}
    assert by_name["M80 5.56x45"]["price"] == 305
    assert by_name["M855 5.56x45"]["price"] == 400

    prev = {r["bullet_name"]: r for r in db.previous_prices()}
    assert prev["M80 5.56x45"]["price"] == 310

    trend = db.trend("M80 5.56x45", bucket_sec=60,
                     from_epoch=int(base), to_epoch=int(base + 300))
    assert [p["price"] for p in trend] == [300, 310, 305]


def test_records_filter_paging(db):
    base = datetime(2025, 9, 6, 4, 0, 0).timestamp()
    recs = [make_record(price=100 + i, captured_at=iso(base + i)) for i in range(10)]
    db.add_records("dev-1", None, recs)

    rows, total = db.records(limit=4, offset=0)
    assert total == 10 and len(rows) == 4

    rows2, _ = db.records(from_epoch=int(base + 3), to_epoch=int(base + 6))
    # i=3..6 -> price 103..106，按时间倒序
    assert [r["price"] for r in rows2] == [106, 105, 104, 103]


def test_daily_stats(db):
    import time as _t
    ts = _t.time()
    db.add_records("dev-1", None, [
        make_record(name="A", price=100, captured_at=iso(ts - 100)),
        make_record(name="A", price=150, captured_at=iso(ts - 50)),
        make_record(name="A", price=120, captured_at=iso(ts)),
    ])
    d = db.daily_stats()
    assert d["A"]["high"] == 150 and d["A"]["low"] == 100 and d["A"]["count"] == 3
