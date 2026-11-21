# 惠州市中心人民医院采购平台 · 前置流程自动化

当前可运行的自动化代码在 `automation_py`，技术栈是 Python、Playwright 和 Pytest。

## 目录

```text
HuiZhouAuto/
├─ automation_py/   # 自动化代码、测试和运行脚本
├─ docs/            # 使用说明和已知限制
├─ analysis/        # 流程分析、开发计划和技术方案
├─ AGENTS.md        # AI 协作规则
└─ PROGRESS.md      # 当前进度
```

## 快速开始

```powershell
cd D:\Desktop\HuiZhouAuto\automation_py
python -m pip install -r requirements.txt
Copy-Item .env.local.example .env.local
python scripts/env_check.py
python -m pytest -q
```

密码只放在环境变量或 `automation_py/.env.local`，不要写入代码、文档或提交记录。

全链、采购方式和环境问题见 `automation_py/README.md` 与 `docs/`。
