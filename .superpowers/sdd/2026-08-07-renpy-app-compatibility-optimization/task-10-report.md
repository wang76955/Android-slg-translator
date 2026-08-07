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

## 独立审查后的二次修复

审查发现首次集成仍有覆盖率假阳性风险，已补上并加入行为级测试：

- UI coverage 使用原始 exact-old 作为分组、缓存和候选值 key，不再把换行、Tab 等控制字符归一化后再统计；JSON 导出仍由 `JSON.stringify` 负责转义，渲染仍使用 `textContent`。
- 远程翻译只在单批 `Vo` 返回经过保护文本恢复的结果时记录为 validator-approved；cache/local-rule 累积 map 不再被整体标记为已验证。批次失败会进入 rejected 集合，不能借缓存绕过完整构建门禁。
- 本地/远程结果会记录候选译文以产生覆盖率侧 collision；新的翻译轮次会同步清理不确定项、分类表、候选译文和碰撞条目。
- `x-common` 的 developer/console、internal/error、expired、settings/optional 路径提供显式分类原因；普通公共故事/UI 文本默认仍纳入覆盖率。扫描器把分类原因传入 UI。
- 新增 Node 行为测试，实际执行生成的 coverage IIFE，验证多行 exact-old 不合并、validated/rejected/collision 计数以及全状态 reset。

该轮修复的验证命令：

- `python -m unittest test_translation_coverage.py test_translation_quality.py -v`：待本轮提交后复跑并记录最终计数。
- `python -m unittest test_fast_scanner.py -v`：待本轮提交后复跑并记录最终计数。

本报告对应提交消息：`feat: gate renpy builds on validated translation coverage`。

## 任务 10 集成复核修复

对首次实现进行本地集成复核后，补齐了以下边界：

- 本地缓存和本地 LLM 的 `Map` 结果现在通过同一个 validator-approved 入口计入覆盖率；本地 LLM 返回的 rejected entries 会向上汇总并计入拒绝数。
- 每次开始新的翻译轮次都会清空上一轮的 coverage records、validated map、rejected set 和不完整测试补丁选择，避免跨游戏或跨轮次污染。
- 覆盖率统计不再把原文截断为 400 个字符；脱敏仍通过 JSON 序列化和 UI `textContent` 完成，因此长 exact-old 不会被错误合并。

复核后的验证结果：

- `python -m py_compile test_translation_coverage.py patch_workshop_ui.py`：通过。
- `python -m unittest test_translation_coverage.py test_translation_quality.py -v`：24 tests，`OK`，1 个缺少审计夹具的测试明确 skip。
- `python -m unittest test_fast_scanner.py -v`：49 tests，`OK`。
- `git diff --check`：通过。
