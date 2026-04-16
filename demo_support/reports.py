from collections import Counter
from decimal import Decimal

from audit.audit_journal import AuditJournal
from demo_support.common import format_timestamp
from domain.bank import Bank
from domain.client import Client
from transactions.transaction import Transaction


def build_transaction_statistics(transactions: list[Transaction], suspicious_operations: list[dict]) -> dict:
    suspicious_ids = {entry["transaction_id"] for entry in suspicious_operations}
    blocked_ids = {
        entry["transaction_id"]
        for entry in suspicious_operations
        if "transaction_blocked_high_risk" in entry["events"]
    }

    return {
        "total_transactions": len(transactions),
        "by_status": dict(Counter(transaction.status.value for transaction in transactions)),
        "by_type": dict(Counter(transaction.transaction_type.value for transaction in transactions)),
        "by_priority": dict(Counter(transaction.priority.name.lower() for transaction in transactions)),
        "suspicious_transactions": len(suspicious_ids),
        "blocked_high_risk": len(blocked_ids),
        "total_fees": sum((transaction.fee for transaction in transactions), start=Decimal("0.00")),
    }


def build_suspicious_operations(transactions: list[Transaction], audit_journal: AuditJournal) -> list[dict]:
    suspicious_entries = audit_journal.filter(entity_type="transaction", suspicious_only=True)
    suspicious_by_transaction: dict[str, dict] = {}

    for entry in suspicious_entries:
        if entry.transaction_id is None:
            continue
        transaction_meta = suspicious_by_transaction.setdefault(
            entry.transaction_id,
            {
                "events": set(),
                "risk_levels": set(),
            },
        )
        transaction_meta["events"].add(entry.event)
        if entry.risk_level is not None:
            transaction_meta["risk_levels"].add(entry.risk_level.value)

    suspicious_operations = []
    for transaction in transactions:
        metadata = suspicious_by_transaction.get(transaction.transaction_id)
        if metadata is None:
            continue
        suspicious_operations.append(
            {
                "transaction_id": transaction.transaction_id,
                "status": transaction.status.value,
                "amount": transaction.amount,
                "currency": transaction.currency.value,
                "sender": transaction.sender,
                "recipient": transaction.recipient,
                "failure_reason": transaction.failure_reason,
                "events": sorted(metadata["events"]),
                "risk_levels": sorted(metadata["risk_levels"]),
            }
        )

    return suspicious_operations


def build_client_transaction_history(
    bank: Bank,
    client: Client,
    transactions: list[Transaction],
) -> list[dict]:
    history = []

    for transaction in sorted(transactions, key=lambda item: (item.created_at, item.transaction_id)):
        sender_is_client = bank.has_account(transaction.sender) and bank.get_account_owner(transaction.sender).client_id == client.client_id
        recipient_is_client = bank.has_account(transaction.recipient) and bank.get_account_owner(transaction.recipient).client_id == client.client_id

        if not sender_is_client and not recipient_is_client:
            continue

        if sender_is_client:
            direction = "outgoing"
            if bank.has_account(transaction.recipient):
                counterparty = bank.get_account_owner(transaction.recipient).full_name
            else:
                counterparty = transaction.recipient
        else:
            direction = "incoming"
            counterparty = bank.get_account_owner(transaction.sender).full_name

        history.append(
            {
                "transaction_id": transaction.transaction_id,
                "direction": direction,
                "counterparty": counterparty,
                "status": transaction.status.value,
                "amount": transaction.amount,
                "currency": transaction.currency.value,
                "scheduled_for": format_timestamp(transaction.scheduled_for),
                "finished_at": format_timestamp(
                    transaction.processed_at or transaction.failed_at or transaction.canceled_at
                ),
                "failure_reason": transaction.failure_reason,
            }
        )

    return history


def build_queue_summary(queue_events: list[dict]) -> dict:
    tracked_events = [
        event["event"]
        for event in queue_events
        if event["event"] in {"queued", "completed", "failed", "canceled"}
    ]
    return dict(Counter(tracked_events))
