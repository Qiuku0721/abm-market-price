"""ABM 电脑端统一入口（PyInstaller 打包入口）。

子命令：
    abm.exe web [--host 0.0.0.0] [--port 8600]               启动网页服务（记录/统计/展示）
    abm.exe collect [--config <path>] [--once] [--serial X] [--interval 30]   启动采集控制器

环境变量（网页服务）：
    ABM_DB            数据库文件路径（打包后需指到可写目录，如 发行目录/data/abm.db）
    ABM_SNAPSHOTS_DIR 快照目录（可写，如 发行目录/data/snapshots）
"""

from __future__ import annotations

import argparse
import sys


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

    args = parser.parse_args()

    if args.cmd == "web":
        import uvicorn

        from app.main import app

        uvicorn.run(app, host=args.host, port=args.port)
        return 0

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
