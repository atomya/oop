import logging


class AccountAuditLogger:
    def __init__(self, logger_name: str = __name__):
        self._logger = logging.getLogger(logger_name)

    def log(self, event: str, account, **extra) -> None:
        account_info = dict(account.get_account_info())
        account_info["account_type"] = account_info.pop("type")
        self._logger.info(
            event,
            extra={
                **account_info,
                **extra,
            },
        )
