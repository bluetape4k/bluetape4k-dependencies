# 2026-09-04 catalog version refresh downstream evidence

후보 catalog SHA-256은
`622761bc3e518f052fe769c7fa057b3e1ec0cacd22ad9a871a9d1d8157120e0a`이며,
모든 검증은 후보 파일
`/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/chore/catalog-version-refresh/gradle/libs.versions.toml`
을 `BLUETAPE4K_DEPENDENCIES_CATALOG_PATH`로 주입해 수행했다. 각 저장소의
작업트리는 실행 후 clean 상태였다.

## Exact HEAD 결과

| 저장소 | HEAD | 결과 | 테스트/비고 | 로그 |
| --- | --- | --- | --- | --- |
| `bluetape4k-projects` | `0be7daa7a6d98937126486ff4b84a76e416696d6` | `PENDING` | 전체 build가 `:bluetape4k-lettuce:multiKeyLeasePerformanceTest`의 normalized p95 비율 assertion에서 중단됨. 후보 재실행 3회 중 2회 성공·1회 실패(`13.390084 ≤ 3.6915` 위반); 기준 catalog도 3회 중 2회 성공·1회 compile 환경 실패 | context-mode 실행 출력 및 아래 targeted 재검증 |
| `bluetape4k-aws` | `b564319bd6a6f37475fcf628071ac642131da1d7` | `PASS` | 3,285 tests executed, 34 skipped | `build/next-wave-aws-full-build.log` (`713ae5a0e107ea1c822f1ec69b0b4f7187723ed79e539f873e8bdf33412539dc`) |
| `bluetape4k-experimental` | `2698545c693d781b415b3bdcf5f6c468875ec40e` | `PASS` | 71 tests executed | `build/next-wave-experimental-full-build.log` (`62f9ef63baae52fe6eaf89aafec1582115ab92974b740477bab008d5508c4`) |
| `bluetape4k-exposed` | `85aae98d7a69925cd92f406ac7d0f29cd5d9ea46` | `PENDING` | 4,934 tests executed, 230 skipped 뒤 PostgreSQL test worker가 0 tests로 9분 정지하고 SIGTERM(Colima/Testcontainers JDBC handshake) | `build/next-wave-exposed-full-build.log` (`7deb224f9e6043afd73cb8275e2bea8c82a09f176334bbd1eee4abfdbb6c9798`) |
| `bluetape4k-graph` | `ca21bad1ec90d97d1f98d8e9b70894eed714f4ed` | `PENDING` | 전체 build의 AGE PostgreSQL JDBC 초기화가 EOF로 1회 실패했으나 동일 `AgeRecommendationSuspendTest` 3회 재실행은 모두 성공 | 전체 `build/next-wave-graph-full-build.log` (`07e5e82906de9b24cac87fb8bb405466196fe27c806d7b50d7dc30d6ca14ae03`), 재검증 `build/next-wave-graph-age-recheck.log` (`3a5df0d738c8b68b0ce314e52eafb20415776f0f234ca1908389e141a085ad83`) |
| `bluetape4k-image` | `b5cc7dc08fa01409ccdb90e8f281227ec7e22bb8` | `PASS` | `BUILD SUCCESSFUL`; 18 test task up-to-date, consumerTest 1 skipped | `build/next-wave-image-full-build.log` (`552fff81b7ad9af97583c24acb3d51207cad3cf3ba76608f998572f5c1202105`) |
| `bluetape4k-javers` | `8d7d822918652b37f598741fded46629a600d166` | `PASS` | 486 tests executed | `build/next-wave-javers-full-build.log` (`eafdb4e76954bb4be87f48db5878908ef42e1b754672b434da351760e23f9be6`) |
| `bluetape4k-leader` | `b22f88ccaf8d531e4cc2eb0854daa78f9b423756` | `PASS` | 4,239 tests executed | `build/next-wave-leader-full-build.log` (`42ece51076c67425a4b601b763743bcfb211986c1cdc7dcdddc7fa47c43b6680`) |
| `bluetape4k-text` | `47bd772c791fbe60e8f5a355b14cae35970f1bdf` | `PASS` | `:test` 8개 up-to-date | `build/next-wave-text-full-build.log` (`d1114eaae5787910d0d01268a8731963514ba5ff944fa1ca336322c7cd5d31f3`) |

## 분류

- Graph AGE 실패는 PostgreSQL container mapped-port/handshake readiness 문제이며,
  catalog 변경과 무관한 재현성 낮은 환경 flake로 분류한다.
- Projects Lettuce 실패는 `lettuce = 7.6.0.RELEASE`를 유지한 후보와 기준 catalog에서
  모두 관찰된 normalized p95 성능 assertion flake다. 성능 기준 자체를 완화하거나
  격리된 실행 환경을 도입하는 별도 Projects 이슈가 필요하다.
- Exposed 실패는 테스트가 실행되기 전 Testcontainers JDBC handshake가 정지한
  환경 blocker다. 재실행 가능한 Colima/Testcontainers 상태에서 Full Nightly를
  다시 수행하기 전에는 catalog 승격을 완료로 표시하지 않는다.

## 실행 명령

```shell
BLUETAPE4K_DEPENDENCIES_CATALOG_PATH=<candidate>/gradle/libs.versions.toml \
  ./gradlew build --no-daemon --no-configuration-cache --no-build-cache --console=plain
```

Projects targeted performance 재검증은 위 명령에서
`:bluetape4k-lettuce:multiKeyLeasePerformanceTest --rerun-tasks`만 실행했으며,
후보 3회와 기준 catalog 3회의 결과를 비교했다.
