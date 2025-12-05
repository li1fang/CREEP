# AssetEvent 存储（v1.0)

本文档给出与 [`schemas/v1.0/AssetEvent.json`](../../schemas/v1.0/AssetEvent.json) 对齐的数据库建模与迁移示例，遵循 Schema v1.0 的字段和约束。

## 目标
- 保持与 Schema 必填字段一致（`event_id`, `tenant_id`, `asset_id`, `event_type`, `occurred_at`, `recorded_at`, `version` 设为 NOT NULL）。
- 追加写（Append-Only）：不允许 UPDATE/DELETE，所有历史均可重放。
- 优化链路追踪：为 `tenant_id + occurred_at`、`correlation_id + occurred_at`、`causation_id` 建索引。
- 支撑高写入：按月分区示例，可按租户或时间滚动扩展。

## 示例 DDL / 迁移脚本
迁移脚本位于 [`deploy/sql/asset_events_v1_0.sql`](../../deploy/sql/asset_events_v1_0.sql)，要点如下：

- **字段对齐**：类型与 JSON Schema 对齐，`severity`、`http_status`、`latency_ms`、`version` 等都带校验。
- **主键**：`event_id + occurred_at` 联合 PK，满足分区唯一约束要求并保持事件唯一性。
- **组合索引**：覆盖租户时间序、资产画像（`asset_id + occurred_at`）、调用链（correlation）、因果链（causation）、任务归因（`task_id`）。
- **追加写保护**：触发器阻止 UPDATE/DELETE，违反即抛错。
- **分区示例**：默认按 `occurred_at` RANGE 分区，附带 2024-09/10 示例分区，可由运维任务滚动创建后续分区；若需租户分片，可改为 `PARTITION BY LIST (tenant_id)`。

## 使用建议
1. 在上线前执行脚本，或将其拆分成迁移管理工具的 step：
   ```sql
   \i deploy/sql/asset_events_v1_0.sql
   ```
2. 如果写入量高，建议提前创建未来 2~3 个月的分区，或用调度任务在月底自动生成下一月分区。
3. 追加写策略与审计需求一致，如需数据修正，请采用“补偿事件”而非更新历史行。
4. 若租户隔离需求更高，可改用 `PARTITION BY LIST (tenant_id)` 并按租户/月份组合创建分区，索引定义保持不变。

> Schema 版本：v1.0（请在未来版本升级时同步更新本文档与 SQL 脚本）。

## 链路查询与审计视图
- 在 `deploy/sql/asset_events_v1_0.sql` 中新增 `asset_event_traces` 视图以及 `trace_asset_events` 查询函数，用于把 AssetEvent 与 TaskOrder / AssetSnapshot / LedgerEntry 进行左连接并按时间轴返回。
- 典型排障/审计用法：
  ```sql
  -- 按 task_id 获取事件序列
  SELECT * FROM trace_asset_events('00000000-0000-0000-0000-000000000001');

  -- 按 correlation_id 获取调用链
  SELECT * FROM trace_asset_events(NULL, 'corr-123')
  WHERE tenant_id = 'demo-tenant';

  -- 直接使用视图并带其他过滤条件
  SELECT *
  FROM asset_event_traces
  WHERE tenant_id = 'demo-tenant'
    AND env = 'prod'
    AND occurred_at >= now() - interval '1 day'
  ORDER BY occurred_at;
  ```
> 提示：`asset_event_traces` 暴露 `event_old_status`/`event_new_status`（事件时上下文）与 `current_asset_status`（最新快照）两个维度，避免把“事后快照”误解为事件当时的状态。

## 法医诊断视图（并发场景快速归因）
在高并发/多 Worker 场景下，为避免导出 CSV 做透视表，新增两个聚合视图直接输出“谁表现差”“怎么死的”：

### 供应商/品类绩效（view_provider_performance）
按 `provider_id + sku_category + error_code` 聚合过去 24 小时的成功率和耗时，可直接找出劣质供应商或脆弱 SKU：

```sql
-- 找出成功率低于 80% 的供应商/品类
SELECT *
FROM view_provider_performance
WHERE success_rate < 0.8
ORDER BY success_rate ASC, avg_latency_ms DESC;

-- 聚焦某个 provider 的耗时与错误分布
SELECT sku_category, error_code, total_tasks, failure_count, success_rate, avg_latency_ms
FROM view_provider_performance
WHERE provider_id = 'provider-123'
ORDER BY success_rate ASC;
```

### 失败指纹分布（view_error_patterns）
按 `task_type + error_code + http_status` 聚合失败次数与受影响资产数，一眼看出是大规模封号（资产数多）还是逻辑错误：

```sql
-- 查看近 24 小时主要失败形态
SELECT *
FROM view_error_patterns
ORDER BY occurrence_count DESC
LIMIT 20;

-- 检查单一错误是否集中在特定 task_type
SELECT task_type, occurrence_count, affected_asset_count
FROM view_error_patterns
WHERE error_code = 'IP_BANNED'
ORDER BY occurrence_count DESC;
```

## task_id / lease_id 的外键或弱引用
- 同步约束：脚本使用 `NOT VALID + DEFERRABLE` 外键（`fk_asset_events_task`、`fk_asset_events_lease`）指向 `task_orders(task_id)`、`leases(lease_id)`，默认 `ON DELETE SET NULL` 避免删除上游记录时阻塞事件表。该设计可在写入高峰时先挂载约束、再用后台作业 `VALIDATE CONSTRAINT` 完成校验。
- 异步校验（跨库或历史存量）：当 TaskOrder/Lease 不与 AssetEvent 同库时，可保留弱引用（约束存在但暂不 VALIDATE），并用夜间/低峰任务执行：
  ```sql
  -- 异步校验并回填坏数据
  ALTER TABLE asset_events VALIDATE CONSTRAINT fk_asset_events_task;
  ALTER TABLE asset_events VALIDATE CONSTRAINT fk_asset_events_lease;
  ```
  对于校验失败的行，可按 `task_id` / `lease_id` 进行修复或补全数据后再次 VALIDATE；若无法修复，可把引用置空并记录补偿事件。
- 结合链路追踪：上述视图/函数允许在审计时同时观察 Task/Lease、资产画像与资金流水，便于快速定位“谁触发”“用了哪个 Lease”“产生了哪些账务影响”。
