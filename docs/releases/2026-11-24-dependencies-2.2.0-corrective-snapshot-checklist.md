# Dependencies 2.2.0-SNAPSHOT catalog 보정 체크리스트

상태: **진행 중 — 8개 child snapshot 재게시와 공개 read-back을 마쳤으며, #291 병합·중앙 snapshot·최종 검증이 남음**

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
- [x] 모든 consumer PR exact-head CI와 merged `develop` read-back
- [ ] 전체 publisher publication-POM 및 Maven effective-model gate
- [x] 8개 child snapshot DAG, Full Nightly, 자동 Publish Snapshot, artifact read-back
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

## 2026-11-24 Projects 실행 갱신

- Projects #1918은 승인 head `2fec997ab010f20b0a1b0c28b19fe19fc4145256`에서
  rebase merge되어 `develop`이 `97261ccac819f141db261c4d95e4e12c6483d0a2`를
  가리킨다. post-merge CI run `45332152292`는 동일 head에서 전체 성공했다.
- `Nightly` run `45333761692`는 2026-11-24 05:30 UTC에 `develop`으로
  dispatch했으며, 선언된 `scope=full` 입력과 exact head
  `97261ccac819f141db261c4d95e4e12c6483d0a2`를 사용한다. 현재 실행 중이며
  끝나기 전에는 다음 publisher로 진행하지 않는다.
- Nightly workflow의 성공을 조건으로 `Publish Snapshot`이 `workflow_run`에서
  자동 시작된다. 수동 `publish-snapshot.yml` dispatch는 금지하고, 자동 run의
  exact SHA/conclusion 뒤 metadata, POM, Gradle module metadata를 다시 읽는다.
- Nightly 전 기존 Projects `2.2.0-SNAPSHOT` metadata는 HTTP 200이며 최신 값은
  `2.2.0-20261124.040715-3` (`lastUpdated=20261124040715`)이다. timestamp POM과
  `.module`도 HTTP 200이었지만, 이는 이번 run 전 산출물이므로 새 train 게시로
  간주하지 않는다.
- `Test / Data (rdb)` job `138242766281`은 두 번의 자동 시도에서 Maven Central의
  HTTP 429 때문에 `hibernate-jcache:7.4.7.Final` POM 등을 받지 못해 실패했다.
  원본 job 로그는 동일 요청의 429를 기록한다. 코드를 바꾸지 않고 나머지 matrix의
  종료를 기다린 뒤 해당 실패 job만 재실행한다. run이 최종 성공하고 자동 snapshot
  artifact를 확인하기 전에는 다음 publisher로 넘어가지 않는다.
- 최종 run `45333761692`는 43개 job 성공, `Test / Data (rdb)` 실패 외에
  `Coverage Report`와 `Nightly Status`도 실패했다. Coverage Report 로그는
  `test-data=failure` 집계로 종료했고 Nightly Status는 그 두 실패를 요약했다.
  자동 Publish Snapshot run `45338464266`은 동일 head에서 `workflow_run`으로
  시작됐으나 Nightly 실패 조건 때문에 `skipped`됐다. 따라서 이 실패 run은 게시
  증거가 아니다. 필요한 실패 job과 그 의존 집계를 재실행하고, 성공한 후속 자동
  Publish Snapshot run과 artifact를 별도로 확인한다.
- 실패 job과 집계 job을 재실행한 Nightly attempt 2는 run `45333761692`, exact
  head `97261ccac819f141db261c4d95e4e12c6483d0a2`에서 46개 job 성공으로 종료했다.
  성공한 `workflow_run`으로 자동 Publish Snapshot `45339489301`이 같은 SHA에서
  시작돼 성공으로 종료했다.
- Exposed의 build가 소비하는 Projects BOM은
  `io.github.bluetape4k:bluetape4k-bom:2.2.0-SNAPSHOT`이다. 자동 게시 후 BOM
  metadata와 timestamped POM, 그리고 핵심 라이브러리
  `io.github.bluetape4k:bluetape4k-core:2.2.0-SNAPSHOT` metadata/POM/GMM을
  다시 조회했다. 모두 HTTP 200이며 최신 공통 timestamp는
  `2.2.0-20261124.062516-4` (`lastUpdated=20261124062516`)이다. BOM은 metadata-only
  artifact이므로 module metadata는 해당하지 않는다.
- Projects 단계의 Nightly, 자동 Publish Snapshot 및 downstream 필수 artifact
  read-back이 끝났다. 다음은 Exposed #953이다.
- Exposed #953은 head `bc4da1555e3b2febdfcb2736ff0537e758a02228`에서 42개 PASS,
  조건부 Docs-only validation 1개 SKIPPED, `MERGEABLE`을 재확인했다. formal review,
  issue comment, inline review comment, unresolved thread는 모두 0개였다. exact-head
  rebase merge 후 `develop`은 merge commit
  `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`로 이동했다.
- Exposed develop CI `45341154409`와 Dependency Submission `45341154160`은 해당
  merge commit에서 진행 중이다. 최신 `nightly-tests.yml`은 `scope=full`을 선언하고,
  `publish-snapshot.yml`은 성공한 develop Nightly의 `workflow_run`으로만 자동
  게시한다. post-merge CI/Dependency Submission 성공 뒤 Full Nightly를 실행한다.
- Dependency Submission `45341154160`은 merge commit에서 성공했지만 CI
  `45341154409`의 첫 시도는 실패했다. Build (compile only) 단계는 성공했고 이후
  buildSrc TestKit 단계 실행 중 hosted runner가 shutdown signal을 받아 작업이
  취소됐다. Coverage Report는 그 취소로 Kover XML artifact가 없어 실패했다.
  코드/의존성 오류가 아닌 runner 중단으로 분류하고, exact merge SHA에서 실패한 CI
  job과 coverage 집계만 재실행한다. CI 성공 전에는 Exposed Nightly를 시작하지 않는다.
- CI run `45341154409` attempt 2도 같은 merge SHA에서 Build (compile only)를
  통과했지만, TestKit 회귀 테스트가 시작된 뒤 2026-11-24 07:15:30 UTC에 job이
  취소됐다. 선언된 job 제한은 30분이며 실제 job은 35분간 실행됐다. 취소된 buildSrc
  단계의 로그/테스트 결과 artifact가 생성되지 않았고, Coverage Report는 downstream
  집계로서 Kover XML 누락 때문에 실패했다. 같은 Exposed PR head의 CI run
  `45310196901`에서는 Build job 전체가 15분 08초, TestKit 단계가 6분 55초에 성공했다.
  따라서 attempt 2에는 소스 테스트 실패 증거가 없다. exact merge SHA에서 실패/취소
  job만 재실행했으며 attempt 3은 2026-11-24 07:17:57 UTC에 시작했다. 이 시도가
  완료되기 전에는 Full Nightly를 dispatch하지 않는다.
- Exposed PR head `bc4da1555e3b2febdfcb2736ff0537e758a02228`와 merge SHA
  `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`의 Git tree가 모두
  `7dab1476b2517910ab6a1cdc29eecbec39f53ba6`임을 확인했다. source-identical 임시
  worktree에서 세 buildSrc TestKit class를 개별 실행해 모두 통과했고, CI와 동일한
  `GRADLE_OPTS=-Dorg.gradle.daemon=false`, 세 class 조합 및 XML assertion을
  `--rerun-tasks`로 새로 실행해 `BUILD SUCCESSFUL in 1m 3s`를 확인했다. 이 결과와
  PR exact-head hosted TestKit 성공(`45310196901`, 6분 55초), post-merge attempts 2/3의
  35분 취소 및 결과 artifact 부재를 종합해 hosted-runner 지연으로 분류한다. attempt 3
  이후 실패/취소 job만 exact merge SHA에서 다시 실행한다.
- Exposed CI attempt 3은 run `45341154409`의 Build job `138283554097`에서 TestKit
  단계가 끝나지 않은 채 2026-11-24 07:52:57 UTC에 취소됐다. Coverage Report는
  `45341154409`의 의존 artifact 부재로 실패했다. exact remote `develop` SHA는 계속
  `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`이며, failed/cancelled job 재실행 attempt 4는
  2026-11-24 08:02:02 UTC에 시작했다.
- Experimental #110은 head `12db354321d7a45812db0955b02c66dca182c416`에서 6개
  check 모두 PASS, formal review/issue comment/inline comment/review thread 0개,
  `MERGEABLE`을 확인한 뒤 guarded rebase merge했다. merge commit은
  `0285e3745ce827361b03a46ef74f81c05d8be723`이며 diff의 Settings와 CI pin 모두
  공통 catalog SHA `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`를 가리킨다. 이 저장소는
  catalog-only consumer이므로 publisher Nightly/snapshot 대상은 아니다.
- Experimental merge 후 Dependency Submission run `45349210872`는
  `io.github.bluetape4k:bluetape4k-dependencies:2.2.0-SNAPSHOT`을 benchmark graph에서
  해석하지 못해 실패했다. Sonatype snapshots metadata/POM이 아직 404인 것은
  Dependencies `2.2.0-SNAPSHOT`을 child publisher 순서가 끝난 뒤 마지막에 게시하는
  절차와 일치한다. 중앙 snapshot 게시 후 이 run의 실패 job을 재실행해 제출 artifact를
  확인한다. Experimental CI run `45349210797`은 merge SHA
  `0285e3745ce827361b03a46ef74f81c05d8be723`에서 성공했다.

- Exposed CI run `45341154409` attempt 4도 exact merge SHA에서 실패했지만, 실제
  PostgreSQL 테스트가 시작되기 전 Kover task가 Maven Central의
  `kover-jvm-agent:0.9.11` POM 요청에서 HTTP 429를 다섯 번 받아 종료됐다. CI Status는
  이에 따라 `test-postgresql-module: failure`를 보고했고, 해당 job의 Kover coverage
  upload도 XML 누락으로 실패했다. 이는 테스트 실패가 아닌 저장소 rate-limit 오류다.
- Live `develop`이 merge SHA `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`와 계속
  일치함을 확인하고 run `45341154409`의 실패 job만 재실행했다. 현재 attempt 5가 같은
  SHA에서 2026-11-24 08:46 UTC에 성공했다. PostgreSQL job
  `138322650427`, Coverage Report `138323736205`, CI Status `138323842796`가 모두
  성공했고 `Docs-only validation`만 조건부 skip이다. CI run attempt 5의 전체
  conclusion은 `success`다.
- 성공 CI에 포함된 `Build (compile only)` job `138322652726`의
  `Validate publication POMs` 단계도 성공했다. merge commit과 live `develop`은 계속
  `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`이다.
- Exposed의 보정 전 최신 자동 snapshot은 Nightly `45324855861` 성공 뒤 자동으로
  시작된 Publish Snapshot `45327016051`이며, source SHA는 기존 develop
  `cd4eb89dd1f5240560327a9f0902668fc51c9286`이다. version-level Maven snapshot
  metadata에서 Exposed BOM과 JDBC의 직전 timestamp가 `2.2.0-20261124.043749-3`
  (`lastUpdated=20261124043749`)임을 다시 확인했다. 해당 BOM/JDBC timestamp POM은
  HTTP 200, JDBC `.module`도 HTTP 200이다. BOM은 POM-only다. 이 publication은
  이전 catalog train의 기준점이며 이번 ref의 게시 증거가 아니다.
- Exposed Nightly 직전 upstream Projects snapshot을 다시 확인했다. Projects BOM과
  core metadata 모두 `2.2.0-20261124.062516-4`
  (`lastUpdated=20261124062516`)를 가리킨다. timestamp POM은 HTTP 200이고 core
  `.module`도 HTTP 200이다. 이는 Projects `45339489301`의 성공한 자동 게시와
  일치하며 Exposed의 상위 BOM/core 입력이 공개되어 있음을 확인한다.
- Nightly workflow를 live `develop`에서 다시 읽었다. `workflow_dispatch`가 선언한
  유일한 입력은 `scope`이며 허용값 `smoke`/`full` 중 `full`을 사용할 수 있다.
  같은 `develop`의 `publish-snapshot.yml`은 성공한 `Nightly` `workflow_run`에만
  자동 게시한다. workflow dispatch 스키마, merge SHA, CI 성공을 확인했고, 해당
  SHA를 대상으로 한 Nightly은 아직 없음을 확인한 뒤 run `45359501798`을
  `scope=full`로 dispatch했다. 대상 SHA는
  `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`이며 51/51 jobs가 성공했다.
  성공한 Nightly 직후 workflow_run으로 자동 시작된 Publish Snapshot run
  `45362683582`도 같은 SHA를 확인했다. publication job의 source SHA 검증과
  `Validate publication POMs`가 성공해 실제 Publish SNAPSHOT 단계로 이동했다.
  publish job은 2026-11-24 09:20:48 UTC에 성공했다. Snapshot version-level metadata에서
  Exposed BOM과 JDBC 모두 `2.2.0-20261124.091744-4`
  (`lastUpdated=20261124091744`)를 확인했다. timestamp POM은 모두 HTTP 200이고,
  JDBC `.module` 및 `.jar`도 HTTP 200이다. BOM은 POM-only다. 따라서 AWS가 사용하는
  Exposed BOM/JDBC 선행 산출물이 공개됐다. 수동 snapshot dispatch는 하지 않았다.
- AWS #689은 exact head `dd2b28ce70b3ad8a92d64dbc220da23cdf662f62`에서 20개 CI check
  모두 통과하고 `MERGEABLE`이었다. 현재 PR API와 GraphQL read-back에서 formal review,
  review thread, review comment, issue comment가 모두 0개였으며 base `develop`
  `8ad0b194ed6f8f137f68fc513014983c41ca7940`가 계속 일치했다. Exposed BOM/JDBC
  snapshot 공개 뒤 guarded rebase merge했고, merge commit/live AWS `develop`은
  `6d3a7e02ab0a77d6ddfdafaa8e9f452257652667`이다. post-merge CI
  `45364668007`은 queued, Dependency Submission `45364667954`는 진행 중이다.
  Dependency Submission은 같은 SHA에서 성공했고 CI는 20/20 jobs 성공했다.
  live `develop`의 Nightly dispatch 입력은 `scope` (`smoke` 또는 `full`)이며,
  Publish Snapshot은 successful Nightly `workflow_run`에 자동 연결된다. merge SHA를
  대상으로 한 이전 Nightly이 없음을 다시 확인했다. 이를 근거로 run
  `45366791466`을 `scope=full`로 dispatch했다. 대상 SHA는
  `6d3a7e02ab0a77d6ddfdafaa8e9f452257652667`이다. 성공한 Nightly이 끝나면
  2026-11-24 09:44:09 UTC에 10/10 jobs 성공했다. successful workflow_run으로 자동
  시작한 Publish Snapshot은 `45368005087`이며 같은 SHA를 확인했다. 이 run이 끝나면
  AWS BOM과 required library POM/GMM artifact를 read-back한다. 수동 snapshot
  dispatch는 하지 않는다.
- AWS Publish Snapshot `45368005087`은 Nightly run `45366791466` 이후 자동 시작되어
  2026-11-24 09:47:36 UTC에 성공했다. source SHA는 AWS develop
  `6d3a7e02ab0a77d6ddfdafaa8e9f452257652667`이다. Snapshot version-level metadata에서
  AWS BOM과 다섯 library artifact 모두 `1.2.0-20261124.094701-4`
  (`lastUpdated=20261124094701`)를 가리키며, 각 POM은 HTTP 200이다. 다섯 library의
  `.module`과 `.jar`도 모두 HTTP 200이다. 다음 publisher Graph가 사용할 AWS BOM 및
  `aws-exposed` artifact가 공개됐음을 확인했다.
- Graph #669는 exact head `ec6a27ccc11b3d5f3e7f6a2ce6109374a1cf2120`에서 21개 CI
  check가 모두 성공했고 `MERGEABLE`이었다. PR diff의 Settings, CI, Testcontainers
  contract 세 pin 모두 공통 catalog SHA `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`
  를 가리킨다. 직전 API/GraphQL read-back에서 formal review, review thread, review
  comment, issue comment는 모두 0개였다. develop base는
  `2442ee65ed3f5ebc9f4b169dd20357e9c569d183`였다. AWS snapshot 공개 뒤 exact-head
  guard를 사용해 rebase merge했으며 merge commit은
  `5bb82ae4838d21a561675dcf59d475e12a42bf4a`이다. Dependency Submission run
  `45369108504`는 같은 SHA에서 성공했다. post-merge CI run `45369108244`도 같은 SHA에서
  16/16 jobs 전체 성공했다. Build & Detekt 및 publication POM 검증과 Core/TinkerGraph,
  Spring Boot, Neo4j, Memgraph, Apache AGE, FalkorDB, Ktor Graph 통합 테스트 및
  coverage 집계가 모두 통과했다. live develop Nightly workflow는 `scope=full` 입력을
  선언하고, Publish Snapshot은 성공한 Nightly `workflow_run`에 자동 연결된다. 해당
  merge SHA에서 Nightly이 아직 없음을 확인한 뒤 Full Nightly를 실행하고 자동 snapshot을
  검증한다. 수동 snapshot dispatch는 하지 않는다.
- Graph Full Nightly run `45370531296`은 exact merge SHA
  `5bb82ae4838d21a561675dcf59d475e12a42bf4a`에서 시작했다. wrapper validation은
  통과했고 Build & Detekt가 진행 중이다. 성공 후 자동 Publish Snapshot run과 공개
  Graph BOM/library 산출물을 같은 SHA 및 version-level metadata 기준으로 확인한다.
- Graph Full Nightly의 Ktor Graph job `138364484302`는 test compilation 단계에서
  Maven Central `repo.maven.apache.org`의 HTTP 429 때문에 실패했다. 다섯 retry 모두
  `org.slf4j:log4j-over-slf4j:2.0.20`, `io.mockk:mockk:1.14.12`,
  `io.ktor:ktor-server-test-host:3.6.1` 등 의존성을 가져오지 못했고, 실제 Ktor 테스트는
  시작하지 않았다. 나머지 완료 job은 성공했으며 Testcontainers image-family gate가
  진행 중이다. 원래 Nightly가 종료된 뒤 실패 job만 재실행하고 자동 snapshot은 Nightly
  전체가 성공한 후에만 허용한다.
- Graph Nightly run `45370531296` attempt 1은 Ktor job 실패와 함께 종료됐다. `--failed`
  재실행 attempt 2에서는 Ktor job `138368730826`이 성공했고 다른 테스트 및
  image-family gate도 성공했지만 Coverage Report `138370169815`가 실패했다. 실패 로그는
  attempt 1의 `coverage-all` 보고서와 attempt 2의 개별 coverage artifact에 같은 모듈
  보고서가 함께 들어와 duplicate report로 거부됐음을 보여 준다. 따라서 이 run의 최종
  conclusion은 실패로 남는다. 이 artifact 재조합을 피하려고 동일 merge SHA에서 새 Full
  Nightly run을 실행하며, 그 fresh run 성공 뒤에만 automatic Publish Snapshot을
  기다린다. snapshot을 직접 dispatch하지 않는다.
- Graph Full Nightly fresh run `45373076365`는 최신 live develop SHA
  `5bb82ae4838d21a561675dcf59d475e12a42bf4a`에서 시작했다. live workflow는 입력
  `scope=full`을 허용하며, 직전 run attempt의 실패 artifact와 섞이지 않는 새 run이다.
  성공하면 workflow_run 기반 Publish Snapshot과 Graph library metadata를 검증한다.
- Fresh Graph Full Nightly run `45373076365`는 12/12 jobs 성공으로
  2026-11-24 10:22:16 UTC에 끝났다. 같은 SHA의 성공 workflow_run으로 자동 시작된
  Publish Snapshot은 `45374157263`이며 현재 실제 publication 단계까지 진행됐다. 앞선
  실패/재실행 attempt에서 발생한 Publish Snapshot workflow_run들은 조건상 skip됐고,
  수동 snapshot dispatch는 하지 않았다.
- Graph Publish Snapshot `45374157263`는 source SHA
  `5bb82ae4838d21a561675dcf59d475e12a42bf4a`에서 성공했다. 실제 release target은
  candidate central catalog의 `1.2.0-SNAPSHOT`이며, 기본 checkout에 남아 있던
  `1.1.0-SNAPSHOT`은 이전 development line이다. 올바른 version-level metadata에서 BOM과
  15개 library 모두 `1.2.0-20261124.102417-4`
  (`lastUpdated=20261124102417`)를 가리켰다. 각 artifact의 metadata와 timestamp POM은
  HTTP 200이며, BOM을 제외한 15개 모두 `.module`과 `.jar`도 HTTP 200이다. 이제 Image
  consumer의 선행 Graph 산출물이 공개됐다.
- central PR #291의 기존 CI run `45328093084`는 옛 PR head에서 Build BOM과 최종
  CI Status가 실패했다. Build BOM 로그상 version-catalog artifact 검증(188 aliases),
  cross-repository publication POM contract, 스크립트·Python 테스트는 통과했다. 실패는
  당시 9개 managed consumer의 Settings/CI가 공통 catalog SHA
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3` 대신 이전
  `7a5995fd46031ce1faf16337fa08d954436f8f9a`를 pin한 governance assertion이다. consumer
  PR들의 순차 merge가 끝난 뒤 #291의 최종 head CI를 다시 읽고, 이 assertion이 성공한
  것을 확인하기 전에는 #291을 merge하지 않는다.
- Image #715는 exact head `2a5900a823f73c0de5a35427191990e5d7d300dc`에서 33개 CI check가
  성공했고 조건부 PaddleOCR native acceptance 1개만 skip됐다. PR diff의 Settings와 CI는
  모두 공통 catalog SHA `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`를 pin한다. live PR 및
  GraphQL read-back에서 formal review, review thread, review comment, issue comment는 모두
  0개였고 `MERGEABLE`이었다. independent code-reviewer lane은 실행 파일
  `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host` 누락으로 시작되지 않았다.
  Inline fallback으로 두 설정 변경과 immutable catalog tag/commit을 확인했으며 P0=0,
  P1=0이다. Graph snapshot artifact 확인 후 exact-head guard를 사용해 rebase merge했고
  merge commit은 `042c8b97cd1229f8046f804f2658233b25beba22`이다. post-merge Dependency
  Submission `45376399987`, post-merge CI `45376399976`, Examples `45376399885`는 모두
  같은 SHA에서 성공했다. live `develop` Nightly schema의 입력은 `scope`
  (`smoke`/`full`)이고 Publish Snapshot은 성공한 Nightly workflow_run에서 자동 게시하도록
  선언되어 있다. snapshot dispatch는 Nightly 성공 뒤 자동 workflow_run만 사용한다.
- Image Full Nightly run `45378369004`는 정확한 merge SHA
  `042c8b97cd1229f8046f804f2658233b25beba22`에서 16/16 jobs 성공했다. successful
  workflow_run으로 자동 시작된 Publish Snapshot `45379779377`도 같은 SHA에서 성공했다.
  Sonatype snapshot repository
  `https://central.sonatype.com/repository/maven-snapshots/`의 version-level metadata와
  timestamped artifacts를 확인했다. `1.2.0-SNAPSHOT`의 BOM 및 10개 library가 모두
  `1.2.0-20261124.110007-2`를 가리켰고, BOM POM 및 각 library의 POM, Gradle module,
  JAR 응답이 모두 HTTP 200이다. `repo.maven.apache.org`는 release repository라서 첫
  확인에서 snapshot metadata가 404였고, project의 snapshot repository 설정을 따라
  올바른 Sonatype endpoint에서 검증했다. Snapshot은 수동 dispatch하지 않았다.
- Live read-back에서 Leader #1026 merge commit `87a2a17609b837e159f258298b29d43c3000d631`
  (`2026-11-24T10:38:30Z`)과 Text #355 merge commit
  `73b306b734bf21eaf070f0da32f4f5847b40dc34` (`2026-11-24T10:39:03Z`)도 확인됐다.
  두 PR 모두 공통 catalog SHA를 pin하며 Dependency Submission은 성공했으나, merge SHA에서
  Nightly/Publish Snapshot run은 아직 없었다. 공개 순서를 유지하기 위해 두 저장소의
  Nightly를 보류하고 Image artifact 및 JaVers snapshot 뒤 Leader, 이어 Text 순서로 실행한다.
  Leader Dependency Submission `45376712261`과 CI `45376712289`, Text Dependency
  Submission `45376798008`과 CI `45376798018`은 모두 각 merge SHA에서 성공했다. Nightly는
  두 publisher의 순서를 지키기 위해 JaVers snapshot 공개 뒤에만 시작한다.
- JaVers #406의 exact head `ad1a48880762d16c10149ab250f80f6f6ff370ba`는 CI 17/17 성공,
  `MERGEABLE`, review/thread/comment 0건이었다. diff는 `.github/workflows/ci.yml`과
  `settings.gradle.kts`의 catalog ref를 공통 SHA
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`로 바꾸는 두 줄뿐이고, tag
  `catalog/2026-11-24-01`의 peeled commit도 해당 SHA와 일치했다. 독립 code-reviewer는
  `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host` 누락으로 시작하지 못해
  inline diff review를 수행했고 P0/P1은 없다. 최신 head guard를 사용한 rebase merge 결과는
  `4e67c0fb200e45249272a2b482f9e85bf96fd762` (`2026-11-24T11:07:29Z`)다. Post-merge
  Dependency Submission `45381259022`는 성공했고 CI `45381258961`은 현재 진행 중이다.
  CI 성공 전까지 JaVers Full Nightly 및 snapshot은 dispatch하지 않는다.
- Image, JaVers, Leader, Text 및 앞선 네 소비자 Projects, Exposed, AWS, Graph의 live
  `develop` Settings/CI 파일을 GitHub API에서 읽어 확인했다. 8개 저장소 모두 두 참조가
  공통 catalog commit `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`와 일치한다.
- JaVers post-merge CI `45381258961`은 merge SHA 전체 17/17 jobs 성공했고 Dependency
  Submission `45381259022`도 성공했다. 해당 SHA에 이전 Nightly가 없고 live workflow의
  `scope=full` 입력을 확인한 뒤 Full Nightly `45382290108`을 dispatch했다. 현재
  Nightly의 Build & Detekt, 전체 테스트 matrix, Coverage Report, Nightly Status가 모두
  성공했다. 자동 `workflow_run` Publish Snapshot `45382895829`도 같은 merge SHA에서
  성공했다. Sonatype snapshot repository의 `1.2.0-SNAPSHOT` version-level metadata에서
  BOM과 6개 library 모두 `1.2.0-20261124.111949-3`을 확인했고, BOM POM과 각 library의
  POM, Gradle module, JAR이 모두 HTTP 200이다. Leader Full Nightly를 이어서 시작한다.
- Leader merge SHA `87a2a17609b837e159f258298b29d43c3000d631`의 post-merge CI
  `45376712289`와 Dependency Submission `45376712261`은 모두 성공했다. merge SHA에
  Nightly가 아직 없고 live workflow에서 `scope=full`을 확인한 뒤 Full Nightly
  `45383514092`를 실행 중이다. 성공 후 자동 Publish Snapshot과 Leader BOM/library를
  검증한 다음 Text Full Nightly를 실행한다.
- Leader Full Nightly `45383514092`는 MongoDB 테스트 task 자체와 coverage artifact는
  성공했으나 `test-results-mongodb.zip` 업로드를 finalize할 때 GitHub artifact storage가
  `Failed to FinalizeArtifact: Unable to make request: ECONNRESET`을 반환했다. 나머지
  테스트와 Coverage Report는 성공했고 Nightly Status는 이 job 실패로 실패했다. 성공한
  Nightly가 아니므로 자동 Publish Snapshot `45384650521`도 skip됐다. live develop은
  여전히 같은 merge SHA `87a2a17609b837e159f258298b29d43c3000d631`이며, artifact가
  분리되는 fresh Full Nightly `45385099200`을 같은 SHA에서 다시 실행한다.
- Central PR #291 live head `08cdb92297a1494662ef2918dfe02f79409089c6`의 CI run
  `45380017787`은 Build BOM과 Cross-repository Publication POM Contract를 포함한 9/9
  checks 성공으로 끝났다. 이 head는 이후 checklist receipt를 추가 push하기 전의
  현재 검증된 code head이며, 최신 checklist commit이 생기면 exact-head CI를 다시 확인한다.
- GitHub live state에서 Leader Nightly `45383514092`의 attempt 2도 전체 job, Coverage
  Report, Nightly Status가 성공한 것을 확인했다. 그 attempt에 따른 자동 Publish Snapshot
  `45385539903`도 성공했다. 별도 fresh Full Nightly `45385099200` 역시 정확한 merge SHA에서
  전체 matrix와 Nightly Status가 성공했고, 이 run의 자동 Publish Snapshot
  `45386325388`도 2026-11-24 11:44:20 UTC에 같은 merge SHA
  `87a2a17609b837e159f258298b29d43c3000d631`로 성공했다. Sonatype version-level metadata에서
  BOM과 16개 library 모두 `lastUpdated=20261124114320`, timestamp `20261124.114320`,
  build `4`를 가리킨다. BOM POM 및 16개 library의 POM, Gradle module, JAR 응답이 모두
  HTTP 200이다. `bluetape4k-leader-spring-boot`는 의도된 `plain` classifier JAR를 사용한다.
- Text `develop`의 merge SHA `73b306b734bf21eaf070f0da32f4f5847b40dc34`에서 Full Nightly
  `45388703877`이 10/10 jobs 성공했고, 자동 `workflow_run` Publish Snapshot `45389245283`도
  같은 SHA에서 성공했다. Live Nightly workflow는 `workflow_dispatch` 입력이 없으며,
  Publish Snapshot은 성공한 Nightly에 반응한다. 수동 snapshot dispatch는 하지 않았다.
- Sonatype에서 `io.github.bluetape4k.text:bluetape4k-text-bom:1.2.0-SNAPSHOT` BOM과
  `lingua`, `text-search`, `tokenizer-core`, `tokenizer-japanese`, `tokenizer-korean`의
  version-level metadata가 모두 `lastUpdated=20261124120046`, timestamp
  `1.2.0-20261124.120046-3`을 가리킴을 확인했다. BOM POM/Gradle module과 다섯 library의
  POM/Gradle module/JAR는 HTTP 200이다. BOM은 metadata-only이므로 JAR는 게시 대상이 아니다.

## 2026-11-24 child train closeout

- 여덟 publisher의 순서는 Projects → Exposed → AWS → Graph → Image → JaVers → Leader → Text다.
  각 항목은 해당 merge SHA의 CI/Dependency Submission 성공 뒤 Full Nightly를 실행했고,
  성공 Nightly의 `workflow_run`으로 자동 실행된 Publish Snapshot만 사용했다. 수동 snapshot
  dispatch는 없었다.
- Projects merge `97261ccac819f141db261c4d95e4e12c6483d0a2`, Full Nightly
  `45333761692` attempt 2, automatic snapshot `45339489301`이 성공했다. 공개 metadata 및
  required artifacts는 `2.2.0-20261124.062516-4`로 확인했다.
- Exposed merge `b9aee1ed058595198ccebdf3b7a77cb06ab55a41`, CI `45341154409` attempt 5,
  Full Nightly `45359501798`, automatic snapshot `45362683582`가 성공했다. BOM/JDBC는
  `2.2.0-20261124.091744-4`이며 POM, Gradle module, JAR 응답을 확인했다.
- AWS merge `6d3a7e02ab0a77d6ddfdafaa8e9f452257652667`, CI `45364668007`, Full Nightly
  `45366791466`, automatic snapshot `45368005087`이 성공했다. BOM과 다섯 library는
  `1.2.0-20261124.094701-4`이며 POM/module/JAR 응답이 모두 HTTP 200이다.
- Graph merge `5bb82ae4838d21a561675dcf59d475e12a42bf4a`, Full Nightly
  `45373076365`, automatic snapshot `45374157263`이 성공했다. BOM과 15개 library는
  `1.2.0-20261124.102417-4`; timestamp POM 및 module/JAR를 확인했다.
- Image merge `042c8b97cd1229f8046f804f2658233b25beba22`, Full Nightly
  `45378369004`, automatic snapshot `45379779377`이 성공했다. BOM과 10개 library는
  `1.2.0-20261124.110007-2`; POM/module/JAR 응답이 모두 HTTP 200이다.
- JaVers merge `4e67c0fb200e45249272a2b482f9e85bf96fd762`, Full Nightly
  `45382290108`, automatic snapshot `45382895829`가 성공했다. BOM과 여섯 library는
  `1.2.0-20261124.111949-3`; POM/module/JAR 응답을 확인했다.
- Leader merge `87a2a17609b837e159f258298b29d43c3000d631`, fresh Full Nightly
  `45385099200`, automatic snapshot `45386325388`이 성공했다. BOM과 16개 library는
  `1.2.0-20261124.114320-4`; POM/module/JAR 응답이 모두 HTTP 200이다.
- Text merge `73b306b734bf21eaf070f0da32f4f5847b40dc34`, Full Nightly
  `45388703877`, automatic snapshot `45389245283`이 성공했다. BOM과 다섯 library는
  `1.2.0-20261124.120046-3`; POM/module/JAR 응답이 모두 HTTP 200이다.
- Projects, AWS, Experimental, Exposed, Graph, Image, JaVers, Leader, Text의 live `develop`
  Settings/CI가 모두 catalog commit `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`을 사용한다.
  Experimental은 catalog-only consumer이며 post-merge CI `45349210797`은 성공했다.
  Dependency Submission `45349210872`는 central snapshot 게시 전이라 아직 실패 상태이며,
  Dependencies `2.2.0-SNAPSHOT` 게시 후 실패 job을 다시 실행해 제출을 확인한다.

## 2026-11-24 PR #291 재검증 준비

- PR #291은 `develop` 대상 OPEN, head `08cdb92297a1494662ef2918dfe02f79409089c6`,
  merge state `CLEAN`이다. CI run `45380017787`의 9개 PR checks와 별도 Dependabot
  `submit-gradle` check가 모두 PASS했다. Cross-repository Publication POM Contract도
  PASS했으며, current source diff에서 해결되지 않은 P0/P1은 없다.
- Live read-back에서 review submission, inline review thread/comment, issue comment는
  모두 0개였다. 독립 code-reviewer 시도는 실행 파일
  `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host` 부재로 verdict를 내지 못했다.
  이때까지의 검토는 인라인 fallback이며 독립 리뷰 attestation으로 간주하지 않는다.
- 이 체크리스트와 리뷰 문서를 최신 evidence로 갱신한 뒤 새 PR head의 필수 CI와
  publication-POM contract를 다시 확인한다. 이어 최종 exact-head 리뷰·review/thread/
  mergeability read-back을 하고 #291을 guarded merge한다. 중앙 CI 성공과 자동 snapshot,
  Sonatype read-back 전에 Experimental Dependency Submission과 최종 verifier는 끝난 것으로
  표시하지 않는다.

## 2026-11-24 PR #291 문서 갱신 writer DoD

- **SPW-01 — 완료.** 독자는 Dependencies BOM maintainer다. 목적은 PR #291의 다음 개발선 검토 결과와 새 consumer snapshot 증거를 정확한 범위와 함께 남기는 것이다. 근거는 live PR/CI, manifest/verifier diff, catalog tag, consumer 설정, Sonatype metadata와 artifact 응답이다.
- **SPW-02 — 완료.** 인라인 리뷰에 범위, 수정된 발견 사항, 현재 diff 검토, 아키텍처 순서, 검증 결과, 독립 리뷰 한계와 남은 merge/publication hold를 기록했다.
- **SPW-03 — 완료.** 한국어 문장과 코드·artifact·버전 토큰을 구분했다. `SNAPSHOT`, metadata, POM, Gradle module, JAR는 Maven 게시 맥락의 정확한 식별자로 유지했다.
- **SPW-04 — 완료.** PR/CI 상태, 9개 consumer SHA, 8개 publisher 버전·run, 중앙 publish 보류 사유를 각각 live evidence에 연결했다. 과거 head의 CI를 이번 문서 보정 head의 검증으로 간주하지 않는다.
- **SPW-05 — 완료.** 변경한 checklist와 `docs/reviews/2026-11-24-pr-291-inline-review.md`를 전체 읽고 제목, 목록, 명령·버전 문자열 및 진행 상태를 확인했다. 새 PR head CI/POM contract와 최종 merge 상태는 아직 pending으로 남겼다.
- **KO-01..KO-06 — 완료.** 근거·수치·식별자·불확실성을 보존하고, 불필요한 강조나 번역체를 제거했으며, 변경한 두 문서의 reader-facing 표면을 읽었다.
- **KO-07 — 완료.** `audit-korean-terms.mjs --series clinic-appointment --json` 결과는 두 파일에서 63건이며 모두 `snapshot-loanword`다(checklist 56건, review 7건). 모든 발생은 Maven `-SNAPSHOT`, Maven Central snapshot metadata/artifact, 또는 그 게시 절차를 가리킨다. 일반 도메인 데이터 snapshot 용례는 없어 기술 용어를 유지한 intentional exception으로 판정했다.
