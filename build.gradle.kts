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
    constraints {
        // ── bluetape4k-projects core modules ───────────────────────────────
        api(libs.bluetape4k.bom)
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
