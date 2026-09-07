# Issues #242/#243 의존성·서명 거버넌스 구현 계획

> **실행 규칙:** 이 계획은 `$bluetape-workflow`의 Type A 경로로 실행한다. 구현 전
> `$test-driven-development`, 완료 전 `$verification-before-completion`, 최종 검토 전
> `$requesting-code-review`를 읽고 적용한다. 각 단계는 실패 테스트, 최소 구현,
> 회귀 검증 순서를 지킨다.

**목표:** Timefold Solver `2.6.0`을 중앙 catalog/BOM 경로로 승격하고 세 소비자의
실제 계약을 검증하는 한편, 9개 JVM publisher의 signing key 해석을 하나의
canonical helper와 fail-closed 동기화 도구로 통일한다.

**구조:** 두 이슈는 같은 branch에서 작업하지만 독립 promotion unit으로 커밋하고
검증한다. #243은 Gradle API와 분리된 pure Kotlin helper를 중앙 저장소가 소유하고
각 저장소의 기존 adapter가 generated copy를 호출한다. #242는 중앙 candidate를
catalog path 또는 고유 local BOM coordinate로 주입하고, before/after graph와
소비자 테스트가 모두 통과한 뒤에만 audit policy와 delta ledger를 승격한다.

**기술:** Kotlin/JVM buildSrc, Gradle signing/maven-publish, Python 3 `unittest`,
Gradle version catalog/java-platform, Git worktree, JSON receipt

**중단 경계:** push, PR, merge, tag, workflow dispatch와 Maven Central publication은
수행하지 않는다. 하나의 promotion unit이 실패하면 그 unit만 `BLOCKED`로 기록하고,
다른 unit의 검증된 로컬 커밋은 보존한다.

---

## 저장소와 작업 공간

| 저장소 | 기준 | 영구 변경 | 검증 역할 |
| --- | --- | --- | --- |
| `bluetape4k-dependencies` | 현재 `origin/develop` 기반 worktree | canonical helper, sync/receipt 도구, Timefold catalog/BOM, 문서 | source of truth |
| `bluetape4k-projects` | 새 `origin/develop` worktree | generated helper + adapter 연결 | enhanced adapter, external caller compile |
| `bluetape4k-aws` | 새 `origin/develop` worktree | generated helper + adapter 연결 | default adapter |
| `bluetape4k-exposed` | 새 `origin/develop` worktree | generated helper + adapter 연결 | default adapter + Timefold persistence |
| `bluetape4k-graph` | 새 `origin/develop` worktree | generated helper + adapter 연결 | enhanced adapter, external caller compile |
| `bluetape4k-image` | 새 `origin/develop` worktree | generated helper + adapter 연결 | default adapter; stale checkout 재사용 금지 |
| `bluetape4k-javers` | 새 `origin/develop` worktree | generated helper + adapter 연결 | default adapter |
| `bluetape4k-leader` | 새 `origin/develop` worktree | generated helper + adapter 연결 | default adapter; 원 checkout `.flow-inputs/` 보존 |
| `bluetape4k-text` | 새 `origin/develop` worktree | generated helper + adapter 연결 | default adapter |
| `bluetape4k-experimental` | 새 exact-SHA 검증 worktree | 없음 | 기존 catalog repository map 완성 |
| `timefold-workshop` | 임시 검증 worktree | 없음 | `2.6.0` 호환성 검증 |
| `clinic-appointment` | 임시 검증 worktree | 없음 | local BOM/override 제거 graph 검증 |

모든 영구 worktree branch는 `feat/issues-242-243-governance`를 사용한다. 같은 branch
이름이 이미 존재하면 해당 exact ref와 clean 상태를 먼저 확인하고, 충돌하거나
사용자 변경이 있으면 덮어쓰지 않고 검증 receipt에 `blocked`로 기록한다.

### Task 1: exact-head worktree와 실행 receipt 골격 고정

**Files:**
- Create: `config/publishing-signing-repository-refs.json`
- Create local-only: `build/issues-242-243/repository-map.json`
- Create local-only: `build/issues-242-243/local-receipt.json`
- Create: `scripts/verify-issues-242-243-receipt.py`
- Create: `tests/test_verify_issues_242_243_receipt.py`

- [ ] **Step 1: sibling의 live `origin/develop`과 원 checkout dirty 상태 기록**

```bash
for repo in bluetape4k-projects bluetape4k-aws bluetape4k-exposed \
  bluetape4k-experimental bluetape4k-graph bluetape4k-image bluetape4k-javers \
  bluetape4k-leader bluetape4k-text timefold-workshop clinic-appointment
do
  git -C "/Users/debop/work/bluetape4k/$repo" fetch origin develop
  git -C "/Users/debop/work/bluetape4k/$repo" status --porcelain=v1
  git -C "/Users/debop/work/bluetape4k/$repo" rev-parse 'origin/develop^{commit}'
done
```

Expected: fetch 결과와 무관하게 원 checkout을 수정하지 않으며, 각 base SHA와
dirty baseline을 receipt 초안에 기록한다. fetch 직후 SHA를 shell 변수에 보존하고
뒤 단계에서 `origin/develop`을 다시 해석하지 않는다. `bluetape4k-experimental`도
동일하게 기록한다.

```bash
PROJECTS_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-projects rev-parse 'origin/develop^{commit}')
AWS_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-aws rev-parse 'origin/develop^{commit}')
EXPERIMENTAL_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-experimental rev-parse 'origin/develop^{commit}')
EXPOSED_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-exposed rev-parse 'origin/develop^{commit}')
GRAPH_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-graph rev-parse 'origin/develop^{commit}')
IMAGE_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-image rev-parse 'origin/develop^{commit}')
JAVERS_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-javers rev-parse 'origin/develop^{commit}')
LEADER_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-leader rev-parse 'origin/develop^{commit}')
TEXT_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/bluetape4k-text rev-parse 'origin/develop^{commit}')
WORKSHOP_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/timefold-workshop rev-parse 'origin/develop^{commit}')
CLINIC_BASE_SHA=$(git -C /Users/debop/work/bluetape4k/clinic-appointment rev-parse 'origin/develop^{commit}')
readonly PROJECTS_BASE_SHA AWS_BASE_SHA EXPERIMENTAL_BASE_SHA EXPOSED_BASE_SHA \
  GRAPH_BASE_SHA IMAGE_BASE_SHA JAVERS_BASE_SHA LEADER_BASE_SHA TEXT_BASE_SHA \
  WORKSHOP_BASE_SHA CLINIC_BASE_SHA
```

- [ ] **Step 2: 영구 sibling worktree 생성**

```bash
git -C /Users/debop/work/bluetape4k/bluetape4k-projects worktree add \
  .worktrees/feat/issues-242-243-governance -b feat/issues-242-243-governance "$PROJECTS_BASE_SHA"
```

나머지 7개 signing sibling과 catalog-only Experimental에도 같은 SHA 기반 형식을
적용한다. Experimental branch는 `chore/issues-242-243-validation`을 사용한다.
생성 직후 `git rev-parse HEAD`가 보존한 SHA와 같은지 비교하고 `git status
--porcelain=v1 --untracked-files=all`, `git remote get-url origin`, `git worktree list
--porcelain`을 기록한다.

Workshop과 Clinic에도 `chore/issues-242-243-validation` branch의 임시 worktree를
각각 보존한 `$WORKSHOP_BASE_SHA`, `$CLINIC_BASE_SHA`에서 만든다.

```bash
git -C /Users/debop/work/bluetape4k/timefold-workshop worktree add \
  .worktrees/chore/issues-242-243-validation \
  -b chore/issues-242-243-validation "$WORKSHOP_BASE_SHA"
git -C /Users/debop/work/bluetape4k/clinic-appointment worktree add \
  .worktrees/chore/issues-242-243-validation \
  -b chore/issues-242-243-validation "$CLINIC_BASE_SHA"
```

두 worktree도 생성 직후 HEAD equality, clean 상태, origin과 structured worktree list를
검증한 뒤 receipt consumer section에 `discovered`로 기록한다.

- [ ] **Step 3: receipt validator의 RED 테스트 작성**

다음을 실패 조건으로 고정한다.

테스트 이름은 `test_rejects_missing_repository`,
`test_rejects_blocked_or_prepared_repository`, `test_rejects_digest_mismatch`,
`test_rejects_missing_timefold_coordinate`, `test_rejects_secret_bearing_command`,
`test_accepts_exact_validated_repository_set`으로 고정한다.

local repository map은 기존 `catalog_candidate.py` schema를 그대로 사용해 중앙 +
Projects/AWS/Experimental/Exposed/Graph/Image/Javers/Leader/Text의 exact path와 SHA를
고정한다. receipt는 이 map digest와 별도 Timefold consumer section의 Workshop,
Clinic을 함께 검증한다. 필수 field는 `origin`, `clean-before`, `catalog-ref/source`,
`catalog-sha256`, `signing-sha256`, `base-head`, `candidate-head`, BOM coordinate,
local override, JDK/Gradle/configuration, elapsed/cache/result/output digest다.
legal transition은 `discovered -> prepared -> validated -> adopted`, 그리고
`discovered|prepared|validated -> blocked`뿐이다. `adopted`는 terminal state다.
채택 후 invalidation은 기존 receipt를 수정하지 않고 새 candidate ID와 receipt를 만든다.

- [ ] **Step 4: RED 확인**

```bash
python3 -m unittest tests/test_verify_issues_242_243_receipt.py
```

Expected: validator가 아직 없어서 실패한다.

- [ ] **Step 5: 최소 validator와 receipt 골격 구현**

`scripts/catalog_candidate.py`의 strict v1 repository map loader를 재사용한다.
Workshop과 Clinic은 catalog enum을 완화하지 않고 receipt의 consumer section에서
동일한 canonical path/origin/exact-head primitive로 검증한다. command 문자열에는
environment value, armor marker, password/key assignment가 없어야 한다. 초기 state는
`discovered`다. receipt 갱신은 expected previous state/HEAD/digest를 검사하고 0600
temporary file, file/directory fsync와 `os.replace()`를 사용한다.

`config/publishing-signing-repository-refs.json`은 중앙 canonical revision과 signing
sibling 8개의 candidate commit SHA를 담는 source-controlled manifest다. 최초에는
base SHA를 기록하고, 각 prepared commit 뒤 expected previous SHA를 확인해 candidate
SHA로 갱신한다. catalog-only Experimental은 local strict repository map에만 포함한다.

validator의 `transition` subcommand는 `--repository`, `--from-state`, `--to-state`,
`--expected-head`, `--expected-signing-sha256`을 모두 요구한다. deterministic 실패는
해당 repository를 `blocked`로 전이하고 dependent runner를 취소한다. 수정 뒤에는
새 worktree를 만들지 않고 보존한 last-known-good bytes와 exact base SHA에서
`discovered`부터 replay한다.

- [ ] **Step 6: GREEN 확인**

```bash
python3 -m unittest tests/test_verify_issues_242_243_receipt.py
python3 scripts/verify-issues-242-243-receipt.py \
  build/issues-242-243/local-receipt.json --allow-discovered
```

### Task 2: #243 canonical helper 계약을 테스트로 고정

**Files:**
- Create: `config/publishing-signing/PublishingSigningKeySupport.kt`
- Create: `buildSrc/src/test/kotlin/io/bluetape4k/gradle/PublishingSigningKeySupportTest.kt`
- Modify: `buildSrc/build.gradle.kts`

- [ ] **Step 1: Kotlin contract test 작성**

테스트는 아래 계약을 직접 검증한다.

```kotlin
assertEquals("90ABCDEF", normalizeSigningKeyId("1234567890ABCDEF").value)
assertEquals("0x90ABCDEF", normalizeSigningKeyId("0x1234567890ABCDEF").value)
assertEquals("1234567890ABCDEG", normalizeSigningKeyId("1234567890ABCDEG").value)
assertNull(normalizeSigningKeyId("ABCDEF12").warning)
assertFalse(normalizeSigningKeyId("1234567890ABCDEF").warning!!.contains("1234567890ABCDEF"))
```

추가 case는 공백/빈 값, uppercase prefix, 8자리, 15/17자리, escaped newline,
raw armor, valid Base64 armor, invalid Base64, valid Base64 non-armor, invalid UTF-8,
sentinel secret redaction이다. warning은 ASCII 160 bytes 이하이고 control/ANSI가
없어야 한다.

- [ ] **Step 2: RED 확인**

```bash
./gradlew -p buildSrc test --tests '*PublishingSigningKeySupportTest' \
  --no-daemon --no-configuration-cache --no-build-cache --console=plain
```

Expected: helper symbol이 없어서 compile 또는 test가 실패한다.

- [ ] **Step 3: pure helper 최소 구현**

canonical file은 `package io.bluetape4k.gradle`과 다음 API만 제공한다.

```kotlin
data class NormalizedSigningKeyId(val value: String, val warning: String?)
fun normalizeSigningKeyId(raw: String): NormalizedSigningKeyId
fun resolveSigningKeyId(raw: String): String
fun resolveSigningKey(raw: String): String
```

이 네 선언은 기존 Projects buildSrc의 visibility, parameter nullability와 반환 타입을
그대로 보존한다. adapter는 `normalizeSigningKeyId`의 warning을 사용하고 기존 외부
호출자는 `resolveSigningKeyId(String): String`을 계속 사용한다. Projects/Graph test는
함수 reference type까지 compile-time에 고정한다.

16자리 hex 본문만 trailing 8자리로 줄이고 prefix를 보존한다. Base64 decode 결과는
strict UTF-8이며 `-----BEGIN PGP PRIVATE KEY BLOCK-----` armor일 때만 채택한다.
예외 메시지와 warning에는 원문을 포함하지 않는다.

- [ ] **Step 4: canonical source를 작성하고 RED를 유지**

canonical source만 작성한다. generated copy는 직접 만들지 않는다. 같은 RED 명령이
generated source 부재 때문에 계속 실패하는지 확인하고 Task 3 sync 구현으로 넘어간다.

### Task 3: #243 sync 도구를 fail-closed로 구현

**Files:**
- Create: `scripts/sync-publishing-signing-support.py`
- Create: `scripts/run-issues-242-243-validation.py`
- Create: `tests/test_sync_publishing_signing_support.py`
- Create: `tests/test_run_issues_242_243_validation.py`
- Create: `tests/test_publishing_signing_smoke.py`
- Modify: `buildSrc/src/main/kotlin/PublishingSigningSupport.kt`
- Modify: `tests/test_ci_catalog_governance.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: sync script RED 테스트 작성**

temporary workspace fixture에서 다음을 고정한다.

테스트 이름은 `test_check_accepts_byte_identical_generated_files`,
`test_check_reports_content_drift`, `test_write_repairs_all_targets_atomically`,
`test_preflight_failure_writes_nothing`, `test_replace_failure_rolls_back_previous_targets`,
`test_rejects_symlink_and_path_escape`, `test_repo_limits_work_to_allowlisted_target`,
`test_rejects_unknown_repository`로 고정한다.

- [ ] **Step 2: RED 확인**

```bash
python3 -m unittest tests/test_sync_publishing_signing_support.py
```

- [ ] **Step 3: allowlist·preflight·atomic replacement 구현**

CLI는 `--workspace`, `--repository-map`, repeatable `--repo`, `--write`, `--check`,
`--summary`를 허용한다. strict map의 중앙 + 9개 catalog repository 중 signing
allowlist 9개만 선택한다. 모든 path/symlink/HEAD/origin/현재 bytes/mode를 먼저
검사하고, 같은 디렉터리 0600 temporary file의 fsync, mode 적용, no-follow parent
재검증, `os.replace()`, directory fsync 순으로 교체한다. 실패 시 보관한 기존
bytes/mode 또는 파일 부재 상태로 rollback하고 interruption/replay test를 실행한다.
summary에는 repository/path/digest/status만 출력한다.

- [ ] **Step 4: CI 회귀 테스트와 workflow 연결**

`tests/test_ci_catalog_governance.py`는 Python test step과 managed repository clone
후 exact-ref map 생성, clone의 origin/HEAD/clean read-back, workspace
`--repository-map "$RUNNER_TEMP/issues-242-243-repository-map.json" --check --summary`가
모두 존재함을 검사한다. clone step은
`config/publishing-signing-repository-refs.json`의 commit SHA를 직접 fetch/check out하고
origin, peeled commit, clean 상태를 map에 기록하며, drift check 직전 같은 SHA인지
다시 검사한다. fetch할 수 없는 candidate SHA는 부분 rollout으로 즉시 실패한다.
PR의 중앙 checkout 단계에서는 중앙 generated copy만 검사하고 sibling checkout을
중복 수행하지 않는다.

release workflow diagnostic은 raw armor, escaped newline, valid Base64 armor,
Base64 non-armor, invalid Base64를 canonical helper와 같은 transport 분류로 처리한다.
workflow test는 sentinel key body가 script literal, stdout/stderr와 error message에
나타나지 않는지 검사한다.

- [ ] **Step 5: GREEN 확인**

먼저 canonical source, RED helper test, sync implementation/unit test와 CI policy 변경을
bootstrap Lore commit으로 고정한다. 이 commit에서는 root build와 sync unit test가
통과하고 helper contract test만 generated source 부재라는 의도한 RED다. clean central
HEAD로 repository map을 재생성한 뒤에만 actual `--write`를 실행한다.

sync가 중앙 generated helper를 만든 직후 중앙 default-package adapter에도 네 helper
import, normalized key/key ID와 `GPG_KEY_NAME` fallback을 연결한다. 기존
`SigningConfig`, `resolveSigningConfig`, `configurePublishingSigning(String)`과 no-key,
GPG, publication 선택 동작은 sibling 기본형과 동일하게 보존한다.

```bash
python3 -m unittest tests/test_sync_publishing_signing_support.py \
  tests/test_run_issues_242_243_validation.py tests/test_ci_catalog_governance.py \
  tests/test_publishing_signing_smoke.py
python3 scripts/sync-publishing-signing-support.py \
  --workspace /Users/debop/work/bluetape4k \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" \
  --repo bluetape4k-dependencies --write --check --summary
./gradlew -p buildSrc test compileKotlin --no-daemon \
  --no-configuration-cache --no-build-cache --console=plain
```

### Task 4: #243 8개 sibling adapter를 단계적으로 연결

**Files:**
- Create in each sibling: `buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt`
- Modify in each sibling: `buildSrc/src/main/kotlin/PublishingSigningSupport.kt`
- Modify/Add in each sibling: matching `buildSrc/src/test/**/PublishingSigning*Test.kt`

- [ ] **Step 1: sync 도구로 generated helper 준비**

```bash
python3 scripts/sync-publishing-signing-support.py \
  --workspace /Users/debop/work/bluetape4k \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" \
  --write --check --summary
```

Expected: 중앙 + 8개 sibling의 generated helper가 byte-identical하다.

- [ ] **Step 2: default-package adapter 6개 RED 테스트 작성**

AWS, Exposed, Image, Javers, Leader, Text에서 기존 `SigningConfig`,
`resolveSigningConfig`, `configurePublishingSigning(String)` API를 그대로 호출한다.
Base64 armor, escaped newline, prefixed long ID와 normalized ID의 `GPG_KEY_NAME`
fallback을 검증한다.

- [ ] **Step 3: default-package adapter 최소 연결**

네 helper symbol을 explicit import한다. raw key/key ID 처리를 helper로 교체하되
publication 선택, no-key skip, GPG command와 저장소별 warning 문구는 유지한다.

- [ ] **Step 4: Projects/Graph RED 테스트 작성 후 연결**

같은 package helper를 직접 호출한다. Projects adapter의 중복
`NormalizedSigningKeyId`, `normalizeSigningKeyId`, `resolveSigningKeyId`,
`resolveSigningKey` 선언을 제거한다. `PublishingSigningConfig.keyIdWarning`,
`enabled`, `useGpgCmd`, POM helper와 외부 호출자의 compile contract를 유지한다.

- [ ] **Step 5: 저장소별 buildSrc 검증**

```bash
./gradlew -p buildSrc test compileKotlin --no-daemon \
  --no-configuration-cache --no-build-cache --console=plain
```

9개 저장소에서 repository exact HEAD와 출력 digest를 receipt에 기록한다. Python
runner가 최대 2개 저장소만 병렬 실행하고 subprocess `timeout=600`을 적용하며,
exact `(HEAD, helper digest, task set)` cache key, elapsed, retry count를 기록한다.
최초 실패 stdout/stderr는 secret-redacting wrapper를 거쳐 0600 failure artifact로
보존하고 dependent task를 취소한다.

```bash
python3 scripts/run-issues-242-243-validation.py \
  --phase signing-buildsrc \
  --execution-boundary persistent-trusted \
  --reviewed-head "$CENTRAL_REVIEWED_HEAD" \
  --reviewed-head "$PROJECTS_REVIEWED_HEAD" \
  --reviewed-head "$AWS_REVIEWED_HEAD" \
  --reviewed-head "$EXPOSED_REVIEWED_HEAD" \
  --reviewed-head "$GRAPH_REVIEWED_HEAD" \
  --reviewed-head "$IMAGE_REVIEWED_HEAD" \
  --reviewed-head "$JAVERS_REVIEWED_HEAD" \
  --reviewed-head "$LEADER_REVIEWED_HEAD" \
  --reviewed-head "$TEXT_REVIEWED_HEAD" \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" \
  --receipt "$PWD/build/issues-242-243/local-receipt.json"
```

runner evidence cache는 `build/issues-242-243/cache/`의 canonical JSON과 `0600` output
file이다. key는 repository HEAD, helper/catalog/BOM digest, task set, ordered arguments,
configuration, JDK/Gradle version이다. terminal receipt는 canonical cache output path와
key를 보존하고 실제 파일을 다시 해시한다. 같은 key의 성공 receipt와 output digest를 read-back한
경우에만 subprocess를 생략한다. Gradle build/configuration cache를 끄는 것은
cross-candidate state 재사용을 막기 위한 것이며 runner evidence cache와 구분한다.

- [ ] **Step 6: signing positive/negative smoke**

중앙 `tests/test_publishing_signing_smoke.py`가
`tests/fixtures/publishing-signing-smoke/settings.gradle.kts`와
`tests/fixtures/publishing-signing-smoke/build.gradle.kts`로 구성된 fixture publication의
실행 소유자다. fixture task는 `publishMavenPublicationToTestRepository`와
`signMavenPublication`으로 고정한다.

Python test는 fixture를 0700 temporary directory로 복사한 뒤 중앙의 정확한
`buildSrc/src/main/kotlin/PublishingSigningSupport.kt`, generated
`PublishingSigningKeySupport.kt`와 `buildSrc/build.gradle.kts`를 temporary fixture의
`buildSrc`에 복사한다. source SHA-256이 repository bytes와 같은지 먼저 검사하고
repository Gradle wrapper에 `-p`와 `Path.resolve()`가 반환한 temporary fixture의
canonical path를 별도 argv element로 전달한다. fixture build는 `maven-publish`와 `signing` plugin을 적용하고
중앙 adapter의 `configurePublishingSigning("maven")`을 호출한다. 따라서 positive
`.asc`와 malformed-key 실패 모두 canonical helper를 호출하는 실제 adapter path를
통과한다. wrapper distribution과 Kotlin DSL compiler는 중앙 wrapper/buildSrc 계약을
그대로 사용한다.
0700 temporary `GNUPGHOME`에서 batch GPG로 synthetic throwaway key를 만들고 stdin과
environment로만 전달한다. 0700 isolated `GRADLE_USER_HOME`과 file-based temporary
Maven repository에서 fixture `publish`를 실행해 `.asc`를 검사한다. malformed key +
password는 fixture signing task에서 실패해야 한다. argv는 key/password allowlist를
금지하고, redacting subprocess wrapper는 stdout/stderr, crash artifact, Gradle log와
build scan에서 sentinel/armor body 부재를 검사한다. `finally`에서 성공 임시 자료를
지우되 실패 artifact는 receipt가 가리키는 0600 경로에 보존한다. 실제 publishing
secret과 Maven Central endpoint는 사용하지 않는다.

- [ ] **Step 7: sibling별 Lore commit**

각 저장소에서 adapter test와 compile이 통과한 변경만 독립 커밋한다. commit에는
canonical digest와 실행한 test를 `Tested:` trailer에 기록한다. push하지 않는다.

### Task 5: #242 Timefold 기준선과 중앙 RED 계약 고정

**Files:**
- Modify: `tests/test_catalog_checksum.py`
- Modify: `tests/test_central_catalog_version_deltas.py`
- Modify: `tests/test_audit_latest_stable.py`
- Update local-only: `build/issues-242-243/local-receipt.json`

- [ ] **Step 1: before graph 수집**

core, benchmark, Jackson, Spring Boot starter를 실제 사용하는 configuration에서
`dependencyInsight`로 수집한다. 동일 `(HEAD, catalog/BOM digest, configuration,
coordinate)`는 한 번만 resolve한다.

전체 latest-stable delta ledger를 다시 resolve하지 않는다. validation runner의
`timefold-graphs-baseline` phase가 기존
`verify-latest-stable-resolved-graphs.py`의 observation parser와 ledger serializer를
재사용하되, 이번 이슈의 core/benchmark/Jackson/starter 네 좌표와 실제 consumer
configuration만 입력받는다. 각 child는 600초 timeout을 가진다.

```bash
python3 scripts/run-issues-242-243-validation.py \
  --phase timefold-graphs-baseline \
  --execution-boundary persistent-trusted \
  --reviewed-head "$EXPOSED_BASE_SHA" \
  --reviewed-head "$WORKSHOP_BASE_SHA" \
  --reviewed-head "$CLINIC_BASE_SHA" \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" \
  --exposed-baseline-root /absolute/path/to/bluetape4k-exposed-base-worktree \
  --workshop-baseline-root /absolute/path/to/timefold-workshop-base-worktree \
  --clinic-baseline-root /absolute/path/to/clinic-appointment-base-worktree \
  --receipt "$PWD/build/issues-242-243/local-receipt.json"
```

세 baseline worktree는 receipt에 기록된 각 `base_sha`를 정확히 checkout한 clean
worktree여야 한다. candidate worktree를 baseline에도 재사용하면 runner가 실행 전에
거부한다.

- [ ] **Step 2: 중앙 전환 RED 테스트 작성**

테스트는 `timefold-solver = "2.6.0"`, matching portable checksum,
latest-stable policy의 중앙 직접 관리 상태, 실제 before/after delta ledger의
일관성을 요구한다. consumer 검증 전에는 policy 변경을 구현하지 않는다.

- [ ] **Step 3: RED 확인**

```bash
python3 -m unittest tests/test_catalog_checksum.py \
  tests/test_central_catalog_version_deltas.py tests/test_audit_latest_stable.py
```

Expected: 현재 `2.4.0`과 defer policy 때문에 새 assertions가 실패한다.

- [ ] **Step 4: candidate catalog만 최소 변경**

`gradle/libs.versions.toml`의 `timefold-solver`를 `2.6.0`으로 바꾸고 portable
checksum을 갱신한다. BOM import와 defer policy는 아직 유지한다.

### Task 6: #242 세 소비자 candidate 검증

**Files:**
- Modify: `scripts/run-issues-242-243-validation.py`
- Modify: `tests/test_run_issues_242_243_validation.py`
- Temporary only: `timefold-workshop` 검증 worktree의 local version line
- Temporary only: `clinic-appointment` 검증 worktree의 central BOM/override wiring
- Update local-only: `build/issues-242-243/local-receipt.json`

- [ ] **Step 1: Exposed local catalog candidate 검증**

`BLUETAPE4K_DEPENDENCIES_CATALOG_PATH`를 중앙 worktree의 exact catalog path로
설정하고 checksum을 확인한다. Timefold persistence round-trip, Spring/Jackson
결합 test와 네 좌표 중 해당 configuration graph를 실행한다.

runner의 Exposed command set은 `:exposed:timefold-solver-persistence:test`와 해당
project의 `testRuntimeClasspath` dependencyInsight다.

- [ ] **Step 2: Workshop temporary override 검증**

별도 worktree에서 repo-local `2.2.0`만 `2.6.0`으로 바꾸고 incremental score,
`SolverManager` lifecycle와 benchmark/Jackson configuration을 실행한다. 이 diff는
영구 커밋하지 않으며 #54의 신규 예제를 추가하지 않는다.

runner의 Workshop command set은 `:00-shared:bluetape4k-timefold:test`,
`:01-quickstarts:school-timetabling:test`, `:exposed:jdbc-examples:test`,
`:exposed:r2dbc-examples:test`와 실제 Timefold dependency를 가진 project의
`testRuntimeClasspath` dependencyInsight다.

- [ ] **Step 3: 고유 local BOM 생성**

중앙 candidate를 `io.github.bluetape4k:bluetape4k-dependencies:
2.1.0-issue-242.local`로 전용 임시 Maven repository에 publish한다. 전용
`GRADLE_USER_HOME`, candidate repository 우선순위와 `--refresh-dependencies`를
사용한다. 생성된 POM/JAR/module metadata digest를 receipt에 기록한다.

```bash
GRADLE_USER_HOME="$CANDIDATE_GRADLE_HOME" ./gradlew publishToMavenLocal \
  -PbaseVersion=2.1.0-issue-242.local \
  -Dmaven.repo.local="$CANDIDATE_MAVEN_REPO" \
  --no-daemon --no-configuration-cache --no-build-cache --console=plain
```

두 경로는 `mktemp -d`로 만든 0700 directory의 절대 경로이며 receipt에는 값 대신
`isolated` policy와 artifact digest만 남긴다. Clinic fixture는 첫 repository를
`file://$CANDIDATE_MAVEN_REPO`로 고정하고 dependencyInsight의 component selection
reason과 local POM SHA-256이 candidate output과 같은지 read-back한다.

- [ ] **Step 4: Clinic override 제거 경로 검증**

별도 worktree에서 local Timefold override를 제거하거나 중립화하고 고유 local BOM을
주입한다. 먼저 candidate POM과 Maven effective model을 검증하고 그 artifact digest를
runner cache에 고정한다. 이어서 예약 제약, score restore, DB 반영 test와 runtime graph를 실행한다.
`2.4.0` BOM/module이 남거나 네 좌표가 `2.6.0`이 아니면 실패한다.

runner의 Clinic command set은 `:appointment-solver:test`, `:appointment-api:test`와
`:appointment-solver:dependencyInsight --configuration testRuntimeClasspath`다.
runner test는 이 allowlist, 최대 2개의 일반 Gradle worker, Testcontainers/DB와 local
BOM 단계의 순차 실행, subprocess `timeout=600`, exact cache key, elapsed/result/retry,
redacted first-failure artifact를 고정한다. 모든 Gradle command는 `--no-daemon
--no-configuration-cache --no-build-cache --console=plain`을 사용한다.
`--refresh-dependencies`는 새 catalog/BOM candidate를 처음 resolve하는 graph 단계에만
추가하며, 같은 exact evidence cache key의 test 재실행에서는 사용하지 않는다.

Process-group 종료는 같은 PGID를 유지한 정상 descendant의 bounded cleanup 계약이며 악성
`setsid()` containment 계약이 아니다. Persistent developer host에서는 approved origin,
exact reviewed HEAD, clean worktree와 immutable input을 재검증한 maintainer-trusted source만
실행한다. 외부 fork와 임의 merge ref는 이 경로에 넣지 않으며, GitHub PR에서는 secret 없는
disposable hosted runner를 job-level containment로 사용한다. 악성 source 검증이 필요하면
이 계획의 runner를 재사용하지 않고 VM/container 또는 플랫폼별 sandbox를 별도 gate로 둔다.

```bash
python3 scripts/run-issues-242-243-validation.py \
  --phase consumers \
  --execution-boundary persistent-trusted \
  --reviewed-head "$EXPOSED_REVIEWED_HEAD" \
  --reviewed-head "$WORKSHOP_REVIEWED_HEAD" \
  --reviewed-head "$CLINIC_REVIEWED_HEAD" \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" \
  --workshop-root /Users/debop/work/bluetape4k/timefold-workshop/.worktrees/chore/issues-242-243-validation \
  --clinic-root /Users/debop/work/bluetape4k/clinic-appointment/.worktrees/chore/issues-242-243-validation \
  --receipt "$PWD/build/issues-242-243/local-receipt.json"
```

- [ ] **Step 5: 실패 분류와 정리**

deterministic compile/assertion 실패는 `fail`, Docker/외부 repository 장애는
`blocked`로 기록한다. infrastructure retry는 원인 확인 뒤 한 번만 허용한다.
성공한 임시 worktree와 Maven repository만 clean 상태, exact target path와 receipt
digest를 다시 확인한 뒤 제거한다. 실패한 worktree, 0600 log와 Maven repository는
원인 재현을 위해 보존하고 receipt에 recovery path를 기록한다. 영구 sibling worktree와
사용자 원 checkout은 항상 보존한다.

### Task 7: #242 policy·delta를 검증 결과로 승격

**Files:**
- Modify: `gradle/libs.versions.toml`
- Modify: `gradle/libs.versions.toml.sha256`
- Modify: `config/latest-stable-audit-policy.json`
- Modify: `config/central-catalog-version-deltas.json`
- Update local-only: `build/issues-242-243/local-receipt.json`

- [ ] **Step 1: actual before/after graph diff 생성**

네 Timefold 좌표와 transitive change를 비교한다. preserved line은 delta로 기록하지
않고, 실제 resolved version이 바뀐 항목만 repository/configuration/evidence digest와
함께 ledger에 기록한다.

- [ ] **Step 2: policy 전환**

세 소비자가 모두 통과한 경우에만 `defer-breaking-migration`을 제거하고 기존 정책
schema가 요구하는 중앙 직접 관리 disposition으로 바꾼다. 하나라도 실패하면 catalog,
checksum, policy, delta, #242 목표-state test와 receipt의 candidate projection을 하나의
mutation manifest에 따라 되돌리고 defer 상태를 유지한다. 실패 command와 조건은 별도
blocked evidence entry에 보존해 Python 전체 suite가 baseline 계약에서 통과하도록 한다.

- [ ] **Step 3: GREEN 확인**

```bash
python3 -m unittest tests/test_catalog_checksum.py \
  tests/test_central_catalog_version_deltas.py tests/test_audit_latest_stable.py
python3 scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary
```

- [ ] **Step 4: #242 독립 Lore commit**

catalog/checksum/policy/delta와 consumer receipt가 함께 검증된 경우에만 커밋한다.
`Tested:`에는 세 소비자 exact HEAD, candidate digest와 핵심 command를 요약하고,
실제 배포 검증은 `Not-tested:`에 명시한다.

### Task 8: prepared commit과 중앙 전체 거버넌스 검증

**Files:**
- Verify: all changed central files and sibling generated/adapters

- [ ] **Step 1: prepared implementation commit과 exact map 갱신**

sibling 8개에서 adapter/generated Lore commit을 먼저 만든다. 이어서
`config/publishing-signing-repository-refs.json`을 그 sibling commit으로 갱신하고,
#243 중앙 adapter/generated/CI/manifest와 #242 중앙 candidate를 서로 다른 Lore
commit으로 고정한다. 모든 tracked 변경을 commit한 clean central HEAD에서 local strict
repository map을 다시 만든다. `build/issues-242-243/local-receipt.json`의 각 entry를
expected base HEAD/digest와 비교해 `discovered -> prepared`로 전이한다. 검증 중에는
이 local build receipt만 갱신하고 tracked receipt를 만들지 않아 strict-map clean
조건과 self-reference를 피한다.

- [ ] **Step 2: Python 전체 suite**

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

- [ ] **Step 3: catalog와 generated source drift 검사**

```bash
scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" --check --summary
scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" --check --summary
scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" --check --summary
python3 scripts/sync-publishing-signing-support.py \
  --workspace /Users/debop/work/bluetape4k \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" --check --summary
python3 scripts/verify-issues-242-243-receipt.py \
  build/issues-242-243/local-receipt.json --allow-prepared
```

- [ ] **Step 4: 중앙 build와 publication POM gate**

```bash
./gradlew build --no-daemon --no-configuration-cache --no-build-cache --console=plain
```

runner의 `publication-poms` phase는 `scripts/verify-publication-poms.py --workspace
/Users/debop/work/bluetape4k --repository-map "$PWD/build/issues-242-243/repository-map.json"
--summary` argv를 정확히 구성한다. 다음 명령을 실행하면 runner가 전체 child process에 `timeout=1800`을
적용하고 timeout 시 process group을 종료한 뒤 redacted first-failure log를 보존한다.

```bash
python3 scripts/run-issues-242-243-validation.py \
  --phase publication-poms \
  --execution-boundary persistent-trusted \
  --reviewed-head "$CENTRAL_REVIEWED_HEAD" \
  --repository-map "$PWD/build/issues-242-243/repository-map.json" \
  --receipt "$PWD/build/issues-242-243/local-receipt.json"
```

POM gate는 최대 30분, 전체 local validation은 90분으로 제한한다. POM의 모든
dependency-management entry에 effective version이 있고 Timefold BOM이 `2.6.0`을
관리하는지 확인한다.

- [ ] **Step 5: validated/adopted receipt와 evidence commit**

모든 gate가 성공하면 local receipt의 각 entry를 `prepared -> validated`로 전이하고
전체 digest를 read-back한다. 이어서 `validated -> adopted` bytes를 temporary file에
만들지만 branch ref는 아직 움직이지 않는다. 이 bytes를 tracked receipt path에 놓고
regular index에 stage한 뒤 `git write-tree`와 `git commit-tree`로 reviewed implementation
HEAD를 parent로 하는 prospective evidence commit object를 만든다. immutable strict
map은 reviewed implementation HEAD를 계속 가리키고 수정하지 않는다.

final validator는 prospective commit object의 parent가 receipt의
`reviewed-implementation-head`와 같고, 그 commit diff가 tracked receipt 한 경로만
포함하며 staged/committed bytes가 temporary adopted digest와 같은지 검사한다. 검증이
성공한 경우에만 `git update-ref`에 branch ref, validator가 반환한 40자리 prospective
object ID와 receipt의 40자리 reviewed HEAD를 argv로 전달해 compare-and-swap으로
branch를 atomic하게 채택한다. 검증이
실패하면 branch는 implementation HEAD에 남기고 index를 그 tree로 복구하며 local
receipt를 `blocked`로 기록한다. 따라서 terminal `adopted`는 검증된 ref update와 함께만
효력이 생긴다.

```bash
python3 scripts/verify-issues-242-243-receipt.py \
  docs/releases/2026-09-06-issues-242-243-local-receipt.json \
  --evidence-commit "$PROSPECTIVE_EVIDENCE_COMMIT"
```

- [ ] **Step 6: clean/diff 검사**

```bash
git diff --check
git status --short --branch
```

각 sibling도 같은 검사를 수행한다. 원 checkout의 기존 dirty 상태는 결과에서
분리하고 변경하거나 정리하지 않는다.

### Task 9: 7-Tier 최종 review와 lesson 기록

**Files:**
- Create: `docs/review/2026-09-06-issues-242-243-dependency-signing-governance-review.md`
- Create: `docs/lessons/2026-09-06-issues-242-243-dependency-signing-governance.md`
- Modify: `docs/lessons/README.md`

- [ ] **Step 1: exact refs 고정**

중앙과 8개 sibling의 HEAD, diff, generated digest, catalog/BOM digest와 receipt
digest를 review 문서 첫머리에 기록한다. 검토 중 commit이 바뀌면 모든 verdict를
stale로 보고 해당 관점을 다시 실행한다.

- [ ] **Step 2: 독립 6관점 검토**

architecture, security, stability/operations, performance, user/caller,
developer/API 관점에서 파일/line 근거와 P0/P1/P2를 받는다. P0/P1은 수정 후 해당
관점을 exact new head에서 재검토한다.

- [ ] **Step 3: 통합 7번째 관점 검토**

7-Tier 통합 검토는 다음을 분리해 판정한다.

- 기능/정합성
- security와 secret redaction
- buildSrc API/ABI 및 consumer compatibility
- fail-closed CI/운영 복구
- 성능/검증 budget
- 테스트 adequacy와 skipped/blocked 항목
- 생태계 재사용 및 중복 제거

Pass 조건은 P0=0, P1=0이다. unavailable lane은 pass로 치지 않고 `PENDING` 또는
inline review로 명확히 표시한다.

- [ ] **Step 4: lesson과 review 문서 작성**

왜 pure helper 경계를 선택했는지, staged multi-repo adoption의 한계, Timefold
candidate injection에서 catalog와 BOM을 분리한 이유, 재사용 가능한 후속 개선을
한국어로 기록한다. 문서 자연스러움 검사와 placeholder scan을 수행한다.

- [ ] **Step 5: evidence-only Lore commit과 provenance read-back**

review/lesson만 evidence-only commit으로 남긴다. 이 commit이 검토한 implementation
SHA를 바꾸지 않았고 production/config/test source를 포함하지 않는지, receipt에
기록한 reviewed implementation SHA와 `HEAD^`를 비교하고 evidence path allowlist로
검증한다. 문서
수정이 implementation 결론에 영향을 주면 verdict를 stale 처리하고 해당 관점을
다시 실행한다. 모든 branch는 로컬에 남기고 remote push는 하지 않는다.

---

## 최종 DoD

- [ ] 중앙 spec과 plan이 구현 전에 별도 Lore commit으로 고정됐다.
- [ ] #243 canonical helper test가 빈 값, armor, Base64, invalid input와 key ID mapping을 모두 통과한다.
- [ ] 중앙 + sibling 8개의 generated helper가 byte-identical하다.
- [ ] 9개 adapter의 기존 API와 저장소별 POM/GPG/missing-key 동작이 유지된다.
- [ ] synthetic signature positive smoke와 malformed-key redacted negative smoke가 통과한다.
- [ ] Timefold `2.6.0`, checksum, policy, actual delta ledger가 일치한다.
- [ ] core, benchmark, Jackson, Spring Boot starter의 before/after graph가 receipt에 있다.
- [ ] Exposed, Workshop, Clinic의 지정 계약 검증이 exact candidate에서 통과한다.
- [ ] Python suite, sync 4종, 중앙 Gradle build와 publication POM gate가 통과한다.
- [ ] receipt validator가 모든 repository를 `validated` 이상으로 판정한다.
- [ ] 7-Tier review가 exact heads에서 P0=0, P1=0이다.
- [ ] review와 lesson 문서가 있고 모든 영구 변경이 로컬 Lore commit으로 남았다.
- [ ] push/PR/merge/tag/publication은 `N/A`다.

완료 시 최종 상태는 `DONE`이다. 검증 불가 항목, consumer failure, 부분 signing
rollout 또는 stale exact ref가 하나라도 있으면 해당 promotion unit은 `PENDING`이나
`BLOCKED`이며 완료로 보고하지 않는다.
