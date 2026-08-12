with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find RenPyRpycParser class section
ridx = content.find("Lcom/slgtranslator/app/RenPyRpycParser;", 120000)
section = content[ridx:ridx+10000]

# Find normalizeVisibleText method
nidx = section.find("normalizeVisibleText")
if nidx >= 0:
    start = section.rfind("name", 0, nidx)
    end = min(len(section), nidx + 6000)
    print(section[start:end])
else:
    print("normalizeVisibleText not in RenPyRpycParser section")
    # Try searching whole dump
    nidx = content.find("normalizeVisibleText")
    if nidx >= 0:
        start = max(0, nidx - 200)
        end = min(len(content), nidx + 3000)
        print(content[start:end])
