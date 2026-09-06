# Issues #242/#243 의존성·서명 거버넌스 설계

## 문제

`bluetape4k-dependencies`는 공용 version catalog와 BOM을 관리하지만, 두 계약이
현재 서로 다른 방식으로 불완전하게 전파된다.

- Timefold Solver는 중앙 catalog에서 `2.4.0`으로 보류되어 있다. 공식 안정판
  `2.6.0`에는 점수 복원과 join 처리 수정이 포함되어 있으므로 버전 문자열만
  올려서는 소비자의 점수 정합성을 증명할 수 없다.
- `PublishingSigningSupport`는 9개 저장소에 복제되어 있다.
  `bluetape4k-projects`에 추가된 Base64 key 처리와 long key ID 정규화가 다른
  저장소에 전파되지 않아 같은 secret도 저장소별로 다르게 해석된다.

이 작업은 #242의 의존성 전환과 #243의 build-time signing 계약 단일화를 같은
작업 branch에서 수행하되, 두 변경을 독립 promotion unit으로 검증한다. 한 unit의
실패가 다른 unit의 검증된 변경을 자동으로 되돌리지는 않는다. 태그, Maven Central
배포, PR 생성과 병합은 범위 밖이다.

## 현재 근거

- 기준 branch는 `origin/develop`, 기준 SHA는
  `9698c9d66bea6fcba373143ee8fa5bfbd9812d4b`다.
- `gradle/libs.versions.toml`의 `timefold-solver`는 `2.4.0`이다.
- `build.gradle.kts`는 `api(platform(libs.timefold.solver.bom))`으로 Timefold BOM을
  가져온다.
- `config/latest-stable-audit-policy.json`은 Timefold를
  `defer-breaking-migration`으로 분류한다.
- `bluetape4k-projects`의 `PublishingSigningSupport.kt`는 ASCII armor, escaped
  newline, Base64 key와 16자리 key ID를 처리한다. 나머지 저장소는 이 계약을
  모두 구현하지 않는다.
- 중앙 기준선 `./gradlew build`는 성공했다.
- latest-stable audit는 `2.6.0`과 Maven metadata SHA-256
  `305e3bf461f489ede46351f7e0a3f56a6466fa4ffda9b20f70922ef25fff920b`를
  이미 기록한다.
- `clinic-appointment`는 직접 모듈을 `2.6.0`으로 사용하지만 일부 lockfile의
  Timefold BOM은 `2.4.0`이다. runtime graph에서 이 혼재를 해소했는지 확인해야
  한다.

## 목표

1. Timefold Solver `2.6.0`을 중앙 catalog와 BOM 경로에 적용하고, 핵심
   소비자의 resolved graph와 점수·영속화 계약을 검증한다.
2. signing key 해석과 key ID 정규화를 한 canonical source에서 관리한다.
3. 저장소별 publication 이름, POM 메타데이터, GPG fallback과 경고 정책은
   각 저장소 adapter가 계속 소유한다.
4. generated source drift를 중앙 CI에서 fail-closed로 검출한다.
5. secret 원문을 오류, 경고, 테스트 출력에 노출하지 않는다.

## 범위

### 중앙 저장소

- Timefold version, checksum, latest-stable 정책과 의도적 resolved-version delta
- Gradle 독립 canonical signing key helper
- 동기화·검사 스크립트, 단위 테스트와 CI drift 검사
- 설계, 실행 계획, review와 lesson 증거

### signing 소비 저장소

- `bluetape4k-projects`, `bluetape4k-aws`, `bluetape4k-exposed`,
  `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`,
  `bluetape4k-leader`, `bluetape4k-text`
- 동일한 generated pure helper와 기존 adapter의 최소 연결 변경
- `buildSrc` compile/test 및 publication/signing configuration smoke test

중앙 저장소 1개와 sibling 8개를 합쳐 signing 대상은 총 9개다.

### Timefold 검증 소비자

- `bluetape4k-exposed`: Timefold persistence round-trip과 Spring/Jackson 결합
- `timefold-workshop`: `2.6.0` 후보에서 증분 점수와 `SolverManager` lifecycle
- `clinic-appointment`: 현재 `2.6.0` 경로의 예약 제약, 점수 복원과 DB 반영

`timefold-workshop #54`가 요구하는 신규 shadow-variable 예제와 전체 교육 과정
개편은 이 작업에 포함하지 않는다. 검증 실패는 #242의 compatibility hold를
유지하는 근거이며, 별도 소비자 기능을 임의로 흡수하는 근거가 아니다.

## 검토한 방식

### 1. published convention plugin으로 즉시 통합

소스 복제를 제거할 수 있지만, signing helper를 사용하려면 plugin을 먼저
배포해야 한다. release bootstrap과 plugin resolution이 9개 저장소의 배포를
동시에 막을 수 있어 이번 단계에서는 제외한다.

### 2. `PublishingSigningSupport.kt` 전체를 하나의 template으로 복사

구조는 단순하지만 저장소별 POM 메타데이터, 함수 이름, `enabled` 처리와
경고 정책까지 중앙 template에 결합된다. 작은 차이를 template 조건문으로
관리하면 signing 계약보다 sync 도구가 더 복잡해지므로 제외한다.

### 3. pure helper만 canonical source로 관리

Gradle API에 의존하지 않는 다음 계약만 동일한 generated Kotlin 파일로
배포한다.

- `NormalizedSigningKeyId`
- `normalizeSigningKeyId`
- `resolveSigningKeyId`
- `resolveSigningKey`

canonical helper는 기존 Projects buildSrc API를 그대로 보존한다.
`NormalizedSigningKeyId`와 네 함수는 public top-level 선언이며,
`resolveSigningKeyId(raw: String): String`, `resolveSigningKey(raw: String): String`의
nullability와 반환 타입을 바꾸지 않는다. adapter 내부 진단은
`normalizeSigningKeyId(raw: String): NormalizedSigningKeyId`의 bounded warning을
사용한다.

각 저장소의 `PublishingSigningSupport.kt`는 기존 공개 buildSrc 함수와
publication 동작을 유지하면서 이 helper를 호출한다. 이번 설계는 이 방식을
사용한다. 구현 범위가 작고 compile-time에 전체 연결을 검증할 수 있으며,
추후 convention plugin으로 옮겨도 adapter API를 유지할 수 있다.

canonical source는
`config/publishing-signing/PublishingSigningKeySupport.kt`에 두고
`package io.bluetape4k.gradle`을 사용한다. default package인 기존 adapter는
generated helper를 import하고, 이미 같은 package를 사용하는 `projects`와
`graph`는 import 없이 호출한다. generated file header에는 기준 데이터 원본
경로, 동기화 명령과 직접 편집 금지를 기록한다. canonical source만 직접
편집할 수 있다.

`bluetape4k-projects/PublishingSigningSupport.kt`에 이미 있는 네 선언은 adapter
파일에서 제거한다. generated helper가 유일한 선언 소유자가 되며, sync contract
test는 adapter에 같은 symbol이 다시 선언되면 실패한다.

## signing 계약

### Key ID

- 앞뒤 공백을 제거한다.
- 빈 값은 빈 값으로 유지한다.
- 정확히 16자리인 hex 값만 trailing 8자리로 줄인다.
- `0x` 또는 `0X` prefix는 유지하고, 정확히 16자리인 hex 본문만 trailing
  8자리로 줄인다.
- 변환 경고에는 입력 secret을 포함하지 않는다. key ID는 secret key material과
  구분되지만, 진단에는 원문 전체 대신 정규화 동작과 결과만 남긴다.
- 16자리가 아닌 값은 기존 호환성을 위해 그대로 유지한다.
- 길이가 16이어도 hex가 아닌 값은 기존 호환성을 위해 그대로 유지한다.

현 `bluetape4k-projects` 구현은 문자 집합을 검사하지 않고 길이만으로 축약한다.
hex-only 축약은 이 작업에서 의도한 hardening이다. 정상 OpenPGP key ID에는 영향을
주지 않으며, non-hex 16자리 입력은 변형하지 않은 채 Gradle/GPG 검증으로 넘긴다.
회귀 테스트로 이 차이를 고정한다.

대표 mapping은 다음과 같다.

| 입력 | 결과 |
|---|---|
| `ABCDEF12` | `ABCDEF12` |
| `1234567890ABCDEF` | `90ABCDEF` |
| `0x1234567890ABCDEF` | `0x90ABCDEF` |
| `0X1234567890ABCDEF` | `0X90ABCDEF` |
| `1234567890ABCDEG` | 변경하지 않음 |

정규화 warning은 ASCII 160 bytes 이하이며 raw key ID, newline, control character,
ANSI escape를 포함하지 않는다. 메시지는 축약 여부와 결과 길이만 설명한다.

### Signing key

- 빈 값은 빈 값으로 유지한다.
- ASCII armor와 `\\n`이 포함된 값은 escaped newline을 실제 newline으로 바꾼다.
- 나머지 값은 strict Base64 decode를 시도한다.
- Base64 decode 결과가 UTF-8 ASCII-armored private key일 때만 decoded 값을
  사용한다. binary bytes, invalid UTF-8 또는 armor가 아닌 decoded text는 raw
  값으로 되돌린다.
- Base64가 아니면 기존 raw 값으로 되돌려 호환성을 유지한다. 이 함수는 PGP
  유효성 검증기가 아니라 CI secret의 transport encoding을 정규화하는 함수다.
  실제 key 유효성은 Gradle signing parser가 판단한다.
- parser와 sync 도구는 key 내용을 로그하거나 예외 메시지에 포함하지 않는다.

### Adapter

- `SIGNING_KEY`와 password가 있으면 in-memory PGP signing을 사용한다.
- GPG command fallback, publication 선택과 missing-key 정책은 기존 저장소
  adapter가 유지한다.
- 정규화 경고는 값 자체를 출력하지 않는 bounded 메시지로 기록한다.
- buildSrc adapter는 local 비게시 빌드의 기존 skip 계약을 유지한다. publication
  권한과 unsigned artifact 거부는 release workflow와 Maven Central validation이
  소유한다. 이번 unit은 누락 secret 정책을 새로 정의하지 않고, synthetic key로
  signature artifact가 생성되는 positive smoke와 malformed key가 signing task에서
  실패하는 negative smoke를 증명한다.

기존 adapter 조합은 다음과 같이 보존한다.

| Adapter | 입력 | 결과 |
|---|---|---|
| 전체 | key + password | in-memory PGP signing 구성 |
| 전체 | `SIGNING_USE_GPG_CMD=true` | 기존 GPG fallback 구성 |
| 기본형 | no-key, key-only, password-only | 기존과 같이 signing 생략 |
| `projects`/`graph` | password-only | 기존 bounded missing-key warning |
| `projects`/`graph` | `enabled=false` | signing 구성 안 함 |
| 전체 | malformed key + password | Gradle signing task에서 redacted 실패 |

`GPG_KEY_NAME`이 비어 있으면 모든 adapter가 normalized key ID를 fallback으로
사용한다. custom warning과 publication 이름은 저장소별 기존 값을 유지한다.

adapter migration 표는 다음과 같다.

| 저장소 | Package | 보존 API | 연결 변경 |
|---|---|---|---|
| dependencies/aws/exposed/image/javers/leader/text | default | `SigningConfig`, `resolveSigningConfig`, `configurePublishingSigning(String)` | generated helper 네 symbol을 import하고 key/key ID만 helper로 해석 |
| graph | `io.bluetape4k.gradle` | `PublishingSigningConfig`, `resolvePublishingSigningConfig`, `configurePublishingSigning(String, Boolean, String)` | 같은 package generated helper를 직접 호출 |
| projects | `io.bluetape4k.gradle` | graph와 같은 API 및 `PublishingSigningConfig.keyIdWarning` | 기존 네 helper 선언을 제거하고 generated helper를 유일한 소유자로 사용 |

세 variant 모두 compile regression을 실행하고, `projects`/`graph`는 외부
`resolvePublishingSigningConfig().useGpgCmd` 호출자도 compile로 검증한다.

## 동기화 계약

`scripts/sync-publishing-signing-support.py`는 중앙 canonical file을 아래
경로로 복사하거나 비교한다.

```text
buildSrc/src/main/kotlin/PublishingSigningKeySupport.kt
```

고정된 managed repository 목록만 허용하고 `--workspace`, `--repository-map`,
`--repo`, `--write`, `--check`, `--summary`를 제공한다. `--repository-map`은 각
대상의 canonical absolute worktree path, approved origin과 exact HEAD를 고정하며,
write/check 직전에 다시 검증한다. 경로 이탈, symlink target, 저장소 누락,
canonical source 누락과 content drift는 실패한다. `--write --check`는 쓰기 후
동일성까지 검증한다. 중앙 CI는 Python 단위 테스트와 중앙 generated copy를
모든 PR에서 검사하고, sibling workspace drift는 저장소가 준비되는 전체
workspace gate에서 검사한다.

sync는 쓰기 전에 모든 대상 경로, symlink, 현재 bytes, mode와 canonical digest를
검사한다. 전체 preflight가 성공한 뒤 같은 디렉터리의 0600 임시 파일을 fsync하고
원래 mode를 적용한 다음 atomic replace한다. 대상 parent를 다시 열어 no-follow
검증하고 directory fsync로 교체를 확정한다. 한 대상에서 실패하면 이미 교체한
대상은 사전에 보관한 bytes와 mode로 복구한다.
검증 receipt는 대상 저장소 exact HEAD, clean/dirty 기준선, 이전/이후 digest와
결과를 기록한다. worktree를 발견했지만 후보 commit이 없는 상태는 `discovered`다.
multi-repo Git commit 자체는 원자적이지 않으므로 각 저장소를 `prepared`로
커밋한 다음 전체 exact-ref map을 `validated`로 고정하고, 중앙 drift gate가 모두
일치할 때만 `adopted`로 판정한다. 일부 저장소만 준비된 상태는 `blocked`이며
promotion 증거로 사용할 수 없다. 모든 전이는 이전 state, expected HEAD와 digest를
compare-and-set 방식으로 검사하고 receipt 자체도 temporary-file, fsync, atomic
replace로 갱신한다.

PR delivery를 수행할 때는 중앙 canonical revision과 8개 sibling exact ref를
candidate repository map으로 묶고 `sibling prepared -> 중앙 validated -> 중앙
adopted` 순서를 따른다. 이번 로컬 작업은 PR을 만들지 않으므로 동일한 map을
local worktree SHA와 digest receipt로 검증한다.

local candidate repository map은 기존 `scripts/catalog_candidate.py`의 중앙 + 9개
catalog repository enum과 canonical path, approved origin, clean worktree, symlink,
exact-ref 검증을 그대로 재사용한다. signing sync는 그 map에서 중앙 + 8개 signing
repository만 고정 allowlist로 선택하고 catalog-only Experimental은 수정하지 않는다.
Timefold Workshop과 Clinic은 catalog enum을 완화하지 않고 전용 receipt의 consumer
section에서 같은 검증 primitive를 적용한다. 이 작업 전용 receipt는
`docs/releases/2026-09-06-issues-242-243-local-receipt.json`에 저장하고 다음
versioned schema를 사용한다.

source-controlled `config/publishing-signing-repository-refs.json`은 canonical source
SHA-256과 8개 sibling candidate commit SHA를 고정한다. 자신의 Git commit을 문서
안에 기록하는 self-reference는 만들지 않는다. 로컬 repository map은 이
manifest에 absolute worktree path와 catalog-only Experimental entry를 결합한다.
CI는 branch/default HEAD를 임의로 clone하지 않고 manifest의 commit을 fetch/check out한
뒤 origin, peeled commit, clean 상태를 재검증한다. manifest commit이 remote에 없으면
부분 rollout으로 fail-closed한다.

```json
{
  "schema-version": 1,
  "candidate": {
    "catalog-path": "gradle/libs.versions.toml",
    "catalog-sha256": "...",
    "bom-coordinate": "io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local"
  },
  "repositories": [
    {
      "name": "bluetape4k-exposed",
      "origin": "git@github.com:bluetape4k/bluetape4k-exposed.git",
      "base-head": "...",
      "candidate-head": "...",
      "reviewed-implementation-head": "...",
      "clean-before": true,
      "signing-sha256": "...",
      "catalog-ref": "...",
      "catalog-sha256": "...",
      "catalog-source": "local-candidate|immutable-ref|repo-local",
      "bom-coordinate": "...",
      "local-override": "present|removed|not-applicable",
      "state": "discovered|prepared|validated|adopted|blocked"
    }
  ],
  "consumers": [
    {
      "name": "bluetape4k-exposed|timefold-workshop|clinic-appointment",
      "origin": "git@github.com:bluetape4k/repository-name.git",
      "base-head": "...",
      "candidate-head": "...",
      "catalog-ref": "...",
      "catalog-sha256": "...",
      "catalog-source": "local-candidate|immutable-ref|repo-local",
      "bom-coordinate": "...",
      "local-override": "present|removed|not-applicable",
      "graphs": [
        {
          "coordinate": "ai.timefold.solver:timefold-solver-core",
          "configuration": "testRuntimeClasspath",
          "before-version": "2.4.0",
          "after-version": "2.6.0",
          "selection-reason": "selected by candidate BOM",
          "output-sha256": "..."
        }
      ],
      "state": "discovered|prepared|validated|adopted|blocked"
    }
  ],
  "commands": [
    {
      "repository": "...",
      "command": "redacted command without environment values",
      "jdk": "...",
      "gradle": "...",
      "configuration": "...",
      "elapsed-seconds": 0,
      "cache": "isolated|shared-read",
      "result": "pass|fail|blocked",
      "output-sha256": "..."
    }
  ]
}
```

`scripts/verify-issues-242-243-receipt.py`가 schema, exact repository set, digest,
상태 전이와 필수 Timefold 좌표를 검증한다. receipt에는 secret과 environment
값을 기록하지 않는다. `blocked`가 하나라도 있거나 `validated`보다 낮은 target이
있으면 adoption은 실패한다.

tracked receipt를 담는 evidence commit은 자신의 SHA를 receipt 안에 기록하지 않는다.
coordinator는 adopted receipt를 포함하는 prospective commit object를 branch ref
갱신 없이 만들고, final validator는 별도 `--evidence-commit` 입력을 받아 그 commit의 parent가
central `reviewed-implementation-head`와 같고 diff가 receipt 경로 하나뿐인지
검증한다. 검증 성공 후에만 expected reviewed HEAD를 old value로 둔 compare-and-swap
ref update로 prospective commit을 채택한다. strict repository map은 reviewed
implementation envelope를 계속 가리켜 evidence commit과 implementation exact-head의
의미를 혼합하지 않는다.

release workflow의 inline signing diagnostic은 key의 길이 또는 입력 형식만
검사하는 별도 운영 진단이다. 실제 Gradle signing parser의 기준 데이터 원본으로
사용하지 않는다. 이번 변경에서는 해당 diagnostic이 raw armor, escaped newline,
Base64-encoded armor, Base64 non-armor와 invalid Base64를 canonical transport
normalizer와 같은 분류로 처리하도록 갱신한다. diagnostic은 key 원문이나 decoded
본문을 출력하지 않으며 sentinel 기반 workflow policy test로 이를 검증한다.

## Timefold 전환 계약

- 중앙 version ref만 `2.6.0`으로 변경하고 Timefold BOM import는 유지한다.
- portable checksum sidecar를 갱신한다.
- `defer-breaking-migration`은 소비자 검증이 모두 통과한 뒤에만 제거한다.
- core, benchmark, Jackson, Spring Boot starter의 before/after resolved version과
  selection reason을 기록한다.
- 의도적인 transitive 변화만 `central-catalog-version-deltas.json`에 기록한다.
- catalog source ref와 Maven Central BOM version을 같은 증거로 취급하지 않는다.
- 소비자 검증이 실패하면 version bump와 정책 변경을 함께 되돌리고, 실패한
  계약과 재검토 조건을 기록한다.

검증 순서는 다음과 같다.

1. 각 소비자의 `2.4.0` 또는 현재 override 기준선 graph를 저장한다.
2. 중앙 candidate catalog와 BOM을 만든 뒤 exact local path/version으로 주입한다.
3. lockfile과 직접 override가 candidate 선택을 가리지 않는지 검사한다.
4. 동일 configuration에서 candidate graph와 selection reason을 저장한다.
5. 소비자 테스트가 통과한 뒤에만 policy와 delta ledger를 승격한다.

`bluetape4k-exposed`는 `BLUETAPE4K_DEPENDENCIES_CATALOG_PATH`로 이 worktree의
catalog와 checksum을 주입한다. `timefold-workshop`은 별도 검증 worktree에서
local `2.2.0` override만 `2.6.0`으로 바꾸고, 해당 변경을 #242의 영구 산출물로
커밋하지 않는다. `clinic-appointment`는 중앙 candidate BOM을 고유 local version으로
`publishToMavenLocal`한 뒤 별도 검증 worktree에서 그 BOM을 사용하고, local
Timefold override를 제거한 graph와 기존 override graph를 비교한다.

local candidate BOM은 `2.1.0-issue-242.local`로 고정하고 전용 임시
`GRADLE_USER_HOME`과 Maven repository를 사용한다. 소비자는 candidate repository를
첫 번째로 조회하고 `--refresh-dependencies`를 사용한다. resolved POM/JAR의
coordinate와 SHA-256이 candidate output과 같아야 한다. 검증 후 임시 repository는
receipt digest를 남긴 다음 제거한다. 이 local candidate 판정과 실제 published
stable BOM 경로 판정은 별도 필드로 기록한다.

Timefold graph ledger는 네 좌표를 반드시 포함한다.

| Version key | Coordinate | 최소 configuration | Pass 기준 |
|---|---|---|---|
| `timefold-solver` | `ai.timefold.solver:timefold-solver-core` | `testRuntimeClasspath` | candidate `2.6.0` 선택 |
| `timefold-solver` | `ai.timefold.solver:timefold-solver-benchmark` | 실제 benchmark consumer runtime | candidate `2.6.0` 선택 |
| `timefold-solver` | `ai.timefold.solver:timefold-solver-jackson` | 실제 Jackson consumer runtime | candidate `2.6.0` 선택 |
| `timefold-solver` | `ai.timefold.solver:timefold-solver-spring-boot-starter` | 실제 starter consumer runtime | candidate `2.6.0` 선택 |

범용 검증 runner는 기존 `scripts/verify-latest-stable-resolved-graphs.py`의 observation
parser와 ledger serializer를 재사용하되, 전체 latest-stable delta를 다시 resolve하지
않고 Timefold 네 좌표와 실제 consumer configuration만 실행한다. 각 consumer receipt가
catalog ref/source/checksum, BOM coordinate, configuration, before/after, selection
reason과 local override 상태를 참조하게 한다. clinic은
runtime graph에 `2.4.0` BOM이 남거나 direct override 없이 candidate `2.6.0`을
선택하지 못하면 실패한다.

## 실패 모드와 대응

1. **generated source drift**: `--check`가 저장소와 경로를 표시하고 non-zero로
   종료한다. key 내용은 출력하지 않는다.
2. **잘못된 Base64 입력**: raw 값 fallback으로 기존 signing 동작을 유지한다.
   실제 PGP 유효성은 Gradle signing이 판단한다.
3. **long key ID 오해석**: trailing 8자리로 정규화하고 bounded 경고를 남긴다.
4. **Timefold transitive graph 변화**: before/after graph와 delta ledger가
   불일치하면 중앙 전환을 중단한다.
5. **소비자 점수 또는 persistence 회귀**: compatibility hold를 유지하고
   중앙 candidate를 채택하지 않는다.
6. **cross-repo 기준선 불일치**: 저장소별 exact HEAD와 결과를 분리해서
   기록하며, 다른 SHA의 성공 결과를 현재 candidate 증거로 재사용하지 않는다.
7. **sync 중 부분 쓰기**: staged file을 폐기하고, 이미 교체한 대상은 preflight
   bytes로 복구한 뒤 receipt를 `blocked`로 기록한다.

## 테스트 전략

### #243

- canonical helper의 빈 값, armor, escaped newline, Base64와 invalid Base64
- short, long, prefixed long key ID와 bounded warning
- warning/error output에 sentinel secret이 없는지 검사
- sync script의 clean, drift, missing repo, symlink, `--repo`, write/check
- 중앙 generated copy와 8개 sibling generated copy의 byte equality
- 9개 저장소 `buildSrc` compile/test와 signing task configuration smoke
- synthetic signing key의 signature artifact 생성과 malformed key의 redacted 실패

### #242

- catalog checksum, latest-stable policy와 delta ledger 단위 테스트
- catalog/shared-version/Dependabot ignore sync
- 중앙 `./gradlew build`
- 모든 등록 publisher의 effective POM 검사
- Timefold core/benchmark/Jackson/starter dependency graph
- Exposed persistence round-trip, workshop incremental score와 `SolverManager`,
  clinic constraint/score/DB 테스트

Testcontainers 또는 실제 DB 검사는 저장소별로 순차 실행한다. 각 명령에는
repository HEAD, JDK/Gradle version, configuration, catalog/BOM candidate,
`--refresh-dependencies` 사용 여부와 출력 SHA-256을 receipt에 기록한다. Docker
미가동이나 외부 repository 장애는 `BLOCKED`, 같은 입력에서 재현되는
assertion/compile 실패는 `FAIL`로 분류한다. infrastructure retry는 원인 확인 뒤
한 번만 허용하며 최초 실패 로그를 보존한다.

검증 DAG는 read-only metadata/파일 검사를 최대 3 workers로 실행하고, Gradle
compile/test/POM은 저장소당 하나씩 최대 2 workers로 실행한다. Testcontainers,
실제 DB와 Maven local candidate 소비는 항상 순차 실행한다. 저장소별 Gradle
timeout은 10분, POM 전체 gate는 30분, 전체 local validation budget은 90분으로
제한한다. 첫 deterministic 실패에서는 dependent task를 취소하고 receipt를
`blocked`로 닫는다. 같은 `(repository HEAD, catalog/BOM digest, configuration,
coordinate, phase)` graph 요청은 한 번만 resolve하며 후속 검사는 기존 output
digest를 재사용한다. POM 생성물도 같은 exact candidate에서 재생성하지 않는다.
cache는 exact HEAD와 catalog/BOM digest로 구분하고, receipt에 worker 수, elapsed,
cache policy, 재실행 여부를 기록한다. Gradle build/configuration cache는 끄되,
runner는 HEAD, helper/catalog/BOM digest, task/configuration과 toolchain으로 만든
evidence key의 성공 receipt와 output digest를 read-back한 경우 subprocess를 생략한다.
`--refresh-dependencies`는 새 candidate의 최초 graph resolve에만 사용한다. 중앙 CI의 기존 managed-repository clone
step에서 signing drift를 함께 검사해 별도 checkout을 만들지 않는다.

## 호환성과 운영 경계

- runtime public API와 ABI 변화는 없다. #243은 `buildSrc` 내부 계약이다.
- 기존 `configurePublishingSigning` 호출 시그니처는 유지한다.
- `2.6.0` resolved graph가 Spring Boot/Jackson 호환선을 바꾸면 그 변화는 delta
  ledger와 소비자 검증을 모두 통과해야 한다.
- secret, tag, release, workflow dispatch, Maven Central publication은 수행하지 않는다.
- PR을 만들지 않으므로 remote branch와 CI exact-head 결과는 이번 작업의 DoD에
  포함하지 않고 명시적 N/A로 남긴다.

## 완료 조건

- [ ] #243 canonical helper의 contract test가 통과한다.
- [ ] 9개 저장소 generated helper가 byte-identical하고 drift 검사가 fail-closed다.
- [ ] 9개 저장소의 기존 publication adapter API와 고유 동작이 유지된다.
- [ ] Base64, armor, escaped newline과 short/long/prefixed key ID가 정의된 mapping에 맞는 결과를 낸다.
- [ ] secret sentinel이 진단과 테스트 출력에 나타나지 않는다.
- [ ] Timefold `2.6.0` catalog, checksum, policy와 delta ledger가 일치한다.
- [ ] core/benchmark/Jackson/starter before/after graph가 기록된다.
- [ ] Exposed, workshop, clinic의 지정 계약 검증이 통과한다.
- [ ] 세 소비자의 catalog source/ref/checksum, BOM coordinate, override와
      published/local candidate 판정이 receipt에서 검증된다.
- [ ] catalog sync, shared-version sync, Dependabot ignore sync, POM gate와 중앙 build가 통과한다.
- [ ] 7-Tier 최종 review에서 P0=0, P1=0이다.
- [ ] spec, plan, review, lesson과 로컬 Lore commit이 남는다.
- [ ] local exact-ref map과 command/result digest receipt가 남는다.

## DoD와 중단 조건

모든 로컬 구현·검증·독립 review가 통과하면 PR delivery 행을 N/A로 기록하고
작업을 종료한다. Timefold 소비자 검증이 실패하거나 signing adapter 호환성을
보존할 수 없으면 해당 변경을 채택하지 않고 `PENDING` 또는 `BLOCKED` 증거를
남긴다. 사용자 승인 없이 PR, push, merge, tag 또는 publication 단계로 진행하지
않는다.
