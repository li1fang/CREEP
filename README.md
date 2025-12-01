# CREEP

\<div align="center"\>

### Cyber Resource Enterprise Erp Platform

**网络资源企业级 ERP 平台**

[](https://www.google.com/search?q=https://github.com/creep-protocol/creep)
[](https://www.google.com/search?q=LICENSE)
[](https://www.google.com/search?q=docs/architecture)
[](https://www.google.com/search?q=schemas)

**全球化数字供应链编排 · 资产全生命周期管理 · FinOps 财务闭环**

[文档](https://www.google.com/search?q=docs/) · [安装](https://www.google.com/search?q=docs/guides/getting-started.md) · [架构](https://www.google.com/search?q=docs/architecture/system-overview.md) · [贡献](https://www.google.com/search?q=CONTRIBUTING.md)

\</div\>

-----

## 📖 简介 (Introduction)

**CREEP** 是一个面向现代数字经济的 **通用资产操作系统 (Asset OS)**。

在自动化测试、合成监控、数据采集及高频交易等场景中，企业面临着海量异构资源（全球 IP、虚拟卡资金、算力节点、数字身份）的管理难题。传统的 ERP 无法处理这些存活周期极短、高频流动且属性各异的“非标资产”。

CREEP 引入了 **供应链管理 (SCM)** 与 **制造执行系统 (MES)** 的核心逻辑，基于 **WebAssembly (Wasm)** 的原子化执行能力，提供了一套标准化的协议，实现了从**寻源、采购、质检、生产、调度、归因到销售**的全链路自动化。

它不是一个简单的脚本运行器，它是一座**数字工厂**：将碎片化的原材料转化为高价值的数字成品。

-----

## 🏗 核心原理 (Core Principles)

CREEP 的架构建立在 **“联邦 Schema (Federated Schema)”** 与 **“状态机驱动 (State Machine Driven)”** 之上。

### 1\. 联邦 Schema 体系 (S-DOC Standards)

系统不依赖单一的大表，而是通过五大核心 Schema 定义世界的真理：

| 编号 | 协议名称 | 角色定位 | 核心职责 |
| :--- | :--- | :--- | :--- |
| **S-01** | **AssetSnapshot** | **世界状态** | 资产当前的快照。只存现状，不存历史。支持独占与共享并发模型。 |
| **S-02** | **TaskOrder** | **驱动引擎** | 系统的“动词”。定义任务意图、优先级、超时及幂等性约束。 |
| **S-03** | **LedgerEntry** | **价值记录** | 金融级复式记账。记录每一笔资金流动（IN/OUT）与成本摊销。 |
| **S-04** | **AssetEvent** | **审计真相** | 不可变的事件日志。记录全链路因果关系 (Correlation/Causation)。 |
| **S-05** | **AssetGraph** | **拓扑地图** | 有向图结构。定义身份树 (Persona)、BOM (物料清单) 及资产依赖关系。 |

### 2\. 混合调度架构 (Hybrid Scheduling)

为了平衡数据一致性与高并发吞吐，CREEP 采用分层调度：

  * **冷存储 (PostgreSQL):** 作为 Single Source of Truth，负责持久化存储资产快照与财务账本。
  * **热分发 (Redis Dispenser):** Loader 服务将可用资产预加载至 Redis 队列，Wasm Worker 进行无锁原子获取 (LPOP)。
  * **原子执行 (Wasm Atom):** 业务逻辑默认编译为 Wasm，实现毫秒级冷启动与极高的资源密度。

-----

## ⚡️ 核心特性 (Features)

### 💎 万物皆资产 (Universal Asset Management)

通过通用的 JSONB 结构与元数据驱动，CREEP 统一管理五大类资产：

  * **RAW\_NET:** 网络耗材 (Residential IPs, Proxies)
  * **RAW\_FUND:** 资金耗材 (VCCs, Crypto Wallets)
  * **INFRA:** 基础设施 (VPS, Pods, Devices)
  * **LOGIC:** 逻辑资产 (Accounts, Cookies, Fingerprints)
  * **PRODUCT:** 数字成品 (Tokens, Tickets, Finished Accounts)

### 🏭 工业级供应链 (Industrial SCM)

  * **寻源与质检:** 自动对接供应商 API，入库前执行海关级质检 (Pre-flight Check)。
  * **熔断机制:** 基于 `Batch_ID` 和子网段的自动熔断策略，防止批量风控。
  * **生命周期管理:** 自动处理资产冷却 (Cooling)、复用 (Reuse) 与淘汰 (Retire)。

### 💰 FinOps 财务闭环

  * **精准归因:** 每一分钱的支出都能追溯到具体的 `Tenant` (租户)、`Project` (项目) 和 `Task` (任务)。
  * **成本摊销:** 支持将基础设施 (Infra) 的长期成本按使用时长摊销到单次任务中。
  * **自动对账:** 内置 `external_ref` 锚点，支持与云厂商账单及银行流水自动核对。

### 🌐 身份图谱 (Identity Graph)

  * 以 `IDENTITY` 为根节点，构建完整的数字人 (Persona) 树。
  * 支持 **BOM (物料清单)** 管理，精确定义成品的原材料构成（如：1 Product = 1 IP + 1 VCC + 0.01 Server）。

-----

## 🔄 工作流 (Workflows)

CREEP 将复杂的业务抽象为四条标准化的流水线：

```mermaid
graph TD
    subgraph Procurement [采购与入库]
        A[供应商 API] -->|购买| B(Pre-flight Check)
        B -->|合格| C[DB: AssetSnapshot (NEW)]
        C -->|账单| D[DB: LedgerEntry (OUT)]
    end

    subgraph Production [调度与生产]
        E[TaskOrder (PENDING)] -->|调度| F{Redis Dispenser}
        C -->|加载| F
        F -->|LPOP| G[Wasm Worker]
        G -->|执行业务| H[产出成品 / 验证结果]
    end

    subgraph Audit [审计与归因]
        H -->|记录| I[DB: AssetEvent]
        H -->|消耗| J[DB: LedgerEntry (Task Burn)]
        H -->|更新| K[DB: AssetSnapshot (READY/PRODUCT/COOLING/BANNED)]
    end

    subgraph Sales [销售与交付]
        L[外部 API 请求] -->|匹配| K
        K -->|交付| N[Client]
        N -->|收入| O[DB: LedgerEntry (IN)]
    end
```

-----

## 🚀 快速开始 (Getting Started)

### 1\. 安装控制面

使用 Helm 部署 CREEP 控制面到 Kubernetes 集群：

```bash
helm repo add creep https://charts.creep-protocol.org
helm install creep creep/control-plane \
  --set provider.hetzner.token=$HETZNER_TOKEN \
  --set srm.currency=USD
```

### 2\. 定义任务 (Submit a Task)

创建一个 `TaskOrder` 来执行一次端到端测试（或抢购任务）。注意 `resource_hints` 定义了所需的原材料。

```yaml
# task-example.yaml
apiVersion: creep.io/v1
kind: TaskOrder
metadata:
  tenant_id: "org_acme"
  env: "prod"
spec:
  task_type: "E2E_CHECKOUT_TEST"
  priority: 80
  timeout_ms: 60000
  idempotency_key: "req_unique_12345" # 金融级幂等保障
  
  # 定义所需资源 (BOM)
  resource_hints:
    - sku_category: "RAW_NET"
      sku_code: "ip.residential.uk.*"
      min_count: 1
    - sku_category: "RAW_FUND"
      sku_code: "vcc.visa.onetime"
      min_count: 1
      
  # 预算上限
  max_total_cost: 5.0
  currency: "USD"
```

### 3\. 查看资产状态

通过 CLI 或 SQL 查看资产的生命周期与财务状况：

```sql
-- 查看当前可用 IP 库存
SELECT id, ip_addr, health_score 
FROM creep_assets 
WHERE sku_category = 'RAW_NET' AND status = 'READY';

-- 查看某任务的真实成本（含损耗）
SELECT task_id, SUM(amount) as total_cost 
FROM creep_ledger_entries 
WHERE task_id = 'task_uuid_...' AND direction = 'OUT'
GROUP BY task_id;
```

-----

## 🛡 使用场景 (Use Cases)

1.  **全球自动化 QA**: 在真实的网络环境（住宅 IP）和支付环境（真实 VCC）中，对电商平台进行端到端的下单与支付测试。
2.  **合成监控 (Synthetic Monitoring)**: 利用全球碎片化算力节点，构建分布式探针网络，实时监控 CDN 延迟与服务可用性。
3.  **数字资产套利**: 自动化管理高价值数字商品（如门票、Token）的获取、库存管理与多渠道分销。
4.  **FinOps 预算控制**: 为内部研发团队提供沙箱环境，自动限制云资源和 SaaS 订阅的支出，防止预算溢出。

-----

## 🤝 贡献 (Contributing)

CREEP 遵循 **Schema-First** 的开发理念。任何功能的变更必须先提交 S-DOC 提案。

  * 请阅读 [CONTRIBUTING.md](https://www.google.com/search?q=CONTRIBUTING.md) 了解开发流程。
  * 查看 [schemas/](https://www.google.com/search?q=schemas/) 目录了解当前的法律条文。

-----

## ⚠️ 免责声明 (Disclaimer)

CREEP 是一个通用的基础设施管理工具。用户在使用本软件管理 IP、VCC 或其他资源时，必须严格遵守当地法律法规及服务提供商的使用条款。本项目维护者不对任何滥用行为负责。

-----

\<p align="center"\>
Made with 💜 by the \<b\>Natural Control Architect\</b\>.
\</p\>
