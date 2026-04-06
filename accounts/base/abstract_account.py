from abc import ABC, abstractmethod
from decimal import Decimal
from shared.enums import AccountStatus
from shared.exceptions import AccountClosedError, InvalidOperationError
from utils.unique_id import mask_numeric_suffix, prepare_unique_id, reserve_unique_id
from utils.validation import require_enum


class AbstractAccount(ABC):
    _used_account_ids: set[str] = set()

    def __init__(self, owner: str, account_id: str | None = None, status: AccountStatus = AccountStatus.ACTIVE):
        validated_status = require_enum(status, AccountStatus, "Status", article="an")
        prepared_account_id = prepare_unique_id(
            account_id,
            used_ids=self._used_account_ids,
            label="Account ID",
            min_digits=4,
        )

        self._owner = owner
        self._balance = Decimal("0.00")
        self._status = validated_status
        self._account_id = prepared_account_id
        self._account_id_reserved = False

    def _reserve_account_id(self) -> None:
        if self._account_id_reserved:
            return

        reserve_unique_id(
            self._account_id,
            used_ids=self._used_account_ids,
            label="Account ID",
        )
        self._account_id_reserved = True

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
