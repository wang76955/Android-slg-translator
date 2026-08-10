# Android Resource Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Android `resources.arsc`、二进制 XML、`string`、`plurals` 和 `string-array` 建立结构化提取与安全重建后端，并在完整 base/split 集合上验证安装和中文生效。

**Architecture:** 先把 ARSCLib 作为候选依赖执行 Android 端 D8、读取、修改、重建和重读技术门禁；通过后由 `AndroidResourceAdapter` 生成带 resource ID、config 和 sourceOwner 的记录，`AndroidResourceWriter` 只修改明确定位的资源项。writer 输出到临时 APK 集合，独立 adapter 重读后才交给现有签名与安装流程；候选依赖未通过时保持 `TRANSLATABLE_NO_PATCH`。

**Tech Stack:** Java 8、Android binary resources、ARSCLib `1.4.0` 候选、Capacitor、ZIP streams、Python `unittest`、javac/D8、APKTool/apksigner、ADB。

## Global Constraints

- 前置条件：阶段 0 能力分层已通过；不得绕过 `EngineAdapter`/`WriterBackend`。
- 不允许对 `resources.arsc` 或 binary XML 做等长字节替换。
- 候选依赖必须通过 Apache-2.0 许可证、D8、Android 13 启动、增量体积 `<=8 MiB`、峰值 PSS 增量 `<=120 MiB` 门禁。
- 只支持 `string`、`plurals`、`string-array`；style、drawable、layout 任意文本和 DEX hardcoded string 不进入首版。
- 保留 locale qualifier、默认资源回退、resource ID、bag parent、数组顺序和 binary XML 引用。
- `%s`、`%d`、位置参数、转义、HTML span 和 `translatable=false` 必须确定性校验。
- 完整 split 集合不可用时返回 `split_set_incomplete`，不得生成 base-only 可安装补丁。
- writer 不覆盖源 APK，失败后删除临时集合。
- 每个 verified 版本至少两个资源布局不同的合法 APK。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceAdapter.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceRecord.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceWriter.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceValidator.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceDependencyProbe.java`
- Create: `apk-work/ui-redesign/test_android_resource_backend.py`
- Create: `docs/qa/android-resource-backend-matrix.md`
- Modify: `apk-work/native-fast-scan/fetch_third_party.py`
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`

## Tasks

### Task 1: 封闭验证 ARSCLib 候选依赖

**Files:**
- Modify: `apk-work/native-fast-scan/fetch_third_party.py`
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceDependencyProbe.java`
- Test: `apk-work/ui-redesign/test_android_resource_backend.py`

**Interfaces:**
- Produces: `AndroidResourceDependencyProbe.probe(byte[] arsc, byte[] binaryXml) -> ProbeResult`。
- Produces: `ProbeResult.readOk/writeOk/reReadOk/outputBytes/errorCode`。

- [ ] **Step 1: 写失败测试**

```python
def test_arsclib_dependency_is_pinned_and_probe_requires_reread():
    source = PROBE.read_text("utf-8")
    self.assertIn("reReadOk", source)
    self.assertIn("android_resource_rebuild_unavailable", source)
    self.assert_pinned_jar("arsclib", "1.4.0")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_android_resource_backend.AndroidResourceBackendTest.test_arsclib_dependency_is_pinned_and_probe_requires_reread -v`

Expected: FAIL because dependency and probe are absent.

- [ ] **Step 3: 添加带 SHA-256 的依赖下载和 probe**

`fetch_third_party.py` 固定 Maven 坐标、版本和 SHA-256；哈希不匹配立即删除 jar。probe 读取 fixture、修改一个独立字符串、序列化、重新解析并比较 resource ID/config/value；任何异常返回 `android_resource_rebuild_unavailable`。

- [ ] **Step 4: 构建并运行依赖门禁**

Run: `Set-Location D:\文件翻译\apk-work\native-fast-scan; python fetch_third_party.py; python build_fast_scanner.py; Set-Location ..\ui-redesign; python -m unittest test_android_resource_backend -v`

Expected: PASS; D8 无 duplicate class，probe 重读成功，体积和内存报告写入测试输出。

- [ ] **Step 5: 提交依赖探针**

```powershell
git add apk-work/native-fast-scan/fetch_third_party.py apk-work/native-fast-scan/build_fast_scanner.py apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceDependencyProbe.java apk-work/ui-redesign/test_android_resource_backend.py
git commit --only -m "test: gate android resource dependency" -- apk-work/native-fast-scan/fetch_third_party.py apk-work/native-fast-scan/build_fast_scanner.py apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceDependencyProbe.java apk-work/ui-redesign/test_android_resource_backend.py
```

### Task 2: 结构化提取 Android 资源记录

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceRecord.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceAdapter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_android_resource_backend.py`

**Interfaces:**
- Produces: `AndroidResourceAdapter.extract(InstalledApkSet) -> List<AndroidResourceRecord>`。
- Record fields: `recordId/sourceOwner/resourceId/packageName/type/name/config/sourceText/index/translatable`。

- [ ] **Step 1: 写失败的提取 harness**

```java
List<AndroidResourceRecord> records = AndroidResourceAdapter.extract(fixtureSet);
require(find(records, "string", "app_name").sourceText.equals("Demo"), "string");
require(find(records, "plurals", "count", "one").sourceOwner.equals("base"), "plural owner");
require(find(records, "string-array", "items", 1).sourceText.equals("Second"), "array order");
require(records.stream().noneMatch(r -> !r.translatable), "non-translatable excluded");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_android_resource_backend.AndroidResourceBackendTest.test_adapter_extracts_string_plural_array_and_owner -v`

Expected: FAIL because adapter and record types are absent.

- [ ] **Step 3: 实现 adapter**

adapter 按 base 后 split 顺序读取资源表；`recordId` 使用 adapterId、sourceOwner、resourceId、config、type、index 和原文计算。二进制 XML 只用于确认引用和诊断，不把 layout literal 自动列为首版可写记录。

- [ ] **Step 4: 运行提取测试**

Run: `python -m unittest test_android_resource_backend -v`

Expected: PASS; locale、重复资源名、split owner 和数组顺序稳定。

- [ ] **Step 5: 提交 adapter**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceRecord.java apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_android_resource_backend.py
git commit --only -m "feat: extract structured android resources" -- apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceRecord.java apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_android_resource_backend.py
```

### Task 3: 校验格式参数、span 和资源形状

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceValidator.java`
- Test: `apk-work/ui-redesign/test_android_resource_backend.py`

**Interfaces:**
- Produces: `validate(AndroidResourceRecord, String) -> ValidationResult`。

- [ ] **Step 1: 写失败测试**

```java
require(validate(record("%1$s has %2$d"), "%1$s 有 %2$d").valid, "valid format");
require(hasCode(validate(record("%1$s has %2$d"), "%s 有 %d"), "format_argument_changed"), "position");
require(hasCode(validate(record("<b>Hello</b>"), "Hello"), "span_changed"), "span");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_android_resource_backend.AndroidResourceBackendTest.test_validator_preserves_android_format_and_spans -v`

Expected: FAIL because validator is absent.

- [ ] **Step 3: 实现 token validator**

解析 printf token、转义和 span 树；plurals 必须保留 quantity 集合，array 必须保留长度。空译文和新增资源引用失败关闭。

- [ ] **Step 4: 运行 validator 测试**

Run: `python -m unittest test_android_resource_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交 validator**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceValidator.java apk-work/ui-redesign/test_android_resource_backend.py
git commit --only -m "feat: validate android resource translations" -- apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceValidator.java apk-work/ui-redesign/test_android_resource_backend.py
```

### Task 4: 重建资源表并独立重读

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceWriter.java`
- Test: `apk-work/ui-redesign/test_android_resource_backend.py`

**Interfaces:**
- Produces: `write(InstalledApkSet, Map<String,String>, File) -> PatchArtifact`。
- Produces: `validate(PatchArtifact) -> PatchValidationReport`。

- [ ] **Step 1: 写失败的 writer 测试**

```java
PatchArtifact artifact = writer.write(sourceSet, approved, outputDir);
require(!artifact.modifiedOwners.contains("split:config.xxhdpi"), "unowned split untouched");
require(writer.validate(artifact).valid, "independent reread");
require(sha256(sourceSet.baseApk).equals(originalSha), "source unchanged");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_android_resource_backend.AndroidResourceBackendTest.test_writer_rebuilds_only_owned_resources_and_rereads -v`

Expected: FAIL because writer is absent.

- [ ] **Step 3: 实现 owner-aware writer**

每个 owner 独立复制 APK、修改其资源表、重建 ZIP；保留未修改 entry 的压缩方式。validator 使用新的 adapter 实例读取产物并按 recordId 比较译文、resource ID、config 和集合形状。

- [ ] **Step 4: 运行 writer 测试**

Run: `python -m unittest test_android_resource_backend -v`

Expected: PASS; corrupt table、owner mismatch 和 split 缺失均失败关闭。

- [ ] **Step 5: 提交 writer**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceWriter.java apk-work/ui-redesign/test_android_resource_backend.py
git commit --only -m "feat: rebuild validated android resources" -- apk-work/native-fast-scan/src/com/slgtranslator/app/AndroidResourceWriter.java apk-work/ui-redesign/test_android_resource_backend.py
```

### Task 5: 接入能力、UI 与完整 APK 集合

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Test: `apk-work/ui-redesign/test_android_resource_backend.py`

**Interfaces:**
- Adapter ID: `android-resources`。
- Error codes: `android_resource_rebuild_unavailable`、`writer_output_invalid`、`split_set_incomplete`。

- [ ] **Step 1: 写失败的流程测试**

```javascript
check(scan.adapterId===`android-resources`,`adapter`);
check(scan.workflow===`PATCHABLE_VERIFIED`,`workflow after dependency gate`);
await startTranslation();
check(writerCalls===1&&buildCalls===1&&installCalls===0,`build but do not auto-install`);
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_android_resource_backend test_workshop_patch.WorkshopPatchContractTest.test_android_resource_workflow -v`

Expected: FAIL because workflow routing is absent.

- [ ] **Step 3: 实现 adapter 路由和用户状态**

依赖 probe 未通过时返回 `TRANSLATABLE_NO_PATCH`；通过且 source set 完整时返回 `PATCHABLE_VERIFIED`。完成状态显示“Android 资源补丁已生成”，安装仍由用户明确触发。

- [ ] **Step 4: 运行集成测试**

Run: `python -m unittest test_android_resource_backend.py test_fast_scanner.py test_workshop_patch.py -v`

Expected: PASS.

- [ ] **Step 5: 提交集成**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_android_resource_backend.py
git commit --only -m "feat: integrate android resource backend" -- apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_android_resource_backend.py
```

### Task 6: 真机资源矩阵验收

**Files:**
- Create: `docs/qa/android-resource-backend-matrix.md`
- Modify: `docs/qa/renpy-release-checklist.md`
- Test: `apk-work/ui-redesign/test_android_resource_backend.py`

**Interfaces:**
- Verifies two distinct resource layouts and one complete split set。

- [ ] **Step 1: 写失败的矩阵测试**

```python
def test_verified_rows_require_reread_install_launch_and_chinese_text():
    self.assert_matrix_complete(MATRIX, minimum_samples=2, require_split=True)
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_android_resource_backend.AndroidResourceBackendTest.test_verified_rows_require_reread_install_launch_and_chinese_text -v`

Expected: FAIL until device evidence exists.

- [ ] **Step 3: 构建、签名并安装样本**

Run: `Set-Location D:\文件翻译\apk-work\ui-redesign; python build_workshop_apk.py; adb install -r D:\文件翻译\apk-work\slg-workshop-ui-signed.apk`

记录资源重读、zipalign、v2/v3 签名、安装、启动、中文、资源回退和 split session 结果。

- [ ] **Step 4: 运行全量回归**

Run: `python -m unittest test_android_resource_backend.py test_fast_scanner.py test_workshop_patch.py test_built_apk.py -v`

Expected: PASS.

- [ ] **Step 5: 提交验收证据**

```powershell
git add docs/qa/android-resource-backend-matrix.md docs/qa/renpy-release-checklist.md apk-work/ui-redesign/test_android_resource_backend.py
git commit --only -m "test: verify android resource backend" -- docs/qa/android-resource-backend-matrix.md docs/qa/renpy-release-checklist.md apk-work/ui-redesign/test_android_resource_backend.py
```

## Self-Review Results

- 范围覆盖：依赖门禁、提取、格式校验、owner-aware writer、UI 和真机矩阵均有任务。
- 安全边界：无 ARSCLib 技术验证时保持导出能力，不退回二进制替换。
- Split 边界：所有记录和产物保留 manifest splitName，缺集合失败关闭。
- 验证闭环：writer 输出由全新 adapter 实例重读后才进入签名流程。
