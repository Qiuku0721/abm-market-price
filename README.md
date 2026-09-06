# 暗区突围 · 市场价格自动记录工具（子弹）

自动采集《暗区突围》游戏内市场子弹价格：**安卓 Kotlin App 全自动**（截屏 → OCR 识别 → 模拟点击遍历 → 上报），**电脑端 Python 程序**负责接收、存储、统计与展示。

> ⚠️ **合规与封号风险**：对游戏内 UI 的自动化操作（模拟点击/滚动）可能违反游戏条款，被反作弊系统判定为外挂并封号。本项目仅限学习与研究用途，内置限频与随机抖动以降低特征，但**风险自负**。如需零风险，可仅保留「截屏识别上报」链路人工翻页（当前版本未内置）。

## 架构一览

```
安卓真机（Kotlin App）                    电脑（Windows / Python）
MediaProjection 截屏 ──┐                 FastAPI :8600
ML Kit OCR 识别名称/价格 ── 采集循环         ├─ SQLite（记录/清单/设备/快照）
无障碍 dispatchGesture 点击/滚动            ├─ 本地 Web 页（最新价/走势/明细/快照抽查）
HTTP + 文件队列 断网重传 ── USB/Wi-Fi ────►  └─ CSV / Excel 导出
```

- 🎓 新手使用教程：`docs/TUTORIAL.md`
- 详细设计：`docs/PLAN.md` ｜ 两端协议：`docs/PROTOCOL.md` ｜ 环境安装与验证：`docs/SETUP.md`

## 自动构建（保存代码即自动编译）

**双击 `auto-build.bat`** 启动监听（窗口保持开启），之后每次保存：

- `android/app/src` 或构建配置改动 → 自动 `assembleDebug`，产物刷新到
  `android/app/build/outputs/apk/debug/app-debug.apk`；
- `pc/` 代码改动 → 自动语法检查（已运行过一次 `pc\scripts\start.bat` 建立 `.venv` 后则跑 `pytest`）。

构建日志写入根目录 `auto-build.log`，按 Ctrl+C 停止监听。

> 环境说明：自动构建固定使用 `~\.jdks` 下的 JDK（优先 21/17）与 `android/local.properties` 指向的
> Android SDK；Gradle wrapper 版本为 8.11.1（支持 JDK 21）。如首次手动编译：
> `set JAVA_HOME=%USERPROFILE%\.jdks\ms-21.0.11 && cd android && gradlew.bat assembleDebug`

## 快速开始

### 电脑端（Python 3.10+）

```bash
cd pc
scripts\start.bat        # Windows：自动建 venv、装依赖、启动 http://0.0.0.0:8600
# 浏览器打开 http://127.0.0.1:8600
# USB 有线模式（推荐）：插数据线 -> 双击 pc\scripts\usb-link.bat，App 填 http://127.0.0.1:8600
# Wi-Fi 模式：App 填电脑局域网 IP（cmd 里 ipconfig 查看）
```

手动方式：`python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && python server.py`。

### 手机端（Android 8.0+，真机）

1. 用 Android Studio 打开 `android/`，构建并安装（或 `cd android && gradlew.bat assembleDebug`，产物 `app/build/outputs/apk/debug/app-debug.apk`）。
2. 系统设置 → 无障碍 → 开启 **ABM Collector 手势服务**。
3. USB 有线模式（推荐）：手机开 USB 调试并插数据线 → 双击 `pc\scripts\usb-link.bat` 建好通道 → 打开 App，地址保持默认 `http://127.0.0.1:8600`；Wi-Fi 模式则填电脑局域网 IP。然后编辑子弹清单（每行一个名称）→「保存清单」→「开始采集」，按提示授予**屏幕录制**权限。
4. 将《暗区突围》切到**市场列表页**并保持前台，App 会按周期自动滚动扫描并上报。

## 目录结构

```
docs/       PLAN（设计）/ PROTOCOL（协议）/ SETUP（环境与验证）
android/    手机端 Kotlin App
pc/         电脑端 Python 程序（server.py 入口，app/ 业务，tests/ 单测）
```

## 验证状态与已知限制

| 项 | 状态 |
|---|---|
| 两端协议字段/端点一致性 | ✅ 已核对（App ↔ PC ↔ PROTOCOL 三方一致） |
| App 端 Kotlin 源码静态一致性（括号/本地 import） | ✅ 已核对 |
| PC 端 app.js 语法 | ✅ node --check 通过 |
| Android 编译 / 真机端到端 | ⏳ 待 JDK+Android Studio（`docs/SETUP.md` §B/§C） |
| Python 运行验证（venv/uvicorn/pytest/curl 冒烟） | ⏳ 待 Python 环境（`docs/SETUP.md` §A） |
| 真机回归清单（价格与游戏实价一致性、连续运行稳定性） | ⏳ 需真实游戏账号，按 `docs/SETUP.md` §C 执行 |

**已知限制**

- 当前开发机未安装 Python / Android SDK / JDK，运行级验证未在本机执行；相关命令与预期输出已写入 `docs/SETUP.md`。
- 界面识别基于「市场列表页 + 列表遍历」（计划批准的首版方案）；若游戏界面布局/分辨率不同，需按 `LayoutProfile` 与命中行截图在页面上抽查调参。
- 名称匹配为单行 OCR 子串匹配，名称被 UI 断行显示时可能漏匹配（App 日志会记录「未找到」项）。
- 价格解析依赖价格格位于行右侧的布局假设，偏离时命中行缩略图可辅助人工核对。

## 里程碑

- [x] M1 工程骨架与文档
- [x] M2 手机端 App（Kotlin）— 代码完成，运行验证待环境
- [x] M3 电脑端程序（Python）— 代码完成，运行验证待环境
- [ ] M4 真机联调收尾（待用户环境）

## 风险与对策

限频（默认 5 分钟/轮，可调）、手势随机抖动、采集间隔 ±25% 抖动、可随时停止；详见 `docs/PLAN.md` §9。
