from datetime import datetime, timedelta
from decimal import Decimal

from accounts import PremiumAccount
from audit.loggers.base_audit_logger import BaseAuditLogger
from domain.bank import Bank
from risk.risk_analyzer import RiskAnalyzer
from shared.enums import AccountStatus, AuditLevel, Currency, RiskLevel, TransactionStatus, TransactionType
from shared.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
    TemporaryProcessingError,
)
from transactions.rules import TransactionRules
from transactions.transaction import Transaction
from transactions.transaction_queue import TransactionQueue
from utils.currency import (
    BASE_EXCHANGE_RATES,
    convert_currency_amount,
    quantize_money,
    validate_exchange_rates,
)
from utils.validation import (
    require_non_negative_decimal,
    require_non_negative_int,
    require_positive_int,
)


class TransactionProcessor:
    def __init__(
        self,
        bank: Bank,
        audit_logger: BaseAuditLogger,
        now_provider=None,
        exchange_rates: dict[Currency, Decimal] | None = None,
        external_transfer_fee_rate=TransactionRules.DEFAULT_EXTERNAL_TRANSFER_FEE_RATE,
        max_retries: int = TransactionRules.DEFAULT_MAX_RETRIES,
        retry_delay_minutes: int = TransactionRules.DEFAULT_RETRY_DELAY_MINUTES,
        risk_analyzer: RiskAnalyzer | None = None,
    ):
        if not isinstance(bank, Bank):
            raise InvalidOperationError("TransactionProcessor requires a Bank instance")

        self._bank = bank
        self._audit_logger = audit_logger
        self._now_provider = now_provider or datetime.now
        self._risk_analyzer = risk_analyzer
        self._exchange_rates = validate_exchange_rates(exchange_rates or BASE_EXCHANGE_RATES)
        self._external_transfer_fee_rate = require_non_negative_decimal(
            external_transfer_fee_rate,
            "External transfer fee rate",
        )
        self._max_retries = require_non_negative_int(max_retries, "Max retries")
        self._retry_delay_minutes = require_positive_int(
            retry_delay_minutes,
            "Retry delay minutes",
        )

    def _now(self) -> datetime:
        return self._now_provider()

    def _calculate_fee(self, transaction: Transaction, sender_amount: Decimal) -> Decimal:
        if transaction.transaction_type == TransactionType.EXTERNAL_TRANSFER:
            return quantize_money(sender_amount * self._external_transfer_fee_rate)
        return Decimal("0.00")

    @staticmethod
    def _validate_account_for_transfer(account, role: str, *, check_negative_balance: bool = False) -> None:
        if account.status == AccountStatus.FROZEN:
            raise AccountFrozenError()
        if account.status == AccountStatus.CLOSED:
            raise AccountClosedError()
        if check_negative_balance and account.balance < 0 and not isinstance(account, PremiumAccount):
            raise InvalidOperationError(f"{role} account cannot transfer while balance is negative")

    def _prepare_execution_plan(self, transaction: Transaction) -> dict:
        sender = self._bank.get_account(transaction.sender)
        sender_owner = self._bank.get_account_owner(transaction.sender)
        self._bank.ensure_operation_allowed(
            "process_transaction",
            client_id=sender_owner.client_id,
            transaction_id=transaction.transaction_id,
        )
        self._validate_account_for_transfer(sender, "Sender", check_negative_balance=True)

        if transaction.transaction_type == TransactionType.INTERNAL_TRANSFER:
            if transaction.sender == transaction.recipient:
                raise InvalidOperationError("Sender and recipient accounts must be different")
            if not self._bank.has_account(transaction.recipient):
                raise InvalidOperationError("Recipient account not found")
            recipient = self._bank.get_account(transaction.recipient)
            self._validate_account_for_transfer(recipient, "Recipient")
            recipient_credit_amount = convert_currency_amount(
                transaction.amount,
                transaction.currency,
                recipient.currency,
                self._exchange_rates,
            )
        else:
            recipient = None
            recipient_credit_amount = quantize_money(transaction.amount)

        sender_debit_amount = convert_currency_amount(
            transaction.amount,
            transaction.currency,
            sender.currency,
            self._exchange_rates,
        )
        fee_amount = self._calculate_fee(transaction, sender_debit_amount)
        total_debit = quantize_money(sender_debit_amount + fee_amount)

        return {
            "sender": sender,
            "recipient": recipient,
            "sender_owner": sender_owner,
            "sender_debit_amount": sender_debit_amount,
            "recipient_credit_amount": recipient_credit_amount,
            "fee_amount": fee_amount,
            "total_debit": total_debit,
        }

    def _refund_sender(self, sender, amount: Decimal) -> None:
        sender.deposit(amount)

    def _send_external_transfer(self, transaction: Transaction, amount: Decimal) -> None:
        if amount <= 0:
            raise InvalidOperationError("External transfer amount must be positive")

    def _execute_plan(self, transaction: Transaction, plan: dict) -> None:
        sender = plan["sender"]
        recipient = plan["recipient"]
        total_debit = plan["total_debit"]
        recipient_credit_amount = plan["recipient_credit_amount"]
        sender_debited = False

        try:
            sender.withdraw(total_debit)
            sender_debited = True

            if transaction.transaction_type == TransactionType.INTERNAL_TRANSFER:
                recipient.deposit(recipient_credit_amount)
            else:
                self._send_external_transfer(transaction, recipient_credit_amount)
        except Exception:
            if sender_debited:
                self._refund_sender(sender, total_debit)
            raise

    def _handle_retry(self, queue: TransactionQueue, transaction: Transaction, error: Exception) -> None:
        if transaction.retry_count < self._max_retries:
            next_attempt_at = self._now() + timedelta(minutes=self._retry_delay_minutes)
            transaction.schedule_retry(next_attempt_at)
            self._audit_logger.log(
                "transaction_retry_scheduled",
                transaction,
                level=AuditLevel.WARNING,
                message="Temporary processing error, retry scheduled",
                error=str(error),
                next_retry_at=next_attempt_at.isoformat(timespec="seconds"),
            )
            return

        transaction.mark_failed(str(error), self._now())
        queue.remove(transaction.transaction_id)
        self._audit_logger.log(
            "transaction_failed",
            transaction,
            level=AuditLevel.ERROR,
            message="Transaction failed after retry attempts were exhausted",
            error=str(error),
        )

    def _assess_risk(self, queue: TransactionQueue, transaction: Transaction):
        if self._risk_analyzer is None:
            return None, None

        sender_owner = self._bank.get_account_owner(transaction.sender)
        assessment = self._risk_analyzer.assess_transaction(
            transaction,
            client_id=sender_owner.client_id,
            current_time=self._now(),
        )
        blocked = assessment.level == RiskLevel.HIGH
        self._risk_analyzer.record_assessment(
            sender_owner.client_id,
            transaction,
            assessment,
            blocked=blocked,
            succeeded=False,
            timestamp=self._now(),
        )

        if assessment.suspicious:
            event = "transaction_blocked_high_risk" if blocked else "transaction_risk_detected"
            level = AuditLevel.ERROR if blocked else AuditLevel.WARNING
            message = "High risk transaction blocked" if blocked else "Suspicious transaction detected"
            self._audit_logger.log(
                event,
                transaction,
                level=level,
                message=message,
                suspicious=True,
                risk_level=assessment.level,
                client_id=sender_owner.client_id,
                risk_score=assessment.score,
                risk_reasons=list(assessment.reasons),
            )

        if blocked:
            transaction.mark_failed("High risk operation blocked", self._now())
            queue.remove(transaction.transaction_id)
            return sender_owner.client_id, assessment

        return sender_owner.client_id, assessment

    def process_next(self, queue: TransactionQueue) -> Transaction | None:
        if not isinstance(queue, TransactionQueue):
            raise InvalidOperationError("process_next requires a TransactionQueue instance")

        transaction = queue.get_next_ready(self._now())
        if transaction is None:
            return None

        try:
            sender_client_id, assessment = self._assess_risk(queue, transaction)
        except InvalidOperationError as error:
            transaction.mark_failed(str(error), self._now())
            queue.remove(transaction.transaction_id)
            self._audit_logger.log(
                "transaction_failed",
                transaction,
                level=AuditLevel.ERROR,
                message="Transaction failed during risk evaluation",
                error=str(error),
            )
            return transaction

        if transaction.status == TransactionStatus.FAILED:
            return transaction

        try:
            plan = self._prepare_execution_plan(transaction)
            transaction.mark_processing(self._now())
            self._execute_plan(transaction, plan)
            transaction.mark_completed(self._now(), fee=plan["fee_amount"])
            queue.remove(transaction.transaction_id)
            if self._risk_analyzer is not None and sender_client_id is not None:
                self._risk_analyzer.mark_successful_transaction(sender_client_id, transaction)
            self._audit_logger.log(
                "transaction_completed",
                transaction,
                level=AuditLevel.INFO,
                message="Transaction completed successfully",
                suspicious=bool(assessment and assessment.suspicious),
                risk_level=assessment.level if assessment is not None else None,
                client_id=sender_client_id,
                fee=plan["fee_amount"],
                sender_debit_amount=plan["sender_debit_amount"],
                recipient_credit_amount=plan["recipient_credit_amount"],
            )
        except TemporaryProcessingError as error:
            self._handle_retry(queue, transaction, error)
        except (InvalidOperationError, InsufficientFundsError, AccountFrozenError, AccountClosedError) as error:
            transaction.mark_failed(str(error), self._now())
            queue.remove(transaction.transaction_id)
            self._audit_logger.log(
                "transaction_failed",
                transaction,
                level=AuditLevel.ERROR,
                message="Transaction failed due to business rule or account state",
                suspicious=bool(assessment and assessment.suspicious),
                risk_level=assessment.level if assessment is not None else None,
                client_id=sender_client_id,
                error=str(error),
            )
        except Exception as error:
            transaction.mark_failed(f"Unexpected processing error: {error}", self._now())
            queue.remove(transaction.transaction_id)
            self._audit_logger.log(
                "transaction_failed",
                transaction,
                level=AuditLevel.CRITICAL,
                message="Transaction failed due to unexpected processing error",
                suspicious=bool(assessment and assessment.suspicious),
                risk_level=assessment.level if assessment is not None else None,
                client_id=sender_client_id,
                error=str(error),
            )

        return transaction

    def process_all(self, queue: TransactionQueue, limit: int | None = None) -> list[Transaction]:
        if not isinstance(queue, TransactionQueue):
            raise InvalidOperationError("process_all requires a TransactionQueue instance")
        if limit is not None:
            require_positive_int(limit, "Processing limit")

        processed_transactions: list[Transaction] = []
        while limit is None or len(processed_transactions) < limit:
            transaction = self.process_next(queue)
            if transaction is None:
                break
            processed_transactions.append(transaction)
        return processed_transactions
