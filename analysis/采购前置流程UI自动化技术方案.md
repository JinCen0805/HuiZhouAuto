# 采购前置流程 UI 自动化 · 技术方案（Playwright + Pytest）

> 文档版本：v2.0（2026-11-18）—— 更新为 Playwright + Pytest 方案
> 适用范围：本地环境 `http://127.0.0.1`（本地全栈）
> 配套文档：[开发计划](采购前置流程UI自动化开发计划-Playwright-Pytest-AI.md)、[可行性评估](采购前置流程UI自动化可行性评估.md)
> 现有基础：`automation_py/` Python 实现（本方案已落地）

---

## 1. 技术选型

### 1.1 核心技术栈（已全部验证可用）

| 层 | 选型 | 版本 | 状态 |
|---|---|---|---|
| 运行时 | **Python 3.12.14**（DSH 内置） | 3.12.14 | ✅ 已有 |
| 浏览器自动化 | **playwright**（Python） | 1.65.2 | ✅ 刚安装，已验证可启动浏览器 |
| 浏览器引擎 | **本机 Chromium**（已有，复用 JS PoC 的） | chromium-1234 | ✅ 已验证打开 HP 首页正常 |
| 测试框架 | **pytest** | 9.2.0 | ✅ 已安装 |
| Playwright pytest 插件 | **pytest-playwright** | 0.10.0 | ✅ 已安装 |
| HTTP 请求 | **requests** | 2.34.2 | ✅ 已安装（登录/接口辅助） |
| 测试报告 | **pytest-html** / **allure-pytest** | 4.2.0 / 2.16.2 | ✅ 已安装 |
| Python 路径 | `C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe` | — | 固定 |
| Chromium 路径 | `C:\Users\Grayson\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe` | — | 固定 |

**关键验证**：已直接用 `sync_playwright` + 本机 Chromium 打开 `http://127.0.0.1/HospitalProcurement/index.html`，返回正确标题，无需再下载任何浏览器。

### 1.2 完整依赖

```
playwright==1.65.2
pytest==9.2.0
pytest-playwright==0.10.0
pytest-html==4.2.0
allure-pytest==2.16.2
requests==2.34.2
```

```bash
# 一条命令安装（已完成）
python -m pip install playwright pytest pytest-playwright pytest-html allure-pytest requests
```

### 1.3 为什么 Playwright + Pytest 是好选择

| 优势 | 说明 |
|---|---|
| **Pytest fixture 天然解决多账号问题** | 每个角色 session 写成 fixture，按需注入，自动缓存/销毁 |
| **参数化测试（pytest.mark.parametrize）** | 多供应商响应、多审批节点逐一跑，代码量减半 |
| **Page Object Model 与 pytest 契合** | conftest.py 集中管理 POM 实例化和浏览器生命周期 |
| **报告齐全** | pytest-html 开箱即用；allure 报告更美观，支持步骤/截图/附件 |
| **Python 团队更熟悉** | 比 Node 更普遍，新同学上手快 |
| **pytest-playwright 自动截图** | `--screenshot=on` 失败自动截图；`--tracing=on` 自动录 trace |
| **与现有 JS PoC 并存** | 新 Python 目录 `automation_py/`，与 `automation/` 并存，互不影响 |

### 1.4 pytest-playwright 与自定义的关系

`pytest-playwright` 提供的 `page`、`browser`、`context` fixture **不直接用于本项目**——
原因是本项目需要多账号、多 context 并行，以及 HTTP 登录后 cookie 注入，
不是简单的"每个 test 一个页面"模式。

方案：**只借用 `playwright` fixture 拿到 Playwright 实例**，其余 browser/context/page 全部自己管理。

---

## 2. 目录结构

```
automation_py/
├─ conftest.py              # pytest 全局配置：Playwright 实例、会话缓存、报告 hook
├─ pytest.ini               # pytest 配置：测试路径、marker、--screenshot、超时
│
├─ core/
│  ├─ session.py            # 多账号登录：HTTP 登录 + cookie 注入 Playwright context
│  ├─ browser.py            # 浏览器工厂：context 创建、changeView 开模块、iframe 定位
│  ├─ config.py             # 配置加载：flow_config.json + 环境变量（密码）
│  ├─ assert_helper.py      # 业务断言：失败自动截图 + 写 allure step
│  ├─ reporter.py           # 阶段报告：写 reports/{run_id}/report.json
│  └─ retry.py              # 重试装饰器（网络/超时类，最多 3 次）
│
├─ pages/                   # Page Object Model
│  ├─ procurement_apply.py  # 采购申请：列表、新增弹窗、申请单管理
│  ├─ package_management.py # 分包管理：列表、分包编辑弹窗
│  ├─ survey_project.py     # 调研项目管理：完善信息、编辑公告、立即发布
│  ├─ survey_result.py      # 调研结果：评审响应材料、资格性审查
│  ├─ survey_argument.py    # 调研论证：规划抽取、论证情况、上传结果
│  ├─ requirement.py        # 采购需求在线编制
│  ├─ audit_management.py   # 审计管理（HP 侧：推送）
│  ├─ demand_review.py      # 采购需求审查（三阶段）
│  ├─ method_confirm.py     # 采购方式分配
│  ├─ execution_apply.py    # 采购执行申请
│  ├─ approval.py           # 业务审批通用页（个人待办 + 办理弹窗）
│  └─ discipline.py         # 纪检监察平台（监察项目 + 采购专项审计）
│
├─ api/                     # API Helper（直调后端，不走浏览器）
│  ├─ jjjc_api.py           # 纪检：分配监督员、审计受理/通过
│  ├─ professor_mock.py     # 专家 mock：生成 callid、keypress=1 确认参加
│  ├─ signature_api.py      # 论证报告签名：获取 token、提交 base64 图
│  ├─ survey_api.py         # 立即发布公告 pushOneById
│  ├─ approval_api.py       # 审批待办查询 + 通用 complete（BT6/BT8/BT13/BT14）
│  └─ file_api.py           # 文件上传 /doFile/upload/ + download
│
├─ flows/                   # 流程层：每阶段一个函数，编排 Pages + APIs
│  ├─ s01_apply.py
│  ├─ s04_supervisor.py
│  ├─ s05_package.py
│  ├─ s06_survey_info.py
│  ├─ s07_notice.py
│  ├─ s08_supplier_reply.py
│  ├─ s10_review.py
│  ├─ s11_extract.py
│  ├─ s13_argument.py
│  ├─ s15_requirement.py
│  ├─ s16_audit.py
│  ├─ s18_demand_review.py
│  ├─ s19_method.py
│  ├─ s20_execution.py
│  └─ run_all.py            # 全链编排（读 run_context，调 S01→S20）
│
├─ tests/
│  ├─ smoke/
│  │  └─ test_smoke.py      # L1 冒烟：14 个页面可加载 + 关键接口 200
│  ├─ flows/
│  │  ├─ test_p0_main.py    # P0：S01→S04→S05 全链（生成"待调研"数据）
│  │  ├─ test_p1_survey.py  # P1：S06→S10（调研信息→供应商响应→资格审查）
│  │  ├─ test_p1_argument.py# P1：S11→S13（专家抽取→论证）
│  │  ├─ test_p2_docs.py    # P2：S15→S18（需求编制→审计→审查）
│  │  └─ test_p2_finish.py  # P2：S19→S20（方式分配→执行申请→采购中）
│  └─ regression/
│     └─ test_full_chain.py # 全链回归（依次运行所有阶段，断点续跑）
│
├─ fixtures/
│  ├─ flow_config.json      # 业务参数（部门/账号/模板/采购方式等）
│  └─ files/                # 附件素材（供应商响应文件、论证报告、文书等）
│
├─ reports/                 # 运行结果（.gitignore）
│  └─ {run_id}/             # report.json + screenshots/ + allure_results/
│
├─ scripts/
│  ├─ env_check.py          # 环境自检
│  └─ cleanup.py            # 按 runId 清理测试数据
│
├─ .env.local               # 密码（.gitignore）
├─ .gitignore
├─ requirements.txt
├─ pytest.ini
└─ README.md
```

---

## 3. 核心模块设计

### 3.1 `conftest.py`——pytest 全局配置

```python
# automation_py/conftest.py

import pytest
import os
from core.config import Config
from core.session import SessionManager
from core.browser import BrowserFactory
from core.reporter import Reporter

# ── 全局单例 ──────────────────────────────────────────────
@pytest.fixture(scope="session")
def config():
    """加载 flow_config.json + 环境变量"""
    return Config.load()

@pytest.fixture(scope="session")
def run_id(config):
    """生成唯一 run_id，贯穿整个测试会话"""
    import datetime, random, string
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = ''.join(random.choices(string.ascii_lowercase, k=3))
    return f"UI自动化-{ts}-{suffix}"

@pytest.fixture(scope="session")
def reporter(run_id):
    return Reporter(run_id)

@pytest.fixture(scope="session")
def pw_instance():
    """Playwright 实例（session 级，只启动一次）"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        yield pw

@pytest.fixture(scope="session")
def session_manager(config):
    return SessionManager(config)

# ── 角色 Session（按需缓存）────────────────────────────────
# 用 fixture 参数化账号名：每个角色只登录一次，复用到整个 session

@pytest.fixture(scope="session")
def session_applicant(session_manager, pw_instance):
    return session_manager.get_session(pw_instance, "applicant")

@pytest.fixture(scope="session")
def session_supervisor(session_manager, pw_instance):
    return session_manager.get_session(pw_instance, "supervisor")  # jjzr

@pytest.fixture(scope="session")
def session_audit_director(session_manager, pw_instance):
    return session_manager.get_session(pw_instance, "auditDirector")  # sjbzr

# ... 其他角色 fixture

# ── 失败自动截图 ───────────────────────────────────────────
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        # 截图保存到 reports/{run_id}/failures/
        page = item.funcargs.get("page")
        if page:
            path = f"reports/failures/{item.name}.png"
            os.makedirs("reports/failures", exist_ok=True)
            page.screenshot(path=path)
```

---

### 3.2 `core/session.py`——多账号登录与 cookie 管理

```python
# automation_py/core/session.py

import hashlib, requests, json, os
from pathlib import Path

CHROME_PATH = r"C:\Users\Grayson\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE_URL = os.getenv("HP_BASE", "http://127.0.0.1")

class Session:
    """单账号会话：HTTP cookie + Playwright context + http client"""
    def __init__(self, username: str, cookies: list, context, http: "HttpClient"):
        self.username = username
        self.cookies = cookies
        self.context = context      # Playwright BrowserContext
        self.http = http            # requests.Session（带 cookie）
    
    def new_page(self):
        return self.context.new_page()

class SessionManager:
    """缓存每个账号的 Session，避免重复登录"""
    
    def __init__(self, config):
        self.config = config
        self._cache: dict[str, Session] = {}
    
    def get_session(self, pw, role: str) -> Session:
        username = self.config.accounts[role]
        if username not in self._cache:
            self._cache[username] = self._login(pw, username)
        return self._cache[username]
    
    def _login(self, pw, username: str) -> Session:
        password = self._get_password(username)
        
        # 1. HTTP 登录
        s = requests.Session()
        s.get(f"{BASE_URL}/Register/login/verification.do")
        md5_pwd = hashlib.md5(password.encode()).hexdigest()
        resp = s.post(f"{BASE_URL}/Register/login/userLogin.do", data={
            "username": username,
            "password": md5_pwd,
            "checkCode": "qwe!@#",
            "SimplePwd": "0"
        })
        assert resp.json()["success"], f"登录失败：{username} -> {resp.text}"
        
        # 2. 选平台/角色
        sel = s.get(f"{BASE_URL}/Register/SelectPlatformAction/select.do").json()
        platform_key, role_key = self._find_platform_role(sel["data"], "采购交易系统")
        goto = s.post(f"{BASE_URL}/Register/SelectPlatformAction/gotoIndex.do", data={
            "platform": platform_key,
            "roleCode": role_key,
            "macAddress": "", "ipAddress": ""
        }).json()
        
        # 3. 注入 cookie 到 Playwright context
        cookies = [
            {"name": c.name, "value": c.value, "domain": "127.0.0.1", "path": "/"}
            for c in s.cookies
        ]
        browser = pw.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 900}, locale="zh-CN")
        context.add_cookies(cookies)
        
        return Session(username, cookies, context, s)
    
    def _get_password(self, username: str) -> str:
        key = f"HP_PASSWORD_{username.upper().replace('-', '_')}"
        pwd = os.getenv(key)
        if not pwd:
            raise EnvironmentError(f"密码未配置：{key}")
        return pwd
    
    def _find_platform_role(self, data, platform_name: str):
        """从 select.do 返回的 AES 密文中找目标平台和角色"""
        platform_key = next(
            k for item in data["platform"] for k, v in item.items() if v == platform_name
        )
        for item in data["roleCode"]:
            if platform_key in item:
                role_key = next(k for k in item if k != platform_key)
                return platform_key, role_key
        raise ValueError(f"未找到平台 {platform_name} 的角色")
```

---

### 3.3 `core/browser.py`——iframe 与弹窗操作

```python
# automation_py/core/browser.py

import re
from playwright.sync_api import Page, Frame

CHROME_PATH = r"C:\Users\Grayson\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
HP_INDEX = "http://127.0.0.1/HospitalProcurement/index.html"

def open_hp(session) -> Page:
    """打开 HP 首页，等待菜单渲染"""
    page = session.new_page()
    target = session.http.post(
        "http://127.0.0.1/Register/SelectPlatformAction/gotoIndex.do"
    ).json().get("data", HP_INDEX)
    page.goto(f"http://127.0.0.1{target}", wait_until="domcontentloaded")
    page.wait_for_selector("#menu li", timeout=15000)
    return page

def open_module(page: Page, url: str, menu_id: str = "") -> Frame:
    """
    通过 changeView 打开业务模块，返回目标 iframe。
    比菜单点击更稳定——不受菜单折叠/显隐影响。
    """
    page.evaluate(f"changeView('', '{url}', '{menu_id}')")
    # 等待 iframe 以该 URL 出现
    page.wait_for_function(
        f"[...document.querySelectorAll('iframe')].some(f => f.src.includes('{url.split('?')[0]}'))",
        timeout=15000
    )
    return get_frame(page, url)

def get_frame(page: Page, url_pattern: str) -> Frame:
    """按 URL 关键字定位 iframe"""
    pattern = re.compile(re.escape(url_pattern.split("?")[0]))
    for frame in page.frames:
        if pattern.search(frame.url):
            return frame
    raise RuntimeError(f"Frame not found: {url_pattern}")

def confirm_dialog(page: Page, frame: Frame, btn_text: str = "确定", timeout: int = 15000):
    """
    处理双套弹窗（HCUI.popDialog 弹 top / layer.open 弹 frame）。
    策略：top 优先，500ms 后查 frame。
    """
    import time
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        # top 层
        top_btns = page.locator(f".layui-layer-dialog .layui-layer-btn0")
        if top_btns.count() > 0:
            top_btns.last.click()
            return "top"
        # frame 层
        frame_btns = frame.locator(f".layui-layer-dialog .layui-layer-btn0")
        if frame_btns.count() > 0:
            frame_btns.last.click()
            return "frame"
        page.wait_for_timeout(200)
    raise TimeoutError(f"Confirm dialog '{btn_text}' not found after {timeout}ms")

def wait_for_msg(page: Page, frame: Frame, timeout: int = 5000) -> str:
    """等待 Layui msg 弹窗并返回文本"""
    # msg 通常弹在 top
    try:
        page.wait_for_selector(".layui-layer-msg", timeout=timeout)
        return page.locator(".layui-layer-msg").last.inner_text()
    except Exception:
        return ""
```

---

### 3.4 Page Object 示例——`pages/procurement_apply.py`

```python
# automation_py/pages/procurement_apply.py

from playwright.sync_api import Frame
from core.browser import confirm_dialog, wait_for_msg

MODULE_URL = "/HospitalProcurement/view/procurementApply/list.html"
MENU_ID = "0000006000001"

class ProcurementApplyPage:
    """采购申请管理页（L1 iframe）"""
    
    def __init__(self, page, frame: Frame):
        self.page = page
        self.frame = frame
    
    # ── 发起采购申请 Tab ──────────────────────────────────────
    def get_first_enabled_plan(self) -> dict:
        """返回第一条可发起的预算计划行数据"""
        rows = self.frame.locator(
            ".layui-table-view:not(.layui-table-fixed) .layui-table-body "
            "button[lay-event='singleLaunch']:not(.visual-disabled)"
        )
        rows.first.wait_for(state="visible", timeout=15000)
        row = rows.first.locator("xpath=ancestor::tr")
        cells = row.locator("td").all_inner_texts()
        return {"row_text": " ".join(cells), "btn": rows.first}
    
    def click_single_launch(self, btn):
        btn.click()
        self.page.wait_for_function(
            "[...document.querySelectorAll('iframe')].some(f => f.src.includes('procurementApply/edit'))",
            timeout=10000
        )
    
    # ── 新增采购申请弹窗 ──────────────────────────────────────
    def fill_application(self, project_name: str):
        """弹窗在 top 层的 layer iframe 里"""
        from core.browser import get_frame
        edit_frame = get_frame(self.page, "procurementApply/edit.html")
        edit_frame.wait_for_selector("[idname='projectName']", timeout=10000)
        edit_frame.fill("[idname='projectName']", project_name)
        edit_frame.select_option("[idname='projectAttribute']", "1")
        edit_frame.fill("[idname='purchaseContent']", "自动化测试采购内容")
        edit_frame.fill("[idname='applicationReason']", "自动化测试申请理由")
    
    def save_draft(self):
        """点保存草稿按钮（在 top 层的 layer btn 区）"""
        self.page.locator(".layui-layer-btn a:has-text('保存草稿')").last.click()
        self.page.wait_for_timeout(3000)
    
    # ── 申请单管理 Tab ────────────────────────────────────────
    def switch_to_applications_tab(self):
        self.frame.locator(".layui-tab-title li[lay-id='applications']").click()
        self.frame.wait_for_function(
            "document.querySelector('#applicationTable + .layui-table-view tr')",
            timeout=15000
        )
    
    def find_application_row(self, project_name: str) -> Frame:
        rows = self.frame.locator(
            ".layui-table-view:not(.layui-table-fixed) .layui-table-body tr"
        )
        for i in range(rows.count()):
            if project_name in rows.nth(i).inner_text():
                return rows.nth(i)
        raise LookupError(f"申请单 '{project_name}' 未找到")
    
    def confirm_application(self, row, project_name: str) -> str:
        """点列表行的确认按钮，返回确认后状态文字"""
        row.locator("button[lay-event='confirm']").click()
        confirm_dialog(self.page, self.frame)
        self.page.wait_for_timeout(3000)
        # 重新找到这行，读状态列
        updated_row = self.find_application_row(project_name)
        cells = updated_row.locator("td").all_inner_texts()
        # status 在第 8 列
        return cells[7] if len(cells) > 7 else ""
```

---

### 3.5 测试文件示例——`tests/flows/test_p0_main.py`

```python
# automation_py/tests/flows/test_p0_main.py

import pytest
import allure
from core.browser import open_hp, open_module, MODULE_URL as HP_BASE
from pages.procurement_apply import ProcurementApplyPage, MODULE_URL as APPLY_URL, MENU_ID as APPLY_MENU
from pages.package_management import PackageManagementPage
from api.jjjc_api import JjjcApi
from core.assert_helper import assert_status, assert_api_success
import datetime, random, string

@pytest.fixture(scope="module")
def run_context():
    """P0 阶段共享上下文"""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return {
        "run_id": f"UI自动化-{ts}",
        "project_name": f"UI自动化-{ts}-心电监护仪",
        "request_code": None,
        "request_id": None,
    }


class TestP0MainChain:
    """P0 主链：采购申请 → 纪检分配 → 分包 → 生成调研项目"""
    
    @allure.title("S01 - 采购申请发起（计划内，单独发起）")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_s01_apply(self, session_applicant, run_context):
        with allure.step("打开 HP 首页并进入采购申请管理"):
            page = open_hp(session_applicant)
            frame = open_module(page, APPLY_URL, APPLY_MENU)
            apply_page = ProcurementApplyPage(page, frame)
        
        with allure.step("选第一条可用预算计划，点单独发起"):
            plan = apply_page.get_first_enabled_plan()
            allure.attach(plan["row_text"], name="选中的预算计划", attachment_type=allure.attachment_type.TEXT)
            apply_page.click_single_launch(plan["btn"])
        
        with allure.step("填写申请表单并保存草稿"):
            apply_page.fill_application(run_context["project_name"])
            apply_page.save_draft()
        
        with allure.step("切换到申请单管理 Tab，找到草稿并确认"):
            apply_page.switch_to_applications_tab()
            row = apply_page.find_application_row(run_context["project_name"])
            status = apply_page.confirm_application(row, run_context["project_name"])
        
        with allure.step("断言状态变为待分配监督员"):
            assert_status(status, "待分配监督员", f"申请确认后状态应为待分配监督员，实际：{status}")
        
        # 保存申请单号供后续阶段使用
        row_text = apply_page.find_application_row(run_context["project_name"]).inner_text()
        import re
        match = re.search(r'[A-Z]{2,}-[A-Z0-9]+-CG\d+', row_text)
        run_context["request_code"] = match.group() if match else ""
        allure.attach(run_context["request_code"], name="申请单号", attachment_type=allure.attachment_type.TEXT)
        page.close()
    
    @allure.title("S04 - 纪检主任分配监督员")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_s04_supervisor(self, session_supervisor, run_context):
        assert run_context.get("request_code"), "依赖 S01，申请单号不能为空"
        
        jjjc = JjjcApi(session_supervisor.http)
        
        with allure.step("获取监督员列表"):
            candidates = jjjc.list_supervisors()
            supervisor = next(s for s in candidates if s["onDutyStatus"] == "在岗")
        
        with allure.step(f"查找待分配项目 {run_context['project_code']}"):
            project = jjjc.find_project(run_context["project_name"])
            assert project, f"纪检平台未找到项目：{run_context['project_name']}"
        
        with allure.step("分配监督员（全流程）"):
            result = jjjc.assign_supervisor(
                project_id=project["uuid"],
                supervisor_user_id=supervisor["supervisorUserId"],
                scope="1"
            )
            assert_api_success(result, "分配监督员失败")
        
        with allure.step("断言项目状态变为待分包（requestStatus=8）"):
            updated = jjjc.find_project(run_context["project_name"])
            assert updated["requestStatus"] == "8", f"分配后状态应为 8，实际：{updated['requestStatus']}"
    
    @allure.title("S05 - 项目分包（新增子包 → 确认锁定）")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_s05_package(self, session_applicant, run_context):
        from pages.package_management import PackageManagementPage, MODULE_URL as PKG_URL, MENU_ID as PKG_MENU
        
        page = open_hp(session_applicant)
        frame = open_module(page, PKG_URL, PKG_MENU)
        pkg_page = PackageManagementPage(page, frame)
        
        with allure.step(f"在分包管理列表找到 {run_context['request_code']}"):
            pkg_page.search(run_context["request_code"])
            row = pkg_page.find_row(run_context["request_code"])
        
        with allure.step("点分包，新增子包（选所有预算计划）"):
            pkg_page.open_editor(row)
            sub_name = f"{run_context['run_id']}-子包01"
            pkg_page.add_subpackage(sub_name)
        
        with allure.step("确认分包锁定"):
            pkg_page.confirm_package(run_context["request_code"])
        
        with allure.step("断言是否分包=是，且调研项目已生成"):
            is_packaged = pkg_page.is_packaged(run_context["request_code"])
            assert is_packaged, "分包确认后 '是否分包' 应为 '是'"
        
        with allure.step("切到调研项目管理，断言项目已生成"):
            from pages.survey_project import SurveyProjectPage, MODULE_URL as SURVEY_URL, MENU_ID as SURVEY_MENU
            survey_frame = open_module(page, SURVEY_URL, SURVEY_MENU)
            survey = SurveyProjectPage(page, survey_frame)
            assert survey.project_exists(run_context["project_name"]), "调研项目未自动生成"
        
        page.close()
```

---

### 3.6 `pytest.ini`——pytest 配置

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 失败时自动截图（由 pytest-playwright 提供）
addopts =
    --screenshot=only-on-failure
    --output=reports/screenshots
    --tb=short
    --timeout=120

# 自定义 marker
markers =
    smoke: 冒烟测试（L1）
    p0: 主链前半段（S01→S05）
    p1: 调研论证（S06→S13）
    p2: 需求执行（S15→S20）
    full: 全链回归
```

---

### 3.7 运行脚本——`scripts/run_flow.py`（支持断点续跑）

```python
# automation_py/scripts/run_flow.py
# 用法：
#   python scripts/run_flow.py                      # 全链
#   python scripts/run_flow.py --from s11           # 从 S11 续跑
#   python scripts/run_flow.py --run-id UI自动化-xxx # 指定 run_id

import argparse, json, os
from pathlib import Path

STAGES = ["s01", "s04", "s05", "s06", "s07", "s08", "s10", "s11", "s13", "s15", "s16", "s18", "s19", "s20"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="from_stage", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stages", default=None, help="指定阶段，逗号分隔，如 s01,s04,s05")
    args = parser.parse_args()
    
    stages = args.stages.split(",") if args.stages else STAGES
    if args.from_stage:
        idx = next((i for i, s in enumerate(stages) if s == args.from_stage), 0)
        stages = stages[idx:]
    
    # 构建 pytest 命令
    test_files = [f"tests/flows/test_{s}*.py" for s in stages]
    cmd = f"python -m pytest {' '.join(test_files)} -v --alluredir=reports/allure_results"
    if args.run_id:
        cmd += f" --run-id={args.run_id}"
    
    print(f"Running: {cmd}")
    os.system(cmd)

if __name__ == "__main__":
    main()
```

---

## 4. 关键技术问题解法

### 4.1 多层 iframe 定位

```python
# 不用 page.frame_locator()——系统 iframe 无稳定 CSS 选择器
# 用 page.frames 列表按 URL 过滤

def get_frame(page: Page, url_pattern: str) -> Frame:
    import re
    pattern = re.compile(re.escape(url_pattern.split("?")[0]))
    for frame in page.frames:
        if pattern.search(frame.url):
            return frame
    raise RuntimeError(f"Frame not found: {url_pattern}")
```

### 4.2 Layui 表格固定列 DOM 重复

```python
# 固定列（fixed left/right）会复制一份 DOM，导致同一行出现两次
# 策略：只在 :not(.layui-table-fixed) 容器内查找

row_locator = frame.locator(
    ".layui-table-view:not(.layui-table-fixed) .layui-table-body tr"
)
```

### 4.3 双套弹窗（top/frame）

```python
# HCUI.popDialog → 弹在 top (page)
# layer.open type:1 → 弹在 iframe (frame)

def confirm_dialog(page, frame, timeout=15000):
    import time
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if page.locator(".layui-layer-dialog .layui-layer-btn0").count() > 0:
            page.locator(".layui-layer-dialog .layui-layer-btn0").last.click()
            return "top"
        if frame.locator(".layui-layer-dialog .layui-layer-btn0").count() > 0:
            frame.locator(".layui-layer-dialog .layui-layer-btn0").last.click()
            return "frame"
        page.wait_for_timeout(200)
    raise TimeoutError("弹窗未出现")
```

### 4.4 密码管理

```bash
# .env.local（.gitignore）
HP_PASSWORD_CBBM1=<测试密码>
HP_PASSWORD_WANGLUN=<测试密码>
HP_PASSWORD_JJZR=<测试密码>
...
```

```python
# 启动前加载
from dotenv import load_dotenv  # 或手动解析
load_dotenv(".env.local")
```

---

## 5. 运行方式

```bash
$PYTHON = "C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$PYTEST = "C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\Scripts\pytest.exe"

# 环境自检
& $PYTHON scripts/env_check.py

# P0 冒烟
& $PYTEST tests/smoke/ -v

# P0 全链（S01→S05）
& $PYTEST tests/flows/test_p0_main.py -v --alluredir=reports/allure_results

# 全链回归
& $PYTEST tests/regression/ -v --alluredir=reports/allure_results

# 查看 Allure 报告
allure serve reports/allure_results

# 断点续跑
& $PYTHON scripts/run_flow.py --from s11 --run-id UI自动化-20261119-143022-abc
```

---

## 6. 与现有 JS PoC 的关系

| 项 | JS PoC（`automation/`） | Python 新版（`automation_py/`） |
|---|---|---|
| 状态 | 已可运行（S01/S04/S05）| 本方案目标 |
| 存档 | 保留，不删除 | 新建目录，互不影响 |
| 参考 | 登录逻辑、接口 URL、iframe 定位策略全部可复用 | 直接翻译，不从零探索 |
| 依赖 | playwright-core（Node）| playwright + pytest（Python）|

JS PoC 中探测出的所有接口 URL、cookie 机制、菜单 id、iframe URL、弹窗处理策略，
**直接翻译为 Python 版**，不需要重新摸索。

---

## 7. 技术风险与应对

| 风险 | 应对 |
|---|---|
| `pytest-playwright` 与多账号/有状态流程冲突 | 只借 `playwright` fixture 拿 Playwright 实例，自己管 browser/context/page |
| `requests.Session` cookie 与 Playwright cookie 不同步 | 每次 gotoIndex 后重新取 `requests.cookies` 注入 Playwright |
| Layui 固定列 DOM 重复导致重复操作 | 统一用 `:not(.layui-table-fixed)` 选择器 |
| Allure 报告路径/编码问题（Windows） | `--alluredir` 指定相对路径；文件名用 ASCII run_id |
| Python 路径未加入 PATH（pytest.exe 警告） | 脚本里用绝对路径调用；不依赖 PATH |
