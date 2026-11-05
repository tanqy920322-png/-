import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAR = ROOT / "var"
VAR.mkdir(exist_ok=True)
DB_PATH = VAR / "pytest.db"
STORAGE = VAR / "pytest-storage"
if DB_PATH.exists():
    DB_PATH.unlink()
if STORAGE.exists():
    shutil.rmtree(STORAGE)
STORAGE.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_PATH}"
os.environ["REDIS_URL"] = ""
os.environ["STORAGE_DIR"] = str(STORAGE)
os.environ["API_SECRET"] = "test-secret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "demo1234"
os.environ["TEST_OTP"] = "123456"
os.environ["AUTO_SEED"] = "true"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
