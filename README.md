# 惠州市中心人民医院采购平台 · 前置流程自动化

本项目用 Playwright 和 Pytest 自动走完采购前置流程：从采购申请、纪检分配、分包、调研、资格审查、专家抽取、论证、需求书、审计、三方审查、采购方式分配，到采购执行申请。

全链成功后，采购申请单状态为 9（采购中），采购执行项目会离开审批中。

## 项目结构

```text
HuiZhouAuto/
├─ automation_py/        # 自动化代码和运行入口
│  ├─ core/              # 配置、登录、浏览器、报告
│  ├─ api/               # 采购、审批、执行等接口
│  ├─ pages/             # 页面操作
│  ├─ flows/             # S01 到 S20 流程
│  ├─ tests/             # 冒烟、流程和单元测试
│  ├─ fixtures/files/    # 测试附件
│  └─ scripts/           # 环境检查、全链、造数和清理
├─ docs/                 # 使用说明、环境修复和采购方式
├─ analysis/             # 流程分析、开发计划和技术方案
├─ AGENTS.md             # AI 协作规则
└─ PROGRESS.md           # 当前进度
```

密码文件、登录缓存、测试报告和 Python 缓存不提交到 Git。

## 使用方法

先进入自动化目录：

```powershell
cd D:\Desktop\HuiZhouAuto\automation_py
```

检查环境和运行默认测试：

```powershell
python scripts/env_check.py
python -m pytest -q
```

跑一条完整前置流程：

```powershell
$env:HP_ARGUMENT_MQ_BRIDGE='1'
python scripts/run_full_chain.py `
  --project-name "医院电梯年度维护保养服务采购" `
  --purchase-method 7 `
  --in-hospital-price-type 2 `
  --applicant cbbm1 `
  --handler "采购办经办人"
```

常用参数：

| 参数 | 作用 | 默认 |
|---|---|---|
| `--project-name` | 采购项目名称 | 运行编号加“全链” |
| `--purchase-method` | 采购方式 | 2，比选采购 |
| `--in-hospital-price-type` | 议比价方式：1 院内议价，2 院内比价 | 方式 7 时默认 1 |
| `--applicant` | 承办干事登录账号 | `cbbm1` |
| `--handler` | 采购执行经办人姓名或账号 | 采购办经办人 |
| `--uniqueness-attachment` | 唯一来源谈判的会议纪要 | 方式 4 必填 |
| `--headed` | 显示浏览器 | 不显示 |

采购方式：

| 值 | 方式 |
|---|---|
| 1 | 委托采购 |
| 2 | 比选采购 |
| 3 | 竞争谈判采购 |
| 4 | 唯一来源谈判采购 |
| 7 | 院内议（比）价采购 |

子包名称按“项目名称-子包1”生成。运行报告在 `automation_py/reports/<runId>/`，该目录不提交。

断点续跑：

```powershell
python scripts/run_full_chain.py --resume
python scripts/run_full_chain.py --resume --request-code FW-YWB-CG20260123
python scripts/run_full_chain.py --from S15
```

## 部署方式

自动化程序不需要单独部署服务。把它放到能访问目标采购系统的 Windows 机器上，安装依赖后即可运行。

1. 安装 Python 3.12、Git，并准备 Playwright 使用的 Chromium。
2. 克隆仓库：

```powershell
git clone https://github.com/JinCen0805/HuiZhouAuto.git
cd HuiZhouAuto\automation_py
python -m pip install -r requirements.txt
python -m playwright install chromium
```

3. 复制密码模板并填写本机密码：

```powershell
Copy-Item .env.local.example .env.local
```

密码键名是 `HP_PASSWORD_<账号大写>`，例如 `HP_PASSWORD_CBBM1`。`.env.local` 不要提交。

4. 准备被测系统：

- 本地运行时，先启动 `D:\Desktop\HuiZhouProject\start-local-project.cmd`，入口是 `http://127.0.0.1`。
- 专家抽取链需要本地 RabbitMQ 桥接，运行全链前设置 `HP_ARGUMENT_MQ_BRIDGE=1`。
- 可发起的预算计划用完后，执行 `python scripts/seed_local_plan.py --count 10`。
- 线上环境默认只允许只读检查。写操作必须单独授权，并设置 `HP_ENV=online`、`HP_BASE_URL` 和 `HP_ALLOW_ONLINE_WRITES=1`。

5. 部署后先执行：

```powershell
python scripts/env_check.py
python -m pytest tests/smoke -q
```

环境自检通过后，再按上一节运行全链。环境异常见 `docs/环境修复手册.md`，采购方式详见 `docs/采购方式选择.md`。
