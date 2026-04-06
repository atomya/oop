from audit.base_audit_logger import BaseAuditLogger


class TransactionAuditLogger(BaseAuditLogger):
    def __init__(self, logger_name: str = __name__):
        super().__init__(logger_name)

    def _build_payload(self, transaction) -> dict:
        return dict(transaction.get_transaction_info())
