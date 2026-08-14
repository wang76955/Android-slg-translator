package com.slgtranslator.app;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.csv.CSVRecord;

import java.io.IOException;
import java.io.StringReader;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * CSV/TSV asset codec. Preserves the delimiter, quote behaviour, header,
 * empty fields, line endings and column counts; keys are
 * {@code row:<n>/column:<header-or-index>}.
 */
public final class DelimitedAssetCodec implements StructuredTextAdapter.AssetCodec {

    public static final String CODE_PARSE_FAILED = "structured_delimited_parse_failed";
    public static final String CODE_SHAPE_MISMATCH = "structured_delimited_shape_mismatch";

    private final StructuredTextAdapter adapter;
    private final String id;
    private final char delimiter;

    public DelimitedAssetCodec(StructuredTextAdapter adapter, String id, char delimiter) {
        this.adapter = adapter;
        this.id = id;
        this.delimiter = delimiter;
    }

    @Override
    public String id() {
        return id;
    }

    @Override
    public boolean detect(String path, byte[] bytes) {
        String lower = StructuredTextAdapter.lowerPath(path);
        if (id.equals("csv") && !lower.endsWith(".csv")) {
            return false;
        }
        if (id.equals("tsv") && !lower.endsWith(".tsv")) {
            return false;
        }
        if (!StructuredTextAdapter.isUtf8Clean(bytes)
                || StructuredTextAdapter.hasReplacementChar(bytes)) {
            return false;
        }
        try {
            List<List<String>> rows = parse(new String(bytes, StandardCharsets.UTF_8));
            return rows.size() >= 1 && consistentColumns(rows);
        } catch (IOException error) {
            return false;
        }
    }

    @Override
    public List<StructuredTextRecord> extract(String owner, String path, byte[] bytes)
            throws IOException {
        List<List<String>> rows;
        try {
            rows = parse(new String(bytes, StandardCharsets.UTF_8));
        } catch (IOException error) {
            throw new IOException(CODE_PARSE_FAILED + ": " + safeMessage(error), error);
        }
        if (!consistentColumns(rows)) {
            throw new IOException(CODE_SHAPE_MISMATCH + ": inconsistent column counts");
        }
        List<String> header = headerRow(rows);
        List<StructuredTextRecord> records = new ArrayList<>();
        int counter = 0;
        int start = header == null ? 0 : 1;
        for (int row = start; row < rows.size(); row++) {
            List<String> cells = rows.get(row);
            for (int column = 0; column < cells.size(); column++) {
                String cell = cells.get(column);
                if (cell == null || cell.isEmpty()) {
                    continue;
                }
                String columnKey = header == null
                        ? String.valueOf(column)
                        : header.get(column);
                String keyPath = "row:" + row + "/column:" + columnKey;
                records.add(adapter.record(owner, path, id(), keyPath, cell, counter));
                counter++;
            }
        }
        return records;
    }

    @Override
    public byte[] rewrite(byte[] bytes, Map<String, String> translations)
            throws IOException {
        String text = new String(bytes, StandardCharsets.UTF_8);
        List<List<String>> rows;
        try {
            rows = parse(text);
        } catch (IOException error) {
            throw new IOException(CODE_PARSE_FAILED + ": " + safeMessage(error), error);
        }
        if (!consistentColumns(rows)) {
            throw new IOException(CODE_SHAPE_MISMATCH + ": inconsistent column counts");
        }
        List<String> header = headerRow(rows);
        for (Map.Entry<String, String> entry : translations.entrySet()) {
            int[] position = parseKey(entry.getKey(), rows.size(), header);
            if (position == null) {
                throw new IOException(CODE_SHAPE_MISMATCH + ": unknown key "
                        + entry.getKey());
            }
            rows.get(position[0]).set(position[1], entry.getValue());
        }
        return print(rows, lineEndingOf(text)).getBytes(StandardCharsets.UTF_8);
    }

    @Override
    public ValidationResult verify(byte[] original, byte[] rewritten,
                                   List<StructuredTextRecord> records,
                                   Map<String, String> translations) throws IOException {
        List<List<String>> before;
        List<List<String>> after;
        try {
            before = parse(new String(original, StandardCharsets.UTF_8));
            after = parse(new String(rewritten, StandardCharsets.UTF_8));
        } catch (IOException error) {
            return ValidationResult.fail(CODE_PARSE_FAILED, safeMessage(error));
        }
        if (!consistentColumns(before) || !consistentColumns(after)) {
            return ValidationResult.fail(CODE_SHAPE_MISMATCH, "inconsistent columns");
        }
        if (before.size() != after.size()) {
            return ValidationResult.fail("writer_output_invalid", "row count changed");
        }
        if (!lineEndingOf(new String(original, StandardCharsets.UTF_8))
                .equals(lineEndingOf(new String(rewritten, StandardCharsets.UTF_8)))) {
            return ValidationResult.fail("writer_output_invalid", "line ending changed");
        }
        List<String> header = headerRow(before);
        for (int row = 0; row < before.size(); row++) {
            if (before.get(row).size() != after.get(row).size()) {
                return ValidationResult.fail("writer_output_invalid",
                        "column count changed at row " + row);
            }
            for (int column = 0; column < before.get(row).size(); column++) {
                String oldCell = before.get(row).get(column);
                String newCell = after.get(row).get(column);
                String columnKey = header == null
                        ? String.valueOf(column) : header.get(column);
                String expected = translations.get("row:" + row + "/column:" + columnKey);
                if (expected != null) {
                    if (!expected.equals(newCell)) {
                        return ValidationResult.fail("writer_output_invalid",
                                "translation mismatch at row " + row + " column " + column);
                    }
                } else if (!safe(oldCell).equals(safe(newCell))) {
                    return ValidationResult.fail("writer_output_invalid",
                            "untouched cell changed at row " + row + " column " + column);
                }
            }
        }
        return ValidationResult.ok();
    }

    private List<List<String>> parse(String text) throws IOException {
        CSVFormat format = CSVFormat.Builder.create(CSVFormat.DEFAULT)
                .setDelimiter(delimiter)
                .setQuote('"')
                .build();
        List<List<String>> rows = new ArrayList<>();
        try (CSVParser parser = format.parse(new StringReader(text))) {
            for (CSVRecord record : parser) {
                List<String> cells = new ArrayList<>();
                for (String value : record) {
                    cells.add(value == null ? "" : value);
                }
                rows.add(cells);
            }
        } catch (RuntimeException error) {
            throw new IOException(CODE_PARSE_FAILED + ": " + safeMessage(error), error);
        }
        return rows;
    }

    private String print(List<List<String>> rows, String lineEnding) throws IOException {
        CSVFormat format = CSVFormat.Builder.create(CSVFormat.DEFAULT)
                .setDelimiter(delimiter)
                .setQuote('"')
                .setRecordSeparator(lineEnding)
                .build();
        StringWriter buffer = new StringWriter();
        try (CSVPrinter printer = new CSVPrinter(buffer, format)) {
            for (List<String> row : rows) {
                printer.printRecord(row);
            }
        }
        return buffer.toString();
    }

    private static boolean consistentColumns(List<List<String>> rows) {
        if (rows.isEmpty()) {
            return false;
        }
        int width = rows.get(0).size();
        for (List<String> row : rows) {
            if (row.size() != width) {
                return false;
            }
        }
        return true;
    }

    private static List<String> headerRow(List<List<String>> rows) {
        if (rows.size() < 2) {
            return null;
        }
        List<String> first = rows.get(0);
        Set<String> names = new HashSet<>();
        for (String cell : first) {
            String value = cell == null ? "" : cell.trim();
            if (value.isEmpty() || !names.add(value)) {
                return null;
            }
        }
        return first;
    }

    /** Returns {row, column} for "row:<n>/column:<header-or-index>". */
    private int[] parseKey(String keyPath, int rowCount, List<String> header) {
        if (keyPath == null || !keyPath.startsWith("row:")) {
            return null;
        }
        int columnSlash = keyPath.indexOf("/column:");
        if (columnSlash < 0) {
            return null;
        }
        try {
            int row = Integer.parseInt(keyPath.substring(4, columnSlash));
            String columnKey = keyPath.substring(columnSlash + "/column:".length());
            if (row < 0 || row >= rowCount) {
                return null;
            }
            int column = -1;
            if (header != null) {
                for (int index = 0; index < header.size(); index++) {
                    if (columnKey.equals(header.get(index))) {
                        column = index;
                        break;
                    }
                }
            } else {
                column = Integer.parseInt(columnKey);
            }
            if (column < 0) {
                return null;
            }
            return new int[]{row, column};
        } catch (NumberFormatException invalid) {
            return null;
        }
    }

    private static String lineEndingOf(String text) {
        return text.indexOf("\r\n") >= 0 ? "\r\n" : "\n";
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? error.toString() : message;
    }
}
