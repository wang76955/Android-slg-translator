# APK Fast Scan Design

## Goal

Reduce APK inspection from an unbounded full-entry stream scan to a responsive, bounded directory scan while preserving the existing list result, package-name detection, and translation flow.

## Root cause

The installed `FileManagerPlugin.listApkEntries` opens the selected content URI with `ZipInputStream`. Calling `closeEntry()` advances through every entry body, so inspection reads and may decompress almost the entire APK before returning. The call also runs synchronously and has no internal deadline, leaving the UI on “正在检查文件” indefinitely when a provider or archive is slow.

## Architecture

The APK-level build will add a small `FastApkScanner` Java helper as `classes7.dex`. A reproducible smali patch will replace only `FileManagerPlugin.listApkEntries` in `classes6.dex`, delegating to the helper on a background thread. Existing native methods and previous dex fixes remain unchanged.

For the first inspection of an APK, the helper copies only the compressed APK bytes from the content URI to a temporary cache file, opens it with `ZipFile`, and enumerates the ZIP central directory without reading entry bodies. It applies the same filename filtering and file-type detection through the existing plugin’s private methods, extracts the package name from `AndroidManifest.xml`, resolves the existing `{entries, totalFiles}` contract, and adds optional timing metadata. Temporary APK bytes are deleted in `finally`.

An in-memory four-entry LRU cache is keyed by URI, display name, size, and last-modified metadata. Re-selecting the same APK during the same app session reuses the entry list and package name without another copy. The cache stores metadata only, never a persistent copy of the APK.

## Runtime behavior

- Scanning runs off the Android main thread, so the WebView remains responsive.
- Copying and scanning have a 60-second deadline. A timeout rejects the native call with a clear error instead of waiting forever.
- The scan result includes `packageName`; the frontend uses it directly and calls the legacy `getApkPackageName` method only as a compatibility fallback.
- The visible shell shows elapsed time during inspection and maps `选择文件失败:` logs to a dedicated “检查失败” state with a reselect action.
- Existing translation, patch generation, installation, API-key, and output-directory behavior remains unchanged.

## Build integration

`build_fast_scanner.py` will compile lightweight Capacitor stubs, compile the Java helper against Android 15, produce `classes7.dex` with D8, decode an APK overlay containing the current modified `classes6.dex`, replace the one smali method, and rebuild only the patched dex. `build_workshop_apk.py` will package both generated dex files before zipalign and signing.

## Verification

Automated tests will prove that:

- the helper uses `ZipFile`, a background thread, a bounded deadline, temporary-file cleanup, and a four-entry metadata cache;
- the patched `classes6.dex` delegates `listApkEntries` to `FastApkScanner`;
- the signed APK contains the helper dex and the frontend package-name fast path;
- existing workshop UI and APK signing tests still pass.

Device verification will compare a small fixture and the larger selected APK, confirming that the native callback returns, the ready state appears, the package name is retained, and a repeat scan is faster.
