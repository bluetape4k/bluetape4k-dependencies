#!/usr/bin/env python3
"""Validate the normalized report-only supply-chain evidence contract."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = REPOSITORY_ROOT / "config" / "supply-chain-report-only.json"
DEFAULT_SCHEMA = REPOSITORY_ROOT / "config" / "supply-chain-report.schema.json"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TRAIN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]+$")
EXCEPTION_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]+$")
ECOSYSTEMS = frozenset(
    {"kotlin-gradle", "go", "python", "rust", "publication", "sbom-provenance"}
)
ECOSYSTEM_ORDER = (
    "kotlin-gradle",
    "go",
    "python",
    "rust",
    "publication",
    "sbom-provenance",
)
ECOSYSTEM_INDEX = {name: index for index, name in enumerate(ECOSYSTEM_ORDER)}
STATUSES = frozenset({"pass", "review", "not-applicable", "blocked"})
SEVERITIES = frozenset({"none", "low", "moderate", "high", "critical"})
REACHABILITY = frozenset({"yes", "no", "unknown", "not-applicable"})
TOP_LEVEL_FIELDS = frozenset(
    {"schema-version", "report-only", "train", "repository", "generated-at", "records"}
)
RECORD_FIELDS = frozenset(
    {
        "id",
        "ecosystem",
        "status",
        "severity",
        "affected",
        "reachable",
        "exception-id",
        "exception-expiry",
        "evidence-url",
        "owner",
        "source",
        "summary",
    }
)
SOURCE_FIELDS = frozenset({"tool", "command", "path"})


class ReportError(ValueError):
    """Raised when the report envelope is malformed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReportError(message)


def _non_empty_string(value: object, field: str) -> str:
    _require(
        isinstance(value, str) and bool(value.strip()),
        f"{field} must be a non-empty string",
    )
    return value


def _date(value: object, field: str) -> dt.date:
    _require(
        isinstance(value, str) and DATE_RE.fullmatch(value) is not None,
        f"{field} must be YYYY-MM-DD",
    )
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ReportError(f"{field} is not a calendar date: {value}") from exc


def _date_time(value: object, field: str) -> dt.datetime:
    _require(isinstance(value, str), f"{field} must be an ISO-8601 date-time")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportError(f"{field} is not an ISO-8601 date-time: {value}") from exc
    _require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed


def _https_url(value: object, field: str) -> str:
    url = _non_empty_string(value, field)
    parsed = urlparse(url)
    _require(
        parsed.scheme == "https" and bool(parsed.netloc),
        f"{field} must be an HTTPS URL",
    )
    return url


def _load_json(path: Path, label: str) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot load {label}: {path}") from exc
    _require(isinstance(document, dict), f"{label} must be a JSON object")
    return document


def validate_schema_document(schema: dict[str, object]) -> None:
    """Keep the checked-in schema honest without adding a JSON-schema dependency."""

    _require(
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "schema draft must be 2020-12",
    )
    _require(schema.get("type") == "object", "schema root type must be object")
    _require(
        schema.get("additionalProperties") is False,
        "schema must reject unknown root fields",
    )
    required = schema.get("required")
    _require(
        required
        == [
            "schema-version",
            "report-only",
            "train",
            "repository",
            "generated-at",
            "records",
        ],
        "schema root required fields drifted",
    )
    definitions = schema.get("$defs")
    _require(
        isinstance(definitions, dict) and "record" in definitions,
        "schema record definition is missing",
    )
    record = definitions["record"]
    _require(
        isinstance(record, dict) and record.get("additionalProperties") is False,
        "schema record must reject unknown fields",
    )
    _require(
        record.get("required")
        == [
            "id",
            "ecosystem",
            "status",
            "severity",
            "affected",
            "reachable",
            "exception-id",
            "exception-expiry",
            "evidence-url",
            "owner",
            "source",
            "summary",
        ],
        "schema record required fields drifted",
    )


def validate_report(report: dict[str, object], *, as_of: dt.date) -> dict[str, object]:
    _require(set(report) == TOP_LEVEL_FIELDS, "report envelope fields are not exact")
    _require(report.get("schema-version") == 1, "report schema-version must be 1")
    _require(report.get("report-only") is True, "report-only must remain true")
    train = _non_empty_string(report.get("train"), "train")
    _require(TRAIN_RE.fullmatch(train) is not None, "train must be YYYY-MM-DD-slug")
    _non_empty_string(report.get("repository"), "repository")
    generated_at = _date_time(report.get("generated-at"), "generated-at")
    records = report.get("records")
    _require(isinstance(records, list) and records, "records must be a non-empty array")

    record_keys: list[tuple[int, str]] = []
    statuses: Counter[str] = Counter()
    blocking_candidates: list[str] = []
    expired_exceptions: list[str] = []
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        _require(isinstance(record, dict), f"{prefix} must be an object")
        _require(set(record) == RECORD_FIELDS, f"{prefix} fields are not exact")
        record_id = _non_empty_string(record.get("id"), f"{prefix}.id")
        _require(
            ID_RE.fullmatch(record_id) is not None,
            f"{prefix}.id is not a stable slug",
        )
        ecosystem = record.get("ecosystem")
        _require(ecosystem in ECOSYSTEMS, f"{prefix}.ecosystem is not supported")
        record_keys.append((ECOSYSTEM_INDEX[ecosystem], record_id))
        status = record.get("status")
        _require(status in STATUSES, f"{prefix}.status is not supported")
        statuses[status] += 1
        severity = record.get("severity")
        _require(severity in SEVERITIES, f"{prefix}.severity is not supported")
        affected = record.get("affected")
        _require(
            isinstance(affected, dict)
            and set(affected) == {"artifact", "module"},
            f"{prefix}.affected must contain artifact and module",
        )
        _non_empty_string(affected.get("artifact"), f"{prefix}.affected.artifact")
        _non_empty_string(affected.get("module"), f"{prefix}.affected.module")
        reachable = record.get("reachable")
        _require(reachable in REACHABILITY, f"{prefix}.reachable is not supported")
        exception_id = record.get("exception-id")
        if exception_id is not None:
            _require(
                isinstance(exception_id, str)
                and EXCEPTION_RE.fullmatch(exception_id) is not None,
                f"{prefix}.exception-id is invalid",
            )
        exception_expiry = record.get("exception-expiry")
        if exception_expiry is not None:
            expiry = _date(exception_expiry, f"{prefix}.exception-expiry")
            _require(exception_id is not None, f"{prefix}.exception-expiry requires exception-id")
            if expiry < as_of:
                expired_exceptions.append(record_id)
        else:
            _require(exception_id is None, f"{prefix}.exception-id requires exception-expiry")
        _https_url(record.get("evidence-url"), f"{prefix}.evidence-url")
        _non_empty_string(record.get("owner"), f"{prefix}.owner")
        source = record.get("source")
        _require(
            isinstance(source, dict) and set(source) == SOURCE_FIELDS,
            f"{prefix}.source fields are not exact",
        )
        for field in SOURCE_FIELDS:
            _non_empty_string(source.get(field), f"{prefix}.source.{field}")
        _non_empty_string(record.get("summary"), f"{prefix}.summary")
        if severity in {"high", "critical"} and reachable == "yes":
            blocking_candidates.append(record_id)

    record_ids = [record_id for _, record_id in record_keys]
    _require(len(record_ids) == len(set(record_ids)), "record ids must be unique")
    _require(
        record_keys == sorted(record_keys),
        "records must be sorted by ecosystem and id for deterministic diffs",
    )
    generated_date_utc = generated_at.astimezone(dt.timezone.utc).date()
    _require(
        generated_date_utc <= as_of,
        "generated-at cannot be after the report as-of date",
    )
    return {
        "records": len(records),
        "statuses": dict(sorted(statuses.items())),
        "blocking-candidates": blocking_candidates,
        "expired-exceptions": expired_exceptions,
        "as-of": as_of.isoformat(),
    }


def run(report_path: Path, schema_path: Path, *, as_of: dt.date) -> dict[str, object]:
    schema = _load_json(schema_path, "schema")
    validate_schema_document(schema)
    report = _load_json(report_path, "report")
    return validate_report(report, as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--as-of", default=dt.datetime.now(dt.timezone.utc).date().isoformat()
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    try:
        as_of = _date(args.as_of, "--as-of")
        summary = run(args.report, args.schema, as_of=as_of)
    except (OSError, ReportError) as exc:
        print(f"Supply-chain report contract: FAIL ({exc})", file=sys.stderr)
        return 2
    if args.summary:
        statuses = ", ".join(f"{key}={value}" for key, value in summary["statuses"].items())
        print(
            "Supply-chain report-only: "
            f"records={summary['records']}; {statuses}; "
            f"blocking-candidates={len(summary['blocking-candidates'])}; "
            f"expired-exceptions={len(summary['expired-exceptions'])}; "
            "findings do not fail this gate"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
