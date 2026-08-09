#!/usr/bin/env python3
"""Sync downstream Dependabot ignores for centrally managed dependencies.

Downstream repositories should not receive Dependabot PRs for dependency
versions owned by bluetape4k-dependencies. Those versions must be changed in
this repository first, then propagated with sync-shared-versions.py.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import importlib.util
import sys
from pathlib import Path

SYNC_SHARED_VERSIONS_PATH = (
    Path(__file__).resolve().with_name("sync-shared-versions.py")
)
SYNC_SHARED_SPEC = importlib.util.spec_from_file_location(
    "sync_shared_versions", SYNC_SHARED_VERSIONS_PATH
)
if SYNC_SHARED_SPEC is None or SYNC_SHARED_SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SYNC_SHARED_VERSIONS_PATH}")
sync_shared_versions = importlib.util.module_from_spec(SYNC_SHARED_SPEC)
sys.modules["sync_shared_versions"] = sync_shared_versions
SYNC_SHARED_SPEC.loader.exec_module(sync_shared_versions)
DEFAULT_REPOSITORIES = sync_shared_versions.DEFAULT_REPOSITORIES


MARKER_START = (
    "      # <central-dependency-ignore by scripts/sync-dependabot-ignores.py>"
)
MARKER_END = "      # </central-dependency-ignore>"

CENTRAL_DEPENDENCY_IGNORES = (
    "io.github.bluetape4k*",
    "org.jetbrains.kotlin*",
    "org.jetbrains.kotlinx*",
    "org.jetbrains.dokka",
    "org.jetbrains.kotlinx:kover-gradle-plugin",
    "io.spring.gradle:dependency-management-plugin",
    "org.springframework.boot",
    "org.springframework.boot:*",
    "com.fasterxml.jackson*",
    "tools.jackson*",
    "org.bouncycastle:*",
    "com.ongres.scram:*",
    "io.github.classgraph:classgraph",
    "org.apache.tomcat:*",
    "org.apache.tomcat.embed:*",
    "org.jetbrains.exposed:*",
    "io.lettuce:lettuce-core",
    "org.redisson:*",
    "org.apache.kafka:*",
    "org.springframework.kafka:*",
    "org.springframework.retry:*",
    "io.projectreactor.kafka:*",
    "org.testcontainers:*",
    "org.apache.fory:*",
    "software.amazon.awssdk:*",
    "software.amazon.awssdk.crt:*",
    "aws.sdk.kotlin:*",
    "io.fabric8:*",
    "io.ktor:*",
    "io.netty:*",
    "com.google.protobuf:*",
    "org.slf4j:*",
    "io.vertx:*",
    "com.google.guava:guava",
    "org.ow2.asm:*",
    "com.github.luben:zstd-jni",
    "jakarta.xml.bind:jakarta.xml.bind-api",
    "com.hazelcast:hazelcast",
    "com.sksamuel.scrimage:*",
    "ai.timefold.solver:*",
    "org.flywaydb:*",
    "com.gradleup.shadow",
    "org.springdoc:*",
    "org.postgresql:postgresql",
    "com.mysql:mysql-connector-j",
    "io.r2dbc:r2dbc-h2",
    "io.projectreactor:reactor-bom",
    "io.gatling*",
    "io.github.hakky54:logcaptor",
    "io.agroal:*",
    "org.javamoney:moneta",
    "org.mybatis.dynamic-sql:mybatis-dynamic-sql",
    "org.webjars:webjars-locator-core",
    "org.apache.commons:commons-csv",
    "org.apache.commons:commons-exec",
    "org.apache.commons:commons-pool2",
    "commons-io:commons-io",
    "commons-codec:commons-codec",
    "commons-logging:commons-logging",
)


@dataclasses.dataclass(frozen=True)
class DependabotChange:
    repo: str
    path: Path


def default_workspace() -> Path:
    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if parent.name == "bluetape4k-dependencies":
            return parent.parent
    return script_path.parents[2]


def generated_block() -> list[str]:
    lines = [
        MARKER_START,
        "      # Versions below are governed by bluetape4k-dependencies.",
        "      # Update the central catalog first, then propagate downstream.",
    ]
    for dependency_name in CENTRAL_DEPENDENCY_IGNORES:
        lines.append(f'      - dependency-name: "{dependency_name}"')
    lines.append(MARKER_END)
    return lines


def remove_existing_block(lines: list[str]) -> list[str]:
    result: list[str] = []
    in_block = False
    for line in lines:
        if line == MARKER_START:
            in_block = True
            continue
        if line == MARKER_END:
            in_block = False
            continue
        if not in_block:
            result.append(line)
    return result


def sync_text(text: str) -> str:
    lines = remove_existing_block(text.splitlines())
    gradle_update_start = next(
        (
            index
            for index, line in enumerate(lines)
            if line == '  - package-ecosystem: "gradle"'
        ),
        None,
    )
    if gradle_update_start is None:
        return "\n".join(lines) + "\n"

    next_update = next(
        (
            index
            for index in range(gradle_update_start + 1, len(lines))
            if lines[index].startswith("  - package-ecosystem: ")
        ),
        len(lines),
    )
    ignore_index = next(
        (
            index
            for index in range(gradle_update_start, next_update)
            if lines[index] == "    ignore:"
        ),
        None,
    )

    block = generated_block()
    if ignore_index is None:
        insert_index = next_update
        lines[insert_index:insert_index] = ["    ignore:", *block]
    else:
        lines[ignore_index + 1 : ignore_index + 1] = block
    return "\n".join(lines) + "\n"


def target_files(workspace: Path, repositories: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for repo in repositories:
        config = workspace / repo / ".github" / "dependabot.yml"
        if config.exists():
            files.append(config)
    return files


def candidate_dependabot_file(repository_root: Path) -> Path | None:
    config = repository_root / ".github" / "dependabot.yml"
    if not config.exists() and not config.is_symlink():
        return None
    if config.is_symlink() or not config.is_file() or config.resolve() != config:
        raise RuntimeError(f"candidate Dependabot config must be a regular non-symlink file: {config}")
    try:
        config.relative_to(repository_root)
    except ValueError as exc:
        raise RuntimeError(f"candidate Dependabot config escapes repository root: {config}") from exc
    return config


def candidate_repository_root(catalog: Path) -> Path:
    if catalog.name != "libs.versions.toml" or catalog.parent.name != "gradle":
        raise RuntimeError(f"candidate catalog path is not canonical: {catalog}")
    return catalog.parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=default_workspace(),
        help="Workspace containing sibling repositories.",
    )
    parser.add_argument(
        "--repo",
        dest="repositories",
        action="append",
        help="Repository directory to sync. May be passed multiple times.",
    )
    parser.add_argument(
        "--repository-map",
        type=Path,
        help="Strict v1 candidate repository map; disables sibling discovery.",
    )
    parser.add_argument(
        "--write", action="store_true", help="Rewrite downstream dependabot.yml files."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail when files are not synced."
    )
    parser.add_argument("--summary", action="store_true", help="Print changed files.")
    parser.add_argument(
        "--diff", action="store_true", help="Print unified diffs for required changes."
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    repositories = (
        tuple(args.repositories) if args.repositories else DEFAULT_REPOSITORIES
    )
    if args.repository_map:
        unknown = sorted(set(repositories) - set(DEFAULT_REPOSITORIES))
        if unknown:
            print(
                f"Unknown managed repositories: {', '.join(unknown)}",
                file=sys.stderr,
            )
            return 2
        try:
            mapped = sync_shared_versions.load_repository_map(
                args.repository_map, workspace, DEFAULT_REPOSITORIES
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        try:
            targets = []
            for repo in repositories:
                config = candidate_dependabot_file(
                    candidate_repository_root(mapped[repo].catalog)
                )
                if config is not None:
                    targets.append((repo, config))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    else:
        files = target_files(workspace, repositories)
        targets = [(config.parents[1].name, config) for config in files]
    changes: list[DependabotChange] = []

    if not targets:
        print(
            "No downstream Dependabot files found. "
            f"Check --workspace ({workspace}) and --repo filters.",
            file=sys.stderr,
        )
        return 1 if args.check else 0

    for repository, config in targets:
        before = config.read_text(encoding="utf-8")
        after = sync_text(before)
        if before == after:
            continue
        changes.append(DependabotChange(repo=repository, path=config))
        if args.diff:
            sys.stdout.writelines(
                difflib.unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile=str(config),
                    tofile=str(config),
                ),
            )
        if args.write:
            if args.repository_map:
                sync_shared_versions.catalog_candidate.write_atomic(
                    config, after.encode("utf-8")
                )
            else:
                config.write_text(after, encoding="utf-8")

    if args.summary or changes:
        for change in changes:
            print(f"{change.repo}: {change.path}")

    if args.check and changes and not args.write:
        print(
            f"Dependabot ignore drift detected: {len(changes)} files require updates.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
