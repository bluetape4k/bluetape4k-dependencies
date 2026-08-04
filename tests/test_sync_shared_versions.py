from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "sync-shared-versions.py"
)
SPEC = importlib.util.spec_from_file_location("sync_shared_versions", SCRIPT_PATH)
assert SPEC is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_shared_versions"] = sync
assert SPEC.loader is not None
SPEC.loader.exec_module(sync)


class SyncSharedVersionsTest(unittest.TestCase):
    def test_real_catalog_centrally_governs_slf4j_bridges(self) -> None:
        catalog_path = SCRIPT_PATH.parents[1] / "gradle" / "libs.versions.toml"
        libraries = sync.read_catalog(catalog_path).libraries

        expected_modules = {
            "jcl-over-slf4j": "org.slf4j:jcl-over-slf4j",
            "jul-to-slf4j": "org.slf4j:jul-to-slf4j",
            "log4j-over-slf4j": "org.slf4j:log4j-over-slf4j",
        }

        for alias, module in expected_modules.items():
            with self.subTest(alias=alias):
                self.assertEqual(libraries[alias].module, module)
                self.assertEqual(libraries[alias].version_ref, "slf4j")

    def test_catalog_ref_gaps_detect_settings_and_ci_workflow_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "bluetape4k-sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            workflow = repo / ".github" / "workflows" / "ci.yml"
            catalog.parent.mkdir(parents=True)
            workflow.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            (repo / "settings.gradle.kts").write_text(
                'val catalogRef = providers.gradleProperty("catalogRef").orElse("'
                + "a" * 40
                + '")\n',
                encoding="utf-8",
            )
            workflow.write_text(
                "env:\n  BLUETAPE4K_DEPENDENCIES_CATALOG_REF: '" + "b" * 40 + "'\n",
                encoding="utf-8",
            )

            gaps = sync.find_catalog_ref_gaps("bluetape4k-sample", catalog)

        self.assertEqual(
            gaps,
            [
                sync.AdoptionGap(
                    "bluetape4k-sample",
                    "catalog-ref-mismatch",
                    "BLUETAPE4K_DEPENDENCIES_CATALOG_REF",
                    "a" * 40,
                    "b" * 40,
                ),
            ],
        )

    def test_catalog_ref_gaps_accept_matching_settings_and_ci_workflow_refs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "bluetape4k-sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            workflow = repo / ".github" / "workflows" / "ci.yml"
            catalog.parent.mkdir(parents=True)
            workflow.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            expected_ref = "c" * 40
            (repo / "settings.gradle.kts").write_text(
                f'val catalogRef = providers.gradleProperty("catalogRef").orElse("{expected_ref}")\n',
                encoding="utf-8",
            )
            workflow.write_text(
                f"env:\n  BLUETAPE4K_DEPENDENCIES_CATALOG_REF: '{expected_ref}'\n",
                encoding="utf-8",
            )

            gaps = sync.find_catalog_ref_gaps("bluetape4k-sample", catalog)

        self.assertEqual(gaps, [])

    def test_catalog_loader_gaps_detect_implicit_sibling_and_missing_safety_contracts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "bluetape4k-sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            (repo / "settings.gradle.kts").write_text(
                'val sibling = "../bluetape4k-dependencies/gradle/libs.versions.toml"\n'
                "uri(url).toURL().openStream()\n",
                encoding="utf-8",
            )

            gaps = sync.find_catalog_loader_gaps("bluetape4k-sample", catalog)

        self.assertIn("implicit-sibling-fallback", {gap.key for gap in gaps})
        self.assertIn("explicit-regular-file", {gap.key for gap in gaps})
        self.assertIn("immutable-ref", {gap.key for gap in gaps})
        self.assertIn("bounded-download", {gap.key for gap in gaps})
        self.assertIn("catalog-structure", {gap.key for gap in gaps})

    def test_catalog_loader_gaps_accept_complete_loader_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "bluetape4k-sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            (repo / "settings.gradle.kts").write_text(
                "\n".join(
                    [
                        "bluetape4kDependenciesCatalogRef.matches(Regex(immutableRefPattern))",
                        "java.nio.file.Files.isSymbolicLink(catalogFile.toPath())",
                        "connection.connectTimeout = 10_000",
                        "connection.readTimeout = 30_000",
                        "fun downloadCatalogFile(url: String, target: File, maxBytes: Long)",
                        "fun validateCatalogStructure(catalogFile: File)",
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            gaps = sync.find_catalog_loader_gaps("bluetape4k-sample", catalog)

        self.assertEqual(gaps, [])

    def test_real_catalog_centrally_governs_complete_exposed_family(self) -> None:
        catalog_path = SCRIPT_PATH.parents[1] / "gradle" / "libs.versions.toml"
        libraries = sync.read_catalog(catalog_path).libraries

        expected_modules = {
            "exposed-bom": "org.jetbrains.exposed:exposed-bom",
            "exposed-core": "org.jetbrains.exposed:exposed-core",
            "exposed-dao": "org.jetbrains.exposed:exposed-dao",
            "exposed-java-time": "org.jetbrains.exposed:exposed-java-time",
            "exposed-jdbc": "org.jetbrains.exposed:exposed-jdbc",
            "exposed-json": "org.jetbrains.exposed:exposed-json",
            "exposed-migration-jdbc": "org.jetbrains.exposed:exposed-migration-jdbc",
            "exposed-migration-r2dbc": "org.jetbrains.exposed:exposed-migration-r2dbc",
            "exposed-r2dbc": "org.jetbrains.exposed:exposed-r2dbc",
            "exposed-spring7-transaction": "org.jetbrains.exposed:spring7-transaction",
            "exposed-spring-boot4-starter": "org.jetbrains.exposed:exposed-spring-boot4-starter",
        }

        for alias, module in expected_modules.items():
            with self.subTest(alias=alias):
                self.assertEqual(libraries[alias].module, module)
                self.assertEqual(libraries[alias].version_ref, "exposed")

    def test_default_repositories_include_active_gradle_repos(self) -> None:
        self.assertIn("bluetape4k-projects", sync.DEFAULT_REPOSITORIES)
        self.assertIn("bluetape4k-exposed", sync.DEFAULT_REPOSITORIES)
        self.assertIn("bluetape4k-experimental", sync.DEFAULT_REPOSITORIES)
        for repo in sync.EXAMPLE_REPOSITORIES:
            self.assertNotIn(repo, sync.DEFAULT_REPOSITORIES)

    def test_compatibility_line_errors_detect_wrong_major(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'spring-kafka = "3.3.13"',
                        'spring-kafka4 = "3.3.15"',
                        'jackson3 = "3.1.3"',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            errors = sync.compatibility_line_errors(catalog, "sample")

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].repo, "sample")
        self.assertEqual(errors[0].alias, "spring-kafka4")
        self.assertEqual(errors[0].expected_major, "4")

    def test_compatibility_line_errors_accept_expected_major(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'spring-boot3 = "3.5.14"',
                        'spring-boot4 = "4.0.6"',
                        'jackson2 = "2.21.3"',
                        'jackson3 = "3.1.3"',
                        'kafka3 = "3.9.2"',
                        'kafka4 = "4.2.0"',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            errors = sync.compatibility_line_errors(catalog, "sample")

        self.assertEqual(errors, [])

    def test_print_default_repositories_cli(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--print-default-repositories",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bluetape4k-projects", result.stdout)
        self.assertIn("bluetape4k-exposed", result.stdout)
        self.assertNotIn("exposed-workshop", result.stdout)

    def test_inventory_cli_accepts_report_and_disposition_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--print-default-repositories",
                    "--inventory-out",
                    str(Path(tmp) / "inventory.json"),
                    "--summary-out",
                    str(Path(tmp) / "summary.json"),
                    "--dispositions",
                    str(Path(tmp) / "dispositions.json"),
                    "--format",
                    "json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_canonical_json_bytes_is_sorted_and_newline_terminated(self) -> None:
        self.assertEqual(
            sync.canonical_json_bytes({"z": 1, "a": {"한글": 2}}),
            '{"a":{"한글":2},"z":1}\n'.encode(),
        )

    def test_dispositions_require_exact_inventory_pair_set(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parent / "fixtures" / "catalog-authority"
        )
        expected_pairs = {("a" * 64, "default")}

        valid = sync.load_dispositions(fixture_root / "dispositions-valid.json")
        sync.validate_dispositions(valid, expected_pairs)

        orphan = sync.load_dispositions(fixture_root / "dispositions-orphan.json")
        with self.assertRaisesRegex(RuntimeError, "orphan"):
            sync.validate_dispositions(orphan, expected_pairs)

    def test_dispositions_reject_invalid_evidence_combination(self) -> None:
        invalid = {
            "schema-version": 1,
            "records": [
                {
                    "authority-id": "a" * 64,
                    "line-id": "default",
                    "disposition": "bom-managed-versionless",
                    "evidence": {
                        "type": "catalog-alias",
                        "path": "gradle/libs.versions.toml",
                    },
                    "status": "pending",
                    "owner": "dependency-governance",
                }
            ],
        }

        with self.assertRaisesRegex(RuntimeError, "publication-pom"):
            sync.validate_dispositions(invalid, {("a" * 64, "default")})

    def test_dispositions_reject_missing_and_duplicate_pairs(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parent / "fixtures" / "catalog-authority"
        )
        valid = sync.load_dispositions(fixture_root / "dispositions-valid.json")
        with self.assertRaisesRegex(RuntimeError, "missing"):
            sync.validate_dispositions(
                valid, {("a" * 64, "default"), ("b" * 64, "default")}
            )

        duplicate = {**valid, "records": valid["records"] * 2}
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            sync.validate_dispositions(duplicate, {("a" * 64, "default")})

    def test_authority_lines_split_same_coordinate_compatibility_families(self) -> None:
        if sys.version_info < (3, 11):
            self.skipTest("catalog authority inventory requires stdlib tomllib")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            central = root / "central.toml"
            central.write_text(
                """[versions]
h2-v2 = "2.4.240"
[libraries]
h2-v2 = { module = "com.h2database:h2", version.ref = "h2-v2" }
""",
                encoding="utf-8",
            )
            repository = root / "bluetape4k-projects"
            catalog = repository / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                """[versions]
h2-v1 = "1.4.197"
h2-v2 = "2.4.240"
[libraries]
h2 = { module = "com.h2database:h2", version.ref = "h2-v1" }
h2-v2 = { module = "com.h2database:h2", version.ref = "h2-v2" }
""",
                encoding="utf-8",
            )
            lines_path = root / "authority-lines.json"
            lines_path.write_text(
                json.dumps(
                    {
                        "schema-version": 1,
                        "records": [
                            {
                                "repository": "bluetape4k-projects",
                                "subject-kind": "library",
                                "coordinate-or-plugin-id": "com.h2database:h2",
                                "alias": "h2",
                                "line-id": "h2-1",
                            },
                            {
                                "repository": "bluetape4k-projects",
                                "subject-kind": "library",
                                "coordinate-or-plugin-id": "com.h2database:h2",
                                "alias": "h2-v2",
                                "line-id": "h2-2",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            lines = sync.load_authority_lines(lines_path)
            used: set[tuple[str, str, str, str]] = set()
            records = sync.catalog_authority_records(
                root,
                central,
                ("bluetape4k-projects",),
                authority_lines=lines,
                used_authority_lines=used,
            )
            sync.validate_authority_line_usage(lines, used)

        self.assertEqual(
            {(record["alias"], record["line-id"]) for record in records},
            {("h2", "h2-1"), ("h2-v2", "h2-2")},
        )
        self.assertEqual(
            len(
                {
                    (record["authority-id"], record["line-id"])
                    for record in records
                }
            ),
            2,
        )

    def test_authority_lines_reject_duplicate_and_unused_selectors(self) -> None:
        record = {
            "repository": "bluetape4k-projects",
            "subject-kind": "library",
            "coordinate-or-plugin-id": "com.h2database:h2",
            "alias": "h2",
            "line-id": "h2-1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "authority-lines.json"
            path.write_text(
                json.dumps({"schema-version": 1, "records": [record, record]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "duplicate authority line"):
                sync.load_authority_lines(path)

        selector = (
            "bluetape4k-projects",
            "library",
            "com.h2database:h2",
            "h2",
        )
        with self.assertRaisesRegex(RuntimeError, "unused authority line"):
            sync.validate_authority_line_usage({selector: "h2-1"}, set())

    def test_structural_disposition_requires_same_repository_issue_and_review_date(
        self,
    ) -> None:
        record = {
            "authority-id": "a" * 64,
            "line-id": "default",
            "disposition": "structural-repo-owned",
            "evidence": {
                "type": "settings-evaluation",
                "path": "settings.gradle.kts",
            },
            "status": "pending",
            "owner": "dependency-governance",
            "repository": "bluetape4k-projects",
            "issue": "https://github.com/bluetape4k/bluetape4k-aws/issues/1",
            "review-by": "2026-12-01",
        }
        manifest = {"schema-version": 1, "records": [record]}

        with self.assertRaisesRegex(RuntimeError, "same-repository issue"):
            sync.validate_dispositions(
                manifest, {("a" * 64, "default")}, today=date(2026, 8, 4)
            )

        record["issue"] = "https://github.com/bluetape4k/bluetape4k-projects/issues/1"
        record["review-by"] = "2026-08-04"
        with self.assertRaisesRegex(RuntimeError, "expired structural review"):
            sync.validate_dispositions(
                manifest, {("a" * 64, "default")}, today=date(2026, 8, 4)
            )

    def test_real_workspace_has_approved_explicit_external_library_baseline(
        self,
    ) -> None:
        if sys.version_info < (3, 11):
            self.skipTest("catalog authority inventory requires stdlib tomllib")
        workspace = SCRIPT_PATH.parents[4]
        if not all(
            (workspace / repo / "gradle" / "libs.versions.toml").is_file()
            for repo in sync.DEFAULT_REPOSITORIES
        ):
            self.skipTest("managed sibling repositories are unavailable")

        authority_lines = sync.load_authority_lines(
            SCRIPT_PATH.parents[1]
            / "config"
            / "central-catalog-authority-lines.json"
        )
        used_authority_lines: set[tuple[str, str, str, str]] = set()
        records = sync.catalog_authority_records(
            workspace,
            SCRIPT_PATH.parents[1] / "gradle" / "libs.versions.toml",
            sync.DEFAULT_REPOSITORIES,
            authority_lines=authority_lines,
            used_authority_lines=used_authority_lines,
        )
        sync.validate_authority_line_usage(authority_lines, used_authority_lines)

        self.assertEqual(
            sum(record["subject-kind"] == "library" for record in records), 864
        )
        self.assertEqual(
            sum(record["subject-kind"] == "plugin" for record in records), 44
        )
        self.assertEqual(
            len(
                {
                    record["coordinate-or-plugin-id"]
                    for record in records
                    if record["subject-kind"] == "plugin"
                }
            ),
            9,
        )
        self.assertEqual(
            {
                (record["repository"], record["alias"], record["line-id"])
                for record in records
                if record["line-id"] != "default"
            },
            {
                ("bluetape4k-projects", "h2", "h2-1"),
                ("bluetape4k-projects", "h2-v2", "h2-2"),
                (
                    "bluetape4k-projects",
                    "jakarta-persistence-api",
                    "jakarta-persistence-31",
                ),
                (
                    "bluetape4k-projects",
                    "jakarta-persistence-api-v32",
                    "jakarta-persistence-32",
                ),
            },
        )
        self.assertEqual(
            records,
            sorted(
                records,
                key=lambda item: (
                    item["repository"],
                    item["source-path"],
                    item["source-line"],
                    item["alias"],
                ),
            ),
        )

    def test_real_workspace_has_approved_hard_coded_candidate_baseline(self) -> None:
        if sys.version_info < (3, 11):
            self.skipTest("catalog authority inventory requires stdlib tomllib")
        workspace = SCRIPT_PATH.parents[4]
        if not all((workspace / repo).is_dir() for repo in sync.DEFAULT_REPOSITORIES):
            self.skipTest("managed sibling repositories are unavailable")

        records = sync.hard_coded_authority_records(
            workspace, sync.DEFAULT_REPOSITORIES
        )

        self.assertEqual(len(records), 43)
        self.assertEqual(
            sum(
                record["coordinate-or-plugin-id"]
                == "org.gradle.toolchains.foojay-resolver-convention"
                for record in records
            ),
            9,
        )
        self.assertFalse(
            any(
                record["coordinate-or-plugin-id"].startswith(("scm:", "jdbc:"))
                for record in records
            )
        )

    def test_read_source_versions_reads_only_marked_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'ignored = "0.1.0"',
                        sync.SOURCE_START,
                        'kotlin = "2.4.0"  # central',
                        sync.SOURCE_END,
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            versions = sync.read_source_versions(catalog)

        self.assertEqual(set(versions), {"kotlin"})
        self.assertEqual(versions["kotlin"].version, "2.4.0")

    def test_read_source_versions_keeps_mavenrepository_group_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        sync.SOURCE_START,
                        'jackson = "2.21.3"  # https://mvnrepository.com/artifact/com.fasterxml.jackson/jackson-bom',
                        sync.SOURCE_END,
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            versions = sync.read_source_versions(catalog)

        self.assertEqual(
            versions["jackson"].module_groups, frozenset({"com.fasterxml.jackson"})
        )

    def test_read_source_versions_requires_marked_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text('[versions]\nkotlin = "2.4.0"\n', encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError, "missing source-of-truth markers"
            ):
                sync.read_source_versions(catalog)

    def test_central_catalog_exposes_all_shared_plugin_ids(self) -> None:
        catalog = sync.read_catalog(
            Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml"
        )

        expected = {
            "kotlin-allopen": ("org.jetbrains.kotlin.plugin.allopen", "kotlin"),
            "kotlin-jpa": ("org.jetbrains.kotlin.plugin.jpa", "kotlin"),
            "kotlin-kapt": ("org.jetbrains.kotlin.kapt", "kotlin"),
            "kotlin-noarg": ("org.jetbrains.kotlin.plugin.noarg", "kotlin"),
            "kotlin-serialization": (
                "org.jetbrains.kotlin.plugin.serialization",
                "kotlin",
            ),
            "kotlin-spring": ("org.jetbrains.kotlin.plugin.spring", "kotlin"),
            "gatling": ("io.gatling.gradle", "gatling"),
            "kover": ("org.jetbrains.kotlinx.kover", "kover"),
            "shadow": ("com.gradleup.shadow", "shadow"),
            "spring-boot3": ("org.springframework.boot", "spring-boot3"),
            "spring-boot4": ("org.springframework.boot", "spring-boot4"),
        }

        for alias, (plugin_id, version_ref) in expected.items():
            with self.subTest(alias=alias):
                self.assertEqual(catalog.plugins[alias].plugin_id, plugin_id)
                self.assertEqual(catalog.plugins[alias].version_ref, version_ref)

    def test_sync_catalog_updates_only_matching_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'kotlin = "2.3.20"',
                        'repo-only = "1.0.0"',
                        "",
                    ],
                ),
                encoding="utf-8",
            )
            source = {
                "kotlin": sync.SourceVersion(
                    alias="kotlin",
                    version="2.4.0",
                    line='kotlin = "2.4.0"  # central',
                ),
            }

            synced_text, changes = sync.sync_catalog(catalog, source)

        self.assertIn('kotlin = "2.4.0"', synced_text)
        self.assertIn('repo-only = "1.0.0"', synced_text)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].alias, "kotlin")

    def test_sync_catalog_does_not_rewrite_when_version_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            original = '[versions]\nkotlin = "2.4.0"  # local comment\n'
            catalog.write_text(original, encoding="utf-8")
            source = {
                "kotlin": sync.SourceVersion(
                    alias="kotlin",
                    version="2.4.0",
                    line='kotlin = "2.4.0"  # central comment',
                ),
            }

            synced_text, changes = sync.sync_catalog(catalog, source)

        self.assertEqual(synced_text, original)
        self.assertEqual(changes, [])

    def test_sync_catalog_updates_inline_library_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                "\n".join(
                    [
                        "[libraries]",
                        'fory-kotlin = { module = "org.apache.fory:fory-kotlin", version = "0.14.1" }',
                        "",
                    ],
                ),
                encoding="utf-8",
            )
            source = {
                "fory-kotlin": sync.SourceVersion(
                    alias="fory-kotlin",
                    version="0.15.0",
                    line='fory-kotlin = "0.15.0"',
                ),
            }

            synced_text, changes = sync.sync_catalog(catalog, source)

        self.assertIn('version = "0.15.0"', synced_text)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].alias, "fory-kotlin")

    def test_sync_catalog_skips_same_alias_for_different_module_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            original = "\n".join(
                [
                    "[versions]",
                    'jackson = "3.1.3"',
                    "",
                    "[libraries]",
                    'jackson-bom = { module = "tools.jackson:jackson-bom", version.ref = "jackson" }',
                    "",
                ],
            )
            catalog.write_text(original, encoding="utf-8")
            source = {
                "jackson": sync.SourceVersion(
                    alias="jackson",
                    version="2.21.3",
                    line='jackson = "2.21.3"',
                    module_groups=frozenset({"com.fasterxml.jackson"}),
                ),
            }

            synced_text, changes = sync.sync_catalog(catalog, source)

        self.assertEqual(synced_text, original)
        self.assertEqual(changes, [])

    def test_verify_self_version_alias_allows_released_consumer_line(self) -> None:
        source = {
            "bluetape4k-dependencies": sync.SourceVersion(
                alias="bluetape4k-dependencies",
                version="1.1.3",
                line='bluetape4k-dependencies = "1.1.3"',
            ),
        }

        sync.verify_self_version_alias(source)

    def test_verify_self_version_alias_requires_self_alias(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "source-of-truth block"):
            sync.verify_self_version_alias({})

    def test_cli_check_rejects_duplicate_and_write_does_not_mutate_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            catalog = (
                workspace / "bluetape4k-projects" / "gradle" / "libs.versions.toml"
            )
            catalog.parent.mkdir(parents=True)
            catalog.write_text('[versions]\nkotlin = "0.0.0"\n', encoding="utf-8")

            check = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--workspace",
                    str(workspace),
                    "--repo",
                    "bluetape4k-projects",
                    "--check",
                    "--summary",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(check.returncode, 0)
            self.assertIn("bluetape4k-projects", check.stdout + check.stderr)
            self.assertIn("kotlin", check.stdout + check.stderr)

            write = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--workspace",
                    str(workspace),
                    "--repo",
                    "bluetape4k-projects",
                    "--write",
                    "--check",
                    "--summary",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(write.returncode, 0)
            self.assertIn('kotlin = "0.0.0"', catalog.read_text(encoding="utf-8"))

            recheck = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--workspace",
                    str(workspace),
                    "--repo",
                    "bluetape4k-projects",
                    "--check",
                    "--summary",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(recheck.returncode, 0)

    def test_equal_central_version_is_still_an_adoption_gap(self) -> None:
        source_catalog = sync.read_catalog(
            Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text('[versions]\nkotlin = "2.4.0"\n', encoding="utf-8")

            gaps = sync.find_adoption_gaps(
                "bluetape4k-projects",
                sync.read_catalog(catalog),
                source_catalog,
                (),
            )

        self.assertTrue(
            any(gap.kind == "version-duplicate" and gap.key == "kotlin" for gap in gaps)
        )

    def test_exact_coordinate_duplicate_and_alias_identity_conflict_are_reported(
        self,
    ) -> None:
        source_catalog = sync.read_catalog(
            Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'classgraph = "4.8.184"',
                        "",
                        "[libraries]",
                        'local-classgraph = { module = "io.github.classgraph:classgraph", version.ref = "classgraph" }',
                        'classgraph = { module = "io.github.classgraph:different-artifact", version.ref = "classgraph" }',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            gaps = sync.find_adoption_gaps(
                "bluetape4k-projects",
                sync.read_catalog(catalog),
                source_catalog,
                (),
            )

        self.assertTrue(
            any(
                gap.kind == "library-coordinate-duplicate"
                and gap.key == "local-classgraph"
                for gap in gaps
            )
        )
        self.assertTrue(
            any(
                gap.kind == "library-identity-conflict" and gap.key == "classgraph"
                for gap in gaps
            )
        )

    def test_versionless_local_alias_is_allowed_but_inline_version_is_reported(
        self,
    ) -> None:
        source_catalog = sync.read_catalog(
            Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[libraries]",
                        'managed-classgraph = { module = "io.github.classgraph:classgraph" }',
                        'pinned-classgraph = { module = "io.github.classgraph:classgraph", version = "4.8.184" }',
                        "",
                        "[plugins]",
                        'managed-kotlin = { id = "org.jetbrains.kotlin.jvm" }',
                        'pinned-kotlin = { id = "org.jetbrains.kotlin.jvm", version = "2.4.0" }',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            gaps = sync.find_adoption_gaps(
                "bluetape4k-projects",
                sync.read_catalog(catalog),
                source_catalog,
                (),
            )

        self.assertFalse(any(gap.key == "managed-classgraph" for gap in gaps))
        self.assertFalse(any(gap.key == "managed-kotlin" for gap in gaps))
        self.assertTrue(
            any(
                gap.kind == "library-coordinate-duplicate"
                and gap.key == "pinned-classgraph"
                for gap in gaps
            )
        )
        self.assertTrue(
            any(
                gap.kind == "plugin-id-duplicate" and gap.key == "pinned-kotlin"
                for gap in gaps
            )
        )

    def test_exact_plugin_id_duplicate_and_plugin_id_conflict_are_reported(
        self,
    ) -> None:
        source_catalog = sync.read_catalog(
            Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'kotlin = "2.4.0"',
                        "",
                        "[plugins]",
                        'local-kotlin = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }',
                        'kotlin-jvm = { id = "example.not-kotlin", version.ref = "kotlin" }',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            gaps = sync.find_adoption_gaps(
                "bluetape4k-projects",
                sync.read_catalog(catalog),
                source_catalog,
                (),
            )

        self.assertTrue(
            any(
                gap.kind == "plugin-id-duplicate" and gap.key == "local-kotlin"
                for gap in gaps
            )
        )
        self.assertTrue(
            any(
                gap.kind == "plugin-identity-conflict" and gap.key == "kotlin-jvm"
                for gap in gaps
            )
        )

    def test_valid_exception_preserves_compatibility_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exception_file = Path(tmp) / "exceptions.toml"
            exception_file.write_text(
                "\n".join(
                    [
                        "[[exception]]",
                        'repository = "bluetape4k-exposed"',
                        'key = "querydsl5"',
                        'central-key = "querydsl"',
                        'kind = "library-version"',
                        'coordinate = "com.querydsl:querydsl-core"',
                        'expected-local-version = "5.1.0"',
                        'compatibility-family = "querydsl-javax"',
                        'reason = "The repository still compiles against the javax QueryDSL line."',
                        'issue = "https://github.com/bluetape4k/bluetape4k-exposed/issues/999"',
                        'owner = "bluetape4k-exposed-maintainers"',
                        'introduced = "2026-07-15"',
                        'review-by = "2026-10-15"',
                        'resolution-condition = "Remove after the QueryDSL 7 migration passes."',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            exceptions = sync.load_exceptions(exception_file, today=date(2026, 7, 15))

        self.assertEqual(len(exceptions), 1)
        self.assertEqual(exceptions[0].central_key, "querydsl")
        self.assertEqual(exceptions[0].expected_local_version, "5.1.0")

    def test_exception_only_suppresses_the_declared_library_pin(self) -> None:
        central = sync.CatalogData(
            path=Path("central.toml"),
            versions={"querydsl": "7.0.0"},
            libraries={
                "querydsl-core": sync.CatalogLibrary(
                    alias="querydsl-core",
                    module="com.querydsl:querydsl-core",
                    version_ref="querydsl",
                ),
            },
            plugins={},
        )
        local = sync.CatalogData(
            path=Path("local.toml"),
            versions={"querydsl5": "5.1.0"},
            libraries={
                "querydsl5-core": sync.CatalogLibrary(
                    alias="querydsl5-core",
                    module="com.querydsl:querydsl-core",
                    version_ref="querydsl5",
                ),
            },
            plugins={},
        )
        declared = sync.CatalogException(
            repository="bluetape4k-exposed",
            key="querydsl5-core",
            central_key="querydsl-core",
            kind="library-version",
            coordinate="com.querydsl:querydsl-core",
            expected_local_version="5.1.0",
            compatibility_family="querydsl5",
            reason="Keep the javax compatibility line.",
            issue="https://github.com/bluetape4k/bluetape4k-exposed/issues/999",
            owner="bluetape4k-exposed-maintainers",
            introduced=date(2026, 7, 15),
            review_by=date(2026, 10, 15),
            resolution_condition="Remove after QueryDSL migration.",
        )

        self.assertEqual(
            sync.find_adoption_gaps("bluetape4k-exposed", local, central, (declared,)),
            [],
        )
        for changed in (
            replace(declared, kind="plugin-version"),
            replace(declared, coordinate="com.querydsl:not-querydsl-core"),
            replace(declared, expected_local_version="999.0.0"),
            replace(declared, compatibility_family="querydsl6"),
        ):
            with self.subTest(changed=changed):
                gaps = sync.find_adoption_gaps(
                    "bluetape4k-exposed", local, central, (changed,)
                )
                self.assertTrue(
                    any(gap.kind == "library-coordinate-duplicate" for gap in gaps)
                )

    def test_exception_schema_rejects_unknown_or_expired_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exception_file = Path(tmp) / "exceptions.toml"
            exception_file.write_text(
                "\n".join(
                    [
                        "[[exception]]",
                        'repository = "bluetape4k-exposed"',
                        'key = "querydsl5"',
                        'central-key = "querydsl"',
                        'kind = "library-version"',
                        'coordinate = "com.querydsl:querydsl-core"',
                        'expected-local-version = "5.1.0"',
                        'compatibility-family = "querydsl-javax"',
                        'reason = "The repository still compiles against the javax QueryDSL line."',
                        'issue = "https://github.com/bluetape4k/bluetape4k-exposed/issues/999"',
                        'owner = "bluetape4k-exposed-maintainers"',
                        'introduced = "2026-01-01"',
                        'review-by = "2026-02-01"',
                        'resolution-condition = "Remove after migration."',
                        'unexpected = "not allowed"',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "unknown|expired"):
                sync.load_exceptions(exception_file, today=date(2026, 7, 15))

    def test_repository_map_rejects_legacy_flat_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            catalog = root / "bluetape4k-projects" / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            legacy_map = root / "legacy.json"
            legacy_map.write_text(
                json.dumps(
                    {
                        "not-managed": {
                            "catalog": str(catalog),
                            "branch": "x",
                            "expected_head": "a" * 40,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "top-level fields"):
                sync.load_repository_map(legacy_map, root, sync.DEFAULT_REPOSITORIES)

    def test_target_catalogs_rejects_missing_requested_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                RuntimeError, "missing managed repository catalog"
            ):
                sync.target_catalogs(Path(tmp), ("bluetape4k-projects",))

    def test_repository_map_uses_shared_strict_v1_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            invalid = root / "invalid.json"
            invalid.write_text('{"schema_version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "top-level fields"):
                sync.load_repository_map(invalid, root, sync.DEFAULT_REPOSITORIES)


if __name__ == "__main__":
    unittest.main()
