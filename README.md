# 暗区突围 · 市场价格记录工具

> 版本说明：**旧的「安卓 App 自动采集」方案已移除（弃用）**，当前为**纯电脑端方案**。

## 方案（电脑端）

- 手机只当"屏幕"；电脑经 **USB(adb)** 完成：截屏 → 模拟点击遍历口径 → OCR 识别子弹与价格 → 写入数据库 → 网页展示统计。
- 三个组件：
  - **桌面控制端**（GUI）：实时画面预览、鼠标标定点击点、采集频率、一键启停采集、一键重置；
  - **采集控制器**：`abm.exe collect`，遍历左栏口径、逐屏枚举该口径全部子弹并记录价格（DirectML GPU 加速）；
  - **网页服务**：`abm.exe web`（或 `启动网页.bat`），历史记录 / 当日最高最低 / 走势 / 清单 / 导出 / 快照抽查。

## 快速开始（发行版 `release/`）

1. 手机开「开发者选项 → USB 调试」并连电脑；
2. 双击 `启动网页.bat` → 浏览器打开 `http://127.0.0.1:8600`；
3. 双击 `ABMCollectorApp.exe` → 刷新设备 → 抓一帧 → 在画面点选"每轮点击位置" → 设采集频率 → 「▶ 启动采集」；
4. `config.json` 可调口径列表、频率、面板/价格区参数。

> 开发版（源码）用法见 `docs/PC_COLLECTOR.md`；桌面控制端见 `docs/DESKTOP.md`。

## 文档导航

| 文档 | 内容 |
|---|---|
| `docs/PC_COLLECTOR.md` | 采集控制器原理/参数/调参/排查 |
| `docs/DESKTOP.md` | C# 桌面控制端用法（预览/标定/频率/启停） |
| `docs/DEPLOY_README.md` | 发行版（release/）结构与使用 |
| `docs/COMMERCIALIZATION.md` | 商业化合规转型方案 |
| `docs/PLAN.md` | 历史设计计划（安卓 App 章节已弃用） |
| `docs/PROTOCOL.md` | 历史两端协议（安卓 App 章节已弃用） |

## 验证状态与已知限制

- ✅ `pytest` 12 项通过；发行版已实测 `web` / `collect` / 一键重置可用。
- ⏳ 需真实手机联调；游戏市场为**口径分栏 + 卡片网格**，价格在卡片底部。
- 采集参数集中在 `config.json`：`calibers`（口径顺序）、`left_panel.x`/`grid_panel.x`（左栏/网格滑动位置）、`price_below_row_px`（价格带高度）、`interval_sec`（频率）。
- ⚠️ **风险**：对游戏 UI 的自动点击操作可能违反游戏条款、导致封号；商业化须先合规改造（见 `docs/COMMERCIALIZATION.md`）。

## 目录

```
pc/       python 采集控制器与网页服务（源码/开发版）
desktop/  C# 桌面控制端源码
docs/     文档
release/  发行目录（零源码，可整目录分发）
```
