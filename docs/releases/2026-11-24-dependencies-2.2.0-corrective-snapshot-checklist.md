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
- 공통 catalog ref: 기존
  `7a5995fd46031ce1faf16337fa08d954436f8f9a`는 사용하지 않는다. 새 immutable
  ref `catalog/2026-11-24-01`은 commit
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`을 가리키며, 서명된 annotated tag
  object SHA는 `4d1351b5f65b773e9ed657694d063037061d42f4`다. 원격 tag object와
  peeled commit을 2026-11-24에 다시 읽어 일치함을 확인했다.
- consumer 범위: Projects, AWS, Experimental, Exposed, Graph, Image, JaVers,
  Leader, Text. 아홉 후보 모두 Settings/CI에서 commit SHA
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`을 사용한다. Projects CI의 catalog
  tag pin은 `catalog/2026-11-24-01`, annotated tag-object pin은
  `4d1351b5f65b773e9ed657694d063037061d42f4`다.
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
- PR #291은 `develop` 대상 OPEN이다. 이 체크리스트의 최신 live read-back은
  head `0d3816359137e740b9895e25db81f4d6b9ba1d57`이며, manifest 보정과 리뷰
  기록은 같은 PR에 반영한다. merge 직전 최종 head의 checks, review/thread,
  mergeability, 승인 상태를 다시 읽는다.
- Projects #1915와 Experimental #103은 action version만 변경하는 OPEN PR이다.
  catalog ref 행을 수정하지 않으며, consumer 보정 PR과 함께 현재 mergeability를
  다시 확인한다.

## 완료 확인

- [x] Catalog self alias, verifier, 회귀 테스트, checksum sidecar, stable 경계
- [x] `catalog/2026-11-24-01` immutable tag, commit SHA 및 tag-object SHA read-back
- [x] 9개 consumer 후보가 같은 SHA를 Settings/CI에서 사용; Projects tag pins 일치
- [ ] 모든 consumer PR exact-head CI와 merged `develop` read-back
- [ ] 전체 publisher publication-POM 및 Maven effective-model gate
- [ ] 8개 child snapshot DAG, Full Nightly, 자동 Publish Snapshot, artifact read-back
- [ ] PR #291 exact-head checks/reviews/threads/독립 리뷰 및 guarded merge
- [ ] Dependencies `2.2.0-SNAPSHOT` 자동 publish와 Central artifact read-back
- [ ] 최종 verifier `--require-artifacts`, POM gate 및 9개 consumer SHA parity

## 2026-11-24 후보 로컬 검증

- `tests.test_post_publish_next_development_line` 및
  `tests.test_latest_stable_version_deltas`: 아래 재검증에서 32개 PASS.
  `2.2.0-SNAPSHOT` self alias 허용과 stable verifier의 snapshot 거부 경계를
  함께 검증했다.
- `tests.test_catalog_checksum`: 2개 PASS.
- `scripts/audit-latest-stable.py --check --check-audit --audit-summary`:
  PASS — authority 523, metadata verified 518, preview-only 5, unavailable 0.
- `python3.13 -m py_compile ...` 및 `git diff --check`: PASS.
- `./gradlew build`: BUILD SUCCESSFUL. Gradle 10 호환성 관련 기존 deprecation
  안내가 출력됐으며 빌드는 통과했다.
- 이 로컬 검증은 PR #291의 새 exact-head CI와 소비자 publication-POM gate를
  대체하지 않는다. tag는 아래에 기록한 대로 생성했지만, 보정 catalog ref로
  재게시한 snapshot artifact 증거는 아직 없다.

## 2026-11-24 PR #291 CI 보정

- PR #291의 과거 head `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`에서 run
  `45308419517`은 `Cross-repository Publication POM Contract` PASS 후 `Build BOM`의 기존
  `test_catalog_self_version_matches_the_release_version`가 catalog self alias를
  `baseVersion + snapshotVersion`인 정식 `2.2.0`으로 고정해 실패했다. 이 검사는
  다음 개발선 `2.2.0-SNAPSHOT` 계약과 맞지 않았다.
- 회귀 테스트를 다음 개발선 manifest의 `development-version`과
  `snapshot-suffix`에서 기대값을 계산하고 source `baseVersion`/빈
  `snapshotVersion` 및 catalog alias를 각각 확인하도록 변경했다. 수정된 집중
  테스트와 새 exact-head hosted CI를 재확인한다.
- 로컬 전체 테스트는 624개 중 이 보정 외 두 검사가 실패했다.
  workspace-wide 검사가 실제 형제 checkout에서 catalog authority 15개와
  hard-coded baseline 52개를 읽었기 때문이다. hard-coded 결과의 source path에
  `.worktrees`는 0개였고, 이 차이는 local workspace 상태에 한정된다. 해당 두
  검사는 hosted runner에 형제 저장소가 없으면 skip되므로 이 결과를 중앙 PR
  코드의 회귀로 취급하지 않는다.
- tag와 consumer ref 후보는 생성했으나, 이 결과는 당시 `c44ec6c` PR head에
  한정된다. manifest 보정 후의 새 exact-head CI와 publication-POM gate를 별도로
  확인해야 한다.

## 2026-11-24 재검증 진행 상태

- Catalog tag `catalog/2026-11-24-01`의 원격 tag object
  `4d1351b5f65b773e9ed657694d063037061d42f4`와 peeled commit
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`가 일치한다.
- Projects PR #1918은 head `2fec997ab010f20b0a1b0c28b19fe19fc4145256`에서
  31개 검사가 모두 PASS하고 `MERGEABLE`이다. 로컬
  `tests.test_catalog_workflows`도 150개 PASS다. merge 직전 리뷰/thread와 exact
  head를 다시 읽는다.
- AWS #689 (`dd2b28c`, 20 PASS), Experimental #110 (`12db354`, 6 PASS),
  Exposed #953 (`bc4da15`, 42 PASS, 조건부 1 SKIPPED), Graph #669 (`ec6a27c`,
  21 PASS), Image #715 (`2a5900a`, 33 PASS, 조건부 1 SKIPPED), JaVers #406
  (`ad1a488`, 17 PASS), Leader #1026 (`3ba771f`, 46 PASS), Text #355
  (`6968882`, 13 PASS)는 모두 `develop` 대상 OPEN/MERGEABLE이다. 아홉 후보의
  Settings/CI ref는 모두 `c44ec6c…`이며, 이 train의 각 merge 직전에 해당 PR의
  exact head와 reviews/threads를 다시 읽는다.
- PR #291은 `develop` 대상 OPEN, 마지막 live head
  `0d3816359137e740b9895e25db81f4d6b9ba1d57`, mergeable이며 기존 10개 checks가
  모두 PASS했다. 이 head에는 중앙 manifest의 `snapshot-catalog-ref`가
  consumer ref와 다르게 이전 SHA `7a5995fd46031ce1faf16337fa08d954436f8f9a`로
  남은 P1이 발견되어, manifest와 회귀 테스트를 공통 SHA `c44ec6c…`로 바꾸고
  기대 candidate branch도 `chore/snapshot-catalog-c44ec6c`로 수정했다.
- 수정 후 `python3.13 -m unittest tests.test_post_publish_next_development_line
  tests.test_latest_stable_version_deltas`는 32개 PASS, `git diff --check`도
  PASS했다. 이 변경은 현재 중앙 후보에서 아직 commit/push 및 hosted CI 재실행
  전이다.
- Sonatype snapshot endpoint에서 Dependencies metadata는 HTTP 404이며, 8개 child
  BOM의 이전 catalog train metadata와 BOM POM/GMM은 모두 HTTP 200이다. 확인한
  최신 값은 Projects `20261123.000921-2`, Exposed `20261123.021344-2`, AWS
  `20261123.003256-2`, Graph `20261123.002829-2`, Image `20261123.025144-1`,
  JaVers `20261123.033837-1`, Leader `20261123.090259-1`, Text
  `20261123.095025-1`이다. 이 artifacts는 `catalog/2026-11-22-01` 기준 이전
  train 산출물이므로 이번 공통 ref의 Nightly·Publish Snapshot 증거로 사용하지
  않는다. 각 publisher의 새 merge SHA에서 순서대로 다시 게시한다.
- #291의 현재 head에는 review submission, inline review thread, issue comment가
  없다. Native reviewer/architect 실행은 설치된 code-mode host 파일 부재로 시작되지
  않았고, Claude Code는 조직에서 subscription access를 막아 독립 verdict를 내지
  못했다. 따라서 아래 인라인 fallback 기록은 독립 리뷰 증거가 아니며, 새 exact
  head에 대한 CI와 live review/thread read-back도 아직 남아 있다.

## 2026-11-24 문서 근거와 작성 검증

- README 영문·한국어의 central dependency alias는 모두 `2.2.0-SNAPSHOT`이다.
  현재 안정 소비자는 Dependencies `2.1.0`을 유지하고, `2.2.0` stable artifact는
  아직 공개되지 않았다는 공식 release 기준 및 `gradle/libs.versions.toml`과
  일치한다.
- 근거는 release checklist의 Projects → Exposed → child publisher dependency DAG
  → child artifact read-back → central Dependencies snapshot 순서, live PR
  heads/checks, snapshot metadata/POM/GMM endpoint, catalog tag read-back이다.
  11-22 checklist는 당시 train의 historical evidence로 보존한다.
- Maven `-SNAPSHOT` version과 snapshot publication을 가리키는 표현은 일반 데이터
  snapshot을 뜻하지 않는다. Clinic terminology audit의 `snapshot-loanword`
  결과가 이 문맥에 걸리면 용어를 바꾸지 않고 intentional exception으로 기록한다.
- `audit-korean-terms.mjs --series clinic-appointment --json` 결과는 6개 문서에서
  53개 finding이며 모두 `snapshot-loanword` 한 규칙에 해당한다. 각 발생 위치는
  Maven `-SNAPSHOT` 버전, Maven Central snapshot metadata/artifact, catalog train,
  또는 해당 게시 절차를 설명한다. 실제 도메인 데이터 snapshot을 지칭한 결과는
  없어서 기술 용어를 유지했다.
- README.ko.md의 warm-up 설명 2건도 Maven Central snapshot metadata/artifact 접근을
  다룬다. intentional exception으로 확인했고 다른 terminology rule은 없었다.

### 인라인 리뷰 작성 게이트

- [x] **SPW-01 — 독자·목적·근거 고정.** 독자는 중앙 BOM maintainer이며,
  PR #291의 release-verifier/config/docs 계약과 BOM/catalog 경계를 검토한다.
  근거는 후보 manifest, verifier 테스트, 아홉 consumer pin, live release/Central
  상태, 중앙 BOM import와 publish workflow다.
- [x] **SPW-02 — 리뷰 형식 충족.** 두 P1의 위치·영향·수정·미검증 경계,
  publisher DAG 아키텍처 판정, 전체 범위, 독립 리뷰 한계를 기록했다.
- [x] **SPW-03 — 한국어 기술 문체.** `references/korean-naturalness-checklist.md`
  KO-01..KO-07을 확인했다. Maven의 `SNAPSHOT`, ref, exact-head 등 식별자는
  그대로 두고 변경 설명은 구체적인 문장으로 작성했다.
- [x] **SPW-04 — 기술 사실 추적.** manifest/ref는 config·consumer 설정과,
  버전은 공식 `2.1.0` 상태 및 다음 development line과 대조했다. 수정 전 CI를
  새 head 검증으로 취급하지 않는다.
- [x] **SPW-05 — 최종 읽기.** `docs/reviews/2026-11-24-pr-291-inline-review.md`
  전체를 다시 읽었고, 코드/아키텍처 inline 판정의 범위, 독립 리뷰 부재와 새
  CI/POM pending을 명시했다.

### Lesson 작성 게이트

- [x] **SPW-01 — 독자·목적·근거 고정.** 독자는 후속 catalog-train 유지보수자다.
  근거는 9개 소비자 저장소에 같은 SHA를 요구하는 policy, 중앙 manifest, tag, verifier다.
- [x] **SPW-02 — Lesson 형식 충족.** 상황, 원인, 결정, 결과, 검증과 재발 방지
  규칙을 각각 기록했다.
- [x] **SPW-03 — 한국어 기술 문체.** `references/korean-naturalness-checklist.md`
  KO-01..KO-07을 확인하고 코드 토큰과 문장 의미를 분리했다.
- [x] **SPW-04 — 기술 사실 추적.** 테스트 32개, catalog tag/peeled commit,
  consumer ref 및 남은 POM/publication 경계를 현재 후보와 대조했다.
- [x] **SPW-05 — 최종 읽기.** `docs/lessons/2026-11-24-snapshot-verifier-catalog-ref.md`
  전체를 다시 읽고 미완료 검증을 명시했다.

### 문서·검증 read-back

- README 두 locale에서 중앙 dependency alias는 `2.2.0-SNAPSHOT`으로 일치하며,
  `gradle/libs.versions.toml`의 버전과 같다.
- `tests.test_catalog_checksum`,
  `tests.test_post_publish_next_development_line`,
  `tests.test_latest_stable_version_deltas`: 34개 PASS. catalog SHA-256 sidecar와
  현재 `gradle/libs.versions.toml`도 일치한다.
- `git diff --check`와 `py_compile`은 PASS다. Ruff 후보와 `origin/develop`의
  16개 진단을 code/행/열로 비교했으며 candidate-only 진단은 0개다.

