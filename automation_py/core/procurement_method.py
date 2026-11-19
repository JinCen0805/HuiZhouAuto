"""采购方式选项：支持用户选择自主采购的采购方式，并按规则补齐必填参数。

自主采购可选（与后端校验一致）：
    1 委托采购
    2 比选采购（默认）
    3 竞争谈判采购
    4 唯一来源谈判采购（需上传唯一性论证会议纪要附件）
    7 议（比）价采购（需选择议比价方式：1 院内议价 / 2 院内比价）

注：零星采购(5)、紧急采购(6) 后端要求走各自专门页面，不在本流程支持；
政府采购方式需要政府采购买卖流程，当前流程默认自治采购，仅预留映射。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from core.config import PACKAGE_ROOT

SELF_METHODS = {
    "1": {"name": "委托采购", "needs_bid_evaluation_form": False,
          "needs_in_hospital_price_type": False, "needs_uniqueness_attachment": False},
    "2": {"name": "比选采购", "needs_bid_evaluation_form": True,
          "needs_in_hospital_price_type": False, "needs_uniqueness_attachment": False},
    "3": {"name": "竞争谈判采购", "needs_bid_evaluation_form": True,
          "needs_in_hospital_price_type": False, "needs_uniqueness_attachment": False},
    "4": {"name": "唯一来源谈判采购", "needs_bid_evaluation_form": False,
          "needs_in_hospital_price_type": False, "needs_uniqueness_attachment": True},
    "7": {"name": "议（比）价采购", "needs_bid_evaluation_form": False,
          "needs_in_hospital_price_type": True, "needs_uniqueness_attachment": False},
}

GOV_METHODS = {
    "0": {"name": "公开招标", "needs_bid_evaluation_form": True},
    "10": {"name": "邀请招标", "needs_bid_evaluation_form": True},
    "11": {"name": "竞争性谈判", "needs_bid_evaluation_form": False},
    "12": {"name": "竞争性磋商", "needs_bid_evaluation_form": True},
    "13": {"name": "单一来源采购", "needs_bid_evaluation_form": False},
    "14": {"name": "询价", "needs_bid_evaluation_form": False},
}

ALIASES = {
    "委托采购": "1",
    "比选采购": "2",
    "竞争谈判采购": "3",
    "唯一来源谈判采购": "4",
    "唯一性来源谈判采购": "4",
    "院内议价": "7",
    "院内比价": "7",
    "议（比）价采购": "7",
    "议比价": "7",
    "院内议（比）价": "7",
}

UNIQUENESS_ATTACHMENT_NAME = "唯一性论证会议纪要.pdf"


@dataclass
class MethodSelection:
    category: str
    method: str
    name: str
    bid_evaluation_form: str
    in_hospital_price_type: int | None
    uniqueness_attachment: str | None
    governance: bool

    @property
    def needs_bid_evaluation_form(self) -> bool:
        table = GOV_METHODS if self.governance else SELF_METHODS
        return bool(table[self.method].get("needs_bid_evaluation_form"))


def _parse_code(raw: str) -> str:
    value = str(raw or "").strip()
    if value in ALIASES:
        return ALIASES[value]
    if value in SELF_METHODS or value in GOV_METHODS:
        return value
    options = [f"{k} {v['name']}" for k, v in SELF_METHODS.items()]
    raise ValueError(f"不支持的采购方式：{raw!r}；自主采购可选：{options}")


def resolve(record: dict, ctx: dict | None = None) -> MethodSelection:
    ctx = ctx or {}
    government = str(record.get("governmentProcurement")) in ("是", "1", "true", "True")
    category = str(ctx.get("purchase_category")
                   or os.environ.get("HP_PURCHASE_CATEGORY")
                   or ("0" if government else "1")).strip()
    if category not in ("0", "1"):
        raise ValueError(f"采购类别只能是 0（政府采购）或 1（自主采购）：{category}")

    raw_method = (ctx.get("purchase_method") or os.environ.get("HP_PURCHASE_METHOD")
                  or "2")
    method = _parse_code(raw_method)
    table = GOV_METHODS if category == "0" else SELF_METHODS
    if method not in table:
        raise ValueError(f"采购类别 {category} 不支持采购方式 {method}（请使用：{list(table)}）")

    name = table[method]["name"]
    needs_price = bool(table[method].get("needs_in_hospital_price_type"))
    price_type = ctx.get("in_hospital_price_type") or os.environ.get("HP_IN_HOSPITAL_PRICE_TYPE")
    if needs_price:
        price_type = int(price_type or 1)
        if price_type not in (1, 2):
            raise ValueError("议比价方式只能是 1（院内议价）或 2（院内比价）")
    else:
        price_type = None

    uniqueness = None
    if table[method].get("needs_uniqueness_attachment"):
        uniqueness = (ctx.get("uniqueness_attachment")
                      or os.environ.get("HP_UNIQUENESS_ATTACHMENT")
                      or str(PACKAGE_ROOT / "fixtures" / "files" / "wjc测试文件.pdf"))

    bid_form = str(ctx.get("bid_evaluation_form")
                   or os.environ.get("HP_BID_EVALUATION_FORM")
                   or "0")
    return MethodSelection(
        category=category,
        method=method,
        name=name,
        bid_evaluation_form=bid_form,
        in_hospital_price_type=price_type,
        uniqueness_attachment=uniqueness,
        governance=category == "0",
    )
