from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.services.operation_log import log_operation


async def operation_request_logger(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = uuid4().hex
    start = time.perf_counter()
    path = request.url.path
    method = request.method
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - start) * 1000)
        log_operation(
            "http.request",
            category="request",
            status="error",
            request_id=request_id,
            duration_ms=duration_ms,
            target_type="http_request",
            target_id=f"{method} {path}",
            message=f"{method} {path} failed",
            metadata={"method": method, "path": path, "status_code": 500},
            level=logging.ERROR,
        )
        raise

    duration_ms = int((time.perf_counter() - start) * 1000)
    status_code = response.status_code
    level = logging.WARNING if status_code >= 400 else logging.INFO
    status = "error" if status_code >= 500 else "failure" if status_code >= 400 else "success"
    log_operation(
        "http.request",
        category="request",
        status=status,
        request_id=request_id,
        duration_ms=duration_ms,
        target_type="http_request",
        target_id=f"{method} {path}",
        message=f"{method} {path} {status_code}",
        metadata={"method": method, "path": path, "status_code": status_code},
        level=level,
    )
    response.headers["X-Request-ID"] = request_id
    return response
