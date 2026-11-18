"""业务断言：失败时抛出带上下文的 AssertionError（后续追加截图/Allure 步骤）。"""
from __future__ import annotations

from typing import Any


def assert_true(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_status(actual: str, expected: str, message: str = "") -> None:
    assert_true(
        actual == expected,
        message or f"状态不符：期望 {expected!r}，实际 {actual!r}",
    )


def assert_contains(text: str, keyword: str, message: str = "") -> None:
    assert_true(
        keyword in (text or ""),
        message or f"文本不包含 {keyword!r}：{(text or '')[:200]!r}",
    )


def assert_api_success(body: Any, message: str = "接口未返回 success=true") -> None:
    assert_true(
        isinstance(body, dict) and body.get("success") is True,
        f"{message}：{str(body)[:300]}",
    )


def assert_non_empty(value: Any, field_name: str) -> None:
    assert_true(
        value not in (None, "", [], {}),
        f"字段不能为空：{field_name}",
    )
