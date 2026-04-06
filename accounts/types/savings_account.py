from decimal import Decimal

from accounts.base.bank_account import BankAccount
from shared.enums import AccountStatus, Currency
from shared.exceptions import InsufficientFundsError
from utils.validation import require_non_negative_decimal, require_positive_decimal


class SavingsAccount(BankAccount):
    def __init__(
        self,
        owner,
        currency: Currency,
        min_balance,
        monthly_interest_rate,
        account_id=None,
        status=AccountStatus.ACTIVE,
    ):
        super().__init__(owner, currency, account_id=account_id, status=status)
        self._min_balance = require_non_negative_decimal(min_balance, "Minimum balance")
        self._monthly_interest_rate = require_non_negative_decimal(
            monthly_interest_rate,
            "Monthly interest rate",
        )
        self._reserve_account_id()

    @property
    def min_balance(self) -> Decimal:
        return self._min_balance

    @property
    def monthly_interest_rate(self) -> Decimal:
        return self._monthly_interest_rate

    def withdraw(self, amount):
        amount = require_positive_decimal(amount, "Amount")
        self._check_status()

        projected_balance = self._balance - amount
        if projected_balance < self._min_balance:
            raise InsufficientFundsError()

        self._balance = projected_balance

    def apply_monthly_interest(self) -> Decimal:
        self._check_status()
        interest = self._balance * self._monthly_interest_rate
        self._balance += interest
        return interest

    def get_account_info(self):
        info = self._build_account_info(account_type="savings")
        info.update(
            {
                "min_balance": self._min_balance,
                "monthly_interest_rate": self._monthly_interest_rate,
            }
        )
        return info

    def __str__(self):
        return (
            f"SavingsAccount {self.owner} "
            f"{self._masked_account_id()} "
            f"{self.status.value} "
            f"{self.balance} {self.currency.value} "
            f"min={self._min_balance} rate={self._monthly_interest_rate}"
        )
