from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from shared.enums import Currency, RiskLevel
from transactions.transaction import Transaction
from utils.currency import BASE_EXCHANGE_RATES, convert_currency_amount, validate_exchange_rates
from utils.validation import require_non_negative_decimal, require_non_negative_int, require_positive_int

from risk.risk_assessment import RiskAssessment


class RiskAnalyzer:
    def __init__(
        self,
        *,
        base_currency: Currency = Currency.USD,
        exchange_rates: dict[Currency, Decimal] | None = None,
        large_amount_threshold=Decimal("1000.00"),
        frequent_window_minutes: int = 10,
        frequent_operations_threshold: int = 3,
        now_provider=None,
    ):
        self._base_currency = base_currency
        self._exchange_rates = validate_exchange_rates(exchange_rates or BASE_EXCHANGE_RATES)
        self._large_amount_threshold = require_non_negative_decimal(
            large_amount_threshold,
            "Large amount threshold",
        )
        self._frequent_window = timedelta(
            minutes=require_positive_int(frequent_window_minutes, "Frequent window minutes")
        )
        self._frequent_operations_threshold = require_non_negative_int(
            frequent_operations_threshold,
            "Frequent operations threshold",
        )
        self._now_provider = now_provider or datetime.now
        self._operation_history: dict[str, list[datetime]] = defaultdict(list)
        self._known_recipients: dict[str, set[str]] = defaultdict(set)
        self._assessments_by_client: dict[str, list[RiskAssessment]] = defaultdict(list)
        self._blocked_operations_by_client: Counter = Counter()

    def _now(self) -> datetime:
        return self._now_provider()

    def _prune_history(self, client_id: str, current_time: datetime) -> list[datetime]:
        cutoff = current_time - self._frequent_window
        self._operation_history[client_id] = [
            timestamp
            for timestamp in self._operation_history[client_id]
            if timestamp >= cutoff
        ]
        return self._operation_history[client_id]

    def assess_transaction(
        self,
        transaction: Transaction,
        *,
        client_id: str,
        current_time: datetime | None = None,
    ) -> RiskAssessment:
        timestamp = current_time or self._now()
        recent_operations = self._prune_history(client_id, timestamp)
        amount_in_base_currency = convert_currency_amount(
            transaction.amount,
            transaction.currency,
            self._base_currency,
            self._exchange_rates,
        )

        score = 0
        reasons: list[str] = []

        if amount_in_base_currency >= self._large_amount_threshold:
            score += 40
            reasons.append("large_amount")

        if len(recent_operations) >= self._frequent_operations_threshold:
            score += 25
            reasons.append("frequent_operations")

        if transaction.recipient not in self._known_recipients[client_id]:
            score += 20
            reasons.append("new_recipient")

        if 0 <= timestamp.hour < 5:
            score += 30
            reasons.append("night_operation")

        if score >= 60:
            level = RiskLevel.HIGH
        elif score >= 30:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return RiskAssessment(score=score, level=level, reasons=reasons)

    def record_assessment(
        self,
        client_id: str,
        transaction: Transaction,
        assessment: RiskAssessment,
        *,
        blocked: bool = False,
        succeeded: bool = False,
        timestamp: datetime | None = None,
    ) -> None:
        current_time = timestamp or self._now()
        self._operation_history[client_id].append(current_time)
        self._prune_history(client_id, current_time)
        self._assessments_by_client[client_id].append(assessment)

        if blocked:
            self._blocked_operations_by_client[client_id] += 1

        if succeeded:
            self._known_recipients[client_id].add(transaction.recipient)

    def mark_successful_transaction(self, client_id: str, transaction: Transaction) -> None:
        self._known_recipients[client_id].add(transaction.recipient)

    def get_client_risk_profile(self, client_id: str) -> dict:
        assessments = self._assessments_by_client[client_id]
        risk_counts = Counter(assessment.level.value for assessment in assessments)

        highest_risk = RiskLevel.LOW.value
        if any(assessment.level == RiskLevel.HIGH for assessment in assessments):
            highest_risk = RiskLevel.HIGH.value
        elif any(assessment.level == RiskLevel.MEDIUM for assessment in assessments):
            highest_risk = RiskLevel.MEDIUM.value

        return {
            "client_id": client_id,
            "assessments_count": len(assessments),
            "risk_levels": dict(risk_counts),
            "highest_risk": highest_risk,
            "blocked_operations": self._blocked_operations_by_client[client_id],
            "known_recipients": len(self._known_recipients[client_id]),
            "recent_operations": len(self._operation_history[client_id]),
        }
