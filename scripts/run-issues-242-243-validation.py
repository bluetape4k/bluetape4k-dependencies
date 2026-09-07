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
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

CATALOG_CANDIDATE_PATH = Path(__file__).resolve().with_name("catalog_candidate.py")
CATALOG_CANDIDATE_SPEC = importlib.util.spec_from_file_location(
    "issues_242_243_catalog_candidate_runner", CATALOG_CANDIDATE_PATH
)
if CATALOG_CANDIDATE_SPEC is None or CATALOG_CANDIDATE_SPEC.loader is None:
    raise RuntimeError("cannot load catalog_candidate.py")
catalog_candidate = importlib.util.module_from_spec(CATALOG_CANDIDATE_SPEC)
sys.modules.setdefault(CATALOG_CANDIDATE_SPEC.name, catalog_candidate)
CATALOG_CANDIDATE_SPEC.loader.exec_module(catalog_candidate)

PHASES = (
    "signing-buildsrc",
    "candidate-bom-publication",
    "timefold-graphs-baseline",
    "timefold-graphs-candidate",
    "consumers",
    "publication-poms",
)
EXECUTION_BOUNDARIES = ("persistent-trusted", "disposable-hosted")
MAX_WORKERS = 2
CHILD_TIMEOUT_SECONDS = 600
PUBLICATION_POMS_TIMEOUT_SECONDS = 1800
TOTAL_VALIDATION_BUDGET_SECONDS = 90 * 60
TERMINATE_GRACE_SECONDS = 5
DRAIN_SECONDS = 5
MAX_DIAGNOSTIC_LINES = 80
MAX_COMMAND_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_FAILURE_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_CACHE_ENTRY_BYTES = 64 * 1024
GRADLE_FLAGS = (
    "--no-daemon",
    "--no-configuration-cache",
    "--no-build-cache",
    "--console=plain",
)
SIGNING_REPOSITORIES = catalog_candidate.SIGNING_REPOSITORIES
CATALOG_REPOSITORIES = catalog_candidate.CATALOG_REPOSITORIES
CONSUMER_REPOSITORIES = ("timefold-workshop", "clinic-appointment")
CANDIDATE_BOM_VERSION = "2.1.0-issue-242.local"
CANDIDATE_BOM_ARTIFACTS = (
    f"bluetape4k-dependencies-{CANDIDATE_BOM_VERSION}.pom",
    f"bluetape4k-dependencies-{CANDIDATE_BOM_VERSION}.module",
)
CANONICAL_HELPER_RELATIVE = Path(
    "config/publishing-signing/PublishingSigningKeySupport.kt"
)
GENERATED_HELPER_RELATIVE = Path(
    "buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt"
)
CANDIDATE_INIT_SCRIPT_RELATIVE = Path("config/issues-242-243-candidate.init.gradle")
CANDIDATE_REPOSITORY_PROPERTY = "issues242243CandidateMavenRepo"
CANDIDATE_VERSION_PROPERTY = "issues242243CandidateBomVersion"
TIMEFOLD_COORDINATES = (
    "ai.timefold.solver:timefold-solver-core",
    "ai.timefold.solver:timefold-solver-benchmark",
    "ai.timefold.solver:timefold-solver-jackson",
    "ai.timefold.solver:timefold-solver-spring-boot-starter",
)
TIMEFOLD_GRAPH_TASKS = {
    "bluetape4k-exposed": (
        ":bluetape4k-exposed-timefold-solver-persistence:dependencyInsight",
    ),
    "timefold-workshop": (
        ":school-timetabling:dependencyInsight",
    ),
    "clinic-appointment": (
        ":appointment-solver:dependencyInsight",
    ),
}
TIMEFOLD_GRAPH_COORDINATES = {
    "bluetape4k-exposed": ("ai.timefold.solver:timefold-solver-core",),
    "timefold-workshop": (
        "ai.timefold.solver:timefold-solver-core",
        "ai.timefold.solver:timefold-solver-jackson",
        "ai.timefold.solver:timefold-solver-spring-boot-starter",
    ),
    "clinic-appointment": ("ai.timefold.solver:timefold-solver-benchmark",),
}
CONSUMER_TASKS = {
    "bluetape4k-exposed": (":bluetape4k-exposed-timefold-solver-persistence:test",),
    "timefold-workshop": (
        ":bluetape4k-timefold:test",
        ":school-timetabling:test",
        ":exposed-jdbc-examples:test",
        ":exposed-r2dbc-examples:test",
    ),
    "clinic-appointment": (
        ":appointment-solver:test",
        ":appointment-api:test",
    ),
}


def candidate_arguments(
    *,
    central_root: Path,
    candidate_maven_repository: Path,
) -> tuple[str, ...]:
    """Return explicit candidate-only arguments required by a repository."""

    return (
        "--init-script",
        str(central_root / CANDIDATE_INIT_SCRIPT_RELATIVE),
        f"-D{CANDIDATE_REPOSITORY_PROPERTY}={candidate_maven_repository}",
        f"-D{CANDIDATE_VERSION_PROPERTY}={CANDIDATE_BOM_VERSION}",
    )


def parse_dependency_insight(
    output: str, coordinate: str
) -> DependencyInsightObservation:
    """Parse one exact dependencyInsight component and its selection reasons."""

    if "No dependencies matching given input were found" in output:
        raise InputContractError(f"dependency was not resolved: {coordinate}")
    selected_pattern = re.compile(
        rf"^{re.escape(coordinate)}:([^\s]+)(?:\s+->\s+([^\s]+))?\s*$",
        re.MULTILINE,
    )
    selected_match = selected_pattern.search(output)
    if selected_match is None:
        raise InputContractError(f"dependency was not resolved: {coordinate}")
    selected_version = selected_match.group(2) or selected_match.group(1)
    if not selected_version or selected_version.startswith(("{", "[", "(")):
        raise InputContractError(f"selected version is invalid: {coordinate}")

    tail = output[selected_match.end() :]
    reason_heading = re.search(r"^\s*Selection reasons:\s*$", tail, re.MULTILINE)
    if reason_heading is None:
        raise InputContractError(f"selection reason is missing: {coordinate}")
    reasons: list[str] = []
    for line in tail[reason_heading.end() :].splitlines():
        match = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if match is not None:
            reason = match.group(1)
            if reason not in reasons:
                reasons.append(reason)
            continue
        if reasons:
            break
        if line.strip():
            break
    if not reasons:
        raise InputContractError(f"selection reason is missing: {coordinate}")
    return DependencyInsightObservation(
        coordinate=coordinate,
        selected_version=selected_version,
        selection_reason="; ".join(reasons),
    )


def validate_graph_result(job: ValidationJob, result: CommandResult) -> CommandResult:
    """Fail a successful Gradle invocation unless its graph evidence is semantic."""

    if result.status != "pass" or not job.phase.startswith("timefold-graphs-"):
        return result
    if not job.coordinate:
        return dataclasses.replace(
            result,
            status="fail",
            diagnostics="graph job is missing an exact dependency coordinate",
        )
    output = result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
    try:
        observation = parse_dependency_insight(output, job.coordinate)
        if (
            job.phase == "timefold-graphs-candidate"
            and observation.selected_version != "2.6.0"
        ):
            raise InputContractError(
                f"expected 2.6.0 but selected {observation.selected_version}: "
                f"{job.coordinate}"
            )
    except InputContractError as exc:
        return dataclasses.replace(
            result,
            status="fail",
            diagnostics=bounded_diagnostics(str(exc)),
        )
    return result


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
PRIVATE_ARMOR_RE = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----.*?"
    r"-----END [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----",
    re.IGNORECASE | re.DOTALL,
)
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
SECRET_ASSIGNMENT_ARG_RE = re.compile(r"^([^\s=]+)(=)(.*)$")
SAFE_ENVIRONMENT_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "JAVA_HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "GRADLE_USER_HOME",
        "USER",
        "LOGNAME",
        "TERM",
    }
)
CANDIDATE_ENVIRONMENT_KEYS = frozenset(
    {
        "BLUETAPE4K_DEPENDENCIES_CATALOG_PATH",
        "ISSUES_242_243_CANDIDATE_MAVEN_REPO",
    }
)
GRADLE_HOME_POLICY = "ephemeral-0700"


class ValidationFailure(RuntimeError):
    """Raised when one bounded validation job fails."""

    def __init__(self, message: str, result: Optional[CommandResult] = None) -> None:
        super().__init__(message)
        self.result = result


class InputContractError(RuntimeError):
    """Raised when the repository map or local receipt is not fail-closed."""


@dataclasses.dataclass(frozen=True)
class DependencyInsightObservation:
    coordinate: str
    selected_version: str
    selection_reason: str


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
    diagnostics: str = ""
    failure_artifact: Optional[Path] = None
    cached: bool = False
    job_id: str = ""
    repository: str = ""
    cancelled: bool = False
    cache_key: str = ""
    cache_output_path: str = ""
    candidate_artifact_manifest_bytes: bytes = b""


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
    arguments: tuple[str, ...] = ()
    repository_origin: str = ""
    repository_branch: str = ""
    job_id: str = ""
    environment_overrides: tuple[tuple[str, str], ...] = ()
    candidate_maven_repository: Optional[Path] = None
    produced_maven_repository: Optional[Path] = None
    candidate_catalog_path: Optional[Path] = None
    coordinate: str = ""

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
            arguments=self.arguments,
        )


@dataclasses.dataclass(frozen=True)
class PhaseResult:
    phase: str
    status: str
    output_sha256: str
    jobs: tuple[CommandResult, ...]
    failure: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SchedulerResult:
    """Results keyed by scheduler item, including blocked queue entries."""

    results: dict[Any, Any]
    errors: dict[Any, str]
    submitted: tuple[Any, ...]
    cancelled: tuple[Any, ...]
    first_failure: Optional[Any]


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
    if not path.is_absolute():
        raise InputContractError(f"{description} must be absolute and canonical: {path}")
    path = _absolute_without_following(path)
    _reject_symlink_components(path)
    if path.resolve() != path:
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


def _canonical_input_path(path: Path, description: str) -> Path:
    """Validate a caller path lexically before any canonical resolution."""

    if not path.is_absolute():
        raise InputContractError(f"{description} must be absolute and canonical: {path}")
    lexical = _absolute_without_following(path)
    _reject_symlink_components(lexical)
    if lexical.resolve() != lexical:
        raise InputContractError(f"{description} must be absolute and canonical: {lexical}")
    _regular_file(lexical, description)
    return lexical


def _canonical_directory(path: Path, description: str) -> Path:
    if not path.is_absolute():
        raise InputContractError(f"{description} must be absolute and canonical: {path}")
    lexical = _absolute_without_following(path)
    _reject_symlink_components(lexical)
    if lexical.resolve() != lexical or not lexical.is_dir() or lexical.is_symlink():
        raise InputContractError(f"{description} must be a canonical directory: {lexical}")
    return lexical


def _validate_sha256(value: str, description: str) -> str:
    if SHA256_RE.fullmatch(value) is None:
        raise InputContractError(f"invalid {description} SHA-256")
    return value


def candidate_artifact_manifest(repository: Path) -> dict[str, Any]:
    """Return a digest-bound manifest for the local java-platform publication."""

    repository = _canonical_directory(repository, "candidate Maven repository")
    try:
        repository_files = catalog_candidate.bounded_file_manifest(
            repository, description="candidate Maven repository"
        )
    except RuntimeError as exc:
        raise InputContractError(str(exc)) from exc
    artifact_directory = (
        repository
        / "io"
        / "github"
        / "bluetape4k"
        / "bluetape4k-dependencies"
        / CANDIDATE_BOM_VERSION
    )
    artifacts: dict[str, str] = {}
    for name in CANDIDATE_BOM_ARTIFACTS:
        path = _canonical_existing_file(
            artifact_directory / name, f"candidate BOM artifact {name}"
        )
        artifacts[name] = sha256_file(path)
    pom_name, module_name = CANDIDATE_BOM_ARTIFACTS
    try:
        pom_root = ET.parse(artifact_directory / pom_name).getroot()
        namespace = ""
        if pom_root.tag.startswith("{"):
            namespace = pom_root.tag.partition("}")[0] + "}"
        pom_identity = tuple(
            (pom_root.findtext(f"{namespace}{field}") or "").strip()
            for field in ("groupId", "artifactId", "version")
        )
        module_document = json.loads(
            (artifact_directory / module_name).read_text(encoding="utf-8")
        )
        component = module_document["component"]
        module_identity = (
            component["group"],
            component["module"],
            component["version"],
        )
    except (ET.ParseError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise InputContractError("candidate BOM metadata is malformed") from exc
    expected_identity = (
        "io.github.bluetape4k",
        "bluetape4k-dependencies",
        CANDIDATE_BOM_VERSION,
    )
    if pom_identity != expected_identity or module_identity != expected_identity:
        raise InputContractError("candidate BOM metadata identity mismatch")
    digest = sha256_bytes(canonical_json_bytes(repository_files))
    return {
        "repository_path": str(repository),
        "version": CANDIDATE_BOM_VERSION,
        "artifacts": artifacts,
        "repository_files": repository_files,
        "sha256": digest,
    }


def validated_candidate_catalog(central_root: Path) -> tuple[Path, str]:
    """Read back the central candidate catalog against its portable sidecar."""

    catalog = _canonical_existing_file(
        central_root / "gradle" / "libs.versions.toml", "candidate catalog"
    )
    sidecar = _canonical_existing_file(
        central_root / "gradle" / "libs.versions.toml.sha256",
        "candidate catalog checksum",
    )
    checksum_fields = sidecar.read_text(encoding="utf-8").strip().split()
    if not checksum_fields:
        raise InputContractError("candidate catalog checksum is empty")
    declared = checksum_fields[0]
    actual = sha256_file(catalog)
    if _validate_sha256(declared, "candidate catalog") != actual:
        raise InputContractError("candidate catalog checksum mismatch")
    return catalog, actual


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
    arguments: Sequence[str] = (),
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
        "arguments": list(arguments),
        "gradle_home_policy": GRADLE_HOME_POLICY,
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


def _empty_candidate_repository(path: Path) -> Path:
    path = _absolute_without_following(path)
    _reject_symlink_components(path.parent)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    repository = _canonical_directory(path, "candidate Maven repository")
    if any(repository.iterdir()):
        raise InputContractError("candidate Maven repository must be empty before publication")
    return repository


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
        entry_bytes = catalog_candidate.bounded_regular_file_bytes(
            entry_path,
            description="evidence cache entry",
            max_bytes=MAX_CACHE_ENTRY_BYTES,
            require_private_mode=True,
        )
        document = json.loads(entry_bytes.decode("utf-8"))
    except (OSError, RuntimeError, UnicodeDecodeError, json.JSONDecodeError):
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
        output = catalog_candidate.bounded_regular_file_bytes(
            output_path,
            description="evidence cache output",
            max_bytes=MAX_COMMAND_OUTPUT_BYTES,
            require_private_mode=True,
        )
    except (OSError, RuntimeError):
        return None
    if sha256_bytes(output) != digest:
        return None
    try:
        output_text = output.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    if redact_output(output_text) != output_text:
        # Never promote an old or externally-written cache entry containing
        # material that the runner would redact into a trusted cache hit.
        return None
    return {
        **document,
        "output_path": str(output_path),
        "output": output_text,
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
    if len(output) > MAX_COMMAND_OUTPUT_BYTES:
        raise InputContractError("evidence cache output exceeds the size limit")
    cache_directory = _safe_cache_directory(cache_directory)
    safe_output = redact_output(output).encode("utf-8")
    if len(safe_output) > MAX_COMMAND_OUTPUT_BYTES:
        raise InputContractError("redacted cache output exceeds the size limit")
    output_path = cache_directory / f"{key}.output"
    digest = sha256_bytes(safe_output)
    _atomic_write(output_path, safe_output)
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
                field_text = str(field)
                if catalog_candidate.is_secret_name(field_text):
                    continue
                document[field] = _redact_value(value)
    _atomic_write(cache_directory / f"{key}.json", canonical_json_bytes(document))
    hit = read_cache_entry(cache_directory, key)
    if hit is None:
        raise InputContractError("evidence cache read-back failed")
    return hit


def redact_output(value: Any) -> str:
    """Reuse the catalog candidate's credential-safe diagnostic boundary."""
    return catalog_candidate.redact_diagnostic(value)


def _redact_value(value: Any) -> Any:
    if isinstance(value, (bytes, str)):
        return redact_output(value)
    if isinstance(value, Mapping):
        return {
            str(key): _redact_value(nested)
            for key, nested in value.items()
            if not catalog_candidate.is_secret_name(str(key))
        }
    if isinstance(value, list):
        return [_redact_value(nested) for nested in value]
    if isinstance(value, tuple):
        return [_redact_value(nested) for nested in value]
    return value


def sanitized_environment(source: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Return the narrow child environment allowlist, excluding secret names."""

    values = os.environ if source is None else source
    return {
        str(key): str(value)
        for key, value in values.items()
        if str(key) in SAFE_ENVIRONMENT_KEYS
        and not catalog_candidate.is_secret_name(str(key))
    }


def child_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Keep safe base variables plus explicitly injected candidate bindings."""

    allowed = SAFE_ENVIRONMENT_KEYS | CANDIDATE_ENVIRONMENT_KEYS
    return {
        str(key): str(value)
        for key, value in source.items()
        if str(key) in allowed and not catalog_candidate.is_secret_name(str(key))
    }


def redact_command(command: Sequence[str]) -> tuple[str, ...]:
    """Redact secret assignments and option values without changing argv shape."""

    redacted: list[str] = []
    redact_next = False
    for raw_value in command:
        value = str(raw_value)
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        assignment = SECRET_ASSIGNMENT_ARG_RE.fullmatch(value)
        if assignment is not None and catalog_candidate.is_secret_name(
            assignment.group(1)
        ):
            redacted.append(f"{assignment.group(1)}=<redacted>")
            continue
        option_assignment = re.match(r"^(-{1,2}[^=]+)=(.*)$", value)
        if option_assignment is not None and catalog_candidate.is_secret_name(
            option_assignment.group(1).lstrip("-")
        ):
            redacted.append(f"{option_assignment.group(1)}=<redacted>")
            continue
        if value.startswith("-") and catalog_candidate.is_secret_name(
            value.lstrip("-")
        ):
            redacted.append(value)
            redact_next = True
            continue
        redacted.append(redact_output(value))
    if redact_next:
        # A missing option value is still represented by the original argv;
        # there is no value to disclose or replace.
        return tuple(redacted)
    return tuple(redacted)


def bounded_diagnostics(value: Any, max_lines: int = MAX_DIAGNOSTIC_LINES) -> str:
    if max_lines <= 0:
        raise ValueError("max_lines must be positive")
    text = redact_output(value)
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _process_group_alive(process: subprocess.Popen[bytes]) -> bool:
    process.poll()
    try:
        os.killpg(process.pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _wait_for_process_group_exit(
    process: subprocess.Popen[bytes], timeout_seconds: float
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while _process_group_alive(process):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)
    return True


def _terminate_process_group(process: subprocess.Popen[bytes]) -> str:
    if not _process_group_alive(process):
        return "SIGTERM"
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return "SIGTERM"
    if _wait_for_process_group_exit(process, TERMINATE_GRACE_SECONDS):
        return "SIGTERM"
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if not _wait_for_process_group_exit(process, DRAIN_SECONDS):
        raise ValidationFailure("process group did not drain after SIGKILL")
    return "SIGKILL"


def run_command(
    *,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: float,
    failure_artifact: Optional[Path] = None,
    cancel_event: Optional[threading.Event] = None,
) -> CommandResult:
    """Run trusted exact-source code with bounded inherited-group cleanup.

    The process group is an operational cleanup mechanism, not a portable
    adversarial sandbox. A hostile descendant can call ``setsid()`` and leave
    the group, so high-level callers must first validate the approved origin,
    exact reviewed HEAD, clean worktree, and immutable command inputs.
    """

    if not command:
        raise InputContractError("validation command must not be empty")
    if timeout_seconds <= 0:
        raise InputContractError("validation timeout must be positive")
    cwd = _canonical_directory(cwd, "validation cwd")
    started = time.monotonic()
    process: Optional[subprocess.Popen[bytes]] = None
    timed_out = False
    group_terminated = False
    termination_signal: Optional[str] = None
    cancelled = False
    output_limit_exceeded = False
    descendants_terminated = False
    stdout = b""
    stderr = b""
    launch_error: Optional[str] = None
    try:
        if cancel_event is not None and cancel_event.is_set():
            ended = time.monotonic()
            text = "validation command cancelled before launch"
            digest = sha256_bytes(text.encode("utf-8"))
            return CommandResult(
                status="blocked",
                returncode=None,
                stdout="",
                stderr="",
                elapsed_seconds=ended - started,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256=digest,
                diagnostics=text,
                cancelled=True,
            )
        process = subprocess.Popen(
            [str(value) for value in command],
            cwd=str(cwd),
            env=child_environment(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        if process.stdout is None or process.stderr is None:
            raise ValidationFailure("validation command pipes are unavailable")
        stdout_buffer = bytearray()
        stderr_buffer = bytearray()
        total_output_bytes = 0
        with selectors.DefaultSelector() as output_selector:
            for name, stream in (
                ("stdout", process.stdout),
                ("stderr", process.stderr),
            ):
                os.set_blocking(stream.fileno(), False)
                output_selector.register(stream, selectors.EVENT_READ, name)
            deadline = time.monotonic() + timeout_seconds
            while output_selector.get_map():
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    group_terminated = True
                    termination_signal = _terminate_process_group(process)
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    group_terminated = True
                    termination_signal = _terminate_process_group(process)
                    break
                events = output_selector.select(timeout=min(0.05, remaining))
                for selector_key, _mask in events:
                    try:
                        chunk = os.read(selector_key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        output_selector.unregister(selector_key.fileobj)
                        continue
                    remaining_budget = MAX_COMMAND_OUTPUT_BYTES - total_output_bytes
                    target = (
                        stdout_buffer
                        if selector_key.data == "stdout"
                        else stderr_buffer
                    )
                    if remaining_budget > 0:
                        target.extend(chunk[:remaining_budget])
                    total_output_bytes += len(chunk)
                    if total_output_bytes > MAX_COMMAND_OUTPUT_BYTES:
                        output_limit_exceeded = True
                        group_terminated = _process_group_alive(process)
                        if group_terminated:
                            termination_signal = _terminate_process_group(process)
                        break
                if output_limit_exceeded:
                    break
                if process.poll() is not None and _process_group_alive(process):
                    descendants_terminated = True
                    group_terminated = True
                    termination_signal = _terminate_process_group(process)
                    break
            if not (cancelled or timed_out or output_limit_exceeded):
                remaining = deadline - time.monotonic()
                try:
                    process.wait(timeout=max(0.01, remaining))
                except subprocess.TimeoutExpired:
                    timed_out = True
                    group_terminated = True
                    termination_signal = _terminate_process_group(process)
                else:
                    if _process_group_alive(process):
                        descendants_terminated = True
                        group_terminated = True
                        termination_signal = _terminate_process_group(process)
            stdout = bytes(stdout_buffer)
            stderr = bytes(stderr_buffer)
        process.stdout.close()
        process.stderr.close()
    except OSError as exc:
        launch_error = f"cannot launch validation command: {exc.__class__.__name__}"
    ended = time.monotonic()
    raw_output = stdout + (b"\n" if stdout and stderr else b"") + stderr
    if launch_error:
        raw_output = launch_error.encode("utf-8")
    elif output_limit_exceeded:
        raw_output = b"validation command output limit exceeded\n" + raw_output
    elif descendants_terminated:
        raw_output = b"validation command left processes in its assigned group\n" + raw_output
    redacted = redact_output(raw_output)
    output_digest = sha256_bytes(redacted.encode("utf-8"))
    returncode = None if process is None else process.returncode
    status = (
        "blocked"
        if cancelled
        else "pass"
        if (
            process is not None
            and returncode == 0
            and not timed_out
            and not output_limit_exceeded
            and not descendants_terminated
        )
        else "fail"
    )
    artifact: Optional[Path] = None
    if status != "pass" and failure_artifact is not None:
        artifact = _absolute_without_following(failure_artifact)
        _reject_symlink_components(artifact.parent)
        if artifact.is_symlink():
            raise InputContractError(f"failure artifact must not be a symlink: {artifact}")
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
        cancelled=cancelled,
    )


def run_bounded_jobs(
    items: Iterable[Any],
    worker: Callable[[Any], Any],
    *,
    max_workers: int,
    failure_predicate: Optional[Callable[[Any], bool]] = None,
    collect_failures: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> Any:
    """Run bounded jobs while preserving item/result identity on cancellation."""

    if max_workers <= 0:
        raise InputContractError("max_workers must be positive")
    all_items = tuple(items)
    item_order = {item: index for index, item in enumerate(all_items)}
    pending = iter(all_items)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    futures: dict[concurrent.futures.Future[Any], Any] = {}
    results: dict[Any, Any] = {}
    errors: dict[Any, str] = {}
    submitted: list[Any] = []
    cancelled: set[Any] = set()
    first_failure: Optional[Any] = None
    first_exception: Optional[BaseException] = None
    internal_cancel = cancel_event or threading.Event()
    stopped = False

    def submit_next() -> bool:
        nonlocal stopped
        if stopped or internal_cancel.is_set():
            return False
        try:
            item = next(pending)
        except StopIteration:
            return False
        futures[executor.submit(worker, item)] = item
        submitted.append(item)
        return True

    def ordered(items_to_order: Iterable[Any]) -> list[Any]:
        return sorted(items_to_order, key=lambda item: item_order[item])

    def mark_failure(item: Any, result: Any = None, error: Optional[BaseException] = None) -> None:
        nonlocal first_failure, first_exception, stopped
        if first_failure is None or item_order[item] < item_order[first_failure]:
            first_failure = item
            first_exception = error
        stopped = True
        internal_cancel.set()
        if error is not None:
            errors[item] = redact_output(f"{error.__class__.__name__}: {error}")
        elif result is not None:
            results[item] = result

    try:
        for _ in range(max_workers):
            if not submit_next():
                break
        while futures:
            done, _ = concurrent.futures.wait(
                tuple(futures), return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in sorted(done, key=lambda value: item_order[futures[value]]):
                item = futures.pop(future)
                if future.cancelled():
                    cancelled.add(item)
                    continue
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - collect and cancel siblings
                    mark_failure(item, error=exc)
                    continue
                results[item] = result
                if failure_predicate is not None and failure_predicate(result):
                    mark_failure(item, result=result)
            if stopped or internal_cancel.is_set():
                # Every submitted child is considered in-flight, even if its
                # executor worker has not switched to it yet.  Leave it in the
                # pool so a sibling failure is observed as a second result;
                # process workers receive the shared event and terminate
                # cooperatively.  Only never-submitted queue entries become
                # blocked below.
                if futures:
                    done, _ = concurrent.futures.wait(tuple(futures))
                    for future in sorted(done, key=lambda value: item_order[futures[value]]):
                        item = futures.pop(future)
                        if future.cancelled():
                            cancelled.add(item)
                            continue
                        try:
                            results[item] = future.result()
                        except Exception as exc:  # noqa: BLE001 - receipt needs mapping
                            errors[item] = redact_output(f"{exc.__class__.__name__}: {exc}")
                cancelled.update(item for item in all_items if item not in submitted)
                break
            for _ in done:
                submit_next()
        executor.shutdown(wait=True, cancel_futures=True)
    except BaseException:
        for future, item in list(futures.items()):
            if future.cancel():
                cancelled.add(item)
        internal_cancel.set()
        executor.shutdown(wait=True, cancel_futures=True)
        raise

    if not collect_failures:
        if first_exception is not None:
            raise first_exception
        if first_failure is not None:
            failed_result = results.get(first_failure)
            detail = f"bounded job failed: {first_failure}"
            if failed_result is not None and failed_result.diagnostics:
                detail += f": {failed_result.diagnostics}"
            raise ValidationFailure(detail, failed_result)
        return results
    return SchedulerResult(
        results=results,
        errors=errors,
        submitted=tuple(submitted),
        cancelled=tuple(ordered(cancelled)),
        first_failure=first_failure,
    )


def require_disposable_hosted_environment(environment: Mapping[str, str]) -> None:
    """Require GitHub's disposable hosted-runner boundary."""

    if (
        environment.get("GITHUB_ACTIONS") != "true"
        or environment.get("RUNNER_ENVIRONMENT") != "github-hosted"
    ):
        raise InputContractError(
            "disposable-hosted execution requires a GitHub-hosted Actions runner"
        )


def validate_execution_boundary(
    boundary: Optional[str],
    reviewed_heads: Sequence[str],
    required_heads: Iterable[str],
    environment: Mapping[str, str],
) -> None:
    """Bind execution to either reviewed heads or a disposable hosted job."""

    if boundary not in EXECUTION_BOUNDARIES:
        raise InputContractError("validation execution boundary is required")
    required_head_set = set(required_heads)
    if not required_head_set or any(
        COMMIT_RE.fullmatch(head) is None for head in required_head_set
    ):
        raise InputContractError("validation job has an invalid repository HEAD")
    if boundary == "disposable-hosted":
        require_disposable_hosted_environment(environment)
        if reviewed_heads:
            raise InputContractError(
                "disposable-hosted execution must not claim persistent reviewed heads"
            )
        return
    if len(reviewed_heads) != len(set(reviewed_heads)) or any(
        COMMIT_RE.fullmatch(head) is None for head in reviewed_heads
    ):
        raise InputContractError("reviewed HEAD assertions are invalid")
    if set(reviewed_heads) != required_head_set:
        raise InputContractError(
            "persistent-trusted execution requires every exact job HEAD to be reviewed"
        )


def required_phase_heads(
    phase: str,
    repository_map: Mapping[str, Any],
    receipt: Mapping[str, Any],
    repositories: Optional[Sequence[str]],
) -> frozenset[str]:
    """Derive the phase trust set without executing repository code."""

    entries = _entry_by_name(repository_map)
    if phase == "signing-buildsrc":
        names = tuple(repositories) if repositories is not None else SIGNING_REPOSITORIES
        if set(names) - set(SIGNING_REPOSITORIES):
            raise InputContractError("signing phase repository is not allowlisted")
        heads = (str(entries[name]["candidate_head"]) for name in names)
    elif phase in {"candidate-bom-publication", "publication-poms"}:
        if repositories:
            raise InputContractError(f"{phase} does not accept repository selection")
        heads = (str(entries["bluetape4k-dependencies"]["candidate_head"]),)
    elif phase == "timefold-graphs-baseline":
        heads = (
            str(entries["bluetape4k-exposed"]["base_sha"]),
            str(_consumer_entry(receipt, "timefold-workshop")["base_sha"]),
            str(_consumer_entry(receipt, "clinic-appointment")["base_sha"]),
        )
    elif phase in {"timefold-graphs-candidate", "consumers"}:
        heads = (
            str(entries["bluetape4k-exposed"]["candidate_head"]),
            str(_consumer_entry(receipt, "timefold-workshop")["candidate_head"]),
            str(_consumer_entry(receipt, "clinic-appointment")["candidate_head"]),
        )
    else:
        raise InputContractError(f"unknown validation phase: {phase}")
    result = frozenset(heads)
    if not result or any(COMMIT_RE.fullmatch(head) is None for head in result):
        raise InputContractError("validation phase has an invalid repository HEAD")
    return result


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


def validation_budget_remaining(receipt: Mapping[str, Any]) -> float:
    value = receipt.get("validation_budget")
    fields = {"total_seconds", "elapsed_seconds", "remaining_seconds"}
    if not isinstance(value, Mapping) or set(value) != fields:
        raise InputContractError("validation budget receipt is invalid")
    total = value["total_seconds"]
    elapsed = value["elapsed_seconds"]
    remaining = value["remaining_seconds"]
    if (
        isinstance(total, bool)
        or isinstance(elapsed, bool)
        or isinstance(remaining, bool)
        or not all(isinstance(item, (int, float)) for item in (total, elapsed, remaining))
        or float(total) != float(TOTAL_VALIDATION_BUDGET_SECONDS)
        or float(elapsed) < 0
        or float(remaining) < 0
        or abs(float(total) - float(elapsed) - float(remaining)) > 0.001
    ):
        raise InputContractError("validation budget receipt is invalid")
    return float(remaining)


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


def should_refresh_graph_dependencies(phase: str) -> bool:
    if phase not in {"timefold-graphs-baseline", "timefold-graphs-candidate"}:
        raise InputContractError(f"not a Timefold graph phase: {phase}")
    return phase == "timefold-graphs-candidate"


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
        completed = catalog_candidate.run_bounded_capture(
            ["git", "-C", str(root), *args], cwd=root
        )
        if completed.returncode:
            raise InputContractError(f"cannot inspect repository: {root}")
        return completed.stdout.decode("utf-8", errors="strict").strip()
    except (OSError, UnicodeDecodeError, RuntimeError) as exc:
        raise InputContractError(f"cannot inspect repository: {root}") from exc


def git_source_tree_sha256(root: Path, head: str) -> str:
    """Bind the exact tracked source tree used by a producer job."""

    root = _canonical_directory(root, "source worktree")
    if COMMIT_RE.fullmatch(head) is None:
        raise InputContractError("invalid source HEAD")
    try:
        completed = catalog_candidate.run_bounded_capture(
            ["git", "-C", str(root), "ls-tree", "-r", "-z", head], cwd=root
        )
    except (OSError, RuntimeError) as exc:
        raise InputContractError("cannot read source tree") from exc
    if completed.returncode or not completed.stdout:
        raise InputContractError("source tree is empty")
    return sha256_bytes(completed.stdout)


def _tool_version(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    deadline: Optional[float],
) -> str:
    remaining = 30.0 if deadline is None else deadline - time.monotonic()
    if remaining <= 0:
        raise InputContractError("total validation budget exceeded during toolchain probe")
    result = run_command(
        command=command,
        cwd=cwd,
        environment=environment,
        timeout_seconds=min(30.0, remaining),
    )
    if result.timed_out and deadline is not None and time.monotonic() >= deadline:
        raise InputContractError("total validation budget exceeded during toolchain probe")
    if result.status != "pass":
        raise InputContractError("toolchain probe did not produce a successful result")
    output = (result.stdout + "\n" + result.stderr).strip().splitlines()
    if not output:
        raise InputContractError("toolchain probe did not produce version evidence")
    return output[0][:160]


def detect_toolchain(
    root: Path, *, deadline: Optional[float] = None
) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="issues-242-243-toolchain-home-") as directory:
        gradle_home = Path(directory).resolve()
        os.chmod(gradle_home, 0o700)
        environment = sanitized_environment(os.environ)
        environment["GRADLE_USER_HOME"] = str(gradle_home)
        java = shutil.which("java") or "java"
        jdk = _tool_version(
            (java, "-version"),
            cwd=root,
            environment=environment,
            deadline=deadline,
        )
    wrapper = _canonical_existing_file(
        root / "gradle" / "wrapper" / "gradle-wrapper.properties",
        "Gradle wrapper properties",
    )
    match = re.search(
        r"(?m)^distributionUrl=.*?/gradle-(.+?)-(?:bin|all)\.zip(?:[?#].*)?$",
        wrapper.read_text(encoding="utf-8"),
    )
    if match is None or not match.group(1).strip():
        raise InputContractError("Gradle wrapper version is unavailable")
    return jdk, f"Gradle {match.group(1).strip()} (wrapper)"


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


def job_helper_path(
    *, repository: str, root: Path, central_root: Path, phase: str
) -> Path:
    """Return the phase helper bound by the receipt's ``helper_sha256`` field."""

    if phase in {"timefold-graphs-candidate", "consumers"}:
        return central_root / CANDIDATE_INIT_SCRIPT_RELATIVE
    if repository in CONSUMER_REPOSITORIES or phase == "publication-poms":
        return central_root / CANONICAL_HELPER_RELATIVE
    return root / GENERATED_HELPER_RELATIVE


def _job_digests(
    root: Path,
    central_root: Path,
    *,
    repository: str,
    phase: str,
    catalog_path: Optional[Path] = None,
    bom_sha256: Optional[str] = None,
) -> tuple[str, str, str]:
    phase_helper = job_helper_path(
        repository=repository,
        root=root,
        central_root=central_root,
        phase=phase,
    )
    if not phase_helper.is_file() or phase_helper.is_symlink():
        raise InputContractError(f"phase helper is missing: {phase_helper}")
    catalog = catalog_path or root / "gradle" / "libs.versions.toml"
    bom = central_root / "build.gradle.kts"
    return (
        _digest_required(phase_helper, "phase helper"),
        _digest_required(catalog, "repository catalog"),
        _validate_sha256(bom_sha256, "candidate BOM artifact manifest")
        if bom_sha256 is not None
        else _digest_required(bom, "central BOM build"),
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
    repository_origin: str = "",
    repository_branch: str = "",
    environment_overrides: Optional[Mapping[str, str]] = None,
    candidate_maven_repository: Optional[Path] = None,
    produced_maven_repository: Optional[Path] = None,
    candidate_catalog_path: Optional[Path] = None,
    candidate_bom_sha256: Optional[str] = None,
    deadline: Optional[float] = None,
) -> ValidationJob:
    helper, catalog, bom = _job_digests(
        root,
        central_root,
        repository=repository,
        phase=phase,
        catalog_path=candidate_catalog_path,
        bom_sha256=candidate_bom_sha256,
    )
    jdk, gradle = detect_toolchain(root, deadline=deadline)
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
        task_set=tuple(tasks),
        repository_head=repository_head,
        helper_sha256=helper,
        catalog_sha256=catalog,
        bom_sha256=bom,
        jdk_version=jdk,
        gradle_version=gradle,
        arguments=tuple(arguments),
        repository_origin=repository_origin,
        repository_branch=repository_branch,
        environment_overrides=tuple(sorted((environment_overrides or {}).items())),
        candidate_maven_repository=candidate_maven_repository,
        produced_maven_repository=produced_maven_repository,
        candidate_catalog_path=candidate_catalog_path,
    )


def validate_job_binding(
    job: ValidationJob, bindings: Mapping[str, Mapping[str, Any]]
) -> None:
    """Revalidate map identity, clean state, and every cache input digest."""

    binding = bindings.get(job.repository)
    if binding is None and job.repository == "publication-poms":
        binding = bindings.get("bluetape4k-dependencies")
    if not isinstance(binding, Mapping):
        raise InputContractError(f"missing repository binding for job: {job.repository}")
    root_value = binding.get("candidate_worktree")
    if not isinstance(root_value, str):
        raise InputContractError(f"repository worktree binding is invalid: {job.repository}")
    root = _canonical_directory(Path(root_value), f"repository worktree for {job.repository}")
    job_root = _canonical_directory(job.cwd, f"job cwd for {job.repository}")
    if root != job_root:
        raise InputContractError(f"repository worktree mismatch: {job.repository}")
    expected_head = binding.get("candidate_head")
    if expected_head != job.repository_head:
        raise InputContractError(f"repository HEAD mismatch: {job.repository}")
    expected_origin = binding.get("origin")
    if job.repository_origin and expected_origin != job.repository_origin:
        raise InputContractError(f"repository origin mismatch: {job.repository}")
    expected_branch = binding.get("candidate_branch")
    if job.repository_branch and expected_branch != job.repository_branch:
        raise InputContractError(f"repository branch mismatch: {job.repository}")
    if binding.get("clean", True) is not True or binding.get("exact_head", True) is not True:
        raise InputContractError(f"repository map is not clean exact-head: {job.repository}")
    if _git(root, "remote", "get-url", "origin") != expected_origin:
        raise InputContractError(f"repository origin changed: {job.repository}")
    if _git(root, "branch", "--show-current") != expected_branch:
        raise InputContractError(f"repository branch changed: {job.repository}")
    if _git(root, "rev-parse", "HEAD") != expected_head:
        raise InputContractError(f"repository HEAD changed: {job.repository}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise InputContractError(f"repository became dirty: {job.repository}")

    central_binding = bindings.get("bluetape4k-dependencies", binding)
    central_value = central_binding.get("candidate_worktree")
    if not isinstance(central_value, str):
        raise InputContractError("central repository binding is invalid")
    central_root = _canonical_directory(Path(central_value), "central repository worktree")
    helper_digest = _digest_required(
        job_helper_path(
            repository=job.repository,
            root=root,
            central_root=central_root,
            phase=job.phase,
        ),
        "job phase helper",
    )
    catalog_path = job.candidate_catalog_path or root / "gradle" / "libs.versions.toml"
    catalog_digest = _digest_required(catalog_path, "job catalog")
    if job.candidate_maven_repository is not None:
        bom_digest = str(
            candidate_artifact_manifest(job.candidate_maven_repository)["sha256"]
        )
    else:
        bom_digest = _digest_required(central_root / "build.gradle.kts", "job BOM")
    for actual, expected, label in (
        (helper_digest, job.helper_sha256, "helper"),
        (catalog_digest, job.catalog_sha256, "catalog"),
        (bom_digest, job.bom_sha256, "BOM"),
    ):
        if actual != expected:
            raise InputContractError(f"{label} digest changed: {job.repository}")


def _consumer_entry(receipt: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    consumers = receipt.get("consumers")
    if not isinstance(consumers, list):
        raise InputContractError("local receipt has no consumer entries")
    item = next((value for value in consumers if isinstance(value, Mapping) and value.get("name") == name), None)
    if not isinstance(item, Mapping):
        raise InputContractError(f"local receipt is missing consumer: {name}")
    return item


def _consumer_root_from_receipt(
    receipt: Mapping[str, Any], name: str, requested_root: Optional[Path]
) -> tuple[Path, str]:
    item = _consumer_entry(receipt, name)
    value = item.get("candidate_worktree")
    head = item.get("candidate_head")
    if not isinstance(value, str) or not isinstance(head, str):
        raise InputContractError(f"consumer receipt binding is incomplete: {name}")
    root = _canonical_directory(Path(value), f"consumer worktree for {name}")
    if requested_root is not None and root != _canonical_directory(
        requested_root, f"requested consumer worktree for {name}"
    ):
        raise InputContractError(f"consumer root does not match receipt: {name}")
    if _git(root, "rev-parse", "HEAD") != head:
        raise InputContractError(f"consumer HEAD mismatch: {name}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise InputContractError(f"consumer worktree is dirty: {name}")
    return root, head


def _baseline_root_from_binding(
    binding: Mapping[str, Any], requested_root: Optional[Path], name: str
) -> tuple[Path, str, str, str]:
    if requested_root is None:
        raise InputContractError(f"baseline phase requires an exact base worktree: {name}")
    root = _canonical_directory(requested_root, f"baseline worktree for {name}")
    candidate_worktree = binding.get("candidate_worktree")
    if isinstance(candidate_worktree, str) and root == Path(candidate_worktree):
        raise InputContractError(f"baseline worktree reuses candidate worktree: {name}")
    base_sha = binding.get("base_sha")
    origin = binding.get("origin")
    if not isinstance(base_sha, str) or not isinstance(origin, str):
        raise InputContractError(f"baseline binding is incomplete: {name}")
    if _git(root, "rev-parse", "HEAD") != base_sha:
        raise InputContractError(f"baseline HEAD mismatch: {name}")
    if _git(root, "remote", "get-url", "origin") != origin:
        raise InputContractError(f"baseline origin mismatch: {name}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise InputContractError(f"baseline worktree is dirty: {name}")
    return root, base_sha, origin, _git(root, "branch", "--show-current")


def _make_timefold_graph_jobs(
    *,
    repository: str,
    root: Path,
    repository_head: str,
    central_root: Path,
    repository_origin: str = "",
    repository_branch: str = "",
    phase: str = "timefold-graphs-baseline",
    candidate_maven_repository: Optional[Path] = None,
    candidate_catalog_path: Optional[Path] = None,
    candidate_bom_sha256: Optional[str] = None,
    environment_overrides: Optional[Mapping[str, str]] = None,
    arguments: Sequence[str] = (),
    deadline: Optional[float] = None,
) -> tuple[ValidationJob, ...]:
    jobs: list[ValidationJob] = []
    for coordinate in TIMEFOLD_GRAPH_COORDINATES[repository]:
        jobs.append(
            dataclasses.replace(
                _make_job(
                    repository=repository,
                    phase=phase,
                    root=root,
                    tasks=TIMEFOLD_GRAPH_TASKS[repository],
                    arguments=tuple(arguments)
                    + (
                        "--configuration",
                        "testRuntimeClasspath",
                        "--dependency",
                        coordinate,
                    ),
                    configuration="testRuntimeClasspath",
                    repository_head=repository_head,
                    central_root=central_root,
                    refresh_dependencies=should_refresh_graph_dependencies(phase),
                    repository_origin=repository_origin,
                    repository_branch=repository_branch,
                    environment_overrides=environment_overrides,
                    candidate_maven_repository=candidate_maven_repository,
                    candidate_catalog_path=candidate_catalog_path,
                    candidate_bom_sha256=candidate_bom_sha256,
                    deadline=deadline,
                ),
                coordinate=coordinate,
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
    exposed_baseline_root: Optional[Path] = None,
    workshop_baseline_root: Optional[Path] = None,
    clinic_baseline_root: Optional[Path] = None,
    candidate_maven_repository: Optional[Path] = None,
    repositories: Optional[Sequence[str]] = None,
    deadline: Optional[float] = None,
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
                repository_origin=str(entries[name]["origin"]),
                repository_branch=str(entries[name]["candidate_branch"]),
                deadline=deadline,
            )
            for name in names
        )

    if phase == "candidate-bom-publication":
        if selected:
            raise InputContractError(
                "candidate-bom-publication does not accept repository selection"
            )
        if candidate_maven_repository is None:
            raise InputContractError(
                "candidate-bom-publication requires the candidate Maven repository"
            )
        candidate_repository = _empty_candidate_repository(
            candidate_maven_repository
        )
        central = entries["bluetape4k-dependencies"]
        return (
            _make_job(
                repository="bluetape4k-dependencies",
                phase=phase,
                root=central_root,
                tasks=("publishBluetapeDependenciesPublicationToMavenLocal",),
                configuration="candidate-bom-publication",
                arguments=(
                    f"-Dmaven.repo.local={candidate_repository}",
                    f"-PbaseVersion={CANDIDATE_BOM_VERSION}",
                    "-PsnapshotVersion=",
                ),
                repository_head=str(central["candidate_head"]),
                central_root=central_root,
                max_workers=1,
                repository_origin=str(central["origin"]),
                repository_branch=str(central["candidate_branch"]),
                produced_maven_repository=candidate_repository,
                deadline=deadline,
            ),
        )

    consumer_roots: dict[str, tuple[Path, str]] = {}
    consumer_bindings: dict[str, Mapping[str, Any]] = {}
    if phase in {"timefold-graphs-baseline", "timefold-graphs-candidate", "consumers"}:
        consumer_bindings["timefold-workshop"] = _consumer_entry(receipt, "timefold-workshop")
        consumer_bindings["clinic-appointment"] = _consumer_entry(receipt, "clinic-appointment")
        consumer_roots["timefold-workshop"] = _consumer_root_from_receipt(
            receipt, "timefold-workshop", workshop_root
        )
        consumer_roots["clinic-appointment"] = _consumer_root_from_receipt(
            receipt, "clinic-appointment", clinic_root
        )
    candidate_repository: Optional[Path] = None
    candidate_manifest_sha256: Optional[str] = None
    candidate_catalog: Optional[Path] = None
    if phase in {"timefold-graphs-candidate", "consumers"}:
        if candidate_maven_repository is None:
            raise InputContractError(f"{phase} requires the candidate Maven repository")
        candidate_repository = _canonical_directory(
            candidate_maven_repository, "candidate Maven repository"
        )
        candidate_manifest_sha256 = str(
            candidate_artifact_manifest(candidate_repository)["sha256"]
        )
        candidate_catalog, _ = validated_candidate_catalog(central_root)
    if phase == "timefold-graphs-baseline":
        jobs: list[ValidationJob] = []
        exposed = entries["bluetape4k-exposed"]
        exposed_root, exposed_head, exposed_origin, exposed_branch = (
            _baseline_root_from_binding(
                exposed, exposed_baseline_root, "bluetape4k-exposed"
            )
        )
        jobs.extend(
            _make_timefold_graph_jobs(
                repository="bluetape4k-exposed",
                root=exposed_root,
                repository_head=exposed_head,
                central_root=central_root,
                repository_origin=exposed_origin,
                repository_branch=exposed_branch,
                deadline=deadline,
            )
        )
        requested_baselines = {
            "timefold-workshop": workshop_baseline_root,
            "clinic-appointment": clinic_baseline_root,
        }
        for name in ("timefold-workshop", "clinic-appointment"):
            root, head, origin, branch = _baseline_root_from_binding(
                consumer_bindings[name], requested_baselines[name], name
            )
            jobs.extend(
                _make_timefold_graph_jobs(
                    repository=name,
                    root=root,
                    repository_head=head,
                    central_root=central_root,
                    repository_origin=origin,
                    repository_branch=branch,
                    deadline=deadline,
                )
            )
        return tuple(jobs)
    if phase == "timefold-graphs-candidate":
        assert candidate_repository is not None
        assert candidate_manifest_sha256 is not None
        assert candidate_catalog is not None
        jobs = []
        exposed = entries["bluetape4k-exposed"]
        jobs.extend(
            _make_timefold_graph_jobs(
                repository="bluetape4k-exposed",
                root=Path(exposed["candidate_worktree"]),
                repository_head=str(exposed["candidate_head"]),
                central_root=central_root,
                repository_origin=str(exposed["origin"]),
                repository_branch=str(exposed["candidate_branch"]),
                phase=phase,
                candidate_maven_repository=candidate_repository,
                candidate_catalog_path=candidate_catalog,
                candidate_bom_sha256=candidate_manifest_sha256,
                environment_overrides={
                    "BLUETAPE4K_DEPENDENCIES_CATALOG_PATH": str(candidate_catalog),
                },
                arguments=candidate_arguments(
                    central_root=central_root,
                    candidate_maven_repository=candidate_repository,
                ),
                deadline=deadline,
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
                    repository_origin=str(consumer_bindings[name]["origin"]),
                    repository_branch=str(consumer_bindings[name]["candidate_branch"]),
                    phase=phase,
                    candidate_maven_repository=candidate_repository,
                    candidate_bom_sha256=candidate_manifest_sha256,
                    arguments=candidate_arguments(
                        central_root=central_root,
                        candidate_maven_repository=candidate_repository,
                    ),
                    deadline=deadline,
                )
            )
        return tuple(jobs)
    if phase == "consumers":
        assert candidate_repository is not None
        assert candidate_manifest_sha256 is not None
        assert candidate_catalog is not None
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
                repository_origin=str(exposed["origin"]),
                repository_branch=str(exposed["candidate_branch"]),
                environment_overrides={
                    "BLUETAPE4K_DEPENDENCIES_CATALOG_PATH": str(candidate_catalog),
                },
                arguments=candidate_arguments(
                    central_root=central_root,
                    candidate_maven_repository=candidate_repository,
                ),
                candidate_maven_repository=candidate_repository,
                candidate_catalog_path=candidate_catalog,
                candidate_bom_sha256=candidate_manifest_sha256,
                deadline=deadline,
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
                    repository_origin=str(consumer_bindings[name]["origin"]),
                    repository_branch=str(consumer_bindings[name]["candidate_branch"]),
                    arguments=candidate_arguments(
                        central_root=central_root,
                        candidate_maven_repository=candidate_repository,
                    ),
                    candidate_maven_repository=candidate_repository,
                    candidate_bom_sha256=candidate_manifest_sha256,
                    deadline=deadline,
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
                repository_origin=str(entries["bluetape4k-dependencies"]["origin"]),
                repository_branch=str(entries["bluetape4k-dependencies"]["candidate_branch"]),
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


def _job_environment(job: ValidationJob) -> dict[str, str]:
    environment = sanitized_environment(os.environ)
    for key, value in job.environment_overrides:
        if key not in CANDIDATE_ENVIRONMENT_KEYS:
            raise InputContractError(f"job environment key is not allowlisted: {key}")
        if not value:
            raise InputContractError(f"job environment value is empty: {key}")
        environment[key] = value
    return environment


def _load_job_bindings(
    repository_map_path: Path,
    receipt_path: Path,
    jobs: Sequence[ValidationJob] = (),
) -> dict[str, dict[str, Any]]:
    latest_map = load_strict_repository_map(repository_map_path)
    latest_receipt = load_local_receipt(receipt_path, repository_map_path)
    bindings = _entry_by_name(latest_map)
    consumers = latest_receipt.get("consumers")
    if not isinstance(consumers, list):
        raise InputContractError("local receipt has no consumer bindings")
    for item in consumers:
        if isinstance(item, Mapping) and isinstance(item.get("name"), str):
            bindings[str(item["name"])] = dict(item)
    for job in jobs:
        if job.phase != "timefold-graphs-baseline":
            continue
        bindings[job.repository] = {
            "candidate_worktree": str(job.cwd),
            "candidate_head": job.repository_head,
            "origin": job.repository_origin,
            "candidate_branch": job.repository_branch,
            "clean": True,
            "exact_head": True,
        }
    return bindings


def _bound_result(job: ValidationJob, status: str, reason: str) -> CommandResult:
    safe_reason = redact_output(reason)
    return CommandResult(
        status=status,
        returncode=None,
        stdout="",
        stderr="",
        elapsed_seconds=0.0,
        timed_out=False,
        process_group_terminated=False,
        termination_signal=None,
        output_sha256=sha256_bytes(safe_reason.encode("utf-8")),
        diagnostics=bounded_diagnostics(safe_reason),
        job_id=job.job_id,
        repository=job.repository,
        cancelled=status == "blocked",
    )


def execute_job(
    job: ValidationJob,
    *,
    cache_directory: Path,
    receipt_path: Path,
    binding_loader: Optional[Callable[[], Mapping[str, Mapping[str, Any]]]] = None,
    cancel_event: Optional[threading.Event] = None,
    deadline: Optional[float] = None,
) -> CommandResult:
    def revalidate() -> None:
        if binding_loader is not None:
            validate_job_binding(job, binding_loader())

    if deadline is not None and time.monotonic() >= deadline:
        return _bound_result(job, "blocked", "total validation budget exceeded")

    # Revalidate immediately before reading a cache and again before trusting a
    # hit or launching a child.  This closes the TOCTOU window around every job.
    revalidate()
    # A producer's stdout cache cannot reconstruct its artifact tree. Always
    # execute producers against an empty receipt-bound repository instead of
    # treating scalar command output as publication evidence.
    hit = (
        None
        if job.produced_maven_repository is not None
        else read_cache_entry(cache_directory, job.cache_key)
    )
    if hit is not None:
        revalidate()
        manifest_bytes = b""
        if job.produced_maven_repository is not None:
            manifest_bytes = canonical_json_bytes(
                candidate_artifact_manifest(job.produced_maven_repository)
            )
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
            job_id=job.job_id,
            repository=job.repository,
            cache_key=job.cache_key,
            cache_output_path=str(hit["output_path"]),
            candidate_artifact_manifest_bytes=manifest_bytes,
        )
    revalidate()
    timeout = (
        PUBLICATION_POMS_TIMEOUT_SECONDS
        if job.phase == "publication-poms"
        else CHILD_TIMEOUT_SECONDS
    )
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _bound_result(job, "blocked", "total validation budget exceeded")
        timeout = min(timeout, remaining)
    with tempfile.TemporaryDirectory(prefix="issues-242-243-gradle-home-") as directory:
        gradle_home = Path(directory).resolve()
        os.chmod(gradle_home, 0o700)
        environment = _job_environment(job)
        environment["GRADLE_USER_HOME"] = str(gradle_home)
        result = run_command(
            command=job.command,
            cwd=job.cwd,
            environment=environment,
            timeout_seconds=timeout,
            failure_artifact=_failure_artifact_for(receipt_path, job),
            cancel_event=cancel_event,
        )
    result = dataclasses.replace(result, job_id=job.job_id, repository=job.repository)
    if deadline is not None and result.timed_out and time.monotonic() >= deadline:
        result = dataclasses.replace(
            result,
            diagnostics="total validation budget exceeded",
        )
    if result.status == "pass":
        # Bind successful output to the same clean exact source inputs after the
        # child exits. A concurrent tracked-file edit during publication must
        # never be attested as output of the preflighted HEAD.
        revalidate()
        manifest_bytes = b""
        if job.produced_maven_repository is not None:
            manifest_bytes = canonical_json_bytes(
                candidate_artifact_manifest(job.produced_maven_repository)
            )
        output = (result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr).encode("utf-8")
        cache_entry = write_cache_entry(
            cache_directory,
            job.cache_key,
            output,
            metadata={
                "repository": job.repository,
                "phase": job.phase,
                "configuration": job.configuration,
            },
        )
        result = dataclasses.replace(
            result,
            output_sha256=str(cache_entry["output_sha256"]),
            cache_key=job.cache_key,
            cache_output_path=str(cache_entry["output_path"]),
            candidate_artifact_manifest_bytes=manifest_bytes,
        )
    return result


def _worker(
    job: ValidationJob,
    *,
    cache_directory: Path,
    receipt_path: Path,
    binding_loader: Optional[Callable[[], Mapping[str, Mapping[str, Any]]]] = None,
    cancel_event: Optional[threading.Event] = None,
    deadline: Optional[float] = None,
) -> CommandResult:
    return execute_job(
        job,
        cache_directory=cache_directory,
        receipt_path=receipt_path,
        binding_loader=binding_loader,
        cancel_event=cancel_event,
        deadline=deadline,
    )


def _phase_digest(phase: str, results: Sequence[CommandResult], failure: Optional[str]) -> str:
    payload = {
        "schema_version": 1,
        "phase": phase,
        "results": [
            {
                "status": result.status,
                "output_sha256": result.output_sha256,
                "cached": result.cached,
                "job_id": result.job_id,
                "repository": result.repository,
                "cancelled": result.cancelled,
            }
            for result in results
        ],
        "failure": failure,
    }
    return sha256_bytes(canonical_json_bytes(payload))


def _bound_command_record(
    job: ValidationJob, command_result: CommandResult
) -> dict[str, Any]:
    command = " ".join(redact_command(job.command))
    coordinate: str | None = job.coordinate or None
    selected_version: str | None = None
    selection_reason: str | None = None
    if job.phase.startswith("timefold-graphs-") and command_result.status == "pass":
        output = command_result.stdout + (
            "\n" if command_result.stdout and command_result.stderr else ""
        ) + command_result.stderr
        observation = parse_dependency_insight(output, job.coordinate)
        selected_version = observation.selected_version
        selection_reason = observation.selection_reason
    override_disposition = (
        "candidate"
        if job.candidate_maven_repository is not None
        or job.produced_maven_repository is not None
        or job.candidate_catalog_path is not None
        else "baseline"
    )
    task_set = sorted(set(job.task_set))
    immutable_input = {
        "schema_version": 1,
        "repository": job.repository,
        "phase": job.phase,
        "command": command,
        "repository_head": job.repository_head,
        "helper_sha256": job.helper_sha256,
        "catalog_sha256": job.catalog_sha256,
        "bom_sha256": job.bom_sha256,
        "task_set": task_set,
        "configuration": job.configuration,
        "jdk": job.jdk_version,
        "gradle": job.gradle_version,
        "coordinate": coordinate,
        "override_disposition": override_disposition,
        "arguments": list(job.arguments),
        "gradle_home_policy": GRADLE_HOME_POLICY,
    }
    return {
        "repository": job.repository,
        "phase": job.phase,
        "command": command,
        "jdk": job.jdk_version,
        "gradle": job.gradle_version,
        "configuration": job.configuration,
        "elapsed_seconds": command_result.elapsed_seconds,
        "cache": "shared-read" if command_result.cached else "isolated",
        "job_id": job.job_id,
        "cache_key": command_result.cache_key or None,
        "cache_output_path": command_result.cache_output_path or None,
        "result": command_result.status,
        "output_sha256": command_result.output_sha256,
        "coordinate": coordinate,
        "selected_version": selected_version,
        "selection_reason": selection_reason,
        "repository_head": job.repository_head,
        "helper_sha256": job.helper_sha256,
        "catalog_sha256": job.catalog_sha256,
        "bom_sha256": job.bom_sha256,
        "task_set": task_set,
        "override_disposition": override_disposition,
        "arguments": list(job.arguments),
        "gradle_home_policy": GRADLE_HOME_POLICY,
        "input_sha256": sha256_bytes(canonical_json_bytes(immutable_input)),
    }


def _update_consumer_graphs(
    document: dict[str, Any], result: PhaseResult, jobs: Sequence[ValidationJob]
) -> None:
    """Bind parsed graph values to the two external consumer receipt entries."""

    if result.phase not in {
        "timefold-graphs-baseline",
        "timefold-graphs-candidate",
    }:
        return
    consumers = document.get("consumers")
    if not isinstance(consumers, list):
        raise InputContractError("local receipt consumers must be an array")
    by_name = {
        item.get("name"): item
        for item in consumers
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for repository in CONSUMER_REPOSITORIES:
        expected = TIMEFOLD_GRAPH_COORDINATES[repository]
        pairs = [
            (job, command_result)
            for job, command_result in zip(jobs, result.jobs)
            if job.repository == repository
        ]
        if not pairs or any(command_result.status != "pass" for _, command_result in pairs):
            continue
        if tuple(job.coordinate for job, _ in pairs) != expected:
            raise InputContractError(
                f"consumer graph coordinates are incomplete: {repository}"
            )
        parsed = [
            (
                job,
                command_result,
                parse_dependency_insight(
                    command_result.stdout
                    + ("\n" if command_result.stdout and command_result.stderr else "")
                    + command_result.stderr,
                    job.coordinate,
                ),
            )
            for job, command_result in pairs
        ]
        consumer = by_name.get(repository)
        if not isinstance(consumer, dict):
            raise InputContractError(f"local receipt is missing consumer: {repository}")
        if result.phase == "timefold-graphs-baseline":
            consumer["graphs"] = [
                {
                    "coordinate": observation.coordinate,
                    "configuration": job.configuration,
                    "before_version": observation.selected_version,
                    "after_version": "pending-candidate",
                    "selection_reason": (
                        f"before: {observation.selection_reason}; after: pending-candidate"
                    ),
                    "output_sha256": command_result.output_sha256,
                }
                for job, command_result, observation in parsed
            ]
            continue
        existing = {
            item.get("coordinate"): item
            for item in consumer.get("graphs", [])
            if isinstance(item, dict)
        }
        updated: list[dict[str, Any]] = []
        for job, command_result, observation in parsed:
            graph = existing.get(job.coordinate)
            if not isinstance(graph, dict) or graph.get("before_version") in {
                None,
                "pending-baseline",
            }:
                if result.status != "pass":
                    updated = []
                    break
                raise InputContractError(
                    f"candidate graph lacks baseline evidence: {repository} {job.coordinate}"
                )
            before_reason = str(graph.get("selection_reason", "")).split(
                "; after:", 1
            )[0]
            updated.append(
                {
                    "coordinate": observation.coordinate,
                    "configuration": job.configuration,
                    "before_version": graph["before_version"],
                    "after_version": observation.selected_version,
                    "selection_reason": (
                        f"{before_reason}; after: {observation.selection_reason}"
                    ),
                    "output_sha256": command_result.output_sha256,
                }
            )
        if updated:
            consumer["graphs"] = updated


def _write_receipt_update(
    path: Path,
    result: PhaseResult,
    jobs: Sequence[ValidationJob],
    *,
    expected_receipt_sha256: Optional[str] = None,
    expected_state: Optional[str] = None,
    phase_elapsed_seconds: float = 0.0,
    reserved_seconds: Optional[float] = None,
) -> None:
    """CAS-update a receipt under its strict validator's lock."""

    if len(jobs) != len(result.jobs):
        raise InputContractError("receipt command/result mapping is incomplete")
    path = _canonical_existing_file(path, "local receipt")
    if expected_receipt_sha256 is not None:
        _validate_sha256(expected_receipt_sha256, "expected receipt")
    receipt_module = _load_receipt_module()
    lock = getattr(receipt_module, "_receipt_lock", None)
    validate = getattr(receipt_module, "validate_receipt", None)
    write_atomic = getattr(receipt_module, "write_atomic", None)
    if not callable(lock) or not callable(validate) or not callable(write_atomic):
        raise InputContractError("strict receipt module lacks lock/validate/write helpers")
    with lock(path):
        # Recheck the target after acquiring the module lock so a replacement
        # between the preflight and lock acquisition cannot be followed.
        path = _canonical_existing_file(path, "local receipt")
        try:
            original_bytes = path.read_bytes()
            current_digest = sha256_bytes(original_bytes)
            raw_document = json.loads(original_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InputContractError("cannot read local receipt for update") from exc
        if expected_receipt_sha256 is not None and current_digest != expected_receipt_sha256:
            raise InputContractError("stale receipt digest for update")
        if not isinstance(raw_document, Mapping):
            raise InputContractError("local receipt must be an object")
        current_state = raw_document.get("current_state")
        if expected_state is not None and current_state != expected_state:
            raise InputContractError("stale receipt state for update")
        try:
            validated = validate(path)
        except Exception as exc:
            raise InputContractError(f"latest receipt validation failed: {exc}") from exc
        if not isinstance(validated, Mapping):
            raise InputContractError("strict receipt validator returned an invalid document")
        document = json.loads(json.dumps(dict(validated)))
        if phase_elapsed_seconds < 0:
            raise InputContractError("phase elapsed time is invalid")
        budget = document["validation_budget"]
        if reserved_seconds is None:
            remaining = validation_budget_remaining(document)
            consumed = min(remaining, phase_elapsed_seconds)
            budget["elapsed_seconds"] = float(budget["elapsed_seconds"]) + consumed
            budget["remaining_seconds"] = remaining - consumed
        else:
            if reserved_seconds <= 0 or reserved_seconds > float(budget["total_seconds"]):
                raise InputContractError("validation budget reservation is invalid")
            if float(budget["remaining_seconds"]) != 0.0:
                raise InputContractError("validation budget reservation was not consumed")
            consumed = min(reserved_seconds, phase_elapsed_seconds)
            budget["elapsed_seconds"] = (
                float(budget["total_seconds"]) - reserved_seconds + consumed
            )
            budget["remaining_seconds"] = reserved_seconds - consumed
        effective_result = result
        budget_exceeded = (
            reserved_seconds is not None
            and phase_elapsed_seconds > reserved_seconds + 0.001
        )
        if budget_exceeded:
            failure = "total validation budget exceeded during phase execution"
            effective_result = PhaseResult(
                phase=result.phase,
                status="blocked",
                output_sha256=_phase_digest(result.phase, result.jobs, failure),
                jobs=result.jobs,
                failure=failure,
            )
        phases = document.setdefault("phases", [])
        if not isinstance(phases, list):
            raise InputContractError("local receipt phases must be an array")
        previous_phase = next(
            (
                item
                for item in phases
                if isinstance(item, Mapping) and item.get("name") == effective_result.phase
            ),
            None,
        )
        previous_elapsed = (
            float(previous_phase.get("elapsed_seconds", 0.0))
            if previous_phase is not None
            else 0.0
        )
        phases[:] = [
            item
            for item in phases
            if not isinstance(item, Mapping) or item.get("name") != effective_result.phase
        ]
        phases.append(
            {
                "name": effective_result.phase,
                "result": effective_result.status,
                "output_sha256": effective_result.output_sha256,
                "elapsed_seconds": previous_elapsed + phase_elapsed_seconds,
                "reserved_seconds": previous_elapsed + (reserved_seconds or 0.0),
                "job_ids": [job.job_id for job in jobs],
            }
        )
        producer_pairs = [
            (job, command_result)
            for job, command_result in zip(jobs, result.jobs)
            if job.produced_maven_repository is not None
        ]
        if len(producer_pairs) > 1:
            raise InputContractError("candidate BOM phase has multiple producers")
        candidate_artifact_digests = {
            job.bom_sha256
            for job in jobs
            if job.candidate_maven_repository is not None
        }
        if len(candidate_artifact_digests) > 1:
            raise InputContractError("candidate jobs do not share one artifact manifest")
        if producer_pairs and producer_pairs[0][1].status == "pass":
            producer_job, producer_result = producer_pairs[0]
            assert producer_job.produced_maven_repository is not None
            try:
                manifest = json.loads(
                    producer_result.candidate_artifact_manifest_bytes.decode("utf-8")
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise InputContractError(
                    "candidate BOM producer manifest snapshot is invalid"
                ) from exc
            if not isinstance(manifest, dict) or (
                manifest.get("repository_path")
                != str(producer_job.produced_maven_repository)
            ):
                raise InputContractError(
                    "candidate BOM producer manifest snapshot is invalid"
                )
            phases[:] = [
                item
                for item in phases
                if not isinstance(item, Mapping)
                or item.get("name") != "candidate-bom-artifacts"
            ]
            phases.append(
                {
                    "name": "candidate-bom-artifacts",
                    "result": (
                        "pass"
                        if effective_result.status == "pass"
                        else effective_result.status
                    ),
                    "output_sha256": manifest["sha256"],
                    "elapsed_seconds": 0.0,
                    "reserved_seconds": 0.0,
                    "job_ids": [],
                }
            )
            manifest["central_head"] = document["central"]["candidate_head"]
            manifest["catalog_sha256"] = producer_job.catalog_sha256
            manifest["source_tree_sha256"] = git_source_tree_sha256(
                producer_job.cwd, producer_job.repository_head
            )
            producer_record = _bound_command_record(producer_job, producer_result)
            manifest["producer_job_id"] = producer_job.job_id
            manifest["producer_input_sha256"] = producer_record["input_sha256"]
            manifest["producer_output_sha256"] = producer_result.output_sha256
            document["candidate_artifact_manifest"] = manifest
        elif candidate_artifact_digests:
            manifest = document.get("candidate_artifact_manifest")
            if not isinstance(manifest, Mapping):
                raise InputContractError("candidate artifact producer evidence is missing")
            candidate_repository_paths = {
                str(job.candidate_maven_repository)
                for job in jobs
                if job.candidate_maven_repository is not None
            }
            if (
                len(candidate_repository_paths) != 1
                or manifest.get("repository_path") not in candidate_repository_paths
                or manifest.get("sha256") not in candidate_artifact_digests
            ):
                raise InputContractError("candidate jobs do not match producer evidence")
        _update_consumer_graphs(document, effective_result, jobs)
        commands = document.setdefault("commands", [])
        if not isinstance(commands, list):
            raise InputContractError("local receipt commands must be an array")
        commands[:] = [
            item
            for item in commands
            if not isinstance(item, Mapping) or item.get("phase") != effective_result.phase
        ]
        for job, command_result in zip(jobs, result.jobs):
            commands.append(_bound_command_record(job, command_result))
        cache_roots = {
            str(Path(command_result.cache_output_path).parent)
            for command_result in result.jobs
            if command_result.cache_output_path
        }
        if len(cache_roots) > 1:
            raise InputContractError("phase command outputs use multiple cache roots")
        if cache_roots:
            cache_root = next(iter(cache_roots))
            existing_cache_root = document.get("evidence_cache_root")
            if existing_cache_root not in {None, cache_root}:
                raise InputContractError("receipt evidence cache root changed")
            document["evidence_cache_root"] = cache_root
        failures = document.setdefault("failure_record", [])
        if not isinstance(failures, list):
            raise InputContractError("local receipt failure_record must be an array")
        for job, command_result in zip(jobs, result.jobs):
            if command_result.status != "pass":
                failures.append(
                    {
                        "repository": job.repository,
                        "phase": result.phase,
                        "reason": bounded_diagnostics(
                            command_result.diagnostics or "bounded validation phase failed", 1
                        ),
                        "output_sha256": command_result.output_sha256,
                    }
                )
        if budget_exceeded:
            failures.append(
                {
                    "repository": "validation-budget",
                    "phase": effective_result.phase,
                    "reason": effective_result.failure,
                    "output_sha256": effective_result.output_sha256,
                }
            )
        if effective_result.status != "pass":
            blocked_names = {
                job.repository
                for job, command_result in zip(jobs, result.jobs)
                if command_result.status != "pass"
            }
            if budget_exceeded or "publication-poms" in blocked_names:
                blocked_names.add("bluetape4k-dependencies")
            for section in ("repositories", "consumers"):
                values = document.get(section, [])
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict) and item.get("name") in blocked_names:
                            item["state"] = "blocked"
            if "bluetape4k-dependencies" in blocked_names:
                central = document.get("central")
                if isinstance(central, dict):
                    central["state"] = "blocked"
            document["current_state"] = "blocked"
        _reject_secret_content(document)
        payload = canonical_json_bytes(document)
        try:
            write_atomic(path, payload)
            readback = validate(path)
        except Exception as exc:
            try:
                write_atomic(path, original_bytes)
            except Exception as restore_exc:  # noqa: BLE001 - preserve primary failure
                raise InputContractError(
                    f"receipt update validation failed and restore failed: {restore_exc}"
                ) from exc
            raise InputContractError(f"receipt update read-back validation failed: {exc}") from exc
        if not isinstance(readback, Mapping):
            raise InputContractError("strict receipt read-back is invalid")


def _reserve_validation_budget(
    path: Path,
    *,
    expected_receipt_sha256: str,
    expected_state: str,
) -> tuple[float, str]:
    """Reserve all remaining budget before execution so crashes fail closed."""

    path = _canonical_existing_file(path, "local receipt")
    _validate_sha256(expected_receipt_sha256, "expected receipt")
    receipt_module = _load_receipt_module()
    lock = getattr(receipt_module, "_receipt_lock", None)
    validate = getattr(receipt_module, "validate_receipt", None)
    write_atomic = getattr(receipt_module, "write_atomic", None)
    if not callable(lock) or not callable(validate) or not callable(write_atomic):
        raise InputContractError("strict receipt module lacks lock/validate/write helpers")
    with lock(path):
        path = _canonical_existing_file(path, "local receipt")
        original_bytes = path.read_bytes()
        if sha256_bytes(original_bytes) != expected_receipt_sha256:
            raise InputContractError("stale receipt digest for budget reservation")
        try:
            document = validate(path)
        except Exception as exc:
            raise InputContractError(f"latest receipt validation failed: {exc}") from exc
        if not isinstance(document, Mapping) or document.get("current_state") != expected_state:
            raise InputContractError("stale receipt state for budget reservation")
        updated = json.loads(json.dumps(dict(document)))
        reserved = validation_budget_remaining(updated)
        if reserved <= 0:
            raise InputContractError("total validation budget exceeded")
        budget = updated["validation_budget"]
        budget["elapsed_seconds"] = float(budget["total_seconds"])
        budget["remaining_seconds"] = 0.0
        try:
            write_atomic(path, canonical_json_bytes(updated))
            readback = validate(path)
        except Exception as exc:
            try:
                write_atomic(path, original_bytes)
            except Exception as restore_exc:  # noqa: BLE001 - preserve primary failure
                raise InputContractError(
                    "budget reservation validation failed and restore failed: "
                    f"{restore_exc}"
                ) from exc
            raise InputContractError(
                f"budget reservation read-back validation failed: {exc}"
            ) from exc
        if not isinstance(readback, Mapping):
            raise InputContractError("strict receipt read-back is invalid")
        return reserved, sha256_file(path)


def run_phase(
    phase: str,
    *,
    repository_map_path: Path,
    receipt_path: Path,
    workshop_root: Optional[Path] = None,
    clinic_root: Optional[Path] = None,
    exposed_baseline_root: Optional[Path] = None,
    workshop_baseline_root: Optional[Path] = None,
    clinic_baseline_root: Optional[Path] = None,
    candidate_maven_repository: Optional[Path] = None,
    cache_directory: Optional[Path] = None,
    repositories: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    execution_boundary: Optional[str] = None,
    reviewed_heads: Sequence[str] = (),
) -> PhaseResult:
    # Reject lexical parent/component symlinks before any canonical resolution.
    repository_map_path = _canonical_input_path(repository_map_path, "repository map")
    receipt_path = _canonical_input_path(receipt_path, "local receipt")
    repository_map = load_strict_repository_map(repository_map_path)
    receipt = load_local_receipt(receipt_path, repository_map_path)
    expected_receipt_sha256 = sha256_file(receipt_path)
    expected_state = receipt.get("current_state")
    if not isinstance(expected_state, str) or not expected_state:
        raise InputContractError("local receipt current_state is invalid")
    recorded_phases = [
        str(item["name"])
        for item in receipt.get("phases", [])
        if isinstance(item, Mapping)
        and item.get("name") not in {"discover", "candidate-bom-artifacts"}
    ]
    if phase in recorded_phases:
        if phase == "candidate-bom-publication":
            raise InputContractError(
                "cannot rerun candidate BOM producer without a new receipt"
            )
        if recorded_phases[-1] != phase:
            raise InputContractError(
                f"cannot rerun non-tail phase without a new receipt: {phase}"
            )
    expected_candidate_repository = _absolute_without_following(
        receipt_path.parent / "candidate-m2"
    )
    if candidate_maven_repository is not None:
        requested_candidate_repository = _absolute_without_following(
            candidate_maven_repository
        )
        if requested_candidate_repository != expected_candidate_repository:
            raise InputContractError(
                "candidate Maven repository must use the receipt-bound path"
            )
        candidate_maven_repository = requested_candidate_repository
        if phase == "candidate-bom-publication":
            _empty_candidate_repository(candidate_maven_repository)
    expected_cache_directory = _absolute_without_following(receipt_path.parent / "cache")
    if cache_directory is not None and _absolute_without_following(
        cache_directory
    ) != expected_cache_directory:
        raise InputContractError("evidence cache must use the receipt-bound path")
    cache_directory = expected_cache_directory
    validate_execution_boundary(
        execution_boundary,
        reviewed_heads,
        required_phase_heads(phase, repository_map, receipt, repositories),
        os.environ,
    )
    reserved_budget: Optional[float] = None
    phase_started: Optional[float] = None
    deadline: Optional[float] = None
    if not dry_run:
        reserved_budget, expected_receipt_sha256 = _reserve_validation_budget(
            receipt_path,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_state=expected_state,
        )
        phase_started = time.monotonic()
        deadline = phase_started + reserved_budget
    jobs = build_phase_jobs(
        phase,
        repository_map,
        receipt,
        workshop_root=workshop_root,
        clinic_root=clinic_root,
        exposed_baseline_root=exposed_baseline_root,
        workshop_baseline_root=workshop_baseline_root,
        clinic_baseline_root=clinic_baseline_root,
        candidate_maven_repository=candidate_maven_repository,
        repositories=repositories,
        deadline=deadline,
    )
    if dry_run:
        digest = _phase_digest(phase, (), None)
        return PhaseResult(phase, "pass", digest, ())
    assert reserved_budget is not None
    assert phase_started is not None
    assert deadline is not None
    max_workers = 1 if phase == "publication-poms" else MAX_WORKERS
    jobs_by_id = {
        index: dataclasses.replace(job, job_id=f"{phase}:{index}:{job.repository}")
        for index, job in enumerate(jobs)
    }
    cancel_event = threading.Event()
    binding_loader = lambda: _load_job_bindings(
        repository_map_path, receipt_path, tuple(jobs_by_id.values())
    )
    result_by_id: dict[int, CommandResult] = {}
    failure: Optional[str] = None
    outcome = run_bounded_jobs(
        tuple(jobs_by_id),
        lambda index: _worker(
            jobs_by_id[index],
            cache_directory=cache_directory,
            receipt_path=receipt_path,
            binding_loader=binding_loader,
            cancel_event=cancel_event,
            deadline=deadline,
        ),
        max_workers=max_workers,
        failure_predicate=lambda result: getattr(result, "status", "fail") != "pass",
        collect_failures=True,
        cancel_event=cancel_event,
    )
    for index, result in outcome.results.items():
        result_by_id[index] = result
    for index, detail in outcome.errors.items():
        result_by_id[index] = _bound_result(jobs_by_id[index], "fail", detail)
    for index in outcome.cancelled:
        result_by_id.setdefault(
            index,
            _bound_result(jobs_by_id[index], "blocked", "cancelled before submission"),
        )
    for index, job in jobs_by_id.items():
        result_by_id.setdefault(
            index,
            _bound_result(job, "blocked", "job result was not observed"),
        )
    results = [
        validate_graph_result(jobs_by_id[index], result_by_id[index])
        for index in sorted(jobs_by_id)
    ]
    if outcome.first_failure is not None:
        first_result = result_by_id.get(outcome.first_failure)
        failure = f"first failed job: {jobs_by_id[outcome.first_failure].job_id}"
        if first_result is not None and first_result.diagnostics:
            failure += f": {first_result.diagnostics}"
    elif outcome.errors:
        failure = "runner job error: " + "; ".join(outcome.errors.values())
    status = (
        "fail"
        if any(result.status == "fail" for result in results)
        else "blocked"
        if any(result.status == "blocked" for result in results)
        else "pass"
    )
    output_digest = _phase_digest(phase, results, failure)
    phase_result = PhaseResult(phase, status, output_digest, tuple(results), failure)
    _write_receipt_update(
        receipt_path,
        phase_result,
        tuple(jobs_by_id[index] for index in sorted(jobs_by_id)),
        expected_receipt_sha256=expected_receipt_sha256,
        expected_state=expected_state,
        phase_elapsed_seconds=time.monotonic() - phase_started,
        reserved_seconds=reserved_budget,
    )
    return phase_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--repository-map", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--workshop-root", type=Path)
    parser.add_argument("--clinic-root", type=Path)
    parser.add_argument("--exposed-baseline-root", type=Path)
    parser.add_argument("--workshop-baseline-root", type=Path)
    parser.add_argument("--clinic-baseline-root", type=Path)
    parser.add_argument("--candidate-maven-repository", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--repo", action="append", dest="repositories")
    parser.add_argument(
        "--execution-boundary", choices=EXECUTION_BOUNDARIES, required=True
    )
    parser.add_argument("--reviewed-head", action="append", default=[])
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
            exposed_baseline_root=args.exposed_baseline_root,
            workshop_baseline_root=args.workshop_baseline_root,
            clinic_baseline_root=args.clinic_baseline_root,
            candidate_maven_repository=args.candidate_maven_repository,
            cache_directory=args.cache_dir,
            repositories=args.repositories,
            dry_run=args.dry_run,
            execution_boundary=args.execution_boundary,
            reviewed_heads=args.reviewed_head,
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
