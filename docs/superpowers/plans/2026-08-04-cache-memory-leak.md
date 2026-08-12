# 翻译缓存内存泄漏修复计划（2026-08-04）

> **For agentic workers:** 按 TDD 实现：先写失败测试，再实现，最后跑全套测试并重新构建 APK。

**Goal:** 修复"点击安装包 / 清理旧缓存后应用内存占用不变"：缓存清理未释放 `cacheIndex` 引用，且翻译缓存无限增长无上限。

**Root cause:**
1. `_mode==='full'` 清空 `vo={}` 但**没有清空 `cacheIndex`**——`cacheIndex` 持有所有旧缓存项
   （`{sourceText, translatedText, updatedAt}`）的引用，内存不释放；且 `To()` 查缓存时
   `vo[cacheV2Key(...)] || cacheIndex[...]` 仍能命中旧缓存，导致"清理无效"。
2. `Eo()` 每次翻译把结果写入 `vo` + `cacheIndex`，**无上限、无淘汰**——游戏越大缓存越多，
   内存持续增长。

**Fix:**
1. full 模式清空时同步清空 `cacheIndex`。
2. 新增 `maybePruneCache()`：缓存条目（`_o` 前缀键）超过 30000 条时按 `updatedAt` 淘汰最旧一半，
   并同步删除 `cacheIndex` 引用；在 `wo()` 保存前调用。

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（新增 `patch_cache_memory` 补丁函数，
  在 `patch_translation_quality` 之后调用）
- Test: `apk-work/ui-redesign/test_workshop_patch.py` / `test_translation_quality.py`

## 任务 1：写失败测试（TDD 红灯）

- `test_full_clear_resets_cache_index`：补丁后 JS 必须包含
  `_mode==='full'&&(vo={},cacheIndex={},bo=!0,await wo())`（当前是 `vo={}` 不带 cacheIndex → FAIL）
- `test_cache_prune_caps_memory`：Node 行为测试——填充 31000 条缓存到 vo + cacheIndex，
  调用 `maybePruneCache()`，断言 vo/cacheIndex 降到 ≤30000、最旧条目被删、`To()` 查被删条目返回 null

## 任务 2：最小实现

- `patch_cache_memory(js)`：
  - 替换 `_mode==='full'&&(vo={},bo=!0,await wo())` → `vo={},cacheIndex={},bo=!0,await wo()`
  - 在 `async function wo(){` 前注入 `maybePruneCache`（上限 30000，淘汰最旧一半，
    从 vo 键剥离 `_o+'v2|'` 前缀得到 cacheIndex 键同步删除）
  - 在 `wo()` 的 `globalThis.__slgCacheDbg.entries=Object.keys(vo).length;bo=!1;` 前调用 `maybePruneCache()`
- 跑全套测试确认绿灯

## 任务 3：重新构建并验证

- `python build_workshop_apk.py` 重新打包
- 从 APK 提取 JS 验证修复点存在
- 更新 `docs/translation-quality-rules.md`：记录缓存内存管理经验（cacheIndex 必须与 vo 同步清理）
