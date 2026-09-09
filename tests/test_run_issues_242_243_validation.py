from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run-issues-242-243-validation.py"
SPEC = importlib.util.spec_from_file_location("run_issues_242_243_validation", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules["run_issues_242_243_validation"] = runner


class ValidationRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        SPEC.loader.exec_module(runner)

    def test_phase_and_execution_budget_contract(self) -> None:
        self.assertEqual(
            runner.PHASES,
            (
                "signing-buildsrc",
                "candidate-bom-publication",
                "timefold-graphs-baseline",
                "timefold-graphs-candidate",
                "consumers",
                "publication-poms",
            ),
        )
        self.assertEqual(runner.MAX_WORKERS, 2)
        self.assertEqual(runner.CHILD_TIMEOUT_SECONDS, 600)
        self.assertEqual(runner.PUBLICATION_POMS_TIMEOUT_SECONDS, 1800)
        self.assertEqual(runner.TOTAL_VALIDATION_BUDGET_SECONDS, 5400)
        self.assertEqual(runner.GRADLE_HOME_POLICY, "ephemeral-0700")
        self.assertIn("--no-configuration-cache", runner.GRADLE_FLAGS)
        self.assertIn("--no-build-cache", runner.GRADLE_FLAGS)

    def test_issue_242_scope_excludes_signing_and_keeps_required_phases(self) -> None:
        self.assertEqual(
            runner.ISSUE_242_REQUIRED_PHASES,
            (
                "candidate-bom-publication",
                "timefold-graphs-baseline",
                "timefold-graphs-candidate",
                "consumers",
                "publication-poms",
            ),
        )
        self.assertEqual(runner.scoped_phases("issue-242"), runner.ISSUE_242_REQUIRED_PHASES)
        self.assertEqual(runner.scoped_phases("issues-242-243"), runner.PHASES)
        with self.assertRaisesRegex(runner.InputContractError, "signing"):
            runner.validate_scope_phase("issue-242", "signing-buildsrc")

    def test_issue_242_exposed_graph_contains_only_direct_timefold_coordinate(self) -> None:
        self.assertEqual(
            runner.issue_242_graph_coordinates("bluetape4k-exposed"),
            (
                "ai.timefold.solver:timefold-solver-core",
            ),
        )

    def test_issue_242_graphs_cover_all_required_coordinates_across_consumers(self) -> None:
        covered = set().union(
            *(runner.issue_242_graph_coordinates(repository)
              for repository in runner.ISSUE_242_CONSUMER_REPOSITORIES)
        )
        self.assertEqual(covered, set(runner.TIMEFOLD_COORDINATES))

    def test_timefold_tasks_use_exact_included_project_names(self) -> None:
        self.assertEqual(
            runner.TIMEFOLD_COORDINATES,
            (
                "ai.timefold.solver:timefold-solver-core",
                "ai.timefold.solver:timefold-solver-benchmark",
                "ai.timefold.solver:timefold-solver-jackson",
                "ai.timefold.solver:timefold-solver-spring-boot-starter",
            ),
        )
        self.assertEqual(
            runner.TIMEFOLD_GRAPH_TASKS["bluetape4k-exposed"],
            (":bluetape4k-exposed-timefold-solver-persistence:dependencyInsight",),
        )
        self.assertEqual(
            runner.TIMEFOLD_GRAPH_TASKS["timefold-workshop"],
            (":school-timetabling:dependencyInsight",),
        )
        self.assertEqual(
            runner.TIMEFOLD_GRAPH_COORDINATES,
            {
                "bluetape4k-exposed": ("ai.timefold.solver:timefold-solver-core",),
                "timefold-workshop": (
                    "ai.timefold.solver:timefold-solver-core",
                    "ai.timefold.solver:timefold-solver-jackson",
                    "ai.timefold.solver:timefold-solver-spring-boot-starter",
                ),
                "clinic-appointment": (
                    "ai.timefold.solver:timefold-solver-benchmark",
                ),
            },
        )
        self.assertEqual(
            runner.CONSUMER_TASKS["timefold-workshop"],
            (
                ":bluetape4k-timefold:test",
                ":school-timetabling:test",
                ":exposed-jdbc-examples:test",
                ":exposed-r2dbc-examples:test",
            ),
        )
        self.assertEqual(
            runner.CONSUMER_TASKS["bluetape4k-exposed"],
            (":bluetape4k-exposed-timefold-solver-persistence:test",),
        )
        self.assertEqual(
            runner.CONSUMER_TASKS["clinic-appointment"],
            (":appointment-solver:test", ":appointment-api:test"),
        )

    def test_dependency_insight_parser_requires_selected_version_and_reason(self) -> None:
        coordinate = "ai.timefold.solver:timefold-solver-core"
        output = f"""
> Task :module:dependencyInsight
{coordinate}:2.4.0 -> 2.6.0
  Selection reasons:
      - Selected by rule
      - By constraint: candidate BOM

{coordinate}:2.6.0
\\--- testRuntimeClasspath
"""
        observation = runner.parse_dependency_insight(output, coordinate)
        self.assertEqual(observation.selected_version, "2.6.0")
        self.assertEqual(
            observation.selection_reason,
            "Selected by rule; By constraint: candidate BOM",
        )

        with self.assertRaisesRegex(runner.InputContractError, "not resolved"):
            runner.parse_dependency_insight(
                "No dependencies matching given input were found in configuration",
                coordinate,
            )
        with self.assertRaisesRegex(runner.InputContractError, "selection reason"):
            runner.parse_dependency_insight(f"{coordinate}:2.6.0\n", coordinate)

    def test_candidate_graph_result_fails_closed_on_wrong_selected_version(self) -> None:
        coordinate = "ai.timefold.solver:timefold-solver-core"
        job = mock.Mock(
            phase="timefold-graphs-candidate",
            coordinate=coordinate,
            repository="bluetape4k-exposed",
        )
        result = runner.CommandResult(
            status="pass",
            returncode=0,
            stdout=(
                f"{coordinate}:2.4.0\n"
                "  Selection reasons:\n"
                "      - By constraint: stale BOM\n"
            ),
            stderr="",
            elapsed_seconds=0.1,
            timed_out=False,
            process_group_terminated=False,
            termination_signal=None,
            output_sha256="a" * 64,
        )
        checked = runner.validate_graph_result(job, result)
        self.assertEqual(checked.status, "fail")
        self.assertIn("expected 2.6.0", checked.diagnostics)

    def test_graph_semantic_failure_cannot_retain_success_cache_evidence(self) -> None:
        coordinate = "ai.timefold.solver:timefold-solver-core"
        job = mock.Mock(
            phase="timefold-graphs-candidate",
            coordinate=coordinate,
            repository="bluetape4k-exposed",
        )
        result = runner.CommandResult(
            status="pass",
            returncode=0,
            stdout=(
                f"{coordinate}:2.4.0\n"
                "  Selection reasons:\n"
                "      - By constraint: stale BOM\n"
            ),
            stderr="",
            elapsed_seconds=0.1,
            timed_out=False,
            process_group_terminated=False,
            termination_signal=None,
            output_sha256="a" * 64,
            cached=True,
            cache_key="b" * 64,
            cache_output_path="/receipt/cache/b.output",
        )

        checked = runner.validate_graph_result(job, result)

        self.assertEqual(checked.status, "fail")
        self.assertFalse(checked.cached)
        self.assertEqual(checked.cache_key, "")
        self.assertEqual(checked.cache_output_path, "")

    def test_consumer_graph_receipt_records_before_after_and_selection_reasons(self) -> None:
        coordinate = "ai.timefold.solver:timefold-solver-benchmark"
        document = {
            "consumers": [
                {"name": "timefold-workshop", "graphs": []},
                {"name": "clinic-appointment", "graphs": []},
            ]
        }
        job = mock.Mock(
            repository="clinic-appointment",
            coordinate=coordinate,
            configuration="testRuntimeClasspath",
        )

        def result(version: str, digest: str, reason: str) -> runner.CommandResult:
            return runner.CommandResult(
                status="pass",
                returncode=0,
                stdout=(
                    f"{coordinate}:{version}\n"
                    "  Selection reasons:\n"
                    f"      - {reason}\n"
                ),
                stderr="",
                elapsed_seconds=0.1,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256=digest,
            )

        baseline_result = result("2.4.0", "a" * 64, "By constraint: stable BOM")
        runner._update_consumer_graphs(
            document,
            runner.PhaseResult(
                "timefold-graphs-baseline", "pass", "c" * 64, (baseline_result,)
            ),
            (job,),
        )
        candidate_result = result("2.6.0", "b" * 64, "By constraint: candidate BOM")
        runner._update_consumer_graphs(
            document,
            runner.PhaseResult(
                "timefold-graphs-candidate", "pass", "d" * 64, (candidate_result,)
            ),
            (job,),
        )
        graph = document["consumers"][1]["graphs"][0]
        self.assertEqual(graph["before_version"], "2.4.0")
        self.assertEqual(graph["after_version"], "2.6.0")
        self.assertIn("before: By constraint: stable BOM", graph["selection_reason"])
        self.assertIn("after: By constraint: candidate BOM", graph["selection_reason"])
        self.assertEqual(graph["output_sha256"], "b" * 64)

    def test_issue_242_consumer_graph_receipt_includes_exposed_coordinates(self) -> None:
        document = {
            "scope": "issue-242",
            "consumers": [
                {
                    "name": name,
                    "graphs": [],
                }
                for name in runner.ISSUE_242_CONSUMER_REPOSITORIES
            ],
        }
        coordinates = runner.issue_242_graph_coordinates("bluetape4k-exposed")
        jobs = tuple(
            mock.Mock(
                repository="bluetape4k-exposed",
                coordinate=coordinate,
                configuration="testRuntimeClasspath",
            )
            for coordinate in coordinates
        )

        def phase_result(version: str, digest_prefix: str) -> runner.PhaseResult:
            results = tuple(
                runner.CommandResult(
                    status="pass",
                    returncode=0,
                    stdout=(
                        f"{coordinate}:{version}\n"
                        "  Selection reasons:\n"
                        f"      - By constraint: {'candidate' if version == '2.6.0' else 'stable'} BOM\n"
                    ),
                    stderr="",
                    elapsed_seconds=0.1,
                    timed_out=False,
                    process_group_terminated=False,
                    termination_signal=None,
                    output_sha256=digest_prefix * 64,
                )
                for coordinate in coordinates
            )
            return runner.PhaseResult(
                "timefold-graphs-baseline" if version == "2.4.0" else "timefold-graphs-candidate",
                "pass",
                digest_prefix * 64,
                results,
            )

        runner._update_consumer_graphs(document, phase_result("2.4.0", "c"), jobs)
        runner._update_consumer_graphs(document, phase_result("2.6.0", "d"), jobs)
        exposed = next(item for item in document["consumers"] if item["name"] == "bluetape4k-exposed")
        self.assertEqual(
            [graph["coordinate"] for graph in exposed["graphs"]],
            list(coordinates),
        )
        self.assertTrue(all(graph["after_version"] == "2.6.0" for graph in exposed["graphs"]))

    def test_failed_candidate_phase_keeps_pending_consumer_baseline_without_crashing(self) -> None:
        coordinate = "ai.timefold.solver:timefold-solver-benchmark"
        document = {
            "consumers": [
                {"name": "timefold-workshop", "graphs": []},
                {
                    "name": "clinic-appointment",
                    "graphs": [
                        {
                            "coordinate": coordinate,
                            "before_version": "pending-baseline",
                        }
                    ],
                },
            ]
        }
        job = mock.Mock(
            repository="clinic-appointment",
            coordinate=coordinate,
            configuration="testRuntimeClasspath",
        )
        command_result = runner.CommandResult(
            status="pass",
            returncode=0,
            stdout=(
                f"{coordinate}:2.6.0\n"
                "  Selection reasons:\n"
                "      - By constraint: candidate BOM\n"
            ),
            stderr="",
            elapsed_seconds=0.1,
            timed_out=False,
            process_group_terminated=False,
            termination_signal=None,
            output_sha256="a" * 64,
        )
        runner._update_consumer_graphs(
            document,
            runner.PhaseResult(
                "timefold-graphs-candidate", "fail", "b" * 64, (command_result,)
            ),
            (job,),
        )
        self.assertEqual(
            document["consumers"][1]["graphs"][0]["before_version"],
            "pending-baseline",
        )

    def test_repository_inventory_reuses_catalog_candidate_authority(self) -> None:
        self.assertEqual(
            runner.CATALOG_REPOSITORIES,
            runner.catalog_candidate.CATALOG_REPOSITORIES,
        )
        self.assertEqual(
            runner.SIGNING_REPOSITORIES,
            runner.catalog_candidate.SIGNING_REPOSITORIES,
        )

    def test_candidate_artifact_manifest_binds_actual_platform_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            artifact = (
                repository
                / "io/github/bluetape4k/bluetape4k-dependencies"
                / runner.CANDIDATE_BOM_VERSION
            )
            artifact.mkdir(parents=True)
            pom = artifact / f"bluetape4k-dependencies-{runner.CANDIDATE_BOM_VERSION}.pom"
            module = artifact / f"bluetape4k-dependencies-{runner.CANDIDATE_BOM_VERSION}.module"
            pom.write_text(
                "<project><groupId>io.github.bluetape4k</groupId>"
                "<artifactId>bluetape4k-dependencies</artifactId>"
                f"<version>{runner.CANDIDATE_BOM_VERSION}</version></project>\n",
                encoding="utf-8",
            )
            module.write_bytes(
                runner.canonical_json_bytes(
                    {
                        "component": {
                            "group": "io.github.bluetape4k",
                            "module": "bluetape4k-dependencies",
                            "version": runner.CANDIDATE_BOM_VERSION,
                        }
                    }
                )
            )

            first = runner.candidate_artifact_manifest(repository)
            self.assertEqual(set(first["artifacts"]), {pom.name, module.name})
            self.assertEqual(len(first["sha256"]), 64)
            module.write_bytes(
                runner.canonical_json_bytes(
                    {
                        "component": {
                            "group": "io.github.bluetape4k",
                            "module": "bluetape4k-dependencies",
                            "version": runner.CANDIDATE_BOM_VERSION,
                        },
                        "changed": True,
                    }
                )
            )
            self.assertNotEqual(first["sha256"], runner.candidate_artifact_manifest(repository)["sha256"])

            changed = runner.candidate_artifact_manifest(repository)
            extra = artifact / "unexpected-extra.jar"
            extra.write_bytes(b"extra")
            self.assertNotEqual(
                changed["sha256"],
                runner.candidate_artifact_manifest(repository)["sha256"],
            )

            module.unlink()
            with self.assertRaisesRegex(runner.InputContractError, "candidate BOM artifact"):
                runner.candidate_artifact_manifest(repository)

    def test_candidate_artifact_manifest_rejects_malformed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            artifact = (
                repository
                / "io/github/bluetape4k/bluetape4k-dependencies"
                / runner.CANDIDATE_BOM_VERSION
            )
            artifact.mkdir(parents=True)
            pom_name, module_name = runner.CANDIDATE_BOM_ARTIFACTS
            (artifact / pom_name).write_text("<not-project>", encoding="utf-8")
            (artifact / module_name).write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(
                runner.InputContractError, "metadata is malformed|metadata identity"
            ):
                runner.candidate_artifact_manifest(repository)

    def test_candidate_environment_is_explicit_and_not_inherited_implicitly(self) -> None:
        source = {
            "PATH": "/bin",
            "HOME": "/tmp/home",
            "DOCKER_HOST": "unix:///Users/debop/.colima/default/docker.sock",
            "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE": "/var/run/docker.sock",
            "TESTCONTAINERS_REUSE_ENABLE": "true",
            "TESTCONTAINERS_RYUK_DISABLED": "true",
            "BLUETAPE4K_DEPENDENCIES_CATALOG_PATH": "/candidate/catalog.toml",
            "ISSUES_242_243_CANDIDATE_MAVEN_REPO": "/candidate/m2",
            "CENTRAL_PASSWORD": "secret",
        }
        environment = runner.sanitized_environment(source)
        self.assertEqual(
            set(environment),
            {
                "PATH",
                "HOME",
                "DOCKER_HOST",
                "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE",
                "TESTCONTAINERS_REUSE_ENABLE",
                "TESTCONTAINERS_RYUK_DISABLED",
            },
        )
        job = mock.Mock(
            environment_overrides=(
                ("BLUETAPE4K_DEPENDENCIES_CATALOG_PATH", "/candidate/catalog.toml"),
                ("ISSUES_242_243_CANDIDATE_MAVEN_REPO", "/candidate/m2"),
            )
        )
        with mock.patch.dict(os.environ, source, clear=True):
            explicit = runner._job_environment(job)
        self.assertEqual(
            set(explicit),
            {
                "PATH",
                "HOME",
                "DOCKER_HOST",
                "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE",
                "TESTCONTAINERS_REUSE_ENABLE",
                "TESTCONTAINERS_RYUK_DISABLED",
                "BLUETAPE4K_DEPENDENCIES_CATALOG_PATH",
                "ISSUES_242_243_CANDIDATE_MAVEN_REPO",
            },
        )

    def test_run_command_preserves_explicit_candidate_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    "import os; print(os.environ['ISSUES_242_243_CANDIDATE_MAVEN_REPO'])",
                ),
                cwd=root,
                environment={
                    "PATH": os.environ["PATH"],
                    "ISSUES_242_243_CANDIDATE_MAVEN_REPO": "/candidate/m2",
                },
                timeout_seconds=5,
            )
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.stdout.strip(), "/candidate/m2")

    def test_candidate_catalog_must_match_portable_checksum_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            central = Path(directory).resolve()
            catalog = central / "gradle/libs.versions.toml"
            sidecar = central / "gradle/libs.versions.toml.sha256"
            catalog.parent.mkdir(parents=True)
            catalog.write_text('[versions]\ntimefold-solver = "2.6.0"\n', encoding="utf-8")
            digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
            sidecar.write_text(f"{digest}\n", encoding="utf-8")

            self.assertEqual(runner.validated_candidate_catalog(central), (catalog, digest))
            sidecar.write_text(f"{'0' * 64}\n", encoding="utf-8")
            with self.assertRaisesRegex(runner.InputContractError, "checksum mismatch"):
                runner.validated_candidate_catalog(central)

    def test_cache_key_is_canonical_and_binds_every_required_input(self) -> None:
        first = runner.cache_key(
            repository="bluetape4k-projects",
            repository_head="a" * 40,
            helper_sha256="b" * 64,
            catalog_sha256="c" * 64,
            bom_sha256="d" * 64,
            task_set=("test", "compileKotlin"),
            configuration="buildSrc",
            jdk_version="21.0.8",
            gradle_version="8.14.3",
        )
        same = runner.cache_key(
            repository="bluetape4k-projects",
            repository_head="a" * 40,
            helper_sha256="b" * 64,
            catalog_sha256="c" * 64,
            bom_sha256="d" * 64,
            task_set=("compileKotlin", "test"),
            configuration="buildSrc",
            jdk_version="21.0.8",
            gradle_version="8.14.3",
        )
        self.assertEqual(first, same)
        self.assertEqual(len(first), 64)
        for field, value in (
            ("repository_head", "e" * 40),
            ("helper_sha256", "f" * 64),
            ("catalog_sha256", "1" * 64),
            ("bom_sha256", "2" * 64),
            ("configuration", "other"),
            ("jdk_version", "17"),
            ("gradle_version", "8.10"),
        ):
            inputs = {
                "repository": "bluetape4k-projects",
                "repository_head": "a" * 40,
                "helper_sha256": "b" * 64,
                "catalog_sha256": "c" * 64,
                "bom_sha256": "d" * 64,
                "task_set": ("test", "compileKotlin"),
                "configuration": "buildSrc",
                "jdk_version": "21.0.8",
                "gradle_version": "8.14.3",
            }
            inputs[field] = value
            with self.subTest(field=field):
                self.assertNotEqual(first, runner.cache_key(**inputs))
        changed_tasks = {
            "repository": "bluetape4k-projects",
            "repository_head": "a" * 40,
            "helper_sha256": "b" * 64,
            "catalog_sha256": "c" * 64,
            "bom_sha256": "d" * 64,
            "task_set": ("compileKotlin",),
            "configuration": "buildSrc",
            "jdk_version": "21.0.8",
            "gradle_version": "8.14.3",
        }
        self.assertNotEqual(first, runner.cache_key(**changed_tasks))
        changed_arguments = {
            **changed_tasks,
            "task_set": ("test", "compileKotlin"),
            "arguments": ("--dependency", "demo:artifact"),
        }
        self.assertNotEqual(first, runner.cache_key(**changed_arguments))
        map_bound = {
            **changed_tasks,
            "task_set": ("test", "compileKotlin"),
            "repository_map_sha256": "3" * 64,
        }
        self.assertNotEqual(first, runner.cache_key(**map_bound))
        self.assertNotEqual(
            runner.cache_key(**map_bound),
            runner.cache_key(**{**map_bound, "repository_map_sha256": "4" * 64}),
        )

    def test_cache_hit_requires_success_and_readback_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory).resolve()
            output = cache / "output.log"
            output.write_bytes(b"successful output\n")
            output.chmod(0o600)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            key = "a" * 64
            entry = cache / f"{key}.json"
            entry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "pass",
                        "cache_key": key,
                        "output_path": str(output),
                        "output_sha256": digest,
                    }
                ),
                encoding="utf-8",
            )
            entry.chmod(0o600)
            hit = runner.read_cache_entry(cache, key)
            self.assertIsNotNone(hit)
            self.assertEqual(hit["output_sha256"], digest)
            output.write_bytes(b"tampered")
            self.assertIsNone(runner.read_cache_entry(cache, key))

            for hostile_output in (
                b"before to\x9b31mken=sentinel-raw-cache after",
                b"before to\xffken=sentinel-invalid-cache after",
            ):
                output.write_bytes(hostile_output)
                hostile_digest = hashlib.sha256(hostile_output).hexdigest()
                entry.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "status": "pass",
                            "cache_key": key,
                            "output_path": str(output),
                            "output_sha256": hostile_digest,
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertIsNone(runner.read_cache_entry(cache, key))

            output.write_bytes(b"successful output\n")
            entry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "fail",
                        "cache_key": key,
                        "output_path": str(output),
                        "output_sha256": digest,
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(runner.read_cache_entry(cache, key))

            with mock.patch.object(runner, "MAX_COMMAND_OUTPUT_BYTES", 16):
                oversized = b"x" * 17
                output.write_bytes(oversized)
                entry.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "status": "pass",
                            "cache_key": key,
                            "output_path": str(output),
                            "output_sha256": hashlib.sha256(oversized).hexdigest(),
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertIsNone(runner.read_cache_entry(cache, key))

    def test_redaction_removes_secret_material_and_bounds_diagnostics(self) -> None:
        armor_header = "-----BEGIN PGP " + "PRIVATE KEY BLOCK-----"
        armor_footer = "-----END PGP " + "PRIVATE KEY BLOCK-----"
        body = (
            "before\n"
            "PASSWORD=super-secret\n"
            "AWS_SECRET_ACCESS_KEY=sentinel-aws-secret\n"
            "AWS_ACCESS_KEY_ID=sentinel-aws-id\n"
            "MY_SECRET_ACCESS_KEY=sentinel-my-secret\n"
            f"{armor_header}\n"
            "sentinel-private-body\n"
            f"{armor_footer}\n"
            "after\n"
        )
        redacted = runner.redact_output(body)
        self.assertNotIn("super-secret", redacted)
        self.assertNotIn("sentinel-aws-secret", redacted)
        self.assertNotIn("sentinel-aws-id", redacted)
        self.assertNotIn("sentinel-my-secret", redacted)
        self.assertNotIn("sentinel-private-body", redacted)
        self.assertNotIn("BEGIN PGP PRIVATE KEY BLOCK", redacted)
        bypasses = runner.redact_output(
            "error: PASSWORD=sentinel-password\n"
            "Authorization: Bearer sentinel-bearer\n"
            "https://example.invalid/path?token=sentinel-query&safe=yes\n"
            "warning: api_key=sentinel-api-key\n"
            "fatal: access_token=sentinel-access-token\n"
            "fatal: client-secret: sentinel-client-secret\n"
            "fatal: accessToken=sentinel-camel-access\n"
            "fatal: clientSecret: sentinel-camel-client\n"
            "fatal: apiKey=sentinel-camel-api\n"
            "https://example.invalid/repo?accessToken=sentinel-camel-query\n"
            "fatal: apikey=sentinel-compound-api\n"
            "fatal: privatekey=sentinel-compound-private\n"
            "fatal: signingkey=sentinel-compound-signing\n"
            "fatal: accesskey=sentinel-compound-access\n"
            "fatal: secretaccesskey=sentinel-compound-secret-access\n"
            "https://example.invalid/repo?apikey=sentinel-compound-query-api\n"
            "https://example.invalid/repo?clientsecret=sentinel-compound-query-client\n"
            "fatal: my_apikey=sentinel-namespaced-api\n"
            "fatal: service-privatekey=sentinel-namespaced-private\n"
            "fatal: aws_secretaccesskey=sentinel-namespaced-secret-access\n"
            "fatal: build_signingkey=sentinel-namespaced-signing\n"
            "https://example.invalid/repo?my_clientsecret=sentinel-namespaced-query-client\n"
            "https://example.invalid/repo?oauth_accesskeyid=sentinel-namespaced-query-access\n"
            "fatal: access%5Ftoken=sentinel-encoded-assignment\n"
            "fatal: access%54oken=sentinel-encoded-camel-assignment\n"
            "fatal: to%00ken=sentinel-encoded-control\n"
            "fatal: to%E2%80%8Bken=sentinel-encoded-format\n"
            "fatal: to%1B%5B31mken=sentinel-encoded-ansi\n"
            "fatal: access%255Ftoken=sentinel-nested-encoded\n"
            "fatal: to+ken=sentinel-plus-encoded\n"
            "fatal: to%u006ben=sentinel-residual-percent\n"
            "fatal: ｔｏｋｅｎ=sentinel-fullwidth-token\n"
            "fatal: ａｐｉｋｅｙ=sentinel-fullwidth-api\n"
            "fatal: to%EF%BC%8500ken=sentinel-encoded-fullwidth-percent\n"
            "fatal: to％00ken=sentinel-raw-fullwidth-percent\n"
            "fatal: to%2500ken=sentinel-nested-control\n"
            "fatal: to%25E2%2580%258Bken=sentinel-nested-format\n"
            "fatal: to%09ken=sentinel-encoded-tab\n"
            "fatal: to%0Aken=sentinel-encoded-lf\n"
            "fatal: to%0Dken=sentinel-encoded-cr\n"
            "fatal: to%C2%85ken=sentinel-encoded-c1\n"
            "fatal: to%E2%80%A8ken=sentinel-encoded-line-separator\n"
            "fatal: to\x85ken=sentinel-raw-c1\n"
            "fatal: to\u2028ken=sentinel-raw-line-separator\n"
            "fatal: to\u2029ken=sentinel-raw-paragraph-separator\n"
            "fatal: to\u00a0ken=sentinel-raw-nbsp\n"
            "fatal: to\tken=sentinel-raw-tab\n"
            "fatal: to\u009b31mken=sentinel-c1-csi\n"
            "fatal: to\u009dtitle\u009cken=sentinel-c1-osc\n"
            "fatal: to\x1bPtitle\x1b\\ken=sentinel-dcs\n"
            "fatal: my_to%09ken=sentinel-namespaced-encoded-tab\n"
            "https://example.invalid/?to%E2%80%8Bken=sentinel-encoded-query\n"
            "https://example.invalid/?to%09ken=sentinel-encoded-tab-query\n"
            "https://example.invalid/?to+ken=sentinel-plus-query\n"
            "https://example.invalid/?ｔｏｋｅｎ=sentinel-fullwidth-query\n"
            "fatal: myapikey=sentinel-compound-prefix\n"
            "fatal: apikeyfoo=sentinel-compound-suffix\n"
            "fatal: secretaccesskeyid=sentinel-compound-nested\n"
            "fatal: myprivatekey=sentinel-compound-private-prefix\n"
            "fatal: access\x1b[31mToken=sentinel-ansi-assignment\n"
            "fatal: to\x00ken=sentinel-control-assignment\n"
            "fatal: access\u200bToken=sentinel-format-assignment\n"
            "https://example.invalid/?access\x1b[31mToken=sentinel-ansi-query\n"
            "-----BEGIN PGP PRIVATE\x1b[31m KEY BLOCK-----\n"
            "sentinel-ansi-private-body\n"
            "-----END PGP PRIVATE KEY BLOCK-----\n"
            "prefix Authorization: Basic sentinel-basic\n"
            "https://user:sentinel-userinfo@example.invalid/repo.git\n"
            "https://sentinel-token-only@example.invalid/repo.git\n"
            "https://user%3Asentinel-encoded@example.invalid/repo.git\n"
            "password: |\n  sentinel-folded\n"
            "-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            "sentinel-truncated-private-body\n"
            "fatal: token＝sentinel-unicode-equals\n"
            "fatal: token：sentinel-unicode-colon\n"
            "https://x.invalid/?token＝sentinel-unicode-query\n"
            "fatal: token\r\n=sentinel-crlf-delimiter\n"
            "fatal: to\nken=sentinel-cross-line\n"
            "fatal: mytoken=sentinel-contiguous-token\n"
            "fatal: tokenvalue=sentinel-contiguous-token-prefix\n"
            "fatal: mysecret=sentinel-contiguous-secret\n"
            "fatal: mykey=sentinel-contiguous-key\n"
            "fatal:to\nken=sentinel-punctuation-boundary\n"
            "fatal: to\n\nken=sentinel-multi-line\n"
            "fatal: token=\nsentinel-value-line\n"
            "fatal: token:\r\nsentinel-colon-value\n"
            "Cookie: session=sentinel-cookie\n"
            "Set-Cookie: session=sentinel-set-cookie\n"
            "fatal: session=sentinel-session\n"
            "Ａuthorization: Basic sentinel-fullwidth-header\n"
            "Authoriz%61tion: Bearer sentinel-encoded-header"
        )
        for sentinel in (
            "sentinel-password",
            "sentinel-bearer",
            "sentinel-query",
            "sentinel-api-key",
            "sentinel-access-token",
            "sentinel-client-secret",
            "sentinel-camel-access",
            "sentinel-camel-client",
            "sentinel-camel-api",
            "sentinel-camel-query",
            "sentinel-compound-api",
            "sentinel-compound-private",
            "sentinel-compound-signing",
            "sentinel-compound-access",
            "sentinel-compound-secret-access",
            "sentinel-compound-query-api",
            "sentinel-compound-query-client",
            "sentinel-namespaced-api",
            "sentinel-namespaced-private",
            "sentinel-namespaced-secret-access",
            "sentinel-namespaced-signing",
            "sentinel-namespaced-query-client",
            "sentinel-namespaced-query-access",
            "sentinel-encoded-assignment",
            "sentinel-encoded-camel-assignment",
            "sentinel-encoded-control",
            "sentinel-encoded-format",
            "sentinel-encoded-ansi",
            "sentinel-nested-encoded",
            "sentinel-plus-encoded",
            "sentinel-residual-percent",
            "sentinel-fullwidth-token",
            "sentinel-fullwidth-api",
            "sentinel-encoded-fullwidth-percent",
            "sentinel-raw-fullwidth-percent",
            "sentinel-nested-control",
            "sentinel-nested-format",
            "sentinel-encoded-tab",
            "sentinel-encoded-lf",
            "sentinel-encoded-cr",
            "sentinel-encoded-c1",
            "sentinel-encoded-line-separator",
            "sentinel-raw-c1",
            "sentinel-raw-line-separator",
            "sentinel-raw-paragraph-separator",
            "sentinel-raw-nbsp",
            "sentinel-raw-tab",
            "sentinel-c1-csi",
            "sentinel-c1-osc",
            "sentinel-dcs",
            "sentinel-namespaced-encoded-tab",
            "sentinel-encoded-query",
            "sentinel-encoded-tab-query",
            "sentinel-plus-query",
            "sentinel-fullwidth-query",
            "sentinel-compound-prefix",
            "sentinel-compound-suffix",
            "sentinel-compound-nested",
            "sentinel-compound-private-prefix",
            "sentinel-ansi-assignment",
            "sentinel-control-assignment",
            "sentinel-format-assignment",
            "sentinel-ansi-query",
            "sentinel-ansi-private-body",
            "sentinel-truncated-private-body",
            "sentinel-basic",
            "sentinel-userinfo",
            "sentinel-token-only",
            "sentinel-encoded",
            "sentinel-folded",
            "sentinel-unicode-equals",
            "sentinel-unicode-colon",
            "sentinel-unicode-query",
            "sentinel-crlf-delimiter",
            "sentinel-cross-line",
            "sentinel-contiguous-token",
            "sentinel-contiguous-token-prefix",
            "sentinel-contiguous-secret",
            "sentinel-contiguous-key",
            "sentinel-punctuation-boundary",
            "sentinel-multi-line",
            "sentinel-value-line",
            "sentinel-colon-value",
            "sentinel-cookie",
            "sentinel-set-cookie",
            "sentinel-session",
            "sentinel-fullwidth-header",
            "sentinel-encoded-header",
        ):
            self.assertNotIn(sentinel, bypasses)
        lines = runner.bounded_diagnostics("\n".join(f"line-{i}" for i in range(100)))
        self.assertEqual(lines, "\n".join(f"line-{i}" for i in range(20, 100)))

    def test_gradle_commands_disable_both_gradle_caches(self) -> None:
        command = runner.gradle_command(
            Path("/workspace/repo"), ("test", "compileKotlin"), configuration="buildSrc"
        )
        self.assertEqual(command[0], "/workspace/repo/gradlew")
        self.assertIn("-p", command)
        self.assertIn("buildSrc", command)
        self.assertIn("test", command)
        self.assertIn("compileKotlin", command)
        self.assertIn("--no-daemon", command)
        self.assertIn("--no-configuration-cache", command)
        self.assertIn("--no-build-cache", command)
        self.assertIn("--console=plain", command)

    def test_only_candidate_graphs_refresh_dependencies(self) -> None:
        self.assertFalse(
            runner.should_refresh_graph_dependencies("timefold-graphs-baseline")
        )
        self.assertTrue(
            runner.should_refresh_graph_dependencies("timefold-graphs-candidate")
        )

    def test_baseline_graph_requires_a_clean_exact_base_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(
                ["git", "init", "-b", "baseline", str(root)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Baseline Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "baseline@example.invalid"],
                check=True,
            )
            (root / "fixture.txt").write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-m", "fixture"],
                check=True,
                capture_output=True,
            )
            origin = "git@github.com:bluetape4k/demo.git"
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", origin], check=True
            )
            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            binding = {"base_sha": head, "origin": origin}
            actual = runner._baseline_root_from_binding(binding, root, "demo")
            self.assertEqual(actual, (root, head, origin, "baseline"))
            with self.assertRaisesRegex(runner.InputContractError, "exact base worktree"):
                runner._baseline_root_from_binding(binding, None, "demo")
            with self.assertRaisesRegex(runner.InputContractError, "reuses candidate"):
                runner._baseline_root_from_binding(
                    {**binding, "candidate_worktree": str(root)}, root, "demo"
                )
            with self.assertRaisesRegex(runner.InputContractError, "HEAD mismatch"):
                runner._baseline_root_from_binding(
                    {"base_sha": "a" * 40, "origin": origin}, root, "demo"
                )

    def test_validation_budget_is_fail_closed_and_receipt_bound(self) -> None:
        self.assertEqual(
            runner.validation_budget_remaining(
                {
                    "validation_budget": {
                        "total_seconds": 5400,
                        "elapsed_seconds": 123.5,
                        "remaining_seconds": 5276.5,
                    }
                }
            ),
            5276.5,
        )
        with self.assertRaisesRegex(runner.InputContractError, "validation budget"):
            runner.validation_budget_remaining({})

    def test_expired_total_budget_blocks_job_before_cache_or_launch(self) -> None:
        job = runner.ValidationJob(
            repository="demo",
            phase="signing-buildsrc",
            cwd=Path("/tmp"),
            command=("echo", "ok"),
            configuration="buildSrc",
            task_set=("test",),
            repository_head="a" * 40,
            helper_sha256="b" * 64,
            catalog_sha256="c" * 64,
            bom_sha256="d" * 64,
            jdk_version="25",
            gradle_version="9.7.0",
        )
        result = runner.execute_job(
            job,
            cache_directory=Path("/path/that/must/not/be/read"),
            receipt_path=Path("/path/that/must/not/be/read.json"),
            deadline=time.monotonic() - 1,
        )
        self.assertEqual(result.status, "blocked")
        self.assertIn("total validation budget exceeded", result.diagnostics)

    def test_execute_job_uses_a_fresh_private_gradle_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            observed: dict[str, object] = {}

            def run_command(**kwargs: object) -> runner.CommandResult:
                environment = kwargs["environment"]
                assert isinstance(environment, dict)
                gradle_home = Path(str(environment["GRADLE_USER_HOME"]))
                observed["path"] = gradle_home
                observed["mode"] = stat.S_IMODE(gradle_home.stat().st_mode)
                observed["exists_during_run"] = gradle_home.is_dir()
                return runner.CommandResult(
                    status="fail",
                    returncode=1,
                    stdout="",
                    stderr="failed",
                    elapsed_seconds=0.1,
                    timed_out=False,
                    process_group_terminated=False,
                    termination_signal=None,
                    output_sha256="a" * 64,
                )

            job = runner.ValidationJob(
                repository="demo",
                phase="signing-buildsrc",
                cwd=root,
                command=("./gradlew", "test"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="25",
                gradle_version="9.7.0",
            )
            with mock.patch.object(runner, "run_command", side_effect=run_command):
                result = runner.execute_job(
                    job,
                    cache_directory=root / "cache",
                    receipt_path=root / "receipt.json",
                )

            self.assertEqual(result.status, "fail")
            self.assertTrue(observed["exists_during_run"])
            self.assertEqual(observed["mode"], 0o700)
            self.assertFalse(Path(str(observed["path"])).exists())

    def test_successful_job_revalidates_source_binding_after_child_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            job = runner.ValidationJob(
                repository="demo",
                phase="signing-buildsrc",
                cwd=root,
                command=("./gradlew", "test"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="25",
                gradle_version="9.7.0",
            )
            command_result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout="ok",
                stderr="",
                elapsed_seconds=0.1,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256="a" * 64,
            )
            binding_loader = mock.Mock(return_value={})
            with (
                mock.patch.object(runner, "run_command", return_value=command_result),
                mock.patch.object(runner, "validate_job_binding") as validate,
            ):
                result = runner.execute_job(
                    job,
                    cache_directory=root / "cache",
                    receipt_path=root / "receipt.json",
                    binding_loader=binding_loader,
                )

            self.assertEqual(result.status, "pass")
            self.assertEqual(binding_loader.call_count, 3)
            self.assertEqual(validate.call_count, 3)

    def test_candidate_producer_captures_one_immutable_manifest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_repository = root / "candidate-m2"
            candidate_repository.mkdir()
            job = runner.ValidationJob(
                repository="bluetape4k-dependencies",
                phase="candidate-bom-publication",
                cwd=root,
                command=("./gradlew", "publishToMavenLocal"),
                configuration="candidate-bom-publication",
                task_set=("publishToMavenLocal",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="25",
                gradle_version="9.7.0",
                produced_maven_repository=candidate_repository,
            )
            command_result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout="ok",
                stderr="",
                elapsed_seconds=0.1,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256="a" * 64,
            )
            manifest = {
                "repository_path": str(candidate_repository),
                "sha256": "e" * 64,
            }
            with (
                mock.patch.object(
                    runner,
                    "read_cache_entry",
                    return_value={
                        "output": "stale cache",
                        "output_sha256": "0" * 64,
                        "output_path": str(root / "cache" / "stale.output"),
                    },
                ) as read_cache,
                mock.patch.object(
                    runner, "run_command", return_value=command_result
                ) as run_command,
                mock.patch.object(
                    runner,
                    "write_cache_entry",
                    return_value={
                        "output_sha256": "a" * 64,
                        "output_path": str(root / "cache" / "fresh.output"),
                    },
                ),
                mock.patch.object(runner, "candidate_artifact_manifest", return_value=manifest),
            ):
                result = runner.execute_job(
                    job,
                    cache_directory=root / "cache",
                    receipt_path=root / "receipt.json",
                )

            read_cache.assert_not_called()
            run_command.assert_called_once()
            manifest["sha256"] = "f" * 64
            self.assertEqual(
                json.loads(result.candidate_artifact_manifest_bytes)["sha256"],
                "e" * 64,
            )

    def test_receipt_update_uses_captured_producer_manifest_without_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            receipt = root / "receipt.json"
            map_path = root / "map.json"
            map_path.write_text("map\n", encoding="utf-8")
            receipt.write_text(
                json.dumps(
                    {
                        "repository_map": {
                            "path": str(map_path),
                            "sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
                        },
                        "current_state": "discovered",
                        "central": {"candidate_head": "a" * 40},
                        "candidate_artifact_manifest": None,
                        "validation_budget": {
                            "total_seconds": 5400.0,
                            "elapsed_seconds": 0.0,
                            "remaining_seconds": 5400.0,
                        },
                        "phases": [],
                        "commands": [],
                        "failure_record": [],
                    }
                ),
                encoding="utf-8",
            )
            receipt.chmod(0o600)
            candidate_repository = root / "candidate-m2"
            candidate_repository.mkdir()

            @contextmanager
            def lock(path: Path):
                yield

            class StrictReceipt:
                _receipt_lock = staticmethod(lock)

                @staticmethod
                def validate_receipt(path: Path) -> dict[str, object]:
                    return json.loads(path.read_text(encoding="utf-8"))

                write_atomic = staticmethod(runner._atomic_write)

            manifest = {
                "repository_path": str(candidate_repository),
                "version": runner.CANDIDATE_BOM_VERSION,
                "artifacts": {"fixture": "d" * 64},
                "repository_files": {"fixture": "d" * 64},
                "sha256": "e" * 64,
            }
            job = runner.ValidationJob(
                repository="bluetape4k-dependencies",
                phase="candidate-bom-publication",
                cwd=root,
                command=("./gradlew", "publishToMavenLocal"),
                configuration="candidate-bom-publication",
                task_set=("publishToMavenLocal",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="25",
                gradle_version="9.7.0",
                job_id="candidate-bom-publication:0:bluetape4k-dependencies",
                produced_maven_repository=candidate_repository,
            )
            command_result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout="ok",
                stderr="",
                elapsed_seconds=0.1,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256="f" * 64,
                job_id=job.job_id,
                repository=job.repository,
                candidate_artifact_manifest_bytes=runner.canonical_json_bytes(manifest),
            )
            phase = runner.PhaseResult(
                job.phase,
                "pass",
                runner._phase_digest(job.phase, (command_result,), None),
                (command_result,),
            )
            with (
                mock.patch.object(runner, "_load_receipt_module", return_value=StrictReceipt),
                mock.patch.object(
                    runner, "git_source_tree_sha256", return_value="1" * 64
                ),
                mock.patch.object(
                    runner,
                    "candidate_artifact_manifest",
                    side_effect=AssertionError("receipt update must not rescan artifacts"),
                ),
            ):
                runner._write_receipt_update(
                    receipt,
                    phase,
                    (job,),
                    expected_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
                    expected_state="discovered",
                    phase_elapsed_seconds=0.1,
                )

            updated = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(updated["candidate_artifact_manifest"]["sha256"], "e" * 64)
            self.assertEqual(
                updated["candidate_artifact_manifest"]["source_tree_sha256"],
                "1" * 64,
            )

    def test_toolchain_probe_uses_one_private_home_and_deadline_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
            wrapper = root / "gradle/wrapper/gradle-wrapper.properties"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text(
                "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.6.1-bin.zip\n",
                encoding="utf-8",
            )
            observed: list[tuple[Path, int, bool]] = []

            def run_command(**kwargs: object) -> runner.CommandResult:
                environment = kwargs["environment"]
                assert isinstance(environment, dict)
                gradle_home = Path(str(environment["GRADLE_USER_HOME"]))
                observed.append(
                    (
                        gradle_home,
                        stat.S_IMODE(gradle_home.stat().st_mode),
                        "CENTRAL_PASSWORD" in environment,
                    )
                )
                return runner.CommandResult(
                    status="pass",
                    returncode=0,
                    stdout="tool 1.0\n",
                    stderr="",
                    elapsed_seconds=0.01,
                    timed_out=False,
                    process_group_terminated=False,
                    termination_signal=None,
                    output_sha256="a" * 64,
                )

            with mock.patch.object(runner, "run_command", side_effect=run_command):
                with mock.patch.dict(os.environ, {"CENTRAL_PASSWORD": "secret"}, clear=False):
                    self.assertEqual(
                        runner.detect_toolchain(
                            root, deadline=time.monotonic() + 10
                        ),
                        ("tool 1.0", "Gradle 9.6.1 (wrapper)"),
                    )

            self.assertEqual(len(observed), 1)
            self.assertTrue(all(mode == 0o700 for _, mode, _ in observed))
            self.assertTrue(all(not leaked for _, _, leaked in observed))
            self.assertFalse(observed[0][0].exists())
            with self.assertRaisesRegex(runner.InputContractError, "budget exceeded"):
                runner.detect_toolchain(root, deadline=time.monotonic() - 1)

            for result, message in (
                (
                    runner.CommandResult(
                        status="fail",
                        returncode=1,
                        stdout="",
                        stderr="probe failed",
                        elapsed_seconds=0.01,
                        timed_out=False,
                        process_group_terminated=False,
                        termination_signal=None,
                        output_sha256="b" * 64,
                    ),
                    "successful result",
                ),
                (
                    runner.CommandResult(
                        status="pass",
                        returncode=0,
                        stdout="",
                        stderr="",
                        elapsed_seconds=0.01,
                        timed_out=False,
                        process_group_terminated=False,
                        termination_signal=None,
                        output_sha256="c" * 64,
                    ),
                    "version evidence",
                ),
            ):
                with self.subTest(message=message):
                    with mock.patch.object(
                        runner, "run_command", return_value=result
                    ):
                        with self.assertRaisesRegex(runner.InputContractError, message):
                            runner.detect_toolchain(
                                root, deadline=time.monotonic() + 10
                            )

    def test_candidate_jobs_use_receipt_bound_bom_without_disabling_verification(self) -> None:
        central = Path("/workspace/bluetape4k-dependencies")
        candidate = Path("/workspace/candidate-m2")
        common = (
            "--init-script",
            str(central / runner.CANDIDATE_INIT_SCRIPT_RELATIVE),
            f"-D{runner.CANDIDATE_REPOSITORY_PROPERTY}={candidate}",
            f"-D{runner.CANDIDATE_VERSION_PROPERTY}={runner.CANDIDATE_BOM_VERSION}",
        )
        self.assertEqual(
            runner.candidate_arguments(
                central_root=central,
                candidate_maven_repository=candidate,
            ),
            common,
        )
        self.assertNotIn("--dependency-verification=off", common)

    def test_candidate_init_script_forces_the_receipt_bound_bom(self) -> None:
        script = (
            SCRIPT_PATH.parents[1] / runner.CANDIDATE_INIT_SCRIPT_RELATIVE
        ).read_text(encoding="utf-8")

        self.assertIn(
            '"io.github.bluetape4k",\n                "bluetape4k-dependencies",',
            script,
        )
        self.assertIn("includeVersion(", script)
        self.assertIn("repositories.exclusiveContent", script)
        self.assertIn('configuration.name == "testImplementation"', script)
        self.assertIn("project.dependencies.enforcedPlatform(candidateBom)", script)
        self.assertIn("details.useVersion(candidateBomVersion)", script)
        self.assertIn('project.plugins.withId("io.spring.dependency-management")', script)
        self.assertIn("dependencyManagement.imports", script)

    def test_consumer_jobs_bind_canonical_helper_without_generated_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            central = workspace / "bluetape4k-dependencies"
            consumer = workspace / "timefold-workshop"
            canonical = central / runner.CANONICAL_HELPER_RELATIVE
            generated = consumer / runner.GENERATED_HELPER_RELATIVE
            canonical.parent.mkdir(parents=True)
            consumer.mkdir()
            canonical.write_text("canonical helper\n", encoding="utf-8")

            self.assertFalse(generated.exists())
            self.assertEqual(
                runner.job_helper_path(
                    repository="timefold-workshop",
                    root=consumer,
                    central_root=central,
                    phase="timefold-graphs-baseline",
                ),
                canonical,
            )

    def test_publication_pom_command_reuses_strict_non_candidate_map(self) -> None:
        command = runner.publication_pom_command(
            central_root=Path("/workspace/bluetape4k-dependencies"),
            workspace=Path("/workspace"),
            repository_map=Path("/workspace/repository-map.json"),
            repository_map_sha256="a" * 64,
        )
        self.assertEqual(command[0], sys.executable)
        self.assertIn("scripts/verify-publication-poms.py", " ".join(command))
        self.assertIn("--repository-map", command)
        self.assertIn(str(Path("/workspace/repository-map.json")), command)
        self.assertIn("--repository-map-sha256", command)
        self.assertIn("a" * 64, command)
        self.assertIn("--summary", command)
        self.assertNotIn("timefold-workshop", command)
        self.assertNotIn("clinic-appointment", command)

    def test_parallel_scheduler_stops_submitting_after_first_failure(self) -> None:
        started: list[str] = []

        def worker(item: str) -> dict[str, object]:
            started.append(item)
            if item == "fail":
                raise runner.ValidationFailure("deterministic failure")
            time.sleep(0.03)
            return {"repository": item, "status": "pass"}

        with self.assertRaises(runner.ValidationFailure):
            runner.run_bounded_jobs(("fail", "in-flight", "must-not-start"), worker, max_workers=2)
        self.assertNotIn("must-not-start", started)

    def test_timeout_terminates_process_group_and_writes_0600_redacted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifact = root / "failure.log"
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    "import time; print('PASSWORD=secret\\nAWS_SECRET_ACCESS_KEY=sentinel-aws-secret\\nAWS_ACCESS_KEY_ID=sentinel-aws-id\\nMY_SECRET_ACCESS_KEY=sentinel-my-secret\\nCookie: session=sentinel-cookie-artifact\\nＡuthorization: Basic sentinel-auth-artifact', flush=True); time.sleep(10)",
                ),
                cwd=root,
                environment=os.environ,
                timeout_seconds=0.05,
                failure_artifact=artifact,
            )
            self.assertEqual(result.status, "fail")
            self.assertTrue(result.timed_out)
            self.assertTrue(result.process_group_terminated)
            self.assertTrue(artifact.is_file())
            self.assertEqual(stat.S_IMODE(artifact.stat().st_mode), 0o600)
            self.assertNotIn("secret", artifact.read_text(encoding="utf-8"))
            artifact_text = artifact.read_text(encoding="utf-8")
            self.assertNotIn("sentinel-aws-secret", artifact_text)
            self.assertNotIn("sentinel-aws-id", artifact_text)
            self.assertNotIn("sentinel-my-secret", artifact_text)
            self.assertNotIn("sentinel-cookie-artifact", artifact_text)
            self.assertNotIn("sentinel-auth-artifact", artifact_text)

    def test_raw_control_bytes_fail_closed_for_command_and_cache_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifact = root / "failure.log"
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    "import os, sys; os.write(2, b'before to\\x9b31mken=sentinel-raw-csi after'); sys.exit(1)",
                ),
                cwd=root,
                environment=os.environ,
                timeout_seconds=2,
                failure_artifact=artifact,
            )
            self.assertEqual(result.status, "fail")
            self.assertEqual(result.stderr, "<redacted>")
            self.assertNotIn("sentinel-raw-csi", result.diagnostics)
            self.assertEqual(artifact.read_text(encoding="utf-8"), "<redacted>")

            cache = root / "cache"
            key = "b" * 64
            runner.write_cache_entry(
                cache,
                key,
                b"before to\xffken=sentinel-invalid-utf8 after",
            )
            hit = runner.read_cache_entry(cache, key)
            self.assertIsNotNone(hit)
            self.assertEqual(hit["output"], "<redacted>")
            self.assertNotIn(
                "sentinel-invalid-utf8",
                (cache / f"{key}.output").read_text(encoding="utf-8"),
            )

    def test_output_limit_terminates_process_group_and_bounds_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runner, "MAX_COMMAND_OUTPUT_BYTES", 4096
        ):
            root = Path(directory).resolve()
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    "import os; chunk=b'x'*4096\nwhile True: os.write(1, chunk)",
                ),
                cwd=root,
                environment=os.environ,
                timeout_seconds=5,
            )
            self.assertEqual(result.status, "fail")
            self.assertFalse(result.timed_out)
            self.assertTrue(result.process_group_terminated)
            self.assertIn("output limit exceeded", result.diagnostics)
            self.assertLessEqual(len(result.stdout.encode("utf-8")), 4096)

    def test_successful_leader_cannot_leave_a_descendant_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runner, "TERMINATE_GRACE_SECONDS", 0.05
        ):
            root = Path(directory).resolve()
            child_pid_path = root / "child.pid"
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    (
                        "import pathlib, subprocess, sys, time; "
                        "child=subprocess.Popen([sys.executable, '-c', "
                        "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)']); "
                        "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); "
                        "time.sleep(0.1)"
                    ),
                    str(child_pid_path),
                ),
                cwd=root,
                environment=os.environ,
                timeout_seconds=3,
            )
            self.assertEqual(result.status, "fail")
            self.assertTrue(result.process_group_terminated)
            self.assertEqual(result.termination_signal, "SIGKILL")
            self.assertIn("left processes in its assigned group", result.diagnostics)
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)

    def test_nested_bounded_capture_inherits_outer_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runner, "TERMINATE_GRACE_SECONDS", 0.05
        ):
            root = Path(directory).resolve()
            child_pid_path = root / "nested-child.pid"
            child_code = (
                "import os,pathlib,sys,time; "
                "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
                "time.sleep(30)"
            )
            helper_code = (
                "import importlib.util,pathlib,sys; "
                "spec=importlib.util.spec_from_file_location('nested_candidate', sys.argv[1]); "
                "module=importlib.util.module_from_spec(spec); "
                "sys.modules[spec.name]=module; spec.loader.exec_module(module); "
                "module.run_bounded_capture([sys.executable, '-c', sys.argv[3], sys.argv[4]], "
                "cwd=pathlib.Path(sys.argv[2]), timeout_seconds=30)"
            )
            environment = dict(os.environ)
            environment[runner.catalog_candidate.PROCESS_GROUP_OWNER_ENV] = (
                runner.catalog_candidate.PROCESS_GROUP_OWNER_VALUE
            )
            result = runner.run_command(
                command=(
                    sys.executable,
                    "-c",
                    helper_code,
                    str(runner.CATALOG_CANDIDATE_PATH),
                    str(root),
                    child_code,
                    str(child_pid_path),
                ),
                cwd=root,
                environment=environment,
                timeout_seconds=0.5,
            )

            self.assertTrue(result.timed_out)
            self.assertTrue(result.process_group_terminated)
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)

    def test_publication_job_declares_the_outer_process_group_owner(self) -> None:
        job = mock.Mock(phase="publication-poms", environment_overrides=())
        environment = runner._job_environment(job)
        self.assertEqual(
            environment[runner.catalog_candidate.PROCESS_GROUP_OWNER_ENV],
            runner.catalog_candidate.PROCESS_GROUP_OWNER_VALUE,
        )

    def test_receipt_binding_rejects_map_path_or_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            map_path = root / "map.json"
            map_path.write_text("{}\n", encoding="utf-8")
            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "repository_map": {
                            "path": str(map_path),
                            "sha256": "0" * 64,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                runner.load_local_receipt(receipt, map_path)

    def test_execution_boundary_requires_reviewed_heads_or_hosted_runner(self) -> None:
        job = runner.ValidationJob(
            repository="bluetape4k-dependencies",
            phase="signing-buildsrc",
            cwd=Path("/workspace"),
            command=("./gradlew", "test"),
            configuration="buildSrc",
            task_set=("test",),
            repository_head="a" * 40,
            helper_sha256="b" * 64,
            catalog_sha256="c" * 64,
            bom_sha256="d" * 64,
            jdk_version="25",
            gradle_version="9.7.0",
        )
        with self.assertRaisesRegex(runner.InputContractError, "boundary"):
            runner.validate_execution_boundary(None, (), (job.repository_head,), {})
        with self.assertRaisesRegex(runner.InputContractError, "every exact job HEAD"):
            runner.validate_execution_boundary(
                "persistent-trusted", (), (job.repository_head,), {}
            )
        runner.validate_execution_boundary(
            "persistent-trusted", ("a" * 40,), (job.repository_head,), {}
        )
        with self.assertRaisesRegex(runner.InputContractError, "GitHub-hosted"):
            runner.validate_execution_boundary(
                "disposable-hosted", (), (job.repository_head,), {}
            )
        runner.validate_execution_boundary(
            "disposable-hosted",
            (),
            (job.repository_head,),
            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"},
        )

    def test_phase_trust_sets_include_every_executed_repository_head(self) -> None:
        repository_map = {
            "repositories": [
                {
                    "name": name,
                    "candidate_head": f"{index + 1:040x}",
                    "base_sha": f"{index + 101:040x}",
                }
                for index, name in enumerate(runner.CATALOG_REPOSITORIES)
            ]
        }
        entries = {
            item["name"]: item for item in repository_map["repositories"]
        }

        self.assertEqual(
            runner.required_phase_heads(
                "publication-poms", repository_map, {}, None
            ),
            frozenset(
                entries[name]["candidate_head"]
                for name in runner.SIGNING_REPOSITORIES
            ),
        )
        self.assertEqual(
            runner.required_phase_heads(
                "candidate-bom-publication", repository_map, {}, None
            ),
            frozenset(
                {entries["bluetape4k-dependencies"]["candidate_head"]}
            ),
        )

        receipt = {
            "consumers": [
                {"name": "timefold-workshop", "candidate_head": "e" * 40},
                {"name": "clinic-appointment", "candidate_head": "f" * 40},
            ]
        }
        for phase in ("timefold-graphs-candidate", "consumers"):
            with self.subTest(phase=phase):
                self.assertEqual(
                    runner.required_phase_heads(
                        phase, repository_map, receipt, None
                    ),
                    frozenset(
                        {
                            entries["bluetape4k-dependencies"]["candidate_head"],
                            entries["bluetape4k-exposed"]["candidate_head"],
                            "e" * 40,
                            "f" * 40,
                        }
                    ),
                )

    def test_run_phase_rejects_lexical_parent_symlink_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            map_path = linked / "map.json"
            receipt_path = linked / "receipt.json"
            with mock.patch.object(runner, "load_strict_repository_map") as load_map, self.assertRaisesRegex(
                runner.InputContractError, "symlink"
            ):
                runner.run_phase(
                    "signing-buildsrc",
                    repository_map_path=map_path,
                    receipt_path=receipt_path,
                    dry_run=True,
                )
            load_map.assert_not_called()

    def test_run_phase_reserves_budget_before_job_toolchain_discovery(self) -> None:
        class StopAfterOrderCheck(RuntimeError):
            pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            map_path = root / "map.json"
            receipt_path = root / "receipt.json"
            map_path.write_text("{}\n", encoding="utf-8")
            receipt_path.write_text("{}\n", encoding="utf-8")
            events: list[str] = []

            def reserve(*args: object, **kwargs: object) -> tuple[float, str]:
                events.append("reserve")
                return 30.0, "a" * 64

            def build(*args: object, **kwargs: object) -> tuple[runner.ValidationJob, ...]:
                self.assertEqual(events, ["reserve"])
                self.assertIsInstance(kwargs.get("deadline"), float)
                raise StopAfterOrderCheck

            with (
                mock.patch.object(runner, "load_strict_repository_map", return_value={}),
                mock.patch.object(
                    runner,
                    "load_local_receipt",
                    return_value={"current_state": "discovered"},
                ),
                mock.patch.object(runner, "sha256_file", return_value="b" * 64),
                mock.patch.object(
                    runner,
                    "required_phase_heads",
                    return_value=frozenset({"a" * 40}),
                ),
                mock.patch.object(
                    runner, "_reserve_validation_budget", side_effect=reserve
                ),
                mock.patch.object(runner, "build_phase_jobs", side_effect=build),
                self.assertRaises(StopAfterOrderCheck),
            ):
                runner.run_phase(
                    "signing-buildsrc",
                    repository_map_path=map_path,
                    receipt_path=receipt_path,
                    execution_boundary="persistent-trusted",
                    reviewed_heads=("a" * 40,),
                )

            self.assertEqual(events, ["reserve"])

    def test_run_phase_rejects_non_tail_rerun_and_unbound_output_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            map_path = root / "map.json"
            receipt_path = root / "receipt.json"
            map_path.write_text("{}\n", encoding="utf-8")
            receipt_path.write_text("{}\n", encoding="utf-8")
            repository_map: dict[str, object] = {}

            with (
                mock.patch.object(
                    runner, "load_strict_repository_map", return_value=repository_map
                ),
                mock.patch.object(
                    runner,
                    "load_local_receipt",
                    return_value={
                        "current_state": "discovered",
                        "phases": [
                            {"name": "signing-buildsrc"},
                            {"name": "consumers"},
                        ],
                    },
                ),
                mock.patch.object(runner, "sha256_file", return_value="a" * 64),
                self.assertRaisesRegex(runner.InputContractError, "non-tail phase"),
            ):
                runner.run_phase(
                    "signing-buildsrc",
                    repository_map_path=map_path,
                    receipt_path=receipt_path,
                    dry_run=True,
                )

            with (
                mock.patch.object(
                    runner, "load_strict_repository_map", return_value=repository_map
                ),
                mock.patch.object(
                    runner,
                    "load_local_receipt",
                    return_value={
                        "current_state": "discovered",
                        "phases": [{"name": "candidate-bom-publication"}],
                    },
                ),
                mock.patch.object(runner, "sha256_file", return_value="a" * 64),
                self.assertRaisesRegex(
                    runner.InputContractError, "producer without a new receipt"
                ),
            ):
                runner.run_phase(
                    "candidate-bom-publication",
                    repository_map_path=map_path,
                    receipt_path=receipt_path,
                    candidate_maven_repository=root / "candidate-m2",
                    dry_run=True,
                )

            empty_receipt = {"current_state": "discovered", "phases": []}
            for keyword, value, message in (
                ("candidate_maven_repository", root / "other-m2", "receipt-bound"),
                ("cache_directory", root / "other-cache", "receipt-bound"),
            ):
                with (
                    mock.patch.object(
                        runner, "load_strict_repository_map", return_value=repository_map
                    ),
                    mock.patch.object(
                        runner, "load_local_receipt", return_value=empty_receipt
                    ),
                    mock.patch.object(runner, "sha256_file", return_value="a" * 64),
                    self.assertRaisesRegex(runner.InputContractError, message),
                ):
                    runner.run_phase(
                        "signing-buildsrc",
                        repository_map_path=map_path,
                        receipt_path=receipt_path,
                        dry_run=True,
                        **{keyword: value},
                    )

    def test_receipt_update_is_locked_strictly_validated_and_compare_and_swap_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            receipt = root / "receipt.json"
            initial = {
                "repository_map": {"path": str(root / "map.json"), "sha256": "a" * 64},
                "current_state": "discovered",
                "central": {"candidate_head": "a" * 40},
                "candidate_artifact_manifest": None,
                "validation_budget": {
                    "total_seconds": 5400,
                    "elapsed_seconds": 0.0,
                    "remaining_seconds": 5400.0,
                },
                "phases": [],
                "commands": [],
                "failure_record": [],
            }
            (root / "map.json").write_text("map\n", encoding="utf-8")
            initial["repository_map"]["sha256"] = hashlib.sha256(
                (root / "map.json").read_bytes()
            ).hexdigest()
            receipt.write_text(json.dumps(initial), encoding="utf-8")
            receipt.chmod(0o600)
            candidate_repository = root / "candidate-m2"
            artifact = (
                candidate_repository
                / "io/github/bluetape4k/bluetape4k-dependencies"
                / runner.CANDIDATE_BOM_VERSION
            )
            artifact.mkdir(parents=True)
            pom_name, module_name = runner.CANDIDATE_BOM_ARTIFACTS
            (artifact / pom_name).write_text(
                "<project><groupId>io.github.bluetape4k</groupId>"
                "<artifactId>bluetape4k-dependencies</artifactId>"
                f"<version>{runner.CANDIDATE_BOM_VERSION}</version></project>\n",
                encoding="utf-8",
            )
            (artifact / module_name).write_bytes(
                runner.canonical_json_bytes(
                    {
                        "component": {
                            "group": "io.github.bluetape4k",
                            "module": "bluetape4k-dependencies",
                            "version": runner.CANDIDATE_BOM_VERSION,
                        }
                    }
                )
            )
            artifact_digest = runner.candidate_artifact_manifest(candidate_repository)["sha256"]
            calls: list[str] = []

            @contextmanager
            def lock(path: Path):
                calls.append("lock-enter")
                yield
                calls.append("lock-exit")

            class StrictReceipt:
                _receipt_lock = staticmethod(lock)

                @staticmethod
                def validate_receipt(path: Path) -> dict[str, object]:
                    calls.append("validate")
                    return json.loads(path.read_text(encoding="utf-8"))

                write_atomic = staticmethod(runner._atomic_write)

            job = runner.ValidationJob(
                repository="demo",
                phase="signing-buildsrc",
                cwd=root,
                command=("echo", "ok"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="jdk",
                gradle_version="gradle",
            )
            result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout="",
                stderr="",
                elapsed_seconds=0.01,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256="e" * 64,
            )
            phase = runner.PhaseResult("signing-buildsrc", "pass", "f" * 64, (result,))
            expected_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            with mock.patch.object(runner, "_load_receipt_module", return_value=StrictReceipt):
                reserved, reserved_digest = runner._reserve_validation_budget(
                    receipt,
                    expected_receipt_sha256=expected_digest,
                    expected_state="discovered",
                )
                self.assertEqual(reserved, 5400.0)
                reserved_document = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual(reserved_document["validation_budget"]["elapsed_seconds"], 5400.0)
                self.assertEqual(reserved_document["validation_budget"]["remaining_seconds"], 0.0)
                runner._write_receipt_update(
                    receipt,
                    phase,
                    (job,),
                    expected_receipt_sha256=reserved_digest,
                    expected_state="discovered",
                    phase_elapsed_seconds=0.01,
                    reserved_seconds=reserved,
                )
                self.assertGreaterEqual(calls.count("validate"), 2)
                self.assertEqual(calls[0], "lock-enter")
                updated = json.loads(receipt.read_text(encoding="utf-8"))
                command = updated["commands"][0]
                self.assertEqual(command["phase"], "signing-buildsrc")
                self.assertEqual(command["repository_head"], "a" * 40)
                self.assertEqual(command["helper_sha256"], "b" * 64)
                self.assertEqual(command["catalog_sha256"], "c" * 64)
                self.assertEqual(command["bom_sha256"], "d" * 64)
                self.assertEqual(command["task_set"], ["test"])
                self.assertEqual(command["override_disposition"], "baseline")
                self.assertEqual(command["arguments"], [])
                self.assertEqual(command["gradle_home_policy"], "ephemeral-0700")
                self.assertRegex(command["input_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(updated["validation_budget"]["elapsed_seconds"], 0.01)
                self.assertEqual(updated["validation_budget"]["remaining_seconds"], 5399.99)
                stale_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
                self.assertNotEqual(stale_digest, expected_digest)
                with self.assertRaisesRegex(runner.InputContractError, "digest"):
                    runner._write_receipt_update(
                        receipt,
                        phase,
                        (job,),
                        expected_receipt_sha256=expected_digest,
                        expected_state="discovered",
                    )
                self.assertEqual(updated, json.loads(receipt.read_text(encoding="utf-8")))

                failed_result = runner.CommandResult(
                    status="fail",
                    returncode=1,
                    stdout="",
                    stderr="failed",
                    elapsed_seconds=0.01,
                    timed_out=False,
                    process_group_terminated=False,
                    termination_signal=None,
                    output_sha256="1" * 64,
                )
                failed_phase = runner.PhaseResult(
                    "signing-buildsrc", "fail", "2" * 64, (failed_result,)
                )
                current_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
                runner._write_receipt_update(
                    receipt,
                    failed_phase,
                    (job,),
                    expected_receipt_sha256=current_digest,
                    expected_state="discovered",
                    phase_elapsed_seconds=0.01,
                )
                failed_document = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual(failed_document["current_state"], "blocked")

    def test_receipt_update_records_actual_elapsed_time_when_budget_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "repository_map": {
                            "path": str(root / "map.json"),
                            "sha256": "a" * 64,
                        },
                        "current_state": "discovered",
                        "central": {"candidate_head": "a" * 40},
                        "candidate_artifact_manifest": None,
                        "validation_budget": {
                            "total_seconds": 10.0,
                            "elapsed_seconds": 10.0,
                            "remaining_seconds": 0.0,
                        },
                        "phases": [],
                        "commands": [],
                        "failure_record": [],
                    }
                ),
                encoding="utf-8",
            )
            receipt.chmod(0o600)
            (root / "map.json").write_text("map\n", encoding="utf-8")

            @contextmanager
            def lock(path: Path):
                yield

            class StrictReceipt:
                _receipt_lock = staticmethod(lock)

                @staticmethod
                def validate_receipt(path: Path) -> dict[str, object]:
                    return json.loads(path.read_text(encoding="utf-8"))

                write_atomic = staticmethod(runner._atomic_write)

            job = runner.ValidationJob(
                repository="bluetape4k-dependencies",
                phase="signing-buildsrc",
                cwd=root,
                command=("echo", "ok"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256="b" * 64,
                catalog_sha256="c" * 64,
                bom_sha256="d" * 64,
                jdk_version="jdk",
                gradle_version="gradle",
            )
            command_result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout="",
                stderr="",
                elapsed_seconds=12.5,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256="e" * 64,
            )
            phase = runner.PhaseResult(
                "signing-buildsrc", "pass", "f" * 64, (command_result,)
            )
            with mock.patch.object(runner, "_load_receipt_module", return_value=StrictReceipt):
                runner._write_receipt_update(
                    receipt,
                    phase,
                    (job,),
                    expected_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
                    expected_state="discovered",
                    phase_elapsed_seconds=12.5,
                    reserved_seconds=10.0,
                )

            updated = json.loads(receipt.read_text(encoding="utf-8"))
            recorded_phase = updated["phases"][0]
            self.assertEqual(recorded_phase["result"], "blocked")
            self.assertEqual(recorded_phase["elapsed_seconds"], 12.5)
            self.assertEqual(recorded_phase["reserved_seconds"], 10.0)
            self.assertEqual(updated["current_state"], "blocked")
            self.assertIn("budget exceeded", updated["failure_record"][-1]["reason"])

    def test_job_binding_rechecks_git_identity_clean_state_and_all_input_digests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "gradle").mkdir()
            (root / "buildSrc/src/main/kotlin").mkdir(parents=True)
            (root / "gradle/libs.versions.toml").write_text("catalog\n", encoding="utf-8")
            (root / "build.gradle.kts").write_text("bom\n", encoding="utf-8")
            helper = root / "buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt"
            helper.write_text("helper\n", encoding="utf-8")
            job = runner.ValidationJob(
                repository="demo",
                phase="signing-buildsrc",
                cwd=root,
                command=("echo", "ok"),
                configuration="buildSrc",
                task_set=("test",),
                repository_head="a" * 40,
                helper_sha256=runner.sha256_file(helper),
                catalog_sha256=runner.sha256_file(root / "gradle/libs.versions.toml"),
                bom_sha256=runner.sha256_file(root / "build.gradle.kts"),
                jdk_version="jdk",
                gradle_version="gradle",
                repository_origin="git@example/demo.git",
                repository_branch="feat/demo",
            )
            binding = {
                "name": "demo",
                "candidate_worktree": str(root),
                "candidate_head": "a" * 40,
                "origin": "git@example/demo.git",
                "candidate_branch": "feat/demo",
            }
            with mock.patch.object(
                runner,
                "_git",
                side_effect=lambda _root, *args: {
                    ("remote", "get-url", "origin"): "git@example/demo.git",
                    ("branch", "--show-current"): "feat/demo",
                    ("rev-parse", "HEAD"): "a" * 40,
                    ("status", "--porcelain=v1", "--untracked-files=all"): "",
                }[args],
            ):
                runner.validate_job_binding(job, {"demo": binding})
                map_bound_job = runner.dataclasses.replace(
                    job, repository_map_sha256="c" * 64
                )
                runner.validate_job_binding(
                    map_bound_job,
                    {
                        "demo": binding,
                        "__repository_map__": {"sha256": "c" * 64},
                    },
                )
                with self.assertRaisesRegex(
                    runner.InputContractError, "repository map digest"
                ):
                    runner.validate_job_binding(
                        map_bound_job,
                        {
                            "demo": binding,
                            "__repository_map__": {"sha256": "d" * 64},
                        },
                    )
            bad_binding = dict(binding, candidate_head="b" * 40)
            with self.assertRaisesRegex(
                runner.InputContractError, "HEAD"
            ), mock.patch.object(runner, "_git", side_effect=lambda _root, *args: "a" * 40):
                runner.validate_job_binding(job, {"demo": bad_binding})

    def test_scheduler_keeps_two_failures_and_blocks_queued_jobs_without_submission(self) -> None:
        started: list[int] = []

        def worker(item: int) -> runner.CommandResult:
            started.append(item)
            return runner.CommandResult(
                status="fail" if item in {0, 1} else "pass",
                returncode=1 if item in {0, 1} else 0,
                stdout="",
                stderr="",
                elapsed_seconds=0.01,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256=f"{item + 1:064x}",
                repository=f"repo-{item}",
                job_id=f"job-{item}",
            )

        outcome = runner.run_bounded_jobs(
            (0, 1, 2),
            worker,
            max_workers=2,
            failure_predicate=lambda result: result.status != "pass",
            collect_failures=True,
        )
        self.assertEqual(set(started), {0, 1})
        self.assertEqual(set(outcome.results), {0, 1})
        self.assertEqual(outcome.first_failure, 0)
        self.assertEqual(outcome.cancelled, (2,))
        self.assertEqual({item: outcome.results[item].status for item in outcome.results}, {0: "fail", 1: "fail"})

    def test_cancellation_terminates_running_process_group_and_marks_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cancel = threading.Event()
            timer = threading.Timer(0.05, cancel.set)
            timer.start()
            try:
                result = runner.run_command(
                    command=(sys.executable, "-c", "import time; time.sleep(10)"),
                    cwd=root,
                    environment={"PATH": os.environ["PATH"]},
                    timeout_seconds=2,
                    cancel_event=cancel,
                )
            finally:
                timer.cancel()
            self.assertEqual(result.status, "blocked")
            self.assertTrue(result.cancelled)
            self.assertTrue(result.process_group_terminated)

    def test_child_environment_and_command_cache_are_secret_free(self) -> None:
        source = {
            "PATH": "/bin",
            "HOME": "/tmp/home",
            "JAVA_HOME": "/jdk",
            "CENTRAL_PASSWORD": "secret-central",
            "AWS_SECRET_ACCESS_KEY": "secret-aws",
            "MY_API_KEY": "secret-api",
            "SERVICE_TOKEN": "secret-token",
            "SERVICE_SECRET": "secret-secret",
            "SERVICE_KEY": "secret-key",
            "AWS_ACCESS_KEY_ID": "sentinel-aws-id",
            "MY_SECRET_ACCESS_KEY": "sentinel-my-secret",
        }
        environment = runner.sanitized_environment(source)
        self.assertEqual(set(environment), {"PATH", "HOME", "JAVA_HOME"})
        command = runner.redact_command(
            (
                "gradlew",
                "CENTRAL_PASSWORD=secret-central",
                "AWS_SECRET_ACCESS_KEY=sentinel-aws-secret",
                "AWS_ACCESS_KEY_ID=sentinel-aws-id",
                "MY_SECRET_ACCESS_KEY=sentinel-my-secret",
                "SERVICE_KEY=secret-key",
                "--password=secret-password",
                "--clientSecret",
                "sentinel-arg-camel",
                "access%54oken=sentinel-arg-encoded",
                "--my_apikey=sentinel-arg-compound",
                "to%00ken=sentinel-arg-control",
                "--to%E2%80%8Bken=sentinel-arg-format",
                "to%09ken=sentinel-arg-tab",
                "--to%0Aken=sentinel-arg-lf",
                "--my_to%0Dken=sentinel-arg-namespaced-cr",
                "access%255Ftoken=sentinel-arg-nested",
                "to+ken=sentinel-arg-plus",
                "to%u006ben=sentinel-arg-residual-percent",
                "ｔｏｋｅｎ=sentinel-arg-fullwidth-token",
                "to%EF%BC%8500ken=sentinel-arg-fullwidth-percent",
                "--myapikey=sentinel-arg-compound-prefix",
                "apikeyfoo=sentinel-arg-compound-suffix",
                "mytoken=sentinel-arg-contiguous",
                "token＝sentinel-arg-unicode-delimiter",
                "to\nken=sentinel-arg-cross-line",
                "sessionFactorySession=sentinel-arg-session-factory-session",
                "myAuthorization=sentinel-arg-authorization",
                "authorizationHeader=sentinel-arg-authorization-header",
                "proxyAuthorization=sentinel-arg-proxy-authorization",
                "cookieHeader=sentinel-arg-cookie-header",
                "setCookieHeader=sentinel-arg-set-cookie-header",
                "Authorization: Bear\r\n er sentinel-arg-folded-authorization",
            )
        )
        rendered_command = " ".join(command)
        for sentinel in (
            "secret",
            "sentinel-arg-camel",
            "sentinel-arg-encoded",
            "sentinel-arg-compound",
            "sentinel-arg-control",
            "sentinel-arg-format",
            "sentinel-arg-tab",
            "sentinel-arg-lf",
            "sentinel-arg-namespaced-cr",
            "sentinel-arg-nested",
            "sentinel-arg-plus",
            "sentinel-arg-residual-percent",
            "sentinel-arg-fullwidth-token",
            "sentinel-arg-fullwidth-percent",
            "sentinel-arg-compound-prefix",
            "sentinel-arg-compound-suffix",
            "sentinel-arg-contiguous",
            "sentinel-arg-unicode-delimiter",
            "sentinel-arg-cross-line",
            "sentinel-arg-session-factory-session",
            "sentinel-arg-authorization",
            "sentinel-arg-authorization-header",
            "sentinel-arg-proxy-authorization",
            "sentinel-arg-cookie-header",
            "sentinel-arg-set-cookie-header",
            "sentinel-arg-folded-authorization",
        ):
            self.assertNotIn(sentinel, rendered_command)
        self.assertEqual(
            runner._redact_value(
                {
                    "accessToken": "sentinel-meta-camel",
                    "my_apikey": "sentinel-meta-compound",
                    "to%00ken": "sentinel-meta-control",
                    "to%E2%80%8Bken": "sentinel-meta-format",
                    "to%1B%5B31mken": "sentinel-meta-ansi",
                    "to%09ken": "sentinel-meta-tab",
                    "to%0Aken": "sentinel-meta-lf",
                    "my_to%0Dken": "sentinel-meta-namespaced-cr",
                    "access%255Ftoken": "sentinel-meta-nested",
                    "to+ken": "sentinel-meta-plus",
                    "to%u006ben": "sentinel-meta-residual-percent",
                    "ｔｏｋｅｎ": "sentinel-meta-fullwidth-token",
                    "to%EF%BC%8500ken": "sentinel-meta-fullwidth-percent",
                    "myapikey": "sentinel-meta-compound-prefix",
                    "apikeyfoo": "sentinel-meta-compound-suffix",
                    "mytoken": "sentinel-meta-contiguous-token",
                    "mykey": "sentinel-meta-contiguous-key",
                    "to\u200bken": "sentinel-meta-raw-format",
                    "sessionFactorySession": "sentinel-meta-session-factory-session",
                    "myAuthorization": "sentinel-meta-authorization",
                    "authorizationHeader": "sentinel-meta-authorization-header",
                    "proxyAuthorization": "sentinel-meta-proxy-authorization",
                    "cookieHeader": "sentinel-meta-cookie-header",
                    "setCookieHeader": "sentinel-meta-set-cookie-header",
                    "safe": "ok",
                }
            ),
            {"safe": "ok"},
        )
        self.assertEqual(
            runner._redact_value(
                {
                    "safe": (
                        "Authorization: Bear\r\n er sentinel-meta-folded-authorization"
                    )
                }
            ),
            {"safe": "<redacted>"},
        )
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory).resolve()
            key = "a" * 64
            runner.write_cache_entry(
                cache,
                key,
                b"CENTRAL_PASSWORD=secret-central\n"
                b"AWS_SECRET_ACCESS_KEY=sentinel-aws-secret\n"
                b"AWS_ACCESS_KEY_ID=sentinel-aws-id\n"
                b"MY_SECRET_ACCESS_KEY=sentinel-my-secret\n"
                b"SERVICE_KEY=secret-key\n"
                b"Cookie: session=sentinel-cookie-cache\n"
                b"session=sentinel-session-cache\n"
                b"TOKEN%252525253Dsentinel-deep-cache\n"
                b"token\nsuffix=sentinel-fragment-cache\n"
                b"sessionFactorySession=sentinel-session-factory-cache\n"
                b"myAuthorization=sentinel-authorization-cache\n"
                b"authorizationHeader=sentinel-authorization-header-cache\n"
                b"proxyAuthorization=sentinel-proxy-authorization-cache\n"
                b"cookieHeader=sentinel-cookie-header-cache\n"
                b"setCookieHeader=sentinel-set-cookie-header-cache\n"
                b"Authorization: Bear\r\n er sentinel-folded-authorization-cache\n",
                metadata={
                    "accessToken": "sentinel-meta-camel",
                    "my_apikey": "sentinel-meta-compound",
                    "to%00ken": "sentinel-meta-control",
                    "to%E2%80%8Bken": "sentinel-meta-format",
                    "to%1B%5B31mken": "sentinel-meta-ansi",
                    "to%09ken": "sentinel-meta-tab",
                    "to%0Aken": "sentinel-meta-lf",
                    "my_to%0Dken": "sentinel-meta-namespaced-cr",
                    "access%255Ftoken": "sentinel-meta-nested",
                    "to+ken": "sentinel-meta-plus",
                    "to%u006ben": "sentinel-meta-residual-percent",
                    "ｔｏｋｅｎ": "sentinel-meta-fullwidth-token",
                    "to%EF%BC%8500ken": "sentinel-meta-fullwidth-percent",
                    "myapikey": "sentinel-meta-compound-prefix",
                    "apikeyfoo": "sentinel-meta-compound-suffix",
                    "mytoken": "sentinel-meta-contiguous-token",
                    "mykey": "sentinel-meta-contiguous-key",
                    "to\u200bken": "sentinel-meta-raw-format",
                    "safe": "ok",
                },
            )
            output = runner.read_cache_entry(cache, key)
            self.assertIsNotNone(output)
            self.assertNotIn("secret-central", output["output"])
            self.assertNotIn("secret-key", output["output"])
            self.assertNotIn("sentinel-aws-secret", output["output"])
            self.assertNotIn("sentinel-aws-id", output["output"])
            self.assertNotIn("sentinel-my-secret", output["output"])
            self.assertNotIn("sentinel-cookie-cache", output["output"])
            self.assertNotIn("sentinel-session-cache", output["output"])
            self.assertNotIn("sentinel-deep-cache", output["output"])
            self.assertNotIn("sentinel-fragment-cache", output["output"])
            self.assertNotIn("sentinel-session-factory-cache", output["output"])
            self.assertNotIn("sentinel-authorization-cache", output["output"])
            self.assertNotIn("sentinel-authorization-header-cache", output["output"])
            self.assertNotIn("sentinel-proxy-authorization-cache", output["output"])
            self.assertNotIn("sentinel-cookie-header-cache", output["output"])
            self.assertNotIn("sentinel-set-cookie-header-cache", output["output"])
            self.assertNotIn("sentinel-folded-authorization-cache", output["output"])
            cache_text = (cache / f"{key}.json").read_text(encoding="utf-8")
            self.assertNotIn("sentinel-meta-camel", cache_text)
            self.assertNotIn("sentinel-meta-compound", cache_text)
            self.assertNotIn("sentinel-meta-control", cache_text)
            self.assertNotIn("sentinel-meta-format", cache_text)
            self.assertNotIn("sentinel-meta-ansi", cache_text)
            self.assertNotIn("sentinel-meta-tab", cache_text)
            self.assertNotIn("sentinel-meta-lf", cache_text)
            self.assertNotIn("sentinel-meta-namespaced-cr", cache_text)
            self.assertNotIn("sentinel-meta-nested", cache_text)
            self.assertNotIn("sentinel-meta-plus", cache_text)
            self.assertNotIn("sentinel-meta-residual-percent", cache_text)
            self.assertNotIn("sentinel-meta-fullwidth-token", cache_text)
            self.assertNotIn("sentinel-meta-fullwidth-percent", cache_text)
            self.assertNotIn("sentinel-meta-compound-prefix", cache_text)
            self.assertNotIn("sentinel-meta-compound-suffix", cache_text)
            self.assertNotIn("sentinel-meta-contiguous-token", cache_text)
            self.assertNotIn("sentinel-meta-contiguous-key", cache_text)
            self.assertNotIn("sentinel-meta-raw-format", cache_text)
            self.assertEqual(output["safe"], "ok")


if __name__ == "__main__":
    unittest.main()
