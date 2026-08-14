import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_fast_scanner import third_party_classpath


ROOT = Path(__file__).parent
BASE_JS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
BASE_CSS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-C044IUg3.css"
FAST_SCAN = ROOT.parent / "native-fast-scan"
JAVA_HOME = ROOT.parent.parent / ".tools" / "jdk-17" / "jdk-17.0.19+10"
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"


def load_patch():
    spec = importlib.util.spec_from_file_location("patch_workshop_ui", ROOT / "patch_workshop_ui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_node(script: str, cwd: Path) -> str:
    result = subprocess.run(
        ["node", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise AssertionError("node failed: " + (result.stderr or "")[:2000])
    return result.stdout


def run_behavior_probe(js: str) -> dict:
    """提取补丁后 JS 的关键函数，在 Node 中执行并返回行为结果。"""
    with tempfile.TemporaryDirectory() as directory:
        js_path = Path(directory) / "patched.js"
        js_path.write_text(js, encoding="utf-8")
        js_literal = json.dumps(str(js_path))
        script = f"""
const fs = require('fs');
const js = fs.readFileSync({js_literal}, 'utf-8');
const out = {{}};

// Le: Ren'Py 源格式说话人提取
(function() {{
  const start = js.indexOf('function Le(');
  const end = js.indexOf('function Re(', start);
  const Le = new Function('He', js.slice(start, end) + '\\nreturn Le;')(() => true);
  out.le = Le('maria "Hello, world."\\n"Plain line"\\n', '');
}})();

// 翻译引擎区域：No / Ro / Go / Vo
const regionStart = js.indexOf('var ko=');
const regionEnd = js.indexOf('function Ko(e,t,n)');
const region = js.slice(regionStart, regionEnd) + '\\nreturn {{No,Po,Fo,Io,Ro,Bo,Vo,Ho,Wo,Go}};';
const api = new Function(region)();

out.no = api.No([
  {{ keyPath: 'a', text: 'Yes', speaker: 'maria' }},
  {{ keyPath: 'b', text: 'Yes', speaker: 'hero' }},
  {{ keyPath: 'c', text: 'No', speaker: 'hero' }},
]);
out.noNoSpeaker = api.No([{{ keyPath: 'x', text: 'Plain' }}]);
out.ro = api.Ro({{ text: 'Hi {{name}}', speaker: 'maria' }});
out.roNoSpeaker = api.Ro({{ text: 'Hi {{name}}' }});
out.goEnZh = api.Go('en', 'zh', [], true);
out.goJaEn = api.Go('ja', 'en', [], true);
out.goReasoner = api.Go('en', 'zh', [], false);

async function runVo(items) {{
  let captured = null;
  const client = {{
    chat: {{ completions: {{ create: async (req) => {{
      captured = req;
      const content = req.messages[1].content;
      const texts = JSON.parse(content.slice(content.lastIndexOf('[')));
      return {{ choices: [{{ message: {{ content: JSON.stringify({{ translations: texts.map(t => '译:' + t) }}) }} }}] }};
    }} }} }},
  }};
  const result = await api.Vo(client, 'deepseek-v4-flash', items, 'en', 'zh', [], true);
  return {{ user: captured.messages[1].content, result: Array.from(result.entries()) }};
}}

(async () => {{
  // 真实格式：文件路径::序号
  out.voConsecutive = await runVo([
    {{ keyPath: 'assets/x-game/x-ch1ep1.rpyc::rpyc_string_0', text: 'Hi', speaker: 'maria', protectedText: api.Fo('Hi') }},
    {{ keyPath: 'assets/x-game/x-ch1ep1.rpyc::rpyc_string_1', text: 'What?', protectedText: api.Fo('What?') }},
  ]);
  // 跳号：缓存/本地规则剔除后序号不连续
  out.voGapped = await runVo([
    {{ keyPath: 'assets/x-game/x-ch1ep1.rpyc::rpyc_string_0', text: 'A', protectedText: api.Fo('A') }},
    {{ keyPath: 'assets/x-game/x-ch1ep1.rpyc::rpyc_string_2', text: 'B', protectedText: api.Fo('B') }},
    {{ keyPath: 'assets/x-game/x-ch1ep1.rpyc::rpyc_string_4', text: 'C', protectedText: api.Fo('C') }},
  ]);
  // 退化：无文件前缀（旧格式/JSON key），不应有 Source file 或场景提示
  out.voNoPrefix = await runVo([
    {{ keyPath: 'rpyc_string_0', text: 'A', protectedText: api.Fo('A') }},
    {{ keyPath: 'rpyc_string_1', text: 'B', protectedText: api.Fo('B') }},
  ]);
  // 单行：只有 Source file，不应有 lines 场景提示
  out.voSingleLine = await runVo([
    {{ keyPath: 'assets/x-game/x-ch1ep1.rpyc::rpyc_string_0', text: 'Alone', protectedText: api.Fo('Alone') }},
  ]);
  // 修复点：ke 调用带文件名前缀 + 缓存版本
  out.keCallPatched = js.includes('l=ke(i,s,o.name+`::`,g)');
  out.cacheNamespace = js.includes('var _o=`slg-translator-cache:`');
  process.stdout.write(JSON.stringify(out));
}})();
"""
        return json.loads(run_node(script, ROOT))


class TranslationQualityPatchTest(unittest.TestCase):
    """验证视觉小说 EN→ZH 质量补丁：说话人、prompt、上下文注入与修复点。"""

    def setUp(self):
        self.module = load_patch()
        self.js, _ = self.module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

    def test_v4_pro_model_is_available_in_list(self):
        self.assertIn("deepseek-v4-pro", self.js)
        self.assertIn(
            "supportsJsonMode:!1",
            self.js[self.js.index("deepseek-v4-pro") :],
        )

    def test_keypath_prefix_and_cache_namespace_compatibility(self):
        # 修复 P0-1：提取时把文件路径写入 keyPath（真实格式 file::seq）
        self.assertEqual(self.js.count("l=ke(i,s,o.name+`::`,g)"), 1)
        # 修复 P0-2：缓存键加 v2 版本，旧缓存自动失效
        self.assertEqual(self.js.count("var _o=`slg-translator-cache:`,vo={}"), 1)
        self.assertNotIn("slg-translator-cache:v2:", self.js)

    def test_task8_marker_cache_and_compile_keep_exact_keys(self):
        start = self.js.index("function cacheScopeIdentity(")
        end = self.js.index("function Do()", start)
        cache_runtime = self.js[start:end]
        harness = f"""
const runtime = {json.dumps(cache_runtime)};
const cacheApi = new Function(
  "let _o=`slg-translator-cache:`;"+
  "let vo={{}},cacheIndex={{}},_dirty={{}},yo=false,bo=false;"+
  "function U(value) {{ let hash=2166136261; for (let i=0;i<value.length;i++) {{ hash^=value.charCodeAt(i); hash=Math.imul(hash,16777619); }} return (hash>>>0).toString(36); }}"+
  runtime+
  "return {{cacheV2Key,To,Eo,vo}};"
)();
const scope = `en|zh|model|0`;
const slot = `Save{{#slot}}`;
const menu = `Save{{#menu}}`;
const slotKey = cacheApi.cacheV2Key(scope, slot);
const menuKey = cacheApi.cacheV2Key(scope, menu);
if (slotKey === menuKey) throw new Error(`marker cache keys collided`);
cacheApi.Eo(scope, slot, `slot translation`);
cacheApi.Eo(scope, menu, `menu translation`);
if (cacheApi.To(scope, slot) !== `slot translation`) throw new Error(`slot lookup crossed`);
if (cacheApi.To(scope, menu) !== `menu translation`) throw new Error(`menu lookup crossed`);
if (cacheApi.vo[slotKey].sourceText !== slot || cacheApi.vo[menuKey].sourceText !== menu) throw new Error(`exact old marker was not retained`);
process.stdout.write(JSON.stringify({{slotKey,menuKey,slotSource:cacheApi.vo[slotKey].sourceText,menuSource:cacheApi.vo[menuKey].sourceText}}));
"""
        result = json.loads(run_node(harness, ROOT))
        self.assertNotEqual(result["slotKey"], result["menuKey"])
        self.assertEqual(result["slotSource"], "Save{#slot}")
        self.assertEqual(result["menuSource"], "Save{#menu}")

    def test_behavior_speaker_dedupe_and_conditional_fields(self):
        out = run_behavior_probe(self.js)
        le_items = {item["text"]: item for item in out["le"]}
        self.assertEqual(le_items["Hello, world."]["speaker"], "maria")
        self.assertNotIn("speaker", le_items["Plain line"])

        # No：相同文本去重保留第一个说话人；无说话人时不产生 speaker 字段
        self.assertEqual(out["no"][0]["speaker"], "maria")
        self.assertIn("b", out["no"][0]["duplicateKeys"])
        self.assertEqual(out["no"][1]["speaker"], "hero")
        self.assertNotIn("speaker", out["noNoSpeaker"][0])

        # Ro：占位符保护后 speaker 保留；无 speaker 时不产生字段
        self.assertEqual(out["ro"]["speaker"], "maria")
        self.assertEqual(out["ro"]["protectedText"]["text"], "Hi __PH0__")
        self.assertNotIn("speaker", out["roNoSpeaker"])

    def test_behavior_prompt_rewrite(self):
        out = run_behavior_probe(self.js)
        self.assertIn("翻译腔", out["goEnZh"])
        self.assertIn("VISUAL NOVEL TRANSLATION HABITS", out["goEnZh"])
        self.assertIn("呢/吧/啊/嘛/哦/呀", out["goEnZh"])
        self.assertIn("Hmph→哼", out["goEnZh"])
        self.assertIn("never three dots", out["goEnZh"])
        self.assertIn("Repetition is meaningful", out["goEnZh"])
        self.assertIn("REFERENCE EXAMPLES", out["goEnZh"])
        self.assertNotIn("REFERENCE EXAMPLES", out["goJaEn"])
        self.assertIn("Think carefully", out["goReasoner"])

    def test_behavior_vo_context_injection(self):
        out = run_behavior_probe(self.js)

        # 真实格式 + 连续序号 → Source file + consecutive 强提示
        self.assertIn("Source file: x-ch1ep1.rpyc", out["voConsecutive"]["user"])
        self.assertIn(
            "These are consecutive lines from the same scene",
            out["voConsecutive"]["user"],
        )
        self.assertIn("[0] → maria", out["voConsecutive"]["user"])

        # 跳号 → 弱提示（同文件），不误导为连续
        self.assertIn("Source file: x-ch1ep1.rpyc", out["voGapped"]["user"])
        self.assertIn("These lines belong to the same file", out["voGapped"]["user"])
        self.assertNotIn("consecutive", out["voGapped"]["user"])

        # 无文件前缀 → 完全无上下文提示，退化为原行为
        self.assertNotIn("Source file:", out["voNoPrefix"]["user"])
        self.assertNotIn("These lines", out["voNoPrefix"]["user"])
        self.assertNotIn("consecutive", out["voNoPrefix"]["user"])

        # 单行 → 只有 Source file，不出现 lines/consecutive 场景提示
        self.assertIn("Source file: x-ch1ep1.rpyc", out["voSingleLine"]["user"])
        self.assertNotIn("These lines", out["voSingleLine"]["user"])
        self.assertNotIn("consecutive", out["voSingleLine"]["user"])

        # 翻译结果正常返回
        self.assertEqual(out["voConsecutive"]["result"][0][1], "译:Hi")


    def test_task8_java_corpus_keeps_occurrences_and_only_marks_context_collisions(self):
        harness = r'''
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.RenpyTranslationCorpus;
import java.util.*;
public final class Task8CorpusHarness {
  public static void main(String[] args) {
    RenpyTextRecord same1 = new RenpyTextRecord("OK{#menu}", RenpyTextRecord.Kind.MENU, "", "", "game/a.rpyc", 1, 1, true);
    RenpyTextRecord same2 = new RenpyTextRecord("OK{#menu}", RenpyTextRecord.Kind.MENU, "", "", "game/a.rpyc", 2, 2, true);
    RenpyTextRecord c1 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "alice", "dialog-a", "game/a.rpyc", 3, 1, true);
    RenpyTextRecord c2 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "bob", "dialog-b", "game/b.rpyc", 4, 1, true);
    RenpyTextRecord c3 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "carol", "dialog-c", "game/c.rpyc", 5, 1, true);
    RenpyTextRecord c4 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "dave", "dialog-d", "game/d.rpyc", 6, 1, true);
    RenpyTextRecord c5 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "erin", "dialog-e", "game/e.rpyc", 7, 1, true);
    RenpyTranslationCorpus.Corpus corpus = RenpyTranslationCorpus.build(Arrays.asList(same1, same2, c1, c2, c3, c4, c5));
    RenpyTranslationCorpus.Entry repeated = corpus.get("OK{#menu}");
    RenpyTranslationCorpus.Entry collision = corpus.get("Fine.");
    if (repeated == null || repeated.occurrences.size() != 2 || repeated.contextualCollision) throw new AssertionError("repeat");
    if (collision == null || collision.occurrences.size() != 5 || !collision.contextualCollision) throw new AssertionError("collision");
    String[][] expectedRepeated = new String[][] {
        {"game/a.rpyc", "1", "MENU", "", ""},
        {"game/a.rpyc", "2", "MENU", "", ""}
    };
    for (int i = 0; i < expectedRepeated.length; i++) {
      RenpyTextRecord actual = repeated.occurrences.get(i);
      String[] expected = expectedRepeated[i];
      if (!expected[0].equals(actual.sourcePath) || actual.sourceLine != Integer.parseInt(expected[1])
          || actual.kind != RenpyTextRecord.Kind.valueOf(expected[2]) || !expected[3].equals(actual.speaker)
          || !expected[4].equals(actual.identifier)) throw new AssertionError("repeated occurrence " + i);
    }
    String[][] expectedCollision = new String[][] {
        {"game/a.rpyc", "3", "DIALOGUE", "alice", "dialog-a"},
        {"game/b.rpyc", "4", "DIALOGUE", "bob", "dialog-b"},
        {"game/c.rpyc", "5", "DIALOGUE", "carol", "dialog-c"},
        {"game/d.rpyc", "6", "DIALOGUE", "dave", "dialog-d"},
        {"game/e.rpyc", "7", "DIALOGUE", "erin", "dialog-e"}
    };
    for (int i = 0; i < expectedCollision.length; i++) {
      RenpyTextRecord actual = collision.occurrences.get(i);
      String[] expected = expectedCollision[i];
      if (!expected[0].equals(actual.sourcePath) || actual.sourceLine != Integer.parseInt(expected[1])
          || actual.kind != RenpyTextRecord.Kind.valueOf(expected[2]) || !expected[3].equals(actual.speaker)
          || !expected[4].equals(actual.identifier)) throw new AssertionError("collision occurrence " + i);
    }
    String prompt = RenpyTranslationCorpus.contextPrompt(collision);
    if (!prompt.contains("contexts=5")) throw new AssertionError("prompt count");
    for (int i = 0; i < 3; i++) {
      String[] expected = expectedCollision[i];
      String expectedLine = "- " + expected[0] + ":" + expected[1]
          + " kind=" + expected[2] + " speaker=" + expected[3]
          + " identifier=" + expected[4] + "\n";
      if (!prompt.contains(expectedLine)) throw new AssertionError("prompt context " + i);
    }
    if (prompt.split("- game/").length - 1 != 3 || prompt.contains("game/d.rpyc")
        || prompt.contains("game/e.rpyc")) throw new AssertionError("prompt context bound");
    if (!prompt.equals(RenpyTranslationCorpus.contextPrompt(collision))) throw new AssertionError("prompt nondeterministic");
    System.out.print("ok");
  }
}
'''
        with tempfile.TemporaryDirectory(prefix="task8-corpus-") as directory:
            out = Path(directory) / "classes"
            out.mkdir()
            source = Path(directory) / "Task8CorpusHarness.java"
            source.write_text(harness, encoding="utf-8")
            subprocess.run([str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8", "-d", str(out),
                            str(FAST_SCAN / "src/com/slgtranslator/app/RenpyTextRecord.java"),
                            str(FAST_SCAN / "src/com/slgtranslator/app/RenpyTranslationCorpus.java"), str(source)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = subprocess.run([str(JAVA), "-cp", str(out), "Task8CorpusHarness"], check=False,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ok")

    def test_task8_ui_reports_collisions_and_exports_sanitized_json(self):
        self.assertIn("contextualCollision", self.js)
        self.assertIn("occurrenceCount", self.js)
        self.assertIn("duplicateCount", self.js)
        self.assertIn("translationCollisionReport", self.js)
        self.assertIn("JSON.stringify", self.js)
        self.assertIn("slg-translation-collision-report", self.js)
        self.assertIn("导出碰撞 JSON", self.js)

    def test_task8_ui_report_renders_counts_and_sanitizes_export(self):
        with tempfile.TemporaryDirectory(prefix="task8-ui-report-") as directory:
            js_path = Path(directory) / "patched.js"
            js_path.write_text(self.js, encoding="utf-8")
            js_literal = json.dumps(str(js_path))
            script = f"""
const fs = require('fs');
const js = fs.readFileSync({js_literal}, 'utf-8');
const start = js.indexOf('(function(){{/* up to 3 representative contexts */const root=typeof window');
const end = js.indexOf('}})()', start) + 4;
if (start < 0 || end <= start) throw new Error('collision report IIFE missing');
const nodes = {{}};
function node(tag) {{ return {{tag, id:'', children:[], hidden:false, style:{{}}, textContent:'',
  append(...items) {{ for (const item of items) {{ this.children.push(item); if (item && item.id) nodes[item.id] = item; }} }},
  replaceChildren(...items) {{ this.children=[]; this.append(...items); }},
  setAttribute() {{}},
  click() {{}}
}}; }}
const host = node('main');
globalThis.window = globalThis;
globalThis.document = {{
  querySelector: () => host,
  getElementById: id => nodes[id] || null,
  createElement: tag => node(tag),
}};
eval(js.slice(start, end));
const report = globalThis.__slgTranslationCollisionReport([
  {{exactOld:'OK{{#menu}}', sourcePath:'game/a.rpyc', kind:'MENU', speaker:''}},
  {{exactOld:'OK{{#menu}}', sourcePath:'game/a.rpyc', kind:'MENU', speaker:''}},
  {{exactOld:'Fine.', sourcePath:'game/a.rpyc', kind:'DIALOGUE', speaker:'alice', apiKey:'secret'}},
  {{exactOld:'Fine.', sourcePath:'game/b.rpyc', kind:'DIALOGUE', speaker:'bob'}},
]);
const panel = nodes['slg-translation-collision-report'];
if (!panel) throw new Error('collision report panel not rendered');
process.stdout.write(JSON.stringify({{report, summary:panel.children[1].textContent, json:globalThis.__slgTranslationCollisionReportJson}}));
"""
            result = json.loads(run_node(script, ROOT))
        self.assertEqual(result["report"]["uniqueOldCount"], 2)
        self.assertEqual(result["report"]["occurrenceCount"], 4)
        self.assertEqual(result["report"]["duplicateCount"], 2)
        self.assertEqual(result["report"]["collisionCount"], 1)
        self.assertIn("唯一原文 2", result["summary"])
        self.assertIn("总出现 4", result["summary"])
        self.assertNotIn("secret", result["json"])

    def test_task8_compile_gate_rejects_conflicting_pairs_before_writing(self):
        harness = r'''
package com.slgtranslator.app;
import java.util.*;
public final class Task8CompileGateHarness {
  public static void main(String[] args) throws Exception {
    List<String[]> conflict = Arrays.asList(
        new String[] {"Fine.", "好。"}, new String[] {"Fine.", "行。"});
    String direct = LocalTranslationSupport.translationCollisionConflict(conflict);
    if (direct == null || !direct.contains("translation_collision_conflict")) throw new AssertionError("support gate");
    try {
      TranslationCompiler.compileTranslationArtifact("selectable", conflict, null);
      throw new AssertionError("compiler accepted collision");
    } catch (Exception expected) {
      if (!String.valueOf(expected.getMessage()).contains("translation_collision_conflict")) throw expected;
    }
    List<String[]> same = Arrays.asList(
        new String[] {"Fine.", "好。"}, new String[] {"Fine.", "好。"});
    if (LocalTranslationSupport.translationCollisionConflict(same) != null) throw new AssertionError("same translation rejected");
    List<String[]> markerPairs = Arrays.asList(
        new String[] {"Save{#slot}", "Translated slot{#slot}"},
        new String[] {"Save{#menu}", "Translated menu{#menu}"},
        new String[] {"Save{#slot}", "Translated slot{#slot}"});
    TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
    meta.version = 7;
    meta.key = "unlocked";
    TranslationCompiler.TranslationArtifact artifact =
        TranslationCompiler.compileTranslationArtifact("always_on", markerPairs, meta);
    if (artifact == null || artifact.rpyc == null || artifact.rpyc.length == 0) throw new AssertionError("artifact missing");
    RenpyPatchValidator.Result artifactValidation = RenpyPatchValidator.validateCompiledRpyc(
        artifact.rpyc, 7, "unlocked", null, 3);
    if (!artifactValidation.valid) throw new AssertionError("artifact validation: " + artifactValidation.code);
    List<String> emitted = RpycTextExtractor.extractTexts(artifact.rpyc);
    if (!emitted.contains("Save{#slot}") || !emitted.contains("Save{#menu}")) throw new AssertionError("marker old text missing from artifact");
  }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="task8-compile-gate-") as directory:
            directory_path = Path(directory)
            source = directory_path / "Task8CompileGateHarness.java"
            classes = directory_path / "classes"
            source.write_text(harness, encoding="utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(source)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.Task8CompileGateHarness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_task8_prompt_limits_contexts_and_compile_rejects_conflicting_translations(self):
        self.assertIn("translation_collision_conflict", self.js)
        self.assertIn("conflicting translations", self.js)

    def test_task9_compile_gate_rejects_invalid_translation_before_rpyc(self):
        harness = r'''
package com.slgtranslator.app;
import java.util.*;
public final class Task9LintGateHarness {
  public static void main(String[] args) throws Exception {
    RenpyTextValidator.ValidationResult bad = RenpyTextValidator.validate(
        "{b}Hello{/b} [name] %s", "{b}Bonjour{/i} [other] %d");
    if (bad.valid || !bad.codes.contains("tag_misnested")
        || !bad.codes.contains("interpolation_changed")
        || !bad.codes.contains("printf_changed")) throw new AssertionError("lint diagnostics");
    List<String[]> pairs = new ArrayList<String[]>();
    pairs.add(new String[] {"{b}Hello{/b} [name] %s", "{b}Bonjour{/i} [other] %d"});
    try {
      TranslationCompiler.compileTranslationArtifact("selectable", pairs, new TranslationCompiler.TemplateMeta());
      throw new AssertionError("invalid translation reached RPYC writer");
    } catch (Exception expected) {
      String message = String.valueOf(expected.getMessage());
      if (!message.contains("tag_misnested") || !message.contains("old=")
          || !message.contains("new=") || !message.contains("source=")) throw expected;
    }
  }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="task9-lint-gate-") as directory:
            directory_path = Path(directory)
            source = directory_path / "Task9LintGateHarness.java"
            classes = directory_path / "classes"
            source.write_text(harness, encoding="utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(source)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.Task9LintGateHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_mlkit_echo_fallback_matrix(self):
        harness = r'''
package com.slgtranslator.app;

public final class MlkitEchoFallbackHarness {
  private static void eq(String expected, String actual, String label) {
    if (expected == null ? actual != null : !expected.equals(actual)) {
      throw new AssertionError(label + " expected=" + expected + " actual=" + actual);
    }
  }
  public static void main(String[] args) {
    eq("操！", MlKitTranslator.echoFallback("fuck！"), "fuck-bang");
    eq("操。", MlKitTranslator.echoFallback("fuck。"), "fuck-dot");
    eq("操", MlKitTranslator.echoFallback("fuck"), "fuck-bare");
    eq("{b}操！{/b}", MlKitTranslator.echoFallback("{b}fuck！{/b}"), "fuck-tag");
    eq("嗯哼。", MlKitTranslator.echoFallback("ehem。"), "ehem");
    eq("琪亚拉？", MlKitTranslator.echoFallback("chiara？"), "chiara");
    eq("吉利！", MlKitTranslator.echoFallback("gillie！"), "gillie");
    eq("呀！", MlKitTranslator.echoFallback("eep！"), "eep");
    eq("呃啊！", MlKitTranslator.echoFallback("aaaaaaagh！"), "aagh");
    eq("啊！", MlKitTranslator.echoFallback("aaaaaaah！"), "aah");
    eq("什——", MlKitTranslator.echoFallback("wha-"), "wha");
    eq("砰", MlKitTranslator.echoFallback("thwock"), "thwock");
    eq("{i}砰{/i}", MlKitTranslator.echoFallback("{i}thwock{/i}"), "thwock-i");
    eq("{i}塞玛·托米·阿尔·萨马塞拉姆？{/i}",
        MlKitTranslator.echoFallback("{i}Sema Tomi Al Saamaselam？{/i}"), "sema");
    eq("{i}伊沙妮·阿格拉迪·阿尔·瓦希·萨马科{/i}",
        MlKitTranslator.echoFallback("{i}Ishani A\u2019Gradi Al Vashi Samako{/i}"), "ishani-curly");
    eq("{i}伊沙妮·阿格拉迪·阿尔·瓦希·萨马科{/i}",
        MlKitTranslator.echoFallback("{i}Ishani A\u02bcGradi Al Vashi Samako{/i}"), "ishani-02bc");
    eq("什……什么？", MlKitTranslator.echoFallback("w什么？"), "w-shenme");
    eq("嘿，艾什特尔。", MlKitTranslator.echoFallback("嘿，eshtel。"), "hey-eshtel");
    eq("好嘞。", MlKitTranslator.echoFallback("alrighty。"), "alrighty");
    eq("拜拜！", MlKitTranslator.echoFallback("byeeeeeee！"), "byeeee");
    eq("什么鬼？", MlKitTranslator.echoFallback("dafuq？"), "dafuq");
    eq("德鲁萨里。", MlKitTranslator.echoFallback("druthari。"), "druthari");
    eq("萨里亚？", MlKitTranslator.echoFallback("saarya？"), "saarya");
    eq("嗯！", MlKitTranslator.echoFallback("mmh！"), "mmh");
    eq("伊维·克莱门茨。", MlKitTranslator.echoFallback("Evie Clements."), "evie");
    eq("{b}——呢！{/b}", MlKitTranslator.echoFallback("{b}-ne！{/b}"), "ne-fragment");
    eq("——认真的！", MlKitTranslator.echoFallback("-serious！"), "serious-fragment");
    eq("（哔——）", MlKitTranslator.echoFallback("（beeeeeeeeeeeeeep）"), "beep");
    eq("（扑棱扑棱扑棱扑棱扑棱扑棱）", MlKitTranslator.echoFallback("（flapflapflapflapflapflap）"), "flap");
    eq("（嗡——）", MlKitTranslator.echoFallback("（whrrrrrrrrrrrrrrr）"), "whrr");
    eq("{b}他妈的！{/b}", MlKitTranslator.echoFallback("{b}fucking！{/b}"), "fucking");
    eq("{fi}所以你能不能就……{/fi}", MlKitTranslator.echoFallback("{fi}So can you just...{/fi}"), "so-can");
    eq("{fi}你知道的……{/fi}", MlKitTranslator.echoFallback("{fi}y'know...{/fi}"), "yknow");
    eq("{fi}也是最危险的{/fi}.", MlKitTranslator.echoFallback("{fi}are also the most dangerous{/fi}."), "most-dangerous");
    eq("{fi=[50]-[1.5]-[750]}闯入者{/fi}.", MlKitTranslator.echoFallback("{fi=[50]-[1.5]-[750]}Interloper{/fi}."), "interloper");
    eq("{i}[playername]——赛·哈拉内·德马。{/i}",
        MlKitTranslator.echoFallback("{i}[playername]-Sai Halane Dema。{/i}"), "playername-incantation");
    eq("{i}阿尔·米沙伊？{/i}", MlKitTranslator.echoFallback("{i}Al Mishai？{/i}"), "al-mishai");
    eq("{i}阿尔·萨马塞-拉姆？{/i}", MlKitTranslator.echoFallback("{i}Al saamase-lam？{/i}"), "saamase");
    eq("{i}阿鲁莱·纳·阿迈·阿尔·阿卢卡{/i}", MlKitTranslator.echoFallback("{i}Alule Na Amai Al Aluka{/i}"), "alule");
    eq("{i}埃萨·阿莱·塔亚·纳·韦莱，阿尔·维亚·莫拉赛{/i}",
        MlKitTranslator.echoFallback("{i}Etha Alai Thaya Na Vele，Al Veia Moratsai{/i}"), "etha");
    eq("{i}伊亚·瓦伊·贝莱伦德。{/i}", MlKitTranslator.echoFallback("{i}Ia Vai Belelende。{/i}"), "ia-vai");
    eq("{i}吉加·马迪·阿沙加里·阿尔·哈谢什。{/i}",
        MlKitTranslator.echoFallback("{i}Jiga Madi Ashagari Al Hashesh。{/i}"), "jiga");
    eq("{i}凯耶·阿瓦里·德马？{/i}", MlKitTranslator.echoFallback("{i}Kai'e A'Wari Dema？{/i}"), "kaie");
    eq("{i}查·吉加，罗加赛·阿尔·维亚希·阿莱·索利。{/i}",
        MlKitTranslator.echoFallback("{i}Cha Jiga，Rogasai Al Veiasshi Alai Soli。{/i}"), "cha-jiga");
    eq("{i}伊加——伊亚·德马！{/i}", MlKitTranslator.echoFallback("{i}Igaaaaaa ia dema！{/i}"), "igaaaaaa");
    eq("{i}伊沙尼？{/i}", MlKitTranslator.echoFallback("{i}ishani？{/i}"), "ishani-name");
    eq("{i}嘎？{/}", MlKitTranslator.echoFallback("{i}Bawk?{/}"), "bawk");
    eq("{i}琪亚拉开始唱歌。", MlKitTranslator.echoFallback("{i}Chiara begins to sing."), "chiara-sings-malformed");
    eq("{i}你到家之后……{i}", MlKitTranslator.echoFallback("{i}After you get home...{i}"), "after-home-malformed");
    eq("她差点{b}{i}杀掉{/b}{/i}的那个人？", MlKitTranslator.echoFallback("The person she tried to {b}{i}KILL{/b}{/i}?"), "kill-sentence");
    eq("你{b}{i}他妈{/b}{/i}的在这干什么？", MlKitTranslator.echoFallback("The fuck are {b}{i}YOU{/b}{/i} doing here?"), "fuck-sentence");
    eq("还记得这条裙子吗？", MlKitTranslator.echoFallback("Remember this dress?"), "remember-dress");
    eq("涩图？", MlKitTranslator.echoFallback("Titty Pics？"), "titty");
    eq("给我给我给我！", MlKitTranslator.echoFallback("Gimme Gimme Gimme！"), "gimme");
    eq("不不不不不。", MlKitTranslator.echoFallback("NOPE NOPE NOPE NOPE NOPE。"), "nope");
    eq("嘎嘎嘎！", MlKitTranslator.echoFallback("Bawk Bawk Bawk！"), "bawk-bawk");
    eq("哦——天哪！", MlKitTranslator.echoFallback("Ooohhhhhh myyyyyyyy！"), "oh-my");
    eq("喂？", MlKitTranslator.echoFallback("helloooo？"), "helloooo");
    eq("太棒了。", MlKitTranslator.echoFallback("greaaaaaat。"), "great");
    eq("有趣。", MlKitTranslator.echoFallback("iiiiinteresting。"), "interesting");
    eq("冷静。", MlKitTranslator.echoFallback("caaaaalm。"), "calm");
    eq("加奈子！", MlKitTranslator.echoFallback("kanakoooooooo！"), "kanako");
    eq("嘘！", MlKitTranslator.echoFallback("shh！"), "shh");
    eq("D.O.T.？", MlKitTranslator.echoFallback("d.o.t.？"), "dot");
    eq("哟，你个小捣蛋。", MlKitTranslator.echoFallback("Aye，Ya Cheeky Brat。"), "aye");
    eq("在干嘛呢？", MlKitTranslator.echoFallback("whatcha doin'？"), "whatcha");
    eq("妈的，[playername].", MlKitTranslator.echoFallback("goddammit， [playername]."), "goddammit");
    eq("哦[playername]!", MlKitTranslator.echoFallback("ohhh [playername]!"), "ohhh-playername");
    eq("鲁弗斯——[playername].", MlKitTranslator.echoFallback("rufus-[playername]."), "rufus");
    eq("{i}梅——梅莱·伊加！{/i}", MlKitTranslator.echoFallback("{i}M-Mele Iga！{/i}"), "m-mele");
    eq("{i}塞马萨·吉尔[playername].{/i}", MlKitTranslator.echoFallback("{i}Semasa Giel [playername].{/i}"), "semasa");
    eq("{i}罗加萨·马杰·塞拉金·纳·罗米亚·德马。{/i}",
        MlKitTranslator.echoFallback("{i}Rogasa Majie Therakiin Na Romiya Dema。{/i}"), "rogasa");
    eq("{i}萨姆3·萨姆4。{/i}", MlKitTranslator.echoFallback("{i}Sam 3，Sam 4。{/i}"), "sam34");
    eq("{i}南——南达拉！{/i}", MlKitTranslator.echoFallback("{i}n-nandara！{/i}"), "nandara");
    eq("Q", MlKitTranslator.echoFallback("q"), "q");
    eq("啊哈哈！", MlKitTranslator.echoFallback("ahahahahaha！"), "ahaha");
    eq("啊哈哈！", MlKitTranslator.echoFallback("ahahahahahahaaaaa！"), "ahaha-long");
    eq("哈哈哈！", MlKitTranslator.echoFallback("bahahahaha！"), "baha");
    eq("哈哈哈", MlKitTranslator.echoFallback("bahahahahahahahahahaaaaaaaaaaaaaaaaaaaaaahhhhhhhhhhhhhh"), "baha-long");
    eq("啊啊啊！", MlKitTranslator.echoFallback("aaaaaaaiiiiiiiiiiieeeeeee！"), "aie");
    eq("操——", MlKitTranslator.echoFallback("f-"), "f-dash");
    eq("嗯哼。", MlKitTranslator.echoFallback("mhm。"), "mhm");
    eq("哼。", MlKitTranslator.echoFallback("hmph。"), "hmph");
    if (MlKitTranslator.echoFallback("{fi}{bt=h10-p1.5-s1.0}{color=#d61ebe}come with me and share this with me?{/color}{/bt}{/fi}") != null)
        throw new AssertionError("real sentence must not fall back");
    if (MlKitTranslator.echoFallback("Hello world.") != null) throw new AssertionError("sentence must not fall back");
    if (MlKitTranslator.echoFallback("") != null) throw new AssertionError("empty must not fall back");
    if (MlKitTranslator.echoFallback(null) != null) throw new AssertionError("null must not fall back");
    eq("やめて", MlKitTranslator.echoFallback("やめて"), "kana pass-through");
    RenpyTextValidator.ValidationResult v = RenpyTextValidator.validate("fuck！", "操！");
    if (!v.valid) throw new AssertionError("fallback must pass lint: " + v.codes);
    v = RenpyTextValidator.validate("{i}thwock{/i}", "{i}砰{/i}");
    if (!v.valid) throw new AssertionError("tagged fallback must pass lint: " + v.codes);
    String swapOld = "{swap=False@Truth@0.5}{sc}False{/sc}{/swap}: She\u2019s always been {swap=your true love@a damn traitor@0.5}{sc}your true love{/sc}{/swap}.";
    String swapNew = "{swap=False@Truth@0.5}{sc}假象{/sc}{/swap}: 她一直把你当作 {swap=your true love@a damn traitor@0.5}{sc}你的真爱{/sc}{/swap}。";
    v = RenpyTextValidator.validate(swapOld, swapNew);
    if (!v.valid) throw new AssertionError("swap/sc tags must validate: " + v.codes);
    String altOld = "... I wonder if Aoibheann{alt}eeveen{/alt} would know anything about this?";
    String altNew = "……不知道 Aoibheann{alt}eeveen{/alt} 会不会知道这件事？";
    v = RenpyTextValidator.validate(altOld, altNew);
    if (!v.valid) throw new AssertionError("alt tags must validate: " + v.codes);
    String fiOld = "{fi}{bt=h10-p1.5-s1.0}{color=#d61ebe}come with me and share this with me?{/color}{/bt}{/fi}";
    String fiNew = "{fi}{bt=h10-p1.5-s1.0}{color=#d61ebe}跟我来，和我一起分享这个吗？{/color}{/bt}{/fi}";
    v = RenpyTextValidator.validate(fiOld, fiNew);
    if (!v.valid) throw new AssertionError("fi/bt custom tags must validate: " + v.codes);
    v = RenpyTextValidator.validate("{i}Chiara begins to sing.", "{i}琪亚拉开始唱歌。");
    if (!v.valid) throw new AssertionError("malformed-source reproduction must validate: " + v.codes);
    v = RenpyTextValidator.validate("{i}After you get home...{i}", "{i}你到家之后……{i}");
    if (!v.valid) throw new AssertionError("malformed-source reproduction must validate: " + v.codes);
    v = RenpyTextValidator.validate("Plain text.", "{b}broken");
    if (v.valid || !v.codes.contains("tag_unbalanced"))
        throw new AssertionError("newly unbalanced translation must still fail: " + v.codes);
    v = RenpyTextValidator.validate("{b}Hello{/b} [name] %s", "{b}Bonjour{/i} [other] %d");
    if (v.valid || !v.codes.contains("tag_misnested") || !v.codes.contains("tag_unbalanced"))
        throw new AssertionError("misnested translation must still fail: " + v.codes);
    v = RenpyTextValidator.validate("{b}{i}KILL{/b}{/i}", "{b}{i}杀{/b}{/i}");
    if (!v.valid) throw new AssertionError("misnested-source reproduction must validate: " + v.codes);
    System.out.println("mlkit-echo-fallback-ok");
  }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="mlkit-echo-fallback-") as directory:
            directory_path = Path(directory)
            source = directory_path / "MlkitEchoFallbackHarness.java"
            classes = directory_path / "classes"
            source.write_text(harness, encoding="utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(source)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes) + os.pathsep + third_party_classpath(),
                 "com.slgtranslator.app.MlkitEchoFallbackHarness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_task9_full_rejection_matrix_covers_model_and_compile_gates(self):
        harness = r'''
package com.slgtranslator.app;

import com.getcapacitor.JSObject;
import java.lang.reflect.Method;
import java.util.*;
import org.json.JSONArray;

public final class Task9FullMatrixHarness {
  private static final Method ACCEPT;
  static {
    try {
      ACCEPT = LocalLlmEngine.class.getDeclaredMethod(
          "acceptTranslation", LocalTranslationSupport.TextItem.class, String.class,
          JSObject.class, List.class, JSONArray.class, int[].class);
      ACCEPT.setAccessible(true);
    } catch (Exception error) {
      throw new RuntimeException(error);
    }
  }

  private static final class Case {
    final String name;
    final String oldText;
    final String newText;
    final String code;
    Case(String name, String oldText, String newText, String code) {
      this.name = name;
      this.oldText = oldText;
      this.newText = newText;
      this.code = code;
    }
  }

  public static void main(String[] args) throws Exception {
    TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
    assertValid("tag-valid", "{b}Hello{/b}", "{b}你好{/b}", meta);
    assertValid("expression-valid", "Value [score]", "数值 [score]", meta);
    assertValid("named-valid", "Hello %(name)s", "你好 %(name)s", meta);
    assertValid("printf-valid", "Score %s / %d / %1$s", "分数 %s / %d / %1$s", meta);

    List<Case> invalid = Arrays.asList(
        new Case("tag-missing", "{b}Hello{/b}", "Bonjour", "tag_unbalanced"),
        new Case("tag-extra", "{b}Hello{/b}", "{b}Bonjour{/b}{i}x{/i}", "tag_unbalanced"),
        new Case("tag-duplicate", "{b}Hello{/b}", "{b}{b}Bonjour{/b}{/b}", "tag_unbalanced"),
        new Case("tag-reordered", "{b}{i}Hello{/i}{/b}", "{i}{b}Bonjour{/b}{/i}", "tag_unbalanced"),
        new Case("tag-crossed", "{b}{i}Hello{/i}{/b}", "{b}{i}Bonjour{/b}{/i}", "tag_misnested"),
        new Case("expression-missing", "A [one] [two]", "甲 [one]", "interpolation_changed"),
        new Case("expression-extra", "A [one] [two]", "甲 [one] [two] [three]", "interpolation_changed"),
        new Case("expression-duplicate", "A [one] [two]", "甲 [one] [one]", "interpolation_changed"),
        new Case("expression-reordered", "A [one] [two]", "甲 [two] [one]", "interpolation_changed"),
        new Case("named-missing", "A %(name)s %(count)d", "甲 %(name)s", "printf_changed"),
        new Case("named-extra", "A %(name)s", "甲 %(name)s %(other)s", "printf_changed"),
        new Case("named-duplicate", "A %(name)s %(count)d", "甲 %(name)s %(name)s", "printf_changed"),
        new Case("named-reordered", "A %(name)s %(count)d", "甲 %(count)d %(name)s", "printf_changed"),
        new Case("printf-missing", "A %s %d %1$s", "甲 %s %d", "printf_changed"),
        new Case("printf-extra", "A %s %d %1$s", "甲 %s %d %1$s %i", "printf_changed"),
        new Case("printf-duplicate", "A %s %d %1$s", "甲 %s %d %s", "printf_changed"),
        new Case("printf-reordered", "A %s %d %1$s", "甲 %1$s %d %s", "printf_changed"),
        new Case("residual-sentinel", "Hello", "你好 __SLGPH0__", "unrestored_sentinel"));
    for (Case item : invalid) {
      assertInvalid(item, meta);
    }
  }

  private static void assertValid(String name, String oldText, String newText,
                                  TranslationCompiler.TemplateMeta meta) throws Exception {
    RenpyTextValidator.ValidationResult result =
        RenpyTextValidator.validate(oldText, newText);
    if (!result.valid) {
      throw new AssertionError(name + " validator rejected " + result.codes);
    }
    List<String> warnings = new ArrayList<String>();
    boolean accepted = (Boolean) ACCEPT.invoke(null,
        new LocalTranslationSupport.TextItem(name, oldText), newText, new JSObject(),
        warnings, new JSONArray(), new int[] {0});
    if (!accepted || !warnings.isEmpty()) {
      throw new AssertionError(name + " model acceptance failed: " + warnings);
    }
    List<String[]> pairs = new ArrayList<String[]>();
    pairs.add(new String[] {oldText, newText});
    TranslationCompiler.TranslationArtifact artifact =
        TranslationCompiler.compileTranslationArtifact("selectable", pairs, meta);
    if (artifact == null || artifact.rpyc == null || artifact.rpyc.length == 0) {
      throw new AssertionError(name + " did not produce RPYC");
    }
  }

  private static void assertInvalid(Case item,
                                    TranslationCompiler.TemplateMeta meta) throws Exception {
    RenpyTextValidator.ValidationResult result =
        RenpyTextValidator.validate(item.oldText, item.newText);
    if (result.valid || !result.codes.contains(item.code)) {
      throw new AssertionError(item.name + " validator result=" + result.codes);
    }
    List<String> warnings = new ArrayList<String>();
    boolean accepted = (Boolean) ACCEPT.invoke(null,
        new LocalTranslationSupport.TextItem(item.name, item.oldText), item.newText,
        new JSObject(), warnings, new JSONArray(), new int[] {0});
    if (accepted || warnings.isEmpty() || !warnings.toString().contains(item.code)) {
      throw new AssertionError(item.name + " model gate accepted or hid " + item.code
          + ": " + warnings);
    }
    List<String[]> pairs = new ArrayList<String[]>();
    pairs.add(new String[] {item.oldText, item.newText});
    try {
      TranslationCompiler.compileTranslationArtifact("selectable", pairs, meta);
      throw new AssertionError(item.name + " reached RPYC writer");
    } catch (Exception expected) {
      String message = String.valueOf(expected.getMessage());
      if (!message.contains(item.code) || !message.contains("old=")
          || !message.contains("new=") || !message.contains("source=")) {
        throw expected;
      }
    }
  }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="task9-full-matrix-") as directory:
            directory_path = Path(directory)
            source = directory_path / "Task9FullMatrixHarness.java"
            classes = directory_path / "classes"
            source.write_text(harness, encoding="utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(source)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes) + os.pathsep + third_party_classpath(),
                 "com.slgtranslator.app.Task9FullMatrixHarness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()

class CacheMemoryPatchTest(unittest.TestCase):
    """验证缓存内存修复：full 清空同步清 cacheIndex、缓存上限淘汰。"""

    def setUp(self):
        self.module = load_patch()
        self.js, _ = self.module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

    def test_full_clear_resets_cache_index(self):
        # full 清空必须同步清 cacheIndex，否则旧缓存引用残留、清理无效
        self.assertIn(
            "_mode===`full`&&(vo={},cacheIndex={},_dirty={},bo=!0,await wo(!0))",
            self.js,
        )
        self.assertNotIn("_mode===`full`&&(vo={},bo=!0,await wo())", self.js)

    def test_cache_prune_function_injected_and_called(self):
        self.assertEqual(self.js.count("function maybePruneCache("), 1)
        self.assertIn("maybePruneCache();", self.js)

    def test_cache_prune_caps_memory_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            js_path = Path(directory) / "patched.js"
            js_path.write_text(self.js, encoding="utf-8")
            js_literal = json.dumps(str(js_path))
            script = f"""
const fs = require('fs');
const js = fs.readFileSync({js_literal}, 'utf-8');
const start = js.indexOf('var _o=');
const end = js.indexOf('var ko=');
const region = js.slice(start, end) + '\\nreturn {{vo,cacheIndex,_o,cacheV2Key,So,To,Eo,maybePruneCache}};';
const api = new Function(region)();
const scope = 'en|zh|deepseek-v4-flash|g0';
for (let i = 0; i < 31000; i++) {{
  api.Eo(scope, 'text' + i, 't' + i);
}}
// 把前 20000 条的 updatedAt 改为很旧，验证按新旧淘汰
let seen = 0;
for (const k of Object.keys(api.vo)) {{
  if (k.startsWith(api._o)) {{ api.vo[k].updatedAt = seen++; }}
}}
api.maybePruneCache();
const v2keys = Object.keys(api.vo).filter(k => k.startsWith(api._o));
const out = {{}};
out.countAfter = v2keys.length;
out.oldestAlive = Math.min(...v2keys.map(k => api.vo[k].updatedAt));
// cacheIndex 同步：任何 cacheIndex 引用都必须存在于 vo
out.orphanIndex = Object.keys(api.cacheIndex).filter(id => !api.vo[api._o + 'v2|' + id]).length;
// 被淘汰的旧条目在 To 中不可命中
out.toOld = api.To(scope, 'text0');
out.toNew = api.To(scope, 'text30999');
process.stdout.write(JSON.stringify(out));
"""
            out = json.loads(run_node(script, ROOT))

        self.assertLessEqual(out["countAfter"], 30000, "prune 后必须低于上限")
        self.assertGreaterEqual(out["oldestAlive"], 15000, "最旧的一半应被淘汰")
        self.assertEqual(out["orphanIndex"], 0, "cacheIndex 不得残留 vo 中已删除的引用")
        self.assertIsNone(out["toOld"], "被淘汰的条目不得再命中")
        self.assertIsNotNone(out["toNew"], "新条目应保留")
    def test_cache_save_is_throttled_until_forced_flush(self):
        module = self.module
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            js_path = Path(directory) / "patched.js"
            js_path.write_text(js, encoding="utf-8")
            js_literal = json.dumps(str(js_path))
            script = f"""
const fs = require('fs');
const js = fs.readFileSync({js_literal}, 'utf-8');
const start = js.indexOf('var _o=');
const end = js.indexOf('var ko=', start);
const region = js.slice(start, end) + '\\nreturn {{wo,vo,cacheIndex,bo,Eo}};';
const api = new Function(region)();
const saves = [];
globalThis.E={{loadTranslationCache:async()=>({{data:null}}),saveTranslationCache:async payload=>{{saves.push(payload.data.length)}}}};
globalThis.O=()=>{{}};
const scope='en|zh|deepseek-v4-flash|g0';
(async()=>{{
  api.Eo(scope,'text-a','a');
  await api.wo();
  const afterFirst=saves.length;
  api.Eo(scope,'text-b','b');
  await api.wo();
  const afterSecond=saves.length;
  api.Eo(scope,'text-c','c');
  await api.wo(true);
  const afterFlush=saves.length;
   process.stdout.write(JSON.stringify({{afterFirst,afterSecond,afterFlush,skipped:globalThis.__slgCacheDbg.skipped}}));process.exit(0);
}})();
"""
            out = json.loads(run_node(script, ROOT))
            self.assertEqual(out["afterFirst"], 1, "first dirty cache writes a checkpoint")
            self.assertEqual(out["afterSecond"], 1, "recent non-forced calls must not serialize the full cache again")
            self.assertEqual(out["afterFlush"], 2, "forced flush persists the dirty cache")
            self.assertGreaterEqual(out["skipped"], 1, "throttled call is counted as skipped")
