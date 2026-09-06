from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run-issues-242-243-validation.py"
SPEC = importlib.util.spec_from_file_location("run_issues_242_243_validation", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules["run_issues_242_243_validation"] = runner


class ValidationRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        SPEC.loader.exec_module(runner)

    def test_phase_and_execution_budget_contract(self) -> None:
        self.assertEqual(
            runner.PHASES,
            (
                "signing-buildsrc",
                "timefold-graphs-baseline",
                "consumers",
                "publication-poms",
            ),
        )
        self.assertEqual(runner.MAX_WORKERS, 2)
        self.assertEqual(runner.CHILD_TIMEOUT_SECONDS, 600)
        self.assertEqual(runner.PUBLICATION_POMS_TIMEOUT_SECONDS, 1800)
        self.assertIn("--no-configuration-cache", runner.GRADLE_FLAGS)
        self.assertIn("--no-build-cache", runner.GRADLE_FLAGS)

    def test_cache_key_is_canonical_and_binds_every_required_input(self) -> None:
        first = runner.cache_key(
            repository="bluetape4k-projects",
            repository_head="a" * 40,
            helper_sha256="b" * 64,
            catalog_sha256="c" * 64,
            bom_sha256="d" * 64,
            task_set=("test", "compileKotlin"),
            configuration="buildSrc",
            jdk_version="21.0.8",
            gradle_version="8.14.3",
        )
        same = runner.cache_key(
            repository="bluetape4k-projects",
            repository_head="a" * 40,
            helper_sha256="b" * 64,
            catalog_sha256="c" * 64,
            bom_sha256="d" * 64,
            task_set=("compileKotlin", "test"),
            configuration="buildSrc",
            jdk_version="21.0.8",
            gradle_version="8.14.3",
        )
        self.assertEqual(first, same)
        self.assertEqual(len(first), 64)
        for field, value in (
            ("repository_head", "e" * 40),
            ("helper_sha256", "f" * 64),
            ("catalog_sha256", "1" * 64),
            ("bom_sha256", "2" * 64),
            ("configuration", "other"),
            ("jdk_version", "17"),
            ("gradle_version", "8.10"),
        ):
            inputs = {
                "repository": "bluetape4k-projects",
                "repository_head": "a" * 40,
                "helper_sha256": "b" * 64,
                "catalog_sha256": "c" * 64,
                "bom_sha256": "d" * 64,
                "task_set": ("test", "compileKotlin"),
                "configuration": "buildSrc",
                "jdk_version": "21.0.8",
                "gradle_version": "8.14.3",
            }
            inputs[field] = value
            with self.subTest(field=field):
                self.assertNotEqual(first, runner.cache_key(**inputs))
        changed_tasks = {
            "repository": "bluetape4k-projects",
            "repository_head": "a" * 40,
            "helper_sha256": "b" * 64,
            "catalog_sha256": "c" * 64,
            "bom_sha256": "d" * 64,
            "task_set": ("compileKotlin",),
            "configuration": "buildSrc",
            "jdk_version": "21.0.8",
            "gradle_version": "8.14.3",
        }
        self.assertNotEqual(first, runner.cache_key(**changed_tasks))

    def test_cache_hit_requires_success_and_readback_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory).resolve()
            output = cache / "output.log"
            output.write_bytes(b"successful output\n")
            output.chmod(0o600)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            key = "a" * 64
            entry = cache / f"{key}.json"
            entry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "pass",
                        "cache_key": key,
                        "output_path": str(output),
                        "output_sha256": digest,
                    }
                ),
                encoding="utf-8",
            )
            entry.chmod(0o600)
            hit = runner.read_cache_entry(cache, key)
            self.assertIsNotNone(hit)
            self.assertEqual(hit["output_sha256"], digest)
            output.write_bytes(b"tampered")
            self.assertIsNone(runner.read_cache_entry(cache, key))

            output.write_bytes(b"successful output\n")
            entry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "fail",
                        "cache_key": key,
                        "output_path": str(output),
                        "output_sha256": digest,
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(runner.read_cache_entry(cache, key))

    def test_redaction_removes_secret_material_and_bounds_diagnostics(self) -> None:
        body = (
            "before\n"
            "PASSWORD=super-secret\n"
            "AWS_SECRET_ACCESS_KEY=sentinel-aws-secret\n"
            "AWS_ACCESS_KEY_ID=sentinel-aws-id\n"
            "MY_SECRET_ACCESS_KEY=sentinel-my-secret\n"
            "-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            "sentinel-private-body\n"
            "-----END PGP PRIVATE KEY BLOCK-----\n"
            "after\n"
        )
        redacted = runner.redact_output(body)
        self.assertNotIn("super-secret", redacted)
        self.assertNotIn("sentinel-aws-secret", redacted)
        self.assertNotIn("sentinel-aws-id", redacted)
        self.assertNotIn("sentinel-my-secret", redacted)
        self.assertNotIn("sentinel-private-body", redacted)
        self.assertNotIn("BEGIN PGP PRIVATE KEY BLOCK", redacted)
        lines = runner.bounded_diagnostics("\n".join(f"line-{i}" for i in range(100)))
        self.assertEqual(lines, "\n".join(f"line-{i}" for i in range(20, 100)))

    def test_gradle_commands_disable_both_gradle_caches(self) -> None:
        command = runner.gradle_command(
            Path("/workspace/repo"), ("test", "compileKotlin"), configuration="buildSrc"
        )
        self.assertEqual(command[0], "/workspace/repo/gradlew")
        self.assertIn("-p", command)
        self.assertIn("buildSrc", command)
        self.assertIn("test", command)
        self.assertIn("compileKotlin", command)
        self.assertIn("--no-daemon", command)
        self.assertIn("--no-configuration-cache", command)
        self.assertIn("--no-build-cache", command)
        self.assertIn("--console=plain", command)

    def test_publication_pom_command_reuses_strict_non_candidate_map(self) -> None:
        command = runner.publication_pom_command(
            central_root=Path("/workspace/bluetape4k-dependencies"),
            workspace=Path("/workspace"),
            repository_map=Path("/workspace/repository-map.json"),
        )
        self.assertEqual(command[0], sys.executable)
        self.assertIn("scripts/verify-publication-poms.py", " ".join(command))
        self.assertIn("--repository-map", command)
        self.assertIn(str(Path("/workspace/repository-map.json")), command)
        self.assertIn("--summary", command)
        self.assertNotIn("timefold-workshop", command)
        self.assertNotIn("clinic-appointment", command)

    def test_parallel_scheduler_stops_submitting_after_first_failure(self) -> None:
        started: list[str] = []

        def worker(item: str) -> dict[str, object]:
            started.append(item)
            if item == "fail":
                raise runner.ValidationFailure("deterministic failure")
            time.sleep(0.03)
            return {"repository": item, "status": "pass"}

        with self.assertRaises(runner.ValidationFailure):
            runner.run_bounded_jobs(("fail", "in-flight", "must-not-start"), worker, max_workers=2)
        self.assertNotIn("must-not-start", started)

    def test_timeout_terminates_process_group_and_writes_0600_redacted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifact = root / "failure.log"
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    "import time; print('PASSWORD=secret\\nAWS_SECRET_ACCESS_KEY=sentinel-aws-secret\\nAWS_ACCESS_KEY_ID=sentinel-aws-id\\nMY_SECRET_ACCESS_KEY=sentinel-my-secret', flush=True); time.sleep(10)",
                ),
                cwd=root,
                environment=os.environ,
                timeout_seconds=0.05,
                failure_artifact=artifact,
            )
            self.assertEqual(result.status, "fail")
            self.assertTrue(result.timed_out)
            self.assertTrue(result.process_group_terminated)
            self.assertTrue(artifact.is_file())
            self.assertEqual(stat.S_IMODE(artifact.stat().st_mode), 0o600)
            self.assertNotIn("secret", artifact.read_text(encoding="utf-8"))
            artifact_text = artifact.read_text(encoding="utf-8")
            self.assertNotIn("sentinel-aws-secret", artifact_text)
            self.assertNotIn("sentinel-aws-id", artifact_text)
            self.assertNotIn("sentinel-my-secret", artifact_text)

    def test_receipt_binding_rejects_map_path_or_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            map_path = root / "map.json"
            map_path.write_text("{}\n", encoding="utf-8")
            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "repository_map": {
                            "path": str(map_path),
                            "sha256": "0" * 64,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                runner.load_local_receipt(receipt, map_path)

    def test_run_phase_rejects_lexical_parent_symlink_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            map_path = linked / "map.json"
            receipt_path = linked / "receipt.json"
            with mock.patch.object(runner, "load_strict_repository_map") as load_map, self.assertRaisesRegex(
                runner.InputContractError, "symlink"
            ):
                runner.run_phase(
                    "signing-buildsrc",
                    repository_map_path=map_path,
                    receipt_path=receipt_path,
                    dry_run=True,
                )
            load_map.assert_not_called()

    def test_receipt_update_is_locked_strictly_validated_and_compare_and_swap_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            receipt = root / "receipt.json"
            initial = {
                "repository_map": {"path": str(root / "map.json"), "sha256": "a" * 64},
                "current_state": "discovered",
                "phases": [],
                "commands": [],
                "failure_record": [],
            }
            (root / "map.json").write_text("map\n", encoding="utf-8")
            initial["repository_map"]["sha256"] = hashlib.sha256(
                (root / "map.json").read_bytes()
            ).hexdigest()
            receipt.write_text(json.dumps(initial), encoding="utf-8")
            receipt.chmod(0o600)
            calls: list[str] = []

            @contextmanager
            def lock(path: Path):
                calls.append("lock-enter")
                yield
                calls.append("lock-exit")

            class StrictReceipt:
                _receipt_lock = staticmethod(lock)

                @staticmethod
                def validate_receipt(path: Path) -> dict[str, object]:
                    calls.append("validate")
                    return json.loads(path.read_text(encoding="utf-8"))

                write_atomic = staticmethod(runner._atomic_write)

            job = runner.ValidationJob(
                repository="demo",
                phase="signing-buildsrc",
                cwd=root,
                command=("echo", "ok"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="jdk",
                gradle_version="gradle",
            )
            result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout="",
                stderr="",
                elapsed_seconds=0.01,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256="e" * 64,
            )
            phase = runner.PhaseResult("signing-buildsrc", "pass", "f" * 64, (result,))
            expected_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            with mock.patch.object(runner, "_load_receipt_module", return_value=StrictReceipt):
                runner._write_receipt_update(
                    receipt,
                    phase,
                    (job,),
                    expected_receipt_sha256=expected_digest,
                    expected_state="discovered",
                )
                self.assertGreaterEqual(calls.count("validate"), 2)
                self.assertEqual(calls[0], "lock-enter")
                updated = json.loads(receipt.read_text(encoding="utf-8"))
                stale_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
                self.assertNotEqual(stale_digest, expected_digest)
                with self.assertRaisesRegex(runner.InputContractError, "digest"):
                    runner._write_receipt_update(
                        receipt,
                        phase,
                        (job,),
                        expected_receipt_sha256=expected_digest,
                        expected_state="discovered",
                    )
                self.assertEqual(updated, json.loads(receipt.read_text(encoding="utf-8")))

    def test_job_binding_rechecks_git_identity_clean_state_and_all_input_digests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "gradle").mkdir()
            (root / "buildSrc/src/main/kotlin").mkdir(parents=True)
            (root / "gradle/libs.versions.toml").write_text("catalog\n", encoding="utf-8")
            (root / "build.gradle.kts").write_text("bom\n", encoding="utf-8")
            helper = root / "buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt"
            helper.write_text("helper\n", encoding="utf-8")
            job = runner.ValidationJob(
                repository="demo",
                phase="signing-buildsrc",
                cwd=root,
                command=("echo", "ok"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256=runner.sha256_file(helper),
                catalog_sha256=runner.sha256_file(root / "gradle/libs.versions.toml"),
                bom_sha256=runner.sha256_file(root / "build.gradle.kts"),
                jdk_version="jdk",
                gradle_version="gradle",
                repository_origin="git@example/demo.git",
                repository_branch="feat/demo",
            )
            binding = {
                "name": "demo",
                "candidate_worktree": str(root),
                "candidate_head": "a" * 40,
                "origin": "git@example/demo.git",
                "candidate_branch": "feat/demo",
            }
            with mock.patch.object(
                runner,
                "_git",
                side_effect=lambda _root, *args: {
                    ("remote", "get-url", "origin"): "git@example/demo.git",
                    ("branch", "--show-current"): "feat/demo",
                    ("rev-parse", "HEAD"): "a" * 40,
                    ("status", "--porcelain=v1", "--untracked-files=all"): "",
                }[args],
            ):
                runner.validate_job_binding(job, {"demo": binding})
            bad_binding = dict(binding, candidate_head="b" * 40)
            with self.assertRaisesRegex(
                runner.InputContractError, "HEAD"
            ), mock.patch.object(runner, "_git", side_effect=lambda _root, *args: "a" * 40):
                runner.validate_job_binding(job, {"demo": bad_binding})

    def test_scheduler_keeps_two_failures_and_blocks_queued_jobs_without_submission(self) -> None:
        started: list[int] = []

        def worker(item: int) -> runner.CommandResult:
            started.append(item)
            return runner.CommandResult(
                status="fail" if item in {0, 1} else "pass",
                returncode=1 if item in {0, 1} else 0,
                stdout="",
                stderr="",
                elapsed_seconds=0.01,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256=f"{item + 1:064x}",
                repository=f"repo-{item}",
                job_id=f"job-{item}",
            )

        outcome = runner.run_bounded_jobs(
            (0, 1, 2),
            worker,
            max_workers=2,
            failure_predicate=lambda result: result.status != "pass",
            collect_failures=True,
        )
        self.assertEqual(set(started), {0, 1})
        self.assertEqual(set(outcome.results), {0, 1})
        self.assertEqual(outcome.first_failure, 0)
        self.assertEqual(outcome.cancelled, (2,))
        self.assertEqual({item: outcome.results[item].status for item in outcome.results}, {0: "fail", 1: "fail"})

    def test_cancellation_terminates_running_process_group_and_marks_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cancel = threading.Event()
            timer = threading.Timer(0.05, cancel.set)
            timer.start()
            try:
                result = runner.run_command(
                    command=(sys.executable, "-c", "import time; time.sleep(10)"),
                    cwd=root,
                    environment={"PATH": os.environ["PATH"]},
                    timeout_seconds=2,
                    cancel_event=cancel,
                )
            finally:
                timer.cancel()
            self.assertEqual(result.status, "blocked")
            self.assertTrue(result.cancelled)
            self.assertTrue(result.process_group_terminated)

    def test_child_environment_and_command_cache_are_secret_free(self) -> None:
        source = {
            "PATH": "/bin",
            "HOME": "/tmp/home",
            "JAVA_HOME": "/jdk",
            "CENTRAL_PASSWORD": "secret-central",
            "AWS_SECRET_ACCESS_KEY": "secret-aws",
            "MY_API_KEY": "secret-api",
            "SERVICE_TOKEN": "secret-token",
            "SERVICE_SECRET": "secret-secret",
            "SERVICE_KEY": "secret-key",
            "AWS_ACCESS_KEY_ID": "sentinel-aws-id",
            "MY_SECRET_ACCESS_KEY": "sentinel-my-secret",
        }
        environment = runner.sanitized_environment(source)
        self.assertEqual(set(environment), {"PATH", "HOME", "JAVA_HOME"})
        command = runner.redact_command(
            (
                "gradlew",
                "CENTRAL_PASSWORD=secret-central",
                "AWS_SECRET_ACCESS_KEY=sentinel-aws-secret",
                "AWS_ACCESS_KEY_ID=sentinel-aws-id",
                "MY_SECRET_ACCESS_KEY=sentinel-my-secret",
                "SERVICE_KEY=secret-key",
                "--password=secret-password",
            )
        )
        self.assertNotIn("secret", " ".join(command))
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory).resolve()
            key = "a" * 64
            runner.write_cache_entry(
                cache,
                key,
                b"CENTRAL_PASSWORD=secret-central\n"
                b"AWS_SECRET_ACCESS_KEY=sentinel-aws-secret\n"
                b"AWS_ACCESS_KEY_ID=sentinel-aws-id\n"
                b"MY_SECRET_ACCESS_KEY=sentinel-my-secret\n"
                b"SERVICE_KEY=secret-key\n",
            )
            output = runner.read_cache_entry(cache, key)
            self.assertIsNotNone(output)
            self.assertNotIn("secret-central", output["output"])
            self.assertNotIn("secret-key", output["output"])
            self.assertNotIn("sentinel-aws-secret", output["output"])
            self.assertNotIn("sentinel-aws-id", output["output"])
            self.assertNotIn("sentinel-my-secret", output["output"])


if __name__ == "__main__":
    unittest.main()
