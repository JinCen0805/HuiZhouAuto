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

## 本地环境特殊配置（WP5 起）

本地栈默认隔离了 HP→professor 的“抽取建项”MQ 通道，专家抽取会卡住。已按 WP5 方案 A 做如下处理：

1. `db/infra/local-stack/local-stack.ps1`（**未提交，仅本地**）：
   - professor `mq.rabbitmq.vhost` 改为 `/local-hospital-procurement`（与 HP 共用）；
   - `draw.integration.listener.enabled=true`，并恢复 `spring-rabbitmq.xml` 的 auto-startup；
   - 已执行 `local-stack.ps1 restart-service -Service professor`。
2. HP 本地 profile 关闭了 Spring 定时任务（outbox relay 不执行），
   由 `scripts/local_draw_bridge.py` 把待发布的 `draw.command.create` 消息直接投递到 RabbitMQ；
   s11 流程会自动调用（仅本地可用，缺少 docker 时会跳过）。
3. 需要补齐 `hospital.draw.result.queue` 的 `draw.event.#` 绑定（脚本会自动补齐），
   否则 professor 回调会因 `NO_ROUTE` 事务回滚。

未做上述配置时：`pytest tests/flows/test_p1_argument.py` 的链式用例默认 skip；
配置完成后可执行：

```powershell
$env:HP_ARGUMENT_MQ_BRIDGE='1'
& $py -m pytest tests/flows/test_p1_argument.py -v -s
```

## WP8 全链编排（单入口 / 续跑 / 重试 / 报告）

一条命令跑完采购前置全流程（S01→S20，最终申请单 status=9 采购中）：

```powershell
cd D:\Desktop\HuiZhouAuto\automation_py
$py = "C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py scripts/run_full_chain.py            # 全新全链（约 4~5 分钟）
& $py scripts/run_full_chain.py --headed   # 显示浏览器窗口
```

续跑（按申请单当前状态自动定位起始步骤）：

```powershell
& $py scripts/run_full_chain.py --resume
& $py scripts/run_full_chain.py --resume --request-code FW-YWB-CG20260123
& $py scripts/run_full_chain.py --from S15
```

- 失败默认重试 1 次（`--retries N` 可调；S01 不重试，避免重复建单）。
- 报告：`reports/<runId>/report.json` + `report.html`（步骤/耗时/状态/错误/申请单号与状态）。
- 退出码：成功 0，失败 1，便于 CI 集成。
- 续跑状态映射：22→S04、8→S05、7→S06、4→S10、15/16→S15、17→S16、20→S17、19/18→S18、10→S19、11→S20、9→已完成。

## 本地 / 线上环境切换

```powershell
# 本地（默认）
$env:HP_ENV='local'
python scripts/env_check.py

# 线上（只读自检；写操作需显式授权）
$env:HP_ENV='online'
$env:HP_BASE_URL='http://172.16.29.215'
python scripts/env_check.py
```

线上默认禁止写业务数据：`run_full_chain.py` 需要 `HP_ALLOW_ONLINE_WRITES=1` 才执行；
pytest flows 用例在线上默认 skip；数据清理脚本线上禁止执行。
详细说明见 `../docs/环境切换.md`。
