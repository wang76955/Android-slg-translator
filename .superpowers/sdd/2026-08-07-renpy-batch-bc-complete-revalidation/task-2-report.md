# Task 2 report: completion, empty scan, recovery, animation, heartbeat

Date: 2026-08-07
Base before dispatch: 7517acb
Scope: only the five Task 2 tests named in task-2-brief.md.

## Result

All five Task 2 tests pass after replacing the cluster's manual JavaScript slicing with extract_js_function and correcting stale test fixtures/contracts. No product code change was required. The product behavior fixtures confirm the required transitions:

- settled zero-entry scan with no fatal error returns state empty and keeps filename/split metadata.
- savedSession.translating produces an eligible recovery banner.
- recovery dismiss removes SESSION_KEY, resets sessionRestoredAt, invalidates the snapshot through the refresh path, and re-renders immediately.
- translating and patching disable card entrance animation replay.
- translating refresh writes a fresh session heartbeat.

## TDD RED/GREEN evidence

Initial RED was collected at BASE 7517acb before edits, with each exact test run individually using -v:

1. test_completed_zero_entry_scan_is_an_empty_result_not_scanning
   First effective failure: Error: settled zero-entry scan misclassified: {"state":"idle"}.
2. test_dismiss_recovery_banner_re_renders_immediately
   First effective failure: Error: recovery banner offers dismiss.
3. test_task_runtime_bridges_and_recovery_contract
   First effective failure: stale ENOSPC localized-copy token assertion. The resulting patched-bundle dump was not treated as root cause.
4. test_translating_state_does_not_replay_card_entrance_animation
   First effective failure: compacted CSS did not contain the expected selector token.
5. test_translation_heartbeat_updates_session
   First effective failure: Error: heartbeat refreshes savedAt while translating.

After the first extraction replacement, readTaskSnapshot extraction itself failed because the existing Task 1 scanner interpreted the apostrophe in the real regex literal /...Ren'Py.../ as a JavaScript string start. This was classified as BRITTLE_EXTRACTION. The test-side extract_js_function was minimally hardened to recognize regex literals, escapes, and character classes. No production file was changed.

After complete-function extraction, the remaining behavior failures were caused by stale mojibake fixtures and stale static tokens, not product behavior. The fixtures were changed to current UTF-8-equivalent JavaScript Unicode escapes, and assertions were aligned with the current generated contract without removing required behavior assertions.

Final responsibility-group command:

    python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately test_workshop_patch.WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract test_workshop_patch.WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation test_workshop_patch.WorkshopPatchContractTest.test_translation_heartbeat_updates_session -v

Output: Ran 5 tests in 0.404s; OK.

## Per-test root causes and GREEN evidence

### test_completed_zero_entry_scan_is_an_empty_result_not_scanning

Files: apk-work/ui-redesign/test_workshop_patch.py; docs/qa/renpy-workshop-failure-inventory.md.
Classification: STALE_CONTRACT, with an initial BRITTLE_EXTRACTION finding.
Cause: manual slicing ended at an obsolete next-function marker; after switching to complete extract_js_function behavior, the fixture's mojibake status text and old split-copy token no longer matched the current runtime contract. The current fixture drives readTaskSnapshot through the settled zero-entry branch and verifies empty, count 0, filename, splitApk, and splitCount.
GREEN: python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning -v; Ran 1 test ... OK.

### test_dismiss_recovery_banner_re_renders_immediately

Files: apk-work/ui-redesign/test_workshop_patch.py; docs/qa/renpy-workshop-failure-inventory.md.
Classification: STALE_CONTRACT.
Cause: the manual slices did not represent complete current functions, and the fixture used stale encoded labels. Complete extraction of readTaskSnapshot, renderStateBody, setWorkshopState, snapshotKey, refresh, and recoveryBanner with current labels proves the visible banner, dismiss control, marker reset, localStorage removal, refresh, and immediate banner removal.
GREEN: python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately -v; Ran 1 test ... OK.

### test_task_runtime_bridges_and_recovery_contract

Files: apk-work/ui-redesign/test_workshop_patch.py; docs/qa/renpy-workshop-failure-inventory.md.
Classification: STALE_CONTRACT.
Cause: the first assertion expected an obsolete ENOSPC localized token. The global prohibition on any .click() also matched unrelated export-link behavior in the base bundle. The test now checks the current space-error copy/retry action and only rejects direct click shortcuts on sourceButton/startButton/installButton. React ownership, bubbling dispatch, state attributes, and observer debouncing remain asserted.
GREEN: python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract -v; Ran 1 test ... OK.

### test_translating_state_does_not_replay_card_entrance_animation

Files: apk-work/ui-redesign/test_workshop_patch.py; docs/qa/renpy-workshop-failure-inventory.md.
Classification: STALE_CONTRACT.
Cause: the test compacted CSS whitespace but expected a selector containing a descendant space. The current CSS already contains the compact translating and patching animation:none selectors. The test now verifies both active phases and still verifies the default workshopRise animation exists.
GREEN: python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation -v; Ran 1 test ... OK.

### test_translation_heartbeat_updates_session

Files: apk-work/ui-redesign/test_workshop_patch.py; docs/qa/renpy-workshop-failure-inventory.md.
Classification: STALE_CONTRACT.
Cause: the original fixture status was mojibake, so readTaskSnapshot classified it as idle and refresh never entered the translating heartbeat branch. With complete extraction and a current translating fixture, refresh updates savedAt and keeps translating true.
GREEN: python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_heartbeat_updates_session -v; Ran 1 test ... OK.

## Approved completed copy verification

Ran the related focused tests:

    python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_completed_shell_only_offers_install_for_a_current_react_action test_workshop_patch.WorkshopPatchContractTest.test_ready_mode_selector_and_completed_language_guidance test_workshop_patch.WorkshopPatchContractTest.test_session_banner_only_after_translation_started test_workshop_patch.WorkshopPatchContractTest.test_translation_state_requests_screen_wakelock -v

Output: Ran 4 tests in 0.281s; OK.

The completed language guidance test remains green. It preserves selectable guidance to enter the game language settings to choose the translated text and allow switching back; always_on guidance says translation is enabled at startup and cannot claim an in-game switch back; custom-menu guidance says the standard language menu cannot select it. No generic translation-completed success copy was restored.

## Inventory update

Updated only WSP-02, WSP-03, WSP-22, WSP-23, and WSP-24 in docs/qa/renpy-workshop-failure-inventory.md. Each entry now records the baseline first effective failure, the complete-function/current-fixture evidence, the STALE_CONTRACT or BRITTLE_EXTRACTION classification, the changed test file, and a real GREEN command. Network, source chooser, save transfer, settings, cache, and other failure clusters were not repaired or expanded.

## Files changed

- apk-work/ui-redesign/test_workshop_patch.py
- docs/qa/renpy-workshop-failure-inventory.md
- D:/文件翻译/.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/task-2-report.md

apk-work/ui-redesign/patch_workshop_ui.py was intentionally not changed because behavior fixtures show the current patch already satisfies the required state transitions.

## Remaining risks

- extract_js_function now recognizes the regex-literal patterns needed by this runtime, including escaped characters and character classes; it is still a lightweight scanner rather than a full JavaScript parser.
- The generated bundle contains unrelated anchor.click() export behavior; the runtime bridge contract intentionally scopes the no-direct-click assertion to the React-managed task controls.
- The five tests are contract/harness tests around generated JS and CSS. A device-level visual run was outside Task 2 scope.
- The worktree contains pre-existing staged and untracked user files. The commit must use explicit --only paths so those files remain untouched.

