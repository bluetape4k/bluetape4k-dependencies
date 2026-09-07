# Issues #242/#243 구현 계획 검토

## 결론

구현 계획은 6개 독립 관점의 재검토에서 모두 `P0=0`, `P1=0`을 충족했다.
따라서 Type A 계획 gate를 통과하며, 구현은 설계와 계획에 적힌 TDD 순서로 진행한다.

| 관점 | 최초 결과 | 최종 결과 | 핵심 확인 |
| --- | --- | --- | --- |
| Architecture | P0 0 / P1 6 | P0 0 / P1 0 | exact worktree map, clean bootstrap, promotion state와 evidence commit |
| Security | P0 0 / P1 3 | P0 0 / P1 0 | secret redaction, release diagnostic, exact-ref CI |
| Stability/Operations | P0 0 / P1 10 | P0 0 / P1 0 | executable CLI, timeout, retry, failure preservation |
| Performance | P0 0 / P1 4 | P0 0 / P1 0 | Timefold scoped resolve, evidence cache, POM deadline |
| User/Caller | P0 0 / P1 3 | P0 0 / P1 0 | 중앙 adapter, consumer graph schema, receipt lifecycle |
| Developer/API | P0 0 / P1 1 | P0 0 / P1 0 | 기존 buildSrc 함수 signature와 실제 smoke fixture 연결 |

## 반영한 차단 지적

### Exact repository와 상태 전이

- moving `origin/develop` 대신 fetch 직후 보존한 exact commit에서 worktree를 만든다.
- 기존 strict repository map으로 중앙 + 9개 catalog repository를 고정한다.
- Workshop과 Clinic은 별도 consumer section에서 exact HEAD를 검증한다.
- state는 `discovered -> prepared -> validated -> adopted` 순서이며 `adopted`는 terminal이다.
- tracked receipt는 검증 중에 갱신하지 않고 local build receipt로 유지한다.
- adopted evidence commit은 branch ref를 움직이지 않은 prospective object로 먼저 만든다.
  final validator 성공 후에만 compare-and-swap ref update를 수행한다.

### Signing 계약과 보안

- generated helper는 sync 도구가 최초 생성부터 소유한다.
- canonical API는 기존 Projects의 public top-level signature를 유지한다.
- 중앙 adapter와 sibling 8개 adapter가 모두 generated helper를 호출한다.
- release diagnostic도 raw armor, escaped newline, Base64 armor와 fallback 계약을 맞춘다.
- synthetic key는 0700 temporary 영역에서 만들고 argv에 key/password를 넣지 않는다.
- redacting wrapper가 stdout/stderr, Gradle log, crash artifact와 build scan을 검사한다.
- smoke fixture는 실제 중앙 adapter/helper/buildSrc를 digest 확인 후 temporary buildSrc로
  주입해 `configurePublishingSigning("maven")` 경로를 실행한다.

### Timefold candidate 검증

- 전체 latest-stable delta를 다시 resolve하지 않고 필수 네 Timefold 좌표만 다룬다.
- Exposed, Workshop, Clinic의 실제 test task와 graph configuration을 runner allowlist로
  고정한다.
- candidate catalog와 고유 local BOM 경로를 별도로 검증한다.
- Clinic의 DB/Testcontainers 전에 candidate POM과 Maven effective model을 검사한다.
- before/after version, selection reason, configuration과 output digest를 consumer별 graph
  record에 저장한다.

### 실행 budget과 복구

- 일반 Gradle 작업은 최대 2 workers, child timeout 600초다.
- POM phase 전체 timeout은 1800초이고 전체 local validation budget은 90분이다.
- Gradle cache는 끄되 exact input 기반 runner evidence cache로 중복 실행을 생략한다.
- deterministic failure는 dependent task를 취소하고 0600 redacted artifact를 보존한다.
- 성공한 임시 자료만 exact target과 digest를 확인한 뒤 정리하며 실패 자료는 보존한다.

## 최종 gate

- P0: 0
- P1: 0
- 계획 문서 `git diff --check`: 통과
- placeholder scan: 통과
- 한국어 문체 scan: 통과
- 구현 시작 조건: 충족

PR, push, merge, tag, workflow dispatch와 Maven Central publication은 승인 범위 밖이므로
계획과 구현 DoD에서 `N/A`로 유지한다.
