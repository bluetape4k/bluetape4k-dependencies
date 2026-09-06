plugins {
    java
    `maven-publish`
    signing
}

group = "io.bluetape4k.smoke"
version = "1.0.0"

val testRepository = providers
    .environmentVariable("TEST_MAVEN_REPOSITORY")
    .orElse(layout.buildDirectory.dir("test-repository").map { it.asFile.absolutePath })
    .get()

publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
        }
    }
    repositories {
        maven {
            name = "testRepository"
            url = uri(testRepository)
        }
    }
}

configurePublishingSigning("maven")
