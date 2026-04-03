from abc import ABC, abstractmethod
from decimal import Decimal
from shared.enums import AccountStatus
from shared.exceptions import AccountClosedError, InvalidOperationError
from utils.unique_id import mask_numeric_suffix, prepare_unique_id


class AbstractAccount(ABC):
    _used_account_ids: set[str] = set()

    def __init__(self, owner: str, account_id: str | None = None, status: AccountStatus = AccountStatus.ACTIVE):
        self._account_id = prepare_unique_id(
            account_id,
            used_ids=self._used_account_ids,
            label="Account ID",
            min_digits=4,
        )
        self._owner = owner
        self._balance = Decimal("0.00")
        self._status = self._validate_status(status)

    @staticmethod
    def _validate_status(status: AccountStatus) -> AccountStatus:
        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Status must be an AccountStatus enum")
        return status

    def _masked_account_id(self) -> str:
        return mask_numeric_suffix(self._account_id)

    def freeze(self) -> None:
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError()
        if self._status == AccountStatus.FROZEN:
            raise InvalidOperationError("Account is already frozen")
        self._status = AccountStatus.FROZEN

    def unfreeze(self) -> None:
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError()
        if self._status != AccountStatus.FROZEN:
            raise InvalidOperationError("Account is not frozen")
        self._status = AccountStatus.ACTIVE

    def close(self) -> None:
        if self._status == AccountStatus.CLOSED:
            raise InvalidOperationError("Account is already closed")
        self._status = AccountStatus.CLOSED

    @abstractmethod
    def deposit(self, amount): ...

    @abstractmethod
    def withdraw(self, amount): ...

    @abstractmethod
    def get_account_info(self): ...

    @abstractmethod
    def __str__(self): ...
