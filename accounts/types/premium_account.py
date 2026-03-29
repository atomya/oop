from decimal import Decimal

from accounts.base.bank_account import BankAccount
from enums import AccountStatus, Currency
from exceptions import InsufficientFundsError, InvalidOperationError


class PremiumAccount(BankAccount):
    def __init__(
        self,
        owner,
        currency: Currency,
        overdraft_limit,
        withdrawal_limit,
        fixed_fee,
        account_id=None,
        status=AccountStatus.ACTIVE,
    ):
        super().__init__(owner, currency, account_id=account_id, status=status)
        self._overdraft_limit = self._validate_non_negative_decimal(overdraft_limit, "Overdraft limit")
        self._withdrawal_limit = self._validate_non_negative_decimal(withdrawal_limit, "Withdrawal limit")
        self._fixed_fee = self._validate_non_negative_decimal(fixed_fee, "Fixed fee")

    @property
    def overdraft_limit(self) -> Decimal:
        return self._overdraft_limit

    @property
    def withdrawal_limit(self) -> Decimal:
        return self._withdrawal_limit

    @property
    def fixed_fee(self) -> Decimal:
        return self._fixed_fee

    def withdraw(self, amount):
        amount = self._validate_amount(amount)
        self._check_status()

        if amount > self._withdrawal_limit:
            raise InvalidOperationError("Amount exceeds premium withdrawal limit")

        total_debit = amount + self._fixed_fee
        projected_balance = self._balance - total_debit

        if projected_balance < -self._overdraft_limit:
            raise InsufficientFundsError()

        self._balance = projected_balance

    def get_account_info(self):
        info = self._build_account_info(account_type="premium")
        info.update(
            {
                "overdraft_limit": self._overdraft_limit,
                "withdrawal_limit": self._withdrawal_limit,
                "fixed_fee": self._fixed_fee,
            }
        )
        return info

    def __str__(self):
        return (
            f"PremiumAccount {self.owner} "
            f"{self.account_id} "
            f"{self.status.value} "
            f"{self.balance} {self.currency.value} "
            f"overdraft={self._overdraft_limit} fee={self._fixed_fee}"
        )
