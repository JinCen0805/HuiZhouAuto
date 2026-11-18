# 采购前置流程 UI 自动化 · 开发计划（Playwright + Pytest · AI 全程开发）

| 项 | 内容 |
|---|---|
| 文档版本 | v2.0（2026-11-18） |
| 状态 | 待确认（确认后冻结并按工作包执行） |
| 开发模式 | **AI 全程开发**：编码、探测、调试、文档、提交均由 AI 完成；人工只做业务取值确认、环境授权、里程碑验收 |
| 技术栈 | Python 3.12 + Playwright 1.65.2 + Pytest 9 + pytest-playwright + allure-pytest + requests |
| 代码仓库 | `D:\Desktop\HuiZhouAuto`（GitHub: JinCen0805/HuiZhouAuto，private） |
| 被控系统 | 本地全栈 `http://127.0.0.1`；源码只读参考 `D:\Desktop\HuiZhouProject` |
| 替代文档 | 本计划替代 v1.0《采购前置流程UI自动化开发计划》（JS 版 / 人天制估算），保留作历史 |
| 关联文档 | `analysis/采购前置流程UI自动化技术方案.md`（Playwright+Pytest 技术方案）、`analysis/采购前置流程UI自动化可行性评估.md`、`analysis/A_manual_steps.md`、`B_frontend_selectors.md`、`C_backend_data.md`、`D_env_login.md` |

---

## 1. 目标与验收标准

### 1.1 目标

一条命令生成一条可测的采购前置数据，从采购申请一直推进到 **`采购中`（status=9）**，
供招标/开标/评标等下游测试直接使用。

### 1.2 成功标准（可度量、可自动验收）

| 指标 | 目标值 | 验收方式 |
|---|---|---|
| 全链成功率 | 连续 3 次 3/3 | `pytest tests/regression/test_full_chain.py -v` 输出 |
| 单次耗时 | P0（到待调研）≤5 分钟；全链 ≤30 分钟 | 报告 `report.json` 中 `durationMs` |
| 数据完整性 | 申请单/子包/调研项目/论证/需求书/审计/审查/方式/执行申请齐全 | 关键状态断言 + 关键接口返回 |
| 可重复性 | 多次运行互不依赖 | 连续 3 次全链 |
| 可恢复性 | 中途失败可从阶段断点续跑 | `--from s11 --run-id xxx` 实测 |
| 数据可清理 | 按 `runId` 前缀一键清理 | `scripts/cleanup.py --run-id` |
| 文档可交接 | 新人/AI 按 README + AGENTS.md 可独立跑通 | 人工按 Runbook 走一遍 |

### 1.3 不在本期范围

- 采购执行之后（招标/开标/评标/定标/合同）；
- 政府采购平台（GOV）链路；
- 预算外 BT8 八节点审批（组织数据不满足，需单独授权补数据）；
- OnlyOffice 正文自动撰写、审批意见智能生成（用模板/固定值）；
- 生产/测试环境（172.16.x）适配。

---

## 2. 开发模式与分工（AI 全程开发）

### 2.1 角色与职责

| 角色 | 负责 | 投入 |
|---|---|---|
| **AI（开发主体）** | 环境自检、页面探测、PageObject、ApiHelper、Flow、测试、调试、报告、文档、git 提交 | 全程 |
| 人类-业务/测试负责人 | 确认 12 项业务默认值（§9）、提供附件/模板素材、里程碑验收 | 4 次 × 20 分钟 |
| 人类-环境/权限 | 本地环境启动、GitHub 认证窗口点击、数据清理授权、组织数据变更授权 | 按需（约 1 小时） |
| 人类-评审 | 每个里程碑抽查 AI 交付证据（运行日志/截图/报告），确认是否进入下一期 | 4 次 × 10 分钟 |

> **关键原则**：AI 负责"写和验证"，人类只负责"确认业务取值和授权"。
> AI 不允许在没有实际运行证据的情况下声称任何功能已完成。

### 2.2 AI 协作协议（硬约束）

1. **证据制**：任何"已完成"必须附带可复现证据（pytest 输出、截图、接口响应、报告 JSON），
   只写"应该可以"视为未完成。
2. **小步提交**：每个工作包完成并验收后提交一次 git（中文 commit message），
   禁止一次提交多个工作包。
3. **选择器必须实测**：不允许凭 HTML 源码猜测选择器；必须打开真实页面验证，
   把探测过程沉淀到 `scripts/probe_*.py` 或 `explore/` 目录。
4. **接口参数必须实调**：API Helper 的入参以真实请求/响应为准，不臆造字段。
5. **禁止泄露密码**：密码只从环境变量读；任何日志/报告/提交不得出现明文密码。
6. **不越权改业务代码**：`D:\Desktop\HuiZhouProject` 只读参考，不修改；
   `D:\Desktop\HuiZhouAuto` 只改自动化代码。
7. **环境改动需授权**：修改本地栈配置（db/infra/local-stack、openresty/local-dev）前必须说明并获确认。
8. **每轮会话留交接**：更新 `PROGRESS.md`（已完成/进行中/阻塞/下一步），并在会话结束时给人类一句话摘要。

### 2.3 AI 每轮会话标准流程（Session Playbook）

```
1. 读 AGENTS.md + PROGRESS.md + 本计划 + 技术方案
2. 跑环境自检：python scripts/env_check.py（失败先修，修复需人类授权）
3. 跑冒烟：pytest tests/smoke -q（确认基线绿）
4. 取一个工作包（§5），只做该包范围
5. 页面探测 → 写 PageObject → 写 ApiHelper → 写 Flow → 写/更新测试
6. 跑目标测试，保存输出/截图到 reports/{run_id}/
7. 更新 PROGRESS.md，git add/commit/push
8. 给人类：完成项 + 证据 + 阻塞 + 下一步（≤10 行）
```

---

## 3. 技术栈与工程规范（摘要，详见技术方案）

| 项 | 选型 |
|---|---|
| 运行时 | Python 3.12（DSH 内置解释器，固定绝对路径） |
| 浏览器 | 本机 Chromium（复用 `ms-playwright/chromium-1234`，零下载） |
| 框架 | pytest + pytest-playwright（只用其 `playwright` fixture）+ allure-pytest + pytest-html |
| HTTP 辅助 | requests（登录/纪检/专家 mock/签名/立即发布） |
| 配置 | `fixtures/flow_config.json`（业务参数）+ 环境变量（密码） |
| 报告 | Allure + JSON 报告 + 失败截图/trace |

工程规范：

- 目录分层 `core / pages / api / flows / tests / fixtures / scripts`（技术方案 §2）；
- 选择器集中在 PageObject，优先级 `#id > [idname] > [lay-event] > [lay-filter] > 文本`；
- 断言以业务状态/接口数据为准，不以"页面 200"为准；
- 表格固定列 DOM 重复：只在 `:not(.layui-table-fixed)` 内查找行；
- 弹窗：`top` 优先、`frame` 兜底；
- 密码不入库、不入 git、不入日志。

---

## 4. 工作包与里程碑（AI 开发单元）

> 单位：**AI 工作包（WP）**。每个 WP ≈ 1 次 AI 会话（1~3 小时，含自测与提交）。
> 共 **10 个 WP**，预计 **10~12 个 AI 工作时段**（可 5~7 个自然日完成，视会话密度）。

### WP0 环境与仓库骨架（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `automation_py/` 目录、`requirements.txt`、`pytest.ini`、`conftest.py`、`core/` 骨架、`scripts/env_check.py`、`AGENTS.md`、`PROGRESS.md`、`.gitignore` |
| 验收 | `python scripts/env_check.py` 全绿；`pytest --collect-only` 无错误；提交并 push |
| 人工 gate | 无需（环境修复若涉及配置，需 1 次授权） |
| 依赖 | 无 |

### WP1 会话/浏览器/冒烟（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `core/session.py`（多账号 HTTP 登录 + cookie 注入 + 缓存）、`core/browser.py`（iframe/弹窗/changeView）、`tests/smoke/test_smoke.py`（14 页面 + 关键接口） |
| 验收 | 3 个角色（承办/纪检/供应商）可登录开页面；冒烟全绿；提交 |
| 人工 gate | 无 |
| 依赖 | WP0 |

### WP2 S01/S04/S05 迁移（0.5 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `pages/procurement_apply.py`、`pages/package_management.py`、`api/jjjc_api.py`、`flows/s01_apply.py`、`flows/s04_supervisor.py`、`flows/s05_package.py`、`tests/flows/test_p0_main.py` |
| 验收 | `pytest tests/flows/test_p0_main.py -v` 通过；生成 1 条"待调研 + 调研项目"；连续 2 次 |
| 人工 gate | 无（提交后人类可抽查报告） |
| 依赖 | WP1 |

### WP3 审批通用 + 调研信息/公告（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `api/approval_api.py`（BT6/BT8/BT13/BT14/BT19 通用）、`pages/approval.py`、`pages/survey_project.py`、`flows/s06_survey_info.py`、`flows/s07_notice.py`、`api/survey_api.py` |
| 验收 | 用存量待办完成 1 次审批（通过/驳回）；调研信息保存成功；公告立即发布 `state=2` |
| 人工 gate | 业务默认值确认（§9，Day 1~2） |
| 依赖 | WP1 |

### WP4 供应商响应 + 资格性审查（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `pages/survey_result.py`、`flows/s08_supplier_reply.py`、`flows/s10_review.py`、`fixtures/files/` 响应文件样例 |
| 验收 | 3 家供应商响应提交；资格审查通过；状态到"待论证"（state=4） |
| 人工 gate | 附件素材确认（供应商响应文件/技术参数） |
| 依赖 | WP3 |

### WP5 专家抽取 + 论证（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `api/professor_mock.py`、`api/signature_api.py`、`pages/survey_argument.py`、`flows/s11_extract.py`、`flows/s13_argument.py` |
| 验收 | 手动抽选 3 专家 + mock 电话确认；线下论证上传报告完成；申请单 `status=15 待编制` |
| 人工 gate | 论证方式/专家默认值确认（§9） |
| 依赖 | WP4 |

### WP6 采购需求 + 审计（1.5 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `pages/requirement.py`、`pages/audit_management.py`、`pages/discipline.py`、`flows/s15_requirement.py`、`flows/s16_audit.py`、`api/audit_api.py`、需求书/审计报告模板素材 |
| 验收 | 需求书创建+提交；审计推送→纪检受理/报告→主任通过；`audit_status=2` |
| 人工 gate | 模板素材确认 |
| 依赖 | WP5 |

### WP7 终稿/三方审查/方式分配/执行申请（1.5 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `pages/demand_review.py`、`pages/method_confirm.py`、`pages/execution_apply.py`、`flows/s18_demand_review.py`、`flows/s19_method.py`、`flows/s20_execution.py`、4 类文书素材 |
| 验收 | 三方审查通过、方式审批通过（status=11）、执行审批通过（status=9 采购中） |
| 人工 gate | 采购方式/评标方式默认值、4 类文书来源确认 |
| 依赖 | WP6 |

### WP8 全链编排 + 报告（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `flows/run_all.py`、`scripts/run_flow.py`（`--from`/`--stages`/`--run-id`）、`core/reporter.py`、断点续跑、Allure 报告 |
| 验收 | 全链一条命令跑通；中断后可从阶段续跑；报告含阶段/耗时/截图 |
| 人工 gate | 全链验收（人类看报告） |
| 依赖 | WP7 |

### WP9 稳定性/清理/文档/交接（1 个会话）

| 项 | 内容 |
|---|---|
| 产出 | `scripts/cleanup.py`、3 次全链回归报告、README、RUNBOOK、演示录屏、CHANGELOG |
| 验收 | 连续 3 次 3/3；清理无残留；新人按文档可跑 |
| 人工 gate | **最终验收**（人类按 Runbook 独立跑一次） |
| 依赖 | WP8 |

### 里程碑映射

| 里程碑 | 包含 WP | 人工 gate |
|---|---|---|
| M0 环境与骨架 | WP0~WP1 | 无（授权环境修复） |
| M1 主链前半 | WP2 | 抽查报告 |
| M2 调研闭环 | WP3~WP4 | 中期验收（人类看"待论证"数据） |
| M3 论证完成 | WP5 | 抽查 |
| M4 需求/审计/审查/方式 | WP6~WP7 | 抽查 |
| M5 采购中 | WP7（末） | 全链验收 |
| M6 交付 | WP8~WP9 | 最终验收 |

---

## 5. 排期（AI 会话制）

> 假设：每天 1~2 个 AI 工作包；人类 gate 在当天或次日完成。

### 方案 A：紧凑（约 1 周）

| 天 | 工作包 | 人工动作 |
|---|---|---|
| D1 | WP0 + WP1 | 环境启动/授权；确认 12 项默认值 |
| D2 | WP2 + WP3 | 抽查"待调研"数据 |
| D3 | WP4 + WP5 | 确认附件/论证方式 |
| D4 | WP6 | 确认模板素材 |
| D5 | WP7 | 确认采购方式默认值/4 类文书 |
| D6 | WP8 | 全链验收 |
| D7 | WP9 | 最终验收/交接 |

### 方案 B：常规（约 2 周）

每天 1 个 WP，遇到阻塞当天修复；里程碑当天验收。适合同时有其它任务时。

### 关键路径

```
WP0 → WP1 → WP2 → WP3 → WP4 → WP5 → WP6 → WP7 → WP8 → WP9
                          ↘（WP3 审批通用被 WP4/WP6/WP7 复用）
```

风险最高：WP6（审计跨前端）、WP7（BT6/BT13 + 4 类文书）。两项各预留半个会话缓冲。

---

## 6. 分支、提交与仓库规范

- 分支模型：`main` 保持可运行；每个 WP 用 `wp/<nn>-<name>` 短分支，验收后合入 `main` 并 push。
- 提交信息中文、单行说清"做了什么"；一个 WP 可有多个小提交，但合并前 squash 可选。
- 禁止提交：`node_modules/`、`.env.local`、`reports/`、`shots/`、密钥/密码、`__pycache__`。
- 每次 push 前跑 `pytest tests/smoke -q` 和 `python scripts/env_check.py`。
- 仓库根 `AGENTS.md` 作为 AI 协作规则（附录 A），`PROGRESS.md` 作为跨会话交接（附录 B）。

---

## 7. 环境与数据前置清单

| # | 事项 | 责任 | 完成时点 | 验收 |
|---|---|---|---|---|
| 1 | 本地全栈启动（22 服务） | 人类（启动）/AI（自检） | D1 | `env_check.py` 全绿 |
| 2 | 本地网关 `/hospital-procurement/` 路由 | AI（已补，需确认） | D1 | 新版页面无"数据接口请求异常" |
| 3 | 纪检 Redis DB 对齐（7→9 或 key 同步） | 人类授权/AI 修 | D1 | `/jjjc/supervise/*` 无 401 |
| 4 | 测试账号可用（14+ 角色） | 人类提供/AI 自检 | D1 | 登录/菜单自检通过 |
| 5 | 12 项业务默认值 | 人类 | D1~D2 | 写入 `flow_config.json` 并确认 |
| 6 | 附件/模板素材 | 人类提供/AI 整理 | WP4/WP6 前 | `fixtures/files/` 齐全 |
| 7 | OnlyOffice/professor mock/文件服务 | 人类（启动）/AI（自检） | D1 | 自检通过 |
| 8 | 数据清理授权 | 人类 | D2 | 清理脚本评审 |
| 9 | 本地库快照 | 人类 | 全链前 | 可回滚 |

---

## 8. 质量门禁与验收

### 8.1 每个 WP 的 Definition of Done

- [ ] 目标测试/脚本实际运行通过（有输出证据）；
- [ ] 失败路径有截图/报告；
- [ ] 无硬编码密码/环境地址；
- [ ] `pytest tests/smoke -q` 仍全绿；
- [ ] `PROGRESS.md` 已更新；
- [ ] 已 git commit（中文信息）并 push。

### 8.2 里程碑验收命令

```powershell
# 环境
python scripts/env_check.py

# 冒烟
pytest tests/smoke -q

# P0 主链
pytest tests/flows/test_p0_main.py -v --alluredir=reports/allure_results

# 全链
pytest tests/regression/test_full_chain.py -v --alluredir=reports/allure_results

# 断点续跑
python scripts/run_flow.py --from s11 --run-id <runId>

# 清理
python scripts/cleanup.py --run-id <runId>
```

### 8.3 反幻觉规则（AI 专属）

1. 未实际运行 → 不得说"通过/已完成"；
2. 选择器必须来自真实 DOM 探测；接口字段必须来自真实响应；
3. 报告里引用截图/日志路径必须真实存在；
4. 遇到无法验证的假设，明确标注"待验证"，不得写成结论；
5. 每次会话结束必须自查 `git status`，无未提交的意外改动。

---

## 9. 需要人类确认的 12 项业务取值（阻塞点）

| # | 参数 | 建议默认 |
|---|---|---|
| 1 | 发起部门/计划 | 医务部 `cbbm1`、`是否涉政采=否`、`department_id` 非空 |
| 2 | 承办部门主任/分管院领导 | `zhaoliu` / `libai` |
| 3 | 监督员/监督范围 | 在岗监督员任选 + 全流程 |
| 4 | 调研评审指标 | 预置通用模板（质量/安全/技术各 2 条） |
| 5 | 公告模板/发布方式 | "调研公告" + 立即发布 |
| 6 | 供应商响应 | `cy-gys1~3` + 预置响应文件/技术参数 |
| 7 | 资格审查结论 | 3 家全部通过 |
| 8 | 论证方式 | 线下论证（省人工）；线上+签名 API 作为备选 |
| 9 | 抽取方式/专家 | 手动抽选 3 人（`cy-zj1~3`）+ mock 电话确认 |
| 10 | 需求书/审计报告模板 | 按项目类型选默认；正文用模板/预置文件 |
| 11 | 审查类型/结论 | 一般性审查 + 全部通过；不走前加签 |
| 12 | 采购方式/评标方式 | 按金额/项目类型默认；选非"唯一来源"方式 |

---

## 10. 风险与应对（AI 开发特有）

| 风险 | 影响 | 应对 |
|---|---|---|
| AI 声称完成但实际未跑通 | 高 | 证据制 + 人类可复跑验收命令；报告必须含真实日志/截图 |
| AI 上下文丢失/跨会话不一致 | 中 | `AGENTS.md` + `PROGRESS.md` + 每轮会话按 Playbook 起步 |
| AI 猜测选择器/接口字段 | 高 | 强制"页面探测脚本 + 真实响应"；技术方案 §4 的 helper 复用 |
| AI 过度重构/改公共文件 | 中 | 每 WP 限定文件范围；业务仓库只读；提交前 review `git diff --stat` |
| 环境问题反复（网关/Redis/OnlyOffice） | 中 | `env_check.py` 纳入每次会话；W1 集中修复 |
| 业务默认值迟迟不确认 | 高 | D1 定默认值，先用建议值开发，配置可改 |
| 页面改版导致选择器失效 | 中 | 选择器集中 + 冒烟网；页面版本号变更触发回归 |
| 数据污染 | 中 | runId 前缀 + 清理脚本 + 跑前快照 |
| 专家 mock/签名行为变化 | 低 | API Helper 封装 + 契约小测；保留手动兜底 |

**决策门**：WP4 结束时检查"供应商响应/资格审查"UI 成功率；若 <90%，该阶段改 API 为主（保留 UI 冒烟）。

---

## 11. 交付物与交接

| 交付物 | 说明 |
|---|---|
| `automation_py/` 代码 | 可运行全链，按技术方案分层 |
| `tests/` 分层测试 | 冒烟 / 各阶段 / 全链回归 |
| `scripts/` | env_check、run_flow、cleanup |
| `reports/` 样例 | 全链成功报告 + Allure 结果 |
| 文档 | README、RUNBOOK、AGENTS.md、PROGRESS.md、CHANGELOG |
| 演示 | 一条命令跑全链的录屏/说明 |
| 交接 | 人类按 RUNBOOK 独立跑通一次即视为交付完成 |

---

## 12. 第一天行动清单（AI 可直接开始）

1. 在 `D:\Desktop\HuiZhouAuto` 创建 `automation_py/` 骨架（WP0）；
2. 写 `AGENTS.md`、`PROGRESS.md`、`requirements.txt`、`pytest.ini`、`.gitignore`；
3. 写 `scripts/env_check.py` 并跑通（本地服务/网关/Redis/账号/OnlyOffice/mock）；
4. 写 `core/session.py` + `core/browser.py`，用 3 个角色验证登录与开页面（WP1）；
5. 写 `tests/smoke/test_smoke.py`，冒烟全绿；
6. git 提交并 push；给人类 10 行摘要（完成项/证据/阻塞/下一步）；
7. 人类确认 12 项默认值后进入 WP2。

---

## 附录 A：`AGENTS.md`（建议内容）

```markdown
# HuiZhouAuto AI 协作规则

## 项目
- 目标：采购前置流程 UI 自动化（本地环境），Playwright + Pytest，全链到"采购中"。
- 代码目录：D:\Desktop\HuiZhouAuto；被控系统参考源码：D:\Desktop\HuiZhouProject（只读）。
- 先读：analysis/采购前置流程UI自动化技术方案.md、本计划、PROGRESS.md。

## 硬性规则
1. 任何“完成”必须附真实运行证据（pytest 输出/截图/接口响应）。
2. 选择器必须实际打开页面验证；接口字段必须来自真实响应。
3. 密码只从环境变量读；禁止写入任何文件/日志/提交。
4. 每次会话先跑 env_check.py 和 smoke，再动代码。
5. 每完成一个工作包：更新 PROGRESS.md → git add/commit（中文）→ push。
6. 不改 D:\Desktop\HuiZhouProject 下的业务代码；环境配置改动先征得人类同意。
7. 不执行无 WHERE 的 SQL；不删除非本 run_id 前缀的数据。
8. 失败时保留截图/trace，报告写清阶段与原因，不允许“假装通过”。

## 环境
- Python: C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
- Chromium: C:\Users\Grayson\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe
- 本地入口: http://127.0.0.1/HospitalProcurement/index.html
- 密码环境变量: HP_PASSWORD_<USERNAME 大写，- 换 _>（.env.local，gitignore）
```

## 附录 B：`PROGRESS.md` 模板

```markdown
# 进度

## 当前
- 工作包：WP1（进行中）
- 分支：wp/01-session-browser
- 最近提交：<hash> <message>

## 已完成
- [x] WP0 环境与骨架（date）
- [ ] WP1 ...

## 阻塞
- 无 / 说明

## 下一步
1. ...
2. ...

## 证据索引
- reports/20261119-xxxx/report.json
- reports/20261119-xxxx/screenshots/...
```

## 附录 C：AI 会话启动提示词模板

```
读取 D:\Desktop\HuiZhouAuto\AGENTS.md、analysis/采购前置流程UI自动化开发计划-Playwright-Pytest-AI.md、
PROGRESS.md。按 Session Playbook：
1) 跑 env_check 和 smoke；
2) 执行当前工作包 <WP编号>，只改约定范围文件；
3) 实际运行验收命令，保存证据；
4) 更新 PROGRESS.md，commit+push；
5) 输出 10 行摘要（完成/证据/阻塞/下一步）。
不要在没有运行证据时声称完成。
```
