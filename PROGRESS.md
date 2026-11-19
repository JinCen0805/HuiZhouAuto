# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP8 已完成（单入口全链 / 断点续跑 / 失败重试 / HTML+JSON 报告）** → 下一步 WP9（稳定性/清理/交付文档）
- 分支：`main`

## 已完成
- [x] WP0 环境与骨架（env_check 40 PASS）
- [x] WP1 会话/浏览器核心 + 冒烟
- [x] WP2 S01/S04/S05（P0）
- [x] WP3 审批通用 + 调研信息/公告
- [x] WP4 供应商响应 + 资格性审查（state=4）
- [x] WP5 专家抽取 + 线下论证（state=6 / status=15）
- [x] WP6 需求编制 + 审计（status=20）
- [x] WP7 终稿确认 + 三方审查 + 方式分配 + 执行申请（status=9）
- [x] **WP8 全链编排**
  - `flows/orchestrator.py`：步骤注册、断点续跑解析、失败重试、报告汇总
  - `scripts/run_full_chain.py`：单入口 CLI（--resume/--from/--retries/--headed）
  - `core/reporter.py`：report.json + report.html（步骤/耗时/状态/错误/申请单）
  - `tests/unit/test_orchestrator.py`：5 个无浏览器单元测试
  - 各流程增加断点幂等判断（S15/S16/S17/S18/S19/S20）
  - S05 新增子包改为轮询等待（修复偶发“新增子包未显示”抖动）

## 证据（2026-11-19）
- **单入口全新全链**：`python scripts/run_full_chain.py`
  → **success，最终 status=9 采购中，总耗时 273.5s**（4.6 分钟）
  - 报告：`reports/<runId>/report.json` + `report.html`
  - 步骤耗时：S01 3.1s、S04 0.1s、S05 12.4s、S06 7.2s、S07 6.1s、S08 19.4s、
    S10 85.9s、S11 5.8s、S13 119.4s、S15 1.9s、S16 1.6s、S17 1.1s、
    S18 1.8s、S19 2.4s、S20 5.3s
- **断点续跑**：`python scripts/run_full_chain.py --resume`
  → 自动识别申请单 status=20 并从 S17 续跑，**success / status=9**
- 编排单元测试：**5 passed in 3.12s**
- 默认全量 pytest：**41 passed, 4 skipped in 230.79s**
- `env_check.py`：**PASS 40 / WARN 0 / FAIL 0**

## 用法
```powershell
cd D:\Desktop\HuiZhouAuto\automation_py
$py = "C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py scripts/run_full_chain.py                 # 全新全链
& $py scripts/run_full_chain.py --resume        # 自动续跑最近未完成单
& $py scripts/run_full_chain.py --from S15      # 指定起始步骤
& $py scripts/run_full_chain.py --retries 2     # 失败重试次数
```
- 退出码：成功 0，失败 1（可接 CI）。
- 续跑映射：22→S04、8→S05、7→S06、4→S10、15/16→S15、17→S16、20→S17、19/18→S18、10→S19、11→S20、9→已完成。

## 环境恢复记录（2026-11-19）
- 休息约 13 小时后登录报“服务异常”：ZK 中 `DistributedLoginService` 的 **providers 为空**
  （网络/IP 变化后 baseserver 的 Dubbo 注册失效；consumers 仍在）。
- 处理：`local-stack.ps1 restart-service -Service baseserver` → provider 重新注册，env_check 恢复 40 PASS。
- 经验：长时间空闲/网络切换后先跑 `env_check.py`，若 provider 为空重启对应 provider 服务（baseserver 等）。

## 下一步（WP9）
1. 稳定性：同一环境连续跑 2~3 次全链，记录成功率和耗时分布；
2. 数据清理：按 `UI自动化-*` 前缀清理测试申请/调研/审计/执行数据（只清本地测试数据）；
3. 交付文档：快速上手、环境修复手册、已知限制（扫码签名/OnlyOffice/回调端口等）；
4. 最终验收报告与 Git 收尾。

## 证据索引
- 单入口：`python scripts/run_full_chain.py`（273.5s，status=9）
- 续跑：`python scripts/run_full_chain.py --resume`
- 默认全量：`python -m pytest -q`（41 passed, 4 skipped）
- 环境：`python scripts/env_check.py`（40 PASS）
