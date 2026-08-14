package com.slgtranslator.app;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;

import java.io.IOException;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * JSON asset codec. Rewrites only nodes that were originally JSON strings;
 * numbers, booleans, null, object keys and array shapes are never modified.
 * Duplicate object keys are diagnosed and block both extraction and writing.
 */
public final class JsonAssetCodec implements StructuredTextAdapter.AssetCodec {

    public static final String CODE_DUPLICATE_KEY = "structured_json_duplicate_key";
    public static final String CODE_UNSAFE_SHAPE = "structured_json_unsafe_shape";
    public static final String CODE_PARSE_FAILED = "structured_json_parse_failed";

    private final StructuredTextAdapter adapter;

    public JsonAssetCodec(StructuredTextAdapter adapter) {
        this.adapter = adapter;
    }

    @Override
    public String id() {
        return "json";
    }

    @Override
    public boolean detect(String path, byte[] bytes) {
        return path != null
                && StructuredTextAdapter.lowerPath(path).endsWith(".json")
                && StructuredTextAdapter.looksLikeJson(bytes);
    }

    @Override
    public List<StructuredTextRecord> extract(String owner, String path, byte[] bytes)
            throws IOException {
        String text = new String(bytes, StandardCharsets.UTF_8);
        List<StructuredTextRecord> records = new ArrayList<>();
        try {
            JsonReader reader = new JsonReader(new StringReader(text));
            reader.setLenient(false);
            walkForExtract(reader, "", owner, path, records, new int[]{0});
        } catch (java.io.IOException error) {
            throw new IOException(CODE_PARSE_FAILED + ": " + safeMessage(error), error);
        }
        return records;
    }

    /** Traversal order is deterministic: object key order, then array order. */
    private void walkForExtract(JsonReader reader, String pointer, String owner,
                                String path, List<StructuredTextRecord> records,
                                int[] counter) throws IOException {
        JsonToken token = reader.peek();
        if (token == JsonToken.BEGIN_OBJECT) {
            reader.beginObject();
            Set<String> names = new HashSet<>();
            while (reader.hasNext()) {
                String name = reader.nextName();
                if (!names.add(name)) {
                    throw new IOException(CODE_DUPLICATE_KEY + ": key '" + name + "'");
                }
                walkForExtract(reader, pointer + "/" + escapePointer(name),
                        owner, path, records, counter);
            }
            reader.endObject();
        } else if (token == JsonToken.BEGIN_ARRAY) {
            reader.beginArray();
            int index = 0;
            while (reader.hasNext()) {
                walkForExtract(reader, pointer + "/" + index, owner, path, records, counter);
                index++;
            }
            reader.endArray();
        } else if (token == JsonToken.STRING) {
            String value = reader.nextString();
            records.add(adapter.record(owner, path, id(), pointer, value, counter[0]));
            counter[0]++;
        } else {
            reader.skipValue();
        }
    }

    @Override
    public byte[] rewrite(byte[] bytes, Map<String, String> translations)
            throws IOException {
        String text = new String(bytes, StandardCharsets.UTF_8);
        JsonElement root;
        try {
            checkDuplicateKeys(text);
            root = JsonParser.parseString(text);
        } catch (IOException error) {
            throw error;
        } catch (RuntimeException error) {
            throw new IOException(CODE_PARSE_FAILED + ": " + safeMessage(error), error);
        }
        for (Map.Entry<String, String> entry : translations.entrySet()) {
            if (entry.getKey() == null || entry.getValue() == null) {
                throw new IOException(CODE_UNSAFE_SHAPE + ": null translation entry");
            }
            JsonElement target = elementAt(root, entry.getKey());
            if (target == null || !target.isJsonPrimitive()
                    || !target.getAsJsonPrimitive().isString()) {
                throw new IOException(CODE_UNSAFE_SHAPE + ": path '" + entry.getKey()
                        + "' is not a string node");
            }
            JsonElement replacement = new JsonPrimitive(entry.getValue());
            replaceAt(root, entry.getKey(), replacement);
        }
        return root.toString().getBytes(StandardCharsets.UTF_8);
    }

    @Override
    public ValidationResult verify(byte[] original, byte[] rewritten,
                                   List<StructuredTextRecord> records,
                                   Map<String, String> translations) throws IOException {
        String originalText = new String(original, StandardCharsets.UTF_8);
        String rewrittenText = new String(rewritten, StandardCharsets.UTF_8);
        JsonElement originalTree;
        JsonElement rewrittenTree;
        try {
            checkDuplicateKeys(originalText);
            checkDuplicateKeys(rewrittenText);
            originalTree = JsonParser.parseString(originalText);
            rewrittenTree = JsonParser.parseString(rewrittenText);
        } catch (IOException error) {
            return ValidationResult.fail(CODE_PARSE_FAILED, safeMessage(error));
        } catch (RuntimeException error) {
            return ValidationResult.fail(CODE_PARSE_FAILED, safeMessage(error));
        }
        for (StructuredTextRecord record : records) {
            JsonElement before = elementAt(originalTree, record.keyPath);
            JsonElement after = elementAt(rewrittenTree, record.keyPath);
            if (before == null || after == null) {
                return ValidationResult.fail(CODE_UNSAFE_SHAPE,
                        "path disappeared: " + record.keyPath);
            }
            if (!before.isJsonPrimitive() || !before.getAsJsonPrimitive().isString()
                    || !after.isJsonPrimitive() || !after.getAsJsonPrimitive().isString()) {
                return ValidationResult.fail(CODE_UNSAFE_SHAPE,
                        "value type changed at: " + record.keyPath);
            }
            String expected = translations.get(record.keyPath);
            if (expected != null) {
                if (!expected.equals(after.getAsString())) {
                    return ValidationResult.fail("writer_output_invalid",
                            "translation mismatch at: " + record.keyPath);
                }
            } else if (!before.getAsString().equals(after.getAsString())) {
                return ValidationResult.fail("writer_output_invalid",
                        "untouched value changed at: " + record.keyPath);
            }
        }
        return ValidationResult.ok();
    }

    /** Detects duplicate object keys with a strict reader pass. */
    private static void checkDuplicateKeys(String text) throws IOException {
        JsonReader reader = new JsonReader(new StringReader(text));
        reader.setLenient(false);
        try {
            checkDuplicateKeysWalk(reader);
        } catch (IOException error) {
            throw error;
        } catch (RuntimeException error) {
            throw new IOException(CODE_PARSE_FAILED + ": " + safeMessage(error), error);
        }
    }

    private static void checkDuplicateKeysWalk(JsonReader reader) throws IOException {
        JsonToken token = reader.peek();
        if (token == JsonToken.BEGIN_OBJECT) {
            reader.beginObject();
            Set<String> names = new HashSet<>();
            while (reader.hasNext()) {
                String name = reader.nextName();
                if (!names.add(name)) {
                    throw new IOException(CODE_DUPLICATE_KEY + ": key '" + name + "'");
                }
                checkDuplicateKeysWalk(reader);
            }
            reader.endObject();
        } else if (token == JsonToken.BEGIN_ARRAY) {
            reader.beginArray();
            while (reader.hasNext()) {
                checkDuplicateKeysWalk(reader);
            }
            reader.endArray();
        } else {
            reader.skipValue();
        }
    }

    private static JsonElement elementAt(JsonElement root, String pointer) {
        JsonElement current = root;
        for (String segment : pointerSegments(pointer)) {
            if (current == null) {
                return null;
            }
            if (current.isJsonObject()) {
                current = current.getAsJsonObject().get(segment);
            } else if (current.isJsonArray()) {
                try {
                    int index = Integer.parseInt(segment);
                    JsonArray array = current.getAsJsonArray();
                    if (index < 0 || index >= array.size()) {
                        return null;
                    }
                    current = array.get(index);
                } catch (NumberFormatException invalid) {
                    return null;
                }
            } else {
                return null;
            }
        }
        return current;
    }

    private static void replaceAt(JsonElement root, String pointer, JsonElement value) {
        List<String> segments = pointerSegments(pointer);
        JsonElement parent = root;
        for (int index = 0; index < segments.size() - 1; index++) {
            String segment = segments.get(index);
            if (parent.isJsonObject()) {
                parent = parent.getAsJsonObject().get(segment);
            } else {
                parent = parent.getAsJsonArray().get(Integer.parseInt(segment));
            }
        }
        String last = segments.get(segments.size() - 1);
        if (parent.isJsonObject()) {
            parent.getAsJsonObject().add(last, value);
        } else {
            parent.getAsJsonArray().set(Integer.parseInt(last), value);
        }
    }

    static List<String> pointerSegments(String pointer) {
        List<String> segments = new ArrayList<>();
        if (pointer == null || pointer.isEmpty() || !pointer.startsWith("/")) {
            return segments;
        }
        for (String raw : pointer.substring(1).split("/", -1)) {
            segments.add(raw.replace("~1", "/").replace("~0", "~"));
        }
        return segments;
    }

    static String escapePointer(String segment) {
        return segment.replace("~", "~0").replace("/", "~1");
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? error.toString() : message;
    }
}
