# 环境 / 登录链路验证报告（本地环境）

> 验证对象：`http://127.0.0.1`（本地 nginx + 各 Java 服务）
> 验证时间：2026-11-18
> 验证方式：纯 HTTP 客户端（Python urllib + CookieJar，等价于浏览器带 cookie 请求）实测，只读，不修改任何代码/数据库/服务。
> 账号：`cy-*` 见 `db/SQL/cy_测试人员与角色配置.sql`；其余测试账号密码按团队测试账号约定（本报告不记录任何密码明文）。
> 约束：全程只访问 127.0.0.1，未访问 172.16.x 线上/测试环境。

---

## 0. 结论速览（TL;DR）

1. **完整链路已跑通**：登录接口 → `select.do` 拿平台/角色（AES 密文）→ `gotoIndex.do` 拿目标系统入口 URL → 目标系统首页 → `nodeJs/menu_Json` 拿动态菜单。四个环节均有 HTTP 实测证据。
2. **登录成功后前端实际跳卡片页** `/Register/public/selectPlatform2/selectPlatform_2.html`（登录页写了 `localStorage.websiteType='2'`），旧版下拉页 `/Register/system/selectPlatform/selectPlatform.html` 仍在但 UI 不再走它。
3. **「采购交易系统」= `prjCode_PR_NGR`**，入口 `/HospitalProcurement/index.html`；后台 `getUserBasicInfo` 返回 `"prjCode":"prjCode_PR_NGR"`，角色由所选 roleCode 决定。
4. **选平台/进系统只有两个接口**：`GET/POST /Register/SelectPlatformAction/select.do`、`POST /Register/SelectPlatformAction/gotoIndex.do`；`changePlatForm.do` 只用于「切换平台」清 token，不是进入接口。
5. **菜单接口**：`GET /nodeJs/menu_Json`（NodeJsDynamicControl，39001），返回 `{success,msg,type:"menu",content:[...]}`，菜单项 `{id,parentId,level,sort,menu_name,url,menuCode,iconCls,type}`；**依赖 `userLoginInfo` cookie 里已写入 prjCode/roleCode**，所以必须先 `gotoIndex` 再取菜单。
6. **鉴权只认 `userLoginInfo` cookie**：实测只带 `userLoginInfo`（不带 `token`）即可正常取菜单和业务接口；只带 `token` 则被拒。`token` cookie 是 1 年长效的单点登录标记，不是本链路必需。
7. **最稳自动化路径**：Playwright 用 UI 登录（验证码填万能码 `qwe!@#`）→ UI 卡片页按「平台名 + 角色名」点「进入」→ 进 HP 首页 → 断言 `menu_Json`；需要复用会话时导出 `storageState`。不建议手工拼 `userLoginInfo`（值带引号 + 含 `/+=`，易被编码破坏）。
8. **本地环境缺口**：`政府采购` 平台后端未就绪（nginx 502），`服务平台`/`运营平台` 接口路径与 HP 不同；本机只应把 `采购交易系统 + 纪检监察平台` 当完整可验证链路。

---

## 1. 验证环境状态

| 入口 | 结果 | 说明 |
|---|---|---|
| `/Register/public/newLogin/user_login_2.html` | 200 | 登录页正常 |
| `/Register/login/verification.do` | 200 image/png | 验证码接口正常，会种 `JSESSIONID` |
| `/Register/login/userLogin.do` | 200 JSON | 登录可用 |
| `/Register/SelectPlatformAction/select.do` | 200 JSON | 平台/角色可用 |
| `/Register/SelectPlatformAction/gotoIndex.do` | 200 JSON | 进入系统可用 |
| `/HospitalProcurement/index.html` | 200 | HP 首页正常 |
| `/nodeJs/menu_Json` | 200 JSON | 动态菜单正常 |
| `/HospitalProcurement/basicinfo/userinfo/getUserBasicInfo` | 200/500 | 登录后 200，未登录 500 |
| `/GovernmentProcurement/index.html` | 200（静态） | 但同域业务接口 502，GOV 后端未就绪 |
| `/DisciplineInspection/index.html` | 200 | 纪检监察平台前端正常 |
| `/jjjc/health` | `{"status":"UP"}` | 纪检后端健康 |

> 结论：本地链路以 `采购交易系统(HP, prjCode_PR_NGR)` 和 `纪检监察平台(prjCode_PR_JJJC)` 为准；`政府采购` 只有在 GOV 服务起来后才可验证。

---

## 2. 链路时序（实测）

```
[1] GET  /Register/public/newLogin/user_login_2.html        → 200，种 JSESSIONID(/Register/)
[2] POST /Register/login/userLogin.do                        → 200 {"code":"200","success":true}
        form: username / password=MD5(明文) / checkCode=qwe!@# / SimplePwd=0
        Set-Cookie:
          JSESSIONID=...; Path=/Register/; HttpOnly
          userLoginInfo="<AES base64>"; Version=1; Path=/; HttpOnly   ← 会话级(无 Expires)
          token=<AES base64>; Expires=+1年; Path=/; HttpOnly
[3] 前端 JS 跳转 /Register/public/selectPlatform2/selectPlatform_2.html
[4] GET  /Register/SelectPlatformAction/select.do            → 200 {"success":true,"data":{platform:[...],roleCode:[...]}}
[5] POST /Register/SelectPlatformAction/gotoIndex.do         → 200 {"success":true,"data":"/HospitalProcurement/index.html?token=<GUID>"}
        form: platform=<AES(prjCode)> / roleCode=<AES(roleCode)> / macAddress / ipAddress(可空)
        ★ 该接口会重写 userLoginInfo cookie，写入 prjCode、roleCode
[6] GET  /HospitalProcurement/index.html?token=<GUID>        → 200
[7] GET  /nodeJs/menu_Json?…                                 → 200 {"success":true,"content":[96 条菜单]}
        （依赖 userLoginInfo cookie 中 userId+prjCode+roleCode，读 redis key userId_prjCode_roleCode）
[8] 用户点菜单 → changeView(title,url,id) → iframe src=url → 业务页面
```

---

## 3. 登录接口（实测）

**接口**：`POST /Register/login/userLogin.do`
**Content-Type**：`application/x-www-form-urlencoded`

| 参数 | 值/说明 |
|---|---|
| `username` | 登录名，如 `cy-cgb-jbr` |
| `password` | **大写/小写 MD5 十六进制**（= `MD5(明文)`），服务端会再 MD5 一次 |
| `checkCode` | 验证码；**万能码 `qwe!@#` 稳定可用** |
| `SimplePwd` | 固定传 `0`（前端硬编码） |

**成功响应**：
```json
{"code":"200","data":"null","success":true,"mgs":"登录成功"}
```

**失败响应实测**：
| 场景 | 响应 |
|---|---|
| 验证码错 | `{"code":null,"data":3,"success":false,"mgs":"验证码错误"}` |
| 密码错 | `{"code":"200","data":null,"success":false,"mgs":"用户名或密码错误"}` |

**万能码稳定性**：对 9 个账号 × 每个 3 次独立会话共 27 次登录，`qwe!@#` 全部成功（另加各角色流程登录共 50+ 次），**稳定可用**。注意服务端校验验证码后会 `httpSession.invalidate()`，因此每次登录前建议先 GET 一次登录页/验证码接口拿新 `JSESSIONID`，不要复用旧 session。

**游客/无 cookie 表现**（可用于自动化负例断言）：
- `select.do` 无 cookie → `{"success":false,"mgs":"系统异常"}`
- `menu_Json` 无 cookie → `{"success":false,"msg":"cookie不存在，请重新登陆！","content":{}}`
- 业务接口无 cookie → HTTP **500** `{"success":false,"message":"没有相关权限。"}`

---

## 4. 选平台流程（重点）

### 4.1 页面

登录成功后前端按 `localStorage.websiteType=='2'` 跳：
`/Register/public/selectPlatform2/selectPlatform_2.html`（卡片页，**当前实际 UI**）。
旧页面 `/Register/system/selectPlatform/selectPlatform.html`（下拉页）仍存在，但非主路径。

**卡片页 DOM 结构**（`selectPlatform_2.js` 动态渲染，自动化选择器以此为准）：

```html
<div class="body-con">
  <div class="item">
    <div class="item-left">…图标…</div>
    <div class="item-center">
      <div class="platform">采购交易系统</div>          <!-- 平台名 -->
      <div class="roleCode">
        <input type="radio" name="roleCode0" value="<AES(roleCode)>" title="采购执行部门主任" checked>
        <input type="radio" name="roleCode0" value="<AES(roleCode)>" title="专家评委">
      </div>
    </div>
    <div class="item-right" data-i="0" data-platform="<AES(prjCode)>">进入</div>
  </div>
  …
</div>
```

- 卡片顺序 = `select.do` 返回 `platform` 数组顺序；`data-i` = 该平台在数组中的下标。
- 每个平台卡片下渲染该平台的角色 radio，**默认选中第一个（`j==0`）**。
- 点 `.item-right` → `gotoIndex(platform, $('input[name=roleCode'+i+']:checked').val())` → `POST gotoIndex.do` → `window.location.href = result.data`。
- 特殊平台 `uaJWMcBEwludifObbpORAg==` 走 `StoreLoginTokenAction/getUserToken.do`（非本院链路，忽略）。

### 4.2 接口 1：取平台与角色

`GET`（前端 `ajaxFunction` 未指定 type，GET/POST 均实测可用）
`/Register/SelectPlatformAction/select.do`

**必须带 `userLoginInfo` cookie**。返回示例（`cy-cgb-jbr`，密文为 AES，**原样透传给 gotoIndex，禁止解密/改写**）：

```json
{
  "code": null,
  "success": true,
  "mgs": "获取成功",
  "data": {
    "message": "获取成功",
    "platform": [
      {"OBWr2R+Tgi3kgApMN/qroQ==": "政府采购"},
      {"p4uHxmjYXoF/P0EBpcknqQ==": "采购交易系统"},
      {"DDnpxZd7MqCE6OvcNUZFNQ==": "服务平台"}
    ],
    "roleCode": [
      {"DDnpxZd7MqCE6OvcNUZFNQ==": "服务平台", "Pwmml0HH+5nhm+HfiZn+vg==": "采购执行部门经办人"},
      {"If3noBx1bZCQTgM4lPC98Z2v/yraI9ruGjM0Fe9Mp7Q=": "采购执行部门经办人", "OBWr2R+Tgi3kgApMN/qroQ==": "政府采购"},
      {"p4uHxmjYXoF/P0EBpcknqQ==": "采购交易系统", "If3noBx1bZCQTgM4lPC98Z2v/yraI9ruGjM0Fe9Mp7Q=": "采购执行部门经办人"}
    ]
  }
}
```

结构说明：
- `platform[i]`：单键 map，`key = AES(prjCode)`，`value = 平台显示名`。
- `roleCode[j]`：**双键 map**，一个 `AES(prjCode)→平台名`，一个 `AES(roleCode)→角色名`（键顺序不固定，不能假设第一个键是平台）。
- 取某平台的角色：遍历 `roleCode`，找包含该平台密文 key 的 map，另一个 key 即角色密文。
- AES 密钥固定，密文在**不同用户/不同请求间可复现**（同一 prjCode/roleCode 密文一致），但自动化仍建议动态取，不要硬编码。
- 平台/角色只列「字典有名称且角色有效」的组合；平台无可用角色时不会上架。

### 4.3 接口 2：进入系统

`POST /Register/SelectPlatformAction/gotoIndex.do`

| 参数 | 说明 |
|---|---|
| `platform` | `select.do` 返回的 `AES(prjCode)` 密文 |
| `roleCode` | `select.do` 返回的 `AES(roleCode)` 密文 |
| `macAddress` | 可空；仅「专家登录限制」开启且角色属于限制角色时才强制（当前本地实测空值可进） |
| `ipAddress` | 同上 |

**成功响应**：
```json
{"code":null,"success":true,"mgs":"获取跳转地址",
 "data":"/HospitalProcurement/index.html?token=D8FFD01A-B1CE-D952-55F6-C122371FCD7C"}
```

**关键副作用**：`gotoIndex` 成功后会把 `prjCode`、`roleCode` 写回 `userLoginInfo` cookie（AES 重加密）。**只有做过这一步，`nodeJs/menu_Json` 才能拿到菜单**；未做时 `menu_Json` 返回 `{"success":false,"msg":"cookie里的参数错误"}`。

**`changePlatForm.do`**（`POST /Register/login/changePlatForm.do`）只是「切换平台」时删 redis 的 `userId_prjCode` token，成功后前端跳 `selectPlatform_2.html?platform=…`；它**不返回目标系统 URL**，不是进入接口。

### 4.4 平台 → 入口 URL / prjCode 对照（实测 + 仓库文档）

| 选平台卡片 | 目标系统 | gotoIndex 返回的 data | prjCode | 本地可用性 |
|---|---|---|---|---|
| **采购交易系统** | 院内采购主引擎 `hospital-procurement` | `/HospitalProcurement/index.html?token=<GUID>` | **`prjCode_PR_NGR`**（`getUserBasicInfo` 实测确认） | ✅ 完整可用 |
| 纪检监察平台 | `DisciplineInspection` | `/HospitalProcurement/view/disciplineInspection/index.html?token=<GUID>` → 该页 JS 立即 `location.replace('/DisciplineInspection/index.html'+search)` | **`prjCode_PR_JJJC`**（实测确认） | ✅ 完整可用 |
| 政府采购 | `GovernmentProcurement` | `/GovernmentProcurement/index.html?token=<GUID>` | `prjCode_PR_GOV`（见 `db/SQL/cy_政府采购平台角色权限.sql`） | ⚠️ 前端 200，后端接口 502 |
| 服务平台 | `ServicePlatform` | `/ServicePlatform/index.html?token=<GUID>` | 未从运行时确认（接口与 HP 不同） | ⚠️ 仅首页可开 |
| 运营平台 | `operation_platform` | `/operation_platform/index.html?token=<GUID>` | 未从运行时确认 | ⚠️ 仅首页可开 |
| 随行平台 | 外部系统 | `sx.url` 拼接（`prjCode_PR_SX` 特判） | `prjCode_PR_SX` | 无 SX 账号，未验证 |

> **结论：任务里说的「采购交易系统 / 医院采购企业采购平台」= `/HospitalProcurement/` = `prjCode_PR_NGR`。**
> `gotoIndex` 返回的 `?token=<GUID>` 对 HP 仅占位：实测去掉 query 直接开 `/HospitalProcurement/index.html` 仍 200 且菜单正常（鉴权靠 cookie）。GOV 分支该 token 才会写入 redis 供跨系统登录。

---

## 5. HP 首页与动态菜单

### 5.1 首页事实

`/HospitalProcurement/index.html`（标题「采购交易系统」）是传统 iframe 多页签壳：
- 左侧菜单容器 `#menu`，由 `components/zhongMenu/zhongMenu.js` 渲染；
- 中央 `layui-tab`，`createFrame(title,url)` 生成 `<iframe class="mainIframe" src="url">`；
- `changeView(subtitle,url,nodeId)` = tabDelete + tabAdd + tabChange；
- 首页初始化额外调用 `changeView("欢迎使用","/HospitalProcurement/view/welcome/welcome.html","welcome")`；
- 顶部「切换平台」调 `changePlatForm.do`，「修改密码」「退出」为独立接口；
- `getUserBasicInfo` 被用于把 userId 写 cookie 并显示用户名。

### 5.2 菜单接口

`GET /nodeJs/menu_Json`（同域路径，实际由 NodeJsDynamicControl 提供；HP 前端写法 `../../nodeJs/menu_Json`）

**前置条件**：`userLoginInfo` cookie 已由 `gotoIndex` 写入 `userId`、`prjCode`、`roleCode`。
**取数逻辑**：`redis.get(userId + "_" + prjCode + "_" + roleCode)`（该 key 在登录时写入，**TTL 48 小时**）。

**返回结构（实测 `cy-cgb-jbr`，96 条）**：

```json
{
  "success": true,
  "msg": "返回menu成功",
  "type": "menu",
  "content": [
    {
      "level": "0",
      "menu_name": "专家抽取",
      "menuCode": "0000049",
      "fn": "",
      "id": "0000049",
      "sort": "4",
      "iconCls": "fa fa-random menuIcon",
      "type": "menu",
      "url": "view/tenderManagement/expertManagement/index.html",
      "parentId": "0"
    }
  ]
}
```

菜单项字段：`id`（唯一，建议作自动化 key）、`parentId`（`"0"` 为根）、`level`（0/1/2）、`sort`、`menu_name`、`url`（可能为空=仅分组）、`menuCode`、`iconCls`、`type`。
菜单是**扁平数组**，前端按 `pid` 组装树。

**失败响应**（前端会自动 3 秒后跳登录页，自动化需监听）：
- 无 cookie：`{"success":false,"msg":"cookie不存在，请重新登陆！","type":"menu","content":{}}`
- 有 cookie 但未选平台/角色：`{"success":false,"msg":"cookie里的参数错误",...}`
- redis 菜单过期（>48h）：`{"success":false,"msg":"获取菜单数据异常，请重新登陆1！",...}`

### 5.3 菜单 URL → iframe src 拼接规则（决定自动化如何直达）

前端点击菜单：`changeView(title, item.url, item.id)` → `iframe.src = item.url`（**原样**）。

因此「直接可打开 URL」：
```
if item.url startswith("/")  →  http://127.0.0.1 + item.url
else                         →  http://127.0.0.1/HospitalProcurement/ + item.url
```
例外：菜单里有少量 **Windows 反斜杠** URL（如 `view\tenderManagement\tenderInitiation\tenderInitiationPage.html`），浏览器一般能容错，自动化构造 URL 时建议先把 `\` 统一替换为 `/`。

**实测**：以下 view 页直接 GET 均 200（无需登录 cookie，因为静态文件由 nginx/应用静态资源返回）：
`view/procurementApply/list.html`、`view/packageManagement/index.html`、`view/hospitalProcurement/marketResearchManage/surveyProject/list.html`、`view/procurementWorkbench/index.html`、`view/auditManagement/index.html`、`view/procurementRequirementReview/index.html`、`view/businessApproval/personal/todoTaskList.html`、`view/disciplineInspection/index.html`、`/DisciplineInspection/index.html`、`/DisciplineInspection/view/supervisorManage/index.html` 等。

> ⚠️ **关键坑：页面 HTML 200 ≠ 有权限**。view 页 HTML 不校验 cookie；页面内部 Ajax 才校验。实测：
> - 带 cookie：`GET /HospitalProcurement/basicinfo/userinfo/getUserBasicInfo` → 200 `success:true`
> - 无 cookie：同一接口 → **HTTP 500** `{"success":false,"message":"没有相关权限。"}`
> - `POST /HospitalProcurement/hospitalPurchaseRequest/page`（采购申请列表数据）：带 cookie → `{"success":true,"data":{"total":0,…}}`；无 cookie → 500 无权限。
> 自动化断言应落在数据接口/页面内关键 DOM，而不是只看 iframe 页 200。

---

## 6. 重点菜单 → URL 摘录（自动化直达清单）

以下均取自 `menu_Json` 实测返回，URL 为「可直接拼接打开」形式。

### 6.1 需求发起 / 承办部门经办（`cy-cbbm-jbr`，`NGP_CBBM_JBR`，41 条）

| 菜单（路径） | id | URL |
|---|---|---|
| 采购工作台 | `M000005` | `/HospitalProcurement/view/procurementWorkbench/index.html` |
| 采购管理 > 采购申请管理 | `0000006000001` | `/HospitalProcurement/view/procurementApply/list.html` |
| 采购管理 > 采购需求在线编制 | `0000006000005` | `view/procurementRequirement/index.html` |
| 采购管理 > 采购方式分配 | `0000006000003` | `/HospitalProcurement/view/procurementMethodConfirm/index.html` |
| **采购管理 > 分包管理** | `0000006000002` | `/HospitalProcurement/view/packageManagement/index.html` |
| 采购管理 > 采购执行申请管理 | `0000006000004` | `/HospitalProcurement/view/executionApply/list.html` |
| 采购管理 > 采购需求审查管理 | `0000006000008` | `/HospitalProcurement/view/procurementRequirementReview/index.html` |
| 采购管理 > 审计管理 | `0000006000009` | `/HospitalProcurement/view/auditManagement/index.html` |
| **市场调研管理 > 调研项目管理** | `0000001000001` | `/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html` |
| 市场调研管理 > 调研结果管理 | `0000001000006` | `/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyResult/list.html` |
| 市场调研管理 > 调研论证管理 | `0000001000007` | `/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyArgument/list.html` |
| 合同备案 | `5051` | `/HospitalProcurement/view/contractFile/contractFileManagement.html` |
| 紧急采购 > 申请/分包/执行申请 | `0000041000007/8/9` | `/HospitalProcurement/view/emergencyPurchase/{application,package,execution}/index.html` |
| 零星采购 > 申请/分包/执行申请 | `0000048000001/2/3` | `/HospitalProcurement/view/sporadicPurchase/{application,package,execution}/index.html` |
| 产品库管理 > 产品采购申请/分包/执行申请 | `0000046000007/8/9` | `/HospitalProcurement/view/productLibrary/priceUnreasonable/{application,package,execution}/index.html` |
| 履约与验收管理 > 维修工单/项目验收/报废登记 | `M000001000003/2/4` | `/HospitalProcurement/view/{maintenanceWorkOrder,fulfillmentAcceptance,scrapApplication}/index.html` |
| 电话议价 | `NGR_PHONE_NEGOTIATION_LIST` | `/HospitalProcurement/view/phoneNegotiationShell/index.html` |

### 6.2 采购办经办（`cy-cgb-jbr`，`NGP_PURCHASEAGENT`，96 条 / 19 根）

| 菜单（路径） | id | URL |
|---|---|---|
| 采购工作台 | `M000005` | `/HospitalProcurement/view/procurementWorkbench/index.html` |
| 招标管理 > 招标发起 | `100000005` | `view/tenderManagement/tenderInitiation/tenderInitiationPage.html`（原文含反斜杠） |
| 招标管理 > 编制招标文件 | `100000009` | `view/tenderManagement/editTender/editTenderFileList.html` |
| 招标管理 > 发布招标公告 | `100000010` | `/HospitalProcurement/view/tenderManagement/publishBidAnno/tenderAnnoList.html` |
| 招标管理 > 质疑答复 / 投诉处理 | `100000001/3` | `view/questionAndAnswer/answerPage.html` / `complaintHandlingPage.html` |
| 招标管理 > 澄清变更公告 | `109` | `view/tenderManagement/clarifyCorrectionAnno/correctionAnnoList.html` |
| 开标管理 > 开标会议 | `301` | `view/openBidManage/openBidMeetingPage.html` |
| 评标管理 > 评标 / 评标结果 | `4011/4012` | `view/evaluateBid/{evaluate/evaluateBid,evaluateResult/evaluateResult}.html` |
| 定标管理 > 中标人确认 / 中标公告 / 中标通知书 | `5031/5012/5013` | `view/confirmBid/...` |
| 业务审批 > 个人待办 / 科室待办 / 个人已办 / 个人办结 | `603/602/604/605` | `view/businessApproval/{personal/todoTaskList,department/todoTaskList,personal/completedTaskList,personal/finishedTaskList}.html` |
| 业务审批 > 综合查询 / 查看审批信息 | `606/607` | `view/businessApproval/commonQuery/queryList.html[?type=agency]` |
| 委托采购 > 委托采购列表 / 结果审核 / 委托协议签订 | `M000007000009/2/5` | `view/registerBuyActivity/entrustPurchasePage.html` 等 |
| 挂网采购 > 挂网采购列表 / 单一来源公示 | `001/004` | `view/registerBuyActivity/registerBuyActivityPage.html` / `view/singleSourcePublicity/singleSourcePublicityList.html` |
| 议（比）价采购 > 项目管理/邀请/审查/会议/确认成交/成交公告 | `M000008000001/2/3/4/7/13` | `/HospitalProcurement/view/negotiationPurchase/*/index.html` |
| 谈判采购 > 谈判小组/议程/邀请/成交公告/成交通知书 | `NGR_NEGOTIATION_*` | `/HospitalProcurement/view/negotiationPurchase/*/index.html` |
| 合同备案 | `5051` | `/HospitalProcurement/view/contractFile/contractFileManagement.html` |
| 模板管理 > 招投标/通用/合同/需求编制/DOCX | `17001/17002/1700000005/6/7` | `/TemplatService/…`、`/HospitalProcurement/view/template/*` |
| 采购管理 > 采购需求审查管理 | `0000006000008` | `/HospitalProcurement/view/procurementRequirementReview/index.html` |
| 公告转载 / 专家抽取 | `NGR_NOTICE_REPOST / 0000049` | `/HospitalProcurement/view/noticeRepost/index.html` / `view/tenderManagement/expertManagement/index.html` |

### 6.3 采购工作台「待办」

- 菜单入口：`采购工作台` → `/HospitalProcurement/view/procurementWorkbench/index.html`。
- 该页是**前端壳**（`moduleRegistry.js` + `mockPermissionProvider.js`，开发态 mock 权限），模块：`我的工作台 / 待办/已办 / 报表统计 / 流程查询`。
- 「待办/已办」实际 iframe 的还是原审批页：
  - `/HospitalProcurement/view/businessApproval/personal/todoTaskList.html`
  - `/HospitalProcurement/view/businessApproval/personal/completedTaskList.html`
  - `/HospitalProcurement/view/businessApproval/personal/finishedTaskList.html`
  - `/HospitalProcurement/view/businessApproval/department/todoTaskList.html`
- 待办数据接口：`POST /EbiddingBusinessApproval/workflow/task/list/todo`（HP 前端常量 `PROJECT_APPROVAL_NAME="EbiddingBusinessApproval"`）。实测该接口在本地返回 500「系统异常，请联系技术人员。」（后端审批服务/数据未就绪），**不能作为本地自动化断言点**；本地断言建议用 `getUserBasicInfo`、`hospitalPurchaseRequest/page`、`menu_Json`。
- 注意：仓库 `HospitalProcurement` 规则也标注「采购工作台菜单仅用于开发，正式上线前需迁移到后端菜单权限」。

---

## 7. 多角色验证（登录 → 选平台 → 菜单差异）

> 说明：角色名取 `select.do` 返回的显示名；`roleCode/prjCode` 由进入后 `getUserBasicInfo` 实测返回；菜单条数为 `menu_Json` 实测。

| 账号 | 可选平台 | 采购交易系统内角色 | roleCode | prjCode | 菜单数 | 关键菜单/差异 |
|---|---|---|---|---|---|---|
| `zhangsan` | 采购交易系统 | 需求科室申请人 | `REQ_STAFF` | NGR | 5 | 采购工作台、**采购申请管理**、商品库浏览（最精简的申请入口） |
| `cy-cbbm-jbr` | 政府采购、采购交易系统 | 承办部门经办人 | `NGP_CBBM_JBR` | NGR | 41 | **市场调研管理**（调研项目/结果/论证）、**采购管理**（采购申请、需求编制、方式分配、**分包管理**、执行申请、需求审查、审计）、紧急/零星采购、履约验收、产品库、电话议价 |
| `cy-cgb-jbr` | 政府采购、采购交易系统、服务平台 | 采购执行部门经办人 | `NGP_PURCHASEAGENT` | NGR | 96 | 招标/开标/评标/定标/业务审批待办/委托/挂网/谈判/比价/合同/模板/公告/专家抽取全量 |
| `cy-cgb-zr` / `bailu` | 运营平台、政府采购、采购交易系统、服务平台（bailu 无政府采购） | 采购执行部门主任 | `NGP_PURCHASEAGENTLEADER` | NGR | 68 | 与经办基本同量，多审批类（个人待办）、少产品库细化项；**bailu 同平台还有第二个角色「专家评委」且默认选中**（见 7.1） |
| `cy-jjjc` | 纪检监察平台、政府采购、采购交易系统 | 纪检监察 | `NGP_SUPERVISE` | NGR | 29 | 业务审批待办/已办/办结、**采购管理 > 审计管理**、招标备案、比价/谈判查看、流程管理 |
| `jjzr` | 纪检监察平台、采购交易系统 | 纪检主任 | `JJJC_DIRECTOR_JY` | NGR | 2 | 仅「采购管理 > 采购需求审查管理」（HP 侧权限很窄；纪检主战场在纪检监察平台） |
| `sjyj` | 纪检监察平台、采购交易系统 | ①审计部干事 ②纪检监察 | `NGP_SJBGS` / `NGP_SUPERVISE` | NGR | 15 / 29 | 审计部干事：采购管理 > **审计管理**、业务审批、比价/谈判；纪检监察：同 `cy-jjjc` |
| `cy-gys1` | 政府采购、采购交易系统、服务平台 | 供应商 | `NGP_SUPPLIER` | NGR | 107 | 投标管理、保证金、中标管理、合同备案、基本信息（单位/从业人员/业绩/信用）、受邀管理、市场调研（受邀）、开标/比价/谈判查看、商品库；无采购人侧菜单 |

### 7.1 多平台 / 多角色坑（bailu 实测）

`bailu` 的 `select.do` 原始返回（节选）：
```json
{"data":{"platform":[{"ZoEy8/Tm6MrXQFVyFsxbWw==":"运营平台"},
                     {"p4uHxmjYXoF/P0EBpcknqQ==":"采购交易系统"},
                     {"DDnpxZd7MqCE6OvcNUZFNQ==":"服务平台"}],
         "roleCode":[
  {"ZoEy8/Tm6MrXQFVyFsxbWw==":"运营平台","h1AbTpa8Drs+bpYozsIF6kelZekSLP0IMs0EQg4yI15kQlRr4Zk1w3LGTLUCAQCO":"采购办主任"},
  {"DDnpxZd7MqCE6OvcNUZFNQ==":"服务平台","If3noBx1bZCQTgM4lPC98XKO43vvfpLz4XziWzhL7zk=":"采购执行部门主任"},
  {"o7yMUk1KuNr3EfD1CapsPA==":"专家评委","p4uHxmjYXoF/P0EBpcknqQ==":"采购交易系统"},
  {"p4uHxmjYXoF/P0EBpcknqQ==":"采购交易系统","If3noBx1bZCQTgM4lPC98XKO43vvfpLz4XziWzhL7zk=":"采购执行部门主任"}]}}
```
- 「采购交易系统」卡片下有 **两个角色**：`专家评委`（`NGP_EXPERTS`，94 条菜单）与 `采购执行部门主任`（68 条）。
- 卡片页默认选中 **第一个 = 专家评委**。若自动化「点卡片不选角色」，bailu 会以专家身份进 HP，后续按采购办主任跑流程会全部失败。
- 同理 `sjyj` 的「采购交易系统」有「审计部干事 / 纪检监察」、`纪检监察平台`有「审计员 / 纪检监督员」——**必须按角色名显式选择**。

> **自动化铁律：平台按显示名定位；角色必须按 `title` 文本显式勾选，不能依赖默认选中项。**

---

## 8. 纪检监察平台专项（jjzr / sjyj / cy-jjjc）

### 8.1 入口链路

`gotoIndex(platform=纪检监察平台=AES(prjCode_PR_JJJC), roleCode)` →
`/HospitalProcurement/view/disciplineInspection/index.html?token=<GUID>`
→ 该页只有一段 JS：`window.location.replace("/DisciplineInspection/index.html" + search + hash)` →
`/DisciplineInspection/index.html`（独立前端应用，标题「纪检监察平台」）。

- 该应用菜单同样调 `GET /nodeJs/menu_Json`（`../../nodeJs/menu_Json`），依赖同一 `userLoginInfo` cookie。
- `getUserBasicInfo`：`roleCode=AUDITOR/jjjdy/JJJC_DIRECTOR…`，`prjCode=prjCode_PR_JJJC`。
- 纪检后端健康：`GET /jjjc/health` → `{"status":"UP"}`。

### 8.2 菜单（实测）

`jjzr`（纪检监察主任，`JJJC_DIRECTOR`，5 条）：
| 菜单 | URL |
|---|---|
| 纪检监察管理 > 监察项目列表 | `/DisciplineInspection/view/projectList/index.html` |
| 纪检监察管理 > **监督员管理**（纪检分配监督员） | `/DisciplineInspection/view/supervisorManage/index.html` |
| 项目全流程追踪 > 申请单列表 | `/DisciplineInspection/view/projectTrackingList/index.html` |

`sjyj` 的「纪检监察平台」有两个角色：
- 审计员 `AUDITOR`（4 条）：与上面相同，但**没有「监督员管理」**；
- 纪检监督员 `jjjdy`（4 条）：同上无「监督员管理」。
`cy-jjjc` 的「纪检监察平台」= 纪检监督员 `jjjdy`（4 条）。

### 8.3 「审计管理」是前端硬编码注入

`DisciplineInspection/index.js` 的 `appendAuditMenus()` 在菜单渲染后**前端本地追加**（后端菜单没有时）：
| 菜单 | URL |
|---|---|
| 审计管理 > 采购专项审计 | `/DisciplineInspection/view/purchaseAudit/index.html` |
| 审计管理 > 其他项目审计 | `/DisciplineInspection/view/otherAudit/index.html` |
| 审计管理 > 统计汇总与下载 | `/DisciplineInspection/view/auditSummary/index.html` |

> ⚠️ 因此「纪检/审计账号一定能看到审计管理菜单」不代表后端授权；它没有按角色/权限过滤，断言时要区分「菜单可见」与「接口可操作」。页面 URL 均可直接打开（均实测 200）。

---

## 9. Cookie / 会话 / token（实测事实）

| Cookie | 特征（实测 Set-Cookie） | 用途 |
|---|---|---|
| `JSESSIONID` | `Path=/Register/; HttpOnly`，无 Expires | 仅 Register 登录/验证码会话；登录时服务端会 `session.invalidate()` |
| `userLoginInfo` | `Version=1; Path=/; HttpOnly`，**无 Expires（会话级）**；值带双引号，长 ~302，内含 `+ / =` | **真正的鉴权凭证**：AES(userId/username/token；`gotoIndex` 后追加 prjCode/roleCode)。所有业务接口/菜单靠它 |
| `token` | `Expires=+1 年; Path=/; HttpOnly`；值无引号，长 64 | AES(loginToken)，用于单点登录标记（redis `userId_prjCode`，TTL 48h）；**本链路非必需** |

**鉴权矩阵实测**（同一登录会话，手工拼 Cookie 头请求）：

| 携带 cookie | `getUserBasicInfo` | `menu_Json` |
|---|---|---|
| 仅 `userLoginInfo` | 200 `success:true` | 200 `success:true`（96 条） |
| 仅 `token` | **500** 没有相关权限 | **失败** cookie不存在 |
| `userLoginInfo`+`token` | 200 | 200 |
| 都不带 | 500 | 失败 |

**超时/有效期**：
- 登录权限/角色/菜单写 redis，`selectPlatform` 的 `userId` 平台数据、菜单 key、单点登录 key 均 `expire = 60*60*48`（**48 小时**）。超过后菜单接口报「获取菜单数据异常，请重新登陆1！」。
- `userLoginInfo` 是会话 cookie（浏览器关闭清除；`storageState` 可持久化，但 redis 48h 后仍需重新登录）。
- `token` cookie 名义 1 年，但不能单独撑起会话；不要依赖它判断"是否登录"。
- 并发提示：同一账号重复登录会覆盖 redis `userId_prjCode` 单点登录 token；实测两个会话的 `select.do` 仍都可用，但为稳妥，**并行用例一账号一会话**。

---

## 10. 自动化最稳路径（Playwright）

### 10.1 推荐：UI 登录 + UI 选平台（最稳，抗后端加密/跳转变化）

理由：登录密码要 MD5、平台/角色参数是 AES 密文、`userLoginInfo` 是带引号的 HttpOnly cookie、登录后跳转由前端 JS 决定 —— 这些都交给真实浏览器最省事；且万能码让验证码不再是障碍。

```python
# 伪代码（Playwright Python）
page.goto("http://127.0.0.1/Register/public/newLogin/user_login_2.html")
page.fill("#username", USER)
page.fill("#password", PWD)          # 明文，前端自动 CryptoJS.MD5
page.fill("#code", "qwe!@#")         # 万能码
page.click("#loginBtn")
page.wait_for_url("**/selectPlatform_2.html")   # 等前端跳转

# 选平台 + 选角色（关键：角色按 title 显式选）
card = page.locator(".body-con .item", has=page.locator(".platform", has_text="采购交易系统"))
card.locator("input[type=radio][title='采购执行部门主任']").check()
card.locator(".item-right").click()              # 触发 gotoIndex 并 location.href
page.wait_for_url("**/HospitalProcurement/index.html*")

# 断言动态菜单（在页面上下文请求，自动带 cookie）
menu = page.evaluate("""async () => (await fetch('/nodeJs/menu_Json')).json()""")
assert menu["success"] is True and len(menu["content"]) > 0
# 或断言左侧菜单渲染
page.wait_for_selector("#menu li")

# 复用：导出登录态（userLoginInfo 会话 cookie 会被保存）
page.context.storage_state(path="state/<user>.json")
```

### 10.2 备选：纯接口登录 + 注入 cookie（快，适合批量/无浏览器）

可行性已实测（登录→select→gotoIndex→菜单全通）：
1. `POST /Register/login/userLogin.do`（`password=MD5(明文)`，`checkCode=qwe!@#`，`SimplePwd=0`），从 `Set-Cookie` 取 `userLoginInfo`（**保留值两端的双引号**）。
2. `GET /Register/SelectPlatformAction/select.do`，解析出目标平台的 `AES(prjCode)` 与其角色 `AES(roleCode)`。
3. `POST /Register/SelectPlatformAction/gotoIndex.do`（form 传 `platform`/`roleCode`），拿到 `data` 目标 URL；**响应会重写 `userLoginInfo` cookie，必须用新值**。
4. 注入新 `userLoginInfo` 到浏览器 context，或直接 HTTP 请求 `/nodeJs/menu_Json`。

**Playwright storageState 示例**（`userLoginInfo` 域 127.0.0.1、path `/`、httpOnly、session）：
```json
{"cookies":[{"name":"userLoginInfo","value":"\"<原样带引号的值>\"",
  "domain":"127.0.0.1","path":"/","httpOnly":true,"secure":false,"sameSite":"Lax"}],
 "origins":[]}
```
> 只在「性能/批量建会话」时用备选方案；日常 E2E 建议主路径用 10.1。

### 10.3 坑清单（按重要性）

1. **不要手算/解密 platform、roleCode**：它们是 AES 密文，原样回传；字段名必须是 `platform`/`roleCode`。
2. **必须先 `gotoIndex` 再取菜单**：否则 `menu_Json` 报「cookie里的参数错误」；`gotoIndex` 是唯一会把 prjCode/roleCode 写进 cookie 的入口。
3. **多角色平台不能点默认角色**：bailu 的采购交易系统默认是「专家评委」；按 `title` 文本显式 check。
4. **登录返回不是 302**：是 JSON；跳转由前端 `window.location.href` 完成，等 `wait_for_url`，不要等 click navigation。
5. **验证码万能码稳定但 session 会失效**：每次登录前重新 `goto` 登录页；失败重试时也重新走登录页，别复用旧 JSESSIONID。
6. **密码先 MD5**：接口层传 `MD5(明文)`，不是明文；明文字符串含特殊字符（`@` 等）时注意不要二次 URL 编码错误。
7. **cookie 值带引号**：`userLoginInfo` = `"..."`（引号是值的一部分），注入/校验都不要 strip，也不要 URL-encode 其中的 `+ / =`。
8. **页面 200 ≠ 已登录**：view/iframe 页静态资源无鉴权；权限断言请打数据接口（无 cookie 时 500「没有相关权限。」）。
9. **菜单加载失败会自动跳登录页**：`index.html` 在 `menu_Json` 失败时 3 秒后跳 `/Register/public/newLogin/user_login_2.html`，自动化需处理"被踢回登录页"。
10. **原生 `?token=<GUID>` 不必强求**：HP 首页去掉 token 仍正常（鉴权靠 cookie）；但建议照 UI 原样跟随 `gotoIndex` 返回 URL。
11. **iframe 内 URL 相对定位**：相对 url 以 `/HospitalProcurement/` 为基；个别菜单 URL 含反斜杠，构造 URL 时统一换成 `/`。
12. **本地 GOV 链路不可测**：政府采购后端 502；不要把「政府采购」平台放进本地必过用例。服务平台/运营平台接口与 HP 不同，亦未完整验证。
13. **采购工作台是开发态 mock**：`mockPermissionProvider` 本地放行模块，不代表真实权限；「待办」前后端接口在本机 500，不要当断言点。
14. **纪检「审计管理」是前端注入**：出现在菜单不等于后端授权；且 `/DisciplineInspection/` 与 HP 是两个前端应用，URL 前缀不同。
15. **48 小时 redis 有效期**：长跑/隔夜回归的 storageState 会失效，需重新登录；单点登录 token 同账号不要并发多会话。

---

## 11. 可复用的最小验证脚本（HTTP 版，已实测跑通）

```python
import urllib.request, urllib.parse, http.cookiejar, json, hashlib
BASE = "http://127.0.0.1"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def req(method, path, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    r = urllib.request.Request(BASE + path, data=body, method=method,
                               headers={"User-Agent": "Mozilla/5.0"})
    with op.open(r) as resp:
        return resp.read().decode("utf-8", "replace")

req("GET", "/Register/public/newLogin/user_login_2.html")          # 拿 JSESSIONID
print(req("POST", "/Register/login/userLogin.do", {                # 登录
    "username": "cy-cgb-jbr",
    "password": hashlib.md5(PWD.encode()).hexdigest(),             # PWD=测试账号密码(见测试人员与角色配置.sql，本报告不记录)
    "checkCode": "qwe!@#", "SimplePwd": "0"}))
sel = json.loads(req("GET", "/Register/SelectPlatformAction/select.do"))
# 找 采购交易系统 及其角色
pk, rk = None, None
for pm in sel["data"]["platform"]:
    for k, name in pm.items():
        if name == "采购交易系统":
            pk = k
            for rm in sel["data"]["roleCode"]:
                if pk in rm:
                    rk = next(k2 for k2 in rm if k2 != pk)         # 生产代码请按角色名选
print(req("POST", "/Register/SelectPlatformAction/gotoIndex.do",
          {"platform": pk, "roleCode": rk}))                   # 返回 HP 入口 URL
print(req("GET", "/nodeJs/menu_Json")[:300])                   # 动态菜单
```

> 该脚本对 `cy-cgb-jbr` 实测输出：登录 `success:true`；`gotoIndex` 返回 `/HospitalProcurement/index.html?token=…`；`menu_Json` 返回 96 条菜单、`prjCode=prjCode_PR_NGR`。

---

## 12. 证据留档（只读探测产物，位于系统临时目录，未写入仓库）

本次验证的原始 HTTP 响应/解析结果保存在 `%TEMP%\envprobe\`（非项目目录，可随时清理）：
- `result_cy-cgb-jbr.json`、`role_*.json`、`role2_*.json`：各角色登录/select/gotoIndex/菜单原始响应
- `menu_full_*.json`、`menu_*_*.txt`：完整菜单 JSON 与扁平化菜单
- `auth_probe.json`、`final_probe.json`、`cookie_role_probe.json`：鉴权矩阵、登录错误、todo 接口、cookie 作用域
- `discipline_pages.json`：纪检平台页面跳转与状态

项目侧未做任何代码、数据库、服务变更。
