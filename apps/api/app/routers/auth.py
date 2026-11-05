import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import CustomerDep, Db
from app.models import Customer, OtpChallenge
from app.services.auth import create_token
from app.services.ids import new_id

router = APIRouter(prefix="/api/auth", tags=["auth"])
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class OtpRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=11)


class OtpVerify(BaseModel):
    phone: str
    code: str


def _clean_phone(phone: str) -> str:
    text = phone.strip()
    if not PHONE_RE.fullmatch(text):
        raise HTTPException(status_code=400, detail="请输入 11 位中国大陆手机号")
    return text


@router.post("/otp/request")
def request_otp(body: OtpRequest, db: Db):
    phone = _clean_phone(body.phone)
    settings = get_settings()
    challenge = OtpChallenge(
        id=new_id("otp"),
        phone=phone,
        code=settings.test_otp,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(challenge)
    return {
        "sent": True,
        "dev_code": settings.test_otp,
        "message": f"测试环境不发送短信，验证码是 {settings.test_otp}",
    }


@router.post("/otp/verify")
def verify_otp(body: OtpVerify, db: Db):
    phone = _clean_phone(body.phone)
    settings = get_settings()
    if body.code.strip() != settings.test_otp:
        raise HTTPException(status_code=400, detail="验证码不正确")
    customer = db.query(Customer).filter(Customer.phone == phone).one_or_none()
    if customer is None:
        customer = Customer(id=new_id("cus"), phone=phone, display_name=f"客户{phone[-4:]}")
        db.add(customer)
        db.flush()
    return {
        "token": create_token(sub=customer.id, role="customer"),
        "customer": {
            "id": customer.id,
            "phone": customer.phone,
            "display_name": customer.display_name,
        },
    }


@router.get("/me")
def me(customer: CustomerDep):
    return {"id": customer.id, "phone": customer.phone, "display_name": customer.display_name}
