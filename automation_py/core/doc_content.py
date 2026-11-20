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
    """清空表头行之后的数据行，再按 rows 填充（审计明细表用）。"""
    if len(table.rows) <= header_index:
        return
    # 保留表头及其上（标题/合并行），删除表头之后的数据行
    for row in list(table.rows)[header_index + 1:]:
        table._tbl.remove(row._tr)
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = str(value)


def _replace_placeholders(doc: Document, mapping: dict[str, str]) -> None:
    """批量替换段落/表格单元格里的 {{占位符}}（工程类/模板变量通用）。"""
    def _replacer(text: str) -> str:
        if not text:
            return text

        def _one(m) -> str:
            key = m.group(1).strip()
            return mapping.get(key, m.group(0))
        return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", _one, text)

    for para in doc.paragraphs:
        para.text = _replacer(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell.text = _replacer(cell.text)


def _fill_prose_fields(doc: Document, mapping: dict[str, str]) -> None:
    """按行首关键字填充条款式字段（名称/采购单位/总金额），value 空则跳过。"""
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        for prefix, key in (("名称：", "名称"), ("采购单位：", "采购单位"),
                            ("总金额（元）:", "总金额"), ("总金额（元）：", "总金额"),
                            ("预算金额（元）:", "总金额"), ("预算金额（元）：", "总金额")):
            if text.startswith(prefix) and mapping.get(key):
                para.text = prefix + str(mapping[key])
                break


def _header_columns(header_row_cells) -> list[str]:
    return [c.text.strip() for c in header_row_cells]


def _find_budget_table(doc: Document) -> tuple | None:
    """按关键字定位预算表（表头含“预算金额”，且带“预算单价/单价”或“包号/名称”）。"""
    for table in doc.tables:
        for index, row in enumerate(table.rows[:3]):
            text = "|".join(c.text for c in row.cells)
            if "预算金额" in text and ("预算单价" in text or "包号" in text or "分项预算" in text):
                return table, index
    return None


def _fill_budget_table(doc: Document, subpackages: list[dict]) -> None:
    """表头驱动填充预算表：目标表头含“预算金额”关键字。

    只覆盖已确认字段（包号/名称/预算金额/项目属性），数量/单位/单价无真实数据时
    保留模板默认值，避免制造虚假采购量。支持货物/服务/工程等多模板表头差异。
    """
    found = _find_budget_table(doc)
    if not found:
        return
    table, header_index = found
    headers = _header_columns(table.rows[header_index].cells)

    col_by_keyword: dict[str, int] = {}
    for i, h in enumerate(headers):
        if "包号" in h:
            col_by_keyword["包号"] = i
        elif "名称" in h or "标的" in h or "品目名" in h:
            col_by_keyword.setdefault("名称", i)
        elif "预算金额" in h or "分项预算总价" in h or ("总价" in h and "预算" in h):
            col_by_keyword.setdefault("预算金额", i)
        elif "项目属性" in h or "所属行业" in h:
            col_by_keyword.setdefault("项目属性", i)

    rows = list(table.rows[header_index + 1:])
    for sub_index, sub in enumerate(subpackages or []):
        rp_list = sub.get("reserveProjects") or []
        first_rp = rp_list[0] if rp_list else {}
        amount = sub.get("budgetAmount")
        if amount in (None, "") and first_rp:
            amount = first_rp.get("budgetAmount")
        values = {
            "包号": sub.get("subpackageCode") or f"包{sub_index + 1}",
            "名称": sub.get("subpackageName") or first_rp.get("reserveProjectName") or "",
            "预算金额": _num(amount),
            "项目属性": first_rp.get("projectType") or sub.get("projectType") or "",
        }
        row = rows[sub_index] if sub_index < len(rows) else rows[-1]
        for key, col in col_by_keyword.items():
            cell = row.cells[col]
            if values.get(key):
                cell.text = str(values[key])


def _iter_item_rows(subpackages: list[dict]) -> list[dict]:
    """展开子包下的预留项目（技术参数/配置清单填充的数据源）。"""
    items: list[dict] = []
    for sub in subpackages or []:
        for rp in sub.get("reserveProjects") or []:
            items.append({
                "name": rp.get("reserveProjectName") or "",
                "desc": rp.get("preparationBasis") or rp.get("spec") or rp.get("remark") or "",
                "unit": rp.get("unit") or "",
                "quantity": _num(rp.get("quantity"), int_digits=True),
            })
    return items


def _fill_tech_table(doc: Document, subpackages: list[dict]) -> None:
    """填充技术参数/技术指标表：表头含“技术指标/技术参数/技术要求”。

    名称列填预留项目名；描述列填该项目的 preparationBasis 真实说明（无则留空）。
    序号列保留模板序号。数据不足时其余行留空，不编造技术参数。
    """
    items = _iter_item_rows(subpackages)
    if not items:
        return
    for table in doc.tables:
        is_tech = any(
            "技术指标" in "|".join(c.text for c in row.cells) or "技术参数" in "|".join(c.text for c in row.cells)
            or "技术要求" in "|".join(c.text for c in row.cells)
            for row in table.rows[:3]
        )
        if not is_tech:
            continue
        # 在同一表内再找含“名称”的表头行（R0 可能是合并标题“产品技术参数”）
        hdr_index = None
        headers: list[str] = []
        for index, row in enumerate(table.rows[:3]):
            cells = [c.text.strip() for c in row.cells]
            if "名称" in "|".join(cells):
                hdr_index = index
                headers = cells
                break
        if hdr_index is None:
            return  # 无名称列，无法安全填充
        name_col = next((i for i, h in enumerate(headers) if "名称" in h), None)
        desc_col = next((i for i, h in enumerate(headers)
                         if ("描述" in h or "要求" in h or "参数" in h)
                         and i != name_col), None)
        data_start = hdr_index + 1
        for offset, item in enumerate(items[: max(0, len(table.rows) - data_start)]):
            cells = table.rows[data_start + offset].cells
            if len(cells) > name_col:
                cells[name_col].text = item["name"]
            if desc_col is not None and len(cells) > desc_col and item["desc"]:
                cells[desc_col].text = item["desc"]
        return


def fill_requirement_document(docx_bytes: bytes, request: dict,
                              subpackages: list[dict]) -> bytes:
    """填充采购需求书（模板无关）：占位符 + 条款字段 + 预算表。

    覆盖 4 类模板：议价/工程（无表+占位符）、政采货物/服务（多表，预算表按关键字定位）。
    """
    doc = Document(io.BytesIO(docx_bytes))
    request_name = str(request.get("requestName") or "").strip()
    dept = str(request.get("requestDeptNameSnapshot")
               or request.get("organizationName") or "").strip()
    content = str(request.get("purchaseContent") or "").strip()
    reason = str(request.get("applicationReason") or "").strip()

    mapping = {
        "项目名称": request_name or "",
        "采购单位": dept or "",
        "总金额": _num(request.get("totalBudgetAmount")),
        "采购预算": _num(sum(float(x or 0) for x in [request.get("totalBudgetAmount")])),
    }
    _replace_placeholders(doc, mapping)
    _fill_prose_fields(doc, mapping | {"名称": request_name or "", "采购单位": dept or "",
                                        "总金额": _num(request.get("totalBudgetAmount"))})

    overview = "三、项目概况：" + " ".join(x for x in (content, reason) if x)
    _replace_paragraph(doc, "三、项目概况", overview)
    if request_name:
        _replace_paragraph(doc, "采购项目名称", f"采购项目名称：{request_name}")

    _fill_budget_table(doc, subpackages or [])
    _fill_tech_table(doc, subpackages or [])
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
