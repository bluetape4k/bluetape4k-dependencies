from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "gradle" / "libs.versions.toml"


class TenantCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog_text = CATALOG.read_text(encoding="utf-8")

    def test_tenant_artifacts_share_the_projects_bom_authority(self) -> None:
        artifacts = {
            "bluetape4k-tenant": "io.github.bluetape4k:bluetape4k-tenant",
            "bluetape4k-tenant-reactor": (
                "io.github.bluetape4k:bluetape4k-tenant-reactor"
            ),
            "bluetape4k-ktor-tenant": (
                "io.github.bluetape4k:bluetape4k-ktor-tenant"
            ),
        }

        for alias, module in artifacts.items():
            with self.subTest(alias=alias):
                entry = re.search(
                    rf"(?m)^{re.escape(alias)}\s*=\s*(\{{[^\n]+\}})",
                    self.catalog_text,
                )
                self.assertIsNotNone(entry, f"missing catalog alias: {alias}")
                assert entry is not None
                self.assertIn(f'module = "{module}"', entry.group(1))
                self.assertIn('version.ref = "bluetape4k-bom"', entry.group(1))

    def test_tenant_artifacts_do_not_duplicate_version_authority(self) -> None:
        versions_section = self.catalog_text.split("[libraries]", maxsplit=1)[0]

        self.assertNotRegex(
            versions_section,
            r"(?m)^\s*(?:bluetape4k-)?(?:ktor-)?tenant(?:-reactor)?\s*=",
        )


if __name__ == "__main__":
    unittest.main()
