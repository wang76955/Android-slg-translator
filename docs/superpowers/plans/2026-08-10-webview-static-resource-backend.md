# WebView Static Resource Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持 APK 内静态 WebView HTML、本地 locale JSON 和明确文本属性的翻译写回，同时把远程、登录后、加密和运行时 DOM 内容明确标记为不可补丁。

**Architecture:** `WebViewAssetAdapter` 先构建本地入口和引用图，只处理 APK 内可达的 `file:///android_asset`/相对路径资源；JSON 复用 structured-text backend，HTML 使用固定 jsoup `1.23.1` 候选经 D8/Android 门禁后解析。`WebViewAssetWriter` 只替换文本节点和白名单属性，写后重新解析并验证 DOM 定位、URL、script/style 和资源引用未变化。

**Tech Stack:** Java 8、jsoup 1.23.1 候选、structured-text backend、HTML5 DOM、ZIP streams、Python `unittest`、D8、ADB。

## Global Constraints

- 前置条件：阶段 0 和 structured-text backend 已完成。
- 只处理 APK 内静态资源；HTTP(S)、WebSocket、登录态、服务端模板和运行时下载返回 `remote_content_not_patchable`。
- 不注入代理、不绕过证书校验、不修改 CSP、不执行 JavaScript。
- 不翻译 `script`、`style`、URL、id、class、data protocol、事件处理器和不可见控制节点。
- 首版白名单属性仅 `title`、`alt`、`placeholder`、`aria-label`。
- DOM 路径必须稳定且写后可重新定位；解析器修复了畸形 HTML 时必须记录结构差异并阻断 writer。
- 依赖增量体积 `<=3 MiB`，Android 端峰值 PSS 增量 `<=80 MiB`。

---

## File Map

- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetAdapter.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewHtmlCodec.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetWriter.java`、`apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewDependencyProbe.java`。
- Create: `apk-work/ui-redesign/test_webview_backend.py`。
- Create: `docs/qa/webview-static-backend-matrix.md`。
- Modify: `apk-work/native-fast-scan/fetch_third_party.py`、`apk-work/native-fast-scan/build_fast_scanner.py`、`apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`、`apk-work/ui-redesign/patch_workshop_ui.py`。

## Tasks

### Task 1: 验证 jsoup Android 运行门禁

**Files:**
- Modify: `apk-work/native-fast-scan/fetch_third_party.py`、`apk-work/native-fast-scan/build_fast_scanner.py`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewDependencyProbe.java`
- Test: `apk-work/ui-redesign/test_webview_backend.py`

**Interfaces:**
- Produces: `probe(String html) -> ProbeResult(parseOk/serializeOk/reparseOk/structureChanged)`。

- [ ] **Step 1: 写失败测试**

```python
def test_jsoup_is_pinned_and_probe_rejects_structure_repair():
    self.assert_pinned("jsoup", "1.23.1")
    self.assertIn("structureChanged", PROBE.read_text("utf-8"))
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_webview_backend.WebViewBackendTest.test_jsoup_is_pinned_and_probe_rejects_structure_repair -v`

Expected: FAIL because dependency and probe are absent.

- [ ] **Step 3: 添加哈希、许可证、D8 和真机 parse smoke**

probe 对 XHTML、普通 HTML5、畸形 HTML 分别记录 DOM signature；序列化前后 node/tag/attribute 引用变化即 `writer_dependency_unavailable`。

- [ ] **Step 4: 运行门禁测试**

Run: `Set-Location D:\文件翻译\apk-work\native-fast-scan; python fetch_third_party.py; python build_fast_scanner.py; Set-Location ..\ui-redesign; python -m unittest test_webview_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交依赖门禁**

```powershell
git add apk-work/native-fast-scan/fetch_third_party.py apk-work/native-fast-scan/build_fast_scanner.py apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewDependencyProbe.java apk-work/ui-redesign/test_webview_backend.py
git commit --only -m "test: gate webview html parser" -- apk-work/native-fast-scan/fetch_third_party.py apk-work/native-fast-scan/build_fast_scanner.py apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewDependencyProbe.java apk-work/ui-redesign/test_webview_backend.py
```

### Task 2: 检测本地 WebView 资源图和远程边界

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetAdapter.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`
- Test: `apk-work/ui-redesign/test_webview_backend.py`

**Interfaces:**
- Produces: `detect(InstalledApkSet) -> WebViewDetectionResult`。
- Fields: `localEntries/remoteOrigins/dynamicSignals/confidence/workflow`。

- [ ] **Step 1: 写失败测试**

```java
WebViewDetectionResult local = adapter.detect(apk("assets/www/index.html", "assets/www/lang/en.json"));
require(local.workflow.equals("PATCHABLE_VERIFIED"), "local static site");
WebViewDetectionResult remote = adapter.detect(apkWithUrl("https://api.example/story"));
require(remote.workflow.equals("TRANSLATABLE_NO_PATCH"), "remote content");
require(remote.reasonCodes.contains("remote_content_not_patchable"), "reason");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_webview_backend.WebViewBackendTest.test_detection_separates_local_and_remote_content -v`

Expected: FAIL because adapter is absent.

- [ ] **Step 3: 实现受限引用图**

解析 HTML 的相对 `src/href` 和 manifest activity/WebView 证据；只允许规范化后仍位于同一 owner 的 assets 路径。`../` 越界、网络 URL、动态 fetch/XHR 字符串只记录诊断，不进入 writer。

- [ ] **Step 4: 运行检测测试**

Run: `python -m unittest test_webview_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交检测**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_webview_backend.py
git commit --only -m "feat: detect static webview resources" -- apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetAdapter.java apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java apk-work/ui-redesign/test_webview_backend.py
```

### Task 3: 提取和重写 HTML 文本节点

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewHtmlCodec.java`
- Test: `apk-work/ui-redesign/test_webview_backend.py`

**Interfaces:**
- Produces DOM record keys: CSS-like structural path plus node/attribute index。

- [ ] **Step 1: 写失败测试**

```java
List<StructuredTextRecord> records = codec.extract(owner, path, html);
require(texts(records).contains("Start game"), "visible text");
require(!texts(records).contains("https://api.example"), "URL excluded");
require(!texts(records).contains("debug text"), "script excluded");
byte[] out = codec.rewrite(html, approved);
require(codec.verify(html, out, approved).valid, "reparse");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_webview_backend.WebViewBackendTest.test_html_codec_translates_only_visible_whitelist_nodes -v`

Expected: FAIL because codec is absent.

- [ ] **Step 3: 实现 DOM codec**

忽略空白节点和不可见容器；属性只读白名单。验证比较 script/style 字节摘要、URL 集合、element signature、record 数量和译文。

- [ ] **Step 4: 运行 codec 测试**

Run: `python -m unittest test_webview_backend -v`

Expected: PASS.

- [ ] **Step 5: 提交 codec**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewHtmlCodec.java apk-work/ui-redesign/test_webview_backend.py
git commit --only -m "feat: add static webview html codec" -- apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewHtmlCodec.java apk-work/ui-redesign/test_webview_backend.py
```

### Task 4: 接入 writer、UI 和产物重读

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetWriter.java`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`、`apk-work/ui-redesign/test_workshop_patch.py`
- Test: `apk-work/ui-redesign/test_webview_backend.py`

**Interfaces:**
- Adapter ID: `webview-static`。
- Produces: `write(sourceSet, translations, outputDir) -> PatchArtifact`。

- [ ] **Step 1: 写失败流程测试**

```javascript
check(scan.adapterId===`webview-static`,`adapter`);
check(remote.workflow===`TRANSLATABLE_NO_PATCH`,`remote export only`);
check(local.workflow===`PATCHABLE_VERIFIED`,`local writer`);
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_webview_backend test_workshop_patch.WorkshopPatchContractTest.test_webview_static_and_remote_workflows -v`

Expected: FAIL because writer routing is absent.

- [ ] **Step 3: 实现 writer 和 UI 分流**

HTML 与 locale JSON 分别调用对应 codec；产物由全新 adapter 重读。远程内容显示“可导出包内静态文本，远程剧情不可补丁”，不显示安装操作。

- [ ] **Step 4: 运行集成测试**

Run: `python -m unittest test_webview_backend.py test_fast_scanner.py test_workshop_patch.py -v`

Expected: PASS.

- [ ] **Step 5: 提交集成**

```powershell
git add apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetWriter.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_webview_backend.py
git commit --only -m "feat: integrate static webview backend" -- apk-work/native-fast-scan/src/com/slgtranslator/app/WebViewAssetWriter.java apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py apk-work/ui-redesign/test_webview_backend.py
```

### Task 5: 真机静态 WebView 验收

**Files:**
- Create: `docs/qa/webview-static-backend-matrix.md`
- Test: `apk-work/ui-redesign/test_webview_backend.py`

**Interfaces:**
- Verifies one local static sample and one remote-content blocking sample。

- [ ] **Step 1: 写失败矩阵测试**

```python
def test_matrix_requires_local_launch_text_and_remote_blocking_evidence():
    self.assert_local_verified_and_remote_blocked(MATRIX)
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_webview_backend.WebViewBackendTest.test_matrix_requires_local_launch_text_and_remote_blocking_evidence -v`

Expected: FAIL until evidence exists.

- [ ] **Step 3: 构建并执行设备样本**

Run: `Set-Location D:\文件翻译\apk-work\ui-redesign; python build_workshop_apk.py; adb install -r D:\文件翻译\apk-work\slg-workshop-ui-signed.apk`

- [ ] **Step 4: 运行全量回归**

Run: `python -m unittest test_webview_backend.py test_structured_text_backend.py test_fast_scanner.py test_workshop_patch.py -v`

Expected: PASS.

- [ ] **Step 5: 提交证据**

```powershell
git add docs/qa/webview-static-backend-matrix.md apk-work/ui-redesign/test_webview_backend.py
git commit --only -m "test: verify static webview backend" -- docs/qa/webview-static-backend-matrix.md apk-work/ui-redesign/test_webview_backend.py
```

## Self-Review Results

- 范围覆盖：依赖、检测、DOM codec、writer/UI 和真机矩阵完整。
- 网络边界：远程内容始终导出/诊断，不使用代理或证书绕过。
- DOM 边界：script/style/URL/ID/协议字段不翻译，结构修复会阻断 writer。
- 验证闭环：HTML 和 JSON 均写后重解析。
