from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"
BUILD = REPO_ROOT / "build.gradle.kts"
GRADLE_PROPERTIES = REPO_ROOT / "gradle.properties"


class LatestStableVersionDeltaLedgerTest(unittest.TestCase):
    def test_catalog_self_version_matches_the_release_version(self) -> None:
        properties = dict(
            line.split("=", 1)
            for line in GRADLE_PROPERTIES.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        expected = properties["baseVersion"] + properties["snapshotVersion"]
        self.assertIn(
            f'bluetape4k-dependencies = "{expected}"',
            CATALOG.read_text(encoding="utf-8"),
        )

    def test_ledger_has_strict_schema_and_unique_authority_keys(self) -> None:
        document = json.loads(LEDGER.read_text(encoding="utf-8"))

        self.assertEqual(document["schema-version"], 1)
        self.assertEqual(
            document["rollout"], "2026-08-04-issue-169-latest-compatible-stable"
        )
        self.assertEqual(document["audit-cutoff"], "2026-08-04")
        self.assertIn(
            document["status"],
            {"validation-pending", "partial-validation", "verified"},
        )
        self.assertEqual(
            set(document),
            {
                "schema-version",
                "rollout",
                "audit-cutoff",
                "status",
                "delta",
                "hold",
            },
        )

        authority_keys: set[str] = set()
        for delta in document["delta"]:
            self.assertEqual(
                set(delta),
                {
                    "authority-key",
                    "kind",
                    "coordinate",
                    "before",
                    "after",
                    "disposition",
                    "verification",
                    "source",
                    "reason",
                },
            )
            self.assertIn(
                delta["kind"],
                {
                    "plugin",
                    "plugin-family",
                    "library",
                    "library-family",
                    "platform",
                    "compatibility-family",
                },
            )
            self.assertIn(
                delta["disposition"],
                {"adopt-latest", "adopt-compatible-parent-version"},
            )
            self.assertIn(delta["verification"], {"pending", "verified"})
            self.assertNotEqual(delta["before"], delta["after"])
            self.assertTrue(delta["source"].startswith("https://"))
            self.assertNotIn(delta["authority-key"], authority_keys)
            authority_keys.add(delta["authority-key"])

        for hold in document["hold"]:
            self.assertEqual(
                set(hold),
                {
                    "authority-key",
                    "kind",
                    "coordinate",
                    "current",
                    "latest",
                    "disposition",
                    "source",
                    "reason",
                },
            )
            self.assertIn(
                hold["disposition"],
                {"hold-compatibility", "hold-unavailable", "defer-breaking-migration"},
            )
            self.assertNotIn(hold["authority-key"], authority_keys)
            authority_keys.add(hold["authority-key"])

    def test_plugin_batch_matches_the_candidate_catalog(self) -> None:
        catalog = CATALOG.read_text(encoding="utf-8")

        self.assertIn('gatling-plugin    = "3.15.1.2"', catalog)
        self.assertIn('gatling           = "3.15.1"', catalog)
        self.assertIn('version.ref = "gatling-plugin"', catalog)
        self.assertIn('kotlin             = "2.4.0"', catalog)
        self.assertIn('kover             = "0.9.9"', catalog)
        self.assertIn('download = "5.7.0"', catalog)
        self.assertIn('jib = "3.5.4"', catalog)
        self.assertIn('shadow            = "9.6.1"', catalog)
        self.assertIn('jackson3          = "3.2.1"', catalog)
        self.assertIn('aws-kotlin        = "1.8.22"', catalog)
        self.assertIn('aws2              = "2.50.3"', catalog)
        self.assertIn('aws2-crt          = "0.48.2"', catalog)
        for smithy_key in (
            "managed-aws-smithy-kotlin-http-client-engine-crt-h0fe03f75a467",
            "managed-aws-smithy-kotlin-http-client-engine-default-h007ac9aa53c5",
            "managed-aws-smithy-kotlin-http-client-engine-okhttp-hfedd9fc31604",
            "managed-aws-smithy-kotlin-http-hea8fa947b4d3",
            "managed-aws-smithy-kotlin-serde-hb6c6080166ba",
            "managed-aws-smithy-kotlin-serde-json-h39078dce8d4a",
        ):
            self.assertIn(f'{smithy_key} = "1.7.4"', catalog)
        self.assertIn(
            'aws2-aws-crt = { module = "software.amazon.awssdk.crt:aws-crt", version.ref = "aws2-crt" }',
            catalog,
        )
        self.assertIn('ktor              = "3.5.2"', catalog)
        self.assertIn('netty4            = "4.1.136.Final"', catalog)
        self.assertIn(
            'managed-netty-tcnative-classes-h39fc93b48f6f = "2.0.78.Final"',
            catalog,
        )
        self.assertIn('opentelemetry     = "1.64.0"', catalog)
        self.assertIn('vertx4            = "4.5.31"', catalog)
        self.assertIn('vertx             = "5.1.5"', catalog)
        self.assertIn('classgraph        = "4.8.186"', catalog)
        self.assertIn('httpclient5       = "5.6.3"', catalog)
        self.assertIn('hibernate         = "7.4.5.Final"', catalog)
        self.assertIn('zstd              = "1.5.7-12"', catalog)
        self.assertIn('zstd-jni          = "1.5.7-12"', catalog)
        self.assertIn('scrimage          = "4.6.7"', catalog)
        self.assertIn('commons-codec     = "1.22.1"', catalog)
        self.assertIn('dependency-check = "12.2.2"', catalog)

    def test_aws_crt_has_a_published_bom_constraint(self) -> None:
        build = BUILD.read_text(encoding="utf-8")

        self.assertIn("api(libs.aws2.aws.crt)", build)

    def test_selected_family_ledger_matches_the_candidate(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        adopted = {entry["authority-key"]: entry["after"] for entry in ledger["delta"]}

        self.assertEqual(adopted["aws2"], "2.50.3")
        self.assertEqual(adopted["aws2-crt"], "0.48.2")
        self.assertEqual(adopted["aws-smithy-kotlin"], "1.7.4")
        self.assertEqual(adopted["grpc-java"], "1.83.1")
        self.assertEqual(adopted["mongodb-driver"], "5.9.1")
        self.assertEqual(adopted["mutiny"], "3.3.0")

    def test_every_adopted_ledger_coordinate_matches_the_candidate_catalog(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        catalog = CATALOG.read_text(encoding="utf-8")
        versions_section = catalog.split("[versions]", 1)[1].split("\n[", 1)[0]
        versions = dict(
            re.findall(
                r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"',
                versions_section,
                flags=re.MULTILINE,
            )
        )

        for delta in ledger["delta"]:
            coordinate = delta["coordinate"]
            group, name = coordinate.split(":", 1) if ":" in coordinate else ("", "")
            candidate_lines = [
                line
                for line in catalog.splitlines()
                if f'module = "{coordinate}"' in line
                or (group and f'group = "{group}"' in line and f'name = "{name}"' in line)
                or f'id = "{coordinate}"' in line
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

            self.assertIn(
                delta["after"],
                resolved_versions,
                f'{delta["authority-key"]} does not match {coordinate} in the catalog',
            )

    def test_library_batch_two_matches_the_candidate_catalog(self) -> None:
        catalog = CATALOG.read_text(encoding="utf-8")
        expected_families = {
            "managed-grpc-": "1.83.1",
            "managed-cassandra-java-driver-": "4.19.3",
            "managed-mongo": "5.9.1",
            "managed-mutiny": "3.3.0",
            "managed-rest-assured": "6.0.1",
        }
        excluded_keys = {
            "managed-grpc-google-common-protos-h49f5a7d50588",
            "managed-grpc-kotlin-stub-hb3943aafd993",
            "managed-grpc-protoc-gen-grpc-kotlin-h8643385749ff",
        }
        for prefix, version in expected_families.items():
            matching = [
                line
                for line in catalog.splitlines()
                if line.startswith(prefix)
                and line.split("=", 1)[0].strip() not in excluded_keys
            ]
            self.assertGreater(len(matching), 0, prefix)
            self.assertTrue(
                all(f'= "{version}"' in line for line in matching),
                f"{prefix} family is not aligned to {version}",
            )

        for key, version in {
            "managed-groovy-h1ef057f2b39e": "5.0.8",
            "managed-groovy-jsr223-h7a8657ed8c7a": "5.0.8",
            "managed-javers-core-had7b72eff626": "7.11.7",
            "managed-r2dbc-mariadb-h5b11561e1948": "1.4.1",
            "managed-r2dbc-mysql-hd139bc72be49": "1.4.3",
            "managed-r2dbc-postgresql-h38255c5a2805": "1.1.2.RELEASE",
            "managed-spring-cloud-dependencies-hfea315df9a2c": "2025.1.2",
        }.items():
            self.assertIn(f'{key} = "{version}"', catalog)


if __name__ == "__main__":
    unittest.main()
