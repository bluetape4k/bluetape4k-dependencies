"""Read, pin, and promote immutable catalog rollout evidence."""

from __future__ import annotations

import base64
import copy
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
TRANSACTION_SCHEMA_VERSION = 2
TRANSACTION_IDENTITY_SCHEMA_VERSION = 1
TRANSACTION_NEW_FILE_MODE = 0o644
_DIRECTORY_OPEN_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
    os, "O_NOFOLLOW", 0
)
_TARGET_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_DARWIN_RENAME_EXCL = 0x00000004
_LINUX_RENAME_NOREPLACE = 0x00000001
_AT_REMOVEDIR = 0x00000080 if sys.platform == "darwin" else 0x00000200
_MISSING_DESIRED_IDENTITY = object()
LEGACY_VERIFIED_ROLLOUT_STATUS = "verified"


def _fsync_directory_fd(descriptor: int) -> None:
    os.fsync(descriptor)


def _read_descriptor_bytes(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _capture_open_descriptor_state(
    descriptor: int,
) -> tuple[bool, bytes, int | None]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError("catalog rollout transaction target must be a regular file")
    content = _read_descriptor_bytes(descriptor)
    after = os.fstat(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        stat.S_IMODE(before.st_mode),
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        stat.S_IMODE(after.st_mode),
    ):
        raise RuntimeError("catalog rollout transaction target changed during read")
    return True, content, stat.S_IMODE(after.st_mode)


def _capture_transaction_state_at(
    parent_descriptor: int, target_name: str
) -> tuple[bool, bytes, int | None]:
    try:
        descriptor = os.open(
            target_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
    except FileNotFoundError:
        return False, b"", None
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise RuntimeError(
                f"catalog rollout transaction target must be a regular file: {target_name}"
            ) from error
        raise
    try:
        return _capture_open_descriptor_state(descriptor)
    finally:
        os.close(descriptor)


def _capture_transaction_state_and_identity_at(
    parent_descriptor: int, target_name: str
) -> tuple[tuple[bool, bytes, int | None], tuple[int, int] | None]:
    try:
        descriptor = os.open(
            target_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
    except FileNotFoundError:
        return (False, b"", None), None
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise RuntimeError(
                f"catalog rollout transaction target must be a regular file: {target_name}"
            ) from error
        raise
    try:
        state = _capture_open_descriptor_state(descriptor)
        return state, _descriptor_identity(descriptor)
    finally:
        os.close(descriptor)


def _capture_transaction_identity_at(
    parent_descriptor: int, target_name: str
) -> tuple[int, int] | None:
    try:
        descriptor = os.open(
            target_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
    except FileNotFoundError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(
                f"catalog rollout transaction target must be a regular file: {target_name}"
            )
        return _descriptor_identity(descriptor)
    finally:
        os.close(descriptor)


def _capture_directory_identity_at(
    parent_descriptor: int, directory_name: str
) -> tuple[int, int] | None:
    try:
        descriptor = os.open(
            directory_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise RuntimeError(
                f"catalog rollout transaction directory must remain a directory: {directory_name}"
            ) from error
        raise
    try:
        return _descriptor_identity(descriptor)
    finally:
        os.close(descriptor)


def _unlink_private_entry_at(
    parent_descriptor: int,
    entry_name: str,
    expected_identity: tuple[int, int],
    expected_content: bytes,
    expected_mode: int,
) -> None:
    """Remove one already-private inode through an anchored unlinkat call.

    The entry must live in a private directory created by this process.  Keep
    its descriptor open while the syscall runs and validate both the inode and
    content before deletion.  Calling libc directly avoids re-entering the
    monkey-patchable high-level ``os.unlink`` path used by callers and keeps
    the cleanup primitive independent from the public pathname.
    """
    descriptor = os.open(entry_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor)
    try:
        state = _capture_open_descriptor_state(descriptor)
        if (
            _descriptor_identity(descriptor) != expected_identity
            or not _write_state_matches(state, expected_content, expected_mode)
        ):
            raise RuntimeError(
                f"catalog rollout transaction private entry changed externally: {entry_name}"
            )
        libc = ctypes.CDLL(None, use_errno=True)
        unlinkat = getattr(libc, "unlinkat", None)
        if unlinkat is None:
            raise RuntimeError(
                "catalog rollout transaction private unlink primitive is unavailable"
            )
        unlinkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        unlinkat.restype = ctypes.c_int
        # ``AT_UNIQUE`` is not usable for ordinary macOS descriptors: Darwin
        # rejects it with ``ENOTCAPABLE`` outside capability mode.  The entry
        # is already anchored in a private directory and is held open while
        # the syscall runs, so use the portable unlinkat form here.
        if unlinkat(parent_descriptor, os.fsencode(entry_name), 0) != 0:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number), entry_name)
        # A private entry may have another intentional hard link (for example
        # while reconciling a replacement guard).  The anchored unlinkat call
        # removed only this directory entry; callers probe this same private
        # directory before disposing of its container.
    finally:
        os.close(descriptor)


def _unlink_expected_path_if_present(
    path: Path,
    expected_identity: tuple[int, int],
    expected_content: bytes,
    expected_mode: int,
) -> None:
    """Remove a temporary path only when its anchored inode is still owned."""
    parent_descriptor = os.open(path.parent, _DIRECTORY_OPEN_FLAGS)
    try:
        try:
            _unlink_private_entry_at(
                parent_descriptor,
                path.name,
                expected_identity,
                expected_content,
                expected_mode,
            )
        except FileNotFoundError:
            return
    finally:
        os.close(parent_descriptor)


def _remove_private_directory_at(
    parent_descriptor: int,
    entry_name: str,
    expected_identity: tuple[int, int],
) -> None:
    """Remove one already-private empty directory through unlinkat."""
    descriptor = os.open(entry_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor)
    try:
        if _descriptor_identity(descriptor) != expected_identity:
            raise RuntimeError(
                f"catalog rollout transaction private directory changed externally: {entry_name}"
            )
        if os.listdir(descriptor):
            raise RuntimeError(
                f"catalog rollout transaction private directory is not empty: {entry_name}"
            )
        libc = ctypes.CDLL(None, use_errno=True)
        unlinkat = getattr(libc, "unlinkat", None)
        if unlinkat is None:
            raise RuntimeError(
                "catalog rollout transaction private directory unlink primitive is unavailable"
            )
        unlinkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        unlinkat.restype = ctypes.c_int
        if unlinkat(parent_descriptor, os.fsencode(entry_name), _AT_REMOVEDIR) != 0:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number), entry_name)
    finally:
        os.close(descriptor)
    if _capture_directory_identity_at(parent_descriptor, entry_name) is not None:
        raise RuntimeError(
            f"catalog rollout transaction private directory cleanup failed: {entry_name}"
        )


def _open_anchored_parent(
    root_descriptor: int, repository_root: Path, target: Path
) -> tuple[int, str]:
    root = repository_root.resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise RuntimeError("catalog rollout transaction path escapes repository") from error
    if not relative.parts:
        raise RuntimeError("catalog rollout transaction target path is invalid")
    descriptor = os.dup(root_descriptor)
    try:
        for part in relative.parts[:-1]:
            next_descriptor = os.open(
                part, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor, relative.parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _open_target_lock(parent_descriptor: int, target_name: str) -> int | None:
    try:
        descriptor = os.open(
            target_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise RuntimeError(
                f"catalog rollout transaction target must be a regular file: {target_name}"
            ) from error
        raise
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(
                f"catalog rollout transaction target must be a regular file: {target_name}"
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _descriptor_identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _identity_token(identity: tuple[int, int]) -> str:
    """Encode an inode identity in a bounded quarantine-name token."""
    return hashlib.sha256(f"{identity[0]}:{identity[1]}".encode("ascii")).hexdigest()[:32]


def _link_expected_entry_at(
    source_parent: int,
    source_name: str,
    destination_parent: int,
    destination_name: str,
    *,
    expected_identity: tuple[int, int],
) -> tuple[int, int]:
    """Duplicate one expected inode while validating both path identities."""
    source_descriptor = os.open(source_name, _TARGET_OPEN_FLAGS, dir_fd=source_parent)
    try:
        if _descriptor_identity(source_descriptor) != expected_identity:
            raise RuntimeError(
                f"catalog rollout transaction source changed externally: {source_name}"
            )
    finally:
        os.close(source_descriptor)
    os.link(
        source_name,
        destination_name,
        src_dir_fd=source_parent,
        dst_dir_fd=destination_parent,
        follow_symlinks=False,
    )
    try:
        destination_descriptor = os.open(
            destination_name, _TARGET_OPEN_FLAGS, dir_fd=destination_parent
        )
    except OSError as error:
        # ``os.link(..., follow_symlinks=False)`` can publish a symlink when
        # the source path is replaced between the initial identity check and
        # the link syscall.  Do not try to clean up an entry that we can no
        # longer identify as our regular-file inode.
        raise RuntimeError(
            f"catalog rollout transaction linked destination changed externally: {destination_name}"
        ) from error
    try:
        _capture_open_descriptor_state(destination_descriptor)
        destination_identity = _descriptor_identity(destination_descriptor)
    finally:
        os.close(destination_descriptor)
    initial_destination_path_identity = _capture_transaction_identity_at(
        destination_parent, destination_name
    )
    source_path_identity = _capture_transaction_identity_at(source_parent, source_name)
    destination_path_identity = _capture_transaction_identity_at(
        destination_parent, destination_name
    )
    if source_path_identity != expected_identity:
        raise RuntimeError(
            f"catalog rollout transaction source changed externally: {source_name}"
        )
    if (
        destination_identity != expected_identity
        or initial_destination_path_identity != destination_identity
        or destination_path_identity != destination_identity
    ):
        raise RuntimeError(
            f"catalog rollout transaction linked destination changed externally: {destination_name}"
        )
    return destination_identity


def _native_rename_no_replace(
    source_name: str,
    destination_name: str,
    source_parent: int,
    destination_parent: int,
) -> bool:
    """Atomically rename without replacing an existing destination when supported."""
    if "/" in source_name or "/" in destination_name:
        raise RuntimeError("catalog rollout transaction entry name is invalid")
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin" and hasattr(libc, "renameatx_np"):
        renameatx_np = libc.renameatx_np
        renameatx_np.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameatx_np.restype = ctypes.c_int
        result = renameatx_np(
            source_parent,
            os.fsencode(source_name),
            destination_parent,
            os.fsencode(destination_name),
            _DARWIN_RENAME_EXCL,
        )
        if result == 0:
            return True
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise FileExistsError(
                error_number,
                os.strerror(error_number),
                destination_name,
            )
        if error_number not in {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}:
            raise OSError(error_number, os.strerror(error_number), source_name)
        return False
    if hasattr(libc, "renameat2"):
        renameat2 = libc.renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            source_parent,
            os.fsencode(source_name),
            destination_parent,
            os.fsencode(destination_name),
            _LINUX_RENAME_NOREPLACE,
        )
        if result == 0:
            return True
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise FileExistsError(
                error_number,
                os.strerror(error_number),
                destination_name,
            )
        if error_number not in {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}:
            raise OSError(error_number, os.strerror(error_number), source_name)
        return False
    return False


def _rename_no_replace_at(
    source_parent: int,
    source_name: str,
    destination_parent: int,
    destination_name: str,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, int] | None:
    """Move one anchored entry while preserving an already-created destination."""
    source_descriptor: int | None = None
    source_identity = expected_identity
    try:
        try:
            source_descriptor = os.open(
                source_name, _TARGET_OPEN_FLAGS, dir_fd=source_parent
            )
        except IsADirectoryError:
            source_descriptor = None
        if source_descriptor is not None:
            observed_identity = _descriptor_identity(source_descriptor)
            if source_identity is None:
                source_identity = observed_identity
            elif observed_identity != source_identity:
                raise RuntimeError(
                    f"catalog rollout transaction source changed externally: {source_name}"
                )
        elif expected_identity is not None:
            raise RuntimeError(
                f"catalog rollout transaction source changed externally: {source_name}"
            )

        # A no-replace rename of an entry onto itself is already complete.
        # Darwin's ``renameatx_np`` treats this as a no-op, while Linux
        # ``renameat2(..., RENAME_NOREPLACE)`` reports ``EEXIST``.  Keep the
        # anchored identity validation above, then avoid a platform-specific
        # syscall for this same-entry case.
        if (
            source_parent == destination_parent
            and source_name == destination_name
            and (source_descriptor is not None or expected_identity is not None)
        ):
            return source_identity

        if _native_rename_no_replace(
            source_name, destination_name, source_parent, destination_parent
        ):
            if source_identity is None:
                return None
            destination_descriptor = os.open(
                destination_name, _TARGET_OPEN_FLAGS, dir_fd=destination_parent
            )
            try:
                destination_identity = _descriptor_identity(destination_descriptor)
            finally:
                os.close(destination_descriptor)
            if destination_identity != source_identity:
                # The native call is path based, so an external rename can
                # swap the source entry between the descriptor check and the
                # syscall.  If that happened, move the unexpected destination
                # inode back to the source name when the source is now absent;
                # otherwise leave both path entries untouched and fail closed.
                if _capture_transaction_identity_at(source_parent, source_name) is None:
                    try:
                        restored = _native_rename_no_replace(
                            destination_name,
                            source_name,
                            destination_parent,
                            source_parent,
                        )
                        if restored:
                            restored_identity = _capture_transaction_identity_at(
                                source_parent, source_name
                            )
                            if restored_identity != destination_identity:
                                raise RuntimeError(
                                    f"catalog rollout transaction source restore changed externally: {source_name}"
                                )
                    except (FileExistsError, OSError, RuntimeError) as restore_error:
                        raise RuntimeError(
                            f"catalog rollout transaction moved inode changed externally: {destination_name}"
                        ) from restore_error
                raise RuntimeError(
                    f"catalog rollout transaction moved inode changed externally: {destination_name}"
                )
            return destination_identity

        if source_descriptor is None:
            raise RuntimeError(
                "catalog rollout transaction cannot move a directory without no-replace support"
            )
        if source_identity is None:
            raise RuntimeError(
                f"catalog rollout transaction source identity is unavailable: {source_name}"
            )
        raise RuntimeError(
            "catalog rollout transaction safe no-replace rename is unavailable"
        )
    finally:
        if source_descriptor is not None:
            os.close(source_descriptor)


def _unlink_expected_entry_at(
    parent_descriptor: int,
    entry_name: str,
    expected_identity: tuple[int, int],
    expected_content: bytes,
    expected_mode: int,
    *,
    quarantine_directory: bool = True,
) -> None:
    """Remove an expected inode without unlinking a replacement path entry."""
    deletion_name = f"{entry_name}.delete"
    _rename_no_replace_at(
        parent_descriptor,
        entry_name,
        parent_descriptor,
        deletion_name,
        expected_identity=expected_identity,
    )
    try:
        deletion_descriptor = os.open(
            deletion_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            state = _capture_open_descriptor_state(deletion_descriptor)
            if (
                _descriptor_identity(deletion_descriptor) != expected_identity
                or not _write_state_matches(state, expected_content, expected_mode)
            ):
                raise RuntimeError(
                    f"catalog rollout transaction entry changed externally: {entry_name}"
                )
        finally:
            os.close(deletion_descriptor)
        # Do not unlink the validated ``.delete`` path itself.  Move the owned
        # inode once more to a bounded rollback-shaped name first; a concurrent
        # replacement at ``.delete`` is then rejected by the identity check and
        # remains available for quarantine recovery.
        final_name = (
            f"{_quarantine_rollback_base_name(entry_name)}."
            f"{os.getpid()}.{uuid.uuid4().hex}.rollback"
        )
        _rename_no_replace_at(
            parent_descriptor,
            deletion_name,
            parent_descriptor,
            final_name,
            expected_identity=expected_identity,
        )
        final_descriptor = os.open(
            final_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            final_state = _capture_open_descriptor_state(final_descriptor)
            if (
                _descriptor_identity(final_descriptor) != expected_identity
                or not _write_state_matches(final_state, expected_content, expected_mode)
            ):
                raise RuntimeError(
                    f"catalog rollout transaction entry changed externally: {entry_name}"
                )
        finally:
            os.close(final_descriptor)
        transaction_id = _infer_transaction_id_at(parent_descriptor)
        if not quarantine_directory:
            private_directory_name = (
                f".catalog-rollout-private.{os.getpid()}.{uuid.uuid4().hex}"
            )
            os.mkdir(private_directory_name, 0o700, dir_fd=parent_descriptor)
            private_directory_descriptor = os.open(
                private_directory_name,
                _DIRECTORY_OPEN_FLAGS,
                dir_fd=parent_descriptor,
            )
            private_directory_identity = _descriptor_identity(
                private_directory_descriptor
            )
            terminal_name = (
                f"{_quarantine_rollback_base_name(final_name)}."
                f"{os.getpid()}.{uuid.uuid4().hex}.rollback"
            )
            try:
                _rename_no_replace_at(
                    parent_descriptor,
                    final_name,
                    private_directory_descriptor,
                    terminal_name,
                    expected_identity=expected_identity,
                    )
                terminal_descriptor = os.open(
                    terminal_name,
                    _TARGET_OPEN_FLAGS,
                    dir_fd=private_directory_descriptor,
                )
                try:
                    terminal_state = _capture_open_descriptor_state(terminal_descriptor)
                    if (
                        _descriptor_identity(terminal_descriptor) != expected_identity
                        or not _write_state_matches(
                            terminal_state, expected_content, expected_mode
                        )
                    ):
                        raise RuntimeError(
                            f"catalog rollout transaction entry changed externally: {entry_name}"
                        )
                finally:
                    os.close(terminal_descriptor)
                _unlink_private_entry_at(
                    private_directory_descriptor,
                    terminal_name,
                    expected_identity,
                    expected_content,
                    expected_mode,
                )
                if (
                    _capture_transaction_identity_at(
                        private_directory_descriptor, terminal_name
                    )
                    is not None
                ):
                    raise RuntimeError(
                        f"catalog rollout transaction entry cleanup failed: {entry_name}"
                    )
            finally:
                os.close(private_directory_descriptor)
                _remove_expected_directory_at(
                    parent_descriptor,
                    private_directory_name,
                    private_directory_identity,
                )
            return
        quarantine_name = _quarantine_directory_name(
            transaction_id,
            entry_name,
            expected_content,
            expected_mode,
            expected_identity,
        )
        os.mkdir(quarantine_name, 0o700, dir_fd=parent_descriptor)
        quarantine_descriptor = os.open(
            quarantine_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        quarantine_identity = _descriptor_identity(quarantine_descriptor)
        cleanup_name = f".owned.{os.getpid()}.{uuid.uuid4().hex}.unlink"
        try:
            _rename_no_replace_at(
                parent_descriptor,
                final_name,
                quarantine_descriptor,
                cleanup_name,
                expected_identity=expected_identity,
            )
            cleanup_descriptor = os.open(
                cleanup_name, _TARGET_OPEN_FLAGS, dir_fd=quarantine_descriptor
            )
            try:
                cleanup_state = _capture_open_descriptor_state(cleanup_descriptor)
                if (
                    _descriptor_identity(cleanup_descriptor) != expected_identity
                    or not _write_state_matches(
                        cleanup_state, expected_content, expected_mode
                    )
                ):
                    raise RuntimeError(
                        f"catalog rollout transaction entry changed externally: {entry_name}"
                    )
            finally:
                os.close(cleanup_descriptor)
            if _capture_transaction_state_at(parent_descriptor, final_name)[0]:
                raise RuntimeError(
                    f"catalog rollout transaction entry changed externally: {entry_name}"
                )
            terminal_name = (
                f".owned.{os.getpid()}.{uuid.uuid4().hex}.terminal"
            )
            _rename_no_replace_at(
                quarantine_descriptor,
                cleanup_name,
                quarantine_descriptor,
                terminal_name,
                expected_identity=expected_identity,
            )
            terminal_descriptor = os.open(
                terminal_name, _TARGET_OPEN_FLAGS, dir_fd=quarantine_descriptor
            )
            try:
                terminal_state = _capture_open_descriptor_state(terminal_descriptor)
                if (
                    _descriptor_identity(terminal_descriptor) != expected_identity
                    or not _write_state_matches(
                        terminal_state, expected_content, expected_mode
                    )
                ):
                    raise RuntimeError(
                        f"catalog rollout transaction entry changed externally: {entry_name}"
                    )
            finally:
                os.close(terminal_descriptor)
            _unlink_private_entry_at(
                quarantine_descriptor,
                terminal_name,
                expected_identity,
                expected_content,
                expected_mode,
            )
            if _capture_transaction_identity_at(quarantine_descriptor, terminal_name) is not None:
                raise RuntimeError(
                    f"catalog rollout transaction entry cleanup failed: {entry_name}"
                )
        finally:
            os.close(quarantine_descriptor)
            _remove_expected_directory_at(
                parent_descriptor,
                quarantine_name,
                quarantine_identity,
            )
    except BaseException:  # noqa: TRY203 - preserve the private recovery artifact
        # Leave the expected inode under whichever private name the last
        # anchored move reached; the quarantine recovery path will re-expose it.
        raise


def _remove_expected_directory_at(
    parent_descriptor: int,
    directory_name: str,
    expected_identity: tuple[int, int],
) -> None:
    """Remove one expected empty directory without deleting a replacement name."""
    cleanup_name = f".owned-directory.{os.getpid()}.{uuid.uuid4().hex}.delete"
    _rename_no_replace_at(
        parent_descriptor,
        directory_name,
        parent_descriptor,
        cleanup_name,
        expected_identity=expected_identity,
    )
    removal_name: str | None = None
    quarantine_name: str | None = None
    quarantine_identity: tuple[int, int] | None = None
    quarantine_descriptor: int | None = None
    quarantine_removal_name: str | None = None
    moved_into_quarantine = False
    try:
        cleanup_descriptor = os.open(
            cleanup_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            if os.listdir(cleanup_descriptor):
                raise RuntimeError(
                    f"catalog rollout transaction directory is not empty: {directory_name}"
                )
        finally:
            os.close(cleanup_descriptor)
        candidate_removal_name = (
            f".owned-directory.{os.getpid()}.{uuid.uuid4().hex}.remove"
        )
        _rename_no_replace_at(
            parent_descriptor,
            cleanup_name,
            parent_descriptor,
            candidate_removal_name,
            expected_identity=expected_identity,
        )
        removal_name = candidate_removal_name
        removal_descriptor = os.open(
            removal_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            if os.listdir(removal_descriptor):
                raise RuntimeError(
                    f"catalog rollout transaction directory is not empty: {directory_name}"
                )
            if _descriptor_identity(removal_descriptor) != expected_identity:
                raise RuntimeError(
                    f"catalog rollout transaction directory changed externally: {directory_name}"
                )
        finally:
            os.close(removal_descriptor)
        # Move the validated directory into a private 0700 container before
        # the final rmdir.  The public cleanup names are never passed to
        # rmdir, so a replacement at either public name is preserved by the
        # anchored identity check on the move.
        quarantine_name = (
            f".catalog-rollout-directory-cleanup."
            f"{os.getpid()}.{uuid.uuid4().hex}"
        )
        os.mkdir(quarantine_name, 0o700, dir_fd=parent_descriptor)
        quarantine_descriptor = os.open(
            quarantine_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        quarantine_identity = _descriptor_identity(quarantine_descriptor)
        terminal_name = f".owned.{os.getpid()}.{uuid.uuid4().hex}.directory"
        _rename_no_replace_at(
            parent_descriptor,
            removal_name,
            quarantine_descriptor,
            terminal_name,
            expected_identity=expected_identity,
        )
        moved_into_quarantine = True
        removal_name = None
        terminal_descriptor = os.open(
            terminal_name, _DIRECTORY_OPEN_FLAGS, dir_fd=quarantine_descriptor
        )
        try:
            if os.listdir(terminal_descriptor):
                raise RuntimeError(
                    f"catalog rollout transaction directory is not empty: {directory_name}"
                )
            if _descriptor_identity(terminal_descriptor) != expected_identity:
                raise RuntimeError(
                    f"catalog rollout transaction directory changed externally: {directory_name}"
                )
        finally:
            os.close(terminal_descriptor)
        _remove_private_directory_at(
            quarantine_descriptor, terminal_name, expected_identity
        )
        os.close(quarantine_descriptor)
        quarantine_descriptor = None

        quarantine_removal_name = (
            f".{quarantine_name}.{os.getpid()}.{uuid.uuid4().hex}.remove"
        )
        _rename_no_replace_at(
            parent_descriptor,
            quarantine_name,
            parent_descriptor,
            quarantine_removal_name,
            expected_identity=quarantine_identity,
        )
        quarantine_name = None
        quarantine_removal_descriptor = os.open(
            quarantine_removal_name,
            _DIRECTORY_OPEN_FLAGS,
            dir_fd=parent_descriptor,
        )
        try:
            if os.listdir(quarantine_removal_descriptor):
                raise RuntimeError(
                    f"catalog rollout transaction directory cleanup is not empty: {directory_name}"
                )
            if _descriptor_identity(quarantine_removal_descriptor) != quarantine_identity:
                raise RuntimeError(
                    f"catalog rollout transaction directory changed externally: {directory_name}"
                )
        finally:
            os.close(quarantine_removal_descriptor)
        _remove_private_directory_at(
            parent_descriptor, quarantine_removal_name, quarantine_identity
        )
        quarantine_removal_name = None
    except BaseException:
        if quarantine_descriptor is not None:
            os.close(quarantine_descriptor)
        if not moved_into_quarantine:
            restore_name = removal_name or cleanup_name
            restore_exists = True
            try:
                probe = os.open(
                    restore_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
                )
            except FileNotFoundError:
                restore_exists = False
            else:
                os.close(probe)
            if restore_exists:
                try:
                    _rename_no_replace_at(
                        parent_descriptor,
                        restore_name,
                        parent_descriptor,
                        directory_name,
                        expected_identity=expected_identity,
                    )
                except FileExistsError as restore_error:
                    raise RuntimeError(
                        f"catalog rollout transaction directory cleanup conflict: {directory_name}"
                    ) from restore_error
        raise


def _assert_directory_descriptor_matches_path(
    descriptor: int, path: Path
) -> None:
    try:
        path_descriptor = os.open(path, _DIRECTORY_OPEN_FLAGS)
    except OSError as error:
        raise RuntimeError(
            f"catalog rollout transaction parent directory changed externally: {path}"
        ) from error
    try:
        if _descriptor_identity(path_descriptor) != _descriptor_identity(descriptor):
            raise RuntimeError(
                f"catalog rollout transaction parent directory changed externally: {path}"
            )
    finally:
        os.close(path_descriptor)


def _assert_root_descriptor_matches_path(
    root_descriptor: int, repository_root: Path
) -> None:
    try:
        path_descriptor = os.open(repository_root, _DIRECTORY_OPEN_FLAGS)
    except OSError as error:
        raise RuntimeError("catalog rollout repository root changed externally") from error
    try:
        if _descriptor_identity(path_descriptor) != _descriptor_identity(root_descriptor):
            raise RuntimeError("catalog rollout repository root changed externally")
    finally:
        os.close(path_descriptor)


def _write_state_matches(
    state: tuple[bool, bytes, int | None], content: bytes, mode: int | None
) -> bool:
    return state[0] and state[1] == content and (mode is None or state[2] == mode)


def _infer_transaction_id_at(parent_descriptor: int) -> str | None:
    for name, parser in (
        (".catalog-rollout-transaction.identity", _parse_transaction_identity),
        (
            ".catalog-rollout-transaction.finalizing",
            _parse_transaction_finalization_marker,
        ),
    ):
        state = _capture_transaction_state_at(parent_descriptor, name)
        if state[0]:
            try:
                return parser(state[1])[0]
            except RuntimeError:
                return None
    return None


def _discard_expected_tombstone_at(
    parent_descriptor: int,
    tombstone_name: str,
    expected_identity: tuple[int, int],
    expected_content: bytes,
    expected_mode: int,
    *,
    sync_directory: bool = True,
    transaction_id: str | None = None,
) -> None:
    """Delete a tombstone after proving it is still our moved inode.

    The caller holds the target inode lock for the entire tombstone lifecycle;
    opening the same inode and flocking it again would deadlock on macOS.
    """
    try:
        descriptor = os.open(
            tombstone_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
    except FileNotFoundError:
        return
    # Keep one bounded rollback suffix.  Recovery can encounter a tombstone
    # that already came back from quarantine; appending another suffix on each
    # retry eventually crosses NAME_MAX and loses the evidence boundary.
    rollback_base_name = _quarantine_rollback_base_name(tombstone_name)
    cleanup_name = f"{rollback_base_name}.{os.getpid()}.{uuid.uuid4().hex}.rollback"
    deletion_name = cleanup_name
    moved_name: str | None = None
    quarantine_name: str | None = None
    quarantine_descriptor: int | None = None
    quarantine_identity: tuple[int, int] | None = None
    quarantine_created = False
    quarantined = False
    if transaction_id is None:
        transaction_id = _infer_transaction_id_at(parent_descriptor)

    def restore_from_quarantine() -> None:
        nonlocal quarantined, moved_name, quarantine_name
        if not quarantined or quarantine_descriptor is None:
            return
        entries = os.listdir(quarantine_descriptor)
        if len(entries) != 1:
            raise RuntimeError(
                "catalog rollout transaction rollback tombstone restore conflict; "
                "cleanup evidence is ambiguous"
            )
        quarantine_entry_name = entries[0]
        try:
            _rename_no_replace_at(
                quarantine_descriptor,
                quarantine_entry_name,
                parent_descriptor,
                tombstone_name,
                expected_identity=expected_identity,
            )
        except (FileExistsError, RuntimeError) as restore_error:
            raise RuntimeError(
                "catalog rollout transaction rollback tombstone restore "
                f"conflict; cleanup preserved: {quarantine_entry_name}"
            ) from restore_error
        quarantined = False
        moved_name = None

    def preserve_or_restore_moved() -> None:
        nonlocal moved_name
        if moved_name is None:
            return
        moved_state = _capture_transaction_state_at(parent_descriptor, moved_name)
        if not _write_state_matches(moved_state, expected_content, expected_mode):
            raise RuntimeError(
                "catalog rollout transaction rollback tombstone changed externally; "
                f"cleanup preserved: {moved_name}"
            )
        current = _capture_transaction_state_at(parent_descriptor, tombstone_name)
        if current[0]:
            raise RuntimeError(
                "catalog rollout transaction rollback tombstone restore "
                f"conflict; cleanup preserved: {moved_name}"
            )
        try:
            _rename_no_replace_at(
                parent_descriptor,
                moved_name,
                parent_descriptor,
                tombstone_name,
                expected_identity=expected_identity,
            )
        except (FileExistsError, RuntimeError) as restore_error:
            raise RuntimeError(
                "catalog rollout transaction rollback tombstone restore "
                f"conflict; cleanup preserved: {moved_name}"
            ) from restore_error
        moved_name = None

    try:
        state = _capture_open_descriptor_state(descriptor)
        if (
            _descriptor_identity(descriptor) != expected_identity
            or not _write_state_matches(state, expected_content, expected_mode)
        ):
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
            )
        try:
            # Move the owned entry away from its public tombstone name before
            # unlinking.  A concurrent insertion at the original name is then
            # preserved instead of being removed by cleanup.
            _rename_no_replace_at(
                parent_descriptor,
                tombstone_name,
                parent_descriptor,
                cleanup_name,
                expected_identity=expected_identity,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
            ) from error
        moved_name = cleanup_name

        cleanup_descriptor = os.open(
            cleanup_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            cleanup_state = _capture_open_descriptor_state(cleanup_descriptor)
            if (
                _descriptor_identity(cleanup_descriptor) != expected_identity
                or not _write_state_matches(
                    cleanup_state, expected_content, expected_mode
                )
            ):
                raise RuntimeError(
                    f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
                )
        finally:
            os.close(cleanup_descriptor)

        if _capture_transaction_state_at(parent_descriptor, tombstone_name)[0]:
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
            )

        # Quarantine the already-validated inode a second time before unlinking
        # it.  The public cleanup name is never passed to unlink after its
        # validation, so a concurrent insertion at that name is preserved.
        try:
            _rename_no_replace_at(
                parent_descriptor,
                cleanup_name,
                parent_descriptor,
                deletion_name,
                expected_identity=expected_identity,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
            ) from error
        moved_name = deletion_name
        deletion_descriptor = os.open(
            deletion_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            deletion_state = _capture_open_descriptor_state(deletion_descriptor)
            if (
                _descriptor_identity(deletion_descriptor) != expected_identity
                or not _write_state_matches(
                    deletion_state, expected_content, expected_mode
                )
            ):
                raise RuntimeError(
                    f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
                )
        finally:
            os.close(deletion_descriptor)
        if cleanup_name != deletion_name and _capture_transaction_state_at(
            parent_descriptor, cleanup_name
        )[0]:
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
            )
        if _capture_transaction_state_at(parent_descriptor, tombstone_name)[0]:
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
            )
        # A path-entry can be replaced after the final validation.  Move the
        # owned inode into a private directory before unlinking it so an
        # external replacement at the public rollback name cannot be removed.
        quarantine_name = _quarantine_directory_name(
            transaction_id,
            rollback_base_name,
            expected_content,
            expected_mode,
            expected_identity,
        )
        os.mkdir(quarantine_name, 0o700, dir_fd=parent_descriptor)
        quarantine_created = True
        quarantine_descriptor = os.open(
            quarantine_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        quarantine_identity = _descriptor_identity(quarantine_descriptor)
        _rename_no_replace_at(
            parent_descriptor,
            deletion_name,
            quarantine_descriptor,
            deletion_name,
            expected_identity=expected_identity,
        )
        moved_name = None
        quarantined = True
        quarantined_descriptor = os.open(
            deletion_name, _TARGET_OPEN_FLAGS, dir_fd=quarantine_descriptor
        )
        try:
            quarantined_state = _capture_open_descriptor_state(quarantined_descriptor)
            if (
                _descriptor_identity(quarantined_descriptor) != expected_identity
                or not _write_state_matches(
                    quarantined_state, expected_content, expected_mode
                )
            ):
                restore_from_quarantine()
                raise RuntimeError(
                    f"catalog rollout transaction rollback tombstone changed externally: {tombstone_name}"
                )
        finally:
            os.close(quarantined_descriptor)
        _unlink_expected_entry_at(
            quarantine_descriptor,
            deletion_name,
            expected_identity,
            expected_content,
            expected_mode,
            quarantine_directory=False,
        )
        quarantined = False
        _remove_expected_directory_at(
            parent_descriptor,
            quarantine_name,
            quarantine_identity,
        )
        quarantine_name = None
        moved_name = None
        if sync_directory:
            _fsync_directory_fd(parent_descriptor)
    except BaseException as error:
        if quarantined:
            restore_from_quarantine()
        if quarantine_descriptor is not None:
            os.close(quarantine_descriptor)
            quarantine_descriptor = None
        if quarantine_name is not None and quarantine_created and not quarantined:
            try:
                if quarantine_identity is not None:
                    _remove_expected_directory_at(
                        parent_descriptor,
                        quarantine_name,
                        quarantine_identity,
                    )
            except FileNotFoundError:
                pass
        if moved_name is not None:
            try:
                preserve_or_restore_moved()
            except RuntimeError:
                raise
            except FileNotFoundError as restore_error:
                raise RuntimeError(
                    "catalog rollout transaction rollback tombstone restore "
                    f"failed; cleanup preserved: {moved_name}"
                ) from restore_error
            except BaseException as restore_error:
                raise RuntimeError(
                    "catalog rollout transaction rollback tombstone restore "
                    f"failed; cleanup preserved: {moved_name}"
                ) from restore_error
        if moved_name is not None:
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone preserved: {moved_name}"
            ) from error
        raise
    finally:
        if quarantine_descriptor is not None:
            os.close(quarantine_descriptor)
        os.close(descriptor)


def _directory_entry_names(parent_descriptor: int) -> list[str]:
    """List one anchored directory without resolving its path again."""
    try:
        return os.listdir(parent_descriptor)
    except OSError as error:
        raise RuntimeError(
            "catalog rollout transaction parent directory cannot be enumerated"
        ) from error


def _quarantine_directory_name(
    transaction_id: str | None,
    target_name: str,
    content: bytes,
    mode: int,
    expected_identity: tuple[int, int] | None = None,
) -> str:
    identity_token = _identity_token(expected_identity) if expected_identity is not None else None
    return (
        ".catalog-rollout-quarantine."
        f"{transaction_id or 'orphan'}."
        f"{hashlib.sha256(target_name.encode('utf-8')).hexdigest()[:32]}."
        f"{hashlib.sha256(content).hexdigest()}."
        f"{mode:o}."
        f"{identity_token + '.' if identity_token is not None else ''}"
        f"{uuid.uuid4().hex}"
    )


def _parse_quarantine_directory_name(name: str) -> dict[str, Any]:
    prefix = ".catalog-rollout-quarantine."
    if not name.startswith(prefix):
        raise RuntimeError(
            "catalog rollout transaction quarantine evidence is invalid (provenance)"
        )
    body = name[len(prefix) :]
    parts = body.split(".")
    if len(parts) not in {5, 6}:
        raise RuntimeError(
            "catalog rollout transaction quarantine evidence is invalid (provenance)"
        )
    if len(parts) == 5:
        transaction_id, target_sha256, content_sha256, mode_text, nonce = parts
        identity_text = None
    else:
        (
            transaction_id,
            target_sha256,
            content_sha256,
            mode_text,
            identity_text,
            nonce,
        ) = parts
    if (
        transaction_id != "orphan"
        and re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None
        or re.fullmatch(r"[0-9a-f]{32}", target_sha256) is None
        or FULL_SHA256.fullmatch(content_sha256) is None
        or re.fullmatch(r"[0-7]{1,4}", mode_text) is None
        or re.fullmatch(r"[0-9a-f]{32}", nonce) is None
        or (
            identity_text is not None
            and re.fullmatch(r"[0-9a-f]{32}", identity_text) is None
        )
    ):
        raise RuntimeError(
            "catalog rollout transaction quarantine evidence is invalid (provenance)"
        )
    return {
        "content-sha256": content_sha256,
        "expected-identity-token": identity_text,
        "mode": int(mode_text, 8),
        "target-sha256": target_sha256,
        "transaction-id": transaction_id,
    }


def _quarantine_rollback_base_name(entry_name: str) -> str:
    """Return the stable rollback name used as quarantine provenance."""
    match = re.fullmatch(
        r"(?P<base>.+\.[0-9]+\.[0-9a-f]{32}\.rollback)"
        r"\.[0-9]+\.[0-9a-f]{32}\.rollback",
        entry_name,
    )
    return match.group("base") if match is not None else entry_name


def _recover_immutable_cleanup_artifacts_at(
    parent_descriptor: int,
    target_name: str,
    content: bytes,
) -> None:
    """Remove receipt-writer rollback artifacts left by an interrupted cleanup."""
    prefix = f".{target_name}."
    for entry_name in sorted(_directory_entry_names(parent_descriptor)):
        if (
            not entry_name.startswith(prefix)
            or ".tmp." not in entry_name
            or not entry_name.endswith(".rollback")
        ):
            continue
        state, identity = _capture_transaction_state_and_identity_at(
            parent_descriptor, entry_name
        )
        if identity is None:
            continue
        if not _write_state_matches(state, content, 0o600):
            raise RuntimeError(
                "immutable rollout cleanup artifact changed externally: "
                f"{entry_name}"
            )
        _unlink_expected_entry_at(
            parent_descriptor,
            entry_name,
            identity,
            content,
            0o600,
            quarantine_directory=False,
        )


def _quarantine_target_name(entry_name: str) -> str:
    # ``_unlink_expected_entry_at`` can itself be interrupted after moving the
    # entry to its private delete name.  Strip that private suffix before
    # validating the original rollback provenance on the next recovery pass.
    entry_name = re.sub(r"\.delete$", "", entry_name)
    match = re.fullmatch(
        r"(?P<target>.+)\.[0-9]+\.[0-9a-f]{32}\.rollback"
        r"(?:\.[0-9]+\.[0-9a-f]{32}\.rollback)?",
        entry_name,
    )
    if match is None:
        raise RuntimeError("catalog rollout transaction quarantine evidence is invalid")
    return match.group("target")


def _recover_quarantine_directories_at(
    parent_descriptor: int,
    expected_transaction_id: str | None = None,
    *,
    allow_orphan: bool = True,
) -> set[str]:
    """Return files stranded in a private purge directory to its parent.

    A process can stop after the owned rollback inode enters the private
    directory but before unlinking it.  Re-expose that inode under its unique
    rollback name so the normal identity and content checks can finish the
    cleanup on the next transaction recovery.
    """
    prefix = ".catalog-rollout-quarantine."
    transaction_ids: set[str] = set()
    quarantine_names = sorted(
        name for name in _directory_entry_names(parent_descriptor) if name.startswith(prefix)
    )
    provenances = [
        (name, _parse_quarantine_directory_name(name)) for name in quarantine_names
    ]
    if not allow_orphan and expected_transaction_id is None and provenances:
        raise RuntimeError(
            "catalog rollout transaction quarantine has no canonical transaction"
        )
    for quarantine_name, provenance in provenances:
        transaction_id = provenance["transaction-id"]
        if (
            expected_transaction_id is not None
            and transaction_id != expected_transaction_id
        ):
            raise RuntimeError(
                "catalog rollout transaction quarantine belongs to another transaction"
            )
        transaction_ids.add(transaction_id)
        try:
            quarantine_descriptor = os.open(
                quarantine_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
            )
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise RuntimeError(
                    "catalog rollout transaction quarantine changed externally"
                ) from error
            raise
        try:
            quarantine_identity = _descriptor_identity(quarantine_descriptor)
            entries = os.listdir(quarantine_descriptor)
            if len(entries) > 1:
                raise RuntimeError(
                    "catalog rollout transaction quarantine has ambiguous evidence"
                )
            if entries:
                entry_name = entries[0]
                if _capture_transaction_state_at(parent_descriptor, entry_name)[0]:
                    raise RuntimeError(
                        "catalog rollout transaction quarantine restore conflict"
                    )
                if (
                    entry_name
                    in {
                        ".catalog-rollout-transaction.json",
                        ".catalog-rollout-transaction.identity",
                        ".catalog-rollout-transaction.finalizing",
                    }
                    or not entry_name.startswith(".")
                    or not entry_name.endswith((".rollback", ".delete"))
                ):
                    raise RuntimeError(
                        "catalog rollout transaction quarantine evidence is invalid"
                    )
                entry_descriptor = os.open(
                    entry_name, _TARGET_OPEN_FLAGS, dir_fd=quarantine_descriptor
                )
                try:
                    entry_state = _capture_open_descriptor_state(entry_descriptor)
                    entry_identity = _descriptor_identity(entry_descriptor)
                    target_name = _quarantine_target_name(entry_name)
                    if (
                        provenance["expected-identity-token"] is None
                        or _identity_token(entry_identity)
                        != provenance["expected-identity-token"]
                        or hashlib.sha256(target_name.encode("utf-8")).hexdigest()[:32]
                        != provenance["target-sha256"]
                        or entry_state[1] is None
                        or hashlib.sha256(entry_state[1]).hexdigest()
                        != provenance["content-sha256"]
                        or entry_state[2] != provenance["mode"]
                    ):
                        raise RuntimeError(
                            "catalog rollout transaction quarantine provenance changed externally"
                        )
                finally:
                    os.close(entry_descriptor)
                if entry_name.endswith(".delete"):
                    original_entry_name = re.sub(
                        r"\.delete$", "", entry_name
                    )
                    if _capture_transaction_state_at(
                        quarantine_descriptor, original_entry_name
                    )[0]:
                        raise RuntimeError(
                            "catalog rollout transaction quarantine restore conflict"
                        )
                    _rename_no_replace_at(
                        quarantine_descriptor,
                        entry_name,
                        quarantine_descriptor,
                        original_entry_name,
                        expected_identity=entry_identity,
                    )
                    entry_name = original_entry_name
                try:
                    _rename_no_replace_at(
                        quarantine_descriptor,
                        entry_name,
                        parent_descriptor,
                        entry_name,
                        expected_identity=entry_identity,
                    )
                except FileExistsError as error:
                    raise RuntimeError(
                        "catalog rollout transaction quarantine restore conflict"
                    ) from error
                moved_state = _capture_transaction_state_at(
                    parent_descriptor, entry_name
                )
                if (
                    _capture_transaction_identity_at(parent_descriptor, entry_name)
                    != entry_identity
                    or not _write_state_matches(
                        moved_state, entry_state[1], provenance["mode"]
                    )
                ):
                    try:
                        _rename_no_replace_at(
                            parent_descriptor,
                            entry_name,
                            quarantine_descriptor,
                            entry_name,
                            expected_identity=entry_identity,
                        )
                    except BaseException as restore_error:
                        raise RuntimeError(
                            "catalog rollout transaction quarantine restore conflict; "
                            "evidence preserved"
                        ) from restore_error
                    raise RuntimeError(
                        "catalog rollout transaction quarantine provenance changed externally"
                    )
        finally:
            os.close(quarantine_descriptor)
        try:
            _remove_expected_directory_at(
                parent_descriptor,
                quarantine_name,
                quarantine_identity,
            )
        except OSError as error:
            raise RuntimeError(
                "catalog rollout transaction quarantine cleanup failed"
            ) from error
    return transaction_ids


def _artifact_candidates(
    parent_descriptor: int,
    target_name: str,
    suffix: str,
    *,
    transaction_id: str | None = None,
) -> list[str]:
    prefix = f".{target_name}."
    candidates = sorted(
        name
        for name in _directory_entry_names(parent_descriptor)
        if name.startswith(prefix)
        and (
            name.endswith((suffix, f"{suffix}.delete"))
            or (f"{suffix}." in name and name.endswith(".rollback"))
        )
    )
    if transaction_id is None:
        return candidates
    foreign = [
        name
        for name in candidates
        if not name[len(prefix) :].startswith(f"{transaction_id}.")
    ]
    if foreign:
        raise RuntimeError(
            "catalog rollout transaction artifact belongs to another transaction: "
            f"{foreign[0]}"
        )
    return candidates


def _reconcile_target_artifacts_at(
    parent_descriptor: int,
    target_name: str,
    prior_exists: bool,
    prior_content: bytes,
    prior_mode: int | None,
    desired_content: bytes,
    desired_mode: int,
    transaction_id: str | None = None,
) -> None:
    """Recover or remove artifacts left by a process crash during publication."""
    _recover_quarantine_directories_at(
        parent_descriptor, expected_transaction_id=transaction_id
    )
    guard_names = _artifact_candidates(
        parent_descriptor,
        target_name,
        ".replace",
        transaction_id=transaction_id,
    )
    temporary_names = _artifact_candidates(
        parent_descriptor,
        target_name,
        ".tmp",
        transaction_id=transaction_id,
    )
    rollback_names = _artifact_candidates(
        parent_descriptor,
        target_name,
        ".rollback",
        transaction_id=transaction_id,
    )
    if len(guard_names) > 1:
        raise RuntimeError(
            f"catalog rollout transaction has ambiguous replacement guards: {target_name}"
        )
    if len(rollback_names) > 1:
        raise RuntimeError(
            f"catalog rollout transaction has ambiguous rollback tombstones: {target_name}"
        )

    current = _capture_transaction_state_at(parent_descriptor, target_name)
    if rollback_names:
        rollback_name = rollback_names[0]
        rollback_state = _capture_transaction_state_at(parent_descriptor, rollback_name)
        if not _write_state_matches(rollback_state, desired_content, desired_mode):
            raise RuntimeError(
                f"catalog rollout transaction rollback tombstone changed externally: {rollback_name}"
            )
        rollback_descriptor = os.open(
            rollback_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            rollback_identity = _descriptor_identity(rollback_descriptor)
        finally:
            os.close(rollback_descriptor)
        _discard_expected_tombstone_at(
            parent_descriptor,
            rollback_name,
            rollback_identity,
            desired_content,
            desired_mode,
            transaction_id=transaction_id,
        )
    if guard_names:
        guard_name = guard_names[0]
        guard_state = _capture_transaction_state_at(parent_descriptor, guard_name)
        if not prior_exists or not _write_state_matches(
            guard_state, prior_content, prior_mode
        ):
            raise RuntimeError(
                f"catalog rollout transaction replacement guard changed externally: {guard_name}"
            )
        if not current[0]:
            try:
                guard_identity = _capture_transaction_identity_at(
                    parent_descriptor, guard_name
                )
                if guard_identity is None:
                    raise RuntimeError(
                        f"catalog rollout transaction replacement guard changed externally: {guard_name}"
                    )
                _link_expected_entry_at(
                    parent_descriptor,
                    guard_name,
                    parent_descriptor,
                    target_name,
                    expected_identity=guard_identity,
                )
            except FileExistsError as error:
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target_name}"
                ) from error
            _fsync_directory_fd(parent_descriptor)
            current = _capture_transaction_state_at(parent_descriptor, target_name)
            if not _write_state_matches(current, prior_content, prior_mode):
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target_name}"
                )
        elif not (
            _write_state_matches(current, prior_content, prior_mode)
            or _write_state_matches(current, desired_content, desired_mode)
        ):
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {target_name}"
            )
        guard_descriptor = os.open(
            guard_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            guard_identity = _descriptor_identity(guard_descriptor)
        finally:
            os.close(guard_descriptor)
        _discard_expected_tombstone_at(
            parent_descriptor,
            guard_name,
            guard_identity,
            prior_content,
            prior_mode if prior_mode is not None else TRANSACTION_NEW_FILE_MODE,
            transaction_id=transaction_id,
        )

    for temporary_name in temporary_names:
        temporary_state = _capture_transaction_state_at(parent_descriptor, temporary_name)
        if not _write_state_matches(temporary_state, desired_content, desired_mode):
            raise RuntimeError(
                f"catalog rollout transaction temporary artifact changed externally: {temporary_name}"
            )
        temporary_descriptor = os.open(
            temporary_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            temporary_identity = _descriptor_identity(temporary_descriptor)
        finally:
            os.close(temporary_descriptor)
        _discard_expected_tombstone_at(
            parent_descriptor,
            temporary_name,
            temporary_identity,
            desired_content,
            desired_mode,
            transaction_id=transaction_id,
        )


def _journal_tombstone_candidates(
    parent_descriptor: int, journal_name: str
) -> list[str]:
    prefix = f".{journal_name}."
    return sorted(
        name
        for name in _directory_entry_names(parent_descriptor)
        if name.startswith(prefix)
        and (name.endswith(".rollback") or ".rollback." in name)
    )


def _identity_tombstone_candidates(
    parent_descriptor: int, identity_name: str
) -> list[str]:
    prefix = f".{identity_name}."
    return sorted(
        name
        for name in _directory_entry_names(parent_descriptor)
        if name.startswith(prefix)
        and (name.endswith(".rollback") or ".rollback." in name)
    )


def _quarantine_directory_candidates(parent_descriptor: int) -> list[str]:
    prefix = ".catalog-rollout-quarantine."
    return sorted(
        name
        for name in _directory_entry_names(parent_descriptor)
        if name.startswith(prefix)
    )


def catalog_rollout_transaction_identity_path(repository_root: Path) -> Path:
    return repository_root / "config" / ".catalog-rollout-transaction.identity"


def catalog_rollout_transaction_finalization_path(repository_root: Path) -> Path:
    return repository_root / "config" / ".catalog-rollout-transaction.finalizing"


def _parse_transaction_identity(
    content: bytes,
) -> tuple[str, str]:
    try:
        identity = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("catalog rollout transaction identity is invalid") from error
    transaction_id = identity.get("transaction-id") if isinstance(identity, dict) else None
    journal_sha256 = identity.get("journal-sha256") if isinstance(identity, dict) else None
    if (
        not isinstance(identity, dict)
        or identity.get("schema-version") != TRANSACTION_IDENTITY_SCHEMA_VERSION
        or not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None
        or not isinstance(journal_sha256, str)
        or FULL_SHA256.fullmatch(journal_sha256) is None
    ):
        raise RuntimeError("catalog rollout transaction identity is invalid")
    return transaction_id, journal_sha256


def _parse_published_identity_map(
    published: object,
    *,
    error_message: str,
    allow_empty: bool = True,
) -> dict[str, tuple[int, int]]:
    if not isinstance(published, dict) or (not allow_empty and not published):
        raise RuntimeError(error_message)
    result: dict[str, tuple[int, int]] = {}
    for path, identity in published.items():
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or not isinstance(identity, dict)
            or isinstance(identity.get("device"), bool)
            or not isinstance(identity.get("device"), int)
            or isinstance(identity.get("inode"), bool)
            or not isinstance(identity.get("inode"), int)
            or identity["device"] < 0
            or identity["inode"] <= 0
        ):
            raise RuntimeError(error_message)
        result[path] = (identity["device"], identity["inode"])
    return result


def _parse_transaction_identity_progress(
    content: bytes,
) -> tuple[str, str, dict[str, tuple[int, int]]]:
    try:
        identity = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("catalog rollout transaction identity is invalid") from error
    transaction_id, journal_sha256 = _parse_transaction_identity(content)
    published = _parse_published_identity_map(
        identity.get("published-identities", {}) if isinstance(identity, dict) else {},
        error_message="catalog rollout transaction identity inode evidence is invalid",
    )
    return transaction_id, journal_sha256, published


def _transaction_identity_bytes(
    transaction_id: str,
    journal_sha256: str,
    published_identities: dict[str, tuple[int, int]],
) -> bytes:
    return pretty_json(
        {
            "journal-sha256": journal_sha256,
            "published-identities": {
                path: {"device": identity[0], "inode": identity[1]}
                for path, identity in sorted(published_identities.items())
            },
            "schema-version": TRANSACTION_IDENTITY_SCHEMA_VERSION,
            "transaction-id": transaction_id,
        }
    )


def _parse_transaction_finalization_marker(content: bytes) -> tuple[str, str]:
    try:
        marker = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "catalog rollout transaction finalization marker is invalid"
        ) from error
    transaction_id = marker.get("transaction-id") if isinstance(marker, dict) else None
    journal_sha256 = marker.get("journal-sha256") if isinstance(marker, dict) else None
    if (
        not isinstance(marker, dict)
        or marker.get("schema-version") != TRANSACTION_IDENTITY_SCHEMA_VERSION
        or not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None
        or not isinstance(journal_sha256, str)
        or FULL_SHA256.fullmatch(journal_sha256) is None
    ):
        raise RuntimeError(
            "catalog rollout transaction finalization marker is invalid"
        )
    return transaction_id, journal_sha256


def _parse_finalization_published_identities(
    content: bytes,
) -> dict[str, tuple[int, int]]:
    try:
        marker = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "catalog rollout transaction finalization marker is invalid"
        ) from error
    published = marker.get("published-identities") if isinstance(marker, dict) else None
    if not isinstance(published, dict) or not published:
        raise RuntimeError(
            "catalog rollout transaction finalization marker inode evidence is missing"
        )
    return _parse_published_identity_map(
        published,
        error_message="catalog rollout transaction finalization marker inode evidence is invalid",
        allow_empty=False,
    )


def _validated_identity_tombstones_at(
    parent_descriptor: int,
    identity_name: str,
    *,
    canonical_content: bytes | None = None,
) -> list[tuple[str, tuple[int, int], bytes, int]]:
    valid: list[tuple[str, tuple[int, int], bytes, int]] = []
    for candidate in _identity_tombstone_candidates(parent_descriptor, identity_name):
        state = _capture_transaction_state_at(parent_descriptor, candidate)
        if not state[0] or state[2] is None:
            continue
        _parse_transaction_identity(state[1])
        if canonical_content is not None and state[1] != canonical_content:
            raise RuntimeError(
                "catalog rollout transaction identity tombstone differs from canonical identity"
            )
        descriptor = os.open(candidate, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor)
        try:
            valid.append(
                (
                    candidate,
                    _descriptor_identity(descriptor),
                    state[1],
                    state[2],
                )
            )
        finally:
            os.close(descriptor)
    return valid


def _parse_transaction_journal(content: bytes) -> dict[str, Any]:
    try:
        transaction = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("catalog rollout transaction journal is invalid") from error
    if (
        not isinstance(transaction, dict)
        or transaction.get("schema-version") != TRANSACTION_SCHEMA_VERSION
        or not isinstance(transaction.get("writes"), list)
        or not transaction["writes"]
    ):
        raise RuntimeError("catalog rollout transaction journal is invalid")
    transaction_id = transaction.get("transaction-id")
    if (
        not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None
    ):
        raise RuntimeError("catalog rollout transaction journal is invalid")
    return transaction


def _validate_journal_against_identity(
    content: bytes,
    transaction: dict[str, Any],
    identity: tuple[str, str] | None,
    *,
    require_identity: bool,
) -> None:
    if identity is None:
        if require_identity:
            raise RuntimeError(
                "catalog rollout transaction journal tombstone identity is missing"
            )
        return
    transaction_id, journal_sha256 = identity
    if (
        transaction.get("transaction-id") != transaction_id
        or hashlib.sha256(content).hexdigest() != journal_sha256
    ):
        raise RuntimeError(
            "catalog rollout transaction journal tombstone changed externally"
        )


def _validated_journal_tombstones_at(
    parent_descriptor: int,
    journal_name: str,
    identity: tuple[str, str] | None,
    *,
    canonical_content: bytes | None = None,
) -> list[tuple[str, tuple[int, int], bytes, int]]:
    valid: list[tuple[str, tuple[int, int], bytes, int]] = []
    for candidate in _journal_tombstone_candidates(parent_descriptor, journal_name):
        state = _capture_transaction_state_at(parent_descriptor, candidate)
        if not state[0] or state[2] is None:
            continue
        transaction = _parse_transaction_journal(state[1])
        _validate_journal_against_identity(
            state[1], transaction, identity, require_identity=True
        )
        if canonical_content is not None and state[1] != canonical_content:
            raise RuntimeError(
                "catalog rollout transaction journal tombstone differs from canonical journal"
            )
        descriptor = os.open(candidate, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor)
        try:
            valid.append(
                (
                    candidate,
                    _descriptor_identity(descriptor),
                    state[1],
                    state[2],
                )
            )
        finally:
            os.close(descriptor)
    return valid


def _restore_transaction_journal_tombstone_at(
    parent_descriptor: int,
    journal_name: str,
    identity: tuple[str, str] | None,
) -> tuple[str, tuple[int, int], bytes, int] | None:
    """Restore a journal moved to a rollback tombstone before its unlink."""
    valid = _validated_journal_tombstones_at(parent_descriptor, journal_name, identity)
    if not valid:
        return None
    if len(valid) > 1:
        raise RuntimeError(
            "catalog rollout transaction has ambiguous journal tombstones"
        )
    candidate, identity, content, mode = valid[0]
    try:
        _link_expected_entry_at(
            parent_descriptor,
            candidate,
            parent_descriptor,
            journal_name,
            expected_identity=identity,
        )
    except FileExistsError as error:
        raise RuntimeError(
            "catalog rollout transaction journal changed externally"
        ) from error
    _fsync_directory_fd(parent_descriptor)
    restored = _capture_transaction_state_at(parent_descriptor, journal_name)
    if not _write_state_matches(restored, content, mode):
        raise RuntimeError("catalog rollout transaction journal restore mismatch")
    return candidate, identity, content, mode


def _restore_transaction_identity_tombstone_at(
    parent_descriptor: int,
    identity_name: str,
) -> tuple[str, tuple[int, int], bytes, int] | None:
    """Restore an identity sidecar moved to a rollback tombstone before its unlink."""
    valid = _validated_identity_tombstones_at(parent_descriptor, identity_name)
    if not valid:
        return None
    if len(valid) > 1:
        raise RuntimeError(
            "catalog rollout transaction has ambiguous identity tombstones"
        )
    candidate, identity, content, mode = valid[0]
    try:
        _link_expected_entry_at(
            parent_descriptor,
            candidate,
            parent_descriptor,
            identity_name,
            expected_identity=identity,
        )
    except FileExistsError as error:
        raise RuntimeError(
            "catalog rollout transaction identity changed externally"
        ) from error
    _fsync_directory_fd(parent_descriptor)
    restored = _capture_transaction_state_at(parent_descriptor, identity_name)
    if not _write_state_matches(restored, content, mode):
        raise RuntimeError("catalog rollout transaction identity restore mismatch")
    return candidate, identity, content, mode


def _write_expected_bytes_without_directory_fsync(
    parent_descriptor: int,
    target_name: str,
    content: bytes,
    mode: int,
    *,
    transaction_id: str | None = None,
) -> None:
    """Recreate retry evidence without depending on a second directory fsync.

    This is only used after a directory fsync failure has already made the
    normal atomic writer unusable.  The exclusive hard-link publication keeps
    an externally inserted path from being overwritten while restoring the
    expected bytes for the next recovery attempt.
    """
    temporary_name = f".{target_name}.{os.getpid()}.{uuid.uuid4().hex}.evidence"
    temporary_descriptor: int | None = None
    temporary_identity: tuple[int, int] | None = None
    temporary_mode: int | None = None
    try:
        temporary_descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        os.fchmod(temporary_descriptor, mode)
        temporary_identity = _descriptor_identity(temporary_descriptor)
        temporary_mode = stat.S_IMODE(os.fstat(temporary_descriptor).st_mode)
        view = memoryview(content)
        while view:
            written = os.write(temporary_descriptor, view)
            if written <= 0:
                raise OSError("short write while restoring catalog rollout evidence")
            view = view[written:]
        os.fchmod(temporary_descriptor, mode)
        os.fsync(temporary_descriptor)
        os.close(temporary_descriptor)
        temporary_descriptor = None
        try:
            _rename_no_replace_at(
                parent_descriptor,
                temporary_name,
                parent_descriptor,
                target_name,
                expected_identity=temporary_identity,
            )
        except FileExistsError as error:
            raise RuntimeError(
                f"catalog rollout transaction evidence path changed externally: {target_name}"
            ) from error
        if temporary_identity is None or temporary_mode is None:
            raise RuntimeError("catalog rollout transaction evidence state is unavailable")
        _discard_expected_tombstone_at(
            parent_descriptor,
            temporary_name,
            temporary_identity,
            content,
            temporary_mode,
            sync_directory=False,
            transaction_id=transaction_id,
        )
    finally:
        if temporary_descriptor is not None:
            os.close(temporary_descriptor)
        if temporary_identity is not None and temporary_mode is not None:
            try:
                _discard_expected_tombstone_at(
                    parent_descriptor,
                    temporary_name,
                    temporary_identity,
                    content,
                    temporary_mode,
                    sync_directory=False,
                    transaction_id=transaction_id,
                )
            except (FileNotFoundError, OSError, RuntimeError):
                # Preserve an ambiguous evidence artifact for transaction
                # recovery instead of unlinking a replacement path by name.
                pass


def _ensure_expected_target_at(
    parent_descriptor: int,
    target_name: str,
    expected_content: bytes,
    expected_mode: int,
    *,
    transaction_id: str | None = None,
) -> None:
    current = _capture_transaction_state_at(parent_descriptor, target_name)
    if _write_state_matches(current, expected_content, expected_mode):
        return
    if current[0]:
        raise RuntimeError(
            f"catalog rollout transaction evidence path changed externally: {target_name}"
        )
    _write_expected_bytes_without_directory_fsync(
        parent_descriptor,
        target_name,
        expected_content,
        expected_mode,
        transaction_id=transaction_id,
    )
    restored = _capture_transaction_state_at(parent_descriptor, target_name)
    if not _write_state_matches(restored, expected_content, expected_mode):
        raise RuntimeError(
            f"catalog rollout transaction evidence restore mismatch: {target_name}"
        )


def _remove_expected_target_at(
    parent_descriptor: int,
    target_name: str,
    expected_content: bytes,
    expected_mode: int,
    *,
    transaction_id: str | None = None,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    """Remove one known inode without deleting a replacement at the same name."""
    target_lock = _open_target_lock(parent_descriptor, target_name)
    if target_lock is None:
        raise RuntimeError(
            f"catalog rollout transaction rollback conflict: {target_name}"
        )
    tombstone_name = f".{target_name}.{os.getpid()}.{uuid.uuid4().hex}.rollback"
    moved = False
    try:
        locked_state = _capture_open_descriptor_state(target_lock)
        identity = _descriptor_identity(target_lock)
        if expected_identity is not None and identity != expected_identity:
            raise RuntimeError(
                f"catalog rollout transaction rollback conflict: {target_name}"
            )
        if not _write_state_matches(locked_state, expected_content, expected_mode):
            raise RuntimeError(
                f"catalog rollout transaction rollback conflict: {target_name}"
            )

        path_descriptor = os.open(
            target_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            path_state = _capture_open_descriptor_state(path_descriptor)
            if (
                _descriptor_identity(path_descriptor) != identity
                or not _write_state_matches(path_state, expected_content, expected_mode)
            ):
                raise RuntimeError(
                    f"catalog rollout transaction rollback conflict: {target_name}"
                )
        finally:
            os.close(path_descriptor)

        try:
            _rename_no_replace_at(
                parent_descriptor,
                target_name,
                parent_descriptor,
                tombstone_name,
                expected_identity=identity,
            )
        except RuntimeError as error:
            raise RuntimeError(
                "catalog rollout transaction rollback conflict: "
                f"{target_name}"
            ) from error
        except FileNotFoundError as error:
            try:
                _ensure_expected_target_at(
                    parent_descriptor,
                    target_name,
                    expected_content,
                    expected_mode,
                    transaction_id=transaction_id,
                )
            except BaseException as restore_error:
                raise RuntimeError(
                    "catalog rollout transaction rollback conflict; "
                    f"expected evidence could not be restored: {target_name}"
                ) from restore_error
            raise RuntimeError(
                "catalog rollout transaction rollback conflict; "
                f"target disappeared before removal: {target_name}"
            ) from error
        moved = True

        tombstone_descriptor = os.open(
            tombstone_name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        try:
            tombstone_state = _capture_open_descriptor_state(tombstone_descriptor)
            if (
                _descriptor_identity(tombstone_descriptor) != identity
                or not _write_state_matches(
                    tombstone_state, expected_content, expected_mode
                )
            ):
                raise RuntimeError(
                    f"catalog rollout transaction rollback conflict: {target_name}"
                )
        finally:
            os.close(tombstone_descriptor)

        target_state = _capture_transaction_state_at(parent_descriptor, target_name)
        if target_state[0] or _capture_transaction_state_at(parent_descriptor, target_name)[0]:
            try:
                _discard_expected_tombstone_at(
                    parent_descriptor,
                    tombstone_name,
                    identity,
                    expected_content,
                    expected_mode,
                    transaction_id=transaction_id,
                )
                moved = False
            except BaseException:  # noqa: BLE001 - retry cleanup must preserve external conflicts
                try:
                    _discard_expected_tombstone_at(
                        parent_descriptor,
                        tombstone_name,
                        identity,
                        expected_content,
                        expected_mode,
                        transaction_id=transaction_id,
                    )
                    moved = False
                except BaseException as retry_error:
                    raise RuntimeError(
                        "catalog rollout transaction rollback conflict; "
                        f"rollback tombstone preserved: {tombstone_name}"
                    ) from retry_error
            raise RuntimeError(
                "catalog rollout transaction rollback conflict; "
                "external target appeared before tombstone cleanup"
            )
        try:
            _discard_expected_tombstone_at(
                parent_descriptor,
                tombstone_name,
                identity,
                expected_content,
                expected_mode,
                transaction_id=transaction_id,
            )
        except BaseException:
            # A directory-fsync failure after the owned tombstone was unlinked
            # leaves neither path available for the normal rollback branch.
            # Recreate the evidence path before propagating the failure so a
            # later retry still has an unambiguous journal boundary.
            if not _capture_transaction_state_at(parent_descriptor, target_name)[0] and not _capture_transaction_state_at(
                parent_descriptor, tombstone_name
            )[0]:
                _ensure_expected_target_at(
                    parent_descriptor,
                    target_name,
                    expected_content,
                    expected_mode,
                    transaction_id=transaction_id,
                )
                moved = False
            raise
        moved = False
    except BaseException as error:
        if moved:
            try:
                current = _capture_transaction_state_at(parent_descriptor, target_name)
                if not current[0]:
                    try:
                        _link_expected_entry_at(
                            parent_descriptor,
                            tombstone_name,
                            parent_descriptor,
                            target_name,
                            expected_identity=identity,
                        )
                    except FileExistsError as restore_error:
                        try:
                            _discard_expected_tombstone_at(
                                parent_descriptor,
                                tombstone_name,
                                identity,
                                expected_content,
                                expected_mode,
                                transaction_id=transaction_id,
                            )
                            moved = False
                        except BaseException as cleanup_error:
                            raise RuntimeError(
                                "catalog rollout transaction rollback conflict; "
                                f"rollback tombstone preserved: {tombstone_name}"
                            ) from cleanup_error
                        raise RuntimeError(
                            "catalog rollout transaction rollback conflict; "
                            "external target appeared while restoring"
                        ) from restore_error
                    try:
                        _discard_expected_tombstone_at(
                            parent_descriptor,
                            tombstone_name,
                            identity,
                            expected_content,
                            expected_mode,
                            transaction_id=transaction_id,
                        )
                        moved = False
                    except BaseException as cleanup_error:
                        raise RuntimeError(
                            "catalog rollout transaction rollback conflict; "
                            f"rollback tombstone preserved: {tombstone_name}"
                        ) from cleanup_error
                    moved = False
                    _fsync_directory_fd(parent_descriptor)
            except FileNotFoundError:
                pass
            except RuntimeError as restore_error:
                if moved and "rollback tombstone preserved:" not in str(restore_error):
                    raise RuntimeError(
                        "catalog rollout transaction rollback conflict; "
                        f"rollback tombstone preserved: {tombstone_name}"
                    ) from restore_error
                raise
            except BaseException as restore_error:
                if moved:
                    raise RuntimeError(
                        "catalog rollout transaction rollback conflict; "
                        f"rollback tombstone preserved: {tombstone_name}"
                    ) from restore_error
                raise
        if moved:
            detail = str(error) or error.__class__.__name__
            raise RuntimeError(
                f"{detail}; rollback tombstone preserved: {tombstone_name}"
            ) from error
        raise
    finally:
        if moved:
            # Preserve an ambiguous tombstone for the journal retry path.
            pass
        fcntl.flock(target_lock, fcntl.LOCK_UN)
        os.close(target_lock)


def _atomic_write_bytes_at(
    parent_descriptor: int,
    target_name: str,
    content: bytes,
    *,
    mode: int | None = None,
    expected_state: tuple[bool, bytes, int | None] | None = None,
    transaction_id: str | None = None,
) -> tuple[int, int]:
    if expected_state is not None and not _transaction_state_matches(
        _capture_transaction_state_at(parent_descriptor, target_name),
        *expected_state,
    ):
        raise RuntimeError(
            f"catalog rollout transaction target changed externally: {target_name}"
        )
    target_lock = _open_target_lock(parent_descriptor, target_name)
    locked_state = (False, b"", None)
    artifact_transaction_id = transaction_id or "orphan"
    temporary_name = (
        f".{target_name}.{artifact_transaction_id}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    temporary_descriptor: int | None = None
    temporary_identity: tuple[int, int] | None = None
    temporary_mode: int | None = None
    replacement_lock: int | None = None
    replacement_guard_name: str | None = None
    replacement_guard_identity: tuple[int, int] | None = None
    replacement_guard_moved = False
    replacement_guard_preserved = False
    temporary_cleanup_error: BaseException | None = None
    published_identity: tuple[int, int] | None = None
    try:
        if target_lock is not None:
            locked_state = _capture_open_descriptor_state(target_lock)
        temporary_descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        if mode is not None:
            os.fchmod(temporary_descriptor, mode)
        view = memoryview(content)
        while view:
            written = os.write(temporary_descriptor, view)
            if written <= 0:
                raise OSError("short write while committing catalog rollout")
            view = view[written:]
        if mode is not None:
            os.fchmod(temporary_descriptor, mode)
        temporary_identity = _descriptor_identity(temporary_descriptor)
        temporary_mode = stat.S_IMODE(os.fstat(temporary_descriptor).st_mode)
        os.fsync(temporary_descriptor)
        os.close(temporary_descriptor)
        temporary_descriptor = None

        if expected_state is not None and not _transaction_state_matches(
            _capture_transaction_state_at(parent_descriptor, target_name),
            *expected_state,
        ):
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {target_name}"
            )
        if locked_state[0]:
            if expected_state is not None and not _transaction_state_matches(
                _capture_open_descriptor_state(target_lock), *expected_state
            ):
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target_name}"
                )
            replacement_guard_name = (
                f".{target_name}.{artifact_transaction_id}.{os.getpid()}.{uuid.uuid4().hex}.replace"
            )
            try:
                # Move the old inode to a unique guard first.  The destination
                # is never the live target name, so a concurrent path-entry
                # replacement cannot be overwritten by this operation.
                _rename_no_replace_at(
                    parent_descriptor,
                    target_name,
                    parent_descriptor,
                    replacement_guard_name,
                    expected_identity=_descriptor_identity(target_lock),
                )
            except (FileNotFoundError, RuntimeError) as error:
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target_name}"
                ) from error
            replacement_guard_moved = True
            guard_descriptor = os.open(
                replacement_guard_name,
                _TARGET_OPEN_FLAGS,
                dir_fd=parent_descriptor,
            )
            try:
                guard_state = _capture_open_descriptor_state(guard_descriptor)
                replacement_guard_identity = _descriptor_identity(guard_descriptor)
                if (
                    replacement_guard_identity != _descriptor_identity(target_lock)
                    or not _transaction_state_matches(guard_state, *locked_state)
                ):
                    try:
                        _rename_no_replace_at(
                            parent_descriptor,
                            replacement_guard_name,
                            parent_descriptor,
                            target_name,
                            expected_identity=replacement_guard_identity,
                        )
                    except FileExistsError as restore_error:
                        replacement_guard_preserved = True
                        raise RuntimeError(
                            f"catalog rollout transaction target changed externally; "
                            f"replacement guard preserved: {replacement_guard_name}"
                        ) from restore_error
                    replacement_guard_moved = False
                    raise RuntimeError(
                        f"catalog rollout transaction target changed externally: {target_name}"
                    )
            finally:
                os.close(guard_descriptor)
            try:
                _rename_no_replace_at(
                    parent_descriptor,
                    temporary_name,
                    parent_descriptor,
                    target_name,
                    expected_identity=temporary_identity,
                )
            except FileExistsError as error:
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target_name}"
                ) from error
            if temporary_identity is None or temporary_mode is None:
                raise RuntimeError("catalog rollout transaction temporary state is unavailable")
        else:
            try:
                _rename_no_replace_at(
                    parent_descriptor,
                    temporary_name,
                    parent_descriptor,
                    target_name,
                    expected_identity=temporary_identity,
                )
            except FileExistsError as error:
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target_name}"
                ) from error
            if temporary_identity is None or temporary_mode is None:
                raise RuntimeError("catalog rollout transaction temporary state is unavailable")
        if locked_state[0]:
            replaced_lock_state = _capture_open_descriptor_state(target_lock)
            if not _transaction_state_matches(replaced_lock_state, *locked_state):
                replacement_guard_preserved = True
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally; "
                    f"replacement guard preserved: {replacement_guard_name}"
                )

        observed_state = _capture_transaction_state_at(parent_descriptor, target_name)
        if not _write_state_matches(observed_state, content, mode):
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {target_name}"
            )

        replacement_lock = _open_target_lock(parent_descriptor, target_name)
        if replacement_lock is None or temporary_identity is None:
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {target_name}"
            )
        if (
            _descriptor_identity(replacement_lock) != temporary_identity
            or not _write_state_matches(
                _capture_open_descriptor_state(replacement_lock), content, mode
            )
            or _capture_transaction_identity_at(parent_descriptor, target_name)
            != temporary_identity
        ):
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {target_name}"
            )
        _fsync_directory_fd(parent_descriptor)
        if (
            _descriptor_identity(replacement_lock) != temporary_identity
            or not _write_state_matches(
                _capture_open_descriptor_state(replacement_lock), content, mode
            )
            or _capture_transaction_identity_at(parent_descriptor, target_name)
            != temporary_identity
            or not _write_state_matches(
                _capture_transaction_state_at(parent_descriptor, target_name),
                content,
                mode,
            )
        ):
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {target_name}"
            )
        if (
            replacement_guard_moved
            and not replacement_guard_preserved
            and replacement_guard_name is not None
            and replacement_guard_identity is not None
        ):
            _discard_expected_tombstone_at(
                parent_descriptor,
                replacement_guard_name,
                replacement_guard_identity,
                locked_state[1],
                locked_state[2] if locked_state[2] is not None else 0o644,
                transaction_id=transaction_id,
            )
            replacement_guard_moved = False
        if temporary_identity is None:
            raise RuntimeError("catalog rollout transaction published inode is unavailable")
        # Keep the inode captured while the replacement lock and the parent
        # descriptor are still anchored.  Callers must use this identity
        # directly; looking the target up again after this function returns
        # creates a same-bytes replacement window between publish and journal
        # ownership recording.
        published_identity = temporary_identity
    finally:
        if temporary_descriptor is not None:
            os.close(temporary_descriptor)
        try:
            if temporary_identity is not None and temporary_mode is not None:
                _discard_expected_tombstone_at(
                    parent_descriptor,
                    temporary_name,
                    temporary_identity,
                    content,
                    temporary_mode,
                    sync_directory=False,
                    transaction_id=transaction_id,
                )
        except (OSError, RuntimeError) as cleanup_error:
            # Preserve an ambiguous temporary artifact for the transaction
            # recovery pass instead of deleting a replacement path by name,
            # but never report a successful transaction while cleanup failed.
            temporary_cleanup_error = cleanup_error
        if target_lock is not None:
            fcntl.flock(target_lock, fcntl.LOCK_UN)
            os.close(target_lock)
        if replacement_lock is not None:
            fcntl.flock(replacement_lock, fcntl.LOCK_UN)
            os.close(replacement_lock)
        if (
            replacement_guard_moved
            and not replacement_guard_preserved
            and replacement_guard_name is not None
            and replacement_guard_identity is not None
        ):
            try:
                current = _capture_transaction_state_at(parent_descriptor, target_name)
                if not current[0] and locked_state[0]:
                    _link_expected_entry_at(
                        parent_descriptor,
                        replacement_guard_name,
                        parent_descriptor,
                        target_name,
                        expected_identity=replacement_guard_identity,
                    )
                    _discard_expected_tombstone_at(
                        parent_descriptor,
                        replacement_guard_name,
                        replacement_guard_identity,
                        locked_state[1],
                        locked_state[2]
                        if locked_state[2] is not None
                        else TRANSACTION_NEW_FILE_MODE,
                        sync_directory=False,
                        transaction_id=transaction_id,
                    )
                    _fsync_directory_fd(parent_descriptor)
                    replacement_guard_moved = False
                elif _write_state_matches(
                    _capture_transaction_state_at(
                        parent_descriptor, replacement_guard_name
                    ),
                    locked_state[1],
                    locked_state[2],
                ):
                    _discard_expected_tombstone_at(
                        parent_descriptor,
                        replacement_guard_name,
                        replacement_guard_identity,
                        locked_state[1],
                        locked_state[2] if locked_state[2] is not None else 0o644,
                        transaction_id=transaction_id,
                    )
                    replacement_guard_moved = False
            except (OSError, RuntimeError):
                # Keep an unambiguous guard when cleanup races with an
                # external path change; the transaction journal remains the
                # retry authority.
                replacement_guard_preserved = True
        if temporary_cleanup_error is not None:
            raise RuntimeError(
                "catalog rollout transaction temporary cleanup failed; "
                f"artifact preserved: {temporary_name}"
            ) from temporary_cleanup_error
    if published_identity is None:
        raise RuntimeError("catalog rollout transaction published inode is unavailable")
    return published_identity


def atomic_write_bytes(
    path: Path,
    content: bytes,
    *,
    mode: int | None = None,
    expected_state: tuple[bool, bytes, int | None] | None = None,
    parent_descriptor: int | None = None,
    target_name: str | None = None,
    transaction_id: str | None = None,
) -> tuple[int, int] | None:
    if parent_descriptor is not None:
        return _atomic_write_bytes_at(
            parent_descriptor,
            target_name or path.name,
            content,
            mode=mode,
            expected_state=expected_state,
            transaction_id=transaction_id,
        )
    if expected_state is not None and not _transaction_state_matches(
        _capture_transaction_state(path), *expected_state
    ):
        raise RuntimeError(
            f"catalog rollout transaction target changed externally: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    temporary_identity: tuple[int, int] | None = None
    temporary_mode: int | None = None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(content)
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_identity = _descriptor_identity(stream.fileno())
            temporary_mode = stat.S_IMODE(os.fstat(stream.fileno()).st_mode)
        if expected_state is not None and not _transaction_state_matches(
            _capture_transaction_state(path), *expected_state
        ):
            raise RuntimeError(
                f"catalog rollout transaction target changed externally: {path}"
            )
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
        # Path-based callers do not use the returned inode for journal
        # ownership; only the descriptor-anchored transaction path needs it.
        return None
    finally:
        if temporary_identity is not None and temporary_mode is not None:
            _unlink_expected_path_if_present(
                temporary_path,
                temporary_identity,
                content,
                temporary_mode,
            )


def write_immutable_bytes(path: Path, content: bytes) -> None:
    absolute_path = path.absolute()
    if not absolute_path.name or absolute_path == Path(absolute_path.anchor):
        raise RuntimeError("immutable rollout snapshot file path is invalid")
    root_descriptor = os.open(Path(absolute_path.anchor), _DIRECTORY_OPEN_FLAGS)
    parent_descriptor: int | None = None
    temporary_name = f".{absolute_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    temporary_identity: tuple[int, int] | None = None
    try:
        parent_descriptor = _open_or_create_directory_at(
            root_descriptor,
            absolute_path.relative_to(Path(absolute_path.anchor)).parts[:-1],
        )
        _assert_directory_descriptor_matches_path(parent_descriptor, absolute_path.parent)
        _recover_immutable_cleanup_artifacts_at(
            parent_descriptor, absolute_path.name, content
        )
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_identity = _descriptor_identity(stream.fileno())
        try:
            _assert_directory_descriptor_matches_path(
                parent_descriptor, absolute_path.parent
            )
            _rename_no_replace_at(
                parent_descriptor,
                temporary_name,
                parent_descriptor,
                absolute_path.name,
                expected_identity=temporary_identity,
            )
        except FileExistsError:
            _assert_directory_descriptor_matches_path(
                parent_descriptor, absolute_path.parent
            )
            try:
                existing_descriptor = os.open(
                    absolute_path.name, _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
                )
            except OSError as error:
                raise RuntimeError(
                    f"immutable rollout snapshot differs: {absolute_path}"
                ) from error
            try:
                existing_state = _capture_open_descriptor_state(existing_descriptor)
            finally:
                os.close(existing_descriptor)
            if existing_state[1] != content:
                raise RuntimeError(f"immutable rollout snapshot differs: {absolute_path}")
        else:
            _assert_directory_descriptor_matches_path(
                parent_descriptor, absolute_path.parent
            )
            _fsync_directory_fd(parent_descriptor)
            _assert_directory_descriptor_matches_path(
                parent_descriptor, absolute_path.parent
            )
        finally:
            if temporary_identity is not None:
                temporary_path_identity = _capture_transaction_identity_at(
                    parent_descriptor, temporary_name
                )
                if temporary_path_identity is None:
                    pass
                elif temporary_path_identity != temporary_identity:
                    raise RuntimeError(
                        "immutable rollout snapshot temporary artifact changed externally"
                    )
                else:
                    _unlink_expected_entry_at(
                        parent_descriptor,
                        temporary_name,
                        temporary_identity,
                        content,
                        0o600,
                        quarantine_directory=False,
                    )
    finally:
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        os.close(root_descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def catalog_rollout_transaction_path(repository_root: Path) -> Path:
    return repository_root / "config" / ".catalog-rollout-transaction.json"


def catalog_rollout_transaction_lock_path(repository_root: Path) -> Path:
    return repository_root / ".bluetape" / "catalog-rollout-transaction.lock"


@contextmanager
def _catalog_rollout_transaction_lock(repository_root: Path):
    root = repository_root.resolve()
    root_descriptor = os.open(root, _DIRECTORY_OPEN_FLAGS)
    state_descriptor: int | None = None
    lock_descriptor: int | None = None
    root_locked = False
    try:
        # Lock the stable repository-root inode before opening the mutable
        # `.bluetape` path.  This keeps cooperating transactions serialized even
        # if that directory is renamed and recreated during the operation.
        fcntl.flock(root_descriptor, fcntl.LOCK_EX)
        root_locked = True
        _assert_root_descriptor_matches_path(root_descriptor, root)
        try:
            os.mkdir(".bluetape", 0o755, dir_fd=root_descriptor)
        except FileExistsError:
            pass
        state_descriptor = os.open(
            ".bluetape", _DIRECTORY_OPEN_FLAGS, dir_fd=root_descriptor
        )
        lock_descriptor = os.open(
            "catalog-rollout-transaction.lock",
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=state_descriptor,
        )
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        try:
            yield root_descriptor
        finally:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise RuntimeError(
                "catalog rollout transaction lock path must not contain symlinks"
            ) from error
        raise
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if state_descriptor is not None:
            os.close(state_descriptor)
        if root_locked:
            fcntl.flock(root_descriptor, fcntl.LOCK_UN)
        os.close(root_descriptor)


def _capture_transaction_state(target: Path) -> tuple[bool, bytes, int | None]:
    if target.is_symlink():
        raise RuntimeError(f"catalog rollout transaction target must be a regular file: {target}")
    try:
        metadata = target.stat()
    except FileNotFoundError:
        return False, b"", None
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"catalog rollout transaction target must be a regular file: {target}")
    return True, target.read_bytes(), stat.S_IMODE(metadata.st_mode)


def _transaction_state_matches(
    current: tuple[bool, bytes, int | None],
    expected_exists: bool,
    expected_content: bytes,
    expected_mode: int | None,
) -> bool:
    return current == (expected_exists, expected_content, expected_mode)


def validate_receipt_destination(receipt_path: Path, repository_root: Path) -> Path:
    """Validate a receipt output before a caller starts any write."""
    root = repository_root.resolve()
    raw_path = str(receipt_path)
    if "\\" in raw_path or any(
        part in {".", ".."} for part in raw_path.split("/")
    ):
        raise RuntimeError("resolved graph receipt path must stay in the repository")
    lexical_root = repository_root.absolute()
    unresolved = (
        receipt_path if receipt_path.is_absolute() else lexical_root / receipt_path
    )
    relative = None
    for root_candidate in (lexical_root, root):
        try:
            relative = unresolved.absolute().relative_to(root_candidate)
            break
        except ValueError:
            continue
    if relative is None:
        raise RuntimeError("resolved graph receipt path must stay in the repository")
    target, _relative = _validate_relative_repository_path(
        root, relative.as_posix(), "resolved graph receipt"
    )
    target = target.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise RuntimeError("resolved graph receipt path must stay in the repository") from error
    if target.is_symlink():
        raise RuntimeError("resolved graph receipt must be a regular file")
    if target.exists() and not target.is_file():
        raise RuntimeError("resolved graph receipt must be a regular file")
    return target


def _immutable_rollout_path(rollout: str, relative_path: object, label: str) -> str:
    _validate_snapshot_segment(rollout, "rollout")
    if not isinstance(relative_path, str) or not relative_path:
        raise RuntimeError(f"{label} path is required")
    if any(part in {".", ".."} for part in relative_path.replace("\\", "/").split("/")):
        raise RuntimeError(f"{label} must use an immutable snapshot")
    path = Path(relative_path)
    prefix = Path("config") / "rollouts" / rollout
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"{label} must use an immutable snapshot")
    try:
        path.relative_to(prefix)
    except ValueError as error:
        raise RuntimeError(f"{label} must use an immutable snapshot") from error
    if path == prefix:
        raise RuntimeError(f"{label} must use an immutable snapshot")
    return path.as_posix()


def _validate_snapshot_segment(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9._-]+", value) is None
        or not re.search(r"[A-Za-z0-9_-]", value)
    ):
        raise RuntimeError(f"{label} is not safe for an immutable snapshot path")
    return value


def _validate_relative_repository_path(
    repository_root: Path, relative_path: object, label: str
) -> tuple[Path, str]:
    if not isinstance(relative_path, str) or not relative_path:
        raise RuntimeError(f"{label} path is required")
    if "\\" in relative_path or any(
        part in {".", ".."} for part in relative_path.split("/")
    ):
        raise RuntimeError(f"{label} path must stay inside the repository")
    path = Path(relative_path)
    if path.is_absolute():
        raise RuntimeError(f"{label} path must stay inside the repository")
    root = repository_root.resolve()
    target = root / path
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"{label} path must not contain symlinks")
    try:
        target.resolve(strict=False).relative_to(root)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"{label} path escapes the repository") from error
    return target, path.as_posix()


def _require_immutable_rollout_row(
    rollout: str, row: dict[str, Any], *, require_receipt: bool = True
) -> None:
    _immutable_rollout_path(rollout, row.get("audit"), "verified rollout audit")
    _immutable_rollout_path(
        rollout,
        row.get("authority-delta-ledger"),
        "verified rollout delta-ledger",
    )
    for field, label in (
        ("audit-sha256", "verified rollout audit SHA"),
        ("authority-delta-ledger-sha256", "verified rollout delta-ledger SHA"),
    ):
        if FULL_SHA256.fullmatch(str(row.get(field, ""))) is None:
            raise RuntimeError(f"{label} is invalid")
    evidence = row.get("resolved-graph-evidence")
    if not require_receipt and evidence in (None, []):
        return
    if not isinstance(evidence, dict):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "verified rollout lacks immutable resolved graph receipt"
        )
    _immutable_rollout_path(
        rollout, evidence.get("path"), "verified rollout resolved graph receipt"
    )
    if FULL_SHA256.fullmatch(str(evidence.get("sha256", ""))) is None:
        raise RuntimeError("verified rollout resolved graph receipt SHA is invalid")


def is_legacy_rollout_row(row: dict[str, Any]) -> bool:
    """Return whether a row is the explicitly preserved pre-immutable record."""
    return (
        row.get("status") == LEGACY_VERIFIED_ROLLOUT_STATUS
        and row.get("evidence-status") == "legacy-superseded"
    )


def validate_legacy_rollout_contract(row: dict[str, Any]) -> None:
    """Validate the preserved shape of a legacy rollout with unavailable lineage."""
    if not is_legacy_rollout_row(row):
        raise RuntimeError("central rollout row is not an explicit legacy verified row")
    if not isinstance(row.get("rollout"), str) or not row["rollout"]:
        raise RuntimeError("legacy central rollout row requires a rollout name")
    if FULL_SHA256.fullmatch(str(row.get("catalog-sha256", ""))) is None:
        raise RuntimeError("legacy central rollout row catalog SHA is invalid")
    receipt = row.get("candidate-receipt")
    if not isinstance(receipt, str) or not receipt:
        raise RuntimeError("legacy central rollout row requires candidate-receipt")
    path = Path(receipt)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError("legacy central rollout row candidate-receipt path is invalid")
    if row.get("authority-delta-ledger") is not None:
        raise RuntimeError("legacy central rollout row cannot claim its missing authority ledger")
    superseding = row.get("superseding-local-candidate")
    if not isinstance(superseding, dict) or superseding.get("status") != "verified-local-candidate":
        raise RuntimeError("legacy central rollout row requires its superseding local candidate")
    if FULL_SHA256.fullmatch(str(superseding.get("catalog-sha256", ""))) is None:
        raise RuntimeError("legacy superseding candidate catalog SHA is invalid")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(superseding.get("catalog-commit", ""))):
        raise RuntimeError("legacy superseding candidate commit is invalid")
    if not isinstance(row.get("resolved-graph-evidence"), list):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "legacy central rollout row requires inline graph evidence"
        )
    if row.get("audit") is not None or row.get("audit-sha256") is not None:
        raise RuntimeError("legacy central rollout row cannot claim immutable audit evidence")
    if not isinstance(row.get("evidence-exception"), str) or not row["evidence-exception"].strip():
        raise RuntimeError("legacy central rollout row requires an evidence exception")


def _rollout_resolution_contract(ledger: dict[str, Any]) -> dict[str, Any]:
    excluded_top = {
        "candidate-validation-evidence",
        "resolved-graph-evidence",
        "status",
    }
    contract = {
        key: copy.deepcopy(value)
        for key, value in ledger.items()
        if key not in excluded_top and key != "delta"
    }
    contract["delta"] = [
        {
            key: copy.deepcopy(value)
            for key, value in entry.items()
            if key not in {"resolved-graph-specs", "verification"}
        }
        for entry in ledger.get("delta", [])
    ]
    return contract


def _transaction_write_map(
    repository_root: Path, pending_writes: list[tuple[Path, bytes]] | None
) -> dict[str, bytes]:
    root = repository_root.resolve()
    writes: dict[str, bytes] = {}
    for path, content in pending_writes or []:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as error:
            raise RuntimeError("catalog rollout transaction path escapes repository") from error
        writes[relative] = content
    return writes


def _transaction_read(
    repository_root: Path,
    relative_path: str,
    label: str,
    pending_writes: dict[str, bytes],
) -> bytes:
    if relative_path in pending_writes:
        return pending_writes[relative_path]
    return _read_repo_file(repository_root, relative_path, label)


def _validate_cross_file_rollout_evidence(
    repository_root: Path,
    pending_writes: list[tuple[Path, bytes]] | None = None,
) -> None:
    repository_root = repository_root.resolve()
    overlay = _transaction_write_map(repository_root, pending_writes)
    central_path = repository_root / "config" / "central-catalog-version-deltas.json"
    authority_path = repository_root / "config" / "latest-stable-version-deltas.json"
    central_relative = "config/central-catalog-version-deltas.json"
    authority_relative = "config/latest-stable-version-deltas.json"
    if central_relative not in overlay and not central_path.is_file():
        return
    if authority_relative not in overlay and not authority_path.is_file():
        return
    try:
        central = json.loads(
            _transaction_read(repository_root, central_relative, "central ledger", overlay)
        )
        authority = json.loads(
            _transaction_read(repository_root, authority_relative, "authority ledger", overlay)
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("cross-file rollout evidence is invalid") from error
    try:
        if not isinstance(central, dict) or not isinstance(authority, dict):
            raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
                "central and current authority ledgers must be objects"
            )
        rows = central.get("subsequent-rollouts")
        if not isinstance(rows, list):
            raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
                "central catalog rollout rows are invalid"
            )
        loaded_by_rollout: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("status") not in {
                "validation-pending",
                "verified",
                "verified-resolved-graph",
            }:
                continue
            rollout = row.get("rollout")
            if not isinstance(rollout, str) or not rollout:
                raise RuntimeError("central catalog rollout name is invalid")
            if is_legacy_rollout_row(row):
                validate_legacy_rollout_contract(row)
                continue
            _require_immutable_rollout_row(
                rollout,
                row,
                require_receipt=row.get("status") == "verified-resolved-graph",
            )
            loaded, _audit, _artifacts = load_catalog_rollout_evidence(
                central,
                rollout,
                repository_root,
                pending_writes=overlay,
            )
            if loaded.get("status") != row.get("status"):
                raise RuntimeError("central rollout status does not match its delta-ledger")
            if row.get("delta-count") is not None and row["delta-count"] != len(
                loaded.get("delta", [])
            ):
                raise RuntimeError("central rollout delta count does not match its ledger")
            if row.get("baseline-catalog-ref") is not None and row[
                "baseline-catalog-ref"
            ] != loaded.get("baseline", {}).get("catalog-ref"):
                raise RuntimeError("central rollout baseline does not match its ledger")
            row_graph = row.get("resolved-graph-evidence") or []
            ledger_graph = loaded.get("resolved-graph-evidence") or []
            if row_graph != ledger_graph:
                raise RuntimeError("central rollout graph evidence does not match its ledger")
            loaded_by_rollout[rollout] = loaded

        rollout = authority.get("rollout")
        if not isinstance(rollout, str):
            raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
                "current authority rollout is invalid"
            )
        if is_legacy_rollout_row(_one_rollout_row(central, rollout)):
            raise RuntimeError("current authority cannot use a legacy verified rollout")
        snapshot_authority = loaded_by_rollout.get(rollout)
        if snapshot_authority is None:
            snapshot_authority, _, _ = load_catalog_rollout_evidence(
                central,
                rollout,
                repository_root,
                pending_writes=overlay,
            )
        if snapshot_authority.get("status") != authority.get("status"):
            raise RuntimeError("transaction status does not match central evidence")
        if snapshot_authority.get("candidate-validation-evidence") != authority.get(
            "candidate-validation-evidence"
        ):
            raise RuntimeError("transaction candidate-validation evidence does not match")
        normalized_snapshot = copy.deepcopy(snapshot_authority)
        normalized_current = copy.deepcopy(authority)
        if isinstance(normalized_snapshot.get("audit"), dict) and isinstance(
            normalized_current.get("audit"), dict
        ):
            normalized_snapshot["audit"]["path"] = normalized_current["audit"].get("path")
        if _rollout_resolution_contract(normalized_snapshot) != _rollout_resolution_contract(
            normalized_current
        ):
            raise RuntimeError("transaction resolution contract does not match central evidence")
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise RuntimeError("cross-file rollout evidence is invalid") from error


def _transaction_target(repository_root: Path, relative_path: object) -> Path:
    root = repository_root.resolve()
    target, _relative = _validate_relative_repository_path(
        root, relative_path, "catalog rollout transaction"
    )
    if target in {
        catalog_rollout_transaction_path(root),
        catalog_rollout_transaction_identity_path(root),
        catalog_rollout_transaction_finalization_path(root),
        catalog_rollout_transaction_lock_path(root),
    }:
        raise RuntimeError("catalog rollout transaction cannot replace its journal")
    return target


def _transaction_input_relative_path(
    repository_root: Path, path: Path
) -> str:
    root = repository_root.resolve()
    lexical_root = repository_root.absolute()
    candidate = path if path.is_absolute() else lexical_root / path
    candidate = candidate.absolute()
    for base in (lexical_root, root):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    raise RuntimeError("catalog rollout transaction path escapes repository")


def _restore_transaction_target(
    target: Path,
    prior_exists: bool,
    prior_content: bytes,
    prior_mode: int | None,
    desired_content: bytes,
    desired_mode: int,
    *,
    parent_descriptor: int | None = None,
    target_name: str | None = None,
    desired_identity: tuple[int, int] | None | object = _MISSING_DESIRED_IDENTITY,
    transaction_id: str | None = None,
) -> None:
    """Restore a target only when its current bytes match this transaction."""
    if parent_descriptor is None:
        current_exists, current_content, current_mode = _capture_transaction_state(target)
    else:
        current_exists, current_content, current_mode = _capture_transaction_state_at(
            parent_descriptor, target_name or target.name
        )
    if _transaction_state_matches(
        (current_exists, current_content, current_mode),
        prior_exists,
        prior_content,
        prior_mode,
    ):
        return
    if not _transaction_state_matches(
        (current_exists, current_content, current_mode),
        True,
        desired_content,
        desired_mode,
    ):
        raise RuntimeError(f"catalog rollout transaction rollback conflict: {target}")
    if parent_descriptor is None:
        identity_parent = os.open(target.parent, _DIRECTORY_OPEN_FLAGS)
        try:
            current_identity = _capture_transaction_identity_at(
                identity_parent, target.name
            )
        finally:
            os.close(identity_parent)
    else:
        current_identity = _capture_transaction_identity_at(
            parent_descriptor, target_name or target.name
        )
    if (
        desired_identity is not _MISSING_DESIRED_IDENTITY
        and (desired_identity is None or current_identity != desired_identity)
    ):
        raise RuntimeError(
            f"catalog rollout transaction rollback inode conflict: {target}"
        )

    if prior_exists:
        if prior_mode is None:
            raise RuntimeError(f"catalog rollout transaction rollback state is invalid: {target}")
        expected_state = (True, desired_content, desired_mode)
        atomic_write_bytes(
            target,
            prior_content,
            mode=prior_mode,
            expected_state=expected_state,
            parent_descriptor=parent_descriptor,
            target_name=target_name,
            transaction_id=transaction_id,
        )
        if parent_descriptor is None:
            restored_state = _capture_transaction_state(target)
        else:
            restored_state = _capture_transaction_state_at(
                parent_descriptor, target_name or target.name
            )
        if not _transaction_state_matches(restored_state, True, prior_content, prior_mode):
            raise RuntimeError(f"catalog rollout transaction rollback mismatch: {target}")
        return

    if parent_descriptor is None:
        parent_descriptor = os.open(target.parent, _DIRECTORY_OPEN_FLAGS)
        try:
            _remove_expected_target_at(
                parent_descriptor,
                target_name or target.name,
                desired_content,
                desired_mode,
                transaction_id=transaction_id,
            )
            still_exists = _capture_transaction_state_at(
                parent_descriptor, target_name or target.name
            )[0]
        finally:
            os.close(parent_descriptor)
    else:
        _remove_expected_target_at(
            parent_descriptor,
            target_name or target.name,
            desired_content,
            desired_mode,
            transaction_id=transaction_id,
        )
        still_exists = _capture_transaction_state_at(
            parent_descriptor, target_name or target.name
        )[0]
    if still_exists:
        raise RuntimeError(f"catalog rollout transaction rollback mismatch: {target}")


def _recover_catalog_rollout_transaction(
    repository_root: Path,
    root_descriptor: int,
    *,
    journal_parent_descriptor: int | None = None,
    journal_name: str | None = None,
    target_parent_descriptors: dict[str, int] | None = None,
) -> bool:
    repository_root = repository_root.resolve()
    _assert_root_descriptor_matches_path(root_descriptor, repository_root)
    journal_path = catalog_rollout_transaction_path(repository_root)
    if (journal_parent_descriptor is None) != (journal_name is None):
        raise RuntimeError("catalog rollout transaction journal descriptor is incomplete")
    if journal_parent_descriptor is None:
        journal_parent, journal_name = _open_anchored_parent(
            root_descriptor, repository_root, journal_path
        )
    else:
        _assert_directory_descriptor_matches_path(
            journal_parent_descriptor, journal_path.parent
        )
        journal_parent = os.dup(journal_parent_descriptor)
    supplied_target_parents = target_parent_descriptors or {}
    try:
        journal_state, journal_identity = _capture_transaction_state_and_identity_at(
            journal_parent, journal_name
        )
        identity_path = catalog_rollout_transaction_identity_path(repository_root)
        identity_name = identity_path.name
        identity_state, identity_identity = _capture_transaction_state_and_identity_at(
            journal_parent, identity_name
        )
        finalization_path = catalog_rollout_transaction_finalization_path(repository_root)
        finalization_name = finalization_path.name
        finalization_state, finalization_identity = _capture_transaction_state_and_identity_at(
            journal_parent, finalization_name
        )
        journal_candidates = _journal_tombstone_candidates(journal_parent, journal_name)
        identity_candidates = _identity_tombstone_candidates(
            journal_parent, identity_name
        )
        identity_tombstone_artifacts: list[tuple[str, tuple[int, int], bytes, int]] = []
        # A crash can leave the journal in place while the identity sidecar is
        # already moved to its rollback tombstone.  Restore that sidecar before
        # parsing the journal or its finalization marker so v2 recovery retains
        # the same identity boundary as the original transaction.
        if (
            not identity_state[0]
            and identity_candidates
            and (journal_state[0] or journal_candidates or finalization_state[0])
        ):
            identity_tombstone_artifacts = _validated_identity_tombstones_at(
                journal_parent, identity_name
            )
            restored_identity = _restore_transaction_identity_tombstone_at(
                journal_parent, identity_name
            )
            if restored_identity is None:
                raise RuntimeError(
                    "catalog rollout transaction journal tombstone identity is missing"
                )
            identity_state, identity_identity = _capture_transaction_state_and_identity_at(
                journal_parent, identity_name
            )
            identity_candidates = _identity_tombstone_candidates(
                journal_parent, identity_name
            )
        transaction_identity = (
            _parse_transaction_identity(identity_state[1])
            if identity_state[0]
            else None
        )
        progress_published_identities: dict[str, tuple[int, int]] = {}
        if identity_state[0]:
            (
                _progress_transaction_id,
                _progress_journal_sha256,
                progress_published_identities,
            ) = _parse_transaction_identity_progress(identity_state[1])
        preliminary_transaction_id = (
            transaction_identity[0] if transaction_identity is not None else None
        )
        if preliminary_transaction_id is None and journal_state[0]:
            preliminary_transaction_id = _parse_transaction_journal(
                journal_state[1]
            )["transaction-id"]
        if preliminary_transaction_id is None and finalization_state[0]:
            preliminary_transaction_id = _parse_transaction_finalization_marker(
                finalization_state[1]
            )[0]
        quarantine_transaction_ids = _recover_quarantine_directories_at(
            journal_parent,
            expected_transaction_id=preliminary_transaction_id,
            allow_orphan=False,
        )
        finalization_recovery = False
        finalization_published_identities: dict[str, tuple[int, int]] = {}
        if finalization_state[0]:
            marker_identity = _parse_transaction_finalization_marker(
                finalization_state[1]
            )
            if transaction_identity is not None and marker_identity != transaction_identity:
                raise RuntimeError(
                    "catalog rollout transaction finalization marker changed externally"
                )
            finalization_recovery = True
            finalization_published_identities = _parse_finalization_published_identities(
                finalization_state[1]
            )
            if transaction_identity is None:
                transaction_identity = marker_identity
        if transaction_identity is not None:
            unexpected_quarantine_ids = {
                value
                for value in quarantine_transaction_ids
                if value not in {"orphan", transaction_identity[0]}
            }
            if unexpected_quarantine_ids or (
                transaction_identity[0] not in quarantine_transaction_ids
                and "orphan" in quarantine_transaction_ids
                and (journal_state[0] or identity_state[0] or finalization_state[0])
            ):
                raise RuntimeError(
                    "catalog rollout transaction quarantine belongs to another transaction"
                )
        journal_tombstone_artifacts: list[tuple[str, tuple[int, int], bytes, int]] = []
        if not journal_state[0]:
            if not journal_candidates:
                if identity_state[0] or finalization_state[0]:
                    raise RuntimeError(
                        "catalog rollout transaction journal is missing while identity evidence remains"
                    )
                if identity_candidates:
                    identity_tombstone_artifacts = _validated_identity_tombstones_at(
                        journal_parent,
                        identity_name,
                        canonical_content=identity_state[1]
                        if identity_state[0]
                        else None,
                    )
                    if transaction_identity is not None:
                        for (
                            _candidate,
                            _candidate_identity,
                            candidate_content,
                            _candidate_mode,
                        ) in identity_tombstone_artifacts:
                            if _parse_transaction_identity(candidate_content) != transaction_identity:
                                raise RuntimeError(
                                    "catalog rollout transaction identity tombstone changed externally"
                                )
                for (
                    tombstone_name,
                    tombstone_identity,
                    tombstone_content,
                    tombstone_mode,
                ) in identity_tombstone_artifacts:
                    _discard_expected_tombstone_at(
                        journal_parent,
                        tombstone_name,
                        tombstone_identity,
                        tombstone_content,
                        tombstone_mode,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                    )
                if identity_state[0]:
                    _remove_expected_target_at(
                        journal_parent,
                        identity_name,
                        identity_state[1],
                        identity_state[2]
                        if identity_state[2] is not None
                        else TRANSACTION_NEW_FILE_MODE,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                        expected_identity=identity_identity,
                    )
                if finalization_state[0]:
                    _remove_expected_target_at(
                        journal_parent,
                        finalization_name,
                        finalization_state[1],
                        finalization_state[2]
                        if finalization_state[2] is not None
                        else TRANSACTION_NEW_FILE_MODE,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                        expected_identity=finalization_identity,
                    )
                return False
            _restore_transaction_journal_tombstone_at(
                journal_parent, journal_name, transaction_identity
            )
            journal_state, journal_identity = _capture_transaction_state_and_identity_at(
                journal_parent, journal_name
            )
            journal_candidates = _journal_tombstone_candidates(journal_parent, journal_name)
        transaction = _parse_transaction_journal(journal_state[1])
        requires_identity = True
        if requires_identity and transaction_identity is None:
            raise RuntimeError(
                "catalog rollout transaction journal tombstone identity is missing"
            )
        _validate_journal_against_identity(
            journal_state[1],
            transaction,
            transaction_identity,
            require_identity=requires_identity,
        )
        if identity_candidates:
            identity_tombstone_artifacts = _validated_identity_tombstones_at(
                journal_parent,
                identity_name,
                canonical_content=identity_state[1] if identity_state[0] else None,
            )
            for (
                _candidate,
                _candidate_identity,
                candidate_content,
                _candidate_mode,
            ) in identity_tombstone_artifacts:
                if _parse_transaction_identity(candidate_content) != transaction_identity:
                    raise RuntimeError(
                        "catalog rollout transaction identity tombstone changed externally"
                    )
        if journal_candidates:
            journal_tombstone_artifacts = _validated_journal_tombstones_at(
                journal_parent,
                journal_name,
                transaction_identity,
                canonical_content=journal_state[1],
            )

        targets: set[str] = set()
        pending_writes: list[tuple[Path, bytes]] = []
        originals: list[
            tuple[Path, int, str, bool, bytes, int | None, bytes, int]
        ] = []
        try:
            for item in transaction["writes"]:
                if not isinstance(item, dict):
                    raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
                        "catalog rollout transaction write is invalid"
                    )
                target = _transaction_target(repository_root, item.get("path"))
                relative_path = target.relative_to(repository_root).as_posix()
                if relative_path in targets:
                    raise RuntimeError("catalog rollout transaction has duplicate paths")
                targets.add(relative_path)
                encoded = item.get("content-base64")
                digest = item.get("sha256")
                if not isinstance(encoded, str) or not isinstance(digest, str):
                    raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
                        "catalog rollout transaction write is invalid"
                    )
                try:
                    content = base64.b64decode(encoded, validate=True)
                except ValueError as error:
                    raise RuntimeError(
                        "catalog rollout transaction content is invalid"
                    ) from error
                if hashlib.sha256(content).hexdigest() != digest:
                    raise RuntimeError("catalog rollout transaction content SHA does not match")
                prior_exists = item.get("prior-exists")
                prior_digest = item.get("prior-sha256")
                prior_encoded = item.get("prior-content-base64")
                prior_mode = item.get("prior-mode")
                if not isinstance(prior_exists, bool) or not isinstance(
                    prior_digest, str
                ) or not isinstance(prior_encoded, str):
                    raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
                        "catalog rollout transaction original state is invalid"
                    )
                if prior_exists:
                    if (
                        isinstance(prior_mode, bool)
                        or not isinstance(prior_mode, int)
                        or not 0 <= prior_mode <= 0o7777
                    ):
                        raise RuntimeError(
                            "catalog rollout transaction original mode is invalid"
                        )
                elif prior_mode is not None:
                    raise RuntimeError(
                        "catalog rollout transaction original mode is invalid"
                    )
                try:
                    prior_content = base64.b64decode(prior_encoded, validate=True)
                except ValueError as error:
                    raise RuntimeError(
                        "catalog rollout transaction original content is invalid"
                    ) from error
                if hashlib.sha256(prior_content).hexdigest() != prior_digest:
                    raise RuntimeError(
                        "catalog rollout transaction original SHA does not match"
                    )
                if not prior_exists and prior_content:
                    raise RuntimeError(
                        "catalog rollout transaction missing target has content"
                    )
                desired_mode = prior_mode if prior_exists else TRANSACTION_NEW_FILE_MODE
                supplied_parent = supplied_target_parents.get(relative_path)
                if supplied_parent is None:
                    parent_descriptor, target_name = _open_anchored_parent(
                        root_descriptor, repository_root, target
                    )
                else:
                    _assert_directory_descriptor_matches_path(
                        supplied_parent, target.parent
                    )
                    parent_descriptor = os.dup(supplied_parent)
                    target_name = target.name
                pending_writes.append((target, content))
                originals.append(
                    (
                        target,
                        parent_descriptor,
                        target_name,
                        prior_exists,
                        prior_content,
                        prior_mode,
                        content,
                        desired_mode,
                    )
                )

            if not progress_published_identities.keys() <= targets:
                raise RuntimeError(
                    "catalog rollout transaction identity inode evidence has an unknown target"
                )
            if finalization_recovery and set(finalization_published_identities) != targets:
                raise RuntimeError(
                    "catalog rollout transaction finalization inode evidence is incomplete"
                )
            if finalization_recovery:
                for (
                    target,
                    parent_descriptor,
                    target_name,
                    _prior_exists,
                    _prior_content,
                    _prior_mode,
                    content,
                    desired_mode,
                ) in originals:
                    current = _capture_transaction_state_at(parent_descriptor, target_name)
                    if not _transaction_state_matches(
                        current, True, content, desired_mode
                    ):
                        raise RuntimeError(
                            "catalog rollout transaction finalization target changed externally: "
                            f"{target}"
                        )
                    published_identity = finalization_published_identities.get(
                        target.relative_to(repository_root).as_posix()
                    )
                    if published_identity is None or _capture_transaction_identity_at(
                        parent_descriptor, target_name
                    ) != published_identity:
                        raise RuntimeError(
                            "catalog rollout transaction finalization target inode changed externally: "
                            f"{target}"
                        )

            for target, parent_descriptor, _target_name, *_rest in originals:
                _assert_directory_descriptor_matches_path(
                    parent_descriptor, target.parent
                )

            for (
                target,
                parent_descriptor,
                target_name,
                prior_exists,
                prior_content,
                prior_mode,
                content,
                desired_mode,
            ) in originals:
                _reconcile_target_artifacts_at(
                    parent_descriptor,
                    target_name,
                    prior_exists,
                    prior_content,
                    prior_mode,
                    content,
                    desired_mode,
                    transaction_id=transaction_identity[0]
                    if transaction_identity is not None
                    else None,
                )

            for (
                target,
                parent_descriptor,
                target_name,
                prior_exists,
                prior_content,
                prior_mode,
                content,
                desired_mode,
            ) in originals:
                current = _capture_transaction_state_at(parent_descriptor, target_name)
                if _transaction_state_matches(
                    current, prior_exists, prior_content, prior_mode
                ):
                    continue
                if _transaction_state_matches(current, True, content, desired_mode):
                    published_identity = (
                        finalization_published_identities.get(
                            target.relative_to(repository_root).as_posix()
                        )
                        if finalization_recovery
                        else progress_published_identities.get(
                            target.relative_to(repository_root).as_posix()
                        )
                    )
                    if published_identity is None:
                        # A durable desired byte sequence without its
                        # published inode sidecar is not ownership evidence.
                        # Preserve the target and journal for an operator-led
                        # recovery instead of rewriting or deleting an inode
                        # that may have been inserted by another process.
                        raise RuntimeError(
                            "catalog rollout transaction post-publish inode evidence is missing: "
                            f"{target}"
                        )
                    if published_identity is None or _capture_transaction_identity_at(
                        parent_descriptor, target_name
                    ) != published_identity:
                        raise RuntimeError(
                            "catalog rollout transaction target inode changed externally: "
                            f"{target}"
                        )
                    continue
                raise RuntimeError(
                    f"catalog rollout transaction target changed externally: {target}"
                )

            _assert_root_descriptor_matches_path(root_descriptor, repository_root)
            _validate_cross_file_rollout_evidence(repository_root, pending_writes)

            published_identities = dict(
                finalization_published_identities
                if finalization_recovery
                else progress_published_identities
            )

            def persist_published_identities() -> None:
                nonlocal identity_identity, identity_state
                if transaction_identity is None:
                    return
                identity_content = _transaction_identity_bytes(
                    transaction_identity[0],
                    transaction_identity[1],
                    published_identities,
                )
                current_identity_state = _capture_transaction_state_at(
                    journal_parent, identity_name
                )
                if current_identity_state != identity_state:
                    raise RuntimeError(
                        "catalog rollout transaction identity changed externally"
                    )
                if current_identity_state[1] == identity_content:
                    return
                atomic_write_bytes(
                    identity_path,
                    identity_content,
                    expected_state=(
                        current_identity_state[0],
                        current_identity_state[1],
                        current_identity_state[2],
                    ),
                    parent_descriptor=journal_parent,
                    target_name=identity_name,
                    transaction_id=transaction_identity[0],
                )
                identity_state, identity_identity = _capture_transaction_state_and_identity_at(
                    journal_parent, identity_name
                )

            def validate_published_targets() -> None:
                for (
                    target,
                    parent_descriptor,
                    target_name,
                    _prior_exists,
                    _prior_content,
                    _prior_mode,
                    content,
                    desired_mode,
                ) in originals:
                    current = _capture_transaction_state_at(
                        parent_descriptor, target_name
                    )
                    relative_path = target.relative_to(repository_root).as_posix()
                    published_identity = published_identities.get(relative_path)
                    if (
                        not _transaction_state_matches(
                            current, True, content, desired_mode
                        )
                        or published_identity is None
                        or _capture_transaction_identity_at(
                            parent_descriptor, target_name
                        )
                        != published_identity
                    ):
                        raise RuntimeError(
                            "catalog rollout transaction target changed externally: "
                            f"{target}"
                        )

            try:
                for (
                    target,
                    parent_descriptor,
                    target_name,
                    prior_exists,
                    prior_content,
                    prior_mode,
                    content,
                    desired_mode,
                ) in originals:
                    current = _capture_transaction_state_at(parent_descriptor, target_name)
                    if _transaction_state_matches(current, True, content, desired_mode):
                        published_identity = published_identities.get(
                            target.relative_to(repository_root).as_posix()
                        )
                        if published_identity is None:
                            # A durable desired byte sequence without its
                            # published inode sidecar is not ownership
                            # evidence.  Preserve the target and journal for
                            # fail-closed recovery instead of retrying a write
                            # against an inode that may be external.
                            raise RuntimeError(
                                "catalog rollout transaction post-publish inode evidence is missing: "
                                f"{target}"
                            )
                        if _capture_transaction_identity_at(
                            parent_descriptor, target_name
                        ) != published_identity:
                            raise RuntimeError(
                                "catalog rollout transaction target inode changed externally: "
                                f"{target}"
                            )
                        continue
                    if not _transaction_state_matches(
                        current, prior_exists, prior_content, prior_mode
                    ):
                        raise RuntimeError(
                            f"catalog rollout transaction target changed externally: {target}"
                        )
                    published_identity = atomic_write_bytes(
                        target,
                        content,
                        mode=desired_mode,
                        expected_state=(prior_exists, prior_content, prior_mode),
                        parent_descriptor=parent_descriptor,
                        target_name=target_name,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                    )
                    if published_identity is None:
                        raise RuntimeError(
                            "catalog rollout transaction publish inode is missing: "
                            f"{target}"
                        )
                    published_identities[target.relative_to(repository_root).as_posix()] = (
                        published_identity
                    )
                    persist_published_identities()

                _assert_root_descriptor_matches_path(root_descriptor, repository_root)
                for target, parent_descriptor, _target_name, *_rest in originals:
                    _assert_directory_descriptor_matches_path(
                        parent_descriptor, target.parent
                    )
                for (
                    target,
                    parent_descriptor,
                    target_name,
                    prior_exists,
                    prior_content,
                    prior_mode,
                    content,
                    desired_mode,
                ) in originals:
                    _reconcile_target_artifacts_at(
                        parent_descriptor,
                        target_name,
                        prior_exists,
                        prior_content,
                        prior_mode,
                        content,
                        desired_mode,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                    )
                _validate_cross_file_rollout_evidence(repository_root)
                validate_published_targets()
                if _capture_transaction_state_at(journal_parent, journal_name) != journal_state:
                    raise RuntimeError(
                        "catalog rollout transaction journal changed externally"
                    )
                _assert_root_descriptor_matches_path(root_descriptor, repository_root)
                _assert_directory_descriptor_matches_path(
                    journal_parent, journal_path.parent
                )
            except BaseException as error:
                rollback_errors: list[str] = []
                for (
                    target,
                    parent_descriptor,
                    target_name,
                    prior_exists,
                    prior_content,
                    prior_mode,
                    desired_content,
                    desired_mode,
                ) in reversed(originals):
                    try:
                        _restore_transaction_target(
                            target,
                            prior_exists,
                            prior_content,
                            prior_mode,
                            desired_content,
                            desired_mode,
                            parent_descriptor=parent_descriptor,
                            target_name=target_name,
                            desired_identity=published_identities.get(
                                target.relative_to(repository_root).as_posix()
                            ),
                            transaction_id=transaction_identity[0]
                            if transaction_identity is not None
                            else None,
                        )
                    except BaseException as rollback_error:  # noqa: BLE001 - rollback must cover interrupts
                        rollback_errors.append(str(rollback_error))
                if rollback_errors:
                    detail = str(error) or error.__class__.__name__
                    detail += "; rollback failed: " + " | ".join(rollback_errors)
                    raise RuntimeError(detail) from error
                raise

            finalization_content: bytes | None = None
            if transaction_identity is not None:
                if set(published_identities) != targets:
                    raise RuntimeError(
                        "catalog rollout transaction published inode evidence is incomplete"
                    )
                finalization_content = pretty_json(
                    {
                        "journal-sha256": hashlib.sha256(journal_state[1]).hexdigest(),
                        "published-identities": {
                            path: {"device": identity[0], "inode": identity[1]}
                            for path, identity in sorted(published_identities.items())
                        },
                        "schema-version": TRANSACTION_IDENTITY_SCHEMA_VERSION,
                        "transaction-id": transaction_identity[0],
                    }
                )
                if finalization_state[0]:
                    if finalization_state[1] != finalization_content:
                        raise RuntimeError(
                            "catalog rollout transaction finalization marker changed externally"
                        )
                else:
                    atomic_write_bytes(
                        finalization_path,
                        finalization_content,
                        expected_state=(False, b"", None),
                        parent_descriptor=journal_parent,
                        target_name=finalization_name,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                    )
                    finalization_state, finalization_identity = _capture_transaction_state_and_identity_at(
                        journal_parent, finalization_name
                    )

                if identity_state[0] and _capture_transaction_state_at(
                    journal_parent, identity_name
                ) != identity_state:
                    raise RuntimeError(
                        "catalog rollout transaction identity changed externally"
                    )

                validate_published_targets()

            cleanup_identity_content = (
                _transaction_identity_bytes(
                    transaction_identity[0],
                    transaction_identity[1],
                    published_identities,
                )
                if transaction_identity is not None
                else None
            )

            def restore_cleanup_evidence() -> None:
                """Recreate any ownership records removed before a late race.

                Final target validation and evidence cleanup are separate
                filesystem operations.  If a target changes during the last
                cleanup operation, preserve a complete durable recovery
                boundary before returning the error to the caller.
                """
                records: list[tuple[str, Path, bytes, int, tuple[int, int] | None]] = [
                    (
                        journal_name,
                        journal_path,
                        journal_state[1],
                        journal_state[2]
                        if journal_state[2] is not None
                        else TRANSACTION_NEW_FILE_MODE,
                        journal_identity,
                    )
                ]
                if cleanup_identity_content is not None:
                    records.append(
                        (
                            identity_name,
                            identity_path,
                            cleanup_identity_content,
                            identity_state[2]
                            if identity_state[2] is not None
                            else TRANSACTION_NEW_FILE_MODE,
                            identity_identity,
                        )
                    )
                if finalization_content is not None:
                    records.append(
                        (
                            finalization_name,
                            finalization_path,
                            finalization_content,
                            finalization_state[2]
                            if finalization_state[2] is not None
                            else TRANSACTION_NEW_FILE_MODE,
                            finalization_identity,
                        )
                    )
                for name, path, content, mode, expected_identity in records:
                    current = _capture_transaction_state_at(journal_parent, name)
                    if current[0]:
                        if (
                            not _write_state_matches(current, content, mode)
                            or (
                                expected_identity is not None
                                and _capture_transaction_identity_at(
                                    journal_parent, name
                                )
                                != expected_identity
                            )
                        ):
                            raise RuntimeError(
                                f"catalog rollout transaction cleanup evidence changed externally: {path}"
                            )
                        continue
                    atomic_write_bytes(
                        path,
                        content,
                        mode=mode,
                        expected_state=(False, b"", None),
                        parent_descriptor=journal_parent,
                        target_name=name,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                    )
                    restored = _capture_transaction_state_at(journal_parent, name)
                    if not _write_state_matches(restored, content, mode):
                        raise RuntimeError(
                            f"catalog rollout transaction cleanup evidence restore mismatch: {path}"
                        )

            for (
                tombstone_name,
                tombstone_identity,
                tombstone_content,
                tombstone_mode,
            ) in journal_tombstone_artifacts:
                _discard_expected_tombstone_at(
                    journal_parent,
                    tombstone_name,
                    tombstone_identity,
                    tombstone_content,
                    tombstone_mode,
                    transaction_id=transaction_identity[0]
                    if transaction_identity is not None
                    else None,
                )
            for (
                tombstone_name,
                tombstone_identity,
                tombstone_content,
                tombstone_mode,
            ) in identity_tombstone_artifacts:
                _discard_expected_tombstone_at(
                    journal_parent,
                    tombstone_name,
                    tombstone_identity,
                    tombstone_content,
                    tombstone_mode,
                    transaction_id=transaction_identity[0]
                    if transaction_identity is not None
                    else None,
                )
            if identity_state[0]:
                try:
                    if identity_identity is None:
                        raise RuntimeError(
                            "catalog rollout transaction identity changed externally"
                        )
                    # Recheck every published inode immediately before
                    # removing the first durable ownership record.  A target
                    # replacement after the earlier cross-file validation
                    # must keep the transaction evidence live.
                    validate_published_targets()
                    _remove_expected_target_at(
                        journal_parent,
                        identity_name,
                        identity_state[1],
                        identity_state[2]
                        if identity_state[2] is not None
                        else TRANSACTION_NEW_FILE_MODE,
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                        expected_identity=identity_identity,
                    )
                    validate_published_targets()
                except (OSError, RuntimeError) as error:
                    try:
                        restore_cleanup_evidence()
                    except BaseException as restore_error:
                        raise RuntimeError(
                            "catalog rollout transaction identity cleanup evidence restore failed"
                        ) from restore_error
                    raise RuntimeError(
                        "catalog rollout transaction identity changed externally"
                    ) from error
            if _capture_transaction_state_at(journal_parent, identity_name)[0]:
                raise RuntimeError(
                    "catalog rollout transaction identity changed externally"
                )
            if _identity_tombstone_candidates(journal_parent, identity_name):
                raise RuntimeError(
                    "catalog rollout transaction identity tombstone changed externally"
                )
            if _journal_tombstone_candidates(journal_parent, journal_name):
                raise RuntimeError(
                    "catalog rollout transaction journal tombstone changed externally"
                )
            if _capture_transaction_state_at(journal_parent, journal_name) != journal_state:
                raise RuntimeError(
                    "catalog rollout transaction journal changed externally"
                )
            try:
                if journal_identity is None:
                    raise RuntimeError(
                        "catalog rollout transaction journal changed externally"
                    )
                validate_published_targets()
                _remove_expected_target_at(
                    journal_parent,
                    journal_name,
                    journal_state[1],
                    (
                        journal_state[2]
                        if journal_state[2] is not None
                        else TRANSACTION_NEW_FILE_MODE
                    ),
                    transaction_id=transaction_identity[0]
                    if transaction_identity is not None
                    else None,
                    expected_identity=journal_identity,
                )
                validate_published_targets()
            except (OSError, RuntimeError) as error:
                try:
                    restore_cleanup_evidence()
                except BaseException as restore_error:
                    raise RuntimeError(
                        "catalog rollout transaction journal cleanup evidence restore failed"
                    ) from restore_error
                raise RuntimeError(
                    "catalog rollout transaction journal changed externally"
                ) from error
            if finalization_content is not None:
                try:
                    if finalization_identity is None:
                        raise RuntimeError(
                            "catalog rollout transaction finalization marker changed externally"
                        )
                    validate_published_targets()
                    _remove_expected_target_at(
                        journal_parent,
                        finalization_name,
                        finalization_content,
                        (
                            finalization_state[2]
                            if finalization_state[2] is not None
                            else TRANSACTION_NEW_FILE_MODE
                        ),
                        transaction_id=transaction_identity[0]
                        if transaction_identity is not None
                        else None,
                        expected_identity=finalization_identity,
                    )
                    validate_published_targets()
                except (OSError, RuntimeError) as error:
                    try:
                        restore_cleanup_evidence()
                    except BaseException as restore_error:
                        raise RuntimeError(
                            "catalog rollout transaction finalization cleanup evidence restore failed"
                        ) from restore_error
                    raise RuntimeError(
                        "catalog rollout transaction finalization marker changed externally"
                    ) from error
            return True
        finally:
            for _target, parent_descriptor, _target_name, *_rest in originals:
                os.close(parent_descriptor)
    finally:
        os.close(journal_parent)


def recover_catalog_rollout_transaction(repository_root: Path) -> bool:
    root = repository_root.resolve()
    with _catalog_rollout_transaction_lock(root) as root_descriptor:
        _assert_root_descriptor_matches_path(root_descriptor, root)
        return _recover_catalog_rollout_transaction(root, root_descriptor)


def commit_catalog_rollout_transaction(
    repository_root: Path, writes: tuple[tuple[Path, bytes], ...]
) -> None:
    if not writes:
        raise RuntimeError("catalog rollout transaction requires at least one write")
    repository_root_input = repository_root
    root = repository_root.resolve()
    with _catalog_rollout_transaction_lock(root) as root_descriptor:
        _assert_root_descriptor_matches_path(root_descriptor, root)
        journal_path = catalog_rollout_transaction_path(root)
        journal_parent, journal_name = _open_anchored_parent(
            root_descriptor, root, journal_path
        )
        try:
            journal_state = _capture_transaction_state_at(journal_parent, journal_name)
            identity_path = catalog_rollout_transaction_identity_path(root)
            identity_name = identity_path.name
            identity_state = _capture_transaction_state_at(journal_parent, identity_name)
            finalization_path = catalog_rollout_transaction_finalization_path(root)
            finalization_name = finalization_path.name
            finalization_state = _capture_transaction_state_at(
                journal_parent, finalization_name
            )
            if journal_state[0]:
                raise RuntimeError(
                    "catalog rollout transaction already has a pending journal"
                )
            if (
                identity_state[0]
                or finalization_state[0]
                or _journal_tombstone_candidates(journal_parent, journal_name)
                or _identity_tombstone_candidates(journal_parent, identity_name)
                or _quarantine_directory_candidates(journal_parent)
            ):
                _recover_catalog_rollout_transaction(
                    root,
                    root_descriptor,
                    journal_parent_descriptor=journal_parent,
                    journal_name=journal_name,
                )
                journal_state = _capture_transaction_state_at(journal_parent, journal_name)
                identity_state = _capture_transaction_state_at(
                    journal_parent, identity_name
                )
                finalization_state = _capture_transaction_state_at(
                    journal_parent, finalization_name
                )
                if (
                    journal_state[0]
                    or identity_state[0]
                    or finalization_state[0]
                    or _journal_tombstone_candidates(journal_parent, journal_name)
                    or _identity_tombstone_candidates(journal_parent, identity_name)
                    or _quarantine_directory_candidates(journal_parent)
                ):
                    raise RuntimeError(
                        "catalog rollout transaction already has pending evidence"
                    )

            transaction_writes = []
            targets: set[str] = set()
            target_descriptors: dict[str, int] = {}
            try:
                for path, content in writes:
                    relative_input = _transaction_input_relative_path(
                        repository_root_input, path
                    )
                    target = _transaction_target(root, relative_input)
                    relative_path = target.relative_to(root).as_posix()
                    if relative_path in targets:
                        raise RuntimeError("catalog rollout transaction has duplicate paths")
                    targets.add(relative_path)
                    target_parent, target_name = _open_anchored_parent(
                        root_descriptor, root, target
                    )
                    target_descriptors[relative_path] = target_parent
                    prior_exists, prior_content, prior_mode = _capture_transaction_state_at(
                        target_parent, target_name
                    )
                    transaction_writes.append(
                        {
                            "content-base64": base64.b64encode(content).decode("ascii"),
                            "path": relative_path,
                            "prior-content-base64": base64.b64encode(
                                prior_content
                            ).decode("ascii"),
                            "prior-exists": prior_exists,
                            "prior-mode": prior_mode,
                            "prior-sha256": hashlib.sha256(prior_content).hexdigest(),
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
                transaction_id = uuid.uuid4().hex
                journal = {
                    "schema-version": TRANSACTION_SCHEMA_VERSION,
                    "transaction-id": transaction_id,
                    "writes": transaction_writes,
                }
                journal_bytes = pretty_json(journal)
                identity_bytes = _transaction_identity_bytes(
                    transaction_id,
                    hashlib.sha256(journal_bytes).hexdigest(),
                    {},
                )
                atomic_write_bytes(
                    identity_path,
                    identity_bytes,
                    expected_state=(False, b"", None),
                    parent_descriptor=journal_parent,
                    target_name=identity_name,
                    transaction_id=transaction_id,
                )
                atomic_write_bytes(
                    journal_path,
                    journal_bytes,
                    expected_state=(False, b"", None),
                    parent_descriptor=journal_parent,
                    target_name=journal_name,
                    transaction_id=transaction_id,
                )
                recovered = _recover_catalog_rollout_transaction(
                    root,
                    root_descriptor,
                    journal_parent_descriptor=journal_parent,
                    journal_name=journal_name,
                    target_parent_descriptors=target_descriptors,
                )
                if not recovered:
                    raise RuntimeError(
                        "catalog rollout transaction journal disappeared during recovery"
                    )
            finally:
                for descriptor in target_descriptors.values():
                    os.close(descriptor)
        finally:
            os.close(journal_parent)


def pretty_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _rollout_rows(document: dict[str, Any], rollout_name: str) -> list[dict[str, Any]]:
    rows = document.get("subsequent-rollouts")
    if not isinstance(rows, list):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "central catalog ledger rollout rows are invalid"
        )
    return [
        item
        for item in rows
        if isinstance(item, dict) and item.get("rollout") == rollout_name
    ]


def _one_rollout_row(document: dict[str, Any], rollout_name: str) -> dict[str, Any]:
    rows = _rollout_rows(document, rollout_name)
    if len(rows) != 1:
        raise RuntimeError(
            f"expected exactly one central rollout row for {rollout_name}; found {len(rows)}"
        )
    return rows[0]


def _read_repo_file(
    repository_root: Path,
    relative_path: object,
    label: str,
    source_ref: str | None = None,
    pending_writes: dict[str, bytes] | None = None,
) -> bytes:
    root = repository_root.resolve()
    unresolved, relative = _validate_relative_repository_path(
        root, relative_path, label
    )
    path = Path(relative)
    if source_ref is None and pending_writes is not None and relative in pending_writes:
        return pending_writes[relative]
    if source_ref is not None:
        try:
            return subprocess.run(
                ["git", "show", f"{source_ref}:{path.as_posix()}"],
                cwd=repository_root,
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            raise RuntimeError(f"{label} path cannot be read from {source_ref}") from error
    try:
        resolved = unresolved.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"{label} path escapes or is missing") from error
    if not resolved.is_file():
        raise RuntimeError(f"{label} must be a regular file")
    return resolved.read_bytes()


def load_catalog_rollout_evidence(
    document: dict[str, Any],
    rollout_name: str,
    repository_root: Path,
    source_ref: str | None = None,
    pending_writes: dict[str, bytes] | None = None,
) -> tuple[dict[str, Any], bytes, dict[str, dict[str, str]]]:
    """Load evidence from the exact files named by one central rollout row."""
    row = _one_rollout_row(document, rollout_name)
    if is_legacy_rollout_row(row):
        validate_legacy_rollout_contract(row)
        raise RuntimeError(
            "central rollout row uses the explicit legacy verified contract; "
            "do not load it as immutable rollout evidence"
        )
    if row.get("status") in {"validation-pending", "verified-resolved-graph"}:
        _require_immutable_rollout_row(
            rollout_name,
            row,
            require_receipt=row.get("status") == "verified-resolved-graph",
        )
    elif row.get("status") != "verified":
        raise RuntimeError("central rollout row status is unsupported")
    ledger_bytes = _read_repo_file(
        repository_root,
        row.get("authority-delta-ledger"),
        "delta-ledger",
        source_ref,
        pending_writes,
    )
    try:
        authority_ledger = json.loads(ledger_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("central delta-ledger is not valid JSON") from error
    if not isinstance(authority_ledger, dict):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "central delta-ledger must be a JSON object"
        )
    if authority_ledger.get("rollout") != rollout_name:
        raise RuntimeError("central delta-ledger rollout does not match its row")
    if authority_ledger.get("status") != row.get("status"):
        raise RuntimeError("central delta-ledger status does not match its row")
    if authority_ledger.get("candidate", {}).get("catalog-sha256") != row.get(
        "catalog-sha256"
    ):
        raise RuntimeError("central rollout catalog SHA does not match delta-ledger")

    ledger_sha = hashlib.sha256(ledger_bytes).hexdigest()
    expected_ledger_sha = row.get("authority-delta-ledger-sha256")
    if expected_ledger_sha != ledger_sha:
        raise RuntimeError("central delta-ledger SHA does not match file")

    audit_record = authority_ledger.get("audit")
    if not isinstance(audit_record, dict) or audit_record.get("path") != row.get("audit"):
        raise RuntimeError("central audit path does not match delta-ledger")
    audit_bytes = _read_repo_file(
        repository_root,
        row.get("audit"),
        "audit",
        source_ref,
        pending_writes,
    )
    audit_sha = hashlib.sha256(audit_bytes).hexdigest()
    if audit_record.get("sha256") != audit_sha:
        raise RuntimeError("central audit SHA does not match delta-ledger")
    expected_audit_sha = row.get("audit-sha256")
    if expected_audit_sha != audit_sha:
        raise RuntimeError("central audit SHA does not match file")
    if row.get("delta-count") is not None and row["delta-count"] != len(
        authority_ledger.get("delta", [])
    ):
        raise RuntimeError("central rollout delta count does not match its ledger")
    if row.get("baseline-catalog-ref") is not None and row[
        "baseline-catalog-ref"
    ] != authority_ledger.get("baseline", {}).get("catalog-ref"):
        raise RuntimeError("central rollout baseline does not match its ledger")
    if (row.get("resolved-graph-evidence") or []) != (
        authority_ledger.get("resolved-graph-evidence") or []
    ):
        raise RuntimeError("central rollout graph evidence does not match its ledger")
    resolved_graph_artifact = None
    if row.get("status") == "verified-resolved-graph":
        resolved_graph_evidence = row["resolved-graph-evidence"]
        receipt_bytes = _read_repo_file(
            repository_root,
            resolved_graph_evidence["path"],
            "resolved graph receipt",
            source_ref,
            pending_writes,
        )
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        if receipt_sha != resolved_graph_evidence["sha256"]:
            raise RuntimeError("central resolved graph receipt SHA does not match file")
        resolved_graph_artifact = {
            **copy.deepcopy(resolved_graph_evidence),
            "path": resolved_graph_evidence["path"],
            "sha256": receipt_sha,
        }
    artifacts = {
        "audit": {"path": row["audit"], "sha256": audit_sha},
        "authority-delta-ledger": {
            "path": row["authority-delta-ledger"],
            "sha256": ledger_sha,
        },
    }
    if resolved_graph_artifact is not None:
        artifacts["resolved-graph-evidence"] = resolved_graph_artifact
    return (
        authority_ledger,
        audit_bytes,
        artifacts,
    )


def snapshot_rollout_evidence(
    authority_ledger: dict[str, Any],
    audit_bytes: bytes,
    repository_root: Path,
    revision: str | None = None,
    resolved_graph_receipt_bytes: bytes | None = None,
) -> dict[str, dict[str, str]]:
    rollout = _validate_snapshot_segment(
        authority_ledger.get("rollout"), "rollout name"
    )
    if revision is not None:
        revision = _validate_snapshot_segment(revision, "rollout revision")

    audit_sha256 = hashlib.sha256(audit_bytes).hexdigest()
    expected_audit_sha256 = authority_ledger.get("audit", {}).get("sha256")
    if expected_audit_sha256 != audit_sha256:
        raise RuntimeError("rollout audit SHA does not match the audit snapshot")

    snapshot_dir = Path("config") / "rollouts" / rollout
    if revision is not None:
        snapshot_dir /= revision
    audit_relative_path = snapshot_dir / "latest-stable-version-audit.json"
    ledger_relative_path = snapshot_dir / "latest-stable-version-deltas.json"
    ledger_snapshot = copy.deepcopy(authority_ledger)
    ledger_snapshot["audit"]["path"] = audit_relative_path.as_posix()
    ledger_bytes = pretty_json(ledger_snapshot)
    files = {
        Path("latest-stable-version-audit.json"): audit_bytes,
        Path("latest-stable-version-deltas.json"): ledger_bytes,
    }
    artifacts: dict[str, dict[str, str]] = {
        "audit": {"path": audit_relative_path.as_posix(), "sha256": audit_sha256},
        "authority-delta-ledger": {
            "path": ledger_relative_path.as_posix(),
            "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        },
    }
    resolved_graph_evidence = authority_ledger.get("resolved-graph-evidence")
    if resolved_graph_receipt_bytes is not None:
        if not isinstance(resolved_graph_evidence, dict):
            raise RuntimeError("verified rollout lacks resolved graph receipt evidence")
        receipt_sha256 = hashlib.sha256(resolved_graph_receipt_bytes).hexdigest()
        if resolved_graph_evidence.get("sha256") != receipt_sha256:
            raise RuntimeError("resolved graph receipt SHA does not match evidence")
        receipt_relative_path = (
            snapshot_dir / f"resolved-graph-{receipt_sha256[:16]}.json"
        )
        receipt_evidence = copy.deepcopy(resolved_graph_evidence)
        receipt_evidence["path"] = receipt_relative_path.as_posix()
        receipt_evidence["sha256"] = receipt_sha256
        ledger_snapshot["resolved-graph-evidence"] = receipt_evidence
        ledger_bytes = pretty_json(ledger_snapshot)
        files[Path(receipt_relative_path.name)] = resolved_graph_receipt_bytes
        files[Path("latest-stable-version-deltas.json")] = ledger_bytes
        artifacts["resolved-graph-evidence"] = receipt_evidence
    elif authority_ledger.get("status") == "verified-resolved-graph":
        raise RuntimeError("verified rollout requires resolved graph receipt bytes")

    _publish_immutable_snapshot(repository_root, snapshot_dir, files)
    artifacts["authority-delta-ledger"]["sha256"] = hashlib.sha256(ledger_bytes).hexdigest()
    return artifacts


def _open_or_create_directory_at(
    base_descriptor: int,
    parts: tuple[str, ...],
    *,
    mode: int = 0o755,
) -> int:
    """Open a directory path relative to an anchored descriptor without following symlinks."""
    descriptor = os.dup(base_descriptor)
    try:
        for part in parts:
            if part in {"", ".", ".."} or "/" in part:
                raise RuntimeError("immutable rollout snapshot path is invalid")
            try:
                os.mkdir(part, mode, dir_fd=descriptor)
            except FileExistsError:
                pass
            try:
                next_descriptor = os.open(
                    part, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptor
                )
            except OSError as error:
                raise RuntimeError(
                    "immutable rollout snapshot parent changed externally"
                ) from error
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_existing_directory_at(
    base_descriptor: int, parts: tuple[str, ...]
) -> int:
    """Open an existing descriptor-anchored directory without following symlinks."""
    descriptor = os.dup(base_descriptor)
    try:
        for part in parts:
            if part in {"", ".", ".."} or "/" in part:
                raise RuntimeError("immutable rollout snapshot path is invalid")
            try:
                next_descriptor = os.open(
                    part, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptor
                )
            except OSError as error:
                raise RuntimeError(
                    "immutable rollout snapshot parent changed externally"
                ) from error
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _snapshot_relative_parts(relative_path: Path) -> tuple[str, ...]:
    if relative_path.is_absolute() or not relative_path.parts:
        raise RuntimeError("immutable rollout snapshot file path is invalid")
    parts = tuple(relative_path.parts)
    if any(part in {"", ".", ".."} or "/" in part for part in parts):
        raise RuntimeError("immutable rollout snapshot file path is invalid")
    return parts


def _snapshot_file_matches(
    snapshot_descriptor: int,
    relative_path: Path,
    content: bytes,
    display_path: Path,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, int]:
    parts = _snapshot_relative_parts(relative_path)
    parent_descriptor = _open_existing_directory_at(
        snapshot_descriptor, parts[:-1]
    )
    try:
        try:
            descriptor = os.open(
                parts[-1], _TARGET_OPEN_FLAGS, dir_fd=parent_descriptor
            )
        except OSError as error:
            raise RuntimeError(
                f"immutable rollout snapshot differs: {display_path}"
            ) from error
        try:
            state = _capture_open_descriptor_state(descriptor)
            identity = _descriptor_identity(descriptor)
        finally:
            os.close(descriptor)
        if expected_identity is not None and identity != expected_identity:
            raise RuntimeError(
                f"immutable rollout snapshot inode changed: {display_path}"
            )
        if state[1] != content:
            raise RuntimeError(f"immutable rollout snapshot differs: {display_path}")
        return identity
    finally:
        os.close(parent_descriptor)


def _validate_snapshot_descriptor(
    snapshot_descriptor: int,
    expected_identity: tuple[int, int],
    files: dict[Path, bytes],
    snapshot_display: Path,
    *,
    expected_file_identities: dict[Path, tuple[int, int]] | None = None,
) -> dict[Path, tuple[int, int]]:
    """Validate a published snapshot through its anchored directory inode."""
    if _descriptor_identity(snapshot_descriptor) != expected_identity:
        raise RuntimeError(
            f"immutable rollout snapshot changed externally: {snapshot_display}"
        )
    observed_file_identities: dict[Path, tuple[int, int]] = {}
    for relative_path, content in files.items():
        observed_file_identities[relative_path] = _snapshot_file_matches(
            snapshot_descriptor,
            relative_path,
            content,
            snapshot_display / relative_path,
            expected_identity=(
                expected_file_identities.get(relative_path)
                if expected_file_identities is not None
                else None
            ),
        )
    if _descriptor_identity(snapshot_descriptor) != expected_identity:
        raise RuntimeError(
            f"immutable rollout snapshot changed externally: {snapshot_display}"
        )
    return observed_file_identities


def _write_snapshot_file_at(
    staging_descriptor: int,
    relative_path: Path,
    content: bytes,
) -> None:
    parts = _snapshot_relative_parts(relative_path)
    parent_descriptor = _open_or_create_directory_at(
        staging_descriptor, parts[:-1]
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            parts[-1],
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o644,
            dir_fd=parent_descriptor,
        )
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write while publishing immutable rollout snapshot")
            view = view[written:]
        os.fsync(descriptor)
        _fsync_directory_fd(parent_descriptor)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_descriptor)


def _remove_directory_tree_at(
    parent_descriptor: int,
    directory_name: str,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    directory_descriptor = os.open(
        directory_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
    )
    observed_identity = _descriptor_identity(directory_descriptor)
    try:
        if (
            expected_identity is not None and observed_identity != expected_identity
        ):
            raise RuntimeError(
                f"immutable rollout staging directory changed externally: {directory_name}"
            )
        for entry_name in os.listdir(directory_descriptor):
            try:
                child_descriptor = os.open(
                    entry_name, _DIRECTORY_OPEN_FLAGS, dir_fd=directory_descriptor
                )
            except OSError as error:
                if error.errno not in {errno.ENOTDIR, errno.ELOOP}:
                    raise
                child_descriptor = os.open(
                    entry_name, _TARGET_OPEN_FLAGS, dir_fd=directory_descriptor
                )
                try:
                    child_state = _capture_open_descriptor_state(child_descriptor)
                    child_identity = _descriptor_identity(child_descriptor)
                finally:
                    os.close(child_descriptor)
                _unlink_private_entry_at(
                    directory_descriptor,
                    entry_name,
                    child_identity,
                    child_state[1],
                    child_state[2] if child_state[2] is not None else 0o644,
                )
                if _capture_transaction_identity_at(directory_descriptor, entry_name) is not None:
                    raise RuntimeError(
                        f"immutable rollout staging entry cleanup failed: {entry_name}"
                    )
            else:
                try:
                    child_identity = _descriptor_identity(child_descriptor)
                finally:
                    os.close(child_descriptor)
                _remove_directory_tree_at(
                    directory_descriptor,
                    entry_name,
                    expected_identity=child_identity,
                )
    finally:
        os.close(directory_descriptor)
    if expected_identity is not None and _capture_directory_identity_at(
        parent_descriptor, directory_name
    ) != expected_identity:
        raise RuntimeError(
            f"immutable rollout staging directory changed externally: {directory_name}"
        )
    _remove_expected_directory_at(
        parent_descriptor,
        directory_name,
        expected_identity or observed_identity,
    )


def _publish_immutable_snapshot(
    repository_root: Path,
    snapshot_relative: Path,
    files: dict[Path, bytes],
) -> None:
    """Publish one complete immutable snapshot directory atomically.

    Every parent and file is opened relative to an ``O_NOFOLLOW`` descriptor so
    a symlinked ``config``/``rollouts`` path cannot redirect evidence outside
    the repository.
    """
    root = repository_root.resolve()
    if snapshot_relative.is_absolute():
        try:
            snapshot_relative = snapshot_relative.relative_to(root)
        except ValueError as error:
            raise RuntimeError(
                "immutable rollout snapshot path escapes repository"
            ) from error
    snapshot_parts = _snapshot_relative_parts(snapshot_relative)
    if not snapshot_parts:
        raise RuntimeError("immutable rollout snapshot path is invalid")
    for relative_path in files:
        _snapshot_relative_parts(relative_path)

    root_descriptor = os.open(root, _DIRECTORY_OPEN_FLAGS)
    parent_descriptor: int | None = None
    staging_descriptor: int | None = None
    staging_identity: tuple[int, int] | None = None
    staging_name: str | None = None
    try:
        parent_descriptor = _open_or_create_directory_at(
            root_descriptor, snapshot_parts[:-1]
        )
        snapshot_name = snapshot_parts[-1]
        snapshot_display = root.joinpath(*snapshot_parts)
        try:
            snapshot_descriptor = os.open(
                snapshot_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
            )
        except FileNotFoundError:
            snapshot_descriptor = None
        except OSError as error:
            raise RuntimeError(
                f"immutable rollout snapshot is not a directory: {snapshot_display}"
            ) from error
        if snapshot_descriptor is not None:
            snapshot_identity = _descriptor_identity(snapshot_descriptor)
            try:
                snapshot_file_identities = _validate_snapshot_descriptor(
                    snapshot_descriptor, snapshot_identity, files, snapshot_display
                )
                if (
                    _capture_directory_identity_at(parent_descriptor, snapshot_name)
                    != snapshot_identity
                ):
                    raise RuntimeError(
                        f"immutable rollout snapshot changed externally: {snapshot_display}"
                    )
                _assert_directory_descriptor_matches_path(
                    parent_descriptor, root.joinpath(*snapshot_parts[:-1])
                )
                _validate_snapshot_descriptor(
                    snapshot_descriptor,
                    snapshot_identity,
                    files,
                    snapshot_display,
                    expected_file_identities=snapshot_file_identities,
                )
                if (
                    _capture_directory_identity_at(parent_descriptor, snapshot_name)
                    != snapshot_identity
                ):
                    raise RuntimeError(
                        f"immutable rollout snapshot changed externally: {snapshot_display}"
                    )
            finally:
                os.close(snapshot_descriptor)
            return

        staging_name = f".{snapshot_name}.{os.getpid()}.{uuid.uuid4().hex}"
        os.mkdir(staging_name, 0o700, dir_fd=parent_descriptor)
        staging_descriptor = os.open(
            staging_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
        )
        staging_identity = _descriptor_identity(staging_descriptor)
        for relative_path, content in files.items():
            _write_snapshot_file_at(staging_descriptor, relative_path, content)
        _fsync_directory_fd(staging_descriptor)
        if staging_identity is None:
            raise RuntimeError(
                "immutable rollout snapshot staging directory identity is unavailable"
            )
        staging_file_identities = _validate_snapshot_descriptor(
            staging_descriptor, staging_identity, files, snapshot_display
        )
        try:
            _rename_no_replace_at(
                parent_descriptor,
                staging_name,
                parent_descriptor,
                snapshot_name,
            )
        except FileExistsError:
            snapshot_descriptor = os.open(
                snapshot_name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_descriptor
            )
            snapshot_identity = _descriptor_identity(snapshot_descriptor)
            try:
                snapshot_file_identities = _validate_snapshot_descriptor(
                    snapshot_descriptor, snapshot_identity, files, snapshot_display
                )
                if (
                    _capture_directory_identity_at(parent_descriptor, snapshot_name)
                    != snapshot_identity
                ):
                    raise RuntimeError(
                        f"immutable rollout snapshot changed externally: {snapshot_display}"
                    )
                _assert_directory_descriptor_matches_path(
                    parent_descriptor, root.joinpath(*snapshot_parts[:-1])
                )
                _validate_snapshot_descriptor(
                    snapshot_descriptor,
                    snapshot_identity,
                    files,
                    snapshot_display,
                    expected_file_identities=snapshot_file_identities,
                )
            finally:
                os.close(snapshot_descriptor)
        else:
            if (
                _capture_directory_identity_at(parent_descriptor, snapshot_name)
                != staging_identity
            ):
                raise RuntimeError(
                    f"immutable rollout snapshot changed externally: {snapshot_display}"
                )
            _fsync_directory_fd(parent_descriptor)
            if staging_descriptor is None or staging_identity is None:
                raise RuntimeError(
                    "immutable rollout snapshot published descriptor is unavailable"
                )
            # Keep the original staging descriptor anchored across the parent
            # fsync and the final validation.  A same-bytes directory or file
            # replacement at the published path must not be accepted merely
            # because the path still resolves and has the expected content.
            _validate_snapshot_descriptor(
                staging_descriptor,
                staging_identity,
                files,
                snapshot_display,
                expected_file_identities=staging_file_identities,
            )
            if (
                _capture_directory_identity_at(parent_descriptor, snapshot_name)
                != staging_identity
            ):
                raise RuntimeError(
                    f"immutable rollout snapshot changed externally: {snapshot_display}"
                )
            _assert_directory_descriptor_matches_path(
                parent_descriptor, root.joinpath(*snapshot_parts[:-1])
            )
            _validate_snapshot_descriptor(
                staging_descriptor,
                staging_identity,
                files,
                snapshot_display,
                expected_file_identities=staging_file_identities,
            )
            staging_name = None
    finally:
        if staging_descriptor is not None:
            os.close(staging_descriptor)
        if staging_name is not None and parent_descriptor is not None:
            try:
                if staging_identity is None:
                    raise RuntimeError(
                        "immutable rollout staging directory identity is unavailable"
                    )
                _remove_directory_tree_at(
                    parent_descriptor,
                    staging_name,
                    expected_identity=staging_identity,
                )
            except FileNotFoundError:
                pass
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        os.close(root_descriptor)


def ensure_immutable_rollout_snapshot(
    authority_ledger: dict[str, Any],
    audit_bytes: bytes,
    declared_artifacts: dict[str, dict[str, str]],
    repository_root: Path,
) -> dict[str, dict[str, str]]:
    rollout = authority_ledger.get("rollout")
    if not isinstance(rollout, str):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "rollout name is required"
        )
    prefix = f"config/rollouts/{rollout}/"
    if all(
        artifact.get("path", "").startswith(prefix)
        for artifact in declared_artifacts.values()
    ):
        validate_rollout_artifacts(rollout, declared_artifacts)
        for name, artifact in declared_artifacts.items():
            content = _read_repo_file(
                repository_root,
                artifact["path"],
                f"{name} snapshot",
            )
            if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
                raise RuntimeError(f"{name} snapshot SHA does not match file")
        return copy.deepcopy(declared_artifacts)

    ledger_sha = declared_artifacts.get("authority-delta-ledger", {}).get("sha256", "")
    if FULL_SHA256.fullmatch(ledger_sha) is None:
        raise RuntimeError("previous rollout delta-ledger SHA-256 is invalid")
    return snapshot_rollout_evidence(
        authority_ledger,
        audit_bytes,
        repository_root,
        revision=f"legacy-{ledger_sha[:16]}",
    )


def candidate_rollout_snapshot_revision(
    document: dict[str, Any], authority_ledger: dict[str, Any]
) -> str | None:
    rollout = authority_ledger.get("rollout")
    if not isinstance(rollout, str):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "rollout name is required"
        )
    if not _rollout_rows(document, rollout):
        return None
    _one_rollout_row(document, rollout)

    catalog_sha = authority_ledger.get("candidate", {}).get("catalog-sha256", "")
    audit_sha = authority_ledger.get("audit", {}).get("sha256", "")
    if FULL_SHA256.fullmatch(catalog_sha) is None or FULL_SHA256.fullmatch(audit_sha) is None:
        raise RuntimeError("catalog rollout revision requires exact evidence SHA-256 values")
    return f"candidate-{catalog_sha[:16]}-{audit_sha[:16]}"


def validate_rollout_artifacts(
    rollout: str, artifacts: dict[str, dict[str, str]]
) -> None:
    _validate_snapshot_segment(rollout, "rollout name")
    for name in ("audit", "authority-delta-ledger"):
        artifact = artifacts.get(name, {})
        _immutable_rollout_path(rollout, artifact.get("path"), name)
        if FULL_SHA256.fullmatch(artifact.get("sha256", "")) is None:
            raise RuntimeError(f"{name} snapshot SHA-256 is invalid")
    receipt = artifacts.get("resolved-graph-evidence")
    if receipt is not None:
        _immutable_rollout_path(
            rollout, receipt.get("path"), "resolved graph receipt"
        )
        if FULL_SHA256.fullmatch(receipt.get("sha256", "")) is None:
            raise RuntimeError("resolved graph receipt SHA-256 is invalid")


def pin_catalog_rollout_evidence(
    document: dict[str, Any], rollout_name: str, artifacts: dict[str, dict[str, str]]
) -> dict[str, Any]:
    validate_rollout_artifacts(rollout_name, artifacts)
    updated = copy.deepcopy(document)
    row = _one_rollout_row(updated, rollout_name)
    row["audit"] = artifacts["audit"]["path"]
    row["audit-sha256"] = artifacts["audit"]["sha256"]
    row["authority-delta-ledger"] = artifacts["authority-delta-ledger"]["path"]
    row["authority-delta-ledger-sha256"] = artifacts["authority-delta-ledger"][
        "sha256"
    ]
    if "resolved-graph-evidence" in artifacts:
        row["resolved-graph-evidence"] = copy.deepcopy(
            artifacts["resolved-graph-evidence"]
        )
    return updated


def upsert_catalog_rollout(
    document: dict[str, Any],
    authority_ledger: dict[str, Any],
    artifacts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    rollout_name = authority_ledger["rollout"]
    validate_rollout_artifacts(rollout_name, artifacts)
    updated = copy.deepcopy(document)
    candidate_evidence = authority_ledger.get("candidate-validation-evidence", {})
    downstream_evidence = candidate_evidence.get(
        "downstream-full-builds", {"repositories": 9, "status": "pending"}
    )
    publication_evidence = candidate_evidence.get(
        "publication-poms", {"repositories": 9, "status": "pending"}
    )
    if authority_ledger.get("status") == "verified-resolved-graph":
        resolved_graph_evidence = artifacts.get("resolved-graph-evidence")
        if resolved_graph_evidence is None:
            raise RuntimeError("verified rollout requires an immutable resolved graph receipt")
    else:
        resolved_graph_evidence = []
    rollout = {
        "audit": artifacts["audit"]["path"],
        "audit-sha256": artifacts["audit"]["sha256"],
        "authority-delta-ledger": artifacts["authority-delta-ledger"]["path"],
        "authority-delta-ledger-sha256": artifacts["authority-delta-ledger"][
            "sha256"
        ],
        "baseline-catalog-ref": authority_ledger["baseline"]["catalog-ref"],
        "catalog-sha256": authority_ledger["candidate"]["catalog-sha256"],
        "delta-count": len(authority_ledger["delta"]),
        "downstream-full-builds": copy.deepcopy(downstream_evidence),
        "publication-pom-verification": copy.deepcopy(publication_evidence),
        "remote-immutable-ref-verification": candidate_evidence.get(
            "remote-immutable-ref-verification", "pending-candidate-commit-and-push"
        ),
        "resolved-graph-evidence": copy.deepcopy(resolved_graph_evidence),
        "rollout": rollout_name,
        "status": authority_ledger["status"],
    }
    existing = updated["subsequent-rollouts"]
    updated["subsequent-rollouts"] = [
        item for item in existing if item.get("rollout") != rollout_name
    ] + [rollout]
    return updated


def record_promoted_catalog_rollout(
    document: dict[str, Any],
    authority_ledger: dict[str, Any],
    audit_bytes: bytes,
    repository_root: Path,
) -> dict[str, Any]:
    rollout_name = authority_ledger.get("rollout")
    if authority_ledger.get("status") != "verified-resolved-graph":
        raise RuntimeError("only a verified resolved-graph rollout can be recorded")
    row = _one_rollout_row(document, rollout_name)
    if row.get("status") not in {"validation-pending", "verified-resolved-graph"}:
        raise RuntimeError("central rollout is not in a promotable lifecycle state")
    if row.get("catalog-sha256") != authority_ledger.get("candidate", {}).get(
        "catalog-sha256"
    ):
        raise RuntimeError("central rollout catalog SHA does not match promoted ledger")
    evidence = authority_ledger.get("resolved-graph-evidence", {})
    if not isinstance(evidence, dict):
        raise RuntimeError(  # noqa: TRY004 - preserve the validation error contract
            "promoted rollout lacks resolved graph receipt evidence"
        )
    receipt_sha = evidence.get("sha256")
    if not isinstance(receipt_sha, str) or FULL_SHA256.fullmatch(receipt_sha) is None:
        raise RuntimeError("promoted rollout lacks resolved-graph receipt SHA")
    receipt_bytes = _read_repo_file(
        repository_root, evidence.get("path"), "resolved graph receipt"
    )
    if hashlib.sha256(receipt_bytes).hexdigest() != receipt_sha:
        raise RuntimeError("promoted resolved graph receipt SHA does not match file")
    artifacts = snapshot_rollout_evidence(
        authority_ledger,
        audit_bytes,
        repository_root,
        revision=f"resolved-graph-{receipt_sha[:16]}",
        resolved_graph_receipt_bytes=receipt_bytes,
    )
    return upsert_catalog_rollout(document, authority_ledger, artifacts)
