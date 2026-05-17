import nmcp.NmcpExtension

plugins {
    `java-platform`
    `version-catalog`
    `maven-publish`
    signing

    alias(libs.plugins.nmcp)
    alias(libs.plugins.dokka)
}

val centralPublishing = resolveCentralPublishingConfig()
val centralUser: String = centralPublishing.username
val centralPassword: String = centralPublishing.password
val centralSnapshotsParallelism: Int = providers
    .gradleProperty("centralSnapshotsParallelism")
    .map(String::toInt)
    .orElse(1)
    .get()

val projectGroup: String by project
val baseVersion: String by project
val snapshotVersion: String by project

group = projectGroup
version = baseVersion + snapshotVersion

repositories {
    mavenCentral()
    maven {
        name = "central-snapshots"
        url = uri("https://central.sonatype.com/repository/maven-snapshots/")
    }
}

catalog {
    versionCatalog {
        from(files("gradle/libs.versions.toml"))
    }
}

// Allow dependencies block in java-platform
javaPlatform {
    allowDependencies()
}

dependencies {
    // Sub-BOMs imported as platform: all modules in each repo are version-managed for
    // consumers without requiring individual constraint entries here.
    api(platform(libs.bluetape4k.bom))
    api(platform(libs.bluetape4k.aws.bom))
    api(platform(libs.bluetape4k.image.bom))
    api(platform(libs.bluetape4k.text.bom))
    api(platform(libs.bluetape4k.graph.bom))
    api(platform(libs.bluetape4k.leader.bom))
    api(platform(libs.bluetape4k.exposed.bom))
    api(platform(libs.bluetape4k.javers.bom))

    constraints {
        // <generated-managed-modules by scripts/sync-managed-catalog.py>
        // -- bluetape4k-projects modules --
        api(libs.bluetape4k.assertions)
        api(libs.bluetape4k.avro)
        api(libs.bluetape4k.bucket4j)
        api(libs.bluetape4k.cache.core)
        api(libs.bluetape4k.cache.hazelcast)
        api(libs.bluetape4k.cache.lettuce)
        api(libs.bluetape4k.cache.redisson)
        api(libs.bluetape4k.cassandra)
        api(libs.bluetape4k.core)
        api(libs.bluetape4k.coroutines)
        api(libs.bluetape4k.csv)
        api(libs.bluetape4k.elasticsearch)
        api(libs.bluetape4k.fastjson2)
        api(libs.bluetape4k.feign)
        api(libs.bluetape4k.geo)
        api(libs.bluetape4k.grpc)
        api(libs.bluetape4k.hibernate)
        api(libs.bluetape4k.hibernate.cache.lettuce)
        api(libs.bluetape4k.hibernate.reactive)
        api(libs.bluetape4k.http)
        api(libs.bluetape4k.idgenerators)
        api(libs.bluetape4k.io)
        api(libs.bluetape4k.jackson2)
        api(libs.bluetape4k.jackson3)
        api(libs.bluetape4k.javatimes)
        api(libs.bluetape4k.jdbc)
        api(libs.bluetape4k.json)
        api(libs.bluetape4k.junit5)
        api(libs.bluetape4k.jwt)
        api(libs.bluetape4k.kafka)
        api(libs.bluetape4k.kafka.logback)
        api(libs.bluetape4k.kafka4)
        api(libs.bluetape4k.lettuce)
        api(libs.bluetape4k.logging)
        api(libs.bluetape4k.math)
        api(libs.bluetape4k.measured)
        api(libs.bluetape4k.micrometer)
        api(libs.bluetape4k.mock.web.server)
        api(libs.bluetape4k.mock.webflux.server)
        api(libs.bluetape4k.money)
        api(libs.bluetape4k.mongodb)
        api(libs.bluetape4k.mutiny)
        api(libs.bluetape4k.nats)
        api(libs.bluetape4k.netty)
        api(libs.bluetape4k.okio)
        api(libs.bluetape4k.opentelemetry)
        api(libs.bluetape4k.probabilistic)
        api(libs.bluetape4k.protobuf)
        api(libs.bluetape4k.pulsar)
        api(libs.bluetape4k.r2dbc)
        api(libs.bluetape4k.redis)
        api(libs.bluetape4k.redisson)
        api(libs.bluetape4k.resilience4j)
        api(libs.bluetape4k.retrofit2)
        api(libs.bluetape4k.rule.engine)
        api(libs.bluetape4k.science)
        api(libs.bluetape4k.spring.boot.cassandra)
        api(libs.bluetape4k.spring.boot.core)
        api(libs.bluetape4k.spring.boot.hibernate.lettuce)
        api(libs.bluetape4k.spring.boot.mongodb)
        api(libs.bluetape4k.spring.boot.r2dbc)
        api(libs.bluetape4k.spring.boot.redis)
        api(libs.bluetape4k.states)
        api(libs.bluetape4k.testcontainers)
        api(libs.bluetape4k.tink)
        api(libs.bluetape4k.vertx)
        api(libs.bluetape4k.virtualthread.api)
        api(libs.bluetape4k.virtualthread.jdk21)
        api(libs.bluetape4k.virtualthread.jdk25)
        api(libs.bluetape4k.workflow)

        // -- bluetape4k-aws modules --
        api(libs.bluetape4k.aws.java)
        api(libs.bluetape4k.aws.kotlin)
        api(libs.bluetape4k.aws.ktor)
        api(libs.bluetape4k.aws.spring.boot)

        // -- bluetape4k-image modules --
        api(libs.bluetape4k.images)
        api(libs.bluetape4k.images.spring.boot)
        api(libs.bluetape4k.images.vips.api)
        api(libs.bluetape4k.images.vips.java21)
        api(libs.bluetape4k.images.vips.java25)

        // -- bluetape4k-text modules --
        api(libs.bluetape4k.lingua)
        api(libs.bluetape4k.text.search)
        api(libs.bluetape4k.tokenizer.core)
        api(libs.bluetape4k.tokenizer.japanese)
        api(libs.bluetape4k.tokenizer.korean)

        // -- bluetape4k-graph modules --
        api(libs.bluetape4k.graph.age)
        api(libs.bluetape4k.graph.core)
        api(libs.bluetape4k.graph.falkordb)
        api(libs.bluetape4k.graph.io.core)
        api(libs.bluetape4k.graph.io.csv)
        api(libs.bluetape4k.graph.io.graphml)
        api(libs.bluetape4k.graph.io.jackson2)
        api(libs.bluetape4k.graph.io.jackson3)
        api(libs.bluetape4k.graph.ktor)
        api(libs.bluetape4k.graph.memgraph)
        api(libs.bluetape4k.graph.neo4j)
        api(libs.bluetape4k.graph.okio)
        api(libs.bluetape4k.graph.spring.boot)
        api(libs.bluetape4k.graph.tinkerpop)

        // -- bluetape4k-leader modules --
        api(libs.bluetape4k.leader.core)
        api(libs.bluetape4k.leader.exposed.core)
        api(libs.bluetape4k.leader.exposed.jdbc)
        api(libs.bluetape4k.leader.exposed.r2dbc)
        api(libs.bluetape4k.leader.hazelcast)
        api(libs.bluetape4k.leader.ktor)
        api(libs.bluetape4k.leader.micrometer)
        api(libs.bluetape4k.leader.mongodb)
        api(libs.bluetape4k.leader.redis.lettuce)
        api(libs.bluetape4k.leader.redis.redisson)
        api(libs.bluetape4k.leader.spring.boot)
        api(libs.bluetape4k.leader.zookeeper)

        // -- bluetape4k-exposed modules --
        api(libs.bluetape4k.exposed.batch)
        api(libs.bluetape4k.exposed.spring.boot.batch)
        api(libs.bluetape4k.exposed.spring.boot.jdbc)
        api(libs.bluetape4k.exposed.spring.boot.r2dbc)
        api(libs.bluetape4k.exposed.spring.modulith)
        api(libs.exposed.bigquery)
        api(libs.exposed.cache)
        api(libs.exposed.clickhouse)
        api(libs.exposed.core)
        api(libs.exposed.dao)
        api(libs.exposed.duckdb)
        api(libs.exposed.fastjson2)
        api(libs.exposed.jackson2)
        api(libs.exposed.jackson3)
        api(libs.exposed.jdbc)
        api(libs.exposed.jdbc.caffeine)
        api(libs.exposed.jdbc.lettuce)
        api(libs.exposed.jdbc.redisson)
        api(libs.exposed.jdbc.tests)
        api(libs.exposed.measured)
        api(libs.exposed.mysql8)
        api(libs.exposed.postgresql)
        api(libs.exposed.r2dbc)
        api(libs.exposed.r2dbc.caffeine)
        api(libs.exposed.r2dbc.lettuce)
        api(libs.exposed.r2dbc.redisson)
        api(libs.exposed.r2dbc.tests)
        api(libs.exposed.timefold.solver.persistence)
        api(libs.exposed.tink)
        api(libs.exposed.trino)

        // -- bluetape4k-javers modules --
        api(libs.bluetape4k.javers.core)
        api(libs.bluetape4k.javers.persistence.kafka)
        api(libs.bluetape4k.javers.persistence.redis)

        // </generated-managed-modules>
    }
}

extensions.configure<NmcpExtension>("nmcp") {
    publishAllPublicationsToCentralPortal {
        username.set(centralUser)
        password.set(centralPassword)
        publishingType.set("AUTOMATIC")
        uploadSnapshotsParallelism.set(centralSnapshotsParallelism)
    }
}

publishing {
    publications {
        create<MavenPublication>("BluetapeDependencies") {
            from(components["javaPlatform"])

            pom {
                name.set("bluetape4k-dependencies")
                description.set("Centralized BOM for the bluetape4k ecosystem — coordinates versions across all independent modules")
                url.set("https://github.com/bluetape4k/bluetape4k-dependencies")
                licenses {
                    license {
                        name.set("The Apache License, Version 2.0")
                        url.set("https://www.apache.org/licenses/LICENSE-2.0.txt")
                    }
                }
                developers {
                    developer {
                        id.set("debop")
                        name.set("Sunghyouk Bae")
                        email.set("sunghyouk.bae@gmail.com")
                    }
                }
                scm {
                    connection.set("scm:git:git://github.com/bluetape4k/bluetape4k-dependencies.git")
                    developerConnection.set("scm:git:ssh://github.com/bluetape4k/bluetape4k-dependencies.git")
                    url.set("https://github.com/bluetape4k/bluetape4k-dependencies")
                }
            }
        }
        create<MavenPublication>("BluetapeVersionCatalog") {
            from(components["versionCatalog"])
            artifactId = "bluetape4k-version-catalog"

            pom {
                name.set("bluetape4k-version-catalog")
                description.set("Published Gradle version catalog for bluetape4k build plugins, aliases, and managed module coordinates")
                url.set("https://github.com/bluetape4k/bluetape4k-dependencies")
                licenses {
                    license {
                        name.set("The Apache License, Version 2.0")
                        url.set("https://www.apache.org/licenses/LICENSE-2.0.txt")
                    }
                }
                developers {
                    developer {
                        id.set("debop")
                        name.set("Sunghyouk Bae")
                        email.set("sunghyouk.bae@gmail.com")
                    }
                }
                scm {
                    connection.set("scm:git:git://github.com/bluetape4k/bluetape4k-dependencies.git")
                    developerConnection.set("scm:git:ssh://github.com/bluetape4k/bluetape4k-dependencies.git")
                    url.set("https://github.com/bluetape4k/bluetape4k-dependencies")
                }
            }
        }
    }
    repositories {
        mavenCentral()
        maven {
            name = "central-snapshots"
            url = uri("https://central.sonatype.com/repository/maven-snapshots/")
        }
    }
}

configurePublishingSigning("BluetapeDependencies")
configurePublishingSigning("BluetapeVersionCatalog")
