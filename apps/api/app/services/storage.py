from pathlib import Path


class LocalObjectStorage:
    """Filesystem stand-in for OSS / S3. Keys are relative paths under the root."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError("非法存储键")
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise ValueError("非法存储键")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_name(path.name + ".content-type").write_text(content_type, encoding="utf-8")
        return key

    def get(self, key: str) -> tuple[bytes, str]:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        meta = path.with_name(path.name + ".content-type")
        content_type = meta.read_text(encoding="utf-8") if meta.is_file() else "application/octet-stream"
        return path.read_bytes(), content_type.strip()

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except ValueError:
            return False


_storage: LocalObjectStorage | None = None


def get_storage() -> LocalObjectStorage:
    global _storage
    if _storage is None:
        from app.config import get_settings

        root = Path(get_settings().storage_dir)
        if not root.is_absolute():
            root = Path.cwd() / root
        _storage = LocalObjectStorage(root)
    return _storage
