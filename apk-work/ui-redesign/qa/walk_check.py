import zipfile, zlib

z = zipfile.ZipFile('apk-work/ui-redesign/qa/ewn-audit-src.apk')

def read_slot(name, slot_id=2):
    raw = z.read(name)
    pos = 10
    while pos + 12 <= len(raw):
        sid = int.from_bytes(raw[pos:pos+4], 'little')
        off = int.from_bytes(raw[pos+4:pos+8], 'little')
        ln = int.from_bytes(raw[pos+8:pos+12], 'little')
        if sid == 0: break
        if sid == slot_id:
            return zlib.decompress(raw[off:off+ln])
        pos += 12
    return None

def le32(data, pos):
    return int.from_bytes(data[pos:pos+4], 'little')

def length_after(data, pos, code):
    if code in (0x4a, 0x4b, 0x4d, 0x68, 0x71, 0x6a, 0x72, 0x82, 0x83, 0x84, 0x80, 0x47, 0x95):
        return 0
    if code in (0x8c, 0x55, 0x43, 0x8a):
        return data[pos]
    return le32(data, pos)

def skip_newline(data, pos):
    while pos < len(data) and data[pos] != 0x0a:
        pos += 1
    return pos + 1

def walk_java(data):
    ops = []
    pos = 0
    n = len(data)
    while pos < n:
        b = data[pos]
        start = pos
        pos += 1
        if b in (0x4a, 0x58, 0x54, 0x42, 0x8b):
            pos += 4 + length_after(data, pos, b)
        elif b in (0x4b, 0x55, 0x43):
            pos += 1 + length_after(data, pos, b)
        elif b == 0x4d:
            pos += 2
        elif b in (0x47, 0x95):
            pos += 8
        elif b in (0x8a, 0x8c):
            pos += 1 + length_after(data, pos, b)
        elif b in (0x8d, 0x8e, 0x96):
            pos += 8 + int.from_bytes(data[pos:pos+8], 'little')
        elif b in (0x68, 0x71, 0x82, 0x80):
            pos += 1
        elif b in (0x6a, 0x72, 0x84):
            pos += 4
        elif b == 0x83:
            pos += 2
        elif b in (0x49, 0x4c, 0x53, 0x56, 0x46, 0x67, 0x70, 0x50):
            pos = skip_newline(data, pos)
        elif b in (0x63, 0x69):
            pos = skip_newline(data, pos)
            pos = skip_newline(data, pos)
        elif b in (0x28, 0x2e, 0x29, 0x30, 0x31, 0x32, 0x4e, 0x52, 0x62, 0x61, 0x65,
                   0x6c, 0x5d, 0x64, 0x7d, 0x6f, 0x73, 0x74, 0x75, 0x85, 0x86, 0x87,
                   0x88, 0x89, 0x8f, 0x90, 0x91, 0x93, 0x81, 0x92, 0x94, 0x51):
            pass
        else:
            return None, b, start
        if pos > n:
            return None, b, start
        ops.append([b, start, pos])
    return ops, None, None

for fname in ['assets/x-game/x-phone.rpyc', 'assets/x-game/x-myscreens.rpyc', 'assets/x-game/x-screens.rpyc']:
    data = read_slot(fname)
    if data is None:
        print(f'{fname}: NO PICKLE')
        continue
    ops, bad, badpos = walk_java(data)
    if ops is None:
        print(f'{fname}: walk returns null (unknown opcode {hex(bad)} at {badpos})')
    else:
        print(f'{fname}: walk OK, {len(ops)} ops')
