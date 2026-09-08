from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_post_publish_next_development_line import (
    create_catalog_history,
    run_git,
)

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/checkout-catalog-publishers.sh"
MANIFEST = ROOT / "config/catalog-publisher-repository-refs.json"
SIGNING = ROOT / "config/publishing-signing-repository-refs.json"


class CatalogPublisherCheckoutTest(unittest.TestCase):
    def run_checkout(self, root: Path, document: dict) -> subprocess.CompletedProcess:
        manifest = root / "refs.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        # 전송만 로컬 fixture로 대체하고 clone/fetch/checkout은 실제 Git으로 검증한다.
        command = """
gh() {
  local destination="$4"
  shift 5
  git clone "$FIXTURE_SOURCE" "$destination" "$@"
}
export -f gh
bash "$1" "$2" "$3"
"""
        return subprocess.run(
            [
                "bash",
                "-c",
                command,
                "fixture",
                str(HELPER),
                str(root / "catalog"),
                str(manifest),
            ],
            env=dict(
                os.environ, PYTHON=sys.executable, FIXTURE_SOURCE=str(root / "signing")
            ),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def document(self, sha: str) -> dict:
        signing = json.loads(SIGNING.read_text(encoding="utf-8"))
        return {
            "schema-version": 1,
            "repositories": {name: {"commit": sha} for name in signing["repositories"]},
        }

    def test_immutable_catalog_checkout_preserves_signing_history_and_dirty_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "signing"
            refs = create_catalog_history(source)
            run_git(source, "checkout", "--detach", refs["minimum"])
            marker = source / "caller-owned.txt"
            marker.write_text("preserve", encoding="utf-8")
            result = self.run_checkout(root, self.document(refs["forward"]))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(run_git(source, "rev-parse", "HEAD"), refs["minimum"])
            self.assertEqual(marker.read_text(), "preserve")
            for name in self.document(refs["forward"])["repositories"]:
                checkout = root / "catalog" / name
                self.assertEqual(
                    run_git(checkout, "rev-parse", "HEAD"), refs["forward"]
                )
                self.assertEqual(run_git(checkout, "status", "--porcelain"), "")
            result = self.run_checkout(root, self.document(refs["minimum"]))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(
                run_git(root / "catalog/bluetape4k-exposed", "rev-parse", "HEAD"),
                refs["forward"],
            )

    def test_invalid_inventory_or_mutable_ref_fails_before_checkout(self) -> None:
        cases = [self.document("develop"), self.document("a" * 39)]
        missing = self.document("a" * 40)
        del missing["repositories"]["bluetape4k-exposed"]
        cases.append(missing)
        extra = self.document("a" * 40)
        extra["repositories"]["../escape"] = {"commit": "a" * 40}
        cases.append(extra)
        for document in cases:
            with (
                self.subTest(document=document),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                result = self.run_checkout(root, document)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "catalog").exists())

    def test_manifest_pins_all_publishers_separately_from_signing(self) -> None:
        catalog = json.loads(MANIFEST.read_text(encoding="utf-8"))
        signing = json.loads(SIGNING.read_text(encoding="utf-8"))
        self.assertEqual(set(catalog["repositories"]), set(signing["repositories"]))
        publishers = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/verify-publication-poms.py"),
                "--print-default-repositories",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        self.assertEqual(
            set(catalog["repositories"]),
            set(publishers.stdout.split()) - {"bluetape4k-dependencies"},
        )
        self.assertNotEqual(
            catalog["repositories"]["bluetape4k-exposed"],
            signing["repositories"]["bluetape4k-exposed"],
        )
        for value in catalog["repositories"].values():
            self.assertRegex(value["commit"], r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
