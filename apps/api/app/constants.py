PROCUREMENT_CATEGORIES: list[tuple[str, str]] = [
    ("ceiling", "天花"),
    ("wall", "墙面"),
    ("floor", "地面"),
    ("cabinetry", "全屋定制"),
    ("sanitary", "洁具"),
    ("entry_door", "入户门"),
    ("kitchen_appliance", "厨房电器"),
    ("lighting", "灯具"),
    ("switch_socket", "开关插座"),
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
    "ceiling": "ceiling",
    "天花": "ceiling",
    "wall": "wall",
    "墙面": "wall",
    "floor": "floor",
    "地面": "floor",
    "cabinetry": "cabinetry",
    "全屋定制": "cabinetry",
    "柜体": "cabinetry",
    "橱柜": "cabinetry",
    "cabinet": "cabinetry",
    "sanitary": "sanitary",
    "洁具": "sanitary",
    "卫浴": "sanitary",
    "马桶": "sanitary",
    "座便": "sanitary",
    "座便器": "sanitary",
    "toilet": "sanitary",
    "entry_door": "entry_door",
    "入户门": "entry_door",
    "kitchen_appliance": "kitchen_appliance",
    "厨房电器": "kitchen_appliance",
    "电器": "kitchen_appliance",
    "家电": "kitchen_appliance",
    "appliance": "kitchen_appliance",
    "lighting": "lighting",
    "灯具": "lighting",
    "switch_socket": "switch_socket",
    "开关插座": "switch_socket",
}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ASSET_EXTENSIONS = {".dwg", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
TABLE_EXTENSIONS = {".csv", ".xlsx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
