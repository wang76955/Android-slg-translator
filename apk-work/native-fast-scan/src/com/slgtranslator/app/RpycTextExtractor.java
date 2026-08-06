package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.InflaterInputStream;

/**
 * Structural Ren'Py rpyc text extractor. Walks the pickled AST byte stream and
 * pulls out the text users actually see (Say dialogue, menu choices, translate
 * blocks and screen Text nodes), preserving the exact original strings so the
 * translation keys match what Ren'Py looks up at runtime.
 */
public final class RpycTextExtractor {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    private static final Set<String> KEY_NAMES = new HashSet<>();
    private static final Set<String> TEXT_KEYS = new HashSet<>();

    static {
        String[] keys = {
            "linenumber", "col_offset", "filename", "name_version", "name_serial",
            "who", "what", "caption", "items", "arguments", "with", "attributes",
            "multiple", "rollback", "tag", "value", "label", "code", "language",
            "old", "new", "newloc", "store", "varname", "hide", "parameters",
            "expression", "block", "priority", "next", "parsed", "init_offset",
            "init_priority", "style_name", "properties", "type", "target",
            "global_label", "paired", "text", "text_value", "identifier",
            "translate_identifier", "alternate_translate_identifier",
        };
        for (String key : keys) {
            KEY_NAMES.add(key);
        }
        TEXT_KEYS.add("what");
        TEXT_KEYS.add("caption");
        TEXT_KEYS.add("old");
        TEXT_KEYS.add("text");
        TEXT_KEYS.add("text_value");
    }

    private RpycTextExtractor() {
    }

    /** Extracts user-visible text lines from a compiled rpyc file. */
    public static List<String> extractTexts(byte[] rpyc) throws java.io.IOException {
        return extractTexts(rpyc, false);
    }

    /**
     * Extracts text from a compiled rpyc file. When {@code onlyOld} is true the
     * extractor returns only translation old keys (the original-language strings
     * inside x-tl translation files), never the translated what/new values or
     * screen text. The scanner uses this mode for translation buckets so their
     * old keys can seed the supplementary corpus without polluting it.
     */
    public static List<String> extractTexts(byte[] rpyc, boolean onlyOld)
            throws java.io.IOException {
        List<RenpyTextRecord> records = extractRecords(rpyc, "", onlyOld);
        List<String> out = new ArrayList<>(records.size());
        for (RenpyTextRecord record : records) {
            out.add(record.text);
        }
        return out;
    }

    /**
     * Extracts user-visible records from one compiled rpyc script. The source
     * path is supplied by the caller so paths inside RPA archives retain their
     * virtual {@code archive.rpa!/game/script.rpyc} identity.
     */
    public static List<RenpyTextRecord> extractRecords(
            byte[] rpyc, String sourcePath, boolean onlyOld) throws java.io.IOException {
        ExtractState state = new ExtractState(sourcePath, onlyOld);
        byte[] pickle = readSlot(rpyc, 2);
        if (pickle == null) {
            pickle = readSlot(rpyc, 1);
        }
        if (pickle == null) {
            return state.records;
        }
        List<int[]> ops = LanguageMenuSupport.walk(pickle);
        if (ops == null) {
            return state.records;
        }
        Map<Integer, Object> memo = new HashMap<>();
        int memoTrack = 0;
        for (int i = 0; i < ops.size(); i++) {
            int[] op = ops.get(i);
            int code = op[0];
            if (code == 0x8c || code == 0x58) { // SHORT_BINUNICODE / BINUNICODE
                String s = LanguageMenuSupport.stringPayload(pickle, ops, i);
                state.consumeString(s);
            } else if (code == 0x68 || code == 0x6a) { // BINGET / LONG_BINGET
                int index = code == 0x68
                        ? (pickle[op[1] + 1] & 0xff)
                        : le32(pickle, op[1] + 1);
                Object v = memo.get(index);
                if (v instanceof String) {
                    state.consumeString((String) v);
                }
            } else if (code == 0x71 || code == 0x72) { // BINPUT / LONG_BINPUT
                int index = code == 0x71
                        ? (pickle[op[1] + 1] & 0xff)
                        : le32(pickle, op[1] + 1);
                if (state.lastString != null) {
                    memo.put(index, state.lastString);
                }
            } else if (code == 0x94) { // MEMOIZE
                if (state.lastString != null) {
                    memo.put(memoTrack, state.lastString);
                }
                memoTrack++;
            } else if (code == 0x75 || code == 0x65 || code == 0x61 || code == 0x73
                    || code == 0x62 || code == 0x31) { // SETITEMS/APPENDS/APPEND/SETITEM/BUILD/POP_MARK
                state.lastKey = null;
            } else if (code == 0x87) { // TUPLE3 ends a (label, condition, block) menu item
                state.afterTuple3 = true;
            }
        }
        for (String choice : state.choices) {
            state.addRecord(choice, RenpyTextRecord.Kind.MENU, "", true);
        }
        return state.records;
    }

    private static final class ExtractState {
        final List<RenpyTextRecord> records = new ArrayList<>();
        final List<String> choices = new ArrayList<>();
        final Map<String, Integer> occurrences = new HashMap<>();
        final String sourcePath;
        final boolean onlyOld;
        String lastString;
        String lastKey;
        String pendingSpeaker = "";
        boolean itemsMode;
        boolean afterTuple3;

        ExtractState(String sourcePath, boolean onlyOld) {
            this.sourcePath = sourcePath == null ? "" : sourcePath;
            this.onlyOld = onlyOld;
        }

        void consumeString(String value) throws java.io.IOException {
            if (value == null) {
                afterTuple3 = false;
                return;
            }
            if (!onlyOld && "items".equals(lastKey)) {
                if (isChoiceLabel(value)) {
                    choices.add(value);
                }
                itemsMode = true;
            } else if (!onlyOld && itemsMode && afterTuple3 && isChoiceLabel(value)) {
                choices.add(value);
            }
            if ("who".equals(lastKey)) {
                pendingSpeaker = value;
                lastKey = null;
            } else if (lastKey != null && TEXT_KEYS.contains(lastKey)) {
                if (isUserText(value)) {
                    String speaker = "what".equals(lastKey) ? pendingSpeaker : "";
                    addRecord(value, kindFor(lastKey),
                            speaker, true);
                }
                if ("what".equals(lastKey)) {
                    pendingSpeaker = "";
                }
                lastKey = null;
            } else if (KEY_NAMES.contains(value)) {
                if (!"what".equals(value)) {
                    pendingSpeaker = "";
                }
                lastKey = value;
            } else {
                pendingSpeaker = "";
                lastKey = null;
            }
            lastString = value;
            if (!onlyOld) {
                collectExtraRecords(value, this);
            }
            afterTuple3 = false;
        }

        void addRecord(String text, RenpyTextRecord.Kind kind, String speaker,
                       boolean coverageCertain) throws java.io.IOException {
            if (text == null || (onlyOld && kind != RenpyTextRecord.Kind.TRANSLATION_OLD)) {
                return;
            }
            RenpyResourceLimits.checkTextLength(text.length());
            RenpyResourceLimits.checkTextRecordCount((long) records.size() + 1L);
            String occurrenceKey = sourcePath + '\u0000' + text;
            Integer previous = occurrences.get(occurrenceKey);
            int occurrence = previous == null ? 1 : previous + 1;
            occurrences.put(occurrenceKey, occurrence);
            records.add(new RenpyTextRecord(text, kind, speaker, "", sourcePath,
                    -1, occurrence, coverageCertain));
        }
    }

    private static RenpyTextRecord.Kind kindFor(String key) {
        if ("what".equals(key)) {
            return RenpyTextRecord.Kind.DIALOGUE;
        }
        if ("old".equals(key)) {
            return RenpyTextRecord.Kind.TRANSLATION_OLD;
        }
        return RenpyTextRecord.Kind.UI_STRING;
    }

    /**
     * Screen/UI text is marked with the translatable _("...") call in the
     * pickle source payloads, and character display names are defined as
     * Character("Name", ...) calls. Both are looked up at runtime through
     * Ren'Py string translation, so they are collected here alongside the
     * structural dialogue. Names with interpolation ([name]) or backslashes
     * are skipped.
     */
    private static void collectExtraRecords(String s, ExtractState state)
            throws java.io.IOException {
        if (s == null || s.isEmpty()) {
            return;
        }
        java.util.regex.Matcher marked = MARKED_TEXT.matcher(s);
        while (marked.find()) {
            String text = marked.group(1);
            if (isMarkedText(text)) {
                state.addRecord(text, RenpyTextRecord.Kind.UI_STRING, "", false);
            }
        }
        if (s.indexOf("Character(") >= 0 || s.indexOf("Character('") >= 0) {
            java.util.regex.Matcher names = CHARACTER_NAME.matcher(s);
            while (names.find()) {
                String name = names.group(1);
                if (isCharacterName(name)) {
                    state.addRecord(name, RenpyTextRecord.Kind.CHARACTER_NAME, "", false);
                }
            }
        }
        collectSourceCallRecords(s, state);
    }

    /**
     * Source payloads keep the raw .rpy code of custom functions such as
     * send_phone_message("Aine", "message", "channel", ...) or Ren'Py's
     * _VolumePreference(u"Music Volume", 'music', ...) preference helpers. The
     * string-literal arguments are user-visible text, so message-style calls
     * contribute their first two string arguments and preference helpers
     * contribute their label. Variable arguments, paths and empty strings
     * are rejected by isUserText.
     */
    private static void collectSourceCallRecords(String s, ExtractState state)
            throws java.io.IOException {
        if (s == null || s.isEmpty()) {
            return;
        }
        java.util.regex.Matcher call = SOURCE_CALL.matcher(s);
        while (call.find()) {
            String func = call.group(1);
            String args = call.group(2);
            if (func == null || args == null) {
                continue;
            }
            String lower = func.toLowerCase(java.util.Locale.ROOT);
            boolean messageStyle = lower.contains("message") || lower.contains("phone")
                    || lower.contains("chat") || lower.contains("dm");
            boolean preferenceStyle = lower.startsWith("_") && lower.endsWith("preference");
            if (!messageStyle && !preferenceStyle) {
                continue;
            }
            int limit = messageStyle ? 2 : 1;
            int collected = 0;
            for (String arg : splitCallArgs(args)) {
                String value = unquoteLiteral(arg);
                if (value != null && isUserText(value)) {
                    state.addRecord(value, RenpyTextRecord.Kind.CUSTOM_STATEMENT, "", false);
                    collected++;
                    if (collected >= limit) {
                        break;
                    }
                }
            }
        }
    }

    private static final java.util.regex.Pattern MARKED_TEXT = java.util.regex.Pattern.compile(
            "_\\s*\\(\"((?:[^\"\\\\]|\\\\.)*)\"\\)");
    private static final java.util.regex.Pattern CHARACTER_NAME = java.util.regex.Pattern.compile(
            "Character\\(\\s*[\"']([^\"']+)[\"']");
    private static final java.util.regex.Pattern SOURCE_CALL = java.util.regex.Pattern.compile(
            "([A-Za-z_][A-Za-z0-9_]*)\\s*\\(([^()]*)\\)");

    private static boolean isMarkedText(String s) {
        String trimmed = s.trim();
        if (trimmed.length() < 2) {
            return false;
        }
        if (trimmed.matches("\\d+")) {
            return false;
        }
        for (int i = 0; i < trimmed.length(); i++) {
            char c = trimmed.charAt(i);
            if (c < 0x20 || c == 0x7f) {
                return false;
            }
        }
        return true;
    }

    private static boolean isCharacterName(String s) {
        if (s == null || s.isEmpty() || s.length() > 40) {
            return false;
        }
        if (s.indexOf('[') >= 0 || s.indexOf('\\') >= 0 || s.indexOf('/') >= 0) {
            return false;
        }
        if (KEY_NAMES.contains(s)) {
            return false;
        }
        boolean hasLetter = false;
        boolean hasQuestion = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isLetter(c)) {
                hasLetter = true;
            } else if (c == '?') {
                hasQuestion = true;
            }
        }
        return hasLetter || hasQuestion;
    }

    /**
     * Menu choice labels come from the Menu.items tuples. Unlike dialogue,
     * short single-token labels such as "Fine" or "Sky" are legitimate
     * user-visible choices, so the generic identifier filter is relaxed for
     * capitalized words. Attr keys, paths and lower-case identifiers are
     * still rejected to keep pickle attribute noise out.
     */
    private static boolean isChoiceLabel(String s) {
        if (s == null || s.isEmpty()) {
            return false;
        }
        if (s.indexOf('/') >= 0 || s.indexOf('\\') >= 0) {
            return false;
        }
        if (KEY_NAMES.contains(s)) {
            return false;
        }
        if (isUserText(s)) {
            return true;
        }
        // Money choices such as "$1100" (menu option amounts) are user-visible.
        if (s.matches("^[$\u00a5\u20ac\u00a3]\\d+([.,]\\d+)?$")) {
            return true;
        }
        if (s.length() <= 40) {
            boolean lettersOnly = true;
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                if (!Character.isLetter(c)) {
                    lettersOnly = false;
                    break;
                }
            }
            if (lettersOnly && Character.isUpperCase(s.charAt(0))) {
                return true;
            }
        }
        return false;
    }

    private static boolean isUserText(String s) {
        if (s == null || s.length() < 2) {
            return false;
        }
        boolean hasLetter = false;
        boolean allDigits = true;
        boolean hasSpaceOrPunct = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isLetter(c)) {
                hasLetter = true;
                allDigits = false;
            } else if (Character.isDigit(c)) {
                // digits are fine
            } else {
                allDigits = false;
                if (Character.isWhitespace(c) || ".,!?;:()[]{}<>-…—'\"*$%&@+=~^`|\\".indexOf(c) >= 0) {
                    hasSpaceOrPunct = true;
                }
            }
        }
        if (!hasLetter || allDigits) {
            return false;
        }
        // Paths and file names.  Ren'Py markup tags like {/i}, {/b},
        // {/color} contain '/' but are not path separators, so strip
        // all {…} tags before checking for path characters.
        String pathCheck = s.replaceAll("\\{[^}]*\\}", "");
        if (pathCheck.indexOf('/') >= 0 || pathCheck.indexOf('\\') >= 0) {
            return false;
        }
        if (s.length() > 4) {
            String lower = s.toLowerCase();
            for (String ext : new String[]{".rpy", ".rpyc", ".rpym", ".py", ".png", ".jpg",
                    ".jpeg", ".webp", ".ogg", ".mp3", ".wav", ".ttf", ".otf", ".json", ".xml"}) {
                if (lower.endsWith(ext)) {
                    return false;
                }
            }
        }
        // Pure single-token identifiers (variable names, style names, keywords).
        if (!hasSpaceOrPunct && s.length() <= 40) {
            boolean identifier = true;
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                if (!(Character.isLetterOrDigit(c) || c == '_' || c == '-')) {
                    identifier = false;
                    break;
                }
            }
            if (identifier) {
                return false;
            }
        }
        return true;
    }


    private static List<String> splitCallArgs(String args) {
        List<String> result = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        char quote = 0;
        boolean escaped = false;
        for (int i = 0; i < args.length(); i++) {
            char c = args.charAt(i);
            if (escaped) {
                current.append(c);
                escaped = false;
                continue;
            }
            if (c == '\\') {
                current.append(c);
                escaped = true;
                continue;
            }
            if (quote != 0) {
                current.append(c);
                if (c == quote) {
                    quote = 0;
                }
                continue;
            }
            if (c == '\'' || c == '"') {
                quote = c;
                current.append(c);
                continue;
            }
            if (c == ',') {
                result.add(current.toString());
                current.setLength(0);
                continue;
            }
            current.append(c);
        }
        result.add(current.toString());
        return result;
    }

    private static String unquoteLiteral(String arg) {
        String value = arg.trim();
        int start = 0;
        while (start < value.length()) {
            char c = value.charAt(start);
            if (c == 'u' || c == 'r' || c == 'b') {
                start++;
                continue;
            }
            break;
        }
        value = value.substring(start).trim();
        if (value.length() < 2) {
            return null;
        }
        char quote = value.charAt(0);
        if (quote != '\'' && quote != '"') {
            return null;
        }
        if (value.charAt(value.length() - 1) != quote) {
            return null;
        }
        String body = value.substring(1, value.length() - 1);
        StringBuilder out = new StringBuilder();
        boolean escaped = false;
        for (int i = 0; i < body.length(); i++) {
            char c = body.charAt(i);
            if (escaped) {
                switch (c) {
                    case 'n':
                        out.append('\n');
                        break;
                    case 't':
                        out.append('\t');
                        break;
                    case 'r':
                        out.append('\r');
                        break;
                    case '\\':
                        out.append('\\');
                        break;
                    default:
                        out.append(c);
                        break;
                }
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else {
                out.append(c);
            }
        }
        if (escaped) {
            out.append('\\');
        }
        return out.toString();
    }

    // ------------------------------------------------------------------
    // Low level helpers
    // ------------------------------------------------------------------

    private static byte[] readSlot(byte[] rpyc, int slotId) throws java.io.IOException {
        if (rpyc == null || rpyc.length == 0) {
            return null;
        }
        if (slotId == 1 && !startsWith(rpyc, RPC2_MAGIC)) {
            return inflateWhole(rpyc);
        }
        int pos = RPC2_MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            long id = le32Unsigned(rpyc, pos);
            long offset = le32Unsigned(rpyc, pos + 4);
            long length = le32Unsigned(rpyc, pos + 8);
            if (id == 0) {
                return null;
            }
            if (id == slotId) {
                RenpyResourceLimits.checkRange(offset, length, rpyc.length);
                RenpyResourceLimits.checkCompressed(length);
                return inflateRange(rpyc, (int) offset, (int) length);
            }
            pos += 12;
        }
        return null;
    }

    private static byte[] inflateRange(byte[] data, int offset, int length)
            throws java.io.IOException {
        java.util.zip.Inflater inflater = new java.util.zip.Inflater();
        inflater.setInput(data, offset, length);
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            long total = 0;
            while (!inflater.finished()) {
                RenpyResourceLimits.checkInterrupted();
                int read;
                try {
                    read = inflater.inflate(buffer);
                } catch (java.util.zip.DataFormatException e) {
                    throw new IOException("Ren'Py zlib data is invalid", e);
                }
                if (read > 0) {
                    total += read;
                    RenpyResourceLimits.checkInflated(total);
                    RenpyResourceLimits.checkInflateRatio(length, total);
                    out.write(buffer, 0, read);
                } else if (inflater.needsDictionary() || inflater.needsInput()) {
                    throw new IOException("Ren'Py zlib data is truncated");
                } else {
                    throw new IOException("Ren'Py zlib data is invalid");
                }
            }
            if (inflater.getRemaining() != 0) {
                throw new IOException("Ren'Py zlib data has trailing bytes");
            }
            return out.toByteArray();
        } finally {
            inflater.end();
        }
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

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data == null || data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private static byte[] inflateWhole(byte[] data) throws java.io.IOException {
        RenpyResourceLimits.checkCompressed(data.length);
        return inflateRange(data, 0, data.length);
    }
}
