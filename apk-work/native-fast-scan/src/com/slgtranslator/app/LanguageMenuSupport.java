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
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.InflaterInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

/**
 * Adds an independent "翻译文本" entry to a Ren'Py language menu by cloning an
 * existing expendable language button inside the compiled screen pickle. The
 * original buttons (including the cloned one) are left untouched.
 */
public final class LanguageMenuSupport {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    private static final String TRANSLATOR_LABEL = "\u7ffb\u8bd1\u6587\u672c"; // 翻译文本
    private static final int STATUS_NOOP = 0;
    private static final int STATUS_CHANGED = 1;
    private static final int STATUS_ALREADY = 2;
    private static final Object MENU_REWRITE_LOCK = new Object();

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
        // Resolving a content URI and rewriting an APK can involve gigabytes
        // of I/O. Keep the Capacitor bridge thread responsive while preserving
        // the existing single resolve/reject result contract.
        Thread worker = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    File apk = resolveApk(context, apkUri);
                    if (apk == null || !apk.isFile()) {
                        call.reject("\u8865\u4e01\u6e90 APK \u4e0d\u5b58\u5728: " + apkUri);
                        return;
                    }
                    int status = rewriteApkMenu(apk, gameTargetLang, translatorLang);
                    String resolvedApkUri = Uri.fromFile(apk).toString();
                    JSObject result = new JSObject();
                    result.put("changed", status == STATUS_CHANGED);
                    result.put("ready", status != STATUS_NOOP);
                    result.put("resolvedApkUri", resolvedApkUri);
                    result.put("uri", resolvedApkUri);
                    result.put("baseUri", resolvedApkUri);
                    call.resolve(result);
                } catch (Exception e) {
                    String message = e.getMessage();
                    call.reject("\u8bed\u8a00\u83dc\u5355\u6ce8\u5165\u5931\u8d25: " + (message == null ? e.toString() : message));
                }
            }
        }, "slg-menu-inject");
        worker.start();
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

    /**
     * Resolves a selected APK to a local file that remains available after the
     * DocumentsUI provider closes its transient grant. Direct paths and
     * file:// URIs remain direct files; content:// sources are copied once to
     * the app's persistent files directory.
     */
    private static File resolveApk(Context context, String value) throws IOException {
        if (value == null || value.trim().isEmpty()) {
            return null;
        }
        String normalized = value.trim();
        if (!normalized.startsWith("content://")) {
            return fileFrom(normalized);
        }
        if (context == null || context.getContentResolver() == null) {
            throw new IOException("无法读取 content URI");
        }
        File baseDir = context.getExternalFilesDir(null);
        if (baseDir == null) {
            baseDir = context.getFilesDir();
        }
        if (baseDir == null) {
            throw new IOException("应用存储目录不可用");
        }
        // Prefer app-private external storage for very large APKs. It survives
        // the transient DocumentsUI grant while avoiding the tighter internal
        // data quota. Fall back to internal storage when unavailable.
        File resolvedDir = new File(baseDir, "installed-apks");
        if (!resolvedDir.exists() && !resolvedDir.mkdirs()) {
            throw new IOException("无法创建应用 APK 存储目录");
        }
        if (!resolvedDir.isDirectory() || !resolvedDir.canWrite()) {
            throw new IOException("应用 APK 存储目录不可写");
        }

        File target = new File(resolvedDir, "content-" + digest(normalized) + ".apk");
        if (target.isFile()) {
            return target;
        }
        if (target.exists()) {
            throw new IOException("已解析的 APK 不是普通文件");
        }

        File temporary = new File(resolvedDir,
                target.getName() + "." + UUID.randomUUID().toString() + ".partial");
        if (temporary.exists() && !temporary.delete()) {
            throw new IOException("无法清理 APK 副本临时文件");
        }
        boolean committed = false;
        try {
            try (InputStream in = context.getContentResolver().openInputStream(Uri.parse(normalized))) {
                if (in == null) {
                    throw new IOException("无法打开 content URI");
                }
                try (FileOutputStream out = new FileOutputStream(temporary)) {
                    byte[] buffer = new byte[65536];
                    int read;
                    while ((read = in.read(buffer)) != -1) {
                        out.write(buffer, 0, read);
                    }
                    out.flush();
                    out.getFD().sync();
                }
            }
            if (!temporary.isFile()) {
                throw new IOException("APK 副本写入后不是普通文件");
            }
            if (target.exists()) {
                if (target.isFile()) {
                    return target;
                }
                throw new IOException("已解析的 APK 不是普通文件");
            }
            if (!temporary.renameTo(target)) {
                if (target.isFile()) {
                    return target;
                }
                throw new IOException("APK 副本原子提交失败");
            }
            committed = true;
            if (!target.isFile()) {
                throw new IOException("APK 副本提交后不是普通文件");
            }
            return target;
        } finally {
            if (!committed && temporary.exists()) {
                temporary.delete();
            }
        }
    }

    private static String digest(String value) throws IOException {
        try {
            byte[] bytes = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(bytes.length * 2);
            for (byte item : bytes) {
                hex.append(String.format("%02x", item & 0xff));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IOException("无法生成 APK 副本标识", e);
        }
    }

    /**
     * Rewrites the language menu inside an APK in place. Returns STATUS_CHANGED
     * when a new 翻译文本 entry was added, STATUS_ALREADY when the entry already
     * exists (idempotent success), or STATUS_NOOP when no compatible menu exists.
     */
    static int rewriteApkMenu(File apk, String gameTargetLang, String translatorLang) throws IOException {
        synchronized (MENU_REWRITE_LOCK) {
            if (gameTargetLang == null) {
                gameTargetLang = "";
            }
            String replacementName = null;
            byte[] replacementData = null;
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
                    boolean already = menuHasLanguage(original, translatorLang);
                    byte[] rewritten = injectMenu(original, gameTargetLang, translatorLang);
                    if (rewritten != null) {
                        // Fail closed: only commit a rewrite that still carries
                        // the injected language entry and passes the RPC2
                        // stream validator. A rewrite that drops the entry or
                        // corrupts the stream would break the game's script
                        // loading (observed on Ren'Py 8.5.3 screens.rpyc).
                        if (!menuHasLanguage(rewritten, translatorLang)) {
                            continue;
                        }
                        // Stream-validate only protocol-5 (FRAME) rewrites;
                        // legacy protocol-2 streams have no FRAME structure for
                        // the validator to check.
                        java.util.List<int[]> rewrittenOps = walk(rewritten);
                        if (rewrittenOps != null) {
                            boolean hasFrame = false;
                            for (int[] op : rewrittenOps) {
                                if (op[0] == 0x95) {
                                    hasFrame = true;
                                    break;
                                }
                            }
                            if (hasFrame) {
                                try {
                                    RpycStreamValidator.requireValid(rewritten, "menu-inject");
                                } catch (Exception validationError) {
                                    continue;
                                }
                            }
                        }
                        replacementName = name;
                        replacementData = rewritten;
                        break;
                    }
                    if (already) {
                        return STATUS_ALREADY;
                    }
                }
            }
            // Windows keeps the archive locked while ZipFile is open. Commit
            // only after the try-with-resources scope has closed it.
            if (replacementName != null && replacementData != null) {
                replaceZipEntry(apk, replacementName, replacementData);
                return STATUS_CHANGED;
            }
            return STATUS_NOOP;
        }
    }

    /** Returns true when a rpyc already contains the translator language entry. */
    static boolean menuHasLanguage(byte[] rpyc, String translatorLang) {
        if (rpyc.length < RPC2_MAGIC.length || !startsWith(rpyc, RPC2_MAGIC)) {
            return apkHasLanguage(rpyc, translatorLang);
        }
        byte[] needle = ("Language(\"" + translatorLang + "\")").getBytes(StandardCharsets.UTF_8);
        int tablePos = RPC2_MAGIC.length;
        while (tablePos + 12 <= rpyc.length) {
            int id = le32(rpyc, tablePos);
            int offset = le32(rpyc, tablePos + 4);
            int length = le32(rpyc, tablePos + 8);
            if (id == 0) {
                break;
            }
            if (offset < 0 || length < 0 || offset + length > rpyc.length) {
                return false;
            }
            byte[] inflated = inflate(slice(rpyc, offset, offset + length));
            if (inflated != null && containsAscii(inflated, new String(needle, StandardCharsets.UTF_8))) {
                return true;
            }
            tablePos += 12;
        }
        return false;
    }

    /** Also accepts an APK container so callers can validate the resolved copy. */
    private static boolean apkHasLanguage(byte[] apk, String translatorLang) {
        if (apk.length < 4 || apk[0] != 'P' || apk[1] != 'K') {
            return false;
        }
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(apk))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                String name = entry.getName();
                if (name == null || !name.startsWith("assets/")
                        || !(name.endsWith(".rpyc") || name.endsWith(".rpymc"))) {
                    continue;
                }
                ByteArrayOutputStream data = new ByteArrayOutputStream();
                byte[] buffer = new byte[8192];
                int read;
                while ((read = zip.read(buffer)) != -1) {
                    data.write(buffer, 0, read);
                }
                if (menuHasLanguage(data.toByteArray(), translatorLang)) {
                    return true;
                }
            }
        } catch (IOException ignored) {
            return false;
        }
        return false;
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
            byte[] next = appendMenuButton(inflated, gameTargetLang, translatorLang);
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

    private static void writeShortUnicode(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        out.write(0x8c);
        out.write(bytes.length);
        out.write(bytes, 0, bytes.length);
    }

    /**
     * Rewrites the last non-default, non-target language button into an
     * independent 翻译文本 entry that selects the translator language. The
     * rewrite preserves the compiled screen structure. The label style is
     * taken from a button that already displays non-ASCII text when one
     * exists (many games reserve a dedicated CJK-capable style, and the
     * default button style cannot render Chinese glyphs).
     */
    private static byte[] rewriteButton(byte[] data, String gameTargetLang, String translatorLang) {
        List<int[]> ops = walk(data);
        if (ops == null) {
            return null;
        }
        List<String> langs = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        List<List<String>> labelPayloads = new ArrayList<>();
        for (int k = 0; k < ops.size(); k++) {
            String payload = stringPayload(data, ops, k);
            if (payload == null) {
                continue;
            }
            String lang = languageCode(payload);
            if (lang == null) {
                continue;
            }
            String label = null;
            List<String> payloads = new ArrayList<>();
            int from = Math.max(0, k - 240);
            int to = Math.min(ops.size() - 1, k + 240);
            // Compiled Ren'Py screens store the button label after the
            // Language(...) action in some games, and before it in others.
            for (int direction = 0; direction < 2 && label == null; direction++) {
                if (direction == 0) {
                    for (int j = k + 1; j <= to; j++) {
                        String p = stringPayload(data, ops, j);
                        String lab = textLabel(p);
                        if (lab != null) {
                            label = lab;
                            break;
                        }
                    }
                } else {
                    for (int j = k - 1; j >= from; j--) {
                        String p = stringPayload(data, ops, j);
                        String lab = textLabel(p);
                        if (lab != null) {
                            label = lab;
                            break;
                        }
                    }
                }
            }
            if (label != null) {
                for (int j = from; j <= to; j++) {
                    if (j == k) {
                        continue;
                    }
                    String p2 = stringPayload(data, ops, j);
                    if (p2 != null && label.equals(textLabel(p2)) && !payloads.contains(p2)) {
                        payloads.add(p2);
                    }
                }
            }
            langs.add(lang);
            labels.add(label);
            labelPayloads.add(payloads);
        }
        int candidateIdx = -1;
        int defaultIdx = -1;
        for (int i = 0; i < langs.size(); i++) {
            if (langs.get(i).equals(translatorLang)) {
                candidateIdx = i; // repair the existing 翻译文本 button
                break;
            }
            String lang = langs.get(i);
            if (lang.equals("None")) {
                defaultIdx = i;
            } else if (!lang.isEmpty() && !lang.equals(gameTargetLang)) {
                candidateIdx = i;
            }
        }
        if (candidateIdx < 0) {
            candidateIdx = defaultIdx;
        }
        boolean repairMode = candidateIdx >= 0 && langs.get(candidateIdx).equals(translatorLang);
        if (candidateIdx < 0 || labels.get(candidateIdx) == null) {
            return null;
        }
        String[] styles = chooseStyles(labels, labelPayloads, candidateIdx);
        String candidateLang = langs.get(candidateIdx);
        String candidateLabel = labels.get(candidateIdx);
        List<String> candidatePayloads = labelPayloads.get(candidateIdx);
        // Rebuild the slot: drop stale FRAME lengths, rewrite label and language.
        ByteArrayOutputStream out = new ByteArrayOutputStream(data.length + 128);
        boolean changed = false;
        for (int k = 0; k < ops.size(); k++) {
            int[] op = ops.get(k);
            if (op[0] == 0x95) { // FRAME lengths become stale after rewriting; frames are optional
                continue;
            }
            byte[] chunk = slice(data, op[1], op[2]);
            String payload = stringPayload(data, ops, k);
            if (payload != null) {
                if (candidatePayloads.contains(payload)) {
                    String next = rewriteTextPayload(payload, TRANSLATOR_LABEL, styles);
                    if (next != null && !next.equals(payload)) {
                        changed = true;
                        writeShortUnicode(out, next);
                        continue;
                    }
                }
                if (languagePayloadMatches(payload, candidateLang)) {
                    if (!repairMode) {
                        changed = true;
                        writeShortUnicode(out, languagePayload(translatorLang));
                        continue;
                    }
                }
            }
            out.write(chunk, 0, chunk.length);
        }
        return changed ? out.toByteArray() : null;
    }


    /**
     * Clones the last expendable language button and appends the copy as an
     * independent translation-text entry. Original buttons stay untouched.
     */
    private static byte[] appendMenuButton(byte[] data, String gameTargetLang, String translatorLang) {
        List<int[]> ops = walk(data);
        if (ops == null) {
            return null;
        }
        List<String> langs = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        List<List<String>> labelPayloads = new ArrayList<>();
        List<Integer> langOps = new ArrayList<>();
        for (int k = 0; k < ops.size(); k++) {
            String payload = stringPayload(data, ops, k);
            if (payload == null) {
                continue;
            }
            String lang = languageCode(payload);
            if (lang == null) {
                continue;
            }
            String label = null;
            List<String> payloads = new ArrayList<>();
            int from = Math.max(0, k - 240);
            int to = Math.min(ops.size() - 1, k + 240);
            for (int direction = 0; direction < 2 && label == null; direction++) {
                if (direction == 0) {
                    for (int j = k + 1; j <= to; j++) {
                        String p = stringPayload(data, ops, j);
                        String lab = textLabel(p);
                        if (lab != null) {
                            label = lab;
                            break;
                        }
                    }
                } else {
                    for (int j = k - 1; j >= from; j--) {
                        String p = stringPayload(data, ops, j);
                        String lab = textLabel(p);
                        if (lab != null) {
                            label = lab;
                            break;
                        }
                    }
                }
            }
            if (label != null) {
                for (int j = from; j <= to; j++) {
                    if (j == k) {
                        continue;
                    }
                    String p2 = stringPayload(data, ops, j);
                    if (p2 != null && label.equals(textLabel(p2)) && !payloads.contains(p2)) {
                        payloads.add(p2);
                    }
                }
            }
            langs.add(lang);
            labels.add(label);
            labelPayloads.add(payloads);
            langOps.add(k);
        }
        int candidateIdx = -1;
        int defaultIdx = -1;
        for (int i = 0; i < langs.size(); i++) {
            if (langs.get(i).equals(translatorLang)) {
                return null; // already injected
            }
            String lang = langs.get(i);
            if (lang.equals("None")) {
                defaultIdx = i;
            } else if (!lang.isEmpty() && !lang.equals(gameTargetLang)) {
                candidateIdx = i;
            }
        }
        if (candidateIdx < 0) {
            candidateIdx = defaultIdx;
        }
        if (candidateIdx < 0 || labels.get(candidateIdx) == null) {
            return null;
        }
        int langOp = langOps.get(candidateIdx);
        int start = findButtonStart(ops, langOp);
        int end = findButtonEnd(ops, langOp);
        if (start < 0 || end < 0) {
            return null;
        }
        String[] styles = chooseStyles(labels, labelPayloads, candidateIdx);
        String candidateLang = langs.get(candidateIdx);
        List<String> candidatePayloads = labelPayloads.get(candidateIdx);
        byte[] clone = buildCloneButton(data, ops, start, end, candidateLang,
                candidatePayloads, styles, translatorLang);
        if (clone == null) {
            return null;
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream(data.length + clone.length + 64);
        out.write(data, 0, ops.get(end)[1]);
        out.write(clone, 0, clone.length);
        out.write(data, ops.get(end)[1], data.length - ops.get(end)[1]);
        return out.toByteArray();
    }

    /** Finds the opcode index of the SLDisplayable creation for a language button. */
    private static int findButtonStart(List<int[]> ops, int langOp) {
        int newObj = -1;
        for (int i = langOp - 1; i >= 0; i--) {
            if (ops.get(i)[0] == 0x81) {
                newObj = i;
                break;
            }
        }
        if (newObj < 2 || ops.get(newObj - 1)[0] != 0x29) {
            return -1;
        }
        int cls = ops.get(newObj - 2)[0];
        if (cls != 0x68 && cls != 0x6a && cls != 0x63) {
            return -1;
        }
        return newObj - 2;
    }

    /** Finds the APPENDS opcode that closes the language button list. */
    private static int findButtonEnd(List<int[]> ops, int langOp) {
        for (int i = langOp + 1; i + 1 < ops.size(); i++) {
            if (ops.get(i)[0] != 0x62) {
                continue;
            }
            if (ops.get(i + 1)[0] == 0x65 || isButtonStart(ops, i + 1)) {
                return i + 1;
            }
        }
        return -1;
    }

    private static boolean isButtonStart(List<int[]> ops, int index) {
        return index + 2 < ops.size()
                && (ops.get(index)[0] == 0x68
                || ops.get(index)[0] == 0x6a
                || ops.get(index)[0] == 0x63)
                && ops.get(index + 1)[0] == 0x29
                && ops.get(index + 2)[0] == 0x81;
    }

    /** Builds a memo-renumbered byte copy of the button opcode range. */
    private static byte[] buildCloneButton(byte[] data, List<int[]> ops, int startOp, int endOp,
                                           String candidateLang, List<String> candidatePayloads,
                                           String[] styles, String translatorLang) {
        Map<Integer, Integer> memo = new HashMap<>();
        int nextMemo = nextAvailableMemoIndex(data, ops);
        if (nextMemo < 0) {
            return null;
        }
        for (int i = startOp; i < endOp; i++) {
            int code = ops.get(i)[0];
            if (code == 0x71 || code == 0x72) {
                memo.put(memoId(data, ops.get(i)), nextMemo++);
            }
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream(512);
        for (int i = startOp; i < endOp; i++) {
            int[] op = ops.get(i);
            int code = op[0];
            if (code == 0x95) {
                continue;
            }
            byte[] chunk = slice(data, op[1], op[2]);
            if (code == 0x71 || code == 0x72) {
                Integer mapped = memo.get(memoId(data, op));
                if (mapped != null) {
                    writeLongBinInput(out, mapped);
                } else {
                    out.write(chunk, 0, chunk.length);
                }
                continue;
            }
            if (code == 0x68 || code == 0x6a) {
                Integer mapped = memo.get(memoId(data, op));
                if (mapped != null) {
                    writeLongBinGet(out, mapped);
                } else {
                    out.write(chunk, 0, chunk.length);
                }
                continue;
            }
            String payload = stringPayload(data, ops, i);
            if (payload != null) {
                if (languagePayloadMatches(payload, candidateLang)) {
                    writeUnicode(out, languagePayload(translatorLang));
                    continue;
                }
                if (candidatePayloads != null && candidatePayloads.contains(payload)) {
                    String next = rewriteTextPayload(payload, TRANSLATOR_LABEL, styles);
                    if (next != null && !next.equals(payload)) {
                        writeUnicode(out, next);
                        continue;
                    }
                }
            }
            out.write(chunk, 0, chunk.length);
        }
        return out.toByteArray();
    }

    /** Returns the first memo index that cannot collide with the source stream. */
    private static int nextAvailableMemoIndex(byte[] data, List<int[]> ops) {
        int max = -1;
        for (int[] op : ops) {
            if (op[0] != 0x71 && op[0] != 0x72) {
                continue;
            }
            int index = memoId(data, op);
            if (index > max) {
                max = index;
            }
        }
        return max == Integer.MAX_VALUE ? -1 : max + 1;
    }

    private static int memoId(byte[] data, int[] op) {
        if (op[0] == 0x71 || op[0] == 0x68) {
            return data[op[1] + 1] & 0xFF;
        }
        if (op[0] == 0x72 || op[0] == 0x6a) {
            return le32(data, op[1] + 1);
        }
        return -1;
    }

    private static void writeLongBinInput(ByteArrayOutputStream out, int id) {
        out.write(0x72);
        writeIntLe(out, id);
    }

    private static void writeLongBinGet(ByteArrayOutputStream out, int id) {
        out.write(0x6a);
        writeIntLe(out, id);
    }

    private static void writeUnicode(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= 255) {
            writeShortUnicode(out, value);
        } else {
            out.write(0x58);
            writeIntLe(out, bytes.length);
            out.write(bytes, 0, bytes.length);
        }
    }

    /**
     * Extracts the label text from Text(...) payloads like
     * Text(("English"), style="..."), Text("中文", style="...") or
     * Text(_("Info"), style="..."). Returns null when the payload is not a
     * Text label payload.
     */
    private static String textLabel(String payload) {
        if (payload == null) {
            return null;
        }
        if (payload.startsWith("(\"") && payload.endsWith("\")")) {
            String label = payload.substring(2, payload.length() - 2);
            return label.isEmpty() ? null : label;
        }
        if (payload.startsWith("_(\"") && payload.endsWith("\")")) {
            String label = payload.substring(3, payload.length() - 2);
            return label.isEmpty() ? null : label;
        }
        if (!payload.startsWith("Text(")) {
            return null;
        }
        int open = -1;
        int start = 0;
        if (payload.startsWith("Text((\"")) {
            start = "Text((\"".length();
        } else if (payload.startsWith("Text(\"")) {
            start = "Text(\"".length();
        } else if (payload.startsWith("Text(_(\"")) {
            start = "Text(_(\"".length();
        } else {
            return null;
        }
        int end = payload.indexOf("\", style=", start);
        if (end < 0) {
            end = payload.indexOf("\"), style=", start);
        }
        if (end < 0) {
            return null;
        }
        String label = payload.substring(start, end);
        return label.isEmpty() ? null : label;
    }

    /** Returns {normalStyle, hoverStyle} or null. */
    private static String[] stylesOf(List<String> payloads) {
        if (payloads == null || payloads.isEmpty()) {
            return null;
        }
        String normal = null;
        String hover = null;
        for (String payload : payloads) {
            String style = styleName(payload);
            if (style == null) {
                continue;
            }
            if (style.endsWith("_hover")) {
                hover = style;
            } else {
                normal = style;
            }
        }
        if (normal == null && hover == null) {
            return null;
        }
        if (normal == null) {
            normal = hover.substring(0, hover.length() - "_hover".length());
        }
        if (hover == null) {
            hover = normal + "_hover";
        }
        return new String[]{normal, hover};
    }

    private static String styleName(String payload) {
        if (payload == null) {
            return null;
        }
        int idx = payload.indexOf("style=\"");
        if (idx < 0) {
            return null;
        }
        int start = idx + "style=\"".length();
        int end = payload.indexOf('"', start);
        if (end < 0) {
            return null;
        }
        return payload.substring(start, end);
    }

    /**
     * Picks the label style for the injected button: prefer a language
     * button whose label already contains non-ASCII characters (its style is
     * likely CJK-capable), otherwise fall back to the candidate's own style.
     */
    private static String[] chooseStyles(List<String> labels, List<List<String>> labelPayloads,
                                        int candidateIdx) {
        String[] fallback = stylesOf(labelPayloads.get(candidateIdx));
        for (int i = 0; i < labels.size(); i++) {
            String label = labels.get(i);
            if (label == null) {
                continue;
            }
            boolean nonAscii = false;
            for (int c = 0; c < label.length(); c++) {
                if (label.charAt(c) > 127) {
                    nonAscii = true;
                    break;
                }
            }
            if (nonAscii) {
                String[] styles = stylesOf(labelPayloads.get(i));
                if (styles != null) {
                    return styles;
                }
            }
        }
        return fallback;
    }

    /**
     * Rewrites a Text payload: replaces the label text with the translator
     * label and swaps in the chosen style name (keeping the payload's own
     * structural form).
     */
    private static String rewriteTextPayload(String payload, String newLabel, String[] styles) {
        if (payload != null && payload.startsWith("(\"") && payload.endsWith("\")")) {
            return "(\"" + newLabel + "\")";
        }
        if (payload != null && payload.startsWith("_(\"") && payload.endsWith("\")")) {
            return "_(\"" + newLabel + "\")";
        }
        if (styles == null) {
            return null;
        }
        int prefix = -1;
        String separator;
        if (payload.startsWith("Text((\"")) {
            prefix = "Text((\"".length();
            separator = "\"), style=";
        } else if (payload.startsWith("Text(\"")) {
            prefix = "Text(\"".length();
            separator = "\", style=";
        } else if (payload.startsWith("Text(_(\"")) {
            prefix = "Text(_(\"".length();
            separator = "\"), style=";
        } else {
            return null;
        }
        int open = payload.indexOf(separator, prefix);
        if (open < 0) {
            return null;
        }
        String style = styleName(payload);
        String chosen = style != null && style.endsWith("_hover") ? styles[1] : styles[0];
        String head = payload.substring(0, prefix);
        String tail = payload.substring(open);
        int styleIdx = tail.indexOf("style=\"");
        if (styleIdx < 0) {
            return null;
        }
        int styleStart = styleIdx + "style=\"".length();
        int styleEnd = tail.indexOf('"', styleStart);
        if (styleEnd < 0) {
            return null;
        }
        return head + newLabel + tail.substring(0, styleStart) + chosen + tail.substring(styleEnd);
    }


    static String stringPayload(byte[] data, List<int[]> ops, int index) {
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
        if (code == 0x8d) { // BINUNICODE8
            long length = le64(data, op[1] + 1);
            if (length < 0 || length > Integer.MAX_VALUE) {
                return null;
            }
            int len = (int) length;
            return new String(data, op[1] + 9, len, StandardCharsets.UTF_8);
        }
        return null;
    }

    private static String languageCode(String payload) {
        if ("Language(None)".equals(payload)) {
            return "None";
        }
        if (!payload.startsWith("Language(\"") || !payload.endsWith("\")")) {
            return null;
        }
        return payload.substring("Language(\"".length(), payload.length() - 2);
    }

    private static boolean languagePayloadMatches(String payload, String language) {
        return payload != null && language != null
                && languagePayload(language).equals(payload);
    }

    private static String languagePayload(String language) {
        return "None".equals(language)
                ? "Language(None)"
                : "Language(\"" + language + "\")";
    }

    /**
     * Walks a pickle stream, returning [opcode, start, end] triples. Returns
     * null when the stream contains an opcode we do not recognize.
     */
    static List<int[]> walk(byte[] data) {
        List<int[]> ops = new ArrayList<>();
        int pos = 0;
        int n = data.length;
        while (pos < n) {
            int b = data[pos] & 0xFF;
            int start = pos++;
            switch (b) {
                // Fixed-size arguments. Validate the length field before
                // advancing: negative or oversized lengths previously moved
                // pos backwards (a crafted low-bits -4 kept the walker on the
                // same byte forever) or read beyond the stream.
                case 0x4a: // BININT
                case 0x58: // BINUNICODE
                case 0x54: // BINSTRING
                case 0x42: // BINBYTES
                case 0x8b: // LONG4
                    if (pos + 4 > n) {
                        return null;
                    }
                    {
                        int len = lengthAfter(data, pos, b);
                        if (len < 0 || len > n - pos - 4) {
                            return null;
                        }
                        pos += 4 + len;
                    }
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
                    if (pos + 8 > n) {
                        return null;
                    }
                    {
                        long len8 = le64(data, pos);
                        if (len8 < 0 || len8 > Integer.MAX_VALUE
                                || len8 > n - pos - 8) {
                            return null;
                        }
                        pos += 8 + (int) len8;
                    }
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
        File absoluteApk = apk.getAbsoluteFile();
        File parent = absoluteApk.getParentFile();
        if (parent == null || !parent.isDirectory()) {
            throw new IOException("\u6e90 APK \u5b58\u50a8\u76ee\u5f55\u4e0d\u53ef\u7528");
        }
        File temporary = File.createTempFile(absoluteApk.getName() + ".menu-", ".tmp", parent);
        File backup = null;
        boolean installed = false;
        try {
            byte[] buffer = new byte[65536];
            try (FileOutputStream fileOut = new FileOutputStream(temporary);
                 ZipFile zip = new ZipFile(absoluteApk);
                 ZipOutputStream out = new ZipOutputStream(fileOut)) {
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
                out.finish();
                out.flush();
                fileOut.getFD().sync();
            }
            validateZip(temporary, entryName);

            // File.renameTo cannot replace an existing file reliably on all
            // Android filesystems. Move the original aside first, then restore
            // it on any failed install or validation. The original is never
            // deleted before a verified replacement is available.
            backup = File.createTempFile(absoluteApk.getName() + ".menu-", ".bak", parent);
            if (!backup.delete() || !absoluteApk.renameTo(backup)) {
                throw new IOException("\u65e0\u6cd5\u4fdd\u7559\u539f APK\uff0c\u8bf7\u91ca\u653e\u5b58\u50a8\u7a7a\u95f4");
            }
            if (!temporary.renameTo(absoluteApk)) {
                restoreBackup(backup, absoluteApk);
                throw new IOException("\u6ce8\u5165\u540e\u91cd\u547d\u540d\u5931\u8d25");
            }
            installed = true;
            try {
                validateZip(absoluteApk, entryName);
            } catch (IOException validationFailure) {
                if (absoluteApk.exists() && !absoluteApk.delete()) {
                    validationFailure.addSuppressed(new IOException("\u65e0\u6cd5\u79fb\u9664\u5931\u6548 APK"));
                }
                restoreBackup(backup, absoluteApk);
                installed = false;
                throw validationFailure;
            }
            // A valid new APK is now in place. If cleanup itself is not
            // possible, retain the backup rather than risking data loss.
            if (backup.exists()) {
                backup.delete();
            }
        } finally {
            if (temporary.exists()) {
                temporary.delete();
            }
            if (!installed && backup != null && backup.exists() && !absoluteApk.exists()) {
                restoreBackup(backup, absoluteApk);
            }
        }
    }

    private static void restoreBackup(File backup, File apk) throws IOException {
        if (backup == null || !backup.isFile()) {
            throw new IOException("\u65e0\u6cd5\u6062\u590d\u539f APK");
        }
        if (apk.exists() && !apk.delete()) {
            throw new IOException("\u65e0\u6cd5\u6e05\u7406\u5931\u8d25\u7684 APK");
        }
        if (!backup.renameTo(apk)) {
            throw new IOException("\u65e0\u6cd5\u6062\u590d\u539f APK");
        }
    }

    private static void validateZip(File archive, String expectedEntryName) throws IOException {
        try (ZipFile zip = new ZipFile(archive)) {
            ZipEntry entry = zip.getEntry(expectedEntryName);
            if (entry == null) {
                throw new IOException("\u91cd\u5199\u540e ZIP \u7f3a\u5c11\u76ee\u6807\u6761\u76ee");
            }
            try (InputStream in = zip.getInputStream(entry)) {
                byte[] buffer = new byte[8192];
                while (in.read(buffer) != -1) {
                    // Drain the rewritten entry so its CRC and compressed data
                    // are checked before it becomes the active APK.
                }
            }
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
