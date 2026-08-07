package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Exact-old Ren'Py corpus with occurrence-preserving contextual grouping. */
public final class RenpyTranslationCorpus {
    private RenpyTranslationCorpus() {}

    public static Corpus build(List<RenpyTextRecord> records) {
        LinkedHashMap<String, List<RenpyTextRecord>> grouped = new LinkedHashMap<>();
        if (records != null) {
            for (RenpyTextRecord record : records) {
                if (record == null || record.text.length() == 0) continue;
                grouped.computeIfAbsent(record.text, ignored -> new ArrayList<>()).add(record);
            }
        }
        LinkedHashMap<String, Entry> entries = new LinkedHashMap<>();
        for (Map.Entry<String, List<RenpyTextRecord>> item : grouped.entrySet()) {
            entries.put(item.getKey(), new Entry(item.getKey(), item.getValue()));
        }
        return new Corpus(entries);
    }

    public static String contextPrompt(Entry entry) {
        if (entry == null) return "";
        StringBuilder prompt = new StringBuilder("exactOld=").append(entry.exactOld)
                .append(" contexts=").append(entry.contextCount()).append("\n");
        int limit = Math.min(3, entry.occurrences.size());
        for (int i = 0; i < limit; i++) {
            RenpyTextRecord r = entry.occurrences.get(i);
            prompt.append("- ").append(r.sourcePath).append(":").append(r.sourceLine)
                    .append(" kind=").append(r.kind).append(" speaker=").append(r.speaker)
                    .append(" identifier=").append(r.identifier).append("\n");
        }
        if (entry.contextCount() > 3) prompt.append("- up to 3 representative contexts (total ")
                .append(entry.contextCount()).append(")\n");
        return prompt.toString();
    }

    public static final class Entry {
        public final String exactOld;
        public final List<RenpyTextRecord> occurrences;
        public final boolean contextualCollision;
        private final int contextCount;

        private Entry(String exactOld, List<RenpyTextRecord> occurrences) {
            this.exactOld = exactOld;
            this.occurrences = Collections.unmodifiableList(new ArrayList<>(occurrences));
            Set<String> contexts = new LinkedHashSet<>();
            for (RenpyTextRecord r : occurrences) {
                contexts.add(r.speaker + "\u0000" + r.identifier + "\u0000" + r.kind
                        + "\u0000" + r.sourcePath);
            }
            contextCount = contexts.size();
            contextualCollision = contextCount > 1;
        }

        public int contextCount() { return contextCount; }
    }

    public static final class Corpus {
        private final Map<String, Entry> entries;
        private Corpus(Map<String, Entry> entries) {
            this.entries = Collections.unmodifiableMap(new LinkedHashMap<>(entries));
        }
        public Entry get(String exactOld) { return entries.get(exactOld); }
        public int size() { return entries.size(); }
        public Map<String, Entry> entries() { return entries; }
    }
}
