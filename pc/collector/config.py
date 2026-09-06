"""采集控制器配置：pc/collector/config.json（首次运行自动生成示例）。"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULT_CONFIG: dict = {
    # 左栏口径顺序（从上到下；click 每个口径后记录右侧该口径全部子弹）
    # 依你的截图完整顺序：7.62x39 第一个，5.8x42 最后一个；已按要求跳过 12x70毫米
    "calibers": [
        "7.62x39毫米", "7.62x54毫米", "5.56x45毫米", "9x19毫米",
        "7.62x51毫米", "5.7x28毫米", "9x39毫米", "5.45x39毫米", "12.7x99毫米",
        ".44口径", ".45口径", "7.62x25毫米", ".338口径", "5.8x42毫米",
    ],
    # 每轮先执行的导航点击（归一化 0~1）：例如先点顶部「购买」页签
    "nav_taps": [
        # [0.5, 0.05]
    ],
    # 采集周期（秒）
    "interval_sec": 60,
    # 左栏口径列表的滑动参数（在左栏上下滑动以找到目标口径）—— 步长调小（约 2~3 行），避免滚过头
    "left_panel": {"x": 0.12, "from_y": 0.60, "to_y": 0.46, "duration_ms": 300},
    # 右侧子弹网格的滑动参数（切口径后先回顶部，再逐屏下滑；to_y 调小避免跳行）
    "grid_panel": {"x": 0.62, "from_y": 0.72, "to_y": 0.45, "duration_ms": 400},
    # 记录网格前，先向上滚回顶部的次数（避免上一口径残留位置导致顶部第一行漏采）
    "grid_back_to_top_swipes": 4,
    # 每个口径最多枚举几屏（逐屏下滑，直到连续两屏无变化停止）
    "max_grid_pages": 6,
    # 点击每个口径后，是否先在右侧网格执行一次下滑
    "grid_scroll_after_caliber": True,
    # 价格位于名称行下方 N 像素内的横带（卡片底部价格）
    "price_below_row_px": 120,
    # 在每个口径下最多滚动左栏几次找不到就跳过
    "max_left_scrolls": 8,
    # 动作之间最小等待毫秒
    "action_delay_ms": 500,
    # 调试：保存每屏截图到 pc/collector/debug/（0 关，1 每屏）
    "debug_save": 1,
    # 快照保存（命中行截图，网页「明细-查看」可见）
    "save_snapshots": True,
}


def load_config(path: Path | None = None) -> dict:
    import copy
    cfg_path = path or CONFIG_PATH
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[config] 已生成默认配置：{cfg_path}（请按需编辑）")
        return json.loads(json.dumps(DEFAULT_CONFIG))
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    # 补齐新增/缺失键（如旧版 config 升级后缺 calibers/面板参数等）
    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, copy.deepcopy(value))
    return data
