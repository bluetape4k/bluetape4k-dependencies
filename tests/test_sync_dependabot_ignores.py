from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "sync-dependabot-ignores.py"
)
SPEC = importlib.util.spec_from_file_location("sync_dependabot_ignores", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_dependabot_ignores"] = sync
SPEC.loader.exec_module(sync)


class SyncDependabotIgnoresTest(unittest.TestCase):
    def test_cli_exposes_shared_strict_repository_map(self) -> None:
        self.assertTrue(
            callable(sync.sync_shared_versions.catalog_candidate.load_repository_map_v1)
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--repository-map", result.stdout)

    def test_candidate_dependabot_file_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            outside = Path(tmp) / "outside.yml"
            outside.write_text("version: 2\n", encoding="utf-8")
            config = root / ".github" / "dependabot.yml"
            config.parent.mkdir(parents=True)
            config.symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, "non-symlink"):
                sync.candidate_dependabot_file(root)

    def test_candidate_repository_root_uses_catalog_owner(self) -> None:
        catalog = Path("/workspace/repo/gradle/libs.versions.toml")
        self.assertEqual(
            sync.candidate_repository_root(catalog),
            Path("/workspace/repo"),
        )
        with self.assertRaisesRegex(RuntimeError, "not canonical"):
            sync.candidate_repository_root(Path("/workspace/repo/catalog.toml"))

    def test_default_workspace_matches_repository_workspace(self) -> None:
        original_file = sync.__file__
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "bluetape4k"
            script = (
                workspace
                / "bluetape4k-dependencies"
                / "scripts"
                / "sync-dependabot-ignores.py"
            )
            script.parent.mkdir(parents=True)
            script.touch()

            try:
                sync.__file__ = str(script)

                self.assertEqual(sync.default_workspace(), workspace.resolve())
            finally:
                sync.__file__ = original_file

    def test_default_workspace_matches_repository_workspace_from_worktree(self) -> None:
        original_file = sync.__file__
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "bluetape4k"
            script = (
                workspace
                / "bluetape4k-dependencies"
                / ".worktrees"
                / "chore-all-open-issues"
                / "scripts"
                / "sync-dependabot-ignores.py"
            )
            script.parent.mkdir(parents=True)
            script.touch()

            try:
                sync.__file__ = str(script)

                self.assertEqual(sync.default_workspace(), workspace.resolve())
            finally:
                sync.__file__ = original_file

    def test_sync_text_adds_generated_block_to_existing_ignore(self) -> None:
        text = "\n".join(
            [
                "version: 2",
                "updates:",
                '  - package-ecosystem: "gradle"',
                '    directory: "/"',
                "    ignore:",
                '      - dependency-name: "org.springframework.boot"',
                "        update-types:",
                '          - "version-update:semver-major"',
                '  - package-ecosystem: "github-actions"',
                '    directory: "/"',
                "",
            ],
        )

        synced = sync.sync_text(text)

        self.assertIn(sync.MARKER_START, synced)
        self.assertIn('dependency-name: "io.github.bluetape4k*"', synced)
        self.assertIn('dependency-name: "org.slf4j:*"', synced)
        self.assertIn('dependency-name: "org.bouncycastle:*"', synced)
        self.assertIn('dependency-name: "org.apache.tomcat.embed:*"', synced)
        self.assertIn('dependency-name: "org.springframework.boot"', synced)

    def test_sync_text_adds_ignore_section_when_missing(self) -> None:
        text = "\n".join(
            [
                "version: 2",
                "updates:",
                '  - package-ecosystem: "gradle"',
                '    directory: "/"',
                '  - package-ecosystem: "github-actions"',
                '    directory: "/"',
                "",
            ],
        )

        synced = sync.sync_text(text)

        self.assertIn("    ignore:", synced)
        self.assertLess(
            synced.index("    ignore:"),
            synced.index('  - package-ecosystem: "github-actions"'),
        )

    def test_sync_text_leaves_actions_only_config_unchanged(self) -> None:
        text = "\n".join(
            [
                "version: 2",
                "# Gradle/Maven library version updates are centralized in bluetape4k-dependencies.",
                "# Leaf repositories keep Dependabot only for GitHub Actions updates.",
                "updates:",
                '  - package-ecosystem: "github-actions"',
                '    directory: "/"',
                "",
            ],
        )

        self.assertEqual(sync.sync_text(text), text)

    def test_sync_text_is_idempotent(self) -> None:
        text = "\n".join(
            [
                "version: 2",
                "updates:",
                '  - package-ecosystem: "gradle"',
                '    directory: "/"',
                "    ignore:",
                '  - package-ecosystem: "github-actions"',
                '    directory: "/"',
                "",
            ],
        )

        once = sync.sync_text(text)
        twice = sync.sync_text(once)

        self.assertEqual(once, twice)
        self.assertEqual(once.count(sync.MARKER_START), 1)

    def test_cli_check_fails_when_file_requires_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            config = repo / ".github" / "dependabot.yml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "\n".join(
                    [
                        "version: 2",
                        "updates:",
                        '  - package-ecosystem: "gradle"',
                        '    directory: "/"',
                        "",
                    ],
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--workspace",
                    tmp,
                    "--repo",
                    "sample",
                    "--check",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Dependabot ignore drift detected", result.stderr)

    def test_cli_check_fails_when_no_target_files_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "sample"
            repo.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--workspace",
                    tmp,
                    "--repo",
                    "sample",
                    "--check",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("No downstream Dependabot files found", result.stderr)


if __name__ == "__main__":
    unittest.main()
