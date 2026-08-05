#!/usr/bin/env python3
"""Fail-closed migration of downstream Gradle catalogs to the ``bt4k`` catalog.

The authority inventory and policy are the source of truth for the local-to-
central alias mapping.  This helper deliberately edits only tracked
``build.gradle.kts`` files and ``gradle/libs.versions.toml``.  Settings-time
plugin pins (notably Foojay) and hard-coded declarations are reported, never
rewritten speculatively.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import tomllib

SCRIPT_DIR = Path(__file__).resolve().parent
CATALOG_AUTHORITY = SCRIPT_DIR / "catalog_authority.py"
CATALOG_CANDIDATE = SCRIPT_DIR / "catalog_candidate.py"
CATALOG_PROMOTION = SCRIPT_DIR / "promote-catalog-authority.py"
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

INVENTORY_FIELDS = frozenset(
    {
        "alias",
        "authority-id",
        "coordinate-or-plugin-id",
        "declaration-form",
        "declared-version",
        "disposition",
        "evidence",
        "line-id",
        "occurrence-id",
        "owner",
        "repository",
        "repository-count",
        "resolved-version",
        "source-line",
        "source-path",
        "subject-kind",
    }
)
POLICY_SUBJECT_FIELDS = frozenset({"coordinate-or-plugin-id", "lines", "subject-kind"})
POLICY_LINE_FIELDS = frozenset(
    {
        "central-aliases",
        "disposition",
        "evidence",
        "line-id",
        "occurrences",
        "version",
        "version-key",
    }
)
POLICY_OCCURRENCE_FIELDS = frozenset({"central-alias", "local-alias", "repository"})
VERSION_SELECTOR_FIELDS = frozenset(
    {"central-version-key", "local-version-key", "repository"}
)
DISPOSITION_FIELDS = frozenset(
    {
        "authority-id",
        "central-aliases",
        "disposition",
        "evidence",
        "issue",
        "line-id",
        "owner",
        "repository",
        "review-by",
        "status",
    }
)
ALIAS_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SECTION_PATTERN = re.compile(r"^\s*\[([a-z]+)\]\s*$")
ASSIGNMENT_PATTERN = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")
ACCESSOR_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])(?:libs|rootLibs)(?:\.(?:plugins|versions))?"
    r"(?:\.(?:asProvider\(\)|[A-Za-z0-9_]+))+"
)
HARD_CODED_LIBRARY_PATTERN = re.compile(
    r'(?P<quote>["\'])(?P<coordinate>[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+):'
    r'(?P<version>[^"\'\s$]+)(?P=quote)'
)
HARD_CODED_PLUGIN_PATTERN = re.compile(
    r'\bid\(\s*["\'](?P<coordinate>[^"\']+)["\']\s*\)\s*version\s*'
    r'(?:\(\s*)?["\'](?P<version>[^"\'$]+)["\']'
)
DYNAMIC_LIBRARY_PATTERN = re.compile(
    r"\b(?:libs|rootLibs)\.findLibrary\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
DYNAMIC_VERSION_PATTERN = re.compile(
    r"\b(?:libs|rootLibs)\.findVersion\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
ALLOWED_PROVIDER_TAILS = frozenset(
    {
        "asProvider",
        "get",
        "getOrElse",
        "getOrNull",
        "map",
        "orElse",
        "preferredVersion",
        "requiredVersion",
        "strictVersion",
    }
)


class MigrationError(RuntimeError):
    """Raised when a migration input or source contract is unsafe."""


@dataclasses.dataclass(frozen=True)
class CentralAliases:
    libraries: frozenset[str]
    plugins: frozenset[str]
    versions: frozenset[str]
    version_refs: Mapping[str, str]
    version_values: Mapping[str, object]

    def __init__(
        self,
        libraries: Iterable[str],
        plugins: Iterable[str],
        versions: Iterable[str],
        version_refs: Mapping[str, str] | None = None,
        version_values: Mapping[str, object] | None = None,
    ) -> None:
        object.__setattr__(self, "libraries", frozenset(libraries))
        object.__setattr__(self, "plugins", frozenset(plugins))
        object.__setattr__(self, "versions", frozenset(versions))
        object.__setattr__(self, "version_refs", dict(version_refs or {}))
        object.__setattr__(self, "version_values", dict(version_values or {}))


@dataclasses.dataclass(frozen=True)
class CatalogMapping:
    repository: str
    subject_kind: str
    coordinate: str
    line_id: str
    authority_id: str
    local_alias: str
    central_alias: str
    disposition: str
    source_path: str
    source_line: int
    local_version_key: str | None
    central_version_key: str | None
    declaration_form: str
    declared_version: str | None = None


@dataclasses.dataclass(frozen=True)
class Replacement:
    path: Path
    before: str
    after: str
    line: int


@dataclasses.dataclass(frozen=True)
class MigrationPlan:
    repository: str
    root: Path
    catalog: Path
    edits: Mapping[Path, str]
    replacements: tuple[Replacement, ...]
    removed_aliases: tuple[str, ...]
    removed_versions: tuple[str, ...]
    blockers: tuple[str, ...]
    structural_preserved: tuple[str, ...]
    used_version_selectors: tuple[tuple[str, str], ...] = ()

    @property
    def replacements_count(self) -> int:
        return len(self.replacements)

    @property
    def changed(self) -> bool:
        return any(
            path.read_text(encoding="utf-8") != text
            for path, text in self.edits.items()
        )


def _authority_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "catalog_authority", CATALOG_AUTHORITY
    )
    if spec is None or spec.loader is None:
        raise MigrationError("cannot load catalog authority parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "catalog_candidate", CATALOG_CANDIDATE
    )
    if spec is None or spec.loader is None:
        raise MigrationError("cannot load catalog candidate parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _promotion_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "catalog_promotion", CATALOG_PROMOTION
    )
    if spec is None or spec.loader is None:
        raise MigrationError("cannot load catalog promotion parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_file(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.resolve() != path:
        raise MigrationError(f"{label} path must be absolute and canonical: {path}")
    try:
        if path.is_symlink() or not path.is_file():
            raise MigrationError(f"{label} must be a regular non-symlink file: {path}")
    except OSError as exc:
        raise MigrationError(f"{label} is not readable: {path}") from exc
    return path


def _read_json(path: Path, label: str) -> Any:
    _canonical_file(path, label)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError(f"invalid {label} JSON: {path}") from exc


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MigrationError(f"{label} must be a non-empty string")
    return value


def _validate_alias(alias: str, label: str) -> None:
    if ALIAS_PATTERN.fullmatch(alias) is None:
        raise MigrationError(f"invalid {label}: {alias}")


def _version_value_fingerprint(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise MigrationError("central version value is not JSON-compatible") from exc


def _validate_inventory(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise MigrationError("inventory must be a list")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise MigrationError(f"inventory record {index} is not an object")
        unknown = sorted(set(item) - INVENTORY_FIELDS)
        missing = sorted(
            {
                "alias",
                "authority-id",
                "coordinate-or-plugin-id",
                "declaration-form",
                "line-id",
                "repository",
                "source-line",
                "source-path",
                "subject-kind",
            }
            - set(item)
        )
        if unknown:
            raise MigrationError(
                f"unknown inventory fields at index {index}: {', '.join(unknown)}"
            )
        if missing:
            raise MigrationError(
                f"missing inventory fields at index {index}: {', '.join(missing)}"
            )
        for field in (
            "alias",
            "authority-id",
            "coordinate-or-plugin-id",
            "line-id",
            "repository",
            "source-path",
        ):
            _require_string(item[field], f"inventory[{index}].{field}")
        if SHA256_PATTERN.fullmatch(item["authority-id"]) is None:
            raise MigrationError(f"invalid inventory authority-id at index {index}")
        if item["subject-kind"] not in {"library", "plugin"}:
            raise MigrationError(f"invalid inventory subject-kind at index {index}")
        if item["declaration-form"] not in {"catalog", "hard-coded"}:
            raise MigrationError(f"invalid inventory declaration-form at index {index}")
        if not isinstance(item["source-line"], int) or item["source-line"] < 1:
            raise MigrationError(f"invalid inventory source-line at index {index}")
        result.append(dict(item))
    return result


def _validate_policy(raw: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    try:
        _promotion_module()._parse_policy(raw)
    except (ValueError, TypeError, KeyError) as exc:
        raise MigrationError(f"invalid policy: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"schema-version", "subjects"}:
        raise MigrationError("invalid policy schema")
    if raw["schema-version"] != 1 or not isinstance(raw["subjects"], list):
        raise MigrationError("policy schema-version must be 1 with subjects")
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, subject in enumerate(raw["subjects"]):
        if not isinstance(subject, dict) or set(subject) != POLICY_SUBJECT_FIELDS:
            raise MigrationError(f"invalid policy subject at index {index}")
        kind = subject["subject-kind"]
        coordinate = _require_string(
            subject["coordinate-or-plugin-id"], f"policy subject {index} coordinate"
        )
        if kind not in {"library", "plugin"} or not isinstance(subject["lines"], list):
            raise MigrationError(f"invalid policy subject at index {index}")
        for line_index, line in enumerate(subject["lines"]):
            if not isinstance(line, dict) or not POLICY_LINE_FIELDS.issuperset(line):
                raise MigrationError(
                    f"invalid policy line at subject {index} line {line_index}"
                )
            if not POLICY_LINE_FIELDS.issuperset(line):
                raise MigrationError(
                    f"unknown policy line fields at subject {index} line {line_index}"
                )
            line_id = _require_string(line.get("line-id"), "policy line-id")
            central_aliases = line.get("central-aliases")
            if not isinstance(central_aliases, list) or not central_aliases:
                raise MigrationError(
                    f"policy line central-aliases must be non-empty at {index}:{line_index}"
                )
            if len(set(central_aliases)) != len(central_aliases):
                raise MigrationError(
                    f"duplicate policy central alias at {index}:{line_index}"
                )
            for alias in central_aliases:
                _validate_alias(
                    _require_string(alias, "policy central alias"),
                    "policy central alias",
                )
            occurrences = line.get("occurrences")
            if not isinstance(occurrences, list):
                raise MigrationError(
                    f"policy line occurrences must be a list at {index}:{line_index}"
                )
            seen_occurrences: set[tuple[str, str]] = set()
            for occurrence in occurrences:
                if (
                    not isinstance(occurrence, dict)
                    or set(occurrence) != POLICY_OCCURRENCE_FIELDS
                ):
                    raise MigrationError(
                        f"invalid policy occurrence at {index}:{line_index}"
                    )
                repo = _require_string(
                    occurrence["repository"], "policy occurrence repository"
                )
                local_alias = _require_string(
                    occurrence["local-alias"], "policy occurrence local alias"
                )
                central_alias = _require_string(
                    occurrence["central-alias"], "policy occurrence central alias"
                )
                if (repo, local_alias) in seen_occurrences:
                    raise MigrationError(
                        f"duplicate policy occurrence at {index}:{line_index}"
                    )
                seen_occurrences.add((repo, local_alias))
                if central_alias not in central_aliases:
                    raise MigrationError(
                        f"policy occurrence central alias is not declared at {index}:{line_index}"
                    )
            key = (kind, coordinate, line_id)
            if key in result:
                raise MigrationError(f"duplicate policy subject line: {key}")
            result[key] = dict(line)
    return result


def _validate_dispositions(raw: Any) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(raw, dict) or set(raw) != {"schema-version", "records"}:
        raise MigrationError("invalid dispositions schema")
    if raw["schema-version"] != 1 or not isinstance(raw["records"], list):
        raise MigrationError("dispositions schema-version must be 1 with records")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    allowed = {
        "central-direct",
        "compatibility-line",
        "central-version-local-alias",
        "bom-managed-versionless",
        "structural-repo-owned",
    }
    for index, item in enumerate(raw["records"]):
        if not isinstance(item, dict):
            raise MigrationError(f"invalid disposition record at index {index}")
        unknown = sorted(set(item) - DISPOSITION_FIELDS)
        if unknown:
            raise MigrationError(
                f"unknown disposition fields at index {index}: {', '.join(unknown)}"
            )
        aid = _require_string(item.get("authority-id"), "disposition authority-id")
        line_id = _require_string(item.get("line-id"), "disposition line-id")
        if SHA256_PATTERN.fullmatch(aid) is None:
            raise MigrationError(f"invalid disposition authority-id at index {index}")
        aliases = item.get("central-aliases")
        if (
            not isinstance(aliases, list)
            or not aliases
            or any(not isinstance(v, str) for v in aliases)
        ):
            raise MigrationError(
                f"invalid disposition central-aliases at index {index}"
            )
        if len(set(aliases)) != len(aliases):
            raise MigrationError(
                f"duplicate disposition central aliases at index {index}"
            )
        disposition = item.get("disposition")
        if disposition not in allowed:
            raise MigrationError(f"invalid disposition at index {index}: {disposition}")
        if not isinstance(item.get("evidence"), dict) or not _require_string(
            item["evidence"].get("type"), "disposition evidence type"
        ):
            raise MigrationError(f"invalid disposition evidence at index {index}")
        _require_string(item["evidence"].get("path"), "disposition evidence path")
        if item.get("status") not in {"pending", "verified"}:
            raise MigrationError(f"invalid disposition status at index {index}")
        _require_string(item.get("owner"), "disposition owner")
        if disposition == "structural-repo-owned":
            _require_string(item.get("repository"), "structural disposition repository")
        key = (aid, line_id)
        if key in result:
            raise MigrationError(f"duplicate disposition pair: {aid}:{line_id}")
        result[key] = dict(item)
    return result


def _validate_version_selectors(
    raw: Any,
    central_versions: Iterable[str],
    *,
    allowed_repositories: Iterable[str] | None = None,
) -> dict[tuple[str, str], str]:
    """Validate explicit selectors for local version accessors.

    A local version key may back multiple central version refs (for example
    ``jmh`` or ``grpc-kotlin``).  Selectors are intentionally external to the
    policy so the operator must name the repository and accessor use-site
    before a replacement can occur.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict) or set(raw) != {"schema-version", "selectors"}:
        raise MigrationError("invalid version selector schema")
    if raw["schema-version"] != 1 or not isinstance(raw["selectors"], list):
        raise MigrationError("version selector schema-version must be 1")
    central_keys = frozenset(central_versions)
    allowed = frozenset(
        allowed_repositories
        if allowed_repositories is not None
        else (REPOSITORY_NAMES[key] for key in REPOSITORY_KEYS)
    )
    result: dict[tuple[str, str], str] = {}
    for index, item in enumerate(raw["selectors"]):
        if not isinstance(item, dict) or set(item) != VERSION_SELECTOR_FIELDS:
            raise MigrationError(f"invalid version selector at index {index}")
        repository = _require_string(item["repository"], "selector repository")
        local_key = _require_string(
            item["local-version-key"], "selector local-version-key"
        )
        central_key = _require_string(
            item["central-version-key"], "selector central-version-key"
        )
        _validate_alias(local_key, "selector local-version-key")
        _validate_alias(central_key, "selector central-version-key")
        if repository not in allowed:
            raise MigrationError(
                f"selector repository is not a managed selected repository: {repository}"
            )
        if central_key not in central_keys:
            raise MigrationError(
                f"selector central version key is absent from central catalog: {central_key}"
            )
        key = (repository, local_key)
        if key in result:
            raise MigrationError(
                f"duplicate version selector: {repository}:{local_key}"
            )
        result[key] = central_key
    return result


def _policy_occurrence(
    record: Mapping[str, Any], line: Mapping[str, Any], disposition: Mapping[str, Any]
) -> str:
    repository = str(record["repository"])
    local_alias = str(record["alias"])
    matches = [
        occurrence
        for occurrence in line["occurrences"]
        if occurrence["repository"] == repository
        and occurrence["local-alias"] == local_alias
    ]
    disposition_aliases = disposition["central-aliases"]
    if len(matches) > 1:
        raise MigrationError(
            f"ambiguous explicit policy occurrence for {repository}:{local_alias}"
        )
    if matches:
        central_alias = matches[0]["central-alias"]
        if central_alias not in disposition_aliases:
            raise MigrationError(
                f"policy/disposition alias mismatch for {repository}:{local_alias}"
            )
        return central_alias
    same_aliases = [alias for alias in disposition_aliases if alias == local_alias]
    if len(same_aliases) == 1:
        return same_aliases[0]
    if len(disposition_aliases) == 1:
        return disposition_aliases[0]
    raise MigrationError(
        f"ambiguous same-alias fallback for {repository}:{local_alias}"
    )


def derive_catalog_mappings(
    inventory: Any,
    policy: Any,
    dispositions: Any,
    central_library_aliases: Iterable[str],
    central_plugin_aliases: Iterable[str],
    central_version_aliases: Iterable[str] = (),
    central_version_refs: Mapping[str, str] | None = None,
) -> tuple[CatalogMapping, ...]:
    """Derive and validate every inventory occurrence's central alias."""
    records = _validate_inventory(inventory)
    policy_lines = _validate_policy(policy)
    disposition_records = _validate_dispositions(dispositions)
    library_aliases = frozenset(central_library_aliases)
    plugin_aliases = frozenset(central_plugin_aliases)
    version_aliases = frozenset(central_version_aliases)
    expected_pairs = {(record["authority-id"], record["line-id"]) for record in records}
    actual_pairs = set(disposition_records)
    missing = expected_pairs - actual_pairs
    orphan = actual_pairs - expected_pairs
    if missing:
        raise MigrationError(f"missing disposition pairs: {len(missing)}")
    if orphan:
        raise MigrationError(f"orphan disposition pairs: {len(orphan)}")

    result: list[CatalogMapping] = []
    for record in records:
        key = (
            record["subject-kind"],
            record["coordinate-or-plugin-id"],
            record["line-id"],
        )
        disposition = disposition_records[(record["authority-id"], record["line-id"])]
        line = policy_lines.get(key)
        if line is None:
            # The policy intentionally stores only non-default decisions.  A
            # missing line is therefore safe only when the disposition itself
            # provides the complete central alias set; ambiguity is rejected by
            # the same-alias fallback below.
            line = {
                "central-aliases": disposition["central-aliases"],
                "occurrences": [],
                "version-key": None,
            }
        central_alias = _policy_occurrence(record, line, disposition)
        aliases = (
            plugin_aliases if record["subject-kind"] == "plugin" else library_aliases
        )
        if central_alias not in aliases:
            raise MigrationError(
                f"central alias is absent from central catalog: {central_alias}"
            )
        if (
            disposition.get("disposition") == "structural-repo-owned"
            and disposition.get("repository") != record["repository"]
        ):
            raise MigrationError(
                f"structural disposition repository mismatch for {record['repository']}"
            )
        central_version_key = line.get("version-key")
        if central_version_key is None and central_version_refs:
            central_version_key = central_version_refs.get(central_alias)
        if central_version_key is not None:
            central_version_key = _require_string(
                central_version_key, "policy version-key"
            )
            if central_version_key not in version_aliases:
                raise MigrationError(
                    f"policy version-key is absent from central catalog: {central_version_key}"
                )
        result.append(
            CatalogMapping(
                repository=record["repository"],
                subject_kind=record["subject-kind"],
                coordinate=record["coordinate-or-plugin-id"],
                line_id=record["line-id"],
                authority_id=record["authority-id"],
                local_alias=record["alias"],
                central_alias=central_alias,
                disposition=disposition["disposition"],
                source_path=record["source-path"],
                source_line=record["source-line"],
                local_version_key=None,
                central_version_key=central_version_key,
                declaration_form=record["declaration-form"],
                declared_version=record.get("declared-version"),
            )
        )
    return tuple(result)


def _catalog_entries(
    catalog: Path,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], int], list[str]]:
    try:
        document = tomllib.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise MigrationError(f"invalid downstream catalog: {catalog}") from exc
    entries: dict[str, dict[str, Any]] = {}
    for section in ("libraries", "plugins"):
        for alias, raw in document.get(section, {}).items():
            if isinstance(raw, str):
                parts = raw.split(":")
                entry = (
                    {"module": ":".join(parts[:2]), "version": parts[2]}
                    if len(parts) == 3
                    else {"module": raw}
                )
            elif isinstance(raw, dict):
                entry = dict(raw)
                version = entry.get("version")
                if isinstance(version, dict) and set(version) == {"ref"}:
                    entry.pop("version")
                    entry["version.ref"] = version["ref"]
            else:
                raise MigrationError(f"invalid downstream {section} alias: {alias}")
            entries[f"{section}:{alias}"] = entry
    lines = catalog.read_text(encoding="utf-8").splitlines(keepends=True)
    current: str | None = None
    positions: dict[tuple[str, str], int] = {}
    for line_number, text in enumerate(lines, start=1):
        section_match = SECTION_PATTERN.match(text.rstrip("\n"))
        if section_match:
            current = section_match.group(1)
            continue
        if current in {"versions", "libraries", "plugins"}:
            match = ASSIGNMENT_PATTERN.match(text)
            if match:
                positions[(current, match.group(1))] = line_number
    return entries, positions, lines


def _entry_coordinate(kind: str, entry: Mapping[str, Any]) -> str | None:
    if kind == "library":
        return entry.get("module") if isinstance(entry.get("module"), str) else None
    return entry.get("id") if isinstance(entry.get("id"), str) else None


def _tracked_build_files(root: Path) -> tuple[Path, ...]:
    try:
        output = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", "*.gradle.kts"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        paths = [
            root / value
            for value in output.splitlines()
            if Path(value).name == "build.gradle.kts"
        ]
    except (OSError, subprocess.CalledProcessError):
        paths = sorted(root.rglob("build.gradle.kts"))
    return tuple(
        path for path in sorted(paths) if path.is_file() and not path.is_symlink()
    )


def _accessor(alias: str) -> str:
    return alias.replace("-", ".")


def _contains_accessor(text: str, token: str) -> bool:
    for match in re.finditer(rf"(?<![A-Za-z0-9_.]){re.escape(token)}", text):
        suffix = text[match.end() :]
        if (
            not suffix
            or suffix[0]
            not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_."
        ):
            return True
        provider = re.match(r"\.([A-Za-z0-9_]+)", suffix)
        if provider is not None and provider.group(1) in ALLOWED_PROVIDER_TAILS:
            return True
    return False


def _catalog_accessor_variants(token: str) -> tuple[str, ...]:
    """Return the standard and root catalog spellings for ``token``."""
    if token == "libs" or token.startswith("libs."):
        return (token, "rootLibs" + token[len("libs") :])
    return (token,)


def _contains_catalog_accessor(text: str, token: str) -> bool:
    """Match a local catalog accessor regardless of its Gradle variable name."""
    return any(
        _contains_accessor(text, variant)
        for variant in _catalog_accessor_variants(token)
    )


def _central_accessor(
    namespace: str,
    alias: str,
    aliases: Iterable[str],
) -> str:
    prefix = "bt4k"
    if namespace == "plugin":
        prefix = "bt4k.plugins"
    elif namespace == "version":
        prefix = "bt4k.versions"
    accessor = _accessor(alias)
    token = f"{prefix}.{accessor}"
    if any(
        other != alias and _accessor(other).startswith(f"{accessor}.")
        for other in aliases
    ):
        return f"{token}.asProvider()"
    return token


def _ensure_root_bt4k_capture(text: str) -> str:
    if re.search(r"(?m)^val rootBt4k\s*=\s*bt4k\s*$", text):
        return text
    anchor = re.compile(r"(?m)^(val rootLibs\s*=\s*libs\s*)$")
    if len(anchor.findall(text)) != 1:
        raise MigrationError("rootLibs migration requires one root catalog capture")
    return anchor.sub(r"\1\nval rootBt4k = bt4k", text, count=1)


def _hard_coded_matches(
    text: str, mapping: CatalogMapping
) -> tuple[tuple[str, str], ...]:
    """Return direct hard-coded declarations matching a mapping's subject."""
    pattern = (
        HARD_CODED_PLUGIN_PATTERN
        if mapping.subject_kind == "plugin"
        else HARD_CODED_LIBRARY_PATTERN
    )
    return tuple(
        (match.group("coordinate"), match.group("version"))
        for match in pattern.finditer(text)
        if match.group("coordinate") == mapping.coordinate
    )


def _hard_coded_adoption_token(mapping: CatalogMapping) -> str:
    if mapping.subject_kind == "plugin":
        return f"bt4k.plugins.{_accessor(mapping.central_alias)}"
    return f"bt4k.{_accessor(mapping.central_alias)}"


def _hard_coded_adoption_present(text: str, mapping: CatalogMapping) -> bool:
    if _contains_accessor(text, _hard_coded_adoption_token(mapping)):
        return True
    version_key = mapping.central_version_key
    if not isinstance(version_key, str) or not version_key:
        return False
    version_accessor = f"bt4k.versions.{_accessor(version_key)}"
    if _contains_accessor(text, version_accessor):
        return True
    return re.search(
        rf"\bbt4kVersion\(\s*['\"]{re.escape(version_key)}['\"]\s*\)",
        text,
    ) is not None


def _classify_hard_coded_mapping(
    root: Path, mapping: CatalogMapping
) -> str | None:
    """Classify a baseline hard-coded occurrence against the current source.

    The inventory is a baseline, so its line number may no longer point at the
    declaration after an earlier migration.  A direct ``bt4k`` accessor in the
    recorded source file is positive adoption proof only after every direct
    literal for the same coordinate has disappeared.  Any changed direct
    literal or otherwise unclassifiable source remains a blocker.
    """
    source = Path(mapping.source_path)
    if source.is_absolute() or ".." in source.parts:
        return (
            "hard-coded declaration location is unsafe to classify: "
            f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
        )
    path = root / source
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError("not a regular file")
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return (
            "hard-coded declaration location cannot be safely classified: "
            f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
        )

    location = (
        lines[mapping.source_line - 1]
        if 1 <= mapping.source_line <= len(lines)
        else None
    )
    declared_version = mapping.declared_version
    expected = (
        (mapping.coordinate, declared_version)
        if isinstance(declared_version, str) and declared_version
        else None
    )
    current_matches = _hard_coded_matches("\n".join(lines), mapping)
    if expected is not None and expected in current_matches:
        return (
            "hard-coded declaration requires manual migration: "
            f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
        )
    if current_matches:
        return (
            "hard-coded declaration changed without catalog adoption: "
            f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
        )
    if _hard_coded_adoption_present("\n".join(lines), mapping):
        return None

    if location is None:
        # A removed line is safe only when the corresponding bt4k accessor is
        # still present in the file.  Otherwise, there is no evidence of what
        # happened to the baseline occurrence.
        return (
            "hard-coded declaration location cannot be safely classified: "
            f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
        )

    if (
        HARD_CODED_PLUGIN_PATTERN.search(location)
        or HARD_CODED_LIBRARY_PATTERN.search(location)
    ):
        return (
            "hard-coded declaration location contains an unmanaged literal: "
            f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
        )
    return (
        "hard-coded declaration location cannot be safely classified: "
        f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
    )


def _replace_tokens(
    text: str,
    mapping: Mapping[tuple[str, str], str],
    *,
    path: Path,
) -> tuple[str, tuple[Replacement, ...], list[str]]:
    replacements: list[Replacement] = []
    blockers: list[str] = []

    def replace_match(match: re.Match[str]) -> str:
        token = match.group(0)
        pieces = [piece.removesuffix("()") for piece in token.split(".")]
        if pieces[0] not in {"libs", "rootLibs"}:
            return token
        namespace = "library"
        start = 1
        if len(pieces) > 1 and pieces[1] in {"plugins", "versions"}:
            namespace = "plugin" if pieces[1] == "plugins" else "version"
            start = 2
        segments = pieces[start:]
        candidates: list[tuple[int, str, str]] = []
        for count in range(len(segments), 0, -1):
            alias = "-".join(segments[:count])
            replacement = mapping.get((namespace, alias))
            if replacement is not None:
                tail = segments[count:]
                if not tail or all(piece in ALLOWED_PROVIDER_TAILS for piece in tail):
                    candidates.append((count, alias, replacement))
        if not candidates:
            return token
        count, alias, replacement = max(candidates)
        # The token may contain an unknown property after a governed alias.  Do
        # not silently rewrite that expression: it is safer to report it.
        if count < len(segments):
            tail = segments[count:]
            if not all(piece in ALLOWED_PROVIDER_TAILS for piece in tail):
                blockers.append(f"unknown accessor tail in {path}: {token}")
                return token
        tail = segments[count:]
        if tail and tail[0] == "asProvider":
            tail = tail[1:]
        if pieces[0] == "rootLibs" and replacement.startswith("bt4k"):
            replacement = "rootBt4k" + replacement[len("bt4k") :]
        new_token = replacement + ("." + ".".join(tail) if tail else "")
        line = text.count("\n", 0, match.start()) + 1
        replacements.append(Replacement(path, token, new_token, line))
        return new_token

    updated = ACCESSOR_TOKEN_PATTERN.sub(replace_match, text)
    return updated, tuple(replacements), blockers


def _remove_line(
    lines: list[str], line_number: int, expected_alias: str, section: str
) -> None:
    if line_number < 1 or line_number > len(lines):
        raise MigrationError(
            f"expected source line is absent for {section}:{expected_alias}"
        )
    text = lines[line_number - 1]
    match = ASSIGNMENT_PATTERN.match(text)
    if match is None or match.group(1) != expected_alias:
        raise MigrationError(
            f"expected source line mismatch for {section}:{expected_alias}"
        )
    lines[line_number - 1] = ""


def _remove_version_line(
    lines: list[str], alias: str, positions: Mapping[tuple[str, str], int]
) -> bool:
    line_number = positions.get(("versions", alias))
    if line_number is None:
        return False
    _remove_line(lines, line_number, alias, "versions")
    return True


def plan_repository(
    repository: str,
    root: Path,
    catalog: Path,
    inventory: Any,
    policy: Any,
    dispositions: Any,
    central_aliases: CentralAliases,
    version_selectors: Mapping[tuple[str, str], str] | None = None,
) -> MigrationPlan:
    """Plan one repository without mutating it."""
    if (
        not root.is_absolute()
        or root.resolve() != root
        or not root.is_dir()
        or root.is_symlink()
    ):
        raise MigrationError(
            f"repository root must be an absolute regular directory: {root}"
        )
    _canonical_file(catalog, "downstream catalog")
    records = _validate_inventory(inventory)
    mappings = derive_catalog_mappings(
        records,
        policy,
        dispositions,
        central_aliases.libraries,
        central_aliases.plugins,
        central_aliases.versions,
        central_aliases.version_refs,
    )
    selected = tuple(
        mapping for mapping in mappings if mapping.repository == repository
    )
    if not selected:
        raise MigrationError(f"repository has no inventory records: {repository}")
    entries, positions, original_lines = _catalog_entries(catalog)
    catalog_lines = list(original_lines)
    catalog_removals: set[tuple[str, str]] = set()
    local_version_to_central: dict[str, set[str]] = {}
    local_alias_version_keys: dict[str, str] = {}
    accessor_mapping: dict[tuple[str, str], str] = {}
    blockers: list[str] = []
    structural_preserved: list[str] = []
    for mapping in selected:
        if mapping.declaration_form == "hard-coded":
            if (
                mapping.disposition == "structural-repo-owned"
                and mapping.source_path == "settings.gradle.kts"
            ):
                structural_preserved.append(
                    f"{mapping.source_path}:{mapping.source_line}:{mapping.coordinate}"
                )
            else:
                blocker = _classify_hard_coded_mapping(root, mapping)
                if blocker is not None:
                    blockers.append(blocker)
            continue
        section = "libraries" if mapping.subject_kind == "library" else "plugins"
        entry_key = f"{section}:{mapping.local_alias}"
        entry = entries.get(entry_key)
        if entry is not None:
            coordinate = _entry_coordinate(mapping.subject_kind, entry)
            if coordinate != mapping.coordinate:
                raise MigrationError(
                    f"catalog coordinate mismatch for {repository}:{mapping.local_alias}: {coordinate!r} != {mapping.coordinate!r}"
                )
            expected_line = positions.get((section, mapping.local_alias))
            if expected_line != mapping.source_line:
                raise MigrationError(
                    f"expected source line mismatch for {section}:{mapping.local_alias}: {mapping.source_line} != {expected_line}"
                )
            catalog_removals.add((section, mapping.local_alias))
            local_version_key = entry.get("version.ref")
            if isinstance(local_version_key, str):
                local_alias_version_keys[mapping.local_alias] = local_version_key
                local_version_to_central.setdefault(local_version_key, set()).add(
                    mapping.central_version_key or mapping.central_alias
                )
        elif mapping.local_alias in {
            key.split(":", 1)[1] for key in entries if key.startswith(f"{section}:")
        }:
            raise MigrationError(
                f"catalog alias section mismatch for {section}:{mapping.local_alias}"
            )
        central_namespace_aliases = (
            central_aliases.libraries
            if mapping.subject_kind == "library"
            else central_aliases.plugins
        )
        accessor_mapping[(mapping.subject_kind, mapping.local_alias)] = (
            _central_accessor(
                mapping.subject_kind,
                mapping.central_alias,
                central_namespace_aliases,
            )
        )

    selectors = dict(version_selectors or {})
    ambiguous_version_keys: dict[str, set[str]] = {}
    selected_version_keys: set[str] = set()
    used_version_selectors: set[tuple[str, str]] = set()
    for selector_repository, selector_key in selectors:
        if selector_repository != repository:
            continue
        central_candidates = local_version_to_central.get(selector_key)
        if central_candidates is None:
            raise MigrationError(
                f"orphan version selector local key: "
                f"{selector_repository}:{selector_key}"
            )
        if len(central_candidates) == 1:
            raise MigrationError(
                f"orphan version selector for unambiguous local key: "
                f"{selector_repository}:{selector_key}"
            )
    for local_version_key, central_keys in local_version_to_central.items():
        if len(central_keys) != 1:
            selector = selectors.get((repository, local_version_key))
            if selector is None:
                ambiguous_version_keys[local_version_key] = central_keys
                continue
            if selector not in central_keys:
                raise MigrationError(
                    f"version selector does not match local ambiguity: "
                    f"{repository}:{local_version_key} -> {selector}"
                )
            try:
                candidate_values = {
                    _version_value_fingerprint(
                        central_aliases.version_values[central_key]
                    )
                    for central_key in central_keys
                }
            except KeyError as exc:
                raise MigrationError(
                    f"central version value is absent from catalog: {exc.args[0]}"
                ) from exc
            if len(candidate_values) != 1:
                raise MigrationError(
                    f"ambiguous local version requires occurrence-scoped selector "
                    f"when central values differ: {repository}:{local_version_key}"
                )
            accessor_mapping[("version", local_version_key)] = (
                _central_accessor("version", selector, central_aliases.versions)
            )
            selected_version_keys.add(local_version_key)
            used_version_selectors.add((repository, local_version_key))
            continue
        accessor_mapping[("version", local_version_key)] = (
            _central_accessor(
                "version", next(iter(central_keys)), central_aliases.versions
            )
        )

    edits: dict[Path, str] = {}
    replacements: list[Replacement] = []
    for path in _tracked_build_files(root):
        current = path.read_text(encoding="utf-8")
        for alias in sorted(
            {
                mapping.local_alias
                for mapping in selected
                if mapping.declaration_form == "catalog"
            }
        ):
            if (
                DYNAMIC_LIBRARY_PATTERN.search(current.replace("\n", " "))
                and f'"{alias}"' in current
            ):
                blockers.append(
                    f"dynamic library accessor requires manual migration: {path}:{alias}"
                )
            if (
                DYNAMIC_VERSION_PATTERN.search(current.replace("\n", " "))
                and f'"{alias}"' in current
            ):
                blockers.append(
                    f"dynamic version accessor requires manual migration: {path}:{alias}"
                )
        updated, found, token_blockers = _replace_tokens(
            current, accessor_mapping, path=path
        )
        if any(item.before.startswith("rootLibs.") for item in found):
            if path != root / "build.gradle.kts":
                token_blockers.append(
                    f"rootLibs accessor outside root build requires manual migration: {path}"
                )
            else:
                updated = _ensure_root_bt4k_capture(updated)
        replacements.extend(found)
        blockers.extend(token_blockers)
        if updated != current:
            edits[path] = updated

    build_texts_after_replacements = [
        edits.get(path, path.read_text(encoding="utf-8"))
        for path in _tracked_build_files(root)
    ]
    for local_version_key, central_keys in sorted(ambiguous_version_keys.items()):
        token = f"libs.versions.{_accessor(local_version_key)}"
        if any(
            _contains_catalog_accessor(text, token)
            for text in build_texts_after_replacements
        ):
            blockers.append(
                f"ambiguous local version accessor mapping: {local_version_key} -> {','.join(sorted(central_keys))}"
            )

    # Refuse catalog deletion when dynamic or ambiguous references remain.
    if blockers and any(
        "dynamic" in item or "unknown accessor tail" in item for item in blockers
    ):
        catalog_removals.clear()
    ambiguous_aliases = {
        mapping.local_alias
        for mapping in selected
        if local_alias_version_keys.get(mapping.local_alias) in ambiguous_version_keys
    }
    if any("ambiguous local version" in item for item in blockers):
        ambiguous_removals = {
            (section, alias)
            for section, alias in catalog_removals
            if alias in ambiguous_aliases
        }
        catalog_removals.difference_update(ambiguous_removals)

    for section, alias in sorted(catalog_removals):
        line_number = positions.get((section, alias))
        if line_number is not None:
            _remove_line(catalog_lines, line_number, alias, section)

    # Version keys are removable only after all catalog references disappear.
    simulated_catalog = "".join(catalog_lines)
    try:
        simulated_document = tomllib.loads(simulated_catalog)
    except tomllib.TOMLDecodeError as exc:
        raise MigrationError(
            f"catalog migration would produce invalid TOML: {catalog}"
        ) from exc
    remaining_refs: set[str] = set()
    for section in ("libraries", "plugins"):
        for value in simulated_document.get(section, {}).values():
            if isinstance(value, dict):
                ref = (
                    value.get("version", {}).get("ref")
                    if isinstance(value.get("version"), dict)
                    else value.get("version.ref")
                )
                if isinstance(ref, str):
                    remaining_refs.add(ref)
    build_texts = [
        edits.get(path, path.read_text(encoding="utf-8"))
        for path in _tracked_build_files(root)
    ]
    removed_versions: list[str] = []
    for local_key, central_keys in sorted(local_version_to_central.items()):
        if (
            (len(central_keys) == 1 or local_key in selected_version_keys)
            and local_key not in remaining_refs
            and not any(
                _contains_catalog_accessor(
                    text, f"libs.versions.{_accessor(local_key)}"
                )
                for text in build_texts
            )
            and _remove_version_line(catalog_lines, local_key, positions)
        ):
            removed_versions.append(local_key)
    if catalog_lines != original_lines:
        edits[catalog] = "".join(catalog_lines)

    # A governed local accessor must be absent from every tracked build file
    # after replacements.  Unknown local catalog aliases are intentionally not
    # considered governed and remain untouched.
    for path in _tracked_build_files(root):
        text = edits.get(path, path.read_text(encoding="utf-8"))
        for kind, local_alias in accessor_mapping:
            prefix = "libs" if kind == "library" else f"libs.{kind}s"
            token = f"{prefix}.{_accessor(local_alias)}"
            if _contains_catalog_accessor(text, token):
                blockers.append(f"governed local accessor remains: {path}:{token}")

    return MigrationPlan(
        repository=repository,
        root=root,
        catalog=catalog,
        edits=dict(sorted(edits.items(), key=lambda item: str(item[0]))),
        replacements=tuple(
            sorted(
                replacements,
                key=lambda item: (str(item.path), item.line, item.before, item.after),
            )
        ),
        removed_aliases=tuple(sorted(alias for _, alias in catalog_removals if alias)),
        removed_versions=tuple(sorted(removed_versions)),
        blockers=tuple(sorted(set(blockers))),
        structural_preserved=tuple(sorted(set(structural_preserved))),
        used_version_selectors=tuple(sorted(used_version_selectors)),
    )


def apply_plan(plan: MigrationPlan) -> None:
    """Apply a previously validated plan atomically enough for local worktrees."""
    if plan.blockers:
        raise MigrationError(
            f"migration plan has {len(plan.blockers)} unresolved blockers: "
            f"{plan.repository}"
        )
    for path in plan.edits:
        if path.is_symlink() or not path.is_file():
            raise MigrationError(f"migration target is not a regular file: {path}")
    for path, text in plan.edits.items():
        path.write_text(text, encoding="utf-8")


def _load_repository_map(path: Path, workspace: Path) -> dict[str, tuple[Path, Path]]:
    _canonical_file(path, "repository map")
    raw = _read_json(path, "repository map")
    if (
        not isinstance(raw, dict)
        or set(raw) != {"schema_version", "central", "repositories"}
        or raw["schema_version"] != 1
    ):
        raise MigrationError("invalid repository map schema")
    central = raw["central"]
    repos = raw["repositories"]
    if (
        not isinstance(central, dict)
        or not isinstance(repos, dict)
        or set(repos) != set(REPOSITORY_KEYS)
    ):
        raise MigrationError(
            "repository map must contain the canonical nine repositories"
        )
    candidate = _candidate_module()
    if (
        not workspace.is_absolute()
        or workspace.resolve() != workspace
        or not workspace.is_dir()
        or workspace.is_symlink()
    ):
        raise MigrationError(
            f"workspace must be an absolute regular directory: {workspace}"
        )
    try:
        loaded = candidate.load_repository_map_v1(path, workspace)
    except (RuntimeError, OSError) as exc:
        raise MigrationError(str(exc)) from exc
    return {item.key: (item.root, item.catalog) for item in loaded[1:]}


def _central_aliases(path: Path) -> CentralAliases:
    authority = _authority_module()
    try:
        data = authority.parse_catalog(path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MigrationError(f"invalid central catalog: {path}") from exc
    version_refs: dict[str, str] = {}
    for alias, entry in (*data.libraries.items(), *data.plugins.items()):
        ref = entry.get("version.ref")
        if isinstance(ref, str):
            version_refs[alias] = ref
    return CentralAliases(
        data.libraries,
        data.plugins,
        data.versions,
        version_refs,
        data.versions,
    )


def _summary(plan: MigrationPlan) -> dict[str, Any]:
    return {
        "repository": plan.repository,
        "changed-files": [str(path) for path in sorted(plan.edits)],
        "replacements": plan.replacements_count,
        "removed-aliases": list(plan.removed_aliases),
        "removed-versions": list(plan.removed_versions),
        "blockers": list(plan.blockers),
        "structural-preserved": list(plan.structural_preserved),
        "status": "PENDING"
        if plan.blockers
        else ("DONE" if not plan.changed else "READY"),
    }


def _print_summaries(plans: Iterable[MigrationPlan], fmt: str) -> None:
    summaries = [_summary(plan) for plan in plans]
    if fmt == "json":
        print(
            json.dumps(
                summaries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )
        return
    for summary in summaries:
        print(
            f"{summary['repository']}: {summary['status']} "
            f"files={len(summary['changed-files'])} replacements={summary['replacements']} "
            f"aliases={len(summary['removed-aliases'])} versions={len(summary['removed-versions'])} "
            f"blockers={len(summary['blockers'])} structural-preserved={len(summary['structural-preserved'])}"
        )
        for blocker in summary["blockers"]:
            print(f"  BLOCKER: {blocker}")
    print("OK" if all(not plan.blockers for plan in plans) else "PENDING")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--dispositions", required=True, type=Path)
    parser.add_argument("--repository-map", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--central-catalog",
        "--catalog",
        dest="central_catalog",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--version-selectors",
        type=Path,
        help="Explicit repository/local-version to central-version selectors",
    )
    parser.add_argument("--repo", action="append", dest="repositories")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if args.write and args.check:
        mode = "write-check"
    elif args.write:
        mode = "write"
    elif args.check:
        mode = "check"
    else:
        parser.error("one of --write or --check is required")
    try:
        inventory = _read_json(args.inventory, "inventory")
        policy = _read_json(args.policy, "policy")
        dispositions = _read_json(args.dispositions, "dispositions")
        repository_map = _load_repository_map(args.repository_map, args.workspace)
        central_catalog = _canonical_file(args.central_catalog, "central catalog")
        expected_central = _canonical_file(
            Path(
                _read_json(args.repository_map, "repository map")["central"]["catalog"]
            ),
            "mapped central catalog",
        )
        if expected_central != central_catalog:
            raise MigrationError("central catalog does not match repository map")
        aliases = _central_aliases(central_catalog)
        names = {key: REPOSITORY_NAMES[key] for key in REPOSITORY_KEYS}
        requested = args.repositories or list(REPOSITORY_KEYS)
        selected_keys: list[str] = []
        for requested_name in requested:
            key = requested_name
            if key not in REPOSITORY_KEYS:
                key = next(
                    (
                        candidate
                        for candidate, name in names.items()
                        if name == requested_name
                    ),
                    "",
                )
            if key not in REPOSITORY_KEYS:
                raise MigrationError(f"unknown managed repository: {requested_name}")
            if key not in selected_keys:
                selected_keys.append(key)
        selector_document = (
            _read_json(args.version_selectors, "version selectors")
            if args.version_selectors is not None
            else None
        )
        version_selectors = _validate_version_selectors(
            selector_document,
            aliases.versions,
            allowed_repositories=(REPOSITORY_NAMES[key] for key in selected_keys),
        )
        records = _validate_inventory(inventory)
        plans: list[MigrationPlan] = []
        for key in selected_keys:
            root, catalog = repository_map[key]
            plans.append(
                plan_repository(
                    REPOSITORY_NAMES[key],
                    root,
                    catalog,
                    records,
                    policy,
                    dispositions,
                    aliases,
                    version_selectors,
                )
            )
        consumed_selectors = {
            selector
            for plan in plans
            for selector in plan.used_version_selectors
        }
        unused_selectors = sorted(set(version_selectors) - consumed_selectors)
        if unused_selectors:
            raise MigrationError(
                "unused or orphan version selectors: "
                + ", ".join(f"{repo}:{key}" for repo, key in unused_selectors)
            )
        if mode in {"write", "write-check"}:
            blocked = [plan for plan in plans if plan.blockers]
            if blocked:
                details = ", ".join(
                    f"{plan.repository}={len(plan.blockers)}" for plan in blocked
                )
                raise MigrationError(
                    f"migration plans have unresolved blockers: {details}"
                )
            for plan in plans:
                apply_plan(plan)
            if mode == "write-check":
                # Replanning against the same source proves idempotence without
                # reloading the baseline map after it becomes dirty.  Explicit
                # selectors are migration-time disambiguators for local version
                # keys that no longer exist after a successful write, so they
                # must not be revalidated against the migrated catalogs.
                plans = [
                    plan_repository(
                        REPOSITORY_NAMES[key],
                        *repository_map[key],
                        records,
                        policy,
                        dispositions,
                        aliases,
                        {},
                    )
                    for key in selected_keys
                ]
        _print_summaries(plans, args.format)
        if mode == "check" and any(plan.changed for plan in plans):
            return 1
        if any(plan.blockers for plan in plans):
            return 1
        return 0
    except (
        MigrationError,
        OSError,
        UnicodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
