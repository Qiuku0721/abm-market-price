"""FastAPI 应用：接收上报、查询 API、导出、本地页面。与 docs/PROTOCOL.md v1 对齐。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import export as export_mod
from . import stats as stats_mod
from .database import Database
from .models import BulletIn, RecordsBatch

BASE_DIR = Path(__file__).resolve().parent            # pc/app


def _run_base() -> Path:
    if _frozen():
        return Path(sys.executable).resolve().parent
    return BASE_DIR.parent  # 开发：pc/


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# 打包后：数据/页面默认放运行目录（exe 所在），避免写 _internal；开发期用仓库内路径
if _frozen():
    _DATA_BASE = Path(sys.executable).resolve().parent
    PC_STATIC_DIR = Path(os.environ.get("ABM_STATIC_DIR") or (_DATA_BASE / "data"))
    WEB_STATIC_DIR = Path(os.environ.get("ABM_WEB_STATIC") or (_DATA_BASE / "web" / "static"))
else:
    _DATA_BASE = BASE_DIR.parent  # pc/
    PC_STATIC_DIR = Path(os.environ.get("ABM_STATIC_DIR") or (_DATA_BASE / "static"))
    WEB_STATIC_DIR = Path(os.environ.get("ABM_WEB_STATIC") or (BASE_DIR / "web" / "static"))
SNAPSHOTS_DIR = Path(os.environ.get("ABM_SNAPSHOTS_DIR") or (PC_STATIC_DIR / "snapshots"))
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

PROTOCOL_VERSION = "1"
SNAPSHOT_NAME_RE = re.compile(r"^[\w\-]+\.(jpe?g|png)$", re.IGNORECASE)
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
TREND_WINDOWS = {  # window: (bucket_sec, span_sec)
    "1h": (60, 3600),
    "1d": (600, 86400),
    "7d": (3600, 604800),
    "30d": (86400, 2592000),
}

_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def configure_db_for_tests(path: str | Path | None = None) -> Database:
    """测试注入独立数据库实例（数据库文件由 ABM_DB 环境变量或参数决定）。"""
    global _db
    _db = Database(path)
    return _db


async def _scheduler(db) -> None:
    """后台调度：每个整点生成小时财报；每天 20:00 生成当日财报。幂等（表内 UNIQUE 去重）。"""
    last_hour = last_day = None
    while True:
        now = datetime.now()
        key_hour = now.strftime("%Y-%m-%d %H:00")
        key_day = now.strftime("%Y-%m-%d")
        if now.minute <= 1:
            if key_hour != last_hour:
                lb = now.replace(minute=0, second=0, microsecond=0)
                try:
                    from . import reports as R
                    R.generate(db, "hourly", int(lb.timestamp()),
                               int((lb + timedelta(hours=1)).timestamp()), key_hour)
                except Exception as e:  # noqa: BLE001
                    print(f"[scheduler] hourly report 失败：{e}")
                last_hour = key_hour
            if now.hour == 20 and key_day != last_day:
                lb = now.replace(hour=0, minute=0, second=0, microsecond=0)
                try:
                    from . import reports as R
                    R.generate(db, "daily", int(lb.timestamp()), int(now.timestamp()), key_day)
                except Exception as e:  # noqa: BLE001
                    print(f"[scheduler] daily report 失败：{e}")
                last_day = key_day
        await asyncio.sleep(20)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_scheduler(get_db()))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="ABM 价格记录服务", version="1.0", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=str(WEB_STATIC_DIR)), name="assets")
app.mount("/static", StaticFiles(directory=str(PC_STATIC_DIR)), name="static")


def _check_protocol(request: Request) -> None:
    version = request.headers.get("x-abm-protocol")
    if version is not None and version != PROTOCOL_VERSION:
        raise HTTPException(status_code=406, detail="unsupported protocol version")


# ---------- 基础 ----------

@app.get("/health")
def health() -> dict:
    db = get_db()
    return {"status": "ok", "time": datetime.now().isoformat(timespec="seconds"), **db.stats_overview()}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_STATIC_DIR / "index.html")


# ---------- 接收上报 ----------

@app.post("/records")
def post_records(request: Request, batch: RecordsBatch) -> dict:
    _check_protocol(request)
    ip = request.client.host if request.client else None
    result = get_db().add_records(batch.device_id, ip, batch.records)
    return JSONResponse(result)


@app.post("/snapshots")
async def post_snapshot(
    request: Request,
    file: UploadFile = File(...),
    meta: str = Form("{}"),
) -> dict:
    _check_protocol(request)
    name = Path(file.filename or "").name
    if not SNAPSHOT_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="bad snapshot filename")
    data = await file.read()
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=413, detail="snapshot too large")

    device_id: str | None = None
    try:
        device_id = json.loads(meta).get("device_id")
    except (ValueError, AttributeError):
        pass

    day = datetime.now().strftime("%Y%m%d")
    rel = f"{day}/{name}"
    dest = SNAPSHOTS_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    get_db().register_snapshot(name, rel, device_id)
    return {"snapshot_id": name, "url": f"/static/snapshots/{rel}"}


# ---------- 查询 API ----------

@app.get("/api/latest")
def api_latest() -> dict:
    return stats_mod.latest_with_delta(get_db())


@app.get("/api/daily")
def api_daily() -> dict:
    """当日（本地 0 点起）各子弹最高/最低价。"""
    return get_db().daily_stats()


@app.get("/api/trend")
def api_trend(bullet: str, window: str = "7d") -> list[dict]:
    cfg = TREND_WINDOWS.get(window)
    if cfg is None:
        raise HTTPException(status_code=400, detail="bad window, use 1h/1d/7d/30d")
    bucket_sec, span_sec = cfg
    now = int(time.time())
    return get_db().trend(bullet, bucket_sec, now - span_sec, now)


@app.get("/api/records")
def api_records(
    bullet: str | None = None,
    device_id: str | None = None,
    from_: int | None = None,
    to: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    limit = min(max(limit, 1), 1000)
    offset = max(offset, 0)
    rows, total = get_db().records(bullet, device_id, from_, to, limit, offset)
    return {"total": total, "rows": rows}


@app.get("/api/bullets")
def api_bullets() -> list[dict]:
    return get_db().bullets()


@app.post("/api/bullets")
def api_add_bullet(body: BulletIn) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="empty name")
    created = get_db().add_bullet(name)
    return {"ok": True, "created": created}


@app.delete("/api/bullets/{name:path}")
def api_delete_bullet(name: str) -> dict:
    deleted = get_db().delete_bullet(name)
    return {"ok": deleted}


@app.patch("/api/bullets/{name:path}/active")
def api_set_active(name: str, active: int = 1) -> dict:
    get_db().set_bullet_active(name, active != 0)
    return {"ok": True}


# ---------- 导出 ----------

@app.get("/export/csv")
def export_csv(
    bullet: str | None = None,
    device_id: str | None = None,
    from_: int | None = None,
    to: int | None = None,
) -> Response:
    rows, _ = get_db().records(bullet, device_id, from_, to, limit=100_000, offset=0)
    filename = f"abm_prices_{int(time.time())}.csv"
    return Response(
        content=export_mod.to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/excel")
def export_excel(
    bullet: str | None = None,
    device_id: str | None = None,
    from_: int | None = None,
    to: int | None = None,
) -> Response:
    rows, _ = get_db().records(bullet, device_id, from_, to, limit=100_000, offset=0)
    filename = f"abm_prices_{int(time.time())}.xlsx"
    return Response(
        content=export_mod.to_xlsx(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- 财报 ----------

@app.get("/api/reports")
def api_reports(kind: str | None = None, limit: int = 30) -> list[dict]:
    limit = min(max(limit, 1), 100)
    return get_db().list_reports(kind, limit)


@app.get("/api/report/latest")
def api_report_latest(kind: str = "daily") -> dict:
    return get_db().latest_report(kind) or {}


@app.post("/api/reports/generate")
def api_report_generate(kind: str = "daily") -> dict:
    from . import reports as reports_mod
    now = datetime.now()
    if kind == "hourly":
        key = now.strftime("%Y-%m-%d %H:00")
        lb = now.replace(minute=0, second=0, microsecond=0)
        start, end = int(lb.timestamp()), int((lb + timedelta(hours=1)).timestamp())
    else:
        kind = "daily"
        key = now.strftime("%Y-%m-%d")
        lb = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start, end = int(lb.timestamp()), int(now.timestamp())
    rep = reports_mod.generate(get_db(), kind, start, end, key)
    if rep is None:
        return {"ok": False, "reason": "该时段暂无价格数据"}
    return {"ok": True, "report": rep}


# ---------- 局域网无线调试 ----------

@app.post("/api/wifi/connect")
def api_wifi_connect(payload: dict) -> dict:
    try:
        from . import wifi as wifi_mod
        host = str(payload.get("host", "")).strip()
        dev_port = int(payload.get("port", 0))
        pair_port = int(payload["pair_port"]) if payload.get("pair_port") else None
        pair_code = str(payload.get("pair_code", "")).strip() or None
        if not host or not dev_port:
            return {"ok": False, "reason": "请填写手机 IP 与连接端口"}
        result = wifi_mod.wifi_connect(host, dev_port, pair_port, pair_code)
        result["ok"] = bool(result.get("devices"))
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}
