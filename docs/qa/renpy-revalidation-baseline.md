# Ren'Py batch BC complete revalidation baseline

This is the Task 0 baseline for plan `2026-08-07-renpy-batch-bc-complete-revalidation`.
It was collected from `D:\文件翻译` on 2026-08-07. Values below are from the
current checkout and are not carried forward from an older ledger.

## Source APK provenance gate

The source artifact is pinned to the following repository provenance:

| Field | Pinned value |
|---|---|
| Repository | `https://github.com/wang76955/slg-translator` |
| Fixed source commit | `fc2e3f39f85a09799e63fa652e566e3850ff9f31` |
| Raw APK URL | `https://raw.githubusercontent.com/wang76955/slg-translator/fc2e3f39f85a09799e63fa652e566e3850ff9f31/android-release/slg-translator-android-rpyc-v12.apk` |
| Local APK path | `apk-work/github-source/slg-translator-android-rpyc-v12.apk` |
| Local SHA256 | `44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104` |

The repository, fixed commit, raw URL, local path, and SHA256 are one
provenance tuple. If any future revalidation finds a mismatch in any member
of this tuple, it must stop immediately and record `FAIL` or `NOT-RUN`; it must
not continue by substituting another APK or by treating the local file as an
equivalent source.

## Source APK and Git snapshot

Command:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'apk-work/github-source/slg-translator-android-rpyc-v12.apk'
```

Actual output:

```text
Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104       D:\文件翻译\apk-work\github-source\slg-translator-android-rpyc-v12.apk
```

Command:

```powershell
git rev-parse HEAD
git status --short --branch
```

Actual HEAD:

```text
d38b551aa96a3914bfbb3795c70808ae900626f3
```

The status began with `## master`. The four user-protected documents were
already staged as `A` before Task 0:

```text
A  PRODUCT.md
A  docs/superpowers/plans/2026-07-13-apk-main-flow-redesign-v2.md
A  docs/superpowers/specs/2026-07-13-android-apk-ui-redesign-design.md
A  docs/superpowers/specs/2026-07-13-apk-main-flow-redesign-v2-design.md
```

The same status also contained a large pre-existing set of unrelated `??`
APK, screenshot, fixture, and script paths. They were left untouched. No
pre-existing staged path was changed by Task 0.

## Toolchain probe

Commands were run from the repository root:

```powershell
python --version
java -version
node --version
Get-Command adb,apksigner,zipalign -ErrorAction SilentlyContinue | Select-Object Name,Source
```

Actual outputs:

```text
Python 3.14.5

java : The term 'java' is not recognized as the name of a cmdlet, function, script file, or operable program.
...
CategoryInfo          : ObjectNotFound: (java:String) [], CommandNotFoundException
FullyQualifiedErrorId : CommandNotFoundException

v22.14.0

<no output from Get-Command adb,apksigner,zipalign ...>
```

The unavailable tools are explicitly not treated as successful checks:

| Tool | Observed state | State used by this baseline | Recovery command |
|---|---|---|---|
| Python | `Python 3.14.5` | available | `python --version` |
| Java | PowerShell `CommandNotFoundException` | `NOT-RUN` | Set `JAVA_HOME` and prepend `<JAVA_HOME>\bin` to `PATH`, then run `java -version` |
| Node | `v22.14.0` | available | `node --version` |
| `adb` | no `Get-Command` row | `NOT-RUN` | Set `$env:Path` to include `<ANDROID_SDK_ROOT>\platform-tools`, then run `Get-Command adb` |
| `apksigner` | no `Get-Command` row | `NOT-RUN` | Set `$env:Path` to include `<ANDROID_SDK_ROOT>\build-tools\<version>`, then run `Get-Command apksigner` |
| `zipalign` | no `Get-Command` row | `NOT-RUN` | Set `$env:Path` to include `<ANDROID_SDK_ROOT>\build-tools\<version>`, then run `Get-Command zipalign` |

Reusable PowerShell recovery probe once the SDK/JDK locations are installed:

```powershell
$env:JAVA_HOME = '<JAVA_HOME>'
$env:ANDROID_SDK_ROOT = '<ANDROID_SDK_ROOT>'
$env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_SDK_ROOT\platform-tools;$env:ANDROID_SDK_ROOT\build-tools\<version>;$env:Path"
python --version
java -version
node --version
Get-Command adb,apksigner,zipalign -ErrorAction SilentlyContinue | Select-Object Name,Source
```

## Complete unittest baseline

Command, run from `apk-work/ui-redesign` before adding the Task 0 test:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Actual final output summary:

```text
Ran 167 tests in 144.343s

FAILED (failures=25, errors=1, skipped=1)
```

The observed count exactly matched the brief's expected plan-start baseline
(167 / 25 / 1 / 1), so there was no added or disappeared test name to record.
The skipped test reported the existing reason:
`audit APK/extracted texts not present`.

## Failure inventory and reproducible focus commands

The complete `test_workshop_patch.py` run was repeated for this repair round:

```powershell
python -m unittest test_workshop_patch.py -v
```

Actual aggregate output:

```text
Ran 49 tests in 6.926s

FAILED (failures=25, errors=1)
EXIT_CODE=1
```

Each item below was then run with the stable focus command shown in the
`command` column. The first diagnostic is normalized only by removing the
multi-megabyte generated-JavaScript right-hand side from `not found in`
assertions; no bundle dump is pasted here. Categories are the fixed design
categories: `C1` product/generated-asset regression, `C2` test still asserts
old behavior, `C3` test depends on compressed JavaScript internals, `C4`
product/generated-asset encoding boundary, `C5` fixture lacks current
React/Capacitor state, and `C6` external condition missing. No C2 or C6 item
was observed in this baseline.

| # | Result | Test name | command | First valid diagnostic | Category |
|---:|---|---|---|---|---|
| 1 | ERROR | `test_translation_cache_is_reused_across_models` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_cache_is_reused_across_models -v` | `ValueError: substring not found` | C3 |
| 2 | FAIL | `test_completed_zero_entry_scan_is_an_empty_result_not_scanning` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning -v` | `Error: settled zero-entry scan misclassified: {"state":"idle"}` | C5 |
| 3 | FAIL | `test_dismiss_recovery_banner_re_renders_immediately` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately -v` | `Error: recovery banner offers dismiss` | C5 |
| 4 | FAIL | `test_fatal_network_stops_outer_file_controller` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_fatal_network_stops_outer_file_controller -v` | `AssertionError: expected bundle marker not found in <bundle dump omitted>` | C3 |
| 5 | FAIL | `test_installed_app_source_chooser_contract` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_installed_app_source_chooser_contract -v` | `AssertionError: window.__slgSelectionMeta=e not found in <bundle dump omitted>` | C3 |
| 6 | FAIL | `test_installed_list_and_selection_epochs_ignore_stale_requests` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_installed_list_and_selection_epochs_ignore_stale_requests -v` | `AssertionError: 1 != 0 : [eval]:55` | C5 |
| 7 | FAIL | `test_long_running_phases_are_not_reported_as_directory_scanning` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_long_running_phases_are_not_reported_as_directory_scanning -v` | `AssertionError: progress marker not found in <bundle dump omitted>` | C3 |
| 8 | FAIL | `test_network_failure_preempts_stale_translating_ui` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_network_failure_preempts_stale_translating_ui -v` | `AssertionError: network failure UI marker not found in <bundle dump omitted>` | C3 |
| 9 | FAIL | `test_network_failures_stop_batches_without_recursive_splitting` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_network_failures_stop_batches_without_recursive_splitting -v` | `AssertionError: network error marker not found in <bundle dump omitted>` | C3 |
| 10 | FAIL | `test_partial_network_failure_never_writes_or_packages` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_partial_network_failure_never_writes_or_packages -v` | `ReferenceError: _maxDone is not defined` | C1 |
| 11 | FAIL | `test_patch_contains_player_workshop_contract` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_patch_contains_player_workshop_contract -v` | `AssertionError: workshop copy marker not found in <bundle dump omitted>` | C3 |
| 12 | FAIL | `test_patch_installs_visible_android_shell` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_patch_installs_visible_android_shell -v` | `AssertionError: 处理详情 not found in <bundle dump omitted>` | C3 |
| 13 | FAIL | `test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines -v` | `AssertionError: text-pipeline marker not found in <bundle dump omitted>` | C3 |
| 14 | FAIL | `test_save_and_import_game_selection_are_independent` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_and_import_game_selection_are_independent -v` | `AssertionError: 1 != 0 : [eval]:6` | C5 |
| 15 | FAIL | `test_save_transfer_can_import_shared_archive` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_can_import_shared_archive -v` | `AssertionError: 1 != 0 : [eval]:46` | C5 |
| 16 | FAIL | `test_save_transfer_can_pick_game_from_installed_apps` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_can_pick_game_from_installed_apps -v` | `AssertionError: 1 != 0 : [eval]:8` | C5 |
| 17 | FAIL | `test_save_transfer_runtime_actions_and_state_gating` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_runtime_actions_and_state_gating -v` | `AssertionError: 1 != 0 : [eval]:40` | C5 |
| 18 | FAIL | `test_save_transfer_settings_runtime_contract` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_settings_runtime_contract -v` | `AssertionError: 选择游戏 not found in <bundle dump omitted>` | C3 |
| 19 | FAIL | `test_settings_support_provider_model_and_custom_endpoint` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_settings_support_provider_model_and_custom_endpoint -v` | `AssertionError: 已保存： not found in <bundle dump omitted>` | C3 |
| 20 | FAIL | `test_shared_loader_has_deadline_and_stale_safe_settlement` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_shared_loader_has_deadline_and_stale_safe_settlement -v` | `Error: timeout contract` | C5 |
| 21 | FAIL | `test_source_modals_handle_android_back_focus_and_file_fallback` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_source_modals_handle_android_back_focus_and_file_fallback -v` | `Error: error state exposes retry and file fallback` | C5 |
| 22 | FAIL | `test_task_runtime_bridges_and_recovery_contract` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract -v` | `AssertionError: 手机空间不足 not found in <bundle dump omitted>` | C3 |
| 23 | FAIL | `test_translating_state_does_not_replay_card_entrance_animation` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation -v` | `AssertionError: translating animation marker not found in <bundle dump omitted>` | C3 |
| 24 | FAIL | `test_translation_heartbeat_updates_session` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_heartbeat_updates_session -v` | `Error: heartbeat refreshes savedAt while translating` | C5 |
| 25 | FAIL | `test_translation_logs_are_mirrored_into_the_visible_shell` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_logs_are_mirrored_into_the_visible_shell -v` | `AssertionError: details mirror marker not found in <bundle dump omitted>` | C3 |
| 26 | FAIL | `test_translation_progress_emits_starting_batch_before_request` | `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_progress_emits_starting_batch_before_request -v` | `Error: both batches translate` | C5 |

The focused runs all returned exit code 1. The exact test name and command
template are retained for reruns; the concise first diagnostics above are
the audit evidence, while the raw temporary log was not added to the
repository.

This result is a source-test baseline only. It does not claim APK build,
signing, installation, launch, or translation coverage success.

## Task 0 evidence contract

The companion evidence ledger at
`docs/qa/renpy-batch-bc-evidence.md` is the shared state model for Tasks 6–16.
Every row uses exactly one of `PASS`, `FAIL`, or `NOT-RUN`. Task 0 initializes
Tasks 6–16 as `NOT-RUN`; later tasks must replace a row only with evidence
backed by the referenced command and artifact.

The machine assertion is
`TranslationCoverageLogicTest.test_revalidation_evidence_uses_only_explicit_statuses`.
Its TDD RED/GREEN record is in `task-0-report.md`.
