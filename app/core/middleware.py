from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.logging import (
    bind_client_ip,
    bind_request_id,
    reset_client_ip,
    reset_request_id,
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs and emit concise structured request logs."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = logging.getLogger("app.request")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        request_id = request.headers.get(settings.request_id_header) or str(
            uuid.uuid4()
        )
        client_ip = self._resolve_client_ip(request)
        request_token = bind_request_id(request_id)
        ip_token = bind_client_ip(client_ip)
        start_time = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            self._log_completion(
                request=request,
                status_code=response.status_code,
                start_time=start_time,
                level="info",
                message="request completed",
                client_ip=client_ip,
            )
            response.headers[settings.request_id_header] = request_id
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                },
            )
            raise
        finally:
            reset_client_ip(ip_token)
            reset_request_id(request_token)

    def _log_completion(
        self,
        *,
        request: Request,
        status_code: int,
        start_time: float,
        level: str,
        message: str,
        client_ip: str,
    ) -> None:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_fn = getattr(self._logger, level, self._logger.info)
        log_fn(
            message,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": client_ip,
            },
        )

    def _resolve_client_ip(self, request: Request) -> str:
        """Determine the best-effort client IP."""
        if settings.trust_client_ip_header:
            header_value = request.headers.get(settings.client_ip_header)
            if header_value:
                first_ip = header_value.split(",")[0].strip()
                if first_ip:
                    return first_ip

        if request.client and request.client.host:
            return request.client.host
        return "-"
