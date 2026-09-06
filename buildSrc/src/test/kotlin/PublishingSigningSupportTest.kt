import org.gradle.api.Project
import org.gradle.testfixtures.ProjectBuilder
import org.gradle.plugins.signing.SigningExtension
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

class PublishingSigningSupportTest {

    private val armoredPrivateKey = """
        -----BEGIN PGP PRIVATE KEY BLOCK-----
        sentinel-private-key-body
        -----END PGP PRIVATE KEY BLOCK-----
    """.trimIndent()

    @Test
    fun `resolveSigningConfig keeps the public contract while normalizing signing input`() {
        val project = projectWith(
            "signingKeyId" to "0x1234567890ABCDEF",
            "signingKey" to armoredPrivateKey.replace("\n", "\\n"),
            "signingPassword" to "sentinel-password",
        )

        val config = project.resolveSigningConfig()

        assertEquals("0x90ABCDEF", config.keyId)
        assertEquals(armoredPrivateKey, config.key)
        assertEquals("sentinel-password", config.password)
        assertFalse(config.useGpgCmd)
        assertEquals("/opt/homebrew/bin/gpg", config.gpgExecutable)
        assertEquals("0x90ABCDEF", config.gpgKeyName)
    }

    @Test
    fun `configurePublishingSigning keeps the no-key path as a no-op`() {
        val project = projectWith()
        project.pluginManager.apply("signing")

        project.configurePublishingSigning("maven")

        project.extensions.getByType(SigningExtension::class.java)
        assertFalse(project.extensions.extraProperties.has("signing.gnupg.keyName"))
        assertFalse(project.extensions.extraProperties.has("signing.gnupg.executable"))
    }

    @Test
    fun `configurePublishingSigning keeps gpg command properties and normalized fallback`() {
        val project = projectWith(
            "signingKeyId" to "1234567890ABCDEF",
            "signingUseGpgCmd" to "true",
            "signing.gnupg.executable" to "/bin/sh",
        )
        project.pluginManager.apply("signing")

        project.configurePublishingSigning("maven")

        assertEquals(
            "/bin/sh",
            project.extensions.extraProperties["signing.gnupg.executable"],
        )
        assertEquals(
            "90ABCDEF",
            project.extensions.extraProperties["signing.gnupg.keyName"],
        )
    }

    private fun projectWith(vararg properties: Pair<String, String>): Project =
        ProjectBuilder.builder().build().also { project ->
            properties.forEach { (key, value) ->
                project.extensions.extraProperties[key] = value
            }
        }
}
