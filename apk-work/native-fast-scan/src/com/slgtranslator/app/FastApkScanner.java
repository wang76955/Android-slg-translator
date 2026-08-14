package com.slgtranslator.app;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class FastApkScanner {
    static final long SCAN_TIMEOUT_MS = 60_000L;
    static final int MAX_CACHE_ENTRIES = 2;
    static final int MAX_CACHED_APK_ENTRIES = 50_000;
    private static final int COPY_BUFFER_SIZE = 1024 * 1024;
    private static final Set<String> RENPY_SCRIPT_EXTENSIONS = Collections.unmodifiableSet(
        new HashSet<>(Arrays.asList("rpym", "rpymc", "rpy", "rpyc"))
    );
    private static final Set<String> TEXT_EXTENSIONS = Collections.unmodifiableSet(
        new HashSet<>(Arrays.asList(
            "json", "xml", "txt", "csv", "lua", "yaml", "yml",
            "properties", "cfg", "html", "htm", "md", "ini",
            "rpym", "rpymc", "rpy", "rpyc", "strings"
        ))
    );
    private static final Map<String, ScanResult> CACHE = Collections.synchronizedMap(
        new LinkedHashMap<String, ScanResult>(MAX_CACHE_ENTRIES + 1, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, ScanResult> eldest) {
                return size() > MAX_CACHE_ENTRIES;
            }
        }
    );

    private FastApkScanner() {}

    public static void clearCache() {
        synchronized (CACHE) {
            CACHE.clear();
        }
    }

    public static JSObject cacheStats() {
        int entries = 0;
        long cachedApkEntryCount = 0L;
        synchronized (CACHE) {
            entries = CACHE.size();
            for (ScanResult result : CACHE.values()) {
                if (result != null && result.entries != null) {
                    cachedApkEntryCount += result.entries.size();
                }
            }
        }
        return new JSObject()
                .put("entries", entries)
                .put("cachedApkEntryCount", cachedApkEntryCount);
    }

    private static void cacheResult(String key, ScanResult result) {
        if (key == null || result == null || result.entries == null
                || result.entries.size() > MAX_CACHED_APK_ENTRIES) {
            return;
        }
        synchronized (CACHE) {
            CACHE.put(key, result);
        }
    }

    /**
     * Single scanner entry point for exact-old occurrence coverage.  The UI
     * supplies only validator-approved translations; cached failures stay in
     * rejectedTranslations and therefore cannot be counted as translated.
     */
    public static TranslationCoverageReport coverageReport(
            List<RenpyTextRecord> exactOldOccurrences,
            Map<String, String> validatorApprovedTranslations,
            Set<String> rejectedTranslations,
            Map<String, List<String>> candidateTranslations,
            Set<String> uncertainTranslations,
            Map<String, String> classificationReasons) {
        return TranslationCoverageReport.build(
                exactOldOccurrences,
                validatorApprovedTranslations,
                rejectedTranslations,
                candidateTranslations,
                uncertainTranslations,
                classificationReasons);
    }

    /** Fixed Chinese/punctuation baseline used before any model call. */
    static RenpyFontSupport.FontReport fontPreflight(Context context, File apk) {
        return RenpyFontSupport.inspect(
                context, apk, RenpyFontSupport.defaultRequiredCodePoints());
    }

    private static JSObject fontReportJson(RenpyFontSupport.FontReport report) {
        JSObject result = new JSObject();
        JSArray candidates = new JSArray();
        for (String candidate : report.candidateFonts) {
            candidates.put(candidate);
        }
        JSArray missing = new JSArray();
        for (Integer codePoint : report.missingCodePoints) {
            missing.put(codePoint);
        }
        JSArray warnings = new JSArray();
        for (String warning : report.warnings) {
            warnings.put(warning);
        }
        result.put("candidateFonts", candidates);
        result.put("bestFontPath", report.bestFontPath);
        result.put("requiredCount", report.requiredCount);
        result.put("coveredCount", report.coveredCount);
        result.put("missingCodePoints", missing);
        result.put("hasChineseStyleBucket", report.hasChineseStyleBucket);
        result.put("hasEastAsianLineBreakEvidence", report.hasEastAsianLineBreakEvidence);
        result.put("code", report.failureCode());
        result.put("warnings", warnings);
        return result;
    }

    /**
     * Reads one APK entry and, for Ren'Py compiled scripts, returns the
     * structurally extracted user-visible texts as RPYC_STRING lines so the
     * UI can translate dialogue, menu choices and screen text reliably.
     */
    public static void readRenpyTexts(Context context, PluginCall call) {
        String apkUri = call.getString("apkUri");
        if (apkUri == null || apkUri.isEmpty()) {
            apkUri = call.getString("uri");
        }
        String entryName = call.getString("entryName");
        if (apkUri == null || entryName == null || apkUri.isEmpty() || entryName.isEmpty()) {
            call.reject("apkUri and entryName required");
            return;
        }
        try {
            RenpyResourceLimits.checkPath(entryName.replace("!/", "/"));
            InstalledApkSet apkSet = installedApkSet(Uri.parse(apkUri), call);
            File apk = findApkForEntry(apkSet, entryName, call.getString("sourceApk"));
            if (apk == null) {
                call.reject("Entry not found in APK set: " + entryName);
                return;
            }
            String sourceOwner = sourceOwner(apkSet, apk);
            String content = "";
            String fileType = "unknown";
            RenpyFontSupport.FontReport fontReport = null;
            RenpyCompatibilityReport compatibilityReport = null;
            JSArray renpyRecords = new JSArray();
            List<RenpyTextRecord> exactOldOccurrences = new ArrayList<>();
            Map<String, String> coverageClassifications = new LinkedHashMap<>();
            try (ZipFile zip = new ZipFile(apk)) {
                byte[] bytes = readEntryData(zip, entryName, Long.MAX_VALUE);
                if (bytes == null) {
                    call.reject("Entry not found: " + entryName);
                    return;
                }
                String lower = entryName.toLowerCase(Locale.ROOT);
                if (lower.endsWith(".rpyc") || lower.endsWith(".rpymc")) {
                    fontReport = mergeFontReportsForApkSet(context, apkSet);
                    boolean translationBucket = lower.contains("/x-tl/")
                            || lower.contains("/tl/");
                    List<RenpyTextRecord> records;
                    if (bytes.length <= 8 * 1024 * 1024) {
                        records = RpycTextExtractor.extractRecords(
                                bytes, entryName, translationBucket);
                    } else {
                        try (RpycSlotSource source = RpycSlotSource.fromBytes(context, bytes, entryName)) {
                            records = RpycStreamingExtractor.extractRecords(
                                    source, entryName, translationBucket);
                        }
                    }
                    RpycCompatibility.Report rpyc = RpycCompatibility.inspect(bytes);
                    compatibilityReport = RenpyPreflight.inspect(context,
                            new RenpyPreflight.SourceSet(
                                    entryName,
                                    rpyc,
                                    0,
                                    0,
                                    Collections.<String>emptyList(),
                                    "none",
                                    fontReport,
                                    0,
                                    records.size(),
                                    0));
                    exactOldOccurrences.addAll(records);
                    for (RenpyTextRecord record : records) {
                        renpyRecords.put(renpyRecordJson(record, sourceOwner));
                        String classification = coverageClassification(record);
                        if (classification != null) {
                            coverageClassifications.put(record.sourcePath + "\t" + record.text, classification);
                        }
                    }
                    fileType = "rpyc";
                } else {
                    content = new String(bytes, StandardCharsets.UTF_8);
                    int dot = entryName.lastIndexOf('.');
                    fileType = dot >= 0 ? entryName.substring(dot + 1).toLowerCase(Locale.ROOT) : "unknown";
                }
            }
            JSObject result = new JSObject();
            result.put("content", content);
            result.put("fileType", fileType);
            result.put("sourceApk", apk.getName());
            result.put("apkRole", apk.equals(apkSet.baseApk) ? "base" : "split");
            result.put("splitCount", apkSet.splitApks.size());
            result.put("renpyRecords", renpyRecords);
            JSObject classificationJson = new JSObject();
            for (Map.Entry<String, String> entry : coverageClassifications.entrySet()) {
                classificationJson.put(entry.getKey(), entry.getValue());
            }
            result.put("coverageClassifications", classificationJson);
            TranslationCoverageReport initialCoverage = coverageReport(
                    exactOldOccurrences,
                    Collections.<String, String>emptyMap(),
                    Collections.<String>emptySet(),
                    Collections.<String, List<String>>emptyMap(),
                    Collections.<String>emptySet(),
                    coverageClassifications);
            result.put("coverageReport", initialCoverage.toSanitizedJson());
            result.put("coverageOccurrenceCount", initialCoverage.occurrenceCount);
            result.put("coverageUniqueSourceCount", initialCoverage.uniqueSourceCount);
            result.put("coverageGate", initialCoverage.shouldBlockCompleteBuild() ? "blocked" : "clear");
            if (fontReport != null) {
                result.put("fontReport", fontReportJson(fontReport));
                result.put("fontGate", fontReport.isComplete() ? "clear" : "blocked");
            }
            if (compatibilityReport != null) {
                result.put("compatibilityReport", compatibilityReportJson(compatibilityReport));
                result.put("compatibilityGate", compatibilityGate(compatibilityReport));
            }
            EngineCapabilities caps = compatibilityReport == null
                    ? RenpyEngineAdapter.INSTANCE.capabilities(null)
                    : RenpyEngineAdapter.INSTANCE.capabilities(compatibilityReport);
            result.put("adapterId", "renpy");
            result.put("workflow", caps.workflow.name());
            result.put("capabilities", capabilitiesJson(caps));
            result.put("projectFingerprint", projectFingerprintForApkSet(context, apkSet));
            result.put("recordSchemaVersion", 1);
            result.put("translationGate", caps.canTranslate ? "clear" : "blocked");
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("Failed to read entry: " + (message == null ? e.toString() : message));
        }
    }

    /**
     * Structured-text entry reader: detects a first-release codec for the
     * entry, extracts its records and reports the structured-text adapter
     * contract (workflow {@code PATCHABLE_VERIFIED} only when a codec
     * accepted the content).
     */
    public static void readStructuredTexts(Context context, PluginCall call) {
        String apkUri = call.getString("apkUri");
        if (apkUri == null || apkUri.isEmpty()) {
            apkUri = call.getString("uri");
        }
        String entryName = call.getString("entryName");
        if (apkUri == null || entryName == null || apkUri.isEmpty() || entryName.isEmpty()) {
            call.reject("apkUri and entryName required");
            return;
        }
        try {
            RenpyResourceLimits.checkPath(entryName.replace("!/", "/"));
            InstalledApkSet apkSet = installedApkSet(Uri.parse(apkUri), call);
            File apk = findApkForEntry(apkSet, entryName, call.getString("sourceApk"));
            if (apk == null) {
                call.reject("Entry not found in APK set: " + entryName);
                return;
            }
            String sourceOwner = sourceOwner(apkSet, apk);
            StructuredTextAdapter adapter = StructuredTextWriter.defaultAdapter();
            JSArray recordsJson = new JSArray();
            try (ZipFile zip = new ZipFile(apk)) {
                byte[] bytes = readEntryData(zip, entryName, Long.MAX_VALUE);
                if (bytes == null) {
                    call.reject("Entry not found: " + entryName);
                    return;
                }
                StructuredTextAdapter.AssetCodec codec = adapter.codecFor(entryName, bytes);
                if (codec == null) {
                    JSObject unsupported = new JSObject()
                            .put("adapterId", StructuredTextAdapter.ADAPTER_ID)
                            .put("workflow", "TRANSLATABLE_NO_PATCH")
                            .put("capabilities", new JSObject()
                                    .put("canDetect", true)
                                    .put("canExtractStructured", false)
                                    .put("canTranslate", false)
                                    .put("canWritePatch", false)
                                    .put("canActivate", false))
                            .put("translationGate", "blocked")
                            .put("reasonCode", "structured_extraction_unavailable");
                    call.resolve(unsupported);
                    return;
                }
                List<StructuredTextRecord> records = codec.extract(
                        sourceOwner, entryName, bytes);
                for (StructuredTextRecord record : records) {
                    recordsJson.put(new JSObject()
                            .put("recordId", record.recordId)
                            .put("sourceOwner", record.sourceOwner)
                            .put("sourcePath", record.sourcePath)
                            .put("format", record.format)
                            .put("keyPath", record.keyPath)
                            .put("sourceText", record.sourceText)
                            .put("valueType", record.valueType)
                            .put("index", record.index));
                }
            }
            JSObject result = new JSObject()
                    .put("adapterId", StructuredTextAdapter.ADAPTER_ID)
                    .put("workflow", "PATCHABLE_VERIFIED")
                    .put("capabilities", new JSObject()
                            .put("canDetect", true)
                            .put("canExtractStructured", true)
                            .put("canTranslate", true)
                            .put("canWritePatch", true)
                            .put("canActivate", true))
                    .put("translationGate", "clear")
                    .put("records", recordsJson)
                    .put("recordSchemaVersion", 1);
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("Failed to read structured entry: "
                    + (message == null ? e.toString() : message));
        }
    }

    private static JSObject renpyRecordJson(RenpyTextRecord record, String sourceOwner) {
        String owner = sourceOwner == null || sourceOwner.isEmpty() ? "base" : sourceOwner;
        String sourcePath = normalizedRecordSourcePath(owner, record.sourcePath);
        JSObject result = new JSObject()
                .put("text", record.text)
                .put("kind", record.kind.name())
                .put("speaker", record.speaker)
                .put("identifier", record.identifier)
                .put("sourcePath", sourcePath)
                .put("sourceLine", record.sourceLine)
                .put("occurrence", record.occurrence)
                .put("coverageCertain", record.coverageCertain)
                .put("recordId", recordId("renpy", owner, record))
                .put("sourceOwner", owner)
                .put("resourceType", record.kind.name())
                .put("sourceKey", record.identifier)
                .put("recordSchemaVersion", 1);
        String classification = coverageClassification(record);
        if (classification != null) {
            result.put("coverageClassification", classification);
        }
        return result;
    }

    private static String sourceOwner(InstalledApkSet apkSet, File apk) {
        if (apkSet == null || apk == null || apk.equals(apkSet.baseApk)) {
            return "base";
        }
        for (int index = 0; index < apkSet.splitApks.size(); index++) {
            if (apk.equals(apkSet.splitApks.get(index))) {
                String splitName = apkSet.splitNameAt(index);
                if (splitName.endsWith(".apk")) {
                    splitName = splitName.substring(0, splitName.length() - 4);
                }
                return "split:" + splitName;
            }
        }
        return "split:unknown";
    }

    private static String normalizedRecordSourcePath(String sourceOwner, String sourcePath) {
        String value = sourcePath == null ? "" : sourcePath.replace('\\', '/');
        if (value.contains("!/")) {
            return "archive:" + sourceOwner + "!/" + value;
        }
        return value;
    }

    /**
     * Only paths that explicitly identify developer/error/optional buckets are
     * excluded.  Ordinary x-common story/UI files remain in coverage by
     * default, even when their record kind is a custom statement.
     */
    private static String coverageClassification(RenpyTextRecord record) {
        if (record == null || record.sourcePath == null) {
            return null;
        }
        String path = record.sourcePath.replace('\\', '/').toLowerCase(Locale.ROOT);
        if (!(path.contains("/x-common/") || path.startsWith("x-common/"))) {
            return null;
        }
        if (path.contains("/debug") || path.contains("/developer") || path.contains("/console")) {
            return "developer_console";
        }
        if (path.contains("/internal") || path.contains("/error")) {
            return "internal_error";
        }
        if (path.contains("/expired")) {
            return "expired_text";
        }
        if (path.contains("/settings") || path.contains("/optional")) {
            return "settings_optional";
        }
        return null;
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

    private static File findApkForEntry(InstalledApkSet apkSet, String entryName,
                                        String preferredSourceApk) throws IOException {
        // A single content:// APK is materialized under a stable hash name.
        // The scan metadata may still carry the DocumentsUI display/source
        // name, so do not reject that harmless name drift when there are no
        // split APKs. Split sets remain strict: a stale sourceApk must fail
        // closed instead of reading a similarly named entry from the wrong
        // split.
        boolean allowSingleBaseNameDrift = apkSet.splitApks.isEmpty();
        for (File apk : apkSet.allApks()) {
            if (preferredSourceApk != null && !preferredSourceApk.isEmpty()
                    && !preferredSourceApk.equals(apk.getName())
                    && !allowSingleBaseNameDrift) {
                continue;
            }
            try (ZipFile zip = new ZipFile(apk)) {
                if (readEntryData(zip, entryName, Long.MAX_VALUE) != null) {
                    return apk;
                }
            }
        }
        if (preferredSourceApk != null && !preferredSourceApk.isEmpty()
                && !allowSingleBaseNameDrift) {
            throw new IOException("split metadata sourceApk is not part of the selected set");
        }
        return null;
    }

    private static byte[] readEntryBytes(ZipFile zip, ZipEntry entry) throws IOException {
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

    public static void scanAsync(
        Context context,
        String uriText,
        Object plugin,
        PluginCall call
    ) {
        new Thread(() -> {
            try {
                JSObject response = scan(context, Uri.parse(uriText), plugin, call);
                call.resolve(response);
            } catch (Throwable error) {
                String message = error.getMessage();
                String rejection = "Failed to read APK: " + (
                    message == null ? error.getClass().getSimpleName() : message
                );
                call.reject(rejection);
            }
        }, "slg-apk-scan").start();
    }

    private static JSObject scan(Context context, Uri uri, Object plugin) throws Exception {
        return scan(context, uri, plugin, null);
    }

    private static JSObject scan(Context context, Uri uri, Object plugin, PluginCall call) throws Exception {
        long startedAt = SystemClock.elapsedRealtime();
        long deadline = startedAt + SCAN_TIMEOUT_MS;
        Metadata metadata = readMetadata(context.getContentResolver(), uri);
        InstalledApkSet apkSet = null;
        File localBase = fileFrom(uri == null ? null : uri.toString());
        if ((localBase != null && localBase.isFile()) || hasSplitUris(call)) {
            apkSet = installedApkSet(uri, call);
        }
        if (apkSet != null) {
            for (File selected : apkSet.allApks()) {
                TranslationCompiler.assertPristineSource(selected);
            }
        } else if (localBase != null && localBase.isFile()) {
            TranslationCompiler.assertPristineSource(localBase);
        }
        String cacheKey = sha256(apkSet == null
                ? uri + "|" + metadata.displayName + "|" + metadata.size + "|" + metadata.lastModified
                : apkSetCacheKey(apkSet, metadata));
        ScanResult cached;
        synchronized (CACHE) {
            cached = CACHE.get(cacheKey);
        }
        if (cached != null) {
            return toResponse(cached, SystemClock.elapsedRealtime() - startedAt, true);
        }

        if (apkSet != null && !apkSet.splitApks.isEmpty()) {
            ScanResult result = scanApkSet(apkSet, plugin, deadline, context);
            synchronized (CACHE) {
                cacheResult(cacheKey, result);
            }
            return toResponse(result, SystemClock.elapsedRealtime() - startedAt, false);
        }

        ContentResolver resolver = context.getContentResolver();
        ScanResult result = null;
        try (ParcelFileDescriptor descriptor = resolver.openFileDescriptor(uri, "r")) {
            if (descriptor != null) {
                result = scanSeekableDescriptor(descriptor, plugin, deadline, context);
            }
        } catch (Exception ignored) {
            // Cloud-backed and virtual document providers may not expose a
            // seekable descriptor. Those providers use the bounded copy path.
        }
        if (result != null) {
            synchronized (CACHE) {
                cacheResult(cacheKey, result);
            }
            return toResponse(result, SystemClock.elapsedRealtime() - startedAt, false);
        }

        File temp = File.createTempFile("slg-apk-scan-", ".apk", context.getCacheDir());
        try {
            copyCompressedApk(resolver, uri, temp, deadline);
            result = enumerateCentralDirectory(temp, plugin, deadline, context, false);
            synchronized (CACHE) {
                cacheResult(cacheKey, result);
            }
            return toResponse(result, SystemClock.elapsedRealtime() - startedAt, false);
        } finally {
            if (temp.exists() && !temp.delete()) {
                temp.deleteOnExit();
            }
        }
    }

    private static InstalledApkSet installedApkSet(Uri uri, PluginCall call) {
        File base = fileFrom(uri == null ? null : uri.toString());
        if (base == null || !base.isFile()) {
            throw new IllegalArgumentException("base APK is missing or unreadable");
        }
        List<String> splitUris = new ArrayList<>();
        String packageName = "unknown";
        long versionCode = -1L;
        List<String> splitNames = new ArrayList<>();
        if (call != null) {
            String requestedPackage = call.getString("packageName");
            if (requestedPackage != null && !requestedPackage.trim().isEmpty()) {
                packageName = requestedPackage.trim();
            }
            String requestedVersion = call.getString("versionCode");
            if (requestedVersion != null && !requestedVersion.trim().isEmpty()) {
                try {
                    versionCode = Long.parseLong(requestedVersion.trim());
                } catch (NumberFormatException error) {
                    throw new IllegalArgumentException("split metadata versionCode is invalid");
                }
            }
            JSArray values = call.getArray("splitUris");
            JSArray names = call.getArray("splitNames");
            if (values != null) {
                for (int index = 0; index < values.length(); index++) {
                    String value = arrayString(values, index);
                    if (value == null || value.trim().isEmpty()) {
                        throw new IllegalArgumentException("split metadata contains an empty URI");
                    }
                    splitUris.add(value);
                    String splitName = arrayString(names, index);
                    splitNames.add(splitName);
                }
            }
        }
        return InstalledApkSet.fromUris(base.getAbsolutePath(), splitUris, packageName,
                versionCode, splitNames);
    }

    private static String arrayString(JSArray array, int index) {
        if (array == null) return "";
        Object value = array.opt(index);
        if (value == null) return "";
        String text = String.valueOf(value);
        return "null".equals(text) ? "" : text;
    }

    private static boolean hasSplitUris(PluginCall call) {
        if (call == null) return false;
        JSArray values = call.getArray("splitUris");
        return values != null && values.length() > 0;
    }

    private static String apkSetCacheKey(InstalledApkSet apkSet, Metadata baseMetadata) {
        StringBuilder key = new StringBuilder(apkSet.packageName)
                .append('|').append(apkSet.versionCode)
                .append('|').append(apkSet.baseApk.getAbsolutePath())
                .append('|').append(baseMetadata.displayName).append('|')
                .append(baseMetadata.size).append('|').append(baseMetadata.lastModified);
        for (File split : apkSet.splitApks) {
            key.append('|').append(split.getAbsolutePath()).append('|')
                    .append(split.length()).append('|').append(split.lastModified());
        }
        return key.toString();
    }

    /** Scan each ZIP independently, then merge only its central-directory metadata. */
    static ScanResult scanApkSet(InstalledApkSet apkSet, Object plugin,
                                 long deadline, Context context) throws Exception {
        List<ApkEntry> merged = new ArrayList<>();
        List<ApkEntry> mergedIdentity = new ArrayList<>();
        Map<String, ApkEntry> byName = new LinkedHashMap<>();
        ScanResult baseResult = null;
        List<String> languages = new ArrayList<>();
        String menuType = "none";
        int rpaCount = 0;
        RpycCompatibility.Report bestCompatibility = null;
        RenpyCompatibilityReport bestReport = null;
        String bestTemplatePath = null;
        String bestTemplateSource = null;
        List<RenpyFontSupport.FontReport> fontReports = new ArrayList<>();
        List<String> fontReportSources = new ArrayList<>();
        validateApkSetMetadata(context, apkSet);
        for (int index = 0; index < apkSet.allApks().size(); index++) {
            ensureBeforeDeadline(deadline);
            File apk = apkSet.allApks().get(index);
            ScanResult current = enumerateCentralDirectory(
                    apk, plugin, deadline, context, index > 0);
            if (index == 0) {
                baseResult = current;
            }
            if (!"unknown".equals(apkSet.packageName)
                    && current.packageName != null && !current.packageName.isEmpty()
                    && !apkSet.packageName.equals(current.packageName)) {
                throw new IOException("split metadata packageName mismatch in " + apk.getName());
            }
            for (String language : current.renpyLanguages) {
                if (!languages.contains(language)) languages.add(language);
            }
            if ("none".equals(menuType) && !"none".equals(current.renpyMenuType)) {
                menuType = current.renpyMenuType;
            }
            rpaCount += current.rpaCount;
            if (current.compatibilityReport != null && current.compatibilityReport.font != null) {
                fontReports.add(current.compatibilityReport.font);
                fontReportSources.add(apk.getName());
            }
            if (current.compatibility != null && current.compatibilityReport != null) {
                String templatePath = current.compatibilityReport.templatePath;
                String sourceKey = apk.getName() + "!/" + templatePath;
                if (bestCompatibility == null
                        || isBetterTemplate(templatePath, sourceKey, bestTemplatePath, bestTemplateSource)) {
                    bestCompatibility = current.compatibility;
                    bestReport = current.compatibilityReport;
                    bestTemplatePath = templatePath;
                    bestTemplateSource = sourceKey;
                }
            }
            String owner = index == 0 ? "base" : "split:" + stripApkSuffix(apkSet.splitNameAt(index - 1));
            for (ApkEntry entry : current.entries) {
                ApkEntry sourced = entry.withSource(apk.getName(), index == 0 ? "base" : "split", owner);
                if (!byName.containsKey(sourced.name)) {
                    byName.put(sourced.name, sourced);
                    merged.add(sourced);
                } else {
                    byName.get(sourced.name).duplicateSourceApks.add(sourced.sourceApk);
                }
            }
            for (ApkEntry entry : current.identityEntries) {
                mergedIdentity.add(entry.withSource(apk.getName(), index == 0 ? "base" : "split", owner));
            }
        }
        if (baseResult == null) {
            throw new IOException("split metadata has no base APK");
        }
        RenpyFontSupport.FontReport mergedFont = mergeFontReports(fontReports, fontReportSources);
        RenpyCompatibilityReport report = bestReport;
        if (report != null) {
            report = new RenpyCompatibilityReport(
                    report.supportLevel, report.activationStrategy, report.templatePath,
                    bestCompatibility, rpaCount, apkSet.splitApks.size(), languages,
                    menuType, mergedFont, report.uniqueTextCount,
                    report.occurrenceCount, report.collisionCount, report.verificationLevel,
                    report.issues);
        }
        return new ScanResult(merged, baseResult.packageName, languages, menuType,
                bestCompatibility, report, rpaCount, apkSet.splitApks.size(),
                mergedIdentity, apkSet.versionCode >= 0 ? apkSet.versionCode : baseResult.versionCode);
    }

    private static boolean isBetterTemplate(String candidatePath, String candidateSource,
                                            String currentPath, String currentSource) {
        int candidatePriority = TranslationCompiler.templatePriority(candidatePath);
        int currentPriority = currentPath == null
                ? Integer.MAX_VALUE : TranslationCompiler.templatePriority(currentPath);
        if (candidatePriority != currentPriority) {
            return candidatePriority < currentPriority;
        }
        if (currentSource == null) return true;
        return candidateSource.compareToIgnoreCase(currentSource) < 0;
    }

    private static RenpyFontSupport.FontReport mergeFontReports(
            List<RenpyFontSupport.FontReport> fontReports,
            List<String> fontReportSources) {
        if (fontReports == null || fontReports.isEmpty()) return null;
        List<String> candidates = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        Set<Integer> missingAcrossSet = null;
        int expectedRequiredCount = fontReports.get(0).requiredCount;
        boolean requiredSetMismatch = false;
        RenpyFontSupport.FontReport best = null;
        String bestSource = "";
        for (int index = 0; index < fontReports.size(); index++) {
            RenpyFontSupport.FontReport report = fontReports.get(index);
            String source = index < fontReportSources.size() ? fontReportSources.get(index) : "split-" + index;
            for (String candidate : report.candidateFonts) {
                String qualified = source + "!/" + candidate;
                if (!candidates.contains(qualified)) candidates.add(qualified);
            }
            for (String warning : report.warnings) {
                if (!warnings.contains(warning)) warnings.add(warning);
            }
            Set<Integer> missingInReport = new LinkedHashSet<>(report.missingCodePoints);
            if (missingAcrossSet == null) {
                missingAcrossSet = missingInReport;
            } else if (report.requiredCount == expectedRequiredCount) {
                // Each APK contributes fonts visible to the same loader namespace.
                // A code point is still missing only when every APK's best candidate
                // reports it as missing.
                missingAcrossSet.retainAll(missingInReport);
            } else {
                warnings.add("font_preflight_required_set_mismatch");
                requiredSetMismatch = true;
            }
            if (best == null || report.coveredCount > best.coveredCount
                    || (report.coveredCount == best.coveredCount
                    && source.compareToIgnoreCase(bestSource) < 0)) {
                best = report;
                bestSource = source;
            }
        }
        if (best == null) return null;
        String bestPath = best.bestFontPath == null || best.bestFontPath.isEmpty()
                ? "" : bestSource + "!/" + best.bestFontPath;
        List<Integer> missing = new ArrayList<>(missingAcrossSet == null
                ? best.missingCodePoints : missingAcrossSet);
        int requiredCount = requiredSetMismatch
                ? Math.max(expectedRequiredCount, best.requiredCount) : expectedRequiredCount;
        int coveredCount = Math.max(0, requiredCount - missing.size());
        if (requiredSetMismatch) {
            coveredCount = Math.min(coveredCount, best.coveredCount);
        }
        return new RenpyFontSupport.FontReport(
                candidates, bestPath, requiredCount, coveredCount,
                missing,
                hasChineseStyleBucket(fontReports),
                hasEastAsianLineBreakEvidence(fontReports),
                warnings);
    }

    private static RenpyFontSupport.FontReport mergeFontReportsForApkSet(
            Context context, InstalledApkSet apkSet) {
        List<RenpyFontSupport.FontReport> reports = new ArrayList<>();
        List<String> sources = new ArrayList<>();
        for (File source : apkSet.allApks()) {
            reports.add(fontPreflight(context, source));
            sources.add(source.getName());
        }
        return mergeFontReports(reports, sources);
    }

    private static boolean hasChineseStyleBucket(
            List<RenpyFontSupport.FontReport> reports) {
        for (RenpyFontSupport.FontReport report : reports) {
            if (report.hasChineseStyleBucket) return true;
        }
        return false;
    }

    private static boolean hasEastAsianLineBreakEvidence(
            List<RenpyFontSupport.FontReport> reports) {
        for (RenpyFontSupport.FontReport report : reports) {
            if (report.hasEastAsianLineBreakEvidence) return true;
        }
        return false;
    }

    private static void validateApkSetMetadata(Context context, InstalledApkSet apkSet)
            throws IOException {
        if (apkSet == null || apkSet.baseApk == null || apkSet.splitApks == null) {
            throw new IOException("split metadata has no complete APK set");
        }
        if (context == null || context.getPackageManager() == null) {
            if (!apkSet.splitApks.isEmpty()) {
                throw new IOException("split metadata parser is unavailable; refusing base-only scan");
            }
            return;
        }
        try {
            Method parser = context.getPackageManager().getClass().getMethod(
                    "getPackageArchiveInfo", String.class, int.class);
            List<File> all = apkSet.allApks();
            Object baseInfo = parser.invoke(context.getPackageManager(), apkSet.baseApk.getAbsolutePath(), 0);
            if (baseInfo == null) throw new IOException("split metadata base manifest is unreadable");
            String basePackage = stringField(baseInfo, "packageName");
            long baseVersion = versionField(baseInfo);
            if (!"unknown".equals(apkSet.packageName) && !apkSet.packageName.equals(basePackage)) {
                throw new IOException("split metadata packageName mismatch in base APK");
            }
            for (int index = 1; index < all.size(); index++) {
                File split = all.get(index);
                Object splitInfo;
                try {
                    splitInfo = parser.invoke(context.getPackageManager(), split.getAbsolutePath(), 0);
                } catch (Exception parseError) {
                    if (isSplitArchiveParserLimitation(parseError)) {
                        // Some Android releases reject a standalone split with
                        // "Expected base APK". The package manager metadata
                        // already supplied package/version/splitName; keep
                        // those checks and continue scanning the split ZIP.
                        continue;
                    }
                    throw parseError;
                }
                if (splitInfo == null) {
                    throw new IOException("split metadata manifest is unreadable: " + split.getName());
                }
                if (!basePackage.equals(stringField(splitInfo, "packageName"))) {
                    throw new IOException("split metadata packageName mismatch in " + split.getName());
                }
                if (baseVersion >= 0 && versionField(splitInfo) != baseVersion) {
                    throw new IOException("split metadata versionCode mismatch in " + split.getName());
                }
                String actualSplitName = splitNameField(splitInfo);
                String expectedSplitName = apkSet.splitNameAt(index - 1).replaceAll("\\.apk$", "");
                if (actualSplitName == null || actualSplitName.isEmpty()) {
                    throw new IOException("split metadata splitName unavailable in " + split.getName());
                }
                if (!expectedSplitName.equals(actualSplitName)) {
                    throw new IOException("split metadata splitName mismatch in " + split.getName());
                }
            }
            if (apkSet.versionCode >= 0 && baseVersion >= 0 && apkSet.versionCode != baseVersion) {
                throw new IOException("split metadata versionCode mismatch in base APK");
            }
        } catch (IOException error) {
            throw error;
        } catch (Exception error) {
            throw new IOException("split metadata validation failed closed: "
                    + (error.getMessage() == null ? error.toString() : error.getMessage()));
        }
    }

    private static String stringField(Object object, String fieldName) throws Exception {
        Object value = object.getClass().getField(fieldName).get(object);
        return value == null ? "" : String.valueOf(value);
    }

    private static long versionField(Object object) throws Exception {
        try {
            Method method = object.getClass().getMethod("getLongVersionCode");
            Object value = method.invoke(object);
            return value instanceof Number ? ((Number) value).longValue() : -1L;
        } catch (NoSuchMethodException ignored) {
            Object value = object.getClass().getField("versionCode").get(object);
            return value instanceof Number ? ((Number) value).longValue() : -1L;
        }
    }

    private static String splitNameField(Object object) throws Exception {
        try {
            Object value = object.getClass().getField("splitNames").get(object);
            if (value instanceof String[] && ((String[]) value).length == 1) {
                return ((String[]) value)[0];
            }
        } catch (NoSuchFieldException ignored) {
            // Older PackageInfo implementations have no splitNames field.
        }
        return null;
    }

    private static ScanResult scanSeekableDescriptor(
        ParcelFileDescriptor descriptor,
        Object plugin,
        long deadline,
        Context context
    ) throws Exception {
        File descriptorPath = new File("/proc/self/fd/" + descriptor.getFd());
        return enumerateCentralDirectory(descriptorPath, plugin, deadline, context, false);
    }

    private static void copyCompressedApk(
        ContentResolver resolver,
        Uri uri,
        File temp,
        long deadline
    ) throws IOException {
        byte[] buffer = new byte[COPY_BUFFER_SIZE];
        try (
            InputStream input = resolver.openInputStream(uri);
            FileOutputStream output = new FileOutputStream(temp)
        ) {
            if (input == null) {
                throw new IOException("Cannot open selected APK");
            }
            int count;
            while ((count = input.read(buffer)) != -1) {
                ensureBeforeDeadline(deadline);
                output.write(buffer, 0, count);
            }
            output.getFD().sync();
        }
    }

    private static ScanResult enumerateCentralDirectory(
        File apk,
        Object plugin,
        long deadline,
        Context context,
        boolean allowSplitArchiveParserLimit
    ) throws Exception {
        Method likelyText = privateMethod(plugin, "isLikelyTextFile", String.class);
        Method detectType = privateMethod(plugin, "detectFileType", String.class, String.class);
        List<ApkEntry> entries = new ArrayList<>();
        List<ApkEntry> identityEntries = new ArrayList<>();
        String packageName = "";
        long versionCode = -1L;
        long totalScriptInflated = 0;
        int rpaCount = 0;
        RpycCompatibility.Report compatibility = null;
        int compatibilityPriority = Integer.MAX_VALUE;
        String compatibilityPath = null;
        try (ZipFile zip = new ZipFile(apk)) {
            TranslationCompiler.assertPristineSource(apk);
            Enumeration<? extends ZipEntry> enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                ensureBeforeDeadline(deadline);
                ZipEntry entry = enumeration.nextElement();
                if (entry.isDirectory()) {
                    continue;
                }
                String name = entry.getName();
                RenpyResourceLimits.checkPath(name);
                identityEntries.add(new ApkEntry(
                        name, entry.getSize(), entry.getCompressedSize(), entry.getCrc(), "identity"));
                String extension = extensionOf(name);
                if (isRenPyScriptExtension(extension)) {
                    if (entry.getCompressedSize() >= 0) {
                        RenpyResourceLimits.checkCompressed(entry.getCompressedSize());
                    }
                    if (entry.getSize() >= 0) {
                        RenpyResourceLimits.checkInflated(entry.getSize());
                        if (entry.getSize() > RenpyResourceLimits.MAX_TOTAL_SCRIPT_INFLATED
                                - totalScriptInflated) {
                            RenpyResourceLimits.checkTotalInflated(
                                    RenpyResourceLimits.MAX_TOTAL_SCRIPT_INFLATED + 1L);
                        }
                        totalScriptInflated += entry.getSize();
                        RenpyResourceLimits.checkTotalInflated(totalScriptInflated);
                    }
                }
                int templatePriority = TranslationCompiler.templatePriority(name);
                if (templatePriority != Integer.MAX_VALUE
                        && entry.getSize() > 0
                        && entry.getSize() <= 16_000_000L
                        && (templatePriority < compatibilityPriority
                        || (templatePriority == compatibilityPriority
                        && (compatibilityPath == null
                        || name.replace('\\', '/').compareToIgnoreCase(compatibilityPath) < 0)))) {
                    byte[] rpyc = readEntry(zip, entry, deadline);
                    compatibility = RpycCompatibility.inspect(rpyc);
                    compatibilityPriority = templatePriority;
                    compatibilityPath = name.replace('\\', '/');
                }
                if ("rpa".equals(extension) || "rpi".equals(extension)) {
                    rpaCount++;
                    addRpaEntries(zip, entry, name, extension, entries, deadline);
                    continue;
                }
                if ("ttf".equals(extension) || "otf".equals(extension)
                        || "ttc".equals(extension) || "otc".equals(extension)) {
                    RenpyResourceLimits.checkPath(name);
                    entries.add(new ApkEntry(name, entry.getSize(), entry.getCompressedSize(),
                            entry.getCrc(), "font"));
                    continue;
                }
                if (!TEXT_EXTENSIONS.contains(extension)) {
                    continue;
                }
                if (!isRenPyScriptExtension(extension) && !Boolean.TRUE.equals(likelyText.invoke(plugin, name))) {
                    continue;
                }
                String detectedType = (String) detectType.invoke(plugin, name, extension);
                String fileType = normalizeRenPyFileType(extension, detectedType);
                entries.add(new ApkEntry(
                    name,
                    entry.getSize(),
                    entry.getCompressedSize(),
                    entry.getCrc(),
                    fileType
                ));
            }

            ZipEntry manifest = zip.getEntry("AndroidManifest.xml");
            if (manifest != null) {
                readEntry(zip, manifest, deadline);
                packageName = packageNameFromArchive(context, apk, allowSplitArchiveParserLimit);
                versionCode = versionCodeFromArchive(context, apk, allowSplitArchiveParserLimit);
            }
            LinkedHashSet<String> languages = new LinkedHashSet<>();
            for (ApkEntry entry : entries) {
                String name = entry.name;
                if (name.startsWith("assets/")) {
                    String normalized = name.substring("assets/".length());
                    if (normalized.startsWith("x-")) {
                        normalized = normalized.substring(2);
                    }
                    String[] parts = normalized.split("/");
                    for (int i = 0; i + 1 < parts.length; i++) {
                        String dir = parts[i];
                        if ("tl".equals(dir) || "x-tl".equals(dir)) {
                            String code = parts[i + 1];
                            if (code != null && !code.isEmpty() && !code.contains(".")) {
                                languages.add(normalizeLangCode(code));
                            }
                        } else if (dir.startsWith("x-lang_")) {
                            String code = dir.substring("x-lang_".length());
                            if (!code.isEmpty()) {
                                languages.add(normalizeLangCode(code));
                            }
                        }
                    }
                }
            }
            String menuType = detectLanguageMenuType(zip, entries, deadline);
            RenpyFontSupport.FontReport font = fontPreflight(context, apk);
            RenpyCompatibilityReport compatibilityReport = RenpyPreflight.inspect(context,
                    new RenpyPreflight.SourceSet(
                            compatibilityPath,
                            compatibility,
                            rpaCount,
                            0,
                            new ArrayList<>(languages),
                            menuType,
                            font,
                            0,
                            0,
                            0));
            return new ScanResult(entries, packageName, new ArrayList<>(languages), menuType,
                    compatibility, compatibilityReport, rpaCount, 0,
                    identityEntries, versionCode);
        }
    }

    /**
     * Android's package parser is the source of truth for an APK identity.
     * Manifest bytes are binary XML on real APKs, so string heuristics can
     * mistake embedded provider/library names for the application package.
     */
    private static String packageNameFromArchive(Context context, File apk) throws IOException {
        return packageNameFromArchive(context, apk, false);
    }

    private static String packageNameFromArchive(Context context, File apk,
                                                 boolean allowSplitArchiveParserLimit)
            throws IOException {
        if (context == null || apk == null || !apk.isFile()) {
            return "";
        }
        Object packageManager = context.getPackageManager();
        if (packageManager == null) {
            return "";
        }
        try {
            Method parser = packageManager.getClass().getMethod(
                    "getPackageArchiveInfo", String.class, int.class);
            Object packageInfo = parser.invoke(packageManager, apk.getAbsolutePath(), 0);
            if (packageInfo == null) {
                return "";
            }
            String packageName = stringField(packageInfo, "packageName");
            return packageName == null ? "" : packageName.trim();
        } catch (NoSuchMethodException ignored) {
            return "";
        } catch (Exception error) {
            if (allowSplitArchiveParserLimit && isSplitArchiveParserLimitation(error)) {
                return "";
            }
            String message = error.getMessage() == null ? error.toString() : error.getMessage();
            throw new IOException("APK package identity parse failed: " + message, error);
        }
    }

    private static long versionCodeFromArchive(Context context, File apk,
                                               boolean allowSplitArchiveParserLimit)
            throws IOException {
        if (context == null || apk == null || !apk.isFile()) {
            return -1L;
        }
        Object packageManager = context.getPackageManager();
        if (packageManager == null) {
            return -1L;
        }
        try {
            Method parser = packageManager.getClass().getMethod(
                    "getPackageArchiveInfo", String.class, int.class);
            Object packageInfo = parser.invoke(packageManager, apk.getAbsolutePath(), 0);
            return packageInfo == null ? -1L : versionField(packageInfo);
        } catch (NoSuchMethodException ignored) {
            return -1L;
        } catch (Exception error) {
            if (allowSplitArchiveParserLimit && isSplitArchiveParserLimitation(error)) {
                return -1L;
            }
            String message = error.getMessage() == null ? error.toString() : error.getMessage();
            throw new IOException("APK version identity parse failed: " + message, error);
        }
    }

    private static boolean isSplitArchiveParserLimitation(Throwable error) {
        Throwable current = error;
        while (current != null) {
            String message = current.getMessage();
            if (message != null) {
                String lower = message.toLowerCase(Locale.ROOT);
                if (lower.contains("expected base apk")
                        || lower.contains("found split")
                        || lower.contains("split apk")) {
                    return true;
                }
            }
            current = current.getCause();
        }
        return false;
    }

    private static String normalizeLangCode(String code) {
        String value = code.trim().toLowerCase(Locale.ROOT);
        if (value.startsWith("x-")) {
            value = value.substring(2);
        }
        return value.replace("_", "-");
    }

    private static String detectLanguageMenuType(ZipFile zip, List<ApkEntry> entries, long deadline) throws Exception {
        boolean sawLanguageButton = false;
        boolean sawCustomLanguage = false;
        boolean sawRenpyBucket = false;
        boolean sawCustomBucket = false;
        int scanned = 0;
        StringBuilder haystack = new StringBuilder();
        for (ApkEntry entry : entries) {
            String name = entry.name;
            String lower = name.toLowerCase(Locale.ROOT);
            if (lower.contains("x-lang_")) {
                sawCustomBucket = true;
            }
            if (!lower.contains("screens") && !lower.contains("preferences")
                    && !lower.contains("gamemenu") && !lower.contains("mainmenu")) {
                continue;
            }
            if ((entry.compressedSize <= 0 && !name.contains("!/"))
                    || entry.compressedSize > 400_000L) continue;
            if (scanned++ >= 6) break;
            byte[] bytes = readEntryData(zip, name, deadline);
            if (bytes == null) continue;
            String text = new String(bytes, StandardCharsets.ISO_8859_1);
            haystack.append(text);
            if (text.contains("Language")) {
                sawLanguageButton = true;
            }
            if (text.contains("profiler_language") || text.contains("PROFILER_LANGUAGE")) {
                sawCustomLanguage = true;
            }
        }
        if (sawCustomLanguage || sawCustomBucket) {
            return "custom";
        }
        if (sawLanguageButton) {
            return "renpy";
        }
        for (ApkEntry entry : entries) {
            String name = entry.name;
            String lower = name.toLowerCase(Locale.ROOT);
            if (!lower.startsWith("assets/")) continue;
            String path = lower.substring("assets/".length());
            if (path.startsWith("x-")) {
                path = path.substring(2);
            }
            String[] parts = path.split("/");
            for (int i = 0; i + 1 < parts.length; i++) {
                String dir = parts[i];
                if (("tl".equals(dir) || "x-tl".equals(dir))
                        && parts[i + 1].length() > 0
                        && !"none".equalsIgnoreCase(parts[i + 1])) {
                    sawRenpyBucket = true;
                    break;
                }
            }
            if (sawRenpyBucket) break;
        }
        return sawRenpyBucket ? "renpy" : "none";
    }

    private static void addRpaEntries(
        ZipFile zip,
        ZipEntry entry,
        String name,
        String extension,
        List<ApkEntry> entries,
        long deadline
    ) throws IOException {
        if ("rpa".equals(extension)) {
            List<String> scripts = RpaArchive.listEntriesFromZip(zip, entry, name);
            RenpyResourceLimits.checkEntryCount((long) entries.size() + scripts.size());
            for (String script : scripts) {
                entries.add(new ApkEntry(RpaArchive.virtualName(name, script), 0L, 0L, "rpyc"));
            }
            return;
        }
        String dataName = rpaDataName(name);
        ZipEntry dataEntry = dataName == null ? null : zip.getEntry(dataName);
        if (dataEntry == null) {
            return;
        }
        byte[] index = readEntry(zip, entry, deadline);
        List<String> scripts = RpaArchive.listEntries(index, name);
        RenpyResourceLimits.checkEntryCount((long) entries.size() + scripts.size());
        for (String script : scripts) {
            entries.add(new ApkEntry(RpaArchive.virtualName(dataName, script), 0L, 0L, "rpyc"));
        }
    }

    private static String rpaDataName(String name) {
        if (name.toLowerCase(Locale.ROOT).endsWith(".rpi")) {
            return name.substring(0, name.length() - 4) + ".rpa";
        }
        return null;
    }

    private static byte[] readEntryData(ZipFile zip, String entryName, long deadline) throws IOException {
        String[] parts = RpaArchive.splitVirtual(entryName);
        if (parts.length == 2) {
            ZipEntry archive = zip.getEntry(parts[0]);
            if (archive == null) {
                return null;
            }
            String lower = parts[0].toLowerCase(Locale.ROOT);
            if (lower.endsWith(".rpi")) {
                String dataName = rpaDataName(parts[0]);
                ZipEntry data = dataName == null ? null : zip.getEntry(dataName);
                if (data == null) {
                    return null;
                }
                byte[] index = readEntry(zip, archive, deadline);
                return RpaArchive.readEntryFromZip(zip, data, dataName, parts[1], index);
            }
            return RpaArchive.readEntryFromZip(zip, archive, parts[0], parts[1]);
        }
        ZipEntry entry = zip.getEntry(entryName);
        return entry == null ? null : readEntry(zip, entry, deadline);
    }
    private static byte[] readEntry(ZipFile zip, ZipEntry entry, long deadline) throws IOException {
        if (entry.getCompressedSize() >= 0) {
            RenpyResourceLimits.checkCompressed(entry.getCompressedSize());
        }
        if (entry.getSize() >= 0) {
            RenpyResourceLimits.checkInflated(entry.getSize());
        }
        try (
            InputStream input = zip.getInputStream(entry);
            ByteArrayOutputStream output = new ByteArrayOutputStream()
        ) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            long total = 0;
            while ((count = input.read(buffer)) != -1) {
                ensureBeforeDeadline(deadline);
                RenpyResourceLimits.checkInterrupted();
                total += count;
                RenpyResourceLimits.checkInflated(total);
                if (entry.getCompressedSize() > 0) {
                    RenpyResourceLimits.checkInflateRatio(entry.getCompressedSize(), total);
                }
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private static Method privateMethod(Object target, String name, Class<?>... parameters) throws Exception {
        Method method = target.getClass().getDeclaredMethod(name, parameters);
        method.setAccessible(true);
        return method;
    }

    private static JSObject capabilitiesJson(EngineCapabilities value) {
        EngineCapabilities safe = value == null
                ? RenpyEngineAdapter.INSTANCE.capabilities(null) : value;
        return new JSObject()
                .put("canDetect", safe.canDetect)
                .put("canExtractStructured", safe.canExtractStructured)
                .put("canTranslate", safe.canTranslate)
                .put("canWritePatch", safe.canWritePatch)
                .put("canActivate", safe.canActivate);
    }

    private static JSObject toResponse(ScanResult result, long durationMs, boolean cacheHit) throws Exception {
        JSArray entries = new JSArray();
        for (ApkEntry entry : result.entries) {
            JSObject value = new JSObject();
            value.put("name", entry.name);
            value.put("size", entry.size);
            value.put("compressedSize", entry.compressedSize);
            value.put("crc", entry.crc);
            value.put("fileType", entry.fileType);
            value.put("sourceApk", entry.sourceApk);
            value.put("apkRole", entry.apkRole);
            value.put("sourceOwner", entry.sourceOwner);
            JSArray duplicateSources = new JSArray();
            for (String sourceApk : entry.duplicateSourceApks) {
                duplicateSources.put(sourceApk);
            }
            value.put("duplicateSourceApks", duplicateSources);
            entries.put(value);
        }
        JSObject response = new JSObject();
        response.put("entries", entries);
        response.put("totalFiles", entries.length());
        response.put("packageName", result.packageName);
        response.put("splitCount", result.splitCount);
        response.put("adapterId", "renpy");
        EngineCapabilities caps = result.compatibilityReport == null
                ? RenpyEngineAdapter.INSTANCE.capabilities(null)
                : RenpyEngineAdapter.INSTANCE.capabilities(result.compatibilityReport);
        response.put("workflow", caps.workflow.name());
        response.put("capabilities", capabilitiesJson(caps));
        response.put("projectFingerprint", result.projectFingerprint);
        response.put("recordSchemaVersion", 1);
        response.put("translationGate", caps.canTranslate ? "clear" : "blocked");
        JSArray languages = new JSArray();
        for (String language : result.renpyLanguages) {
            languages.put(language);
        }
        response.put("renpyLanguages", languages);
        response.put("renpyMenuType", result.renpyMenuType);
        response.put("compatibilityReport", compatibilityReportJson(result.compatibilityReport));
        response.put("compatibilityGate", compatibilityGate(result.compatibilityReport));
        response.put("compatibilitySupportLevel", result.compatibilityReport == null
                ? "UNSUPPORTED" : result.compatibilityReport.supportLevel.name());
        response.put("verificationLevel", result.compatibilityReport == null
                ? RenpyVerificationEvidence.PENDING_LEVEL
                : result.compatibilityReport.verificationLevel);
        response.put("compatibilityDialect", result.compatibility == null
                ? "UNKNOWN" : result.compatibility.dialect.name());
        if (result.compatibility == null) {
            response.put("supportLevel", "unknown");
            response.put("compatibilityReason", "no_rpyc_template");
            response.put("reasonCode", "no_rpyc_template");
        } else {
            boolean compilerSupported = result.compatibility.canGenerate();
            response.put("supportLevel", compilerSupported ? "compile" : "extract_only");
            response.put("compatibilityReason", result.compatibility.reason);
            response.put("reasonCode", compilerSupported ? "" : "legacy_pickle_writer_required");
            response.put("rpycContainer", result.compatibility.container);
            response.put("preferredSlot", result.compatibility.preferredSlot);
            response.put("pickleProtocol", result.compatibility.pickleProtocol);
            response.put("usesBuiltins", result.compatibility.usesBuiltins);
            response.put("usesPy2Builtins", result.compatibility.usesPy2Builtins);
        }
        response.put("scanDurationMs", durationMs);
        response.put("cacheHit", cacheHit);
        return response;
    }

    private static String compatibilityGate(RenpyCompatibilityReport report) {
        if (report == null || report.supportLevel == RenpyCompatibilityReport.SupportLevel.UNSUPPORTED) {
            return "blocked";
        }
        if (report.supportLevel == RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY) {
            return "extract_only";
        }
        return "clear";
    }

    private static JSObject compatibilityReportJson(RenpyCompatibilityReport report) {
        JSObject result = new JSObject();
        if (report == null) {
            result.put("supportLevel", "UNSUPPORTED");
            result.put("activationStrategy", "NONE");
            result.put("templatePath", "");
            result.put("menuType", "unknown");
            result.put("rpaCount", 0);
            result.put("splitCount", 0);
            result.put("languageBuckets", new JSArray());
            result.put("uniqueTextCount", 0);
            result.put("occurrenceCount", 0);
            result.put("collisionCount", 0);
            JSArray issues = new JSArray();
            issues.put(new JSObject().put("code", "renpy_preflight_missing_report")
                    .put("message", "Compatibility report is unavailable"));
            result.put("issues", issues);
            return result;
        }
        result.put("supportLevel", report.supportLevel.name());
        result.put("activationStrategy", report.activationStrategy.name());
        result.put("verificationLevel", report.verificationLevel);
        result.put("templatePath", report.templatePath);
        result.put("menuType", report.menuType);
        result.put("rpaCount", report.rpaCount);
        result.put("splitCount", report.splitCount);
        JSArray languages = new JSArray();
        for (String language : report.languageBuckets) languages.put(language);
        result.put("languageBuckets", languages);
        result.put("uniqueTextCount", report.uniqueTextCount);
        result.put("occurrenceCount", report.occurrenceCount);
        result.put("collisionCount", report.collisionCount);
        if (report.rpyc != null) {
            result.put("rpyc", new JSObject()
                    .put("container", report.rpyc.container)
                    .put("preferredSlot", report.rpyc.preferredSlot)
                    .put("pickleProtocol", report.rpyc.pickleProtocol)
                    .put("usesBuiltins", report.rpyc.usesBuiltins)
                    .put("usesPy2Builtins", report.rpyc.usesPy2Builtins)
                    .put("generationSupport", report.rpyc.generationSupport == null
                            ? "UNKNOWN_EXTRACT_ONLY" : report.rpyc.generationSupport.name())
                    .put("dialect", report.rpyc.dialect == null
                            ? "UNKNOWN" : report.rpyc.dialect.name())
                    .put("reason", report.rpyc.reason));
        } else {
            result.put("rpyc", null);
        }
        if (report.font != null) result.put("font", fontReportJson(report.font));
        else result.put("font", null);
        JSArray issues = new JSArray();
        for (RenpyCompatibilityReport.Issue issue : report.issues) {
            issues.put(new JSObject().put("code", issue.code).put("message", issue.message));
        }
        result.put("issues", issues);
        return result;
    }

    private static Metadata readMetadata(ContentResolver resolver, Uri uri) {
        String displayName = "";
        long size = -1L;
        long lastModified = -1L;
        try (Cursor cursor = resolver.query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex("_display_name");
                int sizeIndex = cursor.getColumnIndex("_size");
                int modifiedIndex = cursor.getColumnIndex("last_modified");
                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) {
                    displayName = cursor.getString(nameIndex);
                }
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                    size = cursor.getLong(sizeIndex);
                }
                if (modifiedIndex >= 0 && !cursor.isNull(modifiedIndex)) {
                    lastModified = cursor.getLong(modifiedIndex);
                }
            }
        } catch (Exception ignored) {
            // URI identity still provides a safe process-local cache key.
        }
        return new Metadata(displayName, size, lastModified);
    }

    private static String extensionOf(String name) {
        int slash = name.lastIndexOf('/');
        int dot = name.lastIndexOf('.');
        if (dot <= slash || dot == name.length() - 1) {
            return "";
        }
        return name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private static boolean isRenPyScriptExtension(String extension) {
        return RENPY_SCRIPT_EXTENSIONS.contains(extension);
    }

    private static String normalizeRenPyFileType(String extension, String detectedType) {
        if ("rpym".equals(extension) || "rpy".equals(extension)) {
            return "rpy";
        }
        if ("rpymc".equals(extension) || "rpyc".equals(extension)) {
            return "rpyc";
        }
        return detectedType;
    }

    static String recordId(String adapterId, String sourceOwner, RenpyTextRecord record) {
        if (record == null) {
            return sha256Hex(safeIdentityPart(adapterId) + "\n"
                    + safeIdentityPart(sourceOwner) + "\n");
        }
        return sha256Hex(safeIdentityPart(adapterId) + "\n"
                + safeIdentityPart(sourceOwner) + "\n"
                + safeIdentityPart(record.sourcePath) + "\n"
                + record.kind.name() + "\n"
                + safeIdentityPart(record.identifier) + "\n"
                + safeIdentityPart(record.speaker) + "\n"
                + record.occurrence + "\n"
                + safeIdentityPart(record.text));
    }

    static String projectFingerprint(String packageName, long versionCode, int splitCount,
                                     List<ApkEntry> identityEntries) {
        List<ApkEntry> sorted = new ArrayList<>();
        if (identityEntries != null) sorted.addAll(identityEntries);
        Collections.sort(sorted, new Comparator<ApkEntry>() {
            @Override
            public int compare(ApkEntry left, ApkEntry right) {
                int owner = left.sourceOwner.compareTo(right.sourceOwner);
                if (owner != 0) return owner;
                int name = left.name.compareTo(right.name);
                if (name != 0) return name;
                int size = Long.compare(left.size, right.size);
                if (size != 0) return size;
                int compressed = Long.compare(left.compressedSize, right.compressedSize);
                if (compressed != 0) return compressed;
                return Long.compare(left.crc, right.crc);
            }
        });
        StringBuilder value = new StringBuilder()
                .append(safeIdentityPart(packageName)).append('\n')
                .append(versionCode).append('\n')
                .append(splitCount).append('\n');
        for (ApkEntry entry : sorted) {
            if (isSignatureEntry(entry.name)) continue;
            value.append(safeIdentityPart(entry.sourceOwner)).append('\t')
                    .append(safeIdentityPart(entry.name)).append('\t')
                    .append(entry.size).append('\t')
                    .append(entry.compressedSize).append('\t')
                    .append(entry.crc).append('\n');
        }
        return sha256Hex(value.toString());
    }

    private static String projectFingerprintForApkSet(Context context, InstalledApkSet apkSet)
            throws Exception {
        List<ApkEntry> identity = new ArrayList<>();
        List<File> all = apkSet.allApks();
        for (int index = 0; index < all.size(); index++) {
            String owner = index == 0 ? "base"
                    : "split:" + stripApkSuffix(apkSet.splitNameAt(index - 1));
            identity.addAll(identityEntriesForApk(all.get(index), owner));
        }
        return projectFingerprint(apkSet.packageName, apkSet.versionCode,
                apkSet.splitApks.size(), identity);
    }

    private static List<ApkEntry> identityEntriesForApk(File apk, String sourceOwner)
            throws IOException {
        List<ApkEntry> result = new ArrayList<>();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                ZipEntry entry = enumeration.nextElement();
                if (entry.isDirectory()) continue;
                String name = entry.getName();
                RenpyResourceLimits.checkPath(name);
                result.add(new ApkEntry(name, entry.getSize(), entry.getCompressedSize(),
                        entry.getCrc(), "identity", apk.getName(),
                        sourceOwner.startsWith("split:") ? "split" : "base", sourceOwner));
            }
        }
        return result;
    }

    private static boolean isSignatureEntry(String name) {
        String normalized = name == null ? "" : name.replace('\\', '/');
        return normalized.equals("META-INF") || normalized.startsWith("META-INF/");
    }

    private static String stripApkSuffix(String value) {
        if (value == null) return "unknown";
        return value.endsWith(".apk") ? value.substring(0, value.length() - 4) : value;
    }

    private static String safeIdentityPart(String value) {
        return value == null ? "" : value.replace('\\', '/');
    }

    private static String sha256Hex(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(digest.length * 2);
            for (byte item : digest) {
                result.append(String.format(Locale.ROOT, "%02x", item & 0xff));
            }
            return result.toString();
        } catch (Exception error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }
    }

    private static String sha256(String value) throws Exception {
        return sha256Hex(value);
    }

    private static void ensureBeforeDeadline(long deadline) throws IOException {
        if (SystemClock.elapsedRealtime() > deadline) {
            throw new IOException("APK scan timed out after 60 seconds");
        }
    }

    private static final class Metadata {
        final String displayName;
        final long size;
        final long lastModified;

        Metadata(String displayName, long size, long lastModified) {
            this.displayName = displayName;
            this.size = size;
            this.lastModified = lastModified;
        }
    }

    private static final class ApkEntry {
        final String name;
        final long size;
        final long compressedSize;
        final long crc;
        final String fileType;
        final String sourceApk;
        final String apkRole;
        final String sourceOwner;
        final List<String> duplicateSourceApks;

        ApkEntry(String name, long size, long compressedSize, String fileType) {
            this(name, size, compressedSize, -1L, fileType, "base.apk", "base", "base");
        }

        ApkEntry(String name, long size, long compressedSize, long crc, String fileType) {
            this(name, size, compressedSize, crc, fileType, "base.apk", "base", "base");
        }

        ApkEntry(String name, long size, long compressedSize, String fileType,
                 String sourceApk, String apkRole) {
            this(name, size, compressedSize, -1L, fileType, sourceApk, apkRole,
                    "split".equals(apkRole) ? "split:unknown" : "base");
        }

        ApkEntry(String name, long size, long compressedSize, long crc, String fileType,
                 String sourceApk, String apkRole, String sourceOwner) {
            this.name = name;
            this.size = size;
            this.compressedSize = compressedSize;
            this.crc = crc;
            this.fileType = fileType;
            this.sourceApk = sourceApk;
            this.apkRole = apkRole;
            this.sourceOwner = sourceOwner == null || sourceOwner.isEmpty()
                    ? "base" : sourceOwner;
            this.duplicateSourceApks = new ArrayList<>();
        }

        ApkEntry withSource(String sourceApk, String apkRole, String sourceOwner) {
            return new ApkEntry(name, size, compressedSize, crc, fileType,
                    sourceApk, apkRole, sourceOwner);
        }
    }

    private static final class ScanResult {
        final List<ApkEntry> entries;
        final List<ApkEntry> identityEntries;
        final String packageName;
        final long versionCode;
        final String projectFingerprint;
        final List<String> renpyLanguages;
        final String renpyMenuType;
        final RpycCompatibility.Report compatibility;
        final RenpyCompatibilityReport compatibilityReport;
        final int rpaCount;
        final int splitCount;

        ScanResult(List<ApkEntry> entries, String packageName, List<String> renpyLanguages,
                   String renpyMenuType, RpycCompatibility.Report compatibility,
                   RenpyCompatibilityReport compatibilityReport, int rpaCount, int splitCount,
                   List<ApkEntry> identityEntries, long versionCode) {
            this.entries = Collections.unmodifiableList(new ArrayList<>(entries));
            this.identityEntries = Collections.unmodifiableList(new ArrayList<>(
                    identityEntries == null ? Collections.<ApkEntry>emptyList() : identityEntries));
            this.packageName = packageName == null ? "" : packageName;
            this.versionCode = versionCode;
            this.projectFingerprint = projectFingerprint(this.packageName, this.versionCode,
                    splitCount, this.identityEntries);
            this.renpyLanguages = Collections.unmodifiableList(new ArrayList<>(renpyLanguages));
            this.renpyMenuType = renpyMenuType == null ? "none" : renpyMenuType;
            this.compatibility = compatibility;
            this.compatibilityReport = compatibilityReport;
            this.rpaCount = rpaCount;
            this.splitCount = splitCount;
        }
    }
}
