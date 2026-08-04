# Issue #168 외부 의존성 버전 권한 중앙화 설계

## 배경

2026-07 중앙 catalog 채택 train은 immutable `bt4k` catalog import, checksum 검증,
중앙 항목의 중복 권한 guard, downstream publication POM 검증을 도입했다. 그러나
2026-08-03의 9개 관리 library repository 감사에서는 중앙 catalog에 아직 없는 외부
library coordinate 357개와 Gradle plugin ID 9개가 명시 버전을 계속 소유하고 있음을
확인했다.

감사 기준은 각 downstream `gradle/libs.versions.toml`의 외부 coordinate와 plugin ID의
명시 버전이다. 결과는 다음과 같다.

| 구분 | 수량 | 처리 원칙 |
| --- | ---: | --- |
| 명시 외부 library 선언 | 864 | 각 선언의 중앙화 disposition을 기록한다. |
| 중앙 미등록 고유 coordinate | 357 | 중앙 alias 또는 중앙 version key의 후보다. |
| 다중 repository coordinate | 320 | 동일 버전은 직접 중앙화하고, 충돌은 분류한다. |
| 동일 버전 다중 repository coordinate | 287 | resolved graph가 보존되면 중앙 authority로 이전한다. |
| 버전 충돌 coordinate | 33 | 단순 drift, BOM 관리, compatibility line을 구분한다. |
| repository 전용 coordinate | 37 | 중앙 version authority로 승격 가능한지 판단한다. |
| downstream 명시 plugin ID | 9 | 중앙 plugin alias 또는 compatibility alias로 전환한다. |
| Gradle 하드코딩 후보 | 43 | alias/accessor로 전환하거나 구조적 예외를 문서화한다. |

`scripts/sync-shared-versions.py --check`가 현재 통과하는 것은 오류가 아니라 기존
guard의 범위 때문이다. 이 guard는 이미 중앙에 등록된 coordinate/plugin ID의 중복만
찾으므로, 아직 중앙에 없는 반복 권한을 발견하는 보고 기능이 필요하다.

## 목표와 경계

목표는 `bluetape4k-dependencies/gradle/libs.versions.toml`을 관리 대상
`bluetape4k-*` library repository의 외부 dependency/plugin version에 대한 최대한의
source of truth로 만드는 것이다. downstream은 중앙 alias를 직접 사용하거나,
중앙 `bt4k.versions.*`를 참조하는 versionless local alias를 사용한다.

이번 범위에는 `bluetape4k-projects`, `bluetape4k-aws`,
`bluetape4k-experimental`, `bluetape4k-exposed`, `bluetape4k-graph`,
`bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`,
`bluetape4k-text`가 포함된다.

Maven publication, catalog tag 생성/이동, GitHub PR 생성/merge, `1.4.0` 배포는
범위 밖이다. 의도하지 않은 dependency upgrade와 production API 변경도 범위 밖이다.

## 선택지와 결정

### 선택지 A: 중앙 catalog에 version과 alias를 두고 downstream이 직접 소비

중앙 catalog에 공통 alias와 version key를 추가하고, downstream build script를
`bt4k.*` 또는 `bt4k.versions.*`로 바꾼다. 동일 coordinate가 여러 저장소에 있으면
한 중앙 alias를 사용하고, local-only 이름이 필요하면 versionless local alias만
남긴다.

이 방식을 선택한다. 현재 immutable catalog ref/checksum 계약과 가장 잘 맞고,
`sync-shared-versions.py`의 기존 duplicate-authority guard를 자연스럽게 확장할 수
있다.

### 선택지 B: 중앙 version key만 추가하고 모든 local alias를 유지

이 방식은 전환 diff가 작지만, 같은 coordinate의 alias/구조가 계속 여러 repository에
복제된다. alias identity 충돌과 hard-coded coordinate를 줄이지 못하므로 선택하지
않는다.

### 선택지 C: 중앙/로컬 catalog를 합성한 generated catalog를 도입

모든 build script를 `libs.*`로 유지할 수 있지만, 생성물 소유권과 immutable ref의
우선순위가 복잡해지고 현재 catalog import 신뢰 계약을 약화한다. 별도 generator는
추가하지 않는다.

## 설계

### 1. disposition inventory와 guard

새 report는 중앙에 없는 외부 coordinate/plugin ID를 repository 수, resolved version,
alias, 사용 위치 기준으로 출력한다. 각 항목에는 다음 disposition 중 정확히 하나가
있어야 한다.

- `central-direct`: 중앙 alias를 직접 사용한다.
- `central-version-local-alias`: 중앙 version key를 사용하는 repository-local alias를
  유지한다.
- `bom-managed-versionless`: 같은 published POM에서 versioned imported BOM 또는
  dependency management가 version을 제공한다는 POM 검증 근거가 있다.
- `compatibility-line`: major/ABI/지원 matrix가 다른 중앙 alias와 key를 사용한다.
- `structural-repo-owned`: settings plugin resolution 같이 `bt4k` accessor가 생기기 전의
  구조적 제약 또는 실제 단일 저장소 소유 제약이다.

report는 후보를 발견할 뿐 자동 수정하지 않는다. 예외는 기존 strict
`config/central-catalog-exceptions.toml` 계약을 따라 issue, owner, review-by,
resolution condition을 가져야 한다.

inventory는 candidate SHA마다 한 번 전체 생성하는 deterministic JSON artifact다. 각
record는 `authority-id`, `line-id`, `occurrence-id`, `repository`, semantic `subject-kind`
(`library`/`plugin`), mutable `declaration-form` (`catalog`/`hard-coded`),
`coordinate-or-plugin-id`, `alias`, `source-path:line`, `declared-version`,
`resolved-version`, `repository-count`, `disposition`, `evidence`, `owner`를 가진다.
`authority-id`는 repository/semantic subject-kind/coordinate-or-plugin-id를 canonical UTF-8로
연결한 SHA-256이므로 alias, source path, compatibility family와 declaration-form이 바뀌어도
유지된다. hard-coded coordinate/plugin ID는 parser가 source context로 semantic subject-kind를
분류하며, catalog alias로의 변환은 같은 authority identity를 유지한다.
`line-id`는 기본 line이면 `default`이고, 동시에 유지해야 하는 ABI/major compatibility
line이면 `config/central-catalog-authority-lines.json`에 repository, semantic subject,
coordinate/plugin ID, alias selector와 source-controlled canonical identifier(예:
`spring-boot-3`)를 선언한다. selector는 inventory occurrence와 정확히 일치해야 하며,
중복·미사용 selector는 실패한다. `line-id`는 alias/path/declared version에서 파생하지
않으며 명시적 follow-up 없이 변경할 수 없다. `occurrence-id`는
authority-id/line-id/alias/source path/line의 SHA-256이다.
G4는 `(authority-id, line-id)`별 before/after occurrence lineage를 기록해 alias 제거·이동·병합을
reconcile하고, unreconciled deletion/addition은 fail-closed다. aggregate summary는 별도
JSON으로 만든다. migration 반복에서는
변경된 catalog/Gradle source만 incremental scan할 수 있지만, G8 직전에는 항상 전체
inventory를 다시 생성한다.

source-controlled `config/central-catalog-authority-dispositions.json`은 모든 inventory
`(authority-id, line-id)`와 disposition, evidence type/path, status, owner를 one-to-one으로
선언한다. inventory에 없는 pair, inventory의 누락 pair, 복수 disposition, 허용되지 않은 disposition/evidence 조합은
실패다. `bom-managed-versionless`는 generated POM/effective-model evidence 없이는,
`structural-repo-owned`는 settings evaluation evidence와 만료 가능한 same-repository issue
없이는 유효하지 않다. exception TOML은 disposition manifest를 대체하지 않으며 실제
compatibility 또는 direct-adoption exemption에만 사용한다.

disposition은 우선순위에 따라 하나만 선택한다. accessor 평가 전인 구조적 제약은
`structural-repo-owned`, 실제 ABI/major family 차이는 `compatibility-line`, 같은 POM의
관리 근거가 확인된 경우는 `bom-managed-versionless`, 중앙 alias를 바로 쓸 수 있으면
`central-direct`, local alias 이름을 유지해야 할 때만
`central-version-local-alias`다. compatibility/structural exception은 정확한
repository + local key + central key + semantic subject-kind + coordinate/plugin ID + expected local version
및 canonical line-id에만 일치하고, wildcard/dynamic selector는 허용하지 않는다. 기존
TOML schema의 reason, canonical same-repository issue URL, owner, introduced, review-by,
resolution-condition은 모두 필수이며, expired/unknown/duplicate entry는 fail-closed다.
예외는 trust, checksum, credential, POM, resolved-graph gate를 우회하지 못한다.

### 1-1. 후보 topology와 catalog lock

모든 downstream 검증은 후보 `repository-map`과 별도 catalog lock을 먼저 통과해야
한다. map은 관리 repository enum(공유 catalog만 소비하는 `bluetape4k-experimental`
포함)의 각 entry에 대해 canonical absolute catalog path, regular-file/non-symlink
여부, candidate branch, base SHA, expected HEAD를 가진다. 경로 traversal, workspace
밖의 path, duplicate path, detached branch, dirty worktree, unknown/missing repository는
검증 시작 전에 실패한다.

catalog lock은 central candidate의 canonical path, raw
`gradle/libs.versions.toml` bytes의 SHA-256, central branch/HEAD, 대상 immutable catalog
ref와 peel된 commit을 기록한다. 각 downstream entry는 실제 소비 catalog path, declared
ref/commit, 관측 content SHA-256을 lock과 함께 기록해야 한다. path override 검증과
immutable declared-ref 검증은 분리해서 수행하며, 어느 하나라도 lock과 다르면
fail-closed로 `blocked`이다. downstream repository HEAD는 서로 달라도 되지만, 모든
entry의 **central catalog content SHA-256**은 canonical lock과 동일해야 한다.

candidate map과 lock은 trusted central candidate worktree에서 생성하고, source read 전에
origin remote가 승인된 `bluetape4k/bluetape4k-dependencies` repository인지, exact central
commit SHA가 remote에서 읽힌 값과 일치하는지, catalog raw bytes SHA-256이 lock과
일치하는지를 검증한다. mutable branch/tag, path substitution, remote mismatch, map/lock
변조, checkout 뒤 digest 변경은 모두 fail-closed다. Git commit signature verification은
현재 repository policy가 요구하지 않으므로 새 release gate로 추가하지 않지만, CI가 이미
제공하는 provenance 검사가 있으면 그 결과도 ledger에 보존한다.

### 1-2. `bt4k` accessor와 migration barrier

모든 지원 downstream repository는 settings에서 imported catalog 이름을 정확히 `bt4k`로
노출한다. 일반 Gradle project에서는 library alias를 `bt4k.foo.bar`, plugin alias를
`bt4k.plugins.foo.bar`로 사용한다. local alias는 central alias와 같은 coordinate/plugin
ID를 다른 이름으로 재선언할 수 없고, 이름 충돌은 central direct alias 우선, 다음으로
명시적인 versionless local alias, 마지막으로 issue-backed compatibility alias 순서로
해결한다. settings `pluginManagement`는 이 accessor contract의 지원 context가 아니다.

central alias는 lowercase ASCII alphanumeric segment와 single hyphen만 사용하고,
segment는 letter로 시작하며 Gradle accessor normalization 뒤 동일해지는 hyphen/dot/
underscore/case variant와 Kotlin reserved-word segment를 금지한다. catalog parser는
raw alias와 generated accessor path를 모두 계산해 library/plugin namespace 안의 collision을
fail-closed로 보고한다. 각 alias의 첫 accessor segment는 Gradle synthetic top-level namespace
`plugins`, `versions`, `bundles`를 쓸 수 없으며, parser는 library/plugin/bundle/version의
cross-namespace accessor tree도 함께 충돌 검사한다. fixture는 hyphen, dot, underscore, case
variant, reserved word, synthetic namespace, library-plugin same-name, local-central coordinate
collision을 각각 검증한다.

conversion은 개별 default branch에 적용하지 않는다. 모든 9개 repository candidate
worktree는 `prepare` 단계에서 manifest에 base SHA, candidate branch, expected candidate HEAD,
catalog digest, inventory/disposition hash를 기록하고 dry-run을 통과해야 한다. migration
diff는 G1–G7 동안 candidate worktree에만 uncommitted staged state로 존재한다. 모든 entry가
applicable G1–G7 PASS이고 manifest/hash가 같은 `verify` barrier를 통과한 뒤에만 coordinator가
고정 순서로 candidate commit을 만든다. commit 전/중 실패는 `mixed-state`이며 어떤 default
branch도 변경하지 않고, 이미 만들어진 candidate commit/실패 worktree를 증거로 보존한다.
G8은 aggregate receipt의 모든 actual HEAD와 diff hash를 read-back한 뒤에만 통과한다. baseline
복귀가 필요하면 last-known-good SHA에서 별도 worktree를 만들거나 새 repair commit으로만
수정한다. aggregate receipt는 모든 entry의 prepare/verify/apply 상태와 actual HEAD를 기록한다.

central parser fixture와 representative downstream Gradle smoke matrix는 library accessor,
plugin accessor, alias collision rejection, settings-time structural exception을 검증한다.
`./gradlew help`는 generated accessor/설정 평가 smoke이고, impacted module compile은
accessor가 실제 dependency declaration에서 작동함을 증명한다.

### 2. 버전 충돌 처리

33개 충돌 coordinate는 원본 build의 resolved dependency report와 migration 후보 report를
비교한 뒤 세 갈래로 분류한다.

1. 패치/마이너 drift이고 소비자 compile/test/POM이 같은 version을 허용하면 하나의
   중앙 version으로 정렬한다. 변경은
   `config/central-catalog-version-deltas.json`에 기록한다.
2. 상위 BOM이 실제 Maven dependency-management를 제공하면 downstream alias를
   versionless로 전환하고 POM gate로 증명한다.
3. major line, ABI, javax/jakarta, Spring Boot 세대, test fixture 제약이 다르면
   `foo3`/`foo4`처럼 명시적인 중앙 compatibility key/alias를 사용한다. 기존
   `spring-boot3`/`spring-boot4`, `jackson2`/`jackson3`, `kafka3`/`kafka4` 정책을
   따른다.

근거 없이 높은 버전으로 맞추지 않는다. unresolved conflict는 compatibility exception
또는 issue follow-up으로 남기며 해당 항목을 강제 통일하지 않는다.

### 2-1. 실패와 rollback 상태

변환 시작 전에 repository별 base SHA와 last-known-good candidate SHA를 ledger에
기록한다. configuration failure, catalog path/ref/SHA 불일치, 문서화되지 않은 resolved
version delta, POM audit/effective-model failure, representative compile/build failure는
즉시 해당 repository를 `failed`로 표시하고 후속 repository 전환을 중단한다.

실패한 candidate branch/worktree는 증거 보존을 위해 삭제하거나 reset하지 않는다.
수정은 새 repair commit으로만 수행하며, baseline 복귀가 필요하면 기록된
last-known-good SHA에서 별도 worktree를 만든다. repair 또는 복귀 뒤에는 topology/SHA
preflight, affected dependency graph, POM, compile/build을 다시 실행한다. rollback만을
통과시키는 exception은 추가하지 않는다.

### 3. downstream 전환과 hard-coded 항목

공통 library/plugin은 `bt4k` alias로 전환한다. repository-specific alias가 필요한
경우에만 local catalog에 coordinate를 남기되 version은 중앙 authority 또는 증명된 BOM에
위임한다. Gradle script의 하드코딩은 중앙 alias/accessor로 바꾼다.

settings `pluginManagement` 이전에 평가되는 Foojay resolver처럼 중앙 catalog accessor를
쓸 수 없는 항목은 structural exception으로 문서화하고, 중앙에서 별도 버전을 관리할 수
있는지 설정 evaluation 순서와 Gradle smoke test로 검증한다.

| disposition | 허용되는 downstream 형태 | 금지되는 형태 |
| --- | --- | --- |
| `central-direct` | `implementation(bt4k.foo.bar)`, `alias(bt4k.plugins.foo)` | local explicit version/동일 coordinate 중복 |
| `central-version-local-alias` | root dependency management가 `bt4k.versions.foo.get()`로 version을 주입하고 local alias 자체는 versionless | local TOML version key/inline version |
| `bom-managed-versionless` | `implementation(libs.local.foo)`와 POM dependency-management 근거 | 관리 근거 없는 versionless regular dependency |
| `compatibility-line` | `bt4k.foo3`/`bt4k.foo4`처럼 명시된 family alias | 범용 alias로 major/ABI line collapse |
| `structural-repo-owned` | settings-time constant와 issue-backed exception | 일반 module에서 이 exception 재사용 |

예를 들어 library는 `implementation(bt4k.commons.io)`로, plugin은
`alias(bt4k.plugins.test.logger)`로 전환한다. local alias 이름을 유지해야 하면
`foo = { module = "group:artifact" }`처럼 version을 제거하고 published POM 관리 근거를
검증한다. `pluginManagement` 단계는 `bt4k` accessor가 존재하지 않을 수 있으므로 별도
settings-time exception으로만 다룬다.

### 4. 중앙 BOM과 publication metadata

central catalog alias 추가만으로 BOM constraint를 무분별하게 추가하지 않는다. external
dependency가 published POM의 regular dependency 또는 dependency-management에 영향을 주면
central `build.gradle.kts`의 `constraints` block과 generated POM을 함께 검토한다.
versionless regular dependency는 동일 POM의 dependency-management 또는 versioned imported
BOM이 관리한다는 검증이 없으면 허용하지 않는다.

이번 구현은 `scripts/verify-publication-poms.py`의 candidate mode에서 Maven `-U`를 제거하고
offline/cache-manifest 검증을 강제한다. remote metadata refresh는 trusted baseline cache를
준비하는 별도 pre-sandbox operation이며 candidate evidence에 포함하지 않는다. G6는
publisher별 XML structural audit를 먼저 실행하고, 독립 POM generation은 최대 2개 runner
job으로 제한하며, 전체 effective-model pass는 한 번만 실행한다. 여덟 publisher 기준으로
job별 timeout은 25분(4 wave=100분)이고, G6 전체 2시간 중 나머지 20분은 structural audit와
effective-model pass에 예약한다. 예약 시간을 침범하면 scheduler는 새 job을 시작하지 않고
마지막 80줄 diagnostic과 함께 실패한다. G7은 60분, G8은 90분, G1–G5 preflight/guard에는
최대 30분을 예약한다. 따라서 G1–G8 전체 train hard timeout은 5시간 30분이며, scheduler는
각 stage를 시작하기 전에 남은 전체 budget이 그 stage의 예약 worst-case보다 작은지 확인한다.
작으면 실행하지 않고 impossible-budget receipt/diagnostic과 함께 실패한다. 각 timeout은
stage별 receipt/diagnostic을 남긴다.

### 4-1. 지원 matrix와 증거 artifact

| repository role | repositories | required behavior |
| --- | --- | --- |
| library publisher | projects, aws, exposed, graph, image, javers, leader, text | inventory, path/ref lock, help, representative graph/compile/build, generated POM/effective model |
| shared-catalog-only consumer | experimental | inventory, path/ref lock, help, representative graph/compile/build; publication POM은 N/A |
| excluded examples/workshops | workshop 및 별도 example repositories | 이 issue의 inventory/guard 대상이 아니며 candidate map에 포함되면 실패 |

candidate map은 정확히 위 9개만 포함한다. 지원 명령은 default discovery가 아닌 명시된
candidate map/repository list를 입력으로 받으며, unknown/missing/out-of-scope repository는
N/A가 아니라 실패다. machine artifact는
`build/catalog-authority/<catalog-sha256>/inventory.json`과 `summary.json`에, durable
candidate ledger는 `docs/releases/2026-08-03-issue-168-candidate-ledger.md`에 기록한다.
ledger는 모든 inventory ID를 disposition/evidence artifact와 최종 상태에 연결한다.

이번 구현은 `docs/version-management.ko.md`에 candidate map/lock 예시,
disposition/exception lifecycle, command order, ownership, mixed-state/rollback receipt,
candidate-ready handoff를 추가한다. 기존 broad workspace, PR/merge, `publishToMavenLocal`
안내는 release runbook으로 명시 분리하며 candidate train의 실행 근거로 사용할 수 없다.
PR, tag, publish, merge 권한은 새 runbook으로도 부여되지 않는다.

candidate ledger는 `schema-version`, immutable candidate ID, prior receipt hash, current
receipt SHA-256, atomic-write timestamp를 포함한다. writer는 temporary file을 fsync한 뒤
atomic move로 append/rewrite하고, reader는 schema/receipt chain을 read-back 검증한다. 누락,
invalid schema, receipt mismatch, interrupted write는 G8 closeout 실패다.

### 4-2. credential-free validation boundary

candidate validation은 Maven publication을 수행하지 않는다. preflight는
`CENTRAL_USERNAME`, `CENTRAL_PASSWORD`, signing key/password, Sonatype/Nexus token 및
동등한 publish credential이 존재하면 실패하거나 명시적으로 unset한 child environment만
허용한다. 각 repository command는 candidate SHA로 이름 붙인 임시
`GRADLE_USER_HOME`, `--no-daemon`, `--no-configuration-cache`, `--no-build-cache`를 사용한다.

허용 task는 `help`, `dependencies`, `dependencyInsight`, compile/test/build,
`generatePomFileFor*`뿐이며, `publish*`, `sign*`, Central Portal/Sonatype/Nexus upload,
workflow dispatch는 command preflight에서 거부한다. repository URL, module coordinate,
plugin ID, version은 TOML parser의 strict grammar와 approved repository/source rule을
따르고 dynamic/range version 및 resolver repository 변경은 candidate input validation에서
거부한다.

이번 구현은 새 `scripts/run-catalog-validation.py`와 해당 unit/fixture tests를 추가한다.
G1–G8의 Gradle/Maven child process는 이 runner가 만든
disposable sandbox에서만 실행한다. runner는 `env -i` 기반 최소 environment(PATH,
JAVA_HOME, locale, temporary HOME/GRADLE_USER_HOME/MAVEN repository만 허용)를 만들고
`GRADLE_OPTS`, init script, proxy, cloud, VCS/SSH, token, signing, publish 관련 변수와
사용자 home credential을 제거한다. runner는 trusted `develop` baseline에서 사전 준비한
candidate-identical artifact cache만 read-only로 mount하고 `--offline`을 강제한다. 이
issue는 새로운 dependency version을 도입하지 않으므로 cache miss는 network fallback이
아닌 실패다.

macOS에서는 sandbox profile이 workspace/JDK/read-only artifact cache/temporary home과
Gradle이 필요한 JVM child process만 접근하게 하고 network outbound 및 임의 subprocess를
거부한다. 동등한 OS sandbox가 없는 runner에서는 sandbox proof가 없으므로 G1–G8 Gradle
실행을 BLOCKED로 처리하며 unsandboxed fallback을 하지 않는다. runner는
`build/catalog-authority/<catalog-sha256>/preflight.json`에 sanitized environment keys,
sandbox mode, offline/cache digest, 허용/거부 task, exit code를 기록한다. malformed
environment, forbidden task, cache miss, network/process attempt는 fail-closed다.

runner와 fixture는 malicious plugin/build logic, `GRADLE_OPTS`/init-script injection,
proxy/token/SSH input, forbidden publish/sign task, stale cache, catalog post-read mutation을
각각 거부하는 regression을 가진다. preflight receipt의 path/SHA-256은 candidate ledger의
G1/G2 entry에 기록되고 read-back 검증된다. exact central commit의 trusted-worktree review와 CI
provenance artifact는 signature policy를 대신하는 필수 ledger evidence다.

runner manifest만이 Gradle/Maven command를 실행할 수 있고 raw shell invocation은 candidate
train에서 금지한다. manifest는 canonical cwd, catalog lock digest, `--offline`,
`--no-daemon`, `--no-configuration-cache`, `--no-build-cache`, exact task ID를 주입하고 누락
또는 override를 거부한다. runner는 resolved Gradle task graph의 `dependsOn`/`finalizedBy`를
검사해 `publish`, `sign`, upload 계열 task가 하나라도 있으면 실패한다. POM generation task는
`verify-publication-poms.py`의 고정 publisher registry에서만 파생하며 wildcard를 쓰지 않는다.

offline cache는 coordinate, artifact filename, content SHA-256, source repository를 가진
cache manifest로 표현하고 G2 catalog lock에 cache-manifest SHA-256을 bind한다. source
repository는 source-controlled allowlist에 있어야 하며 checksum mismatch/cache miss는
`BLOCKED`다. sandbox mount 전에 manifest와 실제 cache bytes를 검증한다. Maven source가
서명·attestation을 제공하는 경우에는 이를 receipt에 기록하되, 제공하지 않는 artifact에
추가 서명을 요구해 candidate를 막지는 않는다.

## 실패 모드와 완화

| 실패 모드 | 감지 신호 | 완화 및 rollback |
| --- | --- | --- |
| 중앙화가 의도치 않은 upgrade를 일으킴 | before/after resolved graph delta | delta ledger에 기록되지 않은 변경이면 해당 repository 변환을 되돌린다. |
| versionless alias가 Maven POM version을 잃음 | POM audit/effective-model 실패 | versioned central alias 또는 유효한 imported BOM으로 복원한다. |
| settings plugin이 `bt4k` accessor 평가 전 실패 | `./gradlew help` plugin resolution 실패 | structural exception을 유지하고 설정 순서 변경을 별도 설계로 분리한다. |
| compatibility line이 collapse됨 | compile/test/ABI 또는 dependencyInsight 불일치 | 명시적 중앙 compatibility alias를 추가하고 direct migration을 되돌린다. |
| downstream이 서로 다른 catalog SHA를 사용함 | candidate repository-map/checksum 불일치 | cross-repository verification을 `partial`로 유지하고 태그/PR을 금지한다. |

## 검증 전략

각 repository는 같은 후보 central catalog SHA를 사용한다. 검증 gate는 다음 순서로
의존하며, 앞선 gate가 실패하면 이후 gate를 실행하거나 후보를 `candidate-ready`로
표시하지 않는다.

1. **G1 topology preflight**: candidate map의 path/branch/base/HEAD/cleanliness와 관리
   repository 완전성을 검증한다.
2. **G2 catalog lock**: central bytes SHA-256, declared ref/peeled commit, downstream의
   실제 소비 path/SHA를 lock/ledger와 대조한다. path override와 declared-ref를 각각
   검증한다.
3. **G3 inventory/disposition baseline**: 864개 선언과 43개 hard-coded 후보의
   disposition 및 before resolved graph를 기록한다.
4. **G4 migration delta**: 전환 후 동일 report를 비교하고, 허용된 delta만 ledger에
   기록한다.
5. **G5 catalog governance**: managed block, shared authority, checksum, Dependabot
   ignore 검사를 실행한다.
6. **G6 publication contract**: 모든 publisher의 generated POM과 Maven effective model을
   검증한다.
7. **G7 downstream behavior**: 각 repository의 `help`, representative compile/build,
   필요한 `dependencyInsight`를 실행한다.
8. **G8 cross-repository closeout**: 모든 entry가 같은 lock과 applicable G1–G7 PASS를
   갖는지 확인한다. 하나라도 빠지면 `partial` 또는 `blocked-until-tag`이다.

G1은 `build/catalog-authority/<catalog-sha256>/candidate-manifest.json`을 canonical
candidate map/lock/disposition/cache manifest SHA와 exact nine-repository scope에서 생성하고,
그 SHA-256을 ledger G1 receipt에 고정한다. 각 stage는 no-follow open으로 manifest owner,
mode, canonical path와 bytes SHA-256을 재검증한다. manifest mutation은 `BLOCKED`다.

runner CLI는 `--manifest <absolute-path> --stage G1|G2|...|G8`만 받으며, manifest 밖의
cwd/task/catalog path/environment override는 거부한다. G7 stage는 아래 matrix의 exact
`help`, compile, graph task와 affected authority-id의 exact coordinate에 대한
`dependencyInsight --dependency <group:artifact> --configuration compileClasspath`를 실행한다.
G8 stage는 각 repository root의 `build` task와 aggregate receipt read-back을 실행한다.
task가 존재하지 않으면 runner는 가능한 대체 task를 추측하지 않고 실패한다.

저장소별 command matrix는 다음과 같이 고정한다. 각 command는 해당 candidate worktree를
cwd로 하고 `BLUETAPE4K_DEPENDENCIES_CATALOG_PATH`가 G2 lock의 central catalog를 가리킨다.
before/after graph output은 configuration header를 제거하고 `group:artifact:version`을
정렬한 UTF-8 text로 저장해 diff한다.

| repository | configuration/compile gate | graph gate |
| --- | --- | --- |
| projects | `:bluetape4k-core:compileKotlin` | `:bluetape4k-core:dependencies --configuration compileClasspath` |
| aws | `:bluetape4k-aws-java:compileKotlin` | `:bluetape4k-aws-java:dependencies --configuration compileClasspath` |
| experimental | `:shared:compileKotlin` | `:shared:dependencies --configuration compileClasspath` |
| exposed | `:bluetape4k-exposed-core:compileKotlin` | `:bluetape4k-exposed-core:dependencies --configuration compileClasspath` |
| graph | `:bluetape4k-graph-core:compileKotlin` | `:bluetape4k-graph-core:dependencies --configuration compileClasspath` |
| image | `:bluetape4k-images:compileKotlin` | `:bluetape4k-images:dependencies --configuration compileClasspath` |
| javers | `:javers-core:compileKotlin` | `:javers-core:dependencies --configuration compileClasspath` |
| leader | `:bluetape4k-leader-core:compileKotlin` | `:bluetape4k-leader-core:dependencies --configuration compileClasspath` |
| text | `:tokenizer-core:compileKotlin` | `:tokenizer-core:dependencies --configuration compileClasspath` |

각 disposition은 report-only 결과가 아니라 manifest record, normalized graph diff, POM
evidence(해당 시), command exit status를 함께 가져야 한다. artifacts는
`build/catalog-authority/<catalog-sha256>/<repository>/before.txt`, `after.txt`,
`help.json`, `compile.json`, `graph.json`, `insight-<authority-id>.txt`, `build.json`,
`commands.json`으로 보존하고 ledger에서 링크한다.

`CANDIDATE_WORKSPACE`, `CANDIDATE_MAP`, `CENTRAL_WORKTREE`는 G1/G2가 생성한 canonical
absolute path이고, `CANDIDATE_REPOS`는 지원 matrix의 정확한 9개 repository 목록이다.
default repository discovery는 이 train에서 금지되며 preflight가 누락된 map/repo argument를
거부한다. 다음 raw command 형식은 runner manifest가 생성·검증하는 canonical recipe이며,
운영자는 직접 실행하지 않고 runner stage로 호출한다.

```bash
scripts/sync-managed-catalog.py --workspace-root "$CANDIDATE_WORKSPACE" --check --summary
scripts/sync-shared-versions.py --workspace "$CANDIDATE_WORKSPACE" --repository-map "$CANDIDATE_MAP" --check --summary
scripts/sync-dependabot-ignores.py --workspace "$CANDIDATE_WORKSPACE" --repo bluetape4k-projects --repo bluetape4k-aws --repo bluetape4k-experimental --repo bluetape4k-exposed --repo bluetape4k-graph --repo bluetape4k-image --repo bluetape4k-javers --repo bluetape4k-leader --repo bluetape4k-text --check --summary
scripts/verify-publication-poms.py --workspace "$CANDIDATE_WORKSPACE" --repository-map "$CANDIDATE_MAP" --summary
```

```bash
scripts/run-catalog-validation.py --manifest "$CANDIDATE_MANIFEST" --stage G5
scripts/run-catalog-validation.py --manifest "$CANDIDATE_MANIFEST" --stage G6
scripts/run-catalog-validation.py --manifest "$CANDIDATE_MANIFEST" --stage G7
scripts/run-catalog-validation.py --manifest "$CANDIDATE_MANIFEST" --stage G8
```

위 raw recipe의 Gradle/Maven-bearing action은 runner manifest 내부에서만 실행되며, 운영자가
직접 shell에서 실행할 수 없다. central `build`는 G8 manifest task로 정확히 한 번 실행하고,
모든 downstream root build 뒤 동일 sandbox/lock/receipt에 기록한다. G1–G5는 Gradle/POM보다
먼저 실행해 invalid candidate로 비싼 작업을 시작하지 않는다.
G7은 changed/affected repository의 targeted gate를 먼저 실행하고, G8 직전 all-repository
gate로 확장한다. Gradle은 credential-free isolated home 때문에 cache를 공유하지 않으며,
independent non-Testcontainers repository commands만 최대 2개로 병렬 실행한다. publication
POM structural audit는 repository별로 먼저 실행하고 Maven effective-model 전체 검증은
candidate SHA마다 한 번만 수행한다. 각 command의 elapsed time, POM count, cache mode를
summary에 기록해 다음 train의 time budget 근거로 사용한다.

각 acceptance criterion은 report/guard, resolved graph, Gradle build, generated POM 중 적어도
하나의 fresh evidence에 매핑한다. rollout ledger에는 repository, candidate branch,
base/expected/actual HEAD, last-known-good SHA, catalog path, declared ref/commit, catalog
SHA-256, G1–G8 결과, delta ledger link, repair/rollback 상태를 기록한다. P0/P1 review
finding 또는 문서화되지 않은 resolved version delta는 rollout을 중단하고 위 rollback
상태를 따른다.

## 완료 조건

1. 864개 명시 외부 선언의 disposition이 모두 결정돼 있다.
2. 동일 버전 다중 repository coordinate와 plugin의 중앙 authority가 중복 없이 적용돼 있다.
3. 충돌 항목은 evidence-backed alignment 또는 compatibility-line으로 분류돼 있다.
4. hard-coded dependency/plugin version은 전환되거나 구조적 예외로 기록돼 있다.
5. central/downstream guard, checksum, Dependabot, POM, Gradle 검증이 같은 candidate SHA에서 통과한다.
6. `candidate-ready`는 pre-release handoff 상태이며 exact candidate SHA/ref와 ledger를
   포함한다. PR, tag, publish, merge에는 별도의 명시 authority와 fresh exact-head gate가
   필요하다. immutable ref가 아직 없어 declared-ref 검증을 끝낼 수 없으면
   `blocked-until-tag`로 보고한다.
