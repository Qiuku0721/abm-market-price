"""PC 端采集控制器入口。

用法（在 pc/ 目录下）：
    python run_collector.py                 # 连接唯一 USB 设备并开始周期采集
    python run_collector.py --serial XXXXX  # 指定设备
    python run_collector.py --interval 30   # 覆盖周期（秒）
    python run_collector.py --once          # 只跑一轮（调参用）
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Database  # noqa: E402
from collector.config import load_config  # noqa: E402
from collector.controller import CollectorController  # noqa: E402
from collector.device import AdbDevice  # noqa: E402


def main() -> int:
    # Windows 控制台 GBK 兜底：避免中文日志编码异常
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="ABM PC 采集控制器")
    parser.add_argument("--serial", help="adb 设备序列号（默认自动选唯一设备）")
    parser.add_argument("--config", help="配置文件路径（默认 pc/collector/config.json）")
    parser.add_argument("--interval", type=int, help="覆盖采集周期（秒）")
    parser.add_argument("--once", action="store_true", help="只跑一轮后退出")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path(__file__).parent / "collector.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("collector")

    cfg = load_config(Path(args.config) if args.config else None)
    if args.interval:
        cfg["interval_sec"] = args.interval

    try:
        device = AdbDevice(serial=args.serial)
        device.wait_online()
    except Exception as e:  # noqa: BLE001
        logger.error("设备连接失败：%s", e)
        logger.error("请确认：数据线已插、手机开启「USB 调试」并允许本机授权（可用 adb devices 检查）")
        return 1

    db = Database()
    logger.info("数据库：%s（与网页服务共用）", db.path)
    ctrl = CollectorController(device=device, db=db, cfg=cfg)
    ctrl.run_forever(once=args.once)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停止采集")
        sys.exit(0)
