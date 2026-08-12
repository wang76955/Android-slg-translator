with open(r'C:\tools\temp_dex\dex6_dump.txt', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find parseRpyc at offset 0x5f94
# The section for FileManagerPlugin.parseRpyc
idx = content.find("005f94")
print("Looking at FileManagerPlugin.parseRpyc:")
section = content[idx:idx+2000]
print(section)
