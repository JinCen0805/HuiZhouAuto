# 惠州市中心人民医院电子化采购平台 · 采购前置流程 UI 自动化可行性评估

> 评估时间：2026-11-18
> 评估环境：**仅本地环境** `http://127.0.0.1`（本地全栈，未连接 172.16.x 线上/测试环境）
> 依据材料：
> - 手册原文+147 张截图：`_analysis/manual_text.txt`、`_analysis/images2/`
> - 手册步骤化解读：`_analysis/A_manual_steps.md`
> - 前端页面/选择器/接口盘点：`_analysis/B_frontend_selectors.md`
> - 后端接口/审批流/状态机/数据/阻断点：`_analysis/C_backend_data.md`
> - 登录/平台/菜单链路验证：`_analysis/D_env_login.md`
> - 本评估期间实际可运行的 PoC：`automation/`（含截图 `automation/shots/`）
> 证据口径：**实测** = 本地真实跑过；**代码** = 源码/配置有据；**推断** = 依据手册/截图判断、未实测。

---

## 0. 结论（TL;DR）

**能写，而且已经写出了可运行的第一版。**

1. **可行性结论**：采购前置流程可以做成自动化，但**不能是"纯 UI 一键点到底"**。正确形态是
   **"UI 自动化为主线 + 少量接口/mock 处理跨系统、异步、签名、定时发布等环节"** 的混合方案。
   - 原因：主链（申请→纪检→分包→调研→论证→需求→审计→审查→方式→执行）绝大部分是普通表单/列表/弹窗，
     前端控件规范（`id/idName/lay-event`、菜单 id、iframe 结构稳定），适合 UI 自动化；
   - 但专家电话确认、扫码手写签名、调研公告定时发布、企查查背调、OnlyOffice 正文编辑这几类，
     纯点击不可控或依赖外部系统，必须用接口/本地 mock/预置文件绕行（本地都已找到对应能力）。
2. **已经实测跑通的范围**（本次 PoC，本地环境真实数据）：
   - ① 采购申请发起（选预算计划→保存草稿→确认）→ 状态 `待分配监督员`；
   - ① 纪检主任分配监督员（接口）→ 状态 `待分包`；
   - ② 项目分包（新增子包→保存→确认锁定）→ 状态 `待调研`，并**自动生成调研项目**；
   - 一键命令 `pwsh -File automation/run-demo.ps1` 可重复跑通（已连续 3 次成功，
     申请单号 `HW-YXGZB-CG20260008/009/010`）。
3. **全链工作量估算**：约 **17~26 人天**（分三期）。其中：
   - P0（跑到"待调研/调研项目管理"）**4~6 人天**——本次 PoC 已完成约一半；
   - P1（调研论证+供应商响应+需求编制+审计+三方审查）**8~12 人天**；
   - P2（采购方式分配+采购执行申请+端到端回归/CI/数据清理）**5~8 人天**。
4. **必须先解决的 3 个本地环境/数据问题**（详见 §10）：
   - 本地网关缺 `/hospital-procurement/` 路由（新版页面全部"数据接口请求异常"）——**本次已修补本地配置**；
   - 纪检服务与 registers 的 Redis DB 不一致（DB7 vs DB9）→ 纪检接口 401（可用 key 同步绕过，建议改配置根治）；
   - 手册里的 `cy-cbbm-jbr` 账号不能用于前置流程（无管理组织、所属组织已禁用），
     要换 `cbbm1`（医务部，推荐）或 `wanglun`（医学工程部）。
5. **不建议**：直接改库推进状态（`status` 是多闸门派生结果，改库会与审计/审查/方式表脱节），
   也不建议做 100% 纯 UI（异步/签名/外部系统会长期不稳定）。

---

## 1. 评估范围与方法

| 维度 | 内容 |
|---|---|
| 手册 | 采购申请管理 → 项目分包 → 市场调研与论证 → 采购需求与审查 → 采购方式分配 → 采购执行申请（6 大业务章节，连同登录共 21 个步骤/子阶段） |
| 代码 | 前端 `openresty/nginx/html/{HospitalProcurement,DisciplineInspection,Register}`；后端 `hospital-procurement`、`discipline-supervision`、`ebidding-business-approval`、`professor`、`registers`、`nodejsdynamiccontrol` 等 20+ 仓库 |
| 数据 | 本地 MySQL（docker `hospital-local-stack-mysql-1`）只读核对：申请单 535 条、可引用预算计划 181 条、调研项目 82 条、论证 77 条、审计 77 条、需求审查任务 906 条、审批待办等 |
| 实测 | HTTP 登录/菜单链路；Playwright 登录+页面操作；纪检分配接口；分包 UI；审批待办接口；状态回读 |
| 不在范围 | 性能/安全测试、生产改造建议、财务/合规判断；线上环境验证 |

**关键判断**：这个项目的自动化难度不在"页面能不能点"，而在"**业务数据/组织关系/角色账号是否配齐**"
和"**异步/外部依赖是否可绕行**"——这两点本次都拿到了明确结论。

---

## 2. 手册流程与系统定位（自动化对象）

手册 6 大业务章节、21 个子阶段（含登录），涉及 **2 个前端应用**、**6 个后端服务**、**约 20 种角色**：

| 手册章节 | 子阶段 | 主要系统/前端 | 主要角色 |
|---|---|---|---|
| 一、采购申请管理 | S01 计划内申请发起；S02 预算外申请；S03 8 节点审批流 | 采购交易系统（HP） | 承办部门干事、需求科室申请人/主任/分管院领导、承办部门主任、行政主管、财务部、院领导 |
| 一、采购申请管理 | S04 纪检分配监督员 | **纪检监察平台** | 纪检主任、监督员 |
| 二、项目分包 | S05 分包 | 采购交易系统（HP） | 承办部门干事 |
| 三、市场调研与论证 | S06 调研信息；S07 公告编制发布；S08 供应商响应；S09 结果/背调；S10 资格性审查；S11 专家抽取；S12 线上论证；S13 线下论证；S14 延期 | 采购交易系统（HP）+ 专家库 professor | 承办部门干事/主任、供应商、专家、专家组长 |
| 四、采购需求与审查 | S15 需求初稿；S16 审计（推送/受理/主任）；S17 终稿确认；S18 三阶段审查 | 采购交易系统（HP）+ **纪检监察平台**（审计） | 承办部门干事/主任、审计员、审计部主任、财务部、采购部、纪检室主任 |
| 五、采购方式分配 | S19 分配+BT6 三节点审批 | 采购交易系统（HP） | 承办部门干事/主任、采购办主任、院办主任 |
| 六、采购执行申请 | S20 提交+BT13 五节点审批 | 采购交易系统（HP） | 承办部门干事/主任、分管院领导、采购办主任、分管领导 |

> 手册中的"选择监督员/专家/审计员/主任/干事/模板/采购方式/审查类型"等**均未给出选择规则**，
> 自动化时必须参数化，并由业务方确认取值规则（见 §11 待确认清单）。

---

## 3. 技术底座（决定了为什么"能自动化"）

### 3.1 前端：静态 HTML + jQuery + Layui + HCUI + iframe（对自动化友好）

- 页面无构建链、无 React/Vue，DOM 直出；控件普遍带 `id`、项目自定义属性 `idName`、`lay-filter`、
  行内按钮 `lay-event`，**选择器稳定可读**（详见 `_analysis/B_frontend_selectors.md` §2）。
- 首页是传统 iframe 多页签壳：菜单点击 → `changeView(title, url, menuId)` → `iframe` 加载业务页；
  **自动化可调用 `changeView` 直接打开任意模块**，再按 iframe URL 定位，绕开菜单点击的显隐问题
  （本次 PoC 即采用此方式）。
- 弹窗有两套：`HCUI.popDialog.confirm/msg` 弹在 **top 窗口**；`layer.open` 的表单弹窗可能在
  **当前 iframe 内**。脚本按"top 优先、frame 兜底"处理（PoC 已验证）。
- 菜单由 `GET /nodeJs/menu_Json` 动态下发（`{id,parentId,menu_name,url}`），
  不同角色菜单不同 → **自动化账号必须选对平台+角色**，且可用菜单 id 直达页面。

### 3.2 后端：Java 微服务 + Activiti + Redis，状态机清晰

- 采购主链在 `hospital-procurement`（HP，本地 17825）；纪检/审计在 `discipline-supervision`（8099）；
  审批流在 `ebidding-business-approval`（Activiti，8084）；专家库 `professor`（7817）；
  登录/平台/菜单在 `registers`（8081）+ `nodejsdynamiccontrol`（39001）。
- 申请单状态机 `hospital_purchase_request.status` 文档化（0 草稿/22 待分配监督员/8 待分包/
  7 待调研/15 待编制/17 待审计/20 待二次确认/11 待发起采购执行/9 采购中…），
  **每一步都有可断言的业务状态**（见 `_analysis/C_backend_data.md` §2、§5、§7）。
- 审批流 `BT8`（采购申请 8 节点）、`BT6`（采购方式 3 节点）、`BT13`（执行申请 5 节点）、
  `BT14`（需求编制）、`BT19`（调研结果）均有 BPMN 与待办/办理接口：
  `GET /EbiddingBusinessApproval/workflow/task/list/todo`、`POST /workflow/task/complete`
  （本次实测：`zhaoliu` 登录后待办接口返回 8 条，**审批自动化可用**）。

### 3.3 登录与多角色（已验证）

- 登录接口：`POST /Register/login/userLogin.do`（`password=MD5(明文)`、`SimplePwd=0`）。
- **验证码有服务端万能码**：`LoginAction.java` 中 `checkCode` 等于 `qwe!@#` 时直接通过；
  本次对 27 次多账号登录实测稳定通过。→ 自动化登录不需要 OCR/打码。
  ⚠️ 这是测试便利，也是**安全缺陷**（生产环境应移除或仅 local profile 启用）。
- 登录后 `select.do` 返回平台/角色（AES 密文，需原样回传）→ `gotoIndex.do` 返回目标系统 URL；
  **只有做过 gotoIndex，`userLoginInfo` cookie 才带上 prjCode/roleCode，菜单/业务接口才可用**。
- 多角色账号已实测可用（密码见团队测试账号表，本报告不记录）：
  承办部门干事 `cbbm1/cbbm2/wanglun/cy-cbbm-jbr`、承办部门主任 `zhaoliu/cbbmzr`、
  分管院领导 `libai`、行政主管 `qianqi`、财务 `sunba/zhoujiu`、采购办主任 `bailu`、
  院办主任 `baiqi`、分管领导 `fgld/fgyld`、纪检主任 `jjzr`、审计员 `sjyj`、审计部主任 `sjbzr`、
  需求科室 `zhangsan/lisi/wangwu`、供应商 `cy-gys1~3`、专家 `cy-zj1~3`。

### 3.4 本地环境能力（自动化落地条件）

- `start-local-project.cmd` 可拉起 22 个服务（HP/纪检/审批/专家库/文件/OnlyOffice 等），
  本地库有可直接使用的测试数据：**可引用预算计划 181 条**（医务部 32 条、医学工程部 18 条等）。
- 本地已开启专家抽取 mock 回调（`/professor/expertExtract/mock/...`），可模拟"电话确认参加"；
  扫码签名可用 token+base64 直调 `confirmReportSignature`；调研公告可"立即发布"绕过定时；
  文件上传走本地 `/doFile/upload/`，不依赖外部文件服务。
  → **结论：本地环境具备把全链自动跑通的能力，只需少量环境配置修复。**

---

## 4. 分阶段可行性矩阵（核心）

图例：✅ 可行（UI 为主）；⚠️ 可行但需接口/mock/特殊处理；❌ 当前数据/环境下不可行。

| # | 阶段 | 关键动作 | 推荐实现 | 判定 | 关键页面/接口 | 主要卡点与绕行 | 预估工作量 |
|---|---|---|---|---|---|---|---|
| S01 | 采购申请（**计划内**） | 选预算计划→保存草稿→确认 | UI | ✅ **已实测** | `view/procurementApply/list.html`；`hospitalPurchaseRequest/saveDraft`、`/confirm` | 需账号有对应归口部门的可引用预算计划（`wanglun`=医学工程部 / `cbbm1`=医务部）；`cy-cbbm-jbr` 不可用 | 1.5 人天（已完成） |
| S02 | 采购申请（**预算外** BT8） | 新增计划外预算→提交→8 节点审批 | UI | ❌ 当前数据不可行 | `outsidePlanReserveEdit.html`；BT8 `process_purchaseApply` | 需求科室只有"输血科"账号，而输血科不是"归口职能部门 level=2 子部门"→BT8 起始抛错；**建议走计划内**，或补组织数据 | 若补数据 +2 人天 |
| S03 | 采购申请审批流（8 节点） | 待办→办理→选结果/意见→提交 | UI 或接口 | ✅ 可行（接口已验待办） | `view/businessApproval/personal/todoTaskList.html`；`/workflow/task/list/todo`、`/workflow/task/complete` | 8 个角色账号需逐一登录；审批意见可预置固定值；驳回分支可做但非主链 | 2 人天 |
| S04 | 纪检分配监督员 | 列表→分配监督员→选监督员/范围 | UI 或接口 | ✅ **已实测（接口）** | `DisciplineInspection/view/projectList/index.html`；`/jjjc/supervise/assign` | 跨库直接写 `status 22→8`，无回调；本地 Redis DB 不一致需修复（§10） | 0.5 人天（已完成） |
| S05 | 项目分包 | 分包→新增子包→保存→确认 | UI | ✅ **已实测** | `view/packageManagement/index.html`、`editor/index.html`；`/hospitalPurchaseRequest/subpackages/**` | 确认前必须所有预算计划已分配；确认后自动建调研项目 | 1.5 人天（已完成） |
| S06 | 调研信息完善 | 起止时间、概况、评审指标（三类各≥1）、技术参数、材料 | UI | ✅ 可行 | `marketResearchManage/surveyProject/list.html`；`hpSurveyProject/updateById` | 评审指标内容需预置（模板/Excel 导入均可）；时间参数化 | 2 人天 |
| S07 | 调研公告编制发布 | 选模板→编辑→定时发布/立即发布 | UI + 立即发布 | ⚠️ 可行 | `hpSurveyProject/schedulePublish`、`/pushOneById` | **定时发布依赖时间**；用"立即发布"直接把 `state→2`，或把开始时间设为过去 | 1 人天 |
| S08 | 供应商响应 | 上传响应文件、填技术参数、提交 | UI 或接口 | ✅ 可行 | `hpSurveyReply/save` | 需 3 家供应商账号（`cy-gys1~3`）及响应文件样例；本地无外部校验 | 1.5 人天 |
| S09 | 调研结果/背调 | 查看结果、发起背调、0 响应重发 | UI | ⚠️ 部分 | `hpSurveyResult/*` | **背调走企查查，本地不生成**→跳过背调；0 响应分支通常不需要 | 0.5 人天 |
| S10 | 资格性审查 | 逐家通过/不通过→提交主任→主任一键/反驳→提交结论 | UI | ✅ 可行 | `hpSurveyResult/audit`、`submitToDirector`、`directorPassPending`；BT19 | 审查结论需预置；主任账号 `zhaoliu` | 2 人天 |
| S11 | 论证专家规划抽取 | 选方式/抽取方式/时间/地点/人数/专业→抽取/勾选 | UI 填表 + **mock 回调** | ⚠️ 可行（需 API） | `hpSurveyArgument/startExtract`、`saveManualExperts`；professor mock `callids/callback` | **随机抽取+电话确认纯 UI 不可行**：`voice.enable=false`；用"手动抽选"或 mock 回调 keypress=1；本地 mock 已开启 | 2.5 人天 |
| S12 | 线上论证 | 专家评审→组长报告→专家扫码签名 | UI + 签名 API | ⚠️ 可行（需 API） | `saveOpinions`、`saveReport`、`createReportSignatureQr`/`confirmReportSignature` | 签名必须手机扫码手写→用 token+base64 直调接口（无 CA）；报告正文可用模板 | 2.5 人天 |
| S13/S14 | 线下论证/延期 | 指定组长、上传报告、延期 | UI | ✅ 可行 | `saveOfflineResult`、`postponeArgument` | 线下需报告文件；**线下论证比线上省人工，推荐 PoC 用线下** | 1 人天 |
| S15 | 采购需求初稿编制 | 选模板→OnlyOffice 编辑→保存→提交初稿审计 | UI + 文件 | ⚠️ 可行 | `purchase/document/createByTemplate`、`/confirm-save`、`documentApproval/start` | OnlyOffice 正文不宜脚本撰写：用模板/预置文件+`force-save`；BT14 单节点 | 2 人天 |
| S16 | 采购文件审计 | 推送审计→审计员受理/报告→主任通过 | UI（跨前端） | ⚠️ 可行 | HP `hospitalPurchaseAudit/*`；纪检 `/jjjc/purchaseAudit/**` | 跨 2 个前端、2 类账号；审计报告模板已就绪；Again Redis 修复 | 3 人天 |
| S17 | 采购需求终稿确认 | 确认并提交主任→主任审批 | UI | ✅ 可行 | `documentApproval/second-confirmation`；BT14 | 主链标准审批 | 0.5 人天 |
| S18 | 采购需求审查（三阶段） | 发起→主任审查→三方并行→纪检终审（可前加签） | UI | ✅ 可行 | `hospitalPurchaseDemandReview/initiate|complete` | 无 BPMN、纯业务表，按 stage 建任务；三方 = 财务/审计/采购账号；`cgbgm` 无组织，建议 `cgbgs` | 3 人天 |
| S19 | 采购方式分配 | 选类别/方式/依据→BT6 三节点审批 | UI | ✅ 可行 | `procurementMethod/submit`；BT6 | 采购方式/评标方式属业务决策→参数化；唯一来源需附件，建议选普通方式绕开 | 1.5 人天 |
| S20 | 采购执行申请 | 编辑→提交→BT13 五节点→采购中 | UI | ⚠️ 可行 | `submitExecution`；BT13 | 提交前需 **4 类固定文书齐全**（`hpr_purchase_execution_document`）；多实例节点 1 人即过 | 2 人天 |

> 合计约 31 人天（含重复的框架/调试），扣除框架复用与接口辅助，**全链落地约 17~26 人天**。

**特别说明（与手册的差异）**：
- 手册 S03 采购申请审批只出现在"预算外"路径（BT8）；**计划内申请确认后不走审批**，直接进入纪检分配。
  这是本次实测确认的关键事实，意味着"最常用、最省事"的自动化路径是**计划内**。
- 手册 S04"纪检分配"在**纪检监察平台**（另一个前端），不是 HP 菜单。
- 手册 S16 审计受理也在纪检监察平台；HP 侧只负责推送。

---

## 5. 关键阻断点与绕行方案（全部有代码/实测依据）

| # | 阻断点 | 证据 | 纯 UI 能否 | 推荐绕行 | 复杂度 |
|---|---|---|---|---|---|
| B1 | 调研公告**定时发布** | `HpSurveyNoticeScheduleJob` 每 60s 扫定时公告；`startTime<=now` 直接发布 | 能，但要等 | **立即发布接口** `hpSurveyProject/pushOneById`（state→2、开始时间提前）；或把开始时间填过去 | 低 |
| B2 | 调研征集窗口/截止 | 轮次关闭依赖 `end_time` 与定时任务 | 部分 | 把 `start_time` 设为过去、`end_time` 设为未来 | 低 |
| B3 | **专家随机抽取** | `startExtract`→Dubbo professor 同步抽取 | 能点，但结果取决于专家库 | 优先**手动抽选**（MANUAL）：`listManualCandidates`→`saveManualExperts` | 中 |
| B4 | **专家电话通知/按键确认** | professor `MockCallbackService`（本地 `expert.extract.mock-callback.enabled=true`）；`voice.enable=false` | ❌ | **mock 回调**：`POST /professor/expertExtract/mock/projects/{id}/callids` → `POST .../experts/{id}/callback {callid,keypress:"1"}` | 中 |
| B5 | 专家库 HTTP facade 黑洞 | HP `professor.facade.base-url=http://127.0.0.1:9/` | ❌ | 抽取走 Dubbo（ZK 2181 已起），不要依赖 facade HTTP | 低 |
| B6 | 专家短信/账号短信 | `sms.enable=false`、`enabledSMS=false`、发送地址黑洞 | 不受影响 | 不建号/不发短信；用已有 `cy-zj1~3` | 低 |
| B7 | 论证报告**扫码签名** | token 表 + `confirmReportSignature(token,signature)`，签名图直接入库 | ❌（需真人手机） | **API 直调**：取/建 token → 传 base64 签名图；无 CA | 低 |
| B8 | 供应商**背调报告** | `survey.qcc.auto-trigger=false`，企查查外部 | ❌ | 跳过背调（审查页背调列为空不影响主链） | 低 |
| B9 | OnlyOffice 正文（需求书/审计报告/审查页） | OnlyOffice 容器 18099 已起，`createByTemplate`/`/confirm-save`/`force-save` | 能，但脚本不写正文 | **模板+预置文件**，必要时 `force-save`；不做正文自动撰写 | 中 |
| B10 | 采购执行前 **4 类固定文书** | `hpr_purchase_execution_document`（355 行），`submitExecution` 校验 | 能，需先上传 | 在"采购执行申请管理"补齐/上传 4 类文书再提交 | 中 |
| B11 | 预算外(BT8)组织闸门 | 需求科室=输血科非"归口职能部门 level=2"→`submitAudit` 抛"无法唯一匹配归口职能部门" | ❌ 当前数据 | 走计划内；或补 `b_organization/b_userorg/b_usermanageorg`（造组织数据，需授权） | 高 |
| B12 | 本地网关缺 `/hospital-procurement/` | 新版页面调用 `/hospital-procurement/api/...`，本地 nginx 无该 location → 404 → "数据接口请求异常" | ❌ 环境问题 | 网关补路由（本次已补 `openresty/local-dev/nginx.conf`） | 低 |
| B13 | 纪检接口 401 | discipline 服务本地 Redis DB=7，registers 登录 key 写 DB9 | ❌ 环境问题 | 根治：`local-stack.ps1` 将 discipline Redis DB 改为 9 并重启；临时：DB9→DB7 同步 key（PoC 已用） | 低 |
| B14 | 审批待办接口 | 实测 `GET /EbiddingBusinessApproval/workflow/task/list/todo` 用 `zhaoliu` 返回 8 条；POST 会 500（应 GET） | ✅ | UI 走个人待办，或接口直接办理；**注意方法必须 GET** | 低 |
| B15 | 采购工作台前端是开发态壳 | `procurementWorkbench` 使用 mock 权限模块 | 部分 | 不要以工作台 mock 数据做断言；用真实业务页/接口断言 | 低 |
| B16 | 状态不可直接 SQL 推 | `HospitalPurchasePostAuditGateServiceImpl` 按审计/审查/方式三表重算，幂等建执行草稿 | ❌ 不推荐 | 按真实业务链推进；验证三张表后再看 `status=11` | 中 |

---

## 6. 已完成的 PoC 实测（可行性直接证据）

### 6.1 实测结果（本地环境）

| 步骤 | 账号/系统 | 操作 | 结果（真实数据） |
|---|---|---|---|
| 1 | `wanglun` / 采购交易系统 | 采购申请管理→单独发起（TEST-2026-YXGC-*）→保存草稿→确认 | 生成申请单 `HW-YXGZB-CG20260008/009/010`，状态 `待分配监督员` |
| 2 | `jjzr` / 纪检监察平台 | 监察项目列表→分配监督员（接口） | 状态 `22→8 待分包`（跨库写） |
| 3 | `wanglun` / 采购交易系统 | 分包管理→分包→新增子包（`自动化子包-xxxx`）→保存→确认 | `是否分包=是`，状态 `待调研`，子包号 `HW-YXGZB-CG20260010-01` |
| 4 | `wanglun` / 采购交易系统 | 调研项目管理列表 | **自动生成调研项目** `UI自动化前置测试-… / HW-YXGZB-CG20260010 / 待调研` |
| 5 | `zhaoliu` / 采购交易系统 | 审批待办接口 | 返回 8 条待办（BT13），证明审批自动化数据可用 |
| 6 | `jjzr` / 纪检监察平台 | `canManageAssignment` | `canManage=true`，监督员候选 19 人 |

### 6.2 可复现命令

```powershell
# 前提：本地全栈已启动（start-local-project.cmd），且按 §10 修好本地网关/Redis
pwsh -File .\automation\run-demo.ps1
```

### 6.3 关键截图

- 采购申请-新增（表单）：`automation/shots/50-edit-dialog.png`
- 申请单管理-确认弹窗：`automation/shots/55-confirm-dialog.png`
- 确认后状态"待分配监督员"：`automation/shots/56-after-confirm.png`
- 分包-新增子包：`automation/shots/62-subpackage-dialog.png`
- 分包-确认弹窗：`automation/shots/70-package-confirm-dialog.png`
- 确认后"待调研"+ 调研项目自动生成：`automation/shots/72-survey-project-created.png`

### 6.4 PoC 说明了什么

- **登录、多账号、平台切换、动态菜单、iframe 页面、HCUI 弹窗**这些"自动化基础设施"全部可用；
- **业务主链前两阶段可以完全自动化并稳定断言**（状态、子包、调研项目）；
- **跨系统（纪检）用接口更稳**：跨库写状态、无回调依赖，UI 反而要处理另一套前端；
- 全链剩下的工作主要是"按页面逐个补 POM + 把 3 类特殊环节换成接口/mock"，不是"能不能做"的问题。

---

## 7. 推荐实施方案（架构与工程化）

### 7.1 总体架构（UI 主链 + 接口辅助）

```
┌────────────────────────────────────────────────────────────┐
│ 流程编排层 flow/：按 S01→S20 串阶段，阶段间做前置/后置断言     │
├──────────────┬──────────────────┬──────────────────────────┤
│ pageObjects  │ apiHelpers        │ dataFactory              │
│ Playwright   │ HTTP 直调（带 cookie）│ 预算计划查询/附件/模板/账号 │
│ 页面/iframe  │ 纪检/审批/专家mock/签名/立即发布 │ 唯一名称/时间参数生成 │
├──────────────┴──────────────────┴──────────────────────────┤
│ sessionManager：多账号（HTTP 登录→cookie→browser context），  │
│ storageState 缓存 + 失效重登；平台/角色显式选择               │
├────────────────────────────────────────────────────────────┤
│ 断言/报告：业务状态 + 接口返回 + 截图/trace + JSON 报告       │
└────────────────────────────────────────────────────────────┘
```

### 7.2 技术选型建议

| 项 | 建议 | 理由 |
|---|---|---|
| 语言/运行时 | Node.js（本机 v24 可用）+ `playwright-core` | 本次 PoC 已验证；`playwright-core` 可复用本机 Chromium，无需下载浏览器 |
| 浏览器 | 本机 Chrome/Chromium（`executablePath`） | 本地已安装；避免 CI 下载 |
| 登录 | **HTTP 登录 + cookie 注入**（主），UI 登录（备） | 更稳、更快；验证码万能码可用；平台/角色用 `select.do/gotoIndex.do` 原样回传 |
| 页面操作 | Playwright + `changeView` 直达 iframe 页 | 避免菜单显隐/多页签问题；iframe 按 URL 定位 |
| 接口辅助 | Node `fetch` + 同一 cookie | 纪检分配、专家 mock、签名、立即发布、审批兜底 |
| 断言 | 业务状态（申请单/调研/审计/审查/方式/执行）+ 接口返回 | 不看"页面 200"；无权限时业务接口返回 500/401 可识别 |
| 报告 | JSON + 截图 + trace；可选 Allure | 便于排障与回归 |
| CI | 本地栈 `start-all` → 跑脚本 → 数据清理 | 不建议接线上环境 |

### 7.3 关键工程规范

1. **账号/密码不写进仓库**：放环境变量或本地凭据文件（`%LOCALAPPDATA%`），仓库只存角色映射。
2. **一账号一会话**：同账号并发登录会互相覆盖 redis 单点 token；按阶段串行或分账号并行。
3. **全部业务数据打标记**：项目名/子包名/附件名统一前缀 `UI自动化-{runId}-`，便于清理与断言。
4. **参数化业务决策**：监督员/专家/审计员/主任/干事/模板/审查类型/采购方式/评标方式全部配置化，
   首版写"可用默认值"，并在配置中注明依据（业务方确认后固化）。
5. **两套弹窗 helper**：`top` 层与 `frame` 层统一查找；确认按钮按 `layui-layer-btn0` 精确点击
   （本次踩坑：不要用 `.last()` 混选，易点到"取消"）。
6. **失败即截图+保留现场**：每阶段 `page.screenshot` + 关键接口响应存 JSON。
7. **数据清理**：优先走页面/接口删除（草稿、子包）或按 `runId` 标记清理；**不做无条件 SQL delete**。

### 7.4 脚手架（本次已产出，可直接扩展）

```
automation/
├─ lib/hp-session.js          # 登录/选平台/进首页/changeView 开模块（已可用）
├─ poc/stage1-apply.js        # S01（已可用）
├─ poc/stage2a-supervisor.js  # S04（接口，已可用）
├─ poc/stage2b-subpackage.js  # S05-新增子包（已可用）
├─ poc/stage2c-confirm-package.js # S05-确认（已可用）
├─ poc/verify-stage2.js       # 状态/调研项目断言（已可用）
├─ run-demo.ps1               # 一键演示（已可用）
└─ explore/                   # 登录/菜单/纪检/审批接口探测脚本
```

---

## 8. 工作量与分期计划（建议）

| 期 | 目标 | 交付物 | 验收标准 | 工期 |
|---|---|---|---|---|
| **P0 主链前半段** | 计划内申请→纪检分配→分包→调研项目生成→（可选）调研信息+公告立即发布 | 可执行脚本 + 1 条样例数据 + 使用说明 | 一条命令生成"待调研/调研中"数据；失败有截图/日志 | **4~6 人天**（本次已完成约 2.5 人天：S01/S04/S05） |
| **P1 调研论证+需求审计审查** | 供应商响应→资格性审查→专家抽取(mock)/论证/签名→需求编制→审计→三方审查 | 脚本 + mock 调用封装 + 模板/附件库 | 数据推进到"审查通过/待方式分配"，全链可重复 | **8~12 人天** |
| **P2 方式分配+执行申请+工程化** | BT6→BT13→采购中；CI/报告/清理/文档 | 回归套件 + 配置化 + 清理工具 + 交接文档 | 端到端稳定跑 3 次；可指定项目类型/金额/部门 | **5~8 人天** |

**建议先做 P0/P1（12~18 人天）**，即可覆盖下游测试最常缺的"待调研/待论证/审查通过"数据；
若下游测试需要"采购中（可招标）"，再补 P2。

---

## 9. 风险清单

| 类别 | 风险 | 影响 | 应对 |
|---|---|---|---|
| 业务规则 | 监督员/专家/审计员/模板/采购方式无选择规则 | 脚本只能写死默认值，可能不符合业务预期 | 先让业务方确认默认策略（§11） |
| 数据/组织 | 需求科室/承办部门组织绑定不完整（如 `cy-cbbm-jbr`、预算外 BT8） | 部分路径跑不通 | 用已核实的账号组合；预算外走计划内或补组织 |
| 环境 | 本地网关/Redis 配置与生产不一致（本次发现 2 处） | 页面接口 404/401 | 修本地配置并纳入启动脚本；自动化启动前自检 |
| 页面改版 | 前端仍在迭代（页面带版本号、部分页面新旧两版） | 选择器失效 | POM 集中维护 + 每阶段断言+截图；优先用 `id/idName/lay-event` 与接口断言 |
| 异步/外部 | 专家电话、企查查背调、OnlyOffice 正文 | 纯 UI 不可控 | 接口/mock/预置文件；不做正文自动撰写 |
| 数据污染 | 每次运行产生申请/子包/调研项目 | 本地库膨胀、数据干扰 | 统一前缀+清理脚本；限制运行环境 |
| 安全 | 验证码万能码 `qwe!@#` | 生产环境登录绕过风险 | 建议生产移除/仅测试 profile 启用（本次评估发现，需安全侧跟进） |
| 合规 | 自动化操作留下操作日志/审批记录 | 审计口径 | 使用专用测试账号；生产环境禁止运行 |

---

## 10. 本地环境与数据修复建议（自动化运行的前提）

1. **补网关路由**（本次已改本地配置，未提交）：
   `openresty/local-dev/nginx.conf` 增加：
   ```nginx
   location ^~ /hospital-procurement/ {
       rewrite ^/hospital-procurement/(.*)$ /$1 break;
       proxy_set_header Host $host;
       proxy_pass http://${host_gateway}:17825$uri$is_args$args;
   }
   ```
   现象：不补则新版页面（采购申请、分包、调研等）全部提示"数据接口请求异常"。
2. **对齐纪检服务 Redis DB**（本地栈配置差异）：
   `db/infra/local-stack/local-stack.ps1` 中 discipline-supervision 的
   `SPRING_REDIS_DATABASE = '7'` 与 registers 使用的 DB9 不一致，导致 `/jjjc/**` 返回 401
   "登录已过期"。建议改为 `'9'` 并重启该服务；PoC 中已用"DB9 key 同步到 DB7"临时绕过。
3. **修正账号选择**：前置流程不要用 `cy-cbbm-jbr`（无 `B_userManageOrg`，所属组织护理部已禁用），
   用 `cbbm1`（医务部，32 条可引用计划，**全链推荐**）或 `wanglun`（医学工程部，18 条）。
4. **选择计划时用"是否涉政采=否"**：本地政府采购平台（GOV）后端 502，涉政采项目会分流到 GOV；
   选 `governmentProcurement=否` 的预算计划，走院内 HP 调研主链。
5. **预算外（BT8）暂不纳入自动化**：需求科室只有输血科账号且组织不满足归口部门解析；
   如确需，需补组织数据（`b_organization`/`b_userorg`/`b_usermanageorg`），属数据变更需单独授权。
6. **专家环节用本地 mock**：确认 `expert.extract.mock-callback.enabled=true`（当前已开启）；
   否则专家确认无法自动化。
7. **OnlyOffice**：确认 18099 容器在跑；需求书/审计报告优先"模板+预置文件"，正文不自动撰写。
8. **数据清理**：每次运行用统一前缀+`runId`；建议提供受控清理脚本（按前缀删申请/子包/调研），
   不执行无 WHERE 的 SQL。

---

## 11. 需要业务方确认的取值规则（写脚本前）

| # | 待确认项 | 影响阶段 | 建议默认 |
|---|---|---|---|
| 1 | 承办部门/需求科室用哪套（医学工程部 or 医务部） | S01/全链 | **医务部**（`cbbm1`，数据最全） |
| 2 | 监督员选谁、监督范围 | S04 | 任选在岗监督员 + 全流程 |
| 3 | 调研评审指标内容（质量/安全/技术各≥1） | S06/S07 | 预置一套通用模板指标 |
| 4 | 公告模板、发布时间策略 | S07 | "调研公告"模板 + 立即发布 |
| 5 | 供应商响应文件/技术参数样例 | S08 | 预置 3 份响应文件 |
| 6 | 资格性审查结论（通过/不通过） | S10 | 三家全部通过 |
| 7 | 论证方式（线上/线下）、抽取方式（手动/随机） | S11~S13 | **线下论证**（最省人工）；手动抽选+3 名专家 |
| 8 | 论证报告正文、签名策略 | S12 | 模板报告 + API 签名 |
| 9 | 采购需求书模板、审计报告模板 | S15/S16 | 按项目类型选默认模板 |
| 10 | 三方审查类型（一般性/重点）与结论 | S18 | 一般性审查 + 全部通过，不走前加签 |
| 11 | 采购方式/评标方式/选择依据 | S19 | 按金额与项目类型给默认（需制度确认阈值） |
| 12 | 采购执行 4 类固定文书来源 | S20 | 预置模板文件 |

---

## 12. 交付物索引

| 文件 | 内容 |
|---|---|
| `_analysis/采购前置流程UI自动化可行性评估.md` | 本报告 |
| `_analysis/A_manual_steps.md` | 手册 21 阶段/110+ 动作的自动化步骤清单（含截图编号、必填项、阻断点） |
| `_analysis/B_frontend_selectors.md` | 每页 URL/iframe/选择器/lay-event/接口/上传签名组件/风险（约 104KB） |
| `_analysis/C_backend_data.md` | 接口表、状态机、审批流 BT6/BT8/BT13/BT14/BT19、账号角色、数据现状、阻断点、只读 SQL |
| `_analysis/D_env_login.md` | 登录→选平台→菜单链路、多角色差异、cookie/会话、自动化坑清单 |
| `automation/README.md` | PoC 使用说明与设计要点 |
| `automation/run-demo.ps1` | 一键演示（S01→S04→S05→验证） |
| `automation/poc/*.js` | 各阶段 PoC 脚本 |
| `_analysis/manual_text.txt`、`_analysis/image_order.txt`、`_analysis/images2/` | 手册文本与 147 张截图（证据） |

---

## 13. 最终建议（一句话版）

**值得做，而且建议立刻按"混合方案"做 P0/P1**：先修好本地 2 个环境配置、用 `cbbm1`+计划内路径，
把"申请→纪检→分包→调研论证→需求审查"自动化到"审查通过"，即可稳定产出下游测试需要的
"待调研/待论证/待招标"数据；剩余方式分配/执行申请（P2）和少量签名/mock 环节按本报告方案补齐。
预计 **17~26 人天** 可交付可重复使用的全链自动化，而不是每次找人手工跑。
