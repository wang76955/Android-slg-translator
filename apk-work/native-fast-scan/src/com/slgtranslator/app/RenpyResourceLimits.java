package com.slgtranslator.app;

/** Shared limits for untrusted Ren'Py scripts, archives, and text payloads. */
public final class RenpyResourceLimits {

    public static final long MAX_SINGLE_SCRIPT_COMPRESSED = 64L * 1024 * 1024;
    public static final long MAX_SINGLE_SCRIPT_INFLATED = 256L * 1024 * 1024;
    public static final long MAX_TOTAL_SCRIPT_INFLATED = 1024L * 1024 * 1024;
    public static final long MAX_SINGLE_SCRIPT_WORKING_SET = 96L * 1024 * 1024;
    public static final long MAX_TOTAL_SCRIPT_WORKING_SET = 384L * 1024 * 1024;
    public static final int MAX_RPA_ENTRIES = 200_000;
    public static final int MAX_TEXT_RECORDS = 1_000_000;
    public static final int MAX_TEXT_LENGTH = 1_000_000;
    public static final int MAX_INFLATE_RATIO = 200;

    public static final class LimitException extends RuntimeException {
        public final String code;

        public LimitException(String code, String message) {
            super(code + ": " + message);
            this.code = code;
        }
    }

    private RenpyResourceLimits() {
    }

    public static void checkCompressed(long compressed) throws LimitException {
        if (compressed < 0) {
            throw invalidRange("compressed length is negative");
        }
        if (compressed > MAX_SINGLE_SCRIPT_COMPRESSED) {
            throw new LimitException("renpy_limit_compressed",
                    "compressed Ren'Py script exceeds the per-script limit");
        }
    }

    public static void checkInflated(long inflated) throws LimitException {
        if (inflated < 0) {
            throw invalidRange("inflated length is negative");
        }
        if (inflated > MAX_SINGLE_SCRIPT_INFLATED) {
            throw new LimitException("renpy_limit_inflated",
                    "inflated Ren'Py script exceeds the per-script limit");
        }
    }

    public static void checkTotalInflated(long total) throws LimitException {
        if (total < 0) {
            throw invalidRange("total inflated length is negative");
        }
        if (total > MAX_TOTAL_SCRIPT_INFLATED) {
            throw new LimitException("renpy_limit_inflated",
                    "total inflated Ren'Py scripts exceed the scan limit");
        }
    }

    public static void checkWorkingSet(long inflated) throws LimitException {
        if (inflated < 0) {
            throw invalidRange("working-set length is negative");
        }
        if (inflated > MAX_SINGLE_SCRIPT_WORKING_SET) {
            throw new LimitException("renpy_memory_budget_exceeded",
                    "single Ren'Py script exceeds the parser working-set budget");
        }
    }

    public static void checkTotalWorkingSet(long total) throws LimitException {
        if (total < 0) {
            throw invalidRange("total working-set length is negative");
        }
        if (total > MAX_TOTAL_SCRIPT_WORKING_SET) {
            throw new LimitException("renpy_memory_budget_exceeded",
                    "Ren'Py scripts exceed the scan working-set budget");
        }
    }

    public static void checkInflateRatio(long compressed, long inflated)
            throws LimitException {
        if (compressed < 0 || inflated < 0) {
            throw invalidRange("inflate lengths must not be negative");
        }
        if (inflated == 0) {
            return;
        }
        if (compressed == 0
                || (compressed <= Long.MAX_VALUE / MAX_INFLATE_RATIO
                && inflated > compressed * (long) MAX_INFLATE_RATIO)) {
            throw new LimitException("renpy_limit_ratio",
                    "inflated/compressed ratio exceeds the Ren'Py limit");
        }
    }

    public static void checkEntryCount(long count) throws LimitException {
        if (count < 0) {
            throw invalidRange("RPA entry count is negative");
        }
        if (count > MAX_RPA_ENTRIES) {
            throw new LimitException("renpy_limit_entries",
                    "RPA entry count exceeds the scan limit");
        }
    }

    public static void checkTextRecordCount(long count) throws LimitException {
        if (count < 0) {
            throw invalidRange("text record count is negative");
        }
        if (count > MAX_TEXT_RECORDS) {
            throw new LimitException("renpy_limit_entries",
                    "Ren'Py text record count exceeds the scan limit");
        }
    }

    public static void checkTextLength(long length) throws LimitException {
        if (length < 0) {
            throw invalidRange("text length is negative");
        }
        if (length > MAX_TEXT_LENGTH) {
            throw new LimitException("renpy_limit_inflated",
                    "Ren'Py text length exceeds the scan limit");
        }
    }

    public static void checkRange(long offset, long length, long containerLength)
            throws LimitException {
        if (offset < 0 || length < 0 || containerLength < 0
                || offset > containerLength || length > containerLength - offset) {
            throw invalidRange("offset/length is outside the containing resource");
        }
    }

    public static void checkPath(String path) throws LimitException {
        if (path == null || path.isEmpty()) {
            throw invalidRange("Ren'Py archive path is empty");
        }
        String normalized = path.replace('\\', '/');
        if (normalized.startsWith("/")
                || (normalized.length() >= 2 && normalized.charAt(1) == ':')) {
            throw invalidRange("absolute Ren'Py archive path");
        }
        String[] parts = normalized.split("/");
        for (String part : parts) {
            if ("..".equals(part)) {
                throw invalidRange("Ren'Py archive path traversal");
            }
        }
    }

    public static void checkInterrupted() throws LimitException {
        if (Thread.currentThread().isInterrupted()) {
            throw new LimitException("renpy_limit_inflated", "Ren'Py parsing interrupted");
        }
    }

    private static LimitException invalidRange(String message) {
        return new LimitException("renpy_invalid_range", message);
    }
}
