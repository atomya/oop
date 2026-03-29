import logging

from accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from enums import Currency, AccountStatus
from exceptions import AccountFrozenError, InsufficientFundsError
from services.account_audit_logger import AccountAuditLogger
from services.account_service import AccountService


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s | %(id)s %(owner)s %(currency)s %(balance)s",
    )


def build_demo_accounts():
    return [
        BankAccount("Alice", Currency.USD),
        SavingsAccount("Bob", Currency.EUR, min_balance=100, monthly_interest_rate=0.02),
        PremiumAccount("Charlie", Currency.RUB, overdraft_limit=500, withdrawal_limit=2000, fixed_fee=25),
        InvestmentAccount("Diana", Currency.USD),
    ]


def run_demo():
    account_service = AccountService(AccountAuditLogger())
    accounts = build_demo_accounts()
    regular, savings, premium, investment = accounts

    account_service.deposit(regular, 500)
    account_service.withdraw(regular, 200)

    account_service.deposit(savings, 1000)
    account_service.withdraw(savings, 300)
    account_service.apply_monthly_interest(savings)

    account_service.deposit(premium, 300)
    account_service.withdraw(premium, 700)
    account_service.deposit(premium, 1000)
    try:
        account_service.withdraw(premium, 1500)
    except InsufficientFundsError as error:
        print(f"Premium account operation failed: {error}")

    account_service.deposit(investment, 5000)
    account_service.invest_in_asset(investment, "stocks", 1500)
    account_service.invest_in_asset(investment, "bonds", 1000)
    account_service.invest_in_asset(investment, "etf", 700)
    growth_projection = account_service.project_yearly_growth(investment)

    frozen_account = BankAccount("Eva", Currency.CNY, status=AccountStatus.FROZEN)
    try:
        account_service.deposit(frozen_account, 100)
    except AccountFrozenError as error:
        print(f"Frozen account operation failed: {error}")

    for account in [*accounts, frozen_account]:
        print(account)
        print(account.get_account_info())

    print("Investment yearly projection:", growth_projection)


if __name__ == "__main__":
    configure_logging()
    run_demo()
