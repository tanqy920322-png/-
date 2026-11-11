from pathlib import Path

from app.services.image_to_3d import paid_image_to_3d_hook
from app.services.plan_geometry import parse_dxf, parse_svg
from app.services.visual_demo import build_demo_svg

def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login_customer(client, phone="13900001111") -> str:
    requested = client.post("/api/auth/otp/request", json={"phone": phone})
    assert requested.status_code == 200
    verified = client.post("/api/auth/otp/verify", json={"phone": phone, "code": requested.json()["dev_code"]})
    assert verified.status_code == 200
    return verified.json()["token"]


def login_admin(client) -> str:
    response = client.post("/api/admin/login", json={"username": "admin", "password": "demo1234"})
    assert response.status_code == 200
    return response.json()["token"]

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe|\xc3\xc1,\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_paid_image_hook_is_not_called_and_needs_no_key():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "paid_image_to_3d_hook(" not in text:
            continue
        definitions = text.count("def paid_image_to_3d_hook(")
        mentions = text.count("paid_image_to_3d_hook(")
        if mentions != definitions:
            offenders.append(path.name)
    assert offenders == []
    try:
        paid_image_to_3d_hook([b"photo"], "sanitary", (410, 680, 400))
    except RuntimeError as exc:
        assert "未授权" in str(exc)
    else:
        raise AssertionError("paid hook should refuse")


def test_svg_and_dxf_outlines():
    vectors = parse_svg(build_demo_svg())
    assert len(vectors) >= 8
    assert vectors[0][0][0] < vectors[0][1][0]
    dxf = """0
SECTION
2
ENTITIES
0
LINE
10
0
20
0
11
1000
21
0
0
LWPOLYLINE
90
3
10
0
20
0
10
500
20
0
10
500
20
400
0
ENDSEC
0
EOF
"""
    parsed, status = parse_dxf(dxf.encode())
    assert status == "ok"
    assert len(parsed) == 2
    binary, binary_status = parse_dxf(b"AutoCAD Binary DXF\x00")
    assert binary == []
    assert binary_status == "binary"


def test_seeded_stand_ins_do_not_change_the_quote(client):
    token = login_customer(client, "13800138000")
    body = client.get("/api/selections/sel_demo", headers=auth(token)).json()
    assert body["quote"]["total"] == 33511.8
    labels = {item["slot_label"]: item for item in body["substitutes"]}
    assert labels["马桶"]["label"] == "仅用于效果展示，不列入采购"
    assert labels["马桶"]["priced"] is False
    assert labels["马桶"]["orderable"] is False
    assert labels["马桶"]["paid_api_called"] is False
    assert "外形接近" in labels["沙发"]["promise"]
    assert "付费" in "".join(labels["沙发"]["limits"])
    photo = client.get(labels["马桶"]["photo_path"], headers=auth(token))
    assert photo.status_code == 200
    assert photo.content.startswith(b"\x89PNG")
    plan = body["plan"]
    assert plan["media"] == "svg"
    assert plan["honesty"].startswith("这些点是人工点上的")
    toilet = next(mark for mark in plan["marks"] if mark["slot_label"] == "马桶")
    assert toilet["room_name"] == "公卫"
    assert toilet["role"] == "product"
    assert "洁具" in toilet["product_name"]
    floor = next(mark for mark in plan["marks"] if mark["part_id"] == "floor")
    assert floor["role"] == "material"
    switch = next(mark for mark in plan["marks"] if mark["part_id"] == "switch_socket")
    assert switch["role"] == "empty"


def test_customer_upload_persists_and_leaves_the_quote(client):
    token = login_customer(client, "13800138000")
    before = client.get("/api/selections/sel_demo", headers=auth(token)).json()
    total = before["quote"]["total"]
    line_count = len(before["quote"]["lines"])
    created = client.post(
        "/api/selections/sel_demo/substitutes",
        headers=auth(token),
        data={"part_id": "switch_socket", "room_name": "客厅", "slot_label": "开关插座", "width_mm": "86"},
        files={
            "file": ("switch.png", PNG, "image/png"),
            "file_extra": ("switch-side.png", PNG, "image/png"),
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["quote"]["total"] == total
    assert len(body["quote"]["lines"]) == line_count
    saved = next(item for item in body["substitutes"] if item["slot_label"] == "开关插座" and not item["demo"])
    assert saved["width_mm"] == 86
    assert saved["depth_mm"] == 86
    assert saved["extra_photo_path"]
    again = client.get("/api/selections/sel_demo", headers=auth(token)).json()
    assert any(item["id"] == saved["id"] for item in again["substitutes"])
    assert again["quote"]["total"] == total
    removed = client.delete(f"/api/selections/sel_demo/substitutes/{saved['id']}", headers=auth(token))
    assert removed.status_code == 200
    assert removed.json()["quote"]["total"] == total
    assert all(item["id"] != saved["id"] for item in removed.json()["substitutes"])


def test_engineer_marks_a_simplified_plan(client):
    admin = login_admin(client)
    requirements = client.get("/api/admin/delivery-requirements", headers=auth(admin))
    assert requirements.status_code == 200
    text = "".join(requirements.json()["items"])
    assert "分图层" in text
    assert "墙线要闭合" in text
    assert "比例" in text
    assert "DWG" in requirements.json()["not_this_round"]
    project = client.get("/api/projects/GZ2019-003").json()
    unit_b = next(unit["id"] for unit in project["unit_types"] if unit["code"] == "B")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><rect x="10" y="10" width="40" height="20"/></svg>'
    uploaded = client.post(
        f"/api/admin/projects/{project['id']}/plans",
        headers=auth(admin),
        data={"unit_type_id": unit_b, "note": "练习用简化图"},
        files={"file": ("b.svg", svg, "image/svg+xml")},
    )
    assert uploaded.status_code == 200, uploaded.text
    plan = uploaded.json()
    assert plan["active"] is True
    assert plan["vectors"]
    marked = client.post(
        f"/api/admin/projects/{project['id']}/plans/{plan['id']}/marks",
        headers=auth(admin),
        json={"room_name": "公卫", "part_id": "sanitary", "slot_label": "马桶", "x": 0.42, "y": 0.33},
    )
    assert marked.status_code == 200, marked.text
    mark = marked.json()["marks"][0]
    assert mark["room_name"] == "公卫"
    assert mark["role"] == "empty"
    listed = client.get(f"/api/admin/projects/{project['id']}/plans?unit_type_id={unit_b}", headers=auth(admin))
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == plan["id"]
    preview = client.get(plan["preview_path"], headers=auth(admin))
    assert preview.status_code == 200
    assert b"<svg" in preview.content
