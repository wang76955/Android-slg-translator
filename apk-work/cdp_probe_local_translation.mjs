const ws = "ws://127.0.0.1:9222/devtools/page/F2705A86B1E38CD0171763F76F0F5F4B";
const expression = `(async()=>{
  const records=globalThis.__slgCoverageRecords||[];
  const approved=globalThis.__slgValidatorApprovedTranslations instanceof Map
    ? globalThis.__slgValidatorApprovedTranslations : new Map(Object.entries(globalThis.__slgValidatorApprovedTranslations||{}));
  const groups=new Map();
  for(const record of records){
    const old=String(record?.text??"");
    if(!old.trim())continue;
    const group=groups.get(old)||{old,occurrences:0};group.occurrences++;groups.set(old,group);
  }
  const sample=[
    "Wait... Your face looks familiar.",
    "Wait. Your face looks familiar.",
    "Your face looks familiar.",
    "F-finish your food first, then we can...",
    "Finish your food first, then we can.",
    "F-finish your food first",
    "FIREBALL!",
    "Use",
    "60",
    "..."
  ].map((old,index)=>({old,occurrences:1,keyPath:"sample"+index}));
  const result=await Capacitor.Plugins.FileManager.translateLocal({
    texts:sample.map(group=>({keyPath:group.keyPath,text:group.old})),
    sourceLang:"en",targetLang:"zh",engine:"mlkit"
  });
  return JSON.stringify({sample,result});
})()`;

const socket = new WebSocket(ws);
const timer = setTimeout(() => process.exit(3), 90000);
socket.addEventListener("open", () => {
  socket.send(JSON.stringify({
    id: 1,
    method: "Runtime.evaluate",
    params: { expression, awaitPromise: true, returnByValue: true },
  }));
});
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  clearTimeout(timer);
  if (message.error || message.result?.exceptionDetails) {
    console.error(JSON.stringify(message.error || message.result.exceptionDetails));
    process.exitCode = 1;
  } else {
    console.log(message.result?.result?.value ?? "null");
  }
  socket.close();
});
