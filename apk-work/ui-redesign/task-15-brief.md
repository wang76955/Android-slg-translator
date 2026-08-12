# Task 15 brief — restricted protocol-2 writer

## Scope

Revalidate the C13 requirements from the complete revalidation plan. Work offline and do not operate the connected Android device. Preserve the modern writer's byte stability, keep protocol-2 generation limited to the verified capability matrix, and keep unknown or adversarial object graphs extract-only. Do not claim real-game or device results from controlled fixtures.

## Required focused tests

Run the existing executable tests first:

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_modern_writer_is_byte_stable_with_existing_translation_pickle `
 test_fast_scanner.FastApkScannerContractTest.test_protocol2_writer_uses_only_python2_compatible_opcodes `
 test_fast_scanner.FastApkScannerContractTest.test_protocol2_generation_support_matrix_is_verified_or_extract_only `
 test_fast_scanner.FastApkScannerContractTest.test_protocol2_adversarial_object_graph_stays_extract_only -v
```

Expected baseline: 4 PASS. The verifier must not call Python `pickle.loads`, Java object deserialization, or execute `GLOBAL` targets.

## Required boundary

Build a protocol-2 always-on artifact and assert together: pickle language is `NONE`, output path includes `tl/None`, and the selectable artifact remains `slgtranslated`. Verify the modern golden output remains byte-for-byte stable and that the capability matrix does not promote unverified protocol-2 dialogue/object-graph behavior into a writer path.

## Expected scope

Modify only if evidence demonstrates a real gap:

- `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- `apk-work/ui-redesign/test_fast_scanner.py`
- `docs/qa/renpy-batch-bc-evidence.md`
- `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

If current production behavior already satisfies the requirements, add or correct executable evidence only. Do not use unsafe deserialization, widen the protocol-2 opcode set, or silently treat unknown structures as writable.

## Regression and evidence

Run `py_compile`, the focused C13 tests, `python -m unittest test_fast_scanner.py -v`, `python -m unittest test_workshop_patch.py -v`, `python -m unittest discover -s . -p 'test_*.py' -v`, and `python apk-work/native-fast-scan/build_fast_scanner.py`. Inspect the helper DEX for exactly one `RpycPickleWriter` definition. Update C13-01..C13-06 with exact counts, commit references, and explicit controlled-fixture/no-device/no-real-corpus boundaries. Keep unavailable real-corpus and device rows `NOT-RUN`.

Commit message: `test: revalidate restricted protocol2 writer`
