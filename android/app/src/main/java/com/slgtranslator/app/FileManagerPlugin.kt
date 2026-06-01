package com.slgtranslator.app

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.activity.result.ActivityResult
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.ByteArrayOutputStream
import java.util.zip.Inflater
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream

@CapacitorPlugin(name = "FileManager")
class FileManagerPlugin : Plugin() {

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

        val fullText = decompressed.toString(Charsets.UTF_8.name())
        return fullText
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
            val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, Uri.parse(dirUri))
            val newFile = docFile?.createFile("application/octet-stream", fileName)
            if (newFile != null) {
                ctx.contentResolver.openOutputStream(newFile.uri)?.use { it.write(content.toByteArray(Charsets.UTF_8)) }
            }
            call.resolve(JSObject().apply { put("success", newFile != null) })
        } catch (e: Exception) {
            call.reject("Failed to write: ${e.message}")
        }
    }

    @PluginMethod
    fun createDirectory(call: PluginCall) {
        val dirUri = call.getString("dirUri") ?: run { call.reject("dirUri required"); return }
        val dirName = call.getString("dirName") ?: run { call.reject("dirName required"); return }
        try {
            val ctx = getContext()
            val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, Uri.parse(dirUri))
            val created = docFile?.createDirectory(dirName)
            call.resolve(JSObject().apply {
                put("success", created != null)
                put("uri", created?.uri?.toString() ?: "")
            })
        } catch (e: Exception) {
            call.reject("Failed to create dir: ${e.message}")
        }
    }
}
