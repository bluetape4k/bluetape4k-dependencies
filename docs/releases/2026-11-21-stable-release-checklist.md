# Bluetape4k 2026-11-21 stable release checklist

상태: **IN PROGRESS**

## 고정 입력

- 흐름: `stable-release`
- Train class: `dependencies-minor-train`
- 기준 branch: 각 저장소 `develop`
- 대상 stable 버전:
  - `2.1.0`: `bluetape4k-dependencies`, `bluetape4k-projects`, `bluetape4k-exposed`
  - `1.1.0`: `bluetape4k-aws`, `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`, `bluetape4k-text`
- 최종 순서: 8개 내부 publisher를 먼저 공개한 뒤 중앙 `bluetape4k-dependencies:2.1.0`을 마지막에 공개
- publication authority: 사용자가 2026-11-21 stable 정식 배포 진행을 명시적으로 승인
- consumer scope: 9개 managed publisher와 중앙 BOM을 사용하는 downstream consumer
- 제외: `bluetape4k-experimental`, workshop, example, application 저장소는 stable publisher가 아니므로 validation/consumer 범위만 유지

## 대상 exact head와 release artifact

| repository | target | current `develop` SHA | release workflow |
|---|---:|---|---|
| `bluetape4k-projects` | `2.1.0` | `71d450c6ad6b382a1921c800259f378092ea2c8a` | `Publish Release` |
| `bluetape4k-aws` | `1.1.0` | `4a6191bf4e2e2929d890dbb3fa631ca811551701` | `Publish Release` |
| `bluetape4k-exposed` | `2.1.0` | `76c9b14e1acfce7f7721bad1871694fac7e5f340` | `Publish Release` |
| `bluetape4k-graph` | `1.1.0` | `7ccd5ae575fb381a8fc5b6969030c3cf250a78ad` | `Publish Release` |
| `bluetape4k-image` | `1.1.0` | `ccad0059490ca84ffa8b87c2400bd81ff2f38c8d` | `Publish Release` |
| `bluetape4k-javers` | `1.1.0` | `2a35aa7c80faa06da94f350d3af3c88bb7b158cd` | `Publish Release` |
| `bluetape4k-leader` | `1.1.0` | `f22f73281a2365d31f3690327f7938fba8b21687` | `Publish Release` |
| `bluetape4k-text` | `1.1.0` | `d86c4273c6b6a56770ebfa72efc055742dbd0438` | `Publish Release` |
| `bluetape4k-dependencies` | `2.1.0` | `e2097354f25ece39f6ebd3dcafc44e27f85d3b25` | `Publish Release` |

중앙 catalog의 현재 내부 BOM ref는 모두 `-SNAPSHOT`이다. 따라서 최종 BOM은 업스트림 8개 release의 Maven Central 공개 확인 후 stable ref로 갱신한다.

## 현재 live closeout

- Image `1.1.0` milestone open issues: `0`.
- Image #513, #169는 사용자의 결정으로 `Backlog` milestone에 보존됨.
- 9개 대상 저장소의 `develop` 대상 open PR: `0`.
- 대상 stable tags `2.1.0`/`1.1.0`: 모두 아직 없음.
- 대상 changelog의 dated stable section: 아직 없음; release-prep PR에서 추가한다.

## 선행 snapshot 증거

- 8개 Nightly와 9개 Publish Snapshot run이 exact head에서 성공했다.
- 9개 coordinates의 Maven Central Snapshot metadata/POM/Gradle Module endpoint가 모두 HTTP 200이다.
- `scripts/verify-publication-poms.py --workspace .. --summary`: `failures=0`, `repositories=9`, `files=192`, `dependencies=50571`, `maven_models=192`.
- Python governance suite: `212 tests`, `OK (skipped=2)`.
- 상세 snapshot receipt: `docs/releases/2026-11-21-deprecated-api-snapshot-checklist.md`.

## Release DAG

1. `projects 2.1.0`, `aws 1.1.0`, `exposed 2.1.0`, `graph 1.1.0`, `image 1.1.0`, `javers 1.1.0`, `leader 1.1.0`, `text 1.1.0`을 각각 changelog/Full Nightly/tag/release 순서로 공개한다.
2. 각 stable BOM과 대표 artifact를 Maven Central에서 HTTP 200으로 확인한다.
3. 중앙 catalog의 8개 내부 BOM ref를 stable 버전으로 전환하고 모든 POM/effective model을 재생성한다.
4. 중앙 `bluetape4k-dependencies:2.1.0`을 마지막으로 tag/release/publication한다.
5. downstream consumer, GitHub Release/milestone, next development line을 closeout한다.

## Required checklist

- [ ] **REL-01 — 대상 inventory 고정**
  - **Action:** 저장소, 버전, exact head, artifact/BOM matrix, catalog role, consumer scope를 live source에 고정한다.
  - **Evidence:** 이 문서의 target table, workflow YAML, `gradle.properties`, catalog/build source.
  - **Failure:** identity가 바뀌면 checklist를 새로 고정한다.
- [ ] **REL-02 — issue/PR closeout**
  - **Action:** matching milestone과 release-affecting issue/PR을 live GitHub에서 확인한다.
  - **Evidence:** 9개 milestone open issues=0, open PR=0, Image deferred issues는 Backlog로 명시 보존.
  - **Failure:** 새 release-affecting work가 생기면 해당 batch를 보류한다.
- [ ] **REL-03 — snapshot train 증명**
  - **Action:** exact SHA, catalog, full Nightly, snapshot, publication-POM gate를 재사용 가능한 evidence로 고정한다.
  - **Evidence:** snapshot checklist의 7/7 완료와 9개 Central metadata/POM read-back.
  - **Failure:** mismatched/missing artifact면 stable promotion을 중지한다.
- [ ] **REL-04 — stable batch 검증**
  - **Action:** 업스트림 공개 순서와 각 release workflow의 prerequisite를 계산하고 중앙 catalog mutation과 분리한다.
  - **Evidence:** 8개 publisher → central BOM의 acyclic DAG와 Central HTTP 200 prerequisite.
  - **Failure:** downstream은 upstream public artifact 확인 전 실행하지 않는다.
- [ ] **REL-05 — dependencies 최종 gate**
  - **Action:** 모든 내부 BOM ref를 stable/public으로 바꾼 뒤 generated BOM/POM/effective model과 license/version audit를 수행한다.
  - **Evidence:** no `-SNAPSHOT`, complete publisher inventory, Maven model zero-failure summary.
  - **Failure:** SNAPSHOT 또는 missing managed version이면 중앙 BOM release를 중지한다.
- [ ] **REL-06 — consumer synchronization**
  - **Action:** 최종 BOM 공개 후 governed aliases와 repository-level validation을 downstream별로 확인한다.
  - **Evidence:** consumer별 target version, diff, resolution, tests.
  - **Failure:** Gradle help만으로 closeout하지 않는다.
- [ ] **REL-07 — next development line**
  - **Action:** stable closeout 후 다음 snapshot line과 직접 consumer를 live source에 맞춘다.
  - **Evidence:** exact develop SHA, workflow URL, public snapshot metadata.
  - **Failure:** stable branch에 SNAPSHOT 또는 future stable을 남기지 않는다.
- [ ] **REL-08 — public docs handoff**
  - **Action:** changelog, release notes, current install/baseline 문서와 locale index를 공개 버전에 맞춘다.
  - **Evidence:** target dated section, GitHub Release body, stale-version search, locale parity.
  - **Failure:** docs가 stable artifact와 다르면 closeout하지 않는다.
- [ ] **REL-09 — irreversible hold refresh**
  - **Action:** 각 tag/dispatch 직전에 tag absence, exact head, workflow inputs, open work, POM/version audit를 다시 읽는다.
  - **Evidence:** side effect 직전 timestamped live output.
  - **Failure:** stale/unknown evidence면 해당 side effect를 실행하지 않는다.

## Preflight rows

- [ ] **PRE-01 — release eligibility**: 8개 publisher와 final dependencies가 stable candidate임을 확인한다.
- [ ] **PRE-02 — live closeout**: milestone/issue/PR 상태를 각 batch 직전에 재확인한다.
- [ ] **PRE-03 — changelog**: 각 target version의 dated Korean release section을 검증한다.
- [ ] **PRE-04 — candidate execution**: exact-head Full Nightly와 matching snapshot을 검증한다.
- [ ] **PRE-05 — source version**: `snapshotVersion=` empty 및 target version/tag 일치를 검증한다.
- [ ] **PRE-06 — internal references**: 중앙 BOM의 모든 내부 ref가 stable/public인지 검증한다.
- [ ] **PRE-07 — generated BOM/POM**: 전체 publisher inventory와 Maven effective model을 검증한다.
- [ ] **PRE-08 — signing diagnostics**: 각 release workflow의 signing diagnostic을 실행/검증한다.
- [ ] **PRE-09 — artifact matrix**: 예상 group/artifact/version과 대표 POM을 고정한다.
- [ ] **PRE-10 — workflow inputs**: 정확한 release YAML의 declared inputs만 사용한다.

## Side-effect log

| action | repository | version | tag | workflow run | Central read-back |
|---|---|---:|---|---|---|
| stable release | pending | pending | pending | pending | pending |

## DoD

`Required checks: 0/19; N/A: 0; Blocked: 0` — 실행 중. Stable tag/publication이 모두 검증되기 전에는 `DONE`으로 표시하지 않는다.
