package com.slgtranslator.app;

/**
 * One translatable unit inside a structured asset (JSON / CSV / TSV /
 * properties / plain text). {@code recordId} is the stable identity used by
 * the writer's re-parse verification.
 */
public final class StructuredTextRecord {
    public final String recordId;
    public final String sourceOwner;
    public final String sourcePath;
    public final String format;
    public final String keyPath;
    public final String sourceText;
    public final String valueType;
    public final int index;

    public StructuredTextRecord(String recordId, String sourceOwner, String sourcePath,
            String format, String keyPath, String sourceText, String valueType, int index) {
        this.recordId = recordId;
        this.sourceOwner = sourceOwner;
        this.sourcePath = sourcePath;
        this.format = format;
        this.keyPath = keyPath;
        this.sourceText = sourceText;
        this.valueType = valueType;
        this.index = index;
    }
}
