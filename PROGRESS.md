# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP4 已完成** → 下一步 WP5（专家抽取 + 论证）
- 分支：`main`

## 已完成
- [x] WP0 环境与骨架（env_check 38 PASS/1 WARN/0 FAIL）
- [x] WP1 会话/浏览器核心 + 冒烟（26 passed）
- [x] WP2 S01/S04/S05 迁移（P0 全链 18s，连续 2 次）
- [x] WP3 审批通用 + 调研信息/公告（P1 33s；全量 34 passed）
- [x] **WP4 供应商响应 + 资格性审查**
  - `pages/survey_project.py`：供应商侧参与调研、上传响应文件、技术参数
  - `pages/survey_result.py`：评审详情、干事逐家通过、提交主任、主任一键通过、提交结论
  - `flows/s08_supplier_reply.py`：3 家供应商（ybjcsgys1~3）响应
  - `flows/s10_review.py`：征集截止等待 → 干事初审 → 主任评审 → state=4
  - `tests/flows/test_p1_review.py`：自包含验收（P0→S06→S07→S08→S10）

## 证据（2026-11-18）
- `pytest tests/flows/test_p1_review.py -v -s` → **1 passed in 137.66s**
  - 申请单 FW-YWB-CG20260107；3 家供应商响应成功；初审 3 家通过；state=10 → **state=4 OK**
- `pytest tests/flows -q` → **4 passed, 1 skipped in 191.41s**
- 全量 `pytest -q` → **35 passed, 1 skipped in 199.71s**
- `env_check.py` → **PASS 38 / WARN 1 / FAIL 0**（9.3s）

## 本次沉淀的坑与解法
- 供应商响应上传：WebUploader 隐藏 input 在 `#replyFileSelect input[type=file]`，
  `set_input_files` 后必须等 `#replyFileList` 出现“已上传”再提交；
  技术参数行：`.js-nature`（1/2/3）+ `.js-name` + `.js-tech`；
- **资格性审查必须“征集截止后”**（`deadlinePassed`）：S06 把 endTime 设短（1.5 分钟），
  供应商响应完成后等待截止，打开详情时后端刷新 state 2→11，干事才能审核；
- 指定主任不能选第一个“主任”（可能是其他部门主任）：按 **loginName 关键字（zhaoliu）** 匹配选项文本；
- 用例间必须清理遗留弹窗：`tests/flows/conftest.py` 增加 autouse fixture，
  每例结束调 `layer.closeAll()`，否则上一用例的弹窗会遮挡下一用例（全量运行时暴露）；
- 主任“一键通过”→`#btnDirectorFinish`（等待可用）→ 确认，最终 state=4。

## 阻塞 / 已知项
- OnlyOffice(18099) 未启动（WARN，WP6 前启动）。
- 本地纪检 Redis DB 差异：登录后 key 同步缓解，`env_check` 会拦截 401。
- 全量套件约 3 分 20 秒（含 1.5 分钟征集截止等待），后续可考虑用配置缩短。

## 下一步（WP5）
1. `pages/survey_argument.py`：规划抽取（线下论证 + 手动抽选）+ 论证情况 + 上传论证结果；
2. `api/professor_mock.py`：生成 callid + keypress=1 模拟专家电话确认；
3. `flows/s11_extract.py`、`flows/s13_argument.py`：
   抽取 3 名专家并确认 → 指定组长 → 上传论证报告（wjc测试文件.pdf）→ 提交完成论证；
4. 验收：调研论证完成，申请单 status=15（待编制采购需求）。

## 证据索引
- 响应+审查：`python -m pytest tests/flows/test_p1_review.py -v -s`
- 全量：`python -m pytest -q`（35 passed, 1 skipped）
