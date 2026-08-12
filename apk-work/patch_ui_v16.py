from pathlib import Path


path = Path(__file__).parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match, found {count}: {old[:140]!r}")
    text = text.replace(old, new, 1)


replace_once(
    "className:`bg-white border-b border-slate-200 px-4 py-3 shrink-0`",
    "className:`bg-white border-b border-slate-200 px-5 py-4 shrink-0`",
)
replace_once(
    "className:`text-base font-bold text-slate-800`",
    "className:`text-lg font-semibold text-slate-900`",
)
replace_once(
    "children:`选择 APK → 自动扫描 → AI 翻译 → 导出`",
    "children:n?`${i||`已选择 APK`} · ${ae.length||0} 个脚本`:`选择游戏 APK，提取对白并生成可安装补丁`",
)

# Add a compact workflow stepper between the app header and content.
main = "(0,D.jsxs)(`main`,{className:`flex-1 overflow-y-auto p-4 space-y-4 safe-bottom`"
stepper = "(0,D.jsx)(`nav`,{className:`bg-white border-b border-slate-200 px-4 py-3`,children:(0,D.jsx)(`div`,{className:`max-w-3xl mx-auto grid grid-cols-4 gap-1`,children:[[`1`,`选择`,!!n],[`2`,`设置`,!!n&&ae.length>0],[`3`,`处理`,se],[`4`,`完成`,!!T]].map((e,t)=>(0,D.jsxs)(`div`,{className:`flex items-center min-w-0`,children:[(0,D.jsx)(`span`,{className:`h-6 w-6 shrink-0 flex items-center justify-center rounded-full text-xs font-semibold ${e[2]?`bg-blue-600 text-white`:`bg-slate-100 text-slate-400`}`,children:e[0]}),(0,D.jsx)(`span`,{className:`ml-1 text-xs truncate ${e[2]?`text-slate-800 font-medium`:`text-slate-400`}`,children:e[1]}),t<3&&(0,D.jsx)(`span`,{className:`mx-1 h-px flex-1 bg-slate-200`})]},e[0]))})}),"
replace_once(main, stepper + "(0,D.jsxs)(`main`,{className:`flex-1 overflow-y-auto p-4 space-y-4 safe-bottom max-w-3xl mx-auto w-full`")

# Use tighter operational panels instead of oversized rounded cards.
text = text.replace("border border-slate-200 rounded-xl bg-white", "border border-slate-200 rounded-lg bg-white")
text = text.replace("text-white rounded-xl text-sm font-medium", "text-white rounded-lg text-sm font-medium")

# Convert the selected-file notice into a neutral task summary.
replace_once(
    "className:`mt-3 bg-green-50 border border-green-200 rounded-lg p-3`",
    "className:`mt-3 bg-slate-50 border border-slate-200 rounded-lg p-3`",
)
replace_once("className:`text-xs text-green-700 break-all`", "className:`text-xs font-medium text-slate-700 break-all`")
text = text.replace("className:`text-xs text-green-600 mt-1`", "className:`text-xs text-slate-500 mt-1`", 1)

# Add a scan/task summary immediately before translation settings.
settings = "m&&ae.length>0&&(0,D.jsxs)(D.Fragment,{children:["
summary = "m&&ae.length>0&&(0,D.jsxs)(D.Fragment,{children:[(0,D.jsxs)(`section`,{className:`border border-slate-200 rounded-lg bg-white px-4 py-3`,children:[(0,D.jsxs)(`div`,{className:`flex items-center justify-between`,children:[(0,D.jsx)(`h2`,{className:`text-sm font-semibold text-slate-800`,children:`当前任务`}),(0,D.jsx)(`span`,{className:`text-xs text-emerald-600`,children:u?`扫描中`:`已就绪`})]}),(0,D.jsxs)(`div`,{className:`mt-3 grid grid-cols-3 divide-x divide-slate-200`,children:[(0,D.jsxs)(`div`,{children:[(0,D.jsx)(`p`,{className:`text-lg font-semibold text-slate-900`,children:ae.length}),(0,D.jsx)(`p`,{className:`text-xs text-slate-400`,children:`脚本文件`})]}),(0,D.jsxs)(`div`,{className:`pl-3`,children:[(0,D.jsxs)(`p`,{className:`text-sm font-medium text-slate-800`,children:[g.toUpperCase(),` → `,y.toUpperCase()]}),(0,D.jsx)(`p`,{className:`text-xs text-slate-400 mt-1`,children:`翻译方向`})]}),(0,D.jsxs)(`div`,{className:`pl-3`,children:[(0,D.jsx)(`p`,{className:`text-sm font-medium text-slate-800 truncate`,children:_mode===`resume`?`续译`:_mode===`scan`?`增量`:`全量`}),(0,D.jsx)(`p`,{className:`text-xs text-slate-400 mt-1`,children:`任务模式`})]})]})]}),"
replace_once(settings, summary)

# Label the mode selector and add a compact workload description.
replace_once(
    "className:`border border-slate-200 rounded-lg bg-white p-3`,children:[(0,D.jsx)(`div`,{className:`grid grid-cols-3",
    "className:`border border-slate-200 rounded-lg bg-white p-3`,children:[(0,D.jsx)(`h2`,{className:`text-sm font-semibold text-slate-800 mb-2`,children:`任务模式`}),(0,D.jsx)(`div`,{className:`grid grid-cols-3",
)

# Show an explicit progress bar above the primary command while running.
start = "(0,D.jsx)(`button`,{onClick:Ce,disabled:se||!te&&!oe,"
progress = "se&&(0,D.jsxs)(`section`,{className:`border border-blue-200 rounded-lg bg-blue-50 p-3`,children:[(0,D.jsxs)(`div`,{className:`flex items-center justify-between text-xs`,children:[(0,D.jsx)(`span`,{className:`font-medium text-blue-700`,children:`正在处理脚本`}),(0,D.jsxs)(`span`,{className:`text-blue-600`,children:[le.current,` / `,le.total]})]}),(0,D.jsx)(`div`,{className:`mt-2 h-2 overflow-hidden rounded-full bg-blue-100`,children:(0,D.jsx)(`div`,{className:`h-full bg-blue-600 transition-all`,style:{width:`${le.total?Math.min(100,Math.round(le.current/le.total*100)):0}%`}})})]}),"
replace_once(start, progress + start)

# Keep verbose logs available without letting them dominate the main workflow.
old_logs = "(se||de.length>0)&&(0,D.jsx)(ye,{current:le.current,total:le.total,logs:de,status:se?`translating`:T?`done`:`idle`,result:T,onInstallPatchedApk:Te,onUninstallAndInstall:we,onOpenGameSettings:Ee,onLaunchGame:De,apkPackageName:f,installingPatch:pe})"
new_logs = "(se||de.length>0)&&(0,D.jsxs)(`details`,{open:se,className:`border border-slate-200 rounded-lg bg-white overflow-hidden`,children:[(0,D.jsxs)(`summary`,{className:`cursor-pointer list-none px-4 py-3 text-sm font-medium text-slate-700 flex items-center justify-between`,children:[`详细日志`,(0,D.jsxs)(`span`,{className:`text-xs font-normal text-slate-400`,children:[de.length,` 条`]})]}),(0,D.jsx)(`div`,{className:`border-t border-slate-100 p-3`,children:(0,D.jsx)(ye,{current:le.current,total:le.total,logs:de,status:se?`translating`:T?`done`:`idle`,result:T,onInstallPatchedApk:Te,onUninstallAndInstall:we,onOpenGameSettings:Ee,onLaunchGame:De,apkPackageName:f,installingPatch:pe})})]})"
replace_once(old_logs, new_logs)

path.write_text(text, encoding="utf-8")
print("Applied operational dashboard UI refresh")
