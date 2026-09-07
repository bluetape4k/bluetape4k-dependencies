#!/usr/bin/env python3
"""Validate and compare-and-swap the local Issues #242/#243 receipt.

The receipt is intentionally a small, stdlib-only contract.  It binds every
observation to an exact Git worktree and refuses to infer clean, exact-head,
or adoption evidence from a branch name.  The ``transition`` command only
changes a receipt after it has read and validated the expected state, head, and
signing digest while holding a local file lock.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


SCHEMA_VERSION = 2
TOTAL_VALIDATION_BUDGET_SECONDS = 90 * 60
ISSUES = (242, 243)
STATES = frozenset({"discovered", "prepared", "validated", "adopted", "blocked"})
TERMINAL_STATE = "adopted"
LEGAL_TRANSITIONS = {
    "discovered": frozenset({"prepared", "blocked"}),
    "prepared": frozenset({"validated", "blocked"}),
    "validated": frozenset({"adopted", "blocked"}),
    "blocked": frozenset(),
    "adopted": frozenset(),
}

def _load_catalog_candidate_module() -> Any:
    module_name = "issues_242_243_catalog_candidate"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    module_path = Path(__file__).with_name("catalog_candidate.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load catalog_candidate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_signing_sync_module() -> Any:
    module_name = "issues_242_243_signing_sync"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    module_path = Path(__file__).with_name("sync-publishing-signing-support.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sync-publishing-signing-support.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_CATALOG_CANDIDATE = _load_catalog_candidate_module()
CENTRAL_NAME = _CATALOG_CANDIDATE.REPOSITORY_NAMES["central"]
CATALOG_NAMES = _CATALOG_CANDIDATE.CATALOG_REPOSITORIES
PUBLISHER_NAMES = frozenset(_CATALOG_CANDIDATE.PUBLISHER_REPOSITORIES)
SIGNING_NAMES = frozenset(_CATALOG_CANDIDATE.SIGNING_REPOSITORIES)
CONSUMER_NAMES = ("timefold-workshop", "clinic-appointment")
TIMEFOLD_CONSUMER_COORDINATES = {
    "timefold-workshop": (
        "ai.timefold.solver:timefold-solver-core",
        "ai.timefold.solver:timefold-solver-jackson",
        "ai.timefold.solver:timefold-solver-spring-boot-starter",
    ),
    "clinic-appointment": ("ai.timefold.solver:timefold-solver-benchmark",),
}
ALL_NAMES = CATALOG_NAMES + CONSUMER_NAMES
EVIDENCE_RECEIPT_PATH = "docs/releases/2026-09-06-issues-242-243-local-receipt.json"
CANONICAL_SOURCE_RELATIVE = "config/publishing-signing/PublishingSigningKeySupport.kt"
GENERATED_SIGNING_TARGET_RELATIVE = (
    "buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt"
)
REQUIRED_ADOPTION_PHASES = frozenset(
    {
        "signing-buildsrc",
        "candidate-bom-publication",
        "timefold-graphs-baseline",
        "timefold-graphs-candidate",
        "consumers",
        "publication-poms",
        "candidate-bom-artifacts",
    }
)
ADOPTION_GRAPH_COORDINATES = {
    "bluetape4k-exposed": ("ai.timefold.solver:timefold-solver-core",),
    **TIMEFOLD_CONSUMER_COORDINATES,
}
ADOPTION_GRAPH_TASKS = {
    "bluetape4k-exposed": [
        ":bluetape4k-exposed-timefold-solver-persistence:dependencyInsight"
    ],
    "timefold-workshop": [":school-timetabling:dependencyInsight"],
    "clinic-appointment": [":appointment-solver:dependencyInsight"],
}
ADOPTION_CONSUMER_TASKS = {
    "bluetape4k-exposed": [":bluetape4k-exposed-timefold-solver-persistence:test"],
    "timefold-workshop": sorted(
        [
            ":bluetape4k-timefold:test",
            ":school-timetabling:test",
            ":exposed-jdbc-examples:test",
            ":exposed-r2dbc-examples:test",
        ]
    ),
    "clinic-appointment": sorted(
        [":appointment-solver:test", ":appointment-api:test"]
    ),
}
CANDIDATE_BOM_VERSION = "2.1.0-issue-242.local"
CANDIDATE_INIT_SCRIPT_RELATIVE = Path("config/issues-242-243-candidate.init.gradle")
CANDIDATE_REPOSITORY_PROPERTY = "issues242243CandidateMavenRepo"
CANDIDATE_VERSION_PROPERTY = "issues242243CandidateBomVersion"
CANDIDATE_BOM_ARTIFACTS = frozenset(
    {
        f"bluetape4k-dependencies-{CANDIDATE_BOM_VERSION}.pom",
        f"bluetape4k-dependencies-{CANDIDATE_BOM_VERSION}.module",
    }
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
SECRET_VALUE_RE = re.compile(
    r"(?:-----BEGIN(?: [^-\r\n]+)? PRIVATE KEY-----|"
    r"(?:password|passwd|secret|token|credential|access[_-]?key|private[_-]?key)\s*=|"
    r"(?:ghp_|github_pat_|sk-[A-Za-z0-9]|AKIA[0-9A-Z]{12}))",
    re.IGNORECASE,
)
SECRET_FIELD_RE = re.compile(
    r"(?:password|passwd|secret|credential|private[_-]?key|access[_-]?token|"
    r"authorization|client[_-]?secret|signing[_-]?key)",
    re.IGNORECASE,
)


class ReceiptError(RuntimeError):
    """Raised for any fail-closed receipt or repository-map violation."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_controls(value: Any, location: str = "document") -> None:
    if isinstance(value, str):
        if CONTROL_RE.search(value) or ANSI_RE.search(value):
            raise ReceiptError(f"control or ANSI character in {location}")
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ReceiptError(f"non-string JSON key in {location}")
            _reject_controls(key, f"{location}.{key}")
            _reject_controls(nested, f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_controls(nested, f"{location}[{index}]")


def _reject_secrets(value: Any, location: str = "document") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if SECRET_FIELD_RE.search(key_text):
                # Digest fields contain the word signing but never a secret
                # payload; leave only explicitly digest-shaped keys allowed.
                if not key_text.endswith(("_sha256", "-sha256")):
                    raise ReceiptError(f"secret-bearing field {location}.{key_text}")
            _reject_secrets(nested, f"{location}.{key_text}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secrets(nested, f"{location}[{index}]")
        return
    if isinstance(value, str) and SECRET_VALUE_RE.search(value):
        raise ReceiptError(f"secret-bearing value in {location}")


def _regular_nonsymlink(path: Path, description: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ReceiptError(f"{description} is not readable: {path}") from exc
    if stat.S_ISLNK(mode):
        raise ReceiptError(f"{description} must not be a symlink: {path}")
    if not stat.S_ISREG(mode):
        raise ReceiptError(f"{description} must be a regular file: {path}")


def _canonical_path(value: Any, description: str, *, must_exist: bool = True) -> Path:
    if isinstance(value, Path):
        value = str(value)
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"{description} must be a non-empty path")
    path = Path(value)
    if not path.is_absolute() or path != path.resolve():
        raise ReceiptError(f"{description} must be absolute and canonical")
    # resolve() alone follows a symlink.  Check every existing component so a
    # path cannot silently leave the declared workspace through a parent link.
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            mode = current.lstat().st_mode
        except OSError:
            if must_exist:
                raise ReceiptError(f"{description} is not readable: {path}")
            break
        if stat.S_ISLNK(mode):
            raise ReceiptError(f"{description} contains a symlink: {path}")
    if must_exist and not path.exists():
        raise ReceiptError(f"{description} does not exist: {path}")
    return path


def _require_sha256(value: Any, description: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ReceiptError(f"invalid {description} SHA-256")
    return value


def _require_commit(value: Any, description: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise ReceiptError(f"invalid {description} commit SHA")
    if set(value) == {"0"}:
        raise ReceiptError(f"invalid {description} commit SHA")
    return value


def _require_nonempty_string(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"{description} must be a non-empty string")
    return value


def _read_json(path: Path, description: str) -> Any:
    _regular_nonsymlink(path, description)
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"invalid {description} JSON") from exc
    _reject_controls(document)
    _reject_secrets(document)
    return document


def _git(root: Path, *args: str, input_text: str | None = None) -> str:
    try:
        completed = _CATALOG_CANDIDATE.run_bounded_capture(
            ["git", "-C", str(root), *args],
            cwd=root,
            input_bytes=None if input_text is None else input_text.encode("utf-8"),
        )
        if completed.returncode:
            raise subprocess.CalledProcessError(
                completed.returncode,
                completed.args,
                output=completed.stdout,
                stderr=completed.stderr,
            )
        return completed.stdout.decode("utf-8", errors="strict").strip()
    except (OSError, UnicodeDecodeError, RuntimeError, subprocess.CalledProcessError) as exc:
        detail = "no stderr"
        if isinstance(exc, subprocess.CalledProcessError):
            detail = _CATALOG_CANDIDATE.redact_diagnostic(
                exc.stderr or exc.stdout or b"", max_chars=500
            ).strip() or "no stderr"
        raise ReceiptError(f"git validation failed for {root}: {detail}") from exc


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        completed = _CATALOG_CANDIDATE.run_bounded_capture(
            ["git", "-C", str(root), *args], cwd=root
        )
    except (OSError, RuntimeError) as exc:
        raise ReceiptError(f"git object validation failed for {root}") from exc
    if completed.returncode:
        raise ReceiptError(f"git object validation failed for {root}")
    return completed.stdout


def _approved_origin(name: str) -> str:
    return f"git@github.com:bluetape4k/{name}.git"


def _infer_role(name: str) -> str:
    if name == CENTRAL_NAME:
        return "central"
    if name == "bluetape4k-experimental":
        return "validation-only"
    if name in SIGNING_NAMES:
        return "publisher"
    return "consumer"


def _catalog_candidate_module() -> Any:
    return _CATALOG_CANDIDATE


def _strict_map_workspace(document: Any) -> Path:
    if not isinstance(document, Mapping):
        raise ReceiptError("repository map must be an object")
    central = document.get("central")
    repositories = document.get("repositories")
    if not isinstance(central, Mapping) or not isinstance(repositories, Mapping):
        raise ReceiptError("repository map must use the strict v1 schema")
    entries = [central, *repositories.values()]
    roots = [entry.get("root") for entry in entries if isinstance(entry, Mapping)]
    if len(roots) != len(entries) or not all(isinstance(root, str) for root in roots):
        raise ReceiptError("repository map root fields are invalid")
    try:
        workspace = Path(os.path.commonpath(roots))
    except (TypeError, ValueError) as exc:
        raise ReceiptError("repository map workspace cannot be resolved") from exc
    return _canonical_path(workspace, "repository map workspace root")


def _validate_worktree_entry(
    entry: Mapping[str, Any], workspace_root: Path
) -> dict[str, Any]:
    name = entry["name"]
    if entry["role"] != _infer_role(name):
        raise ReceiptError(f"repository role mismatch for {name}")
    if name == "bluetape4k-experimental" and entry["validation_only"] is not True:
        raise ReceiptError("experimental repository must be validation-only")
    if name != "bluetape4k-experimental" and entry["validation_only"] is True:
        raise ReceiptError(f"unexpected validation-only repository for {name}")
    root = _canonical_path(entry["canonical_path"], f"repository path for {name}")
    worktree = _canonical_path(entry["candidate_worktree"], f"worktree path for {name}")
    if root != worktree:
        raise ReceiptError(f"repository path/worktree mismatch for {name}")
    if not root.is_dir() or root.is_symlink():
        raise ReceiptError(f"repository worktree is not a directory for {name}")
    if not _is_relative_to(root, workspace_root):
        raise ReceiptError(f"repository path escapes workspace for {name}")
    origin = _require_nonempty_string(entry["origin"], f"origin for {name}")
    if origin != _approved_origin(name):
        raise ReceiptError(f"origin allowlist mismatch for {name}")
    if _git(root, "remote", "get-url", "origin") != origin:
        raise ReceiptError(f"origin mismatch for {name}")
    base_ref = _require_nonempty_string(entry["base_ref"], f"base ref for {name}")
    if base_ref != "origin/develop":
        raise ReceiptError(f"base ref must be origin/develop for {name}")
    base_sha = _require_commit(entry["base_sha"], f"base for {name}")
    candidate_sha = _require_commit(entry["candidate_head"], f"candidate for {name}")
    branch = _require_nonempty_string(entry["candidate_branch"], f"candidate branch for {name}")
    if branch in {"develop", "main", "master"}:
        raise ReceiptError(f"candidate branch must be isolated for {name}")
    if entry["clean"] is not True or entry["exact_head"] is not True:
        raise ReceiptError(f"repository map requires clean exact-head state for {name}")
    if _git(root, "rev-parse", "HEAD") != candidate_sha:
        raise ReceiptError(f"candidate HEAD mismatch for {name}")
    if _git(root, "branch", "--show-current") != branch:
        raise ReceiptError(f"candidate branch mismatch for {name}")
    if _git(root, "rev-parse", f"{base_sha}^{{commit}}") != base_sha:
        raise ReceiptError(f"base SHA does not peel for {name}")
    if _git(root, "rev-parse", f"{candidate_sha}^{{commit}}") != candidate_sha:
        raise ReceiptError(f"candidate SHA does not peel for {name}")
    develop_head = _git(root, "rev-parse", "refs/remotes/origin/develop^{commit}")
    if _git(root, "merge-base", candidate_sha, develop_head) != base_sha:
        raise ReceiptError(f"base SHA is not the origin/develop fork point for {name}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReceiptError(f"repository is dirty for {name}")
    return dict(entry)


def load_repository_map(path: Path) -> dict[str, Any]:
    """Reuse the catalog candidate strict-v1 loader for the ten catalog repos."""
    path = _canonical_path(path, "repository map")
    document = _read_json(path, "repository map")
    workspace_root = _strict_map_workspace(document)
    candidate = _catalog_candidate_module()
    try:
        repositories = candidate.load_repository_map_v1(path, workspace_root)
    except RuntimeError as exc:
        raise ReceiptError(f"strict repository map validation failed: {exc}") from exc
    verified = [
        {
            "name": item.name,
            "role": _infer_role(item.name),
            "canonical_path": str(item.root),
            "candidate_worktree": str(item.root),
            "origin": item.origin,
            "base_ref": "origin/develop",
            "base_sha": item.base_sha,
            "candidate_branch": item.branch,
            "candidate_head": item.expected_head,
            "clean": True,
            "exact_head": True,
            "validation_only": item.name == "bluetape4k-experimental",
        }
        for item in repositories
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "workspace_root": str(workspace_root),
        "repositories": verified,
    }
    return result


def _expected_fields(value: Any, fields: set[str], description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ReceiptError(f"{description} fields are invalid")
    return value


def _validate_digest_file(path_value: Any, digest_value: Any, description: str, parent: Path) -> Path:
    path = _canonical_path(path_value, f"{description} path")
    if not _is_relative_to(path, parent):
        raise ReceiptError(f"{description} path escapes repository")
    _regular_nonsymlink(path, description)
    digest = _require_sha256(digest_value, description)
    if sha256_bytes(path.read_bytes()) != digest:
        raise ReceiptError(f"{description} SHA-256 mismatch")
    return path


def _validate_common_repo_receipt(
    item: Any,
    mapped: Mapping[str, Any],
    *,
    expected_signing_sha256: str,
) -> dict[str, Any]:
    fields = {
        "name",
        "role",
        "origin",
        "base_ref",
        "base_sha",
        "candidate_branch",
        "candidate_worktree",
        "candidate_head",
        "clean",
        "exact_head",
        "state",
        "signing_sha256",
    }
    value = _expected_fields(item, fields, "repository receipt")
    name = _require_nonempty_string(value["name"], "repository receipt name")
    if name != mapped["name"] or value["role"] != mapped["role"]:
        raise ReceiptError(f"repository receipt does not match map for {name}")
    for key in ("origin", "base_ref", "candidate_branch", "candidate_worktree"):
        if value[key] != mapped[key]:
            raise ReceiptError(f"repository receipt {key} mismatch for {name}")
    if value["clean"] is not True or value["exact_head"] is not True:
        raise ReceiptError(f"repository receipt requires clean exact-head state for {name}")
    if _require_commit(value["base_sha"], f"{name} base") != mapped["base_sha"]:
        raise ReceiptError(f"repository receipt base SHA mismatch for {name}")
    if _require_commit(value["candidate_head"], f"{name} candidate") != mapped["candidate_head"]:
        raise ReceiptError(f"repository receipt candidate SHA mismatch for {name}")
    state = value["state"]
    if state not in STATES:
        raise ReceiptError(f"invalid state for {name}")
    signing = _require_sha256(value["signing_sha256"], f"{name} signing")
    if signing != expected_signing_sha256:
        raise ReceiptError(f"signing digest mismatch for {name}")
    return dict(value)


def _validate_generated_signing_helper(
    repository: Mapping[str, Any], expected_payload: bytes
) -> None:
    name = str(repository["name"])
    if name not in SIGNING_NAMES:
        return
    root = _canonical_path(
        repository["candidate_worktree"], f"{name} candidate worktree"
    )
    target = root / GENERATED_SIGNING_TARGET_RELATIVE
    _regular_nonsymlink(target, f"generated signing helper for {name}")
    if target.read_bytes() != expected_payload:
        raise ReceiptError(f"generated signing helper mismatch for {name}")


def _validate_graph(graph: Any, consumer: str) -> None:
    fields = {
        "coordinate",
        "configuration",
        "before_version",
        "after_version",
        "selection_reason",
        "output_sha256",
    }
    value = _expected_fields(graph, fields, f"graph for {consumer}")
    for key in ("coordinate", "configuration", "before_version", "after_version", "selection_reason"):
        _require_nonempty_string(value[key], f"graph {key} for {consumer}")
    _require_sha256(value["output_sha256"], f"graph output for {consumer}")


def _validate_consumer(
    item: Any, workspace_root: Path, expected_signing_sha256: str
) -> dict[str, Any]:
    fields = {
        "name",
        "role",
        "origin",
        "base_ref",
        "base_sha",
        "candidate_branch",
        "candidate_worktree",
        "candidate_head",
        "clean",
        "exact_head",
        "state",
        "signing_sha256",
        "catalog_ref",
        "catalog_sha256",
        "catalog_source",
        "bom_coordinate",
        "local_override",
        "graphs",
    }
    value = _expected_fields(item, fields, "consumer receipt")
    name = _require_nonempty_string(value["name"], "consumer name")
    if name not in CONSUMER_NAMES or value["role"] != "consumer":
        raise ReceiptError(f"consumer receipt is not allowlisted: {name}")
    _validate_worktree_entry(
        {
            "name": name,
            "role": "consumer",
            "canonical_path": value["candidate_worktree"],
            "candidate_worktree": value["candidate_worktree"],
            "origin": value["origin"],
            "base_ref": value["base_ref"],
            "base_sha": value["base_sha"],
            "candidate_branch": value["candidate_branch"],
            "candidate_head": value["candidate_head"],
            "clean": value["clean"],
            "exact_head": value["exact_head"],
            "validation_only": False,
        },
        workspace_root,
    )
    if value["state"] not in STATES:
        raise ReceiptError(f"invalid consumer state for {name}")
    signing = _require_sha256(value["signing_sha256"], f"{name} signing")
    if signing != expected_signing_sha256:
        raise ReceiptError(f"signing digest mismatch for {name}")
    _require_nonempty_string(value["catalog_ref"], f"{name} catalog ref")
    _require_sha256(value["catalog_sha256"], f"{name} catalog")
    if value["catalog_source"] not in {"local-candidate", "immutable-ref", "repo-local"}:
        raise ReceiptError(f"invalid catalog source for {name}")
    _require_nonempty_string(value["bom_coordinate"], f"{name} BOM coordinate")
    if value["local_override"] not in {"present", "removed", "not-applicable"}:
        raise ReceiptError(f"invalid local override for {name}")
    if not isinstance(value["graphs"], list) or not value["graphs"]:
        raise ReceiptError(f"consumer graphs are missing for {name}")
    for graph in value["graphs"]:
        _validate_graph(graph, name)
    return dict(value)


def _validate_passed_candidate_graphs(
    consumers: Sequence[Mapping[str, Any]], commands: Sequence[Mapping[str, Any]]
) -> None:
    for consumer in consumers:
        name = str(consumer["name"])
        expected = TIMEFOLD_CONSUMER_COORDINATES[name]
        graphs = consumer["graphs"]
        coordinates = [graph.get("coordinate") for graph in graphs]
        if len(coordinates) != len(expected) or set(coordinates) != set(expected):
            raise ReceiptError(f"consumer graph coordinates mismatch for {name}")
        for graph in graphs:
            coordinate = str(graph["coordinate"])
            if graph["configuration"] != "testRuntimeClasspath":
                raise ReceiptError(f"consumer graph configuration mismatch for {name}")
            if graph["before_version"] == "pending-baseline":
                raise ReceiptError(f"consumer baseline graph is pending for {name}")
            if graph["after_version"] != "2.6.0":
                raise ReceiptError(f"consumer candidate graph version mismatch for {name}")
            reason = str(graph["selection_reason"])
            if not reason.startswith("before: ") or "; after: " not in reason:
                raise ReceiptError(f"consumer graph selection reason mismatch for {name}")
            digest = str(graph["output_sha256"])
            if digest == "0" * 64:
                raise ReceiptError(f"consumer graph output is pending for {name}")
            if not any(
                command.get("repository") == name
                and command.get("configuration") == graph["configuration"]
                and command.get("result") == "pass"
                and command.get("output_sha256") == digest
                and f"--dependency {coordinate}" in str(command.get("command", ""))
                for command in commands
            ):
                raise ReceiptError(f"consumer graph command binding mismatch for {name}")


LEGACY_COMMAND_FIELDS = {
    "repository",
    "command",
    "jdk",
    "gradle",
    "configuration",
    "elapsed_seconds",
    "cache",
    "result",
    "output_sha256",
}
BOUND_COMMAND_FIELDS = LEGACY_COMMAND_FIELDS | {
    "phase",
    "coordinate",
    "selected_version",
    "selection_reason",
    "repository_head",
    "helper_sha256",
    "catalog_sha256",
    "bom_sha256",
    "task_set",
    "override_disposition",
    "arguments",
    "gradle_home_policy",
    "input_sha256",
    "job_id",
    "cache_key",
    "cache_output_path",
}


def _bound_command_input(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository": item["repository"],
        "phase": item["phase"],
        "command": item["command"],
        "repository_head": item["repository_head"],
        "helper_sha256": item["helper_sha256"],
        "catalog_sha256": item["catalog_sha256"],
        "bom_sha256": item["bom_sha256"],
        "task_set": item["task_set"],
        "configuration": item["configuration"],
        "jdk": item["jdk"],
        "gradle": item["gradle"],
        "coordinate": item["coordinate"],
        "override_disposition": item["override_disposition"],
        "arguments": item["arguments"],
        "gradle_home_policy": item["gradle_home_policy"],
    }


def _validate_commands(value: Any, evidence_cache_root: Path | None) -> None:
    if not isinstance(value, list):
        raise ReceiptError("commands must be an array")
    for command in value:
        if not isinstance(command, Mapping) or frozenset(command) not in {
            frozenset(LEGACY_COMMAND_FIELDS),
            frozenset(BOUND_COMMAND_FIELDS),
        }:
            raise ReceiptError("command fields are invalid")
        item = command
        for key in ("repository", "command", "jdk", "gradle", "configuration"):
            _require_nonempty_string(item[key], f"command {key}")
        if not isinstance(item["elapsed_seconds"], (int, float)) or item["elapsed_seconds"] < 0:
            raise ReceiptError("command elapsed_seconds is invalid")
        if item["cache"] not in {"isolated", "shared-read"}:
            raise ReceiptError("command cache policy is invalid")
        if item["result"] not in {"pass", "fail", "blocked"}:
            raise ReceiptError("command result is invalid")
        _require_sha256(item["output_sha256"], "command output")
        if set(item) == BOUND_COMMAND_FIELDS:
            _require_nonempty_string(item["phase"], "command phase")
            _require_nonempty_string(item["job_id"], "command job ID")
            _require_commit(item["repository_head"], "command repository HEAD")
            for key in ("helper_sha256", "catalog_sha256", "bom_sha256"):
                _require_sha256(item[key], f"command {key}")
            if not isinstance(item["task_set"], list) or not item["task_set"]:
                raise ReceiptError("command task_set is invalid")
            for task in item["task_set"]:
                _require_nonempty_string(task, "command task")
            if item["task_set"] != sorted(set(item["task_set"])):
                raise ReceiptError("command task_set must be sorted and unique")
            if item["override_disposition"] not in {"baseline", "candidate"}:
                raise ReceiptError("command override disposition is invalid")
            if not isinstance(item["arguments"], list) or any(
                not isinstance(argument, str) or not argument
                for argument in item["arguments"]
            ):
                raise ReceiptError("command arguments are invalid")
            if item["gradle_home_policy"] != "ephemeral-0700":
                raise ReceiptError("command Gradle home policy is invalid")
            coordinate = item["coordinate"]
            selected = item["selected_version"]
            reason = item["selection_reason"]
            if not all(value is None or isinstance(value, str) for value in (coordinate, selected, reason)):
                raise ReceiptError("command graph evidence is invalid")
            if item["phase"].startswith("timefold-graphs-"):
                _require_nonempty_string(coordinate, "command graph coordinate")
                if item["result"] == "pass":
                    _require_nonempty_string(selected, "command selected version")
                    _require_nonempty_string(reason, "command selection reason")
            elif any(value is not None for value in (coordinate, selected, reason)):
                raise ReceiptError("non-graph command contains graph evidence")
            expected_input = sha256_bytes(canonical_json_bytes(_bound_command_input(item)))
            if _require_sha256(item["input_sha256"], "command input") != expected_input:
                raise ReceiptError("command input SHA-256 mismatch")
            cache_key_value = item["cache_key"]
            cache_output_value = item["cache_output_path"]
            if item["result"] == "pass":
                expected_cache_key = sha256_bytes(
                    canonical_json_bytes(
                        {
                            "schema_version": 1,
                            "repository": item["repository"],
                            "repository_head": item["repository_head"],
                            "helper_sha256": item["helper_sha256"],
                            "catalog_sha256": item["catalog_sha256"],
                            "bom_sha256": item["bom_sha256"],
                            "task_set": item["task_set"],
                            "configuration": item["configuration"],
                            "jdk_version": item["jdk"],
                            "gradle_version": item["gradle"],
                            "arguments": item["arguments"],
                            "gradle_home_policy": item["gradle_home_policy"],
                        }
                    )
                )
                if _require_sha256(cache_key_value, "command cache key") != expected_cache_key:
                    raise ReceiptError("command cache key mismatch")
                output_path = _canonical_path(cache_output_value, "command cache output")
                if evidence_cache_root is None or output_path.parent != evidence_cache_root:
                    raise ReceiptError("command cache output escapes receipt cache root")
                if output_path.name != f"{expected_cache_key}.output":
                    raise ReceiptError("command cache output path mismatch")
                _regular_nonsymlink(output_path, "command cache output")
                if stat.S_IMODE(output_path.stat().st_mode) & 0o077:
                    raise ReceiptError("command cache output permissions are not private")
                if sha256_bytes(output_path.read_bytes()) != item["output_sha256"]:
                    raise ReceiptError("command cache output SHA-256 mismatch")
            elif cache_key_value is not None or cache_output_value is not None:
                raise ReceiptError("non-passing command must not claim cache evidence")


def _validate_phases(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ReceiptError("phases are missing")
    fields = {
        "name",
        "result",
        "output_sha256",
        "elapsed_seconds",
        "reserved_seconds",
        "job_ids",
    }
    for phase in value:
        item = _expected_fields(phase, fields, "phase")
        _require_nonempty_string(item["name"], "phase name")
        if item["result"] not in {"pass", "fail", "blocked"}:
            raise ReceiptError("phase result is invalid")
        _require_sha256(item["output_sha256"], "phase output")
        for field in ("elapsed_seconds", "reserved_seconds"):
            number = item[field]
            if isinstance(number, bool) or not isinstance(number, (int, float)) or number < 0:
                raise ReceiptError(f"phase {field} is invalid")
        if not isinstance(item["job_ids"], list) or any(
            not isinstance(job_id, str) or not job_id for job_id in item["job_ids"]
        ):
            raise ReceiptError("phase job IDs are invalid")
        if len(item["job_ids"]) != len(set(item["job_ids"])):
            raise ReceiptError("phase job IDs must be unique")


def _validate_candidate_artifact_manifest(
    value: Any,
    *,
    central: Mapping[str, Any],
    artifact_phase: Mapping[str, Any],
) -> None:
    fields = {
        "repository_path",
        "version",
        "artifacts",
        "repository_files",
        "sha256",
        "central_head",
        "catalog_sha256",
        "source_tree_sha256",
        "producer_job_id",
        "producer_input_sha256",
        "producer_output_sha256",
    }
    item = _expected_fields(value, fields, "candidate artifact manifest")
    repository = _canonical_path(
        item["repository_path"], "candidate Maven repository"
    )
    if not repository.is_dir() or repository.is_symlink():
        raise ReceiptError("candidate Maven repository must be a directory")
    if item["version"] != CANDIDATE_BOM_VERSION:
        raise ReceiptError("candidate BOM version mismatch")
    if item["central_head"] != central["candidate_head"]:
        raise ReceiptError("candidate artifact central HEAD mismatch")
    central_root = _canonical_path(
        central["candidate_worktree"], "central candidate worktree"
    )
    catalog = central_root / "gradle/libs.versions.toml"
    _regular_nonsymlink(catalog, "candidate catalog")
    if _require_sha256(item["catalog_sha256"], "candidate catalog") != sha256_bytes(
        catalog.read_bytes()
    ):
        raise ReceiptError("candidate artifact catalog SHA-256 mismatch")
    source_tree = _git_bytes(
        central_root, "ls-tree", "-r", "-z", str(item["central_head"])
    )
    if _require_sha256(item["source_tree_sha256"], "candidate source tree") != sha256_bytes(
        source_tree
    ):
        raise ReceiptError("candidate source tree SHA-256 mismatch")
    _require_nonempty_string(item["producer_job_id"], "candidate producer job ID")
    _require_sha256(item["producer_input_sha256"], "candidate producer input")
    _require_sha256(item["producer_output_sha256"], "candidate producer output")

    repository_files = item["repository_files"]
    if not isinstance(repository_files, Mapping) or not repository_files:
        raise ReceiptError("candidate repository file manifest is missing")
    actual_files: dict[str, str] = {}
    for path in sorted(repository.rglob("*")):
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise ReceiptError("candidate Maven repository cannot be read") from exc
        if stat.S_ISLNK(mode):
            raise ReceiptError("candidate Maven repository contains a symlink")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ReceiptError("candidate Maven repository contains a non-file")
        actual_files[path.relative_to(repository).as_posix()] = sha256_bytes(
            path.read_bytes()
        )
    if dict(repository_files) != actual_files:
        raise ReceiptError("candidate repository file manifest mismatch")
    repository_sha256 = sha256_bytes(canonical_json_bytes(actual_files))
    if _require_sha256(item["sha256"], "candidate repository") != repository_sha256:
        raise ReceiptError("candidate repository SHA-256 mismatch")
    if artifact_phase["output_sha256"] != repository_sha256:
        raise ReceiptError("candidate artifact phase does not bind repository manifest")

    artifacts = item["artifacts"]
    if not isinstance(artifacts, Mapping) or set(artifacts) != CANDIDATE_BOM_ARTIFACTS:
        raise ReceiptError("candidate BOM artifact allowlist mismatch")
    artifact_prefix = (
        f"io/github/bluetape4k/bluetape4k-dependencies/{CANDIDATE_BOM_VERSION}/"
    )
    for name, digest in artifacts.items():
        if _require_sha256(digest, f"candidate BOM artifact {name}") != actual_files.get(
            artifact_prefix + str(name)
        ):
            raise ReceiptError("candidate BOM artifact SHA-256 mismatch")
    pom_name = f"bluetape4k-dependencies-{CANDIDATE_BOM_VERSION}.pom"
    module_name = f"bluetape4k-dependencies-{CANDIDATE_BOM_VERSION}.module"
    artifact_directory = repository / artifact_prefix
    try:
        pom_root = ET.parse(artifact_directory / pom_name).getroot()
        namespace = ""
        if pom_root.tag.startswith("{"):
            namespace = pom_root.tag.partition("}")[0] + "}"
        pom_identity = tuple(
            (pom_root.findtext(f"{namespace}{field}") or "").strip()
            for field in ("groupId", "artifactId", "version")
        )
        component = json.loads(
            (artifact_directory / module_name).read_text(encoding="utf-8")
        )["component"]
        module_identity = (
            component["group"],
            component["module"],
            component["version"],
        )
    except (ET.ParseError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ReceiptError("candidate BOM metadata is malformed") from exc
    expected_identity = (
        "io.github.bluetape4k",
        "bluetape4k-dependencies",
        CANDIDATE_BOM_VERSION,
    )
    if pom_identity != expected_identity or module_identity != expected_identity:
        raise ReceiptError("candidate BOM metadata identity mismatch")


def _validate_terminal_evidence(document: Mapping[str, Any]) -> None:
    state = str(document["current_state"])
    phases = document["phases"]
    phase_names = [str(item["name"]) for item in phases]
    if len(phase_names) != len(set(phase_names)):
        raise ReceiptError(f"{state} receipt contains duplicate phases")
    missing = REQUIRED_ADOPTION_PHASES - set(phase_names)
    if missing:
        raise ReceiptError(
            f"{state} receipt is missing required phases: " + ", ".join(sorted(missing))
        )
    unknown = set(phase_names) - REQUIRED_ADOPTION_PHASES - {"discover"}
    if unknown:
        raise ReceiptError(
            f"{state} receipt contains unknown phases: " + ", ".join(sorted(unknown))
        )
    if any(item["result"] != "pass" for item in phases):
        raise ReceiptError(f"{state} receipt requires every phase to pass")
    artifact_phase = next(
        item for item in phases if item["name"] == "candidate-bom-artifacts"
    )
    if artifact_phase["output_sha256"] == "0" * 64:
        raise ReceiptError(f"{state} receipt candidate artifact manifest is empty")
    if document["failure_record"] or document["rollback_record"]:
        raise ReceiptError(f"{state} receipt requires empty failure and rollback records")

    central_receipt = next(
        item for item in document["repositories"] if item["name"] == CENTRAL_NAME
    )
    _validate_candidate_artifact_manifest(
        document["candidate_artifact_manifest"],
        central=central_receipt,
        artifact_phase=artifact_phase,
    )

    commands = document["commands"]
    if not commands or any(set(item) != BOUND_COMMAND_FIELDS for item in commands):
        raise ReceiptError(f"{state} receipt requires immutable command evidence")
    if any(item["result"] != "pass" for item in commands):
        raise ReceiptError(f"{state} receipt requires every command to pass")
    command_job_ids = [str(item["job_id"]) for item in commands]
    if len(command_job_ids) != len(set(command_job_ids)):
        raise ReceiptError(f"{state} receipt contains duplicate command job IDs")

    elapsed_total = 0.0
    remaining = float(TOTAL_VALIDATION_BUDGET_SECONDS)
    for phase in phases:
        name = str(phase["name"])
        if name in {"discover", "candidate-bom-artifacts"}:
            if phase["elapsed_seconds"] != 0 or phase["reserved_seconds"] != 0 or phase["job_ids"]:
                raise ReceiptError(f"{name} phase must not consume validation budget")
            continue
        phase_commands = {
            str(item["job_id"]): item for item in commands if item["phase"] == name
        }
        if phase["job_ids"] != list(phase_commands):
            raise ReceiptError("phase job IDs do not bind exact command coverage")
        reserved = float(phase["reserved_seconds"])
        elapsed = float(phase["elapsed_seconds"])
        if abs(reserved - remaining) > 0.001 or elapsed > reserved + 0.001:
            raise ReceiptError("phase validation budget reservation mismatch")
        command_elapsed = max(
            (
                float(phase_commands[job_id]["elapsed_seconds"])
                for job_id in phase["job_ids"]
            ),
            default=0.0,
        )
        if command_elapsed > elapsed + 0.001:
            raise ReceiptError("phase elapsed time is smaller than a command elapsed time")
        phase_payload = {
            "schema_version": 1,
            "phase": name,
            "results": [
                {
                    "status": phase_commands[job_id]["result"],
                    "output_sha256": phase_commands[job_id]["output_sha256"],
                    "cached": phase_commands[job_id]["cache"] == "shared-read",
                    "job_id": job_id,
                    "repository": phase_commands[job_id]["repository"],
                    "cancelled": False,
                }
                for job_id in phase["job_ids"]
            ],
            "failure": None,
        }
        if phase["output_sha256"] != sha256_bytes(canonical_json_bytes(phase_payload)):
            raise ReceiptError("phase output SHA-256 mismatch")
        elapsed_total += elapsed
        remaining -= elapsed
    budget = document["validation_budget"]
    if (
        abs(float(budget["elapsed_seconds"]) - elapsed_total) > 0.001
        or abs(float(budget["remaining_seconds"]) - remaining) > 0.001
    ):
        raise ReceiptError("validation budget is not bound to phase evidence")

    known_command_phases = REQUIRED_ADOPTION_PHASES - {"candidate-bom-artifacts"}
    if {item["phase"] for item in commands} - known_command_phases:
        raise ReceiptError("adopted receipt contains unknown command phases")
    producer_commands = [
        item for item in commands if item["phase"] == "candidate-bom-publication"
    ]
    if len(producer_commands) != 1:
        raise ReceiptError("adopted receipt candidate producer coverage is incomplete")
    producer = producer_commands[0]
    manifest = document["candidate_artifact_manifest"]
    expected_repository = str(
        Path(document["repository_map"]["path"]).parent / "candidate-m2"
    )
    expected_arguments = [
        f"-Dmaven.repo.local={expected_repository}",
        f"-PbaseVersion={CANDIDATE_BOM_VERSION}",
        "-PsnapshotVersion=",
    ]
    if (
        producer["repository"] != CENTRAL_NAME
        or producer["repository_head"] != document["central"]["candidate_head"]
        or producer["task_set"]
        != ["publishBluetapeDependenciesPublicationToMavenLocal"]
        or producer["configuration"] != "candidate-bom-publication"
        or producer["arguments"] != expected_arguments
        or producer["job_id"] != manifest["producer_job_id"]
        or producer["input_sha256"] != manifest["producer_input_sha256"]
        or producer["output_sha256"] != manifest["producer_output_sha256"]
        or manifest["repository_path"] != expected_repository
    ):
        raise ReceiptError("candidate producer provenance mismatch")
    central_root = Path(central_receipt["candidate_worktree"])
    for field, relative in (
        ("helper_sha256", GENERATED_SIGNING_TARGET_RELATIVE),
        ("catalog_sha256", "gradle/libs.versions.toml"),
        ("bom_sha256", "build.gradle.kts"),
    ):
        source = central_root / relative
        _regular_nonsymlink(source, f"candidate producer {field}")
        if producer[field] != sha256_bytes(source.read_bytes()):
            raise ReceiptError("candidate producer source digest mismatch")
    candidate_init_script = central_root / CANDIDATE_INIT_SCRIPT_RELATIVE
    _regular_nonsymlink(candidate_init_script, "candidate init script")
    candidate_init_sha256 = sha256_bytes(candidate_init_script.read_bytes())
    candidate_arguments = [
        "--init-script",
        str(candidate_init_script),
        f"-D{CANDIDATE_REPOSITORY_PROPERTY}={expected_repository}",
        f"-D{CANDIDATE_VERSION_PROPERTY}={CANDIDATE_BOM_VERSION}",
    ]
    candidate_commands = [
        item
        for item in commands
        if item["phase"] in {"timefold-graphs-candidate", "consumers"}
    ]
    if not candidate_commands or any(
        item["helper_sha256"] != candidate_init_sha256
        or item["bom_sha256"] != manifest["sha256"]
        or item["arguments"][: len(candidate_arguments)] != candidate_arguments
        for item in candidate_commands
    ):
        raise ReceiptError("candidate consumer injection provenance mismatch")
    signing_commands = [
        item for item in commands if item["phase"] == "signing-buildsrc"
    ]
    if len(signing_commands) != len(SIGNING_NAMES) or {
        item["repository"] for item in signing_commands
    } != set(SIGNING_NAMES):
        raise ReceiptError("adopted receipt signing command coverage is incomplete")
    if any(item["task_set"] != ["compileKotlin", "test"] for item in signing_commands):
        raise ReceiptError("adopted receipt signing task coverage is incomplete")
    if any(item["arguments"] for item in signing_commands):
        raise ReceiptError("adopted receipt signing command arguments are invalid")

    expected_graphs = {
        (phase, repository, coordinate)
        for phase in ("timefold-graphs-baseline", "timefold-graphs-candidate")
        for repository, coordinates in ADOPTION_GRAPH_COORDINATES.items()
        for coordinate in coordinates
    }
    graph_command_values = [
        item for item in commands if item["phase"].startswith("timefold-graphs-")
    ]
    graph_commands = {
        (item["phase"], item["repository"], item["coordinate"]): item
        for item in graph_command_values
    }
    if len(graph_command_values) != len(expected_graphs) or set(graph_commands) != expected_graphs:
        raise ReceiptError("adopted receipt graph command coverage is incomplete")
    for repository, coordinates in ADOPTION_GRAPH_COORDINATES.items():
        for coordinate in coordinates:
            baseline = graph_commands[("timefold-graphs-baseline", repository, coordinate)]
            candidate = graph_commands[("timefold-graphs-candidate", repository, coordinate)]
            if baseline["override_disposition"] != "baseline":
                raise ReceiptError("baseline graph command uses candidate overrides")
            if candidate["override_disposition"] != "candidate":
                raise ReceiptError("candidate graph command lacks candidate overrides")
            if baseline["selected_version"] == "2.6.0":
                raise ReceiptError("baseline graph already selects candidate Timefold")
            if candidate["selected_version"] != "2.6.0":
                raise ReceiptError("candidate graph does not select Timefold 2.6.0")
            if baseline["task_set"] != ADOPTION_GRAPH_TASKS[repository] or candidate[
                "task_set"
            ] != ADOPTION_GRAPH_TASKS[repository]:
                raise ReceiptError("adopted receipt graph task coverage is incomplete")
            expected_baseline_arguments = [
                "--configuration",
                "testRuntimeClasspath",
                "--dependency",
                coordinate,
            ]
            expected_candidate_arguments = candidate_arguments + expected_baseline_arguments
            if baseline["arguments"] != expected_baseline_arguments:
                raise ReceiptError("baseline graph command arguments are incomplete")
            if candidate["arguments"] != expected_candidate_arguments:
                raise ReceiptError("candidate graph command arguments are incomplete")
            if baseline["input_sha256"] == candidate["input_sha256"]:
                raise ReceiptError("baseline and candidate graph inputs are not independent")

    consumer_commands = [item for item in commands if item["phase"] == "consumers"]
    if len(consumer_commands) != len(ADOPTION_CONSUMER_TASKS) or {
        item["repository"] for item in consumer_commands
    } != set(ADOPTION_CONSUMER_TASKS):
        raise ReceiptError("adopted receipt consumer command coverage is incomplete")
    for item in consumer_commands:
        if item["task_set"] != ADOPTION_CONSUMER_TASKS[item["repository"]]:
            raise ReceiptError("adopted receipt consumer task coverage is incomplete")
        if item["override_disposition"] != "candidate":
            raise ReceiptError("adopted receipt consumer command lacks candidate overrides")
        expected_arguments = candidate_arguments
        if item["arguments"] != expected_arguments:
            raise ReceiptError("adopted receipt consumer command arguments are incomplete")

    publication_commands = [
        item for item in commands if item["phase"] == "publication-poms"
    ]
    if len(publication_commands) != 1 or publication_commands[0]["repository"] != "publication-poms":
        raise ReceiptError("adopted receipt publication command coverage is incomplete")
    if publication_commands[0]["task_set"] != ["verify-publication-poms.py"]:
        raise ReceiptError("adopted receipt publication task coverage is incomplete")
    if publication_commands[0]["arguments"]:
        raise ReceiptError("adopted receipt publication command arguments are invalid")


def _validate_records(value: Any, description: str) -> None:
    if not isinstance(value, list):
        raise ReceiptError(f"{description} must be an array")
    fields = {"repository", "phase", "reason", "output_sha256"}
    for record in value:
        item = _expected_fields(record, fields, description)
        for key in ("repository", "phase", "reason"):
            _require_nonempty_string(item[key], f"{description} {key}")
        _require_sha256(item["output_sha256"], f"{description} output")


def _validate_validation_budget(value: Any) -> None:
    fields = {"total_seconds", "elapsed_seconds", "remaining_seconds"}
    item = _expected_fields(value, fields, "validation budget")
    total = item["total_seconds"]
    elapsed = item["elapsed_seconds"]
    remaining = item["remaining_seconds"]
    if (
        isinstance(total, bool)
        or isinstance(elapsed, bool)
        or isinstance(remaining, bool)
        or not all(isinstance(number, (int, float)) for number in (total, elapsed, remaining))
        or float(total) != float(TOTAL_VALIDATION_BUDGET_SECONDS)
        or float(elapsed) < 0
        or float(remaining) < 0
        or abs(float(total) - float(elapsed) - float(remaining)) > 0.001
    ):
        raise ReceiptError("validation budget is invalid")


def _git_commit_parents(root: Path, commit: str) -> list[str]:
    line = _git(root, "rev-list", "--parents", "-n", "1", commit)
    parts = line.split()
    if not parts or parts[0] != commit:
        raise ReceiptError("evidence commit object mismatch")
    return parts[1:]


def _validate_evidence_commit(
    root: Path, metadata: Mapping[str, Any], evidence_commit: str | None, expected_parent: str
) -> None:
    fields = {"parent", "path", "bytes_sha256"}
    value = _expected_fields(metadata, fields, "prospective evidence commit")
    parent = _require_commit(value["parent"], "evidence parent")
    if parent != expected_parent:
        raise ReceiptError("evidence commit parent does not match validated candidate HEAD")
    path = _require_nonempty_string(value["path"], "evidence path")
    if path != EVIDENCE_RECEIPT_PATH or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ReceiptError("evidence path is not allowlisted")
    digest = _require_sha256(value["bytes_sha256"], "evidence bytes")
    if evidence_commit is None:
        raise ReceiptError("adopted receipt requires prospective evidence commit")
    commit = _require_commit(evidence_commit, "evidence")
    parents = _git_commit_parents(root, commit)
    if parents != [parent]:
        raise ReceiptError("evidence commit must have exactly the validated parent")
    changed = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
    if changed != [path]:
        raise ReceiptError("evidence commit path is not the sole allowlisted receipt")
    content = _git_bytes(root, "show", f"{commit}:{path}")
    if sha256_bytes(content) != digest:
        raise ReceiptError("evidence receipt bytes digest mismatch")


def _derive_global_state(states: Sequence[str]) -> str:
    if any(state == "blocked" for state in states):
        return "blocked"
    if all(state == "adopted" for state in states):
        return "adopted"
    if all(state in {"validated", "adopted"} for state in states):
        return "validated"
    if any(state in {"prepared", "validated", "adopted"} for state in states):
        return "prepared"
    return "discovered"


def _validate_receipt_document(
    path: Path,
    document: Mapping[str, Any],
    *,
    evidence_commit: str | None = None,
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "issues",
        "current_state",
        "validation_budget",
        "repository_map",
        "central",
        "canonical_signing_source",
        "candidate_artifact_manifest",
        "evidence_cache_root",
        "repositories",
        "consumers",
        "commands",
        "phases",
        "failure_record",
        "rollback_record",
        "evidence_commit",
    }
    _expected_fields(document, fields, "receipt")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ReceiptError("receipt schema version is invalid")
    if document["issues"] != list(ISSUES):
        raise ReceiptError("receipt issue IDs must be [242, 243]")
    _validate_validation_budget(document["validation_budget"])
    state = document["current_state"]
    if state not in STATES:
        raise ReceiptError("receipt current state is invalid")
    map_binding = _expected_fields(document["repository_map"], {"path", "sha256"}, "repository map binding")
    map_path = _canonical_path(map_binding["path"], "repository map binding path")
    map_digest = _require_sha256(map_binding["sha256"], "repository map binding")
    if sha256_bytes(map_path.read_bytes()) != map_digest:
        raise ReceiptError("repository map binding SHA-256 mismatch")
    repository_map = load_repository_map(map_path)
    mapped = {item["name"]: item for item in repository_map["repositories"]}
    central_value = _expected_fields(
        document["central"], {"base_sha", "candidate_head", "clean", "exact_head", "state"}, "central receipt"
    )
    central_map = mapped[CENTRAL_NAME]
    if _require_commit(central_value["base_sha"], "central base") != central_map["base_sha"]:
        raise ReceiptError("central base SHA mismatch")
    if _require_commit(central_value["candidate_head"], "central candidate") != central_map["candidate_head"]:
        raise ReceiptError("central candidate SHA mismatch")
    if central_value["clean"] is not True or central_value["exact_head"] is not True:
        raise ReceiptError("central receipt requires clean exact-head state")
    if central_value["state"] not in STATES:
        raise ReceiptError("central state is invalid")
    source = _expected_fields(document["canonical_signing_source"], {"path", "sha256"}, "canonical signing source")
    source_path = _validate_digest_file(
        source["path"], source["sha256"], "canonical signing source", Path(central_map["candidate_worktree"])
    )
    if source_path.relative_to(Path(central_map["candidate_worktree"])).as_posix() != CANONICAL_SOURCE_RELATIVE:
        raise ReceiptError("canonical signing source path is not allowlisted")
    signing_sync = _load_signing_sync_module()
    expected_generated_helper = signing_sync.render_generated_content(
        source_path.read_bytes()
    )
    repository_values = document["repositories"]
    if not isinstance(repository_values, list) or {item.get("name") for item in repository_values if isinstance(item, Mapping)} != set(CATALOG_NAMES):
        raise ReceiptError("receipt repositories must contain the exact catalog set")
    if len(repository_values) != len(CATALOG_NAMES):
        raise ReceiptError("receipt repositories must contain the exact catalog set")
    verified_repositories = []
    for item in repository_values:
        name = item.get("name") if isinstance(item, Mapping) else None
        if name not in mapped or name not in CATALOG_NAMES:
            raise ReceiptError("receipt repository is not in the catalog allowlist")
        verified = _validate_common_repo_receipt(
                item,
                mapped[name],
                expected_signing_sha256=str(source["sha256"]),
            )
        _validate_generated_signing_helper(verified, expected_generated_helper)
        verified_repositories.append(verified)
    consumers = document["consumers"]
    if not isinstance(consumers, list) or len(consumers) != len(CONSUMER_NAMES):
        raise ReceiptError("receipt consumers must contain Workshop and Clinic")
    if {item.get("name") for item in consumers if isinstance(item, Mapping)} != set(CONSUMER_NAMES):
        raise ReceiptError("receipt consumers must contain the exact consumer set")
    verified_consumers = [
        _validate_consumer(
            item,
            Path(repository_map["workspace_root"]),
            str(source["sha256"]),
        )
        for item in consumers
    ]
    cache_root_value = document["evidence_cache_root"]
    evidence_cache_root = (
        None
        if cache_root_value is None
        else _canonical_path(cache_root_value, "evidence cache root")
    )
    if evidence_cache_root is not None:
        if not evidence_cache_root.is_dir() or evidence_cache_root.is_symlink():
            raise ReceiptError("evidence cache root must be a directory")
        if evidence_cache_root != path.parent / "cache":
            raise ReceiptError("evidence cache root is not receipt-bound")
    _validate_commands(document["commands"], evidence_cache_root)
    _validate_phases(document["phases"])
    if any(
        phase.get("name") == "timefold-graphs-candidate"
        and phase.get("result") == "pass"
        for phase in document["phases"]
        if isinstance(phase, Mapping)
    ):
        _validate_passed_candidate_graphs(
            verified_consumers,
            document["commands"],
        )
    _validate_records(document["failure_record"], "failure record")
    _validate_records(document["rollback_record"], "rollback record")
    evidence = document["evidence_commit"]
    if state in {"validated", "adopted"}:
        _validate_terminal_evidence(document)
    if state == "adopted":
        if not isinstance(evidence, Mapping):
            raise ReceiptError("adopted receipt requires evidence metadata")
        if any(item["state"] != "adopted" for item in verified_repositories + verified_consumers):
            raise ReceiptError("adopted receipt contains a non-adopted repository")
        if central_value["state"] != "adopted":
            raise ReceiptError("adopted receipt central state is not adopted")
        _validate_evidence_commit(
            Path(central_map["candidate_worktree"]),
            evidence,
            evidence_commit,
            central_map["candidate_head"],
        )
    elif evidence is not None:
        raise ReceiptError("evidence metadata is only valid for adopted receipts")
    states = [central_value["state"]] + [item["state"] for item in verified_repositories if item["name"] != CENTRAL_NAME] + [item["state"] for item in verified_consumers]
    if _derive_global_state(states) != state:
        raise ReceiptError("receipt current state does not match repository states")
    return {
        **dict(document),
        "repository_map": {"path": str(map_path), "sha256": map_digest},
        "canonical_signing_source": {"path": str(source_path), "sha256": source["sha256"]},
    }


def validate_receipt(path: Path, *, evidence_commit: str | None = None) -> dict[str, Any]:
    """Validate one receipt and return its parsed document."""
    path = _canonical_path(path, "receipt")
    document = _read_json(path, "receipt")
    if not isinstance(document, Mapping):
        raise ReceiptError("receipt must be an object")
    return _validate_receipt_document(path, document, evidence_commit=evidence_commit)


@contextlib.contextmanager
def _receipt_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def write_atomic(path: Path, payload: bytes) -> None:
    """Write bytes with fsync/replace/fsync and preserve an existing mode."""
    if not isinstance(payload, bytes):
        raise TypeError("atomic payload must be bytes")
    path = Path(path)
    parent = _canonical_path(path.parent, "atomic target parent")
    if path != parent / path.name:
        raise ReceiptError("atomic target path must be canonical")
    if path.exists() or path.is_symlink():
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise ReceiptError("atomic target cannot be inspected") from exc
        if stat.S_ISLNK(mode):
            raise ReceiptError("atomic target must not be a symlink")
        if not stat.S_ISREG(mode):
            raise ReceiptError("atomic target must be a regular file")
        old_bytes = path.read_bytes()
        old_mode = stat.S_IMODE(mode)
    else:
        old_bytes = None
        old_mode = 0o600
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temporary = Path(temporary_name)
    replaced = False
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, old_mode)
        if _canonical_path(path.parent, "atomic target parent") != parent:
            raise ReceiptError("atomic target parent changed before replacement")
        if path.is_symlink():
            raise ReceiptError("atomic target must not be a symlink")
        os.replace(temporary, path)
        replaced = True
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if path.is_symlink() or path.read_bytes() != payload:
            raise ReceiptError("atomic write read-back mismatch")
    except Exception:
        if replaced and old_bytes is not None:
            rollback_descriptor, rollback_name = tempfile.mkstemp(prefix=f".{path.name}.rollback.", dir=path.parent)
            rollback = Path(rollback_name)
            try:
                os.fchmod(rollback_descriptor, old_mode)
                with os.fdopen(rollback_descriptor, "wb") as output:
                    output.write(old_bytes)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(rollback, path)
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if rollback.exists():
                    rollback.unlink()
        raise
    finally:
        if temporary.exists():
            temporary.unlink()


def transition_receipt(
    path: Path,
    *,
    repository: str,
    from_state: str,
    to_state: str,
    expected_head: str,
    expected_signing_sha256: str,
    evidence_commit: str | None = None,
) -> dict[str, Any]:
    """CAS-transition one repository/consumer and atomically persist it."""
    if from_state not in STATES or to_state not in STATES or to_state not in LEGAL_TRANSITIONS[from_state]:
        raise ReceiptError(f"illegal state transition {from_state}->{to_state}")
    expected_head = _require_commit(expected_head, "expected head")
    expected_signing_sha256 = _require_sha256(expected_signing_sha256, "expected signing")
    path = _canonical_path(path, "receipt")
    with _receipt_lock(path):
        current = validate_receipt(path)
        candidates = list(current["repositories"]) + list(current["consumers"])
        target = next((item for item in candidates if item.get("name") == repository), None)
        if target is None:
            raise ReceiptError(f"repository not found: {repository}")
        if target["state"] != from_state:
            raise ReceiptError(f"stale expected state for {repository}")
        if target["candidate_head"] != expected_head:
            raise ReceiptError(f"stale expected head for {repository}")
        if target["signing_sha256"] != expected_signing_sha256:
            raise ReceiptError(f"stale expected signing digest for {repository}")
        updated = json.loads(json.dumps(current))
        for collection in (updated["repositories"], updated["consumers"]):
            for item in collection:
                if item["name"] == repository:
                    item["state"] = to_state
        if repository == CENTRAL_NAME:
            updated["central"]["state"] = to_state
        states = [updated["central"]["state"]]
        states.extend(item["state"] for item in updated["repositories"] if item["name"] != CENTRAL_NAME)
        states.extend(item["state"] for item in updated["consumers"])
        updated["current_state"] = _derive_global_state(states)
        if to_state == "blocked":
            updated["failure_record"].append(
                {
                    "repository": repository,
                    "phase": "transition",
                    "reason": "explicitly blocked by compare-and-swap transition",
                    "output_sha256": sha256_bytes(b"blocked"),
                }
            )
        if to_state == "adopted" and updated["current_state"] == "adopted":
            if evidence_commit is None:
                raise ReceiptError("final adopted transition requires evidence commit")
            central_root = Path(updated["repositories"][0]["candidate_worktree"])
            parent = updated["central"]["candidate_head"]
            commit = _require_commit(evidence_commit, "evidence")
            if _git_commit_parents(central_root, commit) != [parent]:
                raise ReceiptError("evidence commit must have exactly the validated parent")
            changed = _git(
                central_root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                commit,
            ).splitlines()
            if changed != [EVIDENCE_RECEIPT_PATH]:
                raise ReceiptError("evidence commit path is not the sole allowlisted receipt")
            evidence_bytes = _git_bytes(
                central_root, "show", f"{commit}:{EVIDENCE_RECEIPT_PATH}"
            )
            updated["evidence_commit"] = {
                "parent": parent,
                "path": EVIDENCE_RECEIPT_PATH,
                "bytes_sha256": sha256_bytes(evidence_bytes),
            }
        _validate_receipt_document(path, updated, evidence_commit=evidence_commit)
        write_atomic(path, canonical_json_bytes(updated))
        return validate_receipt(path, evidence_commit=evidence_commit)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    validate = subparsers.add_parser("validate", help="validate a receipt")
    validate.add_argument("receipt_pos", nargs="?", type=Path)
    validate.add_argument("--receipt", dest="receipt_opt", type=Path)
    validate.add_argument("--evidence-commit")
    validate.add_argument("--allow-discovered", action="store_true")
    validate.add_argument("--allow-prepared", action="store_true")
    transition = subparsers.add_parser("transition", help="CAS transition a repository")
    transition.add_argument("--receipt", required=True, type=Path)
    transition.add_argument("--repository", required=True)
    transition.add_argument("--from-state", required=True)
    transition.add_argument("--to-state", required=True)
    transition.add_argument("--expected-head", required=True)
    transition.add_argument("--expected-signing-sha256", "--expected-signing-digest", dest="expected_signing_sha256", required=True)
    transition.add_argument("--evidence-commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] not in {"validate", "transition", "-h", "--help"}:
        raw.insert(0, "validate")
    args = _parser().parse_args(raw)
    try:
        if args.mode == "validate":
            path = args.receipt_opt or args.receipt_pos
            if path is None:
                raise ReceiptError("validate requires a receipt path")
            document = validate_receipt(path, evidence_commit=args.evidence_commit)
            allowed_states = {"validated", "adopted"}
            if args.allow_discovered:
                allowed_states.add("discovered")
            if args.allow_prepared:
                allowed_states.add("prepared")
            if document["current_state"] not in allowed_states:
                raise ReceiptError(
                    "receipt must be validated or adopted unless its current state "
                    "is explicitly allowed"
                )
            print(sha256_bytes(canonical_json_bytes(document)))
            return 0
        document = transition_receipt(
            args.receipt,
            repository=args.repository,
            from_state=args.from_state,
            to_state=args.to_state,
            expected_head=args.expected_head,
            expected_signing_sha256=args.expected_signing_sha256,
            evidence_commit=args.evidence_commit,
        )
        print(document["current_state"])
        return 0
    except (ReceiptError, OSError, ValueError) as exc:
        detail = _CATALOG_CANDIDATE.redact_diagnostic(exc, max_chars=500)
        print(f"error: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
