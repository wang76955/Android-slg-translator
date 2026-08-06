import importlib.util
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
BASE_JS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
BASE_CSS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-C044IUg3.css"


def load_patch():
    spec = importlib.util.spec_from_file_location(
        "patch_workshop_ui", ROOT / "patch_workshop_ui.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallButtonRefreshTest(unittest.TestCase):
    """The completed shell must not trust the button reference cached at mount
    time. After a new game finishes translating, React replaces the install
    button, so the snapshot has to find the live button again."""

    def test_completed_snapshot_refreshes_install_button_reference(self):
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("function readTaskSnapshot(){")
        end = js.index("function detailToggle(", start)
        snapshot_runtime = js[start:end]

        contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
globalThis.localStorage={getItem(){return null},removeItem(){},setItem(){}};
globalThis.document={querySelectorAll(){return[]}};
globalThis.sourceText=()=>`\u7ffb\u8bd1\u5b8c\u6210\n\u5df2\u5199\u5165\u8865\u4e01 APK: /sdcard/Game-patched-signed.apk`;
globalThis.readProgressLog=()=>({raw:`done`,latest:`done`});
globalThis.installButton={isConnected:false,textContent:`\u5b89\u88c5\u8865\u4e01\u7248`};
globalThis.findButton=()=>({isConnected:true,textContent:`\u5b89\u88c5\u8865\u4e01\u7248`});
const snapshot=readTaskSnapshot();
check(snapshot.state===`completed`,`completed snapshot recognized`);
check(snapshot.installAvailable===true,`installAvailable uses the live React button`);
check(globalThis.installButton.isConnected===true,`snapshot refreshes cached installButton`);
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installButton=currentInstall", js)
        self.assertNotIn(
            "installAvailable:!!installButton?.isConnected",
            js,
            "completed snapshot must refresh the cached button before checking it",
        )

    def test_completed_snapshot_handles_missing_install_button(self):
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("function readTaskSnapshot(){")
        end = js.index("function detailToggle(", start)
        snapshot_runtime = js[start:end]
        contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
globalThis.localStorage={getItem(){return null},removeItem(){},setItem(){}};
globalThis.document={querySelectorAll(){return[]}};
globalThis.sourceText=()=>`\u7ffb\u8bd1\u5b8c\u6210\n\u5df2\u5199\u5165\u8865\u4e01 APK: /sdcard/Game-patched-signed.apk`;
globalThis.readProgressLog=()=>({raw:`done`,latest:`done`});
let installButton={isConnected:false,textContent:`\u5b89\u88c5\u8865\u4e01\u7248`};
globalThis.installButton=installButton;
globalThis.findButton=()=>null;
const snapshot=readTaskSnapshot();
check(snapshot.state===`completed`,`completed snapshot recognized`);
check(snapshot.installAvailable===false,`missing install button disables install`);
check(globalThis.installButton===installButton,`missing button keeps cached reference`);
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class LanguageMenuReinjectionTest(unittest.TestCase):
    """Translating an installed game refreshes the private APK copy before
    building. The language menu injected during the scan is therefore lost
    unless it is injected again on the refreshed copy."""

    def test_translation_start_reinjects_menu_after_source_refresh(self):
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        refresh_start = js.index("window.__slgSelectionMeta?.source===`installed`")
        coordinator_start = js.rindex("Ce=async()=>{", 0, refresh_start)
        coordinator_end = js.index("ce(!0),", coordinator_start)
        coordinator = js[coordinator_start:coordinator_end]

        self.assertIn("_r?.uri&&(window.__slgSelectionMeta.uri=_r.uri)", coordinator)
        self.assertIn(
            "E.injectTranslatorMenu({apkUri:window.__slgSelectionMeta?.uri||n",
            coordinator,
        )
        self.assertIn("window.__slgTranslatorLang=(_m&&_m.ready)", coordinator)
        self.assertGreater(
            coordinator.index("E.injectTranslatorMenu("),
            coordinator.index("window.__slgSelectionMeta.uri=_r.uri"),
            "menu reinjection must happen after the source refresh",
        )

    def test_language_menu_guidance_flag_is_updated_on_reinjection(self):
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn(
            "window.__slgTranslatorLang=(_m&&_m.ready)?'slgtranslated':''",
            js,
        )
        self.assertIn(
            "E.injectTranslatorMenu({apkUri:window.__slgSelectionMeta?.uri||n",
            js,
        )

    def test_scan_resets_reinjection_guard(self):
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn(
            "window.__slgTranslatorLang='',window.__slgMenuInjectedForRefresh=false,window.__slgRenpyLang=",
            js,
        )


if __name__ == "__main__":
    unittest.main()
