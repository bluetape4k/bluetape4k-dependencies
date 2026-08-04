from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "migrate-catalog-authority.py"
)
REPOSITORY_MAP_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "catalog-candidate"
    / "repository-map-valid.json"
)
SPEC = importlib.util.spec_from_file_location("migrate_catalog_authority", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
migrate = importlib.util.module_from_spec(SPEC)
sys.modules["migrate_catalog_authority"] = migrate


def _record(
    authority_id: str,
    *,
    repository: str = "bluetape4k-projects",
    subject_kind: str = "library",
    coordinate: str = "org.example:alpha",
    alias: str = "alpha-local",
    line_id: str = "default",
    source_line: int = 5,
    declaration_form: str = "catalog",
) -> dict[str, object]:
    return {
        "alias": alias,
        "authority-id": authority_id,
        "coordinate-or-plugin-id": coordinate,
        "declaration-form": declaration_form,
        "declared-version": "1.2.3",
        "disposition": None,
        "evidence": None,
        "line-id": line_id,
        "occurrence-id": "b" * 64,
        "owner": None,
        "repository": repository,
        "repository-count": 1,
        "resolved-version": None,
        "source-line": source_line,
        "source-path": "gradle/libs.versions.toml",
        "subject-kind": subject_kind,
    }


def _policy(
    *,
    coordinate: str = "org.example:alpha",
    subject_kind: str = "library",
    local_alias: str = "alpha-local",
    central_alias: str = "alpha",
    line_id: str = "default",
    occurrences: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "schema-version": 1,
        "subjects": [
            {
                "coordinate-or-plugin-id": coordinate,
                "lines": [
                    {
                        "central-aliases": [central_alias],
                        "disposition": "central-direct",
                        "evidence": {"path": "catalog", "type": "catalog-alias"},
                        "line-id": line_id,
                        "occurrences": occurrences
                        if occurrences is not None
                        else [
                            {
                                "central-alias": central_alias,
                                "local-alias": local_alias,
                                "repository": "bluetape4k-projects",
                            }
                        ],
                        "version": "1.2.3",
                        "version-key": "alpha",
                    }
                ],
                "subject-kind": subject_kind,
            }
        ],
    }


def _dispositions(authority_id: str, aliases: list[str]) -> dict[str, object]:
    return {
        "schema-version": 1,
        "records": [
            {
                "authority-id": authority_id,
                "central-aliases": aliases,
                "disposition": "central-direct",
                "evidence": {"path": "catalog", "type": "catalog-alias"},
                "line-id": "default",
                "owner": "test",
                "status": "pending",
            }
        ],
    }


def _central_catalog() -> str:
    return (
        "[versions]\n"
        'alpha = "1.2.3"\n'
        'unused = "9.9.9"\n'
        "[plugins]\n"
        "[libraries]\n"
        'alpha = { module = "org.example:alpha", version.ref = "alpha" }\n'
        'unused = { module = "org.example:unused", version.ref = "unused" }\n'
    )


class MigrateCatalogAuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        SPEC.loader.exec_module(migrate)

    def test_explicit_occurrence_precedes_same_alias_fallback(self) -> None:
        inventory = [_record("a" * 64)]
        policy = _policy(
            occurrences=[
                {
                    "central-alias": "alpha",
                    "local-alias": "alpha-local",
                    "repository": "bluetape4k-projects",
                }
            ]
        )
        mapping = migrate.derive_catalog_mappings(
            inventory,
            policy,
            _dispositions("a" * 64, ["alpha", "other"]),
            {"alpha"},
            set(),
            {"alpha"},
        )
        self.assertEqual(mapping[0].central_alias, "alpha")

    def test_fallback_requires_one_same_alias_and_rejects_ambiguity(self) -> None:
        record = _record("a" * 64, alias="other-local")
        policy = _policy(occurrences=[])
        with self.assertRaisesRegex(migrate.MigrationError, "ambiguous"):
            migrate.derive_catalog_mappings(
                [record],
                policy,
                _dispositions("a" * 64, ["alpha-local", "other"]),
                {"alpha-local", "other"},
                set(),
                {"alpha"},
            )

    def test_plan_replaces_accessors_removes_catalog_lines_and_keeps_settings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            gradle = root / "gradle"
            gradle.mkdir()
            catalog = gradle / "libs.versions.toml"
            catalog.write_text(
                "[versions]\n"
                'alpha-local = "1.2.3"\n'
                'unused = "9.9.9"\n'
                "[plugins]\n"
                'plug-local = { id = "org.example.plugin", version.ref = "alpha-local" }\n'
                "[libraries]\n"
                'alpha-local = { module = "org.example:alpha", version.ref = "alpha-local" }\n',
                encoding="utf-8",
            )
            build = root / "build.gradle.kts"
            build.write_text(
                "plugins { alias(libs.plugins.plug.local) }\n"
                "dependencies { implementation(libs.alpha.local) }\n"
                "val v = libs.versions.alpha.local.get()\n",
                encoding="utf-8",
            )
            settings = root / "settings.gradle.kts"
            settings.write_text(
                'id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"\n',
                encoding="utf-8",
            )
            records = [
                _record("a" * 64, alias="alpha-local", source_line=7),
                _record(
                    "b" * 64,
                    subject_kind="plugin",
                    coordinate="org.example.plugin",
                    alias="plug-local",
                    source_line=5,
                ),
            ]
            policy = {
                "schema-version": 1,
                "subjects": [
                    _policy()["subjects"][0],
                    _policy(
                        subject_kind="plugin",
                        coordinate="org.example.plugin",
                        local_alias="plug-local",
                        central_alias="plug",
                    )["subjects"][0],
                ],
            }
            dispositions = {
                "schema-version": 1,
                "records": [
                    _dispositions("a" * 64, ["alpha"])["records"][0],
                    {
                        **_dispositions("b" * 64, ["plug"])["records"][0],
                        "central-aliases": ["plug"],
                    },
                ],
            }
            plan = migrate.plan_repository(
                "bluetape4k-projects",
                root,
                catalog,
                records,
                policy,
                dispositions,
                migrate.CentralAliases(
                    libraries={"alpha"}, plugins={"plug"}, versions={"alpha"}
                ),
            )
            self.assertEqual(plan.replacements_count, 3)
            self.assertEqual(plan.removed_aliases, ("alpha-local", "plug-local"))
            self.assertEqual(plan.removed_versions, ("alpha-local",))
            self.assertEqual(plan.structural_preserved, ())
            migrate.apply_plan(plan)
            self.assertIn("bt4k.plugins.plug", build.read_text(encoding="utf-8"))
            self.assertIn("bt4k.alpha", build.read_text(encoding="utf-8"))
            self.assertIn(
                "bt4k.versions.alpha.get()", build.read_text(encoding="utf-8")
            )
            self.assertIn("foojay", settings.read_text(encoding="utf-8"))
            self.assertNotIn("alpha-local =", catalog.read_text(encoding="utf-8"))

    def test_hard_coded_candidate_is_an_explicit_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text("[versions]\n[plugins]\n[libraries]\n", encoding="utf-8")
            build = root / "build.gradle.kts"
            build.write_text(
                'dependencies { implementation("org.example:alpha:1.2.3") }\n',
                encoding="utf-8",
            )
            record = _record("a" * 64, declaration_form="hard-coded", source_line=1)
            plan = migrate.plan_repository(
                "bluetape4k-projects",
                root,
                catalog,
                [record],
                _policy(),
                _dispositions("a" * 64, ["alpha"]),
                migrate.CentralAliases(
                    libraries={"alpha"}, plugins=set(), versions={"alpha"}
                ),
            )
            self.assertEqual(len(plan.blockers), 1)
            self.assertIn("hard-coded", plan.blockers[0])
            with self.assertRaisesRegex(migrate.MigrationError, "blockers"):
                migrate.apply_plan(plan)

    def test_unknown_accessor_and_invalid_inputs_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text("[versions]\n[plugins]\n[libraries]\n", encoding="utf-8")
            (root / "build.gradle.kts").write_text(
                "dependencies { implementation(libs.alpha) }\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(migrate.MigrationError, "unknown|missing"):
                migrate.plan_repository(
                    "bluetape4k-projects",
                    root,
                    catalog,
                    [_record("a" * 64)],
                    _policy(),
                    _dispositions("b" * 64, ["alpha"]),
                    migrate.CentralAliases(
                        libraries={"alpha"}, plugins=set(), versions=set()
                    ),
                )

    def test_repository_map_requires_explicit_absolute_workspace(self) -> None:
        with self.assertRaisesRegex(migrate.MigrationError, "workspace"):
            migrate._load_repository_map(REPOSITORY_MAP_FIXTURE, Path("relative"))


if __name__ == "__main__":
    unittest.main()
