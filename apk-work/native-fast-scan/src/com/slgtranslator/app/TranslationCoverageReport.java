package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Coverage accounting for the exact-old Ren'Py corpus.
 *
 * The report deliberately accepts only validator-approved translations.  A
 * rejected cache entry is never allowed to become translated merely because
 * a value is present in the validated map.
 */
public final class TranslationCoverageReport {
    public final int uniqueSourceCount;
    public final int occurrenceCount;
    public final int translatedCount;
    public final int missingCount;
    public final int rejectedCount;
    public final int collisionCount;
    public final int uncertainCount;
    public final Map<String, FileCoverage> files;
    public final Map<String, String> excludedReasons;

    private final List<MissingItem> missingItems;

    private TranslationCoverageReport(
            int uniqueSourceCount,
            int occurrenceCount,
            int translatedCount,
            int missingCount,
            int rejectedCount,
            int collisionCount,
            int uncertainCount,
            Map<String, FileCoverage> files,
            Map<String, String> excludedReasons,
            List<MissingItem> missingItems) {
        this.uniqueSourceCount = uniqueSourceCount;
        this.occurrenceCount = occurrenceCount;
        this.translatedCount = translatedCount;
        this.missingCount = missingCount;
        this.rejectedCount = rejectedCount;
        this.collisionCount = collisionCount;
        this.uncertainCount = uncertainCount;
        this.files = Collections.unmodifiableMap(new LinkedHashMap<>(files));
        this.excludedReasons = Collections.unmodifiableMap(new LinkedHashMap<>(excludedReasons));
        this.missingItems = Collections.unmodifiableList(new ArrayList<>(missingItems));
    }

    /**
     * Builds a report from exact-old occurrences.  classificationReasons may
     * be keyed by sourcePath + "\\t" + exactOld, or by exactOld.  x-common is
     * included by default; only explicit developer/internal/expired/settings
     * classifications remove an occurrence from coverage.
     */
    public static TranslationCoverageReport build(
            List<RenpyTextRecord> records,
            Map<String, String> validatorApprovedTranslations,
            Set<String> rejectedTranslations,
            Map<String, List<String>> candidateTranslations,
            Set<String> uncertainTranslations,
            Map<String, String> classificationReasons) {
        Map<String, SourceGroup> groups = new LinkedHashMap<>();
        Map<String, FileState> fileStates = new LinkedHashMap<>();
        Map<String, String> excluded = new LinkedHashMap<>();
        List<RenpyTextRecord> safeRecords = records == null
                ? Collections.<RenpyTextRecord>emptyList() : records;
        for (RenpyTextRecord record : safeRecords) {
            if (record == null || record.text.trim().isEmpty()) {
                continue;
            }
            String reason = classificationReason(record, classificationReasons);
            if (isExplicitSkip(reason) && isXCommon(record.sourcePath)) {
                excluded.put(record.sourcePath + "\t" + record.text, reason);
                continue;
            }
            SourceGroup group = groups.get(record.text);
            if (group == null) {
                group = new SourceGroup(record.text);
                groups.put(record.text, group);
            }
            group.records.add(record);
            FileState file = fileStates.get(record.sourcePath);
            if (file == null) {
                file = new FileState(record.sourcePath);
                fileStates.put(record.sourcePath, file);
            }
            file.sources.add(record.text);
            file.occurrenceCount++;
        }

        int translated = 0;
        int missing = 0;
        int rejected = 0;
        int collisions = 0;
        int uncertain = 0;
        List<MissingItem> missingItems = new ArrayList<>();
        for (SourceGroup group : groups.values()) {
            String old = group.exactOld;
            boolean isRejected = rejectedTranslations != null && rejectedTranslations.contains(old);
            String approved = validatorApprovedTranslations == null
                    ? null : validatorApprovedTranslations.get(old);
            boolean isTranslated = !isRejected && approved != null && !approved.trim().isEmpty();
            boolean isCollision = hasDistinctCandidates(candidateTranslations == null
                    ? null : candidateTranslations.get(old));
            boolean isUncertain = (uncertainTranslations != null && uncertainTranslations.contains(old))
                    || containsUncertainOccurrence(group.records);
            if (isTranslated) {
                translated++;
            } else if (isRejected) {
                rejected++;
            } else if (isUncertain) {
                // Uncertain extraction is reported separately and is not
                // silently converted into a verified missing value.
            } else {
                missing++;
                missingItems.add(new MissingItem(old, firstSourcePath(group.records),
                        isUncertain ? "uncertain" : "missing", group.records.size()));
            }
            if (isCollision) {
                collisions++;
            }
            if (isUncertain) {
                uncertain++;
            }
            for (RenpyTextRecord record : group.records) {
                FileState file = fileStates.get(record.sourcePath);
                if (file == null || file.seenSources.contains(old)) {
                    continue;
                }
                file.seenSources.add(old);
                if (isTranslated) file.translatedCount++;
                if (!isTranslated && !isRejected && !isUncertain) file.missingCount++;
                if (isRejected) file.rejectedCount++;
                if (isCollision) file.collisionCount++;
                if (isUncertain) file.uncertainCount++;
            }
        }

        Map<String, FileCoverage> files = new LinkedHashMap<>();
        for (FileState state : fileStates.values()) {
            files.put(state.filePath, state.freeze());
        }
        Collections.sort(missingItems, new Comparator<MissingItem>() {
            @Override
            public int compare(MissingItem left, MissingItem right) {
                int count = Integer.compare(right.occurrenceCount, left.occurrenceCount);
                return count != 0 ? count : left.exactOld.compareTo(right.exactOld);
            }
        });
        return new TranslationCoverageReport(
                groups.size(), totalOccurrences(groups), translated, missing, rejected,
                collisions, uncertain, files, excluded, missingItems);
    }

    public boolean shouldBlockCompleteBuild() {
        return missingCount > 0 || rejectedCount > 0;
    }

    public boolean canGenerateIncompleteTestPatch() {
        return true;
    }

    /** Top 20 missing exact-old entries, ordered by repeated occurrences. */
    public List<MissingItem> topMissing() {
        return Collections.unmodifiableList(new ArrayList<>(missingItems.subList(
                0, Math.min(20, missingItems.size()))));
    }

    /** Top 20 source files by missing unique exact-old values. */
    public List<FileCoverage> topMissingFiles() {
        List<FileCoverage> result = new ArrayList<>(files.values());
        Collections.sort(result, new Comparator<FileCoverage>() {
            @Override
            public int compare(FileCoverage left, FileCoverage right) {
                int count = Integer.compare(right.missingCount, left.missingCount);
                return count != 0 ? count : left.filePath.compareTo(right.filePath);
            }
        });
        List<FileCoverage> nonEmpty = new ArrayList<>();
        for (FileCoverage file : result) {
            if (file.missingCount > 0) nonEmpty.add(file);
            if (nonEmpty.size() == 20) break;
        }
        return Collections.unmodifiableList(nonEmpty);
    }

    /** JSON contains source diagnostics only; translations and candidates are never exported. */
    public String toSanitizedJson() {
        StringBuilder json = new StringBuilder(1024);
        json.append('{');
        field(json, "uniqueSourceCount", uniqueSourceCount).append(',');
        field(json, "occurrenceCount", occurrenceCount).append(',');
        field(json, "translatedCount", translatedCount).append(',');
        field(json, "missingCount", missingCount).append(',');
        field(json, "rejectedCount", rejectedCount).append(',');
        field(json, "collisionCount", collisionCount).append(',');
        field(json, "uncertainCount", uncertainCount).append(',');
        field(json, "completeBuildBlocked", shouldBlockCompleteBuild()).append(',');
        json.append("\"files\":{");
        boolean first = true;
        for (FileCoverage file : files.values()) {
            if (!first) json.append(',');
            first = false;
            quote(json, file.filePath).append(':').append(file.toJson());
        }
        json.append("},\"topMissingFiles\":[");
        first = true;
        for (FileCoverage file : topMissingFiles()) {
            if (!first) json.append(',');
            first = false;
            json.append(file.toJson());
        }
        json.append("],\"missing\":[");
        first = true;
        for (MissingItem item : topMissing()) {
            if (!first) json.append(',');
            first = false;
            json.append(item.toJson());
        }
        json.append("],\"excludedReasons\":{");
        first = true;
        for (Map.Entry<String, String> item : excludedReasons.entrySet()) {
            if (!first) json.append(',');
            first = false;
            quote(json, item.getKey()).append(':');
            quote(json, item.getValue());
        }
        return json.append("}}").toString();
    }

    /**
     * Computes the model request set.  Stable validated entries are reused;
     * new values, previous failures, and explicit retries are requested.
     */
    public static IncrementalDiff incrementalDiff(
            List<String> exactOldValues,
            Set<String> unchangedValidated,
            Set<String> priorFailed,
            Set<String> explicitRetranslation) {
        Set<String> request = new LinkedHashSet<>();
        Set<String> validated = unchangedValidated == null
                ? Collections.<String>emptySet() : unchangedValidated;
        for (String value : exactOldValues == null
                ? Collections.<String>emptyList() : exactOldValues) {
            if (value == null || value.trim().isEmpty()) continue;
            if (!validated.contains(value)) request.add(value);
        }
        if (priorFailed != null) request.addAll(priorFailed);
        if (explicitRetranslation != null) request.addAll(explicitRetranslation);
        return new IncrementalDiff(request, validated);
    }

    public static final class IncrementalDiff {
        public final Set<String> requestExactOld;
        public final Set<String> reusedExactOld;

        private IncrementalDiff(Set<String> requestExactOld, Set<String> reusedExactOld) {
            this.requestExactOld = Collections.unmodifiableSet(new LinkedHashSet<>(requestExactOld));
            this.reusedExactOld = Collections.unmodifiableSet(new LinkedHashSet<>(reusedExactOld));
        }
    }

    public static final class MissingItem {
        public final String exactOld;
        public final String sourcePath;
        public final String reason;
        public final int occurrenceCount;

        MissingItem(String exactOld, String sourcePath, String reason, int occurrenceCount) {
            this.exactOld = exactOld;
            this.sourcePath = sourcePath;
            this.reason = reason;
            this.occurrenceCount = occurrenceCount;
        }

        String toJson() {
            StringBuilder json = new StringBuilder();
            json.append('{');
            quote(json, "exactOld").append(':'); quote(json, exactOld).append(',');
            quote(json, "sourcePath").append(':'); quote(json, sourcePath).append(',');
            quote(json, "reason").append(':'); quote(json, reason).append(',');
            field(json, "occurrenceCount", occurrenceCount);
            return json.append('}').toString();
        }
    }

    public static final class FileCoverage {
        public final String filePath;
        public final int sourceCount;
        public final int occurrenceCount;
        public final int translatedCount;
        public final int missingCount;
        public final int rejectedCount;
        public final int collisionCount;
        public final int uncertainCount;

        FileCoverage(String filePath, int sourceCount, int occurrenceCount, int translatedCount,
                     int missingCount, int rejectedCount, int collisionCount, int uncertainCount) {
            this.filePath = filePath;
            this.sourceCount = sourceCount;
            this.occurrenceCount = occurrenceCount;
            this.translatedCount = translatedCount;
            this.missingCount = missingCount;
            this.rejectedCount = rejectedCount;
            this.collisionCount = collisionCount;
            this.uncertainCount = uncertainCount;
        }

        String toJson() {
            StringBuilder json = new StringBuilder();
            json.append('{');
            field(json, "sourceCount", sourceCount).append(',');
            field(json, "occurrenceCount", occurrenceCount).append(',');
            field(json, "translatedCount", translatedCount).append(',');
            field(json, "missingCount", missingCount).append(',');
            field(json, "rejectedCount", rejectedCount).append(',');
            field(json, "collisionCount", collisionCount).append(',');
            field(json, "uncertainCount", uncertainCount);
            return json.append('}').toString();
        }
    }

    private static final class SourceGroup {
        final String exactOld;
        final List<RenpyTextRecord> records = new ArrayList<>();

        SourceGroup(String exactOld) {
            this.exactOld = exactOld;
        }
    }

    private static final class FileState {
        final String filePath;
        final Set<String> sources = new LinkedHashSet<>();
        final Set<String> seenSources = new LinkedHashSet<>();
        int occurrenceCount;
        int translatedCount;
        int missingCount;
        int rejectedCount;
        int collisionCount;
        int uncertainCount;

        FileState(String filePath) {
            this.filePath = filePath == null ? "" : filePath;
        }

        FileCoverage freeze() {
            return new FileCoverage(filePath, sources.size(), occurrenceCount, translatedCount,
                    missingCount, rejectedCount, collisionCount, uncertainCount);
        }
    }

    private static int totalOccurrences(Map<String, SourceGroup> groups) {
        int result = 0;
        for (SourceGroup group : groups.values()) result += group.records.size();
        return result;
    }

    private static boolean containsUncertainOccurrence(List<RenpyTextRecord> records) {
        for (RenpyTextRecord record : records) {
            if (!record.coverageCertain) return true;
        }
        return false;
    }

    private static String firstSourcePath(List<RenpyTextRecord> records) {
        return records.isEmpty() ? "" : records.get(0).sourcePath;
    }

    private static boolean hasDistinctCandidates(List<String> candidates) {
        if (candidates == null) return false;
        Set<String> values = new LinkedHashSet<>();
        for (String candidate : candidates) {
            if (candidate != null && !candidate.trim().isEmpty()) values.add(candidate);
        }
        return values.size() > 1;
    }

    private static boolean isXCommon(String sourcePath) {
        String value = sourcePath == null ? "" : sourcePath.replace('\\', '/').toLowerCase();
        return value.contains("/x-common/") || value.startsWith("x-common/");
    }

    private static boolean isExplicitSkip(String reason) {
        if (reason == null) return false;
        String value = reason.toLowerCase();
        return value.contains("developer_console") || value.contains("internal_error")
                || value.contains("expired_text") || value.contains("settings_optional");
    }

    private static String classificationReason(RenpyTextRecord record, Map<String, String> reasons) {
        if (reasons == null || reasons.isEmpty()) return null;
        String scoped = reasons.get(record.sourcePath + "\t" + record.text);
        return scoped == null ? reasons.get(record.text) : scoped;
    }

    private static StringBuilder field(StringBuilder json, String name, int value) {
        return quote(json, name).append(':').append(value);
    }

    private static StringBuilder field(StringBuilder json, String name, boolean value) {
        return quote(json, name).append(':').append(value);
    }

    private static StringBuilder quote(StringBuilder json, String value) {
        json.append('"');
        String safe = value == null ? "" : value;
        for (int i = 0; i < safe.length(); i++) {
            char c = safe.charAt(i);
            switch (c) {
                case '"': json.append("\\\""); break;
                case '\\': json.append("\\\\"); break;
                case '\n': json.append("\\n"); break;
                case '\r': json.append("\\r"); break;
                case '\t': json.append("\\t"); break;
                default:
                    if (c < 0x20) json.append(' '); else json.append(c);
            }
        }
        return json.append('"');
    }
}
