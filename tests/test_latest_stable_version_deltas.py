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
ISSUE_1832_ROLLOUT = "2026-10-18-issue-1832-amqp-client-catalog"
ISSUE_261_KOVER_ROLLOUT = "2026-10-24-pr-261-kover-only"
ISSUE_260_ROLLOUT = "2026-10-24-issue-260-safe-refresh"
CATALOG_REFRESH_ROLLOUT = "catalog-refresh-2026-10-30"


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
            next(
                rollout["rollout"]
                for rollout in central_document["subsequent-rollouts"]
                if rollout["rollout"] == document["rollout"]
            ),
        )
        status = document["status"]
        self.assertIn(status, {"validation-pending", "verified-resolved-graph"})
        if document["rollout"] == CATALOG_REFRESH_ROLLOUT:
            self.assertEqual(document["audit-cutoff"], "2026-10-30")
        elif document["rollout"] in {ISSUE_261_KOVER_ROLLOUT, ISSUE_260_ROLLOUT}:
            self.assertEqual(document["audit-cutoff"], "2026-10-24")
        elif status == "verified-resolved-graph" and document["rollout"] != ISSUE_1832_ROLLOUT:
            self.assertEqual(document["audit-cutoff"], "2026-09-04")
        else:
            self.assertEqual(document["audit-cutoff"], "2026-10-18")
        required_keys = {
                "schema-version",
                "rollout",
                "audit-cutoff",
                "status",
                "baseline",
                "candidate",
                "audit",
                "delta",
        }
        if status == "verified-resolved-graph":
            required_keys.add("resolved-graph-evidence")
        self.assertTrue(required_keys.issubset(document))
        self.assertTrue(
            set(document).issubset(required_keys | {"candidate-validation-evidence"})
        )
        if document["rollout"] == CATALOG_REFRESH_ROLLOUT:
            self.assertEqual(len(document["delta"]), 194)
            expected_versions = {
                "exposed": ("1.5.0", "1.6.0"),
                "hibernate": ("7.4.7.Final", "7.4.14.Final"),
                "hibernate-reactive-core": ("4.5.5.Final", "4.5.12.Final"),
                "jackson2": ("2.22.3", "2.22.4"),
                "ktor": ("3.6.0", "3.6.1"),
                "openfga": ("0.10.0", "0.10.1"),
                "qdrant": ("1.19.0", "1.20.0"),
                "temporal": ("1.38.0", "1.40.0"),
            }
            self.assertEqual(
                {
                    entry["version-key"]: (entry["before"], entry["after"])
                    for entry in document["delta"]
                    if entry["version-key"] in expected_versions
                },
                expected_versions,
            )
        elif document["rollout"] == ISSUE_261_KOVER_ROLLOUT:
            expected_deltas = {"kover"}
            self.assertEqual(
                {entry["version-key"] for entry in document["delta"]},
                expected_deltas,
            )
            self.assertEqual(len(document["delta"]), 1)
            candidate = document["delta"][0]
            self.assertEqual(candidate["before"], "0.9.9")
            self.assertEqual(candidate["after"], "0.9.11")
            self.assertEqual(
                candidate["authorities"][0]["coordinate-or-plugin-id"],
                "org.jetbrains.kotlinx.kover",
            )
            self.assertEqual(
                candidate["adoption-evidence"],
                {
                    "classification": "verified-latest-compatible",
                    "version": "0.9.11",
                },
            )
        elif document["rollout"] == ISSUE_260_ROLLOUT:
            expected_versions = {
                "spring-boot": ("4.1.1", "4.1.2"),
                "spring-boot4": ("4.1.1", "4.1.2"),
                "jackson3": ("3.2.3", "3.2.4"),
                "kafka4": ("4.2.1", "4.2.2"),
                "spring-kafka4": ("4.1.1", "4.1.2"),
                "ktor": ("3.5.2", "3.6.0"),
                "kotlin": ("2.4.20", "2.4.21"),
            }
            self.assertEqual(
                {
                    entry["version-key"]: (entry["before"], entry["after"])
                    for entry in document["delta"]
                },
                expected_versions,
            )
        elif status == "verified-resolved-graph" and document["rollout"] != ISSUE_1832_ROLLOUT:
            self.assertEqual(len(document["delta"]), 126)
        else:
            expected_deltas = {
                "managed-amqp-client-h639dbc3b57d0",
            }
            self.assertEqual(
                {entry["version-key"] for entry in document["delta"]},
                expected_deltas,
            )
            self.assertEqual(len(document["delta"]), 1)
            candidate = document["delta"][0]
            self.assertEqual(candidate["before"], "5.35.0")
            self.assertEqual(candidate["after"], "5.37.0")
            self.assertEqual(
                candidate["authorities"][0]["coordinate-or-plugin-id"],
                "com.rabbitmq:amqp-client",
            )
            self.assertEqual(
                candidate["adoption-evidence"],
                {
                    "classification": "verified-latest-compatible",
                    "version": "5.37.0",
                },
            )
        self.assertEqual(
            len({entry["version-key"] for entry in document["delta"]}),
            len(document["delta"]),
        )
        for entry in document["delta"]:
            expected_entry_keys = {
                "version-key",
                "before",
                "after",
                "authorities",
                "verification",
                "reason",
                "adoption-evidence",
            }
            if status == "verified-resolved-graph":
                expected_entry_keys.add("resolved-graph-specs")
            self.assertEqual(set(entry), expected_entry_keys)
            self.assertNotEqual(entry["before"], entry["after"])
            self.assertEqual(entry["after"], versions[entry["version-key"]])
            self.assertTrue(entry["authorities"])
            expected_verification = (
                "verified-resolved-graph"
                if status == "verified-resolved-graph"
                else "pending-resolved-graph"
            )
            self.assertEqual(entry["verification"], expected_verification)
            if status == "verified-resolved-graph":
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

        if status == "verified-resolved-graph":
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
        else:
            self.assertNotIn("resolved-graph-evidence", document)

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
            if document["rollout"] == ISSUE_261_KOVER_ROLLOUT:
                self.assertEqual(
                    candidate_receipt["full-builds"]["status"],
                    "completed-with-failures",
                )
                self.assertEqual(candidate_receipt["full-builds"]["failures"], 2)
            else:
                self.assertEqual(candidate_receipt["full-builds"]["status"], "pending")
            self.assertEqual(len(candidate_receipt["full-builds"]["repositories"]), 9)
            self.assertEqual(
                candidate_receipt["full-builds"]["assemble"]["failures"],
                2 if document["rollout"] == ISSUE_261_KOVER_ROLLOUT else 0,
            )
            self.assertEqual(candidate_receipt["publication-poms"]["failures"], 0)
            self.assertEqual(candidate_receipt["publication-poms"]["files"], 192)
            self.assertEqual(candidate_receipt["resolved-graphs"]["status"], "verified")
            graph_evidence = candidate_receipt["resolved-graphs"]["evidence"]
            self.assertEqual(graph_evidence["spec-count"], 1)
            graph_receipt_path = REPO_ROOT / graph_evidence["path"]
            graph_receipt_bytes = graph_receipt_path.read_bytes()
            self.assertEqual(
                hashlib.sha256(graph_receipt_bytes).hexdigest(),
                graph_evidence["sha256"],
            )
            self.assertEqual(
                graph_evidence["path"], document["resolved-graph-evidence"]["path"]
            )
            if document["rollout"] == ISSUE_261_KOVER_ROLLOUT:
                self.assertEqual(
                    candidate_receipt["full-builds"]["status"],
                    "completed-with-failures",
                )
                self.assertEqual(
                    candidate_receipt["full-builds"]["assemble"]["status"],
                    "pending",
                )
                self.assertEqual(candidate_receipt["full-builds"]["failures"], 2)
                self.assertEqual(
                    candidate_receipt["full-builds"]["verified-repositories"], 7
                )
                self.assertEqual(
                    candidate_receipt["full-builds"]["evidence"]["path"],
                    "docs/releases/2026-10-25-pr-261-kover-0911-downstream-full-builds.json",
                )
                full_build_evidence = candidate_receipt["full-builds"]["evidence"]
                full_build_evidence_path = REPO_ROOT / full_build_evidence["path"]
                full_build_evidence_bytes = full_build_evidence_path.read_bytes()
                full_build_evidence_document = json.loads(full_build_evidence_bytes)
                self.assertEqual(
                    hashlib.sha256(full_build_evidence_bytes).hexdigest(),
                    full_build_evidence["sha256"],
                )
                self.assertEqual(
                    full_build_evidence_document["baseline-comparison"]["status"],
                    "completed",
                )
                self.assertEqual(
                    full_build_evidence_document["governance-checks"][
                        "sync-shared-versions"
                    ]["gap-count"],
                    7,
                )
                self.assertEqual(
                    full_build_evidence_document["repositories"]["bluetape4k-exposed"][
                        "failure"
                    ]["classification"],
                    "reproduced-with-baseline",
                )
            else:
                projects_build = candidate_receipt["full-builds"]["projects-full-build"]
                self.assertEqual(projects_build["status"], "completed-with-failures")
                self.assertEqual(projects_build["failed-tasks"], 32)
                self.assertEqual(projects_build["testcontainers"]["failed"], 10)
                self.assertEqual(
                    projects_build["isolated-reruns"]["science"]["tests-failed"], 0
                )

    def test_rollout_audit_summary_matches_its_lifecycle(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        audit = document["audit"]
        current_audit = json.loads(AUDIT.read_text(encoding="utf-8"))

        self.assertEqual(document["audit"]["path"], "config/latest-stable-version-audit.json")
        if document["rollout"] in {ISSUE_261_KOVER_ROLLOUT, ISSUE_260_ROLLOUT}:
            self.assertEqual(document["audit-cutoff"], "2026-10-24")
            if document["candidate"]["catalog-sha256"] == current_audit["inputs"]["catalog"]["sha256"]:
                self.assertEqual(audit["summary"], current_audit["summary"])
        elif (
            document["status"] == "verified-resolved-graph"
            and document["rollout"] != ISSUE_1832_ROLLOUT
        ):
            # 완료된 rollout은 후속 audit의 최신 조회 결과로 덮어쓰지 않는다.
            self.assertNotIn("adopt-latest", audit["summary"]["line-dispositions"])
            self.assertEqual(audit["summary"]["authority-count"], 515)
            self.assertEqual(audit["summary"]["line-count"], 549)
            self.assertEqual(audit["summary"]["line-dispositions"]["current"], 440)
            self.assertEqual(audit["summary"]["metadata-verified"], 510)
        else:
            if document["rollout"] == ISSUE_1832_ROLLOUT:
                self.assertEqual(document["audit-cutoff"], "2026-10-18")
                self.assertEqual(audit["summary"], current_audit["summary"])
                self.assertEqual(audit["summary"]["authority-count"], 523)
                self.assertEqual(audit["summary"]["line-count"], 557)
                self.assertEqual(
                    audit["summary"]["line-dispositions"]["adopt-latest"], 196
                )
            else:
                self.assertEqual(document["status"], "validation-pending")
                # 후속 catalog rollout은 전역 audit을 갱신할 수 있으므로, 이미
                # 기록된 pending lifecycle snapshot을 현재 audit과 강제로 동일시하지 않는다.
                if (
                    document["candidate"]["catalog-sha256"]
                    == current_audit["inputs"]["catalog"]["sha256"]
                ):
                    self.assertEqual(audit["summary"], current_audit["summary"])

    def test_kotlin_candidate_is_stable_and_all_plugin_aliases_are_aligned(self) -> None:
        versions = catalog_versions()
        self.assertEqual(versions["kotlin"], "2.4.21")
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        kotlin_records = [
            record
            for record in audit["records"]
            if any(line["version-key"] == "kotlin" for line in record["current-lines"])
        ]
        self.assertEqual(
            {record["coordinate-or-plugin-id"] for record in kotlin_records},
            {
                "org.jetbrains.kotlin.jvm",
                "org.jetbrains.kotlin.kapt",
                "org.jetbrains.kotlin.plugin.allopen",
                "org.jetbrains.kotlin.plugin.jpa",
                "org.jetbrains.kotlin.plugin.noarg",
                "org.jetbrains.kotlin.plugin.serialization",
                "org.jetbrains.kotlin.plugin.spring",
            },
        )
        for record in kotlin_records:
            self.assertEqual(record["latest-stable"]["status"], "verified")
            for line in record["current-lines"]:
                self.assertEqual(line["current"], versions["kotlin"])
                self.assertEqual(line["disposition"], "current")

    def test_explicit_compatibility_and_unavailable_holds_remain(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        lines = {
            (record["coordinate-or-plugin-id"], line["version-key"]): line
            for record in audit["records"]
            for line in record["current-lines"]
        }

        kafka4_line = lines[("org.apache.kafka:kafka-clients", "kafka4")]
        self.assertEqual(kafka4_line["current"], "4.2.2")
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
            kafka4_line["disposition"],
            "hold-compatibility",
        )
        self.assertIn("Kafka 4.2.2", kafka4_line["disposition-reason"])
        self.assertIn("Spring Kafka 4.1.2", kafka4_line["disposition-reason"])
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
            "current",
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
