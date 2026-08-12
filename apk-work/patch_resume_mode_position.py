from pathlib import Path


path = Path(__file__).parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
text = path.read_text(encoding="utf-8")

control = "ae.length>0&&(0,D.jsxs)(`div`,{className:`mt-3`,children:[(0,D.jsx)(`div`,{className:`grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1`,children:[[`resume`,`继续上次`],[`scan`,`扫描新增`],[`full`,`全部重译`]].map(e=>(0,D.jsx)(`button`,{type:`button`,onClick:()=>setMode(e[0]),className:`px-2 py-1.5 text-xs rounded-md ${_mode===e[0]?`bg-white text-blue-600 shadow-sm`:`text-slate-500`}`,children:e[1]},e[0]))}),(0,D.jsx)(`p`,{className:`mt-1 text-xs text-slate-400`,children:_mode===`resume`?`复用已完成文件和译文缓存`:_mode===`scan`?`重新扫描文件，仅翻译新增文本`:`清空缓存并重新翻译全部文本`})]})"

if text.count(control) != 1:
    raise RuntimeError(f"Expected one existing mode selector, found {text.count(control)}")
text = text.replace(control + ",", "", 1)

button = "(0,D.jsx)(`button`,{onClick:Ce,disabled:se||!te&&!oe,"
if text.count(button) != 1:
    raise RuntimeError(f"Expected one start button, found {text.count(button)}")

visible_control = control.replace(
    "className:`mt-3`",
    "className:`border border-slate-200 rounded-xl bg-white p-3`",
    1,
)
text = text.replace(button, visible_control + "," + button, 1)

path.write_text(text, encoding="utf-8")
print("Moved translation mode selector above the start button")
