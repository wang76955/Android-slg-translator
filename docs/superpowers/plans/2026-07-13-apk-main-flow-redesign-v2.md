# APK Main Flow Redesign v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with checkpoints.

**Goal:** Replace the overlay-style Hero + legacy form with a state-driven single-screen Android task flow for APK selection, scanning, confirmation, and recoverable failure.

**Architecture:** Keep the existing React/Capacitor business handlers intact and add a deterministic UI shell in the injected runtime. The shell owns visible layout and state copy, while hidden legacy controls remain mounted and are triggered through `dispatchEvent` so file picking, scanning, translation, packaging, and installation behavior do not change. A `MutationObserver` derives `idle`, `scanning`, `ready`, and `failed` from existing app text and task logs.

**Tech Stack:** Minified React WebView bundle, injected JavaScript/CSS assets, Python APK repackaging, unittest, ADB screenshots/UI dumps, zipalign, apksigner.

## Global Constraints

- Use Material 3 component vocabulary and keep every touch target at least 48dp.
- Use pure white or neutral surface backgrounds; olive green is reserved for brand, primary action, and success state.
- Hide top-level bottom navigation during `selected`, `scanning`, `ready`, and `failed` task states.
- Keep React-managed native controls mounted; trigger them with bubbling events instead of moving or cloning them.
- Keep API, translation, packaging, install, and file-picker business interfaces unchanged.
- Respect dark mode, safe-area insets, reduced motion, Android system Back, and system font scaling.

---

### Task 1: Lock the state-driven UI contract with failing tests

**Files:**
- Modify: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\test_workshop_patch.py`
- Test fixture: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\patch_workshop_ui.py`

**Interfaces:**
- Consumes: `patch_assets(js, css) -> tuple[str, str]`.
- Produces: string-level contracts for the runtime state machine and visible shell that later tasks must satisfy.

- [ ] **Step 1: Add failing assertions for the task shell and state vocabulary**

Add these assertions to `test_patch_installs_visible_android_shell`:

```python
for token in (
    "workshop-task-shell",
    "data-workshop-state",
    "workshop-state-idle",
    "workshop-state-scanning",
    "workshop-state-ready",
    "workshop-state-failed",
    "setWorkshopState",
    "处理详情",
    "正在检查文件",
    "可以开始了",
    "手机空间不足",
):
    self.assertIn(token, js)
self.assertIn("workshop-task-shell", css)
self.assertIn("workshop-task-shell[data-workshop-state=\"scanning\"]", css)
self.assertIn("workshop-task-shell[data-workshop-state=\"ready\"]", css)
self.assertIn("workshop-task-shell[data-workshop-state=\"failed\"]", css)
```

Add a regression assertion that task states hide the navigation:

```python
self.assertIn(
    ".workshop-runtime[data-workshop-task=\"active\"] .workshop-bottom-nav",
    css,
)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
```

Expected: `FAIL` because the current Hero-only runtime has no task shell or state renderer.

### Task 2: Build the neutral Material 3 task shell styles

**Files:**
- Modify: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\patch_workshop_ui.py`
- Test: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\test_workshop_patch.py`

**Interfaces:**
- Consumes: existing `WORKSHOP_CSS` tokens and safe-area/reduced-motion rules.
- Produces: `.workshop-task-shell` layout and state-specific visual rules used by the runtime in Task 3.

- [ ] **Step 1: Replace the oversized Hero-only composition with shell tokens**

Keep the existing `:root` and dark-mode tokens, then add these rules inside `WORKSHOP_CSS`:

```css
.workshop-task-shell{position:relative;display:flex;flex-direction:column;gap:16px;min-height:calc(100dvh - 24px);padding:20px 16px 112px;background:var(--workshop-bg);color:var(--workshop-ink)}
.workshop-task-topbar{display:flex;align-items:center;justify-content:space-between;min-height:48px}
.workshop-task-topbar h1{margin:0;font-size:20px;line-height:1.25;font-weight:700;letter-spacing:-.01em}
.workshop-task-back{min-width:48px;min-height:48px;border:0;border-radius:14px;background:transparent;color:var(--workshop-ink);font-size:22px}
.workshop-brand-panel{padding:18px 18px 20px;border-radius:20px;background:var(--workshop-primary);color:var(--workshop-on-primary)}
.workshop-brand-panel p{margin:0;font-size:14px;line-height:1.45;opacity:.86}
.workshop-brand-panel h2{margin:4px 0 0;font-size:25px;line-height:1.2;font-weight:750;letter-spacing:-.02em}
.workshop-task-card{padding:18px;border:1px solid color-mix(in oklch,var(--workshop-ink) 12%,transparent);border-radius:18px;background:var(--workshop-surface);box-shadow:none}
.workshop-file-row{display:flex;align-items:center;gap:12px;min-height:56px}
.workshop-file-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;background:color-mix(in oklch,var(--workshop-primary) 12%,var(--workshop-surface));color:var(--workshop-primary);font-weight:800}
.workshop-file-name{min-width:0;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.workshop-file-meta{margin-top:3px;color:var(--workshop-muted);font-size:13px}
.workshop-state-copy{margin:12px 0 0;color:var(--workshop-muted);line-height:1.45}
.workshop-progress{height:4px;margin-top:14px;border-radius:999px;background:color-mix(in oklch,var(--workshop-primary) 14%,transparent);overflow:hidden}
.workshop-progress>i{display:block;width:38%;height:100%;border-radius:inherit;background:var(--workshop-primary);transition:width 220ms ease-out}
.workshop-summary-list{display:grid;gap:10px;margin:16px 0 0;padding:0;list-style:none}
.workshop-summary-row{display:flex;justify-content:space-between;gap:16px;font-size:14px}
.workshop-summary-row span:first-child{color:var(--workshop-muted)}
.workshop-summary-row span:last-child{text-align:right;font-weight:700}
.workshop-detail-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;margin-top:12px;padding:0;border:0;background:transparent;color:var(--workshop-primary);font-weight:700;text-align:left}
.workshop-detail-body{display:none;margin-top:8px;padding:12px;border-radius:12px;background:color-mix(in oklch,var(--workshop-ink) 5%,var(--workshop-surface));color:var(--workshop-muted);font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
.workshop-detail-body[data-open="true"]{display:block}
.workshop-primary-action{display:flex;align-items:center;justify-content:center;width:100%;min-height:52px;margin-top:auto;border:0;border-radius:16px;background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:750;font-size:15px}
.workshop-secondary-action{min-height:48px;margin-top:8px;border:0;background:transparent;color:var(--workshop-primary);font-weight:700}
.workshop-error-card{border-color:color-mix(in oklch,var(--workshop-error) 30%,transparent);background:color-mix(in oklch,var(--workshop-error) 7%,var(--workshop-surface))}
.workshop-error-title{margin:0;color:var(--workshop-error);font-size:18px;font-weight:750}
.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}
.workshop-runtime[data-workshop-task="active"] main{display:none!important}
```

Remove the old full-width `.workshop-start-button` rule and the oversized Hero button rule; the new primary action owns the task CTA.

- [ ] **Step 2: Run the focused test and verify it still fails only on JS tokens**

Run:

```powershell
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
```

Expected: CSS assertions pass; state-runtime assertions remain `FAIL`.

### Task 3: Implement the state renderer without moving React nodes

**Files:**
- Modify: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\patch_workshop_ui.py`
- Test: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\test_workshop_patch.py`

**Interfaces:**
- Consumes: existing React buttons matching `选择`, `开始翻译`, and the existing log text inside `#root`.
- Produces: `setWorkshopState(state, payload)` and a single `.workshop-task-shell` with `data-workshop-state` and `data-workshop-task` attributes.

- [ ] **Step 1: Replace `WORKSHOP_RUNTIME` with an explicit state machine**

The runtime must include these functions and behavior:

```javascript
function setWorkshopState(state, payload={}) {
  shell.dataset.workshopState = state;
  shell.dataset.workshopTask = state === "idle" ? "idle" : "active";
  shell.replaceChildren(renderTopbar(state), renderStateBody(state, payload));
}

function triggerReactButton(button) {
  button?.dispatchEvent(new MouseEvent("click", {
    bubbles: true, cancelable: true, view: window
  }));
}

function readTaskSnapshot() {
  const text = document.querySelector("#root")?.textContent || "";
  const fileName = text.match(/已选择[：:]\s*([^\n]+)/)?.[1]?.trim() || "";
  const count = text.match(/发现\s*(\d+)\s*个可翻译文件/)?.[1] || "";
  const failed = [...document.querySelectorAll("#root *")]
    .find(el => el.textContent?.includes("写入补丁 APK 失败"));
  if (failed && /ENOSPC|No space left/i.test(failed.textContent)) {
    return {state:"failed", reason:"space", raw:failed.textContent};
  }
  if (count) return {state:"ready", fileName, count};
  if (fileName || text.includes("正在扫描")) {
    return {state:"scanning", fileName};
  }
  return {state:"idle"};
}
```

The renderer must create:

- `idle`: brand panel, APK picker card, and one “选择 APK 文件” action;
- `scanning`: file row, “正在检查文件”, linear progress, and “处理详情” toggle;
- `ready`: file row, summary rows, collapsed details, and one “开始翻译” action that dispatches to the hidden React button;
- `failed`: friendly error card with “释放空间后重试” and “重新选择 APK” actions; raw error text is only in details.

The existing source and start buttons remain in the DOM with `aria-hidden="true"` and are never appended into the shell.

- [ ] **Step 2: Add controlled observation and Back handling**

Use one `MutationObserver` on `#root` with a 120ms debounce. On every snapshot change, call `setWorkshopState`. Add a single `window.addEventListener("popstate", ...)` only if the shell is active; the handler returns to `idle` without clearing the selected React state. Do not override the native Back handler or add a second bottom navigation inside task states.

- [ ] **Step 3: Run the focused tests and verify the contract passes**

Run:

```powershell
python -m unittest apk-work/ui-redesign/test_workshop_patch.py -v
```

Expected: all tests in `test_workshop_patch.py` pass.

### Task 4: Add behavior-oriented contract coverage

**Files:**
- Modify: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\test_workshop_patch.py`

**Interfaces:**
- Consumes: generated `js, css` from `patch_assets`.
- Produces: regression checks for event bridging, state mapping, friendly ENOSPC copy, and navigation visibility.

- [ ] **Step 1: Add assertions for event safety and state mapping**

Add these checks:

```python
self.assertIn('dispatchEvent(new MouseEvent("click"', js)
self.assertIn('shell.dataset.workshopState=state', js)
self.assertIn('shell.dataset.workshopTask=state==="idle"?"idle":"active"', js)
self.assertNotIn("hero.append(sourceButton)", js)
self.assertNotIn("button&&button.click()", js)
self.assertIn("ENOSPC|No space left", js)
self.assertIn("释放空间后重试", js)
```

- [ ] **Step 2: Run all unit tests**

Run:

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
```

Expected: every unit test passes.

### Task 5: Build, install, and verify the real APK flow

**Files:**
- Modify: generated assets under `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\generated\` via the build script.
- Build output: `C:\Users\王运\Documents\文件翻译\apk-work\slg-workshop-ui-signed.apk`
- QA screenshots: `C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\qa\`

**Interfaces:**
- Consumes: passing patch contract and existing base APK.
- Produces: signed, installable APK and evidence from ADB screenshot/UI hierarchy.

- [ ] **Step 1: Generate and build the signed APK**

Run:

```powershell
python apk-work/ui-redesign/build_workshop_apk.py
& '.tools/android-15/zipalign.exe' -c 4 apk-work/slg-workshop-ui-signed.apk
& '.tools/android-15/apksigner.bat' verify --verbose apk-work/slg-workshop-ui-signed.apk
```

Expected: zipalign succeeds; apksigner reports v2/v3 verification true.

- [ ] **Step 2: Install on the PEMM20 test device and capture idle state**

Run:

```powershell
$adb='.tools/platform-tools/adb.exe'
& $adb -s MZNRYXEQS859O7GU install -r apk-work/slg-workshop-ui-signed.apk
& $adb -s MZNRYXEQS859O7GU shell monkey -p com.slgtranslator.app 1
Start-Sleep -Seconds 2
& $adb -s MZNRYXEQS859O7GU exec-out screencap -p > apk-work/ui-redesign/qa/main-flow-idle.png
```

Verify visually: neutral surface, compact brand panel, one picker CTA, no API Key or logs, and visible Material navigation only on idle.

- [ ] **Step 3: Exercise selection and ready-state evidence**

Use the system picker to select a known APK fixture, wait for scanning to finish, then capture:

```powershell
& $adb -s MZNRYXEQS859O7GU exec-out screencap -p > apk-work/ui-redesign/qa/main-flow-ready.png
& $adb -s MZNRYXEQS859O7GU shell uiautomator dump /sdcard/main-flow.xml
& $adb -s MZNRYXEQS859O7GU shell cat /sdcard/main-flow.xml
```

Verify the hierarchy contains “发现 … 个可翻译文件” and “开始翻译”, while the task state has no visible bottom navigation.

- [ ] **Step 4: Verify the recoverable ENOSPC presentation**

Use the existing large-APK reproduction or the current partial-output fixture. Confirm the visible UI uses “手机空间不足” and “释放空间后重试”, while the raw `ENOSPC` message is only inside “处理详情”.

- [ ] **Step 5: Run final regression suite**

Run:

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
```

Expected: all unit and built-APK tests pass; the installed APK launches successfully.

## Self-review checklist

- Spec coverage: Tasks 2–3 cover the idle, scanning, ready, failed states; Task 3 covers event bridging and Back; Task 5 covers Android, insets, dark mode/reduced motion, and real-device verification.
- Placeholder scan: no unresolved placeholder markers or unspecified validation steps remain.
- Type consistency: `setWorkshopState(state, payload)`, `readTaskSnapshot()`, `triggerReactButton(button)`, and `patch_assets(js, css)` are named consistently across tasks.
- Scope: only the main-flow UI shell and state mapping are included; works/me and packaging architecture remain outside this plan as required by the spec.
