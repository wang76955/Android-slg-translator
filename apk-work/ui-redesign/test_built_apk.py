import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI_REDESIGN = Path(__file__).resolve().parent
APK_WORK = ROOT / "apk-work"
APK = APK_WORK / "slg-workshop-ui-signed.apk"
BASE_ASSETS = APK_WORK / "extracted" / "assets" / "public" / "assets"
JS_ASSET = "assets/public/assets/index-CJtfdHOF.js"
CSS_ASSET = "assets/public/assets/index-C044IUg3.css"
AAPT2 = ROOT / ".tools" / "android-15" / "aapt2.exe"
DEXDUMP = ROOT / ".tools" / "android-15" / "dexdump.exe"

sys.path.insert(0, str(UI_REDESIGN))
from patch_workshop_ui import patch_assets  # noqa: E402


def generated_text_bytes(text: str) -> bytes:
    """Match Path.write_text(..., encoding="utf-8") used by the builder."""
    return text.replace("\n", os.linesep).encode("utf-8")


class BuiltApkTest(unittest.TestCase):
    def run_tool(self, command: list[str]) -> str:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        if completed.returncode:
            self.fail(
                f"artifact inspection failed ({completed.returncode}): "
                f"{' '.join(command)}\n{completed.stderr}"
            )
        return completed.stdout

    def test_signed_apk_contains_workshop_assets(self):
        self.assertTrue(APK.exists(), "signed workshop APK must exist")
        self.assertTrue(AAPT2.exists(), f"binary manifest verification requires {AAPT2}")
        self.assertTrue(DEXDUMP.exists(), f"signed DEX verification requires {DEXDUMP}")

        base_js = (BASE_ASSETS / "index-CJtfdHOF.js").read_text("utf-8")
        base_css = (BASE_ASSETS / "index-C044IUg3.css").read_text("utf-8")
        expected_js, expected_css = patch_assets(base_js, base_css)

        with zipfile.ZipFile(APK) as archive:
            names = archive.namelist()
            for entry in (JS_ASSET, CSS_ASSET, "classes6.dex", "classes7.dex"):
                self.assertIn(entry, names, f"signed APK must contain {entry}")

            js_bytes = archive.read(JS_ASSET)
            css_bytes = archive.read(CSS_ASSET)
            self.assertEqual(
                js_bytes,
                generated_text_bytes(expected_js),
                "signed APK JavaScript must exactly match current patch_assets output",
            )
            self.assertEqual(
                css_bytes,
                generated_text_bytes(expected_css),
                "signed APK CSS must exactly match current patch_assets output",
            )

            js = js_bytes.decode("utf-8")
            for token in (
                "选择应用或 APK",
                "loadSelectedApk=window.__slgLoadSelectedApk",
                "FileManager.listInstalledApps()",
                "FileManager.selectInstalledApp({packageName:app.packageName})",
                "splitApk",
                "history.pushState",
                "history.back()",
                'window.addEventListener("popstate",handleWorkshopPopState)',
                "installedListEpoch",
                "sourceRequestEpoch",
                "window.__slgSelectionEpoch",
                "没有找到可选择的已安装应用。你仍可从文件选择 APK。",
                "从文件选择 APK",
            ):
                self.assertIn(token, js)
            self.assertEqual(js.count("loadSelectedApk=window.__slgLoadSelectedApk"), 1)
            self.assertNotIn(
                "xe=async()=>{try{let e=await E.pickApkFile();r(e.uri)",
                js,
                "stale file-only loader must not satisfy the artifact contract",
            )
            self.assertNotIn(
                'actionButton("选择 APK 文件"',
                js,
                "stale file-only CTA must not satisfy the artifact contract",
            )
            self.assertEqual(
                archive.getinfo("resources.arsc").compress_type,
                zipfile.ZIP_STORED,
            )

            with tempfile.TemporaryDirectory(dir=APK_WORK) as temporary_directory:
                temporary = Path(temporary_directory)
                dex_dumps = {}
                for dex_name in ("classes6.dex", "classes7.dex"):
                    dex_path = temporary / dex_name
                    dex_path.write_bytes(archive.read(dex_name))
                    dex_dumps[dex_name] = self.run_tool(
                        [str(DEXDUMP), str(dex_path.relative_to(ROOT))]
                    )

        plugin_dump = dex_dumps["classes6.dex"]
        helper_dump = dex_dumps["classes7.dex"]
        self.assertEqual(plugin_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'selectInstalledApp'"), 1)
        self.assertEqual(
            helper_dump.count(
                "Class descriptor  : 'Lcom/slgtranslator/app/InstalledAppSource;'"
            ),
            1,
        )
        self.assertEqual(helper_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(helper_dump.count("name          : 'selectInstalledApp'"), 1)

        manifest_dump = self.run_tool(
            [str(AAPT2), "dump", "xmltree", str(APK), "--file", "AndroidManifest.xml"]
        )
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", manifest_dump)
        self.assertIn("targetSdkVersion(0x01010270)=36", manifest_dump)
        queries_start = manifest_dump.find("E: queries")
        self.assertNotEqual(queries_start, -1, "binary manifest must contain queries")
        application_start = manifest_dump.find("E: application", queries_start)
        self.assertNotEqual(
            application_start,
            -1,
            "binary manifest queries must precede application",
        )
        queries_dump = manifest_dump[queries_start:application_start]
        self.assertIn('"android.intent.action.MAIN"', queries_dump)
        self.assertIn('"android.intent.category.LAUNCHER"', queries_dump)


if __name__ == "__main__":
    unittest.main()
