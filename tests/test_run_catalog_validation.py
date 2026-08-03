from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "run-catalog-validation.py"
)
SPEC = importlib.util.spec_from_file_location("run_catalog_validation", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules["run_catalog_validation"] = runner
SPEC.loader.exec_module(runner)


class RunCatalogValidationTest(unittest.TestCase):
    def test_stage_budget_contract_totals_five_and_half_hours(self) -> None:
        self.assertEqual(
            tuple(stage.value for stage in runner.Stage),
            tuple(f"G{i}" for i in range(1, 9)),
        )
        self.assertEqual(runner.TRAIN_BUDGET_SECONDS, 330 * 60)
        self.assertEqual(runner.STAGE_BUDGET_SECONDS[runner.Stage.G6], 120 * 60)
        self.assertEqual(runner.STAGE_BUDGET_SECONDS[runner.Stage.G7], 60 * 60)
        self.assertEqual(runner.STAGE_BUDGET_SECONDS[runner.Stage.G8], 90 * 60)

    def test_child_environment_drops_credentials_proxies_ssh_and_gradle_injection(
        self,
    ) -> None:
        source = {
            "PATH": "/bin",
            "JAVA_HOME": "/jdk",
            "LANG": "C.UTF-8",
            "CENTRAL_PASSWORD": "secret",
            "HTTPS_PROXY": "http://proxy",
            "SSH_AUTH_SOCK": "/tmp/agent",
            "GRADLE_OPTS": "-I evil.gradle",
        }
        sanitized = runner.sanitized_environment(
            source, Path("/tmp/home"), Path("/tmp/gradle")
        )
        self.assertEqual(
            set(sanitized), {"PATH", "JAVA_HOME", "LANG", "HOME", "GRADLE_USER_HOME"}
        )

    def test_gradle_command_is_offline_and_rejects_publish_tasks(self) -> None:
        command = runner.gradle_command(("help",))
        for flag in (
            "--offline",
            "--no-daemon",
            "--no-configuration-cache",
            "--no-build-cache",
            "--console=plain",
        ):
            self.assertIn(flag, command)
        for task in ("publish", "signRelease", "uploadArchives"):
            with (
                self.subTest(task=task),
                self.assertRaisesRegex(RuntimeError, "forbidden"),
            ):
                runner.gradle_command((task,))

    def test_dynamic_versions_and_source_repositories_are_rejected(self) -> None:
        for text in (
            'version = "1.+"',
            'version = "latest.release"',
            'maven { url = uri("https://repo.example") }',
        ):
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(RuntimeError, "dynamic|repository"),
            ):
                runner.validate_build_text(text)

    def test_predecessor_contract_is_fail_closed(self) -> None:
        self.assertIsNone(runner.predecessor(runner.Stage.G1))
        self.assertEqual(runner.predecessor(runner.Stage.G6), runner.Stage.G5)
        with self.assertRaisesRegex(RuntimeError, "predecessor"):
            runner.require_predecessor(runner.Stage.G6, None, "a" * 64)
        receipt = {"stage": "G5", "status": "PASS", "manifest_sha256": "a" * 64}
        runner.require_predecessor(runner.Stage.G6, receipt, "a" * 64)
        receipt["manifest_sha256"] = "b" * 64
        with self.assertRaisesRegex(RuntimeError, "manifest"):
            runner.require_predecessor(runner.Stage.G6, receipt, "a" * 64)

    def test_evidence_root_uses_lowercase_full_catalog_sha(self) -> None:
        manifest = {
            "central_root": "/workspace/central",
            "catalog_lock": {"catalogs": {"central": {"sha256": "a" * 64}}},
        }
        self.assertEqual(
            runner.evidence_root(manifest),
            Path("/workspace/central/build/catalog-authority") / ("a" * 64),
        )
        manifest["catalog_lock"]["catalogs"]["central"]["sha256"] = "A" * 64
        with self.assertRaisesRegex(RuntimeError, "catalog SHA"):
            runner.evidence_root(manifest)


if __name__ == "__main__":
    unittest.main()
