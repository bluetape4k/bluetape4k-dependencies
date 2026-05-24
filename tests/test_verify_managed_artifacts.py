from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify-managed-artifacts.py"
SPEC = importlib.util.spec_from_file_location("verify_managed_artifacts", SCRIPT_PATH)
assert SPEC is not None
verify = importlib.util.module_from_spec(SPEC)
sys.modules["verify_managed_artifacts"] = verify
assert SPEC.loader is not None
SPEC.loader.exec_module(verify)


class VerifyManagedArtifactsTest(unittest.TestCase):
    def test_parse_managed_artifacts_resolves_version_refs_and_skips_self(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_file = Path(tmp) / "libs.versions.toml"
            catalog_file.write_text(
                """
                [versions]
                bluetape4k-dependencies = "1.1.1"
                bluetape4k-bom = "1.9.0"

                [libraries]
                bluetape4k-dependencies = { module = "io.github.bluetape4k:bluetape4k-dependencies", version.ref = "bluetape4k-dependencies" }
                bluetape4k-core = { module = "io.github.bluetape4k:bluetape4k-core", version.ref = "bluetape4k-bom" }
                junit = { module = "org.junit.jupiter:junit-jupiter", version = "5.14.0" }
                """,
                encoding="utf-8",
            )

            artifacts = verify.parse_managed_artifacts(catalog_file)

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].alias, "bluetape4k-core")
        self.assertEqual(artifacts[0].gav, "io.github.bluetape4k:bluetape4k-core:1.9.0")

    def test_parse_managed_artifacts_can_include_self_after_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_file = Path(tmp) / "libs.versions.toml"
            catalog_file.write_text(
                """
                [versions]
                bluetape4k-dependencies = "1.1.1"

                [libraries]
                bluetape4k-dependencies = { module = "io.github.bluetape4k:bluetape4k-dependencies", version.ref = "bluetape4k-dependencies" }
                """,
                encoding="utf-8",
            )

            artifacts = verify.parse_managed_artifacts(catalog_file, include_self=True)

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].gav, "io.github.bluetape4k:bluetape4k-dependencies:1.1.1")

    def test_pom_url_uses_maven_path_layout(self) -> None:
        artifact = verify.ManagedArtifact(
            alias="bluetape4k-leader-dynamodb",
            group_id="io.github.bluetape4k.leader",
            artifact_id="leader-dynamodb",
            version="0.2.0",
        )

        self.assertEqual(
            verify.pom_url("https://repo1.maven.org/maven2/", artifact),
            "https://repo1.maven.org/maven2/io/github/bluetape4k/leader/leader-dynamodb/0.2.0/leader-dynamodb-0.2.0.pom",
        )

    def test_metadata_url_uses_maven_snapshot_layout(self) -> None:
        artifact = verify.ManagedArtifact(
            alias="bluetape4k-core",
            group_id="io.github.bluetape4k",
            artifact_id="bluetape4k-core",
            version="1.9.2-SNAPSHOT",
        )

        self.assertEqual(
            verify.metadata_url("https://central.sonatype.com/repository/maven-snapshots/", artifact),
            "https://central.sonatype.com/repository/maven-snapshots/io/github/bluetape4k/bluetape4k-core/1.9.2-SNAPSHOT/maven-metadata.xml",
        )

    def test_verify_artifacts_rejects_snapshots_by_default(self) -> None:
        artifact = verify.ManagedArtifact(
            alias="bluetape4k-core",
            group_id="io.github.bluetape4k",
            artifact_id="bluetape4k-core",
            version="1.9.1-SNAPSHOT",
        )

        errors = verify.verify_artifacts([artifact], "https://repo1.maven.org/maven2", 1.0, False)

        self.assertEqual(
            errors,
            [
                "Snapshot version is not release-verifiable: bluetape4k-core -> io.github.bluetape4k:bluetape4k-core:1.9.1-SNAPSHOT"
            ],
        )

    def test_verify_artifacts_allows_snapshots_via_snapshot_metadata(self) -> None:
        artifact = verify.ManagedArtifact(
            alias="bluetape4k-core",
            group_id="io.github.bluetape4k",
            artifact_id="bluetape4k-core",
            version="1.9.2-SNAPSHOT",
        )

        with mock.patch.object(verify, "artifact_exists", return_value=(True, "200")) as artifact_exists:
            errors = verify.verify_artifacts(
                [artifact],
                "https://repo1.maven.org/maven2",
                1.0,
                True,
                "https://central.sonatype.com/repository/maven-snapshots",
            )

        self.assertEqual(errors, [])
        artifact_exists.assert_called_once_with(
            "https://central.sonatype.com/repository/maven-snapshots/io/github/bluetape4k/bluetape4k-core/1.9.2-SNAPSHOT/maven-metadata.xml",
            1.0,
        )

    def test_verify_artifacts_reports_missing_aliases(self) -> None:
        artifact = verify.ManagedArtifact(
            alias="bluetape4k-core",
            group_id="io.github.bluetape4k",
            artifact_id="bluetape4k-core",
            version="1.9.0",
        )

        with mock.patch.object(verify, "artifact_exists", return_value=(False, "404")):
            errors = verify.verify_artifacts([artifact], "https://repo1.maven.org/maven2", 1.0, False)

        self.assertEqual(
            errors,
            ["Missing managed artifact (404): bluetape4k-core -> io.github.bluetape4k:bluetape4k-core:1.9.0"],
        )


if __name__ == "__main__":
    unittest.main()
