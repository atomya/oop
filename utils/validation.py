from datetime import datetime
from decimal import Decimal

from shared.exceptions import InvalidOperationError


def require_non_empty_string(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidOperationError(f"{label} must be a non-empty string")
    return value.strip()


def require_enum(value, enum_cls, label: str, *, allow_none: bool = False, article: str = "a"):
    if value is None and allow_none:
        return None
    if not isinstance(value, enum_cls):
        raise InvalidOperationError(f"{label} must be {article} {enum_cls.__name__} enum")
    return value


def require_datetime(value, label: str, *, allow_none: bool = False) -> datetime | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, datetime):
        raise InvalidOperationError(f"{label} must be a datetime")
    return value


def require_positive_decimal(value, label: str) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperationError(f"{label} cannot be boolean")
    if not isinstance(value, (int, float, Decimal)):
        raise InvalidOperationError(f"{label} must be numeric")

    decimal_value = Decimal(str(value))
    if decimal_value <= 0:
        raise InvalidOperationError(f"{label} must be positive")
    return decimal_value


def require_non_negative_decimal(value, label: str) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperationError(f"{label} cannot be boolean")
    if not isinstance(value, (int, float, Decimal)):
        raise InvalidOperationError(f"{label} must be numeric")

    decimal_value = Decimal(str(value))
    if decimal_value < 0:
        raise InvalidOperationError(f"{label} cannot be negative")
    return decimal_value


def require_non_negative_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidOperationError(f"{label} must be an integer")
    if value < 0:
        raise InvalidOperationError(f"{label} cannot be negative")
    return value


def require_positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidOperationError(f"{label} must be an integer")
    if value <= 0:
        raise InvalidOperationError(f"{label} must be positive")
    return value
