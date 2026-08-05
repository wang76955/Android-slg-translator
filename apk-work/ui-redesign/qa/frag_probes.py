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

data = read_slot('assets/x-game/x-screens.rpyc')
print('x-screens.rpyc pickle:', len(data))

# Search fragments
for probe in ['Music', 'Volume', 'Text Speed', 'Text', 'Auto-Forward', 'Forward', 'ROLLBACK SIDE', 'Rollback']:
    pb = probe.encode('utf-8')
    positions = []
    start = 0
    while True:
        idx = data.find(pb, start)
        if idx < 0: break
        positions.append(idx)
        start = idx + 1
    print(f'{repr(probe)}: {len(positions)} occurrences')
    for idx in positions[:3]:
        ctx = data[max(0,idx-50):idx+len(pb)+50]
        print(f'    @{idx}: {repr(ctx.decode("utf-8", errors="replace"))}')
