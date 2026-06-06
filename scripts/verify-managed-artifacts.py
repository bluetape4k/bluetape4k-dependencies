#!/usr/bin/env python3
"""Verify that managed bluetape4k catalog artifacts exist in Maven Central."""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_REPOSITORY_URL = "https://repo1.maven.org/maven2"
DEFAULT_SNAPSHOT_REPOSITORY_URL = "https://central.sonatype.com/repository/maven-snapshots"
DEFAULT_SNAPSHOT_403_ATTEMPTS = 2
DEFAULT_SNAPSHOT_403_DELAY_SECONDS = 0.2
SELF_ALIAS = "bluetape4k-dependencies"


@dataclasses.dataclass(frozen=True)
class ManagedArtifact:
    alias: str
    group_id: str
    artifact_id: str
    version: str

    @property
    def gav(self) -> str:
        return f"{self.group_id}:{self.artifact_id}:{self.version}"


def strip_inline_comment(line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "#":
            return line[:index]
    return line


def parse_versions(text: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    current_section = ""

    for raw_line in text.splitlines():
        line = strip_inline_comment(raw_line).strip()
        if not line:
            continue
        section = re.fullmatch(r"\[([A-Za-z0-9_.-]+)]", line)
        if section:
            current_section = section.group(1)
            continue
        if current_section != "versions":
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"', line)
        if match:
            versions[match.group(1)] = match.group(2)

    return versions


def parse_managed_artifacts(catalog_file: Path, include_self: bool = False) -> list[ManagedArtifact]:
    text = catalog_file.read_text(encoding="utf-8")
    versions = parse_versions(text)
    artifacts: list[ManagedArtifact] = []

    pattern = re.compile(
        r'^\s*([A-Za-z0-9_.-]+)\s*=\s*\{\s*module\s*=\s*"'
        r'(io\.github\.bluetape4k(?:\.[^:"]+)?):([^"]+)"\s*,\s*'
        r'(?:version\.ref\s*=\s*"([^"]+)"|version\s*=\s*"([^"]+)")',
        flags=re.MULTILINE,
    )

    for match in pattern.finditer(text):
        alias, group_id, artifact_id, version_ref, direct_version = match.groups()
        if alias == SELF_ALIAS and not include_self:
            continue

        version = direct_version
        if version_ref is not None:
            version = versions.get(version_ref)
            if version is None:
                raise RuntimeError(f"{alias} references missing version key: {version_ref}")
        if version is None:
            raise RuntimeError(f"{alias} has no resolvable version")

        artifacts.append(
            ManagedArtifact(
                alias=alias,
                group_id=group_id,
                artifact_id=artifact_id,
                version=version,
            )
        )

    return artifacts


def pom_url(repository_url: str, artifact: ManagedArtifact) -> str:
    base = repository_url.rstrip("/")
    group_path = artifact.group_id.replace(".", "/")
    return (
        f"{base}/{group_path}/{artifact.artifact_id}/{artifact.version}/"
        f"{artifact.artifact_id}-{artifact.version}.pom"
    )


def metadata_url(repository_url: str, artifact: ManagedArtifact) -> str:
    base = repository_url.rstrip("/")
    group_path = artifact.group_id.replace(".", "/")
    return f"{base}/{group_path}/{artifact.artifact_id}/{artifact.version}/maven-metadata.xml"


def artifact_exists(url: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400, str(response.status)
    except urllib.error.HTTPError as error:
        if error.code == 405:
            get_request = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
            try:
                with urllib.request.urlopen(get_request, timeout=timeout) as response:
                    return 200 <= response.status < 400, str(response.status)
            except urllib.error.HTTPError as get_error:
                return False, str(get_error.code)
        return False, str(error.code)
    except urllib.error.URLError as error:
        return False, str(error.reason)
    except TimeoutError:
        return False, "timeout"


def artifact_exists_with_snapshot_403_retry(
    url: str,
    timeout: float,
    is_snapshot: bool,
    allow_snapshots: bool,
    attempts: int,
    delay_seconds: float,
) -> tuple[bool, str]:
    safe_attempts = max(1, attempts)

    for attempt in range(1, safe_attempts + 1):
        exists, status = artifact_exists(url, timeout)
        if exists:
            return exists, status
        if not (is_snapshot and allow_snapshots and status == "403" and attempt < safe_attempts):
            return exists, status
        time.sleep(max(0.0, delay_seconds))

    return False, "403"


def verify_artifacts(
    artifacts: list[ManagedArtifact],
    repository_url: str,
    timeout: float,
    allow_snapshots: bool,
    snapshot_repository_url: str = DEFAULT_SNAPSHOT_REPOSITORY_URL,
    snapshot_403_attempts: int = DEFAULT_SNAPSHOT_403_ATTEMPTS,
    snapshot_403_delay_seconds: float = DEFAULT_SNAPSHOT_403_DELAY_SECONDS,
) -> list[str]:
    errors: list[str] = []

    for artifact in artifacts:
        is_snapshot = artifact.version.endswith("-SNAPSHOT")
        if is_snapshot and not allow_snapshots:
            errors.append(f"Snapshot version is not release-verifiable: {artifact.alias} -> {artifact.gav}")
            continue

        url = metadata_url(snapshot_repository_url, artifact) if is_snapshot else pom_url(repository_url, artifact)
        exists, status = artifact_exists_with_snapshot_403_retry(
            url=url,
            timeout=timeout,
            is_snapshot=is_snapshot,
            allow_snapshots=allow_snapshots,
            attempts=snapshot_403_attempts,
            delay_seconds=snapshot_403_delay_seconds,
        )
        if not exists:
            if is_snapshot and allow_snapshots and status == "403":
                print(f"Transient snapshot artifact check skipped after 403: {artifact.alias} -> {artifact.gav}")
                continue
            errors.append(f"Missing managed artifact ({status}): {artifact.alias} -> {artifact.gav}")

    return errors


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer: {value}") from None


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise RuntimeError(f"{name} must be a number: {value}") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-file",
        type=Path,
        default=Path("gradle/libs.versions.toml"),
        help="Gradle version catalog to verify",
    )
    parser.add_argument(
        "--repository-url",
        default=DEFAULT_REPOSITORY_URL,
        help="Maven repository base URL",
    )
    parser.add_argument(
        "--snapshot-repository-url",
        default=DEFAULT_SNAPSHOT_REPOSITORY_URL,
        help="Maven snapshot repository base URL",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--include-self",
        action="store_true",
        help="Also verify bluetape4k-dependencies itself; use after this version is released",
    )
    parser.add_argument(
        "--allow-snapshots",
        action="store_true",
        help="Allow -SNAPSHOT managed versions instead of failing fast",
    )
    parser.add_argument(
        "--snapshot-403-attempts",
        type=int,
        default=env_int("SNAPSHOT_ARTIFACT_CHECK_ATTEMPTS", DEFAULT_SNAPSHOT_403_ATTEMPTS),
        help="Attempts for transient snapshot 403 artifact checks",
    )
    parser.add_argument(
        "--snapshot-403-delay-seconds",
        type=float,
        default=env_float("SNAPSHOT_ARTIFACT_CHECK_DELAY_SECONDS", DEFAULT_SNAPSHOT_403_DELAY_SECONDS),
        help="Delay between transient snapshot 403 artifact check attempts",
    )
    parser.add_argument("--summary", action="store_true", help="Print verification summary")
    args = parser.parse_args()

    artifacts = parse_managed_artifacts(args.catalog_file, include_self=args.include_self)
    errors = verify_artifacts(
        artifacts=artifacts,
        repository_url=args.repository_url,
        timeout=args.timeout,
        allow_snapshots=args.allow_snapshots,
        snapshot_repository_url=args.snapshot_repository_url,
        snapshot_403_attempts=args.snapshot_403_attempts,
        snapshot_403_delay_seconds=args.snapshot_403_delay_seconds,
    )

    if args.summary:
        print(f"Managed bluetape4k artifacts checked: {len(artifacts)}")
        if not args.include_self:
            print(f"Skipped self artifact: {SELF_ALIAS}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Verified managed bluetape4k artifact availability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
