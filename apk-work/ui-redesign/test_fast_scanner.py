import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAST_SCAN = ROOT / "apk-work" / "native-fast-scan"
SCANNER = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java"
INSTALLED_APPS = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledAppSource.java"
BUILDER = FAST_SCAN / "build_fast_scanner.py"


class FastApkScannerContractTest(unittest.TestCase):
    def test_scanner_uses_central_directory_and_bounded_async_copy(self):
        self.assertTrue(SCANNER.exists(), "FastApkScanner.java must exist")
        source = SCANNER.read_text("utf-8")
        for token in (
            "new Thread",
            "new ZipFile",
            "SCAN_TIMEOUT_MS = 60_000L",
            "temp.delete()",
            "MAX_CACHE_ENTRIES = 4",
            '"packageName"',
            '"scanDurationMs"',
            '"cacheHit"',
        ):
            self.assertIn(token, source)
        self.assertNotIn("ZipInputStream", source)

    def test_scanner_prefers_seekable_descriptor_for_multi_gigabyte_apks(self):
        self.assertTrue(SCANNER.exists(), "FastApkScanner.java must exist")
        source = SCANNER.read_text("utf-8")
        for token in (
            "openFileDescriptor",
            '"/proc/self/fd/"',
            "ParcelFileDescriptor",
            "scanSeekableDescriptor",
        ):
            self.assertIn(token, source)

    def test_build_pipeline_patches_only_the_entrypoint_and_adds_helper_dex(self):
        self.assertTrue(BUILDER.exists(), "build_fast_scanner.py must exist")
        source = BUILDER.read_text("utf-8")
        for token in (
            "listApkEntries",
            "FastApkScanner;->scanAsync",
            ".annotation runtime Lcom/getcapacitor/PluginMethod;",
            "classes6.dex",
            "classes7.dex",
            "apktool_3.0.2.jar",
            "d8.bat",
        ):
            self.assertIn(token, source)

    def test_installed_app_source_is_private_launcher_only(self):
        self.assertTrue(INSTALLED_APPS.exists(), "InstalledAppSource.java must exist")
        source = INSTALLED_APPS.read_text("utf-8")
        for token in (
            "Intent.ACTION_MAIN",
            "Intent.CATEGORY_LAUNCHER",
            "queryIntentActivities",
            "context.getPackageName()",
            "sourceDir",
            "splitSourceDirs",
            'new File(context.getCacheDir(), "installed-apks")',
            'put("source", "installed")',
            'put("splitApk", splitCount > 0)',
        ):
            self.assertIn(token, source)
        self.assertNotIn("QUERY_ALL_PACKAGES", source)

        builder = BUILDER.read_text("utf-8")
        for token in (
            "SOURCE_SOURCES",
            "*map(str, SOURCE_SOURCES)",
            "listInstalledApps",
            "InstalledAppSource;->listInstalledApps",
            "selectInstalledApp",
            "InstalledAppSource;->selectInstalledApp",
        ):
            self.assertIn(token, builder)


if __name__ == "__main__":
    unittest.main()
