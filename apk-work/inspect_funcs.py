from pathlib import Path
s=Path(r"C:\Users\王运\Documents\文件翻译\apk-work\extracted\assets\public\assets\index-CJtfdHOF.js").read_text(encoding="utf-8")
for needle in ["function Jo", "Jo=", "function ke", "ke=", "function is", "fileType"]:
    print("\n===", needle, "===")
    pos=s.find(needle)
    if pos>=0: print(s[max(0,pos-1200):pos+2600])
