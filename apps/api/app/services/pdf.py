from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

FONT_PATH = Path(__file__).resolve().parents[1] / "fonts" / "DroidSansFallbackFull.ttf"


def _yuan(value) -> str:
    number = Decimal(str(value or 0))
    return f"{number:,.2f} 元"


def _area(value) -> str:
    number = Decimal(str(value or 0))
    return f"{number:.2f} ㎡"


def render_quote_pdf(selection: dict) -> bytes:
    if not FONT_PATH.is_file():
        raise RuntimeError(f"缺少中文字体 {FONT_PATH.name}")
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_font("CJK", "", str(FONT_PATH))
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()
    def write(text: str, size: int = 11, height: float = 7) -> None:
        pdf.set_font("CJK", size=size)
        pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")

    write("精装选配报价单", 18, 10)
    write("本单按部位示意单价 × 计价面积计算，供选配演示，不是合同价。", 10, 6)
    pdf.ln(2)

    project = selection["project"]
    unit = selection["unit"]
    style = selection.get("style")
    quote = selection["quote"]
    lines = [
        f"档案编号：{selection['id']}",
        f"客户：{selection['customer_name']}  {selection['customer_phone']}",
        f"项目：{project['name']}（{project['code']}）",
        f"开发商：{project.get('developer') or '—'}",
        f"户型：{unit['name']}  {unit['summary']}  建筑面积 {_area(unit['building_area_m2'])}",
        f"风格：{style['name'] if style else '未选择'}",
        f"状态：{'已提交' if selection['status'] == 'submitted' else '选配中'}",
        f"更新时间：{selection['updated_at']}",
    ]
    for line in lines:
        write(line)
    pdf.ln(2)
    write("部位报价", 12, 8)
    write(quote["area_note"])
    if not quote["lines"]:
        write("尚未选择风格，暂无部位报价。")
    for line in quote["lines"]:
        if line.get("pricing") == "each":
            unit_price = "—" if line["unit_price"] is None else f"{Decimal(str(line['unit_price'])):,.2f} 元"
            qty = Decimal(str(line.get("quantity") or 1))
            basis = f"{unit_price} × {qty:f}".rstrip("0").rstrip(".")
        else:
            unit_price = "—" if line["unit_price"] is None else f"{Decimal(str(line['unit_price'])):,.2f} 元/㎡"
            basis = f"{unit_price} × {_area(line['area_m2'])}"
        tier = {"import": "进口", "domestic": "国产"}.get(line.get("brand_tier") or "", "")
        name = line["scheme_name"] or "未选"
        if tier:
            name = f"{name}（{tier}）"
        write(f"{line['part_name']}  {name}")
        write(f"    {basis} = {_yuan(line['amount'])}", 11, 6)
    pdf.ln(1)
    write(f"部位合计：{_yuan(quote['total'])}", 13, 8)
    pdf.ln(1)
    reference = quote["reference"]
    write("参考口径（不计入合计）")
    write(
        f"硬装 {_yuan(reference['hard_cost_per_m2'])}/㎡ × {_area(reference['building_area_m2'])} = {_yuan(reference['hard_total'])}",
        11,
        6,
    )
    write(
        f"软装 {_yuan(reference['soft_cost_per_m2'])}/㎡ × {_area(reference['building_area_m2'])} = {_yuan(reference['soft_total'])}",
        11,
        6,
    )
    write(reference["note"], 11, 6)
    pdf.ln(2)
    write("分房面积", 12, 8)
    if unit["rooms"]:
        for room in unit["rooms"]:
            mark = "计价" if room["counts_toward_finish"] else "不计入"
            write(f"{room['name']}  {_area(room['area_m2'])}  {mark}", 11, 6)
    else:
        write("未录入分房。", 11, 6)
    pdf.ln(3)
    write("图纸与效果图以后台档案为准。三维预览为选配示意，不是施工 BIM。", 9, 5)
    return bytes(pdf.output())
