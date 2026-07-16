import collections
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from dataclasses import dataclass, field
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
ZIPALIGN = ROOT / ".tools" / "android-15" / "zipalign.exe"
APKSIGNER = ROOT / ".tools" / "android-15" / "apksigner.bat"

sys.path.insert(0, str(UI_REDESIGN))
from patch_workshop_ui import (  # noqa: E402
    CANONICAL_BASE_CSS_SHA256,
    CANONICAL_BASE_JS_SHA256,
    patch_assets,
    verify_canonical_base_assets,
)


@dataclass
class ManifestElement:
    name: str
    attributes: list[str] = field(default_factory=list)
    children: list["ManifestElement"] = field(default_factory=list)


def parse_xmltree(dump: str) -> ManifestElement:
    root = ManifestElement("<root>")
    stack: list[tuple[int, ManifestElement]] = [(-1, root)]
    for line in dump.splitlines():
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith("E: "):
            name = stripped[3:].split(" ", 1)[0]
            while stack[-1][0] >= indent:
                stack.pop()
            element = ManifestElement(name)
            stack[-1][1].children.append(element)
            stack.append((indent, element))
        elif stripped.startswith("A: "):
            if len(stack) == 1:
                raise ValueError("manifest attribute has no owning element")
            stack[-1][1].attributes.append(stripped[3:])
    return root


def find_elements(element: ManifestElement, name: str) -> list[ManifestElement]:
    matches = [element] if element.name == name else []
    for child in element.children:
        matches.extend(find_elements(child, name))
    return matches


class BuiltApkTest(unittest.TestCase):
    CLASS_BLOCK = re.compile(
        r"^Class #\d+\s+-\r?\n.*?(?=^Class #\d+\s+-\r?\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    def require_artifact_inputs(self, *tools: Path) -> None:
        self.assertTrue(APK.is_file(), f"signed APK is missing: {APK}")
        for tool in tools:
            self.assertTrue(tool.is_file(), f"required Android tool is missing: {tool}")

    def run_tool(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            self.fail(f"artifact inspection timed out after 60s: {' '.join(command)}\n{error}")

    def assert_tool_success(self, completed: subprocess.CompletedProcess[str]) -> str:
        output = completed.stdout + completed.stderr
        self.assertEqual(
            completed.returncode,
            0,
            f"artifact inspection failed ({completed.returncode}): "
            f"{' '.join(completed.args)}\n{output}",
        )
        return output

    def assert_class_contract(
        self,
        all_dumps: dict[str, str],
        assigned_dex: str,
        descriptor: str,
        methods: tuple[str, ...],
    ) -> None:
        marker = f"Class descriptor  : '{descriptor}'"
        occurrences = sum(dump.count(marker) for dump in all_dumps.values())
        self.assertEqual(
            occurrences,
            1,
            f"{descriptor} must occur exactly once across every DEX in the APK",
        )
        self.assertIn(marker, all_dumps[assigned_dex], f"{descriptor} must be in {assigned_dex}")
        blocks = [
            match.group(0)
            for match in self.CLASS_BLOCK.finditer(all_dumps[assigned_dex])
            if marker in match.group(0)
        ]
        self.assertEqual(len(blocks), 1, f"could not isolate {descriptor} class block")
        for method in methods:
            self.assertEqual(
                blocks[0].count(f"name          : '{method}'"),
                1,
                f"{method} must occur exactly once inside {descriptor}",
            )

    def move_method_to_wrong_class(self, dump: str, descriptor: str, method: str) -> str:
        descriptor_marker = f"Class descriptor  : '{descriptor}'"
        method_marker = f"name          : '{method}'"
        matches = list(self.CLASS_BLOCK.finditer(dump))
        blocks = [match.group(0) for match in matches]
        target = next(i for i, block in enumerate(blocks) if descriptor_marker in block)
        wrong = next(i for i in range(len(blocks)) if i != target)
        self.assertEqual(blocks[target].count(method_marker), 1)
        blocks[target] = blocks[target].replace(method_marker, "", 1)
        blocks[wrong] += f"\n    {method_marker}\n"
        return dump[: matches[0].start()] + "".join(blocks)

    def assert_queries_contract(self, dump: str) -> None:
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", dump)
        tree = parse_xmltree(dump)
        queries = find_elements(tree, "queries")
        self.assertEqual(len(queries), 1, "manifest must contain exactly one queries element")
        self.assertEqual(
            [child.name for child in queries[0].children],
            ["intent"],
            "queries must contain only one intent and no package/provider/other query child",
        )
        intent = queries[0].children[0]
        self.assertEqual(
            collections.Counter(child.name for child in intent.children),
            collections.Counter({"action": 1, "category": 1}),
            "the same query intent must contain exactly one action and one category",
        )
        action = next(child for child in intent.children if child.name == "action")
        category = next(child for child in intent.children if child.name == "category")
        self.assertEqual(len(action.attributes), 1)
        self.assertEqual(len(category.attributes), 1)
        self.assertIn('="android.intent.action.MAIN"', action.attributes[0])
        self.assertIn('="android.intent.category.LAUNCHER"', category.attributes[0])

    def test_assets_exactly_match_pinned_patch_output(self):
        self.require_artifact_inputs()
        js_path = BASE_ASSETS / "index-CJtfdHOF.js"
        css_path = BASE_ASSETS / "index-C044IUg3.css"
        verify_canonical_base_assets(js_path, css_path)
        self.assertEqual(len(CANONICAL_BASE_JS_SHA256), 64)
        self.assertEqual(len(CANONICAL_BASE_CSS_SHA256), 64)
        expected_js, expected_css = patch_assets(
            js_path.read_text("utf-8"), css_path.read_text("utf-8")
        )

        with zipfile.ZipFile(APK) as archive:
            names = archive.namelist()
            duplicates = [name for name, count in collections.Counter(names).items() if count > 1]
            self.assertEqual(duplicates, [], f"signed APK has duplicate ZIP entries: {duplicates}")
            js_bytes = archive.read(JS_ASSET)
            css_bytes = archive.read(CSS_ASSET)
            self.assertEqual(js_bytes, expected_js.encode("utf-8"))
            self.assertEqual(css_bytes, expected_css.encode("utf-8"))
            self.assertEqual(archive.getinfo("resources.arsc").compress_type, zipfile.ZIP_STORED)

        result = subprocess.run(
            ["node", "--input-type=module", "--check"],
            input=js_bytes.decode("utf-8"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_every_dex_has_unique_entries_and_expected_class_ownership(self):
        self.require_artifact_inputs(DEXDUMP)
        with zipfile.ZipFile(APK) as archive:
            names = archive.namelist()
            duplicates = [name for name, count in collections.Counter(names).items() if count > 1]
            self.assertEqual(duplicates, [], f"signed APK has duplicate ZIP entries: {duplicates}")
            dex_names = sorted(name for name in names if re.fullmatch(r"classes(?:\d+)?\.dex", name))
            self.assertTrue(dex_names, "signed APK must contain at least one classes*.dex")
            with tempfile.TemporaryDirectory(dir=APK_WORK) as directory:
                temporary = Path(directory)
                dumps: dict[str, str] = {}
                for dex_name in dex_names:
                    dex_path = temporary / dex_name
                    dex_path.write_bytes(archive.read(dex_name))
                    completed = self.run_tool(
                        [str(DEXDUMP), str(dex_path.relative_to(ROOT))]
                    )
                    dumps[dex_name] = self.assert_tool_success(completed)

        contracts = (
            (
                "classes6.dex",
                "Lcom/slgtranslator/app/FileManagerPlugin;",
                ("listInstalledApps", "selectInstalledApp", "enableWorkshopBackHandling"),
            ),
            (
                "classes7.dex",
                "Lcom/slgtranslator/app/InstalledAppSource;",
                ("listInstalledApps", "selectInstalledApp"),
            ),
            (
                "classes7.dex",
                "Lcom/slgtranslator/app/WorkshopBackHandler;",
                ("enable", "delegateDefaultBack"),
            ),
        )
        for assigned_dex, descriptor, methods in contracts:
            self.assertIn(assigned_dex, dumps)
            self.assert_class_contract(
                dumps,
                assigned_dex,
                descriptor,
                methods,
            )
            mutated = dict(dumps)
            mutated[assigned_dex] = self.move_method_to_wrong_class(
                mutated[assigned_dex], descriptor, methods[0]
            )
            with self.assertRaises(AssertionError):
                self.assert_class_contract(
                    mutated,
                    assigned_dex,
                    descriptor,
                    methods,
                )

    def test_manifest_queries_are_minimal_and_same_intent(self):
        self.require_artifact_inputs(AAPT2)
        completed = self.run_tool(
            [str(AAPT2), "dump", "xmltree", str(APK), "--file", "AndroidManifest.xml"]
        )
        dump = self.assert_tool_success(completed)
        self.assertIn("targetSdkVersion(0x01010270)=36", dump)
        self.assert_queries_contract(dump)

        split_intents = dump.replace(
            "              E: category (line=10)",
            "          E: intent (line=10)\n              E: category (line=10)",
            1,
        )
        with self.assertRaises(AssertionError):
            self.assert_queries_contract(split_intents)

        package_query = dump.replace(
            "      E: application (line=10)",
            "          E: package (line=10)\n"
            "            A: http://schemas.android.com/apk/res/android:name(0x01010003)=\"example.bad\"\n"
            "      E: application (line=10)",
            1,
        )
        with self.assertRaises(AssertionError):
            self.assert_queries_contract(package_query)

    def test_apk_is_zipaligned_and_v2_v3_signed(self):
        self.require_artifact_inputs(ZIPALIGN, APKSIGNER)
        alignment = self.run_tool([str(ZIPALIGN), "-c", "4", str(APK)])
        self.assert_tool_success(alignment)

        signature = self.run_tool([str(APKSIGNER), "verify", "--verbose", str(APK)])
        output = self.assert_tool_success(signature)
        self.assertRegex(output, r"Verified using v2 scheme .*:\s*true")
        self.assertRegex(output, r"Verified using v3 scheme .*:\s*true")


if __name__ == "__main__":
    unittest.main()
