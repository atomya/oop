from datetime import datetime
from decimal import Decimal
from typing import Callable, TypeVar, overload

from accounts import BankAccount
from domain.client import Client
from shared.enums import AccountStatus, ClientStatus, Currency
from shared.exceptions import InvalidOperationError
from utils.currency import BASE_EXCHANGE_RATES, convert_currency_amount, validate_exchange_rates
from utils.validation import require_enum, require_non_empty_string

AccountType = TypeVar("AccountType", bound=BankAccount)


class Bank:
    def __init__(
        self,
        name: str,
        now_provider: Callable[[], datetime] | None = None,
        base_currency: Currency = Currency.USD,
        exchange_rates: dict[Currency, Decimal] | None = None,
    ):
        self._name = require_non_empty_string(name, "Bank name")
        self._clients: dict[str, Client] = {}
        self._accounts: dict[str, BankAccount] = {}
        self._account_owners: dict[str, str] = {}
        self._suspicious_actions: list[dict] = []
        self._now_provider = now_provider or datetime.now
        self._base_currency = require_enum(base_currency, Currency, "Base currency")
        self._exchange_rates = validate_exchange_rates(exchange_rates or BASE_EXCHANGE_RATES)

    @staticmethod
    def _validate_account_type(
        account_type: type[AccountType] | None,
        *,
        allow_none: bool = False,
    ) -> type[AccountType] | None:
        if account_type is None and allow_none:
            return None

        if not isinstance(account_type, type) or not issubclass(account_type, BankAccount):
            raise InvalidOperationError("Account type must inherit from BankAccount")
        return account_type

    @staticmethod
    def _validate_query(query: str | None) -> str | None:
        if query is None:
            return None
        return require_non_empty_string(query, "Search query").lower()

    @staticmethod
    def _validate_only_active(only_active) -> bool:
        if not isinstance(only_active, bool):
            raise InvalidOperationError("only_active must be a boolean")
        return only_active

    @property
    def name(self) -> str:
        return self._name

    @property
    def suspicious_actions(self) -> list[dict]:
        return list(self._suspicious_actions)

    @property
    def base_currency(self) -> Currency:
        return self._base_currency

    def _now(self) -> datetime:
        return self._now_provider()

    def _is_restricted_hours(self) -> bool:
        current_hour = self._now().hour
        return 0 <= current_hour < 5

    def _get_client(self, client_id: str) -> Client:
        client_id = require_non_empty_string(client_id, "Client ID")
        client = self._clients.get(client_id)
        if client is None:
            raise InvalidOperationError("Client not found")
        return client

    def _get_account(self, account_id: str) -> BankAccount:
        account_id = require_non_empty_string(account_id, "Account ID")
        account = self._accounts.get(account_id)
        if account is None:
            raise InvalidOperationError("Account not found")
        return account

    def get_account(self, account_id: str) -> BankAccount:
        return self._get_account(account_id)

    def has_account(self, account_id: str) -> bool:
        try:
            self._get_account(account_id)
        except InvalidOperationError:
            return False
        return True

    def get_account_owner(self, account_id: str) -> Client:
        account_id = require_non_empty_string(account_id, "Account ID")
        client_id = self._account_owners.get(account_id)
        if client_id is None:
            raise InvalidOperationError("Account owner not found")
        return self._get_client(client_id)

    def _mark_suspicious_action(self, action: str, client: Client | None = None, **details) -> None:
        timestamp = self._now().isoformat(timespec="seconds")
        suspicious_action = {
            "timestamp": timestamp,
            "action": action,
            "client_id": client.client_id if client else None,
            **details,
        }
        self._suspicious_actions.append(suspicious_action)

        if client is not None:
            client.mark_suspicious_action(action)

    def _ensure_operation_allowed(self, action: str, client: Client | None = None, **details) -> None:
        if self._is_restricted_hours():
            self._mark_suspicious_action(action, client=client, reason="restricted_hours", **details)
            raise InvalidOperationError("Operations are not allowed between 00:00 and 05:00")

    def ensure_operation_allowed(self, action: str, client_id: str | None = None, **details) -> None:
        client = self._get_client(client_id) if client_id is not None else None
        self._ensure_operation_allowed(action, client=client, **details)

    def _convert_to_base_currency(self, amount: Decimal, currency: Currency) -> Decimal:
        return convert_currency_amount(amount, currency, self._base_currency, self._exchange_rates)

    def add_client(self, client: Client) -> None:
        if not isinstance(client, Client):
            raise InvalidOperationError("Bank can only register Client instances")
        self._ensure_operation_allowed("add_client", client=client)
        if client.client_id in self._clients:
            raise InvalidOperationError("Client ID must be unique")
        self._clients[client.client_id] = client

    @overload
    def open_account(self, client_id: str, account_type: type[AccountType], **account_data) -> AccountType: ...

    @overload
    def open_account(self, client_id: str, account_type: type[BankAccount] = BankAccount, **account_data) -> BankAccount: ...

    def open_account(self, client_id: str, account_type: type[BankAccount] = BankAccount, **account_data) -> BankAccount:
        account_type = self._validate_account_type(account_type)
        client = self._get_client(client_id)
        self._ensure_operation_allowed("open_account", client=client)

        if client.status == ClientStatus.BLOCKED:
            raise InvalidOperationError("Blocked client cannot open new accounts")

        if "owner" in account_data:
            account_data.pop("owner")

        account = account_type(owner=client.full_name, **account_data)
        self._accounts[account.account_id] = account
        self._account_owners[account.account_id] = client.client_id
        client.register_account(account.account_id)
        return account

    def close_account(self, account_id: str) -> None:
        account = self._get_account(account_id)
        owner = self._get_client(self._account_owners[account_id])
        self._ensure_operation_allowed("close_account", client=owner, account_id=account_id)

        account.close()
        owner.remove_account(account_id)

    def freeze_account(self, account_id: str) -> None:
        account = self._get_account(account_id)
        owner = self._get_client(self._account_owners[account_id])
        self._ensure_operation_allowed("freeze_account", client=owner, account_id=account_id)
        account.freeze()

    def unfreeze_account(self, account_id: str) -> None:
        account = self._get_account(account_id)
        owner = self._get_client(self._account_owners[account_id])
        self._ensure_operation_allowed("unfreeze_account", client=owner, account_id=account_id)
        account.unfreeze()

    def authenticate_client(self, client_id: str, pin_code) -> Client:
        client = self._get_client(client_id)
        self._ensure_operation_allowed("authenticate_client", client=client)

        if client.status == ClientStatus.BLOCKED:
            self._mark_suspicious_action("authenticate_client", client=client, reason="blocked_client")
            raise InvalidOperationError("Client is blocked")

        if not client.verify_pin_code(pin_code):
            attempts = client.record_failed_login()
            self._mark_suspicious_action(
                "authenticate_client",
                client=client,
                reason="invalid_credentials",
                attempts=attempts,
            )

            if attempts >= 3:
                client.block()
                self._mark_suspicious_action(
                    "authenticate_client",
                    client=client,
                    reason="client_blocked_after_failed_attempts",
                    attempts=attempts,
                )
                raise InvalidOperationError("Client is blocked after 3 failed authentication attempts")

            raise InvalidOperationError("Invalid client credentials")

        client.reset_failed_logins()
        return client

    def search_accounts(
        self,
        query: str | None = None,
        client_id: str | None = None,
        status: AccountStatus | None = None,
        currency: Currency | None = None,
        account_type: type[BankAccount] | None = None,
    ) -> list[BankAccount]:
        query = self._validate_query(query)
        status = require_enum(status, AccountStatus, "Status", allow_none=True, article="an")
        currency = require_enum(currency, Currency, "Currency", allow_none=True)
        account_type = self._validate_account_type(account_type, allow_none=True)
        accounts = list(self._accounts.values())

        if client_id is not None:
            client = self._get_client(client_id)
            client_accounts = set(client.account_ids)
            accounts = [account for account in accounts if account.account_id in client_accounts]

        if query is not None:
            accounts = [
                account
                for account in accounts
                if query in account.account_id.lower() or query in account.owner.lower()
            ]

        if status is not None:
            accounts = [account for account in accounts if account.status == status]

        if currency is not None:
            accounts = [account for account in accounts if account.currency == currency]

        if account_type is not None:
            accounts = [account for account in accounts if isinstance(account, account_type)]

        return accounts

    def get_total_balance(self) -> Decimal:
        total = Decimal("0.00")
        for account in self._accounts.values():
            if account.status != AccountStatus.CLOSED:
                total += self._convert_to_base_currency(account.balance, account.currency)
        return total

    def get_clients_ranking(self, only_active: bool = True) -> list[dict]:
        only_active = self._validate_only_active(only_active)
        ranking = []

        for client in self._clients.values():
            if only_active and client.status != ClientStatus.ACTIVE:
                continue

            total_balance = Decimal("0.00")
            for account_id in client.account_ids:
                account = self._accounts[account_id]
                total_balance += self._convert_to_base_currency(account.balance, account.currency)

            ranking.append(
                {
                    "client_id": client.client_id,
                    "full_name": client.full_name,
                    "total_balance": total_balance,
                    "base_currency": self._base_currency.value,
                    "accounts_count": len(client.account_ids),
                    "status": client.status.value,
                }
            )

        return sorted(ranking, key=lambda item: item["total_balance"], reverse=True)
