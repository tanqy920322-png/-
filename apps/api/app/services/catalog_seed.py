"""Preset example SKUs. Brand names here are invented for the prototype."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogProduct
from app.services.sizes import DEFAULT_SIZES

BRANDS = ("素白示例", "北境示例", "澄木示例", "青澜示例")
NOUNS = {
    "ceiling": "平顶板",
    "wall": "墙面板",
    "floor": "地面砖",
    "cabinetry": "柜体",
    "sanitary": "洁具",
    "entry_door": "入户门",
    "kitchen_appliance": "厨电",
    "lighting": "灯具",
    "switch_socket": "开关插座",
}
PER_PART = 36


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def seed_example_products(db: Session) -> int:
    count = 0
    for part_id, noun in NOUNS.items():
        width, depth, height = DEFAULT_SIZES[part_id]
        for index in range(1, PER_PART + 1):
            product_id = f"sku-{part_id}-{index:02d}"
            brand = BRANDS[(index - 1) % len(BRANDS)]
            domestic = 80 + index * (12 if part_id in {"lighting", "switch_socket"} else 90)
            if part_id == "cabinetry":
                domestic = 1600 + index * 180
            elif part_id == "entry_door":
                domestic = 1800 + index * 120
            elif part_id == "kitchen_appliance":
                domestic = 900 + index * 140
            fields = {
                "part_id": part_id,
                "brand": brand,
                "model_code": f"{part_id[:2].upper()}-{index:03d}",
                "name": f"{brand}{noun} {index:02d}",
                "spec": f"示例规格 {width + index * 5}×{depth}×{height + index * 3} mm",
                "width_mm": width + (index % 5) * 20,
                "depth_mm": depth,
                "height_mm": height + (index % 4) * 15,
                "domestic_price": _money(domestic),
                "import_price": _money(domestic * 1.38),
                "status": "confirmed",
                "example": True,
                "source": "preset",
                "note": "自制示例 SKU，不是品牌实拍或官网资料。",
            }
            row = db.get(CatalogProduct, product_id)
            if row is None:
                db.add(CatalogProduct(id=product_id, **fields))
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            count += 1
    db.flush()
    return count


def confirmed_count(db: Session) -> int:
    return len(db.scalars(select(CatalogProduct).where(CatalogProduct.status == "confirmed")).all())
