"""Print-time takeoff. Geometry is fixed rules. The selection quote stays put."""

from decimal import Decimal
from pathlib import Path

from app.services.takeoff import PickIn, RoomLoop, SchemeIn, TakeoffInput, build_takeoff
from app.services.takeoff_geometry import (
    open_run,
    room_area,
    room_perimeter,
    rooms_from_svg,
    wall_area,
)
from app.services.takeoff_mapping import INSTITUTION, UnconnectedModelMapper
from app.services.visual_demo import build_demo_svg

RECT = [(0, 0), (10, 0), (10, 4), (0, 4), (0, 0)]
OPEN = [(0, 0), (10, 0), (10, 4), (0, 4)]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login_admin(client) -> str:
    response = client.post("/api/admin/login", json={"username": "admin", "password": "demo1234"})
    assert response.status_code == 200
    return response.json()["token"]


def _sheet(**kwargs) -> dict:
    base = dict(
        selection_quote={"total": 33511.8, "area_note": "按分房面积", "lines": []},
        scale_m_per_unit=Decimal("1"),
        wall_height_m=Decimal("3"),
        rooms=[RoomLoop("客厅", RECT, True), RoomLoop("餐厅", RECT, True)],
        marks={("客厅", "ceiling"), ("客厅", "floor"), ("客厅", "wall")},
        schemes=[
            SchemeIn("ceiling", "天花", "灰白顶 + 香槟金灯槽", "gold_trough", Decimal("240"), "area"),
            SchemeIn("floor", "地面", "大规格灰砖", "tile", Decimal("100"), "area"),
            SchemeIn("wall", "墙面", "亮光灰乳胶漆", "gloss", Decimal("95"), "area"),
        ],
    )
    base.update(kwargs)
    return build_takeoff(TakeoffInput(**base))


def _items(body: dict, section_id: str) -> list[dict]:
    section = next(item for item in body["sections"] if item["id"] == section_id)
    return section["lines"]


def test_rectangle_is_deterministic_and_not_rewritten():
    first = room_area(RECT, 1)
    second = room_area(RECT, 1)
    edge = room_perimeter(RECT, 1)
    assert first == second
    assert first.quantity == Decimal("40.00")
    assert edge.quantity == Decimal("28.00")
    assert open_run([(0, 0), (10, 0)], 1).quantity == Decimal("10.00")
    assert wall_area(RECT, 1, 3).quantity == Decimal("84.00")
    again = room_perimeter(list(RECT), Decimal("1"))
    assert again.quantity == edge.quantity


def test_missing_scale_and_unclosed_wall_stay_blank():
    missing = room_area(RECT, None)
    assert missing.quantity is None
    assert missing.quantity != Decimal("8")
    assert missing.quantity != Decimal("10")
    assert missing.quantity != Decimal("40")
    assert "比例" in missing.reasons[0]
    short = open_run([(0, 0), (10, 0)], None)
    assert short.quantity is None
    unclosed = room_perimeter(OPEN, 1)
    assert unclosed.quantity is None
    assert unclosed.quantity != Decimal("14")
    assert unclosed.quantity != Decimal("28")
    assert "未闭合" in unclosed.reasons[0]
    point = open_run([(0, 0)], 1)
    assert point.quantity is None
    assert "落点" in point.reasons[0]
    no_height = wall_area(RECT, 1, None)
    assert no_height.quantity is None
    assert "层高" in "".join(no_height.reasons)


def test_demo_svg_uses_drawing_size_not_catalog_area():
    rooms = {room.name: room for room in rooms_from_svg(build_demo_svg())}
    living = rooms["客厅"]
    measured = room_area(living.polygon, Decimal("0.01"))
    assert measured.quantity == Decimal("21.32")
    assert measured.quantity != Decimal("14.00")
    assert measured.quantity != Decimal("8.00")
    blank = room_area(living.polygon, None)
    assert blank.quantity is None


def test_takeoff_prices_area_once_and_leaves_edge_unpriced():
    body = _sheet()
    assert body["institution"] == INSTITUTION == "祺盛"
    assert body["title"].startswith("祺盛")
    assert body["selection_quote"]["total"] == 33511.8
    assert body["mapping"]["model_hook"] == "not_connected"
    assert "不会调用模型" in body["mapping"]["honesty"]
    assert "模型估算" in body["mapping"]["honesty"]
    ceiling = _items(body, "ceiling")
    paint = next(line for line in ceiling if line["item"] == "客厅 平顶乳胶漆")
    edge = next(line for line in ceiling if line["item"] == "客厅 双眼皮")
    assert paint["quantity"] == 40.0
    assert paint["unit"] == "m²"
    assert paint["amount"] == 9600.0
    assert paint["priced"] is True
    assert edge["quantity"] == 28.0
    assert edge["unit"] == "m"
    assert edge["amount"] is None
    assert edge["priced"] is False
    assert edge["included_in_subtotal"] is False
    dining = next(line for line in ceiling if line["item"] == "餐厅 平顶乳胶漆")
    assert dining["quantity"] is None
    assert "未标注" in dining["remark"]
    floor = next(line for line in _items(body, "floor") if line["room_name"] == "客厅")
    wall = next(line for line in _items(body, "wall") if line["room_name"] == "客厅")
    assert floor["amount"] == 4000.0
    assert wall["quantity"] == 84.0
    assert wall["amount"] == 7980.0
    assert body["part_subtotal"] == 40 * 240 + 40 * 100 + 84 * 95
    names = [row["item"] for row in body["exclusions"]]
    assert names == ["水电改造", "人工", "管理费", "税金"]
    assert all(row["remark"] == "不含" and row["included_in_subtotal"] is False for row in body["exclusions"])
    assert all(row["amount"] is None for row in body["exclusions"])
    titles = [section["title"] for section in body["sections"]]
    assert titles[:3] == ["天花", "墙面", "地面"]
    assert "安装" in titles


def test_same_input_builds_the_same_sheet():
    assert _sheet() == _sheet()


def test_effect_unconfirmed_and_generated_stay_out_of_priced_lines():
    body = _sheet(
        picks=[
            PickIn("sanitary", "公卫", "马桶", Decimal("1"), Decimal("480"), True, "pending", "待确认"),
            PickIn("lighting", "客厅", "射灯", Decimal("2"), Decimal("90"), True, "confirmed", "随天花"),
        ],
        schemes=[
            SchemeIn("ceiling", "天花", "灰白顶", "gold_trough", Decimal("240")),
            SchemeIn("floor", "地面", "灰砖", "tile", Decimal("100")),
            SchemeIn("wall", "墙面", "乳胶漆", "gloss", Decimal("95")),
            SchemeIn("sanitary", "洁具", "公卫与厨房", "", Decimal("1680"), "each"),
            SchemeIn("lighting", "灯具", "随天花方案", "", Decimal("860"), "each"),
        ],
        substitutes=[{"room_name": "公卫", "slot_label": "马桶", "part_id": "sanitary"}],
        generated=[{"item": "待生成马桶", "status": "pending"}],
    )
    priced = [line["item"] for section in body["sections"] for line in section["lines"] if line["priced"]]
    assert "公卫 马桶" not in priced
    assert "待生成马桶" not in priced
    assert any(line["item"] == "客厅 射灯" and line["priced"] for section in body["sections"] for line in section["lines"])
    remarks = " ".join(row["remark"] for row in body["unpriced"])
    assert "仅用于效果展示" in remarks
    assert "未确认" in remarks
    assert all(row["priced"] is False and row["included_in_subtotal"] is False for row in body["unpriced"])
    install = _items(body, "install")
    assert all(line["amount"] is None and line["included_in_subtotal"] is False for line in install)
    exclusion_sum = sum(row["amount"] or 0 for row in body["exclusions"])
    assert exclusion_sum == 0
    assert body["part_subtotal"] == _sheet()["part_subtotal"] + 180.0


def test_full_drop_and_wainscot_follow_the_rule_table():
    drop = _sheet(
        schemes=[SchemeIn("ceiling", "天花", "浅二级跌级吊顶", "tray", Decimal("260"))],
        marks={("客厅", "ceiling")},
        rooms=[RoomLoop("客厅", RECT, True)],
    )
    names = [line["item"] for line in _items(drop, "ceiling")]
    assert "客厅 跌级吊顶" in names
    assert "客厅 双眼皮" in names
    band = _sheet(
        schemes=[SchemeIn("wall", "墙面", "浅木护墙 2.4m", "wainscot", Decimal("168"))],
        marks={("客厅", "wall")},
        rooms=[RoomLoop("客厅", RECT, True)],
        wall_height_m=Decimal("3"),
    )
    lines = _items(band, "wall")
    skirt = next(line for line in lines if "护墙" in line["item"])
    upper = next(line for line in lines if "上部" in line["item"])
    assert skirt["quantity"] == 67.2
    assert skirt["priced"] is True
    assert upper["quantity"] == 16.8
    assert upper["priced"] is False
    assert upper["included_in_subtotal"] is False
    no_storey = _sheet(
        schemes=[SchemeIn("wall", "墙面", "浅木护墙 2.4m", "wainscot", Decimal("168"))],
        marks={("客厅", "wall")},
        rooms=[RoomLoop("客厅", RECT, True)],
        wall_height_m=None,
    )
    upper_blank = next(line for line in _items(no_storey, "wall") if "上部" in line["item"])
    assert upper_blank["quantity"] is None
    assert "层高" in upper_blank["remark"]


def test_model_hook_is_unconnected_and_offline():
    result = UnconnectedModelMapper().map_scheme("ceiling", "gold_trough", "灰白顶")
    assert result.connected is False
    assert result.lines == ()
    root = Path(__file__).resolve().parents[1] / "app" / "services"
    for name in ("takeoff.py", "takeoff_geometry.py", "takeoff_mapping.py"):
        text = (root / name).read_text(encoding="utf-8").lower()
        for banned in ("dashscope", "httpx", "openai", "百炼", "tripo"):
            assert banned not in text
        assert 'INSTITUTION = "祺盛"' in (root / "takeoff_mapping.py").read_text(encoding="utf-8")


def test_sel_demo_quote_unchanged_and_takeoff_does_not_invent(client):
    admin = login_admin(client)
    before = client.get("/api/selections/sel_demo", headers=auth(admin)).json()
    assert before["quote"]["total"] == 33511.8
    sheet = client.get("/api/selections/sel_demo/takeoff", headers=auth(admin))
    assert sheet.status_code == 200, sheet.text
    body = sheet.json()
    after = client.get("/api/selections/sel_demo", headers=auth(admin)).json()
    assert after["quote"]["total"] == 33511.8
    assert after["quote"]["lines"] == before["quote"]["lines"]
    assert body["selection_quote"]["total"] == 33511.8
    assert body["institution"] == "祺盛"
    assert body["plan"]["has_scale"] is False
    assert body["mapping"]["model_hook"] == "not_connected"
    living = next(line for line in _items(body, "ceiling") if line["item"].startswith("客厅"))
    assert living["quantity"] is None
    assert living["quantity"] != 14
    assert "比例" in living["remark"]
    assert "未标注" not in living["remark"]
    dining = next(line for line in _items(body, "ceiling") if "餐厅" in line["item"] and "乳胶漆" in line["item"])
    assert dining["quantity"] is None
    assert "未标注" in dining["remark"]
    missing = next(line for line in _items(body, "ceiling") if "儿童房" in line["item"])
    assert missing["quantity"] is None
    assert "没有这个房间" in missing["remark"]
    priced = [line for section in body["sections"] for line in section["lines"] if line["priced"]]
    assert priced == []
    joined = " ".join(row["item"] + row["remark"] for row in body["unpriced"])
    assert "马桶" in joined
    assert "仅用于效果展示" in joined
    assert all(row["priced"] is False for row in body["unpriced"])
    assert [row["item"] for row in body["exclusions"]] == ["水电改造", "人工", "管理费", "税金"]
    assert body["part_subtotal"] == 0
    assert "安装" in [section["title"] for section in body["sections"]]


def test_measure_endpoint_rejects_a_guess_and_keeps_blank(client):
    admin = login_admin(client)
    project = client.get("/api/projects/GZ2019-003").json()
    unit_b = next(unit["id"] for unit in project["unit_types"] if unit["code"] == "B")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 20">'
        '<rect x="0" y="0" width="10" height="4"/>'
        '<text x="1" y="2">客厅</text></svg>'
    ).encode()
    uploaded = client.post(
        f"/api/admin/projects/{project['id']}/plans",
        headers=auth(admin),
        data={"unit_type_id": unit_b, "note": "比例练习"},
        files={"file": ("b-scale.svg", svg, "image/svg+xml")},
    )
    assert uploaded.status_code == 200, uploaded.text
    plan = uploaded.json()
    assert plan["scale_m_per_unit"] is None
    rejected = client.put(
        f"/api/admin/projects/{project['id']}/plans/{plan['id']}/measure",
        headers=auth(admin),
        json={"scale_m_per_unit": 0, "wall_height_m": None},
    )
    assert rejected.status_code == 400
    saved = client.put(
        f"/api/admin/projects/{project['id']}/plans/{plan['id']}/measure",
        headers=auth(admin),
        json={"scale_m_per_unit": 1, "wall_height_m": 3},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["scale_m_per_unit"] == 1
    assert saved.json()["wall_height_m"] == 3
    demo = client.get("/api/selections/sel_demo", headers=auth(admin)).json()
    assert demo["quote"]["total"] == 33511.8
    assert demo["plan"]["scale_m_per_unit"] is None
