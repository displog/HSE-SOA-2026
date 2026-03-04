"""JWT auth для API. ContextVar для передачи токена в impl."""
from contextvars import ContextVar
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth import decode_token
from src.models.user import UserRole

security = HTTPBearer(auto_error=False)

# Токен текущего запроса
_current_auth: ContextVar[Optional[dict]] = ContextVar("current_auth", default=None)


def get_current_auth() -> dict:
    """Получить токен текущего запроса (вызывать из impl)."""
    auth = _current_auth.get()
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Not authenticated"},
        )
    return auth


async def get_token_bearer_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Возвращает {'user_id': UUID, 'role': UserRole} для сгенерированных API."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Invalid or missing token"},
        )
    from uuid import UUID
    payload, err = decode_token(credentials.credentials)
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
    auth = {"user_id": UUID(payload["sub"]), "role": UserRole(payload["role"])}
    _current_auth.set(auth)
    return auth


# Алиас для генератора (bearerAuth -> get_token_bearerAuth)
get_token_bearerAuth = get_token_bearer_auth
