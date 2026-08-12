package android.os;

import java.io.File;

/** Minimal JVM test stub for the Android framework StatFs API. */
public class StatFs {
    private final String path;

    public StatFs(String path) {
        this.path = path;
    }

    public long getAvailableBytes() {
        return new File(path == null ? "." : path).getUsableSpace();
    }
}
