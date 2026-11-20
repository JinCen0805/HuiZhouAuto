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
    doc.add_paragraph("名称：{{项目名称}}")
    doc.add_paragraph("采购单位：{{采购单位}}")
    doc.add_paragraph("三、项目概况：模板示例")
    table = doc.add_table(rows=2, cols=8)
    for cell, value in zip(table.rows[0].cells,
                           ["包号", "名称", "数量", "单位", "预算单价（元）", "预算金额（元）",
                            "项目属性", "备注"]):
        cell.text = value
    # 模板示例数据行：数量/单位/单价保留，只有已确认字段被覆盖
    for cell, value in zip(table.rows[1].cells,
                           ["包1", "心电监护仪", "1", "台", "8000", "8000", "货物类", ""]):
        cell.text = value

    filled = fill_requirement_document(
        _doc_bytes(doc),
        {"requestName": "UI自动化-测试项目", "purchaseContent": "采购内容说明",
         "applicationReason": "申请理由说明", "requestDeptNameSnapshot": "医务部",
         "totalBudgetAmount": 660000},
        [{"subpackageCode": "FW-YWB-CG20260100-01",
          "subpackageName": "UI自动化-测试项目-子包01", "budgetAmount": 660000,
          "reserveProjects": [{"reserveProjectName": "心电监护仪", "projectType": "货物类",
                               "budgetAmount": 660000}]}],
    )
    result = Document(io.BytesIO(filled))
    text = "\n".join(p.text for p in result.paragraphs)
    # 占位符替换
    assert "{{项目名称}}" not in text
    assert "UI自动化-测试项目" in text
    assert "医务部" in text
    assert "采购内容说明" in text
    # 预算表：已确认列被覆盖，未确认列（数量/单位/单价）保留模板默认
    row = result.tables[0].rows[1]
    cols = {c.text: c for c in result.tables[0].rows[0].cells}
    idx_name = list(cols).index("名称")
    assert row.cells[0].text == "FW-YWB-CG20260100-01"  # 包号
    assert "子包01" in row.cells[idx_name].text  # 名称
    assert row.cells[5].text == "660000"  # 预算金额
    assert row.cells[6].text == "货物类"  # 项目属性
    assert row.cells[2].text == "1"  # 数量（模板默认保留）


def test_fill_requirement_engineering_no_table():
    """工程类模板：无预算表、有 {{占位符}}，应替换占位符且不报错。"""
    doc = Document()
    doc.add_paragraph("采购项目内容")
    doc.add_paragraph("名称：{{项目名称}}")
    doc.add_paragraph("采购单位：{{采购单位}}")
    filled = fill_requirement_document(
        _doc_bytes(doc),
        {"requestName": "UI自动化-工程项目", "requestDeptNameSnapshot": "总务处",
         "totalBudgetAmount": 675000},
        [{"subpackageCode": "GC-01", "subpackageName": "修缮工程",
          "budgetAmount": 675000,
          "reserveProjects": [{"reserveProjectName": "医务部-工程", "projectType": "工程类",
                               "budgetAmount": 675000}]}],
    )
    result = Document(io.BytesIO(filled))
    text = "\n".join(p.text for p in result.paragraphs)
    assert "{{项目名称}}" not in text and "{{采购单位}}" not in text
    assert "UI自动化-工程项目" in text
    assert "总务处" in text


def test_fill_audit_report_table():
    doc = Document()
    doc.add_paragraph("×年×月×日")
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
    assert len(rows) == 5  # 标题、空行、表头、1 条数据、1 条合计
    data = rows[3]
    assert data.cells[0].text == "1"
    assert data.cells[1].text == "测试货物"
    assert data.cells[9].text == "2"
    assert data.cells[10].text == "2000"
    assert data.cells[11].text == "1000"  # 建议参考单价=单位价
    assert data.cells[13].text == "医务部"
    assert data.cells[14].text == "同意"
    # 合计行：数量 2 / 报审金额 2000 / 建议参考金额 1000
    total = rows[4]
    assert total.cells[0].text == "合计"
    assert total.cells[9].text == "2"
    assert total.cells[10].text == "2000"
    assert total.cells[12].text == "1000"
    # 落款日期已按关键字填当天
    assert any("20" in (p.text or "") and "年" in (p.text or "") for p in result.paragraphs)


def test_fill_requirement_tech_table():
    """B1：技术参数/技术指标表用真实预留项目名称+说明填充，不编造参数。"""
    doc = Document()
    doc.add_paragraph("名称：{{项目名称}}")
    budget = doc.add_table(rows=2, cols=8)
    for cell, value in zip(budget.rows[0].cells,
                           ["包号", "名称", "数量", "单位", "预算单价（元）", "预算金额（元）",
                            "项目属性", "备注"]):
        cell.text = value
    tech = doc.add_table(rows=4, cols=3)
    for cell, value in zip(tech.rows[0].cells, ["产品技术参数", "产品技术参数", "产品技术参数"]):
        cell.text = value
    for cell, value in zip(tech.rows[1].cells, ["序号", "名称", "技术指标/服务要求描述"]):
        cell.text = value
    for cell, value in zip(tech.rows[2].cells, ["1", "", ""]):
        cell.text = value
    for cell, value in zip(tech.rows[3].cells, ["2", "", ""]):
        cell.text = value

    filled = fill_requirement_document(
        _doc_bytes(doc),
        {"requestName": "UI自动化-技术参数项目", "requestDeptNameSnapshot": "医务部",
         "totalBudgetAmount": 200000},
        [{"subpackageCode": "FW-01", "subpackageName": "宣传视频制作", "budgetAmount": 200000,
          "reserveProjects": [
              {"reserveProjectName": "医院宣传视频", "projectType": "服务类",
               "preparationBasis": "重点专科需向患者说明服务范围，现有内容过期",
               "quantity": 2, "unit": "条"},
              {"reserveProjectName": "第二项服务", "projectType": "服务类",
               "preparationBasis": "用于覆盖新增服务场景。"},
          ]}],
    )
    result = Document(io.BytesIO(filled))
    tech_tb = result.tables[1]
    # 表头 r0=标题(合并)、r1=表头、r2/r3=数据行
    assert tech_tb.rows[2].cells[1].text == "医院宣传视频"  # 名称列
    assert "重点专科需向患者说明" in tech_tb.rows[2].cells[2].text  # 描述列
    assert tech_tb.rows[3].cells[1].text == "第二项服务"
    assert "新增服务场景" in tech_tb.rows[3].cells[2].text
