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
