# Task 17 / C15 implementation brief

## Scope

Revalidate the advanced Ren'Py dialogue-ID translation mode and its rollback
boundary. Work offline only; do not install, launch, or modify the connected
Android device. The real save/load/rollback/jump/selectable/always-on matrix
must remain explicitly `NOT-RUN` unless the main agent later performs it.

## Allowed files

- `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialogueTranslation.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- `apk-work/ui-redesign/patch_workshop_ui.py`
- `apk-work/ui-redesign/test_fast_scanner.py`
- `apk-work/ui-redesign/test_workshop_patch.py`

Do not edit the evidence document or progress ledger; the main agent owns those
files. Do not touch the four pre-staged user documents, unrelated APKs, helper
outputs, or generated artifacts.

## Required behavior

1. Extract only verified `Say`/`TranslateSay` identifier records; never invent
   an identifier from text, source position, or list order.
2. `RpycPickleWriter.isDialogueIdWriterVerified(Dialect,int)` must enable only
   the fixture-verified modern AST version (`17` / `PY3_MODERN`); protocol 2 and
   other versions remain extract-only/global-string-map.
3. The UI capability gate must default to the global string map and enable the
   advanced mode only when extractor, writer, AST-version, and rollback flags
   are all true and at least one reliable dialogue record exists.
4. Reject/fail closed for empty, oversized, whitespace/code-like/unsafe IDs,
   duplicate IDs mapped to different old text, protocol 2, and modern AST
   versions other than 17. No rejected case may emit a `TranslateSay` node.
5. A mixed fixture must keep dialogue translations in `dialogueTranslations`
   while retaining menu labels, character names, and marked UI strings in the
   ordinary `TranslateString` map.
6. Preserve the existing default global-string artifact byte stability.

## Required checks

- Add executable focused coverage for the unsafe-ID and AST-version matrix and
  the four capability flags, not only token assertions.
- Run the focused C15 scanner/workshop tests, `py_compile`, full scanner and
  workshop suites, nested discovery, helper build, and DEX ownership checks.
- Report exact commands/results and keep the device-only matrix `NOT-RUN`.

## Commit boundary

The main agent will create the independent commit with message:
`test: revalidate dialogue id mode rollback boundary`

