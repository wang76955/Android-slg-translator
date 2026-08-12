from pathlib import Path


path = Path(__file__).parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match, found {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


# Empty data is a valid persisted state for the explicit full-retranslate mode.
replace_once(
    "async function wo(){if(!yo||!bo||Object.keys(vo).length===0)return;",
    "async function wo(){if(!yo||!bo)return;",
)

replace_once(
    "[pe,me]=(0,_.useState)(!1),he=(0,_.useRef)([]),",
    "[pe,me]=(0,_.useState)(!1),[_mode,setMode]=(0,_.useState)(`resume`),he=(0,_.useRef)([]),",
)

# Full mode clears persistent sentence and file records. Scan mode bypasses only
# completed-file records, so unchanged sentences still come from cache.
replace_once(
    "else await Co();for(let i=0;i<ae.length;i+=fs){",
    "else await Co(),_mode===`full`&&(vo={},bo=!0,await wo());for(let i=0;i<ae.length;i+=fs){",
)

replace_once(
    "let _fk=`slg-file-v1:${U([n,o.name,g,y,S].join(`|`))}`,_fr=vo[_fk];if(_fr&&Array.isArray(_fr.outputs)&&_fr.outputs.length){",
    "let _fk=`slg-file-v1:${U([n,o.name,g,y,S].join(`|`))}`,_fr=vo[_fk];if(_mode===`resume`&&_fr&&Array.isArray(_fr.outputs)&&_fr.outputs.length){",
)

# Add a compact segmented mode selector above the discovered-file list.
needle = "ae.length>0&&(0,D.jsx)(`div`,{className:`mt-3 max-h-48 overflow-y-auto border border-slate-100 rounded-lg divide-y divide-slate-50`"
replacement = "ae.length>0&&(0,D.jsxs)(`div`,{className:`mt-3`,children:[(0,D.jsx)(`div`,{className:`grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1`,children:[[`resume`,`继续上次`],[`scan`,`扫描新增`],[`full`,`全部重译`]].map(e=>(0,D.jsx)(`button`,{type:`button`,onClick:()=>setMode(e[0]),className:`px-2 py-1.5 text-xs rounded-md ${_mode===e[0]?`bg-white text-blue-600 shadow-sm`:`text-slate-500`}`,children:e[1]},e[0]))}),(0,D.jsx)(`p`,{className:`mt-1 text-xs text-slate-400`,children:_mode===`resume`?`复用已完成文件和译文缓存`:_mode===`scan`?`重新扫描文件，仅翻译新增文本`:`清空缓存并重新翻译全部文本`})]})," + needle
replace_once(needle, replacement)

path.write_text(text, encoding="utf-8")
print("Added resume, scan-new, and full-retranslate modes")
