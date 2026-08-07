import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
BASE_JS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
BASE_CSS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-C044IUg3.css"


def extract_js_function(source: str, signature: str) -> str:
    start = source.find(signature)
    assert start >= 0, f"JavaScript function signature not found: {signature!r}"

    contexts = [("code", None)]
    escaped = False
    regex_class = False
    paren_depth = 0
    brace_depth = 0
    body_started = False

    index = start
    while index < len(source):
        char = source[index]
        mode, template_boundary = contexts[-1]

        if mode == "regex":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "[":
                regex_class = True
            elif char == "]":
                regex_class = False
            elif char == "/" and not regex_class:
                contexts.pop()
            index += 1
            continue

        if mode in ("single", "double", "template"):
            if escaped:
                escaped = False
                index += 1
                continue
            if char == "\\":
                escaped = True
                index += 1
                continue
            if mode == "template":
                if char == "`":
                    contexts.pop()
                elif char == "$" and index + 1 < len(source) and source[index + 1] == "{":
                    contexts.append(("code", brace_depth))
                    index += 2
                    continue
            elif char == ("'" if mode == "single" else '"'):
                contexts.pop()
            index += 1
            continue

        if char == "'":
            contexts.append(("single", None))
        elif char == '"':
            contexts.append(("double", None))
        elif char == "`":
            contexts.append(("template", None))
        elif char == "/":
            previous = index - 1
            while previous >= start and source[previous].isspace():
                previous -= 1
            previous_char = source[previous] if previous >= start else ""
            word_end = previous
            while word_end >= start and (source[word_end].isalnum() or source[word_end] in "_$"):
                word_end -= 1
            previous_word = source[word_end + 1 : previous + 1]
            if (
                previous_char in "([{:;,=!?&|+*%^~<>"
                or not previous_char
                or previous_word in {"return", "throw", "case", "delete", "void", "typeof", "yield", "await"}
            ):
                contexts.append(("regex", None))
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            assert paren_depth > 0, "unbalanced JavaScript parentheses"
            paren_depth -= 1
        elif char == "{":
            if not body_started:
                if paren_depth == 0:
                    body_started = True
                    brace_depth = 1
            else:
                brace_depth += 1
        elif char == "}":
            if template_boundary is not None and brace_depth == template_boundary:
                contexts.pop()
            elif body_started:
                brace_depth -= 1
                if brace_depth == 0:
                    return source[start : index + 1]

        index += 1

    assert body_started and brace_depth == 0, f"unclosed JavaScript function: {signature!r}"
    raise AssertionError(f"unclosed JavaScript function: {signature!r}")


def extract_js_expression(source: str, signature: str) -> str:
    """Extract a top-level comma-delimited initializer without slicing by a later function."""
    start = source.find(signature)
    assert start >= 0, f"JavaScript expression signature not found: {signature!r}"
    contexts = [("code", None)]
    escaped = False
    regex_class = False
    paren_depth = brace_depth = bracket_depth = 0
    control_parens = []
    control_braces = []
    closed_control_paren = False
    closed_control_body = False
    index = start
    while index < len(source):
        char = source[index]
        mode, template_boundary = contexts[-1]
        if mode == "line_comment":
            if char in "\r\n":
                contexts.pop()
            index += 1
            continue
        if mode == "block_comment":
            if char == "*" and index + 1 < len(source) and source[index + 1] == "/":
                contexts.pop()
                index += 2
                continue
            index += 1
            continue
        if mode == "regex":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "[":
                regex_class = True
            elif char == "]":
                regex_class = False
            elif char == "/" and not regex_class:
                contexts.pop()
                regex_class = False
            index += 1
            continue
        if mode in ("single", "double", "template"):
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif mode == "template":
                if char == "`":
                    contexts.pop()
                elif char == "$" and index + 1 < len(source) and source[index + 1] == "{":
                    contexts.append(("code", brace_depth))
                    index += 2
                    continue
            elif char == ("'" if mode == "single" else '"'):
                contexts.pop()
            index += 1
            continue
        if char == "'":
            contexts.append(("single", None))
        elif char == '"':
            contexts.append(("double", None))
        elif char == "`":
            contexts.append(("template", None))
        elif char == "/":
            previous = index - 1
            while previous >= start and source[previous].isspace():
                previous -= 1
            previous_char = source[previous] if previous >= start else ""
            word_end = previous
            while word_end >= start and (
                source[word_end].isalnum() or source[word_end] in "_$"
            ):
                word_end -= 1
            previous_word = source[word_end + 1 : previous + 1]
            if index + 1 < len(source) and source[index + 1] == "/":
                contexts.append(("line_comment", None))
                index += 2
                continue
            if index + 1 < len(source) and source[index + 1] == "*":
                contexts.append(("block_comment", None))
                index += 2
                continue
            if (
                previous_char in "([{:;,=!?&|+*%^~<>"
                or not previous_char
                or previous_word
                in {
                    "return",
                    "throw",
                    "case",
                    "delete",
                    "void",
                    "typeof",
                    "yield",
                    "await",
                    "else",
                }
                or (previous_char == ")" and closed_control_paren)
                or (previous_char == "}" and closed_control_body)
            ):
                contexts.append(("regex", None))
                regex_class = False
        elif char == "(":
            paren_depth += 1
            previous = index - 1
            while previous >= start and source[previous].isspace():
                previous -= 1
            word_end = previous
            while word_end >= start and (
                source[word_end].isalnum() or source[word_end] in "_$"
            ):
                word_end -= 1
            control_parens.append(
                source[word_end + 1 : previous + 1]
                in {"if", "while", "for", "with", "switch", "catch"}
            )
            closed_control_paren = False
        elif char == ")":
            paren_depth -= 1
            closed_control_paren = bool(control_parens.pop()) if control_parens else False
        elif char == "{":
            previous = index - 1
            while previous >= start and source[previous].isspace():
                previous -= 1
            word_end = previous
            while word_end >= start and (
                source[word_end].isalnum() or source[word_end] in "_$"
            ):
                word_end -= 1
            control_braces.append(
                closed_control_paren
                or source[word_end + 1 : previous + 1]
                in {"else", "try", "finally", "do"}
            )
            brace_depth += 1
            closed_control_paren = False
            closed_control_body = False
        elif char == "}":
            if template_boundary is not None and brace_depth == template_boundary:
                contexts.pop()
            else:
                brace_depth -= 1
                closed_control_body = bool(control_braces.pop()) if control_braces else False
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == "," and not (paren_depth or brace_depth or bracket_depth):
            return source[start:index]
        index += 1
    raise AssertionError(
        f"top-level JavaScript expression terminator not found: {signature!r}"
    )


class WorkshopPatchContractTest(unittest.TestCase):
    def load_patch(self):
        module_path = ROOT / "patch_workshop_ui.py"
        self.assertTrue(module_path.exists(), "patch_workshop_ui.py must exist")
        spec = importlib.util.spec_from_file_location("patch_workshop_ui", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_extract_js_function_ignores_braces_inside_strings_and_templates(self):
        source = 'function target(){const a="}";const b=`x${1}`;if(true){return `{ok}`}}\nfunction next(){}'
        block = extract_js_function(source, "function target()")
        self.assertEqual(block, 'function target(){const a="}";const b=`x${1}`;if(true){return `{ok}`}}')

    def test_extract_js_function_handles_regex_literals_and_division(self):
        source = 'function target(){const braces=/[{}]/;const quotient=a / b;return /}/.test("}")?quotient:0} function next(){}'
        block = extract_js_function(source, "function target()")
        self.assertEqual(block, source.split(" function next()")[0])

    def test_extract_js_expression_handles_regex_classes_escapes_and_division(self):
        source = r"loader=()=>{if (ready) /[{}\\]/giu.test(value);const suffix=/\.rp(?:y|ym)c$/i;const literal=/}/;const classPattern=/[{}\\]/;const slash=/\//;const quotient=a / b;const conditional=ready?/}/:a / b;const message=`${literal} ${`inner ${quotient}`}`;return {suffix,literal,classPattern,slash,quotient,conditional,message}},next=()=>{}"
        expression = extract_js_expression(source, "loader=")
        self.assertEqual(expression, source.split(",next=")[0])

    def test_extract_js_expression_fails_closed_without_top_level_terminator(self):
        with self.assertRaisesRegex(AssertionError, "terminator not found"):
            extract_js_expression("loader=()=>{return /[{}]/i}", "loader=")

    def test_extract_js_expression_ignores_line_and_block_comments(self):
        source = (
            "loader=()=>{const line=1 // comma, and a brace }\n"
            "const block=2 /* comma, and a brace } */;return {line,block}},next=()=>{}"
        )
        expression = extract_js_expression(source, "loader=")
        self.assertEqual(expression, source.split(",next=")[0])

    def test_extract_js_expression_handles_regex_after_else_and_control_body(self):
        source = (
            r"loader=()=>{if (ready) {} else /[{},]/giu.test(value);"
            r"if (again) {hit()} /}/.test(value);return {ready,again}},next=()=>{}"
        )
        expression = extract_js_expression(source, "loader=")
        self.assertEqual(expression, source.split(",next=")[0])

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
            "normalizeSelection=e=>",
            "mergeSelectionMetadata=(current,update)=>",
            "nextSplitCountPresent=next.splitCount!==undefined",
            "splitTupleComplete=nextSplitUris&&nextSplitNames",
            "s.splitCount=splitTupleComplete?nextSplitCount:previousSplitCount",
            "next.packageName??previous.packageName",
            "next.versionCode??previous.versionCode",
            "window.__slgSelectionMeta=mergeSelectionMetadata(window.__slgSelectionMeta,_r)",
            "s.baseUri=s.baseUri||s.uri",
            "s.splitUris=splitUris",
            "s.splitNames=splitNames",
            "s.splitCount=Number(s.splitCount",
            "s.packageName=s.packageName||\"\"",
            "s.versionCode=s.versionCode??\"\"",
            "s.source=s.source===\"installed\"",
            "function retryScanTask(payload)",
            "Object.assign(e,{baseUri:e.baseUri||e.uri",
            "splitUris:Array.isArray(e.splitUris)",
            "splitNames:Array.isArray(e.splitNames)",
            "splitCount:Number(e.splitCount",
            "window.__slgSelectionError=null",
            "window.__slgSelectionError={message:",
            "await loadSelectedApk(await E.pickApkFile())",
            "E.listApkEntries({uri:e.uri,baseUri:e.baseUri||e.uri",
            "e.name||e.label||e.uri.split(`/`).pop()||`Unknown.apk`",
            "e.packageName||``",
            "e.versionCode",
            "source:e.source||''",
            "e.splitApk&&t.entries.length===0",
            "function openSourceChooser()",
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
            'actionButton("从文件选择 APK"',
            'actionButton("重新加载"',
            'actionButton("从已安装应用选择"',
            'search.placeholder="搜索应用名称或包名"',
        ):
            self.assertIn(token, js)
        self.assertEqual(js.count("loadSelectedApk=window.__slgLoadSelectedApk"), 1)
        self.assertEqual(js.count("E.listApkEntries({uri:e.uri,baseUri:e.baseUri||e.uri"), 1)
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
        loader_expression = extract_js_expression(
            js, "loadSelectedApk=window.__slgLoadSelectedApk="
        )
        loader_initializer = loader_expression[len("loadSelectedApk=") :]
        timeout_runtime = extract_js_expression(js, "withTimeout=") + ";"
        normalize_runtime = extract_js_expression(js, "normalizeSelection=") + ";"
        scan_runtime = extract_js_expression(js, "scanSelectedApk=") + ";"
        xe_expression = extract_js_expression(js, "xe=async()=>")
        xe_initializer = xe_expression[len("xe=") :]
        filter_runtime = extract_js_function(js, "function filterInstalledApps(apps,query)")
        list_runtime = extract_js_function(js, "async function loadInstalledApps()")
        choose_runtime = extract_js_function(js, "async function chooseInstalledApp(app)")
        snapshot_runtime = extract_js_function(js, "function readTaskSnapshot(){")
        render_runtime = "\n".join(
            (
                extract_js_function(js, "function renderTopbar(state)"),
                extract_js_function(js, "function renderStateBody(state,payload)"),
                extract_js_function(js, "function setWorkshopState(state,payload={})"),
            )
        )
        behavior_contract = rf'''
function check(condition,label){{if(!condition)throw new Error(label)}}
globalThis.window=globalThis;
window.__slgScanTimeoutMs=65000;
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
let normalizeSelection,withTimeout,scanSelectedApk;
{normalize_runtime}
{timeout_runtime}
{scan_runtime}
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
let sourceChooserOpened=0,retries=0,fileFallbacks=0;function openSourceChooser(){{sourceChooserOpened+=1}} function openSettings(){{}} function retryTask(){{retries+=1}} function triggerReactButton(){{fileFallbacks+=1}}
const sourceButton={{}},startButton=null,installButton=null;
function startScanClock(){{}} function stopScanClock(){{}}
function classList(){{return{{remove(){{}},add(){{}}}}}}
let shell={{dataset:{{}},classList:classList(),setAttribute(name,value){{this[name]=value}},replaceChildren(...nodes){{this.rendered=nodes}}}};
const runtimeRoot={{classList:classList(),setAttribute(){{}}}};

async function main(){{
  const installed={{uri:`file://installed.apk`,baseUri:`file://base.apk`,splitUris:[`file://config.apk`,`file://lang.apk`],splitNames:[`config.apk`,`lang.apk`],splitCount:2,name:`Friendly Game.apk`,label:`Friendly Game`,packageName:`game.pkg`,versionCode:17,source:`installed`,splitApk:true}};
  await xe();
  check(calls[0][0]===`pick`&&calls[1][0]===`list`&&calls[1][1]===`file://picked.apk`,`real file picker enters shared URI scanner`);
  check(uri===`file://picked.apk`&&name===`Picked.apk`,`file selection metadata loaded`);
  check(window.__slgSelectionMeta.uri===`file://picked.apk`&&window.__slgSelectionMeta.baseUri===`file://picked.apk`,`file SourceSet preserves uri and baseUri`);
  check(Array.isArray(window.__slgSelectionMeta.splitUris)&&window.__slgSelectionMeta.splitUris.length===0&&Array.isArray(window.__slgSelectionMeta.splitNames)&&window.__slgSelectionMeta.splitNames.length===0&&window.__slgSelectionMeta.splitCount===0,`file SourceSet preserves empty split fields`);
  check(window.__slgSelectionMeta.packageName===``&&window.__slgSelectionMeta.versionCode===``&&window.__slgSelectionMeta.source===`file`,`file SourceSet defines package version and source`);
  check(entries.length===1&&failure===null&&progress.length===0,`old task reset`);

  E.listApkEntries=async input=>{{calls.push([`list`,input.uri]);return{{entries:[],scanDurationMs:5}}}};
  let splitError=``;
  try{{await loadSelectedApk({{uri:`file://split.apk`,label:`Split`,splitApk:true,splitCount:2}})}}catch(error){{splitError=error.message}}
  check(splitError.includes(`\u62c6\u5206\u5b89\u88c5\u5305`)&&splitError.includes(`\u4ece\u6587\u4ef6\u9009\u62e9 APK`),`dedicated split error`);
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
  const retry=failedButtons.find(button=>button.label===`\u91cd\u8bd5\u626b\u63cf`),fileFallback=failedButtons.find(button=>button.label===`\u4ece\u6587\u4ef6\u9009\u62e9 APK`);
  check(retry&&fileFallback,`failed shell offers retry and file fallback`);retry.handler();fileFallback.handler();
  check(retries===1&&fileFallbacks===1,`failed shell recovery actions are executable`);

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
  check(window.__slgSelectionMeta.baseUri===installed.baseUri&&window.__slgSelectionMeta.splitUris.join(`,`)===installed.splitUris.join(`,`),`base and split URI metadata survives`);
  check(window.__slgSelectionMeta.splitNames.join(`,`)===installed.splitNames.join(`,`)&&window.__slgSelectionMeta.splitCount===installed.splitCount,`split names and count survive`);
  check(window.__slgSelectionMeta.packageName===installed.packageName&&window.__slgSelectionMeta.versionCode===installed.versionCode&&window.__slgSelectionMeta.source===`installed`,`package version and source survive`);
  check(logs.some(([message])=>message.includes(`\u6b63\u5728\u8bfb\u53d6`)&&message.includes(`APK`),`installed selection uses dedicated loading log`));
  check(logs.some(([message])=>message.includes(`split`)&&message.includes(`2`),`split warning`));

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
            ["node", "--input-type=module"],
            input=filter_runtime + list_runtime + choose_runtime + snapshot_runtime + render_runtime + behavior_contract,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scan_retry_reuses_current_sourceset_and_replaces_watchdog(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        loader = extract_js_expression(
            js, "loadSelectedApk=window.__slgLoadSelectedApk="
        )
        loader = loader[len("loadSelectedApk=") :]
        helper = "\n".join(
            (
                extract_js_expression(js, "normalizeSelection=") + ";",
                extract_js_expression(js, "withTimeout=") + ";",
                extract_js_expression(js, "scanSelectedApk=") + ";",
            )
        )
        retry_runtime = "\n".join(
            (
                extract_js_function(js, "function retryScanTask(payload)"),
                extract_js_function(js, "function retryTask(payload)"),
            )
        )
        contract = rf'''
function check(condition,label){{if(!condition)throw new Error(label)}}
globalThis.window=globalThis;
let now=1000;Date.now=()=>now;
const timers=[];window.setTimeout=(callback,delay)=>{{timers.push({{callback,delay,at:now+delay,cleared:false}});return timers.length}};window.clearTimeout=id=>{{if(timers[id-1])timers[id-1].cleared=true}};
window.__slgScanTimeoutMs=65000;
const scanning=[],entries=[],logs=[],requests=[];let uri="",name="",pkg="",failure=null;const he={{current:[]}};
function r(value){{uri=value}} function a(value){{name=value}} function s(value){{entries.splice(0,entries.length,...value)}} function p(value){{pkg=value}}
function fe(value){{failure=value}} function w(){{}} function d(value){{scanning.push(value)}} function O(value){{logs.push(value)}}
function Jo(value){{return value}} function Oe(){{return{{rpy:1}}}} const ds={{rpy:"rpy"}},c="all",g="zh";
const E={{listApkEntries(input){{return new Promise((resolve,reject)=>requests.push({{input,resolve,reject}}))}},getApkPackageName:async()=>({{packageName:""}})}};
let normalizeSelection,withTimeout,scanSelectedApk;
{helper}
const loadSelectedApk={loader};const loadCalls=[];window.__slgLoadSelectedApk=selection=>{{loadCalls.push(selection);return loadSelectedApk(selection)}};
let retrying=false,lastSnapshot="",settingsOpen=false,refreshes=0,triggered=0,states=[];
function refresh(){{refreshes+=1}} function setWorkshopState(state,payload){{states.push({{state,payload}})}}
function triggerReactButton(){{triggered+=1}} const sourceButton={{}};const startButton=null;
{retry_runtime}
async function main(){{
 const selection={{uri:"file://retry.apk",baseUri:"file://retry.apk",splitUris:[],splitNames:[],splitCount:0,packageName:"retry.pkg",versionCode:9,source:"file",name:"Retry.apk"}};
 const first=window.__slgLoadSelectedApk(selection);await Promise.resolve();await Promise.resolve();
 check(requests.length===1&&scanning.at(-1)===true,"initial scan starts through shared loader");
 const oldWatchdog=window.__slgScanWatchdog,oldTimer=timers[0],oldEpoch=window.__slgSelectionEpoch;
 retryTask({{reason:"scan",fileName:"Retry.apk",raw:""}});
 await Promise.resolve();await Promise.resolve();
 const newWatchdog=window.__slgScanWatchdog;
 check(requests.length===2&&window.__slgSelectionEpoch>oldEpoch&&oldWatchdog!==newWatchdog&&oldTimer.cleared,"scan retry replaces and invalidates old watchdog");
 check(triggered===0&&states.at(-1).state==="scanning","scan retry does not click the React start or file button");
 const retried=loadCalls[1];
 check(retried.uri===selection.uri&&retried.baseUri===selection.baseUri&&retried.splitUris.length===0&&retried.splitNames.length===0&&retried.splitCount===0&&retried.packageName===selection.packageName&&retried.versionCode===9&&retried.source==="file","scan retry reuses complete current SourceSet");
 requests[0].resolve({{entries:[{{name:"stale",fileType:"rpy"}}]}});
 await first;
 requests[1].resolve({{entries:[{{name:"current",fileType:"rpy"}}]}});
 await Promise.resolve();await Promise.resolve();
 check(entries[0].name==="current"&&window.__slgScanWatchdog===newWatchdog&&window.__slgSelectionError===null,"stale watchdog settlement cannot overwrite retried scan");
}}
main().catch(error=>{{console.error(error);process.exitCode=1}})
'''
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=contract,
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
        helpers = "\n".join(
            (
                extract_js_function(js, "function armModalHistory()"),
                extract_js_function(js, "function releaseModalHistory()"),
                extract_js_function(js, "function closeSourceChooser("),
                extract_js_function(js, "function focusInstalledTarget()"),
            )
        )
        installed_render = extract_js_function(js, "function renderInstalledApps()")
        installed_close = extract_js_function(js, "function closeInstalledApps(")
        pop_handler = extract_js_function(js, "function handleWorkshopPopState()")
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
check(returnedFocus===1,`source modal back restores opener focus`);
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
const retry=content.children.find(node=>node.className===`workshop-source-option`);
const fallback=content.children.find(node=>node.className===`workshop-modal-action`);
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
        helpers = "\n".join(
            (
                extract_js_function(js, "function armModalHistory()"),
                extract_js_function(js, "function releaseModalHistory()"),
                extract_js_function(js, "function closeSourceChooser("),
            )
        )
        settings_close = extract_js_function(js, "function closeSettings(")
        installed_close = extract_js_function(js, "function closeInstalledApps(")
        pop_handler = extract_js_function(js, "function handleWorkshopPopState()")
        handler = extract_js_function(js, "window.__slgHandleAndroidBack=")
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
        helper = "\n".join(
            (
                extract_js_expression(js, "normalizeSelection=") + ";",
                extract_js_expression(js, "withTimeout=") + ";",
                extract_js_expression(js, "scanSelectedApk=") + ";",
            )
        )
        loader_expression = extract_js_expression(
            js, "loadSelectedApk=window.__slgLoadSelectedApk="
        )
        loader = loader_expression[len("loadSelectedApk=") :]
        render_state = extract_js_function(js, "function renderStateBody(state,payload)")
        contract = rf'''
globalThis.window=globalThis;
let now=100000;Date.now=()=>now;
const timers=[];window.setTimeout=(callback,delay)=>{{timers.push({{callback,delay,at:now+delay,cleared:false,fired:false}});return timers.length}};window.clearTimeout=id=>{{if(timers[id-1])timers[id-1].cleared=true}};
function advance(ms){{now+=ms;for(const timer of timers)if(!timer.cleared&&!timer.fired&&timer.at<=now){{timer.fired=true;timer.callback()}}}}
window.__slgScanTimeoutMs=65000;
const scanning=[];let uri=``,name=``,entries=[],pkg=``,failure=null;const logs=[];
function r(v){{uri=v}} function a(v){{name=v}} function s(v){{entries=v}} function p(v){{pkg=v}}
function fe(v){{failure=v}} const he={{current:[]}};function w(){{}} function d(v){{scanning.push(v)}} function O(v){{logs.push(v)}}
function Jo(v){{return v}} function Oe(){{return {{rpy:1}}}} const ds={{rpy:`rpy`}},c=`all`,g=`zh`;
let mode=`pending`,lateResolve;
const E={{listApkEntries(){{if(mode===`pending`)return new Promise(resolve=>lateResolve=resolve);if(mode===`reject`)return Promise.reject(new Error(`native reject`));return Promise.resolve({{entries:[{{name:`fresh`,fileType:`rpy`}}]}})}},getApkPackageName:async()=>({{packageName:``}})}};
let normalizeSelection,withTimeout,scanSelectedApk;
{helper}
const loadSelectedApk={loader};
function textNode(tag,cls,text){{return{{tag,cls,textContent:text,children:[],style:{{}},append(...nodes){{this.children.push(...nodes)}},setAttribute(){{}}}}}}
function actionButton(label,handler,secondary){{return{{tag:`button`,label,handler,children:[]}}}}
function fileRow(){{return textNode(`div`,`file-row`,`file`)}} function detailToggle(){{return textNode(`div`,`details`,`details`)}}
function stateIcon(){{return textNode(`span`,`icon`,`icon`)}} function retryTask(){{}} function openSourceChooser(){{}}
function triggerReactButton(){{}} const sourceButton=null,startButton=null,installButton=null;
{render_state}
async function main(){{
 if(window.__slgScanTimeoutMs!==65000)throw new Error(`production deadline is not observable`);
 const pending=loadSelectedApk({{uri:`pending`,name:`Pending.apk`}});
  if(timers.length!==1||timers[0].delay!==65000||window.__slgScanWatchdog.deadlineAt!==165000)throw new Error(`deadline timer contract`);
 await Promise.resolve();
 if(scanning.at(-1)!==true)throw new Error(`scan did not start before deadline`);
  advance(64999);await Promise.resolve();
  if(window.__slgSelectionError!==null||timers[0].fired)throw new Error(`deadline fired before exact fake time`);
  advance(1);await Promise.resolve();
 let timeout=``;try{{await pending}}catch(e){{timeout=e.message}}
  if(!timeout.includes(`\u8d85\u65f6`)||scanning.at(-1)!==false||window.__slgSelectionError?.message!==timeout||!timers[0].cleared||!timers[0].fired)throw new Error(`timeout contract`);
 const failedBody=renderStateBody(`failed`,{{reason:`scan`,fileName:`Pending.apk`,raw:timeout}}),failedButtons=[];
 function visit(node){{if(!node)return;if(node.tag===`button`)failedButtons.push(node);for(const child of node.children||[])visit(child)}}
 visit(failedBody);
 if(!failedButtons.some(button=>button.label===`\u91cd\u8bd5\u626b\u63cf`)||!failedButtons.some(button=>button.label===`\u4ece\u6587\u4ef6\u9009\u62e9 APK`))throw new Error(`timeout failure lacks retry and file fallback`);
 mode=`reject`;let rejected=``;try{{await loadSelectedApk({{uri:`reject`,name:`Reject.apk`}})}}catch(e){{rejected=e.message}}
 if(rejected!==`native reject`||scanning.at(-1)!==false)throw new Error(`reject contract`);
 mode=`resolve`;await loadSelectedApk({{uri:`fresh`,name:`Fresh.apk`}});lateResolve({{entries:[{{name:`late`,fileType:`rpy`}}]}});await Promise.resolve();await Promise.resolve();
 if(uri!==`fresh`||entries[0].name!==`fresh`||window.__slgSelectionError!==null)throw new Error(`late resolve overwrote fresh selection`);
}}
main().catch(e=>{{console.error(e);process.exitCode=1}})
'''
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=contract,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_loader_watchdog_registers_first_and_updates_state_directly(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        declarations = "\n".join(
            (
                extract_js_expression(js, "normalizeSelection=") + ";",
                extract_js_expression(js, "withTimeout=") + ";",
                extract_js_expression(js, "scanSelectedApk=") + ";",
                extract_js_expression(js, "loadSelectedApk=window.__slgLoadSelectedApk=") + ";",
            )
        )
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
        helpers = "\n".join(
            (
                extract_js_function(js, "function armModalHistory()"),
                extract_js_function(js, "function focusInstalledTarget()"),
                extract_js_function(js, "function releaseModalHistory()"),
            )
        )
        installed_runtime = "\n".join(
            (
                extract_js_function(js, "function filterInstalledApps(apps,query)"),
                extract_js_function(js, "function renderInstalledApps()"),
                extract_js_function(js, "async function loadInstalledApps()"),
                extract_js_function(js, "async function chooseInstalledApp(app)"),
                extract_js_function(js, "function closeInstalledApps("),
            )
        )
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

  installedDialog.hidden=false;installedError=``;
  const oldReject=loadInstalledApps(),currentResolve=loadInstalledApps();
  listResolvers[3].resolve({apps:[{label:`Current`,packageName:`current.pkg`}]});await currentResolve;
  listResolvers[2].reject(new Error(`stale list failed`));await oldReject;
  check(installedApps.length===1&&installedApps[0].packageName===`current.pkg`&&installedError===``,`stale list rejection cannot overwrite current list`);
  const currentReject=loadInstalledApps();listResolvers[4].reject(new Error(`current list failed`));await currentReject;
  check(installedError===`current list failed`&&installedApps[0].packageName===`current.pkg`,`current list rejection surfaces error`);

  const beforeClose=installedApps;
  const closing=loadInstalledApps();closeInstalledApps(true);listResolvers[2].resolve({apps:[{label:`Closed stale`,packageName:`closed.pkg`}]});await closing;
  check(installedDialog.hidden&&installedApps===beforeClose,`closed dialog invalidates pending list response`);

  installedDialog.hidden=false;installedApps=[{label:`One`,packageName:`one.pkg`},{label:`Two`,packageName:`two.pkg`}];installedError=``;
  const chooseResolvers=[];
  window.Capacitor.Plugins.FileManager.selectInstalledApp=({packageName})=>new Promise((resolve,reject)=>{chooseResolvers.push({packageName,resolve,reject})});
  const loaded=[];window.__slgLoadSelectedApk=async selection=>{loaded.push(selection)};
  const chooseOne=chooseInstalledApp(installedApps[0]);
  const chooseTwo=chooseInstalledApp(installedApps[1]);
  renderInstalledApps();
  check(attrs[`aria-busy`]===`true`,`choose marks dialog aria busy`);
  check(findNodes(content.children,node=>node.tag===`button`).every(button=>button.disabled),`busy disables rows and source operations`);
  check(cancelAction.disabled,`busy disables modal source cancellation action`);
  check(findNode(content.children,node=>node.cls===`workshop-installed-status`),`busy copy is visible`);
  chooseResolvers[1].resolve({uri:`file://two.apk`,baseUri:`file://two.apk`,splitUris:[],splitNames:[],splitCount:0,name:`Two.apk`,packageName:`two.pkg`,versionCode:2,source:`installed`});await chooseTwo;
  chooseResolvers[0].resolve({uri:`file://one.apk`,baseUri:`file://one.apk`,splitUris:[],splitNames:[],splitCount:0,name:`One.apk`,packageName:`one.pkg`,versionCode:1,source:`installed`});await chooseOne;
  check(loaded.length===1&&loaded[0].packageName===`two.pkg`,`stale choose resolution cannot close or load`);
  check(loaded[0].uri===`file://two.apk`&&loaded[0].baseUri===`file://two.apk`&&loaded[0].splitCount===0&&loaded[0].versionCode===2&&loaded[0].source===`installed`,`new selection preserves complete SourceSet`);
  check(installedError===``,`stale choose rejection cannot render error`);

  installedDialog.hidden=false;installedError=``;installedBusy=false;
  const chooseThree=chooseInstalledApp(installedApps[0]);
  const chooseFour=chooseInstalledApp(installedApps[1]);
  chooseResolvers[3].resolve({uri:`file://four.apk`,baseUri:`file://four.apk`,splitUris:[],splitNames:[],splitCount:0,name:`Four.apk`,packageName:`four.pkg`,versionCode:4,source:`installed`});await chooseFour;
  chooseResolvers[2].reject(new Error(`stale select failed`));await chooseThree;
  check(loaded.length===2&&loaded[1].packageName===`four.pkg`&&installedError===``,`stale choose rejection cannot replace current selection`);

  installedDialog.hidden=false;installedError=``;installedBusy=false;
  const currentChooseReject=chooseInstalledApp(installedApps[0]);
  chooseResolvers[4].reject(new Error(`current select failed`));await currentChooseReject;
  check(installedError===`current select failed`&&!installedDialog.hidden,`current selection rejection surfaces error`);

  installedDialog.hidden=false;installedApps=[];installedLoading=false;installedError=``;installedBusy=false;renderInstalledApps();
  check(findNode(content.children,node=>node.cls===`workshop-installed-status`),`complete empty guidance`);
  const fallback=findNode(content.children,node=>node.className===`workshop-modal-action`);check(fallback,`empty state file fallback exists`);fallback.onclick();
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
        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
        source_runtime = extract_js_function(js, "function openSourceChooser()")
        action_runtime = extract_js_function(js, "function actionButton(label,handler,secondary)")
        detail_runtime = extract_js_function(js, "function detailToggle(raw,live=false)")
        visible_runtime = "\n".join(
            (render_runtime, source_runtime, action_runtime, detail_runtime)
        )
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
window.requestAnimationFrame=callback=>callback();
window.setTimeout=callback=>{callback();return 1};
globalThis.MouseEvent=class{constructor(type,options){this.type=type;this.options=options}};
function node(tag,text){return{tag,textContent:text??"",children:[],className:"",hidden:false,dataset:{},append(...items){this.children.push(...items)},appendChild(item){this.children.push(item)},setAttribute(){},classList:{add(){},remove(){}}}}
globalThis.document={createElement:tag=>node(tag),querySelector:()=>null,querySelectorAll:()=>[]};
function textNode(tag,cls,text){const value=node(tag,text);value.className=cls;return value}
function fileRow(){return textNode("div","file-row","")}
function triggerReactButton(){}
function clickReact(){return true}
function savePatchedApk(){}
function closeSourceChooser(){}
function openInstalledApps(){}
function armModalHistory(){}
function focusableIn(){return[]}
let detailsOpen=false,sourceDialog=null,runtimeRoot={append(){}},installButton={isConnected:true},modalHistoryClosing=false,manualIdle=false,lastSnapshot="",previousSourceFocus=null,sourceButton={};
function trapModalFocus(){}
function collect(node,out=[]){if(!node)return out;if(node.textContent)out.push(String(node.textContent));for(const child of node.children||[])collect(child,out);return out}
function buttons(node,out=[]){if(!node)return out;if(node.tag===`button`)out.push(node);for(const child of node.children||[])buttons(child,out);return out}
const idle=renderStateBody(`idle`,{});
const ready=renderStateBody(`ready`,{count:1});
const completed=renderStateBody(`completed`,{fileName:`game.apk`,patchedApkPath:`/tmp/game-patched-signed.apk`,installAvailable:true,raw:`done`});
openSourceChooser();
const source=sourceDialog;
const labels=collect(idle).concat(collect(ready),collect(completed),collect(source));
const buttonLabels=buttons(idle).concat(buttons(ready),buttons(completed),buttons(source)).map(button=>button.textContent);
for(const required of REQUIRED_COPY)check(labels.includes(required)||buttonLabels.includes(required),`copy is visible: ${required}`);
check(buttonLabels.includes(`立即安装`),`install copy comes from completed DOM`);
check(buttonLabels.includes(`保存 APK`),`save copy comes from completed DOM`);
'''
        required_copy = (
            "让喜欢的故事，用中文继续。",
            "从文件选择 APK",
            "处理详情",
            "立即安装",
            "保存 APK",
        )
        behavior_contract = behavior_contract.replace(
            "REQUIRED_COPY", repr(list(required_copy)).replace("'", "`")
        )
        result = subprocess.run(
            ["node", "-e", visible_runtime + "\n" + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("workshop-copy:", js)
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
            "选择 APK 文件",
            "正在读取应用列表",
            "从已安装应用选择",
            "处理详情",
            "无法读取这个 APK",
            "我的设置",
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
        mount_runtime = extract_js_function(js, "function mount(){")
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

        trigger_runtime = extract_js_function(js, "function triggerReactButton(button)")
        topbar_runtime = extract_js_function(js, "function renderTopbar(state)")
        file_row_runtime = extract_js_function(js, "function fileRow(fileName)")
        detail_runtime = extract_js_function(js, "function detailToggle(raw,live=false)")
        action_runtime = extract_js_function(js, "function actionButton(label,handler,secondary)")
        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
        state_runtime = extract_js_function(js, "function setWorkshopState(state,payload={})")
        retry_runtime = extract_js_function(js, "function retryTask(payload)")
        # The base bundle has unrelated export-link anchor.click handlers. The
        # safety gate intentionally covers the complete extracted workshop
        # runtime above, so the exclusion is by function ownership, not by
        # narrowing the check to source/start/install variable names.
        workshop_runtime = "".join((trigger_runtime, topbar_runtime, file_row_runtime, detail_runtime, action_runtime, render_runtime, state_runtime, retry_runtime))
        self.assertNotRegex(workshop_runtime, r"\.\s*click\s*\(")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
globalThis.MouseEvent=class{constructor(type,options){this.type=type;this.options=options}};
window.requestAnimationFrame=callback=>callback();
window.setTimeout=callback=>{callback();return 1};
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(key){return this.data[key]??null},setItem(key,value){this.data[key]=String(value)},removeItem(key){delete this.data[key]}};
globalThis.localStorage=localStorage;
let dispatched=0,refreshes=0,detailsOpen=false,lastSnapshot="";
const reactStart={textContent:`\u5f00\u59cb\u7ffb\u8bd1`,disabled:false,isConnected:true,dispatchEvent(event){dispatched+=1;this.lastEvent=event}};
const startButton=reactStart,sourceButton={textContent:`\u9009\u62e9 APK`},installButton=null;
function findButton(label){return label===`\u5f00\u59cb\u7ffb\u8bd1`?reactStart:null}
function refresh(){refreshes+=1}
function startScanClock(){} function stopScanClock(){}
function textNode(tag,cls,text){return{tag,className:cls,text:text||``,textContent:text||``,children:[],dataset:{},style:{},setAttribute(name,value){this[name]=value},append(...nodes){this.children.push(...nodes)},classList:{add(){},remove(){}}}}
const document={createElement(tag){return textNode(tag,``,``)}};
let shell={dataset:{},attrs:{},classList:{add(){},remove(){}},setAttribute(name,value){this.attrs[name]=value},replaceChildren(...nodes){this.rendered=nodes}};
const runtimeRoot={classList:{add(){},remove(){}},setAttribute(name,value){this[name]=value}};
globalThis.__slgWakeLock=null;
triggerReactButton(startButton);
check(dispatched===1,`trigger bridges to the React control`);
check(reactStart.lastEvent.type===`click`&&reactStart.lastEvent.options.bubbles===true&&reactStart.lastEvent.options.cancelable===true&&reactStart.lastEvent.options.view===window,`bridge dispatches a bubbling click event`);
setWorkshopState(`failed`,{reason:`space`,fileName:`Game.apk`,raw:`ENOSPC|No space left on device`});
check(shell.attrs[`data-workshop-state`]===`failed`&&shell.attrs[`data-workshop-task`]===`active`, `failed state data attributes are rendered`);
check(runtimeRoot[`data-workshop-state`]===`failed`&&runtimeRoot[`data-workshop-task`]===`active`, `runtime root receives state attributes`);
function collectText(node){let out=node?.textContent||``;for(const child of node?.children||[])out+=collectText(child);return out}
function collectButtons(node,out=[]){if(!node)return out;if(node.tag===`button`)out.push(node);for(const child of node.children||[])collectButtons(child,out);return out}
const body=shell.rendered[1];
const renderedText=collectText(body);
check(renderedText.includes(`\u624b\u673a\u7a7a\u95f4\u4e0d\u8db3`),`ENOSPC has a localized title`);
check(renderedText.includes(`ENOSPC|No space left on device`),`ENOSPC keeps raw details`);
const retry=collectButtons(body).find(button=>button.textContent===`\u91ca\u653e\u7a7a\u95f4\u540e\u91cd\u8bd5`);
check(retry,`ENOSPC renders retry action`);
retry.onclick();
check(dispatched===2&&refreshes===1,`retry handler bridges and schedules refresh`);
'''
        result = subprocess.run(
            ["node", "-e", workshop_runtime + behavior_contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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
        self.assertIn('\u624b\u673a\u7a7a\u95f4\u4e0d\u8db3', js)
        self.assertIn('\u8bf7\u91ca\u653e\u7a7a\u95f4\u540e\u91cd\u8bd5', js)
        self.assertIn('detailToggle(payload.raw||"ENOSPC|No space left")', js)
        self.assertIn('actionButton("\u91ca\u653e\u7a7a\u95f4\u540e\u91cd\u8bd5",()=>retryTask({fileName:payload.fileName,raw:""}))', js)

        # Keep React-managed controls mounted and avoid direct click shortcuts;
        # the shell may only dispatch events to those existing nodes.
        for moved_node in ("sourceButton", "startButton"):
            for method in ("append", "appendChild", "prepend", "insertBefore", "replaceChildren"):
                self.assertNotRegex(
                    js,
                    rf'\.\s*{method}\s*\(\s*{moved_node}\b',
                )
        self.assertNotRegex(js, r'(?:sourceButton|startButton|installButton)\s*\.\s*click\s*\(')

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
        ):
            self.assertIn(token, js)
        self.assertIn('min-height:48px', ''.join(css.split()))
        self.assertIn('.workshop-settings-error', css)

        settings_runtime = "\n".join(
            (
                'const SETTINGS_KEY="slg-workshop-settings-v1";',
                extract_js_function(js, "function setReactInputValue(input,value)"),
                extract_js_function(js, "function findReactConfigControls()"),
                extract_js_function(js, "function setReactSelectValue(select,value)"),
                extract_js_function(js, "function saveSettingsPrefs(prefs)"),
                extract_js_function(js, "function applySettingsToReact(prefs)"),
            )
        )
        controller_runtime = extract_js_function(js, "Ce=async()=>")
        scheduler_runtime = extract_js_function(
            js, "async function runFileTasksParallel(e,t,concurrency=3)"
        )
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const stored=new Map;
globalThis.localStorage={getItem:key=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,String(value))};
globalThis.Event=class Event{constructor(type){this.type=type}};
globalThis.HTMLInputElement=class HTMLInputElement{};
globalThis.HTMLSelectElement=class HTMLSelectElement{};
function control(value,options=[]){
  return{value,options,events:[],closest:()=>null,
    addEventListener(type,handler){this.events.push([type,handler])},
    append(option){this.options.push(option)},
    dispatchEvent(event){for(const [type,handler] of this.events)if(type===event.type)handler(event);return true}}
}
const provider=control("openai",[{value:"openai"},{value:"deepseek"},{value:"custom"}]);
const model=control("custom",[{value:"custom"}]);
const endpoint=control("",[]);endpoint.placeholder="https://your-api.com/v1";endpoint.focus=()=>{};endpoint.blur=()=>{};
const root={querySelectorAll(selector){return selector==="select"? [provider,model] : [endpoint]}};
globalThis.document={querySelector:()=>root,createElement:()=>({})};
globalThis.findReactApiInput=()=>null;
globalThis.applyApiKeyToReact=()=>{};
const invoked=[];
let x="openai",re="",S="gpt-4o-mini";
provider.addEventListener("change",()=>{x=provider.value;invoked.push({provider:provider.value,model:model.value,endpoint:endpoint.value})});
model.addEventListener("change",()=>{S=model.value;invoked.push({provider:provider.value,model:model.value,endpoint:endpoint.value})});
endpoint.addEventListener("change",()=>{re=endpoint.value;invoked.push({provider:provider.value,model:model.value,endpoint:endpoint.value})});
const prefs={providerId:"custom",model:"custom",customBaseURL:"https://例子.test/v1",customModel:"自定义模型"};
saveSettingsPrefs(prefs);
check(JSON.parse(localStorage.getItem(SETTINGS_KEY)).providerId==="custom","provider stored exactly");
check(JSON.parse(localStorage.getItem(SETTINGS_KEY)).customBaseURL==="https://例子.test/v1","endpoint stored as UTF-8");
check(JSON.parse(localStorage.getItem(SETTINGS_KEY)).customModel==="自定义模型","model stored as UTF-8");
check(applySettingsToReact(prefs)===true,"settings bridge found current controls");
await new Promise(resolve=>setTimeout(resolve,5));
check(invoked.length>=3,"bridge dispatched current-control events");
const invocations=[];
let n="/cache/game.apk",ae=[{name:"script.rpy",fileType:"rpy"}],te="api-key",oe=false;
let y="zh",g="en",m=null,i="game.apk",fs=1,ps=1,_mode="resume";
const _e=[{id:"openai",baseURL:"https://openai.test/v1"},{id:"deepseek",baseURL:"https://deepseek.test/v1"}];
let vo={},cacheIndex={},_dirty={},bo=false,he={current:[]};
function Co(){} function wo(){} function U(value){return String(value)}
function is(value){return value} function ns(){return false} function ke(){return[{text:"needs translation",keyPath:"script.rpy::1",duplicateKeys:[]}]}
function O(){} function ce(){} function fe(){} function ue(){} function w(){}
async function Lo(args){invocations.push(args);return{translations:new Map(),successCount:0,error:"fixture request"}}
const E={readFileContent:async()=>({content:"source",fileType:"rpy"}),compileTranslationsIntoApk:async()=>({compiled:0}),buildPatchedApk:async()=>({uri:"patched.apk"})};
const ds={rpy:"rpy"};
await Ce();
check(invocations.length===1,"production controller invoked translation entry point");
check(invocations[0].baseURL==="https://例子.test/v1","custom endpoint reaches production entry point");
check(invocations[0].model==="自定义模型","custom model reaches production entry point");
check(x==="custom","provider control updates production controller state");
check(invocations[0].targetLang==="zh"&&invocations[0].sourceLang==="en","language arguments remain intact");
'''
        result = subprocess.run(
            [
                "node",
                "-e",
                settings_runtime
                + "\n(async()=>{"
                + behavior_contract.replace(
                    "await Ce();",
                    "let Ce;\n" + controller_runtime + "\n" + scheduler_runtime + "\nawait Ce();",
                    1,
                )
                + "})().catch(error=>{console.error(error);process.exitCode=1})",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _legacy_save_transfer_settings_runtime_contract(self):
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
            "选择游戏",
            "保存存档",
            "导入存档",
            "导入分享存档",
            "saveImportGamePackage",
            "importGameSelect",
            "renderImportArchiveRows",
            "saveExportGamePackage",
            "saveImportGamePackage",
            "saveImportArchiveUri",
            "saveTransferBusy",
            "manualIdleBeforeOverlay",
            "beginOverlay",
            "endOverlay",
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

    def _legacy_save_transfer_runtime_actions_and_state_gating(self):
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
let workshopState="idle";
function readTaskSnapshot(){return{state:workshopState}}
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
  workshopState="translating";updateSavesState();
  check(exportBtn.disabled,"save actions stay disabled while translation is active");
  await exportBtn.onclick();
  check(calls.export.length===0&&savesStatus.textContent.includes("正在处理任务"),"busy save action is rejected without a native call");
  workshopState="idle";updateSavesState();
  const topButtons=[...savesCard.children].filter(el=>el.tag==="button"&&!el.hidden);
  check(topButtons.length===2,"save page keeps only game picker and save buttons");
  check(topButtons.some(el=>el.textContent==="选择游戏")&&topButtons.some(el=>el.textContent==="保存存档"),"save page exposes picker and export intents");
  check(typeof backupBtn==="undefined","backup button is removed from save page");
  saveExportGamePackage="com.sample.game";saveExportGameLabel="Sample Game";updateSavesState();
  check(!exportBtn.disabled,"save-to-download enabled when a game is selected");
  await refreshSaves();
  check(savesList.children.length===1,"list renders one backup row");
  const actions=savesList.children[0].children.find(el=>el.cls==="workshop-save-actions");
  const restore=actions.children.find(el=>el.textContent==="恢复");
  const del=actions.children.find(el=>el.textContent==="删除");
  const share=actions.children.find(el=>el.textContent==="分享");
  check(restore&&share&&del,"row exposes restore, share and delete buttons");
  globalThis.confirm=()=>true;
  await restore.onclick();
  check(calls.restore.length===1&&calls.restore[0].backupDir==="/backups/1"&&calls.restore[0].packageName==="com.sample.game","restore calls native plugin with selected game and backupDir");
  await share.onclick();
  check(calls.share.length===1&&calls.share[0].backupDir==="/backups/1","share calls native plugin with backupDir");
  await del.onclick();
  check(calls.delete.length===1&&calls.delete[0].backupDir==="/backups/1","delete calls native plugin with backupDir");
  check(savesList.children.length===1&&savesList.children[0].textContent==="暂无备份。","delete refreshes the list");
  await exportBtn.onclick();
  check(calls.export.length===1&&calls.export[0].packageName==="com.sample.game","save to download calls native plugin with packageName");
  check(exportBtn.textContent==="保存存档"&&!exportBtn.disabled,"save button resets after completion");
  check(permissionNote.textContent.includes("所有文件访问"),"Android 11+ shows permission guidance");
  const selectedBeforeError=saveExportGamePackage;
  window.Capacitor.Plugins.FileManager.exportSavesToDownloads=async()=>{throw new Error("native export failed")};
  await exportBtn.onclick();
  check(savesStatus.textContent.includes("native export failed"),"native save errors are visible");
  check(saveExportGamePackage===selectedBeforeError,"native save errors do not corrupt export selection");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + saves_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def _legacy_save_transfer_can_pick_game_from_installed_apps(self):
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
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"Game One",packageName:"zitao.mbml"},{label:"Game Two",packageName:"cim.isekai.game"}]}},
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
  check(saveExportGamePackage==="zitao.mbml","picking a game updates the save page local state");
  check(gameLabel.textContent.includes("Game One"),"picked game name is visible");
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

    def _legacy_save_transfer_can_import_shared_archive(self):
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
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"Game One",packageName:"zitao.mbml"}]}},
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
  const delArchive=archiveRows[0].children.find(el=>el.textContent==="删除");
  check(delArchive,"each archive row exposes a delete action");
  await delArchive.onclick();
  check(calls.deleteArchive.length===1&&calls.deleteArchive[0].path==="/downloads/1.zip","delete calls native plugin with selected archive path");
  const remainingSection=importList.children.find(el=>el.cls==="workshop-archive-section"&&!el.hidden);
  const remainingRows=(remainingSection?.children||[]).filter(el=>el.cls==="workshop-save-row"&&el.children.some(c=>c.textContent.endsWith(".zip")));
  check(remainingRows.length===1,"deleted archive is removed from the panel");
  const importOne=remainingRows[0].children.find(el=>el.textContent==="导入");
  check(importOne,"remaining archive row exposes an import action");
  await importOne.onclick();
  check(calls.imports.length===1&&calls.imports[0].path==="/downloads/2.zip","import calls native plugin with selected path");
  check(saveImportGamePackage==="zitao.mbml","import auto-selects the game from the archive");
  check(importGameSelect.value==="zitao.mbml","import updates the import page game picker");
  check(importGameLabel.textContent.includes("Game One"),"import page shows the auto-selected game label");
  check(importList.children.length===0,"imported archive is removed from the downloaded panel");
  check(importStatus.textContent.includes("已导入 zitao.mbml 的存档。"),"import success message is visible");
  check(importArchiveBtn.textContent==="重新选择存档"&&!importArchiveBtn.disabled,"import button resets after completion");
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

    def _legacy_save_and_import_game_selection_are_independent(self):
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
  listSaveGameApps:async()=>({apps:[{label:"Game One",packageName:"zitao.mbml"},{label:"Game Two",packageName:"cim.isekai.game"}]}),
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
  check(saveExportGamePackage==="zitao.mbml","save page keeps its own selected game");
  check(saveImportGamePackage==="cim.isekai.game","import page keeps its own selected game");
  check(gameLabel.textContent.includes("Game One"),"save page shows its own game label");
  check(importGameLabel.textContent.includes("Game Two"),"import page shows its own game label");
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

    def test_save_transfer_settings_runtime_contract(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        helpers = "\n".join(
            (
                extract_js_function(js, "function armModalHistory()"),
                extract_js_function(js, "function releaseModalHistory()"),
                extract_js_function(js, "function beginOverlay()"),
                extract_js_function(js, "function endOverlay()"),
                extract_js_function(js, "function fieldShell("),
                extract_js_function(js, "function inputControl("),
                extract_js_function(js, "function selectControl("),
                extract_js_function(js, "function replaceSelectOptions("),
                extract_js_function(js, "function closeSettings("),
                extract_js_function(js, "function openSettings()"),
            )
        )
        behavior = r'''
function check(condition,label){if(!condition)throw new Error(label)}
function element(tag){
  const el={tag,className:"",textContent:"",hidden:false,disabled:false,value:"",type:"",id:"",children:[],style:{},parent:null,
    classList:{add(){},remove(){}},setAttribute(name,value){this[name]=value},
    append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node)}},
    replaceChildren(...nodes){this.children=[];this.append(...nodes)},
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(node=>node!==this)},
    addEventListener(){},dispatchEvent(){},focus(){},blur(){},querySelector(){return null},querySelectorAll(){return[]}};
  if(tag==="select")Object.defineProperty(el,"options",{get(){return el.children}});
  return el;
}
globalThis.window={Capacitor:{Plugins:{FileManager:{listSaveBackups:async()=>({backups:[]}),listSaveGameApps:async()=>({apps:[]})}}}};
globalThis.navigator={userAgent:"Android 12"};
globalThis.history={state:{},pushState(){},back(){}};
globalThis.localStorage={getItem(){return null},setItem(){},removeItem(){}};
globalThis.document={activeElement:null,createElement:element,querySelector(){return null},querySelectorAll(){return[]}};
function textNode(tag,cls,text){const el=element(tag);el.className=cls;if(text!==undefined)el.textContent=text;return el}
const PROVIDERS={openai:{label:"OpenAI",models:[["gpt-4o","GPT-4o"]]},deepseek:{label:"DeepSeek",models:[["deepseek-chat","DeepSeek"]]},custom:{label:"自定义接口",models:[["custom","自定义"]]}};
let settingsOpen=false,manualIdle=false,manualIdleBeforeOverlay=false,lastSnapshot="before",modalHistoryArmed=false,modalHistoryClosing=false;
let settingsShell=null,settingsPrevNav="首页",shell={hidden:false,dataset:{workshopState:"translating"}},runtimeRoot={append(node){this.child=node}};
let reactApiInput=null,pendingApiKey=null,refreshes=0;
function findReactApiInput(){return null} function readSettingsPrefs(){return{providerId:"openai",model:"gpt-4o",customBaseURL:"",customModel:""}}
function saveSettingsPrefs(){} function applySettingsToReact(){return true} function formatBytes(){return "0 B"} function buildLocalEngineSection(){return element("section")} function refresh(){refreshes+=1}
'''
        result = subprocess.run(
            [
                "node", "-e",
                behavior + "\n" + helpers + r'''
(async()=>{
  openSettings();
  check(settingsOpen&&!settingsShell.hidden&&shell.hidden,"opening settings shows shell and hides task shell");
  check(settingsShell.children.length===6,"settings shell contains menu, save, import, cleanup and about views");
  const menuView=settingsShell.children[0],menu=menuView.children[1],savesView=settingsShell.children[2],importView=settingsShell.children[3];
  check(menu.children.length===5,"settings menu exposes save and import entries");
  const saveItem=menu.children[1],importItem=menu.children[2];
  await saveItem.onclick();
  check(!savesView.hidden&&importView.hidden,"save view is shown and import view remains hidden");
  check(savesView.children.some(child=>child.children?.some(grandchild=>grandchild.type==="button")),"save view contains actionable buttons");
  menu.children[0].onclick();
  await importItem.onclick();
  check(!importView.hidden&&savesView.hidden,"import view is shown and save view is hidden");
  check(importView.children.some(child=>child.children?.some(grandchild=>grandchild.type==="button")),"import view contains actionable buttons");
  closeSettings();
  check(!settingsOpen&&settingsShell.hidden&&!shell.hidden,"closing settings restores shell visibility");
  check(!manualIdle&&shell.dataset.workshopState==="translating","closing settings restores prior manual idle and task state");
  console.log("ok");
})().catch(error=>{console.error(error.stack||error);process.exitCode=1})
''',
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_save_transfer_runtime_actions_and_state_gating(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index("const savesTop=textNode(")
        end = js.index("const cleanupTop=textNode(", start)
        save_runtime = js[start:end]
        behavior = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
Object.defineProperty(globalThis,"navigator",{value:{userAgent:"Android 12"},configurable:true});
let workshopState="idle",archives=[{name:"first.zip",path:"/downloads/first.zip",size:1024},{name:"second.zip",path:"/downloads/second.zip",size:2048}];
let backups=[{name:"backup",path:"/backups/one",fileCount:2,modifiedAt:1}];
const calls={restore:[],share:[],delete:[],export:[],listBackups:0,listArchives:0,imports:[],deleteArchive:[],listGames:0};
function readTaskSnapshot(){return{state:workshopState}}
window.Capacitor={Plugins:{FileManager:{
  listSaveBackups:async()=>{calls.listBackups++;return{backups}},
  restoreSaves:async input=>{calls.restore.push(input);return{restoredFiles:2}},
  shareSaveBackup:async input=>{calls.share.push(input);return{shared:true}},
  deleteBackup:async input=>{calls.delete.push(input);return{deletedFiles:2}},
  exportSavesToDownloads:async input=>{calls.export.push(input);return{path:"/downloads/export.zip"}},
  listSaveArchives:async()=>{calls.listArchives++;return{archives}},
  importSaveBackup:async input=>{calls.imports.push(input);return{packageName:"cim.isekai.game"}},
  deleteSaveArchive:async input=>{calls.deleteArchive.push(input);return{deleted:true}},
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"Export Game",packageName:"zitao.mbml"},{label:"Import Game",packageName:"cim.isekai.game"}]}}
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{},parent:null,type:""};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children=[];el.append(...nodes)};el.remove=function(){if(this.parent)this.parent.children=this.parent.children.filter(node=>node!==this)};el.setAttribute=(name,val)=>{el[name]=val};if(tag==="select")Object.defineProperty(el,"options",{get(){return el.children}});return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
const importView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  await gameBtn.onclick();gameSelect.value="zitao.mbml";gameSelect.onchange();
  await importGameBtn.onclick();importGameSelect.value="cim.isekai.game";importGameSelect.onchange();
  await refreshSaves();await importArchiveBtn.onclick();
  const saveActions=savesList.children[0].children.find(el=>el.cls==="workshop-save-actions").children;
  const restore=saveActions.find(el=>el.cls==="workshop-save-restore");
  const share=saveActions.find(el=>el.cls==="workshop-save-share");
  const del=saveActions.find(el=>el.cls==="workshop-save-delete");
  const archiveRows=importArchiveSection.children.filter(el=>el.cls==="workshop-save-row");
  const importOne=archiveRows[0].children.find(el=>el.cls==="workshop-save-restore");
  const deleteArchive=archiveRows[0].children.find(el=>el.cls==="workshop-save-delete");
  globalThis.confirm=()=>true;
  const busyActions=[
    ["export",()=>exportBtn.onclick(),()=>calls.export.length],
    ["restore",()=>restore.onclick(),()=>calls.restore.length],
    ["share",()=>share.onclick(),()=>calls.share.length],
    ["delete",()=>del.onclick(),()=>calls.delete.length],
    ["archive list",()=>importArchiveBtn.onclick(),()=>calls.listArchives],
    ["archive import",()=>importOne.onclick(),()=>calls.imports.length],
    ["archive delete",()=>deleteArchive.onclick(),()=>calls.deleteArchive.length],
    ["import game picker",()=>importGameBtn.onclick(),()=>calls.listGames],
  ];
  for(const state of ["scanning","translating","patching"]){
    workshopState=state;updateSavesState();updateImportState();
    const selection=[saveExportGamePackage,saveExportGameLabel,gameSelect.value,saveImportGamePackage,saveImportGameLabel,importGameSelect.value];
    const before=busyActions.map(action=>action[2]());
    for(const action of busyActions)await action[1]();
    const after=busyActions.map(action=>action[2]());
    check(JSON.stringify(before)===JSON.stringify(after),state+" busy actions must not call native methods: "+JSON.stringify({before,after}));
    const visible=(savesStatus.textContent+" "+importStatus.textContent+" "+gameLabel.textContent+" "+importGameLabel.textContent);
    check(visible.includes("正在处理任务"),state+" busy error is visible");
    check(JSON.stringify(selection)===JSON.stringify([saveExportGamePackage,saveExportGameLabel,gameSelect.value,saveImportGamePackage,saveImportGameLabel,importGameSelect.value]),state+" selections remain unchanged");
  }
  workshopState="idle";updateSavesState();updateImportState();const exportsBefore=calls.export.length;await exportBtn.onclick();
  check(calls.export.length===exportsBefore+1&&calls.export.at(-1).packageName==="zitao.mbml","idle export recovers after busy states");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + "\n" + save_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
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
let rejectImport=true,archives=[{name:"first.zip",path:"/downloads/first.zip",size:1024},{name:"second.zip",path:"/downloads/second.zip",size:2048}];
const calls={listArchives:0,imports:[],deleteArchive:[],listGames:0};
window.Capacitor={Plugins:{FileManager:{
  listSaveArchives:async()=>{calls.listArchives++;return{archives}},
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"Export Game",packageName:"zitao.mbml"},{label:"Import Game",packageName:"cim.isekai.game"}]}} ,
  importSaveBackup:async input=>{calls.imports.push(input);if(rejectImport)throw new Error("native import rejected");return{packageName:"cim.isekai.game"}},
  deleteSaveArchive:async input=>{calls.deleteArchive.push(input);return{deleted:true}},
  listSaveBackups:async()=>({backups:[]}),restoreSaves:async()=>({}),deleteBackup:async()=>({}),exportSavesToDownloads:async()=>({}),shareSaveBackup:async()=>({})
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{},parent:null,type:""};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children=[];el.append(...nodes)};el.remove=function(){if(this.parent)this.parent.children=this.parent.children.filter(node=>node!==this)};el.setAttribute=(name,val)=>{el[name]=val};if(tag==="select")Object.defineProperty(el,"options",{get(){return el.children}});return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
const importView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  await gameBtn.onclick();gameSelect.value="zitao.mbml";gameSelect.onchange();
  await importGameBtn.onclick();importGameSelect.value="cim.isekai.game";importGameSelect.onchange();
  const exportBefore=[saveExportGamePackage,saveExportGameLabel,gameSelect.value];
  await importArchiveBtn.onclick();
  let rows=importArchiveSection.children.filter(el=>el.cls==="workshop-save-row");
  const importOne=rows[0].children.find(el=>el.cls==="workshop-save-restore");
  await importOne.onclick();
  check(calls.imports.length===1&&calls.imports[0].path==="/downloads/first.zip"&&calls.imports[0].packageName==="cim.isekai.game","native import receives the complete selected URI and independent target package");
  check(saveImportArchiveUri==="","failed import clears the one-shot archive URI");
  check(importStatus.textContent.includes("native import rejected"),"native import rejection is visible");
  check(saveImportGamePackage==="cim.isekai.game"&&saveImportGameLabel==="Import Game"&&importGameSelect.value==="cim.isekai.game","failed import preserves target package label and selector");
  check(saveExportGamePackage===exportBefore[0]&&saveExportGameLabel===exportBefore[1]&&gameSelect.value===exportBefore[2],"failed import preserves export selection");
  check(importArchiveSection.children.filter(el=>el.cls==="workshop-save-row").length===2&&!importOne.disabled,"rejected archive row remains available for retry");
  rejectImport=false;await importOne.onclick();
  check(calls.imports.length===2&&calls.imports[1].path==="/downloads/first.zip"&&calls.imports[1].packageName==="cim.isekai.game","retry sends the same selected archive URI and target package");
  check(saveImportArchiveUri==="","successful import clears the one-shot archive URI");
  check(importStatus.textContent.includes("cim.isekai.game"),"successful import is visible");
  check(importArchiveSection.children.filter(el=>el.cls==="workshop-save-row").length===1,"successful import removes only the imported archive row");
  check(saveExportGamePackage===exportBefore[0]&&saveExportGameLabel===exportBefore[1]&&gameSelect.value===exportBefore[2],"successful import leaves export selection unchanged");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + "\n" + save_import_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
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
  listSaveGameApps:async()=>({apps:[{label:"Game One",packageName:"zitao.mbml"},{label:"Game Two",packageName:"cim.isekai.game"},{label:"Game Three",packageName:"com.yishijietiantang.com"}]}),
  listSaveBackups:async()=>({backups:[]}),listSaveArchives:async()=>({archives:[]}),
  restoreSaves:async()=>({}),deleteBackup:async()=>({}),exportSavesToDownloads:async()=>({}),shareSaveBackup:async()=>({}),importSaveBackup:async()=>({}),deleteSaveArchive:async()=>({})
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{},parent:null,type:""};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children=[];el.append(...nodes)};el.remove=function(){if(this.parent)this.parent.children=this.parent.children.filter(node=>node!==this)};el.setAttribute=(name,val)=>{el[name]=val};if(tag==="select")Object.defineProperty(el,"options",{get(){return el.children}});return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
const importView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  await importGameBtn.onclick();importGameSelect.value="cim.isekai.game";importGameSelect.onchange();
  check(saveImportGamePackage==="cim.isekai.game"&&saveImportGameLabel==="Game Two"&&importGameSelect.value==="cim.isekai.game","import selection is set first");
  await gameBtn.onclick();gameSelect.value="zitao.mbml";gameSelect.onchange();
  check(saveExportGamePackage==="zitao.mbml"&&saveExportGameLabel==="Game One"&&gameSelect.value==="zitao.mbml","export selection is set after import without overwriting it");
  check(saveImportGamePackage==="cim.isekai.game"&&saveImportGameLabel==="Game Two"&&importGameSelect.value==="cim.isekai.game","import remains isolated after export changes");
  gameSelect.value="com.yishijietiantang.com";gameSelect.onchange();
  check(saveExportGamePackage==="com.yishijietiantang.com"&&saveExportGameLabel==="Game Three"&&gameSelect.value==="com.yishijietiantang.com","export changes independently");
  importGameSelect.value="zitao.mbml";importGameSelect.onchange();
  check(saveImportGamePackage==="zitao.mbml"&&saveImportGameLabel==="Game One"&&importGameSelect.value==="zitao.mbml","import changes after export without overwriting it");
  check(saveExportGamePackage==="com.yishijietiantang.com"&&saveExportGameLabel==="Game Three"&&gameSelect.value==="com.yishijietiantang.com","export remains isolated after import changes");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + "\n" + save_import_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
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
  listSaveGameApps:async()=>{calls.listGames++;return{apps:[{label:"Game One",packageName:"zitao.mbml"},{label:"Game Two",packageName:"cim.isekai.game"}]}},
  listSaveBackups:async()=>{calls.listBackups++;return{backups:[]}},restoreSaves:async()=>({}),deleteBackup:async()=>({}),exportSavesToDownloads:async()=>({}),shareSaveBackup:async()=>({})
}}};
function textNode(tag,cls,text){const el={tag,cls,textContent:text??"",hidden:false,disabled:false,value:"",children:[],dataset:{},style:{},parent:null,type:""};el.append=(...nodes)=>{for(const node of nodes){node.parent=el;el.children.push(node)}};el.replaceChildren=(...nodes)=>{el.children=[];el.append(...nodes)};el.remove=function(){if(this.parent)this.parent.children=this.parent.children.filter(node=>node!==this)};el.setAttribute=(name,val)=>{el[name]=val};if(tag==="select")Object.defineProperty(el,"options",{get(){return el.children}});return el}
function viewBack(label,handler){const b=textNode("button","workshop-task-back",label);b.onclick=handler;return b}
function showMenu(){}
const savesView={children:[],append(...nodes){this.children.push(...nodes)}};
async function main(){
  check(exportBtn.disabled,"export is disabled before a game is selected");
  await gameBtn.onclick();
  check(calls.listGames===1&&calls.listInstalled===0,"picker uses save-aware native list without all-app fallback");
  check(gameSelect.children.length===3,"picker renders placeholder and both save-game apps");
  gameSelect.value="cim.isekai.game";gameSelect.onchange();
  check(saveExportGamePackage==="cim.isekai.game"&&saveExportGameLabel==="Game Two"&&gameSelect.value==="cim.isekai.game","picker preserves selected package label and selector");
  check(!exportBtn.disabled&&calls.listBackups>=1,"selected game enables export and refreshes backups");
  console.log("ok");
}
'''
        result = subprocess.run(
            ["node", "-e", behavior + "\n" + saves_runtime + "\nmain().catch(error=>{console.error(error.stack||error);process.exitCode=1})"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_install_bridge_refreshes_stale_react_button(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        trigger_runtime = extract_js_function(js, "function triggerReactButton(button)")
        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
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
        controller_runtime = extract_js_function(js, "Ce=async()=>")
        scheduler_runtime = extract_js_function(
            js, "async function runFileTasksParallel(e,t,concurrency=3)"
        )
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
window.__slgSelectionMeta={packageName:"com.example.game"};
globalThis.U=value=>String(value);
let n="/cache/game.apk",ae=[{name:"script.rpy",fileType:"rpy"}],te="api-key",oe=false;
let x="openai",re="https://openai.test/v1",S="model-a",y="zh",g="en",m=null,i="game.apk",fs=1,ps=1,_mode="full";
let vo={},cacheIndex={},_dirty={},bo=false,he={current:[]},requests=[],writes=[],currentRecords=[];
const _e=[{id:"openai",baseURL:"https://openai.test/v1"},{id:"deepseek",baseURL:"https://deepseek.test/v1"}];
function Co(){} function wo(){} function is(value){return value} function ns(){return true}
function ke(){return currentRecords}
function O(){} function ce(){} function fe(){} function ue(){} function w(){}
function Me(value){return value} function ds(value){return value}
function rs(file,records,translations){return{outputPath:`${file.name}.translated`,content:[...translations.entries()].map(([old,value])=>`${old}=${value}`).join("\n")}}
async function Ne(path,content){writes.push({path,content})}
const E={readFileContent:async()=>({content:"source",fileType:"rpy"}),compileTranslationsIntoApk:async()=>({compiled:0}),buildPatchedApk:async()=>({uri:"patched.apk"})};
async function Lo(args){requests.push({provider:x,model:S,baseURL:args.baseURL,texts:args.texts.map(item=>item.text)});return{translations:new Map(args.texts.map(item=>[item.text,`${item.text} translated`])),successCount:args.texts.length}}
'''
        behavior_contract += "let Ce;\n" + controller_runtime + "\n" + scheduler_runtime + r'''
async function run(sourceRecords,provider,model,endpoint,mode){currentRecords=sourceRecords;x=provider;S=model;re=endpoint;_mode=mode;await Ce()}
await run([{text:"same validated source text",keyPath:"script.rpy::1",duplicateKeys:[]}],"openai","model-a","https://openai.test/v1","full");
check(Object.keys(vo).filter(key=>key.startsWith("slg-file-v1:")).length===1,"production full path writes one file cache entry");
const cacheKey=Object.keys(vo).find(key=>key.startsWith("slg-file-v1:"));
check(cacheKey.startsWith("slg-file-v1:"),"current file cache namespace");
check(vo[cacheKey].translations[0][1]==="same validated source text translated","production path stores translated text");
const firstRequestCount=requests.length;
const firstWriteCount=writes.length;
await run([{text:"same validated source text",keyPath:"script.rpy::1",duplicateKeys:[]}],"deepseek","model-b","https://deepseek.test/v1","resume");
check(Object.keys(vo).filter(key=>key.startsWith("slg-file-v1:")).length===1,"provider/model changes preserve file cache identity");
check(requests.length===firstRequestCount,"matching current source reuses cache without translation request");
check(writes.length>firstWriteCount,"resume path regenerates output from cached translation");
await run([{text:"changed source text",keyPath:"script.rpy::1",duplicateKeys:[]}],"custom","model-c","https://custom.test/v1","resume");
check(requests.length===firstRequestCount+1,"changed source does not reuse stale cache");
check(requests.at(-1).texts.length===1&&requests.at(-1).texts[0]==="changed source text","changed source follows normal translation request");
const writesBeforeRemoval=writes.length;
await run([],"custom","model-d","https://custom.test/v1","resume");
check(requests.length===firstRequestCount+1,"removed source does not trigger a stale translation request");
check(writes.length===writesBeforeRemoval,"removed source does not regenerate stale cached output");
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
            '\u65e0\u6cd5\u8fde\u63a5 ${P}',
            '\u8bf7\u68c0\u67e5\u7f51\u7edc\uff0c\u6216\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546\u3002',
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
  check(providerLabel(`https://example.invalid/v1`)===`\u81ea\u5b9a\u4e49\u63a5\u53e3`,`custom label`);

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

  let requestCalls=0;
  globalThis.Vo=async()=>{requestCalls+=1;throw sdkError};
  let rejected=false;
  try{await Bo({},`model`,[{},{},{},{}],`en`,`zh`,void 0,!0)}catch(error){rejected=error===sdkError}
  check(rejected,`network error escapes recursive split`);
  check(requestCalls===1,`network request is not recursively retried`);

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
  check(result.error===`\u65e0\u6cd5\u8fde\u63a5 DeepSeek\u3002\u8bf7\u68c0\u67e5\u7f51\u7edc\uff0c\u6216\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546\u3002`,`actionable fatal error survives partial results`);
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
        self.assertIn('...r?{error:N||`\u90e8\u5206\u6587\u4ef6\u5904\u7406\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u65e5\u5fd7`}:{}', js)

        start = js.index('async function runFileTasksParallel(e,t,concurrency=3)')
        end = js.index('async function Lo(e){', start)
        scheduler = js[start:end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  const fatal=`\u65e0\u6cd5\u8fde\u63a5 OpenAI\u3002\u8bf7\u68c0\u67e5\u7f51\u7edc\uff0c\u6216\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546\u3002`;
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

        runtime = "\n".join(
            extract_js_function(js, signature)
            for signature in (
                "function isNetworkFailure(e)",
                "function networkFailureParts(e)",
                "function providerLabel(e)",
                "function isProviderNetworkFailure(e)",
                "async function runFileTasksParallel(e,t,concurrency=3)",
                "async function Bo(",
                "async function Lo(e){",
            )
        )
        outer_controller = extract_js_expression(js, "Ce=async()=>")
        package_gate = "if(!N&&(a.length>0||oe))"
        build_marker = "await E.buildPatchedApk"
        self.assertEqual(outer_controller.count(package_gate), 1)
        self.assertIn(build_marker, outer_controller)
        self.assertLess(
            outer_controller.index(package_gate),
            outer_controller.index(build_marker),
        )
        completion_anchor = "t+=p,O("
        self.assertEqual(outer_controller.count(completion_anchor), 1)
        outer_controller = outer_controller.replace(
            completion_anchor,
            "t+=p,globalThis.__slgRecordFileCompletion?.(),O(",
            1,
        )

        behavior_contract = "\n".join(
            (
                runtime,
                r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
globalThis.document={querySelector(){return null}};
const fatal=`无法连接 DeepSeek。请检查网络，或前往“我的”切换供应商。`;
const providerError=new Error(`Connection error`);
providerError.name=`APIConnectionError`;
providerError.cause={code:`ETIMEDOUT`};
let requestCalls=0,writeCalls=0,buildCalls=0,completedFiles=0,finalResult=null;
globalThis.Vo=async()=>{requestCalls+=1;throw providerError};
globalThis.__slgApiSemaphore={run:async fn=>fn()};
globalThis.Co=async()=>{};
globalThis.No=texts=>texts;
globalThis.xo=()=>`scope`;
globalThis.Se=()=>null;
globalThis.To=()=>null;
globalThis.Wo=(map,item,value)=>map.set(item.id,value);
globalThis.Eo=()=>{};
globalThis.wo=async()=>{};
globalThis.H=class{};
globalThis.zo=items=>[items];
globalThis.Ro=item=>item;
globalThis.Ao=1;
globalThis.jo=1;
globalThis.Ko=()=>0;
globalThis.__slgRecordFileCompletion=()=>{completedFiles+=1};
globalThis.O=()=>{};
globalThis.ue=()=>{};
globalThis.ce=()=>{};
globalThis.fe=result=>{finalResult=result};
globalThis.he={current:[]};
globalThis.w=()=>{};
globalThis.U=value=>value;
globalThis.ds={rpy:`rpy`};
globalThis.ke=()=>[{id:0,text:`hello`,duplicateKeys:[]}];
globalThis.rs=()=>({outputPath:`tl/zh.rpy`,content:`translated`});
globalThis.ns=()=>true;
globalThis.qe=()=>`translated`;
globalThis.Ne=async()=>{writeCalls+=1};
globalThis.is=value=>value;
globalThis.Me=value=>value;
globalThis.E={
  createDirectory:async()=>{},
  readFileContent:async()=>({content:`hello`,fileType:`rpy`}),
  compileTranslationsIntoApk:async()=>{throw new Error(`compile must not run`)},
  buildPatchedApk:async()=>{buildCalls+=1},
};
globalThis.n=`source.apk`;
globalThis.ae=[{name:`script.rpy`,fileType:`rpy`}];
globalThis.te=`test-api-key`;
globalThis.oe=false;
globalThis.x=`deepseek`;
globalThis.re=``;
globalThis._e=[{id:`deepseek`,baseURL:`https://api.deepseek.com/v1`}];
globalThis.S=`test-model`;
globalThis.m=null;
globalThis.g=`en`;
globalThis.y=`zh`;
globalThis.ps=1;
globalThis._mode=`test`;
globalThis.vo={};
globalThis.cacheIndex={};
globalThis._dirty={};
globalThis.bo=false;
globalThis.__slgLocalSelected=false;
let Ce;
''',
                outer_controller,
                r'''
async function main(){
  await Ce();
  check(requestCalls===1,`fatal provider rejection happens once through Vo`);
  check(finalResult&&finalResult.success===false,`outer result is failed`);
  check(finalResult.error===fatal,`outer result preserves network error`);
  check(writeCalls===0,`fatal network does not write partial translations`);
  check(buildCalls===0,`fatal network does not package cached or partial files`);
  check(completedFiles===0,`fatal network does not complete a file`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
''',
            )
        )
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
        self.assertIn('actionButton("\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546",openSettings)', js)
        self.assertIn('actionButton("\u91cd\u8bd5\u7ffb\u8bd1",()=>retryTask(', js)

        snapshot_start = js.index('function readTaskSnapshot(){')
        snapshot_end = js.index('function detailToggle(', snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        render_start = js.index('function renderStateBody(')
        render_end = js.index('function setWorkshopState(', render_start)
        render_runtime = js[render_start:render_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const fatal=`\u65e0\u6cd5\u8fde\u63a5 DeepSeek\u3002\u8bf7\u68c0\u67e5\u7f51\u7edc\uff0c\u6216\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546\u3002`;
function sourceText(){return `\u6b63\u5728\u5904\u7406\u811a\u672c 1 / 2\n\u7ffb\u8bd1\u5931\u8d25: ${fatal}`}
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
const settings=buttons.find(button=>button.label===`\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546`);
const retry=buttons.find(button=>button.label===`\u91cd\u8bd5\u7ffb\u8bd1`);
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

    def _legacy_test_long_running_phases_are_not_reported_as_directory_scanning(self):
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
        snapshot = extract_js_function(js, "function readTaskSnapshot()")
        contract = r'''
globalThis.window=globalThis;
window.__slgSelectionError=null;
window.__slgSelectionEpoch=7;
window.__slgSelectionMeta={splitApk:true,splitCount:4};
window.__slgScanWatchdog={epoch:7,timerFired:false,settled:true,applied:false};
function sourceText(){return `\u53d1\u73b0 0 \u4e2a\u53ef\u7ffb\u8bd1\u6587\u4ef6 \u5df2\u9009\u62e9\uff1a\u8ba1\u7b97\u5668.apk`}
function readProgressLog(){return {raw:``,latest:``}}
globalThis.document={querySelectorAll(){return []}};
const result=readTaskSnapshot();
if(result.state!==`empty`||result.count!==`0`||result.fileName!==`\u8ba1\u7b97\u5668.apk`||!result.splitApk||result.splitCount!==4){
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
        self.assertIn('split?"\u8be5\u5e94\u7528\u4f7f\u7528\u62c6\u5206\u5b89\u88c5\u5305"', js)
        self.assertIn('\u5171 \x24{payload.splitCount||0} \u4e2a\u62c6\u5206\u5305', js)

    def _legacy_test_translation_logs_are_mirrored_into_the_visible_shell(self):
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


    def _legacy_ready_mode_selector_and_completed_language_guidance(self):
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


        snapshot_runtime = extract_js_function(js, "function readTaskSnapshot()")
        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
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

function collectText(node,into){if(node&&node.text!==undefined)into.push(String(node.text));for(const child of node.children||[])collectText(child,into)}
function completedTexts(payload){const body=renderStateBody(`completed`,{fileName:`Game.apk`,count:`12`,translated:`34`,patchedApkPath:`/sdcard/Game-patched-signed.apk`,raw:`done`,latest:``,installAvailable:false,...payload});const texts=[];collectText(body,texts);return texts.join(`\n`)}
const selectable=completedTexts({activationMode:`selectable`,renpyLang:``,renpyMenuType:`renpy`});
check(selectable.includes(`\u8bf7\u8fdb\u5165\u6e38\u620f\u8bbe\u7f6e`),`selectable guidance enters game settings`);
check(selectable.includes(`\u7ffb\u8bd1\u6587\u672c`),`selectable guidance names the translation choice`);
check(selectable.includes(`\u5141\u8bb8\u5207\u56de\u539f\u6587`),`selectable guidance permits switching back to original`);

const alwaysOn=completedTexts({activationMode:`always_on`,renpyLang:``,renpyMenuType:`none`});
check(alwaysOn.includes(`\u542f\u52a8\u65f6\u9ed8\u8ba4\u542f\u7528`),`always-on guidance says translation starts enabled`);
check(alwaysOn.includes(`\u6e38\u620f\u5185\u4e0d\u80fd\u5207\u56de\u539f\u6587`),`always-on guidance forbids an in-game switch back`);

const custom=completedTexts({activationMode:``,renpyLang:``,renpyMenuType:`custom`});
check(custom.includes(`\u81ea\u5b9a\u4e49\u8bed\u8a00\u7cfb\u7edf`),`custom language system warning rendered`);
check(custom.includes(`\u4e0d\u80fd\u901a\u8fc7\u6807\u51c6\u8bed\u8a00\u83dc\u5355\u9009\u62e9`),`custom guidance excludes the standard language menu`);
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


    def test_ready_mode_selector_and_completed_language_guidance(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        snapshot_runtime = extract_js_function(js, "function readTaskSnapshot()")
        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
globalThis.localStorage={getItem(){return null},removeItem(){},setItem(){}};
const SESSION_KEY=`slg-workshop-session-v1`;
let sessionRestoredAt=0,installButton=null;
window.__slgRenpyLang=`schinese`;
window.__slgRenpyMenuType=`renpy`;
function sourceText(){return `\u7ffb\u8bd1\u5b8c\u6210\n\u5df2\u5199\u5165\u8865\u4e01 APK`}
function readProgressLog(){return{raw:`done`,latest:`done`}}
const document={querySelectorAll(){return[]}};
const snapshot=readTaskSnapshot();
check(snapshot.state===`completed`&&snapshot.renpyLang===`schinese`&&snapshot.renpyMenuType===`renpy`,`completed metadata flows into snapshot`);
function textNode(tag,cls,text){return{tag,cls,text:text||``,children:[],dataset:{},style:{},setAttribute(){},append(...children){this.children.push(...children)}}}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary,children:[]}}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function recoveryBanner(){return textNode(`section`,`banner`,`banner`)}
function savePatchedApk(){} function triggerReactButton(){} function openSourceChooser(){} function openSettings(){} function retryTask(){}
const startButton=null;
function findButton(){return null}
function completedText(payload){const body=renderStateBody(`completed`,{fileName:`Game.apk`,count:`12`,translated:`34`,patchedApkPath:`/sdcard/Game-patched-signed.apk`,raw:`done`,latest:``,installAvailable:false,...payload});const texts=[];function collect(node){if(node&&node.text!==undefined)texts.push(String(node.text));for(const child of node?.children||[])collect(child)}collect(body);return texts.join(`\n`)}
const selectable=completedText({activationMode:`selectable`,renpyLang:``,renpyMenuType:`renpy`});
const selectableChecks=[selectable.includes(`\u8bf7\u8fdb\u5165\u6e38\u620f\u8bbe\u7f6e`),selectable.includes(`\u7ffb\u8bd1\u6587\u672c`),selectable.includes(`\u5141\u8bb8`)&&selectable.includes(`\u5207\u56de\u539f\u6587`)];
check(selectableChecks.every(Boolean),`selectable guidance is reversible through game settings: ${JSON.stringify(selectableChecks)}`);
const alwaysOn=completedText({activationMode:`always_on`,renpyLang:``,renpyMenuType:`none`});
check(alwaysOn.includes(`\u542f\u52a8\u65f6\u9ed8\u8ba4\u542f\u7528`)&&alwaysOn.includes(`\u6e38\u620f\u5185\u4e0d\u80fd\u5207\u56de\u539f\u6587`),`always-on guidance is startup-only and not reversible in-game`);
const custom=completedText({activationMode:``,renpyLang:``,renpyMenuType:`custom`});
check(custom.includes(`\u81ea\u5b9a\u4e49\u8bed\u8a00\u7cfb\u7edf`)&&custom.includes(`\u4e0d\u80fd\u901a\u8fc7\u6807\u51c6\u8bed\u8a00\u83dc\u5355\u9009\u62e9`),`custom guidance excludes the standard language menu`);
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + render_runtime + behavior_contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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


        pipeline_parser = extract_js_function(js, "function Ne(e,t=``,n)").replace(
            "function Ne(", "function parseRpyc(", 1
        )
        pipeline_controller = extract_js_function(js, "Ce=async()=>")
        pipeline_parallel = extract_js_function(js, "async function runFileTasksParallel")
        values = [
            "Line one\\nLine two",
            "Line one\nLine two",
            r"C:\game\script",
            "中文“测试”",
        ]
        values_json = json.dumps(values, ensure_ascii=False)
        pipeline_harness = r"""
%s
%s
%s
const expected = %s;
const NL = String.fromCharCode(10);
function check(condition, label) { if (!condition) throw new Error(label); }
function emitRpycString(value) {
  return "RPYC_STRING\t" + value
    .replaceAll("\\", "\\\\")
    .replaceAll(NL, "\\n")
    .replaceAll("\\r", "\\\\r")
    .replaceAll("\\t", "\\\\t") + NL;
}
        const protocol = expected.map(emitRpycString).join("");
        check(parseRpyc(protocol, "", "en").length === expected.length,
              "protocol extraction before Ce preserves all four values");
globalThis.window = globalThis;
window.__slgSelectionMeta = {packageName: "com.example.game"};
let n = "source.apk", ae = [{name: "script.rpyc", fileType: "rpyc"}];
let te = "api-key", oe = false, x = "openai", re = "https://openai.test/v1";
let S = "model-a", y = "zh", g = "en", m = null, ps = 1, fs = 1, _mode = "full";
let vo = {}, cacheIndex = {}, _dirty = {}, bo = false, he = {current: []};
const requests = [], writes = [], compileRequests = [];
const _e = [{id: "openai", baseURL: "https://openai.test/v1"}];
function Co() {}
function wo() {}
function is(value) { return String(value); }
function U(value) { return String(value); }
function Me() { return "patched.apk"; }
function ns() { return true; }
function O() {}
function ce() {}
function fe() {}
function ue() {}
function w() {}
function ds(value) { return value; }
function ke(content, fileType, prefix, sourceLang) {
  return parseRpyc(content, prefix, sourceLang);
}
function rs(file, records, translations, language) {
  return {
    outputPath: file.name + "." + language,
    content: JSON.stringify(records.map(item => ({
      keyPath: item.keyPath,
      oldText: item.text,
      newText: translations.get(item.keyPath) || translations.get(item.text) || ""
    })))
  };
}
async function Ne(path, content) { writes.push({path, content}); }
async function Lo(args) {
  requests.push(args.texts.map(item => item.text));
  const translations = new Map();
  for (const item of args.texts) {
    const value = "translated: " + item.text;
    translations.set(item.keyPath, value);
    translations.set(item.text, value);
  }
  return {translations, successCount: args.texts.length, error: ""};
}
const protocolInput = protocol;
const E = {
  createDirectory: async () => ({}),
  readRenpyTexts: async () => ({content: protocolInput, fileType: "rpyc", renpyRecords: []}),
  compileTranslationsIntoApk: async args => {
    compileRequests.push(args);
    return {compiled: args.items.length};
  },
  buildPatchedApk: async () => ({uri: "patched.apk"})
};
%s
%s
async function main() {
  await Ce();
  const cacheKeys = Object.keys(vo).filter(key => key.startsWith("slg-file-v1:"));
  check(cacheKeys.length === 1, "one stable file cache entry");
  check(cacheKeys[0] === "slg-file-v1:com.example.game|script.rpyc|en|zh",
        "cache key preserves source identity only");
  check(vo[cacheKeys[0]].texts.map(item => item.text).join("\u0000") === expected.join("\u0000"),
        "cache keeps exact story text");
  check(requests.length === 1 && requests[0].length === expected.length,
        "translation receives all four exact values");
  check(compileRequests.length === 1, "compile request is issued once");
  const rows = compileRequests[0].items.flatMap(item => JSON.parse(item.content));
  check(rows.slice(0, expected.length).map(row => row.oldText).join("\u0000") === expected.join("\u0000"),
        "compile request keeps exact values");
  check(new Set(rows.map(row => row.oldText)).size === expected.length,
        "compile request collapses distinct values");
  console.log("ok");
}
main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
""" % (pipeline_parser, pipeline_controller, pipeline_parallel, values_json, "", "")
        result = subprocess.run(
            ["node", "-e", pipeline_harness.replace("__BT__", chr(96))],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_rpyc_protocol_escapes_backslashes_before_newlines(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        parser = extract_js_function(js, "function Ne(e,t=``,n)").replace(
            "function Ne(", "function parseRpyc(", 1
        )
        values = [
            "Line one\\nLine two",
            "Line one\nLine two",
            r"C:\game\script",
            "中文“测试”",
        ]
        values_json = json.dumps(values, ensure_ascii=False)
        harness = r"""
%s
const expected = %s;
const NL = String.fromCharCode(10);
function check(condition, label) { if (!condition) throw new Error(label); }
function emitRpycString(value) {
  return "RPYC_STRING\t" + value
    .replaceAll("\\", "\\\\")
    .replaceAll(NL, "\\n")
    .replaceAll("\\r", "\\\\r")
    .replaceAll("\\t", "\\\\t") + NL;
}
for (let index = 0; index < expected.length; index++) {
  const decoded = parseRpyc(emitRpycString(expected[index]), "", "en");
  check(decoded.length === 1 && decoded[0].text === expected[index],
        "protocol round-trip mismatch at " + index);
}
const literal = parseRpyc(emitRpycString(expected[0]), "", "en")[0].text;
const newline = parseRpyc(emitRpycString(expected[1]), "", "en")[0].text;
check(literal !== newline && literal.includes("\\n") && newline.includes(NL),
      "literal backslash-n and real newline collapsed");
console.log("ok");
""" % (parser, values_json)
        result = subprocess.run(
            ["node", "-e", harness],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_restore_session_preserves_complete_source_set_metadata(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        restore_runtime = extract_js_function(js, "function restoreSession()")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}};
globalThis.localStorage=localStorage;
window.__slgSelectionMeta=null;
let restoringSession=false,sessionRestoredAt=0,loaded=null;
window.__slgLoadSelectedApk=async selection=>{loaded=selection};
function refresh(){}
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function main(){
  localStorage.data[SESSION_KEY]=JSON.stringify({
    uri:"file://base.apk",baseUri:"file://base.apk",
    splitUris:["file://config.apk","file://lang.apk"],
    splitNames:["config.apk","lang.apk"],splitCount:2,
    name:"Game.apk",label:"Game",packageName:"game.pkg",
    versionCode:17,source:"installed",savedAt:123,translating:true
  });
  restoreSession();await tick();
  check(loaded&&loaded.uri==="file://base.apk"&&loaded.baseUri==="file://base.apk","restore preserves uri and baseUri");
  check(loaded.splitUris.join(",")==="file://config.apk,file://lang.apk"&&loaded.splitNames.join(",")==="config.apk,lang.apk"&&loaded.splitCount===2,"restore preserves split metadata");
  check(loaded.packageName==="game.pkg"&&loaded.versionCode===17&&loaded.source==="installed","restore preserves package version and source");
  check(loaded.name==="Game.apk"&&loaded.label==="Game"&&loaded.splitApk===false,"restore preserves display metadata and scan mode");
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", restore_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installed_source_refresh_preserves_existing_split_metadata(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        merge_runtime = extract_js_expression(js, "mergeSelectionMetadata=") + ";"
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
'''
        contract = behavior_contract + "\nlet mergeSelectionMetadata;\n" + merge_runtime + r'''
const previous={uri:"file://old.apk",baseUri:"file://base.apk",
  splitUris:["file://config.apk","file://lang.apk"],
  splitNames:["config.apk","lang.apk"],splitCount:2,
  packageName:"old.pkg",versionCode:17,source:"installed",name:"Old.apk"};
const full=mergeSelectionMetadata(previous,{uri:"file://full.apk",baseUri:"file://full-base.apk",splitUris:["file://full-split.apk"],splitNames:["full-split.apk"],splitCount:1,packageName:"new.pkg",versionCode:18,source:"installed"});
check(full.uri==="file://full.apk"&&full.baseUri==="file://full-base.apk","complete refresh updates uri and baseUri");
check(full.splitUris.join(",")==="file://full-split.apk"&&full.splitNames.join(",")==="full-split.apk"&&full.splitCount===1,"complete refresh replaces the split tuple atomically");
check(full.packageName==="new.pkg"&&full.versionCode===18&&full.source==="installed","complete refresh preserves the complete SourceSet shape");
function assertPreviousTuple(update,label){
  const refreshed=mergeSelectionMetadata(previous,Object.assign({uri:"file://refreshed.apk"},update));
  check(refreshed.uri==="file://refreshed.apk"&&refreshed.baseUri===previous.baseUri,label+" keeps uri/baseUri behavior");
  check(JSON.stringify(refreshed.splitUris)===JSON.stringify(previous.splitUris)&&JSON.stringify(refreshed.splitNames)===JSON.stringify(previous.splitNames)&&refreshed.splitCount===previous.splitCount,label+" preserves the prior split tuple");
  check(refreshed.packageName===previous.packageName&&refreshed.versionCode===previous.versionCode&&refreshed.source===previous.source,label+" preserves the other SourceSet fields");
}
assertPreviousTuple({splitUris:[]},"only splitUris");
assertPreviousTuple({splitNames:["replacement.apk"]},"only splitNames");
assertPreviousTuple({splitCount:0},"only splitCount");
assertPreviousTuple({splitUris:["file://one.apk"],splitNames:["one.apk","extra.apk"],splitCount:1},"inconsistent split tuple");
'''
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=contract,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dismiss_recovery_banner_re_renders_immediately(self):
        """Dismissing the interrupted-session banner must re-render right away."""
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        snapshot_runtime = extract_js_function(js, "function readTaskSnapshot()")
        topbar_runtime = extract_js_function(js, "function renderTopbar(state)")
        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
        state_runtime = extract_js_function(js, "function setWorkshopState(state,payload={})")
        key_runtime = extract_js_function(js, "function snapshotKey(s)")
        refresh_runtime = extract_js_function(js, "function refresh()").replace("function refresh(){", "function refreshCore(){", 1)
        recovery_runtime = extract_js_function(js, "function recoveryBanner(savedAt)")
        restore_runtime = extract_js_function(js, "function restoreSession()")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}};
const document={querySelectorAll(){return[]}};
globalThis.localStorage=localStorage;
window.__slgSelectionMeta=null;
window.__slgLoadSelectedApk=async()=>{};
let detailsOpen=false,manualIdle=false,retrying=false,settingsOpen=false,lastSnapshot="",sessionRestoredAt=0,restoringSession=false;
let refreshes=0,renders=0;
function sourceText(){return`\u5df2\u9009\u62e9\uff1aBroken.apk \u53d1\u73b0 5 \u4e2a\u53ef\u7ffb\u8bd1\u6587\u4ef6`}
function readProgressLog(){return{raw:"",latest:""}}
function textNode(tag,cls,text){return{tag,cls,text:text||"",textContent:text||"",children:[],dataset:{},style:{},setAttribute(name,value){this[name]=value},append(...children){this.children.push(...children)}}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary,children:[]}}
function openSourceChooser(){} function openSettings(){} function retryTask(){} function triggerReactButton(){}
const startButton=null,installButton=null,sourceButton=null;
function startScanClock(){} function stopScanClock(){}
function classList(){return{remove(){},add(){}}}
let shell={dataset:{},classList:classList(),attrs:{},setAttribute(name,value){this.attrs[name]=value},replaceChildren(...nodes){renders+=1;this.rendered=nodes}};
const runtimeRoot={classList:classList(),setAttribute(){}};
function collectText(node){let out=node.text||"";for(const child of node.children||[])out+=collectText(child);return out}
function collectButtons(node,acc){if(!node)return acc;if(node.tag===`button`)acc.push(node);for(const child of node.children||[])collectButtons(child,acc);return acc}
function refresh(){refreshes+=1;refreshCore()}
localStorage.setItem(SESSION_KEY,JSON.stringify({uri:"file://picked.apk",name:"Broken.apk",packageName:"game.pkg",source:"installed",savedAt:123,translating:true}));
restoreSession();
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function main(){
await tick();
check(sessionRestoredAt===123,`restore reads translating session savedAt`);
let buttons=collectButtons(shell.rendered[1],[]);
const dismiss=buttons.find(b=>(b.label||b.text)===`\u653e\u5f03\u6062\u590d`);
check(dismiss,`recovery banner offers dismiss`);
check(collectText(shell.rendered[1]).includes(`\u4e0a\u6b21\u7ffb\u8bd1\u4e2d\u65ad`),`banner visible before dismiss`);
check(refreshes===1&&renders===1,`restore refreshes and renders the recovery state`);
snapshotKey=()=>`constant`;
lastSnapshot=`constant`;
dismiss.onclick();
check(localStorage.getItem(SESSION_KEY)===null,`dismiss clears persisted session`);
check(sessionRestoredAt===0,`dismiss clears restored marker`);
check(refreshes===2&&renders===2,`dismiss invalidates snapshot cache and refreshes immediately`);
check(!collectText(shell.rendered[1]).includes(`\u4e0a\u6b21\u7ffb\u8bd1\u4e2d\u65ad`),`dismiss must re-render immediately without banner`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + topbar_runtime + render_runtime + state_runtime + key_runtime + refresh_runtime + recovery_runtime + restore_runtime + behavior_contract],
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
        restore_runtime = extract_js_function(js, "function restoreSession()")
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
        snapshot_runtime = extract_js_function(js, "function readTaskSnapshot()")
        key_runtime = extract_js_function(js, "function snapshotKey(s)")
        refresh_runtime = extract_js_function(js, "function refresh()")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
const SESSION_KEY="slg-workshop-session-v1";
const localStorage={data:{},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}};
const document={querySelectorAll(){return[]}};
let detailsOpen=false,manualIdle=false,retrying=false,settingsOpen=false,lastSnapshot="",sessionLastBeat=0;
function sourceText(){return`\u6b63\u5728\u5904\u7406\u811a\u672c 1/5`}
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
            '.workshop-task-shell[data-workshop-state="translating"].workshop-task-card{animation:none}',
            compact_css,
        )
        self.assertIn(
            '.workshop-task-shell[data-workshop-state="patching"].workshop-task-card{animation:none}',
            compact_css,
        )
        self.assertIn("animation:workshopRise", compact_css)

    def _legacy_test_translation_progress_emits_starting_batch_before_request(self):
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


    def test_long_running_phases_are_not_reported_as_directory_scanning(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        snapshot_runtime = extract_js_function(js, "function readTaskSnapshot()")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
window.__slgSelectionError=null;
window.__slgSelectionEpoch=1;
window.__slgSelectionMeta={};
window.__slgScanWatchdog={epoch:1,timerFired:false,settled:false};
globalThis.findButton=()=>null;
let installButton=null;
let sessionRestoredAt=0;
globalThis.document={querySelectorAll(){return []}};
let phase="";
function sourceText(){return phase}
function readProgressLog(){return{raw:"latest log",latest:"latest log"}}
const cases=[
  ["\u6b63\u5728\u626b\u63cf\u6587\u4ef6","scanning"],
  ["\u5f00\u59cb\u5904\u7406 2 \u4e2a\u6587\u4ef6","translating"],
  ["\u6b63\u5728\u751f\u6210 Ren'Py \u8865\u4e01 APK","patching"],
  ["\u7ffb\u8bd1\u5931\u8d25：\u65e0\u6cd5\u8fde\u63a5 OpenAI\u3002\u8bf7\u68c0\u67e5\u7f51\u7edc\uff0c\u6216\u524d\u5f80\u201c\u6211\u7684\u201d\u5207\u6362\u4f9b\u5e94\u5546\u3002","failed"],
  ["\u7ffb\u8bd1\u5b8c\u6210\n\u8865\u4e01 APK \u5df2\u751f\u6210","completed"]
];
for(const [text,expected] of cases){
  phase=text;
  const result=readTaskSnapshot();
  check(result.state===expected,expected+" state: "+JSON.stringify(result));
  if(expected==="failed")check(result.reason==="network","fatal network reason");
}
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("setWorkshopState(state,payload={})", js)
        self.assertIn("state===\"scanning\"?startScanClock():stopScanClock()", js)
        for state in ("scanning", "translating", "patching", "completed", "failed"):
            self.assertIn(f'workshop-state-{state}', js)
            self.assertIn(
                f'workshop-task-shell[data-workshop-state="{state}"]', css
            )

    def test_translation_logs_are_mirrored_into_the_visible_shell(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        log_runtime = extract_js_function(js, "function readProgressLog()")
        render_runtime = extract_js_function(
            js, "function renderStateBody(state,payload)"
        )
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
const rows=Array.from({length:42},(_,index)=>({innerText:"log-"+index,textContent:"log-"+index}));
const source={children:rows,closest:()=>null};
globalThis.document={querySelectorAll(selector){
  return selector==="#root [class*='font-mono']"?[source]:[];
}};
const progress=readProgressLog();
check(progress.latest==="log-41","latest log is selected");
check(progress.raw.split("\n").length===40,"visible log mirror is bounded");
const logLines=progress.raw.split("\n");
check(!logLines.includes("log-0")&&!logLines.includes("log-1"),"old logs are not replayed");
function textNode(tag,cls,text){return{tag,cls,text,children:[],dataset:{},style:{},append(...children){this.children.push(...children)}}}
function fileRow(name){return textNode("div","file-row",name)}
function detailToggle(raw){return textNode("div","details",raw)}
function collect(node,found=[]){if(!node)return found;if(node.cls)found.push(node);for(const child of node.children||[])collect(child,found);return found}
const translating=renderStateBody("translating",{fileName:"game.apk",current:1,total:2,latest:progress.latest,raw:progress.raw});
const live=collect(translating).filter(node=>node.cls==="workshop-live-line");
check(live.length===1&&live[0].text==="log-41","translating shell mirrors latest log");
const completed=renderStateBody("completed",{fileName:"game.apk",count:1,translated:1,latest:progress.latest,raw:progress.raw});
check(collect(completed).filter(node=>node.cls==="workshop-progress").length===0,"completed shell has no active progress");
check(collect(completed).some(node=>node.cls==="workshop-live-line"&&node.text==="log-41"),"completed shell retains latest log as history");
'''
        result = subprocess.run(
            ["node", "-e", log_runtime + render_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_translation_progress_emits_starting_batch_before_request(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        runtime = "\n".join(
            (
                extract_js_function(js, "function isNetworkFailure(e)"),
                extract_js_function(js, "async function Bo(e,t,n,r,i,a,o,s=0)"),
                extract_js_function(js, "async function Lo(e)"),
            )
        )
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.Co=async()=>{};
globalThis.No=texts=>texts;
globalThis.xo=()=>1;
globalThis.Se=()=>null;
globalThis.To=()=>null;
globalThis.Wo=(map,item,value)=>map.set(item.keyPath||item.text,value);
globalThis.Eo=()=>{};
globalThis.wo=async()=>{};
globalThis.H=class{};
globalThis.zo=items=>items.map(item=>[item]);
globalThis.Ao=4;
globalThis.jo=1;
globalThis.Ko=()=>0;
globalThis.__slgApiSemaphore={run:fn=>fn()};
globalThis.__slgRecordTranslationCandidates=()=>{};
globalThis.__slgRecordValidatorApprovedTranslations=()=>{};
globalThis.providerLabel=()=> "OpenAI";
globalThis.Ro=item=>item;
const events=[];
globalThis.Vo=async(_client,_model,batch)=>{
  events.push("request:"+batch[0].text);
  return new Map(batch.map((_,index)=>[index,"ok"]));
};
async function main(){
  const result=await Lo({texts:[{keyPath:"a",text:"A",duplicateKeys:[]},{keyPath:"b",text:"B",duplicateKeys:[]}],sourceLang:"en",targetLang:"zh",baseURL:"https://api.openai.com/v1",apiKey:"key",model:"m",batchSize:1,onProgress:(e,t,n,r)=>{
    if(r&&r.stage)events.push(r.stage+":"+r.currentBatch);
  }});
  check(result.successCount===2,"both batches translate: "+JSON.stringify(result)+" events="+JSON.stringify(events));
  check(events.indexOf("start:1")>=0,"starting batch is emitted");
  check(events.indexOf("start:1")<events.indexOf("request:A"),"starting batch precedes first request");
  check(events.indexOf("start:2")<events.indexOf("request:B"),"second starting batch precedes second request");
  check(events.includes("completed:2"),"completed batches remain observable");
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
