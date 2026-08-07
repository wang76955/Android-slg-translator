import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAST_SCAN = ROOT / "apk-work" / "native-fast-scan"
BASE_JS = ROOT / "apk-work" / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
BASE_CSS = ROOT / "apk-work" / "extracted" / "assets" / "public" / "assets" / "index-C044IUg3.css"
COMPATIBILITY_MATRIX = ROOT / "docs" / "qa" / "renpy-compatibility-matrix.md"
RELEASE_CHECKLIST = ROOT / "docs" / "qa" / "renpy-release-checklist.md"
JAVA_HOME = Path(os.environ.get("JAVA_HOME", ""))
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"


def third_party_classpath():
    from test_fast_scanner import third_party_classpath as classpath
    return classpath()


def load_patch_workshop_ui():
    module_path = ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py"
    spec = importlib.util.spec_from_file_location("patch_workshop_ui", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise AssertionError("node failed: " + (result.stderr or "")[:3000])
    return result.stdout


class TranslationCoverageLogicTest(unittest.TestCase):
    """Pure-Python coverage comparison used by the full APK audit."""

    def test_revalidation_evidence_uses_only_explicit_statuses(self):
        evidence = (ROOT / "docs/qa/renpy-batch-bc-evidence.md").read_text(encoding="utf-8")
        lines = evidence.splitlines()
        header = [
            "requirementId", "sourceRequirement", "implementation", "automatedTest",
            "command", "status", "artifact", "residualRisk", "commit",
        ]
        header_line_index = lines.index(
            "| requirementId | sourceRequirement | implementation | automatedTest | command | status | artifact | residualRisk | commit |"
        )
        self.assertEqual(
            [cell.strip() for cell in lines[header_line_index].split("|")[1:-1]],
            header,
        )
        self.assertEqual(
            [cell.strip() for cell in lines[header_line_index + 1].split("|")[1:-1]],
            ["---"] * 9,
        )
        data_lines = []
        for line in lines[header_line_index + 2:]:
            if not line.strip():
                break
            self.assertTrue(line.startswith("|"), "unexpected content inside evidence table")
            data_lines.append(line)
        self.assertEqual(len(data_lines), 11)
        rows = []
        for line in data_lines:
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            self.assertEqual(len(cells), 9, "evidence row must have exactly nine columns")
            rows.append(cells)
        self.assertEqual({row[0] for row in rows}, {f"T{task}" for task in range(6, 17)})
        self.assertEqual(len({row[0] for row in rows}), 11)
        statuses = [row[5] for row in rows]
        self.assertTrue(all(status in {"PASS", "FAIL", "NOT-RUN"} for status in statuses))
        self.assertNotIn("assumed-pass", evidence.lower())
        self.assertNotIn("missing = 0 (inferred)", evidence.lower())

    def test_missing_strings_are_reported(self):
        corpus = {"Hello", "Choice A", "Name", "Screen Title"}
        translated = {"Hello", "Choice A"}
        missing = sorted(corpus - translated)
        self.assertEqual(missing, ["Name", "Screen Title"])

    def test_files_without_translation_counterpart_are_flagged(self):
        original_files = {
            "assets/x-game/x-ch1.rpyc",
            "assets/x-game/x-ch2.rpyc",
        }
        translated_files = {
            "assets/x-game/x-tl/x-slgtranslated/x-ch1.rpyc",
        }
        missing_files = sorted(
            name
            for name in original_files
            if not any(
                name.split("/")[-1] == tf.split("/")[-1]
                for tf in translated_files
            )
        )
        self.assertEqual(missing_files, ["assets/x-game/x-ch2.rpyc"])

    def test_builtin_chinese_coverage_is_separate(self):
        corpus = {"Hello", "Menu", "Unique"}
        builtin = {"Hello", "Menu"}      # official Chinese bucket
        translator = {"Hello", "Unique"}  # our slgtranslated bucket
        only_builtin = sorted(builtin - translator)
        self.assertEqual(only_builtin, ["Menu"])
        translator_only = sorted(translator - builtin)
        self.assertEqual(translator_only, ["Unique"])
        uncovered = sorted(corpus - builtin - translator)
        self.assertEqual(uncovered, [])

    def test_task8_collision_report_has_unique_old_occurrences_and_contexts(self):
        entries = [
            {"old": "OK{#menu}", "sourcePath": "game/a.rpyc", "speaker": "", "kind": "MENU"},
            {"old": "OK{#menu}", "sourcePath": "game/a.rpyc", "speaker": "", "kind": "MENU"},
            {"old": "Fine.", "sourcePath": "game/a.rpyc", "speaker": "alice", "kind": "DIALOGUE"},
            {"old": "Fine.", "sourcePath": "game/b.rpyc", "speaker": "bob", "kind": "DIALOGUE"},
        ]
        grouped = {}
        for item in entries:
            grouped.setdefault(item["old"], []).append(item)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped["OK{#menu}"]), 2)
        self.assertEqual({x["speaker"] for x in grouped["Fine."]}, {"alice", "bob"})

    def test_task10_java_report_counts_validated_rejected_collision_uncertain_and_files(self):
        source = r'''
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.TranslationCoverageReport;
import java.util.*;

public final class CoverageReportHarness {
  public static void main(String[] args) {
    List<RenpyTextRecord> records = Arrays.asList(
      new RenpyTextRecord("Hello", RenpyTextRecord.Kind.DIALOGUE, "alice", "", "game/a.rpyc", 10, 1, true),
      new RenpyTextRecord("Hello", RenpyTextRecord.Kind.DIALOGUE, "alice", "", "game/a.rpyc", 11, 2, true),
      new RenpyTextRecord("Missing", RenpyTextRecord.Kind.DIALOGUE, "bob", "", "game/b.rpyc", 20, 1, true),
      new RenpyTextRecord("Rejected", RenpyTextRecord.Kind.UI_STRING, "", "", "game/b.rpyc", 21, 1, true),
      new RenpyTextRecord("Uncertain", RenpyTextRecord.Kind.CUSTOM_STATEMENT, "", "", "game/c.rpyc", 30, 1, false),
      new RenpyTextRecord("MissingLater", RenpyTextRecord.Kind.DIALOGUE, "", "", "game/d.rpyc", 40, 1, true),
      new RenpyTextRecord("MissingAgain", RenpyTextRecord.Kind.DIALOGUE, "", "", "game/d.rpyc", 41, 1, true)
    );
    Map<String, String> validated = new LinkedHashMap<>();
    validated.put("Hello", "你好");
    Set<String> rejected = new LinkedHashSet<>(Collections.singleton("Rejected"));
    Set<String> uncertain = new LinkedHashSet<>(Collections.singleton("Uncertain"));
    Map<String, List<String>> candidates = new LinkedHashMap<>();
    candidates.put("Hello", Arrays.asList("你好", "您好"));
    Map<String, String> classifications = new LinkedHashMap<>();
    classifications.put("game/common.rpyc\tDeveloper", "developer_console");
    TranslationCoverageReport report = TranslationCoverageReport.build(
      records, validated, rejected, candidates, uncertain, classifications);
    require(report.uniqueSourceCount == 6, "unique source count");
    require(report.occurrenceCount == 7, "occurrence count");
    require(report.translatedCount == 1, "validated only count");
    require(report.missingCount == 3, "missing count");
    require(report.rejectedCount == 1, "rejected count");
    require(report.collisionCount == 1, "collision count");
    require(report.uncertainCount == 1, "uncertain count");
    require(report.files.size() == 4, "file count");
    TranslationCoverageReport.FileCoverage a = report.files.get("game/a.rpyc");
    require(a != null && a.sourceCount == 1 && a.occurrenceCount == 2
        && a.translatedCount == 1 && a.missingCount == 0 && a.rejectedCount == 0
        && a.collisionCount == 1 && a.uncertainCount == 0, "game/a.rpyc counts");
    TranslationCoverageReport.FileCoverage b = report.files.get("game/b.rpyc");
    require(b != null && b.sourceCount == 2 && b.occurrenceCount == 2
        && b.translatedCount == 0 && b.missingCount == 1 && b.rejectedCount == 1
        && b.collisionCount == 0 && b.uncertainCount == 0, "game/b.rpyc counts");
    TranslationCoverageReport.FileCoverage c = report.files.get("game/c.rpyc");
    require(c != null && c.sourceCount == 1 && c.occurrenceCount == 1
        && c.translatedCount == 0 && c.missingCount == 0 && c.rejectedCount == 0
        && c.collisionCount == 0 && c.uncertainCount == 1, "game/c.rpyc counts");
    TranslationCoverageReport.FileCoverage d = report.files.get("game/d.rpyc");
    require(d != null && d.sourceCount == 2 && d.occurrenceCount == 2
        && d.translatedCount == 0 && d.missingCount == 2 && d.rejectedCount == 0
        && d.collisionCount == 0 && d.uncertainCount == 0, "game/d.rpyc counts");
    List<TranslationCoverageReport.FileCoverage> topFiles = report.topMissingFiles();
    require(topFiles.size() == 2, "top missing file count");
    require("game/d.rpyc".equals(topFiles.get(0).filePath)
        && "game/b.rpyc".equals(topFiles.get(1).filePath), "top missing file ordering");
    require(report.topMissing().size() == 3 && "Missing".equals(report.topMissing().get(0).exactOld)
        && "MissingAgain".equals(report.topMissing().get(1).exactOld)
        && "MissingLater".equals(report.topMissing().get(2).exactOld), "top missing ordering");
    String json = report.toSanitizedJson();
    require(json.contains("uniqueSourceCount") && json.contains("game/b.rpyc")
        && json.contains("\"topMissingFiles\":[{\"sourceCount\":2,\"occurrenceCount\":2,\"translatedCount\":0,\"missingCount\":2,\"rejectedCount\":0,\"collisionCount\":0,\"uncertainCount\":0},{\"sourceCount\":2,\"occurrenceCount\":2,\"translatedCount\":0,\"missingCount\":1,\"rejectedCount\":1,\"collisionCount\":0,\"uncertainCount\":0}]"), "json fields and top files");
    require(!json.contains("你好") && !json.contains("您好"), "translations must not be exported");
    require(report.shouldBlockCompleteBuild(), "missing/rejected must block complete build");
    require(report.canGenerateIncompleteTestPatch(), "incomplete test patch remains available");
    TranslationCoverageReport.IncrementalDiff diff = TranslationCoverageReport.incrementalDiff(
      Arrays.asList("Hello", "Missing", "New"),
      new LinkedHashSet<>(Collections.singleton("Hello")),
      new LinkedHashSet<>(Collections.singleton("Missing")),
      new LinkedHashSet<>(Collections.singleton("New")));
    require(diff.requestExactOld.contains("Missing") && diff.requestExactOld.contains("New"), "incremental retry");
    require(!diff.requestExactOld.contains("Hello"), "unchanged validated entry reused");

    List<RenpyTextRecord> common = Arrays.asList(
      new RenpyTextRecord("Story common", RenpyTextRecord.Kind.DIALOGUE, "", "", "assets/x-renpy/x-common/story.rpyc", 1, 1, true),
      new RenpyTextRecord("Developer", RenpyTextRecord.Kind.CUSTOM_STATEMENT, "", "", "assets/x-renpy/x-common/debug.rpyc", 2, 1, true));
    TranslationCoverageReport commonReport = TranslationCoverageReport.build(
      common, Collections.singletonMap("Story common", "故事公共文本"), Collections.emptySet(),
      Collections.emptyMap(), Collections.emptySet(),
      Collections.singletonMap("assets/x-renpy/x-common/debug.rpyc\tDeveloper", "developer_console"));
    require(commonReport.uniqueSourceCount == 1, "x-common story text is included by default");
    require(commonReport.excludedReasons.containsValue("developer_console"), "x-common skip requires explicit reason");
  }
  private static void require(boolean value, String message) {
    if (!value) throw new AssertionError(message);
  }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="coverage-report-red-") as temporary:
            root = Path(temporary)
            harness = root / "CoverageReportHarness.java"
            classes = root / "classes"
            harness.write_text(source, "utf-8")
            classes.mkdir()
            result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs),
                 str(FAST_SCAN / "src/com/slgtranslator/app/RenpyTextRecord.java"),
                 str(FAST_SCAN / "src/com/slgtranslator/app/TranslationCoverageReport.java"),
                 str(harness)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "CoverageReportHarness"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_task10_ui_coverage_gate_and_sanitized_report_are_wired(self):
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        for token in (
            "TranslationCoverageReport", "missingCount", "rejectedCount", "uncertainCount",
            "topMissing", "x-common", "coverage", "incomplete", "__slgBuildCoverage",
            "__slgIncompleteTestPatch", "__slgTranslationCoverageReportJson",
            "__slgRecordValidatorApprovedTranslations?.(t,_lr.translations)",
            "__slgRecordTranslationCandidates?.(t,_lr.translations)",
            "__slgRecordTranslationCandidates?.(n,s)",
            "__slgRecordRejectedTranslations?.(_lr.rejected)",
            "coverageClassifications",
            "__slgResetTranslationCoverage",
            "function exact(value)",
        ):
            self.assertIn(token, source)
        self.assertIn("slg-translator-cache:", source)
        self.assertNotIn("slg-translator-cache:v2:", source)
        self.assertNotIn("__slgRecordValidatorApprovedTranslations?.(t,d)", source)

    def test_task10_ui_coverage_preserves_exact_text_and_resets_all_state(self):
        """Execute the generated coverage IIFEs for the critical gate edges."""
        if not (BASE_JS.exists() and BASE_CSS.exists()):
            self.skipTest("canonical workshop assets not present")
        patcher = load_patch_workshop_ui()
        base = BASE_JS.read_text("utf-8")
        css = BASE_CSS.read_text("utf-8")
        patched, _ = patcher.patch_assets(base, css)
        with tempfile.TemporaryDirectory(prefix="coverage-ui-behavior-") as temporary:
            js_path = Path(temporary) / "patched.js"
            js_path.write_text(patched, encoding="utf-8")
            js_literal = json.dumps(str(js_path))
            script = f"""
const fs = require('fs');
const js = fs.readFileSync({js_literal}, 'utf-8');
const marker = js.indexOf('function asMap(value)');
const start = js.lastIndexOf('(function(){{', marker);
const firstClose = js.indexOf('root.__slgRefreshTranslationCoverage()}})()', start);
const firstEnd = js.indexOf('}})()', firstClose) + 4;
const secondStart = js.indexOf('\\n(function(){{', firstEnd) + 1;
const secondEnd = js.indexOf('}})()', secondStart) + 4;
const thirdStart = js.indexOf('\\n(function(){{', secondEnd) + 1;
const thirdEnd = js.indexOf('}})()', thirdStart) + 4;
if (start < 0 || firstEnd <= start || secondStart <= firstEnd || secondEnd <= secondStart || thirdStart <= secondEnd || thirdEnd <= thirdStart) throw new Error('coverage IIFEs missing');
globalThis.window = globalThis;
eval(js.slice(start, firstEnd));
eval(js.slice(secondStart, secondEnd));
eval(js.slice(thirdStart, thirdEnd));
const records = [
  {{text:'line\\nnext', sourcePath:'game/a.rpyc', coverageCertain:true}},
  {{text:'line next', sourcePath:'game/a.rpyc', coverageCertain:true}},
  {{text:'Debug', sourcePath:'assets/x-renpy/x-common/debug.rpyc', coverageCertain:true}},
];
globalThis.__slgCoverageRecords = records;
let initial = globalThis.__slgRefreshTranslationCoverage();
globalThis.__slgRecordValidatorApprovedTranslations([records[0]], new Map([[0, '译文']]));
globalThis.__slgRecordTranslationCandidates([records[1]], new Map([[0, '甲']]));
globalThis.__slgRecordTranslationCandidates([records[1]], new Map([[0, '乙']]));
globalThis.__slgRecordRejectedTranslations([{{old:'line next'}}]);
const after = globalThis.__slgRefreshTranslationCoverage();
globalThis.__slgCoverageUncertain = ['stale'];
globalThis.__slgCoverageClassifications = {{stale:'developer_console'}};
globalThis.__slgTranslationCollisionCandidates = new Map([['stale', ['a', 'b']]]);
globalThis.__slgResetTranslationCoverage();
const reset = globalThis.__slgBuildTranslationCoverageReport([], new Map(), new Set(), [], {{}}, new Map());
process.stdout.write(JSON.stringify({{initial,after,reset}}));
"""
            result = json.loads(run_node(script))
        self.assertEqual(result["initial"]["uniqueSourceCount"], 2)
        self.assertEqual(result["initial"]["occurrenceCount"], 2)
        self.assertEqual(result["initial"]["missingCount"], 2)
        self.assertEqual(result["after"]["translatedCount"], 1)
        self.assertEqual(result["after"]["rejectedCount"], 1)
        self.assertEqual(result["after"]["collisionCount"], 1)
        self.assertEqual(result["reset"]["uniqueSourceCount"], 0)
        self.assertEqual(result["reset"]["occurrenceCount"], 0)

    def test_task10_generated_ui_build_branch_blocks_incomplete_and_warns_incomplete_patch(self):
        """Run the exact generated build gate, including both coverage branches."""
        if not (BASE_JS.exists() and BASE_CSS.exists()):
            self.skipTest("canonical workshop assets not present")
        patcher = load_patch_workshop_ui()
        patched, _ = patcher.patch_assets(BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8"))
        with tempfile.TemporaryDirectory(prefix="coverage-build-gate-") as temporary:
            js_path = Path(temporary) / "patched.js"
            js_path.write_text(patched, encoding="utf-8")
            script = f"""
const fs = require('fs');
const js = fs.readFileSync({json.dumps(str(js_path))}, 'utf-8');
const marker = 'if(!N&&(a.length>0||oe)){{globalThis.__slgRefreshTranslationCoverage?.()';
const start = js.indexOf(marker);
const end = js.indexOf('}},we=async', start);
if (start < 0 || end < 0) throw new Error('generated build gate missing');
const branch = js.slice(start, end);
if (!branch.includes('missingCount>0||_coverage.rejectedCount>0') || !branch.includes('incomplete test patch')) throw new Error('wrong build branch extracted');
async function run(selected) {{
  const logs=[]; let compileCalls=0, buildCalls=0;
  let N='', a=[{{path:'game/tl.rpy',content:'translated'}}], oe=false, r=false, o='', s='', c=false, l=false;
  let n='source.apk', m='output', y='zh', g='en', f='', i='source.apk';
  const window=globalThis;
  window.__slgIncompleteTestPatchSelected=selected;
  window.__slgBuildCoverage={{missingCount:1,rejectedCount:selected?0:1}};
  window.__slgRefreshTranslationCoverage=()=>{{}};
  const O=(message)=>logs.push(String(message));
  const ue=()=>{{}};
  const Me=value=>String(value||'translated.apk');
  const is=value=>String(value||'');
  const ce=()=>{{}};
  const fe=()=>{{}};
  const E={{
    compileTranslationsIntoApk: async()=>{{compileCalls++;return {{compiled:1}}}},
    buildPatchedApk: async()=>{{buildCalls++;return {{uri:'file:///patched.apk',path:'patched.apk',signed:true,signatureVerified:true,fileCount:1,replacedCount:1}}}}
  }};
  const runBranch=new Function('N','a','oe','r','o','s','c','l','n','m','y','g','f','i','O','ue','Me','is','ce','fe','E','window',`return (async()=>{{${{branch}}}})()`);
  let branchResult;
  try {{ branchResult=await runBranch(N,a,oe,r,o,s,c,l,n,m,y,g,f,i,O,ue,Me,is,ce,fe,E,window); }} catch (error) {{ logs.push('ERROR:'+error.message); }}
  return {{selected,compileCalls,buildCalls,logs,branchResult}};
}}
Promise.all([run(false),run(true)]).then(value=>process.stdout.write(JSON.stringify(value)));
"""
            result = json.loads(run_node(script))
        blocked, incomplete = result
        self.assertEqual(blocked["compileCalls"], 0)
        self.assertEqual(blocked["buildCalls"], 0)
        self.assertTrue(any("coverage incomplete" in message for message in blocked["logs"]))
        self.assertEqual(incomplete["compileCalls"], 1)
        self.assertEqual(incomplete["buildCalls"], 1)
        self.assertTrue(any("incomplete test patch" in message for message in incomplete["logs"]))

    def test_task10_generated_ui_export_sanitizes_values_and_secrets(self):
        """Execute the generated report and its real export button handler."""
        if not (BASE_JS.exists() and BASE_CSS.exists()):
            self.skipTest("canonical workshop assets not present")
        patcher = load_patch_workshop_ui()
        patched, _ = patcher.patch_assets(BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8"))
        with tempfile.TemporaryDirectory(prefix="coverage-export-") as temporary:
            js_path = Path(temporary) / "patched.js"
            js_path.write_text(patched, encoding="utf-8")
            script = f"""
const fs = require('fs');
const js = fs.readFileSync({json.dumps(str(js_path))}, 'utf-8');
const nodes=new Map(), buttons=[];
const host={{append(){{}},replaceChildren(){{}}}}; nodes.set('root',host);
function element(tag){{return {{tagName:tag.toUpperCase(),id:'',className:'',style:{{}},hidden:false,children:[],append(...items){{this.children.push(...items)}},replaceChildren(...items){{this.children=items}},click(){{if(this.onclick)this.onclick()}},set textContent(value){{this._text=String(value)}},get textContent(){{return this._text||''}}}}}}
globalThis.document={{querySelector:()=>host,getElementById:id=>nodes.get(id)||null,createElement:tag=>{{const item=element(tag);if(tag==='button')buttons.push(item);const originalId=Object.getOwnPropertyDescriptor(item,'id');Object.defineProperty(item,'id',{{get(){{return item._id||''}},set(value){{item._id=String(value);nodes.set(item._id,item)}}}});return item}}}};
globalThis.window=globalThis;
let exported=''; globalThis.Blob=class{{constructor(parts){{exported=parts.join('')}}}};
globalThis.URL={{createObjectURL:()=> 'blob:coverage',revokeObjectURL:()=>{{}}}};
const marker=js.indexOf('function asMap(value)');
const start=js.lastIndexOf('(function(){{',marker);
const end=js.indexOf('}})()',start)+4;
if(start<0||end<=start)throw new Error('coverage report IIFE missing');
eval(js.slice(start,end));
const records=[{{text:'Hello',sourcePath:'game/a.rpyc',translation:'你好',apiKey:'API-SECRET',secret:'PRIVATE',token:'TOKEN'}}];
globalThis.__slgCoverageRecords=records;
const report=globalThis.__slgBuildTranslationCoverageReport(records,new Map([['Hello','你好']]),new Set(),new Map(),[],new Map());
const button=buttons.find(item=>item.textContent==='导出覆盖率 JSON');
if(!button||typeof button.onclick!=='function')throw new Error('real coverage export handler missing');
button.onclick();
process.stdout.write(JSON.stringify({{report,exported:JSON.parse(exported)}}));
"""
            result = json.loads(run_node(script))
        exported = json.dumps(result["exported"], ensure_ascii=False)
        for value in ("你好", "您好", "API-SECRET", "PRIVATE", "TOKEN"):
            self.assertNotIn(value, exported)
        self.assertEqual(result["exported"]["uniqueSourceCount"], 1)
        self.assertIn("game/a.rpyc", exported)

    def test_task10_generated_ui_reset_clears_every_coverage_state_container(self):
        """Call the generated reset entry and inspect every mutable state holder."""
        if not (BASE_JS.exists() and BASE_CSS.exists()):
            self.skipTest("canonical workshop assets not present")
        patcher = load_patch_workshop_ui()
        patched, _ = patcher.patch_assets(BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8"))
        with tempfile.TemporaryDirectory(prefix="coverage-reset-") as temporary:
            js_path = Path(temporary) / "patched.js"
            js_path.write_text(patched, encoding="utf-8")
            script = f"""
const fs=require('fs'); const js=fs.readFileSync({json.dumps(str(js_path))},'utf-8');
const marker=js.indexOf('function asMap(value)'); const start=js.lastIndexOf('(function(){{',marker);
const firstEnd=js.indexOf('}})()',start)+4; const secondStart=js.indexOf('\\n(function(){{',firstEnd)+1;
const secondEnd=js.indexOf('}})()',secondStart)+4; const thirdStart=js.indexOf('\\n(function(){{',secondEnd)+1;
const thirdEnd=js.indexOf('}})()',thirdStart)+4; if(start<0||thirdEnd<=thirdStart)throw new Error('coverage reset IIFEs missing');
globalThis.window=globalThis; eval(js.slice(start,firstEnd)); eval(js.slice(secondStart,secondEnd)); eval(js.slice(thirdStart,thirdEnd));
globalThis.__slgCoverageRecords=[{{text:'stale',sourcePath:'game/a.rpyc'}}];
globalThis.__slgCoverageUncertain=['stale']; globalThis.__slgCoverageClassifications={{stale:'uncertain'}};
globalThis.__slgValidatorApprovedTranslations=new Map([['stale','旧译文']]);
globalThis.__slgRejectedTranslations=new Set(['stale']);
globalThis.__slgTranslationCollisionCandidates=new Map([['stale',['a','b']]]);
globalThis.__slgTranslationCollisionEntries=[{{old:'stale'}}];
globalThis.__slgIncompleteTestPatchSelected=true;
globalThis.__slgResetTranslationCoverage();
process.stdout.write(JSON.stringify({{records:globalThis.__slgCoverageRecords,uncertain:globalThis.__slgCoverageUncertain,classifications:globalThis.__slgCoverageClassifications,approved:Array.from(globalThis.__slgValidatorApprovedTranslations),rejected:Array.from(globalThis.__slgRejectedTranslations),candidates:Array.from(globalThis.__slgTranslationCollisionCandidates),entries:globalThis.__slgTranslationCollisionEntries,incomplete:globalThis.__slgIncompleteTestPatchSelected}}));
"""
            result = json.loads(run_node(script))
        self.assertEqual(result["records"], [])
        self.assertEqual(result["uncertain"], [])
        self.assertEqual(result["classifications"], {})
        self.assertEqual(result["approved"], [])
        self.assertEqual(result["rejected"], [])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["entries"], [])
        self.assertFalse(result["incomplete"])

    def test_task10_incremental_cache_hit_cannot_bypass_generated_coverage_gate(self):
        """Compose generated incremental selection, coverage, and build gate."""
        if not (BASE_JS.exists() and BASE_CSS.exists()):
            self.skipTest("canonical workshop assets not present")
        patcher = load_patch_workshop_ui()
        patched, _ = patcher.patch_assets(BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8"))
        with tempfile.TemporaryDirectory(prefix="coverage-cache-gate-") as temporary:
            js_path = Path(temporary) / "patched.js"
            js_path.write_text(patched, encoding="utf-8")
            script = f"""
async function main() {{
const fs=require('fs'); const js=fs.readFileSync({json.dumps(str(js_path))},'utf-8');
const marker=js.indexOf('function asMap(value)'); const start=js.lastIndexOf('(function(){{',marker);
const firstEnd=js.indexOf('}})()',start)+4; const secondStart=js.indexOf('\\n(function(){{',firstEnd)+1;
const secondEnd=js.indexOf('}})()',secondStart)+4; const thirdStart=js.indexOf('\\n(function(){{',secondEnd)+1;
const thirdEnd=js.indexOf('}})()',thirdStart)+4; if(start<0||thirdEnd<=thirdStart)throw new Error('coverage IIFEs missing');
globalThis.window=globalThis; eval(js.slice(start,firstEnd)); eval(js.slice(secondStart,secondEnd)); eval(js.slice(thirdStart,thirdEnd));
const diff=globalThis.__slgTranslationCoverageIncrementalDiff(['Hello','Missing','New'],new Map([['Hello','你好']]),['Rejected'],[]);
globalThis.__slgCoverageRecords=[{{text:'Hello',sourcePath:'game/a.rpyc'}},{{text:'Missing',sourcePath:'game/b.rpyc'}},{{text:'Rejected',sourcePath:'game/b.rpyc'}}];
globalThis.__slgValidatorApprovedTranslations=new Map([['Hello','你好']]);
globalThis.__slgRejectedTranslations=new Set(['Rejected']);
globalThis.__slgRefreshTranslationCoverage();
const coverage=globalThis.__slgBuildCoverage;
let compileCalls=0,buildCalls=0,logs=[]; let N='',a=[{{path:'game/tl.rpy',content:'translated'}}],oe=false,r=false,o='',s='',c=false,l=false,n='source.apk',m='output',y='zh',g='en',f='',i='source.apk';
window.__slgIncompleteTestPatchSelected=false; const O=message=>logs.push(String(message)); const ue=()=>{{}}; const Me=value=>String(value||'translated.apk'); const is=value=>String(value||'');
const E={{compileTranslationsIntoApk:async()=>{{compileCalls++;return {{compiled:1}}}},buildPatchedApk:async()=>{{buildCalls++;return {{uri:'file:///patched.apk',path:'patched.apk',signed:true,signatureVerified:true}}}}}};
const marker2='if(!N&&(a.length>0||oe)){{globalThis.__slgRefreshTranslationCoverage?.()'; const branchStart=js.indexOf(marker2); const branchEnd=js.indexOf('}},we=async',branchStart); if(branchStart<0||branchEnd<0)throw new Error('generated gate missing');
const branch=js.slice(branchStart,branchEnd);
const ce=()=>{{}}; const fe=()=>{{}};
const runBranch=new Function('N','a','oe','r','o','s','c','l','n','m','y','g','f','i','O','ue','Me','is','ce','fe','E','window',`return (async()=>{{${{branch}}}})()`);
await runBranch(N,a,oe,r,o,s,c,l,n,m,y,g,f,i,O,ue,Me,is,ce,fe,E,window);
process.stdout.write(JSON.stringify({{diff,coverage,compileCalls,buildCalls,logs}}));
}}
main().catch(error=>{{process.stderr.write(error.stack||String(error));process.exit(1)}});
"""
            result = json.loads(run_node(script))
        self.assertEqual(result["diff"], ["Missing", "New", "Rejected"])
        self.assertEqual(result["coverage"]["missingCount"], 1)
        self.assertEqual(result["coverage"]["rejectedCount"], 1)
        self.assertEqual(result["compileCalls"], 0)
        self.assertEqual(result["buildCalls"], 0)
        self.assertTrue(any("coverage incomplete" in message for message in result["logs"]))

    def test_task10_scanner_keeps_exact_old_occurrences_for_coverage(self):
        source = (FAST_SCAN / "src/com/slgtranslator/app/FastApkScanner.java").read_text("utf-8")
        for token in (
            "renpyRecords", "TranslationCoverageReport", "exactOld", "occurrenceCount",
            "coverageReport", "validatorApprovedTranslations",
        ):
            self.assertIn(token, source)

    def test_task10_missing_fixture_never_becomes_fake_zero(self):
        source = Path(__file__).read_text("utf-8")
        self.assertIn('self.skipTest("audit APK/extracted texts not present")', source)
        self.assertNotIn('missing' + 'Count:0', source)

    def test_task16_matrix_and_release_checklist_cover_every_gate(self):
        """The release documents must keep the machine and device gates explicit."""
        self.assertTrue(COMPATIBILITY_MATRIX.exists(), "Task 16 compatibility matrix is missing")
        self.assertTrue(RELEASE_CHECKLIST.exists(), "Task 16 release checklist is missing")
        matrix = COMPATIBILITY_MATRIX.read_text("utf-8")
        checklist = RELEASE_CHECKLIST.read_text("utf-8")
        for token in (
            "6 / Python 2", "7 / Python 2", "8 / Python 3", "未知 / 不支持",
            "loose RPYC2", "RPA-1", "RPA-2", "RPA-3", "legacy zlib",
            "标准菜单", "自定义菜单", "无菜单", "菜单注入失败",
            "已有中文字体", "缺中文字体", "部分缺字", "单 APK", "base + split",
            "对话", "菜单", "角色名", "UI", "`{#}`", "插值", "printf", "重复语境",
            "supportLevel", "activationStrategy", "templatePath", "text counts",
            "missing", "font result", "build allowed", "install success",
            "startup translation observed", "not-run", "rejected",
        ):
            self.assertIn(token, matrix, "matrix is missing %s" % token)
        for token in (
            "python -m unittest discover -s . -p 'test_*.py' -v",
            "python build_workshop_apk.py", "RenpyPatchValidator", "single APK",
            "base + split", "扫描", "翻译", "lint", "compile", "sign", "install",
            "launch", "translated text", "old save", "rollback", "missing == 0",
            "rejected == 0", "字体终检", "语言激活", "EXTRACT_ONLY", "UNSUPPORTED",
            "not-run",
        ):
            self.assertIn(token, checklist, "release checklist is missing %s" % token)


    def test_audit_pins_the_verified_missing_set(self):
        """The patched APK must cover the full extracted corpus (missing == 0).

        Uses the rebuilt corpus dump (extractor now pulls source-call text and
        translation-bucket old keys) plus the latest patched APK when present.
        """
        import importlib.util
        import sys
        from pathlib import Path
        qa = Path(__file__).resolve().parent / "qa"
        apk = qa / "ewn-audit-patched2.apk"
        dump = qa / "extracted-texts-v2.txt"
        if not (apk.exists() and dump.exists()):
            self.skipTest("audit APK/extracted texts not present")
        spec = importlib.util.spec_from_file_location("audit_coverage", qa / "audit_coverage.py")
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        result = audit.audit(apk_path=apk, dump_path=dump)
        self.assertEqual(len(result["missing"]), 0)
        self.assertGreater(result["translated_keys"], 32000)


if __name__ == "__main__":
    unittest.main()
