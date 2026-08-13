# Issue #163 다국어 공급망 증거 report-only 계약 설계

## 결정 요약

Issue #163의 목표는 새 dependency 관리 시스템을 만드는 것이 아니라, Kotlin/Gradle,
Go, Python, Rust 저장소가 서로 다른 보안 도구를 실행하더라도 결과를 같은 형식으로
읽고 triage할 수 있게 하는 것이다. 이번 변경은 중앙 저장소에 공통 report envelope와
검증기를 추가하고, 현재 중앙 저장소가 실제로 소유하는 Gradle catalog·publication
증거와 다른 언어 저장소의 소유 경계를 기록한다.

보안 finding의 `review` 또는 `blocked` 상태는 이 단계에서 release를 차단하지 않는다.
CI는 report의 구조·출처·정렬을 검증하지만 finding 상태를 failure로 승격하지 않는다.
두 release train의 운영 자료가 쌓인 뒤에만 별도 승인으로 gate 승격을 검토한다.

## 근거와 범위

| 근거 | 현재 확인한 사실 |
| --- | --- |
| [공급망 경계 연구](https://github.com/bluetape4k/bluetape4k-wiki/blob/develop/research/2026-07-18-bluetape-supply-chain-security-boundary.md) | 공통 필드로 `status`, `affected artifact/module`, `reachable`, `exception expiry`, `evidence URL`을 기록하고 두 train 동안 report-only로 측정하라고 권고한다. |
| [`scripts/audit-latest-stable.py`](../../../scripts/audit-latest-stable.py) | 중앙 catalog authority와 안정 버전의 source/evidence를 현재 저장소에서 감사한다. |
| [`scripts/verify-publication-poms.py`](../../../scripts/verify-publication-poms.py) | downstream publisher의 POM과 Maven effective model을 publication 경계에서 검증한다. |
| [Gradle dependency verification](https://docs.gradle.org/current/userguide/dependency_verification.html) | artifact/metadata checksum·signature 검증은 bootstrap trust를 대신하지 않는다. 현재 중앙 저장소에는 `gradle/verification-metadata.xml`이 없다. |
| [Go vulnerability database](https://go.dev/doc/security/vuln/database) | Go 취약점 결과는 module 버전 목록만이 아니라 호출 경로와 함께 Go 저장소에서 triage해야 한다. |

중앙 저장소에는 Go/Python/Rust 소스가 없으므로 해당 scanner를 이 저장소에 복사하지
않는다. 언어별 저장소는 각자의 dependency graph와 호출 코드를 소유하고, 중앙 저장소는
동일 envelope를 소비·요약하는 책임만 가진다. 두 train 측정 작업은
[#199](https://github.com/bluetape4k/bluetape4k-dependencies/issues/199)에서 별도로
추적한다.

## 정규화 report 계약

기준 파일은 [`config/supply-chain-report.schema.json`](../../../config/supply-chain-report.schema.json)이며,
현재 기준선은 [`config/supply-chain-report-only.json`](../../../config/supply-chain-report-only.json)이다.
최상위 envelope는 다음 필드를 가진다.

| 필드 | 규칙 |
| --- | --- |
| `schema-version` | 현재 `1`만 허용한다. |
| `report-only` | 반드시 `true`다. 이 값이 바뀌면 별도 설계·승인이 필요하다. |
| `train` | `YYYY-MM-DD-<slug>` 형식의 release-train 식별자다. |
| `repository` | report를 생성한 저장소다. |
| `generated-at` | timezone을 포함한 ISO-8601 시각이다. |
| `records` | ecosystem별 정렬된 증거 record 배열이다. |

각 record는 다음 의미를 고정한다.

| 필드 | 의미 |
| --- | --- |
| `ecosystem` | `kotlin-gradle`, `go`, `python`, `rust`, `publication`, `sbom-provenance` 중 하나다. |
| `status` | `pass`, `review`, `not-applicable`, `blocked` 중 하나다. |
| `severity` | `none`, `low`, `moderate`, `high`, `critical` 중 하나다. |
| `affected` | 실제 영향을 받는 `artifact`와 `module`을 함께 적는다. |
| `reachable` | 호출 가능성을 `yes`, `no`, `unknown`, `not-applicable`으로 기록한다. |
| `exception-id` / `exception-expiry` | 예외가 없으면 둘 다 `null`이고, 있으면 ID와 `YYYY-MM-DD` 만료일을 함께 적는다. |
| `evidence-url` | 재현 가능한 HTTPS 근거 링크다. |
| `owner` | triage와 후속 조치를 맡는 저장소/팀이다. |
| `source` | 사용한 도구, 실행 명령, 소스 경로다. |
| `summary` | 현재 상태와 한계를 한 문장으로 설명한다. |

`id`는 stable slug이며 record는 `(ecosystem, id)` 순서로 정렬한다. 그러므로 도구가
바뀌거나 새 train을 추가해도 diff가 deterministic하다.

## 현재 기준선의 소유 경계

| Ecosystem | 중앙 기준선 상태 | 소유자 | 다음 evidence |
| --- | --- | --- | --- |
| Kotlin/Gradle catalog | `pass` — authority audit | `dependency-governance` | catalog audit와 downstream adoption 결과 |
| Gradle verification | `review` — metadata 부재를 기록 | `dependency-governance` | verification metadata 도입 여부와 bootstrap 경계 |
| Publication POM | `pass` — POM/effective model 계약 | `dependency-governance` | publisher별 생성 결과 |
| Go | `not-applicable` — 중앙 저장소 밖 | `bluetape-go-maintainers` | `govulncheck ./...`와 reachable call path |
| Python | `not-applicable` — 중앙 저장소 밖 | `bluetape-py-maintainers` | package audit 결과와 예외 근거 |
| Rust | `not-applicable` — 중앙 저장소 밖 | `bluetape-rs-maintainers` | `cargo audit` 결과와 advisory triage |
| SBOM/provenance | `review` — 두 train 수집 대기 | `release-pipeline` | artifact digest, 서명, attestation 경로 |

`not-applicable`은 안전하다는 뜻이 아니라 현재 report 생성 저장소의 소유 범위가
아니라는 뜻이다. 실제 언어별 결과가 들어오면 같은 record 필드로 교체한다.

## CI와 실패 의미

[`scripts/verify-supply-chain-reports.py`](../../../scripts/verify-supply-chain-reports.py)는
다음 구조 오류를 실패시킨다.

- schema version, `report-only`, 필수 필드, enum, HTTPS URL이 계약과 다름
- 예외 ID와 만료일의 한쪽만 존재함
- 중복 ID 또는 ecosystem/id 정렬 불일치
- timezone 없는 `generated-at` 또는 기준일 이후의 생성 시각

유효한 report 안의 finding은 실패시키지 않는다. 검증기는 summary에 다음 두 목록을
출력해 향후 gate 후보를 분리한다.

1. `severity`가 `high`/`critical`이고 `reachable`이 `yes`인 record
2. 기준일 이전에 만료된 exception record

현재 CI의 `supply-chain-report-only` job은 이 검증기를 실행하고 결과를 `ci-status`에
구조 검증으로만 연결한다. 따라서 malformed evidence는 조기에 수정하지만, `review`
finding은 release-blocking으로 해석하지 않는다.

## 두 train 측정과 승격 조건

두 train 동안 [#199](https://github.com/bluetape4k/bluetape4k-dependencies/issues/199)에
각 report의 경로, 생성 시각, 실행 명령, record 수, `review` 수, 예외 갱신 수, triage
소요 시간을 기록한다. 두 번째 train이 끝난 뒤 다음 중 하나를 결정한다.

- noise와 운영 비용이 예측 가능하지 않으면 report-only를 유지한다.
- evidence URL과 owner가 안정되고 severe reachable/expired exception 처리 절차가
  검증되면 별도 issue와 승인으로 제한적인 failure gate를 설계한다.

어떤 경우에도 checksum만으로 bootstrap trust, snapshot, license, provenance를 해결했다고
주장하지 않는다. 중앙 catalog의 dependency version 변경도 이 설계의 자동 결과가 아니다.

## 수용 기준과 DoD

- [x] 네 언어와 publication/SBOM 경계를 같은 JSON schema로 표현한다.
- [x] `status`, `affected artifact/module`, `reachable`, `exception expiry`, `evidence URL`을 모든 record에서 읽을 수 있다.
- [x] 중앙 저장소의 실제 Gradle/POM evidence와 언어별 소유 경계를 기준선 report로 남긴다.
- [x] malformed contract만 CI 실패로 처리하는 report-only 검증 경로를 추가한다.
- [x] 두 release train의 noise·운영 비용 수집을 [#199](https://github.com/bluetape4k/bluetape4k-dependencies/issues/199)로 등록한다.
- [ ] 두 train 결과를 수집하고 failure gate 승격 여부를 별도 승인한다. 이는 #163의 후속 작업이다.

## Writer DoD

- [x] SPW-01: 독자(의존성·release 유지보수자), 목적, 현재 source path/URL, 미확인 범위를 고정했다.
- [x] SPW-02: 설계의 경계, 계약, 실패 의미, 호환성, 수용 기준, DoD를 포함했다.
- [x] SPW-03: 한국어 technical register를 적용하고 명령·식별자·URL·불확실성을 보존했다.
- [x] SPW-04: wiki 연구, 현재 script, CI 변경과 각 주장·소유 경계를 대조했다.
- [x] SPW-05: Markdown heading/table/code/link를 read-back하고 `git diff --check`로 형식을 확인한다.
