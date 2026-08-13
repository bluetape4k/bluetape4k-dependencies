# Issue #163 report-only 공급망 증거 구현 계획

## 실행 경계

- 작업 유형: Type E — 중앙 governance 문서·검증기 유지보수
- Issue: [bluetape4k-dependencies#163](https://github.com/bluetape4k/bluetape4k-dependencies/issues/163)
- 작업 브랜치: `docs/issue-163-report-only`
- 기준 커밋: `86d1912af5fce89236caca749a046a226af3929a`
- 허용 범위: 격리 worktree의 문서·schema·report-only validator·CI·unit test 변경
- 금지 범위: dependency version 변경, downstream 자동 수정, release/tag/publication, push/PR/merge
- 정상 정지점: 로컬 검증 통과, #163 진행 댓글과 #199 후속 이슈 URL read-back

## 파일 책임과 검증

| 순서 | 파일 | 작업 | 증거 |
| --- | --- | --- | --- |
| 1 | `config/supply-chain-report.schema.json` | strict report envelope와 공통 필드를 선언한다. | schema self-check, JSON parse |
| 2 | `config/supply-chain-report-only.json` | 현재 중앙 Gradle/POM evidence와 언어별 소유 경계를 기준선으로 기록한다. | validator summary, evidence URL read-back |
| 3 | `scripts/verify-supply-chain-reports.py` | 구조 오류는 실패시키고 finding 상태는 report-only로 집계한다. | focused unittest, CLI summary |
| 4 | `tests/test_verify_supply_chain_reports.py` | valid baseline, severe reachable candidate, expired exception, schema drift, 정렬 오류를 고정한다. | `python3 -m unittest ...` |
| 5 | `.github/workflows/ci.yml` | `supply-chain-report-only` job을 `ci-status`에 연결한다. | workflow text assertion, YAML parse/read-back |
| 6 | `docs/superpowers/specs/2026-08-14-issue-163-supply-chain-report-only-design.md` | 소유 경계, gate 의미, 두 train 수집 조건을 공개한다. | SPW-01..05, `git diff --check` |

## 의존 순서와 재실행

1. schema와 baseline report를 먼저 추가한다.
2. validator와 focused tests로 envelope를 고정한다.
3. CI job을 연결하고 기존 `ci-status` 의존성을 read-back한다.
4. 문서의 명령·경로·수량·URL을 실제 파일과 대조한다.
5. 실패 시 변경 파일을 되돌리지 않고 원인을 수정한 뒤 2–4단계를 재실행한다.

## 승인·후속 작업 게이트

- push, PR 생성, merge, tag, release, publication은 이 계획의 허용 범위가 아니다.
- 두 release train의 noise·운영 비용 수집은 [#199](https://github.com/bluetape4k/bluetape4k-dependencies/issues/199)에 등록했다.
- report-only 결과를 failure gate로 승격하거나 언어별 scanner를 중앙으로 옮기는 작업은
  별도 이슈와 새 승인 없이는 시작하지 않는다.

## 계획 DoD

- [x] schema·fixture·validator·unit test의 변경 범위를 고정했다.
- [x] 중앙 저장소에 실제로 존재하는 Gradle/POM 검증과 존재하지 않는 언어별 scanner를 구분했다.
- [x] CI 구조 검증과 finding report-only 의미를 분리했다.
- [x] #199에 두 train 수집 후속 작업을 등록했다.
- [ ] 로컬 전체 검증과 최종 이슈 read-back을 완료한다.
