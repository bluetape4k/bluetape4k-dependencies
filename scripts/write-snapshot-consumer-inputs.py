#!/usr/bin/env python3
"""Create and validate the CI-to-Snapshot consumer commit contract.

The CI workflow validates a concrete checkout of every post-publish consumer.
This script records those immutable repository heads and the catalog refs used
by snapshot consumers. Publish Snapshot validates the artifact against its
triggering CI run before checking out any downstream repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "config" / "post-publish-next-development-line.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]*$")


class InputError(RuntimeError):
    """Raised when a manifest or checkout violates the immutable contract."""


def load_verifier() -> Any:
    module_path = REPO_ROOT / "scripts" / "verify-post-publish-next-development-line.py"
    spec = importlib.util.spec_from_file_location("post_publish_verifier", module_path)
    if spec is None or spec.loader is None:
        raise InputError(f"cannot load verifier: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise InputError(f"JSON document must be an object: {path}")
    return value


def load_policy(path: Path) -> tuple[dict[str, Any], Any]:
    verifier = load_verifier()
    document = load_json(path)
    try:
        verifier.validate_manifest(document)
    except (KeyError, TypeError, RuntimeError) as error:
        raise InputError(f"invalid post-publish policy: {error}") from error
    return document, verifier


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise InputError(
            f"git {' '.join(arguments)} failed in {repository}: "
            f"{detail or result.returncode}"
        )
    return result.stdout.strip()


def require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise InputError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def require_run_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not POSITIVE_INTEGER.fullmatch(value):
        raise InputError(f"{label} must be a positive decimal integer")
    return value


def required_repositories(policy: dict[str, Any], verifier: Any) -> list[str]:
    return verifier.required_workspace_repositories(policy)


def snapshot_repositories(policy: dict[str, Any], verifier: Any) -> set[str]:
    return set(verifier.snapshot_catalog_repositories(policy))


def inspect_repository(
    repository: Path,
    name: str,
    snapshot_names: set[str],
    verifier: Any,
) -> dict[str, str]:
    if not repository.is_dir():
        raise InputError(f"missing consumer checkout: {repository}")
    head = require_sha(run_git(repository, "rev-parse", "HEAD"), f"{name} HEAD")
    peeled = run_git(repository, "rev-parse", "--verify", f"{head}^{{commit}}")
    if peeled != head:
        raise InputError(f"{name} HEAD does not resolve to its recorded commit")
    if run_git(repository, "status", "--porcelain=v1", "--untracked-files=all"):
        raise InputError(f"{name} checkout is not clean")

    entry = {"commit": head}
    if name not in snapshot_names:
        return entry

    settings = repository / "settings.gradle.kts"
    workflow = repository / ".github" / "workflows" / "ci.yml"
    if not settings.is_file():
        raise InputError(f"missing snapshot consumer settings: {settings}")
    if not workflow.is_file():
        raise InputError(f"missing snapshot consumer CI workflow: {workflow}")
    catalog_ref = verifier.read_catalog_ref(settings)
    ci_catalog_ref = verifier.read_ci_catalog_ref(workflow)
    require_sha(catalog_ref, f"{name} settings catalog ref")
    require_sha(ci_catalog_ref, f"{name} CI catalog ref")
    if catalog_ref != ci_catalog_ref:
        raise InputError(
            f"{name} settings catalog ref {catalog_ref} must match CI catalog ref {ci_catalog_ref}"
        )
    entry["catalog-ref"] = catalog_ref
    entry["ci-catalog-ref"] = ci_catalog_ref
    return entry


def create_document(
    *,
    policy: dict[str, Any],
    workspace: Path,
    central_root: Path,
    source_commit: str,
    workflow_run_id: str,
    workflow_attempt: str,
    verifier: Any,
) -> dict[str, Any]:
    source_commit = require_sha(source_commit, "source commit")
    workflow_run_id = require_run_id(workflow_run_id, "workflow run id")
    workflow_attempt = require_run_id(workflow_attempt, "workflow attempt")
    actual_central_head = require_sha(
        run_git(central_root, "rev-parse", "HEAD"), "central checkout HEAD"
    )
    if actual_central_head != source_commit:
        raise InputError(
            f"central checkout HEAD {actual_central_head} must match source commit {source_commit}"
        )

    snapshot_names = snapshot_repositories(policy, verifier)
    repositories: dict[str, dict[str, str]] = {}
    for name in required_repositories(policy, verifier):
        repositories[name] = inspect_repository(
            workspace / name, name, snapshot_names, verifier
        )

    document: dict[str, Any] = {
        "schema-version": 1,
        "source": {
            "repository": "bluetape4k-dependencies",
            "commit": source_commit,
            "workflow-run-id": workflow_run_id,
            "workflow-attempt": workflow_attempt,
        },
        "repositories": repositories,
    }
    validate_document(document, policy, verifier)
    return document


def validate_document(
    document: dict[str, Any],
    policy: dict[str, Any],
    verifier: Any,
    *,
    expected_source_commit: str | None = None,
    expected_workflow_run_id: str | None = None,
    expected_workflow_attempt: str | None = None,
) -> None:
    if document.get("schema-version") != 1:
        raise InputError("unsupported snapshot consumer input schema")
    source = document.get("source")
    repositories = document.get("repositories")
    if not isinstance(source, dict):
        raise InputError("snapshot consumer input source is required")
    if set(source) != {
        "repository",
        "commit",
        "workflow-run-id",
        "workflow-attempt",
    }:
        raise InputError("snapshot consumer input source fields are invalid")
    if source["repository"] != "bluetape4k-dependencies":
        raise InputError("snapshot consumer input source repository is invalid")
    source_commit = require_sha(source["commit"], "snapshot source commit")
    workflow_run_id = require_run_id(source["workflow-run-id"], "snapshot workflow run id")
    require_run_id(source["workflow-attempt"], "snapshot workflow attempt")
    if expected_source_commit is not None:
        expected_source_commit = require_sha(expected_source_commit, "expected source commit")
        if source_commit != expected_source_commit:
            raise InputError(
                f"snapshot source commit {source_commit} must match expected CI head {expected_source_commit}"
            )
    if expected_workflow_run_id is not None:
        expected_workflow_run_id = require_run_id(
            expected_workflow_run_id, "expected workflow run id"
        )
        if workflow_run_id != expected_workflow_run_id:
            raise InputError(
                f"snapshot source workflow run {workflow_run_id} must match expected run {expected_workflow_run_id}"
            )
    if expected_workflow_attempt is not None:
        expected_workflow_attempt = require_run_id(
            expected_workflow_attempt, "expected workflow attempt"
        )
        if source["workflow-attempt"] != expected_workflow_attempt:
            raise InputError(
                "snapshot source workflow attempt "
                f"{source['workflow-attempt']} must match expected attempt "
                f"{expected_workflow_attempt}"
            )

    if not isinstance(repositories, dict):
        raise InputError("snapshot consumer input repositories are required")
    required = required_repositories(policy, verifier)
    if set(repositories) != set(required):
        missing = sorted(set(required) - set(repositories))
        extra = sorted(set(repositories) - set(required))
        raise InputError(
            "snapshot consumer input inventory mismatch: "
            f"missing={missing}, extra={extra}"
        )
    snapshot_names = snapshot_repositories(policy, verifier)
    for name in required:
        entry = repositories[name]
        if not isinstance(entry, dict):
            raise InputError(f"snapshot consumer input for {name} must be an object")
        expected_fields = {"commit"}
        if name in snapshot_names:
            expected_fields.update({"catalog-ref", "ci-catalog-ref"})
        if set(entry) != expected_fields:
            raise InputError(f"snapshot consumer input fields are invalid for {name}")
        require_sha(entry["commit"], f"{name} commit")
        if name in snapshot_names:
            catalog_ref = require_sha(entry["catalog-ref"], f"{name} catalog ref")
            ci_catalog_ref = require_sha(entry["ci-catalog-ref"], f"{name} CI catalog ref")
            if catalog_ref != ci_catalog_ref:
                raise InputError(
                    f"{name} manifest catalog ref {catalog_ref} must match CI catalog ref {ci_catalog_ref}"
                )


def read_source_commit(path: Path) -> str:
    document = load_json(path)
    if document.get("schema-version") != 1:
        raise InputError("unsupported snapshot consumer input schema")
    source = document.get("source")
    if not isinstance(source, dict):
        raise InputError("snapshot consumer input source is required")
    if source.get("repository") != "bluetape4k-dependencies":
        raise InputError("snapshot consumer input source repository is invalid")
    return require_sha(source.get("commit"), "snapshot source commit")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    write = subparsers.add_parser("write", help="write a CI consumer input manifest")
    write.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    write.add_argument("--workspace", type=Path, required=True)
    write.add_argument("--central-root", type=Path, default=REPO_ROOT)
    write.add_argument("--output", type=Path, required=True)
    write.add_argument("--source-commit", required=True)
    write.add_argument("--workflow-run-id", required=True)
    write.add_argument("--workflow-attempt", required=True)

    validate = subparsers.add_parser("validate", help="validate a consumer input manifest")
    validate.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--expected-source-commit")
    validate.add_argument("--expected-workflow-run-id")
    validate.add_argument("--expected-workflow-attempt")

    print_checkouts = subparsers.add_parser(
        "print-checkouts", help="print repository and commit pairs from a manifest"
    )
    print_checkouts.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    print_checkouts.add_argument("--manifest", type=Path, required=True)

    source_commit = subparsers.add_parser(
        "source-commit", help="print the source commit from a manifest"
    )
    source_commit.add_argument("--manifest", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "source-commit":
            print(read_source_commit(args.manifest))
            return 0

        policy, verifier = load_policy(args.policy)
        if args.command == "write":
            document = create_document(
                policy=policy,
                workspace=args.workspace.resolve(),
                central_root=args.central_root.resolve(),
                source_commit=args.source_commit,
                workflow_run_id=args.workflow_run_id,
                workflow_attempt=args.workflow_attempt,
                verifier=verifier,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            print(args.output)
            return 0

        document = load_json(args.manifest)
        validate_document(
            document,
            policy,
            verifier,
            expected_source_commit=getattr(args, "expected_source_commit", None),
            expected_workflow_run_id=getattr(args, "expected_workflow_run_id", None),
            expected_workflow_attempt=getattr(args, "expected_workflow_attempt", None),
        )
        if args.command == "validate":
            print("Snapshot consumer input manifest is valid.")
            return 0
        for name in required_repositories(policy, verifier):
            print(f"{name}\t{document['repositories'][name]['commit']}")
        return 0
    except (InputError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
