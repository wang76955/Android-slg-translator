package com.slgtranslator.app;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.IntentSender;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** PackageInstaller bridge for one base APK plus all of its split APKs. */
public final class PackageInstallerSupport {
    private static final String TAG = "SLGInstaller";

    private PackageInstallerSupport() {
    }

    /** Legacy single-APK bridge; it now delegates to the collection installer. */
    public static void installViaSession(Context context, PluginCall call) {
        try {
            installApkSet(context, apkSetFromCall(call), call);
        } catch (Exception error) {
            call.reject("APK set is invalid: " + messageOf(error));
        }
    }

    /** Static evidence the caller precomputes before installation. */
    public static final class StaticEvidence {
        public final boolean allValid;

        public StaticEvidence(boolean allValid) {
            this.allValid = allValid;
        }

        public static StaticEvidence missing() {
            return new StaticEvidence(false);
        }
    }

    /** Writes base first and every split into one PackageInstaller.Session. */
    public static void installApkSet(Context context, InstalledApkSet apkSet, PluginCall call) {
        installApkSet(context, apkSet, call, StaticEvidence.missing());
    }

    /** Writes base first and every split into one PackageInstaller.Session. */
    public static void installApkSet(Context context, InstalledApkSet apkSet, PluginCall call,
            StaticEvidence evidence) {
        int sessionId = -1;
        PackageInstaller installer = null;
        PackageInstaller.Session session = null;
        try {
            validateApkSet(context, apkSet);
            installer = context.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                    PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            if (apkSet.packageName != null && !apkSet.packageName.isEmpty()
                    && !"unknown".equals(apkSet.packageName)) {
                params.setAppPackageName(apkSet.packageName);
            }
            sessionId = installer.createSession(params);
            session = installer.openSession(sessionId);
            writeApk(session, apkSet.baseApk, "base.apk");
            for (int index = 0; index < apkSet.splitApks.size(); index++) {
                writeApk(session, apkSet.splitApks.get(index), splitEntryName(apkSet, index));
            }

            Intent broadcast = new Intent(PackageInstaller.ACTION_PACKAGE_INSTALLED);
            broadcast.setPackage(context.getPackageName());
            PendingIntent pending = PendingIntent.getBroadcast(context, 0, broadcast, PendingIntent.FLAG_MUTABLE);
            final int expectedSession = sessionId;
            final PluginCall retained = call;
            final Context appContext = context.getApplicationContext();
            BroadcastReceiver receiver = new BroadcastReceiver() {
                @Override
                public void onReceive(Context ctx, Intent intent) {
                    int receivedSession = intent.getIntExtra(
                            PackageInstaller.EXTRA_SESSION_ID, -1);
                    if (receivedSession != expectedSession) return;
                    int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS,
                            PackageInstaller.STATUS_FAILURE);
                    if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                        Intent confirm = (Intent) intent.getParcelableExtra(Intent.EXTRA_INTENT);
                        if (confirm != null) {
                            confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            ctx.startActivity(confirm);
                        }
                        return;
                    }
                    try {
                        ctx.unregisterReceiver(this);
                    } catch (RuntimeException ignored) {
                        // Receiver may already have been unregistered.
                    }
                    JSObject result = new JSObject()
                            .put("sessionId", receivedSession)
                            .put("installed", status == PackageInstaller.STATUS_SUCCESS)
                            .put("staticAsserts", evidence != null && evidence.allValid)
                            .put("status", status)
                            .put("splitCount", apkSet.splitApks.size());
                    if (status == PackageInstaller.STATUS_SUCCESS) {
                        retained.resolve(result);
                    } else {
                        String detail = intent.getStringExtra(
                                "android.content.pm.extra.STATUS_MESSAGE");
                        retained.reject("PackageInstaller failed: " + status
                                + (detail == null || detail.isEmpty() ? "" : ": " + detail));
                    }
                }
            };
            IntentFilter filter = new IntentFilter(PackageInstaller.ACTION_PACKAGE_INSTALLED);
            if (Build.VERSION.SDK_INT >= 33) {
                appContext.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
            } else {
                appContext.registerReceiver(receiver, filter);
            }
            Log.i(TAG, "committing session=" + sessionId + " apkCount="
                    + (apkSet.splitApks.size() + 1));
            IntentSender sender = pending.getIntentSender();
            session.commit(sender);
            session.close();
        } catch (Exception error) {
            if (session != null) {
                try {
                    session.close();
                } catch (RuntimeException ignored) {
                    // Continue to abandon the session below.
                }
            }
            if (installer != null && sessionId != -1) {
                try {
                    installer.abandonSession(sessionId);
                } catch (RuntimeException ignored) {
                    // Session may already be finalized by the system.
                }
            }
            call.reject("PackageInstaller failed: " + messageOf(error));
        }
    }

    private static InstalledApkSet apkSetFromCall(PluginCall call) {
        String baseUri = call.getString("baseUri");
        if (baseUri == null || baseUri.isEmpty()) baseUri = call.getString("uri");
        if (baseUri == null || baseUri.isEmpty()) {
            throw new IllegalArgumentException("base APK URI is required");
        }
        List<String> splitUris = new ArrayList<>();
        List<String> splitNames = new ArrayList<>();
        JSArray values = call.getArray("splitUris");
        JSArray names = call.getArray("splitNames");
        if (values != null) {
            for (int index = 0; index < values.length(); index++) {
                String value = arrayString(values, index);
                if (value.isEmpty()) throw new IllegalArgumentException("split URI is empty");
                splitUris.add(value);
                splitNames.add(arrayString(names, index));
            }
        }
        String packageName = call.getString("packageName");
        if (packageName == null || packageName.trim().isEmpty()) packageName = "unknown";
        long versionCode = -1L;
        String version = call.getString("versionCode");
        if (version != null && !version.trim().isEmpty()) {
            versionCode = Long.parseLong(version.trim());
        }
        return InstalledApkSet.fromUris(baseUri, splitUris, packageName, versionCode, splitNames);
    }

    private static String arrayString(JSArray array, int index) {
        if (array == null) return "";
        Object value = array.opt(index);
        if (value == null) return "";
        String text = String.valueOf(value);
        return "null".equals(text) ? "" : text;
    }

    private static void writeApk(PackageInstaller.Session session, File apk, String entryName)
            throws IOException {
        long size = apk.length();
        try (FileInputStream input = new FileInputStream(apk);
             OutputStream output = session.openWrite(entryName, 0, size)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
            session.fsync(output);
        }
    }

    private static String splitEntryName(InstalledApkSet apkSet, int index) {
        String name = apkSet.splitNameAt(index);
        return name.endsWith(".apk") ? name : name + ".apk";
    }

    /** Validate package/version/split/signature metadata before opening a session. */
    private static void validateApkSet(Context context, InstalledApkSet apkSet) throws Exception {
        if (apkSet == null || apkSet.baseApk == null || !apkSet.baseApk.isFile()) {
            throw new IOException("base APK is missing");
        }
        for (File split : apkSet.splitApks) {
            if (split == null || !split.isFile()) throw new IOException("split APK is missing");
        }
        Object packageManager = context.getPackageManager();
        Method parser = packageManager.getClass().getMethod(
                "getPackageArchiveInfo", String.class, int.class);
        int flags = archiveInfoFlags();
        List<File> all = apkSet.allApks();
        Object baseInfo = parser.invoke(packageManager, apkSet.baseApk.getAbsolutePath(), flags);
        if (baseInfo == null) throw new IOException("base manifest is unreadable");
        String packageName = stringField(baseInfo, "packageName");
        long versionCode = versionField(baseInfo);
        if (!"unknown".equals(apkSet.packageName) && !apkSet.packageName.equals(packageName)) {
            throw new IOException("packageName mismatch");
        }
        String signature = signatureOf(baseInfo);
        if (signature == null) throw new IOException("signature metadata is unavailable");
        for (int index = 1; index < all.size(); index++) {
            Object splitInfo = parser.invoke(packageManager, all.get(index).getAbsolutePath(), flags);
            if (splitInfo == null) throw new IOException("split manifest is unreadable");
            if (!packageName.equals(stringField(splitInfo, "packageName"))) {
                throw new IOException("packageName mismatch in split");
            }
            if (versionCode >= 0 && versionField(splitInfo) != versionCode) {
                throw new IOException("versionCode mismatch in split");
            }
            String expected = splitEntryName(apkSet, index - 1).replaceAll("\\.apk$", "");
            if (!expected.equals(splitNameField(splitInfo))) {
                throw new IOException("splitName mismatch in split");
            }
            if (!signature.equals(signatureOf(splitInfo))) {
                throw new IOException("signature mismatch in split");
            }
        }
        if (apkSet.versionCode >= 0 && versionCode >= 0 && apkSet.versionCode != versionCode) {
            throw new IOException("versionCode mismatch");
        }
    }

    private static int archiveInfoFlags() {
        try {
            return Class.forName("android.content.pm.PackageManager")
                    .getField("GET_SIGNING_CERTIFICATES").getInt(null);
        } catch (Exception ignored) {
            return 0;
        }
    }

    private static String stringField(Object object, String fieldName) throws Exception {
        Object value = object.getClass().getField(fieldName).get(object);
        return value == null ? "" : String.valueOf(value);
    }

    private static long versionField(Object object) throws Exception {
        try {
            Method method = object.getClass().getMethod("getLongVersionCode");
            Object value = method.invoke(object);
            return value instanceof Number ? ((Number) value).longValue() : -1L;
        } catch (NoSuchMethodException ignored) {
            Object value = object.getClass().getField("versionCode").get(object);
            return value instanceof Number ? ((Number) value).longValue() : -1L;
        }
    }

    private static String splitNameField(Object object) throws Exception {
        Object value = object.getClass().getField("splitNames").get(object);
        if (value instanceof String[] && ((String[]) value).length == 1) {
            return ((String[]) value)[0];
        }
        throw new IOException("splitName metadata is unavailable");
    }

    private static String signatureOf(Object packageInfo) throws Exception {
        try {
            Object signingInfo = packageInfo.getClass().getField("signingInfo").get(packageInfo);
            if (signingInfo != null) {
                Method signers = signingInfo.getClass().getMethod("getApkContentsSigners");
                Object value = signers.invoke(signingInfo);
                if (value instanceof Object[] && ((Object[]) value).length > 0) {
                    return Arrays.toString((Object[]) value);
                }
            }
        } catch (NoSuchFieldException ignored) {
            // Older Android versions expose PackageInfo.signatures instead.
        }
        Object value = packageInfo.getClass().getField("signatures").get(packageInfo);
        if (value instanceof Object[] && ((Object[]) value).length > 0) {
            return Arrays.toString((Object[]) value);
        }
        return null;
    }

    private static String messageOf(Exception error) {
        return error.getMessage() == null ? error.toString() : error.getMessage();
    }

    private static File fileFrom(String value) {
        if (value == null || value.isEmpty()) return null;
        String normalized = value.trim();
        if (normalized.startsWith("file://")) {
            try {
                return new File(Uri.parse(normalized).getPath());
            } catch (RuntimeException error) {
                return null;
            }
        }
        return new File(normalized);
    }
}
