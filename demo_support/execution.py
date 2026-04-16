from datetime import datetime

from demo_support.common import format_timestamp
from services.transaction_processor import TransactionProcessor
from transactions.transaction import Transaction
from transactions.transaction_queue import TransactionQueue


def record_queue_event(
    queue_events: list[dict],
    *,
    timestamp: datetime,
    event: str,
    transaction: Transaction,
    batch: str,
) -> None:
    queue_events.append(
        {
            "timestamp": format_timestamp(timestamp),
            "event": event,
            "batch": batch,
            "transaction_id": transaction.transaction_id,
            "status": transaction.status.value,
            "priority": transaction.priority.name.lower(),
            "failure_reason": transaction.failure_reason,
        }
    )


def enqueue_transactions(
    queue: TransactionQueue,
    transactions: list[Transaction],
    current_time: dict[str, datetime],
    queue_events: list[dict],
) -> None:
    for transaction in transactions:
        queue.add(transaction)
        record_queue_event(
            queue_events,
            timestamp=current_time["value"],
            event="queued",
            transaction=transaction,
            batch="enqueue",
        )


def cancel_demo_transactions(
    queue: TransactionQueue,
    current_time: dict[str, datetime],
    queue_events: list[dict],
    transaction_ids: list[str],
) -> None:
    for transaction_id in transaction_ids:
        canceled = queue.cancel(transaction_id)
        record_queue_event(
            queue_events,
            timestamp=canceled.canceled_at or current_time["value"],
            event="canceled",
            transaction=canceled,
            batch="queue",
        )


def process_demo_batch(
    queue: TransactionQueue,
    processor: TransactionProcessor,
    current_time: dict[str, datetime],
    queue_events: list[dict],
    batch: str,
    scheduled_time: datetime,
) -> list[Transaction]:
    current_time["value"] = scheduled_time
    processed = processor.process_all(queue)

    for transaction in processed:
        event_time = transaction.processed_at or transaction.failed_at or current_time["value"]
        record_queue_event(
            queue_events,
            timestamp=event_time,
            event=transaction.status.value,
            transaction=transaction,
            batch=batch,
        )

    return processed
