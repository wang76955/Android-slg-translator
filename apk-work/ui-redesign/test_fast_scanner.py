import re
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAST_SCAN = ROOT / "apk-work" / "native-fast-scan"
SCANNER = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java"
INSTALLED_APPS = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledAppSource.java"
BUILDER = FAST_SCAN / "build_fast_scanner.py"
WORKSHOP_BUILDER = ROOT / "apk-work" / "ui-redesign" / "build_workshop_apk.py"
GENERATED = FAST_SCAN / "generated"
DEXDUMP = ROOT / ".tools" / "android-15" / "dexdump.exe"
JAVA_HOME = ROOT / ".tools" / "jdk-17" / "jdk-17.0.19+10"
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"


def java_block_after(source, marker):
    start = source.index(marker)
    opening = source.index("{", start + len(marker))
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"unterminated Java block after {marker!r}")


class FastApkScannerContractTest(unittest.TestCase):
    def assert_installed_app_copy_contract(self, source):
        self.assertRegex(source, r"COPY_BUFFER_SIZE\s*=\s*1024\s*\*\s*1024\s*;")
        self.assertRegex(source, r"byte\[\]\s+buffer\s*=\s*new byte\[COPY_BUFFER_SIZE\]")
        self.assertRegex(
            source,
            r"while\s*\(\(count\s*=\s*input\.read\(buffer\)\)\s*!=\s*-1\)\s*"
            r"\{\s*output\.write\(buffer,\s*0,\s*count\);\s*\}",
        )

        partial_creation = (
            'partial = new File(directory, output.getName() + "." '
            '+ UUID.randomUUID().toString() + ".partial");'
        )
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
        cleanup = java_block_after(source, "private static void cleanOldApks(")
        self.assertIn('endsWith(".apk")', cleanup)
        self.assertNotIn('endsWith(".partial")', cleanup)

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

    def assert_installed_app_privacy_contract(self, source):
        listing = java_block_after(source, "private static void listInstalledAppsOnWorker(")
        launcher_iteration = java_block_after(
            listing,
            "for (ResolveInfo resolveInfo : launchers)",
        )
        self.assertRegex(
            launcher_iteration,
            r"packageName\.equals\(context\.getPackageName\(\)\)\s*\|\|\s*"
            r"unique\.containsKey\(packageName\)",
        )
        self.assertIn("unique.put(packageName,", launcher_iteration)
        self.assertLess(
            launcher_iteration.index("unique.containsKey(packageName)"),
            launcher_iteration.index("unique.put(packageName,"),
        )

        comparator = java_block_after(listing, "public int compare(AppEntry left, AppEntry right)")
        self.assertIn("left.label.compareToIgnoreCase(right.label)", comparator)
        self.assertNotIn("left.label.compareTo(right.label)", comparator)

        serialization = java_block_after(listing, "for (AppEntry app : apps)")
        list_fields = re.findall(r'\.put\("([^"]+)"\s*,', serialization)
        self.assertEqual(list_fields, ["label", "packageName"])
        self.assertNotRegex(serialization, r'"(?:uri|path|sourceDir|sourcePath)"')

        selection = java_block_after(source, "private static void copySelectedApp(")
        self.assertLess(
            selection.index("isLauncherPackage(packageManager, packageName)"),
            selection.index("packageManager.getApplicationInfo(packageName, 0)"),
        )
        validator = java_block_after(source, "private static boolean isLauncherPackage(")
        self.assertIn("queryLauncherApps(packageManager)", validator)
        query = java_block_after(source, "private static List<ResolveInfo> queryLauncherApps(")
        self.assertRegex(query, r"new Intent\(Intent\.ACTION_MAIN\)")
        self.assertRegex(query, r"intent\.addCategory\(Intent\.CATEGORY_LAUNCHER\)")
        self.assertRegex(query, r"packageManager\.queryIntentActivities\(intent,\s*0\)")

        success = selection[selection.index("call.resolve(new JSObject()") :]
        success = success[:success.index("));") + 3]
        success_fields = re.findall(r'\.put\("([^"]+)"\s*,', success)
        self.assertEqual(
            success_fields,
            ["uri", "name", "packageName", "source", "splitApk", "splitCount"],
        )
        self.assertNotRegex(success, r'"(?:path|sourceDir|sourcePath)"')

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
        self.assert_installed_app_privacy_contract(source)

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

    def test_installed_app_privacy_contract_detects_controlled_regressions(self):
        source = INSTALLED_APPS.read_text("utf-8")
        mutations = (
            source.replace(
                "packageName.equals(context.getPackageName()) || ",
                "",
                1,
            ),
            source.replace("compareToIgnoreCase", "compareTo", 1),
            source.replace(
                '.put("packageName", app.packageName)',
                '.put("packageName", app.packageName).put("path", app.packageName)',
                1,
            ),
        )
        for broken in mutations:
            self.assertNotEqual(source, broken, "controlled mutation must alter production source")
            with self.assertRaises(AssertionError):
                self.assert_installed_app_privacy_contract(broken)

    def test_installed_app_requests_are_serialized_and_cache_retains_two_finals(self):
        source = INSTALLED_APPS.read_text("utf-8")
        self.assertIn("Executors.newSingleThreadExecutor", source)
        self.assertIn('return new Thread(runnable, "installed-app-worker")', source)
        listing = java_block_after(source, "public static void listInstalledApps(")
        selection = java_block_after(source, "public static void selectInstalledApp(")
        self.assertIn("WORKER.execute(new Runnable()", listing)
        self.assertIn("WORKER.execute(new Runnable()", selection)
        self.assertNotIn("new Thread", listing)
        self.assertNotIn("new Thread", selection)
        self.assertIn("UUID.randomUUID().toString()", source)

        cleanup = java_block_after(source, "private static void cleanOldApks(")
        self.assertNotIn('endsWith(".partial")', cleanup)
        self.assertIn("finals.size()", cleanup)
        self.assertIn("index >= 2", cleanup)
        self.assertRegex(
            cleanup,
            r"if\s*\(index\s*>=\s*2\s*&&\s*!file\.equals\(keep\)\)\s*"
            r"\{\s*file\.delete\(\);",
        )
        self.assertIn("markNewest(directory, output);", source)
        recency = java_block_after(source, "private static void markNewest(")
        self.assertIn("Math.max(System.currentTimeMillis(), newest + 1)", recency)
        self.assertIn("if (!output.setLastModified(timestamp))", recency)
        self.assertLess(source.index("partial = null;"), source.index("cleanOldApks(directory, output);"))

    def test_cache_cleanup_does_not_delete_active_partial_or_previous_result(self):
        if not JAVA.exists() or not JAVAC.exists():
            self.skipTest("JDK is not present for executable cache ownership test")
        harness = r"""
import com.slgtranslator.app.InstalledAppSource;
import java.io.File;
import java.lang.reflect.Method;

public final class CacheOwnershipHarness {
    public static void main(String[] args) throws Exception {
        File directory = new File(args[0]);
        File first = touch(directory, "first.apk", 1000L);
        File activePartial = touch(directory, "second.request.partial", 1500L);
        Method cleanup = InstalledAppSource.class.getDeclaredMethod("cleanOldApks", File.class, File.class);
        cleanup.setAccessible(true);

        File second = touch(directory, "second.apk", 2000L);
        cleanup.invoke(null, directory, second);
        require(first.isFile(), "the previous returned URI must survive the second selection");
        require(second.isFile(), "the current returned URI must survive cleanup");
        require(activePartial.isFile(), "cleanup must not delete another request's partial");

        File third = touch(directory, "third.apk", 3000L);
        cleanup.invoke(null, directory, third);
        require(!first.exists(), "only finals older than current+previous should be pruned");
        require(second.isFile() && third.isFile(), "current and previous finals must remain");
        require(activePartial.isFile(), "final pruning must never own partial files");
    }

    private static File touch(File directory, String name, long modified) throws Exception {
        File file = new File(directory, name);
        require(file.createNewFile(), "fixture already exists: " + name);
        require(file.setLastModified(modified), "cannot set fixture timestamp: " + name);
        return file;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="installed-cache-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CacheOwnershipHarness.java"
            classes = temporary_path / "classes"
            cache = temporary_path / "cache"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            cache.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    *map(str, stubs),
                    str(INSTALLED_APPS),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CacheOwnershipHarness", str(cache)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_manifest_pipeline_adds_launcher_queries_without_broad_permission(self):
        builder = BUILDER.read_text("utf-8")
        workshop = WORKSHOP_BUILDER.read_text("utf-8")
        for token in (
            "patch_launcher_queries",
            'android.intent.action.MAIN',
            'android.intent.category.LAUNCHER',
            'GENERATED / "AndroidManifest.xml"',
        ):
            self.assertIn(token, builder)
        self.assertNotIn("QUERY_ALL_PACKAGES", builder)
        self.assertIn('"AndroidManifest.xml": FAST_SCAN_GENERATED / "AndroidManifest.xml"', workshop)

    def test_generated_dex_has_unique_installed_app_bridge(self):
        classes6 = GENERATED / "classes6.dex"
        classes7 = GENERATED / "classes7.dex"
        if not classes6.exists() or not classes7.exists():
            if os.environ.get("REQUIRE_FAST_SCAN_ARTIFACTS") == "1":
                self.fail("required generated DEX files are missing; run build_fast_scanner.py")
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
