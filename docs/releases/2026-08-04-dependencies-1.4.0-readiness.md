# dependencies 1.4.0 배포 준비 상태

## 결론

`1.4.0` 후보 catalog의 현재 batch는 로컬 build, 대표 downstream 테스트,
resolved graph 5건, 9개 publication repository의 POM/effective-model 검증을 통과했다.
그러나 Issue #169의 전체 latest-stable audit와 9개 downstream의 exact remote ref
full build가 끝나지 않았으므로 배포 상태는 **PENDING**이다.

검증 대상 catalog bytes는 다음 checksum으로 고정한다.

```text
eec28b1836b9df530545db1a1b74140df4b60e5319a3a0a9825e58e3c4de3093
```

## 최신 버전 audit 범위

2026-08-04 audit inventory는 396개의 고유 external version-authority key를
식별했다.

| 분류 | 수량 | 현재 상태 |
| --- | ---: | --- |
| upstream metadata상 이미 최신 | 164 | 발견 완료, 전수 disposition artifact 미완료 |
| stale로 발견된 일반 key | 200 | 33개 adoption delta만 현재 batch ledger에 기록 |
| 명시적 compatibility line | 27 | 현재 batch에는 Kotlin, AWS CRT, Smithy 등 4개 hold/defer 기록 |
| versionless line | 1 | AWS CRT를 AWS Java SDK parent 호환 버전 `0.48.2`로 고정 |
| non-Central/project metadata 필요 | 4 | UCAR/GeoTools 후속 audit 필요 |

`config/latest-stable-version-deltas.json`은 현재 검증 batch의 33개 adoption과
4개 hold/defer만 표현한다. 따라서 이 파일은 396개 전체 inventory의 완료 증거가
아니며, 나머지 key의 fresh evidence와 disposition은 release blocker다.

추가 metadata sweep에서 확인됐지만 아직 채택/보류 결정을 하지 않은 예로
Google common protos `2.71.0 -> 2.74.0`, Jackson core/Kotlin module
`2.22.0 -> 2.22.1`, Gson `2.13.2 -> 2.14.0`, OkHttp `5.3.2 -> 5.4.0`,
Okio `3.17.0 -> 3.18.1`, Feign `13.12 -> 13.13`, Typesafe Config
`1.4.3 -> 1.4.9`, Tink `1.20.0 -> 1.23.0` 등이 있다. 이들을 현재 batch에
근거 없이 포함하지 않고 후속 family batch와 resolved-graph 검증 대상으로 남긴다.

## 현재 채택 batch

- Gradle plugin: Kover `0.9.9`, Download `5.7.0`, Gatling plugin
  `3.15.1.2`, Jib `3.5.4`, Shadow `9.6.1`
- AWS: Java SDK BOM `2.50.3`, Kotlin SDK `1.8.22`, SDK-parent 호환 CRT
  `0.48.2`, Kotlin SDK 호환 Smithy `1.7.4`
- Runtime/platform: Jackson 3 `3.2.1`, Ktor `3.5.2`, Netty 4
  `4.1.136.Final`, OpenTelemetry `1.64.0`, Vert.x 4 `4.5.31`, Vert.x 5
  `5.1.5`
- Library families: gRPC Java `1.83.1`, Cassandra driver `4.19.3`, Groovy
  `5.0.8`, JaVers `7.11.7`, MongoDB driver `5.9.1`, Mutiny `3.3.0`, R2DBC
  MariaDB/MySQL/PostgreSQL `1.4.1`/`1.4.3`/`1.1.2.RELEASE`, REST Assured
  `6.0.1`, Spring Cloud `2025.1.2`

## 호환성 보류와 deferred migration

| 계열 | 현재 | upstream latest | 영향 범위 | disposition / 이유 |
| --- | --- | --- | --- | --- |
| Kotlin | `2.4.0` | `2.4.10` | projects/aws/exposed/graph/text의 `detekt*` task | hold-compatibility: detekt `2.0.0-alpha.5` 실행 호환성 실패 |
| OWASP Dependency Check | `12.2.2` | `13.0.0` | projects/exposed의 `dependencyCheck*` task | defer-breaking-migration: major migration 별도 검토 필요 |
| AWS CRT | `0.48.2` | `0.48.3` | aws `aws-java` compile/runtime, projects testcontainers test runtime | hold-compatibility: AWS Java SDK `2.50.3` parent-tested 버전 유지 |
| Smithy Kotlin | `1.7.4` | `1.7.5` | aws `aws-kotlin` compile/runtime | hold-compatibility: AWS Kotlin SDK `1.8.22` 직접 요구 버전 유지 |

UCAR/GeoTools처럼 Maven Central 외 metadata가 필요한 artifact와 아직 disposition이
없는 stale key는 `hold-unavailable`로 간주하지 않는다. 근거 수집과 분류가 끝나기
전까지는 단순히 **audit 미완료**다.

## downstream 검증 상태

| repository | candidate HEAD | catalog ref | 대표 compile/test | full build | remote immutable ref |
| --- | --- | --- | --- | --- | --- |
| bluetape4k-projects | `69e551c` | `d6898be` | gRPC, Cassandra, MongoDB, Mutiny 통과 | 미완료 | 중앙 push 전 PENDING |
| bluetape4k-aws | `a1c068d` | `d6898be` | 포함 | 통과 | 중앙 push 전 PENDING |
| bluetape4k-experimental | `e4a7f66` | `d6898be` | 미실행 | 미완료 | 중앙 push 전 PENDING |
| bluetape4k-exposed | `e4a9083` | `d6898be` | R2DBC 통과 | 미완료 | 중앙 push 전 PENDING |
| bluetape4k-graph | `0a574e8` | `d6898be` | 관련 regression 포함 | 이전 batch 통과, exact 최종 batch 미실행 | 중앙 push 전 PENDING |
| bluetape4k-image | `b7d0884` | `d6898be` | benchmark contract regression 포함 | 이전 batch 통과, exact 최종 batch 미실행 | 중앙 push 전 PENDING |
| bluetape4k-javers | `770481c` | `d6898be` | JaVers core 통과 | 미완료 | 중앙 push 전 PENDING |
| bluetape4k-leader | `2ca7ad1` | `d6898be` | Netty native regression 포함 | 이전 batch 통과, exact 최종 batch 미실행 | 중앙 push 전 PENDING |
| bluetape4k-text | `20482d6` | `d6898be` | 포함 | 이전 batch 통과, exact 최종 batch 미실행 | 중앙 push 전 PENDING |

대표 resolved graph에서 확인한 실제 선택 버전은 다음과 같다.

- `io.grpc:grpc-core` -> `1.83.1`
- `org.mongodb:mongodb-driver-core` -> `5.9.1`
- `io.smallrye.reactive:mutiny` -> `3.3.0`
- `software.amazon.awssdk.crt:aws-crt` -> `0.48.2`
- `org.postgresql:r2dbc-postgresql` -> `1.1.2.RELEASE`

publication gate는 9개 repository, 175개 POM, 46,023개 dependency-management
entry, 175개 Maven effective model을 검사했고 최종 재실행의 failure는 0이었다.
중간 재실행 1회에서 AWS Dokka plugin classpath 오류가 발생했으나 동일 AWS task의
단독 실행과 다음 전체 실행은 통과했다. 따라서 결과 수치는 유효하지만 반복 실행
안정성은 release 전 재확인 대상으로 남긴다.

candidate map 기준 `sync-shared-versions.py`, `sync-dependabot-ignores.py`,
`sync-managed-catalog.py`는 통과했다. canonical default sibling checkout만 대상으로
실행하면 작업 branch가 아니라 기존 branch를 읽어 adoption gap을 보고하므로, 이
train의 판정에는
[`2026-08-04-issue-169-candidate-receipt.json`](2026-08-04-issue-169-candidate-receipt.json)의
exact worktree/head map을 사용한다.

## 배포 차단 조건

1. 396개 authority key 전수에 대한 fresh upstream evidence와 explicit disposition
2. 문서화되지 않은 resolved-graph 변화가 없다는 before/after 비교
3. 동일한 exact catalog ref를 사용하는 9개 downstream full build
4. 중앙 commit push 후 remote immutable ref retrieval 검증
5. Maven Central의 기존 stable POM 접근성과 실제 publication credential/dispatch gate

위 조건을 모두 충족하기 전에는 catalog tag, `1.4.0` publication, milestone 종료를
진행하지 않는다.
