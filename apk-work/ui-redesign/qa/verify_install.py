# Verify markup-tagged dialogue translations in the installed APK
import subprocess, zipfile, zlib, re

# Use the local pulled copy (patched2.apk) for quick verification
apk = r'C:\Temp\patched2.apk'

def read_slot(raw, slot_id):
    pos = len(b'RENPY RPC2')
    while pos + 12 <= len(raw):
        sid = int.from_bytes(raw[pos:pos+4], 'little')
        off = int.from_bytes(raw[pos+4:pos+8], 'little')
        ln = int.from_bytes(raw[pos+8:pos+12], 'little')
        if sid == 0: return None
        if sid == slot_id:
            try:
                return zlib.decompress(raw[off:off+ln])
            except:
                return None
        pos += 12
    return None

with zipfile.ZipFile(apk) as z:
    raw = z.read('assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc')
    pickle = read_slot(raw, 2)
    print('Translations rpyc decompressed size:', len(pickle) if pickle else 0, 'bytes')

# Extract old keys and check for markup-tagged dialogue
import pickletools, io
buf = io.BytesIO(pickle)
ops = list(pickletools.genops(buf))
memo = {}
memo_idx = 0
last_string = None
old_keys = set()
last_key = None
for opcode, arg, pos in ops:
    if opcode.name in ('SHORT_BINUNICODE', 'BINUNICODE'):
        last_string = arg
        if last_key == 'old':
            old_keys.add(arg)
            last_key = None
        elif arg == 'old':
            last_key = arg
        else:
            last_key = None
    elif opcode.name in ('BINPUT', 'LONG_BINPUT'):
        memo[arg] = last_string
    elif opcode.name == 'MEMOIZE':
        memo[memo_idx] = last_string
        memo_idx += 1
    elif opcode.name in ('BINGET', 'LONG_BINGET'):
        v = memo.get(arg)
        if isinstance(v, str):
            last_string = v
            if last_key == 'old':
                old_keys.add(v)
                last_key = None
            elif v == 'old':
                last_key = v
            else:
                last_key = None
    elif opcode.name in ('SETITEMS', 'SETITEM', 'BUILD', 'POP_MARK'):
        last_key = None

print('Total translation old keys:', len(old_keys))

# Check for specific markup-tagged dialogue
markup_keys = [k for k in old_keys if '{/i}' in k or '{/b}' in k]
print('Markup-tagged dialogue translations:', len(markup_keys))
for k in sorted(markup_keys)[:10]:
    print('  ', k[:100])
