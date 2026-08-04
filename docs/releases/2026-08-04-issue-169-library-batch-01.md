# Issue #169 최신 안정 버전 적용 - library batch 01

이 배치는 2026-08-04 공식 Maven Central metadata를 기준으로, 기존 major 및
명시된 compatibility line을 유지하는 patch 중심 변경만 포함한다.

| authority key | 기존 | 후보 | 호환 line |
| --- | ---: | ---: | --- |
| `jackson3` | `3.2.0` | `3.2.1` | Jackson 3.2 |
| `aws2` | `2.47.1` | `2.47.6` | AWS Java SDK 2.47 |
| `aws-kotlin` | `1.8.0` | `1.8.22` | AWS Kotlin 1.8 |
| `aws2-crt` | versionless | `0.48.3` | standalone latest stable |
| `aws-smithy-kotlin` | `1.6.14` | `1.7.4` | AWS Kotlin 1.8.22 aligned |
| `ktor` | `3.5.1` | `3.5.2` | Ktor 3.5 |
| `netty4` | `4.1.133.Final` | `4.1.136.Final` | Netty 4.1 / Fabric8 |
| `netty4-tcnative` | `2.0.77.Final` | `2.0.78.Final` | Netty 4.1.136 BOM aligned |
| `opentelemetry` | `1.63.0` | `1.64.0` | OpenTelemetry 1.x |
| `vertx4` | `4.5.27` | `4.5.31` | Vert.x 4.5 / Fabric8 |
| `vertx` | `5.1.4` | `5.1.5` | Vert.x 5.1 |
| `classgraph` | `4.8.184` | `4.8.186` | ClassGraph 4.8 |
| `httpclient5` | `5.6.2` | `5.6.3` | HttpClient 5.6 |
| `hibernate` | `7.4.4.Final` | `7.4.5.Final` | Hibernate ORM 7.4 |
| `zstd`, `zstd-jni` | `1.5.7-11` | `1.5.7-12` | zstd-jni 1.5.7 |
| `scrimage` | `4.6.5` | `4.6.7` | Scrimage 4.6 |
| `commons-codec` | `1.22.0` | `1.22.1` | Commons Codec 1.22 |

AWS SDK Java BOM의 최신 2.x minor train, BouncyCastle provider, Netty 4.2,
Vert.x major 통합은 이 배치에 포함하지 않는다. 해당 변경은 별도 호환성 및 보안
검증 없이 자동 적용할 수 없다.

`software.amazon.awssdk.crt:aws-crt`는 AWS SDK v2 BOM에서 관리되지 않는다.
기존 versionless alias는 full `testCompileClasspath`에서 빈 버전으로 실패했다.
AWS CRT는 AWS SDK Java BOM이 관리하지 않고 parent POM 결합도 없으므로
독립 최신 stable `0.48.3`을 중앙 key로 명시한다. 같은 원칙으로 AWS SDK for Kotlin
`1.8.22`가 요구하는 Smithy runtime `1.7.4`로 직접 alias 여섯 개를 정렬한다.

정확한 metadata URL과 before/after 값은
`config/latest-stable-version-deltas.json`에 기록한다.
