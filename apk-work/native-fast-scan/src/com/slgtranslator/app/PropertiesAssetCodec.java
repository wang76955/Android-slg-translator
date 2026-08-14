package com.slgtranslator.app;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java-properties asset codec with a deterministic continuation/escape
 * parser. Keys stay logical (escapes decoded); values are rewritten through
 * the same escape rules. Duplicate keys are diagnosed and block writing.
 * {@code java.util.Properties.store()} is intentionally never used.
 */
public final class PropertiesAssetCodec implements StructuredTextAdapter.AssetCodec {

    public static final String CODE_DUPLICATE_KEY = "structured_properties_duplicate_key";
    public static final String CODE_PARSE_FAILED = "structured_properties_parse_failed";

    private final StructuredTextAdapter adapter;

    public PropertiesAssetCodec(StructuredTextAdapter adapter) {
        this.adapter = adapter;
    }

    @Override
    public String id() {
        return "properties";
    }

    @Override
    public boolean detect(String path, byte[] bytes) {
        if (path == null || !StructuredTextAdapter.lowerPath(path).endsWith(".properties")) {
            return false;
        }
        if (!StructuredTextAdapter.isUtf8Clean(bytes)
                || StructuredTextAdapter.hasReplacementChar(bytes)) {
            return false;
        }
        try {
            parseEntries(new String(bytes, StandardCharsets.UTF_8));
            return true;
        } catch (IOException error) {
            return false;
        }
    }

    /** One logical entry plus its raw source span. */
    static final class Entry {
        final int rawStart;
        final int rawEnd;
        final String key;
        final String value;
        final String rawKey;

        Entry(int rawStart, int rawEnd, String key, String value, String rawKey) {
            this.rawStart = rawStart;
            this.rawEnd = rawEnd;
            this.key = key;
            this.value = value;
            this.rawKey = rawKey;
        }
    }

    private static final class ParseResult {
        final List<Entry> entries;

        ParseResult(List<Entry> entries) {
            this.entries = entries;
        }
    }

    @Override
    public List<StructuredTextRecord> extract(String owner, String path, byte[] bytes)
            throws IOException {
        ParseResult result = parseEntries(new String(bytes, StandardCharsets.UTF_8));
        List<StructuredTextRecord> records = new ArrayList<>();
        int counter = 0;
        for (Entry entry : result.entries) {
            // Duplicate keys are diagnosed during parsing, so every logical
            // key appears once; the occurrence suffix keeps the keyPath
            // shape stable for future duplicate-tolerant formats.
            records.add(adapter.record(owner, path, id(),
                    entry.key + "#1", entry.value, counter));
            counter++;
        }
        return records;
    }

    @Override
    public byte[] rewrite(byte[] bytes, Map<String, String> translations)
            throws IOException {
        String text = new String(bytes, StandardCharsets.UTF_8);
        ParseResult result = parseEntries(text);
        StringBuilder out = new StringBuilder(text.length() + 64);
        int cursor = 0;
        for (Entry entry : result.entries) {
            String translated = translations.get(entry.key + "#1");
            out.append(text, cursor, entry.rawStart);
            if (translated != null) {
                out.append(entry.rawKey).append("=").append(escapeValue(translated));
            } else {
                out.append(text, entry.rawStart, entry.rawEnd);
            }
            cursor = entry.rawEnd;
        }
        out.append(text, cursor, text.length());
        return out.toString().getBytes(StandardCharsets.UTF_8);
    }

    @Override
    public ValidationResult verify(byte[] original, byte[] rewritten,
                                   List<StructuredTextRecord> records,
                                   Map<String, String> translations) throws IOException {
        ParseResult before;
        ParseResult after;
        try {
            before = parseEntries(new String(original, StandardCharsets.UTF_8));
            after = parseEntries(new String(rewritten, StandardCharsets.UTF_8));
        } catch (IOException error) {
            return ValidationResult.fail(CODE_PARSE_FAILED, safeMessage(error));
        }
        if (before.entries.size() != after.entries.size()) {
            return ValidationResult.fail("writer_output_invalid", "entry count changed");
        }
        for (int index = 0; index < before.entries.size(); index++) {
            Entry b = before.entries.get(index);
            Entry a = after.entries.get(index);
            if (!b.key.equals(a.key)) {
                return ValidationResult.fail("writer_output_invalid",
                        "key order or identity changed at index " + index);
            }
            String expected = translations.get(b.key + "#1");
            if (expected != null) {
                if (!expected.equals(a.value)) {
                    return ValidationResult.fail("writer_output_invalid",
                            "translation mismatch at " + b.key);
                }
            } else if (!safe(b.value).equals(safe(a.value))) {
                return ValidationResult.fail("writer_output_invalid",
                        "untouched value changed at " + b.key);
            }
        }
        return ValidationResult.ok();
    }

    private static ParseResult parseEntries(String text) throws IOException {
        List<Entry> entries = new ArrayList<>();
        int cursor = 0;
        while (cursor < text.length()) {
            int lineEnd = endOfLine(text, cursor);
            String line = text.substring(cursor, lineEnd);
            String trimmed = line.trim();
            if (trimmed.isEmpty() || trimmed.startsWith("#") || trimmed.startsWith("!")) {
                cursor = advancePastLine(text, lineEnd);
                continue;
            }
            int separator = findSeparator(line);
            if (separator < 0) {
                cursor = advancePastLine(text, lineEnd);
                continue;
            }
            int entryStart = cursor;
            String rawKey = line.substring(0, separator).trim();
            String key = decodeEscapes(rawKey);
            StringBuilder rawValue = new StringBuilder();
            String firstSegment = line.substring(separator + 1);
            int leading = 0;
            while (leading < firstSegment.length()
                    && isLineWhitespace(firstSegment.charAt(leading))) {
                leading++;
            }
            rawValue.append(firstSegment.substring(leading));
            cursor = advancePastLine(text, lineEnd);
            int finalLineEnd = lineEnd;
            // A line whose TRAILING backslash count is odd continues on the
            // next physical line; the marker backslash is dropped and the
            // continuation's leading whitespace is stripped.
            while (cursor < text.length()
                    && countTrailingBackslashes(line) % 2 == 1) {
                rawValue.deleteCharAt(rawValue.length() - 1);
                int continuationEnd = endOfLine(text, cursor);
                String continuation = text.substring(cursor, continuationEnd);
                int whitespace = 0;
                while (whitespace < continuation.length()
                        && isLineWhitespace(continuation.charAt(whitespace))) {
                    whitespace++;
                }
                rawValue.append('\n').append(continuation.substring(whitespace));
                line = continuation;
                cursor = advancePastLine(text, continuationEnd);
                finalLineEnd = continuationEnd;
            }
            // The entry span excludes its own line terminator so the gap
            // between entries re-emits the original newline sequence.
            int entryEnd = cursor;
            if (finalLineEnd < text.length()) {
                entryEnd = finalLineEnd;
                if (finalLineEnd > 0 && text.charAt(finalLineEnd - 1) == '\r') {
                    entryEnd = finalLineEnd - 1;
                }
            }
            String value = decodeEscapes(rawValue.toString());
            if (key.isEmpty()) {
                continue;
            }
            for (Entry existing : entries) {
                if (existing.key.equals(key)) {
                    throw new IOException(CODE_DUPLICATE_KEY + ": key '" + key + "'");
                }
            }
            entries.add(new Entry(entryStart, entryEnd, key, value, rawKey));
        }
        return new ParseResult(entries);
    }

    /** Trailing backslashes of a physical line (CR already stripped). */
    private static int countTrailingBackslashes(String line) {
        String content = line.endsWith("\r") ? line.substring(0, line.length() - 1) : line;
        int count = 0;
        for (int index = content.length() - 1; index >= 0; index--) {
            if (content.charAt(index) == '\\') {
                count++;
            } else {
                break;
            }
        }
        return count;
    }

    private static boolean isLineWhitespace(char value) {
        return value == ' ' || value == '\t' || value == '\f';
    }

    /** First unescaped '=', ':' or whitespace ends the key. */
    private static int findSeparator(String line) {
        for (int index = 0; index < line.length(); index++) {
            char value = line.charAt(index);
            if (value == '\\') {
                index++;
                continue;
            }
            if (value == '=' || value == ':' || isLineWhitespace(value)) {
                return index;
            }
        }
        return -1;
    }

    private static String decodeEscapes(String value) {
        StringBuilder out = new StringBuilder(value.length());
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            if (current != '\\' || index + 1 >= value.length()) {
                out.append(current);
                continue;
            }
            char next = value.charAt(++index);
            switch (next) {
                case 't':
                    out.append('\t');
                    break;
                case 'n':
                    out.append('\n');
                    break;
                case 'r':
                    out.append('\r');
                    break;
                case 'f':
                    out.append('\f');
                    break;
                case 'u':
                    if (index + 4 < value.length()) {
                        String hex = value.substring(index + 1, index + 5);
                        try {
                            out.append((char) Integer.parseInt(hex, 16));
                            index += 4;
                            break;
                        } catch (NumberFormatException invalid) {
                            out.append('u');
                            break;
                        }
                    }
                    out.append('u');
                    break;
                default:
                    out.append(next);
                    break;
            }
        }
        return out.toString();
    }

    private static String escapeValue(String value) {
        StringBuilder out = new StringBuilder(value.length() + 8);
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            switch (current) {
                case '\\':
                    out.append("\\\\");
                    break;
                case '\t':
                    out.append("\\t");
                    break;
                case '\n':
                    out.append("\\n");
                    break;
                case '\r':
                    out.append("\\r");
                    break;
                case '\f':
                    out.append("\\f");
                    break;
                default:
                    out.append(current);
                    break;
            }
        }
        return out.toString();
    }

    private static int endOfLine(String text, int from) {
        int index = text.indexOf('\n', from);
        return index < 0 ? text.length() : index;
    }

    private static int advancePastLine(String text, int lineEnd) {
        return lineEnd < text.length() ? lineEnd + 1 : lineEnd;
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? error.toString() : message;
    }
}
