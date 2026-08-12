package android.content;

import android.net.Uri;
import android.os.Parcelable;

public class Intent {
    public static final String ACTION_MAIN = "android.intent.action.MAIN";
    public static final String ACTION_SEND = "android.intent.action.SEND";
    public static final String CATEGORY_LAUNCHER = "android.intent.category.LAUNCHER";
    public static final String EXTRA_STREAM = "android.intent.extra.STREAM";
    public static final String EXTRA_INTENT = "android.intent.extra.INTENT";
    public static final int FLAG_GRANT_READ_URI_PERMISSION = 0x00000001;
    public static final int FLAG_ACTIVITY_NEW_TASK = 0x10000000;

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

    public Intent setType(String type) {
        return this;
    }

    public Intent putExtra(String name, String value) {
        return this;
    }

    public Intent putExtra(String name, int value) {
        return this;
    }

    public Intent putExtra(String name, Parcelable value) {
        return this;
    }

    public static Intent createChooser(Intent target, CharSequence title) {
        return target;
    }

    public String getStringExtra(String name) {
        return null;
    }

    public String getAction() {
        return null;
    }

    public int getIntExtra(String name, int defaultValue) {
        return defaultValue;
    }

    public Parcelable getParcelableExtra(String name) {
        return null;
    }
}
