from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "publishing-signing-smoke"
WRAPPER = REPO_ROOT / "gradlew"
ADAPTER = REPO_ROOT / "buildSrc" / "src" / "main" / "kotlin" / "PublishingSigningSupport.kt"
HELPER = REPO_ROOT / "buildSrc" / "src" / "main" / "kotlin" / "PublishingSigningKeySupport.kt"
BUILDSRC = REPO_ROOT / "buildSrc" / "build.gradle.kts"
SENTINEL_PASSWORD = "issue-242-243-smoke-password"
ARMOR_HEADER = "-----BEGIN PGP PRIVATE KEY BLOCK-----"
ARMOR_FOOTER = "-----END PGP PRIVATE KEY BLOCK-----"
FIXTURE_TASKS = (
    "publishMavenPublicationToTestRepository",
    "signMavenPublication",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_secure_directory(test_case: unittest.TestCase, path: Path) -> None:
    test_case.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700, path)


@unittest.skipUnless(
    shutil.which("gpg") and WRAPPER.exists() and shutil.which("java"),
    "requires gpg, the Gradle wrapper, and Java",
)
class PublishingSigningSmokeTest(unittest.TestCase):
    maxDiff = None

    def test_fixture_signs_a_publication_and_redacts_malformed_key_failure(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="i242243-", dir="/tmp"
        ) as temporary:
            root = Path(temporary).resolve()
            root.chmod(0o700)
            assert_secure_directory(self, root)
            fixture = root / "fixture"
            shutil.copytree(FIXTURE_ROOT, fixture, copy_function=shutil.copy2)
            fixture.chmod(0o700)
            self._copy_canonical_build_inputs(fixture)

            gnupg_home = root / "gnupg"
            gradle_home = root / "gradle-home"
            maven_home = root / "maven-repository"
            for path in (gnupg_home, gradle_home, maven_home):
                path.mkdir(mode=0o700)
                assert_secure_directory(self, path)

            key_id, armored_key = self._create_synthetic_key(gnupg_home)
            environment = {
                "GNUPGHOME": str(gnupg_home),
                "GRADLE_USER_HOME": str(gradle_home),
                "SIGNING_KEY_ID": key_id,
                "SIGNING_KEY": armored_key,
                "SIGNING_PASSWORD": SENTINEL_PASSWORD,
            }

            environment["TEST_MAVEN_REPOSITORY"] = str(maven_home)
            positive = self._run_fixture(fixture, environment)
            self._assert_redacted_output(positive.stdout + positive.stderr)
            if positive.returncode != 0:
                artifact = self._write_failure_artifact("positive", positive)
                self.fail(f"positive signing smoke failed; redacted artifact={artifact}")

            signatures = sorted(maven_home.rglob("*.asc"))
            self.assertTrue(signatures, "positive smoke did not publish an .asc artifact")
            for signature in signatures:
                self.assertTrue(signature.read_bytes(), signature)

            malformed_key = (
                f"{ARMOR_HEADER}\nmalformed-key-body-sentinel\n{ARMOR_FOOTER}"
            )
            negative_environment = dict(environment)
            negative_environment["SIGNING_KEY"] = malformed_key
            negative = self._run_fixture(
                fixture,
                negative_environment,
                clean_publication=True,
            )
            self._assert_redacted_output(negative.stdout + negative.stderr)
            if negative.returncode == 0:
                artifact = self._write_failure_artifact("negative", negative)
                self.fail(
                    "malformed signing key unexpectedly produced a successful publication; "
                    f"redacted artifact={artifact}"
                )

    def test_fixture_inputs_are_canonical_and_private_material_stays_out_of_argv(self) -> None:
        for path in (ADAPTER, HELPER, BUILDSRC):
            self.assertTrue(path.is_file(), path)
        self.assertTrue((FIXTURE_ROOT / "settings.gradle.kts").is_file())
        self.assertTrue((FIXTURE_ROOT / "build.gradle.kts").is_file())
        fixture_build = (FIXTURE_ROOT / "build.gradle.kts").read_text()
        self.assertIn("configurePublishingSigning(\"maven\")", fixture_build)
        self.assertIn('create<MavenPublication>("maven")', fixture_build)
        self.assertEqual(
            FIXTURE_TASKS,
            ("publishMavenPublicationToTestRepository", "signMavenPublication"),
        )

    def _copy_canonical_build_inputs(self, fixture: Path) -> None:
        build_src = fixture / "buildSrc"
        (build_src / "src" / "main" / "kotlin").mkdir(parents=True)
        shutil.copy2(BUILDSRC, build_src / "build.gradle.kts")
        shutil.copy2(
            ADAPTER,
            build_src / "src" / "main" / "kotlin" / ADAPTER.name,
        )
        shutil.copy2(
            HELPER,
            build_src / "src" / "main" / "kotlin" / HELPER.name,
        )
        for source in (ADAPTER, HELPER, BUILDSRC):
            target = {
                ADAPTER: build_src / "src" / "main" / "kotlin" / ADAPTER.name,
                HELPER: build_src / "src" / "main" / "kotlin" / HELPER.name,
                BUILDSRC: build_src / "build.gradle.kts",
            }[source]
            self.assertEqual(sha256(source), sha256(target), source)

        wrapper_target = fixture / "gradlew"
        shutil.copy2(WRAPPER, wrapper_target)
        wrapper_target.chmod(0o700)
        shutil.copytree(
            REPO_ROOT / "gradle" / "wrapper",
            fixture / "gradle" / "wrapper",
            copy_function=shutil.copy2,
        )

    def _create_synthetic_key(self, gnupg_home: Path) -> tuple[str, str]:
        batch = """\
Key-Type: RSA
Key-Length: 2048
Name-Real: Issues 242 243 Smoke
Name-Email: issues-242-243-smoke@example.invalid
Expire-Date: 0
%no-protection
%commit
"""
        generated = self._run(
            [
                "gpg",
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--generate-key",
            ],
            cwd=REPO_ROOT,
            environment={"GNUPGHOME": str(gnupg_home)},
            input_text=batch,
        )
        self.assertEqual(generated.returncode, 0, self._diagnostic(generated))
        listed = self._run(
            ["gpg", "--batch", "--with-colons", "--list-secret-keys"],
            cwd=REPO_ROOT,
            environment={"GNUPGHOME": str(gnupg_home)},
        )
        self.assertEqual(listed.returncode, 0, self._diagnostic(listed))
        key_id = next(
            row.split(":")[4]
            for row in listed.stdout.splitlines()
            if row.startswith("sec:") and len(row.split(":")) > 4
        )
        exported = self._run(
            ["gpg", "--batch", "--armor", "--export-secret-keys", key_id],
            cwd=REPO_ROOT,
            environment={"GNUPGHOME": str(gnupg_home)},
        )
        self.assertEqual(exported.returncode, 0, self._diagnostic(exported))
        self.assertTrue(exported.stdout.startswith(ARMOR_HEADER))
        self.assertTrue(exported.stdout.rstrip().endswith(ARMOR_FOOTER))
        return key_id, exported.stdout

    def _run_fixture(
        self,
        fixture: Path,
        environment: dict[str, str],
        *,
        clean_publication: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if clean_publication:
            shutil.rmtree(
                Path(environment["TEST_MAVEN_REPOSITORY"]), ignore_errors=True
            )
            Path(environment["TEST_MAVEN_REPOSITORY"]).mkdir(mode=0o700)
        command = [
            str((fixture / "gradlew").resolve()),
            "-p",
            str(fixture.resolve()),
            *FIXTURE_TASKS,
            "--no-daemon",
            "--no-configuration-cache",
            "--no-build-cache",
            "--console=plain",
        ]
        return self._run(command, cwd=fixture, environment=environment, timeout=600)

    def _run(
        self,
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        input_text: str | None = None,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        child_environment = os.environ.copy()
        child_environment.update(environment)
        child_environment["GPG_TTY"] = ""
        return subprocess.run(
            command,
            cwd=str(cwd),
            env=child_environment,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _assert_redacted_output(self, output: str) -> None:
        self.assertNotIn(SENTINEL_PASSWORD, output)
        self.assertNotIn("malformed-key-body-sentinel", output)
        self.assertNotIn(ARMOR_HEADER, output)
        self.assertNotIn(ARMOR_FOOTER, output)

    def _redact_output(self, output: str) -> str:
        redacted = output.replace(SENTINEL_PASSWORD, "<redacted-password>")
        redacted = redacted.replace("malformed-key-body-sentinel", "<redacted-key-body>")
        return re.sub(
            rf"{re.escape(ARMOR_HEADER)}.*?{re.escape(ARMOR_FOOTER)}",
            "<redacted-private-armor>",
            redacted,
            flags=re.DOTALL,
        )

    def _write_failure_artifact(
        self, label: str, result: subprocess.CompletedProcess[str]
    ) -> Path:
        artifact_dir = REPO_ROOT / "build" / "issues-242-243"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / f"publishing-signing-smoke-{label}.log"
        artifact.write_text(
            self._redact_output(result.stdout + "\n" + result.stderr)[-12000:],
            encoding="utf-8",
        )
        artifact.chmod(0o600)
        return artifact

    def _diagnostic(self, result: subprocess.CompletedProcess[str]) -> str:
        output = self._redact_output(result.stdout + "\n" + result.stderr)
        return f"returncode={result.returncode}\n{output[-4000:]}"


if __name__ == "__main__":
    unittest.main()
