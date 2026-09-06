# Issue #242 Timefold Solver 2.6.0 전환 보류 증거

## 판정

Timefold Solver `2.6.0` 후보의 resolved graph는 세 소비자에서 검증됐지만,
필수 소비자 테스트가 모두 통과하지 못해 중앙 catalog 전환을 보류한다.
`gradle/libs.versions.toml`은 `2.4.0`을 유지하고
`defer-breaking-migration` 정책도 해제하지 않는다.

## 고정한 증거

- 중앙 검토 구현 HEAD: `7a05d16d68464b438999da7ed6c43710aed35052`
- 후보 BOM: `io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local`
- 후보 POM SHA-256: `cd95fc2cb1c53b982a6190653bf017738a2881f73f6acf1be3be2a117e4ab7ad`
- 후보 module metadata SHA-256: `60546a834a448d62f07065823eecdc2d865b2e6037439f14714527694e01b993`
- 후보 graph: 12/12 통과,
  `output_sha256=71034c9db77e04feed9c4704f2b47b4e2701e00c81879d80d10ee592ab0caad2`
- 소비자 phase: 실패,
  `output_sha256=9abbd3904d89e1fa0320788917fcb99cc56fdabad4ac457acfde45b48ff8b1f2`

## 보류 원인

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
