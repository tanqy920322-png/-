"""Drawn example pictures. These are not photographs of commercial products."""

PART_COLORS = {
    "ceiling": "#E7D3B0",
    "wall": "#F3E6D4",
    "floor": "#C4A574",
    "cabinetry": "#C9A679",
    "sanitary": "#D5E3EA",
    "entry_door": "#8C6239",
    "kitchen_appliance": "#C8C9CB",
    "lighting": "#F0D7A4",
    "switch_socket": "#E4E4E6",
}


def example_svg(part_id: str, title: str, subtitle: str) -> bytes:
    color = PART_COLORS.get(part_id, "#E7D3B0")
    safe_title = (
        title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:18]
    )
    safe_sub = subtitle.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:28]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240">
  <rect width="320" height="240" fill="#f7f1e8"/>
  <rect x="28" y="28" width="264" height="128" rx="16" fill="{color}"/>
  <rect x="48" y="48" width="92" height="88" rx="8" fill="#fffaf3" opacity="0.85"/>
  <rect x="156" y="48" width="112" height="36" rx="8" fill="#fffaf3" opacity="0.7"/>
  <rect x="156" y="96" width="80" height="40" rx="8" fill="#2c2924" opacity="0.18"/>
  <text x="28" y="184" font-family="sans-serif" font-size="16" fill="#2c2924">{safe_title}</text>
  <text x="28" y="208" font-family="sans-serif" font-size="12" fill="#6f675d">{safe_sub}</text>
  <text x="250" y="208" font-family="sans-serif" font-size="12" fill="#8b6438">示例</text>
</svg>"""
    return svg.encode("utf-8")
