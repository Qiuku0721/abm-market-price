import time

from app.reports import gen_daily, gen_hourly, generate

from .helpers import iso, make_record_obj as make_record


def test_gen_hourly_and_daily(db):
    now = int(time.time())
    base = now - 3600
    samples = {
        "7.62x39毫米PS子弹": [100, 110, 120],   # 上涨
        "7.62x39毫米BP子弹": [200, 180, 160],   # 下跌
        "9x19毫米PSO子弹": [50, 52, 54],        # 微涨
    }
    for name, prices in samples.items():
        for i, p in enumerate(prices):
            db.add_records("dev-1", None, [make_record(name=name, price=p, captured_at=iso(base + i * 60))])

    hour = gen_hourly(db, base, base + 3600, "2025-09-06 10:00")
    assert hour is not None
    assert hour["stats"]["n_bullets"] == 3
    assert hour["stats"]["top"] == "7.62x39毫米PS子弹"  # 动量最大
    assert hour["stats"]["worst"] == "7.62x39毫米BP子弹"

    daily = gen_daily(db, base, now, "2025-09-06")
    assert daily is not None
    assert "建议关注买入" in daily["content"]
    assert daily["stats"]["recommend"]  # 有推荐
    # 上涨/波动者倾向被推荐，应在推荐列表中出现
    assert any("PS子弹" in r for r in daily["stats"]["recommend"])

    # 幂等：再次生成返回同一份（不重复插入）
    again = generate(db, "daily", base, now, "2025-09-06")
    assert again["title"] == daily["title"]
    assert db.latest_report("daily")["title"] == daily["title"]
