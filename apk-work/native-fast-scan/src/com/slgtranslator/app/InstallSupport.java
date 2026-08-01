package com.slgtranslator.app;

import android.content.ContentValues;
import android.content.Context;
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
                    try (InputStream in = new FileInputStream(source);
                         OutputStream out = context.getContentResolver().openOutputStream(targetUri)) {
                        if (out != null) {
                            copy(in, out);
                        }
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

    /**
     * Resolves the requested patch path, falling back to the newest generated
     * patch when the logged path is stale or was cleaned up after install.
     */
    static File resolvePatchFile(Context context, String requested) {
        File direct = fileFrom(requested);
        if (direct != null && direct.isFile()) {
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
                if (!file.isFile() || !file.getName().endsWith(PATCH_SUFFIX)) {
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
            directories.add(new File(external, "SLG-Translator-Output"));
            directories.add(external);
        }
        directories.add(new File(context.getFilesDir(), "SLG-Translator-Output"));
        directories.add(context.getFilesDir());
        File cache = context.getCacheDir();
        if (cache != null) {
            directories.add(new File(cache, "SLG-Translator-Output"));
        }
        return directories;
    }

    private static void copy(InputStream in, OutputStream out) throws IOException {
        byte[] buffer = new byte[65536];
        int read;
        while ((read = in.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
    }
}
