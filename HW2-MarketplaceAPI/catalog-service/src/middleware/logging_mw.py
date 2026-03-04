import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


def _get_user_id_from_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    try:
        from src.auth import decode_token
        token = auth[7:]
        payload, _ = decode_token(token)
        if payload and payload.get("type") == "access":
            return payload.get("sub")
    except Exception:
        pass
    return None


def _mask_body(body: bytes, content_type: str) -> str:
    """Mask passwords in request body."""
    if not body:
        return ""
    try:
        text = body.decode("utf-8")
        if "application/json" in content_type:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ("password", "password_hash", "refresh_token"):
                    if key in data and data[key]:
                        data[key] = "***MASKED***"
                return json.dumps(data)
        return text[:500]
    except Exception:
        return "<binary>"


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        body = b""
        if request.method in ("POST", "PUT", "DELETE"):
            body = await request.body()
            # Re-create request with body for downstream
            async def receive():
                return {"type": "http.request", "body": body}
            request = Request(request.scope, receive=receive)

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        user_id = _get_user_id_from_token(request)

        log_entry = {
            "request_id": request_id,
            "method": request.method,
            "endpoint": str(request.url.path),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if request.method in ("POST", "PUT", "DELETE") and body:
            log_entry["body"] = _mask_body(body, request.headers.get("content-type", ""))

        print(json.dumps(log_entry, ensure_ascii=False))

        response.headers["X-Request-Id"] = request_id
        return response
