package android.content.pm;

import android.content.Intent;
import java.util.List;

public class PackageManager {
    public List<ResolveInfo> queryIntentActivities(Intent intent, int flags) { return null; }
    public ApplicationInfo getApplicationInfo(String packageName, int flags) throws NameNotFoundException { return null; }
    public CharSequence getApplicationLabel(ApplicationInfo info) { return null; }

    public static class NameNotFoundException extends Exception {}
}
