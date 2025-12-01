## 📖 二、《AssetGraph v1.0》说明文档

### 1. 版本信息

- **Schema 名称**：`AssetGraph`
- **版本号**：`v1.0`
- **发布编号**：`S-DOC-001-05`
- **状态**：`final`
- **联邦成员角色**：
    
    CREEP Schema Federation – S-05：**世界的“地图层”**
    

> 一句话定位：
> 
> 
> **AssetGraph = CREEP 资产之间的有向关系图（Directed Graph）。**
> 
> 用于回答：
> 
> - “这个账号属于哪个身份？”
> - “这个 Product 是由哪些原材料组装而成？”
> - “这台服务器的算力被分摊给了哪些成品？”

---

### 2. 模型总览

`AssetGraph v1.0` 定义的是 **“边 (Edge)” 的结构**：

> 每一条 AssetGraph 记录 = 图中的一条有向边：
> 
> 
> `from_asset_id  --(edge_type, role, quantity, binding...)-->  to_asset_id`
> 

节点（Node）本身由 `AssetSnapshot` 提供：

- `AssetSnapshot` = 点；
- `AssetGraph` = 点和点之间的有向边。

**关键设计点：**

1. **有向边 (Directed Edge)**
    - 边总是从 `from_asset_id` 指向 `to_asset_id`。
    - 方向语义统一为：
        - “**左边拥有/依赖/由右边构成**”。
2. **边携带属性 (Edge Properties)**
    - `role`, `quantity`, `unit`, `binding_type`, `binding_strength`, `valid_from`, `valid_until` …
    - 可以表达：
        - 身份-账号的绑定强度；
        - Product-BOM 中的数量关系。
3. **支持 BOM（物料清单）**
    - `quantity` + `unit` 支持：
        - “由 1 个 IP + 1 个 VCC + 0.1 台 SERVER 组成”的表述。
4. **IDENTITY 作为根节点**
    - `sku_category = IDENTITY` 的 Asset 被视为 Persona 子图的 Root；
    - 从 IDENTITY 出发的所有出边构成“数字身份森林”的一颗子树。

---

### 3. 字段说明

### 3.1 边与租户身份

- `edge_id: uuid`（必填）
    - 边的唯一 ID。
    - 修改 / 替换某条边时，应创建新 edge_id，而不是 in-place 覆盖。
- `tenant_id: string`（必填）
    - 该边所属租户 ID。
    - 与其他 Schema 的 `tenant_id` 统一，用于多租户隔离。
- `project_id: string`（可选）
    - 主业务归属项目 / 成本中心。
- `env: string`（必填）
    - 环境：`prod` / `staging` / `dev` 等。
    - 用于隔离测试环境图与生产环境图。

---

### 3.2 有向边两端：from / to

- `from_asset_id: uuid`（必填）
    - 有向边的起点。
    - 语义统一为：**“拥有/组合/依赖方”**。
- `to_asset_id: uuid`（必填）
    - 有向边的终点。
    - 语义为：**“被拥有/被组合/被依赖方”**。

> 典型约定：
> 
- Persona 图：
    - `IDENTITY → ACCOUNT`
    - `IDENTITY → COOKIE_STORE`
    - `IDENTITY → DEVICE_FINGERPRINT`
- BOM 图：
    - `PRODUCT → RAW_NET` (IP)
    - `PRODUCT → RAW_FUND` (VCC)
    - `PRODUCT → INFRA` (SERVER)

---

### 3.3 边类型与角色 (edge_type / role / graph_scope)

- `edge_type: string`（必填）
    - 描述边的逻辑类型。
    - 推荐枚举（由上层约定，Schema 不硬编码）：
        - `COMPOSED_OF`：组成关系（BOM：成品 → 原材料）
        - `OWNS`：拥有关系（IDENTITY → ACCOUNT）
        - `DERIVED_FROM`：派生关系（AGED_ACCOUNT → RAW_ACCOUNT）
        - `BINDS`：绑定关系（IDENTITY → IP / DEVICE）
- `role: string`（可选）
    - 对边上的目标资产做进一步角色标注，推荐值如：
        - `MATERIAL`：原材料
        - `FUND`：资金 / VCC
        - `INFRA`：基础设施
        - `ACCOUNT`：账号
        - `IDENTITY`：身份组件
        - `SESSION`：会话 / 临时 token
    - 示例：
        - `edge_type = "COMPOSED_OF", role = "MATERIAL"`
        - `edge_type = "OWNS", role = "ACCOUNT"`
- `graph_scope: string`（可选）
    - 用于对不同“图层”做逻辑分区，比如：
        - `PERSONA`：身份/账号/指纹图
        - `BOM`：物料清单图
        - `DEPENDENCY`：资源依赖图
    - 同一个 `from_asset_id` 在不同 `graph_scope` 下可以有不同的边集。

---

### 3.4 BOM 支持：数量与单位 (quantity / unit / order_index)

- `quantity: number`（可选，≥ 0）
    - 描述从 `from_asset` 视角看，`to_asset` 在该关系中所占的数量：
        - 对 BOM：
            - 例如：“一个 PRODUCT 由 1 个 IP + 1 个 VCC + 0.1 个 SERVER 构成”：
                - P → IP, `quantity = 1`
                - P → VCC, `quantity = 1`
                - P → SERVER, `quantity = 0.1`
        - 对 Persona：
            - 通常可省略或设为 1。
- `unit: string`（可选）
    - `quantity` 的单位，示例：
        - `UNIT`：按件
        - `SHARE`：份额（0.1 台服务器可以用 `SHARE` + `quantity=0.1`）
        - `VCPU_HOUR`：按 vCPU 小时
    - 由租户自行约定枚举集合。
- `order_index: integer`（可选，≥ 0）
    - 用于表达同一 `from_asset` 的多个 `to_asset` 之间的顺序（如多张票、多层指纹组件）。
    - 不参与逻辑推理，只用于：
        - UI 展示排序；
        - 某些需要顺序的策略。

---

### 3.5 绑定语义：binding_type / binding_strength / valid_from / valid_until

> 回应你提出的：
> 
> 
> “IDENTITY 拥有 ACCOUNT，这条边上可能有 binding_strength (绑定强度) 或 role (角色)。”
> 
- `binding_type: "HARD" | "SOFT" | "EPHEMERAL"`（可选）
    - 描述绑定的**生命周期语义**：
        - `HARD`：长期/强绑定
            - 例：Identity 和主账号之间的关系。
        - `SOFT`：可调整/可迁移的绑定
            - 例：某 IP 优先分配给某 Identity，但可以迁移。
        - `EPHEMERAL`：短期/一次性绑定
            - 例：某 IP 在某次任务中暂时绑定到 Identity 上。
- `binding_strength: number`（可选，0–1）
    - 用于表达绑定强度的数值化程度：
        - `1.0`：完全绑定（主账号、主设备）；
        - `0.5`：部分偏好 / 中度关联；
        - `0.0`：理论上不应出现（意味着不绑定，应删除该边）。
- `valid_from: date-time`（可选）
    - 该关系生效时间。
    - 对 `EPHEMERAL` 绑定，通常为 Lease 开始时间。
- `valid_until: date-time`（可选）
    - 该关系失效时间。
    - 对 `EPHEMERAL` 绑定，通常为 Lease 结束时间 / binding 解除时间。
    - 对长期 `HARD` 绑定，可为空。

> 通过 binding_type + binding_strength + valid_from/valid_until，
> 
> 
> 可以精细描述 Identity-Account-Device-IP 之间的绑定历史和当前状态。
> 

---

### 3.6 标签与扩展

- `tags: string[]`（可选）
    - 用于挂载自由标签，例如：
        - `["persona", "ts_tour", "aged_account"]`
        - `["bom", "premium_material"]`
- `meta: object`（可选）
    - 承载租户自定义的边属性，如：
        - `{"strategy": "preferred_ip", "risk_score": 0.2}`
        - `{"billed": true, "material_group": "gold"}`
    - 建议在租户内部规范 meta 的 key/typing；
    - 真正变成“核心属性”的字段，未来可以升级为顶层字段。

---

### 3.7 时间与版本

- `created_at: date-time`（必填）
    - 边记录创建时间。
- `updated_at: date-time`（必填）
    - 最近一次修改该边记录的时间。
- `edge_version: integer`（必填，≥ 1）
    - 用于乐观锁 / 版本控制：
        - 更新边属性时，要求 `edge_version` + 1；
        - 支持在并发修改时做 CAS 检查。

> 与 AssetEvent 不同，AssetGraph 不强制 append-only：
> 
> - 它代表的是“当前地图”的结构；
> - 历史变更由 `AssetEvent` 记录；
> - AssetGraph 可以视为“最新的拓扑视图”，而非事件历史仓库。

---

### 4. 根节点与 IDENTITY 语义

> 回应：“明确 IDENTITY 作为子图根节点的特殊地位”。
> 

在 CREEP 的 Persona 图 (`graph_scope = "PERSONA"`) 中：

- 任意 `sku_category = "IDENTITY"` 的 AssetSnapshot 都是**候选根节点**；
- 从 IDENTITY 出发的所有出边构成一棵 Persona 子树，例如：
    - `IDENTITY --(OWNS / ACCOUNT)--> ACCOUNT`
    - `IDENTITY --(OWNS / COOKIE_STORE)--> COOKIE_STORE`
    - `IDENTITY --(BINDS / DEVICE)--> DEVICE_FINGERPRINT`
    - `IDENTITY --(BINDS / NET)--> PREFERRED_IP`

这种结构允许：

- 快速回答：“这个账号属于哪个 Persona？” → 逆向查找 `... → ACCOUNT` 的入边；
- 快速导出一个 Persona 的全量资源：“从 Identity Root 做一次 DFS/BFS”。

**对于 BOM 图 (`graph_scope = "BOM"`)：**

- `PRODUCT` 节点通常扮演 Root：
    - Product → 原材料 / 资金 / INFRA / LOGIC；
- 可以将 `IDENTITY` 和 `BOM` 图合并，通过：
    - PRODUCT → ACCOUNT → IDENTITY，
        
        构造出“这个 Product 绑定在哪个 Persona”这样的问题。
        

---

### 5. 使用场景示例

### 场景 1：Persona 图 – 身份与账号、指纹、IP 的关系

**需求：**

- Persona P1 拥有一个主账号 A1；
- Persona P1 绑定一个浏览器指纹 F1；
- Persona P1 有一个偏好 IP 节点 IP1（软绑定）。

示例边：

```json
{
  "edge_id": "uuid-e1",
  "tenant_id": "tenant_a",
  "project_id": "project_persona",
  "env": "prod",

  "from_asset_id": "asset-identity-P1",
  "to_asset_id": "asset-account-A1",
  "edge_type": "OWNS",
  "role": "ACCOUNT",
  "graph_scope": "PERSONA",

  "quantity": 1,
  "unit": "UNIT",
  "binding_type": "HARD",
  "binding_strength": 1.0,

  "valid_from": "2025-06-22T00:00:00Z",
  "valid_until": null,
  "order_index": 0,

  "tags": ["primary_account"],
  "meta": {
    "login_email": "foo@example.com"
  },

  "created_at": "2025-06-22T01:00:00Z",
  "updated_at": "2025-06-22T01:00:00Z",
  "edge_version": 1
}

```

```json
{
  "edge_id": "uuid-e2",
  "tenant_id": "tenant_a",
  "project_id": "project_persona",
  "env": "prod",

  "from_asset_id": "asset-identity-P1",
  "to_asset_id": "asset-fingerprint-F1",
  "edge_type": "OWNS",
  "role": "IDENTITY",
  "graph_scope": "PERSONA",

  "quantity": 1,
  "unit": "UNIT",
  "binding_type": "HARD",
  "binding_strength": 0.9,

  "valid_from": "2025-06-22T01:10:00Z",
  "valid_until": null,

  "tags": ["primary_fingerprint"],
  "meta": {},

  "created_at": "2025-06-22T01:10:00Z",
  "updated_at": "2025-06-22T01:10:00Z",
  "edge_version": 1
}

```

```json
{
  "edge_id": "uuid-e3",
  "tenant_id": "tenant_a",
  "project_id": "project_persona",
  "env": "prod",

  "from_asset_id": "asset-identity-P1",
  "to_asset_id": "asset-ip-IP1",
  "edge_type": "BINDS",
  "role": "MATERIAL",
  "graph_scope": "PERSONA",

  "quantity": 1,
  "unit": "UNIT",
  "binding_type": "SOFT",
  "binding_strength": 0.4,

  "valid_from": "2025-06-22T02:00:00Z",
  "valid_until": null,

  "tags": ["preferred_ip"],
  "meta": {
    "geo": "GB"
  },

  "created_at": "2025-06-22T02:00:00Z",
  "updated_at": "2025-06-22T02:00:00Z",
  "edge_version": 1
}

```

这三条边构成一颗以 `asset-identity-P1` 为根的 Persona 子树。

---

### 场景 2：BOM 图 – Product 由 IP + VCC + 0.1 SERVER 组成

**需求：**

一个 PRODUCT（演唱会门票激活服务）由以下组成：

- 1 个特定 IP（Residential UK）
- 1 张一次性 VCC（UK VISA）
- 0.1 台高性能服务器 SERVER1（摊销）

示例边：

```json
{
  "edge_id": "uuid-b1",
  "tenant_id": "tenant_a",
  "project_id": "project_ticket",
  "env": "prod",

  "from_asset_id": "asset-product-PROD1",
  "to_asset_id": "asset-ip-IP_UK1",
  "edge_type": "COMPOSED_OF",
  "role": "MATERIAL",
  "graph_scope": "BOM",

  "quantity": 1,
  "unit": "UNIT",

  "binding_type": "EPHEMERAL",
  "binding_strength": 1.0,

  "valid_from": "2025-06-22T10:00:00Z",
  "valid_until": "2025-06-22T10:05:00Z",

  "tags": ["ip_component"],
  "meta": {
    "geo": "GB"
  },

  "created_at": "2025-06-22T10:00:00Z",
  "updated_at": "2025-06-22T10:00:00Z",
  "edge_version": 1
}

```

```json
{
  "edge_id": "uuid-b2",
  "tenant_id": "tenant_a",
  "project_id": "project_ticket",
  "env": "prod",

  "from_asset_id": "asset-product-PROD1",
  "to_asset_id": "asset-vcc-VCC_UK1",
  "edge_type": "COMPOSED_OF",
  "role": "FUND",
  "graph_scope": "BOM",

  "quantity": 1,
  "unit": "UNIT",

  "binding_type": "EPHEMERAL",
  "binding_strength": 1.0,

  "valid_from": "2025-06-22T10:00:00Z",
  "valid_until": "2025-06-22T10:05:00Z",

  "tags": ["vcc_component"],
  "meta": {
    "issuer_country": "UK"
  },

  "created_at": "2025-06-22T10:00:01Z",
  "updated_at": "2025-06-22T10:00:01Z",
  "edge_version": 1
}

```

```json
{
  "edge_id": "uuid-b3",
  "tenant_id": "tenant_a",
  "project_id": "project_ticket",
  "env": "prod",

  "from_asset_id": "asset-product-PROD1",
  "to_asset_id": "asset-server-SRV1",
  "edge_type": "COMPOSED_OF",
  "role": "INFRA",
  "graph_scope": "BOM",

  "quantity": 0.1,
  "unit": "SHARE",

  "binding_type": "EPHEMERAL",
  "binding_strength": 1.0,

  "valid_from": "2025-06-22T10:00:00Z",
  "valid_until": "2025-06-22T10:05:00Z",

  "tags": ["infra_share"],
  "meta": {
    "runtime_ms": 300000
  },

  "created_at": "2025-06-22T10:00:02Z",
  "updated_at": "2025-06-22T10:00:02Z",
  "edge_version": 1
}

```

配合 `LedgerEntry` 中对 SERVER1 的摊销，可以精确算出：

- 单个 PRODUCT 的真实成本；
- IP / VCC / INFRA 各自贡献了多少成本。

---

### 场景 3：AGED_ACCOUNT 由 RAW_ACCOUNT 派生

**需求：**

- 通过 MES 等系统，把一个 RAW_ACCOUNT 养成一个 Aged Account；
- 需要在图中记录“派生关系”，以便溯源和风险控制。

```json
{
  "edge_id": "uuid-c1",
  "tenant_id": "tenant_a",
  "project_id": "project_account",
  "env": "prod",

  "from_asset_id": "asset-aged-account-A1",
  "to_asset_id": "asset-raw-account-R1",
  "edge_type": "DERIVED_FROM",
  "role": "ACCOUNT",
  "graph_scope": "DEPENDENCY",

  "quantity": 1,
  "unit": "UNIT",

  "binding_type": "HARD",
  "binding_strength": 1.0,

  "valid_from": "2025-06-22T00:00:00Z",
  "valid_until": null,

  "tags": ["aged_account"],
  "meta": {
    "days_aged": 90
  },

  "created_at": "2025-06-22T00:00:00Z",
  "updated_at": "2025-06-22T00:00:00Z",
  "edge_version": 1
}

```

---

### 6. 与其他 Schema 的协作关系（联邦闭环）

- **与 AssetSnapshot v1.0**
    - AssetSnapshot：节点属性（“现在是什么样的东西”）；
    - AssetGraph：节点之间的拓扑关系（“谁属于谁 / 谁由谁组成”）。
- **与 TaskOrder v1.0**
    - TaskOrder 不直接引用 AssetGraph，但：
        - Task 执行中可以创建/更新某些边（比如把账号挂到一个 Identity 下）；
        - 任务完成后，可用 AssetGraph 判断：
            - 这个任务对哪一片 Persona 子树产生了影响。
- **与 LedgerEntry v1.0**
    - BOM 图 + LedgerEntry = 完整成本分摊：
        - 从 Product 回溯到原材料；
        - 按边上的 `quantity/unit/role` 和 LedgerEntry 汇总成本。
- **与 AssetEvent v1.0**
    - AssetEvent 记录“什么时候产生/更新/删除了某条边”（通常以 event_type 表示，如 `EDGE_CREATED`, `EDGE_DELETED`）；
    - AssetGraph 则始终给出最新的“地图快照”；
    - 两者配合可以：
        - 回放图的历史演化；
        - 查出“是什么事件导致这个账号被迁移到另一个 Identity 下”。

---

至此，CREEP Schema Federation 五大基石：

- **S-01**：`AssetSnapshot v1.0` – 状态
- **S-02**：`TaskOrder v1.0` – 动作
- **S-03**：`LedgerEntry v1.0` – 价值
- **S-04**：`AssetEvent v1.0` – 历史与真相
- **S-05**：`AssetGraph v1.0` – 地图与结构

已经全部通过宪法化定义。
