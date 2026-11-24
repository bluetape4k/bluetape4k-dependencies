# Issue #293 Exposed R2DBC DAO alias 구현 계획

> **작업 에이전트:** $executing-plans로 단계를 순서대로 실행하고 각 단계의 체크박스를 갱신한다.

**Goal:** 중앙 Gradle version catalog에서 org.jetbrains.exposed:exposed-dao-r2dbc를 기존 exposed = 1.6.1에 연결해 소비자가 libs.exposed.dao.r2dbc로 사용할 수 있게 한다.

**Architecture:** bluetape4k-dependencies의 [libraries]에 외부 artifact alias 하나를 추가한다. 기존 버전 키와 checksum sidecar를 유지하고, Python 회귀 테스트 및 임시 Maven Central 전용 Gradle 소비자로 alias 좌표와 선택 버전을 검증한다. BOM, Maven publication, Exposed 소비 저장소의 catalog ref는 변경하지 않는다.

**Tech Stack:** Gradle version catalog, TOML, Python unittest, Gradle Kotlin DSL, Maven Central.

---

## 실행 기준과 경계

- 설계 기준: [Issue #293 설계](../specs/2026-11-24-issue-293-exposed-dao-r2dbc-alias-design.md)
- 대상 이슈: [bluetape4k-dependencies #293](https://github.com/bluetape4k/bluetape4k-dependencies/issues/293)
- 소비자 이슈: [bluetape4k-exposed #942](https://github.com/bluetape4k/bluetape4k-exposed/issues/942)
- 저장소/base/head: bluetape4k/bluetape4k-dependencies, develop, chore/issue-293-exposed-dao-r2dbc-alias
- 구현 기준: 최신 `origin/develop`에 작업 브랜치를 rebase한 뒤 exposed = "1.6.1" 및 alias 누락을 다시 확인한다. 계획 작성 시 원격 develop은 78a2f525c1d12c576f80f2c8f84dbb2fbb942ede였으며, 구현 직전 다시 조회한다.
- PR 권한: 위 저장소와 base/head 조합으로 PR 생성까지 승인됐다. 병합, auto-merge, tag, catalog release 및 Maven Central publication은 범위 밖이며 별도 승인이 필요하다.
- 작업 방식: 단일 소유자가 $executing-plans로 순차 실행한다. 작업 worktree는 `/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/chore/issue-293-exposed-dao-r2dbc-alias`다.

## 파일 책임

| 파일 | 책임 |
|---|---|
| gradle/libs.versions.toml | exposed-dao-r2dbc alias를 기존 exposed 버전 키에 연결 |
| gradle/libs.versions.toml.sha256 | catalog 원문 checksum 유지 |
| tests/test_exposed_dao_r2dbc_catalog.py | artifact 좌표, 기존 version ref 및 1.6.1 기준 회귀 검사 |
| docs/superpowers/reviews/2026-11-25-issue-293-plan-review.md | 6관점 계획 리뷰와 통합 판정 기록 |
| docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md | 검증 결과와 재발 방지 기준을 남기는 작업 lesson |

작업 브랜치에는 이미 승인된 설계와 설계 리뷰가 있다. 구현 시 build.gradle.kts, BOM 제약, Dependabot 규칙, 생성 catalog block, publication POM, bluetape4k-exposed 파일은 변경하지 않는다.

## 구현 전 승인과 실행 방식

- 이 계획은 6개 관점 검토와 주 세션 통합, writer DoD를 마친 뒤 사용자의 명시적 승인을 받아야 한다. 승인 전에는 rebase, receipt 상태 변경, 테스트 또는 catalog 편집을 하지 않는다.
- 실행은 주 세션 하나가 맡는다. native reviewer 실행 호스트가 현재 작업에서 시작되지 않았으므로 계획 리뷰는 6개 관점을 각각 기록하는 `inline fallback review`이며 독립 검토 attestation으로 표시하지 않는다.
- 위임 lane 수는 0개다. 쓰기 범위는 표에 적은 계획/리뷰, catalog, Python 테스트, checksum, lesson 파일이다. 성능/안정성/보안/운영/개발자/API/사용자 관점은 독립 lane을 사용할 수 없을 때만 주 세션의 inline review로 기록한다.
- Gradle 소비자 프로젝트와 저장소 빌드는 순차 실행한다. Testcontainers/실제 DB 검증은 런타임 경로가 바뀌지 않는 catalog alias 변경이므로 적용하지 않는다.
- 중단 조건: 계획 또는 코드 리뷰에서 P0/P1 발견, 기준 버전 변경, 필수 검증 실패, 승인 범위 밖 diff, 또는 PR base/head 불일치.

## 단계별 실행

### Task 1: 기준 브랜치와 요구사항 재고정

**Action:** 원격 develop을 갱신하고 작업 브랜치를 최신 기준에 rebase한 뒤, 이슈와 설계 결정이 그대로 유효한지 확인한다.

**Expected DoD:** 깨끗한 chore/issue-293-exposed-dao-r2dbc-alias worktree가 최신 origin/develop 위에 있고, exposed = "1.6.1", alias 누락, #293의 상태·milestone·labels·assignee, #942의 2.2.0 milestone과 담당자를 확인했다.

**대상 파일:** gradle/libs.versions.toml, gradle/libs.versions.toml.sha256, 설계·계획 문서 (읽기 전용 확인)

- [ ] **Step 1: 원격 기준과 이슈 상태 갱신**

feature worktree에서 실행한다.

~~~
git fetch origin develop
git status --porcelain=v1 -b
git rev-parse origin/develop
gh issue view 293 --repo bluetape4k/bluetape4k-dependencies --json state,title,labels,assignees,milestone,url
gh issue view 942 --repo bluetape4k/bluetape4k-exposed --json state,title,labels,assignees,milestone,url
~~~

예상 결과: 승인된 작업 브랜치가 선택되고 #293과 #942 모두 열림·2.2.0·담당자 debop 상태다. #293 label은 chore/dependencies이고 #942 label은 documentation/enhancement/feature/test다. live 값이 달라지면 현재 metadata를 기록하고, 이슈 범위가 달라졌으면 코드를 수정하기 전에 계획과 설계를 맞춘다.

- [ ] **Step 2: 최신 develop에 rebase**

~~~
git rebase origin/develop
git status --porcelain=v1 -b
~~~

예상 결과: 관련 없는 변경 없이 rebase가 끝난다. 충돌이 나면 설계·계획 파일만 upstream 기준으로 해결하고 전체 diff와 이 단계 검사를 다시 확인한다. force-push하거나 commit을 버리지 않는다.

- [ ] **Step 3: Exposed catalog contract 재확인**

~~~
rg -n '^exposed\s*=|^exposed-(bom|core|dao|jdbc|r2dbc|dao-r2dbc)\s*=' gradle/libs.versions.toml
~~~

예상 결과: 구현 전 exposed = "1.6.1"이며 관련 alias가 version.ref = "exposed"를 사용하고 exposed-dao-r2dbc는 없다. 동등한 alias가 이미 있거나 버전이 달라졌으면 편집하지 말고 계획·설계 리뷰를 갱신한다.

- [ ] **Step 4: 승인된 계획과 리뷰 문서 먼저 커밋**

설계와 설계 리뷰는 기존 branch commit에 이미 있다. 계획 승인 뒤 새 계획과 계획 리뷰만 먼저 commit한다. 이 commit은 implementation 이전의 계획 승인 증거를 보존한다.

~~~
git add docs/superpowers/plans/2026-11-24-issue-293-exposed-dao-r2dbc-alias-plan.md \
  docs/superpowers/reviews/2026-11-25-issue-293-plan-review.md
git commit -m "중앙 catalog alias 구현 기준을 승인된 계획으로 고정한다" \
  -m "Constraint: Exposed 1.6.1 기존 version ref를 재사용한다." \
  -m "Rejected: 별도 Exposed 버전 키 추가 | 기존 artifact 버전선과 분리할 근거가 없다." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Directive: 구현 전에 최신 develop과 승인 계획을 다시 확인한다." \
  -m "Tested: 계획 리뷰 P0=0/P1=0 및 writer DoD." \
  -m "Not-tested: 구현과 catalog 검증은 아직 실행하지 않았다."
~~~

예상 결과: 승인된 계획 문서가 한국어 Lore 형식 commit으로 기록된다. 이 시점까지 catalog와 테스트 파일은 수정하지 않는다.

- [ ] **Step 5: 미완료 설계 run을 보존하고 구현 run 시작**

기존 설계 run `20261124T125346Z-df0e8e85`는 `spec_performance_rereview`가 `agent_interrupted` 없이 실패해 inline resolution 조건을 충족하지 않으므로 지원 helper로 BLOCKED 처리했다. 현재 상태는 sequence 19, checksum `b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792`다. 이 receipt는 성공으로 바꾸지 않는다. 승인된 실행 계획용 Type A run `20261124T154608Z-8f6dc689`는 init 당시 `planned`, sequence 1, checksum `fb670e1905a937422348fdd9962d310d88b8f65129db6bea939d36d8a1fa8711`이었다. `run-approve`와 `run-start`를 거쳐 현재 `running`, sequence 3, checksum `fcb699c250ee6fde4d0b9d5c311f414f23ae932947d7c5313823fac5eac84ba3`다. 이후에는 기존 owner file과 run을 재사용한다. `.bluetape` 상태는 지원 helper로만 변경한다.

`--expected-head`는 Git commit SHA가 아니라 직전 receipt의 64자리 소문자 SHA-256 checksum이다. 모든 helper mutation 결과의 `checksum`을 다음 mutation에 전달한다. Git HEAD는 승인 계획 commit을 요약하는 별도 증거로만 기록한다.

~~~
set -euo pipefail
flow=/Users/debop/.codex/skills/bluetape-workflow/scripts/bluetape-flow.py
new_owner=.bluetape/handles/owner-issue-293-implementation.owner
run_id=20261124T154608Z-8f6dc689
plan_head="$(git rev-parse HEAD)"
old_state="$(python3 "$flow" resume-check --run-id 20261124T125346Z-df0e8e85)"
old_diagnosis="$(python3 "$flow" receipt-diagnose --run-id 20261124T125346Z-df0e8e85)"
python3 "$flow" completion-check --run-id 20261124T125346Z-df0e8e85
test "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_state"])' <<< "$old_state")" = blocked
test "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["last_checksum"])' <<< "$old_state")" = b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792
test "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["last_trusted_checksum"])' <<< "$old_diagnosis")" = b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792
test -f "$new_owner"
planned="$(python3 "$flow" resume-check --run-id "$run_id")"
test "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_state"])' <<< "$planned")" = planned
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["last_checksum"])' <<< "$planned")"
approve_output="$(python3 "$flow" run-approve --run-id "$run_id" --owner-file "$new_owner" \
  --expected-head "$receipt_head" --evidence-kind user-approval \
  --evidence-summary "사용자가 승인한 계획의 목표와 범위를 유지해 실행 명령의 receipt CAS 기준을 보정했다; 계획 commit $plan_head; 보존한 설계 run 20261124T125346Z-df0e8e85는 blocked, checksum b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792")"
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["checksum"])' <<< "$approve_output")"
start_output="$(python3 "$flow" run-start --run-id "$run_id" --owner-file "$new_owner" \
  --expected-head "$receipt_head" --evidence-kind approved-plan \
  --evidence-summary "승인한 Issue #293 계획 commit ${plan_head}을 기준으로 구현 run을 시작한다.")"
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["checksum"])' <<< "$start_output")"
python3 "$flow" mutation-check --session-id "$CODEX_THREAD_ID" \
  --target "$PWD/gradle/libs.versions.toml" \
  --target "$PWD/gradle/libs.versions.toml.sha256" \
  --target "$PWD/tests/test_exposed_dao_r2dbc_catalog.py" \
  --target "$PWD/docs/superpowers/reviews/2026-11-25-issue-293-code-review.md" \
  --target "$PWD/docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md"
~~~

진행 조건: 이전 run은 `blocked`, sequence 19, checksum `b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792`로 유지되고 새 run은 `running`이어야 한다. 새 run의 `resume-check`와 `completion-check` receipt checksum이 일치하고 chain 진단이 정상이어야 한다. topology 등록 전에는 component가 미완료로 남는 것이 정상이다. 상태나 checksum이 다르면 helper mutation을 중단하고 조사한다.

새 run은 main session 소유의 execution lane 한 개와 issue component 한 개를 사용한다. component의 필수 check는 plan_review, implementation, verification, code_review, lesson, pr_ci이며 inline review 문서는 해당 review check의 evidence다. lane scope는 승인된 파일 목록과 일치해야 한다. lane, topology, check 결과 및 receipt는 모두 지원 helper로 기록한다.

- [ ] **Step 6: 단일 실행 lane과 component topology 등록**

helper가 요구하는 lane input을 임시 JSON 파일로 만든다. lane id는 issue293_main_execution, agent id는 root, lane role은 execution, fallback은 main session, write scope는 계획에 적은 catalog/test/review/lesson 경로로 고정한다. observed_at은 현재 UTC, startup_ack_deadline은 현재 UTC+30초, command_deadline은 현재 UTC+15분으로 계산한다. 그다음 다음 component를 topology-register에 전달한다.

~~~
set -euo pipefail
flow=/Users/debop/.codex/skills/bluetape-workflow/scripts/bluetape-flow.py
new_owner=.bluetape/handles/owner-issue-293-implementation.owner
receipt="$(python3 "$flow" mutation-check --session-id "$CODEX_THREAD_ID" \
  --target "$PWD/gradle/libs.versions.toml" \
  --target "$PWD/gradle/libs.versions.toml.sha256" \
  --target "$PWD/tests/test_exposed_dao_r2dbc_catalog.py" \
  --target "$PWD/docs/superpowers/reviews/2026-11-25-issue-293-code-review.md" \
  --target "$PWD/docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md")"
run_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])' <<< "$receipt")"
state="$(python3 "$flow" resume-check --run-id "$run_id")"
test "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_state"])' <<< "$state")" = running
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["last_checksum"])' <<< "$state")"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
python3 - "$temp_dir/lane.json" "$temp_dir/topology.json" <<'PY'
from datetime import datetime, timedelta, timezone
import json
import sys

lane_path, topology_path = sys.argv[1:3]
now = datetime.now(timezone.utc)
stamp = lambda delta: (now + delta).isoformat(timespec="seconds").replace("+00:00", "Z")
lane = {
    "lane_id": "issue293_main_execution",
    "agent_id": "root",
    "assignment": "Main session executes the approved Issue #293 plan and owns scoped edits, checks, reviews, lesson, and PR read-back.",
    "lane_role": "execution",
    "write_scope": [
        "gradle/libs.versions.toml",
        "gradle/libs.versions.toml.sha256",
        "tests/test_exposed_dao_r2dbc_catalog.py",
        "docs/superpowers/reviews/2026-11-25-issue-293-code-review.md",
        "docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md",
    ],
    "fallback": "main session",
    "observed_at": stamp(timedelta()),
    "startup_ack_deadline": stamp(timedelta(seconds=30)),
    "command_deadline": stamp(timedelta(minutes=15)),
}
topology = [{
    "id": "issue-293-exposed-dao-r2dbc-alias",
    "required": True,
    "description": "Issue #293의 승인 범위를 구현하고 검증해 PR 증거를 남긴다.",
    "owner_lane": "issue293_main_execution",
    "required_checks": [
        "plan_review", "implementation", "verification",
        "code_review", "lesson", "pr_ci",
    ],
    "dependencies": [],
    "evidence_refs": [],
    "coverage_state": "missing",
}]
for path, value in ((lane_path, lane), (topology_path, topology)):
    with open(path, "w", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False)
PY
printf '%s\n' '[{"kind":"execution-scope","summary":"main session owns only the approved Issue #293 file scope"}]' > "$temp_dir/lane-evidence.json"
printf '%s\n' '[{"kind":"approved-execution-topology","summary":"one main execution lane owns the single Issue #293 component and six ordered checks"}]' > "$temp_dir/topology-evidence.json"
printf '%s\n' '[{"kind":"main-session-active","summary":"root is the current leader session assigned to the execution lane"}]' > "$temp_dir/start-evidence.json"
~~~

topology-register 뒤 lane-start와 startup-ack를 main session agent id root 및 현재 UTC timestamp로 순서대로 기록한다. 각 check는 관련 단계가 통과한 뒤 check-result로 기록한다. 모든 check가 통과한 뒤 component-evidence, lane-complete, completion-check 순으로 검증하고 마지막에 complete를 실행한다. check/lane 증거가 부족하면 complete를 호출하지 않는다.

~~~
lane_output="$(python3 "$flow" lane-create --run-id "$run_id" --owner-file "$new_owner" \
  --expected-head "$receipt_head" --input "$temp_dir/lane.json" \
  --evidence "$temp_dir/lane-evidence.json")"
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["checksum"])' <<< "$lane_output")"
topology_output="$(python3 "$flow" topology-register --run-id "$run_id" --owner-file "$new_owner" \
  --expected-head "$receipt_head" --input "$temp_dir/topology.json" \
  --evidence "$temp_dir/topology-evidence.json")"
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["checksum"])' <<< "$topology_output")"
lane_start_output="$(python3 "$flow" lane-start --run-id "$run_id" --owner-file "$new_owner" \
  --expected-head "$receipt_head" --evidence "$temp_dir/lane-evidence.json" \
  --lane-id issue293_main_execution --agent-id root --at "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["checksum"])' <<< "$lane_start_output")"
ack_output="$(python3 "$flow" startup-ack --run-id "$run_id" --owner-file "$new_owner" \
  --expected-head "$receipt_head" --evidence "$temp_dir/start-evidence.json" \
  --lane-id issue293_main_execution --agent-id root --at "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["checksum"])' <<< "$ack_output")"
~~~

각 Task가 통과하면 check-result 입력에 component id, 해당 check id, passed=true 및 근거를 기록한다. inline plan/code review artifact는 각각 plan_review/code_review check의 근거다. 모든 check가 통과한 뒤 changed-paths 목록과 함께 lane-complete를 기록하고 component-evidence, completion-check 순으로 확인한다. completion-check에서 누락이 없을 때만 complete를 실행한다. lane, topology, check 결과 및 receipt는 모두 지원 helper로 기록한다.

**Step DoD: PENDING** — 최신 기준, 사용자 계획 승인, 계획 commit 및 새 receipt 검증이 필요하다.

### Task 2: Alias 계약의 failing test 작성

**Action:** catalog alias의 module 좌표와 기존 버전 ref를 고정하는 Python 단위 테스트를 먼저 작성한다.

**Expected DoD:** 테스트가 alias가 없는 기준 catalog에서 실패하고, 잘못된 module 또는 version.ref를 허용하지 않는다.

**대상 파일:** tests/test_exposed_dao_r2dbc_catalog.py

- [ ] **Step 1: 회귀 테스트 작성**

다음 내용으로 tests/test_exposed_dao_r2dbc_catalog.py를 생성한다.

~~~python
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExposedDaoR2dbcCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog_text = (ROOT / "gradle/libs.versions.toml").read_text(encoding="utf-8")

    def test_exposed_dao_r2dbc_uses_existing_exposed_161_line(self) -> None:
        version_match = re.search(r'(?m)^exposed\s*=\s*"([^"]+)"', self.catalog_text)
        self.assertIsNotNone(version_match, "missing exposed version key")
        assert version_match is not None
        self.assertEqual(version_match.group(1), "1.6.1")

        alias_match = re.search(r"(?m)^exposed-dao-r2dbc\s*=\s*(\{[^\n]+\})$", self.catalog_text)
        self.assertIsNotNone(alias_match, "missing exposed-dao-r2dbc alias")
        assert alias_match is not None
        entry = alias_match.group(1)
        self.assertIn('module = "org.jetbrains.exposed:exposed-dao-r2dbc"', entry)
        self.assertIn('version.ref = "exposed"', entry)


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: RED 증거 수집**

실행: python3 -m unittest discover -s tests -p 'test_exposed_dao_r2dbc_catalog.py' -v

예상 결과: exposed-dao-r2dbc alias가 없어 테스트가 missing exposed-dao-r2dbc alias 오류로 실패한다. 이 결과로 현재 누락을 테스트가 검출함을 확인한다. 아직 catalog 원본은 수정하지 않는다.

**Step DoD: PENDING** — RED 결과를 읽기 전까지 alias를 추가하지 않는다.

### Task 3: Alias와 checksum 반영

**Action:** [libraries]에 승인된 alias 한 줄을 추가하고 checksum 파일을 다시 만든다.

**Expected DoD:** catalog의 Exposed module alias가 기존 exposed 버전 키를 사용하고 sidecar checksum이 현재 catalog bytes와 일치한다.

**대상 파일:** gradle/libs.versions.toml, gradle/libs.versions.toml.sha256

- [ ] **Step 1: TOML alias 한 줄 추가**

기존 Exposed alias 옆의 [libraries] 영역에 다음 한 줄을 추가한다.

~~~toml
exposed-dao-r2dbc = { module = "org.jetbrains.exposed:exposed-dao-r2dbc", version.ref = "exposed" }
~~~

새 version key, exposed 값 변경, BOM 제약 또는 생성 block 변경은 추가하지 않는다.

- [ ] **Step 2: checksum 갱신**

~~~
cd gradle
shasum -a 256 libs.versions.toml > libs.versions.toml.sha256
shasum -a 256 -c libs.versions.toml.sha256
cd ..
~~~

예상 결과: libs.versions.toml: OK.

- [ ] **Step 3: GREEN 확인**

실행: python3 -m unittest discover -s tests -p 'test_exposed_dao_r2dbc_catalog.py' -v

예상 결과: 테스트 한 건이 OK로 끝난다. 실패하면 TOML 위치·alias 또는 테스트 조건만 수정한 뒤 RED/GREEN 결과를 다시 확인한다.

**Step DoD: PENDING** — Task 2의 RED 결과와 Task 3의 checksum/test 결과가 필요하다.

### Task 4: 중앙 catalog와 실제 Gradle 소비 계약 검증

**Action:** catalog 회귀, 주변 동기화 계약, Maven Central 소비자 접근자 및 저장소 빌드를 확인한다.

**Expected DoD:** 적용 가능한 명령이 통과하고 임시 소비자의 `compileClasspath`가 org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1을 선택한다.

**대상 파일:** 없음. 임시 consumer는 시스템 임시 디렉터리에만 만든 뒤 종료 시 제거한다.

- [ ] **Step 1: checksum과 전체 Python 회귀 검증**

~~~
(cd gradle && shasum -a 256 -c libs.versions.toml.sha256)
python3 -m unittest discover -s tests -p 'test_*.py'
~~~

예상 결과: checksum이 OK이며 Python suite가 종료 코드 0으로 끝난다. 실패하면 원인을 찾아 고친 뒤 다음 검사로 진행한다.

- [ ] **Step 2: 생성 catalog 및 Dependabot 계약 검사**

~~~
python3 scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary
python3 scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary
~~~

예상 결과: 파일을 변경하지 않고 두 검사가 통과한다. 기존 org.jetbrains.exposed:* ignore 규칙을 유지하고 managed catalog 출력은 바뀌지 않는다. 관련 없는 sibling 상태로 실패하면 경로를 확인하고 task-owned 상태일 때만 고친다.

- [ ] **Step 3: 임시 Gradle 소비자로 accessor와 선택 버전 검증**

저장소 루트에서 다음 명령을 실행한다. 의존성 저장소는 Maven Central 하나만 사용하며 명령이 만든 임시 project만 제거한다.

~~~bash
consumer_dir="$(mktemp -d)"
trap 'rm -rf "$consumer_dir"' EXIT
catalog_file="$(pwd)/gradle/libs.versions.toml"
cat > "$consumer_dir/settings.gradle.kts" <<EOF
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { mavenCentral() }
    versionCatalogs {
        create("libs") { from(files("$catalog_file")) }
    }
}
rootProject.name = "exposed-r2dbc-dao-catalog-consumer"
EOF
cat > "$consumer_dir/build.gradle.kts" <<'EOF'
plugins { java }

dependencies {
    implementation(libs.exposed.dao.r2dbc)
}
EOF
./gradlew -p "$consumer_dir" dependencyInsight \
  --dependency org.jetbrains.exposed:exposed-dao-r2dbc \
  --configuration compileClasspath --console=plain
~~~

예상 결과: Gradle이 libs.exposed.dao.r2dbc 접근자를 생성하고 org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1을 선택한다. 실패하면 정확한 오류를 확인하고 동일한 Maven Central 전용 project에서 재검증하기 전까지 통과 처리하지 않는다.

- [ ] **Step 4: 저장소 전체 build 검증**

실행: ./gradlew build --console=plain

예상 결과: BUILD SUCCESSFUL. alias만 추가하므로 application/runtime dependency가 달라지지 않는다. Testcontainers, 실제 DB, coroutine lifecycle/cancellation, concurrency 및 benchmark 검사는 적용되지 않으며, catalog·Python assertion·checksum만 바뀐 diff를 근거로 기록한다.

**Step DoD: PENDING** — 모든 명령을 새로 실행하고 출력을 확인해야 한다.

### Task 5: diff 리뷰, lesson 및 commit

**Action:** 최신 exact-head diff를 승인된 설계와 비교하고 6개 코드 리뷰 관점을 통합한 뒤, 작업 교훈을 작성하고 변경을 커밋한다.

**Expected DoD:** P0=0/P1=0, P2/P3가 수정·후속 조치·근거 있는 N/A로 정리되고, 코드·문서와 작업 교훈이 한국어 Lore 형식 commit으로 보존된다.

**대상 파일:** gradle/libs.versions.toml, gradle/libs.versions.toml.sha256, tests/test_exposed_dao_r2dbc_catalog.py, docs/superpowers/reviews/2026-11-25-issue-293-code-review.md, docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md

- [ ] **Step 1: 요구사항 대비 diff 확인**

~~~
git add -N tests/test_exposed_dao_r2dbc_catalog.py \
  docs/superpowers/reviews/2026-11-25-issue-293-code-review.md \
  docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md
git diff --check
git diff -- gradle/libs.versions.toml gradle/libs.versions.toml.sha256 tests/test_exposed_dao_r2dbc_catalog.py
git status --porcelain=v1
~~~

예상 결과: 새 test/review/lesson 파일도 intent-to-add로 diff 검사에 포함된다. 구현 source diff에는 library alias 하나, focused test 하나, checksum만 있다. version, BOM, publication, generated catalog 또는 consumer repository는 바뀌지 않는다.

- [ ] **Step 2: 6관점 코드 리뷰와 통합**

먼저 현재 exact diff를 성능, 안정성, 보안, 운영, 개발자/API, 사용자/소비자 관점의 독립 검토자에게 요청한다. native reviewer 실행이 불가능하면 주 세션이 여섯 관점을 각각 검토하는 inline fallback으로 전환하고 실패 receipt를 보존한다. TOML catalog 의미, Gradle 접근자/좌표, 테스트 정밀도, checksum 무결성, 호환성, generated/POM 경계, 검증 범위, 문서와 작업 교훈의 정확성을 확인한다. inline review를 독립 검토로 표시하지 않는다.

예상 결과: review artifact가 exact head, P0/P1/P2/P3 finding, 파일/줄 근거, 처리, 검증 및 판정을 기록한다. P0=0, P1=0이어야 한다.

- [ ] **Step 3: Lesson 기록**

docs/superpowers/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md를 만들고 배경, 결정, 결과, 새 검증, 검토/runtime 한계 및 향후 guard를 한국어로 기록한다. catalog alias/version-ref/checksum 검사와 #942가 병합 후 고정된 catalog commit SHA를 사용해야 한다는 조건을 남긴다. commit 전에 SPW-01부터 SPW-05까지 적용하고 작업 교훈을 다시 읽는다.

- [ ] **Step 4: 구현과 lesson commit**

exact diff, tests, code-review gate를 통과한 뒤 catalog, test, checksum, code review 및 lesson을 Korean Lore trailer와 함께 commit한다. upstream이나 승인된 이전 commit을 amend하지 않는다.

**Step DoD: PENDING** — 검토한 exact-head diff와 lesson writer gate가 필요하다.

### Task 6: 승인된 PR 생성과 exact-head 검증

**Action:** 사전 승인된 저장소/base/head로 변경을 push하고 한국어 PR을 만든 다음, GitHub의 최신 metadata와 exact-head CI를 확인한다.

**Expected DoD:** PR이 #293 및 #942와 연결되고 base=develop, head=chore/issue-293-exposed-dao-r2dbc-alias를 사용한다. 마지막 보고는 병합 준비 증거와 미완료 병합 gate를 구분하며 실제로 병합하지 않는다.

**대상:** GitHub PR metadata만 변경한다. 외부에 공개하는 문장은 한국어로 작성한다.

- [ ] **Step 1: PR 생성 직전 승인 범위와 diff 갱신**

~~~
git status --porcelain=v1 -b
git rev-parse HEAD
git diff origin/develop...HEAD --stat
gh issue view 293 --repo bluetape4k/bluetape4k-dependencies --json state,title,labels,assignees,milestone,url
gh issue view 942 --repo bluetape4k/bluetape4k-exposed --json state,title,labels,assignees,milestone,url
gh pr list --repo bluetape4k/bluetape4k-dependencies --state open --head chore/issue-293-exposed-dao-r2dbc-alias --json number,title,url,headRefName,baseRefName
~~~

예상 결과: 작업 브랜치가 clean하고 리뷰가 끝났으며 같은 head를 사용하는 기존 PR이 없다. #293의 상태·milestone·labels·assignee와 #942의 상태·milestone·labels·assignee가 Task 1에서 확인한 값과 맞아야 한다. PR이 이미 있으면 승인된 대상에서만 내용을 갱신하고 중복으로 만들지 않는다.

- [ ] **Step 2: 한국어 PR 생성**

`chore/issue-293-exposed-dao-r2dbc-alias`를 origin에 push하고 develop 대상 PR 하나를 만든다. 설치된 `bluetape-workflow/templates/pr-body-step-dod.md`를 적용한다. 본문에서 `Closes #293` 및 `Refs bluetape4k/bluetape4k-exposed#942`를 연결하고 `## DoD Status`를 마지막 `##` section으로 둔다. auto-merge는 켜지 않는다.

- [ ] **Step 3: live read-back 및 exact-head CI**

PR 번호, URL, base, head SHA, 최종 본문, reviews, threads, mergeability 및 해당 head의 모든 필수 check를 다시 확인한다. CI 완료를 기다리고, 실패는 승인된 작업 브랜치에서 수정한 뒤 관련 검사를 재실행하고 상태를 다시 확인한다. single-developer lane에 해당하는 human-review 하위 gate만 N/A로 기록한다. CI, exact-head check, 독립/inline 코드 리뷰 및 thread 확인은 계속 필요하다.

- [ ] **Step 4: merge 전 정지**

공통 PR gate와 사용자에게 보여 줄 DoD 근거를 모두 모은 뒤에만 병합 준비 상태를 보고한다. merge row는 PENDING으로 두고 병합, auto-merge/admin 우회, tag, publication은 하지 않는다. 작업 교훈은 병합 후 절차가 허용되기 전까지 GNO에 색인하지 않는다.

**Step DoD: PENDING** — 승인 범위에는 PR 생성까지 포함되며 merge는 별도 gate다.

## 위험과 복구

| 위험 | 탐지 | 복구 |
|---|---|---|
| 최신 develop에서 버전 또는 alias 기준이 변경됨 | Task 1의 이슈/catalog 재확인 | 코드 변경을 보류하고 spec 및 계획을 재검토한다. 승인 결정이 달라지면 다시 승인받는다. |
| rebase 충돌이 승인된 설계 문서를 바꿈 | rebase 후 전체 diff와 spec/plan 비교 | 필요한 문서만 병합하고 리뷰/추적성 검사를 다시 실행한다. 기존 commit을 버리거나 force-push하지 않는다. |
| 테스트가 alias의 오타나 별도 버전선을 놓침 | RED/GREEN Python 검사와 Maven Central 전용 소비자 프로젝트 | test assertion 또는 TOML을 좁게 수정하고 관련 검증을 반복한다. |
| checksum 또는 중앙 생성/ignore 검사 실패 | sidecar 검사 및 두 동기화 helper의 check 모드 | 실패 원인을 작업 파일과 분리해 진단하고, 작업 범위에 속한 mismatch만 수정한다. |
| 임시 소비자 프로젝트가 외부 저장소를 포함하거나 선택 버전을 확인하지 못함 | settings의 repository 목록과 dependencyInsight 출력 | 소비자 프로젝트를 Maven Central 하나로 제한하고 정확한 좌표가 보일 때까지 PR 진행을 막는다. |
| 변경이 BOM/POM 또는 downstream build를 바꿈 | exact diff, sync-managed-catalog, repository build | 계획 경계 위반으로 구현을 중지하고 영향/승인 범위를 다시 검토한다. |

alias와 checksum만 제거하면 catalog 변경을 되돌릴 수 있다. Python test와 작업 교훈은 별도 파일이므로 실패 원인과 추적 필요성을 검토해 제거 또는 보존을 결정한다. 외부 게시, schema migration, runtime data rollback은 이 변경에 포함되지 않는다.

## 명세 추적표

| 승인 설계 수용 기준 | 계획 작업 | 완료 증거 |
|---|---|---|
| alias가 정확한 module을 가리킴 | Task 2–3 | Python 회귀 테스트와 Gradle consumer |
| 기존 exposed ref 및 1.6.1 재사용 | Task 1–3 | catalog 재확인 및 테스트 assertion |
| checksum sidecar가 catalog bytes와 일치 | Task 3–4 | shasum -a 256 -c |
| Maven Central 전용 consumer가 alias를 1.6.1로 해석 | Task 4 | temporary consumer dependencyInsight |
| Dependabot 중앙 ignore와 managed catalog 생성 경로가 유지됨 | Task 4 | 두 helper의 --check --summary 결과와 diff |
| Python 회귀 suite와 Gradle build 통과 | Task 4 | 명령 종료 코드 및 출력 |
| 구현 소스 diff가 catalog·test로 제한됨 | Task 5 | exact diff read-back |
| Korean PR과 issue 연결 및 exact-head 확인 | Task 6 | live PR metadata, body, checks, reviews, threads |
| merge/publication/tag 제외 | Task 6 | stop condition과 merge row PENDING |

## PR/문서/검증 영향

- Consumer README/KDoc/CHANGELOG 문서는 추가하지 않는다. 공용 dependency alias만 노출하며 사용 예제와 실험 API 문서는 #942의 Exposed 저장소에서 다룬다.
- Maven BOM은 변경하지 않으므로 POM 생성·검증은 적용되지 않는다. Maven Central resolve는 임시 consumer로 alias 사용 계약을 확인한다.
- Kotlin/JVM source, coroutine, transaction, lifecycle, API/ABI, Testcontainers 및 concurrency 동작은 바뀌지 않는다. Python 회귀 테스트와 catalog resolve를 실행한다.
- PR 본문·리뷰·커밋·lesson의 일반 문장은 한국어로 작성한다. API, coordinate, commands, identifiers, URLs는 그대로 보존한다.
- CI와 리뷰가 끝나도 별도 새 승인 전까지 merge하지 않는다.

## Writer DoD

- [x] **SPW-01 — 근거와 독자 고정:** 이슈 #293/#942, 승인 설계, 현재 remote/catalog 기준, 작업 경계, artifact paths를 기록했다.
- [x] **SPW-02 — 계획 계약 충족:** 정확한 파일·코드·명령·기대 결과·의존 순서·복구·PR gate 및 추적표를 포함했다.
- [x] **SPW-03 — 한국어 기술 문체:** 한국어 자연스러움 checklist와 contextual terminology audit를 적용했고 두 문서 모두 finding 0건이다.
- [x] **SPW-04 — 기술 의미와 추적성:** 계획을 승인 spec, 현재 base, helper contracts와 비교하고 모든 acceptance 기준의 task mapping을 확인했다.
- [x] **SPW-05 — 최종 read-back:** Markdown 구조, code fence, 경로와 명령을 다시 읽고 계획 리뷰 결과를 기록했다.

Plan review: PASS — 여섯 관점 inline fallback review와 main-session 통합에서 P0=0, P1=0; 해결하지 않은 P2/P3가 없다. 계획 실행은 사용자 승인을 기다린다.
