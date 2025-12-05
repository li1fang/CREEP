# AssetEvent 写入接口（v1.0）

面向控制面与 Ingest API 的事件写入端点，严格对齐 [`schemas/v1.0/AssetEvent.json`](../../schemas/v1.0/AssetEvent.json)。

## 校验与可观测性
- 入参采用 JSON Schema v1.0 校验，失败时返回标准化的 `error_code` 与定位字段：
  - `E_SCHEMA_REQUIRED`：缺少必填字段
  - `E_SCHEMA_ADDITIONAL_PROPERTY`：包含未声明字段
  - `E_SCHEMA_FORMAT`：格式不合法（如 `occurred_at` 非 RFC3339 时间）
  - 其他校验错误统一使用 `E_SCHEMA_INVALID`
- 失败响应示例：

```json
{
  "ok": false,
  "error_code": "E_SCHEMA_FORMAT",
  "error_message": "occurred_at: 'not-a-datetime' is not a 'date-time'",
  "error_path": "occurred_at"
}
```

## OpenAPI（控制面/数据平面）
已生成 `deploy/api/asset_event_ingest.openapi.json`，关键片段：
- `POST /api/v1/asset-events`，请求体 `$ref` 至 `AssetEvent` Schema。
- 200 响应：`{"ok": true, "status": "accepted"}`
- 400 响应：携带 `error_code`、`error_message`、`error_path`

### 示例请求
```http
POST /api/v1/asset-events HTTP/1.1
Content-Type: application/json

{
  "event_id": "7d2e8edc-5f35-49de-8c73-309e4445a6a7",
  "tenant_id": "org_acme",
  "asset_id": "c5e5765c-3a7c-4c6b-8f46-93c291f6d580",
  "event_type": "TASK_SUCCESS",
  "occurred_at": "2024-05-12T08:00:00Z",
  "recorded_at": "2024-05-12T08:00:00Z",
  "version": 1,
  "severity": "INFO",
  "latency_ms": 123,
  "error_code": null,
  "message": "Task finished",
  "tags": ["task:checkout"],
  "context": {"region": "us-east"}
}
```

### 成功响应
```json
{"ok": true, "status": "accepted"}
```

### 失败示例（缺少必填字段）
```json
{
  "ok": false,
  "error_code": "E_SCHEMA_REQUIRED",
  "error_message": "event_id: 'event_id' is a required property",
  "error_path": "event_id"
}
```

## gRPC/Proto
生成的 Proto 位于 `deploy/api/asset_event_ingest.proto`，包含：
- `AssetEvent` message：字段与 Schema 对齐
- `AssetEventIngestService.PostAssetEvent`：请求 `AssetEvent`，响应带 `error_code`

## 回归校验
CI 将运行 `python src/tools/api_codegen.py --check`，确保 OpenAPI/Proto 与 Schema 一致；同时运行单测保证校验逻辑返回正确的 `error_code`。
