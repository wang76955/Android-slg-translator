# Changelog

All notable changes to this project are documented in this file.

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
