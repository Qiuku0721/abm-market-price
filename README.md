# 暗区突围 · 市场价格自动记录工具（子弹）

自动采集《暗区突围》游戏内市场子弹价格：**安卓 Kotlin App 全自动**（截屏 → OCR 识别 → 模拟点击遍历 → 上报），**电脑端 Python 程序**负责接收、存储、统计与展示。

> ⚠️ 合规提示：对游戏内 UI 的自动化操作可能违反游戏条款并导致账号封禁。本项目仅限学习与研究用途，请控制使用频率，风险自负。详见 `docs/PLAN.md` 风险章节。

## 快速导航

| 文档 | 内容 |
|---|---|
| `docs/PLAN.md` | 总体架构、模块设计、采集流程、里程碑、风险 |
| `docs/PROTOCOL.md` | 手机端 ↔ 电脑端上报数据协议（字段、端点、示例） |
| `docs/SETUP.md` | Python / Android 环境安装与验证步骤 |

## 目录结构

```
docs/       计划、协议、环境文档
android/    手机端 Kotlin App（Android Studio 工程）
pc/         电脑端 Python 程序（FastAPI + SQLite + 本地 Web 页面）
```

## 状态

- [x] M1 工程骨架与文档
- [ ] M2 手机端 App（Kotlin）
- [ ] M3 电脑端程序（Python）
- [ ] M4 联调收尾

（详见 `docs/PLAN.md` 第 11 节里程碑。）
