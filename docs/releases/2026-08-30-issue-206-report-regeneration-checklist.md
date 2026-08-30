# Issue #206 report-only 재생성 체크리스트

상태: **구현 중 / PR merge-ready까지 승인 / merge·dispatch·publication 보류**

## Release identity

| 항목 | 고정값 |
| --- | --- |
| Repository | `bluetape4k/bluetape4k-dependencies` |
| Flow / class | `routine-snapshot` / `dependencies-major-train`의 report-only 관측 보강 |
| Target version | `2.0.0-SNAPSHOT` |
| Version authority | `gradle.properties`의 `baseVersion=2.0.0`, `snapshotVersion=`; workflow가 `-PsnapshotVersion=-SNAPSHOT` 주입 |
| Base / head | `develop@711b4d850b2afe549e0557ea199132b69def9d81` / `chore/issue-206-report-regeneration` |
| Artifact matrix | `io.github.bluetape4k:bluetape4k-dependencies:2.0.0-SNAPSHOT` BOM 1종과 train별 report-only artifact |
| Catalog role | catalog/version authority 변경 없음; checked-in baseline records를 train 시각으로 재생성 |
| Latest external version | `2.0.0-SNAPSHOT`, timestamp `20260830.061434`, build `4`, metadata `lastUpdated=20260830061434` |
| Latest successful train | [Publish Snapshot #33296408331](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/33296408331), head `9495811cbfeb84e378bd6eaae3e4fb85d50f4ca5` |
| Consumer scope | 현재 repository workflow와 artifact 증거만 변경; downstream repository, catalog ref, dependency version은 변경하지 않음 |
| Target authority | 사용자 승인: 구현, 검증, commit, push, `develop` 대상 PR 생성 및 exact-head CI 확인 |
| Dispatch hold | merge, `workflow_dispatch`, Maven Central publication, tag, release, milestone close는 별도 승인 전까지 실행하지 않음 |

## Live closeout

- [x] Issue [#206](https://github.com/bluetape4k/bluetape4k-dependencies/issues/206): OPEN, assignee `debop`, label `chore`, milestone `2.0.0`
- [x] Issue [#199](https://github.com/bluetape4k/bluetape4k-dependencies/issues/199): CLOSED; 동일 report 재사용 공백을 #206으로 이관
- [x] milestone `2.0.0`: open issue 1건이며 #206만 남음
- [x] open PR: 0건
- [x] 기존 두 train은 report SHA-256 `468cd70c1e50a2c6f889a48f293a37449ed6a699fd036de6b1c588365a529008`과 `generated-at`을 재사용함

## Implementation and evidence plan

- [x] train id와 생성 시각이 다른 run-scoped report를 생성한다.
- [x] report SHA-256, 실행 명령, record별 owner/evidence URL을 artifact에서 read-back 가능하게 한다.
- [x] `review`, high/critical reachable, expired exception, exception update, triage 시간을 train metadata에 기록한다.
- [x] findings는 report-only로 유지하고 malformed contract만 workflow를 실패시킨다.
- [x] `Publish Snapshot`이 publication metadata 검증 뒤 artifact와 job summary를 남기도록 구성한다.
- [ ] 두 개 이상의 연속 성공 train artifact를 비교한 후 #199/#206에 결과를 연결한다.

## 구현 검증

- [x] TDD RED: generator 부재 2건과 workflow 계약 부재 1건이 예상 원인으로 실패
- [x] TDD RED/GREEN: `report-only=false` source 거부와 0이 아닌 triage 밀리초 기록을 각각 실패 후 통과로 확인
- [x] targeted unit tests: 17 tests, failures/errors/skipped=0
- [x] Python 3.13 full suite: 301 tests, failures/errors=0; 기존 외부 SNAPSHOT 403 조건 2건은 conditional skip
- [x] `ruff check`와 새 파일 `ruff format --check`: PASS
- [x] `actionlint .github/workflows/publish-snapshot.yml`: PASS
- [x] `./gradlew build --no-daemon --no-configuration-cache --console=plain`: `BUILD SUCCESSFUL`
- [x] local artifact read-back: report 7 records, distinct SHA-256, owner/evidence 7건, positive triage duration

## Release checklist disposition

| Gate | 상태 | 근거 / 다음 조건 |
| --- | --- | --- |
| `REL-01` target inventory | PASS | 위 identity 표에 version, SHA, artifact, authority, consumer scope, hold를 고정 |
| `REL-02` issue/PR state | PENDING | #206 구현 PR과 후속 실제 train 증거가 남아 있음 |
| `REL-03` snapshot train proof | PENDING | 변경 merge 후 실제 성공 train 2개 artifact 필요 |
| `REL-04` stable batches | N/A | 안정 배포·batch 실행은 이번 승인 범위 밖 |
| `REL-05` dependencies final gate | N/A | final stable BOM publication은 범위 밖 |
| `REL-06` consumers | N/A | downstream 변경은 명시적으로 제외 |
| `REL-07` next development line | N/A | 현재 target 자체가 `2.0.0-SNAPSHOT` development line |
| `REL-08` public docs | N/A | stable docs handoff는 범위 밖 |
| `REL-09` irreversible hold | PENDING | merge/dispatch/publication 직전에 별도 승인과 live 재확인 필요 |

## Stop condition

PR exact head의 CI와 review evidence가 모두 통과하면 merge-ready로 보고하고 정지한다.
merge 후 자동 `Publish Snapshot` 실행과 두 번째 train을 위한 수동 dispatch는 각각 새 승인 경계로 남긴다.
