from datetime import datetime

from .helpers import iso, make_record

HDR = {"X-ABM-Protocol": "1"}


def _seed_one(client, price=320, seconds=0):
    # 用「当前时间」造数，保证 /api/trend 的窗口查询（1h/1d/…回看）能取到数据
    base = datetime.now().timestamp()
    body = {
        "device_id": "dev-api-1",
        "records": [make_record(price=price, captured_at=iso(base + seconds))],
    }
    return client.post("/records", json=body, headers=HDR)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_post_records_dedup_and_query(client):
    assert _seed_one(client, price=320, seconds=0).json()["accepted"] == 1
    assert _seed_one(client, price=321, seconds=60).json()["accepted"] == 1
    # 原样重放 → 判重
    assert _seed_one(client, price=321, seconds=60).json()["duplicates"] == 1

    latest = client.get("/api/latest").json()
    assert latest["M80 5.56x45"]["price"] == 321

    recs = client.get("/api/records", params={"bullet": "M80 5.56x45"}).json()
    assert recs["total"] == 2

    trend = client.get("/api/trend", params={"bullet": "M80 5.56x45", "window": "1h"}).json()
    assert len(trend) >= 1

    bullets = {b["name"] for b in client.get("/api/bullets").json()}
    assert "M80 5.56x45" in bullets  # 自动入清单


def test_protocol_mismatch_rejected(client):
    r = client.post(
        "/records",
        json={"device_id": "d", "records": []},
        headers={"X-ABM-Protocol": "9"},
    )
    assert r.status_code == 406


def test_snapshot_upload_download_and_reject(client):
    meta = '{"device_id":"dev-api-1","kind":"row"}'
    ok = client.post(
        "/snapshots",
        data={"meta": meta},
        files={"file": ("snap_devapi1_1700000000000.jpg", b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")},
        headers=HDR,
    )
    assert ok.status_code == 200
    snap = ok.json()
    assert snap["snapshot_id"].endswith(".jpg")
    assert client.get(snap["url"]).status_code == 200

    bad = client.post(
        "/snapshots",
        files={"file": ("not valid.jpg", b"x", "image/jpeg")},
        headers=HDR,
    )
    assert bad.status_code == 400


def test_export_csv_and_excel(client):
    _seed_one(client, price=320, seconds=0)
    csv = client.get("/export/csv")
    assert csv.status_code == 200
    assert "bullet_name" in csv.text

    xls = client.get("/export/excel")
    assert xls.status_code == 200
    assert xls.content[:2] == b"PK"  # xlsx = zip
