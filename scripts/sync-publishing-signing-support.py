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
import os
import secrets
import stat
import sys
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


@dataclasses.dataclass(frozen=True)
class FileSnapshot:
    payload: bytes
    mode: int


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


def _directory_open_flags() -> int:
    try:
        return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    except AttributeError as exc:
        raise SyncError("platform lacks O_DIRECTORY/O_NOFOLLOW support") from exc


def _regular_open_flags() -> int:
    try:
        return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    except AttributeError as exc:
        raise SyncError("platform lacks O_NOFOLLOW support") from exc


def _open_directory_fd(path: Path, root: Path) -> int:
    """Open every directory component with O_DIRECTORY|O_NOFOLLOW.

    The returned descriptor remains anchored to the checked directory even if
    an attacker replaces a path component after this function returns.
    """
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise SyncError(f"directory escapes repository root: {path}") from exc

    flags = _directory_open_flags()
    descriptor: Optional[int] = None
    try:
        descriptor = os.open(str(root), flags)
        for component in relative.parts:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            try:
                os.close(descriptor)
            except BaseException:
                try:
                    os.close(next_descriptor)
                except BaseException:
                    pass
                raise
            descriptor = next_descriptor
        assert descriptor is not None
        return descriptor
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except BaseException:
                pass
        if isinstance(exc, SyncError):
            raise
        raise SyncError(f"cannot open directory without following symlinks: {path}") from exc


def _read_fd(descriptor: int) -> bytes:
    chunks = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_regular_at(
    parent_fd: int, name: str, description: str
) -> Optional[FileSnapshot]:
    """Read a regular file through a no-follow directory descriptor."""
    try:
        metadata = os.lstat(name, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SyncError(f"cannot inspect {description}: {name}") from exc

    if stat.S_ISLNK(metadata.st_mode):
        raise SyncError(f"{description} must not be a symlink: {name}")
    if not stat.S_ISREG(metadata.st_mode):
        raise SyncError(f"{description} must be a regular file: {name}")

    descriptor: Optional[int] = None
    snapshot: Optional[FileSnapshot] = None
    primary: Optional[BaseException] = None
    try:
        descriptor = os.open(name, _regular_open_flags(), dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        if stat.S_ISLNK(opened.st_mode) or not stat.S_ISREG(opened.st_mode):
            raise SyncError(f"{description} changed to a non-regular file: {name}")
        snapshot = FileSnapshot(_read_fd(descriptor), stat.S_IMODE(opened.st_mode))
    except SyncError as exc:
        primary = exc
    except OSError as exc:
        primary = SyncError(f"cannot read {description}: {name}")
        primary.__cause__ = exc
    if descriptor is not None:
        close_result = _close_fd_preserving(descriptor, primary)
        if close_result is not None:
            if isinstance(close_result, SyncError):
                raise close_result
            raise close_result
    if primary is not None:
        raise primary
    if snapshot is None:
        raise SyncError(f"cannot read {description}: {name}")
    return snapshot


def _close_fd_preserving(descriptor: int, primary: Optional[BaseException]) -> Optional[BaseException]:
    try:
        os.close(descriptor)
    except BaseException as close_error:
        return primary if primary is not None else close_error
    return primary


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
    parent_fd = _open_directory_fd(target.parent, root)
    snapshot: Optional[FileSnapshot] = None
    primary: Optional[BaseException] = None
    try:
        snapshot = _read_regular_at(
            parent_fd,
            TARGET_RELATIVE.name,
            f"generated target for {name}",
        )
    except BaseException as exc:
        primary = exc
    close_result = _close_fd_preserving(parent_fd, primary)
    if close_result is not None:
        raise close_result

    if snapshot is None:
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
    return TargetState(
        repository=name,
        root=root,
        path=target,
        desired=desired,
        prior_exists=True,
        prior_bytes=snapshot.payload,
        prior_mode=snapshot.mode,
        current_digest=sha256_bytes(snapshot.payload),
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
    _require_directory(source.parent, "canonical source parent")
    parent_fd = _open_directory_fd(source.parent, root)
    snapshot: Optional[FileSnapshot] = None
    primary: Optional[BaseException] = None
    try:
        snapshot = _read_regular_at(parent_fd, source.name, "canonical source")
    except BaseException as exc:
        primary = exc
    close_result = _close_fd_preserving(parent_fd, primary)
    if close_result is not None:
        raise close_result
    if snapshot is None:
        raise SyncError(f"canonical source is missing: {source}")
    return snapshot.payload


def _assert_unchanged(state: TargetState, parent_fd: int) -> None:
    snapshot = _read_regular_at(
        parent_fd,
        TARGET_RELATIVE.name,
        f"generated target for {state.repository}",
    )
    if snapshot is None:
        if state.prior_exists:
            raise SyncError(f"target changed during sync: {state.path}")
        return
    if (
        not state.prior_exists
        or snapshot.payload != state.prior_bytes
        or snapshot.mode != state.prior_mode
    ):
        raise SyncError(f"target changed during sync: {state.path}")


def _fsync_directory(parent_fd: int) -> None:
    try:
        os.fsync(parent_fd)
    except OSError as exc:
        raise SyncError("cannot fsync target directory") from exc


def _write_all_fd(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short write while staging generated helper")
        offset += written


def _stage_file(parent_fd: int, payload: bytes, mode: int) -> str:
    """Create and fsync a staged file using only its open directory FD."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    staged_name: Optional[str] = None
    descriptor: Optional[int] = None
    for _ in range(32):
        candidate = ".PublishingSigningKeySupport.kt." + secrets.token_hex(12) + ".tmp"
        try:
            descriptor = os.open(candidate, flags, TEMP_FILE_MODE, dir_fd=parent_fd)
            staged_name = candidate
            break
        except FileExistsError:
            continue
        except OSError as exc:
            raise SyncError("cannot create staged generated helper") from exc
    if descriptor is None or staged_name is None:
        raise SyncError("cannot allocate unique staged generated helper")

    primary: Optional[BaseException] = None
    try:
        os.fchmod(descriptor, TEMP_FILE_MODE)
        _write_all_fd(descriptor, payload)
        os.fsync(descriptor)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
    except BaseException as exc:
        primary = exc

    close_result = _close_fd_preserving(descriptor, primary)
    descriptor = None
    if close_result is None:
        return staged_name

    try:
        os.unlink(staged_name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass
    except BaseException as cleanup_error:
        # Preserve the primary staging/close error; cleanup failure is only
        # surfaced when there was no earlier error to report.
        if primary is None:
            close_result = cleanup_error

    if isinstance(close_result, SyncError):
        raise close_result
    raise close_result


def _remove_staged(staged: Iterable[Tuple[int, str]]) -> None:
    for parent_fd, name in staged:
        try:
            os.unlink(name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _replace_and_read_back(
    state: TargetState, parent_fd: int, staged_name: str
) -> None:
    _assert_unchanged(state, parent_fd)
    os.replace(
        staged_name,
        TARGET_RELATIVE.name,
        src_dir_fd=parent_fd,
        dst_dir_fd=parent_fd,
    )
    _fsync_directory(parent_fd)
    snapshot = _read_regular_at(
        parent_fd,
        TARGET_RELATIVE.name,
        f"generated target for {state.repository}",
    )
    if snapshot is None or snapshot.payload != state.desired or snapshot.mode != state.prior_mode:
        raise SyncError(f"replacement read-back mismatch: {state.path}")


def _restore_state(state: TargetState, parent_fd: int) -> None:
    if state.prior_exists:
        restore_name = _stage_file(
            parent_fd, state.prior_bytes or b"", state.prior_mode
        )
        try:
            os.replace(
                restore_name,
                TARGET_RELATIVE.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            _fsync_directory(parent_fd)
            restored = _read_regular_at(
                parent_fd,
                TARGET_RELATIVE.name,
                f"rollback target for {state.repository}",
            )
            if (
                restored is None
                or restored.payload != (state.prior_bytes or b"")
                or restored.mode != state.prior_mode
            ):
                raise SyncError(f"rollback read-back mismatch: {state.path}")
        finally:
            _remove_staged(((parent_fd, restore_name),))
    else:
        snapshot = _read_regular_at(
            parent_fd,
            TARGET_RELATIVE.name,
            f"generated target for {state.repository}",
        )
        if snapshot is None:
            return
        os.unlink(TARGET_RELATIVE.name, dir_fd=parent_fd)
        _fsync_directory(parent_fd)
        if (
            _read_regular_at(
                parent_fd,
                TARGET_RELATIVE.name,
                f"rollback target for {state.repository}",
            )
            is not None
        ):
            raise SyncError(f"rollback read-back mismatch: {state.path}")


def _write_all(states: Sequence[TargetState]) -> None:
    parent_fds: List[Tuple[TargetState, int]] = []
    staged: List[Tuple[TargetState, int, str]] = []
    replaced: List[TargetState] = []
    try:
        # Open and anchor every target directory before creating any staged
        # file.  All later checks and replacements use these descriptors.
        for state in states:
            _require_no_symlink_components(
                state.path.parent, state.root, f"target parent for {state.repository}"
            )
            parent_fd = _open_directory_fd(state.path.parent, state.root)
            parent_fds.append((state, parent_fd))
            _assert_unchanged(state, parent_fd)
        for state, parent_fd in parent_fds:
            staged_name = _stage_file(parent_fd, state.desired, state.prior_mode)
            staged.append((state, parent_fd, staged_name))
        for state, parent_fd, staged_name in staged:
            # Record the target before replacement so a post-replace read-back
            # failure is covered by the same rollback transaction.
            replaced.append(state)
            _replace_and_read_back(state, parent_fd, staged_name)
    except BaseException as exc:
        _remove_staged((parent_fd, name) for _, parent_fd, name in staged)
        rollback_errors = []
        fd_by_name = {state.repository: parent_fd for state, parent_fd in parent_fds}
        for state in reversed(replaced):
            try:
                _restore_state(state, fd_by_name[state.repository])
            except BaseException as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        detail = str(exc)
        if rollback_errors:
            detail += "; rollback failed: " + " | ".join(rollback_errors)
        raise SyncError(detail) from exc
    finally:
        _remove_staged((parent_fd, name) for _, parent_fd, name in staged)
        for _, parent_fd in reversed(parent_fds):
            try:
                os.close(parent_fd)
            except OSError:
                pass


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
