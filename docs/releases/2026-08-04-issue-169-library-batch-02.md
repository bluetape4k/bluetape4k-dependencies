# Issue #169 library batch 02

두 번째 batch는 실제 downstream 소비처와 대표 테스트가 확인된 same-line stable
업그레이드를 묶는다. 생성된 중앙 alias는 개별 repository가 별도 버전을 선언하지 않고
동일한 family 버전을 사용한다.

| 계열 | 이전 | 적용 | 대표 검증 대상 |
| --- | --- | --- | --- |
| gRPC Java | `1.81.0` | `1.81.1` | `bluetape4k-projects` gRPC tests |
| Cassandra Java driver | `4.19.2` | `4.19.3` | `bluetape4k-projects` Cassandra runtime tests |
| Groovy | `5.0.6` | `5.0.8` | catalog graph and publication POM |
| JaVers | `7.11.0` | `7.11.7` | `bluetape4k-javers` tests |
| MongoDB Java driver | `5.7.0` | `5.7.1` | projects/leader Mongo tests |
| Mutiny | `3.2.0` | `3.2.1` | `bluetape4k-projects` Mutiny tests |
| R2DBC MariaDB | `1.4.0` | `1.4.1` | Exposed R2DBC tests |
| R2DBC MySQL | `1.4.2` | `1.4.3` | Exposed R2DBC tests |
| R2DBC PostgreSQL | `1.1.1.RELEASE` | `1.1.2.RELEASE` | Exposed R2DBC tests |
| REST Assured | `6.0.0` | `6.0.1` | downstream test runtime graph |
| Spring Cloud | `2025.1.1` | `2025.1.2` | Spring integration tests |

gRPC Kotlin `1.5.0`과 Google common protos `2.71.0`은 gRPC Java와 독립된
release line이므로 이번 family 치환에서 제외한다. 모든 ledger 항목은 exact catalog
SHA 기반 downstream build와 publication POM 검증 전까지 `pending`으로 유지한다.
