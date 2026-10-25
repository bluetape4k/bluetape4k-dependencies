from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-latest-stable-resolved-graphs.py"


def load_script():
    spec = importlib.util.spec_from_file_location(
        "verify_latest_stable_resolved_graphs", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VerifyLatestStableResolvedGraphsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script()
        self.ledger = {
            "schema-version": 3,
            "status": "validation-pending",
            "candidate": {"catalog-sha256": "a" * 64},
            "delta": [
                {
                    "version-key": "example",
                    "before": "1.0.0",
                    "after": "1.1.0",
                    "verification": "pending-resolved-graph",
                    "authorities": [
                        {
                            "kind": "library",
                            "coordinate-or-plugin-id": "org.example:alpha",
                        },
                        {
                            "kind": "library",
                            "coordinate-or-plugin-id": "org.example:beta",
                        },
                    ],
                },
                {
                    "version-key": "native-plugin",
                    "before": "1.0.0",
                    "after": "1.1.0",
                    "verification": "pending-resolved-graph",
                    "authorities": [
                        {
                            "kind": "plugin",
                            "coordinate-or-plugin-id": "org.example.native",
                        }
                    ],
                },
            ],
        }

    def observations(self, specs):
        return [
            {
                "spec_id": spec.spec_id,
                "phase": phase,
                "requested": getattr(spec, phase),
                "selected": getattr(spec, phase),
                "components": [
                    f"org.example:{spec.version_key}:{getattr(spec, phase)}",
                    "root project 'latest-stable-resolved-graphs'",
                ],
                "graph_sha256": self.module.sha256_bytes(
                    self.module.canonical_json(
                        [
                            f"org.example:{spec.version_key}:{getattr(spec, phase)}",
                            "root project 'latest-stable-resolved-graphs'",
                        ]
                    )
                ),
            }
            for spec in specs
            for phase in ("before", "after")
        ]

    def test_pending_catalog_without_receipt_requires_matching_worktree_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            catalog_path = root / "gradle" / "libs.versions.toml"
            catalog_path.parent.mkdir(parents=True)
            catalog_bytes = b'[versions]\nexample = "1.1.0"\n'
            catalog_path.write_bytes(catalog_bytes)
            ledger = {
                "status": "validation-pending",
                "candidate": {"catalog-sha256": self.module.sha256_bytes(catalog_bytes)},
            }

            self.assertEqual(
                self.module.candidate_catalog_bytes(ledger, root), catalog_bytes
            )

            catalog_path.write_bytes(b"stale candidate\n")
            with self.assertRaisesRegex(RuntimeError, "pending candidate catalog SHA"):
                self.module.candidate_catalog_bytes(ledger, root)

            ledger["status"] = "verified-resolved-graph"
            with self.assertRaisesRegex(RuntimeError, "receipt pointer is required"):
                self.module.candidate_catalog_bytes(ledger, root)

    def test_build_specs_expands_libraries_and_plugin_markers(self) -> None:
        specs = self.module.build_specs(self.ledger)

        self.assertEqual(len(specs), 3)
        self.assertEqual(
            [spec.coordinate for spec in specs],
            [
                "org.example:alpha",
                "org.example:beta",
                "org.example.native:org.example.native.gradle.plugin",
            ],
        )
        self.assertEqual(len({spec.spec_id for spec in specs}), 3)

    def test_build_specs_can_reverify_a_promoted_ledger(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["status"] = "verified-resolved-graph"
        for delta in ledger["delta"]:
            delta["verification"] = "verified-resolved-graph"

        specs = self.module.build_specs(ledger)

        self.assertEqual(len(specs), 3)

    def test_build_specs_rejects_preview_or_snapshot_versions(self) -> None:
        for invalid in ("1.1.0-SNAPSHOT", "1.1.0-RC1", "1.1.0-beta.1"):
            ledger = copy.deepcopy(self.ledger)
            ledger["delta"][0]["after"] = invalid
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(RuntimeError, "exact stable version"),
            ):
                self.module.build_specs(ledger)

    def test_render_gradle_project_uses_isolated_exact_configurations(self) -> None:
        specs = self.module.build_specs(self.ledger)

        settings, build = self.module.render_gradle_project(specs)

        self.assertIn('rootProject.name = "latest-stable-resolved-graphs"', settings)
        self.assertEqual(build.count("canBeResolved = true"), 6)
        self.assertEqual(build.count("Bundling.EXTERNAL"), 6)
        self.assertEqual(build.count("Usage.JAVA_RUNTIME"), 6)
        self.assertEqual(build.count("TargetJvmEnvironment.STANDARD_JVM"), 6)
        self.assertNotIn("isCanBeResolved", build)
        self.assertNotIn("isCanBeConsumed", build)
        self.assertIn('"org.example:alpha:1.0.0"', build)
        self.assertIn('"org.example:alpha:1.1.0"', build)
        self.assertIn("repo.gradle.org/gradle/libs-releases", build)
        self.assertIn("exclusiveContent", build)
        self.assertIn('includeGroup("javax.media")', build)
        self.assertIn("UnresolvedDependencyResult", build)
        self.assertIn("configuration.resolve()", build)
        self.assertIn("result.allDependencies.find", build)
        self.assertIn("throw new GradleException", build)
        dependency_notations = re.findall(
            r'dependencies\.add\([^,]+, "([^"]+)"\)', build
        )
        self.assertEqual(len(dependency_notations), 6)
        self.assertFalse(
            any(
                re.search(r"(?:\+|latest\.|[\[\]()])", item)
                for item in dependency_notations
            )
        )

    def test_validate_observations_requires_exact_complete_selection(self) -> None:
        specs = self.module.build_specs(self.ledger)
        observations = self.observations(specs)

        validated = self.module.validate_observations(specs, observations)

        self.assertEqual(len(validated), 6)
        wrong = [dict(item) for item in observations]
        wrong[0]["selected"] = "9.9.9"
        with self.assertRaisesRegex(RuntimeError, "selected version"):
            self.module.validate_observations(specs, wrong)
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.module.validate_observations(specs, observations[:-1])
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            self.module.validate_observations(specs, observations + observations[:1])

        unresolved = [dict(item) for item in observations]
        unresolved[0]["selected"] = None
        with self.assertRaisesRegex(RuntimeError, "unresolved dependency"):
            self.module.validate_observations(specs, unresolved)

    def test_validate_observations_rejects_dynamic_or_invalid_graph_hash(self) -> None:
        specs = self.module.build_specs(self.ledger)
        observations = self.observations(specs)
        observations[0]["selected"] = "latest.release"
        with self.assertRaisesRegex(RuntimeError, "dynamic"):
            self.module.validate_observations(specs, observations)

        observations = self.observations(specs)
        observations[0]["graph_sha256"] = "short"
        with self.assertRaisesRegex(RuntimeError, "graph SHA"):
            self.module.validate_observations(specs, observations)

        observations = self.observations(specs)
        observations[0]["components"].append("org.example:tampered:1.0.0")
        with self.assertRaisesRegex(RuntimeError, "graph SHA mismatch"):
            self.module.validate_observations(specs, observations)

    def test_graph_deltas_document_every_component_change(self) -> None:
        specs = self.module.build_specs(self.ledger)
        observations = self.module.validate_observations(
            specs, self.observations(specs)
        )

        deltas = self.module.build_graph_deltas(specs, observations)

        self.assertEqual(len(deltas), 3)
        self.assertTrue(all(delta["added-components"] for delta in deltas))
        self.assertTrue(all(delta["removed-components"] for delta in deltas))

    def test_catalog_validation_separates_current_bytes_from_historical_candidate(
        self,
    ) -> None:
        ledger = copy.deepcopy(self.ledger)
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(
                ["git", "init", str(repo)], check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "test"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
                capture_output=True,
                text=True,
            )
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            historical_bytes = (
                b'[versions]\nexample = "1.1.0"\nnative-plugin = "1.1.0"\n'
            )
            wrong_pointer_bytes = (
                b'[versions]\nexample = "0.9.0"\nnative-plugin = "0.9.0"\n'
            )
            current_bytes = b'[versions]\nexample = "2.0.0"\nnative-plugin = "2.0.0"\n'

            def commit_catalog(content: bytes, message: str) -> str:
                catalog.write_bytes(content)
                subprocess.run(
                    ["git", "-C", str(repo), "add", "gradle/libs.versions.toml"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "commit", "-m", message],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return subprocess.run(
                    ["git", "-C", str(repo), "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()

            historical_commit = commit_catalog(historical_bytes, "candidate")
            wrong_pointer_commit = commit_catalog(wrong_pointer_bytes, "wrong pointer")
            catalog.write_bytes(current_bytes)
            current_sha = hashlib.sha256(current_bytes).hexdigest()
            historical_sha = hashlib.sha256(historical_bytes).hexdigest()
            sidecar = catalog.with_name("libs.versions.toml.sha256")
            sidecar.write_text(f"{current_sha}  libs.versions.toml\n", encoding="utf-8")

            receipt_path = repo / "docs" / "releases" / "candidate.json"
            receipt_path.parent.mkdir(parents=True)
            receipt = {
                "catalog": {
                    "content-commit": historical_commit,
                    "sha256": historical_sha,
                }
            }
            receipt_bytes = self.module.pretty_json(receipt)
            receipt_path.write_bytes(receipt_bytes)
            ledger["candidate"] = {"catalog-sha256": historical_sha}
            ledger["candidate-validation-evidence"] = {
                "path": "docs/releases/candidate.json",
                "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            }

            with mock.patch.object(self.module, "REPO_ROOT", repo):
                self.assertEqual(
                    current_sha,
                    self.module.validate_catalog(ledger, catalog, sidecar),
                )

                sidecar.write_text(
                    f"{'0' * 64}  libs.versions.toml\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(RuntimeError, "sidecar"):
                    self.module.validate_catalog(ledger, catalog, sidecar)
                sidecar.write_text(
                    f"{current_sha}  libs.versions.toml\n", encoding="utf-8"
                )

                receipt["catalog"]["content-commit"] = wrong_pointer_commit
                receipt_bytes = self.module.pretty_json(receipt)
                receipt_path.write_bytes(receipt_bytes)
                ledger["candidate-validation-evidence"]["sha256"] = hashlib.sha256(
                    receipt_bytes
                ).hexdigest()
                with self.assertRaisesRegex(
                    RuntimeError, "historical candidate catalog"
                ):
                    self.module.validate_catalog(ledger, catalog, sidecar)

                tree_sha = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "rev-parse",
                        f"{historical_commit}^{{tree}}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                receipt["catalog"]["content-commit"] = tree_sha
                receipt_bytes = self.module.pretty_json(receipt)
                receipt_path.write_bytes(receipt_bytes)
                ledger["candidate-validation-evidence"]["sha256"] = hashlib.sha256(
                    receipt_bytes
                ).hexdigest()
                with self.assertRaisesRegex(RuntimeError, "must name a commit"):
                    self.module.validate_catalog(ledger, catalog, sidecar)

    def test_promote_ledger_binds_every_delta_to_immutable_receipt(self) -> None:
        specs = self.module.build_specs(self.ledger)
        observations = self.module.validate_observations(
            specs, self.observations(specs)
        )

        promoted = self.module.promote_ledger(
            self.ledger,
            specs,
            observations,
            receipt_path="docs/releases/resolved-graphs.json",
            receipt_sha256="b" * 64,
        )

        self.assertEqual(promoted["status"], "verified-resolved-graph")
        self.assertEqual(promoted["resolved-graph-evidence"]["spec-count"], 3)
        for delta in promoted["delta"]:
            self.assertEqual(delta["verification"], "verified-resolved-graph")
            self.assertTrue(delta["resolved-graph-specs"])

    def test_main_validates_receipt_destination_before_running_gradle(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            canonical_receipt = root.resolve() / "docs" / "resolved-graphs.json"
            self.assertEqual(
                self.module.validate_receipt_destination(canonical_receipt, root),
                canonical_receipt,
            )
            ledger_path = root / "config" / "latest-stable-version-deltas.json"
            ledger_path.parent.mkdir(parents=True)
            ledger_path.write_bytes(self.module.pretty_json(ledger))
            catalog = root / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir()
            catalog.write_text("[versions]\nexample = \"1.1.0\"\n", encoding="utf-8")
            sidecar = root / "gradle" / "libs.versions.toml.sha256"
            sidecar.write_text("catalog\n", encoding="utf-8")
            log_path = root / "build" / "resolved-graphs.log"
            outside_receipt = Path(temporary_directory).parent / "outside-receipt.json"

            with (
                mock.patch.object(self.module, "REPO_ROOT", root),
                mock.patch.object(self.module, "validate_catalog", return_value="a" * 64),
                mock.patch.object(
                    self.module, "run_gradle", return_value=([], [])
                ) as run_gradle,
                mock.patch.object(
                    self.module, "validate_observations", return_value=[]
                ),
                mock.patch(
                    "sys.argv",
                    [
                        "verify-latest-stable-resolved-graphs.py",
                        "--ledger",
                        str(ledger_path),
                        "--catalog",
                        str(catalog),
                        "--catalog-sidecar",
                        str(sidecar),
                        "--receipt",
                        str(outside_receipt),
                        "--log",
                        str(log_path),
                    ],
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "receipt path"):
                    self.module.main()

            run_gradle.assert_not_called()
            self.assertFalse(outside_receipt.exists())
            self.assertFalse(log_path.exists())

    def test_main_continues_graph_validation_after_transaction_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ledger_path = root / "config" / "latest-stable-version-deltas.json"
            ledger_path.parent.mkdir(parents=True)
            ledger_path.write_bytes(self.module.pretty_json(self.ledger))
            catalog = root / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir()
            catalog.write_text("[versions]\nexample = \"1.1.0\"\n", encoding="utf-8")
            sidecar = root / "gradle" / "libs.versions.toml.sha256"
            sidecar.write_text("test\n", encoding="utf-8")
            receipt_path = root / "docs" / "releases" / "resolved-graphs.json"
            log_path = root / "build" / "resolved-graphs.log"

            def run_gradle(specs, output_log):
                output_log.parent.mkdir(parents=True, exist_ok=True)
                output_log.write_text("resolved graph evidence\n", encoding="utf-8")
                return self.observations(specs), [
                    "/repo/gradlew",
                    "-p",
                    "/repo/build/resolved-graphs-test",
                    "resolveLatestStableGraphs",
                ]

            with (
                mock.patch.object(self.module, "REPO_ROOT", root),
                mock.patch.object(
                    self.module, "recover_catalog_rollout_transaction", return_value=True
                ),
                mock.patch.object(self.module, "validate_catalog", return_value="a" * 64),
                mock.patch.object(self.module, "run_gradle", side_effect=run_gradle) as run,
                mock.patch(
                    "sys.argv",
                    [
                        "verify-latest-stable-resolved-graphs.py",
                        "--ledger",
                        str(ledger_path),
                        "--catalog",
                        str(catalog),
                        "--catalog-sidecar",
                        str(sidecar),
                        "--receipt",
                        str(receipt_path),
                        "--log",
                        str(log_path),
                    ],
                ),
            ):
                self.assertEqual(self.module.main(), 0)

            run.assert_called_once()
            self.assertTrue(receipt_path.is_file())

    def test_main_promotion_updates_the_central_immutable_rollout_snapshot(self) -> None:
        audit_module = importlib.util.spec_from_file_location(
            "audit_latest_stable_for_graph_promotion",
            REPO_ROOT / "scripts" / "audit-latest-stable.py",
        )
        self.assertIsNotNone(audit_module)
        self.assertIsNotNone(audit_module.loader)
        audit = importlib.util.module_from_spec(audit_module)
        audit_module.loader.exec_module(audit)

        ledger = copy.deepcopy(self.ledger)
        ledger.update(
            {
                "rollout": "candidate",
                "baseline": {"catalog-ref": "baseline"},
                "audit": {
                    "path": "config/latest-stable-version-audit.json",
                    "sha256": "f" * 64,
                },
            }
        )
        audit_bytes = b'{"schema-version":1}\n'
        ledger["audit"]["sha256"] = hashlib.sha256(audit_bytes).hexdigest()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = root / "config"
            config.mkdir()
            audit_path = config / "latest-stable-version-audit.json"
            audit_path.write_bytes(audit_bytes)
            catalog = config / "catalog.toml"
            catalog.write_text("[versions]\nexample = \"1.1.0\"\n", encoding="utf-8")
            sidecar = config / "catalog.sha256"
            sidecar.write_text("test\n", encoding="utf-8")

            pending_artifacts = audit.snapshot_rollout_evidence(
                ledger, audit_bytes, repository_root=root
            )
            central_path = config / "central-catalog-version-deltas.json"
            central = audit.upsert_catalog_rollout(
                {"schema-version": 2, "subsequent-rollouts": []},
                ledger,
                pending_artifacts,
            )
            central_path.write_bytes(audit.pretty_json(central))
            ledger_path = config / "latest-stable-version-deltas.json"
            ledger_path.write_bytes(self.module.pretty_json(ledger))
            pending_snapshot_path = root / pending_artifacts["authority-delta-ledger"]["path"]
            pending_snapshot_bytes = pending_snapshot_path.read_bytes()
            receipt_path = root / "docs" / "releases" / "resolved-graphs.json"
            log_path = root / "build" / "resolved-graphs.log"

            def run_gradle(specs, output_log):
                output_log.parent.mkdir(parents=True, exist_ok=True)
                output_log.write_text("resolved graph evidence\n", encoding="utf-8")
                return self.observations(specs), [
                    "/repo/gradlew",
                    "-p",
                    "/repo/build/resolved-graphs-test",
                    "resolveLatestStableGraphs",
                ]

            with (
                mock.patch.object(self.module, "REPO_ROOT", root),
                mock.patch.object(self.module, "validate_catalog", return_value="a" * 64),
                mock.patch.object(self.module, "run_gradle", side_effect=run_gradle),
                mock.patch("sys.argv", [
                    "verify-latest-stable-resolved-graphs.py",
                    "--ledger", str(ledger_path),
                    "--catalog", str(catalog),
                    "--catalog-sidecar", str(sidecar),
                    "--central-ledger", str(central_path),
                    "--receipt", "docs/releases/resolved-graphs.json",
                    "--log", str(log_path),
                    "--promote",
                ]),
            ):
                self.assertEqual(self.module.main(), 0)

            promoted = json.loads(ledger_path.read_text(encoding="utf-8"))
            updated_central = json.loads(central_path.read_text(encoding="utf-8"))
            row = updated_central["subsequent-rollouts"][0]
            self.assertEqual(promoted["status"], "verified-resolved-graph")
            self.assertEqual(row["status"], "verified-resolved-graph")
            self.assertEqual(
                row["resolved-graph-evidence"], promoted["resolved-graph-evidence"]
            )
            self.assertTrue(receipt_path.is_file())
            self.assertNotEqual(
                row["authority-delta-ledger"],
                pending_artifacts["authority-delta-ledger"]["path"],
            )
            self.assertEqual(pending_snapshot_path.read_bytes(), pending_snapshot_bytes)
            verified_snapshot_path = root / row["authority-delta-ledger"]
            verified_snapshot = json.loads(
                verified_snapshot_path.read_text(encoding="utf-8")
            )
            self.assertEqual(verified_snapshot["status"], "verified-resolved-graph")
            self.assertEqual(
                hashlib.sha256(verified_snapshot_path.read_bytes()).hexdigest(),
                row["authority-delta-ledger-sha256"],
            )

    def test_receipt_command_does_not_capture_deleted_temporary_path(self) -> None:
        command = [
            "/repo/gradlew",
            "-p",
            "/repo/build/resolved-graphs-random",
            "resolveLatestStableGraphs",
        ]

        normalized = self.module.normalize_receipt_command(command)

        self.assertEqual(
            normalized,
            [
                "./gradlew",
                "-p",
                "<temporary-project>",
                "resolveLatestStableGraphs",
            ],
        )

    def test_run_gradle_creates_build_directory_before_temporary_project(self) -> None:
        specs = self.module.build_specs(self.ledger)
        output_log = self.module.REPO_ROOT / "build" / "test-resolved-graphs.log"
        temporary_project = self.module.REPO_ROOT / "build" / "resolved-graphs-test"
        completed = mock.Mock(returncode=0, stdout="", stderr="")

        with (
            mock.patch.object(Path, "mkdir") as mkdir,
            mock.patch.object(
                self.module.tempfile,
                "TemporaryDirectory",
                return_value=mock.MagicMock(
                    __enter__=mock.Mock(return_value=str(temporary_project)),
                    __exit__=mock.Mock(return_value=False),
                ),
            ) as temporary_directory,
            mock.patch.object(Path, "write_text"),
            mock.patch.object(self.module.subprocess, "run", return_value=completed),
        ):
            self.module.run_gradle(specs, output_log)

        mkdir.assert_any_call(parents=True, exist_ok=True)
        temporary_directory.assert_called_once_with(
            prefix="resolved-graphs-", dir=self.module.REPO_ROOT / "build"
        )

    def test_validate_receipt_replays_contract_observations_and_deltas(self) -> None:
        specs = self.module.build_specs(self.ledger)
        observations = self.module.validate_observations(
            specs, self.observations(specs)
        )
        receipt = {
            "catalog-sha256": self.ledger["candidate"]["catalog-sha256"],
            "command": ["./gradlew"],
            "graph-deltas": list(self.module.build_graph_deltas(specs, observations)),
            "ledger-contract-sha256": self.module.resolution_contract_sha256(
                self.ledger
            ),
            "log-sha256": "b" * 64,
            "observation-count": len(observations),
            "observations": list(observations),
            "schema-version": 2,
            "spec-count": len(specs),
            "status": "verified-resolved-graph",
        }

        validated = self.module.validate_receipt(self.ledger, receipt)

        self.assertEqual(len(validated), 6)
        tampered = json.loads(json.dumps(receipt))
        tampered["graph-deltas"][0]["added-components"] = []
        with self.assertRaisesRegex(RuntimeError, "graph deltas"):
            self.module.validate_receipt(self.ledger, tampered)


if __name__ == "__main__":
    unittest.main()
