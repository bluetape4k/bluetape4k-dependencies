from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit-latest-stable.py"
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"
AUDIT = REPO_ROOT / "config" / "latest-stable-version-audit.json"
BUILD = REPO_ROOT / "build.gradle.kts"
GRADLE_PROPERTIES = REPO_ROOT / "gradle.properties"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_latest_stable", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit-latest-stable.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def catalog_versions() -> dict[str, str]:
    section = CATALOG.read_text(encoding="utf-8").split("[versions]", 1)[1].split("\n[", 1)[0]
    return dict(
        re.findall(
            r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"',
            section,
            flags=re.MULTILINE,
        )
    )


class LatestStableVersionDeltaLedgerTest(unittest.TestCase):
    def test_build_delta_ledger_groups_changed_authorities_by_version_key(self) -> None:
        module = load_script()
        audit = {
            "inputs": {"inventory-sha256": "inventory"},
            "records": [
                {
                    "authority-key": "catalog:library:example:one",
                    "coordinate-or-plugin-id": "example:one",
                    "kind": "library",
                    "current-lines": [
                        {
                            "current": "1.1.0",
                            "version-key": "example",
                            "disposition": "current",
                        }
                    ],
                },
                {
                    "authority-key": "catalog:library:example:two",
                    "coordinate-or-plugin-id": "example:two",
                    "kind": "library",
                    "current-lines": [
                        {
                            "current": "1.1.0",
                            "version-key": "example",
                            "disposition": "current",
                        }
                    ],
                },
            ],
            "summary": {"line-dispositions": {"current": 2}},
        }

        ledger = module.build_delta_ledger(
            baseline_catalog='[versions]\nexample = "1.0.0"\n',
            candidate_catalog='[versions]\nexample = "1.1.0"\n',
            audit=audit,
            baseline_ref="baseline",
            audit_cutoff="2026-08-05",
            rollout="issue-169",
        )

        self.assertEqual(ledger["schema-version"], 2)
        self.assertEqual(len(ledger["delta"]), 1)
        self.assertEqual(ledger["delta"][0]["version-key"], "example")
        self.assertEqual(ledger["delta"][0]["before"], "1.0.0")
        self.assertEqual(ledger["delta"][0]["after"], "1.1.0")
        self.assertEqual(len(ledger["delta"][0]["authorities"]), 2)

    def test_ledger_has_strict_schema_and_exact_candidate_delta(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        versions = catalog_versions()

        self.assertEqual(document["schema-version"], 2)
        self.assertEqual(document["rollout"], "2026-08-05-issue-169-full-authority-audit")
        self.assertEqual(document["audit-cutoff"], "2026-08-05")
        self.assertEqual(document["status"], "validation-pending")
        self.assertEqual(
            set(document),
            {
                "schema-version",
                "rollout",
                "audit-cutoff",
                "status",
                "baseline",
                "candidate",
                "audit",
                "delta",
            },
        )
        self.assertEqual(len(document["delta"]), 122)
        self.assertEqual(
            len({entry["version-key"] for entry in document["delta"]}),
            len(document["delta"]),
        )
        for entry in document["delta"]:
            self.assertEqual(
                set(entry),
                {
                    "version-key",
                    "before",
                    "after",
                    "authorities",
                    "verification",
                    "reason",
                },
            )
            self.assertNotEqual(entry["before"], entry["after"])
            self.assertEqual(entry["after"], versions[entry["version-key"]])
            self.assertTrue(entry["authorities"])
            self.assertEqual(entry["verification"], "pending-resolved-graph")

    def test_audit_closes_all_safe_adoption_candidates(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))

        self.assertEqual(document["audit"]["path"], "config/latest-stable-version-audit.json")
        self.assertNotIn("adopt-latest", audit["summary"]["line-dispositions"])
        self.assertEqual(audit["summary"]["authority-count"], 510)
        self.assertEqual(audit["summary"]["line-count"], 544)
        self.assertEqual(audit["summary"]["metadata-verified"], 505)

    def test_explicit_compatibility_and_unavailable_holds_remain(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        lines = {
            (record["coordinate-or-plugin-id"], line["version-key"]): line
            for record in audit["records"]
            for line in record["current-lines"]
        }

        self.assertEqual(lines[("org.apache.kafka:kafka-clients", "kafka4")]["current"], "4.2.1")
        self.assertEqual(
            lines[("org.apache.kafka:kafka-clients", "kafka4")]["disposition"],
            "hold-compatibility",
        )
        self.assertEqual(
            lines[("org.apache.ignite:ignite-client", "ignite")]["disposition"],
            "hold-unavailable",
        )
        self.assertEqual(
            lines[("net.bytebuddy.byte-buddy-gradle-plugin", "byte-buddy")]["disposition"],
            "hold-compatibility",
        )
        self.assertEqual(
            lines[("org.jetbrains.kotlin.jvm", "kotlin")]["disposition"],
            "hold-compatibility",
        )

    def test_catalog_self_version_matches_the_release_version(self) -> None:
        properties = dict(
            line.split("=", 1)
            for line in GRADLE_PROPERTIES.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        expected = properties["baseVersion"] + properties["snapshotVersion"]
        self.assertIn(f'bluetape4k-dependencies = "{expected}"', CATALOG.read_text())

    def test_aws_crt_has_a_published_bom_constraint(self) -> None:
        self.assertIn("api(libs.aws2.aws.crt)", BUILD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
