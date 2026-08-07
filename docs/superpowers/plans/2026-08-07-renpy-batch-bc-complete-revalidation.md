# Ren'Py 批次 B/C 完整重验实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先消除 `test_workshop_patch.py` 与当前产品行为之间的全部不一致，再从 Task 6 开始逐项重验批次 B/C，并以机器测试、APK 构建、真实游戏和真机证据完成 Task 16 发布收口。

**Architecture:** 把历史提交视为候选实现，以“原要求 → 当前接口 → 可执行测试 → 构建产物 → 外部证据”形成不可跳步的证据链。先建立基线和根因清单，再按职责修复 workshop 契约，随后逐项重验 Task 6–15，最后由 Task 16 汇总自动化、APK 和设备证据；任何阶段门禁失败时不得进入下一阶段。

**Tech Stack:** Python 3 `unittest`、Node.js JavaScript 行为夹具、Java/Android Capacitor 插件、Android D8/build-tools、APK zipalign/apksigner、Ren'Py RPYC/RPA 受限解析与写入、Markdown/JSON 证据文件、Git。

## Global Constraints

- 权威设计：`docs/superpowers/specs/2026-08-07-renpy-batch-bc-complete-revalidation-design.md`。
- 原始要求：`docs/superpowers/plans/2026-08-07-renpy-app-compatibility-optimization.md`；Task 6–16 的每个 Step 都必须映射到证据台账。
- 现有提交只表示候选实现，不表示当前验收通过。
- 顺序固定：Phase 0 → Phase 1 → Task 6 → … → Task 16 → 发布审计；当前门禁未通过时不得推进。
- 每个失败先完成 `superpowers:systematic-debugging` Phase 1 根因调查；每个代码修复使用 `superpowers:test-driven-development` 红—绿流程。
- 禁止通过删除安全断言、改成永真断言、复制乱码或把异常吞掉来获得绿色测试。
- `PASS` 需要当前、直接、可重复的证据；缺少真实样本或设备时使用 `NOT-RUN`，不得推断为通过。
- 没有真实完整 Ren'Py APK/语料时，coverage audit 可以显式 skip，但不得声明 `missing == 0`。
- 没有真机证据时，安装、启动、语言激活、字体显示、旧存档和 rollback 保持 `NOT-RUN`，发布状态保持“未批准”。
- 高级 dialogue ID 模式默认关闭；缺少真实 rollback 证据时必须回退全局 string map。
- 不移植完整 Ren'Py 解释器，不扩大未知 AST/pickle/RPA 的写入范围。
- 源 APK 固定为 `apk-work/github-source/slg-translator-android-rpyc-v12.apk`，GitHub commit 固定为 `fc2e3f39f85a09799e63fa652e566e3850ff9f31`，SHA-256 固定为 `44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104`；发现不一致立即停止。
- 禁止 `git add .`、`git add -A`、`git reset --hard`、全量 checkout 和清理无关未跟踪文件。
- 只能显式暂存当前任务路径；每次提交后必须确认以下用户文件仍处于暂存状态：`PRODUCT.md`、`docs/superpowers/plans/2026-07-13-apk-main-flow-redesign-v2.md`、`docs/superpowers/specs/2026-07-13-android-apk-ui-redesign-design.md`、`docs/superpowers/specs/2026-07-13-apk-main-flow-redesign-v2-design.md`。
- 子智能体仅在用户授权时创建；任何新子智能体模型不得高于 `gpt-5.6-luna`。子智能体报告必须由主智能体检查 diff 并重跑验证。
- 每个任务完成前使用 `superpowers:verification-before-completion`；测试输出、APK 哈希、签名结果和设备证据必须来自当前任务回合。

## File Responsibility Map

| Path | Responsibility |
|---|---|
| `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md` | 当前计划的任务状态、命令、结果、提交和阻塞条件 |
| `docs/qa/renpy-revalidation-baseline.md` | 工具版本、Git/APK 指纹、完整测试基线和工作树边界 |
| `docs/qa/renpy-workshop-failure-inventory.md` | 26 个 workshop 问题的稳定复现、根因、权威行为和红—绿证据 |
| `docs/qa/renpy-batch-bc-evidence.md` | Task 6–16 每项原要求的 `PASS`/`FAIL`/`NOT-RUN` 证据映射 |
| `docs/qa/renpy-compatibility-matrix.md` | 引擎、RPA/RPYC、激活模式、字体、APK 形态和文本类别矩阵 |
| `docs/qa/renpy-release-checklist.md` | 自动化、构建、真实游戏和真机发布门禁 |
| `apk-work/ui-redesign/test_workshop_patch.py` | 当前 bundle/patch 的可执行 UI、状态机、缓存、网络和存档契约 |
| `apk-work/ui-redesign/patch_workshop_ui.py` | 唯一允许修改的前端 patch 生成逻辑；不得直接手改 generated bundle |
| `apk-work/ui-redesign/test_fast_scanner.py` | Java scanner/writer/preflight/split/dialogue fixture 与 DEX 契约 |
| `apk-work/ui-redesign/test_translation_quality.py` | 语境、缓存、lint 和编译门禁契约 |
| `apk-work/ui-redesign/test_translation_coverage.py` | 覆盖率、真实 fixture 跳过规则和发布文档机器断言 |
| `apk-work/ui-redesign/test_engine_performance.py` | 并发、批处理、缓存写入和性能契约 |
| `apk-work/ui-redesign/test_built_apk.py` | APK 资产一致性、zipalign、签名、manifest 和 DEX 归属 |
| `apk-work/native-fast-scan/src/com/slgtranslator/app/*.java` | Ren'Py 受限解析、校验、编译、预检、字体、split 和安装实现 |
| `apk-work/native-fast-scan/build_fast_scanner.py` | Java 编译和 D8 helper DEX 生成 |
| `apk-work/ui-redesign/build_workshop_apk.py` | 最终 workshop APK 构建、对齐和签名 |

---

## Phase 0：冻结完整重验基线

### Task 0：建立基线、进度台账和证据状态模型

**Files:**
- Create: `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`
- Create: `docs/qa/renpy-revalidation-baseline.md`
- Create: `docs/qa/renpy-batch-bc-evidence.md`
- Modify: `apk-work/ui-redesign/test_translation_coverage.py`
- Reference: `docs/superpowers/plans/2026-08-07-renpy-app-compatibility-optimization.md`

**Interfaces:**
- Consumes: Git HEAD/status、固定 APK 指纹、Python/Java/Node/Android 工具版本、`unittest discover` 输出。
- Produces: 稳定状态值 `PASS | FAIL | NOT-RUN`；证据行字段 `requirementId/sourceRequirement/implementation/automatedTest/command/status/artifact/residualRisk/commit`；后续所有任务共用的基线。

- [ ] **Step 1：验证源 APK 和 GitHub 指纹**

Run from repository root:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'apk-work/github-source/slg-translator-android-rpyc-v12.apk'
git rev-parse HEAD
git status --short --branch
```

Expected: APK 哈希精确等于全局约束中的值；状态中四个用户文档保持 `A`；无任务文件被意外修改。

- [ ] **Step 2：记录工具链版本**

Run:

```powershell
python --version
java -version
node --version
Get-Command adb,apksigner,zipalign -ErrorAction SilentlyContinue | Select-Object Name,Source
```

Expected: `docs/qa/renpy-revalidation-baseline.md` 逐项记录实际输出；找不到的外部工具写 `NOT-RUN` 和恢复命令，不写成通过。

- [ ] **Step 3：运行并记录当前完整测试基线**

Run from `apk-work/ui-redesign`:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Expected at plan start: `167` tests、`25 failures`、`1 error`、`1 skipped`。若数字变化，记录当前真实数字和新增/消失的测试名；不要沿用旧数字。

- [ ] **Step 4：创建证据台账头部和状态约束**

Write this exact table header to `docs/qa/renpy-batch-bc-evidence.md`:

```markdown
| requirementId | sourceRequirement | implementation | automatedTest | command | status | artifact | residualRisk | commit |
|---|---|---|---|---|---|---|---|---|
```

Initialize Task 6–16 rows as `NOT-RUN`; do not copy “complete” from the old progress ledger.

- [ ] **Step 5：增加证据状态机器断言**

Add to `test_translation_coverage.py`:

```python
import re

def test_revalidation_evidence_uses_only_explicit_statuses(self):
    evidence = (ROOT / "docs/qa/renpy-batch-bc-evidence.md").read_text(encoding="utf-8")
    self.assertIn("| requirementId |", evidence)
    statuses = re.findall(r"\|\s*(PASS|FAIL|NOT-RUN)\s*\|", evidence)
    self.assertGreaterEqual(len(statuses), 11)
    self.assertNotIn("assumed-pass", evidence.lower())
    self.assertNotIn("missing = 0 (inferred)", evidence.lower())
```

- [ ] **Step 6：运行基线文档测试**

Run:

```powershell
python -m unittest test_translation_coverage.TranslationCoverageLogicTest.test_revalidation_evidence_uses_only_explicit_statuses -v
```

Expected: PASS，且测试只验证证据状态真实性，不要求外部设备已经存在。

- [ ] **Step 7：提交 Phase 0 文档和机器断言**

```powershell
git add -- '.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md' 'docs/qa/renpy-revalidation-baseline.md' 'docs/qa/renpy-batch-bc-evidence.md' 'apk-work/ui-redesign/test_translation_coverage.py'
git commit --only -m 'test: freeze renpy complete revalidation baseline' -- '.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md' 'docs/qa/renpy-revalidation-baseline.md' 'docs/qa/renpy-batch-bc-evidence.md' 'apk-work/ui-redesign/test_translation_coverage.py'
git diff --cached --name-status
```

Expected: 只提交四个任务路径，用户原有四个暂存文档仍存在。

---

## Phase 1：完全对齐 `test_workshop_patch.py`

### Task 1：建立 26 项失败根因清单和稳定 JavaScript 夹具边界

**Files:**
- Create: `docs/qa/renpy-workshop-failure-inventory.md`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Read: `apk-work/ui-redesign/patch_workshop_ui.py`

**Interfaces:**
- Consumes: 49-test workshop 输出和 `patch_workshop_ui.patch_assets(js, css)`。
- Produces: 26 行根因记录；测试辅助函数 `extract_js_function(source: str, signature: str) -> str`，通过括号/字符串感知扫描提取函数，替代易碎的 `str.index(next_function)`。

- [ ] **Step 1：保存精确失败清单**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m unittest test_workshop_patch.py -q 2>&1 | ForEach-Object {
  $line=[string]$_
  if ($line -match '^(FAIL|ERROR):' -or $line -match '^Ran ' -or $line -match '^FAILED') { $line }
}
```

Expected: 25 个 `FAIL`、1 个 `ERROR`。把测试名逐项写入清单，不粘贴数 MB 的压缩 bundle dump。

- [ ] **Step 2：为根因清单建立固定字段**

Each row must contain:

```markdown
### WSP-01 `test_name`
- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_name -v`
- First effective failure: `exact first error`
- Expected behavior: `current approved behavior`
- Observed behavior: `runtime observation`
- Authority: `spec section or production interface`
- Classification: `PRODUCT_REGRESSION | STALE_CONTRACT | BRITTLE_EXTRACTION | ENCODING_BOUNDARY | FIXTURE_GAP | EXTERNAL`
- Change set: `exact paths`
- Red evidence: `command + failure`
- Green evidence: `command + pass`
```

- [ ] **Step 3：先为函数提取器写失败测试**

Add this module-level helper to `test_workshop_patch.py` outside the test class:

```python
def extract_js_function(source: str, signature: str) -> str:
    raise NotImplementedError
```

Add this method inside `WorkshopPatchContractTest`:

```python
    def test_extract_js_function_ignores_braces_inside_strings_and_templates(self):
        source = 'function target(){const a="}";const b=`x${1}`;if(true){return `{ok}`}}\nfunction next(){}'
        block = extract_js_function(source, "function target()")
        self.assertEqual(block, 'function target(){const a="}";const b=`x${1}`;if(true){return `{ok}`}}')
```

- [ ] **Step 4：运行并确认红灯**

Run:

```powershell
python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_extract_js_function_ignores_braces_inside_strings_and_templates -v
```

Expected: ERROR with `NotImplementedError`.

- [ ] **Step 5：实现字符串、转义和模板感知函数提取器**

Implement a single-pass scanner that starts at `signature`, tracks `{}` depth, quote mode (`'`, `"`, `` ` ``), backslash escaping and template `${...}` nesting, and returns exactly when outer depth returns to zero. Raise `AssertionError` if signature is absent or braces never close.

- [ ] **Step 6：运行提取器测试和语法测试**

```powershell
python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_extract_js_function_ignores_braces_inside_strings_and_templates test_workshop_patch.WorkshopPatchContractTest.test_patched_javascript_is_syntactically_valid -v
```

Expected: 2 tests PASS.

- [ ] **Step 7：只提交清单骨架和稳定提取器**

```powershell
git add -- 'docs/qa/renpy-workshop-failure-inventory.md' 'apk-work/ui-redesign/test_workshop_patch.py'
git commit --only -m 'test: inventory workshop failures with stable js extraction' -- 'docs/qa/renpy-workshop-failure-inventory.md' 'apk-work/ui-redesign/test_workshop_patch.py'
```

### Task 2：修复完成页、空扫描、恢复会话和动画状态簇

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify only if root cause is product: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `docs/qa/renpy-workshop-failure-inventory.md`

**Interfaces:**
- Consumes: generated JS functions `readTaskSnapshot()`, `renderStateBody(state,payload)`, `recoveryBanner(savedAt)`, `refresh()` and `snapshotKey(s)`.
- Produces: settled zero-entry scan → `empty`; interrupted translating session → visible recovery banner; dismiss clears `SESSION_KEY` and forces render; active phases disable entrance replay.

Tests in this cluster:

```text
test_completed_zero_entry_scan_is_an_empty_result_not_scanning
test_dismiss_recovery_banner_re_renders_immediately
test_task_runtime_bridges_and_recovery_contract
test_translating_state_does_not_replay_card_entrance_animation
test_translation_heartbeat_updates_session
```

- [ ] **Step 1：逐个运行五个测试并完成根因字段**

Run each exact test with `-v`. Expected: each reproduces the baseline failure before edits; record the first effective failure rather than the final assertion dump.

- [ ] **Step 2：把片段提取改为 `extract_js_function`**

Replace each `js.index("function readTaskSnapshot...")`/manual end marker slice in this cluster with:

```python
snapshot = extract_js_function(js, "function readTaskSnapshot()")
render = extract_js_function(js, "function renderStateBody(state,payload)")
refresh = extract_js_function(js, "function refresh()")
```

Expected: test harness executes the complete current function and no longer truncates at an obsolete next-function marker.

- [ ] **Step 3：保留新完成提示行为**

The completed-state contract must assert:

```text
selectable → 提示进入游戏语言设置选择译文，并允许切回原文
always_on → 提示译文启动即生效，不能声称游戏内可切回原文
custom menu → 明确说明无法通过标准语言菜单选择
```

Do not restore old generic “翻译完成即成功” copy.

- [ ] **Step 4：仅在行为夹具证明产品回归时修改 patch**

Required state transitions:

```javascript
settled && fileCount === 0 && !fatalError  // state: "empty"
savedSession.translating === true          // recovery banner eligible
dismiss                                // remove SESSION_KEY, reset sessionRestoredAt, invalidate snapshot, refresh
state in translating|patching          // no entrance animation replay
```

If current patch already satisfies a transition after complete extraction, update only stale test expectations and classify `STALE_CONTRACT` or `BRITTLE_EXTRACTION`.

- [ ] **Step 5：运行职责组**

```powershell
python -m unittest `
  test_workshop_patch.WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning `
  test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately `
  test_workshop_patch.WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract `
  test_workshop_patch.WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation `
  test_workshop_patch.WorkshopPatchContractTest.test_translation_heartbeat_updates_session -v
```

Expected: 5 PASS.

- [ ] **Step 6：提交状态簇**

Stage only files actually changed and commit message `fix: align workshop completion and recovery states`.

### Task 3：修复应用来源、共享 loader、请求 epoch 和 Android 返回簇

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify only for proven runtime defects: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `docs/qa/renpy-workshop-failure-inventory.md`

**Interfaces:**
- Consumes: `window.__slgLoadSelectedApk(selection)`, `window.__slgSelectionMeta`, installed list epoch, selection epoch, loader deadline and modal back handling.
- Produces: latest request wins；stale resolve/reject cannot overwrite current state；file fallback remains available；selection preserves `uri/baseUri/splitUris/splitNames/packageName/versionCode`。

Tests:

```text
test_installed_app_source_chooser_contract
test_installed_list_and_selection_epochs_ignore_stale_requests
test_shared_loader_has_deadline_and_stale_safe_settlement
test_source_modals_handle_android_back_focus_and_file_fallback
```

- [ ] **Step 1：稳定复现并记录四个首错**

Expected baseline observations include stale request ordering and fallback action mismatches; classify only after executing each Node harness.

- [ ] **Step 2：将选择对象契约固定为完整 SourceSet**

The test fixture must compare this shape:

```javascript
{
  uri, baseUri, splitUris, splitNames,
  splitCount, packageName, versionCode,
  source: "installed" | "file"
}
```

Object identity may be preserved during initial selection, but refreshed metadata may replace the object only if all fields above survive.

- [ ] **Step 3：用可控 deferred Promise 验证 epoch**

Create two list requests and two selection requests; resolve the older request last. Assert only the newest request changes visible list/selection and stale rejection does not render failure.

- [ ] **Step 4：验证 loader deadline 与 modal back**

Use fake timers to cross the exact configured deadline; assert a stable failed state exposes both retry and file fallback. Verify Android back consumes only visible source/installed dialogs and restores focus to the opener.

- [ ] **Step 5：运行职责组和 loader 语法契约**

Run the four tests plus `test_shared_apk_loader_and_installed_selection_behavior` and `test_patched_javascript_is_syntactically_valid`.

Expected: 6 PASS.

- [ ] **Step 6：提交 loader 簇**

Commit message: `fix: align workshop source loader and request epochs`.

### Task 4：修复致命网络错误、批次终止和禁止部分产物簇

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify if behavior is wrong: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `docs/qa/renpy-workshop-failure-inventory.md`

**Interfaces:**
- Consumes: remote batch request loop、outer file controller、fatal network classification、write/package bridge。
- Produces: fatal provider/network error is terminal；不递归拆分重试；不继续后续文件；不写部分文件；不调用 `buildPatchedApk`；visible state is `failed/network`。

Tests:

```text
test_network_failures_stop_batches_without_recursive_splitting
test_fatal_network_stops_outer_file_controller
test_partial_network_failure_never_writes_or_packages
test_network_failure_preempts_stale_translating_ui
```

- [ ] **Step 1：分别复现四个失败并追踪 error 数据流**

Trace: provider rejection → batch handler → file controller → write decision → build decision → `readTaskSnapshot()`。记录 fatal marker 在哪一层丢失或夹具在哪一层截断。

- [ ] **Step 2：收紧行为测试**

Use counters:

```javascript
let requestCalls=0, writeCalls=0, buildCalls=0, completedFiles=0;
```

After the first fatal rejection assert:

```javascript
requestCalls === 1
writeCalls === 0
buildCalls === 0
completedFiles === 0
snapshot.state === "failed"
snapshot.reason === "network"
```

- [ ] **Step 3：修复夹具中的未定义控制变量**

The baseline `ReferenceError: _maxDone is not defined` is a fixture defect unless `_maxDone` is read by production code. Define all harness-owned counters before evaluating extracted production functions; do not add `_maxDone` to production solely to satisfy the fixture.

- [ ] **Step 4：仅在追踪证明终止信号未传播时修改产品**

The minimal product fix must preserve one terminal error object through every layer and check it before write and package. Do not add recursive splitting for network errors.

- [ ] **Step 5：运行四个测试及性能回归**

```powershell
python -m unittest `
  test_workshop_patch.WorkshopPatchContractTest.test_network_failures_stop_batches_without_recursive_splitting `
  test_workshop_patch.WorkshopPatchContractTest.test_fatal_network_stops_outer_file_controller `
  test_workshop_patch.WorkshopPatchContractTest.test_partial_network_failure_never_writes_or_packages `
  test_workshop_patch.WorkshopPatchContractTest.test_network_failure_preempts_stale_translating_ui `
  test_engine_performance.py -v
```

Expected: all tests PASS; performance batching remains bounded.

- [ ] **Step 6：提交网络终止簇**

Commit message: `fix: stop workshop output after fatal translation failures`.

### Task 5：修复缓存、设置、可见 shell、日志和进度簇

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify if proven: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `docs/qa/renpy-workshop-failure-inventory.md`

**Interfaces:**
- Consumes: `slg-file-v1:` cache key、provider/model/custom endpoint settings、visible shell state、progress log mirror。
- Produces: identical file/source reuses validated translation cache across model selection；settings propagate to React/local engine；long phases are not mislabeled as directory scan；progress starts before request and mirrors into shell。

Tests:

```text
test_translation_cache_is_reused_across_models
test_settings_support_provider_model_and_custom_endpoint
test_patch_contains_player_workshop_contract
test_patch_installs_visible_android_shell
test_long_running_phases_are_not_reported_as_directory_scanning
test_translation_logs_are_mirrored_into_the_visible_shell
test_translation_progress_emits_starting_batch_before_request
```

- [ ] **Step 1：修复缓存测试的过时定位前提**

Stop searching for removed `slg-translator-cache:v2:`. Extract and execute current cache key logic, asserting prefix `slg-file-v1:` and that model/provider changes do not invalidate a validated file translation when source identity and text are unchanged.

- [ ] **Step 2：对设置使用行为夹具而非乱码静态文本**

Set provider, model and custom endpoint through current controls, call the bridge, and assert exact values reach settings storage and translation invocation. Chinese labels must be valid UTF-8 literals or Unicode escapes representing the intended text.

- [ ] **Step 3：固定 shell 和进度语义**

Assert:

```text
directory enumeration → scanning
translation request → translating
RPYC compilation/APK merge/sign → patching
fatal network → failed/network
settled success → completed
```

Assert “正在处理批次 1/N” appears before the first request and visible shell mirrors the latest log without replaying completed logs as active work.

- [ ] **Step 4：运行七个测试和 known/performance 回归**

Run the seven exact tests, `test_known_bugfixes.py`, `test_engine_performance.py`, and `test_translation_quality.py`.

Expected: zero failures; current cache namespace remains compatible with Task 8/10 rules.

- [ ] **Step 5：提交 UI/cache/progress 簇**

Commit message: `fix: align workshop cache settings and progress contracts`.

### Task 6：修复存档导入、导出和游戏选择隔离簇

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify if proven: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify if native bridge is wrong: `apk-work/native-fast-scan/src/com/slgtranslator/app/SaveTransfer.java`
- Modify: `docs/qa/renpy-workshop-failure-inventory.md`

**Interfaces:**
- Consumes: save-game app list、export selection、import selection、shared archive picker、settings visibility/state gate。
- Produces: save export and import selections are independent；import accepts only the selected archive and target game；actions disabled while conflicting task active；native errors are visible and do not corrupt selection。

Tests:

```text
test_save_transfer_settings_runtime_contract
test_save_transfer_runtime_actions_and_state_gating
test_save_transfer_can_pick_game_from_installed_apps
test_save_transfer_can_import_shared_archive
test_save_and_import_game_selection_are_independent
```

- [ ] **Step 1：逐个执行并区分 UI 夹具和 native bridge 根因**

If a failure occurs before any plugin method call, classify UI/fixture. If plugin input is wrong, compare with `SaveTransfer` public contract before changing Java.

- [ ] **Step 2：固定独立状态对象**

The executable harness must maintain distinct values:

```javascript
saveExportGamePackage
saveImportGamePackage
saveImportArchiveUri
```

Changing import target must not change export target and vice versa.

- [ ] **Step 3：验证活动任务门禁**

During `scanning|translating|patching`, save transfer actions remain disabled or return an explicit busy error; opening/closing settings must restore prior idle state without restarting translation.

- [ ] **Step 4：运行五个 workshop 测试和 native save tests**

Run the five exact tests plus these scanner contracts:

```text
test_save_game_list_scans_renpy_save_dirs_without_all_apps
test_save_export_zips_directory_and_counts_files
test_save_import_extracts_shared_archive_safely
test_delete_backup_removes_directory_tree
```

Expected: 9 PASS.

- [ ] **Step 5：提交存档簇**

Commit message: `fix: align save transfer selection and runtime gates`.

### Task 7：修复 RPYC 文本换行/编码契约并关闭 Phase 1

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify only if product conversion is wrong: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `docs/qa/renpy-workshop-failure-inventory.md`
- Modify: `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

**Interfaces:**
- Consumes: `RPYC_STRING` bridge encoding, literal `\n`, real newline, backslash and Unicode text。
- Produces: literal backslash-n and actual newline remain distinguishable through extraction → UI → translation → compile path。

Tests:

```text
test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines
test_rpyc_protocol_escapes_backslashes_before_newlines
test_patched_javascript_is_syntactically_valid
```

- [ ] **Step 1：建立四值 round-trip 表**

Use exact inputs:

```python
["Line one\\nLine two", "Line one\nLine two", "C:\\game\\script", "中文「测试」"]
```

Assert each decoded output equals its own input and no pair collapses to the same value.

- [ ] **Step 2：定位编码边界**

Trace bytes/strings at native protocol emission、JavaScript parsing、cache key and compile request. Fix the first layer that conflates values; do not add compensating double-unescape later in the flow.

- [ ] **Step 3：运行编码职责组**

Run the three tests above. Expected: 3 PASS.

- [ ] **Step 4：运行整个 workshop 文件**

```powershell
python -m unittest test_workshop_patch.py -v
```

Expected: `Ran 50 tests` or more（Task 1 added one helper test），`OK`，零失败、零错误。

- [ ] **Step 5：运行 Phase 1 全量回归**

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Expected: no failures/errors. The single real-audit skip may remain only if its external fixture is absent and the skip reason is explicit.

- [ ] **Step 6：完成 26 行根因清单**

Every WSP row must have classification, red command/result, green command/result and exact changed paths. No row may remain without a status.

- [ ] **Step 7：提交 Phase 1 收口**

Commit message: `test: close workshop behavior revalidation gate`.

---

## Phase 2：完整重验批次 B（原 Task 6–12）

### Task 8：重验原 Task 6——结构化 Ren'Py 文本记录

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTextRecord.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: `RpycTextExtractor.extractRecords(byte[] rpyc, String sourcePath, boolean onlyOld)`。
- Produces: `RenpyTextRecord{text,kind,speaker,identifier,sourcePath,sourceLine,occurrence,coverageCertain}`；旧 `extractTexts` API 保持兼容。

- [ ] **Step 1：将原 Task 6 的 Step 1–5 建立 requirement IDs `B06-01`…`B06-05`**

Map each requirement to exact Java fields/methods and existing tests.

- [ ] **Step 2：运行结构化记录专项测试**

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_rpyc_extractor_returns_structured_records_without_breaking_text_api `
 test_fast_scanner.FastApkScannerContractTest.test_fast_scanner_reads_translation_entries_in_old_only_mode `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_compatibility_accumulate_uses_all_read_records -v
```

Expected: 3 PASS; repeated/cross-kind occurrences retain distinct source metadata.

- [ ] **Step 3：增加缺失 speaker 泄漏的对抗夹具（若现有测试未直接覆盖）**

Create two consecutive dialogue nodes, first with speaker `alice`, second without speaker. Assert second record speaker is empty, not `alice`.

- [ ] **Step 4：运行 scanner 全文件和完整 discover**

Expected: scanner and discover zero failures/errors.

- [ ] **Step 5：更新证据并提交**

Set `B06-*` to `PASS` only with current command output; commit message `test: revalidate structured renpy text records`.

### Task 9：重验原 Task 7——官方标记字符串和精确键

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: `_()`, `__()`, `___()`, `_p()` source call forms and legal string prefixes。
- Produces: exact `{#...}` key preservation、triple-quote boundary correctness、dynamic-call uncertainty diagnostics。

- [ ] **Step 1：建立 `B07-01`…`B07-05` 映射**

- [ ] **Step 2：运行官方形式、前缀、三引号和精确键测试**

Run:

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_rpyc_extractor_matches_official_marked_string_forms `
 test_fast_scanner.FastApkScannerContractTest.test_rpyc_extractor_accepts_legal_prefixes_and_keeps_triple_quote_boundaries `
 test_fast_scanner.FastApkScannerContractTest.test_rpyc_extractor_preserves_exact_marked_string_keys_and_dynamic_uncertainty -v
```

Expected: 3 PASS; `Save{#slot}` and `Save{#menu}` remain separate keys.

- [ ] **Step 3：运行 scanner/discover 并更新证据**

- [ ] **Step 4：提交**

Commit message: `test: revalidate official renpy marked strings`.

### Task 10：重验原 Task 8——语境碰撞、出现次数和缓存身份

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTranslationCorpus.java`
- Modify only if evidence fails: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_translation_quality.py`
- Test: `apk-work/ui-redesign/test_translation_coverage.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: `RenpyTranslationCorpus.build(List<RenpyTextRecord>)`, exact old text, all occurrences and contextual candidates。
- Produces: unique/occurrence/duplicate/collision counts；最多三个代表语境；相同 old 的不同译文在编译前失败；缓存 identity 保留 `{#...}`。

- [ ] **Step 1：建立 `B08-01`…`B08-06` 映射**

- [ ] **Step 2：运行 corpus、UI 报告、编译冲突和 cache namespace 测试**

```powershell
python -m unittest `
 test_translation_quality.TranslationQualityPatchTest.test_task8_java_corpus_keeps_occurrences_and_only_marks_context_collisions `
 test_translation_quality.TranslationQualityPatchTest.test_task8_prompt_limits_contexts_and_compile_rejects_conflicting_translations `
 test_translation_quality.TranslationQualityPatchTest.test_task8_ui_report_renders_counts_and_sanitizes_export `
 test_translation_quality.TranslationQualityPatchTest.test_keypath_prefix_and_cache_namespace_compatibility `
 test_translation_coverage.TranslationCoverageLogicTest.test_task8_collision_report_has_unique_old_occurrences_and_contexts -v
```

Expected: 5 PASS.

- [ ] **Step 3：增加 `{#slot}`/`{#menu}` 缓存隔离行为断言**

Execute current cache key builder with both exact olds; assert keys differ and neither strips the disambiguator before cache/compile.

- [ ] **Step 4：运行 quality/coverage/workshop/discover**

- [ ] **Step 5：更新证据并提交**

Commit message: `test: revalidate renpy context collision semantics`.

### Task 11：重验原 Task 9——占位符、标签、插值和 printf 双门禁

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTextValidator.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Modify only if evidence fails: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_translation_quality.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: old/new translation pair, sentinel sequence, Ren'Py tags, `[expression]`, `%(name)s`, `%s`, `%d`, `%1$s`。
- Produces: deterministic validation result/error code；model acceptance gate and compile gate both reject invalid translations。

- [ ] **Step 1：建立 `B09-01`…`B09-06` 映射**

- [ ] **Step 2：运行 validator 和 compile gate tests**

```powershell
python -m unittest `
 test_translation_quality.TranslationQualityPatchTest.test_task9_compile_gate_rejects_invalid_translation_before_rpyc `
 test_fast_scanner.FastApkScannerContractTest.test_local_llm_placeholder_guard_preserves_markup_and_format -v
```

Expected: 2 PASS.

- [ ] **Step 3：增加完整拒绝矩阵**

For each token family, test missing、extra、duplicate、order swap、crossed tags and residual sentinel. Add one valid translation per family. Assert rejected pairs never reach `TranslationCompiler.compileTranslationArtifact` output.

- [ ] **Step 4：运行 quality/scanner/workshop/discover**

- [ ] **Step 5：更新证据并提交**

Commit message: `test: revalidate renpy translation lint gates`.

### Task 12：重验原 Task 10——覆盖率、分类、增量缓存和构建门禁

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCoverageReport.java`
- Modify only if evidence fails: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_translation_coverage.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: complete records、validator-approved map、rejected set、uncertain set、classification reasons、collision candidates。
- Produces: exact missing/rejected/translated/uncertain/collision/file counts；`missingCount > 0 || rejectedCount > 0` blocks full patch；explicit incomplete patch remains visibly warned。

- [ ] **Step 1：建立 `B10-01`…`B10-06` 映射**

- [ ] **Step 2：运行 Java report、UI gate、state reset and fixture honesty tests**

```powershell
python -m unittest `
 test_translation_coverage.TranslationCoverageLogicTest.test_task10_java_report_counts_validated_rejected_collision_uncertain_and_files `
 test_translation_coverage.TranslationCoverageLogicTest.test_task10_ui_coverage_gate_and_sanitized_report_are_wired `
 test_translation_coverage.TranslationCoverageLogicTest.test_task10_ui_coverage_preserves_exact_text_and_resets_all_state `
 test_translation_coverage.TranslationCoverageLogicTest.test_task10_missing_fixture_never_becomes_fake_zero -v
```

Expected: 4 PASS.

- [ ] **Step 3：验证真实 fixture 分支**

If configured fixture exists, run `test_audit_pins_the_verified_missing_set` and require PASS with exact `missing == 0`. If absent, require the explicit skip text `audit APK/extracted texts not present`, set evidence `NOT-RUN`, and keep release unapproved.

- [ ] **Step 4：验证 incomplete test patch 文案不消失**

Execute coverage render with one missing item, select incomplete mode, re-render completed state, and assert warning remains visible and no “完整翻译” success claim appears.

- [ ] **Step 5：运行 coverage/workshop/discover**

- [ ] **Step 6：更新证据并提交**

Commit message: `test: revalidate renpy coverage and build gates`.

### Task 13：重验原 Task 11——中文字体覆盖和东亚断行

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyFontSupport.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: `RenpyFontSupport.codePointsOfTranslations`, `inspect(Context,File,Set<Integer>)`, split-aware merged font reports。
- Produces: candidate list、best font、required/covered/missing code points、Chinese style and line-break evidence；final missing glyphs block release。

- [ ] **Step 1：建立 `B11-01`…`B11-06` 映射**

- [ ] **Step 2：运行 glyph、style rewrite、reset 和 split merge tests**

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_font_report_detects_missing_translation_glyphs `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_style_font_rewrite_rebuilds_rpc2_and_supports_schinese `
 test_fast_scanner.FastApkScannerContractTest.test_font_preflight_state_resets_when_scan_selection_starts `
 test_fast_scanner.FastApkScannerContractTest.test_split_scan_uses_split_template_and_merges_all_font_preflights -v
```

Expected: 4 PASS.

- [ ] **Step 3：验证基线检查和译文终检使用不同 required sets**

The final check must derive code points from accepted translations, not only the fixed baseline set. Assert a Chinese character absent from baseline but present in translation appears in `missingCodePoints` when no candidate covers it.

- [ ] **Step 4：运行 scanner/workshop/discover**

- [ ] **Step 5：更新证据并提交**

Commit message: `test: revalidate renpy font and line break gates`.

### Task 14：重验原 Task 12——统一预检、固定诊断和 UI 门禁

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify only if evidence fails: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: `RenpyPreflight.SourceSet` and `RenpyPreflight.inspect(Context, SourceSet)`。
- Produces: `SAFE | WARNING | EXTRACT_ONLY | UNSUPPORTED`、activation strategy、template/source counts、font report and sanitized issues before any model call。

- [ ] **Step 1：建立 `B12-01`…`B12-05` 映射**

- [ ] **Step 2：运行三类报告、UI 顺序和 extract-only gate tests**

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_compatibility_report_ui_order_fields_and_sanitized_export `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_extract_only_compatibility_gate_blocks_before_model `
 test_fast_scanner.FastApkScannerContractTest.test_renpy_font_preflight_is_before_first_model_call_and_read_bridge_returns_gate -v
```

Expected: 4 PASS.

- [ ] **Step 3：增加 unsupported snapshot**

Use missing/invalid source set and assert `UNSUPPORTED + NONE`, stable issue code, no model call, and extraction/build actions reflect the documented boundary.

- [ ] **Step 4：运行 scanner/workshop/discover**

- [ ] **Step 5：完成批次 B 审计**

All `B06-*` through `B12-*` rows must be current `PASS`, except real fixture/device-only rows may be `NOT-RUN` with release still unapproved.

- [ ] **Step 6：提交**

Commit message: `test: close renpy batch b complete revalidation`.

---

## Phase 3：独立重验批次 C（原 Task 13–15）

### Task 15：重验原 Task 13——Python 2 / protocol 2 受限 writer

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`
- Modify: `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

**Interfaces:**
- Consumes: `RpycPickleWriter.Dialect.PY2_PROTOCOL_2`、verified template meta、language/filename/pairs。
- Produces: protocol-2-compatible pickle/RPYC；independent non-executing object-graph reader verification；unknown/adversarial structures remain extract-only；modern output remains byte-stable。

- [ ] **Step 1：建立 `C13-01`…`C13-06` requirement rows**

Map writer separation、Python 2 opcode set、independent reader、capability matrix and regression command to original Step 1–6.

- [ ] **Step 2：运行 golden、protocol 2 和 adversarial tests**

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_modern_writer_is_byte_stable_with_existing_translation_pickle `
 test_fast_scanner.FastApkScannerContractTest.test_protocol2_writer_uses_only_python2_compatible_opcodes `
 test_fast_scanner.FastApkScannerContractTest.test_protocol2_generation_support_matrix_is_verified_or_extract_only `
 test_fast_scanner.FastApkScannerContractTest.test_protocol2_adversarial_object_graph_stays_extract_only -v
```

Expected: 4 PASS. No Python `pickle.loads`, Java object deserialization or execution of GLOBAL targets is allowed in the verifier.

- [ ] **Step 3：验证 always-on language is nullable**

Build a protocol-2 always-on artifact and assert language is pickle `NONE`, output path is `tl/None`, and selectable behavior remains `slgtranslated`.

- [ ] **Step 4：运行 scanner/workshop/discover**

Expected: zero failures/errors; modern golden remains byte-for-byte stable.

- [ ] **Step 5：构建 helper DEX 并检查 writer ownership**

```powershell
python 'apk-work/native-fast-scan/build_fast_scanner.py'
```

Expected: command succeeds via D8 response file; generated DEX contains one `RpycPickleWriter` definition and no duplicate class.

- [ ] **Step 6：更新证据并独立提交 Task 13**

Commit message: `test: revalidate restricted protocol2 writer`。不得与 Task 14 或 Task 15 合并提交。

### Task 16：重验原 Task 14——Split APK 扫描、签名和单 session 安装

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledApkSet.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledAppSource.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/PackageInstallerSupport.java`
- Modify only if evidence fails: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: `InstalledApkSet.fromUris(baseUri, splitUris, packageName, versionCode, splitNames)` and `PackageInstallerSupport.installApkSet(Context, InstalledApkSet, PluginCall)`。
- Produces: immutable base+split set；atomic private copies；per-ZIP scan with source ownership；merged template/font result；package/version/split/signature validation；base then splits in one installer session。

- [ ] **Step 1：建立 `C14-01`…`C14-06` requirement rows**

- [ ] **Step 2：运行 immutable set、metadata、scan、font、fail-closed 和 install tests**

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_split_apk_set_is_immutable_and_rejects_duplicate_or_missing_parts `
 test_fast_scanner.FastApkScannerContractTest.test_installed_split_names_come_from_manifest_metadata_not_file_names `
 test_fast_scanner.FastApkScannerContractTest.test_split_apk_set_scans_assets_and_installs_in_one_session `
 test_fast_scanner.FastApkScannerContractTest.test_split_scan_uses_split_template_and_merges_all_font_preflights `
 test_fast_scanner.FastApkScannerContractTest.test_split_scanning_and_reading_fail_closed_instead_of_base_only_fallback `
 test_fast_scanner.FastApkScannerContractTest.test_split_ui_preserves_collection_metadata_through_scan_read_compile_and_install -v
```

Expected: 6 PASS.

- [ ] **Step 3：增加 session abandon 对抗测试**

For package mismatch、version mismatch、duplicate splitName、signature mismatch and write failure, assert validation happens before commit and the session is abandoned. Assert write order is `base.apk` followed by declared split order.

- [ ] **Step 4：验证 patch location decision**

Use one fixture where template exists in base and one where it exists only in a split. Assert the report identifies `sourceApk`; if loose-file loader visibility from base cannot be proven, patch the owning split and sign all outputs with the same key.

- [ ] **Step 5：运行 scanner/workshop/discover and rebuild helper**

Expected: zero failures/errors and helper DEX contains `InstalledApkSet`, `InstalledAppSource`, `FastApkScanner`, `PackageInstallerSupport` exactly once.

- [ ] **Step 6：记录真实设备状态**

If a real split target and Android device are unavailable, set the device row to `NOT-RUN` with the exact missing condition. Fixture PASS must not change the real-device row to `PASS`.

- [ ] **Step 7：独立提交 Task 14**

Commit message: `test: revalidate complete split apk lifecycle`.

### Task 17：重验原 Task 15——高级 dialogue ID 模式和回退边界

**Files:**
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialogueTranslation.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Modify only if evidence fails: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- Modify only if evidence fails: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: verified `Say/TranslateSay` identifier records；`RpycPickleWriter.isDialogueIdWriterVerified(Dialect,int)`；capability fields `extractor/writer/astVersion/rollback`。
- Produces: context-specific dialogue translations only for verified modern AST version；menus/character/UI remain string map；duplicate identifier with different old fails closed；mode defaults off。

- [ ] **Step 1：建立 `C15-01`…`C15-06` requirement rows**

- [ ] **Step 2：运行 dialogue fixture and default-off tests**

```powershell
python -m unittest `
 test_fast_scanner.FastApkScannerContractTest.test_dialogue_id_mode_preserves_context_specific_translations `
 test_workshop_patch.WorkshopPatchContractTest.test_ready_mode_selector_and_completed_language_guidance -v
```

Expected: context-specific fixture PASS；advanced mode remains disabled unless every capability flag is true.

- [ ] **Step 3：增加 unsafe identifier and AST version matrix**

Test empty、oversized、whitespace/code-like identifiers, protocol 2, modern version other than `17`, and duplicate ID mapping to different old text. Every case must return extract-only/global-map fallback and must not emit dialogue AST.

- [ ] **Step 4：验证 mixed translation path**

Fixture must contain dialogue、menu、character name and marked UI string. Assert only verified dialogue IDs enter `dialogueTranslations`; all non-dialogue records remain in the global string map and are not dropped.

- [ ] **Step 5：运行 scanner/workshop/discover and helper build**

Expected: automated tests zero failures/errors; helper DEX contains `RenpyDialogueTranslation` and verified writer classes once.

- [ ] **Step 6：执行真实测试游戏存档矩阵或保持 fail-closed**

Required device checks:

```text
new game → translated dialogue
old save load → success
rollback → correct prior text/context
jump → correct target context
selectable → translated and original both selectable
always-on → translated on launch and completion copy accurate
```

If any row is unavailable or fails, set `C15-05` to `NOT-RUN`/`FAIL`, keep `__slgDialogueIdMode=false`, and do not approve advanced mode.

- [ ] **Step 7：独立提交 Task 15**

Commit message: `test: revalidate dialogue id mode rollback boundary`.

- [ ] **Step 8：关闭批次 C 自动化门禁**

Run full scanner, workshop and discover suites. All automated rows must pass. Device-only rows may remain `NOT-RUN`, but then Phase 4 release approval remains blocked.

---

## Phase 4：Task 16 发布级测试、构建和真实设备矩阵

### Task 18：重建 Task 16 机器矩阵和完成定义

**Files:**
- Modify: `docs/qa/renpy-compatibility-matrix.md`
- Modify: `docs/qa/renpy-release-checklist.md`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`
- Modify: `apk-work/ui-redesign/test_translation_coverage.py`
- Modify: `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`

**Interfaces:**
- Consumes: current Task 6–15 evidence, test results and external statuses。
- Produces: matrix rows for engine generation、archive/compiled format、activation、font、APK shape and text category；release status derived from evidence rather than manually asserted。

- [ ] **Step 1：建立 `C16-01`…`C16-06` rows**

Map minimum sample matrix、expected fields、full automated tests、APK build、device smoke and final gate to original Task 16 Step 1–6.

- [ ] **Step 2：update matrix rows without inventing results**

Every row must include support level、activation strategy、template/source、unique/occurrence/collision counts、missing/rejected、font result、build/install/startup/save result and evidence reference. Unknown external outcomes stay `not-run`.

- [ ] **Step 3：strengthen document contract test**

Update `test_task16_matrix_and_release_checklist_cover_every_gate` to assert:

```python
for token in (
    "SAFE", "WARNING", "EXTRACT_ONLY", "UNSUPPORTED",
    "single APK", "base + split", "selectable", "always-on",
    "missing == 0", "old save", "rollback", "NOT-RUN",
):
    self.assertIn(token, matrix + checklist)
```

Also assert the release checklist cannot contain `当前状态：批准发布` while any mandatory row is `FAIL` or `NOT-RUN`.

- [ ] **Step 4：运行 Task 16 documentation tests**

```powershell
python -m unittest `
 test_translation_coverage.TranslationCoverageLogicTest.test_task16_matrix_and_release_checklist_cover_every_gate `
 test_fast_scanner.FastApkScannerContractTest.test_task16_release_artifacts_and_unsupported_gate_are_pinned -v
```

Expected: 2 PASS.

- [ ] **Step 5：提交 machine matrix update**

Commit message: `test: rebuild renpy release evidence matrix`.

### Task 19：运行完整自动化门禁

**Files:**
- Modify only to fix proven regressions: task-scoped source/test files
- Modify: `docs/qa/renpy-release-checklist.md`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: all automated tests from Tasks 0–18。
- Produces: current pass/fail counts and exact skip reasons；zero hidden failures。

- [ ] **Step 1：运行 Python 语法检查**

```powershell
python -m py_compile patch_workshop_ui.py test_workshop_patch.py test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py test_built_apk.py
```

Expected: exit 0.

- [ ] **Step 2：运行 workshop gate**

```powershell
python -m unittest test_workshop_patch.py -v
```

Expected: zero failures/errors.

- [ ] **Step 3：运行 scanner gate**

```powershell
python -m unittest test_fast_scanner.py -v
```

Expected: zero failures/errors.

- [ ] **Step 4：运行 quality/coverage/performance gate**

```powershell
python -m unittest test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

Expected: zero failures/errors; only the explicitly documented real-fixture skip may remain.

- [ ] **Step 5：运行完整 discover**

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Expected: zero failures/errors. Record exact total and every skip; any unexpected skip blocks this task.

- [ ] **Step 6：更新证据并提交**

Commit message: `test: pass renpy complete automated release gate`。只有本回合完整输出为绿色时才能使用此提交信息。

### Task 20：重建 helper DEX 和最终 APK

**Files:**
- Modify only if build defect is proven: `apk-work/native-fast-scan/build_fast_scanner.py`
- Modify only if build defect is proven: `apk-work/ui-redesign/build_workshop_apk.py`
- Build inputs: `apk-work/native-fast-scan/src/com/slgtranslator/app/*.java`
- Test: `apk-work/ui-redesign/test_built_apk.py`
- Modify: `docs/qa/renpy-release-checklist.md`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`

**Interfaces:**
- Consumes: current Java sources and current `patch_workshop_ui.py` output。
- Produces: helper DEX、aligned/signed workshop APK、SHA-256、V2/V3 signature evidence and unique class ownership。

- [ ] **Step 1：重建 helper DEX**

```powershell
python 'apk-work/native-fast-scan/build_fast_scanner.py'
```

Expected: exit 0; D8 uses build-local response file and does not hit Windows command-line length limit.

- [ ] **Step 2：检查 required classes**

Use `dexdump` on generated DEX and require exactly one definition for:

```text
FastApkScanner
RenpyTextRecord
RenpyTextValidator
TranslationCoverageReport
RenpyCompatibilityReport
RenpyPreflight
RenpyPatchValidator
RpycPickleWriter
InstalledApkSet
InstalledAppSource
PackageInstallerSupport
RenpyDialogueTranslation
```

- [ ] **Step 3：重建 workshop APK**

Run from `apk-work/ui-redesign`:

```powershell
python build_workshop_apk.py
```

Expected: exit 0 and output `apk-work/slg-workshop-ui-signed.apk`.

- [ ] **Step 4：运行 built APK tests**

```powershell
python -m unittest test_built_apk.py -v
```

Expected: assets exactly match current patch output；zipalign PASS；V2/V3 signatures PASS；manifest and DEX ownership PASS。

- [ ] **Step 5：记录 APK fingerprint and signature output**

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '..\slg-workshop-ui-signed.apk'
apksigner verify --verbose --print-certs '..\slg-workshop-ui-signed.apk'
```

Record current SHA-256; never copy a previous build hash.

- [ ] **Step 6：提交 build evidence documents only**

Do not commit generated APK/DEX unless repository policy already tracks that exact artifact. Commit checklist/evidence updates with message `test: record renpy release build artifacts`.

### Task 21：执行真实游戏静态审计

**Files:**
- Modify: `docs/qa/renpy-compatibility-matrix.md`
- Modify: `docs/qa/renpy-release-checklist.md`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`
- Optional local fixtures: user-provided real APK and extracted corpus; do not commit proprietary game content

**Interfaces:**
- Consumes: at least one real Ren'Py game APK/corpus for each claimed generation/activation/APK shape。
- Produces: sanitized preflight、coverage、font and validator reports；no game text or personal data in committed evidence。

- [ ] **Step 1：登记样本而不提交受版权保护内容**

For each sample record package hash、engine generation、Python generation、single/split shape and why it covers a matrix row. Do not record raw dialogue.

- [ ] **Step 2：运行 scan/preflight/coverage**

Save sanitized fields:

```text
supportLevel, activationStrategy, templatePath,
uniqueTextCount, occurrenceCount, collisionCount,
missingCount, rejectedCount, uncertainCount,
font.requiredCount, font.coveredCount, font.missingCodePoints
```

- [ ] **Step 3：enforce complete/incomplete distinction**

Full patch requires `missingCount == 0`, `rejectedCount == 0`, no unresolved collision and final font missing set empty. Otherwise only an explicitly selected incomplete test patch is allowed and the matrix remains non-release.

- [ ] **Step 4：validate generated RPYC before merge**

Require `RenpyPatchValidator.Result.valid == true`, stable code `ok`, expected pair count, version and language before APK merge.

- [ ] **Step 5：处理缺少真实样本的情况**

If no legal real sample is available, set affected rows to `NOT-RUN`, record the exact needed sample characteristics, and continue to Task 22 only to document the device blocker. Do not mark Task 21 `PASS`.

- [ ] **Step 6：提交 sanitized evidence**

Commit message: `test: record real renpy game audit evidence` only when no proprietary text/APK is staged.

### Task 22：执行真机端到端矩阵

**Files:**
- Modify: `docs/qa/renpy-compatibility-matrix.md`
- Modify: `docs/qa/renpy-release-checklist.md`
- Modify: `docs/qa/renpy-batch-bc-evidence.md`
- Evidence outside Git: raw `adb logcat`, screenshots, source APKs and saves; commit only sanitized references/results

**Interfaces:**
- Consumes: signed APK、real game samples、Android device、old save fixture。
- Produces: single/split、selectable/always-on、new/old save、rollback/jump/language results。

- [ ] **Step 1：记录设备和安装前状态**

Record Android version、ABI、free space、source package/version and sample hash. Confirm backup/restore permissions before touching saves.

- [ ] **Step 2：执行每个适用样本的固定链路**

```text
scan → preflight → coverage → translate → lint → compile
→ RPYC validate → APK merge → sign → install → launch
→ see translated text → load old save → rollback → jump
→ switch language or confirm always-on
```

- [ ] **Step 3：验证 selectable**

Select translated language, observe expected translated string, switch to original, observe original string, reload old save in both modes, and record outcome.

- [ ] **Step 4：验证 always-on**

Launch and observe translated string without menu selection. Confirm UI never promises in-game switching. Load old save, rollback and jump; record all outcomes.

- [ ] **Step 5：验证 split if applicable**

Confirm base and every split are installed in one session with matching package/version/signature. Launch and verify resources originating in split are readable.

- [ ] **Step 6：验证 rollback/jump for dialogue ID mode**

Only after all rows pass may the advanced mode capability set `rollback=true`. Any failure resets the mode to default-off and marks `C15-05` `FAIL`.

- [ ] **Step 7：record failures honestly**

For crash、missing glyph、wrong language、save load failure or rollback mismatch, record `FAIL`, retain sanitized log reference and keep release unapproved. Do not retry with broader compatibility flags before root-cause investigation.

- [ ] **Step 8：处理无设备情况**

If no device is connected/authorized, record `NOT-RUN` and the exact prerequisite. This is an external blocker, not a successful completion.

- [ ] **Step 9：提交 sanitized device matrix**

Commit message: `test: record renpy android device matrix` only when evidence contains no private game data or device identifiers.

---

## Phase 5：完成审计与发布批准

### Task 23：逐条审计原 Task 6–16 并决定发布状态

**Files:**
- Modify: `docs/qa/renpy-batch-bc-evidence.md`
- Modify: `docs/qa/renpy-compatibility-matrix.md`
- Modify: `docs/qa/renpy-release-checklist.md`
- Modify: `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`
- Reference: `docs/superpowers/plans/2026-08-07-renpy-app-compatibility-optimization.md`

**Interfaces:**
- Consumes: all Task 0–22 current evidence。
- Produces: one auditable final state: `批准发布` or `未批准发布/等待外部验收`。

- [ ] **Step 1：逐个映射原计划 Step**

For Task 6–16, count every `- [ ] **Step N` in the original plan and require a corresponding evidence row. No original Step may be covered only by a task-level summary.

- [ ] **Step 2：check evidence consistency**

For each `PASS`, verify command exists, artifact exists, result matches and commit contains the referenced change. Downgrade weak/indirect evidence to `NOT-RUN` or `FAIL`.

- [ ] **Step 3：run final machine verification fresh**

```powershell
python -m py_compile patch_workshop_ui.py test_workshop_patch.py test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py test_built_apk.py
python -m unittest test_workshop_patch.py -v
python -m unittest test_fast_scanner.py -v
python -m unittest test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
python -m unittest test_built_apk.py -v
python -m unittest discover -s . -p 'test_*.py' -v
```

Expected: zero failures/errors. Every skip is explicitly listed in the release checklist.

- [ ] **Step 4：verify Git boundary**

```powershell
git diff --check
git status --short --branch
git diff --cached --name-status
```

Expected: no whitespace errors; no unrelated files staged by this plan; original four user files remain staged unless the user explicitly changed that state.

- [ ] **Step 5：apply release decision rule**

Set `批准发布` only when:

```text
all automated gates PASS
AND helper/APK/signature gates PASS
AND real sample coverage/font/validator gates PASS
AND single/split applicable device gates PASS
AND selectable/always-on applicable gates PASS
AND new game/old save/rollback/jump/language gates PASS
AND no mandatory requirement is FAIL or NOT-RUN
```

Otherwise set `未批准发布` or `等待外部验收` and name every missing condition.

- [ ] **Step 6：request independent review**

Use `superpowers:requesting-code-review` to review requirement coverage, security boundaries, tests and evidence honesty. Any finding returns to the owning task; do not patch findings inside the final audit commit.

- [ ] **Step 7：commit final audit**

```powershell
git add -- 'docs/qa/renpy-batch-bc-evidence.md' 'docs/qa/renpy-compatibility-matrix.md' 'docs/qa/renpy-release-checklist.md' '.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md'
git commit --only -m 'docs: close renpy batch b and c release audit' -- 'docs/qa/renpy-batch-bc-evidence.md' 'docs/qa/renpy-compatibility-matrix.md' 'docs/qa/renpy-release-checklist.md' '.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md'
```

- [ ] **Step 8：mark goal complete only if all required evidence is PASS**

If any real-game/device mandatory row is `NOT-RUN` or `FAIL`, keep the goal active unless the strict repeated-blocker rule is satisfied; do not redefine completion as “all local work done.”

## Execution Notes

- Execute one task at a time and update the new progress ledger after every verification and commit.
- For Phase 1, a single root-cause cluster is the maximum review unit; do not bundle all 26 workshop issues into one patch.
- For Tasks 8–17, if existing behavior and direct tests already satisfy a requirement, the task may change only tests/evidence; it still requires fresh full regression and an independent commit.
- Raw real-game content, save files, APKs, screenshots and device identifiers stay outside Git. Commit only hashes, sanitized counts, stable issue codes and test outcomes.
- When an external condition is absent, continue all safe local work, leave the corresponding row `NOT-RUN`, and keep release unapproved.
