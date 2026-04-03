import logging
from datetime import date, datetime

from accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from domain.bank import Bank
from domain.client import Client
from shared.enums import Currency, AccountStatus
from shared.exceptions import AccountFrozenError, InsufficientFundsError, InvalidOperationError
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


def run_demo(account_service: AccountService):
    accounts = build_demo_accounts()
    regular, savings, premium, investment = accounts
    messages = []

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
        messages.append(f"Premium account operation failed: {error}")

    account_service.deposit(investment, 5000)
    account_service.invest_in_asset(investment, "stocks", 1500)
    account_service.invest_in_asset(investment, "bonds", 1000)
    account_service.invest_in_asset(investment, "etf", 700)
    growth_projection = account_service.project_yearly_growth(investment)

    frozen_account = BankAccount("Eva", Currency.CNY, status=AccountStatus.FROZEN)
    try:
        account_service.deposit(frozen_account, 100)
    except AccountFrozenError as error:
        messages.append(f"Frozen account operation failed: {error}")

    return {
        "messages": messages,
        "accounts": [*accounts, frozen_account],
        "growth_projection": growth_projection,
    }


def run_bank_demo():
    bank = Bank("Day 3 Demo Bank", now_provider=lambda: datetime(2026, 4, 3, 10, 0))
    client = Client(
        full_name="Frank Stone",
        birth_date=date(1998, 4, 3),
        contacts={"phone": "+15550001111", "email": "frank@example.com"},
        pin_code="2468",
        client_id="client-9001",
    )
    bank.add_client(client)
    account = bank.open_account(client.client_id, SavingsAccount, currency=Currency.USD, min_balance=50, monthly_interest_rate=0.01)
    search_result = bank.search_accounts(client_id=client.client_id)
    messages = []

    try:
        bank.authenticate_client(client.client_id, "0000")
    except InvalidOperationError as error:
        messages.append(f"Authentication failed: {error}")

    authenticated_client = bank.authenticate_client(client.client_id, "2468")
    bank.freeze_account(account.account_id)
    bank.unfreeze_account(account.account_id)

    return {
        "messages": messages,
        "bank": bank,
        "client": authenticated_client,
        "account": account,
        "search_result": search_result,
        "ranking": bank.get_clients_ranking(),
    }


def render_demo_output(demo_result):
    for message in demo_result["messages"]:
        print(message)

    for account in demo_result["accounts"]:
        print(account)
        print(account.get_account_info())

    print("Investment yearly projection:", demo_result["growth_projection"])


def render_bank_demo_output(bank_demo_result):
    for message in bank_demo_result["messages"]:
        print(message)

    print(bank_demo_result["client"])
    print(bank_demo_result["account"])
    print("Bank search result:", [account.account_id for account in bank_demo_result["search_result"]])
    print("Bank ranking:", bank_demo_result["ranking"])


def main():
    configure_logging()
    account_service = AccountService(AccountAuditLogger())
    demo_result = run_demo(account_service)
    bank_demo_result = run_bank_demo()
    render_demo_output(demo_result)
    render_bank_demo_output(bank_demo_result)


if __name__ == "__main__":
    main()
