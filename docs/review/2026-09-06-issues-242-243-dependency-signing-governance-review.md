# Issues #242/#243 dependency 및 signing governance 구현 리뷰

- 검토일: 2026-09-07
- 구현 기준 HEAD: `1df9d6610c62f86bfed276c720172905bd90a9f4`
- 설계 SHA-256: `eacd4e1fe2c3cb5c839cf313890c26f8cdf8f7c776b13c6d2aadf079617704c2`
- 계획 SHA-256: `1c3d6e89dfd382312d8a2384dec7f929c9d2fe7645d5284b457430990558d056`
- 검토 범위: architecture/reuse, security/operations, performance/API, semantic graph,
  검증 영수증

## 결론

`#243`의 공통 signing helper와 중앙 동기화·검증 경계는 로컬 구현 및 exact-ref
검증을 통과했다. `#242`는 semantic graph와 소비자 테스트가 모두 통과하지 않았으므로
`2.4.0`을 유지하고 `BLOCKED`로 판정한다. 두 판정을 하나의 성공 상태로 합치지 않는다.

## 7-Tier 결과

| Tier | 결과 | 근거 |
| --- | --- | --- |
| 1. Correctness | PASS / #242 BLOCKED | 실제 `dependencyInsight`에서 선택 버전과 `Selection reasons`를 파싱하고 `No dependencies matching`을 실패 처리한다. Exposed candidate core가 `2.4.0`을 선택해 승격을 차단했다. |
| 2. Security | PASS | secret redaction이 환경 변수, Bearer header, query token 및 일반 key assignment를 검사한다. synthetic key/password는 argv에 노출하지 않는다. |
| 3. Reliability | PASS | 전체 90분 budget, child timeout, deterministic failure 보존, candidate cache와 fail-closed receipt 상태 전이를 검증한다. |
| 4. Performance | PASS | baseline은 불필요한 `--refresh-dependencies`를 제거하고 candidate만 refresh한다. 전체 deadline이 cache 조회와 job 제출 전에도 적용된다. |
| 5. API/Compatibility | PASS | 기존 `configurePublishingSigning` 진입점을 유지하고 generated helper에 위임한다. 중앙 catalog는 Timefold `2.4.0`과 defer 정책을 유지한다. |
| 6. Maintainability/Reuse | PASS | repository inventory를 `catalog_candidate.py`의 공통 상수로 통합하고 runner, sync, receipt validator가 재사용한다. |
| 7. Verification/Operations | PASS / remote PENDING | 9개 publisher의 canonical source digest 일치, 188 POM과 49,313 dependency entry의 effective model, Python/Gradle/actionlint/gitleaks를 로컬에서 검증한다. PR 및 exact-head GitHub CI는 아직 실행하지 않았다. |

## 리뷰 지적과 해결

| 우선순위 | 지적 | 해결 |
| --- | --- | --- |
| P1 | graph phase가 Gradle 종료 코드만 보고 실제 좌표·버전을 증명하지 못함 | 실제 소비 module/configuration만 조회하고 좌표, 선택 버전, selection reason, output digest를 검증·기록하도록 변경 |
| P1 | signing digest가 영수증 내부 값끼리만 비교되어 canonical source를 증명하지 못함 | 모든 repository와 consumer digest를 실제 canonical source SHA-256과 비교 |
| P1 | redaction이 `PASSWORD=...`, Bearer header, query token 등을 놓침 | assignment/header/query 형식을 포괄하는 redaction과 회귀 테스트 추가 |
| P1 | phase별 timeout 합계가 전체 90분을 넘을 수 있음 | receipt의 누적 elapsed/remaining budget과 전역 deadline 적용 |
| P2 | candidate cache가 POM/module 일부만 묶음 | 격리된 candidate Maven repository 전체 파일 manifest와 digest 검증 |
| P2 | publisher/repository 목록이 여러 script에 중복됨 | `catalog_candidate.py`의 공통 repository inventory 재사용 |

## 검증 증거

- Python 전체 suite: `384` tests 통과, `2` skipped. 최종 문서 반영 뒤 재실행한다.
- targeted runner: `30` tests 통과.
- receipt validator: `22` tests 통과.
- signing buildSrc phase: 9개 repository 통과,
  `output_sha256=77cccde2e0abd2be31e13f4323377e243453a02ce111d9a083f7bad296de18bd`.
- publication POM gate: 9개 repository, 188 POM, 49,313 dependency entry,
  188 Maven effective model, failure 0.
- Gradle `build`, `actionlint`, `gitleaks`, `git diff --check`: 통과.
- semantic graph: baseline과 candidate 모두 실패 상태로 보존.

## 판정

- `#242`: **BLOCKED** — 독립 baseline 부재, Exposed candidate core `2.4.0` 선택,
  Workshop Java 21과 게시 artifact JVM 25 불일치.
- `#243`: **로컬 DONE / GitHub PENDING** — 공통 helper와 중앙 governance 검증은 통과했으나
  PR 및 exact-head CI는 별도 gate다.
- P0: 0
- 미해결 P1: 0. `#242`의 외부 호환성 차단은 구현 결함을 통과 처리하지 않고 별도
  migration train 조건으로 보존한다.
