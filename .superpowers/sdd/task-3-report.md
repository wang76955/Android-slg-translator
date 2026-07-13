# Task 3 report

Status: complete.

Implementation:

- Replaced the overlay runtime with a single state-driven `.workshop-task-shell`.
- Added idle, scanning, ready, and failed renderers with state/data attributes, friendly Chinese copy, expandable details, progress, summary, and contextual actions.
- Kept React picker/start nodes mounted, marked them `aria-hidden`, and bridged visible actions with bubbling `MouseEvent` dispatches.
- Added a debounced `MutationObserver`, snapshot parsing for selection/count/ENOSPC, idempotent rendering, visible Back affordance, and active-task navigation hiding.
- Kept the idle bottom navigation visible while hiding the legacy React main surface, and bridged the failed-state retry action to the existing React start/picker control with a short honest scanning window.
- Removed the obsolete legacy runtime block and updated the contract test for the new shell.

Verification:

```text
python -m py_compile apk-work/ui-redesign/patch_workshop_ui.py
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
  Ran 2 tests in 0.011s - OK
python apk-work/ui-redesign/patch_workshop_ui.py
node --check apk-work/ui-redesign/generated/index-CJtfdHOF.js
  passed
```

The full discovery suite still reports the pre-task expected failure because the signed APK fixture has not been built yet (`test_built_apk.py`: signed workshop APK does not exist). Build/install verification is deferred to Task 5.
