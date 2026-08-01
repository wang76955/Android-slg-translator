package android.content;

import android.content.pm.PackageManager;
import java.io.File;

public class Context {
    public ContentResolver getContentResolver() { return null; }
    public File getFilesDir() { return null; }
    public File getExternalFilesDir(String type) { return null; }
    public File getCacheDir() { return null; }
    public PackageManager getPackageManager() { return null; }
    public String getPackageName() { return null; }
}
