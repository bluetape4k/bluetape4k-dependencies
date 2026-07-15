#!/usr/bin/env python3
"""Check central catalog adoption across governed sibling repositories.

`gradle/libs.versions.toml` in this repository is the source of truth for
organization-wide versions, shared libraries, and Gradle plugins. Downstream
repositories should use the imported `bt4k` catalog directly or keep
versionless local aliases whose versions are supplied from the central catalog.
The checker reports duplicate local authority and never rewrites downstream
catalogs.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_START = "# <shared-version-source-of-truth by scripts/sync-shared-versions.py>"
SOURCE_END = "# </shared-version-source-of-truth>"
SELF_ALIAS = "bluetape4k-dependencies"
VERSION_LINE = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"(?P<suffix>.*)$')
INLINE_VERSION_LINE = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*\{.*\bversion\s*=\s*"([^"]+)".*\}\s*(?:#.*)?$')

DEFAULT_REPOSITORIES = (
    "bluetape4k-projects",
    "bluetape4k-experimental",
    "bluetape4k-aws",
    "bluetape4k-exposed",
    "bluetape4k-graph",
    "bluetape4k-image",
    "bluetape4k-javers",
    "bluetape4k-leader",
    "bluetape4k-text",
)

EXAMPLE_REPOSITORIES = (
    "bluetape4k-workshop",
    "clinic-appointment",
    "exposed-r2dbc-workshop",
    "exposed-workshop",
    "timefold-workshop",
)

COMPATIBILITY_MAJOR_LINES = {
    "ignite": "2",
    "ignite3": "3",
    "jackson2": "2",
    "jackson3": "3",
    "kafka3": "3",
    "kafka4": "4",
    "spring-boot3": "3",
    "spring-boot4": "4",
    "spring-kafka": "3",
    "spring-kafka4": "4",
}


@dataclasses.dataclass(frozen=True)
class SourceVersion:
    alias: str
    version: str
    line: str
    module_groups: frozenset[str] = frozenset()


@dataclasses.dataclass(frozen=True)
class Change:
    repo: str
    alias: str
    before: str
    after: str


@dataclasses.dataclass(frozen=True)
class CompatibilityError:
    repo: str
    alias: str
    version: str
    expected_major: str
    catalog: Path


@dataclasses.dataclass(frozen=True)
class CatalogLibrary:
    alias: str
    module: str
    version_ref: str | None
    version: str | None = None


@dataclasses.dataclass(frozen=True)
class CatalogPlugin:
    alias: str
    plugin_id: str
    version_ref: str | None
    version: str | None = None


@dataclasses.dataclass(frozen=True)
class CatalogData:
    path: Path
    versions: dict[str, str]
    libraries: dict[str, CatalogLibrary]
    plugins: dict[str, CatalogPlugin]


@dataclasses.dataclass(frozen=True)
class CatalogException:
    repository: str
    key: str
    central_key: str
    kind: str
    coordinate: str
    expected_local_version: str
    compatibility_family: str
    reason: str
    issue: str
    owner: str
    introduced: date
    review_by: date
    resolution_condition: str


@dataclasses.dataclass(frozen=True)
class AdoptionGap:
    repository: str
    kind: str
    key: str
    local: str
    central: str


@dataclasses.dataclass(frozen=True)
class RepositoryTarget:
    repository: str
    catalog: Path
    branch: str
    expected_head: str


EXCEPTION_FIELDS = frozenset(
    {
        "repository",
        "key",
        "central-key",
        "kind",
        "coordinate",
        "expected-local-version",
        "compatibility-family",
        "reason",
        "issue",
        "owner",
        "introduced",
        "review-by",
        "resolution-condition",
    },
)
REPOSITORY_TARGET_FIELDS = frozenset({"catalog", "branch", "expected_head"})
EXCEPTION_KINDS = frozenset({"version", "library-version", "library-identity", "plugin-version", "plugin-identity"})
ISSUE_URL = re.compile(r"^https://github\.com/bluetape4k/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)$")
GIT_HEAD = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
STRING_ASSIGNMENT = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"\s*(?:#.*)?$')
SETTINGS_CATALOG_REF = re.compile(r'\.orElse\("([0-9a-f]{40}|[0-9a-f]{64})"\)')
WORKFLOW_CATALOG_REF = re.compile(
    r'^\s*BLUETAPE4K_DEPENDENCIES_CATALOG_REF:\s*[\'\"]?([0-9a-f]{40}|[0-9a-f]{64})[\'\"]?\s*$',
    re.MULTILINE,
)


def _inline_string(value: str, field: str) -> str | None:
    match = re.search(rf'\b{re.escape(field)}\s*=\s*"([^"]+)"', value)
    return match.group(1) if match else None


def read_catalog(catalog: Path) -> CatalogData:
    try:
        lines = catalog.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"invalid version catalog: {catalog}") from exc
    versions: dict[str, str] = {}
    libraries: dict[str, CatalogLibrary] = {}
    plugins: dict[str, CatalogPlugin] = {}
    section = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "versions":
            match = VERSION_LINE.match(stripped)
            if match:
                versions[match.group(1)] = match.group(2)
            continue
        alias_match = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*\{(.*)\}\s*(?:#.*)?$", stripped)
        if alias_match is None:
            continue
        alias, value = alias_match.groups()
        version_ref = _inline_string(value, "version.ref")
        version = _inline_string(value, "version")
        if section == "libraries":
            module = _inline_string(value, "module")
            if module is None:
                group = _inline_string(value, "group")
                name = _inline_string(value, "name")
                module = f"{group}:{name}" if group and name else None
            if module:
                libraries[alias] = CatalogLibrary(alias, module, version_ref, version)
        elif section == "plugins":
            plugin_id = _inline_string(value, "id")
            if plugin_id:
                plugins[alias] = CatalogPlugin(alias, plugin_id, version_ref, version)

    return CatalogData(catalog, versions, libraries, plugins)


def _parse_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise RuntimeError(f"exception {field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"exception {field} must be an ISO date") from exc


def load_exceptions(path: Path, *, today: date | None = None) -> tuple[CatalogException, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"invalid exception file: {path}") from exc
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "exception = []":
            if current is not None or entries:
                raise RuntimeError("exception file mixes empty and table forms")
            continue
        if stripped == "[[exception]]":
            current = {}
            entries.append(current)
            continue
        if current is None:
            raise RuntimeError("exception file has unknown top-level fields")
        match = STRING_ASSIGNMENT.fullmatch(stripped)
        if match is None:
            raise RuntimeError("exception field must be a quoted string")
        key, value = match.groups()
        if key in current:
            raise RuntimeError(f"duplicate exception field: {key}")
        current[key] = value

    observed = today or date.today()
    exceptions: list[CatalogException] = []
    identities: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("exception entry must be a table")
        unknown = set(entry) - EXCEPTION_FIELDS
        missing = EXCEPTION_FIELDS - set(entry)
        if unknown:
            raise RuntimeError(f"exception has unknown fields: {', '.join(sorted(unknown))}")
        if missing:
            raise RuntimeError(f"exception is missing fields: {', '.join(sorted(missing))}")
        for field in EXCEPTION_FIELDS - {"introduced", "review-by"}:
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise RuntimeError(f"exception {field} must be non-empty")
        if entry["kind"] not in EXCEPTION_KINDS:
            raise RuntimeError(f"exception kind must be one of: {', '.join(sorted(EXCEPTION_KINDS))}")
        repository = entry["repository"]
        issue_match = ISSUE_URL.fullmatch(entry["issue"])
        if issue_match is None or issue_match.group(1) != repository:
            raise RuntimeError("exception issue must be a canonical same-repository bluetape4k issue URL")
        introduced = _parse_date(entry["introduced"], "introduced")
        review_by = _parse_date(entry["review-by"], "review-by")
        if review_by < introduced:
            raise RuntimeError("exception review-by precedes introduced")
        if review_by < observed:
            raise RuntimeError(f"exception expired on {review_by.isoformat()}")
        identity = (repository, entry["key"])
        if identity in identities:
            raise RuntimeError(f"duplicate exception: {repository}/{entry['key']}")
        identities.add(identity)
        exceptions.append(
            CatalogException(
                repository=repository,
                key=entry["key"],
                central_key=entry["central-key"],
                kind=entry["kind"],
                coordinate=entry["coordinate"],
                expected_local_version=entry["expected-local-version"],
                compatibility_family=entry["compatibility-family"],
                reason=entry["reason"],
                issue=entry["issue"],
                owner=entry["owner"],
                introduced=introduced,
                review_by=review_by,
                resolution_condition=entry["resolution-condition"],
            ),
        )
    return tuple(exceptions)


def _is_excepted(
    repository: str,
    local_key: str,
    central_key: str,
    kind: str,
    coordinate: str,
    local_version: str,
    compatibility_family: str,
    exceptions: tuple[CatalogException, ...],
) -> bool:
    return any(
        exception.repository == repository
        and exception.key == local_key
        and exception.central_key == central_key
        and exception.kind == kind
        and exception.coordinate == coordinate
        and exception.expected_local_version == local_version
        and exception.compatibility_family == compatibility_family
        for exception in exceptions
    )


def _resolved_local_version(
    version_ref: str | None,
    inline_version: str | None,
    versions: dict[str, str],
) -> str:
    if inline_version is not None:
        return inline_version
    return versions.get(version_ref or "", "")


def find_adoption_gaps(
    repository: str,
    local: CatalogData,
    central: CatalogData,
    exceptions: tuple[CatalogException, ...],
) -> list[AdoptionGap]:
    gaps: list[AdoptionGap] = []
    for key, value in local.versions.items():
        if key in central.versions and not _is_excepted(
            repository,
            key,
            key,
            "version",
            key,
            value,
            key,
            exceptions,
        ):
            gaps.append(AdoptionGap(repository, "version-duplicate", key, value, central.versions[key]))

    central_library_by_module = {library.module: library for library in central.libraries.values()}
    for alias, library in local.libraries.items():
        central_same_alias = central.libraries.get(alias)
        if central_same_alias is not None and central_same_alias.module != library.module:
            if not _is_excepted(
                repository,
                alias,
                alias,
                "library-identity",
                library.module,
                _resolved_local_version(library.version_ref, library.version, local.versions),
                library.version_ref or alias,
                exceptions,
            ):
                gaps.append(
                    AdoptionGap(repository, "library-identity-conflict", alias, library.module, central_same_alias.module),
                )
            continue
        central_same_module = central_library_by_module.get(library.module)
        if (
            central_same_module is not None
            and (library.version_ref is not None or library.version is not None)
            and not _is_excepted(
                repository,
                alias,
                central_same_module.alias,
                "library-version",
                library.module,
                _resolved_local_version(library.version_ref, library.version, local.versions),
                library.version_ref or alias,
                exceptions,
            )
        ):
            gaps.append(
                AdoptionGap(
                    repository,
                    "library-coordinate-duplicate",
                    alias,
                    library.module,
                    central_same_module.alias,
                ),
            )

    central_plugin_by_id = {plugin.plugin_id: plugin for plugin in central.plugins.values()}
    for alias, plugin in local.plugins.items():
        central_same_alias = central.plugins.get(alias)
        if central_same_alias is not None and central_same_alias.plugin_id != plugin.plugin_id:
            if not _is_excepted(
                repository,
                alias,
                alias,
                "plugin-identity",
                plugin.plugin_id,
                _resolved_local_version(plugin.version_ref, plugin.version, local.versions),
                plugin.version_ref or alias,
                exceptions,
            ):
                gaps.append(
                    AdoptionGap(repository, "plugin-identity-conflict", alias, plugin.plugin_id, central_same_alias.plugin_id),
                )
            continue
        central_same_id = central_plugin_by_id.get(plugin.plugin_id)
        if (
            central_same_id is not None
            and (plugin.version_ref is not None or plugin.version is not None)
            and not _is_excepted(
                repository,
                alias,
                central_same_id.alias,
                "plugin-version",
                plugin.plugin_id,
                _resolved_local_version(plugin.version_ref, plugin.version, local.versions),
                plugin.version_ref or alias,
                exceptions,
            )
        ):
            gaps.append(
                AdoptionGap(repository, "plugin-id-duplicate", alias, plugin.plugin_id, central_same_id.alias),
            )
    return gaps


def find_catalog_ref_gaps(repository: str, catalog: Path) -> list[AdoptionGap]:
    """Report when local Gradle and CI resolve different central catalog commits."""
    repository_root = catalog.parents[1]
    settings_path = repository_root / "settings.gradle.kts"
    workflow_path = repository_root / ".github" / "workflows" / "ci.yml"

    settings_text = settings_path.read_text(encoding="utf-8") if settings_path.is_file() else ""
    workflow_text = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    settings_match = SETTINGS_CATALOG_REF.search(settings_text)
    workflow_match = WORKFLOW_CATALOG_REF.search(workflow_text)
    settings_ref = settings_match.group(1) if settings_match else "<missing>"
    workflow_ref = workflow_match.group(1) if workflow_match else "<missing>"

    if settings_ref == workflow_ref and settings_ref != "<missing>":
        return []
    return [
        AdoptionGap(
            repository,
            "catalog-ref-mismatch",
            "BLUETAPE4K_DEPENDENCIES_CATALOG_REF",
            settings_ref,
            workflow_ref,
        ),
    ]


def load_repository_map(
    path: Path,
    workspace: Path,
    allowed_repositories: tuple[str, ...],
) -> dict[str, RepositoryTarget]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("repository map must be a regular non-symlink file")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid repository map") from exc
    if not isinstance(document, dict):
        raise RuntimeError("repository map must be an object")

    workspace_root = workspace.resolve()
    allowed = set(allowed_repositories)
    targets: dict[str, RepositoryTarget] = {}
    for repository, entry in document.items():
        if repository not in allowed:
            raise RuntimeError(f"repository map contains non-managed repository: {repository}")
        if not isinstance(entry, dict) or set(entry) != REPOSITORY_TARGET_FIELDS:
            raise RuntimeError(f"repository map fields are invalid for {repository}")
        catalog = Path(entry["catalog"])
        if not catalog.is_absolute():
            raise RuntimeError(f"catalog path must be absolute for {repository}")
        if catalog.is_symlink():
            raise RuntimeError(f"catalog path must not be a symlink for {repository}")
        resolved_catalog = catalog.resolve()
        if not resolved_catalog.is_relative_to(workspace_root):
            raise RuntimeError(f"catalog path must stay inside workspace for {repository}")
        if not resolved_catalog.is_file():
            raise RuntimeError(f"catalog path is not a regular file for {repository}")
        branch = entry["branch"]
        expected_head = entry["expected_head"]
        if not isinstance(branch, str) or not branch.strip():
            raise RuntimeError(f"branch must be non-empty for {repository}")
        if not isinstance(expected_head, str) or GIT_HEAD.fullmatch(expected_head) is None:
            raise RuntimeError(f"expected_head is invalid for {repository}")
        try:
            actual_branch = subprocess.run(
                ["git", "-C", str(resolved_catalog.parent), "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            actual_head = subprocess.run(
                ["git", "-C", str(resolved_catalog.parent), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(f"catalog is not inside a readable git worktree for {repository}") from exc
        if actual_branch != branch:
            raise RuntimeError(
                f"repository map branch mismatch for {repository}: expected {branch}, found {actual_branch or 'detached HEAD'}",
            )
        if actual_head != expected_head:
            raise RuntimeError(
                f"repository map HEAD mismatch for {repository}: expected {expected_head}, found {actual_head}",
            )
        targets[repository] = RepositoryTarget(repository, resolved_catalog, branch, expected_head)
    return targets


def read_source_versions(catalog: Path) -> dict[str, SourceVersion]:
    text = catalog.read_text(encoding="utf-8")
    module_groups = module_groups_by_version_ref(text)
    try:
        block = text.split(SOURCE_START, 1)[1].split(SOURCE_END, 1)[0]
    except IndexError as exc:
        raise RuntimeError(f"{catalog} is missing source-of-truth markers") from exc

    versions: dict[str, SourceVersion] = {}
    for raw_line in block.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = VERSION_LINE.match(stripped)
        if not match:
            continue
        alias = match.group(1)
        versions[alias] = SourceVersion(
            alias=alias,
            version=match.group(2),
            line=stripped,
            module_groups=source_module_groups(alias, stripped, module_groups),
        )
    return versions


def compatibility_line_errors(catalog: Path, repo: str) -> list[CompatibilityError]:
    errors: list[CompatibilityError] = []
    in_versions = False

    for raw_line in catalog.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_versions = stripped == "[versions]"
            continue
        if not in_versions:
            continue

        match = VERSION_LINE.match(stripped)
        if not match:
            continue

        alias = match.group(1)
        expected_major = COMPATIBILITY_MAJOR_LINES.get(alias)
        if expected_major is None:
            continue

        version = match.group(2)
        if not version.startswith(f"{expected_major}."):
            errors.append(
                CompatibilityError(
                    repo=repo,
                    alias=alias,
                    version=version,
                    expected_major=expected_major,
                    catalog=catalog,
                ),
            )
    return errors


def source_module_groups(
    alias: str,
    source_line: str,
    module_groups: dict[str, frozenset[str]],
) -> frozenset[str]:
    groups = set(module_groups.get(alias, frozenset()))
    metadata_group = mavenrepository_group(source_line)
    if metadata_group is not None:
        groups.add(metadata_group)
    return frozenset(groups)


def mavenrepository_group(text: str) -> str | None:
    match = re.search(r"mvnrepository\.com/artifact/([^/\s]+)/", text)
    return match.group(1) if match else None


def module_groups_by_version_ref(text: str) -> dict[str, frozenset[str]]:
    groups: dict[str, set[str]] = {}
    pattern = re.compile(
        r'\bmodule\s*=\s*"(?P<group>[^":]+):[^"]+".*?\bversion\.ref\s*=\s*"(?P<alias>[^"]+)"',
    )
    for match in pattern.finditer(text):
        groups.setdefault(match.group("alias"), set()).add(match.group("group"))
    return {alias: frozenset(alias_groups) for alias, alias_groups in groups.items()}


def has_conflicting_module_group(
    alias: str,
    source: SourceVersion,
    target_module_groups: dict[str, frozenset[str]],
) -> bool:
    target_groups = target_module_groups.get(alias, frozenset())
    return bool(source.module_groups and target_groups and source.module_groups.isdisjoint(target_groups))


def verify_self_version_alias(source_versions: dict[str, SourceVersion]) -> None:
    catalog_version = source_versions.get(SELF_ALIAS)
    if catalog_version is None:
        raise RuntimeError("source-of-truth block must include `bluetape4k-dependencies`")


def sync_catalog(catalog: Path, source_versions: dict[str, SourceVersion]) -> tuple[str, list[Change]]:
    catalog_text = catalog.read_text(encoding="utf-8")
    target_module_groups = module_groups_by_version_ref(catalog_text)
    lines = catalog_text.splitlines()
    changes: list[Change] = []
    updated: list[str] = []
    in_versions = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_versions = stripped == "[versions]"
            updated.append(raw_line)
            continue

        prefix = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        match = VERSION_LINE.match(stripped) if in_versions else INLINE_VERSION_LINE.match(stripped)
        if not match:
            updated.append(raw_line)
            continue

        alias = match.group(1)
        source = source_versions.get(alias)
        if source is None:
            updated.append(raw_line)
            continue
        if has_conflicting_module_group(alias, source, target_module_groups):
            updated.append(raw_line)
            continue

        old_version = match.group(2)
        if old_version == source.version:
            updated.append(raw_line)
            continue

        new_line = raw_line.replace(f'"{old_version}"', f'"{source.version}"', 1)
        updated.append(new_line)
        if old_version != source.version:
            changes.append(
                Change(
                    repo=catalog.parents[1].name,
                    alias=alias,
                    before=old_version,
                    after=source.version,
                ),
            )

    return "\n".join(updated) + "\n", changes


def target_catalogs(workspace: Path, repositories: tuple[str, ...]) -> list[Path]:
    catalogs: list[Path] = []
    for repo in repositories:
        catalog = workspace / repo / "gradle" / "libs.versions.toml"
        if not catalog.is_file():
            raise RuntimeError(f"missing managed repository catalog: {repo} ({catalog})")
        catalogs.append(catalog)
    return catalogs


def print_default_repositories() -> None:
    for repo in DEFAULT_REPOSITORIES:
        print(repo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Workspace directory containing bluetape4k sibling repositories.",
    )
    parser.add_argument(
        "--repo",
        action="append",
        dest="repositories",
        help="Repository name to sync. May be repeated. Defaults to governed bluetape4k-* repos.",
    )
    parser.add_argument(
        "--repository-map",
        type=Path,
        help="JSON map of managed repository names to candidate catalog paths, branches, and expected HEADs.",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        help="Compatibility exception TOML. Defaults to config/central-catalog-exceptions.toml.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Deprecated compatibility flag. Adoption gaps are never rewritten automatically.",
    )
    parser.add_argument("--check", action="store_true", help="Fail when downstream catalogs duplicate central authority.")
    parser.add_argument("--summary", action="store_true", help="Print a compact adoption summary.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Diagnostic output format.")
    parser.add_argument(
        "--print-default-repositories",
        action="store_true",
        help="Print the built-in repository list and exit.",
    )
    args = parser.parse_args()

    if args.print_default_repositories:
        print_default_repositories()
        return 0

    repo_root = Path(__file__).resolve().parents[1]
    workspace = args.workspace.resolve()
    repositories = tuple(args.repositories) if args.repositories else DEFAULT_REPOSITORIES
    unknown_repositories = sorted(set(repositories) - set(DEFAULT_REPOSITORIES))
    if unknown_repositories:
        print(f"Unknown managed repositories: {', '.join(unknown_repositories)}", file=sys.stderr)
        return 2
    source_catalog = repo_root / "gradle" / "libs.versions.toml"
    source_versions = read_source_versions(source_catalog)
    verify_self_version_alias(source_versions)
    source_data = read_catalog(source_catalog)
    exception_path = args.exceptions or repo_root / "config" / "central-catalog-exceptions.toml"
    try:
        exceptions = load_exceptions(exception_path)
        if args.repository_map:
            mapped = load_repository_map(args.repository_map, workspace, DEFAULT_REPOSITORIES)
            missing = sorted(set(repositories) - set(mapped))
            if missing:
                raise RuntimeError(f"repository map is missing managed repositories: {', '.join(missing)}")
            catalog_entries = [(repository, mapped[repository].catalog) for repository in repositories]
        else:
            catalog_entries = [
                (catalog.parents[1].name, catalog)
                for catalog in target_catalogs(workspace, repositories)
            ]
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    compatibility_errors = compatibility_line_errors(source_catalog, repo_root.name)
    adoption_gaps: list[AdoptionGap] = []
    for repository, catalog in catalog_entries:
        compatibility_errors.extend(compatibility_line_errors(catalog, repository))
        adoption_gaps.extend(find_adoption_gaps(repository, read_catalog(catalog), source_data, exceptions))
        adoption_gaps.extend(find_catalog_ref_gaps(repository, catalog))

    if args.format == "json":
        print(
            json.dumps(
                [dataclasses.asdict(gap) for gap in sorted(adoption_gaps, key=lambda item: (item.repository, item.kind, item.key))],
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    elif args.summary or adoption_gaps:
        for gap in sorted(adoption_gaps, key=lambda item: (item.repository, item.kind, item.key)):
            print(f"{gap.repository}: {gap.kind} {gap.key} local={gap.local} central={gap.central}")
        if not adoption_gaps:
            print("Central catalog adoption is clean.")

    if args.write:
        print("--write is deprecated; adoption gaps were not modified.", file=sys.stderr)
    if adoption_gaps and (args.check or args.write):
        print(f"Central catalog adoption gaps detected: {len(adoption_gaps)}.", file=sys.stderr)
        return 1
    if compatibility_errors:
        for error in compatibility_errors:
            print(
                f"{error.repo}: {error.alias} {error.version} violates expected {error.expected_major}.x "
                f"({error.catalog})",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
