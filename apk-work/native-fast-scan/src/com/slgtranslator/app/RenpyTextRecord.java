package com.slgtranslator.app;

public final class RenpyTextRecord {
    public enum Kind {
        DIALOGUE, MENU, CHARACTER_NAME, UI_STRING,
        TRANSLATION_OLD, CUSTOM_STATEMENT, UNKNOWN
    }

    public final String text;
    public final Kind kind;
    public final String speaker;
    public final String identifier;
    public final String sourcePath;
    public final int sourceLine;
    public final int occurrence;
    public final boolean coverageCertain;

    public RenpyTextRecord(String text, Kind kind, String speaker, String identifier,
                           String sourcePath, int sourceLine, int occurrence,
                           boolean coverageCertain) {
        this.text = text == null ? "" : text;
        this.kind = kind == null ? Kind.UNKNOWN : kind;
        this.speaker = speaker == null ? "" : speaker;
        this.identifier = identifier == null ? "" : identifier;
        this.sourcePath = sourcePath == null ? "" : sourcePath;
        this.sourceLine = sourceLine;
        this.occurrence = occurrence;
        this.coverageCertain = coverageCertain;
    }
}
