package com.slgtranslator.app;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.IntentSender;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.util.Log;
import android.os.Build;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;

/**
 * Installs the patched APK through the Android PackageInstaller.Session
 * API instead of a FileProvider intent. OPPO's installer UI rejects
 * multi-GB APKs delivered over content:// URIs with "瀹夎鍖呭凡鎹熷潯"; the
 * session API streams the APK bytes directly to the system installer,
 * which handles large packages correctly on every OEM.
 */
public final class PackageInstallerSupport {

    private static final String TAG = "SLGInstaller";

    private PackageInstallerSupport() {
    }

    public static void installViaSession(Context context, PluginCall call) {
        String apkUri = call.getString("uri");
        if (apkUri == null || apkUri.isEmpty()) {
            call.reject("琛ヤ竵 APK URI 涓嶈兘涓虹┖");
            return;
        }
        File apk = fileFrom(apkUri);
        if (apk == null || !apk.isFile()) {
            call.reject("琛ヤ竵 APK 涓嶅瓨鍦? " + apkUri);
            return;
        }
        int sessionId = -1;
        PackageInstaller installer = null;
        try {
            installer = context.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                    PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            String packageName = call.getString("packageName");
            if (packageName != null && !packageName.isEmpty()) {
                params.setAppPackageName(packageName);
            }
            sessionId = installer.createSession(params);
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
            Log.i(TAG, "session created: " + sessionId + " size=" + size + " package=" + packageName);

            Intent broadcast = new Intent(PackageInstaller.ACTION_PACKAGE_INSTALLED);
            broadcast.setPackage(context.getPackageName());
            PendingIntent pending = PendingIntent.getBroadcast(context, 0, broadcast, PendingIntent.FLAG_MUTABLE);
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
                    int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS,
                            PackageInstaller.STATUS_FAILURE);
                    Log.i(TAG, "receiver status=" + status + " session=" + receivedSession
                            + " action=" + intent.getAction());
                    if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                        Intent confirm = (Intent) intent.getParcelableExtra(Intent.EXTRA_INTENT);
                        if (confirm != null) {
                            Log.i(TAG, "launching system confirmation: " + confirm);
                            confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            ctx.startActivity(confirm);
                        } else {
                            Log.w(TAG, "pending user action without confirmation intent");
                        }
                        return;
                    }
                    try {
                        ctx.unregisterReceiver(this);
                    } catch (RuntimeException ignored) {
                        // Receiver already unregistered or activity gone.
                    }
                    JSObject result = new JSObject();
                    result.put("sessionId", receivedSession);
                    result.put("installed", status == PackageInstaller.STATUS_SUCCESS);
                    result.put("status", status);
                    if (status == PackageInstaller.STATUS_SUCCESS) {
                        retained.resolve(result);
                    } else {
                        String detail = intent.getStringExtra("android.content.pm.extra.STATUS_MESSAGE");
                        retained.reject("瀹夎澶辫触锛堢姸鎬佺爜 " + status + "锛?"
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
            Log.i(TAG, "committing session=" + sessionId);
            session.commit(sender);
            Log.i(TAG, "session committed, closing");
            session.close();
            Log.i(TAG, "session closed");
        } catch (Exception e) {
            if (installer != null && sessionId != -1) {
                try {
                    installer.abandonSession(sessionId);
                } catch (RuntimeException ignored) {
                    // Session may already be finalized or abandoned by the system.
                }
            }
            String message = e.getMessage();
            call.reject("鍚姩瀹夎澶辫触: " + (message == null ? e.toString() : message));
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
