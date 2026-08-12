from pathlib import Path


path = Path(__file__).parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match, found {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
    "var _o=`slg-translator-cache:`,vo={},yo=!1,bo=!1;",
    "var _o=`slg-translator-cache:`,vo={},yo=!1,bo=!1,bp=Promise.resolve();",
)

replace_once(
    "async function wo(){if(!(!yo||!bo||Object.keys(vo).length===0))try{await E.saveTranslationCache({data:JSON.stringify(vo)}),bo=!1}catch{}}",
    "async function wo(){if(!yo||!bo||Object.keys(vo).length===0)return;let e=JSON.stringify(vo);bo=!1,bp=bp.then(()=>E.saveTranslationCache({data:e})).catch(()=>{bo=!0}),await bp}",
)

# Persist newly translated entries after every completed API batch. The queued
# save implementation above prevents concurrent workers from overwriting a
# newer cache snapshot.
replace_once(
    "}}catch{v=!0,ee+=1}x+=1,l?.(d.size,t.length,`translating`,",
    "}}catch{v=!0,ee+=1}await wo(),x+=1,l?.(d.size,t.length,`translating`,",
)

# Load persistent state before checking file-level completion records.
replace_once(
    "for(let i=0;i<ae.length;i+=fs){",
    "await Co();for(let i=0;i<ae.length;i+=fs){",
)

# A completed file stores its generated Ren'Py outputs. On the next run with
# the same APK URI, entry, languages, and model, restore those outputs without
# reopening the multi-gigabyte APK entry or calling the translation API.
replace_once(
    "try{let{content:i,fileType:s}=await E.readFileContent({uri:n,entryName:o.name}),",
    "try{let _fk=`slg-file-v1:${U([n,o.name,g,y,S].join(`|`))}`,_fr=vo[_fk];if(_fr&&Array.isArray(_fr.outputs)&&_fr.outputs.length){for(let e of _fr.outputs)await Ne(e.outputPath,e.content),a.push({path:e.outputPath,content:e.content});t+=_fr.count||0,O(`  已完成文件，复用 ${_fr.count||0} 条译文`,`success`),ue({current:c+1,total:ae.length});return}let{content:i,fileType:s}=await E.readFileContent({uri:n,entryName:o.name}),",
)

replace_once(
    "for(let e of t.values())await Ne(e.outputPath,e.content),a.push({path:e.outputPath,content:e.content}),O(`  生成 Ren'Py 翻译包：${e.outputPath}`,`success`)}else{",
    "let _fo=Array.from(t.values());for(let e of _fo)await Ne(e.outputPath,e.content),a.push({path:e.outputPath,content:e.content}),O(`  生成 Ren'Py 翻译包：${e.outputPath}`,`success`);if(!m&&p===l.length)vo[_fk]={outputs:_fo,count:p,updatedAt:Date.now()},bo=!0,await wo()}else{",
)

path.write_text(text, encoding="utf-8")
print("Patched incremental batch saves and file-level resume cache")
