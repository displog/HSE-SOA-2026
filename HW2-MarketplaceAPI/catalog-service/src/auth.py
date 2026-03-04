import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from src.models.user import UserRole

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: UUID, role: UserRole) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role.value, "exp": expire, "type": "access"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> tuple[Optional[dict], Optional[str]]:
    """Returns (payload, error_code). error_code is TOKEN_EXPIRED or TOKEN_INVALID."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]), None
    except ExpiredSignatureError:
        return None, "TOKEN_EXPIRED"
    except JWTError:
        return None, "TOKEN_INVALID"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    if not credentials:
        return None
    token = credentials.credentials
    payload, err = decode_token(token)
    if err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": err, "message": "Token expired" if err == "TOKEN_EXPIRED" else "Invalid token"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Invalid token"},
        )
    return {"user_id": UUID(payload["sub"]), "role": UserRole(payload["role"])}


async def require_auth(current: Optional[dict] = Depends(get_current_user)) -> dict:
    if not current:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Invalid or missing token"},
        )
    return current


def require_role(*allowed: UserRole):
    async def _check(current: dict = Depends(require_auth)) -> dict:
        if current["role"] not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCESS_DENIED", "message": "Insufficient permissions"},
            )
        return current
    return _check
