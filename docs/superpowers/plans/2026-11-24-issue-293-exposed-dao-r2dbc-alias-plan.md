# Issue #293 Exposed R2DBC DAO alias 구현 계획

> **작업 에이전트:** $executing-plans로 단계를 순서대로 실행하고 각 단계의 체크박스를 갱신한다.

**Goal:** 중앙 Gradle version catalog에서 org.jetbrains.exposed:exposed-dao-r2dbc를 기존 exposed = 1.6.1에 연결해 소비자가 libs.exposed.dao.r2dbc로 사용할 수 있게 한다.

**Architecture:** bluetape4k-dependencies의 [libraries]에 외부 artifact alias 하나를 추가한다. 기존 버전 키와 checksum sidecar를 유지하고, Python 회귀 테스트 및 임시 Maven Central 전용 Gradle 소비자로 alias 좌표와 선택 버전을 검증한다. BOM, Maven publication, Exposed 소비 저장소의 catalog ref는 변경하지 않는다.

**Tech Stack:** Gradle version catalog, TOML, Python unittest, Gradle Kotlin DSL, Maven Central.

**Workflow Type:** Type A — catalog authority audit, inventory, immutable evidence, and delta pointers are coupled to the alias and span more than five repository files.

---

## 실행 기준과 경계

- 설계 기준: [Issue #293 설계](../specs/2026-11-24-issue-293-exposed-dao-r2dbc-alias-design.md)
- 대상 이슈: [bluetape4k-dependencies #293](https://github.com/bluetape4k/bluetape4k-dependencies/issues/293)
- 소비자 이슈: [bluetape4k-exposed #942](https://github.com/bluetape4k/bluetape4k-exposed/issues/942)
- 저장소/base/head: bluetape4k/bluetape4k-dependencies, develop, chore/issue-293-exposed-dao-r2dbc-alias
- 구현 기준: 최신 `origin/develop`에 작업 브랜치를 rebase한 뒤 exposed = "1.6.1" 및 alias 누락을 다시 확인한다. 계획 작성 시 원격 develop은 78a2f525c1d12c576f80f2c8f84dbb2fbb942ede였으며, 구현 직전 다시 조회한다.
- PR 권한: 위 저장소와 base/head 조합으로 PR 생성까지 승인됐다. 병합, auto-merge, tag, catalog release 및 Maven Central publication은 범위 밖이며 별도 승인이 필요하다.
- 재분류 기준: catalog alias 하나만 보면 Type B처럼 보이지만, authority audit와 immutable rollout evidence를 함께 갱신해야 해 실제 변경은 Type A다. 기존 사용자 승인은 같은 #293 목표, 저장소, base/head 및 PR 생성 범위에 적용된다. 설계·API 경계는 바꾸지 않는다.
- 순서 복구: Type A 재분류는 catalog/audit 변경 뒤에 이뤄졌다. 이미 작성된 구현은 새 설계 결정이 아니라 승인된 alias 목표를 따르며, 이 문서의 독립 계획 리뷰, 전체 검증, 최종 diff 리뷰를 완료하기 전에는 구현 commit과 PR 생성을 진행하지 않는다.
- 작업 방식: 주 세션이 쓰기·통합·외부 작업을 소유한다. Type A의 설계/계획 및 최종 diff 검토는 여섯 독립 관점 lane과 주 세션 통합으로 진행한다. 작업 worktree는 `/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/chore/issue-293-exposed-dao-r2dbc-alias`다.

## 파일 책임

| 파일 | 책임 |
|---|---|
| gradle/libs.versions.toml | exposed-dao-r2dbc alias를 기존 exposed 버전 키에 연결 |
| gradle/libs.versions.toml.sha256 | catalog 원문 checksum 유지 |
| tests/test_exposed_dao_r2dbc_catalog.py | TOML 구조를 파싱해 artifact 좌표, 기존 version ref 및 1.6.1 기준 회귀 검사 |
| scripts/audit-latest-stable.py | catalog 직접 authority 수 기준을 새 coordinate에 맞춤 |
| tests/test_audit_latest_stable.py | 새 Exposed authority와 inventory 수를 고정하고 immutable v4 기준의 기존 523개 audit record를 정확히 보존하는지 검사 |
| config/latest-stable-version-inventory.json | 새 catalog authority를 포함한 생성 inventory |
| config/latest-stable-version-audit.json | 신규 coordinate metadata를 추가하고 기존 record 보존 |
| config/latest-stable-version-deltas.json | 기존 pending rollout의 105개 delta를 보존하고 최신 audit SHA·summary를 연결 |
| config/central-catalog-version-deltas.json | immutable candidate revision을 가리키도록 기존 pending rollout row 갱신 |
| config/rollouts/catalog-refresh-2026-11-20-v4/candidate-<catalog-sha-prefix>-<audit-sha-prefix>/* | 기존 v4 불변 기준 자료를 보존하며 새 audit가 담긴 개정본 추가 |
| docs/superpowers/reviews/2026-11-25-issue-293-plan-review.md | 6관점 계획 리뷰와 통합 판정 기록 |
| docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md | 검증 결과와 재발 방지 기준을 남기는 작업 lesson |

작업 브랜치에는 이미 승인된 설계와 설계 리뷰가 있다. 구현 시 build.gradle.kts, BOM 제약, Dependabot 규칙, 생성 catalog block, publication POM, bluetape4k-exposed 파일은 변경하지 않는다.

## 구현 전 승인과 실행 방식

- 첫 계획과 설계 승인은 이미 완료됐다. Type A 재분류 후 보완한 계획은 독립 여섯 관점 검토와 주 세션 통합을 거쳐 같은 목표·파일 경계에 대한 기존 승인을 실행한다.
- 주 세션은 승인된 파일만 수정한다. 독립 reviewer는 읽기 전용이며 성능, 안정성, 보안, 운영, 개발자/API, 사용자/소비자 관점을 각각 맡는다. 필요한 리뷰 lane을 실행할 수 없으면 workflow의 bounded fallback을 적용하고 독립 attestation으로 표시하지 않는다.
- Gradle 소비자 프로젝트와 저장소 빌드는 순차 실행한다. Testcontainers/실제 DB 검증은 런타임 경로가 바뀌지 않는 catalog alias 변경이므로 적용하지 않는다.
- 중단 조건: 계획 또는 코드 리뷰에서 P0/P1 발견, 기준 버전 변경, 필수 검증 실패, 승인 범위 밖 diff, 또는 PR base/head 불일치.

## 단계별 실행

### Task 1: 기준 브랜치와 요구사항 재고정

**Action:** 원격 develop을 갱신하고 작업 브랜치를 최신 기준에 rebase한 뒤, 이슈와 설계 결정이 그대로 유효한지 확인한다.

**Expected DoD:** 깨끗한 chore/issue-293-exposed-dao-r2dbc-alias worktree가 최신 origin/develop 위에 있고, exposed = "1.6.1", alias 누락, #293의 상태·milestone·labels·assignee, #942의 2.2.0 milestone과 담당자를 확인했다.

**대상 파일:** gradle/libs.versions.toml, gradle/libs.versions.toml.sha256, 설계·계획 문서 (읽기 전용 확인)

- [x] **Step 1: 원격 기준과 이슈 상태 갱신**

feature worktree에서 실행한다.

~~~
git fetch origin develop
git status --porcelain=v1 -b
git rev-parse origin/develop
gh issue view 293 --repo bluetape4k/bluetape4k-dependencies --json state,title,labels,assignees,milestone,url
gh issue view 942 --repo bluetape4k/bluetape4k-exposed --json state,title,labels,assignees,milestone,url
~~~

예상 결과: 승인된 작업 브랜치가 선택되고 #293과 #942 모두 열림·2.2.0·담당자 debop 상태다. #293 label은 chore/dependencies이고 #942 label은 documentation/enhancement/feature/test다. live 값이 달라지면 현재 metadata를 기록하고, 이슈 범위가 달라졌으면 코드를 수정하기 전에 계획과 설계를 맞춘다.

- [x] **Step 2: 최신 develop에 rebase**

~~~
git rebase origin/develop
git status --porcelain=v1 -b
~~~

예상 결과: 관련 없는 변경 없이 rebase가 끝난다. 충돌이 나면 설계·계획 파일만 upstream 기준으로 해결하고 전체 diff와 이 단계 검사를 다시 확인한다. force-push하거나 commit을 버리지 않는다.

- [x] **Step 3: Exposed catalog contract 재확인**

~~~
rg -n '^exposed\s*=|^exposed-(bom|core|dao|jdbc|r2dbc|dao-r2dbc)\s*=' gradle/libs.versions.toml
~~~

예상 결과: 구현 전 exposed = "1.6.1"이며 관련 alias가 version.ref = "exposed"를 사용하고 exposed-dao-r2dbc는 없다. 동등한 alias가 이미 있거나 버전이 달라졌으면 편집하지 말고 계획·설계 리뷰를 갱신한다.

- [x] **Step 4: 승인된 계획과 리뷰 문서 먼저 커밋**

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

- [x] **Step 5: 손상 receipt와 세션 바인딩 실행 이력 확인**

설계 run `20261124T125346Z-df0e8e85`는 지원 helper로 `blocked` 처리됐으며 sequence 19, checksum `b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792`를 보존한다. 최초 실행 run `20261124T154608Z-8f6dc689`의 손상 receipt는 수정·이어쓰기하지 않고 quarantine에 보존했다. `recovery-run-create`는 새 run `20261124T173527Z-b49f7d37`을 생성했지만 현재 `session_id`를 manifest에 전달하지 않아 `mutation-check`에서 사용할 수 없다. 이 run과 receipt는 그대로 보존한다.

이전 session-bound run `20261124T174718Z-8a4ff39c`는 sequence 8, checksum `8ee4a303c877ca9a6d61ae4416753c2b1e0ae11f4aa79cf97e9ba829468d2f45`에서 main lane의 15분 command deadline을 넘겼다. liveness 검사에서 `suspect_stall`을 반환했고 heartbeat 갱신도 만료된 deadline 때문에 거부됐다. 이전 receipt는 지원 helper로 sequence 9, checksum `698ae07a87111498ada53725687c2f5388f1322886f3dd1919bdf360785bad39`에서 `blocked` 처리해 보존했다.

이어진 session-bound run `20261124T184644Z-5bfe429a`에서는 계획 검토 reviewer 여섯 lane이 `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host: host executable was not found`로 exact-file 검토 전에 실패했다. 주 세션 liveness probe를 확인·응답한 후 sequence 37, checksum `6a2380386c1ea6f13c9deddc49a9e11ba4e4b70757232922f336d5b100293e8b`에서 15분 실행 제한으로 `blocked` 처리했다. 이 receipt는 수정하지 않고 보존한다.

Type A run `20261124T190927Z-031a5d5b`는 사용자의 구현·검증·PR 생성 승인을 연결해 시작했으나 main lane의 15분 command deadline을 넘겼다. 2026-11-24T19:43Z의 `liveness-check`가 `suspect_stall`을 반환해 helper로 sequence 8, checksum `d407aac1462a744182a74701bd00df23a854f5373d063e98baadcd660ae75e48`에서 `blocked` 처리하고 보존했다. 그 run의 lane write scope에는 실제 lesson `docs/lessons/...` 대신 잘못된 `docs/superpowers/lessons/...` 경로가 남아 있었다. 이를 덮어쓰지 않고 새 run `20261124T195142Z-e26f7ea3`를 만들었다. 새 run은 승인 sequence 2, start sequence 3, mutation-check 대상 14개 PASS, lane/topology 등록 및 startup ACK sequence 7, checksum `e6e24d9afa5cfee9850583e144521e010d2cf1fecb6628f2c866a8a8775d628c`까지 진행했다. 새 lane write scope는 `docs/lessons/...`를 사용한다. reviewer host `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host`는 exact diff 전에 다시 실패했으며 독립 attestation은 없다. 실패 receipt를 승인이나 리뷰 통과로 표시하지 않는다.

기록 확인에는 `/Users/debop/work/bluetape4k/bluetape-skills/skills/bluetape-workflow/scripts/bluetape-flow.py`를 사용한다. `.bluetape` receipt는 지원 helper로만 변경하고, 모든 변경은 직전 receipt checksum을 `--expected-head`로 전달한다.

진행 조건: `resume-check`와 `completion-check`의 checksum이 일치하며 receipt chain은 정상이다. 작업 시작 시 completion은 여섯 필수 check와 lane/component/main-verification 증거가 없어 미완료였고, 이는 구현 전 상태로 예상된다. 모든 check와 증거가 통과한 뒤에만 `complete`를 호출한다.

현재 세션 바인딩 실행은 main session 소유의 execution lane 한 개와 issue component 한 개를 사용한다. component의 필수 check는 plan_review, implementation, verification, code_review, lesson, pr_ci이며 inline review 문서는 해당 review check의 evidence다. lane scope에는 승인된 변경과 중앙 감사 기준 자료 복구에 필요한 catalog, audit, inventory, transaction 및 문서 경로가 포함돼야 한다. lane, topology, check 결과 및 receipt는 모두 지원 helper로 기록한다.

- [x] **Step 6: 단일 실행 lane과 component topology 등록**

helper가 요구하는 lane input을 임시 JSON 파일로 만든다. 계약상 필드는 `lane_id`, `agent_id`, `assignment`, `write_scope`, `fallback`, `observed_at`, `startup_ack_deadline`, `command_deadline`이다. lane id는 issue293_main_execution, agent id는 root, fallback은 main session이며 write scope는 승인된 catalog/test/audit/config/review/lesson 경로로 고정한다. 별도의 `lane_role` 필드는 계약에 없으므로 넣지 않는다. observed_at은 현재 UTC, startup_ack_deadline은 현재 UTC+30초, command_deadline은 현재 UTC+15분으로 계산한다. 그다음 다음 component를 topology-register에 전달한다.

~~~
set -euo pipefail
flow=/Users/debop/work/bluetape4k/bluetape-skills/skills/bluetape-workflow/scripts/bluetape-flow.py
new_owner=.bluetape/handles/owner-issue-293-session-bound-20261125-final.owner
receipt="$(python3 "$flow" mutation-check --session-id "$CODEX_THREAD_ID" --allow-state running \
  --target "$PWD/gradle/libs.versions.toml" \
  --target "$PWD/gradle/libs.versions.toml.sha256" \
  --target "$PWD/tests/test_exposed_dao_r2dbc_catalog.py" \
  --target "$PWD/scripts/audit-latest-stable.py" \
  --target "$PWD/tests/test_audit_latest_stable.py" \
  --target "$PWD/config/latest-stable-version-inventory.json" \
  --target "$PWD/config/latest-stable-version-audit.json" \
  --target "$PWD/config/latest-stable-version-deltas.json" \
  --target "$PWD/config/central-catalog-version-deltas.json" \
  --target "$PWD/config/rollouts/catalog-refresh-2026-11-20-v4" \
  --target "$PWD/docs/superpowers/plans/2026-11-24-issue-293-exposed-dao-r2dbc-alias-plan.md" \
  --target "$PWD/docs/superpowers/reviews/2026-11-25-issue-293-plan-review.md" \
  --target "$PWD/docs/superpowers/reviews/2026-11-25-issue-293-code-review.md" \
  --target "$PWD/docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md")"
run_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])' <<< "$receipt")"
state="$(python3 "$flow" resume-check --run-id "$run_id")"
test "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_state"])' <<< "$state")" = running
receipt_head="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["last_checksum"])' <<< "$state")"
temp_dir="$(mktemp -d)"
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
    "write_scope": [
        "gradle/libs.versions.toml",
        "gradle/libs.versions.toml.sha256",
        "tests/test_exposed_dao_r2dbc_catalog.py",
        "scripts/audit-latest-stable.py",
        "tests/test_audit_latest_stable.py",
        "config/latest-stable-version-inventory.json",
        "config/latest-stable-version-audit.json",
        "config/latest-stable-version-deltas.json",
        "config/central-catalog-version-deltas.json",
        "config/rollouts/catalog-refresh-2026-11-20-v4",
        "docs/superpowers/plans/2026-11-24-issue-293-exposed-dao-r2dbc-alias-plan.md",
        "docs/superpowers/reviews/2026-11-25-issue-293-code-review.md",
        "docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md",
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

**Step DoD: PASS** — `origin/develop`은 작업 HEAD의 조상이고, #293/#942는 열린 상태·milestone `2.2.0`·assignee `debop`이며, exposed 1.6.1과 alias 부재를 확인했다. 승인 계획 commit과 현재 session-bound receipt, lane/topology도 live read-back으로 검증했다.

### Task 2: Alias 계약의 failing test 작성

**Action:** catalog alias의 module 좌표와 기존 버전 ref를 고정하는 Python 단위 테스트를 먼저 작성한다.

**Expected DoD:** 테스트가 alias가 없는 기준 catalog에서 실패하고, 잘못된 module 또는 version.ref를 허용하지 않는다.

**대상 파일:** tests/test_exposed_dao_r2dbc_catalog.py

- [x] **Step 1: 회귀 테스트 작성**

다음 내용으로 tests/test_exposed_dao_r2dbc_catalog.py를 생성한다.

~~~python
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
catalog = tomllib.loads(
    (ROOT / "gradle/libs.versions.toml").read_text(encoding="utf-8")
)
libraries = catalog["libraries"]
self.assertEqual(catalog["versions"]["exposed"], "1.6.1")
self.assertIn("exposed-dao-r2dbc", libraries)
self.assertEqual(
    libraries["exposed-dao-r2dbc"],
    {
        "module": "org.jetbrains.exposed:exposed-dao-r2dbc",
        "version": {"ref": "exposed"},
    },
)
~~~

- [x] **Step 2: RED 증거 수집**

실행: python3 -m unittest discover -s tests -p 'test_exposed_dao_r2dbc_catalog.py' -v

예상 결과: exposed-dao-r2dbc alias가 없어 TOML `[libraries]`에 해당 키가 없다는 assertion으로 실패한다. 이 결과로 현재 누락을 테스트가 검출함을 확인한다. 아직 catalog 원본은 수정하지 않는다.

**Step DoD: PASS** — 기준 catalog에서 missing alias RED를 먼저 확인했고, 현재 focused 및 전체 Python suite에서 회귀 테스트가 GREEN이다.

### Task 3: Alias와 checksum 반영

**Action:** [libraries]에 승인된 alias 한 줄을 추가하고 checksum 파일을 다시 만든다.

**Expected DoD:** catalog의 Exposed module alias가 기존 exposed 버전 키를 사용하고 sidecar checksum이 현재 catalog bytes와 일치한다.

**대상 파일:** gradle/libs.versions.toml, gradle/libs.versions.toml.sha256

- [x] **Step 1: TOML alias 한 줄 추가**

기존 Exposed alias 옆의 [libraries] 영역에 다음 한 줄을 추가한다.

~~~toml
exposed-dao-r2dbc = { module = "org.jetbrains.exposed:exposed-dao-r2dbc", version.ref = "exposed" }
~~~

새 version key, exposed 값 변경, BOM 제약 또는 생성 block 변경은 추가하지 않는다.

- [x] **Step 2: checksum 갱신**

~~~
cd gradle
shasum -a 256 libs.versions.toml > libs.versions.toml.sha256
shasum -a 256 -c libs.versions.toml.sha256
cd ..
~~~

예상 결과: libs.versions.toml: OK.

- [x] **Step 3: GREEN 확인**

실행: python3 -m unittest discover -s tests -p 'test_exposed_dao_r2dbc_catalog.py' -v

예상 결과: 테스트 한 건이 OK로 끝난다. 실패하면 TOML 위치·alias 또는 테스트 조건만 수정한 뒤 RED/GREEN 결과를 다시 확인한다.

**Step DoD: PASS** — alias가 기존 `exposed = 1.6.1`을 참조하고 sidecar SHA가 catalog bytes와 일치하며 focused·전체 테스트가 통과했다.

### Task 4: catalog authority audit와 실제 Gradle 소비 계약 검증

**Action:** 새 외부 coordinate가 authoritative latest-stable inventory와 audit에도 포함되는지 확인하고, 주변 동기화 계약, Maven Central 소비자 접근자 및 저장소 빌드를 검증한다.

**Expected DoD:** inventory가 managed 325, policy 67, catalog-direct 132, 전체 524 authority를 포함한다. 새 `org.jetbrains.exposed:exposed-dao-r2dbc` audit record가 `exposed = "1.6.1"`에 연결되고 기존 record와 조회 시각은 보존된다. 활성 pending rollout의 105개 version delta와 원본 불변 기준 자료는 유지하고, 새 audit를 담는 별도 불변 개정본을 추가해 central ledger가 그 개정본을 가리킨다. 임시 소비자의 `compileClasspath`는 `org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1`을 선택하며 적용 가능한 검증이 모두 통과한다.

**대상 파일:** `scripts/audit-latest-stable.py`, `tests/test_audit_latest_stable.py`, `config/latest-stable-version-inventory.json`, `config/latest-stable-version-audit.json`, `config/latest-stable-version-deltas.json`, `config/central-catalog-version-deltas.json`, 그리고 helper가 계산하는 `config/rollouts/catalog-refresh-2026-11-20-v4/candidate-<catalog-sha-prefix>-<audit-sha-prefix>/` 불변 개정본. 임시 consumer는 시스템 임시 디렉터리에만 만들고 결과를 읽을 수 있게 둔다. 새 coordinate의 Maven metadata만 조회한다. 전체 `--refresh-audit`는 실행하지 않고, 기존 v4 기준 자료 파일과 105개 version delta를 수정하지 않는다.

- [x] **Step 1: authority 증가 회귀를 먼저 고정한다**

`tests/test_audit_latest_stable.py`에서 authority 수를 `524`, catalog-direct 수를 `132`로 바꾸고 새 `exposed-dao-r2dbc` authority key, alias, version key와 현재 버전을 확인한다. 이 테스트가 아직 `build_inventory()`의 기존 authority count guard에서 실패하는지 확인한다.

기준 실행에서 전체 suite는 새 alias 하나로 catalog authority가 `131`에서 `132`로 늘어 `test_audit_latest_stable.py` 14개 테스트에 실패했다. 실패 원인은 `scripts/audit-latest-stable.py`와 테스트의 고정 count가 `523` authority를 기대하는 것이다.

- [x] **Step 2: inventory와 audit를 새 authority에 맞춘다**

`scripts/audit-latest-stable.py`의 catalog-direct 및 전체 authority 기준을 각각 `132`, `524`로 갱신하고 `--write --summary`로 inventory를 생성한다. `audit_record()`를 사용해 새 Exposed coordinate의 authoritative Maven metadata만 조회하고, 나머지 audit record·metadata 조회 시각은 보존한다. 최신 audit SHA와 summary를 활성 `config/latest-stable-version-deltas.json`에 반영하되, 이 ledger의 기존 rollout, candidate, baseline, 105개 delta는 보존한다. 현재 cross-file guard는 audit hash·summary까지 불변 기준 자료와 비교하므로 top-level pointer만 바꾸면 안 된다. `candidate_rollout_snapshot_revision()`과 `snapshot_rollout_evidence()`로 같은 pending rollout의 새 revision을 추가하고, `pin_catalog_rollout_evidence()`가 만든 central row pointer를 기록한다. 이전 revision은 그대로 보존한다. journal이 남아 있으면 새 revision과 central pointer를 먼저 준비한 뒤 공식 recovery helper로 검증·적용한다.

실행 뒤 `python3.13 scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary`와 `python3.13 -m unittest tests.test_audit_latest_stable tests.test_latest_stable_version_deltas tests.test_central_catalog_version_deltas`를 실행한다. 전체 metadata 재조회나 기존 불변 기준 자료 변경은 하지 않는다. 새 revision과 central row pointer가 기존 pending rollout의 delta 수·catalog SHA·audit SHA와 일치하는지 cross-file 검증한다.

복구 결과: audit inventory `524` authority, `519` metadata verified, `5` preview-only다. 기존 v4 기준 자료와 105개 pending delta는 보존했다. 새 불변 개정본 `candidate-48f7ab2fb9463cfb-4337efdf5c56e545`를 추가하고 central pointer를 갱신했으며, active audit SHA `4337efdf5c56e545549388767ba95fd152f13a31f12027a13ffe6e3d9bfc8439`, active delta SHA `cc7ed2688da1936025bab41b7841a4834f14417c24b86e27d98a29eec22b2ad8`로 transaction journal recovery와 read-back을 통과했다.

- [x] **Step 3: checksum과 전체 Python 회귀 검증**

~~~
(cd gradle && shasum -a 256 -c libs.versions.toml.sha256)
python3.13 -m unittest discover -s tests -p 'test_*.py'
~~~

예상 결과: checksum이 OK이며 Python suite가 종료 코드 0으로 끝난다. 실패하면 원인을 찾아 고친 뒤 다음 검사로 진행한다.

- [x] **Step 4: 생성 catalog 및 Dependabot 계약 검사**

~~~
python3 scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary
python3 scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary
~~~

예상 결과: 파일을 변경하지 않고 두 검사가 통과한다. 기존 org.jetbrains.exposed:* ignore 규칙을 유지하고 managed catalog 출력은 바뀌지 않는다. 관련 없는 sibling 상태로 실패하면 경로를 확인하고 task-owned 상태일 때만 고친다.

- [x] **Step 5: 임시 Gradle 소비자로 accessor와 선택 버전 검증**

저장소 루트에서 다음 명령을 실행한다. 의존성 저장소는 Maven Central 하나만 사용하며 명령이 만든 임시 project만 제거한다.

~~~bash
consumer_dir="$(mktemp -d)"
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

예상 결과: Gradle이 libs.exposed.dao.r2dbc 접근자를 생성하고 org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1을 선택한다. 임시 consumer 디렉터리는 명령이 만든 상태로 남겨 진단에 사용한다. 실패하면 정확한 오류를 확인하고 동일한 Maven Central 전용 project에서 재검증하기 전까지 통과 처리하지 않는다.

- [x] **Step 6: 저장소 전체 build 검증**

실행: ./gradlew build --console=plain

예상 결과: BUILD SUCCESSFUL. alias만 추가하므로 application/runtime dependency가 달라지지 않는다. Testcontainers, 실제 DB, coroutine lifecycle/cancellation, concurrency 및 benchmark 검사는 적용되지 않으며, catalog·Python assertion·checksum만 바뀐 diff를 근거로 기록한다.

- [x] **Step 7: 기존 audit record와 timestamp 불변성 회귀 검사**

`tests/test_audit_latest_stable.py`에서 현재 audit의 authority-key 집합이 immutable v4 baseline에 있던 523개 record를 모두 보존하고, 신규 `catalog:library:org.jetbrains.exposed:exposed-dao-r2dbc` 하나만 추가하는지 비교한다. 각 기존 record 전체를 비교해 개별 `retrieved-at` timestamp와 metadata도 같음을 확인한다.

실행: `python3.13 -m unittest tests.test_audit_latest_stable tests.test_exposed_dao_r2dbc_catalog`

예상 결과: 새 catalog alias는 `[libraries]` TOML 구조에서 정확한 module/version.ref로 파싱되고, 과거 523개 record는 immutable baseline과 완전히 일치한다. 임시 in-memory timestamp 변경 probe는 새 회귀 검사에서 RED여야 한다.

**Step DoD: PASS** — 새 authority record와 기존 523개 audit record 및 개별 조회 시각, pending delta 105개 및 원본 불변 기준 자료를 보존했다. inventory, audit, central pointer, checksum, managed catalog, Dependabot, Gradle consumer 및 repository build가 통과했다. Python suite는 627건 통과, 2건 skip이며 외부 `bluetape4k-core:1.9.2-SNAPSHOT` 확인은 HTTP 403으로 건너뛰었다. 재검증에서 불변 record 및 TOML parser 회귀 테스트도 GREEN이며 timestamp mutation probe는 RED로 거부됐다.

### Task 5: diff 리뷰, lesson 및 commit

**Action:** 최신 exact-head diff를 승인된 설계와 비교하고 6개 코드 리뷰 관점을 통합한 뒤, 작업 교훈을 작성하고 변경을 커밋한다.

**Expected DoD:** P0=0/P1=0, P2/P3가 수정·후속 조치·근거 있는 N/A로 정리되고, 코드·문서와 작업 교훈이 한국어 Lore 형식 commit으로 보존된다.

**대상 파일:** `gradle/libs.versions.toml`, sidecar checksum, 두 Python 회귀 테스트, `scripts/audit-latest-stable.py`, 최신 inventory/audit/delta 및 central pointer JSON, 새 immutable v4 candidate revision, 이 계획·코드 리뷰 artifact, `docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md`.

- [x] **Step 1: 요구사항 대비 diff 확인**

~~~
git add -N tests/test_exposed_dao_r2dbc_catalog.py \
  config/rollouts/catalog-refresh-2026-11-20-v4/candidate-48f7ab2fb9463cfb-4337efdf5c56e545/latest-stable-version-audit.json \
  config/rollouts/catalog-refresh-2026-11-20-v4/candidate-48f7ab2fb9463cfb-4337efdf5c56e545/latest-stable-version-deltas.json \
  docs/superpowers/reviews/2026-11-25-issue-293-code-review.md \
  docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md
git diff --check
git diff origin/develop --stat
git diff -- gradle/libs.versions.toml gradle/libs.versions.toml.sha256 tests/test_exposed_dao_r2dbc_catalog.py
git status --porcelain=v1
~~~

예상 결과: 새 test/review/lesson 파일도 intent-to-add로 diff 검사에 포함된다. catalog authority audit·inventory·delta ledger의 변경은 새 authority와 immutable rollout evidence를 보존하는 데 한정된다. BOM과 published dependency graph는 바뀌지 않는다.

- [x] **Step 2: 6관점 코드 리뷰와 통합**

먼저 현재 exact diff를 성능, 안정성, 보안, 운영, 개발자/API, 사용자/소비자 관점의 독립 검토자에게 요청한다. native reviewer 실행이 불가능하면 bounded liveness recovery 뒤 주 세션 inline fallback으로 전환하고 실패 receipt를 보존한다. TOML catalog 의미, Gradle 접근자/좌표, 테스트 정밀도, checksum 무결성, 호환성, generated/POM 경계, 검증 범위, 문서와 작업 교훈의 정확성을 확인한다. 독립 review와 inline fallback의 provenance를 구분한다.

예상 결과: review artifact가 exact head, P0/P1/P2/P3 finding, 파일/줄 근거, 처리, 검증 및 판정을 기록한다. P0=0, P1=0이어야 한다.

- [x] **Step 3: Lesson 기록**

docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md를 만들고 배경, 결정, 결과, 새 검증, 검토/runtime 한계 및 향후 guard를 한국어로 기록한다. catalog alias/version-ref/checksum 검사, 기존 523개 audit record 불변성, transaction recovery와 #942가 병합 후 고정된 catalog commit SHA를 사용해야 하는 조건을 남긴다. commit 전에 SPW-01부터 SPW-05까지 적용하고 작업 교훈을 다시 읽는다.

- [ ] **Step 4: 구현과 lesson commit**

exact diff와 tests를 통과하고, 독립 reviewer 실행이 불가능하면 workflow의 bounded recovery 뒤 inline fallback review에서 P0/P1=0을 확인한 다음 catalog, audit evidence, tests, checksum, review 및 lesson을 Korean Lore trailer와 함께 commit한다. 실패한 reviewer 실행을 보존하고 독립 attestation이 없음을 명시한다. upstream이나 승인된 이전 commit을 amend하지 않는다.

**Step DoD: PENDING** — inline fallback review와 lesson은 기록했으며, 이번 exact-diff 재검토 뒤 계획·코드 리뷰·lesson의 gate 문구를 일치시키고 commit한다. 독립 reviewer attestation은 없다.

### Task 6: 승인된 PR 생성과 exact-head 검증

**Action:** 사전 승인된 저장소/base/head로 변경을 push하고 한국어 PR을 만든 다음, GitHub의 최신 metadata와 exact-head CI를 확인한다.

**Expected DoD:** PR이 #293 및 #942와 연결되고 base=develop, head=chore/issue-293-exposed-dao-r2dbc-alias, milestone=2.2.0, assignee=debop, labels=chore/dependencies를 사용한다. 마지막 보고는 병합 준비 증거와 미완료 병합 gate를 구분하며 실제로 병합하지 않는다.

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

`chore/issue-293-exposed-dao-r2dbc-alias`를 origin에 push하고 develop 대상 PR 하나를 만든다. 설치된 `bluetape-workflow/templates/pr-body-step-dod.md`를 적용한다. 본문에서 `Closes #293` 및 `Refs bluetape4k/bluetape4k-exposed#942`를 연결하고 `## DoD Status`를 마지막 `##` section으로 둔다. PR milestone은 `2.2.0`, assignee는 `debop`, labels는 `chore`/`dependencies`로 지정한다. auto-merge는 켜지 않는다.

- [ ] **Step 3: live read-back 및 exact-head CI**

PR 번호, URL, base, head SHA, milestone, assignee, labels, 최종 본문, reviews, threads, mergeability 및 해당 head의 모든 필수 check를 다시 확인한다. CI 완료를 기다리고, 실패는 승인된 작업 브랜치에서 수정한 뒤 관련 검사를 재실행하고 상태를 다시 확인한다. single-developer lane에 해당하는 human-review 하위 gate만 N/A로 기록한다. CI, exact-head check, workflow가 허용한 독립 또는 inline fallback 코드 리뷰 및 thread 확인은 계속 필요하다. Inline fallback은 독립 attestation으로 표시하지 않는다.

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
| audit, delta ledger, central pointer 갱신 중 프로세스 중단 또는 이후 복구 필요 | transaction journal, active SHA와 central pointer 교차 검사 | journal과 기존 개정본을 삭제하지 않는다. `python3.13 scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary`는 검사 전에 `recover_catalog_rollout_transaction()`을 실행한다. `python3.13 -m unittest tests.test_central_catalog_version_deltas tests.test_latest_stable_version_deltas`로 crash-recovery와 cross-file 검사를 다시 실행한다. 기존 개정본을 수정하지 않고 새 개정본과 pointer를 지원 helper로 만든다. |
| 변경이 BOM/POM 또는 downstream build를 바꿈 | exact diff, sync-managed-catalog, repository build | 계획 경계 위반으로 구현을 중지하고 영향/승인 범위를 다시 검토한다. |

커밋 전 로컬 변경은 승인된 원본을 기준으로 다시 생성하고 모든 cross-file 검사를 통과시켜야 한다. 커밋 후에는 immutable 개정본을 삭제하거나 덮어쓰지 않는다. 수정이 필요하면 새 catalog 개정본과 central pointer를 지원 helper로 추가하고 audit·delta 검사를 다시 실행한다. 외부 게시, schema migration, runtime data rollback은 이 변경에 포함되지 않는다.

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
- Maven BOM과 publisher build 파일은 변경하지 않는다. workspace publisher build 파일에서 `exposed-dao-r2dbc` 및 `libs.exposed.dao.r2dbc` 참조가 없고, alias는 `api(...)` 제약 또는 BOM import와 연결되지 않아 published POM 입력 그래프에 들어가지 않는다. 따라서 publication POM gate는 N/A이며 구체 근거는 workspace-wide publisher build 파일 검색 결과와 catalog/Gradle consumer diff다. Maven Central resolve는 임시 consumer로 alias 사용 계약을 확인한다.
- Kotlin/JVM source, coroutine, transaction, lifecycle, API/ABI, Testcontainers 및 concurrency 동작은 바뀌지 않는다. Python 회귀 테스트와 catalog resolve를 실행한다.
- PR 본문·리뷰·커밋·lesson의 일반 문장은 한국어로 작성한다. API, coordinate, commands, identifiers, URLs는 그대로 보존한다.
- CI와 리뷰가 끝나도 별도 새 승인 전까지 merge하지 않는다.

## 별도 PR #297 본문 read-back

- 현재 PR `https://github.com/bluetape4k/bluetape4k-dependencies/pull/297`의 head `2d67f92ed9406eb4c49399519f6651adac7dd05b`, base `develop`, milestone `2.2.0`, assignee `debop`을 live read-back했다.
- exact-head status check 10개가 모두 성공했고 reviews 0건, review threads 0건, mergeability `MERGEABLE`/`CLEAN`을 확인했다.
- 본문에서 사용자 요청과 어긋난 “독립 리뷰 생략” 문구를 제거했다. main-session P0/P1 결과와 independent review PENDING을 분리하고, CI/read-back 통과와 남은 independent review gate를 DoD 표에 기록했다.
- PR #297 본문은 갱신됐지만 merge나 auto-merge는 실행하지 않았다.

## Writer DoD

- [x] **SPW-01 — 근거와 독자 고정:** 이슈 #293/#942, milestone `2.2.0`, 승인 설계, 현재 base/head, catalog audit baseline, 작업 경계와 독자를 확인했다.
- [x] **SPW-02 — 계획 계약 충족:** catalog, audit/inventory/delta ledger, immutable revision, 검증, 리뷰, lesson 및 PR 파일 범위와 의존 순서를 대조했다.
- [x] **SPW-03 — 한국어 기술 문체:** 한국어 자연스러움 checklist와 contextual terminology audit를 적용했다.
- [x] **SPW-04 — 기술 의미와 추적성:** 승인 spec, 현재 code diff, 이전 immutable audit, publication POM N/A 근거 및 acceptance 기준을 대조했다.
- [x] **SPW-05 — 최종 read-back:** Markdown 구조, code fence, 경로와 명령을 다시 읽고 inline Type A plan-review 결과를 기록했다.

## Type A Gate Map

| Gate | State | Evidence / next action |
|---|---|---|
| A-01 — 요구사항과 worktree | PASS | Issue #293/#942, milestone, isolated branch, base/head, PR 범위와 merge hold를 live read-back했다. |
| A-02 — 현재 근거와 설계 | PASS | GNO `bluetape4k-github` issue records, `bluetape4k-docs` catalog precedent, catalog source와 immutable v4 audit를 확인했다. |
| A-03 — 설계 승인/리뷰 | PASS | 승인된 spec의 경계를 유지하고 Type A로 여섯 관점 inline re-review와 main integration을 기록했다. independent reviewer host 오류는 별도 code-review gate로 추적한다. |
| A-04 — 계획 승인/리뷰 | PASS | 보완 계획의 여섯 관점 inline review, writer DoD, 실행 이력과 PR metadata 순서를 확인했다. 독립 reviewer attestation으로 표시하지 않는다. |
| A-05 — 위험 예측 | PASS | audit journal, immutable pointer recovery, POM boundary 및 rerun 조건은 위험 표에 기록했다. |
| A-06 — test-first 구현 | PASS | alias 누락 RED 이력, 523-record timestamp mutation RED probe, 새 TOML/audit regression tests GREEN을 기록했다. |
| A-07 — 검증과 scope | PASS | Python 627 pass/2 skip, catalog/audit/Dependabot checks, checksum, Gradle consumer/build와 publication POM N/A 근거를 read-back했다. SNAPSHOT artifact 확인 1건은 HTTP 403으로 건너뛴 한계다. |
| A-08 — 최종 코드 리뷰 | PASS | 최신 exact source/docs diff를 주 세션 inline fallback으로 다시 검토했다. P0/P1=0이며 reviewer host 실패와 독립 attestation 부재를 별도로 기록한다. |
| A-09 — lesson commit | PASS | `docs/lessons/2026-11-25-issue-293-exposed-dao-r2dbc-alias.md`를 작성·검토했고 승인된 변경 commit에 포함한다. |
| A-10 — PR/CI | PENDING | 승인된 repository/base/head로 PR을 만들고 exact-head CI, reviews, threads, metadata를 확인한다. |
| A-11 — merge-ready DoD | PENDING | PR exact head 기준으로 knowledge/documentation과 최종 DoD를 보고한다. |
| A-12 — merge closeout | PENDING | 현재 범위에서는 실행하지 않는다. CG-16 새 승인과 실제 merge 이후 sync/cleanup/index를 수행한다. |

Plan review: PASS — Type A spec 및 보완 계획의 여섯 관점 inline review와 통합 결과를 별도 addendum에 기록한다. 독립 reviewer attestation은 host 오류로 제공되지 않았다.
