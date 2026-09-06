"""采集控制器配置：pc/collector/config.json（首次运行自动生成示例）。"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULT_CONFIG: dict = {
    # 要采集价格的子弹清单（精确名称）
    "bullets": [
        "M80 5.56x45",
    ],
    # 采集周期（秒）
    "interval_sec": 60,
    # 每轮扫描前先执行的导航点击（归一化 0~1 坐标），用于进入市场/子弹分类页
    "nav_taps": [
        # 例：[0.5, 0.92], [0.5, 0.45]
    ],
    # 滚动参数（归一化，竖屏为列表向下滚；如游戏横屏请自行调整方向/区域）
    "scroll": {
        "from_y": 0.72,
        "to_y": 0.30,
        "x": 0.5,
        "duration_ms": 400,
    },
    # 每轮开始回到列表顶部的上滑次数（手指从下往上滑=内容向下=回到顶部；横屏同理）
    "top_swipes": 6,
    # 一行中「价格区」左边界（该行右侧再往右到屏幕边缘之间的区域用于识别价格）
    "price_zone_left_x": 0.52,
    "row_pad_px": 22,
    "max_scrolls": 12,
    # 连续几屏内容无变化判定已到列表底部
    "stagnant_limit": 2,
    # 动作之间最小等待毫秒（防点太快）
    "action_delay_ms": 500,
    # 调试：保存每屏截图到 pc/collector/debug/（0 关闭，1 每屏，2 仅命中行）
    "debug_save": 1,
    # 快照保存（命中行截图，网页「明细-查看」可见）
    "save_snapshots": True,
}


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or CONFIG_PATH
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[config] 已生成默认配置：{cfg_path}（请按需编辑）")
        return json.loads(json.dumps(DEFAULT_CONFIG))
    return json.loads(cfg_path.read_text(encoding="utf-8"))
