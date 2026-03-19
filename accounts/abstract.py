from abc import ABC, abstractmethod
import uuid
from enums import AccountStatus


class AbstractAccount(ABC):

    def __init__(self, owner: str, account_id: str | None = None):
        self._account_id = account_id or str(uuid.uuid4())
        self._owner = owner
        self._balance = 0.0
        self._status = AccountStatus.ACTIVE

    @abstractmethod
    def deposit(self, amount: float): ...

    @abstractmethod
    def withdraw(self, amount: float): ...

    @abstractmethod
    def get_account_info(self): ...