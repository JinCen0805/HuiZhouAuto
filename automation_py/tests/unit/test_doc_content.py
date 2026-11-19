"""内容填充单元测试：需求书/审计报告（不依赖环境）。"""
from __future__ import annotations

import io

from docx import Document

from core.doc_content import fill_audit_report, fill_requirement_document


def _doc_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_fill_requirement_document():
    doc = Document()
    doc.add_paragraph("采购项目名称：模板示例")
    doc.add_paragraph("三、项目概况：模板示例")
    table = doc.add_table(rows=2, cols=9)
    for cell, value in zip(table.rows[0].cells,
                           ["包号", "名称", "单位", "数量", "预算单价（元）", "预算金额（元）",
                            "采购周期", "是否允许进口", "是否专门面向中小微企业"]):
        cell.text = value
    for cell, value in zip(table.rows[1].cells,
                           ["包1", "心电监护仪", "台", "1", "8000", "8000", "壹年", "否", "否"]):
        cell.text = value

    filled = fill_requirement_document(
        _doc_bytes(doc),
        {"requestName": "UI自动化-测试项目", "purchaseContent": "采购内容说明",
         "applicationReason": "申请理由说明"},
        [{"subpackageCode": "FW-YWB-CG20260100-01",
          "subpackageName": "UI自动化-测试项目-子包01", "budgetAmount": 660000}],
    )
    result = Document(io.BytesIO(filled))
    text = "\n".join(p.text for p in result.paragraphs)
    assert "UI自动化-测试项目" in text
    assert "采购内容说明" in text
    rows = result.tables[0].rows
    assert rows[1].cells[0].text == "FW-YWB-CG20260100-01"
    assert "660000" in rows[1].cells[5].text


def test_fill_audit_report_table():
    doc = Document()
    table = doc.add_table(rows=4, cols=16)
    table.rows[0].cells[0].text = "申购项目（货物）审计意见"
    table.rows[1].cells[0].text = ""
    header = ["序号", "货物名称", "企业/联系方式", "品牌", "规格型号/服务类型",
              "配置、技术指标或功能需求", "计价单位", "企业报价（元）", "报审单价（元）",
              "数量", "报审金额（元）", "建议参考单价（元）", "建议参考金额（元）",
              "使用科室", "审核意见", "审计备注"]
    for cell, value in zip(table.rows[2].cells, header):
        cell.text = value

    detail = {
        "department": "医务部",
        "subpackages": [{
            "subpackage": {"subpackageCode": "X-01"},
            "reserveProjects": [{
                "reserveProjectName": "测试货物", "projectType": "货物类",
                "quantity": 2, "unitPrice": 1000, "budgetAmount": 2000,
            }],
        }],
    }
    filled = fill_audit_report(_doc_bytes(doc), detail)
    result = Document(io.BytesIO(filled))
    rows = result.tables[0].rows
    assert len(rows) == 4  # 标题、空行、表头、1 条数据
    data = rows[3]
    assert data.cells[0].text == "1"
    assert data.cells[1].text == "测试货物"
    assert data.cells[9].text == "2"
    assert data.cells[10].text == "2000"
    assert data.cells[13].text == "医务部"
    assert data.cells[14].text == "同意"
