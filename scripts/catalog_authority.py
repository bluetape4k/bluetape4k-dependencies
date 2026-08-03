#!/usr/bin/env python3
"""Stable identities and strict parsing for catalog authority records."""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import tomllib

ALIAS_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")
LINE_ID_PATTERN = re.compile(r"(?:default|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)")
RESERVED_ACCESSOR_NAMESPACES = frozenset({"bundles", "plugins", "versions"})
KOTLIN_RESERVED_WORDS = frozenset(
    {
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
)
DYNAMIC_VERSION_PATTERNS = (
    re.compile(r"\+"),
    re.compile(r"^latest\.", re.IGNORECASE),
    re.compile(r"^(?:\[|\().*(?:\]|\))$"),
)


@dataclasses.dataclass(frozen=True)
class AuthorityRecord:
    authority_id: str
    line_id: str
    occurrence_id: str
    repository: str
    subject_kind: str
    declaration_form: str
    coordinate_or_plugin_id: str
    alias: str
    source_path: str
    source_line: int
    declared_version: str
    resolved_version: str


@dataclasses.dataclass(frozen=True)
class CatalogData:
    versions: dict[str, Any]
    libraries: dict[str, dict[str, Any]]
    plugins: dict[str, dict[str, Any]]
    bundles: dict[str, list[str]]


def authority_id(repository: str, subject_kind: str, coordinate: str) -> str:
    payload = "\0".join((repository, subject_kind, coordinate)).encode("utf-8")  # noqa: FLY002
    return hashlib.sha256(payload).hexdigest()


def authority_key(stable_authority_id: str, line_id: str) -> str:
    if LINE_ID_PATTERN.fullmatch(line_id) is None:
        raise ValueError("invalid canonical line-id")
    return f"{stable_authority_id}:{line_id}"


def _normalized_accessor(alias: str) -> tuple[str, ...]:
    return tuple(re.split(r"[._-]", alias))


def _validate_alias(alias: str) -> tuple[str, ...]:
    if ALIAS_PATTERN.fullmatch(alias) is None:
        raise ValueError(f"invalid accessor alias: {alias}")
    accessor = _normalized_accessor(alias)
    if any(part in KOTLIN_RESERVED_WORDS for part in accessor):
        raise ValueError(f"Kotlin reserved word in accessor alias: {alias}")
    return accessor


def validate_accessor_aliases(
    aliases: Iterable[str] | None = None,
    *,
    libraries: Iterable[str] = (),
    plugins: Iterable[str] = (),
    bundles: Iterable[str] = (),
    versions: Iterable[str] = (),
) -> None:
    """Reject aliases that cannot produce unique, safe Gradle accessors."""
    if aliases is not None:
        if any((tuple(libraries), tuple(plugins), tuple(bundles), tuple(versions))):
            raise ValueError("aliases cannot be combined with named accessor trees")
        libraries = aliases

    owners: dict[tuple[str, ...], tuple[str, str]] = {}
    reserved_library_aliases: list[str] = []
    for tree, prefix, tree_aliases in (
        ("library", (), libraries),
        ("plugin", ("plugins",), plugins),
        ("bundle", ("bundles",), bundles),
        ("version", ("versions",), versions),
    ):
        seen: dict[tuple[str, ...], str] = {}
        for alias in tree_aliases:
            normalized = _validate_alias(alias)
            accessor = prefix + normalized
            if accessor in seen:
                raise ValueError(
                    f"accessor collision: {seen[accessor]} and {alias}"
                )
            seen[accessor] = alias
            if tree == "library" and normalized[0] in RESERVED_ACCESSOR_NAMESPACES:
                reserved_library_aliases.append(alias)
            previous = owners.get(accessor)
            if previous is not None:
                raise ValueError(
                    "cross-tree accessor collision: "
                    f"{previous[0]} {previous[1]} and {tree} {alias}"
                )
            owners[accessor] = (tree, alias)

    if reserved_library_aliases:
        raise ValueError(
            f"reserved accessor namespace: {reserved_library_aliases[0]}"
        )


def _reject_dynamic_version(selector: str) -> None:
    if any(pattern.search(selector) for pattern in DYNAMIC_VERSION_PATTERNS):
        raise ValueError(f"dynamic or range version is not allowed: {selector}")


def _validate_version_value(value: Any) -> None:
    if isinstance(value, str):
        _reject_dynamic_version(value)
        return
    if isinstance(value, Mapping):
        for key in ("require", "strictly", "prefer"):
            selector = value.get(key)
            if isinstance(selector, str):
                _reject_dynamic_version(selector)


def _normalize_entry(value: Any, section: str, alias: str) -> dict[str, Any]:
    if isinstance(value, str):
        if section != "libraries":
            raise ValueError(f"invalid {section} entry: {alias}")
        parts = value.split(":")
        if len(parts) == 2 and all(parts):
            return {"module": value}
        if len(parts) == 3 and all(parts):
            _reject_dynamic_version(parts[2])
            return {"module": ":".join(parts[:2]), "version": parts[2]}
        raise ValueError(f"invalid libraries entry: {alias}")
    if not isinstance(value, dict):
        raise TypeError(f"invalid {section} entry: {alias}")

    normalized = dict(value)
    version = normalized.get("version")
    if isinstance(version, dict) and set(version) == {"ref"}:
        normalized.pop("version")
        normalized["version.ref"] = version["ref"]
    elif version is not None:
        _validate_version_value(version)
    return normalized


def _normalize_bundle(value: Any, alias: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(member, str) and member for member in value
    ):
        raise TypeError(f"invalid bundles entry: {alias}")
    return list(value)


def parse_catalog(path: Path) -> CatalogData:
    """Parse a Gradle catalog with stdlib TOML and strict selector checks."""
    with path.open("rb") as source:
        document = tomllib.load(source)

    versions = dict(document.get("versions", {}))
    libraries = {
        alias: _normalize_entry(value, "libraries", alias)
        for alias, value in document.get("libraries", {}).items()
    }
    plugins = {
        alias: _normalize_entry(value, "plugins", alias)
        for alias, value in document.get("plugins", {}).items()
    }
    bundles = {
        alias: _normalize_bundle(value, alias)
        for alias, value in document.get("bundles", {}).items()
    }

    for value in versions.values():
        _validate_version_value(value)
    validate_accessor_aliases(
        libraries=libraries,
        plugins=plugins,
        bundles=bundles,
        versions=versions,
    )
    return CatalogData(versions, libraries, plugins, bundles)
