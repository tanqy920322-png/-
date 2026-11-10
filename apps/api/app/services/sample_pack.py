"""Build the homemade manual and image pack used to demonstrate import."""

import csv
import io
import zipfile
from pathlib import Path

from fpdf import FPDF

from app.services.product_art import example_svg

FONT_PATH = Path(__file__).resolve().parents[1] / "fonts" / "DroidSansFallbackFull.ttf"
SAMPLES = Path(__file__).resolve().parents[4] / "packages" / "catalog" / "samples"

ROWS = [
    ("ceiling", "CT-901", "示例平顶漆", "5L 桶", 200, 200, 250, "96", "140"),
    ("wall", "WA-902", "示例墙面漆", "5L 桶", 200, 200, 250, "88", "126"),
    ("floor", "FL-903", "示例地砖", "800 砖", 800, 800, 10, "168", "228"),
    ("cabinetry", "CB-904", "示例衣柜", "主卧", 1800, 600, 2400, "4600", "6200"),
    ("sanitary", "SN-905", "示例花洒", "公卫", 220, 220, 180, "580", "820"),
    ("lighting", "LT-906", "示例射灯", "客厅天花", 90, 90, 80, "90", "128"),
]


def _esc(text: str) -> str:
    return text.encode("unicode_escape").decode("ascii")


def sku_line(row: tuple) -> str:
    part, model, name, spec, width, depth, height, domestic, import_price = row
    return f"SKU|{part}|{model}|{_esc(name)}|{_esc(spec)}|{width}|{depth}|{height}|{domestic}|{import_price}"


def build_manual_pdf() -> bytes:
    pdf = FPDF()
    pdf.compress = False
    pdf.add_font("CJK", "", str(FONT_PATH))
    pdf.add_page()
    pdf.set_font("CJK", size=16)
    pdf.cell(0, 12, "示例产品手册", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CJK", size=11)
    pdf.multi_cell(
        0,
        8,
        "本册是原型自编的型号表，不是任何品牌的商业手册。下面每行是一条可导入的示例型号，含品类、规格和国产、进口价。",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", size=8)
    for row in ROWS:
        pdf.cell(0, 7, sku_line(row), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def build_image_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        text = io.StringIO()
        writer = csv.DictWriter(
            text,
            fieldnames=["part_id", "model_code", "name", "spec", "width_mm", "depth_mm", "height_mm", "domestic_price", "import_price", "image"],
        )
        writer.writeheader()
        for row in ROWS:
            part, model, name, spec, width, depth, height, domestic, import_price = row
            image = f"images/{model}.svg"
            writer.writerow(
                {
                    "part_id": part,
                    "model_code": model,
                    "name": name,
                    "spec": spec,
                    "width_mm": width,
                    "depth_mm": depth,
                    "height_mm": height,
                    "domestic_price": domestic,
                    "import_price": import_price,
                    "image": image,
                }
            )
            package.writestr(image, example_svg(part, name, spec))
        package.writestr("manifest.csv", text.getvalue())
    return buffer.getvalue()


def write_samples() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    (SAMPLES / "示例手册.pdf").write_bytes(build_manual_pdf())
    (SAMPLES / "示例图包.zip").write_bytes(build_image_zip())
