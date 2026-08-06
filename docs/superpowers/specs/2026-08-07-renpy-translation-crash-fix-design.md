# Ren'Py 翻译后低内存闪退修复设计

日期：2026-08-07

## 背景与根因

目标游戏 `mayfly.SLLXXL` 在翻译并安装补丁后启动时被 Android 以 `LOW_MEMORY` / `SIGKILL` 结束。复现时游戏进程的匿名内存从约 200 MB 增长到约 2.8 GB，Ren'Py 日志停在 `Loading error handling` 之前，没有 Java 异常或 Ren'Py traceback。

静态检查确认两个相互叠加的原因：

1. `TranslationCompiler.compileTranslationsIntoApk` 收到前端当前任务的输出列表，但忽略了它，改为递归扫描应用级的 `SLG-Translator-Output`。该目录保存过多个游戏、语言和历史任务的 `.rpy`，所以旧文件会混入新的 APK。
2. 编译器把合并后的全部 `TranslateString` 节点写进一个 `x-translations.rpyc`。目标 APK 中该文件包含约 37,429 个节点；Ren'Py 8.5.3 在加载这个单体对象时出现非线性内存增长，最终被系统低内存回收。

本修复只改变翻译结果的选择和 Ren'Py 编译封装，不改变 APK 文本抓取、翻译服务、模型提示词、缓存格式、占位符保护或非 Ren'Py 文件处理。

## 目标与非目标

### 目标

- 当前编译任务只能读取本次任务明确生成的翻译文件。
- 旧输出可以继续保留在设备上，但不能混入当前 APK。
- 保持现有旧文本去重和 `slgtranslated` 语言语义。
- 将过大的单个 RPYC 拆成有界分片，降低 Ren'Py 启动峰值内存。
- 生成失败时给出明确错误，不静默退回全局目录扫描。
- 保持中文样式文件克隆、APK 重写和安装流程兼容。

### 非目标

- 不重写 `FastApkScanner`、`RpycTextExtractor` 的文本提取规则。
- 不改变 API、ML Kit、本地 LLM 的翻译算法、批处理、缓存或提示词。
- 不删除手机上的旧翻译输出、翻译缓存或游戏存档。
- 不在 Android 端移植完整 Ren'Py 编译器。

## 方案

### 1. 当前任务输入隔离

前端在调用原生编译器时只传当前任务生成的相对路径清单，例如 `items: [{path: ...}]`，不再把大段文件内容通过 JS Bridge 发送给编译器。文件内容继续由前端写入现有默认输出目录，避免大 payload 被 Bridge 截断。

原生编译器将每个路径规范化为 `/` 分隔的相对路径，并验证：

- 路径不能是绝对路径、不能包含 `..` 越界段；
- 对应文件必须位于当前应用的 `SLG-Translator-Output` 根目录内；
- 只接受当前翻译桶 `assets/x-game/x-tl/x-slgtranslated/`（以及其等价的 `tl/slgtranslated` 表示）下的 `.rpy` 文件；
- 路径按规范化结果去重并稳定排序。

如果调用没有显式路径清单，或者清单过滤后没有有效文件，编译器直接返回清晰错误/零结果，不再扫描整个输出目录作为隐式 fallback。这样旧文件即使存在，也不会被当前任务读取。

### 2. 合并与有界 RPYC 分片

对被选中的 `.rpy` 仍使用现有 `parseTranslationRpy`，按旧文本去重，保留第一次有效的新文本。语言仍固定为 `slgtranslated`，中文样式仍从游戏内置中文语言包克隆。

合并后的 pair 列表按固定上限拆分为多个分片。初始上限为每片最多 500 个 `TranslateString` 节点，并在测试中保留可调整常量；单个超长文本不能突破分片上限。每个分片使用独立的运行时文件名，例如：

```text
assets/x-game/x-tl/x-slgtranslated/x-translations-0001.rpyc
assets/x-game/x-tl/x-slgtranslated/x-translations-0002.rpyc
...
```

每个 RPYC 仍使用同一 Ren'Py RPC2 模板版本、密钥、语言和 AST 结构。APK 重写时移除本工具之前生成的翻译分片，保留原始游戏的 epoch-dated 编译资源，避免新旧文件重复加载。

编译结果额外返回 `compiled`、`shards` 和 `files`，前端继续用 `compiled > 0` 决定是否关闭普通 `.rpy` 语言镜像逻辑。

### 3. 模板选择与错误边界

模板元数据优先从目标游戏自己的 Ren'Py 翻译桶中读取，避免无条件使用 APK 中遇到的第一个 `.rpyc`。若找不到合法 RPC2 模板，明确拒绝编译并保留原 APK，不生成不确定格式的文件。

解析或写入任一当前文件失败时，错误包含文件路径；不会静默把其它历史文件补进来。非 Ren'Py 文件仍由现有 `buildPatchedApk` 路径处理。

## 测试策略（TDD）

先在 `apk-work/ui-redesign/test_fast_scanner.py` 增加失败的 Java harness 测试，再实现生产代码：

1. **输入隔离**：临时输出目录中同时放当前文件和旧文件，显式传当前路径，断言只读取当前 pair；断言 `..`、绝对路径和非翻译桶路径不会越界或混入。
2. **分片边界**：构造超过一个分片上限的 pair，断言分片数量正确、每片节点数不超过上限、顺序和去重结果稳定。
3. **APK 重写**：构造包含旧生成分片、原始 epoch 编译资源和模板的 ZIP，断言旧生成分片被移除、原始资源保留、新分片可读且条目数正确。
4. **前端契约**：检查 `patch_workshop_ui.py` 生成的编译调用只传路径而不传大段内容，并继续把非翻译文件传给 `buildPatchedApk`。
5. **回归**：运行现有扫描器、RPA、RPYC、占位符、缓存和 APK 契约测试，确认抓取规则和翻译引擎代码未被改动。

## 验证与交付

- 在隔离分支运行定向 Java harness，先观察 RED，再观察 GREEN。
- 运行完整 Python unittest 套件和前端补丁脚本测试。
- 构建工作坊 APK，检查签名、版本和原生 `TranslationCompiler` 字符串。
- 在小型 fixture APK 上验证多个 RPYC 分片；若设备和空间允许，再对目标游戏执行静态 APK 覆盖检查，确认不再出现单个超大 `x-translations.rpyc`。
- 不在没有证据时宣称手机端目标游戏已完全修复；最终报告区分“代码/fixture 已验证”和“真机启动已验证”。
