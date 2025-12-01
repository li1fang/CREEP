## 📖 二、《AssetEvent v1.0》说明文档

### 1. 版本信息

- **Schema 名称**：`AssetEvent`
- **Schema 代号**：`S-04`
- **版本**：`v1.0`
- **Schema ID**：`schema://creep/AssetEvent.v1.0`
- **状态**：`final`
- **适用范围**：
    
    CREEP 中所有“围绕某个资产发生的事件”的统一结构，用作 **黑匣子 / 审计日志 / 调试基础数据**。
    

> 定位一句话：
> 
> 
> **AssetEvent = 某一刻，某个 Asset 发生了什么、为什么、由谁触发、耗时多久。**
> 

---

### 2. 结构总览

`AssetEvent v1.0` 记录的是：

> “在某个时间点，一个资产发生了一件有意义的事（event_type），
> 
> 
> 这件事由谁触发，处于什么上下文，导致了什么状态变化，
> 
> 并携带标准化的 debug 维度（error_code / provider_status / latency_ms 等）。”
> 

特征：

- **Append-Only（追加写）**：事件只能新增，不能修改/删除；
- **强结构化 Payload**：关键调试维度被提升为一级字段（而不是扔进垃圾桶 `payload`）；
- **因果链可追踪**：`correlation_id` + `causation_id` 串联 Task → Allocation → Production → Sale 全链路。

---

### 3. 字段说明

### 3.1 标识与多租户

- **event_id** (`uuid`, required)
    - 事件唯一 ID。
    - 用于：
        - 事件流重放；
        - `causation_id` 引用；
        - 调试和审计中的“证据编号”。
- **tenant_id** (`string`, required)
    - 事件所属租户 ID，与 AssetSnapshot / TaskOrder / LedgerEntry 对齐。
- **project_id** (`string`, optional)
    - 项目 / 成本中心，方便按业务线过滤事件。
- **env** (`string`, optional)
    - `prod` / `staging` / `dev` 等环境标记。

---

### 3.2 目标资产与关联实体

- **asset_id** (`uuid`, required)
    - 此事件对应的资产 ID（`AssetSnapshot.asset_id`）。
    - AssetEvent 是“围绕资产的事件”，因此 asset_id 必须存在。
- **task_id** (`uuid`, optional)
    - 若该事件是由某个 Task 引发，则挂上 `TaskOrder.task_id`。
    - 示例：
        - 某任务执行失败导致 IP `BANNED`；
        - 某任务成功导致 PRODUCT 被 `SOLD`。
- **lease_id** (`uuid`, optional)
    - 若该事件与某个 Lease 强相关（例如某次租用期内被风控），可挂上 Lease ID。

---

### 3.3 因果链：correlation_id & causation_id

> 这部分直接响应你提出的 “因果链” 需求。
> 
- **correlation_id** (`string`, optional)
    - 表示**一条业务请求 / 调用链的全局关联 ID**，通常由上游系统生成；
    - 同一条链路上的所有事件（Task 创建、Lease 分配、Asset 使用、错误返回等）应共享同一个 correlation_id；
    - 用于：
        - 在分布式系统中重构“当时发生了什么”；
        - 将跨服务日志拼接成一条完整时间线。
- **causation_id** (`uuid`, optional)
    - 表示**“谁直接导致了我”**：
        - 即：本事件由哪一个 `event_id` 直接引起；
    - 示例：
        - `Task_FAIL` 事件的 `causation_id` 指向某个 `HTTP_403` 的 AssetEvent；
        - `Asset_BANNED` 事件的 `causation_id` 指向多次失败中的最后一条关键错误事件。

> 设计用法：
> 
> - `correlation_id`：横向串起一整条链（请求级别）。
> - `causation_id`：纵向表示直接前因（事件级别）。

---

### 3.4 事件类型与来源

- **event_type** (`string`, required)
    - 表示“发生了什么”，是这条事件的主语。
    - 建议在租户内部维护枚举，如（非 Schema 强制）：
        - `PROCURED`, `IMPORTED`
        - `INSPECTED_PASS`, `INSPECTED_FAIL`
        - `ALLOCATED`, `RELEASED`
        - `TASK_SUCCESS`, `TASK_FAIL`, `TASK_TIMEOUT`
        - `COOLING_START`, `COOLING_END`
        - `BANNED`, `UNBANNED`
        - `SOLD`, `ARCHIVED`
- **source** (`string`, optional)
    - 谁发出的事件：
        - `control_plane`
        - `worker_node`
        - `external_provider`
        - `finops_daemon`
    - 用于快速区分“是自己逻辑的问题，还是外部世界的问题”。
- **severity** (`"DEBUG" | "INFO" | "WARN" | "ERROR"`, optional)
    - 标准日志级别：
        - `DEBUG`：调试信息；
        - `INFO`：正常状态变更；
        - `WARN`：可疑行为、临时错误；
        - `ERROR`：严重错误、不可忽略问题。

---

### 3.5 状态变更与描述

- **old_status** (`string`, optional)
    - 事件发生前的资产状态，通常对应 `AssetSnapshot.status` 的值。
- **new_status** (`string`, optional)
    - 事件发生后的资产状态。
    - 例如：
        - `READY` → `IN_USE`
        - `IN_USE` → `COOLING`
        - `READY` → `BANNED`

> 状态机的合法转移矩阵由 AssetSnapshot 的附属文档定义，
> 
> 
> AssetEvent 仅记录“当时是如何变化的”。
> 
- **message** (`string`, optional)
    - 人类可读的一句总结，例如：
        - `"IP got HTTP 403 from target site"`
        - `"VCC declined: insufficient funds"`
        - `"Asset cooled down and ready again"`

---

### 3.6 标准化调试字段（Structured Payload）

> 回应“payload 不能变垃圾桶”的审查意见：
> 
> 
> 关键调试信号必须被提升为一级字段。
> 
- **error_code** (`string`, optional)
    - 标准化错误码 / 结果码。建议：
        - 内部业务错误码（如 `E_IP_BANNED`, `E_CARD_DECLINED`）；
        - 或统一映射后的 provider error code。
- **error_message** (`string`, optional)
    - 错误详情的紧凑描述，便于日志和 UI 展示。
- **provider_status** (`string`, optional)
    - Provider 视角的状态概括，例如：
        - `"OK"`, `"BANNED"`, `"TEMP_BLOCK"`, `"RISKY"`, `"DOWN"` 等；
    - 可以映射自多次调用结果。
- **http_status** (`integer 100–599`, optional)
    - 如这次事件涉及 HTTP 调用，可记录对应状态码。
- **latency_ms** (`integer >= 0`, optional)
    - 与本事件绑定的**关键调用**的耗时（毫秒），通常是：
        - 调用目标站点；
        - 调用 Provider；
        - 调用内部关键服务。
- **retryable** (`boolean`, optional)
    - 当前错误是否被策略视为“可重试”。
    - 例如：
        - 网络抖动 → `true`
        - 被明确 BAN → `false`

---

### 3.7 时间戳与标签

- **occurred_at** (`date-time`, required)
    
    > 事件从业务语义看“发生的那一刻”。
    > 
- **recorded_at** (`date-time`, required)
    
    > 事件被写入 CREEP 的时间。
    > 
    - 可能晚于 `occurred_at`，例如异步回传或批量导入。
- **tags** (`string[]`, optional)
    - 任意标签，用于筛选事件，如：
        - `["ts_tour_london", "captcha", "ban_wave"]`

---

### 3.8 上下文扩展

- **context** (`object`, optional)
    - 长尾调试信息的容器。
    - 设计原则：
        - Top-Level keys 只放“稳定、经常需要被查询”的东西；
        - 其它“仅在 debug 场景用到”的复杂结构可以塞在 context 里；
        - 大日志内容不要直接塞进来（建议引用存储位置）。
- **version** (`int >= 1`, required)
    - 用于 Schema 内部演进和极端场景下的并发保护。
    - 业务上应把 AssetEvent 当作 **不可修改**：
        - `version` 一般固定为 1；
        - 如确需修正字段（例如修正 error_message 拼写），也应该视为新的事件，或在 context 中补充，而不是改旧记录。

---

### 4. 设计意图

1. **把 Debug 提升到“结构层问题”，而不是“日志细节”**
    - AssetEvent 不是“随便打一行 log”，而是：
        - 具备强结构的、可检索的、可回放的数据点；
        - error_code / provider_status / latency_ms 被标准化成字段；
    - 后续做 AI 诊断、自动归因、BAN 波检测，都可以直接用这张表做训练数据。
2. **Append-Only：历史永远不被篡改**
    - AssetEvent 旨在成为“黑匣子”：
        - 不允许 update/delete；
        - 更正通过新增新事件来表达；
    - LedgerEntry 管钱，AssetEvent 管“发生过什么”。
3. **因果链：correlation_id + causation_id**
    - correlation_id：
        - 把一次用户请求 / job / control-plane action 下的所有事件串起来；
    - causation_id：
        - 明确“这个事件是由哪个 event 引起的”；
    - 这让你可以回答：
        - “为什么这个 IP 最终被标记为 BANNED？”
            
            → 顺着 causation 链向上爬；
            
        - “某次抢票请求从接收到结束，中间走过了哪些服务？”
            
            → 按 correlation_id + 时间线重建全链路。
            
4. **紧密对齐 AssetSnapshot / TaskOrder / LedgerEntry**
    - AssetSnapshot：
        - 当前状态（一个 asset 的 latest view）。
    - TaskOrder：
        - 谁发起了什么任务。
    - LedgerEntry：
        - 因此付/收了多少钱。
    - AssetEvent：
        - 中间发生了哪些关键时刻、怎么变化的、出错在哪、耗时多少。

---

### 5. 使用场景示例

### 场景 1：IP 被目标站点 403 拒绝一次（可重试）

```json
{
  "event_id": "uuid-e1",
  "tenant_id": "tenant_a",
  "project_id": "project_qa",
  "env": "prod",

  "asset_id": "uuid-ip-1",
  "task_id": "task-e2e-123",
  "lease_id": "lease-xyz",
  "correlation_id": "corr-req-abc",
  "causation_id": null,

  "event_type": "HTTP_PROBE_FAIL",
  "source": "worker_node",
  "severity": "WARN",
  "old_status": "IN_USE",
  "new_status": "IN_USE",

  "message": "Target site returned HTTP 403 during checkout step",
  "error_code": "E_HTTP_403",
  "error_message": "Forbidden by target site",
  "provider_status": "OK",              // IP provider 本身没问题
  "http_status": 403,
  "latency_ms": 850,
  "retryable": true,

  "occurred_at": "2025-06-22T10:00:01Z",
  "recorded_at": "2025-06-22T10:00:01Z",

  "tags": ["checkout", "forbidden"],
  "context": {
    "url": "https://target.example.com/checkout",
    "method": "POST"
  },
  "version": 1
}

```

### 场景 2：IP 多次 403 后被标记 BANNED

```json
{
  "event_id": "uuid-e2",
  "tenant_id": "tenant_a",
  "project_id": "project_qa",
  "env": "prod",

  "asset_id": "uuid-ip-1",
  "task_id": "task-e2e-123",
  "lease_id": "lease-xyz",
  "correlation_id": "corr-req-abc",
  "causation_id": "uuid-e1",

  "event_type": "ASSET_BANNED",
  "source": "control_plane",
  "severity": "ERROR",
  "old_status": "IN_USE",
  "new_status": "BANNED",

  "message": "IP banned due to repeated HTTP 403 failures",
  "error_code": "E_IP_BANNED",
  "error_message": "IP considered risky by target site",
  "provider_status": "RISKY",
  "http_status": 403,
  "latency_ms": 0,
  "retryable": false,

  "occurred_at": "2025-06-22T10:00:05Z",
  "recorded_at": "2025-06-22T10:00:05Z",

  "tags": ["ban_wave"],
  "context": {
    "fail_count_window": 5,
    "window_s": 60
  },
  "version": 1
}

```

### 场景 3：VCC 支付成功事件

```json
{
  "event_id": "uuid-e3",
  "tenant_id": "tenant_a",
  "project_id": "project_ticket",
  "env": "prod",

  "asset_id": "uuid-vcc-1",
  "task_id": "task-ts-snipe-001",
  "lease_id": "lease-vcc-123",
  "correlation_id": "corr-ts-req-888",
  "causation_id": null,

  "event_type": "PAYMENT_SUCCESS",
  "source": "worker_node",
  "severity": "INFO",
  "old_status": "IN_USE",
  "new_status": "IN_USE",

  "message": "Payment completed via VCC",
  "error_code": null,
  "error_message": null,
  "provider_status": "OK",
  "http_status": 200,
  "latency_ms": 320,
  "retryable": false,

  "occurred_at": "2025-06-22T20:00:01Z",
  "recorded_at": "2025-06-22T20:00:01Z",

  "tags": ["ts_tour_london", "payment"],
  "context": {
    "amount": 120.0,
    "currency": "USD"
  },
  "version": 1
}

```

---

### 6. 协作提示（与其他 Schema 的契约）

- **与 AssetSnapshot v1.0**
    - AssetEvent 不直接更新 AssetSnapshot，但：
        - 每次对状态有影响的事件（如 BANNED/COOLING_START/COOLING_END）
            
            应由控制面根据事件内容来修改 AssetSnapshot；
            
    - 事件记录“发生过什么”，快照记录“现在是什么样”。
- **与 TaskOrder v1.0**
    - `task_id` 联通任务工单：
        - 可以按 Task 重建执行轨迹（所有 AssetEvent 按时间排序）；
        - 用于 QA/调试：“为什么这次 E2E 执行失败？”
- **与 LedgerEntry v1.0**
    - 日志与钱可以通过 `task_id` / `asset_id` 关联：
        - 例如：某事件导致了 BAN → BAN 事件 + 对应成本（LedgerEntry）结合看；
        - BAN 事件可触发 `TASK_BURN` / `REFUND` 等账目。
- **与 AssetGraph (未来)**
    - 通过 AssetGraph 知道一个 PRODUCT 背后用了哪些 RAW_NET / RAW_FUND / INFRA；
    - 再通过 AssetEvent 可以看到：
        - 哪个环节最容易出错；
        - 哪个原材料最容易引发 BAN。

---

至此：

- S-01：`AssetSnapshot v1.0` —— 世界状态
- S-02：`TaskOrder v1.0` —— 世界动词
- S-03：`LedgerEntry v1.0` —— 世界的钱
- S-04：`AssetEvent v1.0` —— 世界的历史与真相
