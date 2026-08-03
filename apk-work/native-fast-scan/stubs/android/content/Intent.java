package android.content;

import android.net.Uri;

public class Intent {
    public static final String ACTION_MAIN = "android.intent.action.MAIN";
    public static final String CATEGORY_LAUNCHER = "android.intent.category.LAUNCHER";
    public static final int FLAG_GRANT_READ_URI_PERMISSION = 0x00000001;

    public Intent(String action) {
    }

    public Intent addCategory(String category) {
        return this;
    }

    public Intent setData(Uri uri) {
        return this;
    }

    public Intent setPackage(String packageName) {
        return this;
    }

    public Intent addFlags(int flags) {
        return this;
    }

    public Intent setAction(String action) {
        return this;
    }

    public Intent putExtra(String name, String value) {
        return this;
    }

    public Intent putExtra(String name, int value) {
        return this;
    }

    public String getStringExtra(String name) {
        return null;
    }

    public int getIntExtra(String name, int defaultValue) {
        return defaultValue;
    }
}
