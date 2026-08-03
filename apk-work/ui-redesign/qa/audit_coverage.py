"""Authoritative translation-coverage audit for the patched APK.

Uses:
- corpus: RpycTextExtractor output for every original rpyc/rpymc entry
  (extracted-texts.txt line protocol).
- translated keys: every "old" string literal in the merged
  x-translations.rpyc pickle PLUS every `old` key parsed from
  tl/slgtranslated/*.rpy sources.
- builtin keys: RpycTextExtractor output for x-tl/x-chinese entries.
"""
import re
import zipfile
import zlib
from pathlib import Path

QA = Path('apk-work/ui-redesign/qa')
APK = QA / 'ewn-audit-src.apk'
DUMP = QA / 'extracted-texts.txt'


def unescape(line):
    """Reverse TextDumpHarness escaping: \\\\ -> \\, \\n -> LF, \\r -> CR."""
    return line.replace('\\\\', '\x00').replace('\\n', '\n').replace('\\r', '\r').replace('\x00', '\\')


def parse_dump(path):
    entries = {}
    current = None
    for raw in path.read_text(encoding='utf-8').splitlines():
        if raw.startswith('===E\t'):
            current = raw[5:]
            entries.setdefault(current, [])
        elif current is not None:
            entries[current].append(unescape(raw))
    return entries


def merged_old_keys(apk_path, entry='assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc'):
    with zipfile.ZipFile(apk_path) as z:
        raw = z.read(entry)
    pos = len(b'RENPY RPC2')
    slot = None
    while pos + 12 <= len(raw):
        sid = int.from_bytes(raw[pos:pos + 4], 'little')
        off = int.from_bytes(raw[pos + 4:pos + 8], 'little')
        ln = int.from_bytes(raw[pos + 8:pos + 12], 'little')
        if sid == 0:
            break
        if sid == 2:
            slot = zlib.decompress(raw[off:off + ln])
            break
        pos += 12
    if slot is None:
        return set()
    keys = set()
    i = 0
    n = len(slot)
    while i < n - 2:
        if slot[i] == 0x8c and slot[i + 1] == 3 and slot[i + 2:i + 5] == b'old':
            j = i + 5
            if j < n and slot[j] == 0x8c:
                ln = slot[j + 1]
                keys.add(slot[j + 2:j + 2 + ln].decode('utf-8', errors='replace'))
                i = j + 2 + ln
                continue
            if j + 4 < n and slot[j] == 0x58:
                ln = int.from_bytes(slot[j + 1:j + 5], 'little')
                keys.add(slot[j + 5:j + 5 + ln].decode('utf-8', errors='replace'))
                i = j + 5 + ln
                continue
        i += 1
    return keys


def rpy_old_keys(apk_path, prefix='tl/slgtranslated/'):
    keys = set()
    with zipfile.ZipFile(apk_path) as z:
        for name in z.namelist():
            if not (name.startswith(prefix) and name.endswith('.rpy')):
                continue
            content = z.read(name).decode('utf-8', errors='replace')
            old = None
            in_block = False
            for line in content.splitlines():
                t = line.strip()
                if t.startswith('translate ') and ' strings:' in t:
                    in_block = True
                    old = None
                    continue
                if not in_block:
                    continue
                m = re.match(r'old\s+"((?:[^"\\]|\\.)*)"', t)
                if m:
                    old = m.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                elif t.startswith('new ') and old is not None:
                    m2 = re.match(r'new\s+"((?:[^"\\]|\\.)*)"', t)
                    if m2:
                        keys.add(old)
                    old = None
    return keys


def category(name):
    if '/x-tl/x-slgtranslated/' in name:
        return 'slgtranslated'
    if '/x-tl/x-chinese/' in name:
        return 'chinese'
    if '/x-tl/x-german/' in name:
        return 'german'
    if '/x-tl/x-english/' in name:
        return 'english'
    return 'original'


def audit(apk_path=APK, dump_path=DUMP):
    entries = parse_dump(dump_path)
    translated = merged_old_keys(apk_path) | rpy_old_keys(apk_path)
    builtin = set()
    for name, texts in entries.items():
        if category(name) == 'chinese':
            builtin.update(texts)
    corpus = {}
    for name, texts in entries.items():
        if category(name) != 'original':
            continue
        corpus[name] = texts
    missing = []
    seen = set()
    for name in sorted(corpus):
        for text in corpus[name]:
            if text not in translated and text not in seen:
                seen.add(text)
                missing.append((name, text))
    return {
        'corpus_total': sum(len(v) for v in corpus.values()),
        'corpus_unique': len(set(t for v in corpus.values() for t in v)),
        'translated_keys': len(translated),
        'builtin_keys': len(builtin),
        'missing': missing,
        'missing_in_builtin': [(n, t) for n, t in missing if t in builtin],
    }


if __name__ == '__main__':
    result = audit()
    print('corpus entries/unique:', result['corpus_total'], result['corpus_unique'])
    print('translated keys:', result['translated_keys'])
    print('builtin keys:', result['builtin_keys'])
    print('missing:', len(result['missing']))
    for name, text in result['missing']:
        print(' ', name, repr(text))
    print('missing covered by builtin chinese:', result['missing_in_builtin'])
