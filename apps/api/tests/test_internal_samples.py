import json
import os
from pathlib import Path

from app.database import get_session_factory
from app.models import GeneratedCandidate
from app.services.image_to_3d import paid_image_to_3d_hook

REPO = Path(__file__).resolve().parents[3]
GENERATED = REPO / "packages" / "catalog" / "internal-sample" / "generated"
CONFIRMED_CODES = ["HC0508PT", "CW887REBTM", "E8331L1_DG", "NXXY1157", "CX23"]
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe|\xc3\xc1,\x00\x00\x00\x00IEND\xaeB`\x82"
)

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


def test_confirmed_batch_and_manual_confirm_stay_inside_the_internal_library(client):
    admin = login_admin(client)
    status = client.get("/api/admin/generation", headers=auth(admin))
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "首批五件已确认入库"
    assert body["paid_api_called"] is False
    assert body["postpaid_enabled"] is False
    assert body["free_pack_exhausted"] is True
    assert body["can_generate"] is False
    assert "额度不足" in body["note"]
    assert "后付费没有开通" in body["note"]
    assert "祺盛" in body["note"]
    assert body["queue"] == []
    review = {item["model_code"]: item for item in body["review"]}
    assert list(review) == ["HC0508PT", "CW887REBTM", "E8331L1_DG", "NXXY1157", "CX23", "U60"]
    for code in ("HC0508PT", "CW887REBTM", "E8331L1_DG", "NXXY1157", "CX23"):
        assert review[code]["status"] == "已确认入库"
    assert review["U60"]["status"] == "未做"
    assert "没有产品图" in review["U60"]["note"]
    assert "未接免费接口" not in status.text
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


def test_five_generated_meshes_stay_internal_and_quote_is_unchanged(client, tmp_path):
    manifest = json.loads((GENERATED / "manifest.json").read_text(encoding="utf-8"))
    assert [item["model_code"] for item in manifest["items"]] == CONFIRMED_CODES
    assert manifest["skipped"][0]["model_code"] == "U60"
    assert "没有产品图" in manifest["skipped"][0]["note"]
    assert manifest["free_pack_exhausted"] is True
    assert manifest["postpaid_enabled"] is False
    assert manifest["paid_api_called"] is False
    assert list((GENERATED / "previews").glob("*.glb")) == []
    for item in manifest["items"]:
        preview = GENERATED / item["preview"]
        assert preview.is_file()
        assert preview.read_bytes().startswith(b"\x89PNG")
        assert not (GENERATED / item["mesh_filename"]).exists()

    admin = login_admin(client)
    payload = client.get("/api/admin/internal-samples", headers=auth(admin)).json()
    assert payload["pack_count"] == 20
    assert payload["verified_count"] == 18
    assert "祺盛" in payload["disclaimer"]
    assert "禊盛" not in json.dumps(payload, ensure_ascii=False)
    pack = [item for item in payload["items"] if item["source"] == "sample_pack"]
    assert len(pack) == 20
    generated = [item for item in payload["items"] if item["source"] == "generated" and item["model_code"] in CONFIRMED_CODES]
    generated.sort(key=lambda item: item["priority"])
    assert [item["model_code"] for item in generated] == CONFIRMED_CODES
    parts = {
        "HC0508PT": "sanitary",
        "CW887REBTM": "sanitary",
        "E8331L1_DG": "switch_socket",
        "NXXY1157": "lighting",
        "CX23": "entry_door",
    }
    for item in generated:
        assert item["part_id"] == parts[item["model_code"]]
        assert item["confirmed"] is True
        assert item["customer_visible"] is False
        assert item["priced"] is False
        assert item["orderable"] is False
        assert "生成件" in item["data_status"]
        assert "不给客户看" in item["data_status"]
        assert item["has_image"] is True
        image = client.get(item["image_url"], headers=auth(admin))
        assert image.status_code == 200
        assert image.content.startswith(b"\x89PNG")
        assert item["mesh_ready"] is False
        assert "生模评测" in item["mesh_note"]
        assert item["model_code"] in item["mesh_note"]
        missing = client.get(item["mesh_url"], headers=auth(admin))
        assert missing.status_code == 404
        assert item["model_code"] in missing.json()["detail"]
        assert "生模评测" in missing.json()["detail"]
    schneider = next(item for item in generated if item["model_code"] == "E8331L1_DG")
    assert schneider["brand_label"] == "施耐德 / Schneider"
    pack_codes = {item["model_code"] for item in pack}
    assert set(CONFIRMED_CODES) <= pack_codes
    assert "U60" in pack_codes
    assert client.get("/api/admin/internal-samples/isample-01/mesh", headers=auth(admin)).status_code == 404

    customer = login_customer(client, "13800138000")
    public_codes = {item["model_code"] for item in client.get("/api/products").json()}
    assert set(CONFIRMED_CODES).isdisjoint(public_codes)
    selection = client.get("/api/selections/sel_demo", headers=auth(customer)).json()
    assert selection["quote"]["total"] == 33511.8
    dumped = json.dumps(selection, ensure_ascii=False)
    for code in CONFIRMED_CODES:
        assert code not in dumped

    os.environ["QISHENG_MESH_DIR"] = str(tmp_path)
    try:
        (tmp_path / "HC0508PT.glb").write_bytes(b"glTF\x02\x00\x00\x00test-mesh")
        mounted = client.get("/api/admin/internal-samples", headers=auth(admin)).json()
        toilet = next(item for item in mounted["items"] if item["id"] == "isample-gen-HC0508PT")
        assert toilet["mesh_ready"] is True
        assert "HC0508PT.glb" in toilet["mesh_note"]
        mesh = client.get(toilet["mesh_url"], headers=auth(admin))
        assert mesh.status_code == 200
        assert mesh.content.startswith(b"glTF")
        other = next(item for item in mounted["items"] if item["id"] == "isample-gen-CX23")
        assert other["mesh_ready"] is False
        absent = client.get(other["mesh_url"], headers=auth(admin))
        assert absent.status_code == 404
        assert "CX23.glb" in absent.json()["detail"]
    finally:
        os.environ.pop("QISHENG_MESH_DIR", None)
    cleared = client.get("/api/admin/internal-samples", headers=auth(admin)).json()
    again = next(item for item in cleared["items"] if item["id"] == "isample-gen-HC0508PT")
    assert again["mesh_ready"] is False


def test_new_generation_stops_when_the_free_pack_is_exhausted(client):
    admin = login_admin(client)
    customer = login_customer(client, "13800138000")
    before_ids = {item["id"] for item in client.get("/api/products").json()}
    before_total = client.get("/api/selections/sel_demo", headers=auth(customer)).json()["quote"]["total"]
    assert before_total == 33511.8
    os.environ["HUNYUAN_API_KEY"] = "do-not-use"
    try:
        started = client.post(
            "/api/admin/generation/start",
            headers=auth(admin),
            files={"file": ("door.png", TINY_PNG, "image/png")},
            data={"part_id": "entry_door", "brand": "美心", "model_code": "CX23", "name": "入户门再生成"},
        )
    finally:
        os.environ.pop("HUNYUAN_API_KEY", None)
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "blocked"
    assert body["paid_api_called"] is False
    assert body["postpaid_enabled"] is False
    assert body["free_pack_exhausted"] is True
    assert body["priced"] is False
    assert body["orderable"] is False
    assert body["customer_visible"] is False
    assert "额度已用尽" in body["message"]
    assert "后付费没有开通" in body["message"]
    assert "付费接口" in body["message"]
    assert "积分" in body["message"]
    assert "禊盛" not in started.text
    catalog = client.post(
        "/api/admin/generation/start",
        headers=auth(admin),
        files={"file": ("manual.pdf", b"%PDF-1.1\n%%EOF", "application/pdf")},
        data={"part_id": "", "brand": "", "model_code": "", "name": "图册"},
    )
    assert catalog.status_code == 200
    assert catalog.json()["status"] == "blocked"
    assert catalog.json()["paid_api_called"] is False
    rejected = client.post(
        "/api/admin/generation/start",
        headers=auth(admin),
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert rejected.status_code == 400
    denied = client.post(
        "/api/admin/generation/start",
        headers=auth(customer),
        files={"file": ("door.png", TINY_PNG, "image/png")},
    )
    assert denied.status_code == 401
    after_ids = {item["id"] for item in client.get("/api/products").json()}
    assert after_ids == before_ids
    assert client.get("/api/selections/sel_demo", headers=auth(customer)).json()["quote"]["total"] == 33511.8
    listed = client.get("/api/admin/generation", headers=auth(admin)).json()
    assert listed["paid_api_called"] is False
    assert any(item["filename"] == "door.png" and item["status"] == "blocked" and item["paid_api_called"] is False for item in listed["attempts"])
    assert any(item["filename"] == "manual.pdf" and item["paid_api_called"] is False for item in listed["attempts"])
    assert all(item["status"] == "pending" for item in listed["queue"])
