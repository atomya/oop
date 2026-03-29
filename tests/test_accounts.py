import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from accounts import (
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from enums import AccountStatus, Currency
from exceptions import (
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


class BankAccountTestCase(unittest.TestCase):
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

        with self.assertRaises(InvalidOperationError):
            account.invest_in_asset("crypto", 100)

        with self.assertRaises(InvalidOperationError):
            account.sell_asset("stocks", 500)


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
