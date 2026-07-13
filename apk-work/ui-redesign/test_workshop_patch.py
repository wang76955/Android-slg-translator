import importlib.util
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

    def test_patch_contains_player_workshop_contract(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        for copy in (
            "让喜欢的故事，用中文继续。",
            "选择 APK 文件",
            "处理详情",
            "立即安装",
            "保存 APK",
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
            "workshop-hero",
            "workshop-bottom-nav",
            "workshop-picker-source",
            "workshop-task-shell",
            "data-workshop-state",
            "workshop-state-idle",
            "workshop-state-scanning",
            "workshop-state-ready",
            "workshop-state-failed",
            "setWorkshopState",
            "澶勭悊璇︽儏",
            "姝ｅ湪妫€鏌ユ枃浠?",
            "鍙互寮€濮嬩簡",
            "鎵嬫満绌洪棿涓嶈冻",
            "首页",
            "作品",
            "我的",
        ):
            self.assertIn(token, js)
        self.assertIn('sourceButton.classList.add("workshop-source-button")', js)
        self.assertIn('start.onclick=()=>sourceButton.dispatchEvent', js)
        self.assertIn('startButton.classList.add("workshop-start-button")', js)
        self.assertNotIn("hero.append(sourceButton)", js)
        self.assertNotIn("button&&button.click()", js)
        for token in (
            "env(safe-area-inset-top)",
            "env(safe-area-inset-bottom)",
            ".workshop-hero",
            ".workshop-bottom-nav",
        ):
            self.assertIn(token, css)
        picker_rule = css.split(".workshop-picker-source", 1)[1].split("}", 1)[0]
        self.assertIn(".workshop-picker-source>h2", css)
        self.assertIn(".workshop-start-button", css)
        self.assertIn("workshop-task-shell", css)
        self.assertIn('workshop-task-shell[data-workshop-state="scanning"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="ready"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="failed"]', css)
        self.assertIn(
            '.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav',
            css,
        )
        self.assertIn("left:50%", css)
        self.assertIn("transform:translateX(-50%)", css)
        self.assertIn("width:min(220px,calc(100vw - 48px))", css)
        self.assertIn("min-height:48px", css)
        self.assertNotIn(".workshop-picker-source{display:none!important}", css)
        self.assertNotIn("clip-path", picker_rule)


if __name__ == "__main__":
    unittest.main()
