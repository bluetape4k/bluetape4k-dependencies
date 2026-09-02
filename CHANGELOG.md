# 변경 기록

`bluetape4k-dependencies`의 모든 주요 변경 사항을 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)를 따릅니다.
이 프로젝트는 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 따릅니다.

## [Unreleased]

### 변경

- `2.0.0` 정식 배포 이후 `2.1.0` minor 개발선을 열고 Projects와 Exposed를
  `2.1.0-SNAPSHOT`, 나머지 내부 라이브러리를 `1.1.0-SNAPSHOT`으로 정렬했습니다
  ([#235](https://github.com/bluetape4k/bluetape4k-dependencies/issues/235)).
- 정식 공개된 마지막 3개 internal BOM인 AWS/Javers/Leader를 `1.0.0`
  안정 버전으로 일괄 승격했습니다. 각 signed tag의 exact commit, release
  workflow와 Maven Central 공개 상태를 확인했습니다
  ([#232](https://github.com/bluetape4k/bluetape4k-dependencies/issues/232)).
- 정식 공개된 `bluetape4k-projects` BOM을 `2.0.0-SNAPSHOT`에서 `2.0.0`으로
  승격했습니다. Signed tag의 대상 SHA, exact-head Full Nightly 47/47,
  publication workflow와 Maven Central의 BOM/module metadata 및 대표 library
  POM 공개 상태를 확인했습니다
  ([#226](https://github.com/bluetape4k/bluetape4k-dependencies/issues/226)).
- 정식 공개된 `bluetape4k-graph` BOM을 `1.0.0-SNAPSHOT`에서 `1.0.0`으로
  승격했습니다. Signed tag의 대상 SHA, exact-head Full Nightly, publication
  workflow와 Maven Central의 publication 16개 및 공개 파일 122개를 확인했습니다
  ([#228](https://github.com/bluetape4k/bluetape4k-dependencies/issues/228)).
- 첫 공개 배치인 `bluetape4k-exposed` 2.0.0, `bluetape4k-image` 1.0.0,
  `bluetape4k-text` 1.0.0을 한 catalog commit에서 stable로 승격했습니다.
  Image 1.0.0에 포함된 `bluetape4k-images-captcha`의 과거 generator 제외도
  제거해 catalog alias와 문서에 반영했습니다
  ([#230](https://github.com/bluetape4k/bluetape4k-dependencies/issues/230)).

## [1.4.0] - 2026-08-06

### 추가

- 중앙에서 관리하는 Kotlinx Serialization 1.11.0 BOM과 JSON catalog alias를
  추가하고, 일치하는 BOM을 dependency platform에 import했습니다.
- 채택한 모든 최신 호환 외부 dependency authority에 대해 변경 전후
  resolved graph를 빠짐없이 검증하고, 후보 catalog checksum에 바인딩된
  immutable receipt를 추가했습니다.

### 변경

- 관리 대상 bluetape4k library repository가 사용하는 공통 external library와
  Gradle plugin 버전을 중앙화하면서, 의도적으로 분리된 consumer의 명시적
  compatibility line은 유지했습니다.
- 9개 관리 repository가 명시적 external library/plugin authority를 모두
  제거한 뒤 마지막 50개의 downstream compatibility-line selector를
  제거했습니다. 이제 settings 시점의 9개 Foojay plugin declaration만
  구조적 항목으로 남습니다.
- 121개 catalog version key를 감사한 최신 호환 stable release로 갱신하고,
  격리된 Gradle resolution configuration에서 영향받은 130개
  library/plugin authority를 모두 검증했습니다.

## [1.3.1] - 2026-06-28

### 버그 수정

- 생성된 POM의 license metadata를 repository license 및 bluetape4k 생태계
  정책과 일치하는 MIT License로 수정했습니다.
- Gradle version catalog를 Maven Central publication으로 설명하던 release
  guidance를 수정했습니다. catalog는 생태계 repository를 위한 git-ref
  build contract로 유지되며, Maven Central artifact는
  `bluetape4k-dependencies` BOM입니다.

## [1.3.0] - 2026-06-27

### 변경

- `1.3.0` minor train이 조정된 internal BOM release set을 사용하도록
  준비했습니다: projects `1.11.0`, exposed `1.11.0`, AWS `0.4.0`, image
  `0.3.0`, text `0.2.1`, graph `0.5.1`, leader `0.4.0`, javers `0.2.1`.
- downstream snapshot dependency resolution 전략을 문서화하고 재사용 가능한
  retry wrapper를 추가했으며, 일시적인 Central snapshot `403` 응답에 대한
  snapshot artifact availability check를 강화했습니다.
- 생성된 managed catalog alias와 BOM constraint를
  `bluetape4k-images-ocr`에 맞춰 동기화하고, 최초 published line이 나올
  때까지 unpublished Exposed database module을 gate 안에 유지했습니다.
- 생성된 bluetape4k artifact version 관리를 개별 BOM constraint로 모든
  artifact를 반복하는 대신 imported sub-BOM에 위임했습니다.
- projects 측 Dependabot remediation을 위한 shared dependency catalog를
  cut했습니다. `bluetape4k-dependencies 1.3.0`을 전체 release train으로
  간주하지 않고, internal repository release 후 최종 BOM/catalog artifact로
  유지합니다 ([#101](https://github.com/bluetape4k/bluetape4k-dependencies/issues/101)).

## [1.2.0] - 2026-06-01

### 추가

- 단일 호환 line으로 안전하게 관리할 수 있는 Netty 4.1/4.2, Protobuf,
  Fabric8, Vert.x catalog line과 BOM constraint를 중앙 관리 대상으로
  추가했습니다.

### 변경

- 1.2.0 minor train을 위해 managed `bluetape4k-projects` BOM을 published
  `1.10.0` release로 승격했습니다.
- managed `bluetape4k-aws` BOM을 published `0.3.1` release로 승격했습니다.
- 생성된 catalog 및 `bluetape4k-images-ktor` BOM coverage를 포함해 managed
  `bluetape4k-image` BOM을 published `0.2.0` release로 승격했습니다.
- managed `bluetape4k-text` BOM을 published `0.2.0` release로 승격했습니다.
- managed `bluetape4k-graph` BOM을 published `0.5.0` release로 승격했습니다.
- managed `bluetape4k-leader` BOM을 published `0.3.1` release로 승격했습니다.
- 1.2.0 minor train을 위해 managed `bluetape4k-exposed` BOM을 published
  `1.10.0` release로 승격했습니다.
- 생성된 catalog와 BOM coverage에 `javers-ddd`, `javers-exposed`를 포함해
  managed `bluetape4k-javers` BOM을 published `0.2.0` release로 승격했습니다.

## [1.1.4] - 2026-06-01

### 변경

- 1.1.4 patch train에서 `bluetape4k-aws`, `bluetape4k-image`,
  `bluetape4k-text`, `bluetape4k-graph`, `bluetape4k-javers`를 published
  `bluetape4k-dependencies:1.1.3` baseline에 유지했습니다.
- 다음 repository BOM line이 필요하므로 1.1.4에서 `bluetape4k-ktor-*`,
  `javers-ddd`, `javers-exposed` alias와 constraint를 제외했습니다.
- stable image release에서 publish될 때까지 unreleased
  `bluetape4k-images-ktor` catalog alias와 BOM constraint를 1.1.4 stable
  matrix에서 제외했습니다.
- managed `bluetape4k-projects` BOM을 `1.9.2-SNAPSHOT`에서 published
  `1.9.2` release로 승격하고, `1.10.0`은 다음 minor dependencies train으로
  남겼습니다.
- managed `bluetape4k-exposed` BOM을 `1.9.2-SNAPSHOT`에서 published
  `1.9.2` release로 승격했습니다.
- managed `bluetape4k-leader` BOM을 `0.2.2-SNAPSHOT`에서 published
  `0.2.2` release로 승격했습니다.
- `javers-ddd`, `javers-exposed`의 생성된 Javers alias와 BOM constraint를
  동기화했습니다.

## [1.1.2] - 2026-05-23

### 변경

- managed `bluetape4k-projects` BOM을 `1.9.0`에서 published `1.9.1`
  release로 승격했습니다.

## [1.1.1] - 2026-05-23

### 버그 수정

- managed catalog와 BOM constraint에서 publish되지 않는
  `bluetape4k-mock-web-server`, `bluetape4k-mock-webflux-server` application
  module을 제거했습니다.
- release 준비를 위한 Maven Central artifact availability audit를
  추가했습니다.

## [1.1.0] - 2026-05-23

### 추가

- `bluetape4k-leader-dynamodb` 생성 catalog alias와 BOM constraint를
  추가했습니다.

### 변경

- managed `bluetape4k-leader` BOM을 `0.1.0`에서 published `0.2.0` release로
  승격했습니다.

## [1.0.1] - 2026-05-22

### 추가

- repository maintenance를 위한 Dependabot configuration을 추가했습니다
  ([PR #1](https://github.com/bluetape4k/bluetape4k-dependencies/pull/1)).
- Maven Central Portal publication과 GitHub Release 생성을 위한 release
  workflow를 추가했습니다.
- `develop` push에 따른 SNAPSHOT publication workflow를 추가했습니다
  ([PR #3](https://github.com/bluetape4k/bluetape4k-dependencies/pull/3)).
- central BOM에 `bluetape4k-exposed` module을 추가했습니다
  ([PR #2](https://github.com/bluetape4k/bluetape4k-dependencies/pull/2)).
- AWS, image, text, exposed, javers BOM platform import를 추가했습니다
  ([PR #6](https://github.com/bluetape4k/bluetape4k-dependencies/pull/6)).
- `leader-zookeeper` BOM entry를 추가했습니다
  ([PR #7](https://github.com/bluetape4k/bluetape4k-dependencies/pull/7)).
- `bluetape4k-graph-ktor` 생성 catalog alias와 BOM constraint를
  추가했습니다.

### 변경

- 다음 snapshot train을 `1.0.1-SNAPSHOT`으로 열고 managed
  `bluetape4k-exposed` BOM을 `1.8.1-SNAPSHOT`에 맞췄습니다.
- 공식 첫 Spring Boot integration surface를 공개 BOM release 전에 Spring
  Boot 4 전용 versionless `spring-boot` artifact name으로 표준화했습니다
  ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- 과도기 `leader-spring-boot3` / `leader-spring-boot4` alias를 단일
  `leader-spring-boot` alias로 교체했습니다
  ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- 과도기 Exposed `bluetape4k-spring-boot3-*`,
  `bluetape4k-spring-boot4-*` alias를 versionless
  `bluetape4k-spring-boot-*` alias로 교체했습니다
  ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- core `bluetape4k-projects` Spring Boot integration module에 versionless
  module alias를 추가했습니다
  ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- 생성된 `bluetape4k-graph-spring-boot4-starter` alias를 versionless
  `bluetape4k-graph-spring-boot` alias로 교체했습니다.
- README license reference가 MIT License를 가리키도록 변경했습니다.
- ecosystem BOM set을 현재 published release train으로 승격했습니다:
  `bluetape4k-bom:1.9.0`, `bluetape4k-aws-bom:0.2.0`,
  `bluetape4k-exposed-bom:1.9.0`, `bluetape4k-graph-bom:0.4.0`,
  `bluetape4k-image-bom:0.1.1`, `bluetape4k-javers-bom:0.1.1`,
  `bluetape4k-text-bom:0.1.1`.

### 버그 수정

- dependency constraint가 올바르게 조합되도록 `bluetape4k-bom`, graph BOM,
  leader BOM reference를 platform import로 변환했습니다
  ([PR #4](https://github.com/bluetape4k/bluetape4k-dependencies/pull/4),
  [PR #5](https://github.com/bluetape4k/bluetape4k-dependencies/pull/5)).

### 비고

- Spring Boot 3 artifact는 이전 1.7.x line에서 계속 사용할 수 있지만,
  첫 공식 `bluetape4k-dependencies` public contract에는 의도적으로
  포함하지 않았습니다.
