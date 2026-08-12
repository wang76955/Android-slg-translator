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

        self.assertNotIn(
            "_r?.uri&&(window.__slgSelectionMeta.uri=_r.uri)",
            coordinator,
            "refresh must not write the URI outside the metadata merge",
        )
        self.assertIn(
            "window.__slgSelectionMeta=mergeSelectionMetadata(window.__slgSelectionMeta,_r),persistSelectionSession(window.__slgSelectionMeta)",
            coordinator,
        )
        self.assertIn(
            "E.injectTranslatorMenu({apkUri:window.__slgSelectionMeta?.uri||n",
            coordinator,
        )
        self.assertIn(
            "window.__slgTranslatorLang=window.__slgRenpyMenuType===`renpy`&&_m&&_m.ready",
            coordinator,
        )
        self.assertGreater(
            coordinator.index("E.injectTranslatorMenu("),
            coordinator.index("mergeSelectionMetadata(window.__slgSelectionMeta,_r)"),
            "menu reinjection must happen after the source refresh",
        )

    def test_language_menu_guidance_flag_is_updated_on_reinjection(self):
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn(
            "window.__slgTranslatorLang=window.__slgRenpyMenuType===`renpy`&&_m&&_m.ready?'slgtranslated':''",
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

    def test_content_uri_menu_result_updates_shared_selection_metadata(self):
        """The writable URI returned by menu injection must feed every later stage."""
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        scan_start = js.index("scanSelectedApk=async(e,selectionEpoch)=>{")
        scan_end = js.index(",loadSelectedApk=window.__slgLoadSelectedApk", scan_start)
        scan = js[scan_start:scan_end]
        self.assertIn("resolvedApkUri", scan)
        self.assertIn("mergeSelectionMetadata", scan)
        self.assertIn("window.__slgSelectionMeta=", scan)
        self.assertIn("baseUri", scan)
        self.assertIn(
            "E.buildPatchedApk({uri:(window.__slgSelectionMeta?.uri||n)",
            js,
        )
        self.assertIn(
            "E.compileTranslationsIntoApk({apkUri:(window.__slgSelectionMeta?.uri||n)",
            js,
        )
        self.assertNotIn(
            "window.__slgSelectionMeta.uri=e.uri;window.__slgSelectionMeta.baseUri=e.uri",
            scan,
        )

    def test_non_renpy_scan_materializes_uri_and_persists_merged_session(self):
        """The native materializer is required before any later file read.

        This executes the patched scan function with a small native bridge mock,
        rather than merely checking that the relevant strings are present.
        """
        module = load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        scan_start = js.index("scanSelectedApk=async(e,selectionEpoch)=>{")
        scan_end = js.index(",loadSelectedApk=window.__slgLoadSelectedApk", scan_start)
        scan = js[scan_start:scan_end]
        helper_start = js.rfind("normalizeSelection=", 0, scan_start)
        self.assertGreaterEqual(helper_start, 0)
        helpers = js[helper_start:scan_start].rstrip(",")

        contract = r'''
globalThis.window=globalThis;
window.__slgSelectionEpoch=7;
window.__slgRenpyMenuType=`none`;
window.__slgRenpyLang=``;
const saved={};let injected=null;
globalThis.localStorage={getItem:key=>saved[key]||null,setItem:(key,value)=>{saved[key]=value}};
globalThis.E={
  listApkEntries:async()=>({entries:[],renpyLanguages:[],renpyMenuType:`none`,packageName:`com.example.game`,scanDurationMs:1}),
  getApkPackageName:async()=>({packageName:`com.example.game`}),
  injectTranslatorMenu:async args=>{injected=args;return {ready:false,resolvedApkUri:`file:///data/user/0/com.slgtranslator.app/files/installed-apks/content-game.apk`}}
};
globalThis.r=()=>{};globalThis.a=()=>{};globalThis.p=()=>{};globalThis.s=()=>{};
globalThis.fe=()=>{};globalThis.he={current:[]};globalThis.w=()=>{};globalThis.d=()=>{};globalThis.O=()=>{};
globalThis.Jo=()=>[];globalThis.Oe=()=>({});globalThis.ds={};globalThis.c=[];globalThis.g=[];
'''
        code = contract + "\n" + helpers + "\n" + scan + r'''
(async()=>{
  await scanSelectedApk({uri:`content://fixture/game.apk`,name:`Game.apk`,label:`Game`,packageName:`com.example.game`,source:`file`,splitUris:[`content://fixture/game.apk`],splitNames:[`base.apk`],splitCount:1},7);
  if(!injected||injected.apkUri!==`content://fixture/game.apk`)throw new Error(`non-RenPy scan did not invoke native materializer`);
  if(window.__slgSelectionMeta.uri.indexOf(`file://`)!==0)throw new Error(`resolved URI not merged`);
  if(window.__slgSelectionMeta.baseUri!==window.__slgSelectionMeta.uri)throw new Error(`base URI not merged`);
  const session=JSON.parse(saved[`slg-workshop-session-v1`]);
  if(session.uri!==window.__slgSelectionMeta.uri)throw new Error(`session URI not persisted`);
  if(session.name!==`Game.apk`||session.packageName!==`com.example.game`||session.source!==`file`)throw new Error(`session identity fields lost`);
  if(session.splitCount!==1||session.splitNames[0]!==`base.apk`)throw new Error(`session split fields lost`);
  if(session.translating!==false)throw new Error(`scan must not mark session translating`);
  if(window.__slgActivationMode!==`always_on`)throw new Error(`non-RenPy scan must remain always_on`);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
