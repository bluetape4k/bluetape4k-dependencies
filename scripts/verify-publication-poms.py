#!/usr/bin/env python3
"""Generate and validate publication POMs across bluetape4k library repositories.

The central catalog is a Gradle authoring contract, but its versions can flow
into Maven publication metadata. This guard configures every publisher against
the candidate central catalog, generates its publication POMs, checks the POM
structure, and asks Maven to build every effective model in one reactor.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType
from typing import Iterable


@dataclasses.dataclass(frozen=True)
class Publisher:
    tasks: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class AuditResult:
    errors: tuple[str, ...]
    file_count: int
    dependency_count: int


PUBLISHERS = {
    "bluetape4k-dependencies": Publisher(("generatePomFileForBluetapeDependenciesPublication",)),
    "bluetape4k-projects": Publisher(("generatePomFileForBluetape4kPublication",)),
    "bluetape4k-aws": Publisher(("generatePomFileForBluetapeAwsPublication",)),
    "bluetape4k-exposed": Publisher(("generatePomFileForBluetapeExposedPublication",)),
    "bluetape4k-graph": Publisher(("generatePomFileForBluetapeGraphPublication",)),
    "bluetape4k-image": Publisher(("generatePomFileForBluetapeImagePublication",)),
    "bluetape4k-javers": Publisher(("generatePomFileForBluetapeJaversPublication",)),
    "bluetape4k-leader": Publisher(
        (
            "generatePomFileForBluetapeLeaderPublication",
            "generatePomFileForBluetapeLeaderBomPublication",
        ),
    ),
    "bluetape4k-text": Publisher(("generatePomFileForBluetapeTextPublication",)),
}

SELF_REPOSITORY = "bluetape4k-dependencies"
NON_PUBLISHING_CATALOG_CONSUMERS = frozenset({"bluetape4k-experimental"})
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = SCRIPT_ROOT / "config" / "publication-pom-maven-settings.xml"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def direct_child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if local_name(child.tag) == name), None)


def child_text(element: ET.Element, name: str) -> str:
    child = direct_child(element, name)
    return "" if child is None or child.text is None else child.text.strip()


def dependencies_at(project: ET.Element, container_names: tuple[str, ...]) -> list[ET.Element]:
    current = project
    for name in container_names:
        child = direct_child(current, name)
        if child is None:
            return []
        current = child
    return [child for child in current if local_name(child.tag) == "dependency"]


def coordinate(dependency: ET.Element) -> str:
    group_id = child_text(dependency, "groupId") or "<missing-groupId>"
    artifact_id = child_text(dependency, "artifactId") or "<missing-artifactId>"
    return f"{group_id}:{artifact_id}"


def audit_poms(paths: Iterable[Path]) -> AuditResult:
    pom_paths = tuple(sorted(Path(path).resolve() for path in paths))
    if not pom_paths:
        return AuditResult(("no publication POM files found",), 0, 0)

    errors: list[str] = []
    dependency_count = 0
    for path in pom_paths:
        try:
            project = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            errors.append(f"{path}: invalid XML: {str(exc).splitlines()[0]}")
            continue

        profiles = direct_child(project, "profiles")
        if profiles is not None:
            for profile in profiles:
                if local_name(profile.tag) != "profile":
                    continue
                profile_id = child_text(profile, "id") or "<missing-id>"
                errors.append(f"{path}: publication POM profiles are unsupported: {profile_id}")

        managed_dependencies = dependencies_at(project, ("dependencyManagement", "dependencies"))
        managed_coordinates = {
            coordinate(dependency)
            for dependency in managed_dependencies
            if child_text(dependency, "version")
        }
        has_versioned_bom_import = any(
            child_text(dependency, "version")
            and child_text(dependency, "type") == "pom"
            and child_text(dependency, "scope") == "import"
            for dependency in managed_dependencies
        )

        for dependency in managed_dependencies:
            dependency_count += 1
            if not child_text(dependency, "version"):
                errors.append(
                    f"{path}: missing dependencyManagement version: {coordinate(dependency)}",
                )

        for dependency in dependencies_at(project, ("dependencies",)):
            dependency_count += 1
            dependency_coordinate = coordinate(dependency)
            if child_text(dependency, "version"):
                continue
            if dependency_coordinate in managed_coordinates or has_versioned_bom_import:
                continue
            errors.append(f"{path}: unmanaged dependency has no version: {dependency_coordinate}")

    return AuditResult(tuple(sorted(errors)), len(pom_paths), dependency_count)


def publication_pom_paths(repository_root: Path) -> list[Path]:
    return sorted(
        path.resolve()
        for path in repository_root.rglob("pom-default.xml")
        if ".worktrees" not in path.relative_to(repository_root).parts
        and path.parent.parent.name == "publications"
        and path.parent.parent.parent.name == "build"
        and path.is_file()
    )


def clear_publication_poms(repository_root: Path) -> int:
    paths = publication_pom_paths(repository_root)
    for path in paths:
        path.unlink()
    return len(paths)


def discover_poms(repository_root: Path, repository: str) -> list[Path]:
    paths = publication_pom_paths(repository_root)
    if not paths:
        raise RuntimeError(f"no publication POM files found for {repository} under {repository_root}")
    return paths


def generate_poms(repository: str, repository_root: Path, publisher: Publisher, central_catalog: Path) -> None:
    gradlew = repository_root / "gradlew"
    if not gradlew.is_file():
        raise RuntimeError(f"missing Gradle wrapper for {repository}: {gradlew}")

    command = [
        str(gradlew),
        *publisher.tasks,
        "-PsnapshotVersion=-SNAPSHOT",
        "--rerun-tasks",
        "--no-daemon",
        "--no-configuration-cache",
        "--no-build-cache",
        "--console=plain",
    ]
    environment = os.environ.copy()
    environment["BLUETAPE4K_DEPENDENCIES_CATALOG_PATH"] = str(central_catalog)
    result = subprocess.run(
        command,
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).splitlines()
        diagnostics = "\n".join(output[-80:])
        raise RuntimeError(
            f"Gradle publication POM generation failed for {repository} (exit {result.returncode})\n{diagnostics}",
        )


def reactor_pom(modules: Iterable[str]) -> str:
    module_xml = "\n".join(f"    <module>{module}</module>" for module in modules)
    return f"""\
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>io.github.bluetape4k.validation</groupId>
  <artifactId>publication-pom-reactor</artifactId>
  <version>1</version>
  <packaging>pom</packaging>
  <modules>
{module_xml}
  </modules>
</project>
"""


def copy_reactor_pom(source: Path, target: Path) -> bool:
    """Copy a POM, normalizing Gradle's non-lifecycle `toml` packaging for Maven.

    The source is audited unchanged. Maven receives a temporary copy with
    `pom` packaging so it can build the dependency effective model instead of
    rejecting the Gradle version-catalog artifact before model validation.
    """
    project = ET.parse(source)
    packaging = direct_child(project.getroot(), "packaging")
    if packaging is None or (packaging.text or "").strip() != "toml":
        shutil.copy2(source, target)
        return False

    packaging.text = "pom"
    ET.register_namespace("", "http://maven.apache.org/POM/4.0.0")
    project.write(target, encoding="unicode", xml_declaration=False)
    return True


def validate_maven_models(
    paths: Iterable[Path],
    *,
    settings: Path = DEFAULT_SETTINGS,
    maven_command: str = "mvn",
) -> None:
    pom_paths = tuple(sorted(Path(path).resolve() for path in paths))
    if not pom_paths:
        raise RuntimeError("no publication POM files found for Maven validation")
    if not settings.is_file():
        raise RuntimeError(f"Maven settings file is missing: {settings}")

    with tempfile.TemporaryDirectory(prefix="publication-pom-reactor-") as tmp:
        reactor = Path(tmp)
        modules: list[str] = []
        for index, path in enumerate(pom_paths, start=1):
            module = f"module-{index:03d}"
            module_root = reactor / module
            module_root.mkdir()
            copy_reactor_pom(path, module_root / "pom.xml")
            modules.append(module)
        (reactor / "pom.xml").write_text(reactor_pom(modules), encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    maven_command,
                    "-U",
                    "-q",
                    "-B",
                    "-s",
                    str(settings),
                    "-f",
                    str(reactor / "pom.xml"),
                    "validate",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(f"Maven executable not found: {maven_command}") from exc
        if result.returncode != 0:
            output = (result.stdout + result.stderr).splitlines()
            errors = [line for line in output if "[ERROR]" in line]
            diagnostics = "\n".join((errors or output)[-80:])
            raise RuntimeError(f"Maven effective-model validation failed\n{diagnostics}")


def load_sync_module() -> ModuleType:
    script = SCRIPT_ROOT / "scripts" / "sync-shared-versions.py"
    spec = importlib.util.spec_from_file_location("publication_pom_sync_shared_versions", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load repository-map contract: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def publisher_inventory_errors(
    workspace: Path,
    managed_repositories: Iterable[str],
    repository_roots: dict[str, Path] | None = None,
) -> tuple[str, ...]:
    managed = set(managed_repositories)
    expected = {SELF_REPOSITORY, *(managed - NON_PUBLISHING_CATALOG_CONSUMERS)}
    configured = set(PUBLISHERS)
    errors: list[str] = []
    if configured != expected:
        errors.append(
            "managed publisher inventory mismatch: "
            f"missing={','.join(sorted(expected - configured)) or '<none>'} "
            f"extra={','.join(sorted(configured - expected)) or '<none>'}",
        )

    candidates = managed | {SELF_REPOSITORY}
    workflow_publishers = {
        repository
        for repository in candidates
        if (
            (repository_roots or {}).get(repository, workspace / repository)
            / ".github"
            / "workflows"
            / "publish-snapshot.yml"
        ).is_file()
    }
    if workflow_publishers != configured:
        errors.append(
            "publish workflow inventory mismatch: "
            f"missing={','.join(sorted(configured - workflow_publishers)) or '<none>'} "
            f"extra={','.join(sorted(workflow_publishers - configured)) or '<none>'}",
        )
    return tuple(errors)


def resolve_repository_roots(
    repositories: tuple[str, ...],
    workspace: Path,
    repository_map: Path | None,
) -> dict[str, Path]:
    roots = {SELF_REPOSITORY: SCRIPT_ROOT}
    downstream = tuple(repository for repository in repositories if repository != SELF_REPOSITORY)
    if repository_map is not None:
        sync = load_sync_module()
        mapped = sync.load_repository_map(repository_map, workspace, sync.DEFAULT_REPOSITORIES)
        missing = sorted(set(downstream) - set(mapped))
        if missing:
            raise RuntimeError(f"repository map is missing publisher repositories: {', '.join(missing)}")
        roots.update({repository: mapped[repository].catalog.parents[1] for repository in downstream})
    else:
        roots.update({repository: (workspace / repository).resolve() for repository in downstream})

    for repository in repositories:
        root = roots[repository]
        if not root.is_dir():
            raise RuntimeError(f"missing publisher repository: {repository} ({root})")
    return {repository: roots[repository] for repository in repositories}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=SCRIPT_ROOT.parent,
        help="Workspace directory containing bluetape4k sibling repositories.",
    )
    parser.add_argument(
        "--repo",
        action="append",
        dest="repositories",
        help="Publisher repository to validate. May be repeated. Defaults to every publisher.",
    )
    parser.add_argument(
        "--repository-map",
        type=Path,
        help="Exact candidate repository map accepted by sync-shared-versions.py.",
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Audit existing publication outputs without invoking Gradle.",
    )
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS, help="Maven settings file.")
    parser.add_argument("--maven-command", default="mvn", help="Maven executable.")
    parser.add_argument("--summary", action="store_true", help="Print per-repository POM counts.")
    parser.add_argument(
        "--print-default-repositories",
        action="store_true",
        help="Print downstream publisher repositories for CI checkout and exit.",
    )
    args = parser.parse_args()

    if args.print_default_repositories:
        for repository in PUBLISHERS:
            if repository != SELF_REPOSITORY:
                print(repository)
        return 0

    repositories = tuple(args.repositories) if args.repositories else tuple(PUBLISHERS)
    unknown = sorted(set(repositories) - set(PUBLISHERS))
    if unknown:
        print(f"Unknown publisher repositories: {', '.join(unknown)}", file=sys.stderr)
        return 2

    central_catalog = SCRIPT_ROOT / "gradle" / "libs.versions.toml"
    try:
        sync = load_sync_module()
        roots = resolve_repository_roots(repositories, args.workspace.resolve(), args.repository_map)
        inventory_errors = publisher_inventory_errors(args.workspace.resolve(), sync.DEFAULT_REPOSITORIES, roots)
        if inventory_errors:
            raise RuntimeError("\n".join(inventory_errors))
        all_poms: list[Path] = []
        counts: dict[str, int] = {}
        for repository in repositories:
            if not args.skip_generation:
                clear_publication_poms(roots[repository])
                generate_poms(repository, roots[repository], PUBLISHERS[repository], central_catalog)
            paths = discover_poms(roots[repository], repository)
            counts[repository] = len(paths)
            all_poms.extend(paths)

        audit = audit_poms(all_poms)
        if audit.errors:
            raise RuntimeError("\n".join(audit.errors))
        validate_maven_models(all_poms, settings=args.settings, maven_command=args.maven_command)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.summary:
        for repository in repositories:
            print(f"{repository}: publication_poms={counts[repository]}")
    print(
        "publication-poms: "
        f"failures=0 repositories={len(repositories)} files={audit.file_count} "
        f"dependencies={audit.dependency_count} maven_models={audit.file_count}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
