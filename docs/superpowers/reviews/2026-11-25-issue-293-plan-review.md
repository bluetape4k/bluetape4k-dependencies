# Issue #293 구현 계획 6개 관점 검토

## 판정

- 결과: **PASS — inline fallback review**
- P0: 0건
- P1: 0건
- 수정 완료한 P2: 8건
- 미해결 P2/P3: 0건
- 독립 검토: 수행되지 않음. 아래 inline 검토를 독립 reviewer attestation으로 간주하지 않는다.

## 검토 범위와 근거

- 계획: `docs/superpowers/plans/2026-11-24-issue-293-exposed-dao-r2dbc-alias-plan.md`
- 검토한 계획 SHA-256: `a06e937633756e111a4b29c6cc123d2a4ce401e0ab1cf5ebc03daae1374dd8e4`
- 설계 기준: `docs/superpowers/specs/2026-11-24-issue-293-exposed-dao-r2dbc-alias-design.md`
- 검토한 저장소 HEAD: `3d757eece632e8932e6664ccbb76bf7a069c341b`
- 최신 `origin/develop`: `78a2f525c1d12c576f80f2c8f84dbb2fbb942ede`; 해당 기준으로 rebase한 브랜치는 검토 시점에 ahead 4 / behind 0이었다.
- 2026-11-25 원격 read-back: `git ls-remote`에서 같은 develop SHA를 확인했고, 해당 catalog에서 `exposed = "1.6.1"` 및 `exposed-dao-r2dbc` alias 누락을 확인했다.
- 2026-11-25 workflow read-back: 이전 설계 run은 차단 전에 `running`, sequence 18, checksum `79c3b0dcdb35c275ac6093fe5d44a14357fdff1bee60681f9139da6d783fd0ee`였고, 지원 helper로 BLOCKED 처리한 뒤에는 sequence 19, checksum `b8ca94a1d8110c01939d703c6ef77c23a2d80322e8c83d554ae79d4496693792`다. 새 구현 run은 `planned`, sequence 1, checksum `fb670e1905a937422348fdd9962d310d88b8f65129db6bea939d36d8a1fa8711`로 유지됐다.
- receipt CAS 실행 확인: Git SHA를 전달한 `run-approve`는 `{"error":"contract_error","message":"expected receipt head must be lowercase SHA-256","ok":false,"retryable":false}`로 거부됐고 receipt는 바뀌지 않았다. helper 계약은 `bluetape_runtime.py:348-349`에서 확인했다.
- GitHub 실시간 조회: #293은 열림, milestone `2.2.0`, `chore`/`dependencies`, 담당자 `debop`; #942는 열림, milestone `2.2.0`, `documentation`/`enhancement`/`feature`/`test`, 담당자 `debop`.
- GNO: `bluetape4k-github`에서 #293과 #942 원문을 찾아 선행 관계와 alias 계약을 확인했다. `bluetape4k-docs`는 중앙 catalog 검증 관련 선례를 반환했으나 이번 결정의 직접 근거로 삼지 않고 live issue와 현재 저장소를 기준으로 했다.
- 검토 상태: 계획 보정은 helper 실행 순서와 live issue metadata만 바로잡았으며 승인된 alias 구현 목표와 파일 범위는 유지한다. 기존 사용자 승인이 계속 적용된다.

## 검토 실행 경계

native reviewer 실행은 `/opt/homebrew/Caskroom/codex/0.171.0/bin/codex-code-mode-host: host executable was not found` 오류로 시작되지 않았다. `plan_operator_ops`, `plan_user_caller`, `spec_performance` lane도 같은 실행 호스트 문제로 계획 내용을 읽기 전에 실패했다. 알려진 실행 실패를 반복 호출하지 않고 주 세션에서 여섯 관점을 검토했다. 따라서 이 문서는 독립 검토 attestation을 제공하지 않는다.

## 여섯 관점

| 관점 | 검토 내용 | 판정 |
|---|---|---|
| 성능 | 변경은 중앙 catalog alias 한 줄과 checksum이며 저장소 실행 경로나 런타임 성능을 바꾸지 않는다. Python 회귀 검사, Maven Central 전용 Gradle 소비자 프로젝트, 전체 빌드를 순차 실행한다. Testcontainers와 벤치마크를 제외한 범위는 명시되어 있다. | P0/P1 없음 |
| 안정성 | 테스트는 artifact, 기존 `exposed` ref, `1.6.1`을 확인하고 Gradle 소비자 프로젝트가 `libs.exposed.dao.r2dbc` 접근자와 해석 버전을 확인한다. checksum 검사와 전체 Python 테스트 묶음이 alias 오기와 주변 회귀를 보완한다. | P0/P1 없음 |
| 보안 | 소비자 프로젝트 저장소를 Maven Central 하나로 제한하고 새 버전 키, BOM 변경, 게시를 제외한다. 이번 alias는 bluetape4k 저장소에 실제 실행 dependency를 추가하지 않는다. | P0/P1 없음 |
| 운영 | 최신 `develop`, 이슈 상태와 catalog를 재확인한다. 설계 receipt는 `blocked` 이력으로 보존하며 새 run은 이미 초기화된 `planned` receipt를 재사용한다. `--expected-head`에는 직전 receipt checksum을 전달하고 각 mutation 응답의 checksum으로 갱신한다. 승인 파일 범위를 `mutation-check`한 뒤 PR exact-head CI와 metadata를 다시 읽는다. | P0/P1 없음 |
| 개발자/API | TOML alias 이름이 Gradle의 `libs.exposed.dao.r2dbc` 접근자로 생성되는지 임시 소비자 프로젝트의 설정 스크립트로 확인한다. `implementation(...)` 구문으로 catalog를 소비하고 `dependencyInsight`로 정확한 좌표와 버전을 확인한다. | P0/P1 없음 |
| 사용자/소비자 | #942의 별도 실험 모듈이 중앙 catalog에서 필요한 좌표를 선언할 수 있다. 실제 Exposed 모듈 구현, API 문서, 소비 저장소 변경은 #942에 남기며 병합 후 고정된 catalog commit SHA를 사용하도록 계획 경계가 잡혀 있다. | P0/P1 없음 |

## 통합 발견과 조치

| ID | 심각도 | 발견 | 조치 | 상태 |
|---|---|---|---|---|
| PLAN-P2-01 | P2 | 현재 검토일은 2026-11-25인데, 새 계획 리뷰와 향후 코드 리뷰/작업 교훈 파일 경로가 2026-11-24로 지정되어 있었다. | 계획 리뷰·코드 리뷰·작업 교훈 경로를 2026-11-25로 맞췄다. 기존 승인 설계와 계획 파일명은 작성일이므로 유지했다. | 해결 |
| PLAN-P2-02 | P2 | 새 실행 run의 `mutation-check` 대상에 뒤에서 작성할 코드 리뷰와 작업 교훈이 빠져 lane의 쓰기 범위와 일치하지 않았다. | 두 경로를 `mutation-check` 대상에 추가하고 lane `write_scope`와 동일하게 맞췄다. | 해결 |
| PLAN-P2-03 | P2 | Task 1의 이슈 read-back은 상태·제목·URL만 조회해 milestone, labels, assignee를 확인하지 않았다. | 두 이슈의 milestone/labels/assignees를 조회하도록 명령과 예상 결과를 보완했다. 현재 live 상태도 다시 확인했다. | 해결 |
| PLAN-P2-04 | P2 | Task 5의 `git diff --check`와 diff 출력은 Git에서 추적하지 않는 새 테스트·리뷰·작업 교훈 파일을 확인하지 못했다. | 새 파일을 `git add -N`으로 diff에 포함한 뒤 whitespace와 변경 내용을 읽도록 단계를 고쳤다. | 해결 |
| PLAN-P2-05 | P2 | Task 1은 이전 workflow run을 고정 ID로 종료하기 전에 현재 receipt chain과 run state를 재확인하지 않았다. | `run-block` 전에 `resume-check`, `receipt-diagnose`, `completion-check`를 읽기 전용으로 실행하고 state/checksum/누락 항목이 예상과 다르면 중단하도록 조건을 추가했다. | 해결 |
| PLAN-P2-06 | P2 | PR 생성 직전 #293만 다시 조회하고 두 이슈의 milestone, labels, assignee 최신값을 비교하지 않았다. | PR 생성 전 #293과 #942의 전체 metadata를 조회하고 Task 1 값과 대조하도록 명령과 예상 결과를 보완했다. | 해결 |
| PLAN-P2-07 | P2 | `run-approve`와 이후 helper 명령에 `git rev-parse HEAD`의 40자리 Git SHA를 `--expected-head`로 넘겼다. helper는 receipt의 64자리 lowercase SHA-256을 요구해 `contract_error`가 발생했다. | 계획에서 기존 `planned` run을 재사용하고 `resume-check.last_checksum`과 각 mutation 출력의 `checksum`을 순서대로 전달하도록 고쳤다. 실행 오류 후 새 run의 sequence 1 / checksum `fb670e1905a937422348fdd9962d310d88b8f65129db6bea939d36d8a1fa8711`이 유지됨을 read-back했다. | 해결 |
| PLAN-P2-08 | P2 | 계획과 이전 검토는 #293 milestone을 `backlog`로 기록했으나 현재 live GitHub 값은 `2.2.0`이다. | #293/#942 live metadata를 다시 조회하고 Task 1 예상값 및 본 검토를 `2.2.0`으로 맞췄다. issue scope와 label/assignee는 유지된다. | 해결 |

통합 검토에서 승인 설계와 수용 기준의 충돌, 파일 범위 확대, PR 병합 권한의 혼입은 찾지 못했다. 해결하지 않은 P2/P3는 없다.

## 수용 기준 추적 확인

| 설계 기준 | 계획 위치 | 확인 방법 |
|---|---|---|
| 기존 `exposed = "1.6.1"` 및 artifact 좌표 | Task 1–3 | 현재 catalog 재확인, Python 회귀 테스트, Gradle consumer |
| checksum sidecar 일치 | Task 3–4 | `shasum -a 256 -c` |
| Maven Central에서 accessor 및 버전 해석 | Task 4 | 임시 consumer의 `dependencyInsight` |
| generated catalog 및 Dependabot 정책 유지 | Task 4 | 두 동기화 helper의 `--check --summary` |
| 전체 Python 테스트와 저장소 build | Task 4 | unittest discovery와 `./gradlew build` |
| 좁은 변경과 이슈 연결 | Task 5–6 | exact diff, PR 본문과 live metadata |
| 병합/게시/tag 제외 | Task 6 | 명시적 정지 조건 및 별도 병합 승인 |

## Writer DoD

- [x] **SPW-01 — 근거와 독자 고정:** #293/#942, 계획·설계, live issue 상태와 검토 범위를 기록했다.
- [x] **SPW-02 — 리뷰 계약 충족:** 여섯 관점, 통합 발견, 심각도·처리, 수용 기준 추적 결과와 판정을 기록했다.
- [x] **SPW-03 — 한국어 기술 문체:** 한국어 자연스러움 checklist와 contextual terminology audit를 적용했고 finding 0건을 확인했다.
- [x] **SPW-04 — 기술 의미와 추적성:** 승인 설계와 구현 계획의 수용 기준을 task 단위로 대조했다.
- [x] **SPW-05 — 최종 read-back:** 표, 경로, 명령, 인용 오류와 P0/P1 결과를 확인했다.

**Writer gate: PASS** — 두 문서의 contextual terminology audit가 각각 finding 0건이며 Markdown 구조와 경로 read-back을 마쳤다.
