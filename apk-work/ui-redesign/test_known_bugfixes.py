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


class KnownBugfixContractTest(unittest.TestCase):
    def load_patch(self):
        return load_patch()

    def patch_assets(self):
        module = self.load_patch()
        return module.patch_assets(BASE_JS.read_text("utf-8"), BASE_CSS.read_text("utf-8"))

    def test_active_states_disable_card_entrance_animation(self):
        _, css = self.patch_assets()
        compact = "".join(css.split())
        self.assertIn(
            '.workshop-task-shell[data-workshop-state="translating"] .workshop-task-card{animation:none}',
            css,
        )
        self.assertIn(
            '.workshop-task-shell[data-workshop-state="patching"] .workshop-task-card{animation:none}',
            css,
        )
        self.assertIn("animation:workshopRise", css)

    def test_translation_progress_emits_starting_batch_before_request(self):
        js, _ = self.patch_assets()
        helpers_start = js.index("function isNetworkFailure(e)")
        coordinator_end = js.index("function Ro(e)", helpers_start)
        coordinator = js[helpers_start:coordinator_end]
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
async function main(){
  globalThis.Co=async()=>{};
  globalThis.No=texts=>texts;
  globalThis.xo=()=>`scope`;
  globalThis.Se=()=>null;
  globalThis.To=()=>null;
  globalThis.Wo=(d,e,n)=>{d.set(e.keyPath,n);for(const k of e.duplicateKeys||[])d.set(k,n)};
  globalThis.Eo=()=>{};
  globalThis.wo=async()=>{};
  globalThis.H=class{};
  globalThis.zo=items=>items.map(item=>[item]);
  globalThis.Ro=item=>item;
  globalThis.Ao=4;
  globalThis.jo=1;
  globalThis.Ko=()=>0;
  globalThis.Vo=async(_client,_model,batch)=>new Map(batch.map((_,i)=>[i,`ok`]));
  globalThis.Bo=async(_client,_model,batch)=>({translations:new Map(batch.map((_,i)=>[i,`ok`])),splitCount:0,failedCount:0});
  const progress=[];
  const result=await Lo({texts:[{keyPath:`a`,id:`a`,text:`A`,duplicateKeys:[]},{keyPath:`b`,id:`b`,text:`B`,duplicateKeys:[]}],sourceLang:`en`,targetLang:`zh`,baseURL:`https://api.openai.com/v1`,apiKey:`key`,model:`m`,batchSize:1,onProgress:(e,t,n,r)=>progress.push({e,t,n,r})});
  check(result.successCount===2,`both batches translate`);
  check(progress.some(p=>p.r&&p.r.stage===`start`&&p.r.currentBatch===1&&p.r.totalBatches===2),`coordinator reports starting batch before request`);
  check(progress.some(p=>p.r&&p.r.stage===`completed`&&p.r.completedBatches===2),`coordinator still reports completed batches`);
}
main().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", coordinator + behavior_contract],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_file_progress_logs_starting_batch(self):
        js, _ = self.patch_assets()
        self.assertIn("if(r?.stage===`start`&&r.currentBatch){O(`", js)
        self.assertIn("\u6b63\u5728\u7ffb\u8bd1\u6279\u6b21", js)
        self.assertIn("\uff08\u672c\u6279 ${r.batchSize} \u6761\uff09", js)
        self.assertIn("{stage:`completed`,cachedCount:h,localRuleCount:g,completedBatches:x", js)

    def test_progress_panel_is_read_directly_from_react_log(self):
        js, _ = self.patch_assets()
        self.assertIn("querySelectorAll(\"#root [class*='font-mono']\")", js)
        self.assertNotIn("querySelectorAll(\"#root details\")", js)
        self.assertIn(r"翻译进度\s*([\d,]+)", js)
        self.assertIn(r"\[(\d+)\/(\d+)\]", js)

    def test_local_translate_reports_start_and_completed_batch(self):
        import patch_local_ui
        code = r'''
const progress=[];
globalThis.window={Capacitor:{Plugins:{FileManager:{translateLocal:async({texts})=>({translations:Object.fromEntries(texts.map((t,i)=>[t.keyPath,'T'+i]))})}}}};
''' + patch_local_ui._LOCAL_HELPERS + r'''
(async()=>{
  const result=await window.__slgLocalTranslateImpl({texts:[{keyPath:'a',text:'A'},{keyPath:'b',text:'B'}],sourceLang:'en',targetLang:'zh',engine:'mlkit',onProgress:(e,t,n,p)=>progress.push({e,t,n,p})});
  if(result.successCount!==2)throw new Error('local result count');
  const starts=progress.filter(x=>x.p&&x.p.stage==='start');
  const ends=progress.filter(x=>x.p&&x.p.stage==='completed');
  if(starts.length!==1||starts[0].p.totalBatches!==1||starts[0].p.batchSize!==2)throw new Error('local start payload');
  if(ends.length!==1||ends[0].p.completedBatches!==1||ends[0].p.totalBatches!==1)throw new Error('local completion payload');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_translate_chunks_large_batches_and_reports_progress(self):
        import patch_local_ui
        code = r'''
const progress=[];const calls=[];
globalThis.window={Capacitor:{Plugins:{FileManager:{translateLocal:async({texts})=>{calls.push(texts.length);return {translations:Object.fromEntries(texts.map(t=>[t.keyPath,'T'+t.keyPath]))}}}}}};
''' + patch_local_ui._LOCAL_HELPERS + r'''
(async()=>{
  const texts=Array.from({length:45},(_,i)=>({keyPath:'k'+i,text:'s'+i}));
  const result=await window.__slgLocalTranslateImpl({texts,sourceLang:'en',targetLang:'zh',engine:'mlkit',onProgress:(e,t,n,p)=>progress.push({e,t,n,p})});
  if(result.successCount!==45)throw new Error('chunked local result count');
  if(calls.join(',')!=='20,20,5')throw new Error('chunk sizes: '+calls.join(','));
  const starts=progress.filter(x=>x.p&&x.p.stage==='start');
  const ends=progress.filter(x=>x.p&&x.p.stage==='completed');
  if(starts.length!==3||starts[0].p.totalBatches!==3||starts[0].p.batchSize!==20||starts[2].p.batchSize!==5)throw new Error('chunk start payloads');
  if(ends.length!==3||ends[0].p.completedBatches!==1||ends[2].p.completedBatches!==3||ends[2].p.totalBatches!==3)throw new Error('chunk completion payloads');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_llm_variant_ui_switches_selected_model(self):
        import patch_local_ui
        self.assertIn('["0.5b","Qwen2.5 0.5B', patch_local_ui._LOCAL_HELPERS)
        self.assertIn('["1.5b","Qwen2.5 1.5B', patch_local_ui._LOCAL_HELPERS)
        self.assertIn("llmDownload({variant:llVariant.select.value||\"1.5b\"})", patch_local_ui._LOCAL_HELPERS)
        code = r'''
function makeEl(tag){
  const el={tagName:tag,children:[],className:"",hidden:false,disabled:false,value:"",textContent:"",type:"",id:"",htmlFor:"",attrs:{}};
  el.append=function(...nodes){for(const n of nodes){this.children.push(n)}};
  el.appendChild=el.append;el.setAttribute=function(k,v){this.attrs[k]=v;if(k==="id")this.id=v};el.replaceChildren=function(){this.children=[]};
  return el;
}
function textNode(tag,cls,text){const el=makeEl(tag);el.className=cls||"";if(text!==undefined)el.textContent=text;return el}
globalThis.document={createElement:makeEl};
const downloads=[];
globalThis.window={Capacitor:{Plugins:{FileManager:{
  localStatus:async()=>({mlkit:{downloaded:true},llm:{installed:true,variant:"1.5b",sizeBytes:1117320736}}),
  llmDownload:async(p)=>{downloads.push(p);return {ok:true}},
  llmDelete:async()=>({deleted:true}),localDownload:async()=>({ok:true}),mlkitDelete:async()=>({deleted:true})
}}}};
''' + patch_local_ui._LOCAL_HELPERS + r'''
(async()=>{
  const section=buildLocalEngineSection();
  await section.refreshLocal();
  const llCard=section.children[1];const variantField=llCard.children[2];const select=variantField.children[1];const llBtn=llCard.children[3];
  if(select.value!=="1.5b")throw new Error('initial variant not synced');
  select.value="0.5b";select.onchange();
  if(llBtn.textContent.indexOf("切换为")!==0)throw new Error('switch label missing: '+llBtn.textContent);
  await llBtn.onclick();
  if(downloads.length!==1||downloads[0].variant!=="0.5b")throw new Error('variant download: '+JSON.stringify(downloads));
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(
            ["node", "-e", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
    def test_local_llm_batching_and_dynamic_tokens_are_wired(self):
        java = (ROOT.parent / "native-fast-scan" / "src" / "com" / "slgtranslator" / "app" / "LocalLlmEngine.java").read_text("utf-8")
        self.assertIn("private static final int BATCH_SIZE = 5;", java)
        self.assertIn("private static final int BATCH_MAX_TOKENS = 768;", java)
        self.assertIn("private static int translateBatch(LlamaModel model", java)
        self.assertIn("completeSync(model, userPrompt, systemPrompt, batchMaxTokens(batch))", java)
        self.assertIn("completeSync(model, guard.protectedText, systemPrompt, maxTokensForText(item.text))", java)
        self.assertIn("private static int maxTokensForText(String text)", java)
        self.assertIn("private static List<String> parseBatchOutput(String raw, int count)", java)
        self.assertIn("qwen2.5-0.5b-instruct-q4_k_m.gguf", java)
        self.assertIn("qwen2.5-1.5b-instruct-q4_k_m.gguf", java)

    def test_cache_writes_are_throttled_and_forced_at_commit_points(self):
        js, _ = self.patch_assets()
        self.assertIn("async function wo(_force=false)", js)
        self.assertIn("if(!_force&&Date.now()-_lastSaveAt<4000)", js)
        self.assertIn("_saveTimer=setTimeout(()=>{_saveTimer=null;wo(!0)},4000)", js)
        self.assertIn("m.length===0)return wo(!0),{translations:d,successCount:d.size};", js)
        self.assertIn("return await Promise.all(ne),wo(!0),{translations:d,successCount:d.size", js)
        self.assertIn("_mode===`full`&&(vo={},cacheIndex={},_dirty={},bo=!0,await wo(!0))", js)
        self.assertIn("bo=!0,wo(!0);t+=l.length", js)
        self.assertIn("return N},(window.__slgLocalSelected?2:6));window.__slgCompiledCount=0;if(!N)await wo(!0);if(!N&&(a.length>0||oe)){", js)


if __name__ == "__main__":
    unittest.main()
