package com.slgtranslator.app;

import android.content.Context;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Prototype save transfer for Ren'Py games. Ren'Py Android stores saves under
 * Documents/RenPy_Saves/&lt;package&gt;/, so backing up that directory (and
 * restoring it) moves progress between devices or installs. This is a first
 * version: plain file copies, no conflict resolution.
 */
public final class SaveTransfer {

    private SaveTransfer() {
    }

    public static void backupSaves(Context context, PluginCall call) {
        String packageName = call.getString("packageName");
        if (packageName == null || packageName.isEmpty()) {
            call.reject("packageName required");
            return;
        }
        try {
            File saves = saveRoot(packageName);
            if (saves == null || !saves.isDirectory()) {
                JSObject result = new JSObject();
                result.put("backupDir", "");
                result.put("savedFiles", 0);
                call.resolve(result);
                return;
            }
            File base = context.getExternalFilesDir(null);
            if (base == null) {
                call.reject("external storage unavailable");
                return;
            }
            File backups = new File(base, "save-backups");
            backups.mkdirs();
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            File destination = new File(backups, packageName + "-" + stamp);
            int copied = copyTree(saves, destination);
            JSObject result = new JSObject();
            result.put("backupDir", destination.getAbsolutePath());
            result.put("savedFiles", copied);
            call.resolve(result);
        } catch (Exception e) {
            call.reject("backup failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    public static void restoreSaves(Context context, PluginCall call) {
        String packageName = call.getString("packageName");
        String backupDir = call.getString("backupDir");
        if (packageName == null || packageName.isEmpty() || backupDir == null || backupDir.isEmpty()) {
            call.reject("packageName and backupDir required");
            return;
        }
        try {
            File source = new File(backupDir);
            if (!source.isDirectory()) {
                call.reject("backup directory not found");
                return;
            }
            File saves = saveRoot(packageName);
            if (saves == null) {
                call.reject("save root unavailable");
                return;
            }
            saves.mkdirs();
            int copied = copyTree(source, saves);
            JSObject result = new JSObject();
            result.put("restoredFiles", copied);
            call.resolve(result);
        } catch (Exception e) {
            call.reject("restore failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    public static void listSaveBackups(Context context, PluginCall call) {
        try {
            File base = context.getExternalFilesDir(null);
            JSArray backups = new JSArray();
            if (base != null) {
                File directory = new File(base, "save-backups");
                File[] entries = directory.listFiles();
                if (entries != null) {
                    List<File> sorted = new ArrayList<>();
                    for (File entry : entries) {
                        if (entry.isDirectory()) {
                            sorted.add(entry);
                        }
                    }
                    sorted.sort((left, right) -> Long.compare(right.lastModified(), left.lastModified()));
                    for (File entry : sorted) {
                        JSObject item = new JSObject();
                        item.put("name", entry.getName());
                        item.put("path", entry.getAbsolutePath());
                        item.put("modifiedAt", entry.lastModified());
                        item.put("fileCount", countFiles(entry));
                        backups.put(item);
                    }
                }
            }
            JSObject result = new JSObject();
            result.put("backups", backups);
            call.resolve(result);
        } catch (Exception e) {
            call.reject("list backups failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    /** Documents/RenPy_Saves/&lt;package&gt; on the shared storage. */
    private static File saveRoot(String packageName) {
        File documents = new File(android.os.Environment.getExternalStorageDirectory(), "Documents");
        File renpySaves = new File(documents, "RenPy_Saves");
        return new File(renpySaves, packageName);
    }

    private static int copyTree(File source, File destination) throws IOException {
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("cannot create " + destination);
        }
        int count = 0;
        File[] children = source.listFiles();
        if (children == null) {
            return 0;
        }
        for (File child : children) {
            File target = new File(destination, child.getName());
            if (child.isDirectory()) {
                count += copyTree(child, target);
            } else if (child.isFile()) {
                copyFile(child, target);
                count++;
            }
        }
        return count;
    }

    private static void copyFile(File source, File target) throws IOException {
        try (InputStream in = new FileInputStream(source);
             OutputStream out = new FileOutputStream(target)) {
            byte[] buffer = new byte[65536];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
        }
    }

    private static int countFiles(File directory) {
        int count = 0;
        File[] children = directory.listFiles();
        if (children == null) {
            return 0;
        }
        for (File child : children) {
            if (child.isDirectory()) {
                count += countFiles(child);
            } else if (child.isFile()) {
                count++;
            }
        }
        return count;
    }
}
