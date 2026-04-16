from audit.loggers.base_audit_logger import BaseAuditLogger


class AccountAuditLogger(BaseAuditLogger):
    def __init__(self, logger_name: str = __name__, audit_journal=None, now_provider=None):
        super().__init__(logger_name, audit_journal=audit_journal, now_provider=now_provider)

    def _build_payload(self, account) -> dict:
        payload = dict(account.get_account_info())
        payload["account_type"] = payload.pop("type")
        return payload

    def _build_identifiers(self, payload: dict, extra: dict) -> dict:
        account_id = payload["id"]
        return {
            "entity_id": account_id,
            "account_id": account_id,
            "client_id": extra.get("client_id"),
            "transaction_id": extra.get("transaction_id"),
        }

    def _entity_type(self) -> str:
        return "account"
