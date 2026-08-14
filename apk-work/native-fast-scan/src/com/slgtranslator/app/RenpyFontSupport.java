package com.slgtranslator.app;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
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
    public static final int MAX_REQUIRED_CODE_POINTS = 4096;
    private static final int MAX_EVIDENCE_BYTES = 1024 * 1024;
    private static final int COPY_BUFFER_SIZE = 8192;
    private static final int MAX_CMAP_BYTES = 8 * 1024 * 1024;

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

    /**
     * Returns every non-ASCII code point used by translated values, excluding
     * private-use-area glyphs. Source games carry PUA code points in their own
     * icon fonts (and ML Kit echoes them through); they render through the
     * game's icon font, not the text font, so they must not gate text-font
     * coverage.
     */
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
                if (codePoint > 0x7f && !isPrivateUse(codePoint)) {
                    result.add(codePoint);
                }
                offset += Character.charCount(codePoint);
            }
        }
        return result;
    }

    private static boolean isPrivateUse(int codePoint) {
        return (codePoint >= 0xE000 && codePoint <= 0xF8FF)
                || (codePoint >= 0xF0000 && codePoint <= 0xFFFFD)
                || (codePoint >= 0x100000 && codePoint <= 0x10FFFD);
    }

    public static FontReport inspect(Context context, File apk, Set<Integer> requiredCodePoints) {
        TreeSet<Integer> required = new TreeSet<>();
        boolean requiredLimitHit = false;
        if (requiredCodePoints != null) {
            for (Integer codePoint : requiredCodePoints) {
                if (required.size() >= MAX_REQUIRED_CODE_POINTS) {
                    requiredLimitHit = true;
                    break;
                }
                if (codePoint != null && codePoint >= 0 && codePoint <= 0x10ffff
                        && !(codePoint >= 0xd800 && codePoint <= 0xdfff)) {
                    required.add(codePoint);
                }
            }
        }
        List<String> candidates = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        if (requiredLimitHit) {
            warnings.add("font_preflight_required_code_point_limit");
        }
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
            FontCmap cmap = FontCmap.load(temporary);
            Object[] bridge = createPaint(temporary);
            Method hasGlyph = (Method) bridge[1];
            Object paint = bridge[0];
            for (Integer codePoint : required) {
                if (!hasGlyph(temporary, cmap, paint, hasGlyph, codePoint)) {
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
        FontCmap cmap = FontCmap.load(font);
        Object paint = null;
        Method hasGlyph = null;
        if (cmap == null) {
            Object[] bridge = createPaint(font);
            paint = bridge[0];
            hasGlyph = (Method) bridge[1];
        }
        int covered = 0;
        for (Integer codePoint : required) {
            if (hasGlyph(font, cmap, paint, hasGlyph, codePoint)) {
                covered++;
            }
        }
        return covered;
    }

    /** Checks a standalone font file without consulting Android's fallback fonts. */
    static boolean coversRequiredCodePoints(File font, Set<Integer> required) {
        if (font == null || !font.isFile()) {
            return false;
        }
        try {
            FontCmap cmap = FontCmap.load(font);
            Object paint = null;
            Method hasGlyph = null;
            if (cmap == null) {
                Object[] bridge = createPaint(font);
                paint = bridge[0];
                hasGlyph = (Method) bridge[1];
            }
            if (required == null) {
                return true;
            }
            for (Integer codePoint : required) {
                if (codePoint == null || !hasGlyph(font, cmap, paint, hasGlyph, codePoint)) {
                    return false;
                }
            }
            return true;
        } catch (Exception error) {
            return false;
        }
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

    private static boolean hasGlyph(File font, FontCmap cmap, Object paint, Method method,
                                    int codePoint) throws Exception {
        if (cmap != null) {
            return cmap.contains(codePoint);
        }
        String value = new String(Character.toChars(codePoint));
        try {
            return Boolean.TRUE.equals(method.invoke(paint, value));
        } catch (InvocationTargetException error) {
            return false;
        }
    }

    /**
     * Reads the font's own cmap table. Android Paint.hasGlyph() is deliberately
     * not authoritative here because it may report a glyph supplied by a
     * system fallback font rather than by the APK-local typeface.
     */
    private static final class FontCmap {
        private static final long SFNT_TRUE_TYPE = 0x00010000L;
        private static final long SFNT_OTTO = 0x4f54544fL;
        private static final long SFNT_TRUE = 0x74727565L;
        private static final long SFNT_TYP1 = 0x74797031L;
        private static final long SFNT_TTCF = 0x74746366L;

        private final List<Subtable> subtables;

        private FontCmap(List<Subtable> subtables) {
            this.subtables = subtables;
        }

        static FontCmap load(File font) throws IOException {
            if (font == null || !font.isFile()) {
                return new FontCmap(Collections.<Subtable>emptyList());
            }
            try (RandomAccessFile input = new RandomAccessFile(font, "r")) {
                long fileLength = input.length();
                if (fileLength < 12) {
                    return null;
                }
                long signature = u32(input, 0);
                if (signature == SFNT_TTCF) {
                    return loadCollection(input, fileLength);
                }
                if (!isSfntSignature(signature)) {
                    // Keep the small JVM marker fixtures working; real font
                    // files always take the cmap path above.
                    return null;
                }
                return new FontCmap(loadFace(input, fileLength, 0));
            }
        }

        private static FontCmap loadCollection(RandomAccessFile input, long fileLength)
                throws IOException {
            if (fileLength < 16) {
                return new FontCmap(Collections.<Subtable>emptyList());
            }
            long count = u32(input, 8);
            if (count > 128 || 12L + count * 4L > fileLength) {
                return new FontCmap(Collections.<Subtable>emptyList());
            }
            List<Subtable> result = new ArrayList<>();
            for (int index = 0; index < (int) count; index++) {
                long offset = u32(input, 12L + index * 4L);
                if (offset > fileLength - 12) {
                    continue;
                }
                result.addAll(loadFace(input, fileLength, offset));
            }
            return new FontCmap(result);
        }

        private static List<Subtable> loadFace(RandomAccessFile input, long fileLength,
                                               long faceOffset) throws IOException {
            if (faceOffset < 0 || faceOffset > fileLength - 12
                    || !isSfntSignature(u32(input, faceOffset))) {
                return Collections.emptyList();
            }
            int tableCount = u16(input, faceOffset + 4);
            if (tableCount < 0 || tableCount > 4096
                    || faceOffset + 12L + tableCount * 16L > fileLength) {
                return Collections.emptyList();
            }
            long cmapOffset = -1;
            long cmapLength = -1;
            for (int index = 0; index < tableCount; index++) {
                long record = faceOffset + 12L + index * 16L;
                if (tag(input, record).equals("cmap")) {
                    cmapOffset = u32(input, record + 8);
                    cmapLength = u32(input, record + 12);
                    break;
                }
            }
            if (cmapOffset < 0 || cmapLength <= 0 || cmapLength > MAX_CMAP_BYTES
                    || cmapOffset > fileLength - cmapLength) {
                return Collections.emptyList();
            }
            byte[] cmap = new byte[(int) cmapLength];
            input.seek(cmapOffset);
            input.readFully(cmap);
            return parseSubtables(cmap);
        }

        private static List<Subtable> parseSubtables(byte[] cmap) {
            if (cmap.length < 4) {
                return Collections.emptyList();
            }
            int recordCount = u16(cmap, 2);
            if (recordCount < 0 || 4L + recordCount * 8L > cmap.length) {
                return Collections.emptyList();
            }
            List<Subtable> result = new ArrayList<>();
            for (int index = 0; index < recordCount; index++) {
                int record = 4 + index * 8;
                long offset = u32(cmap, record + 4);
                if (offset < 0 || offset > cmap.length - 2) {
                    continue;
                }
                int format = u16(cmap, (int) offset);
                int length = subtableLength(cmap, (int) offset, format);
                if (length <= 0 || offset + length > cmap.length) {
                    continue;
                }
                byte[] subtable = new byte[length];
                System.arraycopy(cmap, (int) offset, subtable, 0, length);
                result.add(new Subtable(format, subtable));
            }
            return result;
        }

        private static int subtableLength(byte[] data, int offset, int format) {
            if (format == 12 || format == 13) {
                if (offset + 8 > data.length) {
                    return -1;
                }
                long length = u32(data, offset + 4);
                return length > Integer.MAX_VALUE ? -1 : (int) length;
            }
            if (format == 0 || format == 4 || format == 6) {
                if (offset + 4 > data.length) {
                    return -1;
                }
                return u16(data, offset + 2);
            }
            return -1;
        }

        boolean contains(int codePoint) {
            if (codePoint < 0 || codePoint > 0x10ffff
                    || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
                return false;
            }
            for (Subtable subtable : subtables) {
                if (subtable.contains(codePoint)) {
                    return true;
                }
            }
            return false;
        }

        private static boolean isSfntSignature(long value) {
            return value == SFNT_TRUE_TYPE || value == SFNT_OTTO
                    || value == SFNT_TRUE || value == SFNT_TYP1;
        }

        private static String tag(RandomAccessFile input, long offset) throws IOException {
            byte[] bytes = new byte[4];
            input.seek(offset);
            input.readFully(bytes);
            return new String(bytes, StandardCharsets.US_ASCII);
        }

        private static int u16(RandomAccessFile input, long offset) throws IOException {
            input.seek(offset);
            return ((input.readUnsignedByte() << 8) | input.readUnsignedByte());
        }

        private static long u32(RandomAccessFile input, long offset) throws IOException {
            input.seek(offset);
            return ((long) input.readUnsignedByte() << 24)
                    | ((long) input.readUnsignedByte() << 16)
                    | ((long) input.readUnsignedByte() << 8)
                    | input.readUnsignedByte();
        }

        private static int u16(byte[] data, int offset) {
            return ((data[offset] & 0xff) << 8) | (data[offset + 1] & 0xff);
        }

        private static long u32(byte[] data, int offset) {
            return ((long) (data[offset] & 0xff) << 24)
                    | ((long) (data[offset + 1] & 0xff) << 16)
                    | ((long) (data[offset + 2] & 0xff) << 8)
                    | (data[offset + 3] & 0xffL);
        }

        private static final class Subtable {
            private final int format;
            private final byte[] data;

            Subtable(int format, byte[] data) {
                this.format = format;
                this.data = data;
            }

            boolean contains(int codePoint) {
                if (format == 12 || format == 13) {
                    return containsFormat12(codePoint);
                }
                if (format == 4) {
                    return codePoint <= 0xffff && containsFormat4(codePoint);
                }
                if (format == 6) {
                    return containsFormat6(codePoint);
                }
                if (format == 0) {
                    return codePoint <= 0xff && data.length > 6
                            && (data[6 + codePoint] & 0xff) != 0;
                }
                return false;
            }

            private boolean containsFormat12(int codePoint) {
                if (data.length < 16) {
                    return false;
                }
                long length = u32(data, 4);
                long groups = u32(data, 12);
                if (length > data.length || groups > (data.length - 16L) / 12L) {
                    return false;
                }
                int low = 0;
                int high = (int) groups - 1;
                while (low <= high) {
                    int middle = (low + high) >>> 1;
                    int offset = 16 + middle * 12;
                    long start = u32(data, offset);
                    long end = u32(data, offset + 4);
                    if (codePoint < start) {
                        high = middle - 1;
                    } else if (codePoint > end) {
                        low = middle + 1;
                    } else {
                        long glyph = u32(data, offset + 8) + (codePoint - start);
                        return glyph != 0;
                    }
                }
                return false;
            }

            private boolean containsFormat4(int codePoint) {
                if (data.length < 16) {
                    return false;
                }
                int segCount = u16(data, 6) / 2;
                if (segCount <= 0 || 16L + segCount * 8L > data.length) {
                    return false;
                }
                int endCodes = 14;
                int startCodes = endCodes + segCount * 2 + 2;
                int idDeltas = startCodes + segCount * 2;
                int idRangeOffsets = idDeltas + segCount * 2;
                for (int index = 0; index < segCount; index++) {
                    int end = u16(data, endCodes + index * 2);
                    if (codePoint > end) {
                        continue;
                    }
                    int start = u16(data, startCodes + index * 2);
                    if (codePoint < start) {
                        return false;
                    }
                    int delta = (short) u16(data, idDeltas + index * 2);
                    int range = u16(data, idRangeOffsets + index * 2);
                    if (range == 0) {
                        return ((codePoint + delta) & 0xffff) != 0;
                    }
                    int rangeAddress = idRangeOffsets + index * 2;
                    long glyphAddress = rangeAddress + range + 2L * (codePoint - start);
                    if (glyphAddress < 0 || glyphAddress + 2 > data.length) {
                        return false;
                    }
                    int glyph = u16(data, (int) glyphAddress);
                    return glyph != 0 && ((glyph + delta) & 0xffff) != 0;
                }
                return false;
            }

            private boolean containsFormat6(int codePoint) {
                if (data.length < 10) {
                    return false;
                }
                int first = u16(data, 6);
                int count = u16(data, 8);
                if (codePoint < first || codePoint - first >= count
                        || 10L + count * 2L > data.length) {
                    return false;
                }
                return u16(data, 10 + (codePoint - first) * 2) != 0;
            }
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

        /** Returns a stable diagnostic code for UI classification and support logs. */
        public String failureCode() {
            String[] budgetCodes = {
                    "font_preflight_total_size_limit",
                    "font_preflight_font_size_limit",
                    "font_preflight_ratio_limit",
                    "font_preflight_required_code_point_limit"
            };
            for (String code : budgetCodes) {
                if (warnings.contains(code)) {
                    return code;
                }
            }
            if (!missingCodePoints.isEmpty() || requiredCount != coveredCount) {
                return "renpy_font_missing_glyphs";
            }
            for (String warning : warnings) {
                if (warning != null && warning.startsWith("font_preflight_")) {
                    return warning;
                }
            }
            return "";
        }

        public boolean isComplete() {
            return missingCodePoints.isEmpty() && requiredCount == coveredCount
                    && !warnings.contains("font_preflight_required_code_point_limit");
        }
    }
}
