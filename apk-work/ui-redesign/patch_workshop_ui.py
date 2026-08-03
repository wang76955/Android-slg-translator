from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).parent
# These hashes pin the RPYC-revised canonical extraction used as the patching
# baseline. A different extraction must be reviewed and deliberately re-pinned.
CANONICAL_BASE_JS_SHA256 = (
    "d3b0f42a6656e347e5933e17835b8b687f1dc2f5546c1aa15b8fb2048ebe1f85"
)
CANONICAL_BASE_CSS_SHA256 = (
    "fad58dc778c5b4fa0ac263f5aebcba268c6fb32e9d8b39ae980805b49d5fb18f"
)
WORKSHOP_COPY = (
    "让喜欢的故事，用中文继续。",
    "选择 APK 文件",
    "处理详情",
    "立即安装",
    "保存 APK",
)

WORKSHOP_CSS = r""":root{--workshop-bg:oklch(.985 .006 110);--workshop-surface:oklch(.972 .009 105);--workshop-surface-2:oklch(.955 .012 100);--workshop-ink:oklch(.26 .026 140);--workshop-muted:oklch(.52 .032 132);--workshop-primary:oklch(.43 .095 148);--workshop-on-primary:oklch(.99 .004 105);--workshop-primary-soft:oklch(.94 .025 145);--workshop-accent:oklch(.70 .135 72);--workshop-on-accent:oklch(.22 .04 72);--workshop-accent-soft:oklch(.95 .04 85);--workshop-error:oklch(.56 .19 25);--workshop-success:oklch(.52 .12 150);--workshop-warning:oklch(.66 .13 75);--workshop-info:oklch(.55 .10 240);--workshop-border:color-mix(in oklch,var(--workshop-ink) 12%,transparent);--workshop-shadow-sm:0 1px 2px color-mix(in oklch,var(--workshop-ink) 6%,transparent);--workshop-shadow-md:0 8px 24px color-mix(in oklch,var(--workshop-ink) 10%,transparent);--workshop-shadow-lg:0 18px 48px color-mix(in oklch,var(--workshop-ink) 18%,transparent);--workshop-radius-sm:12px;--workshop-radius-md:16px;--workshop-radius-lg:22px;--workshop-radius-xl:28px;color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{--workshop-bg:oklch(.125 .014 135);--workshop-surface:oklch(.17 .017 140);--workshop-surface-2:oklch(.21 .02 145);--workshop-ink:oklch(.94 .008 100);--workshop-muted:oklch(.74 .015 110);--workshop-primary:oklch(.74 .105 152);--workshop-on-primary:oklch(.14 .03 145);--workshop-primary-soft:oklch(.26 .05 150);--workshop-accent:oklch(.78 .12 80);--workshop-on-accent:oklch(.18 .03 75);--workshop-accent-soft:oklch(.30 .06 85);--workshop-error:oklch(.70 .16 25);--workshop-success:oklch(.74 .12 152);--workshop-warning:oklch(.80 .12 80);--workshop-info:oklch(.72 .09 240);--workshop-border:color-mix(in oklch,var(--workshop-ink) 16%,transparent);--workshop-shadow-sm:0 1px 2px rgb(0 0 0 / .18);--workshop-shadow-md:0 8px 24px rgb(0 0 0 / .28);--workshop-shadow-lg:0 18px 48px rgb(0 0 0 / .40)}}
.workshop-touch{min-width:48px;min-height:48px}
.workshop-runtime{min-height:100dvh;padding-top:env(safe-area-inset-top);background:var(--workshop-bg);color:var(--workshop-ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased;letter-spacing:.01em}
.workshop-runtime>header,.workshop-runtime>nav,.workshop-runtime>footer{display:none!important}
.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav{display:grid!important}
.workshop-hero{margin:18px 16px 4px;padding:24px 22px 26px;border-radius:var(--workshop-radius-xl);background:linear-gradient(145deg,var(--workshop-primary),color-mix(in oklch,var(--workshop-primary) 78%,var(--workshop-accent)));color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-md);position:relative;overflow:hidden}
.workshop-hero::before{content:"";position:absolute;top:-40%;right:-15%;width:70%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,color-mix(in oklch,var(--workshop-accent) 34%,transparent),transparent 68%)}
.workshop-hero::after{content:"◈";position:absolute;right:18px;bottom:-8px;font-size:96px;line-height:1;opacity:.12;transform:rotate(12deg)}
.workshop-hero small{position:relative;display:block;font-size:13px;opacity:.88;letter-spacing:.06em;text-transform:uppercase}
.workshop-hero h1{position:relative;margin:8px 0 14px;font-size:28px;line-height:1.16;font-weight:800;letter-spacing:-.025em;text-wrap:balance;max-width:22ch}
.workshop-runtime main{display:none!important;padding:16px 16px 104px!important;background:var(--workshop-bg)!important}.workshop-runtime main>div,.workshop-runtime main>section,.workshop-runtime main details{border-color:var(--workshop-border)!important;background:var(--workshop-surface)!important;border-radius:var(--workshop-radius-lg)!important;box-shadow:var(--workshop-shadow-sm)!important}.workshop-runtime button[class*="bg-blue"]{min-height:48px;background:var(--workshop-primary)!important;color:var(--workshop-on-primary)!important;border-radius:var(--workshop-radius-md)!important}.workshop-runtime [class*="text-blue"]{color:var(--workshop-primary)!important}
.workshop-picker-source>h2,.workshop-picker-source>button{display:none!important}
.workshop-task-shell{position:relative;display:flex;flex-direction:column;gap:16px;min-height:calc(100dvh - 24px);padding:20px 16px 112px;background:var(--workshop-bg);color:var(--workshop-ink)}
.workshop-task-topbar{display:flex;align-items:center;justify-content:space-between;min-height:48px;margin-bottom:-4px}
.workshop-task-topbar h1{margin:0;font-size:20px;line-height:1.25;font-weight:750;letter-spacing:-.01em}
.workshop-task-back{display:flex;align-items:center;gap:3px;min-width:64px;min-height:44px;padding:0 14px 0 10px;border:1px solid var(--workshop-border);border-radius:999px;background:var(--workshop-surface);color:var(--workshop-ink);font-size:15px;font-weight:650;box-shadow:var(--workshop-shadow-sm);transition:background-color 160ms ease-out,transform 120ms ease-out}.workshop-task-back:active{transform:scale(.97);background:var(--workshop-surface-2)}
.workshop-task-back:active{background:var(--workshop-surface-2)}
.workshop-brand-panel{padding:22px 20px 24px;border-radius:var(--workshop-radius-xl);background:linear-gradient(150deg,var(--workshop-primary),color-mix(in oklch,var(--workshop-primary) 80%,var(--workshop-accent)));color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-md);position:relative;overflow:hidden}
.workshop-brand-panel::before{content:"";position:absolute;top:-45%;left:-10%;width:75%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,color-mix(in oklch,var(--workshop-accent) 30%,transparent),transparent 70%)}
.workshop-brand-panel::after{content:"译";position:absolute;right:16px;top:50%;transform:translateY(-50%);font-size:88px;font-weight:900;opacity:.10;letter-spacing:0}
.workshop-brand-panel p,.workshop-brand-panel h2{position:relative}
.workshop-brand-panel p{margin:0;font-size:14px;line-height:1.5;opacity:.9;max-width:32ch}
.workshop-brand-panel h2{margin:6px 0 0;font-size:27px;line-height:1.18;font-weight:800;letter-spacing:-.025em;text-wrap:balance}
.workshop-task-card{padding:18px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-lg);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm)}
.workshop-file-row{display:flex;align-items:center;gap:12px;min-height:56px}
.workshop-file-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary-soft);color:var(--workshop-primary);font-weight:800;font-size:15px}
.workshop-file-name{min-width:0;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.workshop-file-meta{margin-top:3px;color:var(--workshop-muted);font-size:13px}
.workshop-state-copy{margin:12px 0 0;color:var(--workshop-muted);line-height:1.5;font-size:14px}
.workshop-state-copy.workshop-scan-elapsed{display:block;margin-top:6px;color:var(--workshop-muted);font-size:13px;font-variant-numeric:tabular-nums}
.workshop-progress{height:6px;margin-top:16px;border-radius:999px;background:color-mix(in oklch,var(--workshop-primary) 16%,transparent);overflow:hidden;position:relative}
.workshop-progress>i{display:block;width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--workshop-primary),color-mix(in oklch,var(--workshop-primary) 55%,var(--workshop-accent)));transition:width 240ms cubic-bezier(.33,1,.68,1)}
.workshop-progress>i::after{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(90deg,transparent,color-mix(in oklch,var(--workshop-accent) 45%,transparent),transparent);background-size:200% 100%;animation:workshopShimmer 1.8s linear infinite}
@keyframes workshopShimmer{from{background-position:200% 0}to{background-position:-200% 0}}
.workshop-summary-list{display:grid;gap:10px;margin:16px 0 0;padding:0;list-style:none}
.workshop-summary-row{display:flex;justify-content:space-between;gap:16px;font-size:14px;line-height:1.45}
.workshop-summary-row span:first-child{color:var(--workshop-muted)}
.workshop-summary-row span:last-child{text-align:right;font-weight:750;font-variant-numeric:tabular-nums}
.workshop-detail-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;margin-top:12px;padding:0 4px;border:0;background:transparent;color:var(--workshop-primary);font-weight:700;text-align:left;border-radius:var(--workshop-radius-sm);transition:background-color 160ms ease-out}
.workshop-detail-toggle:active{background:var(--workshop-primary-soft)}
.workshop-detail-body{display:none;max-height:240px;margin-top:8px;padding:12px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface-2);color:var(--workshop-muted);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;line-height:1.55;white-space:pre-wrap;overflow:auto;overflow-wrap:anywhere}
.workshop-detail-body[data-open="true"]{display:block}
.workshop-live-line{margin:12px 0 0;padding:10px 12px;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary-soft);color:var(--workshop-muted);font-size:13px;line-height:1.5;overflow-wrap:anywhere}
.workshop-task-shell[data-workshop-state="idle"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="scanning"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="ready"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="translating"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="patching"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="completed"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="failed"] .workshop-progress{display:none}
.workshop-settings-shell{position:fixed;z-index:40;inset:0;display:flex;flex-direction:column;gap:16px;padding:20px 16px max(24px,env(safe-area-inset-bottom));background:var(--workshop-bg);color:var(--workshop-ink);overflow:auto}
.workshop-settings-shell[hidden]{display:none!important}
.workshop-settings-card{padding:20px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-lg);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm)}
.workshop-settings-card label{display:block;margin-bottom:8px;font-size:14px;font-weight:700}
.workshop-settings-input{box-sizing:border-box;width:100%;min-height:52px;padding:12px 14px;border:1px solid color-mix(in oklch,var(--workshop-ink) 20%,transparent);border-radius:var(--workshop-radius-sm);background:var(--workshop-bg);color:var(--workshop-ink);font-size:16px;transition:border-color 160ms ease-out,box-shadow 160ms ease-out}
.workshop-settings-input:focus{outline:none;box-shadow:0 0 0 3px color-mix(in oklch,var(--workshop-primary) 26%,transparent);border-color:var(--workshop-primary)}
.workshop-settings-save{width:100%;min-width:48px;min-height:52px;margin-top:16px;border:0;border-radius:var(--workshop-radius-md);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:750;font-size:15px;box-shadow:var(--workshop-shadow-sm);transition:transform 120ms ease-out,filter 160ms ease-out}
.workshop-settings-save:active{transform:scale(.98)}
.workshop-settings-helper{margin:12px 0 0;color:var(--workshop-muted);font-size:13px;line-height:1.5}
.workshop-settings-title{margin:0 0 16px;font-size:18px;line-height:1.3;font-weight:750}
.workshop-settings-field{display:block;margin-top:14px}
.workshop-settings-field:first-of-type{margin-top:0}
.workshop-settings-field>span{display:block;margin-bottom:7px;font-size:14px;font-weight:700}
.workshop-settings-conditional[hidden]{display:none!important}
.workshop-settings-error{margin:6px 0 0;color:var(--workshop-error);font-size:13px;line-height:1.4}
.workshop-settings-status{margin:10px 0 0;color:var(--workshop-muted);font-size:13px;line-height:1.45}
.workshop-primary-action{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;min-height:52px;margin-top:auto;border:0;border-radius:var(--workshop-radius-md);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:750;font-size:15px;box-shadow:var(--workshop-shadow-sm);transition:transform 120ms ease-out,box-shadow 160ms ease-out,filter 160ms ease-out}
.workshop-primary-action:active{transform:scale(.98);filter:brightness(.96)}
.workshop-secondary-action{min-width:48px;min-height:48px;margin-top:8px;padding:0 8px;border:0;border-radius:var(--workshop-radius-sm);background:transparent;color:var(--workshop-primary);font-weight:700;transition:background-color 160ms ease-out}
.workshop-secondary-action:active{background:var(--workshop-primary-soft)}
.workshop-error-card{border-color:color-mix(in oklch,var(--workshop-error) 32%,transparent);background:color-mix(in oklch,var(--workshop-error) 7%,var(--workshop-surface))}
.workshop-error-title{margin:0;color:var(--workshop-error);font-size:18px;font-weight:750}
.workshop-source-dialog{position:fixed;z-index:50;inset:0;box-sizing:border-box;display:flex;align-items:flex-end;justify-content:center;padding:16px;background:color-mix(in oklch,var(--workshop-ink) 44%,transparent);overflow:auto}.workshop-installed-dialog{position:fixed;z-index:50;inset:0;box-sizing:border-box;display:flex;align-items:flex-end;justify-content:center;padding:16px;background:color-mix(in oklch,var(--workshop-ink) 44%,transparent);overflow:auto}
.workshop-source-dialog[hidden],.workshop-installed-dialog[hidden]{display:none!important}
.workshop-modal-panel{box-sizing:border-box;width:min(100%,560px);max-height:min(82dvh,720px);padding:22px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-xl);background:var(--workshop-bg);color:var(--workshop-ink);box-shadow:var(--workshop-shadow-lg);overflow:auto;animation:workshopSheetIn 220ms cubic-bezier(.33,1,.68,1)}
@keyframes workshopSheetIn{from{transform:translateY(18px);opacity:0}to{transform:translateY(0);opacity:1}}
.workshop-modal-title{margin:0 0 6px;font-size:20px;line-height:1.3;font-weight:750}.workshop-modal-copy{margin:0 0 16px;color:var(--workshop-muted);font-size:14px;line-height:1.5}
.workshop-source-option,.workshop-modal-action,.workshop-app-row{box-sizing:border-box;width:100%;min-height:52px;border:0;border-radius:var(--workshop-radius-md);font:inherit}
.workshop-source-option{display:flex;align-items:center;padding:0 16px;margin-top:8px;background:var(--workshop-surface);color:var(--workshop-ink);font-weight:700;text-align:left;transition:background-color 160ms ease-out}.workshop-source-option:active{background:var(--workshop-surface-2)}.workshop-source-option:first-of-type{background:var(--workshop-primary);color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-sm)}
.workshop-modal-action{margin-top:8px;background:transparent;color:var(--workshop-primary);font-weight:700}.workshop-source-option:focus-visible,.workshop-modal-action:focus-visible,.workshop-app-row:focus-visible{outline:3px solid color-mix(in oklch,var(--workshop-primary) 32%,transparent);outline-offset:2px}
.workshop-installed-search{box-sizing:border-box;width:100%;min-height:52px;margin:12px 0;padding:0 14px;border:1px solid color-mix(in oklch,var(--workshop-ink) 20%,transparent);border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-ink);font-size:16px;transition:border-color 160ms ease-out,box-shadow 160ms ease-out}.workshop-installed-search:focus{outline:none;box-shadow:0 0 0 3px color-mix(in oklch,var(--workshop-primary) 26%,transparent);border-color:var(--workshop-primary)}
.workshop-app-list{display:grid;gap:8px;margin:0;padding:0;list-style:none}.workshop-app-row{display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding:8px 14px;background:var(--workshop-surface);color:var(--workshop-ink);text-align:left;transition:background-color 160ms ease-out}.workshop-app-row:active{background:var(--workshop-surface-2)}.workshop-app-label{font-weight:720}.workshop-app-package{margin-top:2px;color:var(--workshop-muted);font-size:12px;overflow-wrap:anywhere}.workshop-installed-status{margin:12px 0;padding:16px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-muted);line-height:1.5}.workshop-installed-error{color:var(--workshop-error)}
@media(min-width:600px){.workshop-source-dialog,.workshop-installed-dialog{align-items:center}.workshop-modal-panel{border-radius:var(--workshop-radius-xl)}}
.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}
.workshop-runtime[data-workshop-task="active"] main{display:none!important}
body:has(.workshop-runtime[data-workshop-task="active"]) .workshop-bottom-nav{display:none!important}
.workshop-bottom-nav{position:fixed;z-index:30;left:12px;right:12px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(3,1fr);padding:6px;border:1px solid var(--workshop-border);border-radius:26px;background:color-mix(in oklch,var(--workshop-bg) 92%,transparent);box-shadow:var(--workshop-shadow-md);backdrop-filter:blur(10px)}
.workshop-bottom-nav button{min-height:52px;border:0;border-radius:20px;background:transparent;color:var(--workshop-muted);font-size:13px;font-weight:650;transition:color 160ms ease-out,background-color 160ms ease-out,transform 120ms ease-out}.workshop-bottom-nav button:active{transform:scale(.96)}.workshop-bottom-nav button[aria-current="page"]{background:var(--workshop-primary);color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-sm)}
.workshop-gallery-shell{position:fixed;z-index:40;inset:0;display:flex;flex-direction:column;gap:16px;padding:20px 16px max(24px,env(safe-area-inset-bottom));background:var(--workshop-bg);color:var(--workshop-ink);overflow:auto}.workshop-gallery-shell[hidden]{display:none!important}.workshop-gallery-content{display:grid;gap:10px}.workshop-gallery-status{margin:0;padding:16px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-muted);line-height:1.5}.workshop-gallery-list{display:grid;gap:10px;margin:0;padding:0;list-style:none}.workshop-patch-row{padding:14px 16px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-md);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm)}.workshop-patch-name{font-weight:720;overflow-wrap:anywhere}.workshop-patch-meta{margin-top:4px;color:var(--workshop-muted);font-size:13px}.workshop-patch-save{min-height:44px;margin-top:10px;padding:0 16px;border:0;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:700;transition:transform 120ms ease-out,filter 160ms ease-out}.workshop-patch-save:active{transform:scale(.98)}.workshop-gallery-shell .workshop-secondary-action{align-self:flex-start;min-height:48px;padding:0 12px;border:0;background:transparent;color:var(--workshop-primary);font-weight:700}
.workshop-settings-menu{display:grid;gap:10px;margin-top:4px}.workshop-menu-item{position:relative;display:flex;align-items:center;flex-wrap:wrap;gap:2px 12px;width:100%;min-height:60px;padding:10px 16px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-md);background:var(--workshop-surface);color:var(--workshop-ink);text-align:left;box-shadow:var(--workshop-shadow-sm);transition:transform 120ms ease-out,background-color 160ms ease-out,border-color 160ms ease-out}.workshop-menu-item:active{transform:scale(.985);background:var(--workshop-surface-2)}.workshop-menu-item:disabled{opacity:.6}.workshop-menu-item-label{font-weight:750;font-size:15px}.workshop-menu-item-desc{width:100%;margin-top:2px;color:var(--workshop-muted);font-size:12px;line-height:1.4}.workshop-menu-item-arrow{margin-left:auto;color:var(--workshop-muted);font-size:20px;font-weight:500}.workshop-menu-item.workshop-menu-active{border-color:var(--workshop-primary);background:var(--workshop-primary-soft)}.workshop-menu-item.workshop-menu-active .workshop-menu-item-arrow{color:var(--workshop-primary);transform:rotate(90deg)}.workshop-menu-item.workshop-menu-active .workshop-menu-item-label{color:var(--workshop-primary)}.workshop-settings-menu-hint{margin:2px 4px 0;padding:10px 12px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface-2);color:var(--workshop-muted);font-size:13px;line-height:1.5}.workshop-settings-menu-hint[hidden]{display:none!important}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}"""

# Task shell runtime: source React controls stay mounted and are activated via
# bubbling events. The runtime owns only the visible state-driven shell.
WORKSHOP_RUNTIME = r"""
;(()=>{const ID="workshop-runtime";let shell=null,runtimeRoot=null,settingsShell=null,settingsOpen=false,settingsRestored=false,sourceDialog=null,installedDialog=null,installedApps=[],installedLoading=false,installedError="",installedListEpoch=0,sourceRequestEpoch=0,installedBusy=false,previousSourceFocus=null,modalHistoryArmed=false,modalHistoryClosing=false,modalHistoryRearm=false,nativeBackEnabled=false,nativeBackPending=false,sourceButton=null,startButton=null,installButton=null,reactApiInput=null,pendingApiKey=null,observer=null,debounceTimer=0,lastSnapshot="",manualIdle=false,retrying=false,detailsOpen=false;
function textNode(tag,cls,text){const el=document.createElement(tag);el.className=cls;if(text!==undefined)el.textContent=text;return el}
function setReactInputValue(input,value){if(!input)return;input.focus();const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")?.set;if(setter)setter.call(input,value);else input.value=value;input.dispatchEvent(new Event("input",{bubbles:true}));input.dispatchEvent(new Event("change",{bubbles:true}));input.blur()}
function findReactApiInput(){return[...document.querySelectorAll("#root input")].find(el=>!el.closest(".workshop-settings-shell")&&(el.type==="password"||/api.?key/i.test(el.placeholder||el.getAttribute("aria-label")||"")))}
function applyApiKeyToReact(){const input=findReactApiInput();if(!input)return false;reactApiInput=input;if(pendingApiKey!==null&&input.value!==pendingApiKey)setReactInputValue(input,pendingApiKey);if(!input.__slgKeyHooked){input.__slgKeyHooked=true;input.addEventListener('input',()=>{pendingApiKey=input.value;try{const p=readSettingsPrefs();p.apiKey=input.value;saveSettingsPrefs(p)}catch{}})}return true}
const SETTINGS_KEY="slg-workshop-settings-v1";
const PROVIDERS={
  openai:{label:"OpenAI",models:[
    ["gpt-4o-mini","GPT-4o-mini（推荐）"],
    ["gpt-4o","GPT-4o"],
    ["gpt-4-turbo","GPT-4 Turbo"],
    ["gpt-3.5-turbo","GPT-3.5 Turbo"]
  ]},
  deepseek:{label:"DeepSeek",models:[
    ["deepseek-v4-flash","DeepSeek V4 Flash（推荐）"],
    ["deepseek-v4-pro","DeepSeek V4 Pro"]
  ]},
  custom:{label:"自定义接口",models:[]}
};
function defaultSettingsPrefs(){
  return{providerId:"openai",model:"gpt-4o-mini",customBaseURL:"",customModel:""};
}
function readSettingsPrefs(){
  try{
    const value=JSON.parse(localStorage.getItem(SETTINGS_KEY)||"null");
    if(!value||!PROVIDERS[value.providerId])return defaultSettingsPrefs();
    return{...defaultSettingsPrefs(),...value};
  }catch{return defaultSettingsPrefs()}
}
function saveSettingsPrefs(prefs){
  localStorage.setItem(SETTINGS_KEY,JSON.stringify(prefs));
}
function findReactConfigControls(){
  const root=document.querySelector("#root");
  const selects=[...(root?.querySelectorAll("select")||[])].filter(el=>!el.closest(".workshop-settings-shell"));
  const provider=selects.find(el=>["openai","deepseek","custom"].every(value=>[...el.options].some(option=>option.value===value)));
  const model=selects.find(el=>el!==provider&&[...el.options].some(option=>/^(gpt-|deepseek-|custom$)/.test(option.value)));
  const customBaseURL=[...(root?.querySelectorAll("input")||[])].find(el=>!el.closest(".workshop-settings-shell")&&el.placeholder==="https://your-api.com/v1");
  return{provider,model,customBaseURL,apiKey:findReactApiInput()};
}
function setReactSelectValue(select,value){
  if(!select)return false;
  if(![...select.options].some(option=>option.value===value)){
    const option=document.createElement("option");option.value=value;option.textContent=value;select.append(option);
  }
  const setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value")?.set;
  setter?setter.call(select,value):select.value=value;
  select.dispatchEvent(new Event("input",{bubbles:true}));
  select.dispatchEvent(new Event("change",{bubbles:true}));
  return true;
}
function applySettingsToReact(prefs){
  const first=findReactConfigControls();
  if(!setReactSelectValue(first.provider,prefs.providerId))return false;
  window.setTimeout(()=>{
    const controls=findReactConfigControls();
    const model=prefs.providerId==="custom"?prefs.customModel:prefs.model;
    setReactSelectValue(controls.model,model);
    if(prefs.providerId==="custom")setReactInputValue(controls.customBaseURL,prefs.customBaseURL);
    applyApiKeyToReact();
  },0);
  return true;
}
function fieldShell(id,label){
  const field=textNode("label","workshop-settings-field");
  field.htmlFor=id;field.append(textNode("span","",label));return field;
}
function inputControl(id,label,type,value,placeholder){
  const field=fieldShell(id,label),input=document.createElement("input");
  input.id=id;input.className="workshop-settings-input";input.type=type;
  input.value=value||"";input.placeholder=placeholder||"";input.autocomplete="off";
  field.append(input);return{field,input};
}
function selectControl(id,label,options,value){
  const field=fieldShell(id,label),select=document.createElement("select");
  select.id=id;select.className="workshop-settings-input";
  for(const [optionValue,optionLabel] of options){
    const option=document.createElement("option");option.value=optionValue;
    option.textContent=optionLabel;select.append(option);
  }
  select.value=value;field.append(select);return{field,select};
}
function replaceSelectOptions(select,options,value){
  select.replaceChildren();
  for(const [optionValue,optionLabel] of options){
    const option=document.createElement("option");option.value=optionValue;
    option.textContent=optionLabel;select.append(option);
  }
  select.value=options.some(([id])=>id===value)?value:options[0]?.[0]||"";
}
function closeSettings(preserveHistory=false){settingsOpen=false;manualIdle=false;lastSnapshot="";if(settingsShell)settingsShell.hidden=true;if(shell)shell.hidden=false;const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes(settingsPrevNav||"首页"))?.setAttribute("aria-current","page")}if(!preserveHistory)releaseModalHistory();refresh()}
function openSettings(){armModalHistory();settingsOpen=true;manualIdle=true;reactApiInput=reactApiInput||findReactApiInput();if(!settingsPrevNav){const nav=document.querySelector(".workshop-bottom-nav");settingsPrevNav=nav?.querySelector("button[aria-current=page]")?.textContent||"首页"}const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes("我的"))?.setAttribute("aria-current","page")}let menuView=null,serviceView=null,savesView=null,cleanupView=null,aboutView=null;const showMenu=()=>{if(menuView)menuView.hidden=false;if(serviceView)serviceView.hidden=true;if(savesView)savesView.hidden=true;if(cleanupView)cleanupView.hidden=true;if(aboutView)aboutView.hidden=true};const showView=(v)=>{if(!menuView)return;menuView.hidden=true;serviceView.hidden=v!==serviceView;savesView.hidden=v!==savesView;cleanupView.hidden=v!==cleanupView;aboutView.hidden=v!==aboutView};if(!settingsShell){settingsShell=document.createElement("section");settingsShell.className="workshop-settings-shell";settingsShell.setAttribute("role","dialog");settingsShell.setAttribute("aria-modal","true");settingsShell.setAttribute("aria-label","我的设置");function makeView(){const v=textNode("section","workshop-settings-view");v.hidden=true;return v}function viewBack(label,handler){const b=textNode("button","workshop-task-back","‹ 返回");b.type="button";b.setAttribute("aria-label",label);b.onclick=handler;return b}menuView=makeView();serviceView=makeView();savesView=makeView();cleanupView=makeView();aboutView=makeView();const menuTop=textNode("header","workshop-task-topbar");const back=viewBack("返回任务",closeSettings);menuTop.append(back,textNode("h1","","我的设置"));const menu=textNode("div","workshop-settings-menu");function makeMenuItem(label,desc){const row=textNode("button","workshop-menu-item");row.type="button";const name=textNode("span","workshop-menu-item-label",label);const note=textNode("span","workshop-menu-item-desc",desc||"");const arrow=textNode("span","workshop-menu-item-arrow","›");row.append(name,note,arrow);return row}const service=makeMenuItem("翻译服务","配置 AI 供应商与 API Key");const saves=makeMenuItem("存档转移","备份与恢复游戏存档");const cleanup=makeMenuItem("清理安装包与旧缓存","释放手机存储空间");cleanup.classList.add("workshop-settings-cleanup");const about=makeMenuItem("关于","版本信息");menu.append(service,saves,cleanup,about);menuView.append(menuTop,menu);
const serviceTop=textNode("header","workshop-task-topbar");const serviceBack=viewBack("返回菜单",showMenu);serviceTop.append(serviceBack,textNode("h1","","翻译服务"));const card=textNode("section","workshop-settings-card");const prefs=readSettingsPrefs();const title=textNode("h2","workshop-settings-title","翻译服务");const provider=selectControl("settingsProvider","供应商",[["openai","OpenAI"],["deepseek","DeepSeek"],["custom","自定义接口"]],prefs.providerId);provider.id="settingsProvider";let option=provider.select.options[1];option.value="deepseek";option=provider.select.options[2];option.value="custom";const model=selectControl("settingsModel","模型",PROVIDERS[prefs.providerId].models,prefs.model);model.id="settingsModel";const customWrap=textNode("div","workshop-settings-conditional");const customBaseURL=inputControl("settingsCustomBaseURL","自定义 Base URL","url",prefs.customBaseURL,"https://your-api.com/v1");customBaseURL.id="settingsCustomBaseURL";const customModel=inputControl("settingsCustomModel","自定义模型名","text",prefs.customModel,"例如：qwen-plus");customModel.id="settingsCustomModel";customWrap.append(customBaseURL.field,customModel.field);const api=inputControl("settingsApiKey","API Key","password",reactApiInput?.value??pendingApiKey??"","");const label=api.field;label.htmlFor="settingsApiKey";const input=api.input;input.id="settingsApiKey";const error=textNode("p","workshop-settings-error");error.hidden=true;const save=textNode("button","workshop-settings-save","保存");save.type="button";const helper=textNode("p","workshop-settings-status workshop-settings-helper","API Key 仅保存在本机。");const updateProvider=()=>{const providerId=provider.select.value;replaceSelectOptions(model.select,PROVIDERS[providerId].models,providerId===prefs.providerId?prefs.model:"");customWrap.hidden=providerId!=="custom";error.hidden=true};provider.select.onchange=updateProvider;customWrap.hidden=prefs.providerId!=="custom";save.onclick=()=>{const next={providerId:provider.select.value,model:model.select.value,customBaseURL:customBaseURL.input.value.trim(),customModel:customModel.input.value.trim()};if(next.providerId==="custom"&&(!next.customBaseURL||!next.customModel)){error.textContent="请填写自定义 Base URL 和模型名";error.hidden=false;return}error.hidden=true;pendingApiKey=input.value;saveSettingsPrefs(next);applySettingsToReact(next);helper.textContent=`已保存：${PROVIDERS[next.providerId].label} · ${next.providerId==="custom"?next.customModel:next.model}`};card.append(title,provider.field,model.field,customWrap,api.field,error,save,helper);serviceView.append(serviceTop,card);
const savesTop=textNode("header","workshop-task-topbar");const savesBack=viewBack("返回菜单",showMenu);savesTop.append(savesBack,textNode("h1","","存档转移"));const savesCard=textNode("section","workshop-settings-card");savesCard.append(textNode("h2","workshop-settings-title","存档转移"),textNode("p","workshop-settings-helper","存档转移功能即将推出，敬请期待。"));savesView.append(savesTop,savesCard);
const cleanupTop=textNode("header","workshop-task-topbar");const cleanupBack=viewBack("返回菜单",showMenu);cleanupTop.append(cleanupBack,textNode("h1","","清理安装包与旧缓存"));const cleanupCard=textNode("section","workshop-settings-card");const cleanupTitle=textNode("h2","workshop-settings-title","清理安装包与旧缓存");const cleanupStatus=textNode("p","workshop-settings-status","删除已生成的补丁 APK 与旧翻译缓存，释放手机存储空间。");const cleanupBtn=textNode("button","workshop-settings-save","立即清理");cleanupBtn.type="button";const cleanupResult=textNode("p","workshop-settings-status");cleanupBtn.onclick=async()=>{cleanupBtn.disabled=true;cleanupBtn.textContent="正在清理…";try{const r=await window.Capacitor.Plugins.FileManager.cleanupStorage({keepUri:(window.__slgSelectionMeta?.uri)||""});cleanupResult.textContent=`已清理 ${formatBytes(r&&r.freedBytes)} ，删除 ${(r&&r.deletedCount)||0} 个文件`}catch(e){cleanupResult.textContent="清理失败："+(e&&e.message||String(e))}finally{cleanupBtn.disabled=false;cleanupBtn.textContent="立即清理"}};cleanupCard.append(cleanupTitle,cleanupStatus,cleanupBtn,cleanupResult);cleanupView.append(cleanupTop,cleanupCard);
const aboutTop=textNode("header","workshop-task-topbar");const aboutBack=viewBack("返回菜单",showMenu);aboutTop.append(aboutBack,textNode("h1","","关于"));const aboutCard=textNode("section","workshop-settings-card");aboutCard.append(textNode("h2","workshop-settings-title","SLG 翻译器"),textNode("p","workshop-settings-helper","版本：Android v1.0.2"),textNode("p","workshop-settings-helper","把喜欢的游戏，用中文继续。"));aboutView.append(aboutTop,aboutCard);
service.onclick=()=>showView(serviceView);saves.onclick=()=>showView(savesView);cleanup.onclick=()=>showView(cleanupView);about.onclick=()=>showView(aboutView);settingsShell.append(menuView,serviceView,savesView,cleanupView,aboutView);runtimeRoot?.append(settingsShell)}showMenu();settingsShell.hidden=false;if(shell)shell.hidden=true}
function armModalHistory(){if(modalHistoryClosing){modalHistoryRearm=true;return}if(modalHistoryArmed)return;try{history.pushState({...history.state,__slgSourceModal:ID},"")}catch(e){}modalHistoryArmed=true}
function releaseModalHistory(){if(!modalHistoryArmed)return;modalHistoryArmed=false;modalHistoryClosing=true;history.back()}
function focusableIn(dialog){return[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled])')].filter(el=>!el.hidden)}
function trapModalFocus(event,dialog){if(event.key!=="Tab")return;const items=focusableIn(dialog);if(!items.length)return;const first=items[0],last=items.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
function focusInstalledTarget(){window.requestAnimationFrame(()=>{if(!installedDialog||installedDialog.hidden)return;const search=installedDialog.querySelector(".workshop-installed-search"),first=installedDialog.querySelector(".workshop-installed-content button");(search||first)?.focus()})}
function closeSourceChooser(preserveHistory=false){if(sourceDialog)sourceDialog.hidden=true;if(!preserveHistory)releaseModalHistory();previousSourceFocus?.focus()}
function openSourceChooser(){manualIdle=false;lastSnapshot="";previousSourceFocus=document.activeElement;try{armModalHistory()}catch(e){}if(!sourceDialog){sourceDialog=textNode("section","workshop-source-dialog");sourceDialog.hidden=true;sourceDialog.setAttribute("role","dialog");sourceDialog.setAttribute("aria-modal","true");sourceDialog.setAttribute("aria-labelledby","workshop-source-title");const panel=textNode("div","workshop-modal-panel");const title=textNode("h2","workshop-modal-title","选择来源");title.id="workshop-source-title";const copy=textNode("p","workshop-modal-copy","可以从手机里的应用开始，也可以选择一个 APK 文件。");const installed=actionButton("从已安装应用选择",()=>{closeSourceChooser(true);openInstalledApps()});installed.className="workshop-source-option";const file=actionButton("从文件选择 APK",()=>{closeSourceChooser();triggerReactButton(sourceButton)});file.className="workshop-source-option";const cancel=actionButton("取消",closeSourceChooser,true);cancel.className="workshop-modal-action";panel.append(title,copy,installed,file,cancel);sourceDialog.append(panel);sourceDialog.onclick=event=>{if(event.target===sourceDialog)closeSourceChooser()};sourceDialog.onkeydown=event=>{if(event.key==="Escape"){event.preventDefault();closeSourceChooser()}else trapModalFocus(event,sourceDialog)};runtimeRoot?.append(sourceDialog)}sourceDialog.hidden=false;if(modalHistoryClosing){modalHistoryClosing=false;modalHistoryRearm=false}window.requestAnimationFrame(()=>{try{focusableIn(sourceDialog)[0]?.focus()}catch{}})}
function filterInstalledApps(apps,query){const needle=(query||"").trim().toLocaleLowerCase();if(!needle)return apps;return apps.filter(app=>`${app.label||""}\n${app.packageName||""}`.toLocaleLowerCase().includes(needle))}
function renderInstalledApps(){if(!installedDialog)return;installedDialog.setAttribute("aria-busy",String(installedLoading||installedBusy));const list=installedDialog.querySelector(".workshop-installed-content"),search=installedDialog.querySelector(".workshop-installed-search"),cancel=installedDialog.querySelector(".workshop-modal-panel > .workshop-modal-action");if(cancel)cancel.disabled=installedBusy;if(!list)return;list.replaceChildren();if(installedLoading){list.append(textNode("p","workshop-installed-status","正在读取应用列表"));focusInstalledTarget();return}if(installedError){const message=textNode("p","workshop-installed-status workshop-installed-error",`应用列表读取失败：${installedError}`);const retry=actionButton("重新加载",loadInstalledApps);retry.className="workshop-source-option";retry.disabled=installedBusy;const file=actionButton("从文件选择 APK",()=>{closeInstalledApps();triggerReactButton(sourceButton)},true);file.className="workshop-modal-action";file.disabled=installedBusy;list.append(message,retry,file);focusInstalledTarget();return}if(installedBusy)list.append(textNode("p","workshop-installed-status","正在读取应用安装包…"));const visible=filterInstalledApps(installedApps,search?.value||"");if(!visible.length){const empty=textNode("p","workshop-installed-status","没有找到可选择的已安装应用。你仍可从文件选择 APK。");const file=actionButton("从文件选择 APK",()=>{closeInstalledApps();triggerReactButton(sourceButton)},true);file.className="workshop-modal-action";file.disabled=installedBusy;list.append(empty,file);focusInstalledTarget();return}const rows=textNode("ul","workshop-app-list");for(const app of visible){const item=textNode("li","");const button=textNode("button","workshop-app-row");button.type="button";button.disabled=installedBusy;button.append(textNode("span","workshop-app-label",app.label||app.packageName),textNode("span","workshop-app-package",app.packageName));button.onclick=()=>chooseInstalledApp(app);item.append(button);rows.append(item)}list.append(rows);focusInstalledTarget()}
async function loadInstalledApps(){const epoch=++installedListEpoch;installedLoading=true;installedError="";renderInstalledApps();try{const result=await window.Capacitor.Plugins.FileManager.listInstalledApps();if(epoch!==installedListEpoch||!installedDialog||installedDialog.hidden)return;installedApps=Array.isArray(result?.apps)?result.apps:[]}catch(error){if(epoch!==installedListEpoch||!installedDialog||installedDialog.hidden)return;installedError=error?.message||String(error)}finally{if(epoch===installedListEpoch&&installedDialog&&!installedDialog.hidden){installedLoading=false;renderInstalledApps()}}}
async function openInstalledApps(){previousSourceFocus=previousSourceFocus||document.activeElement;armModalHistory();if(!installedDialog){installedDialog=textNode("section","workshop-installed-dialog");installedDialog.hidden=true;installedDialog.setAttribute("role","dialog");installedDialog.setAttribute("aria-modal","true");installedDialog.setAttribute("aria-labelledby","workshop-installed-title");const panel=textNode("div","workshop-modal-panel");const title=textNode("h2","workshop-modal-title","从已安装应用选择");title.id="workshop-installed-title";const search=document.createElement("input");search.className="workshop-installed-search";search.type="search";search.placeholder="搜索应用名称或包名";search.setAttribute("aria-label","搜索应用名称或包名");search.oninput=renderInstalledApps;const content=textNode("div","workshop-installed-content");const cancel=actionButton("取消",closeInstalledApps,true);cancel.className="workshop-modal-action";panel.append(title,search,content,cancel);installedDialog.append(panel);installedDialog.onclick=event=>{if(event.target===installedDialog)closeInstalledApps()};installedDialog.onkeydown=event=>{if(event.key==="Escape"){event.preventDefault();closeInstalledApps()}else trapModalFocus(event,installedDialog)};runtimeRoot?.append(installedDialog)}installedDialog.hidden=false;installedDialog.querySelector(".workshop-installed-search").value="";focusInstalledTarget();await loadInstalledApps()}
async function chooseInstalledApp(app){const epoch=++sourceRequestEpoch;installedBusy=true;installedError="";renderInstalledApps();try{const selection=await window.Capacitor.Plugins.FileManager.selectInstalledApp({packageName:app.packageName});if(epoch!==sourceRequestEpoch||!installedDialog||installedDialog.hidden)return;installedBusy=false;closeInstalledApps(false,true);sourceRequestEpoch+=1;await window.__slgLoadSelectedApk(selection)}catch(error){if(epoch!==sourceRequestEpoch||!installedDialog||installedDialog.hidden)return;installedError=error?.message||String(error);renderInstalledApps()}finally{if(epoch===sourceRequestEpoch&&installedDialog&&!installedDialog.hidden){installedBusy=false;renderInstalledApps();focusInstalledTarget()}}}
function closeInstalledApps(preserveHistory=false,preserveSourceRequest=false){installedListEpoch+=1;if(!preserveSourceRequest)sourceRequestEpoch+=1;installedLoading=false;installedBusy=false;if(installedDialog){installedDialog.hidden=true;installedDialog.setAttribute("aria-busy","false")}if(!preserveHistory)releaseModalHistory();previousSourceFocus?.focus()}
function findButton(label){return[...document.querySelectorAll("#root button")].find(el=>!el.closest(".workshop-task-shell")&&el.textContent&&el.textContent.includes(label))}
function triggerReactButton(button){manualIdle=false;const isStart=button===startButton||button?.textContent?.includes("\u5f00\u59cb\u7ffb\u8bd1");if(isStart){try{const raw=localStorage.getItem(SESSION_KEY);if(raw){const ss=JSON.parse(raw);ss.translating=true;ss.savedAt=Date.now();localStorage.setItem(SESSION_KEY,JSON.stringify(ss))}}catch{}}const isInstall=button===installButton||button?.textContent?.includes("安装补丁版");const target=isStart?(findButton("开始翻译")||button):isInstall?findButton("安装补丁版"):button;if(isInstall&&!target){installButton=null;lastSnapshot="";refresh();return}if(isStart&&target?.disabled){const snap=readTaskSnapshot();setWorkshopState("ready",{...snap,apiRequired:true});return}target?.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,view:window}))}
function sourceText(){const root=document.querySelector("#root");if(!root)return"";const clone=root.cloneNode(true);clone.querySelector(".workshop-task-shell")?.remove();clone.querySelector(".workshop-bottom-nav")?.remove();return clone.textContent||""}
function readProgressLog(){const source=[...document.querySelectorAll("#root details")].find(el=>!el.closest(".workshop-task-shell")&&el.querySelector('[class*="font-mono"]'));const panel=source?.querySelector('[class*="font-mono"]');const lines=[...(panel?.children||[])].slice(-40).map(row=>(row.innerText||row.textContent||"").trim()).filter(Boolean);return{raw:lines.join("\n"),latest:lines.at(-1)||""}}
function readTaskSnapshot(){const selectionError=window.__slgSelectionError;if(selectionError)return{state:"failed",reason:"scan",fileName:selectionError.fileName||"",raw:selectionError.message};const watchdog=window.__slgScanWatchdog,selectionMeta=window.__slgSelectionMeta,text=sourceText();const selected=text.match(/已选择\s*[:：]?\s*([^\n]{1,180}?)(?=发现|正在|处理|$)/);const fileName=selected?.[1]?.trim()||"";const found=text.match(/发现\s*(\d+)\s*个可翻译文件/),headerCount=text.match(/(?:·\s*)?(\d+)\s*个脚本/);const count=found?.[1]||headerCount?.[1]||"";const progress=text.match(/正在处理脚本\s*(\d+)\s*\/\s*(\d+)/);const current=progress?.[1]||"0",total=progress?.[2]||count||"0";const translated=text.match(/共翻译\s*(\d+)\s*条文本/)?.[1]||"";const log=readProgressLog();const failed=[...document.querySelectorAll("#root *")].find(el=>!el.closest(".workshop-task-shell")&&el.textContent?.includes("写入补丁 APK 失败"));if(failed&&/ENOSPC|No space left/i.test(failed.textContent||""))return{state:"failed",reason:"space",raw:failed.textContent};const networkFailed=text.match(/翻译失败\s*[:：]?\s*(无法连接 (?:DeepSeek|OpenAI|自定义接口)。请检查网络，或前往“我的”切换供应商。)/);if(networkFailed)return{state:"failed",reason:"network",raw:networkFailed[1]};if(/翻译完成/.test(text))return{state:"completed",fileName,count,translated,raw:log.raw,latest:log.latest};if(/正在生成 Ren'Py 补丁 APK/.test(text))return{state:"patching",fileName,count,current,total,raw:log.raw,latest:log.latest};if(/正在处理脚本|翻译中|开始处理/.test(text))return{state:"translating",fileName,count,current,total,raw:log.raw,latest:log.latest};if(count==="0"&&watchdog?.epoch===window.__slgSelectionEpoch&&watchdog.settled&&!watchdog.timerFired)return{state:"empty",fileName,count,splitApk:!!selectionMeta?.splitApk,splitCount:selectionMeta?.splitCount||0};if(count!==""&&count!=="0")return{state:"ready",fileName,count};if(fileName||/正在扫描|正在检查文件|检查文件/.test(text))return{state:"scanning",fileName};return{state:"idle"}}
function detailToggle(raw,live=false){const wrap=textNode("div","workshop-detail-wrap");const toggle=textNode("button","workshop-detail-toggle",detailsOpen?"收起详情":"处理详情");toggle.type="button";toggle.setAttribute("aria-expanded",String(detailsOpen));const body=textNode("div","workshop-detail-body",raw||"暂无更多信息");body.dataset.open=String(detailsOpen);const scrollLatest=()=>{if(live&&detailsOpen)window.requestAnimationFrame(()=>{body.scrollTop=body.scrollHeight})};toggle.onclick=()=>{detailsOpen=!detailsOpen;body.dataset.open=String(detailsOpen);toggle.setAttribute("aria-expanded",String(detailsOpen));toggle.textContent=detailsOpen?"收起详情":"处理详情";scrollLatest()};wrap.append(toggle,body);scrollLatest();return wrap}
 function renderTopbar(state){const bar=textNode("header","workshop-task-topbar");const label=state==="scanning"?"读取中":state==="empty"?"无文本":state==="ready"?"已就绪":state==="translating"?"翻译中":state==="patching"?"生成中":state==="completed"?"已完成":state==="failed"?"失败":"";if(state!=="idle"){const back=textNode("button","workshop-task-back","‹ 返回");back.type="button";back.setAttribute("aria-label","返回");back.onclick=()=>setWorkshopState("idle",{fromBack:true});bar.append(back)}bar.append(textNode("h1","","APK 翻译"),textNode("span","workshop-topbar-state",label));return bar}
function fileRow(fileName){const row=textNode("div","workshop-file-row");row.append(textNode("span","workshop-file-icon","APK"));const copy=textNode("div","workshop-file-copy");copy.append(textNode("div","workshop-file-name",fileName||"尚未选择 APK"),textNode("div","workshop-file-meta",fileName?"已选择文件":"支持 Android APK 文件"));row.append(copy);return row}
function actionButton(label,handler,secondary){const button=textNode("button",secondary?"workshop-secondary-action":"workshop-primary-action",label);button.type="button";button.onclick=handler;return button}
function renderStateBody(state,payload){const body=textNode("div","workshop-task-body");if(state==="idle"){const brand=textNode("section","workshop-brand-panel");brand.append(textNode("p","","今天翻译什么？"),textNode("h2","","让喜欢的故事，用中文继续。"));const card=textNode("section","workshop-task-card");card.append(fileRow(""),textNode("p","workshop-state-copy","选择一个应用或 APK，开始你的中文旅程。"),actionButton("选择应用或 APK",openSourceChooser));body.append(brand,card);return body}
const card=textNode("section",state==="failed"?"workshop-task-card workshop-error-card":"workshop-task-card");card.append(fileRow(payload.fileName));if(state==="scanning"){card.append(textNode("p","workshop-state-copy","正在检查文件"));const progress=textNode("div","workshop-progress");progress.append(textNode("i","",""));card.append(progress,detailToggle(payload.raw||"正在检查 APK 文件，请稍候。"));body.append(card);return body}
if(state==="empty"){const split=payload.splitApk;card.append(textNode("h2","workshop-empty-title",split?"该应用使用拆分安装包":"没有找到可翻译文本"),textNode("p","workshop-state-copy",split?`当前只检查了基础 APK（共 ${payload.splitCount||0} 个拆分包），部分文本资源无法直接读取。可以尝试单体 APK 文件或其他应用。`:"这个应用的基础 APK 中没有可直接翻译的文本资源，可以尝试其他应用或 APK 文件。"));body.append(card,actionButton("重新选择应用或 APK",openSourceChooser));return body}
if(state==="ready"){card.append(textNode("p","workshop-state-copy","可以开始了"));card.append(textNode("p","workshop-settings-status","提示：继续上次只翻译新增文本（推荐）；全部重译会重新调用翻译接口。"));if(payload.apiRequired)card.append(textNode("p","workshop-state-copy","请先配置 API Key"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","可翻译文件"),textNode("span","",`${payload.count||0} 个`));list.append(row);card.append(list,detailToggle(payload.raw||"文件检查已完成。"));body.append(card,actionButton("开始翻译",()=>triggerReactButton(startButton)));return body}
if(state==="translating"){card.append(textNode("p","workshop-state-copy","正在翻译文本"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","脚本进度"),textNode("span","",`${payload.current||0} / ${payload.total||payload.count||0}`));list.append(row);const progress=textNode("div","workshop-progress");const fill=textNode("i","","");const current=Number(payload.current)||0,total=Number(payload.total)||0;fill.style.width=`${total?Math.max(6,Math.min(100,Math.round(current/total*100))):20}%`;progress.append(fill);card.append(list,progress);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"正在翻译脚本文本，请保持应用在前台。",true));body.append(card);return body}
if(state==="patching"){card.append(textNode("p","workshop-state-copy","正在生成补丁 APK"));const progress=textNode("div","workshop-progress");progress.append(textNode("i","",""));card.append(progress);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"译文已经完成，正在写入并签名补丁 APK。",true));body.append(card);return body}
if(state==="completed"){card.append(textNode("p","workshop-state-copy","补丁 APK 已生成"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","已翻译文本"),textNode("span","",`${payload.translated||0} 条`));list.append(row);card.append(list);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"翻译和补丁写入已经完成。",true));body.append(card,actionButton("安装补丁版",()=>triggerReactButton(installButton)));return body}
if(payload.reason==="scan"){const title=textNode("h2","workshop-error-title","检查失败");const copy=textNode("p","workshop-state-copy","无法读取这个 APK。请重新选择应用或文件。");card.append(title,copy,detailToggle(payload.raw||"APK scan failed"));body.append(card,actionButton("重新选择 APK",openSourceChooser));return body}
if(payload.reason==="network"){const title=textNode("h2","workshop-error-title","无法连接翻译服务");const copy=textNode("p","workshop-state-copy",payload.raw||"请检查网络，或切换翻译供应商后重试。");card.append(title,copy,detailToggle(payload.raw||"Network failure"));body.append(card,actionButton("前往“我的”切换供应商",openSettings),actionButton("重试翻译",()=>retryTask({fileName:payload.fileName,raw:""}),true));return body}
const title=textNode("h2","workshop-error-title","手机空间不足");const copy=textNode("p","workshop-state-copy","请释放空间后重试。"),details=detailToggle(payload.raw||"ENOSPC|No space left");card.append(title,copy,details);body.append(card,actionButton("释放空间后重试",()=>retryTask({fileName:payload.fileName,raw:""})),actionButton("重新选择 APK",()=>triggerReactButton(sourceButton),true));return body}
function setWorkshopState(state,payload={}){if(!shell)return;shell.dataset.workshopState=state;shell.setAttribute("data-workshop-state",state);shell.dataset.workshopTask=state==="idle"?"idle":"active";const task=shell.dataset.workshopTask;shell.setAttribute("data-workshop-task",shell.dataset.workshopTask);runtimeRoot?.setAttribute("data-workshop-state",state);runtimeRoot?.setAttribute("data-workshop-task",task);shell.classList.remove("workshop-state-idle","workshop-state-scanning","workshop-state-empty","workshop-state-ready","workshop-state-translating","workshop-state-patching","workshop-state-completed","workshop-state-failed");shell.classList.add(`workshop-state-${state}`);runtimeRoot?.classList.remove("workshop-state-idle","workshop-state-scanning","workshop-state-empty","workshop-state-ready","workshop-state-translating","workshop-state-patching","workshop-state-completed","workshop-state-failed");runtimeRoot?.classList.add(`workshop-state-${state}`);shell.replaceChildren(renderTopbar(state),renderStateBody(state,payload))}
function snapshotKey(s){return[s.state,s.fileName||"",s.count||"",s.current||"",s.total||"",s.translated||"",s.reason||"",s.splitApk?`split-${s.splitCount||0}`:"",s.raw||""].join("|")}
function retryTask(payload){retrying=true;triggerReactButton(startButton||sourceButton);setWorkshopState("scanning",payload);window.setTimeout(()=>{retrying=false;refresh()},600)}
function refresh(){if(!shell||retrying||settingsOpen)return;const snap=readTaskSnapshot();const active=snap.state==='scanning'||snap.state==='translating'||snap.state==='patching'||snap.state==='completed'||snap.state==='failed';if(manualIdle&&!active)return;if(snap.state==='translating'){try{const now=Date.now();if(now-sessionLastBeat>=10000){sessionLastBeat=now;const raw=localStorage.getItem(SESSION_KEY);if(raw){const ss=JSON.parse(raw);ss.translating=true;ss.savedAt=now;localStorage.setItem(SESSION_KEY,JSON.stringify(ss))}}}catch{}}const key=snapshotKey(snap);if(key===lastSnapshot)return;lastSnapshot=key;setWorkshopState(snap.state,snap)}
 function decorate(){const heading=[...document.querySelectorAll("#root h2")].find(el=>el.textContent&&el.textContent.includes("选择游戏 APK"));if(heading?.parentElement)heading.parentElement.classList.add("workshop-picker-source");startButton=findButton("开始翻译");if(startButton){startButton.classList.add("workshop-start-button");startButton.setAttribute("aria-hidden","true")}installButton=findButton("安装补丁版");if(installButton)installButton.setAttribute("aria-hidden","true");sourceButton=findButton("选择");if(sourceButton){sourceButton.classList.add("workshop-source-button");sourceButton.setAttribute("aria-label","选择 APK 文件");sourceButton.setAttribute("aria-hidden","true")}applyApiKeyToReact()}

function formatBytes(bytes){const value=Number(bytes)||0;if(value<1024)return`${value} B`;const units=["KB","MB","GB"];let n=value/1024,unit=0;while(n>=1024&&unit<units.length-1){n/=1024;unit+=1}return`${n>=100?Math.round(n):Math.round(n*10)/10} ${units[unit]}`}
function openGallery(){armModalHistory();galleryOpen=true;manualIdle=true;if(!galleryPrevNav){const nav0=document.querySelector(".workshop-bottom-nav");galleryPrevNav=nav0?.querySelector("button[aria-current=page]")?.textContent||"首页"}const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes("\u5b89\u88c5\u5305"))?.setAttribute("aria-current","page")}if(!galleryShell){galleryShell=textNode("section","workshop-gallery-shell");galleryShell.hidden=true;galleryShell.setAttribute("role","dialog");galleryShell.setAttribute("aria-modal","true");galleryShell.setAttribute("aria-label","\u6211\u7684\u8865\u4e01");const top=textNode("header","workshop-task-topbar");const back=textNode("button","workshop-task-back","\u2039 \u8fd4\u56de");back.type="button";back.setAttribute("aria-label","\u8fd4\u56de\u4efb\u52a1");back.onclick=closeGallery;top.append(back,textNode("h1","","\u6211\u7684\u8865\u4e01"));const refresh=textNode("button","workshop-secondary-action","\u5237\u65b0");refresh.type="button";refresh.onclick=loadPatches;const list=textNode("div","workshop-gallery-content");galleryShell.append(top,list,refresh);runtimeRoot?.append(galleryShell)}galleryShell.hidden=false;if(shell)shell.hidden=true;loadPatches()}
function closeGallery(preserveHistory=false){galleryOpen=false;manualIdle=false;lastSnapshot="";if(galleryShell)galleryShell.hidden=true;if(shell)shell.hidden=false;const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes(galleryPrevNav||"首页"))?.setAttribute("aria-current","page")}if(!preserveHistory)releaseModalHistory();refresh()}
function renderGallery(){if(!galleryShell)return;const list=galleryShell.querySelector(".workshop-gallery-content");if(!list)return;list.replaceChildren();if(galleryLoading){list.append(textNode("p","workshop-gallery-status","\u6b63\u5728\u8bfb\u53d6\u8865\u4e01\u5217\u8868\u2026"));return}if(galleryError){list.append(textNode("p","workshop-gallery-status workshop-installed-error","\u8bfb\u53d6\u5931\u8d25\uff1a"+galleryError));return}if(!galleryPatches.length){list.append(textNode("p","workshop-gallery-status","\u8fd8\u6ca1\u6709\u8865\u4e01 APK\u3002\u7ffb\u8bd1\u5b8c\u6210\u540e\uff0c\u8865\u4e01\u4f1a\u81ea\u52a8\u51fa\u73b0\u5728\u8fd9\u91cc\u3002"));return}const rows=textNode("ul","workshop-gallery-list");for(const patch of galleryPatches){const item=textNode("li","");const card=textNode("div","workshop-patch-row");card.append(textNode("div","workshop-patch-name",patch.name||"\u672a\u547d\u540d\u8865\u4e01"));card.append(textNode("div","workshop-patch-meta",`${formatBytes(patch.size)} \u00b7 ${new Date(patch.modifiedAt||Date.now()).toLocaleString()}`));const save=actionButton("\u4fdd\u5b58\u5230\u4e0b\u8f7d",()=>savePatchedApk(patch.path));save.className="workshop-patch-save";card.append(save);item.append(card);rows.append(item)}list.append(rows)}
async function loadPatches(){const plugin=window.Capacitor?.Plugins?.FileManager;galleryLoading=true;galleryError="";renderGallery();if(!plugin?.listPatchedApks){galleryLoading=false;galleryError="\u5f53\u524d\u7248\u672c\u4e0d\u652f\u6301\u8bfb\u53d6\u8865\u4e01\u5217\u8868\uff0c\u8bf7\u5347\u7ea7\u5e94\u7528";renderGallery();return}try{const result=await plugin.listPatchedApks();galleryPatches=Array.isArray(result?.patches)?result.patches:[]}catch(error){galleryError=error?.message||String(error)}finally{galleryLoading=false;renderGallery()}}
function enableNativeBackHandling(){if(nativeBackEnabled||nativeBackPending)return;const plugin=window.Capacitor?.Plugins?.FileManager;if(!plugin?.enableWorkshopBackHandling)return;nativeBackPending=true;Promise.resolve(plugin.enableWorkshopBackHandling()).then(()=>{nativeBackEnabled=true}).catch(()=>{}).finally(()=>{nativeBackPending=false})}
function mount(){decorate();enableNativeBackHandling();if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;const app=document.querySelector("#root>div");if(!app||!sourceButton)return;runtimeRoot=app;if(!shell){app.classList.add(ID);shell=document.createElement("section");shell.className="workshop-task-shell";shell.dataset.workshopState="idle";shell.dataset.workshopTask="idle";app.prepend(shell);const nav=document.createElement("nav");nav.className="workshop-bottom-nav";nav.setAttribute("aria-label","主导航");[["首页",()=>window.scrollTo({top:0,behavior:"smooth"})],["安装包",openGallery],["我的",openSettings]].forEach(([label,action],index)=>{const button=textNode("button","workshop-touch",label);button.type="button";if(index===0)button.setAttribute("aria-current","page");button.onclick=()=>{[...nav.children].forEach(el=>el.removeAttribute("aria-current"));button.setAttribute("aria-current","page");action()};nav.append(button)});app.append(nav);setWorkshopState("idle",{})}refresh()}
function handleWorkshopPopState(){if(modalHistoryClosing){modalHistoryClosing=false;if(modalHistoryRearm){modalHistoryRearm=false;armModalHistory()}return}if(installedDialog&&!installedDialog.hidden){modalHistoryArmed=false;closeInstalledApps(true);return}if(sourceDialog&&!sourceDialog.hidden){modalHistoryArmed=false;closeSourceChooser(true);return}if(settingsOpen){modalHistoryArmed=false;closeSettings(true);return}if(galleryOpen){modalHistoryArmed=false;closeGallery(true);return}if(shell?.dataset.workshopTask==="active"){manualIdle=true;setWorkshopState("idle",{fromBack:true})}}
function schedule(){clearTimeout(debounceTimer);debounceTimer=setTimeout(mount,120)}
window.__slgHandleAndroidBack=()=>{if(installedDialog&&!installedDialog.hidden){closeInstalledApps();return true}if(sourceDialog&&!sourceDialog.hidden){closeSourceChooser();return true}if(settingsOpen){closeSettings();return true}if(galleryOpen){closeGallery();return true}return false};
document.addEventListener("click",event=>{if(event.target.closest?.(".workshop-task-back"))manualIdle=true},{capture:true});observer=new MutationObserver(schedule);observer.observe(document.querySelector("#root")||document.documentElement,{childList:true,subtree:true,characterData:true});window.addEventListener("popstate",handleWorkshopPopState);document.readyState==="loading"?document.addEventListener("DOMContentLoaded",mount):mount()})();
"""


def patch_scan_flow(js: str) -> str:
    old = """xe=async()=>{try{let e=await E.pickApkFile();r(e.uri),a(e.uri.split(`/`).pop()||`Unknown.apk`),s([]),fe(null),w([]),d(!0),O(`正在扫描 APK 中的文本文件...`,`info`);let t=await E.listApkEntries({uri:e.uri});s(t.entries);try{let t=await Promise.race([E.getApkPackageName({uri:e.uri}),new Promise(e=>setTimeout(()=>e({packageName:``}),3e3))]);t.packageName&&(p(t.packageName),O(`识别到包名: `+t.packageName,`info`))}catch{}let n=Jo(t.entries,c,g),i=Oe(n),o=Object.entries(i).map(([e,t])=>`${ds[e]||e}×${t}`).join(`, `);O(`共发现 ${n.length} 个可翻译文件（${o||`默认仅 Ren'Py`}）`,`success`),d(!1)}catch(e){e.message!==`User cancelled`&&O(`选择文件失败: ${e.message}`,`error`),d(!1)}}"""
    new = """function withTimeout(promise,timeoutMs,message){let timer;return new Promise((resolve,reject)=>{timer=setTimeout(()=>reject(new Error(message)),timeoutMs);Promise.resolve(promise).then(resolve,reject)}).finally(()=>clearTimeout(timer))}loadSelectedApk=window.__slgLoadSelectedApk=async e=>{let selectionEpoch=window.__slgSelectionEpoch=(window.__slgSelectionEpoch||0)+1;try{window.__slgSelectionError=null,window.__slgSelectionMeta=e,r(e.uri),a(e.name||e.label||e.uri.split(`/`).pop()||`Unknown.apk`),p(e.packageName||``),s([]),fe(null),he.current=[],w([]),d(!0),O(e.source===`installed`?`正在读取已安装应用的 APK...`:`正在扫描 APK 中的文本文件...`,`info`),e.splitApk&&O(`该应用使用拆分安装包（${e.splitCount||0} 个拆分包），当前先扫描基础 APK，部分资源可能无法读取。`,`info`);let t=await withTimeout(E.listApkEntries({uri:e.uri}),window.__slgScanTimeoutMs||65000,`APK 检查超时，请重新选择应用或文件。`);if(selectionEpoch!==window.__slgSelectionEpoch)return;if(e.splitApk&&t.entries.length===0)throw new Error(`该应用使用拆分安装包，基础 APK 中没有可翻译文件。请改用“从文件选择 APK”。`);s(t.entries),O(`APK 检查${t.cacheHit?`（缓存）`:``}用时 ${Math.max(0,Math.round((t.scanDurationMs||0)/100)/10)} 秒`,`info`);try{let n=e.packageName?{packageName:e.packageName}:t.packageName?{packageName:t.packageName}:await Promise.race([E.getApkPackageName({uri:e.uri}),new Promise(e=>setTimeout(()=>e({packageName:``}),3e3))]);if(selectionEpoch!==window.__slgSelectionEpoch)return;n.packageName&&(p(n.packageName),O(`识别到包名: `+n.packageName,`info`))}catch{}if(selectionEpoch!==window.__slgSelectionEpoch)return;let n=Jo(t.entries,c,g),i=Oe(n),o=Object.entries(i).map(([e,t])=>`${ds[e]||e}×${t}`).join(`, `);if(window.__slgRenpyMenuType===`renpy`){try{let _m=await E.injectTranslatorMenu({apkUri:e.uri,gameTargetLang:window.__slgRenpyLang||'',translatorLang:'slgtranslated'});window.__slgTranslatorLang=(_m&&_m.ready)?'slgtranslated':''}catch{window.__slgTranslatorLang=''}}O(`共发现 ${n.length} 个可翻译文件（${o||`默认仅 Ren'Py`}）`,`success`),d(!1)}catch(t){if(selectionEpoch!==window.__slgSelectionEpoch)return;t.message!==`User cancelled`&&(window.__slgSelectionError={message:t.message,fileName:e.name||e.label||``},O(`选择文件失败: ${t.message}`,`error`)),d(!1);throw t}},xe=async()=>{try{await loadSelectedApk(await E.pickApkFile())}catch(e){e.message!==`User cancelled`&&!window.__slgSelectionError&&(window.__slgSelectionError={message:e.message,fileName:``},O(`选择文件失败: ${e.message}`,`error`)),d(!1)}}"""
    new = new.replace(
        "function withTimeout(promise,timeoutMs,message){",
        "withTimeout=(promise,timeoutMs,message)=>{",
        1,
    ).replace(
        ")}loadSelectedApk=window.__slgLoadSelectedApk=",
        ")},loadSelectedApk=window.__slgLoadSelectedApk=",
        1,
    )
    new = new.replace(
        "withTimeout=(promise,timeoutMs,message)=>{let timer;return new Promise((resolve,reject)=>{"
        "timer=setTimeout(()=>reject(new Error(message)),timeoutMs);"
        "Promise.resolve(promise).then(resolve,reject)}).finally(()=>clearTimeout(timer))},",
        "withTimeout=(promiseFactory,timeoutMs,message,onTimeout,watchdog)=>{let timer,finished=false;"
        "return new Promise((resolve,reject)=>{timer=window.setTimeout(()=>{if(finished)return;"
        "let error=new Error(message);watchdog.timerFired=true;onTimeout(error);reject(error)},timeoutMs);"
        "Promise.resolve().then(promiseFactory).then(resolve,reject)}).finally(()=>{finished=true;"
        "watchdog.settled=true;window.clearTimeout(timer)})},",
        1,
    )
    loader_marker = "loadSelectedApk=window.__slgLoadSelectedApk=async e=>"
    loader_start = new.index(loader_marker)
    loader_end = new.index(",xe=async()=>", loader_start)
    loader = new[loader_start + len(loader_marker) : loader_end]
    body_start = loader.index("try{") + len("try{")
    body_end = loader.index("}catch(t){", body_start)
    scan_body = loader[body_start:body_end]
    nested_deadline_start = scan_body.index("await withTimeout(E.listApkEntries")
    nested_deadline_end = scan_body.index(";if(selectionEpoch", nested_deadline_start)
    scan_body = (
        scan_body[:nested_deadline_start]
        + "await E.listApkEntries({uri:e.uri})"
        + scan_body[nested_deadline_end:]
    )
    timeout_message = "APK 检查超时，请重新选择应用或文件。"
    deadline_loader = (
        "scanTimeoutMs=window.__slgScanTimeoutMs??=65000,"
        "scanSelectedApk=async(e,selectionEpoch)=>{" + scan_body + "},"
        "loadSelectedApk=window.__slgLoadSelectedApk=e=>{"
        "let selectionEpoch=window.__slgSelectionEpoch=(window.__slgSelectionEpoch||0)+1;"
        "let watchdog=window.__slgScanWatchdog={epoch:selectionEpoch,"
        "deadlineAt:Date.now()+window.__slgScanTimeoutMs,timerFired:false,settled:false,applied:false};"
        "return withTimeout(()=>selectionEpoch===window.__slgSelectionEpoch?"
        "scanSelectedApk(e,selectionEpoch):undefined,window.__slgScanTimeoutMs,`"
        + timeout_message
        + "`,timeoutError=>{if(selectionEpoch!==window.__slgSelectionEpoch)return;watchdog.applied=true;"
        "window.__slgSelectionEpoch=selectionEpoch+1;"
        "timeoutError.message!==`User cancelled`&&(window.__slgSelectionError={message:timeoutError.message,fileName:e.name||e.label||``},"
        "O(`选择文件失败: ${timeoutError.message}`,`error`)),d(!1)},watchdog).catch(t=>{"
        "if(watchdog.timerFired){if(watchdog.applied)throw t;return}"
        "if(selectionEpoch!==window.__slgSelectionEpoch)return;"
        "t.message!==`User cancelled`&&(window.__slgSelectionError={message:t.message,fileName:e.name||e.label||``},"
        "O(`选择文件失败: ${t.message}`,`error`)),d(!1);throw t})}"
    )
    new = new[:loader_start] + deadline_loader + new[loader_end:]
    session_save = "loadSelectedApk=window.__slgLoadSelectedApk=e=>{"
    session_replacement = (
        "loadSelectedApk=window.__slgLoadSelectedApk=e=>{"
        "try{globalThis.localStorage?.setItem('slg-workshop-session-v1',"
        "JSON.stringify({uri:e.uri,name:e.name||e.label,packageName:e.packageName||'',source:e.source||'',savedAt:Date.now(),translating:false}))}catch{}"
    )
    if new.count(session_save) != 1:
        raise ValueError("Session persistence signature not found")
    new = new.replace(session_save, session_replacement, 1)

    lang_stash_old = 's(t.entries),O(`APK '
    lang_stash_new = ('window.__slgRenpyLanguages=t.renpyLanguages||[],'
                      'window.__slgRenpyMenuType=t.renpyMenuType||`none`,window.__slgTranslatorLang=\'\',' 
                      'window.__slgRenpyLang=t.renpyMenuType===`renpy`?([`chinese`,`schinese`,`zh-cn`,`zh-hans`,`zh-tw`,`zh`,`zh-hant`,`tchinese`,`simplified-chinese`,`simplified_chinese`,`traditional_chinese`].find(c=>(t.renpyLanguages||[]).includes(c))||``):``,'
                      's(t.entries),O(`APK ')
    if new.count(lang_stash_old) != 1:
        raise ValueError("Language stash signature not found")
    new = new.replace(lang_stash_old, lang_stash_new, 1)
    if js.count(old) != 1:
        raise ValueError("APK picker flow signature not found")
    return js.replace(old, new, 1)


def enhance_runtime(runtime: str) -> str:
    runtime = runtime.replace(
        "manualIdle=false,retrying=false,detailsOpen=false;\nfunction textNode",
        "manualIdle=false,retrying=false,detailsOpen=false,scanStartedAt=0,scanTimer=0;\nfunction textNode",
        1,
    )
    runtime = runtime.replace(
        "function setReactInputValue(input,value)",
        """function updateScanClock(){const elapsed=shell?.querySelector(\".workshop-scan-elapsed\");if(elapsed&&scanStartedAt)elapsed.textContent=`已用时 ${Math.floor((Date.now()-scanStartedAt)/1000)} 秒`}
function startScanClock(){if(!scanStartedAt)scanStartedAt=Date.now();if(!scanTimer)scanTimer=window.setInterval(updateScanClock,1000);window.setTimeout(updateScanClock,0)}
function stopScanClock(){if(scanTimer)window.clearInterval(scanTimer);scanTimer=0;scanStartedAt=0}
function setReactInputValue(input,value)""",
        1,
    )
    runtime = runtime.replace(
        'if(failed&&/ENOSPC|No space left/i.test(failed.textContent||""))',
        'const scanFailed=[...document.querySelectorAll("#root *")].find(el=>!el.closest(".workshop-task-shell")&&el.textContent?.includes("选择文件失败:")&&(el.textContent?.length||0)<500);if(scanFailed)return{state:"failed",reason:"scan",raw:scanFailed.textContent};if(failed&&/ENOSPC|No space left/i.test(failed.textContent||""))',
        1,
    )
    runtime, count = re.subn(
        r'if\(state==="scanning"\)\{card\.append\(textNode\("p","workshop-state-copy","[^"]*"\)\);const progress=',
        'if(state==="scanning"){const copy=textNode("p","workshop-state-copy","正在读取 APK 目录");copy.append(textNode("span","workshop-scan-elapsed","已用时 0 秒"));card.append(copy);const progress=',
        runtime,
        count=1,
    )
    if count != 1:
        raise ValueError("Scanning state signature not found")
    runtime = runtime.replace(
        "function setWorkshopState(state,payload={}){if(!shell)return;",
        'function setWorkshopState(state,payload={}){if(!shell)return;if(state==="translating"||state==="patching"){try{navigator.wakeLock?.request("screen").then(w=>{globalThis.__slgWakeLock=w}).catch(()=>{})}catch{}}else if(globalThis.__slgWakeLock){try{globalThis.__slgWakeLock.release().catch(()=>{})}catch{}globalThis.__slgWakeLock=null}state==="scanning"?startScanClock():stopScanClock();',
        1,
    )
    runtime = runtime.replace(
        'return{state:"completed",fileName,count,translated,raw:log.raw,latest:log.latest};',
        'return{state:"completed",fileName,count,translated,raw:log.raw,latest:log.latest,installAvailable:!!installButton?.isConnected};',
        1,
    )
    runtime, count = re.subn(
        r'body\.append\(card,actionButton\("([^"]+)",\(\)=>triggerReactButton\(installButton\)\)\);return body\}',
        r'body.append(card);if(payload.installAvailable)body.append(actionButton("\1",()=>triggerReactButton(installButton)));return body}',
        runtime,
        count=1,
    )
    if count != 1:
        raise ValueError("Completed install action signature not found")
    runtime = runtime.replace(
        's.reason||"",s.splitApk?`split-${s.splitCount||0}`:"",s.raw||""',
        's.reason||"",s.installAvailable?"install":"",s.sessionRestoredAt?`restored-${s.sessionRestoredAt}`:"",s.splitApk?`split-${s.splitCount||0}`:"",s.raw||""',
        1,
    )
    # --- session auto-resume (renderer-crash recovery) ---
    session_state_old = "manualIdle=false,retrying=false,detailsOpen=false,scanStartedAt=0,scanTimer=0;"
    session_state_new = "manualIdle=false,retrying=false,detailsOpen=false,scanStartedAt=0,scanTimer=0,sessionRestoredAt=0,sessionLastBeat=0,manualIdleBeforeOverlay=false,restoringSession=false,galleryShell=null,galleryOpen=false,galleryPatches=[],galleryLoading=false,galleryError='';"
    if runtime.count(session_state_old) != 1:
        raise ValueError("Session state signature not found")
    runtime = runtime.replace(session_state_old, session_state_new, 1)

    session_key_old = 'const SETTINGS_KEY="slg-workshop-settings-v1";'
    session_key_new = 'const SETTINGS_KEY="slg-workshop-settings-v1";const SESSION_KEY="slg-workshop-session-v1";'
    if runtime.count(session_key_old) != 1:
        raise ValueError("Session key signature not found")
    runtime = runtime.replace(session_key_old, session_key_new, 1)

    save_key_old = "pendingApiKey=input.value;saveSettingsPrefs(next);"
    save_key_new = "pendingApiKey=input.value;next.apiKey=input.value;saveSettingsPrefs(next);"
    if runtime.count(save_key_old) != 1:
        raise ValueError("API key save signature not found")
    runtime = runtime.replace(save_key_old, save_key_new, 1)

    apply_prefs_old = "function applySettingsToReact(prefs){"
    apply_prefs_new = "function applySettingsToReact(prefs){if(prefs?.apiKey)pendingApiKey=prefs.apiKey;"
    if runtime.count(apply_prefs_old) != 1:
        raise ValueError("Apply settings signature not found")
    runtime = runtime.replace(apply_prefs_old, apply_prefs_new, 1)

    mount_old = "function mount(){decorate();enableNativeBackHandling();if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;"
    mount_new = (
        "function restoreSession(){if(restoringSession||window.__slgSelectionMeta)return;let raw=null;try{raw=localStorage.getItem(SESSION_KEY)}catch{}"
        "if(!raw)return;let s=null;try{s=JSON.parse(raw)}catch{}if(!s||!s.uri)return;restoringSession=true;"
        "Promise.resolve(window.__slgLoadSelectedApk?.({uri:s.uri,name:s.name||s.label||\"\",packageName:s.packageName||\"\",source:s.source||\"installed\",splitApk:false,splitCount:0}))"
        ".catch(()=>{}).finally(()=>{restoringSession=false;if(s.translating)sessionRestoredAt=s.savedAt||Date.now();refresh()})}\n"
        "function recoveryBanner(savedAt){const wrap=textNode(\"section\",\"workshop-task-card\");"
        "wrap.append(textNode(\"h2\",\"workshop-settings-title\",\"" "\u4e0a\u6b21\u7ffb\u8bd1\u4e2d\u65ad" "\"),"
        "textNode(\"p\",\"workshop-state-copy\",\"" "\u7ffb\u8bd1\u4f1a\u8bdd\u56e0\u9875\u9762\u5237\u65b0\u4e2d\u65ad\uff0c\u5df2\u5b8c\u6210\u5185\u5bb9\u5df2\u4fdd\u5b58\u5728\u672c\u673a\u7f13\u5b58\u4e2d\u3002" "\"),"
        "textNode(\"p\",\"workshop-state-copy\",`" "\u4e2d\u65ad\u65f6\u95f4\uff1a" "${new Date(savedAt).toLocaleTimeString()}`));"
        "const resume=actionButton(\"" "\u7ee7\u7eed\u4e0a\u6b21\u7ffb\u8bd1" "\",()=>triggerReactButton(startButton));"
        "const dismiss=textNode(\"button\",\"workshop-secondary-action\",\"" "\u653e\u5f03\u6062\u590d" "\");dismiss.type=\"button\";"
        "dismiss.onclick=()=>{try{localStorage.removeItem(SESSION_KEY)}catch{}sessionRestoredAt=0;refresh()};"
        "wrap.append(resume,dismiss);return wrap}\n"
        "function mount(){const _prefs=readSettingsPrefs();if(_prefs.apiKey)pendingApiKey=_prefs.apiKey;"
        "decorate();enableNativeBackHandling();if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;restoreSession();"
    )
    if runtime.count(mount_old) != 1:
        raise ValueError("Mount signature not found")
    runtime = runtime.replace(mount_old, mount_new, 1)

    ready_payload_old = 'return{state:"ready",fileName,count};'
    ready_payload_new = 'return{state:"ready",fileName,count,sessionRestoredAt};'
    if runtime.count(ready_payload_old) != 1:
        raise ValueError("Ready payload signature not found")
    runtime = runtime.replace(ready_payload_old, ready_payload_new, 1)

    ready_banner_old = 'body.append(card,actionButton("\u5f00\u59cb\u7ffb\u8bd1",()=>triggerReactButton(startButton)));return body}'
    ready_banner_new = 'if(payload.sessionRestoredAt)body.append(recoveryBanner(payload.sessionRestoredAt));body.append(card,actionButton("\u5f00\u59cb\u7ffb\u8bd1",()=>triggerReactButton(startButton)));return body}'
    if runtime.count(ready_banner_old) != 1:
        raise ValueError("Ready banner signature not found")
    runtime = runtime.replace(ready_banner_old, ready_banner_new, 1)

    completed_old = 'if(state==="completed"){card.append(textNode("p","workshop-state-copy","\u8865\u4e01 APK \u5df2\u751f\u6210"));'
    completed_new = 'if(state==="completed"){try{localStorage.removeItem(SESSION_KEY)}catch{}sessionRestoredAt=0;card.append(textNode("p","workshop-state-copy","\u8865\u4e01 APK \u5df2\u751f\u6210"));'
    if runtime.count(completed_old) != 1:
        raise ValueError("Completed clear signature not found")
    runtime = runtime.replace(completed_old, completed_new, 1)

    # --- overlay idle-state preservation ---
    overlay_helpers = (
        'function beginOverlay(){manualIdleBeforeOverlay=manualIdle;manualIdle=true}'
        'function endOverlay(){manualIdle=manualIdleBeforeOverlay}\n'
    )
    settings_close_old = 'function closeSettings(preserveHistory=false){settingsOpen=false;manualIdle=false;lastSnapshot="";'
    settings_close_new = 'function closeSettings(preserveHistory=false){settingsOpen=false;endOverlay();lastSnapshot="";'
    if runtime.count(settings_close_old) != 1:
        raise ValueError("Settings close signature not found")
    runtime = runtime.replace(settings_close_old, overlay_helpers + settings_close_new, 1)
    settings_open_old = 'function openSettings(){armModalHistory();settingsOpen=true;manualIdle=true;'
    settings_open_new = 'function openSettings(){armModalHistory();beginOverlay();settingsOpen=true;'
    if runtime.count(settings_open_old) != 1:
        raise ValueError("Settings open signature not found")
    runtime = runtime.replace(settings_open_old, settings_open_new, 1)
    gallery_open_old = 'function openGallery(){armModalHistory();galleryOpen=true;manualIdle=true;'
    gallery_open_new = 'function openGallery(){armModalHistory();beginOverlay();galleryOpen=true;'
    if runtime.count(gallery_open_old) != 1:
        raise ValueError("Gallery open signature not found")
    runtime = runtime.replace(gallery_open_old, gallery_open_new, 1)
    gallery_close_old = 'function closeGallery(preserveHistory=false){galleryOpen=false;manualIdle=false;lastSnapshot="";'
    gallery_close_new = 'function closeGallery(preserveHistory=false){galleryOpen=false;endOverlay();lastSnapshot="";'
    if runtime.count(gallery_close_old) != 1:
        raise ValueError("Gallery close signature not found")
    runtime = runtime.replace(gallery_close_old, gallery_close_new, 1)

    # --- patched APK visibility & signature-conflict handling ---
    snap_old = 'if(/\u7ffb\u8bd1\u5b8c\u6210/.test(text))return{state:"completed",fileName,count,translated,raw:log.raw,latest:log.latest,installAvailable:!!installButton?.isConnected};'
    snap_new = (r'if(/\u7ffb\u8bd1\u5b8c\u6210/.test(text)){const patchedApkPath=(text.match(/\/[^\s]*patched-signed\.apk/)||[])[0]||"";'
                'return{state:"completed",fileName,count,translated,patchedApkPath,raw:log.raw,latest:log.latest,installAvailable:!!installButton?.isConnected}}')
    if runtime.count(snap_old) != 1:
        raise ValueError("Completed snapshot signature not found")
    runtime = runtime.replace(snap_old, snap_new, 1)

    branch_old = 'body.append(card);if(payload.installAvailable)body.append(actionButton("\u5b89\u88c5\u8865\u4e01\u7248",()=>triggerReactButton(installButton)));return body}'
    branch_new = (
        'if(payload.patchedApkPath)card.append(textNode("p","workshop-state-copy workshop-scan-elapsed","' + "\u4f4d\u7f6e\uff1a" + '"+payload.patchedApkPath));'
        'body.append(card);const actions=textNode("div","workshop-summary-list");'
        'if(payload.patchedApkPath)actions.append(actionButton("' + "\u4fdd\u5b58\u8865\u4e01 APK" + '",()=>savePatchedApk(payload.patchedApkPath)));'
        'if(payload.installAvailable){actions.append(actionButton("' + "\u5378\u8f7d\u539f\u7248\u5e76\u5b89\u88c5\u8865\u4e01\u7248" + '",()=>clickReact("' + "\u5378\u8f7d\u539f\u7248+\u5b89\u88c5\u8865\u4e01" + '")));'
        'actions.append(actionButton("' + "\u76f4\u63a5\u5b89\u88c5" + '",()=>triggerReactButton(installButton),true))}'
        'if(actions.children.length)body.append(actions);return body}'
    )
    if runtime.count(branch_old) != 1:
        raise ValueError("Completed branch signature not found")
    runtime = runtime.replace(branch_old, branch_new, 1)

    helpers_anchor = 'function mount(){const _prefs=readSettingsPrefs();'
    helpers_new = (
        'function clickReact(label){const b=findButton(label);if(b){b.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,view:window}));return true}return false}'
        'function savePatchedApk(path){const plugin=window.Capacitor?.Plugins?.FileManager;'
        'const host=galleryOpen&&galleryShell?galleryShell:shell;'
        'const status=textNode("p","workshop-live-line","' + "\u6b63\u5728\u4fdd\u5b58\u8865\u4e01 APK\uff08\u5927\u6587\u4ef6\u53ef\u80fd\u9700\u8981\u4e00\u70b9\u65f6\u95f4\uff09..." + '");host?.append(status);'
        'if(!plugin?.savePatchedApkToDownloads){status.textContent="' + "\u5f53\u524d\u7248\u672c\u4e0d\u652f\u6301\u4fdd\u5b58\u8865\u4e01 APK\uff0c\u8bf7\u5347\u7ea7\u5e94\u7528" + '";return}'
        'Promise.resolve(plugin.savePatchedApkToDownloads({path})).then(r=>{const name=(r&&r.path&&r.path.split("/").pop())||path.split("/").pop()||"";status.textContent="' + "\u5df2\u4fdd\u5b58\u5230 \u4e0b\u8f7d/SLG-Translator/" + '"+(name||"");if(galleryOpen)loadPatches()}).catch(e=>{status.textContent="' + "\u4fdd\u5b58\u5931\u8d25\uff1a" + '"+(e&&e.message||e)})}'
        'function mount(){const _prefs=readSettingsPrefs();'
    )
    if runtime.count(helpers_anchor) != 1:
        raise ValueError("Mount helpers anchor not found")
    runtime = runtime.replace(helpers_anchor, helpers_new, 1)


    # --- translation language guidance + task mode selector ---
    snap_guid_old = 'return{state:"completed",fileName,count,translated,patchedApkPath,raw:log.raw,latest:log.latest,installAvailable:!!installButton?.isConnected}}'
    snap_guid_new = ('return{state:"completed",fileName,count,translated,patchedApkPath,'
                     'renpyLang:window.__slgRenpyLang||\'\',renpyMenuType:window.__slgRenpyMenuType||\'\','
                     'raw:log.raw,latest:log.latest,installAvailable:!!installButton?.isConnected}}')
    if runtime.count(snap_guid_old) != 1:
        raise ValueError("Completed snapshot language signature not found")
    runtime = runtime.replace(snap_guid_old, snap_guid_new, 1)

    guide_anchor = 'if(payload.patchedApkPath)card.append(textNode("p","workshop-state-copy workshop-scan-elapsed","' + "\u4f4d\u7f6e\uff1a" + '"+payload.patchedApkPath));'
    guide_new = (
        guide_anchor
        + 'if(window.__slgTranslatorLang===`slgtranslated`)card.append(textNode("p","workshop-state-copy","' "\u5df2\u6dfb\u52a0\u72ec\u7acb\u7684\u300c\u7ffb\u8bd1\u6587\u672c\u300d\u5165\u53e3\uff0c\u8bf7\u5728\u6e38\u620f\u8bbe\u7f6e\u8bed\u8a00\u4e2d\u9009\u62e9\u300c\u7ffb\u8bd1\u6587\u672c\u300d\u67e5\u770b\u8bd1\u6587" '"));' + 'else if(payload.renpyLang)card.append(textNode("p","workshop-state-copy","' "\u8bd1\u6587\u8bed\u8a00\uff1a" '"+payload.renpyLang+"' "\u2014\u2014 \u5728\u6e38\u620f\u8bbe\u7f6e\u7684\u8bed\u8a00\u4e2d\u9009\u62e9\u5bf9\u5e94\u9009\u9879\u5373\u53ef\u67e5\u770b\u8bd1\u6587" '"));'
        + 'else if(payload.renpyMenuType==="custom")card.append(textNode("p","workshop-state-copy","' "\u6b64\u6e38\u620f\u4f7f\u7528\u81ea\u5b9a\u4e49\u8bed\u8a00\u7cfb\u7edf\uff0c\u8bd1\u6587\u53ef\u80fd\u65e0\u6cd5\u901a\u8fc7\u8bed\u8a00\u83dc\u5355\u9009\u62e9" '"));'
    )
    if runtime.count(guide_anchor) != 1:
        raise ValueError("Language guidance signature not found")
    runtime = runtime.replace(guide_anchor, guide_new, 1)

    mode_anchor = 'if(state==="ready"){card.append(textNode("p","workshop-state-copy","'
    # mode selector inserted right after the ready card opens (before ?????)
    mode_new = (
        'if(state==="ready"){const modes=textNode("div","workshop-summary-list");const _pkg=window.__slgSelectionMeta?.packageName||"";if(globalThis.__slgHasHistory&&globalThis.__slgHasHistory(_pkg)){'
        '["' "\u7ee7\u7eed\u4e0a\u6b21" '","' "\u626b\u63cf\u65b0\u589e" '","' "\u5168\u90e8\u91cd\u8bd1" '"].forEach(label=>{modes.append(actionButton(label,()=>clickReact(label),true))});}'
        'card.append(modes);card.append(textNode("p","workshop-state-copy","'
    )
    if runtime.count(mode_anchor) != 1:
        raise ValueError("Ready mode selector signature not found")
    runtime = runtime.replace(mode_anchor, mode_new, 1)

    runtime = runtime.replace(
        "card.append(textNode(\"p\",\"workshop-settings-status\",\"提示：继续上次只翻译新增文本（推荐）；全部重译会重新调用翻译接口。\"));",
        "if(globalThis.__slgHasHistory&&globalThis.__slgHasHistory(window.__slgSelectionMeta?.packageName||\"\"))card.append(textNode(\"p\",\"workshop-settings-status\",\"提示：继续上次只翻译新增文本（推荐）；全部重译会重新调用翻译接口。\"));",
        1,
    )
    runtime = runtime.replace(
        "window.__slgHandleAndroidBack=()=>{",
        "var settingsPrevNav=\"首页\",galleryPrevNav=\"首页\";globalThis.__slgSrcLang??=`en`;globalThis.__slgDstLang??=`zh`;window.__slgHandleAndroidBack=()=>{",
        1,
    )

    return runtime




def patch_translation_cache(js: str) -> str:
    old_state = 'var _o=`slg-translator-cache:`,vo={},yo=!1,bo=!1,bp=Promise.resolve();'
    new_state = 'var _o=`slg-translator-cache:`,vo={},cacheIndex={},yo=!1,bo=!1,bp=Promise.resolve();globalThis.__slgHasHistory=function(pkg){if(!pkg)return false;try{for(const[_k,_v]of Object.entries(vo)){if(_k.startsWith(`slg-file-v1:`)&&_v&&_v.pkg===pkg)return true}return false}catch{return false}};'
    if js.count(old_state) != 1:
        raise ValueError("Translation cache state signature not found")
    js = js.replace(old_state, new_state, 1)

    old_cache = (
        'async function Co(){if(!yo){try{let e=await E.loadTranslationCache();'
        'e.data&&e.data!==`{}`&&(vo=JSON.parse(e.data))}catch{vo={}}Do(),yo=!0}}'
        'async function wo()'
    )
    new_cache = r'''function cacheScopeIdentity(e){let t=e.indexOf(`|`),n=e.indexOf(`|`,t+1),r=e.lastIndexOf(`|`);return`${e.slice(0,t)}|${e.slice(t+1,n)}|${e.slice(r+1)}`}
function cacheIdentity(e,t){return`${cacheScopeIdentity(e)}|${U(t)}`}
function cacheV2Key(e,t){return _o+`v2|`+cacheIdentity(e,t)}
function rebuildCacheIndex(){cacheIndex={};for(const[e,t]of Object.entries(vo)){let n=null;if(e.startsWith(_o+`v2|`))n=e.slice((_o+`v2|`).length);else if(e.startsWith(_o)){let r=e.slice(_o.length),i=r.lastIndexOf(`|`);if(i>0){let e=cacheScopeIdentity(r.slice(0,i));n=`${e}|${r.slice(i+1)}`}}if(!n||!t?.sourceText||!t?.translatedText)continue;const r=cacheIndex[n];(!r||(t.updatedAt||0)>(r.updatedAt||0))&&(cacheIndex[n]=t)}}
async function Co(){if(!yo){try{let e=await E.loadTranslationCache();e.data&&e.data!==`{}`&&(vo=JSON.parse(e.data))}catch{vo={}}Do(),rebuildCacheIndex(),yo=!0}}
async function wo()'''
    if js.count(old_cache) != 1:
        raise ValueError("Translation cache loader signature not found")
    js = js.replace(old_cache, new_cache, 1)

    old_lookup = (
        'function To(e,t){let n=So(e,t),r=vo[n];return r&&r.sourceText===t?'
        'r.translatedText:null}function Eo(e,t,n){let r=So(e,t);vo[r]={sourceText:t,'
        'translatedText:n,updatedAt:Date.now()},bo=!0}'
    )
    new_lookup = (
        'function To(e,t){let n=cacheIdentity(e,t),r=vo[cacheV2Key(e,t)]||cacheIndex[n];'
        'return r&&r.sourceText===t?r.translatedText:null}'
        'function Eo(e,t,n){let i=cacheV2Key(e,t),a=vo[i];if(Object.prototype.hasOwnProperty.call(vo,i))'
        '{a?.sourceText===t&&a?.translatedText&&(cacheIndex[cacheIdentity(e,t)]=a);return}'
        'let r={sourceText:t,'
        'translatedText:n,updatedAt:Date.now()};vo[i]=r,cacheIndex[cacheIdentity(e,t)]=r,bo=!0}'
    )
    if js.count(old_lookup) != 1:
        raise ValueError("Translation cache lookup signature not found")
    return js.replace(old_lookup, new_lookup, 1)


def patch_translation_network(js: str) -> str:
    helpers_anchor = 'async function Lo(e){'
    helpers = r'''function isNetworkFailure(e){return networkFailureParts(e).some(e=>/^(?:APIConnectionError|Connection error\.?)$/i.test(e)||/\b(?:ERR_NETWORK|ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT)\b/i.test(e)||/\bnet::ERR_(?:CONNECTION_TIMED_OUT|CONNECTION_REFUSED|INTERNET_DISCONNECTED|NAME_NOT_RESOLVED|CONNECTION_RESET|TIMED_OUT)\b/i.test(e)||/\bDNS_PROBE_FINISHED_NXDOMAIN\b/i.test(e)||/^(?:failed(?: to |-to-)fetch|fetch failed)(?:\b|:)/i.test(e)||/\b(?:offline|dns(?: error| lookup failed)?|timed out|timeout)\b/i.test(e))}
function networkFailureParts(e){let t=[],n=e;for(let r=0;r<4&&n!=null;r++){if(typeof n===`object`){for(const e of[`name`,`code`,`message`])n[e]!=null&&t.push(String(n[e]));n=n.cause}else{t.push(String(n));break}}return t}
function providerLabel(e){return/deepseek/i.test(e)?`DeepSeek`:/openai/i.test(e)?`OpenAI`:`自定义接口`}
function isProviderNetworkFailure(e){return/^无法连接 (?:DeepSeek|OpenAI|自定义接口)。请检查网络，或前往“我的”切换供应商。$/.test(String(e||``))}
async function runFileTasksParallel(e,t,concurrency=2){let i=0,fatal=``;async function worker(){while(i<e.length&&!fatal){let j=i++,r=await t(e[j],j);if(r&&!fatal)fatal=r}}let ws=[];for(let k=0;k<Math.min(concurrency,e.length);k++)ws.push(worker());await Promise.all(ws);return fatal}
async function Lo(e){'''
    if js.count(helpers_anchor) != 1:
        raise ValueError("Translation coordinator signature not found")
    js = js.replace(helpers_anchor, helpers, 1)

    if js.count('timeout:3e4,maxRetries:2') != 1:
        raise ValueError("OpenAI retry signature not found")
    js = js.replace('timeout:3e4,maxRetries:2', 'timeout:3e4,maxRetries:1', 1)

    old_worker_catch = 'catch{v=!0,ee+=1}await wo(),x+=1'
    new_worker_catch = (
        'catch(e){v=!0,ee+=1,isNetworkFailure(e)&&(N=`无法连接 ${P}。'
        '请检查网络，或前往“我的”切换供应商。`,b=y.length)}await wo(),x+=1'
    )
    state_anchor = 'let _=new H({apiKey:a,baseURL:i,dangerouslyAllowBrowser:!0,timeout:3e4,maxRetries:1}),v=!1,y='
    state_replacement = 'let _=new H({apiKey:a,baseURL:i,dangerouslyAllowBrowser:!0,timeout:3e4,maxRetries:1}),v=!1,N="",P=providerLabel(i),y='
    if js.count(state_anchor) != 1 or js.count(old_worker_catch) != 1:
        raise ValueError("Translation worker signature not found")
    js = js.replace(state_anchor, state_replacement, 1)
    js = js.replace(old_worker_catch, new_worker_catch, 1)

    old_return = '...v?{error:`Translated ${d.size}/${t.length} items; some batches failed`}:{}'
    new_return = '...N?{error:N}:v?{error:`Translated ${d.size}/${t.length} items; some batches failed`}:{}'
    if js.count(old_return) != 1:
        raise ValueError("Translation result signature not found")
    js = js.replace(old_return, new_return, 1)

    old_split = 'async function Bo(e,t,n,r,i,a,o,s=0){try{return{translations:await Vo(e,t,n,r,i,a,o),splitCount:0,failedCount:0}}catch{'
    new_split = 'async function Bo(e,t,n,r,i,a,o,s=0){try{return{translations:await Vo(e,t,n,r,i,a,o),splitCount:0,failedCount:0}}catch(e){if(isNetworkFailure(e))throw e;'
    if js.count(old_split) != 1:
        raise ValueError("Recursive batch signature not found")
    js = js.replace(old_split, new_split, 1)

    # Source APK resilience: refresh the installed-app source to the persistent
    # directory before translating so a cleared cache cannot break patch builds.
    old_start = "Ce=async()=>{if(!n||ae.length===0||!te&&!oe)return;"
    new_start = (
        "Ce=async()=>{if(!n||ae.length===0||!te&&!oe)return;"
        "if(window.__slgSelectionMeta?.source===`installed`&&window.__slgSelectionMeta?.packageName){try{"
        "let _r=await E.selectInstalledApp({packageName:window.__slgSelectionMeta.packageName});"
        "_r?.uri&&(window.__slgSelectionMeta.uri=_r.uri)}"
        "catch(_e){O(`\u91cd\u65b0\u83b7\u53d6\u6e38\u620f\u5b89\u88c5\u5305\u5931\u8d25: ${_e&&_e.message||_e}`,\u0060error\u0060)}}"
    )
    if js.count(old_start) != 1:
        raise ValueError("Ce start signature not found")
    js = js.replace(old_start, new_start, 1)

    # Read and build from the refreshed meta uri when present.
    old_read = "E.readFileContent({uri:n,entryName:o.name})"
    new_read = (
        "o.fileType===`rpyc`?await E.readRenpyTexts({uri:(window.__slgSelectionMeta?.uri||n),entryName:o.name}):"
        "await E.readFileContent({uri:(window.__slgSelectionMeta?.uri||n),entryName:o.name})"
    )
    if js.count(old_read) != 1:
        raise ValueError("Read file uri signature not found")
    js = js.replace(old_read, new_read, 1)

    old_build = (
        "E.buildPatchedApk({uri:n,files:a,outputDirUri:m,outputName:Me(i),"
        "targetRenpyLanguage:is(y),sourceRenpyLanguage:is(g)}"
    )
    new_build = (
        "E.buildPatchedApk({uri:(window.__slgSelectionMeta?.uri||n),"
        "files:(()=>{const _f=a.filter(_x=>{let _p=String(_x.path);return !_p.includes(`/tl/`)&&!_p.includes(`x-slgtranslated`)});return _f.length?_f:[{path:'assets/slg-translator-marker.txt',content:''}]})(),"
        "outputDirUri:m,outputName:Me(i),"
        "targetRenpyLanguage:window.__slgCompiledCount>0?'':is(y),sourceRenpyLanguage:window.__slgCompiledCount>0?'':is(g)}"
    )
    if js.count(old_build) != 1:
        raise ValueError("Build uri signature not found")
    js = js.replace(old_build, new_build, 1)

    # Friendly error when the source APK was cleared by the system.
    old_fail = "catch(e){r=!0,O(`\u5199\u5165\u8865\u4e01 APK \u5931\u8d25: ${e.message}`,\u0060error\u0060)}"
    new_fail = (
        "catch(e){r=!0;let _m=e&&e.message||String(e);O("
        "/No such file|Failed to build patched APK|not found/i.test(_m)?"
        "`\u5199\u5165\u8865\u4e01 APK \u5931\u8d25\uff1a\u6e90 APK \u5df2\u88ab\u7cfb\u7edf\u6e05\u7406\uff0c\u8bf7\u91cd\u65b0\u9009\u62e9\u6e38\u620f\u540e\u91cd\u8bd5\uff08${_m}\uff09`:"
        "`\u5199\u5165\u8865\u4e01 APK \u5931\u8d25: ${_m}`,\u0060error\u0060)}"
    )
    if js.count(old_fail) != 1:
        raise ValueError("Build failure catch signature not found")
    js = js.replace(old_fail, new_fail, 1)

    outer_state = 'let e=x===`custom`?re:_e.find(e=>e.id===x)?.baseURL||``,t=0,r=!1,a=[],o=``,s=``,c=!1,l=!1;'
    outer_state_with_fatal = 'let e=x===`custom`?re:_e.find(e=>e.id===x)?.baseURL||``,t=0,r=!1,N="",a=[],o=``,s=``,c=!1,l=!1;'
    outer_start = 'for(let i=0;i<ae.length;i+=fs){let o=ae.slice(i,i+fs);await Promise.allSettled(o.map((o,s)=>(async()=>{let c=i+s,l='
    outer_start_sequential = 'N=await runFileTasksParallel(ae,async(o,c)=>{let l='
    outer_end = '})()))}if(a.length>0||oe){'
    outer_end_sequential = 'return N},2);if(!N&&(a.length>0||oe)){'
    if (
        js.count(outer_state) != 1
        or js.count(outer_start) != 1
        or js.count(outer_end) != 1
    ):
        raise ValueError("Translation file controller signature not found")
    js = js.replace(outer_state, outer_state_with_fatal, 1)
    js = js.replace(outer_start, outer_start_sequential, 1)
    js = js.replace(outer_end, outer_end_sequential, 1)

    # Compile the generated translation .rpy files into .rpyc before the APK
    # is assembled: Ren'Py only loads compiled scripts from an APK archive,
    # so plain .rpy files in the patch were never picked up by the game.
    build_gate = 'return N},2);if(!N&&(a.length>0||oe)){O(`\u6b63\u5728\u751f\u6210 Ren\'Py \u8865\u4e01 APK...`,`info`);try{let e=await E.buildPatchedApk'
    build_gate_compiled = (
        'return N},2);if(!N&&(a.length>0||oe)){(!N&&a.length)&&await E.compileTranslationsIntoApk('
        '{apkUri:(window.__slgSelectionMeta?.uri||n),items:a.map(_x=>({path:_x.path,content:_x.content}))}).then('
        '_r=>{window.__slgCompiledCount=_r&&_r.compiled>0?_r.compiled:0;(_r&&_r.compiled>0)?O(`  \u5df2\u7f16\u8bd1\u5e76\u5408\u5e76\u53bb\u91cd ${_r.compiled} \u6761\u8bd1\u6587\uff0c\u6e38\u620f\u5c06\u76f4\u63a5\u52a0\u8f7d\u7f16\u8bd1\u7248\u672c`,`success`):O(`  \u6ca1\u6709\u53ef\u7f16\u8bd1\u7684 Ren\'Py \u7ffb\u8bd1\u8d44\u6e90`,`info`)}).catch('
        '_e=>{O(`  \u7f16\u8bd1\u7ffb\u8bd1\u8d44\u6e90\u5931\u8d25: ${_e&&_e.message||_e}`,`error`)});'
        'O(`\u6b63\u5728\u751f\u6210 Ren\'Py \u8865\u4e01 APK...`,`info`);try{let e=await E.buildPatchedApk'
    )
    if js.count(build_gate) != 1:
        raise ValueError("Build gate signature not found")
    js = js.replace(build_gate, build_gate_compiled, 1)

    result_anchor = '}});if(p===0){'
    result_with_fatal = '}});if(m&&isProviderNetworkFailure(m)){N=m,r=!0,O(`  翻译失败: ${m}`,`error`),ue({current:c+1,total:ae.length});return N}if(p===0){'
    empty_return = 'r=!0,ue({current:c+1,total:ae.length});return}'
    empty_return_with_fatal = 'r=!0,ue({current:c+1,total:ae.length});return N}'
    if js.count(result_anchor) != 1 or js.count(empty_return) != 1:
        raise ValueError("Translation file result signature not found")
    js = js.replace(result_anchor, result_with_fatal, 1)
    js = js.replace(empty_return, empty_return_with_fatal, 1)

    final_error = '...r?{error:`部分文件处理失败，请查看日志`}:{}})'
    final_error_with_fatal = '...r?{error:N||`部分文件处理失败，请查看日志`}:{}})'
    if js.count(final_error) != 1:
        raise ValueError("Translation final result signature not found")
    js = js.replace(final_error, final_error_with_fatal, 1)

    # Stable file-cache key: use the package name so the cache survives
    # re-selecting the game (the APK uri changes on every copy).
    old_key = "let _fk=`slg-file-v1:${U([n,o.name,g,y,S].join(`|`))}`"
    new_key = "let _fk=`slg-file-v1:${U([window.__slgSelectionMeta?.packageName||n,o.name,g,y,S].join(`|`))}`"
    if js.count(old_key) != 1:
        raise ValueError("File cache key signature not found")
    js = js.replace(old_key, new_key, 1)

    # Resume regenerates .rpy outputs with the current language bucket instead
    # of replaying stale paths baked into old cache entries.
    old_resume = (
        "if(_mode===`resume`&&_fr&&Array.isArray(_fr.outputs)&&_fr.outputs.length){"
        "for(let e of _fr.outputs)await Ne(e.outputPath,e.content),a.push({path:e.outputPath,content:e.content});"
        "t+=_fr.count||0,O(`  \u5df2\u5b8c\u6210\u6587\u4ef6\uff0c\u590d\u7528 ${_fr.count||0} \u6761\u8bd1\u6587`,`success`),ue({current:c+1,total:ae.length});return}"
    )
    new_resume = (
        "if(_mode===`resume`&&_fr&&Array.isArray(_fr.translations)&&_fr.translations.length&&Array.isArray(_fr.texts)){"
        "let _map=new Map(),_tmap=new Map(_fr.translations);"
        "for(let r of _fr.texts){let v=_tmap.get(r.keyPath)||_tmap.get(r.text);if(v&&v.trim())_map.set(r.text,v)}"
        "let{content:_c,fileType:_ft}=o.fileType===`rpyc`?await E.readRenpyTexts({uri:(window.__slgSelectionMeta?.uri||n),entryName:o.name}):await E.readFileContent({uri:(window.__slgSelectionMeta?.uri||n),entryName:o.name});"
        "let l=ke(_c,_ft,``,g),_need=l.filter(t=>!t||!_map.has(t.text));"
        "if(_need.length){let _r=await Lo({texts:_need,sourceLang:g,targetLang:y,baseURL:e,apiKey:te,model:S,batchSize:ps,onProgress:()=>{}});if(_r&&_r.successCount>0){for(let t of _need){let v=_r.translations.get(t.keyPath)||_r.translations.get(t.text);if(v&&v.trim())_map.set(t.text,v)}O(`  \u8865\u5145\u7ffb\u8bd1 ${_r.successCount} \u6761\u65b0\u6587\u672c`,`success`)}}"
        "let _outs=[rs(o,l,_map,`None`),rs(o,l,_map,g)],_uniq=new Map;oe||_outs.unshift(rs(o,l,_map,y));"
        "for(let e of _outs)_uniq.set(e.outputPath,e);"
        "for(let e of _uniq.values())await Ne(e.outputPath,e.content),a.push({path:e.outputPath,content:e.content});"
        "vo[_fk]={texts:l,translations:Array.from(_map.entries()),count:l.length,updatedAt:Date.now(),pkg:window.__slgSelectionMeta?.packageName||``},bo=!0,await wo(),delete vo[_fk];"
        "t+=l.length,O(`  \u5df2\u5b8c\u6210\u6587\u4ef6\uff0c\u590d\u7528 ${l.length} \u6761\u8bd1\u6587`,`success`),ue({current:c+1,total:ae.length});return}"
    )
    if js.count(old_resume) != 1:
        raise ValueError("Resume regeneration signature not found")
    js = js.replace(old_resume, new_resume, 1)

    # Cache the raw translations + texts so resume can rebuild outputs.
    old_cache = "vo[_fk]={outputs:_fo,count:p,updatedAt:Date.now()}"
    new_cache = "vo[_fk]={texts:l,translations:Array.from(f.entries()),count:p,updatedAt:Date.now(),pkg:window.__slgSelectionMeta?.packageName||``}"
    if js.count(old_cache) != 1:
        raise ValueError("File cache write signature not found")
    js = js.replace(old_cache, new_cache, 1)
    return js


def patch_translation_memory(js: str) -> str:
    old_log = "he.current=[...he.current,n],w(he.current)}"
    new_log = (
        "he.current.push(n),he.current.length>400&&he.current.splice(0,"
        "he.current.length-400),w(he.current.slice())}"
    )
    if js.count(old_log) != 1:
        raise ValueError("Translation log state signature not found")
    js = js.replace(old_log, new_log, 1)

    old_save = (
        "async function wo(){if(!yo||!bo)return;let e=JSON.stringify(vo);"
        "bo=!1,bp=bp.then(()=>E.saveTranslationCache({data:e})).catch(()=>{bo=!0}),await bp}"
    )
    new_save = (
        "var _saveBusy=!1,_saveAgain=!1,_lastSaveAt=0;globalThis.__slgCacheDbg={calls:0,skipped:0,errors:0,lastError:null};"
        "async function wo(){globalThis.__slgCacheDbg.calls++;"
        "if(!yo){try{await Co()}catch(e){globalThis.__slgCacheDbg.lastError='co:'+(e&&e.message||e);"
        "O('  缓存加载失败: '+(e&&e.message||e),'error')}}"
        "if(!yo||!bo){globalThis.__slgCacheDbg.skipped++;return}"
        "globalThis.__slgCacheDbg.entries=Object.keys(vo).length;bo=!1;"
        "if(_saveBusy){_saveAgain=!0;return}do{_saveAgain=!1,_saveBusy=!0;"
        "let _snap={};for(const[_k,_v]of Object.entries(vo)){"
        "if(_k.startsWith(_o)||_k.startsWith(`slg-file-v1:`))_snap[_k]=_v}let _e=JSON.stringify(_snap);"
        "try{await E.saveTranslationCache({data:_e})}catch(e){bo=!0;globalThis.__slgCacheDbg.errors++;globalThis.__slgCacheDbg.lastError='save:'+(e&&e.message||e)}"
        "_saveBusy=!1,_lastSaveAt=Date.now();if(_saveAgain)await new Promise(r=>setTimeout(r,1500))}while(_saveAgain);"
        "for(let _pk of Object.keys(vo)){if(_pk.startsWith(`slg-file-v1:`))delete vo[_pk]}}"
    )
    if js.count(old_save) != 1:
        raise ValueError("Translation cache save signature not found")
    js = js.replace(old_save, new_save, 1)

    old_debug_log = (
        "try{s===`rpyc`&&console.log(JSON.stringify({rpycEntry:o.name,extracted:l.length,"
        "sample:l.slice(0,8).map(e=>e.text)}))}catch{}"
    )
    if js.count(old_debug_log) != 1:
        raise ValueError("Translation debug log signature not found")
    js = js.replace(old_debug_log, "", 1)

    old_is = "function is(e){return ts[e]||e}"
    new_is = "function is(e){if(e===`zh`){if(globalThis.__slgTranslatorLang)return globalThis.__slgTranslatorLang;if(globalThis.__slgRenpyLang)return globalThis.__slgRenpyLang;}return ts[e]||e}"
    if js.count(old_is) != 1:
        raise ValueError("RenPy language mapper signature not found")
    js = js.replace(old_is, new_is, 1)

    return js

def patch_rpyc_string_pipeline(js: str) -> str:
    # RPYC strings already come from the native structural extractor, which
    # guarantees they are user-visible Say/Menu/Translate/Text payloads. The
    # generic He() filter must not run on them: it rejects dialogue starting
    # with Ren'Py keywords (If/With/While/Stop/Call...), lines containing
    # {/tag} closing tags (slash looks like a path) and short {#tag} menu
    # labels. Only a minimal noise guard remains. The bridge escapes
    # embedded newlines/tabs so the newline-delimited protocol round-trips.
    old_ne = (
        "function Ne(e,t=``,n){let r=[],i=new Set,a=0;for(let o of e.split(`\n`)){"
        "if(!o.startsWith(`RPYC_STRING\t`))continue;let e=o.slice(12).trim();"
        "!He(e,n)||i.has(e)||(i.add(e),r.push({keyPath:`${t}rpyc_string_${a++}`,text:e}))}return r}"
    )
    new_ne = (
        "function Ne(e,t=``,n){let r=[],i=new Set,a=0;for(let o of e.split(`\n`)){"
        "if(!o.startsWith(`RPYC_STRING\t`))continue;let e=o.slice(12);"
        "if(!e.trim()||i.has(e))continue;"
        "e=e.replace("
        "/\\\\(?:\\\\|n|r|t)/g,"
        "m=>m===\"\\\\\\\\\"?\"\\\\\":"
        "m===\"\\\\n\"?\"\\n\":"
        "m===\"\\\\r\"?\"\\r\":"
        "\"\\t\");"
        "i.add(e),r.push({keyPath:`${t}rpyc_string_${a++}`,text:e})}return r}"
    )
    if js.count(old_ne) != 1:
        raise ValueError("Rpyc string pipeline signature not found")
    return js.replace(old_ne, new_ne, 1)


def patch_extraction_rules(js: str) -> str:
    old_he = (
        "/^[A-Za-z_][\\w.]*\\([^)]*\\)$/.test(n)||/^(?:pause|stop|play|scene|show|hide|with|jump|call|return|"
        "if|elif|else|while|python|init|default|define|image|transform|label)\\b/i.test(n)||!We(n,t)||Ke(n))}"
    )
    new_he = (
        "/^[A-Za-z_][\\w.]*\\(.*\\)\\s*$/.test(n)||/^[A-Za-z_][\\w.]*\\s*[+\\-*/%]{1,2}=\\s\\S/.test(n)||"
        "/^[\"'][A-Za-z0-9_./:-]{1,40}[\"']$/.test(n)||/__/.test(n)||"
        "/^[a-z][A-Za-z0-9_]*[A-Z]/.test(n)||(n.length<=16&&!n.includes(' ')&&n.includes('#'))||"
        "/^\\[[A-Za-z0-9_]+\\][!?.,]*$/.test(n)||/^(?:pause|stop|play|scene|show|hide|with|jump|call|return|"
        "if|elif|else|while|python|init|default|define|image|transform|label)\\b/i.test(n)||!We(n,t)||Ke(n))}"
    )
    if js.count(old_he) != 1:
        raise ValueError("He extraction filter signature not found")
    js = js.replace(old_he, new_he, 1)

    old_ve = "/^[0-9a-fA-F]{8,}$/.test(e)||!We(n,t))}function He(e,t)"
    new_ve = (
        "/^[0-9a-fA-F]{8,}$/.test(e)||/^[A-Za-z_][\\w.]*\\(.*\\)\\s*$/.test(n)||"
        "/^[A-Za-z_][\\w.]*\\s*[+\\-*/%]{1,2}=\\s\\S/.test(n)||/^[\"'][A-Za-z0-9_./:-]{1,40}[\"']$/.test(n)||/__/.test(n)||"
        "/^[a-z][A-Za-z0-9_]*[A-Z]/.test(n)||(n.length<=16&&!n.includes(' ')&&n.includes('#'))||"
        "/^\\[[A-Za-z0-9_]+\\][!?.,]*$/.test(n)||"
        "!We(n,t))}function He(e,t)"
    )
    if js.count(old_ve) != 1:
        raise ValueError("Ve extraction filter signature not found")
    js = js.replace(old_ve, new_ve, 1)
    return js


def patch_short_text_and_code_filters(js: str) -> str:
    # Short-text filter: capitalized 1-2 letter tokens are legitimate
    # character names / choices ("E", "Ed", "Li"), so only lowercase
    # short tokens stay filtered as identifier noise.
    old_ue = "t===`en`&&(/^[A-Za-z]{1,2}$/.test(e)||/^[A-Z0-9_-]{2,12}$/.test(e)||/^[a-z_][a-z0-9_]{1,24}$/.test(e))"
    new_ue = "t===`en`&&(/^[a-z]{1,2}$/.test(e)||/^[A-Z0-9_-]{2,12}$/.test(e)||/^[a-z_][a-z0-9_]{1,24}$/.test(e))"
    if js.count(old_ue) != 1:
        raise ValueError("Short-text filter signature not found")
    js = js.replace(old_ue, new_ue, 1)

    # Code filter: '/' or backslash only marks a path when the token has
    # no spaces. User text like "A/Bottom Button" or Ren'Py hyperlink
    # sentences must survive.
    old_ke = "function Ke(e){return!!(e.includes(`/`)||e.includes(`\\\\`)||"
    new_ke = "function Ke(e){return!!(((e.includes(`/`)||e.includes(`\\\\`))&&!e.includes(` `))||"
    if js.count(old_ke) != 1:
        raise ValueError("Code filter signature not found")
    js = js.replace(old_ke, new_ke, 1)
    return js


def patch_speed_tuning(js: str) -> str:
    # Larger batches and more parallel workers speed up translation without
    # changing correctness. The split-and-retry path still handles API
    # limits, and the in-memory cache avoids redundant calls.
    old_const = "Ao=4,jo=80,Mo=6e3"
    new_const = "Ao=5,jo=120,Mo=9e3"
    if js.count(old_const) != 1:
        raise ValueError("Speed tuning constants signature not found")
    js = js.replace(old_const, new_const, 1)
    old_default = "fs=1,ps=80;"
    new_default = "fs=1,ps=120;"
    if js.count(old_default) != 1:
        raise ValueError("Default batch size signature not found")
    js = js.replace(old_default, new_default, 1)
    old_parallel = "runFileTasksParallel(e,t,concurrency=2)"
    new_parallel = "runFileTasksParallel(e,t,concurrency=3)"
    if js.count(old_parallel) != 1:
        raise ValueError("File task concurrency signature not found")
    js = js.replace(old_parallel, new_parallel, 1)
    return js


def patch_candidate_filter(js: str) -> str:
    # Only story scripts should be candidates: existing translation buckets
    # (x-tl/...) are never translated again, and rpy/rpyc duplicates collapse
    # into the compiled variant so work is not doubled.
    # Screen and engine-common files carry the visible menu UI text (_()
    # marked strings), so they are candidates too; only pure-config files
    # (options/style/common) remain skipped.
    old_rpycskip = "var _rpycSkip=/^(?:x-)?(?:gui|media|gallery|gallery_new|screens?|options|common|style|audio|images?|init|splash|preferences)(?:[_-].*)?$/i"
    new_rpycskip = "var _rpycSkip=/^(?:x-)?(?:gui|media|gallery|gallery_new|common|style|audio|images?|init|splash|preferences)(?:[_-].*)?$/i"
    if js.count(old_rpycskip) != 1:
        raise ValueError("Rpyc skip signature not found")
    js = js.replace(old_rpycskip, new_rpycskip, 1)
    old_renpy_skip = "if(r.includes(`/x-renpy/x-common/`)||qo.has(i))return!1;"
    new_renpy_skip = "if(qo.has(i))return!1;"
    if js.count(old_renpy_skip) != 1:
        raise ValueError("Ren'Py common exclusion signature not found")
    js = js.replace(old_renpy_skip, new_renpy_skip, 1)

    # The .rpy output writer must keep the exact source string as the old
    # key: trimming loses leading/trailing whitespace, so dialogue like
    # " Alright, but before I go..." never matches at runtime.
    old_as = (
        "function as(e,t){let n=new Map;for(let r of e){let e=t.get(r.keyPath)||t.get(r.text);"
        "if(!e?.trim())continue;let i=r.text.trim(),a=e.trim();!i||!a||n.has(i)||n.set(i,a)}"
        "return Array.from(n,([e,t])=>({oldText:e,newText:t}))}"
    )
    new_as = (
        "function as(e,t){let n=new Map;for(let r of e){let e=t.get(r.keyPath)||t.get(r.text);"
        "if(!e?.trim())continue;let i=r.text,a=e.trim();!i||!a||n.has(i)||n.set(i,a)}"
        "return Array.from(n,([e,t])=>({oldText:e,newText:t}))}"
    )
    if js.count(old_as) != 1:
        raise ValueError("Output writer signature not found")
    js = js.replace(old_as, new_as, 1)

    # Engine common files (assets/x-renpy/x-common/...) have no game/x-game
    # segment, so os() fell back to a bare tl/<lang>/ path that the compile
    # step never scans. Route them into the same x-game/x-tl bucket so the
    # engine UI strings reach the compiled translations.
    old_os_main = (
        "if(r>=0&&n[r+1])return n[r+1]=ss(n[r+1],t),`${n.join(`/`)}.rpy`;"
    )
    new_os_main = (
        "if(r>=0&&n[r+1]){let s=es(n[r+1]);n[r+1]=ss(n[r+1],t);"
        "if(s&&s!==`none`&&s!==t&&!n[n.length-1].includes(`-${s}-`))n[n.length-1]=`x-${s}-${n[n.length-1]}`;"
        "return `${n.join(`/`)}.rpy`}"
    )
    if js.count(old_os_main) != 1:
        raise ValueError("Output path tl branch signature not found")
    js = js.replace(old_os_main, new_os_main, 1)
    old_os = (
        "return`tl/${t}/${n.at(-1)||`strings`}.rpy`}"
    )
    new_os = (
        "return`assets/x-game/x-tl/x-${t}/${n.at(-1)||`strings`}.rpy`}"
    )
    if js.count(old_os) != 1:
        raise ValueError("Output path fallback signature not found")
    js = js.replace(old_os, new_os, 1)
    old_jo = "function Jo(e,t,n){return e.filter(e=>Yo(e,t,n))}"
    new_jo = (
        "function Jo(e,t,n){let r=e.filter(e=>Yo(e,t,n)),m=new Map;"
        "for(let e of r){let k=e.name.replace(/\\\\/g,`/`).replace(/\\.[^/.]+$/,'');"
        "let p=m.get(k);if(!p||(e.fileType===`rpyc`&&p.fileType!==`rpyc`))m.set(k,e)}"
        "return Array.from(m.values())}"
    )
    if js.count(old_jo) != 1:
        raise ValueError("Candidate filter Jo signature not found")
    js = js.replace(old_jo, new_jo, 1)

    old_yb = "{let e=(r.split(`/`).pop()||``).replace(/\\.[^/.]+$/,``);return _rpycSkip.test(e)?!1:Zo(r,n)}"
    new_yb = "{let q=Qo(r);if(q!=null){let l=es(q);if(l===`slgtranslated`)return!1;if(l===`none`)return!0;let _s=globalThis.__slgSrcLang||`en`,_d=globalThis.__slgDstLang||`zh`;return $o(_s).has(l)||$o(_d).has(l)?!0:!1}let e=(r.split(`/`).pop()||``).replace(/\\.[^/.]+$/,``);return _rpycSkip.test(e)?!1:!0}"
    if js.count(old_yb) != 1:
        raise ValueError("Candidate filter Yo branch signature not found")
    js = js.replace(old_yb, new_yb, 1)
    return js

# ===== 翻译质量优化：视觉小说 EN→ZH 专业本地化 =====

QUALITY_PROMPT_EN_ZH = """You are a senior game localization translator for English → Simplified Chinese visual novels. Translate like an experienced localization team, not a dictionary.

CORE PRINCIPLES
1. Dialogue must read as natural spoken Chinese. Eliminate translationese (翻译腔): no stiff word order, no awkward passives, no unnatural connectors.
2. Preserve the speaker's emotion, tone and personality; match the character's register (tsundere, cheerful, cold, villainous...).
3. Translate meaning, not surface structure. Localize idioms and cultural references into what a Chinese player would naturally say.
4. Keep character and place names as-is unless the game itself establishes a Chinese name.

VISUAL NOVEL TRANSLATION HABITS (apply to every visual novel)
1. Spoken style: dialogue must sound like speech a Chinese person would actually say. Use natural particles (呢/吧/啊/嘛/哦/呀) where a native speaker would, but never stuff every sentence with them.
2. Interjections and exclamations: Hmph→哼, Ah→啊, Uh/Ugh→呃/唔, Huh→嗯/诶, Ha→哈, Oh→哦/啊, Hmm→嗯……, *sigh*→（叹气）/唉, *laugh*→（笑）/呵呵, *yawn*→（打哈欠）. Keep them short and natural; do not over-translate asterisk stage directions.
3. Onomatopoeia: localize to Chinese conventions (bang→砰, creak→吱呀, rustle→沙沙, thud→咚) instead of keeping romanized sounds.
4. Ellipsis: always use …… (two ideographic ellipses), never three dots (...).
5. Sentence rhythm: keep short lines short and punchy. Never merge two short lines into one long sentence, and never split one line into several.
6. Addresses: adapt naturally — mom/dad/brother→妈妈/爸爸/哥哥/姐姐 per relationship and register; Mr./Miss→先生/小姐 (use 君/桑 only when the setting clearly calls for it).
7. Internal monologue vs narration: first-person thoughts must read naturally (我…); narration may be slightly more literary but must stay fluid. Keep Chinese aspect natural (don't clutter with 了/着/过).
8. Repetition is meaningful: if the source repeats a word or pattern for emphasis, keep that repetition in Chinese.
9. Terminology consistency: the same term or name must be rendered identically across lines in a scene.
10. Cultural references: adapt to an equivalent Chinese expression when one exists; otherwise keep the meaning. Never add translator footnotes.

RULES
1. Keep every __PH0__ token EXACTLY in place — they protect code, markup and format strings. Preserve line breaks.
2. Use simplified Chinese punctuation: 「」 for quotes, …… for ellipsis. No half-width punctuation.
3. Dialogue must sound colloquial and fit the character; UI text must stay concise; narration can be slightly literary.
4. Never add translator notes or explanations inside the text.

REFERENCE EXAMPLES
Input: ["Hmph. Don't get the wrong idea. I just happened to pass by."]
Output: {"translations":["哼，别误会了。我只是碰巧路过而已。"]}

Input: ["Wait... are you really okay? You look exhausted."]
Output: {"translations":["等等……你真的没事吗？你看起来累坏了。"]}

Input: ["New Game"]
Output: {"translations":["新的旅程"]}"""


def patch_translation_quality(js: str) -> str:
    # 1) Le：Ren'Py 源格式解析捕获说话人名字（maria "text" → speaker: maria）
    old_le = r'''let c=s.match(/^(['"])((?:[^"'\\]|\\.)+)\1\s*:/),l=s.match(/^(?:(?:[A-Za-z_]\w*|\w+\.[A-Za-z_]\w*)\s+)?(['"])((?:[^"'\\]|\\.)+)\1\s*(?:#.*)?$/),u=c?.[2]??l?.[2];u&&He(u,n)&&!i.has(u)&&(i.add(u),r.push({keyPath:`${t}rpy_${a++}`,text:u}))'''
    new_le = r'''let c=s.match(/^(['"])((?:[^"'\\]|\\.)+)\1\s*:/),l=s.match(/^(?:([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s+)?(['"])((?:[^"'\\]|\\.)+)\2\s*(?:#.*)?$/),u=c?.[2]??l?.[3],sp=l?.[1];u&&He(u,n)&&!i.has(u)&&(i.add(u),r.push({keyPath:`${t}rpy_${a++}`,text:u,...sp?{speaker:sp}:{}}))'''
    if js.count(old_le) != 1:
        raise ValueError("Speaker extraction signature not found")
    js = js.replace(old_le, new_le, 1)

    # 2) No：去重时保留第一个说话人字段，避免 speaker 在去重后丢失
    old_no = r'''function No(e){let t=new Map;for(let n of e){let e=n.text.trim();if(!e)continue;let r=t.get(e);if(r){r.duplicateKeys.push(n.keyPath);continue}t.set(e,{keyPath:n.keyPath,text:n.text,duplicateKeys:[]})}return Array.from(t.values())}'''
    new_no = r'''function No(e){let t=new Map;for(let n of e){let e=n.text.trim();if(!e)continue;let r=t.get(e);if(r){r.duplicateKeys.push(n.keyPath);continue}t.set(e,{keyPath:n.keyPath,text:n.text,duplicateKeys:[],speaker:n.speaker})}return Array.from(t.values())}'''
    if js.count(old_no) != 1:
        raise ValueError("Dedupe signature not found")
    js = js.replace(old_no, new_no, 1)

    # 3) Ro：占位符保护后仍携带 speaker 字段，供 Vo 构造上下文
    old_ro = r'''function Ro(e){return{...e,protectedText:Fo(e.text)}}'''
    new_ro = r'''function Ro(e){return{...e,protectedText:Fo(e.text),speaker:e.speaker}}'''
    if js.count(old_ro) != 1:
        raise ValueError("Placeholder protection signature not found")
    js = js.replace(old_ro, new_ro, 1)

    # 4) Go：system prompt 全面重写（EN→ZH 视觉小说专业版，其他语言对通用版），
    #    推理模型（非 JSON 模式）附加思考引导指令
    old_go = r'''function Go(e,t,n,r){let i=`Translate game dialogue ${ko[e]??e}->${ko[t]??t}. Keep __PH0__ tokens, line breaks, and formatting.`;if(n&&n.length>0){i+=`
Use these terms consistently:
`;for(let e of n)i+=`${e.source}=${e.target}\n`}return r&&(i+=`
Return only JSON: {"translations":["..."]}`),i}'''
    new_go = r'''function Go(e,t,n,r){let i=ko[e]??e,o=ko[t]??t;if(e===`en`&&t===`zh`){i=`''' + QUALITY_PROMPT_EN_ZH + r'''`}else{i=`You are a professional game localization translator. Translate ${i} text to ${o} with natural, idiomatic flow, preserving tone and meaning.`}if(!r){i=`Think carefully about each line's context, tone and natural expression before translating.\n`+i}if(n&&n.length>0){i+=`
Use these terms consistently:
`;for(let e of n)i+=`${e.source}=${e.target}\n`}return r&&(i+=`
Return only JSON: {"translations":["..."]}`),i}'''
    if js.count(old_go) != 1:
        raise ValueError("System prompt signature not found")
    js = js.replace(old_go, new_go, 1)

    # 5) Vo：user content 注入来源文件名与说话人标注，保留 JSON 数组格式
    old_vo = r'''async function Vo(e,t,n,r,i,a,o){let s=new Map,c=Go(r,i,a,o),l=`Translate this JSON array. `+(o?`Return a JSON object exactly like {"translations":["..."]} with translations in the same order:
`:`Return a JSON array with translations in the same order:
`)+Po(n.map(e=>({...e,text:e.protectedText.text}))),u=(await e.chat.completions.create({model:t,messages:[{role:`system`,content:c},{role:`user`,content:l}],temperature:.3,...o?{response_format:{type:`json_object`}}:{}})).choices[0]?.message?.content;if(!u)throw Error(`API returned empty content`);let d=Ho(u);for(let e=0;e<n.length;e++){let t=d[e];typeof t==`string`&&t.trim()&&s.set(e,Io(t,n[e].protectedText))}return s}'''
    new_vo = r'''async function Vo(e,t,n,r,i,a,o){let s=new Map,c=Go(r,i,a,o),p0=String(n[0]?.keyPath||``),_f=p0.includes(`::`)?p0.split(`::`)[0]:``,w=_f.split(`/`).pop()||``,sc=!!_f&&n.every(e=>String(e.keyPath||``).split(`::`)[0]===_f),l=((_f?`Source file: ${w}\n`:`\n`)+(sc?`These are consecutive lines from the same scene (${w}). Translate them as one coherent dialogue flow — keep tone, terminology and speaking habits consistent across all lines.\n`:`\n`)+(n.some(e=>e.speaker)?`Context hints (index → speaker):\n`+n.map((e,i)=>`[${i}]${e.speaker?` → ${e.speaker}`:``}\n`).join(``):``)+`Translate this JSON array. `+(o?`Return a JSON object exactly like {"translations":["..."]} with translations in the same order:
`:`Return a JSON array with translations in the same order:
`)+Po(n.map(e=>({...e,text:e.protectedText.text})))),u=(await e.chat.completions.create({model:t,messages:[{role:`system`,content:c},{role:`user`,content:l}],temperature:.3,...o?{response_format:{type:`json_object`}}:{}})).choices[0]?.message?.content;if(!u)throw Error(`API returned empty content`);let d=Ho(u);for(let e=0;e<n.length;e++){let t=d[e];typeof t==`string`&&t.trim()&&s.set(e,Io(t,n[e].protectedText))}return s}'''
    if js.count(old_vo) != 1:
        raise ValueError("Batch request signature not found")
    js = js.replace(old_vo, new_vo, 1)
    return js
def _verify_digest(data: bytes, expected: str, label: str) -> None:
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(
            f"canonical base {label} SHA-256 mismatch: expected {expected}, got {actual}"
        )


def verify_canonical_base_assets(js_path: Path, css_path: Path) -> None:
    for path, digest, label in (
        (js_path, CANONICAL_BASE_JS_SHA256, "JavaScript"),
        (css_path, CANONICAL_BASE_CSS_SHA256, "CSS"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"canonical base {label} is missing: {path}")
        _verify_digest(path.read_bytes(), digest, label)


def verify_canonical_base_text(js: str, css: str) -> None:
    # read_text() applies universal-newline decoding. Reconstruct the canonical
    # extraction's known line endings so patch_assets still enforces the same pins.
    canonical_js = js.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    canonical_css = css.replace("\r\n", "\n").replace("\r", "\n")
    _verify_digest(canonical_js.encode("utf-8"), CANONICAL_BASE_JS_SHA256, "JavaScript")
    _verify_digest(canonical_css.encode("utf-8"), CANONICAL_BASE_CSS_SHA256, "CSS")


def write_generated_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def patch_assets(js: str, css: str) -> tuple[str, str]:
    verify_canonical_base_text(js, css)
    copy_contract = "\n/* workshop-copy:" + "|".join(WORKSHOP_COPY) + " */\n"
    patched = patch_scan_flow(js)
    patched = patch_translation_cache(patched)
    patched = patch_translation_network(patched)
    patched = patch_translation_memory(patched)
    patched = patch_extraction_rules(patched)
    patched = patch_short_text_and_code_filters(patched)
    patched = patch_rpyc_string_pipeline(patched)
    patched = patch_speed_tuning(patched)
    patched = patch_candidate_filter(patched)
    patched = patch_translation_quality(patched)
    return patched + copy_contract + enhance_runtime(WORKSHOP_RUNTIME), css + "\n" + WORKSHOP_CSS


def main() -> None:
    source = ROOT.parent / "extracted" / "assets" / "public" / "assets"
    output = ROOT / "generated"
    output.mkdir(exist_ok=True)
    js_path = source / "index-CJtfdHOF.js"
    css_path = source / "index-C044IUg3.css"
    verify_canonical_base_assets(js_path, css_path)
    js, css = patch_assets(
        js_path.read_text("utf-8"),
        css_path.read_text("utf-8"),
    )
    write_generated_text(output / "index-CJtfdHOF.js", js)
    write_generated_text(output / "index-C044IUg3.css", css)


if __name__ == "__main__":
    main()
