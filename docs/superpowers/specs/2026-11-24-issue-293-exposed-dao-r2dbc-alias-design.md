# Issue #293: Exposed R2DBC DAO 중앙 catalog alias 설계

## 문서 상태

- 상태: 설계 방향 승인, 6개 관점 사양 리뷰 대기
- 대상: [bluetape4k-dependencies #293](https://github.com/bluetape4k/bluetape4k-dependencies/issues/293)
- 선행 소비자: [bluetape4k-exposed #942](https://github.com/bluetape4k/bluetape4k-exposed/issues/942)
- 기준 저장소: `bluetape4k-dependencies` `develop` `77822aaf77b57ba5b13b8de34146cbb44e2358e5`
- 승인된 PR 대상: 저장소 `bluetape4k/bluetape4k-dependencies`, base `develop`, head `chore/issue-293-exposed-dao-r2dbc-alias`
- 병합, catalog tag, BOM 버전 변경, Maven Central publication은 이 설계에 포함하지 않는다.

## 1. 문제와 결정

`bluetape4k-exposed#942`는 JetBrains Exposed 1.6.1의 실험적 R2DBC DAO를 별도 모듈에서 사용할 계획이다. 중앙 catalog에는 `org.jetbrains.exposed:exposed-dao-r2dbc` alias가 없어 소비 저장소가 기존 중앙 catalog 경로로 이 artifact를 선언할 수 없다.

**결정:** `gradle/libs.versions.toml`의 `[libraries]`에 다음 alias를 추가하고 기존 `exposed` 버전 참조를 재사용한다.

```toml
exposed-dao-r2dbc = { module = "org.jetbrains.exposed:exposed-dao-r2dbc", version.ref = "exposed" }
```

현재 `exposed` 키는 `1.6.1`이다. 새 버전 키를 만들거나 기존 Exposed 버전을 변경하지 않는다. catalog sidecar checksum을 갱신하고, 회귀 테스트와 Maven Central만 사용하는 임시 Gradle 소비자로 좌표와 해석 결과를 확인한다.

## 2. 현재 근거

- #293은 열려 있으며 alias 좌표와 기존 `exposed` version ref 재사용을 명시한다.
- 기준 catalog에서 `exposed = "1.6.1"`이고 `exposed-dao` 및 `exposed-r2dbc` 등 같은 버전을 참조하는 alias가 이미 있다.
- `scripts/sync-dependabot-ignores.py`의 `CENTRAL_DEPENDENCY_IGNORES`에 `org.jetbrains.exposed:*`가 이미 있어 ignore 목록의 추가나 downstream 재생성은 필요하지 않다.
- `scripts/sync-managed-catalog.py`는 Bluetape4k 산출물 alias 블록을 관리한다. JetBrains 외부 artifact alias는 생성 블록에 속하지 않으므로 이 스크립트의 출력 변경은 없다.
- Maven Central의 `org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1` POM 요청이 HTTP 200을 반환했다.
- 승인 전 기준 worktree에서 `./gradlew build --console=plain`이 통과했다. 변경 전 baseline은 `BUILD SUCCESSFUL`이다.
- 제안 alias를 임시 catalog에 넣은 Gradle 소비자 검증에서 `libs.exposed.dao.r2dbc` 접근자가 생성되고, `mavenCentral()`만 설정한 `compileClasspath`가 `1.6.1`을 선택했다. 이 검증은 설계 실험이며 아직 저장소 catalog를 수정하지 않았다.
- GNO의 GitHub 검색에서는 #293과 같은 기존 이슈를 찾지 못했다. docs 검색에서는 별도 BOM 승격 없이 alias-only catalog handoff를 좁게 유지한 선례를 확인했다.

## 3. 대안과 선택 이유

### A. 기존 `exposed` version ref를 쓰는 alias 추가 — 선택

이슈에 적힌 좌표를 그대로 노출하며 현재 Exposed 버전 계약을 유지한다. 기존 alias 패턴과 일치하고, version key나 BOM 제약을 늘리지 않는다. 회귀 테스트와 소비자 해석 검증으로 alias 이름, 모듈 좌표, 선택 버전을 각각 확인할 수 있다.

### B. DAO 전용 version key 추가 — 제외

`exposed-dao-r2dbc`에 별도 버전 키를 두면 BOM 및 다른 Exposed artifact와 버전이 어긋날 수 있다. 현재 이슈는 새 version key를 제외하고 있으며 별도 호환선도 요구하지 않는다.

### C. `bluetape4k-exposed`에만 로컬 alias 추가 — 제외

중앙 catalog를 소비하는 저장소 계약을 우회하고 저장소별 좌표 선언을 중복한다. #293의 목적과 맞지 않는다.

## 4. 변경 경계

### 포함

- `gradle/libs.versions.toml`의 `[libraries]`에 정확한 alias 한 개 추가
- catalog sidecar `gradle/libs.versions.toml.sha256` 갱신
- alias의 module과 `version.ref`를 검사하는 회귀 테스트 추가
- Maven Central만 등록한 임시 Gradle 소비자에서 해석 버전 확인
- 중앙 ignore 및 catalog 생성 경로의 회귀 검사
- #293용 한국어 설계·구현 계획·리뷰·lesson 기록과 승인된 PR

### 제외

- `exposed` 버전 값 또는 `bluetape4k-dependencies` BOM 버전 변경
- `build.gradle.kts`에 `api(libs.exposed.dao.r2dbc)`를 추가하는 일
- `bluetape4k-exposed`의 catalog ref 갱신. 이 소비자 변경은 #293 병합 후 #942 작업에서 immutable SHA와 checksum으로 수행한다.
- Dependabot ignore 목록 변경. 현재 `org.jetbrains.exposed:*` 규칙으로 이미 관리한다.
- generated Bluetape catalog block 수정, publication POM 변경, SNAPSHOT 버전 또는 BOM 게시, catalog tag 및 release
- #942가 구현할 DAO 모듈, coroutine API, repository 동작과 API 문서

## 5. 호환성 및 소비자 계약

alias 추가는 기존 alias와 version key를 변경하지 않는다. 소비자는 다음 accessor를 사용해 `org.jetbrains.exposed:exposed-dao-r2dbc:1.6.1`을 선언할 수 있어야 한다.

```kotlin
implementation(libs.exposed.dao.r2dbc)
```

소비자 검증은 임시 Gradle project의 dependency repository를 `mavenCentral()` 하나로 제한하고 `dependencyInsight`에서 정확한 좌표와 선택 버전을 읽는다. PR의 catalog checksum을 확인한 뒤, #293 병합 후 #942가 그 exact catalog commit SHA를 pin한다. 브랜치나 tag처럼 움직이는 ref로 소비자를 검증하지 않는다.

## 6. 실패 모드와 복구

| 실패 모드 | 영향 | 탐지와 복구 |
|---|---|---|
| Alias 철자 또는 Gradle accessor 충돌 | 소비 build에서 catalog accessor를 사용할 수 없음 | 회귀 테스트와 임시 소비자 compile/resolution으로 검출한다. alias 이름을 바꾸지 않고 TOML과 접근자 증거를 다시 맞춘다. |
| alias가 다른 Exposed 버전을 가리킴 | 1.6.1의 DAO artifact와 API 버전이 불일치 | 테스트가 `version.ref = "exposed"`와 `exposed = "1.6.1"`을 검사하고 `dependencyInsight`를 확인한다. |
| artifact가 Maven Central 경로에서 해석되지 않음 | 소비자의 중앙 저장소 경로가 재현되지 않음 | `mavenCentral()`만 설정한 소비자 검증을 실패로 처리하고 catalog 변경을 보류한다. |
| sidecar checksum이 catalog와 불일치 | 소비자가 immutable catalog를 검증하지 못함 | checksum 단위 테스트와 `shasum -a 256 -c`를 실행하고 sidecar를 다시 생성한다. |
| alias-only 변경이 의도치 않게 BOM/POM 출력을 바꿈 | downstream 게시 계약이 catalog 범위를 넘어서 변경됨 | diff와 BOM/POM 검증 경로를 확인한다. `build.gradle.kts` 변경이나 publisher POM 변화가 생기면 계획 리뷰로 돌아가 범위를 다시 승인받는다. |

실패 시 catalog alias와 sidecar만 원복하면 된다. 해당 변경은 Exposed version 값을 바꾸지 않으므로 데이터 migration이나 runtime rollback은 없다.

## 7. 수용 기준과 완료 정의

- alias가 정확히 `org.jetbrains.exposed:exposed-dao-r2dbc`를 가리키고 기존 `exposed` version ref를 사용한다.
- 회귀 테스트가 alias module과 version ref, 선택된 `1.6.1` 기준을 확인한다.
- checksum sidecar가 catalog 바이트와 일치한다.
- Maven Central 전용 소비자에서 `libs.exposed.dao.r2dbc`가 `1.6.1`을 해석한다.
- `scripts/sync-dependabot-ignores.py --workspace .. --check --summary`와 적용 가능한 catalog 검사가 통과한다.
- `./gradlew build`가 통과하고 최종 diff에 승인된 catalog·test·evidence 파일만 포함된다.
- PR은 승인된 `bluetape4k/bluetape4k-dependencies:develop` 대상으로 생성하고 #293 및 #942를 연결한다. exact-head CI와 live PR 상태를 확인한 뒤 merge-ready 보고에서 멈춘다.
- merge, tag, publication은 fresh explicit approval 전까지 실행하지 않는다.

## 8. 리뷰 관점과 출처

독립 리뷰는 성능, 안정성, 보안, 운영, 개발자/API, 사용자/소비자 관점을 각각 확인한다. Main-session 통합 리뷰는 중복·충돌, repository 규약, catalog/POM 범위, acceptance mapping을 확인하며 P0=0, P1=0일 때만 설계 리뷰를 통과시킨다.

| 출처 | 확인한 근거 |
|---|---|
| [dependencies #293](https://github.com/bluetape4k/bluetape4k-dependencies/issues/293) | alias 정확한 좌표, 기존 version ref, checksum 및 #942 연결 요구 |
| [Exposed #942](https://github.com/bluetape4k/bluetape4k-exposed/issues/942) | 별도 소비 모듈 범위와 중앙 catalog alias 선행 조건 |
| `gradle/libs.versions.toml` at `77822aaf77b57ba5b13b8de34146cbb44e2358e5` | 기존 `exposed = 1.6.1` 및 alias 배치 패턴 |
| `scripts/sync-dependabot-ignores.py` at the same base | `org.jetbrains.exposed:*` 중앙 ignore 규칙 |
| `tests/test_kotlinx_serialization_catalog.py` at the same base | TOML alias의 module 및 version ref 회귀 검사 패턴 |
| [Maven Central POM](https://repo.maven.apache.org/maven2/org/jetbrains/exposed/exposed-dao-r2dbc/1.6.1/exposed-dao-r2dbc-1.6.1.pom) | `1.6.1` artifact 좌표가 중앙 저장소에 존재함 |
| Baseline `./gradlew build --console=plain` | 변경 전 build 성공 |

## 9. Writer gate 기록

- SPW-01: PASS — Korean design artifact, #293 acceptance, #942 consumer dependency, baseline/catalog/POM sources, exact identifiers와 범위를 고정했다.
- SPW-02: PASS — 문제, 결정, 세 대안, 경계, 호환성, 다섯 실패 모드, 검증 기준, 복구 경로를 포함했다.
- SPW-03: PASS — 한국어 기술 문체와 terminology checklist를 적용하고 API·명령·좌표·URL을 보존했다.
- SPW-04: PASS — #293/#942와 catalog/test/ignore/POM 근거를 문서의 결정과 수용 기준에 연결했다.
- SPW-05: PASS — 전체 Markdown을 다시 읽고 문서 상태, 제목, 표, 코드 블록과 링크를 점검했다.
