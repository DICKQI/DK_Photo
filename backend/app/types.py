from __future__ import annotations

import datetime as dt

from sqlalchemy.types import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value
