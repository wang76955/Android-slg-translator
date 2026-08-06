import importlib.util
import json
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
  out.cacheVersion = js.includes('var _o=`slg-translator-cache:v2:`');
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

    def test_keypath_prefix_and_cache_version_patches(self):
        # 修复 P0-1：提取时把文件路径写入 keyPath（真实格式 file::seq）
        self.assertEqual(self.js.count("l=ke(i,s,o.name+`::`,g)"), 1)
        # 修复 P0-2：缓存键加 v2 版本，旧缓存自动失效
        self.assertEqual(self.js.count("var _o=`slg-translator-cache:v2:`"), 1)
        self.assertNotIn("slg-translator-cache:", self.js.replace("slg-translator-cache:v2:", ""))

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
    RenpyTextRecord c1 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "alice", "", "game/a.rpyc", 3, 1, true);
    RenpyTextRecord c2 = new RenpyTextRecord("Fine.", RenpyTextRecord.Kind.DIALOGUE, "bob", "", "game/b.rpyc", 4, 1, true);
    RenpyTranslationCorpus.Corpus corpus = RenpyTranslationCorpus.build(Arrays.asList(same1, same2, c1, c2));
    RenpyTranslationCorpus.Entry repeated = corpus.get("OK{#menu}");
    RenpyTranslationCorpus.Entry collision = corpus.get("Fine.");
    if (repeated == null || repeated.occurrences.size() != 2 || repeated.contextualCollision) throw new AssertionError("repeat");
    if (collision == null || collision.occurrences.size() != 2 || !collision.contextualCollision) throw new AssertionError("collision");
    if (!RenpyTranslationCorpus.contextPrompt(collision).contains("contexts=2")) throw new AssertionError("prompt count");
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
            result = subprocess.run([str(JAVA), "-cp", str(out), "Task8CorpusHarness"], check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.Task8CompileGateHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_task8_prompt_limits_contexts_and_compile_rejects_conflicting_translations(self):
        self.assertIn("up to 3 representative contexts", self.js)
        self.assertIn("translation_collision_conflict", self.js)
        self.assertIn("conflicting translations", self.js)


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
