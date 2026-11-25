# Issue #293: Exposed R2DBC DAO catalog alias 교훈

## 배경

`bluetape4k-exposed#942`가 Exposed 1.6.1의 `exposed-dao-r2dbc` 모듈을 사용하려면 중앙 catalog에 해당 외부 artifact alias가 필요했다. 기존 `exposed` 버전 ref는 1.6.1이었고, 다른 Exposed alias도 같은 ref를 사용했다. 별도 version key, BOM constraint, Exposed 소비 저장소의 catalog ref 변경은 이 작업 범위가 아니었다.

## 결정과 적용

- `[libraries]`에 `exposed-dao-r2dbc`를 추가하고 기존 `version.ref = "exposed"`를 사용했다.
- `libs.versions.toml.sha256`를 갱신했다.
- latest-stable authority inventory/audit에 새 coordinate 한 건을 넣었다. 기존 523개 audit record와 개별 조회 시각, pending rollout의 105개 delta, 기존 v4 기준 자료는 보존했다.
- 기존 immutable evidence를 덮어쓰지 않고 새 candidate revision을 추가한 뒤 central pointer를 갱신했다.
- workspace publisher build 파일에 새 accessor나 artifact를 연결하지 않아 publication POM 입력은 바뀌지 않는다. Maven Central 전용 임시 consumer는 generated accessor와 `org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1` 선택을 확인했다.

## 검증 결과

- 전체 Python suite: `Ran 627 tests in 161.049s; OK (skipped=2)`.
- latest-stable authority: 총 524개(관리 생성 325, 정책 67, catalog 직접 132); audit metadata 519 verified, 5 preview-only.
- managed catalog 및 Dependabot ignore 동기화 검사가 통과했다. catalog checksum과 저장소 `./gradlew build --console=plain`도 통과했다.
- 임시 Gradle consumer에서 `libs.exposed.dao.r2dbc`가 1.6.1을 해석했다.
- suite의 별도 transient 확인은 `bluetape4k-core:1.9.2-SNAPSHOT` HTTP 403 때문에 건너뛰었다. 이는 Exposed artifact의 Maven Central 해석 검증과 구분한다.

## 작업 중 놓치기 쉬운 점

- audit, delta ledger, central pointer를 함께 바꾸므로 catalog alias 한 줄만 보지 말고 transaction journal과 immutable candidate 경로까지 확인해야 한다.
- journal 복구를 검증할 때 `python3.13 scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary`는 검사 전에 `recover_catalog_rollout_transaction()`을 호출한다. crash-recovery 회귀는 `tests.test_central_catalog_version_deltas`와 `tests.test_latest_stable_version_deltas`에서 확인한다.
- 새 소비 모듈은 #293 병합 뒤 작업이 승인되면 중앙 catalog의 움직이는 branch가 아니라 병합된 commit SHA와 checksum을 고정해 사용해야 한다.
- native reviewer host가 시작하지 않으면 결과를 독립 승인으로 표시하지 않는다. 이번 독립 code-reviewer 시도는 `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host: host executable was not found`로 정확한 diff를 읽기 전에 종료됐다. workspace workflow가 정한 bounded recovery 뒤에는 inline fallback review를 수행해 코드 리뷰 gate를 해결하고, 별도의 독립 attestation이 없다는 점은 PR DoD에 공개한다.

## 완료 상태

코드와 catalog 검증은 통과했다. 독립 최종 코드 검토는 host 오류로 시작하지 못했으며, 주 세션 inline fallback만 별도 provenance로 기록한다. 코드 리뷰 gate를 fallback으로 통과하고 나머지 검증이 끝나면 승인된 commit과 PR을 진행한다. 병합, tag, publication은 실행하지 않는다. 만료된 실행 receipt는 보존하고 새 session-bound 실행에서 이어간다.

검증 helper는 nested worktree에서 `--workspace ..`로 호출하면 잘못된 경로를 가리키므로 workspace 경로를 명시한다.

## Writer DoD

- [x] **SPW-01 — 근거와 독자 고정:** #293/#942, `2.2.0` milestone과 중앙 catalog 소비자를 확인했다.
- [x] **SPW-02 — 교훈 완결성:** 결정, audit 영향, 검증, 실패 복구, 후속 소비자 순서 및 stop condition을 기록했다.
- [x] **SPW-03 — 한국어 기술 문체:** 설명은 한국어로 쓰고 명령·API·좌표는 원문을 보존했다.
- [x] **SPW-04 — 기술 의미와 추적성:** 성공한 검사와 HTTP 403 skip, inline/independent review provenance를 구분했다.
- [x] **SPW-05 — 최종 read-back:** 문서 구조와 작업 상태가 구현·PR 계획과 일치하는지 확인했다.
