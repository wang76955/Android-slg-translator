package android.database;

import java.io.Closeable;

public interface Cursor extends Closeable {
    boolean moveToFirst();
    int getColumnIndex(String columnName);
    boolean isNull(int columnIndex);
    String getString(int columnIndex);
    long getLong(int columnIndex);
}
