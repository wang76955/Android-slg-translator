# Android Translation Memory Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变翻译业务流程、翻译结果结构和 APK 数据格式的前提下，降低翻译与补丁生成期间的瞬时内存峰值，并保证任务结束后可回收临时资源。

**Architecture:** 将翻译过程改造成“单文件、单批次、单份驻留”的流水线。WebView 只保留当前批次和必要结果；原生 RPYC 读取使用文件/流边界，避免压缩数据、解压数据、操作表和输出数据同时长期存在；APK 编译产物写入临时文件后再流式合并，不再把所有 `byte[]` 聚合到一个列表。模型和原生缓存采用显式任务结束释放，异常路径与正常路径使用同一清理入口。

**Tech Stack:** Android Java 8 source compatibility, Capacitor PluginCall/JSObject, ML Kit Translator, llama.cpp `LlamaModel`, Java ZIP/Zlib streams, Python `unittest`, Node.js behavior tests, ADB `dumpsys meminfo` and `/proc` sampling.

## Global Constraints

- 保留现有翻译业务流程、缓存键语义、翻译结果字段和 Ren'Py/APK 数据格式。
- 不以 `System.gc()` 作为主修复；优先消除重复 `byte[]`、全量 `List<byte[]>` 和长生命周期模型引用。
- 所有大文件处理必须有明确的单文件、总量、压缩比和中断限制，不能为了降内存而取消 `RenpyResourceLimits`。
- 新增 Java 源码继续使用 `-source 8 -target 8 -encoding UTF-8` 编译。
- WebView 端每次只向原生发送最多 20 条文本；原生每次只返回当前批次结果。
- 任务完成、失败、取消和插件销毁都必须进入同一个资源释放路径。
- 不修改已有用户改动，不执行 `git reset --hard`、`git checkout --` 或批量删除。
- 新增测试从 `D:\文件翻译\apk-work\ui-redesign` 目录运行。
- 目标验收阈值：主进程峰值 PSS `<=300MB`，主进程加 WebView 峰值 PSS `<=420MB`，任务结束 60 秒后主进程 PSS `<=220MB`，连续两次翻译后的残留增量 `<=30MB`。
- 低内存设备验证必须覆盖 Android 13 真机，并确认无 ANR、无 LMK、无错误的“手机空间不足”分类。

---

## Investigation Summary

### Ranked root causes

| Rank | Explanation | Confidence | Evidence and boundary |
|---|---|---|---|
| 1 | 编译阶段把多个生成文件保存为 `List<byte[]>`，最后才统一写入 APK，峰值按所有翻译产物累加。 | High | `TranslationCompiler.java:197-263` 建立 `pendingBytes` 并持续 `add`；`TranslationCompiler.java:1069-1118` 最后才读取列表写 ZIP。该链路可以直接造成大对象同时存活。 |
| 2 | RPYC 处理会同时持有整项压缩数据、解压数组、全量操作表、memo、记录列表和重建输出；资源上限允许单脚本解压到 256MB。 | High | `FastApkScanner.java:140-190` 先读完整 `byte[]`；`RpycTextExtractor.java:107-167` 创建 `pickle`、`ops`、`memo`、records；`RenpyResourceLimits.java:6-12` 允许 256MB 单脚本解压、1GB 总量。 |
| 3 | ML Kit 共享 `Translator` 在普通翻译完成后不关闭；本地 LLM 也有静态加载模型。Native allocator 在回收后仍会保留大块 arena。 | High | `MlKitTranslator.java:293-347` 只在换语言对或删模型时关闭；`MlKitTranslator.java:459-545` 翻译结束没有释放。真机证据曾显示 Native Heap Size 约 207MB、Alloc 约 90MB、Free 约 117MB。 |
| 4 | WebView 和 Capacitor 桥接会复制输入对象、结果 Map、JSON 序列化内容；覆盖率/兼容性记录和缓存索引在任务期间持续增长。 | Medium-High | `patch_local_ui.py:22-35`、`:90-106` 都会创建 `items`、`chunks` 和结果 Map；`patch_workshop_ui.py:1741-1747` 累加完整 `renpyRecords`；`patch_workshop_ui.py:1515-1536` 同时保留 `vo`、`cacheIndex` 和 `_dirty`。 |
| 5 | 扫描缓存最多保留 4 份 `ScanResult`，每份复制完整 APK 条目列表；它不是当前数百 MB 峰值的首要证据，但会延长任务后的驻留时间。 | Medium | `FastApkScanner.java:38-57`、`:1329-1350`。`ScanResult` 未直接保留大字节数组，因此不能把它写成唯一根因。 |
| 6 | UI 把非磁盘错误统一渲染成“手机空间不足”。 | Confirmed classification bug | `patch_workshop_ui.py:440-454` 只识别 `ENOSPC` 后，其余失败路径落到默认空间不足视图；真机 `/data` 仍有约 20GB 可用空间。此问题不等同于内存根因，但会阻断诊断。 |

### Memory lifecycle

```mermaid
flowchart LR
  A[WebView 全量文本] --> B[items / chunks / Map]
  B --> C[Capacitor JSON 桥]
  C --> D[原生 TextItem 列表]
  D --> E[ML Kit 或 Llama 工作区]
  F[APK 条目 byte[]] --> G[RPYC 解压 pickle]
  G --> H[ops / memo / records]
  H --> I[compiled byte[]]
  I --> J[pendingBytes 全量保留]
  J --> K[ZipOutputStream 最终写入]
  E --> L[Native allocator arena]
  B --> M[coverage / cacheIndex / vo]
```

### Known limits

- 现有 `dumpsys procstats` 曾记录主进程 PSS 最大约 450MB、WebView sandbox PSS 最大约 177MB；两个最大值不保证同一时间点同时出现，但足以证明峰值风险真实存在。
- 现有翻译缓存样例约 68KB，不能解释当前数百 MB 峰值；大项目仍会保存完整原文和译文两份，因此需要限制增长。
- 当前证据没有精确到某一个对象的 Java heap dump；实施第一项必须先建立可重复的阶段基线，再确认每一项修复的收益。

## File Map

- Create: `apk-work/ui-redesign/measure_translation_memory.py` — ADB 采样、阶段标记和结果汇总。
- Create: `apk-work/ui-redesign/test_translation_memory.py` — 内存采样解析、JS 会话释放和临时文件存储行为测试。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/PendingApkEntryStore.java` — 文件后备的待写 APK 条目存储。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycSlotSource.java` — RPYC 槽位的临时文件和受限流读取。
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycStreamingExtractor.java` — 流式读取 pickle opcode 并产出 `RenpyTextRecord`。
- Modify: `apk-work/ui-redesign/patch_local_ui.py:18-112` — 单批次前端本地翻译和任务级释放。
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:1503-1539,1703-1751,2348-2377,2419-2421` — 缓存、记录生命周期、RPYC 桥接和错误分类。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/MlKitTranslator.java:293-347,459-545` — Translator 任务级释放。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/LocalLlmEngine.java:386-425,671-687` — Llama 模型任务级释放。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/LocalTranslationSupport.java:111-156,186-208` — 统一释放入口和批次输入限制。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java:38-57,140-228,386-430,1329-1350` — 扫描结果缓存上限和临时引用边界。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java:107-167,899-992` — 切换到流式槽位读取。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java:197-263,1069-1170,1392-1632` — 待写产物磁盘化和流式 ZIP 写入。
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyResourceLimits.java:6-12` — 增加移动端工作集限制，不直接删除现有安全限制。
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py:375-503,910-960` — 注入 `releaseLocalResources` Capacitor 方法。
- Test: `apk-work/ui-redesign/test_engine_performance.py:37-165` — 前端批处理和缓存行为回归。
- Test: `apk-work/ui-redesign/test_fast_scanner.py:865-920,4887-4995,2959-3022` — 原生源码、资源限制和编译器行为回归。

## Tasks

### Task 1: 建立可重复的内存基线

**Files:**
- Create: `apk-work/ui-redesign/measure_translation_memory.py`
- Create: `apk-work/ui-redesign/test_translation_memory.py`
- Test: `apk-work/ui-redesign/test_translation_memory.py`

**Interfaces:**
- Produces: `sample_translation_memory(serial, package, duration_s, output_path) -> dict`。
- Produces: JSON fields `pid`, `timestampMs`, `vmRssKb`, `vmHwmKb`, `pssKb`, `rssKb`, `nativeHeapSizeKb`, `nativeHeapAllocKb`, `nativeHeapFreeKb`, `phase`。
- Consumes: `adb shell pidof`, `adb shell cat /proc/<pid>/status`, `adb shell dumpsys meminfo <package>`。

- [ ] **Step 1: 写失败测试**

```python
def test_parse_proc_status_and_meminfo_extracts_peak_fields():
    status = "VmRSS: 249136 kB\nVmHWM: 444844 kB\n"
    meminfo = "Native Heap Size: 206848 kB\nNative Heap Alloc: 90204 kB\n"
    result = parse_memory_sample(status, meminfo)
    assert result["vmRssKb"] == 249136
    assert result["vmHwmKb"] == 444844
    assert result["nativeHeapFreeKb"] == 116644
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_translation_memory.TranslationMemoryTest.test_parse_proc_status_and_meminfo_extracts_peak_fields -v`

Expected: FAIL because `parse_memory_sample` is not defined.

- [ ] **Step 3: 实现采样器**

实现 `parse_memory_sample` 时按键值读取，不用正则截取整段日志；实现 `sample_translation_memory` 时每 1000ms 采样一次，设备找不到进程立即返回带 `error=process_not_found` 的结果，不能无限等待。命令行参数固定为：

```text
--serial optional --package com.slgtranslator.app --duration 900 --output <json>
```

每次阶段变更由 `--phase` 或环境变量 `SLG_MEMORY_PHASE` 记录；脚本只采样和写 JSON，不触发选择 APK、清数据或重启应用。

- [ ] **Step 4: 运行测试确认绿灯**

Run: `python -m unittest test_translation_memory -v`

Expected: PASS; 解析单元测试覆盖缺失字段、单位转换和进程消失。

- [ ] **Step 5: 建立修复前基线**

Run from `D:\文件翻译\apk-work\ui-redesign`:

```powershell
$env:SLG_MEMORY_PHASE='scan'
python measure_translation_memory.py --serial MZNRYXEQS859O7GU --package com.slgtranslator.app --duration 900 --output qa/memory-baseline-20260810.json
```

Expected: JSON 至少包含扫描、翻译、编译、完成后 60 秒四个阶段；记录主进程、WebView sandbox 和任务结束后的 PSS/RSS，而不是只记录最终一张截图。

### Task 2: 将 WebView 本地翻译改为单批次驻留

**Files:**
- Modify: `apk-work/ui-redesign/patch_local_ui.py:18-35,83-112`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:1558-1568`
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Produces: `window.__slgLocalTranslate({texts, sourceLang, targetLang, onProgress, engine})`，每次只创建一个 20 条 `chunk`。
- Produces: `window.__slgReleaseLocalResources()`，可重复调用且返回 Promise。
- Consumes: `Capacitor.Plugins.FileManager.translateLocal` 和 `releaseLocalResources`。

- [ ] **Step 1: 写失败测试**

```python
def test_local_bridge_does_not_materialize_all_chunks():
    self.assertNotIn("const chunks=[];for(let i=0;i<items.length;i+=20)chunks.push", self.js)
    self.assertIn("const chunk=[]", self.js)

def test_local_translation_finally_releases_native_resources():
    self.assertIn("__slgReleaseLocalResources", self.js)
    self.assertIn("finally", self.js)
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_engine_performance.EnginePerformancePatchTest.test_local_bridge_does_not_materialize_all_chunks -v`

Expected: FAIL because both current bridge implementations still construct the full `chunks` array.

- [ ] **Step 3: 实现单批次循环**

删除全量 `chunks` 数组，保留原始输入 `texts`，按索引构造当前批次：

```javascript
const input = Array.isArray(texts) ? texts : [];
const translations = new Map(), warnings = [], rejected = [];
for (let offset = 0; offset < input.length; offset += 20) {
  const chunk = [];
  for (let i = offset; i < Math.min(offset + 20, input.length); i++) {
    const item = input[i] || {};
    const text = String(item.text || "");
    if (text.trim()) chunk.push({keyPath: String(item.keyPath || ""), text});
  }
  if (!chunk.length) continue;
  const result = await plugin.translateLocal({texts: chunk, sourceLang, targetLang, engine});
  // Merge only the current batch; release `chunk` at the next loop iteration.
}
```

统一 `_CORE_LOCAL_BRIDGE` 与 `localTranslate` 的批处理实现，避免两个实现长期同时维护。翻译调用包在 `try/finally` 中，`finally` 调用 `window.__slgReleaseLocalResources?.()`，并在调用结束后清理当前任务的临时覆盖率数组和被拒绝批次数组；缓存结果仍按现有键写入。

- [ ] **Step 4: 运行行为测试**

Run: `python -m unittest test_engine_performance -v`

Expected: PASS; Node 行为测试断言 55 条输入最多一次向原生发送 20 条、结果数量保持不变、异常时仍调用释放函数。

- [ ] **Step 5: 重建并检查生成 JS**

Run: `python patch_workshop_ui.py` from `D:\文件翻译\apk-work\ui-redesign`。

Expected: `generated/index-CJtfdHOF.js` 包含单批次循环和 `__slgReleaseLocalResources`，不再包含两个全量 `chunks` 构造点。

### Task 3: 释放 ML Kit 与本地 LLM 的任务级资源

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/MlKitTranslator.java:293-347,459-545`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/LocalLlmEngine.java:386-425,671-687`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/LocalTranslationSupport.java:140-156`
- Modify: `apk-work/native-fast-scan/build_fast_scanner.py:402-503,910-960`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Produces: `MlKitTranslator.releaseSharedTranslator()`，同步关闭共享 Translator 并清空语言对字段。
- Produces: `LocalLlmEngine.releaseLoadedModelForIdle()`，调用现有 `releaseLoadedModel()`。
- Produces: `LocalTranslationSupport.releaseLocalResources(Context, PluginCall)`，重复调用安全，返回 `{released:true}`。
- Produces: Capacitor `FileManager.releaseLocalResources(PluginCall)`。

- [ ] **Step 1: 写失败测试**

```python
def test_native_release_bridge_is_declared_once(self):
    source = (FAST_SCAN / "src/com/slgtranslator/app/LocalTranslationSupport.java").read_text("utf-8")
    self.assertIn("releaseLocalResources", source)
    self.assertEqual(source.count("public static void releaseLocalResources"), 1)
    build = (FAST_SCAN / "build_fast_scanner.py").read_text("utf-8")
    self.assertIn("FileManagerPlugin;->releaseLocalResources", build)
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_native_release_bridge_is_declared_once -v`

Expected: FAIL because the release method and dex bridge do not exist.

- [ ] **Step 3: 实现统一释放入口**

在 `MlKitTranslator` 中增加：

```java
static void releaseSharedTranslator() {
    synchronized (TRANSLATOR_LOCK) {
        Translator current = sharedTranslator;
        sharedTranslator = null;
        sharedSource = null;
        sharedTarget = null;
        if (current != null) {
            try { current.close(); } catch (Throwable ignored) { }
        }
    }
}
```

让现有 `resetSharedTranslator()` 委托该方法，避免重复关闭实现。`LocalLlmEngine` 增加包级释放方法，不删除模型文件，只释放已经加载的 native model。`LocalTranslationSupport.releaseLocalResources` 在后台线程顺序调用两个释放方法，异常分别记录后仍 resolve，确保一个引擎释放失败不会阻断另一个引擎。

在 `build_fast_scanner.py` 的 `LOCAL_METHODS` 增加单个 dex 方法，使用 `getContext()` 调用 `LocalTranslationSupport.releaseLocalResources`。不要在每个 20 条批次后释放；只在整个 WebView 会话结束时释放，以避免重复加载模型。

- [ ] **Step 4: 运行 Java/桥接测试**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest -k "release_local_resources" -v`

Expected: PASS; dex 方法计数为 1，释放入口对重复调用不抛异常，模型文件仍存在。

- [ ] **Step 5: 运行编译检查**

Run: `python build_fast_scanner.py` and then the existing fast-scanner build command used by `build_workshop_apk.py`.

Expected: Java 源码和 smali bridge 都能生成；不改变现有 `translateLocal` 参数和返回字段。

### Task 4: 消除 RPYC 读取的全量中间副本

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycSlotSource.java`
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycStreamingExtractor.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java:140-190,1053-1100`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java:107-167,899-992`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyResourceLimits.java:6-12`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:1738-1747,1887-1900`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**
- Produces: `RpycSlotSource.openInflatedSlot(int slotId) -> InputStream`，每次打开都执行槽位范围和解压比检查。
- Produces: `RpycStreamingExtractor.extractRecords(RpycSlotSource source, String sourcePath, boolean onlyOld) -> List<RenpyTextRecord>`。
- Consumes: 现有 `RenpyTextRecord`、`ExtractState`、`LanguageMenuSupport` 的 opcode 语义，不改变记录字段。

- [ ] **Step 1: 写失败测试**

```python
def test_streaming_extractor_handles_large_repetitive_rpyc_under_small_heap(self):
    scanner = (FAST_SCAN / "src/com/slgtranslator/app/FastApkScanner.java").read_text("utf-8")
    extractor = (FAST_SCAN / "src/com/slgtranslator/app/RpycStreamingExtractor.java").read_text("utf-8")
    self.assertIn("RpycStreamingExtractor.extractRecords", scanner)
    self.assertIn("InputStream", extractor)
    self.assertNotIn("List<int[]> ops", extractor)
```

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_streaming_extractor_handles_large_repetitive_rpyc_under_small_heap -v`

Expected: FAIL because no streaming source or extractor exists.

- [ ] **Step 2: 实现文件后备槽位源**

`RpycSlotSource` 把 APK/RPA 单个 RPYC 条目复制到 `context.getCacheDir()/slg-rpyc-work/`，复制缓冲区固定 64KB；达到 `MAX_SINGLE_SCRIPT_COMPRESSED`、`MAX_SINGLE_SCRIPT_INFLATED` 或压缩比限制立即抛出带代码的 `RenpyResourceLimits.LimitException`。实现 `Closeable`，在 `finally` 删除临时文件。任何异常都删除临时文件。

- [ ] **Step 3: 实现流式 opcode 读取**

`RpycStreamingExtractor` 只保留必要的字符串 memo 和 `ExtractState`，按流读取 `PROTO`、unicode、整数、memo、AST 控制 opcode；禁止创建 `List<int[]> ops`。对于未知 opcode 立即 fail closed，错误代码保持现有兼容性分类。将已有 `RpycTextExtractor.extractRecords(byte[],...)` 保留为测试和小数据兼容入口，但当输入超过 8MB 时转发到文件后备实现。

- [ ] **Step 4: 去除 RPYC 返回中的重复 content**

原生 `readRenpyTexts` 对 `rpyc/rpymc` 只返回 `renpyRecords`、覆盖率和报告，不再同时生成完整 `StringBuilder content`。WebView 端在当前文件任务内由 `renpyRecords` 直接生成现有 `RPYC_STRING\t` 协议，解析完成后立即将临时协议变量置为 `null`。非 RPYC 文本文件维持现有 `content` 字段。

- [ ] **Step 5: 调整移动端工作集限制并测试**

保留现有安全限制，同时新增独立的工作集限制：单文件解压软上限 96MB、扫描总解压软上限 384MB；超过软上限返回 `renpy_memory_budget_exceeded`，而不是伪装成空间不足。硬限制 `MAX_SINGLE_SCRIPT_INFLATED=256MB` 和 `MAX_TOTAL_SCRIPT_INFLATED=1GB` 仍保留为防护上限，直到真机兼容性矩阵完成后再评估是否调整。

Run: `python -m unittest test_fast_scanner -k "streaming_extractor or resource_limits or read_renpy" -v`

Expected: PASS; 大型重复数据在 `-Xmx96m` 下完成，小于限制的现有 Ren'Py fixtures 输出完全一致，超限返回稳定错误码。

### Task 5: 将 APK 编译待写产物改为磁盘后备

**Files:**
- Create: `apk-work/native-fast-scan/src/com/slgtranslator/app/PendingApkEntryStore.java`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java:197-263,1069-1170,1392-1632`
- Test: `apk-work/ui-redesign/test_fast_scanner.py:2959-3022`

**Interfaces:**
- Produces: `PendingApkEntryStore.add(String apkName, String runtimeName, byte[] payload) -> int`。
- Produces: `PendingApkEntryStore.openPayload(int index) -> InputStream`。
- Produces: `PendingApkEntryStore.replace(int index, byte[] payload)` and `close()`。
- Consumes: existing `pending` path pairs and `rewriteApkWithEntries` semantics.

- [ ] **Step 1: 写失败测试**

```java
PendingApkEntryStore store = new PendingApkEntryStore(tempDir);
for (int i = 0; i < 24; i++) {
    store.add("generated/" + i, "runtime/" + i, new byte[8 * 1024 * 1024]);
}
require(store.size() == 24, "all entries must be indexed");
require(store.inMemoryPayloadBytes() == 0, "payloads must be file-backed after add");
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_pending_entry_store_is_file_backed -v`

Expected: FAIL because `PendingApkEntryStore` does not exist.

- [ ] **Step 3: 实现磁盘后备存储**

每次 `add` 将当前 `byte[]` 写入任务临时目录并只保留路径、APK 名、runtime 名和长度；`replace` 先写新文件，写成功后再删除旧文件。`close()` 删除所有 payload 和目录。禁止把多个 payload 重新读成一个 `List<byte[]>`。

- [ ] **Step 4: 改造编译器写入路径**

将 `List<byte[]> pendingBytes` 替换为 `PendingApkEntryStore`。`compileRpyc`、字体复制、style 重写、always-on dialogue 重写完成后立即 `store.add`；`rewriteApkWithEntries` 对每个条目调用 `openPayload` 并以 64KB 缓冲区写入 `ZipOutputStream`。`compileTranslationsIntoApk` 最外层 `finally` 必须关闭 store，即使字体预检、验证或 APK 替换失败也不能留下临时文件。

- [ ] **Step 5: 验证产物和峰值**

Run: `python -m unittest test_fast_scanner -k "pending_entry_store or translation_compiler" -v`

Expected: PASS; 现有编译器 golden、协议 2、2624 条文本和 dialogue patcher 测试全部通过；24 个 8MB 产物在 `java -Xmx128m` 下完成，生成 APK 的条目内容和数量与改造前一致。

### Task 6: 限制扫描结果和 WebView 诊断数据的驻留

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java:38-57,386-430,1329-1350`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:1741-1747,2325,2332-2335,2419-2421`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Produces: `FastApkScanner.clearCache()`。
- Produces: `FastApkScanner.cacheStats() -> {entries, cachedApkEntryCount}`，只用于诊断，不改变业务响应。
- Produces: `window.__slgTrimTranslationDiagnostics()`，清理当前任务已消费的 records、候选译文和兼容性累积记录。

- [ ] **Step 1: 写失败测试**

```python
def test_scan_cache_skips_oversized_metadata_results(self):
    source = SCANNER.read_text("utf-8")
    self.assertIn("MAX_CACHED_APK_ENTRIES", source)
    self.assertIn("clearCache", source)

def test_translation_diagnostics_have_explicit_trim_hook(self):
    self.assertIn("__slgTrimTranslationDiagnostics", self.js)
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_scan_cache_skips_oversized_metadata_results -v`

Expected: FAIL because the cache currently has only a count limit and no entry-weight limit or public clear method.

- [ ] **Step 3: 实现原生缓存边界**

将 `MAX_CACHE_ENTRIES` 调整为 2，新增 `MAX_CACHED_APK_ENTRIES=50_000`；当 `ScanResult.entries.size()` 超过该值时返回结果给调用方但不放入 `CACHE`。`clearCache()` 在新 APK 选择和任务结束时由桥接调用；不清理模型文件，不删除翻译缓存。

- [ ] **Step 4: 实现 WebView 诊断裁剪**

保留覆盖率面板所需的计数和前 20 个缺失文件，任务进入 `patching` 前释放已消费的完整 `renpyRecords`、dialogue 记录和候选列表；`__slgValidatorApprovedTranslations` 只保留现有缓存未命中的当前任务结果。`__slgTrimTranslationDiagnostics()` 必须可重复调用并在 `Ce` 新任务开始时重置。

- [ ] **Step 5: 运行行为测试**

Run: `python -m unittest test_engine_performance test_fast_scanner -k "cache or diagnostics or coverage" -v`

Expected: PASS; 覆盖率数字、阻断判断、翻译结果和缓存键不变，任务完成后的 JS 诊断对象不再保留整批记录。

### Task 7: 修正空间、内存和字体预检错误分类

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:440-454`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyFontSupport.java:137-179`
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java:270-282`
- Test: `apk-work/ui-redesign/test_workshop_patch.py`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

**Interfaces:**
- Produces: `classifyWorkshopFailure(message) -> "scan" | "network" | "space" | "memory" | "font" | "compile" | "unknown"`。
- Produces: UI state payload `reason` and `raw` 保持现有字段，新增 `code` 仅用于诊断。

- [ ] **Step 1: 写失败测试**

```python
def test_font_budget_error_is_not_rendered_as_phone_space_error(self):
    js = self.js
    self.assertIn("font_preflight_total_size_limit", js)
    self.assertIn('reason:"font"', js)
    self.assertNotIn('reason:"space"', js[js.index("font_preflight_total_size_limit"):])
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m unittest test_workshop_patch -k "failure or space or font" -v`

Expected: FAIL because the default error renderer at `patch_workshop_ui.py:454` is the space error.

- [ ] **Step 3: 实现稳定分类**

只将 `ENOSPC`, `No space left`, `ENOSPC:` 归为 `space`；将 `font_preflight_`、`renpy_font_` 归为 `font`；将 `OutOfMemoryError`, `memory_budget`, `transaction_memory` 归为 `memory`；将 `translation_validation`, `compile failure`, `renpy_limit_` 归为 `compile` 或 `memory`，按更具体代码优先。未知错误渲染“处理失败”，不得显示“手机空间不足”。

- [ ] **Step 4: 保持原生错误码**

`TranslationCompiler` 和 `RenpyFontSupport` 返回的原始错误代码写入 payload `code`，UI 只显示用户可理解的标题和处理建议，详情面板保留完整代码。设备有充足空间时，`font_preflight_total_size_limit` 必须显示字体资源过大，而不是磁盘不足。

- [ ] **Step 5: 运行回归测试**

Run: `python -m unittest test_workshop_patch test_fast_scanner -k "failure or font or space or resource" -v`

Expected: PASS; 磁盘不足、字体预算、内存预算、网络失败和未知错误各自进入正确状态。

### Task 8: 构建、真机压力和完成验收

**Files:**
- Modify: `docs/qa/renpy-release-checklist.md`
- Create: `docs/qa/translation-memory-acceptance-20260810.md`
- Test: `apk-work/ui-redesign/test_translation_memory.py`

**Interfaces:**
- Consumes: Tasks 1-7 的生成 APK、采样器和测试命令。
- Produces: 基线 JSON、修复后 JSON、阶段对比表和真机验收记录。

- [ ] **Step 1: 运行 Python 和 Node 测试**

Run from `D:\文件翻译\apk-work\ui-redesign`:

```powershell
python -m unittest test_engine_performance test_workshop_patch test_fast_scanner test_translation_memory -v
```

Expected: 全部 PASS；若失败，先记录失败阶段和错误码，再进入对应任务修复，不允许用修改断言的方式消除失败。

- [ ] **Step 2: 生成 fast scanner 和 APK**

Run:

```powershell
python ..\native-fast-scan\build_fast_scanner.py
python build_workshop_apk.py
```

Expected: 生成的 `generated/index-CJtfdHOF.js`、native dex 和签名 APK 均包含本计划的释放入口、流式读取和磁盘后备写入路径。

- [ ] **Step 3: 执行固定真机流程**

使用设备 `MZNRYXEQS859O7GU`，不清理应用数据，依次执行：选择同一 APK、扫描、ML Kit 翻译、生成补丁、返回首页、再次翻译同一 APK。每个阶段让 `measure_translation_memory.py` 写入阶段标记。

- [ ] **Step 4: 验证内存阈值**

验收规则：

```text
主进程峰值 PSS <= 300MB
主进程 + WebView 峰值 PSS <= 420MB
完成后 60 秒主进程 PSS <= 220MB
连续两次翻译后的残留增量 <= 30MB
Native Heap Free 不得持续随任务次数线性增长
```

如果只满足最终 PSS 而峰值仍超标，不得标记完成；必须按阶段最大值判断。

- [ ] **Step 5: 验证功能和兼容性**

检查：原文/译文数量、占位符校验、覆盖率阻断、字体预检、协议 2/现代 RPYC、always-on/selectable 两种模式、APK 签名、生成文件数量和安装流程。每项保留命令输出或截图路径，不能以“看起来正常”作为证据。

- [ ] **Step 6: 写验收记录和提交**

将基线与修复后数据写入 `docs/qa/translation-memory-acceptance-20260810.md`，记录每个阈值的实测值、设备信息、APK SHA-256、失败重试次数和剩余风险。完成后按任务拆分提交，建议提交信息：

```text
test: add translation memory baseline harness
fix: bound local translation batch lifetime
fix: release native translation engines after task
fix: stream RPYC extraction under memory budget
fix: spool APK compiler payloads to disk
fix: trim translation diagnostics and classify failures
test: record device translation memory acceptance
```

## Self-Review Checklist

- [ ] 已覆盖 WebView 输入副本、Capacitor JSON 桥、ML Kit/Llama native 工作区、RPYC 解压、扫描结果缓存和编译器待写产物。
- [ ] 已区分已确认事实、证据推断和当前未知项；没有把 procstats 的不同时间最大值当作同一瞬时值。
- [ ] 已包含正常结束、失败、取消和插件销毁四条释放路径。
- [ ] 已包含真实测试命令、真机压力步骤和明确数值阈值。
- [ ] 已包含“手机空间不足”错误分类修复，避免继续遮蔽内存/字体问题。
- [ ] 已避免把 `System.gc()`、降低动画或删除安全限制作为主要内存方案。
- [ ] 计划中不含未决标记或模糊措辞。
