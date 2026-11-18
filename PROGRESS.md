# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP2 已完成** → 下一步 WP3（审批通用 + 调研信息/公告）
- 分支：`main`

## 已完成
- [x] 分析与技术方案
- [x] 环境安装与账号验证（含供应商 ybjcsgys1~3）
- [x] 12 项业务默认值确认 + 附件素材
- [x] **WP0 环境与骨架**（env_check 38 PASS/1 WARN/0 FAIL；pytest 5 passed）
- [x] **WP1 会话/浏览器核心 + 冒烟**（26 passed；storageState 缓存/失效重登）
- [x] **WP2 S01/S04/S05 迁移**
  - `pages/procurement_apply.py`（单独发起→填表→保存草稿→申请单管理→确认）
  - `pages/package_management.py`（搜索→分包→新增子包→保存→关闭→确认）
  - `api/jjjc_api.py`（监督员列表/项目查询/分配监督员）、`api/hp_api.py`（用户信息/申请单查询）
  - `flows/s01_apply.py`、`flows/s04_supervisor.py`、`flows/s05_package.py`
  - `tests/flows/test_p0_main.py`（一条链：申请→纪检→分包→调研项目）
  - 通用表格辅助 `pages/common.py`（可见表格等待、行定位、行内按钮）

## 证据（2026-11-18）
- `pytest tests/flows/test_p0_main.py -v -s` → **1 passed in 18.44s**
  - runId=UI自动化-20261118-194659-kpr；申请单 HW-YWB-CG20260179；
    状态 22 → 8 → 7；调研项目已生成
- 第二次运行 → **1 passed in 18.24s**（可重复，数据带 runId 前缀）
- 全量 `pytest -q` → **32 passed in 27.66s**
- `env_check.py` 保持 **PASS 38 / WARN 1 / FAIL 0**

## 本次沉淀的坑与解法
- Layui 原生 `select` 被隐藏：用 `evaluate` 直接 set value + `change`，再 `form.render('select')`；
- 页签切换后旧表格仍隐藏：等待“可见的” `.layui-table-view` 有行（`offsetParent !== null`），
  行定位统一用 `.layui-table-view:visible`；
- 保存草稿后编辑 iframe 关闭需要轮询等待，不能只等固定时长；
- 控制台 GBK 无法输出 `✓` 等符号：日志只用 GBK 可编码字符（建议运行时设 `PYTHONIOENCODING=utf-8`）；
- 采购申请分页接口必须带 `departmentId`（取用户 `organizationId`）。

## 阻塞 / 已知项
- OnlyOffice(18099) 未启动（WARN，WP6 前启动）。
- 纪检 Redis DB 差异：登录后 key 同步缓解，`env_check` 会拦截 401。

## 下一步（WP3）
1. `api/approval_api.py`：待办查询 + 通用办理（BT6/BT8/BT13/BT14/BT19），先对存量待办验证；
2. `pages/survey_project.py` + `flows/s06_survey_info.py`（起止时间/概况/评审指标）；
3. `flows/s07_notice.py` + `api/survey_api.py`（模板/立即发布 `state=2`）；
4. 验收：存量数据可完成 1 次审批；调研信息保存成功；公告立即发布成功。

## 证据索引
- P0 全链：`python -m pytest tests/flows/test_p0_main.py -v -s`
- 全量：`python -m pytest -q`（32 passed）
- 环境：`python scripts/env_check.py`
