"""S01 同名申请防重：不依赖环境/页面，用桩验证拦截逻辑。"""
from __future__ import annotations

import pytest

from flows import s01_apply as s01


class _Stop(Exception):
    """哨兵：证明代码已越过防重检查继续往下走。"""


def _ctx() -> dict:
    return {"project_name": "同名测试项目"}


def test_duplicate_name_blocks_before_page(monkeypatch):
    monkeypatch.setattr(s01, "get_user_info", lambda session: {"organizationId": "D1"})
    monkeypatch.setattr(
        s01, "find_request_by_name",
        lambda session, department_id, name: {"requestCode": "HW-YWB-CG20260001", "status": 9},
    )

    def _no_page(*args, **kwargs):  # 命中同名后不应再打开采购申请页
        raise AssertionError("命中同名后不应继续打开采购申请页")

    monkeypatch.setattr(s01, "ProcurementApplyPage", _no_page)
    with pytest.raises(AssertionError) as exc:
        s01.s01_apply(object(), _ctx())
    message = str(exc.value)
    assert "同名采购申请已存在" in message
    assert "HW-YWB-CG20260001" in message


def test_unique_name_continues(monkeypatch):
    monkeypatch.setattr(s01, "get_user_info", lambda session: {"organizationId": "D1"})
    monkeypatch.setattr(s01, "find_request_by_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        s01, "ProcurementApplyPage",
        lambda session: (_ for _ in ()).throw(_Stop()),
    )
    with pytest.raises(_Stop):
        s01.s01_apply(object(), _ctx())
