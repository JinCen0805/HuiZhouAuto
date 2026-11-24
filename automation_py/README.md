# automation_py · 采购前置自动化代码

本目录是惠州项目采购前置流程的 Playwright + Pytest 实现。**运行方式统一见
[根目录 README](../README.md)**，本文只保留代码结构和开发约定。

## 目录

```text
automation_py/
├─ conftest.py           # pytest 全局配置（run_id/config/playwright）
├─ core/                 # 配置、HTTP 会话、浏览器、断言、报告、重试
├─ api/                  # 接口封装
├─ pages/                # PageObject
├─ flows/                # S01~S20 流程编排
├─ tests/                # smoke / flows / unit
├─ fixtures/files/       # 测试附件
├─ scripts/              # 全链入口、线上冒烟等
└─ reports/              # 运行报告（gitignore）
```

## 线上运行速查

```powershell
cd HuiZhouAuto\automation_py
$env:HP_ENV='online'
$env:HP_BASE_URL='http://172.16.29.215'
$env:HP_ALLOW_ONLINE_WRITES='1'

python scripts/online_smoke.py        # 只读冒烟
python scripts/run_full_chain.py --purchase-method 1 --project-name "医院院区安保服务外包采购项目"
```

采购方式参数：

| 值 | 方式 | 额外参数 |
|---|---|---|
| 1 | 委托采购 | 无 |
| 2 | 比选采购 | 无 |
| 3 | 竞争谈判采购 | 无 |
| 4 | 唯一来源谈判采购 | `--uniqueness-attachment` |
| 7 | 院内议（比）价采购 | `--in-hospital-price-type 1/2` |

完整参数、六种方式示例、续跑和运行纪律见 [根目录 README](../README.md)。

## 开发约定

- 密码只从环境变量或 `.env.local` 读取，禁止写入代码、配置、日志；
- 断言以业务状态/接口数据为准，不以“页面 200”为准；
- 线上默认禁止写业务数据，`run_full_chain.py` 需要 `HP_ALLOW_ONLINE_WRITES=1`；
- 每个工作包完成须附实际运行证据，并更新根目录 `PROGRESS.md`。

## 单元测试

```powershell
python -m pytest tests/unit -q
```
