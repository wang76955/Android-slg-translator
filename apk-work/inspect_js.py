from pathlib import Path
p=Path(r"C:\Users\王运\Documents\文件翻译\apk-work\extracted\assets\public\assets\index-CJtfdHOF.js")
s=p.read_text(encoding="utf-8")
for needle in ["readFileContent", "listApkEntries", "RPYC_STRING", "async function", "function Me"]:
    print("\n===", needle, "===")
    pos=0; c=0
    while c<8:
        pos=s.find(needle,pos)
        if pos<0: break
        print(s[max(0,pos-600):pos+1000])
        pos += len(needle); c+=1
