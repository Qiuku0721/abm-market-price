"""对已入库的子弹名做一次性清洗修复：以已知口径为锚，去掉名称开头被 OCR 混入的杂质数字。

用法：python fix_bullet_names.py （自动处理 release/ 与 pc/ 下存在的 abm.db）
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from collector.config import load_config  # noqa: E402
from app.bullet_names import normalize_bullet_name  # noqa: E402


def candidate_dbs() -> list[Path]:
    cands = [
        ROOT.parent / "release" / "data" / "abm.db",
        ROOT / "data" / "abm.db",
        ROOT.parent / "release" / "_internal" / "data" / "abm.db",
    ]
    return [p for p in cands if p.exists()]


def main() -> int:
    calibers = load_config().get("calibers", [])
    dbs = candidate_dbs()
    if not dbs:
        print("未找到数据库（release/data/abm.db 或 pc/data/abm.db），无数据可修复。")
        return 0
    for db_path in dbs:
        conn = sqlite3.connect(str(db_path))
        total = 0
        for table, col in [("price_records", "bullet_name"), ("bullets", "name")]:
            try:
                rows = conn.execute(f"SELECT rowid, {col} FROM {table}").fetchall()
            except sqlite3.OperationalError:
                continue  # 表可能不存在（空库）
            for rid, name in rows:
                if not name:
                    continue
                clean = normalize_bullet_name(str(name))
                if clean and clean != name:
                    conn.execute(
                        f"UPDATE {table} SET {col}=? WHERE rowid=?", (clean, rid)
                    )
                    total += 1
        conn.commit()
        conn.close()
        print(f"已修复 {total} 条名称 @ {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
