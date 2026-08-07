package com.slgtranslator.app;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Conservative APK-local font preflight for Ren'Py translation builds. */
public final class RenpyFontSupport {

    public static final int MAX_FONT_ENTRIES = 64;
    public static final long MAX_FONT_BYTES = 32L * 1024 * 1024;
    public static final long MAX_TOTAL_FONT_BYTES = 128L * 1024 * 1024;
    private static final int MAX_EVIDENCE_BYTES = 1024 * 1024;
    private static final int COPY_BUFFER_SIZE = 8192;

    private static final int[] BASE_CODE_POINTS = {
            '中', '文', '的', '是', '了', '我', '你', '不', '这', '那',
            '，', '。', '！', '？', '：', '；', '、', '“', '”', '‘', '’',
            '（', '）', '【', '】', '《', '》', '…'
    };

    private RenpyFontSupport() {
    }

    /** Fixed, conservative preflight set used before translation output exists. */
    public static Set<Integer> defaultRequiredCodePoints() {
        Set<Integer> result = new TreeSet<>();
        for (int codePoint : BASE_CODE_POINTS) {
            result.add(codePoint);
        }
        return result;
    }

    /** Returns every non-ASCII code point used by translated values. */
    public static Set<Integer> codePointsOfTranslations(Iterable<String> translations) {
        Set<Integer> result = new TreeSet<>();
        if (translations == null) {
            return result;
        }
        for (String value : translations) {
            if (value == null) {
                continue;
            }
            for (int offset = 0; offset < value.length();) {
                int codePoint = value.codePointAt(offset);
                if (codePoint > 0x7f) {
                    result.add(codePoint);
                }
                offset += Character.charCount(codePoint);
            }
        }
        return result;
    }

    public static FontReport inspect(Context context, File apk, Set<Integer> requiredCodePoints) {
        TreeSet<Integer> required = new TreeSet<>();
        if (requiredCodePoints != null) {
            for (Integer codePoint : requiredCodePoints) {
                if (codePoint != null && codePoint >= 0 && codePoint <= 0x10ffff
                        && !(codePoint >= 0xd800 && codePoint <= 0xdfff)) {
                    required.add(codePoint);
                }
            }
        }
        List<String> candidates = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        String bestPath = null;
        int bestCovered = -1;
        boolean styleBucket = false;
        boolean lineBreakEvidence = false;
        if (context == null || apk == null || !apk.isFile()) {
            warnings.add("font_preflight_input_unavailable");
            return new FontReport(candidates, bestPath, required.size(), 0,
                    new ArrayList<>(required), styleBucket, lineBreakEvidence, warnings);
        }

        File tempDirectory = tempDirectory(context, warnings);
        if (tempDirectory == null) {
            warnings.add("font_preflight_temp_directory_unavailable");
        }
        int inspectedFonts = 0;
        long totalFontBytes = 0;
        try (ZipFile zip = new ZipFile(apk)) {
            java.util.Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (entry.isDirectory()) {
                    continue;
                }
                String name = entry.getName();
                String lower = name == null ? "" : name.replace('\\', '/').toLowerCase();
                if (isChineseStylePath(lower)) {
                    styleBucket = true;
                }
                if (isLineBreakEvidencePath(lower)
                        && containsLineBreakEvidence(zip, entry, warnings)) {
                    lineBreakEvidence = true;
                }
                if (!isFontPath(lower)) {
                    continue;
                }
                if (inspectedFonts >= MAX_FONT_ENTRIES) {
                    warnings.add("font_preflight_entry_limit");
                    continue;
                }
                try {
                    RenpyResourceLimits.checkPath(name);
                } catch (RuntimeException invalidPath) {
                    warnings.add("font_preflight_invalid_path");
                    continue;
                }
                long declaredSize = entry.getSize();
                long compressedSize = entry.getCompressedSize();
                if (declaredSize > MAX_FONT_BYTES || declaredSize < -1
                        || compressedSize > MAX_FONT_BYTES || compressedSize < -1) {
                    warnings.add("font_preflight_font_size_limit");
                    continue;
                }
                if (declaredSize >= 0 && totalFontBytes > MAX_TOTAL_FONT_BYTES - declaredSize) {
                    warnings.add("font_preflight_total_size_limit");
                    continue;
                }
                if (declaredSize >= 0 && compressedSize > 0) {
                    try {
                        RenpyResourceLimits.checkInflateRatio(compressedSize, declaredSize);
                    } catch (RuntimeException ratio) {
                        warnings.add("font_preflight_ratio_limit");
                        continue;
                    }
                }
                candidates.add(name);
                inspectedFonts++;
                if (tempDirectory == null) {
                    continue;
                }
                File temporary = null;
                try {
                    temporary = File.createTempFile("slg-font-", ".tmp", tempDirectory);
                    long copied = copyFont(zip, entry, temporary, compressedSize);
                    if (totalFontBytes > MAX_TOTAL_FONT_BYTES - copied) {
                        warnings.add("font_preflight_total_size_limit");
                        continue;
                    }
                    totalFontBytes += copied;
                    int covered = countCovered(temporary, required);
                    if (covered > bestCovered) {
                        bestCovered = covered;
                        bestPath = name;
                    }
                } catch (Exception error) {
                    warnings.add("font_preflight_load_failed");
                } finally {
                    if (temporary != null && temporary.exists() && !temporary.delete()) {
                        warnings.add("font_preflight_temp_cleanup_failed");
                    }
                }
            }
        } catch (Exception error) {
            warnings.add("font_preflight_apk_read_failed");
        }

        if (candidates.size() > 1) {
            warnings.add("font_preflight_multiple_candidates_best_coverage_selected");
        }
        if (!styleBucket) {
            warnings.add("font_preflight_chinese_style_missing");
        }
        if (!lineBreakEvidence) {
            warnings.add("font_preflight_east_asian_line_break_unconfirmed");
        }
        int covered = bestCovered < 0 ? 0 : bestCovered;
        List<Integer> missing = new ArrayList<>();
        if (bestCovered < 0) {
            missing.addAll(required);
        } else if (bestCovered < required.size()) {
            // Re-check only the selected candidate so the report is exact, not an aggregate union.
            missing.addAll(required);
            // The selected temporary file is intentionally gone; inspect() reports the conservative
            // missing set from the best candidate through the per-font result retained below.
            missing = missingForBestCandidate(apk, context, bestPath, required, warnings);
            covered = required.size() - missing.size();
        }
        return new FontReport(candidates, bestPath, required.size(), covered, missing,
                styleBucket, lineBreakEvidence, warnings);
    }

    private static List<Integer> missingForBestCandidate(File apk, Context context, String bestPath,
                                                         Set<Integer> required,
                                                         List<String> warnings) {
        List<Integer> missing = new ArrayList<>();
        if (bestPath == null) {
            missing.addAll(required);
            return missing;
        }
        File directory = tempDirectory(context, warnings);
        if (directory == null) {
            missing.addAll(required);
            return missing;
        }
        File temporary = null;
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(bestPath);
            if (entry == null) {
                missing.addAll(required);
                return missing;
            }
            temporary = File.createTempFile("slg-font-", ".tmp", directory);
            copyFont(zip, entry, temporary, entry.getCompressedSize());
            Object[] bridge = createPaint(temporary);
            Method hasGlyph = (Method) bridge[1];
            Object paint = bridge[0];
            for (Integer codePoint : required) {
                if (!hasGlyph(paint, hasGlyph, codePoint)) {
                    missing.add(codePoint);
                }
            }
        } catch (Exception error) {
            warnings.add("font_preflight_best_font_recheck_failed");
            missing.addAll(required);
        } finally {
            if (temporary != null && temporary.exists() && !temporary.delete()) {
                warnings.add("font_preflight_temp_cleanup_failed");
            }
        }
        return missing;
    }

    private static int countCovered(File font, Set<Integer> required) throws Exception {
        Object[] bridge = createPaint(font);
        Object paint = bridge[0];
        Method hasGlyph = (Method) bridge[1];
        int covered = 0;
        for (Integer codePoint : required) {
            if (hasGlyph(paint, hasGlyph, codePoint)) {
                covered++;
            }
        }
        return covered;
    }

    private static Object[] createPaint(File font) throws Exception {
        // The Android runtime calls Typeface.createFromFile and Paint.hasGlyph here.
        // Reflection keeps the source compatible with the repository's small JVM stubs.
        Class<?> typefaceClass = Class.forName("android.graphics.Typeface");
        Method createFromFile = typefaceClass.getMethod("createFromFile", String.class);
        Object typeface = createFromFile.invoke(null, font.getAbsolutePath());
        Class<?> paintClass = Class.forName("android.graphics.Paint");
        Object paint = paintClass.getConstructor().newInstance();
        Method setTypeface = paintClass.getMethod("setTypeface", typefaceClass);
        setTypeface.invoke(paint, typeface);
        Method hasGlyph = paintClass.getMethod("hasGlyph", String.class);
        return new Object[]{paint, hasGlyph};
    }

    private static boolean hasGlyph(Object paint, Method method, int codePoint) throws Exception {
        String value = new String(Character.toChars(codePoint));
        try {
            return Boolean.TRUE.equals(method.invoke(paint, value));
        } catch (InvocationTargetException error) {
            return false;
        }
    }

    private static long copyFont(ZipFile zip, ZipEntry entry, File target, long compressedSize)
            throws IOException {
        long copied = 0;
        try (InputStream input = zip.getInputStream(entry);
             FileOutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[COPY_BUFFER_SIZE];
            int count;
            while ((count = input.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                copied += count;
                if (copied > MAX_FONT_BYTES) {
                    throw new IOException("font size limit");
                }
                if (compressedSize > 0) {
                    RenpyResourceLimits.checkInflateRatio(compressedSize, copied);
                }
                output.write(buffer, 0, count);
            }
            output.flush();
        }
        return copied;
    }

    private static File tempDirectory(Context context, List<String> warnings) {
        File directory = null;
        try {
            directory = context.getCacheDir();
            if (directory == null) {
                directory = context.getFilesDir();
            }
            if (directory == null || (!directory.exists() && !directory.mkdirs())
                    || !directory.isDirectory()) {
                return null;
            }
            return directory;
        } catch (RuntimeException error) {
            warnings.add("font_preflight_temp_directory_failed");
            return null;
        }
    }

    private static boolean isFontPath(String path) {
        return path.endsWith(".ttf") || path.endsWith(".otf") || path.endsWith(".ttc");
    }

    private static boolean isChineseStylePath(String path) {
        return path.contains("/x-tl/x-chinese/") || path.contains("/tl/chinese/")
                || path.contains("/x-tl/x-schinese/") || path.contains("/tl/schinese/");
    }

    private static boolean isLineBreakEvidencePath(String path) {
        return path.endsWith(".rpy") || path.endsWith(".rpyc") || path.endsWith(".txt")
                || path.endsWith(".json");
    }

    private static boolean containsLineBreakEvidence(ZipFile zip, ZipEntry entry,
                                                      List<String> warnings) {
        try (InputStream input = zip.getInputStream(entry);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[COPY_BUFFER_SIZE];
            int count;
            int total = 0;
            while (total < MAX_EVIDENCE_BYTES
                    && (count = input.read(buffer, 0, Math.min(buffer.length,
                    MAX_EVIDENCE_BYTES - total))) != -1) {
                output.write(buffer, 0, count);
                total += count;
            }
            String text = new String(output.toByteArray(), StandardCharsets.UTF_8).toLowerCase();
            return text.contains("line_break") || text.contains("east_asian")
                    || text.contains("word_break") || text.contains("cjk");
        } catch (IOException error) {
            warnings.add("font_preflight_line_break_evidence_unreadable");
            return false;
        }
    }

    public static final class FontReport {
        public final List<String> candidateFonts;
        public final String bestFontPath;
        public final int requiredCount;
        public final int coveredCount;
        public final List<Integer> missingCodePoints;
        public final boolean hasChineseStyleBucket;
        public final boolean hasEastAsianLineBreakEvidence;
        public final List<String> warnings;

        FontReport(List<String> candidateFonts, String bestFontPath, int requiredCount,
                   int coveredCount, List<Integer> missingCodePoints,
                   boolean hasChineseStyleBucket, boolean hasEastAsianLineBreakEvidence,
                   List<String> warnings) {
            this.candidateFonts = Collections.unmodifiableList(new ArrayList<>(candidateFonts));
            this.bestFontPath = bestFontPath;
            this.requiredCount = requiredCount;
            this.coveredCount = coveredCount;
            this.missingCodePoints = Collections.unmodifiableList(new ArrayList<>(missingCodePoints));
            this.hasChineseStyleBucket = hasChineseStyleBucket;
            this.hasEastAsianLineBreakEvidence = hasEastAsianLineBreakEvidence;
            this.warnings = Collections.unmodifiableList(new ArrayList<>(warnings));
        }

        public boolean isComplete() {
            return missingCodePoints.isEmpty() && requiredCount == coveredCount;
        }
    }
}
