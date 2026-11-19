"""采购方式选择单元测试。"""
from __future__ import annotations

import pytest

from core.procurement_method import resolve


def test_default_is_competitive_selection():
    result = resolve({"governmentProcurement": "否"})
    assert result.category == "1"
    assert result.method == "2"
    assert result.name == "比选采购"
    assert result.needs_bid_evaluation_form is True


def test_entrusted_method():
    result = resolve({"governmentProcurement": "否"}, {"purchase_method": "1"})
    assert result.method == "1"
    assert result.name == "委托采购"
    assert result.needs_bid_evaluation_form is False


def test_in_hospital_negotiation_requires_price_type():
    result = resolve({"governmentProcurement": "否"},
                     {"purchase_method": "7", "in_hospital_price_type": 2})
    assert result.method == "7"
    assert result.in_hospital_price_type == 2
    with pytest.raises(ValueError):
        resolve({"governmentProcurement": "否"},
                {"purchase_method": "7", "in_hospital_price_type": 3})


def test_single_source_attachment_required():
    result = resolve({"governmentProcurement": "否"}, {"purchase_method": "4"})
    assert result.uniqueness_attachment
    assert result.needs_bid_evaluation_form is False


def test_gov_method_rejected_for_self_purchase():
    with pytest.raises(ValueError):
        resolve({"governmentProcurement": "否"}, {"purchase_method": "0"})


def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        resolve({"governmentProcurement": "否"}, {"purchase_method": "99"})


def test_chinese_alias():
    result = resolve({"governmentProcurement": "否"}, {"purchase_method": "院内议价"})
    assert result.method == "7"
    assert result.in_hospital_price_type == 1
