from audit.base_audit_logger import BaseAuditLogger


class AccountAuditLogger(BaseAuditLogger):
    def __init__(self, logger_name: str = __name__):
        super().__init__(logger_name)

    def _build_payload(self, account) -> dict:
        payload = dict(account.get_account_info())
        payload["account_type"] = payload.pop("type")
        return payload
