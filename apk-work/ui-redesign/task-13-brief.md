# Task 13 brief — Ren'Py font coverage and CJK line-break diagnostics

## Scope

Revalidate the B11 requirements from the complete revalidation plan. Work offline in the shared checkout. Do not use the connected Android device for this task. Do not claim a real game corpus or device result.

## Required focused tests

Run these existing tests first:

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_font_report_detects_missing_translation_glyphs `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_style_font_rewrite_rebuilds_rpc2_and_supports_schinese `
 test_fast_scanner.FastApkScannerContractTest.test_font_preflight_state_resets_when_scan_selection_starts `
 test_fast_scanner.FastApkScannerContractTest.test_split_scan_uses_split_template_and_merges_all_font_preflights -v
```

Expected baseline: 4 PASS. Inspect the existing JVM harnesses rather than replacing them with static token checks.

## Required gap

Prove that the final translation font check derives its required code points from accepted translations, not only from the fixed baseline set. Include a character absent from the baseline but present in an accepted translation; when no candidate font covers it, it must appear in `missingCodePoints` and block the final gate. Keep baseline preflight and translation final-check required sets distinct.

## Expected scope

Modify only if the evidence demonstrates a real gap:

- `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyFontSupport.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- `apk-work/ui-redesign/test_fast_scanner.py`
- `docs/qa/renpy-batch-bc-evidence.md`
- `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

Preserve existing runtime behavior and fail-closed font gating. No production change is justified if the existing implementation already satisfies the requirement; add executable evidence instead.

## Regression and evidence

Run `py_compile`, the focused B11 tests, `python -m unittest test_fast_scanner.py -v`, `python -m unittest test_workshop_patch.py -v`, `python -m unittest discover -s . -p 'test_*.py' -v`, and `git diff --check`. Update B11-01..B11-06 with exact counts, commit references, and explicit controlled-fixture/no-device/no-real-corpus boundaries. Keep unavailable real-corpus rows `NOT-RUN`.

Commit message: `test: revalidate renpy font and line break gates`
