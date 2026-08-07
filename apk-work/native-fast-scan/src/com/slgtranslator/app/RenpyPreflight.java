package com.slgtranslator.app;

import android.content.Context;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Single compatibility preflight entry point for a prepared Ren'Py source set. */
public final class RenpyPreflight {
    private RenpyPreflight() {}

    /**
     * All values are already scanner results. This carrier intentionally does
     * not contain APK bytes or script text, so inspect() cannot re-extract the
     * same script merely to render diagnostics.
     */
    public static final class SourceSet {
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

        public SourceSet(
                String templatePath,
                RpycCompatibility.Report rpyc,
                int rpaCount,
                int splitCount,
                List<String> languageBuckets,
                String menuType,
                RenpyFontSupport.FontReport font,
                int uniqueTextCount,
                int occurrenceCount,
                int collisionCount) {
            this.templatePath = templatePath;
            this.rpyc = rpyc;
            this.rpaCount = rpaCount;
            this.splitCount = splitCount;
            this.languageBuckets = languageBuckets == null
                    ? Collections.<String>emptyList()
                    : new ArrayList<>(languageBuckets);
            this.menuType = menuType;
            this.font = font;
            this.uniqueTextCount = uniqueTextCount;
            this.occurrenceCount = occurrenceCount;
            this.collisionCount = collisionCount;
        }
    }

    public static RenpyCompatibilityReport inspect(Context context, SourceSet source) {
        if (source == null || source.rpyc == null || source.templatePath == null
                || source.templatePath.isEmpty()) {
            return report(source, RenpyCompatibilityReport.SupportLevel.UNSUPPORTED,
                    RenpyCompatibilityReport.ActivationStrategy.NONE,
                    new RenpyCompatibilityReport.Issue("renpy_preflight_missing_source",
                            "Ren'Py source set is incomplete"));
        }

        List<RenpyCompatibilityReport.Issue> issues = new ArrayList<>();
        RpycCompatibility.GenerationSupport generation = source.rpyc.generationSupport;
        if (generation == RpycCompatibility.GenerationSupport.LEGACY_EXTRACT_ONLY) {
            issues.add(new RenpyCompatibilityReport.Issue(
                    "renpy_python2_writer_unavailable", "Legacy Python 2 output is extract-only"));
            return report(source, RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY,
                    RenpyCompatibilityReport.ActivationStrategy.NONE, issues);
        }
        if (generation != RpycCompatibility.GenerationSupport.MODERN_SUPPORTED) {
            issues.add(new RenpyCompatibilityReport.Issue(
                    "renpy_rpyc_generation_unknown", "RPYC generation support is not verified"));
            return report(source, RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY,
                    RenpyCompatibilityReport.ActivationStrategy.NONE, issues);
        }

        String menu = normalizeMenu(source.menuType);
        if ("custom".equals(menu)) {
            issues.add(new RenpyCompatibilityReport.Issue(
                    "renpy_menu_strategy_unknown", "Custom language menu requires manual activation review"));
            return report(source, RenpyCompatibilityReport.SupportLevel.WARNING,
                    RenpyCompatibilityReport.ActivationStrategy.ALWAYS_ON, issues);
        }
        if ("none".equals(menu) || "unknown".equals(menu)) {
            issues.add(new RenpyCompatibilityReport.Issue(
                    "renpy_language_menu_missing", "No standard language menu was detected"));
            return report(source, RenpyCompatibilityReport.SupportLevel.WARNING,
                    RenpyCompatibilityReport.ActivationStrategy.ALWAYS_ON, issues);
        }
        return report(source, RenpyCompatibilityReport.SupportLevel.SAFE,
                RenpyCompatibilityReport.ActivationStrategy.SELECTABLE_LANGUAGE, issues);
    }

    private static RenpyCompatibilityReport report(
            SourceSet source,
            RenpyCompatibilityReport.SupportLevel support,
            RenpyCompatibilityReport.ActivationStrategy activation,
            RenpyCompatibilityReport.Issue... issues) {
        return report(source, support, activation, Arrays.asList(issues));
    }

    private static RenpyCompatibilityReport report(
            SourceSet source,
            RenpyCompatibilityReport.SupportLevel support,
            RenpyCompatibilityReport.ActivationStrategy activation,
            List<RenpyCompatibilityReport.Issue> issues) {
        return new RenpyCompatibilityReport(
                support,
                activation,
                source == null ? "" : source.templatePath,
                source == null ? null : source.rpyc,
                source == null ? 0 : source.rpaCount,
                source == null ? 0 : source.splitCount,
                source == null ? Collections.<String>emptyList() : source.languageBuckets,
                source == null ? "unknown" : source.menuType,
                source == null ? null : source.font,
                source == null ? 0 : source.uniqueTextCount,
                source == null ? 0 : source.occurrenceCount,
                source == null ? 0 : source.collisionCount,
                issues);
    }

    private static String normalizeMenu(String value) {
        if (value == null || value.trim().isEmpty()) return "unknown";
        String lower = value.trim().toLowerCase(java.util.Locale.ROOT);
        if ("renpy".equals(lower) || "standard".equals(lower)) return "standard";
        if ("none".equals(lower)) return "none";
        if ("custom".equals(lower)) return "custom";
        return "unknown";
    }
}
