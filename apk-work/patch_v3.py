import zipfile, zlib, hashlib

# Restore original base APK's classes6.dex
base = r'C:\Users\王运\Documents\文件翻译\apk-work\com.slgtranslator.app-base.apk'
dex_path = r'C:\Users\王运\Documents\文件翻译\apk-work\extracted\classes6.dex'

with zipfile.ZipFile(base) as z:
    orig_dex = bytearray(z.read('classes6.dex'))

# Verify the original DEX has original addVisible calls
assert orig_dex[0xa4b4:0xa4b4+4] == bytes.fromhex('7030f300'), "Original DEX should have addVisible at 0xa4b4"
print("Original DEX verified - addVisible calls present")

# Now patch isLikelyVisibleRenPyString in RenPyRpycParser to always return true
# Method at DEX offset 0x9aac
# Original first instruction: 6e10 3401 0b00 (invoke-virtual {v11}, String.length:()I)
# Replace with: 1210 0f00 (const/4 v0, 1; return v0)
current = orig_dex[0x9abc:0x9abc+6]
print(f"Current at 0x9abc: {current.hex()}")
assert current[:2] == bytes.fromhex('6e10'), "Should be invoke-virtual at 0x9abc"

# Write new instructions: const/4 v0, 1; return v0; nop
new_patch = bytes.fromhex('12100f000000')
orig_dex[0x9abc:0x9abc+6] = new_patch
print(f"Patched isLikelyVisibleRenPyString at 0x9abc to always return true")

# Fix DEX checksum and SHA-1
new_csum = zlib.adler32(bytes(orig_dex[12:]))
orig_dex[8:12] = new_csum.to_bytes(4, 'little')
sha1 = hashlib.sha1(bytes(orig_dex[32:])).digest()
orig_dex[12:32] = sha1

with open(dex_path, 'wb') as f:
    f.write(orig_dex)

# Verify
with open(dex_path, 'rb') as f:
    v = f.read()

v_csum = int.from_bytes(v[8:12], 'little')
v_expected = zlib.adler32(v[12:])
print(f"Checksum match: {v_csum == v_expected}")

# Verify patches are correct (addVisible restored, isLikelyVisibleRenPyString always true)
for off in [0xa4b4, 0xa504, 0xa58c, 0xa5d0]:
    d = v[off:off+4]
    has_addVisible = d == bytes.fromhex('7030f3')
    print(f"Offset {hex(off)}: {d.hex()} -> {'addVisible (ORIGINAL)' if has_addVisible else '*** BAD ***'}")

# Verify isLikelyVisibleRenPyString patch
patch_check = v[0x9abc:0x9abc+6]
print(f"isLikelyVisibleRenPyString at 0x9abc: {patch_check.hex()}")
assert patch_check[:4] == bytes.fromhex('12100f00'), "isLikelyVisibleRenPyString patch failed!"

print("\nALL PATCHES VERIFIED!")
