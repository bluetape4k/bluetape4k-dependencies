from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit-latest-stable.py"
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
POLICY = REPO_ROOT / "config" / "central-catalog-authority-policy.json"
INVENTORY = REPO_ROOT / "config" / "latest-stable-version-inventory.json"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_latest_stable", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit-latest-stable.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LatestStableInventoryTest(unittest.TestCase):
    def test_cli_runs_with_the_active_python(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--summary"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("authority=396", result.stdout)

    def test_inventory_reconstructs_the_exact_authority_universe(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)

        self.assertEqual(inventory["schema-version"], 1)
        self.assertEqual(inventory["summary"]["authority-count"], 396)
        self.assertEqual(inventory["summary"]["managed-generated"], 325)
        self.assertEqual(inventory["summary"]["policy-subjects"], 71)
        self.assertEqual(inventory["summary"]["audit-pending"], 396)
        self.assertEqual(len(inventory["records"]), 396)
        self.assertEqual(
            len({record["authority-key"] for record in inventory["records"]}),
            396,
        )
        self.assertNotIn("bluetape4k-workshop", inventory["scope"]["repositories"])
        self.assertIn("bluetape4k-workshop", inventory["scope"]["excluded"])

    def test_committed_inventory_is_canonical_and_current(self) -> None:
        module = load_script()
        expected = module.canonical_json(module.build_inventory(CATALOG, POLICY))

        self.assertEqual(INVENTORY.read_bytes(), expected)

    def test_custom_inputs_record_their_actual_provenance_paths(self) -> None:
        module = load_script()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.toml"
            policy = root / "policy.json"
            shutil.copyfile(CATALOG, catalog)
            shutil.copyfile(POLICY, policy)

            inventory = module.build_inventory(catalog, policy)

        self.assertEqual(inventory["inputs"]["catalog"]["path"], str(catalog.resolve()))
        self.assertEqual(inventory["inputs"]["policy"]["path"], str(policy.resolve()))

    def test_check_rejects_stale_inventory(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)
        inventory["summary"]["authority-count"] = 395

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.json"
            output.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "inventory is stale"):
                module.check_inventory(output, CATALOG, POLICY)


if __name__ == "__main__":
    unittest.main()
