# 进度

> 代码/能力/环境发生变化时更新本文件，用于跨会话交接；单次验证不逐条记录。
> **当前状态：WP0~WP9 全部完成；S01~S20 除 S15/S16（OnlyOffice 编辑器）外均已改为 UI 操作（v2 分支）。**

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
- 混合策略：业务操作以页面操作为主（S01~S14、S18~S20），接口用于取数/定位任务/状态回读与断言；
  S15（需求书编制）、S16（审计）仍为接口直调，页面核心是 OnlyOffice 编辑器，详见 2026-11-29 节评估；
- 审批通用办理（BT14/BT19/BT6/BT13），支持 formProperties/vars 扩展；
- 专家抽取：默认全 UI（规划→勾选→拨号登记）+ 通知方式手工拨号登记；`HP_EXTRACT_MODE=api` 接口直调、
  `HP_DIAL_MODE=AUTO` 或旧后端自动回落 mock 电话确认；本地需 MQ 桥接；
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
  - S11 改为**全 UI**（默认 `HP_EXTRACT_MODE=ui`）：调研论证列表 → 规划页（线下论证 / 手动抽选 /
    通知方式）→ 勾选页 → 拨号登记页；通知方式默认**手工拨号**（`HP_DIAL_MODE=MANUAL`），在拨号登记页
    逐人点「参与」即 `extractStatus=2`，**不再依赖 mock 电话回调**；以 `getDetail.dialMode` 回读为准，
    旧后端仍为 AUTO 时自动回落 mock 路径；`HP_EXTRACT_MODE=api` 保留接口直调。S11 支持断点续跑
    （已抽齐/已规划/名单已够分别跳过，只登记未确认专家）。
  - S13：`--from S13` 续跑时 ctx 无 `survey_project_uuid` 会走页面「设为组长」，该按钮有二次确认弹窗，
    原兜底未处理导致“指定组长”假成功、论证结果提交被拦“请先指定专家组长”；现缺 uuid 时按项目名
    补齐走接口，页面兜底也补上确认。

## 2026-11-29 接口步骤 UI 化（v2 分支）

按“审批工作台 → S04 → S19/S18 → S20 → S15/S16 评估”的顺序把剩余接口直调步骤改为 UI 操作，
保留接口回退（`HP_STEP_MODE=api` 或单步 `HP_<STEP>_MODE=api`，见 `docs/环境切换.md` §9）。

- 新增页面对象：
  - `pages/approval_workbench.py`：审批工作台（三层 iframe：工作台 → 任务中心 → 待办列表；办理弹窗挂 top），
    BT14/BT6/BT13 通用办理；BT6 采购办节点选评标方式、BT13 采购办节点选执行经办人（候选异步加载）；
  - `pages/jjjc_project.py`：纪检监察平台监察项目列表 → 分配监督员弹窗（监督员 Layui 下拉、监督范围全流程）；
  - `pages/procurement_method.py`：采购方式分配（类别按政采标识锁定、方式/议比价方式下拉、唯一来源纪要
    走页面 WebUploader 上传、推送主任审批 + 二次确认）；
  - `pages/demand_review.py`：采购需求审查（干事发起 → 选类型弹窗勾一般性审查 → 审查页一键通过 → 保存 →
    确认通过；5 个角色复用）；
  - `pages/execution_apply.py`：采购执行申请（草稿行提交审批 → 确定）。
- 通用改进：`pages/common.py` 增加 `js_click`（原生 click 触发，绕开 Layui 固定列遮挡/滚动抖动的可点性超时）
  与 `confirm_or_msg`（同时等待确认框/3 秒提示，能报出前端校验文案）；`core/step_mode.py` 统一步骤开关；
  `flows/approval_ui.py` 统一审批节点办理（UI/接口切换）。
- 幂等与续跑：S19 读方式分配详情，`approvalStatus=1`（审批中）时跳过提交；BT6/BT13 用 ctx 记录已完成节点，
  重试/续跑时跳过；节点待办消失且后续节点已出现时视为已办（避免重试从第一个节点找起而失败）。
- 验证（本地，2026-11-29）：
  - 全链 `HW-YWB-CG20260230`（方式 2）一次通过：S04 UI + 9 个审批节点全 UI（BT14×1、BT6×3、BT13×5），status=9；
  - `HW-YWB-CG20260231`（方式 2）续跑：S19 分配方式 UI + S20 执行申请提交 UI + BT13 五节点 UI，status=9；
  - 方式 4 `HW-YWB-CG20260235`：页面纪要上传被“附件正在上传”拦下 → 加短等重试后推送成功，续跑至 status=9；
  - 方式 7 议价：BT13 固定列点击超时（Layui 隐藏固定列）→ 改 `js_click` + 节点幂等后复验；
  - 六方式最终回归（全 UI，顺序执行、均 0 次重试、每条 19 处 UI 操作日志）：
    1 委托 `FW-YWB-CG20260151`（421s）、2 比选 `HW-YWB-CG20260237`（365s）、3 竞争谈判
    `FW-YWB-CG20260152`、4 唯一来源 `FW-YWB-CG20260153`（纪要页面上传）、7 议价 `FW-YWB-CG20260154`（A7）、
    7 比价 `GC-YWB-CG20260038`（A7），全部 success / status=9；报告目录
    `automation_py/reports/UI自动化-20261129-M{1,2,3,4,7Y,7B}-FU02/`。
- S15/S16 评估：两步页面核心是 OnlyOffice 在线编辑器（需求书编辑页、审计报告编辑页），本地栈默认不启动
  OnlyOffice（18099），走 UI 需先启动该容器（约 1.3GB 内存，属环境改动需确认）；线上 S16 已有
  `AuditDraftPage` 编辑器保存路径（`HP_AUDIT_SAVE_MODE=editor`）。结论：暂保持接口路径，作为后续可选项。
- 验证：`env_check.py` PASS 39 / WARN 1（OnlyOffice 可选）/ FAIL 0；`pytest -q` 50 passed / 4 skipped；
  六种方式全链均 success / status=9（0 次重试）：
  1 委托 FW-YWB-CG20260136（332s）、2 比选 FW-YWB-CG20260135、3 竞争谈判 FW-YWB-CG20260137、
  4 唯一来源 HW-YWB-CG20260222、7 院内议价 FW-YWB-CG20260138（终态 A7）、7 院内比价 HW-YWB-CG20260223（终态 A7）。
  报告目录 `automation_py/reports/UI自动化-20261128-M{1,2,3,4,7Y,7B}-R01/`。
- S11 全 UI 复验（2026-11-28 晚）：全新全链 `FW-YWB-CG20260140`（方式 2）success / status=9，
  S11 规划→勾选→登记 12.8s、0 次重试，步骤合计 302s；另一条 `GC-YWB-CG20260037` 经续跑亦到 status=9。
  库内核对：`extract_mode=MANUAL / dial_mode=MANUAL / argument_mode=OFFLINE`，3 位专家 `draw_status=2`。
  报告目录 `automation_py/reports/UI自动化-20261128-M2-UI0{1,2}/`。
- S11 全 UI 下**六种方式复验**（2026-11-28 晚，顺序执行、均 0 次重试、S11 各 13～14.5s）：
  1 委托 `HW-YWB-CG20260226`（292s）、2 比选 `FW-YWB-CG20260143`、3 竞争谈判 `FW-YWB-CG20260144`、
  4 唯一来源 `HW-YWB-CG20260227`、7 院内议价 `HW-YWB-CG20260228`（A7）、7 院内比价 `FW-YWB-CG20260145`（A7），
  全部 success / status=9。报告目录 `automation_py/reports/UI自动化-20261128-M{1,2,3,4,7Y,7B}-UI01/`（M2 为 UI03）。
