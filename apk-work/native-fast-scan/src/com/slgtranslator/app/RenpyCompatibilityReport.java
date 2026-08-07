package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Sanitized, read-only compatibility diagnostics for one Ren'Py source set.
 * The report contains metadata and stable issue codes only; it never carries
 * APK bytes, pickle payloads, API credentials, or full script text.
 */
public final class RenpyCompatibilityReport {
    public enum SupportLevel { SAFE, WARNING, EXTRACT_ONLY, UNSUPPORTED }
    public enum ActivationStrategy { SELECTABLE_LANGUAGE, ALWAYS_ON, NONE }

    public final SupportLevel supportLevel;
    public final ActivationStrategy activationStrategy;
    public final String templatePath;
    public final RpycCompatibility.Report rpyc;
    public final int rpaCount;
    public final int splitCount;
    public final List<String> languageBuckets;
    public final String menuType;
    public final RenpyFontSupport.FontReport font;
    public final int uniqueTextCount;
    public final int occurrenceCount;
    public final int collisionCount;
    public final List<Issue> issues;

    public RenpyCompatibilityReport(
            SupportLevel supportLevel,
            ActivationStrategy activationStrategy,
            String templatePath,
            RpycCompatibility.Report rpyc,
            int rpaCount,
            int splitCount,
            List<String> languageBuckets,
            String menuType,
            RenpyFontSupport.FontReport font,
            int uniqueTextCount,
            int occurrenceCount,
            int collisionCount,
            List<Issue> issues) {
        this.supportLevel = supportLevel == null ? SupportLevel.UNSUPPORTED : supportLevel;
        this.activationStrategy = activationStrategy == null ? ActivationStrategy.NONE : activationStrategy;
        this.templatePath = sanitizePath(templatePath);
        this.rpyc = rpyc;
        this.rpaCount = nonNegative(rpaCount);
        this.splitCount = nonNegative(splitCount);
        this.languageBuckets = sanitizeLanguages(languageBuckets);
        this.menuType = sanitizeToken(menuType, "unknown", 48);
        this.font = font;
        this.uniqueTextCount = nonNegative(uniqueTextCount);
        this.occurrenceCount = nonNegative(occurrenceCount);
        this.collisionCount = nonNegative(collisionCount);
        this.issues = sanitizeIssues(issues);
    }

    public static final class Issue {
        public final String code;
        public final String message;

        public Issue(String code, String message) {
            this.code = sanitizeToken(code, "unknown_issue", 80);
            this.message = sanitizeMessage(message);
        }
    }

    public boolean isBlocked() {
        return supportLevel == SupportLevel.UNSUPPORTED
                || supportLevel == SupportLevel.EXTRACT_ONLY;
    }

    /** JSON containing only fixed diagnostic fields and bounded metadata. */
    public String toSanitizedJson() {
        StringBuilder out = new StringBuilder(768);
        out.append('{');
        field(out, "supportLevel", supportLevel.name());
        field(out, "activationStrategy", activationStrategy.name());
        field(out, "templatePath", templatePath);
        field(out, "menuType", menuType);
        number(out, "rpaCount", rpaCount);
        number(out, "splitCount", splitCount);
        array(out, "languageBuckets", languageBuckets);
        number(out, "uniqueTextCount", uniqueTextCount);
        number(out, "occurrenceCount", occurrenceCount);
        number(out, "collisionCount", collisionCount);
        out.append("\"rpyc\":");
        appendRpyc(out, rpyc);
        out.append(',');
        out.append("\"font\":");
        appendFont(out, font);
        out.append(',');
        out.append("\"issues\":[");
        for (int i = 0; i < issues.size(); i++) {
            if (i > 0) out.append(',');
            Issue issue = issues.get(i);
            out.append('{');
            field(out, "code", issue.code);
            field(out, "message", issue.message);
            trimTrailingComma(out);
            out.append('}');
        }
        out.append(']');
        trimTrailingComma(out);
        out.append('}');
        return out.toString();
    }

    private static void appendRpyc(StringBuilder out, RpycCompatibility.Report report) {
        if (report == null) {
            out.append("null");
            return;
        }
        out.append('{');
        field(out, "container", report.container);
        number(out, "preferredSlot", report.preferredSlot);
        number(out, "pickleProtocol", report.pickleProtocol);
        bool(out, "usesBuiltins", report.usesBuiltins);
        bool(out, "usesPy2Builtins", report.usesPy2Builtins);
        field(out, "generationSupport", report.generationSupport == null
                ? "UNKNOWN_EXTRACT_ONLY" : report.generationSupport.name());
        field(out, "reason", report.reason);
        trimTrailingComma(out);
        out.append('}');
    }

    private static void appendFont(StringBuilder out, RenpyFontSupport.FontReport report) {
        if (report == null) {
            out.append("null");
            return;
        }
        out.append('{');
        number(out, "requiredCount", report.requiredCount);
        number(out, "coveredCount", report.coveredCount);
        number(out, "missingCount", report.missingCodePoints == null
                ? 0 : report.missingCodePoints.size());
        bool(out, "hasChineseStyleBucket", report.hasChineseStyleBucket);
        bool(out, "hasEastAsianLineBreakEvidence", report.hasEastAsianLineBreakEvidence);
        trimTrailingComma(out);
        out.append('}');
    }

    private static List<Issue> sanitizeIssues(List<Issue> source) {
        List<Issue> result = new ArrayList<>();
        if (source != null) {
            for (Issue issue : source) {
                if (issue != null && result.size() < 32) result.add(issue);
            }
        }
        return Collections.unmodifiableList(result);
    }

    private static List<String> sanitizeLanguages(List<String> source) {
        List<String> result = new ArrayList<>();
        if (source != null) {
            for (String value : source) {
                String item = sanitizeToken(value, "", 32);
                if (!item.isEmpty() && !result.contains(item) && result.size() < 64) {
                    result.add(item);
                }
            }
        }
        return Collections.unmodifiableList(result);
    }

    private static String sanitizePath(String value) {
        if (value == null || value.isEmpty()) return "";
        String normalized = value.replace('\\', '/');
        if (normalized.length() > 256 || normalized.contains("\n") || normalized.contains("\r")
                || normalized.contains("../") || normalized.startsWith("../")) return "";
        return normalized;
    }

    private static String sanitizeToken(String value, String fallback, int maxLength) {
        if (value == null || value.isEmpty()) return fallback;
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < value.length() && result.length() < maxLength; i++) {
            char c = value.charAt(i);
            if (c >= 0x20 && c != 0x7f && c != '"' && c != '\\') result.append(c);
        }
        return result.length() == 0 ? fallback : result.toString();
    }

    private static String sanitizeMessage(String value) {
        return sanitizeToken(value, "Compatibility diagnostic", 180);
    }

    private static int nonNegative(int value) { return Math.max(0, value); }

    private static void field(StringBuilder out, String key, String value) {
        out.append('"').append(escape(key)).append("\":\"").append(escape(value)).append("\",");
    }

    private static void number(StringBuilder out, String key, int value) {
        out.append('"').append(escape(key)).append("\":").append(value).append(',');
    }

    private static void bool(StringBuilder out, String key, boolean value) {
        out.append('"').append(escape(key)).append("\":").append(value).append(',');
    }

    private static void array(StringBuilder out, String key, List<String> values) {
        out.append('"').append(escape(key)).append("\":[");
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) out.append(',');
            out.append('"').append(escape(values.get(i))).append('"');
        }
        out.append("],");
    }

    private static void trimTrailingComma(StringBuilder out) {
        if (out.length() > 0 && out.charAt(out.length() - 1) == ',') out.setLength(out.length() - 1);
    }

    private static String escape(String value) {
        if (value == null) return "";
        StringBuilder result = new StringBuilder(value.length() + 8);
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c == '"') result.append("\\\"");
            else if (c == '\\') result.append("\\\\");
            else if (c == '\n') result.append("\\n");
            else if (c == '\r') result.append("\\r");
            else if (c == '\t') result.append("\\t");
            else result.append(c);
        }
        return result.toString();
    }
}
