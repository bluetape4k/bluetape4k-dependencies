from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import List, Optional, Tuple
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "sync-publishing-signing-support.py"
)
SPEC = importlib.util.spec_from_file_location(
    "sync_publishing_signing_support", SCRIPT_PATH
)
assert SPEC is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_publishing_signing_support"] = sync
assert SPEC.loader is not None
SPEC.loader.exec_module(sync)


class SyncPublishingSigningSupportTest(unittest.TestCase):
    def test_repository_inventory_reuses_catalog_candidate_authority(self) -> None:
        self.assertEqual(
            sync.SIGNING_REPOSITORIES,
            sync.catalog_candidate.SIGNING_REPOSITORIES,
        )

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.workspace = Path(self.temp_dir.name).resolve()
        self.central = self.workspace / "bluetape4k-dependencies"
        self.source = (
            self.central
            / "config"
            / "publishing-signing"
            / "PublishingSigningKeySupport.kt"
        )
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"package example\n\nfun signing() = Unit\n")
        self.repository_map = self.workspace / "repository-map.json"
        self.repository_map.write_text("{}\n", encoding="utf-8")

        repository_names = (
            "bluetape4k-dependencies",
            "bluetape4k-projects",
            "bluetape4k-aws",
            "bluetape4k-experimental",
            "bluetape4k-exposed",
            "bluetape4k-graph",
            "bluetape4k-image",
            "bluetape4k-javers",
            "bluetape4k-leader",
            "bluetape4k-text",
        )
        self.repositories = []
        for index, name in enumerate(repository_names):
            root = self.central if index == 0 else self.workspace / name
            root.mkdir(parents=True, exist_ok=True)
            (root / "buildSrc" / "src" / "main" / "kotlin").mkdir(parents=True)
            key = "central" if index == 0 else name.removeprefix("bluetape4k-")
            self.repositories.append(
                sync.catalog_candidate.CandidateRepository(
                    key=key,
                    name=name,
                    root=root,
                    catalog=root / "gradle" / "libs.versions.toml",
                    origin=f"git@github.com:bluetape4k/{name}.git",
                    branch="feat/test",
                    base_sha="a" * 40,
                    expected_head="b" * 40,
                )
            )
        self.repositories = tuple(self.repositories)

        self.target_paths = {
            repository.name: repository.root
            / "buildSrc"
            / "src"
            / "main"
            / "kotlin"
            / "PublishingSigningKeySupport.kt"
            for repository in self.repositories
            if repository.name in sync.SIGNING_REPOSITORIES
        }
        self.generated = sync.render_generated_content(self.source.read_bytes())

    def _load_map(self):
        return mock.patch.object(
            sync.catalog_candidate,
            "load_repository_map_v1",
            return_value=self.repositories,
        )

    def _write_targets(self, payload: Optional[bytes] = None) -> None:
        value = self.generated if payload is None else payload
        for target in self.target_paths.values():
            target.write_bytes(value)
            target.chmod(0o640)

    def _sync(
        self,
        *,
        repositories: Optional[List[str]] = None,
        write: bool = False,
        check: bool = True,
    ) -> Tuple[List[dict], str]:
        output = io.StringIO()
        with self._load_map():
            result = sync.synchronize(
                workspace=self.workspace,
                repository_map=self.repository_map,
                repository_names=repositories,
                write=write,
                check=check,
                summary=True,
                output=output,
            )
        return result, output.getvalue()

    def test_check_accepts_byte_identical_generated_files(self) -> None:
        self._write_targets()

        result, summary = self._sync()

        self.assertEqual(len(result), len(self.target_paths))
        self.assertTrue(all(item["status"] == "ok" for item in result))
        self.assertIn("status=ok", summary)
        self.assertNotIn("package example", summary)

    def test_check_reports_content_drift(self) -> None:
        self._write_targets()
        drifted = self.target_paths["bluetape4k-aws"]
        drifted.write_bytes(b"drift\n")

        with self.assertRaises(sync.SyncError) as raised:
            self._sync()

        self.assertIn("bluetape4k-aws", str(raised.exception))
        self.assertIn("content drift", str(raised.exception))

    def test_write_repairs_all_targets_atomically(self) -> None:
        self._write_targets(payload=b"stale\n")
        modes = {path: path.stat().st_mode & 0o777 for path in self.target_paths.values()}

        result, _ = self._sync(write=True)

        self.assertEqual(len(result), len(self.target_paths))
        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), self.generated, name)
            self.assertEqual(target.stat().st_mode & 0o777, modes[target], name)

    def test_preflight_failure_writes_nothing(self) -> None:
        self._write_targets(payload=b"stale\n")
        first_name = next(iter(self.target_paths))
        first_target = self.target_paths[first_name]
        outside = self.workspace / "outside-signing.kt"
        outside.write_bytes(b"outside\n")
        first_target.unlink()
        first_target.symlink_to(outside)

        with self.assertRaises(sync.SyncError):
            self._sync(write=True)

        self.assertTrue(first_target.is_symlink())
        self.assertEqual(outside.read_bytes(), b"outside\n")
        for name, target in self.target_paths.items():
            if name != first_name:
                self.assertEqual(target.read_bytes(), b"stale\n", name)

    def test_replace_failure_rolls_back_previous_targets(self) -> None:
        self._write_targets(payload=b"stale\n")
        original_replace = sync.os.replace
        replace_count = 0

        def fail_on_second_replace(
            source: str | os.PathLike[str],
            target: str | os.PathLike[str],
            **kwargs,
        ):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("injected replace failure")
            return original_replace(source, target, **kwargs)

        with mock.patch.object(sync.os, "replace", side_effect=fail_on_second_replace):
            with self.assertRaises(sync.SyncError):
                self._sync(write=True)

        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)
        self.assertEqual(list(self.central.glob(".PublishingSigningKeySupport.kt.*")), [])

    def test_rejects_symlink_and_path_escape(self) -> None:
        self._write_targets()
        symlink_target = self.target_paths["bluetape4k-projects"]
        outside = self.workspace / "outside.kt"
        outside.write_bytes(self.generated)
        symlink_target.unlink()
        symlink_target.symlink_to(outside)

        with self.assertRaises(sync.SyncError):
            self._sync()

        escaped = self.workspace.parent / (self.workspace.name + "-escaped-repository")
        escaped.mkdir()
        self.addCleanup(lambda: escaped.rmdir())
        escaped_repo = replace(
            next(
                repository
                for repository in self.repositories
                if repository.name == "bluetape4k-aws"
            ),
            root=escaped,
        )
        repositories = tuple(
            escaped_repo if repository.name == escaped_repo.name else repository
            for repository in self.repositories
        )
        with mock.patch.object(
            sync.catalog_candidate,
            "load_repository_map_v1",
            return_value=repositories,
        ):
            with self.assertRaises(sync.SyncError):
                sync.synchronize(
                    workspace=self.workspace,
                    repository_map=self.repository_map,
                    repository_names=None,
                    write=False,
                    check=True,
                    summary=False,
                    output=io.StringIO(),
                )

    def test_repo_limits_work_to_allowlisted_target(self) -> None:
        self._write_targets(payload=b"stale\n")

        self._sync(repositories=["bluetape4k-projects"], write=True)

        self.assertEqual(
            self.target_paths["bluetape4k-projects"].read_bytes(), self.generated
        )
        for name, target in self.target_paths.items():
            if name != "bluetape4k-projects":
                self.assertEqual(target.read_bytes(), b"stale\n", name)

    def test_rejects_unknown_repository(self) -> None:
        self._write_targets(payload=b"stale\n")

        with self.assertRaises(sync.SyncError) as raised:
            self._sync(repositories=["clinic-appointment"], write=True)

        self.assertIn("unknown repository", str(raised.exception))
        self.assertTrue(all(path.read_bytes() == b"stale\n" for path in self.target_paths.values()))

    def test_strict_repository_map_loader_boundary_is_preserved(self) -> None:
        self._write_targets()
        with mock.patch.object(
            sync.catalog_candidate,
            "load_repository_map_v1",
            return_value=self.repositories,
        ) as loader:
            sync.synchronize(
                workspace=self.workspace,
                repository_map=self.repository_map,
                repository_names=["bluetape4k-projects"],
                write=False,
                check=True,
                summary=False,
                output=io.StringIO(),
            )

        self.assertEqual(loader.call_count, 2)
        for call in loader.call_args_list:
            self.assertEqual(call.args, (self.repository_map, self.workspace))

    def test_experimental_target_is_not_modified(self) -> None:
        self._write_targets(payload=b"stale\n")
        experimental = next(
            repository
            for repository in self.repositories
            if repository.name == "bluetape4k-experimental"
        )
        experimental_target = (
            experimental.root
            / "buildSrc"
            / "src"
            / "main"
            / "kotlin"
            / "PublishingSigningKeySupport.kt"
        )
        experimental_target.write_bytes(b"experimental-sentinel\n")

        self._sync(write=True)

        self.assertEqual(experimental_target.read_bytes(), b"experimental-sentinel\n")

    def test_read_back_mismatch_rolls_back_replaced_targets(self) -> None:
        self._write_targets(payload=b"stale\n")
        original_read = sync._read_regular_at
        read_count = 0
        # One source read, target preflight, anchored preflight, then the
        # first replacement's unchanged check and read-back.
        mismatch_at = len(self.target_paths) * 2 + 4

        def mismatch_on_first_read_back(parent_fd, name, description):
            nonlocal read_count
            read_count += 1
            snapshot = original_read(parent_fd, name, description)
            if read_count == mismatch_at and snapshot is not None:
                return sync.FileSnapshot(b"read-back-mismatch\n", snapshot.mode)
            return snapshot

        with mock.patch.object(
            sync, "_read_regular_at", side_effect=mismatch_on_first_read_back
        ):
            with self.assertRaisesRegex(sync.SyncError, "read-back mismatch"):
                self._sync(write=True)

        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)

    def test_rollback_restores_missing_target_and_original_mode(self) -> None:
        self._write_targets(payload=b"stale\n")
        first_name = next(iter(self.target_paths))
        first_target = self.target_paths[first_name]
        first_target.unlink()
        second_name = list(self.target_paths)[1]
        second_target = self.target_paths[second_name]
        second_target.chmod(0o600)

        original_replace = sync.os.replace
        replace_count = 0

        def fail_on_second_replace(source, target, **kwargs):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("injected replace failure")
            return original_replace(source, target, **kwargs)

        with mock.patch.object(sync.os, "replace", side_effect=fail_on_second_replace):
            with self.assertRaises(sync.SyncError):
                self._sync(write=True)

        self.assertFalse(first_target.exists())
        self.assertEqual(second_target.read_bytes(), b"stale\n")
        self.assertEqual(second_target.stat().st_mode & 0o777, 0o600)

    def test_stage_fd_failure_preserves_primary_error_and_cleans_orphan(self) -> None:
        parent = self.central / "buildSrc" / "src" / "main" / "kotlin"
        parent_fd = sync._open_directory_fd(parent, self.central)
        staged_fds = []
        real_close = sync.os.close

        def fail_fchmod(descriptor, mode):
            staged_fds.append(descriptor)
            raise OSError("primary staging failure")

        def fail_close(descriptor):
            if staged_fds and descriptor == staged_fds[0]:
                raise OSError("secondary close failure")
            return real_close(descriptor)

        try:
            with mock.patch.object(sync.os, "fchmod", side_effect=fail_fchmod):
                with mock.patch.object(sync.os, "close", side_effect=fail_close):
                    with self.assertRaisesRegex(OSError, "primary staging failure"):
                        sync._stage_file(parent_fd, b"staged\n", 0o640)
            self.assertEqual(
                list(parent.glob(".PublishingSigningKeySupport.kt.*")), []
            )
        finally:
            if staged_fds:
                real_close(staged_fds[0])
            real_close(parent_fd)

    def test_repository_map_symlink_is_rejected_before_loader_normalization(self) -> None:
        symlink_map = self.workspace / "repository-map-link.json"
        symlink_map.symlink_to(self.repository_map)

        with self.assertRaisesRegex(sync.SyncError, "repository map"):
            sync.synchronize(
                workspace=self.workspace,
                repository_map=symlink_map,
                repository_names=["bluetape4k-projects"],
                write=False,
                check=True,
                summary=False,
                output=io.StringIO(),
            )

    def test_rollback_conflict_does_not_overwrite_external_change(self) -> None:
        self._write_targets(payload=b"stale\n")
        first_target = next(iter(self.target_paths.values()))
        original_fsync = sync._fsync_directory
        fsync_count = 0

        def mutate_after_first_replace(parent_fd):
            nonlocal fsync_count
            fsync_count += 1
            original_fsync(parent_fd)
            if fsync_count == 1:
                first_target.write_bytes(b"external-change\n")
                first_target.chmod(0o600)

        original_replace = sync.os.replace
        replace_count = 0

        def fail_on_second_replace(source, target, **kwargs):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("injected replace failure")
            return original_replace(source, target, **kwargs)

        with mock.patch.object(sync, "_fsync_directory", side_effect=mutate_after_first_replace):
            with mock.patch.object(sync.os, "replace", side_effect=fail_on_second_replace):
                with self.assertRaisesRegex(sync.SyncError, "rollback conflict"):
                    self._sync(write=True)

        self.assertEqual(first_target.read_bytes(), b"external-change\n")
        self.assertEqual(first_target.stat().st_mode & 0o777, 0o600)

    def test_canonical_source_change_before_write_aborts_without_target_writes(self) -> None:
        self._write_targets(payload=b"stale\n")
        original_snapshot = sync._snapshot_source
        snapshot_count = 0

        def change_after_initial_snapshot(repositories, workspace):
            nonlocal snapshot_count
            snapshot_count += 1
            snapshot = original_snapshot(repositories, workspace)
            if snapshot_count == 1:
                self.source.write_bytes(b"changed-before-write\n")
            return snapshot

        with mock.patch.object(
            sync, "_snapshot_source", side_effect=change_after_initial_snapshot
        ):
            with self.assertRaisesRegex(sync.SyncError, "canonical source changed"):
                self._sync(write=True)

        self.assertEqual(snapshot_count, 2)
        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)

    def test_canonical_source_change_during_write_rolls_back_every_target(self) -> None:
        self._write_targets(payload=b"stale\n")
        original_snapshot = sync._snapshot_source
        snapshot_count = 0

        def change_before_postcondition(repositories, workspace):
            nonlocal snapshot_count
            snapshot_count += 1
            if snapshot_count == 3:
                self.source.write_bytes(b"changed-during-write\n")
            return original_snapshot(repositories, workspace)

        with mock.patch.object(
            sync, "_snapshot_source", side_effect=change_before_postcondition
        ):
            with self.assertRaisesRegex(sync.SyncError, "changed during write"):
                self._sync(write=True)

        self.assertEqual(snapshot_count, 3)
        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)

    def test_read_regular_at_closes_fd_on_keyboard_interrupt(self) -> None:
        self._write_targets()
        target = self.target_paths["bluetape4k-dependencies"]
        parent_fd = sync._open_directory_fd(target.parent, self.central)
        close_calls = []
        real_close = sync.os.close

        def observe_close(descriptor):
            close_calls.append(descriptor)
            return real_close(descriptor)

        try:
            with mock.patch.object(
                sync, "_read_fd", side_effect=KeyboardInterrupt()
            ):
                with mock.patch.object(sync.os, "close", side_effect=observe_close):
                    with self.assertRaises(KeyboardInterrupt):
                        sync._read_regular_at(
                            parent_fd,
                            target.name,
                            "generated target",
                        )
            self.assertTrue(close_calls)
        finally:
            real_close(parent_fd)

    def test_repository_head_drift_before_write_aborts_without_target_writes(self) -> None:
        self._write_targets(payload=b"stale\n")
        changed = tuple(
            replace(repository, expected_head="c" * 40)
            if repository.name == "bluetape4k-aws"
            else repository
            for repository in self.repositories
        )
        with mock.patch.object(
            sync.catalog_candidate,
            "load_repository_map_v1",
            side_effect=[self.repositories, changed],
        ) as loader:
            with self.assertRaisesRegex(sync.SyncError, "repository map changed"):
                sync.synchronize(
                    workspace=self.workspace,
                    repository_map=self.repository_map,
                    repository_names=None,
                    write=True,
                    check=True,
                    summary=False,
                    output=io.StringIO(),
                )

        self.assertEqual(loader.call_count, 2)
        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)

    def test_repository_map_digest_drift_before_check_fails_closed(self) -> None:
        self._write_targets()
        calls = 0

        def mutate_map_on_live_load(path, workspace):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.repository_map.write_text("changed-map\n", encoding="utf-8")
            return self.repositories

        with mock.patch.object(
            sync.catalog_candidate,
            "load_repository_map_v1",
            side_effect=mutate_map_on_live_load,
        ):
            with self.assertRaisesRegex(sync.SyncError, "repository map changed"):
                sync.synchronize(
                    workspace=self.workspace,
                    repository_map=self.repository_map,
                    repository_names=None,
                    write=False,
                    check=True,
                    summary=False,
                    output=io.StringIO(),
                )

    def test_replace_interrupt_after_success_rolls_back(self) -> None:
        self._write_targets(payload=b"stale\n")
        original_replace = sync.os.replace
        interrupted = False

        def replace_then_interrupt(source, target, **kwargs):
            nonlocal interrupted
            result = original_replace(source, target, **kwargs)
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            return result

        with mock.patch.object(sync.os, "replace", side_effect=replace_then_interrupt):
            with self.assertRaises(sync.SyncError):
                self._sync(write=True)

        self.assertTrue(interrupted)
        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)

        # A replay after the interrupted transaction must be safe and complete.
        self._sync(write=True)
        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), self.generated, name)

    def test_replace_failure_before_success_is_safe_cas_conflict(self) -> None:
        self._write_targets(payload=b"stale\n")

        def fail_before_replace(source, target, **kwargs):
            raise OSError("injected pre-replace failure")

        with mock.patch.object(sync.os, "replace", side_effect=fail_before_replace):
            with self.assertRaisesRegex(sync.SyncError, "rollback conflict"):
                self._sync(write=True)

        for name, target in self.target_paths.items():
            self.assertEqual(target.read_bytes(), b"stale\n", name)


if __name__ == "__main__":
    unittest.main()
