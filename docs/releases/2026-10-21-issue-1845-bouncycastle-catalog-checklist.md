# 2026-10-21 Issue #1845 Bouncy Castle 카탈로그 train 체크리스트

상태: **PENDING / 중앙 후보 catalog SHA-256 `11255a5e195a2e66574559fff4568e4551f5b58ab89c68fabeffa2197e331f30`에서 Projects 두 resolved graph 모두 `bcprov-lts8on:2.73.10`으로 유지된다. 중앙 PR은 generated catalog freshness 오류를 겨냥하며 runtime dependency를 수정했다고 주장하지 않는다. PR 생성·정확한 head CI 확인까지만 승인됐다. 병합, immutable catalog ref 생성, 소비자 동기화와 publication은 별도 승인을 기다린다.**

## 목표와 고정 범위

- 분류: Type P `catalog-train-snapshot`, 저장소 class `dependencies-only`.
- 중앙 저장소: `bluetape4k/bluetape4k-dependencies`; base `develop` SHA `dcc7fa7557d3c0548b9e3fc28c48877827ea2f74`; head branch `fix/issue-1845-bouncycastle-lts8on`.
- 대상: `org.bouncycastle:bcprov-lts8on`, 중앙 alias `bouncycastle-bcprov-lts8on`; `2.73.12.1`에서 `2.73.13`으로 변경한다.
- 원인/소비자: Projects Issue #1845는 generated catalog 거버넌스 실패를 추적한다. Projects PR #1844의 exact head `6e23291a78d8fdf3528057a5451773d271acb7ee`가 해당 alias를 `2.73.13`으로 올렸지만, `Central Catalog Governance`가 “generated catalog is stale”로 실패했다. 중앙 catalog가 `2.73.13`을 제공하면 두 카탈로그의 버전이 일치한다.
- 공식 버전 근거: [Maven Central artifact record](https://central.sonatype.com/artifact/org.bouncycastle/bcprov-lts8on), [Bouncy Castle Java LTS 2.73.13 announcement](https://github.com/bcgit/bc-java/discussions/2460). 기존 catalog 주석은 `io.nats:jnats`의 전이 의존성 보안 override임을 명시한다.
- PR 생성 권한: 사용자 승인으로 `bluetape4k/bluetape4k-dependencies`, base `develop`, head `fix/issue-1845-bouncycastle-lts8on` PR 생성 및 검증까지 허용됐다. 병합·tag·release·소비자 PR/기본 브랜치 변경은 승인 범위에 포함되지 않는다.
- 변경 대상: catalog, checksum sidecar, 실제 resolved-version 변화가 확인될 때만 delta ledger, 본 체크리스트. Projects 등 형제 저장소 파일은 이 PR에서 수정하지 않는다.
- 정지 조건: PR 메타데이터와 exact-head CI/read-back을 보고한 뒤 멈춘다. Projects #1844는 이 중앙 PR만으로 닫거나 성공 처리하지 않는다.

## 기준선: 실제 resolved graph

- Projects `develop` SHA `e6a090a0812ddc207d4d7193798799b2ead4afce`에서 중앙 catalog 파일을 지정해 `:bluetape4k-nats:dependencyInsight` (`runtimeClasspath`)와 `:bluetape4k-testcontainers:dependencyInsight` (`testRuntimeClasspath`)를 확인했다. 둘 다 `io.nats:jnats:2.26.2`에서 온 `org.bouncycastle:bcprov-lts8on:2.73.10`을 선택한다.
- Projects의 checked-in Gradle source는 `bt4kLibrary("bouncycastle-bcpkix")`와 `bt4kLibrary("bouncycastle-bcprov")`를 제약으로 선언하지만, `bouncycastle-bcprov-lts8on` alias를 직접 참조하지 않는다. 따라서 중앙/generated catalog 동기화가 실제 runtime graph도 올린다고 가정하지 않는다.
- 후보 catalog를 지정한 같은 두 보고서에서 `2.73.13`이 선택되는지 다시 확인한다. 값이 그대로면 `central-catalog-version-deltas.json`에는 resolved delta를 추가하지 않고, actual dependency override는 별도 consumer 작업으로 남긴다. 이 중앙 PR은 generator freshness 오류만 해결한 것으로 기술한다.
- candidate catalog SHA-256 `11255a5e195a2e66574559fff4568e4551f5b58ab89c68fabeffa2197e331f30`를 지정한 재실행도 두 configuration 모두 `io.nats:jnats:2.26.2 -> org.bouncycastle:bcprov-lts8on:2.73.10`을 출력했다. catalog alias 변경이 resolved graph에는 반영되지 않았으므로 delta ledger는 수정하지 않는다. `2.73.13`은 공식 Sonatype artifact record와 2026-09-22 upstream announcement에서 확인했다. 해당 upstream 발표는 CVE 해결을 포함한다고 하지만, 이번 근거만으로 `2.73.10`의 특정 취약 여부를 판정하지 않는다.
- live GitHub alert #234 (`GHSA-qp49-qgx5-5m26`) read-back은 `open`, vulnerable range `< 2.73.12`, first patched version `2.73.12`, CVSS `7.5`였다. Projects graph의 `2.73.10`은 alert 범위 안이므로 이 중앙 catalog PR만으로 보안 경고가 해결되었다고 처리하지 않는다.
- 현재 Projects #1844 head는 `dependabot/gradle/org.bouncycastle-bcprov-lts8on-2.73.13` / `6e23291a78d8fdf3528057a5451773d271acb7ee`다. `Central Catalog Governance`의 stale-generation 실패는 이 PR의 base catalog가 중앙보다 낮은 상태와 일치한다.

## 실행 계획과 evidence pin

1. 저장소 정책, GNO 기록, issue/PR 상태와 exact base/head를 확인한다.
2. 격리 worktree에서 이 체크리스트를 먼저 확정하고 catalog/checksum만 수정한다.
3. resolved graph 영향, catalog 거버넌스, 9개 publisher의 POM/effective model과 중앙 build를 검증한다.
4. exact diff를 리뷰하고 Korean Lore commit을 만든 뒤 승인된 branch만 push한다.
5. 지침과 issue metadata를 재확인하고 PR을 생성한다. exact PR head의 CI, reviews, threads, labels, milestone, assignee를 다시 읽는다.

실행 위치: `.worktrees/fix/issue-1845-bouncycastle-lts8on`.

## 필수 공통 체크리스트

- [x] **CL-01 — 변경 전에 체크리스트 작성**
  - **Action:** router, 공통, Type P, POM, 문서 게이트를 변경 전에 구체화했다.
  - **Evidence:** 이 문서의 CL/CG/PUB/TOP/POM/DELTA/SPW/KO 항목.
  - **Failure:** 누락된 게이트가 있으면 source mutation을 멈추고 보충한다.
- [x] **CL-02 — 적용 범위 분류**
  - **Action:** 각 게이트를 필수, 조건부, N/A, 승인 대기로 분류한다.
  - **Evidence:** 아래 항목의 상태와 N/A 근거; 미분류 항목은 없다.
  - **Failure:** 미분류 게이트는 필수 미완료로 유지한다.
- [ ] **CL-03 — 의존 순서 준수**
  - **Action:** 아래 행을 문서 순서로 진행하고 선행 게이트 이후에만 다음 단계로 간다.
  - **Evidence:** 단계별 명령·timestamp·결과를 해당 행에 기록한다.
  - **Failure:** 순서가 어긋나면 영향받은 하위 검증을 다시 실행한다.
- [ ] **CL-04 — evidence 즉시 기록**
  - **Action:** 결과를 확인한 직후 해당 행에 기록한다.
  - **Evidence:** 명령, 파일, URL, SHA, count와 결과가 행에 있다.
  - **Failure:** evidence 없는 행은 미완료로 남긴다.
- [ ] **CL-05 — 대기 상태에서 fail-closed**
  - **Action:** 사용자 승인 또는 원격 CI 대기는 `PENDING`으로 남기고 종속 행동을 멈춘다.
  - **Evidence:** 대기 대상과 중지된 행동을 이 문서에 적는다.
  - **Failure:** 승인 대기 중 dependent side effect를 실행하면 관련 proof를 무효화한다.
- [ ] **CL-06 — 누락/순서 오류 복구**
  - **Action:** 누락되거나 순서를 어긴 증거를 복구하고 영향을 받은 후속 proof를 갱신한다.
  - **Evidence:** 복구 명령과 fresh 결과.
  - **Failure:** 복구 전에는 완료를 주장하지 않는다.
- [ ] **CL-07 — irreversible hold 갱신**
  - **Action:** PR 생성 직전 지침/issue를 재확인하고, 병합/tag/release 전에는 별도 fresh 승인과 hold를 다시 확인한다.
  - **Evidence:** 각 행동 직전의 target, authority, 현재 상태.
  - **Failure:** 오래된 승인이나 상태로 side effect를 하지 않는다.
- [ ] **CL-08 — 완료 전 집계**
  - **Action:** `Required checks: X/Y; N/A: N; Blocked: N`와 모든 미완료 ID를 보고한다.
  - **Evidence:** 아래 집계와 개별 상태가 일치한다.
  - **Failure:** 집계가 맞지 않으면 완료 보고를 보류한다.

## 공통 게이트

- [x] **CG-01 — authority 재확인**
  - **Action:** 사용자·workspace·중앙 저장소 지침, Type P skill, 현재 git 상태와 승인 내용을 읽었다.
  - **Evidence:** base `dcc7fa7557d3c0548b9e3fc28c48877827ea2f74`, 승인된 중앙 PR target과 병합/tag/release 제외 범위.
  - **Failure:** authority 또는 target 불일치 시 변경을 멈춘다.
- [x] **CG-02 — 과거/현재 근거 조회**
  - **Action:** GNO `bluetape4k-github`, `bluetape4k-docs`, `bluetape4k-wiki`를 저장소/보안 catalog 용어로 조회하고 live GitHub를 확인했다.
  - **Evidence:** 기존 Dependencies catalog train 체크리스트와 Issue #1845, PR #1844의 live state를 참고한다. 직접 `gh` 결과를 최종 authority로 사용한다.
  - **Failure:** index와 live state가 다르면 live state로 다시 판정하고 문서를 고친다.
- [x] **CG-03 — 사용자 변경과 경계 보호**
  - **Action:** clean `develop`에서 승인된 semantic branch의 격리 worktree를 만들었다.
  - **Evidence:** `.worktrees/fix/issue-1845-bouncycastle-lts8on`, base `origin/develop`; 다른 worktree는 보존한다.
  - **Failure:** dirty/unowned 상태가 발견되면 보존하고 우회하지 않는다.
- [x] **CG-04 — 정책과 언어 경계**
  - **Action:** Korean user-facing checklist/PR prose, LLM-facing operational guidance 영어, 코드 식별자 원문 보존 규칙을 적용한다.
  - **Evidence:** 승인된 중앙 저장소 파일만 변경한다.
  - **Failure:** 형제 저장소나 관리 설정을 승인 없이 수정하지 않는다.
- [x] **CG-05 — 기존 catalog pattern 재사용**
  - **Action:** 중앙 alias, Projects generated mapping, checksum 및 기존 sync/check scripts를 검토하고 같은 구조를 쓴다.
  - **Evidence:** `gradle/libs.versions.toml` alias와 `config/projects-dependabot-catalog.toml` mapping을 유지하고 sidecar만 갱신했다. 7개 non-Projects repo와 Projects `libs.project.versions.toml`에서 `sync-shared-versions --check --summary`가 clean; `sync-dependabot-ignores --check --summary`와 `sync-managed-catalog --check --summary`도 통과했다. 기본 Projects `libs.versions.toml` 검사는 7개 Dependabot-generated duplicate를 보고했으며 동일 workspace의 central `develop`에서도 같은 7개가 재현됐다. CI/정상 Projects authority 검사는 `libs.project.versions.toml`을 사용한다.
  - **Failure:** 새 generator나 의존성을 도입하지 않는다.
- [ ] **CG-06 — 공개/문서 계약 검증**
  - **Action:** 공개 API/ABI 변경 여부와 필요한 reader-facing 문서를 판정한다.
  - **Evidence:** catalog 데이터 변경만 있으므로 API/KDoc/README 계약은 N/A; 이 release checklist는 작성한다.
  - **Failure:** source/API 변경이 발견되면 해당 문서 검증을 추가한다.
- [ ] **CG-07 — 대상 검증 실행**
  - **Action:** checksum, catalog 거버넌스와 영향받는 build/테스트 검증을 수행한다.
  - **Evidence:** checksum 대조 통과; `python3.13 -m unittest tests.test_catalog_checksum tests.test_central_catalog_version_deltas tests.test_ci_catalog_governance tests.test_project_dependabot_catalog tests.test_sync_shared_versions tests.test_sync_dependabot_ignores` 116 tests OK, skipped=2; 중앙 `./gradlew --console=plain build`는 9초/4 tasks로 `BUILD SUCCESSFUL`. POM/effective-model gate는 clean exact candidate commit에서 실행 대기.
  - **Failure:** 실패 원인을 분류하고 해결 전에는 PR 생성으로 진행하지 않는다.
- [ ] **CG-08 — 무거운 검증 직렬화**
  - **Action:** 중앙 build, publisher POM 생성과 Testcontainers/DB/native 검증을 저장소별로 직렬 실행한다.
  - **Evidence:** 실제 실행 순서와 결과; 실행하지 않은 범위는 근거와 함께 N/A 또는 PENDING으로 분류한다.
  - **Failure:** 병렬 shared-state 결과는 버리고 안전하게 다시 실행한다.
- [ ] **CG-09 — lesson gate**
  - **Action:** 변경·diff·오류 복구를 검토하고 재사용 가능한 새 lesson 필요성을 결정한다.
  - **Evidence:** 기존 `docs/lessons/2026-10-09-gradle-dependabot-central-catalog.md`와 대조하고, 새 원인/가드가 없으면 N/A 근거를 기록한다.
  - **Failure:** 새 재발 방지 규칙이 필요하면 pre-PR commit에 lesson을 추가한다.
- [ ] **CG-10 — 최종 pre-PR proof 수렴**
  - **Action:** Type P/POM 검증과 diff review를 마치고 P0/P1을 해결한 exact commit을 만든다.
  - **Evidence:** 변경 파일, checks, 리뷰 결과, 최종 SHA.
  - **Failure:** 미완료 proof가 있으면 PR 생성을 보류한다.
- [ ] **CG-11 — PR 생성 권한 확인**
  - **Action:** 승인된 repository/base/head를 확인하고 pre-PR 게이트 완료를 확인한다.
  - **Evidence:** 이 문서의 사용자 승인과 exact branch.
  - **Failure:** 목표가 바뀌면 PR을 만들지 않는다.
- [ ] **CG-12 — exact branch publish**
  - **Action:** 승인된 head만 push하고 원격 SHA를 되읽는다.
  - **Evidence:** 로컬/원격 head가 같은 commit이다.
  - **Failure:** force push 없이 stale/rejected head를 진단한다.
- [ ] **CG-12A — PR 생성 직전 지침 갱신**
  - **Action:** user/workspace/repo `AGENTS.md`, leaf/common skill, PR template, issue metadata를 재확인한다.
  - **Evidence:** 확인 시각·경로·hash와 변경 없음 또는 영향 gate 재실행 기록.
  - **Failure:** drift가 있으면 PR 생성 전에 checklist와 proof를 갱신한다.
- [ ] **CG-13 — PR 생성 및 read-back**
  - **Action:** 한국어 본문으로 PR을 만들고 assignee/milestone/labels를 issue와 맞춘 뒤 live query한다.
  - **Evidence:** URL/번호, base/head SHA, 상태, 본문 마지막 `## DoD Status`.
  - **Failure:** 메타데이터나 본문 오류를 고치고 다시 읽는다.
- [ ] **CG-14 — exact-head CI와 live review**
  - **Action:** PR head의 필수 CI를 기다리고 reviews/threads를 재확인하며 독립 final review를 완료한다.
  - **Evidence:** green checks, P0=0/P1=0, unresolved thread 없음; human reviewer subgate는 단일 개발자 lane으로 입증될 때만 N/A.
  - **Failure:** CI 실패는 해당 exact head에서 수리하고 다시 확인한다.
- [ ] **CG-15 — merge-ready 보고**
  - **Action:** 완료된 scope의 evidence와 남은 승인 게이트를 수량화해 사용자에게 보고한다.
  - **Evidence:** PR/head, `Required checks: X/Y`, N/A 및 미완료 ID.
  - **Failure:** 근거가 부족하면 merge-ready라고 부르지 않는다.
- [ ] **CG-16 — fresh merge approval**
  - **Action:** CG-15 보고 뒤 exact PR/head 병합 승인을 받는다.
  - **Evidence:** 승인 대기. 현재 승인은 PR 생성까지만 허용한다.
  - **Failure:** 승인 전 병합하지 않는다.
- [ ] **CG-17 — 병합 및 확인**
  - **Action:** 승인 후 지정 전략으로 병합하고 merge SHA를 확인한다.
  - **Evidence:** 현재 범위 밖이며 승인 대기.
  - **Failure:** 현재 단계에서 실행하지 않는다.
- [ ] **CG-17A — canonical checkout 동기화**
  - **Action:** 승인된 병합 후 central develop checkout을 보존하며 동기화한다.
  - **Evidence:** 현재 범위 밖이며 병합 대기.
  - **Failure:** 병합 전 canonical checkout을 바꾸지 않는다.
- [ ] **CG-17B — 승인된 task cleanup**
  - **Action:** 동기화 후 병합된 task worktree/branch만 정리한다.
  - **Evidence:** 현재 범위 밖; 미병합 작업 worktree는 보존한다.
  - **Failure:** 이 단계에서 삭제하지 않는다.
- [ ] **CG-18 — canonical GNO 색인**
  - **Action:** 동기화와 cleanup 뒤 새 lesson이 있으면 canonical GNO에 색인하고 검색한다.
  - **Evidence:** 새 lesson 유무와 병합/동기화 상태를 확인한 뒤 결정한다.
  - **Failure:** 격리 worktree에서 canonical 색인을 만들지 않는다.

## Type P와 topology 게이트

- [ ] **PUB-01 — train identity와 authority 고정**
  - **Action:** `catalog-train-snapshot` / `dependencies-only`, target version, refs, consumer와 side-effect 범위를 고정한다.
  - **Evidence:** 위 고정 범위 및 fresh GitHub state.
  - **Failure:** identity가 달라지면 검증을 멈추고 다시 pin한다.
- [ ] **PUB-02 — live planning/topology 공백 해소**
  - **Action:** catalog train의 issue/PR/workflow/consumer 범위를 조회하고 release topology를 분류한다.
  - **Evidence:** #1845와 #1844는 열려 있음; 중앙 alias가 source of truth이고 Projects 생성 alias는 별도 소비자 상태다.
  - **Failure:** 열린 선행 작업이 있으면 downstream 단계는 대기한다.
- [ ] **TOP-01 — 저장소 분류**
  - **Action:** 중앙 dependencies repo, 8개 stable publisher와 Projects consumer를 구분한다.
  - **Evidence:** verifier의 현재 9개 publisher inventory 및 consumer map.
  - **Failure:** 미분류 publisher는 POM gate를 막는다.
- [ ] **TOP-02 — 관계 유형 지정**
  - **Action:** 각 영향 관계를 `catalogManagedBy`, publication 검증 또는 consumer/handoff로 분류한다.
  - **Evidence:** source alias와 9개 publisher 검증 map.
  - **Failure:** 카탈로그 의존을 stable release 순서로 잘못 승격하지 않는다.
- [ ] **TOP-03 — release DAG 검증**
  - **Action:** 실제 내부 artifact publication이 있는지 판단하고 필요한 경우 DAG를 계산한다.
  - **Evidence:** 이 PR은 외부 catalog metadata만 바꾸므로 artifact dispatch DAG는 N/A; POM gate는 별도로 필수다.
  - **Failure:** publication 영향이 확인되면 DAG와 order를 추가한다.
- [ ] **TOP-04 — flow/class 선택**
  - **Action:** flow를 `catalog-train-snapshot`, class를 `dependencies-only`로 확정한다.
  - **Evidence:** 변경 좌표는 외부 dependency이고 내부 BOM/library 버전은 바뀌지 않는다.
  - **Failure:** 내부 release version 변경이 발견되면 재분류한다.
- [ ] **TOP-05 — train 전환 검증**
  - **Action:** internal upstream artifact 변경과 consumer pin 순서를 판정한다.
  - **Evidence:** internal artifact release는 이 변경에 포함되지 않으며 immutable catalog ref/Projects sync는 승인 대기다.
  - **Failure:** 미래 ref나 미발행 artifact를 참조하지 않는다.
- [ ] **PUB-03a — catalog 후보 고정**
  - **Action:** 변경 전/후 catalog SHA, sidecar와 branch HEAD를 고정한다.
  - **Evidence:** catalog SHA-256, Git commit SHA, checksum check.
  - **Failure:** 입력이 바뀌면 전체 후보 proof를 무효화한다.
- [x] **DELTA-01 — resolved-version delta 판정**
  - **Action:** 보안 경고 소유 소비자인 Projects의 NATS runtime 및 Testcontainers test-runtime graph에서 기준/후보 중앙 catalog 영향을 확인한다.
  - **Evidence:** 2026-10-21 12:02–12:03 UTC, Projects `develop` SHA `e6a090a0812ddc207d4d7193798799b2ead4afce`에서 기준 catalog(`bluetape4k-dependencies` `develop` SHA `dcc7fa7557d3c0548b9e3fc28c48877827ea2f74`, catalog SHA-256 `32887e9060e334600d3ff623ba60bd17fb732f45894d29e0f4a2f1b96924af8b`) 및 후보 catalog SHA-256 `11255a5e195a2e66574559fff4568e4551f5b58ab89c68fabeffa2197e331f30`을 각각 지정해 아래 명령을 실행했다.
    - 기준 stdout: `bluetape4k-projects/build/issue-1845-baseline-dependency-insight.txt`, SHA-256 `a1d51b092a4379dcc7328b623066f4ff612ff6b0760c7d870879035cec6fb955`.
    - 후보 stdout: `bluetape4k-projects/build/issue-1845-candidate-dependency-insight.txt`, SHA-256 `96c73e0893cf9d06a5be5b3cf86ed2e5a389b936ce4906178954eace1766e766`.
    - 실행 명령(기준): `./gradlew --console=plain -Pbluetape4kDependenciesCatalogPath=/Users/debop/work/bluetape4k/bluetape4k-dependencies/gradle/libs.versions.toml :bluetape4k-nats:dependencyInsight --dependency org.bouncycastle:bcprov-lts8on --configuration runtimeClasspath :bluetape4k-testcontainers:dependencyInsight --dependency org.bouncycastle:bcprov-lts8on --configuration testRuntimeClasspath`
    - 실행 명령(후보): `./gradlew --console=plain -Pbluetape4kDependenciesCatalogPath=/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/fix/issue-1845-bouncycastle-lts8on/gradle/libs.versions.toml :bluetape4k-nats:dependencyInsight --dependency org.bouncycastle:bcprov-lts8on --configuration runtimeClasspath :bluetape4k-testcontainers:dependencyInsight --dependency org.bouncycastle:bcprov-lts8on --configuration testRuntimeClasspath`
    - 양쪽 stdout 결과: 두 task 모두 `BUILD SUCCESSFUL`; NATS `runtimeClasspath`와 Testcontainers `testRuntimeClasspath`에서 각각 `org.bouncycastle:bcprov-lts8on:2.73.10` 및 `io.nats:jnats:2.26.2` 경로를 확인했다. 기준/후보 graph가 같아 resolved delta는 없으며, actual override gap은 별도 consumer 작업으로 남는다.
    - 재현 가능한 핵심 출력:
      ```text
      > Task :bluetape4k-nats:dependencyInsight
      org.bouncycastle:bcprov-lts8on:2.73.10
      \--- io.nats:jnats:2.26.2
           \--- runtimeClasspath
      > Task :bluetape4k-testcontainers:dependencyInsight
      org.bouncycastle:bcprov-lts8on:2.73.10
      \--- io.nats:jnats:2.26.2
           \--- testRuntimeClasspath
      BUILD SUCCESSFUL
      ```
  - **Failure:** 영향이 불명확하면 `central-catalog-version-deltas.json`을 임의로 채우지 않고 PENDING으로 둔다.
- [x] **POM-01 — publisher inventory 갱신**
  - **Action:** 9개 실제 publisher와 `verify-publication-poms.py` inventory를 대조한다.
  - **Evidence:** `PUBLISHERS` 및 current CI `publication-pom-contract` inventory가 central, Projects, AWS, Exposed, Graph, Image, JaVers, Leader, Text 9개로 일치한다.
  - **Failure:** missing/extra publisher가 있으면 inventory를 설명하기 전까지 gate를 막는다.
- [ ] **POM-02 — exact candidate repository map**
  - **Action:** 중앙 catalog 후보와 각 publisher의 exact path/branch/HEAD를 담은 map을 만든다.
  - **Evidence:** map 경로·SHA-256 및 source refs.
  - **Failure:** mutable branch 이름만으로 후보를 식별하지 않는다.
- [ ] **POM-03 — 전체 publication POM/effective model**
  - **Action:** map으로 9개 publisher의 POM을 생성하고 구조 및 Maven effective model을 전부 검증한다.
  - **Evidence:** repository/POM/dependency/model/failure counts와 `failures=0`.
  - **Failure:** `--skip-generation`이나 대표 POM만으로 통과 처리하지 않는다.
- [ ] **PUB-04 — stable release preflight**
  - **Action:** stable Maven release preflight 적용 여부를 판단한다.
  - **Evidence:** catalog-only `dependencies-only` PR이며 stable Maven artifact dispatch가 없어 N/A.
  - **Failure:** release dispatch가 scope에 들어오면 전체 preflight를 새로 연다.
- [ ] **PUB-05 — immutable ref hold**
  - **Action:** `catalog/YYYY-MM-DD-NN` ref 생성 직전 fresh authority/hold를 수행한다.
  - **Evidence:** tag는 별도 승인 대상이므로 현재 PENDING.
  - **Failure:** PR 승인으로 tag를 생성하지 않는다.
- [ ] **PUB-06 — artifact dispatch/publication 확인**
  - **Action:** 승인된 artifact가 있을 때만 dispatch 후 공개 artifact를 독립 검증한다.
  - **Evidence:** 현재 변경은 Maven artifact를 publish하지 않으며 dispatch도 승인되지 않아 N/A.
  - **Failure:** workflow dispatch를 실행하지 않는다.
- [ ] **PUB-07 — GitHub release closeout**
  - **Action:** 승인된 GitHub Release와 milestone 상태를 확인한다.
  - **Evidence:** 별도 GitHub Release가 없고 현재 PR scope 밖이므로 N/A.
  - **Failure:** 이 PR에서 issue를 닫거나 release를 만들지 않는다.
- [ ] **PUB-08 — consumer synchronization**
  - **Action:** immutable catalog ref가 승인된 뒤 Projects consumer pin/PR/CI를 정렬한다.
  - **Evidence:** Projects #1844는 OPEN이며 central merge와 새 consumer 단계가 대기 중이다.
  - **Failure:** 현재 central PR만으로 Projects issue/PR을 완료 처리하지 않는다.
- [ ] **PUB-09 — next development line**
  - **Action:** 다음 SNAPSHOT line 요구 여부를 판단한다.
  - **Evidence:** 외부 library metadata만 갱신하고 internal version line을 바꾸지 않아 N/A.
  - **Failure:** 실제 internal version을 바꾸면 이 row를 다시 분류한다.
- [ ] **PUB-10 — publication documentation handoff**
  - **Action:** public install/release docs가 실제 published version을 반영하는지 판단한다.
  - **Evidence:** API/library release가 없어 public install docs 변경은 N/A; 이 checklist만 남긴다.
  - **Failure:** stable publication이 추가되면 해당 문서 handoff를 실행한다.
- [ ] **PUB-11 — 현재 phase 보고**
  - **Action:** PR scope의 결과, 검증, 남은 hold를 정확히 보고한다.
  - **Evidence:** 최종 X/Y와 PR/head/CI 및 병합/tag/release/consumer 대기 ID.
  - **Failure:** catalog train 전체를 완료했다고 과장하지 않는다.

## 문서 품질 게이트

- [x] **SPW-01 — 독자/목적/evidence 고정**
  - **Action:** central maintainer용 Korean release checklist의 목적과 source를 고정한다.
  - **Evidence:** issue/PR, catalog source, workflow skills와 official artifact links가 위에 기록됐다.
  - **Failure:** 출처 없는 기술 주장은 제거한다.
- [x] **SPW-02 — artifact contract 충족**
  - **Action:** 계획, 경계, 게이트, 실패 처리, DoD와 승인 정지를 담는다.
  - **Evidence:** 이 문서의 identity/plan/checklist sections.
  - **Failure:** 빠진 검증 또는 권한 경계를 채우기 전 실행을 보류한다.
- [ ] **SPW-03 — Korean 기술 문체**
  - **Action:** facts를 고정한 뒤 자연스러움/용어 점검을 완료한다.
  - **Evidence:** KO-01..KO-07과 `audit-korean-terms.mjs` 결과.
  - **Failure:** 의미를 바꾸는 번역이나 모호한 표현을 수정한다.
- [ ] **SPW-04 — 기술 의미와 추적성 확인**
  - **Action:** 문장별 기술 주장과 issue/catalog/source를 대조한다.
  - **Evidence:** version, SHA, URL, approval, N/A/PENDING 근거의 일치.
  - **Failure:** 불일치는 의존하는 gate 전에 수정한다.
- [ ] **SPW-05 — 렌더링 read-back/DoD 기록**
  - **Action:** 최종 Markdown을 다시 읽고 모든 SPW 결과를 기록한다.
  - **Evidence:** 최종 경로, audit 결과와 남은 gap.
  - **Failure:** read-back 전에는 문서 gate를 닫지 않는다.
- [ ] **KO-01 — 근거/수치 보존**
  - **Action:** 사실·identifier·URL·uncertainty를 원문 증거와 대조한다.
  - **Evidence:** issue `#1845`, PR `#1844`, version, SHA와 상태 대조.
  - **Failure:** 의미가 달라지면 수정한다.
- [ ] **KO-02 — 일반화 주장 제거**
  - **Action:** 근거 없는 중요성/효과 표현을 구체 행동으로 바꾼다.
  - **Evidence:** checklist 문장 검토.
  - **Failure:** 입증되지 않은 표현을 삭제하거나 한정한다.
- [ ] **KO-03 — 번역투/형식 문장 제거**
  - **Action:** 번역투와 기계적인 문장 구조를 점검한다.
  - **Evidence:** 문장 단위 naturalness review.
  - **Failure:** 부자연스러운 문장을 다듬고 재검토한다.
- [ ] **KO-04 — 용어/문체 확인**
  - **Action:** identifier는 보존하고 일반 기술어는 일관되게 쓴다.
  - **Evidence:** `catalog`, `consumer`, `resolved graph`, `PENDING` 사용이 문맥에 맞는지 검토한다.
  - **Failure:** 잘못된 의미 차이를 만드는 용어를 고친다.
- [ ] **KO-05 — 유머와 말투 제한**
  - **Action:** checklist register를 유지하고 모호한 비유를 제거한다.
  - **Evidence:** 문서에 비유나 홍보 문구가 없다.
  - **Failure:** 직접적인 표현으로 바꾼다.
- [ ] **KO-06 — 모든 reader-facing 면 확인**
  - **Action:** 제목, 본문, 목록, 링크와 metadata를 확인한다.
  - **Evidence:** 단일 Korean release checklist이며 locale parity/diagram은 범위 밖이다.
  - **Failure:** 누락된 표면을 확인한다.
- [ ] **KO-07 — 맥락 용어 audit 실행**
  - **Action:** `node ~/.codex/skills/bluetape-writer/scripts/audit-korean-terms.mjs`로 변경 파일을 검사한다.
  - **Evidence:** 결과와 모든 finding 처리 내역.
  - **Failure:** 설명되지 않은 finding이 있으면 문서 gate를 열어 둔다.

## 현재 집계

- Required checks: 계산 전 / 전체 게이트 종료 시 갱신한다.
- N/A: 각 항목의 범위 증거를 확인한 뒤 집계한다.
- Pending: PR review/CI, 별도 병합 승인, immutable catalog ref, consumer synchronization.
- Blocked: 0 목표; 실패한 검증이 생기면 원인과 복구를 기록한다.
- 제외/미실행: 병합, tag, release, Projects 파일 수정, Projects issue/PR 종료.
