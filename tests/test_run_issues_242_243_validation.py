from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

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
            "-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            "sentinel-private-body\n"
            "-----END PGP PRIVATE KEY BLOCK-----\n"
            "after\n"
        )
        redacted = runner.redact_output(body)
        self.assertNotIn("super-secret", redacted)
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
                    "import time; print('PASSWORD=secret', flush=True); time.sleep(10)",
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


if __name__ == "__main__":
    unittest.main()
