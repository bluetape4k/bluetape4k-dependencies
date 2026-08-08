from __future__ import annotations

import copy
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
AUDIT = REPO_ROOT / "config" / "latest-stable-version-audit.json"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_latest_stable", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit-latest-stable.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LatestStableInventoryTest(unittest.TestCase):
    def test_utc_timestamp_is_supported_by_the_active_python(self) -> None:
        module = load_script()

        self.assertRegex(module.utc_timestamp(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_metadata_url_uses_maven_central_for_libraries(self) -> None:
        module = load_script()

        self.assertEqual(
            module.metadata_url("library", "com.rabbitmq:amqp-client"),
            "https://repo.maven.apache.org/maven2/com/rabbitmq/amqp-client/maven-metadata.xml",
        )

    def test_metadata_url_uses_plugin_marker_metadata_for_plugins(self) -> None:
        module = load_script()

        self.assertEqual(
            module.metadata_url("plugin", "org.owasp.dependencycheck"),
            "https://plugins.gradle.org/m2/org/owasp/dependencycheck/"
            "org.owasp.dependencycheck.gradle.plugin/maven-metadata.xml",
        )

    def test_metadata_url_uses_official_repository_override(self) -> None:
        module = load_script()

        self.assertEqual(
            module.metadata_url("library", "edu.ucar:cdm-core"),
            "https://artifacts.unidata.ucar.edu/repository/unidata-all/"
            "edu/ucar/cdm-core/maven-metadata.xml",
        )

    def test_parse_metadata_excludes_preview_versions(self) -> None:
        module = load_script()
        metadata = b"""<?xml version='1.0'?>
        <metadata><versioning><release>2.1.0-RC1</release><versions>
          <version>1.9.0</version><version>2.0.0.Final</version>
          <version>2.1.0-M1</version><version>2.1.0-RC1</version>
        </versions></versioning></metadata>
        """

        parsed = module.parse_metadata(metadata)

        self.assertEqual(parsed["latest-stable"], "2.0.0.Final")
        self.assertEqual(parsed["stable-versions"], ["1.9.0", "2.0.0.Final"])

    def test_stable_filter_rejects_abbreviated_preview_qualifiers(self) -> None:
        module = load_script()

        for version in (
            "3.2.0-B02",
            "31-RC",
            "1.0.0-rc-1",
            "2.4.10-RC",
            "4.0.0-M0",
            "3.2.0rc2",
            "1.0.0M1",
            "1.0.0ea1",
            "1.1.0-incubating",
            "2.0.0-dev-59",
            "0.0.1-test-1",
            "2.4.0-eap-1",
        ):
            with self.subTest(version=version):
                self.assertFalse(module.is_stable(version))

    def test_select_latest_compatible_preserves_major_line(self) -> None:
        module = load_script()

        self.assertEqual(
            module.select_latest_compatible(
                "4.1.136.Final",
                ["4.1.136.Final", "4.2.0.Final", "5.0.0.Alpha2"],
            ),
            "4.2.0.Final",
        )

    def test_select_latest_compatible_preserves_minor_for_zero_major(self) -> None:
        module = load_script()

        self.assertEqual(
            module.select_latest_compatible("0.48.2", ["0.48.2", "0.48.3", "0.49.0"]),
            "0.48.3",
        )

    def test_select_latest_compatible_normalizes_a_leading_v(self) -> None:
        module = load_script()

        self.assertEqual(
            module.select_latest_compatible("2.10.1", ["v2.4.1", "2.12.0"]),
            "2.12.0",
        )

    def test_select_latest_compatible_excludes_platform_variants(self) -> None:
        module = load_script()

        self.assertEqual(
            module.select_latest_compatible(
                "1.18.10", ["1.18.10", "1.18.11", "1.18.11-jdk5"]
            ),
            "1.18.11",
        )

    def test_classify_line_defers_a_breaking_major_upgrade(self) -> None:
        module = load_script()

        disposition = module.classify_line(
            current="12.2.2",
            latest_stable="13.0.0",
            latest_compatible="12.2.2",
            governance_disposition="central-direct",
        )

        self.assertEqual(disposition, "defer-breaking-migration")

    def test_classify_line_adopts_latest_within_compatibility_lane(self) -> None:
        module = load_script()

        disposition = module.classify_line(
            current="1.6.16",
            latest_stable="1.6.20",
            latest_compatible="1.6.20",
            governance_disposition="central-direct",
        )

        self.assertEqual(disposition, "adopt-latest")

    def test_classify_line_never_adopts_a_downgrade(self) -> None:
        module = load_script()

        disposition = module.classify_line(
            current="8.18.0",
            latest_stable="8.14.0",
            latest_compatible="8.14.0",
            governance_disposition="central-direct",
        )

        self.assertEqual(disposition, "hold-compatibility")

    def test_classify_line_holds_an_alternate_platform_release_channel(self) -> None:
        module = load_script()

        disposition = module.classify_line(
            current="1.18.11",
            latest_stable="1.18.11-jdk5",
            latest_compatible="1.18.11",
            governance_disposition="central-direct",
        )

        self.assertEqual(disposition, "hold-compatibility")

    def test_classify_line_holds_when_upstream_release_order_regresses(self) -> None:
        module = load_script()

        disposition = module.classify_line(
            current="1.9.25.1",
            latest_stable="1.9.25",
            latest_compatible="1.9.25.1",
            governance_disposition="central-direct",
        )

        self.assertEqual(disposition, "hold-compatibility")

    def test_audit_record_captures_metadata_and_line_disposition(self) -> None:
        module = load_script()
        record = {
            "authority-key": "managed:managed-example",
            "coordinate-or-plugin-id": "example:library",
            "kind": "library",
            "current-lines": [
                {
                    "current": "1.2.0",
                    "governance-disposition": "central-direct",
                    "line-id": "default",
                    "version-key": "managed-example",
                }
            ],
        }
        metadata = b"""<metadata><versioning><release>1.3.0</release><versions>
          <version>1.2.0</version><version>1.3.0</version><version>2.0.0-RC1</version>
        </versions></versioning></metadata>"""

        audited = module.audit_record(
            record,
            fetch=lambda _: metadata,
            retrieved_at="2026-08-05T00:00:00Z",
        )

        self.assertEqual(audited["latest-stable"]["latest"], "1.3.0")
        self.assertEqual(audited["latest-stable"]["status"], "verified")
        self.assertEqual(audited["current-lines"][0]["latest-compatible"], "1.3.0")
        self.assertEqual(audited["current-lines"][0]["disposition"], "adopt-latest")
        self.assertTrue(audited["current-lines"][0]["disposition-reason"])
        self.assertEqual(
            audited["latest-stable"]["metadata-sha256"],
            module.hashlib.sha256(metadata).hexdigest(),
        )

    def test_audit_record_applies_an_explicit_line_override(self) -> None:
        module = load_script()
        record = {
            "authority-key": "policy:library:io.netty:netty-buffer",
            "coordinate-or-plugin-id": "io.netty:netty-buffer",
            "kind": "library",
            "current-lines": [
                {
                    "current": "4.1.136.Final",
                    "governance-disposition": "compatibility-line",
                    "line-id": "netty-4",
                    "version-key": "netty4",
                }
            ],
        }
        metadata = b"""<metadata><versioning><release>4.2.17.Final</release><versions>
          <version>4.1.136.Final</version><version>4.2.17.Final</version>
        </versions></versioning></metadata>"""

        audited = module.audit_record(
            record,
            fetch=lambda _: metadata,
            retrieved_at="2026-08-05T00:00:00Z",
            line_overrides={
                "netty4": {
                    "disposition": "hold-compatibility",
                    "reason": "Preserve the Netty 4.1 ABI line.",
                }
            },
        )

        self.assertEqual(audited["current-lines"][0]["disposition"], "hold-compatibility")
        self.assertEqual(
            audited["current-lines"][0]["disposition-reason"],
            "Preserve the Netty 4.1 ABI line.",
        )

    def test_audit_record_applies_an_authority_specific_line_override(self) -> None:
        module = load_script()
        record = {
            "authority-key": "catalog:library:org.apache.ignite:ignite-client",
            "coordinate-or-plugin-id": "org.apache.ignite:ignite-client",
            "kind": "library",
            "current-lines": [
                {
                    "current": "2.18.0",
                    "governance-disposition": "compatibility-line",
                    "line-id": "ignite-2",
                    "version-key": "ignite",
                }
            ],
        }
        metadata = b"""<metadata><versioning><release>3.1.0</release><versions>
          <version>3.0.0</version><version>3.1.0</version>
        </versions></versioning></metadata>"""

        audited = module.audit_record(
            record,
            fetch=lambda _: metadata,
            retrieved_at="2026-08-05T00:00:00Z",
            authority_line_overrides={
                "catalog:library:org.apache.ignite:ignite-client": {
                    "ignite": {
                        "disposition": "hold-unavailable",
                        "reason": "The declared Ignite 2 client coordinate is unavailable.",
                    }
                }
            },
        )

        self.assertEqual(audited["current-lines"][0]["disposition"], "hold-unavailable")
        self.assertEqual(
            audited["current-lines"][0]["disposition-reason"],
            "The declared Ignite 2 client coordinate is unavailable.",
        )

    def test_audit_record_preserves_preview_release_when_using_stable_fallback(self) -> None:
        module = load_script()
        record = {
            "authority-key": "catalog:library:example:library",
            "coordinate-or-plugin-id": "example:library",
            "kind": "library",
            "current-lines": [
                {
                    "current": "1.9.0",
                    "governance-disposition": "central-direct",
                    "line-id": "default",
                    "version-key": "example",
                }
            ],
        }
        metadata = b"""<metadata><versioning><release>2.0.0-RC1</release><versions>
          <version>1.9.0</version><version>2.0.0-RC1</version>
        </versions></versioning></metadata>"""

        audited = module.audit_record(
            record,
            fetch=lambda _: metadata,
            retrieved_at="2026-08-05T00:00:00Z",
        )

        self.assertEqual(audited["latest-stable"]["latest"], "1.9.0")
        self.assertEqual(audited["latest-stable"]["upstream-release"], "2.0.0-RC1")
        self.assertEqual(audited["latest-stable"]["release-status"], "preview-fallback")

    def test_audit_record_fails_closed_when_metadata_is_unavailable(self) -> None:
        module = load_script()
        record = {
            "authority-key": "managed:managed-missing",
            "coordinate-or-plugin-id": "example:missing",
            "kind": "library",
            "current-lines": [
                {
                    "current": "1.0.0",
                    "governance-disposition": "central-direct",
                    "line-id": "default",
                    "version-key": "managed-missing",
                }
            ],
        }

        def unavailable(_: str) -> bytes:
            raise OSError("not found")

        audited = module.audit_record(
            record,
            fetch=unavailable,
            retrieved_at="2026-08-05T00:00:00Z",
        )

        self.assertEqual(audited["latest-stable"]["status"], "metadata-unavailable")
        self.assertEqual(audited["current-lines"][0]["disposition"], "hold-unavailable")

    def test_audit_record_distinguishes_preview_only_metadata(self) -> None:
        module = load_script()
        record = {
            "authority-key": "managed:preview",
            "coordinate-or-plugin-id": "example:preview",
            "kind": "library",
            "current-lines": [
                {
                    "current": "2.0.0-alpha.5",
                    "governance-disposition": "central-direct",
                    "line-id": "default",
                    "version-key": "preview",
                }
            ],
        }
        metadata = b"""<metadata><versioning><release>2.0.0-alpha.6</release><versions>
          <version>2.0.0-alpha.5</version><version>2.0.0-alpha.6</version>
        </versions></versioning></metadata>"""

        audited = module.audit_record(
            record,
            fetch=lambda _: metadata,
            retrieved_at="2026-08-05T00:00:00Z",
        )

        self.assertEqual(audited["latest-stable"]["status"], "preview-only")
        self.assertEqual(audited["latest-stable"]["upstream-release"], "2.0.0-alpha.6")
        self.assertEqual(audited["current-lines"][0]["disposition"], "hold-unavailable")

    def test_build_audit_summarizes_every_authority_and_line(self) -> None:
        module = load_script()
        inventory = {
            "inputs": {"catalog": {"sha256": "catalog"}, "policy": {"sha256": "policy"}},
            "records": [
                {
                    "authority-key": "managed:one",
                    "coordinate-or-plugin-id": "example:one",
                    "kind": "library",
                    "current-lines": [
                        {
                            "current": "1.0.0",
                            "governance-disposition": "central-direct",
                            "line-id": "default",
                            "version-key": "one",
                        }
                    ],
                },
                {
                    "authority-key": "managed:missing",
                    "coordinate-or-plugin-id": "example:missing",
                    "kind": "library",
                    "current-lines": [
                        {
                            "current": "1.0.0",
                            "governance-disposition": "central-direct",
                            "line-id": "default",
                            "version-key": "missing",
                        }
                    ],
                },
            ],
            "schema-version": 1,
            "scope": {"repositories": ["one"], "excluded": []},
        }
        metadata = b"""<metadata><versioning><release>1.0.0</release><versions>
          <version>1.0.0</version>
        </versions></versioning></metadata>"""

        def fetch(url: str) -> bytes:
            if url.endswith("/missing/maven-metadata.xml"):
                raise OSError("missing")
            return metadata

        audit = module.build_audit(
            inventory,
            fetch=fetch,
            retrieved_at="2026-08-05T00:00:00Z",
            audit_policy={
                "authority-line-overrides": {},
                "line-overrides": {},
                "schema-version": 2,
            },
        )

        self.assertEqual(audit["schema-version"], 1)
        self.assertEqual(audit["summary"]["authority-count"], 2)
        self.assertEqual(audit["summary"]["metadata-verified"], 1)
        self.assertEqual(audit["summary"]["metadata-unavailable"], 1)
        self.assertEqual(audit["summary"]["line-dispositions"]["current"], 1)
        self.assertEqual(audit["summary"]["line-dispositions"]["hold-unavailable"], 1)
        self.assertIn("audit-policy-sha256", audit["inputs"])

    def test_sync_policy_versions_reads_current_values_from_catalog(self) -> None:
        module = load_script()
        policy = {
            "schema-version": 1,
            "subjects": [
                {
                    "coordinate-or-plugin-id": "example:library",
                    "subject-kind": "library",
                    "lines": [
                        {
                            "version": "1.0.0",
                            "version-key": "example",
                        }
                    ],
                }
            ],
        }

        synced = module.sync_policy_versions(policy, '[versions]\nexample = "1.1.0"\n')

        self.assertEqual(synced["subjects"][0]["lines"][0]["version"], "1.1.0")
        self.assertEqual(policy["subjects"][0]["lines"][0]["version"], "1.0.0")

    def test_validate_audit_rejects_a_different_inventory(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)
        audit = {
            "inputs": {"inventory-sha256": "stale"},
            "records": [],
            "summary": {"authority-count": 0, "metadata-verified": 0},
        }

        with self.assertRaisesRegex(RuntimeError, "inventory SHA"):
            module.validate_audit(audit, inventory)

    def test_validate_audit_rejects_tampered_record_identity_and_summary(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))

        tampered_identity = copy.deepcopy(audit)
        tampered_identity["records"][0]["coordinate-or-plugin-id"] = "evil:coordinate"
        with self.assertRaisesRegex(RuntimeError, "identity"):
            module.validate_audit(tampered_identity, inventory)

        tampered_summary = copy.deepcopy(audit)
        tampered_summary["summary"]["metadata-verified"] -= 1
        with self.assertRaisesRegex(RuntimeError, "summary"):
            module.validate_audit(tampered_summary, inventory)

    def test_validate_audit_rejects_incoherent_unavailable_metadata(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        record = audit["records"][0]
        record["latest-stable"] = {
            "latest": None,
            "metadata-sha256": None,
            "reason": "tampered",
            "retrieved-at": audit["retrieved-at"],
            "source": module.metadata_url(
                record["kind"], record["coordinate-or-plugin-id"]
            ),
            "status": "metadata-unavailable",
        }
        for line in record["current-lines"]:
            line["disposition"] = "hold-unavailable"
            line["disposition-reason"] = module.disposition_reason("hold-unavailable")
            line["latest-compatible"] = None

        with self.assertRaisesRegex(RuntimeError, "summary"):
            module.validate_audit(audit, inventory)

    def test_validate_audit_rejects_a_coherent_all_unavailable_snapshot(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        for record in audit["records"]:
            record["latest-stable"] = {
                "latest": None,
                "metadata-sha256": None,
                "reason": "The authoritative metadata source was unavailable.",
                "retrieved-at": audit["retrieved-at"],
                "source": module.metadata_url(
                    record["kind"], record["coordinate-or-plugin-id"]
                ),
                "status": "metadata-unavailable",
            }
            for line in record["current-lines"]:
                line["disposition"] = "hold-unavailable"
                line["disposition-reason"] = module.disposition_reason(
                    "hold-unavailable"
                )
                line["latest-compatible"] = None
        audit["summary"] = {
            "authority-count": len(audit["records"]),
            "line-count": sum(
                len(record["current-lines"]) for record in audit["records"]
            ),
            "line-dispositions": {
                "hold-unavailable": sum(
                    len(record["current-lines"]) for record in audit["records"]
                )
            },
            "metadata-preview-only": 0,
            "metadata-unavailable": len(audit["records"]),
            "metadata-verified": 0,
        }

        with self.assertRaisesRegex(RuntimeError, "unavailable upstream metadata"):
            module.validate_audit(audit, inventory)

    def test_cli_runs_with_the_active_python(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--summary"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("authority=514", result.stdout)

    def test_inventory_reconstructs_the_exact_authority_universe(self) -> None:
        module = load_script()
        inventory = module.build_inventory(CATALOG, POLICY)

        self.assertEqual(inventory["schema-version"], 1)
        self.assertEqual(inventory["summary"]["authority-count"], 514)
        self.assertEqual(inventory["summary"]["catalog-direct"], 119)
        self.assertEqual(inventory["summary"]["managed-generated"], 325)
        self.assertEqual(inventory["summary"]["policy-subjects"], 70)
        self.assertEqual(inventory["summary"]["audit-pending"], 514)
        self.assertEqual(len(inventory["records"]), 514)
        self.assertEqual(
            len({record["authority-key"] for record in inventory["records"]}),
            514,
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
