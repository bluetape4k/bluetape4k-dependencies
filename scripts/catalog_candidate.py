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
import stat
import subprocess
import tempfile
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
TOP_LEVEL_FIELDS = frozenset({"schema_version", "central", "repositories"})
REPOSITORY_FIELDS = frozenset(
    {"root", "catalog", "origin", "branch", "base_sha", "expected_head", "clean"}
)
GIT_OBJECT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot inspect git worktree: {root}") from exc


def _approved_origin(key: str) -> str:
    return f"git@github.com:bluetape4k/{REPOSITORY_NAMES[key]}.git"


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
