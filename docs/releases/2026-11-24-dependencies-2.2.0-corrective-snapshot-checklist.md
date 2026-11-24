# Dependencies 2.2.0-SNAPSHOT catalog 보정 체크리스트

상태: **진행 중 — 기존 하위 snapshot 산출물은 이전 catalog ref 기준이며, 보정 ref로 재검증·재게시해야 함**

## 고정 입력

- 대상: `io.github.bluetape4k:bluetape4k-dependencies:2.2.0-SNAPSHOT`
- 최신 정식 버전 read-back: Dependencies, Projects, Exposed `2.1.0`; AWS,
  Graph, Image, JaVers, Leader, Text `1.1.0`. GitHub 최신 release tag와 Maven
  Central POM을 2026-11-24에 확인했다. Central Dependencies `2.1.0` POM은
  직접 fetch에서 HTTP 200이며, 현재 Dependencies `2.2.0-SNAPSHOT` metadata는
  게시 전 상태인 HTTP 404다.
- 목표 child snapshot: Projects/Exposed `2.2.0-SNAPSHOT`; AWS, Graph, Image,
  JaVers, Leader, Text `1.2.0-SNAPSHOT`.
- 대상 authority: 사용자의 현재 지시와 앞서 승인한 next-development snapshot
  train. 정식 `2.2.0` 배포는 이 작업 범위가 아니다.
- 공통 catalog ref: 기존 `7a5995fd46031ce1faf16337fa08d954436f8f9a`는
  사용하지 않는다. 새 immutable ref는 이 보정 commit에서 생성하며 tag 이름은
  `catalog/2026-11-24-01`로 고정한다. 2026-11-24 read-back에서 이 원격 tag는
  아직 없었다. 새 commit SHA와 annotated tag object SHA는 생성 후 이 문서와
  모든 consumer에 동일하게 기록한다.
- consumer 범위: Projects, AWS, Experimental, Exposed, Graph, Image, JaVers,
  Leader, Text. 모두 Settings와 CI가 같은 새 commit SHA를 사용해야 한다.
  Projects CI의 catalog tag와 annotated tag-object pin도 새 값으로 바꾼다.
- 정식 release consumer 5개(Workshop, Clinic, Timefold Workshop, Exposed R2DBC
  Workshop, Exposed Workshop)는 공식 Dependencies `2.1.0` 및 기존 안정 catalog
  `1669b069690864be8a19a67598e9ac9db807f9f5`를 유지한다.

## 게시 순서 및 hold

1. 중앙 catalog self alias를 `2.2.0-SNAPSHOT`으로 바꾸고 개발선 verifier가
   source `baseVersion=2.2.0`, 빈 `snapshotVersion=`, runtime suffix
   `-SNAPSHOT`을 함께 검증하도록 고친다. Stable verifier는 snapshot alias를
   계속 거부해야 한다.
2. 새 catalog SHA/tag를 고정한 다음 9개 consumer의 Settings/CI 참조를 모두
   같은 SHA로 갱신하고 exact-head CI 및 merged develop ref를 확인한다.
3. 8개 publisher의 POM을 새 catalog로 생성하고 Maven effective model 검증을
   통과시킨다.
4. 하위 BOM DAG를 지킨다: Projects → Exposed → AWS, Graph, Image, JaVers,
   Leader, Text. 각 publisher는 선행 artifact의 Central metadata, POM,
   Gradle module metadata를 확인한 뒤 Full Nightly를 실행한다.
5. `Publish Snapshot`은 해당 Nightly 성공 후 자동 실행만 허용한다. 수동
   `publish-snapshot.yml` dispatch는 하지 않는다. 중앙 Dependencies snapshot은
   8개 child snapshot 공개와 #291 병합 후 중앙 `develop` CI 성공으로 자동
   실행한다.
6. 모든 child/central artifact metadata, POM, Gradle module metadata를 다시
   읽고 `verify-post-publish-next-development-line.py --require-artifacts`,
   전체 publication-POM gate, consumer SHA parity를 통과시킨다.

## 기존 train과 보정 범위

- 기존 체크리스트 `2026-11-22-dependencies-2.2.0-development-checklist.md`의
  release·snapshot 이력은 당시 증거로 보존한다. 그 문서의
  `catalog/2026-11-22-01` / `7a5995…` 기준 child snapshot은 이 보정 train의
  완료 증거로 재사용하지 않는다.
- PR #291은 현 시점 OPEN, 기존 head
  `a9cac1c64ce0554ead98a0f36cd5f39e2c1b9222`다. 보정 catalog 및 verifier가
  같은 PR에 반영된다. merge 직전 정확한 head의 checks, review/thread, mergeability,
  승인 상태를 다시 읽는다.
- Projects #1915와 Experimental #103은 action version만 변경하는 OPEN PR이다.
  catalog ref 행을 수정하지 않으며, consumer 보정 PR과 함께 현재 mergeability를
  다시 확인한다.

## 완료 확인

- [ ] Catalog self alias, verifier, 회귀 테스트, checksum sidecar, stable 경계
- [ ] `catalog/2026-11-24-01` immutable tag, commit SHA 및 tag-object SHA read-back
- [ ] 9개 consumer 모두 같은 SHA를 Settings/CI에서 사용; Projects tag pins 일치
- [ ] 모든 consumer PR exact-head CI와 merged `develop` read-back
- [ ] 전체 publisher publication-POM 및 Maven effective-model gate
- [ ] 8개 child snapshot DAG, Full Nightly, 자동 Publish Snapshot, artifact read-back
- [ ] PR #291 exact-head checks/reviews/threads/독립 리뷰 및 guarded merge
- [ ] Dependencies `2.2.0-SNAPSHOT` 자동 publish와 Central artifact read-back
- [ ] 최종 verifier `--require-artifacts`, POM gate 및 9개 consumer SHA parity

## 2026-11-24 후보 로컬 검증

- `tests/test_post_publish_next_development_line.py`: 22개 PASS. `2.2.0-SNAPSHOT`
  self alias 허용과 정식 verifier의 snapshot 거부 경계를 검증했다.
- `tests.test_catalog_checksum`: 2개 PASS.
- `scripts/audit-latest-stable.py --check --check-audit --audit-summary`:
  PASS — authority 523, metadata verified 518, preview-only 5, unavailable 0.
- `python3.13 -m py_compile ...` 및 `git diff --check`: PASS.
- `./gradlew build`: BUILD SUCCESSFUL. Gradle 10 호환성 관련 기존 deprecation
  안내가 출력됐으며 빌드는 통과했다.
- 이 로컬 검증은 PR #291의 새 exact-head CI와 소비자 publication-POM gate를
  대체하지 않는다. 새 catalog commit/tag 및 snapshot artifact 증거는 아직
  생성 전이다.

