from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_WORKSPACE = REPO_ROOT / "tests" / "fixtures" / "catalog-adoption-clean"
GUARD = REPO_ROOT / "scripts" / "sync-shared-versions.py"


class CatalogGovernanceCiTest(unittest.TestCase):
    def test_ci_checks_the_latest_stable_inventory(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        script_step = workflow.split(
            "      - name: Verify catalog scripts\n",
            1,
        )[1].split("      - name:", 1)[0]

        self.assertIn("scripts/audit-latest-stable.py", script_step)
        self.assertIn("scripts/verify-latest-stable-resolved-graphs.py", script_step)
        self.assertIn(
            "scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary",
            script_step,
        )

    def test_pull_requests_use_repo_local_fixture_for_the_adoption_guard(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        clone_step = workflow.split(
            "      - name: Clone managed repositories for catalog script checks\n",
            1,
        )[1].split("      - name:", 1)[0]
        self.assertNotIn("if: ${{ github.event_name != 'pull_request' }}", clone_step)
        self.assertIn("scripts/sync-shared-versions.py --print-default-repositories", clone_step)

        fixture_step = workflow.split(
            "      - name: Verify PR-safe catalog adoption guard\n",
            1,
        )[1].split("      - name:", 1)[0]
        self.assertIn("if: ${{ github.event_name == 'pull_request' }}", fixture_step)
        self.assertIn("--workspace tests/fixtures/catalog-adoption-clean", fixture_step)
        self.assertIn("--repo bluetape4k-projects", fixture_step)
        self.assertIn("--check --summary", fixture_step)

    def test_pull_request_fixture_passes_the_real_guard_cli(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(GUARD),
                "--workspace",
                str(FIXTURE_WORKSPACE),
                "--repo",
                "bluetape4k-projects",
                "--check",
                "--summary",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Central catalog adoption is clean.", result.stdout)

    def test_full_workspace_audit_remains_non_pull_request_only(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        audit_step = workflow.split(
            "      - name: Verify downstream repository sync\n",
            1,
        )[1].split("      - uses:", 1)[0]

        self.assertIn("if: ${{ github.event_name != 'pull_request' }}", audit_step)
        self.assertIn("sync-shared-versions.py --workspace .. --check --summary", audit_step)
        self.assertIn("sync-dependabot-ignores.py --workspace .. --check --summary", audit_step)

    def test_ci_runs_cross_repository_publication_pom_contract(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        job = workflow.split("  publication-pom-contract:\n", 1)[1].split("  ci-status:\n", 1)[0]

        self.assertIn("timeout-minutes: 30", job)
        self.assertIn("scripts/verify-publication-poms.py --print-default-repositories", job)
        self.assertIn("scripts/verify-publication-poms.py --workspace .. --summary", job)
        self.assertIn("uses: actions/setup-java@v5", job)
        self.assertIn("uses: gradle/actions/setup-gradle@v6", job)

        status_job = workflow.split("  ci-status:\n", 1)[1]
        self.assertIn("- publication-pom-contract", status_job)


if __name__ == "__main__":
    unittest.main()
