"""Per-item verification for every candidate missing string.

For each corpus string not matched by an exact translated key, this prints:
  FILE | corpus string (escaped)
  - exact merged old key?        (expected False)
  - exact rpy old key?
  - literal present in merged pickle?  (raw bytes)
  - near-key with newline-vs-backslash-n mismatch (the corruption signature)
  - covered by built-in Chinese?
"""
import importlib.util
import sys
import zipfile
import zlib

sys.path.insert(0, 'apk-work/ui-redesign/qa')
spec = importlib.util.spec_from_file_location('ac', 'apk-work/ui-redesign/qa/audit_coverage.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

entries = m.parse_dump(m.DUMP)
merged_keys = m.merged_old_keys(m.APK)
rpy_keys = m.rpy_old_keys(m.APK)
builtin = set()
for name, texts in entries.items():
    if m.category(name) == 'chinese':
        builtin.update(texts)

# raw merged pickle bytes for literal search
with zipfile.ZipFile(m.APK) as z:
    raw = z.read('assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc')
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

missing = []
for name, texts in entries.items():
    if m.category(name) != 'original':
        continue
    for text in texts:
        if text not in merged_keys and text not in rpy_keys:
            missing.append((name, text))

out = []
for name, text in missing:
    def show(s):
        return repr(s).encode('unicode_escape').decode('ascii')

    nl_form = text.replace('\\n', '\n') if '\\n' in text else None
    backslash_form = text.replace('\n', '\\n') if '\n' in text else None
    near = []
    if nl_form is not None and nl_form in merged_keys:
        near.append('merged-key-real-newline')
    if backslash_form is not None and backslash_form in merged_keys:
        near.append('merged-key-backslash-n')
    out.append(
        'FILE: %s\n  corpus: %s\n  in merged exact: %s | in rpy exact: %s\n'
        '  literal in merged pickle: %s | near-mismatch: %s\n'
        '  builtin chinese: %s\n'
        % (name, show(text), text in merged_keys, text in rpy_keys,
           text.encode('utf-8') in slot, ','.join(near) or '-', text in builtin)
    )

result = '\n'.join(out)
out_path = m.QA / 'per-item-verification.txt'
out_path.write_text(result + '\nTOTAL: %d\n' % len(missing), encoding='utf-8')
print('written', out_path, 'items', len(missing))
