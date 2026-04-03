import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from domain.bank import Bank
from domain.client import Client
from shared.enums import AccountStatus, ClientStatus, Currency
from shared.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)
from accounts.types.investment.portfolio_position import PortfolioPosition
from services.account_audit_logger import AccountAuditLogger
from services.account_service import AccountService


class FakeAuditLogger:
    def __init__(self):
        self.entries = []

    def log(self, event: str, account, **extra) -> None:
        self.entries.append((event, account, extra))


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
        client = build_client(client_id="client-104")
        bank.add_client(client)

        with self.assertRaises(InvalidOperationError):
            bank.open_account(client.client_id, BankAccount, currency=Currency.USD)

        self.assertEqual(len(bank.suspicious_actions), 1)
        self.assertEqual(bank.suspicious_actions[0]["reason"], "restricted_hours")

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
        with patch("services.account_audit_logger.logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            audit_logger = AccountAuditLogger("audit")
            account = SavingsAccount("Bob", Currency.EUR, min_balance=100, monthly_interest_rate=0.02)
            account.deposit(500)
            audit_logger.log("deposit", account, amount=500)

            mock_get_logger.assert_called_once_with("audit")
            mock_logger.info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
