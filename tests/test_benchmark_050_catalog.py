from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Benchmark050CatalogTest(unittest.TestCase):
    def test_plugin_and_runtime_aliases_share_the_approved_release(self) -> None:
        catalog = tomllib.loads((ROOT / "gradle/libs.versions.toml").read_text())
        declarations = [catalog["plugins"]["kotlinx-benchmark"]]
        declarations.extend(
            catalog["libraries"][alias]
            for alias in (
                "kotlinx-benchmark-runtime",
                "kotlinx-benchmark-runtime-jvm",
                "kotlinx-benchmark-runtimejvm",
            )
        )
        self.assertEqual(declarations[0]["id"], "org.jetbrains.kotlinx.benchmark")
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                self.assertEqual(
                    catalog["versions"][declaration["version"]["ref"]], "0.5.0"
                )

    def test_benchmark_delta_does_not_repeat_the_kotlin_compiler_upgrade(self) -> None:
        ledger = json.loads(
            (ROOT / "config/kotlinx-benchmark-0.5.0-version-deltas.json").read_text()
        )
        self.assertEqual(len(ledger["delta"]), 3)
        for delta in ledger["delta"]:
            with self.subTest(version_key=delta["version-key"]):
                self.assertTrue(delta["version-key"].startswith("managed-kotlinx-benchmark"))
                self.assertEqual((delta["before"], delta["after"]), ("0.4.19", "0.5.0"))
        central = json.loads((ROOT / "config/central-catalog-version-deltas.json").read_text())
        rollout = next(
            item for item in central["subsequent-rollouts"]
            if item["rollout"] == ledger["rollout"]
        )
        self.assertEqual(
            rollout["authority-delta-ledger"],
            "config/kotlinx-benchmark-0.5.0-version-deltas.json",
        )


if __name__ == "__main__":
    unittest.main()
