# Task 9 report: Ren'Py text lint

## Scope

Implemented the Task 9 contract only in the six paths named by the brief plus
this report. Existing cache namespace behavior and the four user-staged
documents were left untouched.

## Implementation

- Added `RenpyTextValidator.ValidationResult` with deterministic checks for
  empty translations, sentinel count/index/order, paired Ren'Py markup, nested
  tag order, `[expression]` interpolation, printf tokens, and unrestored
  sentinels.
- Hardened `LocalLlmEngine.restorePlaceholders` to compare the complete
  sentinel sequence before replacement. Model acceptance now validates the
  restored result before placing it in the translation map and returns a
  sanitized rejected-record list containing `old`, `new`, `codes`, and `source`.
- Added both merge-time and artifact-time compiler gates. Invalid pairs are
  rejected before RPYC generation or APK rewrite, with the source path and
  stable validation codes in the failure message. The follow-up review also
  required keeping the existing translation-cache namespace and using a
  single-pass sentinel restoration so replacement text cannot be interpreted
  as another replacement expression.
- Documented the lint contract and rejection record requirements in
  `docs/translation-quality-rules.md`.

## Test-first evidence

The focused test was run before the validator existed and failed at Java
compilation because `RenpyTextValidator` was missing. After implementation,
the required focused test passed:

```text
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_local_llm_placeholder_guard_preserves_markup_and_format -v
Ran 1 test ...
OK
```

The focused guard and compiler-gate tests passed after the follow-up fix. The
full scanner and quality suites must remain green before the fix commit is
considered complete.
