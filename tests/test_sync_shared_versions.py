from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync-shared-versions.py"
SPEC = importlib.util.spec_from_file_location("sync_shared_versions", SCRIPT_PATH)
assert SPEC is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_shared_versions"] = sync
assert SPEC.loader is not None
SPEC.loader.exec_module(sync)


class SyncSharedVersionsTest(unittest.TestCase):
    def test_read_source_versions_reads_only_marked_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[versions]",
                        'ignored = "0.1.0"',
                        sync.SOURCE_START,
                        'kotlin = "2.3.21"  # central',
                        sync.SOURCE_END,
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            versions = sync.read_source_versions(catalog)

        self.assertEqual(set(versions), {"kotlin"})
        self.assertEqual(versions["kotlin"].version, "2.3.21")

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
            catalog.write_text("[versions]\nkotlin = \"2.3.21\"\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "missing source-of-truth markers"):
                sync.read_source_versions(catalog)

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
                    version="2.3.21",
                    line='kotlin = "2.3.21"  # central',
                ),
            }

            synced_text, changes = sync.sync_catalog(catalog, source)

        self.assertIn('kotlin = "2.3.21"', synced_text)
        self.assertIn('repo-only = "1.0.0"', synced_text)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].alias, "kotlin")

    def test_sync_catalog_does_not_rewrite_when_version_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            catalog = repo / "gradle" / "libs.versions.toml"
            catalog.parent.mkdir(parents=True)
            original = '[versions]\nkotlin = "2.3.21"  # local comment\n'
            catalog.write_text(original, encoding="utf-8")
            source = {
                "kotlin": sync.SourceVersion(
                    alias="kotlin",
                    version="2.3.21",
                    line='kotlin = "2.3.21"  # central comment',
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

    def test_verify_source_version_matches_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "gradle.properties").write_text(
                "baseVersion=1.0.0\nsnapshotVersion=\n",
                encoding="utf-8",
            )
            source = {
                "bluetape4k-dependencies": sync.SourceVersion(
                    alias="bluetape4k-dependencies",
                    version="1.0.0",
                    line='bluetape4k-dependencies = "1.0.0"',
                ),
            }

            sync.verify_source_version_matches_project(repo, source)

    def test_cli_check_detects_drift_and_write_fixes_it(self) -> None:
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
            self.assertIn("bluetape4k-projects: kotlin 0.0.0 ->", check.stdout)
            self.assertIn("Shared version drift detected", check.stderr)

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

            self.assertEqual(write.returncode, 0, write.stderr)
            self.assertNotIn('kotlin = "0.0.0"', catalog.read_text(encoding="utf-8"))

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

            self.assertEqual(recheck.returncode, 0, recheck.stderr)
            self.assertIn("Shared versions are aligned.", recheck.stdout)


if __name__ == "__main__":
    unittest.main()
