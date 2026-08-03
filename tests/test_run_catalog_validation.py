from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
        self.assertEqual(runner.STARTUP_CLEANUP_RESERVE_SECONDS, 30 * 60)
        self.assertEqual(
            runner.STARTUP_CLEANUP_RESERVE_SECONDS
            + sum(runner.STAGE_BUDGET_SECONDS.values()),
            runner.TRAIN_BUDGET_SECONDS,
        )

    def test_heavy_stage_scheduler_contracts_are_exact(self) -> None:
        g6 = runner.scheduler_contract(runner.Stage.G6)
        self.assertEqual(
            (g6.jobs, g6.workers, g6.job_seconds, g6.waves, g6.reserve_seconds),
            (8, 2, 25 * 60, 4, 20 * 60),
        )
        g7 = runner.scheduler_contract(runner.Stage.G7)
        self.assertEqual(
            (g7.jobs, g7.workers, g7.job_seconds, g7.waves, g7.reserve_seconds),
            (10, 2, 10 * 60, 5, 10 * 60),
        )
        g8 = runner.scheduler_contract(runner.Stage.G8)
        self.assertEqual(
            (g8.jobs, g8.workers, g8.job_seconds, g8.waves, g8.reserve_seconds),
            (10, 2, 15 * 60, 5, 15 * 60),
        )

    def test_scheduler_rejects_an_impossible_stage_before_launch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "full stage budget"):
            runner.require_stage_budget(runner.Stage.G6, 120 * 60 - 1)
        runner.require_stage_budget(runner.Stage.G6, 120 * 60)

    def test_cache_manifest_binds_allowlisted_regular_files_by_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifact = root / "artifact.jar"
            artifact.write_bytes(b"trusted-cache-artifact")
            document = {
                "schema_version": 1,
                "sources": [
                    {
                        "kind": "gradle-cache-file",
                        "path": str(artifact),
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    }
                ],
            }
            manifest = root / "cache-manifest.json"
            manifest.write_text(json.dumps(document), encoding="utf-8")

            sources = runner.load_cache_manifest(manifest)

            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].path, artifact)
            artifact.write_bytes(b"mutated")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                runner.load_cache_manifest(manifest)

    def test_cache_manifest_rejects_unknown_kind_missing_file_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifact = root / "artifact.jar"
            artifact.write_bytes(b"artifact")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = root / "cache-manifest.json"

            for kind, path, message in (
                ("network-cache", artifact, "kind"),
                ("gradle-cache-file", root / "missing.jar", "regular file"),
            ):
                with self.subTest(kind=kind, path=path):
                    manifest.write_text(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "sources": [
                                    {"kind": kind, "path": str(path), "sha256": digest}
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(RuntimeError, message):
                        runner.load_cache_manifest(manifest)

            link = root / "linked.jar"
            link.symlink_to(artifact)
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {
                                "kind": "gradle-cache-file",
                                "path": str(link),
                                "sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "canonical|symlink"):
                runner.load_cache_manifest(manifest)

    def test_cache_manifest_rejects_group_or_world_writable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifact = root / "artifact.jar"
            artifact.write_bytes(b"artifact")
            manifest = root / "cache-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {
                                "kind": "gradle-cache-file",
                                "path": str(artifact),
                                "sha256": hashlib.sha256(
                                    artifact.read_bytes()
                                ).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest.chmod(0o666)
            with self.assertRaisesRegex(RuntimeError, "writable"):
                runner.load_cache_manifest(manifest)

    def test_g2_declared_ref_hold_preserves_path_sha_for_g3(self) -> None:
        receipt = {
            "stage": "G2",
            "status": "PARTIAL_HOLD",
            "manifest_sha256": "a" * 64,
            "catalog_sha256": "b" * 64,
            "cache_manifest_sha256": "c" * 64,
            "path_sha": "PASS",
            "declared_ref": "BLOCKED_UNTIL_TAG",
        }
        runner.require_predecessor(
            runner.Stage.G3, receipt, "a" * 64, "b" * 64, "c" * 64
        )
        receipt["path_sha"] = "FAIL"
        with self.assertRaisesRegex(RuntimeError, "path/SHA"):
            runner.require_predecessor(
                runner.Stage.G3, receipt, "a" * 64, "b" * 64, "c" * 64
            )

    def test_predecessor_binds_catalog_and_cache_manifest_sha(self) -> None:
        receipt = {
            "stage": "G5",
            "status": "PASS",
            "manifest_sha256": "a" * 64,
            "catalog_sha256": "b" * 64,
            "cache_manifest_sha256": "c" * 64,
        }
        runner.require_predecessor(
            runner.Stage.G6, receipt, "a" * 64, "b" * 64, "c" * 64
        )
        receipt["cache_manifest_sha256"] = "d" * 64
        with self.assertRaisesRegex(RuntimeError, "cache manifest"):
            runner.require_predecessor(
                runner.Stage.G6, receipt, "a" * 64, "b" * 64, "c" * 64
            )

    def test_sandbox_profile_denies_network_and_binds_exact_paths(self) -> None:
        profile = runner.sandbox_profile(
            workspace=Path("/workspace"),
            java_home=Path("/jdk"),
            readable_files=(Path("/cache/a.jar"),),
            writable_roots=(Path("/tmp/home"), Path("/workspace/repo/build")),
            executable_files=(Path("/workspace/repo/gradlew"), Path("/jdk/bin/java")),
        )
        self.assertIn("(deny network*)", profile)
        self.assertIn('(literal "/cache/a.jar")', profile)
        self.assertIn('(subpath "/tmp/home")', profile)
        self.assertNotIn("allow default", profile)

    @unittest.skipUnless(shutil.which("sandbox-exec"), "sandbox-exec unavailable")
    def test_sandbox_exec_network_denial_is_proven(self) -> None:
        command = [
            "sandbox-exec",
            "-p",
            runner.network_denial_profile(),
            "/usr/bin/python3",
            "-c",
            (
                "import socket; "
                'socket.create_connection((\"127.0.0.1\", 9), 0.2)'
            ),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Operation not permitted", result.stderr)

    def test_job_receipt_binds_full_log_and_bounded_last_80_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            log = root / "logs" / "job.log"
            receipt = root / "receipts" / "job.json"
            command = (
                sys.executable,
                "-c",
                "for i in range(100): print(f'line-{i:03d}')",
            )

            result = runner.execute_job(
                command=command,
                cwd=root,
                environment={"PATH": os.environ.get("PATH", "")},
                timeout_seconds=5,
                terminate_grace_seconds=0.1,
                drain_seconds=0.2,
                log_path=log,
                receipt_path=receipt,
                identity={"stage": "G6", "job": "fixture"},
                bindings={
                    "manifest_sha256": "a" * 64,
                    "catalog_sha256": "b" * 64,
                    "cache_manifest_sha256": "c" * 64,
                },
            )

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["command"], list(command))
            self.assertEqual(result["full_log_sha256"], runner.sha256_file(log))
            self.assertEqual(result["last_80_lines_count"], 80)
            self.assertEqual(
                result["last_80_lines_sha256"],
                hashlib.sha256("\n".join(log.read_text().splitlines()[-80:]).encode()).hexdigest(),
            )
            self.assertEqual(json.loads(receipt.read_text()), result)
            with self.assertRaisesRegex(RuntimeError, "immutable"):
                runner.execute_job(
                    command=command,
                    cwd=root,
                    environment={},
                    timeout_seconds=5,
                    terminate_grace_seconds=0.1,
                    drain_seconds=0.2,
                    log_path=log,
                    receipt_path=receipt,
                    identity={"stage": "G6", "job": "fixture"},
                    bindings={},
                )

    def test_timeout_terminates_then_kills_process_group_and_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            log = root / "job.log"
            receipt = root / "job.json"
            result = runner.execute_job(
                command=(sys.executable, "-c", "import time; time.sleep(60)"),
                cwd=root,
                environment={"PATH": os.environ.get("PATH", "")},
                timeout_seconds=0.05,
                terminate_grace_seconds=0.05,
                drain_seconds=0.2,
                log_path=log,
                receipt_path=receipt,
                identity={"stage": "G8", "job": "timeout"},
                bindings={
                    "manifest_sha256": "a" * 64,
                    "catalog_sha256": "b" * 64,
                    "cache_manifest_sha256": "c" * 64,
                },
            )
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["timed_out"])
            self.assertTrue(result["process_group_terminated"])
            self.assertIn(result["termination_signal"], ("SIGTERM", "SIGKILL"))
            self.assertLess(result["elapsed_seconds"], 2)

    def test_trusted_review_and_ci_provenance_bind_exact_central_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            central = Path(directory).resolve()
            workflow = central / ".github" / "workflows" / "ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: CI\n", encoding="utf-8")
            review_output = central / "review.txt"
            review_output.write_text("P1-clear\n", encoding="utf-8")
            ci_output = central / "ci.txt"
            ci_output.write_text("tests passed\n", encoding="utf-8")
            toolchain = central / "toolchain.txt"
            toolchain.write_text("python=3.14\n", encoding="utf-8")
            head = "d" * 40
            review = central / "trusted-worktree-review.json"
            ci = central / "ci-provenance.json"

            def observation(path: Path) -> dict[str, str]:
                return {"path": str(path), "sha256": runner.sha256_file(path)}

            review.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "PASS",
                        "central_head": head,
                        "workflow_sha256": runner.sha256_file(workflow),
                        "reviewer": "independent-code-reviewer",
                        "command": ["review-delta", "--head", head],
                        "output": observation(review_output),
                    }
                ),
                encoding="utf-8",
            )
            ci.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "PASS",
                        "central_head": head,
                        "workflow": str(workflow),
                        "workflow_sha256": runner.sha256_file(workflow),
                        "check_argv": ["python3", "-m", "unittest"],
                        "output": observation(ci_output),
                        "toolchain": observation(toolchain),
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                "central_root": str(central),
                "catalog_lock": {
                    "catalogs": {"central": {"repository_head": head}}
                },
            }

            proof = runner.verify_trusted_provenance(manifest, review, ci)

            self.assertEqual(proof["review_sha256"], runner.sha256_file(review))
            self.assertEqual(proof["ci_sha256"], runner.sha256_file(ci))
            document = json.loads(ci.read_text())
            document["central_head"] = "e" * 40
            ci.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "central HEAD"):
                runner.verify_trusted_provenance(manifest, review, ci)

    def test_provenance_rejects_stale_output_and_self_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "review.txt"
            output.write_text("clear\n", encoding="utf-8")
            review = root / "review.json"
            review.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "PASS",
                        "central_head": "d" * 40,
                        "workflow_sha256": "a" * 64,
                        "reviewer": "self",
                        "command": ["review"],
                        "output": {
                            "path": str(output),
                            "sha256": runner.sha256_file(output),
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "independent reviewer"):
                runner.verify_review_receipt(
                    review, central_head="d" * 40, workflow_sha256="a" * 64
                )
            document = json.loads(review.read_text())
            document["reviewer"] = "independent-reviewer"
            review.write_text(json.dumps(document), encoding="utf-8")
            output.write_text("mutated\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                runner.verify_review_receipt(
                    review, central_head="d" * 40, workflow_sha256="a" * 64
                )

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
        with tempfile.TemporaryDirectory() as directory:
            central = Path(directory).resolve()
            catalog = central / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            digest = runner.sha256_file(catalog)
            manifest = {
                "central_root": str(central),
                "catalog_lock": {
                    "catalogs": {
                        "central": {"path": str(catalog), "sha256": digest}
                    }
                },
            }
            self.assertEqual(
                runner.evidence_root(manifest),
                central / "build" / "catalog-authority" / digest,
            )
            manifest["catalog_lock"]["catalogs"]["central"]["sha256"] = "A" * 64
            with self.assertRaisesRegex(RuntimeError, "catalog SHA"):
                runner.evidence_root(manifest)
            manifest["catalog_lock"]["catalogs"]["central"]["sha256"] = "a" * 64
            with self.assertRaisesRegex(RuntimeError, "raw catalog"):
                runner.evidence_root(manifest)

    def test_g2_catalog_lock_separates_path_sha_from_tag_hold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            catalog = root / "libs.versions.toml"
            catalog.write_text("[versions]\n", encoding="utf-8")
            result = runner._g2_catalog_lock(
                {
                    "catalog_lock": {
                        "catalogs": {
                            "central": {
                                "path": str(catalog),
                                "sha256": runner.sha256_file(catalog),
                                "declared_ref": "d" * 40,
                            }
                        }
                    }
                }
            )
            self.assertEqual(result["status"], "PARTIAL_HOLD")
            self.assertEqual(result["path_sha"], "PASS")
            self.assertEqual(result["declared_ref"], "BLOCKED_UNTIL_TAG")

    def test_g7_insights_are_exact_sorted_deduplicated_gradle_commands(self) -> None:
        authority_a = "a" * 64
        authority_b = "b" * 64
        records = [
            {
                "authority_id": authority_b,
                "line_id": "default",
                "repository": "bluetape4k-projects",
                "project_path": ":module-b",
                "coordinate": "org.example:beta",
                "configuration": "compileClasspath",
                "reason": "compatibility-line",
                "expected_resolved_version": "2.0.0",
                "artifact_path": "evidence/beta.txt",
            },
            {
                "authority_id": authority_a,
                "line_id": "spring-boot3",
                "repository": "bluetape4k-aws",
                "project_path": ":module-a",
                "coordinate": "org.example:alpha",
                "configuration": "compileClasspath",
                "reason": "intentional-version-delta",
                "expected_resolved_version": "1.2.3",
                "artifact_path": "evidence/alpha.txt",
            },
        ]
        normalized = runner.validate_g7_insights(
            records,
            required_authorities={
                (authority_a, "spring-boot3"),
                (authority_b, "default"),
            },
        )
        self.assertEqual(
            [item["authority_id"] for item in normalized], [authority_a, authority_b]
        )
        command = runner.insight_command(normalized[0])
        self.assertEqual(
            command[:6],
            (
                "./gradlew",
                ":module-a:dependencyInsight",
                "--dependency",
                "org.example:alpha",
                "--configuration",
                "compileClasspath",
            ),
        )
        for flag in runner.GRADLE_FLAGS:
            self.assertIn(flag, command)

    def test_g7_insights_reject_missing_extra_wildcard_and_duplicate(self) -> None:
        authority = "a" * 64
        valid = {
            "authority_id": authority,
            "line_id": "default",
            "repository": "bluetape4k-projects",
            "project_path": ":module",
            "coordinate": "org.example:artifact",
            "configuration": "compileClasspath",
            "reason": "changed-normalized-graph",
            "expected_resolved_version": "1.0.0",
            "artifact_path": "evidence/artifact.txt",
        }
        with self.assertRaisesRegex(RuntimeError, "missing"):
            runner.validate_g7_insights([], required_authorities={(authority, "default")})
        with self.assertRaisesRegex(RuntimeError, "extra"):
            runner.validate_g7_insights(
                [valid], required_authorities={("b" * 64, "default")}
            )
        wildcard = {**valid, "coordinate": "org.example:*"}
        with self.assertRaisesRegex(RuntimeError, "coordinate"):
            runner.validate_g7_insights(
                [wildcard], required_authorities={(authority, "default")}
            )
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            runner.validate_g7_insights(
                [valid, valid], required_authorities={(authority, "default")}
            )


if __name__ == "__main__":
    unittest.main()
