from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify-issues-242-243-receipt.py"
SPEC = importlib.util.spec_from_file_location("issues_242_243_receipt", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
receipt = importlib.util.module_from_spec(SPEC)
sys.modules["issues_242_243_receipt"] = receipt
SPEC.loader.exec_module(receipt)


class Issues242243ReceiptTest(unittest.TestCase):
    def test_repository_inventory_reuses_catalog_candidate_authority(self) -> None:
        candidate = receipt._catalog_candidate_module()
        self.assertEqual(receipt.CATALOG_NAMES, candidate.CATALOG_REPOSITORIES)
        self.assertEqual(receipt.SIGNING_NAMES, frozenset(candidate.PUBLISHER_REPOSITORIES))

    def git(
        self,
        root: Path,
        *args: str,
        input_bytes: bytes | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            input=input_bytes,
            capture_output=True,
            check=True,
            env=merged_env,
        )
        return completed.stdout.decode().strip()

    def make_repository(self, workspace: Path, name: str) -> dict[str, object]:
        root = workspace / name
        (root / "gradle").mkdir(parents=True)
        (root / "gradle/libs.versions.toml").write_text(
            '[versions]\ndemo = "1.0.0"\n', encoding="utf-8"
        )
        if name == receipt.CENTRAL_NAME:
            source = root / receipt.CANONICAL_SOURCE_RELATIVE
            source.parent.mkdir(parents=True)
            source.write_text("canonical signing helper\n", encoding="utf-8")
        self.git(root.parent, "init", "-b", "candidate", str(root))
        origin = f"git@github.com:bluetape4k/{name}.git"
        self.git(root, "remote", "add", "origin", origin)
        self.git(root, "config", "user.name", "Receipt Test")
        self.git(root, "config", "user.email", "receipt@example.invalid")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "fixture")
        head = self.git(root, "rev-parse", "HEAD")
        self.git(root, "update-ref", "refs/remotes/origin/develop", head)
        role = "central" if name == receipt.CENTRAL_NAME else receipt._infer_role(name)
        return {
            "name": name,
            "role": role,
            "canonical_path": str(root.resolve()),
            "candidate_worktree": str(root.resolve()),
            "origin": origin,
            "base_ref": "origin/develop",
            "base_sha": head,
            "candidate_branch": "candidate",
            "candidate_head": head,
            "clean": True,
            "exact_head": True,
            "validation_only": role == "validation-only",
        }

    def make_fixture(self) -> tuple[Path, Path, dict[str, object]]:
        workspace = Path(tempfile.mkdtemp(prefix="issues-242-243-")).resolve()
        entries = [self.make_repository(workspace, name) for name in receipt.ALL_NAMES]
        map_path = workspace / "build/issues-242-243/repository-map.json"
        map_path.parent.mkdir(parents=True)
        catalog_entries = entries[: len(receipt.CATALOG_NAMES)]

        def strict_entry(item: dict[str, object]) -> dict[str, object]:
            root = Path(str(item["candidate_worktree"]))
            return {
                "root": str(root),
                "catalog": str(root / "gradle/libs.versions.toml"),
                "origin": item["origin"],
                "branch": item["candidate_branch"],
                "base_sha": item["base_sha"],
                "expected_head": item["candidate_head"],
                "clean": True,
            }

        repository_map = {
            "schema_version": 1,
            "central": strict_entry(catalog_entries[0]),
            "repositories": {
                item["name"].removeprefix("bluetape4k-"): strict_entry(item)
                for item in catalog_entries[1:]
            },
        }
        map_bytes = receipt.canonical_json_bytes(repository_map)
        map_path.write_bytes(map_bytes)
        central = next(item for item in entries if item["name"] == receipt.CENTRAL_NAME)
        source_path = Path(str(central["candidate_worktree"])) / receipt.CANONICAL_SOURCE_RELATIVE
        source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        repository_receipts = []
        for item in entries[: len(receipt.CATALOG_NAMES)]:
            repository_receipts.append(
                {
                    "name": item["name"],
                    "role": item["role"],
                    "origin": item["origin"],
                    "base_ref": item["base_ref"],
                    "base_sha": item["base_sha"],
                    "candidate_branch": item["candidate_branch"],
                    "candidate_worktree": item["candidate_worktree"],
                    "candidate_head": item["candidate_head"],
                    "clean": True,
                    "exact_head": True,
                    "state": "discovered",
                    "signing_sha256": source_digest,
                }
            )
        consumers = []
        for item in entries[len(receipt.CATALOG_NAMES) :]:
            consumers.append(
                {
                    "name": item["name"],
                    "role": "consumer",
                    "origin": item["origin"],
                    "base_ref": item["base_ref"],
                    "base_sha": item["base_sha"],
                    "candidate_branch": item["candidate_branch"],
                    "candidate_worktree": item["candidate_worktree"],
                    "candidate_head": item["candidate_head"],
                    "clean": True,
                    "exact_head": True,
                    "state": "discovered",
                    "signing_sha256": source_digest,
                    "catalog_ref": "candidate/catalog",
                    "catalog_sha256": "a" * 64,
                    "catalog_source": "local-candidate",
                    "bom_coordinate": "io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local",
                    "local_override": "not-applicable",
                    "graphs": [
                        {
                            "coordinate": "ai.timefold.solver:timefold-solver-core",
                            "configuration": "testRuntimeClasspath",
                            "before_version": "2.4.0",
                            "after_version": "2.6.0",
                            "selection_reason": "selected by candidate BOM",
                            "output_sha256": "b" * 64,
                        }
                    ],
                }
            )
        command = {
            "repository": receipt.CENTRAL_NAME,
            "command": "./gradlew build",
            "jdk": "25",
            "gradle": "9.7.0",
            "configuration": "testRuntimeClasspath",
            "elapsed_seconds": 1.0,
            "cache": "isolated",
            "result": "pass",
            "output_sha256": "c" * 64,
        }
        document = {
            "schema_version": 1,
            "issues": [242, 243],
            "current_state": "discovered",
            "validation_budget": {
                "total_seconds": 5400,
                "elapsed_seconds": 0.0,
                "remaining_seconds": 5400.0,
            },
            "repository_map": {"path": str(map_path), "sha256": receipt.sha256_bytes(map_bytes)},
            "central": {
                "base_sha": central["base_sha"],
                "candidate_head": central["candidate_head"],
                "clean": True,
                "exact_head": True,
                "state": "discovered",
            },
            "canonical_signing_source": {"path": str(source_path.resolve()), "sha256": source_digest},
            "repositories": repository_receipts,
            "consumers": consumers,
            "commands": [command],
            "phases": [{"name": "discover", "result": "pass", "output_sha256": "d" * 64}],
            "failure_record": [],
            "rollback_record": [],
            "evidence_commit": None,
        }
        receipt_path = workspace / "build/issues-242-243/local-receipt.json"
        receipt_path.write_bytes(receipt.canonical_json_bytes(document))
        return workspace, receipt_path, document

    def make_prospective_commit(self, root: Path, parent: str, content: bytes) -> str:
        blob = self.git(root, "hash-object", "-w", "--stdin", input_bytes=content)
        index = root / ".receipt-test-index"
        try:
            env = {"GIT_INDEX_FILE": str(index)}
            self.git(root, "read-tree", f"{parent}^{{tree}}", env=env)
            self.git(
                root,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{blob},{receipt.EVIDENCE_RECEIPT_PATH}",
                env=env,
            )
            tree = self.git(root, "write-tree", env=env)
            return self.git(
                root,
                "commit-tree",
                tree,
                "-p",
                parent,
                input_bytes=b"prospective receipt\n",
                env={
                    **env,
                    "GIT_AUTHOR_NAME": "Receipt Test",
                    "GIT_AUTHOR_EMAIL": "receipt@example.invalid",
                    "GIT_COMMITTER_NAME": "Receipt Test",
                    "GIT_COMMITTER_EMAIL": "receipt@example.invalid",
                },
            )
        finally:
            index.unlink(missing_ok=True)

    def test_rejects_missing_repository(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"] = document["consumers"][:1]
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "consumer|repository"):
            receipt.validate_receipt(path)

    def test_rejects_blocked_or_prepared_repository(self) -> None:
        workspace, path, document = self.make_fixture()
        target = document["repositories"][1]
        for state in ("prepared", "blocked"):
            target["state"] = state
            document["current_state"] = state
            path.write_bytes(receipt.canonical_json_bytes(document))
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "validate", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, state)
            self.assertIn("validated", result.stderr, state)

    def test_rejects_digest_mismatch(self) -> None:
        workspace, path, document = self.make_fixture()
        document["canonical_signing_source"]["sha256"] = "e" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "SHA-256|digest"):
            receipt.validate_receipt(path)

    def test_rejects_missing_timefold_coordinate(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"][0]["graphs"][0].pop("coordinate")
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "graph|fields|coordinate"):
            receipt.validate_receipt(path)

    def test_rejects_secret_bearing_command(self) -> None:
        workspace, path, document = self.make_fixture()
        document["commands"][0]["command"] = "PASSWORD=sentinel ./gradlew test"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "secret|command"):
            receipt.validate_receipt(path)

    def test_accepts_exact_validated_repository_set(self) -> None:
        workspace, path, document = self.make_fixture()
        validated = receipt.validate_receipt(path)
        self.assertEqual(validated["issues"], [242, 243])
        self.assertEqual(len(validated["repositories"]), 10)
        self.assertEqual({item["name"] for item in validated["consumers"]}, set(receipt.CONSUMER_NAMES))

    def test_rejects_malformed_schema_and_unknown_field(self) -> None:
        workspace, path, document = self.make_fixture()
        document["schema_version"] = 2
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "schema"):
            receipt.validate_receipt(path)
        document["schema_version"] = 1
        document["unexpected"] = True
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "fields"):
            receipt.validate_receipt(path)

    def test_rejects_dirty_and_mismatched_worktree(self) -> None:
        workspace, path, document = self.make_fixture()
        root = Path(document["repositories"][1]["candidate_worktree"])
        (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "dirty|not clean"):
            receipt.validate_receipt(path)
        (root / "dirty.txt").unlink()
        document["repositories"][1]["candidate_head"] = "1" * 40
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "candidate SHA|HEAD"):
            receipt.validate_receipt(path)

    def test_rejects_consumer_origin_mismatch(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"][0]["origin"] = (
            "git@github.com:bluetape4k/not-the-workshop.git"
        )
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "origin"):
            receipt.validate_receipt(path)

    def test_rejects_graph_field_omission_and_invalid_hash(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"][1]["graphs"][0]["output_sha256"] = "not-a-digest"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "SHA-256|graph"):
            receipt.validate_receipt(path)
        document["consumers"][1]["graphs"][0]["output_sha256"] = "b" * 64
        document["repositories"][2]["base_sha"] = "not-a-commit"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "commit|base"):
            receipt.validate_receipt(path)

    def test_rejects_control_characters_and_invalid_evidence_path(self) -> None:
        workspace, path, document = self.make_fixture()
        document["phases"][0]["name"] = "discover\x1b[31m"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "control|ANSI"):
            receipt.validate_receipt(path)

    def test_adopted_receipt_checks_prospective_parent_path_and_blob_digest(self) -> None:
        workspace, path, document = self.make_fixture()
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["central"]["state"] = "adopted"
        document["current_state"] = "adopted"
        central_root = Path(document["repositories"][0]["candidate_worktree"])
        content = b"tracked local receipt bytes\n"
        prospective = self.make_prospective_commit(
            central_root, document["central"]["candidate_head"], content
        )
        document["evidence_commit"] = {
            "parent": document["central"]["candidate_head"],
            "path": receipt.EVIDENCE_RECEIPT_PATH,
            "bytes_sha256": hashlib.sha256(content).hexdigest(),
        }
        path.write_bytes(receipt.canonical_json_bytes(document))
        receipt.validate_receipt(path, evidence_commit=prospective)
        document["evidence_commit"]["parent"] = "1" * 40
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "parent"):
            receipt.validate_receipt(path, evidence_commit=prospective)

    def test_adopted_receipt_rejects_path_and_digest_mismatch(self) -> None:
        workspace, path, document = self.make_fixture()
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["central"]["state"] = "adopted"
        document["current_state"] = "adopted"
        central_root = Path(document["repositories"][0]["candidate_worktree"])
        content = b"tracked local receipt bytes\n"
        prospective = self.make_prospective_commit(
            central_root, document["central"]["candidate_head"], content
        )
        document["evidence_commit"] = {
            "parent": document["central"]["candidate_head"],
            "path": "docs/releases/not-allowlisted.json",
            "bytes_sha256": hashlib.sha256(content).hexdigest(),
        }
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "allowlisted"):
            receipt.validate_receipt(path, evidence_commit=prospective)
        document["evidence_commit"]["path"] = receipt.EVIDENCE_RECEIPT_PATH
        document["evidence_commit"]["bytes_sha256"] = "f" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "digest"):
            receipt.validate_receipt(path, evidence_commit=prospective)

    def test_atomic_write_preserves_mode_rejects_symlink_and_cas_failure_rolls_back(self) -> None:
        workspace, path, document = self.make_fixture()
        os.chmod(path, 0o640)
        receipt.write_atomic(path, b"replacement")
        self.assertEqual(path.read_bytes(), b"replacement")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        target = workspace / "target"
        target.write_bytes(b"target")
        link = workspace / "link"
        link.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            receipt.write_atomic(link, b"nope")
        linked_parent = workspace / "linked-parent"
        linked_parent.symlink_to(workspace / "real-parent", target_is_directory=True)
        (workspace / "real-parent").mkdir()
        with self.assertRaisesRegex(RuntimeError, "symlink|canonical"):
            receipt.write_atomic(linked_parent / "receipt.json", b"nope")
        path.write_bytes(receipt.canonical_json_bytes(document))
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "stale"):
            receipt.transition_receipt(
                path,
                repository=document["repositories"][1]["name"],
                from_state="discovered",
                to_state="prepared",
                expected_head="2" * 40,
                expected_signing_sha256=document["repositories"][1]["signing_sha256"],
            )
        self.assertEqual(path.read_bytes(), before)

    def test_central_transition_updates_both_central_representations(self) -> None:
        workspace, path, document = self.make_fixture()
        central = document["repositories"][0]
        updated = receipt.transition_receipt(
            path,
            repository=receipt.CENTRAL_NAME,
            from_state="discovered",
            to_state="prepared",
            expected_head=central["candidate_head"],
            expected_signing_sha256=central["signing_sha256"],
        )
        self.assertEqual(updated["central"]["state"], "prepared")
        self.assertEqual(updated["repositories"][0]["state"], "prepared")
        self.assertEqual(updated["current_state"], "prepared")

    def test_last_adopted_transition_derives_prospective_evidence_metadata(self) -> None:
        workspace, path, document = self.make_fixture()
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["repositories"][0]["state"] = "validated"
        document["central"]["state"] = "validated"
        document["current_state"] = "validated"
        path.write_bytes(receipt.canonical_json_bytes(document))
        central_root = Path(document["repositories"][0]["candidate_worktree"])
        content = b"prospective adopted receipt\n"
        prospective = self.make_prospective_commit(
            central_root, document["central"]["candidate_head"], content
        )
        updated = receipt.transition_receipt(
            path,
            repository=receipt.CENTRAL_NAME,
            from_state="validated",
            to_state="adopted",
            expected_head=document["central"]["candidate_head"],
            expected_signing_sha256=document["repositories"][0]["signing_sha256"],
            evidence_commit=prospective,
        )
        self.assertEqual(updated["current_state"], "adopted")
        self.assertEqual(updated["evidence_commit"]["parent"], document["central"]["candidate_head"])
        self.assertEqual(updated["evidence_commit"]["path"], receipt.EVIDENCE_RECEIPT_PATH)
        self.assertEqual(
            updated["evidence_commit"]["bytes_sha256"],
            hashlib.sha256(content).hexdigest(),
        )

    def test_repository_ref_manifest_has_exact_signing_envelope(self) -> None:
        manifest_path = SCRIPT_PATH.parents[1] / "config/publishing-signing-repository-refs.json"
        manifest = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema-version"], 1)
        source_path = SCRIPT_PATH.parents[1] / manifest["canonical-source"]["path"]
        self.assertEqual(manifest["canonical-source"]["status"], "prepared")
        self.assertEqual(
            manifest["canonical-source"]["sha256"],
            hashlib.sha256(source_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(set(manifest["repositories"]), set(receipt.SIGNING_NAMES))
        self.assertNotIn("bluetape4k-experimental", manifest["repositories"])
        self.assertNotIn("timefold-workshop", manifest["repositories"])
        self.assertNotIn("clinic-appointment", manifest["repositories"])

    def test_signing_digests_are_bound_to_canonical_source(self) -> None:
        _workspace, path, document = self.make_fixture()
        document["repositories"][0]["signing_sha256"] = "f" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "signing digest mismatch"):
            receipt.validate_receipt(path)

        _workspace, path, document = self.make_fixture()
        document["consumers"][0]["signing_sha256"] = "f" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "signing digest mismatch"):
            receipt.validate_receipt(path)

    def test_passing_candidate_graph_phase_requires_exact_consumer_ledger(self) -> None:
        _workspace, path, document = self.make_fixture()
        document["phases"].append(
            {
                "name": "timefold-graphs-candidate",
                "result": "pass",
                "output_sha256": "e" * 64,
            }
        )
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "graph coordinates"):
            receipt.validate_receipt(path)

    def test_validation_budget_rejects_inconsistent_remaining_time(self) -> None:
        _workspace, path, document = self.make_fixture()
        document["validation_budget"]["remaining_seconds"] = 5400.0
        document["validation_budget"]["elapsed_seconds"] = 1.0
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "validation budget"):
            receipt.validate_receipt(path)

    def test_cli_exposes_validate_and_transition_modes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("validate", result.stdout)
        self.assertIn("transition", result.stdout)
        workspace, path, document = self.make_fixture()
        default = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate", str(path)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(default.returncode, 0)
        allowed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "validate",
                str(path),
                "--allow-discovered",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)


if __name__ == "__main__":
    unittest.main()
