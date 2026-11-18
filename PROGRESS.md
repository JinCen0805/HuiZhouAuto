# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP5 部分完成（代码已写，动态验证被本地环境阻断）**
- 分支：`main`

## 已完成
- [x] WP0 环境与骨架（env_check 38 PASS/1 WARN/0 FAIL）
- [x] WP1 会话/浏览器核心 + 冒烟（26 passed）
- [x] WP2 S01/S04/S05 迁移（P0 全链 18s，连续 2 次）
- [x] WP3 审批通用 + 调研信息/公告（P1 33s）
- [x] WP4 供应商响应 + 资格性审查（state=4；全量 35 passed）
- [x] **WP5 专家抽取 + 线下论证（代码完成，动态验证受阻）**
  - `api/argument_api.py`：专业目录/详情/规划抽取/手动候选/保存专家/指定组长/线下论证结果
  - `api/professor_mock.py`：mock 建项查询、生成 callid、专家按键回调
  - `pages/survey_argument.py`：论证列表、指定组长、上传论证结果并提交
  - `flows/s11_extract.py`、`flows/s13_argument.py`
  - `tests/flows/test_p1_argument.py`（页面只读通过；链式用例默认 skip）

## 证据（2026-11-18）
- `pytest tests/flows/test_p1_argument.py -v -s` → **1 passed, 1 skipped in 9.98s**
  - 调研论证管理页面加载 OK
  - 链式用例 skip：`本地栈默认隔离 HP→professor 抽取建项 MQ 通道，需 HP_ARGUMENT_MQ_BRIDGE=1`
- 全量 `pytest -q` → **36 passed, 2 skipped in 203.98s**
- `env_check.py` → **PASS 38 / WARN 1 / FAIL 0**
- API 实测（规划抽取）：
  - `POST hpSurveyArgument/startExtract` 返回 success，`extractPlanStatus=QUEUED`、
    `drawSectionCode=HP-SURVEY-{uuid}`
  - 之后 professor mock `/expertExtract/mock/projects?keyword=HP-SURVEY-{uuid}` 返回 0 条；
    `listManualCandidates` 返回“项目不存在” → 抽取建项未发生。
  - 根因：本地栈刻意隔离 HP→professor 的抽取建项 MQ：
    `db/infra/local-stack/local-stack.ps1` 中 professor 配置
    `mq.rabbitmq.vhost='/local-professor'`、`draw.integration.listener.enabled=false`、
    spring-rabbitmq 的 `auto-startup=false`；HP 发布到 vhost `/local-hospital-procurement`。
    MQ listener 不通 → professor 侧不会创建抽取项目 → 手动勾选无可选专家。

## 阻塞事项（需用户决策）
- 要完成 WP5 及后续 WP6~WP8，必须先打通本地 HP→professor 抽取建项通道，二选一：
  - **方案 A（推荐）**：改 `db/infra/local-stack/local-stack.ps1` 中 professor 的本地运行配置：
    vhost 改为 `/local-hospital-procurement`、`draw.integration.listener.enabled=true`、
    恢复 spring-rabbitmq auto-startup（去掉强制 false），然后
    `local-stack.ps1 restart-service -Service professor`；风险中等（需重启/重建 professor，约 5~10 分钟）。
  - **方案 B**：接受“专家抽取不走本地”，改为在测试环境（172.16.29.215）验证 WP5+。
- 在方案确定前，WP6（采购需求/审计）也无法获得 `status=15` 数据（本地库无该状态存量）。

## 下一步
1. 用户确认方案 A 后：修改本地栈配置 → 重启 professor → 跑
   `HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p1_argument.py -v -s`；
2. 通过后进入 WP6（需求编制 + 审计）。

## 证据索引
- 论证页面：`python -m pytest tests/flows/test_p1_argument.py -v -s`
- 全量：`python -m pytest -q`（36 passed, 2 skipped）
