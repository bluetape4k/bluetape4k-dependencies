# Issue #1832 Central 구현 7-Tier 리뷰

## 판정

현재 code/config head `02df3bf8c74fd507b10a8c0ec30200e910391459`에 대한 inline review는 P0=0, 미해결 P1=0, 미해결 P2=0이다. Projects workflow receipt 결함 P1과 중앙 downstream audit의 authority 선택 오류 P2는 테스트를 먼저 실패시킨 뒤 수정했다. Central PR run `39285492069`에서 발견한 parser P1은 Dependabot Core에 설치된 `toml-rb`를 저장소 루트의 일반 `ruby` 실행이 찾지 못한 문제였다. 수정본은 Core 디렉터리에서 `bundle exec ruby`로 실행하며 workflow 회귀 테스트가 이전 구성에서 RED, 수정 후 GREEN임을 확인했다. code/config head의 Central CI run `39290083993`과 Dependency Submission run `39290088094`가 통과했다. 이 리뷰 문서 갱신은 새 PR head를 만들므로 해당 head의 CI가 아직 남아 있다. 이 판정은 catalog tag 발행, Projects 반영, hosted Dependabot 성공을 증명하지 않는다.

## 검토 범위와 기준

- 저장소: bluetape4k/bluetape4k-dependencies, 브랜치 feat/dependabot-standard-catalog, 기준 develop HEAD e9946b18bdb0022f52cd5dc8994d859d470e7bab부터 최초 PR head `03fdf1417c5dcfba02c2daa2e9572bed74477c04`까지와 후속 수정 후보 diff.
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
| 테스트·호출자 | Central 전체 Python suite 515 PASS, 2 SKIP. 두 skip은 isolated worktree에서 관리 sibling 저장소가 없어 real-workspace inventory 테스트가 수행되지 않은 것이다. optional 1.9.2-SNAPSHOT artifact 검사도 HTTP 403을 받아 건너뛰었다. 변경된 기존 Python 파일은 baseline과 candidate Ruff finding이 각각 113건으로 같고 새 finding은 0, 새 Python 파일은 0건이다. | 로컬 검증 PASS; skip 범위 공개 |
| 성능 | 303개 원본 alias의 catalog projection 및 제한된 10개 GAV 검증은 작은 설정 입력의 선형 작업이다. generator는 Kotlin runtime path에 추가되지 않는다. 별도 benchmark는 하지 않았다. | 성능 P2 없음 |
| Ops·CI·통합 | Python 3.11/3.13 matrix와 고정된 Dependabot Core parser, exact catalog SHA, workflow parser receipt 계약이 있다. 첫 PR CI에서 bundle activation 누락을 발견하고 수정 후보에 `bundle exec`와 회귀 테스트를 추가했다. `actionlint`와 code/config exact-head CI가 통과했다. 문서 갱신 commit의 exact-head CI는 아직 대기 중이다. | 최초 CI parser job FAIL; code/config head PASS; 문서 head PENDING |

## 수정한 리뷰 발견

| 심각도 | 발견 | 수정 및 회귀 근거 |
|---|---|---|
| P1 | Projects CI가 필수 parser receipt를 자기 runner에서 만들지 않아 generator --check가 실패할 수 있었다. | Projects에 full SHA pinned upstream parser checkout 및 contract 실행을 추가했다. contract 테스트 RED 후 수정했고 8개 테스트/actionlint가 통과했다. |
| P2 | Projects catalog split 뒤 Central push-only downstream audit가 생성 catalog를 authority source로 읽을 수 있었다. | Projects의 libs.project.versions.toml이 있으면 Projects만 source catalog 선택자를 쓰고 나머지 저장소는 기본 catalog를 읽도록 분기했다. regression test RED 후 수정하고 전체 Central suite를 실행했다. |
| P1 | Central PR parser job에서 `ruby/setup-ruby`가 `dependabot-core/vendor/bundle`에 설치한 `toml-rb`를 저장소 루트의 일반 `ruby` 프로세스가 불러오지 못했다. run log는 `cannot load such file -- toml-rb (LoadError)`로 끝났다. | workflow parser step의 작업 디렉터리를 `dependabot-core`로 지정하고 `bundle exec ruby "$GITHUB_WORKSPACE/tests/fixtures/project-dependabot-catalog/dependabot-parser-contract.rb"`를 실행한다. 새 workflow 회귀 테스트는 이전 구성에서 RED, 변경 후 GREEN이다. 로컬 `actionlint`와 CI 거버넌스 테스트 24개가 통과했고, pinned parser job은 exact-head run `39290083993`에서도 통과했다. |
| P2 | Projects `develop`의 #1837 커밋 `34c84a6`은 중앙 catalog ref `e9946b1`을 고정하지만 Central consumer policy는 모든 저장소에 `198147f`를 적용했다. run `39285492069`는 `Verify catalog scripts`에서 두 값의 불일치를 보고했고 Gradle `Build BOM` 단계는 건너뛰었다. | 검증 경계를 약화하지 않고 `bluetape4k-projects` 전용 immutable ref override를 추가했다. 설정 계약 테스트는 수정 전 RED, 수정 후 21 PASS이며 실제 workspace verifier와 exact-head hosted `Verify catalog scripts`가 모두 통과했다. |

네 건의 발견을 현재 수정 후보에서 고쳤으며 미해결 finding 수에 포함하지 않는다. code/config head `02df3bf8c74fd507b10a8c0ec30200e910391459`의 CI와 Dependency Submission은 통과했다. 이 리뷰 문서 갱신 commit은 별도 exact-head CI를 요구한다.

## 검증 증거와 남은 제한

- 전체 Central unittest: 515 PASS, 2 SKIP, 182.553초.
- 두 skip: real-workspace inventory 검사에서 managed sibling repositories unavailable. 이는 isolated worktree 범위의 제한이다.
- verify-managed-artifacts의 1.9.2-SNAPSHOT 좌표 bluetape4k-core → io.github.bluetape4k:bluetape4k-core:1.9.2-SNAPSHOT 검사는 HTTP 403으로 건너뛰었다. 이를 테스트 실패나 제품 통과로 분류하지 않는다.
- Central actionlint: PASS. py_compile 및 git diff --check: PASS.
- Ruff: 변경된 기존 파일 12개에서 기준/후보 각각 113건, 새 진단 0건. 새 Python 파일 2개에서 진단 0건.
- 로컬 Ruby 2.6.10/Bundler 1.17.2에서는 exact pinned parser를 실행하지 않았다. 대신 PR CI의 Dependabot Gradle Parser Contract가 pinned Ruby action과 upstream commit으로 run `39290083993`에서 통과했다.
- 최초 PR exact-head run `39285492069`의 parser job은 `toml-rb` `LoadError`로 실패했다. `ruby/setup-ruby`는 Dependabot Core bundle에 gem을 설치했으나 parser script가 Bundler 실행 문맥 밖에서 구동된 것이 원인이다. 공식 [ruby/setup-ruby 사용법](https://github.com/ruby/setup-ruby#usage)은 의존성 설치 뒤 `bundle exec`로 명령을 실행한다.
- workflow 회귀 테스트: 기존 구성에서 RED. 수정 후 `python3.13 -m unittest tests.test_ci_catalog_governance` 24 PASS, `actionlint .github/workflows/ci.yml`, py_compile, git diff --check 통과. Ruff는 수정된 테스트 파일의 기준/후보에서 기존 진단이 각각 3건이며 새 진단은 없다.
- 소비자 pin 회귀 테스트: 수정 전 manifest 계약 테스트 RED, 수정 후 `python3.13 -m unittest tests.test_post_publish_next_development_line` 21 PASS. 전체 Central suite 515 PASS, 2 SKIP이며 실제 workspace 검증기는 publisher 8개, 중앙 catalog를 사용하는 저장소 9개, 개발 버전 catalog 예제 5개를 통과했다. artifact 검사 중 `1.9.2-SNAPSHOT` 조회는 HTTP 403으로 건너뛰었다.
- `ruff check tests/test_post_publish_next_development_line.py`는 I001로 실패했으며 `HEAD`의 같은 파일에서도 동일하게 재현돼 기존 진단이다. py_compile과 `git diff --check`는 통과했다.
- code/config exact head `02df3bf8c74fd507b10a8c0ec30200e910391459`의 Central CI run `39290083993`는 전체 성공했다. `Build BOM`은 12m32s, publication POM contract는 13m18s에 성공했고, 나머지 일곱 job도 통과했다.
- hosted `Build BOM`의 unittest summary는 515 tests, 4 skipped였으며 기본 출력에 skip ID와 사유는 없었다. PR 실행에서는 `Verify downstream repository sync`가 pull request 조건 때문에, 소비자 입력 manifest 생성/업로드는 `develop` push 조건 때문에 실행되지 않았다. 이를 실패로 분류하지 않으며 해당 PR run의 증거 범위에서 제외한다. `1.9.2-SNAPSHOT` artifact 조회는 별도로 HTTP 403으로 건너뛰었다. 실제 Gradle `BUILD SUCCESSFUL`과 consumer policy 검증(8 publishers, 9 catalog consumers, 5 development examples)은 통과했다.
- Cross-repository Publication POM Contract는 9개 저장소, 192 POM 파일, 50,518 dependencies, 192 Maven models, 0 failures였다.
- 같은 head의 Automatic Dependency Submission run `39290088094`는 success다. 앞선 run `39288320776`은 parser 통과 후 더 높은 우선순위 PR merge-ref 요청 때문에 취소됐다.
- run `39290083993` 기준 PR은 OPEN/CLEAN/MERGEABLE이다. review API, inline comment API, issue comment API, GraphQL review threads는 모두 비어 있다. 단일 개발자 lane human reviewer subgate는 N/A다.
- GitHub 공식 [status API](https://www.githubstatus.com/api/v2/incidents/unresolved.json)는 `2026-10-19T16:56:58Z`에 unresolved incidents가 없었다. 해당 run은 그 이후 시작했으므로, 로그 조회 HTTP 404나 job 대기를 이 incident의 원인으로 돌리지 않는다.
- GNO/로컬 comparison receipt는 완료되지 않았다. Central PR merge와 signed tag 발행은 별도 승인 경계다. 이후 Projects pin/PR/merge, merge-SHA Dependency Submission, hosted Dependabot `Try again`을 아직 수행하지 않았다. 현재 live read-back에서 Issue #1832와 alert #235 (`GHSA-27j2-h3m2-8237`)는 모두 OPEN이며 alert 심각도는 CRITICAL이다.

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
