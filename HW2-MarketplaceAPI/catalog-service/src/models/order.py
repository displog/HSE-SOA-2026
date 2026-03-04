from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, Enum as SAEnum
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4, UUID


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    status: OrderStatus = Field(
        default=OrderStatus.CREATED,
        sa_column=Column(SAEnum(OrderStatus, native_enum=False), default=OrderStatus.CREATED),
    )
    promo_code_id: Optional[UUID] = Field(default=None, foreign_key="promo_codes.id")
    total_amount: Decimal = Field(default=Decimal("0"))
    discount_amount: Decimal = Field(default=Decimal("0"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="orders.id")
    product_id: UUID = Field(foreign_key="products.id")
    quantity: int = Field(ge=1, le=999)
    price_at_order: Decimal = Field()


class PromoDiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class PromoCode(SQLModel, table=True):
    __tablename__ = "promo_codes"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    code: str = Field(unique=True, max_length=20)
    discount_type: PromoDiscountType = Field(
        sa_column=Column(SAEnum(PromoDiscountType, native_enum=False)),
    )
    discount_value: Decimal = Field()
    min_order_amount: Decimal = Field()
    max_uses: int = Field(ge=0)
    current_uses: int = Field(default=0, ge=0)
    valid_from: datetime = Field()
    valid_until: datetime = Field()
    active: bool = Field(default=True)


class UserOperationType(str, Enum):
    CREATE_ORDER = "CREATE_ORDER"
    UPDATE_ORDER = "UPDATE_ORDER"


class UserOperation(SQLModel, table=True):
    __tablename__ = "user_operations"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    operation_type: UserOperationType = Field(
        sa_column=Column(SAEnum(UserOperationType, native_enum=False)),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
