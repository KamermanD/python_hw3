from typing import Optional
from datetime import datetime, timezone


def localize_datetime(timestamp: Optional[datetime]) -> Optional[datetime]:
    if timestamp and timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp