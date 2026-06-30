from decimal import Decimal

from accounts.base.abstract_account import AbstractAccount
from shared.enums import Currency, AccountStatus
from shared.exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InsufficientFundsError,
)
from utils.validation import require_enum, require_non_negative_decimal, require_positive_decimal

class BankAccount(AbstractAccount):
    def __init__(self, owner, currency: Currency, account_id=None, status=AccountStatus.ACTIVE):
        super().__init__(owner, account_id, status=status)
        self._currency = require_enum(currency, Currency, "Currency")
        if type(self) is BankAccount:
            self._reserve_account_id()

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

    @property
    def total_value(self) -> Decimal:
        return self._balance

    def _build_account_info(self, account_type: str) -> dict:
        return {
            "type": account_type,
            "id": self._account_id,
            "owner": self._owner,
            "balance": self._balance,
            "total_value": self.total_value,
            "currency": self._currency.value,
            "status": self._status.value,
        }

    def _check_status(self):
        if self._status == AccountStatus.FROZEN:
            raise AccountFrozenError
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError

    def deposit(self, amount):
        amount = require_positive_decimal(amount, "Amount")
        self._check_status()
        self._balance += amount

    def get_withdrawal_fee(self, amount) -> Decimal:
        require_positive_decimal(amount, "Amount")
        return Decimal("0.00")

    def get_total_withdrawal_debit(self, amount) -> Decimal:
        amount = require_positive_decimal(amount, "Amount")
        return amount + self.get_withdrawal_fee(amount)

    def withdraw(self, amount):
        total_debit = self.get_total_withdrawal_debit(amount)
        self._check_status()

        if total_debit > self._balance:
            raise InsufficientFundsError()

        self._balance -= total_debit

    def get_account_info(self):
        return self._build_account_info(account_type="bank")

    def __str__(self):
        return (
            f"BankAccount {self.owner} "
            f"{self._masked_account_id()} "
            f"{self.status.value} "
            f"{self.balance} {self.currency.value}"
        )
