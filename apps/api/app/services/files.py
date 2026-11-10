import re
from pathlib import Path
from urllib.parse import quote

CONTENT_TYPES = {
    ".dwg": "application/acad",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".csv": "text/csv; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
}


def safe_filename(name: str) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[\x00-\x1f\\/]+", "_", base).strip(" .")
    return (base or "file")[:180]


def content_type_for(filename: str, fallback: str = "application/octet-stream") -> str:
    return CONTENT_TYPES.get(Path(filename).suffix.lower(), fallback)


def attachment_headers(filename: str, fallback: str = "download") -> dict[str, str]:
    return {
        "Content-Disposition": f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
    }
