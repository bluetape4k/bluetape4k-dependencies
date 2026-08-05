# dependencies 1.4.0 배포 준비 상태

## 결론

`1.4.0`의 superseding local candidate는 로컬 build, 9개 library downstream full build,
resolved graph 33건, 9개 publication repository의 POM/effective-model 검증을 통과했다.
그러나 Issue #169의 전체 latest-stable audit와 Maven Central publication gate가
끝나지 않았으므로 배포 상태는 **PENDING**이다. 이전 candidate의 remote immutable
commit-ref 검증은 2026-08-05에 통과했지만, superseding local candidate는 아직
catalog bytes는 local commit `b6667cfab4a316ad4fa51eeb1a0c1ed2dddc4749`에
고정됐지만 아직 tag/push되지 않았다.

검증 대상 catalog bytes는 다음 checksum으로 고정한다.

```text
6fb588bd79539fbc48a98bfdaadbacdd10ce5fc9cf659a9b8cd188e8f143dd55
```

## 최신 버전 audit 범위

재현 가능한 `config/latest-stable-version-inventory.json`은 325개 managed-generated
authority와 71개 policy subject, 총 396개의 고유 external version authority를
catalog/policy SHA와 함께 식별한다. `scripts/audit-latest-stable.py --check`는 이
집합이나 입력이 바뀌면 실패한다. 아직 전수 upstream 판정이 끝나지 않았으므로
396개 record 모두 fail-closed `audit-pending`이다.

| 분류 | 수량 | 현재 상태 |
| --- | ---: | --- |
| upstream metadata상 이미 최신 | 164 | 발견 완료, 전수 disposition artifact 미완료 |
| stale로 발견된 일반 key | 200 | 39개 adoption delta만 현재 batch ledger에 기록 |
| 명시적 compatibility line | 27 | 현재 batch에는 Kotlin, AWS CRT, Smithy 등을 포함한 12개 hold/defer 기록 |
| versionless line | 1 | AWS CRT를 AWS Java SDK parent 호환 버전 `0.48.2`로 고정 |
| non-Central/project metadata 필요 | 4 | UCAR/GeoTools 후속 audit 필요 |

`config/latest-stable-version-deltas.json`은 `verified-batch` 상태로 현재 검증 batch의 40개 adoption과
11개 hold/defer만 표현한다. 따라서 이 파일은 396개 전체 inventory의 완료 증거가
아니며, 나머지 key의 fresh evidence와 disposition은 release blocker다.

추가 metadata sweep에서 확인한 Jackson core/Kotlin module `2.22.1`, Feign
`13.13`, OkHttp `5.4.0`, TwelveMonkeys `3.14.0`, Typesafe Config `1.4.9`,
Commons Validator `1.11.0`은 batch 03에서 채택하고 검증했다. Google common
protos `2.74.0`, Gson `2.14.0`, Okio `3.18.1`, RabbitMQ `5.34`, jfalkordb
`0.10`, avro4k `2.12`, Tink `1.23.0`은 별도 호환성 검증이 필요해 명시적으로
보류했다. MaxMind GeoIP2 `5.2.0`은 batch 04에서 전용 테스트와 resolved graph,
9개 downstream full build, publication POM gate를 통과해 채택했다.

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
- Batch 03: Jackson 2 core/Kotlin module `2.22.1`, Feign `13.13`, OkHttp
  `5.4.0`, TwelveMonkeys ImageIO `3.14.0`, Typesafe Config `1.4.9`, Commons
  Validator `1.11.0`
- Batch 04: MaxMind GeoIP2 `5.2.0`

## 호환성 보류와 deferred migration

| 계열 | 현재 | upstream latest | 영향 범위 | disposition / 이유 |
| --- | --- | --- | --- | --- |
| Kotlin | `2.4.0` | `2.4.10` | projects/aws/exposed/graph/text의 `detekt*` task | hold-compatibility: detekt `2.0.0-alpha.5` 실행 호환성 실패 |
| OWASP Dependency Check | `12.2.2` | `13.0.0` | projects/exposed의 `dependencyCheck*` task | defer-breaking-migration: major migration 별도 검토 필요 |
| AWS CRT | `0.48.2` | `0.48.3` | aws `aws-java` compile/runtime, projects testcontainers test runtime | hold-compatibility: AWS Java SDK `2.50.3` parent-tested 버전 유지 |
| Smithy Kotlin | `1.7.4` | `1.7.6` | aws `aws-kotlin` compile/runtime | hold-compatibility: AWS Kotlin SDK `1.8.22` 직접 요구 버전 유지 |

UCAR/GeoTools처럼 Maven Central 외 metadata가 필요한 artifact와 아직 disposition이
없는 stale key는 `hold-unavailable`로 간주하지 않는다. 근거 수집과 분류가 끝나기
전까지는 단순히 **audit 미완료**다.

## downstream 검증 상태

| repository | candidate HEAD | catalog ref | 대표 compile/test | full build | remote immutable ref |
| --- | --- | --- | --- | --- | --- |
| bluetape4k-projects | `13e8cb2` | `b2d0e37` | Jackson/Feign/OkHttp/Config 포함 | 통과, 1,019 tasks | 공통 ref/SHA 검증 통과 |
| bluetape4k-aws | `e9a50c6` | `b2d0e37` | 포함 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-experimental | `8696248` | `b2d0e37` | snapshot consumer platform 보강 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-exposed | `438b34d` | `b2d0e37` | R2DBC 포함 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-graph | `718d3dd` | `b2d0e37` | 관련 regression 포함 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-image | `5f4098b` | `b2d0e37` | TwelveMonkeys 포함 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-javers | `c9d2b87` | `b2d0e37` | JaVers core 포함 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-leader | `50c5b65` | `b2d0e37` | Netty native regression 포함 | 통과 | 공통 ref/SHA 검증 통과 |
| bluetape4k-text | `e5e666f` | `b2d0e37` | 포함 | 통과 | fresh remote fetch 통과 |

아래 표는 이전 remote candidate의 exact downstream HEAD/commit ref 증거다. 이후
GeoIP2 `5.2.0`을 추가한 superseding local candidate는 같은 9개 worktree에서 중앙
catalog path override로 full build를 다시 통과했으며, remote immutable ref 검증은
새 candidate commit/push 전까지 pending이다.

대표 resolved graph에서 확인한 실제 선택 버전은 다음과 같다.

- `io.grpc:grpc-core` -> `1.83.1`
- `org.mongodb:mongodb-driver-core` -> `5.9.1`
- `io.smallrye.reactive:mutiny` -> `3.3.0`
- `software.amazon.awssdk.crt:aws-crt` -> `0.48.2`
- `org.postgresql:r2dbc-postgresql` -> `1.1.2.RELEASE`
- `com.fasterxml.jackson.core:jackson-core` -> `2.22.1`
- `io.github.openfeign:feign-core` -> `13.13`
- `com.squareup.okhttp3:okhttp` -> `5.4.0`
- `com.twelvemonkeys.imageio:imageio-core` -> `3.14.0`
- `com.typesafe:config` -> `1.4.9`
- `com.maxmind.geoip2:geoip2` -> `5.2.0`

publication gate는 9개 repository, 175개 POM, 46,023개 dependency-management
entry, 175개 Maven effective model을 검사했고 failure는 0이었다. Commons
Validator는 9개 downstream에 direct consumer가 없어 catalog와 publication POM
gate로 버전 및 dependency-management 완결성을 검증했다. GeoIP2 채택 후에도 같은
수량의 POM/effective-model gate를 재실행해 failure 0을 확인했다.

candidate map 기준 `sync-shared-versions.py`, `sync-dependabot-ignores.py`,
`sync-managed-catalog.py`는 통과했다. canonical default sibling checkout만 대상으로
실행하면 작업 branch가 아니라 기존 branch를 읽어 adoption gap을 보고하므로, 이
train의 판정에는
[`2026-08-04-issue-169-candidate-receipt.json`](2026-08-04-issue-169-candidate-receipt.json)의
exact worktree/head map을 사용한다. Receipt는 생성된 repository map, catalog lock,
candidate manifest/ledger와 네 개 검증 명령의 output SHA-256을 함께 고정한다.

2026-08-05에는 central branch `issue/169-latest-compatible-stable`을 force 없이
push하고 원격 HEAD가 `924554a3675b3076b8f7b8dcb0f185f3ff730b17`임을 read-back했다.
이어 `bluetape4k-text`의 exact candidate HEAD `e5e666f20a9cf19f1f83e48f481919d08ad46453`를
임시 detached worktree로 만들고, local catalog override와 기존 Gradle cache를
배제한 상태에서 commit ref `b2d0e37c0e7f5046f20e61ca530bf5c5edf5af84`로
`./gradlew help`를 실행했다. 원격에서 받은 catalog SHA-256은 기존 full-build
입력과 동일한 `034ca4c42c98bfb901f49ac88bacb58984c17780c6b44f94d1b275209ad6c71a`였고
Gradle configuration은 `BUILD SUCCESSFUL`이었다. 따라서 이전 9개 full build와
remote ref는 동일 catalog bytes에 결박된다.

## 배포 차단 조건

1. 396개 authority key 전수에 대한 fresh upstream evidence와 explicit disposition
2. 새 local candidate commit 및 downstream immutable ref 이관 후 fresh remote fetch
3. 문서화되지 않은 resolved-graph 변화가 없다는 before/after 비교
4. Maven Central의 기존 stable POM 접근성과 실제 publication credential/dispatch gate

위 조건을 모두 충족하기 전에는 catalog tag, `1.4.0` publication, milestone 종료를
진행하지 않는다.
