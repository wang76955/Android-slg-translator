from pathlib import Path
s=Path(r"C:\tools\temp_dex\dex6_dump.txt").read_text(encoding="utf-8",errors="replace")
start=s.find("Class descriptor  : 'Lcom/slgtranslator/app/RenPyRpycParser;'")
end=s.find('Class #16',start)
sec=s[start:end]
for needle in ["name          : 'extractPickleStrings'", "name          : 'parseRpyc'"]:
 p=sec.find(needle)
 print('\n===',needle,p,'===')
 if p>=0: print(sec[p:p+10000])
