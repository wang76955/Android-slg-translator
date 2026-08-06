import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
BASE_JS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
BASE_CSS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-C044IUg3.css"


class WorkshopPatchContractTest(unittest.TestCase):
    def load_patch(self):
        module_path = ROOT / "patch_workshop_ui.py"
        self.assertTrue(module_path.exists(), "patch_workshop_ui.py must exist")
        spec = importlib.util.spec_from_file_location("patch_workshop_ui", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_canonical_extracted_assets_are_cryptographically_pinned(self):
        module = self.load_patch()
        self.assertEqual(
            module.CANONICAL_BASE_JS_SHA256,
            "d3b0f42a6656e347e5933e17835b8b687f1dc2f5546c1aa15b8fb2048ebe1f85",
        )
        self.assertEqual(
            module.CANONICAL_BASE_CSS_SHA256,
            "fad58dc778c5b4fa0ac263f5aebcba268c6fb32e9d8b39ae980805b49d5fb18f",
        )
        module.verify_canonical_base_assets(BASE_JS, BASE_CSS)

        with tempfile.TemporaryDirectory() as directory:
            mutated_js = Path(directory) / BASE_JS.name
            mutated_js.write_bytes(BASE_JS.read_bytes() + b"\nmutation")
            with self.assertRaisesRegex(ValueError, "canonical base JavaScript SHA-256 mismatch"):
                module.verify_canonical_base_assets(mutated_js, BASE_CSS)

            missing_css = Path(directory) / BASE_CSS.name
            with self.assertRaisesRegex(FileNotFoundError, "canonical base CSS is missing"):
                module.verify_canonical_base_assets(BASE_JS, missing_css)

    def test_generated_assets_always_use_lf_newlines(self):
        module = self.load_patch()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "asset.txt"
            module.write_generated_text(output, "alpha\nbeta\n")
            self.assertEqual(output.read_bytes(), b"alpha\nbeta\n")

    def test_patched_javascript_is_syntactically_valid(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--check"],
            input=js,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rpyc_string_filter_rejects_code_assets_and_quoted_tokens(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        he_start = js.index("function He(e,t){")
        he_end = js.index("function Ue(e,t){", he_start)
        he = js[he_start:he_end]
        self.assertIn(r"/^[A-Za-z_][\w.]*\(.*\)\s*$/", he)
        self.assertIn(r"/^[A-Za-z_][\w.]*\s*[+\-*/%]{1,2}=\s\S/", he)
        self.assertIn("/^[\"'][A-Za-z0-9_./:-]{1,40}[\"']$/", he)
        self.assertNotIn(r"/^[A-Za-z_][\w.]*\([^)]*\)$/", he)

    def test_renpy_candidate_filter_keeps_story_scripts_but_rejects_generated_content(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        filter_start = js.index("function Jo(e,t,n){")
        filter_end = js.index("var ts=", filter_start)
        candidate_filter = js[filter_start:filter_end]

        self.assertNotIn("/x-renpy/x-common/", candidate_filter)
        self.assertIn("_rpycSkip", candidate_filter)
        self.assertNotIn("screens?", candidate_filter)
        self.assertIn("common|style", candidate_filter)
        self.assertNotIn("options|", candidate_filter)
        self.assertIn("let q=Qo(r);if(q!=null)", candidate_filter)
        self.assertIn("e===`tl`||e===`x-tl`", candidate_filter)
        self.assertIn("p.fileType!==`rpyc`", candidate_filter)
        renpy_start = candidate_filter.index("if(e.fileType===`rpyc`||e.fileType===`rpy`)")
        renpy_end = candidate_filter.index("}return!!", renpy_start)
        renpy_branch = candidate_filter[renpy_start:renpy_end]
        for obsolete_keyword in ("text", "string", "dialogue", "script"):
            self.assertNotIn(obsolete_keyword, renpy_branch)

    def test_translation_bucket_files_seed_supplementary_corpus(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        filter_start = js.index("function Jo(e,t,n){")
        filter_end = js.index("var ts=", filter_start)
        candidate_filter = js[filter_start:filter_end]
        self.assertIn("slgtranslated", candidate_filter)
        self.assertIn("es(q)", candidate_filter)
        self.assertIn("$o(_s).has(l)", candidate_filter)
        self.assertNotIn("$o(_d).has(l)", candidate_filter)

        contract = r"""
function check(condition,label){if(!condition)throw new Error(label)}
var qo=new Set(['png','jpg','jpeg','gif','webp','bmp','ico','mp3','wav','ogg','aac','flac','m4a','mp4','webm','avi','mkv','mov','ttf','otf','woff','woff2']);
globalThis.__slgSrcLang='en';globalThis.__slgDstLang='zh';
check(Yo({name:'assets/x-game/x-tl/x-chinese/x-phone.rpyc',fileType:'rpyc'},'auto','zh')===false,'chinese tl bucket must be skipped as target language');
check(Yo({name:'assets/x-game/x-tl/x-english/x-phone.rpyc',fileType:'rpyc'},'auto','zh')===true,'english tl bucket must be a candidate');
check(Yo({name:'assets/x-game/x-tl/x-german/x-phone.rpyc',fileType:'rpyc'},'auto','zh')===false,'unrelated german tl bucket must be excluded');
check(Yo({name:'assets/x-game/x-tl/x-bosnian/x-phone.rpyc',fileType:'rpyc'},'auto','zh')===false,'unrelated bosnian tl bucket must be excluded');
check(Yo({name:'assets/x-game/x-tl/x-slgtranslated/x-phone.rpyc',fileType:'rpyc'},'auto','zh')===false,'slgtranslated bucket must be excluded');
check(Yo({name:'assets/x-game/x-ch1ep1.rpyc',fileType:'rpyc'},'auto','zh')===true,'story script must stay a candidate');
"""
        result = subprocess.run(
            ["node", "-e", candidate_filter + contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_recovery_modes_hidden_for_game_without_history(self):
        """New games with no translation history must not show 缁х画涓婃/鎵弿鏂板
        recovery modes; the ready state should only offer a fresh start."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        # The cache module must expose a history helper that reads per-file pkg.
        self.assertIn("globalThis.__slgHasHistory", js)
        self.assertIn("_v.pkg===pkg", js)
        # Per-file cache writes must record the package for history detection.
        self.assertIn("pkg:window.__slgSelectionMeta?.packageName", js)
        # Ready state must guard the recovery mode buttons behind history.
        self.assertIn("if(globalThis.__slgHasHistory&&globalThis.__slgHasHistory(_pkg))", js)

        contract = r"""
function check(condition,label){if(!condition)throw new Error(label)}
var _o=`slg-translator-cache:`,vo={},cacheIndex={},yo=!1,bo=!1,bp=Promise.resolve();
globalThis.__slgHasHistory=function(pkg){if(!pkg)return false;
try{for(const[_k,_v]of Object.entries(vo)){
if(_k.startsWith(`slg-file-v1:`)&&_v&&_v.pkg===pkg)return true}return false}catch{return false}};
check(globalThis.__slgHasHistory('zitao.mbml')===false,'no history initially');
vo['slg-file-v1:abc']={pkg:'zitao.mbml',texts:[],translations:[],count:0};
check(globalThis.__slgHasHistory('zitao.mbml')===true,'history detected after file processed');
check(globalThis.__slgHasHistory('other.pkg')===false,'other game still no history');
"""
        result = subprocess.run(
            ["node", "-e", contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_build_files_filter_keeps_translation_buckets_except_slgtranslated(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn("x-slgtranslated", js)
        self.assertIn("a.filter", js)
        build_fragment = js[js.index("files:(()=>{const _f="):js.index("files:(()=>{const _f=") + 260]
        self.assertIn("x-slgtranslated", build_fragment)
        self.assertNotIn("includes(`/x-tl/`)", build_fragment)

    def test_output_path_keeps_translation_bucket_source_prefix(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        os_start = js.index("function os(e,t){")
        os_end = js.index("function ss(", os_start)
        os_fn = js[os_start:os_end]
        self.assertIn("x-${s}-${n[n.length-1]}", os_fn)
        contract = r"""
function check(condition,label){if(!condition)throw new Error(label)}
function es(e){return e.trim().toLowerCase().replace(/^x[-_]/,``).replace(/[\s-]+/g,`_`)}
function ss(e,t){return e.startsWith(`x-`)?`x-${t}`:t}
// original script keeps its plain name
check(os('assets/x-game/x-ch1ep1.rpyc','slgtranslated').endsWith('/x-slgtranslated/x-ch1ep1.rpy'),'original keeps plain output: '+os('assets/x-game/x-ch1ep1.rpyc','slgtranslated'));
// translation bucket gets source-language prefix so it never clobbers the original
check(os('assets/x-game/x-tl/x-german/x-ch1ep1.rpyc','slgtranslated').endsWith('/x-slgtranslated/x-german-x-ch1ep1.rpy'),'german bucket prefixed: '+os('assets/x-game/x-tl/x-german/x-ch1ep1.rpyc','slgtranslated'));
check(os('assets/x-game/x-tl/x-chinese/x-phone.rpyc','slgtranslated').endsWith('/x-slgtranslated/x-chinese-x-phone.rpy'),'chinese bucket prefixed: '+os('assets/x-game/x-tl/x-chinese/x-phone.rpyc','slgtranslated'));
// engine common fallback still lands in the x-game bucket
check(os('assets/x-renpy/x-common/x-00gui.rpyc','slgtranslated').startsWith('assets/x-game/x-tl/x-slgtranslated/'),'engine common routed: '+os('assets/x-renpy/x-common/x-00gui.rpyc','slgtranslated'));
"""
        result = subprocess.run(
            ["node", "-e", os_fn + contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_translation_state_requests_screen_wakelock(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn("navigator.wakeLock?.request", js)
        self.assertIn("__slgWakeLock", js)
        self.assertIn('state==="patching"', js)

    def test_installed_app_source_chooser_contract(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        for token in (
            "loadSelectedApk=window.__slgLoadSelectedApk=e=>",
            "window.__slgSelectionMeta=e",
            "window.__slgSelectionError=null",
            "window.__slgSelectionError={message:",
            "await loadSelectedApk(await E.pickApkFile())",
            "E.listApkEntries({uri:e.uri})",
            "e.name||e.label||e.uri.split(`/`).pop()||`Unknown.apk`",
            "e.packageName||``",
            "e.splitApk&&t.entries.length===0",
            "function openSourceChooser()",
            "该应用使用拆分安装包，基础 APK 中没有可翻译文件。请改用“从文件选择 APK”。",
            "该应用使用拆分安装包（${e.splitCount||0} 个拆分包），当前先扫描基础 APK，部分资源可能无法读取。",
            "function openInstalledApps()",
            "function filterInstalledApps(apps,query)",
            "function renderInstalledApps()",
            "async function chooseInstalledApp(app)",
            "function armModalHistory()",
            "function handleWorkshopPopState()",
            "function focusInstalledTarget()",
            "installedListEpoch",
            "sourceRequestEpoch",
            "installedBusy",
            "FileManager.listInstalledApps()",
            "FileManager.selectInstalledApp({packageName:app.packageName})",
            "await window.__slgLoadSelectedApk(selection)",
            "閫夋嫨搴旂敤鎴?APK",
            "浠庡凡瀹夎搴旂敤閫夋嫨",
            "浠庢枃浠堕€夋嫨 APK",
            "姝ｅ湪璇诲彇搴旂敤鍒楄〃",
            "娌℃湁鎵惧埌鍙€夋嫨鐨勫凡瀹夎搴旂敤銆備綘浠嶅彲浠庢枃浠堕€夋嫨 APK銆?",
            "姝ｅ湪璇诲彇搴旂敤瀹夎鍖呪€?",
            "姝ｅ湪璇诲彇宸插畨瑁呭簲鐢ㄧ殑 APK...",
            "閲嶆柊鍔犺浇",
            "鎼滅储搴旂敤鍚嶇О鎴栧寘鍚?",
        ):
            self.assertIn(token, js)
        self.assertEqual(js.count("loadSelectedApk=window.__slgLoadSelectedApk"), 1)
        self.assertEqual(js.count("E.listApkEntries({uri:e.uri})"), 1)
        self.assertIn("toLocaleLowerCase()", js)
        self.assertIn("app.label", js)
        self.assertIn("app.packageName", js)
        compact_css = "".join(css.split())
        for token in (
            ".workshop-source-dialog{position:fixed",
            ".workshop-installed-dialog{position:fixed",
            "min-height:52px",
            "prefers-color-scheme:dark",
            "prefers-reduced-motion:reduce",
        ):
            self.assertIn(token, compact_css)
        self.assertIn('event.key==="Escape"', js)
        self.assertIn('event.target===sourceDialog', js)
        self.assertIn('event.target===installedDialog', js)
        self.assertIn("previousSourceFocus?.focus()", js)
        self.assertIn("history.pushState", js)
        self.assertIn("history.back()", js)
        self.assertIn("window.addEventListener(\"popstate\",handleWorkshopPopState)", js)

    def test_shared_apk_loader_and_installed_selection_behavior(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        loader_start = js.index("loadSelectedApk=window.__slgLoadSelectedApk=")
        loader_end = js.index(",xe=async()=>", loader_start)
        loader_initializer = js[
            loader_start + len("loadSelectedApk=") : loader_end
        ]
        timeout_start = js.index("withTimeout=(")
        timeout_runtime = js[timeout_start:loader_start].removesuffix(",") + ";"
        xe_start = js.index("xe=async()=>", loader_end)
        xe_end = js.index(",Se=async()=>", xe_start)
        xe_initializer = js[xe_start + len("xe=") : xe_end]
        filter_start = js.index("function filterInstalledApps(apps,query)")
        filter_end = js.index("function renderInstalledApps()", filter_start)
        filter_runtime = js[filter_start:filter_end]
        list_start = js.index("async function loadInstalledApps()")
        list_end = js.index("async function openInstalledApps()", list_start)
        list_runtime = js[list_start:list_end]
        choose_start = js.index("async function chooseInstalledApp(app)")
        choose_end = js.index("function closeInstalledApps", choose_start)
        choose_runtime = js[choose_start:choose_end]
        snapshot_start = js.index("function readTaskSnapshot(){")
        snapshot_end = js.index("function detailToggle(", snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        render_start = js.index("function renderTopbar(state)")
        render_end = js.index("function setWorkshopState(", render_start)
        render_runtime = js[render_start:render_end]
        state_start = render_end
        state_end = js.index("function snapshotKey(", state_start)
        state_runtime = js[state_start:state_end]
        behavior_contract = rf'''
function check(condition,label){{if(!condition)throw new Error(label)}}
globalThis.window=globalThis;
const calls=[],logs=[],scanning=[];
const he={{current:[]}};
let uri=`old`,name=`old.apk`,entries=[`old`],failure=`old`,progress=[`old`],packageName=`old.pkg`;
function r(value){{uri=value}} function a(value){{name=value}} function s(value){{entries=value}}
function fe(value){{failure=value}} function w(value){{progress=value}} function p(value){{packageName=value}}
function d(value){{scanning.push(value)}} function O(message,type){{logs.push([message,type])}}
function Jo(value){{return value}} function Oe(){{return{{rpy:1}}}} const ds={{rpy:`Ren'Py`}};
const c=`all`,g=`zh`;
const E={{
  listApkEntries:async input=>{{calls.push([`list`,input.uri]);return{{entries:[{{fileType:`rpy`}}],scanDurationMs:1200,packageName:``}}}},
  getApkPackageName:async input=>{{calls.push([`package`,input.uri]);return{{packageName:`fallback.pkg`}}}},
  pickApkFile:async()=>{{calls.push([`pick`]);return{{uri:`file://picked.apk`,name:`Picked.apk`}}}},
}};
{timeout_runtime}
const loadSelectedApk={loader_initializer};
const xe={xe_initializer};
let installedDialog=null,installedError=``,installedLoading=false,installedApps=[],installedListEpoch=0,sourceRequestEpoch=0,installedBusy=false;
const renderedStates=[];
function renderInstalledApps(){{renderedStates.push({{loading:installedLoading,error:installedError,count:installedApps.length}})}}
let closed=0;
function closeInstalledApps(){{closed+=1}}
const document={{querySelectorAll(){{return[]}}}};
function sourceText(){{return`宸查€夋嫨锛欱roken.apk`}} function readProgressLog(){{return{{raw:``,latest:``}}}}
function textNode(tag,cls,text){{return{{tag,cls,text,children:[],dataset:{{}},style:{{}},setAttribute(){{}},append(...children){{this.children.push(...children)}}}}}}
function fileRow(){{return textNode(`div`,`file-row`,`file`)}} function detailToggle(raw){{return textNode(`div`,`details`,raw)}}
function actionButton(label,handler,secondary=false){{return{{tag:`button`,label,handler,secondary,children:[]}}}}
let sourceChooserOpened=0;function openSourceChooser(){{sourceChooserOpened+=1}} function openSettings(){{}} function retryTask(){{}} function triggerReactButton(){{}}
const startButton=null,installButton=null;
function startScanClock(){{}} function stopScanClock(){{}}
function classList(){{return{{remove(){{}},add(){{}}}}}}
let shell={{dataset:{{}},classList:classList(),setAttribute(name,value){{this[name]=value}},replaceChildren(...nodes){{this.rendered=nodes}}}};
const runtimeRoot={{classList:classList(),setAttribute(){{}}}};

async function main(){{
  const installed={{uri:`file://installed.apk`,name:`Friendly Game.apk`,label:`Friendly Game`,packageName:`game.pkg`,source:`installed`,splitApk:true,splitCount:3}};
  await xe();
  check(calls[0][0]===`pick`&&calls[1][0]===`list`&&calls[1][1]===`file://picked.apk`,`real file picker enters shared URI scanner`);
  check(uri===`file://picked.apk`&&name===`Picked.apk`,`file selection metadata loaded`);
  check(entries.length===1&&failure===null&&progress.length===0,`old task reset`);

  E.listApkEntries=async input=>{{calls.push([`list`,input.uri]);return{{entries:[],scanDurationMs:5}}}};
  let splitError=``;
  try{{await loadSelectedApk({{uri:`file://split.apk`,label:`Split`,splitApk:true,splitCount:2}})}}catch(error){{splitError=error.message}}
  check(splitError===`璇ュ簲鐢ㄤ娇鐢ㄦ媶鍒嗗畨瑁呭寘锛屽熀纭€ APK 涓病鏈夊彲缈昏瘧鏂囦欢銆傝鏀圭敤鈥滀粠鏂囦欢閫夋嫨 APK鈥濄€俙,`dedicated split error`);
  check(scanning.at(-1)===false,`error clears scanning`);
  E.listApkEntries=async()=>({{entries:[{{fileType:`rpy`}}]}});
  await loadSelectedApk({{uri:`file://retry.apk`,name:`Retry.apk`}});
  check(scanning.at(-1)===false&&uri===`file://retry.apk`,`selection recovers after error`);

  E.pickApkFile=async()=>({{uri:`file://broken.apk`,name:`Broken.apk`}});
  E.listApkEntries=async()=>{{throw new Error(`broken scan`)}};
  await xe();
  check(window.__slgSelectionError?.message===`broken scan`,`file failure bridges explicit selection error`);
  check(scanning.at(-1)===false,`file failure clears scanning`);
  const failedSnapshot=readTaskSnapshot();
  check(failedSnapshot.state===`failed`&&failedSnapshot.reason===`scan`,`file failure beats stale selected filename`);
  setWorkshopState(failedSnapshot.state,failedSnapshot);
  check(shell.dataset.workshopState===`failed`&&shell.dataset.workshopTask===`active`,`visible shell enters failed state`);
  const failedBody=shell.rendered[1],failedButtons=[];
  function visit(node){{if(!node)return;if(node.tag===`button`)failedButtons.push(node);for(const child of node.children||[])visit(child)}}
  visit(failedBody);
  const reselect=failedButtons.find(button=>button.label===`\u91cd\u65b0\u9009\u62e9 APK`);
  check(reselect,`failed shell offers source recovery`);reselect.handler();
  check(sourceChooserOpened===1,`failed shell recovery opens source chooser`);

  const apps=[{{label:`Alpha Story`,packageName:`com.game.one`}},{{label:`Beta`,packageName:`ORG.EXAMPLE.TWO`}}];
  check(filterInstalledApps(apps,`alpha`)[0]===apps[0],`case-insensitive label search`);
  check(filterInstalledApps(apps,`example`)[0]===apps[1],`case-insensitive package search`);

  installedDialog={{hidden:false,setAttribute(){{}},querySelector(){{return null}}}};
  window.Capacitor={{Plugins:{{FileManager:{{listInstalledApps:async()=>{{throw new Error(`native list failed`)}}}}}}}};
  await loadInstalledApps();
  check(renderedStates.some(state=>state.loading),`list exposes loading state`);
  check(installedLoading===false&&installedError===`native list failed`,`list exposes recoverable error state`);
  window.Capacitor.Plugins.FileManager.listInstalledApps=async()=>({{apps:[]}});
  await loadInstalledApps();
  check(installedLoading===false&&installedError===``&&installedApps.length===0,`retry reaches empty state`);

  let selectedArgs=null,loadedSelection=null;
  window.Capacitor={{Plugins:{{FileManager:{{selectInstalledApp:async args=>{{selectedArgs=args;return installed}}}}}}}};
  E.listApkEntries=async input=>{{calls.push([`list`,input.uri]);return{{entries:[{{fileType:`rpy`}}],scanDurationMs:9}}}};
  await chooseInstalledApp(apps[0]);
  check(selectedArgs.packageName===apps[0].packageName,`native installed selection`);
  check(closed===1,`installed selection closes`);
  check(calls.at(-1)[0]===`list`&&calls.at(-1)[1]===installed.uri,`installed selection enters real shared scanner`);
  check(uri===installed.uri&&name===installed.name&&packageName===installed.packageName,`installed metadata survives real loader`);
  check(window.__slgSelectionMeta===installed,`installed split metadata preserved by identity`);
  check(logs.some(([message])=>message===`姝ｅ湪璇诲彇宸插畨瑁呭簲鐢ㄧ殑 APK...`),`installed selection uses dedicated loading log`);
  check(logs.some(([message])=>message===`璇ュ簲鐢ㄤ娇鐢ㄦ媶鍒嗗畨瑁呭寘锛? 涓媶鍒嗗寘锛夛紝褰撳墠鍏堟壂鎻忓熀纭€ APK锛岄儴鍒嗚祫婧愬彲鑳芥棤娉曡鍙栥€俙),`split warning`);

  let resolveOldScan,resolveNewScan;
  E.listApkEntries=input=>new Promise(resolve=>{{if(input.uri===`file://old.apk`)resolveOldScan=resolve;else resolveNewScan=resolve}});
  const oldScan=loadSelectedApk({{uri:`file://old.apk`,name:`Old.apk`}});
  await new Promise(resolve=>setTimeout(resolve,0));
  const newScan=loadSelectedApk({{uri:`file://new.apk`,name:`New.apk`,packageName:`new.pkg`}});
  await new Promise(resolve=>setTimeout(resolve,0));
  resolveNewScan({{entries:[{{fileType:`rpy`,name:`new-entry`}}]}});await newScan;
  resolveOldScan({{entries:[{{fileType:`rpy`,name:`old-entry`}}],packageName:`old.pkg`}});await oldScan;
  check(uri===`file://new.apk`&&name===`New.apk`,`new scan identity survives reverse completion`);
  check(entries[0].name===`new-entry`&&packageName===`new.pkg`,`stale scan cannot overwrite entries or package`);
  check(window.__slgSelectionError===null&&scanning.at(-1)===false,`stale completion cannot overwrite error or scanning state`);
}}
main().catch(error=>{{console.error(error);process.exitCode=1}});
'''
        result = subprocess.run(
            ["node", "-e", filter_runtime + list_runtime + choose_runtime + snapshot_runtime + render_runtime + state_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_modals_handle_android_back_focus_and_file_fallback(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        helper_start = js.index("function armModalHistory()")
        helper_end = js.index("function filterInstalledApps(", helper_start)
        helpers = js[helper_start:helper_end]
        render_start = js.index("function renderInstalledApps()")
        render_end = js.index("async function loadInstalledApps()", render_start)
        installed_render = js[render_start:render_end]
        close_start = js.index("function closeInstalledApps(")
        close_end = js.index("function findButton(", close_start)
        installed_close = js[close_start:close_end]
        pop_start = js.index("function handleWorkshopPopState()")
        pop_end = js.index("function schedule()", pop_start)
        pop_handler = js[pop_start:pop_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const ID=`workshop-runtime`;
let pushes=0,backs=0;
globalThis.history={state:{base:true},pushState(){pushes+=1},back(){backs+=1}};
window.setTimeout=()=>0;
window.requestAnimationFrame=callback=>{callback();return 1};
let returnedFocus=0;
let previousSourceFocus={focus(){returnedFocus+=1}};
let modalHistoryArmed=false,modalHistoryClosing=false;
let settingsOpen=false,manualIdle=false,shell=null;
function closeSettings(){} function setWorkshopState(){}
let sourceDialog={hidden:false};
let installedDialog=null;

armModalHistory();
check(pushes===1&&modalHistoryArmed,`opening modal arms one history entry`);
handleWorkshopPopState();
check(sourceDialog.hidden===true&&!modalHistoryArmed,`Android back closes visible source modal`);
check(backs===0,`back event does not navigate or exit twice`);
armModalHistory();armModalHistory();
check(pushes===2,`reopening does not stack duplicate history while open`);
closeSourceChooser();
check(backs===1,`programmatic close consumes its one history entry`);

const search={focusCalls:0,focus(){this.focusCalls+=1}};
const content={children:[],replaceChildren(){this.children=[]},append(...nodes){this.children.push(...nodes)}};
installedDialog={hidden:false,setAttribute(){},querySelector(selector){if(selector===`.workshop-installed-search`)return search;if(selector===`.workshop-installed-content`)return content;if(selector===`.workshop-installed-content button`)return content.children.find(node=>node.tag===`button`)||null;return null}};
let installedLoading=true,installedError=``,installedApps=[],installedListEpoch=0,sourceRequestEpoch=0,installedBusy=false;
function textNode(tag,cls,text){return{tag,cls,textContent:text,children:[],append(...nodes){this.children.push(...nodes)}}}
function actionButton(label,handler){return{tag:`button`,textContent:label,onclick:handler,children:[]}}
let retries=0,fileFallbacks=0,closed=0;
function loadInstalledApps(){retries+=1}
function triggerReactButton(){fileFallbacks+=1}
const sourceButton={};
renderInstalledApps();
check(search.focusCalls===1,`loading state restores focus to search`);
installedLoading=false;installedError=`native failed`;renderInstalledApps();
check(search.focusCalls===2,`error replacement restores focus`);
const retry=content.children.find(node=>node.textContent===`閲嶆柊鍔犺浇`);
const fallback=content.children.find(node=>node.textContent===`浠庢枃浠堕€夋嫨 APK`);
check(retry&&fallback,`error state exposes retry and file fallback`);
retry.onclick();check(retries===1,`retry action is executable`);
modalHistoryArmed=false;
fallback.onclick();
check(fileFallbacks===1&&installedDialog.hidden,`file fallback closes dialog and triggers real React picker bridge`);

installedDialog.hidden=false;installedError=`choose failed`;renderInstalledApps();
focusInstalledTarget();
check(search.focusCalls>=4,`choose failure re-show can focus a valid target`);
'''
        result = subprocess.run(
            [
                "node",
                "-e",
                helpers
                + installed_render
                + installed_close
                + pop_handler
                + behavior_contract,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_android_back_handler_consumes_only_visible_overlays(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn("window.__slgHandleAndroidBack=", js)
        self.assertIn("enableWorkshopBackHandling", js)
        self.assertIn("function openSettings(){armModalHistory()", js)
        self.assertIn("if(settingsOpen){modalHistoryArmed=false;closeSettings(true);return}", js)
        helper_start = js.index("function armModalHistory()")
        helper_end = js.index("function filterInstalledApps(", helper_start)
        helpers = js[helper_start:helper_end]
        settings_start = js.index("function closeSettings(")
        settings_end = js.index("function openSettings()", settings_start)
        settings_close = js[settings_start:settings_end]
        installed_start = js.index("function closeInstalledApps(")
        installed_end = js.index("function findButton(", installed_start)
        installed_close = js[installed_start:installed_end]
        pop_start = js.index("function handleWorkshopPopState()")
        pop_end = js.index("function schedule()", pop_start)
        pop_handler = js[pop_start:pop_end]
        start = js.index("window.__slgHandleAndroidBack=")
        end = js.index('document.addEventListener("click"', start)
        handler = js[start:end]
        contract = r'''
function check(value,label){if(!value)throw new Error(label)}
globalThis.window=globalThis;
globalThis.document={querySelector(){return null},querySelectorAll(){return[]},addEventListener(){},createElement(){return{children:[],append(){},classList:{add(){},remove(){}},setAttribute(){},querySelector(){return null},querySelectorAll(){return[]}}},body:{}};
const ID=`workshop-runtime`;
let pushes=0,backs=0,marker=false;
globalThis.history={state:{base:true},pushState(state){pushes+=1;marker=true;this.state=state},back(){backs+=1;marker=false;this.state={base:true}}};
let modalHistoryArmed=false,modalHistoryClosing=false,modalHistoryRearm=false;
let returnedFocus=0,previousSourceFocus={focus(){returnedFocus+=1}};
let sourceDialog=null,installedDialog=null,settingsShell={hidden:false},settingsOpen=false,galleryShell=null,galleryOpen=false;
let installedListEpoch=0,sourceRequestEpoch=0,installedLoading=false,installedBusy=false;
let manualIdle=false,manualIdleBeforeOverlay=false,lastSnapshot=``,shell={hidden:true,dataset:{workshopTask:`idle`}},refreshes=0;
function refresh(){refreshes+=1} function setWorkshopState(){} function closeGallery(){}
function beginOverlay(){manualIdleBeforeOverlay=manualIdle;manualIdle=true} function endOverlay(){manualIdle=manualIdleBeforeOverlay}

function resetHistory(){pushes=0;backs=0;marker=false;returnedFocus=0;refreshes=0;modalHistoryArmed=false;modalHistoryClosing=false;modalHistoryRearm=false;history.state={base:true}}
function assertNativeClose(label,isClosed,closeEffects){
  check(window.__slgHandleAndroidBack()===true,`${label} consumed`);
  check(isClosed(),`${label} closed`);
  check(backs===1&&!modalHistoryArmed&&!marker,`${label} releases exactly one marker`);
  check(closeEffects()===1,`${label} closes exactly once`);
  handleWorkshopPopState();
  check(backs===1&&isClosed()&&closeEffects()===1,`${label} release popstate does not close twice`);
  check(window.__slgHandleAndroidBack()===false,`${label} leaves ordinary back delegated`);
}

resetHistory();sourceDialog={hidden:false};armModalHistory();
assertNativeClose(`source modal`,()=>sourceDialog.hidden,()=>returnedFocus);

resetHistory();sourceDialog=null;installedDialog={hidden:false,setAttribute(){}};armModalHistory();
assertNativeClose(`installed modal`,()=>installedDialog.hidden,()=>returnedFocus);

resetHistory();installedDialog=null;settingsOpen=true;settingsShell.hidden=false;armModalHistory();
assertNativeClose(`settings overlay`,()=>!settingsOpen&&settingsShell.hidden,()=>refreshes);
'''
        result = subprocess.run(
            [
                "node",
                "-e",
                "globalThis.window=globalThis;"
                + helpers
                + settings_close
                + installed_close
                + pop_handler
                + handler
                + contract,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shared_loader_has_deadline_and_stale_safe_settlement(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn("withTimeout=(", js)
        self.assertIn("window.clearTimeout(timer)", js)
        self.assertIn("window.__slgScanTimeoutMs??=65000", js)
        self.assertIn("withTimeout(()=>selectionEpoch===window.__slgSelectionEpoch?", js)
        self.assertNotIn("withTimeout(E.listApkEntries", js)
        helper_start = js.index("withTimeout=(")
        loader_start = js.index("loadSelectedApk=window.__slgLoadSelectedApk=", helper_start)
        loader_end = js.index(",xe=async()=>", loader_start)
        helper = js[helper_start:loader_start].removesuffix(",") + ";"
        loader = js[loader_start + len("loadSelectedApk="):loader_end]
        contract = rf'''
globalThis.window=globalThis;
const scanning=[];let uri=``,name=``,entries=[],pkg=``,failure=null;const logs=[];
function r(v){{uri=v}} function a(v){{name=v}} function s(v){{entries=v}} function p(v){{pkg=v}}
function fe(v){{failure=v}} const he={{current:[]}};function w(){{}} function d(v){{scanning.push(v)}} function O(v){{logs.push(v)}}
function Jo(v){{return v}} function Oe(){{return {{rpy:1}}}} const ds={{rpy:`rpy`}},c=`all`,g=`zh`;
let mode=`pending`,lateResolve;
const E={{listApkEntries(){{if(mode===`pending`)return new Promise(resolve=>lateResolve=resolve);if(mode===`reject`)return Promise.reject(new Error(`native reject`));return Promise.resolve({{entries:[{{name:`fresh`,fileType:`rpy`}}]}})}},getApkPackageName:async()=>({{packageName:``}})}};
{helper}
const loadSelectedApk={loader};
async function main(){{
 if(window.__slgScanTimeoutMs!==65000)throw new Error(`production deadline is not observable`);
 window.__slgScanTimeoutMs=10;
 let timeout=``;try{{await loadSelectedApk({{uri:`pending`,name:`Pending.apk`}})}}catch(e){{timeout=e.message}}
 if(!/timed out|瓒呮椂/i.test(timeout)||scanning.at(-1)!==false||window.__slgSelectionError?.message!==timeout)throw new Error(`timeout contract`);
 mode=`reject`;let rejected=``;try{{await loadSelectedApk({{uri:`reject`,name:`Reject.apk`}})}}catch(e){{rejected=e.message}}
 if(rejected!==`native reject`||scanning.at(-1)!==false)throw new Error(`reject contract`);
 mode=`resolve`;await loadSelectedApk({{uri:`fresh`,name:`Fresh.apk`}});lateResolve({{entries:[{{name:`late`,fileType:`rpy`}}]}});await new Promise(resolve=>setTimeout(resolve,0));
 if(uri!==`fresh`||entries[0].name!==`fresh`||window.__slgSelectionError!==null)throw new Error(`late resolve overwrote fresh selection`);
}}
main().catch(e=>{{console.error(e);process.exitCode=1}})
'''
        result = subprocess.run(["node", "-e", contract], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_loader_watchdog_registers_first_and_updates_state_directly(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        declaration_start = js.index("withTimeout=(")
        declaration_end = js.index(",xe=async()=>", declaration_start)
        declarations = js[declaration_start:declaration_end]
        contract = rf'''
function check(value,label){{if(!value)throw new Error(label)}}
globalThis.window=globalThis;window.__slgScanTimeoutMs=25;
const timers=[];window.setTimeout=(callback,delay)=>{{timers.push({{callback,delay,cleared:false}});return timers.length}};
window.clearTimeout=id=>{{timers[id-1].cleared=true}};
const scanning=[],logs=[];let nativeResolve,nativeStarted=false,entries=[];
function r(){{}} function a(){{}} function p(){{}} function s(value){{entries=value}} function fe(){{}}
const he={{current:[]}};function w(){{}} function d(value){{scanning.push(value)}} function O(message){{logs.push(message)}}
function Jo(value){{return value}} function Oe(){{return{{rpy:1}}}} const ds={{rpy:`rpy`}},c=`all`,g=`zh`;
const E={{listApkEntries(){{nativeStarted=true;return new Promise(resolve=>nativeResolve=resolve)}},getApkPackageName:async()=>({{packageName:``}})}};
function productionHost(){{let {declarations};return loadSelectedApk}}
async function main(){{
 const loadSelectedApk=productionHost();
 const pending=loadSelectedApk({{uri:`pending`,name:`Pending.apk`}});
 check(timers.length===1&&timers[0].delay===25,`watchdog timer was not registered synchronously`);
 check(!nativeStarted,`native scan started before watchdog registration`);
 await Promise.resolve();check(nativeStarted&&scanning.at(-1)===true,`deferred native scan did not start`);
 timers[0].callback();
 const watchdog=window.__slgScanWatchdog;
 check(watchdog.deadlineAt>0&&watchdog.timerFired&&watchdog.applied,`watchdog observability missing`);
 check(window.__slgSelectionEpoch===2&&window.__slgSelectionError?.message&&scanning.at(-1)===false,`watchdog did not directly fail active scan`);
 let rejection=``;try{{await pending}}catch(error){{rejection=error.message}}
 check(rejection===window.__slgSelectionError.message&&watchdog.settled&&timers[0].cleared,`timeout promise did not reject and settle`);
 nativeResolve({{entries:[{{name:`late`,fileType:`rpy`}}]}});await Promise.resolve();await Promise.resolve();
 check(entries.length===0&&window.__slgSelectionError,`late native result overwrote watchdog failure`);

 window.__slgSelectionError=null;nativeStarted=false;
 const stale=loadSelectedApk({{uri:`stale`,name:`Stale.apk`}});await Promise.resolve();
 window.__slgSelectionEpoch+=1;timers[1].callback();await stale;
 check(window.__slgSelectionError===null&&!window.__slgScanWatchdog.applied,`stale watchdog mutated newer epoch`);
}}
main().catch(error=>{{console.error(error);process.exitCode=1}})
'''
        result = subprocess.run(
            ["node", "-e", contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installed_list_and_selection_epochs_ignore_stale_requests(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        helper_start = js.index("function armModalHistory()")
        helper_end = js.index("function filterInstalledApps(", helper_start)
        helpers = js[helper_start:helper_end]
        installed_start = helper_end
        installed_end = js.index("function findButton(", installed_start)
        installed_runtime = js[installed_start:installed_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;const ID=`workshop-runtime`;
window.requestAnimationFrame=callback=>{callback();return 1};window.setTimeout=()=>0;
globalThis.history={state:{},pushState(){},back(){}};
let modalHistoryArmed=false,modalHistoryClosing=false,modalHistoryRearm=false,previousSourceFocus={focus(){}};
const content={children:[],replaceChildren(){this.children=[]},append(...nodes){this.children.push(...nodes)}};
const search={value:``,focus(){}};
const cancelAction={disabled:false};
const attrs={};
let installedDialog={hidden:false,setAttribute(name,value){attrs[name]=String(value)},querySelector(selector){if(selector===`.workshop-installed-content`)return content;if(selector===`.workshop-installed-search`)return search;if(selector===`.workshop-installed-content button`)return findNode(content.children,node=>node.tag===`button`);if(selector===`.workshop-modal-panel > .workshop-modal-action`)return cancelAction;return null}};
function findNode(nodes,predicate){for(const node of nodes||[]){if(predicate(node))return node;const nested=findNode(node.children,predicate);if(nested)return nested}return null}
function findNodes(nodes,predicate,result=[]){for(const node of nodes||[]){if(predicate(node))result.push(node);findNodes(node.children,predicate,result)}return result}
function textNode(tag,cls,text){return{tag,cls,textContent:text,children:[],dataset:{},style:{},disabled:false,setAttribute(name,value){this[name]=value},append(...nodes){this.children.push(...nodes)}}}
function actionButton(label,handler,secondary){const button=textNode(`button`,secondary?`secondary`:`primary`,label);button.onclick=handler;return button}
let installedApps=[],installedLoading=false,installedError=``,installedListEpoch=0,sourceRequestEpoch=0,installedBusy=false;
let fallbackClicks=0;const sourceButton={};function triggerReactButton(){fallbackClicks+=1}

const listResolvers=[];
window.Capacitor={Plugins:{FileManager:{listInstalledApps:()=>new Promise((resolve,reject)=>listResolvers.push({resolve,reject}))}}};

async function main(){
  const first=loadInstalledApps(),second=loadInstalledApps();
  listResolvers[1].resolve({apps:[{label:`New`,packageName:`new.pkg`}]});await second;
  listResolvers[0].resolve({apps:[{label:`Old`,packageName:`old.pkg`}]});await first;
  check(installedApps.length===1&&installedApps[0].packageName===`new.pkg`,`slow old list cannot overwrite fast new list`);

  const beforeClose=installedApps;
  const closing=loadInstalledApps();closeInstalledApps(true);listResolvers[2].resolve({apps:[{label:`Closed stale`,packageName:`closed.pkg`}]});await closing;
  check(installedDialog.hidden&&installedApps===beforeClose,`closed dialog invalidates pending list response`);

  installedDialog.hidden=false;installedApps=[{label:`One`,packageName:`one.pkg`},{label:`Two`,packageName:`two.pkg`}];installedError=``;
  const chooseResolvers={};
  window.Capacitor.Plugins.FileManager.selectInstalledApp=({packageName})=>new Promise((resolve,reject)=>{chooseResolvers[packageName]={resolve,reject}});
  const loaded=[];window.__slgLoadSelectedApk=async selection=>{loaded.push(selection.packageName)};
  const chooseOne=chooseInstalledApp(installedApps[0]);
  const chooseTwo=chooseInstalledApp(installedApps[1]);
  renderInstalledApps();
  check(attrs[`aria-busy`]===`true`,`choose marks dialog aria busy`);
  check(findNodes(content.children,node=>node.tag===`button`).every(button=>button.disabled),`busy disables rows and source operations`);
  check(cancelAction.disabled,`busy disables modal source cancellation action`);
  check(findNode(content.children,node=>node.textContent===`姝ｅ湪璇诲彇搴旂敤瀹夎鍖呪€),`busy copy is visible`);
  chooseResolvers[`two.pkg`].resolve({uri:`file://two.apk`,name:`Two.apk`,packageName:`two.pkg`,source:`installed`});await chooseTwo;
  chooseResolvers[`one.pkg`].resolve({uri:`file://one.apk`,name:`One.apk`,packageName:`one.pkg`,source:`installed`});await chooseOne;
  check(loaded.join(`,`)===`two.pkg`,`stale choose success cannot close or load`);

  installedDialog.hidden=false;modalHistoryArmed=true;
  const staleFailure=chooseInstalledApp({label:`Three`,packageName:`three.pkg`});
  closeInstalledApps();chooseResolvers[`three.pkg`].reject(new Error(`stale select failed`));await staleFailure;
  check(installedDialog.hidden&&!modalHistoryArmed,`stale choose failure cannot rearm or reopen after close`);

  installedDialog.hidden=false;installedApps=[];installedLoading=false;installedError=``;installedBusy=false;renderInstalledApps();
  check(findNode(content.children,node=>node.textContent===`娌℃湁鎵惧埌鍙€夋嫨鐨勫凡瀹夎搴旂敤銆備綘浠嶅彲浠庢枃浠堕€夋嫨 APK銆俙),`complete empty guidance`);
  const fallback=findNode(content.children,node=>node.textContent===`浠庢枃浠堕€夋嫨 APK`);check(fallback,`empty state file fallback exists`);fallback.onclick();
  check(fallbackClicks===1&&installedDialog.hidden,`empty fallback executes React file picker bridge`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", helpers + installed_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_patch_contains_player_workshop_contract(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        for copy in (
            "璁╁枩娆㈢殑鏁呬簨锛岀敤涓枃缁х画銆?",
            "閫夋嫨 APK 鏂囦欢",
            "澶勭悊璇︽儏",
            "绔嬪嵆瀹夎",
            "淇濆瓨 APK",
        ):
            self.assertIn(copy, js)
        compact_css = "".join(css.split())
        for token in (
            "--workshop-primary",
            "prefers-color-scheme:dark",
            "prefers-reduced-motion:reduce",
            "min-height:48px",
        ):
            self.assertIn(token, compact_css)

    def test_patch_installs_visible_android_shell(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        for token in (
            "workshop-runtime",
            "workshop-task-shell",
            "workshop-bottom-nav",
            "workshop-picker-source",
            "data-workshop-state",
            "workshop-state-idle",
            "workshop-state-scanning",
            "workshop-state-ready",
            "workshop-state-translating",
            "workshop-state-patching",
            "workshop-state-completed",
            "workshop-state-failed",
            "setWorkshopState",
            "澶勭悊璇︽儏",
            "姝ｅ湪妫€鏌ユ枃浠?",
            "鍙互寮€濮嬩簡",
            "鎵嬫満绌洪棿涓嶈冻",
            "棣栭〉",
            "瀹夎鍖?",
            "鎴戠殑",
        ):
            self.assertIn(token, js)
        self.assertIn('sourceButton.classList.add("workshop-source-button")', js)
        self.assertIn('triggerReactButton(button)', js)
        self.assertIn('dispatchEvent(new MouseEvent("click"', js)
        self.assertIn('runtimeRoot?.setAttribute("data-workshop-task",task)', js)
        self.assertIn('runtimeRoot=app', js)
        self.assertIn('retryTask({fileName:payload.fileName,raw:""})', js)
        self.assertIn('startButton.classList.add("workshop-start-button")', js)
        self.assertNotIn("hero.append(sourceButton)", js)
        self.assertNotIn("button&&button.click()", js)
        for token in (
            "env(safe-area-inset-top)",
            "env(safe-area-inset-bottom)",
            ".workshop-bottom-nav",
        ):
            self.assertIn(token, css)
        picker_rule = css.split(".workshop-picker-source", 1)[1].split("}", 1)[0]
        self.assertIn(".workshop-picker-source>h2", css)
        self.assertIn("workshop-task-shell", css)
        self.assertIn('workshop-task-shell[data-workshop-state="scanning"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="ready"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="translating"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="patching"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="completed"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="failed"]', css)
        self.assertIn(
            '.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav',
            css,
        )
        self.assertIn(
            '.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav',
            css,
        )
        self.assertIn("min-height:48px", css)
        self.assertNotIn(".workshop-picker-source{display:none!important}", css)
        self.assertNotIn("clip-path", picker_rule)

    def test_runtime_injects_legacy_ui_hide_style_before_mount(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn("#root>div:not(.workshop-runtime)>header", js)
        self.assertIn("bootStyle.textContent=", js)

    def test_mount_creates_shell_before_react_source_button_is_available(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("function mount(){")
        end = js.index("function handleWorkshopPopState(){", start)
        mount_runtime = js[start:end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const ID="workshop-runtime";
let shell=null,runtimeRoot=null,settingsRestored=true,pendingApiKey=null,sourceButton=null,startButton=null,installButton=null;
const app={classList:{classes:[],add(value){this.classes.push(value)},remove(){}},dataset:{},setAttribute(){},children:[],prepend(node){this.children.unshift(node)},append(node){this.children.push(node)},querySelector(){return null}};
const document={querySelector(){return app},querySelectorAll(){return[]},createElement(tag){return{tag,className:"",textContent:"",children:[],dataset:{},style:{},type:"",onclick:null,setAttribute(){},append(...nodes){this.children.push(...nodes)},classList:{add(){},remove(){}}}},head:{appendChild(){}},addEventListener(){}};
globalThis.document=document;
function textNode(tag,cls,text){const el=document.createElement(tag);el.className=cls;if(text!==undefined)el.textContent=text;return el}
function decorate(){} function enableNativeBackHandling(){} function applySettingsToReact(){return false} function readSettingsPrefs(){return{}} function restoreSession(){} function installLocalHooks(){}
function setWorkshopState(state,payload={}){if(!shell)return;shell.dataset.workshopState=state;shell.dataset.workshopTask=state==="idle"?"idle":"active";runtimeRoot?.setAttribute("data-workshop-state",state);runtimeRoot?.setAttribute("data-workshop-task",shell.dataset.workshopTask)}
function refresh(){} function openGallery(){} function openSettings(){}
mount();
check(app.classList.classes.includes(ID),"legacy app root is marked before React source button exists");
check(!!shell&&shell.className==="workshop-task-shell","shell mounts before React source button exists");
'''
        result = subprocess.run(
            ["node", "-e", mount_runtime + behavior_contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_task_runtime_bridges_and_recovery_contract(self):
        """The visible shell must bridge to React without taking ownership of it."""
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        # Native React handlers are reached through a bubbling event, so the
        # picker, start, and retry paths continue to use the existing app API.
        self.assertIn('dispatchEvent(new MouseEvent("click"', js)
        self.assertIn('bubbles:true,cancelable:true,view:window', js)
        self.assertIn('function triggerReactButton(button)', js)
        self.assertIn('actionButton("\u4fdd\u5b58\u8865\u4e01 APK"', js)
        self.assertIn('shell.setAttribute("data-workshop-state",state)', js)
        self.assertRegex(
            js,
            r'shell\.setAttribute\("data-workshop-task",(?:shell\.dataset\.workshopTask|task)\)',
        )
        for state in ("idle", "scanning", "ready", "failed"):
            self.assertIn(f'workshop-state-{state}', js)
            self.assertIn(f'workshop-task-shell[data-workshop-state="{state}"]', css)
        self.assertIn(
            '.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav',
            css,
        )
        self.assertIn(
            '.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav',
            css,
        )
        self.assertIn('.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav{display:grid!important}', css)
        self.assertIn('.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}', css)

        # ENOSPC is recoverable: the user sees a concise localized message,
        # while the raw diagnostic remains behind the details disclosure.
        self.assertIn('ENOSPC|No space left', js)
        self.assertIn('return{state:"failed",reason:"space",raw:failed.textContent}', js)
        self.assertIn('鎵嬫満绌洪棿涓嶈冻', js)
        self.assertIn('閲婃斁绌洪棿鍚庨噸璇?', js)
        self.assertIn('detailToggle(payload.raw||"ENOSPC|No space left")', js)
        self.assertIn('actionButton("閲婃斁绌洪棿鍚庨噸璇?,()=>retryTask({fileName:payload.fileName,raw:""}))', js)

        # Keep React-managed controls mounted and avoid direct click shortcuts;
        # the shell may only dispatch events to those existing nodes.
        for moved_node in ("sourceButton", "startButton"):
            for method in ("append", "appendChild", "prepend", "insertBefore", "replaceChildren"):
                self.assertNotRegex(
                    js,
                    rf'\.\s*{method}\s*\(\s*{moved_node}\b',
                )
        self.assertNotRegex(js, r'\.\s*click\s*\(')

        # A single debounced observer prevents React's intermediate renders
        # from causing duplicate shell mounts or state flicker.
        compact_js = ''.join(js.split())
        self.assertIn('newMutationObserver(schedule)', compact_js)
        self.assertIn('clearTimeout(debounceTimer);debounceTimer=setTimeout(mount,120)', compact_js)
        self.assertIn('observer.observe(document.querySelector("#root")||document.documentElement', compact_js)

    def test_settings_support_provider_model_and_custom_endpoint(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        for token in (
            'const SETTINGS_KEY="slg-workshop-settings-v1"',
            'function readSettingsPrefs()',
            'function saveSettingsPrefs(prefs)',
            'function findReactConfigControls()',
            'function setReactSelectValue(select,value)',
            'function applySettingsToReact(prefs)',
            'localStorage.setItem(SETTINGS_KEY,JSON.stringify(prefs))',
            'provider.id="settingsProvider"',
            'model.id="settingsModel"',
            'customBaseURL.id="settingsCustomBaseURL"',
            'customModel.id="settingsCustomModel"',
            'input.id="settingsApiKey"',
            'option.value="deepseek"',
            'option.value="custom"',
            'https://your-api.com/v1',
            '宸蹭繚瀛橈細',
        ):
            self.assertIn(token, js)
            self.assertIn('min-height:48px', ''.join(css.split()))
            self.assertIn('.workshop-settings-error', css)

    def test_save_transfer_settings_runtime_contract(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        for token in (
            "function refreshSaves()",
            "plugin.restoreSaves",
            "plugin.listSaveBackups",
            "plugin.deleteBackup",
            "plugin.exportSavesToDownloads",
            "plugin.shareSaveBackup",
            "plugin.listSaveArchives",
            "plugin.importSaveBackup",
            "plugin.deleteSaveArchive",
            "plugin.listSaveGameApps",
            "plugin.listInstalledApps",
            "閫夋嫨娓告垙",
            "淇濆瓨瀛樻。",
            "瀵煎叆瀛樻。",
            "瀵煎叆鍒嗕韩瀛樻。",
            "importSelectedPkg",
            "importGameSelect",
            "renderImportArchiveRows",
            "exportBtn.textContent",
            "restore.textContent",
            "share.textContent",
            "del.textContent",
        ):
            self.assertIn(token, js)
        start = js.index("const savesTop=textNode(")
        end = js.index("const cleanupTop=textNode(", start)
        saves_runtime = js[start:end]
        self.assertNotIn("澶囦唤褰撳墠瀛樻。", saves_runtime)
        self.assertNotIn("manageBtn", saves_runtime)
        self.assertNotIn("importGoBtn", saves_runtime)

    def test_save_transfer_runtime_actions_and_state_gating(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("const savesTop=textNode(")
        end = js.index("const importTop=textNode(", start)
        saves_runtime = js[start:end]
        behavior = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
Object.defineProperty(globalThis,"navigator",{value:{userAgent:"Android 12"},configurable:true});
let backups=[{name:"com.sample.game-20260804-120000",path:"/backups/1",fileCount:2,modifiedAt:1}];
const calls={restore:[],delete:[],export:[],share:[],list:0};
window.Capacitor={Plugins:{FileManager:{
  listSaveBackups:async()=>{calls.list++;return{backups}},
  restoreSaves:async input=>{calls.restore.push(input);return{restoredFiles:2}},
  deleteBackup:async input=>{calls.delete.push(input);backups=[];return{deletedFiles:2}},
  exportSavesToDownloads:async input=>{calls.export.push(input);return{path:"/storage/emulated/0/Download/SLG-Translator/saves/com.sample.game.zip",uri:"content://downloads/1",zipFiles:2}},
  shareSaveBackup:async input=>{calls.share.push(input);return{path:"/storage/emulated/0/Download/SLG-Translator/saves/com.sample.game-20260804-120000.zip",shared:true}},
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{}};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children.splice(0,el.children.length,...nodes);for(const node of nodes){node.parent=el;el.children.push(node)}};el.remove=function(){if(this.parent){const index=this.parent.children.indexOf(this);if(index>=0)this.parent.children.splice(index,1)}};el.setAttribute=(name,val)=>{el[name]=val};return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  check(exportBtn.disabled,"save button is disabled before picking a game");
  const topButtons=[...savesCard.children].filter(el=>el.tag==="button"&&!el.hidden);
  check(topButtons.length===2,"save page keeps only game picker and save buttons");
  check(topButtons.some(el=>el.textContent==="閫夋嫨娓告垙")&&topButtons.some(el=>el.textContent==="淇濆瓨瀛樻。"),"save page exposes picker and export intents");
  check(typeof backupBtn==="undefined","backup button is removed from save page");
  savesSelectedPkg="com.sample.game";savesSelectedLabel="Sample Game";updateSavesState();
  check(!exportBtn.disabled,"save-to-download enabled when a game is selected");
  await refreshSaves();
  check(savesList.children.length===1,"list renders one backup row");
  const actions=savesList.children[0].children.find(el=>el.cls==="workshop-save-actions");
  const restore=actions.children.find(el=>el.textContent==="鎭㈠");
  const del=actions.children.find(el=>el.textContent==="鍒犻櫎");
  const share=actions.children.find(el=>el.textContent==="鍒嗕韩");
  check(restore&&share&&del,"row exposes restore, share and delete buttons");
  globalThis.confirm=()=>true;
  await restore.onclick();
  check(calls.restore.length===1&&calls.restore[0].backupDir==="/backups/1"&&calls.restore[0].packageName==="com.sample.game","restore calls native plugin with selected game and backupDir");
  await share.onclick();
  check(calls.share.length===1&&calls.share[0].backupDir==="/backups/1","share calls native plugin with backupDir");
  await del.onclick();
  check(calls.delete.length===1&&calls.delete[0].backupDir==="/backups/1","delete calls native plugin with backupDir");
  check(savesList.children.length===1&&savesList.children[0].textContent==="鏆傛棤澶囦唤銆?,"delete refreshes the list");
  await exportBtn.onclick();
  check(calls.export.length===1&&calls.export[0].packageName==="com.sample.game","save to download calls native plugin with packageName");
  check(exportBtn.textContent==="淇濆瓨瀛樻。"&&!exportBtn.disabled,"save button resets after completion");
  check(permissionNote.textContent.includes("鎵€鏈夋枃浠惰闂?),"Android 11+ shows permission guidance");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + saves_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_save_transfer_can_pick_game_from_installed_apps(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("const savesTop=textNode(")
        end = js.index("const importTop=textNode(", start)
        saves_runtime = js[start:end]
        behavior = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
Object.defineProperty(globalThis,"navigator",{value:{userAgent:"Android 12"},configurable:true});
const calls={listInstalled:0,listGames:0,listBackups:0};
window.Capacitor={Plugins:{FileManager:{
  listInstalledApps:async()=>{calls.listInstalled++;return{apps:[{label:"Chrome",packageName:"com.android.chrome"}]}},
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"鎭跺コ2.2",packageName:"zitao.mbml"},{label:"寮備笘鐣?,packageName:"cim.isekai.game"}]}},
  listSaveBackups:async()=>{calls.listBackups++;return{backups:[]}},
  restoreSaves:async()=>({}),
  deleteBackup:async()=>({}),
  exportSavesToDownloads:async()=>({}),
  shareSaveBackup:async()=>({}),
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{}};el.append=(...nodes)=>el.children.push(...nodes);el.replaceChildren=(...nodes)=>el.children.splice(0,el.children.length,...nodes);el.setAttribute=(name,val)=>{el[name]=val};return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  check(exportBtn.disabled,"save actions are disabled before picking a game");
  await gameBtn.onclick();
  check(calls.listGames===1,"save page game picker loads save-aware apps");
  check(calls.listInstalled===0,"save game picker does not fall back to all installed apps");
  check(gameSelect.children.length===3,"game picker renders placeholder plus apps");
  gameSelect.value="zitao.mbml";gameSelect.onchange();
  check(savesSelectedPkg==="zitao.mbml","picking a game updates the save page local state");
  check(gameLabel.textContent.includes("鎭跺コ2.2"),"picked game name is visible");
  check(!exportBtn.disabled,"picking a game enables save actions");
  check(calls.listBackups>=1,"picking a game refreshes the backup list");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + saves_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_save_transfer_can_import_shared_archive(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("const savesTop=textNode(")
        end = js.index("const cleanupTop=textNode(", start)
        save_import_runtime = js[start:end]
        behavior = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
Object.defineProperty(globalThis,"navigator",{value:{userAgent:"Android 12"},configurable:true});
const calls={listArchives:0,imports:[],deleteArchive:[],listGames:0,listBackups:0};
window.Capacitor={Plugins:{FileManager:{
  listSaveArchives:async()=>{calls.listArchives++;return{archives:[{name:"zitao.mbml-20260805-120000.zip",path:"/downloads/1.zip",size:2048},{name:"renamed.zip",path:"/downloads/2.zip",size:1024}]}},
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"鎭跺コ2.2",packageName:"zitao.mbml"}]}},
  importSaveBackup:async input=>{calls.imports.push(input);return{backupDir:"/backups/imported",name:"imported",fileCount:2,packageName:"zitao.mbml"}},
  deleteSaveArchive:async input=>{calls.deleteArchive.push(input);return{deleted:true}},
  listSaveBackups:async()=>{calls.listBackups++;return{backups:[]}},
  restoreSaves:async()=>({}),
  deleteBackup:async()=>({}),
  exportSavesToDownloads:async()=>({}),
  shareSaveBackup:async()=>({}),
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{}};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children.splice(0,el.children.length,...nodes);for(const node of nodes){node.parent=el;el.children.push(node)}};el.remove=function(){if(this.parent){const index=this.parent.children.indexOf(this);if(index>=0)this.parent.children.splice(index,1)}};el.setAttribute=(name,val)=>{el[name]=val};return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
const importView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  await importGameBtn.onclick();
  check(calls.listGames===1,"import page has its own game picker");
  await importArchiveBtn.onclick();
  check(calls.listArchives===1,"import button scans downloaded archives");
  const archiveSection=importList.children.find(el=>el.cls==="workshop-archive-section"&&!el.hidden);
  const archiveRows=(archiveSection?.children||[]).filter(el=>el.cls==="workshop-save-row"&&el.children.some(c=>c.textContent.endsWith(".zip")));
  check(archiveRows.length===2,"all downloaded archives are shown as importable rows");
  globalThis.confirm=()=>true;
  const delArchive=archiveRows[0].children.find(el=>el.textContent==="鍒犻櫎");
  check(delArchive,"each archive row exposes a delete action");
  await delArchive.onclick();
  check(calls.deleteArchive.length===1&&calls.deleteArchive[0].path==="/downloads/1.zip","delete calls native plugin with selected archive path");
  const remainingSection=importList.children.find(el=>el.cls==="workshop-archive-section"&&!el.hidden);
  const remainingRows=(remainingSection?.children||[]).filter(el=>el.cls==="workshop-save-row"&&el.children.some(c=>c.textContent.endsWith(".zip")));
  check(remainingRows.length===1,"deleted archive is removed from the panel");
  const importOne=remainingRows[0].children.find(el=>el.textContent==="瀵煎叆");
  check(importOne,"remaining archive row exposes an import action");
  await importOne.onclick();
  check(calls.imports.length===1&&calls.imports[0].path==="/downloads/2.zip","import calls native plugin with selected path");
  check(importSelectedPkg==="zitao.mbml","import auto-selects the game from the archive");
  check(importGameSelect.value==="zitao.mbml","import updates the import page game picker");
  check(importGameLabel.textContent.includes("鎭跺コ2.2"),"import page shows the auto-selected game label");
  check(importList.children.length===0,"imported archive is removed from the downloaded panel");
  check(importStatus.textContent.includes("宸插鍏?zitao.mbml 鐨勫瓨妗ｃ€?),"import success message is visible");
  check(importArchiveBtn.textContent==="閲嶆柊閫夋嫨瀛樻。"&&!importArchiveBtn.disabled,"import button resets after completion");
  check(calls.listBackups===0,"import page does not refresh the transfer page backup list");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + save_import_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_save_and_import_game_selection_are_independent(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("const savesTop=textNode(")
        end = js.index("const cleanupTop=textNode(", start)
        save_import_runtime = js[start:end]
        behavior = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
Object.defineProperty(globalThis,"navigator",{value:{userAgent:"Android 12"},configurable:true});
window.Capacitor={Plugins:{FileManager:{
  listSaveGameApps:async()=>({apps:[{label:"鎭跺コ2.2",packageName:"zitao.mbml"},{label:"寮備笘鐣?,packageName:"cim.isekai.game"}]}),
  listSaveBackups:async()=>({backups:[]}),
  restoreSaves:async()=>({}),
  deleteBackup:async()=>({}),
  exportSavesToDownloads:async()=>({}),
  shareSaveBackup:async()=>({}),
  listSaveArchives:async()=>({archives:[]}),
  importSaveBackup:async()=>({}),
  deleteSaveArchive:async()=>({}),
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{}};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children.splice(0,el.children.length,...nodes);for(const node of nodes){node.parent=el;el.children.push(node)}};el.remove=function(){if(this.parent){const index=this.parent.children.indexOf(this);if(index>=0)this.parent.children.splice(index,1)}};el.setAttribute=(name,val)=>{el[name]=val};return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
const importView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  await gameBtn.onclick();
  gameSelect.value="zitao.mbml";gameSelect.onchange();
  await importGameBtn.onclick();
  importGameSelect.value="cim.isekai.game";importGameSelect.onchange();
  check(savesSelectedPkg==="zitao.mbml","save page keeps its own selected game");
  check(importSelectedPkg==="cim.isekai.game","import page keeps its own selected game");
  check(gameLabel.textContent.includes("鎭跺コ2.2"),"save page shows its own game label");
  check(importGameLabel.textContent.includes("寮備笘鐣?),"import page shows its own game label");
  check(gameSelect.value==="zitao.mbml"&&importGameSelect.value==="cim.isekai.game","both selectors preserve independent values");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + save_import_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_install_bridge_refreshes_stale_react_button(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("function triggerReactButton(button)")
        end = js.index("function sourceText()", start)
        trigger_runtime = js[start:end]
        render_start = js.index("function renderStateBody(state,payload)")
        render_end = js.index("function setWorkshopState(state,payload={})", render_start)
        render_runtime = js[render_start:render_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
let dispatched=[];
globalThis.MouseEvent=class{constructor(type,options){this.type=type;this.options=options}};
globalThis.window=globalThis;
let manualIdle=true;
let lastSnapshot=`completed`;
let refreshes=0;
function refresh(){refreshes+=1}
const startButton={textContent:`start`,disabled:false,dispatchEvent(){dispatched.push(`start`)}};
const staleInstall={textContent:`安装补丁版`,disabled:false,isConnected:false,dispatchEvent(){dispatched.push(`stale`)}};
const freshInstall={textContent:`安装补丁版`,disabled:false,isConnected:true,dispatchEvent(){dispatched.push(`fresh`)}};
let installButton=staleInstall;
let currentInstall=freshInstall;
function findButton(label){return label===`安装补丁版`?currentInstall:null}
function readTaskSnapshot(){return{state:`completed`}}
function setWorkshopState(){throw new Error(`unexpected state change`)}
function textNode(tag,cls,text){return{tag,cls,text,children:[],append(...children){this.children.push(...children)}}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary,children:[]}}
triggerReactButton(staleInstall);
check(manualIdle===false,`manual idle reset`);
check(dispatched.length===1&&dispatched[0]===`fresh`,`fresh install target`);

installButton=freshInstall;
const rendered=renderStateBody(`completed`,{fileName:`fixture.apk`,translated:`1`,raw:`done`,installAvailable:true});
const buttons=[];
function visit(node){if(!node)return;if(node.tag===`button`)buttons.push(node);for(const child of node.children||[])visit(child)}
visit(rendered);
const visibleInstall=buttons.find(button=>button.label===`\u76f4\u63a5\u5b89\u88c5`);
check(visibleInstall,`install action rendered`);
dispatched=[];
currentInstall=null;
freshInstall.isConnected=false;
visibleInstall.handler();
check(dispatched.length===0,`detached install target is never dispatched`);
check(lastSnapshot===``, `snapshot invalidated`);
check(refreshes===1,`refresh requested`);
'''
        result = subprocess.run(
            ["node", "-e", trigger_runtime + render_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_completed_shell_only_offers_install_for_a_current_react_action(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn('const currentInstall=findButton("', js)
        self.assertIn('installButton=currentInstall', js)
        self.assertIn('const installAvailable=!!currentInstall?.isConnected', js)
        self.assertIn("renpyLang:window.__slgRenpyLang||''", js)
        self.assertIn("renpyMenuType:window.__slgRenpyMenuType||''", js)
        self.assertIn('window.__slgRenpyLanguages=t.renpyLanguages||[]', js)
        self.assertIn('window.__slgRenpyMenuType=t.renpyMenuType||`none`', js)
        self.assertIn('window.__slgRenpyLang=t.renpyMenuType===`renpy`', js)
        self.assertIn('["继续上次","扫描新增","全部重译"]', js)
        self.assertIn('译文语言："+payload.renpyLang', js)
        self.assertIn('自定义语言系统', js)
        self.assertIn('if(payload.activationMode===`selectable`)card.append(textNode', js)
        self.assertIn('else if(payload.activationMode===`always_on`)card.append(textNode', js)
        self.assertIn('不能切回原文', js)
        self.assertNotIn('window.__slgTranslatorLang===`slgtranslated`)card.append', js)
        self.assertIn('s.installAvailable?"install":""', js)
    def test_translation_cache_is_reused_across_models(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index('var _o=`slg-translator-cache:v2:`')
        end = js.index('function Do()', start)
        cache_runtime = js[start:end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
function legacyKey(scope,text){return _o+scope+`|`+U(text)}

const text=`sample source`;
vo={};cacheIndex={};bo=!1;
vo[legacyKey(`en|zh|model-a|glossary-a`,text)]={sourceText:text,translatedText:`old`,updatedAt:10};
vo[legacyKey(`en|zh|model-b|glossary-a`,text)]={sourceText:text,translatedText:`latest`,updatedAt:30};
vo[legacyKey(`en|zh|model-c|glossary-a`,text)]={sourceText:text,updatedAt:40};
rebuildCacheIndex();
check(To(`en|zh|model-new|glossary-a`,text)===`latest`,`model-independent reuse`);
check(To(`fr|zh|model-new|glossary-a`,text)===null,`source isolation`);
check(To(`en|ja|model-new|glossary-a`,text)===null,`target isolation`);
check(To(`en|zh|model-new|glossary-b`,text)===null,`glossary isolation`);

const pipeText=`pipe model source`;
vo={};cacheIndex={};bo=!1;
vo[legacyKey(`en|zh|vendor|model|glossary-one`,pipeText)]={sourceText:pipeText,translatedText:`pipe-one`,updatedAt:10};
vo[legacyKey(`en|zh|vendor|model|glossary-two`,pipeText)]={sourceText:pipeText,translatedText:`pipe-two`,updatedAt:20};
rebuildCacheIndex();
check(cacheIdentity(`en|zh|vendor|model|glossary-one`,pipeText)!==cacheIdentity(`en|zh|vendor|model|glossary-two`,pipeText),`pipe model glossary boundary`);
check(To(`en|zh|replacement-model|glossary-one`,pipeText)===`pipe-one`,`pipe model first glossary`);
check(To(`en|zh|replacement-model|glossary-two`,pipeText)===`pipe-two`,`pipe model second glossary`);

const preserveText=`preserve source`;
const preserveScope=`en|zh|vendor|model|glossary-keep`;
vo={};cacheIndex={};bo=!1;
const preserveKey=cacheV2Key(preserveScope,preserveText);
const existing={sourceText:preserveText,translatedText:`preserved`,updatedAt:5};
vo[preserveKey]=existing;
rebuildCacheIndex();
Eo(preserveScope,preserveText,`replacement`);
check(preserveKey.startsWith(_o+`v2|`),`v2 key prefix`);
check(vo[preserveKey]===existing,`existing v2 object preservation`);
check(To(preserveScope,preserveText)===`preserved`,`existing v2 value preservation`);
check(cacheIndex[cacheIdentity(preserveScope,preserveText)]===existing,`existing v2 index preservation`);
check(To(`en|zh|other-model|glossary-keep`,preserveText)===`preserved`,`preserved v2 cross-model reuse`);
check(bo===!1,`preserved v2 is not marked dirty`);
'''
        result = subprocess.run(
            ["node", "-e", cache_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(
            'def patch_translation_cache(js: str) -> str:',
            Path(module.__file__).read_text("utf-8"),
        )

    def test_network_failures_stop_batches_without_recursive_splitting(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        for token in (
            'function isNetworkFailure(e)',
            'function providerLabel(e)',
            'maxRetries:1',
            'if(isNetworkFailure(e))throw e',
            'b=y.length',
            'P=providerLabel(i)',
            '鏃犳硶杩炴帴 ${P}',
            '鍓嶅線鈥滄垜鐨勨€濆垏鎹緵搴斿晢',
        ):
            self.assertIn(token, js)
        self.assertNotIn('maxRetries:2', js)
        self.assertIn('let c=Math.ceil(n.length/2)', js)

        helpers_start = js.index('function isNetworkFailure(e)')
        coordinator_end = js.index('function Ro(e)', helpers_start)
        split_start = js.index('async function Bo(', coordinator_end)
        split_end = js.index('async function Vo(', split_start)
        coordinator = js[helpers_start:coordinator_end]
        recursive_split = js[split_start:split_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  const sdkError=new Error(`Connection error`);
  sdkError.name=`APIConnectionError`;
  sdkError.cause={code:`ETIMEDOUT`};
  check(isNetworkFailure(new Error(`net::ERR_CONNECTION_TIMED_OUT`)),`browser timeout classification`);
  check(isNetworkFailure(new Error(`net::ERR_CONNECTION_REFUSED`)),`browser refused classification`);
  check(isNetworkFailure(new Error(`net::ERR_INTERNET_DISCONNECTED`)),`browser offline classification`);
  check(isNetworkFailure(new Error(`net::ERR_NAME_NOT_RESOLVED`)),`browser name resolution classification`);
  check(isNetworkFailure(new Error(`DNS_PROBE_FINISHED_NXDOMAIN`)),`browser DNS probe classification`);
  check(isNetworkFailure(new Error(`net::ERR_CONNECTION_RESET`)),`browser reset classification`);
  check(isNetworkFailure(new Error(`net::ERR_TIMED_OUT`)),`browser timed-out classification`);
  check(isNetworkFailure(sdkError),`SDK connection classification`);
  check(isNetworkFailure({cause:{code:`EAI_AGAIN`}}),`nested cause classification`);
  check(isNetworkFailure(new Error(`Failed-to-fetch`)),`failed-to-fetch classification`);
  check(!isNetworkFailure(new Error(`ERR_INVALID_JSON`)),`ERR_INVALID_JSON content classification`);
  check(!isNetworkFailure(new Error(`translation connection count mismatch`)),`arbitrary connection classification`);
  check(!isNetworkFailure(new Error(`network glossary entry is invalid`)),`arbitrary network classification`);
  check(providerLabel(`https://api.deepseek.com/v1`)===`DeepSeek`,`DeepSeek label`);
  check(providerLabel(`https://api.openai.com/v1`)===`OpenAI`,`OpenAI label`);
  check(providerLabel(`https://example.invalid/v1`)===`鑷畾涔夋帴鍙,`custom label`);

  for(const message of [
    `API returned empty content`,
    `Invalid translation JSON`,
    `Translation count mismatch`,
    `ERR_INVALID_JSON`,
  ]){
    const calls=[];
    globalThis.Vo=async(_client,_model,batch)=>{
      calls.push(batch.length);
      if(batch.length>1)throw new Error(message);
      return new Map([[0,`ok`]]);
    };
    const result=await Bo({},`model`,[{},{},{},{}],`en`,`zh`,void 0,!0);
    check(result.translations.size===4,`${message} remains splittable`);
    check(calls.join(`,`)===`4,2,1,1,2,1,1`,`${message} recursive split shape`);
  }

  let networkCalls=0;
  globalThis.Vo=async()=>{networkCalls+=1;throw sdkError};
  let rejected=false;
  try{await Bo({},`model`,[{},{},{},{}],`en`,`zh`,void 0,!0)}catch(error){rejected=error===sdkError}
  check(rejected,`network error escapes recursive split`);
  check(networkCalls===1,`network request is not recursively retried`);

  globalThis.Co=async()=>{};
  globalThis.No=texts=>texts;
  globalThis.xo=()=>`scope`;
  globalThis.Se=()=>null;
  globalThis.To=(_scope,text)=>text===`cached`?`cached translation`:null;
  globalThis.Wo=(map,item,value)=>map.set(item.id,value);
  globalThis.Eo=()=>{};
  globalThis.wo=async()=>{};
  globalThis.H=class{};
  globalThis.zo=items=>items.map(item=>[item]);
  globalThis.Ro=item=>item;
  globalThis.Ao=2;
  globalThis.jo=1;
  globalThis.Ko=()=>0;
  let resolveInflight;
  const inflight=new Promise(resolve=>{resolveInflight=resolve});
  const started=[];
  globalThis.Vo=async(_client,_model,batch)=>{
    const id=batch[0].id;
    started.push(id);
    if(id===`network`)throw sdkError;
    if(id===`inflight`)return inflight;
    throw new Error(`unexpected batch ${id}`);
  };
  const texts=[
    {id:`cached`,text:`cached`,duplicateKeys:[]},
    {id:`network`,text:`network request`,duplicateKeys:[]},
    {id:`inflight`,text:`inflight request`,duplicateKeys:[]},
    {id:`never`,text:`must not start`,duplicateKeys:[]},
  ];
  let settled=false;
  const task=Lo({texts,sourceLang:`en`,targetLang:`zh`,baseURL:`https://api.deepseek.com/v1`,apiKey:`test-key`,model:`test-model`,batchSize:1}).then(result=>{settled=true;return result});
  await new Promise(resolve=>setTimeout(resolve,0));
  check(started.join(`,`)===`network,inflight`,`workers stop acquiring after fatal network error`);
  check(!settled,`coordinator waits for current in-flight work`);
  resolveInflight(new Map([[0,`translated inflight`]]));
  const result=await task;
  check(started.join(`,`)===`network,inflight`,`no later batch starts after in-flight settles`);
  check(result.successCount===2,`cache and in-flight partial results survive`);
  check(result.error===`鏃犳硶杩炴帴 DeepSeek銆傝妫€鏌ョ綉缁滐紝鎴栧墠寰€鈥滄垜鐨勨€濆垏鎹緵搴斿晢銆俙,`actionable fatal error survives partial results`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", coordinator + recursive_split + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_fatal_network_stops_outer_file_controller(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn('async function runFileTasksParallel(e,t,concurrency=3)', js)
        self.assertIn('N=await runFileTasksParallel(ae,async(o,c)=>{', js)
        self.assertIn('...r?{error:N||`閮ㄥ垎鏂囦欢澶勭悊澶辫触锛岃鏌ョ湅鏃ュ織`}:{}', js)

        start = js.index('async function runFileTasksParallel(e,t,concurrency=3)')
        end = js.index('async function Lo(e){', start)
        scheduler = js[start:end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  const fatal=`鏃犳硶杩炴帴 OpenAI銆傝妫€鏌ョ綉缁滐紝鎴栧墠寰€鈥滄垜鐨勨€濆垏鎹緵搴斿晢銆俙;
  const started=[];
  const result=await runFileTasksParallel([`file-1`,`file-2`,`file-3`],async file=>{
    started.push(file);
    if(file===`file-1`)return fatal;
    await new Promise(r=>setTimeout(r,5));
    return ``;
  },2);
  check(started.includes(`file-1`)&&started.includes(`file-2`),`two files start concurrently`);
  check(!started.includes(`file-3`),`third file does not start after fatal`);
  check(result===fatal,`task-wide fatal result survives`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", scheduler + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_partial_network_failure_never_writes_or_packages(self):
        """A fatal provider outage must discard partial file output and packaging."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        controller_start = js.index("N=await runFileTasksParallel")
        network_check = js.index("m&&isProviderNetworkFailure(m)", controller_start)
        result_start = network_check - 3 if js[network_check - 3 : network_check] == "if(" else network_check
        result_end = js.index("t+=p,O(", result_start)
        file_result = js[result_start:result_end]

        build_call = js.index("await E.buildPatchedApk", result_end)
        package_guard_start = js.rfind("if(", controller_start, build_call)
        package_guard_end = js.index("){", package_guard_start) + 1
        package_guard = js[package_guard_start:package_guard_end]

        behavior_contract = rf'''
function check(condition,label){{if(!condition)throw new Error(label)}}
const fatal=`fatal provider network`;
let writes=0,builds=0;
function isProviderNetworkFailure(error){{return error===fatal}}
function O(){{}}
function ue(){{}}
function ns(){{return true}}
function rs(_file,_items,_translations,language){{return{{outputPath:`tl/${{language}}.rpy`,content:`translated`}}}}
async function Ne(){{writes+=1}}
async function wo(){{}}
function qe(){{return `translated`}}
const E={{buildPatchedApk:async()=>{{builds+=1}}}};

async function simulatePartialFile(){{
  let N=``,r=false,p=2,m=fatal,a=[],o={{name:`script.rpy`}},l=[{{}},{{}}],f=new Map(),g=`zh`,y=`en`,oe=false,i=``,s=`rpy`,t=0,c=0,ae=[o],_fk=`cache-key`,vo={{}},bo=false;
  {file_result}
  return N;
}}

async function simulatePackaging(){{
  let N=fatal,a=[{{path:`cached/partial.rpy`,content:`cached`}}],oe=false;
  {package_guard}{{await E.buildPatchedApk()}}
}}

async function main(){{
  const result=await simulatePartialFile();
  check(result===fatal,`fatal network result survives partial success`);
  check(writes===0,`fatal network does not write partial translations`);
  await simulatePackaging();
  check(builds===0,`fatal network does not package cached or partial files`);
}}
main().catch(error=>{{console.error(error);process.exitCode=1}});
'''
        result = subprocess.run(
            ["node", "-e", behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_network_failure_preempts_stale_translating_ui(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn('reason:"network"', js)
        self.assertIn('if(payload.reason==="network")', js)
        self.assertIn('actionButton("鍓嶅線鈥滄垜鐨勨€濆垏鎹緵搴斿晢",openSettings)', js)
        self.assertIn('actionButton("閲嶈瘯缈昏瘧",()=>retryTask(', js)

        snapshot_start = js.index('function readTaskSnapshot(){')
        snapshot_end = js.index('function detailToggle(', snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        render_start = js.index('function renderStateBody(')
        render_end = js.index('function setWorkshopState(', render_start)
        render_runtime = js[render_start:render_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const fatal=`鏃犳硶杩炴帴 DeepSeek銆傝妫€鏌ョ綉缁滐紝鎴栧墠寰€鈥滄垜鐨勨€濆垏鎹緵搴斿晢銆俙;
function sourceText(){return `姝ｅ湪澶勭悊鑴氭湰 1 / 2\n缈昏瘧涓璡n缈昏瘧澶辫触: ${fatal}`}
function readProgressLog(){return{raw:`stale translating log`,latest:`stale translating log`}}
const document={querySelectorAll(){return[]}};
globalThis.findButton=()=>null;
const snapshot=readTaskSnapshot();
check(snapshot.state===`failed`,`network failure beats stale translating state`);
check(snapshot.reason===`network`,`network failure reason`);
check(snapshot.raw===fatal,`actionable failure message preserved`);

function textNode(tag,cls,text){return{tag,cls,text,children:[],append(...children){this.children.push(...children)}}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
let opened=0,retried=0;
function openSettings(){opened+=1}
function retryTask(){retried+=1}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary}}
const body=renderStateBody(`failed`,{reason:`network`,raw:fatal,fileName:`game.apk`});
const buttons=[];
function visit(node){if(!node)return;if(node.tag===`button`)buttons.push(node);for(const child of node.children||[])visit(child)}
visit(body);
const settings=buttons.find(button=>button.label===`鍓嶅線鈥滄垜鐨勨€濆垏鎹緵搴斿晢`);
const retry=buttons.find(button=>button.label===`閲嶈瘯缈昏瘧`);
check(settings&&retry,`network failure renders recovery actions`);
settings.handler();retry.handler();
check(opened===1&&retried===1,`recovery actions are wired`);
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + render_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_long_running_phases_are_not_reported_as_directory_scanning(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        self.assertIn(
            r'if(/\u7ffb\u8bd1\u5b8c\u6210/.test(text)&&/\u5199\u5165\u8865\u4e01|\u8865\u4e01 APK \u5df2\u751f\u6210|\u5df2\u751f\u6210\u8865\u4e01/.test(text)){const patchedApkPath=',
            js,
        )
        self.assertIn('const progress=text.match(/姝ｅ湪澶勭悊鑴氭湰\\s*(\\d+)\\s*\\/\\s*(\\d+)/)', js)
        self.assertIn('if(state==="translating")', js)
        self.assertIn('姝ｅ湪缈昏瘧鏂囨湰', js)
        self.assertIn('if(state==="patching")', js)
        self.assertIn('姝ｅ湪鐢熸垚琛ヤ竵 APK', js)
        self.assertIn('if(state==="completed")', js)
        self.assertIn('琛ヤ竵 APK 宸茬敓鎴?', js)
        self.assertIn('actionButton("\u4fdd\u5b58\u8865\u4e01 APK"', js)
        self.assertIn('state==="scanning"?startScanClock():stopScanClock()', js)
        self.assertIn('characterData:true', ''.join(js.split()))
        for state in ("translating", "patching", "completed"):
            self.assertIn(f'workshop-state-{state}', js)
            self.assertIn(
                f'workshop-task-shell[data-workshop-state="{state}"]', css
            )

    def test_completed_zero_entry_scan_is_an_empty_result_not_scanning(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        snapshot_start = js.index("function readTaskSnapshot()")
        snapshot_end = js.index("function detailToggle(", snapshot_start)
        snapshot = js[snapshot_start:snapshot_end]
        contract = r'''
globalThis.window=globalThis;
window.__slgSelectionError=null;
window.__slgSelectionEpoch=7;
window.__slgSelectionMeta={splitApk:true,splitCount:4};
window.__slgScanWatchdog={epoch:7,timerFired:false,settled:true,applied:false};
function sourceText(){return `SLG 鏂囨湰缈昏瘧 璁＄畻鍣?apk 路 0 涓剼鏈?宸查€夋嫨锛氳绠楀櫒.apk`}
function readProgressLog(){return {raw:``,latest:``}}
globalThis.document={querySelectorAll(){return []}};
const result=readTaskSnapshot();
if(result.state!==`empty`||result.count!==`0`||result.fileName!==`璁＄畻鍣?apk`||!result.splitApk||result.splitCount!==4){
  throw new Error(`settled zero-entry scan misclassified: ${JSON.stringify(result)}`)
}
'''
        result = subprocess.run(
            ["node", "-e", snapshot + contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('split?"璇ュ簲鐢ㄤ娇鐢ㄦ媶鍒嗗畨瑁呭寘"', js)
        self.assertIn('鍏?${payload.splitCount||0} 涓媶鍒嗗寘', js)

    def test_translation_logs_are_mirrored_into_the_visible_shell(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        self.assertIn('function readProgressLog()', js)
        self.assertIn('querySelectorAll("#root details")', js)
        self.assertIn('querySelector(\'[class*="font-mono"]\')', js)
        self.assertIn('.slice(-40)', js)
        self.assertIn(
            'return{raw:lines.join("\\n"),latest:lines.at(-1)||""}', js
        )
        self.assertGreaterEqual(js.count('raw:log.raw,latest:log.latest'), 3)
        self.assertIn('workshop-live-line', js)
        self.assertIn('workshop-live-line', css)
        self.assertIn('detailsOpen=false', js)
        self.assertIn('_k.startsWith(`slg-file-v1:`)', js)
        self.assertIn('_lastSaveAt', js)
        self.assertIn('selectInstalledApp({packageName:window.__slgSelectionMeta.packageName', js)
        self.assertIn('window.__slgSelectionMeta?.uri||n', js)
        self.assertIn('No such file|Failed to build patched APK', js)

        self.assertIn('detailsOpen=false,scanStartedAt=0,scanTimer=0,sessionRestoredAt=0,sessionLastBeat=0,manualIdleBeforeOverlay=false,restoringSession=false,galleryShell=null,galleryOpen=false,galleryPatches=[],galleryLoading=false,galleryError=\'\';', js)
        self.assertIn('body.dataset.open=String(detailsOpen)', js)
        self.assertIn('body.scrollTop=body.scrollHeight', js)
        compact_css = ''.join(css.split())
        self.assertIn('max-height:240px', compact_css)
        self.assertIn('overflow:auto', compact_css)


    def test_ready_mode_selector_and_completed_language_guidance(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn('window.__slgRenpyLanguages=t.renpyLanguages||[]', js)
        self.assertIn('window.__slgRenpyMenuType=t.renpyMenuType||`none`', js)
        self.assertIn('window.__slgRenpyLang=t.renpyMenuType===`renpy`', js)
        self.assertIn('renpyLang:window.__slgRenpyLang||\'\'', js)
        self.assertIn('renpyMenuType:window.__slgRenpyMenuType||\'\'', js)
        self.assertIn('["\u7ee7\u7eed\u4e0a\u6b21","\u626b\u63cf\u65b0\u589e","\u5168\u90e8\u91cd\u8bd1"]', js)
        self.assertIn('window.__slgTranslatorLang=\'\'', js)
        self.assertIn('E.injectTranslatorMenu({apkUri:e.uri', js)
        self.assertIn("translatorLang:'slgtranslated'", js)
        self.assertIn("o.fileType===`rpyc`?await E.readRenpyTexts(", js)
        self.assertIn("_map.set(r.text,v)", js)
        self.assertNotIn("let _map=new Map(_fr.translations)", js)
        self.assertIn('if(globalThis.__slgTranslatorLang)return globalThis.__slgTranslatorLang', js)
        self.assertIn("_m.ready", js)
        self.assertIn("window.__slgSelectionMeta?.packageName||n", js)
        self.assertIn("Array.isArray(_fr.translations)", js)
        self.assertIn("translations:Array.from(f.entries())", js)

        self.assertIn("activationMode:window.__slgActivationMode||'always_on'", js)
        self.assertIn("window.__slgActivationMode=(_m&&_m.ready)?`selectable`:`always_on`", js)
        self.assertIn("请在游戏设置中选择翻译文本查看译文", js)
        self.assertIn("此游戏不支持可靠的语言菜单注入", js)
        self.assertIn('window.__slgTranslatorLang=\'\'', js)
        self.assertIn('E.injectTranslatorMenu({apkUri:e.uri', js)
        self.assertIn("translatorLang:'slgtranslated'", js)
        self.assertIn('if(globalThis.__slgTranslatorLang)return globalThis.__slgTranslatorLang', js)
        self.assertIn("_m.ready", js)
        self.assertIn("window.__slgSelectionMeta?.packageName||n", js)
        self.assertIn("Array.isArray(_fr.translations)", js)
        self.assertIn("translations:Array.from(f.entries())", js)


        snapshot_start = js.index('function readTaskSnapshot(){')
        snapshot_end = js.index('function detailToggle(', snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        render_start = js.index('function renderStateBody(')
        render_end = js.index('function setWorkshopState(', render_start)
        render_runtime = js[render_start:render_end]
        behavior_contract = r"""
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
globalThis.localStorage={getItem(){return null},removeItem(){},setItem(){}};
const SESSION_KEY=`slg-workshop-session-v1`;
let sessionRestoredAt=0;
let installButton=null;
const clicked=[];
window.__slgRenpyLang=`schinese`;
window.__slgRenpyMenuType=`renpy`;
function sourceText(){return `\u7ffb\u8bd1\u5b8c\u6210\n\u5df2\u5199\u5165\u8865\u4e01 APK: /sdcard/SLG-Translator/Game-patched-signed.apk`}
function readProgressLog(){return{raw:`done`,latest:`done`}}
const document={querySelectorAll(){return[]}};
const snapshot=readTaskSnapshot();
check(snapshot.state===`completed`,`completed snapshot recognized`);
check(snapshot.renpyLang===`schinese`&&snapshot.renpyMenuType===`renpy`,`language metadata flows into snapshot`);

function textNode(tag,cls,text){return{tag,cls,text,children:[],dataset:{},style:{},append(...children){this.children.push(...children)}}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary,children:[]}}
function recoveryBanner(){return textNode(`section`,`banner`,`banner`)}
function savePatchedApk(){}
function triggerReactButton(){}
const startButton=null;
globalThis.MouseEvent=class{constructor(type,options){this.type=type;this.options=options}};
function findButton(label){clicked.push(label);return{dispatchEvent(){}}}
function clickReact(label){const b=findButton(label);if(b){b.dispatchEvent(new MouseEvent(`click`,{bubbles:true,cancelable:true,view:window}));return true}return false}

globalThis.__slgHasHistory=()=>true;
window.__slgSelectionMeta={packageName:`zitao.mbml`};
const readyBody=renderStateBody(`ready`,{fileName:`Game.apk`,count:`12`,sessionRestoredAt:0});
const readyButtons=[];
function visit(node){if(!node)return;if(node.tag===`button`)readyButtons.push(node);for(const child of node.children||[])visit(child)}
visit(readyBody);
const labels=readyButtons.map(b=>b.label);
check(labels.includes(`\u7ee7\u7eed\u4e0a\u6b21`)&&labels.includes(`\u626b\u63cf\u65b0\u589e`)&&labels.includes(`\u5168\u90e8\u91cd\u8bd1`),`ready shell offers three task modes`);
const resume=readyButtons.find(b=>b.label===`\u7ee7\u7eed\u4e0a\u6b21`);
resume.handler();
check(clicked.includes(`\u7ee7\u7eed\u4e0a\u6b21`),`mode buttons bridge to React actions`);

const completedBody=renderStateBody(`completed`,{fileName:`Game.apk`,count:`12`,translated:`34`,renpyLang:`chinese`,renpyMenuType:`renpy`,patchedApkPath:`/sdcard/Game-patched-signed.apk`,raw:`done`,latest:``,installAvailable:false});
const texts=[];
function collectText(node,into){if(node&&node.text!==undefined)into.push(String(node.text));for(const child of node.children||[])collectText(child,into)}
collectText(completedBody,texts);
check(texts.some(t=>t.includes(`\u8bd1\u6587\u8bed\u8a00\uff1achinese`)),`completed shell shows translation language`);
check(texts.some(t=>t.includes(`\u5728\u6e38\u620f\u8bbe\u7f6e\u7684\u8bed\u8a00\u4e2d\u9009\u62e9\u5bf9\u5e94\u9009\u9879\u5373\u53ef\u67e5\u770b\u8bd1\u6587`)),`completed shell explains the language menu step`);

const customBody=renderStateBody(`completed`,{fileName:`Game.apk`,translated:`34`,renpyLang:``,renpyMenuType:`custom`,raw:`done`,latest:``,installAvailable:false});
const customTexts=[];
collectText(customBody,customTexts);
check(customTexts.some(t=>t.includes(`\u81ea\u5b9a\u4e49\u8bed\u8a00\u7cfb\u7edf`)),`custom language menu warning rendered`);
"""
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + render_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


    def test_gallery_lists_patches_and_idle_topbar_hides_back(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        for token in (
            "function openGallery()",
            "function closeGallery(",
            "function renderGallery()",
            "async function loadPatches()",
            "function formatBytes(bytes)",
            "listPatchedApks",
            '["\u9996\u9875",()=>window.scrollTo({top:0,behavior:"smooth"})],["\u5b89\u88c5\u5305",openGallery],["\u6211\u7684",openSettings]',
            'if(state!=="idle"){const back=',
            "if(galleryOpen){modalHistoryArmed=false;closeGallery(true);return}",
            "if(galleryOpen){closeGallery();return true}",
            "galleryShell=null,galleryOpen=false,galleryPatches=[]",
            "const host=galleryOpen&&galleryShell?galleryShell:shell;",
            "if(galleryOpen)loadPatches()",
            "\\u4fdd\\u5b58\\u5230\\u4e0b\\u8f7d",
            "\\u6211\\u7684\\u8865\\u4e01",
            'actionButton("\u4fdd\u5b58\u8865\u4e01 APK"',
        ):
            self.assertIn(token, js)
        compact_css = "".join(css.split())
        for token in (".workshop-gallery-shell", ".workshop-patch-row", ".workshop-patch-save"):
            self.assertIn(token, compact_css)

        topbar_start = js.index("function renderTopbar(state)")
        topbar_end = js.index("function fileRow(", topbar_start)
        topbar = js[topbar_start:topbar_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
function textNode(tag,cls,text){return{tag,cls,text,children:[],setAttribute(){},append(...children){this.children.push(...children)}}}
function setWorkshopState(){}
const idle=renderTopbar(`idle`);
check(idle.children.length===2,`idle topbar has no back button`);
check(idle.children.every(el=>el.tag!==`button`),`idle topbar renders only heading and state`);
const ready=renderTopbar(`ready`);
check(ready.children.some(el=>el.tag===`button`&&el.text===`\u2039 \u8fd4\u56de`),`active topbar keeps back button`);
'''
        result = subprocess.run(
            ["node", "-e", topbar + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


    def test_candidate_filter_drops_tl_duplicates_and_crashes_never(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("var qo=new Set(")
        end = js.index("function rs(e,t,n,r)", start)
        runtime = js[start:end]
        contract = (
            "function check(condition,label){if(!condition)throw new Error(label)}\n"
            "const entries=[\n"
            "  {name:'assets/x-game/x-ch1ep1.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-ch1ep1.rpy',fileType:'rpy'},\n"
            "  {name:'assets/x-game/x-tl/x-chinese/x-ch1ep1.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-tl/x-english/x-ch1ep1.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-tl/x-german/x-ch1ep1.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-tl/x-slgtranslated/x-ch1ep1.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-gui.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-renpy/x-common/x-00gamemenu.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-special.rpyc',fileType:'rpyc'},\n"
            "  {name:'assets/x-game/x-special.rpy',fileType:'rpy'}\n"
            "];\n"
            "const result=Jo(entries,`all`,`zh`);\n"
             "check(result.length===4,`story + source translation bucket kept: `+result.length);\n"
             "check(result.some(e=>e.name.includes(`x-00gamemenu.rpyc`)),`engine common kept`);\n"
             "check(result.every(e=>e.fileType===`rpyc`),`compiled variant wins`);\n"
             "check(result.every(e=>!e.name.includes(`x-tl/x-chinese/x-ch1ep1.rpyc`)),`chinese tl bucket skipped as target`);\n"
             "check(result.some(e=>e.name.includes(`x-tl/x-english/x-ch1ep1.rpyc`)),`english tl bucket kept as corpus`);\n"
            "check(result.every(e=>!e.name.includes(`x-tl/x-german`)),`unrelated german tl bucket excluded`);\n"
            "check(result.every(e=>!e.name.includes(`x-slgtranslated`)),`slgtranslated bucket excluded`);\n"
            "check(result.some(e=>e.name.includes(`x-ch1ep1.rpyc`)),`story kept`);\n"
            "check(result.some(e=>e.name.includes(`x-special.rpyc`)),`special kept`)\n"
        )
        result = subprocess.run(
            ["node", "-e", runtime + contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_rpyc_string_pipeline_keeps_story_text_and_roundtrips_newlines(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        ne_start = js.index("function Ne(e,t=``,n)")
        ne_end = js.index("function Pe(", ne_start)
        ne = js[ne_start:ne_end]
        self.assertNotIn("!He(e,n)", ne)
        self.assertIn("e=e.replace(/\\\\(?:\\\\|n|r|t)/g", ne)
        self.assertIn("let i=r.text,a=e.trim();", js)
        self.assertNotIn("let i=r.text.trim(),a=e.trim();", js)
        self.assertIn("cleanupStorage", js)
        self.assertIn("娓呯悊瀹夎鍖呬笌鏃х紦瀛?", js)
        self.assertIn("workshop-settings-cleanup", js)
        self.assertIn("workshop-settings-cleanup", js)
        self.assertIn("瀛樻。杞Щ", js)
        self.assertIn("缁х画涓婃鍙炕璇戞柊澧炴枃鏈紙鎺ㄨ崘锛?", js)
        self.assertIn("return`assets/x-game/x-tl/x-${t}/${n.at(-1)||`strings`}.rpy`}", js)
        self.assertNotIn("return`tl/${t}/${n.at(-1)||`strings`}.rpy`}", js)
        lines = [
            "RPYC_STRING\tSaturday, early morning...",
            "RPYC_STRING\t{i}I cosplay and wear dresses I like for my viewers to see.{w} \\nIt must be nice, then?",
            "RPYC_STRING\tIf Aine really does have feelings for me... Then, I honestly don't know what I should do about it.",
            "RPYC_STRING\tWith all that said... I'm still quite interested in ya.",
            "RPYC_STRING\tStop it. There is no point talking about a person who's no longer here.",
            "RPYC_STRING\tEnter{#ep2}",
            "RPYC_STRING\tTease her",
            "RPYC_STRING\tFine",
            "RPYC_STRING\tSky",
            "RPYC_STRING\tstatement_start",
            "RPYC_STRING\t Alright, but before I go...",
            "not a rpyc line",
        ]
        harness = """
%s
const joined = [%s].join(String.fromCharCode(10));
const out = Ne(joined, "f", "en").map(x => x.text);
for (const want of ["If Aine really does have feelings for me... Then, I honestly don't know what I should do about it.", "With all that said... I'm still quite interested in ya.", "Stop it. There is no point talking about a person who's no longer here.", "Enter{#ep2}", "Fine", "Sky"]) {
  if (!out.includes(want)) throw new Error("missing: " + want);
}
if (!out.includes(" Alright, but before I go...")) throw new Error("leading whitespace must be preserved");
const nl = out.filter(x => x.includes("cosplay"));
if (nl.length !== 1 || !nl[0].includes(String.fromCharCode(10))) throw new Error("newline round-trip failed");
if (out.some(x => x.startsWith("not "))) throw new Error("non-RPYC line leaked");
console.log("ok");
"""
        js_lines = ", ".join(repr(line) for line in lines)
        result = subprocess.run(
            ["node", "-e", harness % (ne, js_lines)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

        os_start = js.index("function os(e,t){")
        os_end = js.index("function cs(e,t,n){", os_start)
        os_code = js[os_start:os_end]
        os_harness = """
%s
const engine = os('assets/x-renpy/x-common/x-00preferences.rpyc', 'slgtranslated');
if (engine !== 'assets/x-game/x-tl/x-slgtranslated/x-00preferences.rpy') throw new Error('engine path: ' + engine);
const story = os('assets/x-game/x-ch1ep1.rpyc', 'slgtranslated');
if (story !== 'assets/x-game/x-tl/x-slgtranslated/x-ch1ep1.rpy') throw new Error('story path: ' + story);
console.log('ok');
"""
        result = subprocess.run(
            ["node", "-e", os_harness % os_code],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


    def test_dismiss_recovery_banner_re_renders_immediately(self):
        """Dismissing the interrupted-session banner must re-render right away."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        snapshot_start = js.index("function readTaskSnapshot(){")
        snapshot_end = js.index("function detailToggle(", snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        topbar_start = js.index("function renderTopbar(state)")
        topbar_end = js.index("function fileRow(", topbar_start)
        topbar_runtime = js[topbar_start:topbar_end]
        render_start = js.index("function renderStateBody(state,payload)")
        render_end = js.index("function setWorkshopState(", render_start)
        render_runtime = js[render_start:render_end]
        state_start = render_end
        state_end = js.index("function snapshotKey(", state_start)
        state_runtime = js[state_start:state_end]
        key_start = js.index("function snapshotKey(s){")
        key_end = js.index("function retryTask(", key_start)
        key_runtime = js[key_start:key_end]
        refresh_start = js.index("function refresh(){")
        refresh_end = js.index("function decorate(){", refresh_start)
        refresh_runtime = js[refresh_start:refresh_end]
        recovery_start = js.index("function recoveryBanner(savedAt){")
        recovery_end = js.index("function mount(){", recovery_start)
        recovery_runtime = js[recovery_start:recovery_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}};
const document={querySelectorAll(){return[]}};
let detailsOpen=false,manualIdle=false,retrying=false,settingsOpen=false,lastSnapshot="",sessionRestoredAt=0;
function sourceText(){return`宸查€夋嫨锛欱roken.apk鍙戠幇 5 涓彲缈昏瘧鏂囦欢`}
function readProgressLog(){return{raw:"",latest:""}}
function textNode(tag,cls,text){return{tag,cls,text,children:[],dataset:{},style:{},setAttribute(){},append(...children){this.children.push(...children)}}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary,children:[]}}
function openSourceChooser(){} function openSettings(){} function retryTask(){} function triggerReactButton(){}
const startButton=null,installButton=null,sourceButton=null;
function startScanClock(){} function stopScanClock(){}
function classList(){return{remove(){},add(){}}}
let shell={dataset:{},classList:classList(),setAttribute(){},replaceChildren(...nodes){this.rendered=nodes}};
const runtimeRoot={classList:classList(),setAttribute(){}};
function collectText(node){let out=node.text||"";for(const child of node.children||[])out+=collectText(child);return out}
function collectButtons(node,acc){if(!node)return acc;if(node.tag===`button`)acc.push(node);for(const child of node.children||[])collectButtons(child,acc);return acc}
sessionRestoredAt=123;
refresh();
let buttons=collectButtons(shell.rendered[1],[]);
const dismiss=buttons.find(b=>(b.label||b.text)===`鏀惧純鎭㈠`);
check(dismiss,`recovery banner offers dismiss`);
check(collectText(shell.rendered[1]).includes(`涓婃缈昏瘧涓柇`),`banner visible before dismiss`);
dismiss.onclick();
check(sessionRestoredAt===0,`dismiss clears restored marker`);
check(!collectText(shell.rendered[1]).includes(`涓婃缈昏瘧涓柇`),`dismiss must re-render immediately without banner`);
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + topbar_runtime + render_runtime + state_runtime + key_runtime + refresh_runtime + recovery_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_banner_only_after_translation_started(self):
        """Recovery banner must only appear for sessions where translation started."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        restore_start = js.index("function restoreSession(){")
        restore_end = js.index("function recoveryBanner(savedAt){", restore_start)
        restore_runtime = js[restore_start:restore_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}};
let restoringSession=false,sessionRestoredAt=0;
let loaded=null;
window.__slgLoadSelectedApk=async e=>{loaded=e};
function refresh(){}
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function main(){
  localStorage.data[SESSION_KEY]=JSON.stringify({uri:"file://picked.apk",name:"Picked.apk",packageName:"game.pkg",source:"installed",savedAt:123,translating:false});
  restoreSession();
  await tick();
  check(!loaded,"selection-only session must not restore automatically");
  check(sessionRestoredAt===0,"selection-only session must not show recovery banner");
  loaded=null;
  localStorage.data[SESSION_KEY]=JSON.stringify({uri:"file://picked.apk",name:"Picked.apk",packageName:"game.pkg",source:"installed",savedAt:456,translating:true});
  restoreSession();
  await tick();
  check(sessionRestoredAt===456,"translation session restores the interrupted marker");
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", restore_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_translation_heartbeat_updates_session(self):
        """While translating, the persisted session gets a fresh heartbeat."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        snapshot_start = js.index("function readTaskSnapshot(){")
        snapshot_end = js.index("function detailToggle(", snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        key_start = js.index("function snapshotKey(s){")
        key_end = js.index("function retryTask(", key_start)
        key_runtime = js[key_start:key_end]
        refresh_start = js.index("function refresh(){")
        refresh_end = js.index("function decorate(){", refresh_start)
        refresh_runtime = js[refresh_start:refresh_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}};
const document={querySelectorAll(){return[]}};
let detailsOpen=false,manualIdle=false,retrying=false,settingsOpen=false,lastSnapshot="",sessionLastBeat=0;
function sourceText(){return`姝ｅ湪澶勭悊鑴氭湰 1/5`}
function readProgressLog(){return{raw:"",latest:""}}
const shell={};
let states=[];function setWorkshopState(state,payload){states.push([state,payload])}
const before=Date.now();
localStorage.data[SESSION_KEY]=JSON.stringify({uri:"file://picked.apk",savedAt:0,translating:true});
refresh();
const session=JSON.parse(localStorage.data[SESSION_KEY]);
check(session.translating===true,"heartbeat keeps translating flag");
check(session.savedAt>=before,"heartbeat refreshes savedAt while translating");
check(states[0][0]===`translating`,"shell still shows translating after heartbeat");
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + key_runtime + refresh_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_overlay_close_preserves_manual_idle_state(self):
        """Closing settings/gallery must restore the idle state from before opening."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        settings_start = js.index("function beginOverlay(){")
        settings_end = js.index("function openSettings(){", settings_start)
        settings_runtime = js[settings_start:settings_end]
        gallery_start = js.index("function closeGallery(preserveHistory=false){")
        gallery_end = js.index("function renderGallery(){", gallery_start)
        gallery_runtime = js[gallery_start:gallery_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
const document={querySelector(){return{children:[],removeAttribute(){},textContent:""}}};
function releaseModalHistory(){}
let refreshes=0;function refresh(){refreshes+=1}
let manualIdle=true,manualIdleBeforeOverlay=true,galleryOpen=true,settingsOpen=true,lastSnapshot="x";
const galleryShell={hidden:false};const settingsShell={hidden:false};const shell={hidden:false};
closeSettings();
check(manualIdle===true,"closing settings restores the pre-overlay idle state");
check(settingsOpen===false&&settingsShell.hidden===true,"settings actually closes");
manualIdle=true;manualIdleBeforeOverlay=true;galleryOpen=true;settingsOpen=false;lastSnapshot="y";
closeGallery();
check(manualIdle===true,"closing gallery restores the pre-overlay idle state");
check(galleryOpen===false&&galleryShell.hidden===true,"gallery actually closes");
'''
        result = subprocess.run(
            ["node", "-e", settings_runtime + gallery_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for token in (
            "function beginOverlay(){",
            "function endOverlay(){",
            "beginOverlay();settingsOpen=true",
            "settingsOpen=false;endOverlay()",
            "beginOverlay();galleryOpen=true",
            "galleryOpen=false;endOverlay()",
        ):
            self.assertIn(token, js, token)

    def test_filters_keep_every_audit_missing_string(self):
        """Regression: the 19 audit-verified gaps must survive the text filters."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        ue_start = js.index("function Ue(e,t){")
        ue_end = js.index("function Ke(e){", ue_start)
        ue = js[ue_start:ue_end]
        ke_start = ue_end
        ke_end = js.index("function qe(", ke_start) if "function qe(" in js[ke_start:] else ke_start + 900
        ke = js[ke_start:ke_end]
        ne_start = js.index("function Ne(e,t=``,n){")
        ne_end = js.index("function Pe(", ne_start)
        ne = js[ne_start:ne_end]
        skip_start = js.index("var _rpycSkip=")
        skip_end = js.index("function Yo(", skip_start)
        skip = js[skip_start:skip_end]
        contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
const NL = String.fromCharCode(10);
const mustKeep = [
  'E',
  'My Bully is My Lover',
  'Right Trigger' + NL + 'A/Bottom Button',
  'Mouse Wheel Up' + NL + 'Click Rollback Side',
  'Loading will lose unsaved progress.' + NL + 'Are you sure you want to do this?',
  "This will upload your saves to the {a=https://sync.renpy.org}Ren'Py Sync Server{/a}." + NL + 'Do you want to continue?',
  '\\n{color=#fff}Copied to clipboard.{/color}',
];
for (const s of mustKeep) {
  check(Ue(s, 'en') === false, 'Ue must keep: ' + JSON.stringify(s));
  check(Ke(s) === false, 'Ke must keep: ' + JSON.stringify(s));
}
const mustDrop = ['bar', 'SKIP', 'assets/x-game/x-ch1.rpyc', 'renpy.config.developer', 'statement_start'];
for (const s of mustDrop) {
  check(Ue(s, 'en') === true || Ke(s) === true, 'filter must drop: ' + JSON.stringify(s));
}
// Ne must preserve literal backslash-n (2 chars) and restore real newlines.
const literalBackslashN = 'Press <esc> to exit console. Type help for help.\\n';
const realNewline = 'Line one' + NL + 'Line two';
const protocolLiteral = 'RPYC_STRING\t' + 'Press <esc> to exit console. Type help for help.' + '\\\\n' + NL;
const protocolReal = 'RPYC_STRING\t' + 'Line one' + '\\n' + 'Line two' + NL;
const out = Ne(protocolLiteral + protocolReal, '', 'en');
check(out.length === 2, 'Ne keeps both lines: ' + out.length);
check(out[0].text === literalBackslashN, 'Ne preserves literal backslash-n: ' + JSON.stringify(out[0].text));
check(out[1].text === realNewline, 'Ne preserves real newline: ' + JSON.stringify(out[1].text));
// candidate filter must include the options file (game title lives there)
check(!_rpycSkip.test('x-options'), 'x-options must not be skipped');
        '''
        result = subprocess.run(
            ["node", "-e", ue + ke + ne + skip + contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_translating_state_does_not_replay_card_entrance_animation(self):
        module = self.load_patch()
        _, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        compact_css = "".join(css.split())
        self.assertIn(
            '.workshop-task-shell[data-workshop-state="translating"] .workshop-task-card{animation:none}',
            compact_css,
        )
        self.assertIn("animation:workshopRise", compact_css)

    def test_translation_progress_emits_starting_batch_before_request(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        helpers_start = js.index("function isNetworkFailure(e)")
        coordinator_end = js.index("function Ro(e)", helpers_start)
        coordinator = js[helpers_start:coordinator_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  globalThis.Co=async()=>{};
  globalThis.No=texts=>texts;
  globalThis.xo=()=>`scope`;
  globalThis.Se=()=>null;
  globalThis.To=()=>null;
  globalThis.Wo=()=>{};
  globalThis.Eo=()=>{};
  globalThis.wo=async()=>{};
  globalThis.H=class{};
  globalThis.zo=items=>items.map(item=>[item]);
  globalThis.Ro=item=>item;
  globalThis.Ao=4;
  globalThis.jo=1;
  globalThis.Ko=()=>0;
  globalThis.Vo=async(_client,_model,batch)=>new Map(batch.map((_,i)=>[i,`ok`]));
  const progress=[];
  const result=await Lo({texts:[{id:`a`,text:`A`,duplicateKeys:[]},{id:`b`,text:`B`,duplicateKeys:[]}],sourceLang:`en`,targetLang:`zh`,baseURL:`https://api.openai.com/v1`,apiKey:`key`,model:`m`,batchSize:1,onProgress:(e,t,n,r)=>progress.push({e,t,n,r})});
  check(result.successCount===2,`both batches translate`);
  check(progress.some(p=>p.r&&p.r.stage===`start`&&p.r.currentBatch===1&&p.r.totalBatches===2),`coordinator reports starting batch before request`);
  check(progress.some(p=>p.r&&p.r.stage==="completed"&&p.r.completedBatches===2),`coordinator still reports completed batches`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", coordinator + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
