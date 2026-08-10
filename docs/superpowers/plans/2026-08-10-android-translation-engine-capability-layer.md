# Android Translation Engine Capability Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不增加新 APK writer 的前提下，将引擎检测、结构化提取、翻译、回写和激活能力分层，使现有 `EXTRACT_ONLY` Ren'Py APK 可以完成模型翻译、缓存、校验和通用 JSON 导出，同时继续阻断 RPYC 编译、APK 构建和安装。

**Architecture:** 新增不可变的 `EngineCapabilities` 与最小泛型 `EngineAdapter`/`WriterBackend` 契约，用 `RenpyEngineAdapter` 和 `RenpyRpycWriter` 包装现有 Ren'Py 判断，不迁移或重写现有提取器与 writer。扫描响应追加 `adapterId`、`workflow`、`capabilities`、`projectFingerprint` 和稳定 `recordId`；前端按能力而不是单一支持等级决定模型调用与 writer 调用。通用翻译项目由前端组装、原生端严格校验并写入 Downloads，导入结果只恢复匹配记录，不匹配记录进入待确认集合。

**Tech Stack:** Java 8、Android/Capacitor `PluginCall`/`JSObject`、`org.json`、MediaStore Downloads、Python `unittest`、Node.js 行为测试、javac Java harness、D8/dexdump、APKTool、ADB。

## Global Constraints

- 保留 `SAFE / WARNING / EXTRACT_ONLY / UNSUPPORTED`，不通过删除门禁提升表面兼容率。
- `EXTRACT_ONLY` 在新能力模型中映射为 `TRANSLATABLE_NO_PATCH`：允许结构化提取、翻译、校验、缓存和导出；禁止 writer、APK 构建、安装和“汉化完成”文案。
- `UNSUPPORTED` 继续在提取、模型、writer、构建和安装之前阻断。
- `SAFE` 与 `WARNING` 的现有 Ren'Py 翻译、RPYC 编译、APK 构建、签名和安装行为必须保持不变。
- 现有桥接字段 `supportLevel`、`compatibilityReason`、`reasonCode`、`compatibilityReport`、`compatibilityGate`、`rpycContainer`、`splitCount` 必须继续返回；新字段只能追加。
- 旧前端忽略新字段时继续依赖 `compatibilityGate=extract_only` 失败关闭；新前端优先读取 `capabilities`，缺失时按旧 `supportLevel` 推导。
- 新 Java 类保持在 `com.slgtranslator.app` 包内，使用 `-source 8 -target 8 -encoding UTF-8`，不调整现有 package 或 DEX 分层。
- 本阶段不增加 Ren'Py 老版本 writer、Android resources writer、结构化文本 writer、Unity writer、DEX/native hook 或 OCR。
- 通用项目格式固定 `schemaVersion: 1`，记录保留 `recordId`、`sourceOwner`、`sourcePath`、`resourceType`、`sourceKey`、`sourceText`、`translation`、`validation`。
- 导入必须校验 schema、项目指纹、adapter、源版本、recordId、原文、占位符和标签；不匹配记录不得自动进入可写集合。
- 翻译缓存增加 `adapterId`、`recordSchemaVersion` 和 `projectFingerprint` 命名空间；旧 Ren'Py exact-old/file cache 只读兼容，不把旧定位验证结果跨引擎复用。
- 导出内容最大 16 MiB、记录最多 200,000 条、单字段最大 64 KiB；超限必须返回稳定错误，不允许无限制解析用户 JSON。
- writer 永不覆盖源 APK；导出失败时清理未完成的 MediaStore 行。
- 不修改或回退工作区已有改动；每次提交只暂存当前任务列出的文件。
- 测试命令从 `D:\文件翻译\apk-work\ui-redesign` 运行；真机构建命令从对应脚本目录运行。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/EngineCapabilities.java` — 通用能力位、工作流枚举和旧支持等级映射。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/EngineAdapter.java` — 最小泛型 adapter 契约。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WriterBackend.java` — 最小泛型 writer 能力契约。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyEngineAdapter.java` — 现有 Ren'Py 报告到能力模型的包装器。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java` — 只声明现有已验证 RPYC writer 支持范围，不新增方言。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationProjectSupport.java` — schema 1 校验、导入匹配和 Downloads JSON 导出。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java:12-107` — 暴露翻译阻断与 writer 阻断的不同语义。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java:57-128` — 通过 Ren'Py adapter 生成能力，不改变原支持等级结论。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java:152-280,398-460,1138-1252` — 扫描能力、项目指纹、source owner 和 record ID 序列化。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java:58-86,700-805` — 在 writer 边界返回稳定阻断结果，保持已验证 writer 路径不变。
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py:230-405,920-977` — 注入翻译项目导出/导入桥接并验证唯一性。
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:475-531,853-1052,1244-1300,1536-1573,1734-1905,2357-2408,2501-2510` — 新能力状态、翻译导出流程、导入、缓存和 UI 完成状态。
- Modify: `apk-work/ui-redesign/test_fast_scanner.py:2368-2435,5772-5948` — Java 契约、扫描字段、桥接和 DEX 回归。
- Modify: `apk-work/ui-redesign/test_workshop_patch.py:2357-2405,2766-2824,3512-3730,4109-4320` — 可翻译无 writer 行为、导出状态、导入和会话兼容。
- Modify: `apk-work/ui-redesign/test_translation_memory.py` — 缓存 schema 与旧缓存只读恢复测试。
- Modify: `docs/qa/renpy-release-checklist.md` — 增加 `TRANSLATABLE_NO_PATCH` 发布验收项和真机证据字段。

## Tasks

### Task 1: 建立能力模型并拆分翻译门禁与 writer 门禁

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/EngineCapabilities.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java:12-107`
- Test: `apk-work/ui-redesign/test_fast_scanner.py:5772-5866`

**Interfaces:**
- Produces: `EngineCapabilities.Workflow`，值固定为 `PATCHABLE_VERIFIED`、`PATCHABLE_EXPERIMENTAL`、`TRANSLATABLE_NO_PATCH`、`EXTRACTABLE_ONLY`、`UNSUPPORTED`。
- Produces: `EngineCapabilities.forRenpy(RenpyCompatibilityReport.SupportLevel, RenpyCompatibilityReport.ActivationStrategy, boolean) -> EngineCapabilities`。
- Produces: `RenpyCompatibilityReport.capabilities() -> EngineCapabilities`。
- Produces: `RenpyCompatibilityReport.isTranslationBlocked() -> boolean` 与 `isWriterBlocked() -> boolean`。
- Compatibility: `RenpyCompatibilityReport.isBlocked()` 保留，但语义改为 `isTranslationBlocked()`；调用方不得再用它判断 writer。

- [ ] **Step 1: 写失败的 Java harness 断言**

在 `test_renpy_preflight_reports_safe_warning_and_extract_only` 的 harness 中加入：

```java
EngineCapabilities safeCaps = safe.capabilities();
require(safeCaps.workflow == EngineCapabilities.Workflow.PATCHABLE_VERIFIED,
        "SAFE must remain patchable verified");
require(safeCaps.canTranslate && safeCaps.canWritePatch,
        "SAFE must translate and write");

EngineCapabilities legacyCaps = legacy.capabilities();
require(legacyCaps.workflow == EngineCapabilities.Workflow.TRANSLATABLE_NO_PATCH,
        "EXTRACT_ONLY must become translatable without patch");
require(legacyCaps.canExtractStructured && legacyCaps.canTranslate,
        "EXTRACT_ONLY must allow structured translation");
require(!legacyCaps.canWritePatch && !legacyCaps.canActivate,
        "EXTRACT_ONLY must keep writer and activation disabled");
require(!legacy.isTranslationBlocked() && legacy.isWriterBlocked(),
        "translation and writer gates must be independent");

require(unsupported.capabilities().workflow == EngineCapabilities.Workflow.UNSUPPORTED,
        "unsupported workflow must stay unsupported");
require(unsupported.isTranslationBlocked() && unsupported.isWriterBlocked(),
        "unsupported must block every downstream capability");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only -v`

Expected: FAIL during javac with `cannot find symbol: class EngineCapabilities` and missing `capabilities()`/`isWriterBlocked()`.

- [ ] **Step 3: 实现不可变能力模型**

创建 `EngineCapabilities.java`，核心实现固定为：

```java
package com.slgtranslator.app;

public final class EngineCapabilities {
    public enum Workflow {
        PATCHABLE_VERIFIED,
        PATCHABLE_EXPERIMENTAL,
        TRANSLATABLE_NO_PATCH,
        EXTRACTABLE_ONLY,
        UNSUPPORTED
    }

    public final boolean canDetect;
    public final boolean canExtractStructured;
    public final boolean canTranslate;
    public final boolean canWritePatch;
    public final boolean canActivate;
    public final boolean canValidateRuntime;
    public final Workflow workflow;

    private EngineCapabilities(boolean detect, boolean extract, boolean translate,
            boolean write, boolean activate, boolean validate, Workflow workflow) {
        this.canDetect = detect;
        this.canExtractStructured = extract;
        this.canTranslate = translate;
        this.canWritePatch = write;
        this.canActivate = activate;
        this.canValidateRuntime = validate;
        this.workflow = workflow == null ? Workflow.UNSUPPORTED : workflow;
    }

    public static EngineCapabilities forRenpy(
            RenpyCompatibilityReport.SupportLevel level,
            RenpyCompatibilityReport.ActivationStrategy activation,
            boolean writerAvailable) {
        if (level == RenpyCompatibilityReport.SupportLevel.SAFE
                || level == RenpyCompatibilityReport.SupportLevel.WARNING) {
            boolean canWrite = writerAvailable;
            return new EngineCapabilities(true, true, true, canWrite,
                    canWrite && activation != RenpyCompatibilityReport.ActivationStrategy.NONE,
                    canWrite, canWrite ? Workflow.PATCHABLE_VERIFIED
                            : Workflow.TRANSLATABLE_NO_PATCH);
        }
        if (level == RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY) {
            return new EngineCapabilities(true, true, true, false, false, false,
                    Workflow.TRANSLATABLE_NO_PATCH);
        }
        return new EngineCapabilities(level != null, false, false, false, false, false,
                Workflow.UNSUPPORTED);
    }
}
```

在 `RenpyCompatibilityReport` 增加：

```java
public EngineCapabilities capabilities() {
    return EngineCapabilities.forRenpy(supportLevel, activationStrategy,
            rpyc != null && rpyc.canGenerate());
}

public boolean isTranslationBlocked() {
    return !capabilities().canTranslate;
}

public boolean isWriterBlocked() {
    return !capabilities().canWritePatch;
}

public boolean isBlocked() {
    return isTranslationBlocked();
}
```

- [ ] **Step 4: 运行局部与完整 Java 契约测试**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only -v`

Expected: PASS; `EXTRACT_ONLY` 的翻译门禁为开放、writer 门禁为关闭，`UNSUPPORTED` 两者都关闭。

Run: `python -m unittest test_fast_scanner.py -v`

Expected: PASS; 现有 `SAFE/WARNING` 分类和 RPYC writer 测试无回归。

- [ ] **Step 5: 提交能力模型**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/EngineCapabilities.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: separate translation and writer capabilities"
```

### Task 2: 增加最小 adapter/writer 契约并包装现有 Ren'Py 路径

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/EngineAdapter.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WriterBackend.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyEngineAdapter.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java:57-128`
- Test: `apk-work/ui-redesign/test_fast_scanner.py:5772-5866`

**Interfaces:**
- Produces: `EngineAdapter<I, W>.adapterId() -> String`、`capabilities(I) -> EngineCapabilities`、`writer() -> WriterBackend<W>`。
- Produces: `WriterBackend<W>.writerId() -> String`、`supports(W) -> boolean`。
- Produces: `RenpyEngineAdapter.INSTANCE`，`adapterId()` 固定返回 `renpy`。
- Produces: `RenpyRpycWriter.INSTANCE`，`writerId()` 固定返回 `renpy-rpyc-existing`。
- Consumes: Task 1 的 `EngineCapabilities` 与 `RenpyCompatibilityReport`。

- [ ] **Step 1: 写失败的 adapter 契约测试**

在同一 Java harness 中加入：

```java
RenpyEngineAdapter adapter = RenpyEngineAdapter.INSTANCE;
require("renpy".equals(adapter.adapterId()), "adapter id must be stable");
require("renpy-rpyc-existing".equals(adapter.writer().writerId()),
        "writer id must describe the existing backend");
require(adapter.writer().supports(safe.rpyc), "safe report must use existing writer");
require(adapter.writer().supports(warning.rpyc), "warning report keeps existing writer");
require(!adapter.writer().supports(legacy.rpyc), "legacy report must not gain a writer");
require(adapter.capabilities(legacy).workflow
        == EngineCapabilities.Workflow.TRANSLATABLE_NO_PATCH,
        "adapter must expose export-only workflow");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only -v`

Expected: FAIL during javac because `RenpyEngineAdapter`, `EngineAdapter` and `WriterBackend` do not exist.

- [ ] **Step 3: 实现四个小类并让 preflight 走 adapter**

```java
package com.slgtranslator.app;

public interface EngineAdapter<I, W> {
    String adapterId();
    EngineCapabilities capabilities(I report);
    WriterBackend<W> writer();
}
```

```java
package com.slgtranslator.app;

public interface WriterBackend<W> {
    String writerId();
    boolean supports(W report);
}
```

```java
package com.slgtranslator.app;

public final class RenpyRpycWriter implements WriterBackend<RpycCompatibility.Report> {
    public static final RenpyRpycWriter INSTANCE = new RenpyRpycWriter();
    private RenpyRpycWriter() {}
    public String writerId() { return "renpy-rpyc-existing"; }
    public boolean supports(RpycCompatibility.Report report) {
        return report != null && report.canGenerate();
    }
}
```

```java
package com.slgtranslator.app;

public final class RenpyEngineAdapter implements
        EngineAdapter<RenpyCompatibilityReport, RpycCompatibility.Report> {
    public static final RenpyEngineAdapter INSTANCE = new RenpyEngineAdapter();
    private RenpyEngineAdapter() {}
    public String adapterId() { return "renpy"; }
    public WriterBackend<RpycCompatibility.Report> writer() { return RenpyRpycWriter.INSTANCE; }
    public EngineCapabilities capabilities(RenpyCompatibilityReport report) {
        if (report == null) {
            return EngineCapabilities.forRenpy(null,
                    RenpyCompatibilityReport.ActivationStrategy.NONE, false);
        }
        return EngineCapabilities.forRenpy(report.supportLevel, report.activationStrategy,
                writer().supports(report.rpyc));
    }
}
```

将 `RenpyCompatibilityReport.capabilities()` 改为委托 `RenpyEngineAdapter.INSTANCE.capabilities(this)`；`RenpyPreflight` 的等级判断保持原样，不增加新的版本通配判断。

- [ ] **Step 4: 运行 adapter 和 preflight 回归**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_preflight_reports_safe_warning_and_extract_only -v`

Expected: PASS; 新契约只包装现有判断，legacy 仍无 writer。

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_rpyc_compatibility_separates_modern_legacy_and_unknown_generation -v`

Expected: PASS; RPYC 方言支持矩阵没有扩大。

- [ ] **Step 5: 提交 adapter 契约**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/EngineAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/WriterBackend.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyEngineAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyCompatibilityReport.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "refactor: wrap renpy engine and writer capabilities"
```

### Task 3: 将能力、项目指纹和稳定记录 ID 接入扫描响应

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java:152-280,398-460,1138-1252`
- Test: `apk-work/ui-redesign/test_fast_scanner.py:5718-5948`

**Interfaces:**
- Produces scan fields: `adapterId: "renpy"`、`workflow`、`capabilities`、`projectFingerprint`、`recordSchemaVersion: 1`。
- Produces read fields: `adapterId`、`workflow`、`capabilities`、`translationGate`。
- Produces each Ren'Py record fields: `recordId`、`sourceOwner`、现有 record fields。
- Compatibility: `compatibilityGate` 继续返回 `blocked`、`extract_only` 或 `clear`。
- Consumes: Task 2 的 `RenpyEngineAdapter.INSTANCE`。

- [ ] **Step 1: 写失败的扫描响应契约测试**

在 `test_renpy_compatibility_report_ui_order_fields_and_sanitized_export` 附近增加：

```python
def test_scanner_exposes_capabilities_fingerprint_and_stable_record_identity(self):
    source = (FAST_SCAN / "src/com/slgtranslator/app/FastApkScanner.java").read_text("utf-8")
    for token in (
        'put("adapterId", "renpy")', 'put("workflow"', 'put("capabilities"',
        'put("projectFingerprint"', 'put("recordSchemaVersion", 1)',
        'put("recordId"', 'put("sourceOwner"', 'put("translationGate"',
    ):
        self.assertIn(token, source)
    self.assertIn('return "extract_only";', source,
                  "legacy compatibilityGate must remain for old frontends")
```

同时在 Java harness 中验证两次相同记录输入产生相同 `recordId`，改变 `sourceOwner` 后 ID 必须变化。

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_scanner_exposes_capabilities_fingerprint_and_stable_record_identity -v`

Expected: FAIL because the new response fields and identity helper are absent.

- [ ] **Step 3: 增加序列化 helper 和确定性指纹**

能力 JSON 使用明确字段，不传 Java 对象：

```java
private static JSObject capabilitiesJson(EngineCapabilities value) {
    EngineCapabilities safe = value == null
            ? RenpyEngineAdapter.INSTANCE.capabilities(null) : value;
    return new JSObject()
            .put("canDetect", safe.canDetect)
            .put("canExtractStructured", safe.canExtractStructured)
            .put("canTranslate", safe.canTranslate)
            .put("canWritePatch", safe.canWritePatch)
            .put("canActivate", safe.canActivate)
            .put("canValidateRuntime", safe.canValidateRuntime);
}
```

项目指纹只使用稳定、脱敏的扫描元数据：`packageName`、`versionCode`、按 `sourceOwner/name/size/compressedSize/crc` 排序后的 ZIP entry 元组、`splitCount`。为 `ApkEntry` 增加 CRC 和 source owner，但不保存 entry 内容；使用现有 SHA-256 helper 输出 64 位小写十六进制，不包含 URI、绝对路径或文本。相同大小但 CRC 不同的源必须产生不同指纹。

记录 identity 固定为：

```java
private static String recordId(String adapterId, String sourceOwner, RenpyTextRecord record) {
    return sha256(adapterId + "\n" + sourceOwner + "\n" + record.sourcePath + "\n"
            + record.kind.name() + "\n" + record.identifier + "\n" + record.speaker + "\n"
            + record.occurrence + "\n" + record.text);
}
```

`sourceOwner` 规则固定为 base APK 的 `base`，split 为 `split:<manifest splitName>`。必须从 `InstalledApkSet.splitNameAt(index)` 或调用方传入的 `splitNames` 获取，不得用临时 APK 文件名代替；完整 splitName 不可用时扫描继续返回旧字段，但 `projectFingerprint`/项目导出进入 `split_set_incomplete` 阻断。RPA 虚拟路径使用 `archive:<sourceOwner>!/<rpa entry>`，不丢失归属。

- [ ] **Step 4: 追加字段但保留旧桥接行为**

在 `toResponse` 和 `readRenpyTexts` 中使用同一个能力对象：

```java
EngineCapabilities caps = RenpyEngineAdapter.INSTANCE.capabilities(report);
result.put("adapterId", "renpy");
result.put("workflow", caps.workflow.name());
result.put("capabilities", capabilitiesJson(caps));
result.put("recordSchemaVersion", 1);
result.put("translationGate", caps.canTranslate ? "clear" : "blocked");
```

`compatibilityGate(report)` 不改，确保旧前端对 `EXTRACT_ONLY` 仍然失败关闭。`toResponse` 接收或计算 `projectFingerprint`；缓存命中与非缓存路径必须返回同一个值。

- [ ] **Step 5: 运行扫描器回归并提交**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_scanner_exposes_capabilities_fingerprint_and_stable_record_identity test_fast_scanner.FastApkScannerContractTest.test_renpy_font_preflight_is_before_first_model_call_and_read_bridge_returns_gate -v`

Expected: PASS; 新字段存在，旧 `compatibilityGate` 仍存在。

Run: `python -m unittest test_fast_scanner.py -v`

Expected: PASS.

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: expose engine capabilities and project identity"
```

### Task 4: 实现通用翻译项目 schema、导入匹配和安全 JSON 导出

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationProjectSupport.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**
- Produces: `TranslationProjectSupport.validateProjectJson(String) -> ValidatedProject`。
- Produces: `TranslationProjectSupport.validateImport(String, String, String, String, String) -> ImportResult`，参数依次为项目 JSON、预期指纹、预期 adapter、预期源版本、当前 records JSON。
- Produces bridge: `exportTranslationProject(Context, PluginCall)`，读取 `projectJson`/`fileName`。
- Produces bridge: `importTranslationProject(Context, PluginCall)`，读取 `projectJson`/`expectedFingerprint`/`expectedAdapterId`/`expectedSourceVersion`/`currentRecordsJson`。
- Error codes: `translation_export_invalid_json`、`translation_export_too_large`、`translation_export_version_mismatch`、`translation_export_record_limit`、`translation_export_write_failed`。
- Consumes: `RenpyTextValidator.validate(oldText, newText)` 用于 `adapterId=renpy` 的占位符和标签复核。

- [ ] **Step 1: 写失败的 Java codec harness**

新增测试 `test_translation_project_schema_export_and_import_validation`，编译并执行以下核心断言：

```java
String current = "[{\"recordId\":\"r1\",\"sourceText\":\"Hello %s\"}]";
String valid = "{\"schemaVersion\":1,\"projectFingerprint\":\"fp1\","
        + "\"adapterId\":\"renpy\",\"sourceVersion\":\"v1\",\"records\":[{"
        + "\"recordId\":\"r1\",\"sourceOwner\":\"base\","
        + "\"sourcePath\":\"assets/game/script.rpyc\",\"resourceType\":\"DIALOGUE\","
        + "\"sourceKey\":\"line-1\",\"sourceText\":\"Hello %s\","
        + "\"translation\":\"你好 %s\",\"validation\":\"APPROVED\"}]}";
TranslationProjectSupport.ValidatedProject parsed =
        TranslationProjectSupport.validateProjectJson(valid);
require(parsed.recordCount == 1, "one record must validate");
TranslationProjectSupport.ImportResult imported =
        TranslationProjectSupport.validateImport(valid, "fp1", "renpy", "v1", current);
require(imported.acceptedCount == 1 && imported.reviewCount == 0,
        "matching record must import automatically");

String changed = valid.replace("Hello %s", "Hello %d");
TranslationProjectSupport.ImportResult stale =
        TranslationProjectSupport.validateImport(changed, "fp1", "renpy", "v1", current);
require(stale.acceptedCount == 0 && stale.reviewCount == 1,
        "changed source text must require review");

String brokenPlaceholder = valid.replace("你好 %s", "你好");
TranslationProjectSupport.ImportResult invalid =
        TranslationProjectSupport.validateImport(brokenPlaceholder, "fp1", "renpy", "v1", current);
require(invalid.acceptedCount == 0 && invalid.reviewCount == 1,
        "placeholder mismatch must not auto-import");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_project_schema_export_and_import_validation -v`

Expected: FAIL during javac because `TranslationProjectSupport` does not exist.

- [ ] **Step 3: 实现受限 parser 和匹配结果**

`TranslationProjectSupport` 必须在构造 `JSONObject` 前检查 UTF-8 字节长度，在遍历前检查 records 长度，并对每个必需字段执行类型、长度和非空校验。公开结果类型固定为：

```java
public static final class ValidatedProject {
    public final String normalizedJson;
    public final String projectFingerprint;
    public final String adapterId;
    public final String sourceVersion;
    public final int recordCount;
}

public static final class ImportResult {
    public final String acceptedRecordsJson;
    public final String reviewRecordsJson;
    public final int acceptedCount;
    public final int reviewCount;
}
```

匹配顺序固定为：schema -> fingerprint -> adapter -> sourceVersion -> recordId 存在 -> sourceText 精确相同 -> translation validator。重复 `recordId`、不存在的 record、原文变化和 validator 失败都进入 `reviewRecordsJson`，每条包含 `recordId` 与稳定 `reasonCode`，不覆盖当前记录。

- [ ] **Step 4: 实现 MediaStore 导出和 PluginCall 包装**

Android 10+ 写入：

```java
ContentValues values = new ContentValues();
values.put(MediaStore.MediaColumns.DISPLAY_NAME, safeFileName);
values.put(MediaStore.MediaColumns.MIME_TYPE, "application/json");
values.put(MediaStore.MediaColumns.RELATIVE_PATH,
        Environment.DIRECTORY_DOWNLOADS + "/SLG-Translator/translations");
Uri target = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
```

写入失败必须调用 `resolver.delete(target, null, null)` 清理半成品。Android 9 及以下写入 `Downloads/SLG-Translator/translations`。桥接返回 `uri`、`fileName`、`recordCount`、`schemaVersion`；导入桥接返回 `acceptedRecordsJson`、`reviewRecordsJson`、`acceptedCount`、`reviewCount`。

- [ ] **Step 5: 运行 codec、边界与清理测试并提交**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_project_schema_export_and_import_validation -v`

Expected: PASS; 匹配、源文本变化和占位符变化分别进入正确集合。

Run: `python -m unittest test_fast_scanner.py -v`

Expected: PASS; Java 8 全量编译通过。

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationProjectSupport.java apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: add translation project import and export support"
```

### Task 5: 注入翻译项目桥接并验证 DEX 唯一性

**Files:**
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py:230-405,920-977`
- Modify: `apk-work/ui-redesign/test_fast_scanner.py:2368-2435,8149-8436`

**Interfaces:**
- Produces Capacitor methods: `exportTranslationProject(PluginCall)`、`importTranslationProject(PluginCall)`。
- Delegates: `TranslationProjectSupport.exportTranslationProject(Context, PluginCall)` 与 `importTranslationProject(Context, PluginCall)`。
- Consumes: Task 4 的两个 static bridge 方法。

- [ ] **Step 1: 写失败的 builder 与 DEX 测试**

增加源码契约断言：

```python
for token in (
    "TRANSLATION_PROJECT_EXPORT_SIGNATURE",
    "TranslationProjectSupport;->exportTranslationProject",
    "TRANSLATION_PROJECT_IMPORT_SIGNATURE",
    "TranslationProjectSupport;->importTranslationProject",
):
    self.assertIn(token, builder)
```

在 `test_generated_dex_has_unique_installed_app_bridge` 增加：

```python
self.assertEqual(plugin_dump.count("name          : 'exportTranslationProject'"), 1)
self.assertEqual(plugin_dump.count("name          : 'importTranslationProject'"), 1)
self.assertEqual(helper_dump.count(
    "Class descriptor  : 'Lcom/slgtranslator/app/TranslationProjectSupport;'"), 1)
```

- [ ] **Step 2: 运行源码测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_project_bridge_contract -v`

Expected: FAIL because the signatures and delegates are absent.

- [ ] **Step 3: 按现有 SaveTransfer 模式注入两个方法**

每个 smali 方法使用 `getContext()`，只调用一次 static delegate：

```smali
.method public final exportTranslationProject(Lcom/getcapacitor/PluginCall;)V
    .locals 1
    invoke-virtual {p0}, Lcom/getcapacitor/Plugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/TranslationProjectSupport;->exportTranslationProject(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method
```

导入方法同样只替换方法名和 delegate。将两个 method tuple 加入现有唯一性循环；部分注入或重复注入必须抛出 `RuntimeError`。

- [ ] **Step 4: 构建 DEX 并运行唯一性测试**

Run: `Set-Location D:\文件翻译\apk-work\native-fast-scan; python build_fast_scanner.py; Set-Location D:\文件翻译\apk-work\ui-redesign`

Expected: 生成 `generated/classes6.dex` 与 helper DEX，javac/D8/APKTool 步骤成功。

Run: `$env:REQUIRE_FAST_SCAN_ARTIFACTS='1'; python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_project_bridge_contract test_fast_scanner.FastApkScannerContractTest.test_generated_dex_has_unique_installed_app_bridge -v`

Expected: PASS; 插件 DEX 中两个 bridge 各一个，helper DEX 中 support class 一个。

- [ ] **Step 5: 提交桥接**

```powershell
git add apk-work/native-fast-scan/build_fast_scanner.py apk-work/ui-redesign/test_fast_scanner.py
git commit -m "feat: register translation project bridges"
```

### Task 6: 让 `EXTRACT_ONLY` 通过模型门禁并在 writer 边界停止

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:475-531,853-1052,1734-1905`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java:58-86,700-805`
- Modify: `apk-work/ui-redesign/test_fast_scanner.py:5888-5948`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py:2766-2824`

**Interfaces:**
- Produces JS helper: `resolveEngineCapabilities(scanOrReport) -> {adapterId, workflow, canExtractStructured, canTranslate, canWritePatch, canActivate, canValidateRuntime}`。
- Produces globals: `__slgEngineCapabilities`、`__slgEngineWorkflow`、`__slgProjectFingerprint`、`__slgRecordSchemaVersion`。
- Produces compiler result on blocked writer: `compiled: 0`、`writerBlocked: true`、`reasonCode: "engine_detected_no_writer"`。
- Consumes: Tasks 3-5 的扫描字段和 bridge。

- [ ] **Step 1: 写失败测试，将旧阻断断言改成可翻译、不可写**

把 `test_renpy_extract_only_compatibility_gate_blocks_before_model` 改名为 `test_renpy_extract_only_allows_model_and_blocks_writer_boundary`，执行生成的 `Ce` 并断言：

```javascript
window.__slgRenpyCompatibilityReport={supportLevel:`EXTRACT_ONLY`,issues:[{code:`renpy_python2_writer_unavailable`}]};
window.__slgEngineCapabilities={canExtractStructured:true,canTranslate:true,canWritePatch:false,canActivate:false,canValidateRuntime:false};
window.__slgEngineWorkflow=`TRANSLATABLE_NO_PATCH`;
await Ce();
check(extractionCalls>0,`extract-only must still extract`);
check(modelCalls>0,`extract-only must reach the selected model`);
check(compileCalls===0&&buildCalls===0&&installCalls===0,
      `writer boundary must stop compile, build and install`);
check(exportCalls===0,`writer-boundary task must not fabricate an export before project assembly exists`);
```

把 `test_extract_only_preflight_blocks_start_translation_action` 改成断言 snapshot 为 `ready`、按钮文案为“翻译并导出”、点击会分发 React start，不出现“重新选择 APK”。保留 `test_renpy_unsupported_snapshot_blocks_generated_extract_model_and_build` 不变。

- [ ] **Step 2: 运行两个行为测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_extract_only_allows_model_and_blocks_writer_boundary test_workshop_patch.WorkshopPatchContractTest.test_extract_only_preflight_allows_translation_export_action -v`

Expected: FAIL because generated JS still sets `EXTRACT_ONLY` as compatibility-blocked and prevents start dispatch.

- [ ] **Step 3: 实现能力 fallback 并只在 `canTranslate=false` 时阻断模型**

fallback 必须兼容旧扫描器：

```javascript
function resolveEngineCapabilities(value){
  const report=value?.compatibilityReport||value||{};
  const supplied=value?.capabilities||report?.capabilities;
  if(supplied)return{adapterId:value?.adapterId||`renpy`,workflow:value?.workflow||`UNSUPPORTED`,...supplied};
  if(report.supportLevel===`SAFE`||report.supportLevel===`WARNING`)
    return{adapterId:`renpy`,workflow:`PATCHABLE_VERIFIED`,canExtractStructured:true,canTranslate:true,canWritePatch:true,canActivate:true,canValidateRuntime:true};
  if(report.supportLevel===`EXTRACT_ONLY`)
    return{adapterId:`renpy`,workflow:`TRANSLATABLE_NO_PATCH`,canExtractStructured:true,canTranslate:true,canWritePatch:false,canActivate:false,canValidateRuntime:false};
  return{adapterId:`renpy`,workflow:`UNSUPPORTED`,canExtractStructured:false,canTranslate:false,canWritePatch:false,canActivate:false,canValidateRuntime:false};
}
```

`triggerReactButton`、`readTaskSnapshot` 和 `Ce` 的模型前门禁只检查 `!caps.canTranslate`。`compatibilityGate=extract_only` 仅保留为旧字段，不得在新前端覆盖明确的 `canTranslate=true`。

字体检查在 `canWritePatch=false` 时记录警告但不阻断模型；在 `canWritePatch=true` 的现有路径仍保持 writer 前阻断。

- [ ] **Step 4: 在唯一 writer 边界分流导出，编译器继续失败关闭**

在覆盖率刷新完成、调用 `compileTranslationsIntoApk` 之前加入最小 writer 分流；Task 7 再把该标记替换为真实导出：

```javascript
if(!window.__slgEngineCapabilities?.canWritePatch){
  window.__slgTranslationAwaitingExport=true;
  O(`译文已完成校验：当前引擎没有经过验证的 APK writer。`,`info`);
  return N;
}
```

`TranslationCompiler` 在 `!RenpyRpycWriter.INSTANCE.supports(report)` 时返回：

```java
new JSObject()
    .put("compiled", 0)
    .put("writerBlocked", true)
    .put("reasonCode", "engine_detected_no_writer")
    .put("workflow", EngineCapabilities.Workflow.TRANSLATABLE_NO_PATCH.name());
```

不得进入 `collect_requested_rpy`、临时产物或 ZIP 写入。

- [ ] **Step 5: 运行分流与严格阻断回归并提交**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_renpy_extract_only_allows_model_and_blocks_writer_boundary test_fast_scanner.FastApkScannerContractTest.test_renpy_unsupported_snapshot_blocks_generated_extract_model_and_build test_workshop_patch.WorkshopPatchContractTest.test_extract_only_preflight_allows_translation_export_action -v`

Expected: PASS; `EXTRACT_ONLY` 调模型并在 writer 边界返回，`UNSUPPORTED` 的提取/模型/构建计数仍全部为 0。

Run: `python -m unittest test_workshop_patch.py test_fast_scanner.py -v`

Expected: PASS; `SAFE/WARNING` 仍调用 compile/build。

```powershell
git add apk-work/ui-redesign/patch_workshop_ui.py apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/test_fast_scanner.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "feat: translate extract-only projects without invoking writers"
```

### Task 7: 组装通用项目、实现导入并增加“译文已导出”完成状态

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:853-1300,2357-2408,2501-2510`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`

**Interfaces:**
- Produces: `__slgBuildTranslationProject() -> schema 1 object`。
- Produces: `__slgImportTranslationProject(projectJson) -> Promise<{acceptedCount, reviewCount}>`。
- Produces task state: `exported`，文案“译文已导出”，操作“再次导出”“导入译文”。
- Consumes: `__slgCoverageRecords`、`__slgValidatorApprovedTranslations`、selection metadata、Tasks 3-5 的 project fields 和 bridge。

- [ ] **Step 1: 写失败的项目组装与 UI 行为测试**

新增 `test_translation_project_export_state_and_import_matching_records`，抽取生成的 helper 后执行：

```javascript
window.__slgProjectFingerprint=`fp1`;
window.__slgEngineAdapterId=`renpy`;
window.__slgRecordSchemaVersion=1;
window.__slgSelectionMeta={versionCode:`42`};
window.__slgCoverageRecords=[{
  recordId:`r1`,sourceOwner:`base`,sourcePath:`assets/game/script.rpyc`,
  kind:`DIALOGUE`,identifier:`line-1`,text:`Hello %s`
}];
window.__slgValidatorApprovedTranslations=new Map([[`Hello %s`,`你好 %s`]]);
const project=globalThis.__slgBuildTranslationProject();
check(project.schemaVersion===1&&project.projectFingerprint===`fp1`,`project identity`);
check(project.records.length===1&&project.records[0].translation===`你好 %s`,`approved record exported`);
check(project.records[0].validation===`APPROVED`,`validation state exported`);
```

行为测试还要让 Task 6 的 writer-boundary 分流实际调用 bridge，并断言 `exportCalls===1`、`compileCalls===0`、`buildCalls===0`、`installCalls===0`。`renderStateBody('exported', payload)` 不包含“保存补丁 APK”“安装补丁版”，包含“译文已导出”“再次导出”“导入译文”。

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_project_export_state_and_import_matching_records -v`

Expected: FAIL because project helpers and `exported` state do not exist.

- [ ] **Step 3: 实现项目组装 helper**

```javascript
globalThis.__slgBuildTranslationProject=function(){
  const approved=globalThis.__slgValidatorApprovedTranslations||new Map();
  const records=[];
  for(const source of globalThis.__slgCoverageRecords||[]){
    const sourceText=String(source.text??``);
    const translation=String(approved.get(sourceText)??``);
    if(!source.recordId||!translation.trim())continue;
    records.push({
      recordId:String(source.recordId),
      sourceOwner:String(source.sourceOwner||`base`),
      sourcePath:String(source.sourcePath||``),
      resourceType:String(source.kind||`UNKNOWN`),
      sourceKey:String(source.identifier||source.keyPath||``),
      sourceText,
      translation,
      validation:`APPROVED`
    });
  }
  return{
    schemaVersion:1,
    projectFingerprint:String(window.__slgProjectFingerprint||``),
    adapterId:String(window.__slgEngineAdapterId||`renpy`),
    sourceVersion:String(window.__slgSelectionMeta?.versionCode||window.__slgProjectFingerprint||``),
    records
  };
};
```

发生同原文多译文碰撞时，不选择任意候选；该记录不进入 `APPROVED` records，并在导出前沿用现有 collision/coverage 阻断提示。项目必须在 `__slgTrimTranslationDiagnostics()` 清空逐条记录之前组装。

- [ ] **Step 4: 将 writer-boundary 标记替换为真实导出，并实现导入和独立完成状态**

把 Task 6 的 `__slgTranslationAwaitingExport` 分支替换为：

```javascript
if(!window.__slgEngineCapabilities?.canWritePatch){
  const project=globalThis.__slgBuildTranslationProject();
  const exported=await E.exportTranslationProject({
    projectJson:JSON.stringify(project),
    fileName:`${project.adapterId}-${project.projectFingerprint.slice(0,12)}.translation.json`
  });
  window.__slgTranslationExportResult=exported;
  window.__slgTranslationExportCompleted=true;
  window.__slgTranslationAwaitingExport=false;
  O(`译文已导出：当前引擎没有经过验证的 APK writer。`,`success`);
  return N;
}
```

导入调用原生 validator：

```javascript
globalThis.__slgImportTranslationProject=async function(projectJson){
  const currentRecords=JSON.stringify((globalThis.__slgCoverageRecords||[]).map(r=>({
    recordId:r.recordId,sourceText:r.text
  })));
  const result=await window.Capacitor.Plugins.FileManager.importTranslationProject({
    projectJson,
    expectedFingerprint:String(window.__slgProjectFingerprint||``),
    expectedAdapterId:String(window.__slgEngineAdapterId||`renpy`),
    expectedSourceVersion:String(window.__slgSelectionMeta?.versionCode||window.__slgProjectFingerprint||``),
    currentRecordsJson:currentRecords
  });
  for(const item of JSON.parse(result.acceptedRecordsJson||`[]`))
    globalThis.__slgValidatorApprovedTranslations.set(item.sourceText,item.translation);
  window.__slgTranslationImportReview=JSON.parse(result.reviewRecordsJson||`[]`);
  globalThis.__slgRefreshTranslationCoverage?.();
  return result;
};
```

“导入译文”按钮必须打开一个只接受 JSON 的文件输入，并通过 `FileReader` 把文本交给上述 helper：

```javascript
function chooseTranslationProject(){
  const input=document.createElement(`input`);
  input.type=`file`;
  input.accept=`application/json,.json`;
  input.onchange=()=>{
    const file=input.files?.[0];
    if(!file)return;
    const reader=new FileReader();
    reader.onload=()=>globalThis.__slgImportTranslationProject(String(reader.result||``));
    reader.onerror=()=>O(`读取翻译项目失败`,`error`);
    reader.readAsText(file,`utf-8`);
  };
  input.click();
}
```

`readTaskSnapshot` 在日志含“译文已导出”或 `__slgTranslationExportCompleted` 时返回 `state:'exported'`。该状态清除 `translating` 会话标记，但保留项目 identity 和译文缓存；界面不显示 APK 保存或安装操作。

- [ ] **Step 5: 运行 UI 与生成 JS 回归并提交**

Run: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_project_export_state_and_import_matching_records test_workshop_patch.WorkshopPatchContractTest.test_extract_only_preflight_allows_translation_export_action -v`

Expected: PASS.

Run: `python -m unittest test_workshop_patch.py -v`

Expected: PASS; existing completed APK state remains separate from exported state.

```powershell
git add apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "feat: add translation project export and import workflow"
```

### Task 8: 为缓存和恢复会话增加 adapter/schema/fingerprint 命名空间

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:475-531,1244-1300,1536-1573,1909-1990`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py:2357-2405,3512-3730,4293-4320`
- Modify: `apk-work/ui-redesign/test_translation_memory.py`

**Interfaces:**
- Produces file cache key: `slg-file-v2:<hash(adapterId|recordSchemaVersion|projectFingerprint|sourcePath|sourceLang|targetLang)>`。
- Produces exact-old cache metadata: `adapterId`、`recordSchemaVersion`、`projectFingerprint`。
- Produces session fields: `adapterId`、`workflow`、`recordSchemaVersion`、`projectFingerprint`。
- Compatibility: old `slg-file-v1` and old exact-old entries may provide model text fallback only; they cannot provide record identity or writer validation.
- Consumes: Task 3 的项目字段和 Task 7 的 restored translations。

- [ ] **Step 1: 写失败的缓存隔离测试**

扩展 `test_translation_cache_is_reused_across_models`：

```javascript
window.__slgEngineAdapterId=`renpy`;
window.__slgRecordSchemaVersion=1;
window.__slgProjectFingerprint=`fp-a`;
await run([{recordId:`r1`,text:`same`,keyPath:`script.rpyc::1`}],`openai`,`m1`,`url`,`full`);
const firstRequests=requests.length;
await run([{recordId:`r1`,text:`same`,keyPath:`script.rpyc::1`}],`deepseek`,`m2`,`url`,`resume`);
check(requests.length===firstRequests,`same project reuses model translation`);
window.__slgProjectFingerprint=`fp-b`;
await run([{recordId:`r1`,text:`same`,keyPath:`script.rpyc::1`}],`deepseek`,`m2`,`url`,`resume`);
check(requests.length===firstRequests+1,`different project cannot reuse writable file location`);
window.__slgEngineAdapterId=`android-resources`;
await run([{recordId:`r1`,text:`same`,keyPath:`res/values/strings.xml::1`}],`deepseek`,`m2`,`url`,`resume`);
check(requests.length===firstRequests+2,`different adapter cannot share record mapping`);
```

增加旧 `slg-file-v1` fixture，断言它可以恢复相同原文的译文文本，但新写入只产生 `slg-file-v2`。

- [ ] **Step 2: 运行缓存与会话测试确认红灯**

Run: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_cache_is_reused_across_models test_workshop_patch.WorkshopPatchContractTest.test_restore_session_preserves_complete_source_set_metadata test_translation_memory -v`

Expected: FAIL because current key lacks adapter/schema/fingerprint and session does not preserve these fields.

- [ ] **Step 3: 实现 v2 cache scope 与 v1 只读 fallback**

```javascript
function translationProjectScope(){
  return[
    window.__slgEngineAdapterId||`renpy`,
    Number(window.__slgRecordSchemaVersion||1),
    window.__slgProjectFingerprint||window.__slgSelectionMeta?.packageName||n
  ].join(`|`);
}
function fileCacheV2Key(file){
  return`slg-file-v2:${U([translationProjectScope(),file.name,g,y].join(`|`))}`;
}
```

读取顺序固定为 v2 -> 同一 source 的 v1 fallback；从 v1 恢复的数据仅填充 translation，不复制旧 recordId、validation、compiled path 或 writer 结果。保存快照时同时保存现有 dirty exact-old 项和 `slg-file-v2:` 项。

- [ ] **Step 4: 扩展 session identity 并处理旧任务**

`mergeSelectionMetadata`、`persistSelectionSession`、`restoreSession` 增加四个字段。旧会话没有这些字段时：重新扫描获得 identity，再允许恢复译文；不得在扫描前直接恢复 writer/build 状态。`sameSource` 优先比较 `projectFingerprint`，字段缺失时才回退现有 URI/package/version 比较。

- [ ] **Step 5: 运行缓存、恢复与内存测试并提交**

Run: `python -m unittest test_workshop_patch.WorkshopPatchContractTest.test_translation_cache_is_reused_across_models test_workshop_patch.WorkshopPatchContractTest.test_restore_session_preserves_complete_source_set_metadata test_workshop_patch.WorkshopPatchContractTest.test_selection_session_does_not_inherit_translating_across_apk_identity test_translation_memory -v`

Expected: PASS; 同项目跨模型复用，不同项目/adapter 隔离，旧 cache 只读恢复。

```powershell
git add apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_translation_memory.py
git commit -m "feat: namespace translation cache by engine project"
```

### Task 9: 完成契约、构建、DEX 和真机验收

**Files:**
- Modify: `docs/qa/renpy-release-checklist.md`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_workshop_patch.py`
- Test: `apk-work/ui-redesign/test_translation_memory.py`
- Generated verification only: `apk-work/native-fast-scan/generated/classes6.dex`、helper DEX、最终 signed APK。

**Interfaces:**
- Verifies: `EXTRACT_ONLY -> TRANSLATABLE_NO_PATCH -> exported`。
- Verifies: `SAFE/WARNING -> PATCHABLE_VERIFIED -> compile/build/install`。
- Verifies: `UNSUPPORTED -> blocked`。
- Verifies: bridge uniqueness、APK signature、device export file and zero patch/install invocation for export-only fixture。

- [ ] **Step 1: 写失败测试，增加发布清单断言**

在 `test_fast_scanner.py` 增加：

```python
def test_release_checklist_covers_translation_export_only_workflow(self):
    checklist = (ROOT / "docs/qa/renpy-release-checklist.md").read_text("utf-8")
    for token in (
        "TRANSLATABLE_NO_PATCH", "engine_detected_no_writer", "译文已导出",
        "零 RPYC writer 调用", "零 APK 构建调用", "零安装调用",
        "projectFingerprint", "recordSchemaVersion", "translation_export_version_mismatch",
    ):
        self.assertIn(token, checklist)
```

- [ ] **Step 2: 运行清单测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_release_checklist_covers_translation_export_only_workflow -v`

Expected: FAIL listing the missing acceptance tokens.

- [ ] **Step 3: 更新发布清单并运行全量自动化测试**

清单必须分别记录三个 fixture 的扫描 JSON、模型调用计数、export/compile/build/install 计数、导出文件 SHA-256、重新导入结果和用户可见完成文案。运行：

```powershell
python -m unittest test_fast_scanner.py test_workshop_patch.py test_translation_memory.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

Expected: PASS; 不允许仅运行新增测试后宣称完成。

- [ ] **Step 4: 重建并验证 DEX/APK**

```powershell
Set-Location D:\文件翻译\apk-work\native-fast-scan
python build_fast_scanner.py
Set-Location D:\文件翻译\apk-work\ui-redesign
python build_workshop_apk.py
$env:REQUIRE_FAST_SCAN_ARTIFACTS='1'
python -m unittest test_fast_scanner.FastApkScannerContractTest.test_generated_dex_has_unique_installed_app_bridge test_built_apk.py -v
```

Expected: javac、D8、APKTool、zipalign、签名验证和 DEX 唯一性全部通过；最终 APK 中存在 `TranslationProjectSupport`，两个新 bridge 各一个。

- [ ] **Step 5: 真机执行三条工作流**

使用数据保留安装：

```powershell
adb install -r D:\文件翻译\apk-work\slg-workshop-ui-signed.apk
adb shell monkey -p com.slgtranslator.app -c android.intent.category.LAUNCHER 1
```

依次验证：

1. `EXTRACT_ONLY` fixture：可点击“翻译并导出”，模型有调用，Downloads 生成 schema 1 JSON，可重新导入；日志和计数证明 RPYC writer、APK build、安装均为 0。
2. `SAFE` fixture：仍生成并安装可运行补丁，菜单/always-on 策略与修改前一致。
3. `UNSUPPORTED` fixture：开始操作被阻断，模型、导出、writer、build、install 均为 0。

保存设备型号、Android 版本、工具 APK SHA-256、fixture 指纹、导出 JSON SHA-256、安装/启动结果和 UI 截图路径到 release checklist。

- [ ] **Step 6: 提交验收文档**

```powershell
git add docs/qa/renpy-release-checklist.md apk-work/ui-redesign/test_fast_scanner.py
git commit -m "test: verify translation export-only workflow"
```

---

## Execution Order

1. Tasks 1-3 建立能力模型和扫描契约；完成后旧前端行为仍保持安全阻断。
2. Tasks 4-5 建立原生项目格式和桥接；此时尚不改变用户主流程。
3. Tasks 6-7 放开翻译并在 writer 边界导出，形成第一个可独立验收的用户结果。
4. Task 8 完成缓存/会话迁移，避免用户升级后重复消耗模型费用或跨引擎错配。
5. Task 9 执行全量回归与真机验证后才允许发布。

任何任务发现 `SAFE/WARNING` 构建行为变化时，停止后续任务并先恢复现有 verified writer 行为；不能用更新测试期望掩盖回归。

## Deferred Work

- Ren'Py Python 2、未知 pickle 方言和其他旧 RPYC 的新 writer。
- Android `resources.arsc`、binary XML 和 AAPT2 重建。
- JSON/CSV/properties/HTML 通用结构化文本 writer。
- WebView、Unity AssetBundle、DEX、native、Flutter AOT 和图片 OCR。
- `PATCHABLE_EXPERIMENTAL` 的开发者开关与实验产物命名。

这些内容分别编写后续实施计划；本计划只建立它们需要复用的能力、adapter、项目导出和缓存边界。

## Self-Review Results

- 范围覆盖：能力模型、adapter/writer 契约、扫描响应、模型门禁、writer 边界、JSON 导入导出、UI 状态、缓存、会话、桥接、DEX、APK 和真机验收均有独立任务。
- 安全边界：`EXTRACT_ONLY` 只增加翻译与导出能力；`UNSUPPORTED` 未放开；现有 `SAFE/WARNING` writer 路径没有被替换。
- 兼容边界：旧桥接字段与 `compatibilityGate=extract_only` 保留，新前端有明确 fallback，旧缓存只读恢复。
- 类型一致：所有任务统一使用 `EngineCapabilities`、`EngineAdapter<I, W>`、`WriterBackend<W>`、`RenpyEngineAdapter`、`RenpyRpycWriter`、`ValidatedProject`、`ImportResult` 和 schema 1 字段名。
- 占位检查：每个任务都给出精确文件、接口、失败测试、预期失败、最小实现、通过命令和提交命令，没有留空实现步骤。
- 验证闭环：最终完成标准同时要求自动化测试、生成 JS、Java 8 编译、DEX 唯一性、签名 APK 和三类真机工作流证据。
