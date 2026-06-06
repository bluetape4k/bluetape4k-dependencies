from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "retry-snapshot-resolution.sh"


class RetrySnapshotResolutionTest(unittest.TestCase):
    def test_retries_central_snapshot_403_then_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "attempts"
            command_file = Path(tmp) / "flaky-snapshot.sh"
            command_file.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    attempts=0
                    if [ -f "{state_file}" ]; then
                      attempts="$(cat "{state_file}")"
                    fi
                    attempts=$((attempts + 1))
                    echo "$attempts" > "{state_file}"
                    if [ "$attempts" -eq 1 ]; then
                      echo "Could not resolve io.github.bluetape4k:bluetape4k-redisson:1.11.0-SNAPSHOT"
                      echo "Received status code 403 from https://central.sonatype.com/repository/maven-snapshots/io/github/bluetape4k/bluetape4k-redisson/1.11.0-SNAPSHOT/maven-metadata.xml"
                      exit 1
                    fi
                    echo "ok"
                    """
                ),
                encoding="utf-8",
            )
            command_file.chmod(0o755)

            env = os.environ.copy()
            env["SNAPSHOT_RESOLUTION_ATTEMPTS"] = "2"
            env["SNAPSHOT_RESOLUTION_DELAY_SECONDS"] = "0"
            result = subprocess.run(
                [str(SCRIPT_PATH), str(command_file)],
                cwd=tmp,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("retrying attempt 2/2", result.stdout)
            self.assertEqual(state_file.read_text(encoding="utf-8").strip(), "2")

    def test_does_not_retry_non_snapshot_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "attempts"
            command_file = Path(tmp) / "broken-test.sh"
            command_file.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    attempts=0
                    if [ -f "{state_file}" ]; then
                      attempts="$(cat "{state_file}")"
                    fi
                    attempts=$((attempts + 1))
                    echo "$attempts" > "{state_file}"
                    echo "There were failing tests"
                    exit 1
                    """
                ),
                encoding="utf-8",
            )
            command_file.chmod(0o755)

            env = os.environ.copy()
            env["SNAPSHOT_RESOLUTION_ATTEMPTS"] = "3"
            env["SNAPSHOT_RESOLUTION_DELAY_SECONDS"] = "0"
            result = subprocess.run(
                [str(SCRIPT_PATH), str(command_file)],
                cwd=tmp,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertNotIn("retrying attempt", result.stdout)
            self.assertEqual(state_file.read_text(encoding="utf-8").strip(), "1")

    def test_does_not_retry_snapshot_failure_without_403_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "attempts"
            command_file = Path(tmp) / "missing-snapshot.sh"
            command_file.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    attempts=0
                    if [ -f "{state_file}" ]; then
                      attempts="$(cat "{state_file}")"
                    fi
                    attempts=$((attempts + 1))
                    echo "$attempts" > "{state_file}"
                    echo "Could not resolve io.github.bluetape4k:missing-module:1.11.0-SNAPSHOT"
                    echo "maven-metadata.xml returned 404"
                    exit 1
                    """
                ),
                encoding="utf-8",
            )
            command_file.chmod(0o755)

            env = os.environ.copy()
            env["SNAPSHOT_RESOLUTION_ATTEMPTS"] = "3"
            env["SNAPSHOT_RESOLUTION_DELAY_SECONDS"] = "0"
            result = subprocess.run(
                [str(SCRIPT_PATH), str(command_file)],
                cwd=tmp,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertNotIn("retrying attempt", result.stdout)
            self.assertEqual(state_file.read_text(encoding="utf-8").strip(), "1")


if __name__ == "__main__":
    unittest.main()
