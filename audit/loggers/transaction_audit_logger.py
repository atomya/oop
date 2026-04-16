from audit.loggers.base_audit_logger import BaseAuditLogger


class TransactionAuditLogger(BaseAuditLogger):
    def __init__(self, logger_name: str = __name__, audit_journal=None, now_provider=None):
        super().__init__(logger_name, audit_journal=audit_journal, now_provider=now_provider)

    def _build_payload(self, transaction) -> dict:
        return dict(transaction.get_transaction_info())

    def _build_identifiers(self, payload: dict, extra: dict) -> dict:
        transaction_id = payload["transaction_id"]
        return {
            "entity_id": transaction_id,
            "client_id": extra.get("client_id"),
            "account_id": extra.get("account_id"),
            "transaction_id": transaction_id,
        }

    def _entity_type(self) -> str:
        return "transaction"
