# Issue #242 Timefold Solver 2.6.0 중앙 전환 설계

## 문서 상태

- 상태: 사용자 승인 설계
- 대상 이슈: [bluetape4k-dependencies #242](https://github.com/bluetape4k/bluetape4k-dependencies/issues/242)
- 기준 저장소: `bluetape4k-dependencies` `develop` `b09670ae6d500d91688fcc15fcc201d40f60c2ce`
- 대상 버전: `ai.timefold.solver:timefold-solver-bom:2.6.0`
- 범위: 중앙 catalog/BOM, `bluetape4k-exposed`, `timefold-workshop`, `clinic-appointment`
- 제외: Issue #243 signing 변경, PR/merge, tag, Maven Central publication, 후보 배포 트리거

이 문서는 구현 전에 고정하는 Type-A 설계다. 현재 중앙 catalog는 Timefold
`2.4.0`을 유지한다. 소비자 검증과 publication 증거가 모두 통과하기 전에는
`defer-breaking-migration` 정책을 해제하거나 중앙 버전을 채택하지 않는다.

## 1. 문제와 결정

중앙 BOM은 `build.gradle.kts`에서 `api(platform(libs.timefold.solver.bom))`으로
Timefold BOM을 관리하지만 소비자마다 별도 version source와 BOM 경로가 있다.
따라서 version ref 하나를 `2.6.0`으로 바꾸는 것만으로는 다음을 증명할 수 없다.

- `core`, `benchmark`, `jackson`, `spring-boot-starter`가 실제 runtime에서
  `2.6.0`을 선택했는지
- `bluetape4k-exposed`의 score persistence가 저장 후 복원되는지
- workshop의 증분 점수와 `SolverManager` job lifecycle이 유지되는지
- clinic의 예약 제약, score 복원, Exposed DB 반영이 유지되는지
- 소비자가 동일한 immutable catalog/BOM 입력을 사용했는지

**결정:** 중앙 후보를 먼저 immutable SHA와 local candidate BOM digest로 고정한
뒤, Exposed → workshop → clinic 순서로 소비자 검증을 수행한다. 각 소비자는
baseline과 candidate를 같은 immutable consumer HEAD에서 별도로 실행한다. 하나의
필수 경로가 실패하면 중앙 catalog는 `2.4.0`과 보류 정책을 유지하고, 실패
증거와 재검토 조건을 보존한다.

## 2. 현재 근거와 이전 실패의 반영

### 2.1 현재 저장소 상태

| 대상 | 현재 기준 | 현재 version/BOM 경로 | 설계상 확인점 |
|---|---|---|---|
| 중앙 dependencies | `b09670ae6d500d91688fcc15fcc201d40f60c2ce` | `gradle/libs.versions.toml`의 `timefold-solver = "2.4.0"`; `build.gradle.kts:164`의 Timefold BOM import | catalog, checksum, delta ledger, POM 전체 |
| `bluetape4k-exposed` | `d5fb9602491ad64811bffcda227e3b2deecf9eea` | `settings.gradle.kts`가 immutable `bluetape4kDependenciesCatalogRef`를 내려받고 checksum 검증; `build.gradle.kts:317-320`이 `bt4kVersion("timefold-solver")`를 네 좌표에 적용 | candidate catalog SHA와 네 좌표의 선택 이유 |
| `timefold-workshop` | `e47496a` | `gradle/libs.versions.toml`이 Timefold `2.2.0`을 직접 선언하고 root build가 별도 Timefold BOM을 import | 중앙 BOM 단일 경로로 전환, JVM metadata |
| `clinic-appointment` | `9cd0ecb0d04d80bbdadddd8f52ed2d47cfc2f4cf` | root가 `bluetape4k-dependencies` BOM을 import하지만 `appointment-solver/build.gradle.kts:1-5`가 Timefold BOM `2.6.0`을 로컬 재정의; lockfile에는 `2.4.0`도 남아 있음 | local override 제거 후 resolved graph와 DB 테스트 |

### 2.2 보류 증거

`docs/releases/2026-09-07-issue-242-timefold-2.6.0-blocked-evidence.md`의 보류
판정을 설계 입력으로 사용한다.

1. 이전 graph runner는 `dependencyInsight` exit code만 검사해 `12/12 pass`를
   잘못 기록했다. 새 runner는 실제 좌표, 선택 version, `Selection reasons`,
   configuration과 output digest를 함께 검사한다.
2. `bluetape4k-exposed` 후보 graph가 `2.6.0`이 아니라 `2.4.0`을 선택했다.
3. workshop baseline과 candidate가 같은 후보 worktree를 재사용해 독립 baseline이
   아니었다.
4. clinic baseline은 immutable candidate BOM을 baseline repository에서 찾지 못했다.
5. 당시 workshop과 게시 artifact의 JVM target이 달라 테스트 실행 전 resolution이
   실패했다. 현재 workshop HEAD는 Java 25 toolchain을 선언하지만 candidate
   artifact metadata와의 일치는 다시 확인해야 한다.

이전 `12/12 pass`나 receipt 내부 digest 일치만으로는 채택하지 않는다.

## 3. 목표와 비목표

### 목표

- 중앙 catalog와 BOM 경로에서 Timefold `2.6.0`을 재현 가능한 candidate로 만든다.
- 네 필수 좌표의 before/after resolved version과 selection reason을 기록한다.
- Exposed persistence, workshop score/lifecycle, clinic constraint/score/DB 경계를
  실제 테스트로 검증한다.
- Spring Boot와 Jackson 결합, Exposed persistence artifact, 소비자 BOM 경로를
  함께 확인한다.
- catalog checksum, managed/shared version, Dependabot ignore, build, publisher
  POM/effective model 증거를 exact SHA에 결속한다.
- 실패 시 `2.4.0` 보류 상태를 유지하고 재현 가능한 차단 증거를 남긴다.

### 비목표

- Timefold API를 새로 추상화하거나 workshop 전체 교육 과정을 재작성하지 않는다.
- `timefold-workshop #54`의 shadow-variable 예제 확장은 필요한 compatibility
  수정이 아닌 한 이번 설계에 흡수하지 않는다.
- Issue #243의 signing helper, 중앙 plugin, publisher adapter는 변경하지 않는다.
- 태그, release, Maven Central publication, PR merge는 별도 승인 단계다.

## 4. 제안 구조

### 4.1 중앙 candidate

중앙 worktree에서 다음을 하나의 promotion unit으로 만든다.

1. `gradle/libs.versions.toml`의 `timefold-solver`를 `2.6.0`으로 변경한다.
2. `gradle/libs.versions.toml.sha256`를 다시 생성하고 catalog 구조를 검증한다.
3. `config/central-catalog-version-deltas.json`에 Timefold 네 좌표의 의도적
   resolved-version delta만 기록한다. 실제 선택 결과가 없는 보존 compatibility
   line은 delta로 기록하지 않는다.
4. `config/latest-stable-version-audit.json`과 inventory를 중앙 audit 명령으로
   갱신한다. `defer-breaking-migration` 해제는 모든 소비자 검증 뒤로 미룬다.
5. `./gradlew publishToMavenLocal`로 고유 candidate BOM coordinate를 만들고 POM와
   Gradle Module Metadata의 SHA-256을 저장한다. stable `2.1.0` 또는 최신 개발용
   artifact를
   candidate 증거로 사용하지 않는다.

candidate 식별자는 다음 입력을 모두 포함한다.

```text
central_commit_sha
catalog_sha256
candidate_bom_coordinate
candidate_pom_sha256
candidate_module_metadata_sha256
```

후속 consumer는 이 식별자와 `base_sha`를 receipt에 기록한다. moving branch,
현재 Maven Local의 이름 없는 artifact, 또는 마지막 실행의 출력만 재사용하지 않는다.

### 4.2 중앙 계약을 재사용하는 소비자 경로

#### `bluetape4k-exposed`

`settings.gradle.kts`의 immutable catalog download/checksum 경로에 candidate
commit을 주입한다. `build.gradle.kts`의 `bt4kVersion("timefold-solver")`가
다음 네 좌표에 동일한 candidate version을 제공하는지 확인한다.

```text
ai.timefold.solver:timefold-solver-core
ai.timefold.solver:timefold-solver-benchmark
ai.timefold.solver:timefold-solver-jackson
ai.timefold.solver:timefold-solver-spring-boot-starter
```

`exposed/timefold-solver-persistence`의 기존 score transformer 테스트를
candidate에서 실행하고, 대표 score를 insert → load → equality 비교로 검증한다.
`dependencyInsight` 결과에는 선택 version과 `Selection reasons`가 모두 있어야
하며, 좌표가 없으면 exit code와 관계없이 실패한다.

#### `timefold-workshop`

현재 local catalog의 `timefold-solver = "2.2.0"`와 별도 Timefold BOM import를
중앙 BOM 경로와 중복된 source로 판단한다. 기본 설계는 다음과 같다.

- local catalog의 Timefold module alias는 versionless로 유지한다.
- root build는 직접 Timefold BOM을 import하지 않고
  `bluetape4k-dependencies` BOM의 managed constraints를 사용한다.
- candidate 검증에서는 central candidate BOM coordinate와 catalog commit을
  동시에 고정한다.
- `01-quickstarts/school-timetabling`의 `SolverManager` submit/status/terminate
  lifecycle과 `exposed/jdbc-examples`, `exposed/r2dbc-examples`의 score round-trip을
  실행한다.

이 경로가 Gradle dependency-management에서 BOM constraint를 전달하지 못하면
`2.6.0` 명시 alias를 임시 검증 입력으로 사용할 수 있지만, 중앙 BOM 단일 경로를
확립하기 전에는 채택하지 않는다. JVM toolchain, Kotlin `jvmTarget`, dependency
artifact `TargetJvmVersion`이 모두 일치하지 않으면 테스트를 성공으로 집계하지
않고 #54와 함께 보류한다.

#### `clinic-appointment`

root의 `bluetape4k-dependencies` BOM을 candidate로 고정하고
`appointment-solver/build.gradle.kts`의 local Timefold BOM override를 제거한다.
versionless `timefold-solver-core`와 benchmark alias가 중앙 BOM에서
`2.6.0`을 선택해야 한다. 기존 lockfile의 `2.4.0` 항목은 무조건 문자열 치환하지
않고, 각 configuration을 candidate로 재해석한 뒤 lock을 갱신한다.

검증 범위는 다음과 같다.

- `ConstraintVerifier`와 예약 제약 regression
- move undo 이후 score 복원 및 `SolverResult`의 feasible 상태
- H2 및 PostgreSQL/Testcontainers 경로의 Exposed 저장/조회 반영
- Spring Boot/Jackson serialization과 solver module 결합

### 4.3 Publisher POM와 소비자 provenance

catalog candidate가 만들어진 뒤 등록 publisher 전체에 대해
`scripts/verify-publication-poms.py --workspace .. --summary`를 실행한다.
모든 POM의 dependency-management entry에는 실제 version 또는 versioned imported
BOM이 있어야 한다. Gradle build 통과만으로 POM 계약을 대체하지 않는다.

각 소비자 receipt에는 다음을 저장한다.

```text
repository
base_sha
candidate_commit_sha
catalog_sha256
candidate_bom_coordinate
configuration
resolved_versions
selection_reasons
test_task
output_sha256
result
```

baseline과 candidate는 같은 `base_sha`의 clean worktree에서 각각 실행한다.
candidate로 수정한 worktree를 baseline에 재사용하면 receipt를 만들지 않는다.

## 5. 실패 처리와 안전 경계

| 실패 | 판정 | 조치 |
|---|---|---|
| catalog checksum/구조 불일치 | 중앙 candidate invalid | catalog 채택 중단, checksum과 입력 SHA 보존 |
| 네 Timefold 좌표 중 하나라도 `2.6.0` 미선택 | graph invalid | `2.4.0` 보류 유지, `Selection reasons`와 output 보존 |
| baseline/candidate HEAD 불일치 | 비교 invalid | 동일 immutable HEAD에서 두 phase 재실행 |
| workshop JVM target 또는 BOM 전달 실패 | consumer blocked | #54와 원인/재검토 조건 기록, 중앙 version 유지 |
| Exposed persistence/clinic DB/score 실패 | consumer blocked | 해당 결과를 P1로 유지하고 promotion 중단 |
| publisher POM/effective model 실패 | publication contract invalid | 중앙 catalog adoption과 publication 모두 보류 |
| consumer catalog ref가 moving branch | provenance invalid | exact commit SHA와 sidecar checksum으로 다시 실행 |

실패한 worktree, local Maven repository, graph output은 명시적 정리 승인 전까지
보존한다. 기존 사용자 dirty 상태가 있는 worktree는 사용하지 않는다.

## 6. Type-A review 관점

구현 plan과 검증 receipt는 다음 여섯 관점을 독립적으로 확인한다.

| 관점 | 필수 질문 |
|---|---|
| Performance | candidate resolve와 workshop/clinic 테스트가 동일 입력에서 재현되며 timeout/캐시가 결과를 숨기지 않는가? |
| Stability | score, SolverManager lifecycle, DB round-trip 실패가 fail-closed로 중단되는가? |
| Security | local BOM, catalog URL, Gradle output에 secret이나 mutable ref가 들어가지 않는가? |
| Operator/Ops | 실패 산출물, exact SHA, checksum, 재실행 명령을 보존하는가? |
| Developer/API | 기존 Timefold alias와 Exposed persistence API를 불필요하게 깨지 않는가? |
| User/Caller | clinic/workshop 호출자가 실제로 중앙 버전을 받고 동일한 score 계약을 보는가? |

P0/P1 finding이 남으면 구현/PR/채택으로 진행하지 않는다.

## 7. 수용 기준과 DoD

다음 항목은 모두 충족해야 `2.6.0 adopted`를 검토할 수 있다.

- [ ] 중앙 catalog와 checksum이 `2.6.0`을 가리키고 catalog audit/inventory가 통과한다.
- [ ] core/benchmark/jackson/starter의 baseline/candidate resolved version과
  `Selection reasons`가 모두 `2.6.0`이다.
- [ ] `bluetape4k-exposed` persistence score round-trip 테스트가 통과한다.
- [ ] workshop의 incremental score와 `SolverManager` lifecycle, JDBC/R2DBC score
  persistence 테스트가 통과한다.
- [ ] clinic의 reservation constraint, score restoration, H2/PostgreSQL Exposed
  반영과 Spring/Jackson 결합 테스트가 통과한다.
- [ ] consumer별 immutable commit SHA, catalog checksum, candidate BOM POM/metadata
  digest가 receipt에 기록된다.
- [ ] 모든 등록 publisher의 publication POM/effective model이 통과한다.
- [ ] `sync-managed-catalog.py`, `sync-shared-versions.py`,
  `sync-dependabot-ignores.py`, Python regression suite와 `./gradlew build`가
  통과한다.
- [ ] 실패 또는 `SKIPPED` 필수 단계가 없고, 남은 gap은 모두 보류 사유로 기록된다.
- [ ] Type-A 여섯 관점에서 P0/P1이 0이다.

이 문서의 DoD는 merge, tag, release, 개발용 artifact 배포를 포함하지 않는다.
그 작업은 exact-head CI와 별도 사용자 승인 뒤에 수행한다.

## 8. 근거 원장

| 근거 | 용도 |
|---|---|
| `gradle/libs.versions.toml:105,679` | 중앙 Timefold version과 BOM alias |
| `build.gradle.kts:164` | 중앙 java-platform의 Timefold BOM import |
| `bluetape4k-exposed/settings.gradle.kts:8-153` | immutable catalog ref와 checksum contract |
| `bluetape4k-exposed/build.gradle.kts:317-320` | 네 Timefold 좌표의 central version injection |
| `timefold-workshop/gradle/libs.versions.toml` | 현재 local `2.2.0` 선언과 별도 aliases |
| `timefold-workshop/build.gradle.kts` | 현재 Java/Kotlin toolchain과 BOM imports |
| `timefold-workshop/01-quickstarts/school-timetabling/.../TimetableController.kt` | `SolverManager` lifecycle 호출자 |
| `timefold-workshop/exposed/{jdbc,r2dbc}-examples/src/test/...` | score persistence 소비자 |
| `clinic-appointment/appointment-solver/build.gradle.kts:1-30` | local Timefold BOM override와 version task |
| `clinic-appointment/build.gradle.kts:916-924` | 중앙 dependencies BOM import |
| `docs/releases/2026-09-07-issue-242-timefold-2.6.0-blocked-evidence.md` | 이전 graph/baseline/JVM 실패와 재검토 조건 |
| `https://github.com/TimefoldAI/timefold-solver/releases/tag/v2.6.0` | 공식 stable release와 변경 근거 |
| `https://github.com/bluetape4k/timefold-workshop/issues/54` | workshop migration 추적 |
| `https://github.com/bluetape4k/clinic-appointment/issues/450` | clinic 독립 Timefold 검증 추적 |

## 9. 설계 게이트 기록

- [x] 문제, 범위, 현재 source와 이전 실패 증거를 확인했다.
- [x] 중앙 BOM 단일 경로와 immutable consumer evidence를 선택했다.
- [x] baseline/candidate 분리, failure hold, rollback/보존 경계를 정의했다.
- [x] 수용 기준과 Type-A review 관점을 정의했다.
- [x] 사용자 설계 승인을 받았다.
- [ ] 구현 plan 승인 전에는 코드와 소비자 저장소를 변경하지 않는다.
