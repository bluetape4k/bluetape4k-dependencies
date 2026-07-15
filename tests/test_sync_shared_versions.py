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


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync-shared-versions.py"
SPEC = importlib.util.spec_from_file_location("sync_shared_versions", SCRIPT_PATH)
assert SPEC is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_shared_versions"] = sync
assert SPEC.loader is not None
SPEC.loader.exec_module(sync)


class SyncSharedVersionsTest(unittest.TestCase):
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

        self.assertEqual(versions["jackson"].module_groups, frozenset({"com.fasterxml.jackson"}))

    def test_read_source_versions_requires_marked_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text("[versions]\nkotlin = \"2.4.0\"\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "missing source-of-truth markers"):
                sync.read_source_versions(catalog)

    def test_central_catalog_exposes_all_shared_plugin_ids(self) -> None:
        catalog = sync.read_catalog(Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml")

        expected = {
            "kotlin-allopen": ("org.jetbrains.kotlin.plugin.allopen", "kotlin"),
            "kotlin-jpa": ("org.jetbrains.kotlin.plugin.jpa", "kotlin"),
            "kotlin-kapt": ("org.jetbrains.kotlin.kapt", "kotlin"),
            "kotlin-noarg": ("org.jetbrains.kotlin.plugin.noarg", "kotlin"),
            "kotlin-serialization": ("org.jetbrains.kotlin.plugin.serialization", "kotlin"),
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
                        "kotlin = \"2.3.20\"",
                        "repo-only = \"1.0.0\"",
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
            catalog = workspace / "bluetape4k-projects" / "gradle" / "libs.versions.toml"
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
        source_catalog = sync.read_catalog(Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml")
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text('[versions]\nkotlin = "2.4.0"\n', encoding="utf-8")

            gaps = sync.find_adoption_gaps(
                "bluetape4k-projects",
                sync.read_catalog(catalog),
                source_catalog,
                (),
            )

        self.assertTrue(any(gap.kind == "version-duplicate" and gap.key == "kotlin" for gap in gaps))

    def test_exact_coordinate_duplicate_and_alias_identity_conflict_are_reported(self) -> None:
        source_catalog = sync.read_catalog(Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml")
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

        self.assertTrue(any(gap.kind == "library-coordinate-duplicate" and gap.key == "local-classgraph" for gap in gaps))
        self.assertTrue(any(gap.kind == "library-identity-conflict" and gap.key == "classgraph" for gap in gaps))

    def test_versionless_local_alias_is_allowed_but_inline_version_is_reported(self) -> None:
        source_catalog = sync.read_catalog(Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml")
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
        self.assertTrue(any(gap.kind == "library-coordinate-duplicate" and gap.key == "pinned-classgraph" for gap in gaps))
        self.assertTrue(any(gap.kind == "plugin-id-duplicate" and gap.key == "pinned-kotlin" for gap in gaps))

    def test_exact_plugin_id_duplicate_and_plugin_id_conflict_are_reported(self) -> None:
        source_catalog = sync.read_catalog(Path(__file__).resolve().parents[1] / "gradle" / "libs.versions.toml")
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

        self.assertTrue(any(gap.kind == "plugin-id-duplicate" and gap.key == "local-kotlin" for gap in gaps))
        self.assertTrue(any(gap.kind == "plugin-identity-conflict" and gap.key == "kotlin-jvm" for gap in gaps))

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

        self.assertEqual(sync.find_adoption_gaps("bluetape4k-exposed", local, central, (declared,)), [])
        for changed in (
            replace(declared, kind="plugin-version"),
            replace(declared, coordinate="com.querydsl:not-querydsl-core"),
            replace(declared, expected_local_version="999.0.0"),
            replace(declared, compatibility_family="querydsl6"),
        ):
            with self.subTest(changed=changed):
                gaps = sync.find_adoption_gaps("bluetape4k-exposed", local, central, (changed,))
                self.assertTrue(any(gap.kind == "library-coordinate-duplicate" for gap in gaps))

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

    def test_repository_map_rejects_unknown_traversal_and_symlink_catalogs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            real_repo = root / "bluetape4k-projects"
            catalog = real_repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            symlink = root / "catalog-link.toml"
            symlink.symlink_to(catalog)

            unknown_map = root / "unknown.json"
            unknown_map.write_text(
                json.dumps({"not-managed": {"catalog": str(catalog), "branch": "x", "expected_head": "a" * 40}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "managed repository"):
                sync.load_repository_map(unknown_map, root, sync.DEFAULT_REPOSITORIES)

            traversal_map = root / "traversal.json"
            traversal_map.write_text(
                json.dumps({"bluetape4k-projects": {"catalog": str(root / ".." / "outside.toml"), "branch": "x", "expected_head": "a" * 40}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "workspace|catalog"):
                sync.load_repository_map(traversal_map, root, sync.DEFAULT_REPOSITORIES)

            symlink_map = root / "symlink.json"
            symlink_map.write_text(
                json.dumps({"bluetape4k-projects": {"catalog": str(symlink), "branch": "x", "expected_head": "a" * 40}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                sync.load_repository_map(symlink_map, root, sync.DEFAULT_REPOSITORIES)

    def test_target_catalogs_rejects_missing_requested_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "missing managed repository catalog"):
                sync.target_catalogs(Path(tmp), ("bluetape4k-projects",))

    def test_repository_map_pins_candidate_branch_and_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "bluetape4k-projects"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[versions]\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "candidate", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "add", "gradle/libs.versions.toml"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Catalog Test",
                    "-c",
                    "user.email=catalog@example.invalid",
                    "commit",
                    "-m",
                    "candidate",
                ],
                check=True,
                capture_output=True,
            )
            head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            valid_map = root / "valid.json"
            valid_map.write_text(
                json.dumps(
                    {
                        "bluetape4k-projects": {
                            "catalog": str(catalog),
                            "branch": "candidate",
                            "expected_head": head,
                        },
                    },
                ),
                encoding="utf-8",
            )
            targets = sync.load_repository_map(valid_map, root, sync.DEFAULT_REPOSITORIES)
            self.assertEqual(targets["bluetape4k-projects"].expected_head, head)

            wrong_branch = root / "wrong-branch.json"
            wrong_branch.write_text(
                json.dumps(
                    {
                        "bluetape4k-projects": {
                            "catalog": str(catalog),
                            "branch": "other",
                            "expected_head": head,
                        },
                    },
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "branch mismatch"):
                sync.load_repository_map(wrong_branch, root, sync.DEFAULT_REPOSITORIES)

            wrong_head = root / "wrong-head.json"
            wrong_head.write_text(
                json.dumps(
                    {
                        "bluetape4k-projects": {
                            "catalog": str(catalog),
                            "branch": "candidate",
                            "expected_head": "a" * 40,
                        },
                    },
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "HEAD mismatch"):
                sync.load_repository_map(wrong_head, root, sync.DEFAULT_REPOSITORIES)


if __name__ == "__main__":
    unittest.main()
