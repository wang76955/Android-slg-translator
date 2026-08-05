# Check which rpyc files generate the largest outputs
import zipfile, zlib, pickletools, io

apk = r'C:\Users\王运\Documents\文件翻译\apk-work\ui-redesign\qa\ewn-audit-patched2.apk'

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

def estimate_output_size(pickle):
    """Estimate total RPYC_STRING output size."""
    total = 0
    count = 0
    buf = io.BytesIO(pickle)
    try:
        ops = list(pickletools.genops(buf))
    except:
        return 0, 0
    for opcode, arg, pos in ops:
        if opcode.name in ('SHORT_BINUNICODE', 'BINUNICODE') and isinstance(arg, str):
            # Each string becomes "RPYC_STRING\t" + escaped + "\n"
            escaped_len = len(arg) * 2 + 14  # rough estimate (worst case all backslashes)
            total += escaped_len
            count += 1
    return total, count

with zipfile.ZipFile(apk) as z:
    all_files = sorted([n for n in z.namelist()
        if (n.startswith('assets/x-game/') or n.startswith('assets/x-renpy/'))
        and n.endswith('.rpyc') and '/x-tl/' not in n])
    
    sizes = []
    for fn in all_files:
        raw = z.read(fn)
        pickle = read_slot(raw, 2)
        if pickle is None:
            pickle = read_slot(raw, 1)
        if pickle is None:
            continue
        size, count = estimate_output_size(pickle)
        sizes.append((fn, size, count))
    
    sizes.sort(key=lambda x: x[1], reverse=True)
    print('Top 10 largest output files:')
    for fn, size, count in sizes[:10]:
        print('  %s: ~%.1f MB, %d strings' % (fn.split('/')[-1], size/1e6, count))
    
    total = sum(s for _, s, _ in sizes)
    print('\nTotal estimated output: %.1f MB' % (total/1e6))
