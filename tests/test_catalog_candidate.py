from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "catalog_candidate.py"
SPEC = importlib.util.spec_from_file_location("catalog_candidate", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
candidate = importlib.util.module_from_spec(SPEC)
sys.modules["catalog_candidate"] = candidate
SPEC.loader.exec_module(candidate)


class CatalogCandidateTest(unittest.TestCase):
    def test_git_failure_preserves_only_redacted_diagnostics(self) -> None:
        cases = (
            (
                "fatal: https://x-access-token:url-secret@github.com/example/repo.git",
                "url-secret",
            ),
            ("fatal: Authorization: Bearer bearer-secret", "bearer-secret"),
            ("fatal: authorization=Basic basic-secret", "basic-secret"),
            ("fatal: token=token-secret", "token-secret"),
            ("fatal: password: password-secret", "password-secret"),
            (
                "warning: retrying\nfatal: Authorization: Bearer multiline-secret",
                "multiline-secret",
            ),
        )
        for stderr, secret in cases:
            with self.subTest(stderr=stderr):
                failure = subprocess.CalledProcessError(
                    128,
                    ["git", "rev-parse", "missing"],
                    stderr=stderr,
                )
                with mock.patch.object(
                    candidate.subprocess, "run", side_effect=failure
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, r"git rev-parse failed.*<redacted>"
                    ) as raised:
                        candidate._git(Path("/tmp/example"), "rev-parse", "missing")

                self.assertNotIn(secret, str(raised.exception))

    def make_repository(self, workspace: Path, key: str) -> tuple[Path, str, str]:
        name = candidate.REPOSITORY_NAMES[key]
        root = workspace / name
        catalog = root / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\ndemo = "1.0.0"\n', encoding="utf-8")
        subprocess.run(
            ["git", "init", "-b", "candidate", str(root)],
            check=True,
            capture_output=True,
        )
        origin = f"git@github.com:bluetape4k/{name}.git"
        subprocess.run(
            ["git", "-C", str(root), "remote", "add", "origin", origin], check=True
        )
        subprocess.run(
            ["git", "-C", str(root), "add", "gradle/libs.versions.toml"], check=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-m",
                "fixture",
            ],
            check=True,
            capture_output=True,
        )
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "update-ref",
                "refs/remotes/origin/develop",
                head,
            ],
            check=True,
        )
        return root, origin, head

    def make_map(self, workspace: Path) -> tuple[Path, dict[str, object]]:
        entries: dict[str, dict[str, object]] = {}
        for key in ("central", *candidate.REPOSITORY_KEYS):
            root, origin, head = self.make_repository(workspace, key)
            entries[key] = {
                "root": str(root),
                "catalog": str(root / "gradle" / "libs.versions.toml"),
                "origin": origin,
                "branch": "candidate",
                "base_sha": head,
                "expected_head": head,
                "clean": True,
            }
        document = {
            "schema_version": 1,
            "central": entries.pop("central"),
            "repositories": {key: entries[key] for key in candidate.REPOSITORY_KEYS},
        }
        path = workspace / "repository-map.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path, document

    def test_load_repository_map_v1_returns_canonical_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            path, _ = self.make_map(workspace)
            loaded = candidate.load_repository_map_v1(path, workspace)
        self.assertEqual(
            tuple(item.key for item in loaded), ("central", *candidate.REPOSITORY_KEYS)
        )

    def test_legacy_flat_map_and_unknown_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            path, document = self.make_map(workspace)
            path.write_text(json.dumps(document["repositories"]), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "schema|fields"):
                candidate.load_repository_map_v1(path, workspace)
            document["unexpected"] = True
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "fields"):
                candidate.load_repository_map_v1(path, workspace)

            with self.assertRaisesRegex(RuntimeError, "absolute"):
                candidate.load_repository_map_v1(Path("relative.json"), workspace)

    def test_traversal_dirty_and_symlink_inputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            path, document = self.make_map(workspace)
            document["repositories"]["projects"]["catalog"] = str(
                workspace / ".." / "outside.toml"
            )
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "workspace|catalog|canonical"):
                candidate.load_repository_map_v1(path, workspace)

            path, document = self.make_map(workspace / "fresh")
            projects = Path(document["repositories"]["projects"]["root"])
            (projects / "dirty.txt").write_text("dirty", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "clean"):
                candidate.load_repository_map_v1(path, workspace / "fresh")

            link = workspace / "map-link.json"
            link.symlink_to(path)
            with self.assertRaisesRegex(RuntimeError, "symlink|canonical"):
                candidate.load_repository_map_v1(link, workspace / "fresh")

    def test_catalog_lock_binds_raw_catalog_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            path, _ = self.make_map(workspace)
            repositories = candidate.load_repository_map_v1(path, workspace)
            lock = candidate.create_catalog_lock(repositories)
            for item in repositories:
                self.assertEqual(
                    lock["catalogs"][item.key]["sha256"],
                    hashlib.sha256(item.catalog.read_bytes()).hexdigest(),
                )

    def test_base_sha_must_be_the_origin_develop_fork_point(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            path, document = self.make_map(workspace)
            projects = Path(document["repositories"]["projects"]["root"])
            stale_base = str(document["repositories"]["projects"]["base_sha"])
            (projects / "gradle/libs.versions.toml").write_text(
                '[versions]\ndemo = "2.0.0"\n', encoding="utf-8"
            )
            subprocess.run(
                ["git", "-C", str(projects), "add", "gradle/libs.versions.toml"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(projects),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "advance",
                ],
                check=True,
                capture_output=True,
            )
            advanced = subprocess.check_output(
                ["git", "-C", str(projects), "rev-parse", "HEAD"], text=True
            ).strip()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(projects),
                    "update-ref",
                    "refs/remotes/origin/develop",
                    advanced,
                ],
                check=True,
            )
            document["repositories"]["projects"]["expected_head"] = advanced
            document["repositories"]["projects"]["base_sha"] = stale_base
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "fork point"):
                candidate.load_repository_map_v1(path, workspace)

    def test_map_producer_round_trips_a_diverged_exact_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            path, document = self.make_map(workspace)
            projects = Path(document["repositories"]["projects"]["root"])
            fork_point = str(document["repositories"]["projects"]["base_sha"])

            subprocess.run(
                ["git", "-C", str(projects), "checkout", "-b", "develop"],
                check=True,
                capture_output=True,
            )
            (projects / "develop.txt").write_text("develop\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(projects), "add", "develop.txt"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(projects),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "advance develop",
                ],
                check=True,
                capture_output=True,
            )
            develop_head = subprocess.check_output(
                ["git", "-C", str(projects), "rev-parse", "HEAD"], text=True
            ).strip()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(projects),
                    "update-ref",
                    "refs/remotes/origin/develop",
                    develop_head,
                ],
                check=True,
            )

            subprocess.run(
                ["git", "-C", str(projects), "checkout", "candidate"],
                check=True,
                capture_output=True,
            )
            (projects / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(projects), "add", "candidate.txt"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(projects),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "advance candidate",
                ],
                check=True,
                capture_output=True,
            )
            candidate_head = subprocess.check_output(
                ["git", "-C", str(projects), "rev-parse", "HEAD"], text=True
            ).strip()

            document["repositories"]["projects"] = (
                candidate.inspect_repository_for_map(
                    "bluetape4k-projects", projects, candidate_head
                )
            )
            path.write_text(json.dumps(document), encoding="utf-8")
            loaded = candidate.load_repository_map_v1(path, workspace)

            projects_entry = next(item for item in loaded if item.key == "projects")
            self.assertEqual(projects_entry.base_sha, fork_point)
            self.assertEqual(projects_entry.expected_head, candidate_head)

    def test_map_producer_accepts_single_branch_candidate_after_develop_fetch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            source, _, fork_point = self.make_repository(workspace, "projects")
            subprocess.run(
                ["git", "-C", str(source), "checkout", "-b", "develop"],
                check=True,
                capture_output=True,
            )
            (source / "develop.txt").write_text("develop\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(source), "add", "develop.txt"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "advance develop",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(source), "checkout", "candidate"],
                check=True,
                capture_output=True,
            )
            (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(source), "add", "candidate.txt"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "advance candidate",
                ],
                check=True,
                capture_output=True,
            )
            candidate_head = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()

            bare = workspace / "projects-remote.git"
            clone = workspace / "single-branch-projects"
            subprocess.run(
                ["git", "clone", "--bare", str(source), str(bare)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--branch",
                    "candidate",
                    "--single-branch",
                    f"file://{bare}",
                    str(clone),
                ],
                check=True,
                capture_output=True,
            )
            missing_develop = subprocess.run(
                ["git", "-C", str(clone), "rev-parse", "origin/develop"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing_develop.returncode, 0)

            subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone),
                    "fetch",
                    "--no-tags",
                    "--filter=blob:none",
                    "origin",
                    "develop:refs/remotes/origin/develop",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone),
                    "remote",
                    "set-url",
                    "origin",
                    "git@github.com:bluetape4k/bluetape4k-projects.git",
                ],
                check=True,
            )

            entry = candidate.inspect_repository_for_map(
                "bluetape4k-projects", clone, candidate_head
            )
            self.assertEqual(entry["base_sha"], fork_point)

    def test_manifest_verify_revalidates_every_bound_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            repository_map, _ = self.make_map(workspace)
            repositories = candidate.load_repository_map_v1(repository_map, workspace)
            disposition = workspace / "disposition.json"
            cache = workspace / "cache.json"
            human_ledger = workspace / "ledger.md"
            disposition.write_text("{}\n", encoding="utf-8")
            cache.write_text("{}\n", encoding="utf-8")
            human_ledger.write_text("# ledger\n", encoding="utf-8")
            machine_ledger_path = workspace / "machine-ledger.json"
            genesis = candidate.append_ledger_record(
                machine_ledger_path,
                {"stage": "prepare-inputs"},
                fencing_token="test-fence",
            )
            manifest = candidate.create_candidate_manifest(
                repository_map,
                workspace,
                repositories,
                disposition,
                cache,
                human_ledger,
                {
                    "path": str(machine_ledger_path),
                    "fencing_token": "test-fence",
                    "genesis_record_sha256": candidate.record_sha256(genesis),
                },
            )
            manifest_path = workspace / "manifest.json"
            candidate.write_atomic(
                manifest_path, candidate.canonical_json_bytes(manifest)
            )
            self.assertEqual(
                candidate.verify_candidate_manifest(manifest_path), manifest
            )
            cache.write_text('{"changed":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "cache manifest SHA-256 mismatch"
            ):
                candidate.verify_candidate_manifest(manifest_path)

    def test_manifest_verify_rejects_schema_only_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text('{"schema_version":1}\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "fields"):
                candidate.verify_candidate_manifest(manifest)

    def test_atomic_writer_and_ledger_chain_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "atomic.json"
            payload = candidate.canonical_json_bytes({"ok": True})
            candidate.write_atomic(output, payload)
            self.assertEqual(output.read_bytes(), payload)

            ledger = root / "ledger.json"
            first = candidate.append_ledger_record(
                ledger, {"stage": "prepare"}, fencing_token="one"
            )
            second = candidate.append_ledger_record(
                ledger, {"stage": "verify"}, fencing_token="one"
            )
            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(
                second["prior_record_sha256"], candidate.record_sha256(first)
            )
            with self.assertRaisesRegex(RuntimeError, "fencing"):
                candidate.append_ledger_record(
                    ledger, {"stage": "bad"}, fencing_token="two"
                )

            corrupted = json.loads(ledger.read_bytes())
            corrupted["records"][1]["prior_record_sha256"] = "0" * 64
            ledger.write_bytes(candidate.canonical_json_bytes(corrupted))
            with self.assertRaisesRegex(RuntimeError, "invalid ledger chain"):
                candidate.append_ledger_record(
                    ledger, {"stage": "bad"}, fencing_token="one"
                )

    def test_genesis_initialization_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            payload = {"stage": "prepare-inputs"}
            first = candidate.initialize_ledger_genesis(
                ledger, payload, fencing_token="same"
            )
            second = candidate.initialize_ledger_genesis(
                ledger, payload, fencing_token="same"
            )
            self.assertEqual(first, second)
            self.assertEqual(len(json.loads(ledger.read_bytes())["records"]), 1)
            with self.assertRaisesRegex(RuntimeError, "genesis input mismatch"):
                candidate.initialize_ledger_genesis(
                    ledger, {"stage": "different"}, fencing_token="same"
                )

    def test_concurrent_genesis_initialization_creates_one_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            payload = {"stage": "prepare-inputs"}
            with ThreadPoolExecutor(max_workers=2) as executor:
                records = list(
                    executor.map(
                        lambda _: candidate.initialize_ledger_genesis(
                            ledger, payload, fencing_token="same"
                        ),
                        range(2),
                    )
                )
            self.assertEqual(records[0], records[1])
            self.assertEqual(len(json.loads(ledger.read_bytes())["records"]), 1)


if __name__ == "__main__":
    unittest.main()
