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
THIRD_PARTY = HERE / "third-party"
NATIVE_ABI = "arm64-v8a"
# Kotlin stdlib is only a compile-time dependency: the base APK already
# ships kotlin-stdlib and kotlinx-coroutines and the app must keep those.
COMPILE_ONLY_JARS = {"kotlin-stdlib-2.0.21.jar", "lifecycle-common-2.0.0.jar"}

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
    (
        ".method public final listSaveGameApps(Lcom/getcapacitor/PluginCall;)V",
        "Lcom/slgtranslator/app/InstalledAppSource;->listSaveGameApps",
        """.method public final listSaveGameApps(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstalledAppSource;->listSaveGameApps(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
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
INSTALL_APK_SIGNATURE = ".method public final installApk(Lcom/getcapacitor/PluginCall;)V"
INSTALL_APK_DELEGATE = "Lcom/slgtranslator/app/PackageInstallerSupport;->installViaSession"
INSTALL_APK_PATTERN = re.compile(
    r"(?ms)^\.method public final installApk\(Lcom/getcapacitor/PluginCall;\)V\r?\n.*?^\.end method"
)
INSTALL_APK_METHOD = """.method public final installApk(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/PackageInstallerSupport;->installViaSession(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
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
COMPILE_TL_SIGNATURE = ".method public final compileTranslationsIntoApk(Lcom/getcapacitor/PluginCall;)V"
COMPILE_TL_DELEGATE = "Lcom/slgtranslator/app/TranslationCompiler;->compileTranslationsIntoApk"
CLEANUP_SIGNATURE = ".method public final cleanupStorage(Lcom/getcapacitor/PluginCall;)V"
CLEANUP_DELEGATE = "Lcom/slgtranslator/app/CleanupSupport;->cleanupStorage"
CLEANUP_METHOD = """.method public final cleanupStorage(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/CleanupSupport;->cleanupStorage(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_BACKUP_SIGNATURE = ".method public final backupSaves(Lcom/getcapacitor/PluginCall;)V"
SAVE_BACKUP_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->backupSaves"
SAVE_BACKUP_METHOD = """.method public final backupSaves(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->backupSaves(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_RESTORE_SIGNATURE = ".method public final restoreSaves(Lcom/getcapacitor/PluginCall;)V"
SAVE_RESTORE_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->restoreSaves"
SAVE_RESTORE_METHOD = """.method public final restoreSaves(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->restoreSaves(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_LIST_SIGNATURE = ".method public final listSaveBackups(Lcom/getcapacitor/PluginCall;)V"
SAVE_LIST_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->listSaveBackups"
SAVE_LIST_METHOD = """.method public final listSaveBackups(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->listSaveBackups(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_DELETE_SIGNATURE = ".method public final deleteBackup(Lcom/getcapacitor/PluginCall;)V"
SAVE_DELETE_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->deleteBackup"
SAVE_DELETE_METHOD = """.method public final deleteBackup(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->deleteBackup(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_ARCHIVE_DELETE_SIGNATURE = ".method public final deleteSaveArchive(Lcom/getcapacitor/PluginCall;)V"
SAVE_ARCHIVE_DELETE_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->deleteSaveArchive"
SAVE_ARCHIVE_DELETE_METHOD = """.method public final deleteSaveArchive(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->deleteSaveArchive(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_EXPORT_SIGNATURE = ".method public final exportSavesToDownloads(Lcom/getcapacitor/PluginCall;)V"
SAVE_EXPORT_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->exportSavesToDownloads"
SAVE_EXPORT_METHOD = """.method public final exportSavesToDownloads(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->exportSavesToDownloads(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_SHARE_SIGNATURE = ".method public final shareSaveBackup(Lcom/getcapacitor/PluginCall;)V"
SAVE_SHARE_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->shareSaveBackup"
SAVE_SHARE_METHOD = """.method public final shareSaveBackup(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->shareSaveBackup(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_ARCHIVES_SIGNATURE = ".method public final listSaveArchives(Lcom/getcapacitor/PluginCall;)V"
SAVE_ARCHIVES_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->listSaveArchives"
SAVE_ARCHIVES_METHOD = """.method public final listSaveArchives(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->listSaveArchives(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
SAVE_IMPORT_SIGNATURE = ".method public final importSaveBackup(Lcom/getcapacitor/PluginCall;)V"
SAVE_IMPORT_DELEGATE = "Lcom/slgtranslator/app/SaveTransfer;->importSaveBackup"
SAVE_IMPORT_METHOD = """.method public final importSaveBackup(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/SaveTransfer;->importSaveBackup(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
READ_TEXTS_SIGNATURE = ".method public final readRenpyTexts(Lcom/getcapacitor/PluginCall;)V"
READ_TEXTS_DELEGATE = "Lcom/slgtranslator/app/FastApkScanner;->readRenpyTexts"
READ_TEXTS_METHOD = """.method public final readRenpyTexts(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/FastApkScanner;->readRenpyTexts(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
COMPILE_TL_METHOD = """.method public final compileTranslationsIntoApk(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/TranslationCompiler;->compileTranslationsIntoApk(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""

# On-device translation kernel bridge methods: localStatus / localDownload /
# translateLocal / mlkitDelete / llmDownload / llmDelete. Methods that need
# the plugin instance for progress listeners pass p0 as java.lang.Object.
LOCAL_DELEGATE = "Lcom/slgtranslator/app/LocalTranslationSupport;"
LOCAL_METHODS = (
    (
        ".method public final localStatus(Lcom/getcapacitor/PluginCall;)V",
        f"{LOCAL_DELEGATE}->localStatus",
        """.method public final localStatus(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/LocalTranslationSupport;->localStatus(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
    (
        ".method public final localDownload(Lcom/getcapacitor/PluginCall;)V",
        f"{LOCAL_DELEGATE}->localDownload",
        """.method public final localDownload(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p0, p1}, Lcom/slgtranslator/app/LocalTranslationSupport;->localDownload(Landroid/content/Context;Ljava/lang/Object;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
    (
        ".method public final translateLocal(Lcom/getcapacitor/PluginCall;)V",
        f"{LOCAL_DELEGATE}->translateLocal",
        """.method public final translateLocal(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/LocalTranslationSupport;->translateLocal(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
    (
        ".method public final mlkitDelete(Lcom/getcapacitor/PluginCall;)V",
        f"{LOCAL_DELEGATE}->mlkitDelete",
        """.method public final mlkitDelete(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/LocalTranslationSupport;->mlkitDelete(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
    (
        ".method public final llmDownload(Lcom/getcapacitor/PluginCall;)V",
        f"{LOCAL_DELEGATE}->llmDownload",
        """.method public final llmDownload(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p0, p1}, Lcom/slgtranslator/app/LocalTranslationSupport;->llmDownload(Landroid/content/Context;Ljava/lang/Object;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
    (
        ".method public final llmDelete(Lcom/getcapacitor/PluginCall;)V",
        f"{LOCAL_DELEGATE}->llmDelete",
        """.method public final llmDelete(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/LocalTranslationSupport;->llmDelete(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method""",
    ),
)

ANDROID_NAMESPACE = "http://schemas.android.com/apk/res/android"
ANDROID_NAME = f"{{{ANDROID_NAMESPACE}}}name"


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, check=True, env=env)


def build_helper_dex(build: Path, env: dict[str, str], extra_class_dirs: tuple[Path, ...] = ()) -> Path:
    stubs = build / "stub-classes"
    helper = build / "helper-classes"
    dex_output = build / "helper-dex"
    third_party_classes = build / "third-party-classes"
    stubs.mkdir(parents=True)
    helper.mkdir(parents=True)
    dex_output.mkdir(parents=True)
    third_party_classes.mkdir(parents=True)
    common = ["-source", "8", "-target", "8", "-encoding", "UTF-8"]

    # Extract classes.jar from every third-party AAR into a class directory so
    # javac and d8 can consume them like plain class files.
    classpath_entries: list[Path] = []
    merged_class_dirs: list[Path] = []
    for aar in sorted(THIRD_PARTY.glob("*.aar")):
        out_dir = third_party_classes / aar.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(aar) as archive:
            names = [n for n in archive.namelist() if n == "classes.jar"]
            if not names:
                continue
            with archive.open("classes.jar") as jar_bytes:
                import io
                with zipfile.ZipFile(io.BytesIO(jar_bytes.read())) as jar:
                    for entry in jar.namelist():
                        if entry.endswith(".class") and not entry.startswith("kotlin/") and not entry.startswith("kotlinx/") and not entry.startswith("META-INF/"):
                            target = out_dir / entry
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(jar.read(entry))
        if any(out_dir.rglob("*.class")):
            classpath_entries.append(out_dir)
            jar_path = build / f"third-party-{aar.stem}.jar"
            with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as jar_archive:
                for class_file in sorted(out_dir.rglob("*.class")):
                    jar_archive.write(class_file, class_file.relative_to(out_dir).as_posix())
            merged_class_dirs.append(jar_path)
    for jar in sorted(THIRD_PARTY.glob("*.jar")):
        classpath_entries.append(jar)
        if jar.name not in COMPILE_ONLY_JARS:
            merged_class_dirs.append(jar)

    classpath = os.pathsep.join([str(stubs), *map(str, classpath_entries)])
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
            classpath,
            "-d",
            str(helper),
            *map(str, SOURCE_SOURCES),
        ],
        env,
    )
    classes = sorted(map(str, helper.rglob("*.class")))
    merged_inputs = [*classes]
    for extra_dir in extra_class_dirs:
        merged_inputs.extend(map(str, sorted(extra_dir.rglob("*.class"))))
    for merged_entry in merged_class_dirs:
        if merged_entry.is_dir():
            merged_inputs.extend(map(str, sorted(merged_entry.rglob("*.class"))))
        else:
            merged_inputs.append(str(merged_entry))
    run(
        [
            str(D8),
            "--min-api",
            "24",
            "--classpath",
            str(stubs),
            "--output",
            str(dex_output),
            *merged_inputs,
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
    application = root.find("application")
    if application is not None:
        application.set("{" + ANDROID_NAMESPACE + "}largeHeap", "true")
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


def inject_native_libs(decoded: Path) -> None:
    """Copy the arm64 native libraries from the llama and ML Kit AARs into
    the decoded APK so apktool b puts them under lib/arm64-v8a/."""
    lib_dir = decoded / "lib" / NATIVE_ABI
    lib_dir.mkdir(parents=True, exist_ok=True)
    for aar_name in ("llama-android-0.1.1.aar", "translate-17.0.3.aar"):
        with zipfile.ZipFile(THIRD_PARTY / aar_name) as archive:
            for entry in archive.namelist():
                if entry.startswith(f"jni/{NATIVE_ABI}/") and entry.endswith(".so"):
                    name = Path(entry).name
                    (lib_dir / name).write_bytes(archive.read(entry))


def patch_mlkit_manifest(manifest: Path) -> None:
    """Merge the ML Kit component discovery service, init provider and the
    ACCESS_NETWORK_STATE permission into the app manifest (Gradle would merge
    these from the AAR manifests automatically; this pipeline does it by hand)."""
    ET.register_namespace("android", ANDROID_NAMESPACE)
    tree = ET.parse(manifest)
    root = tree.getroot()
    application = root.find("application")
    if application is None:
        raise RuntimeError("AndroidManifest.xml has no application element")

    existing_permissions = {
        item.get(ANDROID_NAME) for item in root.findall("uses-permission")
    }
    if "android.permission.ACCESS_NETWORK_STATE" not in existing_permissions:
        permission = ET.Element("uses-permission")
        permission.set(ANDROID_NAME, "android.permission.ACCESS_NETWORK_STATE")
        root.insert(0, permission)

    provider_name = "com.google.mlkit.common.internal.MlKitInitProvider"
    has_provider = any(
        item.get(ANDROID_NAME) == provider_name for item in application.findall("provider")
    )
    if not has_provider:
        provider = ET.SubElement(application, "provider")
        provider.set(ANDROID_NAME, provider_name)
        provider.set("{" + ANDROID_NAMESPACE + "}authorities", "com.slgtranslator.app.mlkitinitprovider")
        provider.set("{" + ANDROID_NAMESPACE + "}exported", "false")
        provider.set("{" + ANDROID_NAMESPACE + "}initOrder", "99")

    service_name = "com.google.mlkit.common.internal.MlKitComponentDiscoveryService"
    service = next(
        (item for item in application.findall("service") if item.get(ANDROID_NAME) == service_name),
        None,
    )
    if service is None:
        service = ET.SubElement(application, "service")
        service.set(ANDROID_NAME, service_name)
        service.set("{" + ANDROID_NAMESPACE + "}exported", "false")
        service.set("{" + ANDROID_NAMESPACE + "}directBootAware", "true")
    registrar_names = {
        meta.get(ANDROID_NAME) for meta in service.findall("meta-data")
    }
    if "com.google.firebase.components:com.google.mlkit.common.internal.CommonComponentRegistrar" not in registrar_names:
        meta = ET.SubElement(service, "meta-data")
        meta.set(ANDROID_NAME, "com.google.firebase.components:com.google.mlkit.common.internal.CommonComponentRegistrar")
        meta.set("{" + ANDROID_NAMESPACE + "}value", "com.google.firebase.components.ComponentRegistrar")
    if "com.google.firebase.components:com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar" not in registrar_names:
        meta = ET.SubElement(service, "meta-data")
        meta.set(ANDROID_NAME, "com.google.firebase.components:com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar")
        meta.set("{" + ANDROID_NAMESPACE + "}value", "com.google.firebase.components.ComponentRegistrar")

    tree.write(manifest, encoding="utf-8", xml_declaration=True)

def patch_version_manifest(manifest: Path) -> None:
    """Set the release version on the decoded manifest.

    apktool restores versionCode/versionName from original/AndroidManifest.xml
    when the decoded XML omits them, so write them explicitly here to pin the
    release version (1.0.10 / versionCode 10).
    """
    ET.register_namespace("android", ANDROID_NAMESPACE)
    tree = ET.parse(manifest)
    root = tree.getroot()
    root.set("{" + ANDROID_NAMESPACE + "}versionCode", "10")
    root.set("{" + ANDROID_NAMESPACE + "}versionName", "1.0.10")
    tree.write(manifest, encoding="utf-8", xml_declaration=True)


MLKIT_AAR_RES = (
    ("res/raw/translate_models_metadata.json", "res/raw/translate_models_metadata.json"),
    ("res/xml/rapid_response_client_defaults.xml", "res/xml/rapid_response_client_defaults.xml"),
)


def inject_mlkit_resources(decoded: Path) -> None:
    """Copy the ML Kit translate AAR resources into the decoded APK so
    aapt2 assigns real resource ids during apktool b. ML Kit's zzad reads
    R.xml.rapid_response_client_defaults, so the ids must exist in the app's
    resource table or model download fails with a resource-resolution error."""
    with zipfile.ZipFile(THIRD_PARTY / "translate-17.0.3.aar") as archive:
        for entry_name, target_rel in MLKIT_AAR_RES:
            target = decoded / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry_name))


def extract_mlkit_resource_ids(decoded: Path) -> tuple[int, int]:
    """Extract the aapt2-assigned resource ids for the two ML Kit resources.
    Returns (rapid_response_xml_id, translate_models_raw_id)."""
    arsc = decoded / "build" / "apk" / "resources.arsc"
    if not arsc.is_file():
        raise RuntimeError("resources.arsc missing after apktool b")

    # aapt2 dump needs a zip/APK container, so pack the built apk dir first.
    apk_root = decoded / "build" / "apk"
    dump_apk = decoded / "resource-dump.apk"
    with zipfile.ZipFile(dump_apk, "w", zipfile.ZIP_STORED) as archive:
        for path in sorted(apk_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(apk_root).as_posix())
    aapt2 = ANDROID_TOOLS / "aapt2.exe"
    proc = subprocess.run(
        [str(aapt2), "dump", "resources", str(dump_apk)],
        check=True, capture_output=True, text=True, errors="replace"
    )
    xml_id = 0
    raw_id = 0
    for line in proc.stdout.splitlines():
        if "xml/rapid_response_client_defaults" in line:
            match = re.search(r"0x[0-9a-fA-F]+", line)
            if match:
                xml_id = int(match.group(0), 16)
        elif "raw/translate_models_metadata" in line:
            match = re.search(r"0x[0-9a-fA-F]+", line)
            if match:
                raw_id = int(match.group(0), 16)
    if xml_id == 0 or raw_id == 0:
        raise RuntimeError(f"ML Kit resource ids not found (xml={xml_id:#x}, raw={raw_id:#x})")
    print(f"ML Kit resource ids: xml=0x{xml_id:08x} raw=0x{raw_id:08x}")
    return xml_id, raw_id


def generate_mlkit_r_classes(build: Path, env: dict[str, str], xml_id: int, raw_id: int) -> Path:
    """Generate com.google.mlkit.nl.translate.R (+xml/raw inner classes) with
    the resource ids aapt2 assigned, then compile them into class files that
    d8 merges into the helper dex."""
    src_dir = build / "mlkit-r-src"
    out_dir = build / "mlkit-r-classes"
    src_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    package_dir = src_dir / "com" / "google" / "mlkit" / "nl" / "translate"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "R.java").write_text(
        "package com.google.mlkit.nl.translate;\n"
        "public final class R {\n"
        "    private R() {}\n"
        "    public static final class xml {\n"
        f"        public static final int rapid_response_client_defaults = 0x{xml_id:08x};\n"
        "    }\n"
        "    public static final class raw {\n"
        f"        public static final int translate_models_metadata = 0x{raw_id:08x};\n"
        "    }\n"
        "}\n"
    )
    javac = JAVA_HOME / "bin" / "javac.exe"
    run(
        [
            str(javac),
            "-source", "8", "-target", "8", "-encoding", "UTF-8",
            "-d", str(out_dir),
            str(package_dir / "R.java"),
        ],
        env,
    )
    return out_dir


def patch_plugin_dex(build: Path, env: dict[str, str]) -> tuple[Path, Path, Path, list[Path], int, int]:
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
    patch_mlkit_manifest(decoded / "AndroidManifest.xml")
    patch_version_manifest(decoded / "AndroidManifest.xml")
    inject_mlkit_resources(decoded)
    inject_native_libs(decoded)
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
    compile_tl_count = patched.count(COMPILE_TL_SIGNATURE)
    if compile_tl_count == 0:
        patched = patched.rstrip() + "\n\n" + COMPILE_TL_METHOD + "\n"
    elif compile_tl_count != 1:
        raise RuntimeError(f"Translation compile bridge is repeatedly injected: {compile_tl_count}")
    if patched.count(COMPILE_TL_SIGNATURE) != 1 or patched.count(COMPILE_TL_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid translation compile bridge")
    read_texts_count = patched.count(READ_TEXTS_SIGNATURE)
    if read_texts_count == 0:
        patched = patched.rstrip() + "\n\n" + READ_TEXTS_METHOD + "\n"
    elif read_texts_count != 1:
        raise RuntimeError(f"Read Ren'Py texts bridge is repeatedly injected: {read_texts_count}")
    if patched.count(READ_TEXTS_SIGNATURE) != 1 or patched.count(READ_TEXTS_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid read Ren'Py texts bridge")
    cleanup_count = patched.count(CLEANUP_SIGNATURE)
    if cleanup_count == 0:
        patched = patched.rstrip() + "\n\n" + CLEANUP_METHOD + "\n"
    elif cleanup_count != 1:
        raise RuntimeError(f"Cleanup bridge is repeatedly injected: {cleanup_count}")
    if patched.count(CLEANUP_SIGNATURE) != 1 or patched.count(CLEANUP_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid cleanup bridge")
    for signature, delegate, method, label in (
        (SAVE_BACKUP_SIGNATURE, SAVE_BACKUP_DELEGATE, SAVE_BACKUP_METHOD, "save backup"),
        (SAVE_RESTORE_SIGNATURE, SAVE_RESTORE_DELEGATE, SAVE_RESTORE_METHOD, "save restore"),
        (SAVE_LIST_SIGNATURE, SAVE_LIST_DELEGATE, SAVE_LIST_METHOD, "save list"),
        (SAVE_DELETE_SIGNATURE, SAVE_DELETE_DELEGATE, SAVE_DELETE_METHOD, "save delete"),
        (SAVE_ARCHIVE_DELETE_SIGNATURE, SAVE_ARCHIVE_DELETE_DELEGATE, SAVE_ARCHIVE_DELETE_METHOD, "save archive delete"),
        (SAVE_EXPORT_SIGNATURE, SAVE_EXPORT_DELEGATE, SAVE_EXPORT_METHOD, "save export"),
        (SAVE_SHARE_SIGNATURE, SAVE_SHARE_DELEGATE, SAVE_SHARE_METHOD, "save share"),
        (SAVE_ARCHIVES_SIGNATURE, SAVE_ARCHIVES_DELEGATE, SAVE_ARCHIVES_METHOD, "save archives"),
        (SAVE_IMPORT_SIGNATURE, SAVE_IMPORT_DELEGATE, SAVE_IMPORT_METHOD, "save import"),
    ):
        count = patched.count(signature)
        if count == 0:
            patched = patched.rstrip() + "\n\n" + method + "\n"
        elif count != 1:
            raise RuntimeError(f"{label} bridge is repeatedly injected: {count}")
        if patched.count(signature) != 1 or patched.count(delegate) != 1:
            raise RuntimeError(f"Expected exactly one valid {label} bridge")
    local_counts = [patched.count(signature) for signature, _, _ in LOCAL_METHODS]
    if local_counts == [0] * len(LOCAL_METHODS):
        patched = patched.rstrip() + "\n\n" + "\n\n".join(
            method for _, _, method in LOCAL_METHODS
        ) + "\n"
    elif local_counts != [1] * len(LOCAL_METHODS):
        raise RuntimeError(f"Local translation bridge methods are partially or repeatedly injected: {local_counts}")
    for signature, delegate, _ in LOCAL_METHODS:
        if patched.count(signature) != 1 or patched.count(delegate) != 1:
            raise RuntimeError(f"Expected exactly one valid local translation bridge for {signature}")
    existing_install = INSTALL_APK_PATTERN.findall(patched)
    if len(existing_install) != 1:
        raise RuntimeError(f"Expected exactly one installApk method, found {len(existing_install)}")
    patched, replaced = INSTALL_APK_PATTERN.subn(INSTALL_APK_METHOD, patched, count=1)
    if replaced != 1:
        raise RuntimeError(f"Expected to replace one installApk method, replaced {replaced}")
    if patched.count(INSTALL_APK_SIGNATURE) != 1 or patched.count(INSTALL_APK_DELEGATE) != 1:
        raise RuntimeError("Expected exactly one valid installApk session bridge")
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
    native_libs = sorted((decoded / "lib" / NATIVE_ABI).glob("*.so"))
    xml_id, raw_id = extract_mlkit_resource_ids(decoded)
    apk_root = decoded / "build" / "apk"
    res_files = [
        ("resources.arsc", apk_root / "resources.arsc"),
        ("res/raw/translate_models_metadata.json", apk_root / "res" / "raw" / "translate_models_metadata.json"),
        ("res/xml/rapid_response_client_defaults.xml", apk_root / "res" / "xml" / "rapid_response_client_defaults.xml"),
    ]
    for _rel, res_file in res_files:
        if not res_file.is_file():
            raise RuntimeError(f"Expected ML Kit resource file missing: {res_file}")
    return result, result3, compiled_manifest, native_libs, res_files, xml_id, raw_id


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
        plugin_dex, bridge_dex, compiled_manifest, native_libs, res_files, xml_id, raw_id = patch_plugin_dex(build, env)
        r_classes = generate_mlkit_r_classes(build, env, xml_id, raw_id)
        helper_dex = build_helper_dex(build, env, (r_classes,))
        classes6 = GENERATED / "classes6.dex"
        classes3 = GENERATED / "classes3.dex"
        classes7 = GENERATED / "classes7.dex"
        manifest = GENERATED / "AndroidManifest.xml"
        shutil.copy2(plugin_dex, classes6)
        shutil.copy2(bridge_dex, classes3)
        shutil.copy2(helper_dex, classes7)
        shutil.copy2(compiled_manifest, manifest)
        for res_rel, res_file in res_files:
            target = GENERATED / res_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(res_file, target)
        native_dir = GENERATED / "lib" / NATIVE_ABI
        native_dir.mkdir(parents=True, exist_ok=True)
        for native_lib in native_libs:
            shutil.copy2(native_lib, native_dir / native_lib.name)
    return classes6, classes7, manifest, classes3


if __name__ == "__main__":
    generated = main()
    print("\n".join(map(str, generated)))
