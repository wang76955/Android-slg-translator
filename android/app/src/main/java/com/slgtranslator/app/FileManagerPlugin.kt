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
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

@CapacitorPlugin(name = "FileManager")
class FileManagerPlugin : Plugin() {

    // ===== 权限 =====
    @PluginMethod
    fun checkPermission(call: PluginCall) {
        val ret = JSObject()
        ret.put("granted", if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Environment.isExternalStorageManager() else true)
        call.resolve(ret)
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
        val ret = JSObject()
        ret.put("granted", if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Environment.isExternalStorageManager() else true)
        call.resolve(ret)
    }

    // ===== APK 文件选择 =====
    @PluginMethod
    fun pickApkFile(call: PluginCall) {
        try {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                type = "*/*"
                putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("application/vnd.android.package-archive", "application/zip"))
                addCategory(Intent.CATEGORY_OPENABLE)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivityForResult(call, intent, "onApkPicked")
        } catch (e: Exception) {
            call.reject("Failed to open picker: ${e.message}")
        }
    }

    @ActivityCallback
    fun onApkPicked(call: PluginCall, result: ActivityResult) {
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            val uri = result.data!!.data!!
            val ret = JSObject()
            ret.put("uri", uri.toString())
            call.resolve(ret)
        } else {
            call.reject("User cancelled")
        }
    }

    // ===== 解析 APK/ZIP 文件 =====
    @PluginMethod
    fun listApkEntries(call: PluginCall) {
        val uriStr = call.getString("uri") ?: run { call.reject("uri required"); return }
        try {
            val ctx = getContext()
            val inputStream = ctx.contentResolver.openInputStream(Uri.parse(uriStr))
            val zipStream = ZipInputStream(inputStream)
            val entries = JSArray()
            val seenFolders = HashSet<String>()

            var entry: ZipEntry? = zipStream.nextEntry
            while (entry != null) {
                val name = entry.name
                if (!entry.isDirectory) {
                    // 只列出 JSON 文件
                    if (name.endsWith(".json", ignoreCase = true)) {
                        val obj = JSObject()
                        obj.put("name", name)
                        obj.put("size", entry.size)
                        obj.put("compressedSize", entry.compressedSize)
                        entries.put(obj)
                    }
                } else {
                    seenFolders.add(name)
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }
            zipStream.close()

            val ret = JSObject()
            ret.put("entries", entries)
            ret.put("totalJsonFiles", entries.length())
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to read APK: ${e.message}")
        }
    }

    @PluginMethod
    fun readApkEntry(call: PluginCall) {
        val uriStr = call.getString("uri")
        val entryName = call.getString("entryName")
        if (uriStr == null || entryName == null) { call.reject("uri and entryName required"); return }
        try {
            val ctx = getContext()
            val inputStream = ctx.contentResolver.openInputStream(Uri.parse(uriStr))
            val zipStream = ZipInputStream(inputStream)

            var found: ZipEntry? = null
            var entry: ZipEntry? = zipStream.nextEntry
            while (entry != null) {
                if (entry.name == entryName) {
                    found = entry
                    break
                }
                zipStream.closeEntry()
                entry = zipStream.nextEntry
            }

            if (found == null) {
                zipStream.close()
                call.reject("Entry not found: $entryName")
                return
            }

            val text = zipStream.bufferedReader(Charsets.UTF_8).readText()
            zipStream.close()

            val ret = JSObject()
            ret.put("content", text)
            ret.put("name", entryName)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to read entry: ${e.message}")
        }
    }

    // ===== 选择输出目录 =====
    @PluginMethod
    fun pickOutputDir(call: PluginCall) {
        try {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or
                         Intent.FLAG_GRANT_WRITE_URI_PERMISSION or
                         Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivityForResult(call, intent, "onOutputDirPicked")
        } catch (e: Exception) {
            call.reject("Failed to open picker: ${e.message}")
        }
    }

    @ActivityCallback
    fun onOutputDirPicked(call: PluginCall, result: ActivityResult) {
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            val uri = result.data!!.data!!
            try {
                val takeFlags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                getContext().contentResolver.takePersistableUriPermission(uri, takeFlags)
            } catch (_: Exception) {}
            val ret = JSObject()
            ret.put("uri", uri.toString())
            call.resolve(ret)
        } else {
            call.reject("User cancelled")
        }
    }

    // ===== 文件写入（SAF） =====
    @PluginMethod
    fun writeFileToDir(call: PluginCall) {
        val dirUri = call.getString("dirUri")
        val fileName = call.getString("fileName")
        val content = call.getString("content")
        if (dirUri == null || fileName == null || content == null) {
            call.reject("dirUri, fileName, content required"); return
        }
        try {
            val ctx = getContext()
            val treeUri = Uri.parse(dirUri)
            val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, treeUri)
            val newFile = docFile?.createFile("*/*", fileName)
            if (newFile != null) {
                val out = ctx.contentResolver.openOutputStream(newFile.uri)
                out?.write(content.toByteArray(Charsets.UTF_8))
                out?.close()
            }
            val ret = JSObject()
            ret.put("success", newFile != null)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to write: ${e.message}")
        }
    }

    @PluginMethod
    fun createDirectory(call: PluginCall) {
        val dirUri = call.getString("dirUri")
        val dirName = call.getString("dirName")
        if (dirUri == null || dirName == null) { call.reject("dirUri, dirName required"); return }
        try {
            val ctx = getContext()
            val treeUri = Uri.parse(dirUri)
            val docFile = androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, treeUri)
            val created = docFile?.createDirectory(dirName)
            val ret = JSObject()
            ret.put("success", created != null)
            ret.put("uri", created?.uri?.toString() ?: "")
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to create dir: ${e.message}")
        }
    }
}