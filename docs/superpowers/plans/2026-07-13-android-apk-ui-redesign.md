# Android APK Player Workshop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改写已验证翻译内核的前提下，将现有 Capacitor APK 重设计为面向普通玩家的“玩家工坊”安卓界面，并安装到已连接的 PEMM20 手机上验收。

**Architecture:** 保留 `com.slgtranslator.app-base.apk` 的 Capacitor 容器、本地桥接、Ren'Py 扫描器和 APK 打包逻辑。用一个幂等 Python 补丁从干净基线 JS/CSS 生成新界面资源，再通过可重复构建脚本替换资源、zipalign、签名和验证。真机上使用 ADB 安装、启动、截图和测试核心交互。

**Tech Stack:** Python 3，打包后的 React/Tailwind WebView 资源，Capacitor Android，Android Build Tools 35 (`zipalign`, `apksigner`)，ADB，PowerShell。

## Global Constraints

- 平台为 Android，紧凑屏幕使用 Material 3 底部导航，任务页正确支持系统返回。
- 首版只支持 DeepSeek，API Key 仅保存在本机，不在 UI 日志中显示完整密钥。
- 浅色和深色主题默认跟随系统，正文至少达到 WCAG AA，触控目标不小于 48dp。
- 主流程为选择 APK、扫描、翻译确认、翻译/打包和完成。
- 完成页突出“立即安装”，同时提供“保存 APK”。
- 任务需要支持暂停、继续和应用重启后恢复；本次 UI 实现不得破坏现有恢复内核。
- 动画仅表达状态，时长 150–250ms，并响应 `prefers-reduced-motion`。
- 不使用玻璃拟态、渐变文字、侧边色条、堆叠 FAB 或全屏技术日志。

---

### Task 1: Freeze a clean UI baseline and add patch contract tests

**Files:**
- Create: `apk-work/ui-redesign/baseline/index-CJtfdHOF.js`
- Create: `apk-work/ui-redesign/baseline/index-C044IUg3.css`
- Create: `apk-work/ui-redesign/test_workshop_patch.py`
- Create: `apk-work/ui-redesign/patch_workshop_ui.py`

**Interfaces:**
- Consumes: `apk-work/extracted/assets/public/assets/index-CJtfdHOF.js` and `index-C044IUg3.css` as the currently working v16 asset baseline.
- Produces: `patch_assets(js: str, css: str) -> tuple[str, str]`, used by all later build steps.

- [ ] **Step 1: Copy the verified v16 assets into the immutable baseline directory**

Run:

```powershell
New-Item -ItemType Directory -Force apk-work\ui-redesign\baseline
Copy-Item apk-work\extracted\assets\public\assets\index-CJtfdHOF.js apk-work\ui-redesign\baseline\index-CJtfdHOF.js
Copy-Item apk-work\extracted\assets\public\assets\index-C044IUg3.css apk-work\ui-redesign\baseline\index-C044IUg3.css
```

Expected: both baseline files exist and their SHA-256 values remain stable across repeated UI builds.

- [ ] **Step 2: Write the failing patch contract test**

Create `apk-work/ui-redesign/test_workshop_patch.py` with:

```python
from pathlib import Path
from patch_workshop_ui import patch_assets

ROOT = Path(__file__).parent


def test_patch_contains_workshop_contract():
    js = (ROOT / "baseline" / "index-CJtfdHOF.js").read_text("utf-8")
    css = (ROOT / "baseline" / "index-C044IUg3.css").read_text("utf-8")
    patched_js, patched_css = patch_assets(js, css)
    required_copy = [
        "让喜欢的故事，用中文继续。",
        "选择 APK 文件",
        "处理详情",
        "立即安装",
        "保存 APK",
    ]
    for copy in required_copy:
        assert copy in patched_js
    required_css = [
        "--workshop-primary",
        "prefers-color-scheme:dark",
        "prefers-reduced-motion:reduce",
        "min-height:48px",
    ]
    compact = patched_css.replace(" ", "").replace("\n", "")
    for token in required_css:
        assert token in compact


def test_patch_is_deterministic():
    js = (ROOT / "baseline" / "index-CJtfdHOF.js").read_text("utf-8")
    css = (ROOT / "baseline" / "index-C044IUg3.css").read_text("utf-8")
    assert patch_assets(js, css) == patch_assets(js, css)
```

- [ ] **Step 3: Run the contract test and verify it fails**

Run:

```powershell
python -m unittest discover -s apk-work\ui-redesign -p "test_*.py" -v
```

Expected: FAIL because `patch_workshop_ui` or `patch_assets` does not exist.

- [ ] **Step 4: Add the minimal deterministic patch module**

Create `apk-work/ui-redesign/patch_workshop_ui.py` with the following public structure; subsequent tasks fill the replacement lists:

```python
from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_assets(js: str, css: str) -> tuple[str, str]:
    patched_js = js
    patched_css = css + "\n/* workshop-ui */\n"
    return patched_js, patched_css


def main() -> None:
    root = Path(__file__).parent
    js, css = patch_assets(
        (root / "baseline" / "index-CJtfdHOF.js").read_text("utf-8"),
        (root / "baseline" / "index-C044IUg3.css").read_text("utf-8"),
    )
    output = root / "generated"
    output.mkdir(exist_ok=True)
    (output / "index-CJtfdHOF.js").write_text(js, "utf-8")
    (output / "index-C044IUg3.css").write_text(css, "utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the test and confirm only the not-yet-implemented visual contract fails**

Run: `python -m unittest discover -s apk-work\ui-redesign -p "test_*.py" -v`

Expected: deterministic test PASS; copy/token assertions FAIL and enumerate the missing workshop strings.

- [ ] **Step 6: Commit the baseline and tests**

```powershell
git add apk-work/ui-redesign
git commit -m "test: define workshop UI patch contract"
```

Expected: commit succeeds after repository-local Git identity is configured.

### Task 2: Implement the Player Workshop shell, themes, and navigation

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: `replace_once(text, old, new, label)` and the frozen v16 bundle.
- Produces: generated JS/CSS containing the home shell, responsive bottom navigation, light/dark semantic tokens, safe-area handling, 48px targets, and reduced-motion rules.

- [ ] **Step 1: Extend the failing test with shell requirements**

Add to `test_workshop_patch.py`:

```python
def test_shell_has_three_destinations_and_safe_areas():
    js = (ROOT / "baseline" / "index-CJtfdHOF.js").read_text("utf-8")
    css = (ROOT / "baseline" / "index-C044IUg3.css").read_text("utf-8")
    patched_js, patched_css = patch_assets(js, css)
    for label in ["首页", "作品", "我的"]:
        assert label in patched_js
    assert "env(safe-area-inset-top)" in patched_css
    assert "env(safe-area-inset-bottom)" in patched_css
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run: `python -m unittest discover -s apk-work\ui-redesign -p "test_workshop_patch.py" -v`

Expected: FAIL on missing destination labels and safe-area tokens.

- [ ] **Step 3: Add semantic workshop CSS tokens and platform rules**

Append exactly one `WORKSHOP_CSS` block from `patch_assets`:

```python
WORKSHOP_CSS = r"""
:root{--workshop-bg:oklch(1 0 0);--workshop-surface:oklch(.965 .004 95);--workshop-ink:oklch(.22 .018 112);--workshop-muted:oklch(.46 .025 108);--workshop-primary:oklch(.36 .082 120);--workshop-on-primary:oklch(.98 .004 95);--workshop-accent:oklch(.84 .145 84);--workshop-on-accent:oklch(.24 .035 84);color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--workshop-bg:oklch(.11 0 0);--workshop-surface:oklch(.17 .012 112);--workshop-ink:oklch(.94 .008 95);--workshop-muted:oklch(.72 .018 105);--workshop-primary:oklch(.72 .10 120);--workshop-on-primary:oklch(.14 .025 120);--workshop-accent:oklch(.78 .13 84);--workshop-on-accent:oklch(.16 .025 84)}}
html,body,#root{min-height:100%;background:var(--workshop-bg);color:var(--workshop-ink)}
.workshop-app{min-height:100dvh;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom);background:var(--workshop-bg)}
.workshop-surface{background:var(--workshop-surface);border-radius:20px}
.workshop-primary{min-height:48px;background:var(--workshop-primary);color:var(--workshop-on-primary);border-radius:16px}
.workshop-touch{min-width:48px;min-height:48px}
.workshop-bottom-nav{padding-bottom:max(8px,env(safe-area-inset-bottom))}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
"""
```

- [ ] **Step 4: Replace the v16 dashboard header/stepper with the workshop home shell**

Use `replace_once` against exact fragments discovered in the frozen baseline. The replacement must contain the following stable UI contract so later tests do not depend on minified variable names:

```javascript
<header aria-label="Patch屋"><p>今天翻译什么？</p><h1>让喜欢的故事，用中文继续。</h1></header>
<nav aria-label="主导航"><button aria-current="page">首页</button><button>作品</button><button>我的</button></nav>
```

Preserve the existing file-picker callback and all existing state variables; only replace presentation markup and class strings.

- [ ] **Step 5: Run tests and generate assets twice to prove determinism**

```powershell
python -m unittest discover -s apk-work\ui-redesign -p "test_*.py" -v
python apk-work\ui-redesign\patch_workshop_ui.py
$first=(Get-FileHash apk-work\ui-redesign\generated\index-CJtfdHOF.js).Hash
python apk-work\ui-redesign\patch_workshop_ui.py
$second=(Get-FileHash apk-work\ui-redesign\generated\index-CJtfdHOF.js).Hash
if($first -ne $second){throw 'UI patch is not deterministic'}
```

Expected: all tests PASS and both hashes match.

- [ ] **Step 6: Commit the shell and theme**

```powershell
git add apk-work/ui-redesign
git commit -m "feat: add player workshop shell and themes"
```

### Task 3: Implement guided task states and completion actions

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: existing bundle state for selected APK, scan results, translation progress, logs, generated APK, install callback, and resume mode.
- Produces: five guided states with stable Chinese copy, an expandable diagnostics area, pause/resume affordance, and completion actions wired to existing callbacks.

- [ ] **Step 1: Add failing tests for every state and action**

```python
def test_guided_flow_copy_and_actions_are_present():
    js = (ROOT / "baseline" / "index-CJtfdHOF.js").read_text("utf-8")
    css = (ROOT / "baseline" / "index-C044IUg3.css").read_text("utf-8")
    patched_js, _ = patch_assets(js, css)
    for label in [
        "选择 APK 文件", "正在查找剧情文本", "开始翻译",
        "暂停", "继续翻译", "正在生成汉化 APK",
        "汉化完成", "立即安装", "保存 APK", "处理详情",
    ]:
        assert label in patched_js
```

- [ ] **Step 2: Verify the new test fails**

Run: `python -m unittest discover -s apk-work\ui-redesign -p "test_*.py" -v`

Expected: FAIL with the first missing guided-flow label.

- [ ] **Step 3: Map existing state variables into five visible task stages**

In `patch_assets`, replace the current operational cards with one `section` selected by existing conditions:

```javascript
!selectedApk ? "select" :
scanning ? "scan" :
result ? "complete" :
translating ? "translate" :
"confirm"
```

Each branch must render one heading, one explanatory sentence, one primary action, and no more than one secondary action. The scan and translate branches use `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, and `aria-valuemax="100"`.

- [ ] **Step 4: Reuse existing install/save/resume handlers**

Wire visible controls to the existing minified callbacks found in the baseline:

```javascript
onClick:installPatchedApk       // 立即安装
onClick:savePatchedApk          // 保存 APK；若基线只有文件导出，绑定该导出回调
onClick:pauseTranslation        // 暂停；绑定现有任务中止/快照入口
onClick:resumeTranslation       // 继续翻译；绑定现有 resume 入口
```

Do not invent a native call. The verified v16 bundle currently exposes `Te` for install, `we` for uninstall-and-install, `Ee` for opening game settings, `De` for launching the game, `Ce` for starting work, `se` for the running flag, `T` for the result, and `_mode` for resume/scan/full mode. Record these identifiers beside the replacement table and assert each complete callback fragment occurs exactly once before patching. Implement “保存 APK” by calling the existing Capacitor Filesystem `writeFile` path already present in the bundle, passing the generated result represented by `T`; do not add a new native bridge method.

- [ ] **Step 5: Fold logs into an accessible details section**

Render verbose output only inside:

```html
<details class="workshop-details">
  <summary class="workshop-touch">处理详情</summary>
  <div role="log" aria-live="polite"></div>
</details>
```

Never insert API Key text into this log container.

- [ ] **Step 6: Run all patch tests**

Run: `python -m unittest discover -s apk-work\ui-redesign -p "test_*.py" -v`

Expected: PASS for deterministic patching, theme/shell contract, all five task stages, completion actions, and details section.

- [ ] **Step 7: Commit the guided flow**

```powershell
git add apk-work/ui-redesign
git commit -m "feat: add guided APK translation flow"
```

### Task 4: Build, align, sign, and statically verify the APK

**Files:**
- Create: `apk-work/ui-redesign/build_workshop_apk.py`
- Create: `apk-work/ui-redesign/test_built_apk.py`
- Generate: `apk-work/slg-workshop-ui-unsigned.apk`
- Generate: `apk-work/slg-workshop-ui-aligned.apk`
- Generate: `apk-work/slg-workshop-ui-signed.apk`

**Interfaces:**
- Consumes: generated JS/CSS, `com.slgtranslator.app-base.apk`, the currently verified `classes6.dex`, local Android Build Tools, and the existing signing key configuration used by v16/v17.
- Produces: a zipaligned and signed APK installable as `com.slgtranslator.app`.

- [ ] **Step 1: Write a failing built-APK verification test**

```python
import zipfile
from pathlib import Path

APK = Path(__file__).parents[1] / "slg-workshop-ui-signed.apk"


def test_signed_apk_contains_workshop_assets():
    assert APK.exists()
    with zipfile.ZipFile(APK) as archive:
        js = archive.read("assets/public/assets/index-CJtfdHOF.js").decode("utf-8")
        css = archive.read("assets/public/assets/index-C044IUg3.css").decode("utf-8")
        assert "让喜欢的故事，用中文继续。" in js
        assert "--workshop-primary" in css
        assert archive.getinfo("resources.arsc").compress_type == zipfile.ZIP_STORED
```

- [ ] **Step 2: Run the test and verify it fails because the APK does not exist**

Run: `python -m unittest discover -s apk-work\ui-redesign -p "test_built_apk.py" -v`

Expected: FAIL at `assert APK.exists()`.

- [ ] **Step 3: Implement the deterministic APK replacement builder**

`build_workshop_apk.py` must:

1. call `patch_workshop_ui.main()`;
2. copy every base APK member while preserving `ZipInfo.external_attr`;
3. replace both generated web assets and the verified `classes6.dex`;
4. store `resources.arsc` and all `.dex` entries uncompressed;
5. write `slg-workshop-ui-unsigned.apk`;
6. invoke `zipalign -f -p 4`;
7. invoke `apksigner sign` with the same keystore and alias used by the last working APK;
8. invoke `apksigner verify --verbose --print-certs` and fail on a nonzero exit code.

Use `subprocess.run([...], check=True)` with argument arrays. Do not construct shell command strings containing credentials.

- [ ] **Step 4: Build and verify the signed APK**

```powershell
$env:JAVA_HOME=(Resolve-Path '.tools\jdk-17\jdk-17.0.19+10')
python apk-work\ui-redesign\build_workshop_apk.py
python -m unittest discover -s apk-work\ui-redesign -p "test_built_apk.py" -v
& '.tools\android-15\zipalign.exe' -c -v 4 apk-work\slg-workshop-ui-signed.apk
& '.tools\android-15\apksigner.bat' verify --verbose --print-certs apk-work\slg-workshop-ui-signed.apk
```

Expected: build exits 0, unit test PASS, zipalign verification successful, and APK Signature Scheme verification reports at least v2 as true.

- [ ] **Step 5: Commit build automation without generated APK binaries**

```powershell
git add apk-work/ui-redesign/build_workshop_apk.py apk-work/ui-redesign/test_built_apk.py
git commit -m "build: package and verify workshop APK"
```

### Task 5: Install to PEMM20 and perform phone acceptance testing

**Files:**
- Generate: `apk-work/ui-redesign/qa/home-light.png`
- Generate: `apk-work/ui-redesign/qa/home-dark.png`
- Generate: `apk-work/ui-redesign/qa/task-progress.png`
- Generate: `apk-work/ui-redesign/qa/completion.png`
- Create: `apk-work/ui-redesign/qa/acceptance.md`

**Interfaces:**
- Consumes: `.tools/platform-tools/adb.exe`, signed APK, connected device serial `MZNRYXEQS859O7GU` (`PEMM20`).
- Produces: installed app plus screenshot and interaction evidence for the design acceptance criteria.

- [ ] **Step 1: Confirm the intended device and back up current package metadata**

```powershell
$adb='.tools\platform-tools\adb.exe'
& $adb -s MZNRYXEQS859O7GU get-state
& $adb -s MZNRYXEQS859O7GU shell dumpsys package com.slgtranslator.app | Select-String 'versionName|versionCode|firstInstallTime|lastUpdateTime'
```

Expected: `device`, model PEMM20, and existing package metadata if installed.

- [ ] **Step 2: Install the signed APK and launch it**

```powershell
$adb='.tools\platform-tools\adb.exe'
& $adb -s MZNRYXEQS859O7GU install -r apk-work\slg-workshop-ui-signed.apk
& $adb -s MZNRYXEQS859O7GU shell am force-stop com.slgtranslator.app
& $adb -s MZNRYXEQS859O7GU shell monkey -p com.slgtranslator.app -c android.intent.category.LAUNCHER 1
```

Expected: `Success`; app launches without a crash dialog.

- [ ] **Step 3: Capture the light-theme home screen and inspect startup logs**

```powershell
New-Item -ItemType Directory -Force apk-work\ui-redesign\qa
& $adb -s MZNRYXEQS859O7GU exec-out screencap -p > apk-work\ui-redesign\qa\home-light.png
& $adb -s MZNRYXEQS859O7GU logcat -d -t 300 | Select-String 'FATAL EXCEPTION|AndroidRuntime|Capacitor'
```

Expected: screenshot shows the workshop headline, one dominant APK selection action, and three bottom destinations; logs contain no app-process fatal exception.

- [ ] **Step 4: Test system dark theme and capture evidence**

```powershell
& $adb -s MZNRYXEQS859O7GU shell cmd uimode night yes
Start-Sleep -Seconds 1
& $adb -s MZNRYXEQS859O7GU exec-out screencap -p > apk-work\ui-redesign\qa\home-dark.png
& $adb -s MZNRYXEQS859O7GU shell cmd uimode night no
```

Expected: the app switches to the semantic dark palette; text, buttons, dividers, and system bars remain readable.

- [ ] **Step 5: Exercise the file picker and guided flow on the phone**

Manually tap “选择 APK 文件”, choose a known small test APK already on the device, and verify:

- system file picker opens;
- chosen file summary is visible;
- scanning state uses a linear progress indicator;
- confirmation page shows detected text count before DeepSeek requests;
- invalid or absent API Key routes to settings without deleting the task;
- processing details remain collapsed by default.

Capture `task-progress.png` after reaching the task state.

- [ ] **Step 6: Verify completion actions using an existing completed task or controlled small fixture**

Reach the completion page and confirm:

- “立即安装” is the filled primary action;
- “保存 APK” is simultaneously visible;
- denying unknown-app permission does not delete the generated file;
- returning from Android settings resumes installation;
- reopening the app retains the task/result.

Capture `completion.png`.

- [ ] **Step 7: Record acceptance results**

Create `qa/acceptance.md` with a row for each Global Constraint and the evidence filename or command output. Mark a row PASS only after direct observation; list any failure with the exact screen and reproduction steps.

- [ ] **Step 8: Run final verification**

```powershell
python -m unittest discover -s apk-work\ui-redesign -p "test_*.py" -v
& '.tools\android-15\zipalign.exe' -c -v 4 apk-work\slg-workshop-ui-signed.apk
& '.tools\android-15\apksigner.bat' verify --verbose apk-work\slg-workshop-ui-signed.apk
& '.tools\platform-tools\adb.exe' -s MZNRYXEQS859O7GU shell pidof com.slgtranslator.app
```

Expected: tests PASS, alignment/signature checks exit 0, and `pidof` returns a live process ID.

- [ ] **Step 9: Commit QA evidence and hand off the installed build**

```powershell
git add apk-work/ui-redesign/qa
git commit -m "test: verify workshop UI on PEMM20"
```

Report the installed APK path, device model/serial, test results, and clickable screenshot paths.
