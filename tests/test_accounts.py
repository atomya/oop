import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from audit.account_audit_logger import AccountAuditLogger
from audit.base_audit_logger import BaseAuditLogger
from audit.transaction_audit_logger import TransactionAuditLogger
from accounts.types.investment.portfolio_position import PortfolioPosition
from domain.bank import Bank
from domain.client import Client
from shared.enums import AccountStatus, ClientStatus, Currency
from shared.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)
from services.account_service import AccountService
from services.transaction_processor import TransactionProcessor
from shared.enums import TransactionPriority, TransactionStatus, TransactionType
from shared.exceptions import TemporaryProcessingError
from transactions.transaction import Transaction
from transactions.transaction_queue import TransactionQueue


class FakeAuditLogger(BaseAuditLogger):
    def __init__(self):
        self.entries = []

    def _build_payload(self, entity) -> dict:
        return {}

    def log(self, event: str, entity, **extra) -> None:
        self.entries.append((event, entity, extra))


def build_client(
    full_name: str = "Alice Example",
    birth_date: date | None = None,
    contacts: dict[str, str] | None = None,
    pin_code="1234",
    client_id: str | None = None,
    status: ClientStatus = ClientStatus.ACTIVE,
    today_provider=None,
) -> Client:
    return Client(
        full_name=full_name,
        birth_date=birth_date if birth_date is not None else date(1990, 4, 3),
        contacts=contacts if contacts is not None else {"phone": "+10000000000", "email": "alice@example.com"},
        pin_code=pin_code,
        client_id=client_id,
        status=status,
        today_provider=today_provider,
    )


def build_transaction_bank(current_time: dict[str, datetime]):
    bank = Bank("Transaction Bank", now_provider=lambda: current_time["value"])
    audit_logger = FakeAuditLogger()
    account_service = AccountService(audit_logger)

    alice = build_client()
    bob = build_client()
    carol = build_client()
    dave = build_client()
    emma = build_client()

    for client in (alice, bob, carol, dave, emma):
        bank.add_client(client)

    alice_account = bank.open_account(alice.client_id, BankAccount, currency=Currency.USD)
    bob_account = bank.open_account(
        bob.client_id,
        SavingsAccount,
        currency=Currency.EUR,
        min_balance=0,
        monthly_interest_rate=0.01,
    )
    carol_account = bank.open_account(
        carol.client_id,
        PremiumAccount,
        currency=Currency.USD,
        overdraft_limit=500,
        withdrawal_limit=1000,
        fixed_fee=10,
    )
    dave_account = bank.open_account(dave.client_id, BankAccount, currency=Currency.USD)
    emma_account = bank.open_account(emma.client_id, BankAccount, currency=Currency.KZT)

    account_service.deposit(alice_account, 2000)
    account_service.deposit(carol_account, 50)
    bank.freeze_account(dave_account.account_id)

    return {
        "bank": bank,
        "audit_logger": audit_logger,
        "account_service": account_service,
        "alice_account": alice_account,
        "bob_account": bob_account,
        "carol_account": carol_account,
        "dave_account": dave_account,
        "emma_account": emma_account,
    }


class BankAccountTestCase(unittest.TestCase):
    def test_bank_account_generates_short_account_id(self):
        account = BankAccount("Alice", Currency.USD)

        self.assertEqual(len(account.account_id), 8)
        self.assertGreaterEqual(sum(char.isdigit() for char in account.account_id), 4)

    def test_bank_account_rejects_invalid_amounts(self):
        account = BankAccount("Alice", Currency.USD)

        with self.assertRaises(InvalidOperationError):
            account.deposit(True)

        with self.assertRaises(InvalidOperationError):
            account.deposit(0)

        with self.assertRaises(InvalidOperationError):
            account.withdraw("100")

    def test_bank_account_withdraws_successfully(self):
        account = BankAccount("Alice", Currency.USD)
        account.deposit(200)

        account.withdraw(50)

        self.assertEqual(account.balance, Decimal("150"))

    def test_bank_account_respects_status(self):
        frozen_account = BankAccount("Frozen", Currency.USD, status=AccountStatus.FROZEN)
        closed_account = BankAccount("Closed", Currency.USD, status=AccountStatus.CLOSED)

        with self.assertRaises(AccountFrozenError):
            frozen_account.deposit(100)

        with self.assertRaises(AccountClosedError):
            closed_account.deposit(100)

    def test_bank_account_withdraw_raises_on_insufficient_funds(self):
        account = BankAccount("Alice", Currency.USD)

        with self.assertRaises(InsufficientFundsError):
            account.withdraw(50)


class AccountConfigValidationTestCase(unittest.TestCase):
    def test_constructor_config_values_reject_invalid_inputs(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("Alice", Currency.USD, status="frozen")

        with self.assertRaises(InvalidOperationError):
            BankAccount("Alice", "USD")

        with self.assertRaises(InvalidOperationError):
            BankAccount("Alice", Currency.USD, account_id="ABCD12")

        with self.assertRaises(InvalidOperationError):
            BankAccount("Alice", Currency.USD, account_id="")

    def test_failed_account_validation_does_not_burn_account_id(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("Alice", "USD", account_id="ID12AB34")

        valid_account = BankAccount("Alice", Currency.USD, account_id="ID12AB34")
        self.assertEqual(valid_account.account_id, "ID12AB34")

        with self.assertRaises(InvalidOperationError):
            SavingsAccount(
                "Bob",
                Currency.EUR,
                min_balance="bad",
                monthly_interest_rate=0.03,
                account_id="ID56CD78",
            )

        valid_savings = SavingsAccount(
            "Bob",
            Currency.EUR,
            min_balance=100,
            monthly_interest_rate=0.03,
            account_id="ID56CD78",
        )
        self.assertEqual(valid_savings.account_id, "ID56CD78")

    def test_constructor_rejects_duplicate_account_id(self):
        BankAccount("Alice", Currency.USD, account_id="AB12CD34")

        with self.assertRaises(InvalidOperationError):
            BankAccount("Bob", Currency.USD, account_id="AB12CD34")

        with self.assertRaises(InvalidOperationError):
            SavingsAccount("Bob", Currency.EUR, min_balance=True, monthly_interest_rate=0.03)

        with self.assertRaises(InvalidOperationError):
            SavingsAccount("Bob", Currency.EUR, min_balance=100, monthly_interest_rate="bad")

        with self.assertRaises(InvalidOperationError):
            PremiumAccount(
                "Charlie",
                Currency.USD,
                overdraft_limit=500,
                withdrawal_limit=1000,
                fixed_fee=-1,
            )


class SavingsAccountTestCase(unittest.TestCase):
    def test_savings_account_respects_min_balance(self):
        account = SavingsAccount("Bob", Currency.EUR, min_balance=100, monthly_interest_rate=0.03)
        account.deposit(500)

        account.withdraw(300)
        self.assertEqual(account.balance, Decimal("200"))

        with self.assertRaises(InsufficientFundsError):
            account.withdraw(150)

    def test_savings_account_applies_monthly_interest(self):
        account = SavingsAccount("Bob", Currency.EUR, min_balance=0, monthly_interest_rate=0.05)
        account.deposit(1000)

        interest = account.apply_monthly_interest()

        self.assertEqual(interest, Decimal("50.00"))
        self.assertEqual(account.balance, Decimal("1050.00"))
        self.assertEqual(account.min_balance, Decimal("0"))
        self.assertEqual(account.monthly_interest_rate, Decimal("0.05"))


class PremiumAccountTestCase(unittest.TestCase):
    def test_premium_account_allows_overdraft_with_fee(self):
        account = PremiumAccount(
            "Charlie",
            Currency.USD,
            overdraft_limit=500,
            withdrawal_limit=1000,
            fixed_fee=10,
        )
        account.deposit(200)
        account.withdraw(600)

        self.assertEqual(account.balance, Decimal("-410"))

    def test_premium_account_enforces_withdrawal_limit(self):
        account = PremiumAccount(
            "Charlie",
            Currency.USD,
            overdraft_limit=500,
            withdrawal_limit=300,
            fixed_fee=10,
        )
        account.deposit(1000)

        with self.assertRaises(InvalidOperationError):
            account.withdraw(400)

    def test_premium_account_rejects_overdraft_beyond_limit(self):
        account = PremiumAccount(
            "Charlie",
            Currency.USD,
            overdraft_limit=500,
            withdrawal_limit=1000,
            fixed_fee=10,
        )
        account.deposit(100)

        with self.assertRaises(InsufficientFundsError):
            account.withdraw(600)

        self.assertEqual(account.overdraft_limit, Decimal("500"))
        self.assertEqual(account.withdrawal_limit, Decimal("1000"))
        self.assertEqual(account.fixed_fee, Decimal("10"))


class InvestmentAccountTestCase(unittest.TestCase):
    def test_investment_account_projects_growth(self):
        account = InvestmentAccount("Diana", Currency.USD)
        account.deposit(1000)
        account.invest_in_asset("stocks", 400)
        account.invest_in_asset("etf", 300)

        projection = account.project_yearly_growth()

        self.assertEqual(projection["stocks"], Decimal("448.00"))
        self.assertEqual(projection["etf"], Decimal("327.00"))
        self.assertEqual(account.balance, Decimal("300"))

    def test_investment_account_withdraws_and_rejects_over_investing(self):
        account = InvestmentAccount("Diana", Currency.USD)
        account.deposit(1000)
        account.withdraw(200)

        self.assertEqual(account.balance, Decimal("800"))

        with self.assertRaises(InsufficientFundsError):
            account.invest_in_asset("stocks", 900)

    def test_investment_account_withdraw_raises_on_insufficient_funds(self):
        account = InvestmentAccount("Diana", Currency.USD)
        account.deposit(100)

        with self.assertRaises(InsufficientFundsError):
            account.withdraw(200)

    def test_investment_account_can_sell_asset(self):
        account = InvestmentAccount("Diana", Currency.USD)
        account.deposit(1000)
        account.invest_in_asset("stocks", 400)

        account.sell_asset("stocks", 150)

        self.assertEqual(account.balance, Decimal("750"))
        self.assertEqual(account.portfolio["stocks"], Decimal("250"))

    def test_investment_account_rejects_invalid_asset_operations(self):
        account = InvestmentAccount("Diana", Currency.USD)
        account.deposit(1000)
        account.invest_in_asset("stocks", 400)
        balance_before = account.balance
        portfolio_before = dict(account.portfolio)

        with self.assertRaises(InvalidOperationError):
            account.invest_in_asset("crypto", 100)

        self.assertEqual(account.balance, balance_before)
        self.assertEqual(account.portfolio, portfolio_before)

        with self.assertRaises(InvalidOperationError):
            account.sell_asset("stocks", 500)


class AccountStringFormatTestCase(unittest.TestCase):
    def test_account_string_uses_masked_id_suffix(self):
        accounts = [
            BankAccount("Alice", Currency.USD, account_id="AB98CD76"),
            SavingsAccount("Bob", Currency.EUR, min_balance=0, monthly_interest_rate=0.02, account_id="87AB65CD43E21"),
            PremiumAccount(
                "Charlie",
                Currency.USD,
                overdraft_limit=500,
                withdrawal_limit=1000,
                fixed_fee=10,
                account_id="11AB22CD33EF44",
            ),
            InvestmentAccount("Diana", Currency.USD, account_id="ZX99CV88BN77"),
        ]

        for account in accounts:
            account_string = str(account)
            digits_only = "".join(char for char in account.account_id if char.isdigit())
            self.assertIn(f"****{digits_only[-4:]}", account_string)


class ClientTestCase(unittest.TestCase):
    def test_client_generates_id_and_rejects_invalid_client_id(self):
        generated_client = build_client()
        self.assertEqual(len(generated_client.client_id), 8)

        with self.assertRaises(InvalidOperationError):
            build_client(client_id="")

        with self.assertRaises(InvalidOperationError):
            build_client(client_id=True)

    def test_failed_client_validation_does_not_burn_client_id(self):
        with self.assertRaises(InvalidOperationError):
            build_client(client_id="client-201", status="blocked")

        valid_client = build_client(client_id="client-201")
        self.assertEqual(valid_client.client_id, "client-201")

        with self.assertRaises(InvalidOperationError):
            build_client(client_id="client-202", contacts={})

        valid_second_client = build_client(client_id="client-202")
        self.assertEqual(valid_second_client.client_id, "client-202")

    def test_client_rejects_invalid_status_contacts_and_pin_code(self):
        with self.assertRaises(InvalidOperationError):
            build_client(status="blocked")

        with self.assertRaises(InvalidOperationError):
            build_client(birth_date="1990-04-03")

        with self.assertRaises(InvalidOperationError):
            build_client(contacts={})

        with self.assertRaises(InvalidOperationError):
            build_client(contacts={"phone": "   "})

        with self.assertRaises(InvalidOperationError):
            build_client(pin_code=True)

        with self.assertRaises(InvalidOperationError):
            build_client(pin_code="   ")

    def test_client_rejects_underage_person_by_birth_date_boundary(self):
        today = date(2026, 4, 3)

        with self.assertRaises(InvalidOperationError):
            build_client(birth_date=date(2008, 4, 4), today_provider=lambda: today)

        adult_client = build_client(
            birth_date=date(2008, 4, 3),
            today_provider=lambda: today,
        )

        self.assertEqual(adult_client.age, 18)

    def test_client_tracks_accounts_and_status(self):
        client = build_client(client_id="client-001")

        client.register_account("AB12CD34")
        client.mark_suspicious_action("invalid_credentials")
        client.block()

        self.assertEqual(client.account_ids, ["AB12CD34"])
        self.assertEqual(client.status, ClientStatus.BLOCKED)
        self.assertEqual(client.suspicious_actions, ["invalid_credentials"])

    def test_client_age_accounts_for_month_and_day(self):
        client = build_client(
            birth_date=date(1990, 10, 15),
            today_provider=lambda: date(2026, 10, 14),
        )

        self.assertEqual(client.age, 35)

        exact_birthday_client = build_client(
            birth_date=date(1990, 10, 15),
            today_provider=lambda: date(2026, 10, 15),
        )

        self.assertEqual(exact_birthday_client.age, 36)


class BankTestCase(unittest.TestCase):
    def test_bank_adds_client_and_opens_account(self):
        bank = Bank("Test Bank", now_provider=lambda: datetime(2026, 4, 3, 10, 0))
        client = build_client(client_id="client-101")
        bank.add_client(client)

        account = bank.open_account(client.client_id, BankAccount, currency=Currency.USD)

        self.assertEqual(account.owner, client.full_name)
        self.assertIn(account.account_id, client.account_ids)
        self.assertEqual(bank.get_total_balance(), Decimal("0.00"))

    def test_bank_can_freeze_unfreeze_and_close_account(self):
        bank = Bank("Test Bank", now_provider=lambda: datetime(2026, 4, 3, 10, 0))
        client = build_client(client_id="client-102")
        bank.add_client(client)
        account = bank.open_account(client.client_id, BankAccount, currency=Currency.EUR)

        bank.freeze_account(account.account_id)
        self.assertEqual(account.status, AccountStatus.FROZEN)

        bank.unfreeze_account(account.account_id)
        self.assertEqual(account.status, AccountStatus.ACTIVE)

        bank.close_account(account.account_id)
        self.assertEqual(account.status, AccountStatus.CLOSED)
        self.assertEqual(client.account_ids, [])

    def test_bank_blocks_client_after_three_failed_logins(self):
        bank = Bank("Test Bank", now_provider=lambda: datetime(2026, 4, 3, 10, 0))
        client = build_client(client_id="client-103", pin_code="9999")
        bank.add_client(client)

        for _ in range(2):
            with self.assertRaises(InvalidOperationError):
                bank.authenticate_client(client.client_id, "1111")

        with self.assertRaises(InvalidOperationError):
            bank.authenticate_client(client.client_id, "1111")

        self.assertEqual(client.status, ClientStatus.BLOCKED)
        self.assertGreaterEqual(len(bank.suspicious_actions), 3)

    def test_bank_restricts_night_operations_and_marks_them_suspicious(self):
        bank = Bank("Night Bank", now_provider=lambda: datetime(2026, 4, 3, 1, 30))
        client = build_client(client_id="client-109")

        with self.assertRaises(InvalidOperationError):
            bank.add_client(client)

        self.assertEqual(len(bank.suspicious_actions), 1)
        self.assertEqual(bank.suspicious_actions[0]["action"], "add_client")
        self.assertEqual(bank.suspicious_actions[0]["reason"], "restricted_hours")

    def test_bank_restricts_night_authentication_and_account_operations(self):
        current_time = {"value": datetime(2026, 4, 3, 10, 0)}
        day_bank = Bank("Day Bank", now_provider=lambda: current_time["value"])
        client = build_client(client_id="client-110")
        day_bank.add_client(client)

        current_time["value"] = datetime(2026, 4, 3, 1, 30)

        with self.assertRaises(InvalidOperationError):
            day_bank.authenticate_client(client.client_id, "1234")

        with self.assertRaises(InvalidOperationError):
            day_bank.open_account(client.client_id, BankAccount, currency=Currency.USD)

        self.assertEqual(len(day_bank.suspicious_actions), 2)
        self.assertEqual(day_bank.suspicious_actions[0]["action"], "authenticate_client")
        self.assertEqual(day_bank.suspicious_actions[0]["reason"], "restricted_hours")
        self.assertEqual(day_bank.suspicious_actions[1]["action"], "open_account")
        self.assertEqual(day_bank.suspicious_actions[1]["reason"], "restricted_hours")

    def test_bank_searches_accounts_and_builds_ranking(self):
        bank = Bank("Ranking Bank", now_provider=lambda: datetime(2026, 4, 3, 12, 0))
        rich_client = build_client(full_name="Rich Client", client_id="client-105")
        basic_client = build_client(full_name="Basic Client", client_id="client-106")
        blocked_client = build_client(full_name="Blocked Client", client_id="client-107", status=ClientStatus.BLOCKED)
        bank.add_client(rich_client)
        bank.add_client(basic_client)
        bank.add_client(blocked_client)

        rich_account = bank.open_account(rich_client.client_id, BankAccount, currency=Currency.USD)
        basic_account = bank.open_account(basic_client.client_id, SavingsAccount, currency=Currency.EUR, min_balance=0, monthly_interest_rate=0.01)

        rich_account.deposit(1500)
        basic_account.deposit(500)

        search_result = bank.search_accounts(client_id=basic_client.client_id, account_type=SavingsAccount)
        ranking = bank.get_clients_ranking()
        full_ranking = bank.get_clients_ranking(only_active=False)

        self.assertEqual(search_result, [basic_account])
        self.assertEqual(ranking[0]["client_id"], rich_client.client_id)
        self.assertEqual(ranking[0]["total_balance"], Decimal("1500.00"))
        self.assertEqual(len(ranking), 2)
        self.assertEqual(len(full_ranking), 3)
        self.assertEqual(bank.get_total_balance(), Decimal("2000.00"))

    def test_bank_rejects_invalid_arguments_before_late_failures(self):
        bank = Bank("Validation Bank", now_provider=lambda: datetime(2026, 4, 3, 12, 0))
        client = build_client(client_id="client-108")
        bank.add_client(client)
        account = bank.open_account(client.client_id, BankAccount, currency=Currency.USD)

        with self.assertRaises(InvalidOperationError):
            bank.open_account(client.client_id, dict, currency=Currency.USD)

        with self.assertRaises(InvalidOperationError):
            bank.authenticate_client(123, "1234")

        with self.assertRaises(InvalidOperationError):
            bank.freeze_account("   ")

        with self.assertRaises(InvalidOperationError):
            bank.search_accounts(query=123)

        with self.assertRaises(InvalidOperationError):
            bank.search_accounts(query="   ")

        with self.assertRaises(InvalidOperationError):
            bank.search_accounts(status="active")

        with self.assertRaises(InvalidOperationError):
            bank.search_accounts(currency="USD")

        with self.assertRaises(InvalidOperationError):
            bank.search_accounts(account_type=dict)

        with self.assertRaises(InvalidOperationError):
            bank.get_clients_ranking(only_active="yes")

        self.assertEqual(account.status, AccountStatus.ACTIVE)


class AccountServiceTestCase(unittest.TestCase):
    def test_account_service_logs_operations(self):
        audit_logger = FakeAuditLogger()
        service = AccountService(audit_logger)
        account = InvestmentAccount("Diana", Currency.USD)

        service.deposit(account, 1000)
        service.invest_in_asset(account, "stocks", 400)

        self.assertEqual(account.balance, Decimal("600"))
        self.assertEqual(account.portfolio["stocks"], Decimal("400"))
        self.assertEqual(audit_logger.entries[0][0], "deposit")
        self.assertEqual(audit_logger.entries[1][0], "invest_in_asset")

    def test_account_service_logs_withdraw_interest_sell_and_projection(self):
        audit_logger = FakeAuditLogger()
        service = AccountService(audit_logger)
        savings = SavingsAccount("Bob", Currency.EUR, min_balance=0, monthly_interest_rate=0.05)
        investment = InvestmentAccount("Diana", Currency.USD)

        service.deposit(savings, 1000)
        service.apply_monthly_interest(savings)

        service.deposit(investment, 1000)
        service.withdraw(investment, 100)
        service.invest_in_asset(investment, "stocks", 300)
        service.sell_asset(investment, "stocks", 100)
        projection = service.project_yearly_growth(investment)

        self.assertEqual(audit_logger.entries[1][0], "apply_monthly_interest")
        self.assertEqual(audit_logger.entries[3][0], "withdraw")
        self.assertEqual(audit_logger.entries[5][0], "sell_asset")
        self.assertEqual(audit_logger.entries[6][0], "project_yearly_growth")
        self.assertIn("stocks", projection)


class PortfolioPositionTestCase(unittest.TestCase):
    def test_portfolio_position_rejects_non_positive_changes(self):
        position = PortfolioPosition("stocks")

        with self.assertRaises(InvalidOperationError):
            position.add(0)

        with self.assertRaises(InvalidOperationError):
            position.remove(0)


class AccountAuditLoggerTestCase(unittest.TestCase):
    def test_account_audit_logger_writes_structured_log(self):
        with patch("audit.base_audit_logger.logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            audit_logger = AccountAuditLogger("audit")
            account = SavingsAccount("Bob", Currency.EUR, min_balance=100, monthly_interest_rate=0.02)
            account.deposit(500)
            audit_logger.log("deposit", account, amount=500)

            mock_get_logger.assert_called_once_with("audit")
            mock_logger.info.assert_called_once()


class TransactionQueueTestCase(unittest.TestCase):
    def test_transaction_validation_failure_does_not_burn_transaction_id(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=10,
                currency="USD",
                sender="sender-invalid",
                recipient="recipient-invalid",
                transaction_id="tx-entity-001",
                created_at=datetime(2026, 4, 5, 12, 0),
            )

        valid_transaction = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=10,
            currency=Currency.USD,
            sender="sender-valid",
            recipient="recipient-valid",
            transaction_id="tx-entity-001",
            created_at=datetime(2026, 4, 5, 12, 0),
        )

        self.assertEqual(valid_transaction.transaction_id, "tx-entity-001")

    def test_transaction_queue_prioritizes_delays_and_can_cancel(self):
        current_time = {"value": datetime(2026, 4, 5, 12, 0)}
        queue = TransactionQueue(now_provider=lambda: current_time["value"])

        low_priority = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=10,
            currency=Currency.USD,
            sender="sender-1",
            recipient="external-1",
            priority=TransactionPriority.LOW,
            transaction_id="tx-low-001",
            created_at=current_time["value"],
        )
        high_priority = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=10,
            currency=Currency.USD,
            sender="sender-2",
            recipient="external-2",
            priority=TransactionPriority.HIGH,
            transaction_id="tx-high-001",
            created_at=current_time["value"],
        )
        delayed_transaction = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=10,
            currency=Currency.USD,
            sender="sender-3",
            recipient="external-3",
            priority=TransactionPriority.HIGH,
            scheduled_for=current_time["value"] + timedelta(hours=1),
            transaction_id="tx-delay-001",
            created_at=current_time["value"],
        )
        canceled_transaction = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=10,
            currency=Currency.USD,
            sender="sender-4",
            recipient="external-4",
            transaction_id="tx-cancel-001",
            created_at=current_time["value"],
        )

        for transaction in (low_priority, high_priority, delayed_transaction, canceled_transaction):
            queue.add(transaction)

        queue.cancel(canceled_transaction.transaction_id)

        pending_snapshot = queue.pending_transactions()
        self.assertIsInstance(pending_snapshot[0], dict)

        first = queue.get_next_ready(current_time["value"])
        queue.remove(first.transaction_id)
        second = queue.get_next_ready(current_time["value"])
        queue.remove(second.transaction_id)
        third = queue.get_next_ready(current_time["value"])

        self.assertEqual(first.transaction_id, high_priority.transaction_id)
        self.assertEqual(second.transaction_id, low_priority.transaction_id)
        self.assertIsNone(third)
        self.assertEqual(canceled_transaction.status, TransactionStatus.CANCELED)

        current_time["value"] = current_time["value"] + timedelta(hours=2)
        delayed_ready = queue.get_next_ready(current_time["value"])
        queue.remove(delayed_ready.transaction_id)
        self.assertEqual(delayed_ready.transaction_id, delayed_transaction.transaction_id)
        self.assertEqual(len(queue), 0)

    def test_transaction_queue_uses_fair_priority_cycle(self):
        current_time = {"value": datetime(2026, 4, 5, 12, 0)}
        queue = TransactionQueue(now_provider=lambda: current_time["value"])

        transactions = [
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=10,
                currency=Currency.USD,
                sender="sender-high-1",
                recipient="external-high-1",
                priority=TransactionPriority.HIGH,
                transaction_id="tx-cycle-high-001",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=10,
                currency=Currency.USD,
                sender="sender-high-2",
                recipient="external-high-2",
                priority=TransactionPriority.HIGH,
                transaction_id="tx-cycle-high-002",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=10,
                currency=Currency.USD,
                sender="sender-normal-1",
                recipient="external-normal-1",
                priority=TransactionPriority.NORMAL,
                transaction_id="tx-cycle-normal-001",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=10,
                currency=Currency.USD,
                sender="sender-normal-2",
                recipient="external-normal-2",
                priority=TransactionPriority.NORMAL,
                transaction_id="tx-cycle-normal-002",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=10,
                currency=Currency.USD,
                sender="sender-low-1",
                recipient="external-low-1",
                priority=TransactionPriority.LOW,
                transaction_id="tx-cycle-low-001",
                created_at=current_time["value"],
            ),
        ]

        for transaction in transactions:
            queue.add(transaction)

        pop_order = []
        while len(queue) > 0:
            next_transaction = queue.get_next_ready(current_time["value"])
            pop_order.append(next_transaction.transaction_id)
            queue.remove(next_transaction.transaction_id)

        self.assertEqual(
            pop_order,
            [
                "tx-cycle-high-001",
                "tx-cycle-normal-001",
                "tx-cycle-high-002",
                "tx-cycle-normal-002",
                "tx-cycle-low-001",
            ],
        )


class TransactionProcessorTestCase(unittest.TestCase):
    def test_transaction_processor_handles_conversion_external_fee_and_failures(self):
        current_time = {"value": datetime(2026, 4, 5, 12, 0)}
        transaction_setup = build_transaction_bank(current_time)
        bank = transaction_setup["bank"]
        alice_account = transaction_setup["alice_account"]
        bob_account = transaction_setup["bob_account"]
        dave_account = transaction_setup["dave_account"]

        audit_logger = FakeAuditLogger()
        processor = TransactionProcessor(
            bank,
            audit_logger,
            now_provider=lambda: current_time["value"],
        )
        queue = TransactionQueue(now_provider=lambda: current_time["value"])

        internal_transaction = Transaction(
            transaction_type=TransactionType.INTERNAL_TRANSFER,
            amount=100,
            currency=Currency.USD,
            sender=alice_account.account_id,
            recipient=bob_account.account_id,
            transaction_id="tx-proc-001",
            created_at=current_time["value"],
        )
        external_transaction = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=50,
            currency=Currency.USD,
            sender=alice_account.account_id,
            recipient="external-recipient-1",
            transaction_id="tx-proc-002",
            created_at=current_time["value"],
        )
        frozen_failure = Transaction(
            transaction_type=TransactionType.INTERNAL_TRANSFER,
            amount=20,
            currency=Currency.USD,
            sender=alice_account.account_id,
            recipient=dave_account.account_id,
            transaction_id="tx-proc-003",
            created_at=current_time["value"],
        )
        insufficient_failure = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=5000,
            currency=Currency.USD,
            sender=alice_account.account_id,
            recipient="external-recipient-2",
            transaction_id="tx-proc-004",
            created_at=current_time["value"],
        )

        for transaction in (
            internal_transaction,
            external_transaction,
            frozen_failure,
            insufficient_failure,
        ):
            queue.add(transaction)

        processed_transactions = processor.process_all(queue)

        self.assertEqual(len(processed_transactions), 4)
        self.assertEqual(internal_transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(external_transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(frozen_failure.status, TransactionStatus.FAILED)
        self.assertEqual(insufficient_failure.status, TransactionStatus.FAILED)
        self.assertEqual(bob_account.balance, Decimal("92.00"))
        self.assertEqual(alice_account.balance, Decimal("1849.00"))
        self.assertEqual(external_transaction.fee, Decimal("1.00"))
        self.assertGreaterEqual(len(audit_logger.entries), 4)

    def test_transaction_processor_retries_temporary_failures_without_losing_money(self):
        current_time = {"value": datetime(2026, 4, 5, 12, 0)}
        transaction_setup = build_transaction_bank(current_time)
        bank = transaction_setup["bank"]
        alice_account = transaction_setup["alice_account"]

        audit_logger = FakeAuditLogger()
        processor = TransactionProcessor(
            bank,
            audit_logger,
            now_provider=lambda: current_time["value"],
            retry_delay_minutes=5,
        )
        queue = TransactionQueue(now_provider=lambda: current_time["value"])
        transaction = Transaction(
            transaction_type=TransactionType.EXTERNAL_TRANSFER,
            amount=30,
            currency=Currency.USD,
            sender=alice_account.account_id,
            recipient="external-recipient-retry",
            transaction_id="tx-retry-001",
            created_at=current_time["value"],
        )
        queue.add(transaction)

        attempts = {"count": 0}

        def flaky_send(*_args, **_kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TemporaryProcessingError("Gateway unavailable")

        processor._send_external_transfer = flaky_send

        first_pass = processor.process_all(queue)
        self.assertEqual(len(first_pass), 1)
        self.assertEqual(transaction.status, TransactionStatus.SCHEDULED)
        self.assertEqual(transaction.retry_count, 1)
        self.assertEqual(alice_account.balance, Decimal("2000.00"))

        current_time["value"] = current_time["value"] + timedelta(minutes=6)
        second_pass = processor.process_all(queue)
        self.assertEqual(len(second_pass), 1)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(alice_account.balance, Decimal("1969.40"))

    def test_transaction_processor_executes_ten_queued_transactions(self):
        current_time = {"value": datetime(2026, 4, 5, 12, 0)}
        transaction_setup = build_transaction_bank(current_time)
        bank = transaction_setup["bank"]
        alice_account = transaction_setup["alice_account"]
        bob_account = transaction_setup["bob_account"]
        carol_account = transaction_setup["carol_account"]
        dave_account = transaction_setup["dave_account"]
        emma_account = transaction_setup["emma_account"]

        audit_logger = FakeAuditLogger()
        processor = TransactionProcessor(
            bank,
            audit_logger,
            now_provider=lambda: current_time["value"],
            retry_delay_minutes=5,
        )
        queue = TransactionQueue(now_provider=lambda: current_time["value"])

        transactions = [
            Transaction(
                transaction_type=TransactionType.INTERNAL_TRANSFER,
                amount=100,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient=bob_account.account_id,
                priority=TransactionPriority.HIGH,
                transaction_id="tx-batch-001",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=100,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient="external-batch-001",
                priority=TransactionPriority.NORMAL,
                transaction_id="tx-batch-002",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.INTERNAL_TRANSFER,
                amount=10,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient=emma_account.account_id,
                transaction_id="tx-batch-003",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.INTERNAL_TRANSFER,
                amount=20,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient=dave_account.account_id,
                transaction_id="tx-batch-004",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=5000,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient="external-batch-002",
                transaction_id="tx-batch-005",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=200,
                currency=Currency.USD,
                sender=carol_account.account_id,
                recipient="external-batch-003",
                transaction_id="tx-batch-006",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.INTERNAL_TRANSFER,
                amount=50,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient=bob_account.account_id,
                scheduled_for=current_time["value"] + timedelta(hours=1),
                transaction_id="tx-batch-007",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=25,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient="external-batch-004",
                transaction_id="tx-batch-008",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=30,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient="external-batch-retry",
                priority=TransactionPriority.HIGH,
                transaction_id="tx-batch-009",
                created_at=current_time["value"],
            ),
            Transaction(
                transaction_type=TransactionType.INTERNAL_TRANSFER,
                amount=15,
                currency=Currency.USD,
                sender=alice_account.account_id,
                recipient="missing-account-id",
                transaction_id="tx-batch-010",
                created_at=current_time["value"],
            ),
        ]

        for transaction in transactions:
            queue.add(transaction)

        queue.cancel("tx-batch-008")

        attempts = {"tx-batch-009": 0}

        def flaky_send(transaction, amount):
            if transaction.transaction_id == "tx-batch-009":
                attempts["tx-batch-009"] += 1
            if transaction.transaction_id == "tx-batch-009" and attempts["tx-batch-009"] == 1:
                raise TemporaryProcessingError("Temporary gateway timeout")

        processor._send_external_transfer = flaky_send

        first_batch = processor.process_all(queue)
        self.assertEqual(len(first_batch), 8)
        self.assertEqual(transactions[8].status, TransactionStatus.SCHEDULED)
        self.assertEqual(transactions[6].status, TransactionStatus.SCHEDULED)
        self.assertEqual(transactions[7].status, TransactionStatus.CANCELED)

        current_time["value"] = current_time["value"] + timedelta(hours=1, minutes=10)
        second_batch = processor.process_all(queue)
        self.assertEqual(len(second_batch), 2)
        self.assertEqual(len(queue), 0)

        completed = [transaction for transaction in transactions if transaction.status == TransactionStatus.COMPLETED]
        failed = [transaction for transaction in transactions if transaction.status == TransactionStatus.FAILED]
        canceled = [transaction for transaction in transactions if transaction.status == TransactionStatus.CANCELED]

        self.assertEqual(len(completed), 6)
        self.assertEqual(len(failed), 3)
        self.assertEqual(len(canceled), 1)
        self.assertEqual(alice_account.balance, Decimal("1707.40"))
        self.assertEqual(bob_account.balance, Decimal("138.00"))
        self.assertEqual(emma_account.balance, Decimal("4600.00"))
        self.assertEqual(carol_account.balance, Decimal("-164.00"))


class TransactionAuditLoggerTestCase(unittest.TestCase):
    def test_transaction_audit_logger_writes_structured_log(self):
        with patch("audit.base_audit_logger.logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            audit_logger = TransactionAuditLogger("transaction_audit")
            transaction = Transaction(
                transaction_type=TransactionType.EXTERNAL_TRANSFER,
                amount=100,
                currency=Currency.USD,
                sender="sender-logger",
                recipient="recipient-logger",
                transaction_id="tx-log-001",
                created_at=datetime(2026, 4, 5, 12, 0),
            )
            audit_logger.log("transaction_created", transaction, note="demo")

            mock_get_logger.assert_called_once_with("transaction_audit")
            mock_logger.info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
