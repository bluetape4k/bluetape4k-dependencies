from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-supply-chain-reports.py"
REPORT = REPO_ROOT / "config" / "supply-chain-report-only.json"
SCHEMA = REPO_ROOT / "config" / "supply-chain-report.schema.json"


def load_script():
    spec = importlib.util.spec_from_file_location("verify_supply_chain_reports", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load verify-supply-chain-reports.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupplyChainReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script()
        self.report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_baseline_report_is_valid_and_report_only(self) -> None:
        self.module.validate_schema_document(self.schema)

        summary = self.module.validate_report(self.report, as_of=date(2026, 8, 14))

        self.assertEqual(summary["records"], 7)
        self.assertEqual(summary["statuses"]["pass"], 2)
        self.assertEqual(summary["statuses"]["review"], 2)
        self.assertEqual(summary["statuses"]["not-applicable"], 3)
        self.assertEqual(summary["blocking-candidates"], [])
        self.assertEqual(summary["expired-exceptions"], [])

    def test_findings_are_not_a_failure_gate(self) -> None:
        report = copy.deepcopy(self.report)
        report["records"][0]["status"] = "blocked"
        report["records"][0]["severity"] = "critical"
        report["records"][0]["reachable"] = "yes"

        summary = self.module.validate_report(report, as_of=date(2026, 8, 14))

        self.assertEqual(summary["blocking-candidates"], ["gradle-catalog-authority"])

    def test_expired_exception_is_reported_but_schema_remains_valid(self) -> None:
        report = copy.deepcopy(self.report)
        record = report["records"][0]
        record["exception-id"] = "SC-001"
        record["exception-expiry"] = "2026-08-01"

        summary = self.module.validate_report(report, as_of=date(2026, 8, 14))

        self.assertEqual(summary["expired-exceptions"], ["gradle-catalog-authority"])

    def test_unknown_fields_and_unsorted_records_are_rejected(self) -> None:
        report = copy.deepcopy(self.report)
        report["records"][0]["unexpected"] = True
        with self.assertRaisesRegex(self.module.ReportError, "fields are not exact"):
            self.module.validate_report(report, as_of=date(2026, 8, 14))

        report = copy.deepcopy(self.report)
        report["records"] = list(reversed(report["records"]))
        with self.assertRaisesRegex(self.module.ReportError, "sorted by ecosystem and id"):
            self.module.validate_report(report, as_of=date(2026, 8, 14))

    def test_exception_fields_are_paired(self) -> None:
        report = copy.deepcopy(self.report)
        report["records"][0]["exception-expiry"] = "2026-09-01"

        with self.assertRaisesRegex(self.module.ReportError, "requires exception-id"):
            self.module.validate_report(report, as_of=date(2026, 8, 14))

    def test_cli_reads_the_checked_in_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.module.run(REPORT, SCHEMA, as_of=date(2026, 8, 14))
            self.assertEqual(result["as-of"], "2026-08-14")


if __name__ == "__main__":
    unittest.main()
