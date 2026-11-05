PROCUREMENT_CATEGORIES: list[tuple[str, str]] = [
    ("general", "综合"),
    ("toilet", "马桶"),
    ("sanitary", "洁具"),
    ("appliance", "电器"),
    ("cabinet", "橱柜"),
]

ASSET_KINDS: list[tuple[str, str]] = [
    ("floor_plan", "平面图"),
    ("usage_drawing", "用量图"),
    ("render", "效果图"),
    ("furniture_photo", "家具照片"),
    ("other", "其他"),
]

CATEGORY_LABELS = dict(PROCUREMENT_CATEGORIES)
KIND_LABELS = dict(ASSET_KINDS)

CATEGORY_ALIASES = {
    "general": "general",
    "综合": "general",
    "toilet": "toilet",
    "马桶": "toilet",
    "座便": "toilet",
    "座便器": "toilet",
    "sanitary": "sanitary",
    "洁具": "sanitary",
    "卫浴": "sanitary",
    "appliance": "appliance",
    "电器": "appliance",
    "家电": "appliance",
    "cabinet": "cabinet",
    "橱柜": "cabinet",
}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ASSET_EXTENSIONS = {".dwg", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
TABLE_EXTENSIONS = {".csv", ".xlsx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
