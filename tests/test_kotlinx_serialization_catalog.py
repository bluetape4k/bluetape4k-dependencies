from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KotlinxSerializationCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog_text = (ROOT / "gradle/libs.versions.toml").read_text(encoding="utf-8")
        cls.build_text = (ROOT / "build.gradle.kts").read_text(encoding="utf-8")

    def test_catalog_exposes_versioned_bom_and_json_aliases(self) -> None:
        self.assertRegex(
            self.catalog_text,
            r'(?m)^kotlinx-serialization\s*=\s*"1\.11\.0"',
        )
        self.assert_catalog_alias(
            "kotlinx-serialization-bom",
            "org.jetbrains.kotlinx:kotlinx-serialization-bom",
        )
        self.assert_catalog_alias(
            "kotlinx-serialization-json",
            "org.jetbrains.kotlinx:kotlinx-serialization-json",
        )

    def test_platform_imports_the_serialization_bom(self) -> None:
        self.assertIn(
            "api(platform(libs.kotlinx.serialization.bom))",
            self.build_text,
        )

    def assert_catalog_alias(self, alias: str, module: str) -> None:
        match = re.search(
            rf"(?m)^{re.escape(alias)}\s*=\s*(\{{[^\n]+\}})",
            self.catalog_text,
        )
        self.assertIsNotNone(match, f"missing catalog alias: {alias}")
        entry = match.group(1)
        self.assertIn(f'module = "{module}"', entry)
        self.assertIn('version.ref = "kotlinx-serialization"', entry)


if __name__ == "__main__":
    unittest.main()
