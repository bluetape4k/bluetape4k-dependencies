from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
CHECKSUM = REPO_ROOT / "gradle" / "libs.versions.toml.sha256"


class CatalogChecksumTest(unittest.TestCase):
    def test_checked_in_checksum_matches_catalog(self) -> None:
        checksum_line = CHECKSUM.read_text(encoding="ascii").strip()
        match = re.fullmatch(r"([0-9a-f]{64})  libs\.versions\.toml", checksum_line)
        self.assertIsNotNone(match, "checksum must use portable sha256sum format")
        assert match is not None

        actual = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
        self.assertEqual(match.group(1), actual)


if __name__ == "__main__":
    unittest.main()
