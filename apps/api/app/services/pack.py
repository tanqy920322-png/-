import io
import json
import zipfile


def render_image_pack(selection: dict) -> bytes:
    project = selection["project"]
    unit = selection["unit"]
    style = selection.get("style") or {}
    manifest = {
        "kind": "image_pack_placeholder",
        "selection_id": selection["id"],
        "project_code": project["code"],
        "unit_name": unit["name"],
        "style_name": style.get("name"),
        "note": "图册占位包。正式效果图将在三维导出或图像接口接入后写入，当前不含渲染成图。",
        "files": ["说明.txt", "manifest.json"],
    }
    note = "\n".join(
        [
            "精装选配 · 图册占位",
            f"档案：{selection['id']}",
            f"项目：{project['name']}（{project['code']}）",
            f"户型：{unit['name']}",
            f"风格：{style.get('name') or '未选择'}",
            "",
            "此压缩包不是效果图成图。",
            "后续可放入：三维截图、部位材质板、客户上传的家具照片。",
            "场景生成计划接入阿里云百炼 DashScope 或火山引擎，当前未调用。",
        ]
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("说明.txt", note)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return buffer.getvalue()
