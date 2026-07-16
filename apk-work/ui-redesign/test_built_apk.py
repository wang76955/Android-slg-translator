import os
import re
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
    CLASS_BLOCK = re.compile(
        r"^Class #\d+\s+-\r?\n.*?(?=^Class #\d+\s+-\r?\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )

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

    def assert_dex_ownership(
        self,
        dex_dump: str,
        class_descriptor: str,
        method_names: tuple[str, ...],
        forbidden_descriptor: str,
    ) -> None:
        descriptor_marker = f"Class descriptor  : '{class_descriptor}'"
        forbidden_marker = f"Class descriptor  : '{forbidden_descriptor}'"
        self.assertEqual(
            dex_dump.count(descriptor_marker),
            1,
            f"{class_descriptor} must occur exactly once in its assigned DEX",
        )
        self.assertNotIn(
            forbidden_marker,
            dex_dump,
            f"{forbidden_descriptor} must not occur in this DEX",
        )

        matching_blocks = [
            match.group(0)
            for match in self.CLASS_BLOCK.finditer(dex_dump)
            if descriptor_marker in match.group(0)
        ]
        self.assertEqual(
            len(matching_blocks),
            1,
            f"could not isolate the unique class block for {class_descriptor}",
        )
        class_block = matching_blocks[0]
        for method_name in method_names:
            method_marker = f"name          : '{method_name}'"
            self.assertEqual(
                class_block.count(method_marker),
                1,
                f"{method_name} must belong exactly once to {class_descriptor}",
            )
            self.assertEqual(
                dex_dump.count(method_marker),
                1,
                f"no other class in the DEX may define {method_name}",
            )

    def move_method_to_wrong_class(
        self,
        dex_dump: str,
        class_descriptor: str,
        method_name: str,
    ) -> str:
        descriptor_marker = f"Class descriptor  : '{class_descriptor}'"
        method_marker = f"name          : '{method_name}'"
        blocks = [match.group(0) for match in self.CLASS_BLOCK.finditer(dex_dump)]
        target_indexes = [
            index for index, block in enumerate(blocks) if descriptor_marker in block
        ]
        self.assertEqual(len(target_indexes), 1, "mutation requires one target class")
        target_index = target_indexes[0]
        self.assertEqual(
            blocks[target_index].count(method_marker),
            1,
            "mutation requires one target method marker",
        )
        wrong_index = next(
            (index for index in range(len(blocks)) if index != target_index),
            None,
        )
        self.assertIsNotNone(wrong_index, "mutation requires a second class block")

        blocks[target_index] = blocks[target_index].replace(method_marker, "", 1)
        blocks[wrong_index] += f"\n    {method_marker}\n"
        first_block = next(self.CLASS_BLOCK.finditer(dex_dump))
        return dex_dump[: first_block.start()] + "".join(blocks)

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
        self.assert_dex_ownership(
            plugin_dump,
            "Lcom/slgtranslator/app/FileManagerPlugin;",
            ("listInstalledApps", "selectInstalledApp"),
            "Lcom/slgtranslator/app/InstalledAppSource;",
        )
        self.assert_dex_ownership(
            helper_dump,
            "Lcom/slgtranslator/app/InstalledAppSource;",
            ("listInstalledApps", "selectInstalledApp"),
            "Lcom/slgtranslator/app/FileManagerPlugin;",
        )

        mutation_cases = (
            (
                plugin_dump,
                "Lcom/slgtranslator/app/FileManagerPlugin;",
                "Lcom/slgtranslator/app/InstalledAppSource;",
            ),
            (
                helper_dump,
                "Lcom/slgtranslator/app/InstalledAppSource;",
                "Lcom/slgtranslator/app/FileManagerPlugin;",
            ),
        )
        for dex_dump, owner_descriptor, forbidden_descriptor in mutation_cases:
            with self.subTest(mutated_owner=owner_descriptor):
                mutated_dump = self.move_method_to_wrong_class(
                    dex_dump,
                    owner_descriptor,
                    "listInstalledApps",
                )
                with self.assertRaises(AssertionError):
                    self.assert_dex_ownership(
                        mutated_dump,
                        owner_descriptor,
                        ("listInstalledApps", "selectInstalledApp"),
                        forbidden_descriptor,
                    )

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
