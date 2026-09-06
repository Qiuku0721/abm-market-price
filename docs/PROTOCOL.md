# 两端数据上报协议 v1

> 适用：手机端 Kotlin App（采集方）↔ 电脑端 Python 程序（接收方）
> 电脑端默认监听 `0.0.0.0:8600`；App 中配置电脑局域网 IP。

## 1. 通用约定

- 传输：HTTP/1.1 over TCP（局域网），默认 `http://<PC_IP>:8600`。
- 内容：`Content-Type: application/json`，UTF-8；快照上传为 `multipart/form-data`。
- 时间戳：ISO 8601 带时区偏移字符串，如 `2025-09-06T12:34:56+08:00`。
- 价格单位：**单发价格**（整数，科恩币 `Koen`，无小数）。
- `device_id`：App 首次启动生成 UUID 并持久化，用于多设备区分。
- 幂等去重键（PC 端）：`(device_id, bullet_name, market_type, captured_at 截断到分钟)` + 相同价格 → 判为重复；同键不同价格视为一次新观测。
- App 请求头携带 `X-ABM-Protocol: 1`；不匹配时 PC 返回 `406`。

## 2. 端点一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| POST | `/records` | 批量上报价格记录（核心） |
| POST | `/snapshots` | 上传截图快照（multipart），返回 `snapshot_id` |
| GET | `/api/latest` | 各子弹最新价 |
| GET | `/api/records` | 明细查询（分页） |
| GET | `/api/trend` | 走势点 |
| GET | `/api/bullets` | 子弹清单 CRUD |
| GET | `/export/csv` | 导出 CSV |
| GET | `/export/excel` | 导出 Excel（.xlsx） |

## 3. 上报记录 `POST /records`

请求体：

```json
{
  "device_id": "9f2e8d4a-1c3b-4a5e-9f0c-abcdef012345",
  "records": [
    {
      "bullet_name": "M80 5.56x45",
      "price": 320,
      "currency": "Koen",
      "market_type": "market",
      "captured_at": "2025-09-06T12:34:56+08:00",
      "source": "list_scan",
      "snapshot_id": "snap_9f2e8d4a_1757100896000.jpg"
    }
  ]
}
```

字段规格：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `device_id` | string(36) | 是 | UUID |
| `records[]` | array | 是 | 单批 ≤ 200 条，超出拆分 |
| `bullet_name` | string ≤ 64 | 是 | 归一化：去首尾空白、全角空格转半角 |
| `price` | int | 是 | 正整数，区间 [1, 10_000_000] |
| `currency` | string | 否 | 默认 `Koen` |
| `market_type` | string | 否 | 默认 `market`（保留扩展，如 `detail`） |
| `captured_at` | string(ISO8601) | 是 | 采集时刻 |
| `source` | string | 否 | `list_scan` 列表扫描（默认） |
| `snapshot_id` | string | 否 | 先传图后引用；无则不存图 |

成功响应 `200`：

```json
{
  "accepted": 1,
  "duplicates": 0,
  "rejected": [
    { "index": 0, "reason": "price out of range" }
  ]
}
```

## 4. 快照上传 `POST /snapshots`

- `multipart/form-data`：
  - `file`：JPEG/PNG，≤ 2 MB；
  - `meta`：JSON 字符串，含 `device_id`、`kind`（`list`/`detail`/`debug`）、`bullet_name`、`captured_at`。
- `snapshot_id` 由 **App 生成**并幂等：`snap_<device_id 前 8 位>_<epochMillis>.jpg`；同名重复上传覆盖，PC 落盘到 `pc/static/snapshots/<yyyyMMdd>/<snapshot_id>`。
- 响应 `200`：`{ "snapshot_id": "snap_...", "url": "/static/snapshots/20250906/snap_....jpg" }`

## 5. 查询接口（供本地页面）

- `GET /api/latest?device_id=` → `{ "bullet_name": { "price": 320, "captured_at": "...", "snapshot_id": "..." } , ...}`
- `GET /api/records?bullet=&from=&to=&device_id=&limit=200&offset=0` → 明细数组 + `total`
- `GET /api/trend?bullet=&window=1h|1d|7d|30d` → `[{ "t": "...", "price": 320 }, ...]`（按窗口聚合：1h=分钟点，其余按小时/日取最新）
- `GET /api/bullets` → 清单数组；`POST /api/bullets` / `DELETE /api/bullets/{name}` 增删（页面用）
- `GET /export/csv?bullet=&from=&to=` → `text/csv` 附件
- `GET /export/excel?bullet=&from=&to=` → `.xlsx` 附件
- `GET /health` → `{ "status": "ok", "time": "..." }`

## 6. 校验与错误

- 价格校验：`1 ≤ price ≤ 10_000_000`；`bullet_name` 非空且长度 ≤ 64。
- 非 2xx 响应统一为 `{ "error": { "code": "<code>", "message": "<说明>" } }`。
- App 端重试策略：网络错误或 `5xx` 进入本地队列，指数退避重试（1s → 2s → …上限 5min），队列保留 7 天；`400/406/422` 视为不可重试，丢弃并记日志；`429` 按 `Retry-After` 等待。

## 7. 版本协商

- 请求头 `X-ABM-Protocol: 1`，PC 响应同头。协议升级时递增版本号，旧 App 由 PC 返回 `406` 提示升级。

## 8. 示例（Windows PowerShell / curl.exe）

```bash
curl.exe -X POST http://127.0.0.1:8600/records -H "Content-Type: application/json" -H "X-ABM-Protocol: 1" -d '{"device_id":"9f2e8d4a-1c3b-4a5e-9f0c-abcdef012345","records":[{"bullet_name":"M80 5.56x45","price":320,"captured_at":"2025-09-06T12:34:56+08:00"}]}'

curl.exe -F "file=@shot.jpg" -F "meta={\"device_id\":\"9f2e8d4a-1c3b-4a5e-9f0c-abcdef012345\",\"kind\":\"list\"}" http://127.0.0.1:8600/snapshots
```
