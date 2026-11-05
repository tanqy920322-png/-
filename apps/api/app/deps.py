from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer
from app.services.auth import read_bearer

Db = Annotated[Session, Depends(get_db)]


def require_customer(
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> Customer:
    payload = read_bearer(authorization)
    if payload.get("role") != "customer":
        raise HTTPException(status_code=401, detail="请先登录")
    customer = db.get(Customer, payload.get("sub"))
    if customer is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    return customer


def require_admin(authorization: Annotated[str | None, Header()] = None) -> dict:
    payload = read_bearer(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="请先登录管理后台")
    return payload


def require_actor(authorization: Annotated[str | None, Header()] = None) -> dict:
    payload = read_bearer(authorization)
    if payload.get("role") not in {"admin", "customer"}:
        raise HTTPException(status_code=401, detail="请先登录")
    return payload


CustomerDep = Annotated[Customer, Depends(require_customer)]
AdminDep = Annotated[dict, Depends(require_admin)]
ActorDep = Annotated[dict, Depends(require_actor)]
