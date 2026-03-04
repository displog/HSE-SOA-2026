from decimal import Decimal
from sqlalchemy import Column, Enum as SAEnum
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from uuid import uuid4, UUID


class ProductStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True
    )
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    price: Decimal = Field(gt=Decimal('0.00'))
    stock: int = Field(ge=0)
    category: str = Field(max_length=100)
    status: ProductStatus = Field(
        default=ProductStatus.ACTIVE,
        sa_column=Column(SAEnum(ProductStatus, native_enum=False), index=True),
    )
    seller_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )