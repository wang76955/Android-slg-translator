with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find RenPyRpycParser class definition  
idx = content.find('Lcom/slgtranslator/app/RenPyRpycParser;')
print('Found at:', hex(idx) if idx >= 0 else -1)

if idx >= 0:
    start = max(0, idx - 50)
    # Print a few thousand chars around it
    end = min(len(content), start + 2000)
    print(content[start:end])
