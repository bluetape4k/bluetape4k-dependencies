#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "Usage: retry-snapshot-resolution.sh <command> [args...]" >&2
  exit 64
fi

max_attempts="${SNAPSHOT_RESOLUTION_ATTEMPTS:-5}"
delay_seconds="${SNAPSHOT_RESOLUTION_DELAY_SECONDS:-30}"

is_snapshot_resolution_failure() {
  local log_file="$1"
  grep -Eiq "Received status code 403|GET 403|HEAD 403" "$log_file" &&
    grep -Eiq \
      "central\.sonatype\.com/repository/maven-snapshots|maven-metadata\.xml|Unable to load Maven meta-data|Could not resolve .*SNAPSHOT" \
      "$log_file"
}

for attempt in $(seq 1 "$max_attempts"); do
  log_file="$(mktemp)"

  set +e
  "$@" 2>&1 | tee "$log_file"
  status="${PIPESTATUS[0]}"
  set -e

  if [ "$status" -eq 0 ]; then
    rm -f "$log_file"
    exit 0
  fi

  if [ "$attempt" -lt "$max_attempts" ] && is_snapshot_resolution_failure "$log_file"; then
    echo "SNAPSHOT dependency resolution failed; retrying attempt $((attempt + 1))/${max_attempts} after ${delay_seconds}s"
    rm -f "$log_file"
    sleep "$delay_seconds"
    continue
  fi

  rm -f "$log_file"
  exit "$status"
done
