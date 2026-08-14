package com.slgtranslator.app;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Deterministic safety checks for generated Ren'Py dialogue text. */
public final class RenpyTextValidator {
    private static final Pattern SENTINEL = Pattern.compile("__SLGPH(\\d+)__");
    private static final Pattern INTERPOLATION = Pattern.compile("\\[[^\\]\\r\\n]+\\]");
    private static final Pattern PRINTF = Pattern.compile(
            "%((?:\\([A-Za-z_][A-Za-z0-9_]*\\))|(?:[0-9]*\\$)?)[sdif]");
    private static final Pattern TAG = Pattern.compile("\\{([^{}]*)\\}");
    private static final Set<String> PAIRED_TAGS;
    private static final Set<String> SELF_CLOSING_TAGS;

    static {
        Set<String> paired = new HashSet<>();
        Collections.addAll(paired, "b", "i", "font", "a", "color", "size", "outline", "alpha",
                "swap", "alt", "sc", "fi", "bt");
        PAIRED_TAGS = Collections.unmodifiableSet(paired);
        Set<String> selfClosing = new HashSet<>();
        Collections.addAll(selfClosing, "w", "p", "nw", "fast", "clear", "space", "image", "vspace",
                "hbox", "rb", "rt", "k", "cps", "done");
        SELF_CLOSING_TAGS = Collections.unmodifiableSet(selfClosing);
    }

    public static final class ValidationResult {
        public final boolean valid;
        public final List<String> codes;

        ValidationResult(boolean valid, List<String> codes) {
            this.valid = valid;
            this.codes = Collections.unmodifiableList(new ArrayList<>(codes));
        }
    }

    private RenpyTextValidator() {
    }

    public static ValidationResult validate(String oldText, String newText) {
        String oldValue = oldText == null ? "" : oldText;
        String newValue = newText == null ? "" : newText;
        List<String> codes = new ArrayList<>();
        if (newValue.trim().length() == 0) {
            add(codes, "empty_translation");
        }
        validateSentinels(oldValue, newValue, codes);

        TagResult oldTags = parseTags(oldValue);
        TagResult newTags = parseTags(newValue);
        // A faithful reproduction of the original's tag signature is accepted
        // even when the source game shipped malformed or misnested markup
        // ({i} without a close, {b}{i}...{/b}{/i}, custom tags, ...): Ren'Py
        // renders it the same way as the original, so we introduce no new
        // breakage. Any signature change or newly misnested structure fails.
        if (!oldTags.signature.equals(newTags.signature)) {
            add(codes, "tag_unbalanced");
        }
        if (newTags.misnested && !oldTags.misnested) {
            add(codes, "tag_misnested");
        }

        if (!tokens(oldValue, INTERPOLATION).equals(tokens(newValue, INTERPOLATION))) {
            add(codes, "interpolation_changed");
        }
        if (!tokens(oldValue, PRINTF).equals(tokens(newValue, PRINTF))) {
            add(codes, "printf_changed");
        }
        if (SENTINEL.matcher(newValue).find()) {
            add(codes, "unrestored_sentinel");
        }
        return new ValidationResult(codes.isEmpty(), codes);
    }

    private static void validateSentinels(String oldValue, String newValue, List<String> codes) {
        List<Integer> expected = sentinelIndexes(oldValue);
        List<Integer> actual = sentinelIndexes(newValue);
        if (expected.equals(actual)) {
            return;
        }
        if (actual.size() < expected.size() || !containsAllWithCounts(expected, actual)) {
            add(codes, "sentinel_missing");
        }
        if (actual.size() > expected.size() || !containsAllWithCounts(actual, expected)) {
            add(codes, "sentinel_extra");
        }
        if (expected.size() == actual.size() && containsAllWithCounts(expected, actual)) {
            add(codes, "sentinel_reordered");
        }
    }

    private static boolean containsAllWithCounts(List<Integer> wanted, List<Integer> available) {
        Map<Integer, Integer> counts = new HashMap<>();
        for (Integer value : available) {
            Integer count = counts.get(value);
            counts.put(value, count == null ? 1 : count + 1);
        }
        for (Integer value : wanted) {
            Integer count = counts.get(value);
            if (count == null || count == 0) {
                return false;
            }
            counts.put(value, count - 1);
        }
        return true;
    }

    private static List<Integer> sentinelIndexes(String value) {
        List<Integer> indexes = new ArrayList<>();
        Matcher matcher = SENTINEL.matcher(value);
        while (matcher.find()) {
            try {
                indexes.add(Integer.parseInt(matcher.group(1)));
            } catch (NumberFormatException ignored) {
                indexes.add(-1);
            }
        }
        return indexes;
    }

    private static List<String> tokens(String value, Pattern pattern) {
        List<String> found = new ArrayList<>();
        Matcher matcher = pattern.matcher(value);
        while (matcher.find()) {
            found.add(matcher.group());
        }
        return found;
    }

    private static final class TagResult {
        final boolean unbalanced;
        final boolean misnested;
        final List<String> signature;

        TagResult(boolean unbalanced, boolean misnested, List<String> signature) {
            this.unbalanced = unbalanced;
            this.misnested = misnested;
            this.signature = signature;
        }
    }

    private static TagResult parseTags(String value) {
        Deque<String> stack = new ArrayDeque<>();
        List<String> signature = new ArrayList<>();
        boolean unbalanced = braceBalance(value) != 0;
        boolean misnested = false;
        Matcher matcher = TAG.matcher(value);
        while (matcher.find()) {
            String raw = matcher.group(1).trim();
            if (raw.length() == 0) {
                continue;
            }
            boolean closing = raw.charAt(0) == '/';
            String body = closing ? raw.substring(1).trim() : raw;
            String name = tagName(body);
            if (name.length() == 0) {
                signature.add("raw:" + raw);
                continue;
            }
            if (!PAIRED_TAGS.contains(name) && !SELF_CLOSING_TAGS.contains(name)) {
                signature.add("raw:" + raw);
                if (closing) {
                    unbalanced = true;
                }
                continue;
            }
            String normalized = closing ? "/" + name : name + tagArgument(body, name);
            signature.add(normalized);
            if (!PAIRED_TAGS.contains(name)) {
                if (closing) {
                    unbalanced = true;
                }
                continue;
            }
            if (closing) {
                if (stack.isEmpty()) {
                    unbalanced = true;
                } else if (!stack.peek().equals(name)) {
                    misnested = true;
                    unbalanced = true;
                    removeMatchingTag(stack, name);
                } else {
                    stack.pop();
                }
            } else {
                stack.push(name);
            }
        }
        if (!stack.isEmpty()) {
            unbalanced = true;
        }
        return new TagResult(unbalanced, misnested, signature);
    }

    private static int braceBalance(String value) {
        int balance = 0;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c == '{') {
                balance++;
            } else if (c == '}') {
                balance--;
            }
        }
        return balance;
    }

    private static void removeMatchingTag(Deque<String> stack, String name) {
        while (!stack.isEmpty()) {
            String top = stack.pop();
            if (top.equals(name)) {
                return;
            }
        }
    }

    private static String tagName(String body) {
        int end = 0;
        while (end < body.length()) {
            char c = body.charAt(end);
            if (!Character.isLetter(c)) {
                break;
            }
            end++;
        }
        return body.substring(0, end).toLowerCase(java.util.Locale.ROOT);
    }

    private static String tagArgument(String body, String name) {
        if (body.length() <= name.length()) {
            return "";
        }
        return body.substring(name.length()).trim();
    }

    private static void add(List<String> codes, String code) {
        if (!codes.contains(code)) {
            codes.add(code);
        }
    }
}
