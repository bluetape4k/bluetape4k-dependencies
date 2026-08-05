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
