# HuiZhouAuto · AI 协作规则

> 本文件是 AI 在本仓库工作的硬性约定。每次会话开始先读本文件；`PROGRESS.md` 在需要了解
> 能力/环境现状时再查，`analysis/` 仅在改流程代码时按需查阅。

## 1. 项目目标

采购前置流程 UI 自动化：从采购申请一路推进到 **采购中（status=9）**，产出下游可测数据。
技术栈：Python 3.12 + Playwright 1.65.2 + Pytest 9 + pytest-playwright + requests。

## 2. 目录与边界

- 本仓库：`D:\Desktop\HuiZhouAuto`（自动化代码、分析文档、附件素材）。
- 被控系统源码：`D:\Desktop\HuiZhouProject` —— **只读参考，禁止修改**。
- 本机入口：`http://127.0.0.1/HospitalProcurement/index.html`。
- 本地全栈启动：`D:\Desktop\HuiZhouProject\start-local-project.cmd`。

## 3. 硬性规则

1. **证据制**：任何“完成/通过”必须附实际运行证据（命令输出、截图、接口响应、报告路径）。
   没有运行证据不得声称完成。
2. **选择器实测**：选择器必须打开真实页面验证；接口字段必须来自真实响应，不臆造。
3. **密码零落地**：密码只从环境变量或 `automation_py/.env.local`（gitignore）读取；
   禁止写入代码、配置、文档、日志、提交。
4. **小步提交**：仅当代码（含脚本、规则文件）发生变化时提交，每个工作包一次
   （中文 commit message）；纯跑数不提交。
5. **会话流程（两种模式）**：
   - **跑数（不改代码）**：`env_check.py` → `scripts/probe_online_precheck.py`
     （名字/计划/经办人）→ 逐条 `scripts/run_full_chain.py`（输出落
     `reports/{runId}/console.log`）→ `scripts/verify_online_result.py` 只读核对；
     任一步失败即停。不写 `PROGRESS.md`、不提交，结果以汇总表回复。
   - **改代码**：改前跑目标环境 `env_check.py` + `pytest -q tests/unit`；改了
     `flows/`、`core/`、`pages/`、`api/` 再跑全量 `pytest -q`（需本地栈）。验证后提交。
   - `PROGRESS.md` 只记能力/代码、环境、已知问题三类变化；跑数记录不入库。
6. **不执行危险操作**：不跑无 WHERE 的 SQL；不删除非本 `runId` 前缀数据；
   环境配置改动（`db/infra/local-stack`、`openresty/local-dev`）先征得用户同意。
7. **失败保留现场**：截图/日志/trace 保存到 `reports/{runId}/`，报告写清阶段与原因。
8. **不越界重构**：每个工作包只改约定范围文件；提交前检查 `git diff --stat`。

## 4. 环境固定值

| 项 | 值 |
|---|---|
| Python | `C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe` |
| Chromium | `C:\Users\Grayson\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe` |
| 前端入口 | `http://127.0.0.1/HospitalProcurement/index.html` |
| 密码变量 | `HP_PASSWORD_<账号大写，- 换 _>`；`.env.local` 模板见 `automation_py/.env.local.example` |
| 报告目录 | `automation_py/reports/{runId}/` |

## 5. 常用命令

```powershell
$py = "C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd D:\Desktop\HuiZhouAuto\automation_py
& $py scripts/env_check.py
& $py -m pytest -q
& $py -m pytest tests/smoke -v

# 跑数（线上示例；本地去掉 HP_* 变量）
$env:HP_ENV='online'; $env:HP_BASE_URL='http://172.16.29.215'; $env:HP_ALLOW_ONLINE_WRITES='1'
& $py scripts/probe_online_precheck.py --plan-count 3 --name "项目名"
& $py scripts/run_full_chain.py --run-id UI自动化-YYYYMMDD-R01 --project-name "项目名" `
    --purchase-method 2 --plan-count 3
& $py scripts/verify_online_result.py --code "申请单号" --expect-method 2 --expect-plans 3
```

## 6. Git

- 分支：`main` 保持可运行；工作包可用 `wp/<nn>-<name>` 分支，验收后合并。
- commit 信息用中文，说明“做了什么、为什么”；禁止 AI 署名/Co-Authored-By。
- 禁止提交：`__pycache__/`、`.pytest_cache/`、`reports/`、`.env.local`、密码、`.sessions/`。
