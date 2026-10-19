# Issue #1832 Central 구현 7-Tier 리뷰

## 판정

Central 변경에 대한 현재 inline review에서 P0=0, 미해결 P1=0, 미해결 P2=0이다. Projects workflow receipt 결함 P1과 중앙 downstream audit의 authority 선택 오류 P2를 발견했지만 둘 다 테스트를 먼저 실패시킨 뒤 수정했다. 이 판정은 Central PR exact-head CI, catalog tag 발행, Projects 반영, hosted Dependabot 성공을 증명하지 않는다.

## 검토 범위와 기준

- 저장소: bluetape4k/bluetape4k-dependencies, 브랜치 feat/dependabot-standard-catalog, 기준 HEAD e9946b18bdb0022f52cd5dc8994d859d470e7bab 이후의 미커밋 diff.
- 변경 면: repository-map v2, catalog/authority_catalog 정규화, 프로젝트 전용 catalog generator와 receipt/lock, sync-shared-versions의 catalog 선택자, CI Python/parser job 및 대응 테스트.
- 방식: 승인된 inline review. 독립 reviewer 또는 subagent attestation은 주장하지 않는다. 요청 모델은 gpt-6-luna max이며 runtime provenance는 확인하지 않았다.
- 공개 상태: Issue #1832는 OPEN이다. 2026-10-20 live 조회에서 FreeMarker alert #235, GHSA-27j2-h3m2-8237, CRITICAL, first patched version 2.3.35가 OPEN이었다. [GitHub advisory](https://github.com/advisories/GHSA-27j2-h3m2-8237)와 [Apache FreeMarker 2.3.35 릴리스 노트](https://freemarker.apache.org/docs/versions_2_3_35.html)는 이 버전 경계를 뒷받침한다.

## 7-Tier 결과

| Tier | 결과 | 판정 |
|---|---|---|
| 보안 | 대상 좌표는 full commit pinned 설정과 중앙 GAV/alias mapping으로 제한한다. parser receipt는 pinned upstream commit, fixture와 generated catalog 해시, 좌표 결과를 결속한다. canonical path와 non-symlink 검사, 입력 재해시 및 candidate lock 검증이 있다. | 코드 P0/P1=0; live alert/hosted 실행 PENDING |
| 정확성·수명주기 | map v1에서 authority_catalog을 catalog로 정규화해 기존 계약을 유지하고 v2는 source와 generated catalog를 분리한다. Projects 전용 선택자는 Projects 단독 대상에서만 허용한다. dirty/stale HEAD와 경로·SHA 불일치를 거부한다. | P0/P1=0 |
| 구조·재사용 | 직접/간접 map consumer가 공통 normalized loader를 쓰고, build-project-map은 승인된 Central/Projects worktree만 묶는다. Central push audit는 분리된 Projects source catalog를 별도 검사한다. | P0/P1=0 |
| Kotlin API·ABI·공개 계약 | 이 저장소는 관리 도구·workflow 변경만 포함한다. Projects Kotlin/Java production source는 바뀌지 않았고 13개 게시 모듈 POM 및 module.json은 총 26개가 baseline과 byte-identical했다. ABI dump는 N/A. | P0/P1=0; ABI 도구 N/A |
| 테스트·호출자 | Central 전체 Python suite 514 tests PASS, 2 skips. 두 skip은 isolated worktree에서 관리 sibling 저장소가 없어 real-workspace inventory 테스트가 수행되지 않은 것이다. optional 1.9.2-SNAPSHOT artifact 검사도 HTTP 403을 받아 건너뛰었다. 변경된 기존 Python 파일은 baseline과 candidate Ruff finding이 각각 113건으로 같고 새 finding은 0, 새 Python 파일은 0건이다. | 로컬 검증 PASS; skip 범위 공개 |
| 성능 | 303개 원본 alias의 catalog projection 및 제한된 10개 GAV 검증은 작은 설정 입력의 선형 작업이다. generator는 Kotlin runtime path에 추가되지 않는다. 별도 benchmark는 하지 않았다. | 성능 P2 없음 |
| Ops·CI·통합 | Python 3.11/3.13 matrix와 고정된 Dependabot Core parser, exact catalog SHA, workflow parser receipt 계약이 있다. actionlint와 py_compile 통과. Central PR exact-head CI는 아직 실행되지 않았다. | 로컬 workflow 검사 PASS; PR CI PENDING |

## 수정한 리뷰 발견

| 심각도 | 발견 | 수정 및 회귀 근거 |
|---|---|---|
| P1 | Projects CI가 필수 parser receipt를 자기 runner에서 만들지 않아 generator --check가 실패할 수 있었다. | Projects에 full SHA pinned upstream parser checkout 및 contract 실행을 추가했다. contract 테스트 RED 후 수정했고 8개 테스트/actionlint가 통과했다. |
| P2 | Projects catalog split 뒤 Central push-only downstream audit가 생성 catalog를 authority source로 읽을 수 있었다. | Projects의 libs.project.versions.toml이 있으면 Projects만 source catalog 선택자를 쓰고 나머지 저장소는 기본 catalog를 읽도록 분기했다. regression test RED 후 수정하고 전체 Central suite를 실행했다. |

두 발견은 고쳐졌으며 미해결 finding 수에 포함하지 않는다.

## 검증 증거와 남은 제한

- 전체 Central unittest: 514 PASS, 2 SKIP, 221.538초.
- 두 skip: real-workspace inventory 검사에서 managed sibling repositories unavailable. 이는 isolated worktree 범위의 제한이다.
- verify-managed-artifacts의 1.9.2-SNAPSHOT 좌표 bluetape4k-core → io.github.bluetape4k:bluetape4k-core:1.9.2-SNAPSHOT 검사는 HTTP 403으로 건너뛰었다. 이를 테스트 실패나 제품 통과로 분류하지 않는다.
- Central actionlint: PASS. py_compile 및 git diff --check: PASS.
- Ruff: 변경된 기존 파일 12개에서 기준/후보 각각 113건, 새 진단 0건. 새 Python 파일 2개에서 진단 0건.
- 로컬 Ruby 2.6.10/Bundler 1.17.2로 exact pinned parser를 실행하지 않았다. PR CI에서 pinned Ruby action과 upstream commit으로 확인한다.
- GNO/로컬 comparison receipt, Central remote exact-head CI, review/thread read-back은 아직 완료되지 않았다.
- Central merge와 signed tag 발행은 별도 승인 경계다. 이 이후 Projects pin/PR/merge, exact-SHA Dependency Submission, hosted Try again을 진행한다.

## Writer DoD

| 검사 | 결과 |
|---|---|
| SPW-01 목적·독자·근거·미확인 사항 | PASS |
| SPW-02 리뷰 구조·심각도·수정·남은 검증 | PASS |
| SPW-03 한국어 기술 문체 및 용어 일관성 | PASS |
| SPW-04 diff·테스트·alert·advisory 근거 대조 | PASS |
| SPW-05 최종 read-back 및 workflow DoD 기록 | PASS |
| KO-01..KO-06 사실·문체·용어·표·링크 점검 | PASS |
| KO-07 contextual terminology audit | PASS, 최종 audit 결과를 계획에 기록 |
