"""ABM 电脑端统一入口（PyInstaller 打包入口）。

子命令：
    abm.exe web [--host 0.0.0.0] [--port 8600]               启动网页服务（记录/统计/展示）
    abm.exe collect [--config <path>] [--once] [--serial X] [--interval 30]   启动采集控制器
    abm.exe reset [--db <path>] [--snapshots <dir>]           一键清空记录/日志/快照

环境变量（网页服务）：
    ABM_DB            数据库文件路径（打包后需指到可写目录，如 发行目录/data/abm.db）
    ABM_SNAPSHOTS_DIR 快照目录（可写，如 发行目录/data/snapshots）
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def do_reset(db_path: str | None, snapshots_dir: str | None, logs: list[str] | None = None) -> None:
    """清空价格/清单/设备/快照表 + 删除快照文件与日志。保留数据库结构与目录。"""
    if db_path and Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        try:
            for table in ("price_records", "bullets", "devices", "snapshots"):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
        finally:
            conn.close()
        print(f"已清空数据库：{db_path}")

    if snapshots_dir and Path(snapshots_dir).exists():
        n = 0
        for p in Path(snapshots_dir).rglob("*"):
            if p.is_file():
                p.unlink()
                n += 1
        print(f"已删除快照 {n} 个。")
        Path(snapshots_dir).mkdir(parents=True, exist_ok=True)

    for lp in (logs or []):
        if lp and Path(lp).exists():
            Path(lp).unlink()
            print(f"已删除日志：{lp}")


def cmd_reset(args) -> int:
    import os

    db = args.db or os.environ.get("ABM_DB")
    snaps = args.snapshots or os.environ.get("ABM_SNAPSHOTS_DIR")
    do_reset(db, snaps, args.logs or [])
    print("一键重置完成。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="abm", description="ABM 电脑端入口")
    sub = parser.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("web", help="启动网页服务")
    w.add_argument("--host", default="0.0.0.0")
    w.add_argument("--port", type=int, default=8600)

    c = sub.add_parser("collect", help="启动采集控制器")
    c.add_argument("--config", help="config.json 路径")
    c.add_argument("--serial", help="adb 设备序列号")
    c.add_argument("--interval", type=int, help="采集周期（秒）覆盖")
    c.add_argument("--once", action="store_true", help="只跑一轮")

    r = sub.add_parser("reset", help="一键清空所有记录/日志/历史")
    r.add_argument("--db", help="数据库文件路径")
    r.add_argument("--snapshots", help="快照目录")
    r.add_argument("--logs", nargs="*", default=[], help="要删除的日志文件")

    args = parser.parse_args()

    if args.cmd == "web":
        import uvicorn

        from app.main import app

        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.cmd == "reset":
        return cmd_reset(args)

    # collect：复用 run_collector 的主逻辑
    import run_collector as rc

    argv = ["run_collector"]
    if args.config:
        argv += ["--config", args.config]
    if args.serial:
        argv += ["--serial", args.serial]
    if args.interval:
        argv += ["--interval", str(args.interval)]
    if args.once:
        argv += ["--once"]
    sys.argv = argv
    return rc.main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停止")
        sys.exit(0)
