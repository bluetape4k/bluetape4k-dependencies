# 2026-11-20 중앙 catalog 최신화·consumer train 체크리스트

상태: **IN PROGRESS**

## 목표와 고정 범위

- 분류: Type P `catalog-train-snapshot`, 저장소 class `dependencies-only`.
- 중앙 저장소: `bluetape4k/bluetape4k-dependencies`; base `origin/develop`
  `8d0df9233939afa7a6b1e995c0ca3f90de42674`; 작업 branch
  `chore/catalog-refresh-2026-11-20-v2`.
- 목표: JetBrains Exposed `1.6.0 -> 1.6.1`을 포함해 공식 metadata에서
  확인된 호환성 유지 최신 stable 버전을 중앙 catalog에 반영하고, 9개
  managed consumer의 immutable catalog ref를 같은 중앙 commit으로 수렴한다.
- 실행 요청 범위: central catalog, downstream refs/sync, nightly, snapshot
  publication. Stable publication, tag, merge와 public release는 별도 gate로
  유지한다.
- 최신 audit 기준: `2026-11-19T18:43:53Z` retrieval, authority 523,
  catalog line 557, `adopt-latest` 2, `current` 439,
  `defer-breaking-migration` 33, `hold-compatibility` 74,
  `hold-unavailable` 9. catalog edit 전 135개 line 후보를 재검증한 뒤,
  동일 version-key와 compatibility line이 모두 일치하는 107개 key를
  채택했다. `spring-boot4`는 BOM 두 line이 `4.2.0`을 제안하지만 Gradle
  plugin line은 `4.1.2`가 최신으로 판정되어 혼합 key를 보류했다.

## 작업 위치와 보호 경계

모든 변경은 각 저장소의 새 격리 worktree에서 수행한다. 기존 dirty checkout,
기존 worktree와 기존 branch는 재사용하거나 삭제하지 않는다.

| 저장소 | 작업 branch | 기준 `origin/develop` |
| --- | --- | --- |
| `bluetape4k-dependencies` | `chore/catalog-refresh-2026-11-20-v2` | `8d0df9233939afa7a6b1e995c0ca3f90de42674` |
| `bluetape4k-projects` | `chore/catalog-refresh-2026-11-20-v2` | `b0e270adec9e964c5604e455923f8b8d222819ad` |
| `bluetape4k-aws` | `chore/catalog-refresh-2026-11-20-v2` | `7d3fef99b99eef1dfd25b602187c9d476df7e3af` |
| `bluetape4k-experimental` | `chore/catalog-refresh-2026-11-20-v2` | `b72d6b63946cf95a154bba7fdae0d7bc9a49a106` |
| `bluetape4k-exposed` | `chore/catalog-refresh-2026-11-20-v2` | `e84252c9f3e2b586082e1a0baec6deef8a64840b` |
| `bluetape4k-graph` | `chore/catalog-refresh-2026-11-20-v2` | `f8c47cbde0e4989d3260cbdd6581847a900649eb` |
| `bluetape4k-image` | `chore/catalog-refresh-2026-11-20-v2` | `304f62a56f013e137d9c4102877e2e89b2bc8132` |
| `bluetape4k-javers` | `chore/catalog-refresh-2026-11-20-v2` | `b87401d39accb5ab4ce5e23b1611c51ec8ed090a` |
| `bluetape4k-leader` | `chore/catalog-refresh-2026-11-20-v2` | `07b5e0a95ff672cec62a36f7c67c55d7513c8c96` |
| `bluetape4k-text` | `chore/catalog-refresh-2026-11-20-v2` | `b728f658cec324668bebd19447bbec9879615ca0` |

## 실행 DAG

1. 중앙 catalog의 최신 stable 후보를 재검증하고 catalog, checksum, audit,
   delta evidence를 갱신한다.
2. 중앙 후보를 커밋·push한 뒤 그 immutable commit SHA를 9개 consumer의
   `settings.gradle.kts`와 CI ref에 반영한다.
3. 중앙 policy의 snapshot ref와 publisher repository map을 소비자 후보
   commit에 맞추고, sync/governance/POM/build 검증을 수행한다.
4. 정확한 develop head와 선언된 workflow inputs를 다시 읽은 뒤 Nightly를
   실행한다.
5. Nightly와 exact-head CI가 통과하고 publication hold 조건이 충족되면
   `Publish Snapshot`을 실행하고 공개 metadata/artifact를 read-back한다.
6. merge, tag, stable publication은 별도 승인 없이는 실행하지 않는다.

## 필수 게이트

- [x] **CL-01** — 변경 전 workflow·repo guidance·GNO/live 상태를 확인하고
  이 checklist를 격리 worktree에 작성했다.
- [x] **CL-02** — Type P와 central/downstream/nightly/snapshot 범위를 고정했다.
- [x] **CL-03** — 새 semantic branch/worktree를 10개 저장소에 만들고 기존
  dirty/unmerged 상태를 보존했다.
- [x] **CAT-01** — 최신 stable audit를 새 catalog 기준으로 재생성했다.
  `authority=523`, `lines=557`, `metadata-unavailable=0`을 확인했다.
- [x] **CAT-02** — `gradle/libs.versions.toml`의 107개 version-key와
  Exposed `1.6.1`을 갱신하고 checksum `839994e63f01e47a377a84bcea28266184de6a84db1cff844162176f0f4dac9b`을
  기록했다.
- [x] **CAT-03** — `config/latest-stable-version-deltas.json`과 central
  rollout evidence를 `catalog-refresh-2026-11-20`으로 생성했다. delta 107,
  status `validation-pending`이며 resolved graph 검증 전이다.
- [ ] **CAT-04** — 중앙 `./gradlew build`와 catalog governance test를 통과한다.
- [ ] **CON-01** — 9개 consumer의 settings/CI catalog ref를 한 immutable
  central commit으로 갱신한다.
- [ ] **CON-02** — managed-catalog/shared-version/Dependabot ignore sync를
  각 후보에서 검증한다.
- [ ] **POM-01** — 8개 publisher와 catalog-only experimental의 publication
  POM/effective-model gate를 통과한다.
- [ ] **CON-03** — 9개 consumer의 대상 build/test와 exact candidate map을
  통과한다.
- [ ] **NIGHTLY-01** — 각 대상 repository의 YAML 선언 input과 workflow SHA를
  dispatch 직전에 재확인한다.
- [ ] **NIGHTLY-02** — 선언된 Nightly workflow를 정확한 develop head에서
  실행하고 run/head/job 결과를 read-back한다.
- [ ] **PUB-01** — snapshot publication preflight에서 baseVersion,
  `snapshotVersion`, signing, policy ref, exact CI/Nightly run을 고정한다.
- [ ] **PUB-02** — central `Publish Snapshot` workflow를 선언된 `ci_run_id`
  로만 dispatch한다.
- [ ] **PUB-03** — 중앙 BOM과 8개 publisher snapshot의 metadata/POM 및
  대표 artifact를 공개 저장소에서 검증한다.
- [ ] **PUB-04** — 9개 consumer의 snapshot catalog ref와 publication 결과를
  read-back하고 receipt를 봉인한다.
- [ ] **DOC-01** — `git diff --check`, checklist/evidence SHA, Korean reader
  문서와 generated file 계약을 확인한다.
- [ ] **CLOSE-01** — `Required checks: X/Y; N/A: N; Blocked: N` 집계를
  evidence와 일치시키고 미완료 ID를 보고한다.

## 승인·정지 조건

- 중앙/consumer branch push는 요청된 catalog train과 snapshot 실행에 필요한
  범위로 제한한다. PR 생성·merge·tag·stable publication은 target/base/head와
  fresh exact-head 승인 없이는 수행하지 않는다.
- workflow가 지원하지 않는 input, stale head, dirty publisher, missing POM,
  unresolved dependency graph, failed/skipped required job이 발견되면 해당
  downstream side effect를 중지하고 `PENDING` 또는 `BLOCKED`로 기록한다.
- nightly 또는 snapshot이 성공해도 그것이 merge approval이나 stable release
  approval을 대체하지 않는다.
