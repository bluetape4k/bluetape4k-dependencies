#!/usr/bin/env python3
"""Project the approved central dependency coordinates into Gradle's default catalog."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if sys.version_info < (3, 11):  # noqa: UP036 - fail before importing tomllib
    raise SystemExit(
        "project-dependabot-catalog.py requires Python 3.11 or newer (tomllib)"
    )

tomllib = importlib.import_module("tomllib")


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
catalog_candidate = importlib.import_module("catalog_candidate")


SCRIPT_NAME = "project-dependabot-catalog.py"
PROJECTS_SOURCE_REL = Path("gradle/libs.project.versions.toml")
PROJECTS_ALLOWLIST_REL = Path("gradle/libs.project.versions.allowlist.json")
GENERATED_CATALOG_REL = Path("gradle/libs.versions.toml")
CENTRAL_CATALOG_REL = Path("gradle/libs.versions.toml")
MAPPING_REL = Path("config/projects-dependabot-catalog.toml")
PARSER_FIXTURE_REL = Path(
    "tests/fixtures/project-dependabot-catalog/dependabot-parser-contract.rb"
)
MAPPING_FIELDS = frozenset(
    {"alias", "module", "source_type", "source_name", "version_key"}
)
ALLOWLIST_FIELDS = frozenset({"schema_version", "libraries", "plugins", "bundles"})
FIXED_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SECTION_RE = re.compile(
    rb"(?m)^(?P<header>\[(?P<name>[A-Za-z0-9_-]+)\])[ \t]*(?:\#[^\r\n]*)?(?:\r?\n|$)"
)
TABLE_CANDIDATE_RE = re.compile(
    rb"(?m)^\[(?P<name>[^\]\r\n]+)\][ \t]*(?:\#[^\r\n]*)?(?:\r?\n|$)"
)


class CatalogError(ValueError):
    """Raised when a catalog or projection input violates the strict contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _load_toml(payload: bytes, label: str) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
        value = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CatalogError(f"{label} is not valid UTF-8 TOML") from exc
    if not isinstance(value, dict):
        raise CatalogError(f"{label} must contain a TOML table")
    return value


def _load_json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise CatalogError(f"{label} must be a JSON object")
    return value


def _fixed_version(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or FIXED_VERSION_RE.fullmatch(value) is None
    ):
        raise CatalogError(f"{label} must resolve to one fixed version string")
    lowered = value.lower()
    if lowered.startswith("latest.") or "snapshot" in lowered:
        raise CatalogError(f"{label} must not use a dynamic version")
    return value


def _resolved_library_version(
    alias: str, entry: dict[str, Any], versions: dict[str, Any]
) -> str:
    value = entry.get("version")
    if isinstance(value, str):
        return _fixed_version(value, f"central library {alias} version")
    if not isinstance(value, dict) or set(value) != {"ref"}:
        raise CatalogError(
            f"central library {alias} must use a direct fixed version or one version.ref"
        )
    ref = value["ref"]
    if not isinstance(ref, str) or not ref or ref not in versions:
        raise CatalogError(f"central library {alias} has an unresolved version.ref")
    return _fixed_version(versions[ref], f"central version {ref}")


def _normalize_alias(alias: str) -> str:
    if not isinstance(alias, str) or not alias:
        raise CatalogError("catalog alias must be a non-empty string")
    return ".".join(part.lower() for part in re.split(r"[-_.]+", alias) if part)


def _validate_alias_collisions(aliases: list[str], label: str) -> None:
    normalized: dict[str, str] = {}
    for alias in aliases:
        key = _normalize_alias(alias)
        if not key:
            raise CatalogError(f"{label} contains an invalid alias: {alias!r}")
        previous = normalized.get(key)
        if previous is not None and previous != alias:
            raise CatalogError(
                f"{label} contains accessor-normalized alias collision: "
                f"{previous} and {alias}"
            )
        normalized[key] = alias


def _validate_allowlist(
    allowlist: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, str]:
    if set(allowlist) != ALLOWLIST_FIELDS or allowlist.get("schema_version") != 1:
        raise CatalogError("Projects allowlist fields or schema_version are invalid")
    if not isinstance(allowlist.get("libraries"), list):
        raise CatalogError("Projects allowlist libraries must be an array")
    if allowlist.get("plugins") != [] or allowlist.get("bundles") != []:
        raise CatalogError("Projects allowlist plugins and bundles must be empty")

    expected: dict[str, str] = {}
    listed_aliases: list[str] = []
    for entry in allowlist["libraries"]:
        if not isinstance(entry, dict) or set(entry) != {"alias", "module"}:
            raise CatalogError(
                "Projects allowlist entries must contain alias and module"
            )
        alias, module = entry["alias"], entry["module"]
        if (
            not isinstance(alias, str)
            or ALIAS_RE.fullmatch(alias) is None
            or not isinstance(module, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", module) is None
        ):
            raise CatalogError("Projects allowlist alias or module is invalid")
        if alias in expected:
            raise CatalogError(f"Projects allowlist repeats alias {alias}")
        listed_aliases.append(alias)
        expected[alias] = module
    if listed_aliases != sorted(listed_aliases):
        raise CatalogError("Projects allowlist libraries must be sorted by alias")

    libraries = catalog.get("libraries")
    if not isinstance(libraries, dict):
        raise CatalogError("Projects source catalog must contain [libraries]")
    actual: dict[str, str] = {}
    for alias, entry in libraries.items():
        if not isinstance(entry, dict) or "module" not in entry:
            raise CatalogError(f"Projects source alias {alias} must use module = GAV")
        if "version" in entry:
            raise CatalogError(
                f"Projects source alias {alias} must be versionless; found version"
            )
        if set(entry) != {"module"}:
            raise CatalogError(
                f"Projects source alias {alias} must only contain module"
            )
        if not isinstance(entry["module"], str):
            raise CatalogError(f"Projects source alias {alias} module must be a string")
        actual[alias] = entry["module"]
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        changed = sorted(
            alias
            for alias in set(actual) & set(expected)
            if actual[alias] != expected[alias]
        )
        raise CatalogError(
            "Projects source catalog and allowlist differ "
            f"(missing={missing[:5]}, unexpected={unexpected[:5]}, changed={changed[:5]})"
        )
    if catalog.get("plugins", {}) or catalog.get("bundles", {}):
        raise CatalogError("Projects source plugins and bundles must be empty")
    _validate_alias_collisions(list(actual), "Projects source catalog")
    return actual


def _validate_mapping(mapping: dict[str, Any]) -> list[dict[str, str]]:
    if (
        set(mapping)
        != {
            "schema_version",
            "dependabot_core_commit",
            "projection",
        }
        or mapping.get("schema_version") != 1
    ):
        raise CatalogError(
            "central projection mapping fields or schema_version are invalid"
        )
    parser_commit = mapping.get("dependabot_core_commit")
    if (
        not isinstance(parser_commit, str)
        or GIT_OBJECT_RE.fullmatch(parser_commit) is None
    ):
        raise CatalogError("central mapping must pin a full Dependabot core commit")
    entries = mapping.get("projection")
    if not isinstance(entries, list) or len(entries) != 10:
        raise CatalogError(
            "central projection mapping must contain exactly ten entries"
        )
    aliases: set[str] = set()
    modules: set[str] = set()
    result: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != MAPPING_FIELDS:
            raise CatalogError(
                "projection entries must contain the exact mapping fields"
            )
        if any(
            not isinstance(entry[field], str) or not entry[field]
            for field in MAPPING_FIELDS
        ):
            raise CatalogError("projection mapping fields must be non-empty strings")
        if ALIAS_RE.fullmatch(entry["alias"]) is None:
            raise CatalogError(f"projection alias is invalid: {entry['alias']}")
        if re.fullmatch(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", entry["module"]) is None:
            raise CatalogError(f"projection module is not a GAV: {entry['module']}")
        if (
            ALIAS_RE.fullmatch(entry["source_name"]) is None
            or ALIAS_RE.fullmatch(entry["version_key"]) is None
        ):
            raise CatalogError(
                f"projection source or version key is invalid for {entry['alias']}"
            )
        if entry["source_type"] not in {"version", "library"}:
            raise CatalogError(
                f"projection source_type is invalid for {entry['alias']}"
            )
        if entry["alias"] in aliases or entry["module"] in modules:
            raise CatalogError("projection mapping contains a duplicate alias or GAV")
        aliases.add(entry["alias"])
        modules.add(entry["module"])
        result.append({field: entry[field] for field in MAPPING_FIELDS})
    _validate_alias_collisions(list(aliases), "projection mapping")
    return result


def _source_version(entry: dict[str, str], central: dict[str, Any]) -> str:
    versions = central.get("versions", {})
    libraries = central.get("libraries", {})
    if not isinstance(versions, dict) or not isinstance(libraries, dict):
        raise CatalogError("central catalog requires [versions] and [libraries]")
    if entry["source_type"] == "version":
        if entry["source_name"] not in versions:
            raise CatalogError(
                f"central version key is missing: {entry['source_name']}"
            )
        return _fixed_version(
            versions[entry["source_name"]],
            f"central version {entry['source_name']}",
        )

    source = libraries.get(entry["source_name"])
    if not isinstance(source, dict):
        raise CatalogError(f"central library alias is missing: {entry['source_name']}")
    if source.get("module") != entry["module"]:
        raise CatalogError(
            f"central library {entry['source_name']} module does not match "
            f"{entry['module']}"
        )
    return _resolved_library_version(entry["source_name"], source, versions)


def _sections(payload: bytes) -> dict[str, tuple[int, int]]:
    allowed = {b"versions", b"plugins", b"libraries", b"bundles"}
    for candidate in TABLE_CANDIDATE_RE.finditer(payload):
        if candidate.group("name") not in allowed:
            raise CatalogError(
                "Projects source contains a table that cannot be byte-preservingly projected"
            )
    matches = list(SECTION_RE.finditer(payload))
    sections: dict[str, tuple[int, int]] = {}
    for index, match in enumerate(matches):
        name = match.group("name").decode("ascii")
        if name in sections:
            raise CatalogError(f"Projects source repeats [{name}] table")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(payload)
        sections[name] = (match.end(), end)
    return sections


def _line_records(
    payload: bytes, sections: dict[str, tuple[int, int]]
) -> list[tuple[int, int, bytes, str | None]]:
    boundaries = sorted((start, name) for name, (start, _) in sections.items())
    records = []
    current: str | None = None
    position = 0
    for line in payload.splitlines(keepends=True):
        for start, name in boundaries:
            if start == position:
                current = name
                break
        end = position + len(line)
        records.append((position, end, line, current))
        position = end
    if position < len(payload):
        records.append((position, len(payload), payload[position:], current))
    return records


def _line_ending(payload: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in payload else b"\n"


def _render_existing_alias(line: bytes, alias: str, version_key: str) -> bytes:
    encoded_alias = re.escape(alias.encode("ascii"))
    match = re.fullmatch(
        rb"([ \t]*"
        + encoded_alias
        + rb"[ \t]*=[ \t]*\{)([^{}\r\n]*)(\}[ \t]*(?:\#[^\r\n]*)?)(\r?\n)?",
        line,
    )
    if match is None:
        raise CatalogError(
            f"mapped source alias {alias} must be a single-line inline table"
        )
    inner = match.group(2)
    body = inner.rstrip(b" \t")
    trailing = inner[len(body) :]
    suffix = b', version.ref = "' + version_key.encode("ascii") + b'"'
    return (
        match.group(1)
        + body
        + suffix
        + trailing
        + match.group(3)
        + (match.group(4) or b"")
    )


def render_catalog(
    project_catalog: bytes,
    allowlist_bytes: bytes,
    central_catalog: bytes,
    mapping_bytes: bytes,
) -> bytes:
    """Return a deterministic byte-preserving catalog projection."""
    project = _load_toml(project_catalog, "Projects source catalog")
    allowlist = _load_json(allowlist_bytes, "Projects allowlist")
    central = _load_toml(central_catalog, "central catalog")
    mapping = _load_toml(mapping_bytes, "central projection mapping")
    source_libraries = _validate_allowlist(allowlist, project)
    projections = _validate_mapping(mapping)
    existing_versions = project.get("versions", {})
    if not isinstance(existing_versions, dict):
        raise CatalogError("Projects source [versions] must be a table")
    if "versions" not in _sections(project_catalog) or "libraries" not in _sections(
        project_catalog
    ):
        raise CatalogError("Projects source must contain [versions] and [libraries]")

    projected: list[dict[str, str]] = []
    version_values: dict[str, str] = {}
    for item in projections:
        source_module = source_libraries.get(item["alias"])
        if source_module is not None and source_module != item["module"]:
            raise CatalogError(
                f"Projects source alias {item['alias']} GAV does not match projection"
            )
        version = _source_version(item, central)
        previous = version_values.setdefault(item["version_key"], version)
        if previous != version:
            raise CatalogError(
                f"projection version key {item['version_key']} resolves to multiple versions"
            )
        if item["version_key"] in existing_versions:
            raise CatalogError(
                f"projection version key collides with Projects source: {item['version_key']}"
            )
        projected.append(item)

    output_libraries = dict(source_libraries)
    for item in projected:
        previous = output_libraries.get(item["alias"])
        if previous is not None and previous != item["module"]:
            raise CatalogError(f"projection alias {item['alias']} changes its GAV")
        output_libraries[item["alias"]] = item["module"]
    _validate_alias_collisions(list(output_libraries), "generated catalog")
    module_alias: dict[str, str] = {}
    for alias, module in output_libraries.items():
        previous = module_alias.get(module)
        if previous is not None and previous != alias:
            raise CatalogError(
                f"generated catalog maps GAV {module} to both {previous} and {alias}"
            )
        module_alias[module] = alias

    for item in projected:
        current = project["libraries"].get(item["alias"])
        if current is not None and "version" in current:
            raise CatalogError(
                f"Projects source alias {item['alias']} must be versionless"
            )

    sections = _sections(project_catalog)
    records = _line_records(project_catalog, sections)
    line_by_alias: dict[str, tuple[int, int, bytes]] = {}
    for start, end, line, section in records:
        if section != "libraries":
            continue
        match = re.match(rb"^[ \t]*([A-Za-z0-9_-]+)[ \t]*=", line)
        if match:
            alias = match.group(1).decode("ascii")
            if alias in source_libraries:
                if alias in line_by_alias:
                    raise CatalogError(f"Projects source repeats alias {alias}")
                line_by_alias[alias] = (start, end, line)

    newline = _line_ending(project_catalog)
    edits: list[tuple[int, int, bytes]] = []
    missing_aliases = []
    for item in projected:
        found = line_by_alias.get(item["alias"])
        if found is None:
            missing_aliases.append(item)
            continue
        start, end, line = found
        edits.append(
            (
                start,
                end,
                _render_existing_alias(line, item["alias"], item["version_key"]),
            )
        )

    version_additions = b"".join(
        key.encode("ascii")
        + b' = "'
        + version_values[key].encode("ascii")
        + b'"'
        + newline
        for key in version_values
    )
    if version_additions:
        start, end = sections["versions"]
        prefix = (
            b""
            if start == end or project_catalog[:end].endswith((b"\n", b"\r"))
            else newline
        )
        edits.append((end, end, prefix + version_additions))

    if missing_aliases:
        start, end = sections["libraries"]
        prefix = (
            b""
            if end == start or project_catalog[:end].endswith((b"\n", b"\r"))
            else newline
        )
        additions = b"".join(
            item["alias"].encode("ascii")
            + b' = { module = "'
            + item["module"].encode("ascii")
            + b'", version.ref = "'
            + item["version_key"].encode("ascii")
            + b'" }'
            + newline
            for item in missing_aliases
        )
        edits.append((end, end, prefix + additions))

    result = project_catalog
    for start, end, replacement in sorted(
        edits, key=lambda item: (item[0], item[1]), reverse=True
    ):
        result = result[:start] + replacement + result[end:]
    generated = _load_toml(result, "generated catalog")
    generated_libraries = generated.get("libraries", {})
    if set(generated_libraries) != set(output_libraries):
        raise CatalogError("generated catalog library alias set changed unexpectedly")
    actual_versioned = {
        alias for alias, entry in generated_libraries.items() if "version" in entry
    }
    if actual_versioned != {item["alias"] for item in projected}:
        raise CatalogError("generated catalog versioned aliases do not match mapping")
    for item in projected:
        entry = generated_libraries[item["alias"]]
        if entry.get("module") != item["module"]:
            raise CatalogError(f"generated alias {item['alias']} has the wrong GAV")
        if entry.get("version") != {"ref": item["version_key"]}:
            raise CatalogError(
                f"generated alias {item['alias']} has the wrong version.ref"
            )
        if (
            generated["versions"].get(item["version_key"])
            != version_values[item["version_key"]]
        ):
            raise CatalogError(
                f"generated version {item['version_key']} is inconsistent"
            )
    return result


def _canonical_path(path: Path, label: str, *, must_exist: bool = True) -> Path:
    if not path.is_absolute():
        raise CatalogError(f"{label} path must be absolute")
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise CatalogError(f"{label} path does not exist") from exc
    if resolved != path:
        raise CatalogError(f"{label} path must be canonical and non-symlinked")
    return path


def _regular_file(path: Path, label: str, *, must_exist: bool = True) -> None:
    _canonical_path(path, label, must_exist=must_exist)
    if not must_exist and not path.exists():
        return
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise CatalogError(f"{label} is unavailable") from exc
    if not stat.S_ISREG(mode):
        raise CatalogError(f"{label} must be a regular non-symlink file")


def _directory(path: Path, label: str) -> None:
    _canonical_path(path, label)
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise CatalogError(f"{label} is unavailable") from exc
    if not stat.S_ISDIR(mode):
        raise CatalogError(f"{label} must be a regular non-symlink directory")


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CatalogError(f"cannot inspect {root.name} Git state") from exc
    if completed.returncode != 0:
        raise CatalogError(f"Git inspection failed for {root.name}")
    try:
        return completed.stdout.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise CatalogError(f"Git output is not UTF-8 for {root.name}") from exc


def _expected_origin(repository: str) -> str:
    return f"git@github.com:bluetape4k/{repository}.git"


def _repository_state(root: Path, repository: str) -> dict[str, str]:
    _directory(root, f"{repository} root")
    if _git(root, "rev-parse", "--show-toplevel") != str(root):
        raise CatalogError(f"{repository} root is not its canonical Git root")
    origin = _git(root, "remote", "get-url", "origin")
    if origin != _expected_origin(repository):
        raise CatalogError(f"{repository} origin is not the canonical SSH remote")
    branch = _git(root, "branch", "--show-current")
    if not branch:
        raise CatalogError(f"{repository} worktree must be attached to a branch")
    head = _git(root, "rev-parse", "HEAD")
    if GIT_OBJECT_RE.fullmatch(head) is None:
        raise CatalogError(f"{repository} HEAD is not a full commit SHA")
    try:
        origin_develop = _git(root, "rev-parse", "refs/remotes/origin/develop^{commit}")
        base_sha = _git(root, "merge-base", head, origin_develop)
    except CatalogError as exc:
        raise CatalogError(f"{repository} origin/develop base is unavailable") from exc
    if GIT_OBJECT_RE.fullmatch(base_sha) is None:
        raise CatalogError(f"{repository} origin/develop fork point is invalid")
    return {
        "root": str(root),
        "origin": origin,
        "branch": branch,
        "base_sha": base_sha,
        "expected_head": head,
    }


def _require_clean(root: Path, repository: str) -> None:
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise CatalogError(f"{repository} worktree must be clean")


def _input_paths(projects_root: Path, central_root: Path) -> dict[str, Path]:
    return {
        "generator": Path(__file__).resolve(),
        "mapping": central_root / MAPPING_REL,
        "projects_source": projects_root / PROJECTS_SOURCE_REL,
        "projects_allowlist": projects_root / PROJECTS_ALLOWLIST_REL,
        "central_catalog": central_root / CENTRAL_CATALOG_REL,
        "generated_catalog": projects_root / GENERATED_CATALOG_REL,
    }


def _read_inputs(
    projects_root: Path, central_root: Path
) -> tuple[dict[str, Path], dict[str, bytes]]:
    paths = _input_paths(projects_root, central_root)
    values: dict[str, bytes] = {}
    for name, path in paths.items():
        if name == "generated_catalog" and not path.exists():
            continue
        _regular_file(path, name.replace("_", " "))
        try:
            values[name] = path.read_bytes()
        except OSError as exc:
            raise CatalogError(f"cannot read {name.replace('_', ' ')}") from exc
    return paths, values


def _snapshot_sha256(
    paths: dict[str, Path], values: dict[str, bytes]
) -> dict[str, str]:
    return {
        name: catalog_candidate.sha256_bytes(values[name])
        for name in paths
        if name in values
    }


def _validate_project_pin(projects_root: Path, central_sha: str) -> None:
    settings_path = projects_root / "settings.gradle.kts"
    properties_path = projects_root / "gradle.properties"
    _regular_file(settings_path, "Projects settings.gradle.kts")
    _regular_file(properties_path, "Projects gradle.properties")
    settings = settings_path.read_text(encoding="utf-8")
    match = re.search(
        r"val\s+bluetape4kDependenciesCatalogRef\s*=.*?"
        r"\.orElse\(\"([0-9a-f]{40}(?:[0-9a-f]{24})?)\"\)",
        settings,
        re.DOTALL,
    )
    if match is None:
        raise CatalogError("Projects settings default catalog pin is not explicit")
    values = [match.group(1)]
    properties = properties_path.read_text(encoding="utf-8")
    property_match = re.search(
        r"(?m)^\s*bluetape4kDependenciesCatalogRef\s*=\s*([0-9a-f]{40}(?:[0-9a-f]{24})?)\s*$",
        properties,
    )
    environment = os.environ.get("BLUETAPE4K_DEPENDENCIES_CATALOG_REF")
    if property_match is not None:
        values.append(property_match.group(1))
    if environment:
        values.append(environment)
    if any(value != central_sha for value in values):
        raise CatalogError(
            "Projects effective central catalog pin does not match central HEAD"
        )


def _map_path_value(entry: dict[str, Any], key: str, expected: Path) -> None:
    value = entry.get(key)
    if not isinstance(value, str) or value != str(expected):
        raise CatalogError(f"repository map {key} path mismatch")
    _regular_file(expected, f"repository map {key}")


def _load_project_repository_map(
    map_path: Path, projects_root: Path, central_root: Path
) -> tuple[dict[str, Any], bytes, dict[str, dict[str, str]]]:
    _regular_file(map_path, "repository map")
    payload = map_path.read_bytes()
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError("repository map is invalid JSON") from exc
    if canonical_json_bytes(document) != payload:
        raise CatalogError("repository map must use canonical JSON bytes")
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "central", "repositories"}
        or document.get("schema_version") != 2
        or not isinstance(document.get("central"), dict)
        or not isinstance(document.get("repositories"), dict)
        or set(document["repositories"]) != {"projects"}
    ):
        raise CatalogError("repository map must be the generator-only v2 envelope")

    observations = {
        "central": _repository_state(central_root, "bluetape4k-dependencies"),
        "projects": _repository_state(projects_root, "bluetape4k-projects"),
    }
    expected_paths = {
        "central": {
            "catalog": central_root / CENTRAL_CATALOG_REL,
            "authority_catalog": central_root / CENTRAL_CATALOG_REL,
        },
        "projects": {
            "catalog": projects_root / GENERATED_CATALOG_REL,
            "authority_catalog": projects_root / PROJECTS_SOURCE_REL,
        },
    }
    for name in ("central", "projects"):
        entry = document[name] if name == "central" else document["repositories"][name]
        expected_fields = {
            "root",
            "catalog",
            "authority_catalog",
            "origin",
            "branch",
            "base_sha",
            "expected_head",
            "clean",
        }
        if not isinstance(entry, dict) or set(entry) != expected_fields:
            raise CatalogError(f"repository map fields are invalid for {name}")
        state = observations[name]
        for field, value in state.items():
            if entry.get(field) != value:
                raise CatalogError(f"repository map {field} mismatch for {name}")
        if entry.get("clean") is not True:
            raise CatalogError(f"repository map clean flag is false for {name}")
        for field, path in expected_paths[name].items():
            _map_path_value(entry, field, path)
        _require_clean(Path(state["root"]), name)

    _validate_project_pin(projects_root, observations["central"]["expected_head"])
    return document, payload, observations


def _evidence_directory(path: Path | None, projects_root: Path) -> Path:
    selected = path or (projects_root / ".gradle" / "issue-1832-evidence")
    if not selected.is_absolute():
        raise CatalogError("evidence directory path must be absolute")
    resolved = selected.resolve(strict=False)
    if selected != resolved or not resolved.is_relative_to(projects_root):
        raise CatalogError("evidence directory must be canonical and inside Projects")
    relative = resolved.relative_to(projects_root)
    if not relative.parts or relative.parts[0] != ".gradle":
        raise CatalogError("evidence directory must stay under Projects .gradle")
    for ancestor in (projects_root, *resolved.parents):
        if ancestor == projects_root.parent:
            break
        if ancestor.is_symlink():
            raise CatalogError("evidence directory path contains a symlink")
    return resolved


def _file_record(path: Path) -> dict[str, str]:
    _regular_file(path, "evidence input")
    return {
        "path": str(path),
        "sha256": catalog_candidate.sha256_bytes(path.read_bytes()),
    }


def _load_canonical_json(
    path: Path, label: str, *, payload: bytes | None = None
) -> dict[str, Any]:
    _regular_file(path, label)
    if payload is None:
        payload = path.read_bytes()
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{label} is invalid JSON") from exc
    if not isinstance(document, dict) or canonical_json_bytes(document) != payload:
        raise CatalogError(f"{label} must be a canonical JSON object")
    return document


def _verify_parser_receipt(
    path: Path,
    projects_root: Path,
    central_root: Path,
    generated_catalog: Path,
    mapping: dict[str, Any],
    *,
    payload: bytes | None = None,
) -> dict[str, Any]:
    receipt = _load_canonical_json(path, "parser receipt", payload=payload)
    required = {
        "schema_version",
        "dependabot_core_commit",
        "parser_fixture",
        "generated_catalog",
        "dependencies",
    }
    if set(receipt) != required or receipt.get("schema_version") != 1:
        raise CatalogError("parser receipt fields or schema_version are invalid")
    expected_commit = mapping.get("dependabot_core_commit")
    if (
        not isinstance(expected_commit, str)
        or GIT_OBJECT_RE.fullmatch(expected_commit) is None
        or receipt.get("dependabot_core_commit") != expected_commit
    ):
        raise CatalogError(
            "parser receipt Dependabot commit does not match pinned config"
        )
    fixture = receipt["parser_fixture"]
    if not isinstance(fixture, dict) or set(fixture) != {"path", "sha256"}:
        raise CatalogError("parser receipt fixture record is invalid")
    if not isinstance(fixture["path"], str):
        raise CatalogError("parser receipt fixture path is invalid")
    fixture_path = Path(fixture["path"])
    _regular_file(fixture_path, "Dependabot parser fixture")
    expected_fixture_path = central_root / PARSER_FIXTURE_REL
    if fixture_path != expected_fixture_path:
        raise CatalogError(
            "parser receipt does not reference the pinned contract fixture"
        )
    if (
        not isinstance(fixture.get("sha256"), str)
        or SHA256_RE.fullmatch(fixture["sha256"]) is None
        or catalog_candidate.sha256_bytes(fixture_path.read_bytes())
        != fixture["sha256"]
    ):
        raise CatalogError("Dependabot parser fixture SHA-256 mismatch")
    generated_record = receipt["generated_catalog"]
    if (
        not isinstance(generated_record, dict)
        or set(generated_record) != {"path", "sha256"}
        or generated_record.get("path") != str(generated_catalog)
    ):
        raise CatalogError("parser receipt generated catalog record is invalid")
    _regular_file(generated_catalog, "parser receipt generated catalog")
    if not generated_catalog.is_relative_to(projects_root):
        raise CatalogError("parser receipt generated catalog must be inside Projects")
    generated_sha = catalog_candidate.sha256_bytes(generated_catalog.read_bytes())
    if (
        not isinstance(generated_record.get("sha256"), str)
        or SHA256_RE.fullmatch(generated_record["sha256"]) is None
        or generated_record["sha256"] != generated_sha
    ):
        raise CatalogError("parser receipt generated catalog SHA-256 mismatch")

    generated = _load_toml(generated_catalog.read_bytes(), "generated catalog")
    projections = _validate_mapping(mapping)
    dependencies = receipt["dependencies"]
    if not isinstance(dependencies, list) or len(dependencies) != len(projections):
        raise CatalogError("parser receipt must contain all ten mapped dependencies")
    expected_dependencies = []
    for item in projections:
        version_key = item["version_key"]
        expected_dependencies.append(
            {
                "alias": item["alias"],
                "module": item["module"],
                "version_ref": version_key,
                "version": generated["versions"][version_key],
            }
        )
    if dependencies != expected_dependencies:
        raise CatalogError("parser receipt dependency observations differ from catalog")
    return receipt


def _build_receipt(
    paths: dict[str, Path],
    repository_map: Path,
    map_payload: bytes,
    observations: dict[str, dict[str, str]],
    command: list[str],
) -> dict[str, Any]:
    central_head = observations["central"]["expected_head"]
    peeled = _git(
        Path(observations["central"]["root"]), "rev-parse", f"{central_head}^{{commit}}"
    )
    if peeled != central_head:
        raise CatalogError("central HEAD does not peel to the same commit")
    return {
        "schema_version": 1,
        "generator": _file_record(paths["generator"]),
        "mapping": _file_record(paths["mapping"]),
        "projects_source": _file_record(paths["projects_source"]),
        "projects_allowlist": _file_record(paths["projects_allowlist"]),
        "central_catalog": _file_record(paths["central_catalog"]),
        "generated_catalog": _file_record(paths["generated_catalog"]),
        "repository_map": {
            "path": str(repository_map),
            "sha256": catalog_candidate.sha256_bytes(map_payload),
        },
        "projects": {
            "root": observations["projects"]["root"],
            "expected_head": observations["projects"]["expected_head"],
        },
        "central": {
            "root": observations["central"]["root"],
            "expected_head": central_head,
            "peeled_commit": peeled,
        },
        "command": command,
        "python_version": sys.version,
    }


def _build_candidate_lock(
    receipt_path: Path,
    receipt_bytes: bytes,
    parser_receipt_path: Path,
    parser_receipt_bytes: bytes,
    repository_map: Path,
    map_payload: bytes,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt": {
            "path": str(receipt_path),
            "sha256": catalog_candidate.sha256_bytes(receipt_bytes),
        },
        "parser_receipt": {
            "path": str(parser_receipt_path),
            "sha256": catalog_candidate.sha256_bytes(parser_receipt_bytes),
        },
        "repository_map": {
            "path": str(repository_map),
            "sha256": catalog_candidate.sha256_bytes(map_payload),
        },
        "projects": receipt["projects"],
        "central": receipt["central"],
        "catalogs": {
            "projects_authority": _file_record(
                Path(receipt["projects_source"]["path"])
            ),
            "projects_generated": _file_record(
                Path(receipt["generated_catalog"]["path"])
            ),
            "central_authority": _file_record(Path(receipt["central_catalog"]["path"])),
        },
        "mapping": receipt["mapping"],
        "projects_allowlist": receipt["projects_allowlist"],
    }


def _verify_evidence(evidence_dir: Path) -> None:
    receipt_path = evidence_dir / "generator-receipt.json"
    lock_path = evidence_dir / "candidate-lock.json"
    parser_path = evidence_dir / "parser-receipt.json"
    receipt = _load_canonical_json(receipt_path, "generator receipt")
    lock = _load_canonical_json(lock_path, "candidate lock")
    expected_receipt_fields = {
        "schema_version",
        "generator",
        "mapping",
        "projects_source",
        "projects_allowlist",
        "central_catalog",
        "generated_catalog",
        "repository_map",
        "projects",
        "central",
        "command",
        "python_version",
    }
    if set(receipt) != expected_receipt_fields or receipt.get("schema_version") != 1:
        raise CatalogError("generator receipt fields or schema_version are invalid")
    records: dict[str, dict[str, str]] = {}
    for field in (
        "generator",
        "mapping",
        "projects_source",
        "projects_allowlist",
        "central_catalog",
        "generated_catalog",
        "repository_map",
    ):
        record = receipt[field]
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise CatalogError(f"generator receipt {field} record is invalid")
        if not isinstance(record["path"], str):
            raise CatalogError(f"generator receipt {field} path is invalid")
        path = Path(record["path"])
        _regular_file(path, f"generator receipt {field}")
        if (
            not isinstance(record["sha256"], str)
            or SHA256_RE.fullmatch(record["sha256"]) is None
            or catalog_candidate.sha256_bytes(path.read_bytes()) != record["sha256"]
        ):
            raise CatalogError(f"generator receipt {field} SHA-256 mismatch")
        records[field] = record

    map_record = receipt["repository_map"]
    if (
        not isinstance(map_record, dict)
        or set(map_record) != {"path", "sha256"}
        or not isinstance(map_record.get("path"), str)
        or not isinstance(map_record.get("sha256"), str)
    ):
        raise CatalogError("generator receipt repository map record is invalid")
    map_path = Path(map_record["path"])
    central = receipt["central"]
    projects = receipt["projects"]
    if not isinstance(central, dict) or set(central) != {
        "root",
        "expected_head",
        "peeled_commit",
    }:
        raise CatalogError("generator receipt central repository record is invalid")
    if not isinstance(projects, dict) or set(projects) != {"root", "expected_head"}:
        raise CatalogError("generator receipt Projects repository record is invalid")
    if (
        not isinstance(central.get("root"), str)
        or not isinstance(central.get("expected_head"), str)
        or not isinstance(central.get("peeled_commit"), str)
        or GIT_OBJECT_RE.fullmatch(central["expected_head"]) is None
        or GIT_OBJECT_RE.fullmatch(central["peeled_commit"]) is None
        or not isinstance(projects.get("root"), str)
        or not isinstance(projects.get("expected_head"), str)
        or GIT_OBJECT_RE.fullmatch(projects["expected_head"]) is None
    ):
        raise CatalogError("generator receipt repository roots or HEADs are invalid")
    central_root = Path(central["root"])
    projects_root = Path(projects["root"])
    if not map_path.is_relative_to(evidence_dir):
        raise CatalogError(
            "generator receipt repository map must be inside evidence directory"
        )
    map_document, map_payload, observations = _load_project_repository_map(
        map_path, projects_root, central_root
    )
    del map_document
    if (
        SHA256_RE.fullmatch(map_record["sha256"]) is None
        or catalog_candidate.sha256_bytes(map_payload) != map_record["sha256"]
    ):
        raise CatalogError("generator receipt repository map SHA-256 mismatch")
    peeled = _git(
        central_root,
        "rev-parse",
        f"{observations['central']['expected_head']}^{{commit}}",
    )
    expected_central = {
        "root": observations["central"]["root"],
        "expected_head": observations["central"]["expected_head"],
        "peeled_commit": peeled,
    }
    expected_projects = {
        "root": observations["projects"]["root"],
        "expected_head": observations["projects"]["expected_head"],
    }
    if (
        peeled != observations["central"]["expected_head"]
        or central != expected_central
        or projects != expected_projects
    ):
        raise CatalogError("generator receipt repository identity or HEAD is stale")

    expected_paths = _input_paths(projects_root, central_root)
    for field in (
        "generator",
        "mapping",
        "projects_source",
        "projects_allowlist",
        "central_catalog",
        "generated_catalog",
    ):
        if records[field]["path"] != str(expected_paths[field]):
            raise CatalogError(f"generator receipt {field} path mismatch")
    paths, values = _read_inputs(projects_root, central_root)
    generated = render_catalog(
        values["projects_source"],
        values["projects_allowlist"],
        values["central_catalog"],
        values["mapping"],
    )
    if values.get("generated_catalog") != generated:
        raise CatalogError("generator receipt generated catalog is stale")
    if (
        not isinstance(receipt["command"], list)
        or any(not isinstance(item, str) or not item for item in receipt["command"])
        or not isinstance(receipt["python_version"], str)
    ):
        raise CatalogError("generator receipt command or Python version is invalid")

    parser_payload = parser_path.read_bytes()
    mapping_data = _load_toml(values["mapping"], "central projection mapping")
    _verify_parser_receipt(
        parser_path,
        projects_root,
        central_root,
        paths["generated_catalog"],
        mapping_data,
        payload=parser_payload,
    )
    expected_lock = {
        "schema_version": 1,
        "receipt": {
            "path": str(receipt_path),
            "sha256": catalog_candidate.sha256_bytes(receipt_path.read_bytes()),
        },
        "parser_receipt": {
            "path": str(parser_path),
            "sha256": catalog_candidate.sha256_bytes(parser_payload),
        },
        "repository_map": map_record,
        "projects": projects,
        "central": central,
        "catalogs": {
            "projects_authority": receipt["projects_source"],
            "projects_generated": receipt["generated_catalog"],
            "central_authority": receipt["central_catalog"],
        },
        "mapping": receipt["mapping"],
        "projects_allowlist": receipt["projects_allowlist"],
    }
    if lock != expected_lock:
        raise CatalogError("candidate lock does not match generator/parser receipts")


def _write_evidence_file(path: Path, payload: bytes, label: str) -> None:
    _canonical_path(path, label, must_exist=False)
    if path.exists():
        _regular_file(path, label)
        if path.read_bytes() != payload:
            raise CatalogError(f"existing {label} differs; refusing to overwrite")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    created = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        try:
            os.link(temp_path, path)
            created = True
        except FileExistsError:
            _regular_file(path, label)
            if path.read_bytes() != payload:
                raise CatalogError(f"existing {label} differs; refusing to overwrite")
            return
        _fsync_directory(path.parent)
        if path.read_bytes() != payload:
            raise CatalogError(f"{label} read-back mismatch")
    except BaseException:
        if created and path.exists():
            _regular_file(path, label)
            if path.read_bytes() != payload:
                raise CatalogError(f"{label} changed; refusing recovery removal")
            path.unlink()
            _fsync_directory(path.parent)
        raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _assert_inputs_unchanged(
    paths: dict[str, Path],
    values: dict[str, bytes],
    *,
    exclude: frozenset[str] = frozenset(),
) -> None:
    for name, expected in values.items():
        if name in exclude:
            continue
        path = paths[name]
        _regular_file(path, name.replace("_", " "))
        try:
            actual = path.read_bytes()
        except OSError as exc:
            raise CatalogError(f"cannot re-read {name.replace('_', ' ')}") from exc
        if catalog_candidate.sha256_bytes(actual) != catalog_candidate.sha256_bytes(
            expected
        ):
            raise CatalogError(f"{name.replace('_', ' ')} changed during generation")


def _write_mode(
    projects_root: Path,
    central_root: Path,
    paths: dict[str, Path],
    values: dict[str, bytes],
    generated: bytes,
    initial_states: dict[str, dict[str, str]],
) -> None:
    _assert_inputs_unchanged(paths, values, exclude=frozenset({"generated_catalog"}))
    for repository, root in (
        ("bluetape4k-projects", projects_root),
        ("bluetape4k-dependencies", central_root),
    ):
        if _repository_state(root, repository) != initial_states[repository]:
            raise CatalogError(
                f"{repository} HEAD or repository identity changed during generation"
            )
    output = paths["generated_catalog"]
    _regular_file(output, "generated catalog output", must_exist=False)
    _write_atomic(output, generated)
    if output.read_bytes() != generated:
        raise CatalogError("generated catalog write did not pass final read-back")


def _check_mode(
    projects_root: Path,
    central_root: Path,
    paths: dict[str, Path],
    values: dict[str, bytes],
    generated: bytes,
    map_path: Path,
    evidence_dir: Path,
    initial_states: dict[str, dict[str, str]],
    command: list[str],
) -> None:
    if not map_path.is_relative_to(evidence_dir):
        raise CatalogError("repository map must be inside evidence directory")
    map_document, map_payload, observations = _load_project_repository_map(
        map_path, projects_root, central_root
    )
    del map_document
    output = paths["generated_catalog"]
    _regular_file(output, "generated catalog")
    if output.read_bytes() != generated:
        raise CatalogError("generated catalog is stale")
    mapping_data = _load_toml(values["mapping"], "central projection mapping")
    parser_path = evidence_dir / "parser-receipt.json"
    parser_payload = parser_path.read_bytes()
    _verify_parser_receipt(
        parser_path,
        projects_root,
        central_root,
        output,
        mapping_data,
        payload=parser_payload,
    )

    _assert_inputs_unchanged(paths, values)
    if map_path.read_bytes() != map_payload:
        raise CatalogError("repository map changed during verification")
    _regular_file(parser_path, "parser receipt")
    if parser_path.read_bytes() != parser_payload:
        raise CatalogError("parser receipt changed during verification")
    if (
        _repository_state(projects_root, "bluetape4k-projects")
        != initial_states["bluetape4k-projects"]
    ):
        raise CatalogError(
            "Projects HEAD or repository identity changed during verification"
        )
    if (
        _repository_state(central_root, "bluetape4k-dependencies")
        != initial_states["bluetape4k-dependencies"]
    ):
        raise CatalogError(
            "central HEAD or repository identity changed during verification"
        )
    _require_clean(projects_root, "Projects")
    _require_clean(central_root, "central")
    _validate_project_pin(projects_root, observations["central"]["expected_head"])

    receipt_path = evidence_dir / "generator-receipt.json"
    lock_path = evidence_dir / "candidate-lock.json"
    receipt = _build_receipt(
        paths,
        map_path,
        map_payload,
        observations,
        command,
    )
    receipt_bytes = canonical_json_bytes(receipt)
    lock = _build_candidate_lock(
        receipt_path,
        receipt_bytes,
        parser_path,
        parser_payload,
        map_path,
        map_payload,
        receipt,
    )
    lock_bytes = canonical_json_bytes(lock)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _write_evidence_file(receipt_path, receipt_bytes, "generator receipt")
    _write_evidence_file(lock_path, lock_bytes, "candidate lock")
    _verify_evidence(evidence_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", type=Path, required=True)
    parser.add_argument("--central-root", type=Path, required=True)
    parser.add_argument("--repository-map", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        projects_root = _canonical_path(args.projects_root, "Projects root")
        central_root = _canonical_path(args.central_root, "central root")
        if projects_root == central_root:
            raise CatalogError(
                "Projects and central roots must be different repositories"
            )
        initial_states = {
            "bluetape4k-projects": _repository_state(
                projects_root, "bluetape4k-projects"
            ),
            "bluetape4k-dependencies": _repository_state(
                central_root, "bluetape4k-dependencies"
            ),
        }
        paths, values = _read_inputs(projects_root, central_root)
        required_inputs = {
            "generator",
            "mapping",
            "projects_source",
            "projects_allowlist",
            "central_catalog",
        }
        if not required_inputs.issubset(values):
            raise CatalogError("one or more fixed generator inputs are missing")
        generated = render_catalog(
            values["projects_source"],
            values["projects_allowlist"],
            values["central_catalog"],
            values["mapping"],
        )
        if args.write:
            if args.repository_map is not None or args.evidence_dir is not None:
                raise CatalogError(
                    "--write does not accept repository-map or evidence-dir"
                )
            _write_mode(
                projects_root,
                central_root,
                paths,
                values,
                generated,
                initial_states,
            )
            return 0

        if args.repository_map is None:
            raise CatalogError("--check requires --repository-map")
        map_path = _canonical_path(args.repository_map, "repository map")
        evidence_dir = _evidence_directory(args.evidence_dir, projects_root)
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--projects-root",
            str(projects_root),
            "--central-root",
            str(central_root),
            "--repository-map",
            str(map_path),
            "--evidence-dir",
            str(evidence_dir),
            "--check",
        ]
        _check_mode(
            projects_root,
            central_root,
            paths,
            values,
            generated,
            map_path,
            evidence_dir,
            initial_states,
            command,
        )
        return 0
    except (CatalogError, OSError, RuntimeError) as exc:
        print(f"{SCRIPT_NAME}: {exc}", file=sys.stderr)
        return 1


def _write_atomic(path: Path, payload: bytes) -> None:
    _canonical_path(path, "generated catalog output", must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    _canonical_path(path, "generated catalog output", must_exist=False)
    previous: bytes | None = None
    previous_mode = 0o644
    if path.exists():
        _regular_file(path, "generated catalog output")
        try:
            metadata = path.lstat()
            previous = path.read_bytes()
        except OSError as exc:
            raise CatalogError("generated catalog output is unavailable") from exc
        previous_mode = stat.S_IMODE(metadata.st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    replaced = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fchmod(stream.fileno(), previous_mode)
            os.fsync(stream.fileno())
        _canonical_path(path, "generated catalog output", must_exist=False)
        if previous is None:
            if path.exists() or path.is_symlink():
                raise CatalogError(
                    "generated catalog output appeared during validation"
                )
        else:
            _regular_file(path, "generated catalog output")
            if (
                path.read_bytes() != previous
                or stat.S_IMODE(path.lstat().st_mode) != previous_mode
            ):
                raise CatalogError("generated catalog output changed during validation")
        os.replace(temp_path, path)
        replaced = True
        _fsync_directory(path.parent)
        if path.read_bytes() != payload:
            raise CatalogError("generated catalog atomic write read-back mismatch")
    except BaseException as error:
        try:
            if replaced and previous is not None:
                _restore_bytes(path, previous, previous_mode)
            elif replaced and path.exists():
                _regular_file(path, "generated catalog output")
                if path.read_bytes() != payload:
                    raise CatalogError(
                        "generated catalog changed; refusing recovery removal"
                    )
                path.unlink()
                _fsync_directory(path.parent)
        except BaseException as restore_error:  # noqa: BLE001 - preserve recovery evidence
            raise CatalogError(
                "generated catalog write failed and recovery failed: "
                f"{type(error).__name__}; {type(restore_error).__name__}"
            ) from error
        raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _restore_bytes(path: Path, payload: bytes, mode: int) -> None:
    _canonical_path(path, "generated catalog recovery output")
    _regular_file(path, "generated catalog recovery output")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.restore.", dir=path.parent
    )
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        if path.read_bytes() != payload or stat.S_IMODE(path.lstat().st_mode) != mode:
            raise CatalogError("generated catalog recovery read-back mismatch")
        _fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
