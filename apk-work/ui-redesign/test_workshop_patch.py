import importlib.util
import subprocess
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
            "workshop-state-translating",
            "workshop-state-patching",
            "workshop-state-completed",
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
        self.assertIn('runtimeRoot?.setAttribute("data-workshop-task",task)', js)
        self.assertIn('runtimeRoot=app', js)
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
        self.assertIn('workshop-task-shell[data-workshop-state="translating"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="patching"]', css)
        self.assertIn('workshop-task-shell[data-workshop-state="completed"]', css)
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
        self.assertIn('actionButton("选择 APK 文件",()=>triggerReactButton(sourceButton))', js)
        self.assertIn('actionButton("开始翻译",()=>triggerReactButton(startButton))', js)
        # The guard must inspect the freshly queried React node, not a stale
        # reference captured before React rerenders the form.
        self.assertIn('target?.disabled', js)
        self.assertIn('请先配置 API Key', js)
        self.assertIn('const snap=readTaskSnapshot()', js)
        self.assertIn('setWorkshopState("ready",{...snap,apiRequired:true})', js)
        self.assertIn('正在处理脚本', js)
        for token in (
            "workshop-settings-shell",
            "workshop-settings-input",
            "workshop-settings-save",
            "API Key",
            "我的设置",
            "openSettings",
            "setReactInputValue",
            "我的",
            'input.id="settingsApiKey"',
            'label.htmlFor="settingsApiKey"',
            'input.focus()',
            'input.blur()',
            'pendingApiKey=null',
            'function applyApiKeyToReact()',
            'pendingApiKey=input.value',
            'applyApiKeyToReact()',
            '!el.closest(".workshop-settings-shell")',
            'function closeSettings(){settingsOpen=false;manualIdle=false',
            'state==="scanning"?"读取中":state==="ready"?"已就绪":state==="translating"?"翻译中":state==="patching"?"生成中":state==="completed"?"已完成":state==="failed"?"失败":""',
            'const target=button===startButton?(findButton("开始翻译")||button):button',
            'const isStart=button===startButton||button?.textContent?.includes("开始翻译")',
            'if(isStart&&target?.disabled)',
        ):
            self.assertIn(token, js)
        self.assertIn("workshop-settings-card", css)
        self.assertIn("workshop-settings-input", css)
        self.assertIn('function retryTask(payload)', js)
        self.assertIn('triggerReactButton(startButton||sourceButton)', js)
        self.assertIn('window.setTimeout(()=>{retrying=false;refresh()},600)', js)
        for token in (
            "t.packageName",
            "scanDurationMs",
            "cacheHit",
            "workshop-scan-elapsed",
            'reason:"scan"',
            'function startScanClock()',
            'function stopScanClock()',
        ):
            self.assertIn(token, js)

        # State changes are reflected on both data attributes and state
        # classes, which lets the CSS keep idle navigation and active task
        # content mutually exclusive.
        self.assertIn('shell.dataset.workshopState=state', js)
        self.assertIn('shell.dataset.workshopTask=state==="idle"?"idle":"active"', js)
        self.assertIn('shell.setAttribute("data-workshop-state",state)', js)
        self.assertRegex(
            js,
            r'shell\.setAttribute\("data-workshop-task",(?:shell\.dataset\.workshopTask|task)\)',
        )
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
        self.assertIn('.workshop-runtime[data-workshop-task="idle"] .workshop-bottom-nav{display:grid!important}', css)
        self.assertIn('.workshop-runtime[data-workshop-task="active"] .workshop-bottom-nav{display:none!important}', css)

        # ENOSPC is recoverable: the user sees a concise localized message,
        # while the raw diagnostic remains behind the details disclosure.
        self.assertIn('ENOSPC|No space left', js)
        self.assertIn('return{state:"failed",reason:"space",raw:failed.textContent}', js)
        self.assertIn('手机空间不足', js)
        self.assertIn('释放空间后重试', js)
        self.assertIn('detailToggle(payload.raw||"ENOSPC|No space left")', js)
        self.assertIn('actionButton("释放空间后重试",()=>retryTask({fileName:payload.fileName,raw:""}))', js)

        # Keep React-managed controls mounted and avoid direct click shortcuts;
        # the shell may only dispatch events to those existing nodes.
        for moved_node in ("sourceButton", "startButton"):
            for method in ("append", "appendChild", "prepend", "insertBefore", "replaceChildren"):
                self.assertNotRegex(
                    js,
                    rf'\.\s*{method}\s*\(\s*{moved_node}\b',
                )
        self.assertNotRegex(js, r'\.\s*click\s*\(')

        # A single debounced observer prevents React's intermediate renders
        # from causing duplicate shell mounts or state flicker.
        compact_js = ''.join(js.split())
        self.assertIn('newMutationObserver(schedule)', compact_js)
        self.assertIn('clearTimeout(debounceTimer);debounceTimer=setTimeout(mount,120)', compact_js)
        self.assertIn('observer.observe(document.querySelector("#root")||document.documentElement', compact_js)

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

    def test_translation_cache_is_reused_across_models(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        start = js.index('var _o=`slg-translator-cache:`')
        end = js.index('function Do()', start)
        cache_runtime = js[start:end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
function legacyKey(scope,text){return _o+scope+`|`+U(text)}

const text=`sample source`;
vo={};cacheIndex={};bo=!1;
vo[legacyKey(`en|zh|model-a|glossary-a`,text)]={sourceText:text,translatedText:`old`,updatedAt:10};
vo[legacyKey(`en|zh|model-b|glossary-a`,text)]={sourceText:text,translatedText:`latest`,updatedAt:30};
vo[legacyKey(`en|zh|model-c|glossary-a`,text)]={sourceText:text,updatedAt:40};
rebuildCacheIndex();
check(To(`en|zh|model-new|glossary-a`,text)===`latest`,`model-independent reuse`);
check(To(`fr|zh|model-new|glossary-a`,text)===null,`source isolation`);
check(To(`en|ja|model-new|glossary-a`,text)===null,`target isolation`);
check(To(`en|zh|model-new|glossary-b`,text)===null,`glossary isolation`);

const pipeText=`pipe model source`;
vo={};cacheIndex={};bo=!1;
vo[legacyKey(`en|zh|vendor|model|glossary-one`,pipeText)]={sourceText:pipeText,translatedText:`pipe-one`,updatedAt:10};
vo[legacyKey(`en|zh|vendor|model|glossary-two`,pipeText)]={sourceText:pipeText,translatedText:`pipe-two`,updatedAt:20};
rebuildCacheIndex();
check(cacheIdentity(`en|zh|vendor|model|glossary-one`,pipeText)!==cacheIdentity(`en|zh|vendor|model|glossary-two`,pipeText),`pipe model glossary boundary`);
check(To(`en|zh|replacement-model|glossary-one`,pipeText)===`pipe-one`,`pipe model first glossary`);
check(To(`en|zh|replacement-model|glossary-two`,pipeText)===`pipe-two`,`pipe model second glossary`);

const preserveText=`preserve source`;
const preserveScope=`en|zh|vendor|model|glossary-keep`;
vo={};cacheIndex={};bo=!1;
const preserveKey=cacheV2Key(preserveScope,preserveText);
const existing={sourceText:preserveText,translatedText:`preserved`,updatedAt:5};
vo[preserveKey]=existing;
rebuildCacheIndex();
Eo(preserveScope,preserveText,`replacement`);
check(preserveKey.startsWith(_o+`v2|`),`v2 key prefix`);
check(vo[preserveKey]===existing,`existing v2 object preservation`);
check(To(preserveScope,preserveText)===`preserved`,`existing v2 value preservation`);
check(cacheIndex[cacheIdentity(preserveScope,preserveText)]===existing,`existing v2 index preservation`);
check(To(`en|zh|other-model|glossary-keep`,preserveText)===`preserved`,`preserved v2 cross-model reuse`);
check(bo===!1,`preserved v2 is not marked dirty`);
'''
        result = subprocess.run(
            ["node", "-e", cache_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(
            'def patch_translation_cache(js: str) -> str:',
            Path(module.__file__).read_text("utf-8"),
        )

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
            'P=providerLabel(i)',
            '无法连接 ${P}',
            '前往“我的”切换供应商',
        ):
            self.assertIn(token, js)
        self.assertNotIn('maxRetries:2', js)
        self.assertIn('let c=Math.ceil(n.length/2)', js)

        helpers_start = js.index('function isNetworkFailure(e)')
        coordinator_end = js.index('function Ro(e)', helpers_start)
        split_start = js.index('async function Bo(', coordinator_end)
        split_end = js.index('async function Vo(', split_start)
        coordinator = js[helpers_start:coordinator_end]
        recursive_split = js[split_start:split_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  const sdkError=new Error(`Connection error`);
  sdkError.name=`APIConnectionError`;
  sdkError.cause={code:`ETIMEDOUT`};
  check(isNetworkFailure(new Error(`net::ERR_CONNECTION_TIMED_OUT`)),`browser timeout classification`);
  check(isNetworkFailure(new Error(`net::ERR_CONNECTION_REFUSED`)),`browser refused classification`);
  check(isNetworkFailure(new Error(`net::ERR_INTERNET_DISCONNECTED`)),`browser offline classification`);
  check(isNetworkFailure(new Error(`net::ERR_NAME_NOT_RESOLVED`)),`browser name resolution classification`);
  check(isNetworkFailure(new Error(`DNS_PROBE_FINISHED_NXDOMAIN`)),`browser DNS probe classification`);
  check(isNetworkFailure(new Error(`net::ERR_CONNECTION_RESET`)),`browser reset classification`);
  check(isNetworkFailure(new Error(`net::ERR_TIMED_OUT`)),`browser timed-out classification`);
  check(isNetworkFailure(sdkError),`SDK connection classification`);
  check(isNetworkFailure({cause:{code:`EAI_AGAIN`}}),`nested cause classification`);
  check(isNetworkFailure(new Error(`Failed-to-fetch`)),`failed-to-fetch classification`);
  check(!isNetworkFailure(new Error(`ERR_INVALID_JSON`)),`ERR_INVALID_JSON content classification`);
  check(!isNetworkFailure(new Error(`translation connection count mismatch`)),`arbitrary connection classification`);
  check(!isNetworkFailure(new Error(`network glossary entry is invalid`)),`arbitrary network classification`);
  check(providerLabel(`https://api.deepseek.com/v1`)===`DeepSeek`,`DeepSeek label`);
  check(providerLabel(`https://api.openai.com/v1`)===`OpenAI`,`OpenAI label`);
  check(providerLabel(`https://example.invalid/v1`)===`自定义接口`,`custom label`);

  for(const message of [
    `API returned empty content`,
    `Invalid translation JSON`,
    `Translation count mismatch`,
    `ERR_INVALID_JSON`,
  ]){
    const calls=[];
    globalThis.Vo=async(_client,_model,batch)=>{
      calls.push(batch.length);
      if(batch.length>1)throw new Error(message);
      return new Map([[0,`ok`]]);
    };
    const result=await Bo({},`model`,[{},{},{},{}],`en`,`zh`,void 0,!0);
    check(result.translations.size===4,`${message} remains splittable`);
    check(calls.join(`,`)===`4,2,1,1,2,1,1`,`${message} recursive split shape`);
  }

  let networkCalls=0;
  globalThis.Vo=async()=>{networkCalls+=1;throw sdkError};
  let rejected=false;
  try{await Bo({},`model`,[{},{},{},{}],`en`,`zh`,void 0,!0)}catch(error){rejected=error===sdkError}
  check(rejected,`network error escapes recursive split`);
  check(networkCalls===1,`network request is not recursively retried`);

  globalThis.Co=async()=>{};
  globalThis.No=texts=>texts;
  globalThis.xo=()=>`scope`;
  globalThis.Se=()=>null;
  globalThis.To=(_scope,text)=>text===`cached`?`cached translation`:null;
  globalThis.Wo=(map,item,value)=>map.set(item.id,value);
  globalThis.Eo=()=>{};
  globalThis.wo=async()=>{};
  globalThis.H=class{};
  globalThis.zo=items=>items.map(item=>[item]);
  globalThis.Ro=item=>item;
  globalThis.Ao=2;
  globalThis.jo=1;
  globalThis.Ko=()=>0;
  let resolveInflight;
  const inflight=new Promise(resolve=>{resolveInflight=resolve});
  const started=[];
  globalThis.Vo=async(_client,_model,batch)=>{
    const id=batch[0].id;
    started.push(id);
    if(id===`network`)throw sdkError;
    if(id===`inflight`)return inflight;
    throw new Error(`unexpected batch ${id}`);
  };
  const texts=[
    {id:`cached`,text:`cached`,duplicateKeys:[]},
    {id:`network`,text:`network request`,duplicateKeys:[]},
    {id:`inflight`,text:`inflight request`,duplicateKeys:[]},
    {id:`never`,text:`must not start`,duplicateKeys:[]},
  ];
  let settled=false;
  const task=Lo({texts,sourceLang:`en`,targetLang:`zh`,baseURL:`https://api.deepseek.com/v1`,apiKey:`test-key`,model:`test-model`,batchSize:1}).then(result=>{settled=true;return result});
  await new Promise(resolve=>setTimeout(resolve,0));
  check(started.join(`,`)===`network,inflight`,`workers stop acquiring after fatal network error`);
  check(!settled,`coordinator waits for current in-flight work`);
  resolveInflight(new Map([[0,`translated inflight`]]));
  const result=await task;
  check(started.join(`,`)===`network,inflight`,`no later batch starts after in-flight settles`);
  check(result.successCount===2,`cache and in-flight partial results survive`);
  check(result.error===`无法连接 DeepSeek。请检查网络，或前往“我的”切换供应商。`,`actionable fatal error survives partial results`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", coordinator + recursive_split + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_fatal_network_stops_outer_file_controller(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn('async function runFileTasksUntilFatal(e,t)', js)
        self.assertIn('N=await runFileTasksUntilFatal(ae,async(o,c)=>{', js)
        self.assertIn('...r?{error:N||`部分文件处理失败，请查看日志`}:{}', js)

        start = js.index('async function runFileTasksUntilFatal(e,t)')
        end = js.index('async function Lo(e){', start)
        scheduler = js[start:end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  const fatal=`无法连接 OpenAI。请检查网络，或前往“我的”切换供应商。`;
  const started=[];
  const result=await runFileTasksUntilFatal([`file-1`,`file-2`],async file=>{
    started.push(file);
    return file===`file-1`?fatal:``;
  });
  check(started.join(`,`)===`file-1`,`second file does not start`);
  check(result===fatal,`task-wide fatal result survives`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", scheduler + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_network_failure_preempts_stale_translating_ui(self):
        module = self.load_patch()
        js, _ = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )
        self.assertIn('reason:"network"', js)
        self.assertIn('if(payload.reason==="network")', js)
        self.assertIn('actionButton("前往“我的”切换供应商",openSettings)', js)
        self.assertIn('actionButton("重试翻译",()=>retryTask(', js)

        snapshot_start = js.index('function readTaskSnapshot(){')
        snapshot_end = js.index('function detailToggle(', snapshot_start)
        snapshot_runtime = js[snapshot_start:snapshot_end]
        render_start = js.index('function renderStateBody(')
        render_end = js.index('function setWorkshopState(', render_start)
        render_runtime = js[render_start:render_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
const fatal=`无法连接 DeepSeek。请检查网络，或前往“我的”切换供应商。`;
function sourceText(){return `正在处理脚本 1 / 2\n翻译中\n翻译失败: ${fatal}`}
function readProgressLog(){return{raw:`stale translating log`,latest:`stale translating log`}}
const document={querySelectorAll(){return[]}};
const snapshot=readTaskSnapshot();
check(snapshot.state===`failed`,`network failure beats stale translating state`);
check(snapshot.reason===`network`,`network failure reason`);
check(snapshot.raw===fatal,`actionable failure message preserved`);

function textNode(tag,cls,text){return{tag,cls,text,children:[],append(...children){this.children.push(...children)}}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
let opened=0,retried=0;
function openSettings(){opened+=1}
function retryTask(){retried+=1}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary}}
const body=renderStateBody(`failed`,{reason:`network`,raw:fatal,fileName:`game.apk`});
const buttons=[];
function visit(node){if(!node)return;if(node.tag===`button`)buttons.push(node);for(const child of node.children||[])visit(child)}
visit(body);
const settings=buttons.find(button=>button.label===`前往“我的”切换供应商`);
const retry=buttons.find(button=>button.label===`重试翻译`);
check(settings&&retry,`network failure renders recovery actions`);
settings.handler();retry.handler();
check(opened===1&&retried===1,`recovery actions are wired`);
'''
        result = subprocess.run(
            ["node", "-e", snapshot_runtime + render_runtime + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_long_running_phases_are_not_reported_as_directory_scanning(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        self.assertIn(
            'if(/正在处理脚本|翻译中|开始处理/.test(text))return{state:"translating"',
            js,
        )
        self.assertNotIn(
            'if(/正在处理脚本|翻译中|开始处理/.test(text))return{state:"scanning"',
            js,
        )
        self.assertIn(
            'if(/正在生成 Ren\'Py 补丁 APK/.test(text))return{state:"patching"',
            js,
        )
        self.assertIn(
            'if(/翻译完成/.test(text))return{state:"completed"',
            js,
        )
        self.assertIn('const progress=text.match(/正在处理脚本\\s*(\\d+)\\s*\\/\\s*(\\d+)/)', js)
        self.assertIn('if(state==="translating")', js)
        self.assertIn('正在翻译文本', js)
        self.assertIn('if(state==="patching")', js)
        self.assertIn('正在生成补丁 APK', js)
        self.assertIn('if(state==="completed")', js)
        self.assertIn('补丁 APK 已生成', js)
        self.assertIn('actionButton("安装补丁版"', js)
        self.assertIn('state==="scanning"?startScanClock():stopScanClock()', js)
        self.assertIn('characterData:true', ''.join(js.split()))
        for state in ("translating", "patching", "completed"):
            self.assertIn(f'workshop-state-{state}', js)
            self.assertIn(
                f'workshop-task-shell[data-workshop-state="{state}"]', css
            )

    def test_translation_logs_are_mirrored_into_the_visible_shell(self):
        module = self.load_patch()
        js, css = module.patch_assets(
            BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8")
        )

        self.assertIn('function readProgressLog()', js)
        self.assertIn('querySelectorAll("#root details")', js)
        self.assertIn('querySelector(\'[class*="font-mono"]\')', js)
        self.assertIn('.slice(-40)', js)
        self.assertIn(
            'return{raw:lines.join("\\n"),latest:lines.at(-1)||""}', js
        )
        self.assertGreaterEqual(js.count('raw:log.raw,latest:log.latest'), 3)
        self.assertIn('workshop-live-line', js)
        self.assertIn('workshop-live-line', css)
        self.assertIn('detailsOpen=false', js)
        self.assertIn('detailsOpen=false,scanStartedAt=0,scanTimer=0;', js)
        self.assertIn('body.dataset.open=String(detailsOpen)', js)
        self.assertIn('body.scrollTop=body.scrollHeight', js)
        compact_css = ''.join(css.split())
        self.assertIn('max-height:240px', compact_css)
        self.assertIn('overflow:auto', compact_css)


if __name__ == "__main__":
    unittest.main()
