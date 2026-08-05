#!/usr/bin/env python3
"""Build the fail-closed latest-stable audit inventory for catalog authorities."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import datetime as dt
import hashlib
import json
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
DEFAULT_POLICY = REPO_ROOT / "config" / "central-catalog-authority-policy.json"
DEFAULT_OUTPUT = REPO_ROOT / "config" / "latest-stable-version-inventory.json"
DEFAULT_AUDIT_OUTPUT = REPO_ROOT / "config" / "latest-stable-version-audit.json"
DEFAULT_AUDIT_POLICY = REPO_ROOT / "config" / "latest-stable-audit-policy.json"
DEFAULT_DELTA_LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"
DEFAULT_CENTRAL_DELTA_LEDGER = REPO_ROOT / "config" / "central-catalog-version-deltas.json"

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
PREVIEW_VERSION = re.compile(
    r"(?i)(?:snapshot|alpha|beta|preview|milestone|incubating|nightly|eap|"
    r"(?:^|[-.])(?:dev|test)(?:$|[-.])|"
    r"\d(?:a|b|m|rc|cr|ea)\d*(?=$|[-.])|"
    r"(?:^|[-.])(?:a|b|m|rc|cr|ea)(?:[-.]?\d+)?(?:$|[-.]))"
)
METADATA_REPOSITORY_OVERRIDES = {
    "edu.ucar:cdm-core": "https://artifacts.unidata.ucar.edu/repository/unidata-all",
    "org.geotools:gt-epsg-hsql": "https://repo.osgeo.org/repository/release",
    "org.geotools:gt-referencing": "https://repo.osgeo.org/repository/release",
    "org.geotools:gt-shapefile": "https://repo.osgeo.org/repository/release",
}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def pretty_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def utc_timestamp() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata_url(kind: str, subject: str) -> str:
    if kind == "plugin":
        group_path = subject.replace(".", "/")
        return (
            f"https://plugins.gradle.org/m2/{group_path}/"
            f"{subject}.gradle.plugin/maven-metadata.xml"
        )
    if kind != "library" or ":" not in subject:
        raise ValueError(f"unsupported authority: {kind}:{subject}")
    group, artifact = subject.split(":", 1)
    repository = METADATA_REPOSITORY_OVERRIDES.get(
        subject, "https://repo.maven.apache.org/maven2"
    )
    return (
        f"{repository}/{group.replace('.', '/')}/{artifact}/maven-metadata.xml"
    )


def is_stable(version: str) -> bool:
    return bool(version) and PREVIEW_VERSION.search(version) is None


def version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    version = re.sub(r"^[vV](?=\d)", "", version)
    return tuple(
        (0, int(token)) if token.isdigit() else (1, token.lower())
        for token in re.findall(r"\d+|[A-Za-z]+", version)
    )


def variant_channel(version: str) -> tuple[str, ...]:
    return tuple(
        token.lower()
        for token in re.findall(r"(?i)(?:^|[-.])(android\d*|jdk\d*|legacy)(?=$|[-.])", version)
    )


def parse_metadata(metadata: bytes) -> dict[str, Any]:
    root = ET.fromstring(metadata)
    versions = [
        element.text.strip()
        for element in root.findall(".//version")
        if element.text and element.text.strip()
    ]
    stable_versions = sorted(
        {version for version in versions if is_stable(version)}, key=version_key
    )
    release = (root.findtext(".//release") or "").strip()
    latest_stable = release if is_stable(release) else None
    if latest_stable is None and stable_versions:
        latest_stable = stable_versions[-1]
    return {
        "latest-stable": latest_stable,
        "release": release or None,
        "stable-versions": stable_versions,
    }


def compatibility_prefix(version: str) -> tuple[int, ...]:
    numbers = [int(token) for token in re.findall(r"\d+", version)]
    if not numbers:
        return ()
    if numbers[0] == 0 and len(numbers) > 1:
        return tuple(numbers[:2])
    return (numbers[0],)


def select_latest_compatible(current: str, stable_versions: list[str]) -> str | None:
    prefix = compatibility_prefix(current)
    channel = variant_channel(current)
    compatible = [
        version
        for version in stable_versions
        if compatibility_prefix(version) == prefix
        and variant_channel(version) == channel
    ]
    return max(compatible, key=version_key) if compatible else None


def classify_line(
    *,
    current: str,
    latest_stable: str,
    latest_compatible: str | None,
    governance_disposition: str,
) -> str:
    if current == latest_stable:
        return "current"
    if latest_compatible and current != latest_compatible:
        if version_key(latest_compatible) <= version_key(current):
            return "hold-compatibility"
        return "adopt-latest"
    if (
        latest_compatible == current
        and compatibility_prefix(latest_stable) == compatibility_prefix(current)
        and (
            variant_channel(latest_stable) != variant_channel(current)
            or version_key(latest_stable) <= version_key(current)
        )
    ):
        return "hold-compatibility"
    if governance_disposition == "compatibility-line":
        return "hold-compatibility"
    return "defer-breaking-migration"


def disposition_reason(disposition: str) -> str:
    reasons = {
        "adopt-latest": "Adopt the latest stable release within the inferred compatibility line.",
        "current": "The current version already equals the authoritative latest stable release.",
        "defer-breaking-migration": "The authoritative latest stable release crosses the inferred compatibility boundary.",
        "hold-compatibility": "Preserve the current compatibility line; the automatic candidate is outside the line or is not newer.",
        "hold-unavailable": "No stable release is available for this declared line from the authoritative metadata source.",
    }
    return reasons[disposition]


def audit_record(
    record: dict[str, Any],
    *,
    fetch: Any,
    retrieved_at: str,
    line_overrides: dict[str, dict[str, str]] | None = None,
    authority_line_overrides: dict[str, dict[str, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    line_overrides = line_overrides or {}
    authority_line_overrides = authority_line_overrides or {}
    audited = copy.deepcopy(record)
    source = metadata_url(record["kind"], record["coordinate-or-plugin-id"])
    try:
        metadata = fetch(source)
        parsed = parse_metadata(metadata)
    except (OSError, TimeoutError) as error:
        audited["latest-stable"] = {
            "latest": None,
            "metadata-sha256": None,
            "reason": f"{type(error).__name__}: {error}",
            "retrieved-at": retrieved_at,
            "source": source,
            "status": "metadata-unavailable",
        }
        for line in audited["current-lines"]:
            line["disposition"] = "hold-unavailable"
            line["disposition-reason"] = disposition_reason("hold-unavailable")
            line["latest-compatible"] = None
        return audited

    latest_stable = parsed["latest-stable"]
    if latest_stable is None:
        audited["latest-stable"] = {
            "latest": None,
            "metadata-sha256": hashlib.sha256(metadata).hexdigest(),
            "reason": "Authoritative upstream metadata contains preview releases but no stable release.",
            "retrieved-at": retrieved_at,
            "source": source,
            "status": "preview-only",
            "upstream-release": parsed["release"],
        }
        for line in audited["current-lines"]:
            line["disposition"] = "hold-unavailable"
            line["disposition-reason"] = disposition_reason("hold-unavailable")
            line["latest-compatible"] = None
        return audited

    audited["latest-stable"] = {
        "latest": latest_stable,
        "metadata-sha256": hashlib.sha256(metadata).hexdigest(),
        "reason": "Authoritative upstream Maven metadata was parsed with preview versions excluded.",
        "retrieved-at": retrieved_at,
        "source": source,
        "status": "verified",
    }
    if parsed["release"] != latest_stable:
        audited["latest-stable"]["release-status"] = "preview-fallback"
        audited["latest-stable"]["upstream-release"] = parsed["release"]
    for line in audited["current-lines"]:
        latest_compatible = select_latest_compatible(
            line["current"], parsed["stable-versions"]
        )
        line["latest-compatible"] = latest_compatible
        line["disposition"] = classify_line(
            current=line["current"],
            latest_stable=latest_stable,
            latest_compatible=latest_compatible,
            governance_disposition=line["governance-disposition"],
        )
        line["disposition-reason"] = disposition_reason(line["disposition"])
        override = authority_line_overrides.get(record["authority-key"], {}).get(
            line["version-key"]
        ) or line_overrides.get(line["version-key"])
        if override:
            line["disposition"] = override["disposition"]
            line["disposition-reason"] = override["reason"]
    return audited


def build_audit(
    inventory: dict[str, Any],
    *,
    fetch: Any,
    retrieved_at: str,
    workers: int = 1,
    line_overrides: dict[str, dict[str, str]] | None = None,
    audit_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if audit_policy is not None:
        line_overrides = audit_policy["line-overrides"]
    authority_line_overrides = (
        audit_policy.get("authority-line-overrides", {}) if audit_policy else {}
    )
    def audit(record: dict[str, Any]) -> dict[str, Any]:
        return audit_record(
            record,
            fetch=fetch,
            retrieved_at=retrieved_at,
            line_overrides=line_overrides,
            authority_line_overrides=authority_line_overrides,
        )

    if workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            records = list(executor.map(audit, inventory["records"]))
    else:
        records = [audit(record) for record in inventory["records"]]
    metadata_statuses = Counter(
        record["latest-stable"]["status"] for record in records
    )
    line_dispositions = Counter(
        line["disposition"]
        for record in records
        for line in record["current-lines"]
    )
    inputs = {
            **inventory["inputs"],
            "inventory-sha256": hashlib.sha256(canonical_json(inventory)).hexdigest(),
    }
    if audit_policy is not None:
        inputs["audit-policy-sha256"] = hashlib.sha256(
            canonical_json(audit_policy)
        ).hexdigest()
    return {
        "inputs": inputs,
        "records": records,
        "retrieved-at": retrieved_at,
        "schema-version": 1,
        "scope": inventory["scope"],
        "summary": {
            "authority-count": len(records),
            "line-count": sum(len(record["current-lines"]) for record in records),
            "line-dispositions": dict(sorted(line_dispositions.items())),
            "metadata-unavailable": metadata_statuses["metadata-unavailable"],
            "metadata-preview-only": metadata_statuses["preview-only"],
            "metadata-verified": metadata_statuses["verified"],
        },
    }


def build_delta_ledger(
    *,
    baseline_catalog: str,
    candidate_catalog: str,
    audit: dict[str, Any],
    baseline_ref: str,
    audit_cutoff: str,
    rollout: str,
) -> dict[str, Any]:
    baseline_versions = parse_versions(baseline_catalog)
    candidate_versions = parse_versions(candidate_catalog)
    authorities_by_key: dict[str, list[dict[str, str]]] = {}
    for record in audit["records"]:
        for line in record["current-lines"]:
            authorities_by_key.setdefault(line["version-key"], []).append(
                {
                    "authority-key": record["authority-key"],
                    "coordinate-or-plugin-id": record["coordinate-or-plugin-id"],
                    "current": line["current"],
                    "disposition": line["disposition"],
                    "disposition-reason": line["disposition-reason"],
                    "kind": record["kind"],
                    "latest-compatible": line.get("latest-compatible"),
                    "metadata-status": record["latest-stable"]["status"],
                }
            )

    delta: list[dict[str, Any]] = []
    for version_key in sorted(candidate_versions):
        before = baseline_versions.get(version_key)
        after = candidate_versions[version_key]
        if before is None or before == after:
            continue
        authorities = authorities_by_key.get(version_key, [])
        if not authorities:
            raise RuntimeError(
                f"changed version key is absent from the authority audit: {version_key}"
            )
        if any(authority["metadata-status"] != "verified" for authority in authorities):
            raise RuntimeError(
                "changed version key lacks verified latest-compatible adoption "
                f"evidence: {version_key}"
            )
        if all(authority["latest-compatible"] == after for authority in authorities):
            adoption_evidence = {
                "classification": "verified-latest-compatible",
                "version": after,
            }
            reason = (
                "Adopt the audited latest stable release within the approved "
                "compatibility line."
            )
        elif all(
            authority["disposition"] == "hold-compatibility"
            and authority["current"] == after
            and authority["disposition-reason"]
            for authority in authorities
        ):
            adoption_evidence = {
                "classification": "verified-compatibility-alignment",
                "version": after,
            }
            reason = (
                "Align to the explicitly audited compatibility constraint shared "
                "by every governed authority."
            )
        else:
            raise RuntimeError(
                "changed version key lacks verified latest-compatible adoption "
                f"or compatibility-alignment evidence: {version_key}"
            )
        delta.append(
            {
                "adoption-evidence": adoption_evidence,
                "after": after,
                "authorities": sorted(
                    [
                        {
                            key: value
                            for key, value in authority.items()
                            if key
                            not in {
                                "current",
                                "disposition-reason",
                                "latest-compatible",
                                "metadata-status",
                            }
                        }
                        for authority in authorities
                    ],
                    key=lambda authority: (
                        authority["authority-key"],
                        authority["coordinate-or-plugin-id"],
                    ),
                ),
                "before": before,
                "reason": reason,
                "verification": "pending-resolved-graph",
                "version-key": version_key,
            }
        )

    audit_bytes = canonical_json(audit)
    return {
        "audit": {
            "path": "config/latest-stable-version-audit.json",
            "sha256": hashlib.sha256(audit_bytes).hexdigest(),
            "summary": audit["summary"],
        },
        "audit-cutoff": audit_cutoff,
        "baseline": {
            "catalog-ref": baseline_ref,
            "catalog-sha256": hashlib.sha256(baseline_catalog.encode()).hexdigest(),
        },
        "candidate": {
            "catalog-sha256": hashlib.sha256(candidate_catalog.encode()).hexdigest(),
        },
        "delta": delta,
        "rollout": rollout,
        "schema-version": 3,
        "status": "validation-pending",
    }


def upsert_catalog_rollout(
    document: dict[str, Any], authority_ledger: dict[str, Any]
) -> dict[str, Any]:
    updated = copy.deepcopy(document)
    rollout = {
        "audit": authority_ledger["audit"]["path"],
        "authority-delta-ledger": "config/latest-stable-version-deltas.json",
        "baseline-catalog-ref": authority_ledger["baseline"]["catalog-ref"],
        "catalog-sha256": authority_ledger["candidate"]["catalog-sha256"],
        "delta-count": len(authority_ledger["delta"]),
        "downstream-full-builds": {"repositories": 9, "status": "pending"},
        "publication-pom-verification": {"repositories": 9, "status": "pending"},
        "remote-immutable-ref-verification": "pending-candidate-commit-and-push",
        "resolved-graph-evidence": [],
        "rollout": authority_ledger["rollout"],
        "status": authority_ledger["status"],
    }
    existing = updated["subsequent-rollouts"]
    updated["subsequent-rollouts"] = [
        item for item in existing if item["rollout"] != rollout["rollout"]
    ] + [rollout]
    return updated


def validate_audit(
    audit: dict[str, Any],
    inventory: dict[str, Any],
    audit_policy: dict[str, Any] | None = None,
) -> None:
    expected_inventory_sha = hashlib.sha256(canonical_json(inventory)).hexdigest()
    if audit.get("inputs", {}).get("inventory-sha256") != expected_inventory_sha:
        raise RuntimeError("audit inventory SHA does not match the current inventory")
    if audit_policy is not None:
        expected_policy_sha = hashlib.sha256(canonical_json(audit_policy)).hexdigest()
        if audit.get("inputs", {}).get("audit-policy-sha256") != expected_policy_sha:
            raise RuntimeError("audit policy SHA does not match the current audit policy")

    if audit.get("schema-version") != 1:
        raise RuntimeError("audit schema version is invalid")
    if audit.get("scope") != inventory.get("scope"):
        raise RuntimeError("audit scope does not match the current inventory")
    for input_name in ("catalog", "policy"):
        if audit.get("inputs", {}).get(input_name) != inventory.get("inputs", {}).get(
            input_name
        ):
            raise RuntimeError(f"audit {input_name} input does not match inventory")

    inventory_by_key = {
        record["authority-key"]: record for record in inventory["records"]
    }
    expected_keys = set(inventory_by_key)
    records = audit.get("records", [])
    actual_keys = {record.get("authority-key") for record in records}
    if actual_keys != expected_keys or len(records) != len(expected_keys):
        raise RuntimeError("audit authority coverage does not match the current inventory")

    allowed_metadata_statuses = {"verified", "metadata-unavailable", "preview-only"}
    allowed_dispositions = {
        "adopt-latest",
        "current",
        "defer-breaking-migration",
        "hold-compatibility",
        "hold-unavailable",
    }
    metadata_statuses: Counter[str] = Counter()
    line_dispositions: Counter[str] = Counter()
    for record in records:
        inventory_record = inventory_by_key[record["authority-key"]]
        for field in (
            "aliases",
            "authority-key",
            "authority-source",
            "coordinate-or-plugin-id",
            "kind",
        ):
            if record.get(field) != inventory_record.get(field):
                raise RuntimeError(
                    f"audit record identity does not match inventory: {record['authority-key']}:{field}"
                )
        inventory_lines = {
            (line["line-id"], line["version-key"]): line
            for line in inventory_record["current-lines"]
        }
        audit_lines = {
            (line.get("line-id"), line.get("version-key")): line
            for line in record.get("current-lines", [])
        }
        if set(audit_lines) != set(inventory_lines):
            raise RuntimeError(
                f"audit line identity does not match inventory: {record['authority-key']}"
            )
        for line_key, inventory_line in inventory_lines.items():
            audit_line = audit_lines[line_key]
            for field in ("current", "governance-disposition", "line-id", "version-key"):
                if audit_line.get(field) != inventory_line.get(field):
                    raise RuntimeError(
                        f"audit line identity does not match inventory: {record['authority-key']}:{line_key}:{field}"
                    )

        metadata = record.get("latest-stable", {})
        metadata_status = metadata.get("status")
        if metadata_status not in allowed_metadata_statuses:
            raise RuntimeError(f"audit record is not explicit: {record['authority-key']}")
        if metadata.get("source") != metadata_url(
            record["kind"], record["coordinate-or-plugin-id"]
        ):
            raise RuntimeError(f"audit metadata source is invalid: {record['authority-key']}")
        if metadata.get("retrieved-at") != audit.get("retrieved-at"):
            raise RuntimeError(
                f"audit metadata retrieval time is invalid: {record['authority-key']}"
            )
        digest = metadata.get("metadata-sha256")
        if metadata_status == "verified":
            if (
                not isinstance(metadata.get("latest"), str)
                or not is_stable(metadata["latest"])
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise RuntimeError(
                    f"verified audit metadata is incomplete: {record['authority-key']}"
                )
        elif metadata_status == "preview-only":
            if (
                metadata.get("latest") is not None
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise RuntimeError(
                    f"preview-only audit metadata is incoherent: {record['authority-key']}"
                )
        elif metadata.get("latest") is not None or digest is not None:
            raise RuntimeError(
                f"unavailable audit metadata is incoherent: {record['authority-key']}"
            )
        metadata_statuses[metadata_status] += 1

        for line in record["current-lines"]:
            if line.get("disposition") not in allowed_dispositions:
                raise RuntimeError(
                    f"audit line disposition is not explicit: {record['authority-key']}:{line['line-id']}"
                )
            if not line.get("disposition-reason"):
                raise RuntimeError(
                    f"audit line reason is not explicit: {record['authority-key']}:{line['line-id']}"
                )
            if metadata_status in {"metadata-unavailable", "preview-only"} and (
                line["disposition"] != "hold-unavailable"
                or line.get("latest-compatible") is not None
            ):
                raise RuntimeError(
                    f"unavailable audit line is not fail-closed: {record['authority-key']}:{line['line-id']}"
                )
            line_dispositions[line["disposition"]] += 1

    expected_summary = {
        "authority-count": len(records),
        "line-count": sum(len(record["current-lines"]) for record in records),
        "line-dispositions": dict(sorted(line_dispositions.items())),
        "metadata-unavailable": metadata_statuses["metadata-unavailable"],
        "metadata-preview-only": metadata_statuses["preview-only"],
        "metadata-verified": metadata_statuses["verified"],
    }
    if audit.get("summary") != expected_summary:
        raise RuntimeError("audit summary does not match audited records")


def fetch_metadata(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "bluetape4k-dependencies-latest-stable-audit/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


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


def parse_versioned_aliases(catalog: str) -> list[tuple[str, str, str, str]]:
    aliases: list[tuple[str, str, str, str]] = []
    for kind, section_name in (("library", "libraries"), ("plugin", "plugins")):
        for line in catalog_section(catalog, section_name).splitlines():
            alias = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*\{', line)
            version_ref = re.search(r'version\.ref\s*=\s*"([^"]+)"', line)
            if alias is None or version_ref is None:
                continue
            if kind == "library":
                module = re.search(r'module\s*=\s*"([^"]+)"', line)
                group = re.search(r'group\s*=\s*"([^"]+)"', line)
                name = re.search(r'name\s*=\s*"([^"]+)"', line)
                if module:
                    subject = module.group(1)
                elif group and name:
                    subject = f"{group.group(1)}:{name.group(1)}"
                else:
                    continue
            else:
                plugin_id = re.search(r'id\s*=\s*"([^"]+)"', line)
                if plugin_id is None:
                    continue
                subject = plugin_id.group(1)
            aliases.append((kind, subject, alias.group(1), version_ref.group(1)))
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


def sync_policy_versions(policy: dict[str, Any], catalog: str) -> dict[str, Any]:
    synced = copy.deepcopy(policy)
    versions = parse_versions(catalog)
    for subject in synced["subjects"]:
        for line in subject["lines"]:
            version_key = line.get("version-key")
            if version_key:
                if version_key not in versions:
                    raise RuntimeError(
                        f"policy version key is absent from catalog: {version_key}"
                    )
                line["version"] = versions[version_key]
    return synced


def build_catalog_direct_records(
    catalog: str, represented: set[tuple[str, str]]
) -> list[dict[str, Any]]:
    versions = parse_versions(catalog)
    grouped: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for kind, subject, alias, version_key in parse_versioned_aliases(catalog):
        if (kind, subject) in represented:
            continue
        if kind == "library" and subject.startswith("io.github.bluetape4k"):
            continue
        grouped.setdefault((kind, subject), []).append((alias, version_key))

    records: list[dict[str, Any]] = []
    for (kind, subject), aliases_and_keys in sorted(grouped.items()):
        version_keys = sorted({version_key for _, version_key in aliases_and_keys})
        disposition = "compatibility-line" if len(version_keys) > 1 else "central-direct"
        records.append(
            {
                "aliases": sorted({alias for alias, _ in aliases_and_keys}),
                "authority-key": f"catalog:{kind}:{subject}",
                "authority-source": "catalog-direct",
                "coordinate-or-plugin-id": subject,
                "current-lines": [
                    {
                        "current": versions[version_key],
                        "governance-disposition": disposition,
                        "line-id": version_key,
                        "version-key": version_key,
                    }
                    for version_key in version_keys
                ],
                "kind": kind,
                "latest-stable": pending_latest_stable(),
            }
        )
    return records


def build_inventory(catalog_path: Path, policy_path: Path) -> dict[str, Any]:
    catalog = catalog_path.read_text(encoding="utf-8")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    managed_records = build_managed_records(catalog)
    policy_records = build_policy_records(policy)
    represented = {
        (record["kind"], record["coordinate-or-plugin-id"])
        for record in managed_records + policy_records
    }
    catalog_records = build_catalog_direct_records(catalog, represented)
    records = sorted(
        managed_records + policy_records + catalog_records,
        key=lambda record: record["authority-key"],
    )

    if (
        len(managed_records) != 325
        or len(policy_records) != 70
        or len(catalog_records) != 114
        or len(records) != 509
    ):
        raise RuntimeError(
            "authority universe changed; expected 325 managed + 70 policy + 114 catalog = 509, "
            f"found {len(managed_records)} + {len(policy_records)} + "
            f"{len(catalog_records)} = {len(records)}"
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
            "catalog-direct": len(catalog_records),
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
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--audit-policy", type=Path, default=DEFAULT_AUDIT_POLICY)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--refresh-audit", action="store_true")
    parser.add_argument("--check-audit", action="store_true")
    parser.add_argument("--audit-summary", action="store_true")
    parser.add_argument("--write-policy-versions", action="store_true")
    parser.add_argument("--refresh-delta-ledger", action="store_true")
    parser.add_argument("--baseline-ref")
    parser.add_argument("--delta-ledger", type=Path, default=DEFAULT_DELTA_LEDGER)
    parser.add_argument("--refresh-central-rollout", action="store_true")
    parser.add_argument(
        "--central-delta-ledger", type=Path, default=DEFAULT_CENTRAL_DELTA_LEDGER
    )
    parser.add_argument("--central-ledger-base-ref")
    parser.add_argument(
        "--audit-cutoff", default=dt.datetime.now(dt.timezone.utc).date().isoformat()
    )
    parser.add_argument("--rollout", default="2026-08-05-issue-169-full-authority-audit")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write_policy_versions:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        catalog = args.catalog.read_text(encoding="utf-8")
        args.policy.write_bytes(canonical_json(sync_policy_versions(policy, catalog)))
    inventory = build_inventory(args.catalog, args.policy)
    audit = None
    audit_policy = json.loads(args.audit_policy.read_text(encoding="utf-8"))
    if args.refresh_audit:
        retrieved_at = utc_timestamp()
        audit = build_audit(
            inventory,
            fetch=lambda url: fetch_metadata(url, args.timeout),
            retrieved_at=retrieved_at,
            workers=args.workers,
            audit_policy=audit_policy,
        )
        args.audit_output.write_bytes(canonical_json(audit))
    if args.refresh_delta_ledger:
        if not args.baseline_ref:
            raise RuntimeError("--baseline-ref is required with --refresh-delta-ledger")
        baseline_catalog = subprocess.run(
            ["git", "show", f"{args.baseline_ref}:gradle/libs.versions.toml"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if audit is None:
            audit = json.loads(args.audit_output.read_text(encoding="utf-8"))
        validate_audit(audit, inventory, audit_policy)
        ledger = build_delta_ledger(
            baseline_catalog=baseline_catalog,
            candidate_catalog=args.catalog.read_text(encoding="utf-8"),
            audit=audit,
            baseline_ref=args.baseline_ref,
            audit_cutoff=args.audit_cutoff,
            rollout=args.rollout,
        )
        args.delta_ledger.write_bytes(pretty_json(ledger))
    if args.refresh_central_rollout:
        if args.central_ledger_base_ref:
            document_text = subprocess.run(
                [
                    "git",
                    "show",
                    f"{args.central_ledger_base_ref}:config/central-catalog-version-deltas.json",
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        else:
            document_text = args.central_delta_ledger.read_text(encoding="utf-8")
        document = json.loads(document_text)
        authority_ledger = json.loads(args.delta_ledger.read_text(encoding="utf-8"))
        args.central_delta_ledger.write_bytes(
            pretty_json(upsert_catalog_rollout(document, authority_ledger))
        )
    if args.write:
        args.output.write_bytes(canonical_json(inventory))
    if args.check:
        check_inventory(args.output, args.catalog, args.policy)
    if args.summary:
        summary = inventory["summary"]
        print(
            f"authority={summary['authority-count']} managed={summary['managed-generated']} "
            f"policy={summary['policy-subjects']} catalog={summary['catalog-direct']} "
            f"audit-pending={summary['audit-pending']}"
        )
    if args.check_audit:
        audit = json.loads(args.audit_output.read_text(encoding="utf-8"))
        validate_audit(audit, inventory, audit_policy)
    if args.audit_summary:
        if audit is None:
            audit = json.loads(args.audit_output.read_text(encoding="utf-8"))
        summary = audit["summary"]
        dispositions = " ".join(
            f"{name}={count}"
            for name, count in summary["line-dispositions"].items()
        )
        print(
            f"authority={summary['authority-count']} lines={summary['line-count']} "
            f"metadata-verified={summary['metadata-verified']} "
            f"metadata-preview-only={summary.get('metadata-preview-only', 0)} "
            f"metadata-unavailable={summary['metadata-unavailable']} {dispositions}"
        )
    if not (
        args.write
        or args.check
        or args.summary
        or args.refresh_audit
        or args.check_audit
        or args.audit_summary
        or args.write_policy_versions
        or args.refresh_delta_ledger
        or args.refresh_central_rollout
    ):
        print(canonical_json(inventory).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
