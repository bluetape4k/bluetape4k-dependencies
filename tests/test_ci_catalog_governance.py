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
    def test_pull_requests_use_repo_local_fixture_without_cloning_siblings(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        clone_step = workflow.split(
            "      - name: Clone managed repositories for catalog script checks\n",
            1,
        )[1].split("      - name:", 1)[0]
        self.assertIn("if: ${{ github.event_name != 'pull_request' }}", clone_step)

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


if __name__ == "__main__":
    unittest.main()
