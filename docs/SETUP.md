# 环境安装与验证（SETUP）

> ⚠️ 注：安卓 App 方案（§B Android 构建/真机、§C 真机回归）**已弃用移除**；
> 当前电脑端方案只需保留 **USB 调试** 相关知识（§B.4 前几条），其余 A 节（Python 3.12）与
> `pc/scripts/start.bat`、`run_collector.py`、`pytest` 仍适用。

> 当前开发机（Windows）**尚未安装 Python 与 Android SDK**。以下步骤在有网络与安装权限的机器上执行；
> 每条验证命令均给出「预期输出」，作为 M2/M3 阶段运行级验证的依据。

## A. Python（电脑端程序，要求 3.10+）

1. 安装 Python **3.12**（推荐；采集控制器依赖的 RapidOCR 需 Python <3.13，3.14 不可用）：
   - 管理员 PowerShell：`winget install Python.Python.3.12`；
   - 或从 https://www.python.org/downloads/ 下载安装，**务必勾选 “Add python.exe to PATH”**。
   - 注意：若此前 `python` 命令触发 Microsoft Store 占位页，安装后需**关闭并重开终端**。
2. 验证：
   ```bash
   python --version          # 预期：Python 3.12.x
   python -m pip --version   # 预期：pip 24.x from ...\site-packages\pip
   ```
3. 创建虚拟环境并安装依赖（在 `pc/` 目录内）：
   ```bash
   cd pc
   python -m venv .venv
   .venv\Scripts\activate        # 提示符前出现 (.venv)
   python -m pip install -r requirements.txt
   ```
4. 冒烟验证：
   ```bash
   python -c "import fastapi, uvicorn, openpyxl, multipart; print('deps ok')"
   # 预期：deps ok
   python -m pytest               # 预期：全部通过（数据层/统计单测）
   ```
5. 启动服务：
   ```bash
   python server.py
   # 预期日志：Uvicorn running on http://0.0.0.0:8600
   ```
6. 模拟上报冒烟（另开一个终端）：
   ```bash
   curl.exe -s http://127.0.0.1:8600/health
   # 预期：{"status":"ok",...}
   curl.exe -X POST http://127.0.0.1:8600/records -H "Content-Type: application/json" -d '{"device_id":"test","records":[{"bullet_name":"测试子弹","price":100,"captured_at":"2025-09-06T12:00:00+08:00"}]}'
   # 预期：{"accepted":1,"duplicates":0,"rejected":[]}
   ```
7. 浏览器打开 `http://127.0.0.1:8600` 应能看到统计页面。

## B. Android（手机端 App）

1. 安装 JDK 17（如 Temurin 17）与 Android Studio（内含 SDK Platform 34、Build-Tools 34.0.0）。
2. 首次打开 `android/` 工程，等待 Gradle 同步（使用仓库自带 `gradle wrapper`）。
3. 命令行构建（可选）：
   ```bash
   cd android
   ./gradlew.bat assembleDebug
   # 预期：BUILD SUCCESSFUL；产物 app/build/outputs/apk/debug/app-debug.apk
   ```
4. 真机准备（安卓 8.0+，建议 10+）：
   - 开发者选项 → 开启「USB 调试」；`adb install -r app-debug.apk`（仅首装需要 USB）。
   - 系统设置 → 无障碍 → 开启 **ABM Collector** 无障碍服务（点击注入必需）。
   - 首次启动 App → 点「开始」→ 授予**屏幕录制**（MediaProjection）与**悬浮窗**权限。
5. 使用步骤：App 内填写电脑局域网 IP → 保存/编辑子弹清单 → 点「开始」自动采集。

## C. 真机端到端回归清单（需真实游戏账号，用户执行）

| # | 步骤 | 预期 |
|---|---|---|
| 1 | 手机连同一 Wi-Fi，电脑端 `python server.py` 已运行 | `/health` ok |
| 2 | App 配置电脑 IP，点「开始」 | 悬浮窗出现，状态=采集中 |
| 3 | 手动切到游戏市场页并保持前台 | App 自动截屏识别 |
| 4 | 观察 App 内日志/悬浮状态 | 出现「已命中 N 项」 |
| 5 | 电脑端页面 `/api/latest` | 有对应子弹最新价 |
| 6 | 对照游戏内实价 | 价格一致（±0，数值相同） |
| 7 | 连续运行 ≥ 30 分钟 | 无卡死，无崩溃，记录持续增长 |
| 8 | 中途关闭电脑端服务再恢复 | App 本地队列补齐重传 |

## D. 已知限制

- 本开发机无 Python / Android SDK：运行级验证（§A.4、B.3）需环境就绪后执行；
- 识别准确率依赖游戏界面版本，若大面积失败，用 App「debug 快照」与页面「快照抽查」人工核对后调参。
