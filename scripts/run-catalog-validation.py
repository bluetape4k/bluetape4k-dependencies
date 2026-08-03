#!/usr/bin/env python3
"""Run credential-free, manifest-bound catalog validation stages."""

from __future__ import annotations

import argparse
import enum
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


class Stage(enum.Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"
    G6 = "G6"
    G7 = "G7"
    G8 = "G8"


TRAIN_BUDGET_SECONDS = 330 * 60
STAGE_BUDGET_SECONDS = {
    Stage.G1: 6 * 60,
    Stage.G2: 6 * 60,
    Stage.G3: 6 * 60,
    Stage.G4: 6 * 60,
    Stage.G5: 6 * 60,
    Stage.G6: 120 * 60,
    Stage.G7: 60 * 60,
    Stage.G8: 90 * 60,
}
GRADLE_FLAGS = (
    "--offline",
    "--no-daemon",
    "--no-configuration-cache",
    "--no-build-cache",
    "--console=plain",
)
FORBIDDEN_TASK = re.compile(r"(?:publish|sign|upload)", re.IGNORECASE)
FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _candidate_module():
    path = Path(__file__).resolve().with_name("catalog_candidate.py")
    spec = importlib.util.spec_from_file_location("catalog_candidate_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sanitized_environment(
    source: Mapping[str, str], home: Path, gradle_home: Path
) -> dict[str, str]:
    result = {
        key: source[key]
        for key in ("PATH", "JAVA_HOME", "LANG", "LC_ALL")
        if source.get(key)
    }
    result["HOME"] = str(home)
    result["GRADLE_USER_HOME"] = str(gradle_home)
    return result


def gradle_command(tasks: Sequence[str]) -> tuple[str, ...]:
    if not tasks:
        raise RuntimeError("Gradle task list must not be empty")
    if any(FORBIDDEN_TASK.search(task) for task in tasks):
        raise RuntimeError("forbidden publish/sign/upload Gradle task")
    if any(token in {"dependsOn", "finalizedBy"} for token in tasks):
        raise RuntimeError("forbidden task graph injection")
    return ("./gradlew", *tasks, *GRADLE_FLAGS)


def validate_build_text(text: str) -> None:
    if re.search(
        r'(?i)(?:version\s*=\s*["\'](?:latest\.|[^"\']*\+)|["\'](?:latest\.|[^"\']*\+)["\'])',
        text,
    ):
        raise RuntimeError("dynamic version is forbidden")
    if re.search(r"https?://|mavenLocal\s*\(", text):
        raise RuntimeError("source repository declaration is forbidden")
    if re.search(r"\b(?:dependsOn|finalizedBy)\b", text):
        raise RuntimeError("task graph mutation is forbidden")


def predecessor(stage: Stage) -> Stage | None:
    if stage is Stage.G1:
        return None
    return Stage(f"G{int(stage.value[1:]) - 1}")


def require_predecessor(
    stage: Stage, receipt: Mapping[str, object] | None, manifest_sha256: str
) -> None:
    required = predecessor(stage)
    if required is None:
        return
    if (
        receipt is None
        or receipt.get("stage") != required.value
        or receipt.get("status") != "PASS"
    ):
        raise RuntimeError(f"{stage.value} predecessor {required.value} is not PASS")
    if receipt.get("manifest_sha256") != manifest_sha256:
        raise RuntimeError("predecessor manifest SHA-256 mismatch")


def evidence_root(manifest: Mapping[str, object]) -> Path:
    try:
        central_root = Path(str(manifest["central_root"]))
        digest = manifest["catalog_lock"]["catalogs"]["central"]["sha256"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("manifest is missing central catalog lock") from exc
    if not isinstance(digest, str) or FULL_SHA256.fullmatch(digest) is None:
        raise RuntimeError("central catalog SHA must be lowercase full SHA-256")
    return central_root / "build" / "catalog-authority" / digest


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_and_verify_manifest(path: Path) -> tuple[dict[str, object], str]:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise RuntimeError(
            "manifest path must be absolute, canonical, and non-symlinked"
        )
    module = _candidate_module()
    manifest = module.verify_candidate_manifest(path)
    return manifest, hashlib.sha256(path.read_bytes()).hexdigest()


def run_stage(manifest: dict[str, object], manifest_sha256: str, stage: Stage) -> int:
    root = evidence_root(manifest)
    receipts = root / "receipts" / stage.value
    aggregate = receipts / "aggregate.json"
    previous = predecessor(stage)
    previous_receipt = None
    if previous is not None:
        prior_path = root / "receipts" / previous.value / "aggregate.json"
        if prior_path.is_file() and not prior_path.is_symlink():
            previous_receipt = json.loads(prior_path.read_bytes())
    try:
        require_predecessor(stage, previous_receipt, manifest_sha256)
        if shutil.which("sandbox-exec") is None:
            raise RuntimeError(
                "sandbox-exec is unavailable; unsandboxed fallback is forbidden"
            )
        raise RuntimeError(
            f"{stage.value} execution is not implemented; zero-child fail-closed hold"
        )
    except RuntimeError as exc:
        status, reason = "BLOCKED", str(exc)
    payload = {
        "schema_version": 1,
        "stage": stage.value,
        "status": status,
        "manifest_sha256": manifest_sha256,
        "zero_child_launch": True,
        "reason": reason,
    }
    _candidate_module().write_atomic(aggregate, canonical_bytes(payload))
    return 0 if status == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--stage", choices=[stage.value for stage in Stage], required=True
    )
    args = parser.parse_args()
    manifest, digest = load_and_verify_manifest(args.manifest)
    return run_stage(manifest, digest, Stage(args.stage))


if __name__ == "__main__":
    raise SystemExit(main())
