# Issue #242 Timefold 2.6.0 차단 증거

- 검증일: 2026-09-09
- 범위: 중앙 BOM candidate, `bluetape4k-exposed`, `timefold-workshop`, `clinic-appointment`
- baseline evidence runner HEAD: `dd899e1f49a6aaa582664388915322a5bf553a3b`
- receipt: `build/issues-242-243/issue-242-receipt.json`
- receipt state: `blocked`
- baseline phase output SHA-256: `dd02d3e0d7de28b5017f055113430084d70c439bda1aaf255509edfcb5c34d59`

## 판정

중앙 catalog의 Timefold candidate는 `2.6.0`으로 생성됐지만, 소비자 baseline
graph가 필수 계약을 충족하지 못해 승격을 중단한다. `defer-breaking-migration`
정책과 `validation-pending` delta 상태를 유지하며 candidate graph, 소비자 테스트,
publication POM phase는 실행하지 않았다.

## 재현된 차단 원인

1. `bluetape4k-exposed`의
   `:bluetape4k-exposed-timefold-solver-persistence:dependencyInsight`
   `testRuntimeClasspath`에서 다음 좌표가 존재하지 않았다.

   - `ai.timefold.solver:timefold-solver-benchmark`
   - `ai.timefold.solver:timefold-solver-jackson`
   - `ai.timefold.solver:timefold-solver-spring-boot-starter`

   Gradle은 해당 `dependencyInsight` 명령을 exit code 0으로 종료했지만,
   runner의 semantic parser는 `No dependencies matching given input`을 실패로
   기록했다. 이 결과를 성공 graph로 집계하지 않았다. 각 실패 output digest는
   receipt의 baseline `failure_record`와 command record에 보존돼 있다.

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

1. Exposed에서 네 필수 좌표를 실제 consumer runtime에 매핑하거나, 실제 사용하지
   않는 좌표를 필수 graph 계약에서 제외하는 설계 결정을 명시한다. 단순히 Gradle
   exit code 0을 성공으로 바꾸지 않는다.
2. Clinic의 `temporal-bom:1.38.0` verification metadata를 공식 artifact digest로
   갱신하고, 동일한 clean baseline에서 benchmark graph를 재현한다.
3. baseline이 통과한 뒤에만 candidate graph가 네 좌표의 `2.6.0` 선택을 보이고,
   이어서 Exposed/Workshop/Clinic 테스트와 publisher POM 검증을 실행한다.

현재 상태는 **BLOCKED**이며, 이 문서는 Issue #242를 닫거나 2.6.0 adoption을
승인하는 근거가 아니다.
