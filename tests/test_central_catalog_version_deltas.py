from __future__ import annotations

import json
import unittest
from pathlib import Path


LEDGER = Path(__file__).resolve().parents[1] / "config" / "central-catalog-version-deltas.json"


class CentralCatalogVersionDeltaLedgerTest(unittest.TestCase):
    def test_ledger_has_strict_schema_and_unique_coordinates(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))

        self.assertEqual(document["schema-version"], 1)
        self.assertEqual(document["rollout"], "2026-07-15-central-catalog-adoption")
        self.assertIn(document["status"], {"pending-resolved-graph", "verified"})
        self.assertEqual(set(document), {"schema-version", "rollout", "status", "delta"})

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
        identities: set[tuple[str, str]] = set()
        for delta in document["delta"]:
            self.assertEqual(set(delta), expected_fields)
            self.assertIn(delta["repository"], {"bluetape4k-projects", "bluetape4k-experimental"})
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

    def test_ledger_records_only_the_audited_adoption_deltas(self) -> None:
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
            ("bluetape4k-projects", "io.fabric8:kubernetes-client-bom", "7.7.0", "7.8.0"),
            ("bluetape4k-projects", "org.flywaydb:flyway-core", "11.20.3", "12.10.0"),
            ("bluetape4k-projects", "org.apache.tomcat:tomcat-jdbc", "11.0.18", "11.0.24"),
            ("bluetape4k-experimental", "com.gradleup.shadow", "9.4.2", "9.5.1"),
            ("bluetape4k-experimental", "io.netty:netty-bom", "4.2.15.Final", "4.2.16.Final"),
            ("bluetape4k-experimental", "org.apache.logging.log4j:log4j-bom", "2.26.0", "2.26.1"),
            ("bluetape4k-experimental", "com.zaxxer:HikariCP", "7.0.2", "7.1.0"),
            ("bluetape4k-experimental", "org.flywaydb:flyway-core", "12.6.0", "12.10.0"),
            (
                "bluetape4k-experimental",
                "io.github.bluetape4k:bluetape4k-dependencies",
                "1.4.0-SNAPSHOT",
                "1.3.1",
            ),
        }

        self.assertEqual(actual, expected)

    def test_compatibility_lines_are_not_misclassified_as_version_deltas(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        coordinates = {(delta["repository"], delta["coordinate"]) for delta in document["delta"]}

        preserved_compatibility_lines = {
            ("bluetape4k-projects", "org.apache.kafka:kafka-clients"),
            ("bluetape4k-projects", "org.apache.ignite:ignite-core"),
            ("bluetape4k-projects", "org.springframework.kafka:spring-kafka"),
            ("bluetape4k-experimental", "com.fasterxml.jackson:jackson-bom"),
            ("bluetape4k-experimental", "io.github.bluetape4k:bluetape4k-exposed-bom"),
            ("bluetape4k-aws", "tools.jackson:jackson-bom"),
            ("bluetape4k-leader", "org.springframework.boot:spring-boot-dependencies"),
        }

        self.assertTrue(coordinates.isdisjoint(preserved_compatibility_lines))


if __name__ == "__main__":
    unittest.main()
