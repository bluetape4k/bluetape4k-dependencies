# Issue #242 Timefold Solver 2.6.0 전환 보류 증거

## 판정

Timefold Solver `2.6.0` 후보의 필수 소비자 테스트가 모두 통과하지 못했고,
초기 graph phase도 의미 검증 없이 Gradle 종료 코드만 확인한 것으로 재감사됐다.
선택 버전과 `Selection reasons`를 검사하는 semantic graph runner로 재실행한
baseline과 candidate phase도 모두 실패했으므로 중앙 catalog 전환을 보류한다.
`gradle/libs.versions.toml`은 `2.4.0`을 유지하고
`defer-breaking-migration` 정책도 해제하지 않는다.

## 고정한 증거

- semantic graph 검증 구현 HEAD: `1df9d6610c62f86bfed276c720172905bd90a9f4`
- 후보 BOM: `io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local`
- 후보 POM SHA-256: `cd95fc2cb1c53b982a6190653bf017738a2881f73f6acf1be3be2a117e4ab7ad`
- 후보 module metadata SHA-256: `60546a834a448d62f07065823eecdc2d865b2e6037439f14714527694e01b993`
- 후보 Maven repository 전체 manifest phase: 통과,
  `output_sha256=7ce4935f1a2ba0d8c69af98759e63f2e82c878ab718cfaba9d16e4f944ddc2bd`
- 초기 후보 graph runner 결과: `12/12 pass`로 기록됐으나 무효,
  `output_sha256=71034c9db77e04feed9c4704f2b47b4e2701e00c81879d80d10ee592ab0caad2`
- semantic baseline graph phase: 실패,
  `output_sha256=01a0f0212142f4923f2ef4a07104581d26e6ad53f1bbd95c5b7ca4663b940e39`
- semantic candidate graph phase: 실패,
  `output_sha256=fdaf4cf7db15c171b4cb32d46f05b515df7f4f335e596ab5fd5939d6f3a7a7cc`
- 소비자 phase: 실패,
  `output_sha256=9abbd3904d89e1fa0320788917fcb99cc56fdabad4ac457acfde45b48ff8b1f2`

## 보류 원인

### Resolved graph 증거 결함

초기 runner는 `dependencyInsight`가 exit code `0`을 반환하면 통과 처리했다.
보존한 출력을 다시 검사한 결과, 실제 소비하지 않는 좌표에는
`No dependencies matching given input were found`가 포함됐고,
`bluetape4k-exposed`의 후보 core graph는 `2.4.0`을 선택했다. 따라서 위의
`12/12 pass`는 버전 전환 증거로 사용할 수 없다.

runner는 이후 실제 소비 모듈에 좌표를 매핑하고, 선택 버전과
`Selection reasons`를 파싱하며, 후보가 정확히 `2.6.0`을 선택하지 않으면
fail-closed 처리하도록 보강했다. 이 보강 자체는 기존 후보를 통과로 바꾸지 않는다.

재실행 결과도 승격 조건을 충족하지 못했다.

- `bluetape4k-exposed`의 candidate core graph는 예상 `2.6.0` 대신 `2.4.0`을
  선택했다.
- Workshop 검증 worktree는 이미 `2.6.0` 후보로 변경돼 baseline과 candidate가
  모두 `2.6.0`을 선택했다. 이는 독립적인 `2.2.x` 기준선 증거가 아니다.
- Clinic baseline은 검증 worktree가 참조하는 로컬 후보 BOM을 baseline repository에서
  찾지 못해 graph를 만들지 못했다. candidate benchmark graph는 `2.6.0`을 선택했지만,
  대응하는 immutable baseline이 없으므로 전환 증거로 사용할 수 없다.

따라서 일부 candidate graph의 성공을 전체 승격 성공으로 집계하지 않고 두 phase를
모두 실패 상태로 영수증에 보존한다.

### JVM target 불일치

`timefold-workshop`은 Java 21 toolchain을 사용하지만 현재 게시된
`bluetape4k 2.0.0` 및 `bluetape4k-exposed 2.0.0` artifact는 JVM 25 metadata를
요구한다. 다음 명령은 테스트 실행 전에 `testRuntimeClasspath`를 해석하는 단계에서
실패했다.

```bash
./gradlew :bluetape4k-timefold:test :school-timetabling:test \
  :exposed-jdbc-examples:test :exposed-r2dbc-examples:test \
  --no-daemon --no-configuration-cache --no-build-cache --console=plain
```

대표적인 비호환 dependency는
`io.github.bluetape4k:bluetape4k-io:2.0.0`과
`io.github.bluetape4k.exposed:bluetape4k-exposed-dao:2.0.0`이다.
이는 Timefold `2.6.0` 자체의 기능 회귀로 판정할 근거가 아니라, 필수 소비자 검증을
막는 JVM target 계약 불일치다.

## 재검토 조건

다음 조건을 모두 충족하는 별도 migration train에서 #242를 재개한다.

1. `timefold-workshop #54`에서 Java/Bluetape JVM target을 일치시키거나,
   Java 21과 호환되는 동등한 후보 dependency 경로를 제공한다.
2. 동일한 immutable consumer HEAD와 후보 BOM digest를 기록한다.
3. core, benchmark, Jackson, Spring Boot starter의 resolved version과 selection
   reason을 다시 수집한다.
4. Exposed persistence round-trip, Workshop의 증분 점수와 `SolverManager`
   lifecycle, Clinic의 예약 제약·점수 복원·DB 반영 테스트를 모두 통과한다.
5. 통과 후에만 `defer-breaking-migration`을 제거하고 실제 resolved delta를
   `config/central-catalog-version-deltas.json`에 기록한다.

실패 worktree와 local candidate Maven repository는 재현 자료이므로 명시적 정리
승인 전까지 보존한다.
