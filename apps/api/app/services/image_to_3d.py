"""Local photo stand-in, plus a reserved paid image-to-3D hook that nothing calls."""

from app.services.sizes import DEFAULT_SIZES, size_for

EFFECT_LABEL = "仅用于效果展示，不列入采购"
EFFECT_PROMISE = "外形接近、能看出来是同一类、同一款式方向"
EFFECT_LIMITS = [
    "用上传的照片贴在这一类的常用外形上，不重建细部。",
    "单张照片可能看不清背面和细部。",
    "这不是付费图生三维的质量。",
]

# Placeable categories. Sofa is a soft furnishing, not one of the nine priced parts.
PLACEABLE_PARTS = (
    "sanitary",
    "sofa",
    "switch_socket",
    "cabinetry",
    "lighting",
    "entry_door",
    "kitchen_appliance",
)

PART_NAMES = {
    "sanitary": "洁具",
    "sofa": "软装沙发",
    "switch_socket": "开关插座",
    "cabinetry": "全屋定制",
    "lighting": "灯具",
    "entry_door": "入户门",
    "kitchen_appliance": "厨房电器",
    "ceiling": "天花",
    "wall": "墙面",
    "floor": "地面",
}

# width, depth, height in millimetres. Slot-specific when the category default is a poor fit.
SLOT_MM: dict[tuple[str, str], tuple[int, int, int]] = {
    ("sanitary", "马桶"): (410, 680, 400),
    ("sanitary", "花洒"): (180, 180, 2100),
    ("sanitary", "面盆"): (700, 480, 180),
    ("sanitary", "菜盆"): (760, 460, 200),
    ("sofa", "沙发"): (2200, 900, 780),
    ("switch_socket", "开关插座"): (86, 86, 12),
    ("switch_socket", "开关"): (86, 86, 12),
    ("cabinetry", "柜体"): (1800, 600, 2400),
    ("lighting", "灯具"): (320, 320, 280),
    ("entry_door", "入户门"): (960, 80, 2100),
    ("kitchen_appliance", "厨电"): (900, 510, 600),
    ("kitchen_appliance", "烟机"): (900, 500, 420),
}


def paid_image_to_3d_hook(
    photos: list[bytes],
    category: str,
    size_mm: tuple[int, int, int],
) -> dict:
    """Reserved for a future paid image-to-3D provider.

    Nothing in the app calls this. It does not read API keys and does not open a network connection.
    """
    del photos, category, size_mm
    raise RuntimeError("付费图生三维未授权，不会发出请求。")


def default_size_mm(part_id: str, slot_label: str) -> tuple[int, int, int]:
    label = (slot_label or "").strip()
    exact = SLOT_MM.get((part_id, label))
    if exact:
        return exact
    for (part, slot), size in SLOT_MM.items():
        if part == part_id and slot and slot in label:
            return size
    if part_id in DEFAULT_SIZES:
        return size_for(part_id)
    if part_id == "sofa":
        return SLOT_MM[("sofa", "沙发")]
    return (600, 600, 600)


def stand_in_notice(*, photo_count: int, demo: bool) -> dict:
    limits = list(EFFECT_LIMITS)
    if photo_count < 2:
        limits.append("只上传了一张时，背面仍是这类的常用外形，不是照片。")
    if demo:
        limits.append("当前这张是演示用的示意图，不是客户实拍，也不是品牌照片。")
    return {
        "method": "photo_on_typical_mesh",
        "paid_api_called": False,
        "priced": False,
        "orderable": False,
        "label": EFFECT_LABEL,
        "promise": EFFECT_PROMISE,
        "limits": limits,
    }
