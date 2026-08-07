from __future__ import annotations

import hashlib
from pathlib import Path
import re

from patch_local_ui import enhance_local_runtime
from scan_flow_constants import SCAN_FLOW


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

WORKSHOP_CSS = r"""
:root{
--workshop-bg:oklch(.985 .006 110);
--workshop-surface:oklch(.972 .009 105);
--workshop-surface-2:oklch(.955 .012 100);
--workshop-surface-3:oklch(.932 .017 102);
--workshop-ink:oklch(.26 .026 140);
--workshop-ink-strong:oklch(.20 .028 140);
--workshop-muted:oklch(.50 .032 132);
--workshop-on-soft:oklch(.39 .045 145);
--workshop-primary:oklch(.43 .095 148);
--workshop-primary-strong:oklch(.36 .10 148);
--workshop-on-primary:oklch(.99 .004 105);
--workshop-primary-soft:oklch(.94 .025 145);
--workshop-accent:oklch(.70 .135 72);
--workshop-on-accent:oklch(.22 .04 72);
--workshop-accent-soft:oklch(.95 .04 85);
--workshop-error:oklch(.56 .19 25);
--workshop-success:oklch(.52 .12 150);
--workshop-warning:oklch(.66 .13 75);
--workshop-info:oklch(.55 .10 240);
--workshop-border:color-mix(in oklch,var(--workshop-ink) 12%,transparent);
--workshop-outline:color-mix(in oklch,var(--workshop-ink) 20%,transparent);
--workshop-outline-strong:color-mix(in oklch,var(--workshop-primary) 55%,transparent);
--workshop-focus-ring:color-mix(in oklch,var(--workshop-primary) 30%,transparent);
--workshop-disabled:color-mix(in oklch,var(--workshop-ink) 36%,transparent);
--workshop-disabled-bg:color-mix(in oklch,var(--workshop-ink) 8%,transparent);
--workshop-shadow-sm:0 1px 2px color-mix(in oklch,var(--workshop-ink) 6%,transparent);
--workshop-shadow-md:0 8px 24px color-mix(in oklch,var(--workshop-ink) 10%,transparent);
--workshop-shadow-lg:0 18px 48px color-mix(in oklch,var(--workshop-ink) 18%,transparent);
--workshop-radius-sm:12px;
--workshop-radius-md:16px;
--workshop-radius-lg:22px;
--workshop-radius-xl:28px;
--workshop-font-xs:12px;
--workshop-font-sm:13px;
--workshop-font-base:14px;
--workshop-font-md:15px;
--workshop-font-lg:17px;
--workshop-font-title:20px;
--workshop-font-display:26px;
--workshop-ease:cubic-bezier(.33,1,.68,1);
color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{
--workshop-bg:oklch(.125 .014 135);
--workshop-surface:oklch(.17 .017 140);
--workshop-surface-2:oklch(.21 .02 145);
--workshop-surface-3:oklch(.25 .023 145);
--workshop-ink:oklch(.94 .008 100);
--workshop-ink-strong:oklch(.97 .006 100);
--workshop-muted:oklch(.74 .015 110);
--workshop-on-soft:oklch(.82 .02 145);
--workshop-primary:oklch(.74 .105 152);
--workshop-primary-strong:oklch(.80 .095 152);
--workshop-on-primary:oklch(.14 .03 145);
--workshop-primary-soft:oklch(.26 .05 150);
--workshop-accent:oklch(.78 .12 80);
--workshop-on-accent:oklch(.18 .03 75);
--workshop-accent-soft:oklch(.30 .06 85);
--workshop-error:oklch(.70 .16 25);
--workshop-success:oklch(.74 .12 152);
--workshop-warning:oklch(.80 .12 80);
--workshop-info:oklch(.72 .09 240);
--workshop-border:color-mix(in oklch,var(--workshop-ink) 16%,transparent);
--workshop-outline:color-mix(in oklch,var(--workshop-ink) 26%,transparent);
--workshop-outline-strong:color-mix(in oklch,var(--workshop-primary) 60%,transparent);
--workshop-focus-ring:color-mix(in oklch,var(--workshop-primary) 32%,transparent);
--workshop-disabled:color-mix(in oklch,var(--workshop-ink) 36%,transparent);
--workshop-disabled-bg:color-mix(in oklch,var(--workshop-ink) 10%,transparent);
--workshop-shadow-sm:0 1px 2px rgb(0 0 0 / .18);
--workshop-shadow-md:0 8px 24px rgb(0 0 0 / .28);
--workshop-shadow-lg:0 18px 48px rgb(0 0 0 / .40)}}
.workshop-runtime,.workshop-runtime *{box-sizing:border-box}
.workshop-touch{min-width:48px;min-height:48px}
.workshop-runtime{min-height:100dvh;padding-top:env(safe-area-inset-top);background:var(--workshop-bg);color:var(--workshop-ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased;-webkit-tap-highlight-color:transparent;touch-action:manipulation;text-rendering:optimizeLegibility;letter-spacing:.01em}
.workshop-runtime button:focus-visible,.workshop-runtime input:focus-visible,.workshop-runtime select:focus-visible,.workshop-runtime [tabindex]:focus-visible{outline:3px solid var(--workshop-focus-ring);outline-offset:2px}
.workshop-runtime button:disabled{opacity:.55;box-shadow:none;cursor:default}
.workshop-runtime>header,.workshop-runtime>nav,.workshop-runtime>footer{display:none!important}
.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav{display:grid!important}
.workshop-hero{margin:18px 16px 4px;padding:24px 22px 26px;border-radius:var(--workshop-radius-xl);background:linear-gradient(145deg,var(--workshop-primary),color-mix(in oklch,var(--workshop-primary) 78%,var(--workshop-accent)));color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-md);position:relative;overflow:hidden}
.workshop-hero::before{content:"";position:absolute;top:-40%;right:-15%;width:70%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,color-mix(in oklch,var(--workshop-accent) 34%,transparent),transparent 68%)}
.workshop-hero::after{content:"";position:absolute;top:0;right:0;width:42%;height:100%;opacity:.16;background-image:radial-gradient(circle at 1px 1px,color-mix(in oklch,var(--workshop-on-primary) 80%,transparent) 1px,transparent 0);background-size:18px 18px;mask-image:linear-gradient(135deg,transparent 20%,#000 100%);-webkit-mask-image:linear-gradient(135deg,transparent 20%,#000 100%)}
.workshop-hero small{position:relative;display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border:1px solid color-mix(in oklch,var(--workshop-on-primary) 28%,transparent);border-radius:999px;font-size:var(--workshop-font-xs);opacity:.95;letter-spacing:.05em}
.workshop-hero small::before{content:"";width:7px;height:7px;border-radius:50%;background:color-mix(in oklch,var(--workshop-accent) 72%,var(--workshop-on-primary));box-shadow:0 0 0 3px color-mix(in oklch,var(--workshop-accent) 30%,transparent)}
.workshop-hero h1{position:relative;margin:12px 0 0;font-size:var(--workshop-font-display);line-height:1.16;font-weight:800;letter-spacing:-.025em;text-wrap:balance;max-width:22ch}
.workshop-runtime main{display:none!important;padding:16px 16px 104px!important;background:var(--workshop-bg)!important}.workshop-runtime main>div,.workshop-runtime main>section,.workshop-runtime main details{border-color:var(--workshop-border)!important;background:var(--workshop-surface)!important;border-radius:var(--workshop-radius-lg)!important;box-shadow:var(--workshop-shadow-sm)!important}.workshop-runtime button[class*="bg-blue"]{min-height:48px;background:var(--workshop-primary)!important;color:var(--workshop-on-primary)!important;border-radius:var(--workshop-radius-md)!important}.workshop-runtime [class*="text-blue"]{color:var(--workshop-primary)!important}
.workshop-picker-source>h2,.workshop-picker-source>button{display:none!important}
.workshop-task-shell{position:relative;display:flex;flex-direction:column;gap:16px;min-height:calc(100dvh - 24px);padding:20px 16px 112px;background:var(--workshop-bg);color:var(--workshop-ink)}
.workshop-task-topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:48px;margin-bottom:-4px}
.workshop-task-topbar h1{margin:0;font-size:var(--workshop-font-title);line-height:1.25;font-weight:780;letter-spacing:-.01em}
.workshop-topbar-state{display:inline-flex;align-items:center;gap:7px;margin-left:auto;padding:7px 12px;border:1px solid var(--workshop-border);border-radius:999px;background:var(--workshop-surface);color:var(--workshop-muted);font-size:var(--workshop-font-xs);font-weight:750;box-shadow:var(--workshop-shadow-sm);white-space:nowrap}
.workshop-topbar-state::before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor;box-shadow:0 0 0 3px color-mix(in oklch,currentColor 16%,transparent)}
.workshop-chip-scanning{color:var(--workshop-info)}
.workshop-chip-ready,.workshop-chip-completed{color:var(--workshop-success)}
.workshop-chip-translating,.workshop-chip-patching{color:var(--workshop-accent)}
.workshop-chip-empty,.workshop-chip-failed{color:var(--workshop-error)}
.workshop-task-back{display:inline-flex;align-items:center;gap:2px;min-width:64px;min-height:44px;padding:0 14px 0 8px;border:1px solid var(--workshop-border);border-radius:999px;background:var(--workshop-surface);color:var(--workshop-ink);font-size:var(--workshop-font-md);font-weight:700;box-shadow:var(--workshop-shadow-sm);transition:background-color 160ms ease-out,transform 120ms ease-out,box-shadow 160ms ease-out}
.workshop-task-back:active{transform:scale(.96);background:var(--workshop-surface-2)}
.workshop-brand-panel{padding:22px 20px 24px;border-radius:var(--workshop-radius-xl);background:linear-gradient(150deg,var(--workshop-primary),color-mix(in oklch,var(--workshop-primary) 80%,var(--workshop-accent)));color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-md);position:relative;overflow:hidden}
.workshop-brand-panel::before{content:"";position:absolute;top:-45%;left:-10%;width:75%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,color-mix(in oklch,var(--workshop-accent) 30%,transparent),transparent 70%)}
.workshop-brand-panel::after{content:"";position:absolute;right:-4px;bottom:-16px;width:58%;height:110%;opacity:.14;background-image:radial-gradient(circle at 1px 1px,color-mix(in oklch,var(--workshop-on-primary) 84%,transparent) 1px,transparent 0);background-size:16px 16px;mask-image:linear-gradient(135deg,transparent 24%,#000 100%);-webkit-mask-image:linear-gradient(135deg,transparent 24%,#000 100%)}
.workshop-brand-panel p,.workshop-brand-panel h2{position:relative}
.workshop-brand-panel p{margin:0;font-size:var(--workshop-font-base);line-height:1.5;opacity:.92;max-width:32ch}
.workshop-brand-panel h2{margin:6px 0 0;font-size:var(--workshop-font-display);line-height:1.18;font-weight:800;letter-spacing:-.025em;text-wrap:balance}
.workshop-steps{display:grid;gap:10px;margin:0;padding:14px 16px;list-style:none;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-lg);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm)}
.workshop-steps li{display:grid;grid-template-columns:30px 1fr;grid-template-rows:auto auto;column-gap:10px;align-items:center}
.workshop-step-index{display:grid;place-items:center;grid-row:1 / span 2;width:28px;height:28px;border-radius:50%;background:var(--workshop-primary-soft);color:var(--workshop-primary);font-size:var(--workshop-font-xs);font-weight:800;font-variant-numeric:tabular-nums}
.workshop-step-copy{font-size:var(--workshop-font-base);font-weight:750;line-height:1.3}
.workshop-step-note{color:var(--workshop-muted);font-size:var(--workshop-font-xs);line-height:1.4}
.workshop-task-card{padding:18px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-lg);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm);animation:workshopRise 200ms var(--workshop-ease)}
.workshop-task-shell[data-workshop-state="translating"] .workshop-task-card{animation:none}
.workshop-task-shell[data-workshop-state="patching"] .workshop-task-card{animation:none}
@keyframes workshopRise{from{transform:translateY(6px);opacity:0}to{transform:translateY(0);opacity:1}}
.workshop-file-row{display:flex;align-items:center;gap:12px;min-height:56px}
.workshop-file-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;background:linear-gradient(150deg,var(--workshop-primary-soft),color-mix(in oklch,var(--workshop-primary-soft) 82%,var(--workshop-accent-soft)));color:var(--workshop-primary);font-weight:800;font-size:var(--workshop-font-md);letter-spacing:.02em}
.workshop-file-name{min-width:0;font-weight:720;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.workshop-file-meta{margin-top:3px;color:var(--workshop-muted);font-size:var(--workshop-font-sm)}
.workshop-state-copy{margin:12px 0 0;color:var(--workshop-muted);line-height:1.5;font-size:var(--workshop-font-base)}
.workshop-state-copy.workshop-scan-elapsed{display:block;margin-top:6px;color:var(--workshop-muted);font-size:var(--workshop-font-sm);font-variant-numeric:tabular-nums}
.workshop-state-icon{display:grid;place-items:center;width:52px;height:52px;margin:14px 0 2px;border-radius:16px;background:var(--workshop-primary-soft);color:var(--workshop-primary)}
.workshop-state-icon svg{display:block}
.workshop-state-icon-scanning,.workshop-state-icon-patching{background:var(--workshop-accent-soft);color:var(--workshop-accent)}
.workshop-state-icon-ready,.workshop-state-icon-completed{background:color-mix(in oklch,var(--workshop-success) 14%,var(--workshop-surface));color:var(--workshop-success)}
.workshop-state-icon-empty,.workshop-state-icon-failed{background:color-mix(in oklch,var(--workshop-error) 12%,var(--workshop-surface));color:var(--workshop-error)}
.workshop-progress{height:8px;margin-top:16px;border-radius:999px;background:color-mix(in oklch,var(--workshop-primary) 14%,transparent);overflow:hidden;position:relative}
.workshop-progress>i{display:block;width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--workshop-primary),color-mix(in oklch,var(--workshop-primary) 55%,var(--workshop-accent)));transition:width 240ms var(--workshop-ease)}
.workshop-progress>i::after{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(90deg,transparent,color-mix(in oklch,var(--workshop-accent) 45%,transparent),transparent);background-size:200% 100%;animation:workshopShimmer 1.8s linear infinite}
@keyframes workshopShimmer{from{background-position:200% 0}to{background-position:-200% 0}}
.workshop-progress-label{display:block;margin-top:8px;color:var(--workshop-muted);font-size:var(--workshop-font-xs);font-weight:750;font-variant-numeric:tabular-nums;text-align:right}
.workshop-summary-list{display:grid;gap:10px;margin:16px 0 0;padding:0;list-style:none}
.workshop-summary-row{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 14px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-sm);background:var(--workshop-surface-2);font-size:var(--workshop-font-base);line-height:1.45}
.workshop-summary-row span:first-child{color:var(--workshop-muted)}
.workshop-summary-row span:last-child{text-align:right;font-weight:780;font-variant-numeric:tabular-nums}
.workshop-detail-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;margin-top:12px;padding:0 4px;border:0;background:transparent;color:var(--workshop-primary);font-weight:750;text-align:left;border-radius:var(--workshop-radius-sm);transition:background-color 160ms ease-out}
.workshop-detail-toggle:active{background:var(--workshop-primary-soft)}
.workshop-detail-body{display:none;max-height:240px;margin-top:8px;padding:12px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface-2);color:var(--workshop-muted);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:var(--workshop-font-xs);line-height:1.55;white-space:pre-wrap;overflow:auto;overflow-wrap:anywhere}
.workshop-detail-body[data-open="true"]{display:block}
.workshop-live-line{position:relative;margin:12px 0 0;padding:10px 12px 10px 30px;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary-soft);color:var(--workshop-muted);font-size:var(--workshop-font-sm);line-height:1.5;overflow-wrap:anywhere}
.workshop-live-line::before{content:"";position:absolute;left:12px;top:14px;width:8px;height:8px;border-radius:50%;background:var(--workshop-primary);box-shadow:0 0 0 3px color-mix(in oklch,var(--workshop-primary) 18%,transparent)}
.workshop-task-shell[data-workshop-state="idle"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="scanning"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="ready"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="translating"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="patching"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="completed"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="failed"] .workshop-progress{display:none}
.workshop-settings-shell{position:fixed;z-index:40;inset:0;display:flex;flex-direction:column;gap:16px;padding:20px 16px max(24px,env(safe-area-inset-bottom));background:var(--workshop-bg);color:var(--workshop-ink);overflow:auto}
.workshop-settings-shell[hidden]{display:none!important}
.workshop-settings-card{padding:20px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-lg);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm);animation:workshopRise 200ms var(--workshop-ease)}
.workshop-settings-card label{display:block;margin-bottom:8px;font-size:var(--workshop-font-base);font-weight:720}
.workshop-settings-input{box-sizing:border-box;width:100%;min-height:52px;padding:12px 14px;border:1px solid var(--workshop-outline);border-radius:var(--workshop-radius-sm);background:var(--workshop-bg);color:var(--workshop-ink);font-size:16px;transition:border-color 160ms ease-out,box-shadow 160ms ease-out}
.workshop-settings-input:focus{outline:none;box-shadow:0 0 0 3px var(--workshop-focus-ring);border-color:var(--workshop-primary)}
.workshop-settings-save{width:100%;min-width:48px;min-height:52px;margin-top:16px;border:0;border-radius:var(--workshop-radius-md);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:760;font-size:var(--workshop-font-md);box-shadow:var(--workshop-shadow-sm);transition:transform 120ms ease-out,filter 160ms ease-out,box-shadow 160ms ease-out}
.workshop-settings-save:active{transform:scale(.98);filter:brightness(.96)}
.workshop-settings-helper{margin:12px 0 0;color:var(--workshop-muted);font-size:var(--workshop-font-sm);line-height:1.5}
.workshop-settings-title{margin:0 0 16px;font-size:var(--workshop-font-lg);line-height:1.3;font-weight:760}
.workshop-settings-field{display:block;margin-top:14px}
.workshop-settings-field:first-of-type{margin-top:0}
.workshop-settings-field>span{display:block;margin-bottom:7px;font-size:var(--workshop-font-base);font-weight:720}
.workshop-settings-conditional[hidden]{display:none!important}
.workshop-settings-error{margin:6px 0 0;color:var(--workshop-error);font-size:var(--workshop-font-sm);line-height:1.4}
.workshop-settings-status{margin:10px 0 0;color:var(--workshop-muted);font-size:var(--workshop-font-sm);line-height:1.45}
.workshop-settings-save:disabled{opacity:.55}
.workshop-save-more{display:flex;align-items:center;justify-content:center;width:100%;min-height:48px;margin-top:10px;padding:0 12px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-primary);font-weight:720;transition:background-color 160ms ease-out}
.workshop-save-more:active{background:var(--workshop-primary-soft)}
.workshop-save-manage{display:grid;gap:10px;margin-top:8px;padding-top:10px;border-top:1px solid var(--workshop-border)}
.workshop-save-manage[hidden]{display:none!important}
.workshop-save-manage .workshop-settings-save{margin-top:0}
.workshop-saves-list{display:grid;gap:10px;margin-top:14px}
.workshop-archive-section{margin-top:16px;padding-top:12px;border-top:1px solid var(--workshop-border);display:grid;gap:10px}
.workshop-archive-section[hidden]{display:none!important}
.workshop-archive-title{margin:0;font-size:var(--workshop-font-base);font-weight:760;color:var(--workshop-muted)}
.workshop-save-row > .workshop-save-restore{min-width:72px;min-height:44px;padding:0 12px;border:0;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:720}
.workshop-save-row > .workshop-save-delete{min-width:48px;min-height:44px;padding:0 8px;border:0;border-radius:var(--workshop-radius-sm);background:transparent;color:var(--workshop-error);font-weight:720}
.workshop-save-row > button:disabled{opacity:.55}
.workshop-saves-empty{margin:0;padding:16px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface-2);color:var(--workshop-muted);line-height:1.5}
.workshop-save-row{display:flex;flex-wrap:wrap;align-items:flex-start;gap:8px 12px;padding:14px 16px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-md);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm)}
.workshop-save-name{flex:1 1 180px;font-weight:730;overflow-wrap:anywhere}.workshop-save-meta{flex:1 1 180px;color:var(--workshop-muted);font-size:var(--workshop-font-sm);line-height:1.5}
.workshop-save-actions{display:flex;gap:8px;margin-left:auto}.workshop-save-actions button{min-width:68px;min-height:44px;padding:0 12px;border:0;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:720}.workshop-save-actions button:disabled{opacity:.55}.workshop-save-actions .workshop-save-restore{min-width:92px}.workshop-save-actions .workshop-save-share{background:transparent;color:var(--workshop-primary)}.workshop-save-actions .workshop-save-delete{background:transparent;color:var(--workshop-error)}.workshop-save-actions .workshop-save-share,.workshop-save-actions .workshop-save-delete{min-width:48px;width:48px;padding:0 4px}
.workshop-primary-action{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;min-height:52px;margin-top:auto;border:0;border-radius:var(--workshop-radius-md);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:760;font-size:var(--workshop-font-md);box-shadow:var(--workshop-shadow-sm);transition:transform 120ms ease-out,box-shadow 160ms ease-out,filter 160ms ease-out}
.workshop-primary-action:active{transform:scale(.98);filter:brightness(.96)}
.workshop-secondary-action{min-width:48px;min-height:48px;margin-top:8px;padding:0 8px;border:0;border-radius:var(--workshop-radius-sm);background:transparent;color:var(--workshop-primary);font-weight:720;transition:background-color 160ms ease-out}
.workshop-secondary-action:active{background:var(--workshop-primary-soft)}
.workshop-error-card{border-color:color-mix(in oklch,var(--workshop-error) 32%,transparent);background:color-mix(in oklch,var(--workshop-error) 7%,var(--workshop-surface))}
.workshop-error-title{margin:0;color:var(--workshop-error);font-size:var(--workshop-font-lg);font-weight:760}
.workshop-source-dialog{position:fixed;z-index:50;inset:0;box-sizing:border-box;display:flex;align-items:flex-end;justify-content:center;padding:16px;background:color-mix(in oklch,var(--workshop-ink) 44%,transparent);overflow:auto}.workshop-installed-dialog{position:fixed;z-index:50;inset:0;box-sizing:border-box;display:flex;align-items:flex-end;justify-content:center;padding:16px;background:color-mix(in oklch,var(--workshop-ink) 44%,transparent);overflow:auto}
.workshop-source-dialog[hidden],.workshop-installed-dialog[hidden]{display:none!important}
.workshop-modal-panel{box-sizing:border-box;width:min(100%,560px);max-height:min(82dvh,720px);padding:22px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-xl);background:var(--workshop-bg);color:var(--workshop-ink);box-shadow:var(--workshop-shadow-lg);overflow:auto;animation:workshopSheetIn 220ms var(--workshop-ease)}
@keyframes workshopSheetIn{from{transform:translateY(18px);opacity:0}to{transform:translateY(0);opacity:1}}
.workshop-modal-title{margin:0 0 6px;font-size:var(--workshop-font-title);line-height:1.3;font-weight:760}.workshop-modal-copy{margin:0 0 16px;color:var(--workshop-muted);font-size:var(--workshop-font-base);line-height:1.5}
.workshop-source-option,.workshop-modal-action,.workshop-app-row{box-sizing:border-box;width:100%;min-height:52px;border:0;border-radius:var(--workshop-radius-md);font:inherit}
.workshop-source-option{display:flex;align-items:center;padding:0 16px;margin-top:8px;background:var(--workshop-surface);color:var(--workshop-ink);font-weight:720;text-align:left;transition:background-color 160ms ease-out}.workshop-source-option:active{background:var(--workshop-surface-2)}.workshop-source-option:first-of-type{background:var(--workshop-primary);color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-sm)}
.workshop-modal-action{margin-top:8px;background:transparent;color:var(--workshop-primary);font-weight:720}.workshop-source-option:focus-visible,.workshop-modal-action:focus-visible,.workshop-app-row:focus-visible{outline:3px solid var(--workshop-focus-ring);outline-offset:2px}
.workshop-installed-search{box-sizing:border-box;width:100%;min-height:52px;margin:12px 0;padding:0 14px;border:1px solid var(--workshop-outline);border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-ink);font-size:16px;transition:border-color 160ms ease-out,box-shadow 160ms ease-out}.workshop-installed-search:focus{outline:none;box-shadow:0 0 0 3px var(--workshop-focus-ring);border-color:var(--workshop-primary)}
.workshop-app-list{display:grid;gap:8px;margin:0;padding:0;list-style:none}.workshop-app-row{display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding:8px 14px;background:var(--workshop-surface);color:var(--workshop-ink);text-align:left;transition:background-color 160ms ease-out}.workshop-app-row:active{background:var(--workshop-surface-2)}.workshop-app-label{font-weight:730}.workshop-app-package{margin-top:2px;color:var(--workshop-muted);font-size:var(--workshop-font-xs);overflow-wrap:anywhere}.workshop-installed-status{margin:12px 0;padding:16px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-muted);line-height:1.5}.workshop-installed-error{color:var(--workshop-error)}
@media(min-width:600px){.workshop-source-dialog,.workshop-installed-dialog{align-items:center}.workshop-modal-panel{border-radius:var(--workshop-radius-xl)}}
.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}
.workshop-runtime[data-workshop-task="active"] main{display:none!important}
body:has(.workshop-runtime[data-workshop-task="active"]) .workshop-bottom-nav{display:none!important}
.workshop-bottom-nav{position:fixed;z-index:30;left:12px;right:12px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(3,1fr);padding:6px;border:1px solid var(--workshop-border);border-radius:26px;background:color-mix(in oklch,var(--workshop-bg) 88%,transparent);box-shadow:var(--workshop-shadow-md);backdrop-filter:blur(14px)}
.workshop-bottom-nav button{position:relative;display:grid;grid-template-rows:22px auto;place-items:center;gap:3px;min-height:56px;padding:7px 4px 5px;border:0;border-radius:18px;background:transparent;color:var(--workshop-muted);font-size:var(--workshop-font-xs);font-weight:660;transition:color 160ms ease-out,background-color 160ms ease-out,transform 120ms ease-out}
.workshop-bottom-nav button:active{transform:scale(.96)}
.workshop-bottom-nav .workshop-nav-icon{display:grid;place-items:center;width:22px;height:22px}
.workshop-bottom-nav .workshop-nav-icon svg{display:block}
.workshop-bottom-nav button[aria-current="page"]{background:var(--workshop-primary);color:var(--workshop-on-primary);box-shadow:var(--workshop-shadow-sm)}
.workshop-gallery-shell{position:fixed;z-index:40;inset:0;display:flex;flex-direction:column;gap:16px;padding:20px 16px max(24px,env(safe-area-inset-bottom));background:var(--workshop-bg);color:var(--workshop-ink);overflow:auto}.workshop-gallery-shell[hidden]{display:none!important}.workshop-gallery-content{display:grid;gap:10px}.workshop-gallery-status{margin:0;padding:16px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface);color:var(--workshop-muted);line-height:1.5}.workshop-gallery-list{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.workshop-empty-state{display:grid;place-items:center;gap:10px;padding:30px 18px;border:1px dashed var(--workshop-border);border-radius:var(--workshop-radius-lg);background:var(--workshop-surface);text-align:center}
.workshop-empty-icon{display:grid;place-items:center;width:56px;height:56px;border-radius:18px;background:var(--workshop-primary-soft);color:var(--workshop-primary)}
.workshop-empty-icon svg{display:block}
.workshop-empty-title{margin:0;font-size:var(--workshop-font-lg);font-weight:760}
.workshop-empty-state .workshop-gallery-status{margin:0;padding:0;background:transparent;color:var(--workshop-muted);max-width:30ch}
.workshop-patch-row{padding:14px 16px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-md);background:var(--workshop-surface);box-shadow:var(--workshop-shadow-sm)}
.workshop-patch-head{display:flex;align-items:center;gap:12px}
.workshop-patch-icon{display:grid;place-items:center;flex:0 0 auto;width:44px;height:44px;border-radius:14px;background:var(--workshop-accent-soft);color:var(--workshop-accent)}
.workshop-patch-icon svg{display:block}
.workshop-patch-copy{min-width:0;flex:1 1 auto}
.workshop-patch-name{font-weight:730;overflow-wrap:anywhere}
.workshop-patch-meta{margin-top:4px;color:var(--workshop-muted);font-size:var(--workshop-font-xs)}
.workshop-patch-save{min-height:44px;margin-top:10px;padding:0 16px;border:0;border-radius:var(--workshop-radius-sm);background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:720;transition:transform 120ms ease-out,filter 160ms ease-out}.workshop-patch-save:active{transform:scale(.98)}
.workshop-gallery-shell .workshop-secondary-action{align-self:flex-start;min-height:48px;padding:0 12px;border:0;background:transparent;color:var(--workshop-primary);font-weight:720}
.workshop-settings-menu{display:grid;gap:10px;margin-top:4px}
.workshop-menu-item{position:relative;display:flex;align-items:center;gap:12px;width:100%;min-height:64px;padding:10px 14px;border:1px solid var(--workshop-border);border-radius:var(--workshop-radius-md);background:var(--workshop-surface);color:var(--workshop-ink);text-align:left;box-shadow:var(--workshop-shadow-sm);transition:transform 120ms ease-out,background-color 160ms ease-out,border-color 160ms ease-out}
.workshop-menu-item:active{transform:scale(.985);background:var(--workshop-surface-2)}
.workshop-menu-item:disabled{opacity:.6}
.workshop-menu-icon{display:grid;place-items:center;flex:0 0 auto;width:44px;height:44px;border-radius:14px;background:var(--workshop-primary-soft);color:var(--workshop-primary)}
.workshop-menu-icon svg{display:block}
.workshop-menu-copy{display:flex;flex:1 1 auto;min-width:0;flex-direction:column;gap:2px}
.workshop-menu-item-label{font-weight:760;font-size:var(--workshop-font-md)}
.workshop-menu-item-desc{margin:0;color:var(--workshop-muted);font-size:var(--workshop-font-xs);line-height:1.4}
.workshop-menu-item-arrow{margin-left:0;color:var(--workshop-muted);font-size:22px;font-weight:500;flex:0 0 auto}
.workshop-menu-item.workshop-menu-active{border-color:var(--workshop-outline-strong);background:var(--workshop-primary-soft)}
.workshop-menu-item.workshop-menu-active .workshop-menu-item-arrow{color:var(--workshop-primary);transform:rotate(90deg)}
.workshop-menu-item.workshop-menu-active .workshop-menu-item-label{color:var(--workshop-primary)}
.workshop-settings-menu-hint{margin:2px 4px 0;padding:10px 12px;border-radius:var(--workshop-radius-sm);background:var(--workshop-surface-2);color:var(--workshop-muted);font-size:var(--workshop-font-sm);line-height:1.5}
.workshop-settings-menu-hint[hidden]{display:none!important}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
"""

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
const savesTop=textNode("header","workshop-task-topbar");
const savesBack=viewBack("返回菜单",showMenu);
savesTop.append(savesBack,textNode("h1","","存档转移"));
const savesCard=textNode("section","workshop-settings-card");
savesCard.append(textNode("h2","workshop-settings-title","存档转移"));
const plugin=window.Capacitor?.Plugins?.FileManager;
const savesStatus=textNode("p","workshop-settings-status");
const permissionNote=textNode("p","workshop-settings-helper");
const backupHint=textNode("p","workshop-settings-helper","请先选择游戏。");
const backupBtn=textNode("button","workshop-settings-save","备份当前存档");
backupBtn.type="button";
const savesList=textNode("div","workshop-saves-list");
const savesEmpty=textNode("p","workshop-saves-empty","暂无备份。");
savesList.append(savesEmpty);
const updateSavesState=()=>{const pkg=window.__slgSelectionMeta?.packageName||"";const ready=!!pkg&&!!plugin;backupBtn.disabled=!ready;backupHint.textContent=!pkg?"请先选择游戏。":"备份保存到本机应用目录。";if(/Android\s+(1[1-9]|[2-9][0-9])/i.test(navigator.userAgent)){permissionNote.textContent="请在系统设置中授予“所有文件访问”权限后，再进行备份或恢复。"}else{permissionNote.hidden=true}};
updateSavesState();
async function refreshSaves(){if(!plugin){savesStatus.textContent="当前版本不支持存档转移。";return}savesStatus.textContent="正在读取备份…";try{const result=await plugin.listSaveBackups();savesList.replaceChildren();const backups=Array.isArray(result?.backups)?result.backups:[];if(!backups.length){savesList.append(savesEmpty);savesEmpty.textContent="暂无备份。";savesStatus.textContent="";return}backups.forEach(item=>{const row=textNode("article","workshop-save-row");const name=textNode("div","workshop-save-name",item.name||"未命名备份");const meta=textNode("div","workshop-save-meta",`${item.fileCount||0} 个文件 · ${new Date(item.modifiedAt||Date.now()).toLocaleString()}`);const actions=textNode("div","workshop-save-actions");const restore=textNode("button","workshop-save-restore","恢复");restore.type="button";const del=textNode("button","workshop-save-delete","删除");del.type="button";restore.onclick=async()=>{if(!confirm(`恢复 ${item.name||"该备份"} 会覆盖当前存档，确定继续？`))return;restore.disabled=true;restore.textContent="恢复中…";try{await plugin.restoreSaves({packageName:window.__slgSelectionMeta?.packageName||"",backupDir:item.path||item.name});savesStatus.textContent="恢复完成。"}catch(e){savesStatus.textContent="恢复失败："+(e&&e.message||String(e))}finally{restore.disabled=false;restore.textContent="恢复"}};del.onclick=async()=>{if(!confirm(`确定删除备份 ${item.name||"该备份"}？`))return;del.disabled=true;del.textContent="删除中…";try{await plugin.deleteBackup({backupDir:item.path||item.name});savesStatus.textContent="已删除备份。";await refreshSaves()}catch(e){savesStatus.textContent="删除失败："+(e&&e.message||String(e));del.disabled=false;del.textContent="删除"}};actions.append(restore,del);row.append(name,meta,actions);savesList.append(row)});savesStatus.textContent=`共 ${backups.length} 个备份。`}catch(e){savesStatus.textContent="读取备份失败："+(e&&e.message||String(e))}}
backupBtn.onclick=async()=>{const pkg=window.__slgSelectionMeta?.packageName||"";if(!pkg)return;backupBtn.disabled=true;backupBtn.textContent="正在备份…";try{await plugin.backupSaves({packageName:pkg});savesStatus.textContent="备份完成。";await refreshSaves()}catch(e){savesStatus.textContent="备份失败："+(e&&e.message||String(e))}finally{updateSavesState()}};
savesCard.append(permissionNote,backupHint,backupBtn,savesStatus,savesList);
const originalBackupClick=backupBtn.onclick;backupBtn.onclick=async()=>{try{return await originalBackupClick()}finally{backupBtn.textContent="\u5907\u4efd\u5f53\u524d\u5b58\u6863"}};
savesView.append(savesTop,savesCard);
const cleanupTop=textNode("header","workshop-task-topbar");const cleanupBack=viewBack("返回菜单",showMenu);cleanupTop.append(cleanupBack,textNode("h1","","清理安装包与旧缓存"));const cleanupCard=textNode("section","workshop-settings-card");const cleanupTitle=textNode("h2","workshop-settings-title","清理安装包与旧缓存");const cleanupStatus=textNode("p","workshop-settings-status","删除已生成的补丁 APK 与旧翻译缓存，释放手机存储空间。");const cleanupBtn=textNode("button","workshop-settings-save","立即清理");cleanupBtn.type="button";const cleanupResult=textNode("p","workshop-settings-status");cleanupBtn.onclick=async()=>{cleanupBtn.disabled=true;cleanupBtn.textContent="正在清理…";try{const r=await window.Capacitor.Plugins.FileManager.cleanupStorage({keepUri:(window.__slgSelectionMeta?.uri)||"",packageName:(window.__slgSelectionMeta?.packageName)||""});cleanupResult.textContent=`已清理 ${formatBytes(r&&r.freedBytes)} ，删除 ${(r&&r.deletedCount)||0} 个文件`}catch(e){cleanupResult.textContent="清理失败："+(e&&e.message||String(e))}finally{cleanupBtn.disabled=false;cleanupBtn.textContent="立即清理"}};cleanupCard.append(cleanupTitle,cleanupStatus,cleanupBtn,cleanupResult);cleanupView.append(cleanupTop,cleanupCard);
const aboutTop=textNode("header","workshop-task-topbar");const aboutBack=viewBack("返回菜单",showMenu);aboutTop.append(aboutBack,textNode("h1","","关于"));const aboutCard=textNode("section","workshop-settings-card");aboutCard.append(textNode("h2","workshop-settings-title","SLG 翻译器"),textNode("p","workshop-settings-helper","版本：Android v1.0.7"),textNode("p","workshop-settings-helper","把喜欢的游戏，用中文继续。"));aboutView.append(aboutTop,aboutCard);
service.onclick=()=>showView(serviceView);saves.onclick=()=>{showView(savesView);refreshSaves()};cleanup.onclick=()=>showView(cleanupView);about.onclick=()=>showView(aboutView);settingsShell.append(menuView,serviceView,savesView,cleanupView,aboutView);runtimeRoot?.append(settingsShell)}showMenu();settingsShell.hidden=false;if(shell)shell.hidden=true}
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
function sourceText(){const root=document.querySelector("#root");if(!root)return"";const clone=root.cloneNode(true);clone.querySelector(".workshop-task-shell")?.remove();clone.querySelector(".workshop-bottom-nav")?.remove();clone.querySelector(".workshop-source-dialog")?.remove();clone.querySelector(".workshop-installed-dialog")?.remove();clone.querySelector(".workshop-settings-shell")?.remove();clone.querySelector(".workshop-gallery-shell")?.remove();return clone.textContent||""}
function readProgressLog(){const source=[...document.querySelectorAll("#root [class*='font-mono']")].find(el=>!el.closest(".workshop-task-shell")&&el.children.length>0);const lines=[...(source?.children||[])].slice(-40).map(row=>(row.innerText||row.textContent||"").trim()).filter(Boolean);return{raw:lines.join("\n"),latest:lines.at(-1)||""}}
function readTaskSnapshot(){const selectionError=window.__slgSelectionError;if(selectionError)return{state:"failed",reason:"scan",fileName:selectionError.fileName||"",raw:selectionError.message};const watchdog=window.__slgScanWatchdog,selectionMeta=window.__slgSelectionMeta,text=sourceText();const selected=text.match(/已选择\s*[:：]?\s*([^\n]{1,180}?)(?=发现|正在|处理|$)/);const fileName=selected?.[1]?.trim()||"";const found=text.match(/发现\s*(\d+)\s*个可翻译文件/),headerCount=text.match(/(?:·\s*)?(\d+)\s*个脚本/);const count=found?.[1]||headerCount?.[1]||"";const progress=text.match(/翻译进度\s*([\d,]+)\s*\/\s*([\d,]+)/)||(readProgressLog().latest.match(/\[(\d+)\/(\d+)\]/))||text.match(/正在处理脚本\s*(\d+)\s*\/\s*(\d+)/);const current=progress?.[1]||"0",total=progress?.[2]||count||"0";const translated=text.match(/共翻译\s*(\d+)\s*条文本/)?.[1]||"";const log=readProgressLog();const failed=[...document.querySelectorAll("#root *")].find(el=>!el.closest(".workshop-task-shell")&&el.textContent?.includes("写入补丁 APK 失败"));if(failed&&/ENOSPC|No space left/i.test(failed.textContent||""))return{state:"failed",reason:"space",raw:failed.textContent};const networkFailed=text.match(/翻译失败\s*[:：]?\s*(无法连接 (?:DeepSeek|OpenAI|自定义接口)。请检查网络，或前往“我的”切换供应商。)/);if(networkFailed)return{state:"failed",reason:"network",raw:networkFailed[1]};if(/翻译完成/.test(text))return{state:"completed",fileName,count,translated,raw:log.raw,latest:log.latest};if(/正在生成 Ren'Py 补丁 APK/.test(text))return{state:"patching",fileName,count,current,total,raw:log.raw,latest:log.latest};if(/正在处理脚本|翻译中|开始处理/.test(text))return{state:"translating",fileName,count,current,total,raw:log.raw,latest:log.latest};if(count==="0"&&watchdog?.epoch===window.__slgSelectionEpoch&&watchdog.settled&&!watchdog.timerFired)return{state:"empty",fileName,count,splitApk:!!selectionMeta?.splitApk,splitCount:selectionMeta?.splitCount||0};if(count!==""&&count!=="0")return{state:"ready",fileName,count};if(fileName||/正在扫描|正在检查文件|检查文件/.test(text))return{state:"scanning",fileName};return{state:"idle"}}
function detailToggle(raw,live=false){const wrap=textNode("div","workshop-detail-wrap");const toggle=textNode("button","workshop-detail-toggle",detailsOpen?"收起详情":"处理详情");toggle.type="button";toggle.setAttribute("aria-expanded",String(detailsOpen));const body=textNode("div","workshop-detail-body",raw||"暂无更多信息");body.dataset.open=String(detailsOpen);const scrollLatest=()=>{if(live&&detailsOpen)window.requestAnimationFrame(()=>{body.scrollTop=body.scrollHeight})};toggle.onclick=()=>{detailsOpen=!detailsOpen;body.dataset.open=String(detailsOpen);toggle.setAttribute("aria-expanded",String(detailsOpen));toggle.textContent=detailsOpen?"收起详情":"处理详情";scrollLatest()};wrap.append(toggle,body);scrollLatest();return wrap}
 function renderTopbar(state){const bar=textNode("header","workshop-task-topbar");const label=state==="scanning"?"读取中":state==="empty"?"无文本":state==="ready"?"已就绪":state==="translating"?"翻译中":state==="patching"?"生成中":state==="completed"?"已完成":state==="failed"?"失败":"";if(state!=="idle"){const back=textNode("button","workshop-task-back","‹ 返回");back.type="button";back.setAttribute("aria-label","返回");back.onclick=()=>setWorkshopState("idle",{fromBack:true});bar.append(back)}bar.append(textNode("h1","","APK 翻译"),textNode("span",`workshop-topbar-state workshop-state-chip workshop-chip-${state}`,label));return bar}
function fileRow(fileName){const row=textNode("div","workshop-file-row");row.append(textNode("span","workshop-file-icon","APK"));const copy=textNode("div","workshop-file-copy");copy.append(textNode("div","workshop-file-name",fileName||"尚未选择 APK"),textNode("div","workshop-file-meta",fileName?"已选择文件":"支持 Android APK 文件"));row.append(copy);return row}
function actionButton(label,handler,secondary){const button=textNode("button",secondary?"workshop-secondary-action":"workshop-primary-action",label);button.type="button";button.onclick=handler;return button}
function renderStateBody(state,payload){function stateIcon(state){const icon=textNode("span",`workshop-state-icon workshop-state-icon-${state}`);if(icon.setAttribute)icon.setAttribute("aria-hidden","true");icon.innerHTML=state==="completed"?'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>':state==="failed"?'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>':state==="ready"?'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 5-5.5"/></svg>':state==="translating"?'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h9"/><path d="M8 3v2"/><path d="M5 11c3-3 6-3 9 0"/><path d="M6 18c4-2 7-1 9 2"/></svg>':state==="patching"?'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/></svg>':'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>';return icon};const body=textNode("div","workshop-task-body");if(state==="idle"){const brand=textNode("section","workshop-brand-panel");brand.append(textNode("p","","今天翻译什么？"),textNode("h2","","让喜欢的故事，用中文继续。"));const steps=textNode("ol","workshop-steps");[["选择","选择游戏或 APK"],["翻译","等待译文生成"],["安装","安装补丁版"]].forEach(([t,n],i)=>{const li=textNode("li","");li.append(textNode("span","workshop-step-index",String(i+1)),textNode("span","workshop-step-copy",t),textNode("span","workshop-step-note",n));steps.append(li)});const card=textNode("section","workshop-task-card");card.append(fileRow(""),textNode("p","workshop-state-copy","选择一个应用或 APK，开始你的中文旅程。"),actionButton("选择应用或 APK",openSourceChooser));body.append(brand,steps,card);return body}
const card=textNode("section",state==="failed"?"workshop-task-card workshop-error-card":"workshop-task-card");card.append(fileRow(payload.fileName));if(state!=="idle")card.append(stateIcon(state));if(state==="scanning"){card.append(textNode("p","workshop-state-copy","正在检查文件"));const progress=textNode("div","workshop-progress");progress.append(textNode("i","",""));card.append(progress,detailToggle(payload.raw||"正在检查 APK 文件，请稍候。"));body.append(card);return body}
if(state==="empty"){const split=payload.splitApk;card.append(textNode("h2","workshop-empty-title",split?"该应用使用拆分安装包":"没有找到可翻译文本"),textNode("p","workshop-state-copy",split?`当前只检查了基础 APK（共 ${payload.splitCount||0} 个拆分包），部分文本资源无法直接读取。可以尝试单个 APK 文件或其他应用。`:"这个应用的基础 APK 中没有可直接翻译的文本资源，可以尝试其他应用或 APK 文件。"));body.append(card,actionButton("重新选择应用或 APK",openSourceChooser));return body}
if(state==="ready"){card.append(textNode("p","workshop-state-copy","可以开始了"));card.append(textNode("p","workshop-settings-status","提示：继续上次只翻译新增文本（推荐）；全部重译会重新调用翻译接口。"));if(payload.apiRequired)card.append(textNode("p","workshop-state-copy","请先配置 API Key"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","可翻译文件"),textNode("span","",`${payload.count||0} 个`));list.append(row);card.append(list,detailToggle(payload.raw||"文件检查已完成。"));body.append(card,actionButton("开始翻译",()=>triggerReactButton(startButton)));return body}
if(state==="translating"){card.append(textNode("p","workshop-state-copy","正在翻译文本"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","脚本进度"),textNode("span","",`${payload.current||0} / ${payload.total||payload.count||0}`));list.append(row);const progress=textNode("div","workshop-progress");const fill=textNode("i","","");const current=Number(payload.current)||0,total=Number(payload.total)||0;const pct=total?Math.max(2,Math.min(100,Math.round(current/total*100))):0;fill.style.width=`${pct}%`;progress.append(fill,textNode("span","workshop-progress-label",`${pct}%`));card.append(list,progress);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"正在翻译脚本文本，请保持应用在前台。",true));body.append(card);return body}
if(state==="patching"){card.append(textNode("p","workshop-state-copy","正在生成补丁 APK"));const progress=textNode("div","workshop-progress");progress.append(textNode("i","",""));progress.append(textNode("span","workshop-progress-label","正在写入补丁…"));card.append(progress);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"译文本已经完成，正在写入并签名补丁 APK。",true));body.append(card);return body}
if(state==="completed"){card.append(textNode("p","workshop-state-copy","补丁 APK 已生成"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","已翻译文本"),textNode("span","",`${payload.translated||0} 条`));list.append(row);const countRow=textNode("li","workshop-summary-row");countRow.append(textNode("span","","可翻译文件"),textNode("span","",`${payload.count||0} 个`));list.append(countRow);card.append(list);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"翻译和补丁写入已经完成。",true));body.append(card,actionButton("安装补丁版",()=>triggerReactButton(installButton)));return body}
if(payload.reason==="scan"){const title=textNode("h2","workshop-error-title","检查失败");const copy=textNode("p","workshop-state-copy","无法读取这个 APK。请重新选择应用或文件。");card.append(title,copy,detailToggle(payload.raw||"APK scan failed"));body.append(card,actionButton("重试扫描",()=>retryTask({fileName:payload.fileName,raw:""})),actionButton("从文件选择 APK",()=>triggerReactButton(sourceButton),true));return body}
if(payload.reason==="network"){const title=textNode("h2","workshop-error-title","无法连接翻译服务");const copy=textNode("p","workshop-state-copy",payload.raw||"请检查网络，或切换翻译供应商后重试。");card.append(title,copy,detailToggle(payload.raw||"Network failure"));body.append(card,actionButton("前往“我的”切换供应商",openSettings),actionButton("重试翻译",()=>retryTask({fileName:payload.fileName,raw:""}),true));return body}
const title=textNode("h2","workshop-error-title","手机空间不足");const copy=textNode("p","workshop-state-copy","请释放空间后重试。"),details=detailToggle(payload.raw||"ENOSPC|No space left");card.append(title,copy,details);body.append(card,actionButton("释放空间后重试",()=>retryTask({fileName:payload.fileName,raw:""})),actionButton("重新选择 APK",()=>triggerReactButton(sourceButton),true));return body}
function setWorkshopState(state,payload={}){if(!shell)return;shell.dataset.workshopState=state;shell.setAttribute("data-workshop-state",state);shell.dataset.workshopTask=state==="idle"?"idle":"active";const task=shell.dataset.workshopTask;shell.setAttribute("data-workshop-task",shell.dataset.workshopTask);runtimeRoot?.setAttribute("data-workshop-state",state);runtimeRoot?.setAttribute("data-workshop-task",task);shell.classList.remove("workshop-state-idle","workshop-state-scanning","workshop-state-empty","workshop-state-ready","workshop-state-translating","workshop-state-patching","workshop-state-completed","workshop-state-failed");shell.classList.add(`workshop-state-${state}`);runtimeRoot?.classList.remove("workshop-state-idle","workshop-state-scanning","workshop-state-empty","workshop-state-ready","workshop-state-translating","workshop-state-patching","workshop-state-completed","workshop-state-failed");runtimeRoot?.classList.add(`workshop-state-${state}`);shell.replaceChildren(renderTopbar(state),renderStateBody(state,payload))}
function snapshotKey(s){return[s.state,s.fileName||"",s.count||"",s.current||"",s.total||"",s.translated||"",s.reason||"",s.splitApk?`split-${s.splitCount||0}`:"",s.raw||""].join("|")}
function retryScanTask(payload){const selection=window.__slgSelectionMeta;if(!selection?.uri||typeof window.__slgLoadSelectedApk!=="function"){triggerReactButton(sourceButton);return}retrying=true;let pending;try{pending=window.__slgLoadSelectedApk(selection);setWorkshopState("scanning",{...payload,fileName:selection.name||selection.label||payload?.fileName||""})}catch(error){retrying=false;window.__slgSelectionError={message:error?.message||String(error),fileName:selection.name||selection.label||""};setWorkshopState("failed",{...payload,reason:"scan",fileName:selection.name||selection.label||"",raw:window.__slgSelectionError.message});return}Promise.resolve(pending).catch(()=>{}).finally(()=>{retrying=false;lastSnapshot="";refresh()})}
function retryTask(payload){if(payload?.reason==="scan"){retryScanTask(payload);return}retrying=true;triggerReactButton(startButton||sourceButton);setWorkshopState("scanning",payload);window.setTimeout(()=>{retrying=false;refresh()},600)}
function refresh(){if(!shell||retrying||settingsOpen)return;const snap=readTaskSnapshot();const active=snap.state==='scanning'||snap.state==='translating'||snap.state==='patching'||snap.state==='completed'||snap.state==='failed';if(manualIdle&&!active)return;if(snap.state==='translating'){try{const now=Date.now();if(now-sessionLastBeat>=10000){sessionLastBeat=now;const raw=localStorage.getItem(SESSION_KEY);if(raw){const ss=JSON.parse(raw);ss.translating=true;ss.savedAt=now;localStorage.setItem(SESSION_KEY,JSON.stringify(ss))}}}catch{}}const key=snapshotKey(snap);if(key===lastSnapshot)return;lastSnapshot=key;setWorkshopState(snap.state,snap)}
 function decorate(){const heading=[...document.querySelectorAll("#root h2")].find(el=>el.textContent&&el.textContent.includes("选择游戏 APK"));if(heading?.parentElement)heading.parentElement.classList.add("workshop-picker-source");startButton=findButton("开始翻译");if(startButton){startButton.classList.add("workshop-start-button");startButton.setAttribute("aria-hidden","true")}installButton=findButton("安装补丁版");if(installButton)installButton.setAttribute("aria-hidden","true");sourceButton=findButton("选择");if(sourceButton){sourceButton.classList.add("workshop-source-button");sourceButton.setAttribute("aria-label","选择 APK 文件");sourceButton.setAttribute("aria-hidden","true")}applyApiKeyToReact()}

function formatBytes(bytes){const value=Number(bytes)||0;if(value<1024)return`${value} B`;const units=["KB","MB","GB"];let n=value/1024,unit=0;while(n>=1024&&unit<units.length-1){n/=1024;unit+=1}return`${n>=100?Math.round(n):Math.round(n*10)/10} ${units[unit]}`}
function openGallery(){armModalHistory();galleryOpen=true;manualIdle=true;if(!galleryPrevNav){const nav0=document.querySelector(".workshop-bottom-nav");galleryPrevNav=nav0?.querySelector("button[aria-current=page]")?.textContent||"首页"}const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes("\u5b89\u88c5\u5305"))?.setAttribute("aria-current","page")}if(!galleryShell){galleryShell=textNode("section","workshop-gallery-shell");galleryShell.hidden=true;galleryShell.setAttribute("role","dialog");galleryShell.setAttribute("aria-modal","true");galleryShell.setAttribute("aria-label","\u6211\u7684\u8865\u4e01");const top=textNode("header","workshop-task-topbar");const back=textNode("button","workshop-task-back","\u2039 \u8fd4\u56de");back.type="button";back.setAttribute("aria-label","\u8fd4\u56de\u4efb\u52a1");back.onclick=closeGallery;top.append(back,textNode("h1","","\u6211\u7684\u8865\u4e01"));const refresh=textNode("button","workshop-secondary-action","\u5237\u65b0");refresh.type="button";refresh.onclick=loadPatches;const list=textNode("div","workshop-gallery-content");galleryShell.append(top,list,refresh);runtimeRoot?.append(galleryShell)}galleryShell.hidden=false;if(shell)shell.hidden=true;loadPatches()}
function closeGallery(preserveHistory=false){galleryOpen=false;manualIdle=false;lastSnapshot="";if(galleryShell)galleryShell.hidden=true;if(shell)shell.hidden=false;const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes(galleryPrevNav||"首页"))?.setAttribute("aria-current","page")}if(!preserveHistory)releaseModalHistory();refresh()}
function renderGallery(){if(!galleryShell)return;const list=galleryShell.querySelector(".workshop-gallery-content");if(!list)return;list.replaceChildren();if(galleryLoading){list.append(textNode("p","workshop-gallery-status","\u6b63\u5728\u8bfb\u53d6\u8865\u4e01\u5217\u8868\u2026"));return}if(galleryError){list.append(textNode("p","workshop-gallery-status workshop-installed-error","\u8bfb\u53d6\u5931\u8d25\uff1a"+galleryError));return}if(!galleryPatches.length){const empty=textNode("div","workshop-empty-state");const eicon=textNode("span","workshop-empty-icon");if(eicon.setAttribute)eicon.setAttribute("aria-hidden","true");eicon.innerHTML='<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/></svg>';empty.append(eicon,textNode("h2","workshop-empty-title","\u8fd8\u6ca1\u6709\u8865\u4e01"),textNode("p","workshop-gallery-status","\u8fd8\u6ca1\u6709\u8865\u4e01 APK\u3002\u7ffb\u8bd1\u5b8c\u6210\u540e\uff0c\u8865\u4e01\u4f1a\u81ea\u52a8\u51fa\u73b0\u5728\u8fd9\u91cc\u3002"));list.append(empty);return}const rows=textNode("ul","workshop-gallery-list");for(const patch of galleryPatches){const item=textNode("li","");const card=textNode("div","workshop-patch-row");const head=textNode("div","workshop-patch-head");const picon=textNode("span","workshop-patch-icon");if(picon.setAttribute)picon.setAttribute("aria-hidden","true");picon.innerHTML='<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/></svg>';const copy=textNode("div","workshop-patch-copy");copy.append(textNode("div","workshop-patch-name",patch.name||"\u672a\u547d\u540d\u8865\u4e01"));copy.append(textNode("div","workshop-patch-meta",`${formatBytes(patch.size)} \u00b7 ${new Date(patch.modifiedAt||Date.now()).toLocaleString()}`));head.append(picon,copy);const save=actionButton("\u4fdd\u5b58\u5230\u4e0b\u8f7d",()=>savePatchedApk(patch.path));save.className="workshop-patch-save";card.append(head,save);item.append(card);rows.append(item)}list.append(rows)}async function loadPatches(){const plugin=window.Capacitor?.Plugins?.FileManager;galleryLoading=true;galleryError="";renderGallery();if(!plugin?.listPatchedApks){galleryLoading=false;galleryError="\u5f53\u524d\u7248\u672c\u4e0d\u652f\u6301\u8bfb\u53d6\u8865\u4e01\u5217\u8868\uff0c\u8bf7\u5347\u7ea7\u5e94\u7528";renderGallery();return}try{const result=await plugin.listPatchedApks();galleryPatches=Array.isArray(result?.patches)?result.patches:[]}catch(error){galleryError=error?.message||String(error)}finally{galleryLoading=false;renderGallery()}}
function enableNativeBackHandling(){if(nativeBackEnabled||nativeBackPending)return;const plugin=window.Capacitor?.Plugins?.FileManager;if(!plugin?.enableWorkshopBackHandling)return;nativeBackPending=true;Promise.resolve(plugin.enableWorkshopBackHandling()).then(()=>{nativeBackEnabled=true}).catch(()=>{}).finally(()=>{nativeBackPending=false})}
function mount(){decorate();enableNativeBackHandling();if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;const app=document.querySelector("#root>div");if(!app||!sourceButton)return;runtimeRoot=app;if(!shell){app.classList.add(ID);shell=document.createElement("section");shell.className="workshop-task-shell";shell.dataset.workshopState="idle";shell.dataset.workshopTask="idle";app.prepend(shell);const nav=document.createElement("nav");nav.className="workshop-bottom-nav";nav.setAttribute("aria-label","主导航");const NAV_ICONS=['<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2Z"/></svg>','<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/></svg>','<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>'];[["首页",()=>window.scrollTo({top:0,behavior:"smooth"})],["安装包",openGallery],["我的",openSettings]].forEach(([label,action],index)=>{const button=textNode("button","workshop-touch",label);button.type="button";const icon=document.createElement("span");icon.className="workshop-nav-icon";icon.setAttribute("aria-hidden","true");icon.innerHTML=NAV_ICONS[index]||"";const name=textNode("span","workshop-nav-label",label);button.append(icon,name);if(index===0)button.setAttribute("aria-current","page");button.onclick=()=>{[...nav.children].forEach(el=>el.removeAttribute("aria-current"));button.setAttribute("aria-current","page");action()};nav.append(button)});app.append(nav);setWorkshopState("idle",{})}refresh()}
function handleWorkshopPopState(){if(modalHistoryClosing){modalHistoryClosing=false;if(modalHistoryRearm){modalHistoryRearm=false;armModalHistory()}return}if(installedDialog&&!installedDialog.hidden){modalHistoryArmed=false;closeInstalledApps(true);return}if(sourceDialog&&!sourceDialog.hidden){modalHistoryArmed=false;closeSourceChooser(true);return}if(settingsOpen){modalHistoryArmed=false;closeSettings(true);return}if(galleryOpen){modalHistoryArmed=false;closeGallery(true);return}if(shell?.dataset.workshopTask==="active"){manualIdle=true;setWorkshopState("idle",{fromBack:true})}}
function schedule(){clearTimeout(debounceTimer);debounceTimer=setTimeout(mount,120)}
window.__slgHandleAndroidBack=()=>{if(installedDialog&&!installedDialog.hidden){closeInstalledApps();return true}if(sourceDialog&&!sourceDialog.hidden){closeSourceChooser();return true}if(settingsOpen){closeSettings();return true}if(galleryOpen){closeGallery();return true}return false};
document.addEventListener("click",event=>{if(event.target.closest?.(".workshop-task-back"))manualIdle=true},{capture:true});observer=new MutationObserver(schedule);observer.observe(document.querySelector("#root")||document.documentElement,{childList:true,subtree:true,characterData:true});window.addEventListener("popstate",handleWorkshopPopState);document.readyState==="loading"?document.addEventListener("DOMContentLoaded",mount):mount()})();
"""


def patch_scan_flow(js: str) -> str:
    start_marker = ",xe=async()=>{"
    end_marker = ",Se=async()=>{"
    start = js.find(start_marker)
    end = js.find(end_marker, start)
    if start < 0 or end < 0:
        raise ValueError("APK scan flow signature not found")
    old_flow = js[start:end]
    if js.count(old_flow) != 1:
        raise ValueError("APK scan flow signature is not unique")
    patched = js.replace(old_flow, SCAN_FLOW, 1)
    normalize_marker = "scanSelectedApk=async(e,selectionEpoch)=>{"
    normalize_replacement = (
        "normalizeSelection=e=>{const s=e||{};const splitUris=Array.isArray(s.splitUris)?s.splitUris:[];"
        "const splitNames=Array.isArray(s.splitNames)?s.splitNames:[];s.uri=s.uri||\"\";"
        "s.baseUri=s.baseUri||s.uri;s.splitUris=splitUris;s.splitNames=splitNames;"
        "s.splitCount=Number(s.splitCount??splitUris.length??0);s.packageName=s.packageName||\"\";"
        "s.versionCode=s.versionCode??\"\";s.source=s.source===\"installed\"||(!s.source&&s.packageName)?\"installed\":\"file\";"
        "return s},mergeSelectionMetadata=(current,update)=>{const previous=current||{},next=update||{},s=Object.assign({},previous,next);"
        "const nextSplitUris=Array.isArray(next.splitUris),nextSplitNames=Array.isArray(next.splitNames),"
        "nextSplitCountPresent=next.splitCount!==undefined&&next.splitCount!==null&&next.splitCount!==\"\",nextSplitCount=Number(next.splitCount);"
        "const splitTupleComplete=nextSplitUris&&nextSplitNames&&nextSplitCountPresent&&Number.isInteger(nextSplitCount)&&nextSplitCount>=0&&"
        "next.splitUris.length===next.splitNames.length&&next.splitUris.length===nextSplitCount;"
        "const previousSplitUris=Array.isArray(previous.splitUris)?previous.splitUris:[],previousSplitNames=Array.isArray(previous.splitNames)?previous.splitNames:[],"
        "previousSplitCount=previous.splitCount??previousSplitUris.length;"
        "s.uri=next.uri||previous.uri||\"\";s.baseUri=next.baseUri||previous.baseUri||s.uri;"
        "s.splitUris=splitTupleComplete?next.splitUris:previousSplitUris;s.splitNames=splitTupleComplete?next.splitNames:previousSplitNames;"
        "s.splitCount=splitTupleComplete?nextSplitCount:previousSplitCount;"
        "s.packageName=next.packageName??previous.packageName??\"\";s.versionCode=next.versionCode??previous.versionCode??\"\";"
        "s.source=next.source??previous.source??(next.packageName?\"installed\":\"file\");return s},scanSelectedApk=async(e,selectionEpoch)=>{"
    )
    if patched.count(normalize_marker) != 1:
        raise ValueError("APK scan normalizer signature is not unique")
    patched = patched.replace(normalize_marker, normalize_replacement, 1)
    timeout_timer_marker = "timeoutMs);Promise.resolve().then(promiseFactory)"
    if patched.count(timeout_timer_marker) != 1:
        raise ValueError("APK scan timeout timer signature is not unique")
    patched = patched.replace(
        timeout_timer_marker,
        "timeoutMs);watchdog.timerId=timer;Promise.resolve().then(promiseFactory)",
        1,
    )
    # Normalize the installed-app payload once so every native call receives
    # the constrained APK-set shape.  The base URI remains for old bridges.
    patched = patched.replace(
        "window.__slgSelectionMeta=e,r(e.uri)",
        "window.__slgSelectionMeta=Object.assign(e,{baseUri:e.baseUri||e.uri,splitUris:Array.isArray(e.splitUris)?e.splitUris:[],splitNames:Array.isArray(e.splitNames)?e.splitNames:[],splitCount:Number(e.splitCount||e.splitUris?.length||0)}),e=window.__slgSelectionMeta,e.splitCount&&O(`已复制基础 APK 与 ${e.splitCount} 个 split，准备合并扫描`,`info`),r(e.uri)",
        1,
    )
    patched = patched.replace(
        "loadSelectedApk=window.__slgLoadSelectedApk=e=>{try{globalThis.localStorage?.setItem",
        "loadSelectedApk=window.__slgLoadSelectedApk=e=>{e=normalizeSelection(e),window.__slgSelectionMeta=e,window.__slgScanWatchdog?.timerId&&window.clearTimeout(window.__slgScanWatchdog.timerId);try{globalThis.localStorage?.setItem",
        1,
    )
    patched = patched.replace(
        "let t=await E.listApkEntries({uri:e.uri});",
        "let t=await E.listApkEntries({uri:e.uri,baseUri:e.baseUri||e.uri,splitUris:e.splitUris||[],splitNames:e.splitNames||[],packageName:e.packageName||'',versionCode:e.versionCode});",
        1,
    )
    patched = patched.replace(
        "e.splitApk&&O(`该应用使用拆分安装包（${e.splitCount||0}个拆分包），当前先扫描基础 APK，部分资源可能无法读取。`,`info`);",
        "e.splitCount&&O(`已准备基础 APK + ${e.splitCount} 个 split，将逐个复制并合并扫描。`,`info`);",
        1,
    )
    patched = patched.replace(
        "JSON.stringify({uri:e.uri,name:e.name||e.label,packageName:e.packageName||'',source:e.source||'',savedAt:Date.now(),translating:false})",
        "JSON.stringify({uri:e.uri,baseUri:e.baseUri||e.uri,splitUris:e.splitUris||[],splitNames:e.splitNames||[],splitCount:e.splitCount||0,name:e.name||e.label,packageName:e.packageName||'',versionCode:e.versionCode,source:e.source||'',savedAt:Date.now(),translating:false})",
        1,
    )
    patched = patched.replace(
        "scanSelectedApk=async(e,selectionEpoch)=>{window.__slgSelectionError=null,",
        "scanSelectedApk=async(e,selectionEpoch)=>{window.__slgFontPreflightDone=false,window.__slgFontPreflightBlocked=false,window.__slgFontPreflightReport=null,window.__slgRenpyCompatibilityPreflightDone=false,window.__slgRenpyCompatibilityReport=null,window.__slgRenpyCompatibilityRecords=[],window.__slgRenpyCompatibilityBlocked=false,window.__slgSelectionError=null,",
        1,
    )
    patched = patched.replace(
        "window.__slgRenpyLanguages=t.renpyLanguages||[],window.__slgRenpyMenuType=t.renpyMenuType||`none`,window.__slgTranslatorLang=''",
        "window.__slgRenpyLanguages=t.renpyLanguages||[],window.__slgRenpyMenuType=t.renpyMenuType||`none`,window.__slgRenpyCompatibilityReport=t.compatibilityReport||null,window.__slgRenpyCompatibilityGate=t.compatibilityGate||`blocked`,window.__slgTranslatorLang=''",
        1,
    )
    patched = patched.replace(
        "window.__slgTranslatorLang='',window.__slgRenpyLang=",
        "window.__slgTranslatorLang='',window.__slgMenuInjectedForRefresh=false,window.__slgRenpyLang=",
        1,
    )
    # Start every scan in the conservative mode. A standard Ren'Py menu is
    # promoted to selectable only after the native injector reports ready;
    # all other outcomes remain always-on.
    patched = patched.replace(
        "):``,s(t.entries)",
        "):``,window.__slgActivationMode=`always_on`,window.__slgCompiledPath=``,s(t.entries)",
        1,
    )
    patched = patched.replace(
        "window.__slgTranslatorLang=(_m&&_m.ready)?'slgtranslated':''",
        "window.__slgTranslatorLang=(_m&&_m.ready)?'slgtranslated':'',window.__slgActivationMode=(_m&&_m.ready)?`selectable`:`always_on`",
        1,
    )
    patched = patched.replace(
        "catch{window.__slgTranslatorLang=''}}",
        "catch{window.__slgTranslatorLang='';window.__slgActivationMode=`always_on`}}",
        1,
    )
    return patched

def patch_saves_runtime(js: str) -> str:
    open_old = 'function openSettings(){armModalHistory();settingsOpen=true;manualIdle=true;reactApiInput=reactApiInput||findReactApiInput();if(!settingsPrevNav){const nav=document.querySelector(".workshop-bottom-nav");settingsPrevNav=nav?.querySelector("button[aria-current=page]")?.textContent||"首页"}const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes("我的"))?.setAttribute("aria-current","page")}let menuView=null,serviceView=null,savesView=null,cleanupView=null,aboutView=null;const showMenu=()=>{if(menuView)menuView.hidden=false;if(serviceView)serviceView.hidden=true;if(savesView)savesView.hidden=true;if(cleanupView)cleanupView.hidden=true;if(aboutView)aboutView.hidden=true};const showView=(v)=>{if(!menuView)return;menuView.hidden=true;serviceView.hidden=v!==serviceView;savesView.hidden=v!==savesView;cleanupView.hidden=v!==cleanupView;aboutView.hidden=v!==aboutView};if(!settingsShell){settingsShell=document.createElement("section");settingsShell.className="workshop-settings-shell";settingsShell.setAttribute("role","dialog");settingsShell.setAttribute("aria-modal","true");settingsShell.setAttribute("aria-label","我的设置");function makeView(){const v=textNode("section","workshop-settings-view");v.hidden=true;return v}function viewBack(label,handler){const b=textNode("button","workshop-task-back","‹ 返回");b.type="button";b.setAttribute("aria-label",label);b.onclick=handler;return b}menuView=makeView();serviceView=makeView();savesView=makeView();cleanupView=makeView();aboutView=makeView();const menuTop=textNode("header","workshop-task-topbar");const back=viewBack("返回任务",closeSettings);menuTop.append(back,textNode("h1","","我的设置"));const menu=textNode("div","workshop-settings-menu");function makeMenuItem(label,desc){const row=textNode("button","workshop-menu-item");row.type="button";const name=textNode("span","workshop-menu-item-label",label);const note=textNode("span","workshop-menu-item-desc",desc||"");const arrow=textNode("span","workshop-menu-item-arrow","›");row.append(name,note,arrow);return row}const service=makeMenuItem("翻译服务","配置 AI 供应商与 API Key");const saves=makeMenuItem("存档转移","备份与恢复游戏存档");const cleanup=makeMenuItem("清理安装包与旧缓存","释放手机存储空间");cleanup.classList.add("workshop-settings-cleanup");const about=makeMenuItem("关于","版本信息");menu.append(service,saves,cleanup,about);menuView.append(menuTop,menu);'
    open_new = 'function openSettings(){armModalHistory();settingsOpen=true;manualIdle=true;reactApiInput=reactApiInput||findReactApiInput();if(!settingsPrevNav){const nav=document.querySelector(".workshop-bottom-nav");settingsPrevNav=nav?.querySelector("button[aria-current=page]")?.textContent||"首页"}const nav=document.querySelector(".workshop-bottom-nav");if(nav){[...nav.children].forEach(el=>el.removeAttribute("aria-current"));[...nav.children].find(el=>el.textContent?.includes("我的"))?.setAttribute("aria-current","page")}let menuView=null,serviceView=null,savesView=null,importView=null,cleanupView=null,aboutView=null;const showMenu=()=>{if(menuView)menuView.hidden=false;if(serviceView)serviceView.hidden=true;if(savesView)savesView.hidden=true;if(cleanupView)cleanupView.hidden=true;if(aboutView)aboutView.hidden=true;if(importView)importView.hidden=true};const showView=(v)=>{if(!menuView)return;menuView.hidden=true;serviceView.hidden=v!==serviceView;savesView.hidden=v!==savesView;cleanupView.hidden=v!==cleanupView;aboutView.hidden=v!==aboutView;importView.hidden=v!==importView};if(!settingsShell){settingsShell=document.createElement("section");settingsShell.className="workshop-settings-shell";settingsShell.setAttribute("role","dialog");settingsShell.setAttribute("aria-modal","true");settingsShell.setAttribute("aria-label","我的设置");function makeView(){const v=textNode("section","workshop-settings-view");v.hidden=true;return v}function viewBack(label,handler){const b=textNode("button","workshop-task-back","‹ 返回");b.type="button";b.setAttribute("aria-label",label);b.onclick=handler;return b}menuView=makeView();serviceView=makeView();savesView=makeView();importView=makeView();cleanupView=makeView();aboutView=makeView();const menuTop=textNode("header","workshop-task-topbar");const back=viewBack("返回任务",closeSettings);menuTop.append(back,textNode("h1","","我的设置"));const menu=textNode("div","workshop-settings-menu");function makeMenuItem(label,desc){const row=textNode("button","workshop-menu-item");row.type="button";const name=textNode("span","workshop-menu-item-label",label);const note=textNode("span","workshop-menu-item-desc",desc||"");const arrow=textNode("span","workshop-menu-item-arrow","›");row.append(name,note,arrow);return row}const service=makeMenuItem("翻译服务","配置 AI 供应商与 API Key");const saves=makeMenuItem("存档转移","保存与分享游戏存档");const importItem=makeMenuItem("导入存档","从下载目录导入游戏存档");const cleanup=makeMenuItem("清理安装包与旧缓存","释放手机存储空间");cleanup.classList.add("workshop-settings-cleanup");const about=makeMenuItem("关于","版本信息");menu.append(service,saves,importItem,cleanup,about);menuView.append(menuTop,menu);'
    if js.count(open_old) != 1:
        raise ValueError("openSettings view signature not found")
    js = js.replace(open_old, open_new, 1)
    menu_make_pat = re.compile(r'function makeMenuItem\(label,desc\)\{const row=textNode\("button","workshop-menu-item"\);row\.type="button";const name=textNode\("span","workshop-menu-item-label",label\);const note=textNode\("span","workshop-menu-item-desc",desc\|\|""\);const arrow=textNode\("span","workshop-menu-item-arrow","[^"]*"\);row\.append\(name,note,arrow\);return row\}')
    menu_make_new = 'function makeMenuItem(label,desc,icon){const row=textNode("button","workshop-menu-item");row.type="button";const iconBox=textNode("span","workshop-menu-icon");if(iconBox.setAttribute)iconBox.setAttribute("aria-hidden","true");iconBox.innerHTML=icon||"";const copy=textNode("span","workshop-menu-copy");copy.append(textNode("span","workshop-menu-item-label",label),textNode("span","workshop-menu-item-desc",desc||""));const arrow=textNode("span","workshop-menu-item-arrow","›");row.append(iconBox,copy,arrow);return row}'
    js, _n = menu_make_pat.subn(menu_make_new, js, count=1)
    if _n != 1:
        raise ValueError("settings menu item signature not found")
    _menu_icons = {
        '翻译服务': '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h9"/><path d="M8 3v2"/><path d="M5 11c3-3 6-3 9 0"/><path d="M6 18c4-2 7-1 9 2"/></svg>',
        '存档转移': '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>',
        '导入存档': '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21V9"/><path d="m7 14 5-5 5 5"/><path d="M5 3h14"/></svg>',
        '清理安装包与旧缓存': '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>',
        '关于': '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>',
    }
    for _label, _icon in _menu_icons.items():
        _call_pat = re.compile(r'(makeMenuItem\("' + _label + r'","[^"]*"\))')
        js, _n = _call_pat.subn(lambda _m: _m.group(1)[:-1] + ',`' + _icon + '`)', js, count=1)
        if _n != 1:
            raise ValueError("settings menu icon not found: " + _label)


    saves_old = 'const backupHint=textNode("p","workshop-settings-helper","请先选择游戏。");\nconst backupBtn=textNode("button","workshop-settings-save","备份当前存档");\nbackupBtn.type="button";\nconst savesList=textNode("div","workshop-saves-list");\nconst savesEmpty=textNode("p","workshop-saves-empty","暂无备份。");\nsavesList.append(savesEmpty);\nconst updateSavesState=()=>{const pkg=window.__slgSelectionMeta?.packageName||"";const ready=!!pkg&&!!plugin;backupBtn.disabled=!ready;backupHint.textContent=!pkg?"请先选择游戏。":"备份保存到本机应用目录。";if(/Android\\s+(1[1-9]|[2-9][0-9])/i.test(navigator.userAgent)){permissionNote.textContent="请在系统设置中授予“所有文件访问”权限后，再进行备份或恢复。"}else{permissionNote.hidden=true}};\nupdateSavesState();\nasync function refreshSaves(){if(!plugin){savesStatus.textContent="当前版本不支持存档转移。";return}savesStatus.textContent="正在读取备份…";try{const result=await plugin.listSaveBackups();savesList.replaceChildren();const backups=Array.isArray(result?.backups)?result.backups:[];if(!backups.length){savesList.append(savesEmpty);savesEmpty.textContent="暂无备份。";savesStatus.textContent="";return}backups.forEach(item=>{const row=textNode("article","workshop-save-row");const name=textNode("div","workshop-save-name",item.name||"未命名备份");const meta=textNode("div","workshop-save-meta",`${item.fileCount||0} 个文件 · ${new Date(item.modifiedAt||Date.now()).toLocaleString()}`);const actions=textNode("div","workshop-save-actions");const restore=textNode("button","workshop-save-restore","恢复");restore.type="button";const del=textNode("button","workshop-save-delete","删除");del.type="button";restore.onclick=async()=>{if(!confirm(`恢复 ${item.name||"该备份"} 会覆盖当前存档，确定继续？`))return;restore.disabled=true;restore.textContent="恢复中…";try{await plugin.restoreSaves({packageName:window.__slgSelectionMeta?.packageName||"",backupDir:item.path||item.name});savesStatus.textContent="恢复完成。"}catch(e){savesStatus.textContent="恢复失败："+(e&&e.message||String(e))}finally{restore.disabled=false;restore.textContent="恢复"}};del.onclick=async()=>{if(!confirm(`确定删除备份 ${item.name||"该备份"}？`))return;del.disabled=true;del.textContent="删除中…";try{await plugin.deleteBackup({backupDir:item.path||item.name});savesStatus.textContent="已删除备份。";await refreshSaves()}catch(e){savesStatus.textContent="删除失败："+(e&&e.message||String(e));del.disabled=false;del.textContent="删除"}};actions.append(restore,del);row.append(name,meta,actions);savesList.append(row)});savesStatus.textContent=`共 ${backups.length} 个备份。`}catch(e){savesStatus.textContent="读取备份失败："+(e&&e.message||String(e))}}\nbackupBtn.onclick=async()=>{const pkg=window.__slgSelectionMeta?.packageName||"";if(!pkg)return;backupBtn.disabled=true;backupBtn.textContent="正在备份…";try{await plugin.backupSaves({packageName:pkg});savesStatus.textContent="备份完成。";await refreshSaves()}catch(e){savesStatus.textContent="备份失败："+(e&&e.message||String(e))}finally{updateSavesState()}};\nsavesCard.append(permissionNote,backupHint,backupBtn,savesStatus,savesList);\nconst originalBackupClick=backupBtn.onclick;backupBtn.onclick=async()=>{try{return await originalBackupClick()}finally{backupBtn.textContent="\\u5907\\u4efd\\u5f53\\u524d\\u5b58\\u6863"}};\nsavesView.append(savesTop,savesCard);'
    saves_new = 'let savesSelectedPkg="",savesSelectedLabel="";\nconst gameLabel=textNode("p","workshop-settings-helper","请先选择游戏。");\nconst gameBtn=textNode("button","workshop-settings-save","选择游戏");\ngameBtn.type="button";\nconst gameSelect=textNode("select","workshop-settings-input");\ngameSelect.hidden=true;gameSelect.style.marginTop="10px";\ngameSelect.setAttribute("aria-label","选择游戏");\nlet saveGameApps=[];\nconst knownSavePackages=new Set(["zitao.mbml","cim.isekai.game","com.yishijietiantang.com","newmanwa.com","com.rogueone.tnt"]);\nfunction saveGameMatches(app){const pkg=app.packageName||"",label=app.label||"";return pkg.includes(".")&&(knownSavePackages.has(pkg)||/renpy|visual\\s*novel|galgame|manwa|isekai|rogueone|恶女/i.test(`${pkg}\\n${label}`))}\nfunction renderSaveGames(apps){\n  gameSelect.replaceChildren();\n  const placeholder=textNode("option","","请选择游戏");placeholder.value="";gameSelect.append(placeholder);\n  for(const app of apps){const option=textNode("option","",app.label||app.packageName||"未命名应用");option.value=app.packageName||"";gameSelect.append(option)}\n  gameSelect.value=savesSelectedPkg;\n}\ngameSelect.onchange=()=>{const pkg=gameSelect.value;if(!pkg)return;const app=saveGameApps.find(a=>a.packageName===pkg)||{packageName:pkg,label:pkg};savesSelectedPkg=pkg;savesSelectedLabel=app.label||pkg;gameLabel.textContent=`当前游戏：${savesSelectedLabel}`;updateSavesState();refreshSaves()};\ngameBtn.onclick=async()=>{gameBtn.disabled=true;gameBtn.textContent="正在读取…";try{const result=plugin.listSaveGameApps?await plugin.listSaveGameApps():await plugin.listInstalledApps();const apps=Array.isArray(result?.apps)?result.apps:[];const fromSaveSource=typeof plugin.listSaveGameApps==="function";saveGameApps=apps.filter(app=>{const pkg=app.packageName||"";return pkg.includes(".")&&(fromSaveSource||saveGameMatches(app))});renderSaveGames(saveGameApps);gameSelect.hidden=false;gameLabel.textContent=saveGameApps.length?`已找到 ${saveGameApps.length} 个游戏，请选择。`:"没有找到已安装的存档目录。";}catch(e){gameLabel.textContent="读取游戏列表失败："+(e&&e.message||String(e))}finally{gameBtn.disabled=false;gameBtn.textContent=savesSelectedPkg?"重新选择游戏":"选择游戏"}};\nconst exportBtn=textNode("button","workshop-settings-save","保存存档");\nexportBtn.type="button";\nconst savesList=textNode("div","workshop-saves-list");\nconst savesEmpty=textNode("p","workshop-saves-empty","暂无备份。");\nsavesList.append(savesEmpty);\nconst updateSavesState=()=>{const pkg=savesSelectedPkg;const ready=!!pkg&&!!plugin;exportBtn.disabled=!ready;gameLabel.textContent=!pkg?"请先选择游戏。":`当前游戏：${savesSelectedLabel||pkg}`;gameBtn.textContent=pkg?"重新选择游戏":"选择游戏";if(gameSelect.options)gameSelect.value=pkg;if(/Android\\s+(1[1-9]|[2-9][0-9])/i.test(navigator.userAgent)){permissionNote.textContent="请在系统设置中授予“所有文件访问”权限后，再进行保存或恢复。"}else{permissionNote.hidden=true}};\nupdateSavesState();\nasync function refreshSaves(){if(!plugin){savesStatus.textContent="当前版本不支持存档转移。";return}savesStatus.textContent="正在读取备份…";try{const result=await plugin.listSaveBackups();savesList.replaceChildren();const backups=Array.isArray(result?.backups)?result.backups:[];if(!backups.length){savesList.append(savesEmpty);savesEmpty.textContent="暂无备份。";savesStatus.textContent="";return}backups.forEach(item=>{const row=textNode("article","workshop-save-row");const name=textNode("div","workshop-save-name",item.name||"未命名备份");const meta=textNode("div","workshop-save-meta",`${item.fileCount||0} 个文件 · ${new Date(item.modifiedAt||Date.now()).toLocaleString()}`);const actions=textNode("div","workshop-save-actions");const restore=textNode("button","workshop-save-restore","恢复");restore.type="button";const share=textNode("button","workshop-save-share","分享");share.type="button";const del=textNode("button","workshop-save-delete","删除");del.type="button";restore.onclick=async()=>{if(!confirm(`恢复 ${item.name||"该备份"} 会覆盖当前存档，确定继续？`))return;restore.disabled=true;restore.textContent="恢复中…";try{await plugin.restoreSaves({packageName:savesSelectedPkg,backupDir:item.path||item.name});savesStatus.textContent="恢复完成。"}catch(e){savesStatus.textContent="恢复失败："+(e&&e.message||String(e))}finally{restore.disabled=false;restore.textContent="恢复"}};share.onclick=async()=>{share.disabled=true;share.textContent="分享中…";try{await plugin.shareSaveBackup({backupDir:item.path||item.name});savesStatus.textContent="已分享存档。"}catch(e){savesStatus.textContent="分享失败："+(e&&e.message||String(e))}finally{share.disabled=false;share.textContent="分享"}};del.onclick=async()=>{if(!confirm(`确定删除备份 ${item.name||"该备份"}？`))return;del.disabled=true;del.textContent="删除中…";try{await plugin.deleteBackup({backupDir:item.path||item.name});savesStatus.textContent="已删除备份。";await refreshSaves()}catch(e){savesStatus.textContent="删除失败："+(e&&e.message||String(e));del.disabled=false;del.textContent="删除"}};actions.append(restore,share,del);row.append(name,meta,actions);savesList.append(row)});savesStatus.textContent=`共 ${backups.length} 个备份。`}catch(e){savesStatus.textContent="读取备份失败："+(e&&e.message||String(e))}}\nexportBtn.onclick=async()=>{const pkg=savesSelectedPkg;if(!pkg)return;exportBtn.disabled=true;exportBtn.textContent="正在保存…";try{const result=await plugin.exportSavesToDownloads({packageName:pkg});savesStatus.textContent=result?.path?`已保存：${result.path}`:"已保存到下载。";}catch(e){savesStatus.textContent="保存失败："+(e&&e.message||String(e))}finally{exportBtn.textContent="保存存档";updateSavesState()}};\nsavesCard.append(permissionNote,gameLabel,gameBtn,gameSelect,exportBtn,savesStatus,savesList);\nsavesView.append(savesTop,savesCard);\nconst importTop=textNode("header","workshop-task-topbar");\nconst importBack=viewBack("返回菜单",showMenu);\nimportTop.append(importBack,textNode("h1","","导入存档"));\nconst importCard=textNode("section","workshop-settings-card");\nimportCard.append(textNode("h2","workshop-settings-title","导入存档"));\nconst importPermission=textNode("p","workshop-settings-helper");\nconst importStatus=textNode("p","workshop-settings-status");\nconst importGameLabel=textNode("p","workshop-settings-helper","请先选择游戏。");\nconst importGameBtn=textNode("button","workshop-settings-save","选择游戏");\nimportGameBtn.type="button";\nconst importGameSelect=textNode("select","workshop-settings-input");\nimportGameSelect.hidden=true;importGameSelect.style.marginTop="10px";importGameSelect.setAttribute("aria-label","选择游戏");\nlet importSelectedPkg="",importSelectedLabel="";\nlet importGameApps=[];\nfunction renderImportGames(apps){importGameSelect.replaceChildren();const placeholder=textNode("option","","请选择游戏");placeholder.value="";importGameSelect.append(placeholder);for(const app of apps){const option=textNode("option","",app.label||app.packageName||"未命名应用");option.value=app.packageName||"";importGameSelect.append(option)}importGameSelect.value=importSelectedPkg}\nimportGameSelect.onchange=()=>{const pkg=importGameSelect.value;if(!pkg)return;const app=importGameApps.find(a=>a.packageName===pkg)||{packageName:pkg,label:pkg};importSelectedPkg=pkg;importSelectedLabel=app.label||pkg;importGameLabel.textContent=`当前游戏：${importSelectedLabel}`;updateImportState()};\nimportGameBtn.onclick=async()=>{importGameBtn.disabled=true;importGameBtn.textContent="正在读取…";try{const result=plugin.listSaveGameApps?await plugin.listSaveGameApps():await plugin.listInstalledApps();const apps=Array.isArray(result?.apps)?result.apps:[];const fromSaveSource=typeof plugin.listSaveGameApps==="function";importGameApps=apps.filter(app=>{const pkg=app.packageName||"";return pkg.includes(".")&&(fromSaveSource||saveGameMatches(app))});renderImportGames(importGameApps);importGameSelect.hidden=false;importGameLabel.textContent=importGameApps.length?`已找到 ${importGameApps.length} 个游戏，请选择。`:"没有找到已安装的存档目录。";}catch(e){importGameLabel.textContent="读取游戏列表失败："+(e&&e.message||String(e))}finally{importGameBtn.disabled=false;importGameBtn.textContent=importSelectedPkg?"重新选择游戏":"选择游戏"}};\nconst importArchiveBtn=textNode("button","workshop-settings-save","导入分享存档");\nimportArchiveBtn.type="button";\nconst importList=textNode("div","workshop-saves-list");\nlet importArchives=[];\nlet importArchiveSection=null;\nfunction renderImportArchiveRows(){\n  if(importArchiveSection){importArchiveSection.hidden=true;try{importArchiveSection.remove()}catch(e){}importArchiveSection=null}\n  if(!importArchives.length)return;\n  const section=textNode("section","workshop-archive-section");\n  const heading=textNode("h3","workshop-archive-title",`下载目录存档（${importArchives.length}）`);\n  section.append(heading);\n  importArchives.forEach(item=>{\n    const row=textNode("article","workshop-save-row");\n    const name=textNode("div","workshop-save-name",item.name||"未命名存档");\n    const size=item.size||0;\n    const sizeLabel=size>1048576?`${(size/1048576).toFixed(1)} MB`:Math.max(1,Math.round(size/1024))+" KB";\n    const meta=textNode("div","workshop-save-meta",`${sizeLabel} · ${new Date(item.modifiedAt||Date.now()).toLocaleString()}`);\n    const importOne=textNode("button","workshop-save-restore","导入");\n    importOne.type="button";\n    const delArchive=textNode("button","workshop-save-delete","删除");\n    delArchive.type="button";\n    importOne.onclick=async()=>{importOne.disabled=true;importOne.textContent="导入中…";try{const result=await plugin.importSaveBackup({path:item.path});if(result?.packageName){importSelectedPkg=result.packageName;const importedApp=importGameApps.find(a=>a.packageName===result.packageName)||{packageName:result.packageName,label:result.packageName};importSelectedLabel=importedApp.label;renderImportGames(importGameApps);importGameLabel.textContent=`当前游戏：${importSelectedLabel}`;updateImportState()}importArchives=importArchives.filter(a=>a!==item);renderImportArchiveRows();importStatus.textContent=result?.packageName?`已导入 ${result.packageName} 的存档。`:"已导入存档。";}catch(e){importStatus.textContent="导入失败："+(e&&e.message||String(e));importOne.disabled=false;importOne.textContent="导入"}};\n    delArchive.onclick=async()=>{if(!confirm(`确定删除存档 ${item.name||"该文件"}？`))return;delArchive.disabled=true;delArchive.textContent="删除中…";try{await plugin.deleteSaveArchive({path:item.path});importArchives=importArchives.filter(a=>a!==item);renderImportArchiveRows();importStatus.textContent=`已删除 ${item.name||"存档"}。`;}catch(e){importStatus.textContent="删除失败："+(e&&e.message||String(e));delArchive.disabled=false;delArchive.textContent="删除"}};\n    row.append(name,meta,importOne,delArchive);\n    section.append(row);\n  });\n  importArchiveSection=section;\n  importList.append(section);\n}\nimportArchiveBtn.onclick=async()=>{importArchiveBtn.disabled=true;importArchiveBtn.textContent="正在读取…";try{const result=await plugin.listSaveArchives();importArchives=Array.isArray(result?.archives)?result.archives:[];renderImportArchiveRows();importStatus.textContent=importArchives.length?`找到 ${importArchives.length} 个存档 zip，已显示在下方面板。`:"下载目录没有找到存档 zip。";}catch(e){importStatus.textContent="读取存档文件失败："+(e&&e.message||String(e))}finally{importArchiveBtn.disabled=false;importArchiveBtn.textContent="重新选择存档"}};\nconst updateImportState=()=>{const pkg=importSelectedPkg;importGameBtn.textContent=pkg?"重新选择游戏":"选择游戏";importGameLabel.textContent=!pkg?"请先选择游戏。":`当前游戏：${importSelectedLabel||pkg}`;if(importGameSelect.options)importGameSelect.value=pkg;if(/Android\\s+(1[1-9]|[2-9][0-9])/i.test(navigator.userAgent)){importPermission.textContent="请在系统设置中授予“所有文件访问”权限后，再导入或恢复。"}else{importPermission.hidden=true}};\nupdateImportState();\nimportCard.append(importPermission,importGameLabel,importGameBtn,importGameSelect,importArchiveBtn,importStatus,importList);\nimportView.append(importTop,importCard);'
    if js.count(saves_old) != 1:
        raise ValueError("saves runtime signature not found")
    js = js.replace(saves_old, saves_new, 1)

    bottom_old = 'service.onclick=()=>showView(serviceView);saves.onclick=()=>{showView(savesView);refreshSaves()};cleanup.onclick=()=>showView(cleanupView);about.onclick=()=>showView(aboutView);settingsShell.append(menuView,serviceView,savesView,cleanupView,aboutView);runtimeRoot?.append(settingsShell)}showMenu();settingsShell.hidden=false;if(shell)shell.hidden=true}'
    bottom_new = 'service.onclick=()=>showView(serviceView);saves.onclick=()=>{showView(savesView);refreshSaves()};importItem.onclick=()=>showView(importView);cleanup.onclick=()=>showView(cleanupView);about.onclick=()=>showView(aboutView);settingsShell.append(menuView,serviceView,savesView,importView,cleanupView,aboutView);runtimeRoot?.append(settingsShell)}showMenu();settingsShell.hidden=false;if(shell)shell.hidden=true}'
    if js.count(bottom_old) != 1:
        raise ValueError("settings shell append signature not found")
    js = js.replace(bottom_old, bottom_new, 1)
    return js
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
        "if(!raw)return;let s=null;try{s=JSON.parse(raw)}catch{}if(!s||!s.uri||!s.translating)return;restoringSession=true;"
        "Promise.resolve(window.__slgLoadSelectedApk?.({uri:s.uri,baseUri:s.baseUri||s.uri,splitUris:Array.isArray(s.splitUris)?s.splitUris:[],splitNames:Array.isArray(s.splitNames)?s.splitNames:[],splitCount:Number(s.splitCount??(Array.isArray(s.splitUris)?s.splitUris.length:0)),name:s.name||s.label||\"\",label:s.label||s.name||\"\",packageName:s.packageName??\"\",versionCode:s.versionCode??\"\",source:s.source||\"installed\",splitApk:false}))"
        ".catch(()=>{}).finally(()=>{restoringSession=false;if(s.translating)sessionRestoredAt=s.savedAt||Date.now();refresh()})}\n"
        "function recoveryBanner(savedAt){const wrap=textNode(\"section\",\"workshop-task-card\");"
        "wrap.append(textNode(\"h2\",\"workshop-settings-title\",\"" "\u4e0a\u6b21\u7ffb\u8bd1\u4e2d\u65ad" "\"),"
        "textNode(\"p\",\"workshop-state-copy\",\"" "\u7ffb\u8bd1\u4f1a\u8bdd\u56e0\u9875\u9762\u5237\u65b0\u4e2d\u65ad\uff0c\u5df2\u5b8c\u6210\u5185\u5bb9\u5df2\u4fdd\u5b58\u5728\u672c\u673a\u7f13\u5b58\u4e2d\u3002" "\"),"
        "textNode(\"p\",\"workshop-state-copy\",`" "\u4e2d\u65ad\u65f6\u95f4\uff1a" "${new Date(savedAt).toLocaleTimeString()}`));"
        "const resume=actionButton(\"" "\u7ee7\u7eed\u4e0a\u6b21\u7ffb\u8bd1" "\",()=>triggerReactButton(startButton));"
        "const dismiss=textNode(\"button\",\"workshop-secondary-action\",\"" "\u653e\u5f03\u6062\u590d" "\");dismiss.type=\"button\";"
        "dismiss.onclick=()=>{try{localStorage.removeItem(SESSION_KEY)}catch{}sessionRestoredAt=0;lastSnapshot=\"\";refresh()};"
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
    snap_new = (r'if(/\u7ffb\u8bd1\u5b8c\u6210/.test(text)&&/\u5199\u5165\u8865\u4e01|\u8865\u4e01 APK \u5df2\u751f\u6210|\u5df2\u751f\u6210\u8865\u4e01/.test(text)){const patchedApkPath=(text.match(/\/[^\s]*patched-signed\.apk/)||[])[0]||"";'
                'const currentInstall=findButton("' + "\u5b89\u88c5\u8865\u4e01\u7248" + '");if(currentInstall)installButton=currentInstall;'
                'const installAvailable=!!currentInstall?.isConnected;'
                'return{state:"completed",fileName,count,translated,patchedApkPath,raw:log.raw,latest:log.latest,installAvailable}}')
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
    snap_guid_old = 'return{state:"completed",fileName,count,translated,patchedApkPath,raw:log.raw,latest:log.latest,installAvailable}}'
    snap_guid_new = ('return{state:"completed",fileName,count,translated,patchedApkPath,'
                     'activationMode:window.__slgActivationMode||\'always_on\',translatorLanguage:window.__slgTranslatorLang||\'\','
                     'compiledPath:window.__slgCompiledPath||\'\',renpyLang:window.__slgRenpyLang||\'\','
                     'renpyMenuType:window.__slgRenpyMenuType||\'\','
                     'raw:log.raw,latest:log.latest,installAvailable}}')
    if runtime.count(snap_guid_old) != 1:
        raise ValueError("Completed snapshot language signature not found")
    runtime = runtime.replace(snap_guid_old, snap_guid_new, 1)

    guide_anchor = 'if(payload.patchedApkPath)card.append(textNode("p","workshop-state-copy workshop-scan-elapsed","' + "\u4f4d\u7f6e\uff1a" + '"+payload.patchedApkPath));'
    guide_new = (
        guide_anchor
        + 'if(payload.activationMode===`selectable`)card.append(textNode("p","workshop-state-copy","' "\u8bf7\u8fdb\u5165\u6e38\u620f\u8bbe\u7f6e\uff0c\u9009\u62e9\u201c\u7ffb\u8bd1\u6587\u672c\u201d\u67e5\u770b\u8bd1\u6587\uff1b\u5141\u8bb8\u5728\u6e38\u620f\u8bbe\u7f6e\u4e2d\u5207\u56de\u539f\u6587" '"));'
        + 'else if(payload.activationMode===`always_on`)card.append(textNode("p","workshop-state-copy","' "\u6b64\u6e38\u620f\u4e0d\u652f\u6301\u53ef\u9760\u7684\u8bed\u8a00\u83dc\u5355\u6ce8\u5165\uff0c\u4e2d\u6587\u7ffb\u8bd1\u5c06\u5728\u542f\u52a8\u65f6\u9ed8\u8ba4\u542f\u7528\uff0c\u6e38\u620f\u5185\u4e0d\u80fd\u5207\u56de\u539f\u6587" '"));'
        + 'else if(payload.renpyLang)card.append(textNode("p","workshop-state-copy","' "\u8bd1\u6587\u8bed\u8a00\uff1a" '"+payload.renpyLang+"' "\u2014\u2014 \u5728\u6e38\u620f\u8bbe\u7f6e\u7684\u8bed\u8a00\u4e2d\u9009\u62e9\u5bf9\u5e94\u9009\u9879\u5373\u53ef\u67e5\u770b\u8bd1\u6587" '"));'
        + 'else if(payload.renpyMenuType==="custom")card.append(textNode("p","workshop-state-copy","' "\u6b64\u6e38\u620f\u4f7f\u7528\u81ea\u5b9a\u4e49\u8bed\u8a00\u7cfb\u7edf\uff0c\u4e0d\u80fd\u901a\u8fc7\u6807\u51c6\u8bed\u8a00\u83dc\u5355\u9009\u62e9\u8bd1\u6587" '"));'
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

    boot_old = ';(()=>{const ID="workshop-runtime";'
    boot_new = (
        ';(()=>{const bootStyle=document.createElement("style");'
        'bootStyle.textContent="#root>div:not(.workshop-runtime)>header,#root>div:not(.workshop-runtime)>nav,#root>div:not(.workshop-runtime)>footer,#root>div:not(.workshop-runtime)>main{display:none!important}";'
        '(document.head||document.documentElement).appendChild(bootStyle);'
        'const ID="workshop-runtime";'
    )
    if runtime.count(boot_old) != 1:
        raise ValueError("Legacy UI boot style signature not found")
    runtime = runtime.replace(boot_old, boot_new, 1)

    mount_wait_old = 'const app=document.querySelector("#root>div");if(!app||!sourceButton)return;'
    mount_wait_new = 'const app=document.querySelector("#root>div");if(!app)return;'
    if runtime.count(mount_wait_old) != 1:
        raise ValueError("Mount source-button wait signature not found")
    runtime = runtime.replace(mount_wait_old, mount_wait_new, 1)
    runtime = enhance_local_runtime(runtime)
    local_rejected_anchor = 'const map=new Map();const warnings=[];let failedBatches=0,splitBatches=0;'
    local_rejected_replacement = 'const map=new Map();const warnings=[],rejected=[];let failedBatches=0,splitBatches=0;'
    if runtime.count(local_rejected_anchor) != 1:
        raise ValueError("Local translation result state signature not found")
    runtime = runtime.replace(local_rejected_anchor, local_rejected_replacement, 1)
    local_rejected_push = 'if(Array.isArray(res&&res.warnings))warnings.push(...res.warnings);'
    local_rejected_push_new = (
        'if(Array.isArray(res&&res.warnings))warnings.push(...res.warnings);'
        'if(Array.isArray(res&&res.rejected))rejected.push(...res.rejected);'
    )
    if runtime.count(local_rejected_push) != 1:
        raise ValueError("Local translation rejection signature not found")
    runtime = runtime.replace(local_rejected_push, local_rejected_push_new, 1)
    local_return = 'return {translations:map,successCount:map.size,warnings};'
    local_return_new = 'return {translations:map,successCount:map.size,warnings,rejected};'
    if runtime.count(local_return) != 1:
        raise ValueError("Local translation return signature not found")
    runtime = runtime.replace(local_return, local_return_new, 1)

    scan_retry_start = runtime.find('if(payload.reason==="scan"){')
    scan_retry_end = runtime.find('if(payload.reason==="network")', scan_retry_start)
    if scan_retry_start < 0 or scan_retry_end < 0:
        raise ValueError("Scan retry state signature not found")
    scan_retry_section = runtime[scan_retry_start:scan_retry_end]
    scan_retry_call = '()=>retryTask({fileName:payload.fileName,raw:""})'
    if scan_retry_section.count(scan_retry_call) != 1:
        raise ValueError("Scan retry action signature is not unique")
    runtime = runtime[:scan_retry_start] + scan_retry_section.replace(
        scan_retry_call,
        '()=>retryTask({reason:"scan",fileName:payload.fileName,raw:""})',
        1,
    ) + runtime[scan_retry_end:]

    return runtime




def patch_translation_cache(js: str) -> str:
    old_state = 'var _o=`slg-translator-cache:`,vo={},yo=!1,bo=!1,bp=Promise.resolve();'
    new_state = 'var _o=`slg-translator-cache:`,vo={},cacheIndex={},_dirty={},yo=!1,bo=!1,bp=Promise.resolve();globalThis.__slgHasHistory=function(pkg){if(!pkg)return false;try{for(const[_k,_v]of Object.entries(vo)){if(_k.startsWith(`slg-file-v1:`)&&_v&&_v.pkg===pkg)return true}return false}catch{return false}};'
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
async function Co(){if(!yo){try{let e=await E.loadTranslationCache();if(e.data&&e.data!==`{}`){let _loaded=JSON.parse(e.data);if(_loaded&&typeof _loaded===`object`){for(const[_k,_v]of Object.entries(_loaded)){if(_v&&typeof _v===`object`)vo[_k]=_v}}} }catch{vo={}}Do(),rebuildCacheIndex(),yo=!0}}
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
        'translatedText:n,updatedAt:Date.now()};vo[i]=r,cacheIndex[cacheIdentity(e,t)]=r,_dirty[i]=r,bo=!0}'
    )
    if js.count(old_lookup) != 1:
        raise ValueError("Translation cache lookup signature not found")
    return js.replace(old_lookup, new_lookup, 1)


def patch_local_engine(js: str) -> str:
    # Add the on-device provider to the React provider list so the settings
    # UI can select it and the React translate flow keeps working untouched.
    old_providers = "_e=[{id:`openai`,"
    local_provider = (
        "_e=[{id:`local`,name:`本机离线翻译（免费）`,baseURL:``,models:["
        "{id:`mlkit`,name:`轻量翻译（ML Kit）`,supportsJsonMode:!1},"
        "{id:`qwen`,name:`高质量翻译（本地模型）`,supportsJsonMode:!1}]},{id:`openai`,"
    )
    if js.count(old_providers) != 1:
        raise ValueError("Local engine provider anchor not found")
    js = js.replace(old_providers, local_provider, 1)

    # Route batch translation to the local kernel when the workshop runtime
    # arms window.__slgLocalTranslate (local engine selected in settings).
    old_lo = (
        "async function Lo(e){let{texts:t,sourceLang:n,targetLang:r,baseURL:i,apiKey:a,"
        "model:o,glossary:s,batchSize:c=jo,onProgress:l}=e;if(await Co(),t.length===0)"
    )
    local_branch = (
        "if(globalThis.__slgLocalTranslate||globalThis.__slgLocalTranslateImpl){let _engine=\"\";try{"
        "const _s=document.querySelector(\"#settingsProvider\");if(_s&&_s.value===\"local\"){"
        "const _m=document.querySelector(\"#settingsModel\");_engine=(_m&&_m.value===\"qwen\")?\"llm\":\"mlkit\"}}catch(_x){}"
        "if(!_engine){try{const _p=JSON.parse(localStorage.getItem(\"slg-workshop-settings-v1\")||\"null\");"
        "if(_p&&_p.providerId===\"local\")_engine=_p.model===\"qwen\"?\"llm\":\"mlkit\"}catch(_x){}}"
        "if(_engine){let _lr=null,_le=null;try{"
        "_lr=await (globalThis.__slgLocalTranslate||globalThis.__slgLocalTranslateImpl)("
        "{texts:t,sourceLang:n,targetLang:r,onProgress:l,engine:_engine});"
        "_lr?.translations&&globalThis.__slgRecordTranslationCandidates?.(t,_lr.translations);"
        "_lr?.translations&&globalThis.__slgRecordValidatorApprovedTranslations?.(t,_lr.translations);"
        "_lr?.rejected&&globalThis.__slgRecordRejectedTranslations?.(_lr.rejected);"
        "}catch(e){_le=e}if(_lr)return _lr;"
        "if(_le)return {translations:new Map(),successCount:0,"
        "warnings:[String(_le&&_le.message||_le)],error:String(_le&&_le.message||_le)}}}"
    )
    new_lo = old_lo.replace("}=e;if(await Co(),t.length===0)", "}=e;" + local_branch + "if(await Co(),t.length===0)")
    if js.count(old_lo) != 1:
        raise ValueError("Local engine Lo anchor not found")
    js = js.replace(old_lo, new_lo, 1)

    # Let the React start button stay enabled when the local engine is
    # selected even without an API key, and let the translation controller
    # skip its apiKey gate in that case. The workshop runtime keeps
    # window.__slgLocalSelected up to date.
    old_disabled = "disabled:se||!te&&!oe"
    new_disabled = "disabled:se||(!te&&!oe&&!window.__slgLocalSelected)"
    if js.count(old_disabled) != 1:
        raise ValueError("Local engine start-button disabled anchor not found")
    js = js.replace(old_disabled, new_disabled, 1)

    old_gate = "if(!n||ae.length===0||!te&&!oe)return;"
    new_gate = "if(!n||ae.length===0||(!te&&!oe&&!window.__slgLocalSelected))return;"
    if js.count(old_gate) != 1:
        raise ValueError("Local engine controller gate anchor not found")
    js = js.replace(old_gate, new_gate, 1)

    return js



def patch_translation_network(js: str) -> str:
    helpers_anchor = 'async function Lo(e){'
    helpers = r'''function isNetworkFailure(e){return networkFailureParts(e).some(e=>/^(?:APIConnectionError|Connection error\.?)$/i.test(e)||/\b(?:ERR_NETWORK|ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT)\b/i.test(e)||/\bnet::ERR_(?:CONNECTION_TIMED_OUT|CONNECTION_REFUSED|INTERNET_DISCONNECTED|NAME_NOT_RESOLVED|CONNECTION_RESET|TIMED_OUT)\b/i.test(e)||/\bDNS_PROBE_FINISHED_NXDOMAIN\b/i.test(e)||/^(?:failed(?: to |-to-)fetch|fetch failed)(?:\b|:)/i.test(e)||/\b(?:offline|dns(?: error| lookup failed)?|timed out|timeout)\b/i.test(e))}
function networkFailureParts(e){let t=[],n=e;for(let r=0;r<4&&n!=null;r++){if(typeof n===`object`){for(const e of[`name`,`code`,`message`])n[e]!=null&&t.push(String(n[e]));n=n.cause}else{t.push(String(n));break}}return t}
function providerLabel(e){return/deepseek/i.test(e)?`DeepSeek`:/openai/i.test(e)?`OpenAI`:`自定义接口`}
function isProviderNetworkFailure(e){return/^无法连接 (?:DeepSeek|OpenAI|自定义接口)。请检查网络，或前往“我的”切换供应商。$/.test(String(e||``))}
globalThis.__slgApiSemaphore={active:0,limit:6,waiters:[],run:async function(fn){if(this.active>=this.limit)await new Promise(r=>this.waiters.push(r));this.active++;try{return await fn()}finally{this.active--;const next=this.waiters.shift();next&&next()}}};async function runFileTasksParallel(e,t,concurrency=2){let i=0,fatal=``;async function worker(){while(i<e.length&&!fatal){let j=i++,r=await t(e[j],j);if(r&&!fatal)fatal=r}}let ws=[];for(let k=0;k<Math.min(concurrency,e.length);k++)ws.push(worker());await Promise.all(ws);return fatal}
async function Lo(e){'''
    if js.count(helpers_anchor) != 1:
        raise ValueError("Translation coordinator signature not found")
    js = js.replace(helpers_anchor, helpers, 1)

    if js.count('timeout:3e4,maxRetries:2') != 1:
        raise ValueError("OpenAI retry signature not found")
    js = js.replace('timeout:3e4,maxRetries:2', 'timeout:3e4,maxRetries:1', 1)

    old_worker_catch = 'catch{v=!0,ee+=1}await wo(),x+=1'
    new_worker_catch = (
        'catch(e){v=!0,ee+=1,globalThis.__slgRecordRejectedTranslations?.((i||[]).map(_item=>({old:_item.text,reason:`translation_batch_failed`}))),isNetworkFailure(e)&&(N=`无法连接 ${P}。'
        '请检查网络，或前往“我的”切换供应商。`,b=y.length)}wo(),x+=1'
    )
    state_anchor = 'let _=new H({apiKey:a,baseURL:i,dangerouslyAllowBrowser:!0,timeout:3e4,maxRetries:1}),v=!1,y='
    state_replacement = 'let _=new H({apiKey:a,baseURL:i,dangerouslyAllowBrowser:!0,timeout:3e4,maxRetries:1}),v=!1,N="",P=providerLabel(i),y='
    if js.count(state_anchor) != 1 or js.count(old_worker_catch) != 1:
        raise ValueError("Translation worker signature not found")
    js = js.replace(state_anchor, state_replacement, 1)
    js = js.replace(old_worker_catch, new_worker_catch, 1)

    old_worker_start = 'for(;b<y.length;){let e=b++,i=y[e];try{let e=await Bo(_,o,i,n,r,s,u);'
    new_worker_start = 'for(;b<y.length;){let e=b++,i=y[e];l?.(d.size,t.length,`translating`,{stage:`start`,currentBatch:e+1,totalBatches:y.length,batchSize:i.length,cachedCount:h,localRuleCount:g});try{let e=await globalThis.__slgApiSemaphore.run(()=>Bo(_,o,i,n,r,s,u));'
    if js.count(old_worker_start) != 1:
        raise ValueError("Translation batch start signature not found")
    js = js.replace(old_worker_start, new_worker_start, 1)

    old_worker_completed = 'l?.(d.size,t.length,`translating`,{cachedCount:h,localRuleCount:g,completedBatches:x,totalBatches:y.length,currentBatch:e+1,batchSize:i.length,failedBatches:ee,splitBatches:S,estimatedSecondsRemaining:Ko(C,x,y.length)})'
    new_worker_completed = 'l?.(d.size,t.length,`translating`,{stage:`completed`,cachedCount:h,localRuleCount:g,completedBatches:x,totalBatches:y.length,currentBatch:e+1,batchSize:i.length,failedBatches:ee,splitBatches:S,estimatedSecondsRemaining:Ko(C,x,y.length)})'
    if js.count(old_worker_completed) != 1:
        raise ValueError("Translation batch completed signature not found")
    js = js.replace(old_worker_completed, new_worker_completed, 1)

    old_progress_start = 'onProgress:(e,t,n,r)=>{if(n!==`translating`)return;if(!r?.totalBatches){'
    new_progress_start = 'onProgress:(e,t,n,r)=>{if(n!==`translating`)return;if(r?.stage===`start`&&r.currentBatch){O(`  \u6b63\u5728\u7ffb\u8bd1\u6279\u6b21 ${r.currentBatch}/${r.totalBatches}\uff08\u672c\u6279 ${r.batchSize} \u6761\uff09`,`progress`);return}if(!r?.totalBatches){'
    if js.count(old_progress_start) != 1:
        raise ValueError("Translation progress log signature not found")
    js = js.replace(old_progress_start, new_progress_start, 1)

    old_return_empty = 'm.length===0)return await wo(),{translations:d,successCount:d.size};'
    new_return_empty = 'm.length===0)return wo(!0),{translations:d,successCount:d.size};'
    if js.count(old_return_empty) != 1:
        raise ValueError("Translation cache-only return signature not found")
    js = js.replace(old_return_empty, new_return_empty, 1)

    old_return_no_key = 'if(!a)return await wo(),{translations:d,successCount:d.size,error:'
    new_return_no_key = 'if(!a)return wo(!0),{translations:d,successCount:d.size,error:'
    if js.count(old_return_no_key) != 1:
        raise ValueError("Translation no-key return signature not found")
    js = js.replace(old_return_no_key, new_return_no_key, 1)

    old_return_final = 'return await Promise.all(ne),await wo(),{translations:d,successCount:d.size'
    new_return_final = 'return await Promise.all(ne),wo(!0),{translations:d,successCount:d.size'
    if js.count(old_return_final) != 1:
        raise ValueError("Translation final return signature not found")
    js = js.replace(old_return_final, new_return_final, 1)

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

    old_failed_leaf = 'if(n.length<=1||s>=4)return{translations:new Map,splitCount:0,failedCount:1};'
    new_failed_leaf = (
        'if(n.length<=1||s>=4){globalThis.__slgRecordRejectedTranslations?.('
        '(n||[]).map(_item=>({old:_item.text,reason:`translation_validation_failed`})));'
        'return{translations:new Map,splitCount:0,failedCount:1};}'
    )
    if js.count(old_failed_leaf) != 1:
        raise ValueError("Translation failed-leaf signature not found")
    js = js.replace(old_failed_leaf, new_failed_leaf, 1)

    # Source APK resilience: refresh the installed-app source to the persistent
    # directory before translating so a cleared cache cannot break patch builds.
    old_start = "Ce=async()=>{if(!n||ae.length===0||!te&&!oe)return;"
    new_start = (
        "Ce=async()=>{globalThis.__slgResetTranslationCollisionReport?.();globalThis.__slgResetTranslationCoverage?.();if(!n||ae.length===0||!te&&!oe)return;"
        "if(window.__slgSelectionMeta?.source===`installed`&&window.__slgSelectionMeta?.packageName){try{"
        "let _r=await E.selectInstalledApp({packageName:window.__slgSelectionMeta.packageName});"
        "_r?.uri&&(window.__slgSelectionMeta.uri=_r.uri);"
        "if(_r?.uri){window.__slgSelectionMeta=mergeSelectionMetadata(window.__slgSelectionMeta,_r),window.__slgSelectionMeta.uri=_r.uri}}"
        "catch(_e){O(`\u91cd\u65b0\u83b7\u53d6\u6e38\u620f\u5b89\u88c5\u5305\u5931\u8d25: ${_e&&_e.message||_e}`,\u0060error\u0060)}"
        "if(window.__slgRenpyMenuType===`renpy`&&!window.__slgMenuInjectedForRefresh){try{"
        "const _m=await E.injectTranslatorMenu({apkUri:window.__slgSelectionMeta?.uri||n,gameTargetLang:window.__slgRenpyLang||'',translatorLang:'slgtranslated'});"
        "window.__slgTranslatorLang=(_m&&_m.ready)?'slgtranslated':'';"
        "window.__slgActivationMode=(_m&&_m.ready)?`selectable`:`always_on`;"
        "if(_m&&_m.ready)window.__slgMenuInjectedForRefresh=true}catch{window.__slgTranslatorLang='';window.__slgActivationMode=`always_on`}}"
        "}"
        "if(window.__slgRenpyMenuType===`renpy`&&!window.__slgFontPreflightDone){"
        "let _fontTarget=ae.find(_x=>_x.fileType===`rpyc`||_x.fileType===`rpymc`||/\\.rp(?:y|ym)c$/i.test(String(_x.name||``)));"
        "if(!_fontTarget){window.__slgFontPreflightBlocked=true;window.__slgFontPreflightReport=null;O(`Ren'Py 字体预检失败：没有可检查的 Ren'Py 编译脚本（.rpyc/.rpymc），已阻断模型调用。`,`error`);ce(!1);return}"
        "try{let _fr=await E.readRenpyTexts({uri:(window.__slgSelectionMeta?.uri||n),splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],sourceApk:_fontTarget.sourceApk||'',entryName:_fontTarget.name});"
        "window.__slgFontPreflightReport=_fr?.fontReport||null;window.__slgFontPreflightBlocked=!_fr?.fontReport||_fr?.fontGate===`blocked`||(_fr?.fontReport?.missingCodePoints||[]).length>0;"
        "if(window.__slgFontPreflightBlocked){O(`Ren'Py 字体预检失败：固定中文/标点基线存在缺字，已阻断模型调用。缺字码点：${(_fr?.fontReport?.missingCodePoints||[]).join(`,`)}`,`error`);ce(!1);return}"
        "O(`Ren'Py 字体预检通过：固定中文/标点基线 ${_fr?.fontReport?.coveredCount||0}/${_fr?.fontReport?.requiredCount||0}`,`info`)}"
        "catch(_fontError){window.__slgFontPreflightBlocked=true;O(`Ren'Py 字体预检失败：无法读取字体报告，已阻断模型调用。${_fontError&&_fontError.message||_fontError}`,`error`);ce(!1);return}"
        "window.__slgFontPreflightDone=true}"
        "if(window.__slgRenpyMenuType===`renpy`&&!window.__slgRenpyCompatibilityPreflightDone){"
        "let _cr=window.__slgRenpyCompatibilityReport;"
        "if(!_cr){window.__slgRenpyCompatibilityBlocked=true;O(`Ren'Py 兼容性预检失败：扫描器没有返回兼容性报告，已阻断模型调用。`,`error`);ce(!1);return}"
        "window.__slgRenpyCompatibilityReport=_cr;window.__slgRenpyCompatibilityBlocked=_cr.supportLevel===`UNSUPPORTED`||_cr.supportLevel===`EXTRACT_ONLY`||window.__slgRenpyCompatibilityGate===`blocked`||window.__slgRenpyCompatibilityGate===`extract_only`;"
        "globalThis.__slgRenderRenpyCompatibilityReport?.(_cr);"
        "if(window.__slgRenpyCompatibilityBlocked){O(`Ren'Py 兼容性预检失败：${(_cr.issues||[]).map(_i=>_i.code).slice(0,3).join(`,`)||`unsupported`}`,`error`);ce(!1);return}"
        "window.__slgRenpyCompatibilityPreflightDone=true}"
    )
    if js.count(old_start) != 1:
        raise ValueError("Ce start signature not found")
    js = js.replace(old_start, new_start, 1)

    # Read and build from the refreshed meta uri when present.
    old_read = "E.readFileContent({uri:n,entryName:o.name})"
    new_read = (
        "o.fileType===`rpyc`?await E.readRenpyTexts({uri:(window.__slgSelectionMeta?.uri||n),splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],sourceApk:o.sourceApk||'',entryName:o.name}).then(_r=>{"
        "globalThis.__slgCoverageRecords=(globalThis.__slgCoverageRecords||[]).concat((_r&&_r.renpyRecords)||[]);"
        "globalThis.__slgRegisterDialogueRecords?.((_r&&_r.renpyRecords)||[]);"
        "globalThis.__slgCoverageClassifications=Object.assign({},globalThis.__slgCoverageClassifications||{},(_r&&_r.coverageClassifications)||{});"
        "globalThis.__slgAccumulateRenpyCompatibility?.((_r&&_r.renpyRecords)||[]);"
        "globalThis.__slgRefreshTranslationCoverage?.();return _r}):"
        "await E.readFileContent({uri:(window.__slgSelectionMeta?.uri||n),splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],sourceApk:o.sourceApk||'',entryName:o.name})"
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
        "splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],"
        "apkSet:window.__slgSelectionMeta?.apkSet||null,"
        "dialogueIdMode:!!window.__slgDialogueIdMode,dialogueTranslations:window.__slgDialogueIdTranslations||[],"
        "files:(()=>{const _f=a.filter(_x=>{let _p=String(_x.path);return !_p.includes(`/tl/`)&&!_p.includes(`x-slgtranslated`)});return _f.length?_f:[{path:'assets/slg-translator-marker.txt',content:''}]})(),"
        "outputDirUri:m,outputName:Me(i),"
        "targetRenpyLanguage:window.__slgCompiledCount>0?'':is(y),sourceRenpyLanguage:window.__slgCompiledCount>0?'':is(g)}"
    )
    if js.count(old_build) != 1:
        raise ValueError("Build uri signature not found")
    js = js.replace(old_build, new_build, 1)

    # Install the generated base together with every original split in one
    # PackageInstaller session.  The patched output becomes the new base; the
    # split names and source files remain explicit so the native bridge can
    # validate the complete set before committing it.
    old_install = "let t=await E.installApk({uri:e,packageName:f||void 0,cleanupAfterInstall:!0})"
    new_install = (
        "let t=await E.installApk({uri:e,baseUri:e,"
        "splitUris:window.__slgSelectionMeta?.splitUris||[],"
        "splitNames:window.__slgSelectionMeta?.splitNames||[],"
        "packageName:f||void 0,versionCode:window.__slgSelectionMeta?.versionCode,"
        "cleanupAfterInstall:!0})"
    )
    if js.count(old_install) != 1:
        raise ValueError("APK-set install signature not found")
    js = js.replace(old_install, new_install, 1)

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
    outer_state_with_fatal = 'let e=x===`custom`?re:_e.find(e=>e.id===x)?.baseURL||``,t=0,r=!1,N="",_maxDone=0,a=[],o=``,s=``,c=!1,l=!1;'
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

    old_worker_progress_start = 'async(o,c)=>{let l=ds[o.fileType]||`?`;'
    new_worker_progress_start = 'async(o,c)=>{let l=ds[o.fileType]||`?`;(_maxDone=Math.max(_maxDone,c+1),ue({current:_maxDone,total:ae.length}));'
    if js.count(old_worker_progress_start) != 1:
        raise ValueError("Translation worker progress start signature not found")
    js = js.replace(old_worker_progress_start, new_worker_progress_start, 1)

    # Compile the generated translation .rpy files into .rpyc before the APK
    # is assembled: Ren'Py only loads compiled scripts from an APK archive,
    # so plain .rpy files in the patch were never picked up by the game.
    build_gate = 'return N},2);if(!N&&(a.length>0||oe)){O(`\u6b63\u5728\u751f\u6210 Ren\'Py \u8865\u4e01 APK...`,`info`);try{let e=await E.buildPatchedApk'
    build_gate_compiled = (
        'return N},2);if(!N&&(a.length>0||oe)){(!N&&a.length)&&await E.compileTranslationsIntoApk('
        "{apkUri:(window.__slgSelectionMeta?.uri||n),baseUri:(window.__slgSelectionMeta?.baseUri||window.__slgSelectionMeta?.uri||n),splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],activationMode:window.__slgActivationMode||'always_on',dialogueIdMode:!!window.__slgDialogueIdMode,dialogueTranslations:window.__slgDialogueIdTranslations||[],items:a.map(_x=>({path:_x.path,content:_x.content}))}).then("
        '_r=>{window.__slgCompiledCount=_r&&_r.compiled>0?_r.compiled:0;(_r&&_r.compiled>0)?O(`  \u5df2\u7f16\u8bd1\u5e76\u5408\u5e76\u53bb\u91cd ${_r.compiled} \u6761\u8bd1\u6587\uff0c\u6e38\u620f\u5c06\u76f4\u63a5\u52a0\u8f7d\u7f16\u8bd1\u7248\u672c`,`success`):O(`  \u6ca1\u6709\u53ef\u7f16\u8bd1\u7684 Ren\'Py \u7ffb\u8bd1\u8d44\u6e90`,`info`)}).catch('
        '_e=>{O(`  \u7f16\u8bd1\u7ffb\u8bd1\u8d44\u6e90\u5931\u8d25: ${_e&&_e.message||_e}`,`error`)});'
        'O(`\u6b63\u5728\u751f\u6210 Ren\'Py \u8865\u4e01 APK...`,`info`);try{let e=await E.buildPatchedApk'
    )
    coverage_gate = (
        'return N},2);if(!N&&(a.length>0||oe)){globalThis.__slgRefreshTranslationCoverage?.();'
        'let _coverage=globalThis.__slgBuildCoverage;if(_coverage&&(_coverage.missingCount>0||_coverage.rejectedCount>0)){'
        'if(!globalThis.__slgIncompleteTestPatchSelected){O(`coverage incomplete：缺失或拒绝的翻译仍未处理，已阻断完整构建`,`warning`);return N}'
        'O(`incomplete test patch：覆盖率不足，仅生成不完整测试补丁，不能宣称完整翻译`,`warning`)}'
    )
    build_gate_compiled = build_gate_compiled.replace(
        'return N},2);if(!N&&(a.length>0||oe)){', coverage_gate, 1
    )
    build_gate_compiled = build_gate_compiled.replace(
        'return N},2);if(!N&&(a.length>0||oe)){(!N&&a.length)&&await E.compileTranslationsIntoApk(',
        'return N},2);if(!N&&(a.length>0||oe)){window.__slgCompileFailed=false;(!N&&a.length)&&await E.compileTranslationsIntoApk(',
        1,
    )
    build_gate_compiled = build_gate_compiled.replace(
        'O(`  编译翻译资源失败: ${_e&&_e.message||_e}`,`error`)});O(`',
        'window.__slgCompileFailed=true;O(`  编译翻译资源失败: ${_e&&_e.message||_e}`,`error`)});if(window.__slgCompileFailed){return N}O(`',
        1,
    )
    build_gate_compiled = build_gate_compiled.replace(
        "_r=>{window.__slgCompiledCount=_r&&_r.compiled>0?_r.compiled:0;",
        "_r=>{window.__slgCompiledCount=_r&&_r.compiled>0?_r.compiled:0;window.__slgFontReport=_r&&_r.fontReport||null;window.__slgFontWarning=_r&&_r.fontWarning||'';window.__slgActivationMode=_r&&_r.activationMode||window.__slgActivationMode||'always_on';window.__slgTranslatorLang=_r&&_r.translatorLanguage||'';window.__slgCompiledPath=_r&&_r.compiledPath||'';(_r&&_r.fontWarning)&&O(`  字体预检警告：${_r.fontWarning}`,`warning`);",
        1,
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
        "let{content:_c,fileType:_ft}=o.fileType===`rpyc`?await E.readRenpyTexts({uri:(window.__slgSelectionMeta?.uri||n),splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],sourceApk:o.sourceApk||'',entryName:o.name}):await E.readFileContent({uri:(window.__slgSelectionMeta?.uri||n),splitUris:window.__slgSelectionMeta?.splitUris||[],splitNames:window.__slgSelectionMeta?.splitNames||[],sourceApk:o.sourceApk||'',entryName:o.name});"
        "let l=ke(_c,_ft,``,g),_need=l.filter(t=>!t||!_map.has(t.text));"
        "if(_need.length){let _r=await Lo({texts:_need,sourceLang:g,targetLang:y,baseURL:e,apiKey:te,model:S,batchSize:ps,onProgress:()=>{}});if(_r&&_r.successCount>0){for(let t of _need){let v=_r.translations.get(t.keyPath)||_r.translations.get(t.text);if(v&&v.trim())_map.set(t.text,v)}O(`  \u8865\u5145\u7ffb\u8bd1 ${_r.successCount} \u6761\u65b0\u6587\u672c`,`success`)}}"
        "let _outs=[rs(o,l,_map,`None`),rs(o,l,_map,g)],_uniq=new Map;oe||_outs.unshift(rs(o,l,_map,y));"
        "for(let e of _outs)_uniq.set(e.outputPath,e);"
        "for(let e of _uniq.values())await Ne(e.outputPath,e.content),a.push({path:e.outputPath,content:e.content});"
        "vo[_fk]={texts:l,translations:Array.from(_map.entries()),count:l.length,updatedAt:Date.now(),pkg:window.__slgSelectionMeta?.packageName||``},bo=!0,wo(!0);"
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
    old_plain_cache = "vo[_fk]={texts:l,translations:Array.from(f.entries()),count:p,updatedAt:Date.now(),pkg:window.__slgSelectionMeta?.packageName||``},bo=!0,await wo()"
    new_plain_cache = old_plain_cache.replace(",bo=!0,await wo()", ",bo=!0,wo(!0)")
    if js.count(old_plain_cache) != 1:
        raise ValueError("Plain file cache save signature not found")
    js = js.replace(old_plain_cache, new_plain_cache, 1)

    old_progress_mark = 'ue({current:c+1,total:ae.length})'
    new_progress_mark = '(_maxDone=Math.max(_maxDone,c+1),ue({current:_maxDone,total:ae.length}))'
    if js.count(old_progress_mark) < 5:
        raise ValueError("Translation file progress mark signature not found")
    js = js.replace(old_progress_mark, new_progress_mark)
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
        "var _saveTimer=null,_saveBusy=!1,_saveAgain=!1,_lastSaveAt=0;"
        "globalThis.__slgCacheDbg={calls:0,skipped:0,errors:0,lastError:null};"
        "async function wo(_force=false){globalThis.__slgCacheDbg.calls++;"
        "if(!yo){try{await Co()}catch(e){globalThis.__slgCacheDbg.lastError='co:'+(e&&e.message||e);"
        "O('  \u7f13\u5b58\u52a0\u8f7d\u5931\u8d25: '+(e&&e.message||e),'error')}}"
        "if(!yo||!bo){globalThis.__slgCacheDbg.skipped++;return}"
        "if(!_force&&Date.now()-_lastSaveAt<4000){globalThis.__slgCacheDbg.skipped++;"
        "if(!_saveTimer)_saveTimer=setTimeout(()=>{_saveTimer=null;wo(!0)},4000);return}"
        "globalThis.__slgCacheDbg.entries=Object.keys(vo).length;bo=!1;"
        "if(_saveBusy){_saveAgain=!0;return}do{_saveAgain=!1,_saveBusy=!0;"
        "let _snap={};for(const[_k,_v]of Object.entries(_dirty))_snap[_k]=_v;for(const[_k,_v]of Object.entries(vo)){"
        "if(_k.startsWith(`slg-file-v1:`))_snap[_k]=_v}let _e=JSON.stringify(_snap);"
        "try{await E.saveTranslationCache({data:_e});for(const _k of Object.keys(_snap)){if(_k.startsWith(_o))delete _dirty[_k]}}catch(e){bo=!0;globalThis.__slgCacheDbg.errors++;globalThis.__slgCacheDbg.lastError='save:'+(e&&e.message||e)}"
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
    old_call = 'return N},2);if(!N&&(a.length>0||oe)){'
    new_call = 'return N},(window.__slgLocalSelected?2:6));if(!N)await wo(!0);if(!N&&(a.length>0||oe)){'
    if js.count(old_call) != 1:
        raise ValueError("File controller concurrency call signature not found")
    js = js.replace(old_call, new_call, 1)
    return js


def patch_output_write_cache(js: str) -> str:
    old_ne = (
        "async function Ne(e,t){let n=e.split(`/`),r=n.at(-1)||`translation.rpy`,i=m;"
        "for(let e=0;e<n.length-1;e++)try{let t=await E.createDirectory({dirUri:i,dirName:n[e]});"
        "t.success&&t.uri&&(i=t.uri)}catch{}await E.writeFileToDir({dirUri:i,fileName:r,content:t})}"
    )
    new_ne = (
        "async function Ne(e,t){let n=e.split(`/`),r=n.at(-1)||`translation.rpy`,dirs=n.slice(0,-1).join(`/`),"
        "i=(globalThis.__slgDirCacheBase===m&&globalThis.__slgDirCache&&globalThis.__slgDirCache[dirs])||m;"
        "if(i!==m){await E.writeFileToDir({dirUri:i,fileName:r,content:t});return}"
        "globalThis.__slgDirCache=globalThis.__slgDirCache||{};globalThis.__slgDirCacheBase=m;"
        "for(let e=0;e<n.length-1;e++){let _d=n.slice(0,e+1).join(`/`),_u=globalThis.__slgDirCache[_d];"
        "if(_u){i=_u;continue}try{let t=await E.createDirectory({dirUri:i,dirName:n[e]});"
        "t.success&&t.uri&&(i=t.uri)}catch{}if(i&&!globalThis.__slgDirCache[_d])globalThis.__slgDirCache[_d]=i}"
        "await E.writeFileToDir({dirUri:i,fileName:r,content:t})}"
    )
    if js.count(old_ne) != 1:
        raise ValueError("Output write Ne signature not found")
    return js.replace(old_ne, new_ne, 1)

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
    new_yb = "{let q=Qo(r);if(q!=null){let l=es(q);if(l===`slgtranslated`)return!1;if(l===`none`)return!0;let _s=globalThis.__slgSrcLang||`en`;return $o(_s).has(l)?!0:!1}let e=(r.split(`/`).pop()||``).replace(/\\.[^/.]+$/,``);return _rpycSkip.test(e)?!1:!0}"
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
    # 0) keyPath 前缀：提取文本时把文件路径写入 keyPath（o.name + "::"），
    #    供 Vo 注入 Source file / 同文件场景上下文
    old_ke = r'''l=ke(i,s,``,g)'''
    new_ke = r'''l=ke(i,s,o.name+`::`,g)'''
    if js.count(old_ke) != 1:
        raise ValueError("Text extraction call signature not found")
    js = js.replace(old_ke, new_ke, 1)

    # 0b) 缓存键版本：质量策略升级后旧缓存自动失效
    old_o = r'''var _o=`slg-translator-cache:`,vo={}'''
    new_o = r'''var _o=`slg-translator-cache:`,vo={}'''
    if js.count(old_o) != 1:
        raise ValueError("Cache namespace signature not found")
    js = js.replace(old_o, new_o, 1)

    # 1) Le：Ren'Py 源格式解析捕获说话人名字（maria "text" → speaker: maria）
    old_le = r'''let c=s.match(/^(['"])((?:[^"'\\]|\\.)+)\1\s*:/),l=s.match(/^(?:(?:[A-Za-z_]\w*|\w+\.[A-Za-z_]\w*)\s+)?(['"])((?:[^"'\\]|\\.)+)\1\s*(?:#.*)?$/),u=c?.[2]??l?.[2];u&&He(u,n)&&!i.has(u)&&(i.add(u),r.push({keyPath:`${t}rpy_${a++}`,text:u}))'''
    new_le = r'''let c=s.match(/^(['"])((?:[^"'\\]|\\.)+)\1\s*:/),l=s.match(/^(?:([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s+)?(['"])((?:[^"'\\]|\\.)+)\2\s*(?:#.*)?$/),u=c?.[2]??l?.[3],sp=l?.[1];u&&He(u,n)&&!i.has(u)&&(i.add(u),r.push({keyPath:`${t}rpy_${a++}`,text:u,...sp?{speaker:sp}:{}}))'''
    if js.count(old_le) != 1:
        raise ValueError("Speaker extraction signature not found")
    js = js.replace(old_le, new_le, 1)

    # 2) No：去重时保留第一个说话人字段，避免 speaker 在去重后丢失
    old_no = r'''function No(e){let t=new Map;for(let n of e){let e=n.text.trim();if(!e)continue;let r=t.get(e);if(r){r.duplicateKeys.push(n.keyPath);continue}t.set(e,{keyPath:n.keyPath,text:n.text,duplicateKeys:[]})}return Array.from(t.values())}'''
    new_no = r'''function No(e){let t=new Map;for(let n of e){let e=n.text.trim();if(!e)continue;let r=t.get(e);if(r){r.duplicateKeys.push(n.keyPath);continue}t.set(e,{keyPath:n.keyPath,text:n.text,duplicateKeys:[],...(n.speaker?{speaker:n.speaker}:{})})}return Array.from(t.values())}'''
    if js.count(old_no) != 1:
        raise ValueError("Dedupe signature not found")
    js = js.replace(old_no, new_no, 1)

    # 3) Ro：占位符保护后仍携带 speaker 字段，供 Vo 构造上下文
    old_ro = r'''function Ro(e){return{...e,protectedText:Fo(e.text)}}'''
    new_ro = r'''function Ro(e){return{...e,protectedText:Fo(e.text),...(e.speaker?{speaker:e.speaker}:{})}}'''
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
    new_vo = r'''async function Vo(e,t,n,r,i,a,o){let s=new Map,c=Go(r,i,a,o),p0=String(n[0]?.keyPath||``),_f=p0.includes(`::`)?p0.split(`::`)[0]:``,w=_f.split(`/`).pop()||``,sf=!!_f&&n.length>1&&n.every(e=>String(e.keyPath||``).split(`::`)[0]===_f),_ns=n.map(e=>{let k=String(e.keyPath||``).split(`::`).pop()||``,m=k.match(/(?:^|_)(\d+)$/)||k.match(/\[L(\d+)\]/)||k.match(/\[r(\d+)c/);return m?+m[1]:null}).filter(x=>x!==null).sort((a,b)=>a-b),_sc=sf&&_ns.length===n.length&&_ns.length>1&&_ns.every((x,i)=>i===0||x-_ns[i-1]===1),l=((_f?`Source file: ${w}\n`:`\n`)+(_sc?`These are consecutive lines from the same scene (${w}). Translate them as one coherent dialogue flow — keep tone, terminology and speaking habits consistent across all lines.\n`:(sf?`These lines belong to the same file (${w}). Translate them as one coherent passage — keep tone, terminology and speaking habits consistent.\n`:`\n`))+(n.some(e=>e.speaker)?`Context hints (index → speaker):\n`+n.map((e,i)=>`[${i}]${e.speaker?` → ${e.speaker}`:``}\n`).join(``):``)+`Translate this JSON array. `+(o?`Return a JSON object exactly like {"translations":["..."]} with translations in the same order:
`:`Return a JSON array with translations in the same order:
`)+Po(n.map(e=>({...e,text:e.protectedText.text})))),u=(await e.chat.completions.create({model:t,messages:[{role:`system`,content:c},{role:`user`,content:l}],temperature:.3,...o?{response_format:{type:`json_object`}}:{}})).choices[0]?.message?.content;if(!u)throw Error(`API returned empty content`);let d=Ho(u);for(let e=0;e<n.length;e++){let t=d[e];typeof t==`string`&&t.trim()&&s.set(e,Io(t,n[e].protectedText))}return s}'''
    vo_collision_prefix = "async function Vo(e,t,n,r,i,a,o){let s=new Map,c=Go(r,i,a,o),"
    vo_collision_replacement = (
        "async function Vo(e,t,n,r,i,a,o){let _collisionBatch=(n||[]).map(e=>({exactOld:String(e.text??e.protectedText?.text??``),"
        "speaker:String(e.speaker??``),identifier:String(e.identifier??``),kind:String(e.kind??``),"
        "sourcePath:String(e.keyPath??``).split(`::`)[0]})),_collisionEntries=(globalThis.__slgTranslationCollisionEntries||[]).concat(_collisionBatch);"
        "globalThis.__slgTranslationCollisionEntries=_collisionEntries;"
        "globalThis.__slgTranslationCollisionReport?.(_collisionEntries);"
        "let s=new Map,c=Go(r,i,a,o),"
    )
    if new_vo.count(vo_collision_prefix) != 1:
        raise ValueError("Batch collision-report hook signature not found")
    new_vo = new_vo.replace(vo_collision_prefix, vo_collision_replacement, 1)
    if js.count(old_vo) != 1:
        raise ValueError("Batch request signature not found")
    old_vo_return = "return s}"
    new_vo_return = (
        "globalThis.__slgRecordTranslationCandidates?.(n,s);"
        "globalThis.__slgRecordValidatorApprovedTranslations?.(n,s);return s}"
    )
    if new_vo.count(old_vo_return) != 1:
        raise ValueError("Batch result hook signature not found")
    new_vo = new_vo.replace(old_vo_return, new_vo_return, 1)
    js = js.replace(old_vo, new_vo, 1)

    # Task 8: keep a small, sanitized report available to the workshop UI.
    # The report distinguishes unique old strings, repeated occurrences and
    # contextual collisions; it deliberately never exports raw object values.
    collision_report = r'''
(function(){/* up to 3 representative contexts */function sanitize(e){return{old:String(e.old??e.exactOld??``),speaker:String(e.speaker??``),identifier:String(e.identifier??``),kind:String(e.kind??``),sourcePath:String(e.sourcePath??``)}}function translationCollisionReport(entries){let m=new Map;for(let e of entries||[]){let x=sanitize(e),a=m.get(x.old)||{old:x.old,occurrences:[],contexts:new Set};a.occurrences.push(x);a.contexts.add([x.speaker,x.identifier,x.kind,x.sourcePath].join(`\u0000`));m.set(x.old,a)}let rows=Array.from(m.values()).map(x=>({old:x.old,occurrenceCount:x.occurrences.length,duplicateCount:Math.max(0,x.occurrences.length-1),contextualCollision:x.contexts.size>1,contexts:Array.from(x.contexts).slice(0,3)}));let report={uniqueOldCount:rows.length,occurrenceCount:rows.reduce((a,x)=>a+x.occurrenceCount,0),duplicateCount:rows.filter(x=>x.duplicateCount>0).length,collisionCount:rows.filter(x=>x.contextualCollision).length,entries:rows};window.__slgTranslationCollisionReport=report;window.__slgTranslationCollisionReportJson=JSON.stringify(report);return report}function rejectTranslationCollisions(pairs){let m=new Map;for(let p of pairs||[]){let old=String(p.old??p[0]??``),next=String(p.new??p[1]??``),prior=m.get(old);if(prior!==undefined&&prior!==next)throw Error(`translation_collision_conflict: conflicting translations for ${old}`);m.set(old,next)}}window.__slgTranslationCollisionReport=translationCollisionReport;window.__slgRejectTranslationCollisions=rejectTranslationCollisions})();
'''
    collision_report = r'''
(function(){/* up to 3 representative contexts */const root=typeof window!==`undefined`?window:globalThis;function sanitize(e){return{old:String(e?.old??e?.exactOld??``),speaker:String(e?.speaker??``),identifier:String(e?.identifier??``),kind:String(e?.kind??``),sourcePath:String(e?.sourcePath??``)}}function render(report){if(typeof document===`undefined`)return;const host=document.querySelector(`#root>div`)||document.querySelector(`#root`);if(!host)return;let panel=document.getElementById(`slg-translation-collision-report`);if(!panel){panel=document.createElement(`section`);panel.id=`slg-translation-collision-report`;panel.className=`workshop-translation-collision-report`;panel.style.cssText=`margin:12px 0;padding:14px;border:1px solid color-mix(in srgb,#d97706 40%,transparent);border-radius:12px;background:color-mix(in srgb,#d97706 8%,transparent)`;host.append(panel)}panel.hidden=false;panel.replaceChildren();const title=document.createElement(`h3`);title.textContent=`翻译语境诊断`;const summary=document.createElement(`p`);summary.textContent=`唯一原文 ${report.uniqueOldCount} · 总出现 ${report.occurrenceCount} · 重复条目 ${report.duplicateCount} · 语境碰撞 ${report.collisionCount}`;const exportButton=document.createElement(`button`);exportButton.type=`button`;exportButton.textContent=`导出碰撞 JSON`;exportButton.onclick=()=>{const blob=new Blob([root.__slgTranslationCollisionReportJson||JSON.stringify(report)],{type:`application/json`}),url=URL.createObjectURL(blob),a=document.createElement(`a`);a.href=url;a.download=`renpy-translation-collisions.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),0)};const list=document.createElement(`div`);for(const item of report.entries.slice(0,20)){const row=document.createElement(`article`),old=document.createElement(`strong`),meta=document.createElement(`div`);old.textContent=item.old;meta.textContent=`出现 ${item.occurrenceCount} 次 · 重复 ${item.duplicateCount} · 语境碰撞 ${item.contextualCollision?`是`:`否`}`;row.append(old,meta);for(const context of item.contexts){const detail=document.createElement(`small`);detail.textContent=context;row.append(detail)}list.append(row)}panel.append(title,summary,exportButton,list)}function translationCollisionReport(entries){let m=new Map;for(const entry of entries||[]){const item=sanitize(entry),group=m.get(item.old)||{old:item.old,occurrences:0,contexts:new Map};group.occurrences++;const key=[item.speaker,item.identifier,item.kind,item.sourcePath].join(`\u0000`);if(!group.contexts.has(key))group.contexts.set(key,`${item.sourcePath}:${item.speaker||`无说话人`} · ${item.kind}${item.identifier?` · ${item.identifier}`:``}`);m.set(item.old,group)}const rows=Array.from(m.values()).map(group=>({old:group.old,occurrenceCount:group.occurrences,duplicateCount:Math.max(0,group.occurrences-1),contextualCollision:group.contexts.size>1,contexts:Array.from(group.contexts.values()).slice(0,3)})),report={uniqueOldCount:rows.length,occurrenceCount:rows.reduce((sum,item)=>sum+item.occurrenceCount,0),duplicateCount:rows.filter(item=>item.duplicateCount>0).length,collisionCount:rows.filter(item=>item.contextualCollision).length,entries:rows};root.__slgTranslationCollisionReportData=report;root.__slgTranslationCollisionReportJson=JSON.stringify(report);render(report);return report}function reset(){root.__slgTranslationCollisionEntries=[];root.__slgTranslationCollisionReportData=null;root.__slgTranslationCollisionReportJson=``;const panel=typeof document!==`undefined`?document.getElementById(`slg-translation-collision-report`):null;if(panel)panel.hidden=true}function rejectTranslationCollisions(pairs){const seen=new Map;for(const pair of pairs||[]){const old=String(pair?.old??pair?.[0]??``),next=String(pair?.new??pair?.[1]??``);if(seen.has(old)&&seen.get(old)!==next)throw Error(`translation_collision_conflict: conflicting translations for ${old}`);seen.set(old,next)}}root.__slgTranslationCollisionReport=translationCollisionReport;root.__slgRejectTranslationCollisions=rejectTranslationCollisions;root.__slgResetTranslationCollisionReport=reset})()
'''
    coverage_report = r'''
(function(){const root=typeof window!==`undefined`?window:globalThis;
function asMap(value){return value instanceof Map?value:new Map(Object.entries(value||{}))}
function exact(value){return String(value??``)}
function safe(value){return exact(value)}
function isSkipReason(reason){return /developer_console|internal_error|expired_text|settings_optional/i.test(String(reason||``))}
function isXCommon(path){return /(?:^|\/)x-common\//i.test(String(path||``))}
function inferredClassification(raw){let explicit=String(raw?.coverageClassification??raw?.classificationReason??``);if(explicit)return explicit;let path=exact(raw?.sourcePath??String(raw?.keyPath??``).split(`::`)[0]),kind=String(raw?.kind??``).toLowerCase();if(!isXCommon(path))return ``;let subject=(path+` `+kind).toLowerCase();if(/(?:debug|developer|console)/.test(subject))return `developer_console`;if(/(?:internal|error)/.test(subject))return `internal_error`;if(/(?:expired)/.test(subject))return `expired_text`;if(/(?:settings|optional)/.test(subject))return `settings_optional`;return ``}
function incremental(values,validated,failed,retry){let v=asMap(validated),out=new Set;for(const value of values||[]){let old=exact(value);if(old&&!v.has(old))out.add(old)}for(const value of failed||[])out.add(exact(value));for(const value of retry||[])out.add(exact(value));return Array.from(out)}
function render(report){if(typeof document===`undefined`)return;const host=document.querySelector(`#root>div`)||document.querySelector(`#root`);if(!host)return;let panel=document.getElementById(`slg-translation-coverage-report`);if(!panel){panel=document.createElement(`section`);panel.id=`slg-translation-coverage-report`;panel.className=`workshop-translation-coverage-report`;panel.style.cssText=`margin:12px 0;padding:14px;border:1px solid color-mix(in srgb,#b45309 42%,transparent);border-radius:12px;background:color-mix(in srgb,#b45309 8%,transparent)`;host.append(panel)}panel.hidden=false;panel.replaceChildren();const title=document.createElement(`h3`),summary=document.createElement(`p`),status=document.createElement(`p`);title.textContent=`Ren'Py 翻译覆盖率`;summary.textContent=`唯一原文 ${report.uniqueSourceCount} · 总出现 ${report.occurrenceCount} · 已验证 ${report.translatedCount} · 缺失 ${report.missingCount} · 拒绝 ${report.rejectedCount} · 不确定 ${report.uncertainCount}`;status.textContent=report.blocking?`完整构建已阻断：必须补齐缺失或被拒绝的翻译。可显式选择不完整测试补丁。`:`覆盖率通过，可生成完整构建。`;status.style.color=report.blocking?`#b45309`:`#15803d`;const exportButton=document.createElement(`button`);exportButton.type=`button`;exportButton.textContent=`导出覆盖率 JSON`;exportButton.onclick=()=>{const blob=new Blob([root.__slgTranslationCoverageReportJson||JSON.stringify(report)],{type:`application/json`}),url=URL.createObjectURL(blob),a=document.createElement(`a`);a.href=url;a.download=`renpy-translation-coverage.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),0)};const incomplete=document.createElement(`button`);incomplete.type=`button`;incomplete.textContent=root.__slgIncompleteTestPatchSelected?`已选择不完整测试补丁`:`允许不完整测试补丁`;incomplete.disabled=!report.blocking;incomplete.onclick=()=>{root.__slgIncompleteTestPatchSelected=true;root.__slgIncompleteTestPatch=true;incomplete.textContent=`已选择不完整测试补丁`;render(report)};const list=document.createElement(`ol`);for(const item of report.topMissingFiles||[]){const row=document.createElement(`li`);row.textContent=`${item.filePath} · 缺失 ${item.missingCount} · 来源 ${item.sourceCount}`;list.append(row)}panel.append(title,summary,status,exportButton,incomplete,list)}
function buildCoverage(records,validated,rejected,uncertain,classification,candidates){const groups=new Map,files=new Map,excluded={};const v=asMap(validated),bad=new Set(rejected||[]),uncertainSet=new Set(uncertain||[]),classMap=asMap(classification),candidateMap=asMap(candidates);for(const raw of records||[]){const old=exact(raw?.exactOld??raw?.text);if(!old)continue;const path=exact(raw?.sourcePath??String(raw?.keyPath??``).split(`::`)[0]);const reason=classMap.get(`${path}\t${old}`)||classMap.get(old)||inferredClassification(raw);if(isXCommon(path)&&isSkipReason(reason)){excluded[`${path}\t${old}`]=reason;continue}let group=groups.get(old);if(!group)groups.set(old,group={old,paths:new Set,occurrences:0,uncertain:false});group.paths.add(path);group.occurrences++;group.uncertain=group.uncertain||raw?.coverageCertain===false||uncertainSet.has(old);let file=files.get(path);if(!file)files.set(path,file={filePath:path,sources:new Set,occurrences:0,translatedCount:0,missingCount:0,rejectedCount:0,collisionCount:0,uncertainCount:0});file.sources.add(old);file.occurrences++}let translatedCount=0,missingCount=0,rejectedCount=0,collisionCount=0,uncertainCount=0,missing=[];for(const group of groups.values()){const rejected=bad.has(group.old),translated=!rejected&&String(v.get(group.old)||``).trim().length>0,items=Array.from(new Set((candidateMap.get(group.old)||[]).map(exact).filter(Boolean)));const collision=items.length>1;if(translated)translatedCount++;else if(rejected)rejectedCount++;else{missingCount++;missing.push({exactOld:group.old,sourcePath:Array.from(group.paths)[0]||``,occurrenceCount:group.occurrences,reason:group.uncertain?`uncertain`:`missing`})}if(collision)collisionCount++;if(group.uncertain)uncertainCount++;for(const path of group.paths){const file=files.get(path);if(translated)file.translatedCount++;else if(rejected)file.rejectedCount++;else file.missingCount++;if(collision)file.collisionCount++;if(group.uncertain)file.uncertainCount++}}missing.sort((a,b)=>b.occurrenceCount-a.occurrenceCount||a.exactOld.localeCompare(b.exactOld));const topMissingFiles=Array.from(files.values()).filter(e=>e.missingCount>0).sort((a,b)=>b.missingCount-a.missingCount||a.filePath.localeCompare(b.filePath)).slice(0,20).map(e=>({...e,sources:undefined}));const report={uniqueSourceCount:groups.size,occurrenceCount:Array.from(groups.values()).reduce((sum,e)=>sum+e.occurrences,0),translatedCount,missingCount,rejectedCount,collisionCount,uncertainCount,files:Object.fromEntries(Array.from(files.entries()).map(([key,e])=>[key,{...e,sources:undefined}])),topMissingFiles,missing:missing.slice(0,20),excludedReasons:excluded,blocking:missingCount>0||rejectedCount>0};root.__slgTranslationCoverageReport=report;root.__slgTranslationCoverageReportJson=JSON.stringify(report);root.__slgBuildCoverage=report;root.__slgIncompleteTestPatch=report.blocking;render(report);return report}
root.__slgValidatorApprovedTranslations=root.__slgValidatorApprovedTranslations||new Map;root.__slgRejectedTranslations=root.__slgRejectedTranslations||new Set;root.__slgTranslationCoverageIncrementalDiff=incremental;root.__slgRecordValidatorApprovedTranslations=(items,translations)=>{for(let i=0;i<(items||[]).length;i++){const old=safe(items[i]?.text);const value=translations instanceof Map?translations.get(i):translations?.[i];if(old&&value&&String(value).trim())root.__slgValidatorApprovedTranslations.set(old,String(value))}root.__slgRefreshTranslationCoverage?.()};root.__slgRecordRejectedTranslations=items=>{for(const item of items||[]){const old=safe(item?.old??item?.exactOld??item);if(old)root.__slgRejectedTranslations.add(old)}root.__slgRefreshTranslationCoverage?.()};root.__slgRefreshTranslationCoverage=()=>buildCoverage(root.__slgCoverageRecords||[],root.__slgValidatorApprovedTranslations,root.__slgRejectedTranslations,root.__slgCoverageUncertain||[],root.__slgCoverageClassifications||{},root.__slgTranslationCollisionCandidates||{});root.__slgBuildTranslationCoverageReport=buildCoverage;root.__slgSelectIncompleteTestPatch=enabled=>{root.__slgIncompleteTestPatchSelected=!!enabled;root.__slgRefreshTranslationCoverage?.()};root.__slgRefreshTranslationCoverage()})()
'''
    # Uncertain extraction is a separate diagnostic bucket; it must not be
    # silently turned into missing coverage or a fabricated zero.
    coverage_report = coverage_report.replace("else{missingCount++;", "else if(!group.uncertain){missingCount++;")
    coverage_report = coverage_report.replace("else file.missingCount++;", "else if(!group.uncertain)file.missingCount++;")
    coverage_runtime_fix = r'''
(function(){const root=typeof window!==`undefined`?window:globalThis;function exact(value){return String(value??``)}root.__slgRecordValidatorApprovedTranslations=(items,translations)=>{const map=translations instanceof Map?translations:null;for(let i=0;i<(items||[]).length;i++){const item=items[i]||{},old=exact(item.text),value=map?.get(i)??map?.get(item.keyPath)??map?.get(item.text)??translations?.[item.keyPath]??translations?.[item.text]??translations?.[i];if(old&&value&&String(value).trim())root.__slgValidatorApprovedTranslations.set(old,String(value))}root.__slgRefreshTranslationCoverage?.()};root.__slgRecordRejectedTranslations=items=>{for(const item of items||[]){const old=exact(item?.old??item?.exactOld??item);if(old)root.__slgRejectedTranslations.add(old)}root.__slgRefreshTranslationCoverage?.()};root.__slgResetTranslationCoverage=()=>{root.__slgCoverageRecords=[];root.__slgValidatorApprovedTranslations=new Map;root.__slgRejectedTranslations=new Set;root.__slgIncompleteTestPatchSelected=false;root.__slgRefreshTranslationCoverage?.()}})()
'''
    coverage_runtime_fix_v2 = r'''
(function(){const root=typeof window!==`undefined`?window:globalThis;function exact(value){return String(value??``)}function lookup(items,translations,index){const item=items[index]||{},map=translations instanceof Map?translations:null;return map?.get(index)??map?.get(item.keyPath)??map?.get(item.text)??translations?.[item.keyPath]??translations?.[item.text]??translations?.[index]}root.__slgRecordTranslationCandidates=(items,translations)=>{const candidateMap=root.__slgTranslationCollisionCandidates instanceof Map?root.__slgTranslationCollisionCandidates:new Map(Object.entries(root.__slgTranslationCollisionCandidates||{}));for(let i=0;i<(items||[]).length;i++){const item=items[i]||{},old=exact(item.text);let value=lookup(items,translations,i);if(!old||!value||!String(value).trim())continue;let values=candidateMap.get(old)||[];value=String(value);if(!values.includes(value))values.push(value);candidateMap.set(old,values)}root.__slgTranslationCollisionCandidates=candidateMap;root.__slgRefreshTranslationCoverage?.()};root.__slgRecordValidatorApprovedTranslations=(items,translations)=>{root.__slgRecordTranslationCandidates?.(items,translations);for(let i=0;i<(items||[]).length;i++){const item=items[i]||{},old=exact(item.text),value=lookup(items,translations,i);if(old&&value&&String(value).trim())root.__slgValidatorApprovedTranslations.set(old,String(value))}root.__slgRefreshTranslationCoverage?.()};root.__slgRecordRejectedTranslations=items=>{for(const item of items||[]){const old=exact(item?.old??item?.exactOld??item);if(old)root.__slgRejectedTranslations.add(old)}root.__slgRefreshTranslationCoverage?.()};root.__slgResetTranslationCoverage=()=>{root.__slgCoverageRecords=[];root.__slgCoverageUncertain=[];root.__slgCoverageClassifications={};root.__slgValidatorApprovedTranslations=new Map;root.__slgRejectedTranslations=new Set;root.__slgTranslationCollisionCandidates=new Map;root.__slgTranslationCollisionEntries=[];root.__slgIncompleteTestPatchSelected=false;root.__slgRefreshTranslationCoverage?.()}})()
'''
    js += collision_report + coverage_report + coverage_runtime_fix + coverage_runtime_fix_v2
    return js


# ===== 缓存内存管理：full 清空同步清 cacheIndex + 缓存上限淘汰 =====
CACHE_PRUNE_LIMIT = 30000


def patch_cache_memory(js: str) -> str:
    # 1) full 模式清空 vo 时必须同步清 cacheIndex，否则旧缓存引用残留，
    #    内存不释放且 To() 仍能从 cacheIndex 命中旧缓存（清理无效）。
    old_full = "_mode===`full`&&(vo={},bo=!0,await wo())"
    new_full = "_mode===`full`&&(vo={},cacheIndex={},_dirty={},bo=!0,await wo(!0))"
    if js.count(old_full) != 1:
        raise ValueError("Full-clear signature not found")
    js = js.replace(old_full, new_full, 1)

    # 2) 缓存上限：超过 CACHE_PRUNE_LIMIT 条时按 updatedAt 淘汰最旧一半，
    #    并从 cacheIndex 同步删除引用。在 wo() 保存前调用。
    prune_fn = (
        "function maybePruneCache(){let ks=[],pre=_o+`v2|`;"
        "for(const k of Object.keys(vo)){if(k.startsWith(_o))ks.push(k)}"
        f"if(ks.length<={CACHE_PRUNE_LIMIT})return;"
        "ks.sort((a,b)=>(vo[a].updatedAt||0)-(vo[b].updatedAt||0));"
        "let drop=Math.floor(ks.length/2);"
        "for(let i=0;i<drop;i++){let k=ks[i],id=k.startsWith(pre)?k.slice(pre.length):k.slice(_o.length);"
        "delete vo[k];delete cacheIndex[id];delete _dirty[k]}bo=!0}"
    )
    old_anchor = "async function wo(_force=false){"
    if js.count(old_anchor) != 1:
        raise ValueError("wo anchor signature not found")
    js = js.replace(old_anchor, prune_fn + old_anchor, 1)

    old_save = "globalThis.__slgCacheDbg.entries=Object.keys(vo).length;bo=!1;"
    new_save = "maybePruneCache();globalThis.__slgCacheDbg.entries=Object.keys(vo).length;bo=!1;"
    if js.count(old_save) != 1:
        raise ValueError("wo save point signature not found")
    js = js.replace(old_save, new_save, 1)
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


compatibility_report_runtime = r'''
(function(){
const root=typeof window!==`undefined`?window:globalThis;
const fixedFields=[`supportLevel`,`activationStrategy`,`templatePath`,`rpaCount`,`splitCount`,`languageBuckets`,`menuType`,`font`,`uniqueTextCount`,`occurrenceCount`,`collisionCount`,`issues`];
function text(value){return String(value??``).slice(0,512)}
function sanitize(report){const r=report&&typeof report===`object`?report:{},rp=r.rpyc&&typeof r.rpyc===`object`?{container:text(r.rpyc.container),preferredSlot:Number(r.rpyc.preferredSlot)||0,pickleProtocol:Number(r.rpyc.pickleProtocol),generationSupport:text(r.rpyc.generationSupport||`UNKNOWN_EXTRACT_ONLY`)}:null,font=r.font&&typeof r.font===`object`?{requiredCount:Number(r.font.requiredCount)||0,coveredCount:Number(r.font.coveredCount)||0,missingCount:Number(r.font.missingCount)||0,hasChineseStyleBucket:!!r.font.hasChineseStyleBucket,hasEastAsianLineBreakEvidence:!!r.font.hasEastAsianLineBreakEvidence}:null;return{supportLevel:text(r.supportLevel||`UNSUPPORTED`),activationStrategy:text(r.activationStrategy||`NONE`),templatePath:text(r.templatePath),rpyc:rp,rpaCount:Math.max(0,Number(r.rpaCount)||0),splitCount:Math.max(0,Number(r.splitCount)||0),languageBuckets:Array.isArray(r.languageBuckets)?r.languageBuckets.slice(0,64).map(text):[],menuType:text(r.menuType||`unknown`),font,uniqueTextCount:Math.max(0,Number(r.uniqueTextCount)||0),occurrenceCount:Math.max(0,Number(r.occurrenceCount)||0),collisionCount:Math.max(0,Number(r.collisionCount)||0),issues:Array.isArray(r.issues)?r.issues.slice(0,32).map(i=>({code:text(i?.code||`unknown_issue`),message:text(i?.message||``)})):[]}}
function sanitizedJson(report){return JSON.stringify(sanitize(report))}
function accumulate(records){const all=root.__slgRenpyCompatibilityRecords||[];for(const record of records||[]){if(record&&typeof record===`object`)all.push(record)}const unique=new Set,contexts=new Map;for(const record of all){const old=text(record?.text);if(!old)continue;unique.add(old);let set=contexts.get(old)||new Set;set.add([text(record?.speaker),text(record?.identifier),text(record?.kind),text(record?.sourcePath)].join(`\u0000`));contexts.set(old,set)}let collision=0;for(const set of contexts.values())if(set.size>1)collision++;root.__slgRenpyCompatibilityRecords=all;const current=root.__slgRenpyCompatibilityReport;if(current){root.__slgRenpyCompatibilityReport=Object.assign({},current,{uniqueTextCount:unique.size,occurrenceCount:all.filter(record=>text(record?.text)).length,collisionCount:collision});root.__slgRenpyCompatibilityReportJson=sanitizedJson(root.__slgRenpyCompatibilityReport);render(root.__slgRenpyCompatibilityReport)}}
function render(report){if(typeof document===`undefined`)return;const safe=sanitize(report),host=document.querySelector(`#root>div`)||document.querySelector(`#root`);if(!host)return;let panel=document.getElementById(`slg-renpy-compatibility-report`);if(!panel){panel=document.createElement(`section`);panel.id=`slg-renpy-compatibility-report`;panel.className=`workshop-renpy-compatibility-report`;panel.style.cssText=`margin:12px 0;padding:14px;border:1px solid color-mix(in srgb,#2563eb 30%,transparent);border-radius:12px;background:color-mix(in srgb,#2563eb 6%,transparent)`;host.append(panel)}panel.hidden=false;panel.replaceChildren();const title=document.createElement(`h3`);title.textContent=`Ren'Py 兼容性预检`;const list=document.createElement(`dl`);const add=(label,value)=>{const row=document.createElement(`div`),dt=document.createElement(`dt`),dd=document.createElement(`dd`);dt.textContent=label;dd.textContent=typeof value===`string`?value:JSON.stringify(value);row.append(dt,dd);list.append(row)};add(`支持等级`,safe.supportLevel);add(`激活策略`,safe.activationStrategy);add(`脚本格式/槽位`,report?.rpyc?`${text(report.rpyc.container)} / ${Number(report.rpyc.preferredSlot)||0}`:`未识别`);add(`模板路径`,safe.templatePath||`未识别`);add(`RPA 版本/数量`,`${safe.rpaCount}`);add(`Split 数量`,`${safe.splitCount}`);add(`语言桶`,safe.languageBuckets.join(`, `)||`无`);add(`菜单类型`,safe.menuType);add(`字体覆盖`,safe.font?`${safe.font.coveredCount}/${safe.font.requiredCount}`:`未返回`);add(`唯一文本/总出现/碰撞`,`${safe.uniqueTextCount} / ${safe.occurrenceCount} / ${safe.collisionCount}`);add(`阻断原因`,safe.issues.map(i=>i.code).join(`, `)||`无`);const exportButton=document.createElement(`button`);exportButton.type=`button`;exportButton.textContent=`导出兼容性 JSON`;exportButton.onclick=()=>{const blob=new Blob([sanitizedJson(safe)],{type:`application/json`}),url=URL.createObjectURL(blob),a=document.createElement(`a`);a.href=url;a.download=`renpy-compatibility-report.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),0)};panel.append(title,list,exportButton)}
root.__slgSanitizeRenpyCompatibilityReport=sanitize;root.__slgRenpyCompatibilitySanitizedJson=sanitizedJson;root.__slgAccumulateRenpyCompatibility=accumulate;root.__slgRenderRenpyCompatibilityReport=report=>{const safe=sanitize(report);root.__slgRenpyCompatibilityReport=safe;root.__slgRenpyCompatibilityReportJson=sanitizedJson(safe);render(safe);return safe};if(root.__slgRenpyCompatibilityReport)root.__slgRenderRenpyCompatibilityReport(root.__slgRenpyCompatibilityReport)})()
'''


dialogue_id_runtime = r'''
(function(){
const root=typeof window!==`undefined`?window:globalThis;
const ID_RE=/^[A-Za-z0-9._:-]{1,256}$/;
const defaultCapability={extractorVerified:false,writerVerified:false,astVersionVerified:false,rollbackValidated:false};
root.__slgDialogueIdCapability=Object.assign({},defaultCapability,root.__slgDialogueIdCapability||{});
root.__slgDialogueIdMode=false;
root.__slgDialogueIdRecords=[];
root.__slgDialogueIdTranslations=[];
root.__slgDialogueIdStatus={enabled:false,available:false,reason:`default_global_string_map`,contextCount:0};
function reliable(record){return record&&record.kind===`DIALOGUE`&&typeof record.identifier===`string`&&ID_RE.test(record.identifier)&&typeof record.text===`string`&&record.text.length>0&&record.coverageCertain===true}
function assess(requested){
const records=root.__slgDialogueIdRecords||[],cap=root.__slgDialogueIdCapability||defaultCapability;
const ids=new Map,valid=records.filter(reliable);
for(const record of valid){const prior=ids.get(record.identifier);if(prior&&prior!==record.text){root.__slgDialogueIdMode=false;root.__slgDialogueIdStatus={enabled:false,available:false,reason:`identifier_reused_for_multiple_old`,contextCount:0};render();return root.__slgDialogueIdStatus}ids.set(record.identifier,record.text)}
const ready=!!cap.extractorVerified&&!!cap.writerVerified&&!!cap.astVersionVerified&&!!cap.rollbackValidated&&valid.length>0;
let reason=ready?`ready`:(!cap.extractorVerified?`extractor_identifier_unverified`:!cap.writerVerified?`writer_ast_unverified`:!cap.astVersionVerified?`target_ast_version_unverified`:!cap.rollbackValidated?`rollback_not_validated`:`no_reliable_dialogue_identifier`);
const enabled=!!requested&&ready;
root.__slgDialogueIdMode=enabled;
root.__slgDialogueIdStatus={enabled,available:ready,reason:enabled?`enabled`:reason,contextCount:ids.size};
render();return root.__slgDialogueIdStatus}
function register(records){
const prior=root.__slgDialogueIdRecords||[];
root.__slgDialogueIdRecords=prior.concat((records||[]).filter(reliable));
return assess(root.__slgDialogueIdMode)}
function render(){
if(typeof document===`undefined`)return;
const host=document.querySelector(`#root>div`)||document.querySelector(`#root`);if(!host)return;
let panel=document.getElementById(`slg-dialogue-id-mode`);
if(!panel){panel=document.createElement(`section`);panel.id=`slg-dialogue-id-mode`;panel.className=`workshop-dialogue-id-mode`;panel.style.cssText=`margin:12px 0;padding:12px;border:1px solid color-mix(in srgb,#7c3aed 30%,transparent);border-radius:12px;background:color-mix(in srgb,#7c3aed 6%,transparent)`;host.append(panel)}
panel.replaceChildren();const label=document.createElement(`label`),box=document.createElement(`input`);box.type=`checkbox`;box.checked=!!root.__slgDialogueIdMode;box.disabled=!root.__slgDialogueIdStatus.available;box.onchange=()=>assess(box.checked);label.append(box,document.createTextNode(` 高级对话 ID 模式（默认关闭）`));const detail=document.createElement(`small`);detail.style.display=`block`;detail.style.marginTop=`6px`;detail.textContent=root.__slgDialogueIdStatus.available?`已验证 ${root.__slgDialogueIdStatus.contextCount} 个对话 ID；菜单、角色名和 UI 仍使用字符串映射。`:`已回退全局字符串映射：${root.__slgDialogueIdStatus.reason}`;panel.append(label,detail)
}
root.__slgRegisterDialogueRecords=register;
root.__slgPrepareDialogueIdMode=(requested,translations)=>{root.__slgDialogueIdTranslations=Array.isArray(translations)?translations:[];return assess(!!requested)};
root.__slgSetDialogueIdMode=(requested)=>assess(!!requested);
render();
})()
'''


def patch_assets(js: str, css: str) -> tuple[str, str]:
    verify_canonical_base_text(js, css)
    copy_contract = "\n/* workshop-copy:" + "|".join(WORKSHOP_COPY) + " */\n"
    patched = patch_scan_flow(js)
    patched = patch_translation_cache(patched)
    patched = patch_translation_network(patched)
    patched = patch_translation_memory(patched)
    patched = patch_local_engine(patched)
    patched = patch_extraction_rules(patched)
    patched = patch_short_text_and_code_filters(patched)
    patched = patch_rpyc_string_pipeline(patched)
    patched = patch_speed_tuning(patched)
    patched = patch_output_write_cache(patched)
    patched = patch_candidate_filter(patched)
    patched = patch_translation_quality(patched)
    patched = patch_cache_memory(patched)
    patched += compatibility_report_runtime
    patched += dialogue_id_runtime
    runtime = patch_saves_runtime(WORKSHOP_RUNTIME)
    runtime = runtime.replace(
        "当前只检查了基础 APK",
        "已合并读取基础 APK 与全部 split 资源",
        1,
    )
    return patched + copy_contract + enhance_runtime(runtime), css + "\n" + WORKSHOP_CSS


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
