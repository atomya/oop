from abc import ABC, abstractmethod
import logging


class BaseAuditLogger(ABC):
    def __init__(self, logger_name: str = __name__):
        self._logger = logging.getLogger(logger_name)

    def log(self, event: str, entity, **extra) -> None:
        payload = self._build_payload(entity)
        self._logger.info(event, extra={**payload, **extra})

    @abstractmethod
    def _build_payload(self, entity) -> dict:
        pass
