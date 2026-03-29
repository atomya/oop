from abc import ABC, abstractmethod
import uuid
from decimal import Decimal
from enums import AccountStatus


class AbstractAccount(ABC):

    def __init__(self, owner: str, account_id: str | None = None, status: AccountStatus = AccountStatus.ACTIVE):
        self._account_id = account_id or str(uuid.uuid4())
        self._owner = owner
        self._balance = Decimal("0.00")
        self._status = status

    @abstractmethod
    def deposit(self, amount): ...

    @abstractmethod
    def withdraw(self, amount): ...

    @abstractmethod
    def get_account_info(self): ...

    @abstractmethod
    def __str__(self): ...
