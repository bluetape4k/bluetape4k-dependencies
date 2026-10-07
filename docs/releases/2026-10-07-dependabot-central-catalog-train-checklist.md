# 2026-10-07 중앙 Dependabot catalog train 체크리스트

상태: **PENDING / 중앙 후보와 소비처 로컬 검증 진행 중**

## 고정 범위와 중단 조건

- 대상 저장소: `bluetape4k/bluetape4k-dependencies`
- 기준: `develop` / `ef4612ac237550b550dc48eae5ecdfc94b27dab4`
- 후보 브랜치: `fix/dependabot-security-catalog-2026-10`
- 후보 head: 변경 커밋의 exact SHA를 workflow receipt와 final DoD에 기록
- 최신 published BOM: `2.0.0` (2026-09-02)
- 개발 BOM: `2.1.0-SNAPSHOT` (`baseVersion=2.1.0`, 빈 `snapshotVersion`)
- Flow/class: `catalog-train-snapshot` / `dependencies-only`
- 후보 catalog ref: 후보 커밋의 immutable SHA; tag 생성은 승인 범위 밖
- 현재 승인: 중앙 catalog 후보 수정, 로컬 검증, 9개 consumer의 immutable SHA 로컬 동기화
- 별도 승인 필요: push, PR 생성, merge, tag, workflow dispatch, snapshot/stable publication, 브랜치/worktree 삭제
- Merge hold: `develop` CI 성공 시 `Publish Snapshot` workflow가 자동 실행될 수 있으므로 정확한 head와 snapshot 결과를 확인한 뒤 별도 승인한다.
- 제외: 기존 PR #254(Kover)·#255(GitHub Actions), 이슈 #256(Kotlin/Detekt 호환성), repo-local tooling 경고

## 현재 소유권과 후보 변경

2026-10-07 live Dependabot 분류: 열린 alert 144건. 중앙 catalog 132건, repo-tooling 9건, central Spring Boot BOM 전이 3건이다. 중앙 catalog 중 현재 값이 patched 이상인 family는 유지하고, 현재 중앙 catalog보다 패치가 필요한 보안 업데이트만 반영한다. Kotlin은 안정판 `2.4.20`이 이미 중앙 catalog에 있고, `2.4.20-Beta1`은 후보로 사용하지 않는다. Spring Boot 경로의 Tomcat은 중앙 `11.0.25`가 현재 alert의 patched version 이상이다.

| Catalog authority | 기준값 | 후보값 | 근거 |
| --- | --- | --- | --- |
| `jackson2`, managed Jackson core/module-kotlin | `2.22.2` | `2.22.3` | Jackson 2.22 공식 patch list 및 live patched alert |
| `jackson3` | `3.2.2` | `3.2.3` | 공식 Jackson 3.2 patch list에 2026-09-21 release로 기재 |
| `netty4` | `4.1.136.Final` | `4.1.139.Final` | Netty 공식 4.1.139.Final release (2026-10-06), security fixes 포함 |
| `netty` | `4.2.17.Final` | `4.2.19.Final` | Netty 공식 4.2.19.Final release (2026-10-06), security fixes 포함 |
| `freemarker` | Exposed root의 직접 버전 `2.3.35` | 중앙 alias `2.3.35` | #885 실패 좌표에 포함된 의존성의 버전 기준을 중앙 catalog로 옮긴다. 현재 값은 유지하며 snapshot updater 수리 증거로 보지 않는다. |
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
  - **Evidence:** 작업 격리 worktree는 clean base SHA `ef4612ac…`이며 canonical checkout과 다른 기존 worktree를 보존했다.
  - **Failure:** 권한 또는 대상이 달라지면 변경 전에 중단한다.
- [x] **CG-02 — 과거 및 현재 증거를 조회한다.**
  - **Action:** GNO의 github/docs/wiki를 검색하고 live GitHub issue, PR, release, CI, alert를 읽는다.
  - **Evidence:** #194/#101은 CLOSED, #256은 OPEN이지만 범위 밖; PR #254/#255는 독립 작업; 최신 CI run #35380594458은 기준 SHA에서 실패; alert 분류는 144건이다.
  - **Failure:** mutable 결정은 live 증거가 없으면 진행하지 않는다.
- [x] **CG-03 — 사용자 작업과 경계를 보호한다.**
  - **Action:** clean 격리 worktree에서만 수정하고 기존 user-owned checkout/worktree를 보존한다.
  - **Evidence:** central candidate branch가 새로 분리되었고 기존 feature, dirty checkout, worktree를 reset/delete하지 않았다.
  - **Failure:** dirty/ambiguous 상태를 발견하면 그 상태를 보존하고 별도 경로를 쓴다.
- [x] **CG-04 — 정책과 독자 경계를 적용한다.**
  - **Action:** reader-facing checklist와 wiki research note는 한국어로, 코드 식별자/명령/URL은 원형으로 유지한다.
  - **Evidence:** 이 체크리스트는 한국어이며 branch prefix와 Lore commit protocol을 적용한다. 수정본 SPW-01..05 및 KO-01..05/KO-07을 통과했다. KO-06은 단일 언어 운영 체크리스트라 N/A다. 기본 용어 audit에서 발견한 8개 용례는 Gradle publication/catalog, Dependabot dependency graph, 또는 시점별 guidance/audit record를 가리켜 유지했다.
  - **Failure:** 공개/독자 문서의 언어 계약을 위반하면 수정 전 진행하지 않는다.
- [x] **CG-05 — ecosystem pattern을 재사용한다.**
  - **Action:** central TOML, checksum, version-delta, immutable consumer SHA 및 기존 sync/POM helpers를 사용한다.
  - **Evidence:** 기존 `sync-shared-versions.py`, `sync-dependabot-ignores.py`, `verify-publication-poms.py`가 지정되었다.
  - **Failure:** local override나 새 dependency로 central ownership을 우회하지 않는다.
- [ ] **CG-06 — 공개 및 문서 계약을 증명한다.**
  - **Action:** public artifact/API 영향, POM, public manual scope를 후보 diff로 확인한다.
  - **Evidence:** 최종 diff와 9-publisher POM 결과.
  - **Failure:** 안정 BOM 또는 public contract 변경이 발견되면 flow를 재분류한다.
- [x] **CG-07 — 기존 동작을 고정하고 targeted proof를 실행한다.**
  - **Action:** catalog governance CI assertions를 current action pin과 일치시키고 회귀 테스트를 실행한다.
  - **Evidence:** baseline 재현은 `tests.test_ci_catalog_governance` 20개 중 failure 1, error 1이었다. download-artifact 기대를 v8.0.1로 맞추고 setup-java 순서 검증을 action prefix로 고쳤다. 전체 governance/audit suite 73 tests PASS, checksum/audit 재검증 suite 49 tests PASS.
  - **Failure:** targeted suite가 통과하지 않으면 다음 gate로 가지 않는다.
- [ ] **CG-08 — 무거운 검증을 순차 실행한다.**
  - **Action:** central `./gradlew build`와 Exposed Testcontainers 검증을 다른 container suite와 동시에 실행하지 않는다.
  - **Evidence:** 중앙 `./gradlew build` **BUILD SUCCESSFUL**. Exposed Testcontainers 검증은 consumer sync 후 실행 대기.
  - **Failure:** 미완료/failed test를 성공으로 계산하지 않는다.
- [ ] **CG-09 — 재발 방지 lesson을 평가한다.**
  - **Action:** 기존 catalog/security workflow 기록과 반복 원인을 대조하고 필요한 연구 note를 보존한다.
  - **Evidence:** `bluetape4k-github`의 #194 및 기존 central checklist, 공식 release source, wiki note.
  - **Failure:** 재발 lesson이 누락되면 final pre-PR proof 전에 추가한다.
- [ ] **CG-10 — 최종 pre-PR proof를 수렴한다.**
  - **Action:** 모든 applicable leaf gate, final diff review, fresh checks를 통과시키고 exact local head를 기록한다.
  - **Evidence:** P0=0/P1=0, checklist, checks, branch head SHA.
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
  - **Evidence:** guidance snapshot과 drift 판단.
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
  - **Evidence:** 후보 head와 자동 snapshot 부작용을 포함한 fresh approval.
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

- [ ] **PUB-01 — release identity와 authority를 고정한다.**
  - **Action:** flow, versions, class, branches/SHAs, artifact matrix, consumers, side-effect authority를 확정한다.
  - **Evidence:** 이 체크리스트 및 candidate head SHA.
  - **Failure:** 불명확한 identity면 validation/publish를 멈춘다.
- [x] **PUB-02 — live planning/topology gap을 닫는다.**
  - **Action:** issue, PR, release, CI, catalog consumers와 GNO evidence를 분류한다.
  - **Evidence:** #194/#101 closed, #256 unrelated open, #254/#255 unrelated open, latest release `2.0.0`, 9 consumers/8 downstream publishers.
  - **Failure:** release-affecting issue 또는 topology mismatch가 있으면 candidate를 막는다.
- [ ] **PUB-03 — exact candidate state를 증명한다.**
  - **Action:** catalog, checksum, version-delta, cross-repo POM, downstream builds를 exact SHA에서 검증한다.
  - **Evidence:** central/consumer SHAs, POM counts, test/build results.
  - **Failure:** source, generated Maven model, graph가 다르면 promote하지 않는다.
- **N/A — PUB-04 — stable preflight:** 안정 release/dispatch가 범위에 없고 stable artifact/version을 변경하지 않는다.
- [ ] **PUB-05 — irreversible hold를 갱신한다.**
  - **Action:** merge 직전 자동 `Publish Snapshot` workflow와 모든 artifact hold를 새로 읽는다.
  - **Evidence:** 최신 workflow schema, run/metadata, 승인 및 target SHA.
  - **Failure:** snapshot side effect가 승인되지 않았거나 hold가 낡으면 merge하지 않는다.
- [ ] **PUB-06 — publication을 dispatch하고 검증한다.**
  - **Action:** 승인된 exact snapshot workflow를 실행/모니터링하고 metadata를 조회한다.
  - **Evidence:** workflow URL/conclusion 및 artifact matrix.
  - **Failure:** 별도 승인 전에는 실행하지 않는다.
- **N/A — PUB-07 — GitHub release closeout:** 이 train은 stable release/tag를 만들지 않는다.
- [ ] **PUB-08 — downstream consumers를 동기화한다.**
  - **Action:** 9개 consumer pin을 후보 immutable SHA로 동기화하고 영향 모듈을 검증한다.
  - **Evidence:** per-repo diff/ref, resolution/build 결과 및 8개 publisher POM.
  - **Failure:** stale branch, missing consumer, `help`만의 검증이면 candidate-ready가 아니다.
- **N/A — PUB-09 — 다음 development line 열기:** 이미 `2.1.0-SNAPSHOT`이 설정되어 있고 stable release 후속 line을 바꾸지 않는다.
- **N/A — PUB-10 — public manual handoff:** 외부 dependency catalog만 바뀌며 public API/manual/release baseline은 바뀌지 않는다.
- [ ] **PUB-11 — release truth를 보고한다.**
  - **Action:** Required/N/A/Blocked, exact SHAs, run URL, artifacts, 제외 범위를 보고한다.
  - **Evidence:** 최종 DoD 집계와 이 문서.
  - **Failure:** 검증되지 않은 publication/merge 주장을 하지 않는다.

- [ ] **TOP-01 — 모든 repo를 분류한다.**
  - **Action:** central dependencies, 8 stable publishers, experimental, consumers를 구분한다.
  - **Evidence:** consumer/publisher inventory 표와 제외 이유.
  - **Failure:** 미분류 repo를 누락하거나 stable train에 넣지 않는다.
- [ ] **TOP-02 — 모든 edge를 분류한다.**
  - **Action:** catalog management와 publication validation edge를 구분한다.
  - **Evidence:** `dependencies -> 8 publisher POM/build validation`, `experimental -> catalog-only consumer`.
  - **Failure:** catalog/test edge를 stable release order로 오해하지 않는다.
- [ ] **TOP-03 — 실행 DAG가 비순환임을 증명한다.**
  - **Action:** central candidate부터 consumer 검증까지 dependency order를 고정한다.
  - **Evidence:** central catalog -> immutable consumer pins -> consumer/POM verification.
  - **Failure:** cycle 또는 unpublished internal artifact edge가 있으면 차단한다.
- [x] **TOP-04 — 단일 flow/class를 선택한다.**
  - **Action:** catalog-train-snapshot flow와 dependencies-only class를 선택한다.
  - **Evidence:** external dependency catalog updates only; internal Bluetape versions remain unchanged.
  - **Failure:** internal version changes 발견 시 재분류한다.
- **N/A — TOP-05 — incremental internal train:** internal BOM/artifact version을 승격하지 않는다.

- [ ] **POM-01 — publisher inventory를 대조한다.**
  - **Action:** verifier registry와 live publish workflow 9곳을 대조한다.
  - **Evidence:** 9 publisher repo 목록 및 inventory 결과.
  - **Failure:** mismatch면 candidate를 막는다.
- [ ] **POM-02 — 모든 publication POM/model을 검증한다.**
  - **Action:** repository-map의 exact worktree/HEAD와 후보 catalog로 전수 생성·검증한다.
  - **Evidence:** repositories/files/dependencies/models/failures 요약.
  - **Failure:** generation/model/POM failure가 하나라도 있으면 차단한다.
- [ ] **POM-03 — Maven version/profile 규칙을 검증한다.**
  - **Action:** dependencyManagement version과 effective model 및 profile 부재를 확인한다.
  - **Evidence:** verifier의 zero-failure structural/effective-model output.
  - **Failure:** unmanaged dependency 또는 profile이 있으면 차단한다.

## 최신 결과 기록

- Baseline `python3 -m unittest tests.test_ci_catalog_governance`: **FAIL** — 20 tests, 1 failure, 1 error. `publish-snapshot.yml`의 `download-artifact` v8.0.1을 v7로 요구하고, `ci.yml`의 `setup-java` v6.0.1을 v6.0.0으로 찾는 assertion이 stale했다.
- Baseline `python3 -m unittest tests.test_central_catalog_version_deltas`: **PASS** — 6 tests.
- After repair `python3 -m unittest tests.test_ci_catalog_governance tests.test_central_catalog_version_deltas`: **PASS** — 26 tests.
- GitHub CI #35380594458, base `ef4612ac…`: failed; Cross-repository Publication POM Contract는 skipped.
- Candidate `python3.13 -m unittest tests.test_audit_latest_stable tests.test_catalog_checksum tests.test_sync_dependabot_ignores tests.test_ci_catalog_governance tests.test_central_catalog_version_deltas tests.test_latest_stable_version_deltas`: **PASS** — 88 tests.
- Candidate `python3.13 -m unittest tests.test_audit_latest_stable.LatestStableInventoryTest.test_inventory_reconstructs_the_exact_authority_universe tests.test_audit_latest_stable.LatestStableInventoryTest.test_inventory_includes_jsoup_as_catalog_direct_authority -v`: **PASS** — jsoup authority 추가 전 RED, source/test 반영 후 2 tests PASS.
- Candidate `scripts/audit-latest-stable.py --check --check-audit --summary --audit-summary`: **PASS** — 523 authorities (325 managed, 67 policy, 131 catalog); 518 metadata verified, 5 preview-only, 0 unavailable.
- 최종 inventory 생성 결과: 523 authorities (325 managed, 67 policy, 131 catalog); 518 metadata verified, 5 preview-only, 0 unavailable. jsoup은 `org.jsoup:jsoup`, version `1.23.2`, 중앙 direct authority이며 audit source는 Maven Central metadata다.
- Catalog baseline: `ef4612ac237550b550dc48eae5ecdfc94b27dab4`; 여섯 기존 version deltas; catalog checksum `7e45e45881fab8a741049735d9e5e9f04fb5d36223f2715d959a98c1966d4fed`; 중앙 후보 commit SHA는 검증 후 기록한다.
- Candidate `./gradlew build --no-daemon`: **BUILD SUCCESSFUL** (9초, buildSrc 작업은 up-to-date; 기존 NMCP publish API deprecation 경고 1건).
- Candidate `./gradlew build --no-daemon`: **BUILD SUCCESSFUL** (8초; 3 actionable tasks up-to-date; existing NMCP publish API deprecation warning 1건).
- Candidate PR/push/merge/publication: 실행하지 않음.
