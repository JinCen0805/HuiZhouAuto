# 采购前置流程 UI 自动化 PoC（本地环境）

本目录是"采购前置流程自动化可行性评估"的配套 PoC，只针对**本地环境** `http://127.0.0.1`，
不连接线上/测试环境（172.16.x）。

## 已实现范围（实测跑通）

| 阶段 | 方式 | 脚本 | 结果 |
|---|---|---|---|
| ① 采购申请发起：选预算计划 → 保存草稿 → 确认 | UI（Playwright） | `poc/stage1-apply.js` | 草稿 → 待分配监督员（status=22） |
| ① 纪检分配监督员 | 接口（跨系统，纪检平台） | `poc/stage2a-supervisor.js` | status 22 → 8（待分包） |
| ② 分包：新增子包 → 保存 → 确认 | UI（Playwright） | `poc/stage2b-subpackage.js`、`poc/stage2c-confirm-package.js` | status → 待调研（7），自动生成调研项目 |
| 验证 | UI | `poc/verify-stage2.js` | 申请单"待调研"、调研项目管理出现新项目 |

一条命令跑完整条演示链：

```powershell
pwsh -File .\automation\run-demo.ps1
```

## 运行前提（本地栈）

1. 本地全栈已启动：`.\start-local-project.cmd`（或 `local-stack.ps1 start-all`）。
2. `openresty\local-dev\nginx.conf` 已补 `/hospital-procurement/` 网关路由
   （2026-08 起新版 HP 页面调用 `/hospital-procurement/api/...`；本地栈原配置缺这条会 404，
   页面显示"数据接口请求异常"）。
3. 纪检平台与 registers 的 Redis DB 不一致（registers=DB9，discipline-supervision=DB7），
   会导致纪检接口 401。`run-demo.ps1` 会自动把登录 key 从 DB9 同步到 DB7；
   根治方案见评估报告"环境修复建议"。
4. 账号（密码见团队测试账号表，不写入仓库）：
   - `wanglun`（医学工程部 承办部门干事，`NGP_CBBM_JBR`）——发起/分包
   - `jjzr`（纪检监察主任，登录平台必须选"纪检监察平台"）——分配监督员
   - 也可换 `cbbm1`（医务部干事，后端分析推荐，医务部 32 条可引用预算计划）
5. 依赖：`playwright-core` + 本机 Chromium（路径见 `lib/hp-session.js` 的 `HP_CHROME`，
   默认使用 `%LOCALAPPDATA%\ms-playwright\chromium-1234`）。

## 目录

```
automation/
├─ lib/hp-session.js        # 登录（接口+验证码万能码）/选平台/进首页/iframe 打开模块
├─ poc/stage1-apply.js      # ① 采购申请
├─ poc/stage2a-supervisor.js# ① 纪检分配（接口）
├─ poc/stage2b-subpackage.js# ② 分包-新增子包（UI）
├─ poc/stage2c-confirm-package.js # ② 分包-确认（UI）
├─ poc/verify-stage2.js     # 状态与调研项目验证
├─ run-demo.ps1             # 一键演示
├─ explore/                 # 分析期探测脚本（登录/菜单/纪检/审批接口）
└─ shots/                   # 运行截图
```

## 设计要点（为什么这样写）

- **登录**：接口登录最稳（`POST /Register/login/userLogin.do`，password=MD5(明文)，验证码用服务端
  万能码 `qwe!@#`），再 `select.do` → `gotoIndex.do`，把 cookie 注入 Playwright context。
  纯 UI 登录也可行，但接口登录更快、更抗页面改版。
- **进系统/切页面**：不要在 iframe 页直接 `page.goto`（页面依赖 `top` 上下文），
  统一调用首页的 `changeView(title, url, menuId)` 打开页签，再按 frame URL 定位业务 iframe。
- **弹窗**：HCUI 的 confirm/msg 弹在 top 窗口，layer.open 的表单弹窗可能在当前 iframe 内，
  脚本按"top 优先、frame 兜底"查找。
- **断言**：以业务状态/接口数据为准（申请单状态、是否分包、调研项目生成），不以"页面 200"为准。
- **跨系统/异步点**：纪检分配走接口（跨库写 status=22→8，无回调依赖）；专家电话确认、扫码签名
  等按评估报告建议走 mock/API，不在本 PoC 范围内。

## 说明

PoC 会在本地库产生真实测试数据（采购申请/子包/调研项目各 1 条），可按状态自行清理；
不要在生产/线上环境运行。
