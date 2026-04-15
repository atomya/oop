from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.enums import AuditLevel, RiskLevel


@dataclass(slots=True)
class AuditRecord:
    timestamp: datetime
    level: AuditLevel
    event: str
    entity_type: str
    entity_id: str | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    client_id: str | None = None
    account_id: str | None = None
    transaction_id: str | None = None
    suspicious: bool = False
    risk_level: RiskLevel | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(timespec="seconds"),
            "level": self.level.value,
            "event": self.event,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "message": self.message,
            "details": dict(self.details),
            "client_id": self.client_id,
            "account_id": self.account_id,
            "transaction_id": self.transaction_id,
            "suspicious": self.suspicious,
            "risk_level": self.risk_level.value if self.risk_level else None,
        }
