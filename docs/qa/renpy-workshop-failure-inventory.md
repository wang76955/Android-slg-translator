# Ren'Py Workshop 失败根因清单

本清单记录 Task 1 在当前 canonical workshop fixture 上的 26 项失败：1 项 `ERROR`、25 项 `FAIL`。清单只建立证据边界和后续修复入口；Task 1 没有修改产品生成逻辑，也没有把任何失败项伪造为绿色。

### Classification status

本清单中的所有 `Classification` 都是 Phase 0 的 preliminary candidate observation，不是最终根因结论。Phase 1/后续任务必须逐项结合当前实现行为、权威行为来源，以及 fixture 输入/输出和必要的字节或 UTF-8 证据进行确认；若证据不支持当前候选标签，必须替换为允许集合中的其他值。尤其是 `ENCODING_BOUNDARY` 只表示当前观察值得调查，不表示已经证明发生了字节、UTF-8、Node 输入或生产输出转换。

本轮没有分配某个候选标签（例如 `EXTERNAL` 数量为 0）不等于排除该根因；这只是本轮没有分配候选标签，后续仍需调查。

## 基线证据

工作目录：`apk-work/ui-redesign`

精确命令：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m unittest test_workshop_patch.py -q 2>&1 | ForEach-Object {
  $line=[string]$_
  if ($line -match '^(FAIL|ERROR):' -or $line -match '^Ran ' -or $line -match '^FAILED') { $line }
}
```

结果为 `Ran 49 tests`、`FAILED (failures=25, errors=1)`。失败名按命令输出逐项保存如下；压缩 bundle dump 未写入本文件。

提取器边界也已单独验证：

```text
python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_extract_js_function_ignores_braces_inside_strings_and_templates -v
ERROR ... NotImplementedError

python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_extract_js_function_ignores_braces_inside_strings_and_templates test_workshop_patch.WorkshopPatchContractTest.test_patched_javascript_is_syntactically_valid -v
Ran 2 tests ... OK
```

`extract_js_function(source, signature)` 位于测试类外，只扫描从签名开始的函数块；它识别括号深度、花括号深度、单引号、双引号、反引号、反斜杠转义和模板 `${...}` 嵌套。签名缺失及花括号未闭合均为 `AssertionError`。该提取器的 GREEN 不等于下列产品行为已修复。

## 失败清单

### WSP-01 `test_translation_cache_is_reused_across_models`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_cache_is_reused_across_models -v`
- First effective failure: `ValueError: substring not found`；扫描锚点为 `var _o=slg-translator-cache:v2:` 和 `function Do()`。
- Expected behavior: 能稳定取得缓存 runtime，并验证同源语言、目标语言及 glossary 隔离，同时允许跨 model 复用最新翻译。
- Observed behavior: 测试在行为夹具运行前即因固定的下一个函数标记不存在而退出，未能证明缓存行为。
- Authority: `WorkshopPatchContractTest` 的缓存契约；生产入口 `patch_workshop_ui.patch_assets(js, css)`。
- Classification: `BRITTLE_EXTRACTION`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（当前截取契约）；`apk-work/ui-redesign/patch_workshop_ui.py`（被测生成输出，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_cache_is_reused_across_models -v` → `ValueError: substring not found`。
- Green evidence: `NOT-RUN — Task 1 只建立稳定提取器，缓存行为留待后续任务；没有伪造 PASS。`

### WSP-02 `test_completed_zero_entry_scan_is_an_empty_result_not_scanning`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning -v`
- First effective failure (baseline): `Error: settled zero-entry scan misclassified: {"state":"idle"}`.
- Expected behavior: with `settled && fileCount === 0 && !fatalError`, `readTaskSnapshot()` returns `empty` and preserves filename plus split metadata.
- Root-cause evidence: the original fixture used stale mojibake UI tokens; after `extract_js_function(js, "function readTaskSnapshot()")` and a current UTF-8 fixture, the full function returns `empty`, `count:"0"`, the filename, and split metadata.
- Authority: `WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning`; `readTaskSnapshot()`.
- Classification: `STALE_CONTRACT` (the initial extractor failure also exposed `BRITTLE_EXTRACTION`; the Task 1 extractor was made regex-literal safe in the test harness).
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`; no product change.
- Red evidence: baseline `-v` run failed with `state:"idle"`; full-function run then passed after updating only the stale fixture/UI token expectations.
- Green evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_completed_zero_entry_scan_is_an_empty_result_not_scanning -v` -> `Ran 1 test ... OK`.

### WSP-03 `test_dismiss_recovery_banner_re_renders_immediately`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately -v`
- First effective failure (baseline): `Error: recovery banner offers dismiss`.
- Expected behavior: a saved translating session renders a recovery banner; dismiss removes `SESSION_KEY`, resets `sessionRestoredAt`, invalidates the snapshot, calls `refresh()`, and removes the banner immediately.
- Root-cause evidence (Fix round 1): the fixture now writes `SESSION_KEY` with `translating:true`, `savedAt:123`, and a minimal saved session, then executes complete `restoreSession()`/`refresh()`/`recoveryBanner()` paths. The first real post-dismiss run failed at `dismiss invalidates snapshot cache and refreshes immediately`; adding the minimal `lastSnapshot=""` invalidation made the same-key refresh render the banner-free state.
- Authority: `WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately`; `recoveryBanner()`, `refresh()`, `renderStateBody()`.
- Classification: `PRODUCT_REGRESSION` (Fix round 1; the real restore/dismiss fixture demonstrated missing snapshot-cache invalidation).
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`; `apk-work/ui-redesign/patch_workshop_ui.py` (`lastSnapshot=""` before dismiss refresh).
- Red evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately` -> `Error: dismiss invalidates snapshot cache and refreshes immediately`.
- Green evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_dismiss_recovery_banner_re_renders_immediately` -> `Ran 1 test ... OK`; direct assertions covered `localStorage.getItem(SESSION_KEY)===null`, `sessionRestoredAt===0`, two refresh/render passes, and banner disappearance.

### WSP-04 `test_fatal_network_stops_outer_file_controller`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_fatal_network_stops_outer_file_controller -v`
- First effective failure: `AssertionError: expected outer-controller error token not found in patched JavaScript`（断言的完整形式为 `'<expected token>' not found in '<patched bundle>'`；bundle dump 已省略）。
- Expected behavior: 外层文件控制器应使用 `runFileTasksParallel(..., concurrency=3)`，在 fatal provider error 后阻止后续文件，并保留 actionable error。
- Observed behavior: 直接 token 断言失败，未进入 scheduler 行为夹具；当前实现的错误文案/生成片段与契约中的精确字符串不同。
- Authority: `WorkshopPatchContractTest.test_fatal_network_stops_outer_file_controller`；`runFileTasksParallel()` 与文件控制器生产接口。
- Classification: `STALE_CONTRACT`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（过具体 token 契约）；`apk-work/ui-redesign/patch_workshop_ui.py`（生成输出，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_fatal_network_stops_outer_file_controller -v` → `AssertionError: '<expected token>' not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 需由后续任务决定更新契约还是恢复产品接口后再验证。`

### WSP-05 `test_installed_app_source_chooser_contract`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_installed_app_source_chooser_contract -v`
- First effective failure: `AssertionError: 'window.__slgSelectionMeta=e' not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: 已安装应用选择应保存 selection metadata，包含 URI、package、split 信息，并通过真实 shared URI scanner 继续加载。
- Observed behavior: 当前生成代码采用扩展后的 `Object.assign(...)` metadata 写入形式，缺少测试要求的旧精确 token，因此行为夹具未运行；本次 baseline 首个有效错误仍为该精确契约不匹配。
- Authority: `WorkshopPatchContractTest.test_installed_app_source_chooser_contract`；`chooseInstalledApp()`、`loadSelectedApk()` 生产接口。
- Classification: `STALE_CONTRACT`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（过具体 token）；`apk-work/ui-redesign/patch_workshop_ui.py`（metadata 生成输出，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_installed_app_source_chooser_contract -v` → `AssertionError: 'window.__slgSelectionMeta=e' not found in '<patched bundle>'`（bundle dump 已省略）。
- Green evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_installed_app_source_chooser_contract` → `Ran 1 test in 0.067s; OK`；测试改为验证完整 SourceSet 与 shared scanner 行为，未修改运行时 metadata 逻辑。

### WSP-06 `test_installed_list_and_selection_epochs_ignore_stale_requests`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_installed_list_and_selection_epochs_ignore_stale_requests -v`
- First effective failure: `SyntaxError: missing ) after argument list`，定位到夹具中的 `正在读取应用安装包...` 字符串。
- Expected behavior: 旧 installed-list/selection 请求在新请求完成后不得覆盖当前 URI、entries、package 或 error；loading/error 状态必须可恢复。
- Observed behavior: Node 在执行生产片段前就无法解析测试夹具（`[eval]:55`），stale-request 行为没有被执行。
- Authority: `WorkshopPatchContractTest.test_installed_list_and_selection_epochs_ignore_stale_requests`；installed list/selection epoch 生产接口。
- Classification: `FIXTURE_GAP`
- Classification confidence: Confirmed; the harness had an unterminated template literal in its busy-state assertion, so Node could not reach epoch behavior.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（修复 Node harness 语法、改用可控 deferred 与语义断言）；`apk-work/ui-redesign/patch_workshop_ui.py`（未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_installed_list_and_selection_epochs_ignore_stale_requests -v` → `SyntaxError: missing ) after argument list`（`[eval]:55`）。
- Green evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_installed_list_and_selection_epochs_ignore_stale_requests` → `Ran 1 test in 0.122s; OK`；两个 list request 与两个 selection request 均通过逆序 settlement/stale rejection 验证。

### WSP-07 `test_long_running_phases_are_not_reported_as_directory_scanning`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_long_running_phases_are_not_reported_as_directory_scanning -v`
- First effective failure: `AssertionError: expected progress regex token not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: translating、patching、completed 阶段使用明确状态，不被误判为 directory scanning；进度、动画和长任务文案应在 shell 中可见。
- Observed behavior: hard-coded progress 文案/正则 token 未匹配当前生成文本，行为和 CSS 断言未执行。
- Authority: `WorkshopPatchContractTest.test_long_running_phases_are_not_reported_as_directory_scanning`；`readTaskSnapshot()` 与 `setWorkshopState()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（文本/正则契约）；`apk-work/ui-redesign/patch_workshop_ui.py`（中文 runtime 文本生成，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_long_running_phases_are_not_reported_as_directory_scanning -v` → `AssertionError: expected progress regex token not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 需先统一 UTF-8 文本边界和语义断言。`

### WSP-08 `test_network_failure_preempts_stale_translating_ui`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_network_failure_preempts_stale_translating_ui -v`
- First effective failure: `AssertionError: expected network recovery action token not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: network failure 应抢占 stale translating snapshot，显示 `reason: "network"`，保留可操作错误，并提供切换供应商与重试动作。
- Observed behavior: 精确的中文 action token 断言先失败，恢复动作行为夹具未运行。
- Authority: `WorkshopPatchContractTest.test_network_failure_preempts_stale_translating_ui`；`readTaskSnapshot()`、`renderStateBody()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（文案 token 契约）；`apk-work/ui-redesign/patch_workshop_ui.py`（network runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_network_failure_preempts_stale_translating_ui -v` → `AssertionError: expected network recovery action token not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 后续任务需先统一文案编码，再验证状态优先级和动作 wiring。`

### WSP-09 `test_network_failures_stop_batches_without_recursive_splitting`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_network_failures_stop_batches_without_recursive_splitting -v`
- First effective failure: `AssertionError: '无法连接 ${P}' not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: provider/network failure 只发起一次请求并向外传播；普通内容错误仍允许递归拆批，network failure 不得递归重试。
- Observed behavior: provider error 文案 token 断言失败，递归拆批和 worker 停止行为未执行。
- Authority: `WorkshopPatchContractTest.test_network_failures_stop_batches_without_recursive_splitting`；`isNetworkFailure()`、`Bo()`、`Lo()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（中文错误 token）；`apk-work/ui-redesign/patch_workshop_ui.py`（翻译协调器，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_network_failures_stop_batches_without_recursive_splitting -v` → `AssertionError: '无法连接 ${P}' not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 后续任务需处理编码边界后再验证请求次数和拆批语义。`

### WSP-10 `test_partial_network_failure_never_writes_or_packages`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_partial_network_failure_never_writes_or_packages -v`
- First effective failure: `ReferenceError: _maxDone is not defined`。
- Expected behavior: partial file success 后发生 fatal provider outage 时，不写入部分翻译、不构建 patched APK，也不打包缓存输出。
- Observed behavior: 截取出的 file-result 片段引用 `_maxDone`，但独立 Node fixture 没有提供该生产上下文变量，导致行为尚未可判定。
- Authority: `WorkshopPatchContractTest.test_partial_network_failure_never_writes_or_packages`；文件控制器与 `E.buildPatchedApk()` 生产接口。
- Classification: `FIXTURE_GAP`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（缺少 `_maxDone` 的独立 fixture）；`apk-work/ui-redesign/patch_workshop_ui.py`（被截取片段，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_partial_network_failure_never_writes_or_packages -v` → `ReferenceError: _maxDone is not defined`。
- Green evidence: `NOT-RUN — 先补齐 fixture 的生产上下文，再判断写入/打包门禁。`

### WSP-11 `test_patch_contains_player_workshop_contract`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_patch_contains_player_workshop_contract -v`
- First effective failure: `AssertionError: expected player-facing workshop copy not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: patched bundle 应包含 workshop 玩家入口、选择 APK、处理详情、安装和保存等批准文案/结构。
- Observed behavior: 直接中文 copy token 断言失败，未进入后续 workshop contract 检查。
- Authority: `WorkshopPatchContractTest.test_patch_contains_player_workshop_contract`；`WORKSHOP_COPY`、`patch_assets()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（copy token 断言）；`apk-work/ui-redesign/patch_workshop_ui.py`（WORKSHOP_COPY/生成输出，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_patch_contains_player_workshop_contract -v` → `AssertionError: expected player-facing workshop copy not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 文案编码边界及批准 copy 尚未修复。`

### WSP-12 `test_patch_installs_visible_android_shell`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_patch_installs_visible_android_shell -v`
- First effective failure: `AssertionError: '处理详情' not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: runtime mount 后应插入可见 Android shell，显示任务状态、处理详情和底部导航，同时隐藏 legacy UI。
- Observed behavior: 处理详情 token 不匹配，shell 可见性行为夹具未执行。
- Authority: `WorkshopPatchContractTest.test_patch_installs_visible_android_shell`；`mount()`、`setWorkshopState()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（UI copy token）；`apk-work/ui-redesign/patch_workshop_ui.py`（shell 生成，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_patch_installs_visible_android_shell -v` → `AssertionError: '处理详情' not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 尚未修复文案边界或验证 Android shell 行为。`

### WSP-13 `test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines -v`
- First effective failure: `AssertionError: expected cleanup/settings token not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: RPYC 文本管线应保留 story text、过滤非文本资源，并正确区分真实换行和 literal `\\n`；相关 workshop settings/runtime 结构应存在。
- Observed behavior: 进入 `Ne()` 行为 harness 前，固定中文 token 断言已失败。
- Authority: `WorkshopPatchContractTest.test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines`；`Ne()`、`os()`、`patch_assets()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（RPYC/copy token 契约）；`apk-work/ui-redesign/patch_workshop_ui.py`（RPYC patch，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines -v` → `AssertionError: expected cleanup/settings token not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 后续任务需分离文本编码问题与 RPYC 运行时行为。`

### WSP-14 `test_save_and_import_game_selection_are_independent`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_and_import_game_selection_are_independent -v`
- First effective failure: `SyntaxError: Unexpected identifier 'cim'`。
- Expected behavior: 保存页和导入页应各自维护 selected package、label 和 selector value，互不覆盖。
- Observed behavior: Node 先在带 mojibake/引号边界的行为 harness 处解析失败，独立选择状态没有被执行。
- Authority: `WorkshopPatchContractTest.test_save_and_import_game_selection_are_independent`；`savesSelectedPkg`、`importSelectedPkg` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a fixture `SyntaxError`, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（Node harness）；`apk-work/ui-redesign/patch_workshop_ui.py`（save/import runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_and_import_game_selection_are_independent -v` → `SyntaxError: Unexpected identifier 'cim'`。
- Green evidence: `NOT-RUN — 先修复 Node harness 的 UTF-8/引号边界。`

### WSP-15 `test_save_transfer_can_import_shared_archive`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_can_import_shared_archive -v`
- First effective failure: `SyntaxError: missing ) after argument list`。
- Expected behavior: 导入页应列出下载目录 zip，支持删除单个 archive、导入 selected archive，并自动回填对应游戏。
- Observed behavior: 行为 harness 在 Node 解析阶段失败，archive list/import/delete 流程未运行。
- Authority: `WorkshopPatchContractTest.test_save_transfer_can_import_shared_archive`；`listSaveArchives()`、`importSaveBackup()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a fixture `SyntaxError`, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（Node harness 文本）；`apk-work/ui-redesign/patch_workshop_ui.py`（save transfer runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_can_import_shared_archive -v` → `SyntaxError: missing ) after argument list`。
- Green evidence: `NOT-RUN — 夹具可解析后再验证 native archive contract。`

### WSP-16 `test_save_transfer_can_pick_game_from_installed_apps`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_can_pick_game_from_installed_apps -v`
- First effective failure: `SyntaxError: Unexpected identifier 'cim'`。
- Expected behavior: 保存页游戏选择器应使用 save-aware app list，不回退到所有 installed apps，并在选择后启用保存动作、刷新 backup list。
- Observed behavior: Node 在游戏 fixture 字符串处解析失败，native list 调用和 state gating 未运行。
- Authority: `WorkshopPatchContractTest.test_save_transfer_can_pick_game_from_installed_apps`；`listSaveGameApps()`、`updateSavesState()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a fixture `SyntaxError`, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（Node harness）；`apk-work/ui-redesign/patch_workshop_ui.py`（save picker runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_can_pick_game_from_installed_apps -v` → `SyntaxError: Unexpected identifier 'cim'`。
- Green evidence: `NOT-RUN — 先修复 fixture 编码/字符串边界。`

### WSP-17 `test_save_transfer_runtime_actions_and_state_gating`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_runtime_actions_and_state_gating -v`
- First effective failure: `SyntaxError: missing ) after argument list`。
- Expected behavior: 未选择游戏时保存按钮禁用；选择后 restore/share/delete/export 均调用正确 native 参数，并在完成/失败后恢复按钮状态。
- Observed behavior: Node 行为 harness 无法解析，runtime actions 与 gating 没有执行。
- Authority: `WorkshopPatchContractTest.test_save_transfer_runtime_actions_and_state_gating`；`refreshSaves()`、`restoreSaves()`、`shareSaveBackup()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a fixture `SyntaxError`, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（Node harness）；`apk-work/ui-redesign/patch_workshop_ui.py`（save actions，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_runtime_actions_and_state_gating -v` → `SyntaxError: missing ) after argument list`。
- Green evidence: `NOT-RUN — 夹具解析边界修复后再验证动作契约。`

### WSP-18 `test_save_transfer_settings_runtime_contract`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_settings_runtime_contract -v`
- First effective failure: `AssertionError: '选择游戏' not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: settings save-transfer runtime 应包含 backup/restore/share/delete、下载导出、archive import 和独立游戏选择控件，且删除旧按钮/旧入口。
- Observed behavior: 直接中文 picker token 断言失败，runtime slice 及禁用旧控件断言未执行。
- Authority: `WorkshopPatchContractTest.test_save_transfer_settings_runtime_contract`；settings save/import production interface。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（save-transfer 文案 token）；`apk-work/ui-redesign/patch_workshop_ui.py`（settings runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_save_transfer_settings_runtime_contract -v` → `AssertionError: '选择游戏' not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 尚未统一 token 编码或验证 save-transfer runtime。`

### WSP-19 `test_settings_support_provider_model_and_custom_endpoint`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_settings_support_provider_model_and_custom_endpoint -v`
- First effective failure: `AssertionError: '已保存：' not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: settings 应持久化 provider、model、custom endpoint、custom model 和 API key，并把配置同步到 React 控件，错误和成功状态可见。
- Observed behavior: 成功状态中文 token 未匹配，provider/model/custom endpoint 行为断言未执行。
- Authority: `WorkshopPatchContractTest.test_settings_support_provider_model_and_custom_endpoint`；`readSettingsPrefs()`、`saveSettingsPrefs()`、`applySettingsToReact()` 生产接口。
- Classification: `ENCODING_BOUNDARY`
- Classification confidence: Preliminary candidate only; current evidence is a token mismatch, not verified byte-level encoding conversion; root cause pending Phase 1.
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（settings copy token）；`apk-work/ui-redesign/patch_workshop_ui.py`（settings runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_settings_support_provider_model_and_custom_endpoint -v` → `AssertionError: '已保存：' not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 后续任务处理 settings 文本边界后再验证。`

### WSP-20 `test_shared_loader_has_deadline_and_stale_safe_settlement`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_shared_loader_has_deadline_and_stale_safe_settlement -v`
- First effective failure: `Error: timeout contract`。
- Expected behavior: shared loader 应同步注册 watchdog、对 native scan 设置 65 秒可观测 deadline、在 timeout/reject 时清理 scanning 状态，并拒绝 late resolve 覆盖新 selection。
- Observed behavior: baseline harness 首个失败于 timeout contract；修正可控 fake deadline 后，进一步证实扫描失败 UI 缺少可执行 retry/file fallback，已做最小运行时补丁。
- Authority: `WorkshopPatchContractTest.test_shared_loader_has_deadline_and_stale_safe_settlement`；`withTimeout()`、`loadSelectedApk()` 生产接口。
- Classification: `PRODUCT_REGRESSION`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（loader fake-timer/deferred harness 与失败 UI 行为断言）；`apk-work/ui-redesign/patch_workshop_ui.py`（扫描失败状态增加 retry/file fallback）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_shared_loader_has_deadline_and_stale_safe_settlement -v` → `Error: timeout contract`。
- Green evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_shared_loader_has_deadline_and_stale_safe_settlement` → `Ran 1 test in 0.176s; OK`；fake timer 跨过 65000 ms deadline，late resolve 未覆盖失败状态，retry/file fallback 均可执行。

### WSP-21 `test_source_modals_handle_android_back_focus_and_file_fallback`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_source_modals_handle_android_back_focus_and_file_fallback -v`
- First effective failure: `Error: error state exposes retry and file fallback`。
- Expected behavior: installed-app modal 的 loading/error 状态应恢复 focus；error 状态同时提供 retry 和从文件选择 APK fallback，fallback 要关闭 modal 并触发真实 picker bridge。
- Observed behavior: error state 首个失败于 retry/file-fallback 联合断言，后续 Android back/focus 断言未执行。
- Authority: `WorkshopPatchContractTest.test_source_modals_handle_android_back_focus_and_file_fallback`；`renderInstalledApps()`、`closeInstalledApps()` 生产接口。
- Classification: `STALE_CONTRACT`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（modal harness 改为稳定 DOM/action 语义断言）；`apk-work/ui-redesign/patch_workshop_ui.py`（source modal 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_source_modals_handle_android_back_focus_and_file_fallback -v` → `Error: error state exposes retry and file fallback`。
- Green evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_source_modals_handle_android_back_focus_and_file_fallback` → `Ran 1 test in 0.119s; OK`；Android Back 仅消费可见 source/installed modal，恢复 opener focus，file fallback 可执行。

### WSP-22 `test_task_runtime_bridges_and_recovery_contract`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract -v`
- First effective failure (baseline): stale ENOSPC localized-copy token assertion; the later `<patched bundle>` dump is not root-cause evidence.
- Expected behavior: React remains the owner of controls; the shell dispatches bubbling events, exposes task state, and renders the current recoverable ENOSPC contract.
- Root-cause evidence (Fix round 1): complete `triggerReactButton()`, `renderTopbar()`, `fileRow()`, `detailToggle()`, `actionButton()`, `renderStateBody()`, `setWorkshopState()`, and `retryTask()` functions now run in a minimal Node DOM/event fixture. The fixture proves a bubbling click reaches the React control, failed state data attributes are set, ENOSPC renders localized title/raw details/retry, and retry invokes the bridge. The broad `.click()` gate scans the concatenated workshop-runtime functions; unrelated base-bundle anchor clicks are excluded because they are outside those extracted workshop-owned functions, not because of variable-name filtering.
- Authority: `WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract`; `triggerReactButton()`, `renderStateBody()`.
- Classification: `STALE_CONTRACT` (not a network/product fix).
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`; no product change.
- Red evidence: baseline `-v` run failed at the first stale ENOSPC token; no bundle dump was used as root cause.
- Green evidence: `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_task_runtime_bridges_and_recovery_contract` -> `Ran 1 test ... OK` (real Node fixture; not static bundle-only).

### WSP-23 `test_translating_state_does_not_replay_card_entrance_animation`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation -v`
- First effective failure (baseline): selector with a space before the descendant card was not found in whitespace-compacted CSS.
- Expected behavior: translating and patching cards must not replay entrance animation; the default card entrance animation remains available for initial states.
- Root-cause evidence: patched CSS contains `.workshop-task-shell[data-workshop-state="translating"].workshop-task-card{animation:none}` and the corresponding patching rule; the old expectation retained whitespace after CSS compaction.
- Authority: `WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation`; `patch_assets(js, css)` CSS output.
- Classification: `STALE_CONTRACT` (product CSS already satisfied both required active phases).
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`; no product change.
- Red evidence: baseline `-v` run failed on the compacted selector token.
- Green evidence (Fix round 1): `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_translating_state_does_not_replay_card_entrance_animation` -> `Ran 1 test ... OK`.

### WSP-24 `test_translation_heartbeat_updates_session`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_heartbeat_updates_session -v`
- First effective failure (baseline): `Error: heartbeat refreshes savedAt while translating`.
- Expected behavior: while translating, `refresh()` keeps `translating=true`, updates `SESSION_KEY.savedAt`, and keeps the translating state visible.
- Root-cause evidence: the original fixture text was stale mojibake and therefore classified as idle. With `extract_js_function()` and a current `正在处理脚本 1/5` fixture, the full `refresh()` updates the persisted heartbeat and the test passes.
- Authority: `WorkshopPatchContractTest.test_translation_heartbeat_updates_session`; `refresh()`, `SESSION_KEY`.
- Classification: `STALE_CONTRACT` (no product regression after the full-function/current-fixture run).
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`; no product change.
- Red evidence: baseline `-v` run failed at the heartbeat assertion.
- Green evidence (Fix round 1): `python -m unittest -v test_workshop_patch.WorkshopPatchContractTest.test_translation_heartbeat_updates_session` -> `Ran 1 test ... OK`.

### WSP-25 `test_translation_logs_are_mirrored_into_the_visible_shell`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_logs_are_mirrored_into_the_visible_shell -v`
- First effective failure: `AssertionError: 'querySelectorAll("#root details")' not found in '<patched bundle>'`（bundle dump 已省略）。
- Expected behavior: visible shell 应从 React 日志源读取最近 40 行，维护 raw/latest，显示 live line，并在 details 展开时滚动到最新日志。
- Observed behavior: 当前 runtime 使用其他日志源 selector（如 font-mono 容器），旧的 `#root details` 具体实现 token 不存在；可见日志语义尚未由本测试证明。
- Authority: `WorkshopPatchContractTest.test_translation_logs_are_mirrored_into_the_visible_shell`；`readProgressLog()`、`renderStateBody()` 生产接口。
- Classification: `STALE_CONTRACT`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（过具体 selector 契约）；`apk-work/ui-redesign/patch_workshop_ui.py`（日志 runtime，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_logs_are_mirrored_into_the_visible_shell -v` → `AssertionError: 'querySelectorAll("#root details")' not found in '<patched bundle>'`。
- Green evidence: `NOT-RUN — 需将 selector 断言改为语义 fixture 或先确认产品接口后再验证。`

### WSP-26 `test_translation_progress_emits_starting_batch_before_request`

- Reproduce: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_progress_emits_starting_batch_before_request -v`
- First effective failure: `Error: both batches translate`。
- Expected behavior: 每个 batch 在请求前发出 `stage: "start"`，完成后报告 completed batches；两批输入应最终成功翻译。
- Observed behavior: coordinator harness 的 `successCount` 联合断言失败，未观察到两个 batch 的完整 start/completed 序列。
- Authority: `WorkshopPatchContractTest.test_translation_progress_emits_starting_batch_before_request`；`Lo()` translation coordinator 生产接口。
- Classification: `PRODUCT_REGRESSION`
- Change set: `apk-work/ui-redesign/test_workshop_patch.py`（coordinator harness）；`apk-work/ui-redesign/patch_workshop_ui.py`（`Lo()` 生成逻辑，Task 1 未修改）。
- Red evidence: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_progress_emits_starting_batch_before_request -v` → `Error: both batches translate`。
- Green evidence: `NOT-RUN — batch progress/coordinator 修复留待后续任务。`

## Task 1 变更边界与风险

- 允许修改且实际修改：`docs/qa/renpy-workshop-failure-inventory.md`、`apk-work/ui-redesign/test_workshop_patch.py`。
- `apk-work/ui-redesign/patch_workshop_ui.py` 只读；没有修改其生成逻辑。
- `extract_js_function()` 的职责仅是稳定提取完整函数块，不能替代产品修复，也不能让既有失败测试自动变绿。
- 清单中的 `PRODUCT_REGRESSION` 仍需真实产品修复和独立绿灯证据；`STALE_CONTRACT` 需由后续任务决定契约是否过时；`BRITTLE_EXTRACTION` 需改用稳定函数边界；`ENCODING_BOUNDARY` 需先统一 UTF-8/Node 夹具边界；`FIXTURE_GAP` 需补齐被截取生产片段的上下文。
- 本任务未将任何 workshop 失败项标记为 PASS；后续任务应保留这些 Red evidence，并在对应修复后追加可复现的 Green evidence。
