#!/usr/bin/env python3
"""Promote reviewed dependency authority into the central Gradle catalog.

The input policy is deliberately small and explicit.  A policy subject has one
or more compatibility lines; each line names the central aliases and maps every
downstream occurrence (repository plus local alias) to one of those aliases.
Subjects that are absent from the policy are admitted only when a deterministic
single-version catalog default can be derived.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCRIPT_NAME = "scripts/promote-catalog-authority.py"
AUTHORITY_PATH = Path(__file__).resolve().with_name("catalog_authority.py")
AUTHORITY_SPEC = importlib.util.spec_from_file_location(
    "promotion_catalog_authority", AUTHORITY_PATH
)
if AUTHORITY_SPEC is None or AUTHORITY_SPEC.loader is None:
    raise RuntimeError(f"Cannot load {AUTHORITY_PATH}")
catalog_authority = importlib.util.module_from_spec(AUTHORITY_SPEC)
sys.modules.setdefault("promotion_catalog_authority", catalog_authority)
try:
    AUTHORITY_SPEC.loader.exec_module(catalog_authority)
except ModuleNotFoundError as exc:
    if exc.name != "tomllib":
        raise
    catalog_authority = None

SOURCE_END = "# </shared-version-source-of-truth>"
EXTERNAL_END = "# </external-managed-modules by dependency governance>"
VERSIONS_START = f"# <generated-central-authority-versions by {SCRIPT_NAME}>"
VERSIONS_END = "# </generated-central-authority-versions>"
PLUGINS_START = f"# <generated-central-authority-plugins by {SCRIPT_NAME}>"
PLUGINS_END = "# </generated-central-authority-plugins>"
LIBRARIES_START = f"# <generated-central-authority-libraries by {SCRIPT_NAME}>"
LIBRARIES_END = "# </generated-central-authority-libraries>"

ALIAS_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*$")
LINE_PATTERN = re.compile(r"(?:default|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}$")
RESERVED_ACCESSOR_NAMESPACES = {"bundles", "plugins", "versions"}
KOTLIN_RESERVED_WORDS = {
    "as",
    "break",
    "class",
    "continue",
    "do",
    "else",
    "false",
    "for",
    "fun",
    "if",
    "in",
    "interface",
    "is",
    "null",
    "object",
    "package",
    "return",
    "super",
    "this",
    "throw",
    "true",
    "try",
    "typealias",
    "typeof",
    "val",
    "var",
    "when",
    "while",
}
DISPOSITION_EVIDENCE_TYPES = {
    "central-direct": {"catalog-alias"},
    "central-version-local-alias": {"catalog-version"},
    "bom-managed-versionless": {"publication-pom"},
    "compatibility-line": {"compatibility-review"},
    "structural-repo-owned": {"settings-evaluation"},
}


class PromotionError(ValueError):
    """Raised when the authority inputs are not deterministic."""


@dataclasses.dataclass(frozen=True)
class EffectiveLine:
    subject_kind: str
    coordinate: str
    line_id: str
    version: str | None
    version_key: str | None
    aliases: tuple[str, ...]
    occurrence_keys: tuple[tuple[str, str], ...]
    disposition: str
    evidence: dict[str, Any]
    metadata: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class PromotionResult:
    catalog: str
    dispositions: dict[str, Any]


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError(f"invalid {label}: {path}") from exc


def _require_fields(value: dict[str, Any], allowed: set[str], context: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise PromotionError(
            f"unexpected policy fields at {context}: {', '.join(unexpected)}"
        )


def _require_text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise PromotionError(f"{context} must be a non-empty string")
    return value


def _validate_alias(alias: str, context: str) -> None:
    if not ALIAS_PATTERN.fullmatch(alias):
        raise PromotionError(f"invalid central alias at {context}: {alias}")
    if alias.split(".")[0].split("-")[0].split("_")[0] in RESERVED_ACCESSOR_NAMESPACES:
        raise PromotionError(f"reserved accessor namespace at {context}: {alias}")


def _validate_accessor_aliases(
    libraries: set[str], plugins: set[str], versions: set[str]
) -> None:
    if catalog_authority is not None:
        catalog_authority.validate_accessor_aliases(
            libraries=libraries,
            plugins=plugins,
            versions=versions,
        )
        return

    owners: dict[tuple[str, ...], tuple[str, str]] = {}
    for tree, prefix, aliases in (
        ("library", (), libraries),
        ("plugin", ("plugins",), plugins),
        ("version", ("versions",), versions),
    ):
        for alias in aliases:
            if ALIAS_PATTERN.fullmatch(alias) is None:
                raise ValueError(f"invalid accessor alias: {alias}")
            normalized = tuple(alias.split("-"))
            if any(part in KOTLIN_RESERVED_WORDS for part in normalized):
                raise ValueError(f"Kotlin reserved word in accessor alias: {alias}")
            if tree == "library" and normalized[0] in RESERVED_ACCESSOR_NAMESPACES:
                raise ValueError(f"reserved accessor namespace: {alias}")
            accessor = prefix + normalized
            previous = owners.get(accessor)
            if previous is not None:
                raise ValueError(
                    "cross-tree accessor collision: "
                    f"{previous[0]} {previous[1]} and {tree} {alias}"
                )
            owners[accessor] = (tree, alias)


def _validate_line_id(line_id: str, context: str) -> None:
    if not LINE_PATTERN.fullmatch(line_id):
        raise PromotionError(f"invalid line-id at {context}: {line_id}")


def _inventory_records(inventory: Any) -> list[dict[str, Any]]:
    if not isinstance(inventory, list):
        raise PromotionError("inventory must be a list of occurrence records")
    records: list[dict[str, Any]] = []
    required = {
        "authority-id",
        "line-id",
        "repository",
        "subject-kind",
        "coordinate-or-plugin-id",
        "alias",
        "declared-version",
        "declaration-form",
    }
    for index, raw in enumerate(inventory):
        if not isinstance(raw, dict):
            raise PromotionError(f"invalid inventory record at index {index}")
        missing = sorted(required - set(raw))
        if missing:
            raise PromotionError(
                f"inventory record {index} is missing fields: {', '.join(missing)}"
            )
        record = dict(raw)
        authority_id = _require_text(
            record["authority-id"], f"inventory[{index}].authority-id"
        )
        if not SHA256_PATTERN.fullmatch(authority_id):
            raise PromotionError(f"invalid authority-id at inventory index {index}")
        line_id = _require_text(record["line-id"], f"inventory[{index}].line-id")
        _validate_line_id(line_id, f"inventory[{index}]")
        kind = record["subject-kind"]
        if kind not in {"library", "plugin"}:
            raise PromotionError(f"invalid subject-kind at inventory index {index}")
        for field in ("repository", "coordinate-or-plugin-id", "alias"):
            _require_text(record[field], f"inventory[{index}].{field}")
        if record["declared-version"] is not None and not isinstance(
            record["declared-version"], str
        ):
            raise PromotionError(f"invalid declared-version at inventory index {index}")
        if record["declaration-form"] not in {"catalog", "hard-coded"}:
            raise PromotionError(f"invalid declaration-form at inventory index {index}")
        records.append(record)
    return records


def _parse_policy(policy: Any) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if not isinstance(policy, dict) or set(policy) != {"schema-version", "subjects"}:
        raise PromotionError("policy must contain exactly schema-version and subjects")
    if policy["schema-version"] != 1 or not isinstance(policy["subjects"], list):
        raise PromotionError("unsupported policy schema")
    subjects: dict[tuple[str, str], list[dict[str, Any]]] = {}
    subject_fields = {"subject-kind", "coordinate-or-plugin-id", "lines"}
    line_fields = {
        "line-id",
        "version",
        "version-key",
        "central-aliases",
        "occurrences",
        "disposition",
        "evidence",
        "owner",
        "status",
        "repository",
        "issue",
        "review-by",
    }
    occurrence_fields = {"repository", "local-alias", "central-alias"}
    for subject_index, raw_subject in enumerate(policy["subjects"]):
        if not isinstance(raw_subject, dict):
            raise PromotionError(f"invalid policy subject at index {subject_index}")
        _require_fields(raw_subject, subject_fields, f"subjects[{subject_index}]")
        kind = raw_subject.get("subject-kind")
        if kind not in {"library", "plugin"}:
            raise PromotionError(
                f"invalid policy subject-kind at index {subject_index}"
            )
        coordinate = _require_text(
            raw_subject.get("coordinate-or-plugin-id"),
            f"subjects[{subject_index}].coordinate-or-plugin-id",
        )
        key = (kind, coordinate)
        if key in subjects:
            raise PromotionError(f"duplicate policy subject: {kind}:{coordinate}")
        raw_lines = raw_subject.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise PromotionError(f"policy subject has no lines: {kind}:{coordinate}")
        lines: list[dict[str, Any]] = []
        seen_line_ids: set[str] = set()
        for line_index, raw_line in enumerate(raw_lines):
            if not isinstance(raw_line, dict):
                raise PromotionError(f"invalid policy line at {kind}:{coordinate}")
            _require_fields(
                raw_line,
                line_fields,
                f"subjects[{subject_index}].lines[{line_index}]",
            )
            line_id = _require_text(raw_line.get("line-id"), "policy line-id")
            _validate_line_id(line_id, f"{kind}:{coordinate}")
            if line_id in seen_line_ids:
                raise PromotionError(
                    f"duplicate policy line: {kind}:{coordinate}:{line_id}"
                )
            seen_line_ids.add(line_id)
            version = raw_line.get("version")
            if version is not None:
                _require_text(
                    version, f"policy line version {kind}:{coordinate}:{line_id}"
                )
                if any(token in version for token in ("+", "[", "]", "(", ")")):
                    raise PromotionError(f"dynamic policy version: {version}")
            version_key = raw_line.get("version-key")
            if version_key is not None:
                version_key = _require_text(version_key, "policy version-key")
                _validate_alias(
                    version_key, f"{kind}:{coordinate}:{line_id} version-key"
                )
            if version is not None and version_key is None:
                raise PromotionError(
                    "exact policy version requires version-key: "
                    f"{kind}:{coordinate}:{line_id}"
                )
            if version is None and version_key is not None:
                raise PromotionError(
                    "versionless policy line cannot declare version-key: "
                    f"{kind}:{coordinate}:{line_id}"
                )
            raw_aliases = raw_line.get("central-aliases")
            if not isinstance(raw_aliases, list) or not raw_aliases:
                raise PromotionError(
                    f"missing central-aliases: {kind}:{coordinate}:{line_id}"
                )
            aliases: list[str] = []
            for alias in raw_aliases:
                alias = _require_text(alias, "central alias")
                _validate_alias(alias, f"{kind}:{coordinate}:{line_id}")
                if alias in aliases:
                    raise PromotionError(f"duplicate central alias: {alias}")
                aliases.append(alias)
            raw_occurrences = raw_line.get("occurrences")
            if not isinstance(raw_occurrences, list) or not raw_occurrences:
                raise PromotionError(
                    f"missing occurrence selectors: {kind}:{coordinate}:{line_id}"
                )
            occurrences: list[dict[str, str]] = []
            seen_occurrences: set[tuple[str, str]] = set()
            for occurrence_index, raw_occurrence in enumerate(raw_occurrences):
                if not isinstance(raw_occurrence, dict):
                    raise PromotionError("invalid occurrence selector")
                _require_fields(
                    raw_occurrence,
                    occurrence_fields,
                    f"{kind}:{coordinate}:{line_id}.occurrences[{occurrence_index}]",
                )
                occurrence = {
                    field: _require_text(
                        raw_occurrence.get(field), f"occurrence {field}"
                    )
                    for field in occurrence_fields
                }
                if occurrence["central-alias"] not in aliases:
                    raise PromotionError(
                        "occurrence selector uses undeclared central alias: "
                        f"{occurrence['central-alias']}"
                    )
                occurrence_key = (occurrence["repository"], occurrence["local-alias"])
                if occurrence_key in seen_occurrences:
                    raise PromotionError(
                        f"duplicate occurrence selector: {occurrence_key}"
                    )
                seen_occurrences.add(occurrence_key)
                occurrences.append(occurrence)
            disposition = _require_text(
                raw_line.get("disposition"), "policy disposition"
            )
            evidence = raw_line.get("evidence")
            if disposition not in DISPOSITION_EVIDENCE_TYPES:
                raise PromotionError(f"invalid policy disposition: {disposition}")
            if not isinstance(evidence, dict) or set(evidence) != {"type", "path"}:
                raise PromotionError(f"invalid policy evidence for {disposition}")
            evidence_type = _require_text(evidence.get("type"), "policy evidence type")
            evidence_path = _require_text(evidence.get("path"), "policy evidence path")
            if evidence_type not in DISPOSITION_EVIDENCE_TYPES[disposition]:
                raise PromotionError(
                    f"invalid evidence type for {disposition}: {evidence_type}"
                )
            metadata = {
                field: raw_line[field]
                for field in ("owner", "status", "repository", "issue", "review-by")
                if field in raw_line
            }
            lines.append(
                {
                    "line-id": line_id,
                    "version": version,
                    "version-key": version_key,
                    "central-aliases": aliases,
                    "occurrences": occurrences,
                    "disposition": disposition,
                    "evidence": {"type": evidence_type, "path": evidence_path},
                    "metadata": metadata,
                }
            )
        subjects[key] = lines
    return subjects


def _identity_alias_collisions(records: list[dict[str, Any]]) -> set[tuple[str, str]]:
    seen: dict[tuple[str, str], set[str]] = {}
    for record in records:
        key = (record["subject-kind"], record["alias"])
        seen.setdefault(key, set()).add(record["coordinate-or-plugin-id"])
    return {key for key, coordinates in seen.items() if len(coordinates) > 1}


def _default_line(
    subject: tuple[str, str],
    records: list[dict[str, Any]],
    collisions: set[tuple[str, str]],
) -> EffectiveLine:
    kind, coordinate = subject
    if any(record["declaration-form"] != "catalog" for record in records):
        raise PromotionError(
            f"missing explicit policy for hard-coded subject: {kind}:{coordinate}"
        )
    versions = {record["declared-version"] for record in records}
    if len(versions) != 1 or None in versions:
        raise PromotionError(
            f"missing explicit policy for multi-version subject: {kind}:{coordinate}"
        )
    line_ids = {record["line-id"] for record in records}
    if len(line_ids) != 1:
        raise PromotionError(
            f"missing explicit policy for compatibility lines: {kind}:{coordinate}"
        )
    aliases = sorted({record["alias"] for record in records})
    if not aliases or any((kind, alias) in collisions for alias in aliases):
        raise PromotionError(
            f"missing explicit policy for alias identity collision: {kind}:{coordinate}"
        )
    for alias in aliases:
        _validate_alias(alias, f"default {kind}:{coordinate}")
    identity = f"{kind}\0{coordinate}\0{next(iter(line_ids))}".encode()
    digest = hashlib.sha256(identity).hexdigest()[:12]
    version_key = f"managed-{aliases[0]}-h{digest}"
    return EffectiveLine(
        subject_kind=kind,
        coordinate=coordinate,
        line_id=next(iter(line_ids)),
        version=next(iter(versions)),
        version_key=version_key,
        aliases=tuple(aliases),
        occurrence_keys=tuple(
            sorted((record["repository"], record["alias"]) for record in records)
        ),
        disposition="central-direct",
        evidence={"type": "catalog-alias", "path": "gradle/libs.versions.toml"},
        metadata={},
    )


def _effective_lines(
    records: list[dict[str, Any]],
    policy_subjects: dict[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[EffectiveLine], dict[tuple[str, str, str], EffectiveLine]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(
            (record["subject-kind"], record["coordinate-or-plugin-id"]), []
        ).append(record)
    inventory_subjects = set(grouped)
    orphan_subjects = sorted(set(policy_subjects) - inventory_subjects)
    if orphan_subjects:
        raise PromotionError(
            "orphan policy subjects: "
            + ", ".join(f"{kind}:{coordinate}" for kind, coordinate in orphan_subjects)
        )
    collisions = _identity_alias_collisions(records)
    effective: list[EffectiveLine] = []
    matched: dict[tuple[str, str, str], EffectiveLine] = {}
    for subject in sorted(inventory_subjects):
        subject_records = grouped[subject]
        raw_lines = policy_subjects.get(subject)
        if raw_lines is None:
            line = _default_line(subject, subject_records, collisions)
            effective.append(line)
            for record in subject_records:
                matched[
                    (record["repository"], record["alias"], record["authority-id"])
                ] = line
            continue
        used_records: set[int] = set()
        for raw_line in raw_lines:
            selectors = {
                (item["repository"], item["local-alias"]): item
                for item in raw_line["occurrences"]
            }
            selected_indices: list[int] = []
            for index, record in enumerate(subject_records):
                selector = (record["repository"], record["alias"])
                if selector in selectors:
                    if index in used_records:
                        raise PromotionError(
                            f"ambiguous occurrence selector: {selector}"
                        )
                    selected_indices.append(index)
            orphan_selectors = sorted(
                set(selectors)
                - {
                    (
                        subject_records[index]["repository"],
                        subject_records[index]["alias"],
                    )
                    for index in selected_indices
                }
            )
            if orphan_selectors:
                raise PromotionError(
                    f"orphan occurrence selector: {orphan_selectors[0]}"
                )
            if not selected_indices:
                raise PromotionError(
                    "policy line has no matching occurrence: "
                    f"{subject}:{raw_line['line-id']}"
                )
            used_records.update(selected_indices)
            aliases = tuple(raw_line["central-aliases"])
            line = EffectiveLine(
                subject_kind=subject[0],
                coordinate=subject[1],
                line_id=raw_line["line-id"],
                version=raw_line["version"],
                version_key=raw_line["version-key"],
                aliases=aliases,
                occurrence_keys=tuple(sorted(selectors)),
                disposition=raw_line["disposition"],
                evidence=dict(raw_line["evidence"]),
                metadata=dict(raw_line["metadata"]),
            )
            effective.append(line)
            for index in selected_indices:
                record = subject_records[index]
                if record["line-id"] != line.line_id:
                    raise PromotionError(
                        "policy line-id does not match inventory: "
                        f"{subject}:{line.line_id}"
                    )
                matched[
                    (record["repository"], record["alias"], record["authority-id"])
                ] = line
        if len(used_records) != len(subject_records):
            missing_record = subject_records[
                next(
                    index
                    for index in range(len(subject_records))
                    if index not in used_records
                )
            ]
            raise PromotionError(
                "missing occurrence selector: "
                f"{missing_record['repository']}:{missing_record['alias']}"
            )
    if any(
        (record["repository"], record["alias"], record["authority-id"]) not in matched
        for record in records
    ):
        raise PromotionError("missing occurrence selector")
    return effective, matched


def _parse_catalog(
    catalog: str,
) -> dict[str, dict[str, dict[str, str | None]] | dict[str, str]]:
    sections: dict[str, Any] = {"versions": {}, "plugins": {}, "libraries": {}}
    section: str | None = None
    for raw_line in catalog.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section not in sections or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not ALIAS_PATTERN.fullmatch(key):
            continue
        raw_value = raw_value.split("#", 1)[0].strip()
        if section == "versions":
            match = re.search(r'"([^"]*)"', raw_value)
            if match:
                sections[section][key] = match.group(1)
            continue
        entry: dict[str, str | None] = {
            "module": None,
            "id": None,
            "version": None,
            "version-ref": None,
        }
        for field, pattern in (
            ("module", r'\bmodule\s*=\s*"([^"]+)"'),
            ("id", r'\bid\s*=\s*"([^"]+)"'),
            ("version-ref", r'\bversion\.ref\s*=\s*"([^"]+)"'),
            ("version", r'\bversion\s*=\s*"([^"]+)"'),
        ):
            match = re.search(pattern, raw_value)
            if match:
                entry[field] = match.group(1)
        sections[section][key] = entry
    return sections


def _managed_aliases(catalog: str, start: str, end: str) -> set[str]:
    if start not in catalog:
        return set()
    block = catalog.split(start, 1)[1].split(end, 1)[0]
    return {
        match.group(1)
        for match in re.finditer(r"^\s*([a-z][a-z0-9_.-]*)\s*=", block, re.MULTILINE)
    }


def _replace_block(text: str, start: str, end: str, body: str, before: str) -> str:
    block = f"{start}\n{body}{end}\n"
    if start in text:
        pattern = re.compile(
            re.escape(start) + r"\n.*?" + re.escape(end) + r"\n?", re.DOTALL
        )
        return pattern.sub(block, text, count=1)
    index = text.find(before)
    if index < 0:
        raise PromotionError(f"catalog marker not found: {before}")
    return text[:index] + block + text[index:]


def _entry_effective_version(
    entry: dict[str, str | None], versions: dict[str, str]
) -> str | None:
    if entry.get("version-ref"):
        return versions.get(str(entry["version-ref"]))
    return entry.get("version")


def _render_catalog(
    catalog: str,
    lines: list[EffectiveLine],
) -> str:
    parsed = _parse_catalog(catalog)
    existing_versions: dict[str, str] = parsed["versions"]  # type: ignore[assignment]
    existing_plugins: dict[str, dict[str, str | None]] = parsed["plugins"]  # type: ignore[assignment]
    existing_libraries: dict[str, dict[str, str | None]] = parsed["libraries"]  # type: ignore[assignment]
    managed_versions = _managed_aliases(catalog, VERSIONS_START, VERSIONS_END)
    managed_plugins = _managed_aliases(catalog, PLUGINS_START, PLUGINS_END)
    managed_libraries = _managed_aliases(catalog, LIBRARIES_START, LIBRARIES_END)

    generated_versions: dict[str, str] = {}
    generated_plugins: dict[str, tuple[str, str | None, str | None]] = {}
    generated_libraries: dict[str, tuple[str, str | None, str | None]] = {}
    alias_owners: dict[tuple[str, str], tuple[str, str, str]] = {}
    for line in lines:
        if line.version is not None:
            assert line.version_key is not None
            previous_version = generated_versions.get(line.version_key)
            if previous_version is not None and previous_version != line.version:
                raise PromotionError(f"version-key value collision: {line.version_key}")
            generated_versions[line.version_key] = line.version
        for alias in line.aliases:
            owner = (line.subject_kind, line.coordinate, line.line_id)
            alias_key = (line.subject_kind, alias)
            previous_owner = alias_owners.get(alias_key)
            if previous_owner is not None and previous_owner != owner:
                raise PromotionError(f"alias/accessor collision: {alias}")
            alias_owners[alias_key] = owner
            if line.subject_kind == "plugin":
                generated_plugins[alias] = (
                    line.coordinate,
                    line.version_key,
                    line.version,
                )
            else:
                generated_libraries[alias] = (
                    line.coordinate,
                    line.version_key,
                    line.version,
                )

    for key, version in generated_versions.items():
        if (
            key in existing_versions
            and key not in managed_versions
            and existing_versions[key] != version
        ):
            raise PromotionError(f"version-key value collision: {key}")
    for alias, (plugin_id, version_key, version) in generated_plugins.items():
        existing = existing_plugins.get(alias)
        if (
            existing is not None
            and alias not in managed_plugins
            and (
                existing.get("id") != plugin_id
                or _entry_effective_version(existing, existing_versions) != version
            )
        ):
            raise PromotionError(f"alias/accessor collision: {alias}")
    for alias, (module, version_key, version) in generated_libraries.items():
        existing = existing_libraries.get(alias)
        if (
            existing is not None
            and alias not in managed_libraries
            and (
                existing.get("module") != module
                or _entry_effective_version(existing, existing_versions) != version
            )
        ):
            raise PromotionError(f"alias/accessor collision: {alias}")

    try:
        _validate_accessor_aliases(
            (set(existing_libraries) - managed_libraries) | set(generated_libraries),
            (set(existing_plugins) - managed_plugins) | set(generated_plugins),
            (set(existing_versions) - managed_versions) | set(generated_versions),
        )
    except ValueError as exc:
        raise PromotionError(str(exc)) from exc

    version_lines = [
        f'{key} = "{generated_versions[key]}"\n'
        for key in sorted(generated_versions)
        if key not in existing_versions or key in managed_versions
    ]
    plugin_lines: list[str] = []
    for alias in sorted(generated_plugins):
        plugin_id, version_key, version = generated_plugins[alias]
        if alias in existing_plugins and alias not in managed_plugins:
            continue
        suffix = f', version.ref = "{version_key}"' if version_key else ""
        plugin_lines.append(f'{alias} = {{ id = "{plugin_id}"{suffix} }}\n')
    library_lines: list[str] = []
    for alias in sorted(generated_libraries):
        module, version_key, version = generated_libraries[alias]
        if alias in existing_libraries and alias not in managed_libraries:
            continue
        suffix = f', version.ref = "{version_key}"' if version_key else ""
        library_lines.append(f'{alias} = {{ module = "{module}"{suffix} }}\n')

    result = _replace_block(
        catalog, VERSIONS_START, VERSIONS_END, "".join(version_lines), SOURCE_END
    )
    result = _replace_block(
        result, PLUGINS_START, PLUGINS_END, "".join(plugin_lines), "[libraries]"
    )
    return _replace_block(
        result, LIBRARIES_START, LIBRARIES_END, "".join(library_lines), EXTERNAL_END
    )


def _canonical_dispositions(
    records: list[dict[str, Any]],
    matched: dict[tuple[str, str, str], EffectiveLine],
    existing: Any,
) -> dict[str, Any]:
    if not isinstance(existing, dict) or set(existing) != {"schema-version", "records"}:
        raise PromotionError(
            "dispositions must contain exactly schema-version and records"
        )
    if existing["schema-version"] != 1 or not isinstance(existing["records"], list):
        raise PromotionError("unsupported disposition schema")
    existing_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for index, record in enumerate(existing["records"]):
        if not isinstance(record, dict):
            raise PromotionError(f"invalid disposition record at index {index}")
        authority_id = _require_text(
            record.get("authority-id"), "disposition authority-id"
        )
        line_id = _require_text(record.get("line-id"), "disposition line-id")
        _validate_line_id(line_id, "disposition")
        pair = (authority_id, line_id)
        if pair in existing_by_pair:
            raise PromotionError(
                f"duplicate disposition pair: {authority_id}:{line_id}"
            )
        existing_by_pair[pair] = dict(record)
    expected_pairs = {(record["authority-id"], record["line-id"]) for record in records}
    orphan = sorted(set(existing_by_pair) - expected_pairs)
    if orphan:
        raise PromotionError(f"orphan disposition pair: {orphan[0][0]}:{orphan[0][1]}")

    canonical: list[dict[str, Any]] = []
    for record in sorted(
        records,
        key=lambda item: (
            item["authority-id"],
            item["line-id"],
            item["repository"],
            item["alias"],
        ),
    ):
        pair = (record["authority-id"], record["line-id"])
        line = matched[(record["repository"], record["alias"], record["authority-id"])]
        output = dict(existing_by_pair.get(pair, {}))
        output.update(
            {
                "authority-id": pair[0],
                "line-id": pair[1],
                "disposition": line.disposition,
                "evidence": dict(line.evidence),
                "central-aliases": list(line.aliases),
            }
        )
        output.update(line.metadata)
        if line.disposition == "structural-repo-owned":
            output["repository"] = record["repository"]
        output.setdefault("owner", "dependency-governance")
        output.setdefault("status", "pending")
        canonical.append(output)
    # One record per authority pair, regardless of the number of occurrences.
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in canonical:
        deduped[(record["authority-id"], record["line-id"])] = record
    return {"schema-version": 1, "records": [deduped[key] for key in sorted(deduped)]}


def build_result(
    inventory: Any,
    policy: Any,
    catalog: str,
    dispositions: Any,
) -> PromotionResult:
    records = _inventory_records(inventory)
    policy_subjects = _parse_policy(policy)
    lines, matched = _effective_lines(records, policy_subjects)
    rendered_catalog = _render_catalog(catalog, lines)
    rendered_dispositions = _canonical_dispositions(records, matched, dispositions)
    return PromotionResult(rendered_catalog, rendered_dispositions)


def _absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("path must be absolute")
    return path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=_absolute_path)
    parser.add_argument("--policy", required=True, type=_absolute_path)
    parser.add_argument("--catalog", required=True, type=_absolute_path)
    parser.add_argument("--dispositions", required=True, type=_absolute_path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        inventory = _read_json(args.inventory, "inventory")
        policy = _read_json(args.policy, "policy")
        dispositions = _read_json(args.dispositions, "dispositions")
        catalog = args.catalog.read_text(encoding="utf-8")
        result = build_result(inventory, policy, catalog, dispositions)
        disposition_bytes = canonical_json_bytes(result.dispositions)
        if args.check:
            catalog_ok = result.catalog.encode("utf-8") == args.catalog.read_bytes()
            disposition_ok = disposition_bytes == args.dispositions.read_bytes()
            if catalog_ok and disposition_ok:
                print("OK")
                return 0
            if not catalog_ok:
                print(f"catalog drift: {args.catalog}", file=sys.stderr)
            if not disposition_ok:
                print(f"disposition drift: {args.dispositions}", file=sys.stderr)
            return 1
        if result.catalog.encode("utf-8") != args.catalog.read_bytes():
            args.catalog.write_text(result.catalog, encoding="utf-8")
        if disposition_bytes != args.dispositions.read_bytes():
            args.dispositions.write_bytes(disposition_bytes)
        print("OK")
        return 0
    except (OSError, PromotionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
