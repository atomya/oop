from decimal import Decimal

from accounts.base.abstract_account import AbstractAccount
from shared.enums import Currency, AccountStatus
from shared.exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
    InsufficientFundsError,
)

class BankAccount(AbstractAccount):
    def __init__(self, owner, currency: Currency, account_id=None, status=AccountStatus.ACTIVE):
        super().__init__(owner, account_id, status=status)
        self._currency = self._validate_currency(currency)

    @staticmethod
    def _validate_currency(currency: Currency) -> Currency:
        if not isinstance(currency, Currency):
            raise InvalidOperationError("Currency must be a Currency enum")
        return currency

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def balance(self) -> Decimal:
        return self._balance

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def status(self) -> AccountStatus:
        return self._status

    def _validate_amount(self, amount):
        if isinstance(amount, bool):
            raise InvalidOperationError("Amount cannot be boolean")

        if not isinstance(amount, (int, float, Decimal)):
            raise InvalidOperationError("Amount must be numeric")

        amount = Decimal(str(amount))

        if amount <= 0:
            raise InvalidOperationError("Amount must be positive")

        return amount

    def _validate_non_negative_decimal(self, value, label: str) -> Decimal:
        if isinstance(value, bool):
            raise InvalidOperationError(f"{label} cannot be boolean")

        if not isinstance(value, (int, float, Decimal)):
            raise InvalidOperationError(f"{label} must be numeric")

        decimal_value = Decimal(str(value))
        if decimal_value < 0:
            raise InvalidOperationError(f"{label} cannot be negative")

        return decimal_value

    def _build_account_info(self, account_type: str) -> dict:
        return {
            "type": account_type,
            "id": self._account_id,
            "owner": self._owner,
            "balance": self._balance,
            "currency": self._currency.value,
            "status": self._status.value,
        }

    def _check_status(self):
        if self._status == AccountStatus.FROZEN:
            raise AccountFrozenError
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError

    def deposit(self, amount):
        amount = self._validate_amount(amount)
        self._check_status()
        self._balance += amount

    def withdraw(self, amount):
        amount = self._validate_amount(amount)
        self._check_status()

        if amount > self._balance:
            raise InsufficientFundsError()

        self._balance -= amount

    def get_account_info(self):
        return self._build_account_info(account_type="bank")

    def __str__(self):
        return (
            f"BankAccount {self.owner} "
            f"{self._masked_account_id()} "
            f"{self.status.value} "
            f"{self.balance} {self.currency.value}"
        )
