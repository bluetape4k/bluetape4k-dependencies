from __future__ import annotations

import importlib.util
import json
import subprocess
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


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_catalog(repository: Path, content: str, message: str) -> str:
    catalog = repository / "gradle" / "libs.versions.toml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(content, encoding="utf-8")
    run_git(repository, "add", str(catalog.relative_to(repository)))
    run_git(repository, "commit", "-m", message)
    return run_git(repository, "rev-parse", "HEAD")


def create_catalog_history(repository: Path) -> dict[str, str]:
    repository.mkdir(parents=True)
    run_git(repository, "init", "--initial-branch=develop")
    run_git(repository, "config", "user.name", "Bluetape Test")
    run_git(repository, "config", "user.email", "test@bluetape4k.invalid")

    rollback = commit_catalog(repository, '[versions]\nmarker = "rollback"\n', "rollback")
    minimum = commit_catalog(repository, '[versions]\nmarker = "minimum"\n', "minimum")
    forward = commit_catalog(repository, '[versions]\nmarker = "forward"\n', "forward")
    candidate = commit_catalog(repository, '[versions]\nmarker = "candidate"\n', "candidate")

    run_git(repository, "switch", "--detach", minimum)
    outside = commit_catalog(repository, '[versions]\nmarker = "outside"\n', "outside")
    run_git(repository, "switch", "develop")
    return {
        "rollback": rollback,
        "minimum": minimum,
        "forward": forward,
        "candidate": candidate,
        "outside": outside,
    }


def write_snapshot_consumer(repository: Path, settings_ref: str, ci_ref: str) -> None:
    workflow = repository / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    (repository / "settings.gradle.kts").write_text(
        f'catalogRef.orElse("{settings_ref}")\n', encoding="utf-8"
    )
    workflow.write_text(
        "env:\n"
        "  BLUETAPE4K_DEPENDENCIES_CATALOG_REF: "
        f"'{ci_ref}'\n",
        encoding="utf-8",
    )


def snapshot_policy(
    minimum_ref: str,
    override_ref: str | None = None,
) -> dict[str, object]:
    policy: dict[str, object] = {
        "snapshot-catalog-ref": minimum_ref,
        "snapshot-catalog-repositories": ["internal-library"],
        "official-release-repositories": [],
    }
    if override_ref is not None:
        policy["snapshot-catalog-ref-overrides"] = {
            "internal-library": override_ref,
        }
    return {
        "stable-version": "1.4.0",
        "consumer-policy": policy,
    }


class PostPublishNextDevelopmentLineTest(unittest.TestCase):
    def test_build_bom_checkout_fetches_full_history_for_catalog_ancestry(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        build_job = workflow.split("\n  build:\n", maxsplit=1)[1].split(
            "\n  publication-pom-contract:\n", maxsplit=1
        )[0]

        self.assertRegex(
            build_job,
            r"- uses: actions/checkout@v7\n\s+with:\n\s+fetch-depth: 0",
        )

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

    def test_manifest_classifies_snapshot_libraries_and_example_consumers(self) -> None:
        module = load_script()
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
            policy["snapshot-catalog-ref-overrides"],
            {
                "bluetape4k-exposed": "df64293753a9491b337852a158f89d4a93a1734a",
                "bluetape4k-graph": "df64293753a9491b337852a158f89d4a93a1734a",
            },
        )
        self.assertEqual(
            {item["repository"] for item in policy["official-release-repositories"]},
            {
                "bluetape4k-workshop",
                "clinic-appointment",
                "timefold-workshop",
            },
        )
        self.assertEqual(
            {
                item["repository"]
                for item in policy["development-snapshot-repositories"]
            },
            {
                "exposed-r2dbc-workshop",
                "exposed-workshop",
            },
        )
        self.assertEqual(
            set(module.required_workspace_repositories(document)),
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
                "bluetape4k-workshop",
                "clinic-appointment",
                "timefold-workshop",
                "exposed-r2dbc-workshop",
                "exposed-workshop",
            },
        )

    def test_snapshot_candidate_branch_is_derived_from_the_immutable_ref(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(
            module.snapshot_candidate_branch(document),
            "chore/snapshot-catalog-91f9ea9",
        )

    def test_manifest_rejects_source_snapshot_suffix(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        document["source-contract"]["snapshotVersion"] = "-SNAPSHOT"

        with self.assertRaisesRegex(RuntimeError, "snapshotVersion"):
            module.validate_manifest(document)

    def test_manifest_rejects_invalid_snapshot_catalog_ref_override(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        document["consumer-policy"]["snapshot-catalog-ref-overrides"] = {
            "unmanaged-library": "not-a-sha",
        }

        with self.assertRaisesRegex(RuntimeError, "outside snapshot-catalog-repositories"):
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

    def test_consumer_policy_accepts_repository_specific_catalog_minimum(self) -> None:
        module = load_script()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                refs["minimum"],
                refs["minimum"],
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["rollback"], refs["minimum"]),
                central,
            )

        self.assertEqual(errors, [])

    def test_consumer_policy_accepts_catalog_ref_after_minimum(self) -> None:
        module = load_script()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                refs["forward"],
                refs["forward"],
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["minimum"]),
                central,
            )

        self.assertEqual(errors, [])

    def test_consumer_policy_rejects_catalog_ref_before_minimum(self) -> None:
        module = load_script()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                refs["rollback"],
                refs["rollback"],
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["minimum"]),
                central,
            )

        self.assertIn(
            "internal-library snapshot catalog ref "
            f"{refs['rollback']} is older than minimum {refs['minimum']}",
            errors,
        )

    def test_consumer_policy_rejects_catalog_ref_outside_candidate_history(self) -> None:
        module = load_script()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                refs["outside"],
                refs["outside"],
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["minimum"]),
                central,
            )

        self.assertIn(
            "internal-library snapshot catalog ref "
            f"{refs['outside']} is outside candidate HEAD history",
            errors,
        )

    def test_consumer_policy_rejects_settings_and_ci_catalog_ref_mismatch(self) -> None:
        module = load_script()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                refs["forward"],
                refs["minimum"],
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["minimum"]),
                central,
            )

        self.assertIn(
            "internal-library settings catalog ref "
            f"{refs['forward']} must match CI catalog ref {refs['minimum']}",
            errors,
        )

    def test_consumer_policy_rejects_non_sha_catalog_ref(self) -> None:
        module = load_script()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                "develop",
                "develop",
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["minimum"]),
                central,
            )

        self.assertIn(
            "internal-library settings catalog ref must be a lowercase "
            "40-character Git SHA, got 'develop'",
            errors,
        )

    def test_consumer_policy_rejects_missing_catalog_commit(self) -> None:
        module = load_script()
        missing_ref = "f" * 40

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            refs = create_catalog_history(central)
            write_snapshot_consumer(
                workspace / "internal-library",
                missing_ref,
                missing_ref,
            )

            errors = module.verify_consumer_policy(
                workspace,
                snapshot_policy(refs["minimum"]),
                central,
            )

        self.assertIn(
            f"internal-library snapshot catalog ref {missing_ref} "
            "is missing from central history",
            errors,
        )

    def test_consumer_policy_requires_development_snapshot_for_snapshot_examples(self) -> None:
        module = load_script()
        document = {
            "stable-version": "1.4.0",
            "development-version": "2.0.0",
            "snapshot-suffix": "-SNAPSHOT",
            "consumer-policy": {
                "snapshot-catalog-ref": "a" * 40,
                "snapshot-catalog-repositories": [],
                "official-release-repositories": [],
                "development-snapshot-repositories": [
                    {
                        "repository": "example-app",
                        "catalog-version-key": "bluetape4k-dependencies",
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            catalog = workspace / "example-app" / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                '[versions]\nbluetape4k-dependencies = "1.4.0"\n',
                encoding="utf-8",
            )

            errors = module.verify_consumer_policy(workspace, document)

            self.assertIn(
                "example-app must use development bluetape4k-dependencies "
                "2.0.0-SNAPSHOT, got '1.4.0'",
                errors,
            )

            catalog.write_text(
                '[versions]\nbluetape4k-dependencies = "2.0.0-SNAPSHOT"\n',
                encoding="utf-8",
            )

            self.assertEqual(module.verify_consumer_policy(workspace, document), [])


if __name__ == "__main__":
    unittest.main()
