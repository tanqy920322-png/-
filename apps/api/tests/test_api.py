from pathlib import Path

SAMPLE = Path(__file__).resolve().parents[3] / "packages" / "catalog" / "sample_sanitary.csv"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login_customer(client, phone="13900001111") -> str:
    requested = client.post("/api/auth/otp/request", json={"phone": phone})
    assert requested.status_code == 200
    code = requested.json()["dev_code"]
    verified = client.post("/api/auth/otp/verify", json={"phone": phone, "code": code})
    assert verified.status_code == 200
    return verified.json()["token"]


def login_admin(client) -> str:
    response = client.post("/api/admin/login", json={"username": "admin", "password": "demo1234"})
    assert response.status_code == 200
    return response.json()["token"]


def test_health_and_seeded_catalog(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["db"] == "ok"
    styles = client.get("/api/styles").json()
    assert [item["id"] for item in styles] == ["cream", "european", "light_luxury"]
    assert len(styles[0]["parts"]) == 3
    assert [scheme["index"] for scheme in styles[0]["parts"][0]["schemes"]] == [1, 2, 3]
    project = client.get("/api/projects/GZ2019-003")
    assert project.status_code == 200
    body = project.json()
    areas = {unit["code"]: unit["finish_area_m2"] for unit in body["unit_types"]}
    assert areas == {"A": 60.6, "B": 69.6}
    placeholders = [asset for unit in body["unit_types"] for asset in unit["assets"]]
    assert {asset["status"] for asset in placeholders} == {"placeholder"}
    assert any(asset["filename"].endswith(".dwg") for asset in placeholders)


def test_customer_quote_updates_and_rejects_other_style(client):
    token = login_customer(client)
    created = client.post(
        "/api/selections",
        headers=auth(token),
        json={"project_code": "gz2019-003", "unit_type_id": "gz2019-003-a"},
    )
    assert created.status_code == 200
    selection = created.json()
    assert selection["style"] is None
    assert selection["quote"]["total"] == 0
    styled = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={"style_id": "cream"},
    )
    assert styled.status_code == 200
    body = styled.json()
    assert body["ceiling"]["id"] == "cream-ceiling-1"
    assert body["floor"]["id"] == "cream-floor-1"
    assert body["wall"]["id"] == "cream-wall-1"
    assert body["quote"]["total"] == 26239.8
    changed = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={"floor_scheme_id": "cream-floor-2"},
    )
    assert changed.json()["quote"]["total"] == 28057.8
    rejected = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={"ceiling_scheme_id": "european-ceiling-1"},
    )
    assert rejected.status_code == 400
    admin = login_admin(client)
    visible = client.get(f"/api/selections/{selection['id']}", headers=auth(admin))
    assert visible.status_code == 200
    assert visible.json()["customer_phone"] == "13900001111"


def test_admin_publish_import_upload_and_exports(client):
    admin = login_admin(client)
    created = client.post(
        "/api/admin/projects",
        headers=auth(admin),
        json={"code": "PILOT-9", "name": "试点草稿", "publish": False},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]
    hidden = client.get("/api/projects/PILOT-9")
    assert hidden.status_code == 404
    published = client.patch(
        f"/api/admin/projects/{project_id}",
        headers=auth(admin),
        json={"status": "published"},
    )
    assert published.json()["status"] == "published"
    with_unit = client.post(
        f"/api/admin/projects/{project_id}/units",
        headers=auth(admin),
        json={"code": "C", "name": "C户型", "building_area_m2": 70, "finish_area_m2": 50, "summary": "测试户型"},
    )
    assert with_unit.json()["unit_types"][0]["finish_area_m2"] == 50
    upload = client.post(
        f"/api/admin/projects/{project_id}/assets",
        headers=auth(admin),
        data={"kind": "floor_plan", "unit_type_id": f"{project_id}-c"},
        files={"file": ("plan.pdf", b"%PDF-1.4 demo", "application/pdf")},
    )
    assert upload.status_code == 200
    asset = upload.json()["unit_types"][0]["assets"][0]
    assert asset["status"] == "stored"
    downloaded = client.get(f"/api/assets/{asset['id']}/file", headers=auth(admin))
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    missing = client.get("/api/assets/asset-a-usage/file", headers=auth(admin))
    assert missing.status_code == 404

    imported = client.post(
        "/api/admin/procurement/import",
        headers=auth(admin),
        data={"category": "sanitary", "title": "再次导入", "project_id": "gz2019-003"},
        files={"file": ("sample_sanitary.csv", SAMPLE.read_bytes(), "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["row_count"] == 8
    assert imported.json()["items"][0]["category"] == "sanitary"

    token = login_customer(client, "13900002222")
    selection = client.post(
        "/api/selections",
        headers=auth(token),
        json={"project_code": "GZ2019-003", "unit_type_id": "gz2019-003-b"},
    ).json()
    client.patch(f"/api/selections/{selection['id']}", headers=auth(token), json={"style_id": "european"})
    submitted = client.post(f"/api/selections/{selection['id']}/submit", headers=auth(token))
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["quote"]["finish_area_m2"] == 69.6
    pdf = client.post(
        f"/api/selections/{selection['id']}/exports",
        headers=auth(token),
        json={"kind": "quote_pdf"},
    )
    assert pdf.status_code == 200
    pdf_file = client.get(f"/api/exports/{pdf.json()['id']}/file", headers=auth(token))
    assert pdf_file.content.startswith(b"%PDF")
    assert "CJK" in pdf_file.content.decode("latin1", errors="ignore") or len(pdf_file.content) > 800
    pack = client.post(
        f"/api/selections/{selection['id']}/exports",
        headers=auth(token),
        json={"kind": "image_pack"},
    )
    pack_file = client.get(f"/api/exports/{pack.json()['id']}/file", headers=auth(token))
    assert pack_file.content.startswith(b"PK")
    scene = client.post(
        "/api/ai/scene",
        headers=auth(token),
        data={"selection_id": selection["id"]},
        files={"file": ("chair.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert scene.status_code == 200
    assert scene.json()["provider"] == "unconfigured"
    assert "DashScope" in scene.json()["message"] or "百炼" in scene.json()["message"]
    recognize = client.post(
        "/api/ai/floorplan",
        headers=auth(admin),
        data={"asset_id": "asset-a-plan"},
    )
    assert recognize.status_code == 200
    assert "Qwen" in recognize.json()["message"] or "豆包" in recognize.json()["message"]
    listed = client.get("/api/admin/selections", headers=auth(admin))
    assert any(item["id"] == selection["id"] for item in listed.json())
    demo = client.get("/api/selections/sel_demo", headers=auth(admin))
    assert demo.status_code == 200
    assert demo.json()["style"]["id"] == "light_luxury"
    assert demo.json()["quote"]["total"] == 33511.8
    assert {line["part_id"] for line in demo.json()["lines"]} >= {"ceiling", "floor", "wall"}


def test_nine_parts_and_addon_quote(client):
    parts = client.get("/api/parts").json()
    assert [item["id"] for item in parts] == [
        "ceiling",
        "wall",
        "floor",
        "cabinetry",
        "sanitary",
        "entry_door",
        "kitchen_appliance",
        "lighting",
        "switch_socket",
    ]
    categories = {item["id"] for item in client.get("/api/meta").json()["procurement_categories"]}
    assert {"sanitary", "lighting", "entry_door", "kitchen_appliance"} <= categories
    token = login_customer(client, "13900003333")
    selection = client.post(
        "/api/selections",
        headers=auth(token),
        json={"project_code": "GZ2019-003", "unit_type_id": "gz2019-003-a"},
    ).json()
    styled = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={"style_id": "cream"},
    ).json()
    assert styled["quote"]["total"] == 26239.8
    ceiling = next(part for part in styled["parts"] if part["id"] == "ceiling")
    lights = next(item for item in ceiling["schemes"][0]["items"] if item["group_label"] == "客厅天花 · 9 个射灯／筒灯")
    assert lights["room_name"] == "客厅"
    assert lights["display_part_id"] == "lighting"
    assert lights["default_quantity"] == 9
    door = next(part for part in styled["parts"] if part["id"] == "entry_door")
    assert len(door["schemes"][0]["items"]) == 1
    assert door["schemes"][0]["items"][0]["group_label"] == "整户 · 1 樘入户门"
    master = [item for item in next(part for part in styled["parts"] if part["id"] == "cabinetry")["schemes"][1]["items"] if item["room_name"] == "主卧"]
    assert {item["name"] for item in master} == {"衣柜", "书柜", "床头柜"}
    saved = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={
            "lines": [
                {"part_id": "sanitary", "scheme_id": "sanitary-1"},
                {
                    "part_id": "ceiling",
                    "scheme_id": "cream-ceiling-1",
                    "items": [
                        {"item_id": lights["id"], "included": True, "quantity": 9, "brand_tier": "import"}
                    ],
                },
            ]
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["ceiling"]["id"] == "cream-ceiling-1"
    assert body["quote"]["total"] == 28729.8
    sanitary = [line for line in body["quote"]["lines"] if line["part_id"].startswith("sanitary")]
    assert sum(line["amount"] for line in sanitary) == 1680
    assert {line["pricing"] for line in sanitary} == {"each"}
    light_line = next(line for line in body["quote"]["lines"] if line["part_id"].startswith("lighting#"))
    assert light_line["brand_tier"] == "import"
    assert light_line["quantity"] == 9
    assert light_line["amount"] == 810
    stored = {line["part_id"]: line for line in body["lines"]}
    assert stored["sanitary"]["scheme_id"] == "sanitary-1"
    assert {pick["room_name"] for pick in stored["sanitary"]["picks"]} >= {"公卫", "厨房"}
    assert any(pick["brand_tier"] == "import" and pick["quantity"] == 9 for pick in stored["ceiling"]["picks"])
    slot = next(item for item in ceiling["schemes"][0]["items"] if item["name"] == "灯槽灯带")
    with_slot = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={
            "lines": [
                {
                    "part_id": "ceiling",
                    "scheme_id": "cream-ceiling-1",
                    "items": [
                        {"item_id": slot["id"], "included": True, "quantity": 1, "brand_tier": "domestic"}
                    ],
                }
            ]
        },
    )
    assert with_slot.status_code == 200
    assert with_slot.json()["quote"]["total"] == 28889.8
    night = next(item for item in master if item["name"] == "床头柜")
    with_cabinets = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={"lines": [{"part_id": "cabinetry", "scheme_id": "cabinetry-2"}]},
    )
    assert with_cabinets.status_code == 200
    assert with_cabinets.json()["quote"]["total"] == 41689.8
    without_night = client.patch(
        f"/api/selections/{selection['id']}",
        headers=auth(token),
        json={
            "lines": [
                {
                    "part_id": "cabinetry",
                    "scheme_id": "cabinetry-2",
                    "items": [{"item_id": night["id"], "included": False, "quantity": 1, "brand_tier": "domestic"}],
                }
            ]
        },
    )
    assert without_night.status_code == 200
    assert without_night.json()["quote"]["total"] == 40789.8


def test_example_library_import_binding_and_fallback_model(client):
    from app.services.sample_pack import build_image_zip, build_manual_pdf

    products = client.get("/api/products").json()
    assert len(products) >= 9 * 36
    sanitary = [item for item in products if item["part_id"] == "sanitary"]
    assert len(sanitary) >= 36
    assert sanitary[0]["example"] is True
    assert sanitary[0]["import_price"] > sanitary[0]["domestic_price"]
    image = client.get(sanitary[0]["image_url"])
    assert image.status_code == 200
    assert b"<svg" in image.content
    admin = login_admin(client)
    imported = client.post(
        "/api/admin/products/import",
        headers=auth(admin),
        files={"file": ("manual.pdf", build_manual_pdf(), "application/pdf")},
    )
    assert imported.status_code == 200
    pending = imported.json()["products"]
    assert len(pending) == 6
    assert pending[0]["status"] == "pending"
    assert pending[0]["name"] == "示例平顶漆"
    public_ids = {item["id"] for item in client.get("/api/products").json()}
    assert pending[0]["id"] not in public_ids
    confirmed = client.post(f"/api/admin/products/{pending[0]['id']}/confirm", headers=auth(admin))
    assert confirmed.status_code == 200
    assert confirmed.json()["id"] in {item["id"] for item in client.get("/api/products").json()}
    packed = client.post(
        "/api/admin/products/import",
        headers=auth(admin),
        files={"file": ("pack.zip", build_image_zip(), "application/zip")},
    )
    assert packed.status_code == 200
    assert packed.json()["imported"] == 6
    project = client.get("/api/projects/GZ2019-003").json()
    bound = client.post(
        f"/api/admin/projects/{project['id']}/bindings",
        headers=auth(admin),
        json={
            "unit_type_id": project["unit_types"][0]["id"],
            "room_name": "客厅",
            "part_id": "sanitary",
            "product_id": sanitary[0]["id"],
        },
    )
    assert bound.status_code == 200
    assert bound.json()["product"]["id"] == sanitary[0]["id"]
    job = client.post(
        "/api/model-jobs",
        headers=auth(admin),
        json={"part_id": "cabinetry", "name": "示例通用衣柜", "image_names": ["front.png"]},
    )
    assert job.status_code == 200
    body = job.json()
    assert body["status"] == "fallback"
    assert body["product"]["height_mm"] >= 2400
    assert "付费" in body["message"]
