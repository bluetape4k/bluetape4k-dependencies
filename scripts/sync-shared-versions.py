#!/usr/bin/env python3
"""Sync shared version aliases from bluetape4k-dependencies to sibling repos.

`gradle/libs.versions.toml` in this repository is the source of truth for
organization-wide version aliases. Downstream repositories may keep local
version catalogs, but aliases that also exist in the marked source block here
must use the exact same version line.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path


SOURCE_START = "# <shared-version-source-of-truth by scripts/sync-shared-versions.py>"
SOURCE_END = "# </shared-version-source-of-truth>"
SELF_ALIAS = "bluetape4k-dependencies"
VERSION_LINE = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"(?P<suffix>.*)$')
INLINE_VERSION_LINE = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*\{.*\bversion\s*=\s*"([^"]+)".*\}\s*(?:#.*)?$')

DEFAULT_REPOSITORIES = (
    "bluetape4k-projects",
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
        if catalog.exists():
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
    parser.add_argument("--write", action="store_true", help="Rewrite downstream catalogs.")
    parser.add_argument("--check", action="store_true", help="Fail when downstream catalogs drift.")
    parser.add_argument("--summary", action="store_true", help="Print a compact sync summary.")
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
    source_catalog = repo_root / "gradle" / "libs.versions.toml"
    source_versions = read_source_versions(source_catalog)
    verify_self_version_alias(source_versions)

    compatibility_errors = compatibility_line_errors(source_catalog, repo_root.name)
    all_changes: list[Change] = []
    for catalog in target_catalogs(workspace, repositories):
        synced_text, changes = sync_catalog(catalog, source_versions)
        if changes and args.write:
            catalog.write_text(synced_text, encoding="utf-8")
        compatibility_errors.extend(compatibility_line_errors(catalog, catalog.parents[1].name))
        all_changes.extend(changes)

    if args.summary or all_changes:
        for change in all_changes:
            print(f"{change.repo}: {change.alias} {change.before} -> {change.after}")
        if not all_changes:
            print("Shared versions are aligned.")

    if args.check and all_changes and not args.write:
        print(f"Shared version drift detected: {len(all_changes)} changes required.", file=sys.stderr)
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
