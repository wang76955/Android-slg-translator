# Android UI System And Animation Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有业务流程、数据结构、React 控件和 Java 桥接接口的前提下，完成 Android WebView 可见层的 Material 3 视觉、状态动画、列表反馈、性能降级和真机验收升级。

**Architecture:** 继续使用 `patch_workshop_ui.py` 生成注入到现有 React WebView 的可见层。通过稳定的任务壳层和局部节点更新表达任务状态，所有业务动作仍通过已有 React/Java 事件桥接触发；动画只使用 CSS 的 `opacity`、`transform` 和进度宽度变化，并由系统减少动画设置统一降级。

**Tech Stack:** Python 资源生成脚本、现有 React WebView runtime、原生 CSS 动画、Node.js 语法/行为契约测试、Python `unittest`、ADB、`dumpsys gfxinfo`、现有 APK zipalign/apksigner 构建链。

## Global Constraints

- 保留现有功能逻辑，不改变业务流程、数据结构、React 控件和 Java 插件接口。
- 不迁移到 Jetpack Compose，不把 Remotion 作为 APK 运行时动画依赖。
- 没有 DSN、隐私策略和网络策略时不强行接入 Sentry；只保留可插拔的验证边界。
- 继续保护当前工作区内用户已有的 Java、APK、截图、测试、文档和未跟踪资源，不回退、不清理、不覆盖无关文件。
- 动画普通交互不超过 400ms；优先 `transform`、`opacity` 和进度宽度，不动画大面积阴影、模糊或复杂布局高度。
- 低端设备优先保证稳定节点、少量阴影和有限动画；系统启用减少动画时必须提供即时或短淡入降级。
- 文件操作前确认目标路径，修改后运行真实测试和构建验证；同一种执行方式连续失败两次后停止重试并更换方案。

## File Map

- Modify: `apk-work/ui-redesign/test_workshop_patch.py` - 先增加状态映射、局部更新、重复状态、减少动画、列表行级状态和无障碍契约测试。
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py` - 调整 token、状态渲染、稳定 DOM、进度局部更新、状态转场、列表/存档行级动画和性能清理。
- Modify: `apk-work/ui-redesign/build_workshop_apk.py` - 仅在构建验收发现需要记录版本指纹或 QA 输出目录时做最小调整。
- Create or modify: `apk-work/ui-redesign/qa/` - 保存统一 APK 指纹、截图、UI dump、`gfxinfo` 和验收记录；不删除已有证据。
- Reference only: `docs/superpowers/specs/2026-08-09-android-ui-system-upgrade-design.md` - 设计和验收标准来源。

## Acceptance Criteria

- `python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v` 通过，既有 64 项契约测试和新增 UI/动画测试均为 0 失败。
- 生成的 JavaScript 通过 `node --input-type=module --check`，生成 CSS 包含浅色、深色、减少动画和响应式回退。
- 进度更新不调用任务壳层的整块 `replaceChildren`；重复 snapshot 不重播入场动画。
- 八个任务状态 `idle/scanning/empty/ready/translating/patching/completed/failed` 都有明确状态 class、可访问播报和主操作/恢复操作。
- 安装包、存档备份和下载归档支持新增、删除中、完成、失败保留和重试的行级可见反馈。
- 构建产物完成 zipalign、签名、签名验证、安装和启动检查；无法连接真机时必须明确记录未完成项，不把 60FPS、横屏或平板写成已验证。

## Execution Status (2026-08-10)

- Tasks 1-5: implementation and contract coverage are complete; the focused Workshop suite passes `92/92`.
- Task 6: an environment-limited candidate was rebuilt with a temporary verified baseline because `apk-work/com.slgtranslator.app-base.apk` is absent; the new signed APK SHA-256 is `099F371546151F9094BC386A587399FAE2BDF076F340E0DF6B7B4595BC594064`.
- Task 7: installation, cold launch, home/settings screenshots, settings open/close warm-start samples and raw `gfxinfo` reports are present. The complete business-state matrix, archive operations, large font, landscape, system reduced-motion and stable `<10%` settings gate remain unverified or blocked.
- Task 8: code/build/install verification is complete; independent `gpt-5.6-luna` animation review timed out and is recorded as unavailable. This plan is not marked fully complete while the remaining device gates are open.

---

### Task 1: Establish Red UI Contract Tests

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Test target: generated output from `patch_workshop_ui.patch_assets`

**Interfaces:**
- Consumes: existing `extract_js_function`, `extract_js_expression`, `BASE_JS`, and `BASE_CSS` helpers.
- Produces: executable contracts for stable task DOM, state-to-animation mapping, reduced motion, and row-level feedback.

- [ ] Add a test that extracts `setWorkshopState` and fails while it still rebuilds the whole task shell for every snapshot.
- [ ] Add a test that requires a stable progress node/update helper and verifies the shell/card identity is preserved during progress changes.
- [ ] Add a test for every task state and its `workshop-state-*` class, `aria-live` status, and action/recovery branch.
- [ ] Add a test that repeated snapshots with the same key skip rendering and do not restart the entrance animation.
- [ ] Add tests for `prefers-reduced-motion: reduce`, list row enter/leave/retry classes, archive row pending/error states, and 48dp icon-button labels.
- [ ] Run the focused test file and confirm each new test fails for the intended missing behavior before production edits.

### Task 2: Harden the Visual Token And Animation Foundation

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:28-265` (`WORKSHOP_CSS`)
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: existing `workshop-*` class names and state attributes.
- Produces: compatibility-first token CSS, state transition classes, motion reduction, responsive layout and row animation primitives.

- [ ] Replace the remaining decorative continuous shimmer with a finite/opt-in progress cue and add a `prefers-reduced-motion` override that disables shimmer, transforms and number counting.
- [ ] Add `workshop-state-enter`, `workshop-state-exit`, `workshop-row-enter`, `workshop-row-leave`, `workshop-row-pending`, and `workshop-row-error` classes using only compositor-friendly properties.
- [ ] Add explicit light/dark fallback declarations before advanced `oklch`/`color-mix` declarations and retain the existing olive-green semantic roles.
- [ ] Add responsive constraints for compact, expanded, landscape and large-font layouts without changing the task flow.
- [ ] Add accessible focus, disabled, live-status, icon-button and error-state styling while keeping touch targets at least 48dp.
- [ ] Run the new CSS contract tests and the generated JavaScript syntax check.

### Task 3: Convert Task State Rendering To Stable Local Updates

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:266-435` (`WORKSHOP_RUNTIME`)
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:1190-1260` (`enhance_runtime`)
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: existing `readTaskSnapshot`, `snapshotKey`, `renderTopbar`, `renderStateBody`, `retryTask`, `refresh`, and React bridge references.
- Produces: stable `task shell -> topbar/file summary/progress/detail/action` nodes, local progress/status update functions, and one-shot state transitions.

- [ ] Introduce a stable task shell structure with named regions for topbar, file summary, state content, progress, detail and actions while retaining the existing event bridge handlers.
- [ ] Split state rendering into initial mount and local update paths; state changes may replace only the state region, while translating/patching progress updates mutate text, width and live status in place.
- [ ] Track the previous state and animation key so identical states do not re-add entrance classes; apply fade-through only when the semantic state changes.
- [ ] Keep current task payload fields and recovery semantics unchanged, including scan, network, space and compatibility failures.
- [ ] Add `aria-live`/`aria-atomic` updates for task state and progress without duplicating announcements on every polling tick.
- [ ] Ensure scan clock, timers, observer scheduling and screen wake lock are released when leaving their owning state.
- [ ] Run the focused red-green tests, all workshop contract tests, and Node syntax validation.

### Task 4: Add Row-Level Feedback For Patches, Backups And Archives

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:558-670` (`patch_saves_runtime`)
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:300-435` (patch gallery/runtime rows)
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: existing `FileManager` plugin methods, save/restore/import/delete handlers and data fields.
- Produces: stable keyed row rendering with local pending/success/error state and retry actions.

- [ ] Render patch, save-backup and downloaded-archive rows with stable keys derived from existing path/name fields; do not rebuild unrelated rows for one operation.
- [ ] Add local pending state that disables only the active row and exposes an accessible busy label.
- [ ] Add finite enter/leave animations and remove a row only after successful native completion; preserve the row and show retry on failure.
- [ ] Preserve existing list-refresh fallback behavior, including retaining old content when refresh fails.
- [ ] Add archive import retry coverage that resends the original URI/package payload and only removes the successful row.
- [ ] Run focused save/archive tests plus the complete workshop test file.

### Task 5: Performance And Compatibility Guardrails

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify only if required: `apk-work/ui-redesign/build_workshop_apk.py`
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Consumes: stable runtime and row rendering from Tasks 3-4.
- Produces: bounded observer work, no redundant snapshots, no leaked listeners/wake locks, and generated assets ready for APK packaging.

- [ ] Keep a single debounced `MutationObserver` and coalesce refreshes through `requestAnimationFrame`.
- [ ] Verify `snapshotKey` excludes high-frequency fields from full-shell render decisions while local progress fields remain responsive.
- [ ] Ensure hidden legacy React content remains hidden during active task states without adding extra overlay layers.
- [ ] Add compatibility fallbacks for older WebView CSS capabilities and system font scaling.
- [ ] Run Python unit tests, JS syntax check, generated asset digest checks and a clean resource-generation invocation.

### Task 6: Build And Install The Candidate APK

**Files:**
- Generated only: `apk-work/ui-redesign/generated/index-CJtfdHOF.js`
- Generated only: `apk-work/ui-redesign/generated/index-C044IUg3.css`
- Output: `apk-work/slg-workshop-ui-unsigned.apk`, `apk-work/slg-workshop-ui-aligned.apk`, `apk-work/slg-workshop-ui-signed.apk`

**Interfaces:**
- Consumes: generated assets and current native scanner resources.
- Produces: zipaligned, signed, verifiable APK with a recorded SHA-256 fingerprint.

- [ ] Run `python apk-work/ui-redesign/build_workshop_apk.py` from `D:\文件翻译`.
- [ ] Run the existing `apksigner verify --verbose` step and record output plus APK SHA-256 under `apk-work/ui-redesign/qa/`.
- [ ] Install the signed APK on the connected device only after confirming the exact candidate path and package name.
- [ ] Launch the app, capture the initial screen and UI hierarchy, and record whether the device is connected and responsive.

### Task 7: Real-Device UI, Motion And Performance Acceptance

**Files:**
- Create or modify: `apk-work/ui-redesign/qa/2026-08-09-ui-upgrade-acceptance.md`
- Create: screenshots, XML UI dumps and `gfxinfo` evidence under `apk-work/ui-redesign/qa/` using unique names.

**Interfaces:**
- Consumes: signed APK from Task 6 and the design acceptance matrix.
- Produces: evidence-backed pass/blocked status for user-visible flows.

- [ ] Capture idle, source chooser, installed-app search, scanning, empty, ready, translating, patching, completed and failed states.
- [ ] Capture patch gallery, settings, save transfer, archive import/delete/retry, Android Back, dark mode, reduced motion, large font, landscape and expanded width where the device supports them.
- [ ] Run `adb shell dumpsys gfxinfo` around representative button, sheet, list and progress interactions; report frame timing against the 16.7ms budget without claiming unmeasured 60FPS.
- [ ] Check for duplicated overlays, repeated listeners, stale wake locks, flickering progress and hidden legacy content.
- [ ] Record any device limitation as blocked/untested rather than silently treating it as passed.

### Task 8: Final Review And Verification Gate

**Files:**
- Review: all modified files above
- Reference: `docs/superpowers/specs/2026-08-09-android-ui-system-upgrade-design.md`

- [ ] Run `python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v` fresh after all edits.
- [ ] Run generated asset syntax, digest, build and APK verification commands fresh after all edits.
- [ ] Run `oh-my-codex:code-review` against the diff, prioritizing regressions, business-flow changes, animation coverage gaps and performance risks.
- [ ] Reconcile every acceptance criterion with command output or QA evidence; list unverified items explicitly.
- [ ] Do not claim completion until tests, build, installation and required device evidence are all present; otherwise report the exact remaining blocker.
