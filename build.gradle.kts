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

val projectGroup: String = providers.gradleProperty("projectGroup").get()
val baseVersion: String = providers.gradleProperty("baseVersion").get()
val snapshotVersion: String = providers.gradleProperty("snapshotVersion").get()

group = projectGroup
version = baseVersion + snapshotVersion

repositories {
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
    api(platform(libs.aws2.bom))
    api(platform(libs.ktor.bom))
    api(platform(libs.kotlinx.serialization.bom))
    api(platform(libs.log4j.bom))
    api(platform(libs.netty.bom))
    api(platform(libs.opentelemetry.bom))
    api(platform(libs.protobuf.bom))
    api(platform(libs.reactor.bom))
    api(platform(libs.timefold.solver.bom))
    api(platform(libs.vertx.dependencies))

    constraints {
        // <external-managed-modules by dependency governance>
        api(libs.agroal.pool)
        api(libs.avro)
        api(libs.avro.compiler)
        api(libs.aws.kotlin.core)
        api(libs.aws2.aws.crt)
        api(libs.bouncycastle.bcpg)
        api(libs.bouncycastle.bcpkix)
        api(libs.bouncycastle.bcprov)
        api(libs.classgraph)
        api(libs.commons.codec)
        api(libs.commons.compress)
        api(libs.commons.csv)
        api(libs.commons.exec)
        api(libs.commons.io)
        api(libs.commons.lang3)
        api(libs.commons.logging)
        api(libs.commons.pool2)
        api(libs.exposed.core)
        api(libs.exposed.jdbc)
        api(libs.exposed.r2dbc)
        api(libs.exposed.java.time)
        api(libs.exposed.migration.jdbc)
        api(libs.exposed.spring7.transaction)
        api(libs.exposed.spring.boot4.starter)
        api(libs.fabric8.kubernetes.client)
        api(libs.flyway.core)
        api(libs.fory.core)
        api(libs.fory.kotlin)
        api(libs.gatling.app)
        api(libs.guava)
        api(libs.hazelcast)
        api(libs.jakarta.activation.api)
        api(libs.jakarta.xml.bind)
        api(libs.javamoney.moneta)
        api(libs.logcaptor)
        api(libs.log4j.core)
        api(libs.mysql.connector.j)
        api(libs.mybatis.dynamic.sql)
        api(libs.netty.codec.http)
        api(libs.netty.codec.http2)
        api(libs.ow2.asm)
        api(libs.opentelemetry.api)
        api(libs.opentelemetry.extension.trace.propagators)
        api(libs.postgresql)
        api(libs.protobuf.java)
        api(libs.querydsl.apt)
        api(libs.querydsl.core)
        api(libs.querydsl.jpa)
        api(libs.querydsl.sql)
        api(libs.r2dbc.h2)
        api(libs.redisson)
        api(libs.scrimage.core)
        api(libs.slf4j.api)
        api(libs.springdoc.openapi.starter.webmvc.ui)
        api(libs.tomcat.embed.core)
        api(libs.tomcat.jdbc)
        api(libs.vertx.core)
        api(libs.zookeeper)
        api(libs.zstd.jni)
        // </external-managed-modules by dependency governance>
        // <generated-managed-modules by scripts/sync-managed-catalog.py>
        // Managed bluetape4k artifact versions are delegated to the sub-BOM platform imports above.
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
                        name.set("MIT License")
                        url.set("https://opensource.org/licenses/MIT")
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
            credentials(org.gradle.api.artifacts.repositories.PasswordCredentials::class) {
                username = centralUser
                password = centralPassword
            }
            authentication {
                create<org.gradle.authentication.http.BasicAuthentication>("basic")
            }
        }
    }
}

configurePublishingSigning("BluetapeDependencies")
