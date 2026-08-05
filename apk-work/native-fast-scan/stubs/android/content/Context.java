package android.content;

import android.content.pm.PackageManager;
import android.net.Uri;

import java.io.File;

public class Context {
    public ContentResolver getContentResolver() { return null; }
    public File getCacheDir() { return null; }
    public File getFilesDir() { return null; }
    public File getNoBackupFilesDir() { return null; }
    public File getExternalFilesDir(String type) { return null; }
    public PackageManager getPackageManager() { return null; }
    public String getPackageName() { return null; }
    public Context getApplicationContext() { return null; }
    public Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter) { return null; }
    public void unregisterReceiver(BroadcastReceiver receiver) {}
    public void startActivity(Intent intent) {}
}
