from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-post-publish-next-development-line.py"
MANIFEST = REPO_ROOT / "config" / "post-publish-next-development-line.json"


def load_script():
    spec = importlib.util.spec_from_file_location("verify_next_line", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load post-publish next-line verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PostPublishNextDevelopmentLineTest(unittest.TestCase):
    def test_checked_in_manifest_has_runtime_snapshot_contract(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        module.validate_manifest(document)
        self.assertEqual(document["source-contract"]["snapshotVersion"], "")
        self.assertEqual(
            document["source-contract"]["runtime-property"],
            "-PsnapshotVersion=-SNAPSHOT",
        )
        self.assertEqual(len(document["publishable-repositories"]), 8)

    def test_manifest_rejects_source_snapshot_suffix(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        document["source-contract"]["snapshotVersion"] = "-SNAPSHOT"

        with self.assertRaisesRegex(RuntimeError, "snapshotVersion"):
            module.validate_manifest(document)

    def test_development_line_rejects_stable_internal_ref(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = root / "central"
            workspace = root / "workspace"
            (central / "gradle").mkdir(parents=True)
            (central / "gradle.properties").write_text(
                "baseVersion=1.5.0\nsnapshotVersion=\n", encoding="utf-8"
            )
            (central / "gradle" / "libs.versions.toml").write_text(
                "[versions]\n"
                "bluetape4k-dependencies = \"1.5.0\"\n"
                "bluetape4k-bom = \"1.12.1\"\n",
                encoding="utf-8",
            )
            for item in document["publishable-repositories"]:
                repo = workspace / item["repository"]
                (repo / ".github" / "workflows").mkdir(parents=True)
                (repo / "gradle.properties").write_text(
                    f"baseVersion={item['base-version']}\nsnapshotVersion=\n",
                    encoding="utf-8",
                )
                (repo / ".github" / "workflows" / "publish-snapshot.yml").write_text(
                    "JAVA_VERSION: '25'\n-PsnapshotVersion=-SNAPSHOT\n", encoding="utf-8"
                )
                (repo / ".github" / "workflows" / "release.yml").write_text(
                    "snapshotVersion must be empty for release\n", encoding="utf-8"
                )

            errors = module.verify_development(central, workspace, document, False)

        self.assertTrue(any("bluetape4k-bom" in error for error in errors))

    def test_stable_boundary_rejects_snapshot_refs(self) -> None:
        module = load_script()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as temporary:
            central = Path(temporary) / "central"
            (central / "gradle").mkdir(parents=True)
            (central / "gradle.properties").write_text(
                "baseVersion=1.5.0\nsnapshotVersion=\n", encoding="utf-8"
            )
            (central / "gradle" / "libs.versions.toml").write_text(
                "[versions]\n"
                "bluetape4k-dependencies = \"1.5.0\"\n"
                "bluetape4k-bom = \"1.13.0-SNAPSHOT\"\n",
                encoding="utf-8",
            )

            errors = module.verify_stable(central, document, "1.5.0")

        self.assertIn(
            "stable catalog cannot reference a snapshot: bluetape4k-bom=1.13.0-SNAPSHOT",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
