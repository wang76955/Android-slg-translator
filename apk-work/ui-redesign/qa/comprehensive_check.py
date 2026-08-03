import re

entries = {}
current = None
with open('apk-work/ui-redesign/qa/extracted-texts.txt', encoding='utf-8') as f:
    for line in f:
        raw = line.rstrip('\n')
        if raw.startswith('===E\t'):
            current = raw[5:]
            entries.setdefault(current, [])
        elif current is not None:
            val = raw.replace('\\\\', '\x00').replace('\\n', '\n').replace('\\r', '\r').replace('\x00', '\\')
            entries[current].append(val)

def category(name):
    if '/x-tl/x-slgtranslated/' in name: return 'slgtranslated'
    if '/x-tl/x-chinese/' in name: return 'chinese'
    if '/x-tl/x-german/' in name: return 'german'
    if '/x-tl/x-english/' in name: return 'english'
    return 'original'

# Get corpus
corpus = set()
for name, texts in entries.items():
    if category(name) == 'original':
        corpus.update(texts)

# Get all chinese translation texts
chinese_by_file = {}
for name, texts in entries.items():
    if category(name) == 'chinese':
        chinese_by_file[name] = texts

# Get translated keys from our pickle
import zipfile, zlib
z = zipfile.ZipFile('apk-work/ui-redesign/qa/ewn-audit-src.apk')
raw2 = z.read('assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc')
pos = len(b'RENPY RPC2')
slot = None
while pos + 12 <= len(raw2):
    sid = int.from_bytes(raw2[pos:pos+4], 'little')
    off = int.from_bytes(raw2[pos+4:pos+8], 'little')
    ln = int.from_bytes(raw2[pos+8:pos+12], 'little')
    if sid == 0: break
    if sid == 2:
        slot = zlib.decompress(raw2[off:off+ln])
        break
    pos += 12

translated = set()
i = 0
n = len(slot)
while i < n - 2:
    if slot[i] == 0x8c and slot[i+1] == 3 and slot[i+2:i+5] == b'old':
        j = i + 5
        if j < n and slot[j] == 0x8c:
            ln2 = slot[j+1]
            translated.add(slot[j+2:j+2+ln2].decode('utf-8', errors='replace'))
            i = j + 2 + ln2
            continue
        if j+4 < n and slot[j] == 0x58:
            ln2 = int.from_bytes(slot[j+1:j+5], 'little')
            translated.add(slot[j+5:j+5+ln2].decode('utf-8', errors='replace'))
            i = j + 5 + ln2
            continue
    i += 1

# For each Chinese translation file, count English-only strings not in corpus and not in translated
print(f'{"File":<55} {"Total":>6} {"Eng":>6} {"NotInCorpus":>11} {"NotBoth":>8}')
print('-' * 90)
total_not_both = set()
for name in sorted(chinese_by_file):
    texts = set(chinese_by_file[name])
    # English-only strings (contain 3+ ASCII letters, no CJK)
    english = {s for s in texts if re.search(r'[A-Za-z]{3,}', s) and not re.search(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', s)}
    not_in_corpus = english - corpus
    not_both = not_in_corpus - translated
    total_not_both.update({(name, s) for s in not_both})
    if len(texts) > 0:
        print(f'{name:<55} {len(texts):>6} {len(english):>6} {len(not_in_corpus):>11} {len(not_both):>8}')

print(f'\nTotal unique English strings in Chinese translations but not in corpus AND not translated: {len(set(s for _, s in total_not_both))}')

# Write full list
with open('apk-work/ui-redesign/qa/comprehensive-missing.txt', 'w', encoding='utf-8') as f:
    by_file = {}
    for name, s in total_not_both:
        by_file.setdefault(name, []).append(s)
    for name in sorted(by_file):
        f.write(f'=== {name} ({len(by_file[name])} strings)\n')
        for s in sorted(by_file[name]):
            f.write(repr(s) + '\n')
    f.write(f'\nTotal: {len(set(s for _, s in total_not_both))}\n')
