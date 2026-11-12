from app.database import get_session_factory
from app.models import GeneratedCandidate
from app.services.image_to_3d import paid_image_to_3d_hook

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


def test_pack_imports_twenty_rows_without_inventing_the_gaps(client):
    admin = login_admin(client)
    body = client.get("/api/admin/internal-samples", headers=auth(admin))
    assert body.status_code == 200
    payload = body.json()
    rows = [item for item in payload["items"] if item["source"] == "sample_pack"]
    assert len(rows) == 20
    assert sum(1 for item in rows if item["verified"]) == 18
    assert "祺盛" in payload["disclaimer"]
    assert "非授权经销清单" in payload["disclaimer"]
    brands = {item["brand"]: item for item in rows}
    wall = brands["东鹏"]
    assert wall["model_code"] == "T05FA261401"
    assert wall["kind"] == "material"
    assert wall["has_image"] is True
    oppein = brands["欧派"]
    assert oppein["verified"] is False
    assert oppein["model_code"] is None
    assert oppein["width_mm"] is None
    assert oppein["offer_mode"] == "made_to_measure"
    assert oppein["data_status"] == "量尺定制"
    assert oppein["has_image"] is False
    nobilia = brands["Nobilia"]
    assert nobilia["offer_mode"] == "made_to_measure"
    assert nobilia["model_code"] == "U60"
    assert nobilia["width_mm"] == 600
    assert nobilia["depth_mm"] == 561
    assert nobilia["height_mm"] == 720
    assert nobilia["data_status"] == "官方类型表模块尺寸、供按实际尺寸定制对照"
    chint = brands["正泰"]
    assert chint["verified"] is False
    assert chint["model_code"] is None
    assert chint["width_mm"] is None
    assert chint["data_status"] == "未找到可核验公开资料"
    assert chint["has_image"] is False
    for row in (oppein, nobilia, chint):
        assert row["priced"] is False
        assert row["orderable"] is False
        assert row["customer_visible"] is False
    for brand in ("Nobilia", "Hörmann", "Siemens"):
        assert brands[brand]["has_image"] is False
    dumped = body.text
    assert "东麋" not in dumped
    assert "禊盛" not in dumped
    assert "硲盛" not in dumped
    assert "禍盛" not in dumped


def test_material_textures_are_served_and_do_not_enter_the_customer_catalog(client):
    textures = client.get("/api/finish-textures")
    assert textures.status_code == 200
    items = textures.json()["items"]
    assert len(items) == 6
    assert textures.json()["label"].startswith("示意贴图")
    assert {item["part_id"] for item in items} == {"ceiling", "wall", "floor"}
    dongpeng = next(item for item in items if item["brand"] == "东鹏")
    image = client.get(dongpeng["texture_url"])
    assert image.status_code == 200
    assert image.content[:3] == b"\xff\xd8\xff"
    missing = client.get("/api/finish-textures/isample-07/image")
    assert missing.status_code == 404
    public = client.get("/api/products").json()
    codes = {item["model_code"] for item in public}
    assert "HC0508PT" not in codes
    assert "EF1020" not in codes
    assert "T05FA261401" not in codes


def test_generation_is_unfinished_and_confirm_stays_inside_the_internal_library(client):
    admin = login_admin(client)
    status = client.get("/api/admin/generation", headers=auth(admin))
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "未完成"
    assert body["paid_api_called"] is False
    assert body["queue"] == []
    assert [item["status"] for item in body["review"]] == ["未接免费接口"] * 6
    assert [item["model_code"] for item in body["review"]] == [
        "HC0508PT",
        "CW887REBTM",
        "E8331L1_DG",
        "NXXY1157",
        "CX23",
        "U60",
    ]
    db = get_session_factory()()
    db.add(
        GeneratedCandidate(
            id="gen-test-1",
            part_id="sanitary",
            brand="测试",
            model_code="GEN-TEST",
            label="测试生成件",
            status="pending",
            note="测试用，不是真实生模。",
        )
    )
    db.commit()
    db.close()
    queued = client.get("/api/admin/generation", headers=auth(admin)).json()
    assert [item["id"] for item in queued["queue"]] == ["gen-test-1"]
    customer = login_customer(client, "13800138000")
    before = client.get("/api/selections/sel_demo", headers=auth(customer)).json()
    assert before["quote"]["total"] == 33511.8
    confirmed = client.post("/api/admin/generation/gen-test-1/confirm", headers=auth(admin))
    assert confirmed.status_code == 200
    sample = confirmed.json()["sample"]
    assert sample["source"] == "generated"
    assert sample["priced"] is False
    assert sample["customer_visible"] is False
    internal = client.get("/api/admin/internal-samples", headers=auth(admin)).json()
    assert any(item["model_code"] == "GEN-TEST" for item in internal["items"])
    public_codes = {item["model_code"] for item in client.get("/api/products").json()}
    assert "GEN-TEST" not in public_codes
    after = client.get("/api/selections/sel_demo", headers=auth(customer)).json()
    assert after["quote"]["total"] == 33511.8
    assert all(item["priced"] is False and item["orderable"] is False for item in after["substitutes"])
    try:
        paid_image_to_3d_hook([b"x"], "sanitary", (410, 680, 400))
    except RuntimeError:
        pass
    else:
        raise AssertionError("paid hook should refuse")
