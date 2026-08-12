with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

cidx = content.find('Class #15')
sidxa = content.find('Lcom/slgtranslator/app/RenPyRpycParser;', cidx)
sidxb = content.find('Class #16', cidx)
section = content[sidxa:sidxb]

pidx = section.find("parseRpyc")
print('Found at section offset:', pidx)
if pidx >= 0:
    start = section.rfind("name", 0, pidx)
    end = min(len(section), pidx + 6000)
    print(section[start:end])
