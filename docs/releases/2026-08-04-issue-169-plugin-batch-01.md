# Issue #169 최신 안정 버전 적용 - plugin batch 01

감사 기준일은 2026-08-04이다. 이 배치는 Gradle Plugin Portal의 공식 Maven
metadata를 기준으로, 기존 호환 line 안에서 검증 가능한 plugin만 먼저 갱신한다.

## 적용

| authority key | 기존 | 후보 | 판단 |
| --- | ---: | ---: | --- |
| `kotlin` | `2.4.0` | `2.4.10` | `hold-compatibility` |
| `kover` | `0.9.8` | `0.9.9` | `adopt-latest` |
| `download` | `5.6.0` | `5.7.0` | `adopt-latest` |
| `gatling-plugin` | `3.15.1` | `3.15.1.2` | `adopt-latest` |
| `jib` | `3.4.4` | `3.5.4` | `adopt-latest` |
| `shadow` | `9.5.1` | `9.6.1` | `adopt-latest` |

Gatling Gradle plugin은 라이브러리와 별도의 release number를 사용한다. 따라서
라이브러리용 `gatling=3.15.1`은 유지하고 plugin용 `gatling-plugin=3.15.1.2`를
추가한다. 이를 통해 양쪽 모두 각자의 최신 안정 버전을 중앙 catalog에서 관리한다.

## 보류

`org.owasp.dependencycheck`의 최신 안정 버전은 `13.0.0`이지만 현재 `12.2.2`에서
major boundary를 넘는다. 별도 migration 검토 없이 1.4.0 train에 포함하지 않고
`defer-breaking-migration`으로 기록한다.

Kotlin `2.4.10`은 최신 안정 버전이지만 downstream full build의 `detekt` task가
실패했다. `dev.detekt 2.0.0-alpha.5`가 Kotlin `2.4.0`으로 컴파일되어 다른 compiler
patch에서 실행을 거부하므로, 이번 train에서는 Kotlin `2.4.0`을 유지한다.

## 공식 metadata

- Gatling: https://plugins.gradle.org/m2/io/gatling/gradle/io.gatling.gradle.gradle.plugin/maven-metadata.xml
- Kotlin: https://plugins.gradle.org/m2/org/jetbrains/kotlin/jvm/org.jetbrains.kotlin.jvm.gradle.plugin/maven-metadata.xml
- Kover: https://plugins.gradle.org/m2/org/jetbrains/kotlinx/kover/org.jetbrains.kotlinx.kover.gradle.plugin/maven-metadata.xml
- Download Task: https://plugins.gradle.org/m2/de/undercouch/download/de.undercouch.download.gradle.plugin/maven-metadata.xml
- Jib: https://plugins.gradle.org/m2/com/google/cloud/tools/jib/com.google.cloud.tools.jib.gradle.plugin/maven-metadata.xml
- Shadow: https://plugins.gradle.org/m2/com/gradleup/shadow/com.gradleup.shadow.gradle.plugin/maven-metadata.xml
- OWASP Dependency Check: https://plugins.gradle.org/m2/org/owasp/dependencycheck/org.owasp.dependencycheck.gradle.plugin/maven-metadata.xml

## 검증 gate

- catalog checksum 및 ledger schema
- 중앙 build
- Gatling/Jib plugin을 사용하는 downstream의 candidate-catalog configuration
- 9개 downstream full build
- publication POM effective-model gate
