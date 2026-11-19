"""采购需求书/审计报告的本地内容填充（python-docx）。

用途：修复“模板示例数据”问题——把项目/子包/预算/审计信息写入文档，
再通过文件服务上传 + OnlyOffice 回调替换文档当前版本（仅本地/测试环境）。
"""
from __future__ import annotations

import io
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
    """填充审计报告主表：按子包/预算计划写入明细与审计意见。"""
    doc = Document(io.BytesIO(docx_bytes))
    rows: list[list[str]] = []
    seq = 1
    for item in detail.get("subpackages") or []:
        sub = item.get("subpackage") or {}
        department = str(detail.get("department") or "")
        for plan in item.get("reserveProjects") or []:
            quantity = plan.get("quantity") or 1
            unit_price = plan.get("unitPrice") or plan.get("budgetAmount") or ""
            amount = plan.get("budgetAmount") or ""
            rows.append([
                str(seq), str(plan.get("reserveProjectName") or ""), "", "",
                str(plan.get("projectType") or ""), "", "",
                str(unit_price), str(unit_price), str(quantity), str(amount),
                str(unit_price), str(amount), department, "同意", "",
            ])
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
                break
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
