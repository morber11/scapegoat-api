from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from core.config import get_settings

_client_records: dict[str, tuple[int, float]] = {}


def reset_rate_limits() -> None:
    _client_records.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
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
