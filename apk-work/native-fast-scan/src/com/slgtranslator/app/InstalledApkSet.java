package com.slgtranslator.app;

import android.net.Uri;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Immutable, ordered description of one installed APK package.
 *
 * The base APK is kept separate from split APKs deliberately: callers must
 * open each ZIP independently and must never treat the set as one byte stream.
 */
public final class InstalledApkSet {
    public final File baseApk;
    public final List<File> splitApks;
    public final String packageName;
    public final long versionCode;

    private final List<String> splitNames;

    public InstalledApkSet(File baseApk, List<File> splitApks,
                           String packageName, long versionCode) {
        this(baseApk, splitApks, packageName, versionCode, null);
    }

    public InstalledApkSet(File baseApk, List<File> splitApks,
                           String packageName, long versionCode,
                           List<String> splitNames) {
        if (baseApk == null || !baseApk.isFile()) {
            throw new IllegalArgumentException("base APK is missing or unreadable");
        }
        if (packageName == null || packageName.trim().isEmpty()) {
            throw new IllegalArgumentException("packageName is required");
        }
        if (versionCode < -1L) {
            throw new IllegalArgumentException("versionCode is invalid");
        }
        this.baseApk = new File(baseApk.getAbsolutePath());
        this.packageName = packageName.trim();
        this.versionCode = versionCode;

        List<File> copiedSplits = new ArrayList<>();
        if (splitApks != null) {
            for (File splitApk : splitApks) {
                if (splitApk == null || !splitApk.isFile()) {
                    throw new IllegalArgumentException("split APK is missing or unreadable");
                }
                if (this.baseApk.equals(splitApk)) {
                    throw new IllegalArgumentException("baseApk.equals(splitApk)");
                }
                File absolute = new File(splitApk.getAbsolutePath());
                if (copiedSplits.contains(absolute)) {
                    throw new IllegalArgumentException("duplicate split APK");
                }
                copiedSplits.add(absolute);
            }
        }
        this.splitApks = Collections.unmodifiableList(copiedSplits);

        if (!copiedSplits.isEmpty()
                && (splitNames == null || splitNames.size() != copiedSplits.size())) {
            throw new IllegalArgumentException("splitName metadata is unavailable");
        }
        List<String> names = new ArrayList<>();
        for (int index = 0; index < copiedSplits.size(); index++) {
            String name = safeSplitName(splitNames.get(index));
            if (names.contains(name)) {
                throw new IllegalArgumentException("duplicate splitName metadata");
            }
            names.add(name);
        }
        this.splitNames = Collections.unmodifiableList(names);
    }

    public List<String> splitNames() {
        return splitNames;
    }

    public String splitNameAt(int index) {
        if (index < 0 || index >= splitNames.size()) {
            throw new IndexOutOfBoundsException("split index " + index);
        }
        return splitNames.get(index);
    }

    public List<File> allApks() {
        List<File> result = new ArrayList<>();
        result.add(baseApk);
        result.addAll(splitApks);
        return Collections.unmodifiableList(result);
    }

    public static InstalledApkSet fromUris(String baseUri, List<String> splitUris,
                                           String packageName, long versionCode) {
        return fromUris(baseUri, splitUris, packageName, versionCode, null);
    }

    public static InstalledApkSet fromUris(String baseUri, List<String> splitUris,
                                           String packageName, long versionCode,
                                           List<String> splitNames) {
        File base = fileFrom(baseUri);
        List<File> splits = new ArrayList<>();
        if (splitUris != null) {
            for (String splitUri : splitUris) {
                File split = fileFrom(splitUri);
                if (split == null) {
                    throw new IllegalArgumentException("split URI is not a local file");
                }
                splits.add(split);
            }
        }
        return new InstalledApkSet(base, splits, packageName, versionCode, splitNames);
    }

    private static File fileFrom(String value) {
        if (value == null || value.trim().isEmpty()) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.startsWith("file://")) {
            try {
                return new File(Uri.parse(normalized).getPath());
            } catch (RuntimeException error) {
                return null;
            }
        }
        return new File(normalized);
    }

    private static String safeSplitName(String requested) {
        String value = requested == null ? "" : requested.trim();
        if (value.isEmpty()) throw new IllegalArgumentException("splitName metadata is unavailable");
        value = value.replace('\\', '/');
        int slash = value.lastIndexOf('/');
        if (slash >= 0) {
            value = value.substring(slash + 1);
        }
        if (value.endsWith(".apk")) {
            value = value.substring(0, value.length() - 4);
        }
        if (!value.matches("[A-Za-z0-9._-]+") || value.isEmpty()) {
            throw new IllegalArgumentException("splitName metadata is invalid");
        }
        return value + ".apk";
    }
}
