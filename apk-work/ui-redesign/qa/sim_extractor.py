import zipfile, zlib, re

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
            return None
        if pos > n:
            return None
        ops.append([b, start, pos])
    return ops

KEY_NAMES = {'linenumber','col_offset','filename','name_version','name_serial','who','what','caption','items','arguments','with','attributes','multiple','rollback','tag','value','label','code','language','old','new','newloc','store','varname','hide','parameters','expression','block','priority','next','parsed','init_offset','init_priority','style_name','properties','type','target','global_label','paired','text','text_value','identifier','translate_identifier','alternate_translate_identifier'}
TEXT_KEYS = {'what','caption','old','text','text_value'}

def get_string(data, ops, i):
    op = ops[i]
    code = op[0]
    if code == 0x8c:
        ln = data[op[1]+1]
        return data[op[1]+2:op[1]+2+ln].decode('utf-8', errors='replace')
    if code == 0x58:
        ln = le32(data, op[1]+1)
        return data[op[1]+5:op[1]+5+ln].decode('utf-8', errors='replace')
    return None

def extractor_sim(data):
    ops = walk_java(data)
    if ops is None:
        return []
    memo = {}
    memoTrack = 0
    last_string = None
    last_key = None
    out = []
    choices = []
    items_mode = False
    after_tuple3 = False
    extra_seen = set()
    for i, op in enumerate(ops):
        code = op[0]
        if code in (0x8c, 0x58):
            s = get_string(data, ops, i)
            if s is not None:
                if last_key == 'items':
                    choices.append(s)
                    items_mode = True
                elif items_mode and after_tuple3:
                    choices.append(s)
                if last_key is not None and last_key in TEXT_KEYS:
                    out.append(s)
                    last_key = None
                elif s in KEY_NAMES:
                    last_key = s
                else:
                    last_key = None
                last_string = s
                # collectExtraTexts
                for m in re.finditer(r'_\(\"((?:[^\"\\\\]|\\\\.)*)\"\)', s):
                    txt = m.group(1)
                    if len(txt.strip()) >= 2 and txt not in extra_seen:
                        extra_seen.add(txt)
                        out.append(txt)
            after_tuple3 = False
        elif code in (0x68, 0x6a):
            idx = data[op[1]+1] if code == 0x68 else le32(data, op[1]+1)
            v = memo.get(idx)
            if isinstance(v, str):
                s = v
                if last_key == 'items':
                    choices.append(s)
                    items_mode = True
                elif items_mode and after_tuple3:
                    choices.append(s)
                if last_key is not None and last_key in TEXT_KEYS:
                    out.append(s)
                    last_key = None
                elif s in KEY_NAMES:
                    last_key = s
                else:
                    last_key = None
                last_string = s
                for m in re.finditer(r'_\(\"((?:[^\"\\\\]|\\\\.)*)\"\)', s):
                    txt = m.group(1)
                    if len(txt.strip()) >= 2 and txt not in extra_seen:
                        extra_seen.add(txt)
                        out.append(txt)
            after_tuple3 = False
        elif code in (0x71, 0x72):
            idx = data[op[1]+1] if code == 0x71 else le32(data, op[1]+1)
            if last_string is not None:
                memo[idx] = last_string
        elif code == 0x94:
            if last_string is not None:
                memo[memoTrack] = last_string
            memoTrack += 1
        elif code in (0x75, 0x65, 0x61, 0x73, 0x62, 0x31):
            last_key = None
        elif code == 0x87:
            after_tuple3 = True
    out.extend(choices)
    return out

data = read_slot('assets/x-game/x-phone.rpyc')
texts = extractor_sim(data)
print(f'extractor sim on x-phone.rpyc: {len(texts)} texts')
for t in texts[:30]:
    print(f'  {repr(t[:100])}')

# Now find where "I'm fine, Aine" appears in the ops and what precedes it
target = "I'm fine, Aine. Really."
ops = walk_java(data)
# Find the string op
for i, op in enumerate(ops):
    if op[0] in (0x8c, 0x58):
        s = get_string(data, ops, i)
        if s == target:
            # Look at preceding ops to understand context
            ctx = ops[max(0, i-15):i+2]
            print(f'\nContext around {repr(target)}:')
            for c in ctx:
                ccode = c[0]
                cs = get_string(data, ops, ops.index(c)) if c[0] in (0x8c, 0x58) else None
                desc = f'opcode {hex(ccode)}'
                if cs is not None:
                    desc += f' str={repr(cs[:50])}'
                print(f'  {desc}')
            break
