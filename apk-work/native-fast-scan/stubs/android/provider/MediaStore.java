package android.provider;

import android.net.Uri;

public final class MediaStore {
    public static final class MediaColumns {
        public static final String DISPLAY_NAME = "_display_name";
        public static final String MIME_TYPE = "mime_type";
        public static final String RELATIVE_PATH = "relative_path";
        private MediaColumns() {}
    }

    public static final class Downloads {
        public static final Uri EXTERNAL_CONTENT_URI = Uri.parse("content://media/external/downloads");
        private Downloads() {}
    }

    private MediaStore() {}
}
