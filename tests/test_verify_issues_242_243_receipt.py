from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify-issues-242-243-receipt.py"
SPEC = importlib.util.spec_from_file_location("issues_242_243_receipt", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
receipt = importlib.util.module_from_spec(SPEC)
sys.modules["issues_242_243_receipt"] = receipt
SPEC.loader.exec_module(receipt)

RUNNER_PATH = SCRIPT_PATH.with_name("run-issues-242-243-validation.py")
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "issues_242_243_validation_runner_for_receipt_test", RUNNER_PATH
)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
runner = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules["issues_242_243_validation_runner_for_receipt_test"] = runner
RUNNER_SPEC.loader.exec_module(runner)


class Issues242243ReceiptTest(unittest.TestCase):
    def test_repository_inventory_reuses_catalog_candidate_authority(self) -> None:
        candidate = receipt._catalog_candidate_module()
        self.assertEqual(receipt.CATALOG_NAMES, candidate.CATALOG_REPOSITORIES)
        self.assertEqual(receipt.PUBLISHER_NAMES, frozenset(candidate.PUBLISHER_REPOSITORIES))
        self.assertEqual(receipt.SIGNING_NAMES, frozenset(candidate.SIGNING_REPOSITORIES))

    def test_git_failure_and_cli_errors_reuse_credential_redaction(self) -> None:
        raw = (
            "fatal: access_token=sentinel-access-token\n"
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
            "fatal: token:\r\nsentinel-colon-value"
        )
        failure = subprocess.CalledProcessError(128, ["git", "status"], stderr=raw)
        with mock.patch.object(receipt.subprocess, "run", side_effect=failure):
            with self.assertRaises(receipt.ReceiptError) as raised:
                receipt._git(Path("/tmp/example"), "status")
        for sentinel in (
            "sentinel-access-token",
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
        ):
            self.assertNotIn(sentinel, str(raised.exception))

        stderr = io.StringIO()
        with mock.patch.object(
            receipt,
            "validate_receipt",
            side_effect=receipt.ReceiptError("client_secret=sentinel-client-secret"),
        ), redirect_stderr(stderr):
            exit_code = receipt.main(["validate", "/tmp/receipt.json"])
        self.assertEqual(exit_code, 2)
        self.assertNotIn("sentinel-client-secret", stderr.getvalue())
        self.assertIn("<redacted>", stderr.getvalue())

    def git(
        self,
        root: Path,
        *args: str,
        input_bytes: bytes | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            input=input_bytes,
            capture_output=True,
            check=True,
            env=merged_env,
        )
        return completed.stdout.decode().strip()

    def make_repository(self, workspace: Path, name: str) -> dict[str, object]:
        root = workspace / name
        (root / "gradle").mkdir(parents=True)
        (root / "gradle/libs.versions.toml").write_text(
            '[versions]\ndemo = "1.0.0"\n', encoding="utf-8"
        )
        if name == receipt.CENTRAL_NAME:
            source = root / receipt.CANONICAL_SOURCE_RELATIVE
            source.parent.mkdir(parents=True)
            source.write_text("canonical signing helper\n", encoding="utf-8")
            (root / "build.gradle.kts").write_text(
                "plugins { `java-platform` }\n", encoding="utf-8"
            )
            init_script = root / receipt.CANDIDATE_INIT_SCRIPT_RELATIVE
            init_script.parent.mkdir(parents=True, exist_ok=True)
            init_script.write_bytes(
                (RUNNER_PATH.parents[1] / runner.CANDIDATE_INIT_SCRIPT_RELATIVE).read_bytes()
            )
        if name in receipt.SIGNING_NAMES:
            target = root / receipt.GENERATED_SIGNING_TARGET_RELATIVE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(
                receipt._load_signing_sync_module().render_generated_content(
                    b"canonical signing helper\n"
                )
            )
        self.git(root.parent, "init", "-b", "candidate", str(root))
        origin = f"git@github.com:bluetape4k/{name}.git"
        self.git(root, "remote", "add", "origin", origin)
        self.git(root, "config", "user.name", "Receipt Test")
        self.git(root, "config", "user.email", "receipt@example.invalid")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "fixture")
        head = self.git(root, "rev-parse", "HEAD")
        self.git(root, "update-ref", "refs/remotes/origin/develop", head)
        role = "central" if name == receipt.CENTRAL_NAME else receipt._infer_role(name)
        return {
            "name": name,
            "role": role,
            "canonical_path": str(root.resolve()),
            "candidate_worktree": str(root.resolve()),
            "origin": origin,
            "base_ref": "origin/develop",
            "base_sha": head,
            "candidate_branch": "candidate",
            "candidate_head": head,
            "clean": True,
            "exact_head": True,
            "validation_only": role == "validation-only",
        }

    def make_fixture(self) -> tuple[Path, Path, dict[str, object]]:
        workspace = Path(tempfile.mkdtemp(prefix="issues-242-243-")).resolve()
        entries = [self.make_repository(workspace, name) for name in receipt.ALL_NAMES]
        map_path = workspace / "build/issues-242-243/repository-map.json"
        map_path.parent.mkdir(parents=True)
        catalog_entries = entries[: len(receipt.CATALOG_NAMES)]

        def strict_entry(item: dict[str, object]) -> dict[str, object]:
            root = Path(str(item["candidate_worktree"]))
            return {
                "root": str(root),
                "catalog": str(root / "gradle/libs.versions.toml"),
                "origin": item["origin"],
                "branch": item["candidate_branch"],
                "base_sha": item["base_sha"],
                "expected_head": item["candidate_head"],
                "clean": True,
            }

        repository_map = {
            "schema_version": 1,
            "central": strict_entry(catalog_entries[0]),
            "repositories": {
                item["name"].removeprefix("bluetape4k-"): strict_entry(item)
                for item in catalog_entries[1:]
            },
        }
        map_bytes = receipt.canonical_json_bytes(repository_map)
        map_path.write_bytes(map_bytes)
        central = next(item for item in entries if item["name"] == receipt.CENTRAL_NAME)
        source_path = Path(str(central["candidate_worktree"])) / receipt.CANONICAL_SOURCE_RELATIVE
        source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        repository_receipts = []
        for item in entries[: len(receipt.CATALOG_NAMES)]:
            repository_receipts.append(
                {
                    "name": item["name"],
                    "role": item["role"],
                    "origin": item["origin"],
                    "base_ref": item["base_ref"],
                    "base_sha": item["base_sha"],
                    "candidate_branch": item["candidate_branch"],
                    "candidate_worktree": item["candidate_worktree"],
                    "candidate_head": item["candidate_head"],
                    "clean": True,
                    "exact_head": True,
                    "state": "discovered",
                    "signing_sha256": source_digest,
                }
            )
        consumers = []
        for item in entries[len(receipt.CATALOG_NAMES) :]:
            consumers.append(
                {
                    "name": item["name"],
                    "role": "consumer",
                    "origin": item["origin"],
                    "base_ref": item["base_ref"],
                    "base_sha": item["base_sha"],
                    "candidate_branch": item["candidate_branch"],
                    "candidate_worktree": item["candidate_worktree"],
                    "candidate_head": item["candidate_head"],
                    "clean": True,
                    "exact_head": True,
                    "state": "discovered",
                    "signing_sha256": source_digest,
                    "catalog_ref": "candidate/catalog",
                    "catalog_sha256": "a" * 64,
                    "catalog_source": "local-candidate",
                    "bom_coordinate": "io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local",
                    "local_override": "not-applicable",
                    "graphs": [
                        {
                            "coordinate": "ai.timefold.solver:timefold-solver-core",
                            "configuration": "testRuntimeClasspath",
                            "before_version": "2.4.0",
                            "after_version": "2.6.0",
                            "selection_reason": "selected by candidate BOM",
                            "output_sha256": "b" * 64,
                        }
                    ],
                }
            )
        command = {
            "repository": receipt.CENTRAL_NAME,
            "command": "./gradlew build",
            "jdk": "25",
            "gradle": "9.7.0",
            "configuration": "testRuntimeClasspath",
            "elapsed_seconds": 1.0,
            "cache": "isolated",
            "result": "pass",
            "output_sha256": "c" * 64,
        }
        document = {
            "schema_version": receipt.SCHEMA_VERSION,
            "issues": [242, 243],
            "current_state": "discovered",
            "validation_budget": {
                "total_seconds": 5400,
                "elapsed_seconds": 0.0,
                "remaining_seconds": 5400.0,
            },
            "repository_map": {"path": str(map_path), "sha256": receipt.sha256_bytes(map_bytes)},
            "central": {
                "base_sha": central["base_sha"],
                "candidate_head": central["candidate_head"],
                "clean": True,
                "exact_head": True,
                "state": "discovered",
            },
            "canonical_signing_source": {"path": str(source_path.resolve()), "sha256": source_digest},
            "candidate_artifact_manifest": None,
            "evidence_cache_root": None,
            "repositories": repository_receipts,
            "consumers": consumers,
            "commands": [command],
            "phases": [
                {
                    "name": "discover",
                    "result": "pass",
                    "output_sha256": "d" * 64,
                    "elapsed_seconds": 0.0,
                    "reserved_seconds": 0.0,
                    "job_ids": [],
                }
            ],
            "failure_record": [],
            "rollback_record": [],
            "evidence_commit": None,
        }
        receipt_path = workspace / "build/issues-242-243/local-receipt.json"
        receipt_path.write_bytes(receipt.canonical_json_bytes(document))
        return workspace, receipt_path, document

    def make_adoptable(self, document: dict[str, object]) -> None:
        workspace = Path(str(document["repository_map"]["path"])).parents[2]
        cache_directory = workspace / "build/issues-242-243/cache"
        cache_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(cache_directory, 0o700)
        candidate_repository = workspace / "build/issues-242-243/candidate-m2"
        artifact_directory = (
            candidate_repository
            / "io/github/bluetape4k/bluetape4k-dependencies"
            / runner.CANDIDATE_BOM_VERSION
        )
        artifact_directory.mkdir(parents=True, exist_ok=True)
        for name, payload in (
            (
                f"bluetape4k-dependencies-{runner.CANDIDATE_BOM_VERSION}.pom",
                (
                    "<project><groupId>io.github.bluetape4k</groupId>"
                    "<artifactId>bluetape4k-dependencies</artifactId>"
                    f"<version>{runner.CANDIDATE_BOM_VERSION}</version></project>\n"
                ).encode(),
            ),
            (
                f"bluetape4k-dependencies-{runner.CANDIDATE_BOM_VERSION}.module",
                runner.canonical_json_bytes(
                    {
                        "component": {
                            "group": "io.github.bluetape4k",
                            "module": "bluetape4k-dependencies",
                            "version": runner.CANDIDATE_BOM_VERSION,
                        }
                    }
                ),
            ),
        ):
            (artifact_directory / name).write_bytes(payload)
        artifact_manifest = runner.candidate_artifact_manifest(candidate_repository)
        central = next(
            item for item in document["repositories"] if item["name"] == receipt.CENTRAL_NAME
        )
        catalog_path = Path(str(central["candidate_worktree"])) / "gradle/libs.versions.toml"
        catalog_sha256 = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        artifact_manifest["central_head"] = document["central"]["candidate_head"]
        artifact_manifest["catalog_sha256"] = catalog_sha256
        document["candidate_artifact_manifest"] = artifact_manifest

        commands: list[dict[str, object]] = []
        results_by_phase: dict[str, list[runner.CommandResult]] = {}
        job_index = 0

        def add_command(
            repository: str,
            phase: str,
            *,
            coordinate: str | None = None,
            selected_version: str | None = None,
            override_disposition: str = "baseline",
        ) -> None:
            nonlocal job_index
            if phase == "signing-buildsrc":
                task_set = ["compileKotlin", "test"]
            elif phase == "candidate-bom-publication":
                task_set = ["publishBluetapeDependenciesPublicationToMavenLocal"]
            elif phase == "consumers":
                task_set = receipt.ADOPTION_CONSUMER_TASKS[repository]
            elif phase == "publication-poms":
                task_set = ["verify-publication-poms.py"]
            elif phase.startswith("timefold-graphs-"):
                task_set = receipt.ADOPTION_GRAPH_TASKS[repository]
            else:
                task_set = ["dependencyInsight"]
            arguments: list[str] = []
            if phase == "candidate-bom-publication":
                arguments.extend(
                    [
                        f"-Dmaven.repo.local={candidate_repository}",
                        f"-PbaseVersion={runner.CANDIDATE_BOM_VERSION}",
                        "-PsnapshotVersion=",
                    ]
                )
            elif phase in {"timefold-graphs-candidate", "consumers"}:
                central_root = Path(str(central["candidate_worktree"]))
                arguments.extend(
                    [
                        "--init-script",
                        str(central_root / receipt.CANDIDATE_INIT_SCRIPT_RELATIVE),
                        f"-D{receipt.CANDIDATE_REPOSITORY_PROPERTY}={candidate_repository}",
                        f"-D{receipt.CANDIDATE_VERSION_PROPERTY}={runner.CANDIDATE_BOM_VERSION}",
                    ]
                )
            if phase.startswith("timefold-graphs-"):
                arguments.extend(
                    [
                        "--configuration",
                        "testRuntimeClasspath",
                        "--dependency",
                        str(coordinate),
                    ]
                )
            job = runner.ValidationJob(
                repository=repository,
                phase=phase,
                cwd=Path("/fixture"),
                command=("./gradlew", *task_set, *arguments),
                configuration=(
                    "candidate-bom-publication"
                    if phase == "candidate-bom-publication"
                    else "testRuntimeClasspath"
                ),
                task_set=tuple(task_set),
                repository_head=(
                    str(document["central"]["candidate_head"])
                    if phase == "candidate-bom-publication"
                    else "a" * 40
                ),
                helper_sha256=(
                    hashlib.sha256(
                        (
                            Path(str(central["candidate_worktree"]))
                            / (
                                receipt.CANDIDATE_INIT_SCRIPT_RELATIVE
                                if phase in {"timefold-graphs-candidate", "consumers"}
                                else receipt.GENERATED_SIGNING_TARGET_RELATIVE
                            )
                        ).read_bytes()
                    ).hexdigest()
                    if phase
                    in {
                        "candidate-bom-publication",
                        "timefold-graphs-candidate",
                        "consumers",
                    }
                    else "b" * 64
                ),
                catalog_sha256=catalog_sha256,
                bom_sha256=(
                    hashlib.sha256(
                        (
                            Path(str(central["candidate_worktree"]))
                            / "build.gradle.kts"
                        ).read_bytes()
                    ).hexdigest()
                    if phase == "candidate-bom-publication"
                    else
                    str(artifact_manifest["sha256"])
                    if override_disposition == "candidate"
                    else "d" * 64
                ),
                jdk_version="25",
                gradle_version="9.7.0",
                arguments=tuple(arguments),
                candidate_maven_repository=(
                    candidate_repository
                    if override_disposition == "candidate"
                    and phase != "candidate-bom-publication"
                    else None
                ),
                produced_maven_repository=(
                    candidate_repository
                    if phase == "candidate-bom-publication"
                    else None
                ),
                coordinate=coordinate or "",
                job_id=f"{phase}:{job_index}:{repository}",
            )
            job_index += 1
            output = ""
            if coordinate:
                output = (
                    f"{coordinate}:{selected_version}\n"
                    "  Selection reasons:\n"
                    "      - selected by immutable fixture\n"
                )
            output_bytes = output.encode("utf-8")
            output_sha256 = hashlib.sha256(output_bytes).hexdigest()
            cache_output_path = cache_directory / f"{job.cache_key}.output"
            runner._atomic_write(cache_output_path, output_bytes)
            result = runner.CommandResult(
                status="pass",
                returncode=0,
                stdout=output,
                stderr="",
                elapsed_seconds=1.0,
                timed_out=False,
                process_group_terminated=False,
                termination_signal=None,
                output_sha256=output_sha256,
                job_id=job.job_id,
                repository=repository,
                cache_key=job.cache_key,
                cache_output_path=str(cache_output_path),
            )
            commands.append(runner._bound_command_record(job, result))
            results_by_phase.setdefault(phase, []).append(result)

        for repository in receipt.SIGNING_NAMES:
            add_command(repository, "signing-buildsrc")
        add_command(
            receipt.CENTRAL_NAME,
            "candidate-bom-publication",
            override_disposition="candidate",
        )
        producer_record = commands[-1]
        artifact_manifest["source_tree_sha256"] = runner.git_source_tree_sha256(
            Path(str(central["candidate_worktree"])),
            str(document["central"]["candidate_head"]),
        )
        artifact_manifest["producer_job_id"] = producer_record["job_id"]
        artifact_manifest["producer_input_sha256"] = producer_record["input_sha256"]
        artifact_manifest["producer_output_sha256"] = producer_record["output_sha256"]
        for phase, selected, disposition in (
            ("timefold-graphs-baseline", "2.4.0", "baseline"),
            ("timefold-graphs-candidate", "2.6.0", "candidate"),
        ):
            for repository, coordinates in receipt.ADOPTION_GRAPH_COORDINATES.items():
                for coordinate in coordinates:
                    add_command(
                        repository,
                        phase,
                        coordinate=coordinate,
                        selected_version=selected,
                        override_disposition=disposition,
                    )
        for repository in receipt.ADOPTION_GRAPH_COORDINATES:
            add_command(repository, "consumers", override_disposition="candidate")
        add_command("publication-poms", "publication-poms")
        phases = [
            {
                "name": "discover",
                "result": "pass",
                "output_sha256": "d" * 64,
                "elapsed_seconds": 0.0,
                "reserved_seconds": 0.0,
                "job_ids": [],
            }
        ]
        remaining = float(receipt.TOTAL_VALIDATION_BUDGET_SECONDS)
        elapsed_total = 0.0
        for phase_name in (
            "signing-buildsrc",
            "candidate-bom-publication",
            "timefold-graphs-baseline",
            "timefold-graphs-candidate",
            "consumers",
            "publication-poms",
        ):
            phase_results = results_by_phase[phase_name]
            elapsed = sum(item.elapsed_seconds for item in phase_results)
            phases.append(
                {
                    "name": phase_name,
                    "result": "pass",
                    "output_sha256": runner._phase_digest(
                        phase_name, phase_results, None
                    ),
                    "elapsed_seconds": elapsed,
                    "reserved_seconds": remaining,
                    "job_ids": [item.job_id for item in phase_results],
                }
            )
            remaining -= elapsed
            elapsed_total += elapsed
        phases.append(
            {
                "name": "candidate-bom-artifacts",
                "result": "pass",
                "output_sha256": artifact_manifest["sha256"],
                "elapsed_seconds": 0.0,
                "reserved_seconds": 0.0,
                "job_ids": [],
            }
        )
        document["validation_budget"] = {
            "total_seconds": receipt.TOTAL_VALIDATION_BUDGET_SECONDS,
            "elapsed_seconds": elapsed_total,
            "remaining_seconds": remaining,
        }
        document["evidence_cache_root"] = str(cache_directory)
        document["phases"] = phases
        document["commands"] = commands
        for consumer in document["consumers"]:
            coordinates = receipt.TIMEFOLD_CONSUMER_COORDINATES[consumer["name"]]
            consumer["graphs"] = [
                {
                    "coordinate": coordinate,
                    "configuration": "testRuntimeClasspath",
                    "before_version": "2.4.0",
                    "after_version": "2.6.0",
                    "selection_reason": (
                        "before: selected by immutable fixture; "
                        "after: selected by immutable fixture"
                    ),
                    "output_sha256": next(
                        item["output_sha256"]
                        for item in commands
                        if item["phase"] == "timefold-graphs-candidate"
                        and item["repository"] == consumer["name"]
                        and item["coordinate"] == coordinate
                    ),
                }
                for coordinate in coordinates
            ]

    def make_prospective_commit(self, root: Path, parent: str, content: bytes) -> str:
        blob = self.git(root, "hash-object", "-w", "--stdin", input_bytes=content)
        index = root / ".receipt-test-index"
        try:
            env = {"GIT_INDEX_FILE": str(index)}
            self.git(root, "read-tree", f"{parent}^{{tree}}", env=env)
            self.git(
                root,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{blob},{receipt.EVIDENCE_RECEIPT_PATH}",
                env=env,
            )
            tree = self.git(root, "write-tree", env=env)
            return self.git(
                root,
                "commit-tree",
                tree,
                "-p",
                parent,
                input_bytes=b"prospective receipt\n",
                env={
                    **env,
                    "GIT_AUTHOR_NAME": "Receipt Test",
                    "GIT_AUTHOR_EMAIL": "receipt@example.invalid",
                    "GIT_COMMITTER_NAME": "Receipt Test",
                    "GIT_COMMITTER_EMAIL": "receipt@example.invalid",
                },
            )
        finally:
            index.unlink(missing_ok=True)

    def mark_validated(self, document: dict[str, object]) -> None:
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "validated"
        document["central"]["state"] = "validated"
        document["current_state"] = "validated"

    def test_rejects_missing_repository(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"] = document["consumers"][:1]
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "consumer|repository"):
            receipt.validate_receipt(path)

    def test_rejects_blocked_or_prepared_repository(self) -> None:
        workspace, path, document = self.make_fixture()
        target = document["repositories"][1]
        for state in ("prepared", "blocked"):
            target["state"] = state
            document["current_state"] = state
            path.write_bytes(receipt.canonical_json_bytes(document))
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "validate", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, state)
            self.assertIn("validated", result.stderr, state)

    def test_rejects_digest_mismatch(self) -> None:
        workspace, path, document = self.make_fixture()
        document["canonical_signing_source"]["sha256"] = "e" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "SHA-256|digest"):
            receipt.validate_receipt(path)

    def test_rejects_missing_timefold_coordinate(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"][0]["graphs"][0].pop("coordinate")
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "graph|fields|coordinate"):
            receipt.validate_receipt(path)

    def test_rejects_secret_bearing_command(self) -> None:
        workspace, path, document = self.make_fixture()
        document["commands"][0]["command"] = "PASSWORD=sentinel ./gradlew test"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "secret|command"):
            receipt.validate_receipt(path)

    def test_accepts_exact_validated_repository_set(self) -> None:
        workspace, path, document = self.make_fixture()
        validated = receipt.validate_receipt(path)
        self.assertEqual(validated["issues"], [242, 243])
        self.assertEqual(len(validated["repositories"]), 10)
        self.assertEqual({item["name"] for item in validated["consumers"]}, set(receipt.CONSUMER_NAMES))

    def test_runner_command_records_round_trip_through_receipt_validator(self) -> None:
        workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        path.write_bytes(receipt.canonical_json_bytes(document))

        validated = receipt.validate_receipt(path)
        signing = [
            item for item in validated["commands"] if item["phase"] == "signing-buildsrc"
        ]
        self.assertEqual(
            {item["repository"] for item in signing},
            set(runner.SIGNING_REPOSITORIES),
        )
        self.assertTrue(all(item["task_set"] == ["compileKotlin", "test"] for item in signing))
        self.assertTrue(all(item["arguments"] == [] for item in signing))

    def test_validated_receipt_rehashes_cache_outputs_and_candidate_repository(self) -> None:
        _workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        self.mark_validated(document)
        path.write_bytes(receipt.canonical_json_bytes(document))
        receipt.validate_receipt(path)

        cache_output = Path(document["commands"][0]["cache_output_path"])
        cache_output.write_bytes(cache_output.read_bytes() + b"tampered\n")
        with self.assertRaisesRegex(receipt.ReceiptError, "cache output SHA-256"):
            receipt.validate_receipt(path)

        self.make_adoptable(document)
        path.write_bytes(receipt.canonical_json_bytes(document))
        artifact = next(
            Path(document["candidate_artifact_manifest"]["repository_path"]).rglob("*.pom")
        )
        artifact.write_bytes(artifact.read_bytes() + b"tampered\n")
        with self.assertRaisesRegex(receipt.ReceiptError, "repository file manifest"):
            receipt.validate_receipt(path)

    def test_terminal_receipt_rejects_synthetic_cache_and_budget_job_bindings(self) -> None:
        _workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        self.mark_validated(document)
        document["commands"][0]["cache_output_path"] = "/missing/synthetic.output"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "cache output"):
            receipt.validate_receipt(path)

        self.make_adoptable(document)
        self.mark_validated(document)
        original_output = Path(document["commands"][0]["cache_output_path"])
        sibling_cache = original_output.parent.parent / "unbound-cache"
        sibling_cache.mkdir()
        sibling_output = sibling_cache / original_output.name
        sibling_output.write_bytes(original_output.read_bytes())
        document["commands"][0]["cache_output_path"] = str(sibling_output)
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "receipt cache root"):
            receipt.validate_receipt(path)

        self.make_adoptable(document)
        self.mark_validated(document)
        phase = next(
            item for item in document["phases"] if item["name"] == "signing-buildsrc"
        )
        phase["reserved_seconds"] -= 1.0
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "budget reservation"):
            receipt.validate_receipt(path)

        self.make_adoptable(document)
        self.mark_validated(document)
        phase = next(
            item for item in document["phases"] if item["name"] == "signing-buildsrc"
        )
        phase["job_ids"] = phase["job_ids"][1:]
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "job IDs"):
            receipt.validate_receipt(path)

    def test_terminal_receipt_rejects_candidate_producer_provenance_tampering(self) -> None:
        _workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        self.mark_validated(document)
        document["candidate_artifact_manifest"]["source_tree_sha256"] = "0" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "source tree SHA-256"):
            receipt.validate_receipt(path)

        self.make_adoptable(document)
        self.mark_validated(document)
        document["candidate_artifact_manifest"]["producer_input_sha256"] = "0" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "producer provenance"):
            receipt.validate_receipt(path)

    def test_terminal_receipt_binds_candidate_commands_to_artifact_manifest(self) -> None:
        _workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        self.mark_validated(document)
        command = next(
            item
            for item in document["commands"]
            if item["phase"] == "timefold-graphs-candidate"
        )
        command["bom_sha256"] = "0" * 64
        command["cache_key"] = runner.cache_key(
            repository=command["repository"],
            repository_head=command["repository_head"],
            helper_sha256=command["helper_sha256"],
            catalog_sha256=command["catalog_sha256"],
            bom_sha256=command["bom_sha256"],
            task_set=command["task_set"],
            configuration=command["configuration"],
            jdk_version=command["jdk"],
            gradle_version=command["gradle"],
            arguments=command["arguments"],
        )
        previous_output = Path(command["cache_output_path"])
        rebound_output = previous_output.with_name(f'{command["cache_key"]}.output')
        rebound_output.write_bytes(previous_output.read_bytes())
        os.chmod(rebound_output, 0o600)
        command["cache_output_path"] = str(rebound_output)
        immutable_input = {
            "schema_version": 1,
            "repository": command["repository"],
            "phase": command["phase"],
            "command": command["command"],
            "repository_head": command["repository_head"],
            "helper_sha256": command["helper_sha256"],
            "catalog_sha256": command["catalog_sha256"],
            "bom_sha256": command["bom_sha256"],
            "task_set": command["task_set"],
            "configuration": command["configuration"],
            "jdk": command["jdk"],
            "gradle": command["gradle"],
            "coordinate": command["coordinate"],
            "override_disposition": command["override_disposition"],
            "arguments": command["arguments"],
            "gradle_home_policy": command["gradle_home_policy"],
        }
        command["input_sha256"] = receipt.sha256_bytes(
            receipt.canonical_json_bytes(immutable_input)
        )
        path.write_bytes(receipt.canonical_json_bytes(document))

        with self.assertRaisesRegex(
            receipt.ReceiptError, "candidate consumer injection provenance"
        ):
            receipt.validate_receipt(path)

    def test_validated_state_requires_complete_terminal_evidence(self) -> None:
        workspace, path, document = self.make_fixture()
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "validated"
        document["central"]["state"] = "validated"
        document["current_state"] = "validated"
        path.write_bytes(receipt.canonical_json_bytes(document))

        with self.assertRaisesRegex(RuntimeError, "validated receipt is missing required phases"):
            receipt.validate_receipt(path)

    def test_partial_validation_derives_prepared_global_state(self) -> None:
        self.assertEqual(
            receipt._derive_global_state(["validated", "prepared", "discovered"]),
            "prepared",
        )
        self.assertEqual(
            receipt._derive_global_state(["validated", "adopted", "validated"]),
            "validated",
        )

    def test_rejects_malformed_schema_and_unknown_field(self) -> None:
        workspace, path, document = self.make_fixture()
        document["schema_version"] = 1
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "schema"):
            receipt.validate_receipt(path)
        document["schema_version"] = receipt.SCHEMA_VERSION
        document["unexpected"] = True
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "fields"):
            receipt.validate_receipt(path)

    def test_rejects_dirty_and_mismatched_worktree(self) -> None:
        workspace, path, document = self.make_fixture()
        root = Path(document["repositories"][1]["candidate_worktree"])
        (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "dirty|not clean"):
            receipt.validate_receipt(path)
        (root / "dirty.txt").unlink()
        document["repositories"][1]["candidate_head"] = "1" * 40
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "candidate SHA|HEAD"):
            receipt.validate_receipt(path)

    def test_rejects_consumer_origin_mismatch(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"][0]["origin"] = (
            "git@github.com:bluetape4k/not-the-workshop.git"
        )
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "origin"):
            receipt.validate_receipt(path)

    def test_rejects_graph_field_omission_and_invalid_hash(self) -> None:
        workspace, path, document = self.make_fixture()
        document["consumers"][1]["graphs"][0]["output_sha256"] = "not-a-digest"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "SHA-256|graph"):
            receipt.validate_receipt(path)
        document["consumers"][1]["graphs"][0]["output_sha256"] = "b" * 64
        document["repositories"][2]["base_sha"] = "not-a-commit"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "commit|base"):
            receipt.validate_receipt(path)

    def test_rejects_control_characters_and_invalid_evidence_path(self) -> None:
        workspace, path, document = self.make_fixture()
        document["phases"][0]["name"] = "discover\x1b[31m"
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "control|ANSI"):
            receipt.validate_receipt(path)

    def test_adopted_receipt_checks_prospective_parent_path_and_blob_digest(self) -> None:
        workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["central"]["state"] = "adopted"
        document["current_state"] = "adopted"
        central_root = Path(document["repositories"][0]["candidate_worktree"])
        content = b"tracked local receipt bytes\n"
        prospective = self.make_prospective_commit(
            central_root, document["central"]["candidate_head"], content
        )
        document["evidence_commit"] = {
            "parent": document["central"]["candidate_head"],
            "path": receipt.EVIDENCE_RECEIPT_PATH,
            "bytes_sha256": hashlib.sha256(content).hexdigest(),
        }
        path.write_bytes(receipt.canonical_json_bytes(document))
        receipt.validate_receipt(path, evidence_commit=prospective)
        document["evidence_commit"]["parent"] = "1" * 40
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "parent"):
            receipt.validate_receipt(path, evidence_commit=prospective)

    def test_adopted_receipt_rejects_path_and_digest_mismatch(self) -> None:
        workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["central"]["state"] = "adopted"
        document["current_state"] = "adopted"
        central_root = Path(document["repositories"][0]["candidate_worktree"])
        content = b"tracked local receipt bytes\n"
        prospective = self.make_prospective_commit(
            central_root, document["central"]["candidate_head"], content
        )
        document["evidence_commit"] = {
            "parent": document["central"]["candidate_head"],
            "path": "docs/releases/not-allowlisted.json",
            "bytes_sha256": hashlib.sha256(content).hexdigest(),
        }
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "allowlisted"):
            receipt.validate_receipt(path, evidence_commit=prospective)
        document["evidence_commit"]["path"] = receipt.EVIDENCE_RECEIPT_PATH
        document["evidence_commit"]["bytes_sha256"] = "f" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(RuntimeError, "digest"):
            receipt.validate_receipt(path, evidence_commit=prospective)

    def test_atomic_write_preserves_mode_rejects_symlink_and_cas_failure_rolls_back(self) -> None:
        workspace, path, document = self.make_fixture()
        os.chmod(path, 0o640)
        receipt.write_atomic(path, b"replacement")
        self.assertEqual(path.read_bytes(), b"replacement")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        target = workspace / "target"
        target.write_bytes(b"target")
        link = workspace / "link"
        link.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            receipt.write_atomic(link, b"nope")
        linked_parent = workspace / "linked-parent"
        linked_parent.symlink_to(workspace / "real-parent", target_is_directory=True)
        (workspace / "real-parent").mkdir()
        with self.assertRaisesRegex(RuntimeError, "symlink|canonical"):
            receipt.write_atomic(linked_parent / "receipt.json", b"nope")
        path.write_bytes(receipt.canonical_json_bytes(document))
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "stale"):
            receipt.transition_receipt(
                path,
                repository=document["repositories"][1]["name"],
                from_state="discovered",
                to_state="prepared",
                expected_head="2" * 40,
                expected_signing_sha256=document["repositories"][1]["signing_sha256"],
            )
        self.assertEqual(path.read_bytes(), before)

    def test_central_transition_updates_both_central_representations(self) -> None:
        workspace, path, document = self.make_fixture()
        central = document["repositories"][0]
        updated = receipt.transition_receipt(
            path,
            repository=receipt.CENTRAL_NAME,
            from_state="discovered",
            to_state="prepared",
            expected_head=central["candidate_head"],
            expected_signing_sha256=central["signing_sha256"],
        )
        self.assertEqual(updated["central"]["state"], "prepared")
        self.assertEqual(updated["repositories"][0]["state"], "prepared")
        self.assertEqual(updated["current_state"], "prepared")

    def test_last_adopted_transition_derives_prospective_evidence_metadata(self) -> None:
        workspace, path, document = self.make_fixture()
        self.make_adoptable(document)
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["repositories"][0]["state"] = "validated"
        document["central"]["state"] = "validated"
        document["current_state"] = "validated"
        path.write_bytes(receipt.canonical_json_bytes(document))
        central_root = Path(document["repositories"][0]["candidate_worktree"])
        content = b"prospective adopted receipt\n"
        prospective = self.make_prospective_commit(
            central_root, document["central"]["candidate_head"], content
        )
        updated = receipt.transition_receipt(
            path,
            repository=receipt.CENTRAL_NAME,
            from_state="validated",
            to_state="adopted",
            expected_head=document["central"]["candidate_head"],
            expected_signing_sha256=document["repositories"][0]["signing_sha256"],
            evidence_commit=prospective,
        )
        self.assertEqual(updated["current_state"], "adopted")
        self.assertEqual(updated["evidence_commit"]["parent"], document["central"]["candidate_head"])
        self.assertEqual(updated["evidence_commit"]["path"], receipt.EVIDENCE_RECEIPT_PATH)
        self.assertEqual(
            updated["evidence_commit"]["bytes_sha256"],
            hashlib.sha256(content).hexdigest(),
        )

    def test_repository_ref_manifest_has_exact_signing_envelope(self) -> None:
        manifest_path = SCRIPT_PATH.parents[1] / "config/publishing-signing-repository-refs.json"
        manifest = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema-version"], 1)
        source_path = SCRIPT_PATH.parents[1] / manifest["canonical-source"]["path"]
        self.assertEqual(manifest["canonical-source"]["status"], "prepared")
        self.assertEqual(
            manifest["canonical-source"]["sha256"],
            hashlib.sha256(source_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(set(manifest["repositories"]), set(receipt.PUBLISHER_NAMES))
        self.assertNotIn("bluetape4k-experimental", manifest["repositories"])
        self.assertNotIn("timefold-workshop", manifest["repositories"])
        self.assertNotIn("clinic-appointment", manifest["repositories"])

    def test_signing_digests_are_bound_to_canonical_source(self) -> None:
        _workspace, path, document = self.make_fixture()
        document["repositories"][0]["signing_sha256"] = "f" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "signing digest mismatch"):
            receipt.validate_receipt(path)

    def test_generated_signing_helpers_are_read_back_from_every_publisher(self) -> None:
        _workspace, path, document = self.make_fixture()
        publisher = next(
            item
            for item in document["repositories"]
            if item["name"] != receipt.CENTRAL_NAME and item["name"] in receipt.SIGNING_NAMES
        )
        target = Path(publisher["candidate_worktree"]) / receipt.GENERATED_SIGNING_TARGET_RELATIVE
        self.git(
            Path(publisher["candidate_worktree"]),
            "update-index",
            "--assume-unchanged",
            receipt.GENERATED_SIGNING_TARGET_RELATIVE,
        )
        target.write_text("drift\n", encoding="utf-8")
        with self.assertRaisesRegex(
            receipt.ReceiptError, "generated signing helper mismatch"
        ):
            receipt.validate_receipt(path)

    def test_adopted_receipt_requires_complete_immutable_evidence(self) -> None:
        _workspace, path, document = self.make_fixture()
        for item in document["repositories"] + document["consumers"]:
            item["state"] = "adopted"
        document["central"]["state"] = "adopted"
        document["current_state"] = "adopted"
        document["evidence_commit"] = {
            "parent": document["central"]["candidate_head"],
            "path": receipt.EVIDENCE_RECEIPT_PATH,
            "bytes_sha256": "a" * 64,
        }
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "missing required phases"):
            receipt.validate_receipt(path, evidence_commit="b" * 40)

        _workspace, path, document = self.make_fixture()
        document["consumers"][0]["signing_sha256"] = "f" * 64
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "signing digest mismatch"):
            receipt.validate_receipt(path)

    def test_passing_candidate_graph_phase_requires_exact_consumer_ledger(self) -> None:
        _workspace, path, document = self.make_fixture()
        document["phases"].append(
            {
                "name": "timefold-graphs-candidate",
                "result": "pass",
                "output_sha256": "e" * 64,
                "elapsed_seconds": 0.0,
                "reserved_seconds": 0.0,
                "job_ids": [],
            }
        )
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "graph coordinates"):
            receipt.validate_receipt(path)

    def test_validation_budget_rejects_inconsistent_remaining_time(self) -> None:
        _workspace, path, document = self.make_fixture()
        document["validation_budget"]["remaining_seconds"] = 5400.0
        document["validation_budget"]["elapsed_seconds"] = 1.0
        path.write_bytes(receipt.canonical_json_bytes(document))
        with self.assertRaisesRegex(receipt.ReceiptError, "validation budget"):
            receipt.validate_receipt(path)

    def test_cli_exposes_validate_and_transition_modes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("validate", result.stdout)
        self.assertIn("transition", result.stdout)
        workspace, path, document = self.make_fixture()
        default = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate", str(path)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(default.returncode, 0)
        allowed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "validate",
                str(path),
                "--allow-discovered",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)


if __name__ == "__main__":
    unittest.main()
