from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.auth import require_role
from src.db import get_db
from src.models.order import PromoCode, PromoDiscountType
from src.models.user import UserRole
from src.schemas.generated import PromoCodeCreate, PromoCodeResponse

router = APIRouter(prefix="/promo-codes", tags=["promo-codes"])


@router.post("", response_model=PromoCodeResponse, status_code=201)
def create_promo_code(
    data: PromoCodeCreate,
    db: Session = Depends(get_db),
    current: dict = Depends(require_role(UserRole.SELLER, UserRole.ADMIN)),
):
    stmt = select(PromoCode).where(PromoCode.code == data.code)
    if db.exec(stmt).first():
        raise HTTPException(status_code=400, detail={"error_code": "VALIDATION_ERROR", "message": "Promo code already exists"})
    promo = PromoCode(
        code=data.code,
        discount_type=PromoDiscountType(data.discount_type.value),
        discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        max_uses=data.max_uses,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        active=data.active if data.active is not None else True,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return PromoCodeResponse(
        id=promo.id,
        code=promo.code,
        discount_type=promo.discount_type.value,
        discount_value=promo.discount_value,
        min_order_amount=promo.min_order_amount,
        max_uses=promo.max_uses,
        current_uses=promo.current_uses,
        valid_from=promo.valid_from,
        valid_until=promo.valid_until,
        active=promo.active,
    )
