package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
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
        long[] location = index.get(internalName);
        if (location == null) {
            throw new IOException("RPA entry not found: " + internalName);
        }
        long offset = location[0];
        long length = location[1];
        if (offset < 0 || length < 0 || offset + length > data.length) {
            throw new IOException("RPA entry out of bounds: " + internalName);
        }
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
                while ((read = in.read(buffer)) != -1) {
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
        long[] location = index.get(internalName);
        if (location == null) {
            throw new IOException("RPA entry not found: " + internalName);
        }
        long offset = location[0];
        long length = location[1];
        if (offset < 0 || length < 0 || length > Integer.MAX_VALUE) {
            throw new IOException("RPA entry out of bounds: " + internalName);
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
                position += read;
            }
            return result;
        }
    }

    private static byte[] readIndexBytes(InputStream in, byte[] head, long indexOffset) throws IOException {
        ByteArrayOutputStream all = new ByteArrayOutputStream();
        if (indexOffset >= 0 && indexOffset < head.length) {
            all.write(head, (int) indexOffset, head.length - (int) indexOffset);
        } else if (indexOffset > head.length) {
            skipFully(in, indexOffset - head.length);
        }
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) != -1) {
            all.write(buffer, 0, read);
        }
        return all.toByteArray();
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

    private static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
        return out.toByteArray();
    }

    private static void skipFully(InputStream in, long count) throws IOException {
        long remaining = count;
        while (remaining > 0) {
            long skipped = in.skip(remaining);
            if (skipped <= 0) {
                if (in.read() == -1) {
                    return;
                }
                remaining--;
            } else {
                remaining -= skipped;
            }
        }
    }

    private static Map<String, long[]> readIndex(byte[] data, String archiveName) {
        if (data == null || data.length == 0) {
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
            byte[] compressed = slice(data, (int) indexOffset, data.length);
            return parseIndexPickle(inflate(compressed), true, key);
        }
        if (startsWith(data, RPA2_MAGIC)) {
            if (data.length < 25) {
                return Collections.emptyMap();
            }
            long indexOffset = parseHex(data, 8, 16);
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
        try (InputStream in = new InflaterInputStream(new ByteArrayInputStream(data));
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
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
                        int length = data[position++] & 0xff;
                        stack.add(new String(data, position, length, StandardCharsets.UTF_8));
                        position += length;
                        break;
                    }
                    case 0x58: { // BINUNICODE
                        int length = le32(data, position);
                        position += 4;
                        stack.add(new String(data, position, length, StandardCharsets.UTF_8));
                        position += length;
                        break;
                    }
                    case 0x43: { // SHORT_BINBYTES
                        int length = data[position++] & 0xff;
                        stack.add(Arrays.copyOfRange(data, position, position + length));
                        position += length;
                        break;
                    }
                    case 0x42: { // BINBYTES
                        int length = le32(data, position);
                        position += 4;
                        stack.add(Arrays.copyOfRange(data, position, position + length));
                        position += length;
                        break;
                    }
                    case 0x8e: { // BINBYTES8
                        long length = le64(data, position);
                        position += 8;
                        if (length < 0 || length > Integer.MAX_VALUE) {
                            return Collections.emptyMap();
                        }
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
                        int length = data[position++] & 0xff;
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
        for (Map.Entry<Object, Object> entry : ((Map<Object, Object>) value).entrySet()) {
            if (!(entry.getKey() instanceof String)) {
                continue;
            }
            String name = (String) entry.getKey();
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
