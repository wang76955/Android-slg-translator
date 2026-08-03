import zipfile, zlib

z = zipfile.ZipFile('apk-work/ui-redesign/qa/ewn-audit-src.apk')
raw = z.read('assets/x-game/x-phone.rpyc')
pos = 10
data = None
while pos + 12 <= len(raw):
    sid = int.from_bytes(raw[pos:pos+4], 'little')
    off = int.from_bytes(raw[pos+4:pos+8], 'little')
    ln = int.from_bytes(raw[pos+8:pos+12], 'little')
    if sid == 0: break
    if sid == 2:
        data = zlib.decompress(raw[off:off+ln])
        break
    pos += 12

# Extract the big source string
ln = int.from_bytes(data[2186:2190], 'little')
src = data[2190:2190+ln].decode('utf-8', errors='replace')
with open('apk-work/ui-redesign/qa/phone-source.py', 'w', encoding='utf-8') as f:
    f.write(src)
print('Wrote phone-source.py:', len(src), 'chars')

# Count patterns
import re
send_calls = re.findall(r'send_phone_message\(', src)
print('send_phone_message calls:', len(send_calls))

# Count _("...") marked text
marked = re.findall(r'_\(\"((?:[^\"\\\\]|\\\\.)*)\"\)', src)
print('_() marked strings:', len(marked))
for m in marked[:10]:
    print('  ', repr(m[:80]))

# Sample some send_phone_message calls
for m in re.finditer(r'send_phone_message\([^)]*\)', src):
    print('CALL:', repr(m.group(0)[:150]))
