from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings

_client_records: dict[str, tuple[int, float]] = {}


def reset_rate_limits() -> None:
    _client_records.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Request:
        settings = get_settings()
        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds

        client_ip = request.client.host if request.client else "unknown"

        now = time.monotonic()
        count, start = _client_records.get(client_ip, (0, now))

        if now - start >= window:
            count = 0
            start = now

        if count >= limit:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        _client_records[client_ip] = (count + 1, start)
        response = await call_next(request)

        return response


class PrivateNetworkMiddleware(BaseHTTPMiddleware):
    """handle new access control request private network header
    """
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        if "access-control-request-private-network" in request.headers:
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response
