with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content=f.read()
for off in ['0064d8','005f94','00a6e4','009aac']:
    idx=content.find(off)
    print('\n===',off,'===')
    if idx>=0: print(content[idx:idx+6500])
