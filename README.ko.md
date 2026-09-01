# bluetape4k-dependencies

[English](README.md) | 한국어

<!-- README_VISUAL_OVERVIEW:START -->
## Overview Diagram

![Bluetape4k Dependencies overview diagram](docs/images/readme-diagrams/root-readme-overview-01.png)
<!-- README_VISUAL_OVERVIEW:END -->


[![CI](https://github.com/bluetape4k/bluetape4k-dependencies/actions/workflows/ci.yml/badge.svg)](https://github.com/bluetape4k/bluetape4k-dependencies/actions/workflows/ci.yml)
[![Maven Central](https://img.shields.io/maven-central/v/io.github.bluetape4k/bluetape4k-dependencies)](https://central.sonatype.com/artifact/io.github.bluetape4k/bluetape4k-dependencies)
[![Kotlin](https://img.shields.io/badge/Kotlin-2.4-7F52FF?logo=kotlin)](https://kotlinlang.org)
[![JVM](https://img.shields.io/badge/JVM-21-ED8B00?logo=openjdk)](https://openjdk.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Dependency resolution은 BOM으로, Gradle build alias는 catalog로 관리합니다.**

![bluetape4k dependencies 버전 정렬 작업대 일러스트](./docs/assets/dependencies-workbench.png)

`bluetape4k-dependencies`는 bluetape4k 생태계 전체를 위한 중앙화된 BOM(Bill of Materials)입니다.
`spring-boot-dependencies`와 동일한 패턴을 따릅니다: 플랫폼 의존성 하나만 추가하면 모든 bluetape4k
모듈의 버전이 자동으로 정렬됩니다 — 개별 아티팩트에 버전을 명시할 필요가 없습니다.

같은 레포지토리의 `gradle/libs.versions.toml`은 내부 Gradle Version Catalog source입니다.
공통 plugin version, library alias, bluetape4k 모듈 좌표를 제공합니다.

---

## 왜 별도의 BOM 레포지토리가 필요한가?

bluetape4k 생태계는 각자 독립적인 릴리즈 주기를 가진 여러 레포지토리로 분리되어 있습니다:

| 레포지토리 | Group ID |
|---|---|
| [bluetape4k-projects](https://github.com/bluetape4k/bluetape4k-projects) | `io.github.bluetape4k` |
| [bluetape4k-aws](https://github.com/bluetape4k/bluetape4k-aws) | `io.github.bluetape4k.aws` |
| [bluetape4k-image](https://github.com/bluetape4k/bluetape4k-image) | `io.github.bluetape4k.image` |
| [bluetape4k-text](https://github.com/bluetape4k/bluetape4k-text) | `io.github.bluetape4k.text` |
| [bluetape4k-graph](https://github.com/bluetape4k/bluetape4k-graph) | `io.github.bluetape4k.graph` |
| [bluetape4k-leader](https://github.com/bluetape4k/bluetape4k-leader) | `io.github.bluetape4k.leader` |
| [bluetape4k-exposed](https://github.com/bluetape4k/bluetape4k-exposed) | `io.github.bluetape4k.exposed` |
| [bluetape4k-javers](https://github.com/bluetape4k/bluetape4k-javers) | `io.github.bluetape4k.javers` |

중앙화된 BOM과 catalog가 없으면 사용자는 각 레포지토리 버전, Gradle plugin 버전,
compatibility-line alias를 직접 추적해야 합니다. `bluetape4k-dependencies`는 dependency
constraint와 Gradle build alias를 한 곳에 모아 이 문제를 해결합니다.

---

## 구조

![dependencies Architecture diagram](docs/images/readme-diagrams/bluetape4k-dependencies-architecture-01.png)

---

## 사용 방법

Dependency resolution에는 BOM을 사용합니다. 내부 Gradle build alias와 plugin version에는 checkout된
`bluetape4k-dependencies/gradle/libs.versions.toml`을 사용합니다. Catalog는 BOM을 대체하지
않습니다. Catalog는 Gradle build가 공유하는 이름 체계를 제공하고, BOM은 실제 resolved dependency
version을 정렬합니다.

### Gradle Version Catalog

```kotlin
// settings.gradle.kts
dependencyResolutionManagement {
    versionCatalogs {
        create("bt4k") {
            from(files("../bluetape4k-dependencies/gradle/libs.versions.toml"))
        }
    }
}
```

```kotlin
// build.gradle.kts
plugins {
    alias(bt4k.plugins.kotlin.jvm)
    alias(bt4k.plugins.nmcp) apply false
}

dependencies {
    implementation(platform("io.github.bluetape4k:bluetape4k-dependencies:VERSION"))
    implementation(bt4k.bluetape4k.core)
    implementation(bt4k.bluetape4k.coroutines)
}
```

BOM을 플랫폼 의존성으로 추가하면 이후 모든 bluetape4k 아티팩트를 **버전 없이** 선언할 수 있습니다.

### Gradle (Kotlin DSL)

```kotlin
dependencies {
    implementation(platform("io.github.bluetape4k:bluetape4k-dependencies:VERSION"))

    // bluetape4k-projects — 핵심 유틸리티
    implementation("io.github.bluetape4k:bluetape4k-core")
    implementation("io.github.bluetape4k:bluetape4k-coroutines")
    implementation("io.github.bluetape4k:bluetape4k-logging")
    implementation("io.github.bluetape4k:bluetape4k-jackson2")
    implementation("io.github.bluetape4k:bluetape4k-jackson3")
    implementation("io.github.bluetape4k:bluetape4k-idgenerators")
    implementation("io.github.bluetape4k:bluetape4k-resilience4j")
    implementation("io.github.bluetape4k:bluetape4k-spring-boot-core")
    testImplementation("io.github.bluetape4k:bluetape4k-junit5")
    testImplementation("io.github.bluetape4k:bluetape4k-testcontainers")

    // bluetape4k-aws
    implementation("io.github.bluetape4k.aws:bluetape4k-aws-java")
    implementation("io.github.bluetape4k.aws:bluetape4k-aws-kotlin")
    implementation("io.github.bluetape4k.aws:bluetape4k-aws-spring-boot")

    // bluetape4k-image
    implementation("io.github.bluetape4k.image:bluetape4k-images")
    implementation("io.github.bluetape4k.image:bluetape4k-images-vips-api")

    // bluetape4k-text
    implementation("io.github.bluetape4k.text:tokenizer-core")
    implementation("io.github.bluetape4k.text:lingua")

    // bluetape4k-graph
    implementation("io.github.bluetape4k.graph:bluetape4k-graph-core")
    implementation("io.github.bluetape4k.graph:bluetape4k-graph-neo4j")

    // bluetape4k-leader
    implementation("io.github.bluetape4k.leader:bluetape4k-leader-core")
    implementation("io.github.bluetape4k.leader:bluetape4k-leader-redis-lettuce")
    implementation("io.github.bluetape4k.leader:bluetape4k-leader-spring-boot")
}
```

### Gradle (Groovy DSL)

```groovy
dependencies {
    implementation platform("io.github.bluetape4k:bluetape4k-dependencies:VERSION")

    implementation "io.github.bluetape4k:bluetape4k-core"
    implementation "io.github.bluetape4k:bluetape4k-coroutines"
    // ... 버전 불필요
}
```

### Maven

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>io.github.bluetape4k</groupId>
            <artifactId>bluetape4k-dependencies</artifactId>
            <version>VERSION</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<dependencies>
    <dependency>
        <groupId>io.github.bluetape4k</groupId>
        <artifactId>bluetape4k-core</artifactId>
        <!-- 버전 불필요 -->
    </dependency>
</dependencies>
```

---

## Spring Boot 정책

`bluetape4k-dependencies`의 첫 공식 배포는 Spring Boot 4-only 통합을
표준으로 삼습니다. Spring Boot 3 아티팩트는 기존 1.7.x 라인에 남아 있지만,
이 BOM의 forward public contract로는 노출하지 않습니다.

Spring Boot 4 통합은 versionless `spring-boot` 아티팩트 이름을 사용합니다:

| 기존 또는 전환 전 이름 | 첫 공식 BOM 표준 이름 |
|---|---|
| `bluetape4k-spring-boot3-*` | 노출하지 않음 |
| `bluetape4k-spring-boot4-*` | `bluetape4k-spring-boot-*` |
| `leader-spring-boot3` / `leader-spring-boot4` | `leader-spring-boot` |
| `bluetape4k-spring-boot4-exposed-*` | `exposed-spring-boot-*` |

---

## 관리 모듈 목록

관리 catalog alias는 sibling repository의 `settings.gradle.kts` 모듈 include
목록에서 생성합니다. Published artifact version은 import된 bluetape4k sub-BOM에
위임합니다:

```bash
scripts/sync-managed-catalog.py --check --summary
scripts/sync-managed-catalog.py --write --check --summary
scripts/verify-managed-artifacts.py --summary
python3 -m unittest tests/test_sync_managed_catalog.py
```

bluetape4k 유지보수자를 위한 상세 버전 관리 절차는
[`docs/version-management.ko.md`](docs/version-management.ko.md)를 참고하세요.

정확한 생성 아티팩트 alias 목록과 published Gradle Version Catalog의 기준은
`gradle/libs.versions.toml`입니다.
아래 섹션은 주요 public module family를 요약합니다.

이 레포지토리의 shared dependency/plugin version alias는 관리 대상 library 레포지토리의
source of truth이기도 합니다. 해당 alias를 변경한 뒤에는 downstream의 중앙 catalog adoption을 검증합니다:

```bash
scripts/sync-shared-versions.py --workspace .. --check --summary
scripts/sync-dependabot-ignores.py --workspace .. --check --summary
scripts/sync-dependabot-ignores.py --workspace .. --write --check --summary
scripts/triage-dependabot-alerts.py --repo bluetape4k-projects
```

현재 방식은 `bluetape4k-dependencies/gradle/libs.versions.toml`을 `bt4k` catalog로
직접 import하는 중앙 관리 방식입니다. `scripts/sync-shared-versions.py`는 downstream 파일을
수정하지 않는 read-only adoption guard이며, 중앙 version/coordinate/plugin id를 local catalog가
다시 소유하면 실패합니다. 기존 `--write` option은 호환성 때문에 인식하지만 파일을 변경하지 않습니다.

PR CI는 sibling-dependent managed-catalog 및 artifact 검사를 위해 관리 repository를 clone하지만,
adoption guard 자체는 `tests/fixtures/catalog-adoption-clean`의 clean fixture에 실행합니다. Push와 수동
CI는 같은 clone을 사용해 전체 workspace adoption 감사도 수행합니다. `gradle/libs.versions.toml.sha256`은 immutable catalog ref의 portable integrity
sidecar이므로 catalog 변경 때마다 다시 생성해야 합니다. 중앙 채택 과정에서 의도한 버전 변화는
`config/central-catalog-version-deltas.json`에 기록하고, migration 전후 dependency report가 확인하기
전까지 `pending-resolved-graph`로 유지합니다.

Workshop과 example 레포지토리는 catalog sync 대상이 아닙니다. 이 레포지토리들은
배포된 `bluetape4k-dependencies` BOM artifact version을 소비해야 하며, central catalog
alias bump를 직접 따라가지 않습니다.

관리 대상 downstream library 레포지토리의 Dependabot도 중앙에서 관리하는 dependency name을 ignore해야 합니다.
새 shared dependency line을 추가하면 `scripts/sync-dependabot-ignores.py`의
`CENTRAL_DEPENDENCY_IGNORES`에 dependency name을 추가하고, 위 명령으로
downstream `.github/dependabot.yml`을 동기화합니다.

Active bluetape4k `-SNAPSHOT` artifact를 소비하는 downstream workflow는
`--refresh-dependencies`를 기본값에서 제거하고, bounded changing-module cache를 유지하며,
snapshot-heavy Gradle warm-up command를 `scripts/retry-snapshot-resolution.sh`로
감쌉니다. 이 wrapper는 Central snapshot metadata/artifact `403` signature에서만
재시도하고 실제 build/test failure는 즉시 실패시킵니다. 자세한 CI/Nightly/Examples
운영 절차는 [`docs/version-management.ko.md`](docs/version-management.ko.md)에
정리되어 있습니다.

Dependabot security alert은 alert이 보이는 레포지토리가 아니라 dependency owner 기준으로
분류합니다. `scripts/triage-dependabot-alerts.py`로 open alert을 다음 route로 나눕니다.

| Route | Owner | Action |
|---|---|---|
| `central-catalog` | `bluetape4k-dependencies` | source-of-truth catalog를 먼저 갱신하고 downstream adoption guard를 실행합니다. |
| `central-bom-transitive` | `spring-boot` 같은 central BOM line | patched BOM이 있으면 BOM line을 올리고, 없으면 central override를 추가하거나 유지한 뒤 downstream resolution을 검증합니다. |
| `repo-tooling` | alert 레포지토리 | Gradle/plugin/settings tooling을 해당 레포에서 고치되, 공통이면 central governance로 승격합니다. |
| `repo-local` | alert 레포지토리 | manifest를 소유한 레포에서 직접 고칩니다. |

관리 대상 downstream 레포지토리는 checkout된
`bluetape4k-dependencies/gradle/libs.versions.toml`을 `bt4k` catalog로 import하며,
repository convention plugin을 통해 `bluetape4k-dependencies` BOM을 platform으로 import해야
합니다. BOM은 dependency resolution 계약이고, catalog는 Gradle authoring 계약입니다.

권장 릴리즈 흐름은 다음과 같습니다:

1. 이 레포지토리의 source-of-truth block을 수정합니다.
2. `scripts/sync-shared-versions.py --workspace .. --check --summary`로 downstream 중복 권한이 없는지 확인합니다.
3. 중앙 관리 dependency name이 추가/삭제되면
   `scripts/sync-dependabot-ignores.py --workspace .. --write --check --summary`를 실행합니다.
4. 변경된 관리 대상 downstream library 레포지토리 PR을 열고 CI 검증 후 머지합니다.
5. 마지막으로 `bluetape4k-dependencies` PR을 머지합니다. 이 PR의 CI는 downstream `develop` branch를
   다시 clone해서 설정된 관리 대상 library 레포지토리에 shared-version drift가 남아 있는지 검사합니다.

Compatibility-line alias는 의도적으로 분리합니다. 자동 동기화 중 `kafka3`/`kafka4`,
`jackson2`/`jackson3`, `spring-boot3`/`spring-boot4`, `spring-kafka`/`spring-kafka4` 같은 alias를
하나로 합치지 않습니다.

### bluetape4k-projects (`io.github.bluetape4k`)

아래 표는 현재 `gradle/libs.versions.toml`에 생성되는 모든 managed `bluetape4k-projects` artifact를
기록합니다.

| 아티팩트 | 영역 |
|---|---|
| `bluetape4k-assertions` | 테스트 assertion |
| `bluetape4k-avro` | 직렬화 |
| `bluetape4k-bom` | BOM |
| `bluetape4k-bucket4j` | Rate limiting |
| `bluetape4k-cache-core` | Cache |
| `bluetape4k-cache-hazelcast` | Cache |
| `bluetape4k-cache-lettuce` | Cache |
| `bluetape4k-cache-redisson` | Cache |
| `bluetape4k-cassandra` | Data access |
| `bluetape4k-core` | 핵심 유틸리티 |
| `bluetape4k-coroutines` | Coroutines |
| `bluetape4k-csv` | 직렬화 |
| `bluetape4k-elasticsearch` | Search |
| `bluetape4k-fastjson2` | 직렬화 |
| `bluetape4k-feign` | HTTP client |
| `bluetape4k-geo` | Geo 유틸리티 |
| `bluetape4k-grpc` | gRPC |
| `bluetape4k-hibernate` | Hibernate |
| `bluetape4k-hibernate-cache-lettuce` | Hibernate cache |
| `bluetape4k-hibernate-reactive` | Hibernate Reactive |
| `bluetape4k-http` | HTTP |
| `bluetape4k-idgenerators` | ID 생성 |
| `bluetape4k-io` | I/O |
| `bluetape4k-jackson2` | Jackson 2 |
| `bluetape4k-jackson3` | Jackson 3 |
| `bluetape4k-javatimes` | 날짜/시간 |
| `bluetape4k-jdbc` | JDBC |
| `bluetape4k-json` | JSON |
| `bluetape4k-junit5` | JUnit 5 |
| `bluetape4k-jwt` | JWT |
| `bluetape4k-kafka` | Kafka 3 line |
| `bluetape4k-kafka-logback` | Kafka logging |
| `bluetape4k-kafka4` | Kafka 4 line |
| `bluetape4k-lettuce` | Redis Lettuce |
| `bluetape4k-logging` | Logging |
| `bluetape4k-math` | Math |
| `bluetape4k-measured` | Measurement |
| `bluetape4k-micrometer` | Metrics |
| `bluetape4k-money` | Money |
| `bluetape4k-mongodb` | MongoDB |
| `bluetape4k-mutiny` | Mutiny |
| `bluetape4k-nats` | NATS |
| `bluetape4k-netty` | Netty |
| `bluetape4k-okio` | Okio |
| `bluetape4k-opentelemetry` | OpenTelemetry |
| `bluetape4k-probabilistic` | 확률적 자료구조 |
| `bluetape4k-protobuf` | Protobuf |
| `bluetape4k-pulsar` | Pulsar |
| `bluetape4k-r2dbc` | R2DBC |
| `bluetape4k-redis` | Redis |
| `bluetape4k-redisson` | Redis Redisson |
| `bluetape4k-resilience4j` | Resilience4j |
| `bluetape4k-retrofit2` | HTTP client |
| `bluetape4k-rule-engine` | Rules |
| `bluetape4k-science` | Science 유틸리티 |
| `bluetape4k-spring-boot-cassandra` | Spring Boot |
| `bluetape4k-spring-boot-core` | Spring Boot |
| `bluetape4k-spring-boot-hibernate-lettuce` | Spring Boot |
| `bluetape4k-spring-boot-mongodb` | Spring Boot |
| `bluetape4k-spring-boot-r2dbc` | Spring Boot |
| `bluetape4k-spring-boot-redis` | Spring Boot |
| `bluetape4k-states` | State machine |
| `bluetape4k-testcontainers` | Testcontainers |
| `bluetape4k-tink` | Tink crypto |
| `bluetape4k-vertx` | Vert.x |
| `bluetape4k-virtualthread-api` | Virtual threads |
| `bluetape4k-virtualthread-jdk21` | Virtual threads |
| `bluetape4k-virtualthread-jdk25` | Virtual threads |
| `bluetape4k-workflow` | Workflow 유틸리티 |

### bluetape4k-aws (`io.github.bluetape4k.aws`)

| 아티팩트 | 설명 |
|---|---|
| `aws` | AWS SDK v2 Kotlin 확장 |
| `aws-kotlin` | AWS Kotlin SDK 지원 |
| `aws-spring-boot` | AWS용 Spring Boot 자동 설정 |
| `aws-ktor` | AWS용 Ktor 통합 |

### bluetape4k-image (`io.github.bluetape4k.image`)

| 아티팩트 | 설명 |
|---|---|
| `bluetape4k-image-bom` | 이미지 모듈 BOM |
| `images` | 이미지 처리 핵심 유틸리티 |
| `images-ktor` | 이미지 모듈 Ktor 통합 |
| `images-ocr` | 이미지 모듈 OCR 통합 |
| `images-spring-boot` | 이미지 모듈 Spring Boot 통합 |
| `images-vips-api` | libvips API 추상화 |
| `images-vips-java21` | Java 21용 libvips 바인딩 |
| `images-vips-java25` | Java 25용 libvips 바인딩 |

### bluetape4k-text (`io.github.bluetape4k.text`)

| 아티팩트 | 설명 |
|---|---|
| `tokenizer-core` | 텍스트 토크나이저 핵심 API |
| `tokenizer-japanese` | 일본어 토크나이저 (Kuromoji) |
| `tokenizer-korean` | 한국어 토크나이저 (Nori / Komoran) |
| `lingua` | 언어 감지 (Lingua) |
| `text-search` | 전문 검색 유틸리티 |

### bluetape4k-graph (`io.github.bluetape4k.graph`)

| 아티팩트 | 설명 |
|---|---|
| `bluetape4k-graph-bom` | 그래프 모듈 BOM |
| `graph-core` | 핵심 그래프 추상화 |
| `graph-age` | Apache AGE (PostgreSQL 그래프) 통합 |
| `graph-falkordb` | FalkorDB 통합 |
| `graph-memgraph` | Memgraph 통합 |
| `graph-neo4j` | Neo4j 통합 |
| `graph-tinkerpop` | Apache TinkerPop 통합 |
| `graph-io-core` | 그래프 I/O 핵심 |
| `graph-io-csv` | CSV 그래프 직렬화 |
| `graph-io-graphml` | GraphML 직렬화 |
| `graph-io-jackson2` | Jackson 2.x 그래프 직렬화 |
| `graph-io-jackson3` | Jackson 3.x 그래프 직렬화 |
| `graph-okio` | Okio 기반 그래프 I/O |

### bluetape4k-leader (`io.github.bluetape4k.leader`)

| 아티팩트 | 설명 |
|---|---|
| `leader-bom` | 리더 선출 모듈 BOM |
| `leader-core` | 핵심 리더 선출 API |
| `leader-redis-lettuce` | Lettuce 기반 Redis 리더 선출 |
| `leader-redis-redisson` | Redisson 기반 Redis 리더 선출 |
| `leader-exposed-core` | Exposed 리더 선출 공통 |
| `leader-exposed-jdbc` | Exposed JDBC 리더 선출 |
| `leader-exposed-r2dbc` | Exposed R2DBC 리더 선출 |
| `leader-mongodb` | MongoDB 리더 선출 |
| `leader-hazelcast` | Hazelcast 리더 선출 |
| `leader-zookeeper` | ZooKeeper/Apache Curator 리더 선출 |
| `leader-spring-boot` | Spring Boot 4 자동 설정과 AOP |
| `leader-ktor` | 리더 선출 Ktor 통합 |
| `leader-micrometer` | 리더 선출 Micrometer 메트릭 |

---

## 버전 관리 정책

각 업스트림 레포지토리는 **독립적인 버전**을 유지하며 `gradle/libs.versions.toml`에서 관리됩니다:

```toml
[versions]
bluetape4k-dependencies = "2.0.0"
bluetape4k-bom          = "2.0.0"
bluetape4k-aws-bom      = "1.0.0-SNAPSHOT"
bluetape4k-image-bom    = "1.0.0-SNAPSHOT"
bluetape4k-text-bom     = "1.0.0-SNAPSHOT"
bluetape4k-graph-bom    = "1.0.0-SNAPSHOT"
bluetape4k-leader-bom   = "1.0.0-SNAPSHOT"
bluetape4k-exposed-bom  = "2.0.0-SNAPSHOT"
bluetape4k-javers-bom   = "1.0.0-SNAPSHOT"
```

정식 배포 train에서는 각 upstream artifact가 Maven Central에 공개된 뒤 해당
BOM ref만 순서대로 stable로 승격합니다. Downstream build는 검증·병합된 exact
catalog commit을 사용하며, 모든 internal BOM이 stable이 되기 전에는 최종
`bluetape4k-dependencies` BOM을 게시하지 않습니다.

새로운 업스트림 릴리즈를 반영하려면 `libs.versions.toml`에서 해당 버전을
수정하고 `libs.versions.toml.sha256`을 갱신한 뒤 publication POM을 검증합니다.
Release checklist가 dispatch를 허용할 때만 새 BOM 버전을 게시합니다.

---

## 라이선스

[MIT License](LICENSE) 라이선스를 따릅니다.
