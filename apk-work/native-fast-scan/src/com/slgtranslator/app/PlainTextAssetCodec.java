package com.slgtranslator.app;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Plain-text asset codec. Accepts only confirmable UTF-8 (optionally with a
 * UTF-8 BOM); ambiguous encodings (UTF-16 without BOM, invalid bytes,
 * embedded NULs) are excluded. Non-empty lines become translatable records
 * keyed by {@code line:<n>} (1-based); line endings are preserved.
 */
public final class PlainTextAssetCodec implements StructuredTextAdapter.AssetCodec {

    public static final String CODE_ENCODING = "structured_extraction_unavailable";
    public static final String CODE_PARSE_FAILED = "structured_text_parse_failed";

    private final StructuredTextAdapter adapter;

    public PlainTextAssetCodec(StructuredTextAdapter adapter) {
        this.adapter = adapter;
    }

    @Override
    public String id() {
        return "text";
    }

    @Override
    public boolean detect(String path, byte[] bytes) {
        if (path == null || !StructuredTextAdapter.lowerPath(path).endsWith(".txt")) {
            return false;
        }
        return confirmableUtf8(bytes);
    }

    static boolean confirmableUtf8(byte[] bytes) {
        if (bytes == null || bytes.length == 0) {
            return false;
        }
        if (bytes.length >= 2 && (bytes[0] & 0xff) == 0xff && (bytes[1] & 0xff) == 0xfe) {
            return false; // UTF-16 LE BOM
        }
        if (bytes.length >= 2 && (bytes[0] & 0xff) == 0xfe && (bytes[1] & 0xff) == 0xff) {
            return false; // UTF-16 BE BOM
        }
        if (bytes.length >= 4 && (bytes[0] & 0xff) == 0x00 && (bytes[1] & 0xff) == 0x00
                && (bytes[2] & 0xff) == 0xfe && (bytes[3] & 0xff) == 0xff) {
            return false; // UTF-32 BE BOM
        }
        if (bytes.length >= 4 && (bytes[0] & 0xff) == 0xff && (bytes[1] & 0xff) == 0xfe
                && (bytes[2] & 0xff) == 0x00 && (bytes[3] & 0xff) == 0x00) {
            return false; // UTF-32 LE BOM
        }
        if (!StructuredTextAdapter.isUtf8Clean(bytes)
                || StructuredTextAdapter.hasReplacementChar(bytes)) {
            return false;
        }
        for (byte value : bytes) {
            if (value == 0) {
                return false; // embedded NUL: binary, not confirmable text
            }
        }
        return true;
    }

    @Override
    public List<StructuredTextRecord> extract(String owner, String path, byte[] bytes)
            throws IOException {
        String text = textOf(bytes);
        List<StructuredTextRecord> records = new ArrayList<>();
        int counter = 0;
        int lineNumber = 0;
        int cursor = 0;
        while (cursor <= text.length()) {
            lineNumber++;
            int lineEnd = text.indexOf('\n', cursor);
            String line;
            if (lineEnd < 0) {
                line = text.substring(cursor);
                cursor = text.length() + 1;
            } else {
                line = text.substring(cursor, lineEnd);
                cursor = lineEnd + 1;
            }
            if (line.endsWith("\r")) {
                line = line.substring(0, line.length() - 1);
            }
            if (line.trim().isEmpty()) {
                continue;
            }
            records.add(adapter.record(owner, path, id(),
                    "line:" + lineNumber, line, counter));
            counter++;
        }
        return records;
    }

    @Override
    public byte[] rewrite(byte[] bytes, Map<String, String> translations)
            throws IOException {
        boolean bom = StructuredTextAdapter.hasUtf8Bom(bytes);
        String text = textOf(bytes);
        String lineEnding = text.indexOf("\r\n") >= 0 ? "\r\n" : "\n";
        StringBuilder out = new StringBuilder(text.length() + 64);
        int lineNumber = 0;
        int cursor = 0;
        boolean first = true;
        while (cursor <= text.length()) {
            lineNumber++;
            int lineEnd = text.indexOf('\n', cursor);
            String raw;
            if (lineEnd < 0) {
                raw = text.substring(cursor);
                cursor = text.length() + 1;
            } else {
                raw = text.substring(cursor, lineEnd);
                cursor = lineEnd + 1;
            }
            String line = raw.endsWith("\r") ? raw.substring(0, raw.length() - 1) : raw;
            String translated = translations.get("line:" + lineNumber);
            String replacement = translated != null ? translated : line;
            if (!first) {
                out.append(lineEnding);
            }
            out.append(replacement);
            first = false;
        }
        byte[] body = out.toString().getBytes(StandardCharsets.UTF_8);
        if (!bom) {
            return body;
        }
        byte[] withBom = new byte[body.length + 3];
        withBom[0] = (byte) 0xef;
        withBom[1] = (byte) 0xbb;
        withBom[2] = (byte) 0xbf;
        System.arraycopy(body, 0, withBom, 3, body.length);
        return withBom;
    }

    @Override
    public ValidationResult verify(byte[] original, byte[] rewritten,
                                   List<StructuredTextRecord> records,
                                   Map<String, String> translations) throws IOException {
        List<StructuredTextRecord> before = extract(
                records.isEmpty() ? "" : records.get(0).sourceOwner,
                records.isEmpty() ? "" : records.get(0).sourcePath, original);
        List<StructuredTextRecord> after = extract(
                records.isEmpty() ? "" : records.get(0).sourceOwner,
                records.isEmpty() ? "" : records.get(0).sourcePath, rewritten);
        Map<String, String> beforeByPath = new LinkedHashMap<>();
        Map<String, String> afterByPath = new LinkedHashMap<>();
        for (StructuredTextRecord record : before) {
            beforeByPath.put(record.keyPath, record.sourceText);
        }
        for (StructuredTextRecord record : after) {
            afterByPath.put(record.keyPath, record.sourceText);
        }
        if (!beforeByPath.keySet().equals(afterByPath.keySet())) {
            return ValidationResult.fail("writer_output_invalid",
                    "line set changed");
        }
        for (Map.Entry<String, String> entry : beforeByPath.entrySet()) {
            String expected = translations.get(entry.getKey());
            String actual = afterByPath.get(entry.getKey());
            if (expected != null) {
                if (!expected.equals(actual)) {
                    return ValidationResult.fail("writer_output_invalid",
                            "translation mismatch at " + entry.getKey());
                }
            } else if (!entry.getValue().equals(actual)) {
                return ValidationResult.fail("writer_output_invalid",
                        "untouched line changed at " + entry.getKey());
            }
        }
        return ValidationResult.ok();
    }

    private static String textOf(byte[] bytes) throws IOException {
        if (!confirmableUtf8(bytes)) {
            throw new IOException(CODE_ENCODING + ": not confirmable UTF-8 text");
        }
        int offset = StructuredTextAdapter.hasUtf8Bom(bytes) ? 3 : 0;
        return new String(bytes, offset, bytes.length - offset, StandardCharsets.UTF_8);
    }
}
