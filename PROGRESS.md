# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。
> **当前状态：WP0~WP9 全部完成，采购前置全流程（申请→采购中）已打通并交付。**

## 总览

| 工作包 | 内容 | 状态 |
|---|---|---|
| WP0 | 环境/骨架/自检 | ✅ 完成 |
| WP1 | 会话/浏览器核心 + 冒烟 | ✅ 完成 |
| WP2 | S01/S04/S05 | ✅ 完成 |
| WP3 | 审批通用 + 调研信息/公告 | ✅ 完成 |
| WP4 | 供应商响应 + 资格性审查（state=4） | ✅ 完成 |
| WP5 | 专家抽取 + 线下论证（state=6 / status=15） | ✅ 完成 |
| WP6 | 需求编制 + 审计（status=20） | ✅ 完成 |
| WP7 | 终稿确认 + 三方审查 + 方式分配 + 执行申请（status=9） | ✅ 完成 |
| WP8 | 全链编排/断点续跑/重试/报告 | ✅ 完成 |
| WP9 | 稳定性/清理/交付文档 | ✅ 完成 |

## 最终验收（2026-11-19）

- **单入口全链**：`python scripts/run_full_chain.py` → **success / status=9 采购中 / 273.5s**
- **稳定性连续 3 次全链**：4:51、4:50、4:56，**3/3 成功**
- **断点续跑**：`--resume` 从 status=20 自动续跑 S17→S20 成功
- **默认回归**：`pytest -q` → **41 passed, 4 skipped（237.09s）**
- **编排单元测试**：5 passed
- **环境自检**：`env_check.py` → **PASS 40 / WARN 0 / FAIL 0**
- **测试数据清理**：`cleanup_test_data.py --apply` 软删除 431 条 `UI自动化-*` 数据，
  清理后预览为 0

## 交付物

- 代码：`automation_py/`（api/core/flows/pages/scripts/tests）
- 文档：
  - `docs/快速上手.md`
  - `docs/环境修复手册.md`
  - `docs/已知限制.md`
  - `docs/交付验收报告.md`
- 分析：`analysis/`（可行性评估、开发计划、技术方案、手工步骤拆解）
- 报告样例：`automation_py/reports/<runId>/report.html`（不入库）

## 关键实现

- 15 个角色会话、多平台（采购交易系统 / 纪检监察平台）；
- 页面操作以 `changeView` 打开模块、iframe 定位，弹窗/遮罩统一清理；
- 混合策略：关键业务节点 API 直调 + 页面校验（需求书创建/保存、审计、审查、方式、执行审批）；
- 审批通用办理（BT14/BT19/BT6/BT13），支持 formProperties/vars 扩展；
- 专家抽取：线下 + 手动 + mock 电话确认 + 本地 MQ 桥接；
- 审计报告：本地用 JWT 回调协议标记已保存（生产由 OnlyOffice 触发）；
- 全链编排：状态→步骤映射续跑、失败重试、JSON/HTML 报告。

## 本地环境适配（不属业务代码）

1. `local-stack.ps1`（本机 untracked）：
   - professor 共用 HP vhost、开启 draw listener、恢复 rabbit auto-startup；
   - business-approval 回调：HP `17825`、PE `8088/ProcurementExecution`。
2. `discipline application-local.yml`：文件下载端口 7707 → 17707。
3. OnlyOffice 容器启动（18099）。
4. 本地脚本：`scripts/local_draw_bridge.py`（outbox→MQ + 结果绑定）、
   `scripts/local_env.py`（纪检账号 Redis DB9→DB7）。
5. `.env.local` 本地测试密码（gitignored，未进仓库）。

## 常见问题（详见 docs/环境修复手册.md）

- 登录“服务异常” → ZK provider 为空 → `restart-service -Service baseserver`；
- 抽取卡住 → 检查 professor listener / MQ 桥接；
- 审批后状态不动 → 检查回调端口（17825 / 8088）；
- 纪检接口 401 → 同步 Redis DB9→DB7 key；
- 审计报告 7707 连接拒绝 → 确认下载端口 17707；
- 长时间空闲后先跑 `env_check.py`。

## Git

- 分支：`main`
- 提交：WP0~WP9 每包独立提交 + 本地环境/踩坑记录；仓库不含密码。

## 本地增强（产品需求变更后，线上暂缓）

- 环境切换：`HP_ENV=local/online` + `HP_BASE_URL`；账号分组、cookie/redirect 适配、线上只读冒烟`online_smoke.py`。
- 供应商账号修正：线上/本地统一使用 `ybjcsgys1~3`。
- S16 线上编辑器保存路径本地验证：`HP_AUDIT_SAVE_MODE=editor` 下 P3 全链通过（302.90s）。
- S15/S16 曾做过 OnlyOffice 正文填充，已按人工操作口径删除。模板生成的正文保持原样。

## 采购方式可选择（本地增强）

- 支持自主采购方式：1 委托采购 / 2 比选采购（默认）/ 3 竞争谈判采购 /
  4 唯一来源谈判采购（需唯一性论证会议纪要附件）/ 7 议（比）价采购（需议比价方式）。
- 配置方式：环境变量 `HP_PURCHASE_METHOD`、`HP_IN_HOSPITAL_PRICE_TYPE`、
  `HP_UNIQUENESS_ATTACHMENT`、`HP_BID_EVALUATION_FORM`；或单入口参数
  `--purchase-method/--in-hospital-price-type/--uniqueness-attachment/--bid-evaluation-form`。
- 已本地全链验证：2（历史）、3（292.34s）、7/院内议价（292.47s）、4（293.41s），均 status=9；
  1 委托采购（293.05s）均 status=9。
- 新增单测 `tests/unit/test_procurement_method.py`。
- 本地计划耗尽时用 `scripts/seed_local_plan.py` 克隆种子计划；默认回归 50 passed / 4 skipped。

## 本地取证（2026-11-20）

- OnlyOffice 正文不填：人工走前置流程时不在编辑器里改正文，自动化已删除对应填充代码。
  需求书和审计报告保持模板生成结果；审计报告仍按原流程标记已保存。
- 默认回归基线在删除前为 51 passed / 4 skipped。提交：`fa18499`。

## 2026-11-24 本地项目更新适配

本地项目更新（hospital-procurement `0a6ecd27`、GovernmentProcurement `38c35b4`、
professor `07d9aba`、procurement-execution `fc7786a`、ebidding-business-approval `cca66f5` 等）
后，前置相关变更与适配结果：

- **专家抽取改按科室**（`16536d2b` 等）：
  - S11 改为优先调用 `listDepartments`，用 `departmentNodeId` 规划/勾选专家；
    科室目录不可用时回落原专业模式（兼容未升级环境）。
- **审计初稿增加承办部门主任复核**（`9d506754` 等）：
  - 新链路：承办干事初始化/保存审计报告初稿 → 提交主任复核 → 承办部门主任复核并选审计员推送
    → 审计员审理 → 审计部主任通过；
  - S16 改用 HP `/hospitalPurchaseAudit/{id}/report/*`、`draft/*` 接口，本地保存仍走
    OnlyOffice JWT 回调（HP 回调地址），推送时携带 `submissionId`。
- **采购执行审批角色修复**（BT13 紧急 1~3 万走主管副院长）：常规路径不受影响，S20 5 节点照常通过。
- **审计报告初始化/审计分页/审查汇总明细修复**：S15/S16/S18 回归通过。
- **合同、支付凭证、履约、质疑投诉、站内信**：属采购中之后流程，不影响前置。

5 种采购方式本地全链回归（均 `status=9 采购中`）：

| 方式 | 场景 | 结果 | 报告目录 |
|---|---|---|---|
| 1 | 委托采购 | success | `reports/UI自动化-20261124-M1` |
| 2 | 比选采购 | success | `reports/UI自动化-20261124-M2R2` |
| 3 | 竞争谈判采购 | success | `reports/UI自动化-20261124-M3` |
| 4 | 唯一来源谈判（含会议纪要附件） | success | `reports/UI自动化-20261124-M4` |
| 7 | 院内议价 | success | `reports/UI自动化-20261124-M7` |
