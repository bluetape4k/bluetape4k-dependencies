from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "config" / "central-catalog-version-deltas.json"
CATALOG = LEDGER.parents[1] / "gradle" / "libs.versions.toml"


class CentralCatalogVersionDeltaLedgerTest(unittest.TestCase):
    def test_ledger_has_strict_schema_and_unique_coordinates(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))

        self.assertEqual(document["schema-version"], 2)
        self.assertEqual(
            document["rollout"], "2026-08-03-issue-168-central-catalog-authority"
        )
        self.assertIn(document["status"], {"pending-resolved-graph", "verified"})
        self.assertEqual(
            set(document),
            {"schema-version", "rollout", "status", "subsequent-rollouts", "delta"},
        )

        expected_fields = {
            "repository",
            "kind",
            "coordinate",
            "before",
            "after",
            "classification",
            "verification",
            "reason",
        }
        repositories = {
            "bluetape4k-projects",
            "bluetape4k-aws",
            "bluetape4k-experimental",
            "bluetape4k-exposed",
            "bluetape4k-graph",
            "bluetape4k-image",
            "bluetape4k-javers",
            "bluetape4k-leader",
            "bluetape4k-text",
        }
        identities: set[tuple[str, str]] = set()
        for delta in document["delta"]:
            self.assertEqual(set(delta), expected_fields)
            self.assertIn(delta["repository"], repositories)
            self.assertIn(delta["kind"], {"library", "platform", "plugin"})
            self.assertIn(
                delta["classification"],
                {"central-adoption", "compatibility-bugfix", "released-bom-alignment"},
            )
            self.assertIn(delta["verification"], {"pending-resolved-graph", "verified"})
            self.assertNotEqual(delta["before"], delta["after"])
            self.assertTrue(delta["reason"].strip())
            identity = (delta["repository"], delta["coordinate"])
            self.assertNotIn(identity, identities)
            identities.add(identity)

    def test_issue_169_rollout_links_the_authority_ledger_and_local_evidence(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        rollout = document["subsequent-rollouts"][0]

        self.assertEqual(
            rollout["rollout"], "2026-08-04-issue-169-latest-compatible-stable"
        )
        self.assertEqual(rollout["status"], "partial-resolved-graph")
        self.assertEqual(
            rollout["authority-delta-ledger"],
            "config/latest-stable-version-deltas.json",
        )
        receipt = json.loads(
            (LEDGER.parents[1] / rollout["candidate-receipt"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(receipt["catalog"]["sha256"], rollout["catalog-sha256"])
        self.assertEqual(receipt["publication-poms"]["failures"], 0)
        self.assertEqual(
            rollout["catalog-sha256"],
            (
                LEDGER.parents[1] / "gradle" / "libs.versions.toml.sha256"
            ).read_text(encoding="utf-8").split()[0],
        )
        pom = rollout["publication-pom-verification"]
        self.assertEqual(pom["status"], "verified-local-candidate")
        self.assertEqual(pom["failures"], 0)
        self.assertEqual(pom["repositories"], 9)

        evidence = rollout["resolved-graph-evidence"]
        self.assertEqual(len(evidence), 10)
        self.assertEqual(
            len({entry["authority-key"] for entry in evidence}), len(evidence)
        )
        self.assertEqual(
            len({(entry["repository"], entry["coordinate"]) for entry in evidence}),
            len(evidence),
        )
        self.assertTrue(
            all(entry["verification"] == "verified-local-candidate" for entry in evidence)
        )
        authority_ledger = json.loads(
            (LEDGER.parents[1] / rollout["authority-delta-ledger"]).read_text(
                encoding="utf-8"
            )
        )
        authority_deltas = {
            entry["authority-key"]: entry for entry in authority_ledger["delta"]
        }
        catalog = CATALOG.read_text(encoding="utf-8")
        versions_section = catalog.split("[versions]", 1)[1].split("\n[", 1)[0]
        versions = dict(
            re.findall(
                r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"',
                versions_section,
                flags=re.MULTILINE,
            )
        )
        for entry in evidence:
            authority = authority_deltas[entry["authority-key"]]
            self.assertEqual(entry["authority-coordinate"], authority["coordinate"])
            self.assertEqual(entry["authority-before"], authority["before"])
            self.assertEqual(entry["after"], authority["after"])

            coordinate = entry["authority-coordinate"]
            group, name = coordinate.split(":", 1)
            candidate_lines = [
                line
                for line in catalog.splitlines()
                if f'module = "{coordinate}"' in line
                or (f'group = "{group}"' in line and f'name = "{name}"' in line)
            ]
            resolved_versions: set[str] = set()
            for line in candidate_lines:
                version_ref = re.search(r'version\.ref\s*=\s*"([^"]+)"', line)
                if version_ref:
                    resolved_versions.add(versions[version_ref.group(1)])
                    continue
                inline_version = re.search(r'version\s*=\s*"([^"]+)"', line)
                if inline_version:
                    resolved_versions.add(inline_version.group(1))
            self.assertIn(entry["after"], resolved_versions)
        self.assertEqual(
            rollout["remote-immutable-ref-verification"], "pending-central-push"
        )

    def test_ledger_records_only_issue_168_reviewed_adoption_deltas(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        actual = {
            (
                delta["repository"],
                delta["coordinate"],
                delta["before"],
                delta["after"],
            )
            for delta in document["delta"]
        }
        expected = {
            ("bluetape4k-aws", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
            ("bluetape4k-aws", "tools.jackson:jackson-bom", "3.1.3", "3.2.0"),
            ("bluetape4k-experimental", "at.yawk.lz4:lz4-java", "1.11.0", "1.11.1"),
            ("bluetape4k-experimental", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
            ("bluetape4k-experimental", "ch.qos.logback:logback-core", "1.5.32", "1.5.38"),
            ("bluetape4k-experimental", "com.fasterxml.jackson:jackson-bom", "2.22.0", "2.22.1"),
            ("bluetape4k-experimental", "jakarta.inject:jakarta.inject-api", "2.0.1.MR", "2.0.1"),
            ("bluetape4k-exposed", "com.falkordb:jfalkordb", "0.7.0", "0.8.0"),
            ("bluetape4k-exposed", "com.github.avro-kotlin.avro4k:avro4k-core", "2.10.0", "2.10.1"),
            ("bluetape4k-exposed", "io.zipkin.brave:brave", "6.3.0", "6.3.1"),
            ("bluetape4k-exposed", "io.zipkin.brave:brave-tests", "6.3.0", "6.3.1"),
            ("bluetape4k-exposed", "org.duckdb:duckdb_jdbc", "1.1.3", "1.5.2.1"),
            ("bluetape4k-exposed", "org.hibernate.reactive:hibernate-reactive-core", "4.3.3.Final", "4.5.0.Final"),
            ("bluetape4k-exposed", "org.owasp.dependencycheck", "12.1.9", "12.2.2"),
            ("bluetape4k-graph", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
            ("bluetape4k-graph", "ch.qos.logback:logback-core", "1.5.32", "1.5.38"),
            ("bluetape4k-graph", "org.apache.commons:commons-text", "1.13.1", "1.15.0"),
            ("bluetape4k-graph", "dev.detekt", "2.0.0-alpha.3", "2.0.0-alpha.5"),
            ("bluetape4k-image", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
            ("bluetape4k-javers", "at.yawk.lz4:lz4-java", "1.11.0", "1.11.1"),
            ("bluetape4k-javers", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
            ("bluetape4k-leader", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
            ("bluetape4k-projects", "ch.qos.logback:logback-classic", "1.5.37", "1.5.38"),
            ("bluetape4k-projects", "ch.qos.logback:logback-core", "1.5.37", "1.5.38"),
            ("bluetape4k-projects", "com.clickhouse:clickhouse-jdbc", "0.9.5", "0.9.8"),
            ("bluetape4k-projects", "io.gatling.highcharts:gatling-charts-highcharts", "3.15.0", "3.15.1"),
            ("bluetape4k-projects", "io.gatling:gatling-core-java", "3.15.0", "3.15.1"),
            ("bluetape4k-projects", "io.gatling:gatling-http-java", "3.15.0", "3.15.1"),
            ("bluetape4k-projects", "io.nats:jnats", "2.25.1", "2.25.3"),
            ("bluetape4k-projects", "io.trino:trino-jdbc", "475", "480"),
            ("bluetape4k-projects", "org.apache.commons:commons-rng-simple", "1.6", "1.7"),
            ("bluetape4k-projects", "org.elasticmq:elasticmq-rest-sqs_2.13", "1.6.12", "1.7.1"),
            ("bluetape4k-projects", "io.gatling.gradle", "3.15.0", "3.15.1"),
            ("bluetape4k-text", "ch.qos.logback:logback-classic", "1.5.32", "1.5.38"),
        }

        self.assertEqual(actual, expected)

    def test_compatibility_lines_are_not_misclassified_as_version_deltas(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        coordinates = {(delta["repository"], delta["coordinate"]) for delta in document["delta"]}

        preserved_compatibility_lines = {
            ("bluetape4k-projects", "org.apache.kafka:kafka-clients"),
            ("bluetape4k-projects", "org.apache.ignite:ignite-core"),
            ("bluetape4k-projects", "org.springframework.kafka:spring-kafka"),
            ("bluetape4k-experimental", "io.github.bluetape4k:bluetape4k-exposed-bom"),
            ("bluetape4k-leader", "org.springframework.boot:spring-boot-dependencies"),
        }

        self.assertTrue(coordinates.isdisjoint(preserved_compatibility_lines))


if __name__ == "__main__":
    unittest.main()
