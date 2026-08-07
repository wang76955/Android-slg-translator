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
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
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
            String activationMode = normalizeActivationMode(call.getString("activationMode"));
            TemplateMeta meta = readTemplateMeta(apk);
            if (meta.compatibility != null
                    && !meta.compatibility.canGenerate()) {
                call.resolve(compileResult(activationMode, 0, compiledPathFor(activationMode),
                        translatorLanguageFor(activationMode), meta));
                return;
            }
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
                    String oldText = pair[0];
                    String newText = pair[1] == null ? "" : pair[1];
                    String validation = validationMessage(oldText, newText, rpy.getPath());
                    if (validation != null) {
                        call.reject("translation_validation_failed: " + validation);
                        return;
                    }
                    if (merged.containsKey(oldText)
                            && !merged.get(oldText).equals(newText)) {
                        call.reject("translation_collision_conflict: conflicting translations for exactOld '"
                                + oldText + "'");
                        return;
                    }
                    merged.put(oldText, newText);
                }
            }
            if (language == null || language.isEmpty() || merged.isEmpty()) {
                call.resolve(compileResult(activationMode, 0, compiledPathFor(activationMode),
                        translatorLanguageFor(activationMode), meta));
                return;
            }
            List<String[]> pairs = new ArrayList<>();
            for (java.util.Map.Entry<String, String> entry : merged.entrySet()) {
                pairs.add(new String[]{entry.getKey(), entry.getValue()});
            }
            Set<Integer> requiredCodePoints = new LinkedHashSet<>(
                    RenpyFontSupport.defaultRequiredCodePoints());
            // The fixed baseline is a hard gate before any translation artifact is written.
            RenpyFontSupport.FontReport baselineReport = RenpyFontSupport.inspect(
                    context, apk, requiredCodePoints);
            if (!baselineReport.isComplete()) {
                call.reject("renpy_font_missing_glyphs: baseline missingCodePoints="
                        + baselineReport.missingCodePoints + ", bestFont="
                        + String.valueOf(baselineReport.bestFontPath));
                return;
            }
            requiredCodePoints.addAll(RenpyFontSupport.codePointsOfTranslations(merged.values()));
            RenpyFontSupport.FontReport fontReport = RenpyFontSupport.inspect(
                    context, apk, requiredCodePoints);
            if (!fontReport.isComplete()) {
                call.reject("renpy_font_missing_glyphs: missingCodePoints="
                        + fontReport.missingCodePoints + ", bestFont="
                        + String.valueOf(fontReport.bestFontPath));
                return;
            }
            TranslationArtifact artifact = compileTranslationArtifact(activationMode, pairs, meta);
            List<String[]> pending = new ArrayList<>();
            List<byte[]> pendingBytes = new ArrayList<>();
            pending.add(new String[]{artifact.compiledPath, artifact.runtimeFilename});
            pendingBytes.add(artifact.rpyc);
            if ("selectable".equals(artifact.activationMode)) {
                byte[] styleRpyc = cloneChineseStyleRpyc(apk, fontReport.bestFontPath);
                if (styleRpyc == null) {
                    call.reject("renpy_font_style_rewrite_unsafe: no verified chinese/schinese style "
                            + "could be safely cloned with the APK-local best font");
                    return;
                }
                pending.add(new String[]{"assets/x-game/x-tl/x-slgtranslated/x-style.rpyc",
                        "game/tl/slgtranslated/style.rpy"});
                pendingBytes.add(styleRpyc);
            }
            rewriteApkWithEntries(apk, pending, pendingBytes);
            call.resolve(compileResult(artifact.activationMode, merged.size(),
                    artifact.compiledPath, artifact.translatorLanguage, meta, fontReport));
        } catch (Exception e) {
            if (e instanceof CompilationValidationException) {
                CompilationValidationException validation = (CompilationValidationException) e;
                call.reject(validation.code + ": " + validation.getMessage());
                return;
            }
            String message = e.getMessage();
            call.reject("\u7f16\u8bd1\u7ffb\u8bd1\u8d44\u6e90\u5931\u8d25: " + (message == null ? e.toString() : message));
        }
    }

    private static JSObject compileResult(String activationMode, int compiled,
                                          String compiledPath, String translatorLanguage,
                                          TemplateMeta meta) {
        return compileResult(activationMode, compiled, compiledPath, translatorLanguage, meta, null);
    }

    private static JSObject compileResult(String activationMode, int compiled,
                                          String compiledPath, String translatorLanguage,
                                          TemplateMeta meta,
                                          RenpyFontSupport.FontReport fontReport) {
        JSObject result = new JSObject();
        result.put("compiled", compiled);
        result.put("activationMode", activationMode);
        result.put("translatorLanguage", translatorLanguage);
        result.put("compiledPath", compiledPath);
        if (meta != null) {
            result.put("templatePath", meta.sourcePath);
            result.put("templateVersion", meta.version);
            result.put("templateSource", meta.selectionReason);
            if (meta.compatibility != null
                    && !meta.compatibility.canGenerate()) {
                result.put("supportLevel", "extract_only");
                result.put("reasonCode", "legacy_pickle_writer_required");
                result.put("compatibilityReason", meta.compatibility.reason);
                result.put("message", "\u53ef\u4ee5\u63d0\u53d6\u548c\u7ffb\u8bd1\uff0c\u4f46\u5f53\u524d\u7248\u672c\u4e0d\u80fd\u4e3a\u8be5 Ren'Py/Python \u7248\u672c\u5b89\u5168\u751f\u6210\u7ffb\u8bd1\u811a\u672c\u3002");
            } else {
                result.put("supportLevel", "compile");
                result.put("reasonCode", "");
                result.put("compatibilityReason", meta.compatibility == null
                        ? "no_compatibility_report" : meta.compatibility.reason);
                result.put("message", "");
            }
        }
        if (fontReport != null) {
            JSObject report = new JSObject();
            JSArray candidates = new JSArray();
            for (String candidate : fontReport.candidateFonts) {
                candidates.put(candidate);
            }
            JSArray missing = new JSArray();
            for (Integer codePoint : fontReport.missingCodePoints) {
                missing.put(codePoint);
            }
            JSArray warnings = new JSArray();
            for (String warning : fontReport.warnings) {
                warnings.put(warning);
            }
            report.put("candidateFonts", candidates);
            report.put("bestFontPath", fontReport.bestFontPath);
            report.put("requiredCount", fontReport.requiredCount);
            report.put("coveredCount", fontReport.coveredCount);
            report.put("missingCodePoints", missing);
            report.put("hasChineseStyleBucket", fontReport.hasChineseStyleBucket);
            report.put("hasEastAsianLineBreakEvidence", fontReport.hasEastAsianLineBreakEvidence);
            report.put("warnings", warnings);
            result.put("fontReport", report);
            if (!fontReport.hasChineseStyleBucket || !fontReport.hasEastAsianLineBreakEvidence) {
                result.put("fontWarning", "未确认完整的中文 translate style 或东亚断行证据；请检查游戏排版。");
            } else if (!fontReport.warnings.isEmpty()) {
                result.put("fontWarning", "字体预检发现边界警告：" + fontReport.warnings);
            }
        }
        return result;
    }

    private static String normalizeActivationMode(String activationMode) {
        if (activationMode == null || activationMode.isEmpty() || "selectable".equals(activationMode)) {
            return "selectable";
        }
        if ("always_on".equals(activationMode)) {
            return "always_on";
        }
        throw new IllegalArgumentException("unsupported activationMode: " + activationMode);
    }

    private static String translatorLanguageFor(String activationMode) {
        return "always_on".equals(activationMode) ? null : "slgtranslated";
    }

    private static String compiledPathFor(String activationMode) {
        return "always_on".equals(activationMode)
                ? "assets/x-game/x-tl/x-None/x-slgtranslator-translations.rpyc"
                : "assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc";
    }

    static final class TranslationArtifact {
        final String activationMode;
        final String translatorLanguage;
        final String compiledPath;
        final String runtimeFilename;
        final byte[] rpyc;

        TranslationArtifact(String activationMode, String translatorLanguage,
                            String compiledPath, String runtimeFilename, byte[] rpyc) {
            this.activationMode = activationMode;
            this.translatorLanguage = translatorLanguage;
            this.compiledPath = compiledPath;
            this.runtimeFilename = runtimeFilename;
            this.rpyc = rpyc;
        }
    }

    private static final class CompilationValidationException extends IOException {
        final String code;

        CompilationValidationException(String code, String message) {
            super(message == null ? "generated RPYC validation failed" : message);
            this.code = code;
        }
    }

    static TranslationArtifact compileTranslationArtifact(String activationMode,
                                                            List<String[]> pairs,
                                                            TemplateMeta meta)
            throws CompilationValidationException {
        String collision = LocalTranslationSupport.translationCollisionConflict(pairs);
        if (collision != null) {
            throw new CompilationValidationException("translation_collision_conflict", collision);
        }
        String source = meta == null || meta.sourcePath == null
                ? "translation-artifact" : meta.sourcePath;
        for (String[] pair : pairs) {
            if (pair == null || pair.length < 2) {
                throw new CompilationValidationException("translation_validation_failed",
                        "old= new= source=" + source + " codes=[empty_translation]");
            }
            String validation = validationMessage(pair[0], pair[1], source);
            if (validation != null) {
                throw new CompilationValidationException("translation_validation_failed", validation);
            }
        }
        String normalized = normalizeActivationMode(activationMode);
        String translatorLanguage = translatorLanguageFor(normalized);
        String compiledPath = compiledPathFor(normalized);
        String runtimeFilename = "always_on".equals(normalized)
                ? "game/tl/None/slgtranslator-translations.rpy"
                : "game/tl/slgtranslated/translations.rpy";
        byte[] rpyc = compileRpyc(translatorLanguage, runtimeFilename, pairs, meta);
        RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                rpyc, meta.version, meta.key, translatorLanguage, pairs.size());
        if (!validation.valid) {
            throw new CompilationValidationException(validation.code, validation.message);
        }
        return new TranslationArtifact(normalized, translatorLanguage, compiledPath,
                runtimeFilename, rpyc);
    }

    private static String validationMessage(String oldText, String newText, String source) {
        RenpyTextValidator.ValidationResult result = RenpyTextValidator.validate(oldText, newText);
        if (result.valid) {
            return null;
        }
        return "old=" + String.valueOf(oldText)
                + " new=" + String.valueOf(newText)
                + " source=" + String.valueOf(source)
                + " codes=" + result.codes;
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
        RpycPickleWriter.Dialect dialect = dialectFor(meta);
        byte[] pickle = RpycPickleWriter.buildTranslationPickle(
                dialect, language, filename, pairs, meta.version, meta.key);
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

    private static RpycPickleWriter.Dialect dialectFor(TemplateMeta meta) {
        if (meta == null || meta.compatibility == null) {
            return RpycPickleWriter.Dialect.PY3_MODERN;
        }
        if (!meta.compatibility.canGenerate()) {
            throw new IllegalArgumentException("template generation support is not verified: "
                    + meta.compatibility.reason);
        }
        if (meta.compatibility.isProtocol2WriterVerified()) {
            return RpycPickleWriter.Dialect.PY2_PROTOCOL_2;
        }
        return RpycPickleWriter.Dialect.PY3_MODERN;
    }

    static byte[] buildPickle(String language, String filename, List<String[]> pairs, int version, String key) {
        return RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY3_MODERN,
                language, filename, pairs, version, key);
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
        if (data == null) {
            return null;
        }
        RenpyResourceLimits.checkCompressed(data.length);
        java.util.zip.Inflater inflater = new java.util.zip.Inflater();
        inflater.setInput(data);
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            long total = 0;
            while (!inflater.finished()) {
                RenpyResourceLimits.checkInterrupted();
                int read;
                try {
                    read = inflater.inflate(buffer);
                } catch (java.util.zip.DataFormatException e) {
                    return null;
                }
                if (read > 0) {
                    total += read;
                    RenpyResourceLimits.checkInflated(total);
                    RenpyResourceLimits.checkInflateRatio(data.length, total);
                    out.write(buffer, 0, read);
                } else if (inflater.needsDictionary() || inflater.needsInput()) {
                    return null;
                } else {
                    return null;
                }
            }
            if (inflater.getRemaining() != 0) {
                return null;
            }
            return out.toByteArray();
        } finally {
            inflater.end();
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

    static int templatePriority(String zipPath) {
        if (zipPath == null) {
            return Integer.MAX_VALUE;
        }
        String normalized = zipPath.replace('\\', '/').toLowerCase();
        if (!normalized.startsWith("assets/") || !normalized.endsWith(".rpyc")) {
            return Integer.MAX_VALUE;
        }
        if (normalized.startsWith("assets/x-renpy/x-common/")
                || normalized.startsWith("assets/renpy/common/")) {
            return 100;
        }
        if (normalized.startsWith("assets/x-game/")) {
            String relative = normalized.substring("assets/x-game/".length());
            return relative.startsWith("x-tl/") || relative.startsWith("tl/") ? 10 : 0;
        }
        if (normalized.startsWith("assets/game/")) {
            String relative = normalized.substring("assets/game/".length());
            return relative.startsWith("tl/") || relative.startsWith("x-tl/") ? 10 : 0;
        }
        return 20;
    }

    private static String templateSelectionReason(int priority) {
        switch (priority) {
            case 0:
                return "game-script";
            case 10:
                return "game-translation";
            case 20:
                return "game-resource";
            case 100:
                return "common";
            default:
                return "unknown";
        }
    }

    static final class TemplateMeta {
        int version;
        String key = "unlocked";
        byte[] trailer;
        String sourcePath;
        String selectionReason;
        RpycCompatibility.Report compatibility;
    }

    private static final class TemplateCandidate {
        final String path;
        final int priority;
        final int version;
        final String key;
        final byte[] trailer;
        final RpycCompatibility.Report compatibility;

        TemplateCandidate(String path, int priority, int version, String key, byte[] trailer,
                          RpycCompatibility.Report compatibility) {
            this.path = path;
            this.priority = priority;
            this.version = version;
            this.key = key;
            this.trailer = trailer;
            this.compatibility = compatibility;
        }
    }

    static TemplateMeta readTemplateMeta(File apk) throws IOException {
        List<TemplateCandidate> candidates = new ArrayList<>();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                int priority = templatePriority(name);
                if (priority == Integer.MAX_VALUE) {
                    continue;
                }
                if (entry.getSize() <= 0 || entry.getSize() > 16_000_000L) {
                    continue;
                }
                byte[] bytes = readEntry(zip, entry);
                RpycCompatibility.Report compatibility = RpycCompatibility.inspect(bytes);
                byte[] pickle = startsWith(bytes, RPC2_MAGIC)
                        ? readSlot(bytes, 2) : readSlot(bytes, 1);
                Object[] found = pickle == null ? new Object[]{0, null} : scanVersionKey(pickle);
                if ((Integer) found[0] != 0
                        || !compatibility.canGenerate()) {
                    candidates.add(new TemplateCandidate(
                            name,
                            priority,
                            (Integer) found[0],
                            found[1] == null ? "unlocked" : (String) found[1],
                            slice(bytes, Math.max(0, bytes.length - 16), bytes.length),
                            compatibility));
                }
            }
        }
        if (candidates.isEmpty()) {
            throw new IOException("\u672a\u627e\u5230\u53ef\u7528\u7684 Ren'Py \u7f16\u8bd1\u811a\u672c\u6a21\u677f");
        }
        java.util.Collections.sort(candidates, new java.util.Comparator<TemplateCandidate>() {
            @Override
            public int compare(TemplateCandidate left, TemplateCandidate right) {
                int priority = Integer.compare(left.priority, right.priority);
                if (priority != 0) {
                    return priority;
                }
                return left.path.replace('\\', '/').compareToIgnoreCase(
                        right.path.replace('\\', '/'));
            }
        });
        TemplateCandidate selected = candidates.get(0);
        List<String> conflictingPaths = new ArrayList<>();
        for (TemplateCandidate candidate : candidates) {
            if (candidate.priority != selected.priority) {
                break;
            }
            if (candidate.version != selected.version || !candidate.key.equals(selected.key)) {
                conflictingPaths.add(candidate.path + " (version=" + candidate.version
                        + ", key=" + candidate.key + ")");
            }
        }
        if (!conflictingPaths.isEmpty()) {
            conflictingPaths.add(0, selected.path + " (version=" + selected.version
                    + ", key=" + selected.key + ")");
            throw new IOException("Ren'Py \u6a21\u677f version/key \u4e0d\u4e00\u81f4: "
                    + joinPaths(conflictingPaths));
        }
        TemplateMeta meta = new TemplateMeta();
        meta.version = selected.version;
        meta.key = selected.key;
        meta.trailer = selected.trailer;
        meta.sourcePath = selected.path;
        meta.selectionReason = templateSelectionReason(selected.priority);
        meta.compatibility = selected.compatibility;
        return meta;
    }

    private static String joinPaths(List<String> paths) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < paths.size(); i++) {
            if (i > 0) {
                out.append(", ");
            }
            out.append(paths.get(i));
        }
        return out.toString();
    }

    /**
     * Walks the pickle stream and returns {version, keyIndexOffset...} values
     * found after the 'version' and 'key' dictionary keys.
     */

    private static byte[] readSlot(byte[] rpyc, int slotId) {
        if (slotId == 1 && !startsWith(rpyc, RPC2_MAGIC)) {
            return inflate(rpyc);
        }
        int pos = RPC2_MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            long id = le32Unsigned(rpyc, pos);
            long offset = le32Unsigned(rpyc, pos + 4);
            long length = le32Unsigned(rpyc, pos + 8);
            if (id == 0) {
                return null;
            }
            if (id == slotId) {
                RenpyResourceLimits.checkRange(offset, length, rpyc.length);
                RenpyResourceLimits.checkCompressed(length);
                return inflate(slice(rpyc, (int) offset, (int) (offset + length)));
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
     * The compiler does not own arbitrary loose .rpy files in a game's tl
     * tree. In particular, an existing game tl/None file must survive a
     * translation build.
     */
    private static boolean isStaleTranslationRpy(String name) {
        return false;
    }

    /**
     * True only for exact translation artifacts generated by this app. Never
     * use a broad /tl/ or /x-tl/ test here: game-owned language buckets,
     * including tl/None, are not ours to delete.
     */
    private static boolean isStaleGeneratedRpyc(String name, long time) {
        return isAppGeneratedTranslationEntry(name);
    }

    private static boolean isAppGeneratedTranslationEntry(String name) {
        if (name == null || !name.toLowerCase().endsWith(".rpyc")) {
            return false;
        }
        String normalized = name.replace('\\', '/').toLowerCase();
        // x-translations.rpyc is the selectable artifact emitted by older
        // builds; keep it in this exact-name allowlist so switching to
        // always_on cannot leave two app-owned translation copies behind.
        return normalized.endsWith("/x-slgtranslator-translations.rpyc")
                || normalized.endsWith("/x-translations.rpyc");
    }

    /**
     * Finds the game's built-in Chinese style file (the one that switches
     * fonts to a CJK-capable font) and clones it for the translator
     * language. Returns the rewritten rpyc bytes, or null when unavailable.
     */
    static byte[] cloneChineseStyleRpyc(File apk, String bestFontPath) throws IOException {
        String runtimeFontPath = renpyFontPath(bestFontPath);
        if (runtimeFontPath == null || runtimeFontPath.isEmpty()) {
            return null;
        }
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                if (!name.startsWith("assets/") || !name.endsWith(".rpyc")) {
                    continue;
                }
                String lower = name.toLowerCase();
                if (!isChineseStylePath(lower)) {
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
                byte[] withFont = rewriteChineseStyleFont(bytes, runtimeFontPath);
                if (withFont == null) {
                    continue;
                }
                String oldLanguage = lower.contains("schinese") ? "schinese" : "chinese";
                byte[] rewritten = rewriteRpycLanguage(withFont, oldLanguage, "slgtranslated");
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
        return containsAscii(pickle, "text_font") || containsAscii(pickle, "font");
    }

    private static boolean isChineseStylePath(String path) {
        return path.contains("/x-tl/x-chinese/") || path.contains("/tl/chinese/")
                || path.contains("/x-tl/x-schinese/") || path.contains("/tl/schinese/");
    }

    /** Converts a validated APK asset entry into the path Ren'Py resolves in the game root. */
    static String renpyFontPath(String apkPath) {
        if (apkPath == null || apkPath.isEmpty()) {
            return null;
        }
        String normalized = apkPath.replace('\\', '/');
        int assets = normalized.indexOf("assets/");
        if (assets >= 0) {
            normalized = normalized.substring(assets + "assets/".length());
        }
        int game = normalized.indexOf("x-game/");
        if (game >= 0) {
            normalized = normalized.substring(game + "x-game/".length());
        }
        if (normalized.startsWith("/")) {
            normalized = normalized.substring(1);
        }
        if (!normalized.endsWith(".ttf") && !normalized.endsWith(".otf")
                && !normalized.endsWith(".ttc")) {
            return null;
        }
        try {
            RenpyResourceLimits.checkPath(normalized);
        } catch (RuntimeException invalidPath) {
            return null;
        }
        return normalized;
    }

    /**
     * Rewrites only a pickle string value reached through a font-style key.
     * Unknown pickle opcodes or malformed streams fail closed; no binary
     * substring replacement is used.
     */
    static byte[] rewriteChineseStyleFont(byte[] rpyc, String bestFontPath) {
        if (!startsWith(rpyc, RPC2_MAGIC) || bestFontPath == null || bestFontPath.isEmpty()) {
            return null;
        }
        List<int[]> slots = parseRpc2Slots(rpyc);
        if (slots == null || slots.isEmpty()) {
            return null;
        }
        List<byte[]> rebuilt = new ArrayList<>();
        boolean changed = false;
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
            ByteArrayOutputStream out = new ByteArrayOutputStream(inflated.length + 64);
            boolean fontKeyPending = false;
            boolean slotChanged = false;
            for (int index = 0; index < ops.size(); index++) {
                int[] op = ops.get(index);
                String payload = LanguageMenuSupport.stringPayload(inflated, ops, index);
                if (payload != null) {
                    if ("text_font".equals(payload) || "font".equals(payload)
                            || "font_name".equals(payload)) {
                        fontKeyPending = true;
                    } else if (fontKeyPending && isFontReference(payload)) {
                        writePickleString(out, bestFontPath);
                        slotChanged = true;
                        fontKeyPending = false;
                        continue;
                    } else {
                        fontKeyPending = false;
                    }
                }
                // FRAME lengths become stale when the font path length changes.
                // Omitting optional FRAME opcodes leaves a valid protocol stream.
                if (op[0] == 0x95) {
                    continue;
                }
                out.write(inflated, op[1], op[2] - op[1]);
            }
            rebuilt.add(slotChanged ? deflate(out.toByteArray()) : compressed);
            changed |= slotChanged;
        }
        if (!changed) {
            return null;
        }
        int dataEnd = 0;
        for (int[] slot : slots) {
            dataEnd = Math.max(dataEnd, slot[1] + slot[2]);
        }
        byte[] trailer = dataEnd < rpyc.length ? slice(rpyc, dataEnd, rpyc.length) : new byte[0];
        return rebuildRpc2WithTrailer(slots, rebuilt, trailer);
    }

    private static boolean isFontReference(String value) {
        return value.endsWith(".ttf") || value.endsWith(".otf") || value.endsWith(".ttc");
    }

    private static List<int[]> parseRpc2Slots(byte[] rpyc) {
        List<int[]> slots = new ArrayList<>();
        int tablePos = RPC2_MAGIC.length;
        while (tablePos + 12 <= rpyc.length) {
            int id = le32(rpyc, tablePos);
            int offset = le32(rpyc, tablePos + 4);
            int length = le32(rpyc, tablePos + 8);
            if (id == 0) {
                return slots;
            }
            if (offset < 0 || length < 0 || offset > rpyc.length
                    || length > rpyc.length - offset) {
                return null;
            }
            slots.add(new int[]{id, offset, length});
            tablePos += 12;
        }
        return null;
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
        if (entry.getCompressedSize() >= 0) {
            RenpyResourceLimits.checkCompressed(entry.getCompressedSize());
        }
        if (entry.getSize() >= 0) {
            RenpyResourceLimits.checkInflated(entry.getSize());
        }
        int initialSize = entry.getSize() > 0
                ? (int) Math.min(entry.getSize(), 16_000_000L) : 0;
        try (InputStream in = zip.getInputStream(entry);
             ByteArrayOutputStream out = new ByteArrayOutputStream(initialSize)) {
            byte[] buffer = new byte[8192];
            int read;
            long total = 0;
            while ((read = in.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                total += read;
                RenpyResourceLimits.checkInflated(total);
                if (entry.getCompressedSize() > 0) {
                    RenpyResourceLimits.checkInflateRatio(entry.getCompressedSize(), total);
                }
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

    private static long le32Unsigned(byte[] data, int pos) {
        return (data[pos] & 0xffL)
                | ((data[pos + 1] & 0xffL) << 8)
                | ((data[pos + 2] & 0xffL) << 16)
                | ((data[pos + 3] & 0xffL) << 24);
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
