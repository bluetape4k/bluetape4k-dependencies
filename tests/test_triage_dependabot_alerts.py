from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "triage-dependabot-alerts.py"
SPEC = importlib.util.spec_from_file_location("triage_dependabot_alerts", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
triage = importlib.util.module_from_spec(SPEC)
sys.modules["triage_dependabot_alerts"] = triage
SPEC.loader.exec_module(triage)


class TriageDependabotAlertsTest(unittest.TestCase):
    def alert(self, package: str, manifest: str = "gradle/libs.versions.toml") -> triage.Alert:
        return triage.Alert(
            repo="sample",
            number=1,
            severity="high",
            package=package,
            manifest=manifest,
            vulnerable_range="< 1.0.1",
            patched_version="1.0.1",
            ghsa="GHSA-test",
            summary="test advisory",
        )

    def test_package_names_from_catalog_reads_library_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "libs.versions.toml"
            catalog.write_text(
                "\n".join(
                    [
                        "[libraries]",
                        'tomcat-embed-core = { module = "org.apache.tomcat.embed:tomcat-embed-core", version = "11.0.22" }',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            names = triage.package_names_from_catalog(catalog)

        self.assertEqual(names, {"org.apache.tomcat.embed:tomcat-embed-core"})

    def test_classify_central_catalog_package(self) -> None:
        classified = triage.classify_alert(
            self.alert("org.bouncycastle:bcprov-jdk18on"),
            {"org.bouncycastle:*"},
        )

        self.assertEqual(classified.route, "central-catalog")
        self.assertEqual(classified.owner, "bluetape4k-dependencies")

    def test_classify_central_bom_transitive_package(self) -> None:
        classified = triage.classify_alert(
            self.alert("org.apache.tomcat.embed:tomcat-embed-core"),
            set(),
        )

        self.assertEqual(classified.route, "central-bom-transitive")
        self.assertEqual(classified.owner, "spring-boot")

    def test_classify_spring_framework_as_spring_boot_transitive(self) -> None:
        classified = triage.classify_alert(
            self.alert("org.springframework:spring-webmvc"),
            set(),
        )

        self.assertEqual(classified.route, "central-bom-transitive")
        self.assertEqual(classified.owner, "spring-boot")

    def test_classify_settings_plugin_as_repo_tooling(self) -> None:
        classified = triage.classify_alert(
            self.alert("some.plugin:plugin", manifest="settings.gradle.kts"),
            set(),
        )

        self.assertEqual(classified.route, "repo-tooling")
        self.assertEqual(classified.owner, "sample")

    def test_classify_unknown_as_repo_local(self) -> None:
        classified = triage.classify_alert(self.alert("example:local"), set())

        self.assertEqual(classified.route, "repo-local")
        self.assertEqual(classified.owner, "sample")


if __name__ == "__main__":
    unittest.main()
