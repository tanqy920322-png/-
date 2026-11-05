import io

from openpyxl import Workbook

from app.services.importer import parse_price_table


def test_gb18030_csv_and_category_default():
    raw = "名称,单价,单位\n花洒,890,套\n".encode("gb18030")
    rows = parse_price_table("prices.csv", raw, "sanitary")
    assert rows[0]["name"] == "花洒"
    assert rows[0]["unit_price"] == __import__("decimal").Decimal("890.00")
    assert rows[0]["category"] == "sanitary"


def test_xlsx_row_category_overrides_table_category():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["品类", "名称", "单价", "SKU"])
    sheet.append(["橱柜", "地柜延米", 1800, "CAB-001"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    rows = parse_price_table("cabinet.xlsx", buffer.getvalue(), "general")
    assert rows[0]["category"] == "cabinet"
    assert rows[0]["sku_code"] == "CAB-001"
    assert rows[0]["unit_price"] == __import__("decimal").Decimal("1800.00")
