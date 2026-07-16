# Installed App Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a searchable installed-app source alongside the existing APK file picker, then route both sources through the same scan and translation pipeline.

**Architecture:** Extend the existing `FileManagerPlugin` smali delegation so two new plugin methods call a focused Java helper in `classes7.dex`. The helper queries only launcher-visible apps and copies a selected base APK into private cache. The WebView patch exposes one shared `loadSelectedApk(selection)` function used by both file and installed-app sources.

**Tech Stack:** Android PackageManager, Capacitor plugin bridge, Java 8/D8, smali/apktool, injected JavaScript/CSS, Python `unittest`, Node behavior tests, ADB, zipalign, APK Signature Scheme v2/v3.

---

## File Map

- Create `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledAppSource.java`: launcher-app discovery, validation, and private-cache APK copy.
- Create Android package-manager stubs under `apk-work/native-fast-scan/stubs/android/content/pm/` plus `Intent.java`: compile-only signatures for the helper.
- Modify `apk-work/native-fast-scan/stubs/android/net/Uri.java`, `android/content/Context.java`, and `com/getcapacitor/PluginCall.java`: add the compile-only methods used by selection.
- Modify `apk-work/native-fast-scan/build_fast_scanner.py`: compile the new helper and inject two `FileManagerPlugin` delegating methods.
- Modify `apk-work/ui-redesign/patch_workshop_ui.py`: shared selection loader, source chooser, installed-app search/list, split warning, error states.
- Modify `apk-work/ui-redesign/test_fast_scanner.py`: native source/build contract tests.
- Modify `apk-work/ui-redesign/test_workshop_patch.py`: executable WebView selection behavior tests.
- Modify `apk-work/ui-redesign/test_built_apk.py`: signed artifact contract.
- Generated only: `apk-work/slg-workshop-ui-signed.apk` and QA screenshots; never commit them.

### Task 1: Native installed-app bridge

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledAppSource.java`
- Create: `apk-work/native-fast-scan/stubs/android/content/Intent.java`
- Create: `apk-work/native-fast-scan/stubs/android/content/pm/ApplicationInfo.java`
- Create: `apk-work/native-fast-scan/stubs/android/content/pm/PackageManager.java`
- Create: `apk-work/native-fast-scan/stubs/android/content/pm/ResolveInfo.java`
- Create: `apk-work/native-fast-scan/stubs/android/content/pm/ActivityInfo.java`
- Modify: `apk-work/native-fast-scan/stubs/android/content/Context.java`
- Modify: `apk-work/native-fast-scan/stubs/android/net/Uri.java`
- Modify: `apk-work/native-fast-scan/stubs/com/getcapacitor/PluginCall.java`
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

- [ ] **Step 1: Add a failing native contract test**

Add `test_installed_app_source_is_private_launcher_only` asserting these production tokens:

```python
source = (FAST_SCAN / "src/com/slgtranslator/app/InstalledAppSource.java").read_text("utf-8")
builder = BUILDER.read_text("utf-8")
for token in (
    "Intent.ACTION_MAIN", "Intent.CATEGORY_LAUNCHER",
    "queryIntentActivities", "context.getPackageName()",
    "applicationInfo.sourceDir", "applicationInfo.splitSourceDirs",
    'new File(context.getCacheDir(), "installed-apks")',
    'value.put("source", "installed")',
    'value.put("splitApk", splitCount > 0)',
):
    self.assertIn(token, source)
self.assertNotIn("QUERY_ALL_PACKAGES", source)
self.assertIn("listInstalledApps", builder)
self.assertIn("selectInstalledApp", builder)
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m unittest apk-work/ui-redesign/test_fast_scanner.py -v
```

Expected: FAIL because `InstalledAppSource.java` and delegating methods do not exist.

- [ ] **Step 3: Implement the native helper**

Implement these public plugin entry points and keep all path handling private:

```java
public static void listInstalledApps(Context context, PluginCall call) {
    new Thread(() -> {
        try {
            PackageManager pm = context.getPackageManager();
            Intent launcher = new Intent(Intent.ACTION_MAIN);
            launcher.addCategory(Intent.CATEGORY_LAUNCHER);
            List<ResolveInfo> resolved = pm.queryIntentActivities(launcher, 0);
            Map<String, AppRow> unique = new LinkedHashMap<>();
            for (ResolveInfo item : resolved) {
                if (item.activityInfo == null || item.activityInfo.applicationInfo == null) continue;
                String packageName = item.activityInfo.applicationInfo.packageName;
                if (packageName == null || packageName.equals(context.getPackageName())) continue;
                String label = String.valueOf(item.loadLabel(pm)).trim();
                unique.put(packageName, new AppRow(label.isEmpty() ? packageName : label, packageName));
            }
            List<AppRow> rows = new ArrayList<>(unique.values());
            Collections.sort(rows, (a, b) -> a.label.compareToIgnoreCase(b.label));
            JSArray apps = new JSArray();
            for (AppRow row : rows) apps.put(row.toJson());
            JSObject result = new JSObject();
            result.put("apps", apps);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("Unable to list installed apps: " + safeMessage(error));
        }
    }, "slg-installed-app-list").start();
}

public static void selectInstalledApp(Context context, PluginCall call) {
    String requested = call.getString("packageName");
    if (requested == null || requested.trim().isEmpty()) {
        call.reject("packageName required");
        return;
    }
    new Thread(() -> copyValidatedPackage(context, requested, call), "slg-installed-app-copy").start();
}
```

`copyValidatedPackage` must re-query launcher activities, reject packages outside that set, copy `sourceDir` through a 1 MiB buffer to `installed-apks/<sha256(package|lastModified|length)>.partial`, call `FileDescriptor.sync()`, then atomically rename to `.apk`. Return:

```java
JSObject value = new JSObject();
value.put("uri", Uri.fromFile(output).toString());
value.put("name", label + ".apk");
value.put("packageName", packageName);
value.put("source", "installed");
value.put("splitApk", splitCount > 0);
value.put("splitCount", splitCount);
```

Delete stale `.partial` files and the previous private cached installed APK after a successful replacement. Never log `sourceDir`.

- [ ] **Step 4: Add compile stubs and plugin delegation**

Add only the Java signatures used by the helper: `Intent(String)`, `addCategory`, `Context.getPackageManager/getPackageName`, `PackageManager.queryIntentActivities/getApplicationInfo`, `ResolveInfo.loadLabel`, `PluginCall.getString`, `Uri.fromFile/toString`, and the `ApplicationInfo` fields. Existing `Context.getCacheDir()` stays unchanged.

In `build_fast_scanner.py`, compile every helper source instead of only `FastApkScanner.java`:

```python
HELPER_SOURCES = sorted((HERE / "src").rglob("*.java"))
# javac ... *map(str, HELPER_SOURCES)
```

Append these methods to `FileManagerPlugin.smali` immediately before the class EOF:

```smali
.method public final listInstalledApps(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation
    .locals 1
    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstalledAppSource;->listInstalledApps(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method

.method public final selectInstalledApp(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation
    .locals 1
    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstalledAppSource;->selectInstalledApp(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method
```

Guard insertion with exact-count checks so rebuilding never duplicates methods.

- [ ] **Step 5: Run GREEN and build helper dex**

Run:

```powershell
python -m unittest apk-work/ui-redesign/test_fast_scanner.py -v
python apk-work/native-fast-scan/build_fast_scanner.py
```

Expected: tests pass; generated `classes6.dex` and `classes7.dex` contain `listInstalledApps`, `selectInstalledApp`, and `InstalledAppSource`.

- [ ] **Step 6: Commit native bridge**

```powershell
git add -- apk-work/native-fast-scan apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: add installed app source bridge"
```

### Task 2: Shared selection loader and source chooser

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

- [ ] **Step 1: Add failing shared-loader behavior tests**

Add a contract plus executable Node test that extracts the generated selection runtime and verifies:

```javascript
const fileSelection={uri:`content://picked/game.apk`,name:`game.apk`,source:`file`};
const appSelection={uri:`file:///private/app.apk`,name:`Game.apk`,packageName:`game.pkg`,source:`installed`,splitApk:false};
await loadSelectedApk(fileSelection);
await loadSelectedApk(appSelection);
check(scanUris.join(`,`)===`${fileSelection.uri},${appSelection.uri}`,`both sources share scanner`);
check(resetCount===2,`both sources reset prior task state`);
```

Add separate assertions for search by label/package name, self-app exclusion coming from native results, recoverable list error, and split metadata retained until scan completes.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
```

Expected: FAIL because `loadSelectedApk`, the source chooser, and installed-app list do not exist.

- [ ] **Step 3: Rewrite the original picker into one shared loader**

Patch the minified React selection block into this shape without changing scan semantics:

```javascript
const loadSelectedApk=async e=>{
  r(e.uri);a(e.name||e.uri.split(`/`).pop()||`Unknown.apk`);s([]);fe(null);w([]);d(!0);
  window.__slgSelectionMeta=e;
  O(e.source===`installed`?`正在读取已安装应用的 APK...`:`正在扫描 APK 中的文本文件...`,`info`);
  let t=await E.listApkEntries({uri:e.uri});
  if(e.splitApk&&t.entries.length===0)throw Error(`该应用使用拆分安装包，基础 APK 中没有可翻译文件。请改用“从文件选择 APK”。`);
  s(t.entries);
  // preserve the existing duration/package-name/file-count logging block exactly
  d(!1);
};
window.__slgLoadSelectedApk=loadSelectedApk;
const xe=async()=>{try{await loadSelectedApk(await E.pickApkFile())}catch(e){...}};
```

The catch path must set scanning false and keep the source chooser usable.

- [ ] **Step 4: Build the source chooser UI**

Add these runtime functions:

```javascript
function openSourceChooser(){/* dialog: installed app / APK file / cancel */}
async function openInstalledApps(){
  setInstalledAppsState("loading");
  try{
    const result=await window.Capacitor.Plugins.FileManager.listInstalledApps();
    installedApps=Array.isArray(result.apps)?result.apps:[];
    renderInstalledApps();
  }catch(error){renderInstalledAppsError(error)}
}
function filterInstalledApps(query){
  const value=query.trim().toLocaleLowerCase();
  return installedApps.filter(app=>!value||app.label.toLocaleLowerCase().includes(value)||app.packageName.toLocaleLowerCase().includes(value));
}
async function chooseInstalledApp(packageName){
  const selection=await window.Capacitor.Plugins.FileManager.selectInstalledApp({packageName});
  closeSourceChooser();
  if(selection.splitApk)showSplitWarning(selection.splitCount);
  await window.__slgLoadSelectedApk(selection);
}
```

Change the visible primary action label to `选择应用或 APK` and route it to `openSourceChooser`. The file entry still invokes the current React file button. Use a native `<dialog>` or fixed modal outside overflow containers, 52 px controls, keyboard focus, backdrop close, dark tokens, and reduced-motion behavior.

- [ ] **Step 5: Add split and empty/error UX**

- Split warning: `该应用使用拆分安装包（N 个拆分包），当前先扫描基础 APK，部分资源可能无法读取。`
- Empty list: `没有找到可选择的已安装应用。你仍可从文件选择 APK。`
- Copy failure: preserve the native error and offer `重新选择` plus `从文件选择 APK`.
- Zero entries for split: use the explicit split limitation error, never ordinary success/zero-text state.

- [ ] **Step 6: Run GREEN and full suite**

```powershell
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
git diff --check
```

Expected: shared-loader behavior tests and all existing 17 tests pass.

- [ ] **Step 7: Commit WebView flow**

```powershell
git add -- apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "feat: select installed Android apps"
```

### Task 3: Signed artifact contract and build

**Files:**
- Modify: `apk-work/ui-redesign/test_built_apk.py`
- Generated: `apk-work/slg-workshop-ui-signed.apk`

- [ ] **Step 1: Add failing artifact assertions**

Assert the signed APK contains:

```python
for token in (
    "listInstalledApps", "selectInstalledApp", "InstalledAppSource",
    "选择应用或 APK", "__slgLoadSelectedApk", "splitApk",
):
    self.assertTrue(token in js or token.encode() in dex6 or token.encode() in dex7)
```

Also inspect the manifest dump and assert `android.permission.QUERY_ALL_PACKAGES` is absent.

- [ ] **Step 2: Run RED against the old artifact**

```powershell
python -m unittest apk-work/ui-redesign/test_built_apk.py -v
```

Expected: FAIL because the old signed APK has no installed-app bridge.

- [ ] **Step 3: Rebuild and verify GREEN**

```powershell
python apk-work/ui-redesign/build_workshop_apk.py
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
& '.tools/android-15/zipalign.exe' -c 4 'apk-work/slg-workshop-ui-signed.apk'
& '.tools/android-15/apksigner.bat' verify --verbose 'apk-work/slg-workshop-ui-signed.apk'
```

Expected: full suite passes; zipalign succeeds; v2/v3 signatures verify.

- [ ] **Step 4: Commit artifact contract only**

```powershell
git add -- apk-work/ui-redesign/test_built_apk.py
git commit -m "test: verify installed app picker artifact"
```

Do not commit APKs, generated dex, screenshots, `.tools`, extracted trees, or user files.

### Task 4: Real-device acceptance and broad regression audit

**Files:**
- Generated only: `apk-work/ui-redesign/qa/installed-app-picker.png`
- Update locally: `.superpowers/sdd/installed-app-selection-report.md`

- [ ] **Step 1: Record non-sensitive pre-install state**

Record only cache JSON byte length, total entry count, saved provider/model, and package version. Do not print keys or record values. Expected cache count: at least 13,058.

- [ ] **Step 2: Install without clearing data**

```powershell
$adb='.tools/platform-tools/adb.exe'
& $adb install -r 'apk-work/slg-workshop-ui-signed.apk'
& $adb logcat -c
& $adb shell am force-stop com.slgtranslator.app
& $adb shell monkey -p com.slgtranslator.app 1
```

Expected: `Success`; no uninstall and no `pm clear`.

- [ ] **Step 3: Exercise both selection sources**

Verify on the phone:

1. `选择应用或 APK` opens two source options.
2. Installed-app list loads without `QUERY_ALL_PACKAGES`, excludes SLG Translator, and search works by app name and package.
3. Select a known launcher app; its label/package appear and APK scanning begins.
4. Return and choose an APK file; the existing picker and scan still work.
5. If a split app is available, confirm the warning; do not claim full split support.

- [ ] **Step 4: Broad bug audit**

Run the complete automated suite and inspect fresh logcat for:

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
git diff --check
$errors=& $adb logcat -d | Select-String -Pattern 'ReferenceError|Uncaught|FATAL EXCEPTION|SecurityException'
if ($errors) { $errors; exit 1 }
```

Also verify provider/model persistence, old cache count not decreasing, start-translation action, progress log visibility, network fatal not producing partial APK, and install action reaching the Android unknown-source/installer boundary.

- [ ] **Step 5: Capture final evidence**

Capture one readable installed-app list screenshot, record APK SHA-256, test count, zipalign result, v2/v3 result, install result, cache count before/after, and any known split limitation. Never include API keys, cached texts, or private APK paths.

## Completion Evidence

- Installed-app search/list works on the connected phone without `QUERY_ALL_PACKAGES`.
- Selecting a launcher app enters the same scanner as file selection.
- File APK selection remains functional.
- Split APKs produce an explicit warning and a specific zero-entry error.
- Full suite passes, zipalign succeeds, v2/v3 signatures verify, and `adb install -r` succeeds.
- Cache entry count does not drop below its pre-install value.
- Fresh logcat has no `ReferenceError`, `Uncaught`, `FATAL EXCEPTION`, or `SecurityException`.
- Final commit hashes and signed APK path are recorded.
