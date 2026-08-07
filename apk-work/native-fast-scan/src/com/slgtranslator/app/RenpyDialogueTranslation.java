package com.slgtranslator.app;

/**
 * One context-specific Ren'Py dialogue translation.
 *
 * The identifier is copied from the compiled Say/TranslateSay object.  It is
 * never derived from text, source position, or list order: those values are
 * not stable dialogue IDs and using them would make old saves unsafe.
 */
public final class RenpyDialogueTranslation {
    public final String identifier;
    public final String speakerExpression;
    public final String oldText;
    public final String newText;
    public final String sourcePath;
    public final int sourceLine;

    public RenpyDialogueTranslation(String identifier, String speakerExpression,
                                    String oldText, String newText,
                                    String sourcePath, int sourceLine) {
        this.identifier = requireIdentifier(identifier);
        this.speakerExpression = speakerExpression == null ? "" : speakerExpression;
        this.oldText = requireText(oldText, "oldText");
        this.newText = requireText(newText, "newText");
        this.sourcePath = sourcePath == null ? "" : sourcePath;
        this.sourceLine = sourceLine < 0 ? -1 : sourceLine;
    }

    /** Creates an extracted source entry before a translation is available. */
    public static RenpyDialogueTranslation source(String identifier,
                                                   String speakerExpression,
                                                   String oldText,
                                                   String sourcePath,
                                                   int sourceLine) {
        return new RenpyDialogueTranslation(identifier, speakerExpression,
                oldText, oldText, sourcePath, sourceLine);
    }

    public RenpyDialogueTranslation withNewText(String translation) {
        return new RenpyDialogueTranslation(identifier, speakerExpression,
                oldText, translation, sourcePath, sourceLine);
    }

    /** Advanced mode must not silently accept an empty or synthetic ID. */
    public boolean isUsableForAdvancedMode() {
        return !identifier.isEmpty() && !oldText.isEmpty() && !newText.isEmpty();
    }

    private static String requireIdentifier(String value) {
        String normalized = value == null ? "" : value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("dialogue identifier is required");
        }
        if (normalized.length() > 256
                || !normalized.matches("[A-Za-z0-9._:-]+")) {
            throw new IllegalArgumentException("dialogue identifier is not a safe literal");
        }
        return normalized;
    }

    private static String requireText(String value, String field) {
        if (value == null) {
            throw new IllegalArgumentException(field + " is required");
        }
        return value;
    }
}
