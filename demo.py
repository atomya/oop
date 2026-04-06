import logging
from datetime import date, datetime, timedelta

from accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from audit.account_audit_logger import AccountAuditLogger
from audit.transaction_audit_logger import TransactionAuditLogger
from domain.bank import Bank
from domain.client import Client
from services.transaction_processor import TransactionProcessor
from shared.enums import Currency, AccountStatus, TransactionType
from shared.exceptions import AccountFrozenError, InsufficientFundsError, InvalidOperationError
from services.account_service import AccountService
from transactions.transaction import Transaction
from transactions.transaction_queue import TransactionQueue


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
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


def run_transaction_demo():
    current_time = {"value": datetime(2026, 4, 3, 14, 0)}
    bank = Bank("Day 4 Demo Bank", now_provider=lambda: current_time["value"])
    account_service = AccountService(AccountAuditLogger("demo.accounts"))

    clients = [
        Client(
            full_name="Alice River",
            birth_date=date(1990, 1, 10),
            contacts={"phone": "+10000000001", "email": "alice@example.com"},
            pin_code="1111",
        ),
        Client(
            full_name="Bob Stone",
            birth_date=date(1991, 2, 11),
            contacts={"phone": "+10000000002", "email": "bob@example.com"},
            pin_code="2222",
        ),
        Client(
            full_name="Carol Frost",
            birth_date=date(1989, 3, 12),
            contacts={"phone": "+10000000003", "email": "carol@example.com"},
            pin_code="3333",
        ),
        Client(
            full_name="Dave Snow",
            birth_date=date(1988, 4, 13),
            contacts={"phone": "+10000000004", "email": "dave@example.com"},
            pin_code="4444",
        ),
        Client(
            full_name="Emma Lake",
            birth_date=date(1992, 5, 14),
            contacts={"phone": "+10000000005", "email": "emma@example.com"},
            pin_code="5555",
        ),
    ]

    for client in clients:
        bank.add_client(client)

    alice_account = bank.open_account(clients[0].client_id, BankAccount, currency=Currency.USD)
    bob_account = bank.open_account(
        clients[1].client_id,
        SavingsAccount,
        currency=Currency.EUR,
        min_balance=0,
        monthly_interest_rate=0.01,
    )
    carol_account = bank.open_account(
        clients[2].client_id,
        PremiumAccount,
        currency=Currency.USD,
        overdraft_limit=500,
        withdrawal_limit=1000,
        fixed_fee=10,
    )
    dave_account = bank.open_account(clients[3].client_id, BankAccount, currency=Currency.USD)
    emma_account = bank.open_account(clients[4].client_id, BankAccount, currency=Currency.KZT)

    account_service.deposit(alice_account, 2000)
    account_service.deposit(carol_account, 50)
    bank.freeze_account(dave_account.account_id)

    queue = TransactionQueue(now_provider=lambda: current_time["value"])
    processor = TransactionProcessor(
        bank,
        TransactionAuditLogger("demo.transactions"),
        now_provider=lambda: current_time["value"],
    )

    transactions = [
        Transaction(TransactionType.INTERNAL_TRANSFER, 100, Currency.USD, alice_account.account_id, bob_account.account_id, transaction_id="demo-tx-001", created_at=current_time["value"]),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 100, Currency.USD, alice_account.account_id, "external-demo-001", transaction_id="demo-tx-002", created_at=current_time["value"]),
        Transaction(TransactionType.INTERNAL_TRANSFER, 10, Currency.USD, alice_account.account_id, emma_account.account_id, transaction_id="demo-tx-003", created_at=current_time["value"]),
        Transaction(TransactionType.INTERNAL_TRANSFER, 20, Currency.USD, alice_account.account_id, dave_account.account_id, transaction_id="demo-tx-004", created_at=current_time["value"]),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 5000, Currency.USD, alice_account.account_id, "external-demo-002", transaction_id="demo-tx-005", created_at=current_time["value"]),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 200, Currency.USD, carol_account.account_id, "external-demo-003", transaction_id="demo-tx-006", created_at=current_time["value"]),
        Transaction(TransactionType.INTERNAL_TRANSFER, 50, Currency.USD, alice_account.account_id, bob_account.account_id, scheduled_for=current_time["value"] + timedelta(hours=1), transaction_id="demo-tx-007", created_at=current_time["value"]),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 25, Currency.USD, alice_account.account_id, "external-demo-004", transaction_id="demo-tx-008", created_at=current_time["value"]),
        Transaction(TransactionType.EXTERNAL_TRANSFER, 30, Currency.USD, alice_account.account_id, "external-demo-005", transaction_id="demo-tx-009", created_at=current_time["value"]),
        Transaction(TransactionType.INTERNAL_TRANSFER, 15, Currency.USD, alice_account.account_id, "missing-demo-account", transaction_id="demo-tx-010", created_at=current_time["value"]),
    ]

    for transaction in transactions:
        queue.add(transaction)

    queue.cancel("demo-tx-008")
    first_pass = processor.process_all(queue)
    current_time["value"] = current_time["value"] + timedelta(hours=1, minutes=10)
    second_pass = processor.process_all(queue)

    return {
        "transactions": transactions,
        "processed_count": len(first_pass) + len(second_pass),
        "remaining_in_queue": len(queue),
        "balances": {
            "alice": alice_account.balance,
            "bob": bob_account.balance,
            "carol": carol_account.balance,
            "emma": emma_account.balance,
        },
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


def render_transaction_demo_output(transaction_demo_result):
    print("Processed transactions:", transaction_demo_result["processed_count"])
    print("Remaining in queue:", transaction_demo_result["remaining_in_queue"])
    print("Final balances:", transaction_demo_result["balances"])
    for transaction in transaction_demo_result["transactions"]:
        print(
            transaction.transaction_id,
            transaction.status.value,
            transaction.fee,
            transaction.failure_reason,
        )


def main():
    configure_logging()
    account_service = AccountService(AccountAuditLogger())
    demo_result = run_demo(account_service)
    bank_demo_result = run_bank_demo()
    transaction_demo_result = run_transaction_demo()
    render_demo_output(demo_result)
    render_bank_demo_output(bank_demo_result)
    render_transaction_demo_output(transaction_demo_result)


if __name__ == "__main__":
    main()
