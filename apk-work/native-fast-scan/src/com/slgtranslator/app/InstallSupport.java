package com.slgtranslator.app;

import android.content.ContentValues;
import android.content.Context;
import android.content.ContentResolver;
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
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Install-time helpers for the patched APK: copying it to a user-visible
 * location so it can be found even when the in-app install hits a signature
 * conflict or gets cancelled, plus listing the patches already generated.
 */
public final class InstallSupport {

    private static final String SUB_DIR = "SLG-Translator";
    private static final String PATCH_SUFFIX = "-patched-signed.apk";

    private InstallSupport() {
    }

    public static void savePatchedApkToDownloads(Context context, PluginCall call) {
        String requested = call.getString("path");
        try {
            File source = resolvePatchFile(context, requested);
            if (source == null) {
                call.reject("补丁 APK 不存在，请重新翻译生成后再保存");
                return;
            }
            String fileName = source.getName();
            Uri targetUri = null;
            if (Build.VERSION.SDK_INT >= 29) {
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
                values.put(MediaStore.MediaColumns.MIME_TYPE, "application/vnd.android.package-archive");
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/" + SUB_DIR);
                targetUri = context.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (targetUri != null) {
                    try {
                        try (InputStream in = new FileInputStream(source);
                             OutputStream out = context.getContentResolver().openOutputStream(targetUri)) {
                            if (out == null) {
                                throw new IOException("output stream unavailable");
                            }
                            copy(in, out);
                        }
                    } catch (IOException copyFailure) {
                        deleteQuietly(context.getContentResolver(), targetUri);
                        throw copyFailure;
                    }
                }
            }
            if (targetUri == null) {
                File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), SUB_DIR);
                if (!dir.exists() && !dir.mkdirs()) {
                    throw new IOException("无法创建目录: " + dir);
                }
                File dest = new File(dir, fileName);
                try (InputStream in = new FileInputStream(source);
                     OutputStream out = new FileOutputStream(dest)) {
                    copy(in, out);
                }
                targetUri = Uri.fromFile(dest);
            }
            String visiblePath = "/storage/emulated/0/Download/" + SUB_DIR + "/" + fileName;
            JSObject result = new JSObject();
            result.put("path", visiblePath);
            result.put("uri", targetUri.toString());
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("保存补丁 APK 失败: " + (message == null ? e.toString() : message));
        }
    }

    public static void listPatchedApks(Context context, PluginCall call) {
        try {
            List<File> patches = new ArrayList<>();
            Set<String> seen = new HashSet<>();
            for (File dir : outputDirectories(context)) {
                File[] files = dir.listFiles();
                if (files == null) {
                    continue;
                }
                for (File file : files) {
                    if (!file.isFile() || !file.getName().endsWith(PATCH_SUFFIX)) {
                        continue;
                    }
                    if (!seen.add(file.getAbsolutePath())) {
                        continue;
                    }
                    patches.add(file);
                }
            }
            patches.sort((left, right) -> Long.compare(right.lastModified(), left.lastModified()));
            JSArray items = new JSArray();
            for (File file : patches) {
                JSObject item = new JSObject();
                item.put("name", file.getName());
                item.put("path", file.getAbsolutePath());
                item.put("size", file.length());
                item.put("modifiedAt", file.lastModified());
                items.put(item);
            }
            JSObject result = new JSObject();
            result.put("patches", items);
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("读取补丁列表失败: " + (message == null ? e.toString() : message));
        }
    }

    public static void deletePatchedApk(Context context, PluginCall call) {
        try {
            File target = validateDeleteTarget(context, call.getString("path"));

            // Re-check the exact file immediately before deletion so a changed path
            // cannot turn this operation into a broader cleanup.
            if (!isSafePatchFile(context, target)) {
                call.reject("删除目标已失效或不再位于专用输出目录中");
                return;
            }
            if (!target.delete()) {
                call.reject("删除补丁 APK 失败，文件可能已被移除");
                return;
            }
            JSObject result = new JSObject();
            result.put("deleted", true);
            result.put("path", target.getAbsolutePath());
            call.resolve(result);
        } catch (IllegalArgumentException e) {
            call.reject(e.getMessage());
        } catch (IOException e) {
            call.reject("校验删除路径失败: " + e.getMessage());
        } catch (RuntimeException e) {
            String message = e.getMessage();
            call.reject("删除补丁 APK 失败: " + (message == null ? e.toString() : message));
        }
    }

    private static File validateDeleteTarget(Context context, String requested) throws IOException {
        if (requested == null || requested.trim().isEmpty()) {
            throw new IllegalArgumentException("删除路径不能为空");
        }
        String path = requested.trim();
        if (hasUriScheme(path)) {
            throw new IllegalArgumentException("不允许使用 URI 路径删除 APK");
        }
        File target = new File(path);
        if (!target.isAbsolute()) {
            throw new IllegalArgumentException("删除路径必须是绝对文件路径");
        }
        if (!isSafePatchFile(context, target)) {
            throw new IllegalArgumentException("删除路径不是专用输出目录中的补丁 APK");
        }
        return target;
    }

    private static boolean isSafePatchFile(Context context, File target) throws IOException {
        if (target == null || !target.isAbsolute()
                || !target.isFile() || !target.getName().endsWith(PATCH_SUFFIX)) {
            return false;
        }

        String absolutePath = target.getAbsolutePath();
        String canonicalPath = target.getCanonicalPath();
        if (!canonicalPath.equals(absolutePath)) {
            return false;
        }

        File parent = target.getParentFile();
        if (parent == null) {
            return false;
        }
        String canonicalParent = parent.getCanonicalPath();
        for (File output : outputDirectories(context)) {
            if (canonicalParent.equals(output.getCanonicalPath())) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasUriScheme(String value) {
        int colon = value.indexOf(':');
        if (colon <= 0) {
            return false;
        }
        if (colon == 1 && value.length() > 2
                && (value.charAt(2) == '\\' || value.charAt(2) == '/')) {
            return false;
        }
        for (int i = 0; i < colon; i++) {
            char ch = value.charAt(i);
            if (i == 0) {
                if (!Character.isLetter(ch)) {
                    return false;
                }
            } else if (!Character.isLetterOrDigit(ch) && ch != '+' && ch != '-' && ch != '.') {
                return false;
            }
        }
        return true;
    }

    /**
     * Resolves the requested patch path, falling back to the newest generated
     * patch when the logged path is stale or was cleaned up after install.
     */
    static File resolvePatchFile(Context context, String requested) {
        File direct = fileFrom(requested);
        if (isSafePatchFileQuietly(context, direct)) {
            return direct;
        }
        File best = null;
        long bestTime = -1L;
        for (File dir : outputDirectories(context)) {
            File[] files = dir.listFiles();
            if (files == null) {
                continue;
            }
            for (File file : files) {
                if (!isSafePatchFileQuietly(context, file)) {
                    continue;
                }
                if (requested != null && !requested.isEmpty() && requested.contains(file.getName())) {
                    return file;
                }
                if (file.lastModified() > bestTime) {
                    bestTime = file.lastModified();
                    best = file;
                }
            }
        }
        return best;
    }

    private static boolean isSafePatchFileQuietly(Context context, File file) {
        try {
            return isSafePatchFile(context, file);
        } catch (IOException ignored) {
            return false;
        }
    }

    private static File fileFrom(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.startsWith("file://")) {
            try {
                return new File(Uri.parse(normalized).getPath());
            } catch (RuntimeException e) {
                return null;
            }
        }
        return new File(normalized);
    }

    private static List<File> outputDirectories(Context context) {
        List<File> directories = new ArrayList<>();
        File external = context.getExternalFilesDir(null);
        if (external != null) {
            addOutputDirectory(directories, new File(external, "SLG-Translator-Output"));
        }
        File files = context.getFilesDir();
        if (files != null) {
            addOutputDirectory(directories, new File(files, "SLG-Translator-Output"));
        }
        File cache = context.getCacheDir();
        if (cache != null) {
            addOutputDirectory(directories, new File(cache, "SLG-Translator-Output"));
        }
        return directories;
    }

    private static void addOutputDirectory(List<File> directories, File directory) {
        try {
            if (!directory.exists() && !directory.mkdirs()) {
                return;
            }
            if (!directory.isDirectory()) {
                return;
            }
            if (!directory.getCanonicalPath().equals(directory.getAbsolutePath())) {
                return;
            }
            for (File existing : directories) {
                if (existing.getCanonicalPath().equals(directory.getCanonicalPath())) {
                    return;
                }
            }
            directories.add(directory);
        } catch (IOException ignored) {
            // An unreadable or non-canonical output directory is not app-owned.
        }
    }

    private static void copy(InputStream in, OutputStream out) throws IOException {
        byte[] buffer = new byte[65536];
        int read;
        while ((read = in.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
    }

    /** Removes a MediaStore row that was inserted but never fully written. */
    private static void deleteQuietly(ContentResolver resolver, Uri uri) {
        try {
            resolver.delete(uri, null, null);
        } catch (RuntimeException ignored) {
            // Best-effort cleanup; the save failure is already surfaced to the caller.
        }
    }
}
