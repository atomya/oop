from datetime import datetime


def format_timestamp(timestamp: datetime | None) -> str | None:
    if timestamp is None:
        return None
    return timestamp.isoformat(timespec="seconds")
