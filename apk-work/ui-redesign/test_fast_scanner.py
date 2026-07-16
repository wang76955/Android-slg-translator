import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAST_SCAN = ROOT / "apk-work" / "native-fast-scan"
SCANNER = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java"
INSTALLED_APPS = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledAppSource.java"
BUILDER = FAST_SCAN / "build_fast_scanner.py"
GENERATED = FAST_SCAN / "generated"
DEXDUMP = ROOT / ".tools" / "android-15" / "dexdump.exe"


class FastApkScannerContractTest(unittest.TestCase):
    def assert_installed_app_copy_contract(self, source):
        self.assertRegex(source, r"COPY_BUFFER_SIZE\s*=\s*1024\s*\*\s*1024\s*;")
        self.assertRegex(source, r"byte\[\]\s+buffer\s*=\s*new byte\[COPY_BUFFER_SIZE\]")
        self.assertRegex(
            source,
            r"while\s*\(\(count\s*=\s*input\.read\(buffer\)\)\s*!=\s*-1\)\s*"
            r"\{\s*output\.write\(buffer,\s*0,\s*count\);\s*\}",
        )

        partial_creation = 'partial = new File(directory, output.getName() + ".partial");'
        self.assertIn(partial_creation, source)
        self.assertRegex(
            source,
            r"if\s*\(partial\.exists\(\)\s*&&\s*!partial\.delete\(\)\)\s*"
            r'\{\s*throw new IOException\("stale partial"\);\s*\}',
        )
        self.assertRegex(
            source,
            r"finally\s*\{\s*if\s*\(partial\s*!=\s*null\s*&&\s*partial\.exists\(\)\)\s*"
            r"\{\s*partial\.delete\(\);\s*\}\s*\}",
        )
        self.assertRegex(source, r"output\.flush\(\);\s*output\.getFD\(\)\.sync\(\);")

        rename = "if (!partial.renameTo(output))"
        self.assertIn(rename, source)
        self.assertLess(source.index(partial_creation), source.index(rename))
        self.assertIn('throw new IOException("atomic rename")', source)
        self.assertRegex(
            source,
            r"catch\s*\(IOException error\)\s*\{\s*"
            r'call\.reject\("Could not copy the app APK\. Free storage space and try again\."\);',
        )

        self.assertIn('MessageDigest.getInstance("SHA-256")', source)
        self.assertIn(
            'String identity = packageName + "/" + source.lastModified() + "/" + source.length();',
            source,
        )
        self.assertIn('new File(directory, fingerprint(packageName, source) + ".apk")', source)

        self.assertLess(source.index("partial = null;"), source.index("cleanOldApks(directory, output);"))
        self.assertRegex(
            source,
            r"if\s*\(!file\.equals\(keep\)\s*&&\s*"
            r'\(file\.getName\(\)\.endsWith\("\.apk"\)\s*\|\|\s*'
            r'file\.getName\(\)\.endsWith\("\.partial"\)\)\)\s*\{\s*file\.delete\(\);',
        )

        selection_start = source.index("int splitCount =")
        result_chain = re.search(
            r"call\.resolve\(new JSObject\(\)(.*?)\);",
            source[selection_start:],
            re.DOTALL,
        )
        self.assertIsNotNone(result_chain, "selection must resolve a structured installed-app result")
        result = result_chain.group(1)
        for field in (
            '.put("uri", Uri.fromFile(output).toString())',
            '.put("name", label + ".apk")',
            '.put("packageName", packageName)',
            '.put("source", "installed")',
            '.put("splitApk", splitCount > 0)',
            '.put("splitCount", splitCount)',
        ):
            self.assertIn(field, result)

        self.assertNotRegex(
            source,
            r"call\.reject\([^;]*(?:sourceDir|getAbsolutePath\(\)|getPath\(\))",
        )
        self.assertNotRegex(
            source,
            r"(?:System\.(?:out|err)|printStackTrace|Log\.)[^;]*"
            r"(?:sourceDir|getAbsolutePath\(\)|getPath\(\))",
        )

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
        self.assert_installed_app_copy_contract(source)

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
        self.assertIn("bridge_counts == [0] * len(INSTALLED_APP_METHODS)", builder)
        self.assertIn("bridge_counts != [1] * len(INSTALLED_APP_METHODS)", builder)
        self.assertIn("patched.count(signature) != 1 or patched.count(delegate) != 1", builder)
        self.assertIn("Expected exactly one listApkEntries method", builder)
        self.assertEqual(builder.count('".method public final listInstalledApps('), 2)
        self.assertEqual(builder.count('".method public final selectInstalledApp('), 2)

    def test_installed_app_contract_detects_copy_buffer_regression(self):
        source = INSTALLED_APPS.read_text("utf-8")
        broken = source.replace("1024 * 1024", "8192", 1)
        self.assertNotEqual(source, broken, "controlled mutation must alter the buffer constant")
        with self.assertRaises(AssertionError):
            self.assert_installed_app_copy_contract(broken)

    def test_generated_dex_has_unique_installed_app_bridge(self):
        classes6 = GENERATED / "classes6.dex"
        classes7 = GENERATED / "classes7.dex"
        if not classes6.exists() or not classes7.exists():
            self.skipTest("generated DEX files are not present; run build_fast_scanner.py first")
        self.assertTrue(DEXDUMP.exists(), "generated DEX verification requires dexdump.exe")

        def dump(path):
            completed = subprocess.run(
                [str(DEXDUMP.relative_to(ROOT)), str(path.relative_to(ROOT))],
                check=True,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            return completed.stdout

        plugin_dump = dump(classes6)
        helper_dump = dump(classes7)
        self.assertEqual(plugin_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'selectInstalledApp'"), 1)
        self.assertEqual(
            helper_dump.count("Class descriptor  : 'Lcom/slgtranslator/app/InstalledAppSource;'"),
            1,
        )
        self.assertEqual(helper_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(helper_dump.count("name          : 'selectInstalledApp'"), 1)


if __name__ == "__main__":
    unittest.main()
