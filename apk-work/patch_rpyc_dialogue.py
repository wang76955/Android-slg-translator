import hashlib
import pathlib
import zlib


dex_path = pathlib.Path(__file__).parent / "extracted" / "classes6.dex"
data = bytearray(dex_path.read_bytes())

patches = {
    # Ren'Py RPC2 slot 1 is metadata; dialogue/AST strings are stored in slot 2.
    # Seed slotPos at magicLength + 12 so parsing starts from the second record.
    0xA0D2: (bytes.fromhex("6200210021000102"), bytes.fromhex("13000a00d802000c")),
    # 0x42 (BINBYTES) is not a string opcode in these protocol-2 Ren'Py
    # pickles. Treat it as an ordinary byte; otherwise arbitrary payload data
    # is interpreted as a huge length and the scanner jumps to EOF.
    0xA628: (bytes.fromhex("a5000000"), bytes.fromhex("03000000")),
    # 0x54 (BINSTRING) has the same unsafe false-positive behavior when the
    # byte occurs inside object payloads. This game stores text with X/U/8c.
    0xA630: (bytes.fromhex("a5000000"), bytes.fromhex("03000000")),
    # If a four-byte string candidate fails bounds/UTF-8 validation, advance
    # one byte instead of trusting its bogus length and jumping out of data.
    0xA5C6: (bytes.fromhex("38040800"), bytes.fromhex("38041100")),
    # Restore the parser's original 1,000,000-byte pickle string ceiling.
    0xA1EA: (bytes.fromhex("140100200000"), bytes.fromhex("140140420f00")),
    # RenPyRpycParser.extractPickleStrings: bypass addVisible/normalization and
    # retain each decoded pickle string for the JS dialogue classifier.
    0xA4B4: (bytes.fromhex("7030f3000602"), bytes.fromhex("6e2058012000")),
    0xA504: (bytes.fromhex("7030f3000502"), bytes.fromhex("6e2058012000")),
    0xA58C: (bytes.fromhex("7030f3000803"), bytes.fromhex("6e2058013000")),
    0xA5D0: (bytes.fromhex("7030f3000604"), bytes.fromhex("6e2058014000")),
}

for offset, (old, new) in patches.items():
    actual = bytes(data[offset : offset + len(old)])
    if actual == new:
        continue
    if actual != old:
        raise RuntimeError(
            f"Unexpected bytes at 0x{offset:x}: {actual.hex()} (expected {old.hex()})"
        )
    data[offset : offset + len(old)] = new

# DEX SHA-1 signature and Adler-32 checksum cover the modified payload.
data[12:32] = hashlib.sha1(data[32:]).digest()
data[8:12] = (zlib.adler32(data[12:]) & 0xFFFFFFFF).to_bytes(4, "little")
dex_path.write_bytes(data)
print("Patched RenPy dialogue extraction call sites and refreshed DEX checksums")
