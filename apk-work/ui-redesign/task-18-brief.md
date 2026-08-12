# Task 18 / C16 implementation brief

## Scope

Rebuild the release machine matrix and definition-of-done documents from the
current Task 6–17 evidence. This is offline documentation/test work only; do
not install or launch anything on the connected Android phone, and do not
invent a real Ren'Py corpus or device outcome.

## Allowed files

- `docs/qa/renpy-compatibility-matrix.md`
- `docs/qa/renpy-release-checklist.md`
- `docs/qa/renpy-batch-bc-evidence.md`
- `apk-work/ui-redesign/test_translation_coverage.py`

The main agent owns the progress ledger and final commit. Do not edit it, do
not modify the four pre-staged user documents, and do not touch APK/DEX
artifacts or unrelated source files.

## Required matrix contract

1. Add explicit C16-01..C16-06 requirement/evidence rows covering engine
   generation, archive/compiled format, activation strategy, font coverage,
   APK shape/build, device smoke and final release gate.
2. Every matrix/release row must preserve support level, activation strategy,
   template/source, unique/occurrence/collision counts, missing/rejected,
   font result, build/install/startup/save result, and evidence reference.
   Unknown external outcomes must remain `NOT-RUN`/`not-run`.
3. Update the document contract test so it checks these exact tokens in both
   matrix and checklist:

   `SAFE`, `WARNING`, `EXTRACT_ONLY`, `UNSUPPORTED`, `single APK`,
   `base + split`, `selectable`, `always-on`, `missing == 0`, `old save`,
   `rollback`, `NOT-RUN`.

4. The release checklist must not contain `当前状态：批准发布` while any
   mandatory row is `FAIL` or `NOT-RUN`; make the assertion executable.
5. Preserve the honest C15/C14 boundaries: automated evidence is local
   controlled-fixture evidence; C15-05 real save/rollback/device behavior,
   real corpus rows and any unverified device result stay NOT-RUN.

## Required verification

Run the two Task 18 documentation tests from `apk-work/ui-redesign` and
`py_compile` for `test_translation_coverage.py`. Report exact results. Do not
create a commit; the main agent will review and commit the four allowed paths.

