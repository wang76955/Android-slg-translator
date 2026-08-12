from pathlib import Path


path = Path(__file__).parent / "extracted" / "assets" / "public" / "assets" / "index-CJtfdHOF.js"
text = path.read_text(encoding="utf-8")

old = "className:`bg-white border-b border-slate-200 px-5 py-4 shrink-0`"
new = "className:`bg-white border-b border-slate-200 px-4 py-3 shrink-0`"
if text.count(old) != 1:
    raise RuntimeError("Header class not found")
text = text.replace(old, new, 1)

old = "className:`max-w-3xl mx-auto grid grid-cols-4 gap-1`,children:"
new = "className:`mx-auto grid gap-1`,style:{maxWidth:`768px`,gridTemplateColumns:`repeat(4,minmax(0,1fr))`},children:"
if text.count(old) != 1:
    raise RuntimeError("Stepper grid not found")
text = text.replace(old, new, 1)

old = "className:`flex-1 overflow-y-auto p-4 space-y-4 safe-bottom max-w-3xl mx-auto w-full`"
new = "className:`flex-1 overflow-y-auto p-4 space-y-4 safe-bottom mx-auto w-full`,style:{maxWidth:`768px`}"
if text.count(old) != 1:
    raise RuntimeError("Main container not found")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Fixed dashboard spacing and four-column stepper")
