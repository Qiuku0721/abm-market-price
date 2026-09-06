# ABM 桌面采集控制端（C# / WinForms）

> 角色：**控制面板 + 画面预览标定**。手机画面经 USB(adb) 实时预览、鼠标点选"每轮点击位置"、
> 调节采集频率/清单，一键启动 **python 采集控制器**；识别与数据入库仍在 python 侧完成，两端共享
> `pc/collector/config.json`。网页统计（`http://127.0.0.1:8600`）保持不变。

## 界面功能

| 区域 | 功能 |
|---|---|
| 顶部设备栏 | 刷新/选择 adb 设备 |
| 左侧画面 | 「抓一帧」或勾选「实时预览(1s)」；**左键点画面 = 添加一个每轮点击点**（红圈+序号，顺序即执行顺序） |
| 右侧-导航点击 | 点列表可删除选中 / 试点最后 / 清空；「试点」立即对手机执行一次点击验证坐标 |
| 右侧-频率 | 采集频率（秒，5~86400），写入 `interval_sec` |
| 右侧-清单 | 子弹清单（每行一个），写入 `bullets` |
| 右侧-保存 | 写回 `config.json`（python 采集器直接读取） |
| 右侧-采集控制 | ▶ 启动 / ■ 停止 python `run_collector.py` 子进程，日志实时回显在底部 |
| 底部日志 | 采集器输出与本程序提示 |

## 构建与运行

环境：需要 .NET 8 SDK（本机已装到用户目录；命令行直接 `dotnet` 若不可用，用下面完整路径）。

```bash
# 编译（Release）
"%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe" build desktop\ABMCollectorApp\ABMCollectorApp.csproj -c Release

# 或发布为独立文件夹（含 exe，可拷贝）
"%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe" publish desktop\ABMCollectorApp\ABMCollectorApp.csproj -c Release -o dist\desktop
```

发布产物：`desktop\ABMCollectorApp\bin\Release\net8.0-windows\ABMCollectorApp.exe`
（发布到 `dist\desktop\ABMCollectorApp.exe`）。

> 程序放在仓库内运行即可自动找到 `pc/collector/config.json`；若拷贝到别处，
> 在界面里用「浏览…」重新指定 config 路径，采集启动会自动定位仓库内的 python 环境。

## 使用流程

1. 手机开 USB 调试插线；先双击 `pc\scripts\start.bat` 起网页服务（本程序不代管网页进程）。
2. 打开 ABMCollectorApp → 顶部「刷新设备」选中你的手机。
3. 点「抓一帧」看到游戏当前画面；把游戏切到市场入口后「实时预览」勾上，画面会持续刷新。
4. 依次左键点击：市场入口 → 子弹分类 →（需要的话其它按钮），生成红点列表；
   用「试点」验证坐标确实点中了目标。
5. 填频率（如 15 秒）与子弹清单 → 「保存配置」。
6. 「▶ 启动采集」——底部日志出现 python 输出；网页 `http://127.0.0.1:8600` 查看数据。
7. 想改点位/频率：改完**保存配置**，再「■ 停止」「▶ 启动」让采集器重新加载。

## 常见问题

| 现象 | 处理 |
|---|---|
| "未找到 adb" | 装 platform-tools 或设置 ANDROID_HOME；本机常见位置 `D:\IDEA\adb\platform-tools` |
| 设备列表为空 | 手机插线 + 允许 USB 调试授权，点「刷新设备」 |
| 画面点不了/没反应 | 先「抓一帧」成功、画面显示后再点选 |
| 「试点」点了没效果 | 确认当前画面正是游戏（需游戏在前台） |
| 启动采集报缺 .venv | 先运行 `pc\scripts\start.bat`（会装 Python 3.12 依赖，RapidOCR 不支持 3.14） |
| 想改滚动方向/价格区 | 保留在 `config.json` 的 `scroll` / `price_zone_left_x`（高级参数，本界面暂未收纳） |

## 与 CLI 的关系

本程序只是把 `python run_collector.py --config <路径>` 包了一层（写配置 + 拉子进程 + 日志）。
命令行方式 `cd pc && python run_collector.py` 依然可用，两者共用同一份 `config.json`。
