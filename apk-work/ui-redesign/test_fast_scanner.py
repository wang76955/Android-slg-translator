import re
import os
import subprocess
import tempfile
import unittest
import struct
from pathlib import Path
import io
import zipfile


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

THIRD_PARTY = FAST_SCAN / "third-party"

_THIRD_PARTY_CLASSPATH = None

def third_party_classpath() -> str:
    """Return a javac classpath mirroring build_fast_scanner.py."""
    global _THIRD_PARTY_CLASSPATH
    if _THIRD_PARTY_CLASSPATH:
        return _THIRD_PARTY_CLASSPATH
    root = Path(tempfile.mkdtemp(prefix="slg-third-party-classpath-"))
    entries = []
    for aar in sorted(THIRD_PARTY.glob("*.aar")):
        out = root / aar.stem
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(aar) as archive:
            if "classes.jar" not in archive.namelist():
                continue
            with zipfile.ZipFile(io.BytesIO(archive.read("classes.jar"))) as jar:
                for name in jar.namelist():
                    if name.endswith(".class") and not name.startswith(("kotlin/", "kotlinx/", "META-INF/")):
                        target = out / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(jar.read(name))
        if any(out.rglob("*.class")):
            entries.append(str(out))
    entries.extend(str(jar) for jar in sorted(THIRD_PARTY.glob("*.jar")))
    _THIRD_PARTY_CLASSPATH = os.pathsep.join(entries)
    return _THIRD_PARTY_CLASSPATH

RPC2_MAGIC = b"RENPY RPC2"

def pickle_short(value: str) -> bytes:
    payload = value.encode("utf-8")
    if len(payload) > 255:
        raise AssertionError("fixture strings must be short")
    return b"\x8c" + bytes([len(payload)]) + payload

def pickle_int1(value: int) -> bytes:
    return b"\x4b" + bytes([value])

def build_menu_fixture_rpyc() -> bytes:
    """Builds a minimal RPC2 rpyc whose pickle contains a Menu node with
    items labels, dialogue and an attr key that must be filtered."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what") + pickle_short("Hello, world!")
    # Screen text marked with _("...") and a Character("Name") definition
    # (inside a PyCode-style source payload).
    p += pickle_short('_("Start")')
    p += pickle_short('Character("Sky", color = "#fff")')
    p += pickle_short("items")
    # Screen text marked with _("...") and a Character("Name") definition
    # (inside a PyCode-style source payload).
    p += b"\x5d\x94\x28"  # EMPTY_LIST MEMOIZE MARK
    for label, money in (("First choice", False), ("Second{#x}", False),
                         ("$1100", True), ("Fine", False)):
        p += pickle_short(label) + b"\x94"  # label MEMOIZE
        p += b"\x4e"  # NONE condition
        p += b"\x5d\x28\x65"  # EMPTY_LIST MARK APPENDS (empty block)
        p += b"\x87\x94"  # TUPLE3 MEMOIZE
    p += pickle_short("statement_start")  # must be filtered (attr key)
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    pickle_bytes = bytes(p)
    import zlib
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16



def build_source_call_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle embeds source strings containing
    message-style and Ren'Py preference-style function calls. The extractor
    must pull the string-literal arguments (phone message text, preference
    labels) while ignoring variable arguments, empty strings and paths."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what") + pickle_short("Hello, world!")
    # Source payloads: message-style calls (phone) and Ren'Py preference calls.
    p += pickle_short('send_phone_message("Aine", "Hello there.", "aine_dm")')
    p += pickle_short('send_phone_message(sender, message_text, channel_name)')
    p += pickle_short('send_phone_message("Aine", "images/ch2ep1_1042.jpg", "aine_dm", 2)')
    p += pickle_short("_VolumePreference(u\"Music Volume\", 'music', 'config.has_music')")
    p += pickle_short("_SliderPreference(u'Auto-Forward Time', \"afm_time\", 40, 'config.has_afm')")
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16



def build_markup_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle contains Say nodes whose `what`
    values include Ren'Py markup tags with '/' characters ({/i}, {/b}).
    The extractor must NOT treat these as file paths."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what")
    p += pickle_short("I like you a lot. You are good at causing some {i}activity{/i} inside me.")
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    # Second Say with bold markup and a closing slash
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(2)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what")
    p += pickle_short("No, {b}kill{/b} her...")
    p += b"\x75\x86\x62"
    # Third Say with a real path (must be filtered)
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(3)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what")
    p += pickle_short("images/scenes/ch1ep1_001.png")
    p += b"\x75\x86\x62"
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    pickle_bytes = bytes(p)
    import zlib
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16

def build_translate_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle contains a TranslateString node with
    old/new keys plus a Say node with a translated what. The old-only extractor
    must return only the English old key, never the translated what/new."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/tl/chinese/fixture.rpy")
    p += pickle_short("what") + pickle_short("English dialogue")
    p += pickle_short("old") + pickle_short("English original")
    p += pickle_short("new") + pickle_short("\u4e2d\u6587\u539f\u6587")
    p += pickle_short("text") + pickle_short("English screen text")
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


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
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
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
            [str(DEXDUMP), str(CAPACITOR_DEX.relative_to(ROOT))],
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
                    "-classpath",
                    third_party_classpath(),
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
            'installedApksDir(context)',
            "getExternalFilesDir(null)",
            '"installed-apks"',
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
            "listSaveGameApps",
            "InstalledAppSource;->listSaveGameApps",
        ):
            self.assertIn(token, builder)
        self.assertIn("bridge_counts == [0] * len(INSTALLED_APP_METHODS)", builder)
        self.assertIn("bridge_counts != [1] * len(INSTALLED_APP_METHODS)", builder)
        self.assertIn("patched.count(signature) != 1 or patched.count(delegate) != 1", builder)
        self.assertIn("Expected exactly one listApkEntries method", builder)
        self.assertEqual(builder.count('".method public final listInstalledApps('), 2)
        self.assertEqual(builder.count('".method public final selectInstalledApp('), 2)
        self.assertEqual(builder.count('".method public final listSaveGameApps('), 2)

    def test_save_game_list_scans_renpy_save_dirs_without_all_apps(self):
        source = INSTALLED_APPS.read_text("utf-8")
        self.assertIn("public static void listSaveGameApps(", source)
        listing = java_block_after(source, "private static void listSaveGameAppsOnWorker(")
        self.assertIn('new File(android.os.Environment.getExternalStorageDirectory(), "Documents")', listing)
        self.assertIn('new File(documents, "RenPy_Saves")', listing)
        self.assertIn('packageName.contains(".")', listing)
        self.assertNotIn("queryLauncherApps", listing)
        self.assertNotIn("queryIntentActivities", listing)
        self.assertNotIn("QUERY_ALL_PACKAGES", source)
        builder = BUILDER.read_text("utf-8")
        self.assertIn(".method public final listSaveGameApps(Lcom/getcapacitor/PluginCall;)V", builder)
        self.assertIn("Lcom/slgtranslator/app/InstalledAppSource;->listSaveGameApps", builder)

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
                    "-classpath",
                    third_party_classpath(),
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
                    str(DEXDUMP),
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
        self.assertEqual(plugin_dump.count("name          : 'listSaveGameApps'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'enableWorkshopBackHandling'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'listSaveArchives'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'importSaveBackup'"), 1)
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
        self.assertEqual(helper_dump.count("name          : 'listSaveGameApps'"), 1)
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


    def test_language_menu_support_rewrites_expendable_slot(self):
        support = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "LanguageMenuSupport.java"
        self.assertTrue(support.exists(), "LanguageMenuSupport.java must exist")
        source = support.read_text("utf-8")
        for token in (
            "injectTranslatorMenu",
            "rewriteButton",
            "rewriteApkMenu",
            'Language(\\"',
            "translatorLang",
            "\\u7ffb\\u8bd1\\u6587\\u672c",
            "0x95",
            "STATUS_ALREADY",
            "menuHasLanguage",
            'result.put("ready"',
            "STATUS_ALREADY",
            "menuHasLanguage",
            'result.put("ready"',
        ):
            self.assertIn(token, source)
        self.assertNotIn("spliceButton", source)
        builder = BUILDER.read_text("utf-8")
        for token in (
            "INJECT_MENU_SIGNATURE",
            "LanguageMenuSupport;->injectTranslatorMenu",
        ):
            self.assertIn(token, builder)

    def test_rpyc_text_extractor_registers_structural_reading_bridge(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        self.assertTrue(extractor.exists(), "RpycTextExtractor.java must exist")
        source = extractor.read_text("utf-8")
        for token in (
            "extractTexts", "walk", "MEMOIZE", "BINGET", "what", "caption",
            "SHORT_BINUNICODE", "BINUNICODE",
        ):
            self.assertIn(token, source)
        scanner = SCANNER.read_text("utf-8")
        for token in ("readRenpyTexts", "RpycTextExtractor.extractTexts", "RPYC_STRING\\t"):
            self.assertIn(token, scanner)
        builder = BUILDER.read_text("utf-8")
        for token in ("READ_TEXTS_SIGNATURE", "FastApkScanner;->readRenpyTexts"):
            self.assertIn(token, builder)

    def test_rpyc_extractor_keeps_menu_choices_and_single_token_labels(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        for token in (
            "itemsMode", "afterTuple3", "isChoiceLabel", "0x87", "TUPLE3",
            "items\".equals(lastKey)", 
        ):
            self.assertIn(token, source)
        scanner = SCANNER.read_text("utf-8")
        for token in ('replace("\\n", "\\\\n")', 'RPYC_STRING\\t'):
            self.assertIn(token, scanner)

        fixture = build_menu_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class MenuExtractorHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("Hello, world!"), "dialogue must be extracted");
        require(set.contains("First choice"), "first menu label must be extracted");
        require(set.contains("Start"), "_() marked screen text must be extracted");
        require(set.contains("Sky"), "Character name must be extracted");
        require(set.contains("Second{#x}"), "tagged menu label must be extracted");
        require(set.contains("$1100"), "money menu label must be extracted");
        require(set.contains("Fine"), "single-token capitalized label must be extracted");
        require(!set.contains("statement_start"), "attr key must not be treated as a label");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="menu-extractor-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "MenuExtractorHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "MenuExtractorHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_extracts_source_call_argument_texts(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        self.assertIn("collectSourceCallTexts", source)

        fixture = build_source_call_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class SourceCallHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("Hello, world!"), "dialogue must still be extracted");
        require(set.contains("Hello there."), "phone message text must be extracted");
        require(set.contains("Music Volume"), "preference label must be extracted");
        require(set.contains("Auto-Forward Time"), "slider preference label must be extracted");
        require(!set.contains("sender"), "variable argument must not be extracted");
        require(!set.contains("message_text"), "variable argument must not be extracted");
        require(!set.contains("images/ch2ep1_1042.jpg"), "path argument must not be extracted");
        require(!set.contains("aine_dm"), "channel argument must not be extracted");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="source-call-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "SourceCallHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SourceCallHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_old_only_mode_skips_translated_what_and_new(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        self.assertIn("onlyOld", source)

        fixture = build_translate_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class OldOnlyHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes, true);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("English original"), "old key must be extracted");
        require(!set.contains("English dialogue"), "translated what must not be extracted");
        require(!set.contains("English screen text"), "screen text must not be extracted");
        require(!set.contains("\u4e2d\u6587\u539f\u6587"), "new value must not be extracted");
        // Full mode keeps dialogue and screen text as before.
        List<String> full = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> fullSet = new java.util.HashSet<>(full);
        require(fullSet.contains("English dialogue"), "full mode keeps dialogue");
        require(fullSet.contains("English screen text"), "full mode keeps screen text");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="old-only-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "OldOnlyHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "OldOnlyHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    
    def test_rpyc_extractor_keeps_renpy_markup_dialogue(self):
        """Dialogue containing Ren'Py markup tags like {/i} and {/b} must
        not be rejected as file paths.  The '/' inside markup tags is not
        a path separator."""
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        self.assertIn("pathCheck", source, "isUserText must strip markup before path check")

        fixture = build_markup_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class MarkupExtractorHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("I like you a lot. You are good at causing some {i}activity{/i} inside me."),
                "italic markup dialogue must be extracted");
        require(set.contains("No, {b}kill{/b} her..."),
                "bold markup dialogue must be extracted");
        require(!set.contains("images/scenes/ch1ep1_001.png"),
                "real file path must still be filtered");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="markup-extractor-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "MarkupExtractorHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "MarkupExtractorHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_fast_scanner_reads_translation_entries_in_old_only_mode(self):
        scanner = SCANNER.read_text("utf-8")
        self.assertIn("extractTexts(bytes, true)", scanner)
        self.assertIn("x-tl", scanner)

    def test_cleanup_storage_keeps_newest_patch_and_selection_source(self):
        cleanup = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "CleanupSupport.java"
        self.assertTrue(cleanup.exists(), "CleanupSupport.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in (
            "CLEANUP_SIGNATURE", "CLEANUP_DELEGATE", "CleanupSupport;->cleanupStorage",
        ):
            self.assertIn(token, builder)
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.CleanupSupport;
import java.io.File;

public final class CleanupHarness {
    static final class FakeContext extends Context {
        File external;
        @Override public File getExternalFilesDir(String type) { return external; }
    }
    static final class CapturingCall extends PluginCall {
        String keepUri;
        String rejected;
        @Override public String getString(String key) {
            return "keepUri".equals(key) ? keepUri : null;
        }
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
    }

    public static void main(String[] args) throws Exception {
        File base = new File(args[0]);
        File installed = new File(base, "installed-apks"); installed.mkdirs();
        File keep = new File(installed, "keep.apk"); require(keep.createNewFile(), "create keep");
        File staleSource = new File(installed, "stale.apk"); require(staleSource.createNewFile(), "create stale");
        File output = new File(base, "SLG-Translator-Output"); output.mkdirs();
        File patchOld = new File(output, "patch-old.apk"); require(patchOld.createNewFile(), "create old patch");
        patchOld.setLastModified(1000L);
        File patchNew = new File(output, "patch-new.apk"); require(patchNew.createNewFile(), "create new patch");
        patchNew.setLastModified(3000L);
        FakeContext context = new FakeContext();
        context.external = base;
        CapturingCall call = new CapturingCall();
        call.keepUri = keep.toURI().toString();
        CleanupSupport.cleanupStorage(context, call);
        require(call.rejected == null, "cleanup must resolve: " + call.rejected);
        require(!staleSource.exists(), "stale installed copy must be deleted");
        require(keep.exists(), "current selection source must be kept");
        require(!patchOld.exists(), "old patch must be deleted");
        require(patchNew.exists(), "newest patch must be kept");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="cleanup-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CleanupHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            fixture.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CleanupHarness", str(fixture)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_cleanup_storage_deletes_other_games_patch_by_package(self):
        """Patch APKs whose package differs from the selected game are
        deleted (their patches are already installed); the selected game's
        own patch is kept."""
        cleanup = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "CleanupSupport.java"
        source = cleanup.read_text("utf-8")
        self.assertIn("packageName", source)
        self.assertIn("packageNameOf", source)
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.CleanupSupport;
import java.io.File;

public final class CleanupPackageHarness {
    static final class FakeContext extends Context {
        File external;
        @Override public File getExternalFilesDir(String type) { return external; }
    }
    static final class CapturingCall extends PluginCall {
        String keepUri, packageName;
        String rejected;
        @Override public String getString(String key) {
            if ("keepUri".equals(key)) return keepUri;
            if ("packageName".equals(key)) return packageName;
            return null;
        }
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
    }
    public static void main(String[] args) throws Exception {
        File base = new File(args[0]);
        File installed = new File(base, "installed-apks"); installed.mkdirs();
        File keep = new File(installed, "keep.apk"); require(keep.createNewFile(), "create keep");
        File output = new File(base, "SLG-Translator-Output"); output.mkdirs();
        File patchOther = new File(output, "patch-other.apk");
        writeManifest(patchOther, "com.other.game");
        File patchCurrent = new File(output, "patch-current.apk");
        writeManifest(patchCurrent, "com.current.game");
        FakeContext context = new FakeContext();
        context.external = base;
        CapturingCall call = new CapturingCall();
        call.keepUri = keep.toURI().toString();
        call.packageName = "com.current.game";
        CleanupSupport.cleanupStorage(context, call);
        require(call.rejected == null, "cleanup must resolve: " + call.rejected);
        require(!patchOther.exists(), "other game patch must be deleted");
        require(patchCurrent.exists(), "current game patch must be kept");
        require(keep.exists(), "current selection source must be kept");
    }
    static void writeManifest(File apk, String pkg) throws Exception {
        java.util.zip.ZipOutputStream out = new java.util.zip.ZipOutputStream(new java.io.FileOutputStream(apk));
        out.putNextEntry(new java.util.zip.ZipEntry("AndroidManifest.xml"));
        byte[] pkgBytes = pkg.getBytes("UTF-16LE");
        out.write(new byte[]{1, 0, 2, 0});
        out.write(pkgBytes);
        out.write(new byte[]{0, 0});
        out.close();
    }
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="cleanup-pkg-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CleanupPackageHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            fixture.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CleanupPackageHarness", str(fixture)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


    def test_cleanup_storage_removes_interrupted_partials_in_installed_apks(self):
        """Cleanup must remove .partial/.tmp leftovers inside installed-apks."""
        cleanup = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "CleanupSupport.java"
        self.assertTrue(cleanup.exists(), "CleanupSupport.java must exist")
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.CleanupSupport;
import java.io.File;

public final class CleanupPartialHarness {
    static final class FakeContext extends Context {
        File external;
        @Override public File getExternalFilesDir(String type) { return external; }
    }
    static final class CapturingCall extends PluginCall {
        String keepUri;
        String rejected;
        @Override public String getString(String key) {
            return "keepUri".equals(key) ? keepUri : null;
        }
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
    }

    public static void main(String[] args) throws Exception {
        File base = new File(args[0]);
        File installed = new File(base, "installed-apks"); installed.mkdirs();
        File keep = new File(installed, "keep.apk"); require(keep.createNewFile(), "create keep");
        File stalePartial = new File(installed, "keep.apk.uuid.partial"); require(stalePartial.createNewFile(), "create partial");
        File staleTmp = new File(installed, "stale.tmp"); require(staleTmp.createNewFile(), "create tmp");
        File output = new File(base, "SLG-Translator-Output"); output.mkdirs();
        FakeContext context = new FakeContext();
        context.external = base;
        CapturingCall call = new CapturingCall();
        call.keepUri = keep.toURI().toString();
        CleanupSupport.cleanupStorage(context, call);
        require(call.rejected == null, "cleanup must resolve: " + call.rejected);
        require(keep.exists(), "current selection source must be kept");
        require(!stalePartial.exists(), "interrupted partial copy must be removed");
        require(!staleTmp.exists(), "interrupted tmp file must be removed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="cleanup-partial-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CleanupPartialHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            fixture.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CleanupPartialHarness", str(fixture)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_protocol_escapes_backslashes_before_newlines(self):
        """The RPYC_STRING bridge must not conflate literal backslash-n with a real newline."""
        scanner = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java"
        source = scanner.read_text("utf-8")
        escape_start = source.index("String escaped = text.replace")
        escape_block = source[escape_start:escape_start + 500]
        backslash_idx = escape_block.index('text.replace("\\\\", "\\\\\\\\")')
        newline_idx = escape_block.index('.replace("\\n", "\\\\n")')
        self.assertLess(backslash_idx, newline_idx, "backslash must be escaped before newline")

    def test_save_patched_apk_failure_cleans_media_store_entry(self):
        """A failed MediaStore copy must remove the half-written download row."""
        install = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstallSupport.java"
        self.assertTrue(install.exists(), "InstallSupport.java must exist")
        harness = r"""
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.InstallSupport;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

public final class InstallSaveFailureHarness {
    static final class FakeUri extends Uri {}
    static final class FakeResolver extends ContentResolver {
        int deleteCalls = 0;
        @Override public Uri insert(Uri uri, ContentValues values) { return new FakeUri(); }
        @Override public OutputStream openOutputStream(Uri uri) {
            return new OutputStream() {
                @Override public void write(int b) throws IOException { throw new IOException("disk full"); }
            };
        }
        @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
            deleteCalls++;
            return 1;
        }
    }
    static final class FakeContext extends Context {
        FakeResolver resolver;
        @Override public ContentResolver getContentResolver() { return resolver; }
    }
    static final class CapturingCall extends PluginCall {
        String rejected;
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
        String requestedPath;
        @Override public String getString(String key) {
            return "path".equals(key) ? requestedPath : null;
        }
    }

    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        try (FileOutputStream out = new FileOutputStream(source)) {
            out.write(new byte[131072]);
        }
        FakeContext context = new FakeContext();
        context.resolver = new FakeResolver();
        CapturingCall call = new CapturingCall();
        call.requestedPath = source.getAbsolutePath();
        InstallSupport.savePatchedApkToDownloads(context, call);
        require(call.rejected != null, "copy failure must reject the call");
        require(context.resolver.deleteCalls >= 1, "failed media store copy must delete the inserted row");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="install-save-failure-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "InstallSaveFailureHarness.java"
            classes = temporary_path / "classes"
            source = temporary_path / "patch.apk"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "InstallSaveFailureHarness", str(source)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_package_installer_session_bridge_is_injected(self):
        """installApk must delegate to PackageInstallerSupport.installViaSession
        so multi-GB patched APKs install without OPPO FileProvider corruption."""
        support = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "PackageInstallerSupport.java"
        self.assertTrue(support.exists(), "PackageInstallerSupport.java must exist")
        source = support.read_text("utf-8")
        for token in ("installViaSession", "PackageInstaller.SessionParams", "MODE_FULL_INSTALL",
                      "session.openWrite", "session.commit", "ACTION_PACKAGE_INSTALLED"):
            self.assertIn(token, source)
        builder = BUILDER.read_text("utf-8")
        self.assertIn("INSTALL_APK_SIGNATURE", builder)
        self.assertIn("INSTALL_APK_PATTERN", builder)
        self.assertIn("PackageInstallerSupport;->installViaSession", builder)
        self.assertIn("installViaSession(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V", builder)


    def test_save_transfer_copies_and_counts_files(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in (
            "SAVE_BACKUP_SIGNATURE", "SAVE_RESTORE_SIGNATURE", "SAVE_LIST_SIGNATURE",
            "SaveTransfer;->backupSaves", "SaveTransfer;->restoreSaves", "SaveTransfer;->listSaveBackups",
        ):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import java.io.File;
import java.lang.reflect.Method;

public final class SaveTransferHarness {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        File dest = new File(args[1]);
        File nested = new File(source, "game"); nested.mkdirs();
        File slot = new File(source, "auto-1.save"); require(slot.createNewFile(), "create save");
        File inner = new File(nested, "meta.bin"); require(inner.createNewFile(), "create meta");
        Method copyTree = SaveTransfer.class.getDeclaredMethod("copyTree", File.class, File.class);
        copyTree.setAccessible(true);
        Method countFiles = SaveTransfer.class.getDeclaredMethod("countFiles", File.class);
        countFiles.setAccessible(true);
        int copied = (Integer) copyTree.invoke(null, source, dest);
        require(copied == 2, "two files must be copied: " + copied);
        require(new File(dest, "auto-1.save").isFile(), "save slot copied");
        require(new File(dest, "game/meta.bin").isFile(), "nested file copied");
        require((Integer) countFiles.invoke(null, dest) == 2, "count must match");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-transfer-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveTransferHarness.java"
            classes = temporary_path / "classes"
            source_dir = temporary_path / "source"
            dest_dir = temporary_path / "dest"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            source_dir.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveTransferHarness", str(source_dir), str(dest_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


    def test_save_export_zips_directory_and_counts_files(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in ("SAVE_EXPORT_SIGNATURE", "SaveTransfer;->exportSavesToDownloads"):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import java.io.File;
import java.lang.reflect.Method;
import java.util.zip.ZipFile;

public final class SaveExportHarness {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        File zip = new File(args[1]);
        File nested = new File(source, "game"); nested.mkdirs();
        File slot = new File(source, "auto-1.save"); require(slot.createNewFile(), "create save");
        File inner = new File(nested, "meta.bin"); require(inner.createNewFile(), "create meta");
        Method zipTree = SaveTransfer.class.getDeclaredMethod("zipDirectory", File.class, File.class);
        zipTree.setAccessible(true);
        int zipped = (Integer) zipTree.invoke(null, source, zip);
        require(zipped == 2, "two files must be zipped: " + zipped);
        try (ZipFile archive = new ZipFile(zip)) {
            require(archive.getEntry("auto-1.save") != null, "save slot zipped");
            require(archive.getEntry("game/meta.bin") != null, "nested file zipped");
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-export-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveExportHarness.java"
            classes = temporary_path / "classes"
            source_dir = temporary_path / "source"
            zip_file = temporary_path / "backup.zip"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            source_dir.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveExportHarness", str(source_dir), str(zip_file)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_save_share_backup_bridge_contract(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in ("SAVE_SHARE_SIGNATURE", "SaveTransfer;->shareSaveBackup"):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import android.content.Context;
import com.getcapacitor.PluginCall;
import java.lang.reflect.Method;

public final class SaveShareHarness {
    public static void main(String[] args) throws Exception {
        Method share = SaveTransfer.class.getDeclaredMethod("shareSaveBackup", Context.class, PluginCall.class);
        require(share != null, "shareSaveBackup bridge method must exist");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-share-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveShareHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveShareHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_save_import_extracts_shared_archive_safely(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        source = transfer.read_text("utf-8")
        for token in (
            "listSaveArchives", "importSaveBackup", "collectArchives", "extractZip",
            "packageFromName", "Environment.getExternalStoragePublicDirectory",
            "name.contains(\"..\")", "canonicalTarget.getPath().startsWith(rootPrefix)",
            "deleteSaveArchive", "invalid save archive path",
        ):
            self.assertIn(token, source)
        builder = BUILDER.read_text("utf-8")
        for token in (
            "SAVE_ARCHIVES_SIGNATURE", "SAVE_IMPORT_SIGNATURE",
            "SaveTransfer;->listSaveArchives", "SaveTransfer;->importSaveBackup",
            "SAVE_ARCHIVE_DELETE_SIGNATURE", "SaveTransfer;->deleteSaveArchive",
        ):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class SaveImportHarness {
    public static void main(String[] args) throws Exception {
        File zipFile = new File(args[0]);
        File dest = new File(args[1]);
        File unsafeZip = new File(args[2]);
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(zipFile))) {
            write(zip, "com.example.game/auto-1.save", "slot");
            write(zip, "com.example.game/game/meta.bin", "meta");
        }
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(unsafeZip))) {
            write(zip, "../evil.txt", "bad");
        }
        Method extract = SaveTransfer.class.getDeclaredMethod("extractZip", File.class, File.class);
        extract.setAccessible(true);
        int count = (Integer) extract.invoke(null, zipFile, dest);
        require(count == 2, "extracted file count");
        require(new File(dest, "auto-1.save").isFile(), "root stripped");
        require(new File(dest, "game/meta.bin").isFile(), "nested preserved");
        File unsafeDest = new File(dest, "unsafe");
        try {
            extract.invoke(null, unsafeZip, unsafeDest);
            require(false, "unsafe zip must be rejected");
        } catch (InvocationTargetException error) {
            require(error.getCause() instanceof IOException, "unsafe zip rejection reason");
        }
        Method packageName = SaveTransfer.class.getDeclaredMethod("packageFromName", String.class);
        packageName.setAccessible(true);
        Object parsed = packageName.invoke(null, "com.example.game-20260805-120000.zip");
        require("com.example.game".equals(parsed), "package parsed from shared archive name");
        Object shared = packageName.invoke(null, "com.example.game-20260805-120000-20260806-130000.zip");
        require("com.example.game".equals(shared), "package parsed from shared backup name with two stamps");
        Object renamed = packageName.invoke(null, "renamed.zip");
        require(renamed == null, "renamed archive falls back to manual game selection");
    }

    private static void write(ZipOutputStream zip, String name, String content) throws Exception {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes("UTF-8"));
        zip.closeEntry();
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-import-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveImportHarness.java"
            classes = temporary_path / "classes"
            zip_file = temporary_path / "shared.zip"
            dest_dir = temporary_path / "dest"
            unsafe_zip = temporary_path / "unsafe.zip"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveImportHarness", str(zip_file), str(dest_dir), str(unsafe_zip)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


    def test_delete_backup_removes_directory_tree(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in ("SAVE_DELETE_SIGNATURE", "SaveTransfer;->deleteBackup"):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import android.content.Context;
import com.getcapacitor.PluginCall;
import java.io.File;
import java.lang.reflect.Method;

public final class SaveDeleteHarness {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        File dest = new File(args[1]);
        File nested = new File(source, "game"); nested.mkdirs();
        File slot = new File(source, "auto-1.save"); require(slot.createNewFile(), "create save");
        File inner = new File(nested, "meta.bin"); require(inner.createNewFile(), "create meta");
        Method copyTree = SaveTransfer.class.getDeclaredMethod("copyTree", File.class, File.class);
        copyTree.setAccessible(true);
        Method deleteTree = SaveTransfer.class.getDeclaredMethod("deleteTree", File.class);
        deleteTree.setAccessible(true);
        require(SaveTransfer.class.getDeclaredMethod("deleteBackup", Context.class, PluginCall.class) != null,
            "deleteBackup bridge method must exist");
        int copied = (Integer) copyTree.invoke(null, source, dest);
        require(copied == 2, "two files must be copied: " + copied);
        int deleted = (Integer) deleteTree.invoke(null, dest);
        require(deleted == 2, "two files must be deleted: " + deleted);
        require(!dest.exists(), "backup directory must be removed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-delete-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveDeleteHarness.java"
            classes = temporary_path / "classes"
            source_dir = temporary_path / "source"
            dest_dir = temporary_path / "dest"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            source_dir.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveDeleteHarness", str(source_dir), str(dest_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


if __name__ == "__main__":
    unittest.main()
