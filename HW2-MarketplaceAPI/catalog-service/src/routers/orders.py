import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, Session

from src.auth import require_role
from src.db import get_db
from src.models.order import Order, OrderItem, OrderStatus, UserOperation, UserOperationType
from src.models.product import Product, ProductStatus
from src.models.user import UserRole
from src.models.order import PromoCode, PromoDiscountType
from src.schemas.generated import OrderCreate, OrderUpdate, OrderResponse, OrderItemResponse

ORDER_LIMIT_MINUTES = int(os.getenv("ORDER_LIMIT_MINUTES", "5"))

router = APIRouter(prefix="/orders", tags=["orders"])


def _check_order_rate_limit(db: Session, user_id: UUID, op_type: UserOperationType) -> None:
    stmt = (
        select(UserOperation)
        .where(
            UserOperation.user_id == user_id,
            UserOperation.operation_type == op_type,
        )
        .order_by(UserOperation.created_at.desc())
        .limit(1)
    )
    last = db.exec(stmt).first()
    if last and (datetime.now(timezone.utc) - last.created_at) < timedelta(minutes=ORDER_LIMIT_MINUTES):
        raise HTTPException(
            status_code=429,
            detail={"error_code": "ORDER_LIMIT_EXCEEDED", "message": "Order rate limit exceeded"},
        )


def _check_active_orders(db: Session, user_id: UUID) -> None:
    stmt = select(Order).where(
        Order.user_id == user_id,
        Order.status.in_([OrderStatus.CREATED, OrderStatus.PAYMENT_PENDING]),
    )
    if db.exec(stmt).first():
        raise HTTPException(
            status_code=409,
            detail={"error_code": "ORDER_HAS_ACTIVE", "message": "User already has an active order"},
        )


def _apply_promo(
    db: Session,
    code: str,
    total_amount: Decimal,
) -> tuple[Decimal, Decimal, Optional[UUID]]:
    stmt = select(PromoCode).where(PromoCode.code == code)
    promo = db.exec(stmt).first()
    if not promo:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "PROMO_CODE_INVALID", "message": "Promo code not found or invalid"},
        )
    now = datetime.now(timezone.utc)
    if not promo.active or promo.current_uses >= promo.max_uses or now < promo.valid_from or now > promo.valid_until:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "PROMO_CODE_INVALID", "message": "Promo code expired or inactive"},
        )
    if total_amount < promo.min_order_amount:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "PROMO_CODE_MIN_AMOUNT", "message": "Order amount below minimum for promo"},
        )
    if promo.discount_type == PromoDiscountType.PERCENTAGE:
        discount = total_amount * promo.discount_value / 100
        discount = min(discount, total_amount * Decimal("0.70"))
    else:
        discount = min(promo.discount_value, total_amount)
    return total_amount - discount, discount, promo.id


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current: dict = Depends(require_role(UserRole.USER, UserRole.ADMIN)),
):
    if current["role"] == UserRole.SELLER:
        raise HTTPException(status_code=403, detail={"error_code": "ACCESS_DENIED", "message": "Sellers cannot create orders"})

    _check_order_rate_limit(db, current["user_id"], UserOperationType.CREATE_ORDER)
    _check_active_orders(db, current["user_id"])

    qty_by_product: dict[UUID, int] = defaultdict(int)
    for item in data.items:
        qty_by_product[item.product_id] += item.quantity

    products_map: dict[UUID, Product] = {}
    insufficient: list[dict] = []
    for product_id, total_qty in qty_by_product.items():
        stmt = select(Product).where(Product.id == product_id)
        prod = db.exec(stmt).first()
        if not prod:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": f"Product {product_id} not found"},
            )
        if prod.status != ProductStatus.ACTIVE.value:
            raise HTTPException(
                status_code=409,
                detail={"error_code": "PRODUCT_INACTIVE", "message": f"Product {product_id} is inactive"},
            )
        if prod.stock < total_qty:
            insufficient.append({"product_id": str(product_id), "requested": total_qty, "available": prod.stock})
        products_map[product_id] = prod
    if insufficient:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "INSUFFICIENT_STOCK", "message": "Insufficient stock", "details": {"items": insufficient}},
        )

    total = Decimal("0")
    order_items_data = []
    for item in data.items:
        prod = products_map[item.product_id]
        price = prod.price
        total += price * item.quantity
        order_items_data.append((item.product_id, item.quantity, price))

    discount_amount = Decimal("0")
    promo_code_id = None
    if data.promo_code:
        total, discount_amount, promo_code_id = _apply_promo(db, data.promo_code, total)
        stmt = select(PromoCode).where(PromoCode.code == data.promo_code)
        promo = db.exec(stmt).first()
        promo.current_uses += 1
        db.add(promo)

    order = Order(
        user_id=current["user_id"],
        status=OrderStatus.CREATED,
        promo_code_id=promo_code_id,
        total_amount=total,
        discount_amount=discount_amount,
    )
    db.add(order)
    db.flush()

    for product_id, qty, price in order_items_data:
        oi = OrderItem(order_id=order.id, product_id=product_id, quantity=qty, price_at_order=price)
        db.add(oi)
        prod = products_map[product_id]
        prod.stock -= qty
        db.add(prod)

    op = UserOperation(user_id=current["user_id"], operation_type=UserOperationType.CREATE_ORDER)
    db.add(op)
    db.commit()
    db.refresh(order)

    items = db.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        total_amount=order.total_amount,
        discount_amount=order.discount_amount,
        items=[OrderItemResponse(product_id=oi.product_id, quantity=oi.quantity, price_at_order=oi.price_at_order) for oi in items],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current: dict = Depends(require_role(UserRole.USER, UserRole.ADMIN)),
):
    if current["role"] == UserRole.SELLER:
        raise HTTPException(status_code=403, detail={"error_code": "ACCESS_DENIED", "message": "Sellers cannot view orders"})
    stmt = select(Order).where(Order.id == order_id)
    order = db.exec(stmt).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error_code": "ORDER_NOT_FOUND", "message": "Order not found"})
    if current["role"] == UserRole.USER and order.user_id != current["user_id"]:
        raise HTTPException(status_code=403, detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Order belongs to another user"})
    items = db.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        total_amount=order.total_amount,
        discount_amount=order.discount_amount,
        items=[OrderItemResponse(product_id=oi.product_id, quantity=oi.quantity, price_at_order=oi.price_at_order) for oi in items],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: UUID,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current: dict = Depends(require_role(UserRole.USER, UserRole.ADMIN)),
):
    if current["role"] == UserRole.SELLER:
        raise HTTPException(status_code=403, detail={"error_code": "ACCESS_DENIED", "message": "Sellers cannot update orders"})
    stmt = select(Order).where(Order.id == order_id)
    order = db.exec(stmt).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error_code": "ORDER_NOT_FOUND", "message": "Order not found"})
    if current["role"] == UserRole.USER and order.user_id != current["user_id"]:
        raise HTTPException(status_code=403, detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Order belongs to another user"})
    if order.status != OrderStatus.CREATED:
        raise HTTPException(status_code=409, detail={"error_code": "INVALID_STATE_TRANSITION", "message": "Order can only be updated in CREATED state"})

    _check_order_rate_limit(db, current["user_id"], UserOperationType.UPDATE_ORDER)

    old_items = db.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    for oi in old_items:
        stmt = select(Product).where(Product.id == oi.product_id)
        prod = db.exec(stmt).first()
        if prod:
            prod.stock += oi.quantity
            db.add(prod)
    for oi in old_items:
        db.delete(oi)

    qty_by_product: dict[UUID, int] = defaultdict(int)
    for item in data.items:
        qty_by_product[item.product_id] += item.quantity

    products_map: dict[UUID, Product] = {}
    insufficient: list[dict] = []
    for product_id, total_qty in qty_by_product.items():
        stmt = select(Product).where(Product.id == product_id)
        prod = db.exec(stmt).first()
        if not prod:
            raise HTTPException(status_code=404, detail={"error_code": "PRODUCT_NOT_FOUND", "message": f"Product {product_id} not found"})
        if prod.status != ProductStatus.ACTIVE.value:
            raise HTTPException(status_code=409, detail={"error_code": "PRODUCT_INACTIVE", "message": f"Product {product_id} is inactive"})
        if prod.stock < total_qty:
            insufficient.append({"product_id": str(product_id), "requested": total_qty, "available": prod.stock})
        products_map[product_id] = prod
    if insufficient:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "INSUFFICIENT_STOCK", "message": "Insufficient stock", "details": {"items": insufficient}},
        )

    total = Decimal("0")
    for item in data.items:
        prod = products_map[item.product_id]
        total += prod.price * item.quantity
        oi = OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity, price_at_order=prod.price)
        db.add(oi)
        prod.stock -= item.quantity
        db.add(prod)

    discount_amount = Decimal("0")
    if order.promo_code_id:
        stmt = select(PromoCode).where(PromoCode.id == order.promo_code_id)
        promo = db.exec(stmt).first()
        now = datetime.now(timezone.utc)
        valid = promo and promo.active and promo.current_uses < promo.max_uses and now >= promo.valid_from and now <= promo.valid_until
        if valid and total >= promo.min_order_amount:
            if promo.discount_type == PromoDiscountType.PERCENTAGE:
                discount_amount = min(total * promo.discount_value / 100, total * Decimal("0.70"))
            else:
                discount_amount = min(promo.discount_value, total)
            total -= discount_amount
        else:
            if promo:
                promo.current_uses -= 1
                db.add(promo)
            order.promo_code_id = None

    order.total_amount = total
    order.discount_amount = discount_amount
    order.updated_at = datetime.now(timezone.utc)
    db.add(order)

    op = UserOperation(user_id=current["user_id"], operation_type=UserOperationType.UPDATE_ORDER)
    db.add(op)
    db.commit()
    db.refresh(order)

    items = db.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        total_amount=order.total_amount,
        discount_amount=order.discount_amount,
        items=[OrderItemResponse(product_id=oi.product_id, quantity=oi.quantity, price_at_order=oi.price_at_order) for oi in items],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.post("/{order_id}/cancel", status_code=204)
def cancel_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current: dict = Depends(require_role(UserRole.USER, UserRole.ADMIN)),
):
    if current["role"] == UserRole.SELLER:
        raise HTTPException(status_code=403, detail={"error_code": "ACCESS_DENIED", "message": "Sellers cannot cancel orders"})
    stmt = select(Order).where(Order.id == order_id)
    order = db.exec(stmt).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error_code": "ORDER_NOT_FOUND", "message": "Order not found"})
    if current["role"] == UserRole.USER and order.user_id != current["user_id"]:
        raise HTTPException(status_code=403, detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Order belongs to another user"})
    if order.status not in (OrderStatus.CREATED, OrderStatus.PAYMENT_PENDING):
        raise HTTPException(status_code=409, detail={"error_code": "INVALID_STATE_TRANSITION", "message": "Order can only be canceled in CREATED or PAYMENT_PENDING state"})

    items = db.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    for oi in items:
        stmt = select(Product).where(Product.id == oi.product_id)
        prod = db.exec(stmt).first()
        if prod:
            prod.stock += oi.quantity
            db.add(prod)
    if order.promo_code_id:
        stmt = select(PromoCode).where(PromoCode.id == order.promo_code_id)
        promo = db.exec(stmt).first()
        if promo:
            promo.current_uses -= 1
            db.add(promo)
    order.status = OrderStatus.CANCELED
    order.updated_at = datetime.now(timezone.utc)
    db.add(order)
    db.commit()
