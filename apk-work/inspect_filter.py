from pathlib import Path
s=Path(r"C:\Users\王运\Documents\文件翻译\apk-work\extracted\assets\public\assets\index-CJtfdHOF.js").read_text(encoding="utf-8")
for needle in ["function We", "We=", "function He", "function Ve", "function Jo(e,t,n)"]:
 p=s.find(needle)
 print('\n===',needle,p,'===')
 if p>=0: print(s[max(0,p-500):p+2200])
