#!/usr/bin/env python3
"""Run bounded, receipt-bound validation phases for Issues #242 and #243.

The runner is deliberately small and credential-free.  It accepts the strict
catalog repository map produced by ``catalog_candidate.py`` and a local
receipt, builds only allowlisted commands, disables Gradle's persistent build
and configuration caches, and records redacted output digests.  A successful
cache entry is reusable only after its output file is read back and hashed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

PHASES = (
    "signing-buildsrc",
    "timefold-graphs-baseline",
    "consumers",
    "publication-poms",
)
MAX_WORKERS = 2
CHILD_TIMEOUT_SECONDS = 600
PUBLICATION_POMS_TIMEOUT_SECONDS = 1800
TERMINATE_GRACE_SECONDS = 5
DRAIN_SECONDS = 5
MAX_DIAGNOSTIC_LINES = 80
MAX_FAILURE_ARTIFACT_BYTES = 2 * 1024 * 1024
GRADLE_FLAGS = (
    "--no-daemon",
    "--no-configuration-cache",
    "--no-build-cache",
    "--console=plain",
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
CATALOG_REPOSITORIES = SIGNING_REPOSITORIES + ("bluetape4k-experimental",)
CONSUMER_REPOSITORIES = ("timefold-workshop", "clinic-appointment")
CANONICAL_HELPER_RELATIVE = Path(
    "config/publishing-signing/PublishingSigningKeySupport.kt"
)
GENERATED_HELPER_RELATIVE = Path(
    "buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt"
)
TIMEFOLD_COORDINATES = (
    "ai.timefold.solver:timefold-solver-core",
    "ai.timefold.solver:timefold-solver-benchmark",
    "com.fasterxml.jackson.core:jackson-databind",
    "org.springframework.boot:spring-boot-starter",
)
TIMEFOLD_GRAPH_TASKS = {
    "bluetape4k-exposed": (
        ":exposed:timefold-solver-persistence:dependencyInsight",
    ),
    "timefold-workshop": (
        ":01-quickstarts:school-timetabling:dependencyInsight",
    ),
    "clinic-appointment": (
        ":appointment-solver:dependencyInsight",
    ),
}
CONSUMER_TASKS = {
    "bluetape4k-exposed": (":exposed:timefold-solver-persistence:test",),
    "timefold-workshop": (
        ":00-shared:bluetape4k-timefold:test",
        ":01-quickstarts:school-timetabling:test",
        ":exposed:jdbc-examples:test",
        ":exposed:r2dbc-examples:test",
    ),
    "clinic-appointment": (
        ":appointment-solver:test",
        ":appointment-api:test",
        ":appointment-solver:dependencyInsight",
    ),
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PRIVATE_ARMOR_RE = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----.*?"
    r"-----END [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----",
    re.IGNORECASE | re.DOTALL,
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)(\b(?:password|passwd|secret|token|credential|access[_-]?key|"
    r"private[_-]?key|signing[_-]?key)\b\s*[=:]\s*)([^\r\n]+)"
)
SECRET_URI_RE = re.compile(r"(?i)(://[^\s:/]+:)[^\s@]+(@)")
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class ValidationFailure(RuntimeError):
    """Raised when one bounded validation job fails."""

    def __init__(self, message: str, result: Optional[CommandResult] = None) -> None:
        super().__init__(message)
        self.result = result


class InputContractError(RuntimeError):
    """Raised when the repository map or local receipt is not fail-closed."""


@dataclasses.dataclass(frozen=True)
class CommandResult:
    status: str
    returncode: Optional[int]
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool
    process_group_terminated: bool
    termination_signal: Optional[str]
    output_sha256: str
    diagnostics: str
    failure_artifact: Optional[Path] = None
    cached: bool = False


@dataclasses.dataclass(frozen=True)
class ValidationJob:
    repository: str
    phase: str
    cwd: Path
    command: tuple[str, ...]
    configuration: str
    task_set: tuple[str, ...]
    repository_head: str
    helper_sha256: str
    catalog_sha256: str
    bom_sha256: str
    jdk_version: str
    gradle_version: str

    @property
    def cache_key(self) -> str:
        return cache_key(
            repository=self.repository,
            repository_head=self.repository_head,
            helper_sha256=self.helper_sha256,
            catalog_sha256=self.catalog_sha256,
            bom_sha256=self.bom_sha256,
            task_set=self.task_set,
            configuration=self.configuration,
            jdk_version=self.jdk_version,
            gradle_version=self.gradle_version,
        )


@dataclasses.dataclass(frozen=True)
class PhaseResult:
    phase: str
    status: str
    output_sha256: str
    jobs: tuple[CommandResult, ...]
    failure: Optional[str] = None


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, description: str, *, require_secure_mode: bool = False) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise InputContractError(f"{description} is not readable: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise InputContractError(f"{description} must be a regular non-symlink file: {path}")
    if require_secure_mode and stat.S_IMODE(metadata.st_mode) & 0o077:
        raise InputContractError(f"{description} must not be group/world accessible: {path}")


def _canonical_existing_file(path: Path, description: str) -> Path:
    if not path.is_absolute() or path.resolve() != path:
        raise InputContractError(f"{description} must be absolute and canonical: {path}")
    _regular_file(path, description)
    return path


def _canonical_json_path(path: Path, description: str) -> Path:
    return _canonical_existing_file(path, description)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _absolute_without_following(path: Path) -> Path:
    """Make an absolute lexical path without resolving symlink components."""

    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(metadata.st_mode):
            raise InputContractError(f"path contains a symlink: {path}")


def _validate_sha256(value: str, description: str) -> str:
    if SHA256_RE.fullmatch(value) is None:
        raise InputContractError(f"invalid {description} SHA-256")
    return value


def cache_key(
    *,
    repository: str,
    repository_head: str,
    helper_sha256: str,
    catalog_sha256: str,
    bom_sha256: str,
    task_set: Sequence[str],
    configuration: str,
    jdk_version: str,
    gradle_version: str,
) -> str:
    """Return the canonical exact-input evidence cache key."""

    if not repository or not configuration or not jdk_version or not gradle_version:
        raise InputContractError("cache key identity fields must be non-empty")
    if COMMIT_RE.fullmatch(repository_head) is None:
        raise InputContractError("invalid repository HEAD for cache key")
    for value, label in (
        (helper_sha256, "helper"),
        (catalog_sha256, "catalog"),
        (bom_sha256, "BOM"),
    ):
        _validate_sha256(value, label)
    normalized_tasks = sorted({str(task) for task in task_set if str(task)})
    if not normalized_tasks:
        raise InputContractError("cache task set must not be empty")
    payload = {
        "schema_version": 1,
        "repository": repository,
        "repository_head": repository_head,
        "helper_sha256": helper_sha256,
        "catalog_sha256": catalog_sha256,
        "bom_sha256": bom_sha256,
        "task_set": normalized_tasks,
        "configuration": configuration,
        "jdk_version": jdk_version,
        "gradle_version": gradle_version,
    }
    return sha256_bytes(canonical_json_bytes(payload))


def _safe_cache_directory(path: Path) -> Path:
    path = _absolute_without_following(path)
    _reject_symlink_components(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    if path.resolve() != path or path.is_symlink():
        raise InputContractError(f"cache directory must not be a symlink: {path}")
    if not path.is_dir():
        raise InputContractError(f"cache path is not a directory: {path}")
    return path


def _atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path = _absolute_without_following(path)
    _reject_symlink_components(path.parent)
    if path.is_symlink():
        raise InputContractError(f"atomic target must not be a symlink: {path}")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _reject_symlink_components(parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if path.read_bytes() != payload:
            raise InputContractError(f"atomic write read-back mismatch: {path}")
        os.chmod(path, mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_cache_entry(cache_directory: Path, key: str) -> Optional[dict[str, Any]]:
    """Read a cache hit only if status, path, and output digest all verify."""

    if not SHA256_RE.fullmatch(key):
        raise InputContractError("invalid evidence cache key")
    cache_directory = _safe_cache_directory(cache_directory)
    entry_path = cache_directory / f"{key}.json"
    if not entry_path.exists():
        return None
    try:
        _regular_file(entry_path, "evidence cache entry", require_secure_mode=True)
        document = json.loads(entry_path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, InputContractError):
        return None
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return None
    if document.get("status") != "pass" or document.get("cache_key") != key:
        return None
    output_value = document.get("output_path")
    digest = document.get("output_sha256")
    if not isinstance(output_value, str) or not isinstance(digest, str):
        return None
    if SHA256_RE.fullmatch(digest) is None:
        return None
    output_path = Path(output_value)
    if not output_path.is_absolute() or output_path.resolve() != output_path:
        return None
    if not _is_relative_to(output_path, cache_directory):
        return None
    try:
        _regular_file(output_path, "evidence cache output", require_secure_mode=True)
        if sha256_file(output_path) != digest:
            return None
        output = output_path.read_bytes()
    except OSError:
        return None
    return {
        **document,
        "output_path": str(output_path),
        "output": output.decode("utf-8", errors="replace"),
    }


def write_cache_entry(
    cache_directory: Path,
    key: str,
    output: bytes,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    if not SHA256_RE.fullmatch(key):
        raise InputContractError("invalid evidence cache key")
    cache_directory = _safe_cache_directory(cache_directory)
    output_path = cache_directory / f"{key}.output"
    digest = sha256_bytes(output)
    _atomic_write(output_path, output)
    document: dict[str, Any] = {
        "schema_version": 1,
        "status": "pass",
        "cache_key": key,
        "output_path": str(output_path),
        "output_sha256": digest,
    }
    if metadata:
        for field, value in metadata.items():
            if field not in document:
                document[field] = value
    _atomic_write(cache_directory / f"{key}.json", canonical_json_bytes(document))
    hit = read_cache_entry(cache_directory, key)
    if hit is None:
        raise InputContractError("evidence cache read-back failed")
    return hit


def redact_output(value: Any) -> str:
    """Redact armor, secret assignments, credentials, controls, and ANSI escapes."""

    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = PRIVATE_ARMOR_RE.sub("<redacted-private-key>", text)
    text = SECRET_ASSIGNMENT_RE.sub(r"\1<redacted>", text)
    text = SECRET_URI_RE.sub(r"\1<redacted>\2", text)
    text = ANSI_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    return text


def bounded_diagnostics(value: Any, max_lines: int = MAX_DIAGNOSTIC_LINES) -> str:
    if max_lines <= 0:
        raise ValueError("max_lines must be positive")
    text = redact_output(value)
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _terminate_process_group(process: subprocess.Popen[bytes]) -> str:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return "SIGTERM"
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=DRAIN_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise ValidationFailure("process group did not drain after SIGKILL") from exc
        return "SIGKILL"


def run_command(
    *,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: float,
    failure_artifact: Optional[Path] = None,
) -> CommandResult:
    """Run one command in a new process group with bounded termination."""

    if not command:
        raise InputContractError("validation command must not be empty")
    if timeout_seconds <= 0:
        raise InputContractError("validation timeout must be positive")
    cwd = cwd.resolve()
    if not cwd.is_dir() or cwd.is_symlink():
        raise InputContractError(f"validation cwd is not a regular directory: {cwd}")
    started = time.monotonic()
    process: Optional[subprocess.Popen[bytes]] = None
    timed_out = False
    group_terminated = False
    termination_signal: Optional[str] = None
    stdout = b""
    stderr = b""
    launch_error: Optional[str] = None
    try:
        process = subprocess.Popen(
            [str(value) for value in command],
            cwd=str(cwd),
            env={str(key): str(value) for key, value in environment.items()},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            group_terminated = True
            termination_signal = _terminate_process_group(process)
            stdout, stderr = process.communicate()
    except OSError as exc:
        launch_error = f"cannot launch validation command: {exc.__class__.__name__}"
    ended = time.monotonic()
    raw_output = stdout + (b"\n" if stdout and stderr else b"") + stderr
    if launch_error:
        raw_output = launch_error.encode("utf-8")
    redacted = redact_output(raw_output)
    output_digest = sha256_bytes(redacted.encode("utf-8"))
    returncode = None if process is None else process.returncode
    status = "pass" if process is not None and returncode == 0 and not timed_out else "fail"
    artifact: Optional[Path] = None
    if status != "pass" and failure_artifact is not None:
        artifact = failure_artifact.resolve()
        payload = redacted.encode("utf-8")
        if len(payload) > MAX_FAILURE_ARTIFACT_BYTES:
            payload = payload[-MAX_FAILURE_ARTIFACT_BYTES:]
        _atomic_write(artifact, payload)
    return CommandResult(
        status=status,
        returncode=returncode,
        stdout=redact_output(stdout),
        stderr=redact_output(stderr),
        elapsed_seconds=ended - started,
        timed_out=timed_out,
        process_group_terminated=group_terminated,
        termination_signal=termination_signal,
        output_sha256=output_digest,
        diagnostics=bounded_diagnostics(redacted),
        failure_artifact=artifact,
    )


def run_bounded_jobs(
    items: Iterable[Any],
    worker: Callable[[Any], Any],
    *,
    max_workers: int,
) -> dict[Any, Any]:
    """Run at most ``max_workers`` jobs and never submit after first failure."""

    if max_workers <= 0:
        raise InputContractError("max_workers must be positive")
    pending = iter(items)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    futures: dict[concurrent.futures.Future[Any], Any] = {}
    results: dict[Any, Any] = {}

    def submit_next() -> bool:
        try:
            item = next(pending)
        except StopIteration:
            return False
        futures[executor.submit(worker, item)] = item
        return True

    try:
        for _ in range(max_workers):
            if not submit_next():
                break
        while futures:
            done, _ = concurrent.futures.wait(
                tuple(futures), return_when=concurrent.futures.FIRST_COMPLETED
            )
            completed: list[tuple[Any, Any]] = []
            failure: Optional[BaseException] = None
            for future in done:
                item = futures.pop(future)
                try:
                    completed.append((item, future.result()))
                except Exception as exc:  # noqa: BLE001 - cancel siblings on any worker failure
                    failure = exc
            if failure is not None:
                for future in futures:
                    future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)
                raise failure
            for item, result in completed:
                results[item] = result
            for _ in completed:
                submit_next()
    except BaseException:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    return results


def _load_receipt_module() -> Any:
    path = Path(__file__).resolve().with_name("verify-issues-242-243-receipt.py")
    spec = importlib.util.spec_from_file_location("issues_242_243_receipt_runner", path)
    if spec is None or spec.loader is None:
        raise InputContractError("cannot load strict receipt validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_strict_repository_map(path: Path) -> dict[str, Any]:
    """Load the exact central plus nine catalog repositories through v1."""

    try:
        return _load_receipt_module().load_repository_map(path)
    except Exception as exc:
        if isinstance(exc, InputContractError):
            raise
        raise InputContractError(f"strict repository map validation failed: {exc}") from exc


def _reject_secret_content(value: Any, location: str = "document") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if re.search(
                r"(?:password|passwd|private[_-]?key|access[_-]?token)",
                key_text,
                re.IGNORECASE,
            ) and not key_text.endswith(("_sha256", "-sha256")):
                raise InputContractError(f"secret-bearing receipt field: {location}.{key_text}")
            _reject_secret_content(nested, f"{location}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_content(nested, f"{location}[{index}]")
    elif isinstance(value, str) and (
        PRIVATE_ARMOR_RE.search(value)
        or re.search(r"(?:ghp_|github_pat_|AKIA[0-9A-Z]{12})", value)
    ):
        raise InputContractError(f"secret-bearing receipt value: {location}")


def load_local_receipt(path: Path, repository_map: Path) -> dict[str, Any]:
    """Read the local receipt and bind it to the exact map bytes."""

    path = _canonical_json_path(path, "local receipt")
    repository_map = _canonical_json_path(repository_map, "repository map")
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputContractError("invalid local receipt JSON") from exc
    if not isinstance(document, dict):
        raise InputContractError("local receipt must be an object")
    _reject_secret_content(document)
    receipt_module = _load_receipt_module()
    try:
        receipt_module._reject_controls(document)
        receipt_module._reject_secrets(document)
    except Exception as exc:
        raise InputContractError(f"local receipt contains unsafe content: {exc}") from exc
    binding = document.get("repository_map")
    if not isinstance(binding, Mapping):
        raise InputContractError("local receipt is missing repository_map binding")
    bound_path = binding.get("path")
    bound_digest = binding.get("sha256")
    if (
        not isinstance(bound_path, str)
        or not Path(bound_path).is_absolute()
        or Path(bound_path).resolve() != repository_map
    ):
        raise InputContractError("local receipt repository map path mismatch")
    if not isinstance(bound_digest, str) or bound_digest != sha256_file(repository_map):
        raise InputContractError("local receipt repository map SHA-256 mismatch")
    return document


def gradle_command(
    repository_root: Path,
    tasks: Sequence[str],
    *,
    configuration: str,
    arguments: Sequence[str] = (),
    max_workers: Optional[int] = None,
    refresh_dependencies: bool = False,
) -> tuple[str, ...]:
    if not tasks or any(not task for task in tasks):
        raise InputContractError("Gradle task set must not be empty")
    root = Path(repository_root)
    command: list[str] = [str(root / "gradlew")]
    if configuration == "buildSrc":
        command.extend(("-p", "buildSrc"))
    command.extend(str(task) for task in tasks)
    command.extend(str(argument) for argument in arguments)
    if refresh_dependencies:
        command.append("--refresh-dependencies")
    command.extend(GRADLE_FLAGS)
    if max_workers is not None:
        if max_workers <= 0:
            raise InputContractError("Gradle max-workers must be positive")
        command.append(f"--max-workers={max_workers}")
    return tuple(command)


def publication_pom_command(
    *, central_root: Path, workspace: Path, repository_map: Path
) -> tuple[str, ...]:
    script = central_root / "scripts" / "verify-publication-poms.py"
    return (
        sys.executable,
        str(script),
        "--workspace",
        str(workspace.resolve()),
        "--repository-map",
        str(repository_map.resolve()),
        "--summary",
    )


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InputContractError(f"cannot inspect repository: {root}") from exc
    return completed.stdout.strip()


def _tool_version(command: Sequence[str], *, cwd: Path) -> str:
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    output = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
    return output[0][:160] if output else "unavailable"


def detect_toolchain(root: Path) -> tuple[str, str]:
    java = shutil.which("java") or "java"
    jdk = _tool_version((java, "-version"), cwd=root)
    gradle = _tool_version((str(root / "gradlew"), "--version"), cwd=root)
    return jdk, gradle


def _entry_by_name(repository_map: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = repository_map.get("repositories")
    if not isinstance(entries, list):
        raise InputContractError("strict repository map has no repository list")
    result: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            raise InputContractError("strict repository map contains invalid entry")
        result[str(item["name"])] = dict(item)
    if set(result) != set(CATALOG_REPOSITORIES):
        raise InputContractError("strict repository map is not the exact catalog set")
    return result


def _digest_required(path: Path, description: str) -> str:
    path = _canonical_existing_file(path, description)
    return sha256_file(path)


def _job_digests(root: Path, central_root: Path) -> tuple[str, str, str]:
    helper = root / GENERATED_HELPER_RELATIVE
    if not helper.is_file() or helper.is_symlink():
        raise InputContractError(f"generated signing helper is missing: {helper}")
    catalog = root / "gradle" / "libs.versions.toml"
    bom = central_root / "build.gradle.kts"
    return (
        _digest_required(helper, "generated signing helper"),
        _digest_required(catalog, "repository catalog"),
        _digest_required(bom, "central BOM build"),
    )


def _make_job(
    *,
    repository: str,
    phase: str,
    root: Path,
    tasks: Sequence[str],
    configuration: str,
    repository_head: str,
    central_root: Path,
    arguments: Sequence[str] = (),
    max_workers: Optional[int] = None,
    refresh_dependencies: bool = False,
) -> ValidationJob:
    helper, catalog, bom = _job_digests(root, central_root)
    jdk, gradle = detect_toolchain(root)
    return ValidationJob(
        repository=repository,
        phase=phase,
        cwd=root,
        command=gradle_command(
            root,
            tasks,
            configuration=configuration,
            arguments=arguments,
            max_workers=max_workers,
            refresh_dependencies=refresh_dependencies,
        ),
        configuration=configuration,
        task_set=tuple(tasks) + tuple(arguments),
        repository_head=repository_head,
        helper_sha256=helper,
        catalog_sha256=catalog,
        bom_sha256=bom,
        jdk_version=jdk,
        gradle_version=gradle,
    )


def _consumer_root_from_receipt(
    receipt: Mapping[str, Any], name: str, requested_root: Optional[Path]
) -> tuple[Path, str]:
    consumers = receipt.get("consumers")
    if not isinstance(consumers, list):
        raise InputContractError("local receipt has no consumer entries")
    item = next((value for value in consumers if isinstance(value, Mapping) and value.get("name") == name), None)
    if not isinstance(item, Mapping):
        raise InputContractError(f"local receipt is missing consumer: {name}")
    value = item.get("candidate_worktree")
    head = item.get("candidate_head")
    if not isinstance(value, str) or not isinstance(head, str):
        raise InputContractError(f"consumer receipt binding is incomplete: {name}")
    root = Path(value).resolve()
    if requested_root is not None and root != requested_root.resolve():
        raise InputContractError(f"consumer root does not match receipt: {name}")
    if not root.is_dir() or root.is_symlink():
        raise InputContractError(f"consumer worktree is unavailable: {name}")
    if _git(root, "rev-parse", "HEAD") != head:
        raise InputContractError(f"consumer HEAD mismatch: {name}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise InputContractError(f"consumer worktree is dirty: {name}")
    return root, head


def _make_timefold_graph_jobs(
    *,
    repository: str,
    root: Path,
    repository_head: str,
    central_root: Path,
) -> tuple[ValidationJob, ...]:
    jobs: list[ValidationJob] = []
    for coordinate in TIMEFOLD_COORDINATES:
        jobs.append(
            _make_job(
                repository=repository,
                phase="timefold-graphs-baseline",
                root=root,
                tasks=TIMEFOLD_GRAPH_TASKS[repository],
                arguments=(
                    "--configuration",
                    "testRuntimeClasspath",
                    "--dependency",
                    coordinate,
                ),
                configuration="testRuntimeClasspath",
                repository_head=repository_head,
                central_root=central_root,
                refresh_dependencies=True,
            )
        )
    return tuple(jobs)


def build_phase_jobs(
    phase: str,
    repository_map: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    workshop_root: Optional[Path] = None,
    clinic_root: Optional[Path] = None,
    repositories: Optional[Sequence[str]] = None,
) -> tuple[ValidationJob, ...]:
    if phase not in PHASES:
        raise InputContractError(f"unknown validation phase: {phase}")
    entries = _entry_by_name(repository_map)
    central_root = Path(entries["bluetape4k-dependencies"]["candidate_worktree"])
    selected = tuple(repositories) if repositories is not None else None
    if phase == "signing-buildsrc":
        names = selected or SIGNING_REPOSITORIES
        unknown = set(names) - set(SIGNING_REPOSITORIES)
        if unknown:
            raise InputContractError("signing phase repository is not allowlisted")
        return tuple(
            _make_job(
                repository=name,
                phase=phase,
                root=Path(entries[name]["candidate_worktree"]),
                tasks=("test", "compileKotlin"),
                configuration="buildSrc",
                repository_head=str(entries[name]["candidate_head"]),
                central_root=central_root,
                max_workers=MAX_WORKERS,
            )
            for name in names
        )

    consumer_roots: dict[str, tuple[Path, str]] = {}
    if phase in {"timefold-graphs-baseline", "consumers"}:
        consumer_roots["timefold-workshop"] = _consumer_root_from_receipt(
            receipt, "timefold-workshop", workshop_root
        )
        consumer_roots["clinic-appointment"] = _consumer_root_from_receipt(
            receipt, "clinic-appointment", clinic_root
        )
    if phase == "timefold-graphs-baseline":
        jobs: list[ValidationJob] = []
        exposed = entries["bluetape4k-exposed"]
        jobs.extend(
            _make_timefold_graph_jobs(
                repository="bluetape4k-exposed",
                root=Path(exposed["candidate_worktree"]),
                repository_head=str(exposed["candidate_head"]),
                central_root=central_root,
            )
        )
        for name in ("timefold-workshop", "clinic-appointment"):
            root, head = consumer_roots[name]
            jobs.extend(
                _make_timefold_graph_jobs(
                    repository=name,
                    root=root,
                    repository_head=head,
                    central_root=central_root,
                )
            )
        return tuple(jobs)
    if phase == "consumers":
        jobs = []
        exposed = entries["bluetape4k-exposed"]
        jobs.append(
            _make_job(
                repository="bluetape4k-exposed",
                phase=phase,
                root=Path(exposed["candidate_worktree"]),
                tasks=CONSUMER_TASKS["bluetape4k-exposed"],
                configuration="consumer-tests",
                repository_head=str(exposed["candidate_head"]),
                central_root=central_root,
            )
        )
        for name in ("timefold-workshop", "clinic-appointment"):
            root, head = consumer_roots[name]
            jobs.append(
                _make_job(
                    repository=name,
                    phase=phase,
                    root=root,
                    tasks=CONSUMER_TASKS[name],
                    configuration="consumer-tests",
                    repository_head=head,
                    central_root=central_root,
                )
            )
        return tuple(jobs)
    if phase == "publication-poms":
        if selected:
            raise InputContractError("publication-poms does not accept repository selection")
        return (
            ValidationJob(
                repository="publication-poms",
                phase=phase,
                cwd=central_root,
                command=publication_pom_command(
                    central_root=central_root,
                    workspace=Path(str(repository_map["workspace_root"])),
                    repository_map=Path(str(receipt["repository_map"]["path"])),
                ),
                configuration="strict-non-candidate-map",
                task_set=("verify-publication-poms.py",),
                repository_head=str(entries["bluetape4k-dependencies"]["candidate_head"]),
                helper_sha256=_digest_required(
                    central_root / CANONICAL_HELPER_RELATIVE, "canonical signing helper"
                ),
                catalog_sha256=_digest_required(
                    central_root / "gradle" / "libs.versions.toml", "central catalog"
                ),
                bom_sha256=_digest_required(central_root / "build.gradle.kts", "central BOM build"),
                jdk_version="publication-pom-gate",
                gradle_version="publication-pom-gate",
            ),
        )
    raise InputContractError(f"unsupported validation phase: {phase}")


def _failure_artifact_for(receipt_path: Path, job: ValidationJob) -> Path:
    safe_phase = SAFE_NAME_RE.sub("-", job.phase).strip("-")
    safe_repo = SAFE_NAME_RE.sub("-", job.repository).strip("-")
    directory = receipt_path.parent / "failures"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    return directory / f"{safe_phase}-{safe_repo}-{int(time.time() * 1000000)}.log"


def _job_environment() -> dict[str, str]:
    environment = {str(key): str(value) for key, value in os.environ.items()}
    # Never pass Gradle init scripts or arbitrary JVM command-line injection
    # into a governance validation child.
    environment.pop("GRADLE_OPTS", None)
    environment.pop("JAVA_TOOL_OPTIONS", None)
    environment.pop("_JAVA_OPTIONS", None)
    return environment


def execute_job(job: ValidationJob, *, cache_directory: Path, receipt_path: Path) -> CommandResult:
    hit = read_cache_entry(cache_directory, job.cache_key)
    if hit is not None:
        output = str(hit.get("output", ""))
        return CommandResult(
            status="pass",
            returncode=0,
            stdout=output,
            stderr="",
            elapsed_seconds=0.0,
            timed_out=False,
            process_group_terminated=False,
            termination_signal=None,
            output_sha256=str(hit["output_sha256"]),
            diagnostics=bounded_diagnostics(output),
            cached=True,
        )
    timeout = (
        PUBLICATION_POMS_TIMEOUT_SECONDS
        if job.phase == "publication-poms"
        else CHILD_TIMEOUT_SECONDS
    )
    result = run_command(
        command=job.command,
        cwd=job.cwd,
        environment=_job_environment(),
        timeout_seconds=timeout,
        failure_artifact=_failure_artifact_for(receipt_path, job),
    )
    if result.status == "pass":
        output = (result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr).encode("utf-8")
        write_cache_entry(
            cache_directory,
            job.cache_key,
            output,
            metadata={
                "repository": job.repository,
                "phase": job.phase,
                "configuration": job.configuration,
            },
        )
    return result


def _worker(job: ValidationJob, *, cache_directory: Path, receipt_path: Path) -> CommandResult:
    result = execute_job(job, cache_directory=cache_directory, receipt_path=receipt_path)
    if result.status != "pass":
        detail = f"{job.repository} {job.phase} failed"
        if result.timed_out:
            detail += " (timeout)"
        if result.diagnostics:
            detail += f": {result.diagnostics}"
        raise ValidationFailure(detail, result)
    return result


def _phase_digest(phase: str, results: Sequence[CommandResult], failure: Optional[str]) -> str:
    payload = {
        "schema_version": 1,
        "phase": phase,
        "results": [
            {
                "status": result.status,
                "output_sha256": result.output_sha256,
                "cached": result.cached,
            }
            for result in results
        ],
        "failure": failure,
    }
    return sha256_bytes(canonical_json_bytes(payload))


def _write_receipt_update(path: Path, result: PhaseResult, jobs: Sequence[ValidationJob]) -> None:
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputContractError("cannot read local receipt for update") from exc
    if not isinstance(document, dict):
        raise InputContractError("local receipt must be an object")
    phases = document.setdefault("phases", [])
    if not isinstance(phases, list):
        raise InputContractError("local receipt phases must be an array")
    phases[:] = [item for item in phases if not isinstance(item, Mapping) or item.get("name") != result.phase]
    phases.append(
        {
            "name": result.phase,
            "result": result.status,
            "output_sha256": result.output_sha256,
        }
    )
    commands = document.setdefault("commands", [])
    if not isinstance(commands, list):
        raise InputContractError("local receipt commands must be an array")
    for job, command_result in zip(jobs, result.jobs):
        commands.append(
            {
                "repository": job.repository,
                "command": " ".join(redact_output(value) for value in job.command),
                "jdk": job.jdk_version,
                "gradle": job.gradle_version,
                "configuration": job.configuration,
                "elapsed_seconds": command_result.elapsed_seconds,
                "cache": "shared-read" if command_result.cached else "isolated",
                "result": command_result.status,
                "output_sha256": command_result.output_sha256,
            }
        )
    if result.status != "pass":
        failures = document.setdefault("failure_record", [])
        if not isinstance(failures, list):
            raise InputContractError("local receipt failure_record must be an array")
        failures.append(
            {
                "repository": jobs[0].repository if jobs else "runner",
                "phase": result.phase,
                "reason": "bounded validation phase failed",
                "output_sha256": result.output_sha256,
            }
        )
    _atomic_write(path, canonical_json_bytes(document))


def run_phase(
    phase: str,
    *,
    repository_map_path: Path,
    receipt_path: Path,
    workshop_root: Optional[Path] = None,
    clinic_root: Optional[Path] = None,
    cache_directory: Optional[Path] = None,
    repositories: Optional[Sequence[str]] = None,
    dry_run: bool = False,
) -> PhaseResult:
    repository_map_path = repository_map_path.resolve()
    receipt_path = receipt_path.resolve()
    repository_map = load_strict_repository_map(repository_map_path)
    receipt = load_local_receipt(receipt_path, repository_map_path)
    jobs = build_phase_jobs(
        phase,
        repository_map,
        receipt,
        workshop_root=workshop_root,
        clinic_root=clinic_root,
        repositories=repositories,
    )
    if dry_run:
        digest = _phase_digest(phase, (), None)
        return PhaseResult(phase, "pass", digest, ())
    cache_directory = cache_directory or receipt_path.parent / "cache"
    max_workers = 1 if phase == "publication-poms" else MAX_WORKERS
    jobs_by_id = {index: job for index, job in enumerate(jobs)}
    results: list[CommandResult] = []
    failure: Optional[str] = None
    try:
        outcome = run_bounded_jobs(
            tuple(jobs_by_id),
            lambda index: _worker(
                jobs_by_id[index], cache_directory=cache_directory, receipt_path=receipt_path
            ),
            max_workers=max_workers,
        )
        results = [outcome[index] for index in sorted(outcome)]
    except ValidationFailure as exc:
        failure = redact_output(str(exc))
        if exc.result is not None:
            results.append(exc.result)
    except Exception as exc:  # noqa: BLE001 - preserve bounded failure in the local receipt
        failure = redact_output(f"runner failure: {exc.__class__.__name__}: {exc}")
    status = "pass" if failure is None and len(results) == len(jobs) else "fail"
    output_digest = _phase_digest(phase, results, failure)
    phase_result = PhaseResult(phase, status, output_digest, tuple(results), failure)
    _write_receipt_update(receipt_path, phase_result, jobs[: len(results)])
    return phase_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--repository-map", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--workshop-root", type=Path)
    parser.add_argument("--clinic-root", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--repo", action="append", dest="repositories")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_phase(
            args.phase,
            repository_map_path=args.repository_map,
            receipt_path=args.receipt,
            workshop_root=args.workshop_root,
            clinic_root=args.clinic_root,
            cache_directory=args.cache_dir,
            repositories=args.repositories,
            dry_run=args.dry_run,
        )
    except (InputContractError, ValidationFailure, OSError, RuntimeError) as exc:
        print(redact_output(str(exc)), file=sys.stderr)
        return 2
    if args.summary or result.status != "pass":
        print(
            f"{result.phase}: status={result.status} output_sha256={result.output_sha256} "
            f"jobs={len(result.jobs)}"
        )
        if result.failure:
            print(bounded_diagnostics(result.failure), file=sys.stderr)
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
