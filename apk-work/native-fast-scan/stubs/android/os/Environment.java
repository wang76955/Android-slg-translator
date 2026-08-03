package android.os;

import java.io.File;

public class Environment {
    public static final String DIRECTORY_DOWNLOADS = "Download";
    public static File getExternalStorageDirectory() { return new File("/storage/emulated/0"); }
    public static File getExternalStoragePublicDirectory(String type) { return new File("/storage/emulated/0/" + type); }
    private Environment() {}
}
