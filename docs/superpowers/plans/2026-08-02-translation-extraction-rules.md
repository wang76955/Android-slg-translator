# 翻译抽取规则完善实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让翻译软件能提取并翻译之前漏掉的约 1,932 条文本（手机对话、UI 偏好文本、翻译文件 old keys），并验证原 19 条修复生效。

**Architecture:** 三处修复：(1) `RpycTextExtractor` 增加对 pickle 内嵌源码字符串中函数调用参数的提取（消息类 + Ren'Py 偏好类）；(2) JS 端把游戏自带翻译文件（x-tl/x-chinese|english|german）的 old keys 纳入补充语料；(3) 保留既有对话/菜单/screen 提取。每步 TDD 红绿灯。

**Tech Stack:** Java 8 (RpycTextExtractor)、Python (patch_workshop_ui.py + unittest)、APK 构建脚本。

---

## 背景与根因（审计确认）

1. **手机对话文本（1,815 条）**：`assets/x-game/x-phone.rpyc` 的 pickle 内含一条 323,909 字节的 BINUNICODE（完整 `phone.rpy` 源码），文本是 `send_phone_message("Aine", "消息", "aine_dm", ...)` 调用的参数。现有 extractor 只解析结构化 `what/caption/old/text/text_value` 键与 `_("...")`/`Character("...")` 正则，不提取函数调用参数 → 该文件提取 0 条。
2. **UI/偏好文本（约 100 条）**：如 "Music Volume" 在 `x-classic_preferences_common.rpymc` 的源码字符串 `_VolumePreference(u"Music Volume", 'music', ...)` 中；`u"..."` 前缀字符串不是 `_("...")`，未被提取。
3. **翻译文件 old keys 继承**：部分文本（如 "And Sky is her?"）完全不在任何原始 rpyc 中，只存在于 `x-tl/x-chinese/x-strings.rpyc` 等翻译文件的 `TranslateString` old keys。JS 端 `_f` 过滤把 `/x-tl/`、`/tl/` 完全排除，导致这些原文永远不会进入语料。
4. **原 19 条**：代码已修（FastApkScanner 转义、JS 长度/路径/options 过滤），需重跑翻译验证。

---

### Task 1: extractor 提取源码字符串中的函数调用参数

**Files:**
- Modify: `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycTextExtractor.java` (collectExtraTexts 附近)
- Test: `apk-work/ui-redesign/test_fast_scanner.py` (新增 fixture + harness)

- [ ] **Step 1: 写失败测试** — 构造 rpyc fixture，pickle 含源码字符串 `send_phone_message("Aine", "Hello there.", "aine_dm")` 与 `_VolumePreference(u"Music Volume", 'music')`，断言 extractor 输出包含 "Hello there." 与 "Music Volume"。
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 实现 `collectSourceCallTexts(String source, Set<String> out)`**
  - 正则匹配 `函数名(args)`，函数名白名单：
    - 消息类：包含 `message`/`phone`/`chat`/`dm` 或等于 `send_phone_message` → 提取前 2 个字符串参数
    - 偏好类：`_VolumePreference`/`_SliderPreference`/`_Preference` → 提取第 1 个字符串参数
  - 参数解析支持 `"..."` 与 `'...'`（含 `u` 前缀），处理转义。
  - 复用 `isUserText` 过滤。
- [ ] **Step 4: 运行测试确认通过**
- [ ] **Step 5: 回归全量测试**

### Task 2: JS 端纳入翻译文件 old keys 作为补充语料

**Files:**
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py` (`patch_candidate_filter` 附近)
- Test: `apk-work/ui-redesign/test_workshop_patch.py`

- [ ] **Step 1: 写失败测试** — 断言补丁后的 JS 不再完全排除 `/x-tl/x-chinese/`，且保留 `x-tl/x-slgtranslated/` 排除。
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 实现** — 修改 `_f` 过滤：允许 `x-tl/x-chinese|english|german/` 作为补充语料文件进入提取列表；仍排除 `x-tl/x-slgtranslated/` 与 `/tl/`。
- [ ] **Step 4: 运行测试确认通过**
- [ ] **Step 5: 回归全量测试**

### Task 3: 全量测试 + 审计复测

**Files:**
- Run: `python -m unittest discover apk-work/ui-redesign -p "test_*.py"`
- Run: `python apk-work/ui-redesign/qa/audit_coverage.py`（先重建 extracted-texts）

- [ ] **Step 1: 全套测试通过（红绿灯）**
- [ ] **Step 2: 用修复后的 extractor 重建 corpus**（对 ewn-audit-src.apk 重跑全部 rpyc 提取）
- [ ] **Step 3: 审计**：目标 `missing == []`（至少大幅下降且新增文本覆盖中文翻译 old keys）

### Task 4: 构建 APK + 真机验证

**Files:**
- Run: `python apk-work/ui-redesign/build_workshop_apk.py`
- ADB: `C:\Users\王运\Documents\文件翻译\.tools\platform-tools\adb.exe`

- [ ] **Step 1: 构建补丁 APK（红绿灯：退出码 0）**
- [ ] **Step 2: 安装到手机**
- [ ] **Step 3: 启动验证 + 扫描"恶女2.2"重跑翻译**
- [ ] **Step 4: 编译新补丁并复测审计**

---

## 自审

- **覆盖**：1→手机文本；2→UI 偏好文本；3→翻译文件继承 + 验证；4→端到端。原 19 条由 Task 3/4 验证。
- **占位符**：无。
- **一致性**：`collectSourceCallTexts` 签名在 Task 1 定义并被 extractTexts 调用；`_f` 过滤修改在 Task 2。
