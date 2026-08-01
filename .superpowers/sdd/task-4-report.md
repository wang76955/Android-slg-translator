# Task 4 Report: signed artifact and real-device acceptance

## Status

Partially accepted on a real PEMM20 device. The final signed APK, preserved-data
install, visible/localStorage provider persistence, cache preservation,
install-action regressions, and native installer boundary passed. Three broader
plan checks remain evidence gaps: a real-device localhost fail-fast run, a
non-zero legacy-cache hit/new-v2-write run, and hidden React control persistence.
No key or cache record text was read or printed.

Final source/test commit: `d3b43b5` (followed by artifact-contract hardening).

## TDD record

### Signed-artifact contract

- RED against the old signed APK: `test_signed_apk_contains_workshop_assets`
  failed first on missing `slg-workshop-settings-v1`.
- The first rebuild revealed that the plan's literal
  `slg-translator-cache:v2|` assertion contradicted the approved Task 2
  implementation, which deliberately composes `_o + \`v2|\``. The temporary
  literal production change was reverted. The artifact test now pins the exact
  reviewed `cacheV2Key` implementation; it failed against the temporary literal
  artifact and passed after rebuilding the approved dynamic implementation.

### Install-action defect found during device QA

- Device RED: the visible completed-state button existed and was enabled, its
  click listener fired once, but the current React tree had no connected
  `安装补丁版` button. The underlying click count was zero, the translator remained
  the resumed activity, and logcat contained no installer/native action.
- Regression RED: `test_install_bridge_refreshes_stale_react_button` failed with
  `fresh install target` because the bridge dispatched to a detached captured
  node.
- GREEN: the bridge now resolves the current React install action at click time.
- A second regression failed before the completed shell tracked whether a current
  React install action existed. GREEN conditionally exposes the visible install
  action and includes install availability in the snapshot key.
- Initial post-fix device result for the no-text fixture: current React install action
  `false`, visible install action `false`; the inert button is no longer offered.
  A later native-boundary follow-up is recorded at the end of this report.

## Build and automated verification

- Build: `python apk-work/ui-redesign/build_workshop_apk.py` exited 0.
- Final suite: `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v`
  passed **16/16** tests in 0.515 seconds.
- Zip alignment: `.tools/android-15/zipalign.exe -c 4` exited 0.
- Signatures: v2 `true`, v3 `true`; v1, v3.1, and v4 `false`; one signer.
- Initial pre-review artifact: `apk-work/slg-workshop-ui-signed.apk`
- Size: 10,245,570 bytes.
- Initial pre-review SHA-256:
  `A4EFE7340FAC4A7BD1B543A5A452601EDD7451C04BA048A132A5A3C0B8DD9EFD`.

## Preserved-data installation

- Final command used `adb install -r apk-work/slg-workshop-ui-signed.apk` only.
- Result: `Success`.
- The app was force-stopped and relaunched after install. No uninstall or
  `pm clear` command was used.
- Package: `com.slgtranslator.app`, versionName `1.0.1`, versionCode `2`.

## Provider settings and persistence

- Provider values: `openai`, `deepseek`, `custom`.
- Provider control height: 52 CSS px (requirement: at least 48).
- Custom fields were hidden for DeepSeek.
- Saved provider/model: `deepseek` / `deepseek-v4-flash`.
- Before force-stop, visible, localStorage, and hidden React provider/model fields
  all matched. After force-stop/relaunch, the visible and stored fields still
  matched `deepseek` / `deepseek-v4-flash`.
- Final screenshot: `apk-work/ui-redesign/qa/provider-settings.png` (720x1600).

## Cache privacy, preservation, and fixture result

Only byte/count/prefix metadata was evaluated.

| Measurement | Before install | After final install |
| --- | ---: | ---: |
| JSON bytes | 6,332,569 | 6,332,569 |
| Total entries | 13,058 | 13,058 |
| v2-prefixed entries | 0 | 0 |
| Legacy translation entries | 13,044 | 13,044 |
| Legacy `deepseek-v4-flash` entries | 13,043 | 13,043 |

The safely selectable `slg-qa-fixture.apk` exposed one script file but logged
that no text required translation and completed with zero translated strings.
Therefore it did not provide a non-zero cache-hit log, the requested 146-entry
RPYC completion, or a newly saved v2 key. Old-cache preservation is proven by
the unchanged post-install totals and legacy prefix counts; lookup/write behavior
remains covered by executable source tests. Screenshot:
`apk-work/ui-redesign/qa/cache-recovery.png`.

## Bounded network-failure QA

Not executed. The script checked only whether the API-key field was empty. At
the final fixture gate it was non-empty, so the script aborted before changing
provider, endpoint, model, or key. No attempt was made to read, recover, print,
or overwrite the value. Consequently there is no honest real-device duration,
attempt count, or recursive-split log result. The generated network classifier,
one-retry bound, no-recursive-split behavior, and fatal propagation remain covered
by the passing executable Node/Python tests.

## Final diagnostics and concerns

- `git diff --check` exited 0 (line-ending warnings only).
- Fresh logcat search found no `ReferenceError` or `Uncaught` entry.
- Device storage displayed a low-space warning during an earlier full-patch state;
  the final small fixture avoided large processing.
- DocumentsUI initially reopened a nested QQ directory; selecting the explicit
  safe fixture succeeded after returning to Downloads. A genuine completed patch
  fixture was not available for installer-opening proof.
- Generated APKs, screenshots, `.tools`, extracted/generated trees, and unrelated
  pre-existing modified/untracked files are intentionally not staged.

## Review-fix pass (2026-07-13)

### Stale install action: RED then GREEN

- Review RED: the executable Node behavior test rendered a completed shell while
  a React install node existed, detached that node before the visible click, and
  failed because the captured fallback still received the dispatch. The static
  runtime contract also failed because it still contained
  `findButton("安装补丁版") || button`.
- GREEN: install clicks now resolve only the current
  `findButton("安装补丁版")`. When it returns null, the bridge clears
  `installButton`, invalidates `lastSnapshot`, calls `refresh()`, and returns
  before dispatch. The existing stale-to-fresh-node behavior remains covered.
- `test_built_apk.py` pins the null-target invalidation sequence in the signed
  artifact, so a source-only fix cannot pass acceptance.

### Rebuild and preserved-data device check

- Source contract suite: **12/12** passed.
- Rebuild exited 0; full rebuilt-artifact suite: **16/16** passed in 0.502 s.
- Zip alignment exited 0. APK Signature Scheme v2 and v3 both verified true.
- Rebuilt artifact size: 10,245,570 bytes; SHA-256:
  `60EDA10F24F6A9BC5E426C33D3D9FB7F818603DEE01336B1088519D0FDC7B4B8`.
- `adb install -r apk-work/slg-workshop-ui-signed.apk` returned `Success`.
  No uninstall or `pm clear` was used.
- Cache metadata was identical immediately before and after the review install:
  7,848,631 bytes, 13,058 total entries, 0 v2-prefixed entries, 13,044 legacy
  entries, and 13,043 keys containing the configured DeepSeek model identity.
  No cache record text or full key was emitted.
- After a cleared-logcat cold launch, the app was the resumed activity and the
  AndroidRuntime fatal-log query returned zero lines.

### Honest remaining acceptance gaps

- After force-stop/relaunch, visible settings and localStorage both remained
  `deepseek` / `deepseek-v4-flash`; the provider control was 52 CSS px, custom
  fields were hidden, and the API-key field was empty. However, the underlying
  React provider/model controls were absent (`null`; only the settings shell
  selects existed). Hidden-React persistence is therefore **not verified** in
  this cold-start state.
- This review pass initially did not invoke `FileManager.installApk`; the later
  native-boundary follow-up below supersedes that observation. No install
  confirmation was attempted.
- The API-key field was empty, but the tiny translatable-fixture localhost
  fail-fast exercise was not run before the review pass was closed. The bounded
  retry/no-recursive-split behavior remains automated-test evidence only.
- A non-zero cache-hit log remains a blocker; preserved legacy cache counts and
  executable cache lookup/write tests are the available evidence.

### Native installer boundary follow-up

- After commit `d3b43b5` was installed, the app's own
  `FileManager.installApk` entry point was invoked against an existing private
  signed patched-APK cache file. The promise was started from the live WebView;
  no APK contents, API key, or cache record text were read.
- Android immediately resumed
  `com.android.settings/.Settings$ManageAppExternalSourcesActivity`. UI
  automation confirmed the screen title `安装未知应用`, the source app
  `SLG 文本翻译 1.0.1`, and `允许来自此来源的应用` was currently off.
- This proves the native installation boundary is no longer a no-op. The
  permission was not enabled, no installation was confirmed, and the device was
  returned to `com.slgtranslator.app/.MainActivity`.
