#!/usr/bin/env bash
# 카탈로그 생성과 POM 검증은 서명 이력과 분리한 동일한 불변 ref를 사용한다.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=${1:?Usage: checkout-catalog-publishers.sh WORKSPACE [MANIFEST]}
manifest=${2:-"$script_dir/../config/catalog-publisher-repository-refs.json"}

# 전체 입력 검증 실패가 process substitution에 가려지지 않도록 먼저 완료한다.
refs=$("${PYTHON:-python3}" - "$script_dir" "$manifest" <<'PY'
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from catalog_candidate import PUBLISHER_REPOSITORIES

document = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
if document.get("schema-version") != 1:
    raise SystemExit("unsupported catalog publisher ref schema")
repositories = document.get("repositories", {})
if set(repositories) != set(PUBLISHER_REPOSITORIES):
    raise SystemExit("catalog publisher ref inventory mismatch")
for name, value in sorted(repositories.items()):
    sha = value.get("commit") if isinstance(value, dict) else None
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit(f"catalog publisher requires an exact commit: {name}")
for name, value in sorted(repositories.items()):
    print(f"{name}\t{value['commit']}")
PY
)

# 기존 checkout은 clean 여부와 무관하게 보존한다. 재시도에는 새 디렉터리를 사용한다.
while IFS=$'\t' read -r repo expected_sha; do
    if [[ -e "$workspace/$repo" || -L "$workspace/$repo" ]]; then
        echo "catalog publisher destination already exists: $repo" >&2
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
    echo "catalog-publisher=$repo head=$expected_sha"
done <<< "$refs"
