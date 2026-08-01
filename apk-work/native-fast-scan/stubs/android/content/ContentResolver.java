package android.content;

import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.InputStream;

public class ContentResolver {
    public InputStream openInputStream(Uri uri) { return null; }
    public ParcelFileDescriptor openFileDescriptor(Uri uri, String mode) { return null; }
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) { return null; }
    public java.io.OutputStream openOutputStream(Uri uri) { return null; }
    public Uri insert(Uri uri, ContentValues values) { return null; }
}
