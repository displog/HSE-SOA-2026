from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, Session

from src.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    require_auth,
)
from src.db import get_db
from src.models.user import User, UserRole as DbUserRole
from src.schemas.generated import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    stmt = select(User).where(User.email == data.email)
    if db.exec(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "VALIDATION_ERROR", "message": "Email already registered"},
        )
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=DbUserRole(data.role.value),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    role = user.role if isinstance(user.role, DbUserRole) else DbUserRole(user.role)
    return TokenResponse(
        access_token=create_access_token(user.id, role),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    stmt = select(User).where(User.email == data.email)
    user = db.exec(stmt).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Invalid email or password"},
        )
    role = user.role if isinstance(user.role, DbUserRole) else DbUserRole(user.role)
    return TokenResponse(
        access_token=create_access_token(user.id, role),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    payload, err = decode_token(data.refresh_token)
    if err or not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "REFRESH_TOKEN_INVALID", "message": "Invalid or expired refresh token"},
        )
    from uuid import UUID
    user_id = UUID(payload["sub"])
    stmt = select(User).where(User.id == user_id)
    user = db.exec(stmt).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "REFRESH_TOKEN_INVALID", "message": "User not found"},
        )
    role = user.role if isinstance(user.role, DbUserRole) else DbUserRole(user.role)
    return TokenResponse(
        access_token=create_access_token(user.id, role),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )
