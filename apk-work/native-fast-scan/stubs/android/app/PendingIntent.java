package android.app;

import android.content.Context;
import android.content.Intent;
import android.content.IntentSender;

public class PendingIntent {
    public static final int FLAG_IMMUTABLE = 0x04000000;
    public static final int FLAG_MUTABLE = 0x02000000;
    public static final int FLAG_UPDATE_CURRENT = 0x08000000;

    public static PendingIntent getBroadcast(Context context, int requestCode, Intent intent, int flags) {
        return null;
    }

    public IntentSender getIntentSender() {
        return null;
    }
}
