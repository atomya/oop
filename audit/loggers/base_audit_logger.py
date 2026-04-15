from abc import ABC, abstractmethod
from datetime import datetime
import logging

from audit.audit_record import AuditRecord
from audit.audit_journal import AuditJournal
from shared.enums import AuditLevel, RiskLevel


class BaseAuditLogger(ABC):
    def __init__(self, logger_name: str = __name__, audit_journal: AuditJournal | None = None):
        self._logger = logging.getLogger(logger_name)
        self._audit_journal = audit_journal

    def log(
        self,
        event: str,
        entity,
        *,
        level: AuditLevel = AuditLevel.INFO,
        message: str | None = None,
        suspicious: bool = False,
        risk_level: RiskLevel | None = None,
        **extra,
    ) -> None:
        payload = self._build_payload(entity)
        self._logger.log(self._logging_level(level), event, extra={**payload, **extra})

        if self._audit_journal is not None:
            identifiers = self._build_identifiers(payload, extra)
            self._audit_journal.record(
                AuditRecord(
                    timestamp=datetime.now(),
                    level=level,
                    event=event,
                    entity_type=self._entity_type(),
                    entity_id=identifiers.get("entity_id"),
                    message=message or event,
                    details={**payload, **extra},
                    client_id=identifiers.get("client_id"),
                    account_id=identifiers.get("account_id"),
                    transaction_id=identifiers.get("transaction_id"),
                    suspicious=suspicious,
                    risk_level=risk_level,
                )
            )

    @staticmethod
    def _logging_level(level: AuditLevel) -> int:
        return {
            AuditLevel.INFO: logging.INFO,
            AuditLevel.WARNING: logging.WARNING,
            AuditLevel.ERROR: logging.ERROR,
            AuditLevel.CRITICAL: logging.CRITICAL,
        }[level]

    @abstractmethod
    def _build_payload(self, entity) -> dict:
        pass

    @abstractmethod
    def _build_identifiers(self, payload: dict, extra: dict) -> dict:
        pass

    @abstractmethod
    def _entity_type(self) -> str:
        pass
