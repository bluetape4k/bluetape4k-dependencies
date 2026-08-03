#!/usr/bin/env python3
"""Run credential-free, manifest-bound catalog validation stages."""

from __future__ import annotations

import argparse
import dataclasses
import enum
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
import time
from collections.abc import Mapping, Sequence
from pathlib import Path


class Stage(enum.Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"
    G6 = "G6"
    G7 = "G7"
    G8 = "G8"


TRAIN_BUDGET_SECONDS = 330 * 60
STARTUP_CLEANUP_RESERVE_SECONDS = 30 * 60
STAGE_BUDGET_SECONDS = {
    Stage.G1: 6 * 60,
    Stage.G2: 6 * 60,
    Stage.G3: 6 * 60,
    Stage.G4: 6 * 60,
    Stage.G5: 6 * 60,
    Stage.G6: 120 * 60,
    Stage.G7: 60 * 60,
    Stage.G8: 90 * 60,
}
GRADLE_FLAGS = (
    "--offline",
    "--no-daemon",
    "--no-configuration-cache",
    "--no-build-cache",
    "--console=plain",
)
FORBIDDEN_TASK = re.compile(r"(?:publish|sign|upload)", re.IGNORECASE)
FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
CACHE_KINDS = frozenset(
    {"gradle-cache-file", "gradle-distribution-file", "maven-local-file"}
)


@dataclasses.dataclass(frozen=True)
class SchedulerContract:
    jobs: int
    workers: int
    job_seconds: int
    waves: int
    reserve_seconds: int

    @property
    def total_seconds(self) -> int:
        return self.job_seconds * self.waves + self.reserve_seconds


@dataclasses.dataclass(frozen=True)
class CacheSource:
    kind: str
    path: Path
    sha256: str


HEAVY_SCHEDULER_CONTRACTS = {
    Stage.G6: SchedulerContract(8, 2, 25 * 60, 4, 20 * 60),
    Stage.G7: SchedulerContract(10, 2, 10 * 60, 5, 10 * 60),
    Stage.G8: SchedulerContract(10, 2, 15 * 60, 5, 15 * 60),
}


def scheduler_contract(stage: Stage) -> SchedulerContract:
    try:
        contract = HEAVY_SCHEDULER_CONTRACTS[stage]
    except KeyError as exc:
        raise RuntimeError(f"{stage.value} has no heavy scheduler contract") from exc
    if contract.total_seconds != STAGE_BUDGET_SECONDS[stage]:
        raise RuntimeError(f"{stage.value} scheduler does not fill its stage budget")
    return contract


def require_stage_budget(stage: Stage, remaining_seconds: float) -> None:
    required = STAGE_BUDGET_SECONDS[stage]
    if remaining_seconds < required:
        raise RuntimeError(
            f"{stage.value} full stage budget is unavailable: "
            f"required={required}, remaining={remaining_seconds}"
        )


def _regular_cache_file(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"{label} must be a readable regular file: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"{label} must be a regular file and not a symlink: {path}")
    if metadata.st_uid != os.getuid():
        raise RuntimeError(f"{label} must be owned by the current user: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise RuntimeError(f"{label} must not be group or world writable: {path}")


def load_cache_manifest(path: Path) -> tuple[CacheSource, ...]:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise RuntimeError(
            "cache manifest path must be absolute, canonical, and non-symlinked"
        )
    _regular_cache_file(path, "cache manifest")
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid cache manifest JSON") from exc
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "sources"}
        or document["schema_version"] != 1
        or not isinstance(document["sources"], list)
        or not document["sources"]
    ):
        raise RuntimeError("invalid cache manifest v1 envelope")

    sources: list[CacheSource] = []
    seen: set[Path] = set()
    for index, value in enumerate(document["sources"]):
        if not isinstance(value, dict) or set(value) != {"kind", "path", "sha256"}:
            raise RuntimeError(f"invalid cache source fields at index {index}")
        kind = value["kind"]
        if kind not in CACHE_KINDS:
            raise RuntimeError(f"cache source kind is not allowlisted at index {index}")
        source_path = Path(value["path"])
        if (
            not source_path.is_absolute()
            or source_path.resolve() != source_path
            or source_path.is_symlink()
        ):
            raise RuntimeError(
                f"cache source path must be absolute, canonical, and non-symlinked: {source_path}"
            )
        _regular_cache_file(source_path, f"cache source {index}")
        if source_path in seen:
            raise RuntimeError(f"duplicate cache source path: {source_path}")
        digest = value["sha256"]
        if not isinstance(digest, str) or FULL_SHA256.fullmatch(digest) is None:
            raise RuntimeError(f"invalid cache source SHA-256 at index {index}")
        actual = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual != digest:
            raise RuntimeError(f"cache source SHA-256 mismatch: {source_path}")
        seen.add(source_path)
        sources.append(CacheSource(kind, source_path, digest))
    return tuple(sources)


def _sandbox_filter(kind: str, paths: Sequence[Path]) -> str:
    clauses = " ".join(f'({kind} {json.dumps(str(path))})' for path in paths)
    return clauses


def sandbox_profile(
    *,
    workspace: Path,
    java_home: Path,
    readable_files: Sequence[Path],
    writable_roots: Sequence[Path],
    executable_files: Sequence[Path],
) -> str:
    read_filters = _sandbox_filter("literal", readable_files)
    write_filters = _sandbox_filter("subpath", writable_roots)
    exec_filters = _sandbox_filter("literal", executable_files)
    return "\n".join(
        (
            "(version 1)",
            "(deny default)",
            "(deny network*)",
            "(allow process-fork)",
            "(allow signal (target self))",
            "(allow file-read-metadata)",
            "(allow file-read*",
            f'  (subpath {json.dumps(str(workspace))})',
            f'  (subpath {json.dumps(str(java_home))})',
            f"  {read_filters})",
            f"(allow file-write* {write_filters})",
            f"(allow process-exec {exec_filters})",
            "",
        )
    )


def network_denial_profile() -> str:
    """Return the minimal executable fixture used to prove kernel network denial."""
    return "(version 1) (allow default) (deny network*)"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_secure_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise RuntimeError(f"{label} path must be absolute, canonical, and non-symlinked")
    _regular_cache_file(path, label)
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label} JSON") from exc
    if not isinstance(document, dict):
        raise TypeError(f"invalid {label} document")
    return document


def _verify_file_observation(value: object, label: str) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise RuntimeError(f"invalid {label} observation")
    path_value, digest = value["path"], value["sha256"]
    if not isinstance(path_value, str) or not isinstance(digest, str):
        raise TypeError(f"invalid {label} observation values")
    path = Path(path_value)
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise RuntimeError(f"{label} path must be absolute, canonical, and non-symlinked")
    _regular_cache_file(path, label)
    if FULL_SHA256.fullmatch(digest) is None or sha256_file(path) != digest:
        raise RuntimeError(f"{label} SHA-256 mismatch")
    return path


def _string_argv(value: object, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise RuntimeError(f"invalid {label} argv")
    return tuple(value)


def verify_review_receipt(
    path: Path, *, central_head: str, workflow_sha256: str
) -> dict[str, object]:
    document = _load_secure_json(path, "trusted review receipt")
    expected = {
        "schema_version",
        "status",
        "central_head",
        "workflow_sha256",
        "reviewer",
        "command",
        "output",
    }
    if set(document) != expected or document["schema_version"] != 1:
        raise RuntimeError("invalid trusted review receipt schema")
    if document["status"] != "PASS":
        raise RuntimeError("trusted review receipt is not PASS")
    if document["central_head"] != central_head:
        raise RuntimeError("trusted review central HEAD mismatch")
    if document["workflow_sha256"] != workflow_sha256:
        raise RuntimeError("trusted review workflow SHA-256 mismatch")
    reviewer = document["reviewer"]
    if not isinstance(reviewer, str) or not reviewer or reviewer.casefold() in {
        "self",
        "runner",
        "main-agent",
    }:
        raise RuntimeError("trusted review requires an independent reviewer identity")
    _string_argv(document["command"], "trusted review command")
    _verify_file_observation(document["output"], "trusted review output")
    return document


def verify_ci_provenance(
    path: Path,
    *,
    central_root: Path,
    central_head: str,
    workflow_sha256: str,
) -> dict[str, object]:
    document = _load_secure_json(path, "CI provenance")
    expected = {
        "schema_version",
        "status",
        "central_head",
        "workflow",
        "workflow_sha256",
        "check_argv",
        "output",
        "toolchain",
    }
    if set(document) != expected or document["schema_version"] != 1:
        raise RuntimeError("invalid CI provenance schema")
    if document["status"] != "PASS":
        raise RuntimeError("CI provenance is not PASS")
    if document["central_head"] != central_head:
        raise RuntimeError("CI provenance central HEAD mismatch")
    workflow = central_root / ".github" / "workflows" / "ci.yml"
    if document["workflow"] != str(workflow):
        raise RuntimeError("CI provenance workflow path mismatch")
    _regular_cache_file(workflow, "CI workflow")
    if (
        document["workflow_sha256"] != workflow_sha256
        or sha256_file(workflow) != workflow_sha256
    ):
        raise RuntimeError("CI provenance workflow SHA-256 mismatch")
    _string_argv(document["check_argv"], "CI check")
    _verify_file_observation(document["output"], "CI output")
    _verify_file_observation(document["toolchain"], "CI toolchain")
    return document


def verify_trusted_provenance(
    manifest: Mapping[str, object], review_path: Path, ci_path: Path
) -> dict[str, str]:
    try:
        central_root = Path(str(manifest["central_root"]))
        central = manifest["catalog_lock"]["catalogs"]["central"]
        central_head = central["repository_head"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("manifest is missing central provenance binding") from exc
    if not isinstance(central_head, str):
        raise TypeError("manifest central HEAD is invalid")
    workflow = central_root / ".github" / "workflows" / "ci.yml"
    _regular_cache_file(workflow, "CI workflow")
    workflow_sha256 = sha256_file(workflow)
    verify_review_receipt(
        review_path,
        central_head=central_head,
        workflow_sha256=workflow_sha256,
    )
    verify_ci_provenance(
        ci_path,
        central_root=central_root,
        central_head=central_head,
        workflow_sha256=workflow_sha256,
    )
    return {
        "review_sha256": sha256_file(review_path),
        "ci_sha256": sha256_file(ci_path),
        "workflow_sha256": workflow_sha256,
    }


def _terminate_process_group(
    process: subprocess.Popen[bytes],
    *,
    terminate_grace_seconds: float,
    drain_seconds: float,
) -> str:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return "SIGTERM"
    try:
        process.wait(timeout=terminate_grace_seconds)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=drain_seconds)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("process group did not drain after SIGKILL") from exc
        return "SIGKILL"


def execute_job(
    *,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: float,
    terminate_grace_seconds: float,
    drain_seconds: float,
    log_path: Path,
    receipt_path: Path,
    identity: Mapping[str, str],
    bindings: Mapping[str, str],
) -> dict[str, object]:
    if not command:
        raise RuntimeError("job command must not be empty")
    if timeout_seconds <= 0 or terminate_grace_seconds < 0 or drain_seconds < 0:
        raise RuntimeError("job timeout and drain values are invalid")
    for path, label in ((log_path, "log"), (receipt_path, "receipt")):
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"immutable job {label} already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    timed_out = False
    process_group_terminated = False
    termination_signal: str | None = None
    with log_path.open("xb") as output:
        try:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=dict(environment),
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            raise RuntimeError(f"cannot launch job command: {command[0]}") from exc
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process_group_terminated = True
            termination_signal = _terminate_process_group(
                process,
                terminate_grace_seconds=terminate_grace_seconds,
                drain_seconds=drain_seconds,
            )
            exit_code = process.returncode
        output.flush()
        os.fsync(output.fileno())

    ended = time.monotonic()
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    last_lines = lines[-80:]
    tail_bytes = "\n".join(last_lines).encode()
    payload: dict[str, object] = {
        "schema_version": 1,
        **dict(identity),
        **dict(bindings),
        "status": "PASS" if exit_code == 0 and not timed_out else "FAIL",
        "command": list(command),
        "cwd": str(cwd),
        "monotonic_started": started,
        "monotonic_ended": ended,
        "elapsed_seconds": ended - started,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "cancelled": False,
        "process_group_terminated": process_group_terminated,
        "termination_signal": termination_signal,
        "input_sha256": {},
        "output_sha256": {},
        "last_80_lines_count": len(last_lines),
        "last_80_lines_sha256": hashlib.sha256(tail_bytes).hexdigest(),
        "full_log_sha256": sha256_file(log_path),
        "artifacts": {"full_log": str(log_path)},
    }
    _candidate_module().write_atomic(receipt_path, canonical_bytes(payload))
    return payload


def _candidate_module():
    path = Path(__file__).resolve().with_name("catalog_candidate.py")
    spec = importlib.util.spec_from_file_location("catalog_candidate_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sanitized_environment(
    source: Mapping[str, str], home: Path, gradle_home: Path
) -> dict[str, str]:
    result = {
        key: source[key]
        for key in ("PATH", "JAVA_HOME", "LANG", "LC_ALL")
        if source.get(key)
    }
    result["HOME"] = str(home)
    result["GRADLE_USER_HOME"] = str(gradle_home)
    return result


def gradle_command(tasks: Sequence[str]) -> tuple[str, ...]:
    if not tasks:
        raise RuntimeError("Gradle task list must not be empty")
    if any(FORBIDDEN_TASK.search(task) for task in tasks):
        raise RuntimeError("forbidden publish/sign/upload Gradle task")
    if any(token in {"dependsOn", "finalizedBy"} for token in tasks):
        raise RuntimeError("forbidden task graph injection")
    return ("./gradlew", *tasks, *GRADLE_FLAGS)


def validate_build_text(text: str) -> None:
    if re.search(
        r'(?i)(?:version\s*=\s*["\'](?:latest\.|[^"\']*\+)|["\'](?:latest\.|[^"\']*\+)["\'])',
        text,
    ):
        raise RuntimeError("dynamic version is forbidden")
    if re.search(r"https?://|mavenLocal\s*\(", text):
        raise RuntimeError("source repository declaration is forbidden")
    if re.search(r"\b(?:dependsOn|finalizedBy)\b", text):
        raise RuntimeError("task graph mutation is forbidden")


def predecessor(stage: Stage) -> Stage | None:
    if stage is Stage.G1:
        return None
    return Stage(f"G{int(stage.value[1:]) - 1}")


def require_predecessor(
    stage: Stage,
    receipt: Mapping[str, object] | None,
    manifest_sha256: str,
    catalog_sha256: str | None = None,
    cache_manifest_sha256: str | None = None,
) -> None:
    required = predecessor(stage)
    if required is None:
        return
    if receipt is None or receipt.get("stage") != required.value:
        raise RuntimeError(f"{stage.value} predecessor {required.value} is not PASS")
    if receipt.get("manifest_sha256") != manifest_sha256:
        raise RuntimeError("predecessor manifest SHA-256 mismatch")
    if catalog_sha256 is not None and receipt.get("catalog_sha256") != catalog_sha256:
        raise RuntimeError("predecessor catalog SHA-256 mismatch")
    if (
        cache_manifest_sha256 is not None
        and receipt.get("cache_manifest_sha256") != cache_manifest_sha256
    ):
        raise RuntimeError("predecessor cache manifest SHA-256 mismatch")
    if stage is Stage.G3 and required is Stage.G2:
        if receipt.get("status") == "PASS":
            return
        if (
            receipt.get("status") == "PARTIAL_HOLD"
            and receipt.get("path_sha") == "PASS"
            and receipt.get("declared_ref") == "BLOCKED_UNTIL_TAG"
        ):
            return
        raise RuntimeError("G3 predecessor G2 path/SHA proof is not PASS")
    if receipt.get("status") != "PASS":
        raise RuntimeError(f"{stage.value} predecessor {required.value} is not PASS")


def evidence_root(manifest: Mapping[str, object]) -> Path:
    try:
        central_root = Path(str(manifest["central_root"]))
        central = manifest["catalog_lock"]["catalogs"]["central"]
        digest = central["sha256"]
        catalog_path = Path(str(central["path"]))
    except (KeyError, TypeError) as exc:
        raise RuntimeError("manifest is missing central catalog lock") from exc
    if not isinstance(digest, str) or FULL_SHA256.fullmatch(digest) is None:
        raise RuntimeError("central catalog SHA must be lowercase full SHA-256")
    expected_catalog = central_root / "gradle" / "libs.versions.toml"
    if catalog_path != expected_catalog or catalog_path.resolve() != catalog_path:
        raise RuntimeError("central catalog path is not canonical")
    _regular_cache_file(catalog_path, "central catalog")
    if sha256_file(catalog_path) != digest:
        raise RuntimeError("central raw catalog SHA-256 mismatch")
    return central_root / "build" / "catalog-authority" / digest


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_and_verify_manifest(path: Path) -> tuple[dict[str, object], str]:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise RuntimeError(
            "manifest path must be absolute, canonical, and non-symlinked"
        )
    _regular_cache_file(path, "candidate manifest")
    module = _candidate_module()
    manifest = module.verify_candidate_manifest(path)
    return manifest, hashlib.sha256(path.read_bytes()).hexdigest()


def _g1_preflight(
    manifest: Mapping[str, object],
    manifest_sha256: str,
    cache_sources: Sequence[CacheSource],
    provenance: Mapping[str, str],
    root: Path,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "manifest_sha256": manifest_sha256,
        "catalog_sha256": manifest["catalog_lock"]["catalogs"]["central"][
            "sha256"
        ],
        "cache_manifest_sha256": manifest["cache_manifest"]["sha256"],
        "cache_source_count": len(cache_sources),
        "cache_source_sha256": [source.sha256 for source in cache_sources],
        "environment_allowlist": [
            "PATH",
            "JAVA_HOME",
            "LANG",
            "LC_ALL",
            "HOME",
            "GRADLE_USER_HOME",
        ],
        "sandbox_exec": str(Path(shutil.which("sandbox-exec") or "")),
        "network_policy": "deny",
        "provenance": dict(provenance),
    }
    path = root / "preflight.json"
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"immutable preflight already exists: {path}")
    _candidate_module().write_atomic(path, canonical_bytes(payload))
    return {"preflight": str(path), "preflight_sha256": sha256_file(path)}


def _g2_catalog_lock(manifest: Mapping[str, object]) -> dict[str, object]:
    try:
        catalogs = manifest["catalog_lock"]["catalogs"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("manifest is missing catalog lock entries") from exc
    if not isinstance(catalogs, dict) or not catalogs:
        raise RuntimeError("manifest catalog lock entries are invalid")
    entries: list[dict[str, str]] = []
    for repository in sorted(catalogs):
        value = catalogs[repository]
        if not isinstance(value, dict):
            raise TypeError(f"catalog lock entry is invalid: {repository}")
        path = Path(str(value.get("path", "")))
        digest = value.get("sha256")
        declared_ref = value.get("declared_ref")
        if (
            not path.is_absolute()
            or path.resolve() != path
            or not isinstance(digest, str)
            or FULL_SHA256.fullmatch(digest) is None
        ):
            raise RuntimeError(f"catalog path/SHA lock is invalid: {repository}")
        _regular_cache_file(path, f"catalog for {repository}")
        if sha256_file(path) != digest:
            raise RuntimeError(f"catalog path/SHA mismatch: {repository}")
        ref_status = (
            "PASS"
            if isinstance(declared_ref, str)
            and declared_ref.startswith("catalog/")
            else "BLOCKED_UNTIL_TAG"
        )
        entries.append(
            {
                "repository": repository,
                "path_sha": "PASS",
                "declared_ref": ref_status,
                "required_ref": "catalog/<approved-train-tag>",
                "catalog_sha256": digest,
            }
        )
    declared_status = (
        "PASS"
        if all(item["declared_ref"] == "PASS" for item in entries)
        else "BLOCKED_UNTIL_TAG"
    )
    return {
        "status": "PASS" if declared_status == "PASS" else "PARTIAL_HOLD",
        "path_sha": "PASS",
        "declared_ref": declared_status,
        "catalogs": entries,
    }


def run_stage(manifest: dict[str, object], manifest_sha256: str, stage: Stage) -> int:
    root = evidence_root(manifest)
    receipts = root / "receipts" / stage.value
    aggregate = receipts / "aggregate.json"
    previous = predecessor(stage)
    previous_receipt = None
    if previous is not None:
        prior_path = root / "receipts" / previous.value / "aggregate.json"
        if prior_path.is_file() and not prior_path.is_symlink():
            previous_receipt = json.loads(prior_path.read_bytes())
    if aggregate.is_file() and not aggregate.is_symlink():
        existing = json.loads(aggregate.read_bytes())
        if existing.get("manifest_sha256") != manifest_sha256:
            raise RuntimeError("immutable aggregate belongs to a different manifest")
        return 0 if existing.get("status") in {"PASS", "PARTIAL_HOLD"} else 2
    try:
        catalog_sha256 = str(
            manifest["catalog_lock"]["catalogs"]["central"]["sha256"]
        )
        cache_binding = manifest["cache_manifest"]
        if not isinstance(cache_binding, dict):
            raise TypeError("invalid cache manifest binding")
        cache_manifest_sha256 = str(cache_binding["sha256"])
        cache_sources = load_cache_manifest(Path(str(cache_binding["path"])))
        require_predecessor(
            stage,
            previous_receipt,
            manifest_sha256,
            catalog_sha256,
            cache_manifest_sha256,
        )
        if shutil.which("sandbox-exec") is None:
            raise RuntimeError(
                "sandbox-exec is unavailable; unsandboxed fallback is forbidden"
            )
        central_root = Path(str(manifest["central_root"]))
        prepare_root = central_root / "build" / "catalog-authority" / "prepare"
        provenance = verify_trusted_provenance(
            manifest,
            prepare_root / "trusted-worktree-review.json",
            prepare_root / "ci-provenance.json",
        )
        details: dict[str, object] = {"provenance": provenance}
        if stage is Stage.G1:
            details.update(
                _g1_preflight(
                    manifest, manifest_sha256, cache_sources, provenance, root
                )
            )
            status, reason = "PASS", "credential-free preflight verified"
        elif stage is Stage.G2:
            details.update(_g2_catalog_lock(manifest))
            status = str(details.pop("status"))
            reason = (
                "catalog path/SHA locks pass; immutable tag authority is pending"
                if status == "PARTIAL_HOLD"
                else "catalog path/SHA/ref locks pass"
            )
        else:
            raise RuntimeError(
                f"{stage.value} execution is not implemented; zero-child fail-closed hold"
            )
    except RuntimeError as exc:
        status, reason, details = "BLOCKED", str(exc), {}
    payload = {
        "schema_version": 1,
        "stage": stage.value,
        "status": status,
        "manifest_sha256": manifest_sha256,
        "catalog_sha256": manifest.get("catalog_lock", {})
        .get("catalogs", {})
        .get("central", {})
        .get("sha256"),
        "cache_manifest_sha256": manifest.get("cache_manifest", {}).get("sha256"),
        "zero_child_launch": True,
        "child_launch_count": 0,
        "reason": reason,
        **details,
    }
    _candidate_module().write_atomic(aggregate, canonical_bytes(payload))
    return 0 if status in {"PASS", "PARTIAL_HOLD"} else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--stage", choices=[stage.value for stage in Stage], required=True
    )
    args = parser.parse_args()
    manifest, digest = load_and_verify_manifest(args.manifest)
    return run_stage(manifest, digest, Stage(args.stage))


if __name__ == "__main__":
    raise SystemExit(main())
