# 采购前置流程前端分析（Playwright 页面 / URL / iframe / 选择器 / 接口盘点）

> 分析范围：`openresty\nginx\html\HospitalProcurement`、`openresty\nginx\html\DisciplineInspection`（以及少量 `Register`、`GovernmentProcurement` 对照）。
> 分析方式：只读静态分析（HTML/JS/Api.js/Store.js/tests/日志/菜单缓存），**未修改项目代码、未启动/停止服务、未访问线上环境**。
> 证据来源：源码 grep/精读；`logs\NodeJsDynamicControl.log-*` 中 `/nodeJs/menu_Json` 的原始 JSON 响应（含 menuCode/url/parentId）；`automation\menu-cy-cgb-jbr.json`（cy-cgb-jbr 角色真实菜单）；`db\SQL` 中菜单/权限补丁；`automation\probe-*.js`（已跑通的登录/选平台/取菜单 HTTP 探测脚本）。
> 约定：下文中“菜单 code”即 `B_menu.menuCode`，同时就是左侧菜单 DOM 的 `node-id`、页签 `lay-id`。菜单文案/路径来自日志与缓存，**不同角色下发的菜单不同**，详见第 5 节。

---

## 0. 结论摘要（先看这 10 条）

1. 平台是 **静态页 + jQuery + Layui + HCUI + iframe**，无构建链；所有业务页都在 L0 外壳页的 `iframe.mainIframe` 里，单个菜单 = 一个 iframe = 一个 Layui 页签。
2. 表格统一是 **HCUI.datagrid（Layui table 封装的别名）**，操作列按钮是 `<a>/<button ... lay-event="xxx">文字</a>`，通过 `layui.table.on("tool(<lay-filter>)")` 分发。Playwright 定位：行内 `[lay-event="view"]`，不要按列序号。
3. **弹窗默认渲染在顶层窗口**：`renderPublickHead.js` 把 `HCUI_CONFIG.popDialog.isTop = top.layer`，`getBaseWin(isTop)` 为真时使用 `window.top.layer`。所以 `HCUI.popDialog` 的 `.layui-layer` 挂在**外壳页 body**，内容 iframe 的 src 才是业务页。Playwright 必须“外层 page 找 layer 容器 + frameLocator 进 iframe”，不要在业务 iframe 内部找 `.layui-layer`。
4. 表格列使用 `fixed:"left"/"right"`（采购申请管理最典型），Layui 会**复制一份固定列 DOM**（`.layui-table-fixed-l/.layui-table-fixed-r`）。点操作按钮或断言单元格时必须限定在 `.layui-table-main` 或明确允许 fixed 副本，否则会 strict mode 冲突/点到不可见副本。
5. 采购申请管理页有 **Tab 懒渲染**：`#applicationTable` 所在 tab 未激活、宽度为 0 时不会 `HCUI.datagrid`，代码最多轮询 8×50ms；自动化必须在点击“申请单管理”页签后再等表格渲染。
6. 表单字段基本不用 `name`，而用自定义属性 **`idName`**（`appCommon.formUtil.getParamByIdName("#form")` 读取）。CSS 属性名在 HTML 解析后小写，因此 Playwright 用 `[idname="requestName"]`（值大小写敏感）；文档里写作 `[idName=...]` 是源码写法。
7. 上传是 **WebUploader**：隐藏 `input[type=file]` + `#<filePicker>` 按钮 + `#<uploaderId>` 容器；服务端 `/doFile/upload/`（分片 512KB），下载 `/doFile/download/?attachmentId=`。市场调研页面用 `QaMultiFile`（包 WebUploader，选完自动传）；审计详情用原生 `#auditFileInput`。
8. 签名有两条路：PC 端生成二维码 `reportSignatureQr.html` / 审批页 `#approvalScanSignBtn`，手机端打开 `reportSignatureScan.html` 在 `#canvas` 手写并提交。自动化不要真的扫码，走接口或“无签名提交”路径（审批签名是可选的）。
9. 菜单 `url` 可能是**不带前导 `/` 的相对路径**（如 `view/procurementRequirement/index.html`、`view/businessApproval/personal/todoTaskList.html`），相对的是 L0 页 `/HospitalProcurement/index.html`，所以运行期仍是 `/HospitalProcurement/view/...`；而 `0000006 采购管理`下的部分菜单带前导 `/`。
10. 角色决定菜单：`cy-cgb-jbr` 的菜单 JSON 里**没有**采购申请/分包/需求编制/方式分配/执行申请/审计管理这些菜单；日志里另一角色（NGP_CBBM_JBR 等）才有 `0000006 采购管理` 的 0000006000001~0000009。E2E 必须用具备“采购办/需求科室/纪检”权限的账号，否则左侧菜单根本点不到。

---

## 1. 页面清单表

### 1.1 运行环境与 iframe 层级约定

```
L0  http://127.0.0.1/HospitalProcurement/index.html            ← 外壳（左侧 zhongMenu + 顶部 bar + layui tab）
 └ L1  iframe.mainIframe[name="<菜单名>"]  src="<菜单url>"      ← 一个菜单一个 iframe，一个 layui tab（lay-id = 菜单 node-id）
     └ L2  HCUI.popDialog 的 .layui-layer-iframe（默认挂 window.top）
         └ iframe（业务弹窗页，如 procurementApply/edit.html）
             └ L3  继续 popDialog（如 edit.html → reserveSelect.html）
纪检：http://127.0.0.1/DisciplineInspection/index.html          ← 独立外壳，结构与 HP 相同（zhongMenu + iframe + layui tab）
```

- 外壳页签：`#mainTab`（`lay-filter="mainTab"`，`lay-allowClose="true"`），tab 标题高度被 CSS 隐藏（`height:0`），**页签栏不可见但 DOM 存在**；切页签用 `element.tabChange('mainTab', nodeId)`，nodeId = 菜单 code。
- iframe 生成函数：`index.html` 的 `createFrame(title,url)`，`<iframe class="mainIframe" name="<菜单名>" src="<url>">`。
- 弹窗：`HCUI.popDialog({name,title,content,area,parentData,btn,btnFun,closeFun})`；容器 `.layui-layer.layui-layer-iframe`，标题 `.layui-layer-title`，按钮 `.layui-layer-btn0/.layui-layer-btn1`；子窗通过 `HCUI.popDialog.getLayerWindow({name})` 取 window。
- 状态码：`HcUI_CONFIG.datagrid` 要求接口返回 `{success:true, data:{records:[],total:n}}`（或 `data.list/total`，`fillterType` 变体），`fillter` 转成 Layui 的 `{code:0,data,count}`。

### 1.2 主表

| # | 业务步骤 | 菜单实际指向的 HTML（相对 `nginx/html`） | 运行时 URL / iframe 层级 | 打开方式 | 页面 title | 关键 JS |
|---|---|---|---|---|---|---|
| 0 | 登录 | `Register/public/newLogin/user_login_2.html` | `http://127.0.0.1/Register/public/newLogin/user_login_2.html`（L0） | 独立页 | 登录 | 页面内联脚本；POST `/Register/login/userLogin.do`，GET `/Register/login/verification.do`（验证码图 `#codeImg`） |
| 1a | 采购申请管理（列表） | `HospitalProcurement/view/procurementApply/list.html`（菜单 0000006000001，父 0000006 采购管理） | L1 `/HospitalProcurement/view/procurementApply/list.html` | 菜单→L1 iframe | 采购申请管理 | `procurementApplyApi.js`、`procurementStore.js`、页面内联脚本 |
| 1b | 发起采购（选预算计划） | 同 list.html 内 `lay-id="launch"` 页签（`#reserveLaunchTable`） | 同 1a，切页签不换 URL | 页签 | 采购申请管理 | 同上（`/hospital-procurement/api/plan-management/reserve-library`） |
| 1c | 新增/编辑采购申请 | `HospitalProcurement/view/procurementApply/edit.html` | L2 iframe `.../view/procurementApply/edit.html?v=20260916-product-handoff1` | HCUI.popDialog, area 96%×94%，标题“新增采购申请/编辑采购申请”，按钮“保存草稿/关闭” | 采购申请 | `procurementApplyApi.js`、`procurementStore.js` |
| 1d | 选择预算品目 | `HospitalProcurement/view/procurementApply/reserveSelect.html` | L3 iframe（从 edit.html 弹出） | popDialog，标题“选择预算计划/新增预算品目” | 新增预算品目 | `procurementApplyApi.js`、`procurementStore.js` |
| 1e | 计划外预算品目 | `HospitalProcurement/view/procurementApply/outsidePlanReserveEdit.html` | L3 iframe（edit.html 弹出） | popDialog | （无 title） | 同上 + `outsidePlanReserveEdit` 内联 |
| 1f | 采购申请详情 | `HospitalProcurement/view/procurementApply/view.html` | L2 iframe | popDialog，标题“采购申请详情”，按钮“关闭” | 采购申请详情 | 同上 |
| 2a | 分包管理（列表） | `HospitalProcurement/view/packageManagement/index.html`（0000006000002） | L1 | 菜单→L1 iframe | 分包管理 | `packageManagementApi.js`、`packageStore.js`、`index.js` |
| 2b | 采购分包（编辑/确认） | `HospitalProcurement/view/packageManagement/editor/index.html` | L2 iframe | popDialog（`#packageApplicationTable` 行内“分包/查看/确认”） | 采购分包 | `packageStore.js`、`packageManagementApi.js`、`editor/index.js` |
| 2c | 分包弹窗内“子包”表单 | `editor/index.html` 内 `#packageFormDialog`（layer type 1，页面内 DOM，不是 iframe） | L2 同页 | layer.open type 1 | — | `editor/index.js` |
| 3a | 市场调研-调研项目管理 | `HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html`（0000001000001，父 0000001 市场调研管理） | L1 | 菜单→L1 iframe | 调研项目管理 | `surveyProject/list.js` |
| 3b | 调研项目维护/编辑 | `.../surveyProject/edit.html` | L2 iframe（`?v=20261014-save-file`） | popDialog | 编辑调研项目 | 页面内联大脚本 + `common/qaMultiFile.js` |
| 3c | 调研公告编辑/发布 | `.../surveyProject/notice.html` | L2 iframe（`?v=20261012-extra1`） | popDialog | 调研公告 | 内联 + `qaMultiFile.js` + `template/templateCommonJs.js` |
| 3d | 查看/参与调研（供应商侧） | `.../surveyProject/participate.html`、`.../surveyProject/replies.html` | L2 iframe | popDialog | 参与调研 / 调研回复 | 内联 + `qaMultiFile.js` |
| 3e | 公告管理（旧版 PreProject 体系） | `.../announcementManage/list.html`（未在已抓取菜单中出现，菜单由角色/历史数据决定） | L1（若配置了菜单） | 菜单→L1 或 从调研项目进入 | 公告管理 | `announcementManage/js/list.js`、`RoleCodeCommon.js` |
| 3f | 公告新增/编辑 | `.../announcementManage/add.html`、`noEdit.html`、`tobeEdited.html`、`noEditView.html`、`uploadFileBySupplier.html` | L2 iframe | popDialog | （add.html 无 title） | 内联 + `js/mulView.js`、`requireBusiness/Qualification/Technical*.html` |
| 3g | 市场调研-调研结果管理 | `.../surveyResult/list.html`（0000001000006） | L1 | 菜单→L1 iframe | 调研结果管理 | `surveyResult/list.js`、`qaMultiFile.js` |
| 3h | 调研结果详情 / 资格性审查 / 主任审批 | `.../surveyResult/detail.html?uuid=<项目id>&mode=handle` | L2 iframe | popDialog（标题“调研结果”，见 `approvalCommon.openSurveyResultTask`） | 调研结果详情 | `surveyResult/detail.html` 内联脚本 |
| 3i | 市场调研-调研论证管理 | `.../surveyArgument/list.html`（0000001000007） | L1 | 菜单→L1 iframe | 调研论证管理 | `surveyArgument/list.js` |
| 3j | 规划专家抽取 | `.../surveyArgument/extract.html` | L2 iframe | popDialog | 规划专家抽取 | 内联 `#saveExtract` 等 |
| 3k | 勾选专家（人工） | `.../surveyArgument/pick.html` | L2 iframe | popDialog | 勾选专家 | 内联（`apiPrefix`） |
| 3l | 补抽专家 | `.../surveyArgument/makeup.html` | L2 iframe | popDialog | 补抽专家 | 内联 |
| 3m | 查看时间规划 | `.../surveyArgument/schedule.html` | L2 iframe | popDialog | 查看时间规划 | 内联 |
| 3n | 论证延期 | `.../surveyArgument/postpone.html` | L2 iframe | popDialog | 论证延期 | 内联 |
| 3o | 专家填写论证意见/投票 | `.../surveyArgument/fill.html` | L2 iframe | popDialog | 调研论证 | 内联 + `qaMultiFile.js` |
| 3p | 查看论证情况 | `.../surveyArgument/situation.html` | L2 iframe | popDialog | 查看论证情况 | 内联 |
| 3q | 论证报告编辑 | `.../surveyArgument/report.html` | L2 iframe | popDialog | 论证报告 | 内联 + `template/templateCommonJs.js` |
| 3r | 扫码签名（PC 端二维码） | `.../surveyArgument/reportSignatureQr.html` | L3 iframe（report.html 弹出） | popDialog | 扫码签名 | `reportSignatureQr.js` |
| 3s | 手机端手写签名 | `.../surveyArgument/reportSignatureScan.html?token=...` | 独立页（手机扫二维码） | 手机浏览器 | 论证报告签名 | `reportSignatureScan.js` |
| 3t | 上传论证结果 | `.../surveyArgument/result.html` | L2 iframe | popDialog | 上传论证结果 | 内联 + `qaMultiFile.js` |
| 3u | 确认最终采购需求 | `.../finalPurchaseRequire/list.html`（是否在菜单由角色决定） | L1 | 菜单→L1 | 确认最终采购需求 | `finalPurchaseRequire/list.js` |
| 4 | 采购需求在线编制（列表） | 菜单 url = `view/procurementRequirement/index.html`（0000006000005，无前导 `/`）→ `/HospitalProcurement/view/procurementRequirement/index.html` | L1 | 菜单→L1 iframe | 采购需求在线编制 | `compileStatus.js`、`procurementDocumentPersist.js`、`index.js` |
| 4a | 选择编制模板 | `.../procurementRequirement/chooseTemplate.html` | L2 iframe | popDialog | 选择编制模板 | `chooseTemplate.js` |
| 4b | 在线编制采购文件 | `.../procurementRequirement/editDocument.html` | L2 iframe | popDialog | 在线编制采购文件 | `editDocument.js` |
| 4c | OnlyOffice 编辑器 | `.../procurementRequirement/onlyofficeDocument.html` | L3 iframe（editDocument 弹出） | popDialog | （无 title） | `onlyofficeDocument.js`（`DocsAPI.DocEditor`） |
| 5 | 审计管理（HP 推送审计） | `/HospitalProcurement/view/auditManagement/index.html`（0000006000009） | L1 | 菜单→L1 iframe | 审计管理 | `auditManagementApi.js`、`index.js` |
| 5a | 审计详情（编辑内容/附件/生成报告/推送） | `/HospitalProcurement/view/auditManagement/detail.html` | L2 iframe | popDialog | 审计详情 | `detail.js` |
| 6 | 采购需求审查管理（列表） | `/HospitalProcurement/view/procurementRequirementReview/index.html`（0000006000008） | L1 | 菜单→L1 iframe | 采购需求审查管理 | `index.js` |
| 6a | 采购需求审查弹窗 | `/HospitalProcurement/view/procurementRequirementReview/review/index.html` | L2 iframe（`name="procurementRequirementReviewDialog"`，96%×94%） | popDialog | 采购需求审查 / 查看审查结论 | `review/index.js` |
| 7 | 采购方式分配（列表） | `/HospitalProcurement/view/procurementMethodConfirm/index.html`（0000006000003） | L1（页内有 `procurementMethodTabs` 两个页签：待分配 `candidateTable`/已分配 `recordTable`） | 菜单→L1 iframe | 采购方式分配 | `procurementMethodApi.js`、`procurementMethodStore.js`、`index.js` |
| 7a | 分配方式编辑页 | `/HospitalProcurement/view/procurementMethodConfirm/editor/index.html` | L2 iframe | popDialog | 采购方式分配 | `editor/index.js` |
| 8 | 采购执行申请管理（列表） | `/HospitalProcurement/view/executionApply/list.html`（0000006000004） | L1 | 菜单→L1 iframe | 采购执行申请管理 | `executionApplyApi.js`、`procurementStore.js`、`reserveStore.js`、页面内联 |
| 8a | 采购执行申请编辑 | `/HospitalProcurement/view/executionApply/edit.html` | L2 iframe，area 96%×94% | popDialog | 采购执行申请 | `executionApplyApi.js` + 内联 |
| 8b | 采购执行申请详情 | `/HospitalProcurement/view/executionApply/view.html` | L2 iframe | popDialog | 采购执行申请详情 | 同上 |
| 9 | 采购工作台 | `/HospitalProcurement/view/procurementWorkbench/index.html`（M000005，父 0） | L1；工作台内部再嵌 `#pwb-module-frames` 模块 iframe（`modules/taskCenter/index.html` 等） | 菜单→L1 iframe | 采购工作台 | `index.js`、`config/runtimeConfig.js`、`common/frameManager.js`、各 module |
| 9a | 待办/已办/办结（工作台内） | `/HospitalProcurement/view/businessApproval/personal/todoTaskList.html` 等 | L3 iframe（工作台 taskCenter 的 `#pwb-task-frames` 再嵌） | 工作台页签 | 个人待办/个人已办/个人办结 | `todoTaskList.js`、`completedTaskList.js`、`finishedTaskList.js` |
| 9b | 业务审批-个人待办 | 菜单 603 → `view/businessApproval/personal/todoTaskList.html` | L1 | 菜单→L1 iframe | 个人待办 | `approvalCommon.js`、`businessTypeUtil.js`、`todoTaskList.js` |
| 9c | 业务审批-科室待办 | 菜单 602 → `view/businessApproval/department/todoTaskList.html` | L1 | 菜单→L1 iframe | 科室待办 | `department/todoTaskList.js` |
| 9d | 业务审批-个人已办/办结 | 菜单 604/605 → `personal/completedTaskList.html` / `finishedTaskList.html` | L1 | 菜单→L1 iframe | 个人已办 / 个人办结 | 对应 js |
| 9e | 审批办理页 | 菜单 603 行内“办理”→ `view/businessApproval/personal/toCompletePage.html` | L2 iframe（1200px×90%） | popDialog（title“任务办理--[流程名]”，btn“提交/返回”） | 审核页面 | `toCompletePage.js`、`businessDataModel/Renderer.js`、`approvalScanSign.js` |
| 9f | 查看审批信息/综合查询 | 菜单 606/607 → `view/businessApproval/commonQuery/queryList.html[?type=agency]` | L1 | 菜单→L1 iframe | 综合查询 | `queryList.js` |
| 10a | 纪检-首页/壳 | `/DisciplineInspection/index.html`（菜单 0000063，父 0） | L0'（独立外壳） | 菜单→新平台壳 | 纪检监察平台 | `index.js`（本地注入审计菜单 `appendAuditMenus`） |
| 10b | 纪检-监察项目列表（分配监督员） | `/DisciplineInspection/view/projectList/index.html`（0000063000001） | L1' `/DisciplineInspection/index.html` 的 iframe | 菜单→L1' iframe | 监察项目列表 | `projectList/index.js` |
| 10c | 纪检-监督员管理 | `/DisciplineInspection/view/supervisorManage/index.html`（0000063000003） | L1' | 菜单→L1' iframe | 监督员管理 | `supervisorManage/index.js` |
| 10d | 纪检-采购专项审计 | `/DisciplineInspection/view/purchaseAudit/index.html`（M000007000001，父 M000007 审计管理） | L1' | 菜单→L1' iframe | 采购专项审计 | `purchaseAuditApi.js`、`index.js` |
| 10e | 纪检-审计详情/审理/报告编辑 | `/DisciplineInspection/view/purchaseAudit/detail.html`、`review.html`、`reportEditor.html`、`onlyofficePreview.html` | L2' iframe | popDialog | 采购专项审计详情 / 审理采购专项审计 | `detail.js`、`review.js` |
| 10f | 纪检-其他项目审计 | `/DisciplineInspection/view/otherAudit/index.html`（M000007000002） | L1' | 菜单→L1' iframe | 其他项目审计 | `otherAudit/index.js` |
| 10g | 纪检-审计报告模板管理 | `/DisciplineInspection/view/purchaseAuditTemplate/index.html`（M000007000003） | L1' | 菜单→L1' iframe | 审计报告模板管理 | `purchaseAuditTemplateApi.js`、`index.js` |
| 10h | 纪检-申请单列表/全流程详情 | `/DisciplineInspection/view/projectTrackingList/index.html`（0000047000001）、`/view/projectTrackingSingle/index.html`（0000047000002“全流程详情”） | L1' | 菜单→L1' iframe | 申请单列表 / 全流程详情 | `projectTrackingApi.js`、`index.js` |
| 10i | 纪检-统计汇总与下载 | `/DisciplineInspection/view/auditSummary/index.html`（前端本地注入，非后端菜单） | L1' | 菜单（前端注入） | （auditSummary） | `auditSummary/index.js` |

**关于“分包管理新旧版本”**：HP 目录只有 `view/packageManagement/index.html`（新版列表）+ `editor/index.html`（弹窗编辑），**没有独立旧版子目录**；菜单 `0000006000002` 指向新版 `index.html`。历史上同类“申请→分包→确认”实现在 `view/productLibrary/priceUnreasonable/package/`、`view/sporadicPurchase/package/`、`view/emergencyPurchase/package/`（均含 `index.html`+`editor/index.html`，结构与新版一致），若手册里的“旧版”指向这些，请按第 5 节角色菜单确认入口。

**关于“党政/纪检平台判断”**：
- 纪检监察平台是**独立前端** `/DisciplineInspection/`（有独立 `index.html`/`index.js`/`menu.css`/`components`，但复用 `/HospitalProcurement/components/zhongMenu/`）。菜单 0000063 → `/DisciplineInspection/index.html`。
- HP 内 `view/disciplineInspection/index.html` 只是 462 字节跳转页：`location.replace("/DisciplineInspection/index.html"+search+hash)`；HP 根目录还有个历史遗留壳 `HospitalProcurement/disciplineInspection.html`（title 仍是“采购交易系统”，不要用）。
- 审计员/主任审批在纪检平台：`DisciplineInspection/view/purchaseAudit/detail.html`（通过/驳回）与 `review.html`（提交主任审批）。HP 的 `auditManagement` 只是“采购人推送审计给审计员”的列表页。

---

## 2. 选择器 / 控件清单（重点）

### 2.0 通用规则（先读，后面不再重复）

| 事项 | 事实 | Playwright 建议 |
|---|---|---|
| 表格组件 | `HCUI.datagrid` = Layui table 封装（`elem/id/url/cols/page/limit/where/response.fillter`），`HCUI.datagrid.initOrRefresh(option, ins)` / `.curPageReload(ins)` 是静态方法 | 等 `.layui-table-view` 出现且 `.layui-table-main tbody tr` 有行；不要等“loading 消失” |
| 操作列 | 页面用 formatter 拼 `<button class="layui-btn layui-btn-mini" lay-event="view">查看</button>`（部分用 `<a ...>`） | `row.locator('[lay-event="view"]')`；禁用态是 `lay-event="blockedEdit"` 且 `aria-disabled=true` |
| 事件分发 | `layui.table.on("tool(<lay-filter>)", handler)`，`obj.event` 即 `lay-event` | 直接点行内 `[lay-event]` 元素即可触发 |
| 固定列 | `fixed:"left"/"right"` 的列会生成 `.layui-table-fixed-l/.layui-table-fixed-r` 的**副本 DOM** | 断言/点击统一 `.layui-table-main` 内定位；若必须点固定列，限定 `.layui-table-fixed-r` |
| 表单字段 | 用 `idName="xxx"`（不是 `name`），`appCommon.formUtil.getParamByIdName("#formId")` 读值 | `[idname="xxx"]`；输入后需 `form.render()` 的页面（layui select/日期）不要只 `fill` |
| Layui 下拉 | `<select lay-filter=...>` 被 Layui 重绘为 `.layui-form-select`，原生 select 被隐藏 | 先 `click('.layui-form-select')`，再点 `.layui-form-select dd[lay-value="x"]`；或 `selectOption(...,{force:true})` 后再 dispatch change |
| 日期 | `HCUI.datePicker`/laydate：input 点击弹 `.layui-laydate` | `click(input)` → `.layui-laydate td[lay-ymd="..."]` → `click(.layui-laydate .laydate-btns-confirm)`；也可直接 fill 后 blur（部分页面校验格式） |
| 弹窗 | 默认 `type:2` iframe 且 **layer 在 top 窗口**；内容页 URL 在 iframe.src | `page.locator('.layui-layer-iframe iframe[src*="..."]')` → `frameLocator` → 操作；按钮 `.layui-layer-btn0` |
| 按钮确认 | 危险/提交类均有 `HCUI.popDialog.confirm`/`msg` 的 layer 提示 | 处理 `page.on('dialog')` 不够（不是原生 alert），要点 `.layui-layer-dialog .layui-layer-btn0` |
| Loading | `appCommon.otherUtil.ajaxFunction` 默认在 top 窗口 `layer.load(1,{time:20000})` | 用“表格行/目标元素出现”做等待条件，不要用 networkidle（轮询/长连接多） |

### 2.1 外壳页 `/HospitalProcurement/index.html`

- 菜单容器：`#menu`（`zhongMenu` 初始化），菜单节点 DOM（由 `components/zhongMenu/zhongMenu.js` 渲染）：
  - 一级：`<li level="level_0"><div node="node" node-text="采购管理" node-id="0000006" url="">…`
  - 二级可点击叶子：`<a node="node" node-text="采购申请管理" node-id="0000006000001" url="/HospitalProcurement/view/procurementApply/list.html" onClick="zhongMenuClickNode(this)">`
  - 定位示例：`page.locator('#menu a[node-text="采购申请管理"]')`、`page.locator('#menu [node-id="0000006000001"]')`。
- 页签：`#mainTab`；当前页 `#mainTab .layui-tab-title li.layui-this`（隐藏但存在）；页签 id：`#mainTab .layui-tab-title li[lay-id="0000006000001"]`。
- 业务 iframe：`iframe.mainIframe`，`attr('src')` = 菜单 url（相对/绝对），`attr('name')` = 菜单名。
- 顶栏：`#system_username`（用户名，`title` 存 legalName）；切平台 `div.switch[onclick="changePlatform()"]`（文本“切换平台”）；改密 `div.changeSecret[onclick="showUpdatePsd()"]`；退出 `div.quit[onclick="loginOut()"]`。
- 菜单加载：`GET ../../nodeJs/menu_Json`（实际 `/nodeJs/menu_Json`，GET JSON）。失败时 `layer.msg("登录已超时，请重新登录")` 3 秒后跳 `/Register/public/newLogin/user_login_2.html`。成功时 `content` 是数组，每项字段 `{id,parentId,url,iconCls,menu_name,level,sort}`。
- 工作台菜单本地兜底：`filterProductLibraryMenus()` 对 `NGP_SUPPLIER` 删除 6 个产品库菜单（见 index.html 第 450-470 行）。

### 2.2 采购申请管理 `/HospitalProcurement/view/procurementApply/list.html`

**页签**（`lay-filter="procurementWorkspaceTabs"`，无 `lay-id` 之外的 id）：

- `#mainTab` 内的 L1 iframe → `.procurement-workspace-tabs .layui-tab-title li[lay-id="launch"]`（发起采购申请，默认激活）
- `.layui-tab-title li[lay-id="applications"]`（申请单管理）
- 内容：`.procurement-workspace-content .layui-tab-item`（第 0 个=launch，第 1 个=applications）
- 特殊角色 `REQ_STAFF`：`__init` 会隐藏 launch 页签、强制显示 applications 和 `#outsidePlanLaunchBar`（发起计划外采购）。

**发起采购页签（launch）**

| 控件 | 选择器 | 说明 |
|---|---|---|
| 搜索表单 | `#reserveLaunchSearch[lay-filter="reserveLaunchSearch"]` | 字段 `[idname="budgetCode"]`、`[idname="projectName"]`、`[idname="year"]`、`[idname="attributeType"]`、`[idname="status"]`（未执行/执行中/已完成）、`[idname="ownerDepartment"]` |
| 搜索/重置 | `#launchSearchBtn`、`#launchResetBtn` | 均 `type=button` |
| 组合发起 | `#combineLaunchBtn`（disabled 直到选中 ≥2 条同规则预算） | 规则文案在 `.launch-selection-rule` |
| 清空选择 | `#clearLaunchSelectionBtn` | |
| 选中统计 | `#launchSelectedCount`、`#launchSelectedAmount`、`#launchLockedType`、`#launchLockedGov`、`#launchLockedSme` | 断言用 |
| 表格 | `table#reserveLaunchTable[lay-filter="reserveLaunchTableIndex"]` | 行复选框：`.launch-reserve-checkbox`（`$(document).on("change")`） |
| 计划外发起 | `#outsidePlanLaunchBar`（默认隐藏）内 `#outsidePlanLaunchBtn`（文本“发起采购”） | 仅 `REQ_STAFF` 显示 |
| 页签计数 | `#launchTabCount`、`#applicationTabCount` | |

**申请单管理页签（applications）**

| 控件 | 选择器 |
|---|---|
| 搜索表单 | `#applicationSearchBar[lay-filter="applicationSearch"]`；字段 `[idname="requestCode"]`、`[idname="requestName"]`、`[idname="status"]`（0 草稿/1 审批中/2 已驳回待修改/3 审批通过待承办/4 已取消作废/5 采购执行完成/6 已修改待重申/7 待调研/8 待分包/15 待编制采购需求文件/16 编制文件审批中/17 待审计/18 采购需求审查中/19 待审查与方式分配/10 待分配采购方式/11 待发起采购执行/22 待分配监督员） |
| 按钮 | `#applicationSearchBtn`、`#applicationResetBtn` |
| 表格 | `table#applicationTable[lay-filter="applicationTableIndex"]`；`cols` 见 list.html 288-304 行 |
| 状态列 | `format: statusFormatter` → `ProcurementApplyApi.statusLabel(status,row)`，注意 status=7 时显示的是 `surveyState` 文案 |
| 操作列 | `field:"handle", title:"操作", fixed:"right", width:320, formatter: applicationOperationFormatter` |
| 行内按钮 | 普通行：`[lay-event="view"]查看`、`[lay-event="edit"]编辑`、`[lay-event="deleteDraft"]删除草稿`、`[lay-event="confirm"]确认` 或 `[lay-event="submitAudit"]提交审批`；未选中预算时的行：`[lay-event="singleLaunch"]单独发起` |
| 阻塞态 | `[lay-event="blockedEdit"]`、`blockedConfirm`、`blockedDeleteDraft`、`blockedSubmitAudit`、`blockedSingleLaunch`（`aria-disabled="true"`） |
| 全表懒渲染 | 首次切到该页签才 `HCUI.datagrid(applicationTableOption())`；`refreshApplicationTableLayout` 最多重试 8×50ms |

**新增/编辑弹窗 `/view/procurementApply/edit.html`（L2）**

| 控件 | 选择器 |
|---|---|
| 表单 | `#applicationForm[lay-filter="applicationForm"]`（container `.layui-form hcLayout`） |
| 字段 | `[idname="projectName"]`（采购申请名称）、`[idname="attributeType"]`（项目属性）、`[idname="projectAttribute"]`、`[idname="requestDepartment"]`、`[idname="applicationReason"]`、`[idname="purchaseContent"]`、`[idname="code"]`（申请编号，只读）、`#attributeType`（项目类型 select）、`#selectedCount`、`#selectedAmount` |
| 预算明细表 | `#selectedReserveTable[lay-filter="selectedReserveTableIndex"]`；行内 `[lay-event="editReserve"]编辑`、`[lay-event="remove"]删除`、`[lay-event="blockedRemove"]删除(禁用)` |
| 新增预算计划 | `#addReserveBtn` → 打开 `reserveSelect.html` |
| 计划外新增 | `#addReserveBtn` 之外有“计划外新增预算计划”入口（`outsidePlanReserveEdit.html`，见 edit.html 490 行 popDialog） |
| 附件 | 容器 `#applicationAttachmentUploader`（WebUploader 根），选文件按钮 `#applicationAttachmentFilePicker`，列表 `#applicationAttachmentTable`，表体 `#applicationAttachmentBody`；`uploaderInit({uploaderId:"applicationAttachmentUploader",filePicker:"applicationAttachmentFilePicker",...})` |
| 驳回信息 | `#rejectInfoSection`、`#rejectReason`、`#rejectUserName` |
| 修复属性 | `#repairAttributeFields`、`[idname="repairEquipmentCode"]`、`[idname="repairEquipmentModel"]`、`[idname="repairManufacturer"]`、`[idname="repairOriginalValue"]` |
| 弹窗按钮 | 父层 `.layui-layer-btn0` = “保存草稿”（父页 list.html 的 `btn:["保存草稿","关闭"]`） |

**预算品目选择弹窗 `/view/procurementApply/reserveSelect.html`（L3）**

- 搜索：`#reserveSelectorSearch[lay-filter="reserveSelectorSearch"]`，字段 `[idname="budgetCode"]`、`[idname="projectName"]`；按钮 `#reserveSelectorSearchBtn`、`#reserveSelectorResetBtn`
- 表格：`#reserveSelectorTable[lay-filter="reserveSelectorTableIndex"]`
- 已选统计：`#selectorSelectedCount`、`#selectorGovText`、`#selectorTypeText`、`#lockedProjectType`
- 勾选：行复选框 `input[type="checkbox"][lay-filter]` 或 `input[name="..."]`（页面内联，建议 `.layui-table-main input[type=checkbox]`）

**详情 `/view/procurementApply/view.html`**：`#projectName/#code/#status/#requestDepartment/#attributeType/#projectAttribute/#applicationReason/#purchaseContent/#applicant/#itemCount/#totalAmount/#totalBudgetAmount`，`#viewReserveTable[lay-filter="viewReserveTableIndex"]`，附件 `#applicationAttachmentTable/#applicationAttachmentBody`，驳回 `#rejectInfoSection`，修复明细 `#repairDetailSection`。

### 2.3 分包管理 `/HospitalProcurement/view/packageManagement/index.html`

- 搜索：`#packageSearchForm[lay-filter="packageSearchForm"]`；字段 `[idname="requestCode"]`、`[idname="requestName"]`、`[idname="subpackageStatus"]`（1 已分包 / 0 未分包，`lay-filter="packageSubpackageStatusFilter"`）
- 按钮：`#packageSearchBtn`、`#packageResetBtn`、`#packageSyncSurveyBtn`（“同步历史调研项目”，`display:none`，仅开发/特定条件出现）
- 表格：`table#packageApplicationTable[lay-filter="packageApplicationTableIndex"]`
- 操作列：`查看 [lay-event="view"]`、`分包 [lay-event="edit"]`、`确认 [lay-event="confirm"]`；禁用态 `blockedView/blockedEdit/blockedConfirm`（`visual-disabled`）
- 弹窗：`HCUI.popDialog({name:"packageEditor",content:".../packageManagement/editor/index.html"})`（见 index.js 160 行）

**分包编辑 `/view/packageManagement/editor/index.html`（L2，不是 iframe 内再 iframe 的弹窗）**

- 基本信息（只读文本）：`#applicationCode`、`#packageStatus`、`#projectName`、`#projectAttribute`、`#projectType`、`#demandDepartment`、`#applicant`、`#applyDate`、`#reserveItemCount`、`#applicationAmount`
- 预算计划工作区：`#budgetItemWorkspace`（拖拽/勾选分配）；子包工作区：`#packageWorkspace`
- 汇总：`#summaryApplicationAmount`、`#summaryPackageAmount`、`#summaryUnassignedAmount`
- 附件表：`#attachmentRows`
- 操作：`#confirmBtn`（确认）、`#closeBtn`（关闭）
- 子包表单弹窗：`#packageFormDialog`（layer type 1 打开的**页面内 DOM**，不是 iframe）：`#dialogPackageCode`（只读）、`#dialogPackageName`、`#dialogItemOptions`（预算多选）、`#dialogPackageAmount`（只读）、`#dialogQuoteForm`（报价方式）、`#dialogGovSection`（政采字段区）、`#dialogBidEvaluationForm`、`#dialogValidityOfBid`、`#dialogSupplyPeriod`、`#dialogSupplyPeriodLabel`、`#dialogPackageReason`、`#dialogBudgetTip`
- layer type 1 的弹层（`layer.open`，见 editor/index.js 371 行）容器在**该 iframe 自身文档或 top**（依 layer 实现而定，自动化时应同时兼容：先在本 frame 找 `.layui-layer`，找不到再在 page 顶文档找）

### 2.4 市场调研模块 `view/hospitalProcurement/marketResearchManage/`

三个列表页结构相同：`#searchBar[lay-filter="formDemo"]`、`#doSearch`、`#resetBtn`、`table#hcGrid[lay-filter="tableIndex"]`，操作列都走 `layui.table.on('tool(tableIndex)')`。

**调研项目 list.html**：字段 `[idname="projectName"]`、`[idname="projectCode"]`、`[idname="bussinessType"]`（D01 货物/D02 工程/D03 服务）、`[idname="state"]`（1 待调研/2 调研中/3 待发布调研公告/4 待完善论证信息/5 论证中/6 论证完成/7 待论证/8 专家未抽齐/9 论证逾期/10 待部门主任审批/11 待部门干事审批/12 待干事重新发起调研）。
操作按钮（`surveyProject/list.js`）：`[lay-event="edit"]`（草稿时“完善信息”，其它“编辑”）、`[lay-event="editNotice"]`（编辑公告）、`[lay-event="viewNotice"]`（查看公告/查看调研公告）、`[lay-event="participate"]`（参与调研）、`[lay-event="viewReply"]`（查看提交调研资料）、`[lay-event="publishNow"]`（立即发布调研公告）、`[lay-event="downloadNoticePack"]`（下载公告及附件，直接 `location.href`）、`[lay-event="view"]`（查看调研项目）。
弹窗内容（`list.js` 546/565/577/601/628 行）：`edit.html?v=20261014-save-file`、`notice.html?v=20261012-extra1`、`participate.html?v=20261102-notpl1`。

**调研项目编辑 `surveyProject/edit.html`（L2）**
- 表单：`[lay-filter="formDemo"]`；字段 `[idname="projectName"]`、`[idname="projectCode"]`、`[idname="bussinessType"]`、`[idname="projectBudget"]`、`[idname="purchaseDept"]`、`[idname="startTime"]`、`[idname="endTime"]`、`[idname="handler"]`、`[idname="handlerPhone"]`、`[idname="projectSummary"]`；下拉/只读回显 `#bussinessType/#bussinessTypeName/#startTime/#endTime/#purchaseDept/#handlerPhone`
- 其它调研附件：`#otherSurveyUploader`+`#otherSurveyUploadBtn`+`#otherSurveySelect`+`#otherSurveyList/#otherSurveyViewList`、`[idname="otherSurveyAttachmentIds"]`、`[idname="otherSurveyAttachmentNames"]`
- 技术参数表：`#techTable`、`#techTableBody`、`#techEmptyHint`；按钮 `#btnAddTechRow`（新增）、`#btnTechDelSelected`（删除选中）、`#btnTechImport`（导入）、`#btnTechDownload`（下载模板）、`#btnTechUseTpl`（选用模板）
- 子包表：`#subpackageTable`
- Excel 导入子页：`indexUpload.html`（`parseIndexExcel`）、`techUpload.html`（`parseTechExcel`）、`downloadTechTemplate`

**调研公告 `surveyProject/notice.html`（L2）**：`[idname="bullentTitle"]`、`[idname="bullentContent"]`、`[idname="attachmentIds"]`、`[idname="attachmentNames"]`、`#attachmentIds/#attachmentNames`、`#noticeFileUploader/#noticeFileUploadBtn/#noticeFileSelect`、`#noticeFileList/#noticeFileViewList`、`#importTemplate`（选择模板）、`#templateBtnWrap`、`#bullentContent`（ueditor iframe，富文本编辑器在 `iframe` 内，Playwright 需 `frameLocator('.edui iframe')` 或 `#bullentContent` 对应 contenteditable）

**调研结果 list.html**：`[idname="projectName"]`、`[idname="projectCode"]`、`[idname="state"]`；按钮文本（`surveyResult/list.js`）：`[lay-event="viewResult"]`（查看结果）、`[lay-event="viewSurvey"]`（查看调研情况）、`[lay-event="viewReview"]`（查看评审信息）、`[lay-event="viewReply"]`（评审响应材料）、`[lay-event="downloadQcc"]`（下载背调报告）、`[lay-event="downloadTechSpec"]`（导出技术参数表）、`[lay-event="qccPending"]`（背调生成中）。

**调研结果详情 `surveyResult/detail.html?uuid=<id>&mode=handle|view`（L2）**：`#projectMeta`、`#supplierHead`、`#supplierName`、`#supplierBadge`、`#supplierPane`、`#supplierProfileSection/#supplierProfileGrid`、`#techSpecWrap`、`#fileList`、`#roundSelect`、`#roundSummary`、`#specialRemarkBox`、`#remarkHint`、`#rejectSection/#rejectSectionTitle/#rejectReasonBox`、`#auditBtns`、`#pickSurveyDirectorSelect`、`#directorHint`、`#btnPass`（通过）、`#btnReject`（不通过）、`#btnOverturn`（反驳通过）→ `#btnOverturnConfirm`、`#btnSubmitDirector`（提交主任审批）、`#btnDirectorPassAll`（一键通过）、`#btnDirectorFinish`、`#btnRelaunch`（重新发起调研）、`#btnQccReport`/`#btnQccDownload`。
> 注意：该页从审批中心进入时是 `openSurveyResultTask`（`approvalCommon.js`），`mode=view` 隐藏操作按钮；`mode=handle` 才可审批。

**调研论证 list.html**：`[idname="projectName"]`、`[idname="projectCode"]`、`[idname="state"]`（4/7/8/5/9/6）；状态列含“抽取状态/抽取进度/评审状态/论证方式/论证地点/论证时间/论证延期/扫码签名/查看论证情况/查看时间规划”等；按钮事件（`surveyArgument/list.js` 474-571 行）：`schedule`（查看时间规划/查看时间地点）、`extract`（规划抽取/重新规划）、`pick`（勾选专家）、`progress`（抽取进度）、`situation`（查看论证情况）、`postpone`（延期）、`report`（编制报告）、`result`（上传论证结果）、`sign`（扫码签名）等（具体可用文案以接口返回状态为准，建议优先用 `[lay-event]`）。

**论证各子页关键控件**

| 页面 | 关键 id / 属性 | 主要动作 |
|---|---|---|
| extract.html（规划专家抽取） | `#projectName`、`[lay-filter="extractForm"]`、`name="extractMode"/"argumentMode"/"leaderSelectMode"`、`#addCond`、`#condBody`、`#evaluateExpertNumber`、`#extractStartTime`、`#extractEndTime`、`#voteStartTime`、`#voteEndTime`、`#gatherTime`、`#gatherPlace`、`#gatherEndTime`、`#gapEditor`、`#leaderVoteOption`、`#saveExtract`（保存并抽取）、`#refreshProgress`、`#cancelExtract`、`#confirmedBanner`、`#filledBlock/#filledBody` | 新增专业、保存并抽取、刷新进度 |
| pick.html（勾选专家） | `#projectName`、`#specialtyCode`、`#specialtyBoardBody`、`#candBody`、`name="cand"`、`#pickedCount`、`#statPending/#statConfirmed/#statDeclined/#statRemainTime`、`#pageInfo`、`#prevPage/#nextPage`、`#addSpecialty`、`#newSpecialtyCode/#newSpecialtyCount/#newSpecialtySearch/#newSpecialtySuggest`、`#changeSpecialtyBox`、`#confirmedList`、`#savePick`（提交并打电话）、`#cancelPick` | 勾选专家→提交 |
| makeup.html | `apiPrefix+/listMakeupCandidates`、`/saveMakeupExperts` | 补抽专家 |
| schedule.html | `#projectName`、`#extractStartTime/#extractEndTime`、`#voteStartTime/#voteEndTime`、`#gatherTime/#gatherPlace/#gatherEndTime`、`#extractProgress`、`#currentWindow`、`#leaderModeText`、`#closeSchedule` | 只读查看 |
| postpone.html | `#reason`、`#extractStartTime/#extractEndTime`、`#voteStartTime/#voteEndTime`、`#gatherTime/#gatherEndTime`、`#savePostpone`（确认延期）、`#cancelPostpone` | 延期 |
| fill.html | `#projectName`、`#fileTabs/#fileStage/#fileSupplierName`、`#expertBox/#expertHd`、`#indexCard/#indexTypes/#indexPaneHd/#idxPrev/#idxNext/#idxOpinion`、`#passRow`、`#votePanel/#voteCandidates`、`name="leaderVote"`、`#saveOpinions`、`#saveVote`、`#confirmSubmit`（确定提交）、`#backToFill`（返回修改）、`#openOverview/#overviewPanel/#overviewBody/#overviewSum`、`#downloadFile`、`#closeFill` | 专家逐项意见+投票 |
| situation.html | `#projectName`、`#supTabs`、`#matrixBox/#matrixTitle/#matrixWrap`、`#tallyBox/#tallyTitle/#tallyWrap`、`#doneBox/#doneCount`、`#todoBox/#todoCount`、`#closeSit`；行内“设为组长”按钮 | 查看/指定组长 |
| report.html | `[lay-filter="reportForm"]`、`[idname="argumentContent"]`/`name="argumentContent"`、`#argumentView/#argumentEditWrap/#argumentContent`、`#templateBtnWrap/#importTemplate`（选择模板）、`#saveDraft`、`#submitReport`、`#downloadReport`（导出 Word）、`#openSignQr`、`#signPanel/#signQrImage/#signState/#signCountdown/#refreshSignQr`、`#pendingSignHint`、`#closeReport` | 选模板→编辑→保存/提交/扫码签名 |
| result.html | `#projectName`、`#resultMetaCode/#resultMetaLeader`、`#resultFileUploader/#resultFileUploadBtn/#resultFileSelect/#resultFileList/#resultFileViewList`、`[idname="attachmentIds"]`、`[idname="attachmentNames"]`、同名隐藏域 `#attachmentIds/#attachmentNames`、`#otherFileUploader/#otherFileUploadBtn/#otherFileSelect/#otherFileList/#otherFileViewList`、`[idname="otherAttachmentIds"]`、`#saveDraft`（暂存）、`#submitResult`（提交并完成论证）、`#downloadPack`（过程材料导出）、`#cancelResult` | 上传结果并提交 |
| reportSignatureQr.html | `#projectName`、`#signStatus`、`#signProgress`、`#signQrImage`（img）、`#signCountdown`、`#refreshSignQr`、`#closeSignQr` | 生成二维码等待手机签名（轮询 3s） |
| reportSignatureScan.html | `#canvas`、`#status`、`#name`、`#clear`、`#ok`；URL 参数 `token` | 手机端手写签名 |

**公告管理（旧 PreProject 体系）** `announcementManage/list.html`：`#searchBar`、`[idname="projectName"]`、`[idname="bussinessType"]`、`[idname="purchaseWay"]`、`[idname="bullentType"]`、`#doSearch`、`#resetBtn`、`#addBtn`（新建）、`#import`（导入采购计划信息）、`table#hcGrid[lay-filter="tableIndex"]`；操作事件 `edit/editNotice/editParameter/editParams/participate/view/viewNotice/viewParams/uploadFileBySupplier/delete`。弹窗 `add.html`、`tobeEdited.html`、`noEdit.html`、`noEditView.html`、`uploadFileBySupplier.html`。

**确认最终采购需求** `finalPurchaseRequire/list.html`：`#searchBar`、`[idname="projectName"]`、`[idname="bussinessType"]`、`[idname="purchaseWay"]`、`[idname="bullentType"]`、`#doSearch/#resetBtn/#hcGrid[lay-filter="tableIndex"]`；行内 `[lay-event="confirm"]确认`、`[lay-event="view"]查看参数`。

### 2.5 采购需求在线编制 `/HospitalProcurement/view/procurementRequirement/`

**列表 index.html**：`#requirementSearchForm[lay-filter="requirementSearchForm"]`、`[idname="requestCode"]`、`[idname="requestName"]`、`[idname="status"]`（DRAFT/AUDIT_PENDING/SECOND_CONFIRMATION/AUDIT_REJECTED/APPROVING/APPROVED/REJECTED）、`#requirementSearchBtn/#requirementResetBtn`、`table#requirementApplicationTable[lay-filter="requirementApplicationTableIndex"]`；操作列：`[lay-event="view"]查看`、`[lay-event="edit"]编辑`、`[lay-event="submit"]确认并推送主任/重新推送主任/推送审计`、`[lay-event="download"]下载`；阻塞 `blockedSubmit/blockedEdit/...`。
弹窗：`chooseTemplate.html`（标题“选择编制模板”）、`editDocument.html`（编辑页）。

**编辑页 editDocument.html**：只读信息 `#applicationCode/#applicationName/#applicationApplicant/#applicationDepartment/#applicationProjectType/#applicationProjectAttribute/#applicationBudget/#applicationGovernmentProcurement`、`#documentTitle/#documentStatus/#documentStatusDetail/#workbenchTip`、`#documentWorkbench`、`#projectFilesSection/#projectFilesTableBody`、`#subpackagesSection/#subpackagesTableBody`、`#surveyProcessPackSection/#surveyProcessPackTableBody`、`#documentFileRows`、按钮 `#submitDocumentBtn`（推送审计）、`#closeDocumentBtn`（关闭）。
**模板选择 chooseTemplate.html**：`#templateList`、`#templateEmpty`；两个 tab 文案“采购需求书模板/采购实施计划模板”。
**OnlyOffice onlyofficeDocument.html**：`#onlyoffice-editor`、`#onlyofficeLoading`、`#onlyofficeError`；`window.DocsAPI.DocEditor` 实例（需 onlyoffice 文档服务可用）。

### 2.6 审计管理 `/HospitalProcurement/view/auditManagement/`

**列表 index.html**：`#auditSearchForm[lay-filter="auditSearchForm"]`、`[idname="projectName"]`、`[idname="auditStatus"]`（0 待推送/1 审计中/2 已通过/3 被退回）、`#auditSearchBtn`（查询）、`#auditResetBtn`、`#auditEmptyTip`、`table#auditTable[lay-filter="auditTableIndex"]`。
操作列（index.js 54 行映射）：`[lay-event="查看"]`、`[lay-event="推送审计"]`、`[lay-event="编辑"]`、`[lay-event="补充相关材料"]`、`[lay-event="发起采购执行申请"]`（注意：lay-event 是**中文标签本身**，不是英文 event 名，`esc(name)` 后直接放进 `lay-event`；自动化优先按 `lay-event` 精确值或按钮文本）。
推送弹窗含“选择审计员” `[idname/…]`、`#auditFileInput` 等（详见 detail 页）。

**详情 detail.html**：只读 `#auditCode/#requestCode/#requestName/#applicant/#requestDepartment/#applicationReason/#projectType/#projectAttribute/#projectAttributeRemark(#projectAttributeRemarkRow)/#purchaseContent/#reportBudget/#approvedBudget/#governmentProcurement/#handler/#auditStatusName/#auditorRow/#auditorCell`；`#subpackageWorkspace`；`#auditOpinion`（审计意见输入）；附件 `#fileRows`、`#fileEditToolbar`、`#auditUploadBtn`（上传关联文件）、原生 `input type=file#auditFileInput`（change 即上传，支持多选）；`#generateReportBtn`（生成审计报告，`display:none` 视状态）；“获取调研论证过程材料”按钮。

### 2.7 采购需求审查 `/HospitalProcurement/view/procurementRequirementReview/`

**列表 index.html**：`#reviewSearchForm[lay-filter="reviewSearchForm"]`、`[idname="requestCode"]`、`[idname="requestName"]`、`[idname="reviewStatus"]`、`[idname="reviewType"]`、`#reviewSearchBtn/#reviewResetBtn`、`#reviewListMode`、`#reviewPageRole`、`#reviewStatusFilterWrap`、`#reviewTypeFilterWrap`、`table#reviewApplicationTable[lay-filter="reviewApplicationTableIndex"]`。
操作列按钮：`[lay-event="review"]前加签审查`、`[lay-event="startReview"]审查/查看审查结论`、`[lay-event="viewConclusion"]查看审查结论`、`[lay-event="preSign"]前加签`。
“选择前加签干事”弹窗：`.pre-sign-reviewers` 列表（`#109` 行 `preSignOptions`）。
审查弹窗：`HCUI.popDialog({name:"procurementRequirementReviewDialog",content:".../review/index.html",area:["96%","94%"]})`。

**审查弹窗 review/index.html**：`#documentTitle`、`#documentFileName`、`#documentDownloadLink`、`#documentPreviewButton`（预览）、`#documentEditButton`（编辑）、`#documentEditBar`、`#documentEditState`、`#documentPreview`、`#documentFileFrame`、`#documentContextName`、`#documentContext`、`#documentCopyHeading/#documentCopyText`、`#documentSecondHeading/#documentSecondText`、`#documentSectionTitle`、`#previewApplicationCode/#previewProjectName/#previewProjectType`、`#reviewTypeTabs`（采购需求书/采购实施计划 + 一般性审查/重点审查）、`#reviewQuestionList`、`#reviewQuestionTitle`、`#questionProgress`、`#reviewOpinionGeneral/#reviewOpinionKey`、`#approveAllButtonGeneral/#approveAllButtonKey`（一键通过）、`#saveReviewButtonGeneral/#saveReviewButtonKey`、`#saveDocumentButton`、`#closeDialogButton`、`#conclusionBar/#conclusionText`、`#readOnlyMark`、`#reviewDialogTitle`。
审查问题 radio：`input[value="passed"]` / `input[value="failed"]`（见 tests/pageStructure.test.js），通过时默认意见文本 `DEFAULT_REVIEW_TEXT="通过"`。
> 该弹窗内容页仍可能再次弹 preview/编辑弹窗（OnlyOffice/pdfjs），层级 L3。

### 2.8 采购方式分配 `/HospitalProcurement/view/procurementMethodConfirm/`

**列表 index.html**：`#candidateSearchForm[lay-filter="candidateSearchForm"]`、`#candidateResetBtn/#candidateSearchBtn`、字段 `[idname="requestCode"]`、`[idname="requestName"]`、`[idname="purchaseCategory"]`、`[idname="purchaseMethod"]`；`#candidateCount/#candidateTable[lay-filter="candidateTableIndex"]`；`#recordSearchForm[lay-filter="recordSearchForm"]`、`#recordResetBtn/#recordSearchBtn`、`[idname="requestCode"]`、`[idname="approvalStatus"]`、`#recordCount/#recordTable[lay-filter="recordTableIndex"]`；页签容器 `lay-filter="procurementMethodTabs"`。
操作：候选表 `[lay-event="view"]查看`、`[lay-event="assign"]分配方式`；已分配记录表 `[lay-event="view"]`。
**编辑页 editor/index.html（L2）**：`[lay-filter="methodConfirmForm"]`、`#methodForm`、`[idname="purchaseCategory"]`、`[idname="purchaseMethod"]`、`[idname="procurementBasis"]`、`[idname="bid_evaluation_form"]`、`[idname="govIsProject"]`、`[idname="govOrganizationForm"]`、`[idname="govPublicResourcesProject"]`、`[idname="govPurchaseOrganizeForm"]`、`[idname="govPurchaseSite"]`、`[idname="govRegistrationSite"]`、`[idname="govPayment"]`、`[idname="in_hospital_price_type"]`；只读 `#applicationCode/#applicationReason/#projectName/#projectType/#projectAttribute/#purchaseContent/#approvedBudget/#totalAmount/#demandDepartment/#undertakingDepartment/#undertakingOfficer/#applicant/#confirmationStatus/#methodRecommendation/#govExtFields/#govPurchaseSiteRow/#bidEvaluationForm/#bidEvaluationFormField/#inHospitalPriceType/#inHospitalPriceTypeField/#methodSection/#packageWorkspace`；附件 `#methodAttachmentUploader/#methodAttachmentUploadBtn/#methodAttachmentFilePicker/#addMethodAttachmentBtn/#methodAttachmentUploadBtn/#attachmentRows`；`#approvalOpinionForm[lay-filter="approvalOpinionForm"]`、`#approvalOpinionSection`、`#rejectReason`；`#compileDocumentSection/#compileDocumentTable/#compileDocumentRows`、`#relatedFileSection/#relatedFileTable/#relatedFileRows`、`#surveyProcessPackSection/#surveyProcessPackTable/#surveyProcessPackRows`、`#uniquenessMinutesHint`。

### 2.9 采购执行申请 `/HospitalProcurement/view/executionApply/`

**列表 list.html**：`#searchBar[lay-filter="executionSearch"]`、`[idname="code"]`、`[idname="projectName"]`、`[idname="projectAttribute"]`、`[idname="projectCategory"]`、`[idname="purchaseCategory"]`、`[idname="purchaseMethod"]`、`[idname="status"]`、`#doSearch`、`#resetBtn`、`table#executionTable[lay-filter="executionTableIndex"]`；操作 `[lay-event="view"]查看`、`[lay-event="edit"]编辑`、`[lay-event="submit"]提交审批`。
弹窗：编辑 `edit.html?v=20261030-sporadic-display1`（96%×94%，标题“编辑采购执行申请”）、详情 `view.html`（标题“查看采购执行申请”）。
**编辑 edit.html**：`[lay-filter="executionForm"]`、`[idname="projectName"]`、`[idname="purchaseCategory"]`、`[idname="purchaseMethod"]`、`[idname="executionDepartment"]`、`[idname="emergencyReason"]`、`[idname="sporadicDescription"]`、`#sourceApplication[lay-filter="sourceApplication"]`、`#sourceChooser`、`#sourceRequestName/#sourceApprovalStatus`、`#packageBudgetTable`、`#reserveCount`、`#totalAmount`、`#projectCategory/#projectAttribute/#applicationCode/#demandDepartment/#undertakingDepartment`、`#urgentFields`、`#sporadicFields`；附件 `.section-toolbar`、`.attachment-action[data-action='上传']`、`.attachment-action[data-action='删除']`。
**详情 view.html**：`#applicationCode/#applicationStatus/#code/#status/#createDate/#demandDepartment/#undertakingDepartment/#executionDepartment/#projectName/#projectAttribute/#projectCategory/#purchaseCategory/#purchaseMethod/#totalAmount/#reserveCount/#contact/#phone/#sourceRequestName/#emergencyRow/#emergencyReason/#sporadicRow/#sporadicDescription/#packageBudgetTable`。

### 2.10 采购工作台与业务审批

**工作台 shell index.html**：`#pwb-shell`、`#pwb-module-tabs`（模块页签）、`#pwb-module-frames`（模块 iframe 容器）、`#pwb-shell-status/#pwb-shell-status-icon/#pwb-shell-status-text`、`#pwb-permission-retry`（“重新加载”）。模块清单 `config/moduleRegistry.js`：`dashboard`、`taskCenter`、`analytics`、`processQuery`（iframe 相对路径 `modules/xxx/index.html`）。
- taskCenter：`#pwb-task-center`、`#pwb-task-frames`；页签按钮文本“待办/已办/结办/科室”；内嵌 iframe 指向 `businessApproval/personal/*.html`。
- dashboard：`#pwb-dashboard`、`#pwb-dashboard-grid`、`#pwb-workbench-name/#pwb-workbench-title/#pwb-workbench-date`、`#pwb-customize-btn`（自定义工作台）、`#pwb-customize-dialog`、`#pwb-widget-list`、`#pwb-enter-edit-btn`、`#pwb-save-config-btn`；`lay-filter="widget-check"`。
- processQuery：`#processQueryGrid`（表格，`lay-filter="processQueryGrid"`）、`#keywordInput`、`#btnSearch/#btnReset`、`#pqListView/#pqFlowView/#pqFlowCanvas/#pqFlowGraph`、`#btnZoomIn/#btnZoomOut/#btnZoomFit`、`#pqDrawer/#pqDrawerMask/#pqDrawerBody/#pqDrawerClose/#pqDrawerTitle`、`#pqUrgePanel`、`#btnBackList`。
- analytics：`#...`（见 modules/analytics/index.html，三张 HCUI.datagrid 表）。

**业务审批列表**（`businessApproval/personal/todoTaskList.html` 等）：`#searchBar`、`#searchBtn`、`#resetBtn`、`[idname="processTitle"]`、`[idname="purchaseSectionCode"]`、`[idname="starterName"]`、`[idname="processName"]`、`[idname="processStartTimeBegin/End"]`、`[idname="taskStartTimeBegin/End"]`、`[idname="taskCompletedTimeBegin/End"]`（已办）、`[idname="processFinishTimeBegin/End"]`（办结）、日期控件 id `#processStartTimeBeginPicker/#processStartTimeEndPicker/#taskStartTimeBeginPicker/#taskStartTimeEndPicker/#taskCompletedTimeBeginPicker/…#processFinishTimeBeginPicker/…`；表格 `table#taskTable[lay-filter="taskTableIndex"]`；操作 `[lay-event="toComplete"]办理`、`[lay-event="view"]查看`。（列里还有“任务id”，可用于调试定位。）

**审批办理 toCompletePage.html（L2 iframe）**：`#approval_business_data`（业务数据渲染容器）、`#business_iframe`（旧版业务页 iframe，可能 `about:blank`）、`#formTable`（审核表单，动态生成）、`#backoffDiv`、`#reviewHistory/#reviewHistoryTable`。
`#formTable` 内动态控件（`toCompletePage.js`）：审核结果 radio `input[name="auditResult"]`（PASSED=`1`，REJECTED=`0`，标记 label 通过/驳回）；采购办干事选择 `#handlerUserSelect`；行政/法务审批人 `#administrationUserSelect`（多选）；评标方式 `#bidEvaluationFormSelect`（0 综合评分/1 最低评标价法）；意见 textarea（`comment`）；可选扫码签名区 `tr#approvalSignRow`：`#approvalScanSignBtn`（扫码签名）、`#approvalClearSignBtn`、`#approvalSignPreview`、`#approvalSignImage`、`#approvalSignTip`。
弹窗底部按钮在**父窗口 layer**：`.layui-layer-btn0` = “提交”，`.layui-layer-btn1` = “返回”；提交会 `HCUI.popDialog.confirm("确定审核通过？")` 再 POST `/EbiddingBusinessApproval/workflow/task/complete`。
审批业务数据渲染：`ApprovalBusinessDataRenderer.render("#approval_business_data", taskDetailData)`（`businessDataRenderer.js`），BT 类型映射 `businessTypeUtil.js`；BT13 采购执行、BT14 采购需求文件、BT19 调研结果（`openSurveyResultTask` 直接弹 `surveyResult/detail.html`）、BT20 终止、BT23 成交确认。

**审批签名独立页** `businessApproval/scanSign/approvalTaskSignatureScan.html`：`#canvas`（手写画布）、`#ok`（确认签名）、`#clear`（清除重签）、`#memberName/#memberInfo/#processInfo/#taskInfo/#status/#signPanel`。

### 2.11 纪检监察平台 `DisciplineInspection/`

**壳 index.html**：`#menu`、`#system_username`、`#user_custom_logo`、`lay-filter="mainTab"`；菜单加载 `/nodeJs/menu_Json`，并 `appendAuditMenus` 本地补“审计管理/采购专项审计/其他项目审计/统计汇总与下载”（id 形如 `discipline-audit-management-purchase`）。
**监察项目列表 projectList/index.html**：`#di-project`、`#keywordInput`、`#supervisorFilter[lay-filter="supervisorFilter"]`、`#statusFilter[lay-filter="statusFilter"]`、`#btnSearch/#btnReset`、`#projectGrid[lay-filter="projectGrid"]`（div，HCUI.datagrid 渲染成 Layui table）、`#detailPanel/#detailTitle`、`#docsGrid[lay-filter="docsGrid"]`、`#btnDownloadAll`、`#warnBox/#warnTypeText/#warnBody/#btnWarnNotice/#btnWarnRecord`。
- 行内操作：`[lay-event="viewDocs"]查看资料`、`[lay-event="assignSupervisor"]分配监督员`、`[lay-event="editSupervisor"]修改监督员`、文件行 `[lay-event="downloadDoc"]下载`。
- **分配监督员弹窗**：`assignSupervisorTpl` 模板（`<script type="text/html">`）→ `layer.open({type:1, title:"分配监督员", content: $("#assignSupervisorTpl").html()})`，**弹层挂在 `window.top.layer`**（`getHostWindow()`：`window.top.layer` 优先）。控件：`#assignProjectName`（只读）、`#assignSupervisorSelect`、`name="assignSupervisionScope"`（radio，1 全流程）、`#btnConfirmAssignSupervisor`、`#btnCancelAssignSupervisor`。
- 修改监督员弹窗：`#editSupervisorTpl` → `#editProjectName`、`#newSupervisorSelect[lay-filter="newSupervisorSelect"]`、`#btnConfirmEditSupervisor`、`#btnCancelEditSupervisor`。

**监督员管理 supervisorManage/index.html**：`#di-supervisor`、`#supervisorGrid[lay-filter="supervisorGrid"]`；行内“分配项目”按钮 → `#assignProjectModal`（页面内隐藏 DOM）：`#modalSupervisorName`、`#projectCheckboxList` 内 `input[name="projectIds"]`、`name="modalScope"`、`#btnModalAssign`、`#btnModalCancel`。
**采购专项审计 purchaseAudit/index.html**：`#projectNameInput`、`#projectCodeInput`、`#reportNoInput`、`#statusSelect[lay-filter="statusFilter"]`、`#departmentInput`、`#searchBtn/#resetBtn/#batchDownloadBtn`、`#batchConfirmBtn/#batchCancelBtn`（批量勾选后显示）、`#auditGrid[lay-filter="auditGrid"]`；行内 `[lay-event="view"]查看`、`[lay-event="handle"]办理`、`[lay-event="downloadReport"]下载审计报告`。
- 办理弹窗：`review.html?auditId=`（“审理采购专项审计”，按钮“提交主任审批/选择审计报告模板/关闭”）：`#basicInfo/#requestInfo/#methodInfo/#files/#subpackages/#reportInfo/#auditOpinion/#chooseTemplateBtn/#saveBtn/#message/#closeBtn`。
- 主任审批弹窗：`detail.html?auditId=`（“采购专项审计详情”）：`#auditCode/#requestCode/#requestName/#projectCode/#applicant/#department/#applicationReason/#purchaseContent/#reportBudget/#approvedBudget/#purchaseMethod/#procurementBasis/#methodApprovalStatus/#inHospitalPriceType/#gov*`、`#subpackageWorkspace`、`#fileRows/#fileCount`、`#auditOpinion`、`#directorActionBar` 内 `#directorPassBtn（通过）/#directorRejectBtn（驳回）`、`#auditFinishTime`。
- 报告编辑 `reportEditor.html`；OnlyOffice 预览 `onlyofficePreview.html`。

### 2.12 行内按钮 `lay-event` 汇总（自动化用）

| 页面 | lay-event → 文案 |
|---|---|
| procurementApply/list.html | view 查看；edit 编辑；deleteDraft 删除草稿；confirm 确认；submitAudit 提交审批；singleLaunch 单独发起；blocked* 禁用态 |
| procurementApply/edit.html | editReserve 编辑；remove 删除；blockedRemove 删除(禁用) |
| packageManagement/index.js | view 查看；edit 分包；confirm 确认；blocked* |
| procurementRequirement/index.js | view 查看；edit 编辑；submit 确认并推送主任/重新推送主任/推送审计；download 下载 |
| auditManagement/index.js | **中文 lay-event**：查看 / 推送审计 / 编辑 / 补充相关材料 / 发起采购执行申请 |
| procurementRequirementReview/index.js | review 前加签审查；startReview 审查；viewConclusion 查看审查结论；preSign 前加签 |
| procurementMethodConfirm/index.js | view 查看；assign 分配方式 |
| executionApply/list.html | view 查看；edit 编辑；submit 提交审批 |
| surveyProject/list.js | edit；editNotice；viewNotice；participate；viewReply；publishNow；downloadNoticePack；view |
| surveyResult/list.js | viewResult；viewSurvey；viewReview；viewReply；downloadQcc；downloadTechSpec；qccPending |
| surveyArgument/list.js | schedule；extract；pick；progress；situation；postpone；report；result；sign |
| businessApproval todos | toComplete 办理；view 查看；department/todoTaskList.js 还有 claim（认领） |
| DisciplineInspection projectList | viewDocs 查看资料；assignSupervisor 分配监督员；editSupervisor 修改监督员；downloadDoc 下载 |
| DisciplineInspection purchaseAudit | view 查看；handle 办理；downloadReport 下载审计报告；otherAudit: view 查看资料 |

---

## 3. AJAX 接口目录

> 统一说明：`PROJECT_NAME` 在 HP 页面由 `renderPublickHead.js` 注入 = `HospitalProcurement`；`PROJECT_APPROVAL_NAME` = `EbiddingBusinessApproval`（`approvalCommon.js`）；`PROCUREMENT_EXECUTION_CONTEXT_PATH` 默认 `/ProcurementExecution`。业务接口成功判定通常为 `success === true`（少数用 `code===0/200`），datagrid 列表要求 `data.records/total` 或 `data.list/total`。

### 3.1 采购申请（procurementApply）
来源：`procurementApplyApi.js`（PAGE_URL 等常量、`window.ProcurementApplyApi` 导出）、`list.html` 内联 datagrid。

| 动作 | 方法 | URL | 关键参数 | 成功判定 |
|---|---|---|---|---|
| 列表 | GET | `/HospitalProcurement/hospitalPurchaseRequest/page` | `current`,`size`,`requestCode`,`requestName`,`status`（+`year/attributeType/ownerDepartment` 视页签） | `success:true` + `data.records/data.total`（`normalizePageResponse` 容错 total/totalCount/totalElements） |
| 详情 | GET | `/HospitalProcurement/hospitalPurchaseRequest/detail` | `purchaseRequestId` | `success:true` |
| 保存草稿 | POST | `/HospitalProcurement/hospitalPurchaseRequest/saveDraft` | `buildDraftPayload`：requestName/attributeType/projectAttribute/requestDepartment/applicationReason/purchaseContent/uuid/reserveItems/attachments/planType | `success:true` |
| 删除草稿 | POST | `/HospitalProcurement/hospitalPurchaseRequest/deleteDraft` | `purchaseRequestId` | `success:true` |
| 确认（计划内） | POST | `/HospitalProcurement/hospitalPurchaseRequest/confirm` | `purchaseRequestId` | `success:true` |
| 提交审批 | POST | `/HospitalProcurement/hospitalPurchaseRequest/submitAudit` | `purchaseRequestId` | `success:true` |
| 附件预览 | GET | `/HospitalProcurement/hospitalPurchaseRequest/attachment/preview` | `attachmentId`,`fileName` | 返回文件流 |
| 预算库（发起采购页签） | GET | **`/hospital-procurement/api/plan-management/reserve-library`** | `page`,`pageSize`,`budgetCode`,`projectName`,`year`,`attributeType`,`status`,`ownerDepartment` | 页面 `fillter` 接受 `code===0/200`，`data.records` |
| 附件上传/下载（通用） | POST/GET | `/doFile/upload/`、`/doFile/download/?attachmentId=`，回调 `/HospitalProcurement/tenderingmanagement/tenderAttachment/addAttachment`、`.../deleteAttachment`、`.../queryAttachmentList` | WebUploader chunk | `success:true` |

### 3.2 分包管理（packageManagement）
`packageManagementApi.js`：`DETAIL_URL = /HospitalProcurement/hospitalPurchaseRequest/subpackages/`

| 动作 | 方法 | URL |
|---|---|---|
| 列表 | GET | `/HospitalProcurement/hospitalPurchaseRequest/page`（`subpackageManage=true`,`subpackageStatus`,`departmentId`,`requestCode`,`requestName`,`current`,`size`） |
| 详情 | GET | `/HospitalProcurement/hospitalPurchaseRequest/subpackages/{purchaseRequestId}` |
| 单子包 | GET | `/HospitalProcurement/hospitalPurchaseRequest/subpackages/{purchaseRequestId}/{subpackageId}` |
| 保存分包 | POST | `.../subpackages/{purchaseRequestId}`（body：子包数组/预算分配） |
| 删子包 | DELETE | `.../subpackages/{purchaseRequestId}/{subpackageId}` |
| 确认分包 | POST | `.../subpackages/{purchaseRequestId}/confirm` |
| 同步历史调研项目 | POST | `.../subpackages/syncAllSurveyProjects` |

### 3.3 市场调研（hpSurveyProject）
| 模块 | 动作 | 方法 | URL / 参数 |
|---|---|---|---|
| surveyProject | 列表 | GET | `/HospitalProcurement/hpSurveyProject/hpSurveyProject/getPage`（`projectName/projectCode/bussinessType/state` + 分页） |
| surveyProject | 详情 | GET | `.../hpSurveyProject/getOneById`（`uuid`） |
| surveyProject | 保存 | POST | `.../hpSurveyProject/updateById` |
| surveyProject | 发布公告/排期 | POST | `.../hpSurveyProject/schedulePublish` |
| surveyProject | 推送/流转 | POST | `.../hpSurveyProject/pushOneById`（`uuid`） |
| surveyProject | 下载公告包 | GET | `.../hpSurveyProject/downloadNoticePack?uuid=` |
| surveyProject | 下载技术参数模板 | GET | `.../hpSurveyProject/downloadTechTemplate` |
| surveyProject | Excel 导入 | POST | `.../hpSurveyProject/parseIndexExcel`、`.../parseTechExcel` |
| surveyProject | 公告模板内容 | POST/GET | `.../hpSurveyProject/getAnnouncementContentByTemplate` |
| surveyReply（供应商参与） | 我的回复/保存 | GET/POST | `.../hpSurveyReply/getMyReply`、`.../hpSurveyReply/save`、`.../hpSurveyReply/listByProject` |
| surveyResult | 列表 | GET | `.../hpSurveyResult/getPage` |
| surveyResult | 详情 | GET | `.../hpSurveyResult/getDetail` |
| surveyResult | 审批（通过/驳回/反驳/提交主任） | POST | `.../hpSurveyResult/audit` |
| surveyResult | 重试背调 | POST | `.../hpSurveyResult/retryQccReport` |
| surveyResult | 重新发起调研 | POST | `.../hpSurveyResult/relaunch` |
| surveyResult | 导出技术参数 | GET | `.../hpSurveyResult/downloadTechSpec?uuid=` |
| surveyResult | PDF 预览 | GET | `.../hpSurveyResult/previewAsPdf` |
| surveyArgument | 列表 | GET | `.../hpSurveyArgument/getPage` |
| surveyArgument | 详情 | GET | `.../hpSurveyArgument/getDetail` |
| surveyArgument | 专业列表 / 补抽候选 / 人工候选 | GET | `.../hpSurveyArgument/listMajors`、`/listMakeupCandidates`、`/listManualCandidates` |
| surveyArgument | 开始/继续抽取 | POST JSON | `.../hpSurveyArgument/startExtract`、`/continueExtract`（`contentType: application/json`） |
| surveyArgument | 保存人工勾选/补抽 | POST | `.../hpSurveyArgument/saveManualExperts`、`/saveMakeupExperts`、`/addManualSpecialty` |
| surveyArgument | 延期 | POST | `.../hpSurveyArgument/postponeArgument` |
| surveyArgument | 投票/意见 | POST | `.../hpSurveyArgument/saveVote`、`/saveOpinions` |
| surveyArgument | 报告模板/保存报告 | POST | `.../getReportByTemplate`、`/saveReport` |
| surveyArgument | 导出报告 | POST（xhr） | `.../hpSurveyArgument/downloadReport` |
| surveyArgument | PC 扫码签名 | GET/POST | `.../getDetail`、`.../createReportSignatureQr`（`surveyProjectUuid`） |
| surveyArgument | 手机签名 | POST | `.../prepareReportSignature`（`token`）、`.../confirmReportSignature`（`token`,`signature` dataURL） |
| surveyArgument | 论证情况 / 指定组长 | GET/POST | `.../getDetail`、`.../designateLeader` |
| surveyArgument | 上传论证结果/离线结果 | POST | `.../saveOfflineResult` |
| surveyArgument | 过程材料导出 | GET | `.../downloadProcessPack?uuid=` |
| surveyArgument | 催办/重试 | POST | `.../urgeLeaderReport`、`/retryTrigger` |
| 旧公告体系（PreProject） | 列表/增删改/推送 | GET/POST | `/HospitalProcurement/PreProject/preProject/getPage`、`/add`、`/updateById`、`/deleteById`、`/pushOneById`、`/confirmOneById` |
| 旧公告体系 | 参数/资格指标 | GET/POST | `/HospitalProcurement/PreProjectParamParam/PreProjectParamParam/getPage|add|updateById|deleteById`、`/PreProjectIndex/preProjectIndex/getPage|add|updateById|deleteById|preAddQualificationIndexListFromExcel|preAddBusOrTecIndexListFromExcel` |
| 旧公告体系 | 供应商回复明细 | POST | `/HospitalProcurement/PrePreProjectIndexSuppilerReply/prePreProjectIndexSuppilerReply/add|finishParams` |

### 3.4 采购需求在线编制（procurementRequirement）
| 动作 | 方法 | URL |
|---|---|---|
| 列表 | GET | `/HospitalProcurement/hospitalPurchaseRequest/requirement-editing-page`（`requestCode`,`requestName`,`status`） |
| 编辑上下文 | GET | `.../hospitalPurchaseRequest/requirement-editing-detail?purchaseRequestId=` |
| 保障过程材料包 | POST | `.../hospitalPurchaseRequest/ensureSurveyProcessPack` |
| 模板列表 | GET | `.../purchase/document/template/list` |
| 建文档 | POST | `.../purchase/document/createByTemplate` |
| 删草稿 | GET/POST | `.../purchase/document/deleteDraft?documentUuid=` |
| 按申请查文档 | GET | `.../purchase/document/by-purchase-request/{purchaseRequestId}` |
| 文档状态 | GET | `.../purchase/document/{documentId}/status` |
| OnlyOffice 配置 | GET | `.../purchase/document/{documentUuid}/onlyoffice-config` |
| 浏览器下载 | GET | `.../purchase/document/{documentUuid}/browser-download` |
| 保存/强存（持久化） | POST | `procurementDocumentPersist.js` 组合 `.../purchase/document/{documentUuid}/{suffix}` + force-save（见 `contractFile/document/{uuid}/force-save` 同类模式） |
| 推送审计 | POST | editDocument 页 `#submitDocumentBtn` 对应后端「提交审计」（接口在页内联，建议以 Network 抓一次为准） |

### 3.5 审计管理（HP）
| 动作 | 方法 | URL / 参数 |
|---|---|---|
| 列表 | GET | `/HospitalProcurement/hospitalPurchaseAudit/page`（`projectName`,`auditStatus`） |
| 详情 | GET | `/HospitalProcurement/hospitalPurchaseAudit/detail?auditId=` |
| 审计员候选 | GET | `/HospitalProcurement/hospitalPurchaseAudit/auditorCandidates` |
| 保存审计内容 | PUT JSON | `/HospitalProcurement/hospitalPurchaseAudit/{auditId}/content`（body 审计内容） |
| 推送审计 | POST JSON | `.../{auditId}/push`（`{auditorUserId, attachRequirementDocument:0|1}`） |
| 上传关联文件 | POST multipart | `.../{auditId}/files`（form field `file`，多次调用） |
| 删除文件 | DELETE | `.../{auditId}/files/{documentId}` |
| 生成审计报告 | POST | `.../{auditId}/report/generate`（timeout 180s） |
| 删除报告 | DELETE | `.../{auditId}/report` |

### 3.6 采购需求审查（hospitalPurchaseDemandReview）
| 动作 | 方法 | URL |
|---|---|---|
| 列表 | GET | `/HospitalProcurement/hospitalPurchaseDemandReview/page` |
| 前加签候选 | GET | `.../preSignOptions` |
| 前加签 | POST | `.../preSign` |
| 发起审查 | POST | `.../initiate` |
| 任务详情 | GET | `.../taskDetail` |
| 完成任务 | POST | `.../completeTask` |
| 审查结论 | GET | `.../conclusionDetail` |
| 文档接口前缀 | - | `.../hospitalPurchaseDemandReview/document` |
| 保存审查 | POST | `/HospitalProcurement/hospitalPurchaseDemandReview/save` |
| 文档状态/下载 | GET | `/HospitalProcurement/purchase/document/{documentId}/status`、`/purchase/document/{documentUuid}/browser-download` |

### 3.7 采购方式分配（procurementMethod）
| 动作 | 方法 | URL |
|---|---|---|
| 待分配列表 | GET | `/HospitalProcurement/hospitalPurchaseRequest/procurementMethod/items`（`requestCode`,`requestName`,`purchaseCategory`,`purchaseMethod` 等） |
| 详情 | GET | `.../procurementMethod/detail` |
| 提交分配 | POST | `.../procurementMethod/submit` |
| 完成任务 | POST | `.../procurementMethod/completeTask` |
| 文档下载 | GET | `/HospitalProcurement/purchase/document/{documentUuid}/browser-download` |

### 3.8 采购执行申请（ProcurementExecution 后端）
| 动作 | 方法 | URL |
|---|---|---|
| 可选来源申请 | GET | `/ProcurementExecution/purchase/purchaseProject/selectableSourceApplies` |
| 来源申请详情 | GET | `/ProcurementExecution/purchase/purchaseProject/sourceApplyDetail` |
| 保存执行项目 | POST | `/ProcurementExecution/purchase/purchaseProject/savePurchaseProject` |
| 更新来源申请项目 | POST | `/ProcurementExecution/purchase/purchaseProject/updateSourceApplyProject` |
| 列表 | GET | `/ProcurementExecution/purchase/purchaseProject/getPage` |
| 详情 | GET | `/ProcurementExecution/purchase/purchaseProject/detail` |
| 采购联系人 | GET | `/ProcurementExecution/purchase/purchaseProject/purchaseContactList` |
| 子包文档 | GET/POST/DELETE | `/ProcurementExecution/purchase/subpackageDocument/list`、`/upload`、`/delete` |
| 提交审批 | POST | `/ProcurementExecution/purchase/purchaseProject/commitAudit` |

### 3.9 业务审批（EbiddingBusinessApproval）
| 动作 | 方法 | URL |
|---|---|---|
| 个人待办/已办/办结 | GET | `/EbiddingBusinessApproval/workflow/task/list/todo`、`/list/completed`、`/list/finished` |
| 科室待办 | GET | `/EbiddingBusinessApproval/workflow/task/list/group/todo` |
| 认领 | POST | `/EbiddingBusinessApproval/workflow/task/claim/{taskId}` |
| 任务详情（查看） | GET | `/EbiddingBusinessApproval/workflow/task/{taskId}` |
| 待办任务详情 | GET | `/EbiddingBusinessApproval/workflow/task/todo/{taskId}` |
| 可回退节点 | GET | `/EbiddingBusinessApproval/workflow/task/backoff/tasks/{taskId}` |
| 完成任务 | POST | `/EbiddingBusinessApproval/workflow/task/complete`（form：`formProperties[auditResult]`、`vars[handlerUserId]`、`vars[administrationUserId]`（多值逗号/数组）、`vars[bidEvaluationForm]`、`vars[purchaseExecutionHandlerUserId]`、`comment`） |
| 回退 | POST | `/EbiddingBusinessApproval/workflow/task/backoff` |
| 流程实例列表/查询 | GET | `/EbiddingBusinessApproval/workflow/pi/list`、`/workflow/pi/list-with-pr`、`/workflow/pi/detail/{id}` |
| 扫码签名 | GET/POST | `/EbiddingBusinessApproval/workflow/task/signQr`、`/signStatus`、`/clearSign` |
| 办理页候选人 | GET | `/HospitalProcurement/hospitalPurchaseRequest/handlerCandidates`、`/administrationCandidates`；执行干事 `/ProcurementExecution/purchase/purchaseProject/purchaseContactList` |

### 3.10 纪检（/jjjc）
| 动作 | 方法 | URL |
|---|---|---|
| 监察项目分页 | GET | `/jjjc/supervise/projectPageList` |
| 监督员列表 | GET | `/jjjc/supervise/supervisorList` |
| 全流程资料 | GET | `/jjjc/supervise/processDocuments` |
| 一键打包下载 | GET | `/jjjc/supervise/downloadAllZip` |
| 是否有分配权限 | GET | `/jjjc/supervise/canManageAssignment` |
| 分配监督员 | POST JSON | `/jjjc/supervise/assign`（`{projectId,supervisorUserId,supervisionScope,prjCode,scopeDetail}`） |
| 修改监督员 | POST | `/jjjc/supervise/reassign` |
| 单文件下载 | GET | `/jjjc/supervise/downloadFile?fileId=` |
| 采购专项审计列表 | GET | `/jjjc/purchaseAudit/page` |
| 审计详情/文件/报告 | GET/POST | `/jjjc/purchaseAudit/{auditId}/files/...`、`/jjjc/purchaseAudit/{id}/report`（模板与操作见 `purchaseAuditApi.js`） |
| 审计统计 | GET | `/jjjc/purchaseAudit/statistics/status|type|monthlyTrend|summary|reportAmount` |
| 审计模板 | GET/POST | `/jjjc/purchaseAudit/template/page`、`/template/{id}/variables` |
| 申请单列表 | GET | `/jjjc/supervise/projectTrackingPage` |
| 全流程节点 | GET | `/jjjc/supervise/projectTracking/{requestId}/{summary|preNodes|executionNodes|approvalRecords|postNodes}`、`/nodes/{nodeCode}/detail`、`/subpackages/{subpackageId}/postNodes/{nodeCode}/detail` |

### 3.11 采购工作台
| 动作 | 方法 | URL |
|---|---|---|
| 总览/配置 | GET/POST | `/HospitalProcurement/api/workbench/overview`、`/api/workbench/configuration` |
| 快捷入口 | GET | `/api/workbench/quick-entries`（实际 `projectPath(...)` = `/HospitalProcurement/api/workbench/quick-entries`） |
| 待办统计 | GET | `/EbiddingBusinessApproval/workflow/task/list/todo`、`/list/handled` |
| 流程查询列表 | GET | `/HospitalProcurement/api/workbench/process-query/page` |
| 流程查询详情/催办 | GET/POST | `/api/workbench/process-query/{id}/...`、`/{id}/urge-records` |
| 分析报表 | GET | `/HospitalProcurement/api/procurement-reports/department-analysis`、`/department-analysis/departments` |

---

## 4. 文件上传 / 下载 / 签名 / 模板组件

### 4.1 上传（两条体系）

**(A) uploaderInit（`view/common/attachmentUploader.js` + `attachmentData.js`，WebUploader 封装）**
- 配置：`uploaderInit({uploaderId, filePicker, uploadBtn, config, uploadTable, uploadedTable, ajaxConfig, otherConfig, enhancedUpload, autoUpload})`。
- DOM：容器 `#<uploaderId>`（含 `.webuploader-pick` 按钮）、选文件 `#<filePicker>`、上传按钮 `#<uploadBtn>`、待上传表 `#upload_fileList`、已上传表 `#uploaded_fileList`。
- 服务端默认：上传 `/doFile/upload/`（分片 512KB）、校验 `/doFile/check/`、下载 `/doFile/download/?attachmentId=`；上传成功回调默认 `/HospitalProcurement/tenderingmanagement/tenderAttachment/addAttachment`，删除 `.../deleteAttachment`，列表 `.../queryAttachmentList`。
- 已确认使用页面：`procurementApply/edit.html`（`#applicationAttachmentUploader` + `#applicationAttachmentFilePicker`）、合同/招标/评标等大部分老页面。
- Playwright：`frame.locator('#<uploaderId> input[type=file]').setInputFiles(path)`（隐藏 input 可用 setInputFiles）；随后等 `#uploaded_fileList`/文件行出现“已上传/成功”，或等回调接口 200。

**(B) QaMultiFile（`view/common/qaMultiFile.js`，包 WebUploader，`fileUploadInit`）**
- 用法：`QaMultiFile.create({uploaderId, filePicker, uploadBtn?, ...})`；`QaMultiFile.renderList(target, ids, names, readonly)`；`QaMultiFile.parse/download`。
- UI：容器加 `.qa-drop-wrap`，选择按钮 `.webuploader-pick`（文案“点击选择文件，或将文件拖到此处”），列表 `.qa-file-list`，状态 `.qa-file-status-done`（“已上传”）、`.qa-file-status-uploading` 等；单文件 ≤50MB、最多 10 个、总 200MB（默认，可覆盖）。
- 已确认使用页面：`surveyProject/edit.html`（`#otherSurveyUploader`/`#otherSurveySelect`）、`notice.html`、`participate.html`、`surveyArgument/result.html`、`surveyResult/detail.html`（只读 renderList）、`entrustedComparison/*`、`hpArchive/upload.html`。
- Playwright：`setInputFiles` 到容器内 `input[type=file]`；等 `.qa-file-status-done` 或“已上传”文本。

**(C) 原生 file input（审计详情）**
- `auditManagement/detail.html` 的 `input type=file#auditFileInput`：`change` 即逐个 POST `/hospitalPurchaseAudit/{id}/files`（FormData `file`）；`#auditUploadBtn` 只是触发点击。
- Playwright：`setInputFiles('#auditFileInput', files)`，等 `#fileRows tr` 增加或成功 msg。

**(D) 业务内嵌上传页**：`view/tenderManagement/editTender/tenderFileUpload/uploadAttachment.html`、`view/common/ueditor`（富文本内图片上传走 ueditor，接口在 `target/ueditor.js` 配置，未逐项展开）。

### 4.2 下载
- 通用：`/doFile/download/?attachmentId=<id>`（附件），页面用 `window.location.href = "/doFile/download/?attachmentId=..."`。
- 业务导出：`/HospitalProcurement/hpSurveyProject/hpSurveyProject/downloadNoticePack?uuid=`、`.../hpSurveyArgument/downloadProcessPack?uuid=`、`.../hpSurveyResult/downloadTechSpec?uuid=`、`.../systemTemplate/downloadExcel?fileName=项目商务评审指标Excel导入模版.xlsx`、`/HospitalProcurement/purchase/document/{uuid}/browser-download`。
- PDF 预览统一走 `/HospitalProcurement/components/pdfjs/web/viewer.html?file=<encodeURL>`（弹窗 iframe）。
- Playwright：导出类用 `page.waitForEvent('download')`；PDF 预览页在 iframe 内再套 pdfjs viewer（`#viewer`/`.page`）。

### 4.3 签名 / 扫码
| 场景 | PC 侧 | 手机侧 | 接口 |
|---|---|---|---|
| 调研论证报告签名 | `surveyArgument/report.html` → `#openSignQr`/`#signPanel`/`#signQrImage`（或 `reportSignatureQr.html`） | `reportSignatureScan.html?token=...`：`#canvas` 手写 → `#ok` | `createReportSignatureQr`（GET/POST）、轮询 `getDetail` 3s、`prepareReportSignature`、`confirmReportSignature`（`signature` = canvas.toDataURL('image/png')） |
| 审批节点签名（可选） | 办理页 `#approvalSignBtn`（`#approvalScanSignBtn`）→ layer 二维码 `#approvalSignQrImage`，轮询 `signStatus` | 手机扫码（服务端下发链接，页面不在此仓库） | `/EbiddingBusinessApproval/workflow/task/signQr`、`/signStatus`、`/clearSign`；仅 BT6/BT8/BT13/BT14 启用 |
| 独立手写签名页 | `businessApproval/scanSign/approvalTaskSignatureScan.html`：`#canvas` + `#ok`/`#clear` | — | 由父页打开，提交走父页 complete 请求（签名图作为附件/字段） |

自动化建议：签名是**可选**（`approvalScanSign.js` 注释“不强制签名，提交校验不读本模块状态”），E2E 前置流程可跳过；如必须覆盖，直接调用 `signQr` + 轮询 + `confirmReportSignature` 接口，或用 Playwright 在 canvas 上 `mouse.move/down/up` 画折线后点 `#ok`（仅限本机无真实扫码需求时）。

### 4.4 模板 / Excel 导入
- 模板选择通用组件：`view/template/templateCommonJs.js`（`#importTemplate`/`#templateBtnWrap` → 弹 `view/template/chooseTemplate.html?templateType=...`）。
- 调研项目技术参数：`downloadTechTemplate` 下载模板；`indexUpload.html`（`parseIndexExcel`）、`techUpload.html`（`parseTechExcel`）导入；页面按钮 `#btnTechImport`/`#btnTechDownload`。
- 评审指标 Excel：`downloadExcel?fileName=项目商务评审指标Excel导入模版.xlsx` / `项目技术评审指标Excel导入模版.xlsx`。
- 公告/参数导入：`preAddQualificationIndexListFromExcel`、`preAddBusOrTecIndexListFromExcel`（旧 PreProject 体系）。
- 审计报告：`auditManagement/detail.html` 的 `#generateReportBtn` 生成（后端模板），纪检侧模板管理 `purchaseAuditTemplate`（`docxTemplateList.html` 在 `TemplatService`）。

### 4.5 富文本 / OnlyOffice
- ueditor：`#bullentContent` 等 textarea 由 ueditor 接管，编辑器 iframe 在 `.edui` 容器内（Playwright 用 `frameLocator('#bullentContent')` 或 `.edui iframe`）。
- OnlyOffice：`onlyofficeDocument.html`、`purchaseDocument/onlyofficePreview.html`、纪检 `onlyofficePreview.html`、合同 `onlyofficeEditor`；依赖 `window.DocsAPI.DocEditor` + `/purchase/document/{uuid}/onlyoffice-config`。若本地未部署 document server，此步不可自动化，需跳过并记录。

---

## 5. 鉴权 / 菜单 / 平台切换 / 角色差异

### 5.1 登录与平台选择（已由 `automation/probe-*.js` 验证）
1. `GET /Register/login/verification.do`（拿验证码 cookie；验证码图片 `#codeImg` src 同地址）。
2. `POST /Register/login/userLogin.do`，form：`username`、`password`（MD5，示例账号 `cy-cgb-jbr`/`Hc1234` → `crypto.createHash('md5')`）、`checkCode`（**万能码 `qwe!@#`**，见 `registers/.../LoginAction.java`）、`SimplePwd=0`。
3. 登录页选择器：`#username`、`#password`、`#code`、`#loginBtn`（`lay-filter="loginForm"`）、登录方式 radio `input[name="loginType"]`（用户名登录/CA 登录/粤企签）；验证码刷新 `#codeImg[onclick=changeCode()]`。
4. `GET /Register/SelectPlatformAction/select.do` → 返回 `data.platform` / `data.roleCode`（值是加密/编码后的串，不是明文）。
5. `POST /Register/SelectPlatformAction/gotoIndex.do`，form：`platform`、`roleCode`、`macAddress=''`、`ipAddress=''` → `data` 为要跳转的外壳页（如 `/HospitalProcurement/index.html`）。
6. 外壳页：`GET /nodeJs/menu_Json`（依赖 `userLoginInfo` cookie）→ `{success:true,content:[...]}`；失败提示“登录已超时，请重新登录”3s 后跳 `/Register/public/newLogin/user_login_2.html`。
7. 页面内获取用户：`GET /HospitalProcurement/basicinfo/userinfo/getUserBasicInfo`，成功写 `localStorage`：`roleCode`、`userBasicInfo`、`HospitalProcurement.userBasicInfo`、`HospitalProcurement.userBasicInfo.<platform>`；cookie 写入 `userId`。
8. 退出：`GET /Register/login/loginOut.do`；切平台：`GET /Register/login/changePlatForm.do` → 跳 `/Register/public/selectPlatform2/selectPlatform_2.html?platform=<localStorage.platform>`。

### 5.2 菜单渲染与角色差异
- 菜单数据 = 后端 `B_menu` + `B_permission`，按 `roleCode`/`prjCode` 下发（Redis 缓存 + nodejs 服务日志可见）；字段 `{id(menuCode),parentId,url,iconCls,menu_name,level,sort,type,fn,menuCode}`。
- 前端只做两件事：把 `url/menu_name/parentId` 映射到 zhongMenu 节点；`NGP_SUPPLIER` 时删除产品库 6 个菜单（`index.html: filterProductLibraryMenus`）。HP 前端**不再硬编码**采购管理菜单（`procurementMethodConfirm/tests/menuConfiguration.test.js` 明确断言 index.html / disciplineInspection.html 不含 `procurement_management_root`、`采购申请管理` 等硬编码）。
- 已确认关键菜单元数据（来自日志/缓存）：
  - `0000006 采购管理`（父 0）：`0000006000001 采购申请管理` → `/HospitalProcurement/view/procurementApply/list.html`；`0000006000002 分包管理` → `/HospitalProcurement/view/packageManagement/index.html`；`0000006000003 采购方式分配` → `/HospitalProcurement/view/procurementMethodConfirm/index.html`；`0000006000004 采购执行申请管理` → `/HospitalProcurement/view/executionApply/list.html`；`0000006000005 采购需求在线编制` → `view/procurementRequirement/index.html`（无前导 `/`）；`0000006000008 采购需求审查管理` → `/HospitalProcurement/view/procurementRequirementReview/index.html`；`0000006000009 审计管理` → `/HospitalProcurement/view/auditManagement/index.html`。
  - `0000001 市场调研管理`：`0000001000001 调研项目管理`、`0000001000006 调研结果管理`、`0000001000007 调研论证管理`（均在 `/HospitalProcurement/view/hospitalProcurement/marketResearchManage/` 下）。
  - `0000014 论证管理`（另一套）：`0000014000001 论证项目管理`、`0000014000002 论证管理`、`0000014000003 论证项目历史信息`、`0000014000004 确认最终采购需求`（`view/hospitalProcurement/projectDemonstrate/...`）。
  - `600 业务审批`：`602 科室待办`、`603 个人待办`、`604 个人已办`、`605 个人办结`、`606 综合查询`、`607 查看审批信息(?type=agency)`、`601 流程管理`（6011~6016）。
  - `0000063 纪检监察管理` → `/DisciplineInspection/index.html`；子菜单 `0000063000001 监察项目列表`、`0000063000003 监督员管理`、`M000007 审计管理`（采购专项审计/其他项目审计/审计报告模板管理）、`0000047`（申请单列表/全流程详情）。
- **角色差异实证**：`automation/menu-cy-cgb-jbr.json`（cy-cgb-jbr）只有 96 项，`0000006 采购管理` 下仅 `0000006000008 采购需求审查管理`，没有采购申请/分包/方式分配/执行申请/审计管理；而 `logs/NodeJsDynamicControl.log-*` 中 `NGP_CBBM_JBR` 等角色响应里含 0000001 调研菜单、M000005 工作台等。→ 自动化前先 `GET /nodeJs/menu_Json` 落盘，用菜单 code 断言所需入口存在，不存在就换账号/角色。
- 角色码样例（代码里出现）：`REQ_STAFF`（需求科室，采购申请页强制计划外发起）、`NGP_SUPPLIER`、`NGP_PURCHASE`、`NGP_PURCHASEAGENT`、`NGP_CBBM_JBR`、`NGP_EXPERTS`、`NGP_PURCHASEAGENTLEADER`（完整角色清单以 `B_permission` 为准）。

### 5.3 会话过期 / 错误处理
- 菜单接口失败 → 3s 后跳登录页（见 5.1-6）。
- 业务接口失败：`appCommon.otherUtil.ajaxFunction` 默认 `dataType:JSON`、`type:POST`、`isTop:true`、`loadingMask:true`；loading 用 **top 窗口** `layer.load(1,{time:20000})`。无统一 401 拦截 → 页面多为 `if(!res.success) HCUI.popDialog.msg(res.msg)`；过期后可能停在空表格。E2E 需在每步前校验 `#menu`/用户信息或接口响应，区分“无数据”与“会话失效”。
- 平台隔离：HP 与 GovernmentProcurement/ProcurementExecution/DisciplineInspection 各自有 index 壳；工作台通过 `projectName/apiProjectName` query 参数适配跨平台（`config/runtimeConfig.js`），跨平台页面 URL 会带 `?projectName=...&apiProjectName=...`。

---

## 6. 自动化风险点与等待/定位建议

| # | 风险 | 证据 | 建议 |
|---|---|---|---|
| 1 | **弹窗在 top 文档**（不是当前 iframe） | `renderPublickHead.js`: `HCUI_CONFIG.popDialog.isTop=top.layer`；`package.js`: `getBaseWin(isTop){return isTop && window.top.layer ? window.top : window}` | layer 容器用根 page 定位，内容用 `frameLocator`；兼容 fallback：`page.frames().find(f=>f.url().includes('edit.html'))` |
| 2 | **Layui 固定列复制 DOM** | list.html cols `fixed:left/right`；`refreshApplicationTableLayout` 检查 `.layui-table-fixed-r` | 行/单元格限定 `.layui-table-main`；操作按钮在 `.layui-table-fixed-r .layui-table-body` 里也有一份，二选一且加 `.first()`/nth |
| 3 | **Tab 懒渲染 / 隐藏容器宽度 0** | procurementApply list `refreshApplicationTableLayout` 8×50ms 重试；切 tab 才 init | 点击 `li[lay-id="applications"]` 后 `expect(.layui-table-view).toBeVisible()` + 行数>0；不要先断言再切 |
| 4 | **表格 loading 与遮罩** | HCUI datagrid 自身 loading；ajaxFunction top loading | 不用 `networkidle`；等 `tbody tr` / `.layui-table-view` / 具体按钮出现 |
| 5 | **按钮文案随状态变化** | “完善信息/编辑”、“立即发布调研公告/查看公告”、“确认/提交审批”、“确认并推送主任/重新推送主任/推送审计” | 优先 `[lay-event]`；中文 `lay-event`（auditManagement）用精确值；断言状态列文本 |
| 6 | **禁用按钮仍可见** | `blockedXxx` + `aria-disabled`/`visual-disabled`/`operation-disabled` | 先判 `aria-disabled` / class 再 click；不要用 `isEnabled()` 判断（button 未 disabled） |
| 7 | **同页多 tab + 同页多表格** | procurementApply 2 个表 2 个 filter；methodConfirm 2 个表；workbench 多 iframe | 用 `lay-filter` 区分表；page 内 iframe 用 `name`/`src` 区分 |
| 8 | **iframe 嵌套 3-4 层** | L1 菜单 iframe → L2 popDialog iframe → L3 再弹 | 封装 `openDialogFrame(page, urlPart)`；每层都 `waitForLoadState('domcontentloaded')` |
| 9 | **layer type 1 与 type 2 混用** | packageManagement/editor 子包表单、DisciplineInspection 分配弹窗是 type 1 DOM；多数业务页是 type 2 iframe | 判断 `.layui-layer-iframe` 有 iframe 则进 frame，否则直接在 layer content 内查 |
| 10 | **纪检弹窗挂 top（跨壳）** | `DisciplineInspection/projectList/index.js: getHostWindow()` 优先 `window.top.layer` | 纪检的分配监督员弹窗要在**顶层 DisciplineInspection 壳**的 document 找，不在项目列表 iframe |
| 11 | **Layui select/日期/复选重绘** | `form.render()` 后原生控件隐藏 | 交互走 `.layui-form-select dd[lay-value]`、`.layui-laydate`、`.layui-form-checkbox`；或用 `page.evaluate` 设值后 dispatch `change` 再 `form.render()` |
| 12 | **富文本 ueditor iframe** | notice/noEdit/add 的 `bullentContent` | `frameLocator('iframe[id^="ueditor"]')` 或 `.edui iframe`，`body` contenteditable 输入 |
| 13 | **OnlyOffice 依赖外部文档服务** | onlyofficeDocument.js `new DocsAPI.DocEditor` | 探测 `window.DocsAPI`；不可用则跳过并记录，测试聚焦“生成/状态/下载” |
| 14 | **上传为异步多步** | WebUploader 先传文件再回调后端登记；QaMultiFile 自动上传 | `setInputFiles` 后等“已上传”状态或目标接口 200，再保存 |
| 15 | **扫码签名不可自动化** | QR + 手机端 | 覆盖接口层或跳过（可选签名） |
| 16 | **跨平台接口路径不同** | 采购执行走 `/ProcurementExecution`；预算库走 `/hospital-procurement`；其余走 `/HospitalProcurement` | 断言 URL 前缀；不要统一改 baseURL |
| 17 | **中文乱码/编码** | 源码 UTF-8，`<meta charset="utf-8">`；部分旧页无 title | 断言用中文文本时统一 UTF-8；避免依赖 title |
| 18 | **同页多轮询** | signature 3s 轮询、公告变更 100s 轮询、工作台 loading | 关闭不必要轮询或忽略 console 噪音；用 `expect.poll` 限定超时 |

**推荐等待/定位策略（Playwright 片段）**

```js
// 等外壳 + 菜单
await page.goto('http://127.0.0.1/HospitalProcurement/index.html');
await page.locator('#menu [node-id="0000006000001"]').waitFor({ state: 'visible' });

// 点菜单 → 等 L1 iframe
await page.locator('#menu [node-id="0000006000001"]').click();
const listFrame = page.frameLocator('iframe.mainIframe[name="采购申请管理"]');
await listFrame.locator('#applicationTable').waitFor(); // table 元素在 dom，等 layui-table-view 更稳
await listFrame.locator('.layui-table-view').waitFor();

// 切页签并等懒渲染
await listFrame.locator('.procurement-workspace-tabs .layui-tab-title li[lay-id="applications"]').click();
await expect(listFrame.locator('.layui-table-main tbody tr').first()).toBeVisible();

// 行内按钮
const row = listFrame.locator('.layui-table-main tbody tr', { hasText: 'CGSQ-' }).first();
await row.locator('[lay-event="edit"]').click();

// 顶层 layer 中的弹窗 iframe
const dlg = page.locator('.layui-layer-iframe iframe[src*="procurementApply/edit.html"]');
await dlg.waitFor();
const editFrame = page.frameLocator('.layui-layer-iframe iframe[src*="procurementApply/edit.html"]');
await editFrame.locator('#applicationForm').waitFor();

// 顶层 layer 按钮
await page.locator('.layui-layer-btn0').click(); // 保存草稿
```

---

## 7. 可复用测试工具 / 测试数据

### 7.1 现有 `automation/`（HTTP 层，已可用）
| 文件 | 作用 | 复用方式 |
|---|---|---|
| `automation/probe-login.js` | 纯 Node `fetch` 登录：`verification.do` → `userLogin.do`（MD5 + `qwe!@#`）→ `select.do` 打印平台/角色 | 可提取 cookie jar + `req()` 作为 API 级前置/断言工具；账号 `cy-cgb-jbr`/`Hc1234` |
| `automation/probe-goto.js` | `gotoIndex.do` → 取外壳 HTML → 落盘 `index-session.html`；打印跳转地址 | 生成/校验“角色→平台→外壳 URL”链路 |
| `automation/probe-menu.js` | `gotoIndex` 后 `GET /nodeJs/menu_Json`，落盘 `menu-<user>.json` | **每轮 E2E 前取菜单，断言目标菜单 code 存在**；也可当菜单变更回归 |
| `automation/menu-cy-cgb-jbr.json` | cy-cgb-jbr 真实菜单（96 项） | 角色菜单差异对比基准 |
| `automation/index-session.html` | 真实外壳 HTML 快照 | 离线核对 shell DOM/脚本；注意是快照不可当运行页 |
| `automation/package.json` + `node_modules/playwright-core@1.65.1` | 依赖 | **只有 playwright-core，没有 `playwright` 包/浏览器**；需 `npm i playwright` 或 `playwright-core` + `channel:'chrome'`（本机 Chrome/Edge）；不建议再装一套依赖到项目根 |

### 7.2 源码内前端单测（可作为契约/数据构造参考，非 E2E）
- 运行方式：仓库根执行 `node --test <path>`（Node 18+，`node:test`；`.cjs`/`.js` 均可，见 `openresty/P3_FRONTEND_IMPLEMENTATION_SUMMARY.md:75` 与各测试头注释）。例：
  - `node --test openresty/nginx/html/HospitalProcurement/view/procurementApply/tests/*.test.js`
  - `node --test openresty/nginx/html/HospitalProcurement/view/procurementMethodConfirm/tests/*.test.js`
  - `node --test openresty/nginx/html/DisciplineInspection/view/projectTrackingSingle/tests/*.test.cjs`
- 本流程可直接参考的测试：
  - `procurementApply/tests/procurementApplyApi.test.js`、`procurementApplyForm.test.js`、`procurementApplyList.test.js`（payload/字段/状态/列表行为契约；`buildDraftPayload` 断言可直接作为造数模板）
  - `packageManagement/tests/packageManagementApi.test.js`、`packageManagementList.test.js`
  - `procurementMethodConfirm/tests/procurementMethodApi.test.js`、`procurementMethodEditor.test.js`、`procurementMethodStore.test.js`、`menuConfiguration.test.js`
  - `executionApply/tests/executionApplyApi.test.js`、`executionApplyPage.test.js`
  - `procurementRequirementReview/tests/pageStructure.test.js`（选择器/文案/`lay-event` 断言，可当“页面结构契约”）
  - `procurementRequirement/tests/*.test.js`
  - `auditManagement/tests/auditManagementUx.test.js`
  - `businessApproval/personal/tests/toCompletePage.test.js`（**42KB**，审批表单字段/校验/提交 body 的完整契约，造数首选）、`businessApproval/tests/approvalScanSign.test.js`、`businessData/tests/*`
  - `hospitalProcurement/marketResearchManage/surveyArgument/tests/*`、`surveyProject/tests/techTemplateNature.test.js`
  - `procurementWorkbench/tests/*`（moduleRegistry/hashRouter/frameManager/taskCenter/dashboard 契约）
- 这些测试都用 `vm.runInNewContext` + mock `appCommon/ajax`/DOM，**不是浏览器测试**，但可以复用其中的：
  - 接口 URL 常量、payload 字段名、状态枚举、按钮事件名、菜单 code；
  - 断言正则（如 `pageStructure.test.js` 的 id/文案清单）；
  - 造数思路（例如 `procurementApplyApi.test.js` 的 reserveItems/attachments 结构）。
- 测试数据：无独立 fixture 目录；数据以测试内联对象为主。E2E 真正造数建议走接口（登录后 POST 业务接口）或用 `db/SQL/cy_测试人员与角色配置.sql`、`cy_权限收束_角色菜单.sql` 中的测试账号/角色配置（只读参考，勿在测试中改库）。

### 7.3 建议的最小 POM 清单（落地时）
- `helpers/session.js`：复用 probe 的 cookie jar + login/gotoIndex/menu 三个函数。
- `helpers/shell.js`：`openMenu(page, code)`（点 `[node-id]` + 等 `.mainIframe` src 变化）、`switchTab`、`withDialog(page, srcPart)`。
- `pages/procurementApply.js`、`packageManagement.js`、`marketResearch.js`、`requirement.js`、`audit.js`、`review.js`、`method.js`、`execution.js`、`approval.js`、`discipline.js`。
- 断言层优先用 `data-testid` 不现实（源码没有），统一用本文档的 id/idName/lay-event 常量表。

---

## 8. 实际读过的文件清单（相对 `D:\Desktop\HuiZhouProject`）

**索引/外壳**
- `openresty/nginx/html/HospitalProcurement/index.html`（全量）
- `openresty/nginx/html/HospitalProcurement/components/renderPublickHead/renderPublickHead.js`
- `openresty/nginx/html/HospitalProcurement/components/zhongMenu/zhongMenu.js`（关键段）
- `openresty/nginx/html/HospitalProcurement/static/ajax-global-config.js`
- `openresty/nginx/html/HospitalProcurement/menu.css`（间接）
- `openresty/nginx/html/HospitalProcurement/disciplineInspection.html`（头部）
- `openresty/nginx/html/DisciplineInspection/index.html`（头部）、`index.js`（关键段）
- `openresty/nginx/html/Register/public/newLogin/user_login_2.html`（选择器 grep）

**采购申请 / 分包**
- `.../view/procurementApply/list.html`（1-48、48-237、266-385、860-949、890-950 等）
- `.../view/procurementApply/edit.html`（选择器提取 + uploader 行）
- `.../view/procurementApply/reserveSelect.html`、`view.html`、`outsidePlanReserveEdit.html`（选择器提取）
- `.../view/procurementApply/procurementApplyApi.js`（常量、40-110、420-492）
- `.../view/packageManagement/index.html`、`index.js`（1-120）
- `.../view/packageManagement/editor/index.html`（全量）
- `.../view/packageManagement/packageManagementApi.js`（URL 常量/url 行）

**市场调研**
- `.../surveyProject/list.html`、`list.js`（弹窗/导航/事件）
- `.../surveyProject/edit.html`（选择器提取）、`notice.html`、`participate.html`、`replies.html`、`indexUpload.html`、`techUpload.html`
- `.../surveyResult/list.html`、`list.js`、`detail.html`
- `.../surveyArgument/list.html`、`list.js`（事件映射）
- `.../surveyArgument/extract.html`（980-1012）、`fill.html`、`pick.html`、`makeup.html`、`schedule.html`、`postpone.html`、`situation.html`、`report.html`、`result.html`、`reportSignatureQr.html/js`、`reportSignatureScan.html/js`
- `.../announcementManage/list.html`、`add.html`、`noEdit.html`、`noEditView.html`、`tobeEdited.html`、`uploadFileBySupplier.html`、`js/list.js`、`js/mulView.js`、`js/RoleCodeCommon.js`、`js/replyDetailTableCommon.js`
- `.../finalPurchaseRequire/list.html`、`list.js`
- `.../projectDemonstrate/**/list.js`（businessTypeUtil 映射、论证弹窗）
- `.../preSelectCommon.js`

**采购需求编制 / 审计 / 审查 / 方式分配 / 执行**
- `.../procurementRequirement/index.html`、`index.js`、`editDocument.html`、`editDocument.js`（url 行）、`chooseTemplate.html/js`、`onlyofficeDocument.html/js`、`procurementDocumentPersist.js`、`compileStatus.js`
- `.../view/auditManagement/index.html`、`index.js`、`detail.html`、`detail.js`、`auditManagementApi.js`（全量关键段）
- `.../view/procurementRequirementReview/index.html`、`index.js`（关键段 1610-1689）、`review/index.html`、`review/index.js`（url/选择器）、`tests/pageStructure.test.js`
- `.../view/procurementMethodConfirm/index.html`、`index.js`、`editor/index.html`、`procurementMethodApi.js`（常量）
- `.../view/executionApply/list.html`、`edit.html`、`view.html`、`executionApplyApi.js`（常量/url）

**工作台 / 审批**
- `.../view/procurementWorkbench/index.html`、`index.js`（grep）、`config/runtimeConfig.js`、`config/moduleRegistry.js`、`modules/taskCenter/index.html`、`modules/processQuery/index.html`、`modules/dashboard/index.html`
- `.../view/businessApproval/approvalCommon.js`、`approvalScanSign.js`、`businessTypeUtil.js`、`personal/todoTaskList.html/js`、`personal/toCompletePage.html/js`（关键段）、`department/todoTaskList.html/js`、`personal/completedTaskList.html`、`finishedTaskList.html`、`commonQuery/queryList.js`、`scanSign/approvalTaskSignatureScan.html`
- `.../view/businessApproval/businessData/businessDataModel.js`、`businessDataRenderer.js`（grep）

**纪检**
- `.../DisciplineInspection/view/projectList/index.html`、`index.js`（关键段 505-624、660-685、755-830、1240-1260）
- `.../DisciplineInspection/view/supervisorManage/index.html`、`index.js`（关键段）
- `.../DisciplineInspection/view/purchaseAudit/index.html`、`index.js`、`detail.html/js`（grep）、`review.html/js`（grep）、`purchaseAuditApi.js`、`reportEditor`、`onlyofficePreview`
- `.../DisciplineInspection/view/purchaseAuditTemplate/index.js`、`purchaseAuditTemplateApi.js`
- `.../DisciplineInspection/view/projectTrackingList/index.html`、`projectTrackingApi.js`
- `.../DisciplineInspection/view/otherAudit/index.js`、`auditSummary/index.js`（grep）

**公共/上传组件**
- `.../view/common/businessCommonJS.js`（380-489）、`attachmentUploader.js`（头部+默认配置）、`attachmentData.js`（头部）、`qaMultiFile.js`（头部+upload 段）
- `openresty/nginx/html/HospitalProcurement/components/renderPublickHead/target/package.js`（`fileUploadInit`/`_defualUploadConfig`/`popDialog`/`isTop` 段）

**测试/自动化/菜单证据**
- `automation/package.json`、`probe-login.js`、`probe-goto.js`、`probe-menu.js`、`menu-cy-cgb-jbr.json`、`index-session.html`（快照存在性）
- `HospitalProcurement/view/*/tests/*`（目录清单 + 抽读 `procurementApplyApi.test.js`、`dashboardContract.test.js`、`menuConfiguration.test.js`、`pageStructure.test.js`、`approvalScanSign.test.js` 头部）
- `logs/NodeJsDynamicControl.log-*`（grep menu_Json 响应，提取 menuCode/url/parentId）
- `db/SQL/cy_*`（菜单/角色补丁 grep：`gov-survey-menu*.sql`、`cy_权限收束_角色菜单.sql`、`cy_纪检监察平台*.sql` 等）
- `openresty/P3_FRONTEND_IMPLEMENTATION_SUMMARY.md`（测试运行方式）
- `hospital-procurement/docs/采购工作台配置前后端联调说明.md`、`产品库-…方案.md`（BT13/menu 线索）
- `openresty/AGENTS.md`、`openresty/nginx/html/HospitalProcurement/AGENTS.md`（前端规范：必须用 HCUI.datagrid/popDialog/datePicker、ES5、iframe 架构）

> 未读/未覆盖：政府采购平台 `GovernmentProcurement` 的对应页面（结构与 HP 高度同构，菜单在 `view/marketResearchManage/` 等）、`operation_platform`/`ServicePlatform` 的后台管理页、ueditor 上传配置细节、OnlyOffice 服务端配置。若测试需要覆盖政采前置流程，建议按本文件同法对 `GovernmentProcurement` 再跑一遍（其菜单 code 为 `GR_PC_*`/`1900*`，见 `db/SQL/cy_gov_deploy/patches/gov-20260826/gov-survey-menu*.sql`）。
