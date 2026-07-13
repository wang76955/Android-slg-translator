# Task 4 Report — behavior-oriented contract coverage

## Changes

- Extended `apk-work/ui-redesign/test_workshop_patch.py` with a focused runtime
  contract test covering bubbling `MouseEvent` bridges for picker/start/retry,
  state and task data attributes, state classes, idle/active navigation CSS,
  ENOSPC recovery copy and raw-detail disclosure, React-node ownership, and the
  debounced `MutationObserver`. The coverage also pins the picker/start
  callbacks, explicit idle/active display declarations, the failed-state
  mapping, retry callback, append/appendChild movement variants, and optional
  chaining direct-click variants. Movement guards now cover append,
  appendChild, prepend, insertBefore, and replaceChildren, while the direct
  click guard accepts arbitrary receiver names and whitespace.
- Assertions consume only the generated `patch_assets(js, css)` strings and use
  exact UTF-8 copies for the user-visible Chinese strings.

## Verification

Focused command:

```text
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
```

Result: **3 tests passed**.

Full command:

```text
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
```

Result: **3 tests passed, 1 expected failure**. The only failure is
`test_built_apk.BuiltApkTest.test_signed_apk_contains_workshop_assets`, because
`apk-work/slg-workshop-ui-signed.apk` has not been generated yet. Task 5 owns
the APK build and will remove this pre-build limitation.
