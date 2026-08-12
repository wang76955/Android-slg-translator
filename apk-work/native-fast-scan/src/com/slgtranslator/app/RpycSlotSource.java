package com.slgtranslator.app;

import android.content.Context;

import java.io.Closeable;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.util.Arrays;
import java.util.zip.InflaterInputStream;

/**
 * File-backed source for one Ren'Py compiled script. The RPYC container is
 * copied once, then callers open only the selected zlib slot instead of
 * retaining the compressed container and inflated pickle together.
 */
public final class RpycSlotSource implements Closeable {
    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
    private static final int COPY_BUFFER_SIZE = 64 * 1024;

    private final File file;
    private final File workDirectory;
    private boolean closed;

    private RpycSlotSource(File file, File workDirectory) {
        this.file = file;
        this.workDirectory = workDirectory;
    }

    /** Copy an RPYC byte array into the bounded cache-backed source. */
    public static RpycSlotSource fromBytes(Context context, byte[] data, String label)
            throws IOException {
        if (data == null) {
            throw new IOException("renpy_invalid_range: RPYC data is null");
        }
        RenpyResourceLimits.checkCompressed(data.length);
        File directory = createWorkDirectory(context);
        File target = null;
        try {
            target = File.createTempFile("rpyc-", ".bin", directory);
            try (FileOutputStream output = new FileOutputStream(target)) {
                int offset = 0;
                while (offset < data.length) {
                    int count = Math.min(COPY_BUFFER_SIZE, data.length - offset);
                    output.write(data, offset, count);
                    offset += count;
                }
                output.getFD().sync();
            }
            return new RpycSlotSource(target, directory);
        } catch (Throwable error) {
            if (target != null) {
                target.delete();
            }
            directory.delete();
            if (error instanceof IOException) {
                throw (IOException) error;
            }
            throw new IOException("failed to create RPYC work file: " + error, error);
        }
    }

    /** Copy one stream into the bounded cache-backed source. */
    public static RpycSlotSource fromInputStream(Context context, InputStream input, String label)
            throws IOException {
        if (input == null) {
            throw new IOException("renpy_invalid_range: RPYC input is null");
        }
        File directory = createWorkDirectory(context);
        File target = null;
        try {
            target = File.createTempFile("rpyc-", ".bin", directory);
            byte[] buffer = new byte[COPY_BUFFER_SIZE];
            long total = 0;
            try (InputStream source = input; FileOutputStream output = new FileOutputStream(target)) {
                int read;
                while ((read = source.read(buffer)) != -1) {
                    RenpyResourceLimits.checkInterrupted();
                    total += read;
                    RenpyResourceLimits.checkCompressed(total);
                    output.write(buffer, 0, read);
                }
                output.getFD().sync();
            }
            return new RpycSlotSource(target, directory);
        } catch (Throwable error) {
            if (target != null) {
                target.delete();
            }
            directory.delete();
            if (error instanceof IOException) {
                throw (IOException) error;
            }
            throw new IOException("failed to copy RPYC work file: " + error, error);
        }
    }

    /** Open one inflated RPYC slot. Returns null when the slot is absent. */
    public InputStream openInflatedSlot(int slotId) throws IOException {
        if (closed) {
            throw new IOException("RPYC slot source is closed");
        }
        if (slotId <= 0) {
            throw new IOException("renpy_invalid_range: invalid RPYC slot id");
        }
        RandomAccessFile random = new RandomAccessFile(file, "r");
        try {
            long length = random.length();
            if (length <= 0) {
                random.close();
                return null;
            }
            byte[] header = new byte[RPC2_MAGIC.length];
            random.seek(0);
            random.readFully(header);
            if (!Arrays.equals(header, RPC2_MAGIC)) {
                if (slotId != 1) {
                    random.close();
                    return null;
                }
                RenpyResourceLimits.checkCompressed(length);
                return inflated(random, 0, length);
            }

            long position = RPC2_MAGIC.length;
            while (position + 12 <= length) {
                random.seek(position);
                long id = readUInt32(random);
                long offset = readUInt32(random);
                long compressedLength = readUInt32(random);
                if (id == 0) {
                    break;
                }
                if (id == slotId) {
                    RenpyResourceLimits.checkRange(offset, compressedLength, length);
                    RenpyResourceLimits.checkCompressed(compressedLength);
                    return inflated(random, offset, compressedLength);
                }
                position += 12;
            }
            random.close();
            return null;
        } catch (Throwable error) {
            try {
                random.close();
            } catch (Throwable ignored) {
            }
            if (error instanceof IOException) {
                throw (IOException) error;
            }
            throw new IOException("failed to open RPYC slot: " + error, error);
        }
    }

    private InputStream inflated(RandomAccessFile random, long offset, long compressedLength)
            throws IOException {
        RegionInputStream region = new RegionInputStream(random, offset, compressedLength);
        try {
            return new InflatedLimitInputStream(
                    new InflaterInputStream(region), compressedLength);
        } catch (Throwable error) {
            region.close();
            if (error instanceof IOException) {
                throw (IOException) error;
            }
            throw new IOException("failed to open RPYC zlib slot", error);
        }
    }

    private static long readUInt32(RandomAccessFile random) throws IOException {
        long b0 = random.readUnsignedByte();
        long b1 = random.readUnsignedByte();
        long b2 = random.readUnsignedByte();
        long b3 = random.readUnsignedByte();
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24);
    }

    private static File createWorkDirectory(Context context) throws IOException {
        File cache = null;
        if (context != null) {
            try {
                cache = context.getCacheDir();
            } catch (Throwable ignored) {
            }
            if (cache == null) {
                try {
                    cache = context.getFilesDir();
                } catch (Throwable ignored) {
                }
            }
        }
        if (cache == null) {
            cache = new File(System.getProperty("java.io.tmpdir", "."));
        }
        File directory = new File(cache, "slg-rpyc-work");
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("cannot create RPYC work directory");
        }
        return directory;
    }

    @Override
    public void close() {
        if (closed) {
            return;
        }
        closed = true;
        file.delete();
        if (workDirectory != null) {
            workDirectory.delete();
        }
    }

    private static final class RegionInputStream extends InputStream {
        private final RandomAccessFile random;
        private long remaining;
        private boolean closed;

        RegionInputStream(RandomAccessFile random, long offset, long length) throws IOException {
            this.random = random;
            this.remaining = length;
            random.seek(offset);
        }

        @Override
        public int read() throws IOException {
            byte[] one = new byte[1];
            return read(one, 0, 1) < 0 ? -1 : one[0] & 0xff;
        }

        @Override
        public int read(byte[] buffer, int offset, int length) throws IOException {
            if (closed) {
                return -1;
            }
            if (remaining == 0) {
                return -1;
            }
            int wanted = (int) Math.min((long) length, remaining);
            int read = random.read(buffer, offset, wanted);
            if (read < 0) {
                throw new IOException("renpy_zlib_truncated: RPYC slot ended early");
            }
            remaining -= read;
            return read;
        }

        @Override
        public void close() throws IOException {
            if (!closed) {
                closed = true;
                random.close();
            }
        }
    }

    private static final class InflatedLimitInputStream extends FilterInputStream {
        private final long compressedLength;
        private long inflatedLength;

        InflatedLimitInputStream(InputStream input, long compressedLength) {
            super(input);
            this.compressedLength = compressedLength;
        }

        @Override
        public int read() throws IOException {
            byte[] one = new byte[1];
            return read(one, 0, 1) < 0 ? -1 : one[0] & 0xff;
        }

        @Override
        public int read(byte[] buffer, int offset, int length) throws IOException {
            int read = super.read(buffer, offset, length);
            if (read > 0) {
                inflatedLength += read;
                RenpyResourceLimits.checkWorkingSet(inflatedLength);
                RenpyResourceLimits.checkInflated(inflatedLength);
                RenpyResourceLimits.checkInflateRatio(compressedLength, inflatedLength);
                RenpyResourceLimits.checkInterrupted();
            }
            return read;
        }
    }
}
