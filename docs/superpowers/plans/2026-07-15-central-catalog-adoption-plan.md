# 중앙 Catalog 채택 실행 계획

## 성공 기준과 정지 조건

9개 Kotlin 라이브러리 저장소가 중앙 catalog를 실제 version authority로 사용하고, 중앙 관리 key의 로컬 재선언은 검증 도구가 차단해야 한다. 모든 변경은 로컬 `build/central-catalog-adoption` worktree branch에 남긴다. 중앙/다운스트림 후보 catalog 검증이 통과하면 이번 작업은 배포 전 `candidate-ready` 상태에서 정지한다. immutable tag, publish, push, PR, merge와 live enforcement 활성화는 수행하지 않는다.

## Task 1: 중앙 거버넌스 테스트를 실패 상태로 추가

**Files**

- Modify: `tests/test_sync_shared_versions.py`
- Test: `python3 -m unittest tests/test_sync_shared_versions.py`

**Steps**

1. `bluetape4k-experimental`을 active library repository 목록에 포함하는 실패 테스트를 추가한다.
2. 중앙 version key가 downstream `[versions]`에 동일 값으로 존재해도 중복으로 판정하는 테스트를 추가한다.
3. exact library `group:artifact`와 exact plugin id 중복을 판정하고 same-group/different-artifact, alias collision, plugin-id mismatch를 거부하는 테스트를 추가한다.
4. 같은 이름이 다른 compatibility family를 뜻하는 경우 명시적 예외 없이는 실패하는 테스트를 추가한다.
5. `repository`, `key`, `central-key`, `expected-local-version`, `reason`, `issue`, `owner`, `introduced`, `review-by`가 있는 예외만 허용하고 stale/unknown/expired/duplicate field를 거부하는 테스트를 추가한다.
6. equal/different duplicate 모두 `--write`가 변경하지 않는 테스트와 Jackson 3/QueryDSL 5 pin 보존 테스트를 추가한다.
7. managed repository enum, canonical worktree map, regular non-symlink file, path traversal/unknown/missing repository 거부 테스트를 추가한다.
8. 기존 compatibility major 검사가 유지되는 테스트를 보강한다.
9. 테스트를 실행해 새 테스트가 구현 부재로 실패하는지 확인한다.

## Task 2: 중앙 adoption guard와 예외 계약 구현

**Files**

- Modify: `scripts/sync-shared-versions.py`
- Create: `config/central-catalog-exceptions.toml`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_sync_shared_versions.py`

**Steps**

1. downstream catalog의 `[versions]`, library coordinate/`version.ref`, plugin id/`version.ref`를 구조적으로 읽는 모델을 추가한다.
2. 중앙 관리 key 및 exact coordinate/plugin id 재선언을 adoption gap으로 보고하는 read-only 검사를 추가한다.
3. strict schema의 `config/central-catalog-exceptions.toml`을 읽고 compatibility family, expected local value, reason, same-org issue, owner, introduced, review-by를 검증한다.
4. `--write`는 중앙 중복과 compatibility 예외를 모두 변경하지 않는다. legacy value-copy test를 제거하고 guard-only semantics를 고정한다.
5. repeatable `--repo-root repo=/absolute/worktree` 또는 `--repository-map`으로 후보 worktree path/branch/expected HEAD를 명시하고 canonical path를 검증한다.
6. `--check --summary`와 deterministic `--format json`을 지원한다. 각 record는 repo/path/key, local/central coordinate와 value, exception 상태, remediation을 포함하고 config error와 adoption gap exit code를 구분한다.
7. PR CI에서는 central repo 자체/unit fixture와 명시된 단일 repository만 fail-fast 검증하고, 전체 workspace audit는 rollout 완료 전 report-only로 둔다. scheduled/manual audit 활성화는 별도 rollout 단계다.
8. 9개 downstream CI에 pinned central checkout과 single-repository guard를 호출하는 reusable workflow/동등한 local step을 추가해 중복이 PR에서 재도입되지 않게 한다. rollout 중에는 각 저장소 자기 catalog만 검사한다.
9. 문서에 기존 `--write` 자동 교정과 새 read-only guard 동작, exit code, 수동 migration 예시를 기록하고 `--write`를 deprecated compatibility option으로 표시한다. 영어 README와 한국어 README를 함께 갱신한다.
10. unit test 전체와 `./gradlew build`를 실행한다.

## Task 3: 중앙 shared plugin alias 완성

**Files**

- Modify: `gradle/libs.versions.toml`
- Test: `tests/test_sync_shared_versions.py`

**Steps**

1. 9개 downstream catalog의 모든 plugin과 `version.ref`를 inventory하고, 중앙 version key를 참조하는 각 plugin을 `central-plugin-alias`, `compatibility-exception`, `repo-owned` 중 하나로 분류한다.
2. Kotlin JVM/Spring/allopen/noarg/JPA/serialization/kapt, Spring Boot 3/4, dependency-management, Dokka, NMCP/aggregation, Exposed, Kover, Shadow, Gatling을 포함해 중앙 관리 version을 사용하는 shared plugin id를 중앙 catalog에 추가한다.
3. Spring Boot 3/4처럼 compatibility line이 분리되는 shared plugin alias를 명확한 이름으로 추가한다.
4. expected Gradle accessors와 exact plugin id/version ref를 unit fixture 또는 catalog parser test로 검증한다.
5. 모든 중앙 version key 참조 plugin에 disposition이 있고 미분류 항목이 0인지 테스트한다.
6. central `./gradlew build`로 catalog syntax와 accessor를 검증한다.

## Task 4: compatibility 분류와 baseline 고정

1. AWS Jackson 3, Exposed QueryDSL 5, Experimental의 7개 drift를 bulk replacement 전에 표로 분류한다.
2. 각 family를 `central-direct`, `central-version-local-alias`, `compatibility-exception`, `repo-owned` 중 하나로 확정한다.
3. Experimental은 migration 전후 dependency/plugin resolution report를 비교하고 각 delta를 보존 pin 또는 명시적 migration decision으로 분류한다.
4. 모든 예외를 중앙 exception file에 먼저 등록하고 bulk replacement task의 exclusion input으로 사용한다.

## Task 5: 공통 catalog import trust 계약 정리

**Repositories**

- `bluetape4k-experimental`
- 필요 시 나머지 8개 library repository의 `settings.gradle.kts`

**Steps**

1. `bluetape4k-experimental`의 Maven version-catalog artifact import를 file-based `bt4k` catalog import로 교체한다.
2. implicit sibling discovery를 제거하고 explicit regular non-symlink path 또는 official immutable ref만 허용한다.
3. remote/cache 경로는 fixed HTTPS origin, bounded timeout/size, TOML/required-marker parse, temporary download+atomic move, content SHA-256 검증을 요구한다.
4. invalid explicit path, symlink, malformed/symbolic ref, missing/moved tag, digest mismatch, corrupt cache, offline cache reuse를 settings smoke fixture로 검증한다.
5. 9개 저장소에서 후보 path `bt4k` accessor 생성 여부를 `./gradlew help`로 검증한다.

## Task 6: 직접 중앙 plugin alias 채택

**Repositories**

- 9개 library repository의 root/module `build.gradle.kts`
- 각 repository의 `gradle/libs.versions.toml`

**Steps**

1. Task 3에서 `central-plugin-alias`로 분류한 모든 plugin을 `bt4k.plugins.*`로 교체한다. Kotlin plugin suite, Spring Boot compatibility aliases, dependency-management, Dokka, NMCP/aggregation, Exposed, Kover, Shadow, Gatling을 빠뜨리지 않는다.
2. 더 이상 참조하지 않는 local plugin alias와 local version key를 제거한다.
3. repository 전용 plugin과 중앙에 없는 plugin은 local catalog에 유지한다.
4. local plugin `version.ref`가 예외 없이 중앙 version key를 가리키는 항목이 0인지 guard로 확인한다.
5. 각 저장소에서 `./gradlew help`를 실행해 Kotlin DSL accessor와 plugin resolution을 검증한다.

## Task 7: 중앙 BOM과 동일 coordinate library alias 채택

**Repositories**

- `bluetape4k-image`, `bluetape4k-text`
- `bluetape4k-javers`, `bluetape4k-leader`
- `bluetape4k-aws`, `bluetape4k-graph`
- `bluetape4k-experimental`, `bluetape4k-exposed`, `bluetape4k-projects`

**Steps**

1. Task 4의 compatibility classification을 exclusion input으로 사용하고, 위험이 낮은 저장소부터 exact coordinate가 같은 중앙 BOM/library alias를 `bt4k.*` 직접 참조로 교체한다.
2. local-only coordinate가 중앙 BOM/dependency-management에 포함되면 versionless alias로 바꾼다.
3. 중앙 alias가 없고 BOM이 version을 공급하지 않는 local-only coordinate는 `bt4k.versions.*`에서 root dependency management로 한 번만 version을 주입한다.
4. 제거된 alias가 build script에 남지 않았는지 repository-wide literal search로 확인한다.
5. 각 저장소에서 `./gradlew help` 후 영향 모듈 compile/build를 실행한다.

## Task 8: repository별 검증과 단계적 rollback gate

1. repository별 exact `help`, compile/build, dependency resolution 명령 표를 작성한다.
2. 후보 path로 configuration/build/resolution을 실행하고 migration 전후 resolved `group:artifact:version`과 plugin id/version을 비교한다.
3. declared ref 검증은 새 immutable train ref가 없으면 `blocked-until-tag`로 기록하고 live integration/enforcement를 금지한다.
4. rollback trigger와 last-known-good SHA를 ledger에 기록한다. 실패한 downstream은 revert하고 audit는 repair될 때까지 실패/partial로 둔다. rollback용 예외는 금지하고 compatibility exception만 허용한다.

### 저장소별 필수 검증 매트릭스

모든 명령은 후보 path 모드와, immutable train ref가 준비된 뒤 fresh `GRADLE_USER_HOME`의 declared-ref 모드에서 각각 실행한다. migration 전후 같은 명령의 resolved `group:artifact:version` report를 정렬 비교한다.

| 저장소 | configuration/build gate | representative resolution gate |
|---|---|---|
| `bluetape4k-projects` | `./gradlew :bluetape4k-core:compileKotlin build` | `./gradlew :bluetape4k-core:dependencies --configuration compileClasspath` |
| `bluetape4k-experimental` | `./gradlew :shared:compileKotlin build` | `./gradlew :shared:dependencies --configuration compileClasspath` |
| `bluetape4k-aws` | `./gradlew :bluetape4k-aws-java:compileKotlin build` | `./gradlew :bluetape4k-aws-java:dependencies --configuration compileClasspath` |
| `bluetape4k-exposed` | `./gradlew :bluetape4k-exposed-core:compileKotlin build` | `./gradlew :bluetape4k-exposed-core:dependencies --configuration compileClasspath` |
| `bluetape4k-graph` | `./gradlew :bluetape4k-graph-core:compileKotlin build` | `./gradlew :bluetape4k-graph-core:dependencies --configuration compileClasspath` |
| `bluetape4k-image` | `./gradlew :bluetape4k-images:compileKotlin build` | `./gradlew :bluetape4k-images:dependencies --configuration compileClasspath` |
| `bluetape4k-javers` | `./gradlew :javers-core:compileKotlin build` | `./gradlew :javers-core:dependencies --configuration compileClasspath` |
| `bluetape4k-leader` | `./gradlew :bluetape4k-leader-core:compileKotlin build` | `./gradlew :bluetape4k-leader-core:dependencies --configuration compileClasspath` |
| `bluetape4k-text` | `./gradlew :tokenizer-core:compileKotlin build` | `./gradlew :tokenizer-core:dependencies --configuration compileClasspath` |

versionless alias 또는 compatibility family가 representative module 밖에서만 쓰이면 해당 module/configuration의 `dependencies` 또는 `dependencyInsight --dependency <group-or-module> --configuration <configuration>`을 추가한다.

## Task 9: repository-wide 검증과 잔여 중복 보고

**Commands**

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
scripts/sync-shared-versions.py --repository-map <candidate-worktrees.json> --check --summary
scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary
./gradlew build --no-daemon --no-configuration-cache --console=plain
```

각 downstream worktree에서 다음을 실행한다.

```bash
BLUETAPE4K_DEPENDENCIES_CATALOG_PATH=<central-worktree>/gradle/libs.versions.toml \
  ./gradlew help --no-daemon --no-configuration-cache --console=plain
```

그리고 Task 8의 repository별 exact compile/build/dependency-resolution 명령을 실행한다.

**Evidence**

1. 중앙 guard summary/JSON에서 허용되지 않은 version/coordinate/plugin 중복 0건을 확인한다.
2. 9개 downstream `help`가 모두 exit 0인지 확인한다.
3. targeted/full build와 dependency resolution 비교 결과의 fresh exit status를 기록한다.
4. rollout ledger에 10개 worktree의 path, branch, base/head SHA, declared ref, candidate catalog SHA, guard/help/build 결과, rollback SHA를 기록한다.
5. 모든 entry가 같은 catalog SHA를 사용하지 않으면 `partial`로 판정하고 enforcement를 활성화하지 않는다.
6. 의도한 파일 외 변경, generated noise, credential 또는 publish side effect가 없는지 검토한다.

## Task 10: 배포 경계, 독립 리뷰와 로컬 handoff

1. 중앙 guard와 downstream diff를 correctness, compatibility, test coverage 관점으로 독립 리뷰한다.
2. P0/P1을 모두 수정하고 관련 검증을 재실행한다.
3. P2/P3은 이번 범위에서 수정하거나 이유와 후속 issue 필요성을 기록한다.
4. `.github/workflows/publish-snapshot.yml`의 develop-push 자동 snapshot 조건을 확인하고 governance-only merge의 publishable-path gate가 없으면 중앙 push/merge를 snapshot 승인 전까지 차단한다.
5. 완료된 local branch/worktree, rollout ledger, `candidate-ready` 또는 `partial/blocked-until-tag` 상태를 사용자에게 전달한다.
6. push, PR, merge, catalog tag, Maven publish, live cross-repo enforcement는 별도 명시 요청 전까지 수행하지 않는다.

## Exception schema 예시

```toml
[[exception]]
repository = "bluetape4k-exposed"
key = "querydsl5"
central-key = "querydsl"
kind = "library-version"
coordinate = "com.querydsl:querydsl-core"
expected-local-version = "5.1.0"
compatibility-family = "querydsl-javax"
reason = "The repository still compiles against the javax QueryDSL line."
issue = "https://github.com/bluetape4k/bluetape4k-exposed/issues/NNN"
owner = "bluetape4k-exposed-maintainers"
introduced = "2026-07-15"
review-by = "2026-10-15"
resolution-condition = "Remove after the QueryDSL 7 migration passes source and resolved-graph checks."
```

guard는 malformed/unknown field, duplicate repository+key, orphan local key, already-resolved duplicate, non-canonical issue URL, 빈 reason/owner, expired review-by를 실패시킨다.
