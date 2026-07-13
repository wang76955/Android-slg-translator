from __future__ import annotations

from pathlib import Path
import re


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
.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav{display:grid!important}
.workshop-hero{margin:18px 16px 4px;padding:22px 20px;border-radius:24px;background:var(--workshop-primary);color:var(--workshop-on-primary);box-shadow:0 16px 36px color-mix(in oklch,var(--workshop-primary) 20%,transparent)}
.workshop-hero small{display:block;font-size:13px;opacity:.8}.workshop-hero h1{margin:7px 0 18px;font-size:26px;line-height:1.18;font-weight:750;letter-spacing:-.02em}
.workshop-runtime main{display:none!important;padding:16px 16px 104px!important;background:var(--workshop-bg)!important}.workshop-runtime main>div,.workshop-runtime main>section,.workshop-runtime main details{border-color:color-mix(in oklch,var(--workshop-ink) 12%,transparent)!important;background:var(--workshop-surface)!important;border-radius:18px!important;box-shadow:none!important}.workshop-runtime button[class*="bg-blue"]{min-height:48px;background:var(--workshop-primary)!important;color:var(--workshop-on-primary)!important;border-radius:16px!important}.workshop-runtime [class*="text-blue"]{color:var(--workshop-primary)!important}
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
.workshop-scan-elapsed{display:block;margin-top:6px;color:var(--workshop-muted);font-size:13px;font-variant-numeric:tabular-nums}
.workshop-progress{height:4px;margin-top:14px;border-radius:999px;background:color-mix(in oklch,var(--workshop-primary) 14%,transparent);overflow:hidden}
.workshop-progress>i{display:block;width:38%;height:100%;border-radius:inherit;background:var(--workshop-primary);transition:width 220ms ease-out}
.workshop-summary-list{display:grid;gap:10px;margin:16px 0 0;padding:0;list-style:none}
.workshop-summary-row{display:flex;justify-content:space-between;gap:16px;font-size:14px}
.workshop-summary-row span:first-child{color:var(--workshop-muted)}
.workshop-summary-row span:last-child{text-align:right;font-weight:700}
.workshop-detail-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;margin-top:12px;padding:0;border:0;background:transparent;color:var(--workshop-primary);font-weight:700;text-align:left}
.workshop-detail-body{display:none;max-height:240px;margin-top:8px;padding:12px;border-radius:12px;background:color-mix(in oklch,var(--workshop-ink) 5%,var(--workshop-surface));color:var(--workshop-muted);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;line-height:1.55;white-space:pre-wrap;overflow:auto;overflow-wrap:anywhere}
.workshop-detail-body[data-open="true"]{display:block}
.workshop-live-line{margin:12px 0 0;padding:10px 12px;border-radius:12px;background:color-mix(in oklch,var(--workshop-primary) 8%,var(--workshop-surface));color:var(--workshop-muted);font-size:13px;line-height:1.45;overflow-wrap:anywhere}
.workshop-task-shell[data-workshop-state="idle"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="scanning"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="ready"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="translating"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="patching"] .workshop-progress{display:block}
.workshop-task-shell[data-workshop-state="completed"] .workshop-progress{display:none}
.workshop-task-shell[data-workshop-state="failed"] .workshop-progress{display:none}
.workshop-settings-shell{position:fixed;z-index:40;inset:0;display:flex;flex-direction:column;gap:16px;padding:20px 16px max(24px,env(safe-area-inset-bottom));background:var(--workshop-bg);color:var(--workshop-ink);overflow:auto}
.workshop-settings-shell[hidden]{display:none!important}
.workshop-settings-card{padding:20px;border:1px solid color-mix(in oklch,var(--workshop-ink) 12%,transparent);border-radius:20px;background:var(--workshop-surface)}
.workshop-settings-card label{display:block;margin-bottom:8px;font-size:14px;font-weight:700}
.workshop-settings-input{box-sizing:border-box;width:100%;min-height:52px;padding:12px 14px;border:1px solid color-mix(in oklch,var(--workshop-ink) 20%,transparent);border-radius:14px;background:var(--workshop-bg);color:var(--workshop-ink);font-size:16px}
.workshop-settings-input:focus{outline:3px solid color-mix(in oklch,var(--workshop-primary) 28%,transparent);outline-offset:2px;border-color:var(--workshop-primary)}
.workshop-settings-save{width:100%;min-width:48px;min-height:52px;margin-top:16px;border:0;border-radius:16px;background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:750;font-size:15px}
.workshop-settings-helper{margin:12px 0 0;color:var(--workshop-muted);font-size:13px;line-height:1.5}
.workshop-settings-title{margin:0 0 16px;font-size:18px;line-height:1.3;font-weight:750}
.workshop-settings-field{display:block;margin-top:14px}
.workshop-settings-field:first-of-type{margin-top:0}
.workshop-settings-field>span{display:block;margin-bottom:7px;font-size:14px;font-weight:700}
.workshop-settings-conditional[hidden]{display:none!important}
.workshop-settings-error{margin:6px 0 0;color:var(--workshop-error);font-size:13px;line-height:1.4}
.workshop-settings-status{margin:10px 0 0;color:var(--workshop-muted);font-size:13px;line-height:1.45}
.workshop-primary-action{display:flex;align-items:center;justify-content:center;width:100%;min-height:52px;margin-top:auto;border:0;border-radius:16px;background:var(--workshop-primary);color:var(--workshop-on-primary);font-weight:750;font-size:15px}
.workshop-secondary-action{min-width:48px;min-height:48px;margin-top:8px;border:0;background:transparent;color:var(--workshop-primary);font-weight:700}
.workshop-error-card{border-color:color-mix(in oklch,var(--workshop-error) 30%,transparent);background:color-mix(in oklch,var(--workshop-error) 7%,var(--workshop-surface))}
.workshop-error-title{margin:0;color:var(--workshop-error);font-size:18px;font-weight:750}
.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}
.workshop-runtime[data-workshop-task="active"] main{display:none!important}
body:has(.workshop-runtime[data-workshop-task="active"]) .workshop-bottom-nav{display:none!important}
.workshop-bottom-nav{position:fixed;z-index:30;left:12px;right:12px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(3,1fr);padding:6px;border:1px solid color-mix(in oklch,var(--workshop-ink) 12%,transparent);border-radius:22px;background:color-mix(in oklch,var(--workshop-bg) 94%,transparent);box-shadow:0 10px 35px color-mix(in oklch,var(--workshop-ink) 16%,transparent)}
.workshop-bottom-nav button{min-height:52px;border:0;border-radius:16px;background:transparent;color:var(--workshop-muted);font-size:13px;font-weight:650}.workshop-bottom-nav button[aria-current="page"]{background:var(--workshop-surface);color:var(--workshop-primary)}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
"""

# Task shell runtime: source React controls stay mounted and are activated via
# bubbling events. The runtime owns only the visible state-driven shell.
WORKSHOP_RUNTIME = r"""
;(()=>{const ID="workshop-runtime";let shell=null,runtimeRoot=null,settingsShell=null,settingsOpen=false,settingsRestored=false,sourceButton=null,startButton=null,installButton=null,reactApiInput=null,pendingApiKey=null,observer=null,debounceTimer=0,lastSnapshot="",manualIdle=false,retrying=false,detailsOpen=false;
function textNode(tag,cls,text){const el=document.createElement(tag);el.className=cls;if(text!==undefined)el.textContent=text;return el}
function setReactInputValue(input,value){if(!input)return;input.focus();const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")?.set;if(setter)setter.call(input,value);else input.value=value;input.dispatchEvent(new Event("input",{bubbles:true}));input.dispatchEvent(new Event("change",{bubbles:true}));input.blur()}
function findReactApiInput(){return[...document.querySelectorAll("#root input")].find(el=>!el.closest(".workshop-settings-shell")&&(el.type==="password"||/api.?key/i.test(el.placeholder||el.getAttribute("aria-label")||"")))}
function applyApiKeyToReact(){const input=findReactApiInput();if(!input)return false;reactApiInput=input;if(pendingApiKey!==null&&input.value!==pendingApiKey)setReactInputValue(input,pendingApiKey);return true}
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
function closeSettings(){settingsOpen=false;manualIdle=false;lastSnapshot="";if(settingsShell)settingsShell.hidden=true;if(shell)shell.hidden=false;refresh()}
function openSettings(){settingsOpen=true;manualIdle=true;reactApiInput=reactApiInput||findReactApiInput();if(!settingsShell){settingsShell=document.createElement("section");settingsShell.className="workshop-settings-shell";settingsShell.setAttribute("role","dialog");settingsShell.setAttribute("aria-modal","true");settingsShell.setAttribute("aria-label","我的设置");const top=textNode("header","workshop-task-topbar");const back=textNode("button","workshop-task-back","‹");back.type="button";back.setAttribute("aria-label","返回任务");back.onclick=closeSettings;top.append(back,textNode("h1","","我的设置"));const card=textNode("section","workshop-settings-card");const prefs=readSettingsPrefs();const title=textNode("h2","workshop-settings-title","翻译服务");const provider=selectControl("settingsProvider","供应商",[["openai","OpenAI"],["deepseek","DeepSeek"],["custom","自定义接口"]],prefs.providerId);provider.id="settingsProvider";let option=provider.select.options[1];option.value="deepseek";option=provider.select.options[2];option.value="custom";const model=selectControl("settingsModel","模型",PROVIDERS[prefs.providerId].models,prefs.model);model.id="settingsModel";const customWrap=textNode("div","workshop-settings-conditional");const customBaseURL=inputControl("settingsCustomBaseURL","自定义 Base URL","url",prefs.customBaseURL,"https://your-api.com/v1");customBaseURL.id="settingsCustomBaseURL";const customModel=inputControl("settingsCustomModel","自定义模型名","text",prefs.customModel,"例如：qwen-plus");customModel.id="settingsCustomModel";customWrap.append(customBaseURL.field,customModel.field);const api=inputControl("settingsApiKey","API Key","password",reactApiInput?.value??pendingApiKey??"","");const label=api.field;label.htmlFor="settingsApiKey";const input=api.input;input.id="settingsApiKey";const error=textNode("p","workshop-settings-error");error.hidden=true;const save=textNode("button","workshop-settings-save","保存");save.type="button";const helper=textNode("p","workshop-settings-status workshop-settings-helper","API Key 仅保存在本机。");const updateProvider=()=>{const providerId=provider.select.value;replaceSelectOptions(model.select,PROVIDERS[providerId].models,providerId===prefs.providerId?prefs.model:"");customWrap.hidden=providerId!=="custom";error.hidden=true};provider.select.onchange=updateProvider;customWrap.hidden=prefs.providerId!=="custom";save.onclick=()=>{const next={providerId:provider.select.value,model:model.select.value,customBaseURL:customBaseURL.input.value.trim(),customModel:customModel.input.value.trim()};if(next.providerId==="custom"&&(!next.customBaseURL||!next.customModel)){error.textContent="请填写自定义 Base URL 和模型名";error.hidden=false;return}error.hidden=true;pendingApiKey=input.value;saveSettingsPrefs(next);applySettingsToReact(next);helper.textContent=`已保存：${PROVIDERS[next.providerId].label} · ${next.providerId==="custom"?next.customModel:next.model}`;};card.append(title,provider.field,model.field,customWrap,api.field,error,save,helper);settingsShell.append(top,card);runtimeRoot?.append(settingsShell)}settingsShell.hidden=false;if(shell)shell.hidden=true}
function findButton(label){return[...document.querySelectorAll("#root button")].find(el=>!el.closest(".workshop-task-shell")&&el.textContent&&el.textContent.includes(label))}
function triggerReactButton(button){manualIdle=false;const target=button===startButton?(findButton("开始翻译")||button):button;const isStart=button===startButton||button?.textContent?.includes("开始翻译");if(isStart&&target?.disabled){const snap=readTaskSnapshot();setWorkshopState("ready",{...snap,apiRequired:true});return}target?.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,view:window}))}
function sourceText(){const root=document.querySelector("#root");if(!root)return"";const clone=root.cloneNode(true);clone.querySelector(".workshop-task-shell")?.remove();clone.querySelector(".workshop-bottom-nav")?.remove();return clone.textContent||""}
function readProgressLog(){const source=[...document.querySelectorAll("#root details")].find(el=>!el.closest(".workshop-task-shell")&&el.querySelector('[class*="font-mono"]'));const panel=source?.querySelector('[class*="font-mono"]');const lines=[...(panel?.children||[])].slice(-40).map(row=>(row.innerText||row.textContent||"").trim()).filter(Boolean);return{raw:lines.join("\n"),latest:lines.at(-1)||""}}
function readTaskSnapshot(){const text=sourceText();const selected=text.match(/已选择\s*[:：]?\s*([^\n]{1,180}?)(?=发现|正在|处理|$)/);const fileName=selected?.[1]?.trim()||"";const found=text.match(/发现\s*(\d+)\s*个可翻译文件/);const count=found?.[1]||"";const progress=text.match(/正在处理脚本\s*(\d+)\s*\/\s*(\d+)/);const current=progress?.[1]||"0",total=progress?.[2]||count||"0";const translated=text.match(/共翻译\s*(\d+)\s*条文本/)?.[1]||"";const log=readProgressLog();const failed=[...document.querySelectorAll("#root *")].find(el=>!el.closest(".workshop-task-shell")&&el.textContent?.includes("写入补丁 APK 失败"));if(failed&&/ENOSPC|No space left/i.test(failed.textContent||""))return{state:"failed",reason:"space",raw:failed.textContent};if(/翻译完成/.test(text))return{state:"completed",fileName,count,translated,raw:log.raw,latest:log.latest};if(/正在生成 Ren'Py 补丁 APK/.test(text))return{state:"patching",fileName,count,current,total,raw:log.raw,latest:log.latest};if(/正在处理脚本|翻译中|开始处理/.test(text))return{state:"translating",fileName,count,current,total,raw:log.raw,latest:log.latest};if(count!=="")return{state:"ready",fileName,count};if(fileName||/正在扫描|正在检查文件|检查文件/.test(text))return{state:"scanning",fileName};return{state:"idle"}}
function detailToggle(raw,live=false){const wrap=textNode("div","workshop-detail-wrap");const toggle=textNode("button","workshop-detail-toggle",detailsOpen?"收起详情":"处理详情");toggle.type="button";toggle.setAttribute("aria-expanded",String(detailsOpen));const body=textNode("div","workshop-detail-body",raw||"暂无更多信息");body.dataset.open=String(detailsOpen);const scrollLatest=()=>{if(live&&detailsOpen)window.requestAnimationFrame(()=>{body.scrollTop=body.scrollHeight})};toggle.onclick=()=>{detailsOpen=!detailsOpen;body.dataset.open=String(detailsOpen);toggle.setAttribute("aria-expanded",String(detailsOpen));toggle.textContent=detailsOpen?"收起详情":"处理详情";scrollLatest()};wrap.append(toggle,body);scrollLatest();return wrap}
 function renderTopbar(state){const bar=textNode("header","workshop-task-topbar");const back=textNode("button","workshop-task-back","‹");back.type="button";back.setAttribute("aria-label","返回");back.onclick=()=>setWorkshopState("idle",{fromBack:true});const label=state==="scanning"?"读取中":state==="ready"?"已就绪":state==="translating"?"翻译中":state==="patching"?"生成中":state==="completed"?"已完成":state==="failed"?"失败":"";bar.append(back,textNode("h1","","APK 翻译"),textNode("span","workshop-topbar-state",label));return bar}
function fileRow(fileName){const row=textNode("div","workshop-file-row");row.append(textNode("span","workshop-file-icon","APK"));const copy=textNode("div","workshop-file-copy");copy.append(textNode("div","workshop-file-name",fileName||"尚未选择 APK"),textNode("div","workshop-file-meta",fileName?"已选择文件":"支持 Android APK 文件"));row.append(copy);return row}
function actionButton(label,handler,secondary){const button=textNode("button",secondary?"workshop-secondary-action":"workshop-primary-action",label);button.type="button";button.onclick=handler;return button}
function renderStateBody(state,payload){const body=textNode("div","workshop-task-body");if(state==="idle"){const brand=textNode("section","workshop-brand-panel");brand.append(textNode("p","","今天翻译什么？"),textNode("h2","","让喜欢的故事，用中文继续。"));const card=textNode("section","workshop-task-card");card.append(fileRow(""),textNode("p","workshop-state-copy","选择一个 APK，开始你的中文旅程。"),actionButton("选择 APK 文件",()=>triggerReactButton(sourceButton)));body.append(brand,card);return body}
const card=textNode("section",state==="failed"?"workshop-task-card workshop-error-card":"workshop-task-card");card.append(fileRow(payload.fileName));if(state==="scanning"){card.append(textNode("p","workshop-state-copy","正在检查文件"));const progress=textNode("div","workshop-progress");progress.append(textNode("i","",""));card.append(progress,detailToggle(payload.raw||"正在检查 APK 文件，请稍候。"));body.append(card);return body}
if(state==="ready"){card.append(textNode("p","workshop-state-copy","可以开始了"));if(payload.apiRequired)card.append(textNode("p","workshop-state-copy","请先配置 API Key"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","可翻译文件"),textNode("span","",`${payload.count||0} 个`));list.append(row);card.append(list,detailToggle(payload.raw||"文件检查已完成。"));body.append(card,actionButton("开始翻译",()=>triggerReactButton(startButton)));return body}
if(state==="translating"){card.append(textNode("p","workshop-state-copy","正在翻译文本"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","脚本进度"),textNode("span","",`${payload.current||0} / ${payload.total||payload.count||0}`));list.append(row);const progress=textNode("div","workshop-progress");const fill=textNode("i","","");const current=Number(payload.current)||0,total=Number(payload.total)||0;fill.style.width=`${total?Math.max(6,Math.min(100,Math.round(current/total*100))):20}%`;progress.append(fill);card.append(list,progress);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"正在翻译脚本文本，请保持应用在前台。",true));body.append(card);return body}
if(state==="patching"){card.append(textNode("p","workshop-state-copy","正在生成补丁 APK"));const progress=textNode("div","workshop-progress");progress.append(textNode("i","",""));card.append(progress);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"译文已经完成，正在写入并签名补丁 APK。",true));body.append(card);return body}
if(state==="completed"){card.append(textNode("p","workshop-state-copy","补丁 APK 已生成"));const list=textNode("ul","workshop-summary-list");const row=textNode("li","workshop-summary-row");row.append(textNode("span","","已翻译文本"),textNode("span","",`${payload.translated||0} 条`));list.append(row);card.append(list);if(payload.latest)card.append(textNode("p","workshop-live-line",payload.latest));card.append(detailToggle(payload.raw||"翻译和补丁写入已经完成。",true));body.append(card,actionButton("安装补丁版",()=>triggerReactButton(installButton)));return body}
const title=textNode("h2","workshop-error-title","手机空间不足");const copy=textNode("p","workshop-state-copy","请释放空间后重试。"),details=detailToggle(payload.raw||"ENOSPC|No space left");card.append(title,copy,details);body.append(card,actionButton("释放空间后重试",()=>retryTask({fileName:payload.fileName,raw:""})),actionButton("重新选择 APK",()=>triggerReactButton(sourceButton),true));return body}
function setWorkshopState(state,payload={}){if(!shell)return;shell.dataset.workshopState=state;shell.setAttribute("data-workshop-state",state);shell.dataset.workshopTask=state==="idle"?"idle":"active";const task=shell.dataset.workshopTask;shell.setAttribute("data-workshop-task",shell.dataset.workshopTask);runtimeRoot?.setAttribute("data-workshop-state",state);runtimeRoot?.setAttribute("data-workshop-task",task);shell.classList.remove("workshop-state-idle","workshop-state-scanning","workshop-state-ready","workshop-state-translating","workshop-state-patching","workshop-state-completed","workshop-state-failed");shell.classList.add(`workshop-state-${state}`);runtimeRoot?.classList.remove("workshop-state-idle","workshop-state-scanning","workshop-state-ready","workshop-state-translating","workshop-state-patching","workshop-state-completed","workshop-state-failed");runtimeRoot?.classList.add(`workshop-state-${state}`);shell.replaceChildren(renderTopbar(state),renderStateBody(state,payload))}
function snapshotKey(s){return[s.state,s.fileName||"",s.count||"",s.current||"",s.total||"",s.translated||"",s.reason||"",s.raw||""].join("|")}
function retryTask(payload){retrying=true;triggerReactButton(startButton||sourceButton);setWorkshopState("scanning",payload);window.setTimeout(()=>{retrying=false;refresh()},600)}
function refresh(){if(!shell||manualIdle||retrying||settingsOpen)return;const snap=readTaskSnapshot(),key=snapshotKey(snap);if(key===lastSnapshot)return;lastSnapshot=key;setWorkshopState(snap.state,snap)}
 function decorate(){const heading=[...document.querySelectorAll("#root h2")].find(el=>el.textContent&&el.textContent.includes("选择游戏 APK"));if(heading?.parentElement)heading.parentElement.classList.add("workshop-picker-source");startButton=findButton("开始翻译");if(startButton){startButton.classList.add("workshop-start-button");startButton.setAttribute("aria-hidden","true")}installButton=findButton("安装补丁版");if(installButton)installButton.setAttribute("aria-hidden","true");sourceButton=findButton("选择");if(sourceButton){sourceButton.classList.add("workshop-source-button");sourceButton.setAttribute("aria-label","选择 APK 文件");sourceButton.setAttribute("aria-hidden","true")}applyApiKeyToReact()}
function mount(){decorate();if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;const app=document.querySelector("#root>div");if(!app||!sourceButton)return;runtimeRoot=app;if(!shell){app.classList.add(ID);shell=document.createElement("section");shell.className="workshop-task-shell";shell.dataset.workshopState="idle";shell.dataset.workshopTask="idle";app.prepend(shell);const nav=document.createElement("nav");nav.className="workshop-bottom-nav";nav.setAttribute("aria-label","主导航");[["首页",()=>window.scrollTo({top:0,behavior:"smooth"})],["作品",()=>document.querySelector("#root")?.scrollIntoView({behavior:"smooth",block:"start"})],["我的",openSettings]].forEach(([label,action],index)=>{const button=textNode("button","workshop-touch",label);button.type="button";if(index===0)button.setAttribute("aria-current","page");button.onclick=()=>{[...nav.children].forEach(el=>el.removeAttribute("aria-current"));button.setAttribute("aria-current","page");action()};nav.append(button)});app.append(nav);setWorkshopState("idle",{})}refresh()}
function schedule(){clearTimeout(debounceTimer);debounceTimer=setTimeout(mount,120)}
document.addEventListener("click",event=>{if(event.target.closest?.(".workshop-task-back"))manualIdle=true},{capture:true});observer=new MutationObserver(schedule);observer.observe(document.querySelector("#root")||document.documentElement,{childList:true,subtree:true,characterData:true});window.addEventListener("popstate",()=>{if(settingsOpen){closeSettings();return}if(shell?.dataset.workshopTask==="active"){manualIdle=true;setWorkshopState("idle",{fromBack:true})}});document.readyState==="loading"?document.addEventListener("DOMContentLoaded",mount):mount()})();
"""


def patch_scan_flow(js: str) -> str:
    old = """let t=await E.listApkEntries({uri:e.uri});s(t.entries);try{let t=await Promise.race([E.getApkPackageName({uri:e.uri}),new Promise(e=>setTimeout(()=>e({packageName:``}),3e3))]);t.packageName&&(p(t.packageName),O(`识别到包名: `+t.packageName,`info`))}catch{}"""
    new = """let t=await E.listApkEntries({uri:e.uri});s(t.entries),O(`APK 检查${t.cacheHit?`（缓存）`:``}用时 ${Math.max(0,Math.round((t.scanDurationMs||0)/100)/10)} 秒`,`info`);try{let n=t.packageName?{packageName:t.packageName}:await Promise.race([E.getApkPackageName({uri:e.uri}),new Promise(e=>setTimeout(()=>e({packageName:``}),3e3))]);n.packageName&&(p(n.packageName),O(`识别到包名: `+n.packageName,`info`))}catch{}"""
    if old not in js:
        raise ValueError("APK scan flow signature not found")
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
        'const title=textNode("h2","workshop-error-title"',
        'if(payload.reason==="scan"){const title=textNode("h2","workshop-error-title","检查失败");const copy=textNode("p","workshop-state-copy","无法读取这个 APK。请将文件移动到手机本地存储后重新选择。");card.append(title,copy,detailToggle(payload.raw||"APK scan failed"));body.append(card,actionButton("重新选择 APK",()=>triggerReactButton(sourceButton)));return body}const title=textNode("h2","workshop-error-title"',
        1,
    )
    runtime = runtime.replace(
        "function setWorkshopState(state,payload={}){if(!shell)return;",
        'function setWorkshopState(state,payload={}){if(!shell)return;state==="scanning"?startScanClock():stopScanClock();',
        1,
    )
    return runtime


def patch_translation_cache(js: str) -> str:
    old_state = 'var _o=`slg-translator-cache:`,vo={},yo=!1,bo=!1,bp=Promise.resolve();'
    new_state = 'var _o=`slg-translator-cache:`,vo={},cacheIndex={},yo=!1,bo=!1,bp=Promise.resolve();'
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


def patch_assets(js: str, css: str) -> tuple[str, str]:
    copy_contract = "\n/* workshop-copy:" + "|".join(WORKSHOP_COPY) + " */\n"
    return patch_translation_cache(patch_scan_flow(js)) + copy_contract + enhance_runtime(WORKSHOP_RUNTIME), css + "\n" + WORKSHOP_CSS


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
