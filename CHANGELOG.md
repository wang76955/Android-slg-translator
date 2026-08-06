# Changelog

All notable changes to this project are documented in this file.

## [1.0.8] - 2026-08-06

### Fixed

- Live translation progress now refreshes periodically, so script and batch details no longer stay on stale snapshots
- Selecting an app no longer leaves the panel showing "尚未选择 APK" when the React summary uses a different label format

### Changed

- Release version bumped to 1.0.8 (versionCode 8); About screen now shows Android v1.0.8

## [1.0.6] - 2026-08-06

### Added

- Independent `翻译文本` entry added to compiled Ren'Py language menus while preserving every original language option
- Translation detail view now shows the batch currently being processed
- Faster translation pipeline: global API semaphore, file-level parallel workers, incremental cache persistence, background saves, and output directory URI caching
- Local LLM and ML Kit translation engine improvements for faster on-device translation

### Fixed

- First translation page flash that appeared immediately after opening the app
- Long translation sessions no longer crash the WebView or leak cache memory
- Install button remains functional after translating a new game
- Translated games expose the translated text as a selectable language option
- Cache cleanup now also clears the in-memory cache index

### Changed

- Release version bumped to 1.0.6 (versionCode 6) and the About screen now shows Android v1.0.6

## [1.0.5] - 2026-08-05

### Added

- Save transfer and save import are now separate settings pages with independent game selectors
- Save the selected game's current save and share it as a downloadable archive
- Import shared save ZIP archives from the Downloads directory
- Delete save backups and imported ZIP archives from the UI
- Custom launcher icon set for the workshop APK

### Changed

- Removed the redundant backup-current-save button to simplify the save transfer page

### Fixed

- Old UI flash and automatic ready-state after clearing the app from the background
- Archive list now reflects all discovered save ZIP files

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
