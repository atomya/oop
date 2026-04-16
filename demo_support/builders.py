from datetime import datetime, timedelta

from accounts import BankAccount
from domain.bank import Bank
from domain.client import Client
from services.account_service import AccountService
from shared.enums import TransactionPriority
from transactions.transaction import Transaction

from demo_support.data import ACCOUNT_DEFINITIONS, ACCOUNT_PREPARATION_STEPS, CLIENT_DEFINITIONS, TRANSACTION_GROUP_DEFINITIONS


def build_clients() -> dict[str, Client]:
    return {
        client_key: Client(
            full_name=definition["full_name"],
            birth_date=definition["birth_date"],
            contacts=definition["contacts"],
            pin_code=definition["pin_code"],
        )
        for client_key, definition in CLIENT_DEFINITIONS.items()
    }


def open_accounts(bank: Bank, clients: dict[str, Client]) -> dict[str, BankAccount]:
    accounts_by_key = {}
    for account_key, definition in ACCOUNT_DEFINITIONS.items():
        client = clients[definition["client"]]
        account_data = {key: value for key, value in definition.items() if key not in {"client", "account_type"}}
        accounts_by_key[account_key] = bank.open_account(
            client.client_id,
            definition["account_type"],
            **account_data,
        )
    return accounts_by_key


def prepare_accounts(account_service: AccountService, accounts: dict[str, BankAccount], bank: Bank) -> None:
    for step in ACCOUNT_PREPARATION_STEPS:
        account = accounts[step["account"]]
        if step["action"] == "deposit":
            account_service.deposit(account, step["amount"])
        elif step["action"] == "apply_monthly_interest":
            account_service.apply_monthly_interest(account)
        elif step["action"] == "invest_in_asset":
            account_service.invest_in_asset(account, step["asset_type"], step["amount"])
        elif step["action"] == "freeze":
            bank.freeze_account(account.account_id)
        else:
            raise ValueError(f"Unsupported account preparation action: {step['action']}")


def build_transactions(accounts: dict[str, BankAccount], base_time: datetime) -> list[Transaction]:
    transaction_prefix = accounts["alice_main"].account_id[:4]
    schedule_map = {
        None: None,
        "afternoon": base_time + timedelta(hours=6),
        "night": base_time + timedelta(hours=17, minutes=30),
    }

    def build_external_recipient(recipient_external: tuple[str, int | None]) -> str:
        external_kind, external_number = recipient_external
        if external_kind == "missing_demo_account":
            return "missing-demo-account"
        return f"external-{external_kind}-{external_number:03d}"

    def build_transaction(number: int, definition: dict) -> Transaction:
        sender_account = accounts[definition["sender"]]
        if "recipient_account" in definition:
            recipient_id = accounts[definition["recipient_account"]].account_id
        else:
            recipient_id = build_external_recipient(definition["recipient_external"])
        return Transaction(
            transaction_type=definition["transaction_type"],
            amount=definition["amount"],
            currency=definition["currency"],
            sender=sender_account.account_id,
            recipient=recipient_id,
            priority=definition.get("priority", TransactionPriority.NORMAL),
            scheduled_for=schedule_map[definition.get("scheduled_for", definition["schedule"])],
            transaction_id=f"demo-{transaction_prefix}-tx-{number:03d}",
            created_at=base_time,
        )

    all_definitions = (
        {
            **case,
            "schedule": group["schedule"],
        }
        for group in TRANSACTION_GROUP_DEFINITIONS
        for case in group["cases"]
    )

    return [
        build_transaction(number, definition)
        for number, definition in enumerate(all_definitions, start=1)
    ]
