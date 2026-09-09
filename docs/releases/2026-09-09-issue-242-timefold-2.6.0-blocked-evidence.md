# Issue #242 Timefold 2.6.0 차단 증거

- 검증일: 2026-09-09
- 범위: 중앙 BOM candidate, `bluetape4k-exposed`, `timefold-workshop`, `clinic-appointment`
- receipt: `build/issues-242-243/issue-242-receipt.json` (중앙 mapping 수정 후 새로 생성)
- receipt state: `blocked` (최신 phase 결과는 receipt의 output digest를 기준으로 판정)
- 이전 receipt의 runner HEAD와 baseline output digest는 Exposed mapping 교정 전 증거로
  보존하며, 최신 receipt가 생성되면 이 문서의 실행 근거를 대체한다.

## 판정

중앙 catalog의 Timefold candidate는 `2.6.0`으로 생성됐지만, 소비자 baseline
graph가 필수 계약을 충족하지 못해 승격을 중단한다. `defer-breaking-migration`
정책과 `validation-pending` delta 상태를 유지하며 candidate graph, 소비자 테스트,
publication POM phase는 실행하지 않았다.

## 재현된 차단 원인

1. `bluetape4k-exposed`의
   `:bluetape4k-exposed-timefold-solver-persistence:dependencyInsight`
   `testRuntimeClasspath`는 `ai.timefold.solver:timefold-solver-core`만 직접
   소비한다. 기존 runner가 benchmark/Jackson/starter까지 Exposed 필수 graph로
   요구한 것은 실제 consumer mapping과 불일치했으므로, 이를 성공으로 만들기
   위해 사용하지 않는 dependency를 추가하지 않고 runner와 receipt 계약을
   Exposed core로 교정했다. 네 좌표 전체 계약은 Workshop의 core/Jackson/starter와
   Clinic의 benchmark를 합친 소비자 graph 합집합으로 유지한다.

2. `clinic-appointment` baseline의
   `:appointment-solver:dependencyInsight`가 `temporal-bom:1.38.0`의
   `.module` 및 `.pom` dependency verification 실패로 종료됐다. 따라서 Clinic
   benchmark의 before version을 증명하지 못했다.

3. `timefold-workshop` baseline은 동일한 clean immutable HEAD에서 다음 좌표를
   모두 `2.2.0`으로 선택했다.

   - `ai.timefold.solver:timefold-solver-core`
   - `ai.timefold.solver:timefold-solver-jackson`
   - `ai.timefold.solver:timefold-solver-spring-boot-starter`

## 안전 조치

- Gradle exit code만으로 성공 처리하지 않고 좌표, 선택 버전, `Selection reasons`,
  output digest를 검증했다.
- semantic graph 실패로 전환된 command에서 성공 cache 증거를 제거하도록 runner를
  수정했다 (`c33b2161121e39ca21f74d4ffef255691f57597c`).
- blocked receipt가 미완료 graph의 pending marker와 실패 output digest를 보존하도록
  validator를 수정했다 (`dd899e1f49a6aaa582664388915322a5bf553a3b`).
- candidate Maven repository와 실패 output은 정리 승인 전까지 보존한다.
- PR, merge, tag, Maven Central publication, workflow dispatch는 실행하지 않았다.

## 재검토 조건

다음 조건을 충족한 뒤 새 receipt에서 baseline부터 다시 실행해야 한다.

1. 소비자별 실제 graph mapping(Exposed core, Workshop core/Jackson/starter,
   Clinic benchmark)과 그 합집합이 중앙 네 좌표를 덮는지 새 receipt에서
   확인한다. 단순히 Gradle exit code 0을 성공으로 바꾸지 않는다.
2. Clinic의 `temporal-bom:1.38.0` verification metadata를 공식 artifact digest로
   갱신하고, 동일한 clean baseline에서 benchmark graph를 재현한다. 현재 공식
   digest는 `.module` `b13301f49c3a502d1f7d60a291e8b317e6bfda6fbd80b50b7aaf3fc83adca885`,
   `.pom` `9f954eccc31c771dbceaa174901f4665e482724e394aaf889dc3a5035fe41435`이다.
3. baseline이 통과한 뒤에만 candidate graph가 합집합 네 좌표 모두에서 `2.6.0`
   을 선택하는지 확인하고, 이어서 Exposed/Workshop/Clinic 테스트와 publisher POM
   검증을 실행한다.

현재 상태는 **BLOCKED**이며, 이 문서는 Issue #242를 닫거나 2.6.0 adoption을
승인하는 근거가 아니다.
