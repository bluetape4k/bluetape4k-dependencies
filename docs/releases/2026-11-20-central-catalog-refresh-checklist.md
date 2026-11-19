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
- 최신 audit 기준: `2026-11-19T19:48:34Z` retrieval, authority 523,
  catalog line 557, `adopt-latest` 18, `current` 424,
  `defer-breaking-migration` 32, `hold-compatibility` 74,
  `hold-unavailable` 9. catalog edit 전 후보를 재검증한 뒤, 동일
  version-key와 compatibility line이 모두 일치하는 105개 key를 채택했다.
  `aws2` `2.59.4`와 `sudachi` `0.8.2`는 대상 consumer 회귀를 재현해
  각각 `2.57.7`, `0.8.0`으로 compatibility hold했다. `spring-boot4`는 BOM
  두 line이 `4.2.0`을 제안하지만 Gradle plugin line은 `4.1.2`가 최신으로
  판정되어 혼합 key를 보류했다.

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
- [x] **CAT-02** — `gradle/libs.versions.toml`의 105개 version-key와
  Exposed `1.6.1`을 갱신하고 checksum `ef7046e44f28d4df4b7f1e5346b06fa2f0fbfef4f9838d81e246f643043e08d5`를
  기록했다. AWS SNS verifier와 bundled Sudachi legacy dictionary 회귀는
  각각 `aws2`, `sudachi` hold로 남겼다.
- [x] **CAT-03** — `config/latest-stable-version-deltas.json`과 central
  rollout evidence를 `catalog-refresh-2026-11-20-v2`로 생성했다. delta 105,
  status `validation-pending`이며 resolved graph 검증 전이다.
- [x] **CAT-04** — 중앙 `./gradlew build`와 catalog governance 127개 test를
  통과했다. audit/checksum/diff gate도 통과했다.
- [x] **CON-01** — 9개 consumer의 settings/CI catalog ref를 중앙 catalog
  commit `3a6c235067c11f09906654f078ae4d3821e16c96`으로 갱신하고 push했다.
- [x] **CON-02** — managed-catalog `188 aliases/8 sub-BOMs`, shared-version
  adoption clean, Dependabot ignore sync를 최종 candidate map에서 통과했다.
- [x] **POM-01** — 8개 publisher의 publication POM/effective-model gate를
  통과했다. `failures=0`, `files=191`, `dependencies=50483`,
  `maven_models=191`이다.
- [ ] **CON-03** — 9개 consumer의 대상 build/test와 exact candidate map을
  통과한다.
- [x] **NIGHTLY-01** — 각 대상 repository의 YAML 선언 input과 workflow SHA를
  dispatch 직전에 재확인했다. full scope를 지원하는 workflow에는 `scope=full`
  만 전달했고, input이 없는 workflow에는 추가 input을 전달하지 않았다.
- [ ] **NIGHTLY-02** — 중앙 CI는 run `44609638754`에서 exact head
  `d2575edadac0d9d875c849b99b40611e59263047`로 모든 required job이
  `success`를 반환했다. 9개 consumer Nightly는 exact candidate head로
  dispatch/read-back 중이다. 현재 `experimental` (`44605558895`), `aws`
  (`44605552377`, Maven Central 429 재시도 후), `graph` (`44605572658`,
  image-family gate 재시도 후), `javers` (`44605582315`), `text`
  (`44605595575`)는 exact head에서 성공했다. `projects` (`44605547390`)는
  catalog와 무관한 Maven Central 미게시 `kafka-clients:4.2.2` test-fixtures
  artifact로 재시도 후에도 실패했고, `leader` (`44605588086`)는 기존
  Detekt 위반으로 실패했다. Image (`44605577505`)는 788개 중
  `ChainGoldenImageTest` 1개 pixel mismatch로 실패했으며, 이는 catalog와
  무관한 기존 golden fixture 회귀와 동일하다. Exposed (`44611685663`)는
  첫 시도에서 `1.6.1` plugin/migration 및 Jackson/Flyway/JUnit 연쇄 POM의
  Maven Central 전파 지연으로 실패했고, 현재 공개 URL 복구 및 로컬 Ktor
  검증을 확인해 failed jobs 1회 재시도 중이다. (merge 전 candidate라
  `develop` 보호 조건은 아직 충족하지 않았다.)
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

## 최종 candidate 증거

- 중앙 immutable catalog commit: `3a6c235067c11f09906654f078ae4d3821e16c96`;
  snapshot policy/registry baseline commit: `ae4f572104bde572401e8c5bfaeef95ee1d0a80a`;
  central fixture-contract CI repair commit: `d2575edadac0d9d875c849b99b40611e59263047`.
- Repository map SHA-256: `9bfca79fa45cf1905fb7d7365e843900674daf102a2227f78842e7bddcf9d1aa`;
  candidate manifest SHA-256: `6a80238a88c1fa34007fb4f0633d34c96dd91283d4859e0a9b6266919dfb586d`.
- 최종 candidate branch head는 projects `f06a44e057db68044d1a2034bf42b9f089fac325`,
  aws `1edea816b42d5330282914167b2ed1b13892afda`, experimental
  `3322db42a454c5630b78111356c4968efccd04a0`, exposed
  `637f30ebe219ae6771700b82e21b650f5c4a8fb8`, graph
  `9d07656224cfa10c1719775ceba7cb634968b788`, image
  `baa31049290250030cc3ce81ce7e79ac9881ef4f`, javers
  `bcca5423730e841f478d7e74d168904119b93e55`, leader
  `0801b492b56d9baf272eef9d783a4778ff84053a`, text
  `4985806c518721bf2fc468088b913a074bed47d1`이다.
