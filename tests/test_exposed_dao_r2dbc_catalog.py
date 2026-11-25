from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExposedDaoR2dbcCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = tomllib.loads(
            (ROOT / "gradle/libs.versions.toml").read_text(encoding="utf-8")
        )

    def test_exposed_dao_r2dbc_uses_existing_exposed_161_line(self) -> None:
        self.assertEqual(self.catalog["versions"]["exposed"], "1.6.1")
        libraries = self.catalog["libraries"]
        self.assertIn("exposed-dao-r2dbc", libraries)
        self.assertEqual(
            libraries["exposed-dao-r2dbc"],
            {
                "module": "org.jetbrains.exposed:exposed-dao-r2dbc",
                "version": {"ref": "exposed"},
            },
        )


if __name__ == "__main__":
    unittest.main()
