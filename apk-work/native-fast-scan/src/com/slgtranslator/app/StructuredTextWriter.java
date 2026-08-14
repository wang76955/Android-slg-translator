package com.slgtranslator.app;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Owner-aware ZIP writer for structured assets. It only rewrites files the
 * adapter produced records for, re-selects the codec for each rewritten
 * file, re-parses the output and compares it by recordId; any key / shape /
 * type / translation mismatch returns {@code writer_output_invalid}.
 */
public final class StructuredTextWriter {

    public static final String CODE_WRITER_INVALID = "writer_output_invalid";
    public static final String CODE_UNSUPPORTED = "structured_extraction_unavailable";

    public static final class PatchArtifact {
        public final int rewrittenFiles;
        public final int verifiedFiles;
        public final boolean valid;
        public final String failureCode;
        public final String failureDetail;

        PatchArtifact(int rewrittenFiles, int verifiedFiles, boolean valid,
                      String failureCode, String failureDetail) {
            this.rewrittenFiles = rewrittenFiles;
            this.verifiedFiles = verifiedFiles;
            this.valid = valid;
            this.failureCode = failureCode;
            this.failureDetail = failureDetail;
        }

        static PatchArtifact ok(int rewrittenFiles) {
            return new PatchArtifact(rewrittenFiles, rewrittenFiles, true, "", "");
        }

        static PatchArtifact failed(int rewrittenFiles, String code, String detail) {
            return new PatchArtifact(rewrittenFiles, rewrittenFiles, false, code, detail);
        }
    }

    /** Builds the first-release adapter with all four format codecs. */
    public static StructuredTextAdapter defaultAdapter() {
        StructuredTextAdapter adapter = new StructuredTextAdapter();
        adapter.install(new JsonAssetCodec(adapter));
        adapter.install(new DelimitedAssetCodec(adapter, "csv", ','));
        adapter.install(new DelimitedAssetCodec(adapter, "tsv", '\t'));
        adapter.install(new PropertiesAssetCodec(adapter));
        adapter.install(new PlainTextAssetCodec(adapter));
        return adapter;
    }

    private StructuredTextWriter() {
    }

    /**
     * Rewrites the declared entries of {@code apk} into {@code pending}.
     * {@code translationsByRecordId} is keyed by the recordId the adapter
     * minted; only those records can be written. Every rewritten file is
     * re-parsed and compared before it is accepted into the pending store.
     */
    public static PatchArtifact write(File apk, List<StructuredTextRecord> records,
                                      Map<String, String> translationsByRecordId,
                                      PendingApkEntryStore pending) throws IOException {
        if (apk == null || !apk.isFile()) {
            throw new IOException("structured writer: source APK is unavailable");
        }
        if (pending == null) {
            throw new IOException("structured writer: pending store is required");
        }
        StructuredTextAdapter adapter = defaultAdapter();
        LinkedHashMap<String, List<StructuredTextRecord>> recordsByPath = new LinkedHashMap<>();
        for (StructuredTextRecord record : records) {
            if (record == null || record.sourcePath == null) {
                continue;
            }
            List<StructuredTextRecord> bucket = recordsByPath.get(record.sourcePath);
            if (bucket == null) {
                bucket = new ArrayList<>();
                recordsByPath.put(record.sourcePath, bucket);
            }
            bucket.add(record);
        }
        int rewrittenFiles = 0;
        try (ZipFile zip = new ZipFile(apk)) {
            for (Map.Entry<String, List<StructuredTextRecord>> entry
                    : recordsByPath.entrySet()) {
                String path = entry.getKey();
                ZipEntry zipEntry = zip.getEntry(path);
                if (zipEntry == null || zipEntry.isDirectory()) {
                    return PatchArtifact.failed(rewrittenFiles, CODE_UNSUPPORTED,
                            "structured entry not found: " + path);
                }
                byte[] original = readEntry(zip, zipEntry);
                StructuredTextAdapter.AssetCodec codec = adapter.codecFor(path, original);
                if (codec == null) {
                    return PatchArtifact.failed(rewrittenFiles, CODE_UNSUPPORTED,
                            "no codec accepts entry: " + path);
                }
                LinkedHashMap<String, String> byKeyPath = new LinkedHashMap<>();
                for (StructuredTextRecord record : entry.getValue()) {
                    String translated = translationsByRecordId.get(record.recordId);
                    if (translated != null) {
                        byKeyPath.put(record.keyPath, translated);
                    }
                }
                if (byKeyPath.isEmpty()) {
                    continue;
                }
                byte[] rewritten;
                try {
                    rewritten = codec.rewrite(original, byKeyPath);
                } catch (IOException error) {
                    return PatchArtifact.failed(rewrittenFiles, failureCodeOf(error),
                            safeMessage(error));
                }
                StructuredTextAdapter.AssetCodec.ValidationResult verification =
                        codec.verify(original, rewritten, entry.getValue(), byKeyPath);
                if (!verification.valid) {
                    return PatchArtifact.failed(rewrittenFiles, verification.code,
                            verification.detail);
                }
                pending.add(path, path, rewritten);
                rewrittenFiles++;
            }
        }
        return PatchArtifact.ok(rewrittenFiles);
    }

    private static String failureCodeOf(Throwable error) {
        String message = error.getMessage();
        if (message != null) {
            int end = message.indexOf(':');
            if (end < 0) {
                end = message.indexOf(' ');
            }
            String candidate = end > 0 ? message.substring(0, end) : message;
            if (candidate.startsWith("structured_")) {
                return candidate;
            }
        }
        return CODE_WRITER_INVALID;
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? error.toString() : message;
    }

    private static byte[] readEntry(ZipFile zip, ZipEntry entry) throws IOException {
        RenpyResourceLimits.checkCompressed(entry.getCompressedSize());
        RenpyResourceLimits.checkInflated(entry.getSize());
        try (java.io.InputStream input = zip.getInputStream(entry);
             java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            long total = 0;
            while ((read = input.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                total += read;
                RenpyResourceLimits.checkInflated(total);
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        }
    }
}
