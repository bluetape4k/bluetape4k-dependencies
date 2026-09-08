from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = REPO_ROOT / "config" / "post-publish-next-development-line.json"
SCRIPT = REPO_ROOT / "scripts" / "write-snapshot-consumer-inputs.py"
CHECKOUT = REPO_ROOT / "scripts" / "checkout-snapshot-consumers.sh"


def load_module():
    spec = importlib.util.spec_from_file_location("snapshot_consumer_inputs", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
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


def initialize_repository(repository: Path, content: str) -> str:
    repository.mkdir(parents=True)
    run_git(repository, "init", "--initial-branch=develop")
    run_git(repository, "config", "user.name", "Bluetape Test")
    run_git(repository, "config", "user.email", "test@bluetape4k.invalid")
    (repository / "README.md").write_text(content, encoding="utf-8")
    run_git(repository, "add", "README.md")
    run_git(repository, "commit", "-m", "fixture")
    return run_git(repository, "rev-parse", "HEAD")


class SnapshotConsumerInputsTest(unittest.TestCase):
    def create_fixture(self, root: Path):
        module = load_module()
        policy, verifier = module.load_policy(POLICY)
        central = root / "central"
        initialize_repository(central, "central")
        repositories = {}
        snapshot_names = module.snapshot_repositories(policy, verifier)
        for name in module.required_repositories(policy, verifier):
            repository = root / name
            head = initialize_repository(repository, name)
            if name in snapshot_names:
                catalog_ref = "a" * 40
                (repository / "settings.gradle.kts").write_text(
                    f'catalogRef.orElse("{catalog_ref}")\n', encoding="utf-8"
                )
                workflow = repository / ".github" / "workflows" / "ci.yml"
                workflow.parent.mkdir(parents=True)
                workflow.write_text(
                    "env:\n"
                    "  BLUETAPE4K_DEPENDENCIES_CATALOG_REF: "
                    f"'{catalog_ref}'\n",
                    encoding="utf-8",
                )
                run_git(repository, "add", "settings.gradle.kts", ".github")
                run_git(repository, "commit", "-m", "snapshot catalog fixture")
                head = run_git(repository, "rev-parse", "HEAD")
            repositories[name] = head
        return module, policy, verifier, central, root, repositories

    def test_write_captures_clean_consumer_heads_and_catalog_refs(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, policy, verifier, central, workspace, expected = self.create_fixture(root)
            output = root / "snapshot-consumer-inputs.json"
            document = module.create_document(
                policy=policy,
                workspace=workspace,
                central_root=central,
                source_commit=run_git(central, "rev-parse", "HEAD"),
                workflow_run_id="12345",
                workflow_attempt="2",
                verifier=verifier,
            )
            output.write_text(
                json.dumps(document, indent=2) + "\n", encoding="utf-8"
            )

            module.validate_document(
                json.loads(output.read_text(encoding="utf-8")),
                policy,
                verifier,
                expected_source_commit=document["source"]["commit"],
                expected_workflow_run_id="12345",
                expected_workflow_attempt="2",
            )
            self.assertEqual(
                {
                    name: entry["commit"]
                    for name, entry in document["repositories"].items()
                },
                expected,
            )
            for name in module.snapshot_repositories(policy, verifier):
                self.assertEqual(document["repositories"][name]["catalog-ref"], "a" * 40)
                self.assertEqual(
                    document["repositories"][name]["ci-catalog-ref"], "a" * 40
                )

    def test_write_rejects_a_consumer_that_changed_after_ci_validation(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, policy, verifier, central, workspace, _ = self.create_fixture(root)
            changed = workspace / "bluetape4k-projects" / "README.md"
            changed.write_text("drift\n", encoding="utf-8")
            with self.assertRaisesRegex(module.InputError, "checkout is not clean"):
                module.create_document(
                    policy=policy,
                    workspace=workspace,
                    central_root=central,
                    source_commit=run_git(central, "rev-parse", "HEAD"),
                    workflow_run_id="12345",
                    workflow_attempt="1",
                    verifier=verifier,
                )

    def test_validate_rejects_inventory_and_source_drift(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, policy, verifier, central, workspace, _ = self.create_fixture(root)
            document = module.create_document(
                policy=policy,
                workspace=workspace,
                central_root=central,
                source_commit=run_git(central, "rev-parse", "HEAD"),
                workflow_run_id="12345",
                workflow_attempt="1",
                verifier=verifier,
            )
            document["repositories"].pop("bluetape4k-projects")
            with self.assertRaisesRegex(module.InputError, "inventory mismatch"):
                module.validate_document(document, policy, verifier)

            document = module.create_document(
                policy=policy,
                workspace=workspace,
                central_root=central,
                source_commit=run_git(central, "rev-parse", "HEAD"),
                workflow_run_id="12345",
                workflow_attempt="1",
                verifier=verifier,
            )
            with self.assertRaisesRegex(module.InputError, "must match expected CI head"):
                module.validate_document(
                    document,
                    policy,
                    verifier,
                    expected_source_commit="b" * 40,
                )
            with self.assertRaisesRegex(module.InputError, "must match expected attempt"):
                module.validate_document(
                    document,
                    policy,
                    verifier,
                    expected_workflow_attempt="2",
                )

    def test_checkout_helper_uses_exact_manifest_heads(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, policy, verifier, central, workspace, expected = self.create_fixture(root)
            document = module.create_document(
                policy=policy,
                workspace=workspace,
                central_root=central,
                source_commit=run_git(central, "rev-parse", "HEAD"),
                workflow_run_id="12345",
                workflow_attempt="1",
                verifier=verifier,
            )
            manifest = root / "snapshot-consumer-inputs.json"
            manifest.write_text(json.dumps(document) + "\n", encoding="utf-8")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_gh = fake_bin / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "[[ \"$1\" == repo && \"$2\" == clone ]]\n"
                "source=\"$FIXTURE_ROOT/${3#bluetape4k/}\"\n"
                "git clone \"$source\" \"$4\" >/dev/null\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            checked_out = root / "checked-out"
            environment = dict(os.environ)
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FIXTURE_ROOT"] = str(root)
            result = subprocess.run(
                ["bash", str(CHECKOUT), str(checked_out), str(manifest)],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, expected_head in expected.items():
                self.assertEqual(run_git(checked_out / name, "rev-parse", "HEAD"), expected_head)
                self.assertEqual(
                    run_git(checked_out / name, "status", "--porcelain=v1"), ""
                )


if __name__ == "__main__":
    unittest.main()
