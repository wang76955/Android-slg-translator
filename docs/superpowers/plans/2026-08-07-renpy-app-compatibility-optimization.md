# Ren'Py 应用兼容性优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项实施本计划。所有步骤使用复选框跟踪；没有通过当前任务的测试和验收门禁前，不进入下一任务。

**Goal:** 把当前 Android Ren'Py 翻译工具从“可以处理已适配样本”提升为“能在翻译前判断兼容性、在构建后自证有效，并对主流 Ren'Py APK 提供安全降级”的产品。

**Architecture:** 保留现有 Capacitor 前端、Java 原生扫描/编译插件、远程模型与 llama.cpp 本地模型的主链路，不移植完整 Ren'Py 运行时。新增“兼容性预检 → 结构化语料 → 严格翻译校验 → 版本感知编译 → 产物自验证 → 安装验证”六道边界，并继续使用 APK loose file 覆盖机制，不重写游戏原始 RPA。

**Tech Stack:** Java 8、Android/Capacitor 原生插件、Python `unittest` 测试夹具、Java harness（`javac`/`java`）、ZIP/RPA/RPYC2/zlib/pickle、llama.cpp、本地或 OpenAI 兼容翻译 API。

## Global Constraints

- 默认处理对象是用户合法取得、由用户本地选择的 APK；不提供修改后游戏的公共分发功能。
- 不移植完整 Ren'Py Python 解释器或编译器；只实现本项目实际需要的兼容读取、受限写入和验证逻辑。
- 不重写 RPA 来注入翻译；默认继续写入 APK 的 loose file 资源目录。
- 默认使用 `TranslateString old/new` 字符串翻译，保持标签、跳转和控制流不变；逐对话 ID 翻译属于高级兼容模式。
- `{#...}` 是 Ren'Py 消歧键的一部分，在提取、去重、缓存和编译阶段都必须保留。
- 不把“APK 成功生成或安装”当作翻译成功；语言激活、RPYC 可加载性、字体覆盖和缺失统计必须单独验证。
- 对无法可靠判断的老版本、未知 pickle 方言或未知 AST 结构，默认停止编译并说明原因，不生成伪成功补丁。
- 所有 APK、RPA、RPYC 和字体均视为不可信输入；读取、解压、解析和临时文件必须有大小、数量、压缩比和时限上限。
- 不修改已有翻译缓存 key 的语义；需要升级格式时增加明确的 schema/version，并提供兼容读取。
- 当前工作树含大量用户文件且尚无正常提交历史；实施时禁止 `git add .`、`git reset --hard` 和批量清理。只有建立安全基线后，才按任务列出的精确路径提交。
- 测试命令默认从 `apk-work/ui-redesign` 运行；每个任务遵循“失败测试 → 最小实现 → 局部回归 → 全量回归”。
- Ren'Py `master` 的 RPYC 魔数和脚本结构会变化；兼容判断必须来自目标 APK，不能把某次源码快照的值硬编码为全局事实。

---

## 1. 当前基线

### 1.1 已完成且必须保留的能力

- RPA-1、RPA-2、RPA-3 索引读取和虚拟条目扫描。
- RPYC2 槽位读取，以及旧式整文件 zlib `.rpyc` 提取回退。
- `tl` 已有翻译中只提取 `old` 源文本的补充语料模式。
- 独立 `slgtranslated` 语言桶编译和兼容语言菜单注入。
- 本地 LLM 的基础占位符 sentinel 保护。
- API 全局并发限制、六工作线程、增量缓存和输出目录 URI 缓存。
- APK 重打包、签名、安装桥接、存档目录备份/恢复和清理逻辑。

### 1.2 已验证测试基线

在 2026-08-07 的源码审查中运行：

```powershell
python -m unittest test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

结果：56 项通过，1 项跳过。跳过项依赖真实完整 APK/语料，因此当前绿色测试不能替代真实游戏的“缺失为 0”和启动验证。

### 1.3 当前最高风险

| 优先级 | 风险 | 用户可见结果 |
|---|---|---|
| P0 | 无标准语言菜单时仍写入 `tl/slgtranslated` | 构建、安装成功，但游戏仍显示原文 |
| P0 | `readTemplateMeta` 可能选择 `x-renpy/x-common` | 生成 RPYC 的 version/key 与游戏不一致，启动报错 |
| P0 | 旧 RPYC 可读，但当前 pickle 写入包含 Python 3 opcode | 老 Ren'Py 可以扫描却无法加载补丁 |
| P0 | 没有编译产物自验证 | 错误直到用户启动游戏才暴露 |
| P1 | 英文游戏可能没有中文字体或东亚断行样式 | 方框、缺字、标点换行异常 |
| P1 | 提取结果只有 `List<String>` | 丢失说话人、文件、行号、类型和重复语境 |
| P1 | 相同 old 只保留一个 new | “Fine.” 等多义文本被错误统一翻译 |
| P1 | sentinel 只检查存在，不严格检查序列和嵌套 | 标签、变量或格式参数可能被模型破坏 |
| P1 | 缺少完整 lint 与覆盖率构建门禁 | 漏译和错误标签被打进 APK |
| P2 | 只复制 installed app 的 base APK | Split APK 游戏漏脚本、漏资源或安装失败 |
| P2 | 解压/解析上限不完整 | 大文件、畸形文件或压缩炸弹造成内存耗尽 |

---

## 2. 目标数据流

```text
用户选择 APK/已安装应用
  ↓
兼容性预检 RenpyCompatibilityReport
  ├─ 引擎/脚本格式与模板来源
  ├─ RPA、RPYC、Split APK、语言桶和菜单
  ├─ 激活策略：SELECTABLE_LANGUAGE / ALWAYS_ON / UNSUPPORTED
  ├─ 字体基础覆盖和资源安全预算
  └─ 支持等级：SAFE / WARNING / EXTRACT_ONLY / UNSUPPORTED
  ↓
结构化提取 List<RenpyTextRecord>
  ↓
精确去重、语境碰撞统计、公共引擎文本分类
  ↓
翻译缓存/本地模型/远程模型
  ↓
RenpyTextValidator：占位符、标签、插值、printf、空译文
  ↓
TranslationCoverageReport：已翻译、拒绝、缺失、碰撞、不确定项
  ↓
版本感知 RPYC 编译
  ↓
RenpyPatchValidator：槽位、解压、version/key、语言值、映射数量
  ↓
字体终检、APK 合并、签名、安装与启动验收
```

---

## 3. 阶段门禁

### P0：正确性门禁

完成 P0 后必须保证：

- 标准语言菜单游戏能选择“翻译文本”；
- 无菜单或不兼容菜单游戏能使用 `tl/None` 启动即翻译；
- 游戏脚本模板不会被 `x-common` 抢占；
- 未知/旧版写入能力不会被标记成成功；
- 写入 APK 前能解析并验证自己生成的 RPYC；
- 所有输入解析都有基本资源上限。

### P1：质量与可诊断性门禁

完成 P1 后必须保证：

- 每条语料具有来源、类型和出现位置；
- 占位符、文本标签、插值和 printf 参数可严格验证；
- 用户能看到唯一文本、出现次数、缺失数、拒绝数和碰撞数；
- 中文字体与东亚断行风险在构建前可见；
- 引擎公共 UI 与开发者/错误文本被分类处理；
- 构建报告能说明补丁为什么可用或为什么被阻止。

### P2：兼容范围门禁

完成 P2 后必须保证：

- 有测试夹具证明 Python 2/protocol 2 输出能被对应受限解析器接受；
- Split APK 可以完整扫描、统一签名并通过一个安装会话安装；
- 对重复原文可以选择高级对话 ID 翻译，而不破坏默认存档安全模式；
- 真实测试 APK 矩阵覆盖 Ren'Py 6/7/8、RPA/loose file、菜单/无菜单和 Split APK。

---

## Task 0：冻结基线与测试报告

**Files:**

- Read: `apk-work/ui-redesign/test_fast_scanner.py`
- Read: `apk-work/ui-redesign/test_translation_quality.py`
- Read: `apk-work/ui-redesign/test_translation_coverage.py`
- Read: `apk-work/ui-redesign/test_engine_performance.py`
- Create during execution: `docs/qa/renpy-optimization-baseline.md`

**Interfaces:**

- Produces: 一份记录测试命令、通过数、跳过原因、APK 构建产物和已知限制的只读基线。
- Consumes: 当前 56 通过、1 跳过的测试状态。

- [ ] **Step 1：运行当前核心测试**

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python -m unittest test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

期望：56 项或更多通过；允许的唯一跳过项必须明确说明缺少真实审计 APK/语料，不能出现失败。

- [ ] **Step 2：记录构建和测试环境**

在 `docs/qa/renpy-optimization-baseline.md` 写入日期、Python/Java 版本、测试总数、跳过项、当前 APK 版本和真实 APK 缺失项。不得把跳过测试写成已验证能力。

- [ ] **Step 3：确认工作树边界**

```powershell
git status --short
```

期望：只记录状态，不清理、不暂存、不覆盖任何用户文件。

---

## Task 1：无菜单游戏的 `tl/None` 默认激活模式

**Files:**

- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

- Add enum-like request value: `activationMode = "selectable" | "always_on"`。
- `selectable` produces `assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc` and `TranslateString.language = "slgtranslated"`。
- `always_on` produces `assets/x-game/x-tl/x-None/x-slgtranslator-translations.rpyc` and `TranslateString.language = null`，即 pickle `NONE` opcode，而不是字符串 `"None"`。
- Native result adds: `activationMode`, `translatorLanguage`, `compiledPath`。

- [ ] **Step 1：写失败测试，固定两种输出模式**

在 `test_fast_scanner.py` 增加 Java harness：使用同一组 `old/new` 分别调用 selectable 和 always-on 编译入口，断言输出路径分别包含 `x-slgtranslated` 和 `x-None`，并断言 always-on pickle 中 TranslateString 的 language 字段是 `NONE`。

- [ ] **Step 2：运行新测试并确认失败**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_compiler_supports_selectable_and_always_on_activation -v
```

期望：因缺少 `activationMode` 或始终写入 `slgtranslated` 而失败。

- [ ] **Step 3：增加 nullable pickle 字符串写入**

在 `TranslationCompiler` 增加：

```java
private static void writeNullableString(ByteArrayOutputStream out, String value) {
    if (value == null) {
        out.write(0x4e); // pickle NONE
        return;
    }
    writeString(out, value);
}
```

TranslateString 的 `language` 字段调用此方法；其他必填字符串继续调用 `writeString`。

- [ ] **Step 4：根据菜单结果选择激活策略**

前端规则固定为：

```text
标准 Ren'Py 菜单且注入成功     -> selectable
没有语言菜单                   -> always_on
自定义菜单且无法证明可切换      -> always_on
标准菜单注入失败               -> always_on
```

不得在 compiled count 大于 0 时把目标语言清空后又不给出默认加载策略。

- [ ] **Step 5：保护 app 自己的 `tl/None` 文件**

清理旧生成文件时只删除 `x-slgtranslator-translations.rpyc`，不得删除游戏原有的其他 `tl/None` 内容。

- [ ] **Step 6：更新完成页文案**

selectable 显示“请在游戏设置中选择翻译文本”；always-on 显示“此游戏不支持可靠的语言菜单注入，中文翻译将在启动时默认启用，游戏内不能切回原文”。

- [ ] **Step 7：运行局部与完整回归**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_compiler_supports_selectable_and_always_on_activation -v
python -m unittest test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

期望：新测试通过，既有测试无回归。

- [ ] **Step 8：精确提交（仅在已有安全 Git 基线时）**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "fix: activate translations when renpy menu is unavailable"
```

---

## Task 2：游戏脚本模板优先选择

**Files:**

- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

- Add: `static int templatePriority(String zipPath)`。
- Priority order, lower is better:
  - `0`: `assets/x-game/` 或 `assets/game/` 下非 `tl` `.rpyc`
  - `10`: 同一游戏目录下的 `tl` `.rpyc`
  - `20`: 其他游戏资源 `.rpyc`
  - `100`: `assets/x-renpy/x-common/` 或 `assets/renpy/common/`
  - `Integer.MAX_VALUE`: 不可用候选
- `TemplateMeta` adds: `sourcePath`, `selectionReason`。

- [ ] **Step 1：构造混合版本失败夹具**

测试 ZIP 同时包含：

```text
assets/x-renpy/x-common/common.rpyc  -> version=1, key=common-key
assets/x-game/x-tl/x-english/ui.rpyc -> version=2, key=game-key
assets/x-game/x-script.rpyc          -> version=2, key=game-key
```

断言最终模板为 `assets/x-game/x-script.rpyc`。

- [ ] **Step 2：运行测试并确认当前选择不稳定**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_template_meta_prefers_game_script_over_common_and_tl -v
```

- [ ] **Step 3：实现稳定排序**

先收集候选，再按 `templatePriority(path)`、规范化路径字典序排序，最后读取第一项；禁止依赖 ZIP central directory 的原始顺序。

- [ ] **Step 4：拒绝明显不一致的游戏模板集合**

如果最高优先级游戏脚本中同时出现多个 `version/key` 组合，返回诊断错误并列出候选路径，不随机选择。

- [ ] **Step 5：将模板来源写入原生结果**

结果 JSON 增加：

```json
{
  "templatePath": "assets/x-game/x-script.rpyc",
  "templateVersion": 2,
  "templateSource": "game-script"
}
```

- [ ] **Step 6：运行回归并精确提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_template_meta_prefers_game_script_over_common_and_tl -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "fix: select renpy template metadata from game scripts"
```

---

## Task 3：RPYC/pickle 能力识别和保守失败

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RpycCompatibility {
    public enum GenerationSupport {
        MODERN_SUPPORTED,
        LEGACY_EXTRACT_ONLY,
        UNKNOWN_EXTRACT_ONLY
    }

    public static Report inspect(byte[] rpyc);

    public static final class Report {
        public final String container;      // rpc2 | legacy-zlib
        public final int preferredSlot;     // 2 | 1
        public final int pickleProtocol;    // 0..5 or -1
        public final boolean usesBuiltins;
        public final boolean usesPy2Builtins;
        public final GenerationSupport generationSupport;
        public final String reason;
    }
}
```

- [ ] **Step 1：增加现代、Python 2 和未知三类夹具**

现代夹具包含 `builtins`/现代全局引用；Python 2 夹具包含 `__builtin__` 与 protocol 2 全局引用；未知夹具使用项目不认识的 GLOBAL/extension 组合。

- [ ] **Step 2：写失败测试固定支持等级**

断言：现代模板为 `MODERN_SUPPORTED`，Python 2 为 `LEGACY_EXTRACT_ONLY`，未知为 `UNKNOWN_EXTRACT_ONLY`。

- [ ] **Step 3：实现只读能力扫描**

扫描 RPYC 首选槽位的 pickle 协议头和受关注 GLOBAL 名称，不执行任意 pickle，不实例化目标类，不把 protocol 2 单独当成 Python 2 的充分条件。

- [ ] **Step 4：在编译前加入支持等级门禁**

只有 `MODERN_SUPPORTED` 可以进入当前 writer。其他等级返回：

```json
{
  "supportLevel": "extract_only",
  "reasonCode": "legacy_pickle_writer_required",
  "message": "可以提取和翻译，但当前版本不能为该 Ren'Py/Python 版本安全生成翻译脚本。"
}
```

- [ ] **Step 5：确保提取功能不被门禁阻断**

编译门禁不得影响 `RpycTextExtractor.extractTexts`；老游戏仍能导出语料和翻译 JSON。

- [ ] **Step 6：运行测试与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_rpyc_compatibility_separates_modern_legacy_and_unknown_generation -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: detect renpy generation compatibility before compiling"
```

---

## Task 4：编译产物自验证

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPatchValidator.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RenpyPatchValidator {
    public static Result validateCompiledRpyc(
            byte[] rpyc,
            int expectedVersion,
            String expectedKey,
            String expectedLanguage,
            int expectedPairCount);

    public static final class Result {
        public final boolean valid;
        public final String code;
        public final String message;
        public final int decodedPairCount;
    }
}
```

`expectedLanguage == null` 表示 always-on 的 `tl/None` 模式。

- [ ] **Step 1：写一个正常和四个损坏产物测试**

损坏类型固定为：槽位长度越界、zlib 截断、version 不匹配、language 错误、映射数量不足。每种必须返回稳定 `code`。

- [ ] **Step 2：运行测试并确认 validator 不存在**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_compiled_rpyc_validator_rejects_corrupt_or_mismatched_outputs -v
```

- [ ] **Step 3：实现受限验证器**

验证器只解析项目 writer 会生成的 pickle 子集；不得调用 Python pickle 或反序列化任意 Java 对象。检查：

```text
RENPY RPC2 header
槽 2/槽 1 offset 与 length 边界
zlib 完整结束
data.version == expectedVersion
data.key == expectedKey
TranslateString.language == expectedLanguage
TranslateString 条数 == expectedPairCount
每个 old/new 均为非 null 字符串
```

- [ ] **Step 4：把验证放在 APK 合并之前**

`compileRpyc(...)` 返回后立即调用 validator。失败时删除/放弃临时产物，`PluginCall.reject` 返回稳定错误码，禁止继续签名。

- [ ] **Step 5：回归与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_compiled_rpyc_validator_rejects_corrupt_or_mismatched_outputs -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPatchValidator.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: validate generated renpy scripts before apk merge"
```

---

## Task 5：不可信输入的统一资源预算

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyResourceLimits.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpaArchive.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RenpyResourceLimits {
    public static final long MAX_SINGLE_SCRIPT_COMPRESSED = 64L * 1024 * 1024;
    public static final long MAX_SINGLE_SCRIPT_INFLATED = 256L * 1024 * 1024;
    public static final long MAX_TOTAL_SCRIPT_INFLATED = 1024L * 1024 * 1024;
    public static final int MAX_RPA_ENTRIES = 200_000;
    public static final int MAX_TEXT_RECORDS = 1_000_000;
    public static final int MAX_TEXT_LENGTH = 1_000_000;
    public static final int MAX_INFLATE_RATIO = 200;
}
```

实际常量如因 Android 低内存设备需要降低，只能整体收紧；提高上限必须有测试和内存依据。

- [ ] **Step 1：增加压缩炸弹、伪造长度和超多条目测试**

夹具只需要用小型数据伪造声明长度/压缩比，不在测试中真的分配数百 MB。

- [ ] **Step 2：实现流式计数解压**

所有 inflate 循环每次写入前检查累计输出、压缩比和线程中断状态；不能调用无界 `readAllBytes` 或按不可信 length 直接分配数组。

- [ ] **Step 3：限制 RPA 索引和条目读取**

拒绝负 offset、负 length、`offset + length` 溢出、超出归档边界、条目数超限和路径穿越形式。

- [ ] **Step 4：返回可诊断错误**

错误码固定为 `renpy_limit_compressed`、`renpy_limit_inflated`、`renpy_limit_ratio`、`renpy_limit_entries`、`renpy_invalid_range`，UI 不显示 Java 堆栈。

- [ ] **Step 5：运行回归与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_resource_limits_reject_bombs_and_invalid_ranges -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyResourceLimits.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpaArchive.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "fix: bound renpy archive and script parsing resources"
```

---

## Task 6：结构化 Ren'Py 文本记录

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTextRecord.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RenpyTextRecord {
    public enum Kind {
        DIALOGUE, MENU, CHARACTER_NAME, UI_STRING,
        TRANSLATION_OLD, CUSTOM_STATEMENT, UNKNOWN
    }

    public final String text;
    public final Kind kind;
    public final String speaker;
    public final String identifier;
    public final String sourcePath;
    public final int sourceLine;     // unknown is -1
    public final int occurrence;
    public final boolean coverageCertain;
}
```

```java
public static List<RenpyTextRecord> extractRecords(
        byte[] rpyc, String sourcePath, boolean onlyOld);
```

现有 `extractTexts(...)` 保留，内部投影 `extractRecords(...).text`，以免一次性破坏调用方。

- [ ] **Step 1：写结构化夹具测试**

夹具包含对话、菜单、角色名、`old/new` 和来源文件字符串。断言 `text/kind/sourcePath/occurrence`，无法可靠恢复的字段使用空字符串或 `-1`，不得编造。

- [ ] **Step 2：实现记录模型和兼容适配层**

先把现有提取分支改为产出 record，再由旧 API 去重返回字符串。`onlyOld=true` 时只产出 `TRANSLATION_OLD`，不返回 `new` 或翻译后的 `what`。

- [ ] **Step 3：把 sourcePath 贯穿 RPA 虚拟路径**

RPA 内部脚本使用：

```text
assets/x-game/archive.rpa!/game/chapter1.rpyc
```

不得只记录归档文件名或丢失内部路径。

- [ ] **Step 4：原生桥接同时返回旧字符串和新 records**

过渡期 JSON 保留当前字段，并新增 `renpyRecords`；前端未升级时仍可工作。

- [ ] **Step 5：运行回归与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_rpyc_extractor_returns_structured_records_without_breaking_text_api -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTextRecord.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: preserve renpy text context during extraction"
```

---

## Task 7：对齐官方标记字符串覆盖面

**Files:**

- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Update: `docs/translation-extraction-rules.md`

**Interfaces:**

- Recognize: `_()`、`__()`、`___()`、`_p()`。
- Support: 单引号、双引号、三单引号、三双引号、合法字符串前缀。
- `_p` 至少保留 context 与可见文本的关联；不能把 context 本身作为普通可见文本发送翻译。
- Never strip `{#...}` before exact-key deduplication。

- [ ] **Step 1：增加官方语法覆盖夹具**

测试源字符串包含：

```renpy
_('single')
__("double")
___('''multi\nline''')
_(r"raw text")
_p("menu-context", "Continue")
```

断言提取出五个可见文本，`menu-context` 只作为上下文保存。

- [ ] **Step 2：实现确定性词法扫描而非单个贪婪正则**

扫描函数必须处理转义、引号类型和括号层级。已有 `splitCallArgs` 可以复用，但调用名、字符串字面量读取和三引号终止应拆成小函数。

- [ ] **Step 3：增加 `{#}` 精确键测试**

`"Save{#slot}"` 与 `"Save{#menu}"` 必须是两个独立 key；可以在运行查找回退阶段去标签，但不能在缓存/编译前合并。

- [ ] **Step 4：记录静态覆盖不确定项**

遇到无法静态理解的 UserStatement 或动态 `_()` 参数时，增加 `coverageCertain=false` 的诊断记录，不把表达式源码当译文。

- [ ] **Step 5：运行测试、更新规则文档并提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_rpyc_extractor_matches_official_marked_string_forms -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java apk-work/ui-redesign/test_fast_scanner.py docs/translation-extraction-rules.md
git commit -m "feat: cover official renpy marked string forms"
```

---

## Task 8：语境碰撞检测和结构化翻译语料

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTranslationCorpus.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/LocalTranslationSupport.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_translation_quality.py`
- Test: `apk-work/ui-redesign/test_translation_coverage.py`

**Interfaces:**

```java
public final class RenpyTranslationCorpus {
    public static Corpus build(List<RenpyTextRecord> records);

    public static final class Entry {
        public final String exactOld;
        public final List<RenpyTextRecord> occurrences;
        public final boolean contextualCollision;
    }
}
```

碰撞定义：同一 `exactOld` 出现在不同 speaker、identifier、kind 或 sourcePath 中；不能因为出现次数大于 1 就自动判为语义冲突。

- [ ] **Step 1：写重复和碰撞测试**

同一场景重复两次 `OK` 只计重复；`Fine.` 分别由两个角色在两个文件中说出，计为碰撞。

- [ ] **Step 2：实现 exactOld 聚合**

聚合键必须包含完整 `{#...}`；保存所有 occurrence，不再在提取早期丢弃第二个位置。

- [ ] **Step 3：把多语境传入模型提示**

碰撞文本的 prompt 最多列出前三个代表语境，要求给出能覆盖所有语境的中性译法。语境超过三个时显示总数，不无限扩大 prompt。

- [ ] **Step 4：禁止静默覆盖不同译文**

编译前若同一 exactOld 对应多个不同 new，返回 `translation_collision_conflict`，列出 old 和候选译文；不再依赖 `putIfAbsent` 静默保留第一项。

- [ ] **Step 5：在 UI 显示重复与碰撞**

至少显示：唯一原文、总出现次数、重复条目、潜在语境碰撞。碰撞项可以导出 JSON 供人工校对。

- [ ] **Step 6：运行测试与提交**

```powershell
python -m unittest test_translation_quality.py test_translation_coverage.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTranslationCorpus.java apk-work/native-fast-scan/src/com/slgtranslator/app/LocalTranslationSupport.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_translation_quality.py apk-work/ui-redesign/test_translation_coverage.py
git commit -m "feat: report renpy translation context collisions"
```

---

## Task 9：严格占位符和 Ren'Py 文本 lint

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTextValidator.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/LocalLlmEngine.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_translation_quality.py`
- Update: `docs/translation-quality-rules.md`

**Interfaces:**

```java
public final class RenpyTextValidator {
    public static ValidationResult validate(String oldText, String newText);

    public static final class ValidationResult {
        public final boolean valid;
        public final List<String> codes;
    }
}
```

错误码至少包含：`empty_translation`、`sentinel_missing`、`sentinel_extra`、`sentinel_reordered`、`tag_unbalanced`、`tag_misnested`、`interpolation_changed`、`printf_changed`、`unrestored_sentinel`。

- [ ] **Step 1：固定 sentinel 精确序列规则**

测试以下情况全部拒绝：少一个、多一个、重复一个、顺序交换、哨兵文本残留。正确翻译必须通过。

- [ ] **Step 2：修改 `restorePlaceholders`**

恢复前从模型输出中提取所有 `__SLGPH<n>__`，与 guard 的期望序列逐项比较；只有数量、编号和顺序完全一致才恢复。

- [ ] **Step 3：实现文本标签栈验证**

对 `{b}`、`{/b}`、`{i}`、`{/i}`、`{font=...}`、`{/font}` 等成对标签使用栈；自闭合/状态标签按 Ren'Py 支持集合分类。交叉闭合如 `{b}{i}x{/b}{/i}` 必须拒绝。

- [ ] **Step 4：验证插值和 printf**

从 old/new 提取规范化 token：`[expression]`、`%(name)s`、`%s`、`%d`、`%1$s`。名称、类型、数量和顺序必须符合各自规则。

- [ ] **Step 5：接入模型接受和编译双门禁**

模型输出先验证；编译前对缓存和人工导入译文再验证一次。失败结果保留 old、new、错误码和来源，不能进入 RPYC。

- [ ] **Step 6：运行测试、更新规则文档并提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_local_llm_placeholder_guard_preserves_markup_and_format -v
python -m unittest test_fast_scanner.py test_translation_quality.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyTextValidator.java apk-work/native-fast-scan/src/com/slgtranslator/app/LocalLlmEngine.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/test_fast_scanner.py apk-work/ui-redesign/test_translation_quality.py docs/translation-quality-rules.md
git commit -m "feat: lint renpy markup and interpolation before compiling"
```

---

## Task 10：覆盖率报告、构建门禁和公共文本分类

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCoverageReport.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_translation_coverage.py`

**Interfaces:**

```java
public final class TranslationCoverageReport {
    public final int uniqueSourceCount;
    public final int occurrenceCount;
    public final int translatedCount;
    public final int missingCount;
    public final int rejectedCount;
    public final int collisionCount;
    public final int uncertainCount;
    public final Map<String, FileCoverage> files;
}
```

构建策略：`missingCount > 0` 或 `rejectedCount > 0` 时默认阻止“完整补丁”构建；用户可以选择“生成不完整测试补丁”，但完成页必须持续显示警告，不能标记为完整翻译。

- [ ] **Step 1：写覆盖率集合运算测试**

使用 exactOld 集合与已通过 validator 的译文集合做差；缓存存在但验证失败的条目计入 rejected，不得计入 translated。

- [ ] **Step 2：按文件和类型分组**

每个文件返回 source/translated/missing/rejected，UI 展示缺失最多的前 20 个文件和可导出的完整 JSON。

- [ ] **Step 3：分类 `x-common`**

默认策略：游戏剧情和游戏 UI 包含；Ren'Py 用户可见公共设置文本可选；开发者控制台、内部错误、过时文本跳过。分类原因写入 record，不能仅凭“是不是 common”全部丢弃。

- [ ] **Step 4：实现增量缓存差集**

新扫描只向模型发送：新 exactOld、旧缓存缺失、旧缓存验证失败或用户显式重译的条目。原文完全相同且译文验证通过时直接复用。

- [ ] **Step 5：恢复真实 APK 审计门禁**

为 `test_audit_pins_the_verified_missing_set` 配置可选本地 fixture 路径；fixture 存在时必须断言 `missing == 0`，不存在时继续明确跳过，不伪造数据。

- [ ] **Step 6：运行覆盖率测试与提交**

```powershell
python -m unittest test_translation_coverage.py test_translation_quality.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCoverageReport.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_translation_coverage.py
git commit -m "feat: gate renpy builds on validated translation coverage"
```

---

## Task 11：中文字体覆盖和东亚断行诊断

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyFontSupport.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RenpyFontSupport {
    public static FontReport inspect(
            Context context,
            File apk,
            Set<Integer> requiredCodePoints);

    public static final class FontReport {
        public final List<String> candidateFonts;
        public final String bestFontPath;
        public final int requiredCount;
        public final int coveredCount;
        public final List<Integer> missingCodePoints;
        public final boolean hasChineseStyleBucket;
        public final boolean hasEastAsianLineBreakEvidence;
    }
}
```

- [ ] **Step 1：准备测试字体夹具**

使用许可证允许纳入测试仓库的小型字体子集：一个不含汉字，一个含测试所需汉字。测试只验证选优和缺字报告，不把测试字体打入最终 APK。

- [ ] **Step 2：提取候选字体并检查 glyph**

把 APK 内候选字体流式复制到 app 私有临时文件，`Typeface.createFromFile` 加载后使用 `Paint.hasGlyph` 检查 required code points；完成后删除临时文件。

- [ ] **Step 3：执行两次检查**

预检阶段使用固定基础中文/标点集合；翻译结束后使用全部译文中去重的非 ASCII code points 做终检。

- [ ] **Step 4：定义构建行为**

```text
100% 覆盖                         -> 通过
有缺字但游戏已有其他可选字体       -> 切换到覆盖最高字体并警告
仍有缺字且未配置合法补充字体        -> 阻止完整补丁构建
```

不得自动打包来源和许可证不明的系统字体。

- [ ] **Step 5：处理样式和断行**

优先复用游戏已有中文 translate style；没有时只对已验证兼容的模板生成最小样式覆盖，并设置东亚断行。无法安全生成样式时至少发出明确警告，不把字体覆盖等同于正确排版。

- [ ] **Step 6：测试与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_font_report_detects_missing_translation_glyphs -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyFontSupport.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: preflight renpy chinese font and line break support"
```

---

## Task 12：统一兼容性预检报告和 UI

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RenpyCompatibilityReport {
    public enum SupportLevel { SAFE, WARNING, EXTRACT_ONLY, UNSUPPORTED }
    public enum ActivationStrategy { SELECTABLE_LANGUAGE, ALWAYS_ON, NONE }

    public final SupportLevel supportLevel;
    public final ActivationStrategy activationStrategy;
    public final String templatePath;
    public final RpycCompatibility.Report rpyc;
    public final int rpaCount;
    public final int splitCount;
    public final List<String> languageBuckets;
    public final String menuType;
    public final RenpyFontSupport.FontReport font;
    public final int uniqueTextCount;
    public final int occurrenceCount;
    public final int collisionCount;
    public final List<Issue> issues;
}
```

- [ ] **Step 1：写三种报告快照测试**

夹具：现代标准菜单=SAFE/selectable，无菜单=WARNING/always-on，旧 Python 2=EXTRACT_ONLY/none。

- [ ] **Step 2：实现单一预检入口**

`RenpyPreflight.inspect(Context, SourceSet)` 组合已有扫描结果，不重复解压同一脚本；预检必须在调用远程/本地模型之前完成。

- [ ] **Step 3：UI 显示固定诊断字段**

至少显示：脚本格式/槽位、模板路径、RPA 版本与数量、Split 数量、语言桶、菜单类型、激活策略、字体覆盖、唯一文本、总出现、碰撞、支持等级和阻断原因。

- [ ] **Step 4：支持报告导出**

导出 JSON 不包含 APK 内容、翻译 API key、完整脚本或用户隐私数据；只包含路径、计数、版本特征和错误码。

- [ ] **Step 5：测试与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only -v
python -m unittest test_fast_scanner.py test_translation_coverage.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: show renpy compatibility preflight before translation"
```

---

## Task 13：真正的 Python 2 / protocol 2 受限 writer

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RpycPickleWriter {
    public enum Dialect { PY2_PROTOCOL_2, PY3_MODERN }

    public static byte[] buildTranslationPickle(
            Dialect dialect,
            String language,
            String filename,
            List<String[]> pairs,
            int version,
            String key);
}
```

PY2 writer 只允许 protocol 2 opcode：`PROTO 2`、`GLOBAL`、`BINUNICODE`、`BINPUT/LONG_BINPUT`、`TUPLE`/`TUPLE1`、`REDUCE`、`BUILD` 等；不得输出 `SHORT_BINUNICODE`、`STACK_GLOBAL` 或模块名 `builtins`，应使用目标模板要求的 `__builtin__`。

- [ ] **Step 1：把现有 writer 移出 `TranslationCompiler`**

先保持现代输出字节级一致，用 golden fixture 固定迁移前后结果，避免重构与兼容改动混在一起。

- [ ] **Step 2：写 Python 2 方言失败测试**

断言输出不含 `0x8c`（SHORT_BINUNICODE）、`0x93`（STACK_GLOBAL）和 `builtins`，包含 protocol 2 允许的 GLOBAL 与 `__builtin__`。

- [ ] **Step 3：实现 protocol 2 opcode 写入**

字符串统一以 UTF-8 `BINUNICODE` 写入并使用 4 字节 little-endian 长度；GLOBAL 使用换行分隔的模块名和类名；memo 指令不得超出 protocol 2。

- [ ] **Step 4：用独立受限读取器验证对象图**

测试读取器只接受计划允许的 opcode，验证 version/key、Init、TranslateString、Return 和字段，不执行 GLOBAL 指向的类。

- [ ] **Step 5：升级能力矩阵**

只有通过对应 fixture 和 validator 的 Python 2 特征从 `LEGACY_EXTRACT_ONLY` 升级为可生成；未知特征继续 extract-only。

- [ ] **Step 6：运行测试与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_protocol2_writer_uses_only_python2_compatible_opcodes -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: generate restricted protocol2 renpy translation scripts"
```

---

## Task 14：Split APK 完整扫描、重签名和会话安装

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledApkSet.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledAppSource.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/PackageInstallerSupport.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class InstalledApkSet {
    public final File baseApk;
    public final List<File> splitApks;
    public final String packageName;
    public final long versionCode;
}
```

`PackageInstallerSupport.installApkSet(Context, InstalledApkSet, PluginCall)` 必须在一个 session 内写入 base 和全部 split。

- [ ] **Step 1：写 base + 两个 split 的扫描夹具**

base 含 manifest，split A 含 `assets/game/chapter.rpyc`，split B 含字体。断言预检合并看到脚本和字体，同时记录原始所属 APK。

- [ ] **Step 2：复制已安装应用的完整 APK 集合**

`sourceDir` 作为 base，`splitSourceDirs` 每项单独复制到 app 私有目录；使用显式文件列表和 `.partial` 原子完成，不把多个 APK 拼成一个文件。

- [ ] **Step 3：定义补丁位置**

优先修改 base；如果目标游戏资源只存在于特定 split，预检必须证明 loose file 在 base 的 loader 命名空间可见，否则修改对应 split。所有输出使用同一签名。

- [ ] **Step 4：一个 session 安装全部 APK**

写入顺序固定 base 后 split；提交前验证 packageName、versionCode、splitName 和签名一致。任一项失败时 abandon session。

- [ ] **Step 5：UI 显示集合状态**

明确显示 base、split 数量、复制进度、补丁所在包和会话安装结果；不能只显示 `splitApk=true` 警告后继续按单 APK 安装。

- [ ] **Step 6：测试与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_split_apk_set_scans_assets_and_installs_in_one_session -v
python -m unittest test_fast_scanner.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledApkSet.java apk-work/native-fast-scan/src/com/slgtranslator/app/InstalledAppSource.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/native-fast-scan/src/com/slgtranslator/app/PackageInstallerSupport.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: patch and install complete renpy split apk sets"
```

---

## Task 15：高级对话 ID 翻译模式

**Files:**

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialogueTranslation.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

```java
public final class RenpyDialogueTranslation {
    public final String identifier;
    public final String speakerExpression;
    public final String oldText;
    public final String newText;
    public final String sourcePath;
    public final int sourceLine;
}
```

默认模式继续使用全局字符串映射；只有 extractor 能可靠恢复官方 identifier、writer 明确支持目标 AST 版本且用户开启高级模式时，才生成逐对话翻译。

- [ ] **Step 1：建立两个相同 old、不同 identifier 的夹具**

同一原文 `Fine.` 分别对应两个标识符和两个译文，断言高级模式不会合并。

- [ ] **Step 2：只读取现有 identifier，不猜测缺失 ID**

如果目标 RPYC 中已有 TranslateSay/identifier，直接保留；无法可靠恢复时继续使用字符串模式并报告原因。

- [ ] **Step 3：生成目标版本支持的对话 AST**

writer 只实现已经由 fixture 验证的字段形状；不能依据当前 master 类字段向所有旧版本写入。

- [ ] **Step 4：保留菜单和 UI 的字符串翻译**

高级模式是 dialogue ID + string map 混合模式，不应让菜单、角色名和 `_()` UI 字符串失去翻译。

- [ ] **Step 5：验证存档和 rollback**

至少使用一个测试游戏分别验证新游戏、旧存档加载、rollback、跳转和切换语言；失败时产品默认关闭高级模式。

- [ ] **Step 6：测试与提交**

```powershell
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_dialogue_id_mode_preserves_context_specific_translations -v
python -m unittest test_fast_scanner.py test_translation_quality.py -v
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialogueTranslation.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: support context specific renpy dialogue translations"
```

---

## Task 16：发布级测试矩阵和完成定义

**Files:**

- Create: `docs/qa/renpy-compatibility-matrix.md`
- Create: `docs/qa/renpy-release-checklist.md`
- Modify: `apk-work/ui-redesign/test_translation_coverage.py`
- Modify: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**

- Produces: 机器测试矩阵、人工真机检查表、每个样本的预检报告和失败证据。
- Consumes: Tasks 1–15 的兼容性报告、覆盖率报告和 validator 结果。

- [ ] **Step 1：建立最小样本矩阵**

矩阵至少包含：

| 维度 | 样本 |
|---|---|
| Ren'Py/Python | 6/Python 2、7/Python 2、8/Python 3、未知/不支持 |
| 脚本容器 | loose RPYC2、RPA-1、RPA-2、RPA-3、legacy zlib |
| 语言激活 | 标准菜单、自定义菜单、无菜单、菜单注入失败 |
| 字体 | 已有中文字体、缺中文字体、部分缺字 |
| 安装 | 单 APK、base + split |
| 语料 | 对话、菜单、角色名、UI、`{#}`、插值、printf、重复语境 |

- [ ] **Step 2：为每个样本保存预期结果**

每项记录：supportLevel、activationStrategy、templatePath、文本计数、缺失数、字体结果、构建是否允许、安装是否成功和启动是否显示译文。

- [ ] **Step 3：运行全量自动化测试**

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python -m unittest discover -s . -p 'test_*.py' -v
```

期望：无失败；任何跳过都必须在矩阵中有明确的外部条件说明。

- [ ] **Step 4：构建 APK**

```powershell
python build_workshop_apk.py
```

期望：构建成功、签名验证通过、原生 helper dex 包含新增类，版本号按产品发布规则更新。

- [ ] **Step 5：执行真机冒烟测试**

每种激活模式至少验证：扫描 → 翻译 → lint → 编译 → 签名 → 安装 → 启动 → 看到译文 → 加载旧存档。selectable 还要验证切回原文；always-on 要验证完成页文案准确。

- [ ] **Step 6：发布门禁**

只有以下条件全部满足才把版本标记为可发布：

```text
自动化测试无失败
真实样本 missing == 0 或用户明确选择不完整测试补丁
rejected == 0
编译产物 validator 通过
字体终检通过
语言激活已在真机证明
安装/存档回归通过
不支持样本被正确阻止，而不是崩溃或伪成功
```

- [ ] **Step 7：提交 QA 文档（仅在安全 Git 基线时）**

```powershell
git add docs/qa/renpy-compatibility-matrix.md docs/qa/renpy-release-checklist.md apk-work/ui-redesign/test_translation_coverage.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "test: add renpy compatibility release matrix"
```

---

## 4. 建议执行批次

### 批次 A：先解决伪成功和崩溃风险

按顺序执行 Task 0–5：

1. 冻结基线；
2. `tl/None` 激活回退；
3. 模板优先级；
4. 能力识别和 extract-only；
5. 产物自验证；
6. 资源预算。

批次 A 完成后即可发布一个“更诚实、更不容易生成坏包”的版本。

### 批次 B：提升翻译覆盖和用户可诊断性

按顺序执行 Task 6–12：

1. 结构化语料；
2. 官方标记字符串覆盖；
3. 碰撞检测；
4. 严格文本 lint；
5. 覆盖率门禁；
6. 字体/断行；
7. 兼容性预检 UI。

批次 B 完成后，产品能解释“翻译了什么、漏了什么、为什么可以构建”。

### 批次 C：扩展旧引擎和安装形态

按顺序执行 Task 13–16：

1. Python 2/protocol 2 writer；
2. Split APK；
3. 高级对话 ID；
4. 发布级兼容矩阵。

批次 C 的每项都应独立发布，不能把老版本 writer、Split APK 和对话 ID 三个高风险改动放进同一个未经验证的版本。

---

## 5. 不实施的方向

- 不在 Android 应用中嵌入完整 Ren'Py 引擎来编译用户游戏。
- 不为了强制切换语言而生成任意版本相关的 Python 字节码。
- 不修改原始标签、jump/call、条件分支或游戏流程来完成普通字符串翻译。
- 不把随机模板 trailer 描述为“重新计算并通过官方校验”；archive-only 路径本来就不比较 `.rpy` digest。
- 不在去重前删除 `{#...}`。
- 不依赖“模型会遵守 prompt”代替确定性占位符和标签验证。
- 不默认翻译所有 `x-renpy/x-common` 开发者、错误和控制台文本。
- 不自动打包来源或许可证不明的字体。
- 不对未知格式尝试“尽量写入”；未知格式只允许扫描、导出和诊断。

---

## 6. 源码行为参考

- Ren'Py 仓库：<https://github.com/renpy/renpy>
- APK/RPA/语言路径加载：`renpy/loader.py`
- RPYC 槽位、version/key 和语言过滤：`renpy/script.py`
- 字符串翻译、`{#}` 回退和语言切换：`renpy/translation/__init__.py`
- 标记字符串扫描：`renpy/translation/scanstrings.py`
- 翻译生成、placeholder filter 和 missing 统计：`renpy/translation/generation.py`
- 对话、菜单和 Translate AST：`renpy/ast.py`
- 对话渲染时的字符串翻译：`renpy/character.py`
- 文本标签和东亚断行：`renpy/text/text.py`
- 字体加载和替换：`renpy/text/font.py`
- 官方 lint 行为：`renpy/lint.py`
- 存档结构和签名：`renpy/loadsave.py`

本地源码参考快照：`D:\文件翻译\_renpy-engine-ref`，日期为 2026-08-06；实施兼容逻辑时以目标 APK 行为和固定测试夹具为准，不以快照日期代替目标版本识别。

---

## 7. 文档自检结果

- 范围覆盖：语言激活、模板选择、版本能力、产物验证、资源限制、提取覆盖、语境碰撞、文本 lint、缺失统计、字体、预检、旧版 writer、Split APK、对话 ID 和发布矩阵均有对应任务。
- 边界一致：默认仍是安全字符串模式；`tl/None` 仅作为无可靠菜单时的显式 always-on 策略；未知版本始终保守失败。
- 类型一致：`RpycCompatibility.Report`、`RenpyTextRecord`、`TranslationCoverageReport`、`RenpyCompatibilityReport` 在后续任务中沿用同一命名。
- 验证闭环：每个功能任务都有失败测试、最小实现、局部回归和明确完成标准；最终 Task 16 执行全量测试、APK 构建和真机验证。
- 工作树安全：计划不要求清理现有文件，不使用宽泛暂存命令；提交步骤只在用户已经建立安全 Git 基线时执行。

