import nmcp.NmcpExtension

plugins {
    `java-platform`
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
    mavenLocal()
    mavenCentral()
    maven {
        name = "central-snapshots"
        url = uri("https://central.sonatype.com/repository/maven-snapshots/")
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
        // ── bluetape4k-projects core modules (also covered by bluetape4k-bom above) ──
        api(libs.bluetape4k.core)
        api(libs.bluetape4k.io)
        api(libs.bluetape4k.netty)
        api(libs.bluetape4k.coroutines)
        api(libs.bluetape4k.logging)
        api(libs.bluetape4k.jackson2)
        api(libs.bluetape4k.jackson3)
        api(libs.bluetape4k.idgenerators)
        api(libs.bluetape4k.resilience4j)
        api(libs.bluetape4k.junit5)
        api(libs.bluetape4k.testcontainers)

        // ── bluetape4k-aws modules ──────────────────────────────────────────
        api(libs.bluetape4k.aws)
        api(libs.bluetape4k.aws.kotlin)
        api(libs.bluetape4k.aws.spring.boot)
        api(libs.bluetape4k.aws.ktor)

        // ── bluetape4k-image modules ────────────────────────────────────────
        api(libs.bluetape4k.images)
        api(libs.bluetape4k.images.vips.api)
        api(libs.bluetape4k.images.vips.java21)
        api(libs.bluetape4k.images.vips.java25)

        // ── bluetape4k-text modules ─────────────────────────────────────────
        api(libs.bluetape4k.tokenizer.core)
        api(libs.bluetape4k.tokenizer.japanese)
        api(libs.bluetape4k.tokenizer.korean)
        api(libs.bluetape4k.lingua)
        api(libs.bluetape4k.text.search)

        // ── bluetape4k-graph modules (versions also covered by graph-bom platform above) ──
        api(libs.bluetape4k.graph.core)
        api(libs.bluetape4k.graph.age)
        api(libs.bluetape4k.graph.falkordb)
        api(libs.bluetape4k.graph.memgraph)
        api(libs.bluetape4k.graph.neo4j)
        api(libs.bluetape4k.graph.tinkerpop)
        api(libs.bluetape4k.graph.io.core)
        api(libs.bluetape4k.graph.io.csv)
        api(libs.bluetape4k.graph.io.graphml)
        api(libs.bluetape4k.graph.io.jackson2)
        api(libs.bluetape4k.graph.io.jackson3)
        api(libs.bluetape4k.graph.io.okio)

        // ── bluetape4k-leader modules (versions also covered by leader-bom platform above) ──
        api(libs.bluetape4k.leader.core)
        api(libs.bluetape4k.leader.redis.lettuce)
        api(libs.bluetape4k.leader.redis.redisson)
        api(libs.bluetape4k.leader.exposed.core)
        api(libs.bluetape4k.leader.exposed.jdbc)
        api(libs.bluetape4k.leader.exposed.r2dbc)
        api(libs.bluetape4k.leader.mongodb)
        api(libs.bluetape4k.leader.hazelcast)
        api(libs.bluetape4k.leader.spring.boot.common)
        api(libs.bluetape4k.leader.spring.boot3)
        api(libs.bluetape4k.leader.spring.boot4)
        api(libs.bluetape4k.leader.micrometer)

        // ── bluetape4k-javers modules ───────────────────────────────────────────
        api(libs.bluetape4k.javers.core)
        api(libs.bluetape4k.javers.persistence.kafka)
        api(libs.bluetape4k.javers.persistence.redis)

        // ── bluetape4k-exposed modules ──────────────────────────────────────────
        api(libs.bluetape4k.exposed.core)
        api(libs.bluetape4k.exposed.dao)
        api(libs.bluetape4k.exposed.jdbc)
        api(libs.bluetape4k.exposed.jdbc.tests)
        api(libs.bluetape4k.exposed.jdbc.caffeine)
        api(libs.bluetape4k.exposed.jdbc.lettuce)
        api(libs.bluetape4k.exposed.jdbc.redisson)
        api(libs.bluetape4k.exposed.r2dbc)
        api(libs.bluetape4k.exposed.r2dbc.tests)
        api(libs.bluetape4k.exposed.r2dbc.caffeine)
        api(libs.bluetape4k.exposed.r2dbc.lettuce)
        api(libs.bluetape4k.exposed.r2dbc.redisson)
        api(libs.bluetape4k.exposed.cache)
        api(libs.bluetape4k.exposed.measured)
        api(libs.bluetape4k.exposed.jackson2)
        api(libs.bluetape4k.exposed.jackson3)
        api(libs.bluetape4k.exposed.fastjson2)
        api(libs.bluetape4k.exposed.tink)
        api(libs.bluetape4k.exposed.bigquery)
        api(libs.bluetape4k.exposed.clickhouse)
        api(libs.bluetape4k.exposed.duckdb)
        api(libs.bluetape4k.exposed.mysql8)
        api(libs.bluetape4k.exposed.postgresql)
        api(libs.bluetape4k.exposed.trino)
        api(libs.bluetape4k.exposed.timefold.solver.persistence)
        api(libs.bluetape4k.batch)
        api(libs.bluetape4k.spring.boot3.batch.exposed)
        api(libs.bluetape4k.spring.boot3.exposed.jdbc)
        api(libs.bluetape4k.spring.boot3.exposed.r2dbc)
        api(libs.bluetape4k.spring.boot4.batch.exposed)
        api(libs.bluetape4k.spring.boot4.exposed.jdbc)
        api(libs.bluetape4k.spring.boot4.exposed.r2dbc)
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
    }
    repositories {
        mavenLocal()
    }
}

configurePublishingSigning("BluetapeDependencies")
