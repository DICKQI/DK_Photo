from __future__ import annotations

from datetime import datetime, timedelta, timezone


APP_TIME_ZONE_NAME = "Asia/Shanghai"
APP_TIME_ZONE = timezone(timedelta(hours=8), name="UTC+08:00")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def assume_app_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIME_ZONE)
    return value.astimezone(APP_TIME_ZONE)


def format_app_timestamp(epoch_seconds: float, milliseconds: float = 0.0) -> str:
    text = datetime.fromtimestamp(epoch_seconds, tz=APP_TIME_ZONE).strftime("%Y-%m-%d %H:%M:%S")
    return f"{text},{milliseconds:03.0f}"
