#!/usr/bin/env python3
"""Snapshot train별 report-only 공급망 증거와 triage metadata를 생성한다."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import shlex
import sys
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPOSITORY_ROOT / "config" / "supply-chain-report-only.json"
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "build" / "supply-chain-report"
TRAIN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")


class GenerationError(ValueError):
    pass


def _read_report(path: Path) -> dict[str, object]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationError(f"cannot load source report: {path}") from exc
    if not isinstance(report, dict) or not isinstance(report.get("records"), list):
        raise GenerationError("source report must be an object with records")
    if report.get("report-only") is not True:
        raise GenerationError("source report-only must be true")
    return report


def _parse_generated_at(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GenerationError("generated-at must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise GenerationError("generated-at must include a timezone")
    return parsed


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _triage(records: list[object], *, as_of: dt.date) -> dict[str, object]:
    review_records: list[str] = []
    high_critical_reachable: list[str] = []
    expired_exceptions: list[str] = []
    ownership: list[dict[str, str]] = []

    for record in records:
        if not isinstance(record, dict):
            raise GenerationError("each source record must be an object")
        record_id = record.get("id")
        owner = record.get("owner")
        evidence_url = record.get("evidence-url")
        if not all(
            isinstance(value, str) and value
            for value in (record_id, owner, evidence_url)
        ):
            raise GenerationError(
                "each source record must expose id, owner, and evidence-url"
            )
        ownership.append(
            {"id": record_id, "owner": owner, "evidence-url": evidence_url}
        )
        if record.get("status") == "review":
            review_records.append(record_id)
        if (
            record.get("severity") in {"high", "critical"}
            and record.get("reachable") == "yes"
        ):
            high_critical_reachable.append(record_id)
        expiry = record.get("exception-expiry")
        if isinstance(expiry, str):
            try:
                if dt.date.fromisoformat(expiry) < as_of:
                    expired_exceptions.append(record_id)
            except ValueError as exc:
                raise GenerationError(
                    f"record {record_id} has an invalid exception-expiry"
                ) from exc

    return {
        "ownership": ownership,
        "review-records": review_records,
        "false-positive-records": [],
        "high-critical-reachable": high_critical_reachable,
        "expired-exceptions": expired_exceptions,
        "exception-updates": [],
    }


def _markdown_summary(metadata: dict[str, object]) -> str:
    triage = metadata["triage"]
    records = metadata["records"]
    lines = [
        "# Supply-chain report-only train evidence",
        "",
        f"- Train: `{metadata['train']}`",
        f"- Generated at: `{metadata['generated-at']}`",
        f"- Report path: `{metadata['report-path']}`",
        f"- Report SHA-256: `{metadata['report-sha256']}`",
        f"- Command: `{metadata['command']}`",
        f"- Triage duration: `{triage['duration-ms']} ms`",
        f"- Review records: `{len(triage['review-records'])}`",
        f"- High/critical reachable: `{len(triage['high-critical-reachable'])}`",
        f"- Expired exceptions: `{len(triage['expired-exceptions'])}`",
        f"- Exception updates: `{len(triage['exception-updates'])}`",
        "- Gate: `report-only` (findings do not fail this gate)",
        "",
        "| Record | Owner | Evidence |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{record['id']}` | `{record['owner']}` | {record['evidence-url']} |"
        for record in records
    )
    return "\n".join(lines) + "\n"


def generate(
    *,
    source: Path,
    report_path: Path,
    metadata_path: Path,
    summary_path: Path,
    train: str,
    generated_at: str,
    command: str,
) -> dict[str, object]:
    if TRAIN_RE.fullmatch(train) is None:
        raise GenerationError("train must be YYYY-MM-DD-slug")
    generated_time = _parse_generated_at(generated_at)
    started_at = dt.datetime.now(dt.timezone.utc)
    started_ns = time.perf_counter_ns()

    source_report = _read_report(source)
    report = copy.deepcopy(source_report)
    report["train"] = train
    report["generated-at"] = generated_at
    _write_json(report_path, report)

    report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    triage_result = _triage(report["records"], as_of=generated_time.date())
    completed_at = dt.datetime.now(dt.timezone.utc)
    duration_ns = time.perf_counter_ns() - started_ns
    duration_ms = max(1, (duration_ns + 999_999) // 1_000_000)
    ownership = triage_result.pop("ownership")
    metadata: dict[str, object] = {
        "schema-version": 1,
        "report-only": True,
        "train": train,
        "repository": report.get("repository"),
        "generated-at": generated_at,
        "source-report-sha256": source_sha256,
        "report-path": report_path.name,
        "report-sha256": report_sha256,
        "command": command,
        "records": ownership,
        "triage": {
            "started-at": started_at.isoformat().replace("+00:00", "Z"),
            "completed-at": completed_at.isoformat().replace("+00:00", "Z"),
            "duration-ms": duration_ms,
            **triage_result,
        },
    }
    _write_json(metadata_path, metadata)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(_markdown_summary(metadata), encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY / "supply-chain-report-only.json",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY / "supply-chain-triage.json",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY / "supply-chain-summary.md",
    )
    parser.add_argument("--train", required=True)
    parser.add_argument(
        "--generated-at",
        default=dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args(argv)
    command = shlex.join(
        [
            sys.executable,
            str(Path(__file__).relative_to(REPOSITORY_ROOT)),
            *(argv or sys.argv[1:]),
        ]
    )
    try:
        metadata = generate(
            source=args.source,
            report_path=args.report,
            metadata_path=args.metadata,
            summary_path=args.summary_output,
            train=args.train,
            generated_at=args.generated_at,
            command=command,
        )
    except (OSError, GenerationError) as exc:
        print(f"Supply-chain report generation: FAIL ({exc})", file=sys.stderr)
        return 2
    triage = metadata["triage"]
    print(
        "Supply-chain report-only generated: "
        f"train={metadata['train']}; sha256={metadata['report-sha256']}; "
        f"review={len(triage['review-records'])}; "
        f"blocking-candidates={len(triage['high-critical-reachable'])}; "
        f"expired-exceptions={len(triage['expired-exceptions'])}; "
        "findings do not fail this gate"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
