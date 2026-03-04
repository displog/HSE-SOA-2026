"""Реализация AuthApi — использует сгенерированный BaseAuthApi."""
from fastapi import HTTPException, status
from sqlmodel import select, Session

from openapi_server.apis.auth_api_base import BaseAuthApi
from src.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.db import SessionLocal
from src.models.user import User, UserRole as DbUserRole
from src.schemas.generated import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse


class AuthApiImpl(BaseAuthApi):
    async def register(self, register_request: RegisterRequest) -> TokenResponse:
        db = SessionLocal()
        try:
            stmt = select(User).where(User.email == register_request.email)
            if db.exec(stmt).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "VALIDATION_ERROR", "message": "Email already registered"},
                )
            user = User(
                email=register_request.email,
                password_hash=hash_password(register_request.password),
                role=DbUserRole(register_request.role.value),
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
        finally:
            db.close()

    async def login(self, login_request: LoginRequest) -> TokenResponse:
        db = SessionLocal()
        try:
            stmt = select(User).where(User.email == login_request.email)
            user = db.exec(stmt).first()
            if not user or not verify_password(login_request.password, user.password_hash):
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
        finally:
            db.close()

    async def refresh(self, refresh_request: RefreshRequest) -> TokenResponse:
        from uuid import UUID
        db = SessionLocal()
        try:
            payload, err = decode_token(refresh_request.refresh_token)
            if err or not payload or payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error_code": "REFRESH_TOKEN_INVALID", "message": "Invalid or expired refresh token"},
                )
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
        finally:
            db.close()
