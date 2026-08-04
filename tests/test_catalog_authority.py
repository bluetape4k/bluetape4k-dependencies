from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

if sys.version_info < (3, 11):
    raise unittest.SkipTest("catalog authority parser requires stdlib tomllib")


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "catalog_authority.py"
SPEC = importlib.util.spec_from_file_location("catalog_authority", SCRIPT_PATH)
assert SPEC is not None
catalog_authority = importlib.util.module_from_spec(SPEC)
sys.modules["catalog_authority"] = catalog_authority
assert SPEC.loader is not None
SPEC.loader.exec_module(catalog_authority)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "catalog-authority"


class CatalogAuthorityTest(unittest.TestCase):
    def test_hard_coded_to_catalog_keeps_authority_identity(self) -> None:
        downstream = catalog_authority.parse_catalog(
            FIXTURE_ROOT
            / "bluetape4k-projects"
            / "gradle"
            / "libs.versions.toml"
        )
        build_text = (
            FIXTURE_ROOT / "bluetape4k-projects" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        hard_coded = re.search(r'implementation\("([^:]+:[^:]+):[^"\s]+"\)', build_text)
        self.assertIsNotNone(hard_coded)
        assert hard_coded is not None
        hard_coded_coordinate = hard_coded.group(1)
        catalog_coordinate = downstream.libraries["demo"]["module"]

        before = catalog_authority.authority_id(
            "bluetape4k-projects", "library", hard_coded_coordinate
        )
        after = catalog_authority.authority_id(
            "bluetape4k-projects", "library", catalog_coordinate
        )

        self.assertEqual(before, after)
        self.assertEqual(
            before,
            hashlib.sha256(
                b"bluetape4k-projects\0library\0org.example:demo"
            ).hexdigest(),
        )

    def test_compatibility_lines_keep_distinct_line_identity(self) -> None:
        self.assertNotEqual(
            catalog_authority.authority_key("same-authority", "spring-boot-3"),
            catalog_authority.authority_key("same-authority", "spring-boot-4"),
        )

    def test_authority_key_rejects_noncanonical_line_identity(self) -> None:
        for line_id in ("Spring-boot-3", "spring_boot_3", "3-spring", "spring--3"):
            with self.subTest(line_id=line_id), self.assertRaisesRegex(
                ValueError, "invalid canonical line-id"
            ):
                catalog_authority.authority_key("same-authority", line_id)

    def test_authority_record_is_frozen(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(catalog_authority.AuthorityRecord)],
            [
                "authority_id",
                "line_id",
                "occurrence_id",
                "repository",
                "subject_kind",
                "declaration_form",
                "coordinate_or_plugin_id",
                "alias",
                "source_path",
                "source_line",
                "declared_version",
                "resolved_version",
            ],
        )
        record = catalog_authority.AuthorityRecord(
            authority_id="authority",
            line_id="default",
            occurrence_id="occurrence",
            repository="bluetape4k-projects",
            subject_kind="library",
            declaration_form="catalog",
            coordinate_or_plugin_id="org.example:demo",
            alias="demo",
            source_path="gradle/libs.versions.toml",
            source_line=3,
            declared_version="1.0.0",
            resolved_version="1.0.0",
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.alias = "changed"

    def test_synthetic_and_normalized_accessor_collisions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "reserved accessor namespace"):
            catalog_authority.validate_accessor_aliases(["plugins-foo"])
        for alias in ("foo.bar", "foo_bar"):
            with self.subTest(alias=alias), self.assertRaisesRegex(
                ValueError, "invalid accessor alias"
            ):
                catalog_authority.validate_accessor_aliases([alias])

    def test_invalid_and_kotlin_reserved_aliases_are_rejected(self) -> None:
        for alias, message in (("Demo", "invalid accessor alias"), ("when", "Kotlin reserved word")):
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, message):
                catalog_authority.validate_accessor_aliases([alias])

    def test_cross_tree_accessor_collisions_are_rejected(self) -> None:
        cases = (
            {"libraries": ["plugins-demo"], "plugins": ["demo"]},
            {"libraries": ["versions-demo"], "versions": ["demo"]},
            {"libraries": ["bundles-demo"], "bundles": ["demo"]},
        )
        for aliases in cases:
            with self.subTest(aliases=aliases), self.assertRaisesRegex(
                ValueError, "cross-tree accessor collision"
            ):
                catalog_authority.validate_accessor_aliases(**aliases)

    def test_namespaced_trees_can_reuse_an_alias(self) -> None:
        catalog_authority.validate_accessor_aliases(
            libraries=["demo"], plugins=["demo"], bundles=["demo"], versions=["demo"]
        )

    def test_catalog_parser_reads_central_and_downstream_catalogs(self) -> None:
        central = catalog_authority.parse_catalog(
            FIXTURE_ROOT / "central" / "gradle" / "libs.versions.toml"
        )
        downstream = catalog_authority.parse_catalog(
            FIXTURE_ROOT
            / "bluetape4k-projects"
            / "gradle"
            / "libs.versions.toml"
        )

        self.assertEqual(central.versions["demo-version"], "1.0.0")
        self.assertEqual(central.libraries["demo"]["module"], "org.example:demo")
        self.assertEqual(
            downstream.libraries["demo"]["version.ref"], "demo-version"
        )

    def test_catalog_parser_rejects_dynamic_and_range_versions(self) -> None:
        for selector in ("1.+", "latest.release", "[1.0,2.0)"):
            with self.subTest(selector=selector), tempfile.TemporaryDirectory() as tmp:
                catalog = Path(tmp) / "libs.versions.toml"
                catalog.write_text(
                    f'[versions]\ndemo = "{selector}"\n', encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "dynamic or range version"):
                    catalog_authority.parse_catalog(catalog)

    def test_catalog_parser_rejects_dynamic_shorthand_library_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                '[libraries]\ndemo = "org.example:demo:1.+"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "dynamic or range version"):
                catalog_authority.parse_catalog(catalog)

    def test_catalog_parser_accepts_exact_version_with_embedded_plus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                '[versions]\nnats-spring = "0.6.2+3.5"\n', encoding="utf-8"
            )

            parsed = catalog_authority.parse_catalog(catalog)

            self.assertEqual(parsed.versions["nats-spring"], "0.6.2+3.5")

    def test_catalog_parser_rejects_invalid_bundle_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text('[bundles]\ndemo = "not-a-list"\n', encoding="utf-8")
            with self.assertRaisesRegex(TypeError, "invalid bundles entry"):
                catalog_authority.parse_catalog(catalog)

    def test_real_catalog_has_no_accessor_collisions(self) -> None:
        catalog = catalog_authority.parse_catalog(
            SCRIPT_PATH.parents[1] / "gradle" / "libs.versions.toml"
        )

        self.assertGreater(len(catalog.versions), 0)
        self.assertGreater(len(catalog.libraries), 0)
        self.assertGreater(len(catalog.plugins), 0)

    def test_real_authority_policy_versions_match_the_catalog(self) -> None:
        repo_root = SCRIPT_PATH.parents[1]
        catalog = catalog_authority.parse_catalog(
            repo_root / "gradle" / "libs.versions.toml"
        )
        policy = json.loads(
            (repo_root / "config" / "central-catalog-authority-policy.json").read_text(
                encoding="utf-8"
            )
        )

        mismatches: list[str] = []
        for subject in policy["subjects"]:
            coordinate = subject["coordinate-or-plugin-id"]
            for line in subject["lines"]:
                version_key = line.get("version-key")
                if version_key is None:
                    continue
                expected = catalog.versions.get(version_key)
                if expected is None:
                    mismatches.append(f"{coordinate}: unknown version-key {version_key}")
                elif line.get("version") != expected:
                    mismatches.append(
                        f"{coordinate}: policy {line.get('version')} != catalog {expected}"
                    )
                if subject["subject-kind"] == "plugin":
                    for alias in line["central-aliases"]:
                        plugin = catalog.plugins.get(alias)
                        if plugin is not None and plugin.get("version.ref") != version_key:
                            mismatches.append(
                                f"{coordinate}: policy key {version_key} != "
                                f"plugin {alias} key {plugin.get('version.ref')}"
                            )

        self.assertEqual(mismatches, [])

    def test_aws_crt_is_a_centrally_versioned_direct_constraint(self) -> None:
        repo_root = SCRIPT_PATH.parents[1]
        policy = json.loads(
            (repo_root / "config" / "central-catalog-authority-policy.json").read_text(
                encoding="utf-8"
            )
        )
        aws_crt = next(
            subject
            for subject in policy["subjects"]
            if subject["coordinate-or-plugin-id"]
            == "software.amazon.awssdk.crt:aws-crt"
        )["lines"][0]

        self.assertEqual(aws_crt["disposition"], "central-direct")
        self.assertEqual(aws_crt["version-key"], "aws2-crt")
        self.assertEqual(aws_crt["version"], "0.48.2")
        self.assertEqual(
            aws_crt["evidence"],
            {"path": "gradle/libs.versions.toml", "type": "catalog-alias"},
        )


if __name__ == "__main__":
    unittest.main()
