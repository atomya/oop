import logging
from accounts.abstract import AbstractAccount
from enums import Currency, AccountStatus
from exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
    InsufficientFundsError,
)

logger = logging.getLogger(__name__)


class BankAccount(AbstractAccount):

    def __init__(self, owner, currency: Currency, account_id=None, status=AccountStatus.ACTIVE):
        super().__init__(owner, account_id)
        self._currency = currency
        self._status = status

    def _validate_amount(self, amount):
        if not isinstance(amount, (int, float)):
            raise InvalidOperationError
        if amount <= 0:
            raise InvalidOperationError

    def _check_status(self):
        if self._status == AccountStatus.FROZEN:
            raise AccountFrozenError
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError

    def deposit(self, amount):
        self._validate_amount(amount)
        self._check_status()
        self._balance += amount

        logger.info("deposit", extra={"id": self._account_id, "amount": amount})

    def withdraw(self, amount):
        self._validate_amount(amount)
        self._check_status()

        if amount > self._balance:
            raise InsufficientFundsError

        self._balance -= amount

        logger.info("withdraw", extra={"id": self._account_id, "amount": amount})

    def get_account_info(self):
        return {
            "id": self._account_id,
            "owner": self._owner,
            "balance": self._balance,
            "currency": self._currency.value,
            "status": self._status.value,
        }

    def __str__(self):
        return (
            f"BankAccount {self._owner} "
            f"****{self._account_id[-4:]} "
            f"{self._status.value} "
            f"{self._balance} {self._currency.value}"
        )