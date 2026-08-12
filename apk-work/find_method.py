with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find RenPyRpycParser.isLikelyVisibleRenPyString method
# It's at 0x9aac
idx = content.find("009aac")
if idx >= 0:
    end = min(len(content), idx + 2000)
    print(content[idx:end])
