from datetime import date
from typing import Callable

from shared.enums import ClientStatus
from shared.exceptions import InvalidOperationError
from utils.unique_id import prepare_unique_id


class Client:
    _used_client_ids: set[str] = set()

    def __init__(
        self,
        full_name: str,
        birth_date: date,
        contacts: dict[str, str],
        pin_code,
        client_id: str | None = None,
        status: ClientStatus = ClientStatus.ACTIVE,
        today_provider: Callable[[], date] | None = None,
    ):
        self._today_provider = today_provider or date.today
        self._full_name = self._validate_full_name(full_name)
        self._birth_date = self._validate_birth_date(birth_date)
        self._ensure_adult(self._birth_date)
        self._contacts = self._validate_contacts(contacts)
        self._pin_code = self._validate_pin_code(pin_code)
        self._client_id = prepare_unique_id(
            client_id,
            used_ids=self._used_client_ids,
            label="Client ID",
            allow_int=False,
        )
        self._status = self._validate_status(status)
        self._account_ids: list[str] = []
        self._failed_login_attempts = 0
        self._suspicious_actions: list[str] = []

    @staticmethod
    def _validate_full_name(full_name: str) -> str:
        if not isinstance(full_name, str) or not full_name.strip():
            raise InvalidOperationError("Client full name must be a non-empty string")
        return full_name.strip()

    @staticmethod
    def _validate_birth_date(birth_date) -> date:
        if isinstance(birth_date, bool) or not isinstance(birth_date, date):
            raise InvalidOperationError("Client birth_date must be a date")
        return birth_date

    def _today(self) -> date:
        return self._today_provider()

    def _calculate_age(self, birth_date: date) -> int:
        today = self._today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age

    def _ensure_adult(self, birth_date: date) -> None:
        if self._calculate_age(birth_date) < 18:
            raise InvalidOperationError("Client must be at least 18 years old")

    @staticmethod
    def _validate_contacts(contacts: dict[str, str]) -> dict[str, str]:
        if not isinstance(contacts, dict) or not contacts:
            raise InvalidOperationError("Client contacts must be a non-empty dictionary")

        normalized_contacts = {}
        for contact_type, value in contacts.items():
            if not isinstance(contact_type, str) or not contact_type.strip():
                raise InvalidOperationError("Contact type must be a non-empty string")
            if not isinstance(value, str) or not value.strip():
                raise InvalidOperationError("Contact value must be a non-empty string")
            normalized_contacts[contact_type.strip()] = value.strip()

        return normalized_contacts

    @staticmethod
    def _validate_pin_code(pin_code) -> str:
        if isinstance(pin_code, bool):
            raise InvalidOperationError("PIN code must be a string or integer")

        if isinstance(pin_code, int):
            pin_code = str(pin_code)
        elif not isinstance(pin_code, str):
            raise InvalidOperationError("PIN code must be a string or integer")

        normalized_pin_code = pin_code.strip()
        if not normalized_pin_code:
            raise InvalidOperationError("PIN code cannot be empty")
        return normalized_pin_code

    @staticmethod
    def _validate_status(status: ClientStatus) -> ClientStatus:
        if not isinstance(status, ClientStatus):
            raise InvalidOperationError("Client status must be a ClientStatus enum")
        return status

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def birth_date(self) -> date:
        return self._birth_date

    @property
    def age(self) -> int:
        return self._calculate_age(self._birth_date)

    @property
    def contacts(self) -> dict[str, str]:
        return dict(self._contacts)

    @property
    def status(self) -> ClientStatus:
        return self._status

    @property
    def account_ids(self) -> list[str]:
        return list(self._account_ids)

    @property
    def failed_login_attempts(self) -> int:
        return self._failed_login_attempts

    @property
    def suspicious_actions(self) -> list[str]:
        return list(self._suspicious_actions)

    def register_account(self, account_id: str) -> None:
        if account_id not in self._account_ids:
            self._account_ids.append(account_id)

    def remove_account(self, account_id: str) -> None:
        if account_id in self._account_ids:
            self._account_ids.remove(account_id)

    def verify_pin_code(self, pin_code) -> bool:
        normalized_pin_code = self._validate_pin_code(pin_code)
        return self._pin_code == normalized_pin_code

    def record_failed_login(self) -> int:
        self._failed_login_attempts += 1
        return self._failed_login_attempts

    def reset_failed_logins(self) -> None:
        self._failed_login_attempts = 0

    def block(self) -> None:
        self._status = ClientStatus.BLOCKED

    def mark_suspicious_action(self, description: str) -> None:
        self._suspicious_actions.append(description)

    def get_client_info(self) -> dict:
        return {
            "id": self._client_id,
            "full_name": self._full_name,
            "birth_date": self._birth_date.isoformat(),
            "age": self.age,
            "status": self._status.value,
            "account_ids": list(self._account_ids),
            "contacts": dict(self._contacts),
            "failed_login_attempts": self._failed_login_attempts,
            "suspicious_actions": list(self._suspicious_actions),
        }

    def __str__(self) -> str:
        return (
            f"Client {self._full_name} "
            f"{self._client_id} "
            f"{self._status.value} "
            f"accounts={len(self._account_ids)}"
        )
