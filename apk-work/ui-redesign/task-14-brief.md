# Task 14 brief — unified Ren'Py preflight and UI gate

## Scope

Revalidate the B12 requirements from the complete revalidation plan. Work offline and do not operate the connected Android device. Preserve the existing fail-closed behavior and sanitized diagnostics. Do not claim real-game or device results from controlled fixtures.

## Required focused tests

Run the existing tests first:

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_compatibility_report_ui_order_fields_and_sanitized_export `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_extract_only_compatibility_gate_blocks_before_model `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_font_preflight_is_before_first_model_call_and_read_bridge_returns_gate -v
```

Expected baseline: 4 PASS. These must exercise Java harnesses/generated runtime behavior, not only token presence.

## Required gap

Add an unsupported snapshot using an invalid or missing source set. Assert all of the following together: `UNSUPPORTED`, activation strategy `NONE`, stable issue code, no model call, and extraction/build actions that reflect the documented boundary. Ensure `EXTRACT_ONLY` is also blocked before any model call and that the unified report is sanitized before export.

## Expected scope

Modify only if evidence demonstrates a real gap:

- `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- `apk-work/ui-redesign/patch_workshop_ui.py`
- `apk-work/ui-redesign/test_fast_scanner.py`
- `docs/qa/renpy-batch-bc-evidence.md`
- `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

If current production behavior already satisfies the requirements, add executable evidence only. Do not weaken validators, remove preflight ordering, or turn unsupported/extract-only into a model-capable state.

## Regression and evidence

Run `py_compile`, the focused B12 tests plus the new unsupported snapshot test, `python -m unittest test_fast_scanner.py -v`, `python -m unittest test_workshop_patch.py -v`, `python -m unittest discover -s . -p 'test_*.py' -v`, and `git diff --check`. Update B12-01..B12-05 with exact counts, commit references, and explicit controlled-fixture/no-device/no-real-corpus boundaries. Keep unavailable real-corpus rows `NOT-RUN`.

Commit message: `test: revalidate renpy preflight and ui gates`
