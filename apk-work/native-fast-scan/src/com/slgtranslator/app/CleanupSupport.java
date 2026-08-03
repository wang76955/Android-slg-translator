package com.slgtranslator.app;

import android.content.Context;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.net.URI;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * One-tap storage cleanup. The app copies multi-gigabyte source APKs into
 * installed-apks/ on every installed-app selection, and every patch run
 * writes another large APK into SLG-Translator-Output/. Old copies pile up
 * and fill the device, so this removes all re-creatable source copies plus
 * stale patch APKs while keeping the current selection source and the newest
 * patch.
 */
public final class CleanupSupport {

    private CleanupSupport() {
    }

    public static void cleanupStorage(Context context, PluginCall call) {
        try {
            String keepUri = call.getString("keepUri");
            File base = context.getExternalFilesDir(null);
            long freed = 0;
            int deleted = 0;
            int kept = 0;
            if (base != null) {
                File installedApks = new File(base, "installed-apks");
                CleanupResult source = deleteApkCopies(installedApks, keepUri);
                freed += source.freedBytes;
                deleted += source.deletedCount;
                kept += source.keptCount;

                File output = new File(base, "SLG-Translator-Output");
                CleanupResult patches = keepNewestApk(output);
                freed += patches.freedBytes;
                deleted += patches.deletedCount;
                kept += patches.keptCount;

                CleanupResult temp = deleteTempFiles(base);
                freed += temp.freedBytes;
                deleted += temp.deletedCount;
                kept += temp.keptCount;

                removeEmptyDir(new File(output, "SLG-Translator-Output"));
            }
            JSObject result = new JSObject();
            result.put("freedBytes", freed);
            result.put("deletedCount", deleted);
            result.put("keptCount", kept);
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("\u6e05\u7406\u5931\u8d25: " + (message == null ? e.toString() : message));
        }
    }

    /** Deletes every .apk under directory except an optional keep file. */
    private static CleanupResult deleteApkCopies(File directory, String keepUri) {
        File keep = fileFrom(keepUri);
        long freed = 0;
        int deleted = 0;
        int kept = 0;
        File[] files = directory == null ? null : directory.listFiles();
        if (files == null) {
            return new CleanupResult(0, 0, 0);
        }
        for (File file : files) {
            if (!file.isFile() || !file.getName().endsWith(".apk")) {
                continue;
            }
            if (keep != null && sameFile(file, keep)) {
                kept++;
                continue;
            }
            long size = file.length();
            if (file.delete()) {
                freed += size;
                deleted++;
            }
        }
        return new CleanupResult(freed, deleted, kept);
    }

    /** Deletes all but the newest .apk under the patch output directory. */
    private static CleanupResult keepNewestApk(File directory) {
        List<File> apks = new ArrayList<>();
        File[] files = directory == null ? null : directory.listFiles();
        if (files != null) {
            for (File file : files) {
                if (file.isFile() && file.getName().endsWith(".apk")) {
                    apks.add(file);
                }
            }
        }
        if (apks.size() <= 1) {
            return new CleanupResult(0, 0, apks.size());
        }
        Collections.sort(apks, new Comparator<File>() {
            @Override
            public int compare(File left, File right) {
                return Long.compare(right.lastModified(), left.lastModified());
            }
        });
        long freed = 0;
        int deleted = 0;
        for (int i = 1; i < apks.size(); i++) {
            long size = apks.get(i).length();
            if (apks.get(i).delete()) {
                freed += size;
                deleted++;
            }
        }
        return new CleanupResult(freed, deleted, 1);
    }

    /** Removes stray temp/idsig files left by interrupted operations. */
    private static CleanupResult deleteTempFiles(File base) {
        long freed = 0;
        int deleted = 0;
        File[] files = base == null ? null : base.listFiles();
        if (files == null) {
            return new CleanupResult(0, 0, 0);
        }
        for (File file : files) {
            if (file.isFile() && isTempName(file.getName())) {
                long size = file.length();
                if (file.delete()) {
                    freed += size;
                    deleted++;
                }
            }
        }
        // Interrupted installed-app copies live in installed-apks/ as
        // .partial/.tmp files; the top-level scan above cannot reach them.
        File installedApks = new File(base, "installed-apks");
        File[] partials = installedApks.listFiles();
        if (partials != null) {
            for (File file : partials) {
                if (file.isFile() && isTempName(file.getName())) {
                    long size = file.length();
                    if (file.delete()) {
                        freed += size;
                        deleted++;
                    }
                }
            }
        }
        return new CleanupResult(freed, deleted, 0);
    }

    private static boolean isTempName(String name) {
        return name.endsWith(".tmp") || name.endsWith(".partial")
                || name.endsWith(".idsig");
    }

    private static void removeEmptyDir(File directory) {
        if (directory == null || !directory.isDirectory()) {
            return;
        }
        File[] children = directory.listFiles();
        if (children == null || children.length == 0) {
            directory.delete();
        }
    }

    private static File fileFrom(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.startsWith("file:")) {
            try {
                return new File(URI.create(normalized));
            } catch (RuntimeException e) {
                return null;
            }
        }
        return new File(normalized);
    }

    /** Compares two files by canonical path (file URIs and plain paths can
     * differ in leading separators on Windows). */
    private static boolean sameFile(File left, File right) {
        try {
            return left.getCanonicalFile().equals(right.getCanonicalFile());
        } catch (java.io.IOException e) {
            return left.equals(right);
        }
    }

    private static final class CleanupResult {
        final long freedBytes;
        final int deletedCount;
        final int keptCount;

        CleanupResult(long freedBytes, int deletedCount, int keptCount) {
            this.freedBytes = freedBytes;
            this.deletedCount = deletedCount;
            this.keptCount = keptCount;
        }
    }
}
