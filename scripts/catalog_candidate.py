#!/usr/bin/env python3
"""Create and verify fail-closed catalog candidate evidence."""

from __future__ import annotations

import argparse
import dataclasses
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time
import unicodedata
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_KEYS = (
    "projects",
    "aws",
    "experimental",
    "exposed",
    "graph",
    "image",
    "javers",
    "leader",
    "text",
)
REPOSITORY_NAMES = {
    "central": "bluetape4k-dependencies",
    **{key: f"bluetape4k-{key}" for key in REPOSITORY_KEYS},
}
CATALOG_REPOSITORIES = tuple(REPOSITORY_NAMES.values())
SIGNING_REPOSITORIES = tuple(
    name for name in CATALOG_REPOSITORIES if name != "bluetape4k-experimental"
)
PUBLISHER_REPOSITORIES = tuple(
    name
    for name in SIGNING_REPOSITORIES
    if name != REPOSITORY_NAMES["central"]
)
TOP_LEVEL_FIELDS = frozenset({"schema_version", "central", "repositories"})
REPOSITORY_FIELDS = frozenset(
    {"root", "catalog", "origin", "branch", "base_sha", "expected_head", "clean"}
)
GIT_OBJECT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PRIVATE_ARMOR_RE = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----.*?"
    r"(?:-----END [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----|\Z)",
    re.IGNORECASE | re.DOTALL,
)
ASSIGNMENT_CANDIDATE_RE = re.compile(
    r"(?m)(?<![\w.%+-])(?=([^\s=:?&#]+)"
    r"([ \t]*[=:][ \t]*)([^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*))"
)
SECRET_URI_RE = re.compile(r"(?i)(://)[^/?#\s]*@")
AUTHORIZATION_RE = re.compile(
    r"(?i)(\bauthorization\s*[:=]\s*)(?:(?:bearer|basic)\s+)?[^\r\n]+"
)
COOKIE_RE = re.compile(r"(?i)(\b(?:set-cookie|cookie)\s*:\s*)[^\r\n]+")
BEARER_RE = re.compile(r"(?i)(\bbearer\s+)[^\s,;]+")
QUERY_PARAMETER_RE = re.compile(
    r"([?&])([^=&#\s]+)(\s*=\s*)([^&#\s]+)"
)
LINE_BREAK_IDENTIFIER_RE = re.compile(
    r"(?<![\w.%+\-=])([^\s=:?&#]+"
    r"(?:(?:[ \t]*(?:\r\n?|\n))+[ \t]*[^\s=:?&#]*)+)"
    r"(?=[ \t]*[=:])"
)
LINE_BREAK_SECRET_VALUE_RE = re.compile(
    r"(?<![\w.%+-])([^\s=:?&#]+)[ \t]*[=:][ \t]*(?:\r\n?|\n)"
)
FOLDED_VALUE_RE = re.compile(
    r"(?m)(?<![\w.%+-])([^\s=:?&#]+)[ \t]*[=:][^\r\n]*(?:\r\n?|\n)[ \t]+"
)
MAX_IDENTIFIER_DECODE_ROUNDS = 4
MAX_SECRET_IDENTIFIER_CHARS = 512
MAX_GIT_CAPTURE_BYTES = 4 * 1024 * 1024
MAX_REDACTION_SCAN_CHARS = MAX_GIT_CAPTURE_BYTES
MAX_CANDIDATE_REPOSITORY_FILES = 4096
MAX_CANDIDATE_REPOSITORY_FILE_BYTES = 16 * 1024 * 1024
MAX_CANDIDATE_REPOSITORY_BYTES = 128 * 1024 * 1024
MAX_CANDIDATE_REPOSITORY_DEPTH = 64
GIT_CAPTURE_TIMEOUT_SECONDS = 30.0
SECRET_NAME_PARTS = frozenset(
    {"password", "passwd", "token", "secret", "credential", "key", "session"}
)
SECRET_COMPOUND_NAMES = frozenset(
    {
        "accesskey",
        "accesskeyid",
        "accesstoken",
        "apikey",
        "authtoken",
        "authorization",
        "bearertoken",
        "clientsecret",
        "cookie",
        "idtoken",
        "keypassword",
        "keystorepassword",
        "privatekey",
        "refreshtoken",
        "secretaccesskey",
        "setcookie",
        "signingkey",
        "signingpassword",
    }
)
SAFE_SECRET_LIKE_NAMES = frozenset(
    {
        "credentialing",
        "hockey",
        "keyboard",
        "keynote",
        "monkey",
        "mymonkey",
        "passwordless",
        "secretariat",
        "secretary",
        "sessionfactory",
        "tokenization",
        "tokenizer",
    }
)


@dataclasses.dataclass(frozen=True)
class CandidateRepository:
    key: str
    name: str
    root: Path
    catalog: Path
    origin: str
    branch: str
    base_sha: str
    expected_head: str


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strip_obfuscating_controls(value: str) -> tuple[str, bool]:
    value = ANSI_RE.sub("", value)
    has_unsupported_sequence = any(
        character == "\x1b" or 0x80 <= ord(character) <= 0x9F
        for character in value
    )
    value = CONTROL_RE.sub("", value)
    normalized = "".join(
        character
        for character in value
        if unicodedata.category(character) != "Cf"
        and not (
            unicodedata.category(character) == "Cc"
            and character not in {"\r", "\n"}
        )
        and not (
            unicodedata.category(character).startswith("Z")
            and character != " "
        )
    )
    return normalized, has_unsupported_sequence


def _normalize_secret_identifier(value: str) -> tuple[str, bool]:
    for _ in range(MAX_IDENTIFIER_DECODE_ROUNDS):
        decoded = urllib.parse.unquote_plus(unicodedata.normalize("NFKC", value))
        if decoded == value:
            break
        value = decoded
    value = unicodedata.normalize("NFKC", value)
    has_encoded_remainder = "%" in value
    value = ANSI_RE.sub("", value)
    has_disallowed_control = any(
        unicodedata.category(character) in {"Cc", "Cf"}
        for character in value
    )
    normalized = "".join(
        character
        for character in value
        if unicodedata.category(character) not in {"Cc", "Cf"}
    )
    return normalized, has_encoded_remainder or has_disallowed_control


def _collapse_secret_identifier(value: str) -> tuple[str, bool]:
    decoded, is_ambiguous = _normalize_secret_identifier(value)
    if is_ambiguous:
        return "", True
    separated = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", decoded)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    parts = tuple(
        part
        for part in re.sub(r"[^A-Za-z0-9]+", "_", separated).lower().split("_")
        if part
    )
    return "".join(parts), False


def _is_safe_secret_like_name(collapsed: str) -> bool:
    if collapsed in SAFE_SECRET_LIKE_NAMES:
        return True
    if "sessionfactory" not in collapsed:
        return False
    remainder = collapsed.replace("sessionfactory", "")
    secret_names = SECRET_NAME_PARTS | SECRET_COMPOUND_NAMES
    return not any(name in remainder for name in secret_names)


def is_secret_name(value: str) -> bool:
    """Classify normalized snake, kebab, camel, encoded, and compound names."""
    if len(value) > MAX_SECRET_IDENTIFIER_CHARS:
        return True
    collapsed, is_ambiguous = _collapse_secret_identifier(value)
    if is_ambiguous:
        return True
    secret_names = SECRET_NAME_PARTS | SECRET_COMPOUND_NAMES
    if _is_safe_secret_like_name(collapsed):
        return False
    return any(name in collapsed for name in secret_names)


def _contains_secret_assignment(value: str) -> bool:
    return any(
        is_secret_name(match.group(1))
        for match in ASSIGNMENT_CANDIDATE_RE.finditer(value)
    ) or any(
        is_secret_name(match.group(2))
        for match in QUERY_PARAMETER_RE.finditer(value)
    )


def _decode_obfuscated_text(value: str) -> tuple[str, bool]:
    normalized = value
    for _ in range(MAX_IDENTIFIER_DECODE_ROUNDS):
        decoded = urllib.parse.unquote_plus(unicodedata.normalize("NFKC", normalized))
        if decoded == normalized:
            break
        normalized = decoded
    return normalized, normalized != value


def _is_sensitive_header_name(value: str) -> bool:
    collapsed, is_ambiguous = _collapse_secret_identifier(value)
    return is_ambiguous or collapsed in {"authorization", "cookie", "setcookie"}


def _has_obfuscated_secret_syntax(value: str) -> bool:
    if len(value) > MAX_REDACTION_SCAN_CHARS:
        return True
    normalized, changed = _decode_obfuscated_text(value)
    has_remaining_obfuscation = (
        urllib.parse.unquote_plus(unicodedata.normalize("NFKC", normalized))
        != normalized
    )
    return changed and (
        has_remaining_obfuscation
        or _contains_secret_assignment(normalized)
        or AUTHORIZATION_RE.search(normalized) is not None
        or COOKIE_RE.search(normalized) is not None
        or _contains_line_break_secret_candidate(normalized)
    )


def _contains_line_break_secret_candidate(value: str) -> bool:
    if any(
        is_secret_name(match.group(1)) or _is_sensitive_header_name(match.group(1))
        for match in FOLDED_VALUE_RE.finditer(value)
    ):
        return True
    if any(
        is_secret_name(match.group(1))
        for match in LINE_BREAK_SECRET_VALUE_RE.finditer(value)
    ):
        return True
    for match in LINE_BREAK_IDENTIFIER_RE.finditer(value):
        if len(match.group(1)) > MAX_SECRET_IDENTIFIER_CHARS:
            return True
        fragments = tuple(
            fragment
            for fragment in re.split(r"[ \t\r\n]+", match.group(1))
            if fragment
        )
        fragment_is_sensitive = tuple(
            is_secret_name(fragment) or _is_sensitive_header_name(fragment)
            for fragment in fragments
        )
        identifier = "".join(fragments)
        identifier_collapsed, identifier_is_ambiguous = _collapse_secret_identifier(
            identifier
        )
        if not identifier_is_ambiguous and _is_safe_secret_like_name(
            identifier_collapsed
        ):
            continue
        if len(fragments) == 1 and fragment_is_sensitive[0]:
            return True
        if any(fragment_is_sensitive[:-1]):
            return True
        if fragment_is_sensitive[-1]:
            continue
        final_fragment, final_is_ambiguous = _collapse_secret_identifier(
            fragments[-1]
        )
        if not final_is_ambiguous and _is_safe_secret_like_name(final_fragment):
            continue
        if is_secret_name(identifier) or _is_sensitive_header_name(identifier):
            return True
    return False


def _redact_assignments(value: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in ASSIGNMENT_CANDIDATE_RE.finditer(value):
        key_start, _key_end = match.span(1)
        if key_start < cursor or not is_secret_name(match.group(1)):
            continue
        parts.append(value[cursor:key_start])
        parts.append(f"{match.group(1)}{match.group(2)}<redacted>")
        cursor = match.end(3)
    parts.append(value[cursor:])
    return "".join(parts)


def _redact_query_parameter(match: re.Match[str]) -> str:
    prefix, key, separator, _value = match.groups()
    if is_secret_name(key):
        return f"{prefix}{key}{separator}<redacted>"
    return match.group(0)


def redact_diagnostic(value: Any, *, max_chars: int | None = None) -> str:
    """Return credential-free diagnostic text suitable for logs and errors."""
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            text = "<redacted>"
            return text[:max_chars] if max_chars is not None else text
    else:
        text = str(value)
    if _has_obfuscated_secret_syntax(text):
        text = "<redacted>"
        return text[:max_chars] if max_chars is not None else text
    text, has_unsupported_sequence = _strip_obfuscating_controls(text)
    if has_unsupported_sequence:
        text = "<redacted>"
        return text[:max_chars] if max_chars is not None else text
    if ("\r" in text or "\n" in text) and _contains_line_break_secret_candidate(text):
        text = "<redacted>"
        return text[:max_chars] if max_chars is not None else text
    text = PRIVATE_ARMOR_RE.sub("<redacted-private-key>", text)
    text = AUTHORIZATION_RE.sub(r"\1<redacted>", text)
    text = COOKIE_RE.sub(r"\1<redacted>", text)
    text = BEARER_RE.sub(r"\1<redacted>", text)
    text = QUERY_PARAMETER_RE.sub(_redact_query_parameter, text)
    text = _redact_assignments(text)
    text = SECRET_URI_RE.sub(r"\1<redacted>@", text)
    return text[:max_chars] if max_chars is not None else text


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _regular_nonsymlink(path: Path, description: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise RuntimeError(f"{description} is not readable: {path}") from exc
    if stat.S_ISLNK(mode):
        raise RuntimeError(f"{description} must not be a symlink: {path}")
    if not stat.S_ISREG(mode):
        raise RuntimeError(f"{description} must be a regular file: {path}")


def bounded_regular_file_bytes(
    path: Path,
    *,
    description: str,
    max_bytes: int,
    require_private_mode: bool = False,
) -> bytes:
    """Read one stable regular file without following its final component."""

    if max_bytes <= 0:
        raise ValueError("bounded file size limit must be positive")
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    except AttributeError as exc:
        raise RuntimeError("platform lacks no-follow file support") from exc
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise RuntimeError(f"{description} must be a regular file")
            if require_private_mode and stat.S_IMODE(opened.st_mode) & 0o077:
                raise RuntimeError(f"{description} must have private permissions")
            payload = source.read(max_bytes + 1)
            closed = os.fstat(source.fileno())
    except OSError as exc:
        raise RuntimeError(f"{description} cannot be read") from exc
    if len(payload) > max_bytes:
        raise RuntimeError(f"{description} exceeds the size limit")
    if (
        opened.st_dev != closed.st_dev
        or opened.st_ino != closed.st_ino
        or opened.st_size != len(payload)
        or closed.st_size != len(payload)
        or opened.st_mtime_ns != closed.st_mtime_ns
    ):
        raise RuntimeError(f"{description} changed while reading")
    return payload


def bounded_file_manifest(
    root: Path,
    *,
    description: str,
    max_files: int = MAX_CANDIDATE_REPOSITORY_FILES,
    max_file_bytes: int = MAX_CANDIDATE_REPOSITORY_FILE_BYTES,
    max_total_bytes: int = MAX_CANDIDATE_REPOSITORY_BYTES,
    max_entries: int | None = None,
    max_depth: int = MAX_CANDIDATE_REPOSITORY_DEPTH,
) -> dict[str, str]:
    """Hash a no-follow file tree with aggregate, per-file, and count limits."""
    if max_entries is None:
        max_entries = max_files * 2
    if min(max_files, max_file_bytes, max_total_bytes, max_entries, max_depth) <= 0:
        raise ValueError("file manifest limits must be positive")
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    except AttributeError as exc:
        raise RuntimeError("platform lacks no-follow file traversal support") from exc
    manifest: dict[str, str] = {}
    total_bytes = 0
    entry_count = 0

    def visit(directory_fd: int, relative_parts: tuple[str, ...]) -> None:
        nonlocal entry_count, total_bytes
        names: list[str] = []
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                entry_count += 1
                if entry_count > max_entries:
                    raise RuntimeError(f"{description} exceeds the entry count limit")
                names.append(entry.name)
        names.sort()
        for name in names:
            metadata = os.stat(
                name, dir_fd=directory_fd, follow_symlinks=False
            )
            if stat.S_ISLNK(metadata.st_mode):
                raise RuntimeError(f"{description} contains a symlink")
            if stat.S_ISDIR(metadata.st_mode):
                if len(relative_parts) + 1 > max_depth:
                    raise RuntimeError(f"{description} exceeds the depth limit")
                child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
                try:
                    opened_directory = os.fstat(child_fd)
                    if (
                        not stat.S_ISDIR(opened_directory.st_mode)
                        or metadata.st_dev != opened_directory.st_dev
                        or metadata.st_ino != opened_directory.st_ino
                    ):
                        raise RuntimeError(f"{description} changed while traversing")
                    visit(child_fd, (*relative_parts, name))
                finally:
                    os.close(child_fd)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError(f"{description} contains a non-file")
            if len(manifest) >= max_files:
                raise RuntimeError(f"{description} exceeds the file count limit")
            descriptor = os.open(name, file_flags, dir_fd=directory_fd)
            digest = hashlib.sha256()
            file_bytes = 0
            with os.fdopen(descriptor, "rb") as source:
                opened = os.fstat(source.fileno())
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or metadata.st_dev != opened.st_dev
                    or metadata.st_ino != opened.st_ino
                ):
                    raise RuntimeError(f"{description} changed while traversing")
                while chunk := source.read(1024 * 1024):
                    file_bytes += len(chunk)
                    if file_bytes > max_file_bytes:
                        raise RuntimeError(f"{description} exceeds the per-file limit")
                    if total_bytes + file_bytes > max_total_bytes:
                        raise RuntimeError(f"{description} exceeds the total byte limit")
                    digest.update(chunk)
                closed = os.fstat(source.fileno())
            if (
                opened.st_dev != closed.st_dev
                or opened.st_ino != closed.st_ino
                or opened.st_size != file_bytes
                or closed.st_size != file_bytes
                or opened.st_mtime_ns != closed.st_mtime_ns
            ):
                raise RuntimeError(f"{description} changed while hashing")
            total_bytes += file_bytes
            relative = Path(*relative_parts, name).as_posix()
            manifest[relative] = digest.hexdigest()

    try:
        root_fd = os.open(root, directory_flags)
        try:
            if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
                raise RuntimeError(f"{description} must be a directory")
            visit(root_fd, ())
        finally:
            os.close(root_fd)
    except OSError as exc:
        raise RuntimeError(f"{description} cannot be read") from exc
    return manifest


def run_bounded_capture(
    command: list[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    input_bytes: bytes | None = None,
    max_output_bytes: int = MAX_GIT_CAPTURE_BYTES,
    timeout_seconds: float = GIT_CAPTURE_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    """Run a trusted helper with bounded capture and inherited-group cleanup.

    This is an operational cleanup boundary, not an adversarial sandbox. A
    deliberately hostile descendant can create a new session and leave the
    process group; callers must execute only reviewed exact-source helpers.
    """
    if max_output_bytes <= 0 or timeout_seconds <= 0:
        raise ValueError("bounded command limits must be positive")
    if input_bytes is not None and len(input_bytes) > max_output_bytes:
        raise RuntimeError("bounded command input limit exceeded")
    deadline = time.monotonic() + timeout_seconds
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=None if environment is None else dict(environment),
        stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("bounded command pipes are unavailable")

    def process_group_alive() -> bool:
        process.poll()
        try:
            os.killpg(process.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    try:
        stdout = bytearray()
        stderr = bytearray()
        total = 0
        input_view = memoryview(input_bytes or b"")
        input_offset = 0
        with selectors.DefaultSelector() as io_selector:
            for name, stream in (
                ("stdout", process.stdout),
                ("stderr", process.stderr),
            ):
                os.set_blocking(stream.fileno(), False)
                io_selector.register(stream, selectors.EVENT_READ, name)
            if process.stdin is not None:
                os.set_blocking(process.stdin.fileno(), False)
                if input_view:
                    io_selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
                else:
                    process.stdin.close()
            while io_selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("bounded command timed out")
                for selector_key, _mask in io_selector.select(
                    timeout=min(0.05, remaining)
                ):
                    if selector_key.data == "stdin":
                        try:
                            written = os.write(
                                selector_key.fd,
                                input_view[input_offset : input_offset + 65536],
                            )
                        except BrokenPipeError:
                            written = len(input_view) - input_offset
                        except BlockingIOError:
                            continue
                        input_offset += written
                        if input_offset >= len(input_view):
                            io_selector.unregister(selector_key.fileobj)
                            selector_key.fileobj.close()
                        continue
                    try:
                        chunk = os.read(selector_key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        io_selector.unregister(selector_key.fileobj)
                        continue
                    remaining_budget = max_output_bytes - total
                    target = stdout if selector_key.data == "stdout" else stderr
                    if remaining_budget > 0:
                        target.extend(chunk[:remaining_budget])
                    total += len(chunk)
                    if total > max_output_bytes:
                        raise RuntimeError("bounded command output limit exceeded")
        returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        if process_group_alive():
            raise RuntimeError("bounded command left processes in its assigned group")
        return subprocess.CompletedProcess(
            command, returncode, bytes(stdout), bytes(stderr)
        )
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        drain_deadline = time.monotonic() + 5
        while process_group_alive() and time.monotonic() < drain_deadline:
            time.sleep(0.02)
        raise
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()
        process.stderr.close()


def _git(root: Path, *args: str) -> str:
    try:
        completed = run_bounded_capture(
            ["git", "-C", str(root), *args], cwd=root
        )
        if completed.returncode:
            raise subprocess.CalledProcessError(
                completed.returncode,
                completed.args,
                output=completed.stdout,
                stderr=completed.stderr,
            )
        return completed.stdout.decode("utf-8", errors="strict").strip()
    except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        raw_stderr = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else b""
        safe_stderr = redact_diagnostic(raw_stderr or b"")
        detail = " | ".join(
            line.strip() for line in safe_stderr.splitlines() if line.strip()
        )
        detail = detail[:500] or "no stderr"
        command = args[0] if args else "command"
        raise RuntimeError(f"git {command} failed for {root}: {detail}") from exc
    except OSError as exc:
        command = args[0] if args else "command"
        raise RuntimeError(f"cannot execute git {command} for {root}") from exc


def _approved_origin(key: str) -> str:
    return f"git@github.com:bluetape4k/{REPOSITORY_NAMES[key]}.git"


def inspect_repository_for_map(
    name: str, root: Path, expected_head: str | None = None
) -> dict[str, object]:
    """Build one strict repository-map entry from the checked-out git topology."""
    if name not in CATALOG_REPOSITORIES:
        raise RuntimeError(f"repository name is not managed: {name}")
    resolved_root = root.resolve()
    origin = _git(resolved_root, "remote", "get-url", "origin")
    expected_origin = f"git@github.com:bluetape4k/{name}.git"
    if origin != expected_origin:
        safe_origin = redact_diagnostic(origin)
        fingerprint = sha256_bytes(safe_origin.encode())[:12]
        raise RuntimeError(f"origin mismatch for {name}: sha256={fingerprint}")
    branch = _git(resolved_root, "branch", "--show-current")
    if not branch:
        branch = f"issues-242-243-{name}"
        try:
            completed = run_bounded_capture(
                [
                    "git",
                    "-C",
                    str(resolved_root),
                    "checkout",
                    "-B",
                    branch,
                    "HEAD",
                ],
                cwd=resolved_root,
            )
            if completed.returncode:
                raise RuntimeError("git checkout failed")
        except (OSError, RuntimeError) as exc:
            raise RuntimeError(
                f"cannot attach repository map branch for {name}"
            ) from exc
    head = _git(resolved_root, "rev-parse", "HEAD")
    peeled_commit = _git(resolved_root, "rev-parse", f"{head}^{{commit}}")
    if peeled_commit != head or (expected_head is not None and head != expected_head):
        raise RuntimeError(f"HEAD mismatch for {name}: {head}")
    develop_head = _git(
        resolved_root, "rev-parse", "refs/remotes/origin/develop^{commit}"
    )
    base_sha = _git(resolved_root, "merge-base", head, develop_head)
    if _git(resolved_root, "rev-parse", f"{base_sha}^{{commit}}") != base_sha:
        raise RuntimeError(f"base SHA does not peel for {name}")
    if _git(resolved_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError(f"worktree is dirty for {name}")
    return {
        "root": str(resolved_root),
        "catalog": str(resolved_root / "gradle" / "libs.versions.toml"),
        "origin": origin,
        "branch": branch,
        "base_sha": base_sha,
        "expected_head": head,
        "clean": True,
    }


def _validate_repository(key: str, value: Any, workspace: Path) -> CandidateRepository:
    if not isinstance(value, dict) or set(value) != REPOSITORY_FIELDS:
        raise RuntimeError(f"repository map fields are invalid for {key}")
    if value["clean"] is not True:
        raise RuntimeError(f"repository map must require clean state for {key}")
    for field in REPOSITORY_FIELDS - {"clean"}:
        if not isinstance(value[field], str) or not value[field]:
            raise RuntimeError(f"repository map {field} is invalid for {key}")

    root = Path(value["root"])
    catalog = Path(value["catalog"])
    if not root.is_absolute() or not catalog.is_absolute():
        raise RuntimeError(f"repository root and catalog must be absolute for {key}")
    resolved_root = root.resolve()
    resolved_catalog = catalog.resolve()
    if root != resolved_root or catalog != resolved_catalog:
        raise RuntimeError(
            f"repository paths must be canonical and non-symlinked for {key}"
        )
    if not _is_relative_to(resolved_root, workspace) or not _is_relative_to(
        resolved_catalog, resolved_root
    ):
        raise RuntimeError(
            f"repository and catalog paths must stay inside workspace for {key}"
        )
    if not resolved_root.is_dir() or resolved_root.is_symlink():
        raise RuntimeError(f"repository root is not a regular directory for {key}")
    _regular_nonsymlink(resolved_catalog, f"catalog for {key}")
    if resolved_catalog != resolved_root / "gradle" / "libs.versions.toml":
        raise RuntimeError(f"catalog path is not canonical for {key}")

    origin = value["origin"]
    if (
        origin != _approved_origin(key)
        or _git(resolved_root, "remote", "get-url", "origin") != origin
    ):
        raise RuntimeError(f"repository map origin mismatch for {key}")
    branch = value["branch"]
    if _git(resolved_root, "branch", "--show-current") != branch:
        raise RuntimeError(f"repository map branch mismatch for {key}")
    base_sha = value["base_sha"]
    expected_head = value["expected_head"]
    if (
        GIT_OBJECT.fullmatch(base_sha) is None
        or GIT_OBJECT.fullmatch(expected_head) is None
    ):
        raise RuntimeError(f"repository map git object is invalid for {key}")
    for label, object_id in (("base", base_sha), ("expected HEAD", expected_head)):
        peeled = _git(resolved_root, "rev-parse", f"{object_id}^{{commit}}")
        if peeled != object_id:
            raise RuntimeError(
                f"repository map {label} does not peel exactly for {key}"
            )
    develop_head = _git(
        resolved_root, "rev-parse", "refs/remotes/origin/develop^{commit}"
    )
    if _git(resolved_root, "merge-base", expected_head, develop_head) != base_sha:
        raise RuntimeError(
            f"repository map base is not the origin/develop fork point for {key}"
        )
    if _git(resolved_root, "rev-parse", "HEAD") != expected_head:
        raise RuntimeError(f"repository map HEAD mismatch for {key}")
    if _git(resolved_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError(f"repository worktree is not clean for {key}")
    return CandidateRepository(
        key,
        REPOSITORY_NAMES[key],
        resolved_root,
        resolved_catalog,
        origin,
        branch,
        base_sha,
        expected_head,
    )


def load_repository_map_v1(
    path: Path, workspace: Path
) -> tuple[CandidateRepository, ...]:
    """Load the exact central plus nine-repository candidate envelope."""
    if not path.is_absolute() or path.resolve() != path:
        raise RuntimeError("repository map path must be absolute and canonical")
    _regular_nonsymlink(path, "repository map")
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid repository map JSON") from exc
    if not isinstance(document, dict) or set(document) != TOP_LEVEL_FIELDS:
        raise RuntimeError("repository map top-level fields are invalid")
    if document["schema_version"] != 1:
        raise RuntimeError("repository map schema_version must be 1")
    repositories = document["repositories"]
    if not isinstance(repositories, dict) or set(repositories) != set(REPOSITORY_KEYS):
        raise RuntimeError(
            "repository map repositories must be the exact canonical nine-entry enum"
        )
    workspace_root = workspace.resolve()
    return (
        _validate_repository("central", document["central"], workspace_root),
        *(
            _validate_repository(key, repositories[key], workspace_root)
            for key in REPOSITORY_KEYS
        ),
    )


def create_catalog_lock(
    repositories: tuple[CandidateRepository, ...],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "catalogs": {
            item.key: {
                "path": str(item.catalog),
                "root": str(item.root),
                "origin": item.origin,
                "branch": item.branch,
                "base_sha": item.base_sha,
                "repository_head": item.expected_head,
                "declared_ref": item.expected_head,
                "peeled_commit": _git(
                    item.root, "rev-parse", f"{item.expected_head}^{{commit}}"
                ),
                "sha256": sha256_bytes(item.catalog.read_bytes()),
            }
            for item in repositories
        },
    }


def create_candidate_manifest(
    repository_map: Path,
    workspace: Path,
    repositories: tuple[CandidateRepository, ...],
    disposition: Path,
    cache_manifest: Path,
    human_ledger: Path,
    machine_ledger: dict[str, str],
) -> dict[str, Any]:
    for path, label in (
        (repository_map, "repository map"),
        (disposition, "disposition"),
        (cache_manifest, "cache manifest"),
        (human_ledger, "human ledger"),
    ):
        _regular_nonsymlink(path, label)
    catalog_lock = create_catalog_lock(repositories)
    return {
        "schema_version": 1,
        "workspace": str(workspace.resolve()),
        "central_root": str(repositories[0].root),
        "repository_map": {
            "path": str(repository_map),
            "sha256": sha256_bytes(repository_map.read_bytes()),
        },
        "catalog_lock": catalog_lock,
        "catalog_lock_sha256": sha256_bytes(canonical_json_bytes(catalog_lock)),
        "disposition": {
            "path": str(disposition),
            "sha256": sha256_bytes(disposition.read_bytes()),
        },
        "cache_manifest": {
            "path": str(cache_manifest),
            "sha256": sha256_bytes(cache_manifest.read_bytes()),
        },
        "human_ledger": {
            "path": str(human_ledger),
            "sha256": sha256_bytes(human_ledger.read_bytes()),
        },
        "machine_ledger": machine_ledger,
    }


def _verify_observation(value: Any, label: str) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise RuntimeError(f"invalid {label} observation")
    path = Path(value["path"])
    if not path.is_absolute() or path.resolve() != path:
        raise RuntimeError(f"{label} path must be absolute and canonical")
    _regular_nonsymlink(path, label)
    digest = value["sha256"]
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        raise RuntimeError(f"invalid {label} SHA-256")
    if sha256_bytes(path.read_bytes()) != digest:
        raise RuntimeError(f"{label} SHA-256 mismatch")
    return path


def verify_candidate_manifest(path: Path) -> dict[str, Any]:
    _regular_nonsymlink(path, "candidate manifest")
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid candidate manifest JSON") from exc
    expected_fields = {
        "schema_version",
        "workspace",
        "central_root",
        "repository_map",
        "catalog_lock",
        "catalog_lock_sha256",
        "disposition",
        "cache_manifest",
        "human_ledger",
        "machine_ledger",
    }
    if not isinstance(document, dict) or set(document) != expected_fields:
        raise RuntimeError("invalid candidate manifest fields")
    if document["schema_version"] != 1:
        raise RuntimeError("invalid candidate manifest schema")
    workspace = Path(document["workspace"])
    central_root = Path(document["central_root"])
    if not workspace.is_absolute() or workspace.resolve() != workspace:
        raise RuntimeError("invalid candidate workspace")
    repository_map = _verify_observation(document["repository_map"], "repository map")
    _verify_observation(document["disposition"], "disposition")
    _verify_observation(document["cache_manifest"], "cache manifest")
    _verify_observation(document["human_ledger"], "human ledger")
    machine_ledger = document["machine_ledger"]
    if not isinstance(machine_ledger, dict) or set(machine_ledger) != {
        "path",
        "fencing_token",
        "genesis_record_sha256",
    }:
        raise RuntimeError("invalid machine ledger binding")
    ledger_path = Path(machine_ledger["path"])
    if not ledger_path.is_absolute() or ledger_path.resolve() != ledger_path:
        raise RuntimeError("machine ledger path must be absolute and canonical")
    _regular_nonsymlink(ledger_path, "machine ledger")
    ledger = json.loads(ledger_path.read_bytes())
    if (
        not isinstance(ledger, dict)
        or ledger.get("schema_version") != 1
        or ledger.get("fencing_token") != machine_ledger["fencing_token"]
        or not isinstance(ledger.get("records"), list)
        or not ledger["records"]
        or record_sha256(ledger["records"][0])
        != machine_ledger["genesis_record_sha256"]
    ):
        raise RuntimeError("machine ledger genesis mismatch")
    repositories = load_repository_map_v1(repository_map, workspace)
    if repositories[0].root != central_root:
        raise RuntimeError("candidate central root mismatch")
    catalog_lock = create_catalog_lock(repositories)
    if document["catalog_lock"] != catalog_lock:
        raise RuntimeError("candidate catalog lock mismatch")
    digest = sha256_bytes(canonical_json_bytes(catalog_lock))
    if document["catalog_lock_sha256"] != digest:
        raise RuntimeError("candidate catalog lock SHA-256 mismatch")
    return document


def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if path.read_bytes() != payload:
            raise RuntimeError("atomic write read-back mismatch")
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def record_sha256(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def read_ledger(path: Path, *, fencing_token: str) -> dict[str, Any]:
    _regular_nonsymlink(path, "ledger")
    try:
        ledger = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RuntimeError("interrupted or invalid ledger") from exc
    if not isinstance(ledger, dict) or set(ledger) != {
        "schema_version",
        "fencing_token",
        "records",
    }:
        raise RuntimeError("invalid ledger envelope")
    if ledger["schema_version"] != 1 or ledger["fencing_token"] != fencing_token:
        raise RuntimeError("ledger fencing token mismatch")
    records = ledger["records"]
    if not isinstance(records, list):
        raise TypeError("invalid ledger records")
    prior = None
    for sequence, existing in enumerate(records, start=1):
        if (
            not isinstance(existing, dict)
            or set(existing) != {"sequence", "prior_record_sha256", "payload"}
            or existing["sequence"] != sequence
            or existing["prior_record_sha256"] != prior
        ):
            raise RuntimeError("interrupted or invalid ledger chain")
        prior = record_sha256(existing)
    return ledger


def _append_ledger_record_unlocked(
    path: Path, payload: dict[str, Any], *, fencing_token: str
) -> dict[str, Any]:
    if not fencing_token:
        raise RuntimeError("fencing token must be non-empty")
    if path.exists():
        ledger = read_ledger(path, fencing_token=fencing_token)
        records = ledger["records"]
    else:
        ledger = {"schema_version": 1, "fencing_token": fencing_token, "records": []}
        records = ledger["records"]
    prior = record_sha256(records[-1]) if records else None
    record = {
        "sequence": len(records) + 1,
        "prior_record_sha256": prior,
        "payload": payload,
    }
    records.append(record)
    write_atomic(path, canonical_json_bytes(ledger))
    read_back = json.loads(path.read_bytes())
    if read_back != ledger:
        raise RuntimeError("ledger read-back mismatch")
    return record


def append_ledger_record(
    path: Path, payload: dict[str, Any], *, fencing_token: str
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return _append_ledger_record_unlocked(
            path, payload, fencing_token=fencing_token
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def initialize_ledger_genesis(
    path: Path, payload: dict[str, Any], *, fencing_token: str
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if path.exists():
            ledger = read_ledger(path, fencing_token=fencing_token)
            records = ledger["records"]
            if not records or records[0].get("payload") != payload:
                raise RuntimeError("ledger genesis input mismatch")
            return records[0]
        return _append_ledger_record_unlocked(
            path, payload, fencing_token=fencing_token
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--workspace", type=Path, required=True)
    prepare.add_argument("--central", type=Path, required=True)
    prepare.add_argument("--repository-map", type=Path, required=True)
    prepare.add_argument("--cache-manifest", type=Path, required=True)
    prepare.add_argument("--manifest-out", type=Path, required=True)
    prepare.add_argument("--ledger", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        verify_candidate_manifest(args.manifest)
        print(sha256_bytes(args.manifest.read_bytes()))
        return 0

    repositories = load_repository_map_v1(args.repository_map, args.workspace)
    if repositories[0].root != args.central.resolve():
        raise RuntimeError("central worktree does not match repository map")
    disposition = (
        args.central / "config" / "central-catalog-authority-dispositions.json"
    )
    catalog_lock = create_catalog_lock(repositories)
    input_binding = {
        "stage": "prepare-inputs",
        "repository_map_sha256": sha256_bytes(args.repository_map.read_bytes()),
        "catalog_lock_sha256": sha256_bytes(canonical_json_bytes(catalog_lock)),
        "disposition_sha256": sha256_bytes(disposition.read_bytes()),
        "cache_manifest_sha256": sha256_bytes(args.cache_manifest.read_bytes()),
        "human_ledger_sha256": sha256_bytes(args.ledger.read_bytes()),
    }
    fencing_token = sha256_bytes(canonical_json_bytes(input_binding))
    machine_ledger_path = args.manifest_out.with_name("candidate-ledger.json")
    genesis = initialize_ledger_genesis(
        machine_ledger_path,
        input_binding,
        fencing_token=fencing_token,
    )
    machine_ledger = {
        "path": str(machine_ledger_path),
        "fencing_token": fencing_token,
        "genesis_record_sha256": record_sha256(genesis),
    }
    manifest = create_candidate_manifest(
        args.repository_map,
        args.workspace,
        repositories,
        disposition,
        args.cache_manifest,
        args.ledger,
        machine_ledger,
    )
    write_atomic(args.manifest_out, canonical_json_bytes(manifest))
    verify_candidate_manifest(args.manifest_out)
    manifest_sha = sha256_bytes(args.manifest_out.read_bytes())
    print(manifest_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
