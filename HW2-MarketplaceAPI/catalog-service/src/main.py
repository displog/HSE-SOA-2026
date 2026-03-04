"""Marketplace API. Роутеры из openapi_server, реализация в impl."""
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.middleware.logging_mw import LoggingMiddleware

from openapi_server.apis.auth_api import router as auth_router
from openapi_server.apis.products_api import router as products_router
from openapi_server.apis.orders_api import router as orders_router
from openapi_server.apis.promo_codes_api import router as promo_codes_router

app = FastAPI(
    title="Marketplace Catalog API",
    description="API для управления товарами и заказами (сгенерировано из OpenAPI)",
    version="1.0.0",
)

app.add_middleware(LoggingMiddleware)

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(promo_codes_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"] if x != "body")
        errors.append({"field": loc, "message": err["msg"]})
    return JSONResponse(
        status_code=400,
        content={"error_code": "VALIDATION_ERROR", "message": "Ошибка валидации входных данных", "details": {"errors": errors}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    body = exc.detail
    if isinstance(body, dict) and "error_code" in body:
        return JSONResponse(status_code=exc.status_code, content=body)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": "UNKNOWN_ERROR", "message": str(body), "details": None},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """500 handler."""
    import traceback
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": str(exc),
            "details": {"traceback": traceback.format_exc()},
        },
    )
