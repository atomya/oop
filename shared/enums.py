from enum import Enum


class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class ClientStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class Currency(Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


class TransactionType(Enum):
    INTERNAL_TRANSFER = "internal_transfer"
    EXTERNAL_TRANSFER = "external_transfer"


class TransactionStatus(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TransactionPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


class AuditLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
