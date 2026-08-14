package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Pattern;

/** Validates that matched glossary terms survive translation. */
public final class RenpyGlossaryValidator {
    public enum MatchMode { EXACT, WHOLE_WORD, CONTEXT }

    public static final class GlossaryTerm {
        public final String source;
        public final String target;
        public final MatchMode matchMode;
        public final String context;

        public GlossaryTerm(String source, String target, MatchMode matchMode, String context) {
            this.source = source;
            this.target = target;
            this.matchMode = matchMode == null ? MatchMode.WHOLE_WORD : matchMode;
            this.context = context;
        }
    }

    private RenpyGlossaryValidator() {}

    public static RenpyTextValidator.ValidationResult validate(
            String oldText, String newText, List<GlossaryTerm> terms) {
        String source = oldText == null ? "" : oldText;
        String translation = newText == null ? "" : newText;
        List<String> codes = new ArrayList<>();
        if (terms != null) {
            for (GlossaryTerm term : terms) {
                if (term != null && matches(source, term)
                        && term.target != null && !translation.contains(term.target)) {
                    codes.add("glossary_term_missing:" + term.source);
                }
            }
        }
        return new RenpyTextValidator.ValidationResult(codes.isEmpty(), codes);
    }

    private static boolean matches(String text, GlossaryTerm term) {
        switch (term.matchMode) {
            case EXACT:
                return text.trim().equals(value(term.source).trim());
            case CONTEXT:
                return !value(term.context).isEmpty()
                        && hasWord(text, term.context)
                        && hasWord(text, term.source);
            case WHOLE_WORD:
            default:
                return hasWord(text, term.source);
        }
    }

    private static boolean hasWord(String text, String word) {
        if (word == null || word.isEmpty()) return false;
        return Pattern.compile("(^|[^A-Za-z0-9_])" + Pattern.quote(word)
                + "([^A-Za-z0-9_]|$)").matcher(text).find();
    }

    private static String value(String text) {
        return text == null ? "" : text;
    }
}
