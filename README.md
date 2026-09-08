# ABM 市场价格记录

给《暗区突围》做了一个市场子弹价格记录工具。

手机连到电脑上（USB 或同一 Wi-Fi），电脑会定时去游戏市场界面，把每个口径下面的子弹价格抓下来，存到本地数据库，网页上能看走势、当日最高最低，晚上八点会自动出一份当日财报，顺带用一套简单的规则给第二天怎么倒卖提个建议。

现在只保留电脑端这套（最早做过一个安卓 App 自动采集的版本，后来弃用删掉了）。

## 能干嘛

- 自动进市场、按口径逐个扫子弹，把名称和价格记下来
- 网页查看：最新价、当日最高最低、历史走势、子弹清单、导出 CSV/Excel
- 每个整点生成小时财报，每晚 8 点生成当日财报（含次日投资建议）
- 桌面控制端：实时看手机画面、鼠标点选点击位置、调频率、一键启停、一键重置

## 怎么跑

电脑端是 Python（FastAPI + SQLite + RapidOCR），桌面控制端是 C#（已经打包成单个 exe，双击就能用）。

装好 Python 3.12 之后：

```bash
cd pc
pip install -r requirements.txt
python entry.py web      # 起网页服务，浏览器打开 http://127.0.0.1:8600
```

采集用桌面控制端 `release\ABMCollectorApp.exe`，里面能选设备、标定点击位置、调采集频率、一键重置。发行版结构和使用方法见 `docs/DEPLOY_README.md`，需要自己从源码打包就用 `desktop/` 下的 C# 工程。

## 技术栈

FastAPI、uvicorn、SQLite、RapidOCR（onnxruntime / DirectML 加速）、Pillow、openpyxl；接口层用 Pydantic；桌面端是 C# / .NET 8；脚本走 adb（USB 或无线）。

## 目录

```
pc/        采集控制器 + 网页服务（Python）
desktop/   桌面控制端（C#，自包含 exe 的源码）
docs/      说明文档（怎么用、怎么调参、风险与合规）
release/   打包好的发行版（本地生成，不入库）
```

## 说几点

- 这是自己折腾着玩的东西，界面识别好不好用要看游戏实际布局，参数基本都放在 `pc/collector/config.json` 里，不对就调它
- 涉及对游戏界面的自动点击，**有账号风险**（可能被封），别拿它当什么稳定工具，更别拿去卖钱，风险自己担
