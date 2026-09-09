# Timefold 2.6.0 중앙 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ai.timefold.solver` 네 좌표를 중앙 `bluetape4k-dependencies` BOM의
`2.6.0` candidate로 고정하고, `bluetape4k-exposed`, `timefold-workshop`,
`clinic-appointment`의 동일한 immutable 입력에서 dependency graph, persistence,
score/lifecycle, DB, publication POM 계약을 검증한다. 모든 필수 증거가 통과한 뒤에만
중앙 catalog의 `2.4.0` 보류 상태를 해제할 수 있도록 receipt와 재현 명령을 남긴다.

**Architecture:** 중앙 catalog SHA와 고유 local candidate BOM을 먼저 만든다. 각
소비자는 같은 base commit에서 baseline worktree와 candidate worktree를 분리하고,
catalog SHA, BOM POM/Module Metadata digest, resolved version, `Selection reasons`,
test output digest를 receipt에 기록한다. Issue #243 signing lane과 publication,
merge, tag는 이 plan의 입력이나 실행 대상이 아니다.

**Tech Stack:** Gradle `java-platform`, version catalog, Python 3.13
`unittest`, Kotlin/JVM, Maven POM/Gradle Module Metadata, Git worktree,
JSON receipt, GitHub Actions exact-head checks.

---

## 실행 경계와 고정 입력

- 기준 중앙 commit은 `b09670ae6d500d91688fcc15fcc201d40f60c2ce`이다.
- 대상 BOM은 `ai.timefold.solver:timefold-solver-bom:2.6.0`이다.
- candidate BOM coordinate는 `io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local`이다.
- 소비자 기준 HEAD는 `bluetape4k-exposed` `d5fb9602491ad64811bffcda227e3b2deecf9eea`,
  `timefold-workshop` `e47496a`, `clinic-appointment`
  `9cd0ecb0d04d80bbdadddd8f52ed2d47cfc2f4cf`를 fetch 직후 다시 고정한다.
- 현재 `config/latest-stable-audit-policy.json`의
  `defer-breaking-migration` 정책은 전체 검증 전까지 유지한다.
- 명령 실행은 `--no-daemon --no-configuration-cache --no-build-cache
  --console=plain`을 사용하고, baseline과 candidate는 동일한 consumer HEAD의
  별도 clean worktree에서 실행한다.
- 실패한 worktree, local Maven repository, graph output, receipt는 사용자에게
  정리 승인을 받기 전까지 삭제하지 않는다.
- PR 생성, merge, tag, Maven Central publication, workflow dispatch는 각각 별도
  사용자 승인 전에는 실행하지 않는다.

## 파일과 저장소 책임

| 책임 | 파일 또는 저장소 | 변경 경계 |
| --- | --- | --- |
| 중앙 runner | `scripts/run-issues-242-243-validation.py` | Issue #242 scope와 네 좌표 graph |
| 중앙 receipt | `scripts/verify-issues-242-243-receipt.py` | issue별 필수 phase 검증 |
| 중앙 회귀 테스트 | `tests/test_run_issues_242_243_validation.py`, `tests/test_verify_issues_242_243_receipt.py` | 기존 combined mode 보존 |
| 중앙 catalog | `gradle/libs.versions.toml`, `gradle/libs.versions.toml.sha256` | Timefold ref와 checksum |
| 중앙 정책/원장 | `config/latest-stable-audit-policy.json`, `config/central-catalog-version-deltas.json` | 검증 전 보류, 검증 후 전환 |
| Exposed | `../bluetape4k-exposed/settings.gradle.kts`, `build.gradle.kts`, `exposed/timefold-solver-persistence` | immutable catalog와 중앙 BOM만 사용 |
| Workshop | `../timefold-workshop/gradle/libs.versions.toml`, `build.gradle.kts`, school/JDBC/R2DBC tests | local Timefold BOM/version 제거 |
| Clinic | `../clinic-appointment/appointment-solver/build.gradle.kts`, lockfiles, solver/API tests | local BOM override 제거 후 lock 재생성 |
| 검증 산출물 | `build/issues-242-243/`, `docs/releases/` | exact SHA/digest와 실패 원인 보존 |

## Task 1: exact-head 작업 공간과 baseline receipt를 고정한다

**Files:**
- Create: `build/issues-242-243/issue-242-repository-map.json` (local evidence)
- Create: `build/issues-242-243/issue-242-receipt.json` (local evidence)
- Create: `build/issues-242-243/issue-242-candidate-maven-repository/` (local evidence)
- Modify: none

- [ ] **Step 1: upstream ref와 dirty 상태를 한 번 수집한다.**

  ```bash
  for repo in bluetape4k-dependencies bluetape4k-exposed timefold-workshop clinic-appointment; do
    git -C "/Users/debop/work/bluetape4k/$repo" fetch origin develop
    git -C "/Users/debop/work/bluetape4k/$repo" rev-parse 'origin/develop^{commit}'
    git -C "/Users/debop/work/bluetape4k/$repo" status --porcelain=v1 --untracked-files=all
  done
  ```

  기대 결과: 네 저장소의 SHA와 원 checkout dirty 목록이 receipt의 `inputs`에
  기록되고, 원 checkout에는 파일 변경이 없다. `bluetape4k-image`의 기존 dirty
  상태는 이 작업에서 변경하지 않는다.

- [ ] **Step 2: consumer baseline/candidate worktree를 기준 SHA에서 만든다.**

  ```bash
  git -C /Users/debop/work/bluetape4k/bluetape4k-exposed worktree add \
    .worktrees/chore/issue-242-timefold-2.6.0-baseline \
    -b chore/issue-242-timefold-2.6.0-baseline d5fb9602491ad64811bffcda227e3b2deecf9eea
  git -C /Users/debop/work/bluetape4k/timefold-workshop worktree add \
    .worktrees/chore/issue-242-timefold-2.6.0-baseline \
    -b chore/issue-242-timefold-2.6.0-baseline e47496a
  git -C /Users/debop/work/bluetape4k/clinic-appointment worktree add \
    .worktrees/chore/issue-242-timefold-2.6.0-baseline \
    -b chore/issue-242-timefold-2.6.0-baseline 9cd0ecb0d04d80bbdadddd8f52ed2d47cfc2f4cf
  ```

  candidate worktree는 각각 `chore/issue-242-timefold-2.6.0-candidate`로 같은
  commit에서 추가한다. 각 worktree에 대해 `git rev-parse HEAD`,
  `git status --porcelain=v1 --untracked-files=all`, `git remote get-url origin`을
  receipt에 저장한다. dirty 또는 HEAD mismatch가 있으면 해당 consumer를
  `blocked`로 두고 source 수정으로 진행하지 않는다.

- [ ] **Step 3: baseline receipt schema를 테스트로 먼저 고정한다.**

  `tests/test_verify_issues_242_243_receipt.py`에 Issue #242 단독 문서를 추가하고,
  repository name, base/candidate SHA, catalog SHA, candidate BOM coordinate,
  POM/Module Metadata digest, graph configuration, resolved versions,
  `Selection reasons`, test task, output digest가 하나라도 없으면 거부하도록
  실패 케이스를 작성한다. signing helper, signing digest, signing repository를
  Issue #242 문서의 필수 필드로 요구하지 않는다.

- [ ] **Step 4: RED를 확인한다.**

  ```bash
  python3 -m unittest tests/test_verify_issues_242_243_receipt.py
  ```

  기대 결과: 새 `issue-242` schema/검증 경로가 아직 없어서 새 테스트가 실패한다.

- [ ] **Step 5: map/receipt 최소 골격을 구현하고 exact path를 검증한다.**

  `scripts/verify-issues-242-243-receipt.py`의 기존 canonical path, SHA, secret
  redaction primitive을 재사용해 `issue-242` 범위와 기존 `[242, 243]` combined
  범위를 분리한다. receipt transition은 `discovered -> prepared -> validated ->
  adopted`와 `discovered|prepared|validated -> blocked`만 허용하고, candidate
  artifact digest는 반드시 실제 파일에서 다시 계산한다.

- [ ] **Step 6: GREEN과 작업 공간 무결성을 확인한다.**

  ```bash
  python3 -m unittest tests/test_verify_issues_242_243_receipt.py
  git worktree list --porcelain
  ```

  기대 결과: receipt 단독 테스트가 통과하고, baseline/candidate가 서로 다른
  path이면서 같은 base SHA를 가리킨다.

## Task 2: validation runner에 Issue #242 단독 scope를 추가한다

**Files:**
- Modify: `scripts/run-issues-242-243-validation.py`
- Modify: `tests/test_run_issues_242_243_validation.py`

- [ ] **Step 1: scope contract RED 테스트를 추가한다.**

  `--scope issue-242`가 `signing-buildsrc`를 만들지 않고
  `candidate-bom-publication`, `timefold-graphs-baseline`,
  `timefold-graphs-candidate`, `consumers`, `publication-poms`만 허용하는지
  검증한다. 인자 없이 실행하는 기존 combined mode는 현재 `PHASES`와 signing
  repository 선택을 그대로 유지해야 한다. `issue-242`에서
  `bluetape4k-exposed`의 graph coordinate가 `core`, `benchmark`, `jackson`,
  `spring-boot-starter` 네 개로 생성되는 테스트를 추가한다. 정확한 좌표는
  다음 네 개로 고정한다.

  ```text
  ai.timefold.solver:timefold-solver-core
  ai.timefold.solver:timefold-solver-benchmark
  ai.timefold.solver:timefold-solver-jackson
  ai.timefold.solver:timefold-solver-spring-boot-starter
  ```

- [ ] **Step 2: RED를 확인한다.**

  ```bash
  python3 -m unittest tests/test_run_issues_242_243_validation.py
  ```

  기대 결과: scope parser와 Exposed 네 좌표가 없어 새 테스트가 실패한다.

- [ ] **Step 3: 최소 구현으로 phase/coordinate 선택을 분리한다.**

  parser에 `--scope {issues-242-243,issue-242}`를 추가하고, scope에 따라
  `build_phase_jobs()`가 allowlist를 선택하게 한다. `TIMEFOLD_GRAPH_COORDINATES`
  를 네 좌표 계약에 맞추고, `parse_dependency_insight()`의 실제 selected
  version과 비어 있지 않은 `Selection reasons` 검사를 그대로 사용한다.
  candidate graph는 모든 좌표가 `2.6.0`이 아니면 실패한다. signing phase를
  Issue #242 scope에서 호출하면 명확한 `InputContractError`를 반환한다.

- [ ] **Step 4: GREEN과 combined 회귀를 실행한다.**

  ```bash
  python3 -m unittest tests/test_run_issues_242_243_validation.py
  python3 scripts/run-issues-242-243-validation.py --help
  ```

  기대 결과: 단독 scope 테스트, 기존 combined parser 테스트, wrong-version
  fail-closed 테스트가 모두 통과한다.

## Task 3: Issue #242 receipt validator를 fail-closed로 완성한다

**Files:**
- Modify: `scripts/verify-issues-242-243-receipt.py`
- Modify: `tests/test_verify_issues_242_243_receipt.py`

- [ ] **Step 1: phase 필수 집합과 graph coverage RED 테스트를 작성한다.**

  `issue-242` 문서가 signing phase를 요구하지 않으며, candidate BOM, baseline
  graph, candidate graph, consumers, publication POM, candidate artifacts를
  모두 요구하는지 테스트한다. Exposed 네 좌표와 Workshop 세 좌표, Clinic
  benchmark 좌표 각각에 selected version과 `Selection reasons`가 없으면
  receipt를 거부하는 케이스를 추가한다. baseline/candidate consumer HEAD가
  다르면 거부하는 케이스도 고정한다.

- [ ] **Step 2: RED를 확인한다.**

  ```bash
  python3 -m unittest tests/test_verify_issues_242_243_receipt.py
  ```

- [ ] **Step 3: scope별 validator를 구현한다.**

  기존 signing field 검증을 combined scope에만 적용하고, Issue #242에서는
  `issue`, `scope`, `candidate_bom`, `catalog`, `consumers`, `phases`,
  `candidate_artifacts`, `terminal_evidence`를 검사한다. `SKIPPED`, `NO-SOURCE`,
  graph coordinate 누락, output digest 누락, moving branch ref, POM 또는 Module
  Metadata SHA 불일치는 `blocked`/실패로 처리한다. 성공 상태의 필수 artifact는
  actual file bytes와 다시 비교한다.

- [ ] **Step 4: GREEN과 CLI 검증을 실행한다.**

  ```bash
  python3 -m unittest tests/test_verify_issues_242_243_receipt.py
  python3 scripts/verify-issues-242-243-receipt.py validate \
    --receipt build/issues-242-243/issue-242-receipt.json --allow-prepared
  ```

  기대 결과: Issue #242 sample receipt가 통과하고, combined receipt의 signing
  필수 검증도 기존과 동일하게 통과한다.

## Task 4: 중앙 catalog candidate를 TDD로 만든다

**Files:**
- Modify: `tests/test_catalog_checksum.py`
- Modify: `tests/test_central_catalog_version_deltas.py`
- Modify: `tests/test_audit_latest_stable.py`
- Modify: `gradle/libs.versions.toml`
- Modify: `gradle/libs.versions.toml.sha256`
- Modify: `config/central-catalog-version-deltas.json`
- Modify: `config/latest-stable-version-audit.json` (audit output only)
- Modify: `config/latest-stable-version-inventory.json` (audit output only)

- [ ] **Step 1: candidate expectation을 먼저 RED로 바꾼다.**

  `tests/test_catalog_checksum.py`에서 Timefold ref의 기대값을 `2.6.0`으로
  바꾸고 checksum sidecar가 실제 catalog bytes와 일치하는지 유지한다.
  `tests/test_audit_latest_stable.py`에는 `defer-breaking-migration`이 전체
  소비자 검증 전까지 유지되어야 한다는 assertion을 남긴다.

- [ ] **Step 2: RED를 확인한다.**

  ```bash
  python3 -m unittest tests/test_catalog_checksum.py tests/test_central_catalog_version_deltas.py tests/test_audit_latest_stable.py
  ```

  기대 결과: 아직 중앙 catalog가 `2.4.0`이므로 candidate expectation이 실패한다.

- [ ] **Step 3: central catalog와 checksum을 최소 변경한다.**

  `gradle/libs.versions.toml`의 `timefold-solver`만 `2.6.0`으로 변경하고,
  `sha256sum gradle/libs.versions.toml > gradle/libs.versions.toml.sha256`로
  sidecar를 다시 만든다. BOM alias와 `build.gradle.kts:164`의
  `api(platform(libs.timefold.solver.bom))`는 유지한다.

- [ ] **Step 4: audit/delta ledger를 validation-pending으로 갱신한다.**

  ```bash
  python3.13 scripts/audit-latest-stable.py --write --refresh-audit \
    --refresh-delta-ledger --baseline-ref develop \
    --delta-ledger config/central-catalog-version-deltas.json \
    --audit-cutoff 2026-09-09 \
    --rollout 2026-09-09-issue-242-timefold-2.6.0 \
    --refresh-central-rollout \
    --central-ledger-base-ref develop --summary --audit-summary
  ```

  ledger의 Timefold entry는 실제 graph/POM 결과가 생길 때까지
  `validation-pending`으로 남긴다. `defer-breaking-migration`을 제거하지 않는다.

- [ ] **Step 5: 중앙 Python 회귀와 catalog governance를 GREEN으로 확인한다.**

  ```bash
  python3 -m unittest tests/test_catalog_checksum.py tests/test_central_catalog_version_deltas.py tests/test_audit_latest_stable.py tests/test_ci_catalog_governance.py
  scripts/sync-managed-catalog.py --check --summary
  scripts/sync-shared-versions.py --workspace .. --check --summary
  scripts/sync-dependabot-ignores.py --workspace .. --check --summary
  ```

  기대 결과: catalog checksum, audit hold, managed/shared/Dependabot contract가
  통과한다.

## Task 5: candidate BOM POM와 Module Metadata를 만든다

**Files:**
- Modify: `build/issues-242-243/issue-242-receipt.json`
- Create: `build/issues-242-243/issue-242-candidate-maven-repository/` (local evidence)
- Modify: none in `config/issues-242-243-candidate.init.gradle`

- [ ] **Step 1: candidate publication phase를 dry-run으로 바인딩한다.**

  ```bash
  python3 scripts/run-issues-242-243-validation.py \
    --scope issue-242 --phase candidate-bom-publication \
    --repository-map build/issues-242-243/issue-242-repository-map.json \
    --receipt build/issues-242-243/issue-242-receipt.json \
    --candidate-maven-repository build/issues-242-243/issue-242-candidate-maven-repository \
    --execution-boundary persistent-trusted --dry-run --summary
  ```

  기대 결과: signing repository나 stable `2.1.0` artifact를 참조하지 않는
  allowlisted Gradle command가 출력된다.

- [ ] **Step 2: candidate BOM을 local repository에 publish한다.**

  runner의 `candidate-bom-publication` phase를 실행하고
  `bluetape4k-dependencies-2.1.0-issue-242.local.pom`와 `.module`을 생성한다.
  두 파일의 SHA-256, catalog commit SHA, catalog sidecar SHA를 receipt에 저장한다.

- [ ] **Step 3: POM/module contract를 읽어 검증한다.**

  ```bash
  find build/issues-242-243/issue-242-candidate-maven-repository \
    -type f \( -name '*.pom' -o -name '*.module' \) -print
  sha256sum build/issues-242-243/issue-242-candidate-maven-repository/io/github/bluetape4k/bluetape4k-dependencies/2.1.0-issue-242.local/*
  ```

  기대 결과: POM dependency-management entries에 version 또는 versioned
  imported BOM이 있고, Module Metadata가 동일 candidate coordinate를 가리킨다.
  누락/순환/다른 version이면 phase를 실패로 기록한다.

## Task 6: `bluetape4k-exposed` 중앙 경로를 검증한다

**Files:**
- Modify only if RED proves required: `../bluetape4k-exposed/settings.gradle.kts`
- Modify only if RED proves required: `../bluetape4k-exposed/build.gradle.kts`
- Modify only if RED proves required: `../bluetape4k-exposed/exposed/timefold-solver-persistence/src/test/kotlin/...`

- [ ] **Step 1: baseline graph를 먼저 실행한다.**

  clean baseline worktree에서 `:bluetape4k-exposed-timefold-solver-persistence:dependencyInsight`
  를 `testRuntimeClasspath`와 네 좌표 각각에 실행한다. 각 결과에서 현재
  선택 version, `Selection reasons`, configuration, output SHA를 receipt에
  기록한다. baseline에서는 `2.4.0`이 선택되어야 한다.

- [ ] **Step 2: candidate catalog/BOM 입력을 주입한다.**

  candidate worktree의 immutable catalog path/ref를
  `-Pbluetape4kDependenciesCatalogPath=<candidate catalog file>` 또는 repository가
  선언한 동일 property로 전달하고, runner의
  `config/issues-242-243-candidate.init.gradle`로 candidate BOM coordinate를
  `testImplementation`에 enforced platform으로 주입한다. `settings.gradle.kts`의
  regular-file/checksum 검증을 우회하지 않는다.

- [ ] **Step 3: candidate graph RED/GREEN을 확인한다.**

  네 좌표가 모두 `2.6.0`과 non-empty `Selection reasons`를 보이는지 runner로
  확인한다. 하나라도 `2.4.0`, `No dependencies matching`, 빈 reason, `SKIPPED`이면
  성공으로 집계하지 않는다. catalog 전달이 실제로 실패하면 Exposed source를
  임의로 복제하지 않고 receipt에 blocker를 기록한다.

- [ ] **Step 4: persistence tests를 실행한다.**

  ```bash
  ./gradlew :bluetape4k-exposed-timefold-solver-persistence:test \
    --no-daemon --no-configuration-cache --no-build-cache --console=plain
  ```

  기대 결과: 기존 score transformer test가 insert → load → equality 경계를
  통과한다. 실패 시 score type, serialization bytes, resolved artifact metadata를
  output에 보존한다.

## Task 7: `timefold-workshop`의 중복 BOM 경로를 제거한다

**Files:**
- Modify: `../timefold-workshop/gradle/libs.versions.toml`
- Modify: `../timefold-workshop/build.gradle.kts`
- Modify only if RED proves required: `../timefold-workshop/01-quickstarts/school-timetabling/...`
- Modify only if RED proves required: `../timefold-workshop/exposed/jdbc-examples/src/test/kotlin/...`
- Modify only if RED proves required: `../timefold-workshop/exposed/r2dbc-examples/src/test/kotlin/...`

- [ ] **Step 1: local BOM override contract을 RED로 고정한다.**

  source contract test 또는 검증 script로 root `build.gradle.kts`가
  `rootLibs.timefold.solver.bom`을 직접 import하지 않고, catalog의 Timefold
  module alias가 versionless인지 검사한다. 기존 `timefold-solver = "2.2.0"`와
  직접 BOM import가 남아 있으므로 RED가 발생해야 한다.

- [ ] **Step 2: 중앙 BOM 단일 경로로 수정한다.**

  local catalog에서 Timefold module aliases의 직접 version source를 제거하고,
  root build의 `mavenBom(rootLibs.timefold.solver.bom.get().toString())`를
  제거한다. 이미 import하는
  `mavenBom(rootLibs.bluetape4k.dependencies.get().toString())`가 해당 constraints를
  관리하는지 확인한다. 중앙 BOM이 constraint를 전달하지 못하면 임시 explicit
  `2.6.0`을 최종 source로 남기지 않고 blocker로 되돌린다.

- [ ] **Step 3: school-timetabling lifecycle을 실행한다.**

  `SolverManager`의 submit/status/terminate 경계가 기존 test와 compile에서
  통과하는지 확인한다. Java 25 toolchain, Kotlin `jvmTarget`, candidate artifact
  `TargetJvmVersion`을 probe하고 세 값이 일치하지 않으면 consumer phase를
  `blocked`로 남긴다.

- [ ] **Step 4: JDBC/R2DBC score persistence를 실행한다.**

  ```bash
  ./gradlew :bluetape4k-timefold:test :school-timetabling:test \
    :exposed-jdbc-examples:test :exposed-r2dbc-examples:test \
    --no-daemon --no-configuration-cache --no-build-cache --console=plain
  ```

  기대 결과: incremental score와 score round-trip이 통과하고, test report의
  `NO-SOURCE` 또는 `SKIPPED`를 성공으로 세지 않는다.

## Task 8: `clinic-appointment` local BOM override와 lock을 정리한다

**Files:**
- Modify: `../clinic-appointment/appointment-solver/build.gradle.kts`
- Modify: `../clinic-appointment/gradle/libs.versions.toml` only if direct version remains
- Modify: `../clinic-appointment/gradle/dependency-locks/*.lockfile` through Gradle resolution
- Modify only if RED proves required: solver/API tests

- [ ] **Step 1: local override RED를 고정한다.**

  `appointment-solver/build.gradle.kts`가 `libs.timefold.solver.bom`을
  `dependencyManagement`에서 import하지 않고 versionless core/benchmark alias만
  사용해야 한다는 contract test를 작성한다. 현재 local BOM import가 있으므로
  RED가 발생한다.

- [ ] **Step 2: root central BOM 경로만 남긴다.**

  appointment-solver의 local Timefold BOM import를 제거하고 root의
  `bluetape4k-dependencies` BOM이 관리하도록 한다. lockfile의 `2.4.0` 문자열을
  일괄 치환하지 않는다. candidate graph가 성공한 뒤 Gradle dependency locking으로
  각 configuration을 재해석하고 lockfile을 갱신한다.

- [ ] **Step 3: clinic candidate test를 실행한다.**

  ```bash
  ./gradlew :appointment-solver:test :appointment-api:test \
    --no-daemon --no-configuration-cache --no-build-cache --console=plain
  ```

  `ConstraintVerifier`, incremental score regression, `SolverService` H2,
  PostgreSQL/Testcontainers, Spring/Jackson serialization 결과를 receipt에
  test task와 output SHA로 기록한다. Docker/Testcontainers 환경이 없으면 해당
  required lane을 pass로 바꾸지 않고 blocked로 남긴다.

## Task 9: baseline/candidate graph와 consumer phase를 receipt에 결속한다

**Files:**
- Modify: `build/issues-242-243/issue-242-receipt.json`
- Modify: `docs/releases/` only when a blocker is found

- [ ] **Step 1: baseline graph phase를 실행하고 output을 보존한다.**

  ```bash
  python3 scripts/run-issues-242-243-validation.py \
    --scope issue-242 --phase timefold-graphs-baseline \
    --repository-map build/issues-242-243/issue-242-repository-map.json \
    --receipt build/issues-242-243/issue-242-receipt.json \
    --execution-boundary persistent-trusted --summary
  ```

  Exposed 네 좌표, Workshop core/Jackson/starter, Clinic benchmark 결과가 모두
  실제 `dependencyInsight` output에 존재해야 한다. baseline과 candidate output은
  별도 path와 digest를 가져야 한다.

- [ ] **Step 2: candidate graph phase를 실행한다.**

  ```bash
  python3 scripts/run-issues-242-243-validation.py \
    --scope issue-242 --phase timefold-graphs-candidate \
    --repository-map build/issues-242-243/issue-242-repository-map.json \
    --receipt build/issues-242-243/issue-242-receipt.json \
    --candidate-maven-repository build/issues-242-243/issue-242-candidate-maven-repository \
    --execution-boundary persistent-trusted --summary
  ```

  모든 required candidate graph가 `2.6.0`을 선택해야 한다. 하나라도 실패하면
  consumers phase를 실행하지 않고 blocker 문서를 만든다.

- [ ] **Step 3: consumers phase를 실행한다.**

  Exposed, Workshop, Clinic의 정확한 test task를 runner allowlist로 실행한다.
  명령 exit code뿐 아니라 test report, resolved artifact, JVM metadata, output
  digest를 확인하고 receipt에 저장한다. `NO-SOURCE`, path-filter skip,
  `SKIPPED`, stale cache는 pass가 아니다.

- [ ] **Step 4: receipt validator와 output digest를 재검증한다.**

  ```bash
  python3 scripts/verify-issues-242-243-receipt.py validate \
    --receipt build/issues-242-243/issue-242-receipt.json --allow-prepared
  ```

  기대 결과: exact catalog SHA, candidate BOM POM/module digest, baseline/candidate
  consumer HEAD, graph selection reason, test output digest가 서로 일치한다.

## Task 10: publisher POM와 central governance를 검증한다

**Files:**
- Modify: `build/issues-242-243/issue-242-receipt.json`
- Modify: `config/central-catalog-version-deltas.json` after all evidence only
- Modify: `config/latest-stable-audit-policy.json` only after adoption decision

- [ ] **Step 1: clean publisher workspace를 확인한다.**

  ```bash
  scripts/verify-publication-poms.py --workspace .. --summary
  ```

  각 publisher POM의 dependency-management entry에 version 또는 versioned
  imported BOM이 있는지 확인한다. dirty `bluetape4k-image` 때문에 전체 실행이
  불가능하면 clean exact worktree 또는 hosted contract를 사용하고, 확인하지 못한
  publisher를 receipt에서 gap으로 남긴다.

- [ ] **Step 2: publication-poms phase를 실행한다.**

  runner가 생성한 POM/effective-model 결과를 실제 file bytes로 검증하고,
  versionless regular dependency가 관리되는지 확인한다. publisher registry,
  workflow, stale POM profile drift가 하나라도 있으면 adoption을 차단한다.

- [ ] **Step 3: central build와 governance suite를 실행한다.**

  ```bash
  python3 -m unittest tests/test_catalog_checksum.py tests/test_central_catalog_version_deltas.py tests/test_ci_catalog_governance.py tests/test_sync_managed_catalog.py tests/test_sync_shared_versions.py tests/test_sync_dependabot_ignores.py
  ./gradlew build --no-daemon --no-configuration-cache --no-build-cache --console=plain
  ```

  기대 결과: central BOM build와 governance test가 통과한다. Gradle만 통과하고
  POM/effective model이 실패한 경우 adoption하지 않는다.

- [ ] **Step 4: delta ledger와 audit policy를 최종 판정한다.**

  모든 필수 evidence가 통과하면 Timefold rollout entry를 `verified`로 바꾸고
  `defer-breaking-migration` 해제 여부를 별도 decision field로 기록한다. 하나라도
  미충족이면 entry를 `validation-pending` 또는 `blocked`로 유지하고 catalog
  adoption을 철회한다.

## Task 11: Type-A 7-Tier review와 변경 범위를 확인한다

**Files:**
- Create: `docs/review/2026-09-09-issue-242-timefold-2.6.0-review.md`
- Modify: affected source files only after review findings

- [ ] **Step 1: Performance/Resilience/Security/Ops/API/Caller 관점을 독립적으로
  기록한다.**

  각 관점에 source, caller, test, ABI/API, docs, CI, design risk, sibling helper
  확인 결과를 적고, `P0` 또는 `P1` finding을 zero로 만든다. graph cache가 결과를
  숨기지 않는지, secret가 command/output에 남지 않는지, mutable ref가 없는지
  receipt evidence로 확인한다.

  별도 7-Tier code review 표에는 (1) source/implementation, (2) callers/consumer,
  (3) tests/fixtures, (4) ABI/API, (5) docs/KDoc, (6) CI/publication contract,
  (7) design/reuse/operational risk를 각각 PASS 또는 근거 있는 BLOCKED로
  기록한다. 하나의 tier가 `SKIPPED`이면 PASS로 집계하지 않는다.

- [ ] **Step 2: Kotlin pattern checklist를 실행한다.**

  `bluetape-kotlin-patterns` 기준으로 불필요한 API 변경, mutable state, 중복
  version source, 테스트 없는 계약 변경을 점검한다. Exposed/Workshop/Clinic의
  기존 helper와 alias를 재사용하고 새 dependency를 추가하지 않는다.

- [ ] **Step 3: self-review와 diff hygiene를 통과한다.**

  ```bash
  git diff --check
  ```

  계획 문서의 미완성 토큰 검사는 결과가 비어 있어야 하며, 각 변경 파일이
  Issue #242 scope에 속해야 한다.

## Task 12: exact-head CI와 PR 준비를 별도 게이트로 둔다

**Files:**
- Modify: none until local evidence is complete
- Create: PR descriptions only after explicit PR gate approval

- [ ] **Step 1: local completion evidence를 고정한다.**

  receipt state를 `validated`로 전환하고, central commit, consumer commit,
  catalog checksum, candidate POM/module SHA, graph/test/POM output digest를
  `docs/releases/2026-09-09-issue-242-timefold-2.6.0-validated.md`에 요약한다.
  evidence가 부족하면 `blocked-evidence` 문서를 만들고 중앙 catalog를
  `2.4.0`으로 되돌린다.

- [ ] **Step 2: PR 생성 전 hosted workflow 계약을 읽는다.**

  `.github/workflows/ci.yml`과 publication POM workflow의 required job,
  path-filter, skip 조건을 확인한다. PR body에는 Korean scope, linked Issue
  #242, exact base/head SHA, receipt path, known gaps, `## DoD Status`를 포함한다.
  PR 생성은 중앙 및 소비자 저장소별로 대상 base/head가 확정되고 사용자 승인이
  있는 경우에만 수행한다.

- [ ] **Step 3: exact-head hosted CI를 검증한다.**

  각 PR의 head SHA를 `gh pr view`와 `gh run view`로 재확인하고 required jobs가
  모두 terminal green인지 확인한다. `SKIPPED`, path-filtered, stale SHA,
  `NO-SOURCE`는 gap으로 기록한다. merge, tag, release, candidate/publication
  dispatch는 이 plan에서 실행하지 않는다.

## Task 13: Issue #242를 evidence와 함께 닫을지 판정한다

**Files:**
- Modify: `docs/releases/2026-09-09-issue-242-timefold-2.6.0-validated.md` or blocked evidence
- GitHub: Issue #242 comment/status only after evidence is complete

- [ ] **Step 1: receipt terminal state를 결정한다.**

  모든 수용 기준과 required hosted CI가 통과하면 `validated`에서 `adopted`로
  CAS transition하고, 그렇지 않으면 `blocked`로 전환한다. `adopted`는 central
  catalog가 실제 `2.6.0`이고 audit policy/delta ledger가 의도적으로 전환된 경우에만
  허용한다.

- [ ] **Step 2: Korean Issue comment를 작성한다.**

  변경된 저장소/commit, graph 좌표별 resolved version과 reason, consumer test,
  POM/effective-model, known gap, 재현 명령, 다음 승인 게이트를 링크한다. 실패
  증거가 있으면 `2.4.0` 보류와 재검토 조건을 명시하고 issue를 닫지 않는다.

- [ ] **Step 3: 정리 전 상태를 보존한다.**

  `git worktree list --porcelain`, `git status --short --branch`, receipt SHA,
  failed output path를 저장한다. 사용자 dirty/default/active/remote worktree는
  삭제하지 않는다.

## 롤백과 복구

| 상황 | 복구 동작 |
| --- | --- |
| catalog checksum mismatch | `gradle/libs.versions.toml`과 sidecar를 마지막 중앙 commit으로 복원하고 candidate artifact/receipt를 보존한다. |
| graph가 `2.4.0`을 선택 | consumer source를 임의로 고치지 않고 candidate catalog path, BOM init script, configuration을 receipt에서 재확인한 뒤 동일 base SHA에서 재실행한다. |
| baseline/candidate HEAD mismatch | 해당 두 worktree를 삭제하지 않고 exact base SHA의 새 clean worktree를 추가해 graph phase만 재실행한다. |
| JVM target 또는 Testcontainers 실패 | test 결과와 환경 증거를 `blocked`로 남기고 catalog adoption을 중단한다. |
| POM/effective model 실패 | Gradle build 성공을 무효로 보고 publication phase를 다시 실행한다. |
| hosted CI가 old SHA를 실행 | PR head와 run SHA를 재고정하고 stale run을 성공으로 세지 않는다. |

## 설계 문서 추적성

| 승인 설계 수용 기준 | 구현 plan |
| --- | --- |
| 중앙 candidate와 immutable identity | Tasks 1, 4, 5, 9 |
| 네 좌표와 selection reason | Tasks 2, 3, 6, 9 |
| Exposed score round-trip | Task 6 |
| Workshop lifecycle/JDBC/R2DBC/JVM metadata | Task 7 |
| Clinic constraint/score/DB/Spring/Jackson | Task 8 |
| publisher POM/effective model | Task 10 |
| fail-closed blocked evidence | Tasks 3, 9, rollback |
| Type-A review와 Kotlin patterns | Task 11 |
| merge/tag/publication 제외 | Tasks 5, 12, 13의 경계 |

## 계획 self-review checklist

- [ ] 각 변경은 exact file path와 RED → GREEN command를 가진다.
- [ ] Issue #243 signing 변경과 관련 repository가 Issue #242 scope에서 제외된다.
- [ ] 기존 combined runner/receipt mode의 회귀 테스트가 있다.
- [ ] `2.4.0` 보류 정책은 모든 필수 증거 전까지 유지된다.
- [ ] `NO-SOURCE`, `SKIPPED`, stale SHA, dirty worktree를 pass로 세지 않는다.
- [ ] local lockfile은 resolution 결과로만 갱신한다.
- [ ] merge, tag, Maven Central publication, workflow dispatch가 실행 단계에 없다.
- [ ] 실패 시 재현 명령과 output digest를 보존하는 rollback 경계가 있다.
