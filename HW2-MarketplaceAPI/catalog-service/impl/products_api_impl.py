"""Реализация ProductsApi — использует сгенерированный BaseProductsApi."""
from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import select, Session, func

from openapi_server.apis.products_api_base import BaseProductsApi
from openapi_server.security_api import get_current_auth
from src.db import SessionLocal
from src.models.product import Product, ProductStatus
from src.schemas.generated import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)


def _error(status_code: int, error_code: str, message: str, details: Optional[dict] = None):
    raise HTTPException(status_code=status_code, detail={"error_code": error_code, "message": message, "details": details})


class ProductsApiImpl(BaseProductsApi):
    async def create_product(
        self,
        product_create: ProductCreate,
        token_bearer_auth: dict = None,
        db: Session = None,
    ) -> ProductResponse:
        if db is None:
            db = SessionLocal()
        token_bearer_auth = token_bearer_auth or get_current_auth()
        if token_bearer_auth["role"].value not in ("SELLER", "ADMIN"):
            _error(403, "ACCESS_DENIED", "Insufficient permissions")
        if product_create.price <= Decimal("0"):
            _error(400, "VALIDATION_ERROR", "Price must be greater than 0")
        product_data = product_create.model_dump()
        product_data["status"] = product_create.status.value
        product_data["seller_id"] = token_bearer_auth["user_id"] if token_bearer_auth["role"].value == "SELLER" else None
        db_product = Product(**product_data)
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return ProductResponse.model_validate(db_product, from_attributes=True)

    async def list_products(
        self,
        page: int = 0,
        size: int = 20,
        status: Optional[str] = None,
        category: Optional[str] = None,
        token_bearer_auth: dict = None,
        db: Session = None,
    ) -> ProductListResponse:
        if db is None:
            db = SessionLocal()
        token_bearer_auth = token_bearer_auth or get_current_auth()
        query = select(Product)
        if status:
            query = query.where(Product.status == status)
        if category:
            query = query.where(Product.category == category)
        count_query = select(func.count(Product.id))
        if query.whereclause is not None:
            count_query = count_query.where(query.whereclause)
        total = db.exec(count_query).one()
        offset = page * size
        paged_query = query.offset(offset).limit(size).order_by(Product.created_at.desc())
        products = db.exec(paged_query).all()
        return ProductListResponse(
            items=[ProductResponse.model_validate(p, from_attributes=True) for p in products],
            totalElements=total,
            page=page,
            size=size,
        )

    async def get_product(
        self,
        id: str,
        token_bearer_auth: dict = None,
        db: Session = None,
    ) -> ProductResponse:
        if db is None:
            db = SessionLocal()
        token_bearer_auth = token_bearer_auth or get_current_auth()
        try:
            uuid_id = id if isinstance(id, UUID) else UUID(str(id))
        except (ValueError, TypeError):
            _error(400, "VALIDATION_ERROR", "Invalid UUID format")
        stmt = select(Product).where(Product.id == uuid_id)
        product = db.exec(stmt).first()
        if not product:
            _error(404, "PRODUCT_NOT_FOUND", f"Product with id {uuid_id} not found")
        return ProductResponse.model_validate(product, from_attributes=True)

    async def update_product(
        self,
        id: str,
        product_update: ProductUpdate,
        token_bearer_auth: dict = None,
        db: Session = None,
    ) -> ProductResponse:
        if db is None:
            db = SessionLocal()
        token_bearer_auth = token_bearer_auth or get_current_auth()
        if token_bearer_auth["role"].value not in ("SELLER", "ADMIN"):
            _error(403, "ACCESS_DENIED", "Insufficient permissions")
        try:
            uuid_id = id if isinstance(id, UUID) else UUID(str(id))
        except (ValueError, TypeError):
            _error(400, "VALIDATION_ERROR", "Invalid UUID format")
        stmt = select(Product).where(Product.id == uuid_id)
        db_product = db.exec(stmt).first()
        if not db_product:
            _error(404, "PRODUCT_NOT_FOUND", f"Product with id {uuid_id} not found")
        if token_bearer_auth["role"].value == "SELLER" and db_product.seller_id != token_bearer_auth["user_id"]:
            _error(403, "ACCESS_DENIED", "You can only update your own products")
        # Генератор передаёт ProductCreate (body), не ProductUpdate; ProductUpdate = RootModel[ProductCreate]
        src = getattr(product_update, "root", product_update)
        update_data = src.model_dump(exclude_unset=True)
        if "status" in update_data:
            raw = update_data["status"]
            update_data["status"] = ProductStatus(getattr(raw, "value", raw))
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db_product.updated_at = datetime.now(timezone.utc)
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return ProductResponse.model_validate(db_product, from_attributes=True)

    async def delete_product(
        self,
        id: str,
        token_bearer_auth: dict = None,
        db: Session = None,
    ) -> None:
        if db is None:
            db = SessionLocal()
        token_bearer_auth = token_bearer_auth or get_current_auth()
        if token_bearer_auth["role"].value not in ("SELLER", "ADMIN"):
            _error(403, "ACCESS_DENIED", "Insufficient permissions")
        try:
            uuid_id = id if isinstance(id, UUID) else UUID(str(id))
        except (ValueError, TypeError):
            _error(400, "VALIDATION_ERROR", "Invalid UUID format")
        stmt = select(Product).where(Product.id == uuid_id)
        db_product = db.exec(stmt).first()
        if not db_product:
            _error(404, "PRODUCT_NOT_FOUND", f"Product with id {uuid_id} not found")
        if token_bearer_auth["role"].value == "SELLER" and db_product.seller_id != token_bearer_auth["user_id"]:
            _error(403, "ACCESS_DENIED", "You can only delete your own products")
        if db_product.status == ProductStatus.ARCHIVED.value:
            return None
        db_product.status = ProductStatus.ARCHIVED.value
        db_product.updated_at = datetime.now(timezone.utc)
        db.add(db_product)
        db.commit()
        return None
