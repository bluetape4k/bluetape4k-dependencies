from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
LESSON = REPO_ROOT / "docs" / "lessons" / "2026-10-27-issue-256-detekt-kotlin-compatibility.md"
MANIFEST = REPO_ROOT / "config" / "detekt-kotlin-compatibility-consumers.json"
SCRIPT = REPO_ROOT / "scripts" / "verify-detekt-kotlin-compatibility.py"

SPEC = importlib.util.spec_from_file_location("verify_detekt_kotlin_compatibility", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)


class DetektKotlinCompatibilityTest(unittest.TestCase):
    """Keep the Issue #256 catalog contract and its reproduction guard explicit."""

    def test_catalog_declares_detekt_boundary_and_resolver_rule(self) -> None:
        catalog = CATALOG.read_text(encoding="utf-8")

        self.assertIn('detekt-dev = "2.0.0-alpha.6"', catalog)
        self.assertIn("getSupportedKotlinVersion()", catalog)

    def test_lesson_contains_reproducible_guard_command(self) -> None:
        lesson = LESSON.read_text(encoding="utf-8")

        self.assertIn("PASS: central Detekt/Kotlin compatibility contract", lesson)
        self.assertIn("assert 'detekt-dev = \"2.0.0-alpha.6\"' in catalog", lesson)
        self.assertIn('assert "getSupportedKotlinVersion()" in catalog', lesson)
        self.assertIn("verify-detekt-kotlin-compatibility.py", lesson)
        self.assertIn("consumer_count=13", lesson)

    def test_manifest_has_disjoint_active_and_root_only_inventory(self) -> None:
        document, consumers = VERIFY.load_manifest(MANIFEST)

        self.assertEqual(document["plugin"]["supported_kotlin_compiler"], "2.4.10")
        self.assertEqual(len(consumers), 13)
        self.assertEqual(sum(not consumer.root_only for consumer in consumers), 10)
        self.assertEqual(sum(consumer.root_only for consumer in consumers), 3)
        self.assertEqual(
            {consumer.repository for consumer in consumers if consumer.root_only},
            {"bluetape4k-image", "bluetape4k-experimental", "exposed-r2dbc-workshop"},
        )

    def test_static_guard_requires_resolver_for_active_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "consumer"
            repository.mkdir()
            (repository / "settings.gradle.kts").write_text(
                'providers.environmentVariable("BLUETAPE4K_DEPENDENCIES_CATALOG_PATH")\n',
                encoding="utf-8",
            )
            build = repository / "build.gradle.kts"
            build.write_text(
                "alias(libs.plugins.detekt.dev)\n"
                "configurations.matching { it.name == \"detekt\" }.configureEach {\n"
                "    useVersion(getSupportedKotlinVersion())\n"
                "}\n",
                encoding="utf-8",
            )
            active = VERIFY.Consumer("consumer", "central", False, None)
            self.assertEqual(VERIFY.inspect_static(active, repository), [])
            build.write_text("alias(libs.plugins.detekt.dev)\n", encoding="utf-8")
            self.assertIn(
                "getSupportedKotlinVersion() resolver is missing from consumer build scripts",
                VERIFY.inspect_static(active, repository),
            )

    def test_static_guard_rejects_detekt_in_root_only_subproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "consumer"
            (repository / "module").mkdir(parents=True)
            (repository / "settings.gradle.kts").write_text("", encoding="utf-8")
            (repository / "build.gradle.kts").write_text(
                "alias(bt4k.plugins.detekt.dev)\n", encoding="utf-8"
            )
            (repository / "module" / "build.gradle.kts").write_text(
                "alias(libs.plugins.detekt.dev)\n", encoding="utf-8"
            )
            root_only = VERIFY.Consumer("consumer", "local", True, None)
            errors = VERIFY.inspect_static(root_only, repository)

        self.assertTrue(any("root-only consumer now applies Detekt" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
