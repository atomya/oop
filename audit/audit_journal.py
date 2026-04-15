import json
from collections import Counter
from pathlib import Path

from audit.audit_record import AuditRecord
from shared.enums import AuditLevel, RiskLevel


class AuditJournal:
    def __init__(self, file_path: str | None = None):
        self._entries: list[AuditRecord] = []
        self._file_path = Path(file_path) if file_path is not None else None

    @property
    def entries(self) -> list[AuditRecord]:
        return list(self._entries)

    def record(self, entry: AuditRecord) -> None:
        self._entries.append(entry)
        if self._file_path is not None:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(entry.to_dict(), ensure_ascii=True, default=str))
                file.write("\n")

    def filter(
        self,
        *,
        level: AuditLevel | None = None,
        event: str | None = None,
        entity_type: str | None = None,
        client_id: str | None = None,
        transaction_id: str | None = None,
        suspicious_only: bool = False,
    ) -> list[AuditRecord]:
        filtered_entries = self._entries

        if level is not None:
            filtered_entries = [entry for entry in filtered_entries if entry.level == level]
        if event is not None:
            filtered_entries = [entry for entry in filtered_entries if entry.event == event]
        if entity_type is not None:
            filtered_entries = [entry for entry in filtered_entries if entry.entity_type == entity_type]
        if client_id is not None:
            filtered_entries = [entry for entry in filtered_entries if entry.client_id == client_id]
        if transaction_id is not None:
            filtered_entries = [entry for entry in filtered_entries if entry.transaction_id == transaction_id]
        if suspicious_only:
            filtered_entries = [entry for entry in filtered_entries if entry.suspicious]

        return list(filtered_entries)

    def suspicious_operations_report(self) -> list[dict]:
        suspicious_entries = self.filter(suspicious_only=True)
        return [entry.to_dict() for entry in suspicious_entries]

    def error_statistics(self) -> dict:
        error_entries = [
            entry
            for entry in self._entries
            if entry.level in (AuditLevel.ERROR, AuditLevel.CRITICAL)
        ]
        return {
            "total_errors": len(error_entries),
            "by_event": dict(Counter(entry.event for entry in error_entries)),
            "by_level": dict(Counter(entry.level.value for entry in error_entries)),
        }

    def client_risk_profile(self, client_id: str) -> dict:
        client_entries = self.filter(client_id=client_id)
        risk_entries = [entry for entry in client_entries if entry.risk_level is not None]
        risk_counter = Counter(entry.risk_level.value for entry in risk_entries)

        highest_risk = None
        if any(entry.risk_level == RiskLevel.HIGH for entry in risk_entries):
            highest_risk = RiskLevel.HIGH.value
        elif any(entry.risk_level == RiskLevel.MEDIUM for entry in risk_entries):
            highest_risk = RiskLevel.MEDIUM.value
        elif any(entry.risk_level == RiskLevel.LOW for entry in risk_entries):
            highest_risk = RiskLevel.LOW.value

        return {
            "client_id": client_id,
            "total_audit_entries": len(client_entries),
            "suspicious_operations": sum(1 for entry in client_entries if entry.suspicious),
            "risk_levels": dict(risk_counter),
            "highest_risk": highest_risk,
        }

    def save_to_file(self, file_path: str | None = None) -> None:
        target_path = Path(file_path) if file_path is not None else self._file_path
        if target_path is None:
            raise ValueError("AuditJournal file path is not configured")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w", encoding="utf-8") as file:
            for entry in self._entries:
                file.write(json.dumps(entry.to_dict(), ensure_ascii=True, default=str))
                file.write("\n")
