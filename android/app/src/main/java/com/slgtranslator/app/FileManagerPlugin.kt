package com.slgtranslator.app

import android.content.Intent
import android.os.Build
import android.os.Environment
import android.provider.Settings
import com.getcapacitor.JSObject
import com.getcapacitor.JSArray
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.File

@CapacitorPlugin(name = "FileManager")
class FileManagerPlugin : Plugin() {

    @PluginMethod
    fun checkPermission(call: PluginCall) {
        val ret = JSObject()
        val granted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            true
        }
        ret.put("granted", granted)
        call.resolve(ret)
    }

    @PluginMethod
    fun requestPermission(call: PluginCall) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                data = android.net.Uri.parse("package:${context.packageName}")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        }
        val ret = JSObject()
        val granted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            true
        }
        ret.put("granted", granted)
        call.resolve(ret)
    }

    @PluginMethod
    fun listDirectory(call: PluginCall) {
        val path = call.getString("path")
        if (path == null) {
            call.reject("path is required")
            return
        }

        val dir = File(path)
        if (!dir.exists() || !dir.isDirectory) {
            call.reject("Directory not found: $path")
            return
        }

        val entries = JSArray()
        dir.listFiles()?.forEach { file ->
            val entry = JSObject()
            entry.put("name", file.name)
            entry.put("path", file.absolutePath)
            entry.put("isDirectory", file.isDirectory)
            entry.put("size", file.length())
            entry.put("lastModified", file.lastModified())
            entries.put(entry)
        }

        val ret = JSObject()
        ret.put("entries", entries)
        call.resolve(ret)
    }

    @PluginMethod
    fun readFile(call: PluginCall) {
        val path = call.getString("path")
        if (path == null) {
            call.reject("path is required")
            return
        }

        val file = File(path)
        if (!file.exists() || !file.isFile) {
            call.reject("File not found: $path")
            return
        }

        try {
            val ret = JSObject()
            ret.put("content", file.readText(Charsets.UTF_8))
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to read file: ${e.message}")
        }
    }

    @PluginMethod
    fun writeFile(call: PluginCall) {
        val path = call.getString("path")
        val content = call.getString("content")
        if (path == null || content == null) {
            call.reject("path and content are required")
            return
        }

        try {
            val file = File(path)
            file.parentFile?.mkdirs()
            file.writeText(content, Charsets.UTF_8)
            val ret = JSObject()
            ret.put("success", true)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to write file: ${e.message}")
        }
    }

    @PluginMethod
    fun backupFile(call: PluginCall) {
        val path = call.getString("path")
        if (path == null) {
            call.reject("path is required")
            return
        }

        val original = File(path)
        if (!original.exists()) {
            call.reject("File not found: $path")
            return
        }

        try {
            val backupPath = "$path.bak"
            val backup = File(backupPath)
            if (!backup.exists()) {
                original.copyTo(backup, overwrite = false)
            }
            val ret = JSObject()
            ret.put("backupPath", backupPath)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to backup file: ${e.message}")
        }
    }

    @PluginMethod
    fun fileExists(call: PluginCall) {
        val path = call.getString("path")
        if (path == null) {
            call.reject("path is required")
            return
        }
        val ret = JSObject()
        ret.put("exists", File(path).exists())
        call.resolve(ret)
    }
}