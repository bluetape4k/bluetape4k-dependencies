#!/usr/bin/env python3
"""Verify Detekt/Kotlin compiler resolution across the consumer inventory.

The catalog comment is only an explanation. This guard inspects the actual
consumer Gradle sources and, when requested, runs each consumer's Detekt
configuration dependency report or root NO-SOURCE canary.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = SCRIPT_ROOT / "config" / "detekt-kotlin-compatibility-consumers.json"
DEFAULT_CATALOG = SCRIPT_ROOT / "gradle" / "libs.versions.toml"
SUPPORTED_SCHEMA_VERSION = 1
GRADLE_SKIP_PARTS = frozenset({".git", ".gradle", ".kotlin", "build", ".worktrees"})
DETekt_PLUGIN_PATTERNS = (
    re.compile(r"\bdev\.detekt\b"),
    re.compile(r"\b(?:bt4k|libs)\.plugins\.detekt(?:\.dev)?\b"),
    re.compile(r"\balias\([^\n]*detekt[^\n]*\)"),
)
RESOLVER_PATTERN = re.compile(r"(?m)^(?!\s*(?://|/\*|\*)).*getSupportedKotlinVersion\s*\(")
@dataclasses.dataclass(frozen=True)
class Consumer:
    repository: str
    catalog: str
    root_only: bool
    probe_project: str | None


def default_workspace() -> Path:
    for parent in (SCRIPT_ROOT, *SCRIPT_ROOT.parents):
        candidate = parent / "bluetape4k-aws"
        if candidate.is_dir():
            return parent
    return SCRIPT_ROOT.parent


def _require_string(value: Any, field: str, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"manifest field {field} must be a non-empty string")
    return value


def load_manifest(path: Path) -> tuple[dict[str, Any], tuple[Consumer, ...]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError("unsupported Detekt compatibility manifest schema")
    plugin = document.get("plugin")
    if not isinstance(plugin, dict):
        raise ValueError("manifest plugin metadata is required")
    for field in ("id", "version", "supported_kotlin_compiler", "resolver"):
        _require_string(plugin.get(field), f"plugin.{field}")

    consumers: list[Consumer] = []
    seen: set[str] = set()
    for section, root_only in (("active", False), ("root_only", True)):
        entries = document.get(section)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"manifest section {section} must be a non-empty list")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValueError(f"manifest {section}[{index}] must be an object")
            repository = _require_string(entry.get("repository"), f"{section}[{index}].repository")
            catalog = _require_string(entry.get("catalog"), f"{section}[{index}].catalog")
            if catalog not in {"central", "local"}:
                raise ValueError(f"unsupported catalog mode for {repository}: {catalog}")
            probe_project = _require_string(
                entry.get("probe_project"),
                f"{section}[{index}].probe_project",
                allow_none=True,
            )
            if not root_only and "probe_project" not in entry:
                raise ValueError(f"active consumer {repository} is missing probe_project")
            if repository in seen:
                raise ValueError(f"duplicate consumer in manifest: {repository}")
            seen.add(repository)
            consumers.append(Consumer(repository, catalog, root_only, probe_project))

    excluded = document.get("excluded")
    if not isinstance(excluded, list):
        raise ValueError("manifest excluded section must be a list")
    for index, entry in enumerate(excluded):
        if not isinstance(entry, dict):
            raise ValueError(f"manifest excluded[{index}] must be an object")
        repository = _require_string(entry.get("repository"), f"excluded[{index}].repository")
        _require_string(entry.get("reason"), f"excluded[{index}].reason")
        if repository in seen:
            raise ValueError(f"excluded consumer overlaps active inventory: {repository}")
        seen.add(repository)
    return document, tuple(consumers)


def gradle_files(repository_root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for current_root, directory_names, file_names in os.walk(repository_root):
        directory_names[:] = sorted(
            name for name in directory_names if name not in GRADLE_SKIP_PARTS
        )
        for file_name in file_names:
            if file_name.endswith(".gradle.kts"):
                files.append(Path(current_root) / file_name)
    return tuple(sorted(files))


def repository_head(repository_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repository_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        return None
    head = completed.stdout.strip()
    return head if re.fullmatch(r"[0-9a-f]{40}", head) else None


def _contains_plugin(text: str) -> bool:
    return any(pattern.search(text) for pattern in DETekt_PLUGIN_PATTERNS)


def inspect_static(consumer: Consumer, repository_root: Path) -> list[str]:
    if not repository_root.is_dir():
        return [f"repository checkout is missing: {repository_root}"]
    files = gradle_files(repository_root)
    if not files:
        return ["repository contains no Gradle Kotlin build scripts"]
    texts = {path: path.read_text(encoding="utf-8") for path in files}
    root_build = repository_root / "build.gradle.kts"
    errors: list[str] = []
    if not root_build.is_file():
        errors.append("root build.gradle.kts is missing")
    if not any(_contains_plugin(text) for text in texts.values()):
        errors.append("Detekt plugin declaration is missing")

    if consumer.root_only:
        non_root_plugin_files = [
            str(path.relative_to(repository_root))
            for path, text in texts.items()
            if path != root_build and _contains_plugin(text)
        ]
        if non_root_plugin_files:
            errors.append(
                "root-only consumer now applies Detekt outside the root build: "
                + ", ".join(non_root_plugin_files)
            )
    else:
        if not any(RESOLVER_PATTERN.search(text) for text in texts.values()):
            errors.append("getSupportedKotlinVersion() resolver is missing from consumer build scripts")

    if consumer.catalog == "central":
        settings = repository_root / "settings.gradle.kts"
        settings_text = settings.read_text(encoding="utf-8") if settings.is_file() else ""
        if "BLUETAPE4K_DEPENDENCIES_CATALOG_PATH" not in settings_text:
            errors.append("central-catalog consumer does not expose the catalog path override")
    return errors


def _command_for(consumer: Consumer) -> tuple[str, ...]:
    if consumer.root_only:
        return ("./gradlew", "detekt", "--rerun-tasks")
    target = "dependencies" if consumer.probe_project is None else f"{consumer.probe_project}:dependencies"
    return ("./gradlew", target, "--configuration", "detekt")


def _resolved_versions(output: str, coordinate: str) -> tuple[str, ...]:
    """Extract selected versions for one module from a Gradle dependency report.

    Gradle prints both the requested and selected version when conflict
    resolution changes a dependency, for example ``2.4.10 -> 2.4.21``.  A
    substring check would accept that output, so the verifier reads the
    right-hand side of the arrow and also handles strict constraints such as
    ``{strictly 2.4.10} -> 2.4.10``.
    """

    versions: list[str] = []
    prefix = f"{coordinate}:"
    for line in output.splitlines():
        coordinate_index = line.find(prefix)
        if coordinate_index < 0:
            continue
        suffix = line[coordinate_index + len(prefix) :].strip()
        if suffix.startswith("{strictly "):
            strict_end = suffix.find("}")
            if strict_end < 0:
                continue
            suffix = suffix[strict_end + 1 :].strip()
        if "->" in suffix:
            selected = suffix.split("->", 1)[1].strip().split()[0]
        else:
            selected = suffix.split()[0] if suffix else ""
        selected = selected.rstrip("(*)").strip()
        if selected:
            versions.append(selected)
    return tuple(versions)


def _require_resolved_version(
    output: str,
    coordinate: str,
    expected_version: str,
    *,
    label: str,
) -> str | None:
    selected_versions = _resolved_versions(output, coordinate)
    if not selected_versions:
        return f"dependency report is missing {coordinate}:{expected_version}"
    mismatches = sorted(set(selected_versions) - {expected_version})
    if mismatches:
        return (
            f"{label} resolved to unexpected version(s): "
            f"{', '.join(mismatches)}; expected {expected_version}"
        )
    return None


def run_probe(
    consumer: Consumer,
    repository_root: Path,
    catalog: Path,
    *,
    timeout_seconds: float,
    plugin_version: str,
    kotlin_compiler: str,
) -> dict[str, Any]:
    command = (
        *_command_for(consumer),
        "--no-daemon",
        "--no-configuration-cache",
        "--console=plain",
    )
    environment = dict(os.environ)
    if consumer.catalog == "central":
        environment["BLUETAPE4K_DEPENDENCIES_CATALOG_PATH"] = str(catalog.resolve())
    try:
        completed = subprocess.run(
            command,
            cwd=repository_root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return {
            "status": "failed",
            "returncode": 124,
            "command": list(command),
            "error": f"timed out after {timeout_seconds:g}s",
            "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
            "markers": _markers(output),
        }

    output = completed.stdout
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"Gradle returned {completed.returncode}")
    if "BUILD SUCCESSFUL" not in output:
        errors.append("Gradle output does not contain BUILD SUCCESSFUL")
    if consumer.root_only:
        if not re.search(r"Task :detekt NO-SOURCE\b", output):
            errors.append("root-only detekt canary did not remain NO-SOURCE")
        if re.search(r"Task :[^\s:]+(?::[^\s:]+)*:detekt\b", output):
            errors.append("root-only detekt canary scheduled a subproject detekt task")
    else:
        plugin_error = _require_resolved_version(
            output,
            "dev.detekt:detekt-cli",
            plugin_version,
            label="Detekt CLI",
        )
        compiler_error = _require_resolved_version(
            output,
            "org.jetbrains.kotlin:kotlin-compiler",
            kotlin_compiler,
            label="Kotlin compiler",
        )
        if plugin_error:
            errors.append(plugin_error)
        if compiler_error:
            errors.append(compiler_error)
    return {
        "status": "passed" if not errors else "failed",
        "returncode": completed.returncode,
        "command": list(command),
        "errors": errors,
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "markers": _markers(output),
    }


def _markers(output: str) -> list[str]:
    markers = []
    for line in output.splitlines():
        stripped = line.strip()
        if any(
            token in stripped
            for token in (
                "BUILD SUCCESSFUL",
                "BUILD FAILED",
                "NO-SOURCE",
                "dev.detekt:detekt-cli:",
                "org.jetbrains.kotlin:kotlin-compiler:",
                "FAILURE:",
            )
        ):
            markers.append(stripped)
    return markers[-40:]


def verify(
    *,
    workspace: Path,
    catalog: Path,
    manifest: Path,
    run_gradle: bool,
    timeout_seconds: float,
    max_concurrency: int,
) -> dict[str, Any]:
    if max_concurrency < 1:
        raise ValueError("max concurrency must be positive")
    document, consumers = load_manifest(manifest)
    plugin = document["plugin"]
    if not catalog.is_file():
        raise ValueError(f"catalog is missing: {catalog}")
    catalog_sha256 = hashlib.sha256(catalog.read_bytes()).hexdigest()
    manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
    results: list[dict[str, Any]] = []
    pending_probes: list[tuple[int, Consumer, Path]] = []
    for index, consumer in enumerate(consumers):
        repository_root = workspace / consumer.repository
        static_errors = inspect_static(consumer, repository_root)
        head = repository_head(repository_root) if repository_root.is_dir() else None
        if head is None:
            static_errors.append("consumer checkout HEAD is unavailable")
        result: dict[str, Any] = {
            "repository": consumer.repository,
            "catalog": consumer.catalog,
            "scope": "root-only" if consumer.root_only else "active",
            "head_sha": head,
            "static": {"status": "passed" if not static_errors else "failed", "errors": static_errors},
        }
        if run_gradle and not static_errors:
            pending_probes.append((index, consumer, repository_root))
        results.append(result)
    if pending_probes:
        workers = min(max_concurrency, len(pending_probes))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    run_probe,
                    consumer,
                    repository_root,
                    catalog,
                    timeout_seconds=timeout_seconds,
                    plugin_version=plugin["version"],
                    kotlin_compiler=plugin["supported_kotlin_compiler"],
                ): index
                for index, consumer, repository_root in pending_probes
            }
            for future in concurrent.futures.as_completed(futures):
                results[futures[future]]["probe"] = future.result()
    failed = [item for item in results if item["static"]["status"] == "failed"]
    if run_gradle:
        failed.extend(item for item in results if item.get("probe", {}).get("status") == "failed")
    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "manifest": str(manifest),
        "workspace": str(workspace),
        "catalog": str(catalog),
        "catalog_sha256": catalog_sha256,
        "manifest_sha256": manifest_sha256,
        "run_gradle": run_gradle,
        "max_concurrency": max_concurrency,
        "timeout_seconds": timeout_seconds,
        "consumer_count": len(results),
        "passed_count": len(results) - len({item["repository"] for item in failed}),
        "failed_repositories": sorted({item["repository"] for item in failed}),
        "results": results,
    }


def _print_text(report: dict[str, Any]) -> None:
    for item in report["results"]:
        status = item["static"]["status"]
        probe = item.get("probe")
        if probe is not None:
            status = "failed" if probe["status"] == "failed" else status
        print(f"[{status.upper()}] {item['repository']} ({item['scope']}, {item['catalog']})")
        for error in item["static"].get("errors", ()):
            print(f"  static: {error}")
        for error in (probe or {}).get("errors", ()):
            print(f"  probe: {error}")
    print(
        f"Summary: {report['consumer_count']} consumers, "
        f"{len(report['failed_repositories'])} failed"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=default_workspace())
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-gradle", action="store_true")
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--max-concurrency", type=int, default=4)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        report = verify(
            workspace=args.workspace.resolve(),
            catalog=args.catalog.resolve(),
            manifest=args.manifest.resolve(),
            run_gradle=args.run_gradle,
            timeout_seconds=args.timeout,
            max_concurrency=args.max_concurrency,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.as_json:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 1 if report["failed_repositories"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
