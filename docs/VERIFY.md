# 端到端验证手册

> ⚠️ 注：§4「手机端真机回归」为**已弃用**的安卓 App 方案内容；
> 当前电脑端采集的验证以 `pc/collector/debug/` 截图 + `config.json` 调参为准（见 `docs/PC_COLLECTOR.md`）。

> 环境安装与依赖验证见 `SETUP.md`；本手册覆盖**联调运行级验证**。
> 当前开发机无 Python / Android SDK，以下命令需在就绪环境执行（预期输出已列出）。

## 1. 电脑端冒烟

```bash
cd pc
python server.py
# 预期：Uvicorn running on http://0.0.0.0:8600
```

```bash
curl.exe -s http://127.0.0.1:8600/health
# 预期：{"status":"ok","time":"...","records":0,"bullets":0,"devices":0}
```

## 2. 模拟上报全链路（无需手机）

```bash
# 2.1 上报一条价格记录（X-ABM-Protocol:1）
curl.exe -X POST http://127.0.0.1:8600/records ^
  -H "Content-Type: application/json" -H "X-ABM-Protocol: 1" ^
  -d "{\"device_id\":\"sim-dev-1\",\"records\":[{\"bullet_name\":\"M80 5.56x45\",\"price\":320,\"captured_at\":\"2025-09-06T12:34:56+08:00\"}]}"
# 预期：{"accepted":1,"duplicates":0,"rejected":[]}

# 2.2 原样重放 → 应判重
# 预期：{"accepted":0,"duplicates":1,"rejected":[]}

# 2.3 版本不匹配 → 406
curl.exe -X POST http://127.0.0.1:8600/records -H "X-ABM-Protocol: 9" ^
  -H "Content-Type: application/json" -d "{\"device_id\":\"d\",\"records\":[]}"
# 预期：HTTP 406
```

```bash
# 2.4 快照上传（生成 1x1 PNG 即可）
curl.exe -F "file=@shot.png" -F "meta={\"device_id\":\"sim-dev-1\",\"kind\":\"row\"}" http://127.0.0.1:8600/snapshots
# 预期：{"snapshot_id":"shot.png","url":"/static/snapshots/<date>/shot.png"}

# 2.5 快照可访问
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8600/static/snapshots/<date>/shot.png
# 预期：200
```

```bash
# 2.6 查询与导出
curl.exe -s http://127.0.0.1:8600/api/latest          # 各子弹最新价 + 涨跌
curl.exe -s "http://127.0.0.1:8600/api/trend?bullet=M80%205.56x45&window=1d"
curl.exe -s "http://127.0.0.1:8600/api/records?limit=10"
curl.exe -s -o prices.csv http://127.0.0.1:8600/export/csv && head -2 prices.csv
curl.exe -s -o prices.xlsx http://127.0.0.1:8600/export/excel   # 打开应正常
```

页面：浏览器打开 `http://127.0.0.1:8600` → 最新价出现「M80 5.56x45 / 320」→ 走势图有 1 个点 → 明细可见 → 快照链接可打开。

## 3. 自动化测试

```bash
cd pc && python -m pytest -q
# 预期：全部通过（数据层去重/校验、统计涨跌、API 端到端）
```

## 4. 手机端真机回归（需真实游戏账号）

| # | 步骤 | 预期 |
|---|---|---|
| 1 | 手机连同一 Wi-Fi；电脑端已运行 | `/health` ok |
| 2 | App 填电脑 IP → 开启无障碍 → 点「开始」→ 授予屏幕录制 | 通知栏出现「采集中」，App 日志显示就绪 |
| 3 | 游戏切到市场列表页并保持前台 | App 自动滚动扫描 |
| 4 | 观察 App 日志 | 出现「命中 X = 价格」与轮次摘要 |
| 5 | 电脑端页面 /api/latest | 有对应子弹最新价 |
| 6 | 对照游戏内实价 | 数值一致 |
| 7 | 连续运行 ≥ 30 分钟 | 无崩溃/卡死，记录持续增长 |
| 8 | 中途关闭电脑端服务再恢复 | App 本地队列补齐重传（pending 目录清空） |
| 9 | 打开明细中的快照 | 与命中行一致，可人工核对 OCR |

## 5. 已知限制（验证边界）

- **本开发机未装 Python / JDK / Android SDK**：§2/§3/§4 与 SETUP §A/§B 的验证均未在本机执行；交付为源码 + 命令预期。
- 识别假定「市场列表页、价格在行右侧」，界面改版后需按 `LayoutProfile` 与命中行快照调参。
- 名称单行断行可能漏匹配（App 日志有「未找到」提示项）。
- 模拟点击自动化存在封号风险（见 README/PLAN 风险章节），工具内置限频与抖动。

## 6. 常见问题

| 现象 | 排查 |
|---|---|
| App 日志「无障碍服务未连接」 | 系统设置开启 ABM Collector 手势服务后重启采集 |
| 截屏全黑/无帧 | 重新授予屏幕录制权限（Android 14 每次会话需授权） |
| 页面无数据 | 检查 App 与 PC 同一网段、IP 端口正确、`/health` 可访问 |
| 上报 406 | App 与 PC 协议版本不一致（`X-ABM-Protocol`） |
| 某子弹总「未找到」 | 该列表页可能不含此项或名称被断行；可改走详情页扩展（未来版本） |
