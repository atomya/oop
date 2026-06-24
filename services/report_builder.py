from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from audit.audit_journal import AuditJournal
from domain.bank import Bank
from services.chart_renderer import MatplotlibChartRenderer
from services.report_output import CsvReportExporter, JsonReportExporter, TextReportFormatter
from shared.enums import AccountStatus, AuditLevel, RiskLevel, TransactionStatus, TransactionType
from shared.exceptions import InvalidOperationError
from transactions.transaction import Transaction


@dataclass(frozen=True, slots=True)
class TransactionBalanceEffect:
    sender_client_id: str
    recipient_client_id: str | None
    sender_debit_base: Decimal
    recipient_credit_base: Decimal

    @property
    def bank_delta(self) -> Decimal:
        return self.recipient_credit_base - self.sender_debit_base

    def delta_for_client(self, client_id: str) -> Decimal:
        delta = Decimal("0.00")
        if self.sender_client_id == client_id:
            delta -= self.sender_debit_base
        if self.recipient_client_id == client_id:
            delta += self.recipient_credit_base
        return delta


class ReportBuilder:
    def __init__(
        self,
        bank: Bank,
        transactions: list[Transaction] | None = None,
        audit_journal: AuditJournal | None = None,
        now_provider=None,
        text_formatter: TextReportFormatter | None = None,
        json_exporter: JsonReportExporter | None = None,
        csv_exporter: CsvReportExporter | None = None,
        chart_renderer: MatplotlibChartRenderer | None = None,
    ):
        if not isinstance(bank, Bank):
            raise InvalidOperationError("ReportBuilder requires a Bank instance")
        if transactions is None:
            normalized_transactions = []
        elif not isinstance(transactions, list) or any(not isinstance(item, Transaction) for item in transactions):
            raise InvalidOperationError("Transactions must be a list of Transaction instances")
        else:
            normalized_transactions = list(transactions)
        if audit_journal is not None and not isinstance(audit_journal, AuditJournal):
            raise InvalidOperationError("Audit journal must be an AuditJournal instance")

        self._bank = bank
        self._transactions = normalized_transactions
        self._audit_journal = audit_journal
        self._now_provider = now_provider or datetime.now
        self._text_formatter = text_formatter or TextReportFormatter()
        self._json_exporter = json_exporter or JsonReportExporter()
        self._csv_exporter = csv_exporter or CsvReportExporter()
        self._chart_renderer = chart_renderer or MatplotlibChartRenderer()
        self._completed_transaction_details_cache: dict[str, dict] | None = None

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _sanitize_filename_part(value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)

    def _ensure_audit_journal(self) -> AuditJournal:
        if self._audit_journal is None:
            raise InvalidOperationError("Audit journal is required for risk reports")
        return self._audit_journal

    def _get_client_account_ids(self, client_id: str) -> set[str]:
        return {account.account_id for account in self._bank.search_accounts(client_id=client_id)}

    def _get_client_accounts(self, client_id: str) -> list:
        return self._bank.search_accounts(client_id=client_id)

    def _get_completed_transactions(self) -> list[Transaction]:
        return sorted(
            [
                transaction
                for transaction in self._transactions
                if transaction.status == TransactionStatus.COMPLETED
            ],
            key=lambda item: (item.processed_at or item.created_at, item.transaction_id),
        )

    def _get_completed_transaction_details(self) -> dict[str, dict]:
        if self._completed_transaction_details_cache is not None:
            return self._completed_transaction_details_cache

        if self._audit_journal is None:
            self._completed_transaction_details_cache = {}
            return self._completed_transaction_details_cache

        details_by_transaction_id = {}
        for entry in self._audit_journal.filter(entity_type="transaction", event="transaction_completed"):
            if entry.transaction_id is None:
                continue
            details_by_transaction_id[entry.transaction_id] = dict(entry.details)

        self._completed_transaction_details_cache = details_by_transaction_id
        return self._completed_transaction_details_cache

    @staticmethod
    def _coerce_decimal(value) -> Decimal:
        return Decimal(str(value))

    def _get_transaction_balance_effect(self, transaction: Transaction) -> TransactionBalanceEffect:
        sender_account = self._bank.get_account(transaction.sender)
        sender_owner_id = self._bank.get_account_owner(transaction.sender).client_id
        transaction_details = self._get_completed_transaction_details().get(transaction.transaction_id, {})

        sender_debit_base = self._bank.convert_to_base_currency(transaction.amount, transaction.currency)
        if transaction.fee > 0:
            sender_debit_base += self._bank.convert_to_base_currency(transaction.fee, sender_account.currency)

        if "total_debit" in transaction_details:
            sender_total_debit = self._coerce_decimal(transaction_details["total_debit"])
            sender_debit_base = self._bank.convert_to_base_currency(sender_total_debit, sender_account.currency)

        recipient_owner_id = None
        recipient_credit_base = Decimal("0.00")
        if transaction.transaction_type == TransactionType.INTERNAL_TRANSFER and self._bank.has_account(transaction.recipient):
            recipient_account = self._bank.get_account(transaction.recipient)
            recipient_owner_id = self._bank.get_account_owner(transaction.recipient).client_id
            if "recipient_credit_amount" in transaction_details:
                recipient_credit_amount = self._coerce_decimal(transaction_details["recipient_credit_amount"])
                recipient_credit_base = self._bank.convert_to_base_currency(
                    recipient_credit_amount,
                    recipient_account.currency,
                )
            else:
                recipient_credit_base = self._bank.convert_to_base_currency(transaction.amount, transaction.currency)

        return TransactionBalanceEffect(
            sender_client_id=sender_owner_id,
            recipient_client_id=recipient_owner_id,
            sender_debit_base=sender_debit_base,
            recipient_credit_base=recipient_credit_base,
        )

    def _build_balance_movement_points(
        self,
        *,
        current_balance: Decimal,
        transactions: list[Transaction],
        delta_resolver,
    ) -> list[dict]:
        running_balance = current_balance
        for transaction in reversed(transactions):
            running_balance -= delta_resolver(transaction)

        points = [{"label": "opening_balance", "value": running_balance}]
        for transaction in transactions:
            running_balance += delta_resolver(transaction)
            points.append(
                {
                    "label": transaction.transaction_id,
                    "value": running_balance,
                }
            )
        return points

    def _build_client_balance_movement_chart(self, client_id: str) -> dict:
        completed_transactions = self._get_completed_transactions()
        client_balance_points = self._build_balance_movement_points(
            current_balance=self._get_client_total_balance(client_id),
            transactions=[
                transaction
                for transaction in completed_transactions
                if self._get_transaction_balance_effect(transaction).delta_for_client(client_id) != Decimal("0.00")
            ],
            delta_resolver=lambda transaction: self._get_transaction_balance_effect(transaction).delta_for_client(client_id),
        )

        return {
            "chart_type": "line",
            "filename": f"client_{self._sanitize_filename_part(client_id)}_balance_movement.png",
            "title": f"Client Balance Movement ({self._bank.base_currency.value})",
            "x_labels": [point["label"] for point in client_balance_points],
            "values": [point["value"] for point in client_balance_points],
            "y_label": f"Balance ({self._bank.base_currency.value})",
        }

    def _build_bank_balance_movement_chart(self) -> dict:
        completed_transactions = self._get_completed_transactions()
        bank_balance_points = self._build_balance_movement_points(
            current_balance=self._bank.get_total_balance(),
            transactions=completed_transactions,
            delta_resolver=lambda transaction: self._get_transaction_balance_effect(transaction).bank_delta,
        )

        return {
            "chart_type": "line",
            "filename": "bank_balance_movement.png",
            "title": f"Bank Balance Movement ({self._bank.base_currency.value})",
            "x_labels": [point["label"] for point in bank_balance_points],
            "values": [point["value"] for point in bank_balance_points],
            "y_label": f"Balance ({self._bank.base_currency.value})",
        }

    @staticmethod
    def _resolve_highest_risk(risk_levels: Counter) -> str | None:
        if risk_levels.get(RiskLevel.HIGH.value):
            return RiskLevel.HIGH.value
        if risk_levels.get(RiskLevel.MEDIUM.value):
            return RiskLevel.MEDIUM.value
        if risk_levels.get(RiskLevel.LOW.value):
            return RiskLevel.LOW.value
        return None

    def _get_client_transactions(self, client_id: str) -> list[dict]:
        client_account_ids = self._get_client_account_ids(client_id)
        history = []

        for transaction in sorted(self._transactions, key=lambda item: (item.created_at, item.transaction_id)):
            sender_is_client = transaction.sender in client_account_ids
            recipient_is_client = (
                self._bank.has_account(transaction.recipient)
                and self._bank.get_account_owner(transaction.recipient).client_id == client_id
            )
            if not sender_is_client and not recipient_is_client:
                continue

            if sender_is_client:
                direction = "outgoing"
                if self._bank.has_account(transaction.recipient):
                    counterparty = self._bank.get_account_owner(transaction.recipient).full_name
                else:
                    counterparty = transaction.recipient
                fee_paid = transaction.fee
            else:
                direction = "incoming"
                counterparty = self._bank.get_account_owner(transaction.sender).full_name
                fee_paid = Decimal("0.00")

            history.append(
                {
                    "transaction_id": transaction.transaction_id,
                    "direction": direction,
                    "counterparty": counterparty,
                    "status": transaction.status.value,
                    "type": transaction.transaction_type.value,
                    "amount": transaction.amount,
                    "currency": transaction.currency.value,
                    "fee_paid": fee_paid,
                    "created_at": transaction.created_at,
                    "finished_at": transaction.processed_at or transaction.failed_at or transaction.canceled_at,
                    "failure_reason": transaction.failure_reason,
                }
            )

        return history

    def _get_client_suspicious_operations(self, client_id: str) -> list[dict]:
        if self._audit_journal is None:
            return []
        return [
            entry.to_dict()
            for entry in self._audit_journal.filter(client_id=client_id, suspicious_only=True)
        ]

    def _get_client_total_balance(self, client_id: str) -> Decimal:
        total_balance = Decimal("0.00")
        for account in self._get_client_accounts(client_id):
            if account.status == AccountStatus.CLOSED:
                continue
            total_balance += self._bank.convert_to_base_currency(account.balance, account.currency)
        return total_balance

    def build_client_report(self, client_id: str) -> dict:
        client = self._bank.get_client(client_id)
        client_accounts = self._get_client_accounts(client.client_id)
        accounts = [account.get_account_info() for account in client_accounts]
        transactions = self._get_client_transactions(client.client_id)
        suspicious_operations = self._get_client_suspicious_operations(client.client_id)
        balances_by_currency: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        accounts_by_currency = Counter()
        account_balances = []

        for account in client_accounts:
            balances_by_currency[account.currency.value] += account.balance
            accounts_by_currency[account.currency.value] += 1
            account_balances.append(
                {
                    "label": account.account_id,
                    "value": account.balance,
                }
            )

        transaction_directions = Counter(item["direction"] for item in transactions)
        risk_profile = (
            self._audit_journal.client_risk_profile(client.client_id)
            if self._audit_journal is not None
            else {
                "client_id": client.client_id,
                "total_audit_entries": 0,
                "suspicious_operations": 0,
                "risk_levels": {},
                "highest_risk": None,
            }
        )

        report = {
            "report_type": "client",
            "report_title": f"Client Report: {client.full_name}",
            "generated_at": self._now(),
            "entity": client.get_client_info(),
            "summary": {
                "total_accounts": len(accounts),
                "active_accounts": sum(1 for account in accounts if account["status"] == AccountStatus.ACTIVE.value),
                "total_balance": self._get_client_total_balance(client.client_id),
                "base_currency": self._bank.base_currency.value,
                "balances_by_currency": dict(balances_by_currency),
                "total_transactions": len(transactions),
                "incoming_transactions": transaction_directions.get("incoming", 0),
                "outgoing_transactions": transaction_directions.get("outgoing", 0),
                "suspicious_transactions": len(suspicious_operations),
                "total_fees_paid": sum((item["fee_paid"] for item in transactions), start=Decimal("0.00")),
            },
            "accounts": accounts,
            "transactions": transactions,
            "risk_profile": risk_profile,
            "suspicious_operations": suspicious_operations,
        }

        report["charts"] = [
            {
                "chart_type": "pie",
                "filename": f"client_{self._sanitize_filename_part(client.client_id)}_accounts_by_currency.png",
                "title": "Client Accounts by Currency",
                "labels": list(accounts_by_currency.keys()) or ["no_accounts"],
                "values": list(accounts_by_currency.values()) or [1],
            },
            {
                "chart_type": "bar",
                "filename": f"client_{self._sanitize_filename_part(client.client_id)}_account_balances.png",
                "title": "Client Account Balances",
                "labels": [item["label"] for item in account_balances] or ["no_accounts"],
                "values": [item["value"] for item in account_balances] or [Decimal("0.00")],
                "y_label": "Balance",
            },
            self._build_client_balance_movement_chart(client.client_id),
        ]
        return report

    def build_bank_report(self) -> dict:
        clients = self._bank.list_clients()
        accounts = self._bank.search_accounts()
        transaction_statuses = Counter(transaction.status.value for transaction in self._transactions)
        account_statuses = Counter(account.status.value for account in accounts)
        balances_by_currency: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        accounts_by_currency = Counter()

        for account in accounts:
            if account.status != AccountStatus.CLOSED:
                balances_by_currency[account.currency.value] += account.balance
            accounts_by_currency[account.currency.value] += 1

        ranking = self._bank.get_clients_ranking(only_active=False)
        top_clients = ranking[:5]
        total_fees = sum((transaction.fee for transaction in self._transactions), start=Decimal("0.00"))
        suspicious_operations = (
            len(self._audit_journal.filter(suspicious_only=True))
            if self._audit_journal is not None
            else 0
        )
        error_statistics = (
            self._audit_journal.error_statistics()
            if self._audit_journal is not None
            else {
                "total_errors": 0,
                "by_event": {},
                "by_level": {},
            }
        )

        report = {
            "report_type": "bank",
            "report_title": f"Bank Report: {self._bank.name}",
            "generated_at": self._now(),
            "summary": {
                "bank_name": self._bank.name,
                "total_clients": len(clients),
                "active_clients": sum(1 for client in clients if client.status.value == "active"),
                "blocked_clients": sum(1 for client in clients if client.status.value == "blocked"),
                "total_accounts": len(accounts),
                "accounts_by_status": dict(account_statuses),
                "accounts_by_currency": dict(accounts_by_currency),
                "balances_by_currency": dict(balances_by_currency),
                "total_balance": self._bank.get_total_balance(),
                "base_currency": self._bank.base_currency.value,
                "total_transactions": len(self._transactions),
                "transactions_by_status": dict(transaction_statuses),
                "total_fees": total_fees,
                "suspicious_operations": suspicious_operations,
                "total_errors": error_statistics["total_errors"],
            },
            "top_clients": top_clients,
            "accounts": [account.get_account_info() for account in accounts],
            "transactions": [transaction.get_transaction_info() for transaction in self._transactions],
            "risk_overview": error_statistics,
        }

        report["charts"] = [
            {
                "chart_type": "pie",
                "filename": "bank_accounts_by_currency.png",
                "title": "Bank Accounts by Currency",
                "labels": list(accounts_by_currency.keys()) or ["no_accounts"],
                "values": list(accounts_by_currency.values()) or [1],
            },
            {
                "chart_type": "bar",
                "filename": "bank_top_clients.png",
                "title": "Top Clients by Balance",
                "labels": [item["full_name"] for item in top_clients] or ["no_clients"],
                "values": [item["total_balance"] for item in top_clients] or [Decimal("0.00")],
                "y_label": self._bank.base_currency.value,
            },
            self._build_bank_balance_movement_chart(),
        ]
        return report

    def build_risk_report(self, client_id: str | None = None) -> dict:
        audit_journal = self._ensure_audit_journal()
        filtered_entries = audit_journal.entries
        report_scope = "bank"
        report_title = f"Risk Report: {self._bank.name}"

        if client_id is not None:
            client = self._bank.get_client(client_id)
            filtered_entries = audit_journal.filter(client_id=client.client_id)
            report_scope = "client"
            report_title = f"Risk Report: {client.full_name}"

        suspicious_entries = [entry for entry in filtered_entries if entry.suspicious]
        risk_levels = Counter(entry.risk_level.value for entry in filtered_entries if entry.risk_level is not None)
        error_entries = [
            entry
            for entry in filtered_entries
            if entry.level in (AuditLevel.ERROR, AuditLevel.CRITICAL)
        ]
        suspicious_events = Counter(entry.event for entry in suspicious_entries)
        cumulative_suspicious = []
        suspicious_count = 0
        for entry in sorted(suspicious_entries, key=lambda item: item.timestamp):
            suspicious_count += 1
            cumulative_suspicious.append(
                {
                    "label": entry.timestamp.isoformat(timespec="seconds"),
                    "value": suspicious_count,
                }
            )

        if not cumulative_suspicious:
            cumulative_suspicious = [{"label": "no_activity", "value": 0}]

        report = {
            "report_type": "risk",
            "report_title": report_title,
            "generated_at": self._now(),
            "scope": report_scope,
            "summary": {
                "total_audit_entries": len(filtered_entries),
                "suspicious_operations": len(suspicious_entries),
                "risk_levels": dict(risk_levels),
                "highest_risk": self._resolve_highest_risk(risk_levels),
                "total_errors": len(error_entries),
                "error_events": dict(Counter(entry.event for entry in error_entries)),
            },
            "suspicious_operations": [entry.to_dict() for entry in suspicious_entries],
            "errors": [entry.to_dict() for entry in error_entries],
            "client_profiles": [],
        }

        if client_id is None:
            client_profiles = []
            for client in self._bank.list_clients():
                profile = audit_journal.client_risk_profile(client.client_id)
                if profile["total_audit_entries"] > 0:
                    client_profiles.append(profile)
            report["client_profiles"] = client_profiles

        report["charts"] = [
            {
                "chart_type": "pie",
                "filename": f"{report_scope}_risk_levels.png",
                "title": "Risk Levels Distribution",
                "labels": list(risk_levels.keys()) or ["no_risk"],
                "values": list(risk_levels.values()) or [1],
            },
            {
                "chart_type": "bar",
                "filename": f"{report_scope}_suspicious_events.png",
                "title": "Suspicious Events",
                "labels": list(suspicious_events.keys()) or ["no_events"],
                "values": list(suspicious_events.values()) or [0],
                "y_label": "Events",
            },
            {
                "chart_type": "line",
                "filename": f"{report_scope}_suspicious_timeline.png",
                "title": "Suspicious Operations Timeline",
                "x_labels": [point["label"] for point in cumulative_suspicious],
                "values": [point["value"] for point in cumulative_suspicious],
                "y_label": "Cumulative Suspicious Operations",
            },
        ]
        return report

    def build_text_report(self, report: dict) -> str:
        return self._text_formatter.format(report)

    def render_text_report(self, report: dict) -> str:
        return self.build_text_report(report)

    def export_to_json(self, report: dict, file_path) -> Path:
        return self._json_exporter.export(report, file_path)

    def export_to_csv(self, report: dict, file_path) -> Path:
        return self._csv_exporter.export(report, file_path)

    def save_charts(self, report: dict, output_dir) -> list[Path]:
        if not isinstance(report, dict) or not isinstance(report.get("charts"), list):
            raise InvalidOperationError("Report must contain chart specifications")
        return self._chart_renderer.save(report["charts"], output_dir)
