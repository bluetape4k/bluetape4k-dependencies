#!/usr/bin/env python3
"""Resolve every latest-stable delta authority at baseline and candidate versions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO_ROOT / "config" / "latest-stable-version-deltas.json"
DEFAULT_CATALOG = REPO_ROOT / "gradle" / "libs.versions.toml"
DEFAULT_CATALOG_SIDECAR = REPO_ROOT / "gradle" / "libs.versions.toml.sha256"
FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
DYNAMIC_VERSION = re.compile(r"(?:\+|^latest\.|[\[\]()])")
PREVIEW_VERSION = re.compile(
    r"(?i)(?:snapshot|alpha|beta|preview|milestone|incubating|nightly|eap|"
    r"(?:^|[-.])(?:dev|test)(?:$|[-.])|"
    r"\d(?:a|b|m|rc|cr|ea)\d*(?=$|[-.])|"
    r"(?:^|[-.])(?:a|b|m|rc|cr|ea)(?:[-.]?\d+)?(?:$|[-.]))"
)
COORDINATE = re.compile(r"^[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+$")
OUTPUT_PREFIX = "BT4K_RESOLUTION\t"


class ResolutionSpec(NamedTuple):
    spec_id: str
    version_key: str
    kind: str
    subject: str
    coordinate: str
    before: str
    after: str


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def pretty_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_receipt_command(command: Sequence[str]) -> list[str]:
    normalized = list(command)
    normalized[0] = "./gradlew"
    try:
        project_index = normalized.index("-p") + 1
    except (ValueError, IndexError) as exc:
        raise RuntimeError("Gradle command lacks temporary project argument") from exc
    normalized[project_index] = "<temporary-project>"
    return normalized


def _exact_version(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or DYNAMIC_VERSION.search(value)
        or PREVIEW_VERSION.search(value)
    ):
        raise RuntimeError(f"{label} must be an exact stable version")
    return value


def catalog_versions(catalog: Path) -> dict[str, str]:
    content = catalog.read_text(encoding="utf-8")
    try:
        versions_section = content.split("[versions]", 1)[1].split("\n[", 1)[0]
    except IndexError as exc:
        raise RuntimeError("catalog lacks a versions section") from exc
    return dict(
        re.findall(
            r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"',
            versions_section,
            flags=re.MULTILINE,
        )
    )


def validate_catalog(ledger: dict[str, Any], catalog: Path, sidecar: Path) -> str:
    catalog_sha = sha256_bytes(catalog.read_bytes())
    if ledger.get("candidate", {}).get("catalog-sha256") != catalog_sha:
        raise RuntimeError("candidate ledger SHA does not match current catalog bytes")
    sidecar_token = sidecar.read_text(encoding="utf-8").split(maxsplit=1)[0]
    if sidecar_token != catalog_sha:
        raise RuntimeError(
            "catalog checksum sidecar does not match current catalog bytes"
        )
    versions = catalog_versions(catalog)
    for entry in ledger.get("delta", []):
        version_key = entry.get("version-key")
        if versions.get(version_key) != entry.get("after"):
            raise RuntimeError(f"catalog version does not match ledger: {version_key}")
    return catalog_sha


def _plugin_marker(plugin_id: str) -> str:
    if not plugin_id or ":" in plugin_id:
        raise RuntimeError(f"invalid plugin id: {plugin_id}")
    return f"{plugin_id}:{plugin_id}.gradle.plugin"


def build_specs(ledger: dict[str, Any]) -> tuple[ResolutionSpec, ...]:
    if ledger.get("schema-version") != 3:
        raise RuntimeError("latest-stable delta ledger schema must be 3")
    status = ledger.get("status")
    verification_by_status = {
        "validation-pending": "pending-resolved-graph",
        "verified-resolved-graph": "verified-resolved-graph",
    }
    if status not in verification_by_status:
        raise RuntimeError("latest-stable delta ledger has unsupported status")
    expected_verification = verification_by_status[status]
    delta = ledger.get("delta")
    if not isinstance(delta, list) or not delta:
        raise RuntimeError("latest-stable delta ledger has no deltas")

    specs: list[ResolutionSpec] = []
    seen: set[str] = set()
    for delta_index, entry in enumerate(delta):
        if not isinstance(entry, dict):
            raise TypeError(f"invalid delta at index {delta_index}")
        version_key = entry.get("version-key")
        if not isinstance(version_key, str) or not version_key:
            raise RuntimeError(f"invalid version key at index {delta_index}")
        before = _exact_version(entry.get("before"), f"{version_key} before")
        after = _exact_version(entry.get("after"), f"{version_key} after")
        if before == after:
            raise RuntimeError(f"delta does not change version: {version_key}")
        if entry.get("verification") != expected_verification:
            raise RuntimeError(
                f"delta verification does not match ledger: {version_key}"
            )
        authorities = entry.get("authorities")
        if not isinstance(authorities, list) or not authorities:
            raise RuntimeError(f"delta has no authorities: {version_key}")
        for authority_index, authority in enumerate(authorities):
            if not isinstance(authority, dict):
                raise TypeError(f"invalid authority for {version_key}")
            kind = authority.get("kind")
            subject = authority.get("coordinate-or-plugin-id")
            if kind not in {"library", "plugin"} or not isinstance(subject, str):
                raise RuntimeError(f"invalid authority for {version_key}")
            coordinate = subject if kind == "library" else _plugin_marker(subject)
            if COORDINATE.fullmatch(coordinate) is None:
                raise RuntimeError(f"invalid authority coordinate: {coordinate}")
            identity = f"{version_key}\0{kind}\0{subject}".encode()
            spec_id = hashlib.sha256(identity).hexdigest()
            if spec_id in seen:
                raise RuntimeError(f"duplicate resolution authority: {version_key}")
            seen.add(spec_id)
            specs.append(
                ResolutionSpec(
                    spec_id,
                    version_key,
                    kind,
                    subject,
                    coordinate,
                    before,
                    after,
                )
            )
    return tuple(
        sorted(specs, key=lambda spec: (spec.version_key, spec.kind, spec.subject))
    )


def resolution_contract(ledger: dict[str, Any]) -> dict[str, Any]:
    excluded_top = {
        "candidate-validation-evidence",
        "resolved-graph-evidence",
        "status",
    }
    contract = {
        key: copy.deepcopy(value)
        for key, value in ledger.items()
        if key not in excluded_top and key != "delta"
    }
    contract["delta"] = [
        {
            key: copy.deepcopy(value)
            for key, value in entry.items()
            if key not in {"resolved-graph-specs", "verification"}
        }
        for entry in ledger["delta"]
    ]
    return contract


def resolution_contract_sha256(ledger: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(resolution_contract(ledger)))


def render_gradle_project(specs: Sequence[ResolutionSpec]) -> tuple[str, str]:
    if not specs:
        raise RuntimeError("resolution spec list must not be empty")
    settings = 'rootProject.name = "latest-stable-resolved-graphs"\n'
    records = [
        {
            "specId": spec.spec_id,
            "phase": phase,
            "coordinate": spec.coordinate,
            "version": getattr(spec, phase),
            "configuration": f"g{index:03d}{phase.title()}",
        }
        for index, spec in enumerate(specs)
        for phase in ("before", "after")
    ]
    records_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    configuration_blocks = "\n".join(
        f'''configurations.create("{record["configuration"]}") {{
    canBeConsumed = false
    canBeResolved = true
    transitive = true
    attributes {{
        attribute(
            org.gradle.api.attributes.Usage.USAGE_ATTRIBUTE,
            objects.named(org.gradle.api.attributes.Usage, org.gradle.api.attributes.Usage.JAVA_RUNTIME)
        )
        attribute(
            org.gradle.api.attributes.Bundling.BUNDLING_ATTRIBUTE,
            objects.named(org.gradle.api.attributes.Bundling, org.gradle.api.attributes.Bundling.EXTERNAL)
        )
        attribute(
            org.gradle.api.attributes.java.TargetJvmEnvironment.TARGET_JVM_ENVIRONMENT_ATTRIBUTE,
            objects.named(
                org.gradle.api.attributes.java.TargetJvmEnvironment,
                org.gradle.api.attributes.java.TargetJvmEnvironment.STANDARD_JVM
            )
        )
    }}
}}
dependencies.add("{record["configuration"]}", "{record["coordinate"]}:{record["version"]}")'''
        for record in records
    )
    build = f'''import groovy.json.JsonOutput

repositories {{
    exclusiveContent {{
        forRepository {{
            maven {{
                name = "osgeoJai"
                url = uri("https://repo.osgeo.org/repository/release/")
            }}
        }}
        filter {{
            includeGroup("javax.media")
        }}
    }}
    mavenCentral()
    maven {{ url = uri("https://plugins.gradle.org/m2/") }}
    maven {{ url = uri("https://repo.gradle.org/gradle/libs-releases") }}
    maven {{ url = uri("https://repo.osgeo.org/repository/release/") }}
    maven {{ url = uri("https://artifacts.unidata.ucar.edu/repository/unidata-all/") }}
}}

def records = new groovy.json.JsonSlurper().parseText('{records_json}')
{configuration_blocks}

tasks.register("resolveLatestStableGraphs") {{
    doLast {{
        records.each {{ record ->
            def configuration = configurations.getByName(record.configuration)
            configuration.resolve()
            def result = configuration.incoming.resolutionResult
            def selected = result.root.dependencies.find {{ dependency ->
                dependency instanceof org.gradle.api.artifacts.result.ResolvedDependencyResult &&
                    dependency.requested.group == record.coordinate.tokenize(":")[0] &&
                    dependency.requested.module == record.coordinate.tokenize(":")[1]
            }}
            def unresolved = result.allDependencies.find {{ dependency ->
                dependency instanceof org.gradle.api.artifacts.result.UnresolvedDependencyResult
            }}
            if (unresolved != null) {{
                def causes = []
                def failure = unresolved.failure
                while (failure != null) {{
                    causes.add(failure.class.name + ": " + failure.message)
                    failure = failure.cause
                }}
                throw new GradleException(
                    "Unresolved dependency ${{unresolved.requested.displayName}}: " +
                        causes.join(" | ")
                )
            }}
            def components = result.allComponents.collect {{ component ->
                component.id.displayName
            }}.sort()
            println("{OUTPUT_PREFIX}" + JsonOutput.toJson([
                spec_id: record.specId,
                phase: record.phase,
                requested: record.version,
                selected: selected?.selected?.moduleVersion?.version,
                components: components,
            ]))
        }}
    }}
}}
'''
    return settings, build


def parse_gradle_output(output: str) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    for line in output.splitlines():
        if not line.startswith(OUTPUT_PREFIX):
            continue
        try:
            record = json.loads(line.removeprefix(OUTPUT_PREFIX))
        except json.JSONDecodeError as exc:
            raise RuntimeError("invalid Gradle resolution output") from exc
        expected = {"spec_id", "phase", "requested", "selected", "components"}
        if not isinstance(record, dict) or set(record) != expected:
            raise RuntimeError("invalid Gradle resolution record")
        components = record.pop("components")
        if not isinstance(components, list) or not all(
            isinstance(component, str) and component for component in components
        ):
            raise RuntimeError("invalid resolved component graph")
        record["components"] = sorted(components)
        record["graph_sha256"] = sha256_bytes(canonical_json(record["components"]))
        observations.append(record)
    return observations


def validate_observations(
    specs: Sequence[ResolutionSpec], observations: Sequence[dict[str, object]]
) -> tuple[dict[str, object], ...]:
    expected = {
        (spec.spec_id, phase): (spec, getattr(spec, phase))
        for spec in specs
        for phase in ("before", "after")
    }
    validated: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, value in enumerate(observations):
        fields = {
            "spec_id",
            "phase",
            "requested",
            "selected",
            "components",
            "graph_sha256",
        }
        if set(value) != fields:
            raise RuntimeError(f"invalid observation fields at index {index}")
        if value["selected"] is None:
            raise RuntimeError(f"unresolved dependency at observation index {index}")
        string_fields = fields - {"components"}
        if not all(isinstance(value[field], str) for field in string_fields):
            raise RuntimeError(f"invalid observation fields at index {index}")
        components = value["components"]
        if not isinstance(components, list) or not all(
            isinstance(component, str) and component for component in components
        ):
            raise RuntimeError(f"invalid observation components at index {index}")
        item = dict(value)
        key = (item["spec_id"], item["phase"])
        if key in seen:
            raise RuntimeError(f"duplicate resolved graph observation: {key}")
        seen.add(key)
        if key not in expected:
            raise RuntimeError(f"extra resolved graph observation: {key}")
        _spec, exact_version = expected[key]
        requested = str(item["requested"])
        selected = str(item["selected"])
        if DYNAMIC_VERSION.search(requested) or DYNAMIC_VERSION.search(selected):
            raise RuntimeError(f"dynamic resolved graph version: {key}")
        if requested != exact_version:
            raise RuntimeError(f"requested version mismatch: {key}")
        if selected != exact_version:
            raise RuntimeError(f"selected version mismatch: {key}")
        graph_sha = str(item["graph_sha256"])
        if FULL_SHA256.fullmatch(graph_sha) is None:
            raise RuntimeError(f"invalid graph SHA: {key}")
        expected_graph_sha = sha256_bytes(canonical_json(sorted(components)))
        if graph_sha != expected_graph_sha:
            raise RuntimeError(f"graph SHA mismatch: {key}")
        item["components"] = sorted(components)
        validated.append(item)
    missing = set(expected) - seen
    if missing:
        raise RuntimeError(f"missing resolved graph observations: {len(missing)}")
    return tuple(sorted(validated, key=lambda item: (item["spec_id"], item["phase"])))


def build_graph_deltas(
    specs: Sequence[ResolutionSpec], observations: Sequence[dict[str, object]]
) -> tuple[dict[str, object], ...]:
    by_key = {(str(item["spec_id"]), str(item["phase"])): item for item in observations}
    deltas: list[dict[str, object]] = []
    for spec in specs:
        before = set(by_key[(spec.spec_id, "before")]["components"])
        after = set(by_key[(spec.spec_id, "after")]["components"])
        deltas.append(
            {
                "added-components": sorted(after - before),
                "removed-components": sorted(before - after),
                "spec_id": spec.spec_id,
            }
        )
    return tuple(sorted(deltas, key=lambda item: str(item["spec_id"])))


def validate_receipt(
    ledger: dict[str, Any], receipt: dict[str, Any]
) -> tuple[dict[str, object], ...]:
    expected_keys = {
        "catalog-sha256",
        "command",
        "graph-deltas",
        "ledger-contract-sha256",
        "log-sha256",
        "observation-count",
        "observations",
        "schema-version",
        "spec-count",
        "status",
    }
    if set(receipt) != expected_keys or receipt.get("schema-version") != 2:
        raise RuntimeError("invalid resolved graph receipt schema")
    if receipt.get("status") != "verified-resolved-graph":
        raise RuntimeError("resolved graph receipt is not verified")
    if receipt.get("catalog-sha256") != ledger["candidate"]["catalog-sha256"]:
        raise RuntimeError("resolved graph receipt catalog SHA mismatch")
    if receipt.get("ledger-contract-sha256") != resolution_contract_sha256(ledger):
        raise RuntimeError("resolved graph receipt contract SHA mismatch")
    specs = build_specs(ledger)
    observations = receipt.get("observations")
    if not isinstance(observations, list):
        raise TypeError("resolved graph receipt observations are invalid")
    validated = validate_observations(specs, observations)
    if receipt.get("spec-count") != len(specs):
        raise RuntimeError("resolved graph receipt spec count mismatch")
    if receipt.get("observation-count") != len(validated):
        raise RuntimeError("resolved graph receipt observation count mismatch")
    if receipt.get("graph-deltas") != list(build_graph_deltas(specs, validated)):
        raise RuntimeError("resolved graph receipt graph deltas mismatch")
    return validated


def promote_ledger(
    ledger: dict[str, Any],
    specs: Sequence[ResolutionSpec],
    observations: Sequence[dict[str, object]],
    *,
    receipt_path: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    if FULL_SHA256.fullmatch(receipt_sha256) is None:
        raise RuntimeError("invalid resolved graph receipt SHA")
    if Path(receipt_path).is_absolute() or ".." in Path(receipt_path).parts:
        raise RuntimeError("resolved graph receipt path must be repository-relative")
    validate_observations(specs, list(observations))
    by_version_key: dict[str, list[str]] = {}
    for spec in specs:
        by_version_key.setdefault(spec.version_key, []).append(spec.spec_id)
    promoted = copy.deepcopy(ledger)
    for delta in promoted["delta"]:
        spec_ids = sorted(by_version_key.get(delta["version-key"], []))
        if not spec_ids:
            raise RuntimeError(
                f"delta lacks resolved graph specs: {delta['version-key']}"
            )
        delta["verification"] = "verified-resolved-graph"
        delta["resolved-graph-specs"] = spec_ids
    promoted["resolved-graph-evidence"] = {
        "observation-count": len(observations),
        "path": receipt_path,
        "sha256": receipt_sha256,
        "spec-count": len(specs),
    }
    promoted["status"] = "verified-resolved-graph"
    return promoted


def run_gradle(
    specs: Sequence[ResolutionSpec], output_log: Path
) -> tuple[list[dict[str, object]], list[str]]:
    settings, build = render_gradle_project(specs)
    (REPO_ROOT / "build").mkdir(parents=True, exist_ok=True)
    output_log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="resolved-graphs-", dir=REPO_ROOT / "build"
    ) as directory:
        project = Path(directory)
        (project / "settings.gradle").write_text(settings, encoding="utf-8")
        (project / "build.gradle").write_text(build, encoding="utf-8")
        command = [
            str(REPO_ROOT / "gradlew"),
            "-p",
            str(project),
            "resolveLatestStableGraphs",
            "--no-daemon",
            "--no-configuration-cache",
            "--no-build-cache",
            "--console=plain",
        ]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    combined = result.stdout + result.stderr
    output_log.write_text(combined, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(
            f"Gradle resolved graph verification failed with exit {result.returncode}; "
            f"see {output_log}"
        )
    return parse_gradle_output(combined), command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--catalog-sidecar", type=Path, default=DEFAULT_CATALOG_SIDECAR)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--refresh-evidence", action="store_true")
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    if args.promote and args.refresh_evidence:
        raise RuntimeError("promotion and evidence refresh are mutually exclusive")
    if args.promote and ledger.get("status") != "validation-pending":
        raise RuntimeError("only a pending ledger can be promoted")
    if args.refresh_evidence and ledger.get("status") != "verified-resolved-graph":
        raise RuntimeError("only a promoted ledger can refresh evidence")
    validate_catalog(ledger, args.catalog, args.catalog_sidecar)
    specs = build_specs(ledger)
    raw_observations, command = run_gradle(specs, args.log)
    observations = validate_observations(specs, raw_observations)
    receipt = {
        "catalog-sha256": ledger["candidate"]["catalog-sha256"],
        "command": normalize_receipt_command(command),
        "graph-deltas": list(build_graph_deltas(specs, observations)),
        "ledger-contract-sha256": resolution_contract_sha256(ledger),
        "log-sha256": sha256_bytes(args.log.read_bytes()),
        "observation-count": len(observations),
        "observations": list(observations),
        "schema-version": 2,
        "spec-count": len(specs),
        "status": "verified-resolved-graph",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_bytes(pretty_json(receipt))
    receipt_sha = sha256_bytes(args.receipt.read_bytes())
    if args.promote or args.refresh_evidence:
        try:
            relative_receipt = args.receipt.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError as exc:
            raise RuntimeError(
                "promoted receipt must be inside the repository"
            ) from exc
        if args.promote:
            promoted = promote_ledger(
                ledger,
                specs,
                observations,
                receipt_path=relative_receipt,
                receipt_sha256=receipt_sha,
            )
        else:
            promoted = copy.deepcopy(ledger)
            promoted["resolved-graph-evidence"] = {
                "observation-count": len(observations),
                "path": relative_receipt,
                "sha256": receipt_sha,
                "spec-count": len(specs),
            }
        args.ledger.write_bytes(pretty_json(promoted))
    print(
        f"status=verified-resolved-graph specs={len(specs)} "
        f"observations={len(observations)} receipt-sha256={receipt_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
