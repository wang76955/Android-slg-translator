package com.slgtranslator.app;

import android.content.Context;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
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
 * Compiles the generated Ren'Py translation .rpy files into compiled .rpyc
 * files that the Android archive loader can actually read. Ren'Py loads
 * scripts from an APK archive only when they are .rpyc; plain .rpy files in
 * the archive are ignored by the script scanner, which is why selecting the
 * injected 翻译文本 language never switched the game text before.
 */
public final class TranslationCompiler {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    private TranslationCompiler() {
    }

    public static void compileTranslationsIntoApk(Context context, PluginCall call) {
        String apkUri = call.getString("apkUri");
        if (apkUri == null || apkUri.isEmpty()) {
            call.reject("apkUri required");
            return;
        }
        try {
            File apk = fileFrom(apkUri);
            if (apk == null || !apk.isFile()) {
                call.reject("\u8865\u4e01\u6e90 APK \u4e0d\u5b58\u5728: " + apkUri);
                return;
            }
            TemplateMeta meta = readTemplateMeta(apk);
            java.util.LinkedHashMap<String, String> merged = new java.util.LinkedHashMap<>();
            String language = null;
            // Read the generated translation .rpy files straight from the output
            // directory. Passing them through the JS bridge truncates large
            // payloads, which silently dropped most files.
            File outputDir = new File(context.getExternalFilesDir(null), "SLG-Translator-Output");
            List<File> rpyFiles = new ArrayList<>();
            collectSlgRpy(outputDir, rpyFiles);
            for (File rpy : rpyFiles) {
                String content = readTextFile(rpy);
                if (content == null || content.isEmpty()) {
                    continue;
                }
                if (language == null) {
                    language = languageOf(rpy.getPath(), content);
                }
                for (String[] pair : parseTranslationRpy(content)) {
                    if (pair[0] == null || pair[0].isEmpty()) {
                        continue;
                    }
                    if (!merged.containsKey(pair[0])) {
                        merged.put(pair[0], pair[1]);
                    }
                }
            }
            if (language == null || language.isEmpty() || merged.isEmpty()) {
                JSObject result = new JSObject();
                result.put("compiled", 0);
                call.resolve(result);
                return;
            }
            List<String[]> pairs = new ArrayList<>();
            for (java.util.Map.Entry<String, String> entry : merged.entrySet()) {
                pairs.add(new String[]{entry.getKey(), entry.getValue()});
            }
            String rpycPath = "assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc";
            String filename = "game/tl/slgtranslated/translations.rpy";
            byte[] rpyc = compileRpyc(language, filename, pairs, meta);
            List<String[]> pending = new ArrayList<>();
            List<byte[]> pendingBytes = new ArrayList<>();
            pending.add(new String[]{rpycPath, filename});
            pendingBytes.add(rpyc);
            byte[] styleRpyc = cloneChineseStyleRpyc(apk);
            if (styleRpyc != null) {
                pending.add(new String[]{"assets/x-game/x-tl/x-slgtranslated/x-style.rpyc",
                        "game/tl/slgtranslated/style.rpy"});
                pendingBytes.add(styleRpyc);
            }
            rewriteApkWithEntries(apk, pending, pendingBytes);
            JSObject result = new JSObject();
            result.put("compiled", merged.size());
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("\u7f16\u8bd1\u7ffb\u8bd1\u8d44\u6e90\u5931\u8d25: " + (message == null ? e.toString() : message));
        }
    }

    /** Only the independent translator language bucket is compiled here. */
    private static boolean isTranslatorBucket(String path) {
        String normalized = path.replace('\\', '/').toLowerCase();
        return normalized.contains("/x-tl/x-slgtranslated/")
                || normalized.contains("/x-tl/x-slgtranslated")
                || normalized.contains("/tl/slgtranslated/");
    }

    private static void collectSlgRpy(File dir, List<File> out) {
        File[] files = dir.listFiles();
        if (files == null) {
            return;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                if (isTranslatorBucket(file.getAbsolutePath())) {
                    collectRpyFiles(file, out);
                } else {
                    collectSlgRpy(file, out);
                }
            }
        }
    }

    private static void collectRpyFiles(File dir, List<File> out) {
        File[] files = dir.listFiles();
        if (files == null) {
            return;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                collectRpyFiles(file, out);
            } else if (file.getName().endsWith(".rpy")) {
                out.add(file);
            }
        }
    }

    private static String readTextFile(File file) {
        try (InputStream in = new java.io.FileInputStream(file);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "";
        }
    }

    private static String languageOf(String path, String content) {
        String normalized = path.replace('\\', '/').toLowerCase();
        if (normalized.contains("slgtranslated")) {
            return "slgtranslated";
        }
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("translate\\s+([A-Za-z0-9_]+)\\s+strings:")
                .matcher(content);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return null;
    }

    /** Converts an APK asset path to the Ren'Py runtime path (x- prefixes stripped). */
    static String runtimeFilename(String apkPath) {
        String normalized = apkPath.replace('\\', '/');
        int idx = normalized.lastIndexOf("/assets/");
        String relative = idx >= 0 ? normalized.substring(idx + "/assets/".length()) : normalized;
        String[] parts = relative.split("/");
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            String part = parts[i];
            if (part.startsWith("x-") && part.length() > 2) {
                part = part.substring(2);
            }
            if (i > 0) {
                out.append('/');
            }
            out.append(part);
        }
        return "game/" + out;
    }

    /**
     * Parses a generated translation .rpy containing
     * {@code translate <lang> strings:} blocks with {@code old/new} pairs.
     */
    static List<String[]> parseTranslationRpy(String content) {
        List<String[]> pairs = new ArrayList<>();
        String[] lines = content.replace("\r\n", "\n").split("\n", -1);
        boolean inStringsBlock = false;
        String oldText = null;
        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.startsWith("translate ") && trimmed.contains(" strings:")) {
                inStringsBlock = true;
                oldText = null;
                continue;
            }
            if (!inStringsBlock) {
                continue;
            }
            if (trimmed.startsWith("old ")) {
                oldText = unquote(trimmed.substring(4).trim());
            } else if (trimmed.startsWith("new ") && oldText != null) {
                String newText = unquote(trimmed.substring(4).trim());
                if (newText != null) {
                    pairs.add(new String[]{oldText, newText});
                }
                oldText = null;
            }
        }
        return pairs;
    }

    /** Unquotes a Ren'Py string literal (JSON-style escaping used by the app). */
    private static String unquote(String value) {
        if (value == null || value.length() < 2) {
            return null;
        }
        char first = value.charAt(0);
        char last = value.charAt(value.length() - 1);
        if (first != '"' || last != '"') {
            return null;
        }
        StringBuilder out = new StringBuilder();
        String body = value.substring(1, value.length() - 1);
        int i = 0;
        while (i < body.length()) {
            char c = body.charAt(i);
            if (c != '\\' || i + 1 >= body.length()) {
                out.append(c);
                i++;
                continue;
            }
            char next = body.charAt(i + 1);
            switch (next) {
                case 'n':
                    out.append('\n');
                    break;
                case 't':
                    out.append('\t');
                    break;
                case 'r':
                    out.append('\r');
                    break;
                case '\\':
                    out.append('\\');
                    break;
                case '"':
                    out.append('"');
                    break;
                case '\'':
                    out.append('\'');
                    break;
                case 'u':
                    if (i + 5 < body.length()) {
                        try {
                            int code = Integer.parseInt(body.substring(i + 2, i + 6), 16);
                            out.append((char) code);
                            i += 4;
                        } catch (NumberFormatException e) {
                            out.append(next);
                        }
                    } else {
                        out.append(next);
                    }
                    break;
                default:
                    out.append(next);
                    break;
            }
            i += 2;
        }
        return out.toString();
    }

    // ------------------------------------------------------------------
    // Pickle + RPC2 generation
    // ------------------------------------------------------------------

    static byte[] compileRpyc(String language, String filename, List<String[]> pairs, TemplateMeta meta) {
        byte[] pickle = buildPickle(language, filename, pairs, meta.version, meta.key);
        byte[] slot = deflate(pickle);
        ByteArrayOutputStream out = new ByteArrayOutputStream(pickle.length + 96);
        out.write(RPC2_MAGIC, 0, RPC2_MAGIC.length);
        int dataStart = RPC2_MAGIC.length + 3 * 12;
        for (int slotId = 1; slotId <= 2; slotId++) {
            writeIntLe(out, slotId);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot, 0, slot.length);
        out.write(slot, 0, slot.length);
        if (meta.trailer != null && meta.trailer.length == 16) {
            out.write(meta.trailer, 0, meta.trailer.length);
        }
        return out.toByteArray();
    }

    static byte[] buildPickle(String language, String filename, List<String[]> pairs, int version, String key) {
        ByteArrayOutputStream p = new ByteArrayOutputStream();
        p.write(0x80); // PROTO
        p.write(0x02);
        // data dict
        p.write(0x7d); // EMPTY_DICT
        p.write(0x28); // MARK
        writeShort(p, "version");
        writeInt(p, version);
        writeShort(p, "key");
        writeShort(p, key);
        writeShort(p, "deferred_parse_errors");
        writeGlobal(p, "collections", "defaultdict");
        writeGlobal(p, "builtins", "list");
        p.write(0x85); // TUPLE1
        p.write(0x52); // REDUCE
        p.write(0x75); // SETITEMS
        // stmts list
        p.write(0x5d); // EMPTY_LIST
        p.write(0x28); // MARK
        // Init node
        writeGlobal(p, "renpy.ast", "Init");
        p.write(0x29); // EMPTY_TUPLE
        p.write(0x81); // NEWOBJ
        p.write(0x4e); // NONE
        p.write(0x7d); // EMPTY_DICT
        p.write(0x28); // MARK
        writeShort(p, "linenumber");
        writeInt(p, 1);
        writeShort(p, "filename");
        writeString(p, filename);
        writeShort(p, "name");
        writeString(p, filename);
        writeInt(p, 1784316460);
        writeInt(p, 1416);
        p.write(0x87); // TUPLE3 (name)
        writeShort(p, "next");
        p.write(0x4e); // NONE
        writeShort(p, "block");
        p.write(0x5d); // EMPTY_LIST
        p.write(0x28); // MARK
        int line = 3;
        int serial = 1417;
        for (String[] pair : pairs) {
            writeGlobal(p, "renpy.ast", "TranslateString");
            p.write(0x29);
            p.write(0x81);
            p.write(0x4e);
            p.write(0x7d);
            p.write(0x28);
            writeShort(p, "linenumber");
            writeInt(p, line);
            writeShort(p, "filename");
            writeString(p, filename);
            writeShort(p, "name");
            writeString(p, filename);
            writeInt(p, 1784316460);
            writeInt(p, serial++);
            p.write(0x87); // TUPLE3 (name)
            writeShort(p, "next");
            p.write(0x4e); // NONE
            writeShort(p, "language");
            writeString(p, language);
            writeShort(p, "old");
            writeString(p, pair[0]);
            writeShort(p, "new");
            writeString(p, pair[1]);
            writeShort(p, "newloc");
            writeString(p, filename);
            writeInt(p, line);
            p.write(0x86); // TUPLE2
            p.write(0x75); // SETITEMS
            p.write(0x86); // TUPLE2 state
            p.write(0x62); // BUILD
            line += 2;
        }
        p.write(0x65); // APPENDS
        writeShort(p, "priority");
        p.write(0x4b); // BININT1
        p.write(0);
        p.write(0x75); // SETITEMS
        p.write(0x86); // TUPLE2
        p.write(0x62); // BUILD
        // Return node
        writeGlobal(p, "renpy.ast", "Return");
        p.write(0x29);
        p.write(0x81);
        p.write(0x4e);
        p.write(0x7d);
        p.write(0x28);
        writeShort(p, "linenumber");
        writeInt(p, line);
        writeShort(p, "filename");
        writeString(p, filename);
        writeShort(p, "expression");
        p.write(0x4e); // NONE
        writeShort(p, "name");
        writeString(p, filename);
        writeInt(p, 1784316460);
        writeInt(p, serial);
        p.write(0x87); // TUPLE3 (name)
        writeShort(p, "next");
        p.write(0x4e); // NONE
        p.write(0x75); // SETITEMS
        p.write(0x86); // TUPLE2
        p.write(0x62); // BUILD
        p.write(0x65); // APPENDS stmts
        p.write(0x86); // TUPLE2 (data, stmts)
        p.write(0x2e); // STOP
        return p.toByteArray();
    }

    private static void writeGlobal(ByteArrayOutputStream out, String module, String name) {
        writeShort(out, module);
        writeShort(out, name);
        out.write(0x93); // STACK_GLOBAL
    }

    private static void writeShort(ByteArrayOutputStream out, String value) {
        writeString(out, value);
    }

    private static void writeString(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= 255) {
            out.write(0x8c); // SHORT_BINUNICODE
            out.write(bytes.length);
        } else {
            out.write(0x58); // BINUNICODE
            writeIntLe(out, bytes.length);
        }
        out.write(bytes, 0, bytes.length);
    }

    private static void writeInt(ByteArrayOutputStream out, int value) {
        if (value >= 0 && value <= 0xff) {
            out.write(0x4b); // BININT1
            out.write(value);
        } else if (value >= -0x8000 && value <= 0x7fff) {
            out.write(0x4d); // BININT2
            out.write(value & 0xff);
            out.write((value >>> 8) & 0xff);
        } else {
            out.write(0x4a); // BININT
            writeIntLe(out, value);
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

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    // ------------------------------------------------------------------
    // Template metadata extraction
    // ------------------------------------------------------------------

    static final class TemplateMeta {
        int version;
        String key = "unlocked";
        byte[] trailer;
    }

    static TemplateMeta readTemplateMeta(File apk) throws IOException {
        TemplateMeta meta = new TemplateMeta();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                if (!name.startsWith("assets/") || !name.endsWith(".rpyc")) {
                    continue;
                }
                if (entry.getSize() <= 0 || entry.getSize() > 16_000_000L) {
                    continue;
                }
                byte[] bytes = readEntry(zip, entry);
                if (!startsWith(bytes, RPC2_MAGIC)) {
                    continue;
                }
                byte[] pickle = readSlot(bytes, 2);
                if (pickle == null) {
                    pickle = readSlot(bytes, 1);
                }
                if (pickle != null) {
                    Object[] found = scanVersionKey(pickle);
                    if ((Integer) found[0] != 0) {
                        meta.version = (Integer) found[0];
                        if (found[1] != null) {
                            meta.key = (String) found[1];
                        }
                        meta.trailer = slice(bytes, Math.max(0, bytes.length - 16), bytes.length);
                        return meta;
                    }
                }
            }
        }
        throw new IOException("\u672a\u627e\u5230\u53ef\u7528\u7684 Ren'Py \u7f16\u8bd1\u811a\u672c\u6a21\u677f");
    }

    /**
     * Walks the pickle stream and returns {version, keyIndexOffset...} values
     * found after the 'version' and 'key' dictionary keys.
     */

    private static byte[] readSlot(byte[] rpyc, int slotId) {
        int pos = RPC2_MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            int id = le32(rpyc, pos);
            int offset = le32(rpyc, pos + 4);
            int length = le32(rpyc, pos + 8);
            if (id == 0) {
                return null;
            }
            if (id == slotId) {
                if (offset < 0 || length < 0 || offset + length > rpyc.length) {
                    return null;
                }
                try (InputStream in = new InflaterInputStream(
                        new java.io.ByteArrayInputStream(rpyc, offset, length));
                     ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                    byte[] buffer = new byte[8192];
                    int read;
                    while ((read = in.read(buffer)) != -1) {
                        out.write(buffer, 0, read);
                    }
                    return out.toByteArray();
                } catch (IOException e) {
                    return null;
                }
            }
            pos += 12;
        }
        return null;
    }

    // ------------------------------------------------------------------
    // Zip rewriting
    // ------------------------------------------------------------------

    private static void rewriteApkWithEntries(File apk, List<String[]> entries, List<byte[]> contents)
            throws IOException {
        File temporary = new File(apk.getAbsolutePath() + ".tl.tmp");
        byte[] buffer = new byte[65536];
        try (ZipFile zip = new ZipFile(apk);
             ZipOutputStream out = new ZipOutputStream(new FileOutputStream(temporary))) {
            java.util.Set<String> written = new java.util.HashSet<>();
            Enumeration<? extends ZipEntry> all = zip.entries();
            while (all.hasMoreElements()) {
                ZipEntry entry = all.nextElement();
                String name = entry.getName();
                ZipEntry next = new ZipEntry(name);
                next.setTime(entry.getTime());
                int replaceIndex = indexOfEntry(entries, name);
                if (replaceIndex >= 0) {
                    next.setMethod(ZipEntry.DEFLATED);
                    out.putNextEntry(next);
                    out.write(contents.get(replaceIndex), 0, contents.get(replaceIndex).length);
                    written.add(name);
                } else {
                    if (isStaleTranslationRpy(name)) {
                        continue; // drop stale .rpy translations; compiled .rpyc are authoritative
                    }
                    if (isStaleGeneratedRpyc(name, entry.getTime())) {
                        continue; // drop compiled translations the app generated for non-translator buckets
                    }
                    copyZipEntry(zip, entry, next, out, buffer);
                }
                out.closeEntry();
            }
            for (int i = 0; i < entries.size(); i++) {
                String name = entries.get(i)[0];
                if (written.contains(name)) {
                    continue;
                }
                ZipEntry next = new ZipEntry(name);
                next.setMethod(ZipEntry.DEFLATED);
                out.putNextEntry(next);
                out.write(contents.get(i), 0, contents.get(i).length);
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

    private static int indexOfEntry(List<String[]> entries, String name) {
        for (int i = 0; i < entries.size(); i++) {
            if (entries.get(i)[0].equals(name)) {
                return i;
            }
        }
        return -1;
    }

    /**
     * True for legacy .rpy translation files under a Ren'Py tl directory.
     * Ren'Py loads them after the game extracts the APK and they collide
     * with the compiled .rpyc versions, so stale copies are removed when the
     * compiled translator bucket is written.
     */
    private static boolean isStaleTranslationRpy(String name) {
        if (name == null || !name.endsWith(".rpy")) {
            return false;
        }
        String normalized = name.replace('\\', '/');
        if (normalized.contains("/x-tl/") || normalized.contains("/tl/")) {
            return true;
        }
        return false;
    }

    /**
     * True for compiled translation files the app itself generated for the
     * non-translator language buckets (the mirror step compiles the .rpy
     * outputs into .rpyc). They duplicate strings across files and crash
     * Ren'Py, so they are removed while the compiled translator bucket is
     * written. Original game files use the Ren'Py epoch timestamp; only
     * recently-written entries are considered stale.
     */
    private static boolean isStaleGeneratedRpyc(String name, long time) {
        if (name == null || !name.endsWith(".rpyc") || time < 946684800000L) {
            return false; // keep original epoch-dated files
        }
        String normalized = name.replace('\\', '/').toLowerCase();
        // The whole translator bucket is rewritten as one merged file, so
        // previous per-file compiled outputs are dropped as well.
        return normalized.contains("/x-tl/") || normalized.contains("/tl/");
    }

    /**
     * Finds the game's built-in Chinese style file (the one that switches
     * fonts to a CJK-capable font) and clones it for the translator
     * language. Returns the rewritten rpyc bytes, or null when unavailable.
     */
    private static byte[] cloneChineseStyleRpyc(File apk) throws IOException {
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                if (!name.startsWith("assets/") || !name.endsWith(".rpyc")) {
                    continue;
                }
                String lower = name.toLowerCase();
                if (!lower.contains("/x-tl/x-chinese/") && !lower.contains("/tl/chinese/")) {
                    continue;
                }
                if (entry.getSize() <= 0 || entry.getSize() > 8_000_000L) {
                    continue;
                }
                byte[] bytes = readEntry(zip, entry);
                if (!startsWith(bytes, RPC2_MAGIC)) {
                    continue;
                }
                if (!containsStyleBytes(bytes)) {
                    continue;
                }
                byte[] rewritten = rewriteRpycLanguage(bytes, "chinese", "slgtranslated");
                if (rewritten != null) {
                    return rewritten;
                }
            }
        }
        return null;
    }

    private static boolean containsStyleBytes(byte[] rpyc) {
        byte[] pickle = readSlot(rpyc, 2);
        if (pickle == null) {
            pickle = readSlot(rpyc, 1);
        }
        if (pickle == null) {
            return false;
        }
        return containsAscii(pickle, "text_font") || containsAscii(pickle, "style_name");
    }

    /**
     * Rewrites a compiled translation file so the language value becomes
     * {@code newLang} (used to clone the game's Chinese font/style setup for
     * the translator language). Only whole string values are replaced.
     */
    static byte[] rewriteRpycLanguage(byte[] rpyc, String oldLang, String newLang) {
        List<int[]> slots = new ArrayList<>();
        int tablePos = RPC2_MAGIC.length;
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
        byte[] oldBytes = oldLang.getBytes(StandardCharsets.UTF_8);
        byte[] newBytes = newLang.getBytes(StandardCharsets.UTF_8);
        byte[] oldFilenamePrefix = ("game/tl/" + oldLang + "/").getBytes(StandardCharsets.UTF_8);
        byte[] newFilenamePrefix = ("game/tl/" + newLang + "/").getBytes(StandardCharsets.UTF_8);
        for (int[] slot : slots) {
            byte[] compressed = slice(rpyc, slot[1], slot[1] + slot[2]);
            byte[] inflated = inflate(compressed);
            if (inflated == null) {
                return null;
            }
            List<int[]> ops = LanguageMenuSupport.walk(inflated);
            if (ops == null) {
                return null;
            }
            ByteArrayOutputStream out = new ByteArrayOutputStream(inflated.length + 32);
            boolean slotChanged = false;
            for (int k = 0; k < ops.size(); k++) {
                int[] op = ops.get(k);
                if (op[0] == 0x95) { // FRAME lengths become stale; frames are optional
                    continue;
                }
                String payload = LanguageMenuSupport.stringPayload(inflated, ops, k);
                if (payload != null) {
                    if (payload.equals(oldLang)) {
                        writePickleString(out, newLang);
                        slotChanged = true;
                        continue;
                    }
                    if (payload.startsWith("game/tl/" + oldLang + "/")) {
                        writePickleString(out, "game/tl/" + newLang + payload.substring(("game/tl/" + oldLang).length()));
                        slotChanged = true;
                        continue;
                    }
                }
                out.write(inflated, op[1], op[2] - op[1]);
            }
            rebuilt.add(slotChanged ? deflate(out.toByteArray()) : compressed);
            changed |= slotChanged;
        }
        if (!changed) {
            return null;
        }
        byte[] trailer = slice(rpyc, Math.max(0, rpyc.length - 16), rpyc.length);
        return rebuildRpc2WithTrailer(slots, rebuilt, trailer);
    }

    private static byte[] concat(byte[] left, byte[] right) {
        byte[] out = new byte[left.length + right.length];
        System.arraycopy(left, 0, out, 0, left.length);
        System.arraycopy(right, 0, out, left.length, right.length);
        return out;
    }

    private static void writePickleString(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= 255) {
            out.write(0x8c);
            out.write(bytes.length);
        } else {
            out.write(0x58);
            writeIntLe(out, bytes.length);
        }
        out.write(bytes, 0, bytes.length);
    }

    private static byte[] rebuildRpc2WithTrailer(List<int[]> slots, List<byte[]> payloads, byte[] trailer) {
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
        if (trailer != null) {
            out.write(trailer, 0, trailer.length);
        }
        return out.toByteArray();
    }

    private static void copyZipEntry(ZipFile zip, ZipEntry entry, ZipEntry next, ZipOutputStream out,
                                     byte[] buffer) throws IOException {
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

    private static File fileFrom(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.startsWith("file://")) {
            try {
                return new File(URI.create(normalized));
            } catch (RuntimeException e) {
                return null;
            }
        }
        return new File(normalized);
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
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }
    /**
     * Walks the pickle stream and extracts the version int (after the
     * 'version' key) and the key string (after the 'key' key).
     */
    private static Object[] scanVersionKey(byte[] data) {
        int version = 0;
        String keyValue = null;
        int pos = 0;
        int n = data.length;
        String lastString = null;
        while (pos < n) {
            int b = data[pos] & 0xff;
            if (b == 0x8c || b == 0x58) { // SHORT_BINUNICODE / BINUNICODE
                int len;
                int start;
                if (b == 0x8c) {
                    if (pos + 2 > n) {
                        break;
                    }
                    len = data[pos + 1] & 0xff;
                    start = pos + 2;
                } else {
                    if (pos + 5 > n) {
                        break;
                    }
                    len = le32(data, pos + 1);
                    start = pos + 5;
                }
                if (start + len > n) {
                    break;
                }
                String s = new String(data, start, len, StandardCharsets.UTF_8);
                if ("key".equals(lastString)) {
                    keyValue = s;
                    lastString = null;
                } else {
                    lastString = s;
                }
                pos = start + len;
                continue;
            } else if (b == 0x4a || b == 0x4b || b == 0x4d) { // BININT variants
                int v;
                if (b == 0x4a) {
                    if (pos + 5 > n) {
                        break;
                    }
                    v = le32(data, pos + 1);
                    pos += 5;
                } else if (b == 0x4b) {
                    if (pos + 2 > n) {
                        break;
                    }
                    v = data[pos + 1] & 0xff;
                    pos += 2;
                } else {
                    if (pos + 3 > n) {
                        break;
                    }
                    v = (data[pos + 1] & 0xff) | ((data[pos + 2] & 0xff) << 8);
                    pos += 3;
                }
                if ("version".equals(lastString)) {
                    version = v;
                    lastString = null;
                }
                continue;
            } else {
                pos++;
            }
        }
        if (version == 0) {
            return new Object[]{0, null};
        }
        return new Object[]{version, keyValue};
    }
}
