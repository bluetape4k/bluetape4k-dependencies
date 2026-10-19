from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import stat
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "project-dependabot-catalog"
SCRIPT_PATH = ROOT / "scripts" / "project-dependabot-catalog.py"
SPEC = importlib.util.spec_from_file_location("project_dependabot_catalog", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load generator module at {SCRIPT_PATH}")
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


class ProjectDependabotCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_catalog = (FIXTURES / "projects.versions.toml").read_bytes()
        cls.allowlist = (FIXTURES / "projects.allowlist.json").read_bytes()
        cls.central_catalog = (FIXTURES / "central.versions.toml").read_bytes()
        cls.mapping = (FIXTURES / "mapping.toml").read_bytes()
        cls.allowlist_data = json.loads(cls.allowlist)
        cls.mapping_data = tomllib.loads(cls.mapping.decode("utf-8"))

    def render(
        self,
        project_catalog: bytes | None = None,
        allowlist: bytes | None = None,
        central_catalog: bytes | None = None,
        mapping: bytes | None = None,
    ) -> bytes:
        return generator.render_catalog(
            project_catalog or self.project_catalog,
            allowlist or self.allowlist,
            central_catalog or self.central_catalog,
            mapping or self.mapping,
        )

    def test_fixture_has_the_closed_projects_library_allowlist(self) -> None:
        self.assertEqual(self.allowlist_data["schema_version"], 1)
        self.assertEqual(len(self.allowlist_data["libraries"]), 303)
        self.assertEqual(self.allowlist_data["plugins"], [])
        self.assertEqual(self.allowlist_data["bundles"], [])
        self.assertEqual(
            [entry["alias"] for entry in self.allowlist_data["libraries"]],
            sorted(entry["alias"] for entry in self.allowlist_data["libraries"]),
        )

    def test_central_mapping_matches_the_reviewed_fixture(self) -> None:
        self.assertEqual(
            (ROOT / "config" / "projects-dependabot-catalog.toml").read_bytes(),
            self.mapping,
        )
        with (FIXTURES / "repository-map-v1.json").open(encoding="utf-8") as stream:
            repository_map_v1 = json.load(stream)
        with (FIXTURES / "repository-map-v2.json").open(encoding="utf-8") as stream:
            repository_map_v2 = json.load(stream)
        self.assertEqual(repository_map_v1["schema_version"], 1)
        self.assertEqual(repository_map_v2["schema_version"], 2)
        self.assertEqual(
            repository_map_v2["repositories"]["projects"]["authority_catalog"],
            "/workspace/bluetape4k-projects/gradle/libs.project.versions.toml",
        )

    def test_projection_materializes_the_ten_mapped_coordinates(self) -> None:
        generated = tomllib.loads(self.render().decode("utf-8"))
        central = tomllib.loads(self.central_catalog.decode("utf-8"))
        mapping = self.mapping_data["projection"]

        self.assertEqual(len(mapping), 10)
        self.assertEqual(
            [
                (
                    item["alias"],
                    item["module"],
                    item["source_type"],
                    item["source_name"],
                    item["version_key"],
                )
                for item in mapping
            ],
            [
                (
                    "jackson-core",
                    "com.fasterxml.jackson.core:jackson-core",
                    "version",
                    "jackson2",
                    "dependabot-jackson2",
                ),
                (
                    "jackson-databind",
                    "com.fasterxml.jackson.core:jackson-databind",
                    "version",
                    "jackson2",
                    "dependabot-jackson2",
                ),
                (
                    "amqp-client",
                    "com.rabbitmq:amqp-client",
                    "library",
                    "amqp-client",
                    "dependabot-amqp-client",
                ),
                (
                    "netty-handler",
                    "io.netty:netty-handler",
                    "version",
                    "netty",
                    "dependabot-netty",
                ),
                (
                    "bouncycastle-bcprov",
                    "org.bouncycastle:bcprov-jdk18on",
                    "library",
                    "bouncycastle-bcprov",
                    "dependabot-bouncycastle-bcprov",
                ),
                (
                    "bouncycastle-bcprov-lts8on",
                    "org.bouncycastle:bcprov-lts8on",
                    "library",
                    "bouncycastle-bcprov-lts8on",
                    "dependabot-bouncycastle-bcprov-lts8on",
                ),
                (
                    "freemarker",
                    "org.freemarker:freemarker",
                    "library",
                    "freemarker",
                    "dependabot-freemarker",
                ),
                ("jsoup", "org.jsoup:jsoup", "library", "jsoup", "dependabot-jsoup"),
                (
                    "jackson3-core",
                    "tools.jackson.core:jackson-core",
                    "version",
                    "jackson3",
                    "dependabot-jackson3",
                ),
                (
                    "jackson3-databind",
                    "tools.jackson.core:jackson-databind",
                    "version",
                    "jackson3",
                    "dependabot-jackson3",
                ),
            ],
        )
        versioned = {
            alias: entry
            for alias, entry in generated["libraries"].items()
            if "version" in entry
        }
        self.assertEqual(set(versioned), {entry["alias"] for entry in mapping})

        for entry in mapping:
            with self.subTest(alias=entry["alias"]):
                projected = generated["libraries"][entry["alias"]]
                self.assertEqual(projected["module"], entry["module"])
                self.assertEqual(projected["version"]["ref"], entry["version_key"])
                self.assertEqual(
                    generated["versions"][entry["version_key"]],
                    self.central_version(entry, central),
                )

    def test_projection_preserves_unmapped_alias_bytes_and_order(self) -> None:
        generated = self.render()
        self.assertEqual(generated, self.render())

        def preserved_lines(catalog: bytes) -> list[bytes]:
            section = b""
            preserved = []
            for line in catalog.splitlines(keepends=True):
                section_match = re.match(rb"\s*\[([^]]+)\]", line)
                if section_match:
                    section = section_match.group(1)
                alias_match = re.match(rb"^([A-Za-z0-9_.-]+)\s*=", line)
                alias = alias_match.group(1).decode() if alias_match else ""
                if section == b"versions" and alias.startswith("dependabot-"):
                    continue
                if section == b"libraries" and alias in self.target_aliases:
                    continue
                preserved.append(line)
            return preserved

        self.assertEqual(
            preserved_lines(generated), preserved_lines(self.project_catalog)
        )
        original = tomllib.loads(self.project_catalog.decode("utf-8"))
        projected = tomllib.loads(generated.decode("utf-8"))
        self.assertEqual(
            set(projected["libraries"]),
            set(original["libraries"])
            | {
                entry["alias"]
                for entry in self.mapping_data["projection"]
                if entry["alias"] not in original["libraries"]
            },
        )
        self.assertEqual(
            set(projected["versions"]),
            set(original["versions"])
            | {entry["version_key"] for entry in self.mapping_data["projection"]},
        )

    def test_generated_fixture_matches_the_projection(self) -> None:
        self.assertEqual(
            (FIXTURES / "generated.versions.toml").read_bytes(), self.render()
        )

    def test_rejects_versioned_source_alias(self) -> None:
        for version_field in (b'version = "2.0.0"', b'version.ref = "jackson2"'):
            with self.subTest(version_field=version_field):
                versioned = re.sub(
                    rb'(?m)^(jackson-core\s*=\s*\{\s*module\s*=\s*"[^"]+")\s*\}',
                    rb"\1, " + version_field + b" }",
                    self.project_catalog,
                    count=1,
                )
                self.assertNotEqual(versioned, self.project_catalog)
                with self.assertRaisesRegex(ValueError, "version"):
                    self.render(versioned)

    def test_rejects_central_module_mismatch(self) -> None:
        central = self.central_catalog.replace(
            b'module = "com.rabbitmq:amqp-client"',
            b'module = "com.rabbitmq:wrong-client"',
        )
        with self.assertRaisesRegex(ValueError, "module"):
            self.render(central_catalog=central)

    def test_rejects_dynamic_rich_and_unresolved_central_versions(self) -> None:
        cases = (
            self.central_catalog.replace(
                b'managed-amqp-client-h639dbc3b57d0 = "5.37.0"',
                b'managed-amqp-client-h639dbc3b57d0 = "5.+"',
            ),
            self.central_catalog.replace(
                b'version.ref = "managed-amqp-client-h639dbc3b57d0"',
                b'version = { prefer = "5.37.0" }',
            ),
            self.central_catalog.replace(
                b'version.ref = "managed-amqp-client-h639dbc3b57d0"',
                b'version.ref = "missing-version-key"',
            ),
        )
        for central in cases:
            with (
                self.subTest(central_sha256=hashlib.sha256(central).hexdigest()),
                self.assertRaises(ValueError),
            ):
                self.render(central_catalog=central)

    def test_rejects_mapping_alias_gav_and_normalization_collisions(self) -> None:
        duplicate_alias = self.mapping.replace(
            b'alias = "jackson3-core"', b'alias = "jackson-core"'
        )
        with self.assertRaisesRegex(ValueError, "duplicate alias or GAV"):
            self.render(mapping=duplicate_alias)

        normalized_collision = self.mapping.replace(
            b'alias = "jackson3-core"', b'alias = "jackson3_core"'
        )
        with self.assertRaisesRegex(ValueError, "collision"):
            self.render(mapping=normalized_collision)

    def test_rejects_multiline_target_declaration(self) -> None:
        multiline = (
            self.project_catalog.replace(
                b'jackson-core = { module = "com.fasterxml.jackson.core:jackson-core" }',
                b"",
            )
            + b'\n[libraries.jackson-core]\nmodule = "com.fasterxml.jackson.core:jackson-core"\n'
        )
        with self.assertRaisesRegex(ValueError, "byte-preservingly"):
            self.render(multiline)

    def test_rejects_plugins_and_bundles_in_closed_allowlist(self) -> None:
        plugin_allowlist = self.allowlist.replace(
            b'"plugins": []', b'"plugins": [{"alias": "plugin"}]'
        )
        with self.assertRaisesRegex(ValueError, "plugins and bundles"):
            self.render(allowlist=plugin_allowlist)

        with_bundles = (
            self.project_catalog + b'\n[bundles]\nexample = ["jackson-core"]\n'
        )
        with self.assertRaisesRegex(ValueError, "plugins and bundles"):
            self.render(with_bundles)

    def test_rejects_extra_fields_in_project_library_aliases(self) -> None:
        project = tomllib.loads(self.project_catalog.decode("utf-8"))
        project["libraries"]["jackson-core"]["name"] = "jackson-core"
        with self.assertRaisesRegex(ValueError, "only contain module"):
            generator._validate_allowlist(self.allowlist_data, project)

    def test_rejects_duplicate_project_gav(self) -> None:
        alias = "other-jackson-core"
        project = self.project_catalog.replace(
            b"[libraries]\n",
            b"[libraries]\n"
            + alias.encode()
            + b' = { module = "com.fasterxml.jackson.core:jackson-core" }\n',
            1,
        )
        allowlist_data = json.loads(self.allowlist)
        allowlist_data["libraries"].append(
            {"alias": alias, "module": "com.fasterxml.jackson.core:jackson-core"}
        )
        allowlist_data["libraries"].sort(key=lambda entry: entry["alias"])
        allowlist = (
            json.dumps(allowlist_data, ensure_ascii=False, indent=2).encode() + b"\n"
        )
        with self.assertRaisesRegex(ValueError, "maps GAV"):
            self.render(project, allowlist=allowlist)

    def test_atomic_write_failures_preserve_existing_output_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "libs.versions.toml"
            original = b'[libraries]\nold = { module = "org.example:old" }\n'
            output.write_bytes(original)
            output.chmod(0o640)
            expected_sha = hashlib.sha256(original).hexdigest()

            real_replace = generator.os.replace
            calls = 0

            def fail_once(source: str | Path, target: str | Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("injected replace failure")
                real_replace(source, target)

            with (
                mock.patch.object(generator.os, "replace", side_effect=fail_once),
                self.assertRaisesRegex(OSError, "injected"),
            ):
                generator._write_atomic(output, b"candidate")
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(), expected_sha
            )
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o640)

            read_calls = 0
            real_read_bytes = Path.read_bytes

            def mismatch_once(path: Path) -> bytes:
                nonlocal read_calls
                if path == output:
                    read_calls += 1
                    if read_calls == 3:
                        return b"wrong read-back"
                return real_read_bytes(path)

            with (
                mock.patch.object(Path, "read_bytes", mismatch_once),
                self.assertRaisesRegex(ValueError, "read-back mismatch"),
            ):
                generator._write_atomic(output, b"candidate")
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(), expected_sha
            )
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o640)

    def test_atomic_write_preserves_existing_mode_and_uses_catalog_mode_for_new_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            existing = root / "existing.versions.toml"
            existing.write_bytes(b"original")
            existing.chmod(0o640)

            generator._write_atomic(existing, b"updated")

            self.assertEqual(existing.read_bytes(), b"updated")
            self.assertEqual(stat.S_IMODE(existing.stat().st_mode), 0o640)

            created = root / "new.versions.toml"
            generator._write_atomic(created, b"catalog")
            self.assertEqual(stat.S_IMODE(created.stat().st_mode), 0o644)

    def test_atomic_write_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            actual_parent = root / "actual"
            actual_parent.mkdir()
            linked_parent = root / "linked"
            linked_parent.symlink_to(actual_parent, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "canonical and non-symlinked"):
                generator._write_atomic(
                    linked_parent / "libs.versions.toml", b"catalog"
                )

    def test_parser_receipt_binds_generated_catalog_to_projects_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory).resolve()
            projects_root = temporary_root / "projects"
            generated_catalog = projects_root / "gradle" / "libs.versions.toml"
            generated_catalog.parent.mkdir(parents=True)
            generated_catalog.write_bytes(self.render())
            receipt_path = temporary_root / "parser-receipt.json"
            receipt = self.parser_receipt(generated_catalog)
            receipt_path.write_bytes(generator.canonical_json_bytes(receipt))

            self.assertEqual(
                generator._verify_parser_receipt(
                    receipt_path,
                    projects_root,
                    ROOT,
                    generated_catalog,
                    self.mapping_data,
                ),
                receipt,
            )

    def test_parser_receipt_rejects_generated_catalog_outside_projects_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory).resolve()
            projects_root = temporary_root / "projects"
            projects_root.mkdir()
            generated_catalog = temporary_root / "outside" / "libs.versions.toml"
            generated_catalog.parent.mkdir()
            generated_catalog.write_bytes(self.render())
            receipt_path = temporary_root / "parser-receipt.json"
            receipt_path.write_bytes(
                generator.canonical_json_bytes(self.parser_receipt(generated_catalog))
            )

            with self.assertRaisesRegex(ValueError, "inside Projects"):
                generator._verify_parser_receipt(
                    receipt_path,
                    projects_root,
                    ROOT,
                    generated_catalog,
                    self.mapping_data,
                )

    def test_parser_receipt_requires_the_pinned_contract_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory).resolve()
            projects_root = temporary_root / "projects"
            generated_catalog = projects_root / "gradle" / "libs.versions.toml"
            generated_catalog.parent.mkdir(parents=True)
            generated_catalog.write_bytes(self.render())
            receipt_path = temporary_root / "parser-receipt.json"
            receipt = self.parser_receipt(generated_catalog)
            receipt["parser_fixture"]["path"] = str(SCRIPT_PATH)
            receipt["parser_fixture"]["sha256"] = hashlib.sha256(
                SCRIPT_PATH.read_bytes()
            ).hexdigest()
            receipt_path.write_bytes(generator.canonical_json_bytes(receipt))

            with self.assertRaisesRegex(ValueError, "pinned contract fixture"):
                generator._verify_parser_receipt(
                    receipt_path,
                    projects_root,
                    ROOT,
                    generated_catalog,
                    self.mapping_data,
                )

    def test_evidence_receipts_and_candidate_lock_bind_inputs_and_reject_tampering(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory).resolve()
            projects_root = temporary_root / "projects"
            central_root = temporary_root / "central"
            evidence_dir = projects_root / ".gradle" / "issue-1832-evidence"
            evidence_dir.mkdir(parents=True)

            paths = {
                "generator": central_root / "scripts" / SCRIPT_PATH.name,
                "mapping": central_root / "config" / "projects-dependabot-catalog.toml",
                "projects_source": projects_root
                / "gradle"
                / "libs.project.versions.toml",
                "projects_allowlist": projects_root
                / "gradle"
                / "libs.project.versions.allowlist.json",
                "central_catalog": central_root / "gradle" / "libs.versions.toml",
                "generated_catalog": projects_root / "gradle" / "libs.versions.toml",
            }
            input_payloads = {
                "generator": SCRIPT_PATH.read_bytes(),
                "mapping": self.mapping,
                "projects_source": self.project_catalog,
                "projects_allowlist": self.allowlist,
                "central_catalog": self.central_catalog,
                "generated_catalog": self.render(),
            }
            for name, path in paths.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(input_payloads[name])

            parser_fixture = central_root / generator.PARSER_FIXTURE_REL
            parser_fixture.parent.mkdir(parents=True, exist_ok=True)
            parser_fixture.write_bytes(
                (FIXTURES / "dependabot-parser-contract.rb").read_bytes()
            )
            central_head = "a" * 40
            projects_head = "b" * 40
            observations = {
                "central": {"root": str(central_root), "expected_head": central_head},
                "projects": {
                    "root": str(projects_root),
                    "expected_head": projects_head,
                },
            }
            map_path = evidence_dir / "repository-map.json"
            map_payload = generator.canonical_json_bytes({"schema_version": 2})
            map_path.write_bytes(map_payload)
            receipt_path = evidence_dir / "generator-receipt.json"
            parser_path = evidence_dir / "parser-receipt.json"
            lock_path = evidence_dir / "candidate-lock.json"
            parser_receipt = self.parser_receipt(paths["generated_catalog"])
            parser_receipt["parser_fixture"] = {
                "path": str(parser_fixture),
                "sha256": hashlib.sha256(parser_fixture.read_bytes()).hexdigest(),
            }
            parser_bytes = generator.canonical_json_bytes(parser_receipt)
            parser_path.write_bytes(parser_bytes)

            with (
                mock.patch.object(generator, "_input_paths", return_value=paths),
                mock.patch.object(
                    generator,
                    "_load_project_repository_map",
                    return_value=({"schema_version": 2}, map_payload, observations),
                ),
                mock.patch.object(generator, "_git", return_value=central_head),
            ):
                receipt = generator._build_receipt(
                    paths,
                    map_path,
                    map_payload,
                    {
                        "central": {
                            **observations["central"],
                            "origin": "git@github.com:bluetape4k/bluetape4k-dependencies.git",
                            "branch": "develop",
                            "base_sha": central_head,
                        },
                        "projects": {
                            **observations["projects"],
                            "origin": "git@github.com:bluetape4k/bluetape4k-projects.git",
                            "branch": "develop",
                            "base_sha": projects_head,
                        },
                    },
                    ["python", str(paths["generator"]), "--check"],
                )
                receipt_bytes = generator.canonical_json_bytes(receipt)
                lock = generator._build_candidate_lock(
                    receipt_path,
                    receipt_bytes,
                    parser_path,
                    parser_bytes,
                    map_path,
                    map_payload,
                    receipt,
                )
                receipt_path.write_bytes(receipt_bytes)
                lock_path.write_bytes(generator.canonical_json_bytes(lock))

                self.assertEqual(receipt["projects"]["expected_head"], projects_head)
                self.assertEqual(receipt["central"]["expected_head"], central_head)
                self.assertEqual(receipt["central"]["peeled_commit"], central_head)
                self.assertEqual(receipt["python_version"], sys.version)
                self.assertEqual(
                    receipt["repository_map"]["sha256"],
                    hashlib.sha256(map_payload).hexdigest(),
                )
                generator._verify_evidence(evidence_dir)

                generator._write_evidence_file(
                    receipt_path, receipt_bytes, "generator receipt"
                )
                with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                    generator._write_evidence_file(
                        receipt_path,
                        b"reused with different content",
                        "generator receipt",
                    )

                paths["mapping"].write_bytes(self.mapping + b"\n")
                with self.assertRaisesRegex(
                    ValueError, "generator receipt mapping SHA-256 mismatch"
                ):
                    generator._verify_evidence(evidence_dir)
                paths["mapping"].write_bytes(self.mapping)

                changed_parser_receipt = dict(parser_receipt)
                changed_parser_receipt["dependencies"] = []
                parser_path.write_bytes(
                    generator.canonical_json_bytes(changed_parser_receipt)
                )
                with self.assertRaisesRegex(
                    ValueError, "parser receipt must contain all ten"
                ):
                    generator._verify_evidence(evidence_dir)

    @property
    def target_aliases(self) -> set[str]:
        return {entry["alias"] for entry in self.mapping_data["projection"]}

    @staticmethod
    def central_version(entry: dict[str, str], central: dict) -> str:
        if entry["source_type"] == "version":
            return central["versions"][entry["source_name"]]
        source_alias = central["libraries"][entry["source_name"]]
        version = source_alias["version"]
        if isinstance(version, str):
            return version
        return central["versions"][version["ref"]]

    def parser_receipt(self, generated_catalog: Path) -> dict:
        generated = tomllib.loads(generated_catalog.read_text(encoding="utf-8"))
        dependencies = [
            {
                "alias": item["alias"],
                "module": item["module"],
                "version_ref": item["version_key"],
                "version": generated["versions"][item["version_key"]],
            }
            for item in self.mapping_data["projection"]
        ]
        parser_fixture = FIXTURES / "dependabot-parser-contract.rb"
        return {
            "schema_version": 1,
            "dependabot_core_commit": self.mapping_data["dependabot_core_commit"],
            "parser_fixture": {
                "path": str(parser_fixture),
                "sha256": hashlib.sha256(parser_fixture.read_bytes()).hexdigest(),
            },
            "generated_catalog": {
                "path": str(generated_catalog),
                "sha256": hashlib.sha256(generated_catalog.read_bytes()).hexdigest(),
            },
            "dependencies": dependencies,
        }


if __name__ == "__main__":
    unittest.main()
