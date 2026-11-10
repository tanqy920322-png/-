"""Large example drawings. The product fills the frame. These are not photographs."""

PART_COLORS = {
    "ceiling": "#F4E7CF",
    "wall": "#F7F1E8",
    "floor": "#E7D3B0",
    "cabinetry": "#C4A574",
    "sanitary": "#F4F7F8",
    "entry_door": "#8C6239",
    "kitchen_appliance": "#E6E7E8",
    "lighting": "#F8E7C4",
    "switch_socket": "#F7F4EE",
}


def _esc(value: str, limit: int) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:limit]
    )


def _kind(part_id: str, title: str) -> str:
    text = f"{part_id} {title}"
    if any(word in text for word in ("马桶", "坐便")):
        return "toilet"
    if "花洒" in text:
        return "shower"
    if any(word in text for word in ("龙头", "面盆", "菜盆")):
        return "basin"
    if any(word in text for word in ("射灯", "筒灯", "灯具", "主灯", "吊灯")):
        return "light"
    if "灯槽" in text:
        return "cove"
    if any(word in text for word in ("衣柜", "书柜", "电视柜", "餐边", "床头", "柜")):
        return "cabinet"
    if "烟机" in text:
        return "hood"
    if any(word in text for word in ("炉灶", "灶")):
        return "hob"
    if any(word in text for word in ("蒸烤", "洗碗", "厨电")):
        return "oven"
    if "过门" in text:
        return "tile"
    if any(word in text for word in ("入户门", "门扇", "装甲门")) or (part_id == "entry_door" and "门" in text):
        return "door"
    if any(word in text for word in ("开关", "插座")):
        return "switch"
    if part_id == "floor" or any(word in text for word in ("地砖", "地面", "波打", "过门")):
        return "tile"
    if part_id == "wall" or "墙" in text:
        return "wall"
    if part_id == "ceiling" or "天花" in text or "平顶" in text:
        return "ceiling"
    if part_id == "sanitary":
        return "toilet"
    if part_id == "lighting":
        return "light"
    if part_id == "cabinetry":
        return "cabinet"
    if part_id == "entry_door":
        return "door"
    if part_id == "kitchen_appliance":
        return "hood"
    if part_id == "switch_socket":
        return "switch"
    return "tile"


def _drawing(kind: str) -> str:
    if kind == "toilet":
        return """
        <rect x="150" y="36" width="340" height="150" rx="18" fill="#f7f7f5" stroke="#c5c8ca" stroke-width="6"/>
        <rect x="190" y="70" width="260" height="28" rx="8" fill="#e4e7e8"/>
        <path d="M120 186 h400 c30 0 70 28 70 90 v70 h-540 v-70 c0-62 40-90 70-90z" fill="#fbfbfa" stroke="#b7bcc0" stroke-width="6"/>
        <ellipse cx="320" cy="300" rx="150" ry="62" fill="#eef2f3" stroke="#9aa3a8" stroke-width="6"/>
        <rect x="230" y="390" width="180" height="28" rx="8" fill="#d5dbde"/>
        """
    if kind == "shower":
        return """
        <rect x="70" y="70" width="36" height="120" rx="10" fill="#c5ccd0"/>
        <rect x="88" y="64" width="250" height="28" rx="12" fill="#b7c0c4"/>
        <circle cx="390" cy="200" r="150" fill="#e8eef0" stroke="#7e8b92" stroke-width="12"/>
        <circle cx="390" cy="200" r="46" fill="#9fd0c8"/>
        <circle cx="300" cy="380" r="12" fill="#9ec9d6"/>
        <circle cx="390" cy="400" r="10" fill="#b7d7e2"/>
        <circle cx="470" cy="370" r="12" fill="#9ec9d6"/>
        """
    if kind == "basin":
        return """
        <rect x="300" y="40" width="22" height="90" rx="6" fill="#c5ccd0"/>
        <path d="M250 70 h140" stroke="#9aa3a8" stroke-width="10" stroke-linecap="round"/>
        <ellipse cx="320" cy="250" rx="200" ry="90" fill="#f7fbfb" stroke="#9aa3a8" stroke-width="8"/>
        <ellipse cx="320" cy="250" rx="120" ry="48" fill="#d5e6ea"/>
        <rect x="140" y="330" width="360" height="70" rx="16" fill="#f3f1ec" stroke="#ddd6cb" stroke-width="4"/>
        """
    if kind == "light":
        return """
        <rect x="250" y="28" width="140" height="18" rx="8" fill="#d9d3c6"/>
        <rect x="308" y="46" width="24" height="70" fill="#c4b8a4"/>
        <path d="M170 130 h300 l-40 150 h-220 z" fill="#f4d7a2" stroke="#c4924a" stroke-width="6"/>
        <rect x="210" y="280" width="220" height="16" rx="6" fill="#fff6e4"/>
        <ellipse cx="320" cy="360" rx="90" ry="18" fill="#f0d7a4" opacity="0.85"/>
        """
    if kind == "cove":
        return """
        <rect x="40" y="70" width="560" height="280" rx="8" fill="#f6f1e8"/>
        <rect x="70" y="100" width="500" height="36" rx="8" fill="#f0d7a4"/>
        <rect x="70" y="156" width="500" height="16" rx="8" fill="#e7d3b0"/>
        <rect x="70" y="300" width="500" height="28" rx="8" fill="#f0d7a4"/>
        """
    if kind == "cabinet":
        return """
        <rect x="120" y="36" width="400" height="400" rx="8" fill="#d7b88a" stroke="#8c6239" stroke-width="6"/>
        <rect x="140" y="56" width="170" height="320" rx="4" fill="#e7d3b0"/>
        <rect x="330" y="56" width="170" height="320" rx="4" fill="#e4cba4"/>
        <rect x="292" y="180" width="12" height="70" rx="4" fill="#8c6239"/>
        <rect x="336" y="180" width="12" height="70" rx="4" fill="#8c6239"/>
        <rect x="120" y="390" width="400" height="36" fill="#8c6239"/>
        """
    if kind == "hood":
        return """
        <rect x="292" y="24" width="56" height="90" fill="#d5d7d8"/>
        <path d="M120 130 h400 l-30 70 h-340 z" fill="#eceeef" stroke="#9aa0a4" stroke-width="6"/>
        <rect x="150" y="210" width="340" height="18" rx="6" fill="#c5c8ca"/>
        <rect x="180" y="280" width="280" height="120" rx="12" fill="#f4f5f5" stroke="#d0d3d4" stroke-width="4"/>
        """
    if kind == "hob":
        return """
        <rect x="90" y="80" width="460" height="300" rx="24" fill="#2c2e30"/>
        <circle cx="230" cy="200" r="62" fill="none" stroke="#c6a36a" stroke-width="10"/>
        <circle cx="420" cy="200" r="62" fill="none" stroke="#c6a36a" stroke-width="10"/>
        <circle cx="230" cy="300" r="40" fill="none" stroke="#8d9396" stroke-width="8"/>
        <circle cx="420" cy="300" r="40" fill="none" stroke="#8d9396" stroke-width="8"/>
        """
    if kind == "oven":
        return """
        <rect x="140" y="40" width="360" height="390" rx="16" fill="#e8e9ea" stroke="#b7bbbe" stroke-width="6"/>
        <rect x="170" y="80" width="300" height="180" rx="8" fill="#2c3338"/>
        <circle cx="320" cy="320" r="28" fill="#c6a36a"/>
        <rect x="190" y="370" width="260" height="16" rx="6" fill="#c5c8ca"/>
        """
    if kind == "door":
        return """
        <rect x="180" y="20" width="280" height="390" rx="6" fill="#a87445" stroke="#6e4b2a" stroke-width="8"/>
        <rect x="206" y="44" width="228" height="150" rx="4" fill="#c4925a"/>
        <rect x="206" y="214" width="228" height="160" rx="4" fill="#c4925a"/>
        <rect x="404" y="210" width="16" height="46" rx="4" fill="#e7d3b0"/>
        """
    if kind == "switch":
        return """
        <rect x="150" y="50" width="340" height="360" rx="28" fill="#f7f4ee" stroke="#d9d3c6" stroke-width="8"/>
        <rect x="230" y="120" width="180" height="220" rx="16" fill="#fff" stroke="#c8c2b6" stroke-width="4"/>
        <rect x="248" y="150" width="144" height="70" rx="10" fill="#f0d7a4"/>
        """
    if kind == "wall":
        return """
        <rect x="40" y="36" width="560" height="380" rx="8" fill="#f6efe4"/>
        <rect x="40" y="36" width="560" height="70" fill="#e7d3b0"/>
        <path d="M40 180 h560 M40 280 h560" stroke="#eadfce" stroke-width="8"/>
        """
    if kind == "ceiling":
        return """
        <rect x="40" y="50" width="560" height="360" fill="#f8f1e6"/>
        <rect x="70" y="80" width="500" height="300" fill="#f3e6d0" stroke="#e7d3b0" stroke-width="16"/>
        <rect x="70" y="80" width="500" height="28" fill="#f0d7a4"/>
        """
    return """
        <rect x="48" y="48" width="250" height="250" fill="#f3e6d0" stroke="#c4a574" stroke-width="10"/>
        <rect x="342" y="48" width="250" height="250" fill="#e7d3b0" stroke="#c4a574" stroke-width="10"/>
        <rect x="48" y="250" width="250" height="160" fill="#ddc49a" stroke="#c4a574" stroke-width="10"/>
        <rect x="342" y="250" width="250" height="160" fill="#f6efe4" stroke="#c4a574" stroke-width="10"/>
        """


def example_svg(part_id: str, title: str, subtitle: str) -> bytes:
    kind = _kind(part_id, title)
    paper = PART_COLORS.get(part_id, "#f7f1e8")
    safe_title = _esc(title or "示例", 22)
    safe_sub = _esc(subtitle or "示例图", 32)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">
  <rect width="640" height="480" fill="{paper}"/>
  {_drawing(kind)}
  <text x="32" y="448" font-family="sans-serif" font-size="22" fill="#2c2924">{safe_title}</text>
  <text x="32" y="470" font-family="sans-serif" font-size="14" fill="#6f675d">{safe_sub}</text>
  <text x="500" y="452" font-family="sans-serif" font-size="18" fill="#8b6438">示例</text>
</svg>"""
    return svg.encode("utf-8")
