# Issue #293 최종 변경 코드 리뷰

## 판정

Inline verdict: PASS; P0=0, P1=0.

- 주 세션의 전체 diff 검토에서 제품 코드 P0/P1 결함은 발견하지 않았다.
- 독립 최종 코드 리뷰는 수행되지 않았다. native reviewer는 저장소를 읽기 전에 실행 host 오류로 종료했으므로 독립 attestation이 없다.
- workflow의 bounded recovery 뒤 수행한 inline fallback review가 코드 리뷰 gate를 충족한다. 독립 attestation은 없지만, fresh exact-diff 재검토와 나머지 gate가 통과하면 승인된 구현 commit과 #293 PR을 진행할 수 있다.

## 검토 범위와 고정 근거

- 저장소: `bluetape4k-dependencies`
- 기준: `origin/develop` `78a2f525c1d12c576f80f2c8f84dbb2fbb942ede`
- 작업 HEAD: `b97a01148d5d5bd7ba3a634a3d1dafc75b2b5175` 및 승인된 uncommitted 변경
- 검토한 source/catalog/audit diff SHA-256: `8d695439229c9799e696f67b7826731dcc686ace2641874467952c7d58247c70`
- 승인 설계 SHA-256: `66d5ff80642334f1c26eda428dfb8315461cfbce06d30740e5dd1b952996eb78`
- 검토 계획 SHA-256: `1ed8cc4a1ece1702bb5d6d5771f2ef30e819e3f9e22b290d2251fa207a27fcaf`
- 변경 축: central catalog alias/checksum, latest-stable authority/audit/inventory/delta pointer와 새 immutable candidate revision, 회귀 테스트 및 이 작업의 문서 증거.
- 변경하지 않은 축: BOM constraint, published build script, Dependabot ignore list, generated Bluetape catalog block, Exposed 소비자 코드와 catalog ref.

## 여섯 관점

| 관점 | 확인 결과 |
|---|---|
| 성능 | 변경은 Gradle version catalog와 정적 audit 자료다. JVM 실행 코드, 요청 경로 또는 런타임 성능을 바꾸지 않는다. |
| 안정성 | alias 테스트가 TOML module 좌표, 기존 `exposed` ref 및 1.6.1을 고정한다. audit 회귀 테스트는 baseline 523개 record 전체와 조회 시각을 비교하고 신규 Exposed authority만 허용한다. |
| 보안 | 새 artifact 해석은 `mavenCentral()`만 사용하는 임시 consumer로 검증했다. credential, repository URL, runtime dependency 설정은 추가되지 않았다. |
| 운영 | authority 수를 132 direct / 524 total로 함께 갱신했고 새 immutable candidate와 pointer를 사용했다. journal 복구와 cross-file 검증은 기존 helper 및 회귀 테스트가 담당한다. 이전 immutable 기준은 그대로 보존했다. |
| 개발자/API | `exposed-dao-r2dbc`는 Gradle의 `libs.exposed.dao.r2dbc` accessor로 생성되고 `org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1`을 선택한다. 기존 version key와 accessor 계약을 바꾸지 않는다. |
| 사용자/소비자 | #293은 alias를 제공하고 #942는 별도 구현으로 소비한다. #942는 #293 병합 뒤 승인된 catalog commit SHA와 checksum을 고정해야 한다. 현재 작업에서 downstream ref를 움직이지 않는다. |

## 결함과 검증 한계

| ID | 분류 | 내용 | 처리 |
|---|---|---|---|
| REVIEW-P2-01 | 환경 검증 한계 | 전체 Python suite의 transient 확인 한 건이 `bluetape4k-core:1.9.2-SNAPSHOT` HTTP 403 때문에 건너뛰었다. | 별도 경고로 남긴다. Exposed 1.6.1 Maven Central consumer 검증과 혼동하지 않는다. |
| REVIEW-P2-02 | 독립 검토 provenance 한계 | reviewer host `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host`가 없어 독립 verdict를 얻지 못했다. | 결함 없음이나 독립 승인으로 간주하지 않는다. bounded recovery 뒤 inline fallback review를 사용하고, 이 provenance 한계를 PR DoD에도 공개한다. |

## 검증 증거

- Python suite: `Ran 627 tests in 161.049s; OK (skipped=2)`; 위 HTTP 403 예외를 함께 기록한다.
- latest-stable audit: 524 authority, 325 managed-generated, 67 policy, 132 catalog-direct; 519 metadata verified와 5 preview-only.
- managed catalog / Dependabot ignore checks, sidecar checksum, Maven Central consumer 및 `./gradlew build --console=plain`: PASS.
- publication POM gate: N/A. Workspace publisher `build.gradle.kts` 검색에서 새 alias/accessor 사용이 없고, `api(...)` dependency graph에 추가되지 않았다.
- 최신 diff에서 `git diff --check`: PASS.

## 독립 검토 상태

`issue293_final_code_review` 독립 lane은 다음 오류로 저장소 검사 전에 종료됐다.

```text
/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host: host executable was not found
```

따라서 이 문서의 inline 검토는 별도 독립 리뷰로 표현하지 않는다. P0/P1=0은 주 세션 검토에서만 확인한 결과다. 독립 attestation은 unavailable로 남지만 workflow-approved inline fallback이 코드 리뷰 gate를 충족한다. merge·tag·publication은 실행하지 않는다.

## Writer DoD

- [x] **SPW-01 — 근거와 독자 고정:** #293/#942, `2.2.0` milestone, 승인된 catalog 변경과 PR 독자를 확인했다.
- [x] **SPW-02 — 리뷰 계약 충족:** source diff, immutable audit 경계, 테스트, publication POM 영향과 CI 한계를 대조했다.
- [x] **SPW-03 — 한국어 기술 문체:** 한국어 문장과 원문 보존이 필요한 명령·식별자를 구분했다.
- [x] **SPW-04 — 기술 의미와 추적성:** alias 좌표, 버전 ref, checksums, 검증 결과 및 independent-review provenance를 확인했다.
- [x] **SPW-05 — 최종 read-back:** 전체 리뷰 문서와 finding 상태를 다시 읽었다.
