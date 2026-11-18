# 采购前置流程 UI 自动化 —— 后端接口 / 审批流 / 状态机 / 测试数据 / 异步阻断点可行性评估

> 分析角色：后端/数据流分析子代理（backend-analyst）
> 工作目录：`D:\Desktop\HuiZhouProject`
> 方式：**只读**代码检索 + **只读** SQL 查询（本地 docker MySQL `hospital-local-stack-mysql-1`，127.0.0.1:3307）。
> **未修改任何项目代码、未写库、未访问线上环境。**
> 证据口径：`文件:行号` 为源码证据；`表名.字段` 为本地库实测证据；无法验证的一律标注「未验证/需人工确认」。

---

## 0. 结论速览（先看这段）

| 阶段 | 手册动作 | 后端主服务 | 纯 UI 可行性 | 关键卡点 |
|---|---|---|---|---|
| ①-1 采购申请（**计划内**预算） | 发起→确认 | hospital-procurement | ✅ **高** | 用 `cbbm1`(医务部干事) + 医务部 32 条可引用计划；确认后 `status=22`，**不走 BT8** |
| ①-2 采购申请（**预算外**） | 发起→BT8 八节点审批 | hospital-procurement + ebidding-business-approval | ⚠️ **中/高（有硬闸门）** | 需求科室只有「输血科」一套账号，而输血科不是「归口职能部门」level=2 子部门 → 储备项目 `department_id` 无法解析 → BT8 起始即抛错（见 §3.3） |
| ①-3 纪检分配监督员 | 纪检主任分配 | discipline-supervision | ✅ **高** | 分配即跨库把 `status 22→8`，可直接用 `/jjjc/supervise/assign` 或 UI |
| ② 分包 | 新增子包→确认 | hospital-procurement | ✅ **高** | 确认后 `status=7`、`survey_state=1`，自动建调研项目 |
| ③ 市场调研与论证 | 6 大步 | hospital-procurement + professor | ⚠️ **中（需绕行）** | 定时发布可用「立即发布」绕过；**专家随机抽取+电话确认必须走 professor mock API**（本地已开启）；扫码签名可用 token+base64 签名绕过 |
| ④ 需求编制 / 审计 / 三方审查 | 编制→BT14→审计→审查 | hospital-procurement + discipline-supervision | ⚠️ **中** | 审计受理在**纪检平台**（另一前端 `/DisciplineInspection/`），OnlyOffice 在线编辑；审查无 BPMN，纯业务表状态 |
| ⑤ 采购方式分配 | 分配→BT6 三节点 | hospital-procurement | ✅ **中/高** | BT6 = `process_purchaseMethodApproval`，需求科室/承办/院办三节点，候选人齐 |
| ⑥ 采购执行申请 | 提交→BT13 | hospital-procurement | ⚠️ **中** | 需 4 类固定文书齐全才可提交；BT13 多实例节点 1 人即过 |

**一句话结论**：`①计划内 → ②分包 → ③调研论证（须用 professor mock 回调） → ④编制/审计/审查 → ⑤方式分配 → ⑥执行申请` 这条链**后端是通的、可自动化的**；`①预算外(BT8)` 因「需求科室=输血科 不是归口职能部门」这一数据/组织配置事实，**当前用 UI 跑不通**，需改库补组织或改走计划内。

---

## 1. 环境、服务与路由（实测）

本地栈由 `db\infra\local-stack\local-stack.ps1` 拉起（`start-local-project.cmd` → `start-all`），nginx 反代配置 `openresty\local-dev\nginx.conf`。

| 前缀 | 后端端口 | 服务 | 说明 |
|---|---|---|---|
| `/Register/` | 8081 | registers | 登录 `POST /Register/login/userLogin.do`（username、password=MD5(明文)、checkCode） |
| `/HospitalProcurement/` | 17825 | **hospital-procurement**（院内采购主引擎） | 申请/分包/调研/需求/方式/执行 全部主页面 |
| `/EbiddingBusinessApproval/` | 8084 | **ebidding-business-approval**（Activiti） | `/workflow/**` 待办/办理/驳回 |
| `/jjjc/` | 8099 | **discipline-supervision**（纪检/审计平台） | `/jjjc/supervise/**`、`/jjjc/purchaseAudit/**`；静态页在 `/DisciplineInspection/` |
| `/professor/` | 7817 | **professor**（专家库） | `/professor/expertExtract/mock/**` 虚拟抽取回调 |
| `/PlanManagement/` | 7822 | plan-management | 计划申报（本报告不涉及主链） |
| `/ProcurementExecution/` | 8088 | procurement-execution | 后端采购执行（BT13 之后） |
| `/baseServer/` 8087、`/PublicServer/` 7805、`/ebiddingFile/` 18082、`/doFile/` 7807+17707、onlyoffice 18099 | | | 组织/附件/文件/在线编辑 |

> 注意：HP 是 jetty vhost `/local-hospital-procurement`，但对外上下文路径是 `/HospitalProcurement`（nginx `location /HospitalProcurement/` + `proxy_pass ...$uri`）。因此接口真实地址 = `http://127.0.0.1/HospitalProcurement/<controller mapping>`。

### 1.1 各阶段前端页面（b_menu 实测，prjCode_PR_NGR）

| 阶段/菜单 | pageUrl |
|---|---|
| 采购申请管理 | `/HospitalProcurement/view/procurementApply/list.html` |
| 项目分包管理 | `/HospitalProcurement/view/packageManagement/index.html` |
| 调研项目管理 | `.../marketResearchManage/surveyProject/list.html` |
| 调研结果管理 | `.../marketResearchManage/surveyResult/list.html` |
| 调研论证管理 | `.../marketResearchManage/surveyArgument/list.html` |
| 确认最终采购需求 | `.../marketResearchManage/finalPurchaseRequire/list.html` |
| 采购需求在线编制 | `/HospitalProcurement/view/procurementRequirement/index.html` |
| 审计管理 | `/HospitalProcurement/view/auditManagement/index.html` |
| 采购需求审查管理 | `/HospitalProcurement/view/procurementRequirementReview/index.html` |
| 采购方式分配 | `/HospitalProcurement/view/procurementMethodConfirm/index.html` |
| 采购执行申请管理 | `/HospitalProcurement/view/executionApply/list.html` |
| 采购工作台（待办/已办/结办） | `/HospitalProcurement/view/procurementWorkbench/index.html` |

---

## 2. 阶段① 采购申请发起（hospital-procurement）

### 2.1 状态机（`HospitalPurchaseRequestStatusEnum`，`hospital_purchase_request.status`）

| 值 | 含义 | 进入时机（代码证据） |
|---|---|---|
| 0 | 草稿 | `saveDraft` |
| 1 | 审批中 | `submitAudit`（仅预算外） |
| 2 | 已驳回待修改 | BT8 驳回回调 |
| 3 | 审批通过待承办 | 兼容旧链 |
| 4 | 已取消/作废 | — |
| 5 | 采购完成 | — |
| 6 | 已修改待重申 | 驳回后申请人修改 |
| 7 | 待调研 | **分包确认后** |
| 8 | 待分包 | **纪检分配监督员后** |
| 9 | 采购中 | **BT13 通过** |
| 10 | 待分配采购方式 | 历史「否」直进 |
| 11 | 待发起采购执行 | 审计+审查+BT6 双闸门通过 |
| 15 | 待编制采购需求文件 | **调研论证报告提交后 7→15** |
| 16 | 编制文件审批中 | 提交 BT14 |
| 17 | 待审计 | BT14 通过后建审计记录 |
| 18 | 采购需求审查中 | 发起需求审查 |
| 19 | 待审查与方式分配 | 审计通过后并行阶段 |
| 20 | 审计通过待二次确认 | 审计通过 |
| 21 | 审计退回待修改 | 审计驳回 |
| 22 | **待分配监督员** | 计划内/紧急确认后**

来源：`hospital-procurement\...\enumeration\HospitalPurchaseRequestStatusEnum.java:8-49`。
另一维度：`survey_state`（调研子状态，见 §5.1）。

### 2.2 接口表

| 动作 | 方法/URL | 关键参数 | 成功后校验 |
|---|---|---|---|
| 保存草稿（计划内） | `POST /HospitalProcurement/hospitalPurchaseRequest/saveDraft` | `purchaseRequestJson`（`HospitalPurchaseRequestSaveDTO`：requestName、requestDeptId/Name、projectType、projectAttribute、purchaseContent、totalBudgetAmount、reserveProjectIds[]、attachments[]） | 返回 uuid；`hospital_purchase_request` 新增 `status=0`，`hospital_purchase_request_project` 有储备项目行 |
| 保存草稿（预算外） | 同上 + `planType=2` + 前端「新增计划外预算计划」 → 同一 saveDraft | | |
| 预算外提交审批 | `POST /.../hospitalPurchaseRequest/submitAudit` | `purchaseRequestId` | `status=1`、写 `process_instance_id`（Activiti `process_purchaseApply`） |
| 驳回后重提 | `POST /.../hospitalPurchaseRequest/resubmitAudit` | `purchaseRequestId` | 继续原流程实例（`BT8_RESUBMIT`），不新建 |
| **确认（计划内/紧急）** | `POST /.../hospitalPurchaseRequest/confirm` | `purchaseRequestId` | `status=22`（零星且 `need_supervisor=0` 时直接 8）、写 `completed_at` |
| 分页 | `GET /.../hospitalPurchaseRequest/page` | `current/size/requestCode/requestName/status` | 列表状态 |
| 详情 | `GET /.../hospitalPurchaseRequest/detail` | `purchaseRequestId` | |
| 删除草稿 | `POST /.../hospitalPurchaseRequest/deleteDraft`、`/batchDeleteDraft` | | |

**关键代码事实**：`confirm()` 里 `if (planType != 计划内 && !urgent) throw "计划外采购申请必须提交 BT8 审批，不能直接确认"`；计划内确认即视为发起完成（`HospitalPurchaseRequestServiceImpl.java:521-604`，注释「计划内/紧急不走 BT8」）。

### 2.3 承办部门/需求科室如何被解析（决定 UI 能否选到数据）

`HospitalPurchaseApprovalAssigneeResolver.java` + `HospitalPurchaseApprovalAssigneeMapper.xml`：

- **承办部门干事（发起人）**：`resolveHandlingDepartments(userId)` 用 `B_userOrg` 找 `pcode=6D0B111786193047948（归口职能部门）` 的 level=2 部门（`:64-91`）。
- **承办部门（流程变量）**：不是申请人手选，而是**从本次申请的储备项目 `project_reserve.department_id` 反查** `B_organization`（`pcode=归口职能部门、LEVEL=2、disable=0`）；解析不出即抛「采购申请存在无法唯一匹配归口职能部门的储备项目」（`selectReserveProjectDepartmentIdsByPurchaseRequestId`、`countUnresolvedReserveProjectDepartmentsByPurchaseRequestId`）。
- **各节点候选人**：`selectUserIdsByRoleCodeAndOrganizationCodes` 用的是 **`B_userManageOrg`（管理组织）**，不是 `B_userOrg`；且要求 `ur.status='2'`、`r.disable='0'`、`o.disable='0'`、`u.disabled='0'`、`enableFlag='1'`。
- 找不到候选人 → `requireCandidateUsers` 抛「XX未配置启用的角色用户：ROLE」（`:463-480`），**整个 submitAudit 直接失败**（不是发起后卡在节点）。

### 2.4 计划内路径的数据起点（推荐）

`GET /HospitalProcurement/api/plan-management/reserve-library/selectable`（`ReserveLibraryController.java:84-96`）的筛选口径（`ProjectReserveMapper.xml` `querySelectablePage`）：

```
is_deleted=0 AND status IN ('active','储备中','未执行') AND approval_status='APPROVED'
AND COALESCE(is_quoted,0)=0 AND valid_from<=NOW() AND valid_until>=NOW()
```

实测本地可用：**181 条**。按承办部门分布（可引用）：

| department_id / 名称 | 可引用条数 | 预算合计 |
|---|---|---|
| CO6AGR1786413569276 医务部 | **32** | — |
| （department_id 为空）医务部 | 47 | 13,417,360 |
| 医学工程部 | 18 | 9,317,000 |
| 设备科 | 14 | 16,426,400 |
| 护理部 | 11 | 3,910,000 |
| 医院办公室 | 11 | 2,211,100 |
| 信息部 | 7 | 2,810,000 |
| …（其余部门 1~4 条） | | |

> 医务部 32 条示例（可直接用于自动化）：`GC-2026-10-007 消防系统改造工程`(115万)、`HW-2026-10-025 电子胃镜`(27.6万)、`FW-2026-10-005 医学检验标本外送服务`(36万)、`GC-2026-10-005 中心供应室扩建工程`(132万)、`FW-2026-10-027 电子病历系统运维服务`(46万)、`HW-2026-10-021 电动综合手术台`(47.2万) 等，`project_type` 货物/服务/工程齐全，`government_procurement=否`（=> 走院内 HP 调研，不进政采平台）。

---

## 3. 阶段① 审批流（Activiti）与纪检分配

### 3.1 部署的流程定义（`ebidding_business_approval.ACT_RE_PROCDEF` 最新版本，实测）

| KEY_ | 版本 | NAME_ | 用途 |
|---|---|---|---|
| `process_purchaseApply` | 43 | 医院采购申请审批 | **BT8** |
| `process_purchaseMethodApproval` | 6 | 采购方式审批 | **BT6** |
| `DocumentApproval` | 49 | 编制文件审批 | **BT14** |
| `process_purchaseExecutionApproval` | 244 | BT13采购执行申请审批 | **BT13** |
| `process_surveyResultAudit` | 34 | 调研结果办理 | 资格性审查（干事→主任） |
| `process_purchaseFile` | 116 | 招标文件串行复核 | 交易系统招标文件（非前置） |

`bt` 码 ↔ key 的权威映射在 `ebidding-business-approval\...\flowconfig\service\FlowBaselineCatalog.java`（`BT6/BT8/BT13/BT14/BT19` 注册块）。

### 3.2 BT8 节点与流转（`deployments\process_purchaseApply.bpmn20.xml` 源码 + 部署库一致）

| 序 | taskDefKey | 名称 | 候选人表达式 |
|---|---|---|---|
| 1 | `dept_director_approval` | 需求科室主任审批 | `${deptDirectorId}` |
| 2 | `dept_leader_approval` | 需求科室分管院领导审批 | `${deptLeaderId}` |
| 3 | `handling_dept_director_approval` | 承办部门主任审批 | `${handlingDeptDirectorId}` |
| 4 | `administration_opinion` | 行政主管部门意见 | `${adminAssignee}`（assignee，单人） |
| 5 | `finance_budget_approval` | 财务部预算审批 | `${financeBudgetUserId}` |
| 6 | `finance_director_approval` | 财务部主任审批 | `${financeDirectorId}` |
| 7 | `handling_dept_leader_approval` | 承办部门分管院领导审批 | `${handlingDeptLeaderId}` |
| 8 | `handling_dept_director_assign_handler` | 承办部门主任指定干事 | `${handlingDeptDirectorId}` |
| ↺ | `applicant_modify_resubmit` | 发起人修改并重新提交 | `${applicantId}` |

- **驳回**：1~7 任一节点 `auditResult='0'` → 网关 → `applicant_modify_resubmit` → 修改后回到节点 1 重走（同一流程实例）。**不会新建实例**（`WorkflowController.resubmitHospitalPurchase`）。
- 节点 8 完成后流程结束，回调把申请单置 `status=22 待分配监督员`（`HospitalPurchaseRequestServiceImpl.java:992、1094`）。
- 流程变量装载：`HospitalPurchaseRequestStartParam`（deptDirectorId/deptLeaderId/handlingDeptDirectorId/handlingDeptLeaderId/adminAssignee/financeBudgetUserId/financeDirectorId…）。

### 3.3 ⚠️ BT8 在本地当前数据下的硬闸门（重点）

用「需求科室=输血科（zhangsan/lisi/wangwu）」+「预算外新增计划」时：

1. 申请人组织 `9ITLQL1792655972474 输血科`，`pcode=YR6QHK1792654145409`（**不是** `6D0B…归口职能部门`、`LEVEL≠2`）。
2. BT8 起始前会执行 `countUnresolvedReserveProjectDepartmentsByPurchaseRequestId`，要求每个关联储备项目都能解析出「归口职能部门 level=2 子部门」；输血科不是 → 计数 >0 → **抛「采购申请存在无法唯一匹配归口职能部门的储备项目…」**（`HospitalPurchaseApprovalAssigneeResolver.java:129-137`、`HospitalPurchaseApprovalAssigneeMapper.xml`）。
3. 即便绕过第 2 点，节点 1/2 也要在「申请人组织树」里找 `REQ_DEPT_DIRECTOR/REQ_DEPT_LEADER`；lisi/wangwu 的管理组织只有输血科 → 能命中；但节点 3~7 需要承办部门，同样取决于储备项目部门。

**结论**：预算外路径要跑通，必须二选一：
- (A) 把需求科室换成「归口职能部门 level=2 子部门」下的科室（改 `b_organization`/`b_userorg`/`b_usermanageorg`，**属于造组织数据**）；或
- (B) **跳过预算外，走计划内（推荐）**：计划内不启动 BT8，确认即进 `status=22`。
（历史数据里确有 BT8 全 8 节点走完的实例：`ACT_HI_TASKINST` 中节点 1~8 完成数 114/88/84/86/74/70/68/67，最后完成时间 2026-10-29，说明流程本身可用，卡的是当前账号-组织-储备数据组合。）

### 3.4 审批引擎通用操作（BT8/BT6/BT13/BT14 通用）

| 动作 | 方法/URL（经 nginx） | 关键参数 | 说明 |
|---|---|---|---|
| 待办（个人 assignee） | `GET /EbiddingBusinessApproval/workflow/task/list/todo` | `current`、`size`、`processDefinitionKey`（可选）、`taskType`、`keyword` | 按登录人 userId 过滤（`WorkflowController.java:137-171`） |
| 待办（候选组） | `GET /EbiddingBusinessApproval/workflow/task/list/group/todo` | 同上 | 按 `ACT_ID_MEMBERSHIP` 的组 + userId（`:87-130`） |
| 已办 | `GET /workflow/task/list/completed`、`/task/list/handled` | | |
| 结办/全部 | `GET /workflow/task/list/finished`、`/task/list/all` | | |
| 任务详情 | `GET /workflow/task/todo/{taskId}` | | 返回表单属性（auditResult/comment） |
| 历史意见 | `GET /workflow/task/outcome/list/{taskId}`、`GET /workflow/historic/list?processInstanceId=` | | |
| **办理/审批** | `POST /EbiddingBusinessApproval/workflow/task/complete` | `TaskCompeletionParam`：`taskId`、`formProperties[auditResult]=1/0`、`comment`、`vars`、`groupId` 等 | `1=通过 0=驳回`；驳回必填 comment |
| 候选人抢办 | `POST /workflow/task/claim/{taskId}` | | 多实例/候选组场景 |
| 回退 | `POST /workflow/task/backoff`、`GET /workflow/task/backoff/tasks/{taskId}` | | |
| 扫码签名（审批） | `POST /workflow/task/signQr`、`GET /workflow/task/signStatus`、`POST /workflow/task/clearSign` | `taskId` | 部分节点需签名 |
| 预算外重提 | `POST /workflow/hospitalPurchaseRequest/resubmit` | `HospitalPurchaseResubmitParam` | 完成 `applicant_modify_resubmit` |
| 方式审批重提 | `POST /workflow/procurementMethod/resubmit` | Map body | BT6 驳回重提 |
| 流程实例 | `GET /workflow/pi/list`、`/pi/detail/{processInstanceId}` | | 验证用 |

**验证方法**：`ACT_RU_TASK`（当前待办）=某节点；`ACT_HI_TASKINST`（`TASK_DEF_KEY_`、`ASSIGNEE_`、`END_TIME_`）=已办；业务表 status 由回调更新。**推荐验证顺序：接口返回 success → 查业务表 status → 查 ACT_RU_TASK 节点名。**

### 3.5 纪检分配监督员（discipline-supervision）

| 动作 | 方法/URL | 关键参数 | 成功后校验 |
|---|---|---|---|
| 监察项目列表（待分配/监察中） | `GET /jjjc/supervise/projectPageList`、`/projectList` | 分页/状态 | 来自 `hospital_procurement.hospital_purchase_request` |
| 监督员候选 | `GET /jjjc/supervise/supervisorList` | | `B_userRole.jjjdy` |
| **分配监督员** | `POST /jjjc/supervise/assign` | JSON：`projectId`（=申请 uuid）或 `projectIds[]`、`supervisorUserId`、`supervisionScope`（`1全流程/2评审/3开标/4自定义`）、可选 scopeDetail | 写 `JJJC_supervisorAssign`；**跨库 UPDATE `hospital_purchase_request.status 22→8`**（`JjjcSupervisorAssignMapper.xml` `advanceToPendingSubpackage`：`WHERE status=22`） |
| 改派 | `POST /jjjc/supervise/reassign` | 同上 | 仅 `JJJC_DIRECTOR`（`canManageAssignment` 返回 canManage） |
| 是否可管理 | `GET /jjjc/supervise/canManageAssignment` | | |
| 全流程资料 | `GET /jjjc/supervise/processDocuments`、`/downloadAllZip` | | |

- 角色常量：`JJJC_DIRECTOR`（纪检监察主任，`b_role` prjCode_PR_JJJC）；通知收件人也按该角色（`SupervisorAssignmentGateService.notifyDirectorsPendingAssignment`）。
- HP 侧**不依赖纪检 HTTP 回调**：纪检直接写状态，HP 定时任务 `SupervisorAssignedNotifyScanTask`（`fixedDelay=15000`）扫描后发站内信（源码注释「不依赖纪检服务 HTTP 回调：纪检只写分配表与状态」）。
- ⚠️ 分配前 HP 只发「待分配」站内信，**没有待办表**——纪检状态即 `status=22`。

---

## 4. 阶段② 项目分包（hospital-procurement）

### 4.1 状态/字段

- `hospital_purchase_request.status`：进入时 `8 待分包`；`hospital_purchase_request.subpackage_status`：`0=未确认 / 1=已确认`（`SUBPACKAGE_STATUS_CONFIRMED`）；实测分布：`0→162`、`1→393`。
- 子包表 `hpr_subpackage`（633 行，无 status 字段，只有 `is_deleted`）；储备项目与子包关联 `hpr_subpackage_project`（673 行）。

### 4.2 接口表

| 动作 | 方法/URL | 关键参数 |
|---|---|---|
| 分包列表/详情 | `GET /HospitalProcurement/hospitalPurchaseRequest/subpackages/{purchaseRequestId}` | 返回申请+子包+储备项目 |
| 新增子包 | `POST /HospitalProcurement/hospitalPurchaseRequest/subpackages/{purchaseRequestId}` | 子包名、预算、`reserveProjectIds[]`、`bidEvaluationForm`、`validityOfBid`、`supplyPeriod` |
| 修改/删除子包 | `PUT` / `DELETE /.../subpackages/{purchaseRequestId}/{subpackageId}` | |
| 同步调研项目 | `POST /.../subpackages/{purchaseRequestId}/syncSurveyProjects`、`/syncAllSurveyProjects` | |
| **确认分包** | `POST /HospitalProcurement/hospitalPurchaseRequest/subpackages/{purchaseRequestId}/confirm` | |

### 4.3 确认后的分流（`HospitalPurchaseSubpackageServiceImpl.java:255-385`）

| 条件 | 结果 |
|---|---|
| 涉及政府采购（`gov=true`） | `govSurveyHandoffService.handoff`（进入政府采购平台调研，非本报告主链） |
| **普通院内采购（gov=false，非紧急/议价/零星）** | `status=7 待调研`、`survey_state=1`、`hpSurveyHandoffService.handoff` → **自动创建 `hp_survey_project`** |
| 紧急(1)/议价(2)/零星(spot) 绿通 | 直达 `status=11`（或中档零星 `status=7` 走调研） |

**校验点**：确认前必须「每个储备项目都已分配进子包」，否则抛「存在未分配到子包的储备项目」；涉政采子包还需填评标方式/投标有效期/货期。

---

## 5. 阶段③ 市场调研与论证（hospital-procurement + professor）

### 5.1 状态机（`HpSurveyProject.state`，`hp_survey_project`；同步 `hospital_purchase_request.survey_state`）

| state | 常量 | 含义 |
|---|---|---|
| 1 | STATE_DRAFT | 草稿（分包确认后自动建） |
| 2 | STATE_PUBLISHED | 调研中（已发布公告） |
| 3 | STATE_SCHEDULED | 定时发布待生效 |
| 4 | STATE_ARGUMENT_PENDING | 审查审完、待论证 |
| 5 | STATE_REVIEWING | 论证中 |
| 6 | STATE_ARGUMENT_DONE | 论证完成（报告已提交）→ 申请单 7→15 |
| 7 | STATE_WAIT_START | 待论证开始 |
| 8 | STATE_EXPERTS_SHORT | 专家未抽齐 |
| 9 | STATE_OVERDUE | 逾期 |
| 10 | STATE_DIRECTOR_PENDING | 待承办部门主任审批（资格性审查） |
| 11 | STATE_HANDLER_PENDING | 待干事审批 |
| 12 | STATE_RELAUNCH_PENDING | 待干事重新发起调研 |

常量来源：`hospital-procurement\...\hpsurvey\entity\HpSurveyProject.java`。
实测分布（82 行）：`1→34、4→1、5→1、6→60、8→5、9→11、10→3、11→6、12→1`。
论证子表 `hp_survey_argument.extract_status`：`0未抽/1抽取中/2已抽/3失败`（实测 `2→72、3→5`）；`report_status`：`0无/1草稿/2已提交`（实测 `2→61、0→16`）；`argument_mode`：`ONLINE/OFFLINE`（`SurveyOfflineArgumentPolicy.java:10-11`）；`extract_mode`：`RANDOM/MANUAL`；`leader_select_mode`：`MANUAL/VOTE`（`HpSurveyArgument.java`）。

### 5.2 接口表（前缀 `http://127.0.0.1/HospitalProcurement/hpSurveyProject/...`）

**调研项目 / 公告（HpSurveyProjectController）**

| 动作 | URL | 参数 |
|---|---|---|
| 列表 | `GET /hpSurveyProject/getPage` | 项目名/申请单号/类型/状态 |
| 详情/完善信息 | `GET /hpSurveyProject/getOneById`、`POST /updateById` | 调研起止时间、评审指标（质量/安全/技术）、技术参数、其他材料 |
| 公告内容套模板 | `GET /hpSurveyProject/getAnnouncementContentByTemplate` | |
| **定时发布** | `POST /hpSurveyProject/schedulePublish` | `HpSurveyProject{uuid,startTime,endTime,bullentTitle,bullentContent,attachmentIds...}`；`startTime<=now` 时直接发布 |
| **立即发布**（跳过定时） | `POST /hpSurveyProject/pushOneById` | `uuid` → `publishNowById`（公告立即 state=2，`start_time` 提前到 now，截止时间不变） |
| 导出模板/解析 Excel | `/downloadTechTemplate`、`/parseIndexExcel`、`/parseTechExcel` | |
| 部门下拉 | `/listDepartments` | |

**供应商响应（HpSurveySupplierReplyController / HpSurveyResultController）**

| 动作 | URL | 参数 |
|---|---|---|
| 参与调研/提交响应 | `POST /hpSurveyReply/save` | 项目 uuid、调研响应文件、技术参数、特殊说明 |
| 我的响应/按项目列表 | `GET /hpSurveyReply/getMyReply`、`/listByProject` | |
| **发起背调** | `POST /hpSurveyResult/retryQccReport`（重试）/ 自动见 `survey.qcc.auto-trigger=false` | 企查查外部，未接本地 |
| 资格审查列表/详情 | `GET /hpSurveyResult/getPage`、`/getDetail` | |
| **干事初审结论** | `POST /hpSurveyResult/audit` | 每家供应商结论 |
| 主任候选 | `GET /hpSurveyResult/listDirectors` | |
| **提交主任审批** | `POST /hpSurveyResult/submitToDirector` | 选主任 → 置 state=10 并启动 BT19 |
| 主任一键通过/反驳/提交结论 | `POST /hpSurveyResult/directorPassPending`、`/directorMark`、`/directorAudit` | 反驳理由必填 |
| 重新发起调研 | `POST /hpSurveyResult/relaunch` | state→12→待调研 |
| 导出技术参数表 | `GET /hpSurveyResult/downloadTechSpec` | |

**论证（HpSurveyArgumentController）**

| 动作 | URL | 参数/说明 |
|---|---|---|
| 列表/详情 | `GET /hpSurveyArgument/getPage`、`/getDetail` | |
| 专业列表/可用专家数 | `GET /hpSurveyArgument/listMajors`、`/queryUsableExpertCount` | 走 `ProfesorExtractService` Dubbo（**不是** HTTP base-url，见 §9 阻断点 D5） |
| **规划抽取（随机/手动）** | `POST /hpSurveyArgument/startExtract` | 论证方式 ONLINE/OFFLINE、抽取方式 RANDOM/MANUAL、起止时间、地点、人数、专业条件（多行，人数和须等于总数）、组长方式 |
| 重触发/再抽/补抽 | `POST /retryTrigger`、`/continueExtract` | |
| 手动勾选专家 | `GET /listManualCandidates`、`POST /saveManualExperts` | |
| 补抽候选/保存 | `GET /listMakeupCandidates`、`POST /saveMakeupExperts` | |
| **专家填意见** | `POST /hpSurveyArgument/saveOpinions` | 专家账号；`hp_survey_argument_opinion` |
| 指定组长 | `POST /designateLeader` | MANUAL 模式 |
| **投票选组长** | `POST /saveVote` | VOTE 模式 |
| 延期/催办 | `POST /postponeArgument`、`/urgeLeaderReport` | |
| **编制并提交报告** | `POST /saveReport`、`GET /getReportByTemplate`、`GET /downloadReport` | 组长；模板套打 Word |
| **扫码签名** | `POST /createReportSignatureQr`（干事/组长发起，生成 `hp_survey_argument_sign_token`）、`GET /prepareReportSignature?token=`、`POST /confirmReportSignature?token=&signature=`（base64 签名图，写 `signature_image`） | 无 CA，签名值直接入库 |
| 线下论证结果上传 | `POST /saveOfflineResult` | `SurveyOfflineArgumentPolicy` 强制线下不在系统填意见 |
| 过程包下载 | `GET /downloadProcessPack`、`/previewAsPdf` | |

**资格性审查流程 BT19**：`process_surveyResultAudit`（v34）节点 `handlerReview 承办干事办理` → `directorReview 承办部门主任办理`；主任「一键通过/反驳通过」对应 `directorPassPending/directorMark`；办完 → state=4（待论证）、`survey_state=4`、申请单仍 7。

### 5.3 调研/论证的异步与人工点（详解见 §11）

| 机制 | 证据 | 本地能否绕过 |
|---|---|---|
| 定时发布公告 | `hpsurvey\job\HpSurveyNoticeScheduleJob.java`：`@Scheduled(fixedDelay=60000, initialDelay=20000)` → `publishDueScheduledNotices()`（扫 `state=3 且 start_time<=now`） | ✅ 用 `pushOneById`（「立即发布」）直接 state=2 |
| 专家随机抽取 | HP `startExtract` → `HpSurveyDrawClient.triggerRandomExtract` → **Dubbo `ProfessorExtractService.triggerExpertExtract`** → professor `drawExpertExtractService.saveExpertExtract(project)`（`ProfessorExtractDubboService.java:134-190`，同步执行） | ✅ Dubbo 直连（不依赖 MQ） |
| 专家电话通知 + 按键确认 | professor `MockCallbackService`（`expert.extract.mock-callback.enabled`） | ✅ **本地已开启**：`POST /professor/expertExtract/mock/projects/{projectId}/callids` 生成 callid → `POST /professor/expertExtract/mock/experts/{expertId}/callback` body `{callid,keypress:"1"}`（1=参加/2=拒绝） |
| 专家短信/语音 | `sms.enable=false`、`voice.enable=false`、`enabledSMS=false`、`sms.sendUrl=http://127.0.0.1:9`（黑洞） | ✅ 本来就不发，不影响流程（专家账号不建号/不发短信仅日志） |
| MQ 抽取通道 | HP `draw_integration_outbox`（202 条，`draw.integration.outbox.relay.fixedDelay=5000`）；professor 侧 `draw.integration.listener.enabled=false` | ⚠️ MQ 方向本地关闭，但 Dubbo 方向可用（设计上 Dubbo 是兜底/实时通道） |
| 扫码签名 | `HpSurveyArgumentController.confirmReportSignature(token, signature)`；token 表 `hp_survey_argument_sign_token`（1756 行，143 已用） | ✅ 可「取 token → 直接 POST 签名 base64」 |
| 背调报告 | `survey.qcc.auto-trigger=false`；`QccSurveyAuditPublisher` 外部企查查 | ⚠️ 本地不生成，需人工/跳过（审查页背调入口会失败） |
| 论证报告模板 | `hp_survey_argument` 已有 `getReportByTemplate`；模板在 `resources/survey/`（PRD 确认） | ✅ 有模板 |

---

## 6. 阶段④ 采购需求编制 / 审计 / 三方审查

### 6.1 采购需求在线编制（`purchaseDocument` / `hospitalPurchaseRequest`）

| 动作 | 方法/URL | 参数/说明 |
|---|---|---|
| 待编制列表 | `GET /HospitalProcurement/hospitalPurchaseRequest/requirement-editing-page` | `status` 空=返回 15+16；按归口部门隔离 |
| 编制详情 | `GET /.../hospitalPurchaseRequest/requirement-editing-detail` | `purchaseRequestId` |
| 挂调研论证过程材料 | `POST /.../hospitalPurchaseRequest/ensureSurveyProcessPack` | |
| **按模板创建文档** | `POST /HospitalProcurement/purchase/document/createByTemplate` | `purchaseRequestId`、`templateUuid`、非政采只需《采购需求书》；政采需 +《采购实施计划》 |
| 在线编辑（OnlyOffice） | `GET /purchase/document/{documentUuid}/onlyoffice-config` | onlyoffice 容器 18099 已起 |
| 保存/强制保存 | `POST /purchase/document/{documentUuid}/confirm-save`、`/force-save` | |
| 文档状态/下载 | `GET /purchase/document/{documentUuid}/status`、`/download` | |
| **提交初稿审计 / 提交主任审批（BT14）** | `POST /HospitalProcurement/documentApproval/start`、`/submit-draft` | 提交后 `status=16`，启动 `DocumentApproval`（BT14）单节点 `documentApprovalDirector 承办部门主任审批` |
| 二次确认 | `POST /HospitalProcurement/documentApproval/second-confirmation` | `status=20` 时「确认并提交主任」 |
| 模板 | `purchase_document_template`（10 条）、`purchase_document_instance`（REQUIREMENT 122 / PLAN 23） | |

### 6.2 审计（HP 推送 + 纪检平台受理）

**HP 侧（干事）**

| 动作 | 方法/URL | 参数 |
|---|---|---|
| 审计列表 | `GET /HospitalProcurement/hospitalPurchaseAudit/page` | `auditStatus`：**0待推送 1审计中 2已通过 3被退回 4已作废**（`HospitalPurchaseAuditPageDTO` 注释） |
| 详情/编辑内容 | `GET /hospitalPurchaseAudit/detail`、`PUT /{auditId}/content` | |
| 上传/删除材料 | `POST/DELETE /hospitalPurchaseAudit/{auditId}/files` | |
| 生成报告（模板） | `POST /hospitalPurchaseAudit/{auditId}/report/generate` | |
| **推送审计** | `POST /hospitalPurchaseAudit/{auditId}/push` | 选审计员；HP `audit_status 0→1`，并在纪检库 `jjjc_purchaseaudit` 建记录 |
| 审计员候选 | `GET /hospitalPurchaseAudit/auditorCandidates` | role `AUDITOR`（纪检平台 prjCode） |

**纪检平台侧（`/jjjc/purchaseAudit/**`，登录选纪检平台）**

| 动作 | 方法/URL | 说明 |
|---|---|---|
| 待受理列表 | `GET /jjjc/purchaseAudit/page` | `auditStatus`：**1待审理 / 2待主任审批 / 3已通过 / 4已退回**（`JjjcPurchaseAuditStatisticsService.java:34`；通过/驳回校验 `oldStatus==2`，`JjjcPurchaseAuditService.java:489、534`） |
| 受理详情 | `GET /{auditId}/detail`、`GET /{auditId}/review` | |
| 审计报告模板 | `GET /jjjc/purchaseAudit/template/enabled`、`POST /{auditId}/report`、`POST /{auditId}/report/force-save` | 模板表 `jjjc_purchaseauditreporttemplate`（3 条）；OnlyOffice 在线编辑 |
| 上传子包/金额附件 | `POST /{auditId}/reserveAttachments` | |
| **提交主任审批** | 由保存报告/受理完成推进 `auditStatus=2` | 站内信通知审计部主任 |
| **主任通过** | `POST /jjjc/purchaseAudit/{auditId}/pass` | `2→3` |
| **主任驳回** | `POST /jjjc/purchaseAudit/{auditId}/reject` | 回 `4 已退回`，审计员重改再提交 |
| 报告下载 | `GET /{auditId}/report/preview`、`POST /batchDownloadReports` | |

**状态回写**：审计通过后 HP `hospital_purchase_audit.audit_status=2`，申请单进入 `20 审计通过待二次确认`（或 `19` 并行）。
实测：HP `hospital_purchase_audit` 77 条，`audit_status 0→3 / 1→3 / 2→71`，`audit_result=1→71`；纪检 `jjjc_purchaseaudit` `auditStatus 3→71（已通过）/2→1/5→1`；审计报告 134 条。

### 6.3 采购需求审查（三阶段，**无 BPMN**，纯业务表）

| 动作 | 方法/URL | 参数 |
|---|---|---|
| 审查列表 | `GET /HospitalProcurement/hospitalPurchaseDemandReview/page` | `review_stage` / `status` |
| **发起审查** | `POST /hospitalPurchaseDemandReview/initiate` | `purchaseRequestId`；置 `status=18 审查中`，建 stage1 任务 |
| 任务详情/结论详情 | `GET /taskDetail`、`GET /conclusionDetail` | |
| **完成审查** | `POST /hospitalPurchaseDemandReview/complete`（兼容 `/completeTask`） | 审查类型 `review_type`：**0待选/1一般性/2重点/3一般+重点**；逐项通过/不通过 + 结论 |
| 前加签候选/加签 | `GET /preSignOptions`、`POST /preSign` | 加签类型 0~3；干事审完回主任确认 |
| 文档 OnlyOffice | `GET /document/onlyoffice-config`、`POST /document/edit-lock`、`/force-save`、`/confirm-revision` | |

**状态字段**（实测分布，共 906 条）：

| 字段 | 取值 |
|---|---|
| `review_stage` | `1=承办部门主任审查`、`2=职能并行部门（财务/审计/采购）`、`3=纪检室主任终审`（`HospitalPurchaseDemandReviewServiceImpl.java:90-92`） |
| `status` | `1=待办`、`2=已完成`、`3=驳回`、`4=已取消`（`:86-89`） |
| `is_pre_sign_task` / `pre_sign_parent_task_id` | 前加签 |

实测：`stage1/status4=81、stage1/status2=65、stage1/status1=6、stage1/status3=1；stage2/status4=571、stage2/status2=180、stage2/status1=8、stage2/status3=1；stage3/status2=33、stage3/status1=2`；`review_type 1=702、0=82、3=111、2=53`。
> 「并行部门」不是 BPMN 会签，而是**同一 stage2 下按部门建多条任务**（`reviewer_department_code/reviewer_user_id/reviewer_role_code`），三方都 status=2 才进 stage3。

---

## 7. 阶段⑤ 采购方式分配（BT6）与 ⑥ 采购执行申请（BT13）

### 7.1 阶段⑤：BT6 `process_purchaseMethodApproval`（v6）

| 节点 | taskDefKey | 候选人 |
|---|---|---|
| 1 | `procurement_method_handling_director_approval` 承办部门主任审批 | `${handlingDeptDirectorId}` |
| 2 | `procurement_method_purchase_office_approval` 采购办主任审批（选评标方式） | `${purchaseOfficeDirectorId}` |
| 3 | `procurement_method_hospital_office_approval` 院办审批 | `${hospitalOfficeDirectorId}` |
| ↺ | `procurement_method_handler_modify_resubmit` 承办干事修改重提 | `${handlerUserId}` |

（部署库 BPMN 实测；`FlowBaselineCatalog.java` 注册 BT6=`process_purchaseMethodApproval`，角色 `HANDLING_DEPT_DIRECTOR / NGP_PURCHASEAGENTLEADER / NGP_ADMIN`。）

| 动作 | 方法/URL |
|---|---|
| 待分配列表（`status=10`） | `GET /HospitalProcurement/hospitalPurchaseRequest/procurementMethod/items` |
| 分配详情 | `GET /.../procurementMethod/detail?purchaseRequestId=` |
| **提交分配/发起 BT6** | `POST /.../procurementMethod/submit`（`HospitalProcurementMethodSubmitDTO`：purchaseRequestId、purchaseCategory、purchaseMethod、procurementBasis、gov 相关字段、`inHospitalPriceType`(零星/议价必填 1议价/2比价/3电话议价)、唯一来源需附件） |
| 驳回后重提 | `POST /.../procurementMethod/completeTask` |

- 表 `hpr_procurement_method_approval.status`：`0草稿/1审批中/2驳回/3通过`（`ProcurementMethodApprovalStatusEnum`）。实测：**3→312、1→8、2→1**（历史大部分已通过）。
- 审批通过后 `status` 演进见 §7.3 双闸门。

### 7.2 阶段⑥：BT13 `process_purchaseExecutionApproval`（v244）

| 节点 | taskDefKey | 名称 |
|---|---|---|
| 1 | `task2`（多实例 `handlingDeptDirectorIdList`，`nrOfCompletedInstances>=1`） | 承办部门主任审批 |
| 2 | `task3_N`（多实例 `handlingDeptLeaderIdList`） | 承办部门分管院领导审批 |
| 3 | `task4_N`（多实例 `purchaseOfficeDirectorIdList`） | 采购办主任审批（选采购办干事经办人） |
| 4 | `task5_N` | 分管领导审批 |
| 5 | `task6_N` | 分管院领导审批 |
| 紧急链 | `task3_U`/`task4_U`（预算 ≤1万 / 1万~3万 / ≥3万 分支） | 院领导/院长 |

（`deployments\process_purchaseExecutionApproval.bpmn20.xml:11-120+`；手动流顺序与手册「承办部门主任-承办部门分管院领导-采购办主任-分管领导-分管院领导」一致。）

| 动作 | 方法/URL | 前置 |
|---|---|---|
| 执行申请列表（`status=11`） | `GET /HospitalProcurement/hospitalPurchaseRequest/executionDetail?purchaseRequestId=` | |
| **提交执行审批** | `POST /.../hospitalPurchaseRequest/submitExecution` | ①BT6 已通过 ②4 类固定文书齐全（`hpr_purchase_execution_document`，355 行） |
| 文书列表/上传/删除 | `GET /HospitalProcurement/purchaseExecutionDocument/list`、`POST /upload`、`/deleteDocument` | |
| 办理 | `POST /EbiddingBusinessApproval/workflow/task/complete` | 各节点 auditResult=1 |

- 表字段：`hospital_purchase_request.execution_status`（实测：`3→219`、`NULL→336`，3 应为「已通过/已完成」）、`execution_proc_inst_id`、`execution_finish_time`。
- BT13 通过回调：`status=9 采购中`（`HospitalPurchaseRequestServiceImpl.java:1734`），并做政采/EEP 同步。

### 7.3 ④⑤→⑥ 的关键双闸门（`HospitalPurchasePostAuditGateServiceImpl.java:50-108`）

```
auditPassed && reviewPassed && methodApproved  →  status=11 待发起采购执行 + 幂等建执行草稿
auditPassed && reviewPassed                    →  status=10 待分配采购方式
auditPassed && 有活跃审查任务                  →  status=18 审查中
auditPassed && 其他                            →  status=19 待审查与方式分配
```
> 这是「审计 / 三方审查 / BT6」三件事并行推进的唯一收敛点；自动化时应**分别验证三张表**（`hospital_purchase_audit.audit_status=2`、`hospital_purchase_demand_review_task` stage2/3 全 status=2、`hpr_procurement_method_approval.status=3`），再看申请单是否到 11。

---

## 8. 审批流「被驳回如何流转」汇总

| 流程 | 驳回落点 | 证据 |
|---|---|---|
| BT8 采购申请 | 网关 → `applicant_modify_resubmit`（assignee=申请人）→ 修改后回节点 1；HP 用 `resubmitAudit` / `POST /workflow/hospitalPurchaseRequest/resubmit` 完成该任务 | `process_purchaseApply.bpmn20.xml`（4 个 `Flow_* 驳回 → applicant_modify_resubmit`，再 `Flow_0l6rlje → dept_director_approval`） |
| BT6 方式分配 | 三节点均可驳 → `procurement_method_handler_modify_resubmit` → 干事改后 `completeTask`；申请单 `status` 回退由业务层处理 | BPMN + `HospitalProcurementMethodApprovalController.completeTask` |
| BT13 执行申请 | 各节点驳回 → `rejectedEnd`（结束，不回退节点）；干事按业务提示修改后重新 `submitExecution` | `process_purchaseExecutionApproval.bpmn20.xml` 各 `gateway*_reject → rejectedEnd` |
| BT14 编制文件 | 主任驳回 → `documentApprovalRejected`；干事修改后再提交 | `process_documentApproval.bpmn20.xml` |
| BT19 调研结果 | 主任「反驳通过」直接以主任结论为准，不回退 | `process_surveyResultAudit.bpmn20.xml`（handlerReview→directorReview→finishedEnd） |
| 审计 | 主任驳回 → `auditStatus=4 已退回`，审计员重改再提交（非 Activiti） | `JjjcPurchaseAuditService.java:534` |
| 需求审查 | 审查项不通过 → 任务 `status=3 驳回`；干事修改后重新发起 | `hospital_purchase_demand_review_task.status` |
| 纪检分配 | 无驳回，改派用 `reassign` | `JjjcSuperviseController.java` |

---

## 9. 测试账号与角色覆盖（本地实测）

> 密码不在本报告出现。登录：`POST http://127.0.0.1/Register/login/userLogin.do`（`username`、`password=MD5(明文)`、`checkCode` 可用万能码）。
> 角色生效条件：`B_userRole.status='2'`、`B_role.disable='0'`、`P_userInfo.disabled='0'`、`enableFlag='1'`。
> **审批候选人取 `B_userManageOrg`（管理组织）；申请人所属科室/承办部门干事取 `B_userOrg`（组织）。**

### 9.1 手册岗位 → 可用账号（全部按库内实际角色码核过）

| 手册岗位 | 账号 | 角色码 / prjCode | 管理组织（B_usermanageorg） | 备注 |
|---|---|---|---|---|
| 需求科室申请人 | `zhangsan` | `REQ_STAFF` / NGR | 无（但 `B_userOrg`=输血科 9ITLQL） | 申请人组织用 `B_userOrg`，可用 |
| 需求科室主任 | `lisi` | `REQ_DEPT_DIRECTOR` / NGR | 输血科 9ITLQL | ✅ |
| 需求科室分管院领导 | `wangwu` | `REQ_DEPT_LEADER` / NGR | 输血科 9ITLQL | ✅ |
| **承办部门干事（发起）** | **`cbbm1`** | `NGP_CBBM_JBR` / NGR | 医务部 CO6AGR | ✅ **推荐**（医务部 32 条可引用计划） |
| 承办部门干事（发起） | `cbbm2` | `NGP_CBBM_JBR` / NGR | 信息部 LXQHYY | ✅（信息部 7 条计划） |
| 承办部门干事（发起） | `wanglun` | `NGP_CBBM_JBR` / NGR | 医学工程部/医务部（**umo.disabled=1**） | ⚠️ 可 saveDraft，审批候选人解析会被过滤 |
| 承办部门干事（发起） | `cy-cbbm-jbr` | `NGP_CBBM_JBR` / NGR | **无 manageorg；B_userOrg=护理部 hzzxrmyy_4（已禁用）** | ❌ 前置流程不可用（仅交易系统代理侧） |
| 承办部门主任 | `zhaoliu` | `HANDLING_DEPT_DIRECTOR` / NGR | 医务部 CO6AGR + 多部门 | ✅ 与 cbbm1 同部门 |
| 承办部门主任 | `cbbmzr` / `cy-xxb-bmzr` | `HANDLING_DEPT_DIRECTOR` | 信息部 LXQHYY | ✅ |
| 承办部门主任 | `cy-ywgcb-bmzr` | `HANDLING_DEPT_DIRECTOR` | 医学工程部 XTNL0T | ✅ |
| 承办部门主任（全部门兜底） | `liming` | `HANDLING_DEPT_DIRECTOR` / NGR | 几乎全部部门 | ✅ 万能主任 |
| **承办部门分管院领导** | `libai` | `HANDLING_DEPT_LEADER` / NGR | 医务部/信息部/医学工程部/医学装备部/财务部/审计部… | ✅ 关键节点唯一主力 |
| 承办部门分管院领导（兜底） | `liming` | `HANDLING_DEPT_LEADER` | 同 libai 覆盖面 | ✅ |
| 行政主管部门意见 | `qianqi` | `ADMIN_OPINION` / NGR | — | ✅（另有 xzzgbm1/xzzgbm3） |
| 财务部预算审批 | `sunba` | `FINANCE_BUDGET` / NGR | — | ✅ |
| 财务部主任 | `zhoujiu` | `FINANCE_DIRECTOR` / NGR | — | ✅（另有 cwbzr） |
| 采购办主任 | `bailu` | `NGP_PURCHASEAGENTLEADER` / NGR | — | ✅（另有 cy-cgb-zr、cy-cgb-fzr、cgbgs） |
| 医院办公室主任/院办 | `baiqi` | `HOSPITAL_OFFICE_DIR` / NGR | — | ✅ BT6 第 3 节点 |
| 分管领导 | `fgld` | `NGP_FGLD` / NGR | — | ✅ BT13 task5_N |
| 分管院领导 | `fgyld` | `NGP_FGYL` / NGR | — | ✅ |
| 院长（紧急链） | `cy-yz` | `NGP_PRESIDENT` / NGR | — | ✅ |
| 采购办干事（需求审查并行） | `cgbgm` | `NGP_CBGS` / NGR | **无组织**（departmentName=采购办） | ⚠️ 角色有、组织缺；审查任务按 `reviewer_department_code` 建，需确认前端是否能选到 |
| 采购办干事（多角色） | `cgbgs` | `NGP_CBGS`+`NGP_PURCHASEAGENT`+`NGP_PURCHASEAGENTLEADER` / NGR | 采购办公室 hzzxrmyy_27 | ⚠️ 一账号多角色（代码注释警告 roleCode 解析歧义） |
| 采购办经办（执行侧） | `cy-cgb-jbr` | `NGP_PURCHASEAGENT` / NGR | 采购办 ZZOXUK | ✅ 交易系统代理侧 |
| **纪检主任** | **`jjzr`** | `JJJC_DIRECTOR` / **prjCode_PR_JJJC**；`JJJC_DIRECTOR_JY` / NGR | 纪检室 O27GEZ（B_userOrg） | ✅ 登录须选「纪检监察平台」 |
| 纪检监督员 | `sjyj` / `cy-jjdy` / `cy-jjjc` / `jjjdy*` | `jjjdy` / JJJC(+NGR) | — | ✅ 分配时 supervisorUserId 用这些 |
| **审计员** | **`sjyj`** | `AUDITOR` / **prjCode_PR_JJJC**；`NGP_SJBGS`+`NGP_SUPERVISE` / NGR | 审计部 QVVCDO（B_userOrg） | ✅ 纪检平台受理审计 |
| 审计部主任 | `sjbzr` | `AUDIT_DEPT_DIR` / JJJC + NGR | 审计部 | ✅ |
| 供应商 | `cy-gys1~3`（+`cy-gys4~6`） | `NGP_SUPPLIER` / NGR(+GOV) | — | ✅ 调研响应/报名 |
| 专家 | `cy-zj1~3` | `NGP_EXPERTS` / NGR(+GOV) | — | ✅ 论证填表/投票/签名 |
| 采购人 | `cy-cgr` | `NGP_PURCHASE` / NGR | — | ✅ |

### 9.2 覆盖缺口（按重要性）

1. **`cy-cbbm-jbr` 不能用于前置流程**：手册/交易系统里它是「承办部门干事」示例账号，但库内 `B_userOrg` 只挂已禁用的护理部 `hzzxrmyy_4`，且**没有 `B_userManageOrg`**。`resolveHandlingDepartments` 只认 `B_userOrg`，审批候选人只认 `B_userManageOrg` → 用它发起会选不到承办部门/解析不到审批人。**必须换 `cbbm1`/`cbbm2`**。
2. **需求科室只有「输血科」一套**（zhangsan/lisi/wangwu），且输血科的父组织是 `YR6QHK…` 而非「归口职能部门」→ 预算外 BT8 的储备项目部门解析会失败（§3.3）。
3. **承办部门分管院领导只有 `libai` + `liming`**：如果要求「不同项目不同分管院领导」，没有第二条数据；且 libai 在 `hzzxrmyy_11 信息部（已禁用）`的 `B_userOrg` 是旧的，靠 manageorg 兼容。
4. **采购办干事 `cgbgm` 无组织**：需求审查 stage2 的「采购部」审查任务若按部门筛选，可能选不到人；`cgbgs` 有组织但一账号三角色。
5. **单角色单人多节点**：财务部（sunba/zhoujiu）、院办（baiqi）、行政主管部门（qianqi）各只有 1 人 → 「多人会签/不同人审批」无法真实模拟；BT13 多实例 `completionCondition=nrOfCompletedInstances>=1`，1 人即视为通过。
6. **纪检主任 `jjzr` 的角色只在 `prjCode_PR_JJJC`**：HP 侧不校验，但登录门户要选对平台，否则菜单出不来。

### 9.3 复现用只读 SQL（可原样执行，不含密码）

```sql
-- 账号与角色
SELECT u.username,u.legalName,u.departmentName,u.disabled,u.enableFlag,ur.roleCode,ur.roleName,ur.prjCode,ur.status
FROM baseserver.p_userinfo u JOIN baseserver.b_userrole ur ON ur.userId=u.userId
WHERE u.username IN ('cbbm1','cbbm2','zhaoliu','libai','qianqi','sunba','zhoujiu','bailu','baiqi','jjzr','sjyj','sjbzr','cgbgm','zhangsan','lisi','wangwu')
ORDER BY u.username,ur.prjCode,ur.roleCode;

-- 组织（申请用 B_userOrg；审批候选人用 B_userManageOrg）
SELECT u.username,'userorg' src,uo.orgCode,o.name,o.disable FROM baseserver.b_userorg uo
JOIN baseserver.p_userinfo u ON u.userId=uo.userId LEFT JOIN baseserver.b_organization o ON o.code=uo.orgCode
WHERE u.username IN ('cbbm1','cbbm2','zhangsan','lisi','wangwu','jjzr','sjyj');
SELECT u.username,'manageorg' src,umo.orgCode,o.name,o.disable,umo.disabled umoDisabled FROM baseserver.b_usermanageorg umo
JOIN baseserver.p_userinfo u ON u.userId=umo.userId LEFT JOIN baseserver.b_organization o ON o.code=umo.orgCode
WHERE u.username IN ('cbbm1','zhaoliu','libai','liming') AND umo.prjCode='prjCode_PR_SP';

-- 归口职能部门列表（level=2 且父=6D0B111786193047948）
SELECT code,name FROM baseserver.b_organization WHERE pcode='6D0B111786193047948' AND disable='0';
```

---

## 10. 本地数据现状（实测）

### 10.1 前置主表

| 表 | 行数 | 状态分布 |
|---|---|---|
| `hospital_purchase_request` | **535** | `0草稿69 / 1审批中22 / 2驳回10 / 3待承办60 / 4作废1 / 5完成9 / 6待重申1 / 7待调研50 / 8待分包38 / 9采购中216 / 10待分配方式7 / 11待执行37 / 16编制审批中8 / 17待审计4 / 18审查中4 / 19待审查与方式5 / 22待分配监督员14` |
| `hospital_purchase_request.subpackage_status` | — | `0未确认162 / 1已确认393` |
| `hospital_purchase_request.survey_state` | — | `NULL 403 / 1→43 / 4→1 / 5→1 / 6→74 / 8→5 / 9→14 / 10→3 / 11→7 / 12→4` |
| `hospital_purchase_request.execution_status` | — | `3→219 / NULL→336` |
| `hpr_subpackage` | 633 | 无状态列 |
| `hpr_subpackage_project` | 673 | — |
| `hpr_procurement_method_approval` | 321 | `3通过312 / 1审批中8 / 2驳回1` |
| `hospital_purchase_audit` | 77 | `0待推送3 / 1审计中3 / 2已通过71`；`audit_result=1→71` |
| `hospital_purchase_demand_review_task` | 906 | 见 §6.3 |
| `hpr_purchase_execution_document` | 355 | 文书（BT13 前置必填 4 类） |
| `project_reserve` | **923** | `approval_status：APPROVED 893 / PENDING 30`；`status：执行中679 / 未执行183 / 已完成14 / 储备中/active 41 / 待审批2`；**可引用 181** |
| `budget_plan_read_model` | 862 | `APPROVED 860 / PENDING 2` |
| `hp_survey_project` | 82 | `1→34 / 4→1 / 5→1 / 6→60 / 8→5 / 9→11 / 10→3 / 11→6 / 12→1` |
| `hp_survey_argument` | 77 | `extract_status 2→72 / 3→5`；`report_status 2→61 / 0→16` |
| `hp_survey_argument_expert` | 283 | `draw_status/notice_status/account_status/signature_status` |
| `hp_survey_argument_sign_token` | 1756（已用 143） | 扫码签名 token |
| `hp_survey_supplier_reply` / `hp_survey_round` | 226 / 107 | 供应商响应/调研轮次 |
| `purchase_document_instance` | 145 | `REQUIREMENT 122 / PLAN 23` |
| `publish_data_to_supervisory_platform` | 292 | 推纪检平台 |
| `JJJC_supervisorAssign`（baseserver） | 176 | 已分配监督员 |
| `jjjc_purchaseaudit`（baseserver） | 73 | `3已通过71 / 2待主任审批1 / 5→1` |
| `jjjc_purchaseauditreport` | 134 | 审计报告 |
| `jjjc_purchaseauditreporttemplate` | 3 | 审计报告模板（有） |
| `ACT_RE_PROCDEF` | 34 个 key | 见 §3.1 |

### 10.2 推荐「跑一条新前置流程」的起点

**首选（计划内，最稳）**：

| 项 | 值 |
|---|---|
| 发起账号 | `cbbm1`（医务部干事，`NGP_CBBM_JBR`） |
| 承办部门 | 医务部 `CO6AGR1786413569276`（`pcode=6D0B111786193047948`、level=2、disable=0，满足所有解析规则） |
| 预算计划（任选，`is_quoted=0`、`APPROVED`、`未执行`） | `GC-2026-10-007 消防系统改造工程` 115万 / `HW-2026-10-025 电子胃镜` 27.6万 / `FW-2026-10-005 医学检验标本外送服务` 36万 / `GC-2026-10-005 中心供应室扩建工程` 132万 / `HW-2026-10-021 电动综合手术台` 47.2万 … |
| 项目类型 | 货物类 / 服务类 / 工程类 均有（组合发起需类型一致） |
| 是否涉政采 | 均为「否」→ 走院内 HP 调研，不触发政采平台 |
| 分包确认后 | 自动建 `hp_survey_project(state=1)` → 去「调研项目管理」完善信息 |
| 后续审批人 | 承办部门主任 `zhaoliu`；分管院领导 `libai`；财务 `sunba`/`zhoujiu`；采购办 `bailu`；院办 `baiqi`；纪检 `jjzr`；审计 `sjyj`/`sjbzr` |

**备选（预算外/BT8，需先补组织）**：需求科室 `zhangsan/lisi/wangwu`（输血科）+ 先把「输血科」挂到归口职能部门下的 level=2 部门，或把申请科室改成 `cbbm1` 所在的医务部。

> 数据干净度提示：`project_reserve.department_id` 有大量为 NULL 的历史行（医务部 47 条、设备科 14 条等），这些**不能**用于 BT8（解析不出承办部门），但计划内路径（`selectable` 只按 status/approval）可用；选择时优先用 `department_id` 非空的 32 条。

---

## 11. 异步 / 时间 / 人工阻断点（逐条：证据 + 判定）

| # | 阻断点 | 代码/配置证据 | 纯 UI 能否走通 | 推荐绕行 |
|---|---|---|---|---|
| D1 | 调研公告**定时发布** | `HpSurveyNoticeScheduleJob` `@Scheduled(fixedDelay=60000, initialDelay=20000)`；`schedulePublish` 当 `start_time<=now` 直接发 | ✅ 能（等 ≤60s，或把开始时间设为过去） | **优先用「立即发布」`POST /hpSurveyProject/pushOneById`**（`publishNowById`，state 直接 2，`start_time` 提前到 now）；或把 `startTime` 填过去时间再 `schedulePublish` |
| D2 | 调研征集时间/截止后收卷 | 轮次关闭由 `HpSurveyRound.CLOSE_*` + job 扫描；供应商响应只在窗口内 | ⚠️ 部分 | 把 `hp_survey_project.start_time/end_time` 设成「已开始、未结束」；截止后响应需 `end_time` 在将来 |
| D3 | **专家随机抽取** | `startExtract` → `HpSurveyDrawClient.triggerRandomExtract(sectionCode)` → Dubbo `ProfessorExtractService.triggerExpertExtract` → professor `saveExpertExtract`（同步）；关联键 `HP-SURVEY-{uuid}[-R{n}]` | ⚠️ UI 能点，但**结果取决于 professor 是否有符合条件专家** | 优先**手动抽选（MANUAL）**：`startExtract(extractMode=MANUAL)` → `listManualCandidates` → `saveManualExperts`，完全绕开随机+电话 |
| D4 | **专家电话通知 + 按键确认** | professor `MockCallbackService`（`expert.extract.mock-callback.enabled`，本地 `=true`）：`POST /professor/expertExtract/mock/projects/{projectId}/callids` → `POST /professor/expertExtract/mock/experts/{expertId}/callback {callid,keypress:"1"}`（1=确认/2=拒绝）；`GET /experts/{expertId}/status` 查状态 | ❌ 真实电话不可用（`voice.enable=false`） | ✅ **必须用 mock 回调**：按 `HP-SURVEY-` 前缀查到 professor 的 drawProjectId，批量生成 callid，再逐个 keypress=1；HP 侧会通过 Dubbo 实时读到「确认参加」 |
| D5 | 专家库 HTTP facade | HP `professor.facade.base-url=http://127.0.0.1:9/`（黑洞，`sysconf.properties` / `local-stack.ps1:666`） | ❌ 走 HTTP 的专家库能力不可用 | 抽取/名单/专业数走 **Dubbo**（`HpSurveyDrawClient`、`ProfessorExtractService`，ZK 127.0.0.1:2181 已起），不要依赖 facade HTTP；若某页确用 HTTP 会失败，需改配置或跳过 |
| D6 | 专家短信/账号短信 | `sms.enable=false`、`enabledSMS=false`、`sms.sendUrl=http://127.0.0.1:9`（HP/professor 均如此） | ✅ 不影响流程 | 不建号/不发短信只打日志；专家用 `cy-zj1~3` 复用已有账号 |
| D7 | MQ 抽取结果通道 | HP `draw_integration_outbox`（202 条，relay 5s）；professor `draw.integration.listener.enabled=false` / `publisher.enabled=false` | ⚠️ MQ 方向断 | 使用 Dubbo 实时查询（`queryExtractedExpertsBySectionCode` preferLive），不要依赖 `hospital.draw.result.queue` |
| D8 | **扫码签名（论证报告）** | `HpSurveyArgumentController.createReportSignatureQr/prepareReportSignature/confirmReportSignature(token,signature)`；token 表 `hp_survey_argument_sign_token`；`signature` 直接存 `hp_survey_argument_expert.signature_image` | ✅ 能 | ①取/生成 token（`createReportSignatureQr` 或直接读表）②`POST confirmReportSignature?token=..&signature=<base64>`；也可用扫码页 `.../surveyArgument/reportSignatureScan.html` |
| D9 | 论证报告模板/套打 | `getReportByTemplate`/`downloadReport`；模板在 `resources/survey/`；`argument_mode=ONLINE` 才需编制+签名，`OFFLINE` 只需上传报告 | ✅ | 线上：组长 `saveReport` → 专家签名；线下：`saveOfflineResult` 上传报告即完成（**更省人工，推荐**） |
| D10 | 供应商**背调报告** | `survey.qcc.auto-trigger=false`；`QccSurveyAuditPublisher` 走外部企查查 | ❌ 本地不生成 | 跳过背调（审查页「本轮背调报告」会空）；必要时人工上传附件 |
| D11 | 资格性审查主任审批 | BT19 `process_surveyResultAudit`；`submitToDirector` → state=10；主任 `directorPassPending/directorMark` | ✅ | 主任账号 `zhaoliu` |
| D12 | **审计受理在另一前端** | 纪检平台 `/jjjc/purchaseAudit/**`，静态页 `/DisciplineInspection/`；登录需选纪检平台；审计员 `sjyj`、主任 `sjbzr` | ⚠️ 双系统多账号 | 可在 UI 走，也可直接调 `/jjjc/purchaseAudit/{id}/pass|reject`；报告用 OnlyOffice（18099 已起） |
| D13 | 审计报告模板 | `jjjc_purchaseauditreporttemplate`（3 条）；`POST /{auditId}/report` + OnlyOffice 编辑 | ✅ | 模板已就绪 |
| D14 | 需求文件在线编辑 | `purchase/document/createByTemplate` + OnlyOffice 18099；`purchaseDocument.callbackUrl=http://host.docker.internal:17825/...` | ✅ | OnlyOffice 容器已起；若编辑超时可用 `force-save`/`submit-draft` 直接提交 |
| D15 | 三方审查「并行会签」 | 无 BPMN；`hospital_purchase_demand_review_task` 按 stage2 多部门建任务；三方各自 `complete` | ✅ | 3 个账号分别登录办理（财务 `sunba`/`zhoujiu`、审计 `sjyj`、采购 `cgbgm`/`cgbgs`）；注意 `cgbgm` 无组织，选不到时用 `cgbgs` |
| D16 | 文件上传 | `fileservice.uploadServerUrl=http://127.0.0.1:7807/`、下载 17707；ebiddingfile 18082；`fileServerCheckUrl` 黑洞（校验被关闭） | ✅ | 直接上传本地文件即可（不校验外部文件服务） |
| D17 | 采购方式「唯一来源」附件 | 手要求唯一性论证会议纪要 | ✅ | 选非唯一来源方式（公开招标/比选等）绕开 |
| D18 | BT13 前置 4 类固定文书 | `hpr_purchase_execution_document` 必须齐全才 `submitExecution` | ⚠️ | 先在「采购执行申请管理」补齐/上传 4 类文书，再提交 |
| D19 | 纪检分配后的状态推进 | 纪检跨库 `UPDATE ... status=8 WHERE status=22`；HP 扫描任务 15s | ✅ | 分配后直接查 `hospital_purchase_request.status`，无需等回调 |

---

## 12. 可行性结论（分阶段）

### 12.1 分阶段判定

| 阶段 | 判定 | 依据 |
|---|---|---|
| ① 采购申请（**计划内**） | **✅ UI 自动化可行** | saveDraft→confirm 纯业务表，无审批、无异步；数据 181 条可引用（医务部 32 条） |
| ① 采购申请（预算外 BT8） | **❌ 当前不可行（数据/组织闸门）** | §3.3：需求科室=输血科 非归口职能部门 level=2 → BT8 起始抛错；需造组织数据或换科室 |
| ① 纪检分配监督员 | **✅ 可行** | 单接口 + 跨库状态回写，无异步 |
| ② 分包 | **✅ 可行** | 纯业务表，确认即建调研项目 |
| ③ 调研公告/供应商响应 | **✅ 可行** | 立即发布绕过定时；供应商 `cy-gys1~3` 直接 `hpSurveyReply/save` |
| ③ 资格性审查 | **✅ 可行** | 业务表 + BT19（干事→主任），账号齐 |
| ③ **专家抽取/确认** | **⚠️ UI 单靠点击不可行，必须调 mock 回调** | `voice.enable=false`/MQ 关闭；professor mock 已开启，走 API 可完全自动化 |
| ③ 论证填表/组长/报告 | **✅ 可行（线上）** | 专家 `cy-zj1~3`；组长指定/投票；报告模板有 |
| ③ 论证报告扫码签名 | **✅ 可行（API 直调）** | token+base64 签名，无 CA |
| ④ 需求编制 + BT14 | **✅ 可行** | OnlyOffice 已起；BT14 单节点 |
| ④ 审计（推送/受理/主任） | **⚠️ 可行但跨前端** | 干事在 HP 推送，审计在纪检平台；报告模板/OnlyOffice 就绪 |
| ④ 三方审查 | **✅ 可行** | 纯业务表；财务/审计/采购各 1~2 账号 |
| ⑤ 方式分配 BT6 | **✅ 可行** | 三节点候选人齐（承办主任/采购办主任/院办） |
| ⑥ 执行申请 BT13 | **⚠️ 可行但有前置** | 必须 4 类固定文书齐全；5 节点账号齐（zhaoliu/libai/bailu/fgld/fgyld） |

### 12.2 推荐执行路径（自动化脚本角度）

**推荐主链路（全后端可验证）**

```
① cbbm1 登录 → saveDraft(医务部 32 条计划之一) → confirm                    → 校验 status=22
① jjzr(纪检平台) → POST /jjjc/supervise/assign(projectId, supervisorUserId=sjyj, scope=1)
                                                                              → 校验 status=8 + JJJC_supervisorAssign
② cbbm1 → subpackages POST(新增子包) → subpackages/{id}/confirm              → 校验 status=7、survey_state=1、hp_survey_project.state=1
③ cbbm1 → hpSurveyProject/updateById(完善信息/指标) → pushOneById(立即发布)   → 校验 hp_survey_project.state=2
③ cy-gys1~3 → hpSurveyReply/save(响应)                                        → 校验 hp_survey_supplier_reply
③ cbbm1 → hpSurveyResult/submitToDirector(选主任 zhaoliu) → zhaoliu directorPassPending/directorAudit
                                                                              → 校验 hp_survey_project.state=4
③ cbbm1 → hpSurveyArgument/startExtract(MANUAL 或 RANDOM)
   RANDOM 额外：professor mock callids → callback keypress=1
                                                                              → 校验 hp_survey_argument.extract_status=2、expert 确认
③ cy-zj1~3 → saveOpinions → (指定/投票组长) → 组长 saveReport
   → createReportSignatureQr → confirmReportSignature(token, base64)
                                                                              → 校验 report_status=2、state=6、申请单 status=15
④ cbbm1 → purchase/document/createByTemplate → OnlyOffice 编辑/force-save → documentApproval/start
   → zhaoliu completeTask(BT14)
                                                                              → 校验 status 16→17/20、hospital_purchase_audit.audit_status=0
④ cbbm1 → hospitalPurchaseAudit/{id}/push(选 sjyj)
   → sjyj 纪检平台 /jjjc/purchaseAudit/{id}/... 提交主任 → sjbzr /pass      → 校验 audit_status=2
④ cbbm1 → hospitalPurchaseDemandReview/initiate → zhaoliu/sunba|zhoujiu/sjyj/cgbgm 各自 complete → jjzr(纪检终审)
                                                                              → 校验 stage2/3 任务 status=2、status=18/19
⑤ cbbm1 → procurementMethod/submit → zhaoliu → bailu(选评标方式) → baiqi
                                                                              → 校验 hpr_procurement_method_approval.status=3
⑥ cbbm1 → 补齐 4 类固定文书 → hospitalPurchaseRequest/submitExecution
   → zhaoliu → libai → bailu(选经办) → fgld → fgyld                              → 校验 status=9、execution_status=3
```

**不推荐**：直接 SQL 造数推进 `status`。原因：`status` 是多闸门派生结果（`HospitalPurchasePostAuditGateServiceImpl` 会按审计/审查/方式三张表重算并幂等建执行草稿），手工改状态会与 `hospital_purchase_audit`、`hpr_procurement_method_approval`、`hospital_purchase_demand_review_task`、`hp_survey_project` 脱节，后续页面按钮/校验会自相矛盾。

**必须保留人工的环节**：当前证据看**没有必须人工的环节**，但以下建议「半自动 + 人工兜底」：审计主任复核意见（业务判断）、论证报告正文内容（可用模板自动填充）、唯一来源论证（跳过该方式）、供应商背调（本地不生成，跳过）。

**必须改库/改配置的唯一一项**：若一定要跑「预算外 BT8」路径，需要补组织/账号绑定（`b_organization` 增加输血科为归口职能部门 level=2，或 `b_userorg`/`b_usermanageorg` 调整），否则只能走计划内。

---

## 13. 附录：本次用到的关键只读 SQL（不含密码）

```sql
-- 1) 可引用预算计划（selectable 口径）
SELECT COUNT(*) FROM hospital_procurement.project_reserve
WHERE is_deleted=0 AND status IN ('active','储备中','未执行') AND approval_status='APPROVED'
  AND COALESCE(is_quoted,0)=0 AND (valid_from IS NULL OR valid_from<=NOW()) AND (valid_until IS NULL OR valid_until>=NOW());
-- 按部门
SELECT department,department_id,COUNT(*) c,SUM(budget_amount) amt
FROM hospital_procurement.project_reserve
WHERE is_deleted=0 AND status IN ('active','储备中','未执行') AND approval_status='APPROVED' AND COALESCE(is_quoted,0)=0
GROUP BY department,department_id ORDER BY c DESC;

-- 2) 申请单状态分布
SELECT status,COUNT(*) FROM hospital_procurement.hospital_purchase_request GROUP BY status ORDER BY status;
SELECT survey_state,COUNT(*) FROM hospital_procurement.hospital_purchase_request GROUP BY survey_state;

-- 3) 各阶段存量
SELECT 'method' k,status,COUNT(*) FROM hospital_procurement.hpr_procurement_method_approval GROUP BY status
UNION ALL SELECT 'audit',audit_status,COUNT(*) FROM hospital_procurement.hospital_purchase_audit GROUP BY audit_status
UNION ALL SELECT 'survey',state,COUNT(*) FROM hospital_procurement.hp_survey_project GROUP BY state
UNION ALL SELECT 'argument_extract',extract_status,COUNT(*) FROM hospital_procurement.hp_survey_argument GROUP BY extract_status
UNION ALL SELECT 'argument_report',report_status,COUNT(*) FROM hospital_procurement.hp_survey_argument GROUP BY report_status
UNION ALL SELECT 'execution',execution_status,COUNT(*) FROM hospital_procurement.hospital_purchase_request GROUP BY execution_status;

-- 4) 需求审查阶段/状态
SELECT review_stage,status,COUNT(*) FROM hospital_procurement.hospital_purchase_demand_review_task GROUP BY review_stage,status;

-- 5) 纪检/审计
SELECT COUNT(*) FROM baseserver.JJJC_supervisorAssign;
SELECT auditStatus,COUNT(*) FROM baseserver.jjjc_purchaseaudit GROUP BY auditStatus;

-- 6) 审批待办（当前）
SELECT PROC_DEF_ID_,COUNT(*) FROM ebidding_business_approval.ACT_RU_TASK GROUP BY PROC_DEF_ID_ ORDER BY 2 DESC;
-- 流程定义
SELECT p.KEY_,p.VERSION_,p.NAME_ FROM ebidding_business_approval.ACT_RE_PROCDEF p
JOIN (SELECT KEY_,MAX(VERSION_) mv FROM ebidding_business_approval.ACT_RE_PROCDEF GROUP BY KEY_) m
  ON m.KEY_=p.KEY_ AND m.mv=p.VERSION_ ORDER BY p.KEY_;
```

---

**报告完成时间**：2026-11-18
**分析范围**：`hospital-procurement`、`ebidding-business-approval`、`discipline-supervision`、`professor`、`openresty`、`db\infra\local-stack`、`db\SQL\cy_测试人员与角色配置.sql`、`db\.trellis\tasks\08-31-hp-survey-argument`、`db\实际执行流程\实际执行流程.md`
**未做**：未修改任何文件（除本报告）、未写数据库、未访问线上环境。
