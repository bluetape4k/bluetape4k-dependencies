#!/usr/bin/env bash
# CI가 검증한 consumer commit만 Snapshot 검증과 publication에 사용한다.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=${1:?Usage: checkout-snapshot-consumers.sh WORKSPACE MANIFEST [POLICY]}
manifest=${2:?Usage: checkout-snapshot-consumers.sh WORKSPACE MANIFEST [POLICY]}
policy=${3:-"$script_dir/../config/post-publish-next-development-line.json"}
python=${PYTHON:-python3}

validation=$("$python" "$script_dir/write-snapshot-consumer-inputs.py" validate \
  --policy "$policy" \
  --manifest "$manifest")
test "$validation" = "Snapshot consumer input manifest is valid."
refs=$("$python" "$script_dir/write-snapshot-consumer-inputs.py" print-checkouts \
  --policy "$policy" \
  --manifest "$manifest")

while IFS=$'\t' read -r repo expected_sha; do
    if [[ -e "$workspace/$repo" || -L "$workspace/$repo" ]]; then
        echo "snapshot consumer destination already exists: $repo" >&2
        exit 1
    fi
done <<< "$refs"
mkdir -p -- "$workspace"

while IFS=$'\t' read -r repo expected_sha; do
    gh repo clone "bluetape4k/$repo" "$workspace/$repo" -- --filter=blob:none --no-checkout
    git -C "$workspace/$repo" fetch --no-tags --filter=blob:none origin "$expected_sha"
    git -C "$workspace/$repo" checkout --detach "$expected_sha"
    test "$(git -C "$workspace/$repo" rev-parse --verify "${expected_sha}^{commit}")" = "$expected_sha"
    test "$(git -C "$workspace/$repo" rev-parse HEAD)" = "$expected_sha"
    test -z "$(git -C "$workspace/$repo" status --porcelain=v1 --untracked-files=all)"
    echo "snapshot-consumer=$repo head=$expected_sha"
done <<< "$refs"
