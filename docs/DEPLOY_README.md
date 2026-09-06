# 发行版（release/）说明

发行目录为「零源码」形式：电脑端全部程序已打包成 exe，不含任何 .py 源码、不含 android 源码。

## 目录结构

```
release/
├── ABMCollectorApp.exe    桌面控制端（自包含，内含 .NET 运行时，双击即用）
├── abm.exe                电脑端入口（web 网页服务 / collect 采集），含 OCR 与 DirectML
├── _internal/             abm.exe 的依赖（onnxruntime/模型等）
├── web/static/            网页页面资源（index/app.js/style.css）
├── config.json            采集配置（口径列表/频率/面板参数）
├── data/                  运行时数据目录（abm.db 数据库、snapshots/ 快照，自动生成）
└── 启动网页.bat           一键启动网页服务
```

## 用法

1. **启动网页服务**：双击 `启动网页.bat`，浏览器打开 `http://127.0.0.1:8600`
   （该脚本已自动设置数据目录到 `data/`、快照到 `data/snapshots`、页面到 `web/static`）。
2. **启动采集**：双击 `ABMCollectorApp.exe` → 刷新设备 → 抓一帧 → 标定导航点击 → 设频率 →
   「▶ 启动采集」。桌面端会调用同目录的 `abm.exe collect`（无需源码）。
3. 想改口径/频率/面板或在采集器层面调参，编辑 `config.json`（采集控制器启动时读取）。

## 手动命令行（代替双击）

```bat
start-web:  abm.exe web                      （需已设 data/web 环境变量，建议直接双击 bat）
collect:    abm.exe collect --config config.json
```

## 前置（目标机器）

- Windows 10/11，电脑端 exe 免装 .NET（已经自包含）；仅需：
- USB 调试：手机连电脑 + 开启开发者选项「USB 调试」并允许授权；
- 可选 GPU 加速：RapidOCR 已内置 `onnxruntime-directml`，任意支持 DX12 的显卡即可用；无 GPU 自动回退 CPU。

## 注意

- `data/` 与 `web/static` 首次运行后由脚本/程序生成；`config.json` 可随时编辑。
- 若换机器，直接整目录拷贝即可，无需安装 Python / .NET。
