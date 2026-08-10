# Unity Static Localization Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Unity APK 中独立 JSON/CSV/Localization 表复用 structured-text writer 安全写回，并对 `resources.assets`/AssetBundle 建立版本化检测和 parser/writer 技术门禁；IL2CPP/native 内容保持诊断或导出。

**Architecture:** `UnityLocalizationAdapter` 通过 `globalgamemanagers`、`data.unity3d`、UnityPlayer/native library 和目录结构多证据检测 Unity，再把独立本地化文件委托给 `StructuredTextAdapter`。深层 Unity 资源使用独立 host probe 基于 AssetsTools.NET `3.0.4` 建立格式矩阵，但在找到可在 Android 应用内合法、稳定运行的 parser/writer 前不升级 `canWritePatch`。

**Tech Stack:** Java 8、structured-text backend、Unity serialized file/AssetBundle diagnostics、AssetsTools.NET 3.0.4 host probe、Python `unittest`、ADB。

## Global Constraints

- 前置条件：阶段 0 和 structured-text backend 完成。
- 只有独立 JSON/CSV/Localization 表可以在首版升级为 `PATCHABLE_VERIFIED`。
- `TextAsset`、`resources.assets`、AssetBundle 在 parser/writer 门禁通过前保持 `TRANSLATABLE_NO_PATCH`。
- IL2CPP、`libil2cpp.so`、native hardcoded string、运行时解密和远程资源不进入 writer。
- 不能用扩展名或 `UnityPlayerActivity` 单一证据判定完整支持。
- Unity writer 必须保持 path ID、type tree、bundle compression、resource reference 和 entry order。
- host probe 不得被包装成 Android 已实现能力。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/UnityLocalizationAdapter.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/UnityEvidence.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/UnityStaticLocalizationWriter.java`。
- Create: `apk-work/ui-redesign/probe_unity_assets.py`、`apk-work/ui-redesign/test_unity_backend.py`。
- Create: `docs/qa/unity-backend-matrix.md`。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`、`apk-work/ui-redesign/patch_workshop_ui.py`、`apk-work/ui-redesign/test_workshop_patch.py`。

## Tasks

### Task 1: 多证据检测 Unity 和支持层级

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/UnityEvidence.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/UnityLocalizationAdapter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_unity_backend.py`

**Interfaces:**
- Produces: `detect(InstalledApkSet) -> DetectionResult` with `confidence/evidence/staticFiles/deepAssets/il2cppSignals/workflow`。

- [ ] **Step 1: 写失败测试**

```java
require(adapter.detect(unityJsonFixture).workflow.equals("PATCHABLE_VERIFIED"), "independent locale");
require(adapter.detect(assetBundleOnly).workflow.equals("TRANSLATABLE_NO_PATCH"), "bundle export only");
require(adapter.detect(fakeUnityName).adapterDetected == false, "filename alone insufficient");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_unity_backend.UnityBackendTest.test_detection_separates_static_bundle_and_false_positive -v`

Expected: FAIL because Unity adapter is absent.

- [ ] **Step 3: 实现证据聚合**

至少两个独立证据才判定 Unity；静态文件必须通过 structured-text codec detect。输出 `unity_static_localization`、`unity_bundle_writer_unavailable`、`unity_il2cpp_not_patchable` reason code。

- [ ] **Step 4: 运行检测测试**

Run: `python -m unittest test_unity_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交检测**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/UnityEvidence.java apk-work/native-fast-scan/src/com/slgtranslator/app/UnityLocalizationAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_unity_backend.py
git commit --only -m "feat: detect unity localization layers" -- apk-work/native-fast-scan/src/com/slgtranslator/app/UnityEvidence.java apk-work/native-fast-scan/src/com/slgtranslator/app/UnityLocalizationAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_unity_backend.py
```

### Task 2: 复用 structured-text writer 处理独立本地化文件

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/UnityStaticLocalizationWriter.java`
- Test: `apk-work/ui-redesign/test_unity_backend.py`

**Interfaces:**
- Produces: `write(InstalledApkSet, records, translations, outputDir) -> PatchArtifact`。

- [ ] **Step 1: 写失败测试**

```java
PatchArtifact artifact = writer.write(source, records, approved, output);
require(structuredAdapter.reRead(artifact).translations.equals(approved), "reread");
require(artifact.modifiedEntries.equals(set("assets/StreamingAssets/Localization/en.json")), "scope");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_unity_backend.UnityBackendTest.test_static_localization_writer_reuses_structured_codec -v`

Expected: FAIL because writer is absent.

- [ ] **Step 3: 实现委托 writer**

writer 不解析 Unity serialized file，只把 adapter 已确认的独立文件交给 `StructuredTextWriter`；返回 adapterId `unity-static`，保留原 sourceOwner。

- [ ] **Step 4: 运行 writer 测试**

Run: `python -m unittest test_unity_backend test_structured_text_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交 writer**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/UnityStaticLocalizationWriter.java apk-work/ui-redesign/test_unity_backend.py
git commit --only -m "feat: write unity static localization files" -- apk-work/native-fast-scan/src/com/slgtranslator/app/UnityStaticLocalizationWriter.java apk-work/ui-redesign/test_unity_backend.py
```

### Task 3: 建立 AssetTools.NET host 技术探针

**Files:**
- Create: `apk-work/ui-redesign/probe_unity_assets.py`
- Modify: `apk-work/ui-redesign/test_unity_backend.py`
- Modify: `docs/qa/unity-backend-matrix.md`

**Interfaces:**
- Produces: JSON report `unityVersion/serializationVersion/typeTree/bundleCompression/readOk/writeOk/reReadOk/referenceStable/androidRuntimeAvailable`。

- [ ] **Step 1: 写失败报告测试**

```python
def test_bundle_candidate_requires_android_runtime_and_reference_stability():
    report = evaluate_probe({"writeOk": True, "reReadOk": True,
                             "referenceStable": True, "androidRuntimeAvailable": False})
    self.assertEqual(report["workflow"], "TRANSLATABLE_NO_PATCH")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_unity_backend.UnityBackendTest.test_bundle_candidate_requires_android_runtime_and_reference_stability -v`

Expected: FAIL because probe evaluator is absent.

- [ ] **Step 3: 实现隔离 host probe**

探针只读取用户提供的合法 fixture，使用固定 AssetsTools.NET 3.0.4 和 .NET runtime；输出修改前后 path ID、type tree、external refs、compression 和 payload hashes。`androidRuntimeAvailable=false` 时永远不升级 app writer。

- [ ] **Step 4: 运行 probe 测试**

Run: `python -m unittest test_unity_backend -v`

Expected: PASS; 缺 dotnet/fixture 返回 dependency unavailable。

- [ ] **Step 5: 提交探针**

```powershell
git add apk-work/ui-redesign/probe_unity_assets.py apk-work/ui-redesign/test_unity_backend.py docs/qa/unity-backend-matrix.md
git commit --only -m "test: characterize unity asset formats" -- apk-work/ui-redesign/probe_unity_assets.py apk-work/ui-redesign/test_unity_backend.py docs/qa/unity-backend-matrix.md
```

### Task 4: 接入 UI 分层状态和导出

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`、`apk-work/ui-redesign/test_workshop_patch.py`
- Test: `apk-work/ui-redesign/test_unity_backend.py`

**Interfaces:**
- Adapter IDs: `unity-static` and `unity-deep-assets`。

- [ ] **Step 1: 写失败流程测试**

```javascript
check(staticScan.workflow===`PATCHABLE_VERIFIED`,`static writer`);
check(bundleScan.workflow===`TRANSLATABLE_NO_PATCH`,`bundle export`);
check(il2cppScan.reasonCodes.includes(`unity_il2cpp_not_patchable`),`IL2CPP diagnostic`);
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_unity_backend test_workshop_patch.WorkshopPatchContractTest.test_unity_layered_workflows -v`

Expected: FAIL because UI routing is absent.

- [ ] **Step 3: 实现状态与操作**

静态文件显示普通补丁流程；deep assets 显示“可翻译并导出，Unity bundle writer 未验证”；IL2CPP 只显示诊断，不把二进制字符串计入覆盖率。

- [ ] **Step 4: 运行集成测试**

Run: `python -m unittest test_unity_backend.py test_structured_text_backend.py test_workshop_patch.py -v`

Expected: PASS.

- [ ] **Step 5: 提交 UI 集成**

```powershell
git add apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_unity_backend.py
git commit --only -m "feat: expose layered unity workflows" -- apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_unity_backend.py
```

### Task 5: 真机 Unity 静态资源验收

**Files:**
- Create/Modify: `docs/qa/unity-backend-matrix.md`
- Test: `apk-work/ui-redesign/test_unity_backend.py`

**Interfaces:**
- Verifies one static localization sample; bundle and IL2CPP remain blocked unless later independent plan passes。

- [ ] **Step 1: 写失败矩阵测试**

```python
def test_matrix_verifies_static_and_keeps_deep_layers_blocked():
    self.assert_static_verified_deep_blocked(MATRIX)
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_unity_backend.UnityBackendTest.test_matrix_verifies_static_and_keeps_deep_layers_blocked -v`

Expected: FAIL until evidence exists.

- [ ] **Step 3: 构建并验证设备样本**

Run: `Set-Location D:\文件翻译\apk-work\ui-redesign; python build_workshop_apk.py; adb install -r D:\文件翻译\apk-work\slg-workshop-ui-signed.apk`

- [ ] **Step 4: 运行全量回归**

Run: `python -m unittest test_unity_backend.py test_structured_text_backend.py test_fast_scanner.py test_workshop_patch.py -v`

Expected: PASS.

- [ ] **Step 5: 提交证据**

```powershell
git add docs/qa/unity-backend-matrix.md apk-work/ui-redesign/test_unity_backend.py
git commit --only -m "test: verify unity static localization backend" -- docs/qa/unity-backend-matrix.md apk-work/ui-redesign/test_unity_backend.py
```

## Self-Review Results

- 范围覆盖：Unity 检测、独立本地化 writer、bundle probe、UI 和设备矩阵完整。
- 能力边界：静态文件可写不代表 AssetBundle 或 IL2CPP 可写。
- 依赖边界：AssetsTools.NET host probe 不被描述为 Android app runtime。
- 验证闭环：静态文件复用 structured parser 重读；deep assets 保持导出。
