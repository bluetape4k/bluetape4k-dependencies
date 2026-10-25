from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit-latest-stable.py"
LEDGER = REPO_ROOT / "config" / "central-catalog-version-deltas.json"
AUTHORITY_LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"
TIMEFOLD_ROLLOUT = "2026-09-09-issue-242-timefold-2.6.0"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_latest_stable", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit-latest-stable.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CentralCatalogVersionDeltaLedgerTest(unittest.TestCase):
    def test_transaction_recovers_after_process_crash_moving_replacement_guard(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
original_move = evidence._rename_no_replace_at

def crash_after_guard(source_parent, source, destination_parent, destination, **kwargs):
    if (
        source == target.name
        and str(destination).startswith(f".{{target.name}}.")
        and str(destination).endswith(".replace")
    ):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(17)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_guard
evidence.commit_catalog_rollout_transaction(root, ((target, b"new-content"),))
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 17, result.stderr)
            self.assertFalse(target.exists())
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())
            self.assertEqual(
                len(list(target.parent.glob(f".{target.name}.*.replace"))), 1
            )
            self.assertEqual(
                len(list(target.parent.glob(f".{target.name}.*.tmp"))), 1
            )

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(evidence.catalog_rollout_transaction_path(root).exists())
            self.assertEqual(
                list(target.parent.glob(f".{target.name}.*.replace")), []
            )
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_transaction_recovers_after_process_crash_moving_journal_tombstone(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            journal = evidence.catalog_rollout_transaction_path(root)
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
journal_name = evidence.catalog_rollout_transaction_path(root).name
original_move = evidence._rename_no_replace_at

def crash_after_journal_move(source_parent, source, destination_parent, destination, **kwargs):
    if source == journal_name and str(destination).endswith(".rollback"):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(19)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_journal_move
evidence.commit_catalog_rollout_transaction(
    root, ((root / "config" / "generated.json", b"new-content"),)
)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 19, result.stderr)
            self.assertFalse(journal.exists())
            self.assertEqual(
                len(list(journal.parent.glob(f".{journal.name}.*.rollback"))), 1
            )
            self.assertEqual(target.read_bytes(), b"new-content")

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(journal.exists())
            self.assertEqual(list(journal.parent.glob(f".{journal.name}.*.rollback")), [])

    def test_transaction_recovers_after_process_crash_after_target_publish(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
original_fsync = evidence._fsync_directory_fd
finalization = evidence.catalog_rollout_transaction_finalization_path(root)

def crash_after_publish(descriptor):
    result = original_fsync(descriptor)
    if (
        target.exists()
        and target.read_bytes() == b"new-content"
        and finalization.is_file()
    ):
        os._exit(23)
    return result

evidence._fsync_directory_fd = crash_after_publish
evidence.commit_catalog_rollout_transaction(root, ((target, b"new-content"),))
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 23, result.stderr)
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())
            self.assertTrue(
                evidence.catalog_rollout_transaction_finalization_path(root).is_file()
            )

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(evidence.catalog_rollout_transaction_path(root).exists())
            self.assertEqual(
                list(target.parent.glob(f".{target.name}.*.replace")), []
            )
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_transaction_recovers_after_process_crash_before_publish_identity_persist(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
original_write = evidence.atomic_write_bytes

def crash_after_target_write(path, content, **kwargs):
    result = original_write(path, content, **kwargs)
    if kwargs.get("target_name") == target.name:
        os._exit(71)
    return result

evidence.atomic_write_bytes = crash_after_target_write
evidence.commit_catalog_rollout_transaction(root, ((target, b"new-content"),))
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 71, result.stderr)
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(evidence.catalog_rollout_transaction_path(root).exists())

    def test_finalization_recovery_rejects_same_bytes_new_inode(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
original_fsync = evidence._fsync_directory_fd
finalization = evidence.catalog_rollout_transaction_finalization_path(root)

def crash_after_finalization(descriptor):
    result = original_fsync(descriptor)
    if target.exists() and target.read_bytes() == b"new-content" and finalization.is_file():
        os._exit(53)
    return result

evidence._fsync_directory_fd = crash_after_finalization
evidence.commit_catalog_rollout_transaction(root, ((target, b"new-content"),))
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 53, result.stderr)
            replacement = target.with_name("replacement.json")
            replacement.write_bytes(b"new-content")
            os.replace(replacement, target)

            with self.assertRaisesRegex(RuntimeError, "inode changed externally"):
                evidence.recover_catalog_rollout_transaction(root)
            self.assertTrue(
                evidence.catalog_rollout_transaction_finalization_path(root).is_file()
            )

    def test_recovery_finishes_when_finalization_write_fails_after_publish(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            finalization_name = evidence.catalog_rollout_transaction_finalization_path(
                root
            ).name
            child = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
original_write = evidence.atomic_write_bytes

def fail_finalization(path, content, **kwargs):
    if kwargs.get("target_name") == {finalization_name!r}:
        raise OSError("injected finalization write failure")
    return original_write(path, content, **kwargs)

evidence.atomic_write_bytes = fail_finalization
evidence.commit_catalog_rollout_transaction(root, ((target, b"new-content"),))
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn("injected finalization write failure", result.stderr)
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())
            self.assertTrue(
                evidence.catalog_rollout_transaction_identity_path(root).is_file()
            )
            self.assertFalse(
                evidence.catalog_rollout_transaction_finalization_path(root).exists()
            )

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(evidence.catalog_rollout_transaction_path(root).exists())
            self.assertFalse(
                evidence.catalog_rollout_transaction_identity_path(root).exists()
            )

    def test_recovery_rejects_missing_journal_with_identity_evidence(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            identity = evidence.catalog_rollout_transaction_identity_path(root)
            identity.parent.mkdir(parents=True)
            identity.write_bytes(
                evidence.pretty_json(
                    {
                        "journal-sha256": "0" * 64,
                        "schema-version": evidence.TRANSACTION_IDENTITY_SCHEMA_VERSION,
                        "transaction-id": "a" * 32,
                    }
                )
            )

            with self.assertRaisesRegex(
                RuntimeError, "journal is missing while identity evidence remains"
            ):
                evidence.recover_catalog_rollout_transaction(root)
            self.assertTrue(identity.is_file())

    def test_tombstone_cleanup_preserves_external_replacement(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            tombstone = parent / ".owned.rollback"
            tombstone.write_bytes(b"owned-content")
            external = b"external-content"
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor = os.open(
                "config", evidence._DIRECTORY_OPEN_FLAGS, dir_fd=root_descriptor
            )
            descriptor = os.open(
                tombstone.name, evidence._TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
            )
            identity = evidence._descriptor_identity(descriptor)
            os.close(descriptor)
            original_move = evidence._rename_no_replace_at

            def insert_external_after_move(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                result = original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )
                if source == tombstone.name and str(destination).endswith(".rollback"):
                    tombstone.write_bytes(external)
                return result

            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=insert_external_after_move,
                ), self.assertRaisesRegex(RuntimeError, "tombstone"):
                    evidence._discard_expected_tombstone_at(
                        parent_descriptor,
                        tombstone.name,
                        identity,
                        b"owned-content",
                        stat.S_IMODE(tombstone.stat().st_mode),
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertEqual(tombstone.read_bytes(), external)
            self.assertEqual(
                len(list(parent.glob(f"{tombstone.name}.*.rollback"))), 1
            )

    def test_rollout_state_transaction_recovers_after_second_replace_fails(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ledger_path = root / "config" / "latest-stable-version-deltas.json"
            central_path = root / "config" / "central-catalog-version-deltas.json"
            ledger_path.parent.mkdir(parents=True)
            audit_bytes = b'{"schema-version":1}\n'
            authority = {
                "rollout": "candidate",
                "status": "validation-pending",
                "baseline": {"catalog-ref": "baseline"},
                "candidate": {"catalog-sha256": "a" * 64},
                "audit": {
                    "path": "config/latest-stable-version-audit.json",
                    "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                },
                "delta": [],
            }
            audit_path = root / "config" / "latest-stable-version-audit.json"
            audit_path.write_bytes(audit_bytes)
            artifacts = evidence.snapshot_rollout_evidence(
                authority, audit_bytes, root
            )
            central = evidence.upsert_catalog_rollout(
                {"schema-version": 2, "subsequent-rollouts": []},
                authority,
                artifacts,
            )
            ledger_bytes = evidence.pretty_json(authority)
            central_bytes = evidence.pretty_json(central)
            ledger_path.write_bytes(b'{"state":"previous-authority"}\n')
            central_path.write_bytes(b'{"state":"previous-central"}\n')
            original_atomic_write = evidence.atomic_write_bytes

            def fail_central_replace(path, content, **kwargs) -> None:
                if path.name == central_path.name and path.parent.resolve() == central_path.parent.resolve():
                    raise OSError("injected central ledger replace failure")
                original_atomic_write(path, content, **kwargs)

            with mock.patch.object(
                evidence, "atomic_write_bytes", side_effect=fail_central_replace
            ), self.assertRaisesRegex(OSError, "injected central ledger"):
                evidence.commit_catalog_rollout_transaction(
                    root,
                    (
                        (ledger_path, ledger_bytes),
                        (central_path, central_bytes),
                    ),
                )

            transaction_path = evidence.catalog_rollout_transaction_path(root)
            self.assertTrue(transaction_path.is_file())
            self.assertEqual(
                ledger_path.read_bytes(), b'{"state":"previous-authority"}\n'
            )
            self.assertEqual(
                central_path.read_bytes(), b'{"state":"previous-central"}\n'
            )

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(ledger_path.read_bytes(), ledger_bytes)
            self.assertEqual(central_path.read_bytes(), central_bytes)
            self.assertFalse(transaction_path.exists())

    def test_transaction_recovery_preserves_external_conflict_across_retry(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first_path = root / "config" / "first.json"
            second_path = root / "config" / "second.json"
            first_path.parent.mkdir(parents=True)
            first_path.write_bytes(b"old-first")
            second_path.write_bytes(b"old-second")
            original_atomic_write = evidence.atomic_write_bytes

            def fail_after_external_change(path, content, **kwargs) -> None:
                if path.name == first_path.name and path.parent.resolve() == first_path.parent.resolve():
                    original_atomic_write(path, content, **kwargs)
                    first_path.write_bytes(b"external-change")
                    return
                if path.name == second_path.name and path.parent.resolve() == second_path.parent.resolve():
                    raise OSError("injected second replace failure")
                original_atomic_write(path, content, **kwargs)

            with mock.patch.object(
                evidence,
                "atomic_write_bytes",
                side_effect=fail_after_external_change,
            ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                evidence.commit_catalog_rollout_transaction(
                    root,
                    ((first_path, b"new-first"), (second_path, b"new-second")),
                )

            journal_path = evidence.catalog_rollout_transaction_path(root)
            self.assertTrue(journal_path.is_file())
            self.assertEqual(first_path.read_bytes(), b"external-change")
            self.assertEqual(second_path.read_bytes(), b"old-second")

            with self.assertRaisesRegex(RuntimeError, "target changed externally"):
                evidence.recover_catalog_rollout_transaction(root)
            self.assertTrue(journal_path.is_file())
            self.assertEqual(first_path.read_bytes(), b"external-change")
            self.assertEqual(second_path.read_bytes(), b"old-second")

    def test_transaction_detects_mutation_before_anchored_replace(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            first_path = root / "config" / "first.json"
            second_path = root / "config" / "second.json"
            first_path.parent.mkdir(parents=True)
            first_path.write_bytes(b"old-first")
            second_path.write_bytes(b"old-second")
            original_atomic_write = evidence.atomic_write_bytes
            mutated = False

            def mutate_before_replace(path, content, **kwargs):
                nonlocal mutated
                if path == second_path and not mutated:
                    mutated = True
                    second_path.write_bytes(b"external-before-replace")
                return original_atomic_write(path, content, **kwargs)

            with mock.patch.object(
                evidence, "atomic_write_bytes", side_effect=mutate_before_replace
            ), self.assertRaisesRegex(RuntimeError, "target changed externally"):
                evidence.commit_catalog_rollout_transaction(
                    root,
                    ((first_path, b"new-first"), (second_path, b"new-second")),
                )

            journal_path = evidence.catalog_rollout_transaction_path(root)
            self.assertTrue(journal_path.is_file())
            self.assertEqual(first_path.read_bytes(), b"old-first")
            self.assertEqual(second_path.read_bytes(), b"external-before-replace")

    def test_transaction_rejects_target_path_swap_before_guard_replace(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            original_move = evidence._rename_no_replace_at
            swapped = False

            def swap_before_guard(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal swapped
                is_guard = (
                    source == target.name
                    and str(destination).startswith(f".{target.name}.")
                    and str(destination).endswith(".replace")
                )
                if is_guard and not swapped:
                    swapped = True
                    target.rename(target.with_name("original-target.json"))
                    target.write_bytes(b"external-path")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            with mock.patch.object(
                evidence, "_rename_no_replace_at", side_effect=swap_before_guard
            ), self.assertRaisesRegex(RuntimeError, "target changed externally"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertTrue(swapped)
            self.assertEqual(target.read_bytes(), b"external-path")
            self.assertEqual(
                (target.parent / "original-target.json").read_bytes(), b"old-content"
            )
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_generated_guard_destination_never_replaces_external_inode(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, target
            )
            original_move = evidence._rename_no_replace_at
            injected: Path | None = None

            def inject_guard_destination(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                if source == target_name and str(destination).endswith(".replace"):
                    injected = target.parent / str(destination)
                    injected.write_bytes(b"external-guard")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=inject_guard_destination,
                ), self.assertRaises(FileExistsError):
                    evidence._atomic_write_bytes_at(
                        parent_descriptor,
                        target_name,
                        b"new-content",
                        mode=0o644,
                        expected_state=(True, b"old-content", 0o644),
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertIsNotNone(injected)
            self.assertEqual(injected.read_bytes(), b"external-guard")
            self.assertEqual(target.read_bytes(), b"old-content")

    def test_native_source_swap_is_restored_without_publishing_external_inode(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            source = parent / "source.json"
            destination = parent / "destination.json"
            source.write_bytes(b"owned-source")
            source_identity = (source.stat().st_dev, source.stat().st_ino)
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, _ = evidence._open_anchored_parent(
                root_descriptor, root, source
            )
            original_native = evidence._native_rename_no_replace
            injected = False

            def swap_before_native(
                source_name, destination_name, source_parent, destination_parent
            ):
                nonlocal injected
                if not injected:
                    injected = True
                    os.rename(
                        source,
                        parent / "owned-moved.json",
                    )
                    source.write_bytes(b"external-source")
                return original_native(
                    source_name, destination_name, source_parent, destination_parent
                )

            try:
                with mock.patch.object(
                    evidence,
                    "_native_rename_no_replace",
                    side_effect=swap_before_native,
                ), self.assertRaisesRegex(RuntimeError, "moved inode changed externally"):
                    evidence._rename_no_replace_at(
                        parent_descriptor,
                        source.name,
                        parent_descriptor,
                        destination.name,
                        expected_identity=source_identity,
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertTrue(injected)
            self.assertEqual(source.read_bytes(), b"external-source")
            self.assertEqual((parent / "owned-moved.json").read_bytes(), b"owned-source")
            self.assertFalse(destination.exists())

    def test_link_expected_entry_preserves_destination_when_source_is_replaced(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            source = parent / "source.json"
            destination = parent / "destination.json"
            owned_moved = parent / "owned-moved.json"
            source.write_bytes(b"owned-source")
            source_identity = (source.stat().st_dev, source.stat().st_ino)
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, _ = evidence._open_anchored_parent(
                root_descriptor, root, source
            )
            real_link = evidence.os.link
            injected = False

            def replace_source_before_link(src, dst, *args, **kwargs):
                nonlocal injected
                if not injected:
                    injected = True
                    source.rename(owned_moved)
                    source.write_bytes(b"external-source")
                return real_link(src, dst, *args, **kwargs)

            try:
                with mock.patch.object(
                    evidence.os, "link", side_effect=replace_source_before_link
                ), self.assertRaisesRegex(RuntimeError, "source changed externally"):
                    evidence._link_expected_entry_at(
                        parent_descriptor,
                        source.name,
                        parent_descriptor,
                        destination.name,
                        expected_identity=source_identity,
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertTrue(injected)
            self.assertFalse(destination.exists())
            self.assertEqual(source.read_bytes(), b"external-source")
            self.assertEqual(owned_moved.read_bytes(), b"owned-source")

    def test_no_native_no_replace_path_fails_closed_without_unlinking_source(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            source = parent / "source.json"
            destination = parent / "destination.json"
            source.write_bytes(b"owned-source")
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, _ = evidence._open_anchored_parent(
                root_descriptor, root, source
            )
            try:
                with mock.patch.object(
                    evidence, "_native_rename_no_replace", return_value=False
                ), self.assertRaisesRegex(RuntimeError, "safe no-replace rename"):
                    evidence._rename_no_replace_at(
                        parent_descriptor,
                        source.name,
                        parent_descriptor,
                        destination.name,
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)
            self.assertEqual(source.read_bytes(), b"owned-source")
            self.assertFalse(destination.exists())

    def test_generated_rollback_destination_never_replaces_external_inode(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, target
            )
            original_move = evidence._rename_no_replace_at
            injected: Path | None = None

            def inject_rollback_destination(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                if source == target_name and str(destination).endswith(".rollback"):
                    injected = target.parent / str(destination)
                    injected.write_bytes(b"external-rollback")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=inject_rollback_destination,
                ), self.assertRaises(FileExistsError):
                    evidence._remove_expected_target_at(
                        parent_descriptor, target_name, b"new-content", 0o644
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertIsNotNone(injected)
            self.assertEqual(injected.read_bytes(), b"external-rollback")
            self.assertEqual(target.read_bytes(), b"new-content")

    def test_expected_entry_unlink_preserves_replacement_at_private_delete_name(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            entry = parent / ".owned.123.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.rollback"
            entry.write_bytes(b"owned")
            owned_moved = parent / "owned-moved"
            original_move = evidence._rename_no_replace_at
            injected = False

            def swap_before_private_unlink(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                if source.endswith(".delete") and not injected:
                    injected = True
                    os.rename(entry.with_name(source), owned_moved)
                    entry.with_name(source).write_bytes(b"external-replacement")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            descriptor = os.open(parent, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=swap_before_private_unlink,
                ), self.assertRaisesRegex(RuntimeError, "source changed externally"):
                    evidence._unlink_expected_entry_at(
                        descriptor,
                        entry.name,
                        (entry.stat().st_dev, entry.stat().st_ino),
                        b"owned",
                        0o644,
                    )
            finally:
                os.close(descriptor)

            self.assertTrue(injected)
            self.assertEqual(owned_moved.read_bytes(), b"owned")
            self.assertEqual(
                entry.with_name(f"{entry.name}.delete").read_bytes(),
                b"external-replacement",
            )

    def test_expected_entry_unlink_preserves_replacement_before_final_unlink(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            entry = parent / ".owned.123.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.rollback"
            entry.write_bytes(b"owned")
            original_unlink = evidence.os.unlink
            unlink_names: list[str] = []

            def replace_final_before_unlink(name, *args, **kwargs):
                unlink_names.append(str(name))
                return original_unlink(name, *args, **kwargs)

            descriptor = os.open(parent, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                with mock.patch.object(
                    evidence.os, "unlink", side_effect=replace_final_before_unlink
                ):
                    evidence._unlink_expected_entry_at(
                        descriptor,
                        entry.name,
                        (entry.stat().st_dev, entry.stat().st_ino),
                        b"owned",
                        0o644,
                    )
            finally:
                os.close(descriptor)

            self.assertTrue(unlink_names)
            self.assertTrue(all(not name.endswith(".rollback") for name in unlink_names))
            self.assertFalse(entry.exists())

    def test_remove_expected_directory_preserves_replacement_before_rmdir(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            parent = root / "config"
            parent.mkdir(parents=True)
            directory = parent / "empty"
            directory.mkdir()
            directory_identity = (directory.stat().st_dev, directory.stat().st_ino)
            owned_moved = parent / "owned-directory-moved"
            original_rmdir = evidence.os.rmdir
            injected = False

            def replace_before_rmdir(name, *args, **kwargs):
                nonlocal injected
                if not injected and str(name).endswith(".delete"):
                    cleanup = parent / str(name)
                    if cleanup.is_dir():
                        injected = True
                        cleanup.rename(owned_moved)
                        cleanup.mkdir()
                return original_rmdir(name, *args, **kwargs)

            descriptor = os.open(parent, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                with mock.patch.object(
                    evidence.os, "rmdir", side_effect=replace_before_rmdir
                ):
                    evidence._remove_expected_directory_at(
                        descriptor, directory.name, directory_identity
                    )
            finally:
                os.close(descriptor)

            self.assertFalse(injected)
            self.assertFalse(directory.exists())
            self.assertFalse(owned_moved.exists())

    def test_transaction_rolls_back_after_post_replace_fsync_failure(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            first_path = root / "config" / "first.json"
            second_path = root / "config" / "second.json"
            first_path.parent.mkdir(parents=True)
            first_path.write_bytes(b"old-first")
            second_path.write_bytes(b"old-second")
            original_fsync = evidence._fsync_directory_fd
            fsync_count = 0

            def fail_first_target_fsync(descriptor):
                nonlocal fsync_count
                fsync_count += 1
                if fsync_count == 2:
                    raise OSError("injected target fsync failure")
                return original_fsync(descriptor)

            with mock.patch.object(
                evidence,
                "_fsync_directory_fd",
                side_effect=fail_first_target_fsync,
            ), self.assertRaisesRegex(OSError, "target fsync"):
                evidence.commit_catalog_rollout_transaction(
                    root,
                    ((first_path, b"new-first"), (second_path, b"new-second")),
                )

            self.assertEqual(first_path.read_bytes(), b"old-first")
            self.assertEqual(second_path.read_bytes(), b"old-second")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_transaction_detects_mutation_during_directory_fsync(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            original_fsync = evidence._fsync_directory_fd
            injected = False

            def mutate_during_fsync(descriptor):
                nonlocal injected
                result = original_fsync(descriptor)
                if not injected and target.read_bytes() == b"new-content":
                    injected = True
                    target.write_bytes(b"external-during-fsync")
                return result

            with mock.patch.object(
                evidence,
                "_fsync_directory_fd",
                side_effect=mutate_during_fsync,
            ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertTrue(injected)
            self.assertEqual(target.read_bytes(), b"external-during-fsync")
            self.assertTrue(
                evidence.catalog_rollout_transaction_path(root).is_file()
            )

    def test_transaction_detects_mutation_inside_replace_and_preserves_it(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            original_move = evidence._rename_no_replace_at
            injected = False

            def mutate_inside_replace(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                is_target = str(destination).startswith(f".{target.name}.") and (
                    source == target.name
                )
                if is_target and not injected:
                    injected = True
                    target.write_bytes(b"external-inside-replace")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            with mock.patch.object(
                evidence, "_rename_no_replace_at", side_effect=mutate_inside_replace
            ), self.assertRaisesRegex(RuntimeError, "target changed externally"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertEqual(target.read_bytes(), b"external-inside-replace")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_transaction_detects_mutation_after_replace_and_preserves_it(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            original_move = evidence._rename_no_replace_at
            injected = False

            def mutate_after_replace(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                is_target = str(destination).startswith(f".{target.name}.") and (
                    source == target.name
                )
                if is_target and not injected:
                    result = original_move(
                        source_parent, source, destination_parent, destination, **kwargs
                    )
                    injected = True
                    target.write_bytes(b"external-after-replace")
                    return result
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            with mock.patch.object(
                evidence, "_rename_no_replace_at", side_effect=mutate_after_replace
            ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertEqual(target.read_bytes(), b"external-after-replace")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_transaction_detects_mutation_after_publish_and_preserves_it(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            original_move = evidence._rename_no_replace_at
            injected = False

            def mutate_after_publish(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                result = original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )
                is_target = destination == target.name and source.endswith(".tmp")
                if is_target and not injected:
                    injected = True
                    target.write_bytes(b"external-after-publish")
                return result

            with mock.patch.object(
                evidence, "_rename_no_replace_at", side_effect=mutate_after_publish
            ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertEqual(target.read_bytes(), b"external-after-publish")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_transaction_detects_mutation_after_second_cross_file_validation(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            original_validate = evidence._validate_cross_file_rollout_evidence
            validation_count = 0

            def mutate_after_second_validation(repository_root, pending_writes=None):
                nonlocal validation_count
                result = original_validate(repository_root, pending_writes)
                validation_count += 1
                if validation_count == 2:
                    replacement = target.with_name("external-after-validation.json")
                    replacement.write_bytes(b"external-after-validation")
                    os.replace(replacement, target)
                return result

            with mock.patch.object(
                evidence,
                "_validate_cross_file_rollout_evidence",
                side_effect=mutate_after_second_validation,
            ), self.assertRaisesRegex(RuntimeError, "rollback conflict|target changed externally"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertEqual(target.read_bytes(), b"external-after-validation")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_transaction_rejects_a_final_symlink_target(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            config_path = root / "config"
            real_target = config_path / "real.json"
            link_target = config_path / "link.json"
            config_path.mkdir(parents=True)
            real_target.write_bytes(b"real-content")
            link_target.symlink_to(real_target.name)

            with self.assertRaisesRegex(RuntimeError, "must not contain symlinks"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((link_target, b"new-content"),)
                )

            self.assertEqual(real_target.read_bytes(), b"real-content")
            self.assertFalse(evidence.catalog_rollout_transaction_path(root).exists())

    def test_transaction_lock_rejects_a_symlinked_state_directory(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory).resolve()
            outside = Path(outside_directory).resolve()
            config_path = root / "config"
            config_path.mkdir(parents=True)
            target = config_path / "target.json"
            target.write_bytes(b"old-content")
            (root / ".bluetape").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(RuntimeError, "lock path"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertFalse((outside / "catalog-rollout-transaction.lock").exists())

    def test_transaction_rejects_repository_root_replacement_after_lock(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "target.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            original_flock = evidence.fcntl.flock
            swapped = False

            def swap_root_after_lock(descriptor, operation):
                nonlocal swapped
                result = original_flock(descriptor, operation)
                if operation == evidence.fcntl.LOCK_EX and not swapped:
                    swapped = True
                    original_root = root.with_name(f"{root.name}.original")
                    root.rename(original_root)
                    replacement_config = root / "config"
                    replacement_config.mkdir(parents=True)
                    (replacement_config / "target.json").write_bytes(b"replacement-old")
                return result

            with mock.patch.object(
                evidence.fcntl, "flock", side_effect=swap_root_after_lock
            ), self.assertRaisesRegex(RuntimeError, "repository root changed externally"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((root / "config" / "target.json", b"new-content"),)
                )

            self.assertTrue(swapped)
            self.assertEqual(
                (root.with_name(f"{root.name}.original") / "config" / "target.json").read_bytes(),
                b"old-content",
            )
            self.assertEqual(target.read_bytes(), b"replacement-old")
            self.assertFalse(evidence.catalog_rollout_transaction_path(root).exists())
            shutil.rmtree(root.with_name(f"{root.name}.original"))

    def test_transaction_rollback_removes_missing_target_with_anchored_parent(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, target
            )
            try:
                evidence._restore_transaction_target(
                    target,
                    False,
                    b"",
                    None,
                    b"new-content",
                    0o644,
                    parent_descriptor=parent_descriptor,
                    target_name=target_name,
                )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertFalse(target.exists())

    def test_transaction_rollback_preserves_a_target_inserted_before_remove(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")
            original_move = evidence._rename_no_replace_at
            injected = False

            def insert_external_before_remove(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                if (
                    not injected
                    and source == target.name
                    and str(destination).startswith(f".{target.name}.")
                ):
                    injected = True
                    moved = target.with_name("original-generated.json")
                    target.rename(moved)
                    target.write_bytes(b"external-inserted")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, target
            )
            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=insert_external_before_remove,
                ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                    evidence._restore_transaction_target(
                        target,
                        False,
                        b"",
                        None,
                        b"new-content",
                        0o644,
                        parent_descriptor=parent_descriptor,
                        target_name=target_name,
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertEqual(target.read_bytes(), b"external-inserted")
            self.assertEqual(
                (target.parent / "original-generated.json").read_bytes(), b"new-content"
            )

    def test_transaction_journal_removal_preserves_a_replacement(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            journal = evidence.catalog_rollout_transaction_path(root)
            journal.parent.mkdir(parents=True)
            journal.write_bytes(b"journal-content")
            original_move = evidence._rename_no_replace_at
            injected = False

            def replace_journal_before_remove(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                if (
                    not injected
                    and source == journal.name
                    and str(destination).startswith(f".{journal.name}.")
                ):
                    injected = True
                    moved = journal.with_name("original-journal.json")
                    journal.rename(moved)
                    journal.write_bytes(b"external-journal")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, journal
            )
            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=replace_journal_before_remove,
                ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                    evidence._remove_expected_target_at(
                        parent_descriptor,
                        target_name,
                        b"journal-content",
                        stat.S_IMODE(journal.stat().st_mode),
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertEqual(journal.read_bytes(), b"external-journal")
            self.assertEqual(
                (journal.parent / "original-journal.json").read_bytes(),
                b"journal-content",
            )

    def test_transaction_journal_removal_recreates_after_directory_fsync_failure(
        self,
    ) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            journal = evidence.catalog_rollout_transaction_path(root)
            journal.parent.mkdir(parents=True)
            journal.write_bytes(b"journal-content")
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, journal
            )
            try:
                with mock.patch.object(
                    evidence,
                    "_fsync_directory_fd",
                    side_effect=OSError("injected journal fsync failure"),
                ), self.assertRaisesRegex(OSError, "injected journal fsync failure"):
                    evidence._remove_expected_target_at(
                        parent_descriptor,
                        target_name,
                        b"journal-content",
                        stat.S_IMODE(journal.stat().st_mode),
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertEqual(journal.read_bytes(), b"journal-content")
            self.assertEqual(
                list(journal.parent.glob(f".{journal.name}.*.rollback")), []
            )

    def test_journal_cleanup_rejects_same_bytes_replacement_inode(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            journal = evidence.catalog_rollout_transaction_path(root)
            journal.parent.mkdir(parents=True)
            journal.write_bytes(b"journal-content")
            journal_mode = stat.S_IMODE(journal.stat().st_mode)
            original_identity = (journal.stat().st_dev, journal.stat().st_ino)
            original_remove = evidence._remove_expected_target_at
            replaced = False

            def replace_before_cleanup(parent_descriptor, target_name, *args, **kwargs):
                nonlocal replaced
                if target_name == journal.name and not replaced:
                    replaced = True
                    replacement = journal.with_name("external-journal.json")
                    replacement.write_bytes(b"journal-content")
                    os.replace(replacement, journal)
                return original_remove(parent_descriptor, target_name, *args, **kwargs)

            parent = os.open(journal.parent, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                with mock.patch.object(
                    evidence,
                    "_remove_expected_target_at",
                    side_effect=replace_before_cleanup,
                ), self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                    evidence._remove_expected_target_at(
                        parent,
                        journal.name,
                        b"journal-content",
                        journal_mode,
                        expected_identity=original_identity,
                    )
            finally:
                os.close(parent)

            self.assertTrue(replaced)
            self.assertEqual(journal.read_bytes(), b"journal-content")
            self.assertNotEqual(
                (journal.stat().st_dev, journal.stat().st_ino), original_identity
            )

    def test_transaction_cleanup_rejects_same_bytes_replacement_inodes(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        for surface in ("journal", "identity", "finalization"):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory).resolve()
                target = root / "config" / "generated.json"
                target.parent.mkdir(parents=True)
                target.write_bytes(b"old-content")
                journal = evidence.catalog_rollout_transaction_path(root)
                identity = evidence.catalog_rollout_transaction_identity_path(root)
                finalization = evidence.catalog_rollout_transaction_finalization_path(root)
                original_validate = evidence._validate_cross_file_rollout_evidence
                original_capture_state_and_identity = (
                    evidence._capture_transaction_state_and_identity_at
                )
                validation_count = 0
                state = {"replaced": False}
                original_identity: tuple[int, int] | None = None
                replacement_identity: tuple[int, int] | None = None

                def replace_same_bytes(path: Path, *, _state=state) -> None:
                    nonlocal original_identity, replacement_identity
                    original_identity = (path.stat().st_dev, path.stat().st_ino)
                    replacement = path.with_name(f"external-{path.name}")
                    replacement.write_bytes(path.read_bytes())
                    os.chmod(replacement, stat.S_IMODE(path.stat().st_mode))
                    os.replace(replacement, path)
                    replacement_identity = (path.stat().st_dev, path.stat().st_ino)
                    _state["replaced"] = True

                def replace_after_validation(
                    repository_root,
                    pending_writes=None,
                    *,
                    _original_validate=original_validate,
                    _surface=surface,
                    _journal=journal,
                    _identity=identity,
                ):
                    nonlocal validation_count
                    result = _original_validate(repository_root, pending_writes)
                    validation_count += 1
                    if _surface in {"journal", "identity"} and validation_count == 2:
                        replace_same_bytes(_journal if _surface == "journal" else _identity)
                    return result

                def replace_after_finalization_capture(
                    parent_descriptor,
                    target_name,
                    *,
                    _original_capture_state_and_identity=original_capture_state_and_identity,
                    _surface=surface,
                    _finalization=finalization,
                    _state=state,
                ):
                    result = _original_capture_state_and_identity(
                        parent_descriptor, target_name
                    )
                    if (
                        _surface == "finalization"
                        and target_name == _finalization.name
                        and result[0][0]
                        and not _state["replaced"]
                    ):
                        replace_same_bytes(_finalization)
                    return result

                if surface == "finalization":
                    validator = mock.patch.object(
                        evidence,
                        "_capture_transaction_state_and_identity_at",
                        side_effect=replace_after_finalization_capture,
                    )
                else:
                    validator = mock.patch.object(
                        evidence,
                        "_validate_cross_file_rollout_evidence",
                        side_effect=replace_after_validation,
                    )
                with validator, self.assertRaisesRegex(RuntimeError, surface):
                    evidence.commit_catalog_rollout_transaction(
                        root, ((target, b"new-content"),)
                    )

                self.assertTrue(state["replaced"])
                self.assertTrue(
                    (journal if surface == "journal" else identity if surface == "identity" else finalization).is_file()
                )
                self.assertNotEqual(original_identity, replacement_identity)

    def test_transaction_rejects_a_mutated_journal_tombstone(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            journal = evidence.catalog_rollout_transaction_path(root)
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
journal_name = evidence.catalog_rollout_transaction_path(root).name
original_move = evidence._rename_no_replace_at

def crash_after_journal_move(source_parent, source, destination_parent, destination, **kwargs):
    if source == journal_name and str(destination).endswith(".rollback"):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(29)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_journal_move
evidence.commit_catalog_rollout_transaction(
    root, ((root / "config" / "generated.json", b"new-content"),)
)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 29, result.stderr)
            tombstone = next(journal.parent.glob(f".{journal.name}.*.rollback"))
            mutated = json.loads(tombstone.read_text(encoding="utf-8"))
            mutated["writes"][0]["content-base64"] = "ZXZpbA=="
            tombstone.write_bytes(evidence.pretty_json(mutated))

            with self.assertRaisesRegex(RuntimeError, "tombstone changed externally"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertTrue(tombstone.is_file())
            self.assertTrue(
                evidence.catalog_rollout_transaction_finalization_path(root).is_file()
            )

    def test_v2_journal_recovery_requires_its_identity_sidecar(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            journal = evidence.catalog_rollout_transaction_path(root)
            journal.write_bytes(
                evidence.pretty_json(
                    {
                        "schema-version": evidence.TRANSACTION_SCHEMA_VERSION,
                        "transaction-id": "2" * 32,
                        "writes": [
                            {
                                "content-base64": "bmV3LWNvbnRlbnQ=",
                                "path": "config/generated.json",
                                "prior-content-base64": "b2xkLWNvbnRlbnQ=",
                                "prior-exists": True,
                                "prior-mode": 0o644,
                                "prior-sha256": hashlib.sha256(b"old-content").hexdigest(),
                                "sha256": hashlib.sha256(b"new-content").hexdigest(),
                            }
                        ],
                    }
                )
            )

            with self.assertRaisesRegex(RuntimeError, "identity is missing"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertTrue(journal.is_file())

    def test_v2_journal_without_a_transaction_id_is_rejected(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            journal = evidence.catalog_rollout_transaction_path(root)
            journal.write_bytes(
                evidence.pretty_json(
                    {
                        "schema-version": evidence.TRANSACTION_SCHEMA_VERSION,
                        "writes": [
                            {
                                "content-base64": "bmV3LWNvbnRlbnQ=",
                                "path": "config/generated.json",
                                "prior-content-base64": "b2xkLWNvbnRlbnQ=",
                                "prior-exists": True,
                                "prior-mode": 0o644,
                                "prior-sha256": hashlib.sha256(
                                    b"old-content"
                                ).hexdigest(),
                                "sha256": hashlib.sha256(b"new-content").hexdigest(),
                            }
                        ],
                    }
                )
            )

            with self.assertRaisesRegex(RuntimeError, "journal is invalid"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertTrue(journal.is_file())

    def test_recovery_cleans_a_duplicate_journal_tombstone_after_restore(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            journal = evidence.catalog_rollout_transaction_path(root)
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
journal_name = evidence.catalog_rollout_transaction_path(root).name
original_move = evidence._rename_no_replace_at

def crash_after_journal_move(source_parent, source, destination_parent, destination, **kwargs):
    if source == journal_name and str(destination).endswith(".rollback"):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(31)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_journal_move
evidence.commit_catalog_rollout_transaction(
    root, ((root / "config" / "generated.json", b"new-content"),)
)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 31, result.stderr)
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, journal_name = evidence._open_anchored_parent(
                root_descriptor, root, journal
            )
            try:
                identity_state = evidence._capture_transaction_state_at(
                    parent_descriptor,
                    evidence.catalog_rollout_transaction_identity_path(root).name,
                )
                if identity_state[0]:
                    identity = evidence._parse_transaction_identity(identity_state[1])
                else:
                    marker_state = evidence._capture_transaction_state_at(
                        parent_descriptor,
                        evidence.catalog_rollout_transaction_finalization_path(root).name,
                    )
                    identity = evidence._parse_transaction_finalization_marker(
                        marker_state[1]
                    )
                restored = evidence._restore_transaction_journal_tombstone_at(
                    parent_descriptor, journal_name, identity
                )
                self.assertIsNotNone(restored)
                self.assertTrue(
                    evidence._journal_tombstone_candidates(
                        parent_descriptor, journal_name
                    )
                )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(journal.exists())
            self.assertEqual(list(journal.parent.glob(f".{journal.name}.*.rollback")), [])
            self.assertFalse(
                evidence.catalog_rollout_transaction_finalization_path(root).exists()
            )

    def test_recovery_removes_orphaned_identity_rollback_tombstone(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            identity = evidence.catalog_rollout_transaction_identity_path(root)
            identity.parent.mkdir(parents=True)
            identity.write_bytes(
                evidence.pretty_json(
                    {
                        "journal-sha256": "0" * 64,
                        "schema-version": evidence.TRANSACTION_IDENTITY_SCHEMA_VERSION,
                        "transaction-id": "1" * 32,
                    }
                )
            )
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
identity_name = evidence.catalog_rollout_transaction_identity_path(root).name
original_move = evidence._rename_no_replace_at

def crash_after_identity_move(source_parent, source, destination_parent, destination, **kwargs):
    if source == identity_name and str(destination).endswith(".rollback"):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(41)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_identity_move
parent = os.open(root / "config", evidence._DIRECTORY_OPEN_FLAGS)
try:
    evidence._remove_expected_target_at(
        parent,
        identity_name,
        evidence.catalog_rollout_transaction_identity_path(root).read_bytes(),
        0o644,
    )
finally:
    os.close(parent)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 41, result.stderr)
            self.assertFalse(identity.exists())
            self.assertEqual(
                len(
                    list(
                        identity.parent.glob(
                            f".{identity.name}.*.rollback"
                        )
                    )
                ),
                1,
            )

            self.assertFalse(evidence.recover_catalog_rollout_transaction(root))
            self.assertFalse(identity.exists())
            self.assertEqual(
                list(identity.parent.glob(f".{identity.name}.*.rollback")), []
            )

    def test_recovery_restores_identity_tombstone_before_v2_cleanup(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            identity_name = evidence.catalog_rollout_transaction_identity_path(root).name
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
identity_name = evidence.catalog_rollout_transaction_identity_path(root).name
original_move = evidence._rename_no_replace_at

def crash_after_identity_move(source_parent, source, destination_parent, destination, **kwargs):
    if source == identity_name and str(destination).endswith(".rollback"):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(47)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_identity_move
evidence.commit_catalog_rollout_transaction(
    root, ((root / "config" / "generated.json", b"new-content"),)
)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 47, result.stderr)
            identity = evidence.catalog_rollout_transaction_identity_path(root)
            journal = evidence.catalog_rollout_transaction_path(root)
            self.assertFalse(identity.exists())
            self.assertTrue(journal.exists())
            self.assertEqual(
                len(list(identity.parent.glob(f".{identity_name}.*.rollback"))), 1
            )

            self.assertTrue(evidence.recover_catalog_rollout_transaction(root))
            self.assertEqual(target.read_bytes(), b"new-content")
            self.assertFalse(identity.exists())
            self.assertFalse(journal.exists())
            self.assertFalse(
                evidence.catalog_rollout_transaction_finalization_path(root).exists()
            )

    def test_finalization_marker_reversion_is_rejected_before_rewrite(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
finalization_name = evidence.catalog_rollout_transaction_finalization_path(root).name
original_write = evidence.atomic_write_bytes

def crash_after_finalization(path, content, **kwargs):
    result = original_write(path, content, **kwargs)
    if kwargs.get("target_name") == finalization_name:
        os._exit(53)
    return result

evidence.atomic_write_bytes = crash_after_finalization
evidence.commit_catalog_rollout_transaction(
    root, ((root / "config" / "generated.json", b"new-content"),)
)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 53, result.stderr)
            target.write_bytes(b"old-content")

            with self.assertRaisesRegex(RuntimeError, "finalization target changed"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertTrue(
                evidence.catalog_rollout_transaction_finalization_path(root).exists()
            )
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).exists())

    def test_recovery_restores_a_quarantine_entry_after_process_crash(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
def crash_after_quarantine(*args, **kwargs):
    os._exit(43)

evidence._unlink_expected_entry_at = crash_after_quarantine
parent = os.open(target.parent, evidence._DIRECTORY_OPEN_FLAGS)
try:
    evidence._remove_expected_target_at(parent, target.name, b"new-content", 0o644)
finally:
    os.close(parent)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 43, result.stderr)
            self.assertFalse(target.exists())
            self.assertEqual(
                len(list(target.parent.glob(".catalog-rollout-quarantine.*"))), 1
            )

            parent = os.open(target.parent, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                self.assertFalse(evidence._capture_transaction_state_at(parent, target.name)[0])
                evidence._recover_quarantine_directories_at(parent)
                evidence._reconcile_target_artifacts_at(
                    parent,
                    target.name,
                    False,
                    b"",
                    None,
                    b"new-content",
                    0o644,
                )
            finally:
                os.close(parent)
            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.glob(".catalog-rollout-quarantine.*")), [])
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.rollback")), [])

    def test_recovery_rejects_canonical_files_injected_into_quarantine(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            config = root / "config"
            config.mkdir(parents=True)
            target = config / "generated.json"
            target.write_bytes(b"old-content")
            quarantine = config / ".catalog-rollout-quarantine.injected"
            quarantine.mkdir()
            journal_name = evidence.catalog_rollout_transaction_path(root).name
            (quarantine / journal_name).write_bytes(b"injected")

            with self.assertRaisesRegex(RuntimeError, "quarantine evidence is invalid"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertTrue((quarantine / journal_name).is_file())

    def test_recovery_rejects_quarantine_owned_by_another_transaction(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            config = root / "config"
            config.mkdir(parents=True)
            content = b"owned-rollback"
            tombstone_name = f".generated.json.123.{'a' * 32}.rollback"
            entry_name = f"{tombstone_name}.456.{'b' * 32}.rollback"
            quarantine_name = evidence._quarantine_directory_name(
                "b" * 32, tombstone_name, content, 0o644
            )
            quarantine = config / quarantine_name
            quarantine.mkdir(mode=0o700)
            (quarantine / entry_name).write_bytes(content)
            parent = os.open(config, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                with self.assertRaisesRegex(RuntimeError, "belongs to another transaction"):
                    evidence._recover_quarantine_directories_at(
                        parent, expected_transaction_id="a" * 32
                    )
            finally:
                os.close(parent)
            self.assertTrue((quarantine / entry_name).is_file())

    def test_recovery_does_not_move_orphan_quarantine_before_canonical_evidence(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            config = root / "config"
            config.mkdir(parents=True)
            content = b"orphan-rollback"
            tombstone_name = f".generated.json.123.{'a' * 32}.rollback"
            entry_name = f"{tombstone_name}.456.{'a' * 32}.rollback"
            quarantine_name = evidence._quarantine_directory_name(
                "orphan", tombstone_name, content, 0o644
            )
            quarantine = config / quarantine_name
            quarantine.mkdir(mode=0o700)
            entry = quarantine / entry_name
            entry.write_bytes(content)

            with self.assertRaisesRegex(RuntimeError, "no canonical transaction"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertTrue(entry.is_file())
            self.assertFalse((config / entry_name).exists())

    def test_recovery_restores_quarantine_after_provenance_inode_content_mutation(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            config = root / "config"
            config.mkdir(parents=True)
            content = b"owned-rollback"
            tombstone_name = f".generated.json.123.{'a' * 32}.rollback"
            entry_name = f"{tombstone_name}.456.{'a' * 32}.rollback"
            quarantine_name = evidence._quarantine_directory_name(
                "a" * 32, tombstone_name, content, 0o644
            )
            quarantine = config / quarantine_name
            quarantine.mkdir(mode=0o700)
            (quarantine / entry_name).write_bytes(content)
            original_move = evidence._rename_no_replace_at
            mutated = False

            def mutate_before_quarantine_restore(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal mutated
                if source == entry_name and destination_parent != source_parent and not mutated:
                    mutated = True
                    descriptor = os.open(source, os.O_WRONLY, dir_fd=source_parent)
                    try:
                        os.write(descriptor, b"mutated-rollback")
                    finally:
                        os.close(descriptor)
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            parent = os.open(config, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=mutate_before_quarantine_restore,
                ), self.assertRaisesRegex(RuntimeError, "provenance changed externally"):
                    evidence._recover_quarantine_directories_at(
                        parent, expected_transaction_id="a" * 32
                    )
            finally:
                os.close(parent)

            self.assertTrue(mutated)
            self.assertTrue((quarantine / entry_name).is_file())
            self.assertFalse((config / entry_name).exists())

    def test_recovery_removes_orphaned_missing_target_rollback_tombstone(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")
            child = f"""
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import catalog_rollout_evidence as evidence

root = Path(sys.argv[1])
target = Path(sys.argv[2])
original_move = evidence._rename_no_replace_at

def crash_after_target_move(source_parent, source, destination_parent, destination, **kwargs):
    if source == target.name and str(destination).endswith(".rollback"):
        original_move(source_parent, source, destination_parent, destination, **kwargs)
        os._exit(37)
    return original_move(source_parent, source, destination_parent, destination, **kwargs)

evidence._rename_no_replace_at = crash_after_target_move
parent = os.open(target.parent, evidence._DIRECTORY_OPEN_FLAGS)
try:
    evidence._remove_expected_target_at(parent, target.name, b"new-content", 0o644)
finally:
    os.close(parent)
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(root), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 37, result.stderr)
            self.assertFalse(target.exists())
            self.assertEqual(
                len(list(target.parent.glob(f".{target.name}.*.rollback"))), 1
            )

            parent = os.open(target.parent, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                evidence._reconcile_target_artifacts_at(
                    parent,
                    target.name,
                    False,
                    b"",
                    None,
                    b"new-content",
                    0o644,
                )
            finally:
                os.close(parent)
            self.assertFalse(target.exists())
            self.assertEqual(
                list(target.parent.glob(f".{target.name}.*.rollback")), []
            )

    def test_reconcile_rejects_foreign_artifacts_and_accepts_same_transaction_guard(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            config = root / "config"
            config.mkdir(parents=True)
            target = config / "generated.json"
            parent = os.open(config, evidence._DIRECTORY_OPEN_FLAGS)
            try:
                foreign_guard = (
                    f".{target.name}.{'b' * 32}.123.{'c' * 32}.replace"
                )
                (config / foreign_guard).write_bytes(b"old-content")
                with self.assertRaisesRegex(RuntimeError, "belongs to another transaction"):
                    evidence._reconcile_target_artifacts_at(
                        parent,
                        target.name,
                        True,
                        b"old-content",
                        0o644,
                        b"new-content",
                        0o644,
                        transaction_id="a" * 32,
                    )
                self.assertTrue((config / foreign_guard).is_file())
                (config / foreign_guard).unlink()

                same_guard = f".{target.name}.{'a' * 32}.123.{'d' * 32}.replace"
                (config / same_guard).write_bytes(b"old-content")
                evidence._reconcile_target_artifacts_at(
                    parent,
                    target.name,
                    True,
                    b"old-content",
                    0o644,
                    b"new-content",
                    0o644,
                    transaction_id="a" * 32,
                )
            finally:
                os.close(parent)

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertFalse((config / same_guard).exists())

    def test_transaction_journal_removal_recreates_after_external_deletion(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            journal = evidence.catalog_rollout_transaction_path(root)
            journal.parent.mkdir(parents=True)
            journal.write_bytes(b"journal-content")
            original_move = evidence._rename_no_replace_at
            deleted = False

            def delete_before_remove(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal deleted
                if not deleted and source == journal.name:
                    deleted = True
                    journal.unlink()
                    raise FileNotFoundError("injected journal deletion")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, journal
            )
            try:
                with mock.patch.object(
                    evidence,
                    "_rename_no_replace_at",
                    side_effect=delete_before_remove,
                ), self.assertRaisesRegex(RuntimeError, "target disappeared before removal"):
                    evidence._remove_expected_target_at(
                        parent_descriptor,
                        target_name,
                        b"journal-content",
                        stat.S_IMODE(journal.stat().st_mode),
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertTrue(deleted)
            self.assertEqual(journal.read_bytes(), b"journal-content")

    def test_transaction_cleans_tombstone_when_restore_conflicts(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")
            original_capture = evidence._capture_transaction_state_at
            original_unlink_expected = evidence._unlink_expected_entry_at
            capture_injected = False
            unlink_injected = False

            def report_missing_then_insert(parent_descriptor, target_name):
                nonlocal capture_injected
                state = original_capture(parent_descriptor, target_name)
                if target_name == target.name and not capture_injected:
                    capture_injected = True
                    target.write_bytes(b"external-inserted")
                    return False, b"", None
                return state

            def fail_first_tombstone_unlink(
                parent_descriptor, entry_name, expected_identity, expected_content, expected_mode
            ):
                nonlocal unlink_injected
                if not unlink_injected:
                    unlink_injected = True
                    raise OSError("injected tombstone unlink failure")
                return original_unlink_expected(
                    parent_descriptor,
                    entry_name,
                    expected_identity,
                    expected_content,
                    expected_mode,
                )

            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, target
            )
            try:
                with mock.patch.object(
                    evidence,
                    "_capture_transaction_state_at",
                    side_effect=report_missing_then_insert,
                ), mock.patch.object(
                    evidence,
                    "_unlink_expected_entry_at",
                    side_effect=fail_first_tombstone_unlink,
                ), self.assertRaisesRegex(RuntimeError, "external target appeared"):
                    evidence._remove_expected_target_at(
                        parent_descriptor,
                        target_name,
                        b"new-content",
                        stat.S_IMODE(target.stat().st_mode),
                    )
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

            self.assertTrue(capture_injected)
            self.assertTrue(unlink_injected)
            self.assertEqual(target.read_bytes(), b"external-inserted")
            self.assertEqual(
                list(target.parent.glob(f".{target.name}.*.rollback")), []
            )

    def test_transaction_rejects_fifo_before_blocking_open(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "fifo"
            target.parent.mkdir(parents=True)
            os.mkfifo(target)
            root_descriptor = os.open(root, evidence._DIRECTORY_OPEN_FLAGS)
            parent_descriptor, target_name = evidence._open_anchored_parent(
                root_descriptor, root, target
            )
            try:
                with self.assertRaisesRegex(RuntimeError, "regular file"):
                    evidence._capture_transaction_state_at(parent_descriptor, target_name)
            finally:
                os.close(parent_descriptor)
                os.close(root_descriptor)

    def test_transaction_anchors_target_parent_when_it_becomes_a_symlink(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory).resolve()
            outside = Path(outside_directory).resolve()
            config_path = root / "config"
            target = config_path / "generated.json"
            config_path.mkdir(parents=True)
            target.write_bytes(b"old-content")
            outside_target = outside / "generated.json"
            outside_target.write_bytes(b"external-content")
            original_atomic_write = evidence.atomic_write_bytes
            swapped = False

            def swap_parent_before_replace(path, content, **kwargs):
                nonlocal swapped
                if path == target and not swapped:
                    swapped = True
                    original_config = root / "config-original"
                    config_path.rename(original_config)
                    config_path.symlink_to(outside, target_is_directory=True)
                return original_atomic_write(path, content, **kwargs)

            with mock.patch.object(
                evidence,
                "atomic_write_bytes",
                side_effect=swap_parent_before_replace,
            ), self.assertRaisesRegex(RuntimeError, "parent directory changed externally"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertTrue(config_path.is_symlink())
            self.assertEqual(outside_target.read_bytes(), b"external-content")
            self.assertEqual(
                (root / "config-original" / "generated.json").read_bytes(),
                b"old-content",
            )
            self.assertTrue(
                (root / "config-original" / ".catalog-rollout-transaction.json").is_file()
            )

    def test_transaction_rollback_removes_a_target_that_did_not_exist(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new-content")

            evidence._restore_transaction_target(
                target,
                False,
                b"",
                None,
                b"new-content",
                0o644,
            )

            self.assertFalse(target.exists())

    def test_transaction_preserves_existing_file_mode(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")
            os.chmod(target, 0o2750)

            evidence.commit_catalog_rollout_transaction(root, ((target, b"new-content"),))

            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o2750)
            self.assertEqual(target.read_bytes(), b"new-content")

    def test_new_transaction_does_not_overwrite_a_pending_journal(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            journal_path = evidence.catalog_rollout_transaction_path(root)
            journal_path.parent.mkdir(parents=True)
            journal_path.write_bytes(b"pending")
            target = root / "config" / "generated.json"

            with self.assertRaisesRegex(RuntimeError, "already has a pending journal"):
                evidence.commit_catalog_rollout_transaction(root, ((target, b"new"),))

            self.assertEqual(journal_path.read_bytes(), b"pending")
            self.assertFalse(target.exists())

    def test_transaction_commit_rejects_a_missing_recovery_journal(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "generated.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old-content")

            with mock.patch.object(
                evidence,
                "_recover_catalog_rollout_transaction",
                return_value=False,
            ), self.assertRaisesRegex(RuntimeError, "journal disappeared during recovery"):
                evidence.commit_catalog_rollout_transaction(
                    root, ((target, b"new-content"),)
                )

            self.assertEqual(target.read_bytes(), b"old-content")
            self.assertTrue(evidence.catalog_rollout_transaction_path(root).is_file())

    def test_transaction_recovery_keeps_journal_when_cross_file_evidence_is_invalid(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            rollout = "candidate"
            snapshot = root / "config" / "rollouts" / rollout
            snapshot.mkdir(parents=True)
            audit_bytes = b'{"schema-version":1}\n'
            receipt_bytes = b'{"status":"verified-resolved-graph"}\n'
            audit_path = "config/rollouts/candidate/latest-stable-version-audit.json"
            delta_path = "config/rollouts/candidate/latest-stable-version-deltas.json"
            receipt_path = "config/rollouts/candidate/resolved-graph-receipt.json"
            (root / audit_path).write_bytes(audit_bytes)
            (root / receipt_path).write_bytes(receipt_bytes)
            authority = {
                "rollout": rollout,
                "status": "verified-resolved-graph",
                "candidate": {"catalog-sha256": "a" * 64},
                "audit": {
                    "path": audit_path,
                    "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                },
                "delta": [],
                "resolved-graph-evidence": {
                    "path": receipt_path,
                    "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                    "observation-count": 0,
                    "spec-count": 0,
                },
            }
            authority_bytes = evidence.pretty_json(authority)
            (root / delta_path).write_bytes(authority_bytes)
            central = {
                "subsequent-rollouts": [
                    {
                        "rollout": rollout,
                        "status": "verified-resolved-graph",
                        "catalog-sha256": "a" * 64,
                        "audit": audit_path,
                        "audit-sha256": hashlib.sha256(audit_bytes).hexdigest(),
                        "authority-delta-ledger": delta_path,
                        "authority-delta-ledger-sha256": "b" * 64,
                        "resolved-graph-evidence": {
                            "path": receipt_path,
                            "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                            "observation-count": 0,
                            "spec-count": 0,
                        },
                    }
                ]
            }
            central_path = root / "config" / "central-catalog-version-deltas.json"
            authority_path = root / "config" / "latest-stable-version-deltas.json"
            previous_authority_bytes = b'{"state":"previous-authority"}\n'
            previous_central_bytes = b'{"state":"previous-central"}\n'
            authority_path.write_bytes(previous_authority_bytes)
            central_path.write_bytes(previous_central_bytes)
            journal = {
                "schema-version": evidence.TRANSACTION_SCHEMA_VERSION,
                "transaction-id": "3" * 32,
                "writes": [
                    {
                        "path": "config/latest-stable-version-deltas.json",
                        "content-base64": __import__("base64").b64encode(
                            authority_bytes
                        ).decode("ascii"),
                        "prior-content-base64": __import__("base64").b64encode(
                            previous_authority_bytes
                        ).decode("ascii"),
                        "prior-exists": True,
                        "prior-mode": __import__("stat").S_IMODE(
                            authority_path.stat().st_mode
                        ),
                        "prior-sha256": hashlib.sha256(
                            previous_authority_bytes
                        ).hexdigest(),
                        "sha256": hashlib.sha256(authority_bytes).hexdigest(),
                    },
                    {
                        "path": "config/central-catalog-version-deltas.json",
                        "content-base64": __import__("base64").b64encode(
                            evidence.pretty_json(central)
                        ).decode("ascii"),
                        "prior-content-base64": __import__("base64").b64encode(
                            previous_central_bytes
                        ).decode("ascii"),
                        "prior-exists": True,
                        "prior-mode": __import__("stat").S_IMODE(
                            central_path.stat().st_mode
                        ),
                        "prior-sha256": hashlib.sha256(
                            previous_central_bytes
                        ).hexdigest(),
                        "sha256": hashlib.sha256(
                            evidence.pretty_json(central)
                        ).hexdigest(),
                    },
                ],
            }
            journal_path = evidence.catalog_rollout_transaction_path(root)
            journal_bytes = evidence.pretty_json(journal)
            evidence.atomic_write_bytes(journal_path, journal_bytes)
            evidence.atomic_write_bytes(
                evidence.catalog_rollout_transaction_identity_path(root),
                evidence.pretty_json(
                    {
                        "journal-sha256": hashlib.sha256(journal_bytes).hexdigest(),
                        "schema-version": evidence.TRANSACTION_IDENTITY_SCHEMA_VERSION,
                        "transaction-id": journal["transaction-id"],
                    }
                ),
            )

            with self.assertRaisesRegex(RuntimeError, "cross-file rollout evidence"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertTrue(journal_path.exists())
            self.assertEqual(authority_path.read_bytes(), previous_authority_bytes)
            self.assertEqual(central_path.read_bytes(), previous_central_bytes)

    def test_cross_file_validation_rejects_a_baseline_mismatch(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            rollout = "candidate"
            immutable_dir = root / "config" / "rollouts" / rollout / "revision-a"
            immutable_dir.mkdir(parents=True)
            audit_bytes = b'{"audit":"pinned"}\n'
            audit_relative = f"config/rollouts/{rollout}/revision-a/audit.json"
            snapshot_ledger_relative = (
                f"config/rollouts/{rollout}/revision-a/deltas.json"
            )
            current_audit_relative = "config/latest-stable-version-audit.json"
            current_ledger_relative = "config/latest-stable-version-deltas.json"
            (root / audit_relative).write_bytes(audit_bytes)
            (root / current_audit_relative).write_bytes(audit_bytes)
            snapshot_ledger = {
                "rollout": rollout,
                "status": "validation-pending",
                "baseline": {"catalog-ref": "expected-base"},
                "candidate": {"catalog-sha256": "a" * 64},
                "audit": {
                    "path": audit_relative,
                    "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                },
                "delta": [],
            }
            current_ledger = json.loads(json.dumps(snapshot_ledger))
            current_ledger["baseline"]["catalog-ref"] = "tampered-base"
            current_ledger["audit"]["path"] = current_audit_relative
            snapshot_ledger_bytes = evidence.pretty_json(snapshot_ledger)
            current_ledger_bytes = evidence.pretty_json(current_ledger)
            (root / snapshot_ledger_relative).write_bytes(snapshot_ledger_bytes)
            (root / current_ledger_relative).write_bytes(current_ledger_bytes)
            central = {
                "subsequent-rollouts": [
                    {
                        "rollout": rollout,
                        "status": "validation-pending",
                        "catalog-sha256": "a" * 64,
                        "baseline-catalog-ref": "expected-base",
                        "delta-count": 0,
                        "audit": audit_relative,
                        "audit-sha256": hashlib.sha256(audit_bytes).hexdigest(),
                        "authority-delta-ledger": snapshot_ledger_relative,
                        "authority-delta-ledger-sha256": hashlib.sha256(
                            snapshot_ledger_bytes
                        ).hexdigest(),
                        "resolved-graph-evidence": [],
                    }
                ]
            }
            central_path = root / "config" / "central-catalog-version-deltas.json"
            central_path.write_bytes(evidence.pretty_json(central))

            with self.assertRaisesRegex(RuntimeError, "cross-file rollout evidence"):
                evidence._validate_cross_file_rollout_evidence(root)

    def test_pending_transaction_recovery_requires_immutable_evidence_paths(self) -> None:
        load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            rollout = "candidate"
            audit_path = "config/latest-stable-version-audit.json"
            delta_path = "config/latest-stable-version-deltas.json"
            audit_bytes = b'{"schema-version":1}\n'
            authority = {
                "rollout": rollout,
                "status": "validation-pending",
                "candidate": {"catalog-sha256": "a" * 64},
                "audit": {
                    "path": audit_path,
                    "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                },
                "delta": [],
            }
            authority_bytes = evidence.pretty_json(authority)
            central = {
                "subsequent-rollouts": [
                    {
                        "rollout": rollout,
                        "status": "validation-pending",
                        "catalog-sha256": "a" * 64,
                        "audit": audit_path,
                        "audit-sha256": hashlib.sha256(audit_bytes).hexdigest(),
                        "authority-delta-ledger": delta_path,
                        "authority-delta-ledger-sha256": hashlib.sha256(
                            authority_bytes
                        ).hexdigest(),
                        "resolved-graph-evidence": [],
                    }
                ]
            }
            central_bytes = evidence.pretty_json(central)
            journal = {
                "schema-version": evidence.TRANSACTION_SCHEMA_VERSION,
                "transaction-id": "4" * 32,
                "writes": [
                    {
                        "path": audit_path,
                        "content-base64": __import__("base64")
                        .b64encode(audit_bytes)
                        .decode("ascii"),
                        "prior-content-base64": "",
                        "prior-exists": False,
                        "prior-mode": None,
                        "prior-sha256": hashlib.sha256(b"").hexdigest(),
                        "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                    },
                    {
                        "path": delta_path,
                        "content-base64": __import__("base64")
                        .b64encode(authority_bytes)
                        .decode("ascii"),
                        "prior-content-base64": "",
                        "prior-exists": False,
                        "prior-mode": None,
                        "prior-sha256": hashlib.sha256(b"").hexdigest(),
                        "sha256": hashlib.sha256(authority_bytes).hexdigest(),
                    },
                    {
                        "path": "config/central-catalog-version-deltas.json",
                        "content-base64": __import__("base64")
                        .b64encode(central_bytes)
                        .decode("ascii"),
                        "prior-content-base64": "",
                        "prior-exists": False,
                        "prior-mode": None,
                        "prior-sha256": hashlib.sha256(b"").hexdigest(),
                        "sha256": hashlib.sha256(central_bytes).hexdigest(),
                    },
                ],
            }
            journal_path = evidence.catalog_rollout_transaction_path(root)
            journal_bytes = evidence.pretty_json(journal)
            evidence.atomic_write_bytes(journal_path, journal_bytes)
            evidence.atomic_write_bytes(
                evidence.catalog_rollout_transaction_identity_path(root),
                evidence.pretty_json(
                    {
                        "journal-sha256": hashlib.sha256(journal_bytes).hexdigest(),
                        "schema-version": evidence.TRANSACTION_IDENTITY_SCHEMA_VERSION,
                        "transaction-id": journal["transaction-id"],
                    }
                ),
            )

            with self.assertRaisesRegex(RuntimeError, "cross-file rollout evidence"):
                evidence.recover_catalog_rollout_transaction(root)

            self.assertTrue(journal_path.exists())

    def test_pending_timefold_rollout_does_not_claim_verified_deltas(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        rollout = next(
            item
            for item in document["subsequent-rollouts"]
            if item["rollout"] == TIMEFOLD_ROLLOUT
        )

        self.assertEqual(rollout["status"], "validation-pending")
        self.assertEqual(rollout["delta-count"], 1)
        self.assertEqual(rollout["resolved-graph-evidence"], [])

    def test_legacy_superseded_row_requires_an_explicit_missing_lineage_contract(self) -> None:
        load_script()
        module = importlib.import_module("catalog_rollout_evidence")
        row = {
            "rollout": "legacy-rollout",
            "status": "verified",
            "evidence-status": "legacy-superseded",
            "evidence-exception": "원본 authority ledger를 복원할 수 없다.",
            "catalog-sha256": "a" * 64,
            "candidate-receipt": "docs/releases/candidate.json",
            "authority-delta-ledger": None,
            "audit": None,
            "audit-sha256": None,
            "resolved-graph-evidence": [],
            "superseding-local-candidate": {
                "status": "verified-local-candidate",
                "catalog-commit": "b" * 40,
                "catalog-sha256": "c" * 64,
            },
        }

        module.validate_legacy_rollout_contract(row)

        row["authority-delta-ledger"] = "config/latest-stable-version-deltas.json"
        with self.assertRaisesRegex(RuntimeError, "cannot claim its missing authority ledger"):
            module.validate_legacy_rollout_contract(row)

    def test_upsert_catalog_rollout_preserves_history(self) -> None:
        module = load_script()
        document = {
            "schema-version": 2,
            "rollout": "issue-168",
            "status": "pending-resolved-graph",
            "delta": [],
            "subsequent-rollouts": [{"rollout": "historical", "status": "verified"}],
        }
        authority = {
            "rollout": "current",
            "status": "validation-pending",
            "baseline": {"catalog-ref": "baseline"},
            "candidate": {"catalog-sha256": "candidate"},
            "audit": {"path": "config/latest-stable-version-audit.json"},
            "delta": [{"version-key": "example"}],
        }
        artifacts = {
            "audit": {
                "path": "config/rollouts/current/latest-stable-version-audit.json",
                "sha256": "a" * 64,
            },
            "authority-delta-ledger": {
                "path": "config/rollouts/current/latest-stable-version-deltas.json",
                "sha256": "b" * 64,
            },
        }

        updated = module.upsert_catalog_rollout(document, authority, artifacts)

        self.assertEqual(updated["subsequent-rollouts"][0]["rollout"], "historical")
        self.assertEqual(updated["subsequent-rollouts"][1]["rollout"], "current")
        self.assertEqual(updated["subsequent-rollouts"][1]["catalog-sha256"], "candidate")
        current = updated["subsequent-rollouts"][1]
        self.assertEqual(current["audit"], artifacts["audit"]["path"])
        self.assertEqual(current["audit-sha256"], artifacts["audit"]["sha256"])
        self.assertEqual(
            current["authority-delta-ledger"],
            artifacts["authority-delta-ledger"]["path"],
        )
        self.assertEqual(
            current["authority-delta-ledger-sha256"],
            artifacts["authority-delta-ledger"]["sha256"],
        )

    def test_snapshot_rollout_evidence_pins_immutable_files(self) -> None:
        module = load_script()
        audit_bytes = b'{"schema-version":1}\n'
        authority = {
            "rollout": "candidate",
            "audit": {
                "path": "config/latest-stable-version-audit.json",
                "sha256": hashlib.sha256(audit_bytes).hexdigest(),
            },
            "delta": [{"version-key": "example"}],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = module.snapshot_rollout_evidence(
                authority, audit_bytes, repository_root=root
            )

            audit_path = root / artifacts["audit"]["path"]
            ledger_path = root / artifacts["authority-delta-ledger"]["path"]
            snapshot_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

            self.assertEqual(audit_path.read_bytes(), audit_bytes)
            self.assertEqual(
                hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                artifacts["audit"]["sha256"],
            )
            self.assertEqual(
                hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
                artifacts["authority-delta-ledger"]["sha256"],
            )
            self.assertEqual(
                snapshot_ledger["audit"]["path"], artifacts["audit"]["path"]
            )
            self.assertEqual(
                snapshot_ledger["audit"]["sha256"], artifacts["audit"]["sha256"]
            )
            self.assertTrue(
                artifacts["audit"]["path"].startswith("config/rollouts/candidate/")
            )
            self.assertTrue(
                artifacts["authority-delta-ledger"]["path"].startswith(
                    "config/rollouts/candidate/"
                )
            )

            changed_audit_bytes = b'{"schema-version":2}\n'
            changed_authority = {
                "rollout": "candidate",
                "audit": {
                    "path": "config/latest-stable-version-audit.json",
                    "sha256": hashlib.sha256(changed_audit_bytes).hexdigest(),
                },
                "delta": [{"version-key": "example"}],
            }
            with self.assertRaisesRegex(RuntimeError, "immutable rollout snapshot differs"):
                module.snapshot_rollout_evidence(
                    changed_authority, changed_audit_bytes, repository_root=root
                )

    def test_snapshot_write_failure_does_not_leave_a_partial_immutable_directory(self) -> None:
        module = load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        audit_bytes = b'{"schema-version":1}\n'
        authority = {
            "rollout": "candidate",
            "audit": {"sha256": hashlib.sha256(audit_bytes).hexdigest()},
            "delta": [],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot_dir = (
                root
                / "config"
                / "rollouts"
                / "candidate"
            )
            original_move = evidence._rename_no_replace_at

            def fail_snapshot_replace(
                source_parent, source, destination_parent, destination, **kwargs
            ) -> None:
                if destination == snapshot_dir.name:
                    raise OSError("injected snapshot directory replace failure")
                original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            with mock.patch.object(
                evidence, "_rename_no_replace_at", side_effect=fail_snapshot_replace
            ), self.assertRaisesRegex(OSError, "injected snapshot directory replace"):
                module.snapshot_rollout_evidence(
                    authority, audit_bytes, repository_root=root
                )

            self.assertFalse(snapshot_dir.exists())
            self.assertFalse(list(snapshot_dir.parent.glob(".candidate.*")))

    def test_snapshot_destination_collision_preserves_external_directory(self) -> None:
        module = load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        audit_bytes = b'{"schema-version":1}\n'
        authority = {
            "rollout": "candidate",
            "audit": {"sha256": hashlib.sha256(audit_bytes).hexdigest()},
            "delta": [],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot_dir = root / "config" / "rollouts" / "candidate"
            original_move = evidence._rename_no_replace_at
            injected = False

            def inject_snapshot_destination(
                source_parent, source, destination_parent, destination, **kwargs
            ):
                nonlocal injected
                if destination == snapshot_dir.name and not injected:
                    injected = True
                    snapshot_dir.mkdir(parents=True)
                    (snapshot_dir / "external.txt").write_bytes(b"external")
                return original_move(
                    source_parent, source, destination_parent, destination, **kwargs
                )

            with mock.patch.object(
                evidence,
                "_rename_no_replace_at",
                side_effect=inject_snapshot_destination,
            ), self.assertRaisesRegex(RuntimeError, "immutable rollout snapshot differs"):
                module.snapshot_rollout_evidence(
                    authority, audit_bytes, repository_root=root
                )

            self.assertTrue(injected)
            self.assertEqual((snapshot_dir / "external.txt").read_bytes(), b"external")

    def test_snapshot_reuse_checks_declared_artifact_bytes(self) -> None:
        module = load_script()
        audit_bytes = b'{"schema-version":1}\n'
        authority = {
            "rollout": "candidate",
            "audit": {"sha256": hashlib.sha256(audit_bytes).hexdigest()},
            "delta": [],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = module.snapshot_rollout_evidence(
                authority, audit_bytes, repository_root=root
            )
            (root / artifacts["audit"]["path"]).write_bytes(b"tampered\n")

            with self.assertRaisesRegex(RuntimeError, "audit snapshot SHA"):
                module.ensure_immutable_rollout_snapshot(
                    authority, audit_bytes, artifacts, root
                )

    def test_snapshot_rejects_dot_segments_in_rollout_and_revision(self) -> None:
        module = load_script()
        audit_bytes = b'{"schema-version":1}\n'
        for rollout, revision in (("..", None), ("candidate", "."), ("candidate", "..")):
            with self.subTest(rollout=rollout, revision=revision):
                authority = {
                    "rollout": rollout,
                    "audit": {"sha256": hashlib.sha256(audit_bytes).hexdigest()},
                    "delta": [],
                }
                with tempfile.TemporaryDirectory() as temporary_directory, self.assertRaisesRegex(
                    RuntimeError, "safe for an immutable"
                ):
                    module.snapshot_rollout_evidence(
                        authority,
                        audit_bytes,
                        repository_root=Path(temporary_directory),
                        revision=revision,
                    )

    def test_snapshot_rejects_symlinked_repository_parents(self) -> None:
        module = load_script()
        audit_bytes = b'{"schema-version":1}\n'
        authority = {
            "rollout": "candidate",
            "audit": {"sha256": hashlib.sha256(audit_bytes).hexdigest()},
            "delta": [],
        }
        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory).resolve()
            outside = Path(outside_directory).resolve()
            (root / "config").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(RuntimeError, "snapshot parent changed externally"):
                module.snapshot_rollout_evidence(authority, audit_bytes, root)

            self.assertEqual(list(outside.rglob("*")), [])

    def test_immutable_bytes_rejects_symlinked_parent_before_external_write(self) -> None:
        load_script()
        module = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory).resolve()
            outside = Path(outside_directory).resolve()
            (root / "config").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(RuntimeError, "snapshot parent changed externally"):
                module.write_immutable_bytes(
                    root / "config" / "rollouts" / "candidate" / "receipt.json",
                    b"receipt\n",
                )

            self.assertEqual(list(outside.rglob("*")), [])

    def test_immutable_bytes_rejects_parent_replacement_after_descriptor_acquisition(self) -> None:
        load_script()
        module = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory).resolve()
            outside = Path(outside_directory).resolve()
            config = root / "config"
            config.mkdir()
            detached_config = root / "config-detached"
            real_open = module.os.open
            injected = False

            def replace_parent_before_component_open(name, *args, **kwargs):
                nonlocal injected
                if name == "rollouts" and not injected:
                    injected = True
                    config.rename(detached_config)
                    config.symlink_to(outside, target_is_directory=True)
                return real_open(name, *args, **kwargs)

            with mock.patch.object(
                module.os, "open", side_effect=replace_parent_before_component_open
            ), self.assertRaisesRegex(RuntimeError, "parent directory changed externally"):
                module.write_immutable_bytes(
                    root / "config" / "rollouts" / "candidate" / "receipt.json",
                    b"receipt\n",
                )

            self.assertTrue(injected)
            self.assertEqual(list(outside.rglob("*")), [])
            self.assertFalse((root / "config" / "rollouts").exists())

    def test_immutable_bytes_does_not_swallow_private_cleanup_failure(self) -> None:
        load_script()
        module = importlib.import_module("catalog_rollout_evidence")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "config" / "receipt.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"receipt\n")

            with mock.patch.object(
                module,
                "_unlink_expected_entry_at",
                side_effect=OSError("injected immutable cleanup failure"),
            ), self.assertRaisesRegex(OSError, "injected immutable cleanup failure"):
                module.write_immutable_bytes(target, b"receipt\n")

            self.assertEqual(target.read_bytes(), b"receipt\n")

    def test_snapshot_rollout_evidence_pins_an_immutable_resolved_graph_receipt(self) -> None:
        module = load_script()
        receipt_bytes = b'{"status":"verified-resolved-graph"}\n'
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        authority = {
            "rollout": "candidate",
            "status": "verified-resolved-graph",
            "audit": {"sha256": "a" * 64},
            "delta": [],
            "resolved-graph-evidence": {
                "path": "docs/releases/resolved-graphs.json",
                "sha256": receipt_sha,
                "observation-count": 0,
                "spec-count": 0,
            },
        }
        audit_bytes = b"audit"
        authority["audit"]["sha256"] = hashlib.sha256(audit_bytes).hexdigest()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = module.snapshot_rollout_evidence(
                authority,
                audit_bytes,
                repository_root=root,
                resolved_graph_receipt_bytes=receipt_bytes,
            )

            receipt_artifact = artifacts["resolved-graph-evidence"]
            self.assertTrue(
                receipt_artifact["path"].startswith("config/rollouts/candidate/")
            )
            self.assertEqual(
                (root / receipt_artifact["path"]).read_bytes(), receipt_bytes
            )
            snapshot = json.loads(
                (
                    root
                    / artifacts["authority-delta-ledger"]["path"]
                ).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                snapshot["resolved-graph-evidence"], receipt_artifact
            )

            changed_authority = json.loads(json.dumps(authority))
            changed_receipt = b'{"status":"tampered"}\n'
            changed_authority["resolved-graph-evidence"]["sha256"] = hashlib.sha256(
                changed_receipt
            ).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "immutable rollout snapshot differs"):
                module.snapshot_rollout_evidence(
                    changed_authority,
                    audit_bytes,
                    repository_root=root,
                    resolved_graph_receipt_bytes=changed_receipt,
                )

    def test_verified_rollout_requires_immutable_snapshot_paths(self) -> None:
        module = load_script()
        document = {
            "subsequent-rollouts": [
                {
                    "rollout": "historical",
                    "status": "verified-resolved-graph",
                    "audit": "config/latest-stable-version-audit.json",
                    "audit-sha256": "a" * 64,
                    "authority-delta-ledger": "config/latest-stable-version-deltas.json",
                    "authority-delta-ledger-sha256": "b" * 64,
                    "resolved-graph-evidence": {
                        "path": "docs/releases/resolved-graphs.json",
                        "sha256": "c" * 64,
                    },
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temporary_directory, self.assertRaisesRegex(
            RuntimeError, "immutable snapshot"
        ):
            module.load_catalog_rollout_evidence(
                document, "historical", Path(temporary_directory)
            )

    def test_previous_rollout_evidence_uses_declared_paths_and_checks_hashes(self) -> None:
        module = load_script()
        audit_bytes = b'{"audit":"previous"}\n'
        authority = {
            "rollout": "previous",
            "status": "validation-pending",
            "candidate": {"catalog-sha256": "c" * 64},
            "audit": {
                "path": "config/previous-audit.json",
                "sha256": hashlib.sha256(audit_bytes).hexdigest(),
            },
            "delta": [],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            subprocess.run(
                ["git", "init", str(root)], check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "test"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
                capture_output=True,
                text=True,
            )
            audit_path = root / "config" / "previous-audit.json"
            audit_path.parent.mkdir(parents=True)
            audit_path.write_bytes(audit_bytes)
            artifacts = module.snapshot_rollout_evidence(
                authority, audit_bytes, repository_root=root
            )
            row = {
                "rollout": "previous",
                "status": "validation-pending",
                "catalog-sha256": "c" * 64,
                "audit": artifacts["audit"]["path"],
                "audit-sha256": artifacts["audit"]["sha256"],
                "authority-delta-ledger": artifacts["authority-delta-ledger"]["path"],
                "authority-delta-ledger-sha256": artifacts[
                    "authority-delta-ledger"
                ]["sha256"],
            }
            expected_authority = json.loads(
                (root / artifacts["authority-delta-ledger"]["path"]).read_bytes()
            )
            subprocess.run(
                ["git", "-C", str(root), "add", "config"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-m", "preserve prior evidence"],
                check=True,
                capture_output=True,
                text=True,
            )
            source_ref = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (root / artifacts["audit"]["path"]).write_bytes(b'{"audit":"overwritten audit"}\n')
            (root / artifacts["authority-delta-ledger"]["path"]).write_bytes(
                b'{"rollout":"overwritten rollout"}\n'
            )
            (root / "config/latest-stable-version-audit.json").write_bytes(
                b'{"audit":"newer mutable audit"}\n'
            )
            (root / "config/latest-stable-version-deltas.json").write_bytes(
                b'{"rollout":"newer mutable rollout"}\n'
            )

            (
                loaded_authority,
                loaded_audit,
                loaded_artifacts,
            ) = module.load_catalog_rollout_evidence(
                {"subsequent-rollouts": [row]}, "previous", root, source_ref=source_ref
            )

            self.assertEqual(loaded_authority, expected_authority)
            self.assertEqual(loaded_audit, audit_bytes)
            self.assertEqual(
                loaded_artifacts,
                {
                    "audit": {
                        "path": row["audit"],
                        "sha256": row["audit-sha256"],
                    },
                    "authority-delta-ledger": {
                        "path": row["authority-delta-ledger"],
                        "sha256": row["authority-delta-ledger-sha256"],
                    },
                },
            )
            row["authority-delta-ledger-sha256"] = "d" * 64
            with self.assertRaisesRegex(RuntimeError, "delta-ledger SHA"):
                module.load_catalog_rollout_evidence(
                    {"subsequent-rollouts": [row]},
                    "previous",
                    root,
                    source_ref=source_ref,
                )

    def test_verified_rollout_reuses_its_declared_revision_snapshot(self) -> None:
        module = load_script()
        audit_bytes = b'{"schema-version":1}\n'
        pending = {
            "rollout": "previous",
            "status": "validation-pending",
            "baseline": {"catalog-ref": "baseline"},
            "candidate": {"catalog-sha256": "c" * 64},
            "audit": {
                "path": "config/latest-stable-version-audit.json",
                "sha256": hashlib.sha256(audit_bytes).hexdigest(),
            },
            "delta": [{"version-key": "example"}],
        }
        promoted = json.loads(json.dumps(pending))
        promoted["status"] = "verified-resolved-graph"
        receipt_bytes = b'{"status":"verified-resolved-graph"}\n'
        promoted["resolved-graph-evidence"] = {
            "observation-count": 2,
            "path": "docs/releases/resolved-graphs.json",
            "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "spec-count": 1,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipt_path = root / promoted["resolved-graph-evidence"]["path"]
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_bytes(receipt_bytes)
            pending_artifacts = module.snapshot_rollout_evidence(
                pending, audit_bytes, repository_root=root
            )
            central = module.upsert_catalog_rollout(
                {"schema-version": 2, "subsequent-rollouts": []},
                pending,
                pending_artifacts,
            )
            pending_snapshot_bytes = (
                root / pending_artifacts["authority-delta-ledger"]["path"]
            ).read_bytes()
            verified_central = module.record_promoted_catalog_rollout(
                central, promoted, audit_bytes, repository_root=root
            )
            row = verified_central["subsequent-rollouts"][0]

            loaded_authority, loaded_audit, declared_artifacts = (
                module.load_catalog_rollout_evidence(
                    verified_central, "previous", root
                )
            )
            reused_artifacts = module.ensure_immutable_rollout_snapshot(
                loaded_authority, loaded_audit, declared_artifacts, root
            )

            self.assertEqual(reused_artifacts, declared_artifacts)
            self.assertEqual(
                reused_artifacts["authority-delta-ledger"]["path"],
                row["authority-delta-ledger"],
            )
            self.assertIn("/resolved-graph-", row["authority-delta-ledger"])
            self.assertEqual(
                (root / pending_artifacts["authority-delta-ledger"]["path"]).read_bytes(),
                pending_snapshot_bytes,
            )

    def test_promoted_rollout_gets_a_new_immutable_central_snapshot(self) -> None:
        module = load_script()
        audit_bytes = b'{"schema-version":1}\n'
        pending = {
            "rollout": "candidate",
            "status": "validation-pending",
            "baseline": {"catalog-ref": "baseline"},
            "candidate": {"catalog-sha256": "c" * 64},
            "audit": {
                "path": "config/latest-stable-version-audit.json",
                "sha256": hashlib.sha256(audit_bytes).hexdigest(),
            },
            "delta": [{"version-key": "example"}],
        }
        promoted = json.loads(json.dumps(pending))
        promoted["status"] = "verified-resolved-graph"
        receipt_bytes = b'{"status":"verified-resolved-graph"}\n'
        promoted["resolved-graph-evidence"] = {
            "observation-count": 2,
            "path": "docs/releases/resolved-graphs.json",
            "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "spec-count": 1,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipt_path = root / promoted["resolved-graph-evidence"]["path"]
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_bytes(receipt_bytes)
            pending_artifacts = module.snapshot_rollout_evidence(
                pending, audit_bytes, repository_root=root
            )
            document = module.upsert_catalog_rollout(
                {"schema-version": 2, "subsequent-rollouts": []},
                pending,
                pending_artifacts,
            )
            pending_ledger_bytes = (
                root / pending_artifacts["authority-delta-ledger"]["path"]
            ).read_bytes()

            updated = module.record_promoted_catalog_rollout(
                document, promoted, audit_bytes, repository_root=root
            )

            row = updated["subsequent-rollouts"][0]
            self.assertEqual(row["status"], "verified-resolved-graph")
            self.assertEqual(
                row["resolved-graph-evidence"]["sha256"],
                promoted["resolved-graph-evidence"]["sha256"],
            )
            self.assertTrue(
                row["resolved-graph-evidence"]["path"].startswith(
                    "config/rollouts/candidate/"
                )
            )
            self.assertNotEqual(
                row["authority-delta-ledger"],
                pending_artifacts["authority-delta-ledger"]["path"],
            )
            self.assertEqual(
                (root / pending_artifacts["authority-delta-ledger"]["path"]).read_bytes(),
                pending_ledger_bytes,
            )
            verified_snapshot = json.loads(
                (root / row["authority-delta-ledger"]).read_text(encoding="utf-8")
            )
            self.assertEqual(verified_snapshot["status"], "verified-resolved-graph")
            self.assertEqual(
                verified_snapshot["resolved-graph-evidence"]["sha256"],
                promoted["resolved-graph-evidence"]["sha256"],
            )
            self.assertEqual(
                verified_snapshot["resolved-graph-evidence"]["path"],
                row["resolved-graph-evidence"]["path"],
            )

    def test_refreshing_existing_rollout_uses_a_new_snapshot_revision(self) -> None:
        module = load_script()
        evidence = importlib.import_module("catalog_rollout_evidence")
        audit_bytes = b'{"schema-version":1}\n'
        updated_audit_bytes = b'{"schema-version":2}\n'
        authority = {
            "rollout": "candidate",
            "status": "validation-pending",
            "candidate": {"catalog-sha256": "c" * 64},
            "audit": {"sha256": hashlib.sha256(audit_bytes).hexdigest()},
            "baseline": {"catalog-ref": "baseline"},
            "delta": [],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            initial = module.snapshot_rollout_evidence(authority, audit_bytes, root)
            central = module.upsert_catalog_rollout(
                {"schema-version": 2, "subsequent-rollouts": []},
                authority,
                initial,
            )
            revised_authority = json.loads(json.dumps(authority))
            revised_authority["audit"]["sha256"] = hashlib.sha256(
                updated_audit_bytes
            ).hexdigest()
            revision = evidence.candidate_rollout_snapshot_revision(
                central, revised_authority
            )
            updated = module.snapshot_rollout_evidence(
                revised_authority, updated_audit_bytes, root, revision=revision
            )

            self.assertTrue(revision.startswith("candidate-"))
            self.assertNotEqual(updated["audit"]["path"], initial["audit"]["path"])
            self.assertEqual((root / initial["audit"]["path"]).read_bytes(), audit_bytes)
            self.assertEqual(
                (root / updated["audit"]["path"]).read_bytes(), updated_audit_bytes
            )

    def test_pin_catalog_rollout_evidence_requires_exactly_one_row(self) -> None:
        module = load_script()
        artifacts = {
            "audit": {
                "path": "config/rollouts/candidate/latest-stable-version-audit.json",
                "sha256": "a" * 64,
            },
            "authority-delta-ledger": {
                "path": "config/rollouts/candidate/latest-stable-version-deltas.json",
                "sha256": "b" * 64,
            },
        }

        for rows in ([], [{"rollout": "candidate"}, {"rollout": "candidate"}]):
            with self.subTest(rows=rows), self.assertRaisesRegex(
                RuntimeError, "exactly one central rollout row"
            ):
                module.pin_catalog_rollout_evidence(
                    {"subsequent-rollouts": rows}, "candidate", artifacts
                )

    def test_ledger_preserves_issue_168_history_and_unique_rollouts(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))

        self.assertEqual(document["schema-version"], 2)
        self.assertEqual(document["rollout"], "2026-08-03-issue-168-central-catalog-authority")
        self.assertEqual(len(document["delta"]), 34)
        rollout_ids = [rollout["rollout"] for rollout in document["subsequent-rollouts"]]
        self.assertEqual(len(rollout_ids), len(set(rollout_ids)))
        self.assertIn("2026-08-04-issue-169-latest-compatible-stable", rollout_ids)
        self.assertIn("2026-08-05-issue-169-full-authority-audit", rollout_ids)

    def test_upsert_catalog_rollout_carries_verified_candidate_evidence(self) -> None:
        module = load_script()
        document = {
            "schema-version": 2,
            "rollout": "issue-168",
            "status": "pending-resolved-graph",
            "delta": [],
            "subsequent-rollouts": [],
        }
        authority = {
            "rollout": "current",
            "status": "verified-resolved-graph",
            "baseline": {"catalog-ref": "baseline"},
            "candidate": {"catalog-sha256": "candidate"},
            "audit": {"path": "config/latest-stable-version-audit.json"},
            "delta": [{"version-key": "example"}],
            "resolved-graph-evidence": {"path": "graphs.json", "spec-count": 1},
            "candidate-validation-evidence": {
                "downstream-full-builds": {"repositories": 9, "failures": 0},
                "publication-poms": {"repositories": 9, "failures": 0},
                "remote-immutable-ref-verification": "verified",
            },
        }
        artifacts = {
            "audit": {
                "path": "config/rollouts/current/latest-stable-version-audit.json",
                "sha256": "a" * 64,
            },
            "authority-delta-ledger": {
                "path": "config/rollouts/current/latest-stable-version-deltas.json",
                "sha256": "b" * 64,
            },
            "resolved-graph-evidence": {
                "path": "config/rollouts/current/resolved-graph.json",
                "sha256": "c" * 64,
                "observation-count": 1,
                "spec-count": 1,
            },
        }

        rollout = module.upsert_catalog_rollout(document, authority, artifacts)[
            "subsequent-rollouts"
        ][0]

        self.assertEqual(rollout["status"], "verified-resolved-graph")
        self.assertEqual(rollout["resolved-graph-evidence"]["spec-count"], 1)
        self.assertEqual(rollout["downstream-full-builds"]["failures"], 0)
        self.assertEqual(rollout["publication-pom-verification"]["failures"], 0)
        self.assertEqual(rollout["remote-immutable-ref-verification"], "verified")

    def test_active_authority_rollout_links_current_evidence(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        authority = json.loads(AUTHORITY_LEDGER.read_text(encoding="utf-8"))
        rollout = next(
            item
            for item in document["subsequent-rollouts"]
            if item["rollout"] == authority["rollout"]
        )

        self.assertEqual(rollout["status"], authority["status"])
        immutable_path_prefix = f"config/rollouts/{authority['rollout']}/"
        self.assertTrue(rollout["authority-delta-ledger"].startswith(immutable_path_prefix))
        if authority["status"] == "validation-pending":
            pending_path = f"{immutable_path_prefix}latest-stable-version-deltas.json"
            revised_path = f"{immutable_path_prefix}candidate-"
            self.assertTrue(
                rollout["authority-delta-ledger"] == pending_path
                or revised_path in rollout["authority-delta-ledger"]
            )
        else:
            self.assertIn("/resolved-graph-", rollout["authority-delta-ledger"])
        self.assertEqual(
            rollout["catalog-sha256"], authority["candidate"]["catalog-sha256"]
        )
        self.assertEqual(
            rollout["baseline-catalog-ref"], authority["baseline"]["catalog-ref"]
        )
        snapshot_ledger = json.loads(
            (REPO_ROOT / rollout["authority-delta-ledger"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(snapshot_ledger["rollout"], authority["rollout"])
        self.assertEqual(snapshot_ledger["delta"], authority["delta"])
        self.assertEqual(snapshot_ledger["audit"]["path"], rollout["audit"])
        self.assertEqual(snapshot_ledger["audit"]["sha256"], rollout["audit-sha256"])
        self.assertTrue(rollout["audit"].startswith("config/rollouts/"))
        self.assertEqual(
            hashlib.sha256((REPO_ROOT / rollout["audit"]).read_bytes()).hexdigest(),
            rollout["audit-sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (REPO_ROOT / rollout["authority-delta-ledger"]).read_bytes()
            ).hexdigest(),
            rollout["authority-delta-ledger-sha256"],
        )
        self.assertEqual(rollout["delta-count"], len(authority["delta"]))
        if authority["status"] == "verified-resolved-graph":
            self.assertEqual(
                rollout["resolved-graph-evidence"]["spec-count"],
                authority["resolved-graph-evidence"]["spec-count"],
            )
        else:
            self.assertEqual(rollout["resolved-graph-evidence"], [])
        validation = authority.get("candidate-validation-evidence")
        if validation is None:
            self.assertEqual(rollout["downstream-full-builds"]["status"], "pending")
            self.assertEqual(
                rollout["publication-pom-verification"]["status"], "pending"
            )
            self.assertEqual(
                rollout["remote-immutable-ref-verification"],
                "pending-candidate-commit-and-push",
            )
        else:
            self.assertEqual(
                rollout["downstream-full-builds"]["status"],
                validation["downstream-full-builds"]["status"],
            )
            self.assertEqual(
                rollout["downstream-full-builds"]["evidence"]["sha256"],
                validation["downstream-full-builds"]["evidence"]["sha256"],
            )
            self.assertEqual(
                rollout["publication-pom-verification"]["status"],
                validation["publication-poms"]["status"],
            )
            self.assertEqual(
                rollout["publication-pom-verification"]["failures"], 0
            )
            self.assertEqual(
                rollout["remote-immutable-ref-verification"],
                validation["remote-immutable-ref-verification"],
            )

    def test_issue_1832_resolved_graph_evidence_sha256_matches_receipt(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        rollout = next(
            item
            for item in document["subsequent-rollouts"]
            if item["rollout"] == "2026-10-18-issue-1832-amqp-client-catalog"
        )
        evidence = rollout["resolved-graph-evidence"]
        receipt = REPO_ROOT / evidence["path"]

        self.assertEqual(
            hashlib.sha256(receipt.read_bytes()).hexdigest(), evidence["sha256"]
        )
        self.assertTrue(evidence["path"].startswith("config/rollouts/"))
        self.assertTrue(rollout["audit"].startswith("config/rollouts/"))
        self.assertTrue(rollout["authority-delta-ledger"].startswith("config/rollouts/"))
        self.assertEqual(
            hashlib.sha256((REPO_ROOT / rollout["audit"]).read_bytes()).hexdigest(),
            rollout["audit-sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (REPO_ROOT / rollout["authority-delta-ledger"]).read_bytes()
            ).hexdigest(),
            rollout["authority-delta-ledger-sha256"],
        )

    def test_every_verified_rollout_points_to_immutable_snapshots(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        for rollout in document["subsequent-rollouts"]:
            if rollout.get("status") != "verified-resolved-graph":
                continue
            with self.subTest(rollout=rollout["rollout"]):
                prefix = f"config/rollouts/{rollout['rollout']}/"
                self.assertTrue(rollout["audit"].startswith(prefix))
                self.assertTrue(rollout["authority-delta-ledger"].startswith(prefix))
                self.assertTrue(
                    rollout["resolved-graph-evidence"]["path"].startswith(prefix)
                )
                for key in ("audit-sha256", "authority-delta-ledger-sha256"):
                    self.assertRegex(rollout[key], r"^[0-9a-f]{64}$")
                self.assertRegex(
                    rollout["resolved-graph-evidence"]["sha256"],
                    r"^[0-9a-f]{64}$",
                )

    def test_compatibility_lines_are_not_issue_168_adoption_deltas(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        coordinates = {(delta["repository"], delta["coordinate"]) for delta in document["delta"]}

        self.assertTrue(
            coordinates.isdisjoint(
                {
                    ("bluetape4k-projects", "org.apache.kafka:kafka-clients"),
                    ("bluetape4k-projects", "org.apache.ignite:ignite-core"),
                    ("bluetape4k-projects", "org.springframework.kafka:spring-kafka"),
                    ("bluetape4k-leader", "org.springframework.boot:spring-boot-dependencies"),
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
