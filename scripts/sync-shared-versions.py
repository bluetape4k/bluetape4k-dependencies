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
import hashlib
import importlib.util
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

CANDIDATE_PATH = Path(__file__).resolve().with_name("catalog_candidate.py")
CANDIDATE_SPEC = importlib.util.spec_from_file_location(
    "catalog_candidate", CANDIDATE_PATH
)
if CANDIDATE_SPEC is None or CANDIDATE_SPEC.loader is None:
    raise RuntimeError(f"Cannot load {CANDIDATE_PATH}")
catalog_candidate = importlib.util.module_from_spec(CANDIDATE_SPEC)
sys.modules.setdefault("catalog_candidate", catalog_candidate)
CANDIDATE_SPEC.loader.exec_module(catalog_candidate)

SOURCE_START = "# <shared-version-source-of-truth by scripts/sync-shared-versions.py>"
SOURCE_END = "# </shared-version-source-of-truth>"
SELF_ALIAS = "bluetape4k-dependencies"
VERSION_LINE = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"(?P<suffix>.*)$')
INLINE_VERSION_LINE = re.compile(
    r'^([A-Za-z0-9_.-]+)\s*=\s*\{.*\bversion\s*=\s*"([^"]+)".*\}\s*(?:#.*)?$'
)

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

DISPOSITION_EVIDENCE_TYPES = {
    "central-direct": frozenset({"catalog-alias"}),
    "central-version-local-alias": frozenset({"catalog-version"}),
    "bom-managed-versionless": frozenset({"publication-pom"}),
    "compatibility-line": frozenset({"compatibility-review"}),
    "structural-repo-owned": frozenset({"settings-evaluation"}),
}
AUTHORITY_LINE_FIELDS = frozenset(
    {
        "repository",
        "subject-kind",
        "coordinate-or-plugin-id",
        "alias",
        "line-id",
    }
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
LINE_ID = re.compile(r"^(?:default|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
HARD_CODED_LIBRARY = re.compile(
    r'(?P<quote>["\'])(?P<group>[A-Za-z0-9_.-]+):(?P<artifact>[A-Za-z0-9_.-]+):'
    r'(?P<version>[^"\'\s$]+)(?P=quote)'
)
HARD_CODED_PLUGIN = re.compile(
    r'\bid\(\s*["\'](?P<plugin>[^"\']+)["\']\s*\)\s*version\s*'
    r'(?:\(\s*)?["\'](?P<version>[^"\'$]+)["\']'
)


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
EXCEPTION_KINDS = frozenset(
    {
        "version",
        "library-version",
        "library-identity",
        "plugin-version",
        "plugin-identity",
    }
)
ISSUE_URL = re.compile(
    r"^https://github\.com/bluetape4k/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)$"
)
GIT_HEAD = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
STRING_ASSIGNMENT = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"\s*(?:#.*)?$')
SETTINGS_CATALOG_REF = re.compile(r'\.orElse\("([0-9a-f]{40}|[0-9a-f]{64})"\)')
WORKFLOW_CATALOG_REF = re.compile(
    r"^\s*BLUETAPE4K_DEPENDENCIES_CATALOG_REF:\s*[\'\"]?([0-9a-f]{40}|[0-9a-f]{64})[\'\"]?\s*$",
    re.MULTILINE,
)
IMPLICIT_SIBLING_CATALOG_PATHS = (
    "../bluetape4k-dependencies/gradle/libs.versions.toml",
    "bluetape4k-dependencies/gradle/libs.versions.toml",
)
CATALOG_LOADER_CONTRACTS = {
    "explicit-regular-file": "Files.isSymbolicLink(catalogFile.toPath())",
    "immutable-ref": "bluetape4kDependenciesCatalogRef.matches(",
    "connect-timeout": "connection.connectTimeout",
    "read-timeout": "connection.readTimeout",
    "bounded-download": "maxBytes: Long",
    "catalog-structure": "validateCatalogStructure(catalogFile: File)",
}


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
        alias_match = re.match(
            r"^([A-Za-z0-9_.-]+)\s*=\s*\{(.*)\}\s*(?:#.*)?$", stripped
        )
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


def load_exceptions(
    path: Path, *, today: date | None = None
) -> tuple[CatalogException, ...]:
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
            raise RuntimeError(
                f"exception has unknown fields: {', '.join(sorted(unknown))}"
            )
        if missing:
            raise RuntimeError(
                f"exception is missing fields: {', '.join(sorted(missing))}"
            )
        for field in EXCEPTION_FIELDS - {"introduced", "review-by"}:
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise RuntimeError(f"exception {field} must be non-empty")
        if entry["kind"] not in EXCEPTION_KINDS:
            raise RuntimeError(
                f"exception kind must be one of: {', '.join(sorted(EXCEPTION_KINDS))}"
            )
        repository = entry["repository"]
        issue_match = ISSUE_URL.fullmatch(entry["issue"])
        if issue_match is None or issue_match.group(1) != repository:
            raise RuntimeError(
                "exception issue must be a canonical same-repository bluetape4k issue URL"
            )
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
            gaps.append(
                AdoptionGap(
                    repository, "version-duplicate", key, value, central.versions[key]
                )
            )

    central_library_by_module = {
        library.module: library for library in central.libraries.values()
    }
    for alias, library in local.libraries.items():
        central_same_alias = central.libraries.get(alias)
        if (
            central_same_alias is not None
            and central_same_alias.module != library.module
        ):
            if not _is_excepted(
                repository,
                alias,
                alias,
                "library-identity",
                library.module,
                _resolved_local_version(
                    library.version_ref, library.version, local.versions
                ),
                library.version_ref or alias,
                exceptions,
            ):
                gaps.append(
                    AdoptionGap(
                        repository,
                        "library-identity-conflict",
                        alias,
                        library.module,
                        central_same_alias.module,
                    ),
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
                _resolved_local_version(
                    library.version_ref, library.version, local.versions
                ),
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

    central_plugin_by_id = {
        plugin.plugin_id: plugin for plugin in central.plugins.values()
    }
    for alias, plugin in local.plugins.items():
        central_same_alias = central.plugins.get(alias)
        if (
            central_same_alias is not None
            and central_same_alias.plugin_id != plugin.plugin_id
        ):
            if not _is_excepted(
                repository,
                alias,
                alias,
                "plugin-identity",
                plugin.plugin_id,
                _resolved_local_version(
                    plugin.version_ref, plugin.version, local.versions
                ),
                plugin.version_ref or alias,
                exceptions,
            ):
                gaps.append(
                    AdoptionGap(
                        repository,
                        "plugin-identity-conflict",
                        alias,
                        plugin.plugin_id,
                        central_same_alias.plugin_id,
                    ),
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
                _resolved_local_version(
                    plugin.version_ref, plugin.version, local.versions
                ),
                plugin.version_ref or alias,
                exceptions,
            )
        ):
            gaps.append(
                AdoptionGap(
                    repository,
                    "plugin-id-duplicate",
                    alias,
                    plugin.plugin_id,
                    central_same_id.alias,
                ),
            )
    return gaps


def find_catalog_ref_gaps(repository: str, catalog: Path) -> list[AdoptionGap]:
    """Report when local Gradle and CI resolve different central catalog commits."""
    repository_root = catalog.parents[1]
    settings_path = repository_root / "settings.gradle.kts"
    workflow_path = repository_root / ".github" / "workflows" / "ci.yml"

    settings_text = (
        settings_path.read_text(encoding="utf-8") if settings_path.is_file() else ""
    )
    workflow_text = (
        workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    )
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


def find_catalog_loader_gaps(repository: str, catalog: Path) -> list[AdoptionGap]:
    """Report catalog loaders that can bypass or weaken the immutable ref contract."""
    settings_path = catalog.parents[1] / "settings.gradle.kts"
    settings_text = (
        settings_path.read_text(encoding="utf-8") if settings_path.is_file() else ""
    )
    gaps: list[AdoptionGap] = []

    for sibling_path in IMPLICIT_SIBLING_CATALOG_PATHS:
        if sibling_path in settings_text:
            gaps.append(
                AdoptionGap(
                    repository,
                    "catalog-loader-contract",
                    "implicit-sibling-fallback",
                    sibling_path,
                    "<none>",
                ),
            )
            break

    for contract, marker in CATALOG_LOADER_CONTRACTS.items():
        if marker not in settings_text:
            gaps.append(
                AdoptionGap(
                    repository,
                    "catalog-loader-contract",
                    contract,
                    "<missing>",
                    marker,
                ),
            )
    return gaps


def load_repository_map(
    path: Path,
    workspace: Path,
    allowed_repositories: tuple[str, ...],
) -> dict[str, RepositoryTarget]:
    loaded = catalog_candidate.load_repository_map_v1(path, workspace)
    executing_root = Path(__file__).resolve().parents[1]
    if loaded[0].root != executing_root:
        raise RuntimeError(
            "repository map central root does not match the executing checkout"
        )
    allowed = set(allowed_repositories)
    targets = {
        item.name: RepositoryTarget(
            item.name, item.catalog, item.branch, item.expected_head
        )
        for item in loaded
        if item.key != "central" and item.name in allowed
    }
    if set(targets) != allowed:
        missing = sorted(allowed - set(targets))
        raise RuntimeError(
            f"repository map is missing managed repositories: {', '.join(missing)}"
        )
    return targets


def repository_roots(
    targets: dict[str, RepositoryTarget],
) -> dict[str, Path]:
    return {
        repository: target.catalog.parents[1]
        for repository, target in targets.items()
    }


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
    return bool(
        source.module_groups
        and target_groups
        and source.module_groups.isdisjoint(target_groups)
    )


def verify_self_version_alias(source_versions: dict[str, SourceVersion]) -> None:
    catalog_version = source_versions.get(SELF_ALIAS)
    if catalog_version is None:
        raise RuntimeError(
            "source-of-truth block must include `bluetape4k-dependencies`"
        )


def sync_catalog(
    catalog: Path, source_versions: dict[str, SourceVersion]
) -> tuple[str, list[Change]]:
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

        match = (
            VERSION_LINE.match(stripped)
            if in_versions
            else INLINE_VERSION_LINE.match(stripped)
        )
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
            raise RuntimeError(
                f"missing managed repository catalog: {repo} ({catalog})"
            )
        catalogs.append(catalog)
    return catalogs


def canonical_json_bytes(value: object) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def write_report(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _catalog_authority_module() -> Any:
    script = Path(__file__).resolve().with_name("catalog_authority.py")
    spec = importlib.util.spec_from_file_location("catalog_authority_inventory", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load catalog authority module: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _section_source_lines(catalog: Path, target_section: str) -> dict[str, int]:
    lines: dict[str, int] = {}
    section = ""
    for line_number, raw_line in enumerate(
        catalog.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section != target_section or not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*=", stripped)
        if match:
            lines[match.group(1)] = line_number
    return lines


def catalog_authority_records(
    workspace: Path,
    central_catalog: Path,
    repositories: tuple[str, ...],
    repository_roots: dict[str, Path] | None = None,
    *,
    authority_lines: dict[tuple[str, str, str, str], str] | None = None,
    used_authority_lines: set[tuple[str, str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    authority = _catalog_authority_module()
    read_catalog(central_catalog)
    pending: list[dict[str, Any]] = []
    subject_repositories: dict[tuple[str, str], set[str]] = {}

    for repository in repositories:
        repository_root = (repository_roots or {}).get(
            repository, workspace / repository
        )
        catalog = repository_root / "gradle" / "libs.versions.toml"
        data = read_catalog(catalog)
        library_source_lines = _section_source_lines(catalog, "libraries")
        for alias, library in data.libraries.items():
            if library.module.startswith("io.github.bluetape4k:"):
                continue
            if library.version is None and library.version_ref is None:
                continue
            declared_version = library.version
            if declared_version is None and library.version_ref is not None:
                declared_version = data.versions.get(library.version_ref)
            if not declared_version:
                raise RuntimeError(
                    f"explicit library authority has no declared version: {repository}:{alias}"
                )
            stable_id = authority.authority_id(repository, "library", library.module)
            line_id = authority_line_id(
                authority_lines,
                used_authority_lines,
                repository,
                "library",
                library.module,
                alias,
            )
            source_path = "gradle/libs.versions.toml"
            source_line = library_source_lines.get(alias)
            if source_line is None:
                raise RuntimeError(
                    f"missing source line for catalog alias: {repository}:{alias}"
                )
            occurrence_payload = "\0".join(
                (stable_id, line_id, alias, source_path, str(source_line))
            ).encode("utf-8")
            pending.append(
                {
                    "alias": alias,
                    "authority-id": stable_id,
                    "coordinate-or-plugin-id": library.module,
                    "declaration-form": "catalog",
                    "declared-version": declared_version,
                    "disposition": None,
                    "evidence": None,
                    "line-id": line_id,
                    "occurrence-id": hashlib.sha256(occurrence_payload).hexdigest(),
                    "owner": None,
                    "repository": repository,
                    "repository-count": 0,
                    "resolved-version": None,
                    "source-line": source_line,
                    "source-path": source_path,
                    "subject-kind": "library",
                }
            )
            subject_repositories.setdefault(("library", library.module), set()).add(
                repository
            )

        plugin_source_lines = _section_source_lines(catalog, "plugins")
        for alias, plugin in data.plugins.items():
            if plugin.version is None and plugin.version_ref is None:
                continue
            declared_version = plugin.version
            if declared_version is None and plugin.version_ref is not None:
                declared_version = data.versions.get(plugin.version_ref)
            if not declared_version:
                raise RuntimeError(
                    f"explicit plugin authority has no declared version: {repository}:{alias}"
                )
            stable_id = authority.authority_id(repository, "plugin", plugin.plugin_id)
            line_id = authority_line_id(
                authority_lines,
                used_authority_lines,
                repository,
                "plugin",
                plugin.plugin_id,
                alias,
            )
            source_path = "gradle/libs.versions.toml"
            source_line = plugin_source_lines.get(alias)
            if source_line is None:
                raise RuntimeError(
                    f"missing source line for plugin alias: {repository}:{alias}"
                )
            occurrence_payload = "\0".join(
                (stable_id, line_id, alias, source_path, str(source_line))
            ).encode("utf-8")
            pending.append(
                {
                    "alias": alias,
                    "authority-id": stable_id,
                    "coordinate-or-plugin-id": plugin.plugin_id,
                    "declaration-form": "catalog",
                    "declared-version": declared_version,
                    "disposition": None,
                    "evidence": None,
                    "line-id": line_id,
                    "occurrence-id": hashlib.sha256(occurrence_payload).hexdigest(),
                    "owner": None,
                    "repository": repository,
                    "repository-count": 0,
                    "resolved-version": None,
                    "source-line": source_line,
                    "source-path": source_path,
                    "subject-kind": "plugin",
                }
            )
            subject_repositories.setdefault(("plugin", plugin.plugin_id), set()).add(
                repository
            )

    for record in pending:
        record["repository-count"] = len(
            subject_repositories[
                (record["subject-kind"], record["coordinate-or-plugin-id"])
            ]
        )
    return sorted(
        pending,
        key=lambda item: (
            item["repository"],
            item["source-path"],
            item["source-line"],
            item["alias"],
        ),
    )


def hard_coded_authority_records(
    workspace: Path,
    repositories: tuple[str, ...],
    repository_roots: dict[str, Path] | None = None,
    *,
    authority_lines: dict[tuple[str, str, str, str], str] | None = None,
    used_authority_lines: set[tuple[str, str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    authority = _catalog_authority_module()
    pending: list[dict[str, Any]] = []
    subject_repositories: dict[tuple[str, str], set[str]] = {}
    excluded_parts = frozenset({".git", ".gradle", ".worktrees", "build"})

    for repository in repositories:
        repository_root = (repository_roots or {}).get(
            repository, workspace / repository
        )
        for source in sorted(repository_root.rglob("*.gradle.kts")):
            relative = source.relative_to(repository_root)
            if excluded_parts.intersection(relative.parts):
                continue
            for source_line, raw_line in enumerate(
                source.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if raw_line.lstrip().startswith("//"):
                    continue
                matches: list[tuple[str, str, str, str]] = []
                for match in HARD_CODED_LIBRARY.finditer(raw_line):
                    group = match.group("group")
                    if group in {"jdbc", "scm"} or group == "io.github.bluetape4k":
                        continue
                    coordinate = f"{group}:{match.group('artifact')}"
                    matches.append(
                        ("library", coordinate, coordinate, match.group("version"))
                    )
                for match in HARD_CODED_PLUGIN.finditer(raw_line):
                    plugin_id = match.group("plugin")
                    matches.append(
                        ("plugin", plugin_id, plugin_id, match.group("version"))
                    )

                for subject_kind, subject, alias, declared_version in matches:
                    stable_id = authority.authority_id(
                        repository, subject_kind, subject
                    )
                    line_id = authority_line_id(
                        authority_lines,
                        used_authority_lines,
                        repository,
                        subject_kind,
                        subject,
                        alias,
                    )
                    source_path = relative.as_posix()
                    occurrence_payload = "\0".join(
                        (stable_id, line_id, alias, source_path, str(source_line))
                    ).encode("utf-8")
                    pending.append(
                        {
                            "alias": alias,
                            "authority-id": stable_id,
                            "coordinate-or-plugin-id": subject,
                            "declaration-form": "hard-coded",
                            "declared-version": declared_version,
                            "disposition": None,
                            "evidence": None,
                            "line-id": line_id,
                            "occurrence-id": hashlib.sha256(
                                occurrence_payload
                            ).hexdigest(),
                            "owner": None,
                            "repository": repository,
                            "repository-count": 0,
                            "resolved-version": None,
                            "source-line": source_line,
                            "source-path": source_path,
                            "subject-kind": subject_kind,
                        }
                    )
                    subject_repositories.setdefault((subject_kind, subject), set()).add(
                        repository
                    )

    for record in pending:
        record["repository-count"] = len(
            subject_repositories[
                (record["subject-kind"], record["coordinate-or-plugin-id"])
            ]
        )
    return sorted(
        pending,
        key=lambda item: (
            item["repository"],
            item["source-path"],
            item["source-line"],
            item["alias"],
        ),
    )


def load_dispositions(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid disposition manifest: {path}") from exc
    if not isinstance(value, dict):
        raise TypeError("disposition manifest must be an object")
    return value


def load_authority_lines(path: Path) -> dict[tuple[str, str, str, str], str]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid authority line manifest: {path}") from exc
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema-version", "records"}
        or manifest.get("schema-version") != 1
        or not isinstance(manifest.get("records"), list)
    ):
        raise RuntimeError("invalid authority line manifest schema")

    result: dict[tuple[str, str, str, str], str] = {}
    for index, record in enumerate(manifest["records"]):
        if not isinstance(record, dict) or set(record) != AUTHORITY_LINE_FIELDS:
            raise RuntimeError(f"invalid authority line record at index {index}")
        repository = record.get("repository")
        subject_kind = record.get("subject-kind")
        subject = record.get("coordinate-or-plugin-id")
        alias = record.get("alias")
        line_id = record.get("line-id")
        if (
            not all(
                isinstance(value, str) and value
                for value in (repository, subject, alias)
            )
            or subject_kind not in {"library", "plugin"}
            or not isinstance(line_id, str)
            or line_id == "default"
            or LINE_ID.fullmatch(line_id) is None
        ):
            raise RuntimeError(f"invalid authority line record at index {index}")
        selector = (repository, subject_kind, subject, alias)
        if selector in result:
            raise RuntimeError(
                "duplicate authority line selector: " + ":".join(selector)
            )
        result[selector] = line_id
    return result


def authority_line_id(
    authority_lines: dict[tuple[str, str, str, str], str] | None,
    used_authority_lines: set[tuple[str, str, str, str]] | None,
    repository: str,
    subject_kind: str,
    subject: str,
    alias: str,
) -> str:
    selector = (repository, subject_kind, subject, alias)
    if authority_lines is None or selector not in authority_lines:
        return "default"
    if used_authority_lines is not None:
        used_authority_lines.add(selector)
    return authority_lines[selector]


def validate_authority_line_usage(
    authority_lines: dict[tuple[str, str, str, str], str],
    used_authority_lines: set[tuple[str, str, str, str]],
) -> None:
    unused = sorted(set(authority_lines) - used_authority_lines)
    if unused:
        raise RuntimeError(f"unused authority line selectors: {len(unused)}")


def validate_dispositions(
    manifest: dict[str, Any],
    expected_pairs: set[tuple[str, str]],
    *,
    today: date | None = None,
) -> None:
    if (
        set(manifest) != {"schema-version", "records"}
        or manifest.get("schema-version") != 1
    ):
        raise RuntimeError("invalid disposition manifest schema")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise TypeError("disposition records must be a list")

    actual_pairs: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"invalid disposition record at index {index}")
        authority_id = record.get("authority-id")
        line_id = record.get("line-id")
        if not isinstance(authority_id, str) or SHA256.fullmatch(authority_id) is None:
            raise RuntimeError(f"invalid authority-id at disposition index {index}")
        if not isinstance(line_id, str) or LINE_ID.fullmatch(line_id) is None:
            raise RuntimeError(f"invalid line-id at disposition index {index}")
        pair = (authority_id, line_id)
        if pair in actual_pairs:
            raise RuntimeError(f"duplicate disposition pair: {authority_id}:{line_id}")
        actual_pairs.add(pair)

        disposition = record.get("disposition")
        allowed_evidence = DISPOSITION_EVIDENCE_TYPES.get(disposition)
        if allowed_evidence is None:
            raise RuntimeError(f"invalid disposition at index {index}: {disposition}")
        evidence = record.get("evidence")
        if (
            not isinstance(evidence, dict)
            or evidence.get("type") not in allowed_evidence
        ):
            expected = ", ".join(sorted(allowed_evidence))
            raise RuntimeError(
                f"invalid evidence for {disposition}; expected {expected}"
            )
        if not isinstance(evidence.get("path"), str) or not evidence["path"]:
            raise RuntimeError(f"missing evidence path at disposition index {index}")
        if record.get("status") not in {"pending", "verified"}:
            raise RuntimeError(f"invalid disposition status at index {index}")
        if not isinstance(record.get("owner"), str) or not record["owner"]:
            raise RuntimeError(f"missing disposition owner at index {index}")
        if disposition == "structural-repo-owned":
            repository = record.get("repository")
            issue = record.get("issue")
            match = ISSUE_URL.fullmatch(issue) if isinstance(issue, str) else None
            if (
                not isinstance(repository, str)
                or match is None
                or match.group(1) != repository
            ):
                raise RuntimeError(
                    f"structural disposition requires a same-repository issue at index {index}"
                )
            review_by = record.get("review-by")
            try:
                review_date = date.fromisoformat(review_by)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"invalid structural review-by at index {index}"
                ) from exc
            observed = today or datetime.now(timezone.utc).date()
            if review_date <= observed:
                raise RuntimeError(
                    f"expired structural review at disposition index {index}"
                )

    orphan = sorted(actual_pairs - expected_pairs)
    missing = sorted(expected_pairs - actual_pairs)
    if orphan:
        raise RuntimeError(f"orphan disposition pairs: {len(orphan)}")
    if missing:
        raise RuntimeError(f"missing disposition pairs: {len(missing)}")


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
        "--inventory-out",
        type=Path,
        help="Write the deterministic external authority inventory as canonical JSON.",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        help="Write the deterministic external authority summary as canonical JSON.",
    )
    parser.add_argument(
        "--dispositions",
        type=Path,
        help="Source-controlled one-to-one authority disposition manifest.",
    )
    parser.add_argument(
        "--authority-lines",
        type=Path,
        help="Source-controlled selectors for simultaneous compatibility lines.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Deprecated compatibility flag. Adoption gaps are never rewritten automatically.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when downstream catalogs duplicate central authority.",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print a compact adoption summary."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Diagnostic output format.",
    )
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
    repositories = (
        tuple(args.repositories) if args.repositories else DEFAULT_REPOSITORIES
    )
    unknown_repositories = sorted(set(repositories) - set(DEFAULT_REPOSITORIES))
    if unknown_repositories:
        print(
            f"Unknown managed repositories: {', '.join(unknown_repositories)}",
            file=sys.stderr,
        )
        return 2
    source_catalog = repo_root / "gradle" / "libs.versions.toml"
    mapped: dict[str, RepositoryTarget] | None = None
    mapped_repository_roots: dict[str, Path] | None = None
    if args.repository_map:
        try:
            mapped = load_repository_map(
                args.repository_map, workspace, DEFAULT_REPOSITORIES
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        mapped_repository_roots = repository_roots(mapped)
    if bool(args.inventory_out) != bool(args.summary_out):
        print(
            "--inventory-out and --summary-out must be supplied together",
            file=sys.stderr,
        )
        return 2
    if args.inventory_out:
        try:
            authority_lines = load_authority_lines(
                args.authority_lines
                or repo_root / "config" / "central-catalog-authority-lines.json"
            )
            used_authority_lines: set[tuple[str, str, str, str]] = set()
            catalog_inventory = catalog_authority_records(
                workspace,
                source_catalog,
                repositories,
                mapped_repository_roots,
                authority_lines=authority_lines,
                used_authority_lines=used_authority_lines,
            )
            hard_coded_inventory = hard_coded_authority_records(
                workspace,
                repositories,
                mapped_repository_roots,
                authority_lines=authority_lines,
                used_authority_lines=used_authority_lines,
            )
            validate_authority_line_usage(authority_lines, used_authority_lines)
            inventory = sorted(
                catalog_inventory + hard_coded_inventory,
                key=lambda item: (
                    item["repository"],
                    item["source-path"],
                    item["source-line"],
                    item["alias"],
                ),
            )
            summary = {
                "catalog-library-occurrences": sum(
                    item["declaration-form"] == "catalog"
                    and item["subject-kind"] == "library"
                    for item in inventory
                ),
                "catalog-plugin-occurrences": sum(
                    item["declaration-form"] == "catalog"
                    and item["subject-kind"] == "plugin"
                    for item in inventory
                ),
                "external-plugin-ids": len(
                    {
                        item["coordinate-or-plugin-id"]
                        for item in catalog_inventory
                        if item["subject-kind"] == "plugin"
                    }
                ),
                "hard-coded-candidates": len(hard_coded_inventory),
                "repository-count": len(repositories),
                "total-occurrences": len(inventory),
                "unique-authority-pairs": len(
                    {(item["authority-id"], item["line-id"]) for item in inventory}
                ),
            }
            write_report(args.inventory_out, inventory)
            write_report(args.summary_out, summary)
            disposition_path = (
                args.dispositions
                or repo_root / "config" / "central-catalog-authority-dispositions.json"
            )
            dispositions = load_dispositions(disposition_path)
            validate_dispositions(
                dispositions,
                {(item["authority-id"], item["line-id"]) for item in inventory},
            )
        except (ImportError, RuntimeError, TypeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    source_versions = read_source_versions(source_catalog)
    verify_self_version_alias(source_versions)
    source_data = read_catalog(source_catalog)
    exception_path = (
        args.exceptions or repo_root / "config" / "central-catalog-exceptions.toml"
    )
    try:
        exceptions = load_exceptions(exception_path)
        if mapped is not None:
            missing = sorted(set(repositories) - set(mapped))
            if missing:
                raise RuntimeError(
                    f"repository map is missing managed repositories: {', '.join(missing)}"
                )
            catalog_entries = [
                (repository, mapped[repository].catalog) for repository in repositories
            ]
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
        adoption_gaps.extend(
            find_adoption_gaps(
                repository, read_catalog(catalog), source_data, exceptions
            )
        )
        adoption_gaps.extend(find_catalog_ref_gaps(repository, catalog))
        adoption_gaps.extend(find_catalog_loader_gaps(repository, catalog))

    if args.format == "json":
        print(
            json.dumps(
                [
                    dataclasses.asdict(gap)
                    for gap in sorted(
                        adoption_gaps,
                        key=lambda item: (item.repository, item.kind, item.key),
                    )
                ],
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    elif args.summary or adoption_gaps:
        for gap in sorted(
            adoption_gaps, key=lambda item: (item.repository, item.kind, item.key)
        ):
            print(
                f"{gap.repository}: {gap.kind} {gap.key} local={gap.local} central={gap.central}"
            )
        if not adoption_gaps:
            print("Central catalog adoption is clean.")

    if args.write:
        print(
            "--write is deprecated; adoption gaps were not modified.", file=sys.stderr
        )
    if adoption_gaps and (args.check or args.write):
        print(
            f"Central catalog adoption gaps detected: {len(adoption_gaps)}.",
            file=sys.stderr,
        )
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
