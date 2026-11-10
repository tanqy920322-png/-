"""Category default sizes, in millimetres, used when a manual does not give one."""

DEFAULT_SIZES: dict[str, tuple[int, int, int]] = {
    "ceiling": (600, 600, 18),
    "wall": (600, 12, 2400),
    "floor": (800, 800, 10),
    "cabinetry": (1800, 600, 2400),
    "sanitary": (680, 400, 780),
    "entry_door": (960, 50, 2100),
    "kitchen_appliance": (900, 510, 600),
    "lighting": (120, 120, 90),
    "switch_socket": (86, 86, 12),
}


def size_for(part_id: str, width: int | None = None, depth: int | None = None, height: int | None = None) -> tuple[int, int, int]:
    fallback = DEFAULT_SIZES.get(part_id, (600, 600, 600))
    return (
        int(width or fallback[0]),
        int(depth or fallback[1]),
        int(height or fallback[2]),
    )
