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
- **S15/S16 内容填充（新增）**：
  - `core/office_files.py`（文件下载/上传 + OnlyOffice 回调更新文档）
  - `core/doc_content.py`（需求书按项目/子包/预算填充；审计报告按审计明细填充）
  - 开关 `HP_CONTENT_FILL=1`（仅本地/测试环境）
  - 本地 P2 验证：284.49s，status=20；抽查文档确认项目名/概况/预算表/审计明细已写入（需求书 documentVersion=2、审计报告 reportVersion=2）
  - 单测 +2（`tests/unit/test_doc_content.py`），默认回归 43 passed / 4 skipped

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

## 本地取证与内容填充（2026-11-20）

- 步骤截图：全链每步开始/结束/失败截图，写入 `reports/<runId>/screenshots/`，HTML 报告可点开。
- 需求书：按真实模板表头填写包号、名称、预算金额、项目属性；工程类模板替换 `{{项目名称}}`、`{{采购单位}}`。
- 审计报告：明细按真实预算计划填写。合计、落款、固定说明段落保持模板原文。
- 约定：人工走前置流程时不在 OnlyOffice 里改正文，自动化默认也不填。
  模板说明、示例技术参数、配置清单、预算表、审计明细都保持模板生成结果。
  `HP_CONTENT_FILL=1` 只是已有的可选开关，不再继续补。
- 验证：`HP_CONTENT_FILL=1` 的 P3 全链 PASSED，313.77s，`FW-YWB-CG20260149` status=9；需求书 documentVersion=2，审计报告 reportVersion=2。
- 默认回归：51 passed / 4 skipped。提交：`fa18499`、`4f5a95d`、`1987eda`、`51113a6`。
