from abc import ABC, abstractmethod
import uuid
from decimal import Decimal
from enums import AccountStatus
from exceptions import InvalidOperationError


class AbstractAccount(ABC):
    _used_account_ids: set[str] = set()

    def __init__(self, owner: str, account_id: str | None = None, status: AccountStatus = AccountStatus.ACTIVE):
        self._account_id = self._prepare_account_id(account_id)
        self._owner = owner
        self._balance = Decimal("0.00")
        self._status = self._validate_status(status)

    @staticmethod
    def _validate_status(status: AccountStatus) -> AccountStatus:
        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Status must be an AccountStatus enum")
        return status

    @classmethod
    def _prepare_account_id(cls, account_id) -> str:
        if account_id is None:
            return cls._generate_unique_account_id()

        validated_account_id = cls._validate_account_id(account_id)
        return cls._reserve_account_id(validated_account_id)

    @classmethod
    def _generate_unique_account_id(cls) -> str:
        while True:
            candidate = uuid.uuid4().hex[:8]
            if len(cls._extract_digits(candidate)) < 4:
                continue

            try:
                return cls._reserve_account_id(candidate)
            except InvalidOperationError:
                continue

    @classmethod
    def _reserve_account_id(cls, account_id: str) -> str:
        if account_id in cls._used_account_ids:
            raise InvalidOperationError("Account ID must be unique")

        cls._used_account_ids.add(account_id)
        return account_id

    @staticmethod
    def _validate_account_id(account_id) -> str:
        if isinstance(account_id, bool):
            raise InvalidOperationError("Account ID must be a string or integer")

        if isinstance(account_id, int):
            account_id = str(account_id)
        elif not isinstance(account_id, str):
            raise InvalidOperationError("Account ID must be a string or integer")

        normalized_account_id = account_id.strip()
        if not normalized_account_id:
            raise InvalidOperationError("Account ID cannot be empty")

        if len(AbstractAccount._extract_digits(normalized_account_id)) < 4:
            raise InvalidOperationError("Account ID must contain at least 4 digits")

        return normalized_account_id

    @staticmethod
    def _extract_digits(value: str) -> str:
        return "".join(char for char in value if char.isdigit())

    def _masked_account_id(self) -> str:
        return f"****{self._extract_digits(self._account_id)[-4:]}"

    @abstractmethod
    def deposit(self, amount): ...

    @abstractmethod
    def withdraw(self, amount): ...

    @abstractmethod
    def get_account_info(self): ...

    @abstractmethod
    def __str__(self): ...
