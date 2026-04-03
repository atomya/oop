import uuid

from shared.exceptions import InvalidOperationError


def extract_digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def mask_numeric_suffix(value: str) -> str:
    return f"****{extract_digits(value)[-4:]}"


def validate_unique_id(
    raw_id,
    *,
    label: str,
    min_digits: int = 0,
    allow_int: bool = True,
) -> str:
    if isinstance(raw_id, bool):
        raise InvalidOperationError(f"{label} must be a string or integer")

    if allow_int and isinstance(raw_id, int):
        raw_id = str(raw_id)
    elif not isinstance(raw_id, str):
        raise InvalidOperationError(f"{label} must be a string")

    normalized_id = raw_id.strip()
    if not normalized_id:
        raise InvalidOperationError(f"{label} cannot be empty")

    if len(extract_digits(normalized_id)) < min_digits:
        raise InvalidOperationError(f"{label} must contain at least {min_digits} digits")

    return normalized_id


def reserve_unique_id(entity_id: str, *, used_ids: set[str], label: str) -> str:
    if entity_id in used_ids:
        raise InvalidOperationError(f"{label} must be unique")

    used_ids.add(entity_id)
    return entity_id


def generate_unique_id(
    *,
    used_ids: set[str],
    label: str,
    length: int = 8,
    min_digits: int = 0,
) -> str:
    while True:
        candidate = uuid.uuid4().hex[:length]
        if len(extract_digits(candidate)) < min_digits:
            continue

        try:
            return reserve_unique_id(candidate, used_ids=used_ids, label=label)
        except InvalidOperationError:
            continue


def prepare_unique_id(
    raw_id,
    *,
    used_ids: set[str],
    label: str,
    length: int = 8,
    min_digits: int = 0,
    allow_int: bool = True,
) -> str:
    if raw_id is None:
        return generate_unique_id(
            used_ids=used_ids,
            label=label,
            length=length,
            min_digits=min_digits,
        )

    validated_id = validate_unique_id(
        raw_id,
        label=label,
        min_digits=min_digits,
        allow_int=allow_int,
    )
    return reserve_unique_id(validated_id, used_ids=used_ids, label=label)
