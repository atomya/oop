from datetime import datetime
from decimal import Decimal

from shared.enums import Currency, TransactionPriority, TransactionStatus, TransactionType
from shared.exceptions import InvalidOperationError
from utils.unique_id import prepare_unique_id, reserve_unique_id
from utils.validation import (
    require_datetime,
    require_enum,
    require_non_empty_string,
    require_non_negative_decimal,
    require_positive_decimal,
)


class Transaction:
    _used_transaction_ids: set[str] = set()

    def __init__(
        self,
        transaction_type: TransactionType,
        amount,
        currency: Currency,
        sender: str,
        recipient: str,
        priority: TransactionPriority = TransactionPriority.NORMAL,
        scheduled_for: datetime | None = None,
        transaction_id: str | None = None,
        created_at: datetime | None = None,
    ):
        validated_type = require_enum(transaction_type, TransactionType, "Transaction type")
        validated_amount = require_positive_decimal(amount, "Transaction amount")
        validated_currency = require_enum(currency, Currency, "Transaction currency")
        validated_sender = require_non_empty_string(sender, "Sender")
        validated_recipient = require_non_empty_string(recipient, "Recipient")
        validated_priority = require_enum(priority, TransactionPriority, "Transaction priority")
        validated_created_at = require_datetime(created_at, "Created at", allow_none=True) or datetime.now()
        validated_scheduled_for = require_datetime(
            scheduled_for,
            "Scheduled for",
            allow_none=True,
        ) or validated_created_at
        if validated_scheduled_for < validated_created_at:
            raise InvalidOperationError("Scheduled for cannot be earlier than created_at")

        prepared_transaction_id = prepare_unique_id(
            transaction_id,
            used_ids=self._used_transaction_ids,
            label="Transaction ID",
            allow_int=False,
        )
        initial_status = (
            TransactionStatus.SCHEDULED
            if validated_scheduled_for > validated_created_at
            else TransactionStatus.PENDING
        )

        reserve_unique_id(
            prepared_transaction_id,
            used_ids=self._used_transaction_ids,
            label="Transaction ID",
        )

        self._transaction_id = prepared_transaction_id
        self._transaction_type = validated_type
        self._amount = validated_amount
        self._currency = validated_currency
        self._sender = validated_sender
        self._recipient = validated_recipient
        self._priority = validated_priority
        self._fee = Decimal("0.00")
        self._status = initial_status
        self._failure_reason: str | None = None
        self._created_at = validated_created_at
        self._scheduled_for = validated_scheduled_for
        self._processed_at: datetime | None = None
        self._failed_at: datetime | None = None
        self._canceled_at: datetime | None = None
        self._retry_count = 0

    @staticmethod
    def _validate_reason(reason) -> str:
        return require_non_empty_string(reason, "Failure reason")

    @property
    def transaction_id(self) -> str:
        return self._transaction_id

    @property
    def transaction_type(self) -> TransactionType:
        return self._transaction_type

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def sender(self) -> str:
        return self._sender

    @property
    def recipient(self) -> str:
        return self._recipient

    @property
    def priority(self) -> TransactionPriority:
        return self._priority

    @property
    def fee(self) -> Decimal:
        return self._fee

    @property
    def status(self) -> TransactionStatus:
        return self._status

    @property
    def failure_reason(self) -> str | None:
        return self._failure_reason

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def scheduled_for(self) -> datetime:
        return self._scheduled_for

    @property
    def processed_at(self) -> datetime | None:
        return self._processed_at

    @property
    def failed_at(self) -> datetime | None:
        return self._failed_at

    @property
    def canceled_at(self) -> datetime | None:
        return self._canceled_at

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def is_ready(self, now: datetime) -> bool:
        validated_now = require_datetime(now, "Current time")
        return self._status in (TransactionStatus.PENDING, TransactionStatus.SCHEDULED) and self._scheduled_for <= validated_now

    def mark_processing(self, processed_at: datetime) -> None:
        if self._status not in (TransactionStatus.PENDING, TransactionStatus.SCHEDULED):
            raise InvalidOperationError("Only pending or scheduled transactions can be processed")
        self._processed_at = require_datetime(processed_at, "Processed at")
        self._status = TransactionStatus.PROCESSING
        self._failure_reason = None

    def mark_completed(self, processed_at: datetime, fee) -> None:
        if self._status != TransactionStatus.PROCESSING:
            raise InvalidOperationError("Only processing transactions can be completed")
        self._processed_at = require_datetime(processed_at, "Processed at")
        self._fee = require_non_negative_decimal(fee, "Transaction fee")
        self._status = TransactionStatus.COMPLETED
        self._failure_reason = None
        self._failed_at = None
        self._canceled_at = None

    def mark_failed(self, reason: str, failed_at: datetime) -> None:
        self._failure_reason = self._validate_reason(reason)
        self._failed_at = require_datetime(failed_at, "Failed at")
        self._status = TransactionStatus.FAILED

    def schedule_retry(self, next_attempt_at: datetime) -> None:
        validated_next_attempt = require_datetime(next_attempt_at, "Next retry at")
        self._retry_count += 1
        self._scheduled_for = validated_next_attempt
        self._status = TransactionStatus.SCHEDULED
        self._failure_reason = None
        self._processed_at = None

    def cancel(self, canceled_at: datetime, reason: str | None = None) -> None:
        if self._status not in (TransactionStatus.PENDING, TransactionStatus.SCHEDULED):
            raise InvalidOperationError("Only pending or scheduled transactions can be canceled")
        self._canceled_at = require_datetime(canceled_at, "Canceled at")
        self._status = TransactionStatus.CANCELED
        self._failure_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None

    def get_transaction_info(self) -> dict:
        return {
            "transaction_id": self._transaction_id,
            "transaction_type": self._transaction_type.value,
            "amount": self._amount,
            "currency": self._currency.value,
            "fee": self._fee,
            "sender": self._sender,
            "recipient": self._recipient,
            "priority": self._priority.name.lower(),
            "status": self._status.value,
            "failure_reason": self._failure_reason,
            "retry_count": self._retry_count,
            "created_at": self._created_at.isoformat(timespec="seconds"),
            "scheduled_for": self._scheduled_for.isoformat(timespec="seconds"),
            "processed_at": self._processed_at.isoformat(timespec="seconds") if self._processed_at else None,
            "failed_at": self._failed_at.isoformat(timespec="seconds") if self._failed_at else None,
            "canceled_at": self._canceled_at.isoformat(timespec="seconds") if self._canceled_at else None,
        }

    def __str__(self) -> str:
        return (
            f"Transaction {self._transaction_id} "
            f"{self._transaction_type.value} "
            f"{self._status.value} "
            f"{self._amount} {self._currency.value}"
        )
