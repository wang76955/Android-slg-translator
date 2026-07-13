from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parent
WORKSHOP_COPY = (
    "让喜欢的故事，用中文继续。",
    "选择 APK 文件",
    "处理详情",
    "立即安装",
    "保存 APK",
)

WORKSHOP_CSS = r"""
:root{--workshop-bg:oklch(1 0 0);--workshop-surface:oklch(.965 .004 95);--workshop-ink:oklch(.22 .018 112);--workshop-muted:oklch(.46 .025 108);--workshop-primary:oklch(.36 .082 120);--workshop-on-primary:oklch(.98 .004 95);--workshop-accent:oklch(.84 .145 84);--workshop-on-accent:oklch(.24 .035 84);--workshop-error:oklch(.56 .17 28);color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{--workshop-bg:oklch(.11 0 0);--workshop-surface:oklch(.17 .012 112);--workshop-ink:oklch(.94 .008 95);--workshop-muted:oklch(.72 .018 105);--workshop-primary:oklch(.72 .10 120);--workshop-on-primary:oklch(.14 .025 120);--workshop-accent:oklch(.78 .13 84);--workshop-on-accent:oklch(.16 .025 84);--workshop-error:oklch(.72 .15 28)}}
.workshop-touch{min-width:48px;min-height:48px}
.workshop-runtime{min-height:100dvh;padding-top:env(safe-area-inset-top);background:var(--workshop-bg);color:var(--workshop-ink)}
.workshop-runtime>header,.workshop-runtime>nav,.workshop-runtime>footer{display:none!important}
.workshop-hero{margin:18px 16px 4px;padding:22px 20px;border-radius:24px;background:var(--workshop-primary);color:var(--workshop-on-primary);box-shadow:0 16px 36px color-mix(in oklch,var(--workshop-primary) 20%,transparent)}
.workshop-hero small{display:block;font-size:13px;opacity:.8}.workshop-hero h1{margin:7px 0 18px;font-size:26px;line-height:1.18;font-weight:750;letter-spacing:-.02em}
.workshop-runtime main{padding:16px 16px 104px!important;background:var(--workshop-bg)!important}.workshop-runtime main>div,.workshop-runtime main>section,.workshop-runtime main details{border-color:color-mix(in oklch,var(--workshop-ink) 12%,transparent)!important;background:var(--workshop-surface)!important;border-radius:18px!important;box-shadow:none!important}.workshop-runtime button[class*="bg-blue"]{min-height:48px;background:var(--workshop-primary)!important;color:var(--workshop-on-primary)!important;border-radius:16px!important}.workshop-runtime [class*="text-blue"]{color:var(--workshop-primary)!important}
.workshop-picker-source>h2,.workshop-picker-source>button{display:none!important}
.workshop-task-shell{position:relative;display:flex;flex-direction:column;gap:16px;min-height:calc(100dvh - 24px);padding:20px 16px 112px;background:var(--workshop-bg);color:var(--workshop-ink)}
.workshop-task-topbar{display:flex;align-items:center;justify-content:space-between;min-height:48px}
.workshop-task-topbar h1{margin:0;font-size:20px;line-height:1.25;font-weight:700;letter-spacing:-.01em}
.workshop-task-back{min-width:48px;min-height:48px;border:0;border-radius:14px;background:transparent;color:var(--workshop-ink);font-size:22px}
.workshop-brand-panel{padding:18px 18px 20px;border-radius:20px;background:var(--workshop-primary);color:var(--workshop-on-primary)}
.workshop-brand-panel p{margin:0;font-size:14px;line-height:1.45;opacity:.86}
.workshop-brand-panel h2{margin:4px 0 0;font-size:25px;line-height:1.2;font-weight:750;letter-spacing:-.02em}
.workshop-task-card{padding:18px;border:1px solid color-mix(in oklch,var(--workshop-ink) 12%,transparent);border-radius:18px;background:var(--workshop-surface);box-shadow:none}
.workshop-file-row{display:flex;align-items:center;gap:12px;min-height:56px}
.workshop-file-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;background:color-mix(in oklch,var(--workshop-primary) 12%,var(--workshop-surface));color:var(--workshop-primary);font-weight:800}
.workshop-file-name{min-width:0;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.workshop-file-meta{margin-top:3px;color:var(--workshop-muted);font-size:13px}
.workshop-state-copy{margin:12px 0 0;color:var(--workshop-muted);line-height:1.45}
.workshop-progress{height:4px;margin-top:14px;border-radius:999px;background:color-mix(in oklch,var(--workshop-primary) 14%,transparent);overflow:hidden}
.workshop-progress>i{display:block;width:38%;height:100%;border-radius:inherit;background:var(--workshop-primary);transition:width 220ms ease-out}
.workshop-summary-list{display:grid;gap:10px;margin:16px 0 0;padding:0;list-style:none}
.workshop-summary-row{display:flex;justify-content:space-between;gap:16px;font-size:14px}
.workshop-summary-row span:first-child{color:var(--workshop-muted)}
.workshop-summary-row span:last-child{text-align:right;font-weight:700}
.workshop-detail-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;margin-top:12px;padding:0;border:0;background:transparent;color:var(--workshop-primary);font-weight:700;text-align:left}
.workshop-detail-body{display:none;margin-top:8px;padding:12px;border-radius:12px;background:color-mix(in oklch,var(--workshop-ink) 5%,var(--workshop-surface));color:var(--workshop-muted);font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
.workshop-detail-body[data-open="true"]{display:block}
.workshop-task-shell[data-workshop-state="idle"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="scanning"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="ready"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="failed"] .workshop-progress{display:none}
.workshop-primary-action{display:flex;align-items:center;justify-content:center;width:100%;min-height:52px;margin-top:auto;border:0;border-radius:16px;background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:750;font-size:15px}
.workshop-secondary-action{min-height:48px;margin-top:8px;border:0;background:transparent;color:var(--workshop-primary);font-weight:700}
.workshop-error-card{border-color:color-mix(in oklch,var(--workshop-error) 30%,transparent);background:color-mix(in oklch,var(--workshop-error) 7%,var(--workshop-surface))}
.workshop-error-title{margin:0;color:var(--workshop-error);font-size:18px;font-weight:750}
.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}
.workshop-runtime[data-workshop-task="active"] main{display:none!important}
body:has(.workshop-runtime[data-workshop-task="active"]) .workshop-bottom-nav{display:none!important}
.workshop-bottom-nav{position:fixed;z-index:30;left:12px;right:12px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(3,1fr);padding:6px;border:1px solid color-mix(in oklch,var(--workshop-ink) 12%,transparent);border-radius:22px;background:color-mix(in oklch,var(--workshop-bg) 94%,transparent);box-shadow:0 10px 35px color-mix(in oklch,var(--workshop-ink) 16%,transparent)}
.workshop-bottom-nav button{min-height:52px;border:0;border-radius:16px;background:transparent;color:var(--workshop-muted);font-size:13px;font-weight:650}.workshop-bottom-nav button[aria-current="page"]{background:var(--workshop-surface);color:var(--workshop-primary)}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
"""

WORKSHOP_RUNTIME = r"""
;(()=>{const ID="workshop-runtime";function textNode(tag,cls,text){const el=document.createElement(tag);el.className=cls;el.textContent=text;return el}function findButton(label){return[...document.querySelectorAll("#root button")].find(el=>!el.closest(".workshop-hero")&&el.textContent&&el.textContent.includes(label))}function scrollToLabel(label){const target=[...document.querySelectorAll("#root h1,#root h2,#root summary")].find(el=>el.textContent&&el.textContent.includes(label));(target||document.querySelector("#root")).scrollIntoView({behavior:"smooth",block:"start"})}function decorate(){const heading=[...document.querySelectorAll("#root h2")].find(el=>el.textContent&&el.textContent.includes("选择游戏 APK"));if(heading&&heading.parentElement)heading.parentElement.classList.add("workshop-picker-source");const startButton=[...document.querySelectorAll("#root button")].find(el=>el.textContent&&el.textContent.includes("开始翻译"));if(startButton)startButton.classList.add("workshop-start-button")}function mount(){const sourceButton=findButton("选择");decorate();const app=document.querySelector("#root>div");if(!app||app.dataset.workshopMounted||!sourceButton)return;app.dataset.workshopMounted="true";app.classList.add(ID);const hero=document.createElement("section");hero.className="workshop-hero";hero.append(textNode("small","","今天翻译什么？"),textNode("h1","","让喜欢的故事，用中文继续。"));sourceButton.classList.add("workshop-source-button");sourceButton.setAttribute("aria-label","选择 APK 文件");const start=textNode("button","workshop-touch","选择 APK 文件");start.type="button";start.setAttribute("aria-hidden","true");start.onclick=()=>sourceButton.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,view:window}));hero.append(start);app.prepend(hero);const nav=document.createElement("nav");nav.className="workshop-bottom-nav";nav.setAttribute("aria-label","主导航");[["首页",()=>window.scrollTo({top:0,behavior:"smooth"})],["作品",()=>scrollToLabel("处理详情")],["我的",()=>scrollToLabel("翻译设置")]].forEach(([label,action],index)=>{const button=textNode("button","workshop-touch",label);button.type="button";if(index===0)button.setAttribute("aria-current","page");button.onclick=()=>{[...nav.children].forEach(el=>el.removeAttribute("aria-current"));button.setAttribute("aria-current","page");action()};nav.append(button)});document.body.append(nav)}new MutationObserver(mount).observe(document.documentElement,{childList:true,subtree:true});document.readyState==="loading"?document.addEventListener("DOMContentLoaded",mount):mount()})();
"""


def patch_assets(js: str, css: str) -> tuple[str, str]:
    copy_contract = "\n/* workshop-copy:" + "|".join(WORKSHOP_COPY) + " */\n"
    return js + copy_contract + WORKSHOP_RUNTIME, css + "\n" + WORKSHOP_CSS


def main() -> None:
    source = ROOT.parent / "extracted" / "assets" / "public" / "assets"
    output = ROOT / "generated"
    output.mkdir(exist_ok=True)
    js, css = patch_assets(
        (source / "index-CJtfdHOF.js").read_text("utf-8"),
        (source / "index-C044IUg3.css").read_text("utf-8"),
    )
    (output / "index-CJtfdHOF.js").write_text(js, "utf-8")
    (output / "index-C044IUg3.css").write_text(css, "utf-8")


if __name__ == "__main__":
    main()
