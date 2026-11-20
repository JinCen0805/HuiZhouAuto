"""采购需求书/审计报告的本地内容填充（python-docx）。

用途：修复“模板示例数据”问题——把项目/子包/预算/审计信息写入文档，
再通过文件服务上传 + OnlyOffice 回调替换文档当前版本（仅本地/测试环境）。
"""
from __future__ import annotations

import io
import re
from typing import Any

from docx import Document


def _replace_paragraph(doc: Document, prefix: str, new_text: str) -> bool:
    for para in doc.paragraphs:
        if (para.text or "").strip().startswith(prefix):
            para.text = new_text
            return True
    return False


def _fill_table_rows(table, rows: list[list[str]], header_index: int = 0) -> None:
    """清空表头行之后的数据行，再按 rows 填充。"""
    if len(table.rows) <= header_index:
        return
    for row in list(table.rows)[header_index + 1:]:
        table._tbl.remove(row._tr)
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = str(value)


def fill_requirement_document(docx_bytes: bytes, request: dict,
                              subpackages: list[dict]) -> bytes:
    """填充采购需求书：项目名称/概况/采购预算表。"""
    doc = Document(io.BytesIO(docx_bytes))
    request_name = str(request.get("requestName") or "").strip()
    content = str(request.get("purchaseContent") or "").strip()
    reason = str(request.get("applicationReason") or "").strip()

    if request_name:
        _replace_paragraph(doc, "采购项目名称", f"采购项目名称：{request_name}")
    overview = "三、项目概况：" + " ".join(x for x in (content, reason) if x)
    _replace_paragraph(doc, "三、项目概况", overview)

    rows: list[list[str]] = []
    for index, sub in enumerate(subpackages or [], start=1):
        code = str(sub.get("subpackageCode") or f"包{index}")
        name = str(sub.get("subpackageName") or "")
        amount = sub.get("budgetAmount")
        try:
            amount_text = f"{float(amount):.2f}" if amount not in (None, "") else ""
        except Exception:
            amount_text = str(amount or "")
        rows.append([code, name, "批", "1", amount_text, amount_text, "按合同", "否", "否"])

    if rows and doc.tables:
        _fill_table_rows(doc.tables[0], rows)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def fill_audit_report(docx_bytes: bytes, detail: dict) -> bytes:
    """填充审计报告主表：按子包/预算计划写入明细、合计与落款日期。

    明细列沿用 16 列审计表头；合计行（数量/报审金额/建议参考金额）由已确认的
    reserveProjects 字段求和得出；落款日期按关键字定位段落（不存在则忽略）。
    """
    doc = Document(io.BytesIO(docx_bytes))
    rows: list[list[str]] = []
    numeric: dict[str, float] = {"quantity": 0.0, "amount": 0.0, "ref_amount": 0.0}
    seq = 1
    for item in detail.get("subpackages") or []:
        department = str(detail.get("department") or "")
        for plan in item.get("reserveProjects") or []:
            quantity = plan.get("quantity") or 1
            unit_price = plan.get("unitPrice") or plan.get("budgetAmount") or ""
            try:
                amount = float(plan.get("budgetAmount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            try:
                ref_price = float(unit_price)
            except (TypeError, ValueError):
                ref_price = 0.0
            rows.append([
                str(seq), str(plan.get("reserveProjectName") or ""), "", "",
                str(plan.get("projectType") or ""), "", "",
                _num(unit_price), _num(unit_price), str(quantity), _num(amount),
                _num(ref_price if ref_price else amount), _num(amount), department, "同意", "",
            ])
            numeric["quantity"] += float(quantity or 0)
            numeric["amount"] += amount
            numeric["ref_amount"] += ref_price if ref_price else amount
            seq += 1

    if rows:
        for table in doc.tables:
            header_index = None
            for index, row in enumerate(table.rows):
                row_text = " ".join(c.text for c in row.cells)
                if "序号" in row_text and "报审金额" in row_text:
                    header_index = index
                    break
            if header_index is not None:
                _fill_table_rows(table, rows, header_index)
                # 追加合计行（金额列与明细行保持一致：索引 9 数量 / 10 报审金额 / 12 建议参考金额 / 13 使用科室）
                total_row = [""] * 16
                total_row[0] = "合计"
                total_row[9] = _num(numeric["quantity"], int_digits=True)
                total_row[10] = _num(numeric["amount"])
                total_row[12] = _num(numeric["ref_amount"])
                _append_row(table, total_row)
                break

    _fill_audit_date(doc, detail)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _num(value, int_digits: bool = False) -> str:
    """金额/数量格式化：整数直写，小数保留两位，去掉无意义 .00 后缀的整数形态。"""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "" if value in (None, "") else str(value)
    if int_digits or f == int(f):
        return str(int(f))
    return f"{f:.2f}"


def _append_row(table, values: list[str]) -> None:
    """向表格追加一行（cell 数与 values 对齐；values 短则补空）。"""
    row = table.add_row()
    for idx, cell in enumerate(row.cells):
        cell.text = str(values[idx]) if idx < len(values) else ""


def _fill_audit_date(doc: Document, detail: dict) -> None:
    """按关键字定位落款日期段落填写当天日期（不存在则忽略，不猜测模板结构）。"""
    from datetime import date

    today = date.today().strftime("%Y年%m月%d日")
    keywords = ("年", "月", "日", "日期")
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        # 落款行：短段落、包含“年/月/日”或“日期”、可填空位
        if any(k in text for k in keywords) and len(text) < 30 \
                and not re.search(r"\d{2,4}\s*年", text):
            para.text = today
            return
