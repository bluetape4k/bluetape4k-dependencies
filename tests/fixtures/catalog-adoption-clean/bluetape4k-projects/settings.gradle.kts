val bluetape4kDependenciesCatalogRef = providers.gradleProperty("catalogRef")
    .orElse("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    .get()

require(bluetape4kDependenciesCatalogRef.matches(Regex("[0-9a-f]{40}")))

fun downloadCatalogFile(url: String, target: File, maxBytes: Long) {
    val connection = uri(url).toURL().openConnection()
    connection.connectTimeout = 10_000
    connection.readTimeout = 30_000
}

fun validateCatalogStructure(catalogFile: File) = Unit

fun requireExplicitCatalog(catalogFile: File) {
    require(catalogFile.isFile && !java.nio.file.Files.isSymbolicLink(catalogFile.toPath()))
}
