# automation_py · Playwright + Pytest

采购前置流程自动化的 Python 实现（**开发中**，按 `analysis/采购前置流程UI自动化开发计划-Playwright-Pytest-AI.md` 的工作包推进）。

## 快速开始

```powershell
cd D:\Desktop\HuiZhouAuto\automation_py

# 1. Python 解释器（DSH 内置）
$py = "C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

# 2. 安装依赖
& $py -m pip install -r requirements.txt

# 3. 配置密码（复制模板后填写；.env.local 已被 gitignore）
Copy-Item .env.local.example .env.local

# 4. 环境自检
& $py scripts/env_check.py

# 5. 引导测试
& $py -m pytest -q
```

## 目录

```
automation_py/
├─ conftest.py          # pytest 全局配置（run_id/config/playwright 实例）
├─ pytest.ini
├─ requirements.txt
├─ core/                # 配置、HTTP 会话、浏览器、断言、报告、重试
├─ pages/               # PageObject（WP1 起逐步添加）
├─ api/                 # 接口辅助（WP2 起逐步添加）
├─ flows/               # 阶段编排（WP2 起逐步添加）
├─ tests/               # smoke / flows / regression
├─ fixtures/files/      # 统一测试附件（wjc测试文件.pdf/.docx）
├─ scripts/env_check.py # 环境自检
└─ reports/             # 运行报告（gitignore）
```

## 约定

- 密码只从环境变量 / `.env.local` 读取，禁止写入代码、配置、日志；
- 业务参数集中在 `fixtures/flow_config.json`（WP2 前补齐）；
- 测试断言以业务状态/接口数据为准，不以“页面 200”为准；
- 每个工作包完成须附实际运行证据，并更新根目录 `PROGRESS.md`。
