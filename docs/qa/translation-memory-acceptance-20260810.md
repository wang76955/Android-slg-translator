# Translation Memory Acceptance

Date: 2026-08-10
Device: `MZNRYXEQS859O7GU` / `PEMM20` / Android 13 / API 33
Package: `com.slgtranslator.app` / versionName `1.0.8` / versionCode `8`

## Scope

This record covers the storage-peak repair in the APK rewrite phase. The confirmed failure was:

```text
Failed to build patched APK: write failed: ENOSPC
```

The source APK stayed on disk while a second rewritten APK and previous APK copies were also present. This created a disk-space peak during ZIP rewriting. The evidence did not identify repeated ML Kit model loading as the direct cause of this failure.

## Implemented

- `TranslationCompiler` now runs a `StatFs.getAvailableBytes()` preflight before APK rewriting.
- The preflight accounts for the source APK, rewritten temporary APK, file-backed pending payloads, and a safety margin.
- App-owned `installed-apks` stale APK copies, `.tl.tmp`, and `.partial` files are pruned before the build. The current source APK and translation output directory are preserved.
- `PendingApkEntryStore` exposes disk-backed payload size without retaining payload bytes in a collection.
- Failed rewrites remove `.tl.tmp`; successful renames do not remove the final APK.
- Low-space failures use the stable code `translation_storage_insufficient` and retain the original I/O message where available.

## Verification Evidence

| Check | Result | Evidence |
|---|---|---|
| Red contract before implementation | PASS as expected | `test_translation_compiler_preflights_rewrite_storage` initially failed on missing `StatFs`/error-code contract |
| Storage source contract | PASS | `python -m unittest test_fast_scanner.FastApkScannerContractTest.test_translation_compiler_preflights_rewrite_storage -v` |
| File-backed payload behavior | PASS | `test_pending_entry_store_is_file_backed` |
| Real preflight cleanup harness | PASS | `test_translation_compiler_storage_preflight_prunes_stale_build_material` |
| Compiler regression harnesses | PASS | requested paths, always-on dialogue, existing keys, large pair counts |
| Frontend performance tests | PASS | 10 tests |
| Workshop UI tests | PASS | 93 tests |
| Memory sampler tests | PASS | 5 tests |
| Java 8 + D8 helper build | PASS | `build_helper_dex` completed and produced `helper-dex/classes.dex` |
| APK rebuild/signature | PASS | Apktool + D8 + `apksigner verify`; v2=true, v3=true, one signer |
| Device install/startup | PASS | `adb install -r -d`; app launched and home screen rendered |

## Artifact

- APK: `apk-work/slg-workshop-ui-signed.apk`
- Size: `34,326,646` bytes
- SHA-256: `55FA735A985D633F199F71E044EDAEC8343199C107C8BB8F5306ECF144DA6BAB`
- Screenshot: `apk-work/qa/translation-storage-fix-home-20260810.png`

The repository's expected `apk-work/com.slgtranslator.app-base.apk` is absent. For this local verification build, the already verified same-package version `1.0.8` signed APK was supplied to both build modules through an in-memory path override. The build scripts were not changed to hide this missing input.

## Device Storage Observation

At the time of verification, `/data/user/0` reported approximately `16G` available on a `107G` filesystem. This is an observation only; it is not a low-space injection test and does not prove a full translation run under the acceptance PSS thresholds.

## Remaining Verification

- Run the complete scan -> translate -> rewrite flow twice on the same real APK while sampling PSS/RSS and native heap.
- Verify the actual device path returns `translation_storage_insufficient` under an injected low-space condition without leaving `.tl.tmp`.
- Record peak PSS, post-task PSS after 60 seconds, and residual growth after the second translation.
- Provide the missing base APK or production keystore before treating the artifact as a release build.
