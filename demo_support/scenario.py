from datetime import datetime

from audit.audit_journal import AuditJournal
from audit.loggers.account_audit_logger import AccountAuditLogger
from audit.loggers.transaction_audit_logger import TransactionAuditLogger
from demo_support.builders import build_clients, build_transactions, open_accounts, prepare_accounts
from demo_support.data import (
    ACCOUNT_DEFINITIONS,
    ACCOUNT_PREPARATION_STEPS,
    CLIENT_DEFINITIONS,
    TRANSACTION_GROUP_DEFINITIONS,
)
from demo_support.execution import cancel_demo_transactions, enqueue_transactions, process_demo_batch
from demo_support.reports import (
    build_client_transaction_history,
    build_queue_summary,
    build_suspicious_operations,
    build_transaction_statistics,
)
from demo_support.validation import validate_demo_definitions
from domain.bank import Bank
from risk.risk_analyzer import RiskAnalyzer
from services.account_service import AccountService
from services.transaction_processor import TransactionProcessor
from transactions.transaction_queue import TransactionQueue


def run_demo() -> dict:
    validate_demo_definitions(
        CLIENT_DEFINITIONS,
        ACCOUNT_DEFINITIONS,
        ACCOUNT_PREPARATION_STEPS,
        TRANSACTION_GROUP_DEFINITIONS,
    )

    current_time = {"value": datetime(2026, 4, 4, 9, 0)}
    audit_journal = AuditJournal()
    bank = Bank("Demo Bank", now_provider=lambda: current_time["value"])
    account_service = AccountService(
        AccountAuditLogger(
            "demo.accounts",
            audit_journal=audit_journal,
            now_provider=lambda: current_time["value"],
        )
    )
    risk_analyzer = RiskAnalyzer(now_provider=lambda: current_time["value"])
    queue = TransactionQueue(now_provider=lambda: current_time["value"])
    processor = TransactionProcessor(
        bank,
        TransactionAuditLogger(
            "demo.transactions",
            audit_journal=audit_journal,
            now_provider=lambda: current_time["value"],
        ),
        now_provider=lambda: current_time["value"],
        risk_analyzer=risk_analyzer,
    )

    clients = build_clients()
    for client in clients.values():
        bank.add_client(client)

    accounts = open_accounts(bank, clients)
    prepare_accounts(account_service, accounts, bank)

    transactions = build_transactions(accounts, current_time["value"])
    queue_events: list[dict] = []

    enqueue_transactions(queue, transactions, current_time, queue_events)
    canceled_transaction_ids = [
        transactions[36].transaction_id,
        transactions[37].transaction_id,
        transactions[38].transaction_id,
    ]
    cancel_demo_transactions(queue, current_time, queue_events, canceled_transaction_ids)

    morning_processed = process_demo_batch(
        queue,
        processor,
        current_time,
        queue_events,
        "morning",
        current_time["value"],
    )
    afternoon_processed = process_demo_batch(
        queue,
        processor,
        current_time,
        queue_events,
        "afternoon",
        datetime(2026, 4, 4, 15, 10),
    )
    night_processed = process_demo_batch(
        queue,
        processor,
        current_time,
        queue_events,
        "night",
        datetime(2026, 4, 5, 2, 30),
    )

    suspicious_operations = build_suspicious_operations(transactions, audit_journal)
    selected_client = clients["alice"]

    return {
        "bank": bank,
        "clients": clients,
        "accounts": accounts,
        "transactions": transactions,
        "processed_batches": {
            "morning": len(morning_processed),
            "afternoon": len(afternoon_processed),
            "night": len(night_processed),
        },
        "queue_events": queue_events,
        "queue_summary": build_queue_summary(queue_events),
        "remaining_in_queue": len(queue),
        "selected_client": selected_client,
        "selected_client_accounts": [
            account.get_account_info()
            for account in bank.search_accounts(client_id=selected_client.client_id)
        ],
        "selected_client_history": build_client_transaction_history(bank, selected_client, transactions),
        "selected_client_suspicious": [
            operation
            for operation in suspicious_operations
            if operation["sender"] in {account.account_id for account in bank.search_accounts(client_id=selected_client.client_id)}
        ],
        "suspicious_operations": suspicious_operations,
        "top_clients": bank.get_clients_ranking()[:3],
        "transaction_statistics": build_transaction_statistics(transactions, suspicious_operations),
        "overall_balance": {
            "amount": bank.get_total_balance(),
            "currency": bank.base_currency.value,
        },
    }
