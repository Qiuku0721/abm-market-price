# PC 端采集控制器（推荐方案）

> 新架构：**手机只当"屏幕"（不装采集逻辑），画面抓取、模拟点击、识别整理全部在电脑端完成**。
> 电脑通过 USB（adb）截屏并注入点击，RapidOCR 识别价格，结果直接写入与网页共用的 SQLite。
> 旧版「App 全自动采集」仍保留在 `android/`，可作为备选，与本方案互不干扰。

## 工作链路

```
手机(USB 调试) ──USB──▶ adb screencap 抓帧 ──▶ RapidOCR 识别名称/价格
        ▲                                      │
        └────── adb shell input tap/swipe ◀────┘ (PC 模拟点击)
                                        │ 命中写入
                                        ▼
                   pc/data/abm.db（与网页 server.py 共用，无需改动）
```

## 快速开始

1. **先起网页服务**（记录/统计/展示，必须）：`pc\scripts\start.bat`，浏览器 `http://127.0.0.1:8600`。
2. **手机插数据线**，开启「开发者选项 → USB 调试」，允许本机授权。
3. **编辑采集配置** `pc/collector/config.json`（首次会自动生成示例）：
   - `bullets`：要查价的子弹清单；
   - `interval_sec`：采集周期（秒）；
   - `nav_taps`：**关键**——每轮先点击的导航位置（进市场→子弹分类），格式 `[宽比例, 高比例]`，
     0~1 小数。先在游戏里目测入口/分类按钮位置填上；
   - `scroll` / `price_zone_left_x` 等：滚动与价格区参数（见文末调参）。
4. **启动采集**：
   ```bash
   cd pc
   python run_collector.py            # 自动连唯一 USB 设备，周期采集
   python run_collector.py --once     # 只跑一轮（调参时用）
   python run_collector.py --interval 30   # 覆盖周期
   ```
   或双击 `pc\scripts\start-collector.bat`。
5. 网页 `http://127.0.0.1:8600` 实时刷新即可看到价格（无需其它操作）。

> 采集日志：控制台 + `pc/collector/collector.log`。调试截图：`pc/collector/debug/page_XX.jpg`。

## 界面调参（首次必看）

App 停止自动采集后，**界面的适配全靠 config.json**，用调试截图辅助：

1. 跑一次 `python run_collector.py --once`，打开 `pc/collector/debug/page_00.jpg` 看当前画面。
2. 确认画面在**子弹列表**：不在的话，在游戏里记住「市场入口」「子弹分类」按钮位置
   （占屏幕的比例，例如底部中间=0.5,0.92），填进 `nav_taps` 再跑。
3. 看列表中每行价格在右侧还是别处：
   - 价格在行右侧 → 保持 `price_zone_left_x` 0.52 附近；
   - 价格在行中间/左侧 → 把 `price_zone_left_x` 调小（如 0.2），让价格格覆盖到价格列。
4. 方向不对（怎么滚都不动/列表反向）：游戏可能是**横屏**，把 `scroll.from_y/to_y`
   对调或按实际方向调整；`top_swipes` 让每轮先回到顶部。
5. 识别不准：放大识别靠裁剪。先看 debug 截图里命中行有没有截到价格。

## 网页没有数据的排查

| 现象 | 处理 |
|---|---|
| 启动即报"未检测到设备" | USB 线/调试/授权没就绪；`adb devices` 应显示 device |
| 一直"价格解析失败" | 价格不在预期位置 → 调 `price_zone_left_x`，看 debug 截图 |
| 一直"未找到" | 没进到子弹列表 → 填好 `nav_taps`；或名称与游戏显示不一致 |
| 控制台有"入库成功"但网页空 | 网页 `server.py` 没开，或等几秒刷新 |

## 名词：滚动方向

- 列表向下滚动看下一屏 = 手指**向上滑** = `swipe(0.5, 0.72h → 0.5, 0.30h)`（默认）；
- 回到列表顶部 = 手指**向下滑** 数次（`top_swipes`）。
- 若你的游戏市场是横屏且列表布局相反，调换 `scroll.from_y` 与 `scroll.to_y` 即可。
