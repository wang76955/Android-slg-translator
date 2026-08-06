# Task 8 report: Ren'Py translation context collisions

## Scope

Baseline: `f66493b`.

Implemented only the Task 8 corpus, local translation support, workshop patch, and quality/coverage regression scope. Existing untracked workspace files were preserved.

## Delivered

- Added `RenpyTranslationCorpus.Entry` with exact `exactOld`, all occurrence records, and contextual collision detection.
- Context identity is exactly `(speaker, identifier, kind, sourcePath)`; repeated occurrences in the same context are not collisions.
- Preserved full exact old keys, including `{#...}` suffixes.
- Added bounded context prompt output (up to three representative contexts).
- Added local translation collision detection that rejects multiple different translations for one exact old string with `translation_collision_conflict`.
- Added sanitized UI collision reporting with unique-old, occurrence, duplicate, and collision counts plus JSON export.
- Added Java corpus and UI/coverage regression assertions already present in the Task 8 test modules.

## Verification

Command run from `apk-work/ui-redesign`:

```text
python -m unittest test_translation_quality.py test_translation_coverage.py -v
Ran 17 tests in 2.595s
OK (skipped=1)
```

The one skipped test requires an audit APK and extracted-text dump that are not present in the workspace. No test failures remained in the requested quality or coverage modules. An earlier invocation from the repository root produced import errors for the pre-existing `patch_local_ui` module because the test loader relies on the UI directory being the working directory; the exact requested directory-scoped command passes.

## Commit

`feat: report renpy translation context collisions`
