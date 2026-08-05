from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit-latest-stable.py"
LEDGER = REPO_ROOT / "config" / "central-catalog-version-deltas.json"
AUTHORITY_LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_latest_stable", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit-latest-stable.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CentralCatalogVersionDeltaLedgerTest(unittest.TestCase):
    def test_upsert_catalog_rollout_preserves_history(self) -> None:
        module = load_script()
        document = {
            "schema-version": 2,
            "rollout": "issue-168",
            "status": "pending-resolved-graph",
            "delta": [],
            "subsequent-rollouts": [{"rollout": "historical", "status": "verified"}],
        }
        authority = {
            "rollout": "current",
            "status": "validation-pending",
            "baseline": {"catalog-ref": "baseline"},
            "candidate": {"catalog-sha256": "candidate"},
            "audit": {"path": "config/latest-stable-version-audit.json"},
            "delta": [{"version-key": "example"}],
        }

        updated = module.upsert_catalog_rollout(document, authority)

        self.assertEqual(updated["subsequent-rollouts"][0]["rollout"], "historical")
        self.assertEqual(updated["subsequent-rollouts"][1]["rollout"], "current")
        self.assertEqual(updated["subsequent-rollouts"][1]["catalog-sha256"], "candidate")

    def test_ledger_preserves_issue_168_history_and_unique_rollouts(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))

        self.assertEqual(document["schema-version"], 2)
        self.assertEqual(document["rollout"], "2026-08-03-issue-168-central-catalog-authority")
        self.assertEqual(len(document["delta"]), 34)
        rollout_ids = [rollout["rollout"] for rollout in document["subsequent-rollouts"]]
        self.assertEqual(len(rollout_ids), len(set(rollout_ids)))
        self.assertIn("2026-08-04-issue-169-latest-compatible-stable", rollout_ids)
        self.assertIn("2026-08-05-issue-169-full-authority-audit", rollout_ids)

    def test_upsert_catalog_rollout_carries_verified_candidate_evidence(self) -> None:
        module = load_script()
        document = {
            "schema-version": 2,
            "rollout": "issue-168",
            "status": "pending-resolved-graph",
            "delta": [],
            "subsequent-rollouts": [],
        }
        authority = {
            "rollout": "current",
            "status": "verified-resolved-graph",
            "baseline": {"catalog-ref": "baseline"},
            "candidate": {"catalog-sha256": "candidate"},
            "audit": {"path": "config/latest-stable-version-audit.json"},
            "delta": [{"version-key": "example"}],
            "resolved-graph-evidence": {"path": "graphs.json", "spec-count": 1},
            "candidate-validation-evidence": {
                "downstream-full-builds": {"repositories": 9, "failures": 0},
                "publication-poms": {"repositories": 9, "failures": 0},
                "remote-immutable-ref-verification": "verified",
            },
        }

        rollout = module.upsert_catalog_rollout(document, authority)[
            "subsequent-rollouts"
        ][0]

        self.assertEqual(rollout["status"], "verified-resolved-graph")
        self.assertEqual(rollout["resolved-graph-evidence"]["spec-count"], 1)
        self.assertEqual(rollout["downstream-full-builds"]["failures"], 0)
        self.assertEqual(rollout["publication-pom-verification"]["failures"], 0)
        self.assertEqual(rollout["remote-immutable-ref-verification"], "verified")

    def test_full_authority_rollout_links_verified_evidence(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        authority = json.loads(AUTHORITY_LEDGER.read_text(encoding="utf-8"))
        rollout = next(
            item
            for item in document["subsequent-rollouts"]
            if item["rollout"] == "2026-08-05-issue-169-full-authority-audit"
        )

        self.assertEqual(rollout["status"], "verified-resolved-graph")
        self.assertEqual(
            rollout["authority-delta-ledger"],
            "config/latest-stable-version-deltas.json",
        )
        self.assertEqual(rollout["catalog-sha256"], authority["candidate"]["catalog-sha256"])
        self.assertEqual(rollout["baseline-catalog-ref"], authority["baseline"]["catalog-ref"])
        self.assertEqual(rollout["audit"], authority["audit"]["path"])
        self.assertEqual(rollout["delta-count"], 123)
        self.assertEqual(rollout["resolved-graph-evidence"]["spec-count"], 143)
        self.assertEqual(rollout["downstream-full-builds"]["failures"], 0)
        self.assertEqual(rollout["publication-pom-verification"]["failures"], 0)
        self.assertEqual(
            rollout["remote-immutable-ref-verification"],
            "verified-fresh-remote-commit-ref",
        )

    def test_compatibility_lines_are_not_issue_168_adoption_deltas(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))
        coordinates = {(delta["repository"], delta["coordinate"]) for delta in document["delta"]}

        self.assertTrue(
            coordinates.isdisjoint(
                {
                    ("bluetape4k-projects", "org.apache.kafka:kafka-clients"),
                    ("bluetape4k-projects", "org.apache.ignite:ignite-core"),
                    ("bluetape4k-projects", "org.springframework.kafka:spring-kafka"),
                    ("bluetape4k-leader", "org.springframework.boot:spring-boot-dependencies"),
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
