"""Read a homemade manual PDF or image pack into products waiting for a person to confirm."""

import csv
import io
import re
import zipfile
import zlib
from decimal import Decimal, ROUND_HALF_UP

from app.services.sizes import size_for

PARTS = {
    "ceiling",
    "wall",
    "floor",
    "cabinetry",
    "sanitary",
    "entry_door",
    "kitchen_appliance",
    "lighting",
    "switch_socket",
}


class ImportError(Exception):
    pass


def _money(value: str) -> Decimal:
    return Decimal(value.strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pdf_literals(data: bytes) -> str:
    chunks: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = match.group(1).strip(b"\r\n")
        try:
            chunks.append(zlib.decompress(raw))
        except zlib.error:
            chunks.append(raw)
    if not chunks:
        chunks = [data]
    found: list[str] = []
    for chunk in chunks:
        for match in re.finditer(rb"\((?:\\\)|\\.|[^\\)])*\)", chunk):
            raw = match.group(0)[1:-1]
            raw = raw.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            found.append(raw.decode("latin1", errors="ignore"))
    return "\n".join(found)


def _plain(value: str) -> str:
    if "\\u" in value:
        return value.encode("utf-8").decode("unicode_escape")
    return value


def _row_from_parts(parts: list[str], source: str) -> dict:
    if len(parts) < 9:
        raise ImportError("示例行至少要有品类、型号、名称、规格、三维尺寸和两个价格")
    part_id, model, name, spec, width, depth, height, domestic, import_price = parts[:9]
    if part_id not in PARTS:
        raise ImportError(f"不认识的品类：{part_id}")
    w, d, h = size_for(part_id, int(float(width)), int(float(depth)), int(float(height)))
    return {
        "part_id": part_id,
        "model_code": model.strip(),
        "name": _plain(name.strip()) or model.strip(),
        "spec": _plain(spec.strip()),
        "width_mm": w,
        "depth_mm": d,
        "height_mm": h,
        "domestic_price": _money(domestic),
        "import_price": _money(import_price),
        "brand": "手册示例",
        "source": source,
        "example": True,
        "status": "pending",
        "note": "从示例手册或图包读出，待人工确认后才给客户看。",
    }


def parse_manual(filename: str, data: bytes) -> list[dict]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _pdf_literals(data)
        rows = []
        for line in text.splitlines():
            if "SKU|" not in line:
                continue
            payload = line[line.find("SKU|") + 4 :]
            rows.append(_row_from_parts(payload.split("|"), "manual"))
        if not rows:
            raise ImportError("手册里没有找到以 SKU| 开头的型号行")
        return rows
    if lower.endswith(".zip"):
        try:
            package = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ImportError("压缩包打不开") from exc
        manifest = next((name for name in package.namelist() if name.endswith("manifest.csv")), None)
        if manifest is None:
            raise ImportError("图包里需要一份 manifest.csv")
        text = package.read(manifest).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for record in reader:
            image_name = (record.get("image") or "").strip()
            row = _row_from_parts(
                [
                    record.get("part_id", ""),
                    record.get("model_code", ""),
                    record.get("name", ""),
                    record.get("spec", ""),
                    record.get("width_mm", ""),
                    record.get("depth_mm", ""),
                    record.get("height_mm", ""),
                    record.get("domestic_price", ""),
                    record.get("import_price", ""),
                ],
                "pack",
            )
            if image_name and image_name in package.namelist():
                row["note"] = f"图包内有示意图 {image_name}。确认后仍以示例图展示，不是实拍。"
            rows.append(row)
        if not rows:
            raise ImportError("图包清单是空的")
        return rows
    raise ImportError("请上传 PDF 手册或 zip 图包")
