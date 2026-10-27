from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
LESSON = REPO_ROOT / "docs" / "lessons" / "2026-10-27-issue-256-detekt-kotlin-compatibility.md"


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


if __name__ == "__main__":
    unittest.main()
