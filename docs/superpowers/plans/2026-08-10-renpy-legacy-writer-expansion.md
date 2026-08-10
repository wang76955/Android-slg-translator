# Ren'Py Legacy Writer Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在阶段 0 能力分层完成后，只为经过真实样本验证的 Ren'Py Python 2/protocol 2 方言增加 RPYC writer，并让其通过产物重读、APK 安装、游戏启动和中文生效门禁。

**Architecture:** 用不可变 `RenpyDialectDescriptor` 描述 container、slot、pickle protocol、GLOBAL 模块、opcode、version/key 和对象图特征；`RenpyDialectRegistry` 只接受精确指纹，不使用版本区间或单一魔数放行。`RenpyLegacyRpycWriter` 参数化现有 `RpycPickleWriter`，生成物继续由独立 `RenpyPatchValidator` 重读；未登记方言保持 `TRANSLATABLE_NO_PATCH`。

**Tech Stack:** Java 8、Ren'Py RPC2/zlib/pickle protocol 2、Python fixture tools、Python `unittest`、javac harness、APKTool、D8、ADB、真实 Ren'Py 6/7 样本矩阵。

## Global Constraints

- 前置条件：`2026-08-10-android-translation-engine-capability-layer.md` 的 Tasks 1-9 全部通过。
- 单个 protocol、`__builtin__` 字符串或 RPC2 magic 不能单独放行 writer。
- 未登记方言、未知 opcode、未知 GLOBAL、未知 version/key 或对象图差异继续映射 `TRANSLATABLE_NO_PATCH`。
- 不执行 pickle，不反序列化任意 Python 对象，只做受限 opcode 解析和确定性写入。
- 不修改标签、jump/call、条件、Python 代码和存档结构；首版只生成现有字符串翻译节点。
- 每个升级为 verified 的方言至少需要两个来源不同的合法样本，并保存来源合法性与 SHA-256。
- 生成物必须由独立 parser 重读，翻译数量、原文 key、译文、slot、version/key 和 opcode 白名单全部一致。
- writer 失败不得修改源 APK，不得覆盖最后一个已验证补丁。
- 匹配版本编译器和运行时字符串映射只做隔离验证；没有达到门禁时不得进入普通用户流程。
- 测试命令从 `D:\文件翻译\apk-work\ui-redesign` 运行。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectDescriptor.java` — 方言指纹值对象。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectRegistry.java` — verified 方言白名单。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyLegacyRpycWriter.java` — protocol 2 方言 writer。
- Create: `apk-work/ui-redesign/renpy_legacy_fixture_catalog.py` — fixture manifest 读取与哈希验证。
- Create: `apk-work/ui-redesign/probe_renpy_legacy_compiler.py` — 匹配版本编译器隔离探针。
- Create: `docs/qa/renpy-legacy-writer-matrix.md` — 样本、方言和真机证据。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java` — 输出 dialect ID 和精确匹配结果。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java` — 接收 descriptor，限制 opcode/GLOBAL。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPatchValidator.java` — 增加方言级重读验证。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java` — 路由现代或 legacy writer。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java` — 选择 writer 并返回 dialect metadata。
- Test: `apk-work/ui-redesign/test_fast_scanner.py`。
- Test: `apk-work/ui-redesign/test_renpy_legacy_writer.py`。

## Tasks

### Task 1: 建立可审计的 legacy fixture 目录

**Files:**
- Create: `apk-work/ui-redesign/renpy_legacy_fixture_catalog.py`
- Create: `apk-work/ui-redesign/test_renpy_legacy_writer.py`
- Create: `apk-work/samples/renpy-legacy/manifest.json`
- Create: `docs/qa/renpy-legacy-writer-matrix.md`

**Interfaces:**
- Produces: `load_fixture_catalog(path: Path) -> list[Fixture]`。
- Produces manifest fields: `fixtureId`、`sourceSha256`、`container`、`slot`、`pickleProtocol`、`expectedDialectId`、`licenseEvidence`、`deviceRequired`。

- [ ] **Step 1: 写失败测试**

```python
def test_fixture_catalog_rejects_missing_hash_or_legal_evidence():
    manifest = {"fixtures": [{"fixtureId": "renpy6-a", "sourceSha256": ""}]}
    with self.assertRaisesRegex(ValueError, "fixture_catalog_invalid"):
        load_fixture_catalog(write_manifest(manifest))
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_fixture_catalog_rejects_missing_hash_or_legal_evidence -v`

Expected: FAIL because `renpy_legacy_fixture_catalog` does not exist.

- [ ] **Step 3: 实现 manifest parser**

```python
@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    source_sha256: str
    container: str
    slot: int
    pickle_protocol: int
    expected_dialect_id: str
    license_evidence: str
    device_required: bool
```

只允许 64 位小写 SHA-256、非空合法性说明、slot 1/2 和 protocol 2；fixture 二进制不提交时，manifest 仍记录外部样本哈希和获取说明。

- [ ] **Step 4: 运行目录测试**

Run: `python -m unittest test_renpy_legacy_writer -v`

Expected: PASS; 缺字段、重复 ID、哈希不一致和未授权样本全部失败关闭。

- [ ] **Step 5: 提交 fixture 目录**

```powershell
git add apk-work/ui-redesign/renpy_legacy_fixture_catalog.py apk-work/ui-redesign/test_renpy_legacy_writer.py apk-work/samples/renpy-legacy/manifest.json docs/qa/renpy-legacy-writer-matrix.md
git commit --only -m "test: add renpy legacy fixture catalog" -- apk-work/ui-redesign/renpy_legacy_fixture_catalog.py apk-work/ui-redesign/test_renpy_legacy_writer.py apk-work/samples/renpy-legacy/manifest.json docs/qa/renpy-legacy-writer-matrix.md
```

### Task 2: 用完整结构指纹识别 legacy 方言

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectDescriptor.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectRegistry.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java`
- Test: `apk-work/ui-redesign/test_renpy_legacy_writer.py`

**Interfaces:**
- Produces: `RenpyDialectDescriptor.fingerprint() -> String`。
- Produces: `RenpyDialectRegistry.match(RpycCompatibility.Evidence) -> RenpyDialectDescriptor|null`。
- Extends: `RpycCompatibility.Report.dialectId`、`writerId`、`dialectVerified`。

- [ ] **Step 1: 写失败的 Java harness**

```java
RenpyDialectDescriptor matched = RenpyDialectRegistry.match(evidence(
        "RPC2", 1, 2, set("__builtin__.set", "renpy.ast.TranslateString"),
        set("PROTO", "GLOBAL", "BINUNICODE", "TUPLE2", "REDUCE", "STOP"), 5003000, 1));
require(matched != null, "registered dialect must match");
require(RenpyDialectRegistry.match(evidence(
        "RPC2", 1, 2, set("evil.module.Class"), matched.opcodes, 5003000, 1)) == null,
        "unknown GLOBAL must fail closed");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_dialect_registry_requires_complete_fingerprint -v`

Expected: FAIL during javac because descriptor and registry are absent.

- [ ] **Step 3: 实现不可变 descriptor 和白名单 registry**

```java
public final class RenpyDialectDescriptor {
    public final String dialectId;
    public final String container;
    public final int preferredSlot;
    public final int pickleProtocol;
    public final Set<String> allowedGlobals;
    public final Set<String> allowedOpcodes;
    public final int version;
    public final int key;
}
```

`match` 对所有字段做精确比较；集合比较使用 canonical sorted representation。registry 首次只登记 fixture 矩阵中两个样本都通过的 dialect。

- [ ] **Step 4: 运行识别回归**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_dialect_registry_requires_complete_fingerprint test_fast_scanner.FastApkScannerContractTest.test_rpyc_compatibility_separates_modern_legacy_and_unknown_generation -v`

Expected: PASS; 未登记 legacy 仍为 extract-only。

- [ ] **Step 5: 提交方言识别**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectDescriptor.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectRegistry.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java apk-work/ui-redesign/test_renpy_legacy_writer.py
git commit --only -m "feat: identify verified renpy legacy dialects" -- apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectDescriptor.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyDialectRegistry.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java apk-work/ui-redesign/test_renpy_legacy_writer.py
```

### Task 3: 参数化 protocol 2 writer

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyLegacyRpycWriter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java`
- Test: `apk-work/ui-redesign/test_renpy_legacy_writer.py`

**Interfaces:**
- Produces: `RenpyLegacyRpycWriter.build(RenpyDialectDescriptor, String, String, List<String[]>) -> byte[]`。
- Produces: `RpycPickleWriter.buildTranslationPickle(..., RenpyDialectDescriptor) -> byte[]`。

- [ ] **Step 1: 写失败的 opcode 测试**

```java
byte[] result = RenpyLegacyRpycWriter.build(dialect, "schinese", "legacy.rpy",
        Arrays.asList(new String[]{"Hello %s", "你好 %s"}));
List<String> opcodes = PickleTestSupport.opcodes(result);
require(!opcodes.contains("FRAME") && !opcodes.contains("MEMOIZE"),
        "protocol 2 output must not contain protocol 4 opcodes");
require(PickleTestSupport.globals(result).equals(dialect.allowedGlobals),
        "writer globals must stay inside the dialect whitelist");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_protocol2_writer_emits_only_registered_dialect_shape -v`

Expected: FAIL because `RenpyLegacyRpycWriter.build` is absent.

- [ ] **Step 3: 实现最小 legacy writer**

writer 只允许 protocol 2 descriptor；调用现有文本 validator；按 descriptor 输出 slot、version/key 和 GLOBAL 名称。任何 pair 无效、descriptor 未 verified 或输出 opcode 超出白名单都抛出 `renpy_legacy_writer_unverified`。

```java
if (dialect == null || dialect.pickleProtocol != 2
        || !RenpyDialectRegistry.isVerified(dialect.dialectId)) {
    throw new IOException("renpy_legacy_writer_unverified");
}
```

- [ ] **Step 4: 运行 writer 与现代路径回归**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_protocol2_writer_emits_only_registered_dialect_shape test_fast_scanner.FastApkScannerContractTest.test_protocol2_writer_uses_only_python2_compatible_opcodes -v`

Expected: PASS; 现代 writer 输出字节保持原样。

- [ ] **Step 5: 提交 writer**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyLegacyRpycWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java apk-work/ui-redesign/test_renpy_legacy_writer.py
git commit --only -m "feat: add verified renpy protocol2 writer" -- apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyLegacyRpycWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/RpycPickleWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyRpycWriter.java apk-work/ui-redesign/test_renpy_legacy_writer.py
```

### Task 4: 增加方言级产物重读和 compiler 路由

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPatchValidator.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`
- Test: `apk-work/ui-redesign/test_renpy_legacy_writer.py`

**Interfaces:**
- Produces: `validateCompiledRpyc(..., RenpyDialectDescriptor) -> Result`。
- Compiler result fields: `dialectId`、`writerId`、`writerVerified`。

- [ ] **Step 1: 写失败的编译路由测试**

```java
TranslationArtifact artifact = TranslationCompiler.compileTranslationArtifact(
        "always_on", pairs, legacyMeta);
require("renpy6-protocol2-v1".equals(artifact.dialectId), "dialect route");
require(artifact.validation.valid, "artifact must be independently re-read");
require(artifact.validation.translationCount == pairs.size(), "count must match");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_compiler_routes_only_verified_legacy_dialect -v`

Expected: FAIL because compiler artifact lacks dialect metadata and route.

- [ ] **Step 3: 实现路由与 validator**

compiler 先调用 registry；matched 时使用 legacy writer，unmatched 立即返回 `writerBlocked=true`。validator 从生成 bytes 重新读取 container、slot、protocol、GLOBAL、opcode、version/key 和翻译 pair，不复用 writer 内部对象。

- [ ] **Step 4: 运行编译器回归**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_compiler_routes_only_verified_legacy_dialect test_fast_scanner.FastApkScannerContractTest.test_compiled_rpyc_validator_rejects_corrupt_or_mismatched_outputs -v`

Expected: PASS; 一个字段变化即阻断。

- [ ] **Step 5: 提交路由**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPatchValidator.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/test_renpy_legacy_writer.py
git commit --only -m "feat: validate and route legacy renpy artifacts" -- apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPatchValidator.java apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java apk-work/ui-redesign/test_renpy_legacy_writer.py
```

### Task 5: 隔离评估匹配版本编译器后端

**Files:**
- Create: `apk-work/ui-redesign/probe_renpy_legacy_compiler.py`
- Modify: `apk-work/ui-redesign/test_renpy_legacy_writer.py`
- Modify: `docs/qa/renpy-legacy-writer-matrix.md`

**Interfaces:**
- Produces: `probe_compiler(sdk_dir, fixture_dir, output_json) -> dict`。
- Report fields: `sdkVersion`、`license`、`inputSha256`、`outputSha256`、`reReadValid`、`startupValidated`、`peakRssMb`、`elapsedMs`。

- [ ] **Step 1: 写失败的探针解析测试**

```python
def test_probe_report_requires_re_read_and_startup_evidence():
    result = evaluate_probe({"reReadValid": True, "startupValidated": False})
    self.assertEqual(result["decision"], "disabled")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_probe_report_requires_re_read_and_startup_evidence -v`

Expected: FAIL because probe evaluator is absent.

- [ ] **Step 3: 实现只读探针**

探针在临时目录调用用户提供的合法 Ren'Py SDK，不修改 Android app，不下载 SDK，不上传游戏文件。只有 `reReadValid=true`、`startupValidated=true`、峰值 RSS `<=512MB`、输出可复现且许可证允许分发时，报告 `candidate`；否则固定 `disabled`。

- [ ] **Step 4: 运行探针测试**

Run: `python -m unittest test_renpy_legacy_writer -v`

Expected: PASS; 缺 SDK 时输出 `dependency_unavailable`，不是伪成功。

- [ ] **Step 5: 提交探针**

```powershell
git add apk-work/ui-redesign/probe_renpy_legacy_compiler.py apk-work/ui-redesign/test_renpy_legacy_writer.py docs/qa/renpy-legacy-writer-matrix.md
git commit --only -m "test: evaluate matched renpy compiler backend" -- apk-work/ui-redesign/probe_renpy_legacy_compiler.py apk-work/ui-redesign/test_renpy_legacy_writer.py docs/qa/renpy-legacy-writer-matrix.md
```

### Task 6: 真机升级 verified 方言

**Files:**
- Modify: `docs/qa/renpy-legacy-writer-matrix.md`
- Modify: `docs/qa/renpy-release-checklist.md`
- Test: `apk-work/ui-redesign/test_renpy_legacy_writer.py`

**Interfaces:**
- Verifies: 每个 dialect 的 extract、translate、write、re-read、sign、install、launch、Chinese text、save/load、rollback。

- [ ] **Step 1: 写失败的矩阵完整性测试**

```python
def test_verified_dialect_rows_require_two_samples_and_device_evidence():
    rows = load_matrix(MATRIX)
    self.assertTrue(all(row.sample_count >= 2 for row in rows if row.status == "VERIFIED"))
    self.assertTrue(all(row.launch and row.chinese_text and row.save_load
                        for row in rows if row.status == "VERIFIED"))
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_renpy_legacy_writer.RenpyLegacyWriterTest.test_verified_dialect_rows_require_two_samples_and_device_evidence -v`

Expected: FAIL until matrix evidence is recorded.

- [ ] **Step 3: 构建并执行设备矩阵**

Run: `Set-Location D:\文件翻译\apk-work\native-fast-scan; python build_fast_scanner.py; Set-Location ..\ui-redesign; python build_workshop_apk.py`

Run: `adb install -r D:\文件翻译\apk-work\slg-workshop-ui-signed.apk`

对每个 dialect 的两个合法样本记录 APK SHA-256、生成物 SHA-256、签名、安装、启动、中文、存档加载和回滚结果。

- [ ] **Step 4: 运行全量回归**

Run: `python -m unittest test_renpy_legacy_writer.py test_fast_scanner.py test_workshop_patch.py test_translation_quality.py test_translation_coverage.py -v`

Expected: PASS; 未验证 dialect 仍导出 JSON，不显示安装操作。

- [ ] **Step 5: 提交验收证据**

```powershell
git add docs/qa/renpy-legacy-writer-matrix.md docs/qa/renpy-release-checklist.md apk-work/ui-redesign/test_renpy_legacy_writer.py
git commit --only -m "test: verify renpy legacy writer matrix" -- docs/qa/renpy-legacy-writer-matrix.md docs/qa/renpy-release-checklist.md apk-work/ui-redesign/test_renpy_legacy_writer.py
```

## Self-Review Results

- 范围覆盖：fixture、方言识别、writer、重读、compiler 路由、匹配编译器探针和真机矩阵均有任务。
- 安全边界：未知 legacy 方言始终保持 `TRANSLATABLE_NO_PATCH`，没有 protocol 通配放行。
- 类型一致：统一使用 `RenpyDialectDescriptor`、`RenpyDialectRegistry`、`RenpyLegacyRpycWriter` 和 `dialectId`。
- 验证闭环：每个 verified dialect 需要两个样本、独立重读和真机启动/中文/存档证据。
