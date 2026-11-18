# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP0 已完成** → 下一步 WP1
- 分支：`main`

## 已完成
- [x] 分析与技术方案（analysis/）
- [x] Playwright + Pytest 环境安装与验证（Python 3.12.14 / playwright 1.65.2 / pytest 9.2.0）
- [x] 供应商账号 ybjcsgys1~3 验证（采购交易系统/供应商/107 菜单）
- [x] 12 项业务默认值确认 + 附件素材就位
- [x] **WP0 环境与仓库骨架**
  - `automation_py/` 骨架：`core/`（config/session/browser/assert_helper/reporter/retry）、
    `conftest.py`、`pytest.ini`、`requirements.txt`、`tests/`
  - `scripts/env_check.py` 环境自检（38 PASS / 1 WARN / 0 FAIL，耗时 6.5s）
  - 引导测试 `pytest -q`：5 passed
  - `AGENTS.md`（根目录 AI 协作规则）、`PROGRESS.md`、`automation_py/README.md`
  - `.env.local.example` 模板；真实密码在 `.env.local`（gitignore）
  - `fixtures/files/` 放入 `wjc测试文件.pdf/.docx`

## 证据
- 环境自检（2026-11-18）：
  - `[A]` Python 3.12.14 / 依赖 / Chromium / Playwright 启动（title=采购交易系统）
  - `[B]` 13 个服务健康 200；新版 API 网关路由（HTTP 500=路由存在）；专家 mock `enabled=true`
  - `[C]` 14 个账号登录+角色+菜单通过；纪检鉴权 `canManage=True`；预算计划接口 `years=5`
  - `[D]` 附件素材 49879B/10221B；报告目录可写
  - `[E]` OnlyOffice(18099) WARN（WP6 前需启动）
- `pytest -q` → `5 passed in 0.11s`

## 阻塞 / 已知项
- OnlyOffice 容器未启动（WARN）：WP6（采购需求/审计报告在线编辑）前启动即可。
- 本地纪检 Redis DB 差异已通过登录 key 同步缓解；`env_check` 每次会验证（401 会 FAIL）。
- `.env.local` 含本地测试密码，已 gitignore；严禁提交。

## 下一步（WP1）
1. `core/session.py` 扩展：Playwright context 注入、storageState 缓存、失效重登；
2. `core/browser.py` 扩展：`open_hp`、`changeView` 开模块、iframe/双套弹窗 helper；
3. `tests/smoke/`：14 个页面可加载 + 关键接口断言；
4. 验收：`pytest tests/smoke -q` 全绿，提交 push。

## 证据索引
- 环境自检命令：`python scripts/env_check.py`（本文件 §证据）
- 引导测试：`python -m pytest -q` → 5 passed
