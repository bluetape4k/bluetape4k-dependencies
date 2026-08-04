from __future__ import annotations

import copy
import importlib.util
import json
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
SELECTOR_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "central-catalog-version-selectors.json"
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
    source_path: str = "gradle/libs.versions.toml",
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
        "source-path": source_path,
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
        policy = {"schema-version": 1, "subjects": []}
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
                'alpha-local = { module = "org.example:alpha", version.ref = "alpha-local" }\n'
                'alpha-local-client = { module = "org.example:alpha-client" }\n',
                encoding="utf-8",
            )
            build = root / "build.gradle.kts"
            build.write_text(
                "plugins { alias(libs.plugins.plug.local) }\n"
                "dependencies { implementation(libs.alpha.local) }\n"
                "dependencies { implementation(libs.alpha.local.client) }\n"
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
            self.assertIn("libs.alpha.local.client", build.read_text(encoding="utf-8"))
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
            record = _record(
                "a" * 64,
                declaration_form="hard-coded",
                source_line=1,
                source_path="build.gradle.kts",
            )
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

    def test_replaced_hard_coded_candidate_is_not_a_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text("[versions]\n[plugins]\n[libraries]\n", encoding="utf-8")
            (root / "build.gradle.kts").write_text(
                "dependencies { implementation(bt4k.alpha) }\n", encoding="utf-8"
            )
            plan = migrate.plan_repository(
                "bluetape4k-projects",
                root,
                catalog,
                [
                    _record(
                        "a" * 64,
                        declaration_form="hard-coded",
                        source_line=1,
                        source_path="build.gradle.kts",
                    )
                ],
                _policy(),
                _dispositions("a" * 64, ["alpha"]),
                migrate.CentralAliases(
                    libraries={"alpha"}, plugins=set(), versions={"alpha"}
                ),
            )
            self.assertEqual(plan.blockers, ())

    def test_shifted_bt4k_adoption_is_not_a_blocker(self) -> None:
        for adoption in (
            "dependencies { implementation(bt4k.alpha) }",
            "val alphaVersion = bt4k.versions.alpha.get()",
            'val alphaVersion = bt4kVersion("alpha")',
        ):
            with self.subTest(adoption=adoption), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                (root / "gradle").mkdir()
                catalog = root / "gradle/libs.versions.toml"
                catalog.write_text(
                    "[versions]\n[plugins]\n[libraries]\n", encoding="utf-8"
                )
                (root / "build.gradle.kts").write_text(
                    "val insertedByEarlierMigration = true\n"
                    f"{adoption}\n",
                    encoding="utf-8",
                )
                plan = migrate.plan_repository(
                    "bluetape4k-projects",
                    root,
                    catalog,
                    [
                        _record(
                            "a" * 64,
                            declaration_form="hard-coded",
                            source_line=1,
                            source_path="build.gradle.kts",
                        )
                    ],
                    _policy(),
                    _dispositions("a" * 64, ["alpha"]),
                    migrate.CentralAliases(
                        libraries={"alpha"}, plugins=set(), versions={"alpha"}
                    ),
                )
                self.assertEqual(plan.blockers, ())

    def test_shifted_bt4k_adoption_with_residual_literal_still_blocks(self) -> None:
        for residual, expected in (
            ('implementation("org.example:alpha:1.2.3")', "requires manual migration"),
            ('implementation("org.example:alpha:9.9.9")', "changed without catalog adoption"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                (root / "gradle").mkdir()
                catalog = root / "gradle/libs.versions.toml"
                catalog.write_text(
                    "[versions]\n[plugins]\n[libraries]\n", encoding="utf-8"
                )
                (root / "build.gradle.kts").write_text(
                    "val insertedByEarlierMigration = true\n"
                    "dependencies { implementation(bt4k.alpha) }\n"
                    f"dependencies {{ {residual} }}\n",
                    encoding="utf-8",
                )
                plan = migrate.plan_repository(
                    "bluetape4k-projects",
                    root,
                    catalog,
                    [
                        _record(
                            "a" * 64,
                            declaration_form="hard-coded",
                            source_line=1,
                            source_path="build.gradle.kts",
                        )
                    ],
                    _policy(),
                    _dispositions("a" * 64, ["alpha"]),
                    migrate.CentralAliases(
                        libraries={"alpha"}, plugins=set(), versions={"alpha"}
                    ),
                )
                self.assertEqual(len(plan.blockers), 1)
                self.assertIn(expected, plan.blockers[0])

    def test_changed_or_unclassifiable_hard_coded_candidate_fails_closed(self) -> None:
        for source, expected in (
            (
                'dependencies { implementation("org.example:alpha:9.9.9") }\n',
                "changed without catalog adoption",
            ),
            (
                'dependencies { implementation("org.other:beta:1.0.0") }\n',
                "unmanaged literal",
            ),
            ("dependencies { implementation(localDependency) }\n", "cannot be safely classified"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                (root / "gradle").mkdir()
                catalog = root / "gradle/libs.versions.toml"
                catalog.write_text(
                    "[versions]\n[plugins]\n[libraries]\n", encoding="utf-8"
                )
                (root / "build.gradle.kts").write_text(source, encoding="utf-8")
                plan = migrate.plan_repository(
                    "bluetape4k-projects",
                    root,
                    catalog,
                    [
                        _record(
                            "a" * 64,
                            declaration_form="hard-coded",
                            source_line=1,
                            source_path="build.gradle.kts",
                        )
                    ],
                    _policy(),
                    _dispositions("a" * 64, ["alpha"]),
                    migrate.CentralAliases(
                        libraries={"alpha"}, plugins=set(), versions={"alpha"}
                    ),
                )
                self.assertEqual(len(plan.blockers), 1)
                self.assertIn(expected, plan.blockers[0])

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

    def test_policy_validation_matches_canonical_promoter(self) -> None:
        for missing in ("disposition", "evidence", "version", "version-key"):
            policy = copy.deepcopy(_policy())
            del policy["subjects"][0]["lines"][0][missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(
                migrate.MigrationError, "invalid policy"
            ):
                migrate._validate_policy(policy)
        empty_occurrences = copy.deepcopy(_policy())
        empty_occurrences["subjects"][0]["lines"][0]["occurrences"] = []
        with self.assertRaisesRegex(migrate.MigrationError, "invalid policy"):
            migrate._validate_policy(empty_occurrences)

    def test_version_selector_config_and_unknown_repositories_fail_closed(self) -> None:
        aliases = migrate._central_aliases(
            Path(__file__).resolve().parents[1] / "gradle/libs.versions.toml"
        )
        selector_document = json.loads(SELECTOR_CONFIG.read_text(encoding="utf-8"))
        selectors = migrate._validate_version_selectors(
            selector_document,
            aliases.versions,
            allowed_repositories={
                "bluetape4k-projects",
                "bluetape4k-exposed",
                "bluetape4k-image",
                "bluetape4k-leader",
                "bluetape4k-text",
            },
        )
        self.assertEqual(
            set(selectors),
            {
                ("bluetape4k-projects", "grpc-kotlin"),
                ("bluetape4k-projects", "jmh"),
                ("bluetape4k-exposed", "jmh"),
                ("bluetape4k-image", "jmh"),
                ("bluetape4k-image", "zxing"),
                ("bluetape4k-leader", "mongo-driver"),
                ("bluetape4k-text", "jmh"),
            },
        )
        invalid = copy.deepcopy(selector_document)
        invalid["selectors"][0]["repository"] = "bluetape4k-unknown"
        with self.assertRaisesRegex(migrate.MigrationError, "managed selected"):
            migrate._validate_version_selectors(
                invalid,
                aliases.versions,
                allowed_repositories={"bluetape4k-projects"},
            )

    def test_apply_plan_preflights_every_target_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            first = root / "first.txt"
            first.write_text("before", encoding="utf-8")
            missing = root / "missing.txt"
            plan = migrate.MigrationPlan(
                repository="bluetape4k-projects",
                root=root,
                catalog=first,
                edits={first: "after", missing: "never"},
                replacements=(),
                removed_aliases=(),
                removed_versions=(),
                blockers=(),
                structural_preserved=(),
            )
            with self.assertRaisesRegex(migrate.MigrationError, "regular file"):
                migrate.apply_plan(plan)
            self.assertEqual(first.read_text(encoding="utf-8"), "before")

    def test_repository_map_requires_explicit_absolute_workspace(self) -> None:
        with self.assertRaisesRegex(migrate.MigrationError, "workspace"):
            migrate._load_repository_map(REPOSITORY_MAP_FIXTURE, Path("relative"))

    def test_accessor_presence_uses_exact_token_boundaries(self) -> None:
        self.assertTrue(
            migrate._contains_accessor(
                "val v = libs.versions.alpha.local.get()",
                "libs.versions.alpha.local",
            )
        )
        self.assertFalse(
            migrate._contains_accessor(
                "val v = libs.versions.alpha.local.client.get()",
                "libs.versions.alpha.local",
            )
        )
        self.assertFalse(
            migrate._contains_accessor(
                "val v = other.libs.versions.alpha.local",
                "libs.versions.alpha.local",
            )
        )

    def test_rootlibs_accessors_migrate_with_exact_prefix_boundaries(self) -> None:
        updated, replacements, blockers = migrate._replace_tokens(
            "implementation(rootLibs.alpha.local)\n"
            "alias(rootLibs.plugins.plug.local)\n"
            "val v = rootLibs.versions.alpha.local.get()\n"
            "val untouched = myrootLibs.alpha.local\n",
            {
                ("library", "alpha-local"): "bt4k.alpha",
                ("plugin", "plug-local"): "bt4k.plugins.plug",
                ("version", "alpha-local"): "bt4k.versions.alpha",
            },
            path=Path("build.gradle.kts"),
        )
        self.assertEqual(blockers, [])
        self.assertEqual(len(replacements), 3)
        self.assertIn("implementation(rootBt4k.alpha)", updated)
        self.assertIn("alias(rootBt4k.plugins.plug)", updated)
        self.assertIn("rootBt4k.versions.alpha.get()", updated)
        self.assertIn("myrootLibs.alpha.local", updated)

    def test_catalog_accessor_presence_covers_rootlibs(self) -> None:
        self.assertTrue(
            migrate._contains_catalog_accessor(
                "val v = rootLibs.versions.alpha.local.get()",
                "libs.versions.alpha.local",
            )
        )
        self.assertFalse(
            migrate._contains_catalog_accessor(
                "val v = myrootLibs.versions.alpha.local.get()",
                "libs.versions.alpha.local",
            )
        )

    def test_central_accessor_normalizes_provider_nodes(self) -> None:
        self.assertEqual(
            migrate._central_accessor(
                "library", "logback", {"logback", "logback-core"}
            ),
            "bt4k.logback.asProvider()",
        )
        self.assertEqual(
            migrate._central_accessor(
                "library", "jakarta-persistence-v31", {"jakarta-persistence-v31"}
            ),
            "bt4k.jakarta.persistence.v31",
        )
        updated, replacements, blockers = migrate._replace_tokens(
            "rootLibs.logback.get()\n"
            "rootLibs.jakarta.persistence.v31.asProvider().get()\n",
            {
                ("library", "logback"): "bt4k.logback.asProvider()",
                (
                    "library",
                    "jakarta-persistence-v31",
                ): "bt4k.jakarta.persistence.v31",
            },
            path=Path("build.gradle.kts"),
        )
        self.assertEqual(blockers, [])
        self.assertEqual(len(replacements), 2)
        self.assertIn("rootBt4k.logback.asProvider().get()", updated)
        self.assertIn("rootBt4k.jakarta.persistence.v31.get()", updated)
        self.assertNotIn("persistence.v31.asProvider()", updated)

    def test_root_bt4k_capture_is_inserted_once(self) -> None:
        source = "val rootLibs = libs\nsubprojects {}\n"
        migrated = migrate._ensure_root_bt4k_capture(source)
        self.assertEqual(migrated.count("val rootBt4k = bt4k"), 1)
        self.assertEqual(migrate._ensure_root_bt4k_capture(migrated), migrated)

    def test_ambiguous_shared_version_keeps_all_catalog_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text(
                "[versions]\n"
                'shared = "1.2.3"\n'
                "[plugins]\n"
                "[libraries]\n"
                'alpha-local = { module = "org.example:alpha", version.ref = "shared" }\n'
                'beta-local = { module = "org.example:beta", version.ref = "shared" }\n',
                encoding="utf-8",
            )
            (root / "build.gradle.kts").write_text(
                "val shared = libs.versions.shared.get()\n", encoding="utf-8"
            )
            inventory = [
                _record("a" * 64, alias="alpha-local", source_line=5),
                _record(
                    "b" * 64,
                    coordinate="org.example:beta",
                    alias="beta-local",
                    source_line=6,
                ),
            ]
            policy = {
                "schema-version": 1,
                "subjects": [
                    _policy(central_alias="alpha")["subjects"][0],
                    _policy(
                        coordinate="org.example:beta",
                        local_alias="beta-local",
                        central_alias="beta",
                    )["subjects"][0],
                ],
            }
            policy["subjects"][0]["lines"][0]["version-key"] = "central-alpha"
            policy["subjects"][1]["lines"][0]["version-key"] = "central-beta"
            dispositions = {
                "schema-version": 1,
                "records": [
                    _dispositions("a" * 64, ["alpha"])["records"][0],
                    _dispositions("b" * 64, ["beta"])["records"][0],
                ],
            }
            plan = migrate.plan_repository(
                "bluetape4k-projects",
                root,
                catalog,
                inventory,
                policy,
                dispositions,
                migrate.CentralAliases(
                    libraries={"alpha", "beta"},
                    plugins=set(),
                    versions={"central-alpha", "central-beta"},
                ),
            )
            self.assertEqual(plan.removed_aliases, ())
            self.assertTrue(
                any("ambiguous local version" in blocker for blocker in plan.blockers)
            )

    def test_explicit_version_selector_rewrites_only_selected_accessor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text(
                "[versions]\n"
                'shared = "1.2.3"\n'
                "[plugins]\n"
                "[libraries]\n"
                'alpha-local = { module = "org.example:alpha", version.ref = "shared" }\n'
                'beta-local = { module = "org.example:beta", version.ref = "shared" }\n',
                encoding="utf-8",
            )
            build = root / "build.gradle.kts"
            build.write_text(
                "val shared = libs.versions.shared.get()\n",
                encoding="utf-8",
            )
            inventory = [
                _record("a" * 64, alias="alpha-local", source_line=5),
                _record(
                    "b" * 64,
                    coordinate="org.example:beta",
                    alias="beta-local",
                    source_line=6,
                ),
            ]
            policy = {
                "schema-version": 1,
                "subjects": [
                    _policy(central_alias="alpha")["subjects"][0],
                    _policy(
                        coordinate="org.example:beta",
                        local_alias="beta-local",
                        central_alias="beta",
                    )["subjects"][0],
                ],
            }
            policy["subjects"][0]["lines"][0]["version-key"] = "central-alpha"
            policy["subjects"][1]["lines"][0]["version-key"] = "central-beta"
            dispositions = {
                "schema-version": 1,
                "records": [
                    _dispositions("a" * 64, ["alpha"])["records"][0],
                    _dispositions("b" * 64, ["beta"])["records"][0],
                ],
            }
            plan = migrate.plan_repository(
                "bluetape4k-projects",
                root,
                catalog,
                inventory,
                policy,
                dispositions,
                migrate.CentralAliases(
                    libraries={"alpha", "beta"},
                    plugins=set(),
                    versions={"central-alpha", "central-beta"},
                    version_values={
                        "central-alpha": "1.2.3",
                        "central-beta": "1.2.3",
                    },
                ),
                version_selectors={("bluetape4k-projects", "shared"): "central-alpha"},
            )
            self.assertEqual(plan.blockers, ())
            self.assertEqual(plan.removed_aliases, ("alpha-local", "beta-local"))
            self.assertEqual(plan.removed_versions, ("shared",))
            self.assertTrue(
                any(
                    replacement.before == "libs.versions.shared.get"
                    and replacement.after == "bt4k.versions.central.alpha.get"
                    for replacement in plan.replacements
                )
            )
            migrate.apply_plan(plan)
            idempotent = migrate.plan_repository(
                "bluetape4k-projects",
                root,
                catalog,
                inventory,
                policy,
                dispositions,
                migrate.CentralAliases(
                    libraries={"alpha", "beta"},
                    plugins=set(),
                    versions={"central-alpha", "central-beta"},
                    version_values={
                        "central-alpha": "1.2.3",
                        "central-beta": "1.2.3",
                    },
                ),
                version_selectors={},
            )
            self.assertFalse(idempotent.changed)
            self.assertEqual(idempotent.blockers, ())

    def test_ambiguous_selector_requires_equal_central_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text(
                "[versions]\n"
                'shared = "1.2.3"\n'
                "[plugins]\n"
                "[libraries]\n"
                'alpha-local = { module = "org.example:alpha", version.ref = "shared" }\n'
                'beta-local = { module = "org.example:beta", version.ref = "shared" }\n',
                encoding="utf-8",
            )
            (root / "build.gradle.kts").write_text(
                "val shared = libs.versions.shared.get()\n", encoding="utf-8"
            )
            inventory = [
                _record("a" * 64, alias="alpha-local", source_line=5),
                _record(
                    "b" * 64,
                    coordinate="org.example:beta",
                    alias="beta-local",
                    source_line=6,
                ),
            ]
            policy = {
                "schema-version": 1,
                "subjects": [
                    _policy(central_alias="alpha")["subjects"][0],
                    _policy(
                        coordinate="org.example:beta",
                        local_alias="beta-local",
                        central_alias="beta",
                    )["subjects"][0],
                ],
            }
            policy["subjects"][0]["lines"][0]["version-key"] = "central-alpha"
            policy["subjects"][1]["lines"][0]["version-key"] = "central-beta"
            dispositions = {
                "schema-version": 1,
                "records": [
                    _dispositions("a" * 64, ["alpha"])["records"][0],
                    _dispositions("b" * 64, ["beta"])["records"][0],
                ],
            }
            aliases = migrate.CentralAliases(
                libraries={"alpha", "beta"},
                plugins=set(),
                versions={"central-alpha", "central-beta"},
                version_values={
                    "central-alpha": "1.2.3",
                    "central-beta": "2.0.0",
                },
            )
            with self.assertRaisesRegex(migrate.MigrationError, "values differ"):
                migrate.plan_repository(
                    "bluetape4k-projects",
                    root,
                    catalog,
                    inventory,
                    policy,
                    dispositions,
                    aliases,
                    version_selectors={
                        ("bluetape4k-projects", "shared"): "central-alpha"
                    },
                )

    def test_orphan_selector_local_key_is_rejected_by_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "gradle").mkdir()
            catalog = root / "gradle/libs.versions.toml"
            catalog.write_text(
                "[versions]\n"
                'alpha-local = "1.2.3"\n'
                "[plugins]\n[libraries]\n"
                'alpha-local = { module = "org.example:alpha", version.ref = "alpha-local" }\n',
                encoding="utf-8",
            )
            (root / "build.gradle.kts").write_text(
                "dependencies { implementation(libs.alpha.local) }\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(migrate.MigrationError, "orphan"):
                migrate.plan_repository(
                    "bluetape4k-projects",
                    root,
                    catalog,
                    [_record("a" * 64, source_line=5)],
                    _policy(),
                    _dispositions("a" * 64, ["alpha"]),
                    migrate.CentralAliases(
                        libraries={"alpha"},
                        plugins=set(),
                        versions={"alpha"},
                        version_values={"alpha": "1.2.3"},
                    ),
                    version_selectors={
                        ("bluetape4k-projects", "missing"): "alpha"
                    },
                )


if __name__ == "__main__":
    unittest.main()
