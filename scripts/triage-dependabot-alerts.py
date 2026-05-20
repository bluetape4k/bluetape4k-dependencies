#!/usr/bin/env python3
"""Classify Dependabot security alerts by dependency ownership.

The source-of-truth rule is:

* centrally governed dependencies are fixed in bluetape4k-dependencies first,
  then propagated downstream with sync-shared-versions.py;
* repo-local dependencies are fixed in the repository that owns the manifest;
* transitive dependencies owned by a central BOM are routed to that BOM line,
  with a temporary central override only when the BOM cannot yet move.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SYNC_SHARED_VERSIONS_PATH = SCRIPT_DIR / "sync-shared-versions.py"
SYNC_DEPENDABOT_IGNORES_PATH = SCRIPT_DIR / "sync-dependabot-ignores.py"


def load_script(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync_shared_versions = load_script(SYNC_SHARED_VERSIONS_PATH, "sync_shared_versions")
sync_dependabot_ignores = load_script(SYNC_DEPENDABOT_IGNORES_PATH, "sync_dependabot_ignores")


CENTRAL_TRANSITIVE_OWNERS = {
    "org.apache.tomcat.embed:*": "spring-boot",
    "org.apache.tomcat:tomcat-*": "spring-boot",
    "org.springframework:spring-*": "spring-boot",
}


@dataclasses.dataclass(frozen=True)
class Alert:
    repo: str
    number: int
    severity: str
    package: str
    manifest: str
    vulnerable_range: str
    patched_version: str
    ghsa: str
    summary: str


@dataclasses.dataclass(frozen=True)
class ClassifiedAlert:
    alert: Alert
    owner: str
    route: str
    action: str


def package_names_from_catalog(catalog: Path) -> set[str]:
    return set(re.findall(r'\bmodule\s*=\s*"([^":]+:[^"]+)"', catalog.read_text(encoding="utf-8")))


def package_patterns(catalog: Path) -> set[str]:
    patterns = set(sync_dependabot_ignores.CENTRAL_DEPENDENCY_IGNORES)
    patterns.update(package_names_from_catalog(catalog))
    patterns.update(CENTRAL_TRANSITIVE_OWNERS)
    return patterns


def matches_any(package_name: str, patterns: set[str]) -> bool:
    return any(fnmatch.fnmatchcase(package_name, pattern) for pattern in patterns)


def transitive_owner(package_name: str) -> str | None:
    for pattern, owner in CENTRAL_TRANSITIVE_OWNERS.items():
        if fnmatch.fnmatchcase(package_name, pattern):
            return owner
    return None


def classify_alert(alert: Alert, central_patterns: set[str]) -> ClassifiedAlert:
    owner = transitive_owner(alert.package)
    if owner is not None:
        return ClassifiedAlert(
            alert=alert,
            owner=owner,
            route="central-bom-transitive",
            action=(
                f"Update the `{owner}` line in bluetape4k-dependencies when a patched BOM exists; "
                "otherwise add or keep a central override and sync downstream."
            ),
        )

    if matches_any(alert.package, central_patterns):
        return ClassifiedAlert(
            alert=alert,
            owner="bluetape4k-dependencies",
            route="central-catalog",
            action="Update central catalog first, then run sync-shared-versions.py and sync-dependabot-ignores.py.",
        )

    if alert.manifest.endswith("settings.gradle.kts"):
        return ClassifiedAlert(
            alert=alert,
            owner=alert.repo,
            route="repo-tooling",
            action="Fix the Gradle/plugin/tooling line in this repository unless it is promoted to the central catalog.",
        )

    return ClassifiedAlert(
        alert=alert,
        owner=alert.repo,
        route="repo-local",
        action="Fix in the repository that owns this manifest.",
    )


GRAPHQL_QUERY = """
query($owner:String!, $name:String!, $states:[RepositoryVulnerabilityAlertState!]!) {
  repository(owner:$owner, name:$name) {
    vulnerabilityAlerts(first: 100, states: $states) {
      nodes {
        number
        vulnerableManifestPath
        securityVulnerability {
          vulnerableVersionRange
          firstPatchedVersion { identifier }
          package { ecosystem name }
          advisory {
            ghsaId
            severity
            summary
          }
        }
      }
    }
  }
}
"""


def fetch_alerts(owner: str, repo: str, state: str) -> list[Alert]:
    result = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={repo}",
            "-f",
            f"states[]={state}",
            "-f",
            f"query={GRAPHQL_QUERY}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    payload = json.loads(result.stdout)
    nodes = payload["data"]["repository"]["vulnerabilityAlerts"]["nodes"]
    alerts: list[Alert] = []
    for node in nodes:
        vulnerability = node["securityVulnerability"]
        advisory = vulnerability["advisory"]
        package = vulnerability["package"]
        patched = vulnerability.get("firstPatchedVersion") or {}
        alerts.append(
            Alert(
                repo=repo,
                number=node["number"],
                severity=advisory["severity"].lower(),
                package=f"{package['name']}",
                manifest=node["vulnerableManifestPath"],
                vulnerable_range=vulnerability["vulnerableVersionRange"],
                patched_version=patched.get("identifier") or "",
                ghsa=advisory["ghsaId"],
                summary=advisory["summary"],
            ),
        )
    return alerts


def render_table(rows: list[ClassifiedAlert]) -> str:
    if not rows:
        return "No Dependabot alerts matched.\n"

    lines = [
        "| Repo | Alert | Severity | Manifest | Package | Patched | Route | Owner |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        alert = row.alert
        lines.append(
            "| "
            + " | ".join(
                [
                    alert.repo,
                    str(alert.number),
                    alert.severity,
                    f"`{alert.manifest}`",
                    f"`{alert.package}`",
                    alert.patched_version or "n/a",
                    row.route,
                    row.owner,
                ],
            )
            + " |",
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default="bluetape4k", help="GitHub owner or organization.")
    parser.add_argument(
        "--repo",
        action="append",
        dest="repositories",
        help="Repository name to triage. May be repeated. Defaults to governed repositories.",
    )
    parser.add_argument("--state", default="OPEN", choices=("OPEN", "FIXED", "DISMISSED"))
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a markdown table.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    central_patterns = package_patterns(repo_root / "gradle" / "libs.versions.toml")
    repositories = args.repositories or sync_shared_versions.DEFAULT_REPOSITORIES
    rows: list[ClassifiedAlert] = []

    for repo in repositories:
        for alert in fetch_alerts(args.owner, repo, args.state):
            rows.append(classify_alert(alert, central_patterns))

    rows.sort(key=lambda row: (row.alert.repo, row.alert.number))
    if args.json:
        print(
            json.dumps(
                [
                    {
                        **dataclasses.asdict(row.alert),
                        "owner": row.owner,
                        "route": row.route,
                        "action": row.action,
                    }
                    for row in rows
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )
    else:
        print(render_table(rows), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
