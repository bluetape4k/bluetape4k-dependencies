from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "promote-catalog-authority.py"
)
SPEC = importlib.util.spec_from_file_location("promote_catalog_authority", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
promote = importlib.util.module_from_spec(SPEC)
sys.modules["promote_catalog_authority"] = promote
SPEC.loader.exec_module(promote)


def _inventory(*records: dict[str, object]) -> list[dict[str, object]]:
    return list(records)


def _record(
    authority_id: str,
    repository: str,
    subject_kind: str,
    coordinate: str,
    alias: str,
    version: str | None,
    *,
    line_id: str = "default",
    declaration_form: str = "catalog",
) -> dict[str, object]:
    return {
        "authority-id": authority_id,
        "line-id": line_id,
        "repository": repository,
        "subject-kind": subject_kind,
        "coordinate-or-plugin-id": coordinate,
        "alias": alias,
        "declared-version": version,
        "declaration-form": declaration_form,
        "source-path": "gradle/libs.versions.toml",
        "source-line": 10,
    }


def _policy(*subjects: dict[str, object]) -> dict[str, object]:
    return {"schema-version": 1, "subjects": list(subjects)}


def _subject(
    kind: str, coordinate: str, *lines: dict[str, object]
) -> dict[str, object]:
    return {
        "subject-kind": kind,
        "coordinate-or-plugin-id": coordinate,
        "lines": list(lines),
    }


def _line(
    line_id: str,
    aliases: list[str],
    occurrences: list[dict[str, str]],
    *,
    version: str | None = "1.2.3",
    version_key: str | None = "alpha",
    disposition: str = "central-direct",
    evidence_type: str = "catalog-alias",
) -> dict[str, object]:
    result: dict[str, object] = {
        "line-id": line_id,
        "central-aliases": aliases,
        "occurrences": occurrences,
        "disposition": disposition,
        "evidence": {"type": evidence_type, "path": "gradle/libs.versions.toml"},
    }
    if version is not None:
        result["version"] = version
    if version_key is not None:
        result["version-key"] = version_key
    return result


class PromoteCatalogAuthorityTest(unittest.TestCase):
    def test_deterministic_render_and_versionless_alias(self) -> None:
        inventory = _inventory(
            _record(
                "a" * 64,
                "repo-a",
                "library",
                "org.example:alpha",
                "alpha-local",
                "1.2.3",
            ),
            _record(
                "b" * 64,
                "repo-b",
                "library",
                "org.example:beta",
                "beta-local",
                None,
            ),
        )
        policy = _policy(
            _subject(
                "library",
                "org.example:alpha",
                _line(
                    "default",
                    ["alpha"],
                    [
                        {
                            "repository": "repo-a",
                            "local-alias": "alpha-local",
                            "central-alias": "alpha",
                        }
                    ],
                ),
            ),
            _subject(
                "library",
                "org.example:beta",
                _line(
                    "default",
                    ["beta"],
                    [
                        {
                            "repository": "repo-b",
                            "local-alias": "beta-local",
                            "central-alias": "beta",
                        }
                    ],
                    version=None,
                    version_key=None,
                ),
            ),
        )
        catalog = (
            "# prefix\n"
            "[versions]\n"
            'existing = "9.9.9"\n'
            "# <shared-version-source-of-truth by scripts/sync-shared-versions.py>\n"
            "# </shared-version-source-of-truth>\n"
            "[plugins]\n"
            'existing = { id = "org.example.existing", version.ref = "existing" }\n'
            "[libraries]\n"
            "# <external-managed-modules by dependency governance>\n"
            "# </external-managed-modules by dependency governance>\n"
        )
        dispositions = {
            "schema-version": 1,
            "records": [
                {
                    "authority-id": "a" * 64,
                    "line-id": "default",
                    "disposition": "central-direct",
                    "evidence": {"type": "catalog-alias", "path": "old"},
                    "owner": "owner",
                    "status": "pending",
                },
                {
                    "authority-id": "b" * 64,
                    "line-id": "default",
                    "disposition": "central-direct",
                    "evidence": {"type": "catalog-alias", "path": "old"},
                    "owner": "owner",
                    "status": "pending",
                },
            ],
        }

        first = promote.build_result(inventory, policy, catalog, dispositions)
        second = promote.build_result(inventory, policy, catalog, dispositions)

        self.assertEqual(first, second)
        self.assertIn('alpha = "1.2.3"', first.catalog)
        self.assertNotIn('beta = "', first.catalog)
        self.assertIn(
            'alpha = { module = "org.example:alpha", version.ref = "alpha" }',
            first.catalog,
        )
        self.assertIn('beta = { module = "org.example:beta" }', first.catalog)
        self.assertEqual(
            [item["authority-id"] for item in first.dispositions["records"]],
            ["a" * 64, "b" * 64],
        )
        self.assertEqual(first.dispositions["records"][0]["central-aliases"], ["alpha"])

    def test_alias_and_version_collision_rejected(self) -> None:
        inventory = _inventory(
            _record("a" * 64, "repo-a", "library", "org.example:alpha", "one", "1.0"),
            _record("b" * 64, "repo-b", "library", "org.example:beta", "two", "2.0"),
        )
        policy = _policy(
            _subject(
                "library",
                "org.example:alpha",
                _line(
                    "default",
                    ["same-alias"],
                    [
                        {
                            "repository": "repo-a",
                            "local-alias": "one",
                            "central-alias": "same-alias",
                        }
                    ],
                    version="1.0",
                    version_key="same-version",
                ),
            ),
            _subject(
                "library",
                "org.example:beta",
                _line(
                    "default",
                    ["same-alias"],
                    [
                        {
                            "repository": "repo-b",
                            "local-alias": "two",
                            "central-alias": "same-alias",
                        }
                    ],
                    version="2.0",
                    version_key="same-version",
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "collision"):
            promote.build_result(
                inventory, policy, "[versions]\n", {"schema-version": 1, "records": []}
            )

    def test_missing_and_orphan_occurrence_mapping_rejected(self) -> None:
        inventory = _inventory(
            _record("a" * 64, "repo-a", "library", "org.example:alpha", "one", "1.0"),
        )
        missing = _policy(
            _subject(
                "library",
                "org.example:alpha",
                _line("default", ["alpha"], []),
            )
        )
        with self.assertRaisesRegex(ValueError, "occurrence"):
            promote.build_result(
                inventory, missing, "[versions]\n", {"schema-version": 1, "records": []}
            )

        orphan = _policy(
            _subject(
                "library",
                "org.example:alpha",
                _line(
                    "default",
                    ["alpha"],
                    [
                        {
                            "repository": "repo-a",
                            "local-alias": "one",
                            "central-alias": "alpha",
                        },
                        {
                            "repository": "repo-b",
                            "local-alias": "orphan",
                            "central-alias": "alpha",
                        },
                    ],
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "orphan"):
            promote.build_result(
                inventory, orphan, "[versions]\n", {"schema-version": 1, "records": []}
            )

    def test_strict_policy_and_existing_version_reuse(self) -> None:
        inventory = _inventory(
            _record(
                "a" * 64,
                "repo-a",
                "library",
                "org.example:alpha",
                "alpha",
                "1.2.3",
            )
        )
        occurrence = {
            "repository": "repo-a",
            "local-alias": "alpha",
            "central-alias": "alpha",
        }
        line = _line("default", ["alpha"], [occurrence])
        subject = _subject("library", "org.example:alpha", line)
        subject["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unexpected policy fields"):
            promote.build_result(
                inventory,
                _policy(subject),
                "[versions]\n",
                {"schema-version": 1, "records": []},
            )

        catalog = (
            "[versions]\n"
            'alpha = "1.2.3"\n'
            "# <shared-version-source-of-truth by "
            "scripts/sync-shared-versions.py>\n"
            "# </shared-version-source-of-truth>\n"
            "[plugins]\n"
            "[libraries]\n"
            "# <external-managed-modules by dependency governance>\n"
            'alpha = { module = "org.example:alpha", version.ref = "alpha" }\n'
            "# </external-managed-modules by dependency governance>\n"
        )
        result = promote.build_result(
            inventory,
            _policy(_subject("library", "org.example:alpha", line)),
            catalog,
            {"schema-version": 1, "records": []},
        )
        self.assertEqual(result.catalog.count('alpha = "1.2.3"'), 1)

        invalid_line = _line(
            "default",
            ["alpha"],
            [occurrence],
            version=None,
            version_key="alpha",
        )
        with self.assertRaisesRegex(ValueError, "versionless"):
            promote.build_result(
                inventory,
                _policy(_subject("library", "org.example:alpha", invalid_line)),
                catalog,
                {"schema-version": 1, "records": []},
            )

    def test_gradle_accessor_alias_grammar_is_fail_closed(self) -> None:
        inventory = _inventory(
            _record(
                "a" * 64,
                "repo-a",
                "library",
                "org.example:alpha",
                "alpha",
                "1.2.3",
            )
        )
        occurrence = {
            "repository": "repo-a",
            "local-alias": "alpha",
            "central-alias": "alpha.bad",
        }
        invalid = _policy(
            _subject(
                "library",
                "org.example:alpha",
                _line("default", ["alpha.bad"], [occurrence]),
            )
        )
        with self.assertRaisesRegex(ValueError, "invalid central alias"):
            promote.build_result(
                inventory,
                invalid,
                "[versions]\n",
                {"schema-version": 1, "records": []},
            )

        reserved = _policy(
            _subject(
                "library",
                "org.example:alpha",
                _line(
                    "default",
                    ["when-value"],
                    [
                        {
                            "repository": "repo-a",
                            "local-alias": "alpha",
                            "central-alias": "when-value",
                        }
                    ],
                    version_key="alpha-version",
                ),
            )
        )
        catalog = (
            "[versions]\n"
            "# <shared-version-source-of-truth by "
            "scripts/sync-shared-versions.py>\n"
            "# </shared-version-source-of-truth>\n"
            "[plugins]\n"
            "[libraries]\n"
            "# <external-managed-modules by dependency governance>\n"
            "# </external-managed-modules by dependency governance>\n"
        )
        with self.assertRaisesRegex(ValueError, "Kotlin reserved word"):
            promote.build_result(
                inventory,
                reserved,
                catalog,
                {"schema-version": 1, "records": []},
            )

    def test_write_is_idempotent_and_check_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_path = root / "inventory.json"
            policy_path = root / "policy.json"
            catalog_path = root / "libs.versions.toml"
            dispositions_path = root / "dispositions.json"
            inventory = _inventory(
                _record(
                    "a" * 64, "repo-a", "plugin", "org.example.plugin", "plug", "1.0"
                ),
            )
            policy = _policy(
                _subject(
                    "plugin",
                    "org.example.plugin",
                    _line(
                        "default",
                        ["plug"],
                        [
                            {
                                "repository": "repo-a",
                                "local-alias": "plug",
                                "central-alias": "plug",
                            }
                        ],
                        version="1.0",
                        version_key="plug",
                    ),
                )
            )
            catalog_path.write_text(
                "[versions]\n"
                "# <shared-version-source-of-truth by "
                "scripts/sync-shared-versions.py>\n"
                "# </shared-version-source-of-truth>\n"
                "[plugins]\n"
                "[libraries]\n"
                "# <external-managed-modules by dependency governance>\n"
                "# </external-managed-modules by dependency governance>\n",
                encoding="utf-8",
            )
            dispositions = {
                "schema-version": 1,
                "records": [
                    {
                        "authority-id": "a" * 64,
                        "line-id": "default",
                        "disposition": "central-direct",
                        "evidence": {"type": "catalog-alias", "path": "old"},
                        "owner": "owner",
                        "status": "pending",
                    }
                ],
            }
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            dispositions_path.write_text(json.dumps(dispositions), encoding="utf-8")

            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--inventory",
                str(inventory_path),
                "--policy",
                str(policy_path),
                "--catalog",
                str(catalog_path),
                "--dispositions",
                str(dispositions_path),
                "--write",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            first_catalog = catalog_path.read_bytes()
            first_dispositions = dispositions_path.read_bytes()
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(first_catalog, catalog_path.read_bytes())
            self.assertEqual(first_dispositions, dispositions_path.read_bytes())

            before_catalog = catalog_path.read_bytes()
            before_dispositions = dispositions_path.read_bytes()
            check = subprocess.run(
                [*command[:-1], "--check"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("OK", check.stdout)
            self.assertEqual(before_catalog, catalog_path.read_bytes())
            self.assertEqual(before_dispositions, dispositions_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
