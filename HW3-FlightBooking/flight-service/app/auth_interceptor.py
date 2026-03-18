import logging
import os

import jwt
import grpc

logger = logging.getLogger(__name__)


def _get_secret() -> str:
    return os.environ.get("FLIGHT_JWT_SECRET", "secret")


def _validate_token(token: str) -> bool:
    try:
        jwt.decode(token, _get_secret(), algorithms=["HS256"])
        return True
    except jwt.InvalidTokenError:
        return False


def _abort_handler(context_msg: str):
    def abort(request, context):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, context_msg)
    return grpc.unary_unary_rpc_method_handler(abort)


class AuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        auth = metadata.get("authorization") or metadata.get("x-authorization")
        if not auth or not auth.startswith("Bearer "):
            return _abort_handler("Missing or invalid authorization")
        token = auth[7:].strip()
        if not _validate_token(token):
            return _abort_handler("Invalid token")
        return continuation(handler_call_details)
