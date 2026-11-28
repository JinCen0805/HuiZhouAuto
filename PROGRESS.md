# 进度

> 代码/能力/环境发生变化时更新本文件，用于跨会话交接；单次验证不逐条记录。
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
  - `README.md`
  - `docs/环境切换.md`
  - `docs/采购方式选择.md`
  - `docs/环境修复手册.md`
  - `docs/已知限制.md`
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

## 2026-11-24 ~ 11-26 能力与适配变化

- S11 专家抽取改按科室：优先 `listDepartments`，用 `departmentNodeId` 规划/勾选，科室目录不可用时回落专业模式。
- S16 审计初稿新增承办部门主任复核链路（HP `/hospitalPurchaseAudit/{id}/report/*`、`draft/*`）；
  线上由 OnlyOffice 在线编辑器真实保存审计初稿。
- S06 幂等跳过、等待放宽到 60s、列表操作前清理残留遮罩；`survey_result.py` 多轮初审兜底、
  提交按钮定位到 detail frame。
- S01 组合发起支持自动翻页查找；保存超时后按项目名查 status=0 草稿兜底；新增同名申请防重。
- 新能力：`--plan-count`（组合发起 N 个预算计划 → N 个子包 → 审计逐计划填数量/单价）、
  `--plan-keyword`、采购方式参数（1 委托 / 2 比选 / 3 竞争谈判 / 4 唯一来源 / 7 议比价）；
  `scripts/probe_online_precheck.py`（跑前预检）、`scripts/verify_online_result.py`（跑后核对）。
- `env_check.py` 线上分支改“服务健康（匿名）+ 业务接口（登录态）”探测并复用登录会话。
- 已知口径：项目属性统一用“1 新增项目”（按项目类型映射为维修/维保会触发设备字段校验）；
  议比价（方式 7）执行项目审批后状态为 A7，其他方式为 A6。
- 线上验证覆盖：六种方式（1/2/3/4/7 议价/7 比价）均跑通"一单三计划三子包"到 status=9；
  跑数明细不入库，需要时按项目名在线上查询或用 `verify_online_result.py` 核对。

## 2026-11-28 被控系统同步后的适配与验证（本地）

- 被控系统两次 `sync-repos`：11-27 01:45、11-28 02:51（hospital-procurement 44 个提交、openresty 64、
  professor / business-approval / procurement-execution / discipline / notify / baseserver / db 若干）；
  本地库 Liquibase 记录已到 `20261127-004`（前置链路新增列全部存在），本地栈 11-28 17:14 于新代码重启。
- 代码适配（静态 diff 分析 + 本地实测得出，接口路径/字段/申请单状态枚举均未变）：
  - S05：分包列表行"确认"按钮被前端 `f0a6274f` 删除，改为编辑器底部 `#confirmBtn`
    （`PackageManagementPage.confirm_in_editor`，旧版前端同样有该按钮，线上兼容）。
  - S16：审计状态分发补入 9「主任复核通过，待推送」（HP `605a2d5e`，`workflow_mode=3`），
    主任复核后、推送前失败时重试/续跑不再报"未识别的审计状态"。
  - `env_check.py` 纪检鉴权 401 时本地先自动同步 Redis DB9→DB7 再判定；pytest smoke/flows 夹具
    登录后同步（`local_env.sync_discipline_keys_if_local`），栈重启后回归不再成批 401。
  - `run_full_chain.py` 输出重定向到文件时 UTF-8 编码兜底（`errors="replace"`），console.log 可完整落盘。
  - 未改：S11 `startExtract` 不传 `dialMode`（后端缺省 AUTO，且避免线上旧后端不识别该字段）。
- 验证：`env_check.py` PASS 39 / WARN 1（OnlyOffice 可选）/ FAIL 0；`pytest -q` 50 passed / 4 skipped；
  六种方式全链均 success / status=9（0 次重试）：
  1 委托 FW-YWB-CG20260136（332s）、2 比选 FW-YWB-CG20260135、3 竞争谈判 FW-YWB-CG20260137、
  4 唯一来源 HW-YWB-CG20260222、7 院内议价 FW-YWB-CG20260138（终态 A7）、7 院内比价 HW-YWB-CG20260223（终态 A7）。
  报告目录 `automation_py/reports/UI自动化-20261128-M{1,2,3,4,7Y,7B}-R01/`。
