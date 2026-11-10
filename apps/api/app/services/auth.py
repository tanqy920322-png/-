from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException

from app.config import get_settings


def create_token(*, sub: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.access_token_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.api_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.api_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="登录已失效") from exc


def read_bearer(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    return decode_token(authorization.split(" ", 1)[1].strip())
