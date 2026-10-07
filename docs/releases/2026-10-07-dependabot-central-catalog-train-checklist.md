# 2026-10-08 중앙 Dependabot catalog train 체크리스트

상태: **PENDING / 중앙 verifier 수정 로컬 검증 완료; exact 교차 저장소 gate와 원격 CI 대기**

## 고정 범위와 중단 조건

- 대상 저장소: `bluetape4k/bluetape4k-dependencies`
- 기준: `develop` / `ef4612ac237550b550dc48eae5ecdfc94b27dab4`
- 후보 브랜치: `fix/dependabot-security-catalog-2026-10`
- 후보 head: 기준 remote head `036b7aeb2e36882fd49ac0938a218d0e8498b202`; verifier·회귀 테스트 및 lesson/checklist 변경은 아직 미커밋
- 최신 published BOM: `2.0.0` (2026-09-02)
- 개발 BOM: `2.1.0-SNAPSHOT` (`baseVersion=2.1.0`, 빈 `snapshotVersion`)
- Flow/class: `catalog-train-snapshot` / `dependencies-only`
- 후보 catalog ref: 후보 커밋의 immutable SHA; tag 생성은 승인 범위 밖
- 현재 승인: 이슈 해결을 위한 중앙 catalog/verifier 수정, 로컬 검증, 관련 consumer 검증
- 별도 exact-target 승인 필요: 새 head push, PR 변경, merge, tag, workflow dispatch, SNAPSHOT/stable publication, 브랜치/worktree 삭제
- Merge hold: `develop` CI 성공 시 `Publish Snapshot` workflow가 자동 실행될 수 있으므로 정확한 head와 SNAPSHOT 결과를 확인한 뒤 별도 승인한다.
- 제외: 기존 PR #254(Kover)·#255(GitHub Actions), 이슈 #256(Kotlin/Detekt 호환성), repo-local tooling 경고

## 2026-10-08 live state

- `gh issue list --repo bluetape4k/bluetape4k-exposed --state open`: 열린 이슈는 #885 하나다. 담당자 `debop`, milestone `2.1.0`, labels `ci`/`dependencies`/`tech-debt`다. 이슈 완료에는 Dependabot 보안 업데이트 성공 run을 확인하거나 해당 경고가 현재 graph에 적용되지 않는다는 live 증거가 필요하다.
- live 조회 기준 원격 consumer/catalog PR은 아래 exact head다. 표의 체크 수는 현재 GitHub PR head의 상태 집계이며 리뷰는 모두 0건이다.

| Repository / PR | Exact remote head | Checks | 현재 상태 |
| --- | --- | ---: | --- |
| Dependencies #257 | `036b7aeb2e36882fd49ac0938a218d0e8498b202` | 6 | 실패/대기 없음. 아래 네 구현/테스트 파일은 이 head에 아직 없음 |
| Projects #1819 | `768a44c8297c3b8bc58538b00cc47c7beebd696e` | 27 | 실패/대기 없음 |
| AWS #658 | `09873d1cce861a27c2aac3e368e99e740a9e9397` | 19 | 실패/대기 없음 |
| Experimental #104 | `040ef88f0c5d263bbfc8b3bcedf96c8d79534e06` | 6 | 실패/대기 없음 |
| Exposed #899 | `bf01557457460b26da49a7299965469682ef83c8` | 13 | `CI Status` 실패, `Coverage Report` queued, Docs-only validation skipped |
| Graph #655 | `da98381342bb90d219f15cc00cb2f1f7bcdf9373` | 21 | 실패/대기 없음 |
| Image #697 | `14034f53c03405655cce37fa9ac27461ea013e50` | 30 | 실패/대기 없음. PaddleOCR native acceptance는 skipped |
| JaVers #396 | `eb02a1897366e2bb773371f2d0b18537b511419d` | 15 | 실패/대기 없음 |
| Leader #955 | `218380a0ff9a5d94f7c2284102fbe2087151ae66` | 46 | 실패/대기 없음 |
| Text #342 | `02a7719368ec9559c17b68b8e060a97ff608678b` | 13 | 실패/대기 없음 |

- Exposed #899 run [37640362574](https://github.com/bluetape4k/bluetape4k-exposed/actions/runs/37640362574)은 exact head `bf015574…`에서 consumer matrix job들이 runner를 시작하지 못한 채 `abandoned`로 기록되어 `Require activated consumer tests`가 실패했다. 같은 head의 build와 benchmark는 성공했다. 비교 run [37400878284](https://github.com/bluetape4k/bluetape4k-exposed/actions/runs/37400878284)은 PR #896의 다른 head `80e77f3fef66671423fa3345ab648ac49bb17620`에서 consumer job을 실행했다. 두 실행 차이는 hosted scheduler 문제라는 추론을 뒷받침할 뿐 원인을 입증하지 않으므로, 최종 head에서 전체 workflow 재실행이 필요하다. #899 run에서 assertion/test 실패 로그는 확인되지 않았다.
- Exposed 진단 PR #896 head `80e77f3fef66671423fa3345ab648ac49bb17620` 본문은 `Closes #885`를 포함하면서 동시에 이슈를 닫지 않는다고 적었다. 이 PR은 merge하지 않는다. 이슈를 닫을 주 해결 PR은 #899 하나로 유지한다.
- 기존 POM map/receipt는 현재 exact checkout과 불일치한다. map의 9개 worktree 경로가 사라졌고 receipt의 central/consumer SHA가 live PR head와 다르다. 기록된 `192` POM / `50,516` dependency / `192` Maven model PASS는 이전 후보의 역사 기록이며 현재 exact candidate 증거로 사용하지 않는다.
- 현재 중앙 후보는 remote head `036b7aeb…` 위에서 네 구현/테스트 파일과 이 체크리스트·lesson을 수정 중이다. verifier는 Jackson 2/3 BOM import가 central version catalog의 정확한 버전으로 각각 한 번 존재하는지 검사한다. 변경 후 local central publication POM 1개/88 dependency 구조 감사와 Maven effective model은 통과했으나, 9개 publisher 전체의 exact-map 재실행은 아직 필요하다.
- Merge, SNAPSHOT dispatch/publication은 보류 상태다. 특히 `develop` merge가 `Publish Snapshot`을 자동 실행할 수 있으므로 merge 직전 hold와 별도 exact-head 승인을 적용한다.

## 현재 소유권과 후보 변경

2026-10-07 live Dependabot 분류: 열린 alert 144건. 중앙 catalog 132건, repo-tooling 9건, central Spring Boot BOM 전이 3건이다. 중앙 catalog 중 현재 값이 patched 이상인 family는 유지하고, 현재 중앙 catalog보다 패치가 필요한 보안 업데이트만 반영한다. Kotlin은 안정판 `2.4.20`이 이미 중앙 catalog에 있고, `2.4.20-Beta1`은 후보로 사용하지 않는다. Spring Boot 경로의 Tomcat은 중앙 `11.0.25`가 현재 alert의 patched version 이상이다.

| Catalog authority | 기준값 | 후보값 | 근거 |
| --- | --- | --- | --- |
| `jackson2`, managed Jackson core/module-kotlin | `2.22.2` | `2.22.3` | Jackson 2.22 공식 patch list 및 live patched alert |
| `jackson3` | `3.2.2` | `3.2.3` | 공식 Jackson 3.2 patch list에 2026-09-21 release로 기재 |
| `netty4` | `4.1.136.Final` | `4.1.139.Final` | Netty 공식 4.1.139.Final release (2026-10-06), security fixes 포함 |
| `netty` | `4.2.17.Final` | `4.2.19.Final` | Netty 공식 4.2.19.Final release (2026-10-06), security fixes 포함 |
| `freemarker` | Exposed root의 직접 버전 `2.3.35` | 중앙 alias `2.3.35` | #885 실패 좌표에 포함된 의존성의 버전 기준을 중앙 catalog로 옮긴다. 현재 값은 유지하며 Dependabot 보안 업데이트 복구 증거로 보지 않는다. |
| `jsoup` | 중앙 version authority 없음; Graph `1.23.1`, Exposed Dokka resolution floor `1.23.1` | 중앙 alias `1.23.2` | Exposed Dependabot alert #180의 patched version이며 [공식 1.23.2 release](https://jsoup.org/news/release-1.23.2)로 확인했다. Exposed와 Graph의 repo-local authority를 중앙 `bt4kVersion("jsoup")`로 합친다. |
| legacy `jackson` key | `2.22.1` | 유지 | 중앙 authority audit이 추적하는 `jackson2`로 Exposed/Text 소비 코드 이동; legacy key는 별도 alias policy 없이 변경하지 않음 |

공식 근거: [Jackson 2.22 patch list](https://github.com/FasterXML/jackson/wiki/Jackson-Release-2.22), [Jackson 3.2 patch list](https://github.com/FasterXML/jackson/wiki/Jackson-Release-3.2), [Netty 4.1.139 release](https://github.com/netty/netty/releases/tag/netty-4.1.139.Final), [Netty 4.2.19 release](https://github.com/netty/netty/releases/tag/netty-4.2.19.Final), [FreeMarker 2.3.35 release notes](https://freemarker.apache.org/docs/versions_2_3_35.html), [GHSA-27j2-h3m2-8237](https://github.com/advisories/GHSA-27j2-h3m2-8237).

중앙 catalog consumer 9곳: `projects`, `aws`, `experimental`, `exposed`, `graph`, `image`, `javers`, `leader`, `text`. Publisher 8곳은 `experimental`을 제외하며, publisher inventory에는 central dependencies 자체를 포함해 POM 검증 대상 9곳이다. 초기 catalog pins는 projects/leader `0765227c…`, aws/exposed/javers `9698c9d…`, experimental/image/text `850959d…`, graph `55b5269b…`로 관측했다. 후보 SHA 생성 후 실제 consumer worktree와 원격 기준을 재확인한다.

## 체크리스트 계약

- [x] **CL-01 — 변경 전에 체크리스트를 생성한다.**
  - **Action:** source/test 구현 전에 후보 identity와 required/N/A/PENDING 항목을 기록한다.
  - **Evidence:** 이 체크리스트가 catalog 및 테스트 파일 수정 전에 생성되었다.
  - **Failure:** 순서 위반이 발견되면 영향을 받은 선행 gate를 복구하고 후속 검증을 다시 한다.
- [x] **CL-02 — 모든 항목의 적용 여부를 분류한다.**
  - **Action:** 공통, Type P, topology, POM 항목을 required/conditional/N/A로 분류한다.
  - **Evidence:** 아래 각 gate에 상태와 N/A 사유를 기록했다.
  - **Failure:** 분류하지 않은 항목은 required 미확인으로 유지한다.
- [x] **CL-03 — 의존 순서대로 실행한다.**
  - **Action:** 중앙 CI 수리 → catalog/checksum/delta → consumer SHA sync → POM/build 검증 → 후보 commit 순으로 진행한다.
  - **Evidence:** 실행 순서와 각 gate 증거를 바로 아래 기록한다.
  - **Failure:** 순서가 바뀌면 영향받은 뒤쪽 증거를 폐기하고 다시 검증한다.
- [x] **CL-04 — 증거를 확인 즉시 기록한다.**
  - **Action:** 각 검증 결과와 exact SHA를 발생 시점에 이 체크리스트에 기록한다.
  - **Evidence:** 실행 명령, 결과, 시각, 경로 또는 live URL.
  - **Failure:** 사후 추정은 증거로 인정하지 않고 해당 gate를 미확인으로 둔다.
- [x] **CL-05 — 실패 또는 대기를 닫힌 상태로 유지한다.**
  - **Action:** 실패와 외부 승인 대기 상태를 보존하고 downstream side effect를 막는다.
  - **Evidence:** 중앙 CI 테스트 baseline 실패 1건과 오류 1건을 기록한 뒤 assertion을 바로잡고 재검증했다. PR/publish 경계는 계속 PENDING이다.
  - **Failure:** 실패 또는 PENDING prerequisite를 우회하면 해당 downstream 검증을 무효 처리한다.
- **N/A — CL-06 — 누락/재정렬 작업 복구:** 작업 순서를 건너뛴 증거가 없고 구현 전에 CL-01을 통과했다. 누락이 발견되면 이 항목을 required로 전환한다.
- [ ] **CL-07 — 외부 side effect 직전 hold를 갱신한다.**
  - **Action:** push, PR, merge, tag 또는 publication 전에 authority와 exact target을 다시 읽는다.
  - **Evidence:** 해당 action의 최신 사용자 권한, exact SHA, CI 및 live GitHub 상태.
  - **Failure:** stale/불명확한 authority면 side effect를 실행하지 않는다.
- [ ] **CL-08 — 완료 전에 수치를 대조한다.**
  - **Action:** 최종 보고에서 `Required checks: X/Y; N/A: N; Blocked: N`을 계산한다.
  - **Evidence:** 체크리스트 상태와 일치하는 DoD 집계 및 unchecked ID 목록.
  - **Failure:** 수치가 맞지 않으면 DONE으로 보고하지 않는다.

## 공통 gate

- [x] **CG-01 — 권한과 현재 상태를 재확인한다.**
  - **Action:** 상위/저장소 지침, workflow, release skill, Kotlin/catalog 패턴, worktree 상태를 확인한다.
  - **Evidence:** 작업 격리 worktree는 base `ef4612ac…`에서 분리됐다. 중앙 후보 branch `fix/dependabot-security-catalog-2026-10`는 remote head `036b7aeb…`이며 구현/테스트 4개와 문서 2개만 수정 중이다. canonical checkout과 다른 기존 worktree는 보존한다.
  - **Failure:** 권한 또는 대상이 달라지면 변경 전에 중단한다.
- [x] **CG-02 — 과거 및 현재 증거를 조회한다.**
  - **Action:** GNO의 github/docs/wiki를 검색하고 live GitHub issue, PR, release, CI, alert를 읽는다.
  - **Evidence:** GNO `bluetape4k-docs`에서 publication-POM gate와 기존 lesson을 확인했고, 관련 GitHub/wiki 쿼리는 이 train의 현재 결정을 추가로 바꾸지 않았다. live Exposed 열린 이슈는 #885 하나이며, PR/CI exact head 현황은 위 2026-10-08 표에 기록했다.
  - **Failure:** mutable 결정은 live 증거가 없으면 진행하지 않는다.
- [x] **CG-03 — 사용자 작업과 경계를 보호한다.**
  - **Action:** clean 격리 worktree에서만 수정하고 기존 user-owned checkout/worktree를 보존한다.
  - **Evidence:** central candidate branch가 새로 분리되었고 기존 feature, dirty checkout, worktree를 reset/delete하지 않았다.
  - **Failure:** dirty/ambiguous 상태를 발견하면 그 상태를 보존하고 별도 경로를 쓴다.
- [x] **CG-04 — 정책과 독자 경계를 적용한다.**
  - **Action:** reader-facing checklist와 wiki research note는 한국어로, 코드 식별자/명령/URL은 원형으로 유지한다.
  - **Evidence:** 두 변경 문서는 한국어 독자 문서 계약을 따른다. 체크리스트와 lesson 각각 SPW-01..05 및 KO-01..05/KO-07을 통과했다. KO-06은 한국어 단일 언어 내부 문서이며 짝 locale 경로가 없어 N/A다. `node /Users/debop/.codex/skills/bluetape-writer/scripts/audit-korean-terms.mjs --json docs/releases/2026-10-07-dependabot-central-catalog-train-checklist.md docs/lessons/2026-10-08-central-bom-import-cardinality.md`의 최신 결과는 2개 파일 모두 `findings=[]`다. 식별자·명령·URL·수치와 불확실성 표현은 원본 근거와 대조했다.
  - **Failure:** 공개/독자 문서의 언어 계약을 위반하면 수정 전 진행하지 않는다.
- [x] **CG-05 — ecosystem pattern을 재사용한다.**
  - **Action:** central TOML, checksum, version-delta, immutable consumer SHA 및 기존 sync/POM helpers를 사용한다.
  - **Evidence:** 기존 `sync-shared-versions.py`, `sync-dependabot-ignores.py`, `verify-publication-poms.py`가 지정되었다.
  - **Failure:** local override나 새 dependency로 central ownership을 우회하지 않는다.
- [x] **CG-06 — 공개 및 문서 계약을 증명한다.**
  - **Action:** public artifact/API 영향, POM, public manual scope를 후보 diff로 확인한다.
  - **Evidence:** 중앙 BOM에 Jackson 2/3 BOM import를 추가하며 Kotlin API와 public manual은 바뀌지 않는다. 변경 후보의 generated central POM 1개/88 dependency 구조 감사는 오류 0건이고 Maven effective model이 통과했다. 전체 publisher 수와 consumer POM gate는 POM-02/03에서 별도로 확인한다.
  - **Failure:** 안정 BOM 또는 public contract 변경이 발견되면 flow를 재분류한다.
- [x] **CG-07 — 기존 동작을 고정하고 targeted proof를 실행한다.**
  - **Action:** catalog governance CI assertions를 current action pin과 일치시키고 회귀 테스트를 실행한다.
  - **Evidence:** POM verifier 회귀 사례를 추가했다. `python3 -m unittest tests/test_verify_publication_poms.py tests/test_ci_catalog_governance.py`는 54 tests PASS다. 전체 `python3.13 -m unittest discover -s tests`는 476개를 실행해 474개가 통과했으며, 실패 2건은 stale canonical sibling workspace의 version-count/Graph override 상태 비교에서 발생했다. 전체 suite는 PASS로 계산하지 않는다.
  - **Failure:** targeted suite가 통과하지 않으면 다음 gate로 가지 않는다.
- [x] **CG-08 — 무거운 검증을 순차 실행한다.**
  - **Action:** central `./gradlew build`와 Exposed Testcontainers 검증을 다른 container suite와 동시에 실행하지 않는다.
  - **Evidence:** 2026-10-08에 현재 중앙 후보 worktree (`036b7aeb…` + scoped uncommitted verifier/docs diff)에서 `./gradlew build --no-daemon --no-parallel` **BUILD SUCCESSFUL**. 이후 Exposed PR #899 exact head `bf01557457460b26da49a7299965469682ef83c8`에서 순차 실행: `:bluetape4k-exposed-jackson2:test --no-daemon --no-parallel --console=plain` **BUILD SUCCESSFUL**, 159 passed / 17 skipped; 다음 `:bluetape4k-exposed-jackson3:test --no-daemon --no-parallel --console=plain` **BUILD SUCCESSFUL**, 160 passed / 17 skipped. 이 모듈 결과는 local consumer tree의 test evidence이며, 후보 central SHA로 sync된 9-repository exact-map proof는 PUB-08/POM-02/03에서 별도로 수행한다.
  - **Failure:** 미완료/failed test를 성공으로 계산하지 않는다.
- [x] **CG-09 — 재발 방지 lesson을 평가한다.**
  - **Action:** 기존 catalog/security workflow 기록과 반복 원인을 대조하고 필요한 연구 note를 보존한다.
  - **Evidence:** 기존 `docs/lessons/2026-07-17-cross-repo-publication-pom-gate.md`와 새 `docs/lessons/2026-10-08-central-bom-import-cardinality.md`를 대조했다. 새 lesson은 정정 버전과 stale 중복 import가 함께 있을 때 verifier가 0 오류를 반환한 RED 관찰과 정확히 1개/정확한 catalog 버전을 요구하는 재발 방지 규칙을 기록한다. checklist와 lesson 모두 SPW-01..05, KO-01..05/KO-07을 통과했고 변경 후 한국어 용어 audit은 2개 파일에서 `findings=[]`다. 이 lesson은 이 후보 commit에 포함한다. canonical GNO 갱신은 merge/local sync/cleanup 뒤 CG-18에서 수행한다.
  - **Failure:** 재발 lesson이 누락되면 final pre-PR proof 전에 추가한다.
- [ ] **CG-10 — 최종 pre-PR proof를 수렴한다.**
  - **Action:** 모든 applicable leaf gate, final diff review, fresh checks를 통과시키고 exact local head를 기록한다.
  - **Evidence:** central 변경의 독립 코드 리뷰는 P0/P1/P2/LOW finding 0이며 targeted suite 54개가 통과했다. 이전 exact map은 stale이고 #899 exact-head CI는 실패했으므로 최종 cross-repo review, POM gate, CI 및 새 local head 기록이 남았다.
  - **Failure:** evidence 부족/높은 심각도 finding이 있으면 PR gate를 닫는다.

### PR과 merge 경계

- [ ] **CG-11 — PR 생성 authority를 확인한다.**
  - **Action:** 요청이 repository, base, head를 특정했는지 확인한다.
  - **Evidence:** 해당 target에 대한 명시적 승인과 CG-01..10 PASS.
  - **Failure:** authority가 없으면 push/PR을 하지 않는다.
- [ ] **CG-12 — exact head를 push한다.**
  - **Action:** 승인된 branch만 push하고 원격 SHA를 read-back한다.
  - **Evidence:** local/remote SHA 일치.
  - **Failure:** mismatch 또는 미승인이면 중단한다.
- [ ] **CG-12A — PR 직전 guidance를 갱신한다.**
  - **Action:** PR 직전 현재 AGENTS, leaf/common rules, PR template, issue metadata를 재확인한다.
  - **Evidence:** 재확인한 지침과 변경 여부 판단.
  - **Failure:** 변경된 guidance를 재검증하기 전 PR을 만들지 않는다.
- [ ] **CG-13 — PR을 생성하고 검증한다.**
  - **Action:** authority가 있으면 한국어 본문, exact head, `## DoD Status`, 담당자/라벨/마일스톤을 반영한다.
  - **Evidence:** live PR URL, metadata, body read-back.
  - **Failure:** live metadata가 다르면 수리하고 CI 대기를 시작하지 않는다.
- [ ] **CG-14 — exact-head CI와 live review를 통과한다.**
  - **Action:** PR head의 required checks, 리뷰와 thread를 다시 읽는다.
  - **Evidence:** required CI 및 unresolved thread 없음; sole-maintainer review 예외는 근거와 함께 N/A 처리한다.
  - **Failure:** failed/skipped/unresolved evidence가 있으면 merge-ready가 아니다.
- [ ] **CG-15 — merge-ready 상태를 보고한다.**
  - **Action:** merge gate 직전 live state와 모든 DoD를 재검증한다.
  - **Evidence:** exact head, CI/review/mergeability 및 hold 상태.
  - **Failure:** stale 상태나 누락 gate가 있으면 보고를 보류한다.
- [ ] **CG-16 — 새 merge 승인을 얻는다.**
  - **Action:** CG-15 결과 후 정확한 PR head의 병합 승인을 확인한다.
  - **Evidence:** 후보 head와 자동 SNAPSHOT publication 부작용을 포함한 fresh approval.
  - **Failure:** 명시적 승인 전에는 merge하지 않는다.
- [ ] **CG-17 — merge를 실행하고 확인한다.**
  - **Action:** 승인된 전략으로 merge 후 live merged state를 확인한다.
  - **Evidence:** PR mergedAt, merge SHA, base read-back.
  - **Failure:** 자동 merge 설정 또는 다른 SHA 사용을 금지한다.
- [ ] **CG-17A — canonical checkout을 동기화한다.**
  - **Action:** merge 후 canonical checkout을 remote base와 동기화하고 dirty state를 보존한다.
  - **Evidence:** local/upstream SHA와 status.
  - **Failure:** unmerged 상태 또는 dirty 보호가 불명확하면 PENDING이다.
- [ ] **CG-17B — 승인된 task work만 정리한다.**
  - **Action:** merge와 canonical sync 후 task-owned worktree/branch만 정리한다.
  - **Evidence:** merged/represented SHA, cleanup list, preserved states.
  - **Failure:** 아직 미통합 후보는 삭제하지 않는다.
- [ ] **CG-18 — canonical GNO lesson을 확인한다.**
  - **Action:** CG-17A/B 후 해당 collection을 갱신·embed·search한다.
  - **Evidence:** canonical checkout SHA와 검색 결과.
  - **Failure:** 미통합 note 또는 cleanup 전 indexing은 PASS가 아니다.
- [ ] **CG-X01 — 다른 irreversible action을 승인한다.**
  - **Action:** tag, dispatch, release, publication 전에 별도 authority와 최신 hold를 확인한다.
  - **Evidence:** exact target/action approval과 그 직전 체크리스트.
  - **Failure:** 승인 전 tag/dispatch/publication을 하지 않는다.

## Type P / topology / publication-POM

- [x] **PUB-01 — release identity와 authority를 고정한다.**
  - **Action:** flow, versions, class, branches/SHAs, artifact matrix, consumers, side-effect authority를 확정한다.
  - **Evidence:** 이 체크리스트와 아래 candidate map에 `catalog-train-snapshot` / `dependencies-only`, `2.1.0-SNAPSHOT`, candidate SHAs, 9 consumers 및 현재 허용된 local-only 범위가 고정되어 있다. 원격 side effect는 아직 실행하지 않았다.
  - **Failure:** 불명확한 identity면 validation/publish를 멈춘다.
- [x] **PUB-02 — live planning/topology gap을 닫는다.**
  - **Action:** issue, PR, release, CI, catalog consumers와 GNO evidence를 분류한다.
  - **Evidence:** 현재 Exposed 열린 issue #885의 acceptance와 label/milestone을 live read-back했다. train 지원 PR 10개의 exact heads/CI 상태는 위 2026-10-08 표에 있고, existing central PR #257의 local changes는 remote에 아직 반영되지 않았다. 최신 published BOM은 `2.0.0`; catalog consumer 9곳과 publisher 9곳의 inventory는 유지된다.
  - **Failure:** release-affecting issue 또는 topology mismatch가 있으면 candidate를 막는다.
- [ ] **PUB-03 — exact candidate state를 증명한다.**
  - **Action:** catalog, checksum, version-delta, cross-repo POM, downstream builds를 exact SHA에서 검증한다.
  - **Evidence:** 이전 candidate map은 사라진 worktree roots와 stale SHA를 포함해 사용할 수 없다. 현재 remote PR heads 기반의 새 map과 전체 POM/Maven model 검증, consumer 범위 read-back이 남았다.
  - **Failure:** source, generated Maven model, graph가 다르면 promote하지 않는다.
- **N/A — PUB-04 — stable preflight:** 안정 release/dispatch가 범위에 없고 stable artifact/version을 변경하지 않는다.
- [ ] **PUB-05 — irreversible hold를 갱신한다.**
  - **Action:** merge 직전 자동 `Publish Snapshot` workflow와 모든 artifact hold를 새로 읽는다.
  - **Evidence:** 최신 workflow schema, run/metadata, 승인 및 target SHA.
  - **Failure:** SNAPSHOT publication이 승인되지 않았거나 hold가 낡으면 merge하지 않는다.
- [ ] **PUB-06 — publication을 dispatch하고 검증한다.**
  - **Action:** 승인된 exact SNAPSHOT workflow를 실행/모니터링하고 metadata를 조회한다.
  - **Evidence:** workflow URL/conclusion 및 artifact matrix.
  - **Failure:** 별도 승인 전에는 실행하지 않는다.
- **N/A — PUB-07 — GitHub release closeout:** 이 train은 stable release/tag를 만들지 않는다.
- [ ] **PUB-08 — downstream consumers를 동기화한다.**
  - **Action:** 9개 consumer pin을 후보 immutable SHA로 동기화하고 영향 모듈을 검증한다.
  - **Evidence:** 현재 원격 PR head의 실패/대기 상태는 위 표와 같다. 기존 local consumer test/POM evidence는 현재 exact branch map과 일치하는지 아직 입증되지 않았고 Exposed #899 CI가 실패했으므로 새 exact map과 CI read-back이 필요하다.
  - **Failure:** stale branch, missing consumer, `help`만의 검증이면 candidate-ready가 아니다.
- **N/A — PUB-09 — 다음 development line 열기:** 이미 `2.1.0-SNAPSHOT`이 설정되어 있고 stable release 후속 line을 바꾸지 않는다.
- **N/A — PUB-10 — public manual handoff:** 외부 dependency catalog만 바뀌며 public API/manual/release baseline은 바뀌지 않는다.
- [ ] **PUB-11 — release truth를 보고한다.**
  - **Action:** Required/N/A/Blocked, exact SHAs, run URL, artifacts, 제외 범위를 보고한다.
  - **Evidence:** 최종 DoD 집계와 이 문서.
  - **Failure:** 검증되지 않은 publication/merge 주장을 하지 않는다.

- [x] **TOP-01 — 모든 repo를 분류한다.**
  - **Action:** central dependencies, 8 stable publishers, experimental, consumers를 구분한다.
  - **Evidence:** consumer는 `projects`, `aws`, `experimental`, `exposed`, `graph`, `image`, `javers`, `leader`, `text` 9곳이다. Publisher 검증은 central dependencies 및 8 downstream publisher(`experimental` 제외) 총 9곳이다.
  - **Failure:** 미분류 repo를 누락하거나 stable train에 넣지 않는다.
- [x] **TOP-02 — 모든 edge를 분류한다.**
  - **Action:** catalog management와 publication validation edge를 구분한다.
  - **Evidence:** `dependencies -> 8 downstream publisher POM/build validation`; `experimental -> central catalog-only consumer`. 내부 Bluetape artifact 승격 edge는 없다.
  - **Failure:** catalog/test edge를 stable release order로 오해하지 않는다.
- [x] **TOP-03 — 실행 DAG가 비순환임을 증명한다.**
  - **Action:** central candidate부터 consumer 검증까지 dependency order를 고정한다.
  - **Evidence:** 구조상 실행 순서는 central catalog -> immutable consumer pins -> consumer/POM verification이며, inventory에는 internal unpublished artifact 승격 edge가 없다. 이 항목은 실행 순서와 cycle 부재만 증명하며 consumer/POM 검증 성공은 `CG-08`, `PUB-08`, `POM-02/03`에서 별도로 증명한다.
  - **Failure:** cycle 또는 unpublished internal artifact edge가 있으면 차단한다.
- [x] **TOP-04 — 단일 flow/class를 선택한다.**
  - **Action:** `catalog-train-snapshot` flow와 `dependencies-only` class를 선택한다.
  - **Evidence:** external dependency catalog updates only; internal Bluetape versions remain unchanged.
  - **Failure:** internal version changes 발견 시 재분류한다.
- **N/A — TOP-05 — incremental internal train:** internal BOM/artifact version을 승격하지 않는다.

- [x] **POM-01 — publisher inventory를 대조한다.**
  - **Action:** verifier registry와 live publish workflow 9곳을 대조한다.
  - **Evidence:** verifier registry 및 map 기준 9곳은 `bluetape4k-dependencies`, `bluetape4k-projects`, `bluetape4k-aws`, `bluetape4k-exposed`, `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`, `bluetape4k-text`이며 `experimental`은 catalog-only라 publisher에서 제외했다.
  - **Failure:** mismatch면 candidate를 막는다.
- [ ] **POM-02 — 모든 publication POM/model을 검증한다.**
  - **Action:** repository-map의 exact worktree/HEAD와 후보 catalog로 전수 생성·검증한다.
  - **Evidence:** 이전 repository-map SHA-256 `e8523d677cc0f899d25c092880fa748b23dc291265686ea07f89467971388f24`가 가리킨 9개 root를 찾을 수 없어 이전 `192`/`50,516` 결과는 historical evidence다. 새 map을 현재 exact PR heads 및 central candidate SHA로 구성해 전체 gate를 재실행한다.
  - **Failure:** generation/model/POM failure가 하나라도 있으면 차단한다.
- [ ] **POM-03 — Maven version/profile 규칙을 검증한다.**
  - **Action:** dependencyManagement version과 effective model 및 profile 부재를 확인한다.
  - **Evidence:** 현재 central candidate POM에서는 Jackson BOM import 좌표별 정확히 1개와 catalog 버전 일치를 구조 검사한다. 전체 192개 예상 publisher POM의 Maven effective-model 결과는 새 map 재실행 뒤 기록한다.
  - **Failure:** unmanaged dependency 또는 profile이 있으면 차단한다.

## 2026-10-07 과거 실행 기록 (현재 exact-map gate 근거 아님)

- Baseline `python3 -m unittest tests.test_ci_catalog_governance`: **FAIL** — 20 tests, 1 failure, 1 error. `publish-snapshot.yml`의 `download-artifact` v8.0.1을 v7로 요구하고, `ci.yml`의 `setup-java` v6.0.1을 v6.0.0으로 찾는 assertion이 stale했다.
- Baseline `python3 -m unittest tests.test_central_catalog_version_deltas`: **PASS** — 6 tests.
- After repair `python3 -m unittest tests.test_ci_catalog_governance tests.test_central_catalog_version_deltas`: **PASS** — 26 tests.
- GitHub CI #35380594458, base `ef4612ac…`: failed; Cross-repository Publication POM Contract는 skipped.
- Candidate `python3.13 -m unittest tests.test_audit_latest_stable tests.test_catalog_checksum tests.test_sync_dependabot_ignores tests.test_ci_catalog_governance tests.test_central_catalog_version_deltas tests.test_latest_stable_version_deltas`: **PASS** — 88 tests.
- Candidate `python3.13 -m unittest tests.test_audit_latest_stable.LatestStableInventoryTest.test_inventory_reconstructs_the_exact_authority_universe tests.test_audit_latest_stable.LatestStableInventoryTest.test_inventory_includes_jsoup_as_catalog_direct_authority -v`: **PASS** — jsoup authority 추가 전 RED, source/test 반영 후 2 tests PASS.
- Candidate `scripts/audit-latest-stable.py --check --check-audit --summary --audit-summary`: **PASS** — 523 authorities (325 managed, 67 policy, 131 catalog); 518 metadata verified, 5 preview-only, 0 unavailable.
- 최종 inventory 생성 결과: 523 authorities (325 managed, 67 policy, 131 catalog); 518 metadata verified, 5 preview-only, 0 unavailable. jsoup은 `org.jsoup:jsoup`, version `1.23.2`, 중앙 direct authority이며 audit source는 Maven Central metadata다.
- 독립 코드 리뷰 첫 결과: P0 0, P1 1, P2 3. P1은 9개 consumer CI checkout pin이 settings immutable SHA `096560faa3384f3b53aa5d0baab9e36fd17eb6fd` 대신 이전 `89e738a3346e410200fe10a175a22aad0f6ecb48`을 사용했고 AWS contract target도 이전 SHA를 기대한 불일치였다. 9개 `ci.yml` (Graph testcontainers contract 포함)과 AWS contract target을 settings와 같은 `096560...`으로 맞췄다. AWS `catalog_pin_contract_test.py` **PASS**, 9/9 settings/CI pin audit **PASS**.
- 독립 리뷰의 P2 세 건을 수리했다. AWS와 Image는 dependency child fingerprint를 순서 무관하게 정규화하고 reordered-field 회귀 테스트를 추가했다. Graph는 반복 child 요소를 element name이 아닌 전체 canonical fingerprint로 정렬하고 반복 `<exclusion>` 순서 회귀 테스트를 추가했다. 각 신규 테스트는 수리 전 실패, 이후 BuildSrc 테스트 통과를 확인했다.
- 독립 최종 리뷰: 9개 consumer exact HEAD에서 P0/P1/P2/LOW = 0. 기존 Graph DOM 경로 coverage gap은 `6b88a8d7`의 실제 `GenerateMavenPom` fixture로 닫았고 집중 BuildSrc 테스트가 **BUILD SUCCESSFUL**. LSP diagnostics는 리뷰 lane에 없어 Gradle compile/test 증거로 대체했으며, 원격 GitHub CI는 아직 실행하지 않았다.
- Catalog baseline: `ef4612ac237550b550dc48eae5ecdfc94b27dab4`; 여섯 기존 version deltas; catalog checksum `7e45e45881fab8a741049735d9e5e9f04fb5d36223f2715d959a98c1966d4fed`; jsoup catalog source commit `0db405f89ec5a98e887c28952212adeb9a2ec026`.
- Candidate `./gradlew build --no-daemon`: **BUILD SUCCESSFUL** (8초; 3 actionable tasks up-to-date; existing NMCP publish API deprecation warning 1건).
- 중앙 jsoup catalog 변경 커밋: `0db405f89ec5a98e887c28952212adeb9a2ec026`; 이후 이 체크리스트 기록 commit을 거쳐 최종 immutable ref를 소비자 설정에 고정한다. Catalog SHA-256은 `7e45e45881fab8a741049735d9e5e9f04fb5d36223f2715d959a98c1966d4fed`로 유지된다.
- 9개 consumer의 중앙 catalog 경로 override `./gradlew help --no-daemon --no-configuration-cache --console=plain` **BUILD SUCCESSFUL**: `projects`, `aws`, `experimental`, `exposed`, `graph`, `image`, `javers`, `leader`, `text`.
- Exposed `:bluetape4k-exposed-jackson2:test` 및 `:bluetape4k-exposed-jackson3:test`, `--rerun-tasks --no-parallel`: 각각 159/159 및 160/160 test methods 통과, 각각 skipped 17건.
- Exposed `:bluetape4k-exposed-core:dependencyInsight` 및 Graph `:bluetape4k-graph-core:dependencyInsight`, configuration `dokkaHtmlGeneratorRuntimeResolver~internal`: 둘 다 `org.jsoup:jsoup:1.16.1 -> 1.23.2`이며 각 저장소의 검토된 resolution rule이 선택 사유로 표시된다.
- 초기 POM 전수 검증은 Projects 3건과 Exposed 5건의 duplicate effective-model 오류로 실패했다. 수정 후 재실행 과정에서 Exposed/Leader의 XML child order 차이와 Image `images-vips-java25`의 직접 의존성 `org.jetbrains.kotlinx:atomicfu-jvm:0.33.0` 중복도 발견해 각 consumer BuildSrc normalizer 및 회귀 테스트로 수리했다. 이 초기 실패는 이력으로 보존하고 아래 최종 전수 결과로 대체한다.
- 최종 exact-candidate POM/Maven 검증은 깨끗한 candidate checkout에서 실행했다. repository-map SHA-256 `e8523d677cc0f899d25c092880fa748b23dc291265686ea07f89467971388f24`; 결과 **PASS**, `failures=0 repositories=9 files=192 dependencies=50516 maven_models=192`. 전체 실행 로그는 후보 central worktree의 ignored `build/dependabot-central-catalog-train/pom-verification-final.log`에 있다.
- Catalog SHA-256: `7e45e45881fab8a741049735d9e5e9f04fb5d36223f2715d959a98c1966d4fed`.

| Repository | Base SHA | Candidate branch | Historical HEAD (superseded) |
| --- | --- | --- | --- |
| `bluetape4k-dependencies` | `ef4612ac237550b550dc48eae5ecdfc94b27dab4` | `fix/dependabot-security-catalog-2026-10` | `57ed052929dbf46f8f4221d9c603c6254c3d81ec` |
| `bluetape4k-projects` | `21a8fc4a324e5a293c1c789caa05bf713258bc20` | `chore/dependabot-central-catalog-2026-10` | `115b1ec9622d3d78799e2d78b30ad3b6b715ea39` |
| `bluetape4k-aws` | `849892b4b469714b5cbedc26811c5dab407c53e8` | `chore/dependabot-central-catalog-2026-10` | `09873d1cce861a27c2aac3e368e99e740a9e9397` |
| `bluetape4k-experimental` | `5ec15e5cb97ee99947031e1e030c4d57ab516d8b` | `chore/dependabot-central-catalog-2026-10` | `040ef88f0c5d263bbfc8b3bcedf96c8d79534e06` |
| `bluetape4k-exposed` | `38f4d92c8a78034b2b2f81f343539f3afa615ef3` | `chore/dependabot-central-catalog-2026-10` | `c6ef5fc645201a29f511c9697d00208723077001` |
| `bluetape4k-graph` | `2b171e1ee9cf2364367188b39babf5864439859e` | `chore/dependabot-central-catalog-2026-10` | `6b88a8d71d5b42105db62e8560ca08d370f445fa` |
| `bluetape4k-image` | `673daf3598ebb6c5afd0e1bf08a4d6ebe5ade0f6` | `chore/dependabot-central-catalog-2026-10` | `a7ff7f1e50a6a3ad85e9ec5b3cc0e509477a9b19` |
| `bluetape4k-javers` | `e153dd7e9b02f460728a1b527fab295bf9b2f072` | `chore/dependabot-central-catalog-2026-10` | `996aa041f30c6ca2e69faa1159b718c6ef4e4e92` |
| `bluetape4k-leader` | `d360a571948af6d2fe189cb1ad4b84ea80928ed8` | `chore/dependabot-central-catalog-2026-10` | `218380a0ff9a5d94f7c2284102fbe2087151ae66` |
| `bluetape4k-text` | `1e338c2f75ea08f18bca204a6e017c8033a47582` | `chore/dependabot-central-catalog-2026-10` | `02a7719368ec9559c17b68b8e060a97ff608678b` |

- Candidate PR/push/merge/publication: 실행하지 않음.
