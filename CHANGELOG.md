# Changelog

All notable changes to this project are documented in this file.

## [1.0.5] - 2026-08-05

### Added

- 全新工坊风 UI：OKLCH 亮/暗双主题、焦点环、禁用态、统一动效、顶栏状态徽章
- 首页三段式引导：选择应用 → 翻译 → 安装补丁
- 底部导航（首页 / 安装包 / 我的）与「我的」五入口菜单
- 翻译服务页：供应商设置、轻量模型、本地大模型、API Key 配置
- 安装包页：补丁 APK 列表，含 APK 图标、元数据、保存到下载
- 存档转移 / 导入存档设置页
- 新应用图标；版本号正式改为 1.0.5（versionCode 5）

### Changed

- 移除「备份当前存档」按钮，减少按钮数量

### Fixed

- 清除后台再进入时旧版 UI 闪现和自动「翻译就绪」误判
- 存档列表只显示一个 zip 的问题

### Notes

- SHA256：`DD1AD3DACAD47FE6C262F832883B7481F647A58A2E27333E5839EE2E3FC0C4AB`
- 最低 Android 版本：Android 7.0（API 24）

## [1.0.4] - 2026-08-04

### Fixed

- Storage cleanup now removes patched APKs of other games by package name, actually freeing space
- Selecting a game no longer misreports "patch APK generated" before translation starts
- Completed state now requires both translation-done and patch-written signals

## [1.0.3] - 2026-08-04

### Added

- Settings sub-views: each feature (translation service, save transfer, cleanup, about) has its own screen
- Navigation restore: closing "My" / "Patches" returns to the previous tab

### Changed

- Bottom navigation renamed from "Works" to "Patches"
- Craft-workshop UI theme: moss-green primary, warm amber accent, brand panel decoration

### Fixed

- Settings shell scope issue where tapping "My" did nothing
- App selection reliability (manualIdle/lastSnapshot state)

## [1.0.2] - 2026-08-03

### Added

- Full dialogue coverage: Ren'Py markup-tagged dialogue no longer filtered as file paths (726 lines)
- PackageInstaller.Session install path for multi-GB patched APKs

### Fixed

- WebView renderer OOM during long translations (largeHeap + per-file cache pruning)
- Translation session interrupted by page refresh

### Changed

- Translation speed: larger batches, higher concurrency

## [1.0.1] - 2026-07-13

- Initial Android release: APK-based Ren'Py translation workflow
