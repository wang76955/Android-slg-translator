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
CAPACITOR_DEX = ROOT / "apk-work" / "extracted" / "classes3.dex"
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
        self.assertIn("catch (Throwable error)", source)

    def test_renpy_scripts_bypass_filename_heuristics_and_keep_supported_types(self):
        source = SCANNER.read_text("utf-8")
        self.assertIn('"rpym", "rpymc", "rpy", "rpyc"', source)
        self.assertIn(
            "if (!isRenPyScriptExtension(extension) && "
            "!Boolean.TRUE.equals(likelyText.invoke(plugin, name)))",
            source,
        )
        self.assertIn(
            "String fileType = normalizeRenPyFileType(extension, detectedType);",
            source,
        )

        harness = r"""
import com.slgtranslator.app.FastApkScanner;
import java.lang.reflect.Method;

public final class RenPyExtensionHarness {
    public static void main(String[] args) throws Exception {
        Method isRenPy = FastApkScanner.class.getDeclaredMethod(
            "isRenPyScriptExtension", String.class
        );
        isRenPy.setAccessible(true);
        Method normalize = FastApkScanner.class.getDeclaredMethod(
            "normalizeRenPyFileType", String.class, String.class
        );
        normalize.setAccessible(true);
        for (String extension : new String[] {"rpy", "rpyc", "rpym", "rpymc"}) {
            require((Boolean) isRenPy.invoke(null, extension), extension + " must bypass filename filtering");
        }
        require(!(Boolean) isRenPy.invoke(null, "json"), "json must retain the existing filename heuristic");
        require("rpy".equals(normalize.invoke(null, "rpym", "text")), "rpym must enter the rpy pipeline");
        require("rpyc".equals(normalize.invoke(null, "rpymc", "text")), "rpymc must enter the rpyc pipeline");
        require("rpyc".equals(normalize.invoke(null, "rpyc", "rpyc")), "rpyc must remain rpyc");
        require("text".equals(normalize.invoke(null, "txt", "text")), "non-RenPy types must be unchanged");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-extension-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenPyExtensionHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    *map(str, stubs),
                    str(SCANNER),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "RenPyExtensionHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_scanner_settles_plugin_call_without_lossy_handler_handoff(self):
        source = SCANNER.read_text("utf-8")
        scan_async = source[
            source.index("public static void scanAsync(") :
            source.index("private static JSObject scan(")
        ]
        self.assertIn("call.resolve(response)", scan_async)
        self.assertIn("call.reject(rejection)", scan_async)
        self.assertNotIn("mainHandler.post", scan_async)
        self.assertNotIn("new Handler(Looper.getMainLooper())", source)

    def test_native_back_handler_is_injected_once_and_delegates_default_back(self):
        handler = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "WorkshopBackHandler.java"
        self.assertTrue(handler.exists(), "WorkshopBackHandler.java must exist")
        source = handler.read_text("utf-8")
        for token in (
            "OnBackPressedCallback",
            "getOnBackPressedDispatcher().addCallback",
            "evaluateJavascript",
            "window.__slgHandleAndroidBack",
            "setEnabled(false)",
            "getOnBackPressedDispatcher().onBackPressed()",
            "setEnabled(true)",
            "activity.runOnUiThread",
        ):
            self.assertIn(token, source)
        builder = BUILDER.read_text("utf-8")
        self.assertIn("BACK_HANDLER_METHOD", builder)
        self.assertIn("enableWorkshopBackHandling", builder)
        self.assertIn("WorkshopBackHandler;->enable", builder)

    def test_back_handler_capacitor_invokes_match_real_base_dex_abi(self):
        self.assertTrue(CAPACITOR_DEX.exists(), "real Capacitor classes3.dex is required")
        self.assertTrue(DEXDUMP.exists(), "Capacitor ABI verification requires dexdump.exe")
        builder = BUILDER.read_text("utf-8")
        method_start = builder.index('BACK_HANDLER_METHOD = """')
        method_end = builder.index('"""', method_start + len('BACK_HANDLER_METHOD = """'))
        method = builder[method_start:method_end]
        invokes = re.findall(
            r"invoke-virtual\s+\{[^}]+\},\s+"
            r"(Lcom/getcapacitor/[^;]+;)->([^\s(]+)(\([^\s]+)",
            method,
        )
        self.assertGreaterEqual(len(invokes), 3)

        completed = subprocess.run(
            [str(DEXDUMP.relative_to(ROOT)), str(CAPACITOR_DEX.relative_to(ROOT))],
            check=True,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        dump = completed.stdout
        for owner, name, descriptor in invokes:
            marker = f"Class descriptor  : '{owner}'"
            start = dump.index(marker)
            end = dump.find("\nClass #", start)
            class_block = dump[start:end if end >= 0 else len(dump)]
            methods = {
                (method_name, method_type)
                for method_name, method_type in re.findall(
                    r"name\s+: '([^']+)'\s+type\s+: '(\([^']+)'",
                    class_block,
                )
            }
            self.assertIn(
                (name, descriptor),
                methods,
                f"{owner}->{name}{descriptor} is absent from real Capacitor ABI",
            )

    def test_native_back_handler_releases_callbacks_and_guards_async_lifecycle(self):
        handler = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "WorkshopBackHandler.java"
        source = handler.read_text("utf-8")
        self.assertRegex(
            source,
            r"Map<ComponentActivity,\s*WeakReference<OnBackPressedCallback>>",
        )

        harness = r"""
import android.webkit.ValueCallback;
import android.webkit.WebView;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.OnBackPressedDispatcher;
import androidx.lifecycle.Lifecycle;
import androidx.lifecycle.LifecycleOwner;
import com.slgtranslator.app.WorkshopBackHandler;

public final class WorkshopBackHandlerHarness {
    public static void main(String[] args) {
        liveFalseDelegatesOnce();
        liveTrueIsConsumed();
        destroyedBeforeJavascriptResultDoesNothing();
        stoppedBeforeJavascriptResultDoesNothing();
        enableIsIdempotent();
    }

    private static void liveFalseDelegatesOnce() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.webView.reply("false");
        require(fixture.dispatcher.defaultBackCount == 1, "live false must delegate once");
    }

    private static void liveTrueIsConsumed() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.webView.reply("true");
        require(fixture.dispatcher.defaultBackCount == 0, "true must consume back");
    }

    private static void destroyedBeforeJavascriptResultDoesNothing() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.activity.destroyed = true;
        fixture.webView.reply("false");
        require(fixture.dispatcher.defaultBackCount == 0, "destroyed activity must not delegate");
    }

    private static void stoppedBeforeJavascriptResultDoesNothing() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.activity.getLifecycle().setCurrentState(Lifecycle.State.CREATED);
        fixture.webView.reply("false");
        require(fixture.dispatcher.defaultBackCount == 0, "stopped activity must not delegate");
    }

    private static void enableIsIdempotent() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        require(fixture.dispatcher.addCount == 1, "enable must install exactly once");
    }

    private static final class Fixture {
        final RecordingDispatcher dispatcher = new RecordingDispatcher();
        final TestActivity activity = new TestActivity(dispatcher);
        final DeferredWebView webView = new DeferredWebView();
    }

    private static final class TestActivity extends ComponentActivity {
        final RecordingDispatcher dispatcher;
        boolean destroyed;

        TestActivity(RecordingDispatcher dispatcher) { this.dispatcher = dispatcher; }
        @Override public void runOnUiThread(Runnable action) { action.run(); }
        @Override public boolean isDestroyed() { return destroyed; }
        @Override public OnBackPressedDispatcher getOnBackPressedDispatcher() { return dispatcher; }
    }

    private static final class RecordingDispatcher extends OnBackPressedDispatcher {
        OnBackPressedCallback callback;
        int addCount;
        int defaultBackCount;

        @Override public void addCallback(LifecycleOwner owner, OnBackPressedCallback callback) {
            this.callback = callback;
            addCount++;
        }
        @Override public void onBackPressed() { defaultBackCount++; }
    }

    private static final class DeferredWebView extends WebView {
        ValueCallback<String> callback;
        @Override public void evaluateJavascript(String script, ValueCallback<String> callback) {
            this.callback = callback;
        }
        void reply(String value) {
            ValueCallback<String> pending = callback;
            callback = null;
            pending.onReceiveValue(value);
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="back-handler-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "WorkshopBackHandlerHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    *map(str, stubs),
                    str(handler),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "WorkshopBackHandlerHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

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
        stale_cleanup = source.index("cleanStalePartials(directory);")
        request_partial = source.index("UUID.randomUUID().toString()")
        self.assertLess(stale_cleanup, request_partial)
        self.assertLess(source.index("partial = null;"), source.index("cleanOldApks(directory, output);"))

    def test_cache_cleanup_removes_interrupted_partial_and_keeps_recent_results(self):
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
        File stalePartial = touch(directory, "interrupted.partial", 1500L);
        Method staleCleanup = InstalledAppSource.class.getDeclaredMethod("cleanStalePartials", File.class);
        staleCleanup.setAccessible(true);
        Method cleanup = InstalledAppSource.class.getDeclaredMethod("cleanOldApks", File.class, File.class);
        cleanup.setAccessible(true);

        File second = touch(directory, "second.apk", 2000L);
        staleCleanup.invoke(null, directory);
        require(!stalePartial.exists(), "a new serialized copy must remove interrupted partials");
        cleanup.invoke(null, directory, second);
        require(first.isFile(), "the previous returned URI must survive the second selection");
        require(second.isFile(), "the current returned URI must survive cleanup");

        File third = touch(directory, "third.apk", 3000L);
        cleanup.invoke(null, directory, third);
        require(!first.exists(), "only finals older than current+previous should be pruned");
        require(second.isFile() && third.isFile(), "current and previous finals must remain");
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

        def dump(path, disassemble=False):
            completed = subprocess.run(
                [
                    str(DEXDUMP.relative_to(ROOT)),
                    *(["-d"] if disassemble else []),
                    str(path.relative_to(ROOT)),
                ],
                check=True,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            return completed.stdout

        plugin_dump = dump(classes6)
        plugin_code = re.sub(r"\s+", "", dump(classes6, disassemble=True))
        helper_dump = dump(classes7)
        helper_code = re.sub(r"\s+", "", dump(classes7, disassemble=True))
        self.assertEqual(plugin_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'selectInstalledApp'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'enableWorkshopBackHandling'"), 1)
        self.assertIn(
            "Lcom/getcapacitor/Plugin;.getActivity:()"
            "Landroidx/appcompat/app/AppCompatActivity;",
            plugin_code,
        )
        self.assertNotIn(
            "Lcom/getcapacitor/Plugin;.getActivity:()Landroid/app/Activity;",
            plugin_code,
        )
        self.assertEqual(
            helper_dump.count("Class descriptor  : 'Lcom/slgtranslator/app/InstalledAppSource;'"),
            1,
        )
        self.assertEqual(helper_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(helper_dump.count("name          : 'selectInstalledApp'"), 1)
        self.assertEqual(
            helper_dump.count("Class descriptor  : 'Lcom/slgtranslator/app/WorkshopBackHandler;'"),
            1,
        )
        self.assertEqual(helper_dump.count("name          : 'enable'"), 1)
        self.assertEqual(helper_dump.count("name          : 'delegateDefaultBack'"), 1)

        actual_methods = set()
        for base_dex in sorted((ROOT / "apk-work" / "extracted").glob("classes*.dex")):
            base_dump = dump(base_dex)
            for block in re.split(r"(?=Class #\d+\s+-)", base_dump):
                owner_match = re.search(r"Class descriptor\s+: '([^']+)'", block)
                if not owner_match:
                    continue
                owner = owner_match.group(1)
                for name, descriptor in re.findall(
                    r"name\s+: '([^']+)'\s+type\s+: '(\([^']+)'",
                    block,
                ):
                    actual_methods.add((owner, name, descriptor))

        # Only inspect code introduced by the back-handler feature.  classes7.dex
        # also contains the older scanner implementation, whose JSArray calls may
        # legally resolve through its org.json superclass and are unrelated here.
        plugin_method = re.search(
            r"com\.slgtranslator\.app\.FileManagerPlugin\."
            r"enableWorkshopBackHandling:.*?(?=catches:)",
            plugin_code,
        )
        self.assertIsNotNone(plugin_method)
        external_invokes = set(
            re.findall(
                r"invoke-(?:virtual|interface|static|direct)(?:/range)?"
                r"\{[^}]*\},"
                r"(Lcom/getcapacitor/[^;]+;)\.([^:]+):(.+?)//method@",
                plugin_method.group(0),
            )
        )
        external_invokes.update(
            re.findall(
                r"invoke-(?:virtual|interface|static|direct)(?:/range)?"
                r"\{[^}]*\},"
                r"(Landroidx/(?:activity|lifecycle)/[^;]+;)"
                r"\.([^:]+):(.+?)//method@",
                helper_code,
            )
        )
        scanner_method = re.search(
            r"com\.slgtranslator\.app\.FastApkScanner\.scanAsync:.*?(?=catches:)",
            helper_code,
        )
        self.assertIsNotNone(scanner_method)
        external_invokes.update(
            re.findall(
                r"invoke-(?:virtual|interface|static|direct)(?:/range)?"
                r"\{[^}]*\},(Lcom/getcapacitor/[^;]+;)"
                r"\.([^:]+):(.+?)//method@",
                scanner_method.group(0),
            )
        )
        self.assertTrue(external_invokes)
        platform_inherited = {
            ("Landroidx/activity/ComponentActivity;", "isDestroyed", "()Z"),
            ("Landroidx/activity/ComponentActivity;", "isFinishing", "()Z"),
        }
        for target in sorted(external_invokes):
            if target in platform_inherited:
                continue
            self.assertIn(
                target,
                actual_methods,
                f"generated external invoke is absent from real base ABI: {target}",
            )


if __name__ == "__main__":
    unittest.main()
