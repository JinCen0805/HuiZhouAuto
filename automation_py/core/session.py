"""HTTP 会话：登录 → 选平台/角色 → 进入系统（不依赖浏览器）。

已验证链路（本地）：
1. GET  /Register/login/verification.do       建立 JSESSIONID
2. POST /Register/login/userLogin.do          password=MD5(明文), checkCode=服务端测试万能码
3. GET  /Register/SelectPlatformAction/select.do   返回平台/角色 AES 密文
4. POST /Register/SelectPlatformAction/gotoIndex.do 原样回传密文，返回目标系统 URL
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import requests

from core.config import DEFAULT_BASE_URL

# 服务端 LoginAction 中内置的测试验证码（本地/测试环境用；生产应移除）
TEST_CAPTCHA = "qwe!@#"


@dataclass
class HttpSession:
    base_url: str = DEFAULT_BASE_URL
    timeout: int = 20
    http: requests.Session = field(default_factory=requests.Session)
    username: str | None = None
    platform: str | None = None
    role: str | None = None
    redirect_url: str | None = None

    def url(self, path: str) -> str:
        return path if path.startswith("http") else self.base_url + path

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.http.get(self.url(path), timeout=self.timeout, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.http.post(self.url(path), timeout=self.timeout, **kwargs)

    # ── 登录链路 ──────────────────────────────────────────────
    def login(self, username: str, password: str) -> "HttpSession":
        self.username = username
        self.get("/Register/login/verification.do")
        resp = self.post(
            "/Register/login/userLogin.do",
            data={
                "username": username,
                "password": hashlib.md5(password.encode("utf-8")).hexdigest(),
                "checkCode": TEST_CAPTCHA,
                "SimplePwd": "0",
            },
        )
        try:
            body = resp.json()
        except ValueError as exc:  # 非 JSON 视为失败
            raise RuntimeError(f"登录响应非 JSON：{resp.status_code} {resp.text[:200]}") from exc
        if not body.get("success"):
            raise RuntimeError(f"登录失败（{username}）：{body.get('mgs') or body}")
        return self

    def select_platform(self, platform_label: str, role_keyword: str | None = None) -> tuple[str, str]:
        """返回 (platform_key, role_key)；密文原样回传，不解密。

        role_keyword：按角色显示名关键字选择（多角色账号必须显式指定，
        例如 bailu 的采购交易系统默认第一个角色是“专家评委”而非“采购执行部门主任”）。
        """
        resp = self.get("/Register/SelectPlatformAction/select.do")
        data = (resp.json() or {}).get("data") or {}
        platform_key = None
        for item in data.get("platform") or []:
            for key, label in item.items():
                if label == platform_label:
                    platform_key = key
        if not platform_key:
            raise RuntimeError(f"未找到平台：{platform_label}；可选：{data.get('platform')}")
        candidates: list[tuple[str, str]] = []
        for item in data.get("roleCode") or []:
            if platform_key in item:
                for key, label in item.items():
                    if key != platform_key:
                        candidates.append((key, label))
        if not candidates:
            raise RuntimeError(f"平台 {platform_label} 未找到可用角色")
        role_key, role_label = candidates[0]
        if role_keyword:
            matched = [c for c in candidates if role_keyword in c[1]]
            if not matched:
                raise RuntimeError(
                    f"平台 {platform_label} 未找到角色（关键字 {role_keyword!r}）；"
                    f"可选：{[c[1] for c in candidates]}"
                )
            role_key, role_label = matched[0]
        self.platform = platform_label
        self.role = role_label
        return platform_key, role_key

    def goto_index(self, platform_label: str, role_keyword: str | None = None) -> str:
        platform_key, role_key = self.select_platform(platform_label, role_keyword)
        resp = self.post(
            "/Register/SelectPlatformAction/gotoIndex.do",
            data={
                "platform": platform_key,
                "roleCode": role_key,
                "macAddress": "",
                "ipAddress": "",
            },
        )
        body = resp.json() or {}
        if not body.get("success") or not body.get("data"):
            raise RuntimeError(f"gotoIndex 失败：{body}")
        self.redirect_url = body["data"]
        return self.redirect_url

    def cookie_header(self) -> str:
        return "; ".join(f"{c.name}={c.value}" for c in self.http.cookies)

    def cookie_list(self) -> list[dict]:
        return [
            {"name": c.name, "value": c.value, "domain": "127.0.0.1", "path": "/"}
            for c in self.http.cookies
        ]

    def menu_json(self) -> dict:
        resp = self.get(
            "/nodeJs/menu_Json",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        return resp.json() or {}


def login_http(username: str, password: str, platform_label: str = "采购交易系统",
               base_url: str = DEFAULT_BASE_URL,
               role_keyword: str | None = None) -> HttpSession:
    """登录并进入目标平台，返回带 cookie 的会话（失败抛 RuntimeError）。"""
    session = HttpSession(base_url=base_url)
    session.login(username, password)
    session.goto_index(platform_label, role_keyword)
    return session
