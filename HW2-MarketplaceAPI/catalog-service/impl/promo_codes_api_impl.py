"""Реализация PromoCodesApi — использует сгенерированный BasePromoCodesApi."""
from fastapi import HTTPException
from sqlmodel import select, Session

from openapi_server.apis.promo_codes_api_base import BasePromoCodesApi
from openapi_server.security_api import get_current_auth
from src.db import SessionLocal
from src.models.order import PromoCode, PromoDiscountType
from src.schemas.generated import PromoCodeCreate, PromoCodeResponse


class PromoCodesApiImpl(BasePromoCodesApi):
    async def create_promo_code(
        self,
        promo_code_create: PromoCodeCreate,
        token_bearer_auth: dict = None,
        db: Session = None,
    ) -> PromoCodeResponse:
        if db is None:
            db = SessionLocal()
        token_bearer_auth = token_bearer_auth or get_current_auth()
        stmt = select(PromoCode).where(PromoCode.code == promo_code_create.code)
        if db.exec(stmt).first():
            raise HTTPException(status_code=400, detail={"error_code": "VALIDATION_ERROR", "message": "Promo code already exists"})
        promo = PromoCode(
            code=promo_code_create.code,
            discount_type=PromoDiscountType(promo_code_create.discount_type.value),
            discount_value=promo_code_create.discount_value,
            min_order_amount=promo_code_create.min_order_amount,
            max_uses=promo_code_create.max_uses,
            valid_from=promo_code_create.valid_from,
            valid_until=promo_code_create.valid_until,
            active=promo_code_create.active if promo_code_create.active is not None else True,
        )
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return PromoCodeResponse(
            id=promo.id, code=promo.code, discount_type=promo.discount_type.value,
            discount_value=promo.discount_value, min_order_amount=promo.min_order_amount,
            max_uses=promo.max_uses, current_uses=promo.current_uses,
            valid_from=promo.valid_from, valid_until=promo.valid_until, active=promo.active,
        )
