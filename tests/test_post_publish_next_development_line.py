from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-post-publish-next-development-line.py"
MANIFEST = REPO_ROOT / "config" / "post-publish-next-development-line.json"


def load_script():
    spec = importlib.util.spec_from_file_location("verify_next_line", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load post-publish next-line verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PostPublishNextDevelopmentLineTest(unittest.TestCase):
    def test_checked_in_manifest_has_runtime_snapshot_contract(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        module.validate_manifest(document)
        self.assertEqual(document["source-contract"]["snapshotVersion"], "")
        self.assertEqual(
            document["source-contract"]["runtime-property"],
            "-PsnapshotVersion=-SNAPSHOT",
        )
        self.assertEqual(len(document["publishable-repositories"]), 8)

    def test_manifest_separates_snapshot_libraries_from_official_release_examples(self) -> None:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        policy = document.get("consumer-policy")
        self.assertIsInstance(policy, dict)
        self.assertEqual(
            set(policy["snapshot-catalog-repositories"]),
            {
                "bluetape4k-projects",
                "bluetape4k-aws",
                "bluetape4k-experimental",
                "bluetape4k-exposed",
                "bluetape4k-graph",
                "bluetape4k-image",
                "bluetape4k-javers",
                "bluetape4k-leader",
                "bluetape4k-text",
            },
        )
        self.assertEqual(
            {item["repository"] for item in policy["official-release-repositories"]},
            {
                "bluetape4k-workshop",
                "clinic-appointment",
                "exposed-r2dbc-workshop",
                "exposed-workshop",
                "timefold-workshop",
            },
        )

    def test_manifest_rejects_source_snapshot_suffix(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        document["source-contract"]["snapshotVersion"] = "-SNAPSHOT"

        with self.assertRaisesRegex(RuntimeError, "snapshotVersion"):
            module.validate_manifest(document)

    def test_development_line_rejects_stable_internal_ref(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            (central / "gradle").mkdir(parents=True)
            (central / "gradle.properties").write_text(
                "baseVersion=1.5.0\nsnapshotVersion=\n", encoding="utf-8"
            )
            (central / "gradle" / "libs.versions.toml").write_text(
                "[versions]\n"
                "bluetape4k-dependencies = \"1.5.0\"\n"
                "bluetape4k-bom = \"1.12.1\"\n",
                encoding="utf-8",
            )
            for item in document["publishable-repositories"]:
                repo = workspace / item["repository"]
                (repo / ".github" / "workflows").mkdir(parents=True)
                (repo / "gradle.properties").write_text(
                    f"baseVersion={item['base-version']}\nsnapshotVersion=\n",
                    encoding="utf-8",
                )
                (repo / ".github" / "workflows" / "publish-snapshot.yml").write_text(
                    "JAVA_VERSION: '25'\n-PsnapshotVersion=-SNAPSHOT\n", encoding="utf-8"
                )
                (repo / ".github" / "workflows" / "release.yml").write_text(
                    "snapshotVersion must be empty for release\n", encoding="utf-8"
                )

            errors = module.verify_development(central, workspace, document, False)

        self.assertTrue(any("bluetape4k-bom" in error for error in errors))

    def test_stable_boundary_rejects_snapshot_refs(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as temporary:
            central = Path(temporary) / "central"
            (central / "gradle").mkdir(parents=True)
            (central / "gradle.properties").write_text(
                "baseVersion=1.5.0\nsnapshotVersion=\n", encoding="utf-8"
            )
            (central / "gradle" / "libs.versions.toml").write_text(
                "[versions]\n"
                "bluetape4k-dependencies = \"1.5.0\"\n"
                "bluetape4k-bom = \"1.13.0-SNAPSHOT\"\n",
                encoding="utf-8",
            )

            errors = module.verify_stable(central, document, "1.5.0")

        self.assertIn(
            "stable catalog cannot reference a snapshot: bluetape4k-bom=1.13.0-SNAPSHOT",
            errors,
        )

    def test_development_line_rejects_snapshot_bom_in_example_repository(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        snapshot_ref = "a" * 40
        snapshot_repositories = [
            item["repository"] for item in document["publishable-repositories"]
        ] + ["bluetape4k-experimental"]
        document["consumer-policy"] = {
            "snapshot-catalog-ref": snapshot_ref,
            "snapshot-catalog-repositories": snapshot_repositories,
            "official-release-repositories": [
                {
                    "repository": "example-app",
                    "catalog-version-key": "bluetape4k-dependencies",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            (central / "gradle").mkdir(parents=True)
            (central / "gradle.properties").write_text(
                "baseVersion=1.5.0\nsnapshotVersion=\n", encoding="utf-8"
            )
            catalog_lines = [
                "[versions]",
                'bluetape4k-dependencies = "1.5.0"',
            ]
            for item in document["publishable-repositories"]:
                catalog_lines.append(
                    f'{item["catalog-alias"]} = "{item["base-version"]}-SNAPSHOT"'
                )
                repo = workspace / item["repository"]
                (repo / ".github" / "workflows").mkdir(parents=True)
                (repo / "gradle.properties").write_text(
                    f"baseVersion={item['base-version']}\nsnapshotVersion=\n",
                    encoding="utf-8",
                )
                (repo / ".github" / "workflows" / "publish-snapshot.yml").write_text(
                    "JAVA_VERSION: '25'\n-PsnapshotVersion=-SNAPSHOT\n", encoding="utf-8"
                )
                (repo / ".github" / "workflows" / "release.yml").write_text(
                    "snapshotVersion must be empty for release\n", encoding="utf-8"
                )
            (central / "gradle" / "libs.versions.toml").write_text(
                "\n".join(catalog_lines) + "\n", encoding="utf-8"
            )
            for repository in snapshot_repositories:
                repo = workspace / repository
                repo.mkdir(parents=True, exist_ok=True)
                (repo / "settings.gradle.kts").write_text(
                    f'catalogRef.orElse("{snapshot_ref}")\n', encoding="utf-8"
                )
            example_catalog = workspace / "example-app" / "gradle" / "libs.versions.toml"
            example_catalog.parent.mkdir(parents=True)
            example_catalog.write_text(
                '[versions]\nbluetape4k-dependencies = "1.5.0-SNAPSHOT"\n',
                encoding="utf-8",
            )

            errors = module.verify_development(central, workspace, document, False)

        self.assertIn(
            "example-app must use official bluetape4k-dependencies 1.4.0, got '1.5.0-SNAPSHOT'",
            errors,
        )

    def test_consumer_policy_rejects_settings_and_ci_catalog_ref_mismatch(self) -> None:
        module = load_script()
        expected_ref = "a" * 40
        document = {
            "stable-version": "1.4.0",
            "consumer-policy": {
                "snapshot-catalog-ref": expected_ref,
                "snapshot-catalog-repositories": ["internal-library"],
                "official-release-repositories": [
                    {
                        "repository": "example-app",
                        "catalog-version-key": "bluetape4k-dependencies",
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            internal = workspace / "internal-library"
            (internal / ".github" / "workflows").mkdir(parents=True)
            (internal / "settings.gradle.kts").write_text(
                f'catalogRef.orElse("{expected_ref}")\n', encoding="utf-8"
            )
            (internal / ".github" / "workflows" / "ci.yml").write_text(
                "env:\n"
                "  BLUETAPE4K_DEPENDENCIES_CATALOG_REF: "
                f"'{('b' * 40)}'\n",
                encoding="utf-8",
            )
            example_catalog = workspace / "example-app" / "gradle" / "libs.versions.toml"
            example_catalog.parent.mkdir(parents=True)
            example_catalog.write_text(
                '[versions]\nbluetape4k-dependencies = "1.4.0"\n',
                encoding="utf-8",
            )

            errors = module.verify_consumer_policy(workspace, document)

        self.assertIn(
            "internal-library CI must use snapshot catalog ref "
            f"{expected_ref}, got '{('b' * 40)}'",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
