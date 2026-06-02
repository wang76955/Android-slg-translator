package com.slgtranslator.app

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.util.Base64
import androidx.activity.result.ActivityResult
import androidx.core.content.FileProvider
import com.android.apksig.ApkSigner
import com.android.apksig.ApkVerifier
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.ByteArrayOutputStream
import java.io.ByteArrayInputStream
import java.io.File
import java.io.OutputStream
import java.security.KeyFactory
import java.security.PrivateKey
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.spec.PKCS8EncodedKeySpec
import java.util.zip.DeflaterOutputStream
import java.util.zip.Inflater
import java.util.zip.InflaterInputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

@CapacitorPlugin(name = "FileManager")
class FileManagerPlugin : Plugin() {
    private var pendingInstallAfterUninstallUri: String? = null
    private var pendingInstallAfterUninstallPackage: String? = null

    companion object {
        // 支持扫描的文本文件扩展名
                private val TEXT_EXTENSIONS = setOf(
            "json", "xml", "txt", "csv", "lua", "yaml", "yml",
            "properties", "cfg", "html", "htm", "md", "ini",
            "rpyc", "rpymc", "rpy",  // Ren'Py
            "strings"                 // Android strings
        )
    }

    // ===== 权限 =====
    @PluginMethod
    fun checkPermission(call: PluginCall) {
        call.resolve(JSObject().apply {
            put("granted", if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Environment.isExternalStorageManager() else true)
        })
    }

    @PluginMethod
    fun requestPermission(call: PluginCall) {
        try {
            val ctx = getContext()
            val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                    data = Uri.parse("package:${ctx.packageName}")
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                }
            } else {
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.fromParts("package", ctx.packageName, null)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            }
            ctx.startActivity(intent)
        } catch (_: Exception) {}
        call.resolve(JSObject().apply {
            put("granted", if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Environment.isExternalStorageManager() else true)
        })
    }

    // ===== APK 选择 =====
    @PluginMethod
    fun pickApkFile(call: PluginCall) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            type = "*/*"
            putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("application/vnd.android.package-archive", "application/zip"))
            addCategory(Intent.CATEGORY_OPENABLE)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        try {
            startActivityForResult(call, intent, "onApkPicked")
        } catch (e: Exception) {
            call.reject("Failed: ${e.message}")
        }
    }

    @ActivityCallback
    private fun onApkPicked(call: PluginCall, result: ActivityResult) {
        if (result.resultCode == Activity.RESULT_OK && result.data?.data != null) {
            val uri = result.data!!.data!!
            call.resolve(JSObject().apply { put("uri", uri.toString()) })
        } else {
            call.reject("User cancelled")
        }
    }


    // ===== 自动获取默认输出目录 =====
    @PluginMethod
    fun getDefaultOutputDir(call: PluginCall) {
        try {
            val ctx = getContext()
            val outputDir = java.io.File(ctx.getExternalFilesDir(null), "SLG-Translator-Output")
            if (!outputDir.exists()) {
                outputDir.mkdirs()
            }
            call.resolve(JSObject().apply {
                put("uri", "file://" + outputDir.absolutePath)
                put("path", outputDir.absolutePath)
            })
        } catch (e: Exception) {
            try {
                val ctx = getContext()
                val outputDir = java.io.File(ctx.filesDir, "SLG-Translator-Output")
                if (!outputDir.exists()) {
                    outputDir.mkdirs()
                }
                call.resolve(JSObject().apply {
                    put("uri", "file://" + outputDir.absolutePath)
                    put("path", outputDir.absolutePath)
                })
            } catch (e2: Exception) {
                call.reject("Failed to get output dir: " + e2.message)
            }
        }
    }

    // ===== 选择输出目录 =====
    @PluginMethod
    fun pickOutputDir(call: PluginCall) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
        try {
            startActivityForResult(call, intent, "onDirPicked")
        } catch (e: Exception) {
            call.reject("Failed: ${e.message}")
        }
    }

    @ActivityCallback
    private fun onDirPicked(call: PluginCall, result: ActivityResult) {
        if (result.resultCode == Activity.RESULT_OK && result.data?.data != null) {
            val uri = result.data!!.data!!
            try {
                val takeFlags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                getContext().contentResolver.takePersistableUriPermission(uri, takeFlags)
            } catch (_: Exception) {}
            call.resolve(JSObject().apply { put("uri", uri.toString()) })
        } else {
            call.reject("User cancelled")
        }
    }

    // ===== 扫描 APK 内文件 =====
    @PluginMethod
    fun listApkEntries(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        try {
            val ctx = getContext()
            val zipStream = ZipInputStream(ctx.contentResolver.openInputStream(Uri.parse(uriStr)))
            val entries = JSArray()
            var entry: ZipEntry? = zipStream.nextEntry
            while (entry != null) {
                if (!entry.isDirectory) {
                    val ext = entry.name.substringAfterLast('.', "").lowercase()
                    if (ext in TEXT_EXTENSIONS || isLikelyTextFile(entry.name)) {
                        val fileType = detectFileType(entry.name, ext)
                        entries.put(JSObject().apply {
                            put("name", entry.name)
                            put("size", entry.size)
                            put("compressedSize", entry.compressedSize)
                            put("fileType", fileType)
                        })
                    }
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }
            zipStream.close()
            call.resolve(JSObject().apply {
                put("entries", entries)
                put("totalFiles", entries.length())
            })
        } catch (e: Exception) {
            call.reject("Failed to read APK: ${e.message}")
        }
    }

    private fun detectFileType(name: String, ext: String): String {
        return when (ext) {
            "json" -> "json"
            "xml" -> "xml"
            "rpyc", "rpymc" -> "rpyc"
            "csv", "tsv" -> "csv"
            "yaml", "yml" -> "yaml"
            "properties" -> "properties"
            "lua" -> "lua"
            "html", "htm" -> "html"
            "md" -> "markdown"
            "ini", "cfg" -> "ini"
            "txt" -> "text"
            "strings" -> "strings"
            "bytes" -> "bytes"
            "dat" -> "dat"
            "rpy" -> "rpy" // Ren'Py 源码
            else -> "unknown"
        }
    }

    private fun isLikelyTextFile(name: String): Boolean {
        // 跳过已知的二进制/媒体文件扩展名
        val binaryExts = setOf("png", "jpg", "jpeg", "gif", "webp", "bmp", "ico",
                               "mp3", "wav", "ogg", "aac", "flac", "m4a",
                               "mp4", "webm", "avi", "mkv", "mov",
                               "ttf", "otf", "woff", "woff2", "eot",
                               "so", "dll", "dex", "oat", "vdex")
        val ext = name.substringAfterLast('.', "").lowercase()
        if (ext in binaryExts) return false

        // 对无扩展名或非标准扩展名的文件进行内容试探
        val baseName = name.substringAfterLast('/').substringBeforeLast('.')
        return baseName.contains("text") || baseName.contains("string") ||
               baseName.contains("dialogue") || baseName.contains("script") ||
               name.endsWith(".txt", ignoreCase = true)
    }

    // ===== 读取文件内容 =====
    @PluginMethod
    fun readFileContent(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        val entryName = call.getString("entryName") ?: run { call.reject("entryName required"); return }
        try {
            val ctx = getContext()
            val zipStream = ZipInputStream(ctx.contentResolver.openInputStream(Uri.parse(uriStr)))
            var found = false
            var content = ""
            var fileType = "unknown"
            var entry: ZipEntry? = zipStream.nextEntry
            while (entry != null) {
                if (entry.name == entryName) {
                    found = true
                    val ext = entry.name.substringAfterLast('.', "").lowercase()
                    fileType = detectFileType(entry.name, ext)

                    content = when (fileType) {
                        "rpyc" -> readRpycContent(zipStream, entry)
                        else -> zipStream.bufferedReader(Charsets.UTF_8).readText()
                    }
                    break
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }
            zipStream.close()
            if (!found) { call.reject("Entry not found: $entryName"); return }
            call.resolve(JSObject().apply {
                put("content", content)
                put("fileType", fileType)
                put("fileExt", entryName.substringAfterLast('.', "").lowercase())
            })
        } catch (e: Exception) {
            call.reject("Failed to read entry: ${e.message}")
        }
    }

    /**
     * 读取 Ren'Py RPC2 格式的 rpyc 文件，解压后提取可读字符串
     */
    private fun readRpycContent(stream: ZipInputStream, entry: ZipEntry): String {
        // 读取整个文件的字节数据
        val allBytes = stream.readBytes()
        return parseRpyc(allBytes)
    }

    private fun parseRpyc(data: ByteArray): String {
        val magic = "RENPY RPC2".toByteArray(Charsets.US_ASCII)
        if (data.size < magic.size || !data.copyOfRange(0, magic.size).contentEquals(magic)) {
            // 不是标准的 RPC2 格式，尝试直接读 UTF-8 文本
            return data.toString(Charsets.UTF_8)
        }

        val hdrLen = magic.size // 10 bytes
        val decompressed = ByteArrayOutputStream()

        // 读取 slot 表并解压每个 slot
        var slotPos = hdrLen
        while (slotPos + 12 <= data.size) {
            val slotNum = byteArrayToInt(data, slotPos)
            if (slotNum == 0 || slotNum > 100) break

            val offset = byteArrayToInt(data, slotPos + 4)
            val compSize = byteArrayToInt(data, slotPos + 8)

            if (offset + compSize > data.size) break

            try {
                val compressed = data.copyOfRange(offset, offset + compSize)
                val decompressedBytes = zlibDecompress(compressed)
                decompressed.write(decompressedBytes)
            } catch (_: Exception) {
                // 解压失败，跳过此 slot
            }

            slotPos += 12
        }

        if (decompressed.size() == 0) {
            // 解压失败，返回原始数据（可能不是标准的 RPC2）
            return data.toString(Charsets.UTF_8)
        }

        return extractPickleStrings(decompressed.toByteArray()).joinToString("\n") { "RPYC_STRING\t$it" }
    }

    private fun extractPickleStrings(data: ByteArray): List<String> {
        val result = linkedSetOf<String>()
        var index = 0

        while (index < data.size) {
            when (data[index].toInt() and 0xFF) {
                0x55 -> {
                    val length = data.getOrNull(index + 1)?.toInt()?.and(0xFF) ?: 0
                    readPickleString(data, index + 2, length)?.let { result.add(it) }
                    index += 2 + length
                }
                0x8C -> {
                    val length = data.getOrNull(index + 1)?.toInt()?.and(0xFF) ?: 0
                    readPickleString(data, index + 2, length)?.let { result.add(it) }
                    index += 2 + length
                }
                0x58, 0x42 -> {
                    if (index + 5 <= data.size) {
                        val length = byteArrayToInt(data, index + 1)
                        readPickleString(data, index + 5, length)?.let { result.add(it) }
                        index += 5 + length
                    } else {
                        index += 1
                    }
                }
                0x8D, 0x8E -> {
                    if (index + 9 <= data.size) {
                        val length = byteArrayToLong(data, index + 1)
                        if (length in 0..1_000_000) {
                            readPickleString(data, index + 9, length.toInt())?.let { result.add(it) }
                            index += 9 + length.toInt()
                        } else {
                            index += 1
                        }
                    } else {
                        index += 1
                    }
                }
                else -> index += 1
            }
        }

        return result.filter { isLikelyVisibleRenPyString(it) }
    }

    private fun readPickleString(data: ByteArray, offset: Int, length: Int): String? {
        if (length <= 0 || length > 20_000 || offset < 0 || offset + length > data.size) return null
        return try {
            data.copyOfRange(offset, offset + length).toString(Charsets.UTF_8).trim()
        } catch (_: Exception) {
            null
        }
    }

    private fun byteArrayToLong(data: ByteArray, offset: Int): Long {
        var value = 0L
        for (i in 0 until 8) {
            value = value or ((data[offset + i].toLong() and 0xFFL) shl (8 * i))
        }
        return value
    }

    private fun isLikelyVisibleRenPyString(text: String): Boolean {
        if (text.length < 2) return false
        if (text.any { it.code < 9 || (it.code in 14..31) }) return false
        if (text.matches(Regex("^[A-Za-z_][A-Za-z0-9_./:-]*$"))) return false
        if (text.matches(Regex("^[-+]?\\d+(?:\\.\\d+)?$"))) return false
        if (text.contains("/") && text.matches(Regex("^[A-Za-z0-9_./ -]+$"))) return false
        if (text.matches(Regex(".*\\.(rpy|rpyc|rpym|py|png|jpg|jpeg|webp|ogg|mp3|wav|ttf|otf|json|xml)$", RegexOption.IGNORE_CASE))) return false
        return true
    }

    private fun byteArrayToInt(data: ByteArray, offset: Int): Int {
        return ((data[offset].toInt() and 0xFF) shl 0) or
               ((data[offset + 1].toInt() and 0xFF) shl 8) or
               ((data[offset + 2].toInt() and 0xFF) shl 16) or
               ((data[offset + 3].toInt() and 0xFF) shl 24)
    }

    private fun zlibDecompress(data: ByteArray): ByteArray {
        val inflater = Inflater()
        inflater.setInput(data)
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        try {
            while (!inflater.finished()) {
                val count = inflater.inflate(buffer)
                output.write(buffer, 0, count)
            }
        } finally {
            inflater.end()
        }
        return output.toByteArray()
    }

    // ===== 向后兼容：旧 API =====
    @PluginMethod
    fun listApkEntriesLegacy(call: PluginCall) {
        // 兼容旧代码
        listApkEntries(call)
    }

    @PluginMethod
    fun readApkEntry(call: PluginCall) {
        // 使用新方法读取
        readFileContent(call)
    }

    // ===== 文件写入 =====
    @PluginMethod
    fun writeFileToDir(call: PluginCall) {
        val dirUri = call.getString("dirUri") ?: run { call.reject("dirUri required"); return }
        val fileName = call.getString("fileName") ?: run { call.reject("fileName required"); return }
        val content = call.getString("content") ?: run { call.reject("content required"); return }
        try {
            val ctx = getContext()
            val uri = Uri.parse(dirUri)
            var success = false

            if (dirUri.startsWith("file:")) {
                val parentDir = java.io.File(uri.path!!)
                if (!parentDir.exists()) parentDir.mkdirs()
                val outFile = java.io.File(parentDir, fileName)
                val parent = outFile.parentFile
                if (parent != null && !parent.exists()) parent.mkdirs()
                outFile.writeBytes(content.toByteArray(Charsets.UTF_8))
                success = true
            } else {
                val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, uri)
                val newFile = docFile?.createFile("application/octet-stream", fileName)
                if (newFile != null) {
                    ctx.contentResolver.openOutputStream(newFile.uri)?.use { it.write(content.toByteArray(Charsets.UTF_8)) }
                    success = true
                }
            }
            call.resolve(JSObject().apply { put("success", success) })
        } catch (e: Exception) {
            call.reject("Failed to write: ${e.message}")
        }
    }

    @PluginMethod
    fun buildPatchedApk(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        val files = call.getArray("files") ?: run { call.reject("files required"); return }
        val outputDirUri = call.getString("outputDirUri")
        val outputName = sanitizeFileName(
            (call.getString("outputName") ?: "translated-patched-signed.apk")
                .replace("-unsigned", "-signed", ignoreCase = true)
        )
        val targetRenpyLanguage = call.getString("targetRenpyLanguage")
            ?.trim()
            ?.takeIf { it.isNotBlank() && !it.equals("None", ignoreCase = true) }
        val sourceRenpyLanguage = call.getString("sourceRenpyLanguage")
            ?.trim()
            ?.takeIf { it.isNotBlank() }

        val patchFiles = linkedMapOf<String, ByteArray>()
        try {
            for (index in 0 until files.length()) {
                val item = files.getJSONObject(index)
                val path = normalizeZipEntryPath(item.optString("path", ""))
                if (path.isBlank()) continue
                patchFiles[path] = item.optString("content", "").toByteArray(Charsets.UTF_8)
            }

            if (patchFiles.isEmpty() && targetRenpyLanguage.isNullOrBlank()) {
                call.reject("No patch files")
                return
            }

            val ctx = getContext()
            val sourceFile = File.createTempFile("slg-source-", ".apk", ctx.cacheDir)
            val unsignedFile = File.createTempFile("slg-patched-unsigned-", ".apk", ctx.cacheDir)
            val signedFile = File.createTempFile("slg-patched-signed-", ".apk", ctx.cacheDir)
            try {
                ctx.contentResolver.openInputStream(Uri.parse(uriStr))?.use { input ->
                    sourceFile.outputStream().use { output -> input.copyTo(output) }
                } ?: run {
                    call.reject("Failed to open source APK")
                    return
                }

                var copiedCount = 0
                var skippedSignatureCount = 0
                var replacedCount = 0
                var mirroredRenpyCount = 0

                ZipFile(sourceFile).use { zipFile ->
                    val countingOutput = CountingOutputStream(unsignedFile.outputStream().buffered())
                    ZipOutputStream(countingOutput).use { zipOut ->
                        val copiedNames = hashSetOf<String>()
                        val renpyMirrorPaths = collectRenpyMirrorPaths(zipFile, targetRenpyLanguage, sourceRenpyLanguage)
                        val entries = zipFile.entries()

                        while (entries.hasMoreElements()) {
                            val entry = entries.nextElement()
                            val normalizedName = normalizeZipEntryPath(entry.name)

                            if (normalizedName.isBlank() || normalizedName.startsWith("META-INF/", ignoreCase = true)) {
                                skippedSignatureCount++
                                continue
                            }

                            if (!entry.isDirectory && patchFiles.containsKey(normalizedName)) {
                                replacedCount++
                                continue
                            }

                            if (!entry.isDirectory && shouldDropRenpySourceTranslation(normalizedName, targetRenpyLanguage, sourceRenpyLanguage)) {
                                replacedCount++
                                continue
                            }

                            if (!entry.isDirectory && shouldDropRenpyMirrorCompiled(normalizedName, targetRenpyLanguage, sourceRenpyLanguage)) {
                                replacedCount++
                                continue
                            }

                            if (!entry.isDirectory && renpyMirrorPaths.contains(normalizedName)) {
                                replacedCount++
                                continue
                            }

                            if (!copiedNames.add(normalizedName)) continue

                            val originalBytes = if (!entry.isDirectory) {
                                zipFile.getInputStream(entry).use { input -> input.readBytes() }
                            } else {
                                ByteArray(0)
                            }
                            val entryBytes = if (!entry.isDirectory) {
                                rewriteRenpyDefaultLanguageSelection(normalizedName, originalBytes, targetRenpyLanguage)
                            } else {
                                originalBytes
                            }

                            val outEntry = ZipEntry(normalizedName)
                            outEntry.time = entry.time
                            outEntry.comment = entry.comment
                            outEntry.extra = if (normalizedName == "resources.arsc") {
                                buildZipAlignmentExtra(countingOutput.bytesWritten, normalizedName, 4)
                            } else {
                                entry.extra
                            }

                            if (entry.method == ZipEntry.STORED && entryBytes.contentEquals(originalBytes)) {
                                outEntry.method = ZipEntry.STORED
                                outEntry.size = entry.size
                                outEntry.compressedSize = entry.compressedSize
                                outEntry.crc = entry.crc
                            }

                            zipOut.putNextEntry(outEntry)
                            if (!entry.isDirectory) {
                                zipOut.write(entryBytes)
                                copiedCount++
                            }
                            zipOut.closeEntry()

                            val mirrorPaths = buildRenpyMirrorPaths(normalizedName, targetRenpyLanguage, sourceRenpyLanguage)
                            for (mirrorPath in mirrorPaths) {
                                if (!entry.isDirectory && copiedNames.add(mirrorPath)) {
                                    val mirrorEntry = ZipEntry(mirrorPath)
                                    mirrorEntry.time = entry.time
                                    mirrorEntry.comment = entry.comment
                                    mirrorEntry.extra = entry.extra
                                    zipOut.putNextEntry(mirrorEntry)
                                    val mirrorBytes = zipFile.getInputStream(entry).use { input -> input.readBytes() }
                                    val outputBytes = rewriteRenpyCompiledLanguageForMirror(
                                        normalizedName,
                                        mirrorPath,
                                        mirrorBytes,
                                        targetRenpyLanguage
                                    )
                                    zipOut.write(outputBytes)
                                    zipOut.closeEntry()
                                    mirroredRenpyCount++
                                }
                            }
                        }

                        for ((path, bytes) in patchFiles) {
                            val outEntry = ZipEntry(path)
                            outEntry.time = System.currentTimeMillis()
                            zipOut.putNextEntry(outEntry)
                            zipOut.write(bytes)
                            zipOut.closeEntry()
                        }
                    }
                }

                signApk(unsignedFile, signedFile)
                val signatureInfo = verifyApkSignature(signedFile)
                val result = writeSignedApkOutput(outputDirUri, outputName, signedFile)

                call.resolve(JSObject().apply {
                    put("success", true)
                    put("uri", result.uri)
                    put("path", result.path)
                    put("fileCount", patchFiles.size)
                    put("copiedCount", copiedCount)
                    put("replacedCount", replacedCount)
                    put("mirroredRenpyCount", mirroredRenpyCount)
                    put("skippedSignatureCount", skippedSignatureCount)
                    put("unsigned", false)
                    put("signed", true)
                    put("signatureVerified", signatureInfo.verified)
                    put("verifiedUsingV1", signatureInfo.v1)
                    put("verifiedUsingV2", signatureInfo.v2)
                    put("verifiedUsingV3", signatureInfo.v3)
                })
            } finally {
                sourceFile.delete()
                unsignedFile.delete()
                signedFile.delete()
            }
        } catch (e: Exception) {
            call.reject("Failed to build patched APK: ${e.message}")
        }
    }

    @PluginMethod
    fun installApk(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        launchApkInstaller(call, uriStr)
    }

    @PluginMethod
    fun uninstallAndInstallApk(call: PluginCall) {
        val packageName = call.getString("packageName") ?: run { call.reject("packageName required"); return }
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }

        if (!isPackageInstalled(packageName)) {
            launchApkInstaller(call, uriStr)
            return
        }

        try {
            pendingInstallAfterUninstallUri = uriStr
            pendingInstallAfterUninstallPackage = packageName
            val intent = Intent(Intent.ACTION_DELETE).apply {
                data = Uri.parse("package:$packageName")
            }
            startActivityForResult(call, intent, "onUninstallBeforeInstallFinished")
        } catch (e: Exception) {
            pendingInstallAfterUninstallUri = null
            pendingInstallAfterUninstallPackage = null
            call.reject("Failed to launch APK uninstaller: ${e.message}")
        }
    }

    @ActivityCallback
    private fun onUninstallBeforeInstallFinished(call: PluginCall, result: ActivityResult) {
        val packageName = pendingInstallAfterUninstallPackage
        val uriStr = pendingInstallAfterUninstallUri
        pendingInstallAfterUninstallPackage = null
        pendingInstallAfterUninstallUri = null

        if (packageName.isNullOrBlank() || uriStr.isNullOrBlank()) {
            call.reject("Missing pending APK install")
            return
        }

        if (isPackageInstalled(packageName)) {
            call.resolve(JSObject().apply {
                put("success", false)
                put("uninstallCancelled", true)
            })
            return
        }

        launchApkInstaller(call, uriStr)
    }

    private fun launchApkInstaller(call: PluginCall, uriStr: String) {
        try {
            val ctx = getContext()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !ctx.packageManager.canRequestPackageInstalls()) {
                val settingsIntent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                    data = Uri.parse("package:${ctx.packageName}")
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                ctx.startActivity(settingsIntent)
                call.resolve(JSObject().apply {
                    put("success", false)
                    put("needsPermission", true)
                })
                return
            }

            val apkUri = toInstallableApkUri(uriStr)
            val installIntent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(apkUri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
                putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true)
            }
            ctx.startActivity(installIntent)
            call.resolve(JSObject().apply {
                put("success", true)
                put("needsPermission", false)
            })
        } catch (e: Exception) {
            call.reject("Failed to launch APK installer: ${e.message}")
        }
    }

    @PluginMethod
    fun createDirectory(call: PluginCall) {
        val dirUri = call.getString("dirUri") ?: run { call.reject("dirUri required"); return }
        val dirName = call.getString("dirName") ?: run { call.reject("dirName required"); return }
        try {
            val ctx = getContext()
            val uri = Uri.parse(dirUri)
            var success = false
            var resultUri = ""

            if (dirUri.startsWith("file:")) {
                val parentDir = java.io.File(uri.path!!)
                val newDir = java.io.File(parentDir, dirName)
                success = newDir.mkdirs() || newDir.exists()
                resultUri = "file://" + java.io.File(parentDir, dirName).absolutePath
            } else {
                val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, uri)
                val created = docFile?.createDirectory(dirName)
                success = created != null
                resultUri = created?.uri?.toString() ?: ""
            }
            call.resolve(JSObject().apply {
                put("success", success)
                put("uri", resultUri)
            })
        } catch (e: Exception) {
            call.reject("Failed to create dir: ${e.message}")
        }
    }

    private data class ApkOutput(
        val uri: String,
        val path: String
    )

    private data class SignatureInfo(
        val verified: Boolean,
        val v1: Boolean,
        val v2: Boolean,
        val v3: Boolean
    )

    private fun writeSignedApkOutput(outputDirUri: String?, outputName: String, signedFile: File): ApkOutput {
        val ctx = getContext()
        if (!outputDirUri.isNullOrBlank()) {
            val uri = Uri.parse(outputDirUri)
            if (outputDirUri.startsWith("file:")) {
                val parentDir = File(uri.path!!)
                if (!parentDir.exists()) parentDir.mkdirs()
                val outFile = File(parentDir, outputName)
                signedFile.inputStream().use { input ->
                    outFile.outputStream().use { output -> input.copyTo(output) }
                }
                return ApkOutput("file://" + outFile.absolutePath, outFile.absolutePath)
            }

            val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, uri)
            docFile?.findFile(outputName)?.delete()
            val newFile = docFile?.createFile("application/vnd.android.package-archive", outputName)
                ?: throw IllegalStateException("Cannot create output APK")
            val stream = ctx.contentResolver.openOutputStream(newFile.uri)
                ?: throw IllegalStateException("Cannot open output APK")
            stream.use { output ->
                signedFile.inputStream().use { input -> input.copyTo(output) }
            }
            return ApkOutput(newFile.uri.toString(), outputName)
        }

        val outputDir = File(ctx.getExternalFilesDir(null), "SLG-Translator-Output")
        if (!outputDir.exists()) outputDir.mkdirs()
        val outFile = File(outputDir, outputName)
        signedFile.inputStream().use { input ->
            outFile.outputStream().use { output -> input.copyTo(output) }
        }
        return ApkOutput("file://" + outFile.absolutePath, outFile.absolutePath)
    }

    private fun signApk(inputApk: File, outputApk: File) {
        val privateKey = loadDebugPrivateKey()
        val certificate = loadDebugCertificate()
        val signerConfig = ApkSigner.SignerConfig.Builder(
            "SLG_TRANSLATOR",
            privateKey,
            listOf(certificate)
        ).build()

        ApkSigner.Builder(listOf(signerConfig))
            .setInputApk(inputApk)
            .setOutputApk(outputApk)
            .setMinSdkVersion(21)
            .setV1SigningEnabled(true)
            .setV2SigningEnabled(true)
            .setV3SigningEnabled(true)
            .setV4SigningEnabled(false)
            .setOtherSignersSignaturesPreserved(false)
            .setCreatedBy("SLG Translator Android")
            .build()
            .sign()
    }

    private fun verifyApkSignature(apkFile: File): SignatureInfo {
        val result = ApkVerifier.Builder(apkFile)
            .setMinCheckedPlatformVersion(Build.VERSION_CODES.N)
            .build()
            .verify()
        return SignatureInfo(
            verified = result.isVerified,
            v1 = result.isVerifiedUsingV1Scheme,
            v2 = result.isVerifiedUsingV2Scheme,
            v3 = result.isVerifiedUsingV3Scheme,
        )
    }

    private fun toInstallableApkUri(uriStr: String): Uri {
        val ctx = getContext()
        val uri = Uri.parse(uriStr)
        if (uri.scheme == "file") {
            val file = File(uri.path ?: throw IllegalArgumentException("Invalid file uri"))
            return FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", file)
        }
        return uri
    }

    private fun loadDebugPrivateKey(): PrivateKey {
        val keyBytes = decodePem(DEBUG_PRIVATE_KEY_PEM)
        return KeyFactory.getInstance("RSA").generatePrivate(PKCS8EncodedKeySpec(keyBytes))
    }

    private fun loadDebugCertificate(): X509Certificate {
        val certBytes = decodePem(DEBUG_CERTIFICATE_PEM)
        return CertificateFactory.getInstance("X.509")
            .generateCertificate(certBytes.inputStream()) as X509Certificate
    }

    private fun decodePem(pem: String): ByteArray {
        val base64Text = pem
            .replace(Regex("-----BEGIN [^-]+-----"), "")
            .replace(Regex("-----END [^-]+-----"), "")
            .replace(Regex("\\s+"), "")
        return Base64.decode(base64Text, Base64.DEFAULT)
    }

    private fun sanitizeFileName(name: String): String {
        return name
            .replace(Regex("[\\\\/:*?\"<>|\\r\\n]+"), "_")
            .ifBlank { "translated-patched-unsigned.apk" }
            .let { if (it.endsWith(".apk", ignoreCase = true)) it else "$it.apk" }
    }

    private fun collectRenpyMirrorPaths(
        zipFile: ZipFile,
        targetRenpyLanguage: String?,
        sourceRenpyLanguage: String?,
    ): Set<String> {
        if (targetRenpyLanguage.isNullOrBlank()) return emptySet()

        val paths = hashSetOf<String>()
        val entries = zipFile.entries()
        while (entries.hasMoreElements()) {
            val entry = entries.nextElement()
            if (entry.isDirectory) continue
            paths.addAll(buildRenpyMirrorPaths(normalizeZipEntryPath(entry.name), targetRenpyLanguage, sourceRenpyLanguage))
        }
        return paths
    }

    private fun buildRenpyMirrorPaths(
        path: String,
        targetRenpyLanguage: String?,
        sourceRenpyLanguage: String?,
    ): Set<String> {
        if (path.isBlank() || targetRenpyLanguage.isNullOrBlank()) return emptySet()
        if (path.endsWith(".rpym", ignoreCase = true)) return emptySet()

        val parts = path.split("/").toMutableList()
        val tlIndex = parts.indexOfFirst { it == "tl" || it == "x-tl" }
        if (tlIndex < 0 || tlIndex + 1 >= parts.size) return emptySet()

        val languageDir = parts[tlIndex + 1]
        val expectedLanguageDir = if (languageDir.startsWith("x-")) {
            "x-$targetRenpyLanguage"
        } else {
            targetRenpyLanguage
        }
        if (!languageDir.equals(expectedLanguageDir, ignoreCase = true)) return emptySet()

        val mirroredLanguages = linkedSetOf("None")
        if (!sourceRenpyLanguage.isNullOrBlank()) mirroredLanguages.add(sourceRenpyLanguage)

        return mirroredLanguages.mapNotNullTo(linkedSetOf()) { mirroredLanguage ->
            if (mirroredLanguage.equals(targetRenpyLanguage, ignoreCase = true)) return@mapNotNullTo null
            if (isRenpyScriptModule(path) && mirroredLanguage.equals("None", ignoreCase = true)) {
                return@mapNotNullTo null
            }
            val mirroredParts = parts.toMutableList()
            mirroredParts[tlIndex + 1] = if (languageDir.startsWith("x-")) "x-$mirroredLanguage" else mirroredLanguage
            mirroredParts.joinToString("/")
        }
    }

    private fun shouldDropRenpySourceTranslation(
        path: String,
        targetRenpyLanguage: String?,
        sourceRenpyLanguage: String?,
    ): Boolean {
        val isRpy = path.endsWith(".rpy", ignoreCase = true)
        val isRpym = path.endsWith(".rpym", ignoreCase = true)
        if (!isRpy && !isRpym) return false
        if (targetRenpyLanguage.isNullOrBlank()) return false

        val parts = path.split("/")
        val tlIndex = parts.indexOfFirst { it == "tl" || it == "x-tl" }
        if (tlIndex < 0 || tlIndex + 1 >= parts.size) return false

        val languageDir = parts[tlIndex + 1]
        val hasPrefix = languageDir.startsWith("x-")
        if (isRpym) {
            return languageDir.equals(if (hasPrefix) "x-None" else "None", ignoreCase = true)
        }

        val languagesToClean = linkedSetOf("None", targetRenpyLanguage)
        if (!sourceRenpyLanguage.isNullOrBlank()) languagesToClean.add(sourceRenpyLanguage)

        return languagesToClean.any { language ->
            val expectedDir = if (hasPrefix) "x-$language" else language
            languageDir.equals(expectedDir, ignoreCase = true)
        }
    }

    private fun shouldDropRenpyMirrorCompiled(
        path: String,
        targetRenpyLanguage: String?,
        sourceRenpyLanguage: String?,
    ): Boolean {
        if (!isRenpyScriptModule(path)) return false
        if (targetRenpyLanguage.isNullOrBlank()) return false

        val language = getRenpyLanguageFromPath(path) ?: return false
        if (language.equals(targetRenpyLanguage, ignoreCase = true)) return false
        if (!sourceRenpyLanguage.isNullOrBlank() && language.equals(sourceRenpyLanguage, ignoreCase = true)) return false

        return language.equals("None", ignoreCase = true)
    }

    private fun rewriteRenpyCompiledLanguageForMirror(
        sourcePath: String,
        mirrorPath: String,
        bytes: ByteArray,
        targetRenpyLanguage: String?,
    ): ByteArray {
        if (!isRenpyCompiledTranslation(sourcePath)) return bytes
        if (targetRenpyLanguage.isNullOrBlank()) return bytes

        val mirrorLanguage = getRenpyLanguageFromPath(mirrorPath) ?: return bytes
        if (mirrorLanguage.equals("None", ignoreCase = true)) return bytes
        if (mirrorLanguage.equals(targetRenpyLanguage, ignoreCase = true)) return bytes

        return rewriteRenpyRpc2Language(bytes, targetRenpyLanguage, mirrorLanguage)
    }

    private fun rewriteRenpyDefaultLanguageSelection(
        path: String,
        bytes: ByteArray,
        targetRenpyLanguage: String?,
    ): ByteArray {
        if (targetRenpyLanguage.isNullOrBlank()) return bytes
        if (!path.endsWith(".rpyc", ignoreCase = true) && !path.endsWith(".rpymc", ignoreCase = true)) return bytes
        val parts = path.split("/")
        val tlIndex = parts.indexOfFirst { it == "tl" || it == "x-tl" }
        if (tlIndex >= 0) return bytes

        val targetExpression = "Language(\"$targetRenpyLanguage\")"
        return rewriteRenpyRpc2Text(bytes) { text ->
            if (text == "Language(None)") targetExpression else text
        }
    }

    private fun isRenpyCompiledTranslation(path: String): Boolean {
        val lowerPath = path.lowercase()
        if (!lowerPath.endsWith(".rpyc") && !lowerPath.endsWith(".rpymc")) return false
        val parts = path.split("/")
        val tlIndex = parts.indexOfFirst { it == "tl" || it == "x-tl" }
        return tlIndex >= 0 && tlIndex + 1 < parts.size
    }

    private fun isRenpyScriptModule(path: String): Boolean {
        val lowerPath = path.lowercase()
        if (!lowerPath.endsWith(".rpy") &&
            !lowerPath.endsWith(".rpyc") &&
            !lowerPath.endsWith(".rpym") &&
            !lowerPath.endsWith(".rpymc")
        ) {
            return false
        }
        val parts = path.split("/")
        val tlIndex = parts.indexOfFirst { it == "tl" || it == "x-tl" }
        return tlIndex >= 0 && tlIndex + 1 < parts.size
    }

    private fun getRenpyLanguageFromPath(path: String): String? {
        val parts = path.split("/")
        val tlIndex = parts.indexOfFirst { it == "tl" || it == "x-tl" }
        if (tlIndex < 0 || tlIndex + 1 >= parts.size) return null
        return parts[tlIndex + 1].removePrefix("x-")
    }

    private data class RenpyRpc2Slot(val id: Int, val offset: Int, val length: Int)

    private fun rewriteRenpyRpc2Language(bytes: ByteArray, fromLanguage: String, toLanguage: String): ByteArray {
        return rewriteRenpyRpc2Text(bytes) { text ->
            rewriteRenpyPickleText(text, fromLanguage, toLanguage)
        }
    }

    private fun rewriteRenpyRpc2Text(bytes: ByteArray, transform: (String) -> String): ByteArray {
        val magic = "RENPY RPC2".toByteArray(Charsets.US_ASCII)
        if (bytes.size < magic.size + 12 || !bytes.copyOfRange(0, magic.size).contentEquals(magic)) return bytes

        val slots = mutableListOf<RenpyRpc2Slot>()
        var headerEnd = magic.size
        while (headerEnd + 12 <= bytes.size) {
            val id = readIntLe(bytes, headerEnd)
            val offset = readIntLe(bytes, headerEnd + 4)
            val length = readIntLe(bytes, headerEnd + 8)
            headerEnd += 12
            if (id == 0) break
            if (offset < 0 || length < 0 || offset + length > bytes.size) return bytes
            slots.add(RenpyRpc2Slot(id, offset, length))
        }
        if (slots.isEmpty()) return bytes

        val trailerStart = slots.maxOf { it.offset + it.length }
        val trailer = if (trailerStart < bytes.size) bytes.copyOfRange(trailerStart, bytes.size) else ByteArray(0)
        val rewrittenSlots = slots.map { slot ->
            val compressed = bytes.copyOfRange(slot.offset, slot.offset + slot.length)
            val decompressed = try {
                InflaterInputStream(ByteArrayInputStream(compressed)).use { it.readBytes() }
            } catch (_: Exception) {
                return bytes
            }
            val rewritten = rewritePickleUnicodeStrings(decompressed, transform)
            val recompressed = ByteArrayOutputStream().use { output ->
                DeflaterOutputStream(output).use { it.write(rewritten) }
                output.toByteArray()
            }
            slot.id to recompressed
        }

        val rebuilt = ByteArrayOutputStream()
        rebuilt.write(magic)
        var nextOffset = magic.size + (slots.size + 1) * 12
        for ((id, data) in rewrittenSlots) {
            writeIntLe(rebuilt, id)
            writeIntLe(rebuilt, nextOffset)
            writeIntLe(rebuilt, data.size)
            nextOffset += data.size
        }
        writeIntLe(rebuilt, 0)
        writeIntLe(rebuilt, 0)
        writeIntLe(rebuilt, 0)
        for ((_, data) in rewrittenSlots) rebuilt.write(data)
        rebuilt.write(trailer)
        return rebuilt.toByteArray()
    }

    private fun rewritePickleUnicodeStrings(bytes: ByteArray, fromLanguage: String, toLanguage: String): ByteArray {
        return rewritePickleUnicodeStrings(bytes) { text ->
            rewriteRenpyPickleText(text, fromLanguage, toLanguage)
        }
    }

    private fun rewritePickleUnicodeStrings(bytes: ByteArray, transform: (String) -> String): ByteArray {
        return rewritePickleUnicodeStringsRange(bytes, 0, bytes.size, transform)
    }

    private fun rewritePickleUnicodeStringsRange(
        bytes: ByteArray,
        startIndex: Int,
        endIndex: Int,
        transform: (String) -> String
    ): ByteArray {
        val output = ByteArrayOutputStream(endIndex - startIndex)
        var index = startIndex
        while (index < endIndex) {
            val opcode = bytes[index].toInt() and 0xff
            when (opcode) {
                0x95 -> {
                    if (index + 9 > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    val length = readLongLe(bytes, index + 1)
                    val frameStart = index + 9
                    val frameEnd = frameStart + length.toInt()
                    if (length < 0 || length > Int.MAX_VALUE || frameEnd > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    val rewrittenFrame = rewritePickleUnicodeStringsRange(
                        bytes,
                        frameStart,
                        frameEnd,
                        transform
                    )
                    output.write(0x95)
                    writeLongLe(output, rewrittenFrame.size.toLong())
                    output.write(rewrittenFrame)
                    index = frameEnd
                }
                0x8c -> {
                    if (index + 2 > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    val length = bytes[index + 1].toInt() and 0xff
                    val start = index + 2
                    val end = start + length
                    if (end > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    writePickleUnicode(output, transform(String(bytes, start, length, Charsets.UTF_8)))
                    index = end
                }
                0x58 -> {
                    if (index + 5 > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    val length = readIntLe(bytes, index + 1)
                    val start = index + 5
                    val end = start + length
                    if (length < 0 || end > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    writePickleUnicode(output, transform(String(bytes, start, length, Charsets.UTF_8)))
                    index = end
                }
                0x8d -> {
                    if (index + 9 > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    val length = readLongLe(bytes, index + 1)
                    val start = index + 9
                    val end = start + length.toInt()
                    if (length < 0 || length > Int.MAX_VALUE || end > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    writePickleUnicode(output, transform(String(bytes, start, length.toInt(), Charsets.UTF_8)))
                    index = end
                }
                else -> {
                    val nextIndex = nextPickleOpcodeIndex(bytes, index)
                    if (nextIndex <= index || nextIndex > endIndex) {
                        output.write(bytes, index, endIndex - index)
                        break
                    }
                    output.write(bytes, index, nextIndex - index)
                    index = nextIndex
                }
            }
        }
        return output.toByteArray()
    }

    private fun writePickleUnicode(output: ByteArrayOutputStream, text: String) {
        val data = text.toByteArray(Charsets.UTF_8)
        if (data.size <= 0xff) {
            output.write(0x8c)
            output.write(data.size)
        } else {
            output.write(0x58)
            writeIntLe(output, data.size)
        }
        output.write(data)
    }

    private fun nextPickleOpcodeIndex(bytes: ByteArray, index: Int): Int {
        val opcode = bytes[index].toInt() and 0xff
        return when (opcode) {
            0x80, 0x4b, 0x71, 0x68, 0x82 -> index + 2
            0x4d, 0x83 -> index + 3
            0x4a, 0x72, 0x6a, 0x54, 0x42, 0x84 -> {
                if (index + 5 > bytes.size) bytes.size else index + 5 + byteCountForPayload(opcode, bytes, index + 1)
            }
            0x47, 0x95, 0x8e, 0x96 -> {
                if (index + 9 > bytes.size) bytes.size else index + 9 + byteCountForPayload(opcode, bytes, index + 1)
            }
            0x55, 0x43, 0x8a -> {
                if (index + 2 > bytes.size) bytes.size else index + 2 + (bytes[index + 1].toInt() and 0xff)
            }
            0x8b -> {
                if (index + 5 > bytes.size) bytes.size else {
                    val length = readIntLe(bytes, index + 1)
                    if (length < 0) bytes.size else index + 5 + length
                }
            }
            0x49, 0x4c, 0x46, 0x53, 0x56, 0x50, 0x67, 0x70 -> nextNewlineIndex(bytes, index + 1)
            0x63, 0x69 -> nextNewlineIndex(bytes, nextNewlineIndex(bytes, index + 1))
            else -> index + 1
        }
    }

    private fun byteCountForPayload(opcode: Int, bytes: ByteArray, lengthOffset: Int): Int {
        return when (opcode) {
            0x54, 0x42 -> {
                val length = readIntLe(bytes, lengthOffset)
                if (length < 0) bytes.size else length
            }
            0x8e, 0x96 -> {
                val length = readLongLe(bytes, lengthOffset)
                if (length < 0 || length > Int.MAX_VALUE) bytes.size else length.toInt()
            }
            else -> 0
        }
    }

    private fun nextNewlineIndex(bytes: ByteArray, start: Int): Int {
        var index = start
        while (index < bytes.size) {
            if (bytes[index] == '\n'.code.toByte()) return index + 1
            index++
        }
        return bytes.size
    }

    private fun rewriteRenpyPickleText(text: String, fromLanguage: String, toLanguage: String): String {
        if (text.equals(fromLanguage, ignoreCase = true)) return toLanguage
        return text
            .replace("/tl/$fromLanguage/", "/tl/$toLanguage/", ignoreCase = true)
            .replace("/x-tl/x-$fromLanguage/", "/x-tl/x-$toLanguage/", ignoreCase = true)
    }

    private fun readIntLe(bytes: ByteArray, offset: Int): Int {
        return (bytes[offset].toInt() and 0xff) or
            ((bytes[offset + 1].toInt() and 0xff) shl 8) or
            ((bytes[offset + 2].toInt() and 0xff) shl 16) or
            ((bytes[offset + 3].toInt() and 0xff) shl 24)
    }

    private fun readLongLe(bytes: ByteArray, offset: Int): Long {
        var value = 0L
        for (i in 0 until 8) {
            value = value or ((bytes[offset + i].toLong() and 0xffL) shl (8 * i))
        }
        return value
    }

    private fun writeIntLe(output: ByteArrayOutputStream, value: Int) {
        output.write(value and 0xff)
        output.write((value ushr 8) and 0xff)
        output.write((value ushr 16) and 0xff)
        output.write((value ushr 24) and 0xff)
    }

    private fun writeLongLe(output: ByteArrayOutputStream, value: Long) {
        for (i in 0 until 8) {
            output.write(((value ushr (8 * i)) and 0xff).toInt())
        }
    }

    private fun buildZipAlignmentExtra(headerOffset: Long, entryName: String, alignment: Int): ByteArray {
        val baseOffset = headerOffset + 30L + entryName.toByteArray(Charsets.UTF_8).size
        for (paddingSize in 0 until alignment + 4) {
            val extraSize = 4 + paddingSize
            if ((baseOffset + extraSize) % alignment == 0L) {
                return byteArrayOf(0xCA.toByte(), 0xFE.toByte(), paddingSize.toByte(), 0x00) +
                    ByteArray(paddingSize)
            }
        }
        return ByteArray(0)
    }

    private fun normalizeZipEntryPath(path: String): String {
        val normalized = path.replace('\\', '/').trim().trimStart('/')
        if (normalized.contains("../") || normalized == ".." || normalized.startsWith("..")) return ""
        return normalized
    }

    
    @PluginMethod
    fun uninstallApk(call: PluginCall) {
        val packageName = call.getString("packageName") ?: run { call.reject("packageName required"); return }
        try {
            val intent = Intent(Intent.ACTION_DELETE).apply {
                data = Uri.parse("package:" + packageName)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            getContext().startActivity(intent)
            call.resolve(JSObject().apply { put("success", true) })
        } catch (e: Exception) {
            call.reject("Failed: " + e.message)
        }
    }

    @PluginMethod
    fun openAppSettings(call: PluginCall) {
        val packageName = call.getString("packageName") ?: run { call.reject("packageName required"); return }
        try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:$packageName")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            getContext().startActivity(intent)
            call.resolve(JSObject().apply { put("success", true) })
        } catch (e: Exception) {
            call.reject("Failed to open app settings: ${e.message}")
        }
    }

    @PluginMethod
    fun launchApp(call: PluginCall) {
        val packageName = call.getString("packageName") ?: run { call.reject("packageName required"); return }
        try {
            val launchIntent = getContext().packageManager.getLaunchIntentForPackage(packageName)
            if (launchIntent == null) {
                call.reject("Cannot launch package: $packageName")
                return
            }
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            getContext().startActivity(launchIntent)
            call.resolve(JSObject().apply { put("success", true) })
        } catch (e: Exception) {
            call.reject("Failed to launch app: ${e.message}")
        }
    }

    @PluginMethod
    fun loadTranslationCache(call: PluginCall) {
        try {
            val cacheFile = java.io.File(java.io.File(getContext().filesDir, "cache"), "translation-cache.json")
            if (cacheFile.exists()) {
                val data = cacheFile.readText(Charsets.UTF_8)
                call.resolve(JSObject().apply { put("data", data) })
            } else {
                call.resolve(JSObject().apply { put("data", "{}") })
            }
        } catch (e: Exception) {
            call.resolve(JSObject().apply { put("data", "{}") })
        }
    }
    @PluginMethod
    fun saveTranslationCache(call: PluginCall) {
        val data = call.getString("data") ?: run { call.reject("data required"); return }
        try {
            val dir = java.io.File(getContext().filesDir, "cache")
            if (!dir.exists()) dir.mkdirs()
            val cacheFile = java.io.File(dir, "translation-cache.json")
            cacheFile.writeText(data, Charsets.UTF_8)
            call.resolve(JSObject().apply { put("success", true) })
        } catch (e: Exception) {
            call.reject("Failed: " + e.message)
        }
    }
    @PluginMethod
    fun getApkPackageName(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        try {
            val ctx = getContext()
            val zipStream = ZipInputStream(ctx.contentResolver.openInputStream(Uri.parse(uriStr)))
            var packageName = ""
            var entry = zipStream.nextEntry
            while (entry != null) {
                if (entry.name.equals("AndroidManifest.xml", ignoreCase = true)) {
                    packageName = extractPackageNameFromManifest(zipStream.readBytes())
                    break
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }
            zipStream.close()
            call.resolve(JSObject().apply { put("packageName", packageName) })
        } catch (e: Exception) {
            call.reject("Failed: " + e.message)
        }
    }

    private fun extractPackageNameFromManifest(data: ByteArray): String {
        val candidates = linkedSetOf<String>()
        collectPackageCandidates(data.toString(Charsets.UTF_8), candidates)
        collectPackageCandidates(readUtf16LeStrings(data), candidates)

        return candidates
            .filterNot { it.startsWith("android.") || it.startsWith("com.android.") }
            .filterNot { it.contains(".permission.") || it.endsWith(".permission") }
            .minByOrNull { scorePackageCandidate(it) }
            ?: ""
    }

    private fun collectPackageCandidates(text: String, output: MutableSet<String>) {
        val pattern = Regex("[A-Za-z][A-Za-z0-9_]*(?:\\.[A-Za-z][A-Za-z0-9_]*)+")
        for (match in pattern.findAll(text)) {
            val value = match.value
            if (value.length in 5..160) output.add(value)
        }
    }

    private fun readUtf16LeStrings(data: ByteArray): String {
        val builder = StringBuilder()
        val current = StringBuilder()
        var index = 0

        while (index + 1 < data.size) {
            val low = data[index].toInt() and 0xFF
            val high = data[index + 1].toInt() and 0xFF
            if (high == 0 && low in 32..126) {
                current.append(low.toChar())
            } else {
                if (current.length >= 4) builder.append(current).append('\n')
                current.clear()
            }
            index += 2
        }

        if (current.length >= 4) builder.append(current)
        return builder.toString()
    }

    private fun scorePackageCandidate(value: String): Int {
        var score = value.length
        if (value.startsWith("com.") || value.startsWith("org.") || value.startsWith("net.")) score += 20
        if (value.contains("intent.") || value.contains("provider.")) score += 50
        return score
    }

    private fun isPackageInstalled(packageName: String): Boolean {
        return try {
            getContext().packageManager.getPackageInfo(packageName, 0)
            true
        } catch (_: Exception) {
            false
        }
    }
private val DEBUG_PRIVATE_KEY_PEM = """
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDei2QW3hm1fTmB
rfmfRBxlmPSMtqdNFN5dfqc/tRpZQpN00rVAO6WHLi8mdvz9XYAOiFX+a+I782Jv
oYdexnd+sx7HemaaDyv+BlK2EJ2F1fsREWVKht3xA12cYUVKeA5gTsyPJlEnpxTu
0/GIfTQxUKGW/lG6shRoApa8l01hJHmPXt5Nj22l1H5pwkGqLVqpl5MKuxCZwv3V
CWJTOQp5XxCINCU9pO17BWkgJ03q4NEOIV8qqBxl52Xsi+s/P7CDBl8kPvFRwSnj
wqaWsop1S99v4Eqvn9vQ/vphME6X10z0l1kBMKfdF+7qIvTXgM97i0upuyZ3Hcg1
vWpaGBJDAgMBAAECggEAbyQ6NllxiXwirisO0YWYkPzUlTnbT9muPA82w9BUemOP
dPaOYqfnQR3FmnYuXvLFM3zPRaLnd31TmeCX1LNVlkcqhgERILuXAuRxhk/B+8cj
/iAr8A5u5SEDLUg+7LQMqfhwnMVMHnuJLsVWiQ3OdRqJuPkGJDEvk8pHMaR2lp5M
GTOkaq82/sdL2ndhLADE7cdx/Qtr/noiHeF/DGZfkjW5ZjnCGxOAhzm2qtpVuW6N
xMkpNB8EEmrVH7J6NZ6nCfLG6Sviq7OTcA7S8GdnOTBuPbOryTmM0bd99j53imwN
2ATkVWHasbhuLQNkw2dh+lioZQgS1vfhv6rLVJwrEQKBgQD5nbNDZ2GZtuwIRlhh
YfsNFHkKrFNXMM9VDsvvNU30t2fexA/gXyOKWVNYR0dP3Z1eL/dWp4Srg1otyfy1
tzJGKMDXBDYRPZEFD/B2DZpgx+OtD650WIzosTLD/x0YHkgxrB1/m+T503IAL0xm
Um+8N7Y9w7F/gPXrpjDwEwqfjwKBgQDkPHJSqBQg8ci7dHd5CsgwN03u5922XD+i
JD4hdeJbOWwRPpZOD5C8esQGZKN67s3ZjfhdyeQBqqrR1yGdLqEk5HLr4cDK/sFJ
o3tQwDPWo5H36pMYPNh9rmXsqLdToG91WxHl1HBMwZ5Mq9b3FoP2m93rDFAUIHr7
zbnZwJaIDQKBgDPHxfcWjAWSD5aL2SuiYqzM8WsIYmV0552SazWdDiXUogRxEYYO
1lWNwB9Q8fccVtfCBYIBUCEwJ1XWT8j2TsSFEbPI2NpsthehvdUPb1XiQVWWKi9S
azCeCZTk6Aknxvwe4yOkmDRG66AkL6oOMcWOnQxk+v4jJ2CR4hb7LDn7AoGABTIr
GB6jdqyKeVoJbkQEkrRvncTBk2k+OZ7Bm1lnsdP41duq6FQKY4AX/l1EK4RMQ2ur
/9aczjzobqaLKVzqZkCdLSmSjgyGsfp60DfP9k76/73jY2XfN91EjMK6ibjZUL6m
Bal0dQrjY7N1zWJB1tdtkfBR0mN66Uihtodf5fECgYEA2kzJagKgl2qJp/gZswOn
4XmLD5p+1XpO1hSVzYjJ62JnmiNY8XEfaQsea386nZajWeYCU7gboP24VxV8as1V
t4hxiEniP7b9OCsCeD1viwkE1US4qgGiefOe7CpONRVhgmivKHuNl5ZiuPuA31/O
fD+V6rwZA4WuHKnD0xWds9U=
-----END PRIVATE KEY-----
""".trimIndent()

    private val DEBUG_CERTIFICATE_PEM = """
-----BEGIN CERTIFICATE-----
MIIDODCCAiCgAwIBAgIUOnBRkzqbFvby6LhGdCsGaFx6+SMwDQYJKoZIhvcNAQEL
BQAwRTELMAkGA1UEBhMCQ04xFzAVBgNVBAoMDlNMRyBUcmFuc2xhdG9yMR0wGwYD
VQQDDBRTTEcgVHJhbnNsYXRvciBEZWJ1ZzAeFw0yNjA1MzExNDMzMjNaFw0zNjA1
MjkxNDMzMjNaMEUxCzAJBgNVBAYTAkNOMRcwFQYDVQQKDA5TTEcgVHJhbnNsYXRv
cjEdMBsGA1UEAwwUU0xHIFRyYW5zbGF0b3IgRGVidWcwggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQDei2QW3hm1fTmBrfmfRBxlmPSMtqdNFN5dfqc/tRpZ
QpN00rVAO6WHLi8mdvz9XYAOiFX+a+I782JvoYdexnd+sx7HemaaDyv+BlK2EJ2F
1fsREWVKht3xA12cYUVKeA5gTsyPJlEnpxTu0/GIfTQxUKGW/lG6shRoApa8l01h
JHmPXt5Nj22l1H5pwkGqLVqpl5MKuxCZwv3VCWJTOQp5XxCINCU9pO17BWkgJ03q
4NEOIV8qqBxl52Xsi+s/P7CDBl8kPvFRwSnjwqaWsop1S99v4Eqvn9vQ/vphME6X
10z0l1kBMKfdF+7qIvTXgM97i0upuyZ3Hcg1vWpaGBJDAgMBAAGjIDAeMAwGA1Ud
EwEB/wQCMAAwDgYDVR0PAQH/BAQDAgeAMA0GCSqGSIb3DQEBCwUAA4IBAQAX+3yN
Ck0b+hnH5hm1Yp9nc9g99N2FI7Uye7/MFRCI1wkwNkb8sbuVbgsEDXe5Rp2T7lEP
L3agThf8B19xbpyA+apRKSVf/98/o/wvrPjQyVfG1KCUArVUosdFWlZj2GYYNGzt
1i+6KCasHkqJma1f3XM14XKPrMFKr8RnioYSciOXRrqoh7c/BZ5J9Y321R3TUMvQ
Ox3MOjzkEE61ntEnzES+hvEFX5fsmacyHFcGuGdNYl8OK+ypxJ1w+SmLlJ+LxFXh
1Mpfx52jlLPXiXrEZGpb1avjGLSYp/ROZeR8O9Me2icCXf0nQrP0adFFvuQnyH92
CxSQ7iXyyhxA2xtr
-----END CERTIFICATE-----
""".trimIndent()
}

private class CountingOutputStream(private val delegate: OutputStream) : OutputStream() {
    var bytesWritten: Long = 0
        private set

    override fun write(value: Int) {
        delegate.write(value)
        bytesWritten += 1
    }

    override fun write(buffer: ByteArray) {
        delegate.write(buffer)
        bytesWritten += buffer.size
    }

    override fun write(buffer: ByteArray, offset: Int, length: Int) {
        delegate.write(buffer, offset, length)
        bytesWritten += length
    }

    override fun flush() {
        delegate.flush()
    }

    override fun close() {
        delegate.close()
    }
}
