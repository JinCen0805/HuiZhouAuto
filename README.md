# 惠州项目 · 采购前置流程自动化

本项目用 Playwright + Pytest 在惠州项目线上环境自动完成采购前置流程：采购申请 → 纪检分配 →
分包 → 调研公告 → 供应商响应 → 资格性审查 → 专家抽取 → 线下论证 → 采购需求书 →
审计 → 三方审查 → 采购方式分配 → 采购执行申请。

全链成功后，采购申请单状态为 **9（采购中）**，采购执行项目离开审批中。

> 本文只说明**线上环境**的运行方式。

## 1. 运行前提

- Windows 10/11；
- Python 3.12；
- 能访问线上环境：`http://172.16.29.215`；
- 具备线上测试账号（承办干事、承办主任、纪检、审计、财务、采购办、院办、供应商等）。

## 2. 安装

```powershell
git clone https://github.com/JinCen0805/HuiZhouAuto.git
cd HuiZhouAuto\automation_py
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 3. 配置账号密码

复制密码模板并填写线上测试账号密码：

```powershell
Copy-Item .env.local.example .env.local
```

密码键名规则：`HP_PASSWORD_<账号大写，- 换 _>`，例如：

```text
HP_PASSWORD_CBBM1=...
HP_PASSWORD_ZHAOLIU=...
HP_PASSWORD_SJYJ=...
HP_PASSWORD_SJBZR=...
HP_PASSWORD_YBJCSGYS1=...
```

`.env.local` 已被 Git 忽略，禁止提交、粘贴到文档或日志。

## 4. 切换到线上环境

线上环境通过环境变量切换，在**当前 PowerShell 窗口**执行：

```powershell
$env:HP_ENV='online'
$env:HP_BASE_URL='http://172.16.29.215'
$env:HP_ALLOW_ONLINE_WRITES='1'
```

说明：

| 变量 | 作用 |
|---|---|
| `HP_ENV` | `online` 表示线上环境 |
| `HP_BASE_URL` | 线上入口地址 |
| `HP_ALLOW_ONLINE_WRITES` | 写操作授权开关；不设置时全链会拒绝执行 |

这三个变量只在当前窗口生效，新开窗口需要重新设置。

切换后先跑一次**只读冒烟**，确认账号、页面和服务正常（不会创建业务数据）：

```powershell
python scripts/online_smoke.py
```

预期结果：`PASS 40 / FAIL 0` 左右，所有账号登录、业务页面和 OnlyOffice 均正常。

## 5. 跑一条完整前置流程

```powershell
python scripts/run_full_chain.py `
  --project-name "医院检验试剂及配套耗材年度框架采购项目" `
  --purchase-method 1
```

默认行为：承办干事 `cbbm1`，采购执行经办人“采购办经办人”，失败重试 1 次。
每条全链约 5~7 分钟；其中约 2 分钟是调研征集截止和论证开始时间的业务等待。

### 常用参数

| 参数 | 作用 | 默认 |
|---|---|---|
| `--project-name` | 采购申请名称（每次运行必须使用**未被占用**的名称） | 运行编号加“全链” |
| `--purchase-method` | 采购方式：1/2/3/4/7 | 2 比选采购 |
| `--in-hospital-price-type` | 方式 7 的议比价方式：1 院内议价，2 院内比价 | 1 |
| `--uniqueness-attachment` | 方式 4 的唯一性论证会议纪要 PDF | 内置示例文件 |
| `--applicant` | 承办干事账号 | `cbbm1` |
| `--handler` | 采购执行经办人姓名或账号 | 采购办经办人 |
| `--run-id` | 运行编号，同时决定报告目录 | 自动生成 |
| `--headed` | 显示浏览器窗口 | 不显示 |
| `--retries` | 失败重试次数 | 1 |
| `--plan-count` | 一条申请单使用的预算计划数；大于 1 时走“组合发起”并生成对应数量的子包 | 1 |

## 6. 按采购类型运行

### 6.1 委托采购

```powershell
python scripts/run_full_chain.py --purchase-method 1 --project-name "医院院区安保服务外包采购项目"
```

### 6.2 比选采购

```powershell
python scripts/run_full_chain.py --purchase-method 2 --project-name "医院全院日常保洁及环境消杀服务项目"
```

### 6.3 竞争谈判采购

```powershell
python scripts/run_full_chain.py --purchase-method 3 --project-name "医院智慧病案管理系统建设项目"
```

### 6.4 唯一来源谈判采购

```powershell
python scripts/run_full_chain.py `
  --purchase-method 4 `
  --project-name "医院中心供氧系统维保及配件更换项目" `
  --uniqueness-attachment "D:\附件\唯一性论证会议纪要.pdf"
```

不传 `--uniqueness-attachment` 时使用仓库内置示例文件，仅建议演示/联调使用；正式测试请传真实会议纪要。

### 6.5 院内议价（方式 7 + 议价方式 1）

```powershell
python scripts/run_full_chain.py `
  --purchase-method 7 `
  --in-hospital-price-type 1 `
  --project-name "医院健康体检中心配套设备采购项目"
```

### 6.6 院内比价（方式 7 + 议价方式 2）

```powershell
python scripts/run_full_chain.py `
  --purchase-method 7 `
  --in-hospital-price-type 2 `
  --project-name "医院临床教学模拟训练设备采购项目"
```

### 6.7 一条申请单使用 3 个预算计划（组合发起）

适用于需要“一条申请单 + 多个预算计划 + 多个子包”的场景。当前比选采购、竞争谈判采购、
唯一来源谈判采购已在本地验证通过：

```powershell
python scripts/run_full_chain.py `
  --plan-count 3 `
  --purchase-method 2 `
  --project-name "医院检验试剂及配套耗材年度框架采购项目"
```

行为说明：

1. S01 自动选择 3 个可组合的预算计划（项目类型、是否政府采购、中小企业预留口径必须一致），
   走“组合发起申请”；
2. S05 自动生成 3 个子包，每个子包分配 1 个预算计划；
3. S16 审计按每个预算计划自动填写审计数量和审计单价；
4. 若找不到 3 个兼容的预算计划，会直接报错，不会自动退回单计划模式；
5. 该能力目前只在本地环境验证通过，线上运行前请先确认线上存在足够的兼容预算计划。

### 采购方式对照

| 值 | 方式 | 额外参数 |
|---|---|---|
| 1 | 委托采购 | 无 |
| 2 | 比选采购 | 无 |
| 3 | 竞争谈判采购 | 无 |
| 4 | 唯一来源谈判采购 | `--uniqueness-attachment` |
| 7 | 院内议（比）价采购 | `--in-hospital-price-type 1/2` |

## 7. 运行结果与报告

- 退出码：成功 `0`，失败 `1`；
- 成功标准：日志出现 `全链完成：status=9 采购中`；
- 报告目录：`automation_py/reports/<runId>/`，包含 `report.json` 和 `report.html`；
- 报告中可查看每个步骤的耗时、状态和失败原因。

运行中以下步骤较慢或可能自动重试，属正常现象：

- S06 完善调研信息：线上偶发首次保存未生效，编排会自动重试；
- S13 线下论证：必须等待论证开始时间到达；
- S16 审计：线上会打开 OnlyOffice 编辑器真实保存审计报告初稿。

## 8. 续跑

按申请单当前状态从断点继续：

```powershell
python scripts/run_full_chain.py `
  --from S10 `
  --request-code FW-YWB-CG20260108 `
  --project-name "医院检验试剂及配套耗材年度框架采购项目" `
  --purchase-method 1
```

注意事项：

1. 续跑必须**重复传入采购方式参数**（`--purchase-method`，方式 7 还要带 `--in-hospital-price-type`），
   否则会回落到默认的比选采购；
2. 续跑使用原申请单的 `--project-name` 和 `--request-code`，不要新建同名申请；
3. 不传 `--from` 时，按申请单状态自动定位起始步骤。

## 9. 运行纪律

- **项目名称必须唯一**：每次运行前确认名称在线上未被使用；不要复用旧名称，否则会出现同名申请，
  影响查询和后续步骤定位。
- **不要并发运行多条全链**：全链共用同一批审批账号和业务数据，并发会互相干扰。
- `HP_ALLOW_ONLINE_WRITES=1` 表示允许在线上测试环境创建/推进真实业务数据，确认授权后再设置。
- 线上测试数据不会自动清理；如需清理请联系环境管理员。
- 密码只放在 `.env.local` 或环境变量中，禁止写入代码、文档、日志。

## 10. 目录结构

```text
HuiZhouAuto/
├─ automation_py/        # 自动化代码和运行入口
│  ├─ core/              # 配置、登录、浏览器、报告
│  ├─ api/               # 接口封装
│  ├─ pages/             # 页面操作
│  ├─ flows/             # S01 到 S20 流程
│  ├─ tests/             # 冒烟、流程和单元测试
│  ├─ fixtures/files/    # 测试附件
│  └─ scripts/           # 全链入口、线上冒烟等
├─ docs/                 # 环境切换、采购方式、修复手册
├─ analysis/             # 流程分析、开发计划和技术方案
└─ PROGRESS.md           # 进度记录
```

更多说明：

- 采购方式细节：`docs/采购方式选择.md`
- 环境切换与限制：`docs/环境切换.md`
- 常见问题：`docs/环境修复手册.md`
