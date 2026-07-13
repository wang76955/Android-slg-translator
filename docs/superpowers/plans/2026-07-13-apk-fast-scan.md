# APK Fast Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace full streamed APK inspection with an asynchronous, cached `ZipFile` directory scan and expose bounded, understandable UI states.

**Architecture:** Add a Java `FastApkScanner` as `classes7.dex`, patch only `FileManagerPlugin.listApkEntries` in the current modified `classes6.dex` to delegate to it, and package both generated dex files through the existing APK builder. Keep the existing Capacitor result contract while adding package-name and timing metadata that the frontend can consume opportunistically.

**Tech Stack:** Java 17, Android SDK 35, D8, apktool/smali, Python 3 `unittest`, Capacitor bridge, generated JavaScript/CSS, adb.

## Global Constraints

- Preserve all current `classes6.dex` behavior outside `listApkEntries`.
- Do not retain full APK copies after a scan; cache metadata results only in memory.
- Enforce a 60-second native scan deadline and always delete temporary files.
- Keep the existing `{entries, totalFiles}` response fields backward compatible.
- Do not regress API-key, translation, patch generation, installation, signing, or workshop UI flows.

---

### Task 1: Fast scanner contract tests

**Files:**
- Create: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `apk-work/ui-redesign/test_built_apk.py`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: Java source and generated dex/APK artifacts.
- Produces: executable contracts for async scanning, central-directory enumeration, timeout, cleanup, package-name reuse, and error UI.

- [ ] **Step 1: Write the failing source contract test**

```python
def test_fast_scanner_uses_central_directory_and_bounded_async_copy(self):
    source = FAST_SCANNER.read_text("utf-8")
    for token in ("new Thread", "new ZipFile", "SCAN_TIMEOUT_MS = 60_000L", "temp.delete()", "MAX_CACHE_ENTRIES = 4"):
        self.assertIn(token, source)
    self.assertNotIn("ZipInputStream", source)
```

- [ ] **Step 2: Write failing build and frontend contracts**

```python
self.assertIn("classes7.dex", archive.namelist())
self.assertIn("t.packageName", js)
self.assertIn("选择文件失败:", js)
self.assertIn("workshop-scan-elapsed", js)
```

- [ ] **Step 3: Run tests and verify RED**

Run: `python -m unittest apk-work/ui-redesign/test_fast_scanner.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_built_apk.py -v`

Expected: FAIL because the Java scanner, dex artifacts, package-name fast path, and scan error UI do not exist.

### Task 2: Native scanner and reproducible dex patch

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Create: `apk-work/native-fast-scan/stubs/com/getcapacitor/JSArray.java`
- Create: `apk-work/native-fast-scan/stubs/com/getcapacitor/JSObject.java`
- Create: `apk-work/native-fast-scan/stubs/com/getcapacitor/PluginCall.java`
- Create: `apk-work/native-fast-scan/build_fast_scanner.py`
- Modify: `apk-work/ui-redesign/build_workshop_apk.py`

**Interfaces:**
- Consumes: `Context`, selected URI, current `FileManagerPlugin` instance, and `PluginCall`.
- Produces: `scanAsync(Context, String, Object, PluginCall)`, generated patched `classes6.dex`, and helper `classes7.dex`.

- [ ] **Step 1: Implement the minimal asynchronous scanner**

```java
public static void scanAsync(Context context, String uriText, Object plugin, PluginCall call) {
    new Thread(() -> {
        try { call.resolve(scan(context, Uri.parse(uriText), plugin)); }
        catch (Exception error) { call.reject("Failed to read APK: " + error.getMessage()); }
    }, "slg-apk-scan").start();
}
```

The private `scan` first opens a seekable `ParcelFileDescriptor` and passes `/proc/self/fd/<fd>` to `ZipFile`. Non-seekable providers fall back to a temporary compressed-byte copy with a deadline. Both paths enumerate `ZipFile.entries()`, invoke existing private filename/type helpers through cached reflection methods, extract the manifest package name, and populate the LRU; fallback temporary files are deleted in `finally`.

- [ ] **Step 2: Implement the reproducible dex generator**

`build_fast_scanner.py` must compile stubs separately, compile the helper against `android.jar`, run D8 to create the helper dex, overlay the current modified `classes6.dex` into a temporary APK, decode with apktool, replace the exact smali method body with an `invoke-static` to `FastApkScanner.scanAsync`, rebuild dex, and copy both outputs into `apk-work/native-fast-scan/generated/`.

- [ ] **Step 3: Package generated dex files**

Update `build_workshop_apk.py` so replacement files overwrite existing entries and `classes7.dex` is appended when absent from the base archive.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest apk-work/ui-redesign/test_fast_scanner.py -v`

Expected: PASS, including dexdump assertions that `listApkEntries` delegates to `FastApkScanner` and the helper references `ZipFile` but not `ZipInputStream`.

### Task 3: Frontend package reuse, elapsed status, and failure recovery

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: optional `packageName`, `scanDurationMs`, and `cacheHit` fields from `listApkEntries`.
- Produces: package-name fallback behavior, elapsed-time scan copy, and a recoverable `reason:"scan"` failed state.

- [ ] **Step 1: Confirm frontend tests fail for the new behavior**

Run: `python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v`

Expected: FAIL on `t.packageName`, `workshop-scan-elapsed`, and `reason:"scan"` assertions.

- [ ] **Step 2: Patch the original React scan flow**

Use the package name returned by the fast scanner and retain the existing three-second `getApkPackageName` race only when the new field is empty. Log whether the scan came from cache and its duration.

- [ ] **Step 3: Add bounded visible state**

Track scan start time, update `.workshop-scan-elapsed` once per second, stop the timer on ready/failed/idle, detect `选择文件失败:` in the hidden React log, and render “检查失败” with a “重新选择 APK” action.

- [ ] **Step 4: Run frontend tests and verify GREEN**

Run: `python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v`

Expected: PASS with all existing workshop contracts preserved.

### Task 4: Signed APK and device verification

**Files:**
- Modify only if a failing verification exposes a defect in the preceding task.

**Interfaces:**
- Consumes: generated assets and generated dex files.
- Produces: `apk-work/slg-workshop-ui-signed.apk` installed on the connected Android device.

- [ ] **Step 1: Build and verify the signed APK**

Run: `python apk-work/ui-redesign/build_workshop_apk.py`

Expected: zipalign and APK signature verification succeed; the signed APK contains patched `classes6.dex` and helper `classes7.dex`.

- [ ] **Step 2: Run the complete automated suite**

Run: `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v`

Expected: all tests PASS.

- [ ] **Step 3: Install and time device scans**

Run: `.tools/platform-tools/adb.exe install -r apk-work/slg-workshop-ui-signed.apk`

Select the small fixture, then the larger APK, then reselect the larger APK. Use Capacitor log timestamps to verify callback completion and a faster cache hit; inspect the WebView to confirm ready/error states and package-name propagation.

- [ ] **Step 4: Commit the verified implementation**

```bash
git add docs/superpowers/plans/2026-07-13-apk-fast-scan.md apk-work/native-fast-scan apk-work/ui-redesign
git commit -m "perf: speed up apk inspection"
```
