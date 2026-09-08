from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_WORKSPACE = REPO_ROOT / "tests" / "fixtures" / "catalog-adoption-clean"
GUARD = REPO_ROOT / "scripts" / "sync-shared-versions.py"


class CatalogGovernanceCiTest(unittest.TestCase):
    def test_development_checkout_selection_preserves_the_signing_checkout(
        self,
    ) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = "      - name: Clone development verification repositories\n"
        self.assertIn(marker, workflow)
        step = workflow.split(marker, 1)[1].split("      - name:", 1)[0]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        from tests.test_post_publish_next_development_line import (
            create_catalog_history,
            run_git,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "signing-checkout"
            refs = create_catalog_history(source)
            candidate = subprocess.check_output(
                [
                    sys.executable,
                    str(
                        REPO_ROOT
                        / "scripts/verify-post-publish-next-development-line.py"
                    ),
                    "--print-snapshot-candidate-branch",
                ],
                text=True,
            ).strip()
            run_git(source, "branch", candidate, refs["forward"])
            run_git(source, "checkout", "--detach", refs["minimum"])
            for status, expected in (
                (200, refs["forward"]),
                (404, refs["candidate"]),
                (403, None),
            ):
                with self.subTest(status=status):
                    runner_temp = root / str(status)
                    runner_temp.mkdir()
                    environment = dict(
                        os.environ,
                        RUNNER_TEMP=str(runner_temp),
                        FIXTURE_SOURCE=str(source),
                        LOOKUP_STATUS=str(status),
                    )
                    # GitHub 호출만 대체하고 checkout과 ref 선택은 실제 Git으로 검증한다.
                    github_fixture = """
gh() {
  if [ "$1" = api ]; then
    if [ "$LOOKUP_STATUS" = 200 ]; then return 0; fi
    echo "gh: lookup failed (HTTP $LOOKUP_STATUS)" >&2
    return 1
  fi
  local destination="$4"
  shift 5
  git clone "$FIXTURE_SOURCE" "$destination" "$@"
}
"""
                    result = subprocess.run(
                        ["bash", "-c", github_fixture + script],
                        cwd=REPO_ROOT,
                        env=environment,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    )
                    if expected is None:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("snapshot candidate lookup failed", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        graph = runner_temp / "development-workspace/bluetape4k-graph"
                        self.assertEqual(run_git(graph, "rev-parse", "HEAD"), expected)
                    self.assertEqual(
                        run_git(source, "rev-parse", "HEAD"), refs["minimum"]
                    )
                    self.assertEqual(run_git(source, "status", "--porcelain"), "")

    def test_development_guard_uses_a_separate_checkout_from_signing(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "      - name: Clone development verification repositories\n", workflow
        )
        clone_step = workflow.split(
            "      - name: Clone development verification repositories\n", 1
        )[1].split("      - name:", 1)[0]
        self.assertIn('"$RUNNER_TEMP/development-workspace/${repo}"', clone_step)
        self.assertNotIn("signing_sha", clone_step)
        self.assertIn('grep -Fq "(HTTP 404)"', clone_step)
        self.assertIn("snapshot candidate lookup failed", clone_step)
        self.assertIn(
            '--summary --workspace "$RUNNER_TEMP/development-workspace"', workflow
        )

    def test_ci_validates_supply_chain_reports_without_promoting_findings(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        report_job = workflow.split("  supply-chain-report-only:\n", 1)[1].split(
            "  ci-status:\n", 1
        )[0]
        status_job = workflow.split("  ci-status:\n", 1)[1]

        self.assertIn("name: Supply-chain Report (report-only)", report_job)
        self.assertIn(
            "python3 scripts/verify-supply-chain-reports.py --summary", report_job
        )
        self.assertIn("- supply-chain-report-only", status_job)

    def test_ci_checks_the_latest_stable_inventory(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        script_step = workflow.split(
            "      - name: Verify catalog scripts\n",
            1,
        )[1].split("      - name:", 1)[0]

        self.assertIn("scripts/audit-latest-stable.py", script_step)
        self.assertIn("scripts/verify-latest-stable-resolved-graphs.py", script_step)
        self.assertIn("scripts/verify-post-publish-next-development-line.py", script_step)
        self.assertIn(
            "scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary",
            script_step,
        )
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py --summary",
            script_step,
        )
        self.assertIn(
            'if [[ "${GITHUB_REF}" == "refs/heads/develop" || "${GITHUB_BASE_REF:-}" == "develop" ]]; then',
            script_step,
        )

    def test_publish_workflows_guard_the_development_line_and_stable_boundary(self) -> None:
        snapshot_workflow = (REPO_ROOT / ".github" / "workflows" / "publish-snapshot.yml").read_text(
            encoding="utf-8"
        )
        release_workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py --summary\n",
            snapshot_workflow,
        )
        clone_command = (
            "python3 scripts/verify-post-publish-next-development-line.py "
            "--print-required-repositories"
        )
        self.assertIn(clone_command, snapshot_workflow)
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py "
            "--print-snapshot-candidate-branch",
            snapshot_workflow,
        )
        self.assertIn('--branch "$candidate_branch" --single-branch', snapshot_workflow)
        self.assertLess(
            snapshot_workflow.index(clone_command),
            snapshot_workflow.index(
                "python3 scripts/verify-post-publish-next-development-line.py --summary\n"
            ),
        )
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py --summary --require-artifacts",
            snapshot_workflow,
        )
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py --stable-release",
            release_workflow,
        )

    def test_publish_snapshot_uploads_a_run_scoped_supply_chain_report(self) -> None:
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "publish-snapshot.yml"
        ).read_text(encoding="utf-8")

        publish_verification = (
            "python3 scripts/verify-post-publish-next-development-line.py "
            "--summary --require-artifacts"
        )
        generation = "python3 scripts/generate-supply-chain-report.py"
        validation = (
            "python3 scripts/verify-supply-chain-reports.py "
            "--report build/supply-chain-report/supply-chain-report-only.json --summary"
        )

        self.assertIn(generation, workflow)
        self.assertIn(validation, workflow)
        self.assertLess(
            workflow.index(publish_verification), workflow.index(generation)
        )
        self.assertLess(workflow.index(generation), workflow.index(validation))
        self.assertIn(
            'cat build/supply-chain-report/supply-chain-summary.md >> "$GITHUB_STEP_SUMMARY"',
            workflow,
        )
        self.assertIn(
            "uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7",
            workflow,
        )
        self.assertIn(
            "name: supply-chain-report-only-${{ github.run_id }}-${{ github.run_attempt }}",
            workflow,
        )
        self.assertIn("path: build/supply-chain-report/", workflow)
        self.assertIn("if-no-files-found: error", workflow)

    def test_publish_snapshot_limits_candidate_branch_to_snapshot_catalog_consumers(self) -> None:
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "publish-snapshot.yml"
        ).read_text(encoding="utf-8")
        clone_step = workflow.split(
            "      - name: Clone snapshot libraries and official-release examples\n",
            1,
        )[1].split("      - uses:", 1)[0]

        self.assertIn("--print-snapshot-catalog-repositories", clone_step)
        self.assertIn("use_snapshot_candidate=true", clone_step)
        self.assertIn(
            '[[ "$use_snapshot_candidate" == true ]]',
            clone_step,
        )
        self.assertIn('grep -Fq "(HTTP 404)"', clone_step)
        self.assertIn("clone_args+=(--branch develop --single-branch)", clone_step)
        self.assertIn("snapshot candidate lookup failed", clone_step)
        self.assertIn("exit 1", clone_step)

    def test_develop_validation_prefers_snapshot_candidate_branches(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        clone_step = workflow.split(
            "      - name: Clone managed repositories for catalog script checks\n",
            1,
        )[1].split("      - name:", 1)[0]
        self.assertNotIn("if: ${{ github.event_name != 'pull_request' }}", clone_step)
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py --print-required-repositories",
            clone_step,
        )
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py "
            "--print-snapshot-candidate-branch",
            clone_step,
        )
        self.assertIn(
            "python3 scripts/verify-post-publish-next-development-line.py "
            "--print-snapshot-catalog-repositories",
            clone_step,
        )
        self.assertIn("use_snapshot_candidate=true", clone_step)
        self.assertIn(
            '[[ "${GITHUB_EVENT_NAME}" == "pull_request" && '
            '"${GITHUB_BASE_REF}" == "develop" ]]',
            clone_step,
        )
        self.assertIn(
            '[[ "${GITHUB_EVENT_NAME}" == "push" && '
            '"${GITHUB_REF}" == "refs/heads/develop" ]]',
            clone_step,
        )
        self.assertIn('--branch "$candidate_branch" --single-branch', clone_step)
        self.assertIn('grep -Fq "(HTTP 404)"', clone_step)
        self.assertIn("clone_args+=(--branch develop --single-branch)", clone_step)
        self.assertIn("snapshot candidate lookup failed", clone_step)

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
        self.assertIn("if: ${{ github.event_name != 'push' }}", job)
        self.assertIn("scripts/verify-publication-poms.py --print-default-repositories", job)
        self.assertIn("scripts/verify-publication-poms.py --workspace .. --summary", job)
        self.assertIn("config/publishing-signing-repository-refs.json", job)
        self.assertIn('fetch --no-tags --filter=blob:none origin "$expected_sha"', job)
        self.assertIn('rev-parse --verify "${expected_sha}^{commit}"', job)
        self.assertNotIn("--depth 1", job)
        self.assertIn("uses: actions/setup-java@v6", job)
        self.assertIn("uses: gradle/actions/setup-gradle@v6", job)

        status_job = workflow.split("  ci-status:\n", 1)[1]
        self.assertIn("- publication-pom-contract", status_job)
        self.assertIn("PUBLICATION_POM_RESULT: ${{ needs.publication-pom-contract.result }}", status_job)
        self.assertIn(
            'if [[ "$EVENT_NAME" != "push" && "$PUBLICATION_POM_RESULT" != "success" ]]; then',
            status_job,
        )

    def test_ci_runs_issue_242_243_python_contract_tests_and_sync_check(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        script_step = workflow.split(
            "      - name: Verify catalog scripts\n", 1
        )[1].split("      - name:", 1)[0]

        for test_name in (
            "tests/test_sync_publishing_signing_support.py",
            "tests/test_run_issues_242_243_validation.py",
            "tests/test_publishing_signing_smoke.py",
            "tests/test_ci_catalog_governance.py",
        ):
            self.assertIn(test_name, script_step)
        self.assertIn("--check --summary", script_step)
        self.assertIn("scripts/sync-publishing-signing-support.py", workflow)

    def test_ci_clones_signing_refs_and_builds_a_strict_repository_map(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        clone_step = workflow.split(
            "      - name: Clone managed repositories for catalog script checks\n", 1
        )[1].split("      - name:", 1)[0]
        self.assertIn("config/publishing-signing-repository-refs.json", clone_step)
        self.assertIn("fetch --no-tags --filter=blob:none origin", clone_step)
        self.assertIn("clone_args=(--depth 1)", clone_step)
        self.assertIn("clone_args=(--filter=blob:none --no-checkout)", clone_step)
        self.assertIn(
            'clone_args=(--filter=blob:none --branch "$candidate_branch" --single-branch)',
            clone_step,
        )
        self.assertIn("selected_candidate_branch=true", clone_step)
        self.assertIn('origin "develop:refs/remotes/origin/develop"', clone_step)
        self.assertIn("clone_args+=(--branch develop --single-branch)", clone_step)
        self.assertIn('checkout -B "issues-242-243-', clone_step)
        self.assertIn("remote get-url origin", clone_step)
        self.assertIn("rev-parse --verify", clone_step)
        self.assertIn("rev-parse HEAD", clone_step)
        self.assertIn("status --porcelain=v1 --untracked-files=all", clone_step)
        self.assertIn("remote set-url origin", clone_step)
        self.assertIn(
            'test "$(git -C "../${repo}" remote get-url origin)" =',
            clone_step,
        )

        map_step = workflow.split(
            "      - name: Build exact catalog repository map\n", 1
        )[1].split("      - name:", 1)[0]
        self.assertIn("inspect_repository_for_map", map_step)
        self.assertIn("issues-242-243-repository-map.json", map_step)

        candidate_source = (
            REPO_ROOT / "scripts" / "catalog_candidate.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"remote", "get-url", "origin"', candidate_source)
        self.assertIn('"merge-base", head, develop_head', candidate_source)
        self.assertIn(
            '"status", "--porcelain=v1", "--untracked-files=all"',
            candidate_source,
        )

        recheck_step = workflow.split(
            "      - name: Recheck exact signing refs before sync\n", 1
        )[1].split("      - name:", 1)[0]
        self.assertIn("config/publishing-signing-repository-refs.json", recheck_step)
        self.assertIn("rev-parse HEAD", recheck_step)
        self.assertIn("status --porcelain=v1 --untracked-files=all", recheck_step)

        central_step = workflow.split(
            "      - name: Verify all generated signing copies\n", 1
        )[1].split("      - name:", 1)[0]
        self.assertNotIn("if:", central_step)
        self.assertIn(
            '--repository-map "$RUNNER_TEMP/issues-242-243-repository-map.json"',
            central_step,
        )
        self.assertIn("python3 scripts/sync-publishing-signing-support.py", central_step)
        self.assertNotIn("--repo ", central_step)
        self.assertNotIn("Verify PR central generated signing copy", workflow)
        self.assertIn("catalog_candidate.REPOSITORY_KEYS", map_step)
        compile_step = workflow.split(
            "      - name: Compile generated signing helpers\n", 1
        )[1].split("      - name:", 1)[0]
        setup_java = workflow.index("      - uses: actions/setup-java@v6.0.0")
        setup_gradle = workflow.index("      - uses: gradle/actions/setup-gradle@v6.3.0")
        compile_helpers = workflow.index("      - name: Compile generated signing helpers")
        self.assertLess(setup_java, compile_helpers)
        self.assertLess(setup_gradle, compile_helpers)
        self.assertIn("ThreadPoolExecutor(max_workers=2)", compile_step)
        self.assertIn("catalog_candidate.SIGNING_REPOSITORIES", compile_step)
        self.assertIn("runner.sanitized_environment", compile_step)
        self.assertIn("runner.require_disposable_hosted_environment", compile_step)
        self.assertIn("runner.run_command", compile_step)
        self.assertNotIn("subprocess.run", compile_step)
        self.assertIn('Path(os.environ["RUNNER_TEMP"])', compile_step)
        self.assertIn('environment["GRADLE_USER_HOME"]', compile_step)
        self.assertIn("os.chmod(gradle_home, 0o700)", compile_step)
        self.assertIn("timeout_seconds=600", compile_step)
        self.assertIn('"-p",', compile_step)
        self.assertIn('"PublishingSigningSupportTest",', compile_step)
        self.assertIn('"--tests",', compile_step)
        self.assertIn('"buildSrc",', compile_step)
        self.assertIn('"compileKotlin",', compile_step)
        self.assertIn('"test",', compile_step)

    def test_ci_does_not_reclone_signing_siblings_for_a_pr_central_check(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        check_step = workflow.split(
            "      - name: Verify all generated signing copies\n", 1
        )[1].split("      - name:", 1)[0]
        self.assertNotIn("if:", check_step)
        self.assertIn("python3 scripts/sync-publishing-signing-support.py", check_step)
        self.assertNotIn("--repo ", check_step)
        self.assertNotIn("gh repo clone", check_step)
        self.assertNotIn("Verify PR central generated signing copy", workflow)

    def test_release_diagnostic_matches_transport_classes_without_secret_output(self) -> None:
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        diagnostic = workflow.split("      - name: Diagnose signing inputs\n", 1)[1].split(
            "      - name:", 1
        )[0]
        for classification in (
            "raw_armor",
            "escaped_newline",
            "base64_armor",
            "base64_nonarmor",
            "invalid_base64",
        ):
            self.assertIn(classification, diagnostic)
        self.assertIn("validate=True", diagnostic)
        self.assertIn('replace("\\\\n", "\\n")', diagnostic)
        self.assertNotIn("sentinel", diagnostic.lower())
        self.assertNotIn("private-key-body", diagnostic.lower())
        self.assertNotIn("print(normalized_key", diagnostic)
        self.assertNotIn("print(decoded", diagnostic)


if __name__ == "__main__":
    unittest.main()
