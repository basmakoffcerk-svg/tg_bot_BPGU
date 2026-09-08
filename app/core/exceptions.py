"""
RFC 7807 Problem Exception definitions, types catalog, and FastAPI exception handlers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("starosta.exceptions")


class ProblemType:
    BLANK = "about:blank"
    UNAUTHORIZED = "https://errors.starosta.app/unauthorized"
    TOKEN_EXPIRED = "https://errors.starosta.app/token-expired"
    ACCOUNT_PENDING = "https://errors.starosta.app/account-pending"
    ACCOUNT_BLOCKED = "https://errors.starosta.app/account-blocked"
    FORBIDDEN_ROLE = "https://errors.starosta.app/forbidden-role"
    USER_NOT_REGISTERED = "https://errors.starosta.app/user-not-registered"
    NOT_FOUND = "https://errors.starosta.app/not-found"
    OUT_OF_BOUNDS = "https://errors.starosta.app/out-of-bounds"
    INACCURATE_GPS = "https://errors.starosta.app/inaccurate-gps"
    CHECKIN_WINDOW_CLOSED = "https://errors.starosta.app/checkin-window-closed"
    PAIR_LOCKED = "https://errors.starosta.app/pair-locked"
    ALREADY_CHECKED_IN = "https://errors.starosta.app/already-checked-in"
    CLOCK_SKEW = "https://errors.starosta.app/clock-skew"
    VALIDATION_ERROR = "https://errors.starosta.app/validation-error"
    INTERNAL_ERROR = "https://errors.starosta.app/internal-error"


class ProblemException(HTTPException):
    """
    HTTP Exception carrying RFC 7807 metadata.
    """
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: Optional[str] = None,
        type_: str = ProblemType.BLANK,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.title = title
        self.type_ = type_
        self.data = data


def setup_exception_handlers(app: FastAPI) -> None:
    """Register RFC 7807 problem details handlers across all exception types."""

    @app.exception_handler(ProblemException)
    async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
        content: Dict[str, Any] = {
            "type": exc.type_,
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": request.url.path,
        }
        if exc.data:
            content["data"] = exc.data
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            media_type="application/problem+json",
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        title = "Ошибка запроса"
        type_ = ProblemType.BLANK
        data = None

        if exc.status_code == 401:
            title = "Ошибка аутентификации"
            type_ = ProblemType.UNAUTHORIZED
        elif exc.status_code == 403:
            title = "Доступ запрещен"
            type_ = ProblemType.FORBIDDEN_ROLE
        elif exc.status_code == 404:
            title = "Ресурс не найден"
            type_ = ProblemType.NOT_FOUND
        elif exc.status_code == 400:
            title = "Неверный запрос"

        detail_text = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        if isinstance(exc.detail, dict):
            type_ = exc.detail.get("type", type_)
            title = exc.detail.get("title", title)
            detail_text = exc.detail.get("detail", detail_text)
            data = exc.detail.get("data")

        content: Dict[str, Any] = {
            "type": type_,
            "title": title,
            "status": exc.status_code,
            "detail": detail_text,
            "instance": request.url.path,
        }
        if data:
            content["data"] = data

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            media_type="application/problem+json",
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        formatted_errors: List[Dict[str, Any]] = []
        for error in exc.errors():
            loc = " -> ".join(str(item) for item in error.get("loc", []))
            formatted_errors.append({
                "loc": loc,
                "msg": str(error.get("msg")),
                "type": str(error.get("type")),
            })

        content: Dict[str, Any] = {
            "type": ProblemType.VALIDATION_ERROR,
            "title": "Ошибка валидации параметров запроса",
            "status": 422,
            "detail": "Один или несколько переданных параметров не соответствуют схеме API.",
            "instance": request.url.path,
            "invalid_params": formatted_errors,
        }
        return JSONResponse(
            status_code=422,
            content=content,
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception on %s: %s", request.url.path, exc)
        content: Dict[str, Any] = {
            "type": ProblemType.INTERNAL_ERROR,
            "title": "Внутренняя ошибка сервера",
            "status": 500,
            "detail": "Произошла непредвиденная ошибка на стороне сервера. Повторите попытку позже.",
            "instance": request.url.path,
        }
        return JSONResponse(
            status_code=500,
            content=content,
            media_type="application/problem+json",
        )
