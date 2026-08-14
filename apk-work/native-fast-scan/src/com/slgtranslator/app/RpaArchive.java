package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.InflaterInputStream;

/**
 * Reads Ren'Py RPA-1/2/3 archive indexes without extracting the whole archive.
 *
 * <p>RPA-3 stores its index as a zlib-compressed pickle dict at the end of the
 * file; RPA-2 uses the same layout without XOR obfuscation; RPA-1 keeps the
 * compressed index in a separate .rpi file and stores raw file data in .rpa.
 * Scripts inside an archive are exposed to the scanner through virtual names
 * like {@code game/archive.rpa!/game/chapter1.rpyc}.
 */
public final class RpaArchive {

    static final String VIRTUAL_SEPARATOR = "!/";

    private static final byte[] RPA3_MAGIC = "RPA-3.0 ".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] RPA2_MAGIC = "RPA-2.0 ".getBytes(StandardCharsets.US_ASCII);
    private static final Object MARK = new Object();
    private static final Object CALLABLE = new Object();
    private static final byte[] EMPTY_BYTES = new byte[0];

    private static final Set<String> SCRIPT_EXTENSIONS = Collections.unmodifiableSet(
        new java.util.HashSet<>(Arrays.asList("rpym", "rpymc", "rpy", "rpyc"))
    );

    private RpaArchive() {
    }

    /** Returns the scanner-facing name for a file stored inside an archive. */
    public static String virtualName(String archiveName, String internalName) {
        return archiveName + VIRTUAL_SEPARATOR + internalName;
    }

    /**
     * Splits a virtual archive name. When the input is not virtual, returns an
     * array with a single element.
     */
    public static String[] splitVirtual(String name) {
        int separator = name.indexOf(VIRTUAL_SEPARATOR);
        if (separator <= 0 || separator + VIRTUAL_SEPARATOR.length() >= name.length()) {
            return new String[]{name};
        }
        return new String[]{
            name.substring(0, separator),
            name.substring(separator + VIRTUAL_SEPARATOR.length()),
        };
    }

    /** Lists Ren'Py script paths inside an RPA-2/3 zip entry without reading the whole archive. */
    public static List<String> listEntriesFromZip(
        java.util.zip.ZipFile zip,
        java.util.zip.ZipEntry entry,
        String archiveName
    ) throws IOException {
        return scriptNames(readZipIndex(zip, entry, archiveName));
    }

    /** Lists Ren'Py script paths inside an RPA index or RPA-1 .rpi file. */
    public static List<String> listEntries(byte[] archiveOrIndex, String archiveName) {
        Map<String, long[]> index = readIndex(archiveOrIndex, archiveName);
        List<String> result = new ArrayList<>();
        for (String name : index.keySet()) {
            if (isScriptPath(name)) {
                result.add(name);
            }
        }
        Collections.sort(result);
        return result;
    }

    /** Returns every archive entry, including non-script files, in real coordinates. */
    public static Map<String, long[]> listEntryLocations(byte[] archiveOrIndex, String archiveName) {
        return readIndex(archiveOrIndex, archiveName);
    }

    /** Reads an RPA-2/3 index from a file without loading the data body. */
    public static Map<String, long[]> readIndexFromFile(RandomAccessFile archive, String archiveName)
            throws IOException {
        if (archive == null) {
            throw new IOException("archive handle is null");
        }
        archive.seek(0L);
        byte[] head = new byte[64];
        int count = archive.read(head);
        if (count < 0) {
            throw new IOException("archive is empty: " + archiveName);
        }
        byte[] header = Arrays.copyOf(head, count);
        if (startsWith(header, RPA3_MAGIC)) {
            long indexOffset = parseHex(header, 8, 16);
            long key = parseHex(header, 25, 8);
            return parseIndexPickle(inflate(readTail(archive, indexOffset)), true, key);
        }
        if (startsWith(header, RPA2_MAGIC)) {
            long indexOffset = parseHex(header, 8, 16);
            return parseIndexPickle(inflate(readTail(archive, indexOffset)), false, 0L);
        }
        throw new IOException("not an RPA-2/3 archive: " + archiveName);
    }

    /** Reads an RPA-1 index from a separate compressed .rpi file. */
    public static Map<String, long[]> readIndexFromFile(
            RandomAccessFile archive,
            byte[] indexData,
            String archiveName
    ) throws IOException {
        if (archive == null) {
            throw new IOException("archive handle is null");
        }
        if (indexData == null) {
            throw new IOException("RPA-1 index data is null: " + archiveName);
        }
        return parseIndexPickle(inflate(indexData), false, 0L);
    }

    /** Reads one bounded entry from a file-backed RPA archive. */
    public static byte[] readEntryFromFile(
            RandomAccessFile archive,
            String archiveName,
            String internalName
    ) throws IOException {
        Map<String, long[]> index = readIndexFromFile(archive, archiveName);
        return readMappedFromFile(archive, index, internalName);
    }

    /** Reads one bounded entry from an RPA-1 data file using a separate .rpi index. */
    public static byte[] readEntryFromFile(
            RandomAccessFile archive,
            byte[] indexData,
            String archiveName,
            String internalName
    ) throws IOException {
        Map<String, long[]> index = readIndexFromFile(archive, indexData, archiveName);
        return readMappedFromFile(archive, index, internalName);
    }

    private static byte[] readMappedFromFile(
            RandomAccessFile archive,
            Map<String, long[]> index,
            String internalName
    ) throws IOException {
        long[] location = index.get(internalName);
        if (location == null) {
            throw new IOException("RPA entry not found: " + internalName);
        }
        RenpyResourceLimits.checkRange(location[0], location[1], archive.length());
        RenpyResourceLimits.checkInflated(location[1]);
        if (location[1] > Integer.MAX_VALUE) {
            throw new IOException("RPA entry is too large to read into memory: " + internalName);
        }
        byte[] result = new byte[(int) location[1]];
        archive.seek(location[0]);
        archive.readFully(result);
        return result;
    }

    /**
     * Reads one raw file from an RPA-2/3 archive. For RPA-1, use the four
     * argument overload that also accepts the .rpi index bytes.
     */
    public static byte[] readEntry(byte[] archiveData, String archiveName, String internalName) throws IOException {
        return readMapped(archiveData, readIndex(archiveData, archiveName), internalName);
    }

    /** Reads one raw file from an RPA-1 data file using the .rpi index. */
    public static byte[] readEntry(
        byte[] archiveData,
        String archiveName,
        String internalName,
        byte[] indexData
    ) throws IOException {
        return readMapped(archiveData, readIndex(indexData, archiveName), internalName);
    }

    private static byte[] readMapped(byte[] data, Map<String, long[]> index, String internalName)
            throws IOException {
        RenpyResourceLimits.checkPath(internalName);
        long[] location = index.get(internalName);
        if (location == null) {
            throw new IOException("RPA entry not found: " + internalName);
        }
        long offset = location[0];
        long length = location[1];
        RenpyResourceLimits.checkRange(offset, length, data.length);
        RenpyResourceLimits.checkInflated(length);
        return Arrays.copyOfRange(data, (int) offset, (int) (offset + length));
    }

    /** Reads one raw file from an RPA-2/3 entry inside an APK. */
    public static byte[] readEntryFromZip(
        java.util.zip.ZipFile zip,
        java.util.zip.ZipEntry archiveEntry,
        String archiveName,
        String internalName
    ) throws IOException {
        Map<String, long[]> index = readZipIndex(zip, archiveEntry, archiveName);
        return readMappedFromZip(zip, archiveEntry, index, internalName);
    }

    /** Reads one raw file from an RPA-1 data entry using a separate .rpi index. */
    public static byte[] readEntryFromZip(
        java.util.zip.ZipFile zip,
        java.util.zip.ZipEntry dataEntry,
        String dataName,
        String internalName,
        byte[] indexData
    ) throws IOException {
        Map<String, long[]> index = parseIndexPickle(inflate(indexData), false, 0);
        return readMappedFromZip(zip, dataEntry, index, internalName);
    }

    private static Map<String, long[]> readZipIndex(
        java.util.zip.ZipFile zip,
        java.util.zip.ZipEntry entry,
        String archiveName
    ) throws IOException {
        try (InputStream in = zip.getInputStream(entry)) {
            byte[] head = readN(in, 64);
            if (startsWith(head, RPA3_MAGIC)) {
                long indexOffset = parseHex(head, 8, 16);
                long key = parseHex(head, 25, 8);
                byte[] compressed = readIndexBytes(in, head, indexOffset);
                return parseIndexPickle(inflate(compressed), true, key);
            }
            if (startsWith(head, RPA2_MAGIC)) {
                long indexOffset = parseHex(head, 8, 16);
                byte[] compressed = readIndexBytes(in, head, indexOffset);
                return parseIndexPickle(inflate(compressed), false, 0);
            }
            if (startsWith(head, new byte[]{0x78, (byte) 0x9c})) {
                ByteArrayOutputStream all = new ByteArrayOutputStream();
                all.write(head);
                byte[] buffer = new byte[8192];
                int read;
                long total = head.length;
                while ((read = in.read(buffer)) != -1) {
                    RenpyResourceLimits.checkInterrupted();
                    total += read;
                    RenpyResourceLimits.checkCompressed(total);
                    all.write(buffer, 0, read);
                }
                return parseIndexPickle(inflate(all.toByteArray()), false, 0);
            }
        }
        return Collections.emptyMap();
    }

    private static byte[] readMappedFromZip(
        java.util.zip.ZipFile zip,
        java.util.zip.ZipEntry entry,
        Map<String, long[]> index,
        String internalName
    ) throws IOException {
        RenpyResourceLimits.checkPath(internalName);
        long[] location = index.get(internalName);
        if (location == null) {
            throw new IOException("RPA entry not found: " + internalName);
        }
        long offset = location[0];
        long length = location[1];
        RenpyResourceLimits.checkInflated(length);
        if (entry.getSize() >= 0) {
            RenpyResourceLimits.checkRange(offset, length, entry.getSize());
        } else if (offset < 0 || length < 0 || offset > Long.MAX_VALUE - length) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_invalid_range", "RPA entry range overflows");
        }
        try (InputStream in = zip.getInputStream(entry)) {
            skipFully(in, offset);
            byte[] result = new byte[(int) length];
            int position = 0;
            while (position < result.length) {
                int read = in.read(result, position, result.length - position);
                if (read < 0) {
                    throw new IOException("RPA entry truncated: " + internalName);
                }
                RenpyResourceLimits.checkInterrupted();
                position += read;
            }
            return result;
        }
    }

    private static byte[] readIndexBytes(InputStream in, byte[] head, long indexOffset) throws IOException {
        if (indexOffset < 0) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_invalid_range", "RPA index offset is negative");
        }
        ByteArrayOutputStream all = new ByteArrayOutputStream();
        long total = 0;
        if (indexOffset >= 0 && indexOffset < head.length) {
            int start = (int) indexOffset;
            int count = head.length - start;
            all.write(head, start, count);
            total += count;
        } else if (indexOffset > head.length) {
            skipFully(in, indexOffset - head.length);
        }
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) != -1) {
            RenpyResourceLimits.checkInterrupted();
            total += read;
            RenpyResourceLimits.checkCompressed(total);
            all.write(buffer, 0, read);
        }
        return all.toByteArray();
    }

    private static byte[] readTail(RandomAccessFile archive, long indexOffset) throws IOException {
        if (indexOffset < 0 || indexOffset > archive.length()) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_invalid_range", "RPA index offset is out of range");
        }
        archive.seek(indexOffset);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        long total = 0L;
        int count;
        while ((count = archive.read(buffer)) != -1) {
            RenpyResourceLimits.checkInterrupted();
            total += count;
            RenpyResourceLimits.checkCompressed(total);
            out.write(buffer, 0, count);
        }
        return out.toByteArray();
    }
    private static byte[] readN(InputStream in, int count) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(count);
        byte[] buffer = new byte[Math.min(count, 8192)];
        int remaining = count;
        while (remaining > 0) {
            int read = in.read(buffer, 0, Math.min(buffer.length, remaining));
            if (read < 0) {
                break;
            }
            out.write(buffer, 0, read);
            remaining -= read;
        }
        return out.toByteArray();
    }

    private static void skipFully(InputStream in, long count) throws IOException {
        if (count < 0) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_invalid_range", "RPA skip length is negative");
        }
        long remaining = count;
        while (remaining > 0) {
            long skipped = in.skip(remaining);
            if (skipped <= 0) {
                if (in.read() == -1) {
                    throw new RenpyResourceLimits.LimitException(
                            "renpy_invalid_range", "RPA entry range exceeds archive data");
                }
                remaining--;
            } else {
                remaining -= skipped;
            }
        }
    }

    private static Map<String, long[]> readIndex(byte[] data, String archiveName) {
        if (data == null || data.length < 2) {
            return Collections.emptyMap();
        }
        boolean zlibIndex = (data[0] & 0xff) == 0x78 && (data[1] & 0xff) == 0x9c;
        if (zlibIndex) {
            return parseIndexPickle(inflate(data), false, 0);
        }
        if (startsWith(data, RPA3_MAGIC)) {
            if (data.length < 34) {
                return Collections.emptyMap();
            }
            long indexOffset = parseHex(data, 8, 16);
            long key = parseHex(data, 25, 8);
            RenpyResourceLimits.checkRange(indexOffset, data.length - indexOffset, data.length);
            byte[] compressed = slice(data, (int) indexOffset, data.length);
            return parseIndexPickle(inflate(compressed), true, key);
        }
        if (startsWith(data, RPA2_MAGIC)) {
            if (data.length < 25) {
                return Collections.emptyMap();
            }
            long indexOffset = parseHex(data, 8, 16);
            RenpyResourceLimits.checkRange(indexOffset, data.length - indexOffset, data.length);
            byte[] compressed = slice(data, (int) indexOffset, data.length);
            return parseIndexPickle(inflate(compressed), false, 0);
        }
        String suffix = archiveName == null ? "" : archiveName.toLowerCase(Locale.ROOT);
        if (suffix.endsWith(".rpi")) {
            return parseIndexPickle(inflate(data), false, 0);
        }
        return Collections.emptyMap();
    }

    private static List<String> scriptNames(Map<String, long[]> index) {
        List<String> result = new ArrayList<>();
        for (String name : index.keySet()) {
            if (isScriptPath(name)) {
                result.add(name);
            }
        }
        Collections.sort(result);
        return result;
    }

    private static boolean isScriptPath(String name) {
        int slash = name.lastIndexOf('/');
        int dot = name.lastIndexOf('.');
        if (dot <= slash || dot == name.length() - 1) {
            return false;
        }
        return SCRIPT_EXTENSIONS.contains(name.substring(dot + 1).toLowerCase(Locale.ROOT));
    }

    private static long parseHex(byte[] data, int start, int length) {
        String value = new String(data, start, length, StandardCharsets.US_ASCII).trim();
        return Long.parseLong(value, 16);
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private static byte[] slice(byte[] data, int start, int end) {
        if (start < 0 || end < start || end > data.length) {
            return new byte[0];
        }
        return Arrays.copyOfRange(data, start, end);
    }

    private static byte[] inflate(byte[] data) {
        if (data == null) {
            throw new RenpyResourceLimits.LimitException(
                    "renpy_invalid_range", "compressed Ren'Py data is null");
        }
        try {
            RenpyResourceLimits.checkCompressed(data.length);
            java.util.zip.Inflater inflater = new java.util.zip.Inflater();
            inflater.setInput(data);
            try {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buffer = new byte[8192];
                long total = 0;
                while (!inflater.finished()) {
                    RenpyResourceLimits.checkInterrupted();
                    int read = inflater.inflate(buffer);
                    if (read > 0) {
                        total += read;
                        RenpyResourceLimits.checkInflated(total);
                        RenpyResourceLimits.checkInflateRatio(data.length, total);
                        out.write(buffer, 0, read);
                    } else if (inflater.needsDictionary() || inflater.needsInput()) {
                        throw new IOException("RPA zlib data is truncated");
                    } else {
                        throw new IOException("RPA zlib data is invalid");
                    }
                }
                // RPA index ranges can contain the same harmless padding as
                // Ren'Py RPC2 slots.  Keep the first complete zlib stream,
                // matching the reader behavior used by Ren'Py/Python.
                return out.toByteArray();
            } catch (java.util.zip.DataFormatException e) {
                throw new IOException("RPA zlib data is invalid", e);
            } finally {
                inflater.end();
            }
        } catch (RenpyResourceLimits.LimitException e) {
            throw e;
        } catch (IOException e) {
            return new byte[0];
        }
    }

    private static Map<String, long[]> parseIndexPickle(byte[] data, boolean xor, long key) {
        Map<Integer, Object> memo = new HashMap<>();
        List<Object> stack = new ArrayList<>();
        int position = 0;
        int memoNext = 0;
        try {
            while (position < data.length) {
                int code = data[position++] & 0xff;
                switch (code) {
                    case 0x80: // PROTO
                        position++;
                        break;
                    case 0x95: // FRAME
                        position += 8;
                        break;
                    case 0x2e: // STOP
                        return toIndexMap(stack.isEmpty() ? null : stack.get(stack.size() - 1), xor, key);
                    case 0x28: // MARK
                        stack.add(MARK);
                        break;
                    case 0x29: // EMPTY_TUPLE
                        stack.add(new ArrayList<Object>());
                        break;
                    case 0x5d: // EMPTY_LIST
                        stack.add(new ArrayList<Object>());
                        break;
                    case 0x7d: // EMPTY_DICT
                        stack.add(new LinkedHashMap<String, Object>());
                        break;
                    case 0x8c: { // SHORT_BINUNICODE
                        if (position >= data.length) {
                            return Collections.emptyMap();
                        }
                        int length = data[position++] & 0xff;
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(new String(data, position, length, StandardCharsets.UTF_8));
                        position += length;
                        break;
                    }
                    case 0x58: { // BINUNICODE
                        if (position + 4 > data.length) {
                            return Collections.emptyMap();
                        }
                        int length = le32(data, position);
                        position += 4;
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(new String(data, position, length, StandardCharsets.UTF_8));
                        position += length;
                        break;
                    }
                    case 0x43: { // SHORT_BINBYTES
                        if (position >= data.length) {
                            return Collections.emptyMap();
                        }
                        int length = data[position++] & 0xff;
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(Arrays.copyOfRange(data, position, position + length));
                        position += length;
                        break;
                    }
                    case 0x42: { // BINBYTES
                        if (position + 4 > data.length) {
                            return Collections.emptyMap();
                        }
                        int length = le32(data, position);
                        position += 4;
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(Arrays.copyOfRange(data, position, position + length));
                        position += length;
                        break;
                    }
                    case 0x8e: { // BINBYTES8
                        if (position + 8 > data.length) {
                            return Collections.emptyMap();
                        }
                        long length = le64(data, position);
                        position += 8;
                        if (length < 0 || length > Integer.MAX_VALUE) {
                            return Collections.emptyMap();
                        }
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(Arrays.copyOfRange(data, position, position + (int) length));
                        position += (int) length;
                        break;
                    }
                    case 0x8f: // EMPTY_BYTES
                        stack.add(EMPTY_BYTES);
                        break;
                    case 0x63: { // GLOBAL
                        position = skipAsciiLine(data, position);
                        position = skipAsciiLine(data, position);
                        stack.add(CALLABLE);
                        break;
                    }
                    case 0x93: { // STACK_GLOBAL
                        if (stack.size() >= 2) {
                            stack.remove(stack.size() - 1);
                            stack.remove(stack.size() - 1);
                            stack.add(CALLABLE);
                        } else {
                            return Collections.emptyMap();
                        }
                        break;
                    }
                    case 0x52: { // REDUCE
                        Object args = stack.remove(stack.size() - 1);
                        stack.remove(stack.size() - 1);
                        stack.add(reduce(args));
                        break;
                    }
                    case 0x81: { // NEWOBJ
                        stack.remove(stack.size() - 1);
                        stack.remove(stack.size() - 1);
                        stack.add(EMPTY_BYTES);
                        break;
                    }
                    case 0x49: { // INT
                        stack.add(Long.parseLong(readAsciiLine(data, position)));
                        position = skipAsciiLine(data, position);
                        break;
                    }
                    case 0x4c: { // LONG
                        String line = readAsciiLine(data, position);
                        position = skipAsciiLine(data, position);
                        if (line.endsWith("L") || line.endsWith("l")) {
                            line = line.substring(0, line.length() - 1);
                        }
                        stack.add(Long.parseLong(line));
                        break;
                    }
                    case 0x8a: { // LONG1
                        if (position >= data.length) {
                            return Collections.emptyMap();
                        }
                        int length = data[position++] & 0xff;
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(pickleLong(data, position, length));
                        position += length;
                        break;
                    }
                    case 0x8b: { // LONG4
                        int length = le32(data, position);
                        position += 4;
                        if (length < 0 || length > 1024) {
                            return Collections.emptyMap();
                        }
                        RenpyResourceLimits.checkRange(position, length, data.length);
                        stack.add(pickleLong(data, position, length));
                        position += length;
                        break;
                    }
                    case 0x4b: // BININT1
                        stack.add((int) (data[position++] & 0xff));
                        break;
                    case 0x4d: // BININT2
                        stack.add(le16(data, position));
                        position += 2;
                        break;
                    case 0x4a: // BININT
                        stack.add(le32(data, position));
                        position += 4;
                        break;
                    case 0x4e: // NONE
                        stack.add(null);
                        break;
                    case 0x88: // NEWTRUE
                        stack.add(Boolean.TRUE);
                        break;
                    case 0x89: // NEWFALSE
                        stack.add(Boolean.FALSE);
                        break;
                    case 0x71: // BINPUT
                        memo.put(data[position++] & 0xff, stack.get(stack.size() - 1));
                        break;
                    case 0x72: // LONG_BINPUT
                        memo.put(le32(data, position), stack.get(stack.size() - 1));
                        position += 4;
                        break;
                    case 0x94: // MEMOIZE
                        memo.put(memoNext++, stack.get(stack.size() - 1));
                        break;
                    case 0x68: // BINGET
                        stack.add(memo.get(data[position++] & 0xff));
                        break;
                    case 0x6a: // LONG_BINGET
                        stack.add(memo.get(le32(data, position)));
                        position += 4;
                        break;
                    case 0x74: // TUPLE
                        stack.add(buildTupleFromMark(stack, false));
                        break;
                    case 0x6c: // LIST
                        stack.add(buildTupleFromMark(stack, true));
                        break;
                    case 0x85: // TUPLE1
                        stack.add(tuple1(stack));
                        break;
                    case 0x86: // TUPLE2
                        stack.add(tuple2(stack));
                        break;
                    case 0x87: // TUPLE3
                        stack.add(tuple3(stack));
                        break;
                    case 0x61: // APPEND
                        append(stack);
                        break;
                    case 0x65: // APPENDS
                        appends(stack);
                        break;
                    case 0x73: // SETITEM
                        setItem(stack);
                        break;
                    case 0x75: // SETITEMS
                        setItems(stack);
                        break;
                    default:
                        // Unknown opcodes do not appear in RPA indexes built by
                        // the official archiver; stop parsing to stay bounded.
                        return Collections.emptyMap();
                }
            }
        } catch (RenpyResourceLimits.LimitException limit) {
            throw limit;
        } catch (RuntimeException ignored) {
            return Collections.emptyMap();
        }
        return Collections.emptyMap();
    }

    @SuppressWarnings("unchecked")
    private static void append(List<Object> stack) {
        Object item = stack.remove(stack.size() - 1);
        Object target = stack.get(stack.size() - 1);
        if (target instanceof List) {
            ((List<Object>) target).add(item);
        }
    }

    @SuppressWarnings("unchecked")
    private static void appends(List<Object> stack) {
        List<Object> items = new ArrayList<>();
        while (!stack.isEmpty() && stack.get(stack.size() - 1) != MARK) {
            items.add(stack.remove(stack.size() - 1));
        }
        if (stack.isEmpty() || stack.get(stack.size() - 1) != MARK) {
            throw new IllegalArgumentException("APPENDS without MARK");
        }
        stack.remove(stack.size() - 1);
        Object target = stack.get(stack.size() - 1);
        if (target instanceof List) {
            List<Object> list = (List<Object>) target;
            for (int i = items.size() - 1; i >= 0; i--) {
                list.add(items.get(i));
            }
        }
    }

    private static Object reduce(Object args) {
        if (args instanceof List && !((List<?>) args).isEmpty()) {
            Object first = ((List<?>) args).get(0);
            if (first instanceof byte[]) {
                return first;
            }
        }
        return EMPTY_BYTES;
    }
    @SuppressWarnings("unchecked")
    private static void setItem(List<Object> stack) {
        Object value = stack.remove(stack.size() - 1);
        Object key = stack.remove(stack.size() - 1);
        Object target = stack.remove(stack.size() - 1);
        if (target instanceof Map) {
            ((Map<Object, Object>) target).put(key, value);
            stack.add(target);
        }
    }

    @SuppressWarnings("unchecked")
    private static void setItems(List<Object> stack) {
        List<Object> pairs = new ArrayList<>();
        while (!stack.isEmpty() && stack.get(stack.size() - 1) != MARK) {
            pairs.add(stack.remove(stack.size() - 1));
        }
        if (stack.isEmpty() || stack.get(stack.size() - 1) != MARK) {
            throw new IllegalArgumentException("SETITEMS without MARK");
        }
        stack.remove(stack.size() - 1);
        Object target = stack.get(stack.size() - 1);
        if (target instanceof Map) {
            Map<Object, Object> dict = (Map<Object, Object>) target;
            for (int i = pairs.size() - 1; i >= 1; i -= 2) {
                dict.put(pairs.get(i), pairs.get(i - 1));
            }
        }
    }

    private static List<Object> tuple1(List<Object> stack) {
        List<Object> tuple = new ArrayList<>();
        tuple.add(stack.remove(stack.size() - 1));
        return tuple;
    }

    private static List<Object> tuple2(List<Object> stack) {
        Object second = stack.remove(stack.size() - 1);
        Object first = stack.remove(stack.size() - 1);
        List<Object> tuple = new ArrayList<>();
        tuple.add(first);
        tuple.add(second);
        return tuple;
    }

    private static List<Object> tuple3(List<Object> stack) {
        Object third = stack.remove(stack.size() - 1);
        Object second = stack.remove(stack.size() - 1);
        Object first = stack.remove(stack.size() - 1);
        List<Object> tuple = new ArrayList<>();
        tuple.add(first);
        tuple.add(second);
        tuple.add(third);
        return tuple;
    }

    private static List<Object> buildTupleFromMark(List<Object> stack, boolean asList) {
        List<Object> items = new ArrayList<>();
        while (!stack.isEmpty() && stack.get(stack.size() - 1) != MARK) {
            items.add(stack.remove(stack.size() - 1));
        }
        if (stack.isEmpty() || stack.get(stack.size() - 1) != MARK) {
            throw new IllegalArgumentException("TUPLE/LIST without MARK");
        }
        stack.remove(stack.size() - 1);
        List<Object> result = new ArrayList<>();
        for (int i = items.size() - 1; i >= 0; i--) {
            result.add(items.get(i));
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, long[]> toIndexMap(Object value, boolean xor, long key) {
        Map<String, long[]> result = new LinkedHashMap<>();
        if (!(value instanceof Map)) {
            return result;
        }
        Map<Object, Object> source = (Map<Object, Object>) value;
        RenpyResourceLimits.checkEntryCount(source.size());
        for (Map.Entry<Object, Object> entry : source.entrySet()) {
            if (!(entry.getKey() instanceof String)) {
                continue;
            }
            String name = (String) entry.getKey();
            RenpyResourceLimits.checkTextLength(name.length());
            RenpyResourceLimits.checkPath(name);
            Object raw = entry.getValue();
            if (!(raw instanceof List) || ((List<?>) raw).isEmpty()) {
                continue;
            }
            Object tupleObject = ((List<?>) raw).get(0);
            if (!(tupleObject instanceof List)) {
                tupleObject = raw;
            }
            List<?> tuple = (List<?>) tupleObject;
            if (tuple.size() < 2) {
                continue;
            }
            Long offset = toLong(tuple.get(0));
            Long length = toLong(tuple.get(1));
            if (offset == null || length == null) {
                continue;
            }
            long realOffset = xor ? offset ^ key : offset;
            long realLength = xor ? length ^ key : length;
            if (realOffset < 0 || realLength < 0
                    || realOffset > Long.MAX_VALUE - realLength) {
                throw new RenpyResourceLimits.LimitException(
                        "renpy_invalid_range", "RPA entry range overflows");
            }
            result.put(name, new long[]{realOffset, realLength});
        }
        return result;
    }

    private static Long toLong(Object value) {
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        return null;
    }

    private static long le64(byte[] data, int position) {
        return (data[position] & 0xffL)
                | ((data[position + 1] & 0xffL) << 8)
                | ((data[position + 2] & 0xffL) << 16)
                | ((data[position + 3] & 0xffL) << 24)
                | ((data[position + 4] & 0xffL) << 32)
                | ((data[position + 5] & 0xffL) << 40)
                | ((data[position + 6] & 0xffL) << 48)
                | ((data[position + 7] & 0xffL) << 56);
    }

    private static String readAsciiLine(byte[] data, int position) {
        int end = position;
        while (end < data.length && data[end] != '\n') {
            end++;
        }
        return new String(data, position, end - position, StandardCharsets.US_ASCII);
    }

    private static int skipAsciiLine(byte[] data, int position) {
        int end = position;
        while (end < data.length && data[end] != '\n') {
            end++;
        }
        return end < data.length ? end + 1 : end;
    }

    private static long pickleLong(byte[] data, int position, int length) {
        if (length <= 0) {
            return 0L;
        }
        byte[] bigEndian = new byte[length];
        for (int i = 0; i < length; i++) {
            bigEndian[i] = data[position + length - 1 - i];
        }
        return new BigInteger(bigEndian).longValue();
    }
    private static int le16(byte[] data, int position) {
        return (data[position] & 0xff) | ((data[position + 1] & 0xff) << 8);
    }

    private static int le32(byte[] data, int position) {
        return (data[position] & 0xff)
                | ((data[position + 1] & 0xff) << 8)
                | ((data[position + 2] & 0xff) << 16)
                | ((data[position + 3] & 0xff) << 24);
    }
}
