# High-Risk Engine And Media Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 DEX/smali、native/IL2CPP、运行时 hook 和图片 OCR/纹理重建建立隔离、可复现的可行性评估，不在证据不足时向普通用户暴露 writer。

**Architecture:** 新增统一 `HighRiskBackendReport` 和 host-side probe 工具，只读取合法 fixture、输出脱敏统计和产物差异，不修改主应用 writer 路由。每类后端都有固定风险门禁、资源预算和停止条件；评估结论只能是 `CANDIDATE_FOR_SEPARATE_PLAN`、`DIAGNOSTIC_ONLY` 或 `REJECTED`，不能直接变成 `PATCHABLE_VERIFIED`。

**Tech Stack:** Python 3、Java 8 diagnostics、apkanalyzer/baksmali host tools、readelf/objdump、Unity metadata diagnostics、OCR bitmap fixtures、Python `unittest`、ADB isolated test device。

## Global Constraints

- 本计划不实现任何生产 writer，不修改 APK、DEX、native library、运行时证书校验或游戏网络流量。
- 所有 fixture 必须有来源合法性、SHA-256、用途和删除策略。
- 不上传 APK、剧情文本、native binary、OCR 图片或 API Key。
- 探针默认离线、只读、临时目录隔离，超时后终止子进程并删除未验证输出。
- 任何反作弊、DRM、签名自检、完整性校验或法律边界不明确的样本立即 `REJECTED`。
- DEX 动态字符串、native 解密、远程内容和 OCR 结果不计入当前结构化翻译覆盖率。
- 运行时 hook 不进入发布构建，不绕过 TLS pinning、登录、付费或访问控制。
- OCR 必须保留原图备份、透明度、尺寸、纹理格式和排版边界；无字体许可时不得分发生成图。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/HighRiskBackendReport.java`。
- Create: `apk-work/ui-redesign/probe_dex_backend.py`。
- Create: `apk-work/ui-redesign/probe_native_il2cpp.py`。
- Create: `apk-work/ui-redesign/probe_runtime_hook.py`。
- Create: `apk-work/ui-redesign/probe_ocr_texture.py`。
- Create: `apk-work/ui-redesign/test_high_risk_backends.py`。
- Create: `docs/qa/high-risk-backend-decision-matrix.md`。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java` — 只追加脱敏诊断字段。

## Tasks

### Task 1: 建立统一风险报告和停止条件

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/HighRiskBackendReport.java`
- Create: `apk-work/ui-redesign/test_high_risk_backends.py`
- Create: `docs/qa/high-risk-backend-decision-matrix.md`

**Interfaces:**
- Produces enum: `CANDIDATE_FOR_SEPARATE_PLAN`、`DIAGNOSTIC_ONLY`、`REJECTED`。
- Fields: `backendId/evidenceCodes/riskCodes/dependencyStatus/sampleCount/peakMemoryMb/elapsedMs/decision`。

- [ ] **Step 1: 写失败测试**

```java
HighRiskBackendReport report = HighRiskBackendReport.evaluate(
        "dex", evidence, Arrays.asList("integrity_check_detected"), 2, 100, 5000);
require(report.decision == Decision.REJECTED, "integrity checks must reject");
require(!report.toSanitizedJson().contains("sourceText"), "no content leakage");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_high_risk_backends.HighRiskBackendTest.test_report_rejects_integrity_and_sanitizes_output -v`

Expected: FAIL because report type is absent.

- [ ] **Step 3: 实现不可变报告**

`CANDIDATE_FOR_SEPARATE_PLAN` 至少需要 2 个合法样本、可重读产物、无 integrity/DRM 风险、依赖可分发和资源预算通过；本类不包含 `canWritePatch`。

- [ ] **Step 4: 运行报告测试**

Run: `python -m unittest test_high_risk_backends -v`

Expected: PASS.

- [ ] **Step 5: 提交风险模型**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/HighRiskBackendReport.java apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
git commit --only -m "test: define high risk backend decisions" -- apk-work/native-fast-scan/src/com/slgtranslator/app/HighRiskBackendReport.java apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
```

### Task 2: 评估 DEX/smali 字符串后端

**Files:**
- Create: `apk-work/ui-redesign/probe_dex_backend.py`
- Modify: `apk-work/ui-redesign/test_high_risk_backends.py`
- Modify: `docs/qa/high-risk-backend-decision-matrix.md`

**Interfaces:**
- Produces report: `literalCount/resourceReferenceCount/dynamicCount/methodReferenceDelta/registerDelta/reassembleOk/verifyOk`。

- [ ] **Step 1: 写失败测试**

```python
def test_dex_probe_rejects_dynamic_or_register_changing_rewrites():
    report = evaluate_dex({"dynamicCount": 1, "registerDelta": 0, "verifyOk": True})
    self.assertEqual(report["decision"], "DIAGNOSTIC_ONLY")
    report = evaluate_dex({"dynamicCount": 0, "registerDelta": 1, "verifyOk": True})
    self.assertEqual(report["decision"], "REJECTED")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_high_risk_backends.HighRiskBackendTest.test_dex_probe_rejects_dynamic_or_register_changing_rewrites -v`

Expected: FAIL because DEX evaluator is absent.

- [ ] **Step 3: 实现只读 host probe**

探针枚举 `const-string`、资源引用、拼接/解密调用和 integrity API；可选实验输出只在临时目录重组并用 verifier 检查，禁止写回用户 APK。任何 method/register/control-flow 变化直接 rejected。

- [ ] **Step 4: 运行 DEX 测试**

Run: `python -m unittest test_high_risk_backends -v`

Expected: PASS; 无 host tool 时报告 dependency unavailable。

- [ ] **Step 5: 提交 DEX 探针**

```powershell
git add apk-work/ui-redesign/probe_dex_backend.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
git commit --only -m "test: evaluate dex translation backend" -- apk-work/ui-redesign/probe_dex_backend.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
```

### Task 3: 评估 native 与 IL2CPP

**Files:**
- Create: `apk-work/ui-redesign/probe_native_il2cpp.py`
- Modify: `apk-work/ui-redesign/test_high_risk_backends.py`、`docs/qa/high-risk-backend-decision-matrix.md`

**Interfaces:**
- Produces: `abi/elfClass/relro/pie/stripped/metadataVersion/stringLiteralCount/relocationRisk/decision`。

- [ ] **Step 1: 写失败测试**

```python
def test_native_probe_never_promotes_in_place_string_replacement():
    result = evaluate_native({"stringLiteralCount": 100, "relocationRisk": "high"})
    self.assertNotEqual(result["decision"], "CANDIDATE_FOR_SEPARATE_PLAN")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_high_risk_backends.HighRiskBackendTest.test_native_probe_never_promotes_in_place_string_replacement -v`

Expected: FAIL because native evaluator is absent.

- [ ] **Step 3: 实现 ELF/metadata 诊断**

只运行 `readelf`/`objdump`/metadata parser，记录 ABI、section、relocation、strip 和 IL2CPP metadata 版本。探针不 patch `.rodata`，不注入 library，不执行目标 native code。

- [ ] **Step 4: 运行 native 测试**

Run: `python -m unittest test_high_risk_backends -v`

Expected: PASS; 当前结论默认为 diagnostic-only 或 rejected。

- [ ] **Step 5: 提交 native 探针**

```powershell
git add apk-work/ui-redesign/probe_native_il2cpp.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
git commit --only -m "test: evaluate native and il2cpp backends" -- apk-work/ui-redesign/probe_native_il2cpp.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
```

### Task 4: 评估运行时 hook 的稳定性与安全边界

**Files:**
- Create: `apk-work/ui-redesign/probe_runtime_hook.py`
- Modify: `apk-work/ui-redesign/test_high_risk_backends.py`、`docs/qa/high-risk-backend-decision-matrix.md`

**Interfaces:**
- Produces: `menu/dialogue/name/interpolation/saveLoad/rollback/crash/anr/antiTamper` coverage report。

- [ ] **Step 1: 写失败测试**

```python
def test_hook_candidate_requires_all_behavior_classes_and_no_antitamper():
    result = evaluate_hook({"menu": True, "dialogue": True, "saveLoad": False,
                            "rollback": True, "antiTamper": False})
    self.assertEqual(result["decision"], "DIAGNOSTIC_ONLY")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_high_risk_backends.HighRiskBackendTest.test_hook_candidate_requires_all_behavior_classes_and_no_antitamper -v`

Expected: FAIL because hook evaluator is absent.

- [ ] **Step 3: 实现测试编排器**

编排器只面向自有测试 APK/开发者构建，记录行为覆盖和崩溃；检测 anti-tamper、TLS、登录或付费路径即 rejected。探针不进入 release APK。

- [ ] **Step 4: 运行 hook 测试**

Run: `python -m unittest test_high_risk_backends -v`

Expected: PASS.

- [ ] **Step 5: 提交 hook 探针**

```powershell
git add apk-work/ui-redesign/probe_runtime_hook.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
git commit --only -m "test: evaluate runtime translation hooks" -- apk-work/ui-redesign/probe_runtime_hook.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
```

### Task 5: 评估 OCR、重排和纹理重建

**Files:**
- Create: `apk-work/ui-redesign/probe_ocr_texture.py`
- Modify: `apk-work/ui-redesign/test_high_risk_backends.py`、`docs/qa/high-risk-backend-decision-matrix.md`

**Interfaces:**
- Produces: `ocrConfidence/layoutOverflow/alphaPreserved/dimensionsPreserved/formatPreserved/fontLicense/visualDiff`。

- [ ] **Step 1: 写失败测试**

```python
def test_ocr_candidate_requires_visual_and_format_invariants():
    result = evaluate_ocr({"alphaPreserved": True, "dimensionsPreserved": True,
                           "formatPreserved": False, "fontLicense": "allowed"})
    self.assertEqual(result["decision"], "REJECTED")
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_high_risk_backends.HighRiskBackendTest.test_ocr_candidate_requires_visual_and_format_invariants -v`

Expected: FAIL because OCR evaluator is absent.

- [ ] **Step 3: 实现离线 fixture 探针**

探针只处理测试图片，保存 OCR boxes、重排结果和像素差；尺寸、alpha、纹理格式或字体许可任一失败即 rejected。OCR 文本不进入结构化覆盖率。

- [ ] **Step 4: 运行 OCR 测试**

Run: `python -m unittest test_high_risk_backends -v`

Expected: PASS.

- [ ] **Step 5: 提交 OCR 探针**

```powershell
git add apk-work/ui-redesign/probe_ocr_texture.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
git commit --only -m "test: evaluate ocr texture pipeline" -- apk-work/ui-redesign/probe_ocr_texture.py apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
```

### Task 6: 汇总继续/停止决策并保持产品门禁

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Modify: `apk-work/ui-redesign/test_high_risk_backends.py`
- Modify: `docs/qa/high-risk-backend-decision-matrix.md`

**Interfaces:**
- Scanner fields: `highRiskDiagnostics` sanitized metadata only。
- Workflow remains `EXTRACTABLE_ONLY` or `TRANSLATABLE_NO_PATCH`。

- [ ] **Step 1: 写失败门禁测试**

```java
JSObject response = scan(highRiskFixture);
require(!response.getCapabilities().canWritePatch, "evaluation cannot enable writer");
require(!response.toString().contains("sourceText"), "diagnostics sanitized");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_high_risk_backends.HighRiskBackendTest.test_evaluation_reports_never_enable_writer -v`

Expected: FAIL because scanner diagnostics are absent.

- [ ] **Step 3: 追加只读诊断字段**

只返回 backend ID、计数区间、风险码和 decision；不返回完整路径、字符串、图片或 binary excerpt。任何 candidate 必须另写独立设计和实施计划后才能改变 capability。

- [ ] **Step 4: 运行全部评估测试**

Run: `python -m unittest test_high_risk_backends.py test_fast_scanner.py test_workshop_patch.py -v`

Expected: PASS; 所有高风险 fixture 的 `canWritePatch=false`。

- [ ] **Step 5: 提交决策矩阵**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
git commit --only -m "test: publish high risk backend decisions" -- apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_high_risk_backends.py docs/qa/high-risk-backend-decision-matrix.md
```

## Self-Review Results

- 范围覆盖：DEX、native/IL2CPP、hook、OCR 和统一决策模型均有独立任务。
- 产品边界：本计划没有任何路径可以把评估结果直接变成 writer 能力。
- 隐私边界：报告只含脱敏计数和风险码，不含内容或 binary excerpt。
- 后续边界：只有 `CANDIDATE_FOR_SEPARATE_PLAN` 才允许创建新的设计与实施计划。
