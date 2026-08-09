# Android 安装包删除与标题统一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 在安装包页面为每个应用生成的补丁 APK 增加独立删除操作，并把页面标题统一为“安装包”，同时保证删除范围不会触及原始 APK、已安装游戏或共享翻译缓存。

**Architecture:** 原生 `InstallSupport` 负责专用输出目录的严格路径校验和精确删除，`build_fast_scanner.py` 将该方法注入现有 `FileManager` bridge。前端 gallery 负责确认、单条目并发保护、状态播报和列表刷新；现有宽泛 `cleanupStorage` 保持独立，不参与此功能。

**Tech Stack:** Python 注入脚本、Java/Android File API、Capacitor WebView JavaScript、pytest、Node.js 合约测试、Android APK 构建/签名和 ADB 真机验证。

## Global Constraints

- 只读取和删除应用专用 `SLG-Translator-Output` 目录下的 `*-patched-signed.apk`。
- 删除接口只接受列表返回的绝对 `file` 路径，不使用 `resolvePatchFile` 的“最新文件”兜底。
- 不触发 `cleanupStorage`，不删除用户原始 APK、下载目录副本、已安装游戏或共享翻译缓存。
- 原生删除前必须做 canonical containment、普通文件、后缀和符号链接校验，并在删除前再次复核文件状态。
- UI 删除按钮必须有至少 48dp 触控目标、可读 `aria-label`、`title` 和 `aria-live`/`aria-busy` 状态。
- 所有新增行为先写失败测试，再写最小实现；每个任务完成后运行对应的窄范围测试。

## File Map

- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstallSupport.java` - 收紧补丁列表目录并实现精确删除。
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py` - 注入 `deletePatchedApk` bridge 方法。
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py` - gallery 删除按钮、确认、状态和“安装包”标题。
- Modify: `apk-work/ui-redesign/test_fast_scanner.py` - Java 路径安全、原生删除和 bridge 构建合约。
- Modify: `apk-work/ui-redesign/test_workshop_patch.py` - gallery UI/JS 行为合约。
- Modify: `docs/qa/renpy-release-checklist.md` - 记录最终构建与真机删除验收证据。

---

### Task 1: Write Native Deletion Safety Tests

**Files:**
- Modify: `apk-work/ui-redesign/test_fast_scanner.py`
- Test source under test: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstallSupport.java`

**Interfaces:**
- Consumes: `InstallSupport.deletePatchedApk(Context, PluginCall)` with `{path: absolutePath}`.
- Produces: a failing Java harness that proves exact deletion and rejects unsafe paths.

- [ ] **Step 1: Add a Java harness test before implementation**

Create a `InstallDeleteSafetyHarness` beside the existing save-failure harness. Its fake context must return a temporary app files directory, and its `PluginCall` must capture `resolve` and `reject`. Create these cases:

```java
File output = new File(filesDir, "SLG-Translator-Output");
File valid = new File(output, "game-patched-signed.apk");
File sibling = new File(filesDir, "user-patched-signed.apk");
File wrongSuffix = new File(output, "notes.apk");
File directory = new File(output, "folder-patched-signed.apk");
```

Assert that the valid file is deleted and resolves with `deleted=true`; assert that the sibling, wrong suffix, directory, relative path, `content://...`, missing path, and a symlink path are rejected and remain unchanged.

- [ ] **Step 2: Run only the new test and verify it fails**

Run:

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python -m pytest -q test_fast_scanner.py -k install_delete_safety
```

Expected: FAIL because `InstallSupport.deletePatchedApk` does not exist and the build bridge has no delete method.

### Task 2: Implement Strict Native Deletion

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstallSupport.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**
- Consumes: `PluginCall.getString("path")`.
- Produces: `deletePatchedApk(Context, PluginCall)` resolving `{deleted: true, path: absolutePath}` or rejecting with a Chinese error message.

- [ ] **Step 1: Restrict `outputDirectories` to dedicated output folders**

Return only these app-owned directories when they exist or can be created: `<externalFilesDir>/SLG-Translator-Output`, `<filesDir>/SLG-Translator-Output`, and `<cacheDir>/SLG-Translator-Output`. Remove parent/root directory entries so `listPatchedApks` cannot surface arbitrary APKs stored beside the app output.

- [ ] **Step 2: Add exact path validation helpers**

Parse only a non-empty absolute filesystem path. Reject URI schemes, relative paths, and inputs whose canonical path differs from the absolute path, which also rejects `..` traversal and symlink indirection. Canonicalize each dedicated output directory and require the target's canonical parent to equal one of those directories. Require a regular file with `-patched-signed.apk` suffix.

- [ ] **Step 3: Add `deletePatchedApk` without fallback resolution**

Validate the target once, re-check `isFile`, parent containment, suffix and symlink state immediately before `delete()`, then delete that exact file. Never call `resolvePatchFile`, never select a newest file, and reject a missing or already-deleted target.

- [ ] **Step 4: Run the native safety test**

Run the targeted pytest command from Task 1. Expected: PASS for the valid file and every rejection case.

### Task 3: Wire the FileManager Bridge

**Files:**
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**
- Consumes: `InstallSupport.deletePatchedApk(Context, PluginCall)`.
- Produces: smali method `.method public final deletePatchedApk(Lcom/getcapacitor/PluginCall;)V` exposed by `FileManagerPlugin`.

- [ ] **Step 1: Add a failing bridge contract assertion**

Extend the existing fast-scanner bridge contract to require the exact signature, delegate string, `PluginMethod` annotation, context lookup and call to `InstallSupport.deletePatchedApk`. Also require that the generated FileManager class contains the signature exactly once.

- [ ] **Step 2: Add signature, delegate and method constants**

Follow the existing `SAVE_APK_*` and `LIST_PATCHES_*` pattern:

```python
DELETE_PATCHES_SIGNATURE = ".method public final deletePatchedApk(Lcom/getcapacitor/PluginCall;)V"
DELETE_PATCHES_DELEGATE = "Lcom/slgtranslator/app/InstallSupport;->deletePatchedApk"
```

Add the method body that obtains `FileManagerPlugin.getContext()` and invokes the static Java method. Insert it through the existing idempotent method injection path.

- [ ] **Step 3: Run bridge tests and build the native dex**

Run the bridge-focused tests, then run the existing native build command used by `build_fast_scanner.py`. Expected: the injected smali compiles and no duplicate method is produced.

### Task 4: Implement Gallery Delete UX

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: `window.Capacitor.Plugins.FileManager.deletePatchedApk({path})`.
- Produces: `deletePatch(patch)`, a per-row icon button, and a gallery title/label of “安装包”.

- [ ] **Step 1: Add failing JavaScript gallery contracts**

Extend the gallery test to require `deletePatch`, `deletePatchedApk`, confirmation text, `workshop-patch-delete`, `aria-label`, `aria-live`, `aria-busy`, `galleryDeleting`, the new title “安装包”, and absence of visible “我的补丁”. Add a Node contract with a fake FileManager plugin that proves cancel does not call native code, duplicate clicks share one request, success reloads the list, failure keeps the item, and a refresh failure preserves the prior list.

- [ ] **Step 2: Add gallery state and deletion flow**

Track deleting paths and a refresh epoch. `deletePatch` must check the plugin and path, call `window.confirm` with the patch name plus the explicit non-uninstall/non-original-APK warning, add the path to the in-flight set, call the exact native path, and finally remove the path from the set. On failure, keep the old list and render a retryable error.

- [ ] **Step 3: Render the per-package delete button and accessible status**

Add a 48dp trash icon button with `type=button`, `aria-label="删除安装包"`, `title="删除安装包"`, disabled state while that path is deleting, and an `aria-live` status region. Keep the existing save action. After a successful refresh, focus the next row or the gallery heading.

- [ ] **Step 4: Rename the gallery title and related labels**

Change the gallery `aria-label`, heading, and empty-state wording from “我的补丁” to “安装包”. Keep the bottom navigation label already set to “安装包”.

- [ ] **Step 5: Run the gallery contract tests**

Run:

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python -m pytest -q test_workshop_patch.py -k gallery
```

Expected: all gallery tests pass, including the new delete behavior contract.

### Task 5: Build, Install and Verify

**Files:**
- Modify: `docs/qa/renpy-release-checklist.md`
- Generated artifacts: `apk-work\slg-workshop-ui-signed.apk` and QA evidence under `apk-work\qa\`

**Interfaces:**
- Consumes: passing native/UI tests and the injected bridge.
- Produces: a signed installable APK and file-level device evidence.

- [ ] **Step 1: Run focused regression tests and syntax checks**

Run the new native and gallery tests, `python -m compileall` for modified Python files, and the existing full UI/native test suites. Expected: zero failures/errors and no unexpected skips.

- [ ] **Step 2: Rebuild and sign the APK**

Run the repository build script, then verify zip alignment, v2/v3 signatures, version metadata and SHA-256. Inspect the generated dex/smali contract for `deletePatchedApk`.

- [ ] **Step 3: Install the candidate on the known Android device**

Use the existing ADB path and install over the current candidate without clearing app data. Confirm the app launches and the gallery title reads “安装包”.

- [ ] **Step 4: Execute file-level deletion acceptance**

Prepare at least two generated patch APKs and record each absolute path, SHA-256 and size. Verify cancel leaves the list and hashes unchanged; delete one item and verify only its file disappears, the other item remains, the original APK hash is unchanged, the installed game still launches, and a failed deletion can be retried. Capture the UI state and relevant logs.

- [ ] **Step 5: Update the QA checklist and perform final review**

Record the final APK hash, device id, test counts, bridge evidence, deletion evidence, and remaining release caveats in `docs/qa/renpy-release-checklist.md`. Run `git diff --check` and a final scoped review of modified files.
