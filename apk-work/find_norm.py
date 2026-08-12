with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find normalizeVisibleText in RenPyRpycParser
# It's at method@0xf8
# Search for the method definition
idx = content.find("normalizeVisibleText")
if idx >= 0:
    start = max(0, idx - 100)
    end = min(len(content), idx + 4000)
    print(content[start:end])
else:
    print("normalizeVisibleText not found!")
