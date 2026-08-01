package com.slgtranslator.app;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;

public final class InstalledAppSource {
    private static final int COPY_BUFFER_SIZE = 1024 * 1024;
    private static final ExecutorService WORKER = Executors.newSingleThreadExecutor(new ThreadFactory() {
        @Override
        public Thread newThread(Runnable runnable) {
            return new Thread(runnable, "installed-app-worker");
        }
    });

    private InstalledAppSource() {}

    public static void listInstalledApps(final Context context, final PluginCall call) {
        WORKER.execute(new Runnable() {
            @Override
            public void run() {
                listInstalledAppsOnWorker(context, call);
            }
        });
    }

    private static void listInstalledAppsOnWorker(Context context, PluginCall call) {
        try {
            PackageManager packageManager = context.getPackageManager();
            List<ResolveInfo> launchers = queryLauncherApps(packageManager);
            Map<String, AppEntry> unique = new HashMap<>();
            for (ResolveInfo resolveInfo : launchers) {
                ApplicationInfo applicationInfo = applicationInfo(resolveInfo);
                if (applicationInfo == null || applicationInfo.packageName == null) {
                    continue;
                }
                String packageName = applicationInfo.packageName;
                if (packageName.equals(context.getPackageName()) || unique.containsKey(packageName)) {
                    continue;
                }
                unique.put(packageName, new AppEntry(labelOf(packageManager, applicationInfo), packageName));
            }

            List<AppEntry> apps = new ArrayList<>(unique.values());
            Collections.sort(apps, new Comparator<AppEntry>() {
                @Override
                public int compare(AppEntry left, AppEntry right) {
                    int labelOrder = left.label.compareToIgnoreCase(right.label);
                    return labelOrder != 0 ? labelOrder : left.packageName.compareTo(right.packageName);
                }
            });
            JSArray resultApps = new JSArray();
            for (AppEntry app : apps) {
                resultApps.put(new JSObject().put("label", app.label).put("packageName", app.packageName));
            }
            call.resolve(new JSObject().put("apps", resultApps));
        } catch (RuntimeException error) {
            call.reject("Unable to list launchable apps. Try reopening the app.");
        }
    }

    public static void selectInstalledApp(final Context context, final PluginCall call) {
        final String packageName = call.getString("packageName");
        if (packageName == null || packageName.trim().isEmpty()) {
            call.reject("Choose an installed app first.");
            return;
        }
        WORKER.execute(new Runnable() {
            @Override
            public void run() {
                copySelectedApp(context, call, packageName);
            }
        });
    }

    private static void copySelectedApp(Context context, PluginCall call, String packageName) {
        File partial = null;
        try {
            PackageManager packageManager = context.getPackageManager();
            if (!isLauncherPackage(packageManager, packageName) || packageName.equals(context.getPackageName())) {
                call.reject("That app is no longer available. Refresh the installed app list.");
                return;
            }

            ApplicationInfo applicationInfo = packageManager.getApplicationInfo(packageName, 0);
            if (applicationInfo.sourceDir == null) {
                call.reject("The selected app has no readable base APK.");
                return;
            }
            File source = new File(applicationInfo.sourceDir);
            if (!source.isFile()) {
                call.reject("The selected app was removed. Refresh the installed app list.");
                return;
            }

            File directory = installedApksDir(context);
            if ((!directory.exists() && !directory.mkdirs()) || !directory.isDirectory()) {
                call.reject("Cannot prepare private storage for the app APK. Free space and try again.");
                return;
            }
            cleanStalePartials(directory);
            File output = new File(directory, fingerprint(packageName, source) + ".apk");
            partial = new File(directory, output.getName() + "." + UUID.randomUUID().toString() + ".partial");
            if (!output.isFile()) {
                if (partial.exists() && !partial.delete()) {
                    throw new IOException("stale partial");
                }
                copyAndSync(source, partial);
                if (!partial.renameTo(output)) {
                    throw new IOException("atomic rename");
                }
            }
            partial = null;
            markNewest(directory, output);
            cleanOldApks(directory, output);

            int splitCount = applicationInfo.splitSourceDirs == null ? 0 : applicationInfo.splitSourceDirs.length;
            String label = labelOf(packageManager, applicationInfo);
            call.resolve(new JSObject()
                    .put("uri", Uri.fromFile(output).toString())
                    .put("name", label + ".apk")
                    .put("packageName", packageName)
                    .put("source", "installed")
                    .put("splitApk", splitCount > 0)
                    .put("splitCount", splitCount));
        } catch (PackageManager.NameNotFoundException error) {
            call.reject("The selected app was uninstalled. Refresh the installed app list.");
        } catch (IOException error) {
            call.reject("Could not copy the app APK. Free storage space and try again.");
        } catch (RuntimeException error) {
            call.reject("Could not access the selected app. Refresh the list and try again.");
        } finally {
            if (partial != null && partial.exists()) {
                partial.delete();
            }
        }
    }

    private static List<ResolveInfo> queryLauncherApps(PackageManager packageManager) {
        Intent intent = new Intent(Intent.ACTION_MAIN);
        intent.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> result = packageManager.queryIntentActivities(intent, 0);
        return result == null ? Collections.<ResolveInfo>emptyList() : result;
    }

    private static boolean isLauncherPackage(PackageManager packageManager, String packageName) {
        for (ResolveInfo resolveInfo : queryLauncherApps(packageManager)) {
            ApplicationInfo applicationInfo = applicationInfo(resolveInfo);
            if (applicationInfo != null && packageName.equals(applicationInfo.packageName)) {
                return true;
            }
        }
        return false;
    }

    private static ApplicationInfo applicationInfo(ResolveInfo resolveInfo) {
        return resolveInfo == null || resolveInfo.activityInfo == null
                ? null
                : resolveInfo.activityInfo.applicationInfo;
    }

    private static String labelOf(PackageManager packageManager, ApplicationInfo applicationInfo) {
        CharSequence label = packageManager.getApplicationLabel(applicationInfo);
        String value = label == null ? "" : label.toString().trim();
        return value.isEmpty() ? applicationInfo.packageName : value;
    }

    /**
     * Persisted location for copied app APKs. The app cache directory is
     * aggressively cleared by OEM cleanup policies (which already broke
     * patch builds when the source APK disappeared), so the copy lives in
     * the app's persistent external files directory instead.
     */
    static File installedApksDir(Context context) {
        File external = context.getExternalFilesDir(null);
        File base = external != null ? external : context.getFilesDir();
        return new File(base, "installed-apks");
    }

    private static void copyAndSync(File source, File partial) throws IOException {
        byte[] buffer = new byte[COPY_BUFFER_SIZE];
        try (FileInputStream input = new FileInputStream(source);
             FileOutputStream output = new FileOutputStream(partial)) {
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            output.flush();
            output.getFD().sync();
        }
    }

    private static String fingerprint(String packageName, File source) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            String identity = packageName + "/" + source.lastModified() + "/" + source.length();
            byte[] bytes = digest.digest(identity.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(bytes.length * 2);
            for (byte value : bytes) {
                hex.append(String.format(Locale.US, "%02x", value & 0xff));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    private static void markNewest(File directory, File output) throws IOException {
        long newest = 0L;
        File[] files = directory.listFiles();
        if (files != null) {
            for (File file : files) {
                if (!file.equals(output) && file.getName().endsWith(".apk")) {
                    newest = Math.max(newest, file.lastModified());
                }
            }
        }
        long timestamp = Math.max(System.currentTimeMillis(), newest + 1);
        if (!output.setLastModified(timestamp)) {
            throw new IOException("cache recency");
        }
    }

    private static void cleanStalePartials(File directory) throws IOException {
        File[] files = directory.listFiles();
        if (files == null) {
            return;
        }
        for (File file : files) {
            if (file.getName().endsWith(".partial") && !file.delete()) {
                throw new IOException("stale partial cleanup");
            }
        }
    }

    private static void cleanOldApks(File directory, File keep) {
        File[] files = directory.listFiles();
        if (files == null) {
            return;
        }
        List<File> finals = new ArrayList<>();
        for (File file : files) {
            if (file.getName().endsWith(".apk")) {
                finals.add(file);
            }
        }
        Collections.sort(finals, new Comparator<File>() {
            @Override
            public int compare(File left, File right) {
                return Long.compare(right.lastModified(), left.lastModified());
            }
        });
        for (int index = 0; index < finals.size(); index++) {
            File file = finals.get(index);
            if (index >= 2 && !file.equals(keep)) {
                file.delete();
            }
        }
    }

    private static final class AppEntry {
        final String label;
        final String packageName;

        AppEntry(String label, String packageName) {
            this.label = label;
            this.packageName = packageName;
        }
    }
}
