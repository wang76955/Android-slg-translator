import importlib.util
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
BASE_JS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
BASE_CSS = ROOT.parent / "extracted" / "assets" / "public" / "assets" / "index-C044IUg3.css"


def load_patch():
    spec = importlib.util.spec_from_file_location("patch_workshop_ui", ROOT / "patch_workshop_ui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_function(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    brace = js.index("{", start)
    depth = 0
    for i in range(brace, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
    raise AssertionError(f"could not extract {name}")


class ProgressRefreshContractTest(unittest.TestCase):
    def patch_assets(self):
        module = load_patch()
        return module.patch_assets(BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8"))

    def test_runtime_polls_refresh_for_live_log_updates(self):
        js, _ = self.patch_assets()
        self.assertIn("window.__slgRefreshTimer", js)
        self.assertIn(
            "if(!document.hidden&&!settingsOpen&&!retrying)refresh()}",
            js,
        )
        self.assertIn("setInterval(", js)

    def test_progress_prefers_live_script_progress_and_separates_blocks(self):
        js, _ = self.patch_assets()
        helpers = "\n".join(
            extract_function(js, name)
            for name in ("sourceText", "readProgressLog", "readTaskSnapshot")
        )
        code = r"""
globalThis.window = {
  __slgSelectionError: null,
  __slgSelectionMeta: { name: "ECHOES.apk" },
  __slgScanWatchdog: { epoch: 1, settled: true, timerFired: false }
};
globalThis.__slgSelectionEpoch = 1;
globalThis.sessionRestoredAt = 0;
const logSource = {
  closest: () => null,
  children: [
    { innerText: "21:20:00 [14/108] old line" },
    { innerText: "21:21:00 [108/108] stale completed line" },
  ],
};
const liveText = { nodeType: 3, textContent: "正在处理脚本 14 / 108" };
const liveBlock = { nodeType: 1, tagName: "SECTION", childNodes: [liveText] };
const logText = { nodeType: 3, textContent: "21:21:00 [108/108] stale" };
const logBlock = { nodeType: 1, tagName: "DIV", childNodes: [logText] };
const clone = {
  querySelector: () => null,
  childNodes: [liveBlock, logBlock],
  textContent: "正在处理脚本 14 / 10821:21:00 [108/108] stale",
};
const root = { cloneNode: () => clone, textContent: clone.textContent };
globalThis.document = {
  querySelector: () => root,
  querySelectorAll: (sel) => sel.includes("font-mono") ? [logSource] : [],
};
const snap = readTaskSnapshot();
if (snap.state !== "translating") throw new Error("state=" + snap.state);
if (snap.current !== "14") throw new Error("current=" + snap.current);
if (snap.total !== "108") throw new Error("total=" + snap.total);
"""
        result = subprocess.run(
            ["node", "-e", helpers + "\n" + code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
    def test_selected_file_name_falls_back_to_selection_meta(self):
        js, _ = self.patch_assets()
        self.assertIn(
            'const fileName=selected?.[1]?.trim()||selectionMeta?.name||selectionMeta?.label||selectionMeta?.fileName||"";',
            js,
        )
        helpers = "\n".join(
            extract_function(js, name)
            for name in ("sourceText", "readProgressLog", "readTaskSnapshot")
        )
        code = r"""
const metaName = "\u793a\u4f8b\u6e38\u620f.apk";
globalThis.window = {
  __slgSelectionError: null,
  __slgSelectionMeta: { name: metaName, label: "\u793a\u4f8b\u6e38\u620f" },
  __slgScanWatchdog: { epoch: 1, settled: true, timerFired: false }
};
globalThis.__slgSelectionEpoch = 1;
globalThis.sessionRestoredAt = 0;
const clone = { querySelector: () => null, textContent: "\u53d1\u73b0 1 \u4e2a\u53ef\u7ffb\u8bd1\u6587\u4ef6" };
const root = { cloneNode: () => clone, textContent: clone.textContent };
globalThis.document = { querySelector: () => root, querySelectorAll: () => [] };
const snap = readTaskSnapshot();
if (snap.state !== "ready") throw new Error("state=" + snap.state);
if (snap.fileName !== metaName) throw new Error("fileName=" + snap.fileName);
if (snap.count !== "1") throw new Error("count=" + snap.count);
"""
        result = subprocess.run(
            ["node", "-e", helpers + "\n" + code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
