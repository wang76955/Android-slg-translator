import zipfile, zlib, hashlib

dex_path = r'C:\Users\王运\Documents\文件翻译\apk-work\extracted\classes6.dex'
with open(dex_path, 'rb') as f:
    dex = bytearray(f.read())

# Patch 1: 0xa504
p1_orig = bytes.fromhex('7030f3000502')
p1_new = bytes.fromhex('6e2058010002')
assert dex[0xa504:0xa504+6] == p1_orig, 'Patch 1 mismatch at 0xa504: ' + dex[0xa504:0xa504+6].hex()
dex[0xa504:0xa504+6] = p1_new
print('Patched 0xa504: ' + p1_orig.hex() + ' -> ' + p1_new.hex())

# Patch 2: 0xa58c
p2_orig = bytes.fromhex('7030f3000803')
p2_new = bytes.fromhex('6e2058010003')
assert dex[0xa58c:0xa58c+6] == p2_orig, 'Patch 2 mismatch at 0xa58c: ' + dex[0xa58c:0xa58c+6].hex()
dex[0xa58c:0xa58c+6] = p2_new
print('Patched 0xa58c: ' + p2_orig.hex() + ' -> ' + p2_new.hex())

# Patch 3: 0xa5d0
p3_orig = bytes.fromhex('7030f3000604')
p3_new = bytes.fromhex('6e2058010004')
assert dex[0xa5d0:0xa5d0+6] == p3_orig, 'Patch 3 mismatch at 0xa5d0: ' + dex[0xa5d0:0xa5d0+6].hex()
dex[0xa5d0:0xa5d0+6] = p3_new
print('Patched 0xa5d0: ' + p3_orig.hex() + ' -> ' + p3_new.hex())

# Verify no remaining addVisible calls
remaining = 0
idx = 0
while True:
    pos = dex.find(bytes.fromhex('7030f3'), idx)
    if pos == -1:
        break
    print('WARNING: remaining unpatched addVisible at 0x' + hex(pos))
    remaining += 1
    idx = pos + 1

if remaining == 0:
    print('All addVisible calls have been patched!')

# Fix DEX checksum and SHA-1
new_csum = zlib.adler32(bytes(dex[12:]))
dex[8:12] = new_csum.to_bytes(4, 'little')
sha1 = hashlib.sha1(bytes(dex[32:])).digest()
dex[12:32] = sha1

with open(dex_path, 'wb') as f:
    f.write(dex)

# Verify
with open(dex_path, 'rb') as f:
    verified = f.read()
v_csum = int.from_bytes(verified[8:12], 'little')
v_expected = zlib.adler32(verified[12:])
print('Checksum: stored=' + hex(v_csum) + ', correct=' + hex(v_expected) + ', match=' + str(v_csum == v_expected))
print('DEX updated successfully!')
