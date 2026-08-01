from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".tools"
ANDROID_TOOLS = TOOLS / "android-15"
JAVA_HOME = TOOLS / "jdk-17" / "jdk-17.0.19+10"
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"
D8 = ANDROID_TOOLS / "d8.bat"
APKTOOL = TOOLS / "apktool" / "apktool_3.0.2.jar"
BASE_APK = ROOT / "apk-work" / "com.slgtranslator.app-base.apk"
SOURCE_DEX = ROOT / "apk-work" / "extracted" / "classes6.dex"
HERE = Path(__file__).resolve().parent
GENERATED = HERE / "generated"
SOURCE_SOURCES = sorted((HERE / "src").rglob("*.java"))
STUB_SOURCES = sorted((HERE / "stubs").rglob("*.java"))

METHOD_PATTERN = re.compile(
    r"(?ms)^\.method public final listApkEntries\(Lcom/getcapacitor/PluginCall;\)V\r?\n.*?^\.end method"
)
DELEGATING_METHOD = """.method public final listApkEntries(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 2
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    const-string v0, "uri"
    invoke-virtual {p1, v0}, Lcom/getcapacitor/PluginCall;->getString(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0

    if-nez v0, :has_uri
    const-string v0, "uri required"
    invoke-virtual {p1, v0}, Lcom/getcapacitor/PluginCall;->reject(Ljava/lang/String;)V
    return-void

    :has_uri
    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v1
    invoke-static {v1, v0, p0, p1}, Lcom/slgtranslator/app/FastApkScanner;->scanAsync(Landroid/content/Context;Ljava/lang/String;Ljava/lang/Object;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""

INSTALLED_APP_METHODS = (
    (
        ".method public final listInstalledApps(Lcom/getcapacitor/PluginCall;)V",
        "Lcom/slgtranslator/app/InstalledAppSource;->listInstalledApps",
        """.method public final listInstalledApps(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstalledAppSource;->listInstalledApps(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
    (
        ".method public final selectInstalledApp(Lcom/getcapacitor/PluginCall;)V",
        "Lcom/slgtranslator/app/InstalledAppSource;->selectInstalledApp",
        """.method public final selectInstalledApp(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstalledAppSource;->selectInstalledApp(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
)

BACK_HANDLER_SIGNATURE = ".method public final enableWorkshopBackHandling(Lcom/getcapacitor/PluginCall;)V"
BACK_HANDLER_DELEGATE = "Lcom/slgtranslator/app/WorkshopBackHandler;->enable"
BACK_HANDLER_METHOD = """.method public final enableWorkshopBackHandling(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 3
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/getcapacitor/Plugin;->getActivity()Landroidx/appcompat/app/AppCompatActivity;
    move-result-object v0
    invoke-virtual {p0}, Lcom/getcapacitor/Plugin;->getBridge()Lcom/getcapacitor/Bridge;
    move-result-object v1
    invoke-virtual {v1}, Lcom/getcapacitor/Bridge;->getWebView()Landroid/webkit/WebView;
    move-result-object v1
    invoke-static {v0, v1}, Lcom/slgtranslator/app/WorkshopBackHandler;->enable(Landroid/app/Activity;Landroid/webkit/WebView;)V

    new-instance v2, Lcom/getcapacitor/JSObject;
    invoke-direct {v2}, Lcom/getcapacitor/JSObject;-><init>()V
    invoke-virtual {p1, v2}, Lcom/getcapacitor/PluginCall;->resolve(Lcom/getcapacitor/JSObject;)V
    return-void
.end method"""

RENDER_GONE_SIGNATURE = (
    ".method public onRenderProcessGone(Landroid/webkit/WebView;Landroid/webkit/RenderProcessGoneDetail;)Z"
)
RENDER_GONE_MARKER = "# workshop: keep app alive on renderer death"
RENDER_GONE_PATTERN = re.compile(
    r"(?ms)^\.method public onRenderProcessGone\(Landroid/webkit/WebView;Landroid/webkit/RenderProcessGoneDetail;\)Z\r?\n.*?^\.end method"
)
RENDER_GONE_METHOD = """.method public onRenderProcessGone(Landroid/webkit/WebView;Landroid/webkit/RenderProcessGoneDetail;)Z
    .locals 2
    .param p1, "view"    # Landroid/webkit/WebView;
    .param p2, "detail"    # Landroid/webkit/RenderProcessGoneDetail;

    # workshop: keep app alive on renderer death
    const/4 v0, 0x1

    :try_start_0
    invoke-virtual {p1}, Landroid/webkit/WebView;->reload()V
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    return v0

    :catch_0
    move-exception v1
    return v0
.end method"""

SAVE_APK_SIGNATURE = ".method public final savePatchedApkToDownloads(Lcom/getcapacitor/PluginCall;)V"
SAVE_APK_DELEGATE = "Lcom/slgtranslator/app/InstallSupport;->savePatchedApkToDownloads"
SAVE_APK_METHOD = """.method public final savePatchedApkToDownloads(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstallSupport;->savePatchedApkToDownloads(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
LIST_PATCHES_SIGNATURE = ".method public final listPatchedApks(Lcom/getcapacitor/PluginCall;)V"
LIST_PATCHES_DELEGATE = "Lcom/slgtranslator/app/InstallSupport;->listPatchedApks"
LIST_PATCHES_METHOD = """.method public final listPatchedApks(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstallSupport;->listPatchedApks(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
INJECT_MENU_SIGNATURE = ".method public final injectTranslatorMenu(Lcom/getcapacitor/PluginCall;)V"
INJECT_MENU_DELEGATE = "Lcom/slgtranslator/app/LanguageMenuSupport;->injectTranslatorMenu"
INJECT_MENU_METHOD = """.method public final injectTranslatorMenu(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p0, p1}, Lcom/slgtranslator/app/LanguageMenuSupport;->injectTranslatorMenu(Landroid/content/Context;Ljava/lang/Object;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""

ANDROID_NAMESPACE = "http://schemas.android.com/apk/res/android"
ANDROID_NAME = f"{{{ANDROID_NAMESPACE}}}name"


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, check=True, env=env)


def build_helper_dex(build: Path, env: dict[str, str]) -> Path:
    stubs = build / "stub-classes"
    helper = build / "helper-classes"
    dex_output = build / "helper-dex"
    stubs.mkdir(parents=True)
    helper.mkdir(parents=True)
    dex_output.mkdir(parents=True)
    common = ["-source", "8", "-target", "8", "-encoding", "UTF-8"]
    run(
        [
            str(JAVAC),
            *common,
            "-d",
            str(stubs),
            *map(str, STUB_SOURCES),
        ],
        env,
    )
    run(
        [
            str(JAVAC),
            *common,
            "-classpath",
            str(stubs),
            "-d",
            str(helper),
            *map(str, SOURCE_SOURCES),
        ],
        env,
    )
    classes = sorted(map(str, helper.rglob("*.class")))
    run(
        [
            str(D8),
            "--min-api",
            "24",
            "--classpath",
            str(stubs),
            "--output",
            str(dex_output),
            *classes,
        ],
        env,
    )
    return dex_output / "classes.dex"


def create_overlay_apk(output: Path) -> None:
    replacement = SOURCE_DEX.read_bytes()
    with zipfile.ZipFile(BASE_APK, "r") as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            data = replacement if item.filename == "classes6.dex" else source.read(item.filename)
            target.writestr(item, data)


def patch_launcher_queries(manifest: Path) -> None:
    ET.register_namespace("android", ANDROID_NAMESPACE)
    tree = ET.parse(manifest)
    root = tree.getroot()
    queries = root.find("queries")
    if queries is None:
        queries = ET.Element("queries")
        application = root.find("application")
        position = list(root).index(application) if application is not None else len(root)
        root.insert(position, queries)
    for intent in queries.findall("intent"):
        actions = {item.get(ANDROID_NAME) for item in intent.findall("action")}
        categories = {item.get(ANDROID_NAME) for item in intent.findall("category")}
        if (
            "android.intent.action.MAIN" in actions
            and "android.intent.category.LAUNCHER" in categories
        ):
            tree.write(manifest, encoding="utf-8", xml_declaration=True)
            return
    intent = ET.SubElement(queries, "intent")
    ET.SubElement(intent, "action", {ANDROID_NAME: "android.intent.action.MAIN"})
    ET.SubElement(intent, "category", {ANDROID_NAME: "android.intent.category.LAUNCHER"})
    tree.write(manifest, encoding="utf-8", xml_declaration=True)


def patch_bridge_webview_client(decoded: Path) -> None:
    candidates = list(decoded.glob("smali_classes3/com/getcapacitor/BridgeWebViewClient.smali"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one BridgeWebViewClient smali file, found {len(candidates)}")
    smali = candidates[0]
    original = smali.read_text("utf-8")
    existing = RENDER_GONE_PATTERN.findall(original)
    if len(existing) != 1:
        raise RuntimeError(f"Expected exactly one onRenderProcessGone method, found {len(existing)}")
    if RENDER_GONE_MARKER in existing[0]:
        return
    patched, replacements = RENDER_GONE_PATTERN.subn(RENDER_GONE_METHOD, original, count=1)
    if replacements != 1 or patched.count(RENDER_GONE_SIGNATURE) != 1:
        raise RuntimeError("Failed to patch BridgeWebViewClient.onRenderProcessGone")
    smali.write_text(patched, "utf-8", newline="\n")


def patch_plugin_dex(build: Path, env: dict[str, str]) -> tuple[Path, Path, Path]:
    overlay = build / "scanner-source.apk"
    decoded = build / "decoded"
    create_overlay_apk(overlay)
    run(
        [
            str(JAVA),
            "-jar",
            str(APKTOOL),
            "d",
            "-f",
            "--no-assets",
            "--all-src",
            "-o",
            str(decoded),
            str(overlay),
        ],
        env,
    )
    patch_launcher_queries(decoded / "AndroidManifest.xml")
    candidates = list(decoded.glob("smali_classes6/com/slgtranslator/app/FileManagerPlugin.smali"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one FileManagerPlugin smali file, found {len(candidates)}")
    smali = candidates[0]
    original = smali.read_text("utf-8")
    existing_entrypoints = METHOD_PATTERN.findall(original)
    if len(existing_entrypoints) != 1:
        raise RuntimeError(f"Expected exactly one listApkEntries method, found {len(existing_entrypoints)}")
    patched, replacements = METHOD_PATTERN.subn(DELEGATING_METHOD, original, count=1)
    if replacements != 1:
        raise RuntimeError(f"Expected to patch one listApkEntries method, patched {replacements}")
    bridge_counts = [patched.count(signature) for signature, _, _ in INSTALLED_APP_METHODS]
    if bridge_counts == [0] * len(INSTALLED_APP_METHODS):
        patched = patched.rstrip() + "\n\n" + "\n\n".join(
            method for _, _, method in INSTALLED_APP_METHODS
        ) + "\n"
    elif bridge_counts != [1] * len(INSTALLED_APP_METHODS):
        raise RuntimeError(f"Installed app bridge methods are partially or repeatedly injected: {bridge_counts}")
    for signature, delegate, _ in INSTALLED_APP_METHODS:
        if patched.count(signature) != 1 or patched.count(delegate) != 1:
            raise RuntimeError(f"Expected exactly one valid installed app bridge for {signature}")
    back_count = patched.count(BACK_HANDLER_SIGNATURE)
    if back_count == 0:
        patched = patched.rstrip() + "\n\n" + BACK_HANDLER_METHOD + "\n"
    elif back_count != 1:
        raise RuntimeError(f"Workshop back bridge is repeatedly injected: {back_count}")
    if patched.count(BACK_HANDLER_SIGNATURE) != 1 or patched.count(BACK_HANDLER_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid workshop back bridge")
    save_apk_count = patched.count(SAVE_APK_SIGNATURE)
    if save_apk_count == 0:
        patched = patched.rstrip() + "\n\n" + SAVE_APK_METHOD + "\n"
    elif save_apk_count != 1:
        raise RuntimeError(f"Save APK bridge is repeatedly injected: {save_apk_count}")
    if patched.count(SAVE_APK_SIGNATURE) != 1 or patched.count(SAVE_APK_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid save APK bridge")
    list_patches_count = patched.count(LIST_PATCHES_SIGNATURE)
    if list_patches_count == 0:
        patched = patched.rstrip() + "\n\n" + LIST_PATCHES_METHOD + "\n"
    elif list_patches_count != 1:
        raise RuntimeError(f"Patch list bridge is repeatedly injected: {list_patches_count}")
    if patched.count(LIST_PATCHES_SIGNATURE) != 1 or patched.count(LIST_PATCHES_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid patch list bridge")
    inject_count = patched.count(INJECT_MENU_SIGNATURE)
    if inject_count == 0:
        patched = patched.rstrip() + "\n\n" + INJECT_MENU_METHOD + "\n"
    elif inject_count != 1:
        raise RuntimeError(f"Language menu bridge is repeatedly injected: {inject_count}")
    if patched.count(INJECT_MENU_SIGNATURE) != 1 or patched.count(INJECT_MENU_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid language menu bridge")
    smali.write_text(patched, "utf-8", newline="\n")
    patch_bridge_webview_client(decoded)
    run(
        [
            str(JAVA),
            "-jar",
            str(APKTOOL),
            "b",
            "-f",
            "--no-apk",
            str(decoded),
        ],
        env,
    )
    result = decoded / "build" / "apk" / "classes6.dex"
    result3 = decoded / "build" / "apk" / "classes3.dex"
    compiled_manifest = decoded / "build" / "apk" / "AndroidManifest.xml"
    if not result.exists() or not compiled_manifest.exists():
        raise RuntimeError("apktool did not produce classes6.dex and AndroidManifest.xml")
    if not result3.exists():
        raise RuntimeError("apktool did not produce classes3.dex")
    return result, result3, compiled_manifest


def main() -> tuple[Path, Path, Path, Path]:
    env = os.environ.copy()
    env["JAVA_HOME"] = str(JAVA_HOME)
    ascii_temp = Path(env.get("CODEX_APK_BUILD_TEMP", "C:/codex-apk-build"))
    ascii_temp.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(ascii_temp)
    env["TMP"] = str(ascii_temp)
    GENERATED.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="slg-fast-scan-", dir=ascii_temp) as temporary:
        build = Path(temporary)
        helper_dex = build_helper_dex(build, env)
        plugin_dex, bridge_dex, compiled_manifest = patch_plugin_dex(build, env)
        classes6 = GENERATED / "classes6.dex"
        classes3 = GENERATED / "classes3.dex"
        classes7 = GENERATED / "classes7.dex"
        manifest = GENERATED / "AndroidManifest.xml"
        shutil.copy2(plugin_dex, classes6)
        shutil.copy2(bridge_dex, classes3)
        shutil.copy2(helper_dex, classes7)
        shutil.copy2(compiled_manifest, manifest)
    return classes6, classes7, manifest, classes3


if __name__ == "__main__":
    generated = main()
    print("\n".join(map(str, generated)))
