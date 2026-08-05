from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
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

    def test_catalog_validation_binds_bytes_sidecar_and_candidate_versions(
        self,
    ) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["candidate"] = {}
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "libs.versions.toml"
            sidecar = Path(directory) / "libs.versions.toml.sha256"
            catalog.write_text(
                '[versions]\nexample = "1.1.0"\nnative-plugin = "1.1.0"\n',
                encoding="utf-8",
            )
            digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
            ledger["candidate"]["catalog-sha256"] = digest
            sidecar.write_text(f"{digest}  libs.versions.toml\n", encoding="utf-8")

            self.module.validate_catalog(ledger, catalog, sidecar)

            sidecar.write_text(f"{'0' * 64}  libs.versions.toml\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "sidecar"):
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
