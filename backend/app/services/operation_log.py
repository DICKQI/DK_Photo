from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any


OPERATION_LOGGER = "dk_photo.operation"
SENSITIVE_KEY_PARTS = ("password", "token", "secret", "authorization", "cookie")
REDACTED = "[REDACTED]"


def log_operation(
    action: str,
    *,
    category: str = "audit",
    status: str = "success",
    actor_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    message: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    level: int = logging.INFO,
) -> None:
    try:
        logging.getLogger(OPERATION_LOGGER).log(
            level,
            message or action,
            extra={
                "log_category": category,
                "operation_action": action,
                "operation_status": status,
                "actor_id": actor_id,
                "target_type": target_type,
                "target_id": target_id,
                "request_id": request_id,
                "duration_ms": duration_ms,
                "operation_metadata": redact_sensitive_metadata(metadata or {}),
            },
        )
    except Exception:
        return


def redact_sensitive_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                result[key_text] = REDACTED
            else:
                result[key_text] = redact_sensitive_metadata(item)
        return result
    if isinstance(value, list):
        return [redact_sensitive_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_metadata(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
