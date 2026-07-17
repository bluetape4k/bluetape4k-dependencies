from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify-publication-poms.py"
SPEC = importlib.util.spec_from_file_location("verify_publication_poms", SCRIPT_PATH)
assert SPEC is not None
verify = importlib.util.module_from_spec(SPEC)
sys.modules["verify_publication_poms"] = verify
assert SPEC.loader is not None
SPEC.loader.exec_module(verify)


def pom(
    artifact_id: str,
    *,
    dependencies: str = "",
    dependency_management: str = "",
    packaging: str = "jar",
) -> str:
    return f"""\
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.example</groupId>
  <artifactId>{artifact_id}</artifactId>
  <version>1.0.0</version>
  <packaging>{packaging}</packaging>
  {dependency_management}
  {dependencies}
</project>
"""


class VerifyPublicationPomsTest(unittest.TestCase):
    def test_publisher_matrix_covers_every_library_publisher(self) -> None:
        self.assertEqual(
            set(verify.PUBLISHERS),
            {
                "bluetape4k-dependencies",
                "bluetape4k-projects",
                "bluetape4k-aws",
                "bluetape4k-exposed",
                "bluetape4k-graph",
                "bluetape4k-image",
                "bluetape4k-javers",
                "bluetape4k-leader",
                "bluetape4k-text",
            },
        )
        self.assertNotIn("bluetape4k-experimental", verify.PUBLISHERS)
        self.assertEqual(
            verify.PUBLISHERS["bluetape4k-leader"].tasks,
            (
                "generatePomFileForBluetapeLeaderPublication",
                "generatePomFileForBluetapeLeaderBomPublication",
            ),
        )

    def test_inventory_rejects_managed_or_workflow_publisher_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            managed = (
                "bluetape4k-projects",
                "bluetape4k-experimental",
                "bluetape4k-new-library",
            )
            for repository in ("bluetape4k-projects", "bluetape4k-new-library"):
                workflow = workspace / repository / ".github" / "workflows" / "publish-snapshot.yml"
                workflow.parent.mkdir(parents=True)
                workflow.write_text("name: publish\n", encoding="utf-8")

            errors = verify.publisher_inventory_errors(workspace, managed)

        self.assertTrue(any("managed publisher inventory mismatch" in error for error in errors))
        self.assertTrue(any("publish workflow inventory mismatch" in error for error in errors))

    def test_inventory_uses_candidate_roots_instead_of_default_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            candidate_root = Path(tmp) / "candidates"
            managed = tuple(
                repository
                for repository in verify.PUBLISHERS
                if repository != verify.SELF_REPOSITORY
            ) + ("bluetape4k-experimental",)
            roots: dict[str, Path] = {}
            for repository in verify.PUBLISHERS:
                root = candidate_root / repository
                roots[repository] = root
                if repository != "bluetape4k-projects":
                    workflow = root / ".github" / "workflows" / "publish-snapshot.yml"
                    workflow.parent.mkdir(parents=True)
                    workflow.write_text("name: publish\n", encoding="utf-8")

            default_workflow = workspace / "bluetape4k-projects" / ".github" / "workflows" / "publish-snapshot.yml"
            default_workflow.parent.mkdir(parents=True)
            default_workflow.write_text("name: stale sibling\n", encoding="utf-8")

            errors = verify.publisher_inventory_errors(workspace, managed, roots)

        self.assertEqual(len(errors), 1)
        self.assertIn("missing=bluetape4k-projects", errors[0])

    def test_audit_rejects_versionless_dependency_management_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pom.xml"
            path.write_text(
                pom(
                    "broken-bom-import",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>example-bom</artifactId>
  <type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
""",
                ),
                encoding="utf-8",
            )

            result = verify.audit_poms([path])

        self.assertEqual(result.file_count, 1)
        self.assertEqual(result.dependency_count, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("missing dependencyManagement version: org.example:example-bom", result.errors[0])

    def test_audit_accepts_regular_dependency_managed_in_same_pom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pom.xml"
            path.write_text(
                pom(
                    "managed-locally",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>managed</artifactId><version>2.0.0</version>
</dependency></dependencies></dependencyManagement>
""",
                    dependencies="""
<dependencies><dependency>
  <groupId>org.example</groupId><artifactId>managed</artifactId>
</dependency></dependencies>
""",
                ),
                encoding="utf-8",
            )

            result = verify.audit_poms([path])

        self.assertEqual(result.errors, ())
        self.assertEqual(result.dependency_count, 2)

    def test_audit_defers_versionless_regular_dependency_to_versioned_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pom.xml"
            path.write_text(
                pom(
                    "managed-by-bom",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>example-bom</artifactId><version>1.0.0</version>
  <type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
""",
                    dependencies="""
<dependencies><dependency>
  <groupId>org.example</groupId><artifactId>managed</artifactId>
</dependency></dependencies>
""",
                ),
                encoding="utf-8",
            )

            result = verify.audit_poms([path])

        self.assertEqual(result.errors, ())

    def test_audit_rejects_profiles_that_maven_reactor_would_leave_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pom.xml"
            path.write_text(
                pom(
                    "profile-dependency",
                    dependencies="""
<profiles><profile><id>optional-stack</id><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>unmanaged</artifactId>
</dependency></dependencies></profile></profiles>
""",
                ),
                encoding="utf-8",
            )

            result = verify.audit_poms([path])

        self.assertEqual(len(result.errors), 1)
        self.assertIn("publication POM profiles are unsupported: optional-stack", result.errors[0])

    def test_discover_poms_rejects_empty_publication_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "no publication POM files found"):
                verify.discover_poms(Path(tmp), "bluetape4k-sample")

    def test_clear_publication_poms_removes_only_current_worktree_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "module" / "build" / "publications" / "main" / "pom-default.xml"
            unrelated = root / "module" / "build" / "reports" / "pom-default.xml"
            nested_worktree = (
                root / ".worktrees" / "other" / "module" / "build" / "publications" / "main" / "pom-default.xml"
            )
            for path in (current, unrelated, nested_worktree):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(pom(path.parent.name), encoding="utf-8")

            removed = verify.clear_publication_poms(root)

            self.assertEqual(removed, 1)
            self.assertFalse(current.exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue(nested_worktree.exists())

    def test_reactor_copy_normalizes_gradle_version_catalog_packaging_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.xml"
            target = root / "target.xml"
            source.write_text(pom("catalog", packaging="toml"), encoding="utf-8")

            normalized = verify.copy_reactor_pom(source, target)

            self.assertTrue(normalized)
            self.assertIn("<packaging>toml</packaging>", source.read_text(encoding="utf-8"))
            self.assertIn("<packaging>pom</packaging>", target.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("mvn"), "Maven is required for effective-model validation")
    def test_maven_model_rejects_dependency_not_managed_by_imported_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bom_path = root / "bom.xml"
            consumer_path = root / "consumer.xml"
            bom_path.write_text(
                pom(
                    "example-bom",
                    packaging="pom",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>managed</artifactId><version>2.0.0</version>
</dependency></dependencies></dependencyManagement>
""",
                ),
                encoding="utf-8",
            )
            consumer_path.write_text(
                pom(
                    "consumer",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>example-bom</artifactId><version>1.0.0</version>
  <type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
""",
                    dependencies="""
<dependencies><dependency>
  <groupId>org.example</groupId><artifactId>unmanaged</artifactId>
</dependency></dependencies>
""",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Maven effective-model validation failed"):
                verify.validate_maven_models([bom_path, consumer_path])

    @unittest.skipUnless(shutil.which("mvn"), "Maven is required for effective-model validation")
    def test_maven_model_accepts_dependency_managed_by_imported_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bom_path = root / "bom.xml"
            consumer_path = root / "consumer.xml"
            bom_path.write_text(
                pom(
                    "example-bom",
                    packaging="pom",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>managed</artifactId><version>2.0.0</version>
</dependency></dependencies></dependencyManagement>
""",
                ),
                encoding="utf-8",
            )
            consumer_path.write_text(
                pom(
                    "consumer",
                    dependency_management="""
<dependencyManagement><dependencies><dependency>
  <groupId>org.example</groupId><artifactId>example-bom</artifactId><version>1.0.0</version>
  <type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
""",
                    dependencies="""
<dependencies><dependency>
  <groupId>org.example</groupId><artifactId>managed</artifactId>
</dependency></dependencies>
""",
                ),
                encoding="utf-8",
            )

            verify.validate_maven_models([bom_path, consumer_path])


if __name__ == "__main__":
    unittest.main()
