# Issue #208 Kotlinx Serialization Catalog Design

- Date: 2026-07-13
- Consumer issue: `bluetape4k-image#208`
- Work type: Type A prerequisite with a later Type P catalog-tag gate
- Approval: the user approved the central-catalog scope expansion in the active thread

## Problem

`bluetape4k-image`의 benchmark harness가
`org.jetbrains.kotlinx:kotlinx-serialization-json`을 직접 사용하지만, 로컬
`libs.kotlinx.serialization.json` alias에는 version이 없다. 승인된 Issue #208
계획대로 로컬 version pin을 제거하면 Gradle은
`kotlinx-serialization-json:.`을 해석하지 못하고 `compileKotlin`이 실패한다.

로컬 `1.11.0` pin은 빌드를 통과시키지만, 공통 dependency version을
`bluetape4k-dependencies`에서 관리한다는 workspace 정책과 Issue #208의 범위
경계를 위반한다.

## Chosen Design

1. `bluetape4k-dependencies/gradle/libs.versions.toml`에
   `kotlinx-serialization = "1.11.0"`을 source-of-truth version으로 추가한다.
2. 같은 catalog에 versioned `kotlinx-serialization-bom`과
   `kotlinx-serialization-json` alias를 추가한다.
3. `bluetape4k-dependencies` Java platform은
   `api(platform(libs.kotlinx.serialization.bom))`으로 serialization family를
   정렬한다. Catalog ref와 Maven BOM 계약은 별개지만 동일 version line에서
   검증한다.
4. `bluetape4k-image`는 로컬 version pin 대신
   `implementation(bt4k.kotlinx.serialization.json)`을 사용한다. Tag 전 검증은
   `-Pbluetape4kDependenciesCatalogPath=<central-worktree>/gradle/libs.versions.toml`
   로 수행한다.
5. 중앙 PR이 `develop`에 merge된 뒤에만 `catalog/2026-07-13-00` tag를 만들고,
   tag 직전에는 별도의 최신 승인을 받는다. 이후 image의 기본 catalog ref를
   해당 tag로 갱신한다.

## Rejected Alternatives

- **Repo-local `1.11.0` pin:** 가장 작지만 source-of-truth를 중복하고 향후
  drift를 만든다.
- **Unversioned local alias 유지:** 현재 dependency-resolution 증거로 실패한다.
- **다른 JSON 구현 또는 수동 JSON:** 승인된 harness architecture와 strict
  serialization contract를 불필요하게 바꾼다.

## Boundaries

- Central scope: catalog version/aliases, serialization BOM import, focused
  contract test, validation evidence, lesson/review artifacts.
- Consumer scope: benchmark module dependency accessor, local catalog pin 제거,
  catalog ref 갱신, focused Kotlin test.
- No production image API, module registration, CI/Nightly, native backend,
  publication version, or Maven Central release change.
- `sync-dependabot-ignores.py` already owns `org.jetbrains.kotlinx*`; no ignore
  entry change is required.
- `sync-shared-versions.py` may update only downstream repositories that already
  declare the same `kotlinx-serialization` version alias. Any unexpected drift
  reopens the downstream scope before writes are committed.

## Failure Modes and Guards

| Failure | Guard |
|---|---|
| JSON alias exists but has no version | focused catalog contract test checks version ref and exact version |
| Catalog and BOM drift | contract test checks aliases plus `api(platform(...))`; Gradle build resolves both |
| Wrong or stale catalog tag | tag target is the merged central `origin/develop` SHA and requires fresh CG-X01 approval |
| Downstream mass rewrite | run sync in check mode first; unexpected paths stop the train |
| Image works only with local checkout | after tag, rerun without catalog-path override against the pinned ref |

## Acceptance Criteria

- Central catalog exposes Serialization 1.11.0 BOM and JSON aliases.
- Central BOM imports the matching Serialization BOM.
- Central Python tests, catalog checks, Gradle build, and local publication pass.
- Image focused tests pass with the central worktree catalog and no local
  serialization version pin.
- The eventual tag points to merged `origin/develop`, is absent before creation,
  and is pushed only after fresh explicit approval.
- PR and merge boundaries remain governed independently for both repositories.
