# Task 10 实施报告：Ren'Py 翻译覆盖率与构建门禁

## 实施范围

本批次只修改了 Task 10 允许的五个路径：

- `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCoverageReport.java`
- `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- `apk-work/ui-redesign/patch_workshop_ui.py`
- `apk-work/ui-redesign/test_translation_coverage.py`
- 本报告文件

Task 9 的 `RenpyTextValidator`、编译器校验路径、缓存命名空间 `slg-translator-cache:` 以及用户既有的四份 staged 文档均未修改。

## 实现结果

`TranslationCoverageReport` 以 exact-old occurrence 为输入，按唯一原文和全部出现次数分别统计：

- `uniqueSourceCount`、`occurrenceCount`、`translatedCount`、`missingCount`、`rejectedCount`、`collisionCount`、`uncertainCount`。
- 每个源文件的 source/occurrence/translated/missing/rejected/collision/uncertain 计数。
- `topMissing()` 和 `topMissingFiles()` 均限制为前 20 项，并按缺失量排序。
- 只有 validator-approved map 中的非空值能计入 translated；同一 exact-old 出现在 rejected 集合时，rejected 优先，不能被缓存值“洗成” translated。
- `x-common` 默认纳入覆盖率；developer console、internal error、expired text、可选 settings 只有在 classification map 提供显式原因时才跳过，原因记录在 `excludedReasons`。
- `incrementalDiff` 复用稳定 validated 值，只请求新 exact-old、历史失败项和显式重译项。
- 缺失或拒绝项会使 `shouldBlockCompleteBuild()` 为 true；不完整测试补丁仍由 `canGenerateIncompleteTestPatch()` 明确允许，但不会改变完整构建门禁。
- JSON 导出只包含覆盖率诊断、源路径、缺失原文和分类原因，不导出翻译候选值或 API key。

`FastApkScanner.readRenpyTexts` 继续返回完整 `renpyRecords`，并通过同一个 `coverageReport(...)` 入口返回初始覆盖率 JSON、occurrence/unique 计数和明确的 `coverageGate` 状态。没有翻译结果时会真实报告缺失，不会把审计 fixture 缺失伪造成 0。

Workshop UI 会累计扫描到的 exact-old occurrence、Task 9/本地引擎返回的 validator-approved translations 和 rejected entries，展示覆盖率摘要、top missing files、完整构建阻断警告，并提供脱敏 JSON 导出。只有用户显式选择不完整测试补丁后，覆盖率不足的流程才继续；即使继续也保留“不完整测试补丁、不能宣称完整翻译”的警告。

## TDD 与验证

先修改 `test_translation_coverage.py` 写入红测，确认实现类不存在、scanner/UI 合同未接入时失败；之后实现最小代码并迭代修复：

- `python -m py_compile test_translation_coverage.py patch_workshop_ui.py`：通过。
- `python -m unittest test_translation_coverage.py -v`：9 tests，`OK`，审计 APK/extracted dump fixture 不存在时 1 个明确 skip。
- `python -m unittest test_translation_coverage.py test_translation_quality.py -v`：24 tests，`OK`，同样只有 1 个明确审计 fixture skip。
- `python -m unittest test_fast_scanner.py -v`：49 tests，`OK`。
- `git diff --check`：通过。

本报告对应提交消息：`feat: gate renpy builds on validated translation coverage`。
