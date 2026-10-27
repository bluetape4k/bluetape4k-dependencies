# Detekt alpha.6과 Kotlin 2.4.x의 compiler 경계

## 배경

Issue [#256](https://github.com/bluetape4k/bluetape4k-dependencies/issues/256)은
중앙 catalog의 Kotlin `2.4.x` train과 `dev.detekt` `2.0.0-alpha.6`을 함께
적용할 때 Detekt configuration classpath가 다른 Kotlin compiler 버전을
사용하는 문제를 추적한다. 현재 중앙 catalog의 제품 Kotlin은 `2.4.21`이고,
기존 Leader canary는 Kotlin `2.4.20`에서 같은 `detekt-dev` 버전을 사용했다.

## 결정 또는 발견

- Detekt 호환성 표는 `2.0.0-alpha.6`이 Kotlin `2.4.10`으로 빌드됐다고
  기록한다. [공식 호환성 표](https://detekt.dev/docs/introduction/compatibility/)와
  [Gradle 설정 문서](https://detekt.dev/docs/2.0.0-alpha.2/gettingstarted/gradle/)를
  기준 정보로 사용한다.
- 제품 compile classpath를 Kotlin `2.4.10`으로 되돌리면 안정 버전과 보안
  업데이트를 취소하므로 중앙 Kotlin line을 낮추지 않는다.
- Detekt plugin이 제공하는
  `dev.detekt.gradle.plugin.getSupportedKotlinVersion()`으로 `detekt`
  configuration만 plugin 지원 compiler에 맞춘다. 제품 소스와 일반 Kotlin
  dependency에는 중앙 Kotlin line을 유지한다.
- 중앙 catalog에는 이 경계를 주석으로 명시하고 checksum sidecar를 갱신한다.
  `detekt-dev` 버전 자체를 임의로 올리거나 compatibility line을 복제하지
  않는다.

## 결과

`gradle/libs.versions.toml`은 Detekt plugin의 compiler 경계와 consumer 적용
규칙을 설명한다. `gradle/libs.versions.toml.sha256`은 새 catalog 바이트를
가리키도록 다시 계산했다. 이미 병합된 AWS #664, Text #345, Leader #965와
기존 Projects/Exposed/Graph/Javers consumer override가 이 규칙을 적용한다.

## 검증

- 변경 전 호환성 계약 guard는 `getSupportedKotlinVersion()` 선언이 없어 RED가
  됐다.
- 변경 후에는 catalog checksum, central sync, publication POM, Gradle build를
  순서대로 재검증한다.
- Leader의 full Nightly backend matrix와 새 원격 immutable catalog ref는
  중앙 commit이 원격에 게시된 뒤 별도 canary에서 확인해야 한다. 현재 일일
  Nightly의 skipped backend jobs를 완료 증거로 사용하지 않는다.

## 향후 지침

Detekt 또는 Kotlin compiler를 올릴 때 먼저 공식 호환성 표와 plugin의 지원
resolver를 확인한다. 제품 Kotlin 버전과 Detekt configuration Kotlin 버전을
하나의 중앙 version ref로 강제하지 말고, consumer build에서 `detekt`
configuration에만 지원 버전을 적용한다. 새 catalog ref를 downstream에 고정할
때는 exact commit, sidecar checksum, consumer canary, full Nightly matrix를
각각 다시 읽고 검증한다.
