package com.slgtranslator.app;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Routes structured APK assets to per-format codecs and mints the stable
 * record identities the writer verifies against after re-parsing.
 *
 * <p>Routing is format-specific and checks both the asset path and the
 * content: a codec only matches when its {@link AssetCodec#detect} accepts
 * the pair. Formats outside the first-release set (YAML, Lua, JavaScript,
 * arbitrary XML/HTML) and files with ambiguous encoding are never routed,
 * so the scanner must fall back to {@code structured_extraction_unavailable}.</p>
 */
public final class StructuredTextAdapter {

    public static final String ADAPTER_ID = "structured-text";

    public interface AssetCodec {
        /** Stable format id, e.g. {@code "json"}. */
        String id();

        /** Accepts the path/content pair only when both signal this format. */
        boolean detect(String path, byte[] bytes);

        /** Extracts translatable records; throws on malformed input. */
        List<StructuredTextRecord> extract(String owner, String path, byte[] bytes)
                throws IOException;

        /** Rewrites only the approved translations; throws on unsafe shapes. */
        byte[] rewrite(byte[] bytes, Map<String, String> translations) throws IOException;

        /** Re-parses the rewritten bytes and compares them to the records. */
        ValidationResult verify(byte[] original, byte[] rewritten,
                List<StructuredTextRecord> records,
                Map<String, String> translations) throws IOException;

        final class ValidationResult {
            public final boolean valid;
            public final String code;
            public final String detail;

            public ValidationResult(boolean valid, String code, String detail) {
                this.valid = valid;
                this.code = code;
                this.detail = detail;
            }

            public static ValidationResult ok() {
                return new ValidationResult(true, "", "");
            }

            public static ValidationResult fail(String code, String detail) {
                return new ValidationResult(false, code, detail);
            }
        }
    }

    private final List<AssetCodec> codecs = new ArrayList<>();

    public void install(AssetCodec codec) {
        if (codec == null) {
            throw new IllegalArgumentException("codec is required");
        }
        for (AssetCodec existing : codecs) {
            if (existing.id().equals(codec.id())) {
                throw new IllegalArgumentException("duplicate codec id: " + codec.id());
            }
        }
        codecs.add(codec);
    }

    /** Returns the first codec whose detect() accepts the pair, or null. */
    public AssetCodec codecFor(String path, byte[] bytes) {
        if (path == null || path.isEmpty() || bytes == null) {
            return null;
        }
        for (AssetCodec codec : codecs) {
            if (codec.detect(path, bytes)) {
                return codec;
            }
        }
        return null;
    }

    /** True when no registered codec can accept this asset. */
    public boolean isUnsupported(String path, byte[] bytes) {
        return codecFor(path, bytes) == null;
    }

    /**
     * Stable record identity: SHA-256 over adapter id, owner, path, format,
     * keyPath, occurrence index and exact source text.
     */
    public String recordId(String owner, String sourcePath, String format,
                           String keyPath, String sourceText, int index) {
        return sha256Hex(ADAPTER_ID + "\n"
                + safe(owner) + "\n"
                + safe(sourcePath) + "\n"
                + safe(format) + "\n"
                + safe(keyPath) + "\n"
                + index + "\n"
                + safe(sourceText));
    }

    public StructuredTextRecord record(String owner, String sourcePath, String format,
                                       String keyPath, String sourceText, int index) {
        return new StructuredTextRecord(
                recordId(owner, sourcePath, format, keyPath, sourceText, index),
                owner, sourcePath, format, keyPath, sourceText, "string", index);
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    static String sha256Hex(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(digest.length * 2);
            for (byte item : digest) {
                out.append(Character.forDigit((item >>> 4) & 0x0f, 16));
                out.append(Character.forDigit(item & 0x0f, 16));
            }
            return out.toString();
        } catch (Exception error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }
    }

    /** Shared content sniffers; codecs combine these with extension checks. */
    static boolean looksLikeJson(byte[] bytes) {
        int index = skipWhitespace(bytes, 0);
        return index < bytes.length
                && (bytes[index] == '{' || bytes[index] == '[');
    }

    static boolean isUtf8Clean(byte[] bytes) {
        try {
            java.nio.charset.StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                    .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
                    .decode(java.nio.ByteBuffer.wrap(bytes));
            return true;
        } catch (java.nio.charset.CharacterCodingException error) {
            return false;
        }
    }

    static boolean hasReplacementChar(byte[] bytes) {
        String text = new String(bytes, StandardCharsets.UTF_8);
        return text.indexOf('\ufffd') >= 0;
    }

    static boolean hasUtf8Bom(byte[] bytes) {
        return bytes.length >= 3
                && (bytes[0] & 0xff) == 0xef
                && (bytes[1] & 0xff) == 0xbb
                && (bytes[2] & 0xff) == 0xbf;
    }

    static int skipWhitespace(byte[] bytes, int from) {
        int index = from;
        while (index < bytes.length) {
            byte value = bytes[index];
            if (value != ' ' && value != '\t' && value != '\r' && value != '\n') {
                break;
            }
            index++;
        }
        return index;
    }

    static String lowerPath(String path) {
        return path == null ? "" : path.replace('\\', '/').toLowerCase(Locale.ROOT);
    }
}
