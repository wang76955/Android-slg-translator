package com.slgtranslator.app;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.StatFs;
import android.util.Log;

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
import java.io.RandomAccessFile;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.InflaterInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Compiles the generated Ren'Py translation .rpy files into compiled .rpyc
 * files that the Android archive loader can actually read. Ren'Py loads
 * scripts from an APK archive only when they are .rpyc; plain .rpy files in
 * the archive are ignored by the script scanner, which is why selecting the
 * injected 翻译文本 language never switched the game text before.
 */
public final class TranslationCompiler {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    private static final String TAG = "SLGCompiler";
    private static final String STORAGE_ERROR_CODE = "translation_storage_insufficient";
    private static final long MIN_STORAGE_SAFETY_MARGIN_BYTES = 256L * 1024L * 1024L;
    private static final String BUNDLED_CJK_FONT_ENTRY =
            "assets/slg/fonts/NotoSansSC-Regular.ttf";
    private static final String BUNDLED_CJK_FONT_APK_PATH =
            "assets/x-game/x-slg-fonts/x-NotoSansSC-Regular.ttf";
    private static final String SOURCE_MARKER_ENTRY =
            "assets/slg-translator-marker.txt";
    private static final Pattern CHINESE_STYLE_FONT_ASSIGNMENT = Pattern.compile(
            "(?m)(\\b(?:text_font|name_text_font|interface_text_font|button_text_font|"
                    + "choice_button_text_font|system_font)\\s*=\\s*[\\\"'])([^\\\"'\\r\\n]+)([\\\"'])");
    private static final Pattern ALWAYS_ON_THEME_FONT_ASSIGNMENT = Pattern.compile(
            "(?m)(\\bregular_font\\s*=\\s*[\\\"'])([^\\\"'\\r\\n]+)([\\\"'])");

    private TranslationCompiler() {
    }

    public static void compileTranslationsIntoApk(Context context, PluginCall call) {
        String apkUri = call.getString("apkUri");
        if (apkUri == null || apkUri.isEmpty()) {
            call.reject("apkUri required");
            return;
        }
        String phase = "start";
        PendingApkEntryStore pendingStore = null;
        try {
            phase = "read_template_meta";
            File apk = fileFrom(apkUri);
            if (apk == null || !apk.isFile()) {
                call.reject("\u8865\u4e01\u6e90 APK \u4e0d\u5b58\u5728: " + apkUri);
                return;
            }
            assertPristineSource(apk);
            String activationMode = normalizeActivationMode(call.getString("activationMode"));
            TemplateMeta meta = readTemplateMeta(apk);
            Log.i(TAG, "compile start mode=" + activationMode
                    + " template=" + meta.sourcePath
                    + " version=" + meta.version
                    + " key=" + meta.key
                    + " compatibility=" + (meta.compatibility == null
                    ? "null" : meta.compatibility.generationSupport));
            WriterBackend<RpycCompatibility.Report> writer = RenpyRpycWriter.INSTANCE;
            boolean writerSupported = writer != null
                    && writer.supports(meta.compatibility);
            boolean extractOnly = meta.compatibility != null
                    && (meta.compatibility.generationSupport
                            == RpycCompatibility.GenerationSupport.LEGACY_EXTRACT_ONLY
                    || meta.compatibility.generationSupport
                            == RpycCompatibility.GenerationSupport.UNKNOWN_EXTRACT_ONLY);
            if (meta.compatibility != null
                    && !meta.compatibility.canGenerate()) {
                if (extractOnly && !writerSupported) {
                    call.resolve(writerBlockedResult(activationMode, meta));
                    return;
                }
                call.resolve(compileResult(activationMode, 0, compiledPathFor(activationMode),
                        translatorLanguageFor(activationMode), meta));
                return;
            }
            if (!writerSupported) {
                call.resolve(writerBlockedResult(activationMode, meta));
                return;
            }
            java.util.LinkedHashMap<String, String> merged = new java.util.LinkedHashMap<>();
            List<TranslationUnit> units = new ArrayList<>();
            List<String> allTranslations = new ArrayList<>();
            phase = "collect_existing_tl_none";
            Set<String> existingAlwaysOnOldTexts = "always_on".equals(activationMode)
                    ? collectExistingAlwaysOnOldTexts(apk)
                    : java.util.Collections.<String>emptySet();
            int skippedExistingTranslationCount = 0;
            boolean crossFileCollision = false;
            String language = null;
            // Read the generated translation .rpy files straight from the output
            // directory. Passing them through the JS bridge truncates large
            // payloads, which silently dropped most files.
            File outputDir = new File(context.getExternalFilesDir(null), "SLG-Translator-Output");
            JSArray requestedItems = call.getArray("items");
            boolean hasRequestedItems = requestedItems != null && requestedItems.length() > 0;
            phase = "collect_requested_rpy";
            List<File> rpyFiles = hasRequestedItems
                    ? collectRequestedRpy(outputDir, requestedItems, activationMode)
                    : new ArrayList<File>();
            // Keep the legacy scan only for callers that predate the item-path
            // contract. Once a request supplies items, stale cached buckets must
            // never be merged into the current compilation.
            if (!hasRequestedItems) {
                collectSlgRpy(outputDir, rpyFiles, activationMode);
            }
            Log.i(TAG, "translation inputs requested=" + hasRequestedItems
                    + " count=" + rpyFiles.size());
            for (File rpy : rpyFiles) {
                phase = "parse_rpy:" + rpy.getName();
                String content = readTextFile(rpy);
                if (content == null || content.isEmpty()) {
                    continue;
                }
                if (language == null) {
                    language = languageOf(rpy.getPath(), content);
                }
                List<String[]> filePairs = new ArrayList<>();
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
                    if (existingAlwaysOnOldTexts.contains(oldText)) {
                        skippedExistingTranslationCount++;
                        continue;
                    }
                    filePairs.add(new String[]{oldText, newText});
                }
                if (filePairs.isEmpty()) {
                    continue;
                }
                String fileCollision = LocalTranslationSupport.translationCollisionConflict(filePairs);
                if (fileCollision != null) {
                    call.reject(fileCollision + ": source=" + rpy.getPath());
                    return;
                }
                units.add(new TranslationUnit(rpy, filePairs));
                for (String[] pair : filePairs) {
                    String oldText = pair[0];
                    String newText = pair[1];
                    allTranslations.add(newText);
                    if (merged.containsKey(oldText)
                            && !merged.get(oldText).equals(newText)) {
                        // An exact-old collision across source files is legal in
                        // Ren'Py's per-file translation model. It cannot be
                        // represented by the legacy single merged artifact, so
                        // the write phase below falls back to one RPYC per file.
                        crossFileCollision = true;
                    } else {
                        merged.put(oldText, newText);
                    }
                }
            }
            Log.i(TAG, "translation units=" + units.size()
                    + " merged=" + merged.size()
                    + " all=" + allTranslations.size()
                    + " skippedExisting=" + skippedExistingTranslationCount
                    + " crossFileCollision=" + crossFileCollision);
            if (language == null || language.isEmpty() || units.isEmpty()) {
                call.resolve(compileResult(activationMode, 0, compiledPathFor(activationMode),
                        translatorLanguageFor(activationMode), meta));
                return;
            }
            List<String[]> pairs = new ArrayList<>();
            for (java.util.Map.Entry<String, String> entry : merged.entrySet()) {
                pairs.add(new String[]{entry.getKey(), entry.getValue()});
            }
            File pendingRoot = context.getCacheDir();
            if (pendingRoot == null) {
                pendingRoot = context.getFilesDir();
            }
            pendingStore = new PendingApkEntryStore(new File(
                    pendingRoot, "slg-pending-apk-" + Long.toHexString(System.nanoTime())));
            Set<Integer> requiredCodePoints = new LinkedHashSet<>(
                    RenpyFontSupport.defaultRequiredCodePoints());
            // The fixed baseline is a hard gate before any translation artifact is written.
            RenpyFontSupport.FontReport baselineReport = RenpyFontSupport.inspect(
                    context, apk, requiredCodePoints);
            if (!baselineReport.isComplete()) {
                FontSelection baselineFallback = selectFont(context, apk, requiredCodePoints);
                if (baselineFallback == null || !baselineFallback.bundledFallback) {
                    String failureCode = fontFailureCode(baselineReport);
                    call.reject(failureCode + ": baseline missingCodePoints="
                            + baselineReport.missingCodePoints + ", bestFont="
                            + String.valueOf(baselineReport.bestFontPath));
                    return;
                }
            }
            requiredCodePoints.addAll(RenpyFontSupport.codePointsOfTranslations(allTranslations));
            RenpyFontSupport.FontReport fontReport = RenpyFontSupport.inspect(
                    context, apk, requiredCodePoints);
            FontSelection fontSelection;
            if (!fontReport.isComplete()) {
                fontSelection = selectFont(context, apk, requiredCodePoints);
                if (fontSelection == null) {
                    String failureCode = fontFailureCode(fontReport);
                    call.reject(failureCode + ": missingCodePoints="
                            + fontReport.missingCodePoints + ", bestFont="
                            + String.valueOf(fontReport.bestFontPath));
                    return;
                }
            } else {
                fontSelection = selectFont(context, apk, requiredCodePoints);
            }
            if (fontSelection == null) {
                String failureCode = fontFailureCode(fontReport);
                call.reject(failureCode + ": missingCodePoints="
                        + fontReport.missingCodePoints + ", bestFont="
                        + String.valueOf(fontReport.bestFontPath));
                return;
            }
            List<String[]> pending = new ArrayList<>();
            String compiledPath;
            String translatorLanguage = translatorLanguageFor(activationMode);
            int compiledCount;
            int translationArtifactCount;
            if (crossFileCollision) {
                phase = "compile_per_file";
                compiledPath = null;
                compiledCount = 0;
                translationArtifactCount = 0;
                for (TranslationUnit unit : units) {
                    phase = "compile_per_file:" + unit.source.getName();
                    String generatedPath = compiledPathForUnit(outputDir, unit.source, activationMode);
                    String runtimeFilename = runtimeFilename(unit.source.getPath());
                    byte[] rpyc = compileRpyc(translatorLanguage, runtimeFilename,
                            unit.pairs, meta);
                    RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                            rpyc, meta.version, meta.key, translatorLanguage, unit.pairs.size());
                    if (!validation.valid) {
                        throw new CompilationValidationException(validation.code, validation.message);
                    }
                    validateCompiledPickleSlots(rpyc);
                    if (compiledPath == null) {
                        compiledPath = generatedPath;
                    }
                    pending.add(new String[]{generatedPath, runtimeFilename});
                    pendingStore.add(generatedPath, runtimeFilename, rpyc);
                    compiledCount += unit.pairs.size();
                    translationArtifactCount++;
                }
            } else {
                phase = "compile_merged";
                TranslationArtifact artifact = compileTranslationArtifact(activationMode, pairs, meta);
                compiledPath = artifact.compiledPath;
                compiledCount = merged.size();
                translationArtifactCount = 1;
                pending.add(new String[]{artifact.compiledPath, artifact.runtimeFilename});
                pendingStore.add(artifact.compiledPath, artifact.runtimeFilename, artifact.rpyc);
            }
            if ("selectable".equals(activationMode)) {
                String translatorRuntimeFont = translatorFontPath(fontSelection.apkPath);
                String translatorAssetFont = translatorFontAssetPath(fontSelection.apkPath);
                byte[] translatorFontBytes = fontSelection.fontBytes;
                if (translatorRuntimeFont == null || translatorAssetFont == null
                        || translatorFontBytes == null || translatorFontBytes.length == 0) {
                    call.reject("renpy_font_asset_missing: could not copy the selected APK font into "
                            + "the slgtranslated language bucket");
                    return;
                }
                // 风格克隆必须与注入进 slgtranslated 桶的字体一致:
                // fontSelection 才是覆盖全部必需码点的那个字体(含 bundled 兜底)。
                byte[] styleRpyc = cloneChineseStyleRpyc(apk, fontSelection.apkPath);
                if (styleRpyc == null) {
                    call.reject("renpy_font_style_rewrite_unsafe: no verified chinese/schinese style "
                            + "could be safely cloned with the selected translation font");
                    return;
                }
                pending.add(new String[]{translatorAssetFont, translatorRuntimeFont});
                pendingStore.add(translatorAssetFont, translatorRuntimeFont, translatorFontBytes);
                pending.add(new String[]{"assets/x-game/x-tl/x-slgtranslated/x-style.rpyc",
                        "game/tl/slgtranslated/style.rpy"});
                pendingStore.add("assets/x-game/x-tl/x-slgtranslated/x-style.rpyc",
                        "game/tl/slgtranslated/style.rpy", styleRpyc);
            }
            DialogueRewriteStats dialogueStats = null;
            if ("always_on".equals(activationMode)) {
                phase = "rewrite_source_dialogue";
                boolean py2Engine = meta.compatibility != null
                        && meta.compatibility.isProtocol2WriterCompatible();
                dialogueStats = new DialogueRewriteStats();
                appendAlwaysOnDialogueEntries(apk, units, pending, pendingStore, py2Engine,
                        dialogueStats);
                appendSelectedFontEntry(fontSelection, activationMode, pending, pendingStore);
                appendAlwaysOnThemeFontEntry(apk, fontSelection.apkPath, pending, pendingStore);
                appendAlwaysOnGuiFontEntry(apk, fontSelection.apkPath, pending, pendingStore);
            }
            phase = "preflight_rewrite_storage";
            preflightRewriteStorage(apk, pendingStore);
            phase = "rewrite_apk";
            rewriteApkWithEntries(apk, pending, pendingStore);
            JSObject result = compileResult(activationMode, compiledCount,
                    compiledPath, translatorLanguage, meta, fontReport);
            result.put("compiledArtifactCount", translationArtifactCount);
            result.put("existingTranslationSkipped", skippedExistingTranslationCount);
            result.put("collisionStrategy", crossFileCollision ? "per_file" : "merged");
            result.put("selectedFontPath", fontSelection.apkPath);
            result.put("bundledFontFallback", fontSelection.bundledFallback);
            if (dialogueStats != null) {
                result.put("dialogueRewriteMissCount", dialogueStats.missedCount);
                JSArray missedSamples = new JSArray();
                for (String sample : dialogueStats.missedSamples) {
                    missedSamples.put(sample);
                }
                result.put("dialogueRewriteMissedSamples", missedSamples);
            }
            call.resolve(result);
        } catch (Exception e) {
            if (e instanceof TranslationStorageException) {
                TranslationStorageException storage = (TranslationStorageException) e;
                call.reject(STORAGE_ERROR_CODE + ": " + storage.getMessage());
                return;
            }
            if (e instanceof CompilationValidationException) {
                CompilationValidationException validation = (CompilationValidationException) e;
                call.reject(validation.code + ": " + validation.getMessage());
                return;
            }
            String message = e.getMessage();
            Log.e(TAG, "compile failure phase=" + phase
                    + " type=" + e.getClass().getName()
                    + " message=" + (message == null ? e.toString() : message));
            call.reject("\u7f16\u8bd1\u7ffb\u8bd1\u8d44\u6e90\u5931\u8d25: phase=" + phase
                    + "; type=" + e.getClass().getName() + "; "
                    + (message == null ? e.toString() : message));
        } finally {
            if (pendingStore != null) {
                pendingStore.close();
            }
        }
    }

    private static String fontFailureCode(RenpyFontSupport.FontReport report) {
        String code = report == null ? null : report.failureCode();
        return code == null || code.isEmpty() ? "renpy_font_missing_glyphs" : code;
    }

    private static JSObject compileResult(String activationMode, int compiled,
                                          String compiledPath, String translatorLanguage,
                                          TemplateMeta meta) {
        return compileResult(activationMode, compiled, compiledPath, translatorLanguage, meta, null);
    }

    private static JSObject writerBlockedResult(String activationMode, TemplateMeta meta) {
        JSObject result = compileResult(activationMode, 0, compiledPathFor(activationMode),
                translatorLanguageFor(activationMode), meta);
        result.put("writerBlocked", true);
        result.put("reasonCode", "engine_detected_no_writer");
        result.put("workflow", EngineCapabilities.Workflow.TRANSLATABLE_NO_PATCH.name());
        return result;
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
            report.put("code", fontReport.failureCode());
            report.put("warnings", warnings);
            result.put("fontReport", report);
            result.put("fontFailureCode", fontReport.failureCode());
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

    /**
     * Gives a per-source-file fallback artifact a stable app-owned name while
     * keeping the original source path in the RPYC node metadata.
     */
    private static String compiledPathForUnit(File outputDir, File source,
                                              String activationMode) throws IOException {
        String root = outputDir.getCanonicalPath().replace('\\', '/');
        String path = source.getCanonicalPath().replace('\\', '/');
        String relative = path.startsWith(root + "/")
                ? path.substring(root.length() + 1) : path;
        String bucket = "always_on"
                .equals(activationMode)
                ? "assets/x-game/x-tl/x-None/"
                : "assets/x-game/x-tl/x-slgtranslated/";
        return bucket + "x-slgtranslator-" + sha256Hex(relative) + ".rpyc";
    }

    private static String sha256Hex(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(
                    value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(digest.length * 2);
            for (byte item : digest) {
                out.append(Character.forDigit((item >>> 4) & 0x0f, 16));
                out.append(Character.forDigit(item & 0x0f, 16));
            }
            return out.toString();
        } catch (Exception ignored) {
            return Integer.toHexString(value.hashCode());
        }
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

    /** One generated .rpy file and its validated translation pairs. */
    public static final class TranslationUnit {
        final File source;
        final List<String[]> pairs;

        public TranslationUnit(File source, List<String[]> pairs) {
            this.source = source;
            this.pairs = pairs;
        }
    }

    /**
     * Accumulates always-on dialogue rewrite visibility: how many exact-old
     * pairs matched no serialized Say.what, with a few capped samples. This
     * makes the silent-skip failure mode visible in the compile result.
     */
    static final class DialogueRewriteStats {
        private static final int MAX_SAMPLES = 3;

        int missedCount;
        final List<String> missedSamples = new ArrayList<>();

        void addMissed(List<String> missed) {
            if (missed == null) {
                return;
            }
            for (String text : missed) {
                missedCount++;
                if (missedSamples.size() < MAX_SAMPLES) {
                    String sample = text == null ? "" : text;
                    missedSamples.add(sample.length() > 80
                            ? sample.substring(0, 80) + "\u2026" : sample);
                }
            }
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
            throws CompilationValidationException, IOException {
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
        validateCompiledPickleSlots(rpyc);
        return new TranslationArtifact(normalized, translatorLanguage, compiledPath,
                runtimeFilename, rpyc);
    }

    /**
     * Every pickle-shaped slot of a compiled RPC2 artifact must pass strict
     * stream validation before it is allowed into the APK. Non-pickle slots
     * (keys tables) are skipped; slots whose content walks as a pickle must
     * satisfy FRAME/memo/bounds checks.
     */
    private static void validateCompiledPickleSlots(byte[] rpyc) throws IOException {
        List<int[]> slots = parseRpc2Slots(rpyc);
        if (slots == null) {
            throw new CompilationValidationException("renpy_pickle_validation_failed",
                    "compiled artifact has no readable RPC2 slots");
        }
        for (int[] slot : slots) {
            byte[] compressed = slice(rpyc, slot[1], slot[1] + slot[2]);
            byte[] inflated = inflate(compressed);
            if (inflated == null || LanguageMenuSupport.walk(inflated) == null) {
                continue; // non-pickle slot
            }
            String code = RpycStreamValidator.validate(inflated);
            if (code != null) {
                throw new CompilationValidationException("renpy_pickle_validation_failed",
                        "compiled artifact pickle is invalid: " + code);
            }
        }
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

    /**
     * Selects the one Ren'Py translation bucket that matches the artifact being
     * generated. The UI may pass metadata for several mirrors (for example
     * x-None, x-english, and x-chinese) in one request, but merging those
     * mirrors makes the same old string collide with different translations.
     */
    private static boolean isCompilerBucket(String path, String activationMode) {
        String normalized = path.replace('\\', '/').toLowerCase();
        if ("always_on".equals(activationMode)) {
            return normalized.contains("/x-tl/x-none/")
                    || normalized.endsWith("/x-tl/x-none")
                    || normalized.contains("/tl/none/")
                    || normalized.endsWith("/tl/none");
        }
        return normalized.contains("/x-tl/x-slgtranslated/")
                || normalized.endsWith("/x-tl/x-slgtranslated")
                || normalized.contains("/tl/slgtranslated/")
                || normalized.endsWith("/tl/slgtranslated");
    }

    /**
     * Reads old keys already registered by the game's own always-on translation
     * bucket. Ren'Py rejects a second TranslateString registration for the same
     * old text, so a generated tl/None artifact must leave those keys to the game.
     */
    private static Set<String> collectExistingAlwaysOnOldTexts(File apk) throws IOException {
        Set<String> result = new LinkedHashSet<>();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                String normalized = name.replace('\\', '/').toLowerCase();
                if (!isAlwaysOnTranslationEntry(normalized)
                        || isAppGeneratedTranslationEntry(name)) {
                    continue;
                }
                byte[] bytes = readEntry(zip, entry);
                List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                        bytes, name, true);
                for (RenpyTextRecord record : records) {
                    if (record.kind == RenpyTextRecord.Kind.TRANSLATION_OLD
                            && record.text != null && !record.text.isEmpty()) {
                        result.add(record.text);
                    }
                }
            }
        }
        return result;
    }

    private static boolean isAlwaysOnTranslationEntry(String normalizedPath) {
        if (normalizedPath == null
                || !(normalizedPath.endsWith(".rpyc") || normalizedPath.endsWith(".rpymc"))) {
            return false;
        }
        return normalizedPath.contains("/x-tl/x-none/")
                || normalizedPath.endsWith("/x-tl/x-none")
                || normalizedPath.contains("/tl/none/")
                || normalizedPath.endsWith("/tl/none");
    }

    /**
     * Selects only the files written for the current JS compilation request.
     * The bridge still carries the small path metadata, while the potentially
     * large translation bodies remain on disk and are read from there.
     */
    private static List<File> collectRequestedRpy(File outputDir, JSArray items,
                                                  String activationMode)
            throws IOException {
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        List<File> result = new ArrayList<>();
        File root = outputDir.getCanonicalFile();
        String rootPrefix = root.getPath() + File.separator;
        for (int i = 0; i < items.length(); i++) {
            Object raw = items.opt(i);
            if (!(raw instanceof JSONObject)) {
                continue;
            }
            String path = ((JSONObject) raw).optString("path", "");
            if (path == null || path.trim().isEmpty()) {
                continue;
            }
            String normalized = path.replace('\\', '/');
            if (!normalized.endsWith(".rpy")
                    || normalized.startsWith("/")
                    || normalized.contains("..")) {
                continue;
            }
            if (!isCompilerBucket(normalized, activationMode)) {
                continue;
            }
            File candidate = new File(outputDir, normalized).getCanonicalFile();
            String candidatePath = candidate.getPath();
            if (!candidatePath.startsWith(rootPrefix) || !candidate.isFile()) {
                continue;
            }
            if (seen.add(candidatePath)) {
                result.add(candidate);
            }
        }
        return result;
    }

    private static void collectSlgRpy(File dir, List<File> out, String activationMode) {
        File[] files = dir.listFiles();
        if (files == null) {
            return;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                if (isCompilerBucket(file.getAbsolutePath(), activationMode)) {
                    collectRpyFiles(file, out);
                } else {
                    collectSlgRpy(file, out, activationMode);
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
        if (meta.compatibility.isProtocol2WriterCompatible()) {
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

    private static void preflightRewriteStorage(File apk, PendingApkEntryStore contents)
            throws IOException {
        if (apk == null || !apk.isFile()) {
            throw new TranslationStorageException("source APK is unavailable");
        }
        if (contents == null) {
            throw new TranslationStorageException("pending APK entries are unavailable");
        }
        pruneStaleBuildCopies(apk);
        File temporary = new File(apk.getAbsolutePath() + ".tl.tmp");
        if (temporary.exists() && !temporary.delete()) {
            throw new TranslationStorageException("stale temporary APK cannot be removed: "
                    + temporary.getAbsolutePath());
        }

        long sourceBytes = Math.max(0L, apk.length());
        long pendingBytes = contents.totalPayloadBytes();
        long safetyMargin = Math.max(MIN_STORAGE_SAFETY_MARGIN_BYTES, sourceBytes / 20L);
        long requiredBytes = safeAdd(safeAdd(sourceBytes, sourceBytes), pendingBytes);
        requiredBytes = safeAdd(requiredBytes, safetyMargin);
        long availableBytes = availableBytesAt(apk.getParentFile());
        if (availableBytes < requiredBytes) {
            throw new TranslationStorageException("requiredBytes=" + requiredBytes
                    + ", availableBytes=" + availableBytes
                    + ", sourceBytes=" + sourceBytes
                    + ", pendingBytes=" + pendingBytes);
        }

        File pendingDirectory = contents.storageDirectory();
        long pendingAvailableBytes = availableBytesAt(pendingDirectory);
        long pendingRequiredBytes = safeAdd(pendingBytes, safetyMargin);
        if (pendingAvailableBytes < pendingRequiredBytes) {
            throw new TranslationStorageException("pendingRequiredBytes=" + pendingRequiredBytes
                    + ", pendingAvailableBytes=" + pendingAvailableBytes
                    + ", pendingBytes=" + pendingBytes);
        }
    }

    /** Selected font bytes plus the archive path used by the generated game. */
    public static final class FontSelection {
        public final String apkPath;
        public final byte[] fontBytes;
        public final boolean bundledFallback;

        FontSelection(String apkPath, byte[] fontBytes, boolean bundledFallback) {
            this.apkPath = apkPath;
            this.fontBytes = fontBytes;
            this.bundledFallback = bundledFallback;
        }
    }

    /**
     * Selects a font that really contains every required glyph. Target APK
     * fonts win; the translator's bundled CJK font is the explicit fallback.
     */
    static FontSelection selectFont(Context context, File targetApk,
                                    Set<Integer> requiredCodePoints) throws IOException {
        if (targetApk == null || !targetApk.isFile()) {
            return null;
        }
        try (ZipFile zip = new ZipFile(targetApk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (entry.isDirectory() || !isFontEntry(entry)) {
                    continue;
                }
                String name = entry.getName();
                byte[] bytes;
                try {
                    bytes = readEntry(zip, entry);
                } catch (RuntimeException rejected) {
                    continue;
                }
                if (bytes.length == 0) {
                    continue;
                }
                File temporary = writeFontSelectionTemp(context, targetApk, bytes);
                try {
                    if (RenpyFontSupport.coversRequiredCodePoints(temporary,
                            requiredCodePoints)) {
                        return new FontSelection(name, bytes, false);
                    }
                } finally {
                    if (temporary != null && temporary.exists() && !temporary.delete()) {
                        temporary.deleteOnExit();
                    }
                }
            }
        }

        File translatorApk = applicationApk(context);
        byte[] bundled = readArchiveEntry(translatorApk, BUNDLED_CJK_FONT_ENTRY);
        if (bundled == null || bundled.length == 0) {
            return null;
        }
        File temporary = writeFontSelectionTemp(context, translatorApk, bundled);
        try {
            if (!RenpyFontSupport.coversRequiredCodePoints(temporary, requiredCodePoints)) {
                return null;
            }
        } finally {
            if (temporary != null && temporary.exists() && !temporary.delete()) {
                temporary.deleteOnExit();
            }
        }
        return new FontSelection(BUNDLED_CJK_FONT_APK_PATH, bundled, true);
    }

    private static boolean isFontEntry(ZipEntry entry) {
        String name = entry == null ? null : entry.getName();
        if (name == null) {
            return false;
        }
        String lower = name.replace('\\', '/').toLowerCase();
        return lower.endsWith(".ttf") || lower.endsWith(".otf") || lower.endsWith(".ttc");
    }

    private static File applicationApk(Context context) {
        if (context == null) {
            return null;
        }
        try {
            PackageManager packageManager = context.getPackageManager();
            if (packageManager == null) {
                return null;
            }
            ApplicationInfo info = packageManager.getApplicationInfo(
                    context.getPackageName(), 0);
            return info == null || info.sourceDir == null ? null : new File(info.sourceDir);
        } catch (PackageManager.NameNotFoundException error) {
            return null;
        } catch (RuntimeException error) {
            return null;
        }
    }

    private static File writeFontSelectionTemp(Context context, File reference,
                                               byte[] bytes) throws IOException {
        File directory = null;
        if (context != null) {
            directory = context.getCacheDir();
            if (directory == null) {
                directory = context.getFilesDir();
            }
        }
        if (directory == null && reference != null) {
            directory = reference.getAbsoluteFile().getParentFile();
        }
        if (directory == null || (!directory.exists() && !directory.mkdirs())
                || !directory.isDirectory()) {
            throw new IOException("font selection temporary directory is unavailable");
        }
        File temporary = File.createTempFile("slg-font-selection-", ".tmp", directory);
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write(bytes);
            output.flush();
            output.getFD().sync();
        } catch (Throwable error) {
            if (!temporary.delete()) {
                temporary.deleteOnExit();
            }
            if (error instanceof IOException) {
                throw (IOException) error;
            }
            throw new IOException("font selection temporary write failed", error);
        }
        return temporary;
    }

    /**
     * The installed APK directory is an app-owned cache. Remove only stale
     * build material there; arbitrary user-selected files are left untouched.
     */
    private static void pruneStaleBuildCopies(File apk) throws IOException {
        if (apk == null) {
            return;
        }
        File parent = apk.getAbsoluteFile().getParentFile();
        if (parent == null || !parent.isDirectory()) {
            return;
        }
        File[] files = parent.listFiles();
        if (files == null) {
            return;
        }
        boolean installedApkCache = "installed-apks".equals(parent.getName());
        for (File file : files) {
            if (file == null || file.equals(apk) || file.isDirectory()) {
                continue;
            }
            String name = file.getName();
            boolean temporary = installedApkCache
                    ? name.endsWith(".tl.tmp") || name.endsWith(".partial")
                    : name.equals(apk.getName() + ".tl.tmp");
            boolean staleApkCopy = installedApkCache && name.endsWith(".apk");
            if ((temporary || staleApkCopy) && !file.delete()) {
                throw new IOException("stale APK cleanup failed: " + file.getAbsolutePath());
            }
        }
    }

    private static long availableBytesAt(File path) throws IOException {
        File target = path;
        if (target == null) {
            throw new TranslationStorageException("storage path is unavailable");
        }
        if (!target.exists()) {
            target = target.getParentFile();
        }
        if (target == null) {
            throw new TranslationStorageException("storage path is unavailable");
        }
        try {
            return new StatFs(target.getAbsolutePath()).getAvailableBytes();
        } catch (RuntimeException error) {
            throw new TranslationStorageException("storage statistics unavailable: "
                    + error.getMessage(), error);
        }
    }

    private static long safeAdd(long left, long right) {
        if (left < 0L || right < 0L || Long.MAX_VALUE - left < right) {
            return Long.MAX_VALUE;
        }
        return left + right;
    }

    private static void rewriteApkWithEntries(File apk, List<String[]> entries,
                                              PendingApkEntryStore contents)
            throws IOException {
        File temporary = new File(apk.getAbsolutePath() + ".tl.tmp");
        byte[] buffer = new byte[65536];
        boolean committed = false;
        try {
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
                        try (InputStream payload = contents.openPayload(replaceIndex)) {
                            int read;
                            while ((read = payload.read(buffer)) != -1) {
                                out.write(buffer, 0, read);
                            }
                        }
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
                    try (InputStream payload = contents.openPayload(i)) {
                        int read;
                        while ((read = payload.read(buffer)) != -1) {
                            out.write(buffer, 0, read);
                        }
                    }
                    out.closeEntry();
                }
            }
            // Post-write re-read: every replaced/added entry must round-trip
            // byte-identically from the rewritten ZIP before it replaces the
            // source APK. A mismatch here fails the build while the source
            // copy is still intact.
            verifyRewrittenEntries(temporary, entries, contents);
            // Replace the source APK atomically instead of delete-then-rename:
            // a rename failure after delete used to destroy the app-owned
            // source copy. The temporary lives in the same directory, so
            // REPLACE_EXISTING is an atomic rename on the same filesystem.
            try {
                Files.move(temporary.toPath(), apk.toPath(),
                        StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException moveError) {
                throw new IOException("\u6ce8\u5165\u540e\u91cd\u547d\u540d\u5931\u8d25: "
                        + (moveError.getMessage() == null
                        ? moveError.toString() : moveError.getMessage()), moveError);
            }
            committed = true;
        } catch (IOException error) {
            if (isNoSpaceError(error)) {
                throw new TranslationStorageException(error.getMessage(), error);
            }
            throw error;
        } finally {
            if (!committed && temporary.exists() && !temporary.delete()) {
                temporary.deleteOnExit();
            }
        }
    }

    /**
     * Re-reads every pending entry from the rewritten ZIP and compares it
     * byte-for-byte with the spooled payload. Runs before the atomic replace
     * so a truncated or corrupted rewrite can never destroy the source APK.
     */
    private static void verifyRewrittenEntries(File temporary, List<String[]> entries,
                                               PendingApkEntryStore contents)
            throws IOException {
        try (ZipFile check = new ZipFile(temporary)) {
            for (int i = 0; i < entries.size(); i++) {
                String name = entries.get(i)[0];
                ZipEntry written = check.getEntry(name);
                if (written == null || written.isDirectory()) {
                    throw new IOException("rewrite verification: entry missing: " + name);
                }
                try (InputStream actual = check.getInputStream(written);
                     InputStream expected = contents.openPayload(i)) {
                    if (!streamsEqual(actual, expected)) {
                        throw new IOException("rewrite verification: entry mismatch: " + name);
                    }
                }
            }
        }
    }

    private static boolean streamsEqual(InputStream left, InputStream right) throws IOException {
        byte[] leftBuffer = new byte[65536];
        byte[] rightBuffer = new byte[65536];
        while (true) {
            int leftRead = readBlock(left, leftBuffer);
            int rightRead = readBlock(right, rightBuffer);
            if (leftRead != rightRead) {
                return false;
            }
            if (leftRead < 0) {
                return true;
            }
            if (!java.util.Arrays.equals(leftBuffer, 0, leftRead, rightBuffer, 0, rightRead)) {
                return false;
            }
        }
    }

    private static int readBlock(InputStream input, byte[] buffer) throws IOException {
        int offset = 0;
        while (offset < buffer.length) {
            int read = input.read(buffer, offset, buffer.length - offset);
            if (read < 0) {
                return offset == 0 ? -1 : offset;
            }
            offset += read;
        }
        return offset;
    }

    private static boolean isNoSpaceError(Throwable error) {
        Throwable current = error;
        while (current != null) {
            String message = current.getMessage();
            if (message != null) {
                String normalized = message.toLowerCase();
                if (normalized.contains("enospc")
                        || normalized.contains("no space left")
                        || normalized.contains("not enough space")) {
                    return true;
                }
            }
            current = current.getCause();
        }
        return false;
    }

    private static final class TranslationStorageException extends IOException {
        TranslationStorageException(String message) {
            super(message);
        }

        TranslationStorageException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    /**
     * Always-on translation files are registered through tl/None for menus and
     * marked strings, but ordinary dialogue is serialized in the game's
     * original Say nodes. Rewrite those source RPYC entries in place so the
     * game displays translated dialogue without requiring a language switch.
     */
    /**
     * True when an APK entry is safe to rewrite in place for always-on
     * dialogue. Screen/style/gui/framework files must never be rewritten:
     * they hold UI definitions and their pickle layout is not a dialogue
     * script, so in-place patching breaks the game's script loading.
     */
    static boolean isDialoguePatchableSource(String path) {
        if (path == null) {
            return false;
        }
        String normalized = path.replace('\\', '/').toLowerCase();
        if (!normalized.endsWith(".rpyc") && !normalized.endsWith(".rpymc")) {
            return false;
        }
        if (normalized.contains("/x-renpy/") || normalized.contains("/renpy/common/")) {
            return false;
        }
        String name = normalized.substring(normalized.lastIndexOf('/') + 1);
        if (name.endsWith(".rpyc")) {
            name = name.substring(0, name.length() - 5);
        } else if (name.endsWith(".rpymc")) {
            name = name.substring(0, name.length() - 6);
        }
        String core = name.startsWith("x-") ? name.substring(2) : name;
        if (core.startsWith("_")) {
            return false;
        }
        for (String segment : normalized.split("/")) {
            String s = segment.startsWith("x-") ? segment.substring(2) : segment;
            if (s.startsWith("_") || s.startsWith("gui") || s.startsWith("screen")
                    || s.startsWith("screens") || s.equals("tl") || s.startsWith("common")) {
                return false;
            }
        }
        String lower = core;
        if (lower.startsWith("gui")
                || lower.contains("_screen")
                || lower.startsWith("screen")
                || lower.startsWith("screens")
                || lower.contains("_layout")
                || lower.contains("preferences")
                || lower.contains("yesno")
                || lower.contains("main_menu")
                || lower.contains("navigation")
                || lower.contains("joystick")
                || lower.contains("load_save")
                || lower.contains("scrolling")
                || lower.startsWith("style")
                || lower.startsWith("options")
                || lower.startsWith("themes")
                || lower.startsWith("common")
                || lower.startsWith("media")
                || lower.startsWith("audio")
                || lower.startsWith("images")
                || lower.startsWith("gallery")
                || lower.startsWith("init")
                || lower.startsWith("splash")) {
            return false;
        }
        return true;
    }

    private static void appendAlwaysOnDialogueEntries(File apk, List<TranslationUnit> units,
                                                       List<String[]> pending,
                                                       PendingApkEntryStore pendingStore)
            throws IOException {
        appendAlwaysOnDialogueEntries(apk, units, pending, pendingStore, false, null);
    }

    private static void appendAlwaysOnDialogueEntries(File apk, List<TranslationUnit> units,
                                                       List<String[]> pending,
                                                       PendingApkEntryStore pendingStore,
                                                       boolean py2Engine,
                                                       DialogueRewriteStats stats)
            throws IOException {
        LinkedHashMap<String, LinkedHashMap<String, String>> looseSources = new LinkedHashMap<>();
        LinkedHashMap<String, LinkedHashMap<String, LinkedHashMap<String, String>>> rpaSources =
                new LinkedHashMap<>();
        for (TranslationUnit unit : units) {
            String sourcePath = sourceApkPath(unit.source);
            if (sourcePath == null || !isDialoguePatchableSource(sourcePath)) {
                continue;
            }
            String[] virtual = RpaArchive.splitVirtual(sourcePath);
            if (virtual.length == 2) {
                LinkedHashMap<String, LinkedHashMap<String, String>> archive =
                        rpaSources.get(virtual[0]);
                if (archive == null) {
                    archive = new LinkedHashMap<>();
                    rpaSources.put(virtual[0], archive);
                }
                LinkedHashMap<String, String> translations = archive.get(virtual[1]);
                if (translations == null) {
                    translations = new LinkedHashMap<>();
                    archive.put(virtual[1], translations);
                }
                for (String[] pair : unit.pairs) {
                    if (pair != null && pair.length >= 2 && pair[0] != null && pair[1] != null) {
                        translations.put(pair[0], pair[1]);
                    }
                }
            } else {
                LinkedHashMap<String, String> translations = looseSources.get(sourcePath);
                if (translations == null) {
                    translations = new LinkedHashMap<>();
                    looseSources.put(sourcePath, translations);
                }
                for (String[] pair : unit.pairs) {
                    if (pair != null && pair.length >= 2 && pair[0] != null && pair[1] != null) {
                        translations.put(pair[0], pair[1]);
                    }
                }
            }
        }
        if (looseSources.isEmpty() && rpaSources.isEmpty()) {
            return;
        }
        try (ZipFile zip = new ZipFile(apk)) {
            for (Map.Entry<String, LinkedHashMap<String, String>> entry : looseSources.entrySet()) {
                String sourcePath = entry.getKey();
                if (entry.getValue().isEmpty()) {
                    continue;
                }
                ZipEntry source = zip.getEntry(sourcePath);
                if (source == null || source.isDirectory()) {
                    continue;
                }
                byte[] original = readEntry(zip, source);
                RpycDialoguePatcher.RewriteOutcome outcome =
                        RpycDialoguePatcher.rewriteSayTextsDetailed(original, entry.getValue());
                if (outcome == null) {
                    if (stats != null) {
                        stats.addMissed(new ArrayList<>(entry.getValue().keySet()));
                    }
                    continue;
                }
                if (stats != null) {
                    stats.addMissed(outcome.missedOldTexts);
                }
                byte[] rewritten = outcome.bytes;
                int existing = indexOfEntry(pending, sourcePath);
                if (existing >= 0) {
                    pendingStore.replace(existing, rewritten);
                } else {
                    pending.add(new String[]{sourcePath, sourcePath});
                    pendingStore.add(sourcePath, sourcePath, rewritten);
                }
            }
            for (Map.Entry<String, LinkedHashMap<String, LinkedHashMap<String, String>>> entry
                    : rpaSources.entrySet()) {
                rebuildVirtualRpaArchive(zip, entry.getKey(), entry.getValue(), py2Engine,
                        pending, pendingStore, stats);
            }
        }
    }

    private static void appendAlwaysOnThemeFontEntry(File apk, String bestFontPath,
                                                      List<String[]> pending,
                                                      PendingApkEntryStore pendingStore)
            throws IOException {
        String runtimeFontPath = alwaysOnFontPath(bestFontPath);
        if (runtimeFontPath == null || runtimeFontPath.isEmpty()) {
            return;
        }
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String sourcePath = entry.getName();
                if (!isAlwaysOnThemePath(sourcePath) || entry.isDirectory()) {
                    continue;
                }
                byte[] original = readEntry(zip, entry);
                byte[] rewritten = rewriteAlwaysOnThemeFont(original, runtimeFontPath);
                if (rewritten == null) {
                    continue;
                }
                int existing = indexOfEntry(pending, sourcePath);
                if (existing >= 0) {
                    pendingStore.replace(existing, rewritten);
                } else {
                    pending.add(new String[]{sourcePath, sourcePath});
                    pendingStore.add(sourcePath, sourcePath, rewritten);
                }
                return;
            }
        }
    }

    private static void appendAlwaysOnGuiFontEntry(File apk, String bestFontPath,
                                                   List<String[]> pending,
                                                   PendingApkEntryStore pendingStore)
            throws IOException {
        String runtimeFontPath = alwaysOnFontPath(bestFontPath);
        if (runtimeFontPath == null || runtimeFontPath.isEmpty()) {
            return;
        }
        final String guiPath = "assets/x-game/x-gui.rpyc";
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(guiPath);
            if (entry == null || entry.isDirectory()) {
                return;
            }
            byte[] rewritten = rewriteChineseStyleFont(readEntry(zip, entry), runtimeFontPath);
            if (rewritten == null) {
                return;
            }
            int existing = indexOfEntry(pending, guiPath);
            if (existing >= 0) {
                pendingStore.replace(existing, rewritten);
            } else {
                pending.add(new String[]{guiPath, guiPath});
                pendingStore.add(guiPath, guiPath, rewritten);
            }
        }
    }

    /** Adds the translator-owned fallback font to the target APK when needed. */
    private static void appendSelectedFontEntry(FontSelection selection,
                                                String activationMode,
                                                List<String[]> pending,
                                                PendingApkEntryStore pendingStore)
            throws IOException {
        if (selection == null || !selection.bundledFallback
                || !"always_on".equals(activationMode)
                || selection.fontBytes == null || selection.fontBytes.length == 0) {
            return;
        }
        if (indexOfEntry(pending, BUNDLED_CJK_FONT_APK_PATH) >= 0) {
            return;
        }
        String runtimePath = alwaysOnFontPath(BUNDLED_CJK_FONT_APK_PATH);
        if (runtimePath == null || runtimePath.isEmpty()) {
            throw new IOException("bundled CJK font runtime path is invalid");
        }
        pending.add(new String[]{BUNDLED_CJK_FONT_APK_PATH, runtimePath});
        pendingStore.add(BUNDLED_CJK_FONT_APK_PATH, runtimePath, selection.fontBytes);
    }

    private static boolean isAlwaysOnThemePath(String path) {
        if (path == null) {
            return false;
        }
        String normalized = path.replace('\\', '/').toLowerCase();
        return "assets/x-renpy/x-common/x-00themes.rpyc".equals(normalized)
                || "assets/renpy/common/00themes.rpyc".equals(normalized);
    }

    /** Exports verified RPA replacements as an independent mod directory. */
    public static void exportRpaMod(File apkOrDir, List<TranslationUnit> units,
                                    File outputDir, boolean py2Engine) throws IOException {
        if (apkOrDir == null || (!apkOrDir.isFile() && !apkOrDir.isDirectory())) {
            throw new IOException("RPA mod source APK is unavailable");
        }
        if (units == null || outputDir == null) {
            throw new IOException("RPA mod arguments are required");
        }
        if (outputDir.exists() && !outputDir.isDirectory()) {
            throw new IOException("RPA mod output is not a directory");
        }
        if (!outputDir.isDirectory() && !outputDir.mkdirs()) {
            throw new IOException("cannot create RPA mod output directory");
        }
        File workspace = new File(outputDir, ".rpa-export-work");
        validateExportWorkspace(outputDir, workspace);
        List<String[]> pending = new ArrayList<>();
        try {
            try (PendingApkEntryStore pendingStore = new PendingApkEntryStore(workspace)) {
                if (Files.isSymbolicLink(workspace.toPath())) {
                    throw new IOException("RPA mod workspace must not be a symbolic link");
                }
                if (apkOrDir.isFile()) {
                    appendAlwaysOnDialogueEntries(apkOrDir, units, pending, pendingStore,
                            py2Engine, null);
                } else {
                    appendAlwaysOnDialogueEntriesFromDirectory(apkOrDir, units, pending,
                            pendingStore, py2Engine, null);
                }
                File stagingRoot = new File(workspace, "staged");
                if (!stagingRoot.mkdirs() && !stagingRoot.isDirectory()) {
                    throw new IOException("cannot create RPA mod staging directory");
                }
                for (int i = 0; i < pending.size(); i++) {
                    String relative = pending.get(i)[0].replace('\\', '/');
                    File target = exportTarget(outputDir, relative);
                    validateExportTarget(target);
                    File staged = exportTarget(stagingRoot, relative);
                    File parent = staged.getParentFile();
                    if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
                        throw new IOException("cannot create RPA mod staging directory: " + parent);
                    }
                    copyFileBacked(pendingStore.openPayload(i), staged);
                    pending.set(i, new String[]{relative, staged.getPath(), target.getPath()});
                }
                commitExportArtifacts(pending, workspace);
            }
        } finally {
            deleteExportWorkspace(workspace);
        }
    }

    private static void validateExportWorkspace(File outputDir, File workspace) throws IOException {
        if (Files.isSymbolicLink(workspace.toPath())) {
            throw new IOException("RPA mod workspace must not be a symbolic link");
        }
        File root = outputDir.getCanonicalFile();
        File candidate = workspace.getCanonicalFile();
        String prefix = root.getPath() + File.separator;
        if (!candidate.getPath().startsWith(prefix)) {
            throw new IOException("RPA mod workspace escapes output directory");
        }
        if (workspace.exists() && !workspace.isDirectory()) {
            throw new IOException("RPA mod workspace is not a directory");
        }
        if (workspace.isDirectory()) {
            String[] children = workspace.list();
            if (children != null && children.length != 0) {
                throw new IOException("RPA mod workspace is not empty");
            }
        }
    }

    private static void validateExportTarget(File target) throws IOException {
        if (Files.isSymbolicLink(target.toPath())) {
            throw new IOException("RPA mod target must not be a symbolic link: " + target);
        }
        if (target.exists() && target.isDirectory()) {
            throw new IOException("RPA mod target is a directory: " + target);
        }
        File parent = target.getParentFile();
        if (parent != null && parent.exists() && !parent.isDirectory()) {
            throw new IOException("RPA mod parent is not a directory: " + parent);
        }
    }

    private static void commitExportArtifacts(List<String[]> pending, File workspace)
            throws IOException {
        File backupRoot = new File(workspace, "backups");
        List<ExportArtifact> artifacts = new ArrayList<>();
        try {
            for (String[] item : pending) {
                if (item == null || item.length < 3) {
                    throw new IOException("RPA mod export metadata is invalid");
                }
                artifacts.add(new ExportArtifact(item[0], new File(item[1]), new File(item[2])));
            }
            for (ExportArtifact artifact : artifacts) {
                File targetParent = artifact.target.getParentFile();
                if (targetParent != null && !targetParent.isDirectory()
                        && !targetParent.mkdirs()) {
                    throw new IOException("cannot create RPA mod directory: " + targetParent);
                }
                if (artifact.target.exists()) {
                    File backup = exportTarget(backupRoot, artifact.relative);
                    File backupParent = backup.getParentFile();
                    if (backupParent != null && !backupParent.isDirectory()
                            && !backupParent.mkdirs()) {
                        throw new IOException("cannot create RPA mod backup directory: "
                                + backupParent);
                    }
                    Files.move(artifact.target.toPath(), backup.toPath(),
                            StandardCopyOption.REPLACE_EXISTING);
                    artifact.backup = backup;
                }
                Files.move(artifact.staged.toPath(), artifact.target.toPath(),
                        StandardCopyOption.REPLACE_EXISTING);
                artifact.committed = true;
            }
        } catch (IOException error) {
            for (int index = artifacts.size() - 1; index >= 0; index--) {
                ExportArtifact artifact = artifacts.get(index);
                try {
                    if (artifact.committed) {
                        Files.deleteIfExists(artifact.target.toPath());
                    }
                    if (artifact.backup != null && artifact.backup.exists()) {
                        Files.move(artifact.backup.toPath(), artifact.target.toPath(),
                                StandardCopyOption.REPLACE_EXISTING);
                    }
                } catch (IOException rollbackError) {
                    error.addSuppressed(rollbackError);
                }
            }
            throw error;
        } finally {
            deleteExportTree(backupRoot);
        }
    }

    private static final class ExportArtifact {
        final String relative;
        final File staged;
        final File target;
        File backup;
        boolean committed;

        ExportArtifact(String relative, File staged, File target) {
            this.relative = relative;
            this.staged = staged;
            this.target = target;
        }
    }

    private static void deleteExportWorkspace(File workspace) throws IOException {
        if (workspace == null) {
            return;
        }
        if (Files.isSymbolicLink(workspace.toPath())) {
            return;
        }
        deleteExportTree(workspace);
        if (workspace.exists()) {
            throw new IOException("RPA mod work directory was not removed: " + workspace);
        }
    }

    private static void deleteExportTree(File file) throws IOException {
        if (file == null || !file.exists()) {
            return;
        }
        if (Files.isSymbolicLink(file.toPath())) {
            Files.deleteIfExists(file.toPath());
            return;
        }
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteExportTree(child);
                }
            }
        }
        Files.deleteIfExists(file.toPath());
    }

    private static void appendAlwaysOnDialogueEntriesFromDirectory(
            File root,
            List<TranslationUnit> units,
            List<String[]> pending,
            PendingApkEntryStore pendingStore,
            boolean py2Engine,
            DialogueRewriteStats stats
    ) throws IOException {
        LinkedHashMap<String, LinkedHashMap<String, LinkedHashMap<String, String>>> rpaSources =
                new LinkedHashMap<>();
        for (TranslationUnit unit : units) {
            String sourcePath = sourceApkPath(unit.source);
            if (sourcePath == null) {
                continue;
            }
            String[] virtual = RpaArchive.splitVirtual(sourcePath);
            if (virtual.length != 2) {
                continue;
            }
            LinkedHashMap<String, LinkedHashMap<String, String>> archive =
                    rpaSources.get(virtual[0]);
            if (archive == null) {
                archive = new LinkedHashMap<>();
                rpaSources.put(virtual[0], archive);
            }
            LinkedHashMap<String, String> translations = archive.get(virtual[1]);
            if (translations == null) {
                translations = new LinkedHashMap<>();
                archive.put(virtual[1], translations);
            }
            for (String[] pair : unit.pairs) {
                if (pair != null && pair.length >= 2 && pair[0] != null && pair[1] != null) {
                    translations.put(pair[0], pair[1]);
                }
            }
        }
        for (Map.Entry<String, LinkedHashMap<String, LinkedHashMap<String, String>>> entry
                : rpaSources.entrySet()) {
            File archive = sourceFileForRelativePath(root, entry.getKey());
            if (archive == null || !archive.isFile()) {
                continue;
            }
            String rpiPath = rpaCompanionPath(entry.getKey());
            File rpi = rpiPath == null ? null : sourceFileForRelativePath(root, rpiPath);
            if (rpiPath != null && (rpi == null || !rpi.isFile())) {
                continue;
            }
            rebuildRpaArchiveFromFiles(archive, rpi, entry.getKey(), entry.getValue(),
                    py2Engine, pending, pendingStore, stats);
        }
    }

    private static File sourceFileForRelativePath(File root, String relative) throws IOException {
        if (relative == null || relative.isEmpty() || relative.startsWith("/")
                || relative.indexOf('\u0000') >= 0) {
            throw new IOException("invalid RPA source path: " + relative);
        }
        File canonicalRoot = root.getCanonicalFile();
        File candidate = new File(canonicalRoot, relative).getCanonicalFile();
        String prefix = canonicalRoot.getPath() + File.separator;
        if (!candidate.getPath().startsWith(prefix)) {
            throw new IOException("RPA source path escapes directory: " + relative);
        }
        return candidate;
    }

    private static void deleteTemporaryFile(File file, String label) throws IOException {
        if (file == null) {
            return;
        }
        Files.deleteIfExists(file.toPath());
        if (file.exists()) {
            throw new IOException(label + " was not removed: " + file);
        }
    }

    private static void rebuildRpaArchiveFromFiles(
            File sourceFile,
            File sourceRpiFile,
            String archivePath,
            Map<String, LinkedHashMap<String, String>> translationsByInternal,
            boolean py2Engine,
            List<String[]> pending,
            PendingApkEntryStore pendingStore,
            DialogueRewriteStats stats
    ) throws IOException {
        File workspace = pendingStore.storageDirectory();
        File rebuiltFile = File.createTempFile("rpa-rebuilt-", ".rpa", workspace);
        String rpiPath = rpaCompanionPath(archivePath);
        File rebuiltRpiFile = sourceRpiFile == null
                ? null : File.createTempFile("rpa-index-rebuilt-", ".rpi", workspace);
        try {
            byte[] sourceRpi = sourceRpiFile == null ? null : readFileBytes(sourceRpiFile);
            Map<String, long[]> before;
            Map<String, byte[]> replacements = new LinkedHashMap<>();
            try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
                before = sourceRpiFile == null
                        ? RpaArchive.readIndexFromFile(source, archivePath)
                        : RpaArchive.listEntryLocations(sourceRpi, rpiPath);
                RenpyResourceLimits.checkEntryCount(before.size());
                for (Map.Entry<String, LinkedHashMap<String, String>> entry
                        : translationsByInternal.entrySet()) {
                    byte[] original = sourceRpiFile == null
                            ? RpaArchive.readEntryFromFile(source, archivePath, entry.getKey())
                            : RpaArchive.readEntryFromFile(source, sourceRpi, archivePath,
                                    entry.getKey());
                    RpycDialoguePatcher.RewriteOutcome outcome =
                            RpycDialoguePatcher.rewriteSayTextsDetailed(original, entry.getValue());
                    if (outcome != null) {
                        replacements.put(entry.getKey(), outcome.bytes);
                        if (stats != null) {
                            stats.addMissed(outcome.missedOldTexts);
                        }
                    } else if (stats != null) {
                        stats.addMissed(new ArrayList<>(entry.getValue().keySet()));
                    }
                }
            }
            if (replacements.isEmpty()) {
                return;
            }
            if (sourceRpiFile != null) {
                try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
                    RpaArchiveWriter.rebuildRpa1(source, sourceRpi, rebuiltFile, rebuiltRpiFile,
                            replacements, py2Engine);
                }
                try (RandomAccessFile rebuilt = new RandomAccessFile(rebuiltFile, "r")) {
                    RpaArchiveWriter.verifyRebuiltRpa1(before, rebuilt,
                            readFileBytes(rebuiltRpiFile), rpiPath, replacements);
                }
            } else {
                try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
                    RpaArchiveWriter.rebuildSelfIndexed(source, rebuiltFile, replacements,
                            py2Engine);
                }
                try (RandomAccessFile rebuilt = new RandomAccessFile(rebuiltFile, "r")) {
                    RpaArchiveWriter.verifyRebuilt(before, rebuilt, archivePath, replacements,
                            null);
                }
            }
            if (indexOfEntry(pending, archivePath) >= 0) {
                throw new IOException("duplicate pending RPA replacement: " + archivePath);
            }
            pending.add(new String[]{archivePath, archivePath});
            pendingStore.addFile(archivePath, archivePath, rebuiltFile);
            if (sourceRpiFile != null) {
                if (indexOfEntry(pending, rpiPath) >= 0) {
                    throw new IOException("duplicate pending RPA index replacement: " + rpiPath);
                }
                pending.add(new String[]{rpiPath, rpiPath});
                pendingStore.addFile(rpiPath, rpiPath, rebuiltRpiFile);
            }
        } finally {
            deleteTemporaryFile(rebuiltFile, "rebuilt RPA temporary file");
            deleteTemporaryFile(rebuiltRpiFile, "rebuilt RPI temporary file");
        }
    }

    private static File exportTarget(File outputDir, String relative) throws IOException {
        if (relative == null || relative.isEmpty() || relative.startsWith("/")
                || relative.indexOf('\u0000') >= 0) {
            throw new IOException("invalid RPA mod path: " + relative);
        }
        File root = outputDir.getCanonicalFile();
        File target = new File(root, relative).getCanonicalFile();
        String prefix = root.getPath() + File.separator;
        if (!target.getPath().startsWith(prefix)) {
            throw new IOException("RPA mod path escapes output directory: " + relative);
        }
        return target;
    }

    private static void copyFileBacked(InputStream input, File target) throws IOException {
        try (InputStream source = input;
             FileOutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = source.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                output.write(buffer, 0, count);
            }
            output.flush();
            output.getFD().sync();
        }
    }

    private static void rebuildVirtualRpaArchive(
            ZipFile zip,
            String archivePath,
            Map<String, LinkedHashMap<String, String>> translationsByInternal,
            boolean py2Engine,
            List<String[]> pending,
            PendingApkEntryStore pendingStore,
            DialogueRewriteStats stats
    ) throws IOException {
        ZipEntry archiveEntry = zip.getEntry(archivePath);
        if (archiveEntry == null || archiveEntry.isDirectory()) {
            return;
        }
        File workspace = pendingStore.storageDirectory();
        File sourceFile = File.createTempFile("rpa-source-", ".rpa", workspace);
        File rebuiltFile = File.createTempFile("rpa-rebuilt-", ".rpa", workspace);
        String rpiPath = rpaCompanionPath(archivePath);
        ZipEntry rpiEntry = rpiPath == null ? null : zip.getEntry(rpiPath);
        boolean rpa1 = rpiEntry != null && !rpiEntry.isDirectory();
        File sourceRpiFile = rpa1
                ? File.createTempFile("rpa-index-source-", ".rpi", workspace) : null;
        File rebuiltRpiFile = rpa1
                ? File.createTempFile("rpa-index-rebuilt-", ".rpi", workspace) : null;
        try {
            copyZipEntryToFile(zip, archiveEntry, sourceFile);
            byte[] sourceRpi = null;
            if (rpa1) {
                copyZipEntryToFile(zip, rpiEntry, sourceRpiFile);
                sourceRpi = readFileBytes(sourceRpiFile);
            }
            Map<String, long[]> before;
            Map<String, byte[]> replacements = new LinkedHashMap<>();
            try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
                before = rpa1
                        ? RpaArchive.listEntryLocations(sourceRpi, rpiPath)
                        : RpaArchive.readIndexFromFile(source, archivePath);
                RenpyResourceLimits.checkEntryCount(before.size());
                for (Map.Entry<String, LinkedHashMap<String, String>> entry
                        : translationsByInternal.entrySet()) {
                    String internalPath = entry.getKey();
                    byte[] original = rpa1
                            ? RpaArchive.readEntryFromFile(source, sourceRpi, archivePath, internalPath)
                            : RpaArchive.readEntryFromFile(source, archivePath, internalPath);
                    RpycDialoguePatcher.RewriteOutcome outcome =
                            RpycDialoguePatcher.rewriteSayTextsDetailed(original, entry.getValue());
                    if (outcome != null) {
                        replacements.put(internalPath, outcome.bytes);
                        if (stats != null) {
                            stats.addMissed(outcome.missedOldTexts);
                        }
                    } else if (stats != null) {
                        stats.addMissed(new ArrayList<>(entry.getValue().keySet()));
                    }
                }
            }
            if (replacements.isEmpty()) {
                return;
            }
            if (rpa1) {
                try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
                    RpaArchiveWriter.rebuildRpa1(source, sourceRpi, rebuiltFile, rebuiltRpiFile,
                            replacements, py2Engine);
                }
                try (RandomAccessFile rebuilt = new RandomAccessFile(rebuiltFile, "r")) {
                    RpaArchiveWriter.verifyRebuiltRpa1(before, rebuilt,
                            readFileBytes(rebuiltRpiFile), rpiPath, replacements);
                }
            } else {
                try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
                    RpaArchiveWriter.rebuildSelfIndexed(source, rebuiltFile, replacements, py2Engine);
                }
                try (RandomAccessFile rebuilt = new RandomAccessFile(rebuiltFile, "r")) {
                    RpaArchiveWriter.verifyRebuilt(before, rebuilt, archivePath, replacements, null);
                }
            }
            int existing = indexOfEntry(pending, archivePath);
            if (existing >= 0) {
                throw new IOException("duplicate pending RPA replacement: " + archivePath);
            }
            pending.add(new String[]{archivePath, archivePath});
            pendingStore.addFile(archivePath, archivePath, rebuiltFile);
            if (rpa1) {
                int existingRpi = indexOfEntry(pending, rpiPath);
                if (existingRpi >= 0) {
                    throw new IOException("duplicate pending RPA index replacement: " + rpiPath);
                }
                pending.add(new String[]{rpiPath, rpiPath});
                pendingStore.addFile(rpiPath, rpiPath, rebuiltRpiFile);
            }
        } finally {
            deleteTemporaryFile(sourceFile, "source RPA temporary file");
            deleteTemporaryFile(rebuiltFile, "rebuilt RPA temporary file");
            deleteTemporaryFile(sourceRpiFile, "source RPI temporary file");
            deleteTemporaryFile(rebuiltRpiFile, "rebuilt RPI temporary file");
        }
    }

    private static String rpaCompanionPath(String archivePath) {
        if (archivePath == null || !archivePath.toLowerCase().endsWith(".rpa")) {
            return null;
        }
        return archivePath.substring(0, archivePath.length() - 4) + ".rpi";
    }

    private static byte[] readFileBytes(File file) throws IOException {
        try (InputStream input = new java.io.FileInputStream(file);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private static void copyZipEntryToFile(ZipFile zip, ZipEntry entry, File target)
            throws IOException {
        if (entry.getCompressedSize() >= 0) {
            RenpyResourceLimits.checkCompressed(entry.getCompressedSize());
        }
        try (InputStream input = zip.getInputStream(entry);
             FileOutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[65536];
            long total = 0L;
            int count;
            while ((count = input.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                total += count;
                RenpyResourceLimits.checkInflated(total);
                if (entry.getCompressedSize() > 0) {
                    RenpyResourceLimits.checkInflateRatio(entry.getCompressedSize(), total);
                }
                output.write(buffer, 0, count);
            }
            output.flush();
            output.getFD().sync();
        }
    }

    private static String sourceApkPath(File generatedRpy) {
        String content = readTextFile(generatedRpy);
        if (content == null || content.isEmpty()) {
            return null;
        }
        String[] lines = content.replace("\r\n", "\n").split("\n", -1);
        for (String line : lines) {
            String trimmed = line.trim();
            if (!trimmed.startsWith("# Source:")) {
                continue;
            }
            String path = trimmed.substring("# Source:".length()).trim().replace('\\', '/');
            if (path.startsWith("assets/") && !path.contains("..")
                    && (path.endsWith(".rpyc") || path.endsWith(".rpymc"))) {
                return path;
            }
        }
        return null;
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
                || normalized.endsWith("/x-translations.rpyc")
                || normalized.contains("/x-tl/x-none/x-slgtranslator-")
                || normalized.contains("/x-tl/x-slgtranslated/x-slgtranslator-");
    }

    /**
     * Translation compilation mutates the app-owned materialized APK. A
     * processed copy must never be accepted as a new translation source: its
     * generated tl/None entries would be scanned as game text and shift every
     * following old/new pair on the next run.
     */
    static void assertPristineSource(File apk) throws IOException {
        if (apk == null || !apk.isFile()) {
            throw new IOException("translation_source_unavailable: source APK is missing");
        }
        try (ZipFile zip = new ZipFile(apk)) {
            assertPristineSource(zip);
        }
    }

    static void assertPristineSource(ZipFile zip) throws IOException {
        if (zip == null) {
            throw new IOException("translation_source_unavailable: source archive is missing");
        }
        if (zip.getEntry(SOURCE_MARKER_ENTRY) != null) {
            throw new IOException("translation_source_already_processed: select the pristine original APK");
        }
        Enumeration<? extends ZipEntry> entries = zip.entries();
        while (entries.hasMoreElements()) {
            String name = entries.nextElement().getName();
            if (isAppGeneratedTranslationEntry(name)) {
                throw new IOException("translation_source_already_processed: select the pristine original APK");
            }
        }
    }

    /**
     * Finds the game's built-in Chinese style file (the one that switches
     * fonts to a CJK-capable font) and clones it for the translator
     * language. Returns the rewritten rpyc bytes, or null when unavailable.
     */
    static byte[] cloneChineseStyleRpyc(File apk, String bestFontPath) throws IOException {
        String normalizedBestFontPath = bestFontPath == null
                ? null : bestFontPath.replace('\\', '/');
        String runtimeFontPath = normalizedBestFontPath != null
                && normalizedBestFontPath.startsWith("assets/")
                ? translatorFontPath(normalizedBestFontPath)
                : renpyFontPath(bestFontPath);
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

    /** Maps an APK font entry to the logical game path after Ren'Py strips x- prefixes. */
    static String alwaysOnFontPath(String apkPath) {
        String gamePath = renpyFontPath(apkPath);
        if (gamePath == null || gamePath.isEmpty()) {
            return null;
        }
        String[] parts = gamePath.split("/");
        StringBuilder logical = new StringBuilder(gamePath.length());
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) {
                logical.append('/');
            }
            String part = parts[i];
            if (part.startsWith("x-") && part.length() > 2) {
                part = part.substring(2);
            }
            logical.append(part);
        }
        return logical.toString();
    }

    /** Maps an APK font entry to the path resolved inside the translator language bucket. */
    static String translatorFontPath(String apkPath) {
        String gamePath = renpyFontPath(apkPath);
        if (gamePath == null || gamePath.isEmpty()) {
            return null;
        }
        int slash = gamePath.lastIndexOf('/');
        String filename = slash >= 0 ? gamePath.substring(slash + 1) : gamePath;
        if (filename.isEmpty()) {
            return null;
        }
        // x- is the APK asset prefix used by the game's unpacker; it is not
        // part of the path Ren'Py resolves inside game/tl.
        String normalizedApkPath = apkPath.replace('\\', '/');
        if (normalizedApkPath.indexOf("assets/") >= 0
                && filename.startsWith("x-") && filename.length() > 2) {
            filename = filename.substring(2);
        }
        return "tl/slgtranslated/" + filename;
    }

    /** Maps an APK font entry to the archive entry copied into the translator bucket. */
    static String translatorFontAssetPath(String apkPath) {
        String gamePath = renpyFontPath(apkPath);
        if (gamePath == null || gamePath.isEmpty()) {
            return null;
        }
        int slash = gamePath.lastIndexOf('/');
        String filename = slash >= 0 ? gamePath.substring(slash + 1) : gamePath;
        if (filename.isEmpty()) {
            return null;
        }
        return "assets/x-game/x-tl/x-slgtranslated/" + filename;
    }

    private static byte[] readArchiveEntry(File apk, String entryName) throws IOException {
        if (apk == null || entryName == null || entryName.isEmpty()) {
            return null;
        }
        String normalized = entryName.replace('\\', '/');
        if (!normalized.startsWith("assets/") || normalized.contains("..")) {
            return null;
        }
        try {
            RenpyResourceLimits.checkPath(normalized);
        } catch (RuntimeException invalidPath) {
            return null;
        }
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(normalized);
            if (entry == null || entry.isDirectory()) {
                return null;
            }
            return readEntry(zip, entry);
        }
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
            java.util.Map<Integer, java.util.List<Integer>> sourceHashOps =
                    collectFontHashAssociations(inflated, ops);
            java.util.Map<Integer, String> changedSources = new java.util.HashMap<>();
            boolean fontKeyPending = false;
            boolean slotChanged = false;
            for (int index = 0; index < ops.size(); index++) {
                String payload = LanguageMenuSupport.stringPayload(inflated, ops, index);
                if (payload != null) {
                    String rewrittenSource = rewriteChineseStyleFontSource(payload, bestFontPath);
                    if (rewrittenSource != null) {
                        changedSources.put(index, rewrittenSource);
                        slotChanged = true;
                        continue;
                    }
                    if ("text_font".equals(payload) || "font".equals(payload)
                            || "font_name".equals(payload)) {
                        fontKeyPending = true;
                    } else if (fontKeyPending && isFontReference(payload)) {
                        changedSources.put(index,
                                rewriteFontReferencePayload(payload, bestFontPath));
                        slotChanged = true;
                        fontKeyPending = false;
                        continue;
                    } else {
                        fontKeyPending = false;
                    }
                }
            }
            if (slotChanged) {
                java.util.Map<Integer, Integer> hashRewrites = new java.util.HashMap<>();
                for (java.util.Map.Entry<Integer, String> entry : changedSources.entrySet()) {
                    java.util.List<Integer> hashes = sourceHashOps.get(entry.getKey());
                    if (hashes == null) {
                        continue;
                    }
                    int hash = renpyHash32(entry.getValue());
                    for (Integer hashIndex : hashes) {
                        hashRewrites.put(hashIndex, hash);
                    }
                }
                ByteArrayOutputStream out = new ByteArrayOutputStream(inflated.length + 64);
                for (int index = 0; index < ops.size(); index++) {
                    int[] op = ops.get(index);
                    String rewrittenSource = changedSources.get(index);
                    if (rewrittenSource != null) {
                        writePickleString(out, rewrittenSource);
                    } else if (hashRewrites.containsKey(index)) {
                        writePickleHash(out, hashRewrites.get(index));
                    } else {
                        // FRAME lengths become stale when the font path length
                        // changes. Omitting optional FRAME opcodes leaves a
                        // valid protocol stream.
                        if (op[0] == 0x95) {
                            continue;
                        }
                        out.write(inflated, op[1], op[2] - op[1]);
                    }
                }
                byte[] rewrittenPickle = out.toByteArray();
                try {
                    RpycStreamValidator.requireValid(rewrittenPickle, "renpy_style_font_rewrite");
                } catch (IOException invalid) {
                    return null;
                }
                rebuilt.add(deflate(rewrittenPickle));
            } else {
                rebuilt.add(compressed);
            }
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

    /** Rewrites the regular font variable used by a game's ordinary Say style. */
    private static byte[] rewriteAlwaysOnThemeFont(byte[] rpyc, String fontPath) {
        if (!startsWith(rpyc, RPC2_MAGIC) || fontPath == null || fontPath.isEmpty()) {
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
            java.util.Map<Integer, java.util.List<Integer>> sourceHashOps =
                    collectFontHashAssociations(inflated, ops);
            java.util.Map<Integer, String> changedSources = new java.util.HashMap<>();
            boolean slotChanged = false;
            for (int index = 0; index < ops.size(); index++) {
                String payload = LanguageMenuSupport.stringPayload(inflated, ops, index);
                String rewrittenSource = rewriteAlwaysOnThemeFontSource(payload, fontPath);
                if (rewrittenSource != null) {
                    changedSources.put(index, rewrittenSource);
                    slotChanged = true;
                    continue;
                }
            }
            if (slotChanged) {
                java.util.Map<Integer, Integer> hashRewrites = new java.util.HashMap<>();
                for (java.util.Map.Entry<Integer, String> entry : changedSources.entrySet()) {
                    java.util.List<Integer> hashes = sourceHashOps.get(entry.getKey());
                    if (hashes == null) {
                        continue;
                    }
                    int hash = renpyHash32(entry.getValue());
                    for (Integer hashIndex : hashes) {
                        hashRewrites.put(hashIndex, hash);
                    }
                }
                ByteArrayOutputStream out = new ByteArrayOutputStream(inflated.length + 64);
                List<Integer> frameOffsets = new ArrayList<>();
                for (int index = 0; index < ops.size(); index++) {
                    int[] op = ops.get(index);
                    String rewrittenSource = changedSources.get(index);
                    if (rewrittenSource != null) {
                        writePickleString(out, rewrittenSource);
                    } else if (hashRewrites.containsKey(index)) {
                        writePickleHash(out, hashRewrites.get(index));
                    } else {
                        if (op[0] == 0x95) {
                            frameOffsets.add(out.size());
                        }
                        out.write(inflated, op[1], op[2] - op[1]);
                    }
                }
                byte[] rewritten = out.toByteArray();
                RpycDialoguePatcher.patchFrameLengths(rewritten, frameOffsets);
                try {
                    RpycStreamValidator.requireValid(rewritten, "renpy_theme_font_rewrite");
                } catch (IOException invalid) {
                    return null;
                }
                rebuilt.add(deflate(rewritten));
                changed = true;
            } else {
                rebuilt.add(compressed);
            }
        }
        if (!changed) {
            return null;
        }
        int dataEnd = 0;
        for (int[] slot : slots) {
            dataEnd = Math.max(dataEnd, slot[1] + slot[2]);
        }
        byte[] trailer = dataEnd < rpyc.length
                ? slice(rpyc, dataEnd, rpyc.length) : new byte[0];
        return rebuildRpc2WithTrailer(slots, rebuilt, trailer);
    }

    private static String rewriteAlwaysOnThemeFontSource(String payload, String fontPath) {
        if (payload == null || fontPath == null || fontPath.isEmpty()
                || !payload.contains("style.say_dialogue.font = regular_font")) {
            return null;
        }
        Matcher matcher = ALWAYS_ON_THEME_FONT_ASSIGNMENT.matcher(payload);
        StringBuffer rewritten = new StringBuffer(payload.length() + 32);
        boolean changed = false;
        while (matcher.find()) {
            String previous = matcher.group(2);
            if (!isFontReference(previous) || previous.equals(fontPath)) {
                continue;
            }
            String replacement = matcher.group(1) + fontPath + matcher.group(3);
            matcher.appendReplacement(rewritten, Matcher.quoteReplacement(replacement));
            changed = true;
        }
        if (!changed) {
            return null;
        }
        matcher.appendTail(rewritten);
        return rewritten.toString();
    }

    private static boolean isFontReference(String value) {
        String lower = unquoteFontReference(value).toLowerCase();
        return lower.endsWith(".ttf") || lower.endsWith(".otf") || lower.endsWith(".ttc");
    }

    private static String unquoteFontReference(String value) {
        if (value == null || value.length() < 2) {
            return value == null ? "" : value;
        }
        char first = value.charAt(0);
        char last = value.charAt(value.length() - 1);
        if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
            return value.substring(1, value.length() - 1);
        }
        return value;
    }

    private static String rewriteFontReferencePayload(String payload, String fontPath) {
        if (payload != null && payload.length() >= 2) {
            char first = payload.charAt(0);
            char last = payload.charAt(payload.length() - 1);
            if (first == '"' && last == '"') {
                return "\"" + fontPath + "\"";
            }
            if (first == '\'' && last == '\'') {
                return "'" + fontPath + "'";
            }
        }
        return fontPath;
    }

    /**
     * Finds the hash field belonging to each serialized PyExpr/PyCode source.
     * The association is derived from the object's constructor/state shape,
     * rather than from a nearby integer, so unrelated AST metadata cannot be
     * mistaken for a cache key.
     */
    private static java.util.Map<Integer, java.util.List<Integer>> collectFontHashAssociations(
            byte[] data, List<int[]> ops) {
        java.util.Map<Integer, java.util.List<Integer>> associations =
                new java.util.HashMap<>();
        for (int source = 0; source < ops.size(); source++) {
            if (LanguageMenuSupport.stringPayload(data, ops, source) == null) {
                continue;
            }
            for (Integer hash : findFontHashesForSource(data, ops, source)) {
                addHashAssociation(associations, source, hash);
            }
        }
        return associations;
    }

    private static void addHashAssociation(
            java.util.Map<Integer, java.util.List<Integer>> associations,
            int sourceIndex, int hashIndex) {
        java.util.List<Integer> hashes = associations.get(sourceIndex);
        if (hashes == null) {
            hashes = new ArrayList<>();
            associations.put(sourceIndex, hashes);
        }
        if (!hashes.contains(hashIndex)) {
            hashes.add(hashIndex);
        }
    }

    private static java.util.List<Integer> findFontHashesForSource(
            byte[] data, List<int[]> ops, int source) {
        java.util.List<Integer> hashes = new ArrayList<>();
        int stateStart = skipMemoize(ops, source + 1);

        // A direct PyCode stores (source, (filename, line), mode, py,
        // hashcode, col_offset). The tuple boundaries identify the fields;
        // no unrelated integer can be selected by position alone.
        int directHash = parseDirectPyCodeHash(ops, stateStart);
        if (directHash >= 0) {
            hashes.add(directHash);
            return hashes;
        }

        // A PyCode may store a PyExpr as its source. The inner PyExpr has
        // (source, filename, line, py, hashcode, col_offset), then REDUCE;
        // the enclosing PyCode repeats the hashcode in its own state.
        int[] pyExprState = parsePyExprState(ops, stateStart);
        if (pyExprState == null) {
            return hashes;
        }
        hashes.add(pyExprState[0]);
        int reduce = skipMemoize(ops, pyExprState[1] + 1);
        if (reduce >= ops.size() || ops.get(reduce)[0] != 0x52) { // REDUCE
            return hashes;
        }
        int outerState = skipMemoize(ops, reduce + 1);
        int outerHash = parseDirectPyCodeHash(ops, outerState);
        if (outerHash >= 0) {
            addHashAssociation(hashes, outerHash);
        }
        return hashes;
    }

    private static int parseDirectPyCodeHash(List<int[]> ops, int stateStart) {
        int index = skipMemoize(ops, stateStart);
        if (index < 0 || index >= ops.size()) {
            return -1;
        }
        // location = (filename, linenumber)
        if (!isReferenceOrStringOpcode(ops.get(index)[0])) {
            return -1;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return -1;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || ops.get(index)[0] != 0x86) { // TUPLE2
            return -1;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isReferenceOrStringOpcode(ops.get(index)[0])) {
            return -1;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return -1;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return -1;
        }
        int hashIndex = index;
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return -1;
        }
        index = skipMemoize(ops, index + 1);
        return index < ops.size() && ops.get(index)[0] == 0x74 ? hashIndex : -1;
    }

    private static int[] parsePyExprState(List<int[]> ops, int stateStart) {
        int index = skipMemoize(ops, stateStart);
        if (index >= ops.size() || !isReferenceOrStringOpcode(ops.get(index)[0])) {
            return null;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return null;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return null;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return null;
        }
        int hashIndex = index;
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || !isIntegerOpcode(ops.get(index)[0])) {
            return null;
        }
        index = skipMemoize(ops, index + 1);
        if (index >= ops.size() || ops.get(index)[0] != 0x74) { // TUPLE
            return null;
        }
        return new int[]{hashIndex, index};
    }

    private static int skipMemoize(List<int[]> ops, int index) {
        while (index < ops.size() && ops.get(index)[0] == 0x94) { // MEMOIZE
            index++;
        }
        return index;
    }

    private static boolean isReferenceOrStringOpcode(int opcode) {
        return opcode == 0x68 || opcode == 0x6a
                || opcode == 0x8c || opcode == 0x58 || opcode == 0x8d;
    }

    private static void addHashAssociation(java.util.List<Integer> hashes, int hashIndex) {
        if (!hashes.contains(hashIndex)) {
            hashes.add(hashIndex);
        }
    }

    private static boolean isIntegerOpcode(int opcode) {
        return opcode == 0x4a || opcode == 0x4b || opcode == 0x4d
                || opcode == 0x8a || opcode == 0x8b;
    }

    private static int renpyHash32(String value) {
        long hash = 0x811c9dc5L;
        for (int index = 0; index < value.length();) {
            int codePoint = value.codePointAt(index);
            hash ^= codePoint;
            hash = (hash * 0x01000193L) & 0xffffffffL;
            index += Character.charCount(codePoint);
        }
        return (int) hash;
    }

    private static void writePickleHash(ByteArrayOutputStream out, int value) {
        long unsigned = value & 0xffffffffL;
        int length = unsigned < 0x80000000L ? 4 : 5;
        out.write(0x8a);
        out.write(length);
        for (int index = 0; index < length; index++) {
            out.write(index < 4 ? (int) (unsigned >>> (index * 8)) : 0);
        }
    }

    private static boolean isChineseFontReference(String value) {
        if (!isFontReference(value)) {
            return false;
        }
        String lower = value.toLowerCase();
        return lower.contains("/chinese/") || lower.contains("/schinese/")
                || lower.startsWith("chinese/") || lower.startsWith("schinese/");
    }

    /**
     * The game's x-style source is stored as one BINUNICODE payload rather than
     * separate pickle key/value strings. Rewrite only known font assignments in
     * that source fragment; malformed or unrelated payloads remain untouched.
     */
    private static String rewriteChineseStyleFontSource(String payload, String bestFontPath) {
        if (payload == null || bestFontPath == null || bestFontPath.isEmpty()
                || (!payload.contains("text_font") && !payload.contains("system_font"))) {
            return null;
        }
        Matcher matcher = CHINESE_STYLE_FONT_ASSIGNMENT.matcher(payload);
        StringBuffer rewritten = new StringBuffer(payload.length() + 64);
        boolean changed = false;
        while (matcher.find()) {
            String previous = matcher.group(2);
            if (!isChineseFontReference(previous)) {
                continue;
            }
            String replacement = matcher.group(1) + bestFontPath + matcher.group(3);
            matcher.appendReplacement(rewritten, Matcher.quoteReplacement(replacement));
            changed = true;
        }
        if (!changed) {
            return null;
        }
        matcher.appendTail(rewritten);
        return rewritten.toString();
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
                if (len < 0 || start > n || len > n - start) {
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
            } else if (b == 0x54 || b == 0x42) { // BINSTRING / BINBYTES
                if (pos + 5 > n) {
                    break;
                }
                int len = le32(data, pos + 1);
                int start = pos + 5;
                if (len < 0 || start > n || len > n - start) {
                    break;
                }
                pos = start + len;
                continue;
            } else if (b == 0x55 || b == 0x43) { // SHORT_BINSTRING / SHORT_BINBYTES
                if (pos + 2 > n) {
                    break;
                }
                int len = data[pos + 1] & 0xff;
                int start = pos + 2;
                if (len > n - start) {
                    break;
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
