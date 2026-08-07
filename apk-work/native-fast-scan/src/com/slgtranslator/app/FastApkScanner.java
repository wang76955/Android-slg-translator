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
    static final int MAX_CACHE_ENTRIES = 4;
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
                    StringBuilder out = new StringBuilder();
                    boolean translationBucket = lower.contains("/x-tl/")
                            || lower.contains("/tl/");
                    List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                            bytes, entryName, translationBucket);
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
                        String text = record.text;
                        // The line protocol splits on newlines, so embedded
                        // control characters are escaped and unescaped in JS.
                        // Escape backslashes first so a literal "\n" in the
                        // original string stays distinguishable from a real
                        // newline after the JS side unescapes the protocol.
                        String escaped = text.replace("\\", "\\\\")
                                .replace("\n", "\\n")
                                .replace("\r", "\\r")
                                .replace("\t", "\\t");
                        out.append("RPYC_STRING\t").append(escaped).append('\n');
                        renpyRecords.put(renpyRecordJson(record));
                        String classification = coverageClassification(record);
                        if (classification != null) {
                            coverageClassifications.put(record.sourcePath + "\t" + record.text, classification);
                        }
                    }
                    content = out.toString();
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
            call.resolve(result);
        } catch (Exception e) {
            String message = e.getMessage();
            call.reject("Failed to read entry: " + (message == null ? e.toString() : message));
        }
    }

    private static JSObject renpyRecordJson(RenpyTextRecord record) {
        JSObject result = new JSObject()
                .put("text", record.text)
                .put("kind", record.kind.name())
                .put("speaker", record.speaker)
                .put("identifier", record.identifier)
                .put("sourcePath", record.sourcePath)
                .put("sourceLine", record.sourceLine)
                .put("occurrence", record.occurrence)
                .put("coverageCertain", record.coverageCertain);
        String classification = coverageClassification(record);
        if (classification != null) {
            result.put("coverageClassification", classification);
        }
        return result;
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
        for (File apk : apkSet.allApks()) {
            if (preferredSourceApk != null && !preferredSourceApk.isEmpty()
                    && !preferredSourceApk.equals(apk.getName())) {
                continue;
            }
            try (ZipFile zip = new ZipFile(apk)) {
                if (readEntryData(zip, entryName, Long.MAX_VALUE) != null) {
                    return apk;
                }
            }
        }
        if (preferredSourceApk != null && !preferredSourceApk.isEmpty()) {
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
                CACHE.put(cacheKey, result);
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
                CACHE.put(cacheKey, result);
            }
            return toResponse(result, SystemClock.elapsedRealtime() - startedAt, false);
        }

        File temp = File.createTempFile("slg-apk-scan-", ".apk", context.getCacheDir());
        try {
            copyCompressedApk(resolver, uri, temp, deadline);
            result = enumerateCentralDirectory(temp, plugin, deadline, context);
            synchronized (CACHE) {
                CACHE.put(cacheKey, result);
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
            ScanResult current = enumerateCentralDirectory(apk, plugin, deadline, context);
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
            for (ApkEntry entry : current.entries) {
                ApkEntry sourced = entry.withSource(apk.getName(), index == 0 ? "base" : "split");
                if (!byName.containsKey(sourced.name)) {
                    byName.put(sourced.name, sourced);
                    merged.add(sourced);
                } else {
                    byName.get(sourced.name).duplicateSourceApks.add(sourced.sourceApk);
                }
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
                    report.occurrenceCount, report.collisionCount, report.issues);
        }
        return new ScanResult(merged, baseResult.packageName, languages, menuType,
                bestCompatibility, report, rpaCount, apkSet.splitApks.size());
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
                Object splitInfo = parser.invoke(context.getPackageManager(), split.getAbsolutePath(), 0);
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
        return enumerateCentralDirectory(descriptorPath, plugin, deadline, context);
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
        Context context
    ) throws Exception {
        Method likelyText = privateMethod(plugin, "isLikelyTextFile", String.class);
        Method detectType = privateMethod(plugin, "detectFileType", String.class, String.class);
        Method extractPackage = privateMethod(plugin, "extractPackageNameFromManifest", byte[].class);
        List<ApkEntry> entries = new ArrayList<>();
        String packageName = "";
        long totalScriptInflated = 0;
        int rpaCount = 0;
        RpycCompatibility.Report compatibility = null;
        int compatibilityPriority = Integer.MAX_VALUE;
        String compatibilityPath = null;
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                ensureBeforeDeadline(deadline);
                ZipEntry entry = enumeration.nextElement();
                if (entry.isDirectory()) {
                    continue;
                }
                String name = entry.getName();
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
                    entries.add(new ApkEntry(name, entry.getSize(), entry.getCompressedSize(), "font"));
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
                    fileType
                ));
            }

            ZipEntry manifest = zip.getEntry("AndroidManifest.xml");
            if (manifest != null) {
                byte[] manifestBytes = readEntry(zip, manifest, deadline);
                Object extracted = extractPackage.invoke(plugin, manifestBytes);
                packageName = extracted instanceof String ? (String) extracted : "";
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
                    compatibility, compatibilityReport, rpaCount, 0);
        }
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

    private static JSObject toResponse(ScanResult result, long durationMs, boolean cacheHit) throws Exception {
        JSArray entries = new JSArray();
        for (ApkEntry entry : result.entries) {
            JSObject value = new JSObject();
            value.put("name", entry.name);
            value.put("size", entry.size);
            value.put("compressedSize", entry.compressedSize);
            value.put("fileType", entry.fileType);
            value.put("sourceApk", entry.sourceApk);
            value.put("apkRole", entry.apkRole);
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
        if (result.compatibility == null) {
            response.put("supportLevel", "unknown");
            response.put("compatibilityReason", "no_rpyc_template");
            response.put("reasonCode", "no_rpyc_template");
        } else {
            boolean modern = result.compatibility.generationSupport
                    == RpycCompatibility.GenerationSupport.MODERN_SUPPORTED;
            response.put("supportLevel", modern ? "compile" : "extract_only");
            response.put("compatibilityReason", result.compatibility.reason);
            response.put("reasonCode", modern ? "" : "legacy_pickle_writer_required");
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

    private static String sha256(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder(digest.length * 2);
        for (byte item : digest) {
            result.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        }
        return result.toString();
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
        final String fileType;
        final String sourceApk;
        final String apkRole;
        final List<String> duplicateSourceApks;

        ApkEntry(String name, long size, long compressedSize, String fileType) {
            this(name, size, compressedSize, fileType, "base.apk", "base");
        }

        ApkEntry(String name, long size, long compressedSize, String fileType,
                 String sourceApk, String apkRole) {
            this.name = name;
            this.size = size;
            this.compressedSize = compressedSize;
            this.fileType = fileType;
            this.sourceApk = sourceApk;
            this.apkRole = apkRole;
            this.duplicateSourceApks = new ArrayList<>();
        }

        ApkEntry withSource(String sourceApk, String apkRole) {
            return new ApkEntry(name, size, compressedSize, fileType, sourceApk, apkRole);
        }
    }

    private static final class ScanResult {
        final List<ApkEntry> entries;
        final String packageName;
        final List<String> renpyLanguages;
        final String renpyMenuType;
        final RpycCompatibility.Report compatibility;
        final RenpyCompatibilityReport compatibilityReport;
        final int rpaCount;
        final int splitCount;

        ScanResult(List<ApkEntry> entries, String packageName, List<String> renpyLanguages,
                   String renpyMenuType, RpycCompatibility.Report compatibility,
                   RenpyCompatibilityReport compatibilityReport, int rpaCount, int splitCount) {
            this.entries = Collections.unmodifiableList(new ArrayList<>(entries));
            this.packageName = packageName == null ? "" : packageName;
            this.renpyLanguages = Collections.unmodifiableList(new ArrayList<>(renpyLanguages));
            this.renpyMenuType = renpyMenuType == null ? "none" : renpyMenuType;
            this.compatibility = compatibility;
            this.compatibilityReport = compatibilityReport;
            this.rpaCount = rpaCount;
            this.splitCount = splitCount;
        }
    }
}
