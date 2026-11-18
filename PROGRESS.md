# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP6 已完成** → 下一步 WP7（终稿确认 + 三方审查 + 方式分配 + 执行申请）
- 分支：`main`

## 已完成
- [x] WP0 环境与骨架（env_check 全绿）
- [x] WP1 会话/浏览器核心 + 冒烟（26 passed）
- [x] WP2 S01/S04/S05（P0 全链）
- [x] WP3 审批通用 + 调研信息/公告
- [x] WP4 供应商响应 + 资格性审查（state=4）
- [x] WP5 专家抽取 + 线下论证（state=6 / status=15）
- [x] **WP6 采购需求编制 + 审计（status=20 审计通过待二次确认）**
  - `api/document_api.py`：模板列表/创建需求书/保存/提交 BT14/审计推送
  - `api/audit_api.py`：纪检平台审计列表/详情/报告/审理/主任通过
  - `api/audit_report.py`：本地用 JWT 回调协议保存审计报告（免开关 OnlyOffice 编辑器）
  - `scripts/local_env.py`：同步纪检平台登录 key（Redis DB9→DB7）
  - `flows/s15_requirement.py`、`flows/s16_audit.py`
  - `tests/flows/test_p2_requirement_audit.py`（自包含全链，默认跳过）

## 本地环境变更（WP6，用户已授权继续）
1. 启动 OnlyOffice 容器（18099，healthy）。
2. `db/infra/local-stack/local-stack.ps1`（untracked 本地文件）：
   - business-approval 的 `hospital.procurement.baseUrl` 覆盖为 `http://127.0.0.1:17825`
     （原配置指向生产端口 7825，导致 BT14/BT6/BT13 回调失败、状态停在审批中）。
3. `discipline-supervision/src/main/resources/application-local.yml`（**tracked，未提交**）：
   - `file.download-base-url` 7707 → 17707（本地文件服务实际下载端口）。
4. 已重启 business-approval、discipline-supervision、professor、onlyoffice。

## 证据（2026-11-18）
- `HP_FULL_CHAIN=1 HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p2_requirement_audit.py -v -s`
  → **1 passed in 271.84s**
  - S15：需求书创建/保存/提交 BT14 → 主任通过 → status=17
  - S16：推送审计 → 报告生成/保存 → 审理 → 审计部主任通过 → **status=20**
- 手工验证（前一条数据）：审计推送 attachRequirementDocument=1 成功、报告回调保存、
  主任通过后 HP status=20
- 默认全量 `pytest -q` → **36 passed, 3 skipped in 208.45s**
- `env_check.py` → **PASS 40 / WARN 0 / FAIL 0**（OnlyOffice、MQ 桥接均 PASS）

## 本次沉淀的坑与解法
- BT14 完成回调依赖 business-approval 的 `hospital.procurement.baseUrl`，本地必须指向 17825；
  否则流程实例结束但业务状态停在 16。
- discipline 本地读取 Redis DB7，审计/纪检账号（sjyj/sjbzr/jjzr）登录后需同步 DB9→DB7 key。
- 审计报告保存：本地不必打开 OnlyOffice 编辑器，可用与 OnlyOffice 同协议的
  JWT 回调（HS256 + 下载回写）把报告落库为“已保存”；生产仍由编辑器触发。
- 审计页面 UI（review.html）在 auditStatus=2 后审计员无法再进入；报告必须在提交审理前保存。
- 需求书保存：`createByTemplate` 后 `confirm-save` 即可（force-save 在未打开编辑器时会失败）。

## 阻塞 / 已知项
- `discipline-supervision/src/main/resources/application-local.yml` 的 1 行本地修改未提交；
  按项目规则需用户确认后提交（该修改仅影响 local profile）。
- 默认全量套件跳过 3 个需显式开关的链（审批写、论证链、P2 全链），
  全链验收需 `HP_ARGUMENT_MQ_BRIDGE=1`（P2 另需 `HP_FULL_CHAIN=1`）。

## 下一步（WP7）
1. S17 终稿确认（`documentApproval/second-confirmation`）；
2. S18 三方审查（财务/审计/采购并行 + 纪检终审）；
3. S19 采购方式分配 + BT6；
4. S20 采购执行申请 + BT13 → **status=9 采购中**。

## 证据索引
- P2 全链：`HP_FULL_CHAIN=1 HP_ARGUMENT_MQ_BRIDGE=1 pytest tests/flows/test_p2_requirement_audit.py -v -s`
- 默认全量：`python -m pytest -q`（36 passed, 3 skipped）
- 环境：`python scripts/env_check.py`（40 PASS）
