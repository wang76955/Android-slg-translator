package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.zip.Deflater;

/**
 * Rebuilds self-indexed Ren'Py RPA archives after selected entries are replaced.
 * Unchanged entries are copied with a fixed-size buffer; only the index and
 * explicitly supplied replacement payloads are held in memory.
 */
public final class RpaArchiveWriter {
    private static final byte[] RPA3_MAGIC = "RPA-3.0 ".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] RPA2_MAGIC = "RPA-2.0 ".getBytes(StandardCharsets.US_ASCII);
    private static final int RPA3_HEADER_LENGTH = 34;
    private static final int RPA2_HEADER_LENGTH = 25;
    private static final int COPY_BUFFER_SIZE = 64 * 1024;

    private RpaArchiveWriter() {
    }

    /** Rebuilds an RPA-2/3 archive, preserving the source format and XOR key. */
    public static void rebuildSelfIndexed(
            RandomAccessFile source,
            File target,
            Map<String, byte[]> replacements,
            boolean py2Dialect
    ) throws IOException {
        if (source == null || target == null) {
            throw new IOException("source and target are required");
        }
        if (replacements == null) {
            replacements = new LinkedHashMap<>();
        }
        byte[] header = readHeader(source);
        boolean rpa3 = startsWith(header, RPA3_MAGIC);
        boolean rpa2 = startsWith(header, RPA2_MAGIC);
        if (!rpa3 && !rpa2) {
            throw new IOException("unsupported RPA format");
        }
        int headerLength = rpa3 ? RPA3_HEADER_LENGTH : RPA2_HEADER_LENGTH;
        long key = rpa3 ? parseHex(header, 25, 8) : 0L;

        Map<String, long[]> sourceIndex = RpaArchive.readIndexFromFile(
                source, rpa3 ? "archive.rpa" : "archive2.rpa");
        RenpyResourceLimits.checkEntryCount(sourceIndex.size());
        validateReplacements(sourceIndex, replacements);

        File absoluteTarget = target.getAbsoluteFile();
        File parent = absoluteTarget.getParentFile();
        if (parent == null || !parent.isDirectory()) {
            throw new IOException("target parent directory does not exist: " + parent);
        }
        File temporary = new File(parent, absoluteTarget.getName() + ".rpa.tmp");
        if (temporary.equals(absoluteTarget)) {
            throw new IOException("temporary target aliases output");
        }
        Files.deleteIfExists(temporary.toPath());

        try {
            try (RandomAccessFile output = new RandomAccessFile(temporary, "rw")) {
                output.setLength(headerLength);
                output.seek(headerLength);
                List<Map.Entry<String, long[]>> ordered = new ArrayList<>(sourceIndex.entrySet());
                ordered.sort(Comparator.comparingLong(entry -> entry.getValue()[0]));
                Map<String, long[]> rebuiltIndex = new LinkedHashMap<>();
                byte[] copyBuffer = new byte[COPY_BUFFER_SIZE];
                long sourceDataEnd = parseHex(header, 8, 16);
                if (sourceDataEnd < headerLength || sourceDataEnd > source.length()) {
                    throw new IOException("RPA data/index boundary is invalid");
                }
                long sourceCursor = headerLength;

                for (Map.Entry<String, long[]> entry : ordered) {
                    String name = entry.getKey();
                    long[] location = entry.getValue();
                    RenpyResourceLimits.checkPath(name);
                    RenpyResourceLimits.checkRange(location[0], location[1], sourceDataEnd);
                    if (location[0] < sourceCursor) {
                        throw new IOException("overlapping RPA entries: " + name);
                    }
                    copyRange(source, output, sourceCursor, location[0] - sourceCursor,
                            copyBuffer, "RPA gap before " + name);
                    long payloadOffset = output.getFilePointer();
                    byte[] replacement = replacements.get(name);
                    if (replacement != null) {
                        RenpyResourceLimits.checkInflated(replacement.length);
                        output.write(replacement);
                        rebuiltIndex.put(name, new long[]{payloadOffset, replacement.length});
                    } else {
                        source.seek(location[0]);
                        copyEntry(source, output, location[1], copyBuffer, name);
                        rebuiltIndex.put(name, new long[]{payloadOffset, location[1]});
                    }
                    sourceCursor = location[0] + location[1];
                }

                copyRange(source, output, sourceCursor, sourceDataEnd - sourceCursor,
                        copyBuffer, "RPA trailing data");
                long indexOffset = output.getFilePointer();
                output.write(buildIndexPickle(rebuiltIndex, rpa3, key, py2Dialect));
                output.getFD().sync();
                output.seek(0L);
                output.write(headerLine(rpa3, indexOffset, key).getBytes(StandardCharsets.US_ASCII));
                output.getFD().sync();
            }
            moveIntoPlace(temporary.toPath(), absoluteTarget.toPath());
        } catch (IOException | RuntimeException error) {
            Files.deleteIfExists(temporary.toPath());
            throw error;
        }
    }

    private static byte[] readHeader(RandomAccessFile source) throws IOException {
        source.seek(0L);
        byte[] buffer = new byte[64];
        int count = source.read(buffer);
        if (count < 0) {
            return new byte[0];
        }
        return Arrays.copyOf(buffer, count);
    }

    private static void validateReplacements(
            Map<String, long[]> sourceIndex,
            Map<String, byte[]> replacements
    ) {
        for (Map.Entry<String, byte[]> replacement : replacements.entrySet()) {
            RenpyResourceLimits.checkPath(replacement.getKey());
            if (!sourceIndex.containsKey(replacement.getKey())) {
                throw new IllegalArgumentException("replacement entry is not in source archive: "
                        + replacement.getKey());
            }
            if (replacement.getValue() == null) {
                throw new IllegalArgumentException("replacement payload is null: "
                        + replacement.getKey());
            }
        }
    }

    private static void copyEntry(
            RandomAccessFile source,
            RandomAccessFile output,
            long length,
            byte[] buffer,
            String name
    ) throws IOException {
        long remaining = length;
        while (remaining > 0) {
            RenpyResourceLimits.checkInterrupted();
            int count = source.read(buffer, 0, (int) Math.min(buffer.length, remaining));
            if (count < 0) {
                throw new IOException("RPA entry truncated: " + name);
            }
            output.write(buffer, 0, count);
            remaining -= count;
        }
    }

    private static void copyRange(
            RandomAccessFile source,
            RandomAccessFile output,
            long offset,
            long length,
            byte[] buffer,
            String label
    ) throws IOException {
        if (length < 0) {
            throw new IOException("negative copy range: " + label);
        }
        source.seek(offset);
        copyEntry(source, output, length, buffer, label);
    }

    /** Rebuilds an RPA-1 data file and its separate compressed .rpi index. */
    public static void rebuildRpa1(
            RandomAccessFile sourceRpa,
            byte[] rpiIndex,
            File targetRpa,
            File targetRpi,
            Map<String, byte[]> replacements,
            boolean py2Dialect
    ) throws IOException {
        if (sourceRpa == null || rpiIndex == null || targetRpa == null || targetRpi == null) {
            throw new IOException("RPA-1 source, index, and targets are required");
        }
        if (replacements == null) {
            replacements = new LinkedHashMap<>();
        }
        Map<String, long[]> sourceIndex = RpaArchive.listEntryLocations(rpiIndex, "archive.rpi");
        RenpyResourceLimits.checkEntryCount(sourceIndex.size());
        validateReplacements(sourceIndex, replacements);

        File absoluteRpa = targetRpa.getAbsoluteFile();
        File absoluteRpi = targetRpi.getAbsoluteFile();
        File parent = absoluteRpa.getParentFile();
        File rpiParent = absoluteRpi.getParentFile();
        if (parent == null || !parent.isDirectory() || rpiParent == null || !rpiParent.isDirectory()) {
            throw new IOException("RPA-1 target directory does not exist");
        }
        File temporaryRpa = new File(parent, absoluteRpa.getName() + ".rpa.tmp");
        File temporaryRpi = new File(rpiParent, absoluteRpi.getName() + ".rpi.tmp");
        Files.deleteIfExists(temporaryRpa.toPath());
        Files.deleteIfExists(temporaryRpi.toPath());

        try {
            Map<String, long[]> rebuiltIndex = new LinkedHashMap<>();
            List<Map.Entry<String, long[]>> ordered = new ArrayList<>(sourceIndex.entrySet());
            ordered.sort(Comparator.comparingLong(entry -> entry.getValue()[0]));
            byte[] copyBuffer = new byte[COPY_BUFFER_SIZE];
            long sourceCursor = 0L;
            try (RandomAccessFile output = new RandomAccessFile(temporaryRpa, "rw")) {
                for (Map.Entry<String, long[]> entry : ordered) {
                    String name = entry.getKey();
                    long[] location = entry.getValue();
                    RenpyResourceLimits.checkPath(name);
                    RenpyResourceLimits.checkRange(location[0], location[1], sourceRpa.length());
                    if (location[0] < sourceCursor) {
                        throw new IOException("overlapping RPA-1 entries: " + name);
                    }
                    copyRange(sourceRpa, output, sourceCursor, location[0] - sourceCursor,
                            copyBuffer, "RPA-1 gap before " + name);
                    long payloadOffset = output.getFilePointer();
                    byte[] replacement = replacements.get(name);
                    if (replacement != null) {
                        RenpyResourceLimits.checkInflated(replacement.length);
                        output.write(replacement);
                        rebuiltIndex.put(name, new long[]{payloadOffset, replacement.length});
                    } else {
                        sourceRpa.seek(location[0]);
                        copyEntry(sourceRpa, output, location[1], copyBuffer, name);
                        rebuiltIndex.put(name, new long[]{payloadOffset, location[1]});
                    }
                    sourceCursor = location[0] + location[1];
                }
                copyRange(sourceRpa, output, sourceCursor, sourceRpa.length() - sourceCursor,
                        copyBuffer, "RPA-1 trailing data");
                output.getFD().sync();
            }
            Files.write(temporaryRpi.toPath(), buildIndexPickle(rebuiltIndex, false, 0L, py2Dialect));
            moveIntoPlace(temporaryRpa.toPath(), absoluteRpa.toPath());
            moveIntoPlace(temporaryRpi.toPath(), absoluteRpi.toPath());
        } catch (IOException | RuntimeException error) {
            Files.deleteIfExists(temporaryRpa.toPath());
            Files.deleteIfExists(temporaryRpi.toPath());
            throw error;
        }
    }

    /** Performs the bounded Java-side reread used before registering a rebuilt archive. */
    public static void verifyRebuilt(
            Map<String, long[]> before,
            RandomAccessFile rebuilt,
            String archiveName,
            Map<String, byte[]> replacements,
            byte[] sourceBytesIfAvailable
    ) throws IOException {
        Map<String, long[]> after = RpaArchive.readIndexFromFile(rebuilt, archiveName);
        if (before == null || after.size() != before.size()) {
            throw new IOException("rebuilt RPA entry count changed");
        }
        if (replacements != null) {
            for (Map.Entry<String, byte[]> replacement : replacements.entrySet()) {
                byte[] actual = RpaArchive.readEntryFromFile(rebuilt, archiveName, replacement.getKey());
                if (!Arrays.equals(actual, replacement.getValue())) {
                    throw new IOException("rebuilt replacement differs: " + replacement.getKey());
                }
            }
        }
        if (sourceBytesIfAvailable != null) {
            RenpyResourceLimits.checkInflated(sourceBytesIfAvailable.length);
        }
    }

    /** Performs the bounded Java-side reread for an RPA-1 data/index pair. */
    public static void verifyRebuiltRpa1(
            Map<String, long[]> before,
            RandomAccessFile rebuiltRpa,
            byte[] rebuiltRpi,
            String archiveName,
            Map<String, byte[]> replacements
    ) throws IOException {
        Map<String, long[]> after = RpaArchive.listEntryLocations(rebuiltRpi, archiveName);
        if (before == null || after.size() != before.size()) {
            throw new IOException("rebuilt RPA-1 entry count changed");
        }
        if (replacements != null) {
            for (Map.Entry<String, byte[]> replacement : replacements.entrySet()) {
                byte[] actual = RpaArchive.readEntryFromFile(
                        rebuiltRpa, rebuiltRpi, archiveName, replacement.getKey());
                if (!Arrays.equals(actual, replacement.getValue())) {
                    throw new IOException("rebuilt RPA-1 replacement differs: "
                            + replacement.getKey());
                }
            }
        }
    }

    private static void moveIntoPlace(Path temporary, Path target) throws IOException {
        try {
            Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException first) {
            Files.deleteIfExists(target);
            Files.move(temporary, target);
        }
    }

    private static byte[] buildIndexPickle(
            Map<String, long[]> index,
            boolean xor,
            long key,
            boolean py2Dialect
    ) {
        ByteArrayOutputStream pickle = new ByteArrayOutputStream();
        pickle.write(0x80); // PROTO
        pickle.write(0x02);
        pickle.write(0x7d); // EMPTY_DICT
        pickle.write(0x28); // MARK
        for (Map.Entry<String, long[]> entry : index.entrySet()) {
            writeString(pickle, entry.getKey(), py2Dialect);
            pickle.write(0x5d); // EMPTY_LIST
            long encodedOffset = xor ? entry.getValue()[0] ^ key : entry.getValue()[0];
            long encodedLength = xor ? entry.getValue()[1] ^ key : entry.getValue()[1];
            writeNonNegativeInt(pickle, encodedOffset);
            writeNonNegativeInt(pickle, encodedLength);
            writeEmptyBytes(pickle);
            pickle.write(0x87); // TUPLE3
            pickle.write(0x61); // APPEND
        }
        pickle.write(0x75); // SETITEMS
        pickle.write(0x2e); // STOP
        return deflate(pickle.toByteArray());
    }

    private static void writeEmptyBytes(ByteArrayOutputStream out) {
        // This is the protocol-2-compatible shape emitted by the existing
        // Python fixture: __builtin__.bytes() -> b"" on Python 2/3.
        out.write(0x63); // GLOBAL
        writeAsciiLine(out, "__builtin__");
        writeAsciiLine(out, "bytes");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x52); // REDUCE
    }

    private static void writeString(ByteArrayOutputStream out, String value, boolean py2Dialect) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        if (bytes.length > RenpyResourceLimits.MAX_TEXT_LENGTH) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_limit_inflated", "RPA index path is too long");
        }
        if (py2Dialect) {
            out.write(0x58); // BINUNICODE
            writeLittleEndian(out, bytes.length, 4);
        } else if (bytes.length <= 255) {
            out.write(0x8c); // SHORT_BINUNICODE
            out.write(bytes.length);
        } else {
            out.write(0x58); // BINUNICODE
            writeLittleEndian(out, bytes.length, 4);
        }
        out.write(bytes, 0, bytes.length);
    }

    private static void writeAsciiLine(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.US_ASCII);
        out.write(bytes, 0, bytes.length);
        out.write('\n');
    }

    private static void writeNonNegativeInt(ByteArrayOutputStream out, long value) {
        if (value < 0 || value > 0xffffffffL) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_invalid_range", "RPA index coordinate exceeds unsigned 32-bit range");
        }
        if (value <= 0xff) {
            out.write(0x4b); // BININT1
            out.write((int) value);
        } else if (value <= 0xffff) {
            out.write(0x4d); // BININT2
            writeLittleEndian(out, value, 2);
        } else if (value <= Integer.MAX_VALUE) {
            out.write(0x4a); // BININT
            writeLittleEndian(out, value, 4);
        } else {
            // Protocol 2 BININT is signed. Encode the remaining positive
            // unsigned-32-bit values as a positive LONG1 with a zero sign byte.
            out.write(0x8a); // LONG1
            out.write(5);
            writeLittleEndian(out, value, 4);
            out.write(0);
        }
    }

    private static void writeLittleEndian(ByteArrayOutputStream out, long value, int width) {
        for (int index = 0; index < width; index++) {
            out.write((int) ((value >>> (index * 8)) & 0xff));
        }
    }

    private static byte[] deflate(byte[] data) {
        Deflater deflater = new Deflater(6);
        try {
            deflater.setInput(data);
            deflater.finish();
            ByteArrayOutputStream compressed = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            while (!deflater.finished()) {
                int count = deflater.deflate(buffer);
                if (count == 0 && !deflater.finished()) {
                    throw new IllegalStateException("RPA index compression stalled");
                }
                compressed.write(buffer, 0, count);
            }
            return compressed.toByteArray();
        } finally {
            deflater.end();
        }
    }

    private static long parseHex(byte[] data, int start, int length) {
        return Long.parseLong(new String(data, start, length, StandardCharsets.US_ASCII).trim(), 16);
    }

    private static String headerLine(boolean rpa3, long indexOffset, long key) {
        return rpa3
                ? String.format(Locale.ROOT, "RPA-3.0 %016x %08x\n", indexOffset, key)
                : String.format(Locale.ROOT, "RPA-2.0 %016x\n", indexOffset);
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int index = 0; index < prefix.length; index++) {
            if (data[index] != prefix[index]) {
                return false;
            }
        }
        return true;
    }
}
