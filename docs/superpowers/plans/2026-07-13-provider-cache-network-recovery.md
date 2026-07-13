# Provider, Cache, and Network Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add complete provider configuration to “我的”, restore the existing cross-model translation cache, and stop unreachable API requests from holding the first translation batch indefinitely.

**Architecture:** Continue using `patch_workshop_ui.py` as the single build-time patch boundary. The visible settings shell discovers and updates the existing React controls through DOM events; two focused patch functions rewrite the minified translation-cache and network-failure blocks before the shell runtime is appended. Contract tests verify every patch signature, while the installed WebView and native cache plugin provide end-to-end evidence.

**Tech Stack:** Python 3 `unittest`, JavaScript injected into an Android Capacitor/React WebView, Capacitor `FileManager`, Android Debug Bridge, zipalign, APK Signature Scheme v2/v3.

## Global Constraints

- Keep OpenAI, DeepSeek, and an OpenAI-compatible custom provider.
- Persist provider, model, custom Base URL, and custom model locally; do not add API Key to the new settings JSON.
- Preserve source language, target language, and glossary isolation while removing provider/model isolation from text-cache lookup.
- Do not delete, overwrite, or bulk-retranslate the existing 13,058 cache records.
- Network failures must not enter recursive batch splitting; content/JSON failures may still split.
- Keep all existing file selection, API Key, translation, patch generation, scan optimization, and live-log bridges working.
- Keep Android touch targets at least 48 dp and retain the existing light/dark/reduced-motion tokens.
- Do not print API Keys or complete cached source/translation strings in tests or diagnostics.

---

## File Map

- `apk-work/ui-redesign/patch_workshop_ui.py`: owns settings-shell markup/CSS/runtime and deterministic build-time rewrites of cache and network behavior.
- `apk-work/ui-redesign/test_workshop_patch.py`: owns source-to-generated-JavaScript contract tests for settings, cache compatibility, and network failure behavior.
- `apk-work/ui-redesign/test_built_apk.py`: verifies the signed artifact actually contains the new runtime contracts.
- `apk-work/ui-redesign/build_workshop_apk.py`: existing build/sign entry point; no behavior change expected.
- `apk-work/slg-workshop-ui-signed.apk`: rebuilt installable artifact; do not commit it.

---

### Task 1: Provider settings in “我的”

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:14-113`

**Interfaces:**
- Consumes: the existing hidden React provider/model `<select>` elements, custom Base URL input, and API Key input.
- Produces: `readSettingsPrefs() -> SettingsPrefs`, `saveSettingsPrefs(prefs)`, `findReactConfigControls()`, `applySettingsToReact(prefs)`, and a visible Material-style settings form.

- [ ] **Step 1: Add a failing provider-settings contract test**

Add this test to `WorkshopPatchContractTest`:

```python
def test_settings_support_provider_model_and_custom_endpoint(self):
    module = self.load_patch()
    js, css = module.patch_assets(
        BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
    )

    for token in (
        'const SETTINGS_KEY="slg-workshop-settings-v1"',
        'function readSettingsPrefs()',
        'function saveSettingsPrefs(prefs)',
        'function findReactConfigControls()',
        'function setReactSelectValue(select,value)',
        'function applySettingsToReact(prefs)',
        'localStorage.setItem(SETTINGS_KEY,JSON.stringify(prefs))',
        'provider.id="settingsProvider"',
        'model.id="settingsModel"',
        'customBaseURL.id="settingsCustomBaseURL"',
        'customModel.id="settingsCustomModel"',
        'input.id="settingsApiKey"',
        'option.value="deepseek"',
        'option.value="custom"',
        'https://your-api.com/v1',
        '已保存：',
    ):
        self.assertIn(token, js)
    self.assertIn('min-height:48px', ''.join(css.split()))
    self.assertIn('.workshop-settings-error', css)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v
```

Expected: `FAIL` because `SETTINGS_KEY`, provider/model controls, and persistence functions are absent.

- [ ] **Step 3: Add settings styles**

Append these rules inside `WORKSHOP_CSS` next to the existing settings rules:

```css
.workshop-settings-title{margin:0 0 16px;font-size:18px;line-height:1.3;font-weight:750}
.workshop-settings-field{display:block;margin-top:14px}
.workshop-settings-field:first-of-type{margin-top:0}
.workshop-settings-field>span{display:block;margin-bottom:7px;font-size:14px;font-weight:700}
.workshop-settings-conditional[hidden]{display:none!important}
.workshop-settings-error{margin:6px 0 0;color:var(--workshop-error);font-size:13px;line-height:1.4}
.workshop-settings-status{margin:10px 0 0;color:var(--workshop-muted);font-size:13px;line-height:1.45}
```

Reuse `.workshop-settings-input` for `<select>` and `<input>` so all controls retain a minimum 52 px height, visible focus treatment, existing color tokens, and dark-theme support.

- [ ] **Step 4: Add non-sensitive settings state and DOM bridge helpers**

Extend the runtime declaration with `settingsRestored=false` and add the following helpers before `openSettings()`:

```javascript
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
```

- [ ] **Step 5: Replace the API-Key-only settings card with the complete form**

Refactor `openSettings()` so the card creates:

```javascript
const prefs=readSettingsPrefs();
const title=textNode("h2","workshop-settings-title","翻译服务");
const provider=selectControl("settingsProvider","供应商",[
  ["openai","OpenAI"],["deepseek","DeepSeek"],["custom","自定义接口"]
],prefs.providerId);
const model=selectControl("settingsModel","模型",PROVIDERS[prefs.providerId].models,prefs.model);
const customWrap=textNode("div","workshop-settings-conditional");
const customBaseURL=inputControl("settingsCustomBaseURL","自定义 Base URL","url",prefs.customBaseURL,"https://your-api.com/v1");
const customModel=inputControl("settingsCustomModel","自定义模型名","text",prefs.customModel,"例如：qwen-plus");
customWrap.append(customBaseURL.field,customModel.field);
const api=inputControl("settingsApiKey","API Key","password",reactApiInput?.value??pendingApiKey??"","");
```

Use these complete construction helpers:

```javascript
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
```

On provider change, refresh the model list and toggle `customWrap.hidden`. On save, validate custom Base URL/model, then run:

```javascript
const next={
  providerId:provider.select.value,
  model:model.select.value,
  customBaseURL:customBaseURL.input.value.trim(),
  customModel:customModel.input.value.trim()
};
if(next.providerId==="custom"&&(!next.customBaseURL||!next.customModel)){
  error.textContent="请填写自定义 Base URL 和模型名";error.hidden=false;return;
}
pendingApiKey=api.input.value;
saveSettingsPrefs(next);
applySettingsToReact(next);
helper.textContent=`已保存：${PROVIDERS[next.providerId].label} · ${next.providerId==="custom"?next.customModel:next.model}`;
```

In `mount()`, after `decorate()`, restore persisted settings once:

```javascript
if(!settingsRestored&&applySettingsToReact(readSettingsPrefs()))settingsRestored=true;
```

- [ ] **Step 6: Run focused and full tests and verify GREEN**

Run:

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
```

Expected: provider-settings test passes; the current nine-test suite remains green.

- [ ] **Step 7: Commit the settings bridge**

```powershell
git add -- apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "feat: add provider settings"
```

---

### Task 2: Cross-model legacy-cache recovery

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:114-170`

**Interfaces:**
- Consumes: minified functions `Co`, `To`, and `Eo`, plus the existing cache object `vo` loaded by `FileManager.loadTranslationCache()`.
- Produces: `patch_translation_cache(js: str) -> str`; generated helpers `cacheIdentity(scope,text)`, `cacheV2Key(scope,text)`, and `rebuildCacheIndex()`.

- [ ] **Step 1: Add a failing cache-migration contract test**

```python
def test_translation_cache_is_reused_across_models(self):
    module = self.load_patch()
    js, _ = module.patch_assets(
        BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
    )
    for token in (
        'function cacheIdentity(e,t)',
        'function cacheV2Key(e,t)',
        'function rebuildCacheIndex()',
        'slg-translator-cache:v2|',
        'updatedAt||0',
        'rebuildCacheIndex(),yo=!0',
        'vo[cacheV2Key(e,t)]',
    ):
        self.assertIn(token, js)
    self.assertIn('function patch_translation_cache(js: str) -> str:',
                  Path(module.__file__).read_text("utf-8"))
```

- [ ] **Step 2: Run the cache test and verify RED**

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v
```

Expected: `FAIL` because cache lookup still includes the selected model.

- [ ] **Step 3: Implement a deterministic cache rewrite**

Add `patch_translation_cache(js: str)` before `patch_assets()` and require each source signature exactly once:

```python
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
    new_cache = r'''function cacheIdentity(e,t){let[n,r,,i]=e.split(`|`);return`${n}|${r}|${i}|${U(t)}`}
function cacheV2Key(e,t){return _o+`v2|`+cacheIdentity(e,t)}
function rebuildCacheIndex(){cacheIndex={};for(const[e,t]of Object.entries(vo)){let n=null;if(e.startsWith(_o+`v2|`))n=e.slice((_o+`v2|`).length);else{const r=e.match(/^slg-translator-cache:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)$/);r&&(n=`${r[1]}|${r[2]}|${r[4]}|${r[5]}`)}if(!n||!t?.sourceText||!t?.translatedText)continue;const r=cacheIndex[n];(!r||(t.updatedAt||0)>(r.updatedAt||0))&&(cacheIndex[n]=t)}}
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
        'function Eo(e,t,n){let r={sourceText:t,translatedText:n,updatedAt:Date.now()},'
        'i=cacheV2Key(e,t);vo[i]=r,cacheIndex[cacheIdentity(e,t)]=r,bo=!0}'
    )
    if js.count(old_lookup) != 1:
        raise ValueError("Translation cache lookup signature not found")
    return js.replace(old_lookup, new_lookup, 1)
```

Update `patch_assets()` to call `patch_translation_cache(patch_scan_flow(js))` before appending `WORKSHOP_RUNTIME`.

- [ ] **Step 4: Run focused and full tests and verify GREEN**

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
```

Expected: cache migration test passes; no existing contract fails.

- [ ] **Step 5: Commit cache recovery**

```powershell
git add -- apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "fix: reuse translation cache across models"
```

---

### Task 3: Fail fast on unreachable provider networks

**Files:**
- Modify: `apk-work/ui-redesign/test_workshop_patch.py`
- Modify: `apk-work/ui-redesign/patch_workshop_ui.py:114-210`

**Interfaces:**
- Consumes: minified `Lo()` batch coordinator and recursive `Bo()` content-recovery function.
- Produces: `patch_translation_network(js: str) -> str`, generated `isNetworkFailure(error)`, `providerLabel(baseURL)`, and a bounded network-error path.

- [ ] **Step 1: Add a failing network-recovery contract test**

```python
def test_network_failures_stop_batches_without_recursive_splitting(self):
    module = self.load_patch()
    js, _ = module.patch_assets(
        BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
    )
    for token in (
        'function isNetworkFailure(e)',
        'function providerLabel(e)',
        'maxRetries:1',
        'if(isNetworkFailure(e))throw e',
        'b=y.length',
        '无法连接 ${providerLabel(i)}',
        '前往“我的”切换供应商',
    ):
        self.assertIn(token, js)
    self.assertNotIn('maxRetries:2', js)
    self.assertIn('let c=Math.ceil(n.length/2)', js)
```

- [ ] **Step 2: Run the network test and verify RED**

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v
```

Expected: `FAIL` because the SDK still retries twice and every error enters recursive split.

- [ ] **Step 3: Implement bounded retry and error classification**

Add this build-time rewrite:

```python
def patch_translation_network(js: str) -> str:
    helpers_anchor = 'async function Lo(e){'
    helpers = r'''function isNetworkFailure(e){const t=String(e?.message||e||``);return/ERR_|network|fetch failed|failed to fetch|timed?\s*out|timeout|dns|offline|connection|ENOTFOUND|ECONNREFUSED/i.test(t)}
function providerLabel(e){return/deepseek/i.test(e)?`DeepSeek`:/openai/i.test(e)?`OpenAI`:`自定义接口`}
async function Lo(e){'''
    if js.count(helpers_anchor) != 1:
        raise ValueError("Translation coordinator signature not found")
    js = js.replace(helpers_anchor, helpers, 1)

    if js.count('timeout:3e4,maxRetries:2') != 1:
        raise ValueError("OpenAI retry signature not found")
    js = js.replace('timeout:3e4,maxRetries:2', 'timeout:3e4,maxRetries:1', 1)

    old_worker_catch = 'catch{v=!0,ee+=1}await wo(),x+=1'
    new_worker_catch = (
        'catch(e){v=!0,ee+=1,isNetworkFailure(e)&&(N=`无法连接 ${providerLabel(i)}。'
        '请检查网络，或前往“我的”切换供应商。`,b=y.length)}await wo(),x+=1'
    )
    state_anchor = 'let _=new H({apiKey:a,baseURL:i,dangerouslyAllowBrowser:!0,timeout:3e4,maxRetries:1}),v=!1,y='
    state_replacement = 'let _=new H({apiKey:a,baseURL:i,dangerouslyAllowBrowser:!0,timeout:3e4,maxRetries:1}),v=!1,N="",y='
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
    return js.replace(old_split, new_split, 1)
```

Call `patch_translation_network()` after `patch_translation_cache()` in `patch_assets()`. The exact ordering is:

```python
patched = patch_scan_flow(js)
patched = patch_translation_cache(patched)
patched = patch_translation_network(patched)
return patched + copy_contract + enhance_runtime(WORKSHOP_RUNTIME), css + "\n" + WORKSHOP_CSS
```

- [ ] **Step 4: Run focused and full tests and verify GREEN**

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
```

Expected: network test passes and recursive content splitting remains present.

- [ ] **Step 5: Commit network recovery**

```powershell
git add -- apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "fix: stop retry storms on network failure"
```

---

### Task 4: Signed artifact and real-device acceptance

**Files:**
- Modify: `apk-work/ui-redesign/test_built_apk.py`
- Generated, not committed: `apk-work/slg-workshop-ui-signed.apk`
- Generated, not committed: `apk-work/ui-redesign/qa/provider-settings.png`
- Generated, not committed: `apk-work/ui-redesign/qa/cache-recovery.png`

**Interfaces:**
- Consumes: all generated JS/CSS contracts from Tasks 1–3 and the phone’s existing `FileManager` cache.
- Produces: a v2/v3-signed APK installed with data preservation plus runtime evidence for settings persistence, cache count, and bounded network failure.

- [ ] **Step 1: Extend the signed-APK contract test**

Add these assertions inside `test_signed_apk_contains_workshop_assets`:

```python
for token in (
    'slg-workshop-settings-v1',
    'settingsProvider',
    'settingsCustomBaseURL',
    'slg-translator-cache:v2|',
    'function isNetworkFailure(e)',
    'maxRetries:1',
):
    self.assertIn(token, js)
```

- [ ] **Step 2: Run the artifact test before rebuilding and verify RED**

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_built_apk.py" -v
```

Expected: `FAIL` because the previously signed APK lacks the new settings/cache/network tokens.

- [ ] **Step 3: Record pre-install cache metadata without exposing contents**

With the current app still installed, forward the WebView debugger and evaluate only the JSON byte length and key count:

```javascript
const result=await Capacitor.Plugins.FileManager.loadTranslationCache();
const parsed=JSON.parse(result.data||"{}");
({bytes:(result.data||"").length,entries:Object.keys(parsed).length});
```

Expected baseline: approximately `6,332,569` bytes and exactly `13,058` entries. Save only these two numbers in the QA notes; never output values from the records.

- [ ] **Step 4: Run all tests and build the signed APK**

```powershell
python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v
python apk-work/ui-redesign/build_workshop_apk.py
```

Expected: all tests pass after the build; `apk-work/slg-workshop-ui-signed.apk` is produced.

- [ ] **Step 5: Verify alignment and signatures**

```powershell
& '.tools/android-15/zipalign.exe' -c 4 'apk-work/slg-workshop-ui-signed.apk'
& '.tools/android-15/apksigner.bat' verify --verbose 'apk-work/slg-workshop-ui-signed.apk'
```

Expected: zip alignment succeeds; APK verifies with v2 and v3 schemes.

- [ ] **Step 6: Install without clearing app data**

```powershell
$adb='.tools/platform-tools/adb.exe'
& $adb install -r 'apk-work/slg-workshop-ui-signed.apk'
& $adb logcat -c
& $adb shell am force-stop com.slgtranslator.app
& $adb shell monkey -p com.slgtranslator.app 1
```

Expected: `Success`. Do not run `pm clear` or uninstall the package.

- [ ] **Step 7: Verify provider UI and persistence**

Use the installed WebView to open “我的”, then verify:

```javascript
({
  providers:[...document.querySelector('#settingsProvider').options].map(o=>o.value),
  model:document.querySelector('#settingsModel').value,
  customHidden:document.querySelector('.workshop-settings-conditional').hidden,
  touchHeight:document.querySelector('#settingsProvider').getBoundingClientRect().height
})
```

Expected: providers are `openai`, `deepseek`, `custom`; height is at least 48 CSS px. Select DeepSeek and `deepseek-v4-flash`, save, force-stop/relaunch, and confirm both the visible fields and hidden React fields still equal those values.

- [ ] **Step 8: Verify old-cache recovery and preservation**

Select the same APK and start translation with DeepSeek. Inspect only log counts and cache metadata.

Expected:

- the initial log reports a cache hit greater than zero instead of `缓存 0 条`;
- the 146-entry RPYC file completes without requesting already cached lines;
- post-install `FileManager.loadTranslationCache()` returns at least 13,058 entries;
- old `deepseek-v4-flash` keys remain present while newly saved translations use the `v2` prefix.

- [ ] **Step 9: Verify fail-fast behavior with a safe unreachable custom endpoint**

Save a temporary custom provider with Base URL `http://127.0.0.1:9/v1`, model `qa-unreachable`, and a dummy non-secret key. Start a translation containing one uncached QA string and measure from request start to task failure.

Expected:

- no recursive split logs appear for the network error;
- at most two request attempts occur;
- the task exits within 70 seconds with “无法连接 自定义接口…前往‘我的’切换供应商”;
- the start action becomes available again.

Restore DeepSeek and `deepseek-v4-flash` after this check.

- [ ] **Step 10: Capture screenshots and run final diagnostics**

```powershell
New-Item -ItemType Directory -Force 'apk-work/ui-redesign/qa' | Out-Null
cmd /c ".tools\platform-tools\adb.exe exec-out screencap -p > apk-work\ui-redesign\qa\provider-settings.png"
git diff --check
$errors=& '.tools/platform-tools/adb.exe' logcat -d | Select-String -Pattern 'ReferenceError|Uncaught'
if ($errors) { $errors; exit 1 }
```

Expected: settings screenshot is readable at 720×1600, `git diff --check` passes, and no JavaScript reference error appears.

- [ ] **Step 11: Commit the artifact contract and final source state**

```powershell
git add -- apk-work/ui-redesign/test_built_apk.py apk-work/ui-redesign/patch_workshop_ui.py apk-work/ui-redesign/test_workshop_patch.py
git commit -m "test: verify provider cache recovery artifact"
```

Do not stage APKs, `.tools`, extracted files, generated assets, QA screenshots, or unrelated existing untracked files.

---

## Completion Evidence

The implementation is complete only when all of the following are recorded in the handoff:

- full unit-test count and passing result;
- zipalign result and v2/v3 signature result;
- `adb install -r` success;
- provider/model persistence after force-stop and relaunch;
- cache entry count before and after installation, with the post-install count not below 13,058;
- real log evidence showing a non-zero old-cache hit;
- bounded failure duration and request-attempt count for the unreachable custom endpoint;
- absence of `ReferenceError` and `Uncaught` in the fresh app log;
- final commit hashes and signed APK path.
