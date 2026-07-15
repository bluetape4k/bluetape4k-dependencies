# bluetape4k 라이브러리 중앙 Catalog 채택 설계

## 배경

`bluetape4k-dependencies/gradle/libs.versions.toml`은 bluetape4k Kotlin 라이브러리 생태계의 dependency, plugin, compatibility line 버전 소스다. 그러나 각 라이브러리 저장소가 같은 버전을 로컬 `[versions]`에 다시 선언하고 `libs.*` alias를 계속 사용하고 있다. 값이 우연히 같더라도 중앙 버전 변경과 로컬 변경이 독립적으로 가능해져 drift와 호환성 충돌을 막지 못한다.

이번 변경은 버전을 올리는 작업이 아니다. 현재 중앙 catalog의 좌표와 버전 계약을 실제 소비 경로로 만들고, 동일한 중앙 버전을 로컬에서 다시 선언하는 패턴을 제거하는 거버넌스 변경이다.

## 범위

대상 라이브러리 저장소는 다음 9개다.

| 저장소 | 현재 중복 버전 키 | 주요 특이사항 |
|---|---:|---|
| `bluetape4k-projects` | 50 | 가장 넓은 로컬 catalog와 다수의 동일 좌표 alias |
| `bluetape4k-experimental` | 24 | 구형 Maven catalog artifact를 사용하며 7개 값 drift |
| `bluetape4k-aws` | 16 | 로컬 `jackson`은 Jackson 3, 중앙 `jackson`은 Jackson 2 의미 |
| `bluetape4k-exposed` | 47 | QueryDSL 5.1과 중앙 QueryDSL 7.4 compatibility 차이 |
| `bluetape4k-graph` | 12 | issue #342 / PR #366에서 일부 중앙 alias 채택 완료 |
| `bluetape4k-image` | 16 | `bt4k` catalog를 import하지만 아직 직접 사용하지 않음 |
| `bluetape4k-javers` | 17 | 일부 중앙 version accessor만 사용하고 plugin은 로컬 |
| `bluetape4k-leader` | 17 | 중앙 catalog를 import하지만 직접 alias 사용이 없음 |
| `bluetape4k-text` | 10 | 중앙 catalog를 import하지만 직접 alias 사용이 없음 |

워크숍, 예제 애플리케이션, Go/Rust/Python 저장소는 제외한다. dependency 버전 업그레이드, catalog train tag 생성, BOM 배포, PR 생성, push, merge도 제외한다.

## 목표 상태

### 1. 직접 중앙 alias 소비

중앙 catalog에 동일한 plugin id 또는 Maven coordinate alias가 있으면 Gradle build에서 `bt4k.plugins.*` 또는 `bt4k.*`를 직접 사용한다. 같은 대상을 가리키는 로컬 alias와 로컬 version key는 제거한다.

### 2. 중앙 version accessor를 사용하는 로컬 coordinate

중앙에 정확한 library alias가 없지만 버전 계열은 중앙 관리 대상이면 로컬 alias의 `version.ref`를 제거한다. root dependency-management/BOM constraint가 version을 공급할 수 있는 경우 versionless alias로 바꾸고, 그렇지 않으면 Gradle build에서 `bt4k.versions.*` provider로 version을 한 번만 주입한다.

### 3. 명시적 compatibility 예외

중앙 compatibility line과 의도적으로 다른 major 또는 artifact family를 사용하는 경우만 로컬 버전을 유지한다. 예외는 다음 정보를 포함해야 한다.

- repository와 local version key
- 중앙 alias와 동일 이름을 피하는 명확한 이름
- compatibility 이유
- 중앙 key와 허용 local value/range
- owner, introduced date, review-by/expiry
- 해소 조건과 같은 조직의 canonical tracking issue URL

`bluetape4k-aws`의 Jackson 3은 `jackson3`로 명명해 중앙 Jackson 2 `jackson`과의 의미 충돌을 없앤다. `bluetape4k-exposed`의 QueryDSL 5.x는 현재 소스 호환성 검증 없이는 중앙 7.x로 올리지 않으며, 이번 변경에서 명시적 예외로 남긴다.

### 4. 중복 재도입 차단

중앙 저장소의 검증 도구는 더 이상 동일 version 값을 downstream catalog에 복사해 주는 것으로 성공을 판단하지 않는다. 중앙 관리 version key를 downstream `[versions]`에서 다시 선언하면 실패해야 한다. 명시적 예외 파일에 등록된 compatibility pin만 허용하고, 존재하지 않는 저장소/alias, 만료되거나 이유 없는 예외도 실패시킨다. `--write`는 compatibility 예외를 포함한 downstream version declaration을 자동 변경하지 않는다.

버전 key만이 아니라 library `group:artifact`와 plugin id의 중복도 검사한다. 같은 group의 다른 artifact, 같은 alias의 다른 coordinate, 같은 version key의 다른 compatibility family는 동일성으로 간주하지 않는다.

### 5. 재현 가능한 catalog 입력

다운스트림 검증은 `BLUETAPE4K_DEPENDENCIES_CATALOG_PATH`로 이번 중앙 worktree의 catalog를 명시해 sibling checkout 우선순위나 오래된 train ref에 영향을 받지 않게 한다. `bluetape4k-experimental`은 Maven에 게시된 구형 version-catalog artifact 대신 다른 라이브러리 저장소와 같은 file-based catalog import 계약으로 전환한다.

일반 build는 implicit sibling catalog를 선택하지 않는다. local catalog는 명시 path로만 허용하고 regular non-symlink file인지 확인한다. remote catalog는 공식 GitHub 저장소의 immutable train tag/commit과 content SHA-256을 rollout ledger에 고정하고, ref 또는 digest가 다르면 fail closed한다. 후보 path 검증과 실제 declared ref 검증은 별도 gate다.

### 6. 단계적 rollout과 관찰 가능성

엄격한 cross-repo enforcement는 9개 downstream migration보다 먼저 활성화하지 않는다.

1. 중앙 guard를 report-only/single-repository mode로 구현한다.
2. compatibility family와 예외를 먼저 분류한다.
3. 중앙 candidate catalog SHA를 고정하고 저장소별로 migrate/verify한다.
4. 새 immutable catalog train ref를 만든 뒤 각 downstream의 declared ref 경로를 검증한다.
5. 모든 downstream default branch가 같은 catalog SHA를 소비할 때 중앙 cross-repo enforcement와 scheduled audit를 활성화한다.

rollout ledger에는 repository, base/head SHA, worktree/catalog path, declared ref/commit, candidate catalog SHA, guard/help/build/dependency-resolution 결과, last-known-good rollback SHA를 기록한다. 모든 필수 entry가 같은 candidate SHA에서 통과하지 않으면 상태는 `partial`이며 enforcement-ready로 간주하지 않는다.

## 선택한 접근

직접 `bt4k` alias 소비와 versionless local alias를 조합하고, 불가피한 compatibility pin만 allowlist로 남긴다.

이 방식은 Gradle version catalog가 alias namespace를 자동 병합하지 않는 제약을 그대로 드러내면서도 버전 권한은 중앙으로 단일화한다. 저장소별로 필요한 로컬 alias 이름은 유지할 수 있고, 중앙 좌표가 이미 존재하는 경우에는 중복 정의 자체를 삭제할 수 있다.

## 검토한 대안

### 기존 materialized sync 유지

중앙 값으로 로컬 값을 덮어쓰는 현재 방식은 drift를 고치지만 중복된 권한과 alias 정의를 남긴다. 어떤 catalog를 실제로 소비하는지 build script만 보고 알기 어렵고, 중앙 sync를 실행하지 않은 branch에서는 다시 drift할 수 있어 채택하지 않는다.

### 중앙과 로컬 catalog를 합성한 단일 generated catalog 생성

모든 build script가 `libs.*`만 사용하도록 만들 수 있지만, 생성 단계와 파일 소유권이 추가되고 checked-out ref와 local overlay의 충돌 규칙이 숨겨진다. 단순한 버전 권한 문제에 별도 generator를 도입하므로 채택하지 않는다.

### 로컬 catalog를 전부 삭제

각 저장소에는 중앙에서 관리할 필요가 없는 전용 coordinate와 alias가 있다. 이들까지 중앙으로 올리면 중앙 catalog가 사용처 하나뿐인 dependency 목록으로 비대해지고 repository boundary가 흐려지므로 채택하지 않는다.

## 실패 모드와 보호 장치

| 실패 모드 | 보호 장치 |
|---|---|
| 중앙 alias가 pinned train tag에 없음 | 후보 중앙 catalog path를 명시한 build 검증 후 train tag 갱신은 별도 release 절차로 수행 |
| sibling checkout이 declared ref보다 우선됨 | 검증 시 `BLUETAPE4K_DEPENDENCIES_CATALOG_PATH` 강제 |
| 같은 version key가 다른 artifact family를 의미함 | module group 비교와 명확한 compatibility alias 이름 사용 |
| versionless alias에 dependency management가 없음 | root BOM/constraint 또는 `bt4k.versions.*` 주입 여부를 build로 검증 |
| plugin alias accessor가 기존 local accessor와 충돌 | local plugin alias 제거와 build script 교체를 같은 변경으로 수행 |
| compatibility major가 의도치 않게 바뀜 | 기존 compatibility-line 검사와 예외 reason/issue 검증 유지 |
| 신규 로컬 중복이 다시 추가됨 | 중앙 guard의 repository-wide check를 CI/build 검증 계약에 포함 |
| 같은 group의 다른 artifact가 동일 alias로 오인됨 | exact `group:artifact`와 exact plugin id 비교, mismatch는 migration 거부 |
| 임의 path/traversal 또는 symlink catalog가 검사 대상이 됨 | managed repository enum, canonical child/path map, regular non-symlink 검증 |
| remote tag/cache가 바뀌거나 손상됨 | immutable commit/content digest 고정, bounded fetch/parse, atomic cache replacement, digest mismatch fail closed |

## 호환성과 롤백

Maven artifact coordinate와 runtime dependency version은 이번 변경에서 바꾸지 않는다. Gradle Kotlin DSL accessor가 `libs.*`에서 `bt4k.*`로 바뀌는 것은 각 저장소의 내부 build contract 변경이다.

저장소별 변경은 독립 branch/worktree에 유지한다. 실패한 downstream 변경은 last-known-good SHA로 되돌리고 cross-repo audit는 repair될 때까지 실패/partial 상태를 유지한다. rollback을 통과시키기 위한 예외는 추가하지 않는다. allowlist는 검증된 compatibility 차이에만 사용한다. configuration failure, resolved-version delta, missing/mismatched ref는 rollback trigger다.

candidate path 검증 뒤에는 같은 repository를 환경 변수 없이 fresh `GRADLE_USER_HOME`에서 declared immutable ref로 다시 검증한다. candidate-only alias가 declared ref에 없다면 downstream integration은 새 catalog train ref가 생길 때까지 `blocked`로 기록한다.

## 완료 조건

1. 9개 라이브러리 저장소가 명시 path 또는 immutable ref로 고정된 file-based `bt4k` catalog를 소비하며 implicit sibling substitution을 허용하지 않는다.
2. 중앙에 동일 plugin/coordinate가 있는 로컬 alias는 가능한 범위에서 제거되고 build는 `bt4k.*`를 직접 사용한다.
3. 중앙 관리 version key의 로컬 중복은 0이거나 문서화된 compatibility 예외다.
4. 의미가 다른 동일 이름 key는 명확한 compatibility 이름으로 교정된다.
5. 중앙 guard가 version key, exact coordinate/plugin id 중복, 잘못된/만료된 예외, compatibility major 위반을 실패로 보고한다.
6. 중앙 Python unit tests와 `./gradlew build`가 통과한다.
7. 9개 downstream 저장소가 후보 중앙 catalog path와 actual declared ref 양쪽에서 configuration 검증을 통과하고, 저장소별 exact compile/build/dependency-resolution 명령을 통과한다.
8. migration 전후 resolved `group:artifact:version`과 plugin id/version 비교에서 문서화되지 않은 delta가 없다.
9. rollout ledger가 10개 저장소의 candidate catalog SHA, HEAD, 검증, rollback evidence를 포함하고 enforcement readiness를 `ready` 또는 `partial`로 판정한다.
10. 현재 dependency version, published artifact, source API에는 의도하지 않은 변경이 없다.
