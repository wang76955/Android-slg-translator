package com.slgtranslator.app;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

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
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

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

    public static void deleteBackup(Context context, PluginCall call) {
        String backupDir = call.getString("backupDir");
        if (backupDir == null || backupDir.isEmpty()) {
            call.reject("backupDir required");
            return;
        }
        try {
            File base = context.getExternalFilesDir(null);
            if (base == null) {
                call.reject("external storage unavailable");
                return;
            }
            File backups = new File(base, "save-backups").getCanonicalFile();
            File target = new File(backupDir).getCanonicalFile();
            String backupsPrefix = backups.getPath() + File.separator;
            if (!target.getPath().startsWith(backupsPrefix)) {
                call.reject("invalid backup directory");
                return;
            }
            if (!target.isDirectory()) {
                call.reject("backup directory not found");
                return;
            }
            int deletedFiles = deleteTree(target);
            JSObject result = new JSObject();
            result.put("deletedFiles", deletedFiles);
            call.resolve(result);
        } catch (Exception e) {
            call.reject("delete backup failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    public static void deleteSaveArchive(Context context, PluginCall call) {
        String path = call.getString("path");
        if (path == null || path.trim().isEmpty()) {
            call.reject("path required");
            return;
        }
        try {
            File downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if (downloads == null) {
                call.reject("downloads unavailable");
                return;
            }
            File downloadsRoot = downloads.getCanonicalFile();
            File target = new File(path).getCanonicalFile();
            String prefix = downloadsRoot.getPath() + File.separator;
            if (!target.getPath().startsWith(prefix) || !target.getName().toLowerCase(Locale.US).endsWith(".zip")) {
                call.reject("invalid save archive path");
                return;
            }
            if (!target.isFile()) {
                call.reject("save archive not found");
                return;
            }
            if (!target.delete()) {
                call.reject("delete save archive failed");
                return;
            }
            call.resolve(new JSObject().put("deleted", true).put("path", target.getPath()));
        } catch (Exception e) {
            call.reject("delete save archive failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }
    public static void exportSavesToDownloads(Context context, PluginCall call) {
        String packageName = call.getString("packageName");
        if (packageName == null || packageName.isEmpty()) {
            call.reject("packageName required");
            return;
        }
        try {
            File saves = saveRoot(packageName);
            if (saves == null || !saves.isDirectory()) {
                call.reject("save directory not found");
                return;
            }
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            String fileName = safeFileName(packageName) + "-" + stamp + ".zip";
            Uri uri = saveZipToDownloads(context, saves, fileName);
            JSObject result = new JSObject();
            result.put("path", "/storage/emulated/0/Download/SLG-Translator/saves/" + fileName);
            result.put("uri", uri.toString());
            result.put("zipFiles", countFiles(saves));
            call.resolve(result);
        } catch (Exception e) {
            call.reject("export failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    public static void shareSaveBackup(Context context, PluginCall call) {
        String backupDir = call.getString("backupDir");
        if (backupDir == null || backupDir.isEmpty()) {
            call.reject("backupDir required");
            return;
        }
        try {
            File backup = new File(backupDir);
            if (!backup.isDirectory()) {
                call.reject("backup directory not found");
                return;
            }
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            String fileName = safeFileName(backup.getName()) + "-" + stamp + ".zip";
            Uri uri = saveZipToDownloads(context, backup, fileName);
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("application/zip");
            send.putExtra(Intent.EXTRA_STREAM, (android.os.Parcelable) uri);
            send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            context.startActivity(Intent.createChooser(send, "分享存档"));
            JSObject result = new JSObject();
            result.put("path", "/storage/emulated/0/Download/SLG-Translator/saves/" + fileName);
            result.put("uri", uri.toString());
            result.put("shared", true);
            call.resolve(result);
        } catch (Exception e) {
            call.reject("share failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    public static void listSaveArchives(Context context, PluginCall call) {
        try {
            File downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            JSArray archives = new JSArray();
            if (downloads != null) {
                collectArchives(downloads, archives, 0);
            }
            call.resolve(new JSObject().put("archives", archives));
        } catch (Exception e) {
            call.reject("list archives failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    public static void importSaveBackup(Context context, PluginCall call) {
        String path = call.getString("path");
        if (path == null || path.trim().isEmpty()) {
            call.reject("path required");
            return;
        }
        try {
            File downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            File source = new File(path).getCanonicalFile();
            if (downloads == null || !source.getPath().startsWith(downloads.getCanonicalFile().getPath() + File.separator)) {
                call.reject("请选择下载目录中的存档 zip");
                return;
            }
            if (!source.isFile() || !source.getName().toLowerCase(Locale.US).endsWith(".zip")) {
                call.reject("存档 zip 不存在");
                return;
            }
            File base = context.getExternalFilesDir(null);
            if (base == null) {
                call.reject("external storage unavailable");
                return;
            }
            File backups = new File(base, "save-backups");
            if (!backups.exists() && !backups.mkdirs()) {
                call.reject("cannot create backup directory");
                return;
            }
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            String baseName = source.getName().replaceFirst("(?i)\\.zip$", "");
            File destination = new File(backups, safeFileName(baseName) + "-" + stamp);
            int extracted = extractZip(source, destination);
            JSObject result = new JSObject();
            result.put("backupDir", destination.getAbsolutePath());
            result.put("name", destination.getName());
            result.put("fileCount", extracted);
            String packageName = packageFromName(source.getName());
            if (packageName != null) {
                result.put("packageName", packageName);
            }
            call.resolve(result);
        } catch (Exception e) {
            call.reject("import failed: " + (e.getMessage() == null ? e.toString() : e.getMessage()));
        }
    }

    private static void collectArchives(File directory, JSArray archives, int depth) {
        if (directory == null || !directory.isDirectory() || depth > 3) {
            return;
        }
        File[] files = directory.listFiles();
        if (files == null) {
            return;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                collectArchives(file, archives, depth + 1);
            } else if (file.isFile() && file.getName().toLowerCase(Locale.US).endsWith(".zip")) {
                JSObject item = new JSObject();
                item.put("name", file.getName());
                item.put("path", file.getAbsolutePath());
                item.put("modifiedAt", file.lastModified());
                item.put("size", file.length());
                archives.put(item);
            }
        }
    }

    private static int extractZip(File source, File destination) throws IOException {
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("cannot create " + destination);
        }
        File root = destination.getCanonicalFile();
        String rootPrefix = root.getPath() + File.separator;
        String commonRoot = commonZipRoot(source);
        int count = 0;
        try (ZipFile zip = new ZipFile(source)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (entry.isDirectory()) {
                    continue;
                }
                String name = entry.getName();
                if (name == null || name.isEmpty() || name.startsWith("__MACOSX/") || name.endsWith(".DS_Store")) {
                    continue;
                }
                name = name.replace('\\', '/');
                if (name.contains("..") || name.startsWith("/")) {
                    throw new IOException("unsafe zip entry: " + name);
                }
                if (commonRoot != null && name.startsWith(commonRoot + "/")) {
                    name = name.substring(commonRoot.length() + 1);
                }
                if (name.isEmpty()) {
                    continue;
                }
                File target = new File(destination, name);
                File canonicalTarget = target.getCanonicalFile();
                if (!canonicalTarget.getPath().startsWith(rootPrefix)) {
                    throw new IOException("unsafe zip entry: " + name);
                }
                File parent = target.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("cannot create " + parent);
                }
                try (InputStream in = zip.getInputStream(entry); OutputStream out = new FileOutputStream(target)) {
                    copy(in, out);
                }
                count++;
            }
        }
        return count;
    }

    private static String commonZipRoot(File source) throws IOException {
        try (ZipFile zip = new ZipFile(source)) {
            String root = null;
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                String name = entries.nextElement().getName();
                if (name == null || name.isEmpty() || name.startsWith("__MACOSX/") || name.endsWith("/")) {
                    continue;
                }
                int slash = name.indexOf('/');
                if (slash <= 0) {
                    return null;
                }
                String first = name.substring(0, slash);
                if (root == null) {
                    root = first;
                } else if (!root.equals(first)) {
                    return null;
                }
            }
            return root;
        }
    }

    private static String packageFromName(String fileName) {
        String base = fileName.replaceFirst("(?i)\\.zip$", "");
        Pattern stamp = Pattern.compile("^(.*)-\\d{8}-\\d{6}$");
        for (int i = 0; i < 2; i++) {
            Matcher matcher = stamp.matcher(base);
            if (!matcher.matches() || !matcher.group(1).contains(".")) {
                break;
            }
            base = matcher.group(1);
        }
        return base.contains(".") ? base : null;
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
            copy(in, out);
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

    private static int deleteTree(File directory) {
        int deleted = 0;
        File[] children = directory.listFiles();
        if (children != null) {
            for (File child : children) {
                if (child.isDirectory()) {
                    deleted += deleteTree(child);
                } else if (child.isFile() && child.delete()) {
                    deleted++;
                }
            }
        }
        directory.delete();
        return deleted;
    }

    private static Uri saveZipToDownloads(Context context, File source, String fileName) throws IOException {
        Uri targetUri = null;
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
            values.put(MediaStore.MediaColumns.MIME_TYPE, "application/zip");
            values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/SLG-Translator/saves");
            targetUri = context.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            if (targetUri != null) {
                try {
                    try (OutputStream out = context.getContentResolver().openOutputStream(targetUri)) {
                        if (out == null) {
                            throw new IOException("output stream unavailable");
                        }
                        zipDirectory(source, out);
                    }
                } catch (IOException failure) {
                    deleteQuietly(context.getContentResolver(), targetUri);
                    throw failure;
                }
            }
        }
        if (targetUri == null) {
            File dir = new File(
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
                "SLG-Translator/saves"
            );
            if (!dir.exists() && !dir.mkdirs()) {
                throw new IOException("cannot create " + dir);
            }
            File destination = new File(dir, fileName);
            zipDirectory(source, destination);
            targetUri = Uri.fromFile(destination);
        }
        return targetUri;
    }

    private static int zipDirectory(File source, File zipFile) throws IOException {
        File parent = zipFile.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("cannot create " + parent);
        }
        try (OutputStream output = new FileOutputStream(zipFile)) {
            return zipDirectory(source, output);
        }
    }

    private static int zipDirectory(File source, OutputStream output) throws IOException {
        try (ZipOutputStream zip = new ZipOutputStream(output)) {
            return zipDirectory(source, "", zip);
        }
    }

    private static int zipDirectory(File directory, String prefix, ZipOutputStream zip) throws IOException {
        int count = 0;
        File[] children = directory.listFiles();
        if (children == null) {
            return 0;
        }
        for (File child : children) {
            String relative = prefix.isEmpty() ? child.getName() : prefix + "/" + child.getName();
            if (child.isDirectory()) {
                count += zipDirectory(child, relative, zip);
            } else if (child.isFile()) {
                ZipEntry entry = new ZipEntry(relative);
                zip.putNextEntry(entry);
                try (InputStream in = new FileInputStream(child)) {
                    copy(in, zip);
                }
                zip.closeEntry();
                count++;
            }
        }
        return count;
    }

    private static void copy(InputStream in, OutputStream out) throws IOException {
        byte[] buffer = new byte[65536];
        int read;
        while ((read = in.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
    }

    private static String safeFileName(String value) {
        String cleaned = value.replaceAll("[^A-Za-z0-9._-]", "_");
        return cleaned.isEmpty() ? "saves" : cleaned;
    }

    private static void deleteQuietly(ContentResolver resolver, Uri uri) {
        try {
            resolver.delete(uri, null, null);
        } catch (RuntimeException ignored) {
            // Best-effort cleanup; the save failure is already surfaced to the caller.
        }
    }
}
