## 📖 《AssetSnapshot v1.0》说明文档

> 状态：final
> 
> 
> 适用范围：CREEP 全栈系统中，对“资产当前状态”的唯一标准投影
> 

---

### 1. 版本信息

- **Schema 名称**：`AssetSnapshot`
- **版本号**：`v1.0`
- **发布编号**：`S-DOC-001-01`
- **状态**：`final`
- **发布主体**：自然控制系统核心执行体 / CREEP 协议层
- **发布日期**：2025-06-22

---

### 2. 结构总览

`AssetSnapshot v1.0` 描述的是：

> “某一时刻，一个数字资产在 CREEP 世界里的当前状态快照”
> 

它不记录历史事件，不记录钱的流水，只记录 **“现在长什么样”**：

- 归属关系（tenant / project / env）
- 分类与来源（SKU / Provider / Batch）
- 生命周期状态与健康度（status / health_score / usage_count）
- 并发占用能力（concurrency_mode / concurrency_limit / current_concurrency / active_lease_id）
- 静态财务视角（acquisition_cost / currency / expected_value）
- 业务规格与动态状态（meta_spec / meta_state）
- 快照版本与审计时间戳（snapshot_version / created_at / updated_at）

**真正的历史行为 & 资金流动**：

- 由 `AssetEvent`（事件审计）记录；
- 由 `LedgerEntry`（财务总账）记录；
- 与本 Schema 解耦。

---

### 3. 字段说明

### 3.1 身份与归属

- `asset_id`
    - 全局唯一资产 ID（UUID）。
    - 所有事件、账本、图谱都通过此 ID 关联到该资产。
- `tenant_id`
    - 所属租户/企业 ID。
    - 支撑多租户 SaaS 与跨企业 ERP。
- `project_id`
    - 项目 / 成本中心。
    - 用于 FinOps 维度聚合（按部门、业务线算成本和利润）。
- `env`
    - 环境标记，例如 `prod` / `staging` / `dev` / `sandbox` 等。
    - 用于隔离测试资源与生产资源。

---

### 3.2 分类与来源

- `sku_category`
    - 资产大类，当前枚举：
        - `RAW_NET`：网络耗材（IP、Proxy、VPN 节点等）
        - `RAW_FUND`：资金耗材（VCC、虚拟钱包、平台余额子账户等）
        - `INFRA`：基础设施（VPS、裸金属、K8s 节点、移动设备等）
        - `LOGIC`：逻辑资产（账号、Cookie、指纹 Seed、配置模板等）
        - `PRODUCT`：成品商品（可直接销售的 Token、Ticket、成品账号等）
        - `IDENTITY`：身份容器（Persona / 数字人），用于作为 AssetGraph 的 Root
    - 同一个 `sku_category` 会共享一套**状态机模板**，在补充文档中定义。
- `sku_code`
    - 具体 SKU 编码，用于业务可读标识，如：
        - `ip.residential.uk.london.4g`
        - `vcc.uk.visa.onetime.100`
        - `ticket.concert.ts.2025.london.a1`
- `provider_id`
    - 外部供应商 ID，例如：
        - `aws`, `gcp`, `hetzner`, `vultr`
        - `iproyal`, `proxy_empire`
        - `internal_mes`（内部 MES 生产线）
- `batch_id`
    - 采购批次号，用于：
        - 供应链溯源；
        - 批次级别熔断（某个批次 IP 全部判定为高风险时）。

---

### 3.3 状态与健康度

- `status`
    - 当前生命周期状态，枚举：
        - `NEW`：刚导入 / 采购，尚未完成质检
        - `READY`：可分配 / 可使用
        - `LOCKED`：已经被某个调度策略选中，正在建立 Lease
        - `IN_USE`：正在任务中被使用
        - `COOLING`：冷却期（比如 IP 刚用完，需冷却 N 小时）
        - `SOLD`：已售出（主要针对 PRODUCT / 部分 LOGIC）
        - `BANNED`：标记为高风险 / 禁用
        - `ARCHIVED`：归档，不再参与调度（仅保留读）
- `health_score`
    - 0–100 的浮点数，用于评估资源质量：
        - 高频成功 + 低失败 → 高分；
        - 高频封号 / 验证码 / 风控 → 降分；
    - 具体更新逻辑由上层 SRM 控制器定义。
- `usage_count`
    - 累计使用次数（被 Task / Lease 绑定的次数）。
- `fail_count`
    - 累计失败次数（或近期窗口内的失败数，由策略决定）。
- `last_status_change_at`
    - 上一次 `status` 字段发生变化的时间。
- `last_used_at`
    - 上一次参与任务的时间（通常由 Lease 完成时回写）。
- `quality_flags`
    - 字符串数组，用于挂载若干质量标签，例如：
        - `["high_success_rate", "residential_ip", "suspected_ban_wave"]`

---

### 3.4 并发能力与租约绑定（响应“并发设计过于简陋”的驳回）

这一块是对 **云服务器 / 高性能 IP 池** 等场景的直接回应。

- `concurrency_mode`
    - 枚举：
        - `EXCLUSIVE`：该资产每次只能被一个 Lease 使用（典型：VCC、敏感账号）
        - `SHARED`：该资产可以被多个 Lease 并行使用（典型：高配 VPS 节点）
    - 该字段由策略在创建 Asset 时确定，通常不会在生命周期中更改。
- `concurrency_limit`
    - 整数 ≥ 1
    - 描述该资产最多允许同时绑定多少个 Lease：
        - 对 `EXCLUSIVE`，规范要求 `concurrency_limit = 1`
        - 对 `SHARED`，可以是 10 / 50 / 100 等由容量评估产生的数值
- `current_concurrency`
    - 整数 ≥ 0
    - 表示**当前**正在与该资产绑定的 Lease 数量（聚合值）：
        - 定义上是一个**缓存字段**，真实关系由 Lease 表决定；
        - 控制面调度时通常使用 `current_concurrency < concurrency_limit` 作为可分配条件。
- `active_lease_id`
    - 仅对 `concurrency_mode = EXCLUSIVE` 有强语义：
        - 当 `concurrency_mode = EXCLUSIVE` 且 `current_concurrency = 1` 时：
            - `active_lease_id` 应当等于当前唯一 Lease 的 ID；
        - 当 `current_concurrency = 0` 时，应为 `null`/缺省；
        - 当 `concurrency_mode = SHARED` 时：
            - `active_lease_id` 没有强含义，可为空或由实现方用于“最近 Lease”的调试用途。

> 说明：
> 
> - 共享资源下的“具体有哪些 Lease 绑定”不在本 Schema 内表达，而由单独的 Lease/Usage 表承担；
> - 本 Schema 只提供调度层需要的**聚合视图**，避免昂贵的实时 join。

---

### 3.5 财务视角（静态成本与估值）

- `currency`
    - 该资产 **记账币种**，使用 ISO 4217 三位大写字符串（如 `USD`, `EUR`, `USDT`）。
- `acquisition_cost`
    - 获取成本（购买、生产或内部结转时的初始成本），≥ 0。
    - 不包含后续任务过程中的运行成本（例如 Gas、带宽、CPU 时间）。
- `estimated_unit_cost`
    - 对“单位使用”的估算成本（可选），用于：
        - 调度时做 Shadow Pricing；
        - 供上层 FinOps 做“如果使用这个资源，每次大概会烧多少钱”的粗估。
- `expected_value`
    - 资产预期价值 / 售价（可选）：
        - 对 `PRODUCT`（票、Token、账号）尤为关键；
        - 对 `INFRA` 可用于估计残值。

> 真正的收入 / 成本 / 利润，以 LedgerEntry 为准。
> 
> 
> AssetSnapshot 只反映“当前账面视角”。
> 

---

### 3.6 规格与动态状态

- `meta_spec`
    - 静态规格对象（不可变），典型例子：
        - IP：`{"ip":"1.2.3.4","geo":"GB","asn":"...","type":"residential"}`
        - VCC：`{"bin":"438628","issuer_country":"GB","brand":"VISA"}`
        - INFRA：`{"region":"eu-central","cpu":2,"ram_gb":4,"disk_gb":40}`
        - PRODUCT：`{"event":"TS_TOUR_2025","seat":"A1","venue":"O2","date":"2025-06-01"}`
- `meta_state`
    - 动态状态对象（可变），典型例子：
        - VCC：`{"balance":5.20,"last_tx_status":"success"}`
        - IP：`{"last_check_status":"ok","last_rtt_ms":80}`
        - INFRA：`{"power_state":"running","platform_balance":12.5}`
- `meta_schema_version`
    - 标识 `meta_spec/meta_state` 所遵循的结构版本（如 `raw_net.v1` / `infra.v2`），
    - 便于在演进时做兼容处理和迁移。

---

### 3.7 快照元数据

- `snapshot_version`
    - 整数 ≥ 1，用于：
        - 乐观锁（避免并发覆盖写）；
        - 允许上层在更新 AssetSnapshot 时基于 `snapshot_version` 做 CAS 检查。
- `created_at`
    - 快照记录首次创建时间（通常为资产入库时刻）。
- `updated_at`
    - 最近一次更新本快照的时间（任何字段变动都会更新）。

---

### 4. 设计意图

1. **名词/动词分离**
    - `AssetSnapshot` 是**名词视角**：它不记录“发生了什么”，只记录“现在是什么样子”。
    - 具体行为将由 `TaskOrder`（动词）、`AssetEvent`、`LedgerEntry` 等 Schema 承担。
2. **并发语义明确化**
    - 响应“昂贵服务器只能跑一个任务”的红队批评：
        - 显式给出 `concurrency_mode / concurrency_limit / current_concurrency`；
        - 保留 `active_lease_id` 只为 EXCLUSIVE 模式服务；
        - 真正的 Lease 列表外置，AssetSnapshot 只做聚合。
3. **财务口径内聚**
    - 仅保留 acquisition_cost / estimated_unit_cost / expected_value 这种 **静态视角**；
    - 所有“任务级别的烧钱”和“销售收入”全部落到 `LedgerEntry`，避免混淆。
4. **结构可扩展但受控**
    - 顶层字段采用 `additionalProperties=false`，确保 Schema 的强约束；
    - 各业务特有属性全部塞进 `meta_spec` / `meta_state`，由各自的二级 Schema 管理。

---

### 5. 使用场景示例

### 场景 1：调度一台可以同时跑 50 个任务的 VPS

- `sku_category = "INFRA"`
- `concurrency_mode = "SHARED"`
- `concurrency_limit = 50`
- `current_concurrency = 37`

调度器逻辑：

- 查询：`status = READY`，`concurrency_mode = SHARED`，`current_concurrency < concurrency_limit`
- 选择上述 VPS，尝试为下一个 Task 创建新的 Lease；
- Lease 创建成功 → `current_concurrency` 聚合 +1（异步 from Lease 表）。

### 场景 2：一次性 VCC 为抢票任务服务

- `sku_category = "RAW_FUND"`
- `concurrency_mode = "EXCLUSIVE"`
- `concurrency_limit = 1`
- `current_concurrency = 0` 或 `1`
- `active_lease_id` 标记当前占用它的任务（如有）。

调度器只会在 `current_concurrency = 0` 时考虑分配该卡。

### 场景 3：卖出一张 Product（演唱会门票）

- `sku_category = "PRODUCT"`
- Task 成功后，生产出一个 `AssetSnapshot`：
    - `status = READY`/`IN_STOCK`（取决于策略）
    - `expected_value` 填入预期售卖价格
- 当实际卖出后：
    - 写一条 `LedgerEntry` 记录收入；
    - AssetSnapshot.status → `SOLD`；
    - `updated_at` / `snapshot_version` 递增。

---

### 6. 协作提示（与其他 Schema 的契约）

1. **与 TaskOrder (`TaskHeader`) 的关系**
    - Task 不直接修改 AssetSnapshot，而是通过：
        - 触发 Lease 创建 / 完成；
        - 触发 AssetEvent；
    - **TaskOrder Schema v1.0 必须包含 `idempotency_key` 字段**：
        - 由上游调用方生成；
        - 相同 `(tenant_id, idempotency_key)` 的 Task 创建请求必须幂等；
        - 这是高频抢票/打码场景防止重复下单的最低保障。
2. **与 AssetEvent 的关系**
    - 任意对 AssetSnapshot 的 `status / health_score / concurrency_* / meta_*` 的变更，
        
        均应产生至少一条 `AssetEvent`：
        
        - event_type 明确；
        - `old_status` / `new_status` 可选填；
    - AssetEvent 的 `payload` 将采用**约束性顶层 Key**，在即将发布的 `AssetEvent v1.0` 中约定至少包括：
        - `error_code`（标准化错误码或结果码）
        - `external_latency_ms`（外部依赖耗时）
        - `provider_status`（下游返回状态汇总）
        - 以及一个 `context` 子对象存放长尾信息
    - 这样可以兼顾灵活性和可治理性。
3. **与 LedgerEntry 的关系**
    - AssetSnapshot 不负责记录钱的流动，只负责：
        - 挂住 `currency` 和 `acquisition_cost`；
        - 为 Ledger 提供 asset_id / tenant_id 等聚合维度。
    - LedgerEntry 通过 `asset_id` + `task_id` 实现精细归因。
4. **与 AssetGraph 的关系**
    - AssetGraph 以 `asset_id` 为节点，描述：
        - 哪些 RAW_NET / RAW_FUND / INFRA / LOGIC 被用来生产某个 PRODUCT；
        - 哪个 IDENTITY 是一棵 Persona 子图的 Root。
    - AssetSnapshot 不存图结构，仅存当前节点自身信息。

---
