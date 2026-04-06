from datetime import datetime
from typing import Callable

from shared.enums import TransactionPriority, TransactionStatus
from shared.exceptions import InvalidOperationError
from transactions.transaction import Transaction
from utils.validation import require_datetime, require_non_empty_string


class TransactionQueue:
    _PRIORITY_CYCLE = (
        TransactionPriority.HIGH,
        TransactionPriority.NORMAL,
        TransactionPriority.HIGH,
        TransactionPriority.NORMAL,
        TransactionPriority.LOW,
    )

    def __init__(self, now_provider: Callable[[], datetime] | None = None):
        self._transactions: dict[str, Transaction] = {}
        self._now_provider = now_provider or datetime.now
        self._cycle_index = 0

    @staticmethod
    def _validate_transaction(transaction) -> Transaction:
        if not isinstance(transaction, Transaction):
            raise InvalidOperationError("Queue can only store Transaction instances")
        return transaction

    def __len__(self) -> int:
        return len(self._transactions)

    def add(self, transaction: Transaction) -> None:
        validated_transaction = self._validate_transaction(transaction)
        if validated_transaction.status not in (TransactionStatus.PENDING, TransactionStatus.SCHEDULED):
            raise InvalidOperationError("Only pending or scheduled transactions can be added to queue")
        if validated_transaction.transaction_id in self._transactions:
            raise InvalidOperationError("Transaction ID must be unique in queue")
        self._transactions[validated_transaction.transaction_id] = validated_transaction

    def cancel(self, transaction_id: str, reason: str = "Canceled by queue") -> Transaction:
        validated_transaction_id = require_non_empty_string(transaction_id, "Transaction ID")
        transaction = self._transactions.get(validated_transaction_id)
        if transaction is None:
            raise InvalidOperationError("Transaction not found")
        transaction.cancel(self._now_provider(), reason=reason)
        self._transactions.pop(validated_transaction_id)
        return transaction

    def remove(self, transaction_id: str) -> Transaction:
        validated_transaction_id = require_non_empty_string(transaction_id, "Transaction ID")
        transaction = self._transactions.pop(validated_transaction_id, None)
        if transaction is None:
            raise InvalidOperationError("Transaction not found")
        return transaction

    @staticmethod
    def _sort_ready_bucket(transactions: list[Transaction]) -> list[Transaction]:
        return sorted(
            transactions,
            key=lambda transaction: (
                transaction.scheduled_for,
                transaction.created_at,
                transaction.transaction_id,
            ),
        )

    def get_next_ready(self, now: datetime | None = None) -> Transaction | None:
        current_time = require_datetime(now, "Queue time") if now is not None else self._now_provider()
        ready_transactions = [
            transaction
            for transaction in self._transactions.values()
            if transaction.is_ready(current_time)
        ]
        if not ready_transactions:
            return None

        ready_buckets = {
            TransactionPriority.HIGH: [],
            TransactionPriority.NORMAL: [],
            TransactionPriority.LOW: [],
        }
        for transaction in ready_transactions:
            ready_buckets[transaction.priority].append(transaction)

        for priority, transactions in ready_buckets.items():
            ready_buckets[priority] = self._sort_ready_bucket(transactions)

        cycle_length = len(self._PRIORITY_CYCLE)
        next_transaction = None
        for offset in range(cycle_length):
            slot_index = (self._cycle_index + offset) % cycle_length
            slot_priority = self._PRIORITY_CYCLE[slot_index]
            if ready_buckets[slot_priority]:
                next_transaction = ready_buckets[slot_priority][0]
                self._cycle_index = (slot_index + 1) % cycle_length
                break

        if next_transaction is None:
            return None

        return next_transaction

    def pending_transactions(self) -> list[dict]:
        return [transaction.get_transaction_info() for transaction in self._transactions.values()]
