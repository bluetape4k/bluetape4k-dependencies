#!/usr/bin/env python3
"""Sync managed bluetape4k modules into this BOM repository.

The managed repositories derive many Gradle project names from
settings.gradle.kts. This script follows those include rules, applies the same
high-level BOM inclusion policy used by each upstream repository, and keeps:

* gradle/libs.versions.toml library aliases
* build.gradle.kts java-platform constraints

aligned with the actual sibling repositories.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path


SCRIPT_NAME = "scripts/sync-managed-catalog.py"
CATALOG_START = f"# <generated-managed-modules by {SCRIPT_NAME}>"
CATALOG_END = f"# </generated-managed-modules>"
CONSTRAINT_START = f"        // <generated-managed-modules by {SCRIPT_NAME}>"
CONSTRAINT_END = "        // </generated-managed-modules>"
MIN_CATALOG_ALIAS_WIDTH = 46


@dataclasses.dataclass(frozen=True)
class IncludeConfig:
    base_dir: str
    with_project_name: bool
    with_base_dir: bool
    exclude_module_names: frozenset[str] = frozenset()


@dataclasses.dataclass(frozen=True)
class MappedInclude:
    module_path: str
    project_name: str


@dataclasses.dataclass(frozen=True)
class Module:
    project_name: str
    artifact_id: str
    alias: str
    group_id: str
    version_ref: str
    project_path: str
    relative_path: str
    include_constraint: bool


@dataclasses.dataclass(frozen=True)
class ManagedRepo:
    label: str
    root_name: str
    group_id: str
    version_ref: str
    alias_mode: str
    exclude_path_fragments: tuple[str, ...] = ()
    exclude_name_suffixes: tuple[str, ...] = ()

    @property
    def root_dir(self) -> str:
        return self.root_name


MANAGED_REPOS: tuple[ManagedRepo, ...] = (
    ManagedRepo(
        label="bluetape4k-projects",
        root_name="bluetape4k-projects",
        group_id="io.github.bluetape4k",
        version_ref="bluetape4k-core",
        alias_mode="identity",
        exclude_path_fragments=("examples", "workshop"),
        exclude_name_suffixes=("-demo", "-benchmark"),
    ),
    ManagedRepo(
        label="bluetape4k-aws",
        root_name="bluetape4k-aws",
        group_id="io.github.bluetape4k.aws",
        version_ref="bluetape4k-aws",
        alias_mode="prefix",
        exclude_path_fragments=("examples",),
    ),
    ManagedRepo(
        label="bluetape4k-image",
        root_name="bluetape4k-image",
        group_id="io.github.bluetape4k.image",
        version_ref="bluetape4k-image",
        alias_mode="prefix",
        exclude_name_suffixes=("-benchmark",),
    ),
    ManagedRepo(
        label="bluetape4k-text",
        root_name="bluetape4k-text",
        group_id="io.github.bluetape4k.text",
        version_ref="bluetape4k-text",
        alias_mode="prefix",
    ),
    ManagedRepo(
        label="bluetape4k-graph",
        root_name="bluetape4k-graph",
        group_id="io.github.bluetape4k.graph",
        version_ref="bluetape4k-graph",
        alias_mode="prefix",
        exclude_path_fragments=("examples",),
    ),
    ManagedRepo(
        label="bluetape4k-leader",
        root_name="bluetape4k-leader",
        group_id="io.github.bluetape4k.leader",
        version_ref="bluetape4k-leader",
        alias_mode="prefix",
        exclude_path_fragments=("examples",),
    ),
    ManagedRepo(
        label="bluetape4k-exposed",
        root_name="bluetape4k-exposed",
        group_id="io.github.bluetape4k.exposed",
        version_ref="bluetape4k-exposed",
        alias_mode="identity",
        exclude_path_fragments=("examples",),
        exclude_name_suffixes=("-demo",),
    ),
    ManagedRepo(
        label="bluetape4k-javers",
        root_name="bluetape4k-javers",
        group_id="io.github.bluetape4k.javers",
        version_ref="bluetape4k-javers",
        alias_mode="prefix",
    ),
)


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


def function_call_args(text: str, function_name: str) -> list[str]:
    calls: list[str] = []
    index = 0
    needle = f"{function_name}("

    while True:
        start = text.find(needle, index)
        if start < 0:
            return calls
        if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            index = start + len(needle)
            continue

        cursor = start + len(needle)
        depth = 1
        in_string = False
        escaped = False

        while cursor < len(text):
            char = text[cursor]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        calls.append(text[start + len(needle) : cursor])
                        index = cursor + 1
                        break
            cursor += 1
        else:
            raise RuntimeError(f"Unclosed {function_name}(...) call")


def parse_set_of_strings(args: str, name: str) -> frozenset[str]:
    match = re.search(rf"{name}\s*=\s*setOf\(([^)]*)\)", args)
    if not match:
        return frozenset()
    return frozenset(re.findall(r'"([^"]+)"', match.group(1)))


def include_modules_default_with_project_name(text: str) -> bool:
    match = re.search(r"fun\s+includeModules\s*\((.*?)\)", text, flags=re.DOTALL)
    if not match:
        return True
    return "withProjectName" in match.group(1)


def parse_include_configs(settings_file: Path) -> list[IncludeConfig]:
    text = settings_file.read_text(encoding="utf-8")
    default_with_project_name = include_modules_default_with_project_name(text)
    configs: list[IncludeConfig] = []

    for args in function_call_args(text, "includeModules"):
        base_match = re.search(r'"([^"]+)"', args)
        if not base_match:
            continue

        positional_bools = [
            token == "true"
            for token in re.findall(r"(?:^|,\s*)(true|false)(?=,|\s*,|\s*$)", args)
        ]
        with_project_name = (
            positional_bools[0] if len(positional_bools) >= 1 else default_with_project_name
        )
        with_base_dir = positional_bools[1] if len(positional_bools) >= 2 else True

        named_project = re.search(r"withProjectName\s*=\s*(true|false)", args)
        named_base = re.search(r"withBaseDir\s*=\s*(true|false)", args)
        with_project_name = parse_bool(
            named_project.group(1) if named_project else None,
            with_project_name,
        )
        with_base_dir = parse_bool(
            named_base.group(1) if named_base else None,
            with_base_dir,
        )

        configs.append(
            IncludeConfig(
                base_dir=base_match.group(1),
                with_project_name=with_project_name,
                with_base_dir=with_base_dir,
                exclude_module_names=parse_set_of_strings(args, "excludeModuleNames"),
            )
        )

    return configs


def parse_mapped_includes(settings_file: Path) -> list[MappedInclude]:
    mapped_includes: list[MappedInclude] = []

    for args in function_call_args(settings_file.read_text(encoding="utf-8"), "includeMappedModule"):
        values = re.findall(r'"([^"]+)"', args)
        if len(values) < 2:
            continue
        mapped_includes.append(MappedInclude(module_path=values[0], project_name=values[1]))

    return mapped_includes


def parse_direct_includes(settings_file: Path) -> list[str]:
    text = settings_file.read_text(encoding="utf-8")
    includes: list[str] = []

    for args in function_call_args(text, "include"):
        includes.extend(re.findall(r'"([^"]+)"', args))

    return includes


def parse_project_dir_overrides(settings_file: Path) -> dict[str, str]:
    text = settings_file.read_text(encoding="utf-8")
    pattern = re.compile(r'project\(":(.*?)"\)\.projectDir\s*=\s*file\("([^"]+)"\)')
    return {name: path for name, path in pattern.findall(text)}


def module_name(config: IncludeConfig, directory_name: str, project_prefix: str = "bluetape4k") -> str:
    base_path = config.base_dir.replace("/", "-")
    if not config.with_project_name and not config.with_base_dir:
        return directory_name
    if config.with_project_name and not config.with_base_dir:
        return f"{project_prefix}-{directory_name}"
    if config.with_project_name:
        return f"{project_prefix}-{base_path}-{directory_name}"
    return f"{base_path}-{directory_name}"


def alias_for(repo: ManagedRepo, artifact_id: str) -> str:
    if repo.alias_mode == "identity" or artifact_id.startswith("bluetape4k-"):
        return artifact_id
    if repo.alias_mode == "prefix":
        return f"bluetape4k-{artifact_id}"
    raise RuntimeError(f"Unsupported alias mode: {repo.alias_mode}")


def to_libs_accessor(alias: str) -> str:
    return alias.replace("-", ".")


def is_bom(artifact_id: str) -> bool:
    return artifact_id.endswith("-bom")


def include_module(repo: ManagedRepo, artifact_id: str, relative_path: str) -> bool:
    path_parts = set(relative_path.split("/"))
    if any(fragment in path_parts for fragment in repo.exclude_path_fragments):
        return False
    return not any(artifact_id.endswith(suffix) for suffix in repo.exclude_name_suffixes)


def direct_include_relative_path(root: Path, project_name: str, overrides: dict[str, str]) -> str | None:
    candidates = []
    if project_name in overrides:
        candidates.append(Path(overrides[project_name]))
    candidates.append(Path(project_name.replace(":", "/")))

    for candidate in candidates:
        module_dir = root / candidate
        if (module_dir / "build.gradle.kts").is_file():
            return candidate.as_posix()

    return None


def discover_repo_modules(workspace_root: Path, repo: ManagedRepo) -> list[Module]:
    root = (workspace_root / repo.root_dir).resolve()
    settings_file = root / "settings.gradle.kts"
    if not settings_file.is_file():
        raise RuntimeError(f"Missing settings.gradle.kts: {settings_file}")

    modules: dict[str, Module] = {}
    overrides = parse_project_dir_overrides(settings_file)

    for project_path in parse_direct_includes(settings_file):
        project_name = project_path.split(":")[-1]
        relative_path = direct_include_relative_path(root, project_path, overrides)
        if relative_path is None:
            relative_path = direct_include_relative_path(root, project_name, overrides)
        if relative_path is None:
            continue
        if not include_module(repo, project_name, relative_path):
            continue

        modules[project_name] = Module(
            project_name=project_name,
            artifact_id=project_name,
            alias=alias_for(repo, project_name),
            group_id=repo.group_id,
            version_ref=repo.version_ref,
            project_path=f":{project_path}",
            relative_path=relative_path,
            include_constraint=not is_bom(project_name),
        )

    for config in parse_include_configs(settings_file):
        base = root / config.base_dir
        if not base.is_dir():
            raise RuntimeError(f"Configured module base does not exist: {base}")

        for module_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            if module_dir.name.startswith(".") or module_dir.name in config.exclude_module_names:
                continue

            if not (module_dir / "build.gradle.kts").is_file():
                continue

            project_name = module_name(config, module_dir.name)
            relative_path = module_dir.relative_to(root).as_posix()
            if not include_module(repo, project_name, relative_path):
                continue

            modules[project_name] = Module(
                project_name=project_name,
                artifact_id=project_name,
                alias=alias_for(repo, project_name),
                group_id=repo.group_id,
                version_ref=repo.version_ref,
                project_path=f":{project_name}",
                relative_path=relative_path,
                include_constraint=not is_bom(project_name),
            )

    for mapped_include in parse_mapped_includes(settings_file):
        module_dir = root / mapped_include.module_path
        if not (module_dir / "build.gradle.kts").is_file():
            continue

        project_name = mapped_include.project_name
        relative_path = module_dir.relative_to(root).as_posix()
        if not include_module(repo, project_name, relative_path):
            continue

        modules[project_name] = Module(
            project_name=project_name,
            artifact_id=project_name,
            alias=alias_for(repo, project_name),
            group_id=repo.group_id,
            version_ref=repo.version_ref,
            project_path=f":{project_name}",
            relative_path=relative_path,
            include_constraint=not is_bom(project_name),
        )

    if not modules:
        raise RuntimeError(f"No managed modules discovered for {repo.label} under {root}")

    return sorted(modules.values(), key=lambda module: module.alias)


def discover_all(workspace_root: Path) -> dict[ManagedRepo, list[Module]]:
    discovered = {repo: discover_repo_modules(workspace_root, repo) for repo in MANAGED_REPOS}
    validate_discovered(discovered)
    return discovered


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def validate_discovered(discovered: dict[ManagedRepo, list[Module]]) -> None:
    aliases = [module.alias for repo in MANAGED_REPOS for module in discovered[repo]]
    duplicate_aliases = duplicate_values(aliases)
    if duplicate_aliases:
        raise RuntimeError("Duplicate catalog aliases:\n  " + "\n  ".join(duplicate_aliases))

    gavs = [
        f"{module.group_id}:{module.artifact_id}"
        for repo in MANAGED_REPOS
        for module in discovered[repo]
    ]
    duplicate_gavs = duplicate_values(gavs)
    if duplicate_gavs:
        raise RuntimeError("Duplicate managed module coordinates:\n  " + "\n  ".join(duplicate_gavs))

    for repo in MANAGED_REPOS:
        repo_aliases = [module.alias for module in discovered[repo]]
        if repo_aliases != sorted(repo_aliases):
            raise RuntimeError(f"{repo.label} modules are not sorted by alias")


def render_catalog_section(discovered: dict[ManagedRepo, list[Module]]) -> str:
    modules = [module for repo in MANAGED_REPOS for module in discovered[repo]]
    max_alias = max(MIN_CATALOG_ALIAS_WIDTH, max(len(module.alias) for module in modules))
    lines = [CATALOG_START]

    for repo in MANAGED_REPOS:
        lines.append(f"# -- {repo.label} modules --")
        for module in discovered[repo]:
            lines.append(
                f'{module.alias:<{max_alias}} = {{ module = "{module.group_id}:{module.artifact_id}",'
                f' version.ref = "{module.version_ref}" }}'
            )
        lines.append("")

    lines.append(CATALOG_END)
    return "\n".join(lines).rstrip() + "\n"


def render_constraint_section(discovered: dict[ManagedRepo, list[Module]]) -> str:
    lines = [CONSTRAINT_START]

    for repo in MANAGED_REPOS:
        lines.append(f"        // -- {repo.label} modules --")
        for module in discovered[repo]:
            if module.include_constraint:
                lines.append(f"        api(libs.{to_libs_accessor(module.alias)})")
        lines.append("")

    lines.append(CONSTRAINT_END)
    return "\n".join(lines).rstrip() + "\n"


def replace_catalog(text: str, replacement: str) -> str:
    if CATALOG_START in text and CATALOG_END in text:
        pattern = re.compile(
            rf"^{re.escape(CATALOG_START)}\n.*?^{re.escape(CATALOG_END)}\n?",
            flags=re.MULTILINE | re.DOTALL,
        )
        return pattern.sub(replacement, text)

    start_match = re.search(r"^# .+bluetape4k-projects .*modules.*\n", text, flags=re.MULTILINE)
    if not start_match:
        raise RuntimeError("Could not find managed libraries start marker")
    return text[: start_match.start()] + replacement


def replace_constraints(text: str, replacement: str) -> str:
    if CONSTRAINT_START in text and CONSTRAINT_END in text:
        pattern = re.compile(
            rf"^\s*// <generated-managed-modules by {re.escape(SCRIPT_NAME)}>\n.*?^\s*// </generated-managed-modules>\n?",
            flags=re.MULTILINE | re.DOTALL,
        )
        return pattern.sub(replacement, text)

    start_match = re.search(r"^\s*// .+bluetape4k-projects .*modules.*\n", text, flags=re.MULTILINE)
    if not start_match:
        raise RuntimeError("Could not find managed constraints start marker")

    close_match = re.search(r"^    }\n}\n\nextensions\.configure", text[start_match.start() :], flags=re.MULTILINE)
    if not close_match:
        raise RuntimeError("Could not find managed constraints end")

    end = start_match.start() + close_match.start()
    return text[: start_match.start()] + replacement + text[end:]


def synced_text(repo_root: Path, discovered: dict[ManagedRepo, list[Module]]) -> tuple[str, str]:
    catalog_file = repo_root / "gradle" / "libs.versions.toml"
    build_file = repo_root / "build.gradle.kts"
    catalog_text = catalog_file.read_text(encoding="utf-8")
    build_text = build_file.read_text(encoding="utf-8")
    return (
        replace_catalog(catalog_text, render_catalog_section(discovered)),
        replace_constraints(build_text, render_constraint_section(discovered)),
    )


def write_if_changed(path: Path, text: str) -> bool:
    current = path.read_text(encoding="utf-8")
    if current == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def parse_catalog_aliases(catalog_file: Path) -> set[str]:
    text = catalog_file.read_text(encoding="utf-8")
    return set(
        re.findall(
            r'^([A-Za-z0-9_.-]+)\s*=\s*\{\s*module\s*=\s*"io\.github\.bluetape4k(?:\.[^:]+)?:',
            text,
            flags=re.MULTILINE,
        )
    )


def parse_build_accessors(build_file: Path) -> set[str]:
    text = build_file.read_text(encoding="utf-8")
    return set(re.findall(r"(?:api|platform)\(libs\.([A-Za-z0-9_.]+)\)", text))


def verify(repo_root: Path, discovered: dict[ManagedRepo, list[Module]]) -> list[str]:
    catalog_file = repo_root / "gradle" / "libs.versions.toml"
    build_file = repo_root / "build.gradle.kts"
    errors: list[str] = []
    expected_aliases = {module.alias for repo in MANAGED_REPOS for module in discovered[repo]}
    catalog_aliases = parse_catalog_aliases(catalog_file)
    build_accessors = parse_build_accessors(build_file)

    missing_aliases = sorted(expected_aliases - catalog_aliases)
    if missing_aliases:
        errors.append("Missing catalog aliases:\n  " + "\n  ".join(missing_aliases))

    missing_constraints = sorted(
        module.alias
        for repo in MANAGED_REPOS
        for module in discovered[repo]
        if module.include_constraint and to_libs_accessor(module.alias) not in build_accessors
    )
    if missing_constraints:
        errors.append("Missing build.gradle.kts constraints:\n  " + "\n  ".join(missing_constraints))

    missing_platforms = sorted(
        module.alias
        for repo in MANAGED_REPOS
        for module in discovered[repo]
        if is_bom(module.artifact_id) and to_libs_accessor(module.alias) not in build_accessors
    )
    if missing_platforms:
        errors.append("Missing build.gradle.kts platform BOM imports:\n  " + "\n  ".join(missing_platforms))

    expected_catalog, expected_build = synced_text(repo_root, discovered)
    if catalog_file.read_text(encoding="utf-8") != expected_catalog:
        errors.append(f"{catalog_file} is not generated from the current managed module set")
    if build_file.read_text(encoding="utf-8") != expected_build:
        errors.append(f"{build_file} is not generated from the current managed module set")

    return errors


def print_summary(discovered: dict[ManagedRepo, list[Module]]) -> None:
    for repo in MANAGED_REPOS:
        constrained = sum(1 for module in discovered[repo] if module.include_constraint)
        print(f"{repo.label}: aliases={len(discovered[repo])}, constraints={constrained}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(".."),
        help="Path containing the managed sibling repositories",
    )
    parser.add_argument("--write", action="store_true", help="Rewrite generated sections")
    parser.add_argument("--check", action="store_true", help="Verify generated sections and fail on drift")
    parser.add_argument("--summary", action="store_true", help="Print discovered module counts")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    workspace_root = args.workspace_root
    if not workspace_root.is_absolute():
        workspace_root = (repo_root / workspace_root).resolve()

    discovered = discover_all(workspace_root)

    if args.write:
        catalog_text, build_text = synced_text(repo_root, discovered)
        changed_catalog = write_if_changed(repo_root / "gradle" / "libs.versions.toml", catalog_text)
        changed_build = write_if_changed(repo_root / "build.gradle.kts", build_text)
        print(f"Updated gradle/libs.versions.toml: {changed_catalog}")
        print(f"Updated build.gradle.kts: {changed_build}")

    if args.summary:
        print_summary(discovered)

    if args.check or not args.write:
        errors = verify(repo_root, discovered)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        total_aliases = sum(len(discovered[repo]) for repo in MANAGED_REPOS)
        total_constraints = sum(
            1
            for repo in MANAGED_REPOS
            for module in discovered[repo]
            if module.include_constraint
        )
        print(f"Verified managed modules: aliases={total_aliases}, constraints={total_constraints}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
