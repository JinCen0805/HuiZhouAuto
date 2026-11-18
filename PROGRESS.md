# 进度

> 每个 AI 工作包结束更新本文件，用于跨会话交接。

## 当前
- 工作包：**WP1 已完成** → 下一步 WP2（S01/S04/S05 迁移）
- 分支：`main`

## 已完成
- [x] 分析与技术方案（analysis/）
- [x] Playwright + Pytest 环境安装与验证
- [x] 供应商账号 ybjcsgys1~3 验证
- [x] 12 项业务默认值确认 + 附件素材就位
- [x] **WP0 环境与仓库骨架**（env_check 38 PASS/1 WARN/0 FAIL；pytest 5 passed）
- [x] **WP1 会话/浏览器核心 + 冒烟**
  - `core/session.py`：`HttpSession`（登录/选平台/角色）、`BrowserSession`
    （HTTP cookie→Playwright context、storageState 缓存、`menu_Json` 校验失效重登）
  - `core/browser.py`：`open_hp`、`get_frame`、`open_module`（changeView）、
    `confirm_dialog`（top 优先/frame 兜底）、`wait_for_msg`
  - `tests/smoke/`：5 角色登录 + 16 页面加载 + 5 个关键接口
  - 多角色账号按角色名显式选择（bailu 默认“专家评委”的坑已规避）

## 证据（2026-11-18）
- `python scripts/env_check.py` → **PASS 38 / WARN 1 / FAIL 0**（6.5s）
  - 唯一 WARN：OnlyOffice(18099) 未启动（WP6 前启动）
- `python -m pytest -q` → **31 passed in 10.24s**
- `python -m pytest tests/smoke -q` → **26 passed in 9.78s**；第二次运行 **26 passed in 9.62s**
  （storageState 缓存复用生效）
- `.sessions/` 已生成 5 个角色缓存文件，且被 `.gitignore` 忽略

## 阻塞 / 已知项
- OnlyOffice(18099) 未启动：WP6 前启动（WARN，不影响 P0/P1 前半段）。
- 本地纪检 Redis DB 差异：靠登录后 key 同步缓解；`env_check` 的“纪检接口鉴权”会拦截 401。
- 多角色账号必须显式指定角色关键字，否则默认第一个角色可能不是目标角色。

## 下一步（WP2）
1. `pages/procurement_apply.py` + `flows/s01_apply.py`（选计划→保存草稿→确认）
2. `api/jjjc_api.py` + `flows/s04_supervisor.py`（纪检分配）
3. `pages/package_management.py` + `flows/s05_package.py`（新增子包→确认）
4. `tests/flows/test_p0_main.py`：一条命令生成“待调研 + 调研项目”，连续 2 次通过

## 证据索引
- 环境自检：见本文件 §证据
- 冒烟：`python -m pytest tests/smoke -q`
