from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync-managed-catalog.py"
SPEC = importlib.util.spec_from_file_location("sync_managed_catalog", SCRIPT_PATH)
assert SPEC is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_managed_catalog"] = sync
assert SPEC.loader is not None
SPEC.loader.exec_module(sync)


class SyncManagedCatalogTest(unittest.TestCase):
    def test_function_call_args_handles_nested_parentheses_and_multiline_calls(self) -> None:
        text = """
            includeModules(
                "graph-io",
                false,
                true,
                excludeModuleNames = setOf("okio", "tmp"),
            )
        """

        calls = sync.function_call_args(text, "includeModules")

        self.assertEqual(len(calls), 1)
        self.assertIn('setOf("okio", "tmp")', calls[0])

    def test_parse_include_configs_keeps_excluded_module_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeModules(
                    "graph-io",
                    false,
                    true,
                    excludeModuleNames = setOf("okio"),
                )
                """,
                encoding="utf-8",
            )

            configs = sync.parse_include_configs(settings_file)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].base_dir, "graph-io")
        self.assertFalse(configs[0].with_project_name)
        self.assertTrue(configs[0].with_base_dir)
        self.assertEqual(configs[0].exclude_module_names, frozenset({"okio"}))

    def test_parse_include_configs_supports_exposed_short_module_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeModules("exposed", withBaseDir = false)

                fun includeModules(baseDir: String, withBaseDir: Boolean = true) {
                    // implementation omitted
                }
                """,
                encoding="utf-8",
            )

            configs = sync.parse_include_configs(settings_file)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].base_dir, "exposed")
        self.assertFalse(configs[0].with_project_name)
        self.assertFalse(configs[0].with_base_dir)
        self.assertEqual(sync.module_name(configs[0], "exposed-core"), "exposed-core")

    def test_parse_mapped_includes_keeps_path_and_project_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeMappedModule("utils/batch", "exposed-batch")
                includeMappedModule("spring-boot/exposed-jdbc", "exposed-spring-boot-jdbc")
                """,
                encoding="utf-8",
            )

            mapped_includes = sync.parse_mapped_includes(settings_file)

        self.assertEqual(
            mapped_includes,
            [
                sync.MappedInclude("utils/batch", "exposed-batch"),
                sync.MappedInclude("spring-boot/exposed-jdbc", "exposed-spring-boot-jdbc"),
            ],
        )

    def test_discover_repo_modules_renders_exposed_short_and_mapped_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            repo_root = workspace_root / "bluetape4k-exposed"
            (repo_root / "exposed" / "exposed-core").mkdir(parents=True)
            (repo_root / "exposed" / "exposed-bom").mkdir(parents=True)
            (repo_root / "spring-boot" / "exposed-jdbc").mkdir(parents=True)

            for build_file in [
                repo_root / "exposed" / "exposed-core" / "build.gradle.kts",
                repo_root / "exposed" / "exposed-bom" / "build.gradle.kts",
                repo_root / "spring-boot" / "exposed-jdbc" / "build.gradle.kts",
            ]:
                build_file.write_text("", encoding="utf-8")

            (repo_root / "settings.gradle.kts").write_text(
                """
                rootProject.name = "bluetape4k-exposed"

                includeModules("exposed", withBaseDir = false)
                includeMappedModule("spring-boot/exposed-jdbc", "exposed-spring-boot-jdbc")

                fun includeModules(baseDir: String, withBaseDir: Boolean = true) {
                    // implementation omitted
                }
                """,
                encoding="utf-8",
            )

            repo = next(managed_repo for managed_repo in sync.MANAGED_REPOS if managed_repo.label == "bluetape4k-exposed")
            modules = sync.discover_repo_modules(workspace_root, repo)

        discovered = {repo: [] for repo in sync.MANAGED_REPOS}
        discovered[repo] = modules
        aliases = {module.alias: module for module in modules}
        self.assertEqual(sorted(aliases), ["exposed-bom", "exposed-core", "exposed-spring-boot-jdbc"])
        self.assertFalse(aliases["exposed-bom"].include_constraint)
        self.assertTrue(aliases["exposed-core"].include_constraint)
        self.assertTrue(aliases["exposed-spring-boot-jdbc"].include_constraint)

        catalog = sync.render_catalog_section(discovered)
        constraints = sync.render_constraint_section(discovered)

        self.assertIn('exposed-bom', catalog)
        self.assertIn('module = "io.github.bluetape4k.exposed:exposed-spring-boot-jdbc"', catalog)
        self.assertIn("api(libs.exposed.core)", constraints)
        self.assertIn("api(libs.exposed.spring.boot.jdbc)", constraints)
        self.assertNotIn("api(libs.exposed.bom)", constraints)

    def test_parse_direct_includes_ignores_include_modules_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeModules("graph", false, false)
                include(
                    "leader-core",
                    "examples:cache-warmer",
                )
                """,
                encoding="utf-8",
            )

            includes = sync.parse_direct_includes(settings_file)

        self.assertEqual(includes, ["leader-core", "examples:cache-warmer"])

    def test_validate_discovered_rejects_duplicate_aliases(self) -> None:
        repo = sync.MANAGED_REPOS[0]
        module = sync.Module(
            project_name="sample",
            artifact_id="sample",
            alias="duplicate",
            group_id="io.github.bluetape4k",
            version_ref="bluetape4k-bom",
            project_path=":sample",
            relative_path="sample",
            include_constraint=True,
        )
        discovered = {managed_repo: [] for managed_repo in sync.MANAGED_REPOS}
        discovered[repo] = [module, module]

        with self.assertRaisesRegex(RuntimeError, "Duplicate catalog aliases"):
            sync.validate_discovered(discovered)


if __name__ == "__main__":
    unittest.main()
