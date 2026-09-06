#!/usr/bin/env python3
"""Synchronize the canonical publishing-signing helper to managed worktrees.

The generated helper is deliberately copied as one byte-identical artifact.
Repository selection and repository-map validation are fail-closed, and a
multi-target write is rolled back if any replacement or read-back fails.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import io
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import IO, Iterable, List, Optional, Sequence, Tuple


CANDIDATE_PATH = Path(__file__).resolve().with_name("catalog_candidate.py")
CANDIDATE_SPEC = importlib.util.spec_from_file_location(
    "catalog_candidate", CANDIDATE_PATH
)
if CANDIDATE_SPEC is None or CANDIDATE_SPEC.loader is None:
    raise RuntimeError("cannot load catalog_candidate.py")
catalog_candidate = importlib.util.module_from_spec(CANDIDATE_SPEC)
sys.modules.setdefault("catalog_candidate", catalog_candidate)
CANDIDATE_SPEC.loader.exec_module(catalog_candidate)


SOURCE_RELATIVE = Path("config/publishing-signing/PublishingSigningKeySupport.kt")
TARGET_RELATIVE = Path(
    "buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt"
)
SIGNING_REPOSITORIES = (
    "bluetape4k-dependencies",
    "bluetape4k-projects",
    "bluetape4k-aws",
    "bluetape4k-exposed",
    "bluetape4k-graph",
    "bluetape4k-image",
    "bluetape4k-javers",
    "bluetape4k-leader",
    "bluetape4k-text",
)
SAFE_NEW_FILE_MODE = 0o644
TEMP_FILE_MODE = 0o600
GENERATED_HEADER = (
    "// GENERATED FILE - DO NOT EDIT.\n"
    "// Source: config/publishing-signing/PublishingSigningKeySupport.kt\n"
    "// Synchronize with: python3 scripts/sync-publishing-signing-support.py"
    " --write --check\n\n"
)


class SyncError(RuntimeError):
    """Raised when the fail-closed sync contract cannot be satisfied."""


@dataclasses.dataclass
class TargetState:
    repository: str
    root: Path
    path: Path
    desired: bytes
    prior_exists: bool
    prior_bytes: Optional[bytes]
    prior_mode: int
    current_digest: str
    desired_digest: str


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render_generated_content(canonical: bytes) -> bytes:
    """Render one deterministic byte sequence for every managed repository."""
    return GENERATED_HEADER.encode("utf-8") + canonical


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _lstat(path: Path, description: str) -> os.stat_result:
    try:
        return path.lstat()
    except FileNotFoundError as exc:
        raise SyncError(f"{description} is missing: {path}") from exc
    except OSError as exc:
        raise SyncError(f"cannot inspect {description}: {path}") from exc


def _require_directory(path: Path, description: str) -> None:
    mode = _lstat(path, description).st_mode
    if stat.S_ISLNK(mode):
        raise SyncError(f"{description} must not be a symlink: {path}")
    if not stat.S_ISDIR(mode):
        raise SyncError(f"{description} must be a directory: {path}")


def _require_regular_file(path: Path, description: str) -> None:
    mode = _lstat(path, description).st_mode
    if stat.S_ISLNK(mode):
        raise SyncError(f"{description} must not be a symlink: {path}")
    if not stat.S_ISREG(mode):
        raise SyncError(f"{description} must be a regular file: {path}")


def _require_no_symlink_components(path: Path, root: Path, description: str) -> None:
    """Reject symlinks in an existing path from root through its parent."""
    if not path.is_absolute() or not root.is_absolute():
        raise SyncError(f"{description} must use absolute paths")
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise SyncError(f"{description} escapes repository root: {path}") from exc

    current = root
    _require_directory(current, "repository root")
    for component in relative.parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            # A missing final target is permitted; all parents must already
            # exist and are checked on the next iteration if present.
            break
        except OSError as exc:
            raise SyncError(f"cannot inspect {description}: {current}") from exc
        if stat.S_ISLNK(mode):
            raise SyncError(f"{description} must not contain symlinks: {current}")


def _validate_repository_root(repository: object, workspace: Path) -> Path:
    root = getattr(repository, "root", None)
    name = getattr(repository, "name", "repository")
    if not isinstance(root, Path) or not root.is_absolute():
        raise SyncError(f"repository root must be absolute for {name}")
    if root.resolve() != root:
        raise SyncError(f"repository root must be canonical for {name}: {root}")
    workspace_root = workspace.resolve()
    if not _is_relative_to(root, workspace_root):
        raise SyncError(f"repository root escapes workspace for {name}: {root}")
    _require_directory(root, f"repository root for {name}")
    return root


def _select_repositories(
    repositories: Sequence[object], names: Optional[Sequence[str]]
) -> Tuple[object, ...]:
    by_name = {getattr(repository, "name", ""): repository for repository in repositories}
    missing = [name for name in SIGNING_REPOSITORIES if name not in by_name]
    if missing:
        raise SyncError(
            "repository map is missing signing repositories: " + ", ".join(missing)
        )
    if names is None:
        selected_names = list(SIGNING_REPOSITORIES)
    else:
        selected_names = list(names)
        unknown = [name for name in selected_names if name not in SIGNING_REPOSITORIES]
        if unknown:
            raise SyncError("unknown repository: " + ", ".join(unknown))
        if len(set(selected_names)) != len(selected_names):
            raise SyncError("repository selection contains duplicates")
    return tuple(by_name[name] for name in selected_names)


def _read_target_state(
    repository: object, desired: bytes, workspace: Path
) -> TargetState:
    name = getattr(repository, "name", "repository")
    root = _validate_repository_root(repository, workspace)
    target = root / TARGET_RELATIVE
    if target.resolve(strict=False) != target:
        raise SyncError(f"target path must be canonical for {name}: {target}")
    _require_no_symlink_components(target.parent, root, f"target parent for {name}")
    _require_directory(target.parent, f"target parent for {name}")

    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return TargetState(
            repository=name,
            root=root,
            path=target,
            desired=desired,
            prior_exists=False,
            prior_bytes=None,
            prior_mode=SAFE_NEW_FILE_MODE,
            current_digest=sha256_bytes(b""),
            desired_digest=sha256_bytes(desired),
        )
    except OSError as exc:
        raise SyncError(f"cannot inspect generated target for {name}: {target}") from exc

    if stat.S_ISLNK(metadata.st_mode):
        raise SyncError(f"generated target must not be a symlink for {name}: {target}")
    if not stat.S_ISREG(metadata.st_mode):
        raise SyncError(f"generated target must be a regular file for {name}: {target}")
    try:
        current = target.read_bytes()
    except OSError as exc:
        raise SyncError(f"cannot read generated target for {name}: {target}") from exc
    return TargetState(
        repository=name,
        root=root,
        path=target,
        desired=desired,
        prior_exists=True,
        prior_bytes=current,
        prior_mode=stat.S_IMODE(metadata.st_mode),
        current_digest=sha256_bytes(current),
        desired_digest=sha256_bytes(desired),
    )


def _snapshot_source(repositories: Sequence[object], workspace: Path) -> bytes:
    central = next(
        (repository for repository in repositories if getattr(repository, "name", "") == "bluetape4k-dependencies"),
        None,
    )
    if central is None:
        raise SyncError("repository map is missing central dependencies repository")
    root = _validate_repository_root(central, workspace)
    source = root / SOURCE_RELATIVE
    if source.resolve(strict=False) != source:
        raise SyncError(f"canonical source path must be canonical: {source}")
    _require_no_symlink_components(source.parent, root, "canonical source parent")
    _require_regular_file(source, "canonical source")
    try:
        return source.read_bytes()
    except OSError as exc:
        raise SyncError(f"cannot read canonical source: {source}") from exc


def _assert_unchanged(state: TargetState) -> None:
    try:
        metadata = state.path.lstat()
    except FileNotFoundError:
        if state.prior_exists:
            raise SyncError(f"target changed during sync: {state.path}")
        return
    except OSError as exc:
        raise SyncError(f"cannot recheck target before replacement: {state.path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise SyncError(f"target changed to a non-regular file: {state.path}")
    current = state.path.read_bytes()
    if (
        not state.prior_exists
        or current != state.prior_bytes
        or stat.S_IMODE(metadata.st_mode) != state.prior_mode
    ):
        raise SyncError(f"target changed during sync: {state.path}")


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _stage_file(directory: Path, payload: bytes, mode: int) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix=".PublishingSigningKeySupport.kt.", suffix=".tmp", dir=str(directory)
    )
    path = Path(raw_path)
    try:
        os.fchmod(descriptor, TEMP_FILE_MODE)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, mode)
        descriptor = -1
        descriptor = os.open(str(path), os.O_RDONLY)
        os.fsync(descriptor)
        return path
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _remove_staged(staged: Iterable[Path]) -> None:
    for path in staged:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _replace_and_read_back(state: TargetState, staged: Path) -> None:
    _require_no_symlink_components(
        state.path.parent, state.root, f"target parent for {state.repository}"
    )
    _assert_unchanged(state)
    os.replace(str(staged), str(state.path))
    _fsync_directory(state.path.parent)
    _require_regular_file(state.path, f"generated target for {state.repository}")
    metadata = state.path.stat()
    current = state.path.read_bytes()
    if current != state.desired or stat.S_IMODE(metadata.st_mode) != state.prior_mode:
        raise SyncError(f"replacement read-back mismatch: {state.path}")


def _restore_state(state: TargetState) -> None:
    _require_directory(state.path.parent, "target parent")
    if state.prior_exists:
        restore = _stage_file(state.path.parent, state.prior_bytes or b"", state.prior_mode)
        try:
            os.replace(str(restore), str(state.path))
            _fsync_directory(state.path.parent)
        finally:
            _remove_staged((restore,))
    else:
        try:
            metadata = state.path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise SyncError(f"cannot safely remove replacement: {state.path}")
        state.path.unlink()
        _fsync_directory(state.path.parent)


def _write_all(states: Sequence[TargetState]) -> None:
    staged: List[Tuple[TargetState, Path]] = []
    replaced: List[TargetState] = []
    try:
        for state in states:
            _require_no_symlink_components(
                state.path.parent, state.root, f"target parent for {state.repository}"
            )
            staged.append(
                (state, _stage_file(state.path.parent, state.desired, state.prior_mode))
            )
        for state, staged_path in staged:
            # Record the target before replacement so a post-replace read-back
            # failure is covered by the same rollback transaction.
            replaced.append(state)
            _replace_and_read_back(state, staged_path)
    except BaseException as exc:
        _remove_staged(path for _, path in staged)
        rollback_errors = []
        for state in reversed(replaced):
            try:
                _restore_state(state)
            except BaseException as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        detail = str(exc)
        if rollback_errors:
            detail += "; rollback failed: " + " | ".join(rollback_errors)
        raise SyncError(detail) from exc
    finally:
        _remove_staged(path for _, path in staged)


def _emit_summary(
    states: Sequence[TargetState], output: IO[str], status: str
) -> None:
    for state in states:
        output.write(
            "repository={repository} path={path} digest={digest} status={status}\n".format(
                repository=state.repository,
                path=state.path,
                digest=state.desired_digest,
                status=status,
            )
        )


def synchronize(
    workspace: Path,
    repository_map: Path,
    repository_names: Optional[Sequence[str]],
    write: bool,
    check: bool,
    summary: bool,
    output: Optional[IO[str]] = None,
) -> List[dict]:
    """Validate or synchronize selected generated helpers."""
    if not write and not check:
        raise SyncError("at least one of --write or --check is required")
    workspace = workspace.resolve()
    repository_map = repository_map.resolve()
    try:
        repositories = catalog_candidate.load_repository_map_v1(
            repository_map, workspace
        )
    except Exception as exc:
        if isinstance(exc, SyncError):
            raise
        raise SyncError(str(exc)) from exc
    selected = _select_repositories(repositories, repository_names)
    canonical = _snapshot_source(repositories, workspace)
    desired = render_generated_content(canonical)
    states = tuple(
        _read_target_state(repository, desired, workspace) for repository in selected
    )
    output = output or sys.stdout

    if write:
        _write_all(states)
        drifted = []
    else:
        drifted = [
            state
            for state in states
            if not state.prior_exists or state.prior_bytes != desired
        ]
    if drifted:
        if summary:
            _emit_summary(states, output, "drift")
        names = ", ".join(state.repository for state in drifted)
        raise SyncError("content drift for: " + names)
    if summary:
        _emit_summary(states, output, "ok")
    return [
        {
            "repository": state.repository,
            "path": str(state.path),
            "digest": state.desired_digest,
            "status": "ok",
        }
        for state in states
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository-map", type=Path, required=True)
    parser.add_argument("--repo", dest="repositories", action="append")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        synchronize(
            workspace=arguments.workspace,
            repository_map=arguments.repository_map,
            repository_names=arguments.repositories,
            write=arguments.write,
            check=arguments.check,
            summary=arguments.summary,
        )
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
