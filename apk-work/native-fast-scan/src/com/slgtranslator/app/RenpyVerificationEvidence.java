package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Joins one inspected RPYC with the versioned external evidence manifest. */
public final class RenpyVerificationEvidence {
    public static final String PENDING_LEVEL = "sample_pending";

    private static final int MAX_JSON_CHARS = 4 * 1024 * 1024;
    private static final int MAX_DEPTH = 32;
    private static final int MAX_CONTAINER_ITEMS = 4096;
    private static final int MAX_STRING_CHARS = 8192;

    private RenpyVerificationEvidence() {
    }

    public static final class Result {
        public final String level;
        public final String reason;
        public final String sampleId;
        public final String structuralDialect;
        public final int distinctFingerprintCount;

        private Result(String level, String reason, String sampleId,
                       String structuralDialect, int distinctFingerprintCount) {
            this.level = level == null ? PENDING_LEVEL : level;
            this.reason = reason == null ? "unknown" : reason;
            this.sampleId = sampleId == null ? "" : sampleId;
            this.structuralDialect = structuralDialect == null ? "" : structuralDialect;
            this.distinctFingerprintCount = Math.max(0, distinctFingerprintCount);
        }

        private static Result pending(String reason) {
            return new Result(PENDING_LEVEL, reason, "", "", 0);
        }
    }

    /**
     * Returns a verified level only when the manifest record and all required
     * structural/runtime evidence match the supplied current artifacts.
     */
    public static Result join(String manifestJson,
                              String apkSha256,
                              String extractedSha256,
                              String objectGraphFingerprint,
                              String structuralDialect) {
        if (manifestJson == null || manifestJson.length() == 0) {
            return Result.pending("manifest_missing");
        }
        if (manifestJson.length() > MAX_JSON_CHARS) {
            return Result.pending("manifest_too_large");
        }
        String normalizedApkSha = normalizeHash(apkSha256);
        String normalizedExtractedSha = normalizeHash(extractedSha256);
        String currentFingerprint = normalizeFingerprint(objectGraphFingerprint);
        String currentDialect = normalizeToken(structuralDialect);
        if (normalizedApkSha == null || normalizedExtractedSha == null
                || currentFingerprint == null || currentDialect == null) {
            return Result.pending("current_artifact_identity_invalid");
        }

        Object parsed;
        try {
            parsed = new JsonParser(manifestJson).parse();
        } catch (JsonFormatException error) {
            return Result.pending("manifest_invalid:" + error.code);
        }
        Map<String, Object> root = object(parsed);
        if (root == null) {
            return Result.pending("manifest_root_not_object");
        }
        if (!numberEquals(root.get("schemaVersion"), 1L)) {
            return Result.pending("manifest_schema_unsupported");
        }
        List<Object> samples = array(root.get("samples"));
        if (samples == null) {
            return Result.pending("manifest_samples_not_array");
        }

        List<Sample> completeSamples = new ArrayList<>();
        Sample current = null;
        String mismatchReason = "sample_not_found";
        for (Object value : samples) {
            Map<String, Object> sampleObject = object(value);
            if (sampleObject == null) {
                continue;
            }
            Sample sample = Sample.read(sampleObject);
            if (sample == null) {
                continue;
            }
            if (!currentDialect.equals(sample.structuralDialect)) {
                if (normalizedApkSha.equals(sample.apkSha256)
                        && normalizedExtractedSha.equals(sample.extractedSha256)
                        && currentFingerprint.equals(sample.fingerprint)) {
                    mismatchReason = "structural_dialect_mismatch";
                }
                continue;
            }
            if (!sample.hasValidSampleLevel()) {
                continue;
            }
            if (sample.isComplete()) {
                completeSamples.add(sample);
            }
            if (normalizedApkSha.equals(sample.apkSha256)
                    && currentFingerprint.equals(sample.fingerprint)) {
                if (!normalizedExtractedSha.equals(sample.extractedSha256)) {
                    mismatchReason = "extracted_artifact_hash_mismatch";
                } else if (!sample.isComplete()) {
                    mismatchReason = sample.incompleteReason();
                } else if (current == null) {
                    current = sample;
                }
            } else if (normalizedApkSha.equals(sample.apkSha256)
                    && normalizedExtractedSha.equals(sample.extractedSha256)) {
                mismatchReason = "object_graph_fingerprint_mismatch";
            }
        }

        if (current == null) {
            return new Result(PENDING_LEVEL, mismatchReason, "", currentDialect, 0);
        }

        Set<String> fingerprints = new HashSet<>();
        for (Sample sample : completeSamples) {
            if (current.bucket.equals(sample.bucket)
                    && currentDialect.equals(sample.structuralDialect)) {
                fingerprints.add(sample.fingerprint);
            }
        }
        String level = fingerprints.size() >= 2
                ? current.bucket + "_dialect_verified"
                : current.level;
        String reason = fingerprints.size() >= 2
                ? "complete_distinct_fingerprints"
                : "complete_sample_evidence";
        return new Result(level, reason, current.sampleId, currentDialect, fingerprints.size());
    }

    private static final class Sample {
        final String sampleId;
        final String apkSha256;
        final String extractedSha256;
        final String fingerprint;
        final String structuralDialect;
        final String level;
        final String bucket;
        final Map<String, Object> structuralVerification;
        final Map<String, Object> runtimeVerification;

        private Sample(String sampleId, String apkSha256, String extractedSha256,
                       String fingerprint, String structuralDialect, String level,
                       String bucket, Map<String, Object> structuralVerification,
                       Map<String, Object> runtimeVerification) {
            this.sampleId = sampleId;
            this.apkSha256 = apkSha256;
            this.extractedSha256 = extractedSha256;
            this.fingerprint = fingerprint;
            this.structuralDialect = structuralDialect;
            this.level = level;
            this.bucket = bucket;
            this.structuralVerification = structuralVerification;
            this.runtimeVerification = runtimeVerification;
        }

        static Sample read(Map<String, Object> sample) {
            Map<String, Object> engine = object(sample.get("engine"));
            Map<String, Object> versionEvidence = engine == null
                    ? null : object(engine.get("versionEvidence"));
            Map<String, Object> packageObject = object(sample.get("package"));
            Map<String, Object> sourceApk = packageObject == null
                    ? null : object(packageObject.get("sourceApk"));
            Map<String, Object> graph = object(sample.get("objectGraph"));
            Map<String, Object> extracted = graph == null
                    ? null : object(graph.get("extractedArtifact"));
            Map<String, Object> structural = object(sample.get("structuralVerification"));
            Map<String, Object> runtime = object(sample.get("runtimeVerification"));
            String level = normalizeToken(sample.get("verificationLevel"));
            String bucket = bucketFor(level);
            String apkSha = sourceApk == null ? null : normalizeHash(sourceApk.get("sha256"));
            String extractedSha = extracted == null
                    ? null : normalizeHash(extracted.get("sha256"));
            String fingerprint = graph == null
                    ? null : normalizeFingerprint(graph.get("objectGraphFingerprint"));
            String dialect = engine == null
                    ? null : normalizeToken(engine.get("structuralDialect"));
            String renpyVersion = engine == null
                    ? null : normalizeToken(engine.get("renpyVersion"));
            String versionSource = versionEvidence == null
                    ? null : normalizeToken(versionEvidence.get("sourceApkEntry"));
            String versionValue = versionEvidence == null
                    ? null : normalizeToken(versionEvidence.get("value"));
            String sampleId = normalizeToken(sample.get("sampleId"));
            if (sampleId == null || apkSha == null || extractedSha == null
                    || fingerprint == null || dialect == null || level == null
                    || bucket == null || renpyVersion == null || versionSource == null
                    || versionValue == null) {
                return null;
            }
            return new Sample(sampleId, apkSha, extractedSha, fingerprint, dialect,
                    level, bucket, structural, runtime);
        }

        boolean hasValidSampleLevel() {
            return level.equals(bucket + "_sample_verified");
        }

        boolean isComplete() {
            if (structuralVerification == null || runtimeVerification == null) {
                return false;
            }
            if (!"passed".equals(string(structuralVerification.get("status")))
                    || !booleanValue(structuralVerification.get("compiledTranslationValidated"))
                    || !"passed".equals(string(structuralVerification.get("independentReread")))) {
                return false;
            }
            if (!"passed".equals(string(runtimeVerification.get("install")))
                    || !"passed".equals(string(runtimeVerification.get("launch")))
                    || !booleanValue(runtimeVerification.get("processAlive"))
                    || !numberEquals(runtimeVerification.get("rpycLoadErrors"), 0L)
                    || !numberEquals(runtimeVerification.get("fatalExceptions"), 0L)
                    || !numberEquals(runtimeVerification.get("tracebacks"), 0L)) {
                return false;
            }
            Map<String, Object> visual = object(
                    runtimeVerification.get("localizedDialogueVisualConfirmation"));
            return visual != null && "confirmed".equals(string(visual.get("status")));
        }

        String incompleteReason() {
            if (structuralVerification == null) return "structural_verification_missing";
            if (!"passed".equals(string(structuralVerification.get("status")))) {
                return "structural_verification_not_passed";
            }
            if (!booleanValue(structuralVerification.get("compiledTranslationValidated"))) {
                return "compiled_translation_not_validated";
            }
            if (!"passed".equals(string(structuralVerification.get("independentReread")))) {
                return "independent_reread_not_passed";
            }
            if (runtimeVerification == null) return "runtime_verification_missing";
            if (!"passed".equals(string(runtimeVerification.get("install")))) {
                return "runtime_install_not_passed";
            }
            if (!"passed".equals(string(runtimeVerification.get("launch")))) {
                return "runtime_launch_not_passed";
            }
            if (!booleanValue(runtimeVerification.get("processAlive"))) {
                return "runtime_process_not_alive";
            }
            if (!numberEquals(runtimeVerification.get("rpycLoadErrors"), 0L)) {
                return "runtime_rpyc_load_errors";
            }
            if (!numberEquals(runtimeVerification.get("fatalExceptions"), 0L)) {
                return "runtime_fatal_exceptions";
            }
            if (!numberEquals(runtimeVerification.get("tracebacks"), 0L)) {
                return "runtime_tracebacks";
            }
            return "localized_dialogue_visual_confirmation_missing";
        }
    }

    private static String bucketFor(String level) {
        if (level == null) return null;
        if (level.equals("modern_84_sample_verified")) return "modern_84";
        if (level.equals("modern_85_sample_verified")) return "modern_85";
        if (level.equals("modern_8x_sample_verified")) return "modern_8x";
        return null;
    }

    private static String normalizeHash(Object value) {
        if (!(value instanceof String)) return null;
        String text = ((String) value).trim().toLowerCase(Locale.ROOT);
        if (text.length() != 64) return null;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return null;
        }
        return text;
    }

    private static String normalizeFingerprint(Object value) {
        if (!(value instanceof String)) return null;
        String text = ((String) value).trim();
        if (text.length() == 0 || text.length() > 1024) return null;
        return text;
    }

    private static String normalizeToken(Object value) {
        if (!(value instanceof String)) return null;
        String text = ((String) value).trim();
        if (text.length() == 0 || text.length() > MAX_STRING_CHARS) return null;
        return text;
    }

    private static String string(Object value) {
        return value instanceof String ? (String) value : null;
    }

    private static boolean booleanValue(Object value) {
        return Boolean.TRUE.equals(value);
    }

    private static boolean numberEquals(Object value, long expected) {
        return value instanceof Number && ((Number) value).doubleValue() == expected;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> object(Object value) {
        return value instanceof Map ? (Map<String, Object>) value : null;
    }

    @SuppressWarnings("unchecked")
    private static List<Object> array(Object value) {
        return value instanceof List ? (List<Object>) value : null;
    }

    private static final class JsonFormatException extends Exception {
        final String code;

        JsonFormatException(String code) {
            this.code = code;
        }
    }

    private static final class JsonParser {
        private final String text;
        private int position;

        JsonParser(String text) {
            this.text = text;
        }

        Object parse() throws JsonFormatException {
            Object value = parseValue(0);
            skipWhitespace();
            if (position != text.length()) throw fail("trailing_data");
            return value;
        }

        private Object parseValue(int depth) throws JsonFormatException {
            if (depth > MAX_DEPTH) throw fail("max_depth");
            skipWhitespace();
            if (position >= text.length()) throw fail("unexpected_eof");
            char current = text.charAt(position);
            if (current == '{') return parseObject(depth + 1);
            if (current == '[') return parseArray(depth + 1);
            if (current == '"') return parseString();
            if (startsWith("true")) {
                position += 4;
                return Boolean.TRUE;
            }
            if (startsWith("false")) {
                position += 5;
                return Boolean.FALSE;
            }
            if (startsWith("null")) {
                position += 4;
                return null;
            }
            if (current == '-' || (current >= '0' && current <= '9')) {
                return parseNumber();
            }
            throw fail("unexpected_token");
        }

        private Map<String, Object> parseObject(int depth) throws JsonFormatException {
            expect('{');
            Map<String, Object> result = new LinkedHashMap<>();
            skipWhitespace();
            if (consume('}')) return result;
            while (true) {
                if (result.size() >= MAX_CONTAINER_ITEMS) throw fail("object_too_large");
                skipWhitespace();
                String key = parseString();
                skipWhitespace();
                expect(':');
                Object value = parseValue(depth);
                if (result.containsKey(key)) {
                    throw fail("duplicate_or_invalid_key");
                }
                result.put(key, value);
                skipWhitespace();
                if (consume('}')) return result;
                expect(',');
            }
        }

        private List<Object> parseArray(int depth) throws JsonFormatException {
            expect('[');
            List<Object> result = new ArrayList<>();
            skipWhitespace();
            if (consume(']')) return result;
            while (true) {
                if (result.size() >= MAX_CONTAINER_ITEMS) throw fail("array_too_large");
                result.add(parseValue(depth));
                skipWhitespace();
                if (consume(']')) return result;
                expect(',');
            }
        }

        private String parseString() throws JsonFormatException {
            expect('"');
            StringBuilder result = new StringBuilder();
            while (position < text.length()) {
                char current = text.charAt(position++);
                if (current == '"') return result.toString();
                if (current < 0x20) throw fail("control_in_string");
                if (current != '\\') {
                    appendStringChar(result, current);
                    continue;
                }
                if (position >= text.length()) throw fail("string_escape_eof");
                char escaped = text.charAt(position++);
                switch (escaped) {
                    case '"': result.append('"'); break;
                    case '\\': result.append('\\'); break;
                    case '/': result.append('/'); break;
                    case 'b': result.append('\b'); break;
                    case 'f': result.append('\f'); break;
                    case 'n': result.append('\n'); break;
                    case 'r': result.append('\r'); break;
                    case 't': result.append('\t'); break;
                    case 'u':
                        result.append((char) parseHexQuad());
                        break;
                    default: throw fail("invalid_string_escape");
                }
                if (result.length() > MAX_STRING_CHARS) throw fail("string_too_large");
            }
            throw fail("unterminated_string");
        }

        private long parseHexQuad() throws JsonFormatException {
            if (position + 4 > text.length()) throw fail("unicode_escape_eof");
            long value = 0;
            for (int i = 0; i < 4; i++) {
                int digit = Character.digit(text.charAt(position++), 16);
                if (digit < 0) throw fail("invalid_unicode_escape");
                value = (value << 4) | digit;
            }
            return value;
        }

        private Number parseNumber() throws JsonFormatException {
            int start = position;
            if (consume('-')) {
                if (position >= text.length()) throw fail("invalid_number");
            }
            if (consume('0')) {
                if (position < text.length() && isDigit(text.charAt(position))) {
                    throw fail("leading_zero");
                }
            } else {
                if (!consumeDigits()) throw fail("invalid_number");
            }
            boolean decimal = false;
            if (consume('.')) {
                decimal = true;
                if (!consumeDigits()) throw fail("invalid_number_fraction");
            }
            if (position < text.length()
                    && (text.charAt(position) == 'e' || text.charAt(position) == 'E')) {
                decimal = true;
                position++;
                if (position < text.length()
                        && (text.charAt(position) == '+' || text.charAt(position) == '-')) {
                    position++;
                }
                if (!consumeDigits()) throw fail("invalid_number_exponent");
            }
            String token = text.substring(start, position);
            try {
                return decimal ? Double.valueOf(token) : Long.valueOf(token);
            } catch (NumberFormatException error) {
                throw fail("number_out_of_range");
            }
        }

        private boolean consumeDigits() {
            int start = position;
            while (position < text.length() && isDigit(text.charAt(position))) position++;
            return position > start;
        }

        private boolean isDigit(char value) {
            return value >= '0' && value <= '9';
        }

        private void appendStringChar(StringBuilder result, char value) throws JsonFormatException {
            result.append(value);
            if (result.length() > MAX_STRING_CHARS) throw fail("string_too_large");
        }

        private boolean startsWith(String value) {
            return text.regionMatches(position, value, 0, value.length());
        }

        private void skipWhitespace() {
            while (position < text.length()) {
                char current = text.charAt(position);
                if (current != ' ' && current != '\t' && current != '\r' && current != '\n') return;
                position++;
            }
        }

        private boolean consume(char expected) {
            if (position < text.length() && text.charAt(position) == expected) {
                position++;
                return true;
            }
            return false;
        }

        private void expect(char expected) throws JsonFormatException {
            if (!consume(expected)) throw fail("expected_" + expected);
        }

        private JsonFormatException fail(String code) {
            return new JsonFormatException(code);
        }
    }
}
