# SLG 翻译器 Bug 全面修复计划（2026-08-02）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复审计发现的 6 类 bug：清理残留 partial、恢复横幅不消失/误报、会话心跳、返回首页状态保持、保存下载失败残留，并保持全部现有功能不回归。

**Architecture:**
- 原生侧：`CleanupSupport.deleteTempFiles` 增加对 `installed-apks/` 子目录的扫描；`InstallSupport.savePatchedApkToDownloads` 失败时删除已插入的 MediaStore 行。
- 前端侧：会话对象增加 `translating` 标志；`snapshotKey` 纳入 `sessionRestoredAt`；开始翻译时记录心跳；弹窗关闭时恢复进入弹窗前的手动空闲状态。
- 全部修复采用 TDD：先写失败测试（JS 行为测试 / Java harness），再实现，最后跑全套 54+ 项测试。

**Tech Stack:** Python（构建与测试）、JavaScript（WebView 前端注入）、Java（Capacitor 原生桥）、Node.js（JS 行为测试）、adb（真机验证）。

---

## 任务 1：清理功能删除 installed-apks 中的 .partial/.tmp

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/CleanupSupport.java`
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

- [ ] **Step 1: 写失败测试**（在 `test_fast_scanner.py` 增加 `test_cleanup_storage_removes_interrupted_partials_in_installed_apks`，复用现有 CleanupHarness 模式，在 installed-apks 内创建 `.partial` 与 `.tmp`，断言清理后被删除）

- [ ] **Step 2: 运行确认红灯**：`python -m unittest apk-work/ui-redesign/test_fast_scanner.py -k partials_in_installed_apks -v` → FAIL

- [ ] **Step 3: 最小实现**：`deleteTempFiles` 改为同时扫描 `base/installed-apks`，删除 `.partial`/`.tmp`/`.idsig`；`deleteApkCopies` 保持只删 `.apk`

- [ ] **Step 4: 运行确认绿灯**：同上命令 → PASS；再跑全套 `python -m unittest discover -s apk-work/ui-redesign -p 'test_*.py'` → 全绿

## 任务 2：放弃恢复横幅立即消失

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（`snapshotKey`）
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

- [ ] **Step 1: 写失败测试**：`test_dismiss_recovery_banner_re_renders_immediately`，模拟 ready 状态含 sessionRestoredAt → 执行 dismiss handler → `refresh()` → 断言 shell 已重绘且不再含“上次翻译中断”

- [ ] **Step 2: 运行确认红灯** → FAIL（横幅仍在）

- [ ] **Step 3: 最小实现**：`snapshotKey` 的 key 数组增加 `s.sessionRestoredAt?"restored":""`

- [ ] **Step 4: 运行确认绿灯** → PASS + 全套绿

## 任务 3：恢复横幅误报 + 会话心跳

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（会话保存、triggerReactButton、restoreSession、recoveryBanner、refresh 心跳）
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

- [ ] **Step 1: 写失败测试**：
  - `test_session_banner_only_after_translation_started`：SESSION_KEY 无 translating 时 restoreSession 后不显示横幅；有 translating 时显示
  - `test_translation_heartbeat_updates_session`：translating 状态 refresh 会更新 savedAt

- [ ] **Step 2: 运行确认红灯** → FAIL

- [ ] **Step 3: 最小实现**：
  - 会话保存加 `translating:false`
  - `triggerReactButton` 开始翻译时置 `translating:true` 并更新 `savedAt`
  - `restoreSession` 仅在 `s.translating` 时设置 `sessionRestoredAt`（仍静默恢复选择）
  - `refresh()` 在 translating 状态每 ≥10s 更新一次 `savedAt`（心跳）

- [ ] **Step 4: 运行确认绿灯** → PASS + 全套绿

## 任务 4：返回首页后打开作品/我的再关闭保持首页

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py`（openSettings/closeSettings/openGallery/closeGallery）
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

- [ ] **Step 1: 写失败测试**：`test_overlay_close_preserves_manual_idle_state`，先置 manualIdle=true + idle，openGallery→closeGallery 后断言仍为 idle

- [ ] **Step 2: 运行确认红灯** → FAIL

- [ ] **Step 3: 最小实现**：openSettings/openGallery 记录 `manualIdleBeforeOverlay`，close 时恢复该值

- [ ] **Step 4: 运行确认绿灯** → PASS + 全套绿

## 任务 5：保存补丁 APK 失败时删除残留下载条目

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/InstallSupport.java`
- Modify: `apk-work/native-fast-scan/stubs/android/content/ContentResolver.java`（增加 delete 方法供测试）
- Test: `apk-work/ui-redesign/test_fast_scanner.py`

- [ ] **Step 1: 写失败测试**：`test_save_patched_apk_failure_cleans_media_store_entry`，FakeContext 的 ContentResolver 返回会抛 IOException 的 OutputStream，断言 delete 被调用且 call.reject

- [ ] **Step 2: 运行确认红灯** → FAIL（当前无 delete 调用）

- [ ] **Step 3: 最小实现**：插入 targetUri 后若拷贝异常，`contentResolver.delete(targetUri, null, null)`

- [ ] **Step 4: 运行确认绿灯** → PASS + 全套绿

## 任务 6：构建、安装与真机验证

- [ ] 运行全套测试（54+ 新测试）全绿
- [ ] `python apk-work/ui-redesign/build_workshop_apk.py` 构建成功
- [ ] `adb install -r -d` 安装到手机
- [ ] 真机验证：清理按钮能删除 .partial；放弃恢复立即消失；恢复横幅只在翻译中断后出现；返回首页后作品/我的关闭仍回首页
