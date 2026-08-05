package com.slgtranslator.app;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.IntentSender;
import android.content.pm.PackageInstaller;
import android.net.Uri;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;

/**
 * Installs the patched APK through the Android PackageInstaller.Session
 * API instead of a FileProvider intent. OPPO's installer UI rejects
 * multi-GB APKs delivered over content:// URIs with "安装包已损坏"; the
 * session API streams the APK bytes directly to the system installer,
 * which handles large packages correctly on every OEM.
 */
public final class PackageInstallerSupport {

    private PackageInstallerSupport() {
    }

    public static void installViaSession(Context context, PluginCall call) {
        String apkUri = call.getString("uri");
        if (apkUri == null || apkUri.isEmpty()) {
            call.reject("补丁 APK URI 不能为空");
            return;
        }
        File apk = fileFrom(apkUri);
        if (apk == null || !apk.isFile()) {
            call.reject("补丁 APK 不存在: " + apkUri);
            return;
        }
        try {
            PackageInstaller installer = context.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                    PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            String packageName = call.getString("packageName");
            if (packageName != null && !packageName.isEmpty()) {
                params.setAppPackageName(packageName);
            }
            int sessionId = installer.createSession(params);
            PackageInstaller.Session session = installer.openSession(sessionId);
            long size = apk.length();
            try (FileInputStream input = new FileInputStream(apk);
                 OutputStream output = session.openWrite("base.apk", 0, size)) {
                byte[] buffer = new byte[1024 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) {
                    output.write(buffer, 0, read);
                }
                session.fsync(output);
            }
            session.close();

            Intent broadcast = new Intent(PackageInstaller.ACTION_PACKAGE_INSTALLED);
            broadcast.setPackage(context.getPackageName());
            PendingIntent pending = PendingIntent.getBroadcast(context, 0, broadcast, 0);
            IntentSender sender = pending.getIntentSender();

            final int expectedSession = sessionId;
            final PluginCall retained = call;
            final Context appContext = context.getApplicationContext();
            BroadcastReceiver receiver = new BroadcastReceiver() {
                @Override
                public void onReceive(Context ctx, Intent intent) {
                    int receivedSession = intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1);
                    if (receivedSession != expectedSession) {
                        return;
                    }
                    try {
                        ctx.unregisterReceiver(this);
                    } catch (RuntimeException ignored) {
                        // Receiver already unregistered or activity gone.
                    }
                    int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS,
                            PackageInstaller.STATUS_FAILURE);
                    JSObject result = new JSObject();
                    result.put("sessionId", receivedSession);
                    result.put("installed", status == PackageInstaller.STATUS_SUCCESS);
                    result.put("status", status);
                    if (status == PackageInstaller.STATUS_SUCCESS) {
                        retained.resolve(result);
                    } else {
                        String detail = intent.getStringExtra("android.content.pm.extra.STATUS_MESSAGE");
                        retained.reject("安装失败（状态码 " + status + "）"
                                + (detail == null || detail.isEmpty() ? "" : ": " + detail));
                    }
                }
            };
            IntentFilter filter = new IntentFilter(PackageInstaller.ACTION_PACKAGE_INSTALLED);
            appContext.registerReceiver(receiver, filter);
            session.commit(sender);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("启动安装失败: " + (message == null ? e.toString() : message));
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
}
