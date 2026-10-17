package io.bluetape4k.gradle

import org.gradle.api.DefaultTask
import org.gradle.api.file.ConfigurableFileCollection
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Classpath
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.TaskAction

abstract class VerifyDokkaFreemarkerResolutionTask : DefaultTask() {
    @get:Input
    abstract val expectedVersion: Property<String>

    @get:Classpath
    abstract val dokkaRuntimeClasspath: ConfigurableFileCollection

    @TaskAction
    fun verify() {
        val expectedArtifact = "freemarker-${expectedVersion.get()}.jar"
        val selectedArtifacts = dokkaRuntimeClasspath.files
            .filter { it.name.startsWith("freemarker-") && it.name.endsWith(".jar") }
            .map { it.name }
            .toSet()

        check(selectedArtifacts == setOf(expectedArtifact)) {
            "Expected Dokka configurations to resolve $expectedArtifact, " +
                "but found ${selectedArtifacts.ifEmpty { setOf("no dependency") }.joinToString()}."
        }
    }
}
