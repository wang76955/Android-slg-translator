# Structured Text Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 APK assets 中的 JSON、CSV/TSV、Java properties 和明确 UTF-8 纯文本提供结构化提取、翻译、写回和重解析验证。

**Architecture:** `StructuredTextAdapter` 按格式选择独立 codec，不使用跨格式正则；JSON 使用固定 Gson `2.13.2`，CSV/TSV 使用 Apache Commons CSV `1.14.1`，properties 使用项目内确定性 continuation/escape parser。`StructuredTextWriter` 只写 adapter 生成的 recordId，写后重新解析并逐条核对 key、类型、数组顺序和译文。

**Tech Stack:** Java 8、Gson 2.13.2、Apache Commons CSV 1.14.1、UTF-8、ZIP streams、Python `unittest`、javac/D8、ADB。

## Global Constraints

- 前置条件：阶段 0 完成；项目 JSON 导入导出可复用。
- 首版只支持 JSON、CSV、TSV、properties 和可确认 UTF-8 的纯文本。
- YAML、Lua、JavaScript、任意 XML 和 HTML 不进入本计划 writer。
- JSON 保留 key/array 顺序和数字、布尔、null 类型；重复 key 进入诊断并阻断写入。
- CSV/TSV 保留 delimiter、quote、header、空字段、行尾和列数。
- properties 保留 key、continuation、escape 和重复 key 诊断；不使用 `java.util.Properties.store()` 重写整个文件。
- 编码不明确、BOM 冲突或解码替换字符存在时返回 `structured_extraction_unavailable`。
- writer 只修改声明 owner/path，源 APK 不变。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextRecord.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextAdapter.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextWriter.java`。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/JsonAssetCodec.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/DelimitedAssetCodec.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/PropertiesAssetCodec.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/PlainTextAssetCodec.java`。
- Create: `apk-work/ui-redesign/test_structured_text_backend.py`。
- Create: `docs/qa/structured-text-backend-matrix.md`。
- Modify: `apk-work/native-fast-scan/fetch_third_party.py`、`apk-work/native-fast-scan/build_fast_scanner.py`、`apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`、`apk-work/ui-redesign/patch_workshop_ui.py`。

## Tasks

### Task 1: 固定 parser 依赖并验证 Android 构建

**Files:**
- Modify: `apk-work/native-fast-scan/fetch_third_party.py`
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py`
- Create: `apk-work/ui-redesign/test_structured_text_backend.py`

**Interfaces:**
- Pins: `gson:2.13.2`、`commons-csv:1.14.1` with SHA-256 and license records。

- [ ] **Step 1: 写失败测试**

```python
def test_structured_parser_jars_are_pinned_and_d8_safe():
    self.assert_pinned("gson", "2.13.2")
    self.assert_pinned("commons-csv", "1.14.1")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_structured_text_backend.StructuredTextBackendTest.test_structured_parser_jars_are_pinned_and_d8_safe -v`

Expected: FAIL because jars are not registered.

- [ ] **Step 3: 增加下载、哈希、许可证和 D8 classpath**

哈希不匹配删除文件；构建后检查 duplicate classes 和 APK 增量体积 `<=4 MiB`。

- [ ] **Step 4: 运行依赖测试**

Run: `Set-Location D:\文件翻译\apk-work\native-fast-scan; python fetch_third_party.py; python build_fast_scanner.py; Set-Location ..\ui-redesign; python -m unittest test_structured_text_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交依赖**

```powershell
git add apk-work/native-fast-scan/fetch_third_party.py apk-work/native-fast-scan/build_fast_scanner.py apk-work/ui-redesign/test_structured_text_backend.py
git commit --only -m "build: add structured text parsers" -- apk-work/native-fast-scan/fetch_third_party.py apk-work/native-fast-scan/build_fast_scanner.py apk-work/ui-redesign/test_structured_text_backend.py
```

### Task 2: 建立公共 record 和 codec 契约

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextRecord.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextAdapter.java`
- Test: `apk-work/ui-redesign/test_structured_text_backend.py`

**Interfaces:**
- Produces: `AssetCodec.detect(path, bytes) -> boolean`、`extract(...) -> List<StructuredTextRecord>`、`rewrite(...)->byte[]`、`verify(...) -> ValidationResult`。
- Record fields: `recordId/sourceOwner/sourcePath/format/keyPath/sourceText/valueType/index`。

- [ ] **Step 1: 写失败的 codec 路由测试**

```java
require(adapter.codecFor("assets/lang/en.json", jsonBytes).id().equals("json"), "json");
require(adapter.codecFor("assets/script.lua", luaBytes) == null, "lua excluded");
require(adapter.codecFor("assets/data.bin", invalidUtf8) == null, "unknown encoding excluded");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_structured_text_backend.StructuredTextBackendTest.test_codec_routing_is_format_specific -v`

Expected: FAIL because adapter contract is absent.

- [ ] **Step 3: 实现 adapter 和稳定 recordId**

codec 选择同时检查扩展名和内容；recordId 哈希 adapterId、owner、path、format、keyPath、index 和 sourceText。

- [ ] **Step 4: 运行路由测试**

Run: `python -m unittest test_structured_text_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交契约**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextRecord.java apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextAdapter.java apk-work/ui-redesign/test_structured_text_backend.py
git commit --only -m "feat: add structured asset codec contract" -- apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextRecord.java apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextAdapter.java apk-work/ui-redesign/test_structured_text_backend.py
```

### Task 3: 实现 JSON codec

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/JsonAssetCodec.java`
- Test: `apk-work/ui-redesign/test_structured_text_backend.py`

**Interfaces:**
- Produces JSON key paths using RFC 6901 escaping。

- [ ] **Step 1: 写失败测试**

```java
byte[] out = codec.rewrite(input, map("/dialogue/0/text", "你好"));
JsonElement parsed = JsonParser.parseString(new String(out, UTF_8));
require(parsed.getAsJsonObject().get("count").getAsInt() == 2, "number preserved");
require(parsed.getAsJsonObject().get("enabled").getAsBoolean(), "boolean preserved");
require(keyOrder(parsed).equals(Arrays.asList("dialogue", "count", "enabled")), "key order");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_structured_text_backend.StructuredTextBackendTest.test_json_codec_preserves_types_order_and_paths -v`

Expected: FAIL because codec is absent.

- [ ] **Step 3: 实现 JSON AST rewrite**

只替换原来为 string 的节点；数字、布尔、null、object key 和 array shape 不可修改。预扫描重复 key，发现后返回 `structured_json_duplicate_key`。

- [ ] **Step 4: 运行 JSON 测试**

Run: `python -m unittest test_structured_text_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交 JSON codec**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/JsonAssetCodec.java apk-work/ui-redesign/test_structured_text_backend.py
git commit --only -m "feat: add json asset translation codec" -- apk-work/native-fast-scan/src/com/slgtranslator/app/JsonAssetCodec.java apk-work/ui-redesign/test_structured_text_backend.py
```

### Task 4: 实现 CSV/TSV、properties 和纯文本 codec

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/DelimitedAssetCodec.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/PropertiesAssetCodec.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/PlainTextAssetCodec.java`
- Test: `apk-work/ui-redesign/test_structured_text_backend.py`

**Interfaces:**
- Delimited keys: `row:<n>/column:<header-or-index>`。
- Properties keys: decoded logical key plus occurrence index。

- [ ] **Step 1: 写失败测试**

```java
require(csv.roundTrip("id,text\r\n1,\"Hello, world\"\r\n").lineEnding.equals("\r\n"), "CSV");
require(properties.extract("a=one\\\n two\na=duplicate\n").duplicateKeys.contains("a"), "duplicate");
require(plain.detect(utf16WithoutBom) == false, "ambiguous encoding");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_structured_text_backend.StructuredTextBackendTest.test_delimited_properties_and_plain_text_roundtrip -v`

Expected: FAIL because codecs are absent.

- [ ] **Step 3: 实现三个 codec**

CSV 使用 Commons CSV format snapshot；properties parser 保存原始 segment 和 continuation；纯文本只接受 UTF-8/BOM UTF-8，按非空可翻译行建立记录。

- [ ] **Step 4: 运行 codec 测试**

Run: `python -m unittest test_structured_text_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交 codecs**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/DelimitedAssetCodec.java apk-work/native-fast-scan/src/com/slgtranslator/app/PropertiesAssetCodec.java apk-work/native-fast-scan/src/com/slgtranslator/app/PlainTextAssetCodec.java apk-work/ui-redesign/test_structured_text_backend.py
git commit --only -m "feat: add delimited properties and text codecs" -- apk-work/native-fast-scan/src/com/slgtranslator/app/DelimitedAssetCodec.java apk-work/native-fast-scan/src/com/slgtranslator/app/PropertiesAssetCodec.java apk-work/native-fast-scan/src/com/slgtranslator/app/PlainTextAssetCodec.java apk-work/ui-redesign/test_structured_text_backend.py
```

### Task 5: 写回 APK、重解析并接入 UI

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextWriter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`、`apk-work/ui-redesign/patch_workshop_ui.py`、`apk-work/ui-redesign/test_workshop_patch.py`
- Test: `apk-work/ui-redesign/test_structured_text_backend.py`

**Interfaces:**
- Adapter ID: `structured-text`。
- Produces: `write(InstalledApkSet, approved, outputDir) -> PatchArtifact`。

- [ ] **Step 1: 写失败流程测试**

```javascript
await translateFixture(`assets/lang/en.json`);
check(writerCalls===1&&verifyCalls===1&&buildCalls===1,`writer flow`);
check(lastResult.workflow===`PATCHABLE_VERIFIED`,`verified codec`);
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_structured_text_backend test_workshop_patch.WorkshopPatchContractTest.test_structured_text_workflow -v`

Expected: FAIL because writer and routing are absent.

- [ ] **Step 3: 实现 owner-aware ZIP writer 和重解析**

writer 对每个文件调用原 codec rewrite；验证阶段重新选择 codec、解析产物并按 recordId 比较。任何 key/shape/type/译文不一致返回 `writer_output_invalid`。

- [ ] **Step 4: 运行集成测试**

Run: `python -m unittest test_structured_text_backend.py test_fast_scanner.py test_workshop_patch.py -v`

Expected: PASS.

- [ ] **Step 5: 提交集成**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_structured_text_backend.py
git commit --only -m "feat: integrate structured text backend" -- apk-work/native-fast-scan/src/com/slgtranslator/app/StructuredTextWriter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_structured_text_backend.py
```

### Task 6: 样本矩阵和真机验收

**Files:**
- Create: `docs/qa/structured-text-backend-matrix.md`
- Test: `apk-work/ui-redesign/test_structured_text_backend.py`

**Interfaces:**
- Verifies at least JSON and one delimited/properties sample on device。

- [ ] **Step 1: 写失败矩阵测试**

```python
def test_verified_formats_have_reread_install_launch_and_text_evidence():
    self.assert_formats_verified({"json", "csv", "properties"})
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_structured_text_backend.StructuredTextBackendTest.test_verified_formats_have_reread_install_launch_and_text_evidence -v`

Expected: FAIL until evidence exists.

- [ ] **Step 3: 构建并执行设备样本**

Run: `Set-Location D:\文件翻译\apk-work\ui-redesign; python build_workshop_apk.py; adb install -r D:\文件翻译\apk-work\slg-workshop-ui-signed.apk`

- [ ] **Step 4: 运行全量回归**

Run: `python -m unittest test_structured_text_backend.py test_fast_scanner.py test_workshop_patch.py test_built_apk.py -v`

Expected: PASS.

- [ ] **Step 5: 提交证据**

```powershell
git add docs/qa/structured-text-backend-matrix.md apk-work/ui-redesign/test_structured_text_backend.py
git commit --only -m "test: verify structured text backend" -- docs/qa/structured-text-backend-matrix.md apk-work/ui-redesign/test_structured_text_backend.py
```

## Self-Review Results

- 范围覆盖：依赖、公共契约、JSON、CSV/TSV、properties、纯文本、writer、UI 和设备矩阵完整。
- 格式边界：每种格式使用独立 parser；YAML/Lua/JS/XML/HTML 明确排除。
- 类型一致：统一使用 `StructuredTextRecord`、`AssetCodec`、`StructuredTextAdapter` 和 `StructuredTextWriter`。
- 验证闭环：每个输出文件都由对应 parser 重解析并按 recordId 对照。
