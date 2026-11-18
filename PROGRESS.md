# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP7 已完成（采购前置全流程打通：status=9 采购中）** → 下一步 WP8（全链编排/断点续跑/报告）/ WP9（稳定性/清理/文档）
- 分支：`main`

## 已完成
- [x] WP0 环境与骨架（env_check 40 PASS）
- [x] WP1 会话/浏览器核心 + 冒烟
- [x] WP2 S01/S04/S05（P0）
- [x] WP3 审批通用 + 调研信息/公告
- [x] WP4 供应商响应 + 资格性审查（state=4）
- [x] WP5 专家抽取 + 线下论证（state=6 / status=15）
- [x] WP6 需求编制 + 审计（status=20）
- [x] **WP7 终稿确认 + 三方审查 + 方式分配 + 执行申请（status=9 采购中）**
  - `api/demand_review_api.py`：需求审查发起/任务/三阶段提交
  - `api/method_api.py`：采购方式分配提交
  - `api/execution_api.py`：执行草稿查询（selectOne by sourceApplyId）/经办人候选/提交审批
  - `flows/s17_confirm.py`、`s18_review.py`、`s19_method.py`、`s20_execution.py`
  - `tests/flows/test_p3_procurement.py`（P0→…→S20 自包含全链，默认跳过）

## 证据（2026-11-18）
- `HP_FULL_CHAIN=1 HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p3_procurement.py -v -s`
  → **1 passed in 291.19s**
  - S17：终稿确认 → BT14 主任通过 → status=19
  - S18：发起审查 → status=18 → 承办主任(一般性审查) → 财务部/审计部/采购部并行 → 纪检主任终审 → status=10
  - S19：方式分配提交（自主采购/比选采购）→ BT6 承办主任→采购办主任(评标方式=综合评分)→院办主任 → status=11
  - S20：执行草稿 → BT13 承办主任→分管院领导→采购办主任(指定经办人)→分管领导→分管院领导 → **status=9 采购中**
- 继续探针（从 status=18 数据续跑 S18→S20）→ **1 passed in 28.71s**
- 默认全量 `pytest -q` → **36 passed, 4 skipped in 227.88s**
- `env_check.py` → **PASS 40 / WARN 0 / FAIL 0**

## 本地环境变更（WP7，用户已授权继续）
1. `db/infra/local-stack/local-stack.ps1`（untracked 本地文件）business-approval 新增：
   - `execution.procurement.baseUrl = http://127.0.0.1:8088/ProcurementExecution`
   - 原配置为 `http://127.0.0.1:8083`（生产 PE 根上下文），本地导致 BT13 回调 404/连接拒绝。
   - 已重启 business-approval。
2. `.env.local`（gitignored）补充 `HP_PASSWORD_ZHOUJIU/CGBGS/CWBZR`（通用测试密码），
   WP7 需要财务部主任 `zhoujiu` 账号。
3. PE 回调现在可正常落库：`purchase_project.execution_approval_completed_at` 写入、purchaser 指定；
   原始 `state` 可能仍显示 A4，但列表按 completed_at 展示"审批通过"，**HP status=9 是最终验收口径**。

## 关键账号/角色（WP7 新增）
| 角色 | 账号 | 登录角色关键字 |
|---|---|---|
| 财务部主任 | `zhoujiu` | 财务部主任 |
| 采购办主任 | `bailu` | 采购执行部门主任 |
| 纪检主任（HP 审查终审） | `jjzr` | 纪检主任 |
| 院办主任 | `baiqi` | 医院办公室主任 |
| 承办部门分管院领导 | `libai` | 承办部门分管院领导 |
| 分管领导 | `fgld` | 分管领导 |
| 分管院领导 | `fgyld` | 分管院领导 |

## 本次沉淀的坑与解法
- S18 阶段1任务属于**承办部门主任**（不是承办干事），阶段2/3任务分别属于财务/审计/采购与纪检主任；
  页面查询必须带 `purchaseRequestId`，任务字段是 `taskId`，文档 id 从 `taskDetail.reviewDocumentId` 取。
- 一般性审查只需 5 个结果字段（ns/bm/prr/raa/pip）全为 1，`reviewResult=1`。
- BT6 采购办主任节点必须提交 `bidEvaluationForm`；通用办理接口用 `formProperties[bidEvaluationForm]=0`。
- BT13 采购办主任选经办人必须走 `vars[purchaseExecutionHandlerUserId]`（不是 formProperties）；
  经办人候选从 PE `purchaseContactList` 取。
- 执行草稿在 PE 列表页按当前用户口径可能查不到，直接 `selectOne?sourceApplyId=<申请uuid>` 最稳。
- S18 可幂等：status 18 已发起时跳过 initiate，便于断点续跑。

## 下一步
- WP8：全链编排（单个入口跑 P0→status=9）、断点续跑、失败重试、报告输出；
- WP9：稳定性（重复跑）、数据清理（UI自动化-* 前缀）、最终文档/交付说明。

## 证据索引
- P3 全链：`HP_FULL_CHAIN=1 HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p3_procurement.py -v -s`
- 默认全量：`python -m pytest -q`（36 passed, 4 skipped）
- 环境：`python scripts/env_check.py`（40 PASS）
