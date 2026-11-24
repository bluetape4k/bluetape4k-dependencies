# bluetape4k 2.2.0 개발선 체크리스트

상태: **역사 기록 — 2026-11-22 catalog train은 2026-11-24 보정 train으로 대체됨**

> 이 문서는 `catalog/2026-11-22-01` 및 catalog commit
> `7a5995fd46031ce1faf16337fa08d954436f8f9a`를 기준으로 진행한 이전 train의
> 기록을 보존합니다. 이 문서의 artifact 검증을 현재 보정 train의 완료 증거로
> 재사용하지 않습니다. 현재 기준인 `catalog/2026-11-24-01`과 commit
> `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`의 진행 상태는
> [2026-11-24 보정 체크리스트](2026-11-24-dependencies-2.2.0-corrective-snapshot-checklist.md)에서
> 추적합니다.

## 고정 입력

- 안정 기준: `bluetape4k-dependencies:2.1.0`, Projects/Exposed `2.1.0`,
  AWS/Graph/Image/JaVers/Leader/Text `1.1.0`
- 다음 중앙 개발선: `bluetape4k-dependencies:2.2.0-SNAPSHOT`
- 다음 내부 BOM: Projects/Exposed `2.2.0-SNAPSHOT`, 나머지 publisher
  `1.2.0-SNAPSHOT`
- 공통 snapshot catalog commit: `7a5995fd46031ce1faf16337fa08d954436f8f9a`
  (`catalog/2026-11-22-01`, tag object
  `f2f53729ee7007bb40adf1ed892a9c160a03ec2e`)
- 공식 release consumer: `bluetape4k-dependencies:2.1.0`과 안정 catalog
  `1669b069690864be8a19a67598e9ac9db807f9f5` 유지

## 의존성 순서

중앙 BOM은 내부 하위 BOM을 import하므로 중앙 snapshot을 먼저 공개하지
않습니다. 다음 순서를 지킵니다.

1. `bluetape4k-projects` `2.2.0-SNAPSHOT`
2. Projects snapshot을 확인한 뒤 `bluetape4k-exposed` `2.2.0-SNAPSHOT`
3. AWS, Graph, Image, JaVers, Leader, Text `1.2.0-SNAPSHOT`을 각 publisher의
   dependency edge에 따라 순차 공개
4. 8개 하위 BOM의 Central metadata/POM/Gradle Module Metadata를 모두 확인
5. 하위 BOM을 import하는 중앙 `bluetape4k-dependencies:2.2.0-SNAPSHOT`
   공개
6. `verify-post-publish-next-development-line.py --require-artifacts`, 전체
   publication-POM gate, downstream smoke를 재실행

순서가 바뀌면 이후 POM/CI 증거를 폐기하고 최초 실패한 predecessor부터
재검증합니다. 중앙 BOM을 먼저 공개해 미게시 하위 snapshot을 가리키는 우회는
허용하지 않습니다.

## Projects 2.1.0 GitHub Release 복구

- 상태: **복구 완료** — [GitHub Release 2.1.0](https://github.com/bluetape4k/bluetape4k-projects/releases/tag/2.1.0)
  게시 `2026-11-22T14:01:55Z`; `Latest` read-back 확인
- 대상: `bluetape4k-projects` 정식 `2.1.0` minor release
- 최신 외부 버전: `2.1.0`; Maven Central의 `bluetape4k-bom:2.1.0`
  POM과 Gradle module metadata가 모두 HTTP 200
- 서명 tag: annotated tag object `6a8d9061f89867fac9ea152bfe7f2a4918dc6367`,
  peeled release commit `1b8105f4948400deae6e5a4b54ad5766d63c9296`
- 게시 증거: exact-tag Publish Release run
  [44905597581](https://github.com/bluetape4k/bluetape4k-projects/actions/runs/44905597581)
  성공. workflow가 같은 commit의 Full Nightly 사전 검증도 통과시켰다.
- Full Nightly 증거: release commit `1b8105f4948400deae6e5a4b54ad5766d63c9296`의
  [run 44902182953](https://github.com/bluetape4k/bluetape4k-projects/actions/runs/44902182953)
  성공; Publish Release workflow의 같은 commit 검증도 통과했다.
- live read-back: GitHub `releases/latest`와 tag 조회에서 `2.1.0`이 현재
  최신 release로 확인됐다. Central 좌표
  `io.github.bluetape4k:bluetape4k-bom:2.1.0`의 POM과 Gradle module metadata는
  HTTP 200이며, exact-tag Publish Release run `44905597581`은 동일 release
  commit에서 성공했다.
- 공개 노트 기준: tag의 `CHANGELOG.md` `[2.1.0] - 2026-11-21` 요약을 사용하고,
  마지막 비교 링크는 실제 직전 release `2.0.0...2.1.0`으로 고정한다.
- 사용자 권한: 앞서 승인한 정식 배포 범위와 이번 next-development 진행 승인에
  따라 기존 공개 tag에 GitHub Release metadata를 복구한다.
- 실행 결과: 기존 `2.1.0` tag를 검증하고 GitHub Release metadata만 생성했다.
  live body에서 요약, 관련 PR, Central 검증, `2.0.0...2.1.0` 비교 링크를
  확인했다. tag 생성, 재태그, artifact 재게시, workflow dispatch는 하지 않았다.

## Snapshot 실행 고정 및 승인

- 실행 흐름: 공통 catalog 변경을 포함한 `catalog-train-snapshot`; 안정 릴리스가
  아닌 next-development snapshot train이다.
- 안정 기준과 최신 외부 버전: Dependencies `2.1.0`, Projects/Exposed `2.1.0`,
  AWS/Graph/Image/JaVers/Leader/Text `1.1.0`. Exposed의 `2.1.0` BOM POM과
  Gradle module metadata가 Maven Central에서 HTTP 200이며 GitHub 최신 release도
  `2.1.0`이다.
- 현 대상: Exposed `io.github.bluetape4k.exposed:bluetape4k-exposed-bom`
  `2.2.0-SNAPSHOT`; `gradle.properties`는 `baseVersion=2.2.0`, 빈
  `snapshotVersion=`이다. Exposed `2.2.0-SNAPSHOT` Central metadata는 아직
  HTTP 404이며 이는 publish 전의 기대 상태다.
- 같은 소비자 catalogRef: `7a5995fd46031ce1faf16337fa08d954436f8f9a`
  (`catalog/2026-11-22-01`; tag object
  `f2f53729ee7007bb40adf1ed892a9c160a03ec2e`).
- 소비자 범위: Projects, Exposed, AWS, Graph, Image, JaVers, Leader, Text 및
  최종 Dependencies BOM. 모두 이 동일한 immutable SHA를 사용하고, 안정 배포
  소비자는 Dependencies `2.1.0`과 catalog
  `1669b069690864be8a19a67598e9ac9db807f9f5`를 유지한다.
- 선행 산출물: Projects `2.2.0-SNAPSHOT`의 BOM/core/io metadata, timestamped
  POM 및 Gradle module metadata가 모두 HTTP 200이다. 공통 timestamp는
  `20261122.150930-1`이다.
- Exposed artifact matrix: exact candidate SHA
  `0396c827fbaf946663775c62c51978242f133463`의 CI run `45040871055`에서
  `production-abi-inventory` artifact `14761413962`를 확인했다. publication
  inventory는 BOM 1개와 게시 모듈 45개, 총 46개 좌표다. Publish Snapshot
  run `45052012962`가 merge SHA `93ca607d12fd09f98c867df870dbbd4a60cb95dd`에서
  성공했다. `io.github.bluetape4k.exposed` 46개 전체 metadata, timestamped
  POM, Gradle module metadata와 metadata가 제공하는 JAR가 Central snapshot
  저장소에서 HTTP 200이며 공통 값은 `2.2.0-20261122.180002-1`이다.
- Dispatch hold: `nightly-tests.yml`은 required choice input `scope`에
  `full`/`smoke`를 선언한다. `publish-snapshot.yml`은 `develop`의 성공한
  Nightly `workflow_run`에서 자동 실행된다. Full Nightly만 dispatch하고
  Publish Snapshot을 수동 dispatch하지 않는다.
- 승인: 사용자가 PR #939 exact head
  `0396c827fbaf946663775c62c51978242f133463` 병합 및 기존 순서의 snapshot
  train 진행을 승인했다.

## AWS 실행 체크리스트

- **대상:** `io.github.bluetape4k.aws:bluetape4k-aws-bom:1.2.0-SNAPSHOT`; 최신 정식 버전은 GitHub 최신 release `1.1.0` (`2026-11-22T01:41:58Z`)이며 `bluetape4k-aws-bom:1.1.0` 및 `bluetape4k-aws-java:1.1.0` POM이 Maven Central에서 HTTP 200이다.
- **정확한 후보:** PR #687, `develop` 대상, exact head `fd2c584903671c894a0a35da262d30d852065e43`; `baseVersion=1.2.0`, 빈 `snapshotVersion=`, 공통 catalogRef `7a5995fd46031ce1faf16337fa08d954436f8f9a`.
- **순서 선행물:** Projects에서 AWS 직접 참조하는 `core`, `io`, `netty`, `idgenerators`, `jackson3`, `resilience4j`, `coroutines` 7/7의 snapshot metadata/POM/Gradle module/JAR가 `20261122.150930-1`에서 HTTP 200이다. Exposed의 게시 inventory 46/46 metadata/POM/Gradle module 및 제공 JAR는 `20261122.180002-1`에서 HTTP 200이다.
- **후보 검토/merge:** exact head `fd2c584903671c894a0a35da262d30d852065e43`에서 독립 코드 리뷰 `APPROVE`, architecture `CLEAR`, P0–P3 0건이다. GitHub review/thread는 0개였고 `mergeStateStatus=CLEAN`, `mergeable=MERGEABLE`을 확인해 `--squash --match-head-commit fd2c584903671c894a0a35da262d30d852065e43`로 병합했다. merge commit은 `e48b7040de23bbf857525d8094f3d06123a1bbb7`이며 canonical `develop`도 clean fast-forward 동기화했다.
- **CI 이력:** run `45018328607` attempt 1은 Projects/Exposed 선행 snapshot 미공개로 실패했다. 공개 후 attempt 2에서는 Gitleaks 설치가 GitHub Releases API HTTP 403으로 실패했고 `aws-spring-boot-exposed-examples`가 Gradle Kotlin DSL의 전이 Kotlin `2.4.10` artifact를 Plugin Portal에서 resolve하지 못했다. 같은 좌표는 Maven Central에 존재한다. PR exact-head run `45056211283`은 Gitleaks, compile, 전체 module/example/ABI/coverage 포함 20/20 jobs 성공했다. merge-push CI `45057867438`도 merge SHA `e48b7040de23bbf857525d8094f3d06123a1bbb7`에서 20/20 jobs 성공했다.
- **Dispatch·Nightly:** `.github/workflows/nightly-tests.yml`의 유일한 수동 입력은 필수 `scope` (`full`/`smoke`)이며 선택값은 `full`이다. `.github/workflows/publish-snapshot.yml`은 `develop`의 성공한 Nightly `workflow_run`으로 자동 게시한다. merge 뒤 exact develop SHA `e48b7040de23bbf857525d8094f3d06123a1bbb7`에서 Full Nightly `45059460948`이 10/10 jobs 성공했다. Publish Snapshot은 수동 dispatch하지 않았다.
- **자동 snapshot·공개 검증:** 자동 Publish Snapshot `45060168924`가 동일한 SHA에서 성공했다. `io.github.bluetape4k.aws`의 BOM과 5개 모듈, 총 6개 coordinate의 Central snapshot metadata 및 metadata가 열거한 58개 POM/module/JAR/source/javadoc/test-fixtures/signature 파일이 모두 HTTP 200이다. 여섯 metadata의 공통 timestamp는 `20261122.192306-1`이다.
- **문서 링크 검증:** AWS PR은 README의 공개되지 않은 `/1.1/` 경로를 영문·한국어 unversioned 기본 경로로 바꿨다. 기본 경로 두 개는 HTTP 200, `/1.1/` 두 경로는 HTTP 404다. WIP 기준일도 `2026-11-23 KST`로 갱신했다. Central manual manifest의 최신 AWS 내용은 아직 `1.0`이므로 stable-doc handoff는 별도 잔여 작업이다.

## Exposed 실행 체크리스트

- [x] **PUB-01 — 릴리스 신원과 권한 고정**
  - **Action:** snapshot 대상, 최신 안정 버전, catalogRef, 소비자 범위와 권한을 고정한다.
  - **Evidence:** 위 Snapshot 실행 고정 및 승인 섹션; PR #939 exact head `0396c827…`; 승인 확인.
  - **Failure:** 대상이나 권한이 바뀌면 merge/dispatch를 멈추고 checklist를 갱신한다.
- [x] **PUB-02 — topology와 선행 publisher 확인**
  - **Action:** live PR 상태를 확인하고 게시 DAG의 선행 publisher를 확인한다.
  - **Evidence:** Projects snapshot `20261122.150930-1` 및 관련 POM/GMM HTTP 200; 아래 PR 표.
  - **Failure:** 미게시 선행물이 확인되면 하위 publisher를 진행하지 않는다.
- [x] **PUB-03 — Exposed 후보 상태 검증**
  - **Action:** 후보 SHA, 공통 catalogRef, CI, Migration Smoke와 publication inventory를 검증한다.
  - **Evidence:** CI run `45040871055` 41/41 jobs 성공; Migration Smoke `45040870932` 성공; stable manual links `45040870998` 성공; artifact inventory 46개.
  - **Failure:** SHA 불일치, 실패/미완료 검사 또는 inventory 차이가 있으면 merge를 중단한다.
- [x] **MERGE-01 — Exposed PR 병합**
  - **Action:** PR #939을 `--squash --match-head-commit 0396c827fbaf946663775c62c51978242f133463`로 병합했다.
  - **Evidence:** PR `MERGED` (`2026-11-22T16:51:25Z`), merge commit 및 canonical `develop` 모두 `93ca607d12fd09f98c867df870dbbd4a60cb95dd`; canonical checkout clean.
  - **Failure:** exact head나 checks가 달라졌거나 merge가 CLEAN이 아니면 중단한다.
- [ ] **PUB-04 — Stable release preflight**
  - **Action:** stable-only preflight를 판정한다.
  - **Evidence:** N/A — 이번 요청은 stable tag/release가 아닌 snapshot train이다.
  - **Failure:** scope에 stable publication이 추가되면 stable checklist를 새로 적용한다.
- [x] **PUB-05 — Full Nightly dispatch hold**
  - **Action:** merge 뒤 canonical `develop` SHA와 workflow input을 재확인하고 `scope=full`만 dispatch한다.
  - **Evidence:** canonical/remote `develop` SHA `93ca607d12fd09f98c867df870dbbd4a60cb95dd`; `baseVersion=2.2.0`, 빈 `snapshotVersion=`, 공통 catalogRef `7a5995fd46031ce1faf16337fa08d954436f8f9a`; merge-push CI `45046150363` 41/41 성공; Full Nightly `45049722415` attempt 2가 같은 SHA에서 51/51 성공; 자동 Publish Snapshot `45052012962` 성공.
  - **Failure:** branch/SHA/schema가 바뀌거나 prerequisite CI가 실패하면 dispatch하지 않는다.
- [x] **PUB-06 — Snapshot publication 및 Central 검증**
  - **Action:** 성공 Nightly에 자동 연결된 Publish Snapshot을 모니터링하고 46개 좌표를 확인한다.
  - **Evidence:** Nightly `45049722415` attempt 1의 HTTP 429는 attempt 2에서 복구되어 51/51 성공했다. 자동 Publish Snapshot `45052012962`도 성공했다. `io.github.bluetape4k.exposed`의 inventory 46개 좌표 전체에서 공통 timestamp `20261122.180002-1`의 Central snapshot metadata, timestamped POM, Gradle module metadata와 제공되는 JAR가 모두 HTTP 200이다.
  - **Failure:** 누락/404가 하나라도 있으면 다음 publisher로 진행하지 않는다.
- [ ] **PUB-07 — Stable GitHub Release closeout**
  - **Action:** stable release closeout 적용 여부를 판정한다.
  - **Evidence:** N/A — snapshot-only 실행이며 tag/GitHub Release를 만들지 않는다.
  - **Failure:** stable scope가 추가되면 별도 승인과 stable preflight 없이는 진행하지 않는다.
- [ ] **PUB-08 — downstream consumer 동기화 검증**
  - **Action:** child BOM snapshot이 모두 공개된 뒤 Dependencies POM gate와 consumer smoke를 다시 실행한다.
  - **Evidence:** 전체 publisher POM gate, `--require-artifacts`, repository별 consumer 결과.
  - **Failure:** 미게시 참조 또는 서로 다른 catalogRef가 있으면 중앙 BOM을 publish하지 않는다.
- [ ] **PUB-09 — 다음 개발선 공개**
  - **Action:** Exposed `2.2.0-SNAPSHOT`와 후속 repo들의 snapshot line을 공개한다.
  - **Evidence:** 각 source SHA, Full Nightly/자동 Publish Snapshot run, Central matrix.
  - **Failure:** 각 repo의 선행 edge가 공개되지 않았으면 해당 repo를 보류한다.
- [ ] **PUB-10 — stable public-doc/manual handoff**
  - **Action:** stable 문서 handoff 적용 여부를 판정한다.
  - **Evidence:** N/A — snapshot-only 실행이며 stable tag/manual release를 만들지 않는다.
  - **Failure:** stable release가 추가되면 central manual handoff 절차를 적용한다.
- [ ] **PUB-11 — 전체 snapshot train 결과 보고**
  - **Action:** 모든 library 및 Dependencies snapshot, run URL, SHA, artifact matrix와 잔여 위험을 보고한다.
  - **Evidence:** applicable check totals reconciled; 각 publisher의 public metadata/POM/GMM와 consumer gate.
  - **Failure:** 누락된 artifact나 unchecked item이 있으면 최종 상태를 PENDING으로 유지한다.

## PR 및 검증 상태

| 저장소 | PR | exact head | 상태 |
|---|---:|---|---|
| Projects | #1914 | `96663caae7bd69ed33d15f418bb6d6c76a010ab9` → merge `905b9efa1ac164ff33c8f935112c7c63bc2feebe` | MERGED; Full Nightly `45033138283` 및 자동 Publish Snapshot `45036217435` 성공; 2.2.0 snapshot 공개 |
| AWS | #687 | `fd2c584903671c894a0a35da262d30d852065e43` → merge `e48b7040de23bbf857525d8094f3d06123a1bbb7` | MERGED; exact-head CI 20/20, 독립 리뷰 PASS; merge-push CI `45057867438` 20/20, Full Nightly `45059460948` 10/10, 자동 Publish Snapshot `45060168924` 성공; artifact 58/58 HTTP 200 (`20261122.192306-1`) |
| Exposed | #939 | `0396c827fbaf946663775c62c51978242f133463` → merge `93ca607d12fd09f98c867df870dbbd4a60cb95dd` | MERGED; merge-push CI 41/41, Full Nightly attempt 2 51/51, 자동 Publish Snapshot 성공; Central snapshot artifact 46/46 검증 완료 (`20261122.180002-1`) |
| Graph | #667 | `d1d35342dffffc095412f79a0b2352cc74c9f06e` → merge `c6929fb13c8165b8b65a17c84e2a915dc4ae509c` | MERGED; PR CI 21/21, merge-push CI 16/16, Examples 2/2 및 Dependency Submission/Testcontainers/branch governance 통과; Full Nightly `45064023557`, 자동 Publish Snapshot `45064802522` 성공; Central metadata 16/16, 열거 파일 158/158 HTTP 200 (`20261122.201103-1`) |
| Image | #713 | `645bca54a66d2b713db8d1b88412b6b06507a2a7` → merge `10604b9fd2b0674ee197ec2dc8e301030da3b774` | MERGED; exact-head CI `45097195284`, Examples `45097195216`, native acceptance `45098486769`, merge-push CI `45100119160`, Examples `45100119205` 통과; Full Nightly `45101476364` 16/16 및 자동 Publish Snapshot `45102359594` 성공; Central metadata 11/11, metadata-listed 파일 108/108 HTTP 200 (`1.2.0-20261123.025144-1`) |
| JaVers | #404 | `3eb8191e9ce64041be4bcdfa0d35942f31e1fd0a` → `52a1ee2b175418bc17fb7b1f0cdf1087a78d7eaa` → merge `09e9ada10e42bd46c8f181f9ad5e574a10a805f6` | MERGED; PR/merge-push CI 17/17, 독립 정적 리뷰 APPROVE (P0-P3 0); Full Nightly `45106603820` 13/13, 자동 Publish Snapshot `45107016698` 성공; Central metadata 7/7·파일 64/64 HTTP 200 (`20261123.033837-1`) |
| Leader | #1020 | `a40190cc67071d3037c1ae32f5e5e4e37b70b77a` → merge `1b08a8654a7096afa29b657e4c37f34a0b733cb9` | MERGED; merge-push CI `45137802372` attempt 2 성공; Full Nightly `45141953279` 29/29, 자동 Publish Snapshot `45143149207` 성공; Central metadata 17/17 및 파일 166/166 HTTP 200 (`20261123.090259-1`) |
| Text | #353 | `4a0bd5227ad14bc779395383d952fcbb9240c49b` → merge `c28141c284cdcb2bf18cb67d20d3bf573e385dce` | MERGED; merge-push CI `45148610033` 13/13, Full Nightly `45149782464` 10/10, 자동 Publish Snapshot `45150411687` 성공; Central metadata 6/6 및 파일 54/54 HTTP 200 (`20261123.095025-1`) |
| Dependencies | #291 | `46ab8a42f20a2db2020cf0dae7244506ca6cf0a4` → audit-pointer repair pending push | attempt 2 Build BOM 실패 원인은 현재 catalog SHA와 latest-stable inventory/audit 입력 SHA의 불일치. 로컬 audit 검사와 49 tests 통과; 독립 review runtime unavailable, 새 exact-head CI 대기 |

## Graph 인라인 fallback 코드 리뷰

- 대상: Graph PR #667, exact head `d1d35342dffffc095412f79a0b2352cc74c9f06e`; base `develop` / stable tag `1.1.0` commit `5527bdc21aa366602b7212191ddb6d87849c8b7a`.
- 검토 범위: 8개 파일, 20 insertions / 17 deletions. workflow와 settings의 catalog SHA, `baseVersion` / `snapshotVersion`, README·CHANGELOG·WIP의 release/development line. Kotlin source, tests, ABI, lifecycle, security 변경은 없다.
- 버전 근거: GitHub Release `1.1.0` 게시 `2026-11-21T16:32:59Z`, annotated tag peel이 `5527bdc...`와 일치하고 Graph BOM `1.1.0` POM은 Maven Central HTTP 200이다. 후보는 `baseVersion=1.2.0`, 빈 `snapshotVersion=`, 공통 catalog SHA `7a5995fd46031ce1faf16337fa08d954436f8f9a`다.
- 검증: `git diff --check` 통과. PR CI attempt 3은 같은 exact head에서 성공했고 현재 21/21 checks pass; review thread 0, mergeability `CLEAN/MERGEABLE`.
- 독립 리뷰 시도: reviewer agent가 diff 확인 전에 실행 환경의 `codex-code-mode-host` 부재와 CUA 비가용으로 verdict를 내지 못했다. 정해진 fallback을 사용했으며 같은 reviewer 재호출은 하지 않았다.
- 인라인 결과: P0=0, P1=0, P2=0, P3=0; 미해결 사항과 disposition 없음. verdict는 **APPROVE (inline fallback; independent attestation 아님)**이다. 별도 독립 리뷰 attestation은 확보되지 않았다.
- 다음 게이트: Graph merge-push CI, Examples, Dependency Submission, Testcontainers 계약, branch governance가 모두 통과했고 develop은 merge SHA에서 clean하다. exact develop SHA의 Full Nightly `45064023557`과 자동 Publish Snapshot `45064802522`가 성공했다. Central snapshot metadata 16/16과 각 metadata가 열거한 timestamped 파일 158/158이 모두 HTTP 200이며 공통 값은 `1.2.0-20261122.201103-1`이다. Graph 완료 후 Image PR #713으로 진행한다. Publish Snapshot을 수동 dispatch하지 않는다.

## JaVers next-development 검증

- 대상: JaVers PR #404, base `develop`, exact head `52a1ee2b175418bc17fb7b1f0cdf1087a78d7eaa`; PR은 OPEN, MERGEABLE이다. 공통 catalogRef는 `7a5995fd46031ce1faf16337fa08d954436f8f9a`, `baseVersion=1.2.0`, 빈 `snapshotVersion=`이다.
- 리뷰에서 확인된 P2는 WIP의 오래된 기준일이었다. `WIP.md`를 `2026-11-23 KST`로 고친 커밋 `52a1ee2`를 올렸고, 독립 exact-head 정적 리뷰에서 P0-P3 0, APPROVE를 받았다.
- exact-head CI run `45104161925`는 catalog governance, compile, 9개 module/example test jobs, ABI/POM, coverage, security 및 aggregate를 포함해 17/17 성공했다. 변경 후 `git diff --check`도 통과했다.
- GitHub review-thread read-back은 0개이며 GitHub reviewDecision은 비어 있다. human-review subgate는 N/A (single-developer lane)이고, 독립 정적 리뷰는 별도로 APPROVE다.
- GitHub review/thread, mergeability와 exact-head CI를 다시 읽은 뒤 PR을 exact head `52a1ee2b175418bc17fb7b1f0cdf1087a78d7eaa`에서 guarded squash-merge했다. merge SHA `09e9ada10e42bd46c8f181f9ad5e574a10a805f6`와 원격 `develop`이 일치한다.
- merge-push CI `45105522017`은 merge SHA에서 17/17 jobs 성공했고 Dependency Submission `45105522008`도 성공했다. canonical remote `develop` SHA는 merge SHA `09e9ada10e42bd46c8f181f9ad5e574a10a805f6`와 일치한다.
- Nightly YAML `.github/workflows/nightly-tests.yml`의 exact merge SHA inputs는 필수 `scope` choice이며 허용값은 `smoke`/`full`; 실행은 `full`이었다. Full Nightly `45106603820`은 같은 SHA에서 13/13 jobs 성공했다. Publish Snapshot `45107016698`은 성공한 Nightly의 `workflow_run`으로 자동 실행·성공했으며 수동 dispatch하지 않았다.
- artifact matrix는 `io.github.bluetape4k.javers`의 `bluetape4k-javers-bom`, `javers-core`, `javers-ddd`, `javers-exposed`, `javers-persistence-kafka`, `javers-persistence-redis`, `javers-spring-boot4-autoconfigure` 7개다. 사전 version-specific metadata는 목표 `1.2.0-SNAPSHOT` 7/7 HTTP 404였다.
- 공개 검증: 목표 snapshot metadata 7/7 HTTP 200, metadata-listed 파일 64/64 HTTP 200이며 공통 timestamp는 `20261123.033837-1`이다. artifact-level latest metadata도 7/7 `1.2.0-SNAPSHOT`을 가리킨다.

## Leader 1.2.0-SNAPSHOT 실행 고정

- 대상은 Leader PR #1020 merge SHA `1b08a8654a7096afa29b657e4c37f34a0b733cb9`의 `1.2.0-SNAPSHOT`이며, Maven group은 `io.github.bluetape4k.leader`다. 동일한 catalogRef `7a5995fd46031ce1faf16337fa08d954436f8f9a`를 사용한다.
- 기대 artifact matrix는 17개 POM: BOM `bluetape4k-leader-bom`과 `bluetape4k-leader-core`, `bluetape4k-leader-redis-lettuce`, `bluetape4k-leader-redis-redisson`, `bluetape4k-leader-exposed-core`, `bluetape4k-leader-exposed-jdbc`, `bluetape4k-leader-exposed-r2dbc`, `bluetape4k-leader-mongodb`, `bluetape4k-leader-hazelcast`, `bluetape4k-leader-zookeeper`, `bluetape4k-leader-etcd`, `bluetape4k-leader-consul`, `bluetape4k-leader-dynamodb`, `bluetape4k-leader-k8s`, `bluetape4k-leader-spring-boot`, `bluetape4k-leader-ktor`, `bluetape4k-leader-micrometer`다. `benchmark`는 `isNonPublishedProject()`로 publication에서 제외된다. `build.gradle.kts`는 license gate에서 17개 POM을 요구한다.
- 최신 안정 artifact `bluetape4k-leader-bom:1.1.0`의 Maven Central POM은 HTTP 200이다. target BOM snapshot metadata는 게시 전 조회에서 HTTP 404이며, source `baseVersion=1.2.0`, 빈 `snapshotVersion=`과 일치한다.
- dispatch hold read-back: remote `develop`은 merge SHA와 일치하고 open PR은 없다. Full Nightly YAML은 필수 `scope`만 선언하며 허용값은 `smoke`/`full`; 이번 dispatch 값은 `full`이다. Publish Snapshot은 동일 `develop` SHA의 성공 Nightly `workflow_run`에서 자동 실행되므로 수동 dispatch하지 않는다.
- merge-push CI run `45137802372` attempt 1의 Maven Central HTTP 429는 같은 SHA의 attempt 2에서 복구됐고 필수 job 및 `CI Status`가 모두 성공했다. Full Nightly `45141953279`는 29/29 jobs 성공했고 자동 Publish Snapshot `45143149207`도 성공했다. Central artifact metadata 17/17과 metadata-listed 파일 166/166이 HTTP 200이며 공통 timestamp는 `20261123.090259-1`이다.

## Text 1.2.0-SNAPSHOT 실행 고정

- Text PR #353 exact head `4a0bd5227ad14bc779395383d952fcbb9240c49b`는 merge SHA `c28141c284cdcb2bf18cb67d20d3bf573e385dce`로 병합됐다. merge-push CI `45148610033`은 13/13 jobs 성공했다.
- exact merge SHA의 Nightly workflow는 dispatch input이 없어 전체 matrix가 실행됐다. Full Nightly `45149782464`는 10/10 jobs 성공했고, 자동 Publish Snapshot `45150411687`은 성공한 Nightly의 `workflow_run`으로 실행·성공했다. 수동 snapshot dispatch는 하지 않았다.
- `io.github.bluetape4k.text`의 `tokenizer-core`, `tokenizer-japanese`, `tokenizer-korean`, `lingua`, `text-search`, `bluetape4k-text-bom` 6개 좌표 metadata와 metadata-listed 파일 54/54가 HTTP 200이며 공통 timestamp는 `20261123.095025-1`이다.
- Text도 공통 catalogRef `7a5995fd46031ce1faf16337fa08d954436f8f9a`를 사용한다.

## 현재 증거와 정지 조건

- `scripts/verify-post-publish-next-development-line.py --summary`는
  `8 publishers`, `9 snapshot libraries`, `5 official-release examples`,
  `0 development-snapshot examples`를 확인했습니다.
- 이 train의 receipt state root는 worktree 루트가 아니라
  `.bluetape/snapshot-train-2026-11-23`입니다. helper 실행 시 이 경로를
  `--state-root`로 지정합니다. 2026-11-24 read-back에서 `verify` sequence 57,
  `resume-check` topology gap 0건을 확인했습니다.
- 개발선/CI 계약 회귀 테스트 47개가 통과했습니다.
- Projects #1914는 merge commit `905b9efa…`로 병합됐고, Full Nightly 및
  자동 Publish Snapshot이 모두 성공했다. BOM/core/io의
  `2.2.0-SNAPSHOT` metadata, timestamped POM과 Gradle module metadata가
  공통 timestamp `20261122.150930-1`에서 HTTP 200이다.
- AWS는 Projects 7/7 및 Exposed 46/46 선행 artifact 공개 후 PR exact-head CI가
  20/20 통과했고 merge SHA `e48b7040de23bbf857525d8094f3d06123a1bbb7`로
  동기화했다. merge-push CI `45057867438`도 20/20, Full Nightly `45059460948`도
  10/10 성공했다. 자동 Publish Snapshot `45060168924`와 AWS 6개 coordinate의
  metadata 및 열거 파일 58/58이 공통 timestamp `20261122.192306-1`로 공개됐다.
  다음 순서인 Graph PR #667은 merge SHA `c6929fb13c8165b8b65a17c84e2a915dc4ae509c`로 병합했다. merge-push CI `45062979019`와 Full Nightly `45064023557`, 자동 Publish Snapshot `45064802522`가 모두 같은 merge SHA에서 성공했다. Central `io.github.bluetape4k.graph`의 BOM/모듈 16개 metadata와 metadata-listed timestamped 파일 158개가 모두 HTTP 200이며 공통 timestamp는 `20261122.201103-1`이다.
- JaVers, Leader, Graph, Image 및 Dependencies의 기존 red checks는 각 선행 artifact
  공개 시점 전후에 실행됐다. 각 repository 차례가 오면 현재 exact head, 선행
  artifact, 전체 checks를 다시 확인한다. Graph 실패는 코드 테스트가 시작되기 전에
  Kover `0.9.11` POM 요청이 Maven Central HTTP 429를 반환한 일시적 dependency-fetch
  실패였으며, coverage artifact 누락은 그 후속 결과다. 같은 exact head의 attempt 3은
  Kover 해석, Ktor Graph 테스트, coverage aggregate, 전체 CI가 모두 통과했다.
  인라인 fallback 리뷰는 P0-P3 미해결 없이 APPROVE이며 독립 attestation이 아님을
  기록했다. PR review thread는 0이었다. 후속 상태 read-back에서 merge-push CI
  `45062979019` 16/16, Examples `45062979083` 2/2, Dependency Submission
  `45062979024`, Testcontainers 계약 `45062978927`, branch governance
  `45062979155`가 모두 성공했다. canonical `develop`은 merge SHA에 clean하게
  동기화됐다. Central snapshot 저장소의 Graph BOM/core `1.2.0-SNAPSHOT` metadata는
  사전 조회 HTTP 404여서 최초 publish 상태와 일치한다. Full Nightly run
  `45064023557`이 merge SHA에서 성공했고 자동 Publish Snapshot `45064802522`도
  성공했다. Central `io.github.bluetape4k.graph`의 BOM/모듈 16개 metadata와
  metadata-listed timestamped 파일 158개가 모두 HTTP 200이며 공통 timestamp는
  `20261122.201103-1`이다. Publish Snapshot은 성공한 Nightly의 `workflow_run`에서만
  자동 실행하며 수동 dispatch하지 않았다.
- Image PR #713의 exact candidate `645bca54a66d2b713db8d1b88412b6b06507a2a7`은
  CI `45097195284`, Examples `45097195216`, native acceptance `45098486769`와
  독립 code review APPROVE를 통과했다. merge SHA
  `10604b9fd2b0674ee197ec2dc8e301030da3b774`의 merge-push CI `45100119160`,
  Examples `45100119205`, Full Nightly `45101476364` 16/16 및 자동 Publish
  Snapshot `45102359594`가 성공했다. Central `io.github.bluetape4k.image`의
  10개 JVM library와 BOM, 총 11개 metadata 및 metadata-listed 108개 파일이
  모두 HTTP 200이며 공통 timestamp는 `1.2.0-20261123.025144-1`이다. 다음
  publisher JaVers PR #404는 merge SHA `09e9ada10e42bd46c8f181f9ad5e574a10a805f6`에서
  Full Nightly `45106603820`과 자동 Publish Snapshot `45107016698`에 성공했다. Central
  metadata 7/7과 열거 파일 64/64가 HTTP 200이다 (`20261123.033837-1`). Leader PR #1020 exact head `a40190cc67071d3037c1ae32f5e5e4e37b70b77a`는 merge SHA `1b08a8654a7096afa29b657e4c37f34a0b733cb9`로 병합됐다. merge-push CI `45137802372` attempt 1에서는 `examples-cache-warmer`와 `examples-k8s-lease`의 `testCompileClasspath`가 Maven Central HTTP 429 (`junit-jupiter:6.1.3`)를 받았고 각 job이 5회 시도 후 실패했다. 같은 SHA의 attempt 2에서는 두 job과 `CI Status`가 모두 성공했다. Full Nightly `45141953279`는 29/29 jobs 성공했고 자동 Publish Snapshot `45143149207`도 성공했다. Central metadata 17/17과 파일 166/166이 HTTP 200이며 공통 timestamp는 `20261123.090259-1`이다.
- Dependencies #291 CI attempt 1은 13개 consumer canary 중 Clinic만
  `kotlin-compiler-embeddable`/Detekt의 Maven Central SHA-256 검증 항목이 없어
  실패했다. Clinic #496에서 누락된 checksum을 반영하고, Projects부터 Text까지
  선행 artifact를 DAG 순서대로 모두 공개했다.
- 같은 PR의 CI attempt 2 (`45021585315`)는 Build BOM과 aggregate `CI Status`가
  실패했다. `tests.test_audit_latest_stable` 16 failures/1 error의 공통 원인은
  현재 `gradle/libs.versions.toml` SHA가
  `0ef060c3b212141d4d0dcb0d7b75bfec60d42095e9a7f4045454a8446ac9ddc3`인데,
  latest-stable inventory와 audit가 이전 catalog SHA
  `48f7ab2fb9463cfb1a18135f5c8b02e0149cdd098494868419735262fe6caa45`에
  묶여 있던 drift다. 외부 metadata가 바뀐 것은 아니므로 metadata를 다시
  가져오지 않고, 기존 523개 기록과 `retrieved-at`을 보존하며 inventory 입력,
  audit 입력 checksum, current delta audit pointer만 갱신했다.
- 로컬 복구 후 Python 3.13
  `scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary`,
  `python3.13 -m unittest tests.test_audit_latest_stable tests.test_latest_stable_version_deltas`
  (49 tests), `git diff --check`가 통과했다. 다음 증거는 수리된 새 exact PR
  head의 hosted CI다. 이전 red를 green으로 해석하지 않으며, 중앙 BOM 게시와
  publication-POM gate는 새 PR CI가 통과하고 병합된 후 진행한다.
- 독립 리뷰 시도에서는 `code-reviewer` agent가 실행 환경의
  `codex-code-mode-host` 부재로 파일을 읽기 전에 종료됐고, CUA fallback도 사용할
  수 없었다. 따라서 이 lane은 정확히 `failed`로 기록했고 APPROVE verdict를 만들지
  않았다. `architect` lane도 dispatch 전에 startup ACK 기한이 만료되어
  `reservation-expired` 근거와 함께 취소했다. 새 exact-head code-reviewer와
  architect 증거가 확보될 때까지 CG-14와 merge readiness는 PENDING이다.
- Receipt 운영 복구 메모: `bluetape-flow.py --expected-head`는 직전
  `mutation-check`가 반환한 receipt checksum이며 Git commit SHA가 아니다. owner
  파일은 state root의 `handles/` 바로 아래여야 하고, topology JSON은 등록 전에
  파싱 검증한다. startup ACK deadline을 넘긴 미실행 lane은 dispatch하지 않고
  `reservation-expired` 근거로 취소한다. 거부된 helper 호출은 receipt를 변경하지
  않았으며, 이 절차를 다음 수행자가 반복하지 않도록 기록했다.
- 각 merge는 해당 exact head의 fresh CI/review/thread/mergeability를 다시
  읽은 뒤 별도 병합 게이트로 처리합니다.

## DoD

- [x] 안정 release 후 source `baseVersion`과 빈 `snapshotVersion` 계약 고정
- [x] 내부 snapshot catalog와 공식 release consumer 경계 고정
- [x] 문서에 하위 publisher → 중앙 BOM 순서 명시
- [x] Projects 2.1.0 GitHub Release metadata를 기존 tag에서 복구하고 live body/Latest 확인
- [x] 개발선 verifier 및 targeted governance tests 통과
- [x] Projects snapshot 공개 및 Central metadata 확인 (`20261122.150930-1`)
- [x] Exposed snapshot 공개 및 46개 artifact metadata/POM/Gradle module 확인 (`20261122.180002-1`, Publish Snapshot `45052012962`)
- [x] AWS snapshot 공개 및 6개 metadata/58개 metadata-listed 파일 HTTP 200 확인 (`20261122.192306-1`, Publish Snapshot `45060168924`)
- [x] Graph snapshot 공개 및 16개 metadata/158개 metadata-listed 파일 HTTP 200 확인 (`20261122.201103-1`, Publish Snapshot `45064802522`)
- [x] Image snapshot 공개 및 11개 metadata/108개 metadata-listed 파일 HTTP 200 확인 (`20261123.025144-1`, Publish Snapshot `45102359594`)
- [x] JaVers snapshot 공개 및 7개 metadata/64개 metadata-listed 파일 HTTP 200 확인 (`20261123.033837-1`, Publish Snapshot `45107016698`)
- [x] Leader snapshot 공개 및 17개 metadata/166개 metadata-listed 파일 HTTP 200 확인 (`20261123.090259-1`, Publish Snapshot `45143149207`)
- [x] Text snapshot 공개 및 6개 metadata/54개 metadata-listed 파일 HTTP 200 확인 (`20261123.095025-1`, Publish Snapshot `45150411687`)
- [x] latest-stable inventory/audit pointer를 현재 catalog SHA에 재바인딩하고 523개 기존 기록 보존 확인
- [ ] 새 Dependencies #291 exact head hosted CI 통과
- [ ] 새 exact-head independent code-reviewer와 architect verdict 확보
- [ ] fresh exact-head merge approval 및 guarded merge, develop CI 확인
- [ ] 성공 develop CI에서 자동 central Publish Snapshot 후 artifact 검증
- [ ] 중앙 `2.2.0-SNAPSHOT` 공개 및 `--require-artifacts` 통과
- [ ] publication-POM 전수 재검증과 downstream smoke

최종 상태: `PENDING` — 8개 child snapshot은 검증 완료했고, 중앙 BOM publication과
post-publish verifier, 전체 POM gate 및 downstream smoke가 남아 있습니다. PR #291의
새 exact-head hosted CI와 독립 code review도 아직 필요합니다.
