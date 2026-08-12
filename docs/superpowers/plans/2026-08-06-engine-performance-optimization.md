# 翻译引擎性能优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变游戏 APK 功能语义的前提下，降低翻译引擎的等待时间和主线程阻塞，让大批量翻译更快完成。

**Architecture:** 本轮先落地 WebView 协调器的低风险高收益优化：全局 API 并发池、真正的文件级并发、增量缓存落盘、输出目录 URI 缓存。高风险的原生 APK 合并重写/镜像跳过留到真机回归阶段。

**Tech Stack:** Python 补丁脚本（`patch_workshop_ui.py`）、minified React JS、Node 行为探针、unittest、APK 重建脚本。

## Global Constraints

- 保持 `patch_workshop_ui.py` 的现有补丁锚点风格，不做整体重写。
- 不改变翻译文本内容、缓存键格式、API 参数语义。
- 新增测试必须从 `apk-work/ui-redesign` 目录运行。
- 修改后必须重新生成 `generated/index-CJtfdHOF.js`。
- 全量翻译时最多允许 6 个文件 worker 和 6 个全局 API 请求并发，避免撞限流。

---

### Task 1: 全局 API 并发池与文件并发修复

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（`patch_translation_network`、`patch_speed_tuning`）
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Consumes: `patch_assets()` 生成的 patched JS。
- Produces: `globalThis.__slgApiSemaphore.run(fn)`、文件控制器调用并发 `6`、编译前最终 `await wo(!0)`。

- [ ] **Step 1: 写失败测试**

```python
def test_global_api_semaphore_is_injected_and_caps_concurrency(self):
    ...
```

- [ ] **Step 2: 运行测试确认红灯**
- [ ] **Step 3: 注入 semaphore helper 并包裹顶层 `Bo` 调用**
- [ ] **Step 4: 把 `return N},2);` 改成 `return N},6);if(!N)await wo(!0);...`**
- [ ] **Step 5: 运行测试确认绿灯**

### Task 2: 增量缓存落盘

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（`patch_translation_cache`、`patch_translation_memory`、`patch_cache_memory`）
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Consumes: `_o`, `vo`, `cacheIndex`, `bo`, `wo(_force)`。
- Produces: `_dirty` 增量表、`Co()` 增量合并、`wo()` 只序列化 dirty 条目与文件级缓存。

- [ ] **Step 1: 写失败测试**
- [ ] **Step 2: 运行测试确认红灯**
- [ ] **Step 3: 初始化 `_dirty`，`Eo` 记录 dirty，`Co` 合并增量**
- [ ] **Step 4: `wo` 只保存 dirty + `slg-file-v1`，成功后清空 dirty**
- [ ] **Step 5: 更新 `maybePruneCache` 与 full 清空逻辑**
- [ ] **Step 6: 运行测试确认绿灯**

### Task 3: 文件级保存改为后台执行

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（`patch_translation_network`）
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Consumes: `wo(_force)` 的异步保存函数。
- Produces: 文件任务不等待每次缓存保存；`runFileTasksParallel` 结束后统一强制 flush。

- [ ] **Step 1: 写失败测试**
- [ ] **Step 2: 运行测试确认红灯**
- [ ] **Step 3: resume/普通分支改为 `wo(!0)` 后台执行**
- [ ] **Step 4: 运行测试确认绿灯**

### Task 4: 输出目录 URI 缓存

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（新增 `patch_output_write_cache`）
- Test: `apk-work/ui-redesign/test_engine_performance.py`

**Interfaces:**
- Consumes: `E.createDirectory`, `E.writeFileToDir`, React 输出目录 `m`。
- Produces: `Ne(path, content)` 对相同父目录只创建一次目录。

- [ ] **Step 1: 写失败测试**
- [ ] **Step 2: 运行测试确认红灯**
- [ ] **Step 3: 实现 `Ne` 目录缓存**
- [ ] **Step 4: 运行测试确认绿灯**

### Task 5: 回归与产物重建

- [ ] 运行 `test_translation_quality.py`、`test_bugfix_install_language.py`、`test_engine_performance.py`
- [ ] 运行 `python patch_workshop_ui.py` 重新生成 `generated/index-CJtfdHOF.js`
- [ ] 运行 `python build_workshop_apk.py` 重建 `slg-workshop-ui-signed.apk`
