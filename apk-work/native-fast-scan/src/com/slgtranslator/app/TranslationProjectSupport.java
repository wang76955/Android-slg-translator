package com.slgtranslator.app;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Schema-1 translation project validation and Downloads persistence. */
public final class TranslationProjectSupport {
    public static final int SCHEMA_VERSION = 1;
    public static final int MAX_PROJECT_BYTES = 16 * 1024 * 1024;
    public static final int MAX_RECORDS = 200_000;
    public static final int MAX_FIELD_BYTES = 64 * 1024;

    private TranslationProjectSupport() {}

    public static final class ValidatedProject {
        public final String normalizedJson;
        public final String projectFingerprint;
        public final String adapterId;
        public final String sourceVersion;
        public final String sourceLang;
        public final String targetLang;
        public final int recordCount;
        private final List<Record> records;
        private final List<RenpyGlossaryValidator.GlossaryTerm> glossary;

        private ValidatedProject(String normalizedJson, String projectFingerprint,
                                 String adapterId, String sourceVersion,
                                 String sourceLang, String targetLang,
                                 List<Record> records,
                                 List<RenpyGlossaryValidator.GlossaryTerm> glossary) {
            this.normalizedJson = normalizedJson;
            this.projectFingerprint = projectFingerprint;
            this.adapterId = adapterId;
            this.sourceVersion = sourceVersion;
            this.sourceLang = sourceLang;
            this.targetLang = targetLang;
            this.records = records;
            this.glossary = glossary;
            this.recordCount = records.size();
        }
    }

    public static final class ImportResult {
        public final String acceptedRecordsJson;
        public final String reviewRecordsJson;
        public final int acceptedCount;
        public final int reviewCount;
        public final String reasonCode;

        private ImportResult(String acceptedRecordsJson, String reviewRecordsJson,
                             int acceptedCount, int reviewCount, String reasonCode) {
            this.acceptedRecordsJson = acceptedRecordsJson;
            this.reviewRecordsJson = reviewRecordsJson;
            this.acceptedCount = acceptedCount;
            this.reviewCount = reviewCount;
            this.reasonCode = reasonCode == null ? "" : reasonCode;
        }
    }

    private static final class Record {
        final Map<String, Object> fields;
        final String recordId;
        final String sourceOwner;
        final String sourcePath;
        final String resourceType;
        final String sourceKey;
        final String sourceText;
        final String translation;
        final String validation;

        Record(Map<String, Object> fields) {
            this.fields = new LinkedHashMap<>(fields);
            this.recordId = requiredString(fields, "recordId");
            this.sourceOwner = requiredString(fields, "sourceOwner");
            this.sourcePath = requiredString(fields, "sourcePath");
            this.resourceType = requiredString(fields, "resourceType");
            this.sourceKey = requiredString(fields, "sourceKey");
            this.sourceText = requiredString(fields, "sourceText");
            this.translation = requiredString(fields, "translation");
            this.validation = requiredString(fields, "validation");
        }
    }

    public static ValidatedProject validateProjectJson(String projectJson) {
        Map<String, Object> root = parseProject(projectJson);
        int schemaVersion = requiredInt(root, "schemaVersion");
        if (schemaVersion != SCHEMA_VERSION) {
            throw new ValidationException("translation_export_version_mismatch");
        }
        String sourceLang = requiredString(root, "sourceLang");
        String targetLang = requiredString(root, "targetLang");
        String fingerprint = requiredString(root, "projectFingerprint");
        String adapterId = requiredString(root, "adapterId");
        String sourceVersion = requiredString(root, "sourceVersion");
        List<RenpyGlossaryValidator.GlossaryTerm> glossary = readGlossary(root.get("glossary"));
        List<Record> records = readRecords(root.get("records"));
        if (records.isEmpty()) {
            throw new ValidationException("translation_export_empty");
        }
        return new ValidatedProject(toJson(root), fingerprint, adapterId, sourceVersion,
                sourceLang, targetLang, records, glossary);
    }

    public static ImportResult validateImport(String projectJson, String expectedFingerprint,
                                               String expectedAdapterId, String expectedSourceVersion,
                                               String expectedSourceLang, String expectedTargetLang,
                                               String currentRecordsJson) {
        ValidatedProject project;
        try {
            project = validateProjectJson(projectJson);
        } catch (ValidationException error) {
            if ("translation_export_empty".equals(error.code)) {
                return result(new ArrayList<Map<String, Object>>(),
                        new ArrayList<Map<String, Object>>(), error.code);
            }
            return result(new ArrayList<Map<String, Object>>(),
                    reviewForUnparsedProject(error.code), error.code);
        }

        Map<String, String> current = readCurrentRecords(currentRecordsJson);
        List<Record> acceptedCandidates = new ArrayList<>();
        List<Map<String, Object>> review = new ArrayList<>();
        Set<String> seenIds = new HashSet<>();
        boolean languageMismatch = !same(project.sourceLang, expectedSourceLang)
                || !same(project.targetLang, expectedTargetLang);
        boolean identityMismatch = !same(project.projectFingerprint, expectedFingerprint)
                || !same(project.adapterId, expectedAdapterId)
                || !same(project.sourceVersion, expectedSourceVersion);

        for (Record record : project.records) {
            String reason = null;
            if (languageMismatch) {
                reason = "translation_export_language_mismatch";
            } else if (identityMismatch) {
                reason = "translation_export_version_mismatch";
            } else if (!seenIds.add(record.recordId)) {
                reason = "translation_export_duplicate_record";
            } else if (!current.containsKey(record.recordId)) {
                reason = "translation_export_record_missing";
            } else if (!same(current.get(record.recordId), record.sourceText)) {
                reason = "translation_export_source_changed";
            } else if (!"APPROVED".equals(record.validation)) {
                reason = "translation_export_not_approved";
            } else if ("renpy".equals(expectedAdapterId)
                    && !RenpyTextValidator.validate(record.sourceText, record.translation).valid) {
                reason = "translation_export_validation_failed";
            } else if ("renpy".equals(expectedAdapterId)
                    && !RenpyGlossaryValidator.validate(record.sourceText, record.translation,
                    project.glossary).valid) {
                reason = "translation_export_glossary_validation_failed";
            }
            if (reason == null) {
                acceptedCandidates.add(record);
            } else {
                review.add(reviewRecord(record, reason));
            }
        }

        Map<String, List<Record>> bySource = new LinkedHashMap<>();
        for (Record record : acceptedCandidates) {
            List<Record> group = bySource.get(record.sourceText);
            if (group == null) {
                group = new ArrayList<>();
                bySource.put(record.sourceText, group);
            }
            group.add(record);
        }
        List<Map<String, Object>> accepted = new ArrayList<>();
        for (List<Record> group : bySource.values()) {
            Set<String> translations = new HashSet<>();
            for (Record record : group) translations.add(record.translation);
            if (translations.size() > 1) {
                for (Record record : group) {
                    review.add(reviewRecord(record, "translation_export_source_collision"));
                }
            } else {
                for (Record record : group) accepted.add(record.fields);
            }
        }
        String reasonCode = languageMismatch ? "translation_export_language_mismatch" : "";
        return result(accepted, review, reasonCode);
    }

    public static void exportTranslationProject(Context context, PluginCall call) {
        String projectJson = call.getString("projectJson");
        String requestedName = call.getString("fileName");
        ValidatedProject project;
        try {
            project = validateProjectJson(projectJson);
        } catch (ValidationException error) {
            call.reject(error.code);
            return;
        }
        String fileName = safeFileName(requestedName);
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                exportWithMediaStore(context, call, project, fileName);
            } else {
                exportWithLegacyStorage(context, call, project, fileName);
            }
        } catch (Exception error) {
            call.reject("translation_export_write_failed");
        }
    }

    public static void importTranslationProject(Context context, PluginCall call) {
        String projectJson = call.getString("projectJson");
        ImportResult result = validateImport(projectJson,
                value(call.getString("expectedFingerprint")),
                value(call.getString("expectedAdapterId")),
                value(call.getString("expectedSourceVersion")),
                value(call.getString("expectedSourceLang")),
                value(call.getString("expectedTargetLang")),
                value(call.getString("currentRecordsJson")));
        if ("translation_export_language_mismatch".equals(result.reasonCode)
                || "translation_export_invalid_json".equals(result.reasonCode)
                || "translation_export_empty".equals(result.reasonCode)) {
            call.reject(result.reasonCode);
            return;
        }
        call.resolve(new JSObject()
                .put("acceptedRecordsJson", result.acceptedRecordsJson)
                .put("reviewRecordsJson", result.reviewRecordsJson)
                .put("acceptedCount", result.acceptedCount)
                .put("reviewCount", result.reviewCount));
    }

    private static void exportWithMediaStore(Context context, PluginCall call,
                                             ValidatedProject project, String fileName)
            throws IOException {
        ContentResolver resolver = context.getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
        values.put(MediaStore.MediaColumns.MIME_TYPE, "application/json");
        values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                Environment.DIRECTORY_DOWNLOADS + "/SLG-Translator/translations");
        Uri target = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        if (target == null) throw new IOException("MediaStore insert failed");
        try (OutputStream output = resolver.openOutputStream(target)) {
            if (output == null) throw new IOException("MediaStore output failed");
            output.write(project.normalizedJson.getBytes(StandardCharsets.UTF_8));
            output.flush();
        } catch (Exception error) {
            resolver.delete(target, null, null);
            throw error instanceof IOException ? (IOException) error : new IOException(error);
        }
        call.resolve(new JSObject().put("uri", target.toString()).put("fileName", fileName)
                .put("recordCount", project.recordCount).put("schemaVersion", SCHEMA_VERSION));
    }

    private static void exportWithLegacyStorage(Context context, PluginCall call,
                                                ValidatedProject project, String fileName)
            throws IOException {
        File directory = new File(Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS), "SLG-Translator/translations");
        if ((!directory.exists() && !directory.mkdirs()) || !directory.isDirectory()) {
            throw new IOException("Downloads directory unavailable");
        }
        File output = uniqueFile(directory, fileName);
        File partial = new File(output.getAbsolutePath() + ".partial");
        try (FileOutputStream stream = new FileOutputStream(partial)) {
            stream.write(project.normalizedJson.getBytes(StandardCharsets.UTF_8));
            stream.getFD().sync();
        }
        if (!partial.renameTo(output)) {
            if (partial.exists()) partial.delete();
            throw new IOException("translation export rename failed");
        }
        call.resolve(new JSObject().put("uri", Uri.fromFile(output).toString())
                .put("fileName", output.getName()).put("recordCount", project.recordCount)
                .put("schemaVersion", SCHEMA_VERSION));
    }

    private static File uniqueFile(File directory, String requestedName) {
        File candidate = new File(directory, requestedName);
        int suffix = 2;
        while (candidate.exists()) {
            int dot = requestedName.lastIndexOf('.');
            String stem = dot > 0 ? requestedName.substring(0, dot) : requestedName;
            String extension = dot > 0 ? requestedName.substring(dot) : ".json";
            candidate = new File(directory, stem + "-" + suffix++ + extension);
        }
        return candidate;
    }

    private static String safeFileName(String requestedName) {
        String value = value(requestedName);
        if (value.isEmpty()) value = "renpy-translation.translation.json";
        value = value.replace('\\', '_').replace('/', '_');
        if (value.length() > 120) value = value.substring(0, 120);
        if (!value.toLowerCase(Locale.ROOT).endsWith(".json")) value += ".json";
        return value;
    }

    private static List<Record> readRecords(Object value) {
        if (!(value instanceof List)) {
            throw new ValidationException("translation_export_invalid_json");
        }
        List<?> raw = (List<?>) value;
        if (raw.size() > MAX_RECORDS) {
            throw new ValidationException("translation_export_record_limit");
        }
        List<Record> result = new ArrayList<>();
        for (Object item : raw) {
            if (!(item instanceof Map)) {
                throw new ValidationException("translation_export_invalid_json");
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> fields = (Map<String, Object>) item;
            result.add(new Record(fields));
        }
        return result;
    }

    private static List<RenpyGlossaryValidator.GlossaryTerm> readGlossary(Object value) {
        List<RenpyGlossaryValidator.GlossaryTerm> result = new ArrayList<>();
        if (value == null) return result;
        if (!(value instanceof List)) {
            throw new ValidationException("translation_export_invalid_glossary");
        }
        for (Object item : (List<?>) value) {
            if (!(item instanceof Map)) {
                throw new ValidationException("translation_export_invalid_glossary");
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> entry = (Map<String, Object>) item;
            String source = requiredGlossaryString(entry, "source");
            String target = requiredGlossaryString(entry, "target");
            String mode = entry.get("matchMode") == null
                    ? "whole-word" : requiredGlossaryString(entry, "matchMode");
            RenpyGlossaryValidator.MatchMode matchMode;
            if ("exact".equals(mode)) {
                matchMode = RenpyGlossaryValidator.MatchMode.EXACT;
            } else if ("whole-word".equals(mode)) {
                matchMode = RenpyGlossaryValidator.MatchMode.WHOLE_WORD;
            } else if ("context".equals(mode)) {
                matchMode = RenpyGlossaryValidator.MatchMode.CONTEXT;
            } else {
                throw new ValidationException("translation_export_invalid_glossary");
            }
            String context = null;
            if (matchMode == RenpyGlossaryValidator.MatchMode.CONTEXT) {
                context = requiredGlossaryString(entry, "context");
            } else if (entry.get("context") != null && !(entry.get("context") instanceof String)) {
                throw new ValidationException("translation_export_invalid_glossary");
            }
            result.add(new RenpyGlossaryValidator.GlossaryTerm(source, target, matchMode, context));
        }
        return result;
    }

    private static String requiredGlossaryString(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (!(value instanceof String) || ((String) value).trim().isEmpty()) {
            throw new ValidationException("translation_export_invalid_glossary");
        }
        return (String) value;
    }

    private static Map<String, String> readCurrentRecords(String json) {
        Map<String, String> result = new HashMap<>();
        try {
            Object parsed = new JsonParser(json == null || json.isEmpty() ? "[]" : json).parse();
            if (!(parsed instanceof List)) return result;
            for (Object item : (List<?>) parsed) {
                if (!(item instanceof Map)) continue;
                @SuppressWarnings("unchecked")
                Map<String, Object> record = (Map<String, Object>) item;
                Object id = record.get("recordId");
                Object text = record.get("sourceText");
                if (id instanceof String && text instanceof String) {
                    result.put((String) id, (String) text);
                }
            }
        } catch (RuntimeException ignored) {
            // A malformed current snapshot cannot auto-accept any record.
        }
        return result;
    }

    private static Map<String, Object> parseProject(String json) {
        if (json == null || utf8Length(json) > MAX_PROJECT_BYTES) {
            throw new ValidationException(json == null
                    ? "translation_export_invalid_json" : "translation_export_too_large");
        }
        try {
            Object parsed = new JsonParser(json).parse();
            if (!(parsed instanceof Map)) {
                throw new ValidationException("translation_export_invalid_json");
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> result = (Map<String, Object>) parsed;
            return result;
        } catch (ValidationException error) {
            throw error;
        } catch (RuntimeException error) {
            throw new ValidationException("translation_export_invalid_json");
        }
    }

    private static int requiredInt(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (!(value instanceof Number)) {
            throw new ValidationException("translation_export_invalid_json");
        }
        long number = ((Number) value).longValue();
        if (number < Integer.MIN_VALUE || number > Integer.MAX_VALUE) {
            throw new ValidationException("translation_export_invalid_json");
        }
        return (int) number;
    }

    private static String requiredString(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (!(value instanceof String) || ((String) value).isEmpty()) {
            throw new ValidationException("translation_export_invalid_json");
        }
        String text = (String) value;
        if (utf8Length(text) > MAX_FIELD_BYTES) {
            throw new ValidationException("translation_export_field_limit");
        }
        return text;
    }

    private static int utf8Length(String value) {
        return value == null ? 0 : value.getBytes(StandardCharsets.UTF_8).length;
    }

    private static boolean same(String left, String right) {
        return value(left).equals(value(right));
    }

    private static String value(String text) {
        return text == null ? "" : text;
    }

    private static Map<String, Object> reviewRecord(Record record, String reason) {
        Map<String, Object> result = new LinkedHashMap<>(record.fields);
        result.put("reasonCode", reason);
        return result;
    }

    private static List<Map<String, Object>> reviewForUnparsedProject(String reason) {
        List<Map<String, Object>> result = new ArrayList<>();
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("reasonCode", reason);
        result.add(item);
        return result;
    }

    private static ImportResult result(List<Map<String, Object>> accepted,
                                       List<Map<String, Object>> review, String reasonCode) {
        return new ImportResult(toJson(accepted), toJson(review), accepted.size(), review.size(), reasonCode);
    }

    private static String toJson(Object value) {
        StringBuilder output = new StringBuilder();
        appendJson(output, value);
        return output.toString();
    }

    private static void appendJson(StringBuilder output, Object value) {
        if (value == null) {
            output.append("null");
        } else if (value instanceof String) {
            output.append('"').append(escape((String) value)).append('"');
        } else if (value instanceof Map) {
            output.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                if (!first) output.append(',');
                first = false;
                output.append('"').append(escape(String.valueOf(entry.getKey()))).append("\":");
                appendJson(output, entry.getValue());
            }
            output.append('}');
        } else if (value instanceof List) {
            output.append('[');
            boolean first = true;
            for (Object item : (List<?>) value) {
                if (!first) output.append(',');
                first = false;
                appendJson(output, item);
            }
            output.append(']');
        } else if (value instanceof Boolean || value instanceof Number) {
            output.append(value.toString());
        } else {
            output.append('"').append(escape(String.valueOf(value))).append('"');
        }
    }

    private static String escape(String value) {
        StringBuilder output = new StringBuilder(value.length() + 8);
        for (int index = 0; index < value.length(); index++) {
            char c = value.charAt(index);
            if (c == '"') output.append("\\\"");
            else if (c == '\\') output.append("\\\\");
            else if (c == '\n') output.append("\\n");
            else if (c == '\r') output.append("\\r");
            else if (c == '\t') output.append("\\t");
            else if (c < 0x20) output.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
            else output.append(c);
        }
        return output.toString();
    }

    private static final class ValidationException extends IllegalArgumentException {
        final String code;
        ValidationException(String code) {
            super(code);
            this.code = code;
        }
    }

    private static final class JsonParser {
        private final String source;
        private int position;

        JsonParser(String source) { this.source = source; }

        Object parse() {
            skipWhitespace();
            Object value = parseValue(0);
            skipWhitespace();
            if (position != source.length()) throw new IllegalArgumentException();
            return value;
        }

        private Object parseValue(int depth) {
            if (depth > 64) throw new IllegalArgumentException();
            skipWhitespace();
            if (position >= source.length()) throw new IllegalArgumentException();
            char c = source.charAt(position);
            if (c == '{') return parseObject(depth + 1);
            if (c == '[') return parseArray(depth + 1);
            if (c == '"') return parseString();
            if (source.startsWith("true", position)) { position += 4; return Boolean.TRUE; }
            if (source.startsWith("false", position)) { position += 5; return Boolean.FALSE; }
            if (source.startsWith("null", position)) { position += 4; return null; }
            return parseNumber();
        }

        private Map<String, Object> parseObject(int depth) {
            Map<String, Object> result = new LinkedHashMap<>();
            position++;
            skipWhitespace();
            if (consume('}')) return result;
            while (true) {
                skipWhitespace();
                if (position >= source.length() || source.charAt(position) != '"') {
                    throw new IllegalArgumentException();
                }
                String key = parseString();
                if (result.containsKey(key)) throw new IllegalArgumentException();
                skipWhitespace();
                if (!consume(':')) throw new IllegalArgumentException();
                Object value = parseValue(depth);
                result.put(key, value);
                skipWhitespace();
                if (consume('}')) return result;
                if (!consume(',')) throw new IllegalArgumentException();
            }
        }

        private List<Object> parseArray(int depth) {
            List<Object> result = new ArrayList<>();
            position++;
            skipWhitespace();
            if (consume(']')) return result;
            while (true) {
                if (result.size() > MAX_RECORDS) throw new IllegalArgumentException();
                result.add(parseValue(depth));
                skipWhitespace();
                if (consume(']')) return result;
                if (!consume(',')) throw new IllegalArgumentException();
            }
        }

        private Number parseNumber() {
            int start = position;
            if (source.charAt(position) == '-') position++;
            while (position < source.length() && Character.isDigit(source.charAt(position))) position++;
            if (position < source.length() && source.charAt(position) == '.') {
                position++;
                while (position < source.length() && Character.isDigit(source.charAt(position))) position++;
            }
            if (position < source.length() && (source.charAt(position) == 'e'
                    || source.charAt(position) == 'E')) {
                position++;
                if (position < source.length() && (source.charAt(position) == '+'
                        || source.charAt(position) == '-')) position++;
                while (position < source.length() && Character.isDigit(source.charAt(position))) position++;
            }
            String number = source.substring(start, position);
            if (number.isEmpty() || "-".equals(number)) throw new IllegalArgumentException();
            try {
                return number.indexOf('.') >= 0 || number.indexOf('e') >= 0 || number.indexOf('E') >= 0
                        ? Double.valueOf(number) : Long.valueOf(number);
            } catch (NumberFormatException error) {
                throw new IllegalArgumentException(error);
            }
        }

        private String parseString() {
            if (!consume('"')) throw new IllegalArgumentException();
            StringBuilder result = new StringBuilder();
            while (position < source.length()) {
                char c = source.charAt(position++);
                if (c == '"') return result.toString();
                if (c == '\\') {
                    if (position >= source.length()) throw new IllegalArgumentException();
                    char escaped = source.charAt(position++);
                    if (escaped == '"' || escaped == '\\' || escaped == '/') result.append(escaped);
                    else if (escaped == 'b') result.append('\b');
                    else if (escaped == 'f') result.append('\f');
                    else if (escaped == 'n') result.append('\n');
                    else if (escaped == 'r') result.append('\r');
                    else if (escaped == 't') result.append('\t');
                    else if (escaped == 'u') {
                        if (position + 4 > source.length()) throw new IllegalArgumentException();
                        String hex = source.substring(position, position + 4);
                        position += 4;
                        result.append((char) Integer.parseInt(hex, 16));
                    } else throw new IllegalArgumentException();
                } else {
                    if (c < 0x20) throw new IllegalArgumentException();
                    result.append(c);
                }
            }
            throw new IllegalArgumentException();
        }

        private boolean consume(char expected) {
            if (position < source.length() && source.charAt(position) == expected) {
                position++;
                return true;
            }
            return false;
        }

        private void skipWhitespace() {
            while (position < source.length() && Character.isWhitespace(source.charAt(position))) position++;
        }
    }
}
