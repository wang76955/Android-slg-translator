package com.slgtranslator.app;

import android.content.Context;
import android.net.Uri;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.InflaterInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/**
 * Adds an independent "翻译文本" entry to a Ren'Py language menu by cloning an
 * existing expendable language button inside the compiled screen pickle. The
 * original buttons (including the cloned one) are left untouched.
 */
public final class LanguageMenuSupport {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    private static final String TRANSLATOR_LABEL = "\u7ffb\u8bd1\u6587\u672c"; // 翻译文本

    private LanguageMenuSupport() {
    }

    public static void injectTranslatorMenu(Context context, Object plugin, PluginCall call) {
        String apkUri = call.getString("apkUri");
        String gameTargetLang = call.getString("gameTargetLang");
        String translatorLang = call.getString("translatorLang");
        if (apkUri == null || apkUri.isEmpty() || translatorLang == null || translatorLang.isEmpty()) {
            call.reject("apkUri and translatorLang required");
            return;
        }
        try {
            File apk = fileFrom(apkUri);
            if (apk == null || !apk.isFile()) {
                call.reject("\u8865\u4e01\u6e90 APK \u4e0d\u5b58\u5728: " + apkUri);
                return;
            }
            boolean changed = rewriteApkMenu(apk, gameTargetLang, translatorLang);
            JSObject result = new JSObject();
            result.put("changed", changed);
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("\u8bed\u8a00\u83dc\u5355\u6ce8\u5165\u5931\u8d25: " + (message == null ? e.toString() : message));
        }
    }

    private static File fileFrom(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.startsWith("file://")) {
            try {
                return new File(Uri.parse(normalized).getPath());
            } catch (RuntimeException e) {
                return null;
            }
        }
        return new File(normalized);
    }

    /** Rewrites the language menu inside an APK in place. Returns true when a menu button was added. */
    static boolean rewriteApkMenu(File apk, String gameTargetLang, String translatorLang) throws IOException {
        if (gameTargetLang == null) {
            gameTargetLang = "";
        }
        String menuEntry = null;
        byte[] newBytes = null;
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                if (!name.startsWith("assets/")) {
                    continue;
                }
                if (!(name.endsWith(".rpyc") || name.endsWith(".rpymc"))) {
                    continue;
                }
                if (name.contains("x-lang_")) {
                    continue;
                }
                if (entry.getSize() <= 0 || entry.getSize() > 8_000_000L) {
                    continue;
                }
                byte[] original = readEntry(zip, entry);
                byte[] rewritten = injectMenu(original, gameTargetLang, translatorLang);
                if (rewritten != null) {
                    menuEntry = name;
                    newBytes = rewritten;
                    break;
                }
            }
        }
        if (menuEntry == null || newBytes == null) {
            return false;
        }
        replaceZipEntry(apk, menuEntry, newBytes);
        return true;
    }

    /**
     * Returns a rewritten rpyc with an extra "翻译文本" button, or null when the
     * file has no compatible language menu / is already injected.
     */
    static byte[] injectMenu(byte[] rpyc, String gameTargetLang, String translatorLang) {
        if (rpyc.length < RPC2_MAGIC.length || !startsWith(rpyc, RPC2_MAGIC)) {
            return null;
        }
        List<int[]> slots = new ArrayList<>(); // {id, offset, length}
        int tablePos = RPC2_MAGIC.length;
        boolean sawLanguageMenu = false;
        while (tablePos + 12 <= rpyc.length) {
            int id = le32(rpyc, tablePos);
            int offset = le32(rpyc, tablePos + 4);
            int length = le32(rpyc, tablePos + 8);
            if (id == 0) {
                break;
            }
            if (offset < 0 || length < 0 || offset + length > rpyc.length) {
                return null;
            }
            slots.add(new int[]{id, offset, length});
            tablePos += 12;
        }
        if (slots.isEmpty()) {
            return null;
        }
        List<byte[]> rebuilt = new ArrayList<>();
        boolean changed = false;
        boolean menuFound = false;
        for (int[] slot : slots) {
            byte[] compressed = slice(rpyc, slot[1], slot[1] + slot[2]);
            byte[] inflated = inflate(compressed);
            if (inflated == null) {
                return null;
            }
            if (!menuFound && containsAscii(inflated, "Language(\"")) {
                menuFound = true;
            }
            byte[] next = rewriteButton(inflated, gameTargetLang, translatorLang);
            if (next == null) {
                rebuilt.add(compressed);
            } else {
                changed = true;
                rebuilt.add(deflate(next));
            }
        }
        if (!changed || !menuFound) {
            return null;
        }
        return rebuildRpc2(slots, rebuilt);
    }

    /**
     * Rewrites the last non-default, non-target language button into an
     * independent 翻译文本 entry that selects the translator language. The
     * rewrite replaces exact pickle string values and preserves the compiled
     * screen structure (the same mechanism the native mirror uses). Returns the
     * rewritten slot, or null when this slot has no compatible menu.
     */
    private static byte[] rewriteButton(byte[] data, String gameTargetLang, String translatorLang) {
        List<int[]> ops = walk(data);
        if (ops == null) {
            return null;
        }
        int candidateIdx = -1;
        String candidateLang = null;
        for (int k = 0; k < ops.size(); k++) {
            String payload = stringPayload(data, ops, k);
            if (payload == null) {
                continue;
            }
            if (payload.equals("Language(\"" + translatorLang + "\")")) {
                return null; // already injected
            }
            String lang = languageCode(payload);
            if (lang != null) {
                if (!lang.equals("None") && !lang.isEmpty() && !lang.equals(gameTargetLang)) {
                    candidateIdx = k;
                    candidateLang = lang;
                }
            }
        }
        if (candidateIdx < 0 || candidateLang == null) {
            return null;
        }
        // Extract the button's display label from the Text(("LABEL"), style=...)
        // strings that precede its Language action.
        String label = null;
        for (int k = Math.max(0, candidateIdx - 40); k < candidateIdx; k++) {
            String payload = stringPayload(data, ops, k);
            if (payload != null && payload.startsWith("Text((\"") && payload.contains("\"), style=")) {
                label = payload.substring("Text((\"".length(), payload.indexOf("\"), style="));
                if (!label.isEmpty()) {
                    break;
                }
            }
        }
        if (label == null || label.isEmpty()) {
            return null;
        }
        // Rebuild the slot: drop stale FRAME lengths, rewrite label and language.
        ByteArrayOutputStream out = new ByteArrayOutputStream(data.length + 64);
        for (int k = 0; k < ops.size(); k++) {
            int[] op = ops.get(k);
            if (op[0] == 0x95) { // FRAME lengths become stale after rewriting; frames are optional
                continue;
            }
            byte[] chunk = slice(data, op[1], op[2]);
            String payload = stringPayload(data, ops, k);
            if (payload != null && payload.startsWith("Text((\"") && payload.contains("\"), style=")) {
                String inner = payload.substring("Text((\"".length(), payload.indexOf("\"), style="));
                if (inner.equals(label)) {
                    String next = "Text((\"" + TRANSLATOR_LABEL + payload.substring(payload.indexOf("\"), style="));
                    writeShortUnicode(out, next);
                    continue;
                }
            }
            if (payload != null && payload.equals("Language(\"" + candidateLang + "\")")) {
                writeShortUnicode(out, "Language(\"" + translatorLang + "\")");
                continue;
            }
            out.write(chunk, 0, chunk.length);
        }
        return out.toByteArray();
    }

    private static void writeShortUnicode(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        out.write(0x8c);
        out.write(bytes.length);
        out.write(bytes, 0, bytes.length);
    }

    private static String stringPayload(byte[] data, List<int[]> ops, int index) {
        int[] op = ops.get(index);
        int code = op[0];
        if (code == 0x8c) { // SHORT_BINUNICODE
            int length = data[op[1] + 1] & 0xFF;
            return new String(data, op[1] + 2, length, StandardCharsets.UTF_8);
        }
        if (code == 0x58) { // BINUNICODE
            int length = le32(data, op[1] + 1);
            return new String(data, op[1] + 5, length, StandardCharsets.UTF_8);
        }
        return null;
    }

    private static String languageCode(String payload) {
        if (!payload.startsWith("Language(\"") || !payload.endsWith("\")")) {
            return null;
        }
        return payload.substring("Language(\"".length(), payload.length() - 2);
    }

    /**
     * Walks a pickle stream, returning [opcode, start, end] triples. Returns
     * null when the stream contains an opcode we do not recognize.
     */
    private static List<int[]> walk(byte[] data) {
        List<int[]> ops = new ArrayList<>();
        int pos = 0;
        int n = data.length;
        while (pos < n) {
            int b = data[pos] & 0xFF;
            int start = pos++;
            switch (b) {
                // Fixed-size arguments.
                case 0x4a: // BININT
                case 0x58: // BINUNICODE
                case 0x54: // BINSTRING
                case 0x42: // BINBYTES
                case 0x8b: // LONG4
                    pos += 4 + lengthAfter(data, pos, b);
                    break;
                case 0x4b: // BININT1
                case 0x55: // SHORT_BINSTRING
                case 0x43: // SHORT_BINBYTES
                    pos += 1 + lengthAfter(data, pos, b);
                    break;
                case 0x4d: // BININT2
                    pos += 2;
                    break;
                case 0x47: // BINFLOAT
                case 0x95: // FRAME
                    pos += 8;
                    break;
                case 0x8a: // LONG1
                case 0x8c: // SHORT_BINUNICODE
                    pos += 1 + lengthAfter(data, pos, b);
                    break;
                case 0x8d: // BINUNICODE8
                case 0x8e: // BINBYTES8
                case 0x96: // BYTEARRAY8
                    pos += 8 + (int) le64(data, pos);
                    break;
                case 0x68: // BINGET
                case 0x71: // BINPUT
                case 0x82: // EXT1
                case 0x80: // PROTO
                    pos += 1;
                    break;
                case 0x6a: // LONG_BINGET
                case 0x72: // LONG_BINPUT
                    pos += 4;
                    break;
                case 0x84: // EXT4
                    pos += 4;
                    break;
                case 0x83: // EXT2
                    pos += 2;
                    break;
                case 0x49: // INT
                case 0x4c: // LONG
                case 0x53: // STRING
                case 0x56: // UNICODE
                case 0x46: // FLOAT
                case 0x67: // GET
                case 0x70: // PUT
                case 0x50: // PERSID
                    pos = skipNewline(data, pos);
                    break;
                case 0x63: // GLOBAL
                case 0x69: // INST
                    pos = skipNewline(data, pos);
                    pos = skipNewline(data, pos);
                    break;
                // Zero-argument opcodes.
                case 0x28: // MARK
                case 0x2e: // STOP
                case 0x29: // EMPTY_TUPLE
                case 0x30: // POP
                case 0x31: // POP_MARK
                case 0x32: // DUP
                case 0x4e: // NONE
                case 0x52: // REDUCE
                case 0x62: // BUILD
                case 0x61: // APPEND
                case 0x65: // APPENDS
                case 0x6c: // LIST
                case 0x5d: // EMPTY_LIST
                case 0x64: // DICT
                case 0x7d: // EMPTY_DICT
                case 0x6f: // OBJ
                case 0x73: // SETITEM
                case 0x74: // TUPLE
                case 0x75: // SETITEMS
                case 0x85: // TUPLE1
                case 0x86: // TUPLE2
                case 0x87: // TUPLE3
                case 0x88: // NEWTRUE
                case 0x89: // NEWFALSE
                case 0x8f: // EMPTY_SET
                case 0x90: // ADDITEMS
                case 0x91: // FROZENSET
                case 0x93: // STACK_GLOBAL
                case 0x81: // NEWOBJ
                case 0x92: // NEWOBJ_EX
                case 0x94: // MEMOIZE
                case 0x51: // BINPERSID
                    break;
                default:
                    return null;
            }
            if (pos > n) {
                return null;
            }
            ops.add(new int[]{b, start, pos});
        }
        return ops;
    }

    /** Reads the payload length that follows a length-prefixed opcode. */
    private static int lengthAfter(byte[] data, int pos, int code) {
        switch (code) {
            case 0x4a: // BININT payload is the int itself (4 bytes)
            case 0x4b:
            case 0x4d:
            case 0x68:
            case 0x71:
            case 0x6a:
            case 0x72:
            case 0x82:
            case 0x83:
            case 0x84:
            case 0x80:
            case 0x47:
            case 0x95:
                return 0;
            case 0x8c: // SHORT_BINUNICODE
            case 0x55: // SHORT_BINSTRING
            case 0x43: // SHORT_BINBYTES
            case 0x8a: // LONG1
                return data[pos] & 0xFF;
            default: // 4-byte lengths
                return le32(data, pos);
        }
    }

    private static int skipNewline(byte[] data, int pos) {
        while (pos < data.length && data[pos] != (byte) '\n') {
            pos++;
        }
        return pos + 1;
    }

    private static byte[] rebuildRpc2(List<int[]> slots, List<byte[]> payloads) {
        int tableBytes = (slots.size() + 1) * 12;
        int dataStart = RPC2_MAGIC.length + tableBytes;
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(RPC2_MAGIC, 0, RPC2_MAGIC.length);
        for (int i = 0; i < slots.size(); i++) {
            writeIntLe(out, slots.get(i)[0]);
            writeIntLe(out, dataStart);
            writeIntLe(out, payloads.get(i).length);
            dataStart += payloads.get(i).length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        for (byte[] payload : payloads) {
            out.write(payload, 0, payload.length);
        }
        return out.toByteArray();
    }

    private static byte[] inflate(byte[] data) {
        try {
            try (InputStream in = new InflaterInputStream(new ByteArrayInputStream(data));
                 ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int read;
                while ((read = in.read(buffer)) != -1) {
                    out.write(buffer, 0, read);
                }
                return out.toByteArray();
            }
        } catch (IOException e) {
            return null;
        }
    }

    private static byte[] deflate(byte[] data) {
        try {
            try (ByteArrayOutputStream raw = new ByteArrayOutputStream();
                 DeflaterOutputStream out = new DeflaterOutputStream(raw)) {
                out.write(data, 0, data.length);
                out.finish();
                return raw.toByteArray();
            }
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private static void replaceZipEntry(File apk, String entryName, byte[] newData) throws IOException {
        File temporary = new File(apk.getAbsolutePath() + ".menu.tmp");
        byte[] buffer = new byte[65536];
        try (ZipFile zip = new ZipFile(apk);
             ZipOutputStream out = new ZipOutputStream(new FileOutputStream(temporary))) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                ZipEntry next = new ZipEntry(name);
                next.setTime(entry.getTime());
                if (name.equals(entryName)) {
                    next.setMethod(ZipEntry.DEFLATED);
                    out.putNextEntry(next);
                    out.write(newData, 0, newData.length);
                } else {
                    if (entry.getMethod() == ZipEntry.STORED) {
                        next.setMethod(ZipEntry.STORED);
                        next.setSize(entry.getSize());
                        next.setCompressedSize(entry.getSize());
                        next.setCrc(entry.getCrc());
                    } else {
                        next.setMethod(ZipEntry.DEFLATED);
                    }
                    out.putNextEntry(next);
                    try (InputStream in = zip.getInputStream(entry)) {
                        int read;
                        while ((read = in.read(buffer)) != -1) {
                            out.write(buffer, 0, read);
                        }
                    }
                }
                out.closeEntry();
            }
        }
        if (!apk.delete()) {
            temporary.delete();
            throw new IOException("\u65e0\u6cd5\u66ff\u6362\u6e90 APK\uff0c\u8bf7\u91ca\u653e\u5b58\u50a8\u7a7a\u95f4");
        }
        if (!temporary.renameTo(apk)) {
            throw new IOException("\u6ce8\u5165\u540e\u91cd\u547d\u540d\u5931\u8d25");
        }
    }

    private static byte[] readEntry(ZipFile zip, ZipEntry entry) throws IOException {
        try (InputStream in = zip.getInputStream(entry);
             ByteArrayOutputStream out = new ByteArrayOutputStream((int) entry.getSize())) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        }
    }

    private static boolean containsAscii(byte[] data, String token) {
        byte[] needle = token.getBytes(StandardCharsets.US_ASCII);
        outer:
        for (int i = 0; i + needle.length <= data.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (data[i + j] != needle[j]) {
                    continue outer;
                }
            }
            return true;
        }
        return false;
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
        byte[] out = new byte[end - start];
        System.arraycopy(data, start, out, 0, out.length);
        return out;
    }

    private static int le32(byte[] data, int pos) {
        return (data[pos] & 0xFF)
                | ((data[pos + 1] & 0xFF) << 8)
                | ((data[pos + 2] & 0xFF) << 16)
                | ((data[pos + 3] & 0xFF) << 24);
    }

    private static long le64(byte[] data, int pos) {
        long value = 0;
        for (int i = 7; i >= 0; i--) {
            value = (value << 8) | (data[pos + i] & 0xFFL);
        }
        return value;
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xFF);
        out.write((value >>> 8) & 0xFF);
        out.write((value >>> 16) & 0xFF);
        out.write((value >>> 24) & 0xFF);
    }
}
