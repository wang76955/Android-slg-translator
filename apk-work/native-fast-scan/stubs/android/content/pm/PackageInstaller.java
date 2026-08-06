package android.content.pm;

import android.content.IntentSender;

import java.io.IOException;
import java.io.OutputStream;

public class PackageInstaller {

    public static final int MODE_FULL_INSTALL = 1;
    public static final String ACTION_PACKAGE_INSTALLED = "android.content.pm.action.PACKAGE_INSTALLED";
    public static final String EXTRA_SESSION_ID = "android.content.pm.extra.SESSION_ID";
    public static final String EXTRA_PACKAGE_NAME = "android.content.pm.extra.PACKAGE_NAME";
    public static final String EXTRA_STATUS = "android.content.pm.extra.STATUS";
    public static final int STATUS_PENDING_USER_ACTION = -1;
    public static final int STATUS_SUCCESS = 0;
    public static final int STATUS_FAILURE = 1;
    public static final int STATUS_FAILURE_ABORTED = 2;

    public int createSession(SessionParams params) {
        return 0;
    }

    public Session openSession(int sessionId) {
        return null;
    }

    public void registerSessionCallback(SessionCallback callback) {
    }

    public void abandonSession(int sessionId) {
    }

    public static class SessionParams {
        public static final int MODE_FULL_INSTALL = 1;

        public SessionParams(int mode) {
        }

        public void setAppPackageName(String packageName) {
        }
    }

    public static class Session {
        public OutputStream openWrite(String name, long offsetBytes, long lengthBytes) {
            return null;
        }

        public void fsync(OutputStream out) throws IOException {
        }

        public void commit(IntentSender statusReceiver) {
        }

        public void close() {
        }

        public void abort() {
        }
    }

    public static abstract class SessionCallback {
        public void onSessionCreated(int sessionId) {
        }

        public void onSessionFinished(int sessionId, boolean success) {
        }

        public void onSessionProgressChanged(int sessionId, float progress) {
        }

        public void onSessionActive(int sessionId) {
        }

        public void onSessionBadgingChanged(int sessionId) {
        }
    }
}
