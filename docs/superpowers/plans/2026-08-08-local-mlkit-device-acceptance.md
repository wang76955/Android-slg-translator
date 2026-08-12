# Local ML Kit Translation Device Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended when a task can be split cleanly) or `superpowers:executing-plans` to implement this plan task-by-task with review checkpoints.

**Goal:** Make the no-API-key local ML Kit route a real, end-to-end usable path for a `content://` APK selected from Android DocumentsUI, then rebuild and verify the application on the connected device with the real Ren'Py game `异世界天堂0.6`.

**Architecture:** Resolve a selected APK URI once into an app-owned, persistent local copy when the source is a virtual/document `content://` URI. Return that resolved URI from the native menu-injection bridge and propagate it into `window.__slgSelectionMeta` before scan/build/compile operations. Keep ordinary filesystem paths and `file://` URIs working without copying. Use the existing native ML Kit bridge and existing local-provider UI; the acceptance route is English → Simplified Chinese with the ML Kit model downloaded once, then usable without an API key.

**Tech Stack:** Java Android/Capacitor bridge, Python asset patch/build scripts, Python `unittest`, Android Debug Bridge, connected Android 13 device, Google ML Kit on-device translation.

## Global Constraints

- Work in the current checkout `D:\文件翻译`; do not create or switch to a worktree because this checkout contains the user’s protected staged documents and large real-device APK/test assets.
- Never use `git reset --hard`, `git checkout --`, `git clean`, broad recursive deletion, `git add .`, or `git add -A`.
- Preserve these four user-pre-staged files exactly and do not stage or commit them: `PRODUCT.md`, `docs/superpowers/plans/2026-07-13-apk-main-flow-redesign-v2.md`, `docs/superpowers/specs/2026-07-13-android-apk-ui-redesign-design.md`, and `docs/superpowers/specs/2026-07-13-apk-main-flow-redesign-v2-design.md`.
- Preserve unrelated untracked build artifacts, screenshots, extracted APKs, device fixtures, and reference directories.
- Any child agent used for this plan must use at most model `gpt-5.6-luna`.
- Do not clear `com.slgtranslator.app` data on the device. Preserve the installed real game `com.yishijietiantang.com` and its existing Downloads APK.
- Do not claim the task is complete until targeted tests, the full automated suite, APK rebuild/signature checks, device model status, and a real translation smoke path have evidence.
- If the ML Kit model cannot be downloaded or the device cannot complete the real route, record the exact external blocker and stop short of claiming release acceptance.

---

## Task 1: Capture the current failure and define the URI contract

**Files:** `apk-work/native-fast-scan/src/com/slgtranslator/app/LanguageMenuSupport.java`, `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`, `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`, `apk-work/ui-redesign/scan_flow_constants.py`, `apk-work/ui-redesign/patch_workshop_ui.py`, `apk-work/ui-redesign/test_fast_scanner.py`, `apk-work/ui-redesign/test_bugfix_install_language.py`.

- Read the existing bridge and UI data flow and document the exact invariant: after menu injection succeeds, the URI used by `readRenpyTexts`, `compileTranslationsIntoApk`, and `buildPatchedApk` must identify the same writable APK copy that contains the injected menu.
- Confirm the existing failure with the current targeted regression command before changing implementation:

  `Push-Location apk-work/ui-redesign; python -m unittest test_fast_scanner.FastApkScannerContractTest.test_language_menu_support_rewrites_expendable_slot -v; Pop-Location`

- Add a short evidence note to the implementation ledger, not to the protected release docs, showing the current `content://` failure and the intended resolved-URI contract.

## Task 2: Add a failing content-URI regression test first

**Files:** `apk-work/native-fast-scan/src/com/slgtranslator/app/LanguageMenuSupport.java`, `apk-work/native-fast-scan/stubs/android/content/Context.java`, `apk-work/native-fast-scan/stubs/android/content/ContentResolver.java`, `apk-work/native-fast-scan/stubs/android/net/Uri.java`, `apk-work/ui-redesign/test_fast_scanner.py`.

- Extend the existing Java harness/stubs only as needed to provide a deterministic `Context.getContentResolver().openInputStream(Uri)` backed by a small fixture APK or byte stream.
- Add a behavior test that invokes `injectTranslatorMenu` with a `content://` URI and asserts all of the following: the call resolves rather than rejects; the result reports a usable resolved local URI/path; the resolved file exists; and the rewritten copy contains the translator language menu.
- Add a second idempotence assertion for the resolved local copy: invoking the bridge again reports ready/already-injected and does not corrupt the archive.
- Run the narrow test and record the expected red failure before implementation. Do not weaken the test to a source-string-only assertion.

## Task 3: Implement one persistent content-URI resolution path and propagate it

**Files:** `apk-work/native-fast-scan/src/com/slgtranslator/app/LanguageMenuSupport.java`, `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`, `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java` only if required by the discovered data flow, `apk-work/ui-redesign/scan_flow_constants.py`, `apk-work/ui-redesign/patch_workshop_ui.py`.

- Implement the smallest shared behavior that copies a `content://` source through `Context.getContentResolver().openInputStream` into an app-owned persistent directory, writes atomically, validates that the result is a regular file, and reuses the copy for the rest of the selected session.
- Keep direct paths and `file://` URIs as direct files. Reject unsupported/empty/non-readable sources with the existing Chinese error style and without leaving a partial copy.
- Make `injectTranslatorMenu` rewrite the resolved writable copy and include the resolved local URI in its `JSObject` result. Preserve `changed`, `ready`, and idempotence semantics.
- Update the generated scan flow source and its Python patch source so a successful injection merges the returned URI into `window.__slgSelectionMeta` (including `baseUri` where applicable) before any later read, compile, build, cleanup, or install operation. The later build must not silently switch back to the original `content://` URI.
- Keep the existing installed-app refresh behavior intact; if that refresh obtains a new URI, resolve/inject that URI and propagate its result again.
- Run the focused Java/Python regression tests after the minimal implementation and verify the previously red test is green.

## Task 4: Lock the no-API-key ML Kit route with automated regression tests

**Files:** `apk-work/ui-redesign/test_bugfix_install_language.py`, `apk-work/ui-redesign/test_known_bugfixes.py`, `apk-work/ui-redesign/test_built_apk.py`, and the smallest relevant source/patch files.

- Add or strengthen tests proving the local provider is present, the ML Kit option is exposed, selecting it hides API-key requirements, and the start/translation path calls the native `localDownload`/`translateLocal` bridge rather than an OpenAI/DeepSeek network path.
- Assert the default/explicit local route uses `sourceLang: "en"`, `targetLang: "zh"`, and the ML Kit engine identifier, while retaining the Qwen route as an optional separate engine rather than making it a prerequisite for acceptance.
- Assert generated JS still contains the native bridge names `localStatus`, `localDownload`, `translateLocal`, and the local-provider API-key bypass after the URI-flow patch.
- Run the focused local-provider and patch-generation tests, then run `Push-Location apk-work/ui-redesign; python -m unittest discover -s . -p 'test_*.py' -v; Pop-Location` and record counts, failures, errors, and explicit skips.

## Task 5: Rebuild a verification APK and install without data loss

**Files/artifacts:** `apk-work/ui-redesign/build_workshop_apk.py`, generated asset outputs, `apk-work/slg-workshop-ui-signed.apk` or the script’s documented output, and a dated verification log/screenshot under `apk-work/`.

- Rebuild using the repository build script from `apk-work/ui-redesign` after all source tests pass.
- Verify the rebuilt APK has the expected package, version, native bridge strings, local-provider strings, and a valid signature/alignment using the existing local Android tooling.
- Record SHA-256 and size of the new artifact.
- Install on the connected device with replacement/downgrade allowed while preserving app data (`adb install -r -d -t <apk>`), then verify `versionCode`, `versionName`, data directory, and foreground launch. Do not uninstall or clear data.
- Capture the app home screen and local translation settings screen after installation.

## Task 6: Download and verify the ML Kit model on the device

**Device route:** `com.slgtranslator.app` → 我的 → 翻译服务 → 本机离线翻译 → 轻量翻译（ML Kit）.

- Confirm no API key is configured/required for the selected provider and capture the settings UI state.
- Start the English→Simplified Chinese ML Kit model download while the device is unlocked. Poll UI/log/storage in bounded intervals, keeping each wait below 60 seconds because the device auto-locks after 30 minutes.
- Verify the native status reports the model as downloaded/ready and that a translation call succeeds for a small deterministic set such as `Hello`, `New Game`, and `Quit` without network/API-key configuration.
- Repeat the same small translation after disabling network connectivity if the available device controls permit; otherwise record the strongest offline evidence available from ML Kit status/logs and the local bridge.
- Capture dated screenshots and `adb logcat` excerpts, redacting secrets if any appear.

## Task 7: Execute the real `异世界天堂0.6` end-to-end local translation path

**Device/game:** installed `com.yishijietiantang.com`, version `0.6`, real APK already present on the device.

- Select/scan the real game APK through DocumentsUI so the source is a real `content://` URI, and verify the scan completes without the old “补丁源 APK 不存在” menu-injection error.
- Verify the resolved local URI is used for subsequent menu injection, Ren'Py extraction, translation compilation, and patched APK build; use UI logs and native logcat evidence rather than assuming success.
- Run the local ML Kit route on the real game’s English text. Wait for the actual translation/build state and verify the full-coverage gate, font preflight, compiled `.rpyc` output, and generated patched APK state. Do not select “incomplete test patch” for release acceptance.
- Install the generated patched APK using the existing complete installation flow, launch the game, and verify the translated menu/dialogue boundary in the real game. Also verify the original game still launches if the install flow keeps a backup or can be restored.
- Verify save/backup or cleanup boundaries relevant to the release checklist without deleting the user’s original real APK or app data.
- Capture screenshots for: selected real APK, scan ready, local provider/model ready, translation progress/completed, generated APK/install result, and in-game translated menu/dialogue.

## Task 8: Re-run full verification and update acceptance evidence

**Files:** `docs/qa/renpy-batch-bc-evidence.md`, `docs/qa/renpy-compatibility-matrix.md`, `docs/qa/renpy-release-checklist.md`, plus a dated implementation/verification log under `docs/qa/` if needed.

- Run the focused regression suite, the full unittest suite, `git diff --check`, APK/package/signature checks, and final device package/activity/log checks.
- Update QA evidence with exact artifact SHA-256, device/build versions, ML Kit model status, local no-API-key evidence, real content-URI path result, screenshots, and any remaining known limitations.
- Change the prior T22-06 `content://` failure to PASS only when the real device path and automated regression both pass. Add a separate local ML Kit acceptance row with explicit PASS/FAIL/BLOCKED evidence.
- Never convert a model/network/device failure into PASS by inference. If any release criterion remains unmet, leave the release decision blocked and report the exact missing evidence.
- Stage and commit only the implementation/test/QA files created by this plan using explicit paths; keep the four protected staged files and all unrelated untracked files untouched.
