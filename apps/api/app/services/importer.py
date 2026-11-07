import csv
import io
import re
from decimal import Decimal, ROUND_HALF_UP

from openpyxl import load_workbook

from app.constants import CATEGORY_ALIASES

HEADER_MAP = {
    "品类": "category",
    "分类": "category",
    "category": "category",
    "sku": "sku_code",
    "sku编码": "sku_code",
    "编码": "sku_code",
    "物料编码": "sku_code",
    "名称": "name",
    "品名": "name",
    "物料名称": "name",
    "name": "name",
    "规格": "spec",
    "型号": "spec",
    "规格型号": "spec",
    "spec": "spec",
    "品牌": "brand",
    "brand": "brand",
    "单位": "unit",
    "unit": "unit",
    "单价": "unit_price",
    "价格": "unit_price",
    "含税单价": "unit_price",
    "unit_price": "unit_price",
    "price": "unit_price",
    "备注": "remark",
    "remark": "remark",
}


class TableImportError(ValueError):
    pass


def _header_key(cell) -> str:
    text = str(cell or "").strip().replace(" ", "").replace("\n", "")
    if text in HEADER_MAP:
        return HEADER_MAP[text]
    return HEADER_MAP.get(text.lower(), "")


def _category(value, default_category: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default_category
    mapped = CATEGORY_ALIASES.get(text) or CATEGORY_ALIASES.get(text.lower())
    if not mapped:
        raise TableImportError(f"无法识别品类：{text}")
    return mapped


def _price(value) -> Decimal:
    if value is None or value == "":
        raise TableImportError("缺少单价")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, (int, float)):
        number = Decimal(str(value))
    else:
        text = str(value).strip()
        text = text.replace(",", "").replace("，", "").replace("￥", "").replace("¥", "").replace("元", "")
        text = re.sub(r"\s+", "", text)
        if not text:
            raise TableImportError("缺少单价")
        try:
            number = Decimal(text)
        except Exception as exc:
            raise TableImportError(f"单价无法解析：{value}") from exc
    if number < 0:
        raise TableImportError("单价不能为负")
    return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rows_from_csv(data: bytes) -> list[list]:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise TableImportError("无法识别表格编码，请使用 UTF-8 或 GB18030 的 CSV")
    return [list(row) for row in csv.reader(io.StringIO(text))]


def _rows_from_xlsx(data: bytes) -> list[list]:
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise TableImportError("Excel 文件无法读取") from exc
    sheet = workbook.active
    rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    workbook.close()
    return rows


def parse_price_table(filename: str, data: bytes, default_category: str) -> list[dict]:
    if default_category not in CATEGORY_ALIASES.values():
        raise TableImportError("请选择价表品类")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "csv":
        rows = _rows_from_csv(data)
    elif suffix == "xlsx":
        rows = _rows_from_xlsx(data)
    else:
        raise TableImportError("仅支持 CSV 或 XLSX")
    header_index = None
    mapped_headers: list[str] = []
    for index, row in enumerate(rows[:8]):
        mapped = [_header_key(cell) for cell in row]
        if "name" in mapped and "unit_price" in mapped:
            header_index = index
            mapped_headers = mapped
            break
    if header_index is None:
        raise TableImportError("表头需要包含「名称」和「单价」")
    items: list[dict] = []
    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        record = {key: "" for key in ("category", "sku_code", "name", "spec", "brand", "unit", "remark")}
        price = None
        for key, cell in zip(mapped_headers, row):
            if not key:
                continue
            if key == "unit_price":
                price = cell
            else:
                record[key] = "" if cell is None else str(cell).strip()
        if not record["name"]:
            continue
        try:
            unit_price = _price(price)
            category = _category(record["category"], default_category)
        except TableImportError as exc:
            raise TableImportError(f"第 {offset} 行：{exc}") from exc
        items.append(
            {
                "category": category,
                "sku_code": record["sku_code"],
                "name": record["name"],
                "spec": record["spec"],
                "brand": record["brand"],
                "unit": record["unit"],
                "unit_price": unit_price,
                "remark": record["remark"],
            }
        )
        if len(items) > 5000:
            raise TableImportError("单次最多导入 5000 行")
    if not items:
        raise TableImportError("没有可导入的数据行")
    return items
