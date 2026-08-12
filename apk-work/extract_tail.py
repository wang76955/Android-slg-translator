from pathlib import Path
s=Path(r"C:\tools\temp_dex\dex6_dump.txt").read_text(encoding="utf-8",errors="replace")
idx=s.find('00a58c:')
print(s[idx:idx+6500])
