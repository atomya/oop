from decimal import Decimal

from accounts.base.bank_account import BankAccount
from accounts.types.investment.portfolio import Portfolio
from enums import AccountStatus, Currency
from exceptions import InsufficientFundsError


class InvestmentAccount(BankAccount):
    def __init__(
        self,
        owner,
        currency: Currency,
        account_id=None,
        status=AccountStatus.ACTIVE,
    ):
        super().__init__(owner, currency, account_id=account_id, status=status)
        self._portfolio = Portfolio()

    @property
    def portfolio(self) -> dict[str, Decimal]:
        return self._portfolio.as_dict()

    def withdraw(self, amount):
        amount = self._validate_amount(amount)
        self._check_status()

        if amount > self._balance:
            raise InsufficientFundsError()

        self._balance -= amount

    def invest_in_asset(self, asset_type: str, amount) -> None:
        amount = self._validate_amount(amount)
        self._check_status()

        if amount > self._balance:
            raise InsufficientFundsError()

        self._balance -= amount
        self._portfolio.invest(asset_type, amount)

    def sell_asset(self, asset_type: str, amount) -> None:
        amount = self._validate_amount(amount)
        self._check_status()

        self._portfolio.sell(asset_type, amount)
        self._balance += amount

    def project_yearly_growth(self, growth_rates: dict[str, Decimal] | None = None) -> dict[str, Decimal]:
        return self._portfolio.project_yearly_growth(growth_rates)

    def get_account_info(self):
        info = self._build_account_info(account_type="investment")
        info.update({"portfolio": self.portfolio})
        return info

    def __str__(self):
        invested_total = self._portfolio.total_invested()
        return (
            f"InvestmentAccount {self.owner} "
            f"{self.account_id} "
            f"{self.status.value} "
            f"available_balance={self.balance} {self.currency.value} "
            f"portfolio={invested_total}"
        )
