# Task 5 Report — Build, install, and verify the real APK flow

## Build and regression evidence

- Worktree: `C:\Users\王运\Documents\文件翻译-worktree`
- Device: `MZNRYXEQS859O7GU` (`PEMM20`), ADB state `device`.
- Focused patch suite before build: `python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v` — 3 tests passed.
- Full suite before build: `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v` — 4 tests passed after the signed artifact was present.
- Build: `python apk-work/ui-redesign/build_workshop_apk.py` — exit 0; generated `apk-work/slg-workshop-ui-signed.apk` (10,229,128 bytes).
- Alignment: `.tools/android-15/zipalign.exe -c 4 apk-work/slg-workshop-ui-signed.apk` — exit 0.
- Signature: `.tools/android-15/apksigner.bat verify --verbose apk-work/slg-workshop-ui-signed.apk` — exit 0; v2 and v3 verification true.
- Install: `adb -s MZNRYXEQS859O7GU install -r apk-work/slg-workshop-ui-signed.apk` — `Success`.
- Final regression after artifact generation: `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v` — 4 tests passed.

## Device evidence

- Idle launch was captured after force-stop/monkey launch in [main-flow-idle.png](../../apk-work/ui-redesign/qa/main-flow-idle.png). It shows the redesigned APK 翻译 shell, olive brand panel, compact file card, single picker CTA, and idle bottom navigation.
- Idle UI hierarchy was captured in [main-flow-idle-uiautomator.xml](../../apk-work/ui-redesign/qa/main-flow-idle-uiautomator.xml). Android exposes the app as a WebView; the visible DOM is therefore not fully represented in the native hierarchy.
- Picker launch was exercised and captured in [main-flow-picker-final.png](../../apk-work/ui-redesign/qa/main-flow-picker-final.png). The system picker opened successfully. A 10.23 MB fixture was pushed non-destructively to `/sdcard/Download/ui-test.apk` and selected from the picker.
- Selected/scanning evidence was captured in [main-flow-selected-final.png](../../apk-work/ui-redesign/qa/main-flow-selected-final.png) with hierarchy in [main-flow-selected-final-uiautomator.xml](../../apk-work/ui-redesign/qa/main-flow-selected-final-uiautomator.xml). The shell visibly hides bottom navigation and shows `处理中`, `已选择文件`, `正在检查文件`, a progress bar, and `处理详情`.

## Limitation

The `main-flow-ready-final.*` filenames are retained historical captures of the scanning state, not ready-state evidence. The picker image is an earlier picker view; the selected fixture evidence is `main-flow-selected-final.*`.

The selected fixture remained in the scanning state for at least 100 seconds; no ready or recoverable-failure transition was observed on this device. The hierarchy confirms the same scanning state and no bottom navigation. This is recorded as a fixture/runtime processing limitation, not claimed as ready-state evidence. Earlier selection of the device's existing `base.apk` also remained scanning and reports a 4.22 GB picker size. Device storage had approximately 12 GB available (`df -h`), so no new ENOSPC failure was reproduced during this run.
