# Issue #169 library batch 03

세 번째 batch는 Maven Central의 최신 stable과 upstream BOM/POM을 2026-08-05에
대조한 뒤, 동일 major 또는 parent 정렬이 확인된 외부 라이브러리 계열만 반영한다.

| 계열 | 이전 | 적용 | 정렬 근거 | 대표 검증 대상 |
| --- | --- | --- | --- | --- |
| Jackson 2 core/Kotlin module | `2.22.0` | `2.22.1` | 기존 Jackson BOM `2.22.1` | projects Jackson/HTTP tests |
| Feign | `13.12` | `13.13` | Feign BOM | projects Feign/Geo tests |
| OkHttp | `5.3.2` | `5.4.0` | OkHttp BOM | projects HTTP/Retrofit tests |
| TwelveMonkeys ImageIO | `3.13.1` | `3.14.0` | 공통 parent version | image TIFF tests |
| Typesafe Config | `1.4.3` | `1.4.9` | 기존 1.4 line | projects rule-engine tests |
| Commons Validator | `1.10.1` | `1.11.0` | 기존 1.x line | catalog/POM gate, direct consumer 없음 |

Jackson annotations는 BOM이 선언한 `2.22`를 유지한다. OkHttp `5.4.0` POM이
Okio `3.17.0`을 사용하므로 Okio `3.18.1`은 이 batch에 섞지 않는다.

Google common protos, Gson, Okio, RabbitMQ, MaxMind, jfalkordb, avro4k, Tink은
각각 독립 gRPC/Protobuf graph, 행동 변경, parent 정렬, Micrometer/Jackson graph,
breaking change, Kotlin serialization ABI, 암호화 호환성 검증이 선행되어야 한다.
각 current/latest와 보류 이유는 `config/latest-stable-version-deltas.json`의
`hold`에 기록한다.

## 검증 결과

- 9개 library downstream full build 통과. `bluetape4k-workshop`과 example app은
  검증 범위에서 제외했다.
- OkHttp `5.4.0`의 `Call.addEventListener` 계약을 HC5/Vert.x transport adapter에
  보강하고 lifecycle/clone/cancel 회귀 테스트를 통과했다.
- Spring Cloud OpenFeign `5.0.2` test context는 중앙 catalog의
  `spring-boot-http-converter` alias로 converter wiring을 복구했다.
- published snapshot의 versionless Gradle metadata를 소비하는 experimental
  benchmark 경계에는 `bt4k` catalog 기반 Exposed, Spring Boot, Testcontainers
  platform을 명시했다. repo-local version은 추가하지 않았다.
- 대표 resolved graph 5건과 9개 publication repository의 175개 POM 및 Maven
  effective model을 검증했다. Commons Validator는 direct consumer가 없어 catalog와
  POM gate로 검증했다.
