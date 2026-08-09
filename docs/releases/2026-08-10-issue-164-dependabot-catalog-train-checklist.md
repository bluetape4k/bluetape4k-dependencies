# Issue #164 Dependabot catalog train 체크리스트

상태: **진행 중 / dependencies-only catalog train**

## 고정 범위

- 대상 저장소: `bluetape4k/bluetape4k-dependencies`
- base/head: `develop` ← `security/issue-164-catalog-security-refresh`
- 기준 head: `200c2a2759567c8e7fd38277681f9c42d190d948`
- 이슈: [#164](https://github.com/bluetape4k/bluetape4k-dependencies/issues/164)
- 사용자 승인: 2026-08-10, 이슈 메타데이터 수정, commit/push 및 PR 생성 포함
- 대상: `bluetape4k-dependencies`와 게시 library 8곳의 중앙 catalog/BOM 보안 버전
- 제외: `bluetape4k-experimental`, workshop, example, application, site
- 금지: tag, catalog tag, snapshot/stable publication, GitHub Release, merge, branch/worktree 삭제

## 체크리스트 계약

- [x] **CL-01 — 변경 전에 체크리스트를 생성한다.**
  - **Action:** router, 공통 gate, Type P, topology 및 publication-POM 항목을 첫 승인 후 변경으로 기록한다.
  - **Evidence:** 이 파일이 source 변경 전 승인된 worktree에 생성되었다.
  - **Failure:** 체크리스트가 없으면 source 또는 GitHub mutation을 중단한다.
- [x] **CL-02 — 모든 항목의 적용 여부를 분류한다.**
  - **Action:** PR 전달까지는 required, merge/배포/tag/Release/cleanup은 현재 범위 밖으로 분류한다.
  - **Evidence:** `CG-01..CG-15`, `PUB-01..PUB-03`, `PUB-08`, `PUB-11`, `TOP-01..TOP-04`, `POM-01..POM-03`은 required다. `CG-16..CG-18`, `CG-X01`, `PUB-04..PUB-07`, `PUB-09..PUB-10`, `TOP-05`는 N/A다.
  - **Failure:** 미분류 항목은 required 미확인으로 취급한다.
- [x] **CL-03 — 의존 순서대로 실행한다.**
  - **Action:** preflight, 구현 검증, commit, push, PR, CI/리뷰 순서로 진행한다.
  - **Evidence:** 2026-08-10 승인 후 현재 문서 생성부터 순서대로 진행한다.
  - **Failure:** 순서를 건너뛰면 영향받은 검증부터 다시 수행한다.
- [x] **CL-04 — 증거를 확인 즉시 기록한다.**
  - **Action:** 각 gate 결과를 이 문서에 바로 반영한다.
  - **Evidence:** preflight 결과가 아래 항목에 기록되었다.
  - **Failure:** 사후 추정은 증거로 인정하지 않는다.
- [x] **CL-05 — 실패 또는 대기는 닫힌 상태로 유지한다.**
  - **Action:** 실패 시 후속 단계를 중단하고, CI/merge 승인은 `PENDING`으로 유지한다.
  - **Evidence:** merge 및 외부 배포 권한은 현재 부여되지 않았다.
  - **Failure:** 미확인 상태에서 후속 side effect를 실행하지 않는다.
- [ ] **CL-08 — 완료 전에 수치를 대조한다.**
  - **Action:** 최종 보고에서 `Required checks: X/Y; N/A: N; Blocked: N`을 계산한다.
  - **Evidence:** 최종 DoD 표와 미확인 ID 목록.
  - **Failure:** 수치가 맞지 않으면 완료를 선언하지 않는다.

## 공통 gate

- [x] **CG-01 — 권한과 현재 상태를 재확인한다.**
  - **Action:** workspace/repo `AGENTS.md`, workflow, publish, Kotlin 지침, status와 diff를 읽는다.
  - **Evidence:** 기준 head와 `origin/develop`이 일치하며 13개 tracked 변경과 resolved-graph receipt 1개가 격리 worktree에 보존되어 있다.
  - **Failure:** 권한 또는 상태가 다르면 mutation 전에 중단한다.
- [x] **CG-02 — 과거 및 현재 증거를 조회한다.**
  - **Action:** GNO와 live GitHub에서 이슈와 catalog 보안 작업을 확인한다.
  - **Evidence:** `bluetape4k-github`에서 #164를 확인했고 docs 검색은 결과 없음, wiki에서 공급망 보안 경계 기록 1건을 확인했다. live GitHub를 최종 권위로 사용한다.
  - **Failure:** 현재 상태가 필요한 결정은 live 조회 없이는 진행하지 않는다.
- [x] **CG-03 — 사용자 작업과 경계를 보호한다.**
  - **Action:** 격리 worktree와 feature branch에서만 작업하고 기존 diff를 보존한다.
  - **Evidence:** `.worktrees/issue-164-catalog-security-refresh`, branch `security/issue-164-catalog-security-refresh`, upstream `origin/develop`.
  - **Failure:** integration branch 또는 관련 없는 dirty 경로를 발견하면 중단한다.
- [x] **CG-04 — 정책과 독자 경계를 적용한다.**
  - **Action:** GitHub/commit/docs는 한국어로 작성하고 code token은 보존한다.
  - **Evidence:** workspace 및 repo-local `AGENTS.md` 정책을 재확인했다.
  - **Failure:** 언어 또는 권한 경계를 위반하면 전달 전에 수정한다.
- [x] **CG-05 — 기존 생태계 패턴을 재사용한다.**
  - **Action:** 중앙 catalog, audit, delta, Dependabot ignore, POM verifier를 기존 구현으로 사용한다.
  - **Evidence:** 새 외부 의존성이나 새 추상화 없이 기존 script/config/test surface만 수정했다.
  - **Failure:** 새 추상화/의존성이 필요하면 별도 범위로 중단한다.
- [x] **CG-06 — public/documentation 계약을 판정한다.**
  - **Action:** public API/README 변경 필요성을 확인한다.
  - **Evidence:** production source와 public API가 없는 governance repo의 version/audit 변경이므로 README/KDoc는 N/A이며 resolved-graph receipt와 본 체크리스트를 남긴다.
  - **Failure:** 사용자 계약 변화가 발견되면 문서 범위를 다시 연다.
- [x] **CG-07 — targeted 및 전체 검증을 수행한다.**
  - **Action:** Python tests, catalog sync, checksum, Gradle build를 현재 bytes에서 다시 실행한다.
  - **Evidence:** targeted 53개와 governance 11개 테스트, 전체 Python 267개가 통과했고 외부 snapshot HTTP 403 관련 2개는 명시적으로 skip됐다. shared-version/ignore/checksum/diff check와 `./gradlew build`가 통과했다.
  - **Failure:** 실패 원인을 수정하고 영향받은 검증을 재실행한다.
- [x] **CG-08 — heavyweight 검증을 직렬화한다.**
  - **Action:** publication POM 검증을 다른 heavyweight matrix와 겹치지 않게 실행한다.
  - **Evidence:** 일반 검증 완료 뒤 publication POM gate를 단독 실행해 repositories 9, files 173, dependencies 45,217, Maven models 173, failures 0을 확인했다.
  - **Failure:** 병렬 실행으로 증거가 모호하면 직렬로 다시 실행한다.
- [x] **CG-09 — lesson gate를 판정한다.**
  - **Action:** 기존 중앙 catalog/보안 라우팅 규칙으로 충분한지 현재 diff를 기준으로 평가한다.
  - **Evidence:** `docs/lessons/2026-08-10-issue-164-library-only-catalog-validation.md`에 명시적 workspace/repository scope 교훈을 기록했다.
  - **Failure:** 재사용 가능한 새 교훈을 기록하지 못하면 PR을 막는다.
- [x] **CG-10 — 최종 pre-PR 증거와 commit을 수렴한다.**
  - **Action:** diff review, P0/P1=0, fresh checks 후 Lore 형식으로 commit한다.
  - **Evidence:** source convergence commit `acc55f5f6c614321cd93c0385618162dfadee801`, P0=0/P1=0, checksum과 `git diff --check` PASS.
  - **Failure:** 미해결 P0/P1 또는 실패한 check가 있으면 commit/PR을 막는다.
- [x] **CG-11 — PR 전달 권한을 확인한다.**
  - **Action:** 승인된 repo/base/head와 선행 gate PASS를 재확인한다.
  - **Evidence:** 2026-08-10 사용자 승인, repo `bluetape4k-dependencies`, base `develop`, head `security/issue-164-catalog-security-refresh`.
  - **Failure:** 권한 불일치 시 PR 생성을 중단한다.
- [ ] **CG-12 — exact head를 push하고 원격 SHA를 확인한다.**
  - **Action:** force 없이 승인된 head를 push한다.
  - **Evidence:** local/remote SHA 일치.
  - **Failure:** 원격 충돌 또는 SHA 불일치 시 PR을 만들지 않는다.
- [ ] **CG-13 — PR을 생성하고 live metadata를 검증한다.**
  - **Action:** assignee `debop`, milestone `1.5.0`, label `dependencies`, 한국어 본문과 마지막 `## DoD Status`를 적용한다.
  - **Evidence:** PR URL, 번호, exact head, live metadata/body.
  - **Failure:** metadata 또는 본문이 다르면 CI 진행 전에 수정한다.
- [ ] **CG-14 — exact-head CI와 현재 리뷰를 확인한다.**
  - **Action:** required check와 review/thread를 live 조회한다.
  - **Evidence:** check 결론, review/thread, P0/P1=0.
  - **Failure:** 실패는 수정하고 pending은 기다린다.
- [ ] **CG-15 — merge-ready 상태를 보고한다.**
  - **Action:** exact PR/head와 체크리스트 수치를 사용자에게 보고한다.
  - **Evidence:** merge-ready DoD와 별도 merge 승인 대기.
  - **Failure:** 증거가 부족하면 merge 승인을 요청하지 않는다.

## Type P, topology 및 publication POM gate

- [x] **PUB-01 — train identity와 권한을 고정한다.**
  - **Action:** `dependencies-only` catalog train, repo/base/head, consumer/publisher 범위와 side-effect 제외를 기록한다.
  - **Evidence:** 이 문서의 고정 범위.
  - **Failure:** identity가 바뀌면 검증 전 중단한다.
- [x] **PUB-02 — live planning과 topology gap을 닫는다.**
  - **Action:** open issue/PR, publisher inventory와 제외 repository를 확인한다.
  - **Evidence:** #164는 OPEN, 승인 head의 기존 PR/원격 branch 없음, publisher 9곳과 library-only 범위를 확인했다.
  - **Failure:** 중복 PR 또는 publisher drift가 있으면 해결한다.
- [x] **PUB-03 — exact candidate state를 증명한다.**
  - **Action:** 현재 catalog bytes로 sync, audit, build 및 publication POM gate를 통과한다.
  - **Evidence:** checksum/governance/build가 통과했고 publication POM gate는 repositories 9, files/models 173, dependencies 45,217, failures 0이다.
  - **Failure:** candidate-ready를 선언하지 않는다.
- [x] **PUB-08 — 승인된 downstream library 범위를 검증한다.**
  - **Action:** projects, aws, exposed, graph, image, javers, leader, text의 중앙 version 영향과 resolved graph를 검증한다.
  - **Evidence:** 8개 library의 shared-version/ignore 검사가 clean이고 resolved graph receipt는 30 specs, 60 observations, status `verified-resolved-graph`다. experimental/workshop/app은 제외했다.
  - **Failure:** workshop/app을 범위에 넣지 않고 library 실패만 수정한다.
- [ ] **PUB-11 — release truth를 보고한다.**
  - **Action:** PR까지의 증거와 publication/tag N/A를 정확히 보고한다.
  - **Evidence:** Required/N/A/Blocked 수치와 남은 merge gate.
  - **Failure:** PR 또는 배포 상태를 과장하지 않는다.
- [x] **TOP-01 — repository를 분류한다.**
  - **Action:** dependencies, stable publisher, experimental, consumer/handoff를 구분한다.
  - **Evidence:** dependencies 1곳, stable publisher library 8곳, experimental/workshop/app 제외.
  - **Failure:** 미분류 repo를 검증/배포 대상에 넣지 않는다.
- [x] **TOP-02 — edge를 분류한다.**
  - **Action:** 이번 변경의 관계를 catalog-managed 및 publication-validation edge로 제한한다.
  - **Evidence:** internal artifact stable release edge와 publication dispatch는 없다.
  - **Failure:** release edge가 발견되면 별도 train으로 재분류한다.
- [x] **TOP-03 — 실행 graph가 순환하지 않음을 확인한다.**
  - **Action:** dependencies candidate에서 8개 publisher 검증으로 향하는 단방향 graph를 확인한다.
  - **Evidence:** `dependencies -> {projects, aws, exposed, graph, image, javers, leader, text}` 검증 순서.
  - **Failure:** 역방향 BOM 의존 또는 cycle이 있으면 중단한다.
- [x] **TOP-04 — 단일 flow/class를 선택한다.**
  - **Action:** internal versions 유지, external/security catalog 변경인 `dependencies-only`를 선택한다.
  - **Evidence:** stable/snapshot publication 및 catalog tag가 범위 밖이다.
  - **Failure:** 공개 artifact version 변경이 필요하면 별도 승인으로 전환한다.
- [x] **POM-01 — live publisher inventory를 대조한다.**
  - **Action:** verifier registry와 publish workflow 보유 repo를 확인한다.
  - **Evidence:** dependencies와 library 8곳, 총 publisher 9곳이 verifier inventory와 일치했다.
  - **Failure:** registry/workflow drift는 candidate를 차단한다.
- [x] **POM-02 — 모든 publication POM과 Maven model을 생성·검증한다.**
  - **Action:** `verify-publication-poms.py`를 generation 포함 실행한다.
  - **Evidence:** repositories 9, files 173, dependencies 45,217, Maven models 173, failures 0.
  - **Failure:** invalid/stale/missing POM 또는 model failure를 수정한다.
- [x] **POM-03 — Maven version/profile 규칙을 확인한다.**
  - **Action:** dependencyManagement version, effective management, profile 부재를 검증한다.
  - **Evidence:** generation과 structural/effective-model 검증이 failures 0으로 종료됐다.
  - **Failure:** versionless unmanaged dependency 또는 profile이 있으면 PR을 막는다.

## 현재 N/A 항목

- `CG-16..CG-18`: merge 승인, merge, cleanup은 별도 사용자 승인 이후에만 적용한다.
- `CG-X01`, `PUB-04..PUB-07`, `PUB-09..PUB-10`, `TOP-05`: tag, workflow dispatch, snapshot/stable publication, GitHub Release, next development line, public docs handoff가 승인 범위에 없다.
