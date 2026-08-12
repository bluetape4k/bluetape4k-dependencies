#!/usr/bin/env python3
"""Fail closed when the post-publish development line is incomplete.

The stable release workflow cannot mutate ``develop`` safely.  This guard makes
the follow-up explicit instead: the next ``baseVersion`` stays in source,
``snapshotVersion`` stays empty, and every published child BOM is referenced
with the runtime ``-SNAPSHOT`` suffix only after its snapshot metadata exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "config" / "post-publish-next-development-line.json"
SNAPSHOT_REPOSITORY = "https://central.sonatype.com/repository/maven-snapshots"
VERSION_LINE = re.compile(r"^([A-Za-z0-9_.-]+)\s*=\s*\"([^\"]+)\"")
PROPERTY_LINE = re.compile(r"^([A-Za-z0-9_.-]+)\s*=\s*(.*)$")
REPOSITORY_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
CATALOG_REF = re.compile(r'\.orElse\("([0-9a-f]{40})"\)')
CI_CATALOG_REF = re.compile(
    r"^\s*BLUETAPE4K_DEPENDENCIES_CATALOG_REF:\s*['\"]?([0-9a-f]{40})['\"]?\s*$",
    re.MULTILINE,
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read manifest {path}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError("next-development manifest must be a JSON object")
    return value


def validate_manifest(document: dict[str, Any]) -> None:
    if document.get("schema-version") != 2:
        raise RuntimeError("unsupported next-development manifest schema")
    if document.get("status") != "active":
        raise RuntimeError("next-development manifest must be active")
    stable = document.get("stable-version")
    development = document.get("development-version")
    suffix = document.get("snapshot-suffix")
    source_contract = document.get("source-contract")
    publishers = document.get("publishable-repositories")
    consumer_policy = document.get("consumer-policy")
    if not isinstance(stable, str) or not SEMVER.fullmatch(stable):
        raise RuntimeError("stable-version must be a stable semantic version")
    if not isinstance(development, str) or not SEMVER.fullmatch(development):
        raise RuntimeError("development-version must be a stable semantic version")
    if not isinstance(suffix, str) or suffix != "-SNAPSHOT":
        raise RuntimeError("snapshot-suffix must be -SNAPSHOT")
    if not isinstance(source_contract, dict):
        raise RuntimeError("source-contract is required")
    if source_contract.get("snapshotVersion") != "":
        raise RuntimeError("source snapshotVersion contract must be empty")
    if source_contract.get("runtime-property") != "-PsnapshotVersion=-SNAPSHOT":
        raise RuntimeError("runtime snapshot property contract is invalid")
    if not isinstance(publishers, list) or not publishers:
        raise RuntimeError("publishable-repositories must be a non-empty list")
    if not isinstance(consumer_policy, dict):
        raise RuntimeError("consumer-policy is required")

    repositories: set[str] = set()
    aliases: set[str] = set()
    for item in publishers:
        if not isinstance(item, dict):
            raise RuntimeError("publisher entries must be objects")
        required = {"repository", "catalog-alias", "group", "artifact", "base-version"}
        if set(item) != required:
            raise RuntimeError(f"publisher entry fields must be {sorted(required)}")
        repository = item["repository"]
        alias = item["catalog-alias"]
        base_version = item["base-version"]
        if not isinstance(repository, str) or not REPOSITORY_NAME.fullmatch(repository):
            raise RuntimeError(f"invalid publisher repository: {repository!r}")
        if not isinstance(alias, str) or not alias:
            raise RuntimeError("publisher catalog-alias must be non-empty")
        if not isinstance(base_version, str) or not SEMVER.fullmatch(base_version):
            raise RuntimeError(f"invalid publisher base-version: {base_version!r}")
        if repository in repositories:
            raise RuntimeError(f"duplicate publisher repository: {repository}")
        if alias in aliases:
            raise RuntimeError(f"duplicate publisher catalog alias: {alias}")
        repositories.add(repository)
        aliases.add(alias)

    required_policy_fields = {
        "snapshot-catalog-ref",
        "snapshot-catalog-repositories",
        "official-release-repositories",
    }
    if set(consumer_policy) != required_policy_fields:
        raise RuntimeError(f"consumer-policy fields must be {sorted(required_policy_fields)}")
    snapshot_ref = consumer_policy["snapshot-catalog-ref"]
    snapshot_repositories = consumer_policy["snapshot-catalog-repositories"]
    official_repositories = consumer_policy["official-release-repositories"]
    if not isinstance(snapshot_ref, str) or not GIT_SHA.fullmatch(snapshot_ref):
        raise RuntimeError("snapshot-catalog-ref must be an immutable Git commit SHA")
    if not isinstance(snapshot_repositories, list) or not snapshot_repositories:
        raise RuntimeError("snapshot-catalog-repositories must be a non-empty list")
    if not all(
        isinstance(repository, str) and REPOSITORY_NAME.fullmatch(repository)
        for repository in snapshot_repositories
    ):
        raise RuntimeError("snapshot-catalog-repositories contains an invalid repository")
    if len(snapshot_repositories) != len(set(snapshot_repositories)):
        raise RuntimeError("snapshot-catalog-repositories contains duplicates")
    if not repositories.issubset(snapshot_repositories):
        raise RuntimeError("every publishable repository must be a snapshot catalog consumer")
    if not isinstance(official_repositories, list) or not official_repositories:
        raise RuntimeError("official-release-repositories must be a non-empty list")

    official_names: set[str] = set()
    for item in official_repositories:
        if not isinstance(item, dict):
            raise RuntimeError("official release consumer entries must be objects")
        required = {"repository", "catalog-version-key"}
        if set(item) != required:
            raise RuntimeError(f"official release consumer fields must be {sorted(required)}")
        repository = item["repository"]
        version_key = item["catalog-version-key"]
        if not isinstance(repository, str) or not REPOSITORY_NAME.fullmatch(repository):
            raise RuntimeError(f"invalid official release consumer: {repository!r}")
        if not isinstance(version_key, str) or not version_key:
            raise RuntimeError("official release catalog-version-key must be non-empty")
        if repository in official_names:
            raise RuntimeError(f"duplicate official release consumer: {repository}")
        official_names.add(repository)
    if set(snapshot_repositories).intersection(official_names):
        raise RuntimeError("a repository cannot consume both snapshot and official release catalogs")


def read_properties(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PROPERTY_LINE.fullmatch(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def read_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    in_versions = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            in_versions = line == "[versions]"
            continue
        if not in_versions or not line or line.startswith("#"):
            continue
        match = VERSION_LINE.match(line)
        if match:
            versions[match.group(1)] = match.group(2)
    return versions


def read_catalog_ref(path: Path) -> str | None:
    match = CATALOG_REF.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def read_ci_catalog_ref(path: Path) -> str | None:
    match = CI_CATALOG_REF.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def required_workspace_repositories(manifest: dict[str, Any]) -> list[str]:
    policy = manifest["consumer-policy"]
    repositories = list(policy["snapshot-catalog-repositories"])
    repositories.extend(item["repository"] for item in policy["official-release-repositories"])
    return repositories


def snapshot_candidate_branch(manifest: dict[str, Any]) -> str:
    snapshot_ref = manifest["consumer-policy"]["snapshot-catalog-ref"]
    return f"chore/snapshot-catalog-{snapshot_ref[:7]}"


def verify_consumer_policy(workspace: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = manifest["consumer-policy"]
    expected_snapshot_ref = policy["snapshot-catalog-ref"]
    stable_version = manifest["stable-version"]

    for repository in policy["snapshot-catalog-repositories"]:
        settings = workspace / repository / "settings.gradle.kts"
        ci_workflow = workspace / repository / ".github" / "workflows" / "ci.yml"
        if not settings.is_file():
            errors.append(f"missing snapshot consumer settings: {settings}")
            continue
        try:
            catalog_ref = read_catalog_ref(settings)
        except OSError as error:
            errors.append(f"cannot read {settings}: {error}")
            continue
        if catalog_ref != expected_snapshot_ref:
            errors.append(
                f"{repository} must use snapshot catalog ref {expected_snapshot_ref}, "
                f"got {catalog_ref!r}"
            )
        if not ci_workflow.is_file():
            errors.append(f"missing snapshot consumer CI workflow: {ci_workflow}")
            continue
        try:
            ci_catalog_ref = read_ci_catalog_ref(ci_workflow)
        except OSError as error:
            errors.append(f"cannot read {ci_workflow}: {error}")
            continue
        if ci_catalog_ref != expected_snapshot_ref:
            errors.append(
                f"{repository} CI must use snapshot catalog ref {expected_snapshot_ref}, "
                f"got {ci_catalog_ref!r}"
            )

    for item in policy["official-release-repositories"]:
        repository = item["repository"]
        version_key = item["catalog-version-key"]
        catalog = workspace / repository / "gradle" / "libs.versions.toml"
        if not catalog.is_file():
            errors.append(f"missing official release consumer catalog: {catalog}")
            continue
        try:
            versions = read_versions(catalog)
        except OSError as error:
            errors.append(f"cannot read {catalog}: {error}")
            continue
        actual = versions.get(version_key)
        if actual != stable_version:
            errors.append(
                f"{repository} must use official bluetape4k-dependencies "
                f"{stable_version}, got {actual!r}"
            )
    return errors


def metadata_url(group: str, artifact: str, version: str) -> str:
    return (
        f"{SNAPSHOT_REPOSITORY}/{group.replace('.', '/')}/{artifact}/{version}/"
        "maven-metadata.xml"
    )


def metadata_exists(
    group: str,
    artifact: str,
    version: str,
    *,
    attempts: int = 2,
    delay_seconds: float = 0.2,
) -> tuple[bool, str]:
    url = metadata_url(group, artifact, version)
    status = "unknown"
    for attempt in range(max(1, attempts)):
        request = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return 200 <= response.status < 400, str(response.status)
        except urllib.error.HTTPError as error:
            status = str(error.code)
            if error.code == 405:
                try:
                    with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as response:
                        return 200 <= response.status < 400, str(response.status)
                except urllib.error.HTTPError as fallback:
                    status = str(fallback.code)
            if status != "403" or attempt + 1 >= max(1, attempts):
                return False, status
        except (urllib.error.URLError, TimeoutError) as error:
            return False, type(error).__name__
        time.sleep(max(0.0, delay_seconds))
    return False, status


def verify_development(
    central_root: Path,
    workspace: Path,
    manifest: dict[str, Any],
    require_artifacts: bool,
) -> list[str]:
    errors: list[str] = []
    stable_version = manifest["stable-version"]
    development_version = manifest["development-version"]
    suffix = manifest["snapshot-suffix"]
    source_contract = manifest["source-contract"]
    properties_path = central_root / "gradle.properties"
    catalog_path = central_root / "gradle" / "libs.versions.toml"
    try:
        properties = read_properties(properties_path)
        versions = read_versions(catalog_path)
    except OSError as error:
        return [f"central source is unreadable: {error}"]

    if properties.get("baseVersion") != development_version:
        errors.append(
            f"central baseVersion must be {development_version}, got {properties.get('baseVersion')!r}"
        )
    if properties.get("snapshotVersion") != source_contract["snapshotVersion"]:
        errors.append("central snapshotVersion must remain empty in source")
    if versions.get("bluetape4k-dependencies") != development_version:
        errors.append("catalog self version must equal the development baseVersion")
    if stable_version == development_version:
        errors.append("stable-version and development-version must differ")
    errors.extend(verify_consumer_policy(workspace, manifest))

    expected_development_version = f"{development_version}{suffix}"
    for item in manifest["publishable-repositories"]:
        repository = item["repository"]
        alias = item["catalog-alias"]
        base_version = item["base-version"]
        expected_snapshot = f"{base_version}{suffix}"
        if versions.get(alias) != expected_snapshot:
            errors.append(
                f"catalog {alias} must reference {expected_snapshot}, got {versions.get(alias)!r}"
            )
        repo_root = workspace / repository
        repo_properties = repo_root / "gradle.properties"
        workflow = repo_root / ".github" / "workflows" / "publish-snapshot.yml"
        release_workflow = repo_root / ".github" / "workflows" / "release.yml"
        if not repo_properties.is_file():
            errors.append(f"missing publisher properties: {repo_properties}")
            continue
        try:
            child_properties = read_properties(repo_properties)
        except OSError as error:
            errors.append(f"cannot read {repo_properties}: {error}")
            continue
        if child_properties.get("baseVersion") != base_version:
            errors.append(
                f"{repository} baseVersion must be {base_version}, got {child_properties.get('baseVersion')!r}"
            )
        if child_properties.get("snapshotVersion") != source_contract["snapshotVersion"]:
            errors.append(f"{repository} snapshotVersion must remain empty in source")
        if not workflow.is_file():
            errors.append(f"missing snapshot workflow: {workflow}")
        else:
            text = workflow.read_text(encoding="utf-8")
            if source_contract["runtime-property"] not in text:
                errors.append(f"{repository} snapshot workflow does not inject -SNAPSHOT at runtime")
            if not re.search(r"JAVA_VERSION:\s*['\"]25['\"]", text):
                errors.append(f"{repository} snapshot workflow must use JDK 25")
        if not release_workflow.is_file():
            errors.append(f"missing release workflow: {release_workflow}")
        else:
            text = release_workflow.read_text(encoding="utf-8")
            if "snapshotVersion must be empty for release" not in text:
                errors.append(f"{repository} release workflow lacks the stable snapshot guard")
        if require_artifacts:
            exists, status = metadata_exists(item["group"], item["artifact"], expected_snapshot)
            if not exists:
                errors.append(
                    f"missing snapshot metadata ({status}): {item['group']}:{item['artifact']}:{expected_snapshot}"
                )

    if require_artifacts:
        exists, status = metadata_exists(
            "io.github.bluetape4k", "bluetape4k-dependencies", expected_development_version
        )
        if not exists:
            errors.append(f"missing central snapshot metadata ({status}): {expected_development_version}")
    return errors


def verify_stable(central_root: Path, manifest: dict[str, Any], version: str) -> list[str]:
    errors: list[str] = []
    properties = read_properties(central_root / "gradle.properties")
    versions = read_versions(central_root / "gradle" / "libs.versions.toml")
    if properties.get("baseVersion") != version:
        errors.append(f"central baseVersion must match stable tag {version}")
    if properties.get("snapshotVersion") != "":
        errors.append("snapshotVersion must be empty for stable publication")
    if versions.get("bluetape4k-dependencies") != version:
        errors.append("catalog self version must match the stable tag")
    for item in manifest["publishable-repositories"]:
        value = versions.get(item["catalog-alias"])
        if value is None:
            errors.append(f"catalog alias is missing: {item['catalog-alias']}")
        elif value.endswith(manifest["snapshot-suffix"]):
            errors.append(f"stable catalog cannot reference a snapshot: {item['catalog-alias']}={value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT.parent)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--require-artifacts", action="store_true")
    parser.add_argument("--stable-release", metavar="VERSION")
    parser.add_argument("--print-required-repositories", action="store_true")
    parser.add_argument("--print-snapshot-candidate-branch", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    try:
        manifest = load_json(args.manifest)
        validate_manifest(manifest)
        if args.print_required_repositories:
            for repository in required_workspace_repositories(manifest):
                print(repository)
            return 0
        if args.print_snapshot_candidate_branch:
            print(snapshot_candidate_branch(manifest))
            return 0
        if args.stable_release:
            errors = verify_stable(REPO_ROOT, manifest, args.stable_release)
            mode = f"stable release {args.stable_release}"
        else:
            errors = verify_development(REPO_ROOT, args.workspace.resolve(), manifest, args.require_artifacts)
            mode = "post-publish development line"
    except (OSError, RuntimeError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.summary:
        print(f"Verified {mode}: {len(manifest['publishable-repositories'])} publishers")
        if not args.stable_release:
            policy = manifest["consumer-policy"]
            print(
                "Verified consumer boundary: "
                f"{len(policy['snapshot-catalog-repositories'])} snapshot libraries, "
                f"{len(policy['official-release-repositories'])} official-release examples"
            )
        if args.require_artifacts and not args.stable_release:
            print("Verified snapshot metadata for the central BOM and all child BOMs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
