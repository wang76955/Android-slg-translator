# SLG Translator 夜间迭代设计文档（2026-08-02）

> 状态：已实现并在真机验证。本文档供用户醒来审阅；细节（尤其存档转移）可继续细化。

## 0. 背景：恶女 2.2 翻译收尾（本轮已验证）

在开始新功能前，先修复并验证了游戏翻译本身：

- 提取器补全：
  - `Menu.items` 选项文本（含 `{#tag}` 短标签，如 `Enter{#ep2}`）
  - `_("...")` 标记的界面文本（主菜单/设置/存档界面等）
  - `Character("名字", ...)` 角色名（官方中文同样用字符串翻译处理角色名）
  - 保留原文首尾空白（Ren'Py 按原文精确匹配，`trim` 会丢 key）
- JS 管线：rpyc 文本不再走激进过滤器（修复 If/With/Stop 开头的对话、`{/tag}` 斜杠、`{#tag}` 被误杀的问题）；`as()` 输出器保留原文 key；引擎文件（`x-renpy/x-common`）输出路由进统一编译桶。
- 结果：编译译文 29616 → 30873 条；角色名（斯凯/艾因/弗雷亚…）、界面（开始/历史/保存/读取/音乐音量…）、带空格行全部进包；游戏启动无崩溃。
- 红绿灯：`python -m unittest test_workshop_patch test_fast_scanner test_built_apk` → 54 项全绿。

## 1. 一键清理安装包与旧缓存

**问题**：每次选择已安装应用都会复制一份 4.2GB 源 APK 到 `installed-apks/`，每次打补丁又写一份补丁 APK，旧副本堆积导致手机存储耗尽（实测占满 107GB）。

**设计**：
- 原生桥 `CleanupSupport.cleanupStorage({keepUri})`：
  - 删除 `installed-apks/` 下除当前选中源（keepUri）外的全部 `.apk`
  - 删除 `SLG-Translator-Output/` 下除最新补丁外的旧 `.apk`
  - 清理 `.tmp/.partial/.idsig` 残留与空目录
  - 返回 `{freedBytes, deletedCount, keptCount}`
- UI：设置页（我的）新增「清理安装包与旧缓存」按钮 + 结果提示。
- 验证：真机点击后释放 7.9GB、删除 2 个旧副本、保留最新补丁。

## 2. 翻译逻辑通用化

现状已经是通用管线，本轮进一步验证并补齐：

- 提取器不依赖具体游戏：结构化遍历 rpyc（Say/TranslateSay/Menu/Translate/Text/`_()`/Character 名），对新老 Ren'Py 版本通用。
- 缓存按 `包名|文件|源语言|目标语言|模型` 哈希，换游戏/换文件不串。
- 补丁注入、语言菜单、编译合并均为通用逻辑（`slgtranslated` 独立语言桶）。
- 本轮补齐：引擎公共文件（`x-renpy/x-common/*.rpyc`）纳入候选并路由到统一编译桶，任何 Ren'Py 游戏的默认 UI 字符串都能翻译。

## 3. 前端交互优化

- ready 状态新增模式提示：「继续上次只翻译新增文本（推荐）；全部重译会重新调用翻译接口」。
- 设置页补上清理入口（见 §1）。
- 保留并完善底部导航（首页/作品/我的）、作品页补丁列表与保存到下载。

## 4. 存档转移（雏形，待细化）

**设计（第一版）**：
- 原生桥（`SaveTransfer`）：
  - `backupSaves({packageName})`：复制 `Documents/RenPy_Saves/<包名>` → 应用目录 `save-backups/<包名>-<时间戳>/`
  - `restoreSaves({packageName, backupDir})`：复制回存档目录（合并）
  - `listSaveBackups()`：列出备份
- UI：作品页底部新增「存档转移（雏形）」区：备份当前游戏存档 / 恢复所选备份 / 备份列表。
- 验证：真机备份 7 个文件 → 删除 auto-3 → 恢复成功。

**待细化（用户明天确认）**：
- 存档目录探测（按包名 vs 按 save_directory）
- 冲突处理（恢复前是否覆盖、是否做双份）
- 跨设备传输方式（文件/剪贴板/云）
- UI 放底部导航还是作品页

## 5. 付费点调研（只列清单，未实现）

见最终回复中的付费点清单（基于 LunaTranslator/MTool 等同类工具、DeepL/OpenAI 成本结构、本 App 架构）。
