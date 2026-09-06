"""SQLite 数据层：建表、批量入库（去重/校验）、清单、查询。

时间模型：
- captured_at 保留原始 ISO8601 文本（展示用）；
- captured_epoch（秒）用于范围/趋势排序；
- captured_minute = epoch//60，与 device+bullet+market_type+price 共同构成去重键
  （同分钟同价重复上报判重；同分钟价格变化视为新观测）。
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS bullets (
    name         TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    device_id  TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    last_ip    TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    rel_path    TEXT NOT NULL,
    device_id   TEXT,
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    bullet_name     TEXT NOT NULL,
    price           INTEGER NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'Koen',
    market_type     TEXT NOT NULL DEFAULT 'market',
    captured_at     TEXT NOT NULL,
    captured_epoch  INTEGER NOT NULL,
    captured_minute INTEGER NOT NULL,
    source          TEXT NOT NULL DEFAULT 'list_scan',
    snapshot_id     TEXT,
    inserted_at     TEXT NOT NULL,
    UNIQUE (device_id, bullet_name, market_type, captured_minute, price)
);
CREATE INDEX IF NOT EXISTS idx_records_bullet_time
    ON price_records (bullet_name, captured_epoch);
CREATE INDEX IF NOT EXISTS idx_records_time
    ON price_records (captured_epoch);
"""

# 用于清洗被 OCR 污染的子弹名（以已知口径为锚，去掉名称开头混入的杂质数字）
_CALIBERS = [
    "7.62x39毫米", "7.62x54毫米", "5.56x45毫米", "9x19毫米",
    "7.62x51毫米", "5.7x28毫米", "9x39毫米", "5.45x39毫米", "12.7x99毫米",
    ".44口径", ".45口径", "7.62x25毫米", ".338口径", "5.8x42毫米",
]


def clean_bullet_name_display(name: str) -> str:
    """展示层清洗：去掉子弹名前混入的杂质（如 '27.62x39毫米…'→'7.62x39毫米…'）。"""
    t = re.sub(r"\s+", "", str(name))
    low = t.lower()
    for c in _CALIBERS:
        k = c.lower()
        i = low.find(k)
        if i >= 0:
            return t[i:]
    return name


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "abm.db"


def parse_epoch(iso: str) -> int | None:
    """ISO8601 → epoch 秒；解析失败返回 None。兼容 'Z' 与 ±hh:mm 偏移。"""
    s = iso.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return int(datetime.fromisoformat(s).timestamp())
    except ValueError:
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """sqlite3 封装：请求级调用（FastAPI 线程池）+ 内部锁串行化写入。"""

    def __init__(self, path: str | Path | None = None):
        db_path = Path(path) if path else Path(
            os.environ.get("ABM_DB", DEFAULT_DB_PATH)
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            # WAL：允许采集控制器与 Web 服务多进程并发读写同一库
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=5000")
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ---------- 写入 ----------

    def add_records(self, device_id: str, last_ip: str | None, records: list) -> dict:
        """入库一批记录。返回 {accepted, duplicates, rejected:[{index,reason}]}。"""
        accepted = 0
        duplicates = 0
        rejected: list[dict] = []
        now = utc_now_iso()
        with self._lock:
            for idx, r in enumerate(records):
                name = (r.bullet_name or "").strip()
                if not name:
                    rejected.append({"index": idx, "reason": "empty bullet_name"})
                    continue
                epoch = parse_epoch(r.captured_at)
                if epoch is None:
                    rejected.append({"index": idx, "reason": "bad captured_at"})
                    continue
                minute = epoch // 60
                cur = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO price_records
                        (device_id, bullet_name, price, currency, market_type,
                         captured_at, captured_epoch, captured_minute,
                         source, snapshot_id, inserted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (device_id, name, r.price, r.currency, r.market_type,
                     r.captured_at, epoch, minute, r.source, r.snapshot_id, now),
                )
                if cur.rowcount == 1:
                    accepted += 1
                else:
                    duplicates += 1
                # 出现的名称自动进入清单（默认启用，不覆盖既有 active 状态）
                self.conn.execute(
                    "INSERT OR IGNORE INTO bullets (name, display_name, created_at) VALUES (?, ?, ?)",
                    (name, name, now),
                )
            self.conn.execute(
                """
                INSERT INTO devices (device_id, first_seen, last_seen, last_ip)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    last_ip = excluded.last_ip
                """,
                (device_id, now, now, last_ip),
            )
            self.conn.commit()
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}

    def register_snapshot(self, snapshot_id: str, rel_path: str, device_id: str | None) -> None:
        now = utc_now_iso()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO snapshots (snapshot_id, rel_path, device_id, uploaded_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET rel_path = excluded.rel_path
                """,
                (snapshot_id, rel_path, device_id, now),
            )
            self.conn.commit()

    # ---------- 清单 ----------

    def bullets(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT name, display_name, active, created_at FROM bullets ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_bullet(self, name: str) -> bool:
        """新增清单项；已存在返回 False。"""
        with self._lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO bullets (name, display_name, created_at) VALUES (?, ?, ?)",
                (name, name, utc_now_iso()),
            )
            self.conn.commit()
            return cur.rowcount == 1

    def delete_bullet(self, name: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM bullets WHERE name = ?", (name,))
            self.conn.commit()
            return cur.rowcount > 0

    def set_bullet_active(self, name: str, active: bool) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE bullets SET active = ? WHERE name = ?", (1 if active else 0, name)
            )
            self.conn.commit()

    # ---------- 查询 ----------

    def latest(self) -> list[dict]:
        """每个子弹的最新一条记录（按 captured_epoch 降序取最新）。"""
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT pr.bullet_name, pr.price, pr.captured_at, pr.captured_epoch,
                       pr.snapshot_id, pr.device_id, s.rel_path
                FROM price_records pr
                LEFT JOIN snapshots s ON s.snapshot_id = pr.snapshot_id
                WHERE pr.id = (
                    SELECT p2.id FROM price_records p2
                    WHERE p2.bullet_name = pr.bullet_name
                    ORDER BY p2.captured_epoch DESC, p2.id DESC
                    LIMIT 1
                )
                ORDER BY pr.bullet_name
                """
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def records(
        self,
        bullet: str | None = None,
        device_id: str | None = None,
        from_epoch: int | None = None,
        to_epoch: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        where, args = self._build_filter(bullet, device_id, from_epoch, to_epoch)
        with self._lock:
            total = self.conn.execute(
                f"SELECT COUNT(*) FROM price_records pr {where}", args
            ).fetchone()[0]
            rows = self.conn.execute(
                f"""
                SELECT pr.*, s.rel_path
                FROM price_records pr
                LEFT JOIN snapshots s ON s.snapshot_id = pr.snapshot_id
                {where}
                ORDER BY pr.captured_epoch DESC, pr.id DESC
                LIMIT ? OFFSET ?
                """,
                (*args, int(limit), int(offset)),
            ).fetchall()
        return [self._row_to_record(r) for r in rows], total

    def previous_prices(self) -> list[dict]:
        """每个子弹的倒数第二条（前一观测）记录，用于计算涨跌。"""
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT pr.bullet_name, pr.price, pr.captured_at, pr.captured_epoch
                FROM price_records pr
                WHERE pr.id = (
                    SELECT p2.id FROM price_records p2
                    WHERE p2.bullet_name = pr.bullet_name
                    ORDER BY p2.captured_epoch DESC, p2.id DESC
                    LIMIT 1 OFFSET 1
                )
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def trend(self, bullet: str, bucket_sec: int,
              from_epoch: int | None = None, to_epoch: int | None = None) -> list[dict]:
        """按时间桶聚合：返回每桶内最后一条观测（桶内最新价）。"""
        where, args = self._build_filter(bullet, None, from_epoch, to_epoch)
        with self._lock:
            rows = self.conn.execute(
                f"""
                SELECT pr.captured_epoch, pr.price
                FROM price_records pr
                {where}
                ORDER BY pr.captured_epoch ASC, pr.id ASC
                """,
                args,
            ).fetchall()
        buckets: dict[int, dict] = {}
        for r in rows:
            b = r["captured_epoch"] // bucket_sec
            buckets[b] = {"t": r["captured_epoch"], "price": r["price"]}
        return [buckets[k] for k in sorted(buckets)]

    def daily_stats(self) -> dict:
        """当日（本地 0 点起）各子弹的最高/最低价与入库次数。"""
        import datetime as _dt
        today0 = int(_dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT bullet_name, MAX(price) AS high, MIN(price) AS low, COUNT(*) AS n
                FROM price_records
                WHERE captured_epoch >= ?
                GROUP BY bullet_name
                """,
                (today0,),
            ).fetchall()
        return {r["bullet_name"]: {"high": r["high"], "low": r["low"], "count": r["n"]} for r in rows}

    def stats_overview(self) -> dict:
        with self._lock:
            total = self.conn.execute("SELECT COUNT(*) FROM price_records").fetchone()[0]
            bullets = self.conn.execute("SELECT COUNT(*) FROM bullets").fetchone()[0]
            devices = self.conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        return {"records": total, "bullets": bullets, "devices": devices}

    # ---------- 内部 ----------

    def _build_filter(
        self,
        bullet: str | None,
        device_id: str | None,
        from_epoch: int | None,
        to_epoch: int | None,
    ) -> tuple[str, list]:
        conds: list[str] = []
        args: list = []
        if bullet:
            conds.append("pr.bullet_name = ?")
            args.append(bullet)
        if device_id:
            conds.append("pr.device_id = ?")
            args.append(device_id)
        if from_epoch is not None:
            conds.append("pr.captured_epoch >= ?")
            args.append(int(from_epoch))
        if to_epoch is not None:
            conds.append("pr.captured_epoch <= ?")
            args.append(int(to_epoch))
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        return where, args

    @staticmethod
    def _row_to_record(r: sqlite3.Row) -> dict:
        d = dict(r)
        rel = d.pop("rel_path", None)
        if d.get("snapshot_id") and rel:
            d["snapshot_url"] = f"/static/snapshots/{rel}"
        # 展示层清洗：去掉被 OCR 混入的杂质前缀
        d["bullet_name"] = clean_bullet_name_display(d.get("bullet_name", ""))
        return d
