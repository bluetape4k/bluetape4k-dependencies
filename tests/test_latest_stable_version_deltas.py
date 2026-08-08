from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit-latest-stable.py"
RESOLVER = REPO_ROOT / "scripts" / "verify-latest-stable-resolved-graphs.py"
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"
CENTRAL_LEDGER = REPO_ROOT / "config" / "central-catalog-version-deltas.json"
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


def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "verify_latest_stable_resolved_graphs", RESOLVER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load resolved graph verifier")
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
                    "latest-stable": {"status": "verified"},
                    "current-lines": [
                        {
                            "current": "1.1.0",
                            "version-key": "example",
                            "disposition": "current",
                            "disposition-reason": "Current latest compatible release.",
                            "latest-compatible": "1.1.0",
                        }
                    ],
                },
                {
                    "authority-key": "catalog:library:example:two",
                    "coordinate-or-plugin-id": "example:two",
                    "kind": "library",
                    "latest-stable": {"status": "verified"},
                    "current-lines": [
                        {
                            "current": "1.1.0",
                            "version-key": "example",
                            "disposition": "current",
                            "disposition-reason": "Current latest compatible release.",
                            "latest-compatible": "1.1.0",
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

        self.assertEqual(ledger["schema-version"], 3)
        self.assertEqual(len(ledger["delta"]), 1)
        self.assertEqual(ledger["delta"][0]["version-key"], "example")
        self.assertEqual(ledger["delta"][0]["before"], "1.0.0")
        self.assertEqual(ledger["delta"][0]["after"], "1.1.0")
        self.assertEqual(len(ledger["delta"][0]["authorities"]), 2)

    def test_build_delta_ledger_requires_verified_latest_compatible_evidence(self) -> None:
        module = load_script()
        audit = {
            "inputs": {"inventory-sha256": "inventory"},
            "records": [
                {
                    "authority-key": "catalog:library:example:one",
                    "coordinate-or-plugin-id": "example:one",
                    "kind": "library",
                    "latest-stable": {"status": "metadata-unavailable"},
                    "current-lines": [
                        {
                            "current": "1.1.0",
                            "version-key": "example",
                            "disposition": "hold-unavailable",
                            "disposition-reason": "Metadata unavailable.",
                            "latest-compatible": None,
                        }
                    ],
                }
            ],
            "summary": {"line-dispositions": {"hold-unavailable": 1}},
        }

        with self.assertRaisesRegex(RuntimeError, "verified latest-compatible"):
            module.build_delta_ledger(
                baseline_catalog='[versions]\nexample = "1.0.0"\n',
                candidate_catalog='[versions]\nexample = "1.1.0"\n',
                audit=audit,
                baseline_ref="baseline",
                audit_cutoff="2026-08-05",
                rollout="issue-169",
            )

    def test_build_delta_ledger_excludes_internal_bom_train_versions(self) -> None:
        module = load_script()
        audit = {
            "inputs": {"inventory-sha256": "inventory"},
            "records": [],
            "summary": {"line-dispositions": {}},
        }

        ledger = module.build_delta_ledger(
            baseline_catalog=(
                '[versions]\nbluetape4k-bom = "1.12.0-SNAPSHOT"\n'
                'bluetape4k-exposed-bom = "1.12.0-SNAPSHOT"\n'
            ),
            candidate_catalog=(
                '[versions]\nbluetape4k-bom = "1.12.1"\n'
                'bluetape4k-exposed-bom = "1.12.0"\n'
            ),
            audit=audit,
            baseline_ref="baseline",
            audit_cutoff="2026-08-05",
            rollout="issue-169",
        )

        self.assertEqual(ledger["delta"], [])
        self.assertEqual(ledger["status"], "validation-pending")

    def test_build_delta_ledger_records_verified_compatibility_alignment(self) -> None:
        module = load_script()
        audit = {
            "inputs": {"inventory-sha256": "inventory"},
            "records": [
                {
                    "authority-key": "catalog:library:example:one",
                    "coordinate-or-plugin-id": "example:one",
                    "kind": "library",
                    "latest-stable": {"status": "verified"},
                    "current-lines": [
                        {
                            "current": "1.5.34",
                            "version-key": "example",
                            "disposition": "hold-compatibility",
                            "disposition-reason": "Align the managed ABI pair.",
                            "latest-compatible": "1.6.1",
                        }
                    ],
                }
            ],
            "summary": {"line-dispositions": {"hold-compatibility": 1}},
        }

        ledger = module.build_delta_ledger(
            baseline_catalog='[versions]\nexample = "1.5.38"\n',
            candidate_catalog='[versions]\nexample = "1.5.34"\n',
            audit=audit,
            baseline_ref="baseline",
            audit_cutoff="2026-08-05",
            rollout="issue-169",
        )

        self.assertEqual(
            ledger["delta"][0]["adoption-evidence"]["classification"],
            "verified-compatibility-alignment",
        )
        self.assertIn("compatibility constraint", ledger["delta"][0]["reason"])

    def test_ledger_has_strict_schema_and_exact_candidate_delta(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        central_document = json.loads(CENTRAL_LEDGER.read_text(encoding="utf-8"))
        versions = catalog_versions()

        self.assertEqual(document["schema-version"], 3)
        self.assertEqual(
            document["rollout"],
            central_document["subsequent-rollouts"][-1]["rollout"],
        )
        self.assertEqual(document["audit-cutoff"], "2026-08-06")
        self.assertEqual(document["status"], "verified-resolved-graph")
        required_keys = {
                "schema-version",
                "rollout",
                "audit-cutoff",
                "status",
                "baseline",
                "candidate",
                "audit",
                "delta",
                "resolved-graph-evidence",
        }
        self.assertTrue(required_keys.issubset(document))
        self.assertTrue(
            set(document).issubset(required_keys | {"candidate-validation-evidence"})
        )
        self.assertEqual(len(document["delta"]), 123)
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
                    "adoption-evidence",
                    "resolved-graph-specs",
                },
            )
            self.assertNotEqual(entry["before"], entry["after"])
            self.assertEqual(entry["after"], versions[entry["version-key"]])
            self.assertTrue(entry["authorities"])
            self.assertEqual(entry["verification"], "verified-resolved-graph")
            self.assertTrue(entry["resolved-graph-specs"])
            self.assertTrue(
                all(
                    re.fullmatch(r"[0-9a-f]{64}", spec_id)
                    for spec_id in entry["resolved-graph-specs"]
                )
            )
            self.assertIn(
                entry["adoption-evidence"]["classification"],
                {
                    "verified-latest-compatible",
                    "verified-compatibility-alignment",
                },
            )
            self.assertEqual(entry["adoption-evidence"]["version"], entry["after"])

        evidence = document["resolved-graph-evidence"]
        receipt_path = REPO_ROOT / evidence["path"]
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        validated_receipt = load_resolver().validate_receipt(document, receipt)
        self.assertEqual(hashlib.sha256(receipt_bytes).hexdigest(), evidence["sha256"])
        self.assertEqual(receipt["status"], "verified-resolved-graph")
        self.assertEqual(receipt["catalog-sha256"], document["candidate"]["catalog-sha256"])
        self.assertEqual(receipt["spec-count"], evidence["spec-count"])
        self.assertEqual(receipt["observation-count"], evidence["observation-count"])
        self.assertEqual(len(receipt["observations"]), evidence["observation-count"])
        self.assertEqual(len(validated_receipt), evidence["observation-count"])
        self.assertEqual(
            {
                observation["spec_id"]
                for observation in receipt["observations"]
            },
            {
                spec_id
                for entry in document["delta"]
                for spec_id in entry["resolved-graph-specs"]
            },
        )

        candidate_evidence = document.get("candidate-validation-evidence")
        if candidate_evidence is not None:
            candidate_receipt_path = REPO_ROOT / candidate_evidence["path"]
            candidate_receipt_bytes = candidate_receipt_path.read_bytes()
            candidate_receipt = json.loads(candidate_receipt_bytes)
            self.assertEqual(
                hashlib.sha256(candidate_receipt_bytes).hexdigest(),
                candidate_evidence["sha256"],
            )
            self.assertEqual(candidate_receipt["status"], "verified-local-candidate")
            self.assertEqual(
                candidate_receipt["catalog"]["sha256"],
                document["candidate"]["catalog-sha256"],
            )
            self.assertEqual(candidate_receipt["full-builds"]["failures"], 0)
            self.assertEqual(len(candidate_receipt["full-builds"]["repositories"]), 9)
            self.assertEqual(candidate_receipt["publication-poms"]["failures"], 0)
            self.assertEqual(candidate_receipt["publication-poms"]["files"], 173)

    def test_audit_closes_all_safe_adoption_candidates(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))

        self.assertEqual(document["audit"]["path"], "config/latest-stable-version-audit.json")
        self.assertNotIn("adopt-latest", audit["summary"]["line-dispositions"])
        self.assertEqual(audit["summary"]["authority-count"], 514)
        self.assertEqual(audit["summary"]["line-count"], 548)
        self.assertEqual(audit["summary"]["line-dispositions"]["current"], 437)
        self.assertEqual(audit["summary"]["metadata-verified"], 509)

    def test_explicit_compatibility_and_unavailable_holds_remain(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        lines = {
            (record["coordinate-or-plugin-id"], line["version-key"]): line
            for record in audit["records"]
            for line in record["current-lines"]
        }

        self.assertEqual(lines[("org.apache.kafka:kafka-clients", "kafka4")]["current"], "4.2.1")
        self.assertEqual(lines[("ch.qos.logback:logback-classic", "logback")]["current"], "1.5.34")
        self.assertEqual(
            lines[("ch.qos.logback:logback-classic", "logback")]["disposition"],
            "hold-compatibility",
        )
        self.assertNotIn(
            ("org.lz4:lz4-java", "org-lz4"),
            lines,
        )
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
