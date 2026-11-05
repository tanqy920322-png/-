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
    assert imported.json()["row_count"] == 5
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
