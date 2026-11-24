# PR #291 인라인 fallback 코드 리뷰

## 범위와 근거

- 저장소: `bluetape4k-dependencies`; PR #291, base `develop`.
- 검토 기준: remote PR head `0d3816359137e740b9895e25db81f4d6b9ba1d57`와 이
  worktree의 로컬 보정 diff. 보정 diff는 아직 원격 PR head의 CI에 포함되지 않았다.
- 검토 범위: 다음 개발선 BOM/catalog, `post-publish-next-development-line`
  manifest 및 verifier, 관련 회귀 테스트, 한·영 README와 WIP, release checklist와
  버전 관리 문서. Kotlin/Java API나 publisher workflow를 변경하지 않는다.
- 최신 release 기준: Dependencies/Projects/Exposed `2.1.0`, 나머지 6개 child
  BOM `1.1.0`. 후보는 Dependencies/Projects/Exposed `2.2.0-SNAPSHOT`, 나머지
  child `1.2.0-SNAPSHOT`을 설정한다.
- 사용자 범위: 단일 maintainer `debop`. 사람 리뷰 subgate는
  `N/A (single-developer lane)`로 기록할 수 있지만, exact-head CI, live
  reviews/threads 확인, 코드 리뷰와 publication-POM gate는 그대로 적용한다.

## 발견 사항과 처리

### P1 — verifier manifest가 consumer catalog ref와 불일치

- 증거: `config/post-publish-next-development-line.json:71`의
  `consumer-policy.snapshot-catalog-ref`는 이전 SHA
  `7a5995fd46031ce1faf16337fa08d954436f8f9a`를 가리켰지만, 9개 consumer의
  Settings/CI와 `catalog/2026-11-24-01`은
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`를 사용한다.
- 영향: post-publish verifier가 새 consumer 후보를 거부하고, snapshot 후보
  branch를 이전 catalog ref에서 파생할 수 있었다.
- 처리: manifest 값을 `c44ec6c…`로 변경하고
  `tests/test_post_publish_next_development_line.py:242`의 ref 기대값과
  `:291`의 candidate branch 기대값을 새 SHA에 맞췄다.
- 상태: 수정 후 집중 테스트 32개가 통과했다. 이 변경은 이전 live PR head의 CI
  결과에 포함되지 않았으므로, 새 exact-head CI와 publication-POM gate는 별도로
  확인해야 한다.

### P1 — README가 미게시 stable Dependencies 버전을 안내

- 증거: 영문·한국어 README의 버전 예시는 child BOM들을 `-SNAPSHOT`으로
  표시하면서 중앙 `bluetape4k-dependencies`만 `2.2.0`으로 적었다. 현재 공식
  중앙 버전은 `2.1.0`이고 `2.2.0` stable artifact는 아직 게시되지 않았다.
- 영향: 예시를 그대로 적용하는 소비자 저장소는 Maven Central에 없는 정식 버전을
  요청할 수 있고, 같은 예시 안의 다음 개발선과도 어긋난다.
- 처리: 두 README locale의 중앙 version alias를 `2.2.0-SNAPSHOT`으로 맞췄다.
- 상태: 로컬 소스 대조에서 두 locale의 version line이 일치한다. 새 exact-head
  CI와 최종 문서 read-back은 계속 필요하다.

## 아키텍처 검토

- 중앙 `bluetape4k-dependencies`는 version catalog를 내부 BOM의 입력으로 사용하고,
  `build.gradle.kts`에서 Projects, AWS, Image, Text, Graph, Leader, Exposed,
  JaVers BOM을 `api(platform(...))`로 가져온다. 따라서 central snapshot은 여덟 child
  BOM이 Maven Central에 보인 뒤에 게시해야 한다.
- consumer Settings/CI와 중앙 verifier policy가 같은 immutable catalog commit
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`을 가리키고, Projects CI는 signed tag
  object와 tag 이름도 검증한다. 서로 다른 consumer catalog 입력은 허용하지 않는다.
- catalog ref 변경은 내부 Gradle build contract이며 BOM release version과 별도다.
  stable consumers는 published Dependencies `2.1.0`을 계속 사용하고, snapshot
  verifier만 개발선 alias `2.2.0-SNAPSHOT`을 허용한다. `baseVersion=2.2.0`과 빈
  `snapshotVersion=`은 workflow가 최종 suffix를 넣도록 유지한다.
- Publisher DAG는 Projects → Exposed → AWS → Graph → Image → JaVers → Leader →
  Text → Dependencies 순서로 실행한다. 각 선행 publisher의 metadata/POM/GMM을
  확인한 뒤 다음 publisher의 Full Nightly를 실행한다. 성공한 Nightly가
  Publish Snapshot을 자동 실행하므로 manual dispatch를 사용할 이유가 없다.
- 아키텍처 미해결 P0/P1: 없음. 단, 전체 publisher POM/effective-model 검증과 새
  catalog ref의 공개 snapshot read-back은 아직 pending이라 출시 준비 완료 판정에는
  사용할 수 없다.

## 나머지 검토

- 개발 BOM self alias `2.2.0-SNAPSHOT`, source `baseVersion=2.2.0` 및 빈
  `snapshotVersion=` 계약, child BOM version, official consumer 경계가 서로
  일치한다.
- verifier는 개발선 self alias에 `-SNAPSHOT`을 요구하고 stable 경계에서는
  snapshot catalog/self alias를 거부한다. 회귀 테스트는 허용·거부 경계를 모두
  검사한다.
- shared catalog SHA sidecar, release consumer와 snapshot consumer의 분리, 9개
  candidate Settings/CI pin은 확인했다. 새 signed catalog tag의 remote object와
  peeled commit도 서로 일치한다.
- 미해결 P0/P1/P2/P3: 없음. 앞서 발견한 P1은 해결했다.

## 검증과 한계

- `python3.13 -m unittest tests.test_post_publish_next_development_line tests.test_latest_stable_version_deltas`: 32개 PASS.
- `python3.13 -m py_compile scripts/verify-post-publish-next-development-line.py tests/test_post_publish_next_development_line.py tests/test_latest_stable_version_deltas.py`: PASS.
- `git diff --check`: PASS.
- Ruff lint 진단은 `origin/develop`과 후보가 동일했다. verifier script 15건,
  verifier test 1건, delta test 0건이며 이번 변경으로 진단 수가 늘지 않았다.
  포맷 검사는 기존 세 파일이 `origin/develop`에서도 이미 실패한다. 추가된
  workspace fixture의 새 줄은 formatter 결과에 맞췄다.
- 이전 head `0d38163`의 hosted CI 10개 check는 PASS했으나, manifest 보정 전
  결과다. 새 head의 CI와 전체 publisher POM/effective-model 검증은 pending이다.
- GitHub live read-back에서 PR #291 review submission, inline thread, issue
  comment는 0개였다.
- native reviewer와 architect 역할은 설치된 `codex-code-mode-host` 실행 파일
  부재로 verdict를 내지 못했다. Claude Code도 조직 설정이 subscription access를
  차단해 독립 verdict를 제공하지 못했다. 이 문서는 main session의 inline
  fallback이며 독립 리뷰 attestation이 아니다.

## 판정

**코드 리뷰: PASS (inline fallback; 독립 attestation 아님).** 해결되지 않은
P0/P1은 없다. **아키텍처 검토: CLEAR (main-session pass; 독립 attestation 아님).**
전체 publisher POM/effective-model 검증, 후속 consumer snapshot train, 새
exact-head CI와 최종 merge hold가 끝날 때까지 PR merge는 대기한다.
