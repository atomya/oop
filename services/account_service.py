from accounts import InvestmentAccount, SavingsAccount
from services.account_audit_logger import AccountAuditLogger


class AccountService:
    def __init__(self, audit_logger: AccountAuditLogger):
        self._audit_logger = audit_logger

    def deposit(self, account, amount) -> None:
        account.deposit(amount)
        self._audit_logger.log("deposit", account, amount=amount)

    def withdraw(self, account, amount) -> None:
        account.withdraw(amount)
        self._audit_logger.log("withdraw", account, amount=amount)

    def apply_monthly_interest(self, account: SavingsAccount):
        interest = account.apply_monthly_interest()
        self._audit_logger.log(
            "apply_monthly_interest",
            account,
            amount=interest,
            rate=account.monthly_interest_rate,
        )
        return interest

    def invest_in_asset(self, account: InvestmentAccount, asset_type: str, amount) -> None:
        account.invest_in_asset(asset_type, amount)
        self._audit_logger.log(
            "invest_in_asset",
            account,
            amount=amount,
            asset_type=asset_type,
        )

    def sell_asset(self, account: InvestmentAccount, asset_type: str, amount) -> None:
        account.sell_asset(asset_type, amount)
        self._audit_logger.log(
            "sell_asset",
            account,
            amount=amount,
            asset_type=asset_type,
        )

    def project_yearly_growth(self, account: InvestmentAccount, growth_rates=None):
        projection = account.project_yearly_growth(growth_rates)
        self._audit_logger.log(
            "project_yearly_growth",
            account,
            projection=projection,
        )
        return projection
