import importlib.util
import json
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
        raise AssertionError("node failed: " + (result.stderr or "")[:2000])
    return result.stdout


class EnginePerformancePatchTest(unittest.TestCase):
    def setUp(self):
        self.module = load_patch()
        self.js, _ = self.module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

    def test_global_api_semaphore_is_injected_and_caps_concurrency(self):
        self.assertIn("globalThis.__slgApiSemaphore=", self.js)
        self.assertIn(
            "await globalThis.__slgApiSemaphore.run(()=>Bo(",
            self.js,
        )
        start = self.js.index("globalThis.__slgApiSemaphore=")
        end = self.js.index("async function runFileTasksParallel", start)
        code = self.js[start:end] + "\nreturn globalThis.__slgApiSemaphore;"
        script = f"""
const semaphore = new Function({json.dumps(code)})();
let active = 0, maxActive = 0, finished = 0;
const delay = ms => new Promise(r => setTimeout(r, ms));
const tasks = Array.from({{length: 12}}, () => semaphore.run(async () => {{
  active++;
  maxActive = Math.max(maxActive, active);
  await delay(5);
  active--;
  finished++;
}}));
Promise.all(tasks).then(() => {{
  process.stdout.write(JSON.stringify({{maxActive, finished}}));
}}).catch(error => {{ console.error(error); process.exit(1); }});
"""
        out = json.loads(run_node(script))
        self.assertLessEqual(out["maxActive"], 6)
        self.assertEqual(out["finished"], 12)

    def test_file_controller_uses_six_workers_and_final_flush(self):
        self.assertIn(
            "return N},(window.__slgLocalSelected?2:6));if(!N)await wo(!0);if(!N&&(a.length>0||oe)){",
            self.js,
        )
        self.assertNotIn(
            "return N},2);if(!N&&(a.length>0||oe)){",
            self.js,
        )
        self.assertGreaterEqual(self.js.count(",bo=!0,wo(!0)"), 2)
        self.assertNotIn("await wo(!0),delete vo[_fk]", self.js)
        self.assertIn(
            "(_maxDone=Math.max(_maxDone,c+1),ue({current:_maxDone,total:ae.length}))",
            self.js,
        )
        self.assertNotIn("ue({current:c+1,total:ae.length})", self.js)

    def test_output_write_caches_directory_uris(self):
        start = self.js.index("async function Ne(e,t){let n=e.split(`/`)")
        end = self.js.index("return(0,D.jsxs)", start)
        writer_src = self.js[start:end] + "\nreturn Ne;"
        script = f"""
const created = [];
const writes = [];
const E = {{
  createDirectory: async ({{dirUri, dirName}}) => {{
    created.push(dirUri + '/' + dirName);
    return {{success: true, uri: dirUri + '/' + dirName}};
  }},
  writeFileToDir: async ({{dirUri, fileName}}) => {{
    writes.push(dirUri + '/' + fileName);
  }},
}};
const Ne = new Function('E', 'm', {json.dumps(writer_src)})(E, 'root');
(async () => {{
  delete globalThis.__slgDirCache;
  delete globalThis.__slgDirCacheBase;
  await Ne('a/b/one.rpy', 'one');
  await Ne('a/b/two.rpy', 'two');
  process.stdout.write(JSON.stringify({{created, writes}}));
}})();
"""
        out = json.loads(run_node(script))
        self.assertEqual(out["created"], ["root/a", "root/a/b"])
        self.assertEqual(out["writes"], ["root/a/b/one.rpy", "root/a/b/two.rpy"])

    def test_cache_save_is_incremental_and_loads_delta(self):
        start = self.js.index("var _o=")
        end = self.js.index("var ko=", start)
        region = (
            self.js[start:end]
            + "\nreturn {wo,vo,cacheIndex,_dirty,bo,Eo,Co,To,cacheV2Key,_o};"
        )
        script = f"""
const apiCode = {json.dumps(region)};
const api = new Function(apiCode)();
const saves = [];
globalThis.E = {{
  loadTranslationCache: async () => ({{data: null}}),
  saveTranslationCache: async payload => {{ saves.push(payload.data); }},
}};
globalThis.O = () => {{}};
const scope = 'en|zh|deepseek-v4-flash|g0';
(async () => {{
  api.Eo(scope, 'a', 'A');
  api.Eo(scope, 'b', 'B');
  await api.wo(true);
  const first = Object.keys(JSON.parse(saves.pop()));
  api.Eo(scope, 'c', 'C');
  await api.wo(true);
  const second = Object.keys(JSON.parse(saves.pop()));
  const voCountBeforeLoad = Object.keys(api.vo).filter(k => k.startsWith(api._o)).length;

  const api2 = new Function(apiCode)();
  const key = api2.cacheV2Key(scope, 'loaded');
  globalThis.E.loadTranslationCache = async () => ({{
    data: JSON.stringify({{[key]: {{sourceText: 'loaded', translatedText: 'X-loaded', updatedAt: 1}}}}),
  }});
  await api2.Co();
  process.stdout.write(JSON.stringify({{
    first,
    second,
    voCountBeforeLoad,
    voCountAfterLoad: Object.keys(api2.vo).filter(k => k.startsWith(api2._o)).length,
    loaded: api2.To(scope, 'loaded'),
  }}));
}})();
"""
        out = json.loads(run_node(script))
        self.assertEqual(len(out["first"]), 2)
        self.assertEqual(len(out["second"]), 1)
        self.assertEqual(out["voCountBeforeLoad"], 3)
        self.assertEqual(out["voCountAfterLoad"], 1)
        self.assertEqual(out["loaded"], "X-loaded")


if __name__ == "__main__":
    unittest.main()
