import logging
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from demo_support.scenario import run_demo
from services.report_builder import ReportBuilder


class ReportBuilderTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)
        cls.demo_result = run_demo()
        cls.selected_client = cls.demo_result["selected_client"]
        cls.builder = ReportBuilder(
            cls.demo_result["bank"],
            cls.demo_result["transactions"],
            cls.demo_result["audit_journal"],
        )

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_report_builder_creates_client_text_report(self):
        report = self.builder.build_client_report(self.selected_client.client_id)
        text_report = self.builder.build_text_report(report)

        self.assertEqual(report["report_type"], "client")
        self.assertEqual(report["entity"]["id"], self.selected_client.client_id)
        self.assertGreaterEqual(report["summary"]["total_accounts"], 1)
        self.assertEqual(len(report["charts"]), 3)
        self.assertIn(self.selected_client.full_name, text_report)
        self.assertIn("summary:", text_report)
        self.assertEqual(report["charts"][0]["title"], "Client Accounts by Currency")
        self.assertEqual(sum(report["charts"][0]["values"]), report["summary"]["total_accounts"])

    def test_report_builder_exports_bank_report_to_json_and_csv(self):
        report = self.builder.build_bank_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = self.builder.export_to_json(report, str(Path(temp_dir) / "bank_report.json"))
            csv_path = self.builder.export_to_csv(report, str(Path(temp_dir) / "bank_report.csv"))

            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())

            with json_path.open("r", encoding="utf-8") as file:
                json_data = json.load(file)
            self.assertEqual(json_data["report_type"], "bank")
            self.assertEqual(json_data["summary"]["bank_name"], self.demo_result["bank"].name)

            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("summary.total_clients", csv_text)
            self.assertIn("summary.total_balance", csv_text)

    def test_report_builder_saves_chart_files(self):
        report = self.builder.build_bank_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            saved_paths = self.builder.save_charts(report, temp_dir)

            self.assertEqual(len(saved_paths), 3)
            for saved_path in saved_paths:
                self.assertTrue(saved_path.exists())
                self.assertGreater(saved_path.stat().st_size, 0)

    def test_report_builder_creates_risk_report(self):
        report = self.builder.build_risk_report()

        self.assertEqual(report["report_type"], "risk")
        self.assertEqual(report["scope"], "bank")
        self.assertGreater(report["summary"]["suspicious_operations"], 0)
        self.assertGreaterEqual(len(report["client_profiles"]), 1)
        self.assertEqual(len(report["charts"]), 3)

    def test_report_builder_creates_client_scoped_risk_report(self):
        report = self.builder.build_risk_report(self.selected_client.client_id)

        self.assertEqual(report["report_type"], "risk")
        self.assertEqual(report["scope"], "client")
        self.assertEqual(report["client_profiles"], [])
        self.assertIn(self.selected_client.full_name, report["report_title"])

    def test_client_balance_chart_ends_with_current_total_balance(self):
        report = self.builder.build_client_report(self.selected_client.client_id)
        balance_chart = report["charts"][2]

        self.assertEqual(balance_chart["x_labels"][0], "opening_balance")
        self.assertEqual(
            Decimal(str(balance_chart["values"][-1])),
            report["summary"]["total_balance"],
        )

    def test_bank_balance_chart_ends_with_current_total_balance(self):
        report = self.builder.build_bank_report()
        balance_chart = report["charts"][2]

        self.assertEqual(balance_chart["x_labels"][0], "opening_balance")
        self.assertEqual(
            Decimal(str(balance_chart["values"][-1])),
            report["summary"]["total_balance"],
        )

    def test_bank_pie_chart_uses_account_counts_not_absolute_balances(self):
        report = self.builder.build_bank_report()
        pie_chart = report["charts"][0]

        self.assertEqual(pie_chart["title"], "Bank Accounts by Currency")
        self.assertEqual(sum(pie_chart["values"]), report["summary"]["total_accounts"])
        self.assertTrue(all(value >= 0 for value in pie_chart["values"]))


if __name__ == "__main__":
    unittest.main()
