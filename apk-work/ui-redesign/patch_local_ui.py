#!/usr/bin/env python3
"""On-device translation kernel UI patches.

These helpers are imported by ``patch_workshop_ui.py``:

* ``patch_local_engine(js)`` - adds the "local" provider to the React app and
  routes batch translation through ``window.__slgLocalTranslate`` when the
  workshop runtime arms it.
* ``enhance_local_runtime(runtime)`` - extends the workshop settings overlay
  with a "本机离线翻译" provider, model download/delete management, status
  polling and the localTranslate bridge that talks to the native
  LocalTranslationSupport plugin methods.
"""

from __future__ import annotations


_CORE_LOCAL_BRIDGE = r'''
globalThis.__slgCoreLocalTranslate=globalThis.__slgCoreLocalTranslate||async function({texts,sourceLang,targetLang,onProgress,engine}){
  const plugin=globalThis.Capacitor?.Plugins?.FileManager;
  if(!plugin||typeof plugin.translateLocal!=="function")throw new Error("本地翻译桥不可用");
  const input=Array.isArray(texts)?texts:[];
  const items=input;
  const translations=new Map(),warnings=[],rejected=[];
  const totalBatches=Math.ceil(input.length/20);
  try{
    for(let offset=0,batch=0;offset<input.length;offset+=20,batch++){
      const chunk=items.slice(offset,offset+20);
      let write=0;
      for(let i=0;i<chunk.length;i++){
        const item=chunk[i]||{},text=String(item.text||"");
        if(text.trim().length>0)chunk[write++]={keyPath:String(item.keyPath||""),text};
      }
      chunk.length=write;
      if(!chunk.length)continue;
      if(typeof onProgress==="function")onProgress(translations.size,input.length,"translating",{stage:"start",currentBatch:batch+1,totalBatches,batchSize:chunk.length});
      const result=await plugin.translateLocal({texts:chunk,sourceLang:sourceLang||"en",targetLang:targetLang||"zh",engine:engine||"mlkit"});
      const entries=result&&result.translations instanceof Map?Array.from(result.translations.entries()):Object.entries(result&&result.translations||{});
      for(const [key,value] of entries){if(value&&String(value).trim().length>0)translations.set(key,String(value))}
      if(Array.isArray(result&&result.warnings))warnings.push(...result.warnings);
      if(Array.isArray(result&&result.rejected))rejected.push(...result.rejected);
      if(typeof onProgress==="function")onProgress(translations.size,input.length,"translating",{stage:"completed",completedBatches:batch+1,totalBatches,currentBatch:batch+1,batchSize:chunk.length});
    }
    return {translations,successCount:translations.size,warnings,rejected};
  }finally{
    await globalThis.__slgReleaseLocalResources?.();
  }
};
globalThis.__slgReleaseLocalResources=globalThis.__slgReleaseLocalResources||async function(){
  const plugin=globalThis.Capacitor?.Plugins?.FileManager;
  if(!plugin||typeof plugin.releaseLocalResources!=="function")return false;
  try{await plugin.releaseLocalResources();return true}catch(error){globalThis.__slgLocalReleaseError=error&&error.message||String(error);return false}
};
'''


def patch_local_engine(js: str) -> str:
    """Add the on-device provider to the React provider list."""
    old_providers = "_e=[{id:`openai`,"
    local_provider = (
        "_e=[{id:`local`,name:`本机离线翻译（免费）`,baseURL:``,models:["
        "{id:`mlkit`,name:`轻量翻译（ML Kit）`,supportsJsonMode:!1},"
        "{id:`qwen`,name:`高质量翻译（本地模型）`,supportsJsonMode:!1}]},{id:`openai`,"
    )
    if js.count(old_providers) != 1:
        raise ValueError("Local engine provider anchor not found")
    js = js.replace(old_providers, local_provider, 1)
    js = _CORE_LOCAL_BRIDGE + js

    # Route batch translation to the local kernel when the workshop runtime
    # arms window.__slgLocalTranslate (local engine selected in settings).
    old_lo = (
        "async function Lo(e){let{texts:t,sourceLang:n,targetLang:r,baseURL:i,apiKey:a,"
        "model:o,glossary:s,batchSize:c=jo,onProgress:l}=e;if(await Co(),t.length===0)"
    )
    local_branch = (
        "if((globalThis.__slgLocalTranslate||globalThis.__slgLocalTranslateImpl||globalThis.__slgLocalSelected||"
        "Array.from(globalThis.document?.querySelectorAll?.(\"select\")||[]).some(_s=>_s.value===\"local\")||"
        "(()=>{try{return JSON.parse(globalThis.localStorage?.getItem?.(\"slg-workshop-settings-v1\")||\"null\")?.providerId===\"local\"}"
        "catch(_x){return false}})())){let _engine=\"\";try{"
        "const _s=document.querySelector(\"#settingsProvider\");if(_s&&_s.value===\"local\"){"
        "const _m=document.querySelector(\"#settingsModel\");_engine=(_m&&_m.value===\"qwen\")?\"llm\":\"mlkit\"}}catch(_x){}"
        "if(!_engine){try{const _p=JSON.parse(localStorage.getItem(\"slg-workshop-settings-v1\")||\"null\");"
        "if(_p&&_p.providerId===\"local\")_engine=_p.model===\"qwen\"?\"llm\":\"mlkit\"}catch(_x){}}"
        "if(_engine){let _lr=null,_le=null;try{"
        "_lr=await (globalThis.__slgLocalTranslate||globalThis.__slgLocalTranslateImpl||globalThis.__slgCoreLocalTranslate)("
        "{texts:t,sourceLang:n,targetLang:r,onProgress:l,engine:_engine})"
        "}catch(e){_le=e}if(_lr)return _lr;"
        "if(_le)return {translations:new Map(),successCount:0,"
        "warnings:[String(_le&&_le.message||_le)],error:String(_le&&_le.message||_le)}}}"
    )
    new_lo = old_lo.replace(
        "}=e;if(await Co(),t.length===0)", "}=e;" + local_branch + "if(await Co(),t.length===0)"
    )
    if js.count(old_lo) != 1:
        raise ValueError("Local engine Lo anchor not found")
    return js.replace(old_lo, new_lo, 1)


_LOCAL_HELPERS = r"""
function localEngineFor(prefs){return prefs&&prefs.providerId==="local"?(prefs.model==="qwen"?"llm":"mlkit"):""}
function installLocalHooks(prefs){const engine=localEngineFor(prefs);window.__slgLocalEngine=engine;window.__slgLocalSelected=!!engine;window.__slgLocalTranslate=engine?localTranslate:null;return engine}
async function localTranslate({texts,sourceLang,targetLang,onProgress,engine}){
  const plugin=window.Capacitor?.Plugins?.FileManager;
  if(!plugin||typeof plugin.translateLocal!=="function")return null;
  const activeEngine=engine||window.__slgLocalEngine||"mlkit";
  const input=Array.isArray(texts)?texts:[];
  if(input.length===0)return {translations:new Map(),successCount:0,warnings:[]};
  try{
    if(typeof onProgress==="function")onProgress(0,input.length,"translating");
    const map=new Map();const warnings=[];let failedBatches=0,splitBatches=0,totalBatches=Math.ceil(input.length/20);
    const items=input;
    for(let offset=0,b=0;offset<input.length;offset+=20,b++){
      const chunk=items.slice(offset,offset+20);
      let write=0;
      for(let i=0;i<chunk.length;i++){
        const item=chunk[i]||{},text=String(item.text||"");
        if(text.trim().length>0)chunk[write++]={keyPath:String(item.keyPath||""),text};
      }
      chunk.length=write;
      if(!chunk.length)continue;
      if(typeof onProgress==="function")onProgress(map.size,input.length,"translating",{stage:"start",currentBatch:b+1,totalBatches,batchSize:chunk.length});
      let res=null;try{res=await plugin.translateLocal({texts:chunk,sourceLang:sourceLang||"en",targetLang:targetLang||"zh",engine:activeEngine})}catch(e){failedBatches++;window.__slgLocalLastError=e&&e.message||String(e);if(typeof onProgress==="function")onProgress(map.size,input.length,"translating",{stage:"failed",currentBatch:b+1,totalBatches,batchSize:chunk.length,failedBatches});continue}
      const entries=res&&res.translations?Object.entries(res.translations):[];
      for(const[k,v]of entries){if(v&&String(v).trim().length>0)map.set(k,String(v))}
      if(Array.isArray(res&&res.warnings))warnings.push(...res.warnings);
      if(typeof onProgress==="function")onProgress(map.size,input.length,"translating");
      if(typeof onProgress==="function")onProgress(map.size,input.length,"translating",{stage:"completed",completedBatches:b+1,totalBatches,currentBatch:b+1,batchSize:chunk.length,failedBatches,splitBatches});
    }
    return {translations:map,successCount:map.size,warnings};
  }catch(e){
    window.__slgLocalLastError=e&&e.message||String(e);
    throw e;
  }finally{
    await globalThis.__slgReleaseLocalResources?.();
  }
}
window.__slgLocalTranslateImpl=localTranslate;
function formatLocalBytes(bytes){const value=Number(bytes)||0;if(value<1024)return value+" B";const units=["KB","MB","GB"];let n=value/1024,unit=0;while(n>=1024&&unit<units.length-1){n/=1024;unit+=1}return `${n>=100?Math.round(n):Math.round(n*10)/10} ${units[unit]}`}
function variantLabel(v){return v==="0.5b"?"Qwen2.5 0.5B":"Qwen2.5 1.5B"}
function variantSize(v){return v==="0.5b"?"约 470MB":"约 1.1GB"}
function buildVariantSelect(){
  const field=textNode("label","workshop-settings-field");
  field.append(textNode("span","","模型规格"));
  const select=document.createElement("select");
  select.id="settingsLocalLlmVariant";select.className="workshop-settings-input";
  for(const [value,label] of [["0.5b","Qwen2.5 0.5B（约 470MB，更快）"],["1.5b","Qwen2.5 1.5B（约 1.1GB，更准）"]]){
    const option=document.createElement("option");option.value=value;option.textContent=label;select.append(option);
  }
  select.value="1.5b";field.append(select);return {field,select};
}
function buildLocalEngineSection(){
  const wrap=textNode("div","workshop-settings-conditional");
  wrap.hidden=true;
  const mlCard=textNode("section","workshop-settings-card");
  mlCard.append(textNode("h2","workshop-settings-title","轻量翻译（ML Kit）"));
  const mlStatus=textNode("p","workshop-settings-status","正在检测模型状态…");
  const mlBtn=textNode("button","workshop-settings-save","下载模型（约 30-60MB）");
  mlBtn.type="button";
  const mlNote=textNode("p","workshop-settings-helper","免费离线翻译，首次使用需联网下载一次，之后完全离线。仅支持英文↔中文（简体）；繁体请用高质量本地模型。");
  mlCard.append(mlStatus,mlBtn,mlNote);
  const llCard=textNode("section","workshop-settings-card");
  llCard.append(textNode("h2","workshop-settings-title","高质量翻译（本地大模型）"));
  const llStatus=textNode("p","workshop-settings-status","正在检测模型状态…");
  const llBtn=textNode("button","workshop-settings-save","下载模型（约 1.1GB）");
  llBtn.type="button";
  const llNote=textNode("p","workshop-settings-helper","基于 Qwen2.5 本地大模型，质量接近云端，适合视觉小说对话。中低端手机每条约 3-8 秒。");
  let variantTouched=false;
  let llState={installed:false,variant:"1.5b"};
  const llVariant=buildVariantSelect();
  llVariant.select.onchange=()=>{variantTouched=true;const selected=llVariant.select.value||"1.5b";if(llState.installed&&llState.variant===selected){llBtn.textContent="删除模型";llBtn.disabled=false}else if(llState.installed){llBtn.textContent=`切换为${variantLabel(selected)}（${variantSize(selected)}）`;llBtn.disabled=false}else{llBtn.textContent=`下载模型${variantLabel(selected)}（${variantSize(selected)}）`;llBtn.disabled=false}};
  llCard.append(llStatus,llVariant.field,llBtn,llNote);
  let polling=null;
  const stopPoll=()=>{if(polling){clearInterval(polling);polling=null}};
  const render=async()=>{
    const plugin=window.Capacitor?.Plugins?.FileManager;
    if(!plugin||typeof plugin.localStatus!=="function"){mlStatus.textContent="当前版本不支持本地翻译，请升级应用";llStatus.textContent="当前版本不支持本地翻译，请升级应用";return}
    try{
      const s=await plugin.localStatus();
      const mk=s&&s.mlkit||{};const ll=s&&s.llm||{};
      llState.installed=!!ll.installed;llState.variant=ll.variant||"1.5b";
      if(!ll.downloading&&!variantTouched){try{llVariant.select.value=ll.variant||"1.5b"}catch(_e){}}
      llVariant.select.disabled=!!(ll.downloading||ll.loading);
      if(mk.downloading){mlStatus.textContent=`下载中… 已下载 ${formatLocalBytes(mk.downloadedBytes)}`;mlBtn.disabled=true;mlBtn.textContent="下载中…"}
      else if(mk.downloaded){mlStatus.textContent="模型已下载，可离线使用";mlBtn.textContent="删除模型";mlBtn.disabled=false}
      else{mlStatus.textContent="模型未下载";mlBtn.textContent="下载模型（约 30-60MB）";mlBtn.disabled=false}
      if(ll.downloading){const pct=ll.totalBytes>0?Math.floor((ll.downloadedBytes||0)*100/ll.totalBytes):-1;llStatus.textContent=`下载中… ${formatLocalBytes(ll.downloadedBytes||0)} / ${formatLocalBytes(ll.totalBytes)}${pct>=0?`（${pct}%）`:``}`;llBtn.disabled=true;llBtn.textContent="下载中…"}
      else if(ll.loading){llStatus.textContent="模型加载中…";llBtn.disabled=true}
      else if(ll.installed){llStatus.textContent=`已安装（${formatLocalBytes(ll.sizeBytes)}）`;llBtn.textContent="删除模型";llBtn.disabled=false}
      else{llStatus.textContent="模型未安装";llBtn.textContent="下载模型（约 1.1GB）";llBtn.disabled=false}
      if(!ll.downloading&&!ll.loading){const activeVariant=ll.variant||"1.5b";const selectedVariant=llVariant.select.value||"1.5b";if(ll.installed&&activeVariant===selectedVariant){llBtn.textContent="删除模型";llBtn.disabled=false}else if(ll.installed){llBtn.textContent=`切换为${variantLabel(selectedVariant)}（${variantSize(selectedVariant)}）`;llBtn.disabled=false}else{llBtn.textContent=`下载模型${variantLabel(selectedVariant)}（${variantSize(selectedVariant)}）`;llBtn.disabled=false}}
    }catch(e){mlStatus.textContent="状态查询失败";llStatus.textContent="状态查询失败"}
  };
  mlBtn.onclick=async()=>{
    const plugin=window.Capacitor?.Plugins?.FileManager;
    if(!plugin||typeof plugin.localDownload!=="function")return;
    if(mlBtn.textContent.includes("删除")){mlBtn.disabled=true;try{await plugin.mlkitDelete();mlStatus.textContent="已删除"}catch(e){mlStatus.textContent="删除失败："+(e&&e.message||e)}finally{mlBtn.disabled=false;render();return}}
    mlBtn.disabled=true;mlBtn.textContent="下载中…";mlStatus.textContent="正在下载…";
    stopPoll();polling=setInterval(()=>render(),1500);
    try{const r=await plugin.localDownload({sourceLang:"en",targetLang:"zh"});mlStatus.textContent="模型已下载，可离线使用"}catch(e){mlStatus.textContent="下载失败："+(e&&e.message||e)}finally{stopPoll();mlBtn.disabled=false;render()}
  };
  llBtn.onclick=async()=>{
    const plugin=window.Capacitor?.Plugins?.FileManager;
    if(!plugin||typeof plugin.llmDownload!=="function")return;
    if(llBtn.textContent.includes("删除")){llBtn.disabled=true;try{await plugin.llmDelete();llStatus.textContent="已删除"}catch(e){llStatus.textContent="删除失败："+(e&&e.message||e)}finally{llBtn.disabled=false;render();return}}
    llBtn.disabled=true;llBtn.textContent="下载中…";llStatus.textContent="正在下载（"+variantSize(llVariant.select.value||"1.5b")+"，请保持网络连接）…";
    stopPoll();polling=setInterval(()=>render(),1500);
    try{const r=await plugin.llmDownload({variant:llVariant.select.value||"1.5b"});llStatus.textContent="模型已安装"}catch(e){llStatus.textContent="下载失败："+(e&&e.message||e)}finally{stopPoll();llBtn.disabled=false;render()}
  };
  wrap.refreshLocal=async()=>{await render()};
  wrap.append(mlCard,llCard);
  return wrap;
}
"""


def enhance_local_runtime(runtime: str) -> str:
    """Extend the workshop runtime string with the local engine settings UI."""
    # 1) Add the local provider to the settings provider map.
    providers_old = '  custom:{label:"自定义接口",models:[]}\n};\n'
    providers_new = (
        '  custom:{label:"自定义接口",models:[]},\n'
        '  local:{label:"本机离线翻译",models:[\n'
        '    ["mlkit","轻量翻译（免费·离线）"],\n'
        '    ["qwen","高质量翻译（本地模型）"]\n'
        "  ]}\n};\n"
    )
    if runtime.count(providers_old) != 1:
        raise ValueError("Local engine providers signature not found")
    runtime = runtime.replace(providers_old, providers_new, 1)

    # 2) Insert the helper functions before the settings field builders.
    anchor = "function fieldShell(id,label){"
    if runtime.count(anchor) != 1:
        raise ValueError("Local engine helpers signature not found")
    runtime = runtime.replace(anchor, _LOCAL_HELPERS + "\n" + anchor, 1)

    # 3) Create the local engine section in the service view.
    provider_select_old = ('const provider=selectControl("settingsProvider","供应商",'
        '[["openai","OpenAI"],["deepseek","DeepSeek"],["custom","自定义接口"]],prefs.providerId);')
    provider_select_new = ('const provider=selectControl("settingsProvider","供应商",'
        '[["openai","OpenAI"],["deepseek","DeepSeek"],["custom","自定义接口"],["local","本机离线翻译"]],prefs.providerId);')
    if runtime.count(provider_select_old) != 1:
        raise ValueError("Local engine provider select signature not found")
    runtime = runtime.replace(provider_select_old, provider_select_new, 1)

    # 3) Create the local engine section in the service view.
    wrap_old = "customWrap.append(customBaseURL.field,customModel.field);"
    wrap_new = "customWrap.append(customBaseURL.field,customModel.field);const localWrap=buildLocalEngineSection();"
    if runtime.count(wrap_old) != 1:
        raise ValueError("Local engine wrap signature not found")
    runtime = runtime.replace(wrap_old, wrap_new, 1)

    show_old = 'customWrap.hidden=prefs.providerId!=="custom";'
    show_new = (
        'customWrap.hidden=prefs.providerId!=="custom";'
        'localWrap.hidden=prefs.providerId!=="local";'
        'api.field.hidden=prefs.providerId==="local";'
    )
    if runtime.count(show_old) != 1:
        raise ValueError("Local engine visibility signature not found")
    runtime = runtime.replace(show_old, show_new, 1)

    update_old = (
        "const updateProvider=()=>{const providerId=provider.select.value;"
        'replaceSelectOptions(model.select,PROVIDERS[providerId].models,providerId===prefs.providerId?prefs.model:"");'
        'customWrap.hidden=providerId!=="custom";error.hidden=true};'
    )
    update_new = (
        "const updateProvider=()=>{const providerId=provider.select.value;"
        'replaceSelectOptions(model.select,PROVIDERS[providerId].models,providerId===prefs.providerId?prefs.model:"");'
        'customWrap.hidden=providerId!=="custom";localWrap.hidden=providerId!=="local";'
        'api.field.hidden=providerId==="local";error.hidden=true;'
        'installLocalHooks({providerId:providerId,model:model.select.value});'
        'if(providerId==="local")setTimeout(()=>{localWrap.refreshLocal?.()},0)};'
    )
    if runtime.count(update_old) != 1:
        raise ValueError("Local engine updateProvider signature not found")
    runtime = runtime.replace(update_old, update_new, 1)

    save_old = "saveSettingsPrefs(next);applySettingsToReact(next);helper.textContent="
    save_new = (
        "saveSettingsPrefs(next);installLocalHooks(next);applySettingsToReact(next);"
        'if(next.providerId==="local")setTimeout(()=>{localWrap.refreshLocal?.()},0);helper.textContent='
    )
    if runtime.count(save_old) != 1:
        raise ValueError("Local engine save signature not found")
    runtime = runtime.replace(save_old, save_new, 1)

    card_old = "card.append(title,provider.field,model.field,customWrap,api.field,error,save,helper);"
    card_new = "card.append(title,provider.field,model.field,customWrap,localWrap,api.field,error,save,helper);"
    if runtime.count(card_old) != 1:
        raise ValueError("Local engine card signature not found")
    runtime = runtime.replace(card_old, card_new, 1)

    # 4) Install hooks on startup so a saved local-provider preference routes
    #    translation to the native kernel even before the settings are opened.
    # 3b) Let the workshop overlay click the React start button even when it is
    #     disabled by the missing-apiKey gate; the local engine does not need
    #     an API key.
    trigger_old = ('if(isStart&&target?.disabled){const snap=readTaskSnapshot();'
        'setWorkshopState("ready",{...snap,apiRequired:true});return}')
    trigger_new = ('if(isStart&&target?.disabled){if(window.__slgLocalSelected){'
        'try{target.disabled=false}catch(_e){}}else{const snap=readTaskSnapshot();'
        'setWorkshopState("ready",{...snap,apiRequired:true});return}}')
    if runtime.count(trigger_old) != 1:
        raise ValueError("Local engine trigger signature not found")
    runtime = runtime.replace(trigger_old, trigger_new, 1)

    mount_old = "if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;restoreSession();"
    mount_new = (
        "if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;"
        "restoreSession();installLocalHooks(readSettingsPrefs());"
    )
    if runtime.count(mount_old) != 1:
        raise ValueError("Local engine mount signature not found")
    runtime = runtime.replace(mount_old, mount_new, 1)

    # Refresh status whenever the service view is opened (saved local provider).
    service_click_old = "service.onclick=()=>showView(serviceView);"
    service_click_new = ("service.onclick=()=>{showView(serviceView);"
        "setTimeout(()=>{localWrap.refreshLocal?.()},0)};")
    if runtime.count(service_click_old) != 1:
        raise ValueError("Local engine service click signature not found")
    runtime = runtime.replace(service_click_old, service_click_new, 1)
    return runtime
