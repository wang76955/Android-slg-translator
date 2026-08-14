package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.InflaterInputStream;

/**
 * Applies an always-on fallback directly to serialized Ren'Py Say.what fields.
 *
 * <p>Ren'Py dialogue is represented by Say/Translate nodes, not by
 * TranslateString entries. This rewriter changes only the value reached by a
 * serialized {@code what} key and leaves labels, jumps, and all other pickle
 * fields untouched. It is intentionally used only for the always-on mode,
 * where the translated text must be active without selecting a language.</p>
 */
public final class RpycDialoguePatcher {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    private RpycDialoguePatcher() {
    }

    /**
     * Returns a rewritten RPC2 RPYC, or {@code null} when no Say.what value
     * matched the supplied exact-text translations.
     */
    public static byte[] rewriteSayTexts(byte[] rpyc, Map<String, String> translations)
            throws IOException {
        RewriteOutcome outcome = rewriteSayTextsDetailed(rpyc, translations);
        return outcome == null ? null : outcome.bytes;
    }

    /** Detailed rewrite result including which exact-old keys actually matched. */
    public static final class RewriteOutcome {
        public final byte[] bytes;
        public final int matchedCount;
        public final List<String> missedOldTexts;

        RewriteOutcome(byte[] bytes, int matchedCount, List<String> missedOldTexts) {
            this.bytes = bytes;
            this.matchedCount = matchedCount;
            this.missedOldTexts = missedOldTexts;
        }
    }

    /**
     * Rewrites Say.what values and reports the keys that matched no serialized
     * dialogue. Returns {@code null} when nothing changed; a structurally
     * invalid rewrite throws instead of shipping corrupt bytes.
     */
    public static RewriteOutcome rewriteSayTextsDetailed(byte[] rpyc,
                                                          Map<String, String> translations)
            throws IOException {
        if (rpyc == null || translations == null || translations.isEmpty()
                || !startsWith(rpyc, RPC2_MAGIC)) {
            return null;
        }
        List<Slot> slots = parseSlots(rpyc);
        if (slots == null || slots.isEmpty()) {
            return null;
        }
        List<byte[]> payloads = new ArrayList<>();
        Set<String> matched = new LinkedHashSet<>();
        boolean changed = false;
        int dataEnd = 0;
        for (Slot slot : slots) {
            dataEnd = Math.max(dataEnd, slot.offset + slot.length);
            byte[] compressed = slice(rpyc, slot.offset, slot.offset + slot.length);
            byte[] inflated = inflate(compressed);
            if (inflated == null) {
                return null;
            }
            byte[] rewritten = rewritePickle(inflated, translations, matched);
            if (rewritten == null) {
                payloads.add(compressed);
            } else {
                RpycStreamValidator.requireValid(rewritten, "renpy_dialogue_rewrite");
                payloads.add(deflate(rewritten));
                changed = true;
            }
        }
        if (!changed) {
            return null;
        }
        List<String> missed = new ArrayList<>();
        for (String key : translations.keySet()) {
            if (!matched.contains(key)) {
                missed.add(key);
            }
        }
        byte[] trailer = dataEnd < rpyc.length ? slice(rpyc, dataEnd, rpyc.length) : new byte[0];
        return new RewriteOutcome(rebuild(slots, payloads, trailer), matched.size(), missed);
    }

    /**
     * Matches a serialized Say.what value against the translation map,
     * tolerating the leading '.' some games keep in their text markers:
     * ".Hello and welcome..." must match the extracted "Hello and welcome...".
     */
    private static String lookupTranslation(Map<String, String> translations, String value,
                                            Set<String> matched) {
        String hit = translations.get(value);
        if (hit != null) {
            return hit;
        }
        if (value != null && value.length() > 1 && value.charAt(0) == '.') {
            String stripped = value.substring(1);
            hit = translations.get(stripped);
            if (hit != null) {
                matched.add(stripped);
                return hit;
            }
        }
        return null;
    }

    private static byte[] rewritePickle(byte[] data, Map<String, String> translations,
                                        Set<String> matched) {
        List<int[]> ops = LanguageMenuSupport.walk(data);
        if (ops == null || ops.isEmpty()) {
            return null;
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream(data.length + 256);
        Map<Integer, String> memo = new HashMap<>();
        String lastString = null;
        boolean waitingForWhat = false;
        boolean changed = false;
        int memoTrack = 0;
        List<Integer> frameOffsets = new ArrayList<>();

        for (int[] op : ops) {
            int code = op[0];
            String value = stringValue(data, op, memo);
            boolean stringLike = value != null;
            if (stringLike) {
                boolean isWhatValue = waitingForWhat;
                String direct = isWhatValue ? translations.get(value) : null;
                String replacement = direct != null ? direct
                        : (isWhatValue ? lookupTranslation(translations, value, matched) : null);
                boolean replace = replacement != null && !replacement.equals(value);
                if (replace) {
                    if (direct != null) {
                        matched.add(value);
                    }
                    writePickleString(out, replacement);
                    value = replacement;
                    changed = true;
                } else {
                    out.write(data, op[1], op[2] - op[1]);
                }

                if (isWhatValue) {
                    waitingForWhat = false;
                } else {
                    waitingForWhat = "what".equals(value);
                }
                lastString = value;
                continue;
            }

            if (code == 0x71 || code == 0x72) { // BINPUT / LONG_BINPUT
                if (lastString != null) {
                    memo.put(memoIndex(data, op, code), lastString);
                }
            } else if (code == 0x94) { // MEMOIZE
                if (lastString != null) {
                    memo.put(memoTrack, lastString);
                }
                memoTrack++;
            }
            if (code == 0x95) { // FRAME: keep opcode, fix length after rewrite
                frameOffsets.add(out.size());
            }
            out.write(data, op[1], op[2] - op[1]);
        }
        if (!changed) {
            return null;
        }
        byte[] result = out.toByteArray();
        patchFrameLengths(result, frameOffsets);
        return result;
    }

    /**
     * Rewrites the 8-byte length of every FRAME (0x95) opcode to the actual byte
     * distance to the next FRAME (or end of stream). String rewrites change frame
     * content lengths; leaving the original length desyncs protocol-5 unpicklers.
     */
    static byte[] patchFrameLengths(byte[] pickle, List<Integer> frameOffsets) {
        for (int f = 0; f < frameOffsets.size(); f++) {
            int start = frameOffsets.get(f);
            int contentStart = start + 9;
            int end = (f + 1 < frameOffsets.size()) ? frameOffsets.get(f + 1) : pickle.length;
            writeLongLe(pickle, start + 1, end - contentStart);
        }
        return pickle;
    }

    private static void writeLongLe(byte[] out, int pos, long value) {
        for (int i = 0; i < 8; i++) {
            out[pos + i] = (byte) (value >>> (i * 8));
        }
    }

    private static String stringValue(byte[] data, int[] op, Map<Integer, String> memo) {
        int code = op[0];
        if (code == 0x8c) { // SHORT_BINUNICODE
            int length = data[op[1] + 1] & 0xff;
            return new String(data, op[1] + 2, length, StandardCharsets.UTF_8);
        }
        if (code == 0x58) { // BINUNICODE
            int length = le32(data, op[1] + 1);
            if (length < 0 || op[1] + 5 + length > data.length) {
                return null;
            }
            return new String(data, op[1] + 5, length, StandardCharsets.UTF_8);
        }
        if (code == 0x54 || code == 0x55) { // BINSTRING / SHORT_BINSTRING
            int length = code == 0x54 ? le32(data, op[1] + 1) : data[op[1] + 1] & 0xff;
            int start = code == 0x54 ? op[1] + 5 : op[1] + 2;
            if (length < 0 || start + length > data.length) {
                return null;
            }
            return new String(data, start, length, StandardCharsets.UTF_8);
        }
        if (code == 0x68 || code == 0x6a) { // BINGET / LONG_BINGET
            return memo.get(memoIndex(data, op, code));
        }
        return null;
    }

    private static int memoIndex(byte[] data, int[] op, int code) {
        return code == 0x68 || code == 0x71
                ? data[op[1] + 1] & 0xff
                : le32(data, op[1] + 1);
    }

    private static List<Slot> parseSlots(byte[] rpyc) {
        List<Slot> slots = new ArrayList<>();
        int pos = RPC2_MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            long id = le32Unsigned(rpyc, pos);
            long offset = le32Unsigned(rpyc, pos + 4);
            long length = le32Unsigned(rpyc, pos + 8);
            pos += 12;
            if (id == 0) {
                return slots;
            }
            try {
                RenpyResourceLimits.checkRange(offset, length, rpyc.length);
                RenpyResourceLimits.checkCompressed(length);
            } catch (RuntimeException invalid) {
                return null;
            }
            slots.add(new Slot((int) id, (int) offset, (int) length));
        }
        return null;
    }

    private static byte[] inflate(byte[] compressed) throws IOException {
        RenpyResourceLimits.checkCompressed(compressed.length);
        try (InflaterInputStream in = new InflaterInputStream(new ByteArrayInputStream(compressed));
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            long total = 0;
            while ((read = in.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                total += read;
                RenpyResourceLimits.checkInflated(total);
                RenpyResourceLimits.checkInflateRatio(compressed.length, total);
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        }
    }

    private static byte[] deflate(byte[] data) throws IOException {
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        try (DeflaterOutputStream out = new DeflaterOutputStream(raw)) {
            out.write(data, 0, data.length);
        }
        return raw.toByteArray();
    }

    private static void writePickleString(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= 255) {
            out.write(0x8c);
            out.write(bytes.length);
        } else {
            out.write(0x58);
            writeIntLe(out, bytes.length);
        }
        out.write(bytes, 0, bytes.length);
    }

    private static byte[] rebuild(List<Slot> slots, List<byte[]> payloads, byte[] trailer) {
        int tableBytes = (slots.size() + 1) * 12;
        int dataStart = RPC2_MAGIC.length + tableBytes;
        ByteArrayOutputStream out = new ByteArrayOutputStream(dataStart + trailer.length);
        out.write(RPC2_MAGIC, 0, RPC2_MAGIC.length);
        for (int i = 0; i < slots.size(); i++) {
            writeIntLe(out, slots.get(i).id);
            writeIntLe(out, dataStart);
            writeIntLe(out, payloads.get(i).length);
            dataStart += payloads.get(i).length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        for (byte[] payload : payloads) {
            out.write(payload, 0, payload.length);
        }
        out.write(trailer, 0, trailer.length);
        return out.toByteArray();
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private static byte[] slice(byte[] data, int start, int end) {
        byte[] out = new byte[end - start];
        System.arraycopy(data, start, out, 0, out.length);
        return out;
    }

    private static int le32(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static long le32Unsigned(byte[] data, int pos) {
        return (data[pos] & 0xffL)
                | ((data[pos + 1] & 0xffL) << 8)
                | ((data[pos + 2] & 0xffL) << 16)
                | ((data[pos + 3] & 0xffL) << 24);
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static final class Slot {
        final int id;
        final int offset;
        final int length;

        Slot(int id, int offset, int length) {
            this.id = id;
            this.offset = offset;
            this.length = length;
        }
    }
}
