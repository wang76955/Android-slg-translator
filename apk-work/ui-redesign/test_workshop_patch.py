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
            "workshop-task-shell",
            "workshop-bottom-nav",
            "workshop-picker-source",
            "data-workshop-state",
            "workshop-state-idle",
            "workshop-state-scanning",
            "workshop-state-ready",
            "workshop-state-failed",
            "setWorkshopState",
            "处理详情",
            "正在检查文件",
            "可以开始了",
            "手机空间不足",
            "首页",
            "作品",
            "我的",
        ):
            self.assertIn(token, js)
        self.assertIn('sourceButton.classList.add("workshop-source-button")', js)
        self.assertIn('triggerReactButton(button)', js)
        self.assertIn('dispatchEvent(new MouseEvent("click"', js)
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
        self.assertIn('function retryTask(payload)', js)
        self.assertIn('triggerReactButton(startButton||sourceButton)', js)
        self.assertIn('window.setTimeout(()=>{retrying=false;refresh()},600)', js)

        # State changes are reflected on both data attributes and state
        # classes, which lets the CSS keep idle navigation and active task
        # content mutually exclusive.
        self.assertIn('shell.dataset.workshopState=state', js)
        self.assertIn('shell.dataset.workshopTask=state==="idle"?"idle":"active"', js)
        self.assertIn('shell.setAttribute("data-workshop-state",state)', js)
        self.assertIn('shell.setAttribute("data-workshop-task",shell.dataset.workshopTask)', js)
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

        # ENOSPC is recoverable: the user sees a concise localized message,
        # while the raw diagnostic remains behind the details disclosure.
        self.assertIn('ENOSPC|No space left', js)
        self.assertIn('手机空间不足', js)
        self.assertIn('释放空间后重试', js)
        self.assertIn('detailToggle(payload.raw||"ENOSPC|No space left")', js)

        # Keep React-managed controls mounted and avoid direct click shortcuts;
        # the shell may only dispatch events to those existing nodes.
        self.assertNotIn('hero.append(sourceButton)', js)
        self.assertNotIn('hero.append(startButton)', js)
        self.assertNotIn('shell.append(sourceButton)', js)
        self.assertNotIn('shell.append(startButton)', js)
        self.assertNotIn('button&&button.click()', js)

        # A single debounced observer prevents React's intermediate renders
        # from causing duplicate shell mounts or state flicker.
        self.assertIn('new MutationObserver(schedule)', js)
        self.assertIn('clearTimeout(debounceTimer);debounceTimer=setTimeout(mount,120)', js)
        self.assertIn('observer.observe(document.querySelector("#root")||document.documentElement', js)


if __name__ == "__main__":
    unittest.main()
