package android.os;

import java.io.Closeable;
import java.io.IOException;

public class ParcelFileDescriptor implements Closeable {
    public int getFd() { return -1; }
    public void close() throws IOException {}
}
