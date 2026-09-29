"""
Structured Observability, Correlation Tracking, and Error Boundary Middleware (Phase 3)

Features:
1. End-to-End Correlation IDs: Every request receives or propagates an `X-Correlation-ID` header.
2. Sanitized Structured Logging: Logs operational metadata (method, path, status, latency_ms, correlation_id)
   while strictly omitting credentials, tokens, passwords, HMAC keys, and private health information.
3. Standardized Error Envelopes: All exceptions are transformed into consistent error responses:
   {
       "error": {
           "code": "VALIDATION_ERROR" | "AUTHENTICATION_ERROR" | "AUTHORIZATION_ERROR" | ...,
           "message": "...",
           "correlation_id": "...",
           "details": {}
       }
   }
"""

import time
import uuid
import logging
from typing import Optional, Dict, Any, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError

# Structured logger setup
logger = logging.getLogger("aegiscare.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [corr=%(correlation_id)s] %(message)s',
        defaults={"correlation_id": "none"}
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every HTTP transaction has a unique correlation ID
    and measures end-to-end request processing latency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # 1. Extract or generate Correlation ID
        incoming_corr_id = request.headers.get("X-Correlation-ID")
        if incoming_corr_id and len(incoming_corr_id.strip()) <= 64:
            correlation_id = incoming_corr_id.strip()
        else:
            correlation_id = str(uuid.uuid4())

        request.state.correlation_id = correlation_id

        # 2. Process request through downstream pipeline
        try:
            response = await call_next(request)
        except Exception as exc:
            # Fallback for unhandled internal exceptions
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"{request.method} {request.url.path} - Unhandled Error: {str(exc)} ({duration_ms}ms)",
                extra={"correlation_id": correlation_id}
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected internal error occurred. Request logged.",
                        "correlation_id": correlation_id,
                    }
                },
                headers={"X-Correlation-ID": correlation_id}
            )

        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id

        # 3. Sanitized Structured Access Log (No query parameters with tokens or PII)
        sanitized_path = request.url.path
        logger.info(
            f"{request.method} {sanitized_path} {response.status_code} - {duration_ms}ms",
            extra={"correlation_id": correlation_id}
        )

        return response


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    correlation_id: str = "none",
    details: Optional[Any] = None,
) -> JSONResponse:
    """Utility to generate consistent, safe JSON error envelopes."""
    content: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        }
    }
    if details is not None:
        content["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"X-Correlation-ID": correlation_id}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers global exception handlers on the FastAPI application."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = getattr(request.state, "correlation_id", "none")
        
        # Categorize error code based on HTTP status
        code_map = {
            400: "VALIDATION_ERROR",
            401: "AUTHENTICATION_ERROR",
            403: "AUTHORIZATION_ERROR",
            404: "NOT_FOUND_ERROR",
            409: "CONFLICT_ERROR",
            422: "UNPROCESSABLE_ENTITY",
            500: "INTERNAL_ERROR",
        }
        code = code_map.get(exc.status_code, "API_ERROR")

        return create_error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            correlation_id=correlation_id,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        correlation_id = getattr(request.state, "correlation_id", "none")
        # Sanitize error detail list
        sanitized_errors = []
        for err in exc.errors():
            sanitized_errors.append({
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            })

        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Request body or parameter validation failed.",
            correlation_id=correlation_id,
            details=sanitized_errors,
        )
