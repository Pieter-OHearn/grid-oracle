import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from api.database import settings
from api.routes.public import router as public_router
from api.services.public import PublicReadError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema changes are explicit; API startup never creates or upgrades data.
    yield


def error_response(code, message, retryable, status):
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "retryable": retryable},
        },
        headers={"Cache-Control": "no-store"},
    )


def create_app(*, legacy: bool | None = None):
    application = FastAPI(
        title="GridOracle public API", version="1.0.0", lifespan=lifespan
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept"],
    )
    application.include_router(public_router)
    # Local/operator rollback only. Public containers do not set this flag.
    if legacy if legacy is not None else os.getenv("GRIDORACLE_LEGACY_API") == "1":
        from api.routes.drivers import router as drivers_router
        from api.routes.models import router as models_router
        from api.routes.races import router as races_router

        application.include_router(races_router)
        application.include_router(models_router)
        application.include_router(drivers_router)

    @application.exception_handler(PublicReadError)
    async def public_error(request: Request, exc: PublicReadError):
        return error_response(exc.code, exc.message, exc.status >= 500, exc.status)

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return error_response(
            "api_unavailable",
            "The data service is unavailable. Please retry.",
            True,
            503,
        )

    @application.exception_handler(ValidationError)
    @application.exception_handler(ValueError)
    async def invalid_data(request: Request, exc: ValueError):
        return error_response(
            "invalid_publication",
            "Stored public data could not be verified.",
            True,
            503,
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return error_response(
            "invalid_request", "Invalid resource or query parameters.", False, 422
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(
            "not_found" if exc.status_code == 404 else "invalid_request",
            "Resource not found" if exc.status_code == 404 else "Request not allowed",
            False,
            exc.status_code,
        )

    @application.get("/health")
    def health_check():
        return {"status": "ok"}

    return application


app = create_app()
