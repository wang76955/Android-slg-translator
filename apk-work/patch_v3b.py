import zipfile, zlib, hashlib

dex_path = r'C:\Users\王运\Documents\文件翻译\apk-work\extracted\classes6.dex'

with open(dex_path, 'rb') as f:
    dex = bytearray(f.read())

# Verify addVisible calls are restored
for off in [0xa4b4, 0xa504, 0xa58c, 0xa5d0]:
    d = dex[off:off+6]
    is_addVisible = d[:3] == bytes.fromhex('7030f3')
    print(f"Offset {hex(off)}: {d.hex()} -> {'addVisible' if is_addVisible else 'OTHER'}")

# Fix SHA-1 first (bytes 32:end)
sha1 = hashlib.sha1(bytes(dex[32:])).digest()
dex[12:32] = sha1
print(f"SHA-1 updated: {sha1.hex()}")

# Then fix checksum (bytes 12:end)
new_csum = zlib.adler32(bytes(dex[12:]))
dex[8:12] = new_csum.to_bytes(4, 'little')
print(f"Checksum updated: {hex(new_csum)}")

with open(dex_path, 'wb') as f:
    f.write(dex)

# Verify
with open(dex_path, 'rb') as f:
    v = f.read()
v_csum = int.from_bytes(v[8:12], 'little')
v_expected = zlib.adler32(v[12:])
print(f"Checksum match: {v_csum == v_expected} (stored={hex(v_csum)}, expected={hex(v_expected)})")

# Verify isLikelyVisibleRenPyString patch
patch_check = v[0x9abc:0x9abc+6]
print(f"isLikelyVisibleRenPyString at 0x9abc: {patch_check.hex()}")
