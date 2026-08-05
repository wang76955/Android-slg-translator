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
    public static List<String> extractTexts(byte[] rpyc) {
        return extractTexts(rpyc, false);
    }

    /**
     * Extracts text from a compiled rpyc file. When {@code onlyOld} is true the
     * extractor returns only translation old keys (the original-language strings
     * inside x-tl translation files), never the translated what/new values or
     * screen text. The scanner uses this mode for translation buckets so their
     * old keys can seed the supplementary corpus without polluting it.
     */
    public static List<String> extractTexts(byte[] rpyc, boolean onlyOld) {
        List<String> out = new ArrayList<>();
        byte[] pickle = readSlot(rpyc, 2);
        if (pickle == null) {
            pickle = readSlot(rpyc, 1);
        }
        if (pickle == null) {
            return out;
        }
        List<int[]> ops = LanguageMenuSupport.walk(pickle);
        if (ops == null) {
            return out;
        }
        Map<Integer, Object> memo = new HashMap<>();
        int memoTrack = 0;
        String lastString = null;
        String lastKey = null;
        boolean itemsMode = false;
        boolean afterTuple3 = false;
        List<String> choices = new ArrayList<>();
        Set<String> extraSeen = new HashSet<>();
        for (int i = 0; i < ops.size(); i++) {
            int[] op = ops.get(i);
            int code = op[0];
            if (code == 0x8c || code == 0x58) { // SHORT_BINUNICODE / BINUNICODE
                String s = LanguageMenuSupport.stringPayload(pickle, ops, i);
                if (s != null) {
                    if ("items".equals(lastKey)) {
                        if (isChoiceLabel(s)) {
                            choices.add(s);
                        }
                        itemsMode = true;
                    } else if (itemsMode && afterTuple3 && isChoiceLabel(s)) {
                        choices.add(s);
                    }
                    if (lastKey != null && TEXT_KEYS.contains(lastKey)) {
                        if ((!onlyOld || "old".equals(lastKey)) && isUserText(s)) {
                            out.add(s);
                        }
                        lastKey = null;
                    } else if (KEY_NAMES.contains(s)) {
                        lastKey = s;
                    } else {
                        lastKey = null;
                    }
                    lastString = s;
                    if (!onlyOld) {
                        collectExtraTexts(s, out, extraSeen);
                    }
                }
                afterTuple3 = false;
            } else if (code == 0x68 || code == 0x6a) { // BINGET / LONG_BINGET
                int index = code == 0x68
                        ? (pickle[op[1] + 1] & 0xff)
                        : le32(pickle, op[1] + 1);
                Object v = memo.get(index);
                if (v instanceof String) {
                    String s = (String) v;
                    if ("items".equals(lastKey)) {
                        if (isChoiceLabel(s)) {
                            choices.add(s);
                        }
                        itemsMode = true;
                    } else if (itemsMode && afterTuple3 && isChoiceLabel(s)) {
                        choices.add(s);
                    }
                    if (lastKey != null && TEXT_KEYS.contains(lastKey)) {
                        if ((!onlyOld || "old".equals(lastKey)) && isUserText(s)) {
                            out.add(s);
                        }
                        lastKey = null;
                    } else if (KEY_NAMES.contains(s)) {
                        lastKey = s;
                    } else {
                        lastKey = null;
                    }
                    lastString = s;
                    if (!onlyOld) {
                        collectExtraTexts(s, out, extraSeen);
                    }
                }
                afterTuple3 = false;
            } else if (code == 0x71 || code == 0x72) { // BINPUT / LONG_BINPUT
                int index = code == 0x71
                        ? (pickle[op[1] + 1] & 0xff)
                        : le32(pickle, op[1] + 1);
                if (lastString != null) {
                    memo.put(index, lastString);
                }
            } else if (code == 0x94) { // MEMOIZE
                if (lastString != null) {
                    memo.put(memoTrack, lastString);
                }
                memoTrack++;
            } else if (code == 0x75 || code == 0x65 || code == 0x61 || code == 0x73
                    || code == 0x62 || code == 0x31) { // SETITEMS/APPENDS/APPEND/SETITEM/BUILD/POP_MARK
                lastKey = null;
            } else if (code == 0x87) { // TUPLE3 ends a (label, condition, block) menu item
                afterTuple3 = true;
            }
        }
        out.addAll(choices);
        return out;
    }

    /**
     * Screen/UI text is marked with the translatable _("...") call in the
     * pickle source payloads, and character display names are defined as
     * Character("Name", ...) calls. Both are looked up at runtime through
     * Ren'Py string translation, so they are collected here alongside the
     * structural dialogue. Names with interpolation ([name]) or backslashes
     * are skipped.
     */
    private static void collectExtraTexts(String s, List<String> out, Set<String> seen) {
        if (s == null || s.isEmpty()) {
            return;
        }
        java.util.regex.Matcher marked = MARKED_TEXT.matcher(s);
        while (marked.find()) {
            String text = marked.group(1);
            if (isMarkedText(text) && seen.add(text)) {
                out.add(text);
            }
        }
        if (s.indexOf("Character(") >= 0 || s.indexOf("Character('") >= 0) {
            java.util.regex.Matcher names = CHARACTER_NAME.matcher(s);
            while (names.find()) {
                String name = names.group(1);
                if (isCharacterName(name) && seen.add(name)) {
                    out.add(name);
                }
            }
        }
        collectSourceCallTexts(s, out, seen);
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
    private static void collectSourceCallTexts(String s, List<String> out, Set<String> seen) {
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
                if (value != null && isUserText(value) && seen.add(value)) {
                    out.add(value);
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

    private static byte[] readSlot(byte[] rpyc, int slotId) {
        int pos = RPC2_MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            int id = le32(rpyc, pos);
            int offset = le32(rpyc, pos + 4);
            int length = le32(rpyc, pos + 8);
            if (id == 0) {
                return null;
            }
            if (id == slotId) {
                if (offset < 0 || length < 0 || offset + length > rpyc.length) {
                    return null;
                }
                try (InputStream in = new InflaterInputStream(
                        new ByteArrayInputStream(rpyc, offset, length));
                     ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                    byte[] buffer = new byte[8192];
                    int read;
                    while ((read = in.read(buffer)) != -1) {
                        out.write(buffer, 0, read);
                    }
                    return out.toByteArray();
                } catch (IOException e) {
                    return null;
                }
            }
            pos += 12;
        }
        return null;
    }

    private static int le32(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }
}
