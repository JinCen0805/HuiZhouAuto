# 惠州市中心人民医院采购平台 · 前置流程自动化

## 目录结构

```
HuiZhouAuto/
├── analysis/                    # 分析文档（只读参考）
│   ├── 采购前置流程UI自动化可行性评估.md
│   ├── 采购前置流程UI自动化开发计划-Playwright-Pytest-AI.md   # 当前计划（AI 全程开发）
│   ├── 采购前置流程UI自动化开发计划.md                        # 历史计划（JS 版，人天估算）
│   ├── 采购前置流程UI自动化技术方案.md
│   ├── A_manual_steps.md        # 手册 21 阶段动作清单
│   ├── B_frontend_selectors.md # 前端选择器/接口盘点
│   ├── C_backend_data.md        # 后端接口/审批流/数据现状
│   ├── D_env_login.md           # 登录/平台/菜单验证
│   └── manual/                  # 手册原文与截图
│       ├── manual_text.txt
│       └── images2/             # 147 张截图
│
├── automation/                  # JS PoC（已可运行）
│   ├── lib/hp-session.js        # 登录/选平台/iframe 开模块
│   ├── poc/                     # 阶段 PoC 脚本
│   │   ├── stage1-apply.js
│   │   ├── stage2a-supervisor.js
│   │   ├── stage2b-subpackage.js
│   │   └── stage2c-confirm-package.js
│   ├── explore/                 # 探测脚本（登录/菜单/纪检/审批接口）
│   ├── shots/                   # 运行截图
│   ├── run-demo.ps1             # 一键演示
│   ├── package.json
│   └── README.md
│
└── automation_py/               # Python + Playwright + Pytest（待建）
    ├── conftest.py
    ├── pytest.ini
    ├── core/                    # 会话/浏览器/断言/报告
    ├── pages/                   # Page Object Model
    ├── api/                     # 接口辅助
    ├── flows/                   # 阶段编排
    ├── tests/                   # 测试文件
    ├── fixtures/                # 配置与附件
    ├── scripts/                 # env-check / run-flow / cleanup
    ├── requirements.txt
    └── README.md
```

## 快速开始

### JS PoC（已可运行）

```powershell
cd D:\Desktop\HuiZhouAuto\automation
npm install

# 密码通过环境变量注入（不要写进命令历史/脚本；推荐用 .env.local）
# 约定：HP_PASSWORD_<账号大写，- 换 _>，兼容 HP_PASS
$env:HP_PASSWORD_WANGLUN = '<从本地凭据文件读取>'
$env:HP_PASSWORD_JJZR    = '<从本地凭据文件读取>'

# 一键演示：采购申请 → 纪检分配 → 分包 → 生成调研项目
powershell.exe -NoProfile -ExecutionPolicy Bypass -File run-demo.ps1
```

> 供应商账号：`ybjcsgys1` / `ybjcsgys2` / `ybjcsgys3`（角色=供应商，已实测可登录并进入
> 「市场调研管理 → 调研项目管理」）。密码同样走环境变量 `HP_PASSWORD_YBJCSGYS1~3`。

### Python 版（待建，技术方案见 analysis/）

```bash
pip install playwright pytest pytest-playwright pytest-html allure-pytest requests
python -m pytest tests/flows/test_p0_main.py -v --alluredir=reports/allure_results
```

## 环境要求

- 本地全栈已启动（`D:\Desktop\HuiZhouProject\start-local-project.cmd`）
- 本机 Chromium（`%LOCALAPPDATA%\ms-playwright\chromium-1234`）
- Node.js v24+（JS PoC）/ Python 3.12+（Python 版）
- 密码通过环境变量注入，不入代码
