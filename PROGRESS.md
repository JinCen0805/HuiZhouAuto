# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP5 已完成** → 下一步 WP6（采购需求编制 + 审计）
- 分支：`main`

## 已完成
- [x] WP0 环境与骨架（env_check 全绿）
- [x] WP1 会话/浏览器核心 + 冒烟（26 passed）
- [x] WP2 S01/S04/S05 迁移（P0 全链 18s，连续 2 次）
- [x] WP3 审批通用 + 调研信息/公告（P1 33s）
- [x] WP4 供应商响应 + 资格性审查（state=4）
- [x] **WP5 专家抽取 + 线下论证（state=6 → 申请单 status=15）**
  - `api/argument_api.py`、`api/professor_mock.py`、`pages/survey_argument.py`
  - `flows/s11_extract.py`（线下+手动抽取 + mock 电话确认 + 本地 MQ 桥接）
  - `flows/s13_argument.py`（指定组长 + 上传论证报告 + 提交）
  - `scripts/local_draw_bridge.py`（本地专用：outbox → RabbitMQ 桥接 + 结果队列绑定）
  - `tests/flows/test_p1_argument.py`（页面只读默认跑；链式用例需 `HP_ARGUMENT_MQ_BRIDGE=1`）

## 本地环境变更（WP5 方案 A，用户已授权）
1. `db/infra/local-stack/local-stack.ps1`（**未提交，仅本地工作区**）：
   - professor Vhost `/local-professor` → `/local-hospital-procurement`；
   - `draw.integration.listener.enabled=true`；
   - professor `spring-rabbitmq.xml` 不再强制 `auto-startup=false`。
2. 已执行 `local-stack.ps1 restart-service -Service professor`（健康检查 UP）。
3. HP 本地 profile 关闭了 Spring 定时任务 → `scripts/local_draw_bridge.py`：
   - 读取 `draw_integration_outbox` 中 status=0 消息，经 RabbitMQ 管理 API 投递；
   - 自动补 `hospital.draw.result.queue` 的 `draw.event.#` 绑定（否则 professor 回调 NO_ROUTE 回滚）。
4. 该机制仅用于本地测试；测试环境仍由真实 relay/MQ 完成。

## 证据（2026-11-18）
- `HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p1_argument.py::test_argument_extract_and_offline -v -s`
  → **1 passed in 272.14s**
  - 申请单 HW-YWB-CG20260195；线下论证；抽取 3 名专家并 mock 确认；
  - 指定组长 → 上传论证报告 → **state=6**；申请单 **status=15（待编制采购需求）**
- 全量（含论证链）：`HP_ARGUMENT_MQ_BRIDGE=1 pytest -q` → **37 passed, 1 skipped in 464.29s**
- 全量（默认，不含论证链）：36 passed, 2 skipped
- `env_check.py` → **PASS 39 / WARN 1 / FAIL 0**（新增“抽取建项 MQ 桥接”检查 PASS）

## 本次沉淀的坑与解法
- HP 本地定时任务被移除 → outbox relay 不执行；用本地桥接脚本投递，无需改 HP 配置。
- professor 回调发布 `EXTRACTION_PROGRESS` 时若 HP 结果队列无绑定会 `NO_ROUTE` 回滚 →
  通过 RabbitMQ 管理 API 补 `draw.event.#` 绑定。
- mock callid 的键是 `drawProjectExpertId`，不是 `expertId`；需用 mock 项目详情做映射；
  回调路径参数必须是 `drawProjectExpertId`。
- 抽取完成后 HP 需从 Dubbo 同步专家状态：轮询时调用 `listManualCandidates` 触发同步。
- 线下论证结果上传要求“论证开始时间已到”：S11 把 gatherTime 设为 now+2min；
  S13 等待到点后再上传（本地测试会多等约 2 分钟）。
- 用例间/阶段间要清理 layer 弹窗与遮罩（`close_all_layers`），否则会拦截后续点击。

## 阻塞 / 已知项
- OnlyOffice(18099) 仍未启动（WARN）；WP6 需求书/审计报告在线编辑可能需要（或走模板+force-save 绕行）。
- `db/infra/local-stack/local-stack.ps1` 的本地修改未提交（按 db 仓库规则需用户确认后提交）。

## 下一步（WP6）
1. `pages/requirement.py` + `flows/s15_requirement.py`：
   选模板创建采购需求书 → 保存/提交初稿审计（BT14）；
2. `pages/audit_management.py` + `flows/s16_audit.py`：
   HP 推送审计 → 纪检平台受理/报告 → 主任通过；
3. 验收：审计通过，申请单进入 19/20（待需求二次确认）。
4. 若 OnlyOffice 不可用，优先走 `createByTemplate` + `force-save` + 提交审核的 API 路径。

## 证据索引
- 论证链：`HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p1_argument.py -v -s`
- 全量：`HP_ARGUMENT_MQ_BRIDGE=1 pytest -q`（37 passed, 1 skipped）
