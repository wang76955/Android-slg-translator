# Task 16 brief — complete split APK lifecycle

## Scope

Revalidate the C14 requirements from the complete revalidation plan offline. Do not operate the connected Android device. Preserve base/split ownership, immutable source copies, manifest-derived split names, fail-closed package/version/signature validation, and one PackageInstaller session with base-before-split write order. Fixture PASS must not be reported as a real-device install PASS.

## Required focused tests

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_split_apk_set_is_immutable_and_rejects_duplicate_or_missing_parts `
 test_fast_scanner.FastApkScannerContractTest.test_installed_split_names_come_from_manifest_metadata_not_file_names `
 test_fast_scanner.FastApkScannerContractTest.test_split_apk_set_scans_assets_and_installs_in_one_session `
 test_fast_scanner.FastApkScannerContractTest.test_split_scan_uses_split_template_and_merges_all_font_preflights `
 test_fast_scanner.FastApkScannerContractTest.test_split_scanning_and_reading_fail_closed_instead_of_base_only_fallback `
 test_fast_scanner.FastApkScannerContractTest.test_split_ui_preserves_collection_metadata_through_scan_read_compile_and_install -v
```

Expected baseline: 6 PASS. The tests must exercise executable Java/Node behavior or an explicit source contract; token-only assertions are insufficient for new gaps.

## Required gaps and boundaries

Check package mismatch, version mismatch, duplicate split name, signature mismatch and write failure. Validation must precede session commit and errors must abandon the session. Verify write order is base.apk followed by declared split names. Verify a template/font asset owned by a split reports its source APK and is not silently patched only in base. If a real split target or device is unavailable, record that device row as NOT-RUN.

## Expected scope

Modify only if evidence demonstrates a real gap:

- `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledApkSet.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledAppSource.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/PackageInstallerSupport.java`
- `apk-work/ui-redesign/patch_workshop_ui.py`
- `apk-work/ui-redesign/test_fast_scanner.py`
- `docs/qa/renpy-batch-bc-evidence.md`
- `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

If current production behavior satisfies the requirements, add executable evidence only. Do not weaken signature/version checks, fall back to base-only scanning, or claim device installation from fixtures.

## Regression and evidence

Run `py_compile`, the focused C14 tests, `python -m unittest test_fast_scanner.py -v`, `python -m unittest test_workshop_patch.py -v`, `python -m unittest discover -s . -p 'test_*.py' -v`, and `python apk-work/native-fast-scan/build_fast_scanner.py`. Inspect helper DEX ownership for InstalledApkSet, InstalledAppSource, FastApkScanner and PackageInstallerSupport exactly once. Update C14-01..C14-06 and the real-device boundary with exact counts and missing-fixture conditions.

Commit message: `test: revalidate complete split apk lifecycle`
