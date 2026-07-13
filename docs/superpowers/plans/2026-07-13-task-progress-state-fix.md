# Task Progress State Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the real APK task phase instead of presenting translation and patch generation as directory scanning.

**Architecture:** Extend the injected task-shell state machine while leaving the React/Capacitor business flow untouched. Derive phase and file progress from the existing React text, then render phase-specific copy and actions through the existing bubbling-event bridge.

**Tech Stack:** Python patch generator, injected JavaScript/CSS, unittest, Android WebView, ADB, zipalign, apksigner.

## Global Constraints

- Do not change the native APK directory scanner or translation API behavior.
- Keep React-managed controls mounted and trigger them only through bubbling events.
- Run the scan clock only in `scanning`.
- Use concise, non-technical Chinese status copy and 48dp minimum touch targets.

---

### Task 1: Lock the phase contract

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

- [ ] Add assertions for `translating`, `patching`, and `completed` state mapping, rendering, CSS selectors, and text-node observation.
- [ ] Run the focused test and confirm it fails because the current runtime maps translation to `scanning`.

### Task 2: Implement phase-specific state rendering

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`

- [ ] Parse file progress from “正在处理脚本 X / Y”.
- [ ] Detect states in failure/completion/patching/translation/ready/scanning order.
- [ ] Render accurate phase copy, progress, details, and completed install action.
- [ ] Observe `characterData` so in-place React text changes refresh the shell.
- [ ] Run the focused and complete unit suites.

### Task 3: Build and verify on Android

**Files:**
- Generate: `apk-work/ui-redesign/generated/*`
- Build: `apk-work/slg-workshop-ui-signed.apk`

- [ ] Build and sign the APK.
- [ ] Verify zip alignment and v2/v3 signatures.
- [ ] Install with ADB and reproduce the real selection/start flow.
- [ ] Confirm the visible shell leaves `scanning` after directory inspection and enters `translating` after start.
