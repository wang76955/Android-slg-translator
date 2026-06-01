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
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream

@CapacitorPlugin(name = "FileManager")
class FileManagerPlugin : Plugin() {

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

    // ===== 解析 APK/ZIP =====
    @PluginMethod
    fun listApkEntries(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        try {
            val ctx = getContext()
            val zipStream = ZipInputStream(ctx.contentResolver.openInputStream(Uri.parse(uriStr)))
            val entries = JSArray()
            var entry: ZipEntry? = zipStream.nextEntry
            while (entry != null) {
                if (!entry.isDirectory && entry.name.endsWith(".json", ignoreCase = true)) {
                    entries.put(JSObject().apply {
                        put("name", entry.name)
                        put("size", entry.size)
                        put("compressedSize", entry.compressedSize)
                    })
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }
            zipStream.close()
            call.resolve(JSObject().apply {
                put("entries", entries)
                put("totalJsonFiles", entries.length())
            })
        } catch (e: Exception) {
            call.reject("Failed to read APK: ${e.message}")
        }
    }

    @PluginMethod
    fun readApkEntry(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        val entryName = call.getString("entryName") ?: run { call.reject("entryName required"); return }
        try {
            val ctx = getContext()
            val zipStream = ZipInputStream(ctx.contentResolver.openInputStream(Uri.parse(uriStr)))
            var found = false
            var text = ""
            var entry: ZipEntry? = zipStream.nextEntry
            while (entry != null) {
                if (entry.name == entryName) {
                    text = zipStream.bufferedReader(Charsets.UTF_8).readText()
                    found = true
                    break
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }
            zipStream.close()
            if (!found) { call.reject("Entry not found: $entryName"); return }
            call.resolve(JSObject().apply { put("content", text) })
        } catch (e: Exception) {
            call.reject("Failed to read entry: ${e.message}")
        }
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
            val newFile = docFile?.createFile("application/json", fileName)
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
