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

    def test_parse_include_configs_keeps_excluded_module_names_and_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeModules(
                    "graph-io",
                    false,
                    true,
                    prefix = "bt4k-",
                    excludeModuleNames = setOf("okio"),
                    excludeDirNames = setOf("tmp"),
                )
                """,
                encoding="utf-8",
            )

            configs = sync.parse_include_configs(settings_file)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].base_dir, "graph-io")
        self.assertFalse(configs[0].with_project_name)
        self.assertTrue(configs[0].with_base_dir)
        self.assertEqual(configs[0].project_prefix, "bt4k-")
        self.assertEqual(configs[0].exclude_module_names, frozenset({"okio", "tmp"}))

    def test_parse_include_configs_supports_exposed_prefixed_module_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeModules("exposed", withBaseDir = false, prefix = "bluetape4k-")

                fun includeModules(baseDir: String, withBaseDir: Boolean = true, prefix: String = "") {
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
        self.assertEqual(sync.module_name(configs[0], "exposed-core"), "bluetape4k-exposed-core")

    def test_parse_mapped_includes_keeps_path_and_project_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "settings.gradle.kts"
            settings_file.write_text(
                """
                includeMappedModule("utils/batch", "exposed-batch")
                includeMappedModule("spring-boot/exposed-jdbc", "exposed-spring-boot-jdbc")
                includeProject("bluetape4k-exposed-bom", file("exposed/bluetape4k-exposed-bom"))
                """,
                encoding="utf-8",
            )

            mapped_includes = sync.parse_mapped_includes(settings_file)

        self.assertEqual(
            mapped_includes,
            [
                sync.MappedInclude("utils/batch", "exposed-batch"),
                sync.MappedInclude("spring-boot/exposed-jdbc", "exposed-spring-boot-jdbc"),
                sync.MappedInclude("exposed/bluetape4k-exposed-bom", "bluetape4k-exposed-bom"),
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

                includeProject("bluetape4k-exposed-bom", file("exposed/bluetape4k-exposed-bom"))
                includeModules(
                    "exposed",
                    withBaseDir = false,
                    prefix = "bluetape4k-",
                    excludeDirNames = setOf("bluetape4k-exposed-bom"),
                )
                includeMappedModule("spring-boot/exposed-jdbc", "bluetape4k-exposed-spring-boot-jdbc")

                fun includeModules(baseDir: String, withBaseDir: Boolean = true, prefix: String = "") {
                    // implementation omitted
                }
                fun includeProject(projectName: String, projectDir: File) {
                    include(projectName)
                    project(":$projectName").projectDir = projectDir
                }
                """,
                encoding="utf-8",
            )

            repo = next(managed_repo for managed_repo in sync.MANAGED_REPOS if managed_repo.label == "bluetape4k-exposed")
            modules = sync.discover_repo_modules(workspace_root, repo)

        discovered = {repo: [] for repo in sync.MANAGED_REPOS}
        discovered[repo] = modules
        aliases = {module.alias: module for module in modules}
        self.assertEqual(
            sorted(aliases),
            [
                "bluetape4k-exposed-bom",
                "bluetape4k-exposed-core",
                "bluetape4k-exposed-spring-boot-jdbc",
            ],
        )
        catalog = sync.render_catalog_section(discovered)
        constraints = sync.render_constraint_section(discovered)

        self.assertIn('bluetape4k-exposed-bom', catalog)
        self.assertIn('module = "io.github.bluetape4k.exposed:bluetape4k-exposed-spring-boot-jdbc"', catalog)
        self.assertIn("delegated to the sub-BOM platform imports", constraints)
        self.assertNotIn("api(libs.bluetape4k.exposed.core)", constraints)
        self.assertNotIn("api(libs.bluetape4k.exposed.spring.boot.jdbc)", constraints)
        self.assertNotIn("api(libs.bluetape4k.exposed.bom)", constraints)

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

    def test_include_module_excludes_examples_demos_and_benchmarks(self) -> None:
        repo = sync.ManagedRepo(
            label="sample",
            root_name="sample",
            group_id="io.github.bluetape4k.sample",
            version_ref="sample-bom",
            alias_mode="prefix",
            exclude_path_fragments=("examples", "benchmark"),
            exclude_name_suffixes=("-demo", "-examples", "-benchmark"),
        )

        self.assertFalse(sync.include_module(repo, "sample-demo", "spring/sample-demo"))
        self.assertFalse(sync.include_module(repo, "sample-examples", "examples/sample-examples"))
        self.assertFalse(sync.include_module(repo, "sample-benchmark", "benchmark/sample-benchmark"))
        self.assertTrue(sync.include_module(repo, "sample-core", "sample-core"))

    def test_projects_repo_excludes_non_published_mock_web_apps(self) -> None:
        repo = next(
            managed_repo
            for managed_repo in sync.MANAGED_REPOS
            if managed_repo.label == "bluetape4k-projects"
        )

        self.assertFalse(sync.include_module(repo, "bluetape4k-mock-web-server", "testing/mock-web-server"))
        self.assertFalse(
            sync.include_module(repo, "bluetape4k-mock-webflux-server", "testing/mock-webflux-server")
        )
        self.assertTrue(sync.include_module(repo, "bluetape4k-testcontainers", "testing/testcontainers"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-ktor-core", "ktor/core", "1.9.2"))
        self.assertTrue(sync.include_module(repo, "bluetape4k-ktor-core", "ktor/core", "1.10.0"))

    def test_projects_repo_excludes_unpublished_ktor_modules(self) -> None:
        repo = next(
            managed_repo
            for managed_repo in sync.MANAGED_REPOS
            if managed_repo.label == "bluetape4k-projects"
        )

        self.assertFalse(sync.include_module(repo, "bluetape4k-ktor-core", "io/ktor/ktor-core"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-ktor-observability", "io/ktor/ktor-observability"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-ktor-openapi", "io/ktor/ktor-openapi"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-ktor-resilience4j", "io/ktor/ktor-resilience4j"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-ktor-testing", "io/ktor/ktor-testing"))

    def test_image_repo_excludes_unpublished_captcha_and_ktor_modules(self) -> None:
        repo = next(
            managed_repo
            for managed_repo in sync.MANAGED_REPOS
            if managed_repo.label == "bluetape4k-image"
        )

        self.assertFalse(sync.include_module(repo, "bluetape4k-images-captcha", "images-captcha"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-images-ktor", "images-ktor"))
        self.assertTrue(sync.include_module(repo, "bluetape4k-images", "images"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-images-ktor", "images-ktor", "0.1.2"))
        self.assertTrue(sync.include_module(repo, "bluetape4k-images-ktor", "images-ktor", "0.2.0"))

    def test_javers_repo_gates_new_modules_by_selected_bom_version(self) -> None:
        repo = next(
            managed_repo
            for managed_repo in sync.MANAGED_REPOS
            if managed_repo.label == "bluetape4k-javers"
        )

        self.assertFalse(sync.include_module(repo, "javers-ddd", "javers-ddd", "0.1.2"))
        self.assertFalse(sync.include_module(repo, "javers-exposed", "javers-exposed", "0.1.2"))
        self.assertTrue(sync.include_module(repo, "javers-ddd", "javers-ddd", "0.2.0"))
        self.assertTrue(sync.include_module(repo, "javers-exposed", "javers-exposed", "0.2.0"))

    def test_exposed_repo_gates_unpublished_database_modules_by_selected_bom_version(self) -> None:
        repo = next(
            managed_repo
            for managed_repo in sync.MANAGED_REPOS
            if managed_repo.label == "bluetape4k-exposed"
        )

        self.assertFalse(
            sync.include_module(repo, "bluetape4k-exposed-cockroachdb", "exposed/exposed-cockroachdb", "1.11.0")
        )
        self.assertFalse(
            sync.include_module(repo, "bluetape4k-exposed-starrocks", "exposed/exposed-starrocks", "1.11.0")
        )
        self.assertTrue(
            sync.include_module(repo, "bluetape4k-exposed-cockroachdb", "exposed/exposed-cockroachdb", "1.12.0")
        )
        self.assertTrue(
            sync.include_module(repo, "bluetape4k-exposed-starrocks", "exposed/exposed-starrocks", "1.12.0")
        )

    def test_exposed_repo_excludes_unpublished_database_modules(self) -> None:
        repo = next(
            managed_repo
            for managed_repo in sync.MANAGED_REPOS
            if managed_repo.label == "bluetape4k-exposed"
        )

        self.assertFalse(sync.include_module(repo, "bluetape4k-exposed-cockroachdb", "exposed/cockroachdb"))
        self.assertFalse(sync.include_module(repo, "bluetape4k-exposed-starrocks", "exposed/starrocks"))
        self.assertTrue(sync.include_module(repo, "bluetape4k-exposed-core", "exposed/core"))

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
        )
        discovered = {managed_repo: [] for managed_repo in sync.MANAGED_REPOS}
        discovered[repo] = [module, module]

        with self.assertRaisesRegex(RuntimeError, "Duplicate catalog aliases"):
            sync.validate_discovered(discovered)


if __name__ == "__main__":
    unittest.main()
