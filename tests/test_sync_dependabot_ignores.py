from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync-dependabot-ignores.py"
SPEC = importlib.util.spec_from_file_location("sync_dependabot_ignores", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules["sync_dependabot_ignores"] = sync
SPEC.loader.exec_module(sync)


class SyncDependabotIgnoresTest(unittest.TestCase):
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
        self.assertLess(synced.index("    ignore:"), synced.index('  - package-ecosystem: "github-actions"'))

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


if __name__ == "__main__":
    unittest.main()
