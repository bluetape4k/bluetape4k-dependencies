from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate-supply-chain-report.py"
SOURCE_REPORT = REPO_ROOT / "config" / "supply-chain-report-only.json"


class GenerateSupplyChainReportTest(unittest.TestCase):
    def run_generator(
        self,
        directory: Path,
        *,
        train: str,
        generated_at: str,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
        report = directory / "supply-chain-report-only.json"
        metadata = directory / "supply-chain-triage.json"
        summary = directory / "supply-chain-summary.md"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source",
                str(SOURCE_REPORT),
                "--report",
                str(report),
                "--metadata",
                str(metadata),
                "--summary-output",
                str(summary),
                "--train",
                train,
                "--generated-at",
                generated_at,
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return result, report, metadata, summary

    def test_generator_records_run_scoped_report_and_triage_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            result, report_path, metadata_path, summary_path = self.run_generator(
                Path(temp_directory),
                train="2026-08-30-publish-snapshot-12345-1",
                generated_at="2026-08-30T12:00:00Z",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            summary = summary_path.read_text(encoding="utf-8")

            self.assertTrue(report["report-only"])
            self.assertEqual(report["train"], "2026-08-30-publish-snapshot-12345-1")
            self.assertEqual(report["generated-at"], "2026-08-30T12:00:00Z")
            self.assertEqual(len(report["records"]), 7)

            expected_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
            self.assertEqual(metadata["report-sha256"], expected_sha256)
            self.assertIn("report-path", metadata)
            self.assertEqual(metadata["report-path"], "supply-chain-report-only.json")
            self.assertEqual(metadata["train"], report["train"])
            self.assertIn("generate-supply-chain-report.py", metadata["command"])
            self.assertEqual(
                metadata["records"][0],
                {
                    "id": "gradle-catalog-authority",
                    "owner": "dependency-governance",
                    "evidence-url": "https://github.com/bluetape4k/bluetape4k-dependencies/blob/develop/config/latest-stable-version-audit.json",
                },
            )
            self.assertEqual(
                metadata["triage"]["review-records"],
                ["gradle-dependency-verification", "sbom-provenance-attestation"],
            )
            self.assertEqual(metadata["triage"]["false-positive-records"], [])
            self.assertEqual(metadata["triage"]["high-critical-reachable"], [])
            self.assertEqual(metadata["triage"]["expired-exceptions"], [])
            self.assertEqual(metadata["triage"]["exception-updates"], [])
            self.assertGreater(metadata["triage"]["duration-ms"], 0)
            datetime.fromisoformat(
                metadata["triage"]["started-at"].replace("Z", "+00:00")
            )
            datetime.fromisoformat(
                metadata["triage"]["completed-at"].replace("Z", "+00:00")
            )
            self.assertIn(expected_sha256, summary)
            self.assertIn("gradle-catalog-authority", summary)
            self.assertIn("dependency-governance", summary)
            self.assertIn("findings do not fail this gate", result.stdout)

    def test_each_train_gets_distinct_generation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()

            first_result, first_report, first_metadata, _ = self.run_generator(
                first,
                train="2026-08-30-publish-snapshot-12345-1",
                generated_at="2026-08-30T12:00:00Z",
            )
            second_result, second_report, second_metadata, _ = self.run_generator(
                second,
                train="2026-08-30-publish-snapshot-12346-1",
                generated_at="2026-08-30T12:05:00Z",
            )

            self.assertEqual(
                first_result.returncode, 0, first_result.stdout + first_result.stderr
            )
            self.assertEqual(
                second_result.returncode, 0, second_result.stdout + second_result.stderr
            )
            self.assertNotEqual(first_report.read_bytes(), second_report.read_bytes())
            self.assertNotEqual(
                json.loads(first_metadata.read_text(encoding="utf-8"))["report-sha256"],
                json.loads(second_metadata.read_text(encoding="utf-8"))[
                    "report-sha256"
                ],
            )

    def test_generator_rejects_a_source_that_is_not_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "source.json"
            source_document = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
            source_document["report-only"] = False
            source.write_text(json.dumps(source_document), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--report",
                    str(root / "report.json"),
                    "--metadata",
                    str(root / "metadata.json"),
                    "--summary-output",
                    str(root / "summary.md"),
                    "--train",
                    "2026-08-30-publish-snapshot-12345-1",
                    "--generated-at",
                    "2026-08-30T12:00:00Z",
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("source report-only must be true", result.stderr)


if __name__ == "__main__":
    unittest.main()
