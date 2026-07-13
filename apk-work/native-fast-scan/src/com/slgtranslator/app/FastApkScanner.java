package com.slgtranslator.app;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class FastApkScanner {
    static final long SCAN_TIMEOUT_MS = 60_000L;
    static final int MAX_CACHE_ENTRIES = 4;
    private static final int COPY_BUFFER_SIZE = 1024 * 1024;
    private static final Set<String> TEXT_EXTENSIONS = Collections.unmodifiableSet(
        new HashSet<>(Arrays.asList(
            "json", "xml", "txt", "csv", "lua", "yaml", "yml",
            "properties", "cfg", "html", "htm", "md", "ini", "rpyc",
            "rpymc", "rpy", "strings"
        ))
    );
    private static final Map<String, ScanResult> CACHE = Collections.synchronizedMap(
        new LinkedHashMap<String, ScanResult>(MAX_CACHE_ENTRIES + 1, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, ScanResult> eldest) {
                return size() > MAX_CACHE_ENTRIES;
            }
        }
    );

    private FastApkScanner() {}

    public static void scanAsync(
        Context context,
        String uriText,
        Object plugin,
        PluginCall call
    ) {
        new Thread(() -> {
            try {
                call.resolve(scan(context, Uri.parse(uriText), plugin));
            } catch (Exception error) {
                String message = error.getMessage();
                call.reject("Failed to read APK: " + (message == null ? error.getClass().getSimpleName() : message));
            }
        }, "slg-apk-scan").start();
    }

    private static JSObject scan(Context context, Uri uri, Object plugin) throws Exception {
        long startedAt = SystemClock.elapsedRealtime();
        long deadline = startedAt + SCAN_TIMEOUT_MS;
        Metadata metadata = readMetadata(context.getContentResolver(), uri);
        String cacheKey = sha256(uri + "|" + metadata.displayName + "|" + metadata.size + "|" + metadata.lastModified);
        ScanResult cached;
        synchronized (CACHE) {
            cached = CACHE.get(cacheKey);
        }
        if (cached != null) {
            return toResponse(cached, SystemClock.elapsedRealtime() - startedAt, true);
        }

        ContentResolver resolver = context.getContentResolver();
        ScanResult result = null;
        try (ParcelFileDescriptor descriptor = resolver.openFileDescriptor(uri, "r")) {
            if (descriptor != null) {
                result = scanSeekableDescriptor(descriptor, plugin, deadline);
            }
        } catch (Exception ignored) {
            // Cloud-backed and virtual document providers may not expose a
            // seekable descriptor. Those providers use the bounded copy path.
        }
        if (result != null) {
            synchronized (CACHE) {
                CACHE.put(cacheKey, result);
            }
            return toResponse(result, SystemClock.elapsedRealtime() - startedAt, false);
        }

        File temp = File.createTempFile("slg-apk-scan-", ".apk", context.getCacheDir());
        try {
            copyCompressedApk(resolver, uri, temp, deadline);
            result = enumerateCentralDirectory(temp, plugin, deadline);
            synchronized (CACHE) {
                CACHE.put(cacheKey, result);
            }
            return toResponse(result, SystemClock.elapsedRealtime() - startedAt, false);
        } finally {
            if (temp.exists() && !temp.delete()) {
                temp.deleteOnExit();
            }
        }
    }

    private static ScanResult scanSeekableDescriptor(
        ParcelFileDescriptor descriptor,
        Object plugin,
        long deadline
    ) throws Exception {
        File descriptorPath = new File("/proc/self/fd/" + descriptor.getFd());
        return enumerateCentralDirectory(descriptorPath, plugin, deadline);
    }

    private static void copyCompressedApk(
        ContentResolver resolver,
        Uri uri,
        File temp,
        long deadline
    ) throws IOException {
        byte[] buffer = new byte[COPY_BUFFER_SIZE];
        try (
            InputStream input = resolver.openInputStream(uri);
            FileOutputStream output = new FileOutputStream(temp)
        ) {
            if (input == null) {
                throw new IOException("Cannot open selected APK");
            }
            int count;
            while ((count = input.read(buffer)) != -1) {
                ensureBeforeDeadline(deadline);
                output.write(buffer, 0, count);
            }
            output.getFD().sync();
        }
    }

    private static ScanResult enumerateCentralDirectory(
        File apk,
        Object plugin,
        long deadline
    ) throws Exception {
        Method likelyText = privateMethod(plugin, "isLikelyTextFile", String.class);
        Method detectType = privateMethod(plugin, "detectFileType", String.class, String.class);
        Method extractPackage = privateMethod(plugin, "extractPackageNameFromManifest", byte[].class);
        List<ApkEntry> entries = new ArrayList<>();
        String packageName = "";
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                ensureBeforeDeadline(deadline);
                ZipEntry entry = enumeration.nextElement();
                if (entry.isDirectory()) {
                    continue;
                }
                String name = entry.getName();
                String extension = extensionOf(name);
                if (!TEXT_EXTENSIONS.contains(extension)) {
                    continue;
                }
                if (!Boolean.TRUE.equals(likelyText.invoke(plugin, name))) {
                    continue;
                }
                String fileType = (String) detectType.invoke(plugin, name, extension);
                entries.add(new ApkEntry(
                    name,
                    entry.getSize(),
                    entry.getCompressedSize(),
                    fileType
                ));
            }

            ZipEntry manifest = zip.getEntry("AndroidManifest.xml");
            if (manifest != null) {
                byte[] manifestBytes = readEntry(zip, manifest, deadline);
                Object extracted = extractPackage.invoke(plugin, manifestBytes);
                packageName = extracted instanceof String ? (String) extracted : "";
            }
        }
        return new ScanResult(entries, packageName);
    }

    private static byte[] readEntry(ZipFile zip, ZipEntry entry, long deadline) throws IOException {
        try (
            InputStream input = zip.getInputStream(entry);
            ByteArrayOutputStream output = new ByteArrayOutputStream()
        ) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                ensureBeforeDeadline(deadline);
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private static Method privateMethod(Object target, String name, Class<?>... parameters) throws Exception {
        Method method = target.getClass().getDeclaredMethod(name, parameters);
        method.setAccessible(true);
        return method;
    }

    private static JSObject toResponse(ScanResult result, long durationMs, boolean cacheHit) throws Exception {
        JSArray entries = new JSArray();
        for (ApkEntry entry : result.entries) {
            JSObject value = new JSObject();
            value.put("name", entry.name);
            value.put("size", entry.size);
            value.put("compressedSize", entry.compressedSize);
            value.put("fileType", entry.fileType);
            entries.put(value);
        }
        JSObject response = new JSObject();
        response.put("entries", entries);
        response.put("totalFiles", entries.length());
        response.put("packageName", result.packageName);
        response.put("scanDurationMs", durationMs);
        response.put("cacheHit", cacheHit);
        return response;
    }

    private static Metadata readMetadata(ContentResolver resolver, Uri uri) {
        String displayName = "";
        long size = -1L;
        long lastModified = -1L;
        try (Cursor cursor = resolver.query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex("_display_name");
                int sizeIndex = cursor.getColumnIndex("_size");
                int modifiedIndex = cursor.getColumnIndex("last_modified");
                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) {
                    displayName = cursor.getString(nameIndex);
                }
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                    size = cursor.getLong(sizeIndex);
                }
                if (modifiedIndex >= 0 && !cursor.isNull(modifiedIndex)) {
                    lastModified = cursor.getLong(modifiedIndex);
                }
            }
        } catch (Exception ignored) {
            // URI identity still provides a safe process-local cache key.
        }
        return new Metadata(displayName, size, lastModified);
    }

    private static String extensionOf(String name) {
        int slash = name.lastIndexOf('/');
        int dot = name.lastIndexOf('.');
        if (dot <= slash || dot == name.length() - 1) {
            return "";
        }
        return name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private static String sha256(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder(digest.length * 2);
        for (byte item : digest) {
            result.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        }
        return result.toString();
    }

    private static void ensureBeforeDeadline(long deadline) throws IOException {
        if (SystemClock.elapsedRealtime() > deadline) {
            throw new IOException("APK scan timed out after 60 seconds");
        }
    }

    private static final class Metadata {
        final String displayName;
        final long size;
        final long lastModified;

        Metadata(String displayName, long size, long lastModified) {
            this.displayName = displayName;
            this.size = size;
            this.lastModified = lastModified;
        }
    }

    private static final class ApkEntry {
        final String name;
        final long size;
        final long compressedSize;
        final String fileType;

        ApkEntry(String name, long size, long compressedSize, String fileType) {
            this.name = name;
            this.size = size;
            this.compressedSize = compressedSize;
            this.fileType = fileType;
        }
    }

    private static final class ScanResult {
        final List<ApkEntry> entries;
        final String packageName;

        ScanResult(List<ApkEntry> entries, String packageName) {
            this.entries = Collections.unmodifiableList(new ArrayList<>(entries));
            this.packageName = packageName == null ? "" : packageName;
        }
    }
}
