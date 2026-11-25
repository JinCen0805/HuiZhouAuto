# HuiZhouAuto · AI 协作规则

> 本文件是 AI 在本仓库工作的硬性约定。每次会话开始先读本文件、`PROGRESS.md`、
> `analysis/采购前置流程UI自动化开发计划-Playwright-Pytest-AI.md`。

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
4. **小步提交**：每个工作包完成并验收后提交一次（中文 commit message）；
   禁止一次提交多个工作包。
5. **会话流程**：先 `python scripts/env_check.py` + `python -m pytest -q`，再动代码；
   仅在代码/能力/环境发生变化时更新 `PROGRESS.md` 并 push；单次验证/回归跑数不逐条记录，
   必要时只在阶段性汇总里记一笔。
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
```

## 6. Git

- 分支：`main` 保持可运行；工作包可用 `wp/<nn>-<name>` 分支，验收后合并。
- commit 信息用中文，说明“做了什么、为什么”；禁止 AI 署名/Co-Authored-By。
- 禁止提交：`__pycache__/`、`.pytest_cache/`、`reports/`、`.env.local`、密码、`.sessions/`。
