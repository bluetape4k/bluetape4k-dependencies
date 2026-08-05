#!/usr/bin/env python3
"""Build the fail-closed latest-stable audit inventory for catalog authorities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
DEFAULT_POLICY = REPO_ROOT / "config" / "central-catalog-authority-policy.json"
DEFAULT_OUTPUT = REPO_ROOT / "config" / "latest-stable-version-inventory.json"

MANAGED_REPOSITORIES = [
    "bluetape4k-projects",
    "bluetape4k-aws",
    "bluetape4k-experimental",
    "bluetape4k-exposed",
    "bluetape4k-graph",
    "bluetape4k-image",
    "bluetape4k-javers",
    "bluetape4k-leader",
    "bluetape4k-text",
]
EXCLUDED_REPOSITORIES = [
    "bluetape4k-workshop",
    "clinic-appointment",
    "exposed-r2dbc-workshop",
    "exposed-workshop",
    "timefold-workshop",
]
PENDING_REASON = "Fresh upstream metadata and explicit disposition are required."


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def pending_latest_stable() -> dict[str, Any]:
    return {
        "latest": None,
        "metadata-sha256": None,
        "reason": PENDING_REASON,
        "retrieved-at": None,
        "source": None,
        "status": "audit-pending",
    }


def catalog_section(catalog: str, name: str) -> str:
    marker = f"[{name}]"
    if marker not in catalog:
        raise RuntimeError(f"catalog is missing {marker}")
    return catalog.split(marker, 1)[1].split("\n[", 1)[0]


def parse_versions(catalog: str) -> dict[str, str]:
    return dict(
        re.findall(
            r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"',
            catalog_section(catalog, "versions"),
            flags=re.MULTILINE,
        )
    )


def parse_managed_aliases(catalog: str) -> dict[str, list[tuple[str, str, str]]]:
    aliases: dict[str, list[tuple[str, str, str]]] = {}
    for kind, section_name in (("library", "libraries"), ("plugin", "plugins")):
        for line in catalog_section(catalog, section_name).splitlines():
            version_ref = re.search(r'version\.ref\s*=\s*"(managed-[^"]+)"', line)
            alias = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*\{', line)
            if not version_ref or not alias:
                continue
            if kind == "library":
                module = re.search(r'module\s*=\s*"([^"]+)"', line)
                group = re.search(r'group\s*=\s*"([^"]+)"', line)
                name = re.search(r'name\s*=\s*"([^"]+)"', line)
                subject = module.group(1) if module else f"{group.group(1)}:{name.group(1)}"
            else:
                plugin_id = re.search(r'id\s*=\s*"([^"]+)"', line)
                if plugin_id is None:
                    raise RuntimeError(f"managed plugin alias is missing id: {line}")
                subject = plugin_id.group(1)
            aliases.setdefault(version_ref.group(1), []).append(
                (kind, alias.group(1), subject)
            )
    return aliases


def build_managed_records(catalog: str) -> list[dict[str, Any]]:
    versions = parse_versions(catalog)
    managed_aliases = parse_managed_aliases(catalog)
    records: list[dict[str, Any]] = []

    for version_key in sorted(key for key in versions if key.startswith("managed-")):
        matches = managed_aliases.get(version_key, [])
        authorities = {(kind, subject) for kind, _, subject in matches}
        if len(authorities) != 1:
            raise RuntimeError(
                f"{version_key} must map to exactly one catalog authority; found {len(authorities)}"
            )

        kind, subject = next(iter(authorities))
        aliases = sorted(alias for match_kind, alias, match_subject in matches if (match_kind, match_subject) == (kind, subject))
        records.append(
            {
                "aliases": aliases,
                "authority-key": f"managed:{version_key}",
                "authority-source": "managed-generated",
                "coordinate-or-plugin-id": subject,
                "current-lines": [
                    {
                        "current": versions[version_key],
                        "governance-disposition": "central-direct",
                        "line-id": "default",
                        "version-key": version_key,
                    }
                ],
                "kind": kind,
                "latest-stable": pending_latest_stable(),
            }
        )
    return records


def build_policy_records(policy: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for subject in policy["subjects"]:
        kind = subject["subject-kind"]
        coordinate = subject["coordinate-or-plugin-id"]
        aliases = sorted({alias for line in subject["lines"] for alias in line["central-aliases"]})
        lines = [
            {
                "current": line["version"],
                "governance-disposition": line["disposition"],
                "line-id": line["line-id"],
                "version-key": line["version-key"],
            }
            for line in subject["lines"]
        ]
        records.append(
            {
                "aliases": aliases,
                "authority-key": f"policy:{kind}:{coordinate}",
                "authority-source": "policy-subject",
                "coordinate-or-plugin-id": coordinate,
                "current-lines": sorted(lines, key=lambda line: line["line-id"]),
                "kind": kind,
                "latest-stable": pending_latest_stable(),
            }
        )
    return sorted(records, key=lambda record: record["authority-key"])


def build_inventory(catalog_path: Path, policy_path: Path) -> dict[str, Any]:
    catalog = catalog_path.read_text(encoding="utf-8")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    managed_records = build_managed_records(catalog)
    policy_records = build_policy_records(policy)
    records = sorted(managed_records + policy_records, key=lambda record: record["authority-key"])

    if len(managed_records) != 325 or len(policy_records) != 71 or len(records) != 396:
        raise RuntimeError(
            "authority universe changed; expected 325 managed + 71 policy = 396, "
            f"found {len(managed_records)} + {len(policy_records)} = {len(records)}"
        )
    if len({record["authority-key"] for record in records}) != len(records):
        raise RuntimeError("authority keys must be unique")

    return {
        "inputs": {
            "catalog": {
                "path": provenance_path(catalog_path),
                "sha256": sha256(catalog_path),
            },
            "policy": {
                "path": provenance_path(policy_path),
                "sha256": sha256(policy_path),
            },
        },
        "records": records,
        "schema-version": 1,
        "scope": {
            "excluded": EXCLUDED_REPOSITORIES,
            "repositories": MANAGED_REPOSITORIES,
        },
        "summary": {
            "audit-pending": len(records),
            "authority-count": len(records),
            "managed-generated": len(managed_records),
            "policy-subjects": len(policy_records),
        },
    }


def check_inventory(output: Path, catalog: Path, policy: Path) -> None:
    if not output.exists() or output.read_bytes() != canonical_json(build_inventory(catalog, policy)):
        raise RuntimeError(f"inventory is stale: {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = build_inventory(args.catalog, args.policy)
    if args.write:
        args.output.write_bytes(canonical_json(inventory))
    if args.check:
        check_inventory(args.output, args.catalog, args.policy)
    if args.summary:
        summary = inventory["summary"]
        print(
            f"authority={summary['authority-count']} managed={summary['managed-generated']} "
            f"policy={summary['policy-subjects']} audit-pending={summary['audit-pending']}"
        )
    if not (args.write or args.check or args.summary):
        print(canonical_json(inventory).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
