package io.bluetape4k.gradle

import java.util.Base64
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class PublishingSigningKeySupportTest {

    private val armoredPrivateKey = """
        -----BEGIN PGP PRIVATE KEY BLOCK-----
        sentinel-private-key-body
        -----END PGP PRIVATE KEY BLOCK-----
    """.trimIndent()

    @Test
    fun `공개 함수 시그니처를 유지한다`() {
        val normalize: (String) -> NormalizedSigningKeyId = ::normalizeSigningKeyId
        val resolveId: (String) -> String = ::resolveSigningKeyId
        val resolveKey: (String) -> String = ::resolveSigningKey

        assertEquals("ABCDEF12", normalize("ABCDEF12").value)
        assertEquals("ABCDEF12", resolveId("ABCDEF12"))
        assertEquals("", resolveKey(""))
    }

    @Test
    fun `16자리 hex key id만 trailing 8자리로 정규화한다`() {
        assertEquals("90ABCDEF", normalizeSigningKeyId("1234567890ABCDEF").value)
        assertEquals("0x90ABCDEF", normalizeSigningKeyId("0x1234567890ABCDEF").value)
        assertEquals("0X90ABCDEF", normalizeSigningKeyId("0X1234567890ABCDEF").value)
    }

    @Test
    fun `축약 대상이 아닌 key id는 trim 외에 변경하지 않는다`() {
        assertEquals("ABCDEF12", normalizeSigningKeyId(" ABCDEF12 ").value)
        assertEquals("1234567890ABCDE", normalizeSigningKeyId("1234567890ABCDE").value)
        assertEquals("1234567890ABCDEF0", normalizeSigningKeyId("1234567890ABCDEF0").value)
        assertEquals("1234567890ABCDEG", normalizeSigningKeyId("1234567890ABCDEG").value)
        assertEquals("", normalizeSigningKeyId("   ").value)
        assertNull(normalizeSigningKeyId("ABCDEF12").warning)
        assertNull(normalizeSigningKeyId("1234567890ABCDEG").warning)
    }

    @Test
    fun `key id warning은 입력 원문을 노출하지 않는 bounded ascii다`() {
        val raw = "1234567890ABCDEF"
        val warning = normalizeSigningKeyId(raw).warning

        assertTrue(warning != null)
        assertFalse(warning.contains(raw))
        assertTrue(warning.toByteArray(Charsets.US_ASCII).size <= 160)
        assertTrue(warning.all { it.code in 0x20..0x7E })
        assertFalse(warning.contains('\u001B'))
    }

    @Test
    fun `raw와 escaped private armor를 정규화한다`() {
        assertEquals(armoredPrivateKey, resolveSigningKey(armoredPrivateKey))
        assertEquals(
            armoredPrivateKey,
            resolveSigningKey(armoredPrivateKey.replace("\n", "\\n")),
        )
    }

    @Test
    fun `strict Base64 private armor만 decode한다`() {
        val encodedArmor = Base64.getEncoder().encodeToString(armoredPrivateKey.toByteArray())
        val encodedText = Base64.getEncoder().encodeToString("not armor".toByteArray())
        val invalidUtf8 = Base64.getEncoder().encodeToString(
            byteArrayOf(0xC3.toByte(), 0x28),
        )

        assertEquals(armoredPrivateKey, resolveSigningKey(encodedArmor))
        assertEquals(armoredPrivateKey, resolveSigningKey("  $encodedArmor  "))
        assertEquals(encodedText, resolveSigningKey(encodedText))
        assertEquals(invalidUtf8, resolveSigningKey(invalidUtf8))
    }

    @Test
    fun `invalid Base64와 blank 입력은 원문으로 fallback한다`() {
        val invalid = "sentinel-secret-is-not-base64!"
        val blank = "   "

        assertEquals(invalid, resolveSigningKey(invalid))
        assertEquals(blank, resolveSigningKey(blank))
    }
}
