import re
import os
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import struct
import pickle
import pickletools
from pathlib import Path
import io
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[2]
FAST_SCAN = ROOT / "apk-work" / "native-fast-scan"
SCANNER = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java"
FONT_SUPPORT = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyFontSupport.java"
PICKLE_WRITER = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycPickleWriter.java"
DIALOGUE_TRANSLATION = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyDialogueTranslation.java"
COMPATIBILITY_REPORT = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyCompatibilityReport.java"
PREFLIGHT = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyPreflight.java"
INSTALLED_APPS = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledAppSource.java"
INSTALLED_APK_SET = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledApkSet.java"
BUILDER = FAST_SCAN / "build_fast_scanner.py"
WORKSHOP_BUILDER = ROOT / "apk-work" / "ui-redesign" / "build_workshop_apk.py"
COMPATIBILITY_MATRIX = ROOT / "docs" / "qa" / "renpy-compatibility-matrix.md"
RELEASE_CHECKLIST = ROOT / "docs" / "qa" / "renpy-release-checklist.md"
GENERATED = FAST_SCAN / "generated"
DEXDUMP = ROOT / ".tools" / "android-15" / "dexdump.exe"
CAPACITOR_DEX = ROOT / "apk-work" / "extracted" / "classes3.dex"
JAVA_HOME = ROOT / ".tools" / "jdk-17" / "jdk-17.0.19+10"
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"


def canonical_workshop_asset(name: str, digest: str) -> Path:
    candidates = (
        ROOT / "apk-work" / "extracted" / "assets" / "public" / "assets" / name,
        ROOT / "_trash" / "uncertain" / "extracted" / "assets" / "public" / "assets" / name,
    )
    for candidate in candidates:
        if candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest() == digest:
            return candidate
    raise AssertionError(f"canonical workshop asset not found: {name}")

THIRD_PARTY = FAST_SCAN / "third-party"

_THIRD_PARTY_CLASSPATH = None

def third_party_classpath() -> str:
    """Return a javac classpath mirroring build_fast_scanner.py."""
    global _THIRD_PARTY_CLASSPATH
    if _THIRD_PARTY_CLASSPATH:
        return _THIRD_PARTY_CLASSPATH
    root = Path(tempfile.mkdtemp(prefix="slg-third-party-classpath-"))
    entries = []
    for aar in sorted(THIRD_PARTY.glob("*.aar")):
        out = root / aar.stem
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(aar) as archive:
            if "classes.jar" not in archive.namelist():
                continue
            with zipfile.ZipFile(io.BytesIO(archive.read("classes.jar"))) as jar:
                for name in jar.namelist():
                    if name.endswith(".class") and not name.startswith(("kotlin/", "kotlinx/", "META-INF/")):
                        target = out / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(jar.read(name))
        if any(out.rglob("*.class")):
            entries.append(str(out))
    entries.extend(str(jar) for jar in sorted(THIRD_PARTY.glob("*.jar")))
    _THIRD_PARTY_CLASSPATH = os.pathsep.join(entries)
    return _THIRD_PARTY_CLASSPATH

RPC2_MAGIC = b"RENPY RPC2"


def rpc2_slots(data: bytes):
    pos = len(RPC2_MAGIC)
    while pos + 12 <= len(data):
        slot_id, offset, length = struct.unpack_from("<III", data, pos)
        if slot_id == 0:
            break
        yield slot_id, offset, length
        pos += 12


# Frozen from HEAD^ (before Task 13) TranslationCompiler.buildPickle for:
# language=slgtranslated, filename=game/t.rpy, version=17, key=fixture-key,
# pairs=[("Hello", "你好")]. Do not derive this fixture from the new writer.
MODERN_PICKLE_GOLDEN_B64 = (
    "gAJ9KIwHdmVyc2lvbksRjANrZXmMC2ZpeHR1cmUta2V5jBVkZWZlcnJlZF9wYXJzZV9lcnJvcnOMC2NvbGxlY3Rpb25z"
    "jAtkZWZhdWx0ZGljdJOMCGJ1aWx0aW5zjARsaXN0k4VSdV0ojAlyZW5weS5hc3SMBEluaXSTKYFOfSiMCmxpbmVudW1i"
    "ZXJLAYwIZmlsZW5hbWWMCmdhbWUvdC5ycHmMBG5hbWWMCmdhbWUvdC5ycHlKLIJaak2IBYeMBG5leHROjAVibG9ja10o"
    "jAlyZW5weS5hc3SMD1RyYW5zbGF0ZVN0cmluZ5MpgU59KIwKbGluZW51bWJlcksDjAhmaWxlbmFtZYwKZ2FtZS90LnJweYwE"
    "bmFtZYwKZ2FtZS90LnJweUosglpqTYkFh4wEbmV4dE6MCGxhbmd1YWdljA1zbGd0cmFuc2xhdGVkjANvbGSMBUhlbGxvjANuZXeMBuS9"
    "oOWlvYwGbmV3bG9jjApnYW1lL3QucnB5SwOGdYZiZYwIcHJpb3JpdHlLAHWGYowJcmVucHkuYXN0jAZSZXR1cm6TKYFOfSiMCmxpbmVudW1i"
    "ZXJLBYwIZmlsZW5hbWWMCmdhbWUvdC5ycHmMCmV4cHJlc3Npb25OjARuYW1ljApnYW1lL3QucnB5SiyCWmpNigWHjARuZXh0TnWGYmWGLg=="
)

def pickle_short(value: str) -> bytes:
    payload = value.encode("utf-8")
    if len(payload) > 255:
        raise AssertionError("fixture strings must be short")
    return b"\x8c" + bytes([len(payload)]) + payload

def pickle_int1(value: int) -> bytes:
    return b"\x4b" + bytes([value])

def build_menu_fixture_rpyc() -> bytes:
    """Builds a minimal RPC2 rpyc whose pickle contains a Menu node with
    items labels, dialogue and an attr key that must be filtered."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what") + pickle_short("Hello, world!")
    # Screen text marked with _("...") and a Character("Name") definition
    # (inside a PyCode-style source payload).
    p += pickle_short("source") + pickle_short('_("Start")')
    p += pickle_short("source") + pickle_short('Character("Sky", color = "#fff")')
    p += pickle_short("items")
    # Screen text marked with _("...") and a Character("Name") definition
    # (inside a PyCode-style source payload).
    p += b"\x5d\x94\x28"  # EMPTY_LIST MEMOIZE MARK
    for label, money in (("First choice", False), ("Second{#x}", False),
                         ("$1100", True), ("Fine", False)):
        p += pickle_short(label) + b"\x94"  # label MEMOIZE
        p += b"\x4e"  # NONE condition
        p += b"\x5d\x28\x65"  # EMPTY_LIST MARK APPENDS (empty block)
        p += b"\x87\x94"  # TUPLE3 MEMOIZE
    p += pickle_short("statement_start")  # must be filtered (attr key)
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    pickle_bytes = bytes(p)
    import zlib
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16



def build_underscore_menu_fixture_rpyc() -> bytes:
    """Builds a minimal RPC2 rpyc whose pickle stores language buttons as
    _("label") payloads after their Language(...) actions, matching the
    compiled screen layout used by Mayfly."""
    # Structural fixture mirrors compiled Ren'Py screens: every button is an
    # SLDisplayable NEWOBJ with a (NONE, state_dict) BUILD and one APPENDS
    # that closes the language vbox children list.
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"ctest\nButton\n" + b"\x71\x01"  # GLOBAL Button, memo 1
    p += b"\x5d\x71\x02"  # EMPTY_LIST children, memo 2
    p += b"\x28"  # MARK for APPENDS
    memo = 100
    for lang, label in (("English", "英语"), ("russian", "俄语"),
                        ("None", "简体中文"), ("TraditionalChinese", "繁體中文")):
        p += b"\x68\x01\x29\x81"  # BINGET 1 EMPTY_TUPLE NEWOBJ
        p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x4e\x7d"  # NONE EMPTY_DICT state
        p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x28"  # MARK for SETITEMS
        action = 'Language("%s")' % lang if lang != "None" else "Language(None)"
        for key, value in (("language", action), ("label", '_("%s")' % label)):
            p += pickle_short(key)
            p += b"\x72" + struct.pack("<I", memo); memo += 1
            p += pickle_short(value)
            p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x75\x86"  # SETITEMS TUPLE2
        p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x62"  # BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    import zlib
    slot = zlib.compress(bytes(p))
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_default_language_menu_fixture_rpyc() -> bytes:
    """Build the two-entry language menu shape used by the target game.

    The default action is serialized as ``Language(None)`` and the labels are
    parenthesized string expressions such as ``("English")``.
    """
    p = bytearray()
    p += b"\x80\x02"
    p += b"ctest\nButton\n" + b"\x71\x01"
    p += b"\x5d\x71\x02\x28"
    memo = 100
    for lang, label in ((None, "English"), ("chinese", "\u7b80\u4f53\u4e2d\u6587")):
        p += b"\x68\x01\x29\x81"
        p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x4e\x7d"
        p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x28"
        action = "Language(None)" if lang is None else 'Language("%s")' % lang
        for key, value in (("language", action), ("label", '("%s")' % label)):
            p += pickle_short(key)
            p += b"\x72" + struct.pack("<I", memo); memo += 1
            p += pickle_short(value)
            p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x75\x86"
        p += b"\x72" + struct.pack("<I", memo); memo += 1
        p += b"\x62"
    p += b"\x65."
    import zlib
    slot = zlib.compress(bytes(p))
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_source_call_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle embeds source strings containing
    message-style and Ren'Py preference-style function calls. The extractor
    must pull the string-literal arguments (phone message text, preference
    labels) while ignoring variable arguments, empty strings and paths."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what") + pickle_short("Hello, world!")
    # Source payloads: message-style calls (phone) and Ren'Py preference calls.
    p += pickle_short("source") + pickle_short('send_phone_message("Aine", "Hello there.", "aine_dm")')
    p += pickle_short("source") + pickle_short('send_phone_message(sender, message_text, channel_name)')
    p += pickle_short("source") + pickle_short('send_phone_message("Aine", "images/ch2ep1_1042.jpg", "aine_dm", 2)')
    p += pickle_short("source") + pickle_short("_VolumePreference(u\"Music Volume\", 'music', 'config.has_music')")
    p += pickle_short("source") + pickle_short("_SliderPreference(u'Auto-Forward Time', \"afm_time\", 40, 'config.has_afm')")
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16



def build_markup_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle contains Say nodes whose `what`
    values include Ren'Py markup tags with '/' characters ({/i}, {/b}).
    The extractor must NOT treat these as file paths."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what")
    p += pickle_short("I like you a lot. You are good at causing some {i}activity{/i} inside me.")
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    # Second Say with bold markup and a closing slash
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(2)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what")
    p += pickle_short("No, {b}kill{/b} her...")
    p += b"\x75\x86\x62"
    # Third Say with a real path (must be filtered)
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(3)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what")
    p += pickle_short("images/scenes/ch1ep1_001.png")
    p += b"\x75\x86\x62"
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    pickle_bytes = bytes(p)
    import zlib
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16

def build_translate_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle contains a TranslateString node with
    old/new keys plus a Say node with a translated what. The old-only extractor
    must return only the English old key, never the translated what/new."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/tl/chinese/fixture.rpy")
    p += pickle_short("what") + pickle_short("English dialogue")
    p += pickle_short("old") + pickle_short("English original")
    p += pickle_short("new") + pickle_short("\u4e2d\u6587\u539f\u6587")
    p += pickle_short("text") + pickle_short("English screen text")
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_rpc2_fixture_with_zlib_padding() -> bytes:
    """Return a legal RPC2 fixture whose selected zlib slot has alignment bytes."""
    raw = bytearray(build_markup_fixture_rpyc())
    table_start = len(RPC2_MAGIC)
    second_entry = table_start + 12
    slot_offset = int.from_bytes(raw[second_entry + 4:second_entry + 8], "little")
    slot_length = int.from_bytes(raw[second_entry + 8:second_entry + 12], "little")
    slot_end = slot_offset + slot_length
    raw[second_entry + 8:second_entry + 12] = struct.pack("<I", slot_length + 2)
    raw[slot_end:slot_end] = b"\x00\x00"
    return bytes(raw)


def build_structured_records_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle mixes dialogue, menu labels, static
    UI text, Character() names, and translate old/new keys for the structured
    extractor contract."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"  # STACK_GLOBAL
    p += b"\x29\x81\x4e\x7d\x28"  # EMPTY_TUPLE NEWOBJ NONE EMPTY_DICT MARK
    p += pickle_short("linenumber") + pickle_int1(7)
    p += pickle_short("filename") + pickle_short("game/chapter1.rpy")
    p += pickle_short("who") + pickle_short("Narrator")
    p += pickle_short("what") + pickle_short("Hello, world!")
    p += pickle_short("what") + pickle_short("A quiet line.")
    p += pickle_short("who") + pickle_short("Narrator")
    p += pickle_short("caption") + pickle_short("A menu caption.")
    p += pickle_short("what") + pickle_short("A structurally unowned line.")
    p += pickle_short("what") + pickle_short("Literal _('not a source call')")
    p += pickle_short("old") + pickle_short("Save{#menu}")
    p += pickle_short("new") + pickle_short("\u4fdd\u5b58")
    p += pickle_short("source") + pickle_short('_("Start")')
    p += pickle_short("source") + pickle_short('_("Repeat me")')
    p += pickle_short("source") + pickle_short('_("Repeat me")')
    p += pickle_short("source") + pickle_short('_("Shared hint")')
    p += pickle_short("source") + pickle_short('Character("Sky", color = "#fff")')
    p += pickle_short("source") + pickle_short('send_phone_message("Aine", "Shared hint", "aine_dm")')
    p += pickle_short("items")
    p += b"\x5d\x94\x28"  # EMPTY_LIST MEMOIZE MARK
    for label in ("First choice", "Second{#x}"):
        p += pickle_short(label) + b"\x94"
        p += b"\x4e"
        p += b"\x5d\x28\x65"
        p += b"\x87\x94"
    p += b"\x75\x86\x62"  # SETITEMS TUPLE2 BUILD
    p += b"\x65"  # APPENDS
    p += b"."  # STOP
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_adjacent_dialogue_speaker_fixture_rpyc() -> bytes:
    """Two independent Say nodes: only the first has a speaker."""
    p = bytearray()
    p += b"\x80\x02\x5d\x28"  # PROTO 2, EMPTY_LIST, MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(31)
    p += pickle_short("filename") + pickle_short("game/speakers.rpy")
    p += pickle_short("who") + pickle_short("alice")
    p += pickle_short("what") + pickle_short("First adjacent line")
    p += b"\x75\x86\x62"
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(32)
    p += pickle_short("filename") + pickle_short("game/speakers.rpy")
    p += pickle_short("what") + pickle_short("Second adjacent line")
    p += b"\x75\x86\x62\x65."
    import zlib
    slot = zlib.compress(bytes(p))
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot


def build_dialogue_id_fixture_rpyc() -> bytes:
    """Two TranslateSay nodes share old text but retain different IDs."""
    p = bytearray()
    p += b"\x80\x02\x5d\x28"  # PROTO 2, EMPTY_LIST, MARK
    for identifier, speaker in (("dialogue-a", "Alice"), ("dialogue-b", "Bob")):
        p += pickle_short("renpy.ast") + pickle_short("TranslateSay") + b"\x93"
        p += b"\x29\x81\x4e\x7d\x28"
        p += pickle_short("linenumber") + pickle_int1(10 if identifier.endswith("a") else 20)
        p += pickle_short("filename") + pickle_short("game/dialogue.rpy")
        p += pickle_short("identifier") + pickle_short(identifier)
        p += pickle_short("who") + pickle_short(speaker)
        p += pickle_short("what") + pickle_short("Fine.")
        p += pickle_short("new") + pickle_short("unused source translation")
        p += b"\x75\x86\x62"  # SETITEMS, TUPLE2, BUILD
    p += b"\x65."
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot


def build_official_marked_string_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle embeds source payloads using the
    official Ren'Py marked-string helper forms."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("PyCode") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("filename") + pickle_short("game/official_marked_strings.rpy")
    p += pickle_short("line") + pickle_int1(1)
    p += pickle_short("source") + pickle_short("_('single')")
    p += pickle_short("source") + pickle_short('__("double")')
    p += pickle_short("source") + pickle_short("___('''multi\\nline''')")
    p += pickle_short("source") + pickle_short('_(r"raw text")')
    p += pickle_short("source") + pickle_short('_p("menu-context", "Continue")')
    p += b"\x75\x86\x62"
    p += b"\x65"
    p += b"."
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_marked_string_exact_key_fixture_rpyc() -> bytes:
    """Builds an RPC2 rpyc whose pickle contains exact-key and dynamic marked
    string forms that must not be collapsed or misreported as certain."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("PyCode") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("filename") + pickle_short("game/exact_keys.rpy")
    p += pickle_short("line") + pickle_int1(1)
    p += pickle_short("source") + pickle_short('_("Save{#slot}")')
    p += pickle_short("source") + pickle_short('_("Save{#menu}")')
    p += pickle_short("source") + pickle_short("_(dynamic_label)")
    p += pickle_short("source") + pickle_short('_p("menu-context", dynamic_label)')
    p += b"\x75\x86\x62"
    p += b"\x65"
    p += b"."
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_marked_string_prefix_boundary_fixture_rpyc() -> bytes:
    """Builds marked strings that exercise prefix legality and quote bounds."""
    p = bytearray()
    p += b"\x80\x02"  # PROTO 2
    p += b"\x5d"  # EMPTY_LIST
    p += b"\x28"  # MARK
    p += pickle_short("renpy.ast") + pickle_short("PyCode") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("filename") + pickle_short("game/prefix_boundaries.rpy")
    p += pickle_short("line") + pickle_int1(1)
    p += pickle_short("source") + pickle_short('_(u"unicode")')
    p += pickle_short("source") + pickle_short('_(b"binary")')
    p += pickle_short("source") + pickle_short('_(ur"unicode raw")')
    p += pickle_short("source") + pickle_short('_(rb"binary raw")')
    p += pickle_short("source") + pickle_short("_('''single triple''')")
    p += pickle_short("source") + pickle_short('_("""double triple""")')
    p += pickle_short("source") + pickle_short('_("""first""")_("after")')
    p += pickle_short("source") + pickle_short("\"\"\"literal _('not a call')\"\"\"")
    p += pickle_short("source") + pickle_short('_(ub"invalid prefix")')
    p += pickle_short("source") + pickle_short("UserStatement(dynamic_statement)")
    p += b"\x75\x86\x62"
    p += b"\x65"
    p += b"."
    import zlib
    pickle_bytes = bytes(p)
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_template_meta_fixture(version: int, key: str) -> bytes:
    p = bytearray(b"\x80\x02\x7d\x28")
    p += pickle_short("version") + pickle_int1(version)
    p += pickle_short("key") + pickle_short(key)
    p += b"\x75\x2e"  # SETITEMS STOP
    import zlib
    slot = zlib.compress(bytes(p))
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_template_meta_negative_length_fixture(version: int, key: str) -> bytes:
    p = bytearray(b"\x80\x02\x7d\x28")
    p += pickle_short("version") + pickle_int1(version)
    p += pickle_short("key") + pickle_short(key)
    # A valid BINSTRING may contain 0x58 followed by four bytes whose signed
    # little-endian value is negative. Metadata scanning must skip its payload
    # instead of misreading it as a BINUNICODE opcode.
    payload = b"\x58\x68\x45\x23\x81\x00"
    p += b"\x54" + struct.pack("<I", len(payload)) + payload
    p += b"\x75\x2e"  # SETITEMS STOP
    import zlib
    slot = zlib.compress(bytes(p))
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_rpa3_fixture(key: int = 0x42424242, entries=None) -> bytes:
    import pickle
    import zlib
    if entries is None:
        content = build_menu_fixture_rpyc()
        entries = (("game/chapter1.rpyc", content), ("game/notes.txt", b"ignore"))
    header_len = 34
    body = bytearray()
    index = {}
    for name, data in entries:
        body += b"Made with Ren'Py."
        offset = header_len + len(body)
        index[name] = [(offset ^ key, len(data) ^ key, b"")]
        body += data
    index_offset = header_len + len(body)
    index_bytes = zlib.compress(pickle.dumps(index, protocol=2))
    return b"RPA-3.0 %016x %08x\n" % (index_offset, key) + bytes(body) + index_bytes


def build_rpa2_fixture() -> bytes:
    import pickle
    import zlib
    content = build_menu_fixture_rpyc()
    header_len = 25
    body = bytearray()
    index = {}
    for name, data in (("game/chapter1.rpyc", content), ("game/notes.txt", b"ignore")):
        body += b"Made with Ren'Py."
        offset = header_len + len(body)
        index[name] = [(offset, len(data))]
        body += data
    index_offset = header_len + len(body)
    index_bytes = zlib.compress(pickle.dumps(index, protocol=2))
    return b"RPA-2.0 %016x\n" % index_offset + bytes(body) + index_bytes


def build_rpa1_fixture():
    import pickle
    import zlib
    content = build_menu_fixture_rpyc()
    body = bytearray()
    index = {}
    for name, data in (("game/chapter1.rpyc", content), ("game/notes.txt", b"ignore")):
        body += b"Made with Ren'Py."
        offset = len(body)
        index[name] = [(offset, len(data))]
        body += data
    rpi = zlib.compress(pickle.dumps(index, protocol=2))
    return rpi, bytes(body)


def build_legacy_rpyc_fixture() -> bytes:
    import zlib
    p = bytearray()
    p += b"\x80\x02"
    p += b"\x5d"
    p += b"\x28"
    p += pickle_short("renpy.ast") + pickle_short("Menu") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("linenumber") + pickle_int1(1)
    p += pickle_short("filename") + pickle_short("game/fixture.rpy")
    p += pickle_short("what") + pickle_short("Hello, world!")
    p += pickle_short("items")
    p += b"\x5d\x94\x28"
    for label, money in (("First choice", False), ("$1100", True)):
        p += pickle_short(label) + b"\x94"
        p += b"\x4e"
        p += b"\x5d\x28\x65"
        p += b"\x87\x94"
    p += b"\x75\x86\x62"
    p += b"\x65"
    p += b"."
    return zlib.compress(bytes(p))


def build_compatibility_rpc2_fixture() -> bytes:
    return wrap_rpc2(__import__("base64").b64decode(MODERN_PICKLE_GOLDEN_B64))


def wrap_rpc2(pickle_bytes: bytes) -> bytes:
    import zlib
    slot = zlib.compress(pickle_bytes)
    table = bytearray()
    data_start = len(RPC2_MAGIC) + 3 * 12
    for slot_id in (1, 2):
        table += struct.pack("<III", slot_id, data_start, len(slot))
        data_start += len(slot)
    table += struct.pack("<III", 0, 0, 0)
    return RPC2_MAGIC + bytes(table) + slot + slot + b"\x00" * 16


def build_compatibility_legacy_fixture() -> bytes:
    import zlib
    p = bytearray(b"\x80\x02c__builtin__\nlist\n")
    p += pickle_short("what") + pickle_short("Hello, world!") + b"\x2e"
    return zlib.compress(bytes(p))


def build_compatibility_legacy_engine_fixture() -> bytes:
    """A minimal old Ren'Py template shape with the standard AST roots."""
    import zlib
    p = bytearray(b"\x80\x02\x7d\x28")
    p += pickle_short("version") + b"\x4b\x01"
    p += pickle_short("key") + pickle_short("unlocked")
    p += pickle_short("deferred_parse_errors")
    for module, name in (
        ("collections", "defaultdict"),
        ("__builtin__", "list"),
    ):
        p += b"c" + module.encode("ascii") + b"\n" + name.encode("ascii") + b"\n"
    p += b"\x85\x52\x75\x5d\x28"
    for module, name in (("renpy.ast", "Init"), ("renpy.ast", "Return")):
        p += b"c" + module.encode("ascii") + b"\n" + name.encode("ascii") + b"\n"
    p += b"\x2e"
    return zlib.compress(bytes(p))


def build_compatibility_unknown_fixture() -> bytes:
    import zlib
    p = bytearray(b"\x80\x05cmystery\nThing\n.")
    return zlib.compress(bytes(p))


def build_modern_global_envelope_fixture() -> bytes:
    p = bytearray(b"\x80\x02\x7d\x28")
    p += pickle_short("version") + pickle_int1(17)
    p += pickle_short("key") + pickle_short("fixture-key")
    p += pickle_short("deferred_parse_errors")
    p += b"cbuiltins\nlist\n"
    p += b"\x75"
    p += b"crenpy.ast\nInit\n"
    p += b"\x86."
    return wrap_rpc2(bytes(p))


def build_modern_bare_builtins_fixture() -> bytes:
    return wrap_rpc2(
        b"\x80\x05" + pickle_short("builtins") + pickle_short("list") + b"\x93."
    )


def build_modern_decoy_fields_fixture() -> bytes:
    p = bytearray(b"\x80\x05\x5d\x28")
    p += pickle_short("builtins") + pickle_short("list") + b"\x93"
    for value in ("version", "key", "deferred_parse_errors", "renpy.ast"):
        p += pickle_short(value)
    p += b"\x65."
    return wrap_rpc2(bytes(p))


def build_modern_nested_three_key_fixture() -> bytes:
    p = bytearray(b"\x80\x05\x7d")
    p += b"\x7d\x28"
    p += pickle_short("version") + pickle_int1(17)
    p += pickle_short("key") + pickle_short("fixture-key")
    p += pickle_short("deferred_parse_errors")
    p += pickle_short("builtins") + pickle_short("list") + b"\x93"
    p += b"\x75"
    p += pickle_short("renpy.ast") + pickle_short("Init") + b"\x93"
    p += b"\x87."
    return wrap_rpc2(bytes(p))


def build_modern_pseudo_stack_global_fixture() -> bytes:
    p = bytearray(b"\x80\x05\x7d\x28")
    p += pickle_short("version") + pickle_int1(17)
    p += pickle_short("key") + pickle_short("fixture-key")
    p += pickle_short("deferred_parse_errors")
    p += pickle_short("builtins") + pickle_short("list") + b"\x93"
    p += b"\x75"
    p += pickle_short("renpy.ast") + b"\x4e\x93"
    p += b"\x86."
    return wrap_rpc2(bytes(p))


def build_modern_frame_collision_fixture() -> bytes:
    """A valid modern envelope whose FRAME (0x95) 8-byte length has a low byte
    that collides with a pickle payload opcode (0x8e BINBYTES8). Real 8.4 files
    hit this whenever the deflated script's frame length ends in 0x8e/0x8d/0x96;
    the old global-name scan misread the length bytes as a huge payload and
    bailed out, misclassifying the file as UNKNOWN. The scan must skip FRAME."""
    body = bytearray(b"\x7d\x28")
    body += pickle_short("version") + pickle_int1(17)
    body += pickle_short("key") + pickle_short("fixture-key")
    body += pickle_short("deferred_parse_errors")
    body += pickle_short("builtins") + pickle_short("list") + b"\x93"
    body += b"\x75"
    body += pickle_short("renpy.ast") + pickle_short("Init") + b"\x93"
    closing = b"\x86\x2e"                # TUPLE2 (envelope, init), STOP
    pad = (0x8e - len(body) - len(closing)) % 256
    body += b"\x94" * pad + closing      # MEMOIZE no-ops pad to the collision
    assert len(body) % 256 == 0x8e
    p = b"\x80\x05\x95" + struct.pack("<Q", len(body)) + bytes(body)
    return wrap_rpc2(p)


def build_modern_revertable_dict_fixture() -> bytes:
    """Modern envelope whose payload reproduces the real 8.4 dict-subclass
    serialization: a Ren'Py RevertableDict is pickled as a NEWOBJ instance
    whose items are written with SETITEM (0x73) and SETITEMS (0x75) applied
    directly to the OBJECT. The structural verifier must accept OBJECT
    targets there (dict-subclass instances are legitimate targets), not fail
    with invalid_setitem or setitems_without_dict."""
    p = bytearray(b"\x80\x05\x7d\x28")
    p += pickle_short("version") + pickle_int1(17)
    p += pickle_short("key") + pickle_short("fixture-key")
    p += pickle_short("deferred_parse_errors")
    p += pickle_short("builtins") + pickle_short("list") + b"\x93"
    p += b"\x75"
    p += pickle_short("renpy.ast") + pickle_short("Init") + b"\x93"
    p += pickle_short("renpy.revertable") + pickle_short("RevertableDict") + b"\x93"
    p += b"\x29\x81"                     # EMPTY_TUPLE, NEWOBJ -> OBJECT instance
    p += pickle_short("volume") + pickle_short("1.0")
    p += b"\x73"                         # SETITEM directly on the OBJECT
    p += b"\x28"                         # MARK
    p += pickle_short("channel") + b"\x4e"
    p += b"\x75"                         # SETITEMS directly on the OBJECT
    p += b"\x86\x86\x2e"
    return wrap_rpc2(bytes(p))


def build_84_default_omission_fixture_rpyc() -> bytes:
    """Simulates the 8.4 default-omission AST shape: a Say node whose
    interact/attributes/etc. default fields are omitted, keeping only
    who/what/next. who=None mirrors a real narration line; the extractor
    must not let that None desynchronize the what field."""
    p = bytearray(b"\x80\x02\x7d\x28")   # PROTO 2, EMPTY_DICT, MARK
    p += pickle_short("version") + pickle_int1(123)
    p += pickle_short("key") + pickle_short("fixture-key")
    p += pickle_short("deferred_parse_errors")
    p += b"cbuiltins\nlist\n"
    p += b"\x75"                          # SETITEMS -> three-key envelope
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"          # NEWOBJ + state dict
    p += pickle_short("who") + b"\x4e"    # who=None (narration)
    p += pickle_short("what") + pickle_short("省略默认字段后的对话")
    p += pickle_short("next") + b"\x4e"   # next=None
    p += b"\x75\x86\x62"                  # SETITEMS, TUPLE2, BUILD
    p += b"\x86."                         # TUPLE2 (envelope, say) STOP
    return wrap_rpc2(bytes(p))


# Long enough that a protocol-4 pickler emits it as BINUNICODE8, not
# SHORT_BINUNICODE. Shared by the fixture builder and the harness assertion.
DEEP_PROTO45_LONG_WHAT = "深层载荷对话。" * 60


def build_deep_proto45_fixture_rpyc() -> bytes:
    """Protocol-4 deep payload: a FRAME frame, a Say whose long what is a
    BINUNICODE8 string, and a PyCode node whose source is a BYTEARRAY8. The
    walker/extractor must stay synchronized through all three payload kinds."""
    long_what = DEEP_PROTO45_LONG_WHAT.encode("utf-8")
    p = bytearray(b"\x80\x04\x95")        # PROTO 4, FRAME (8-byte length patched below)
    p += b"\x00" * 8
    p += b"\x7d\x28"                      # EMPTY_DICT MARK
    p += pickle_short("version") + pickle_int1(17)
    p += pickle_short("key") + pickle_short("fixture-key")
    p += pickle_short("deferred_parse_errors")
    p += b"cbuiltins\nlist\n"
    p += b"\x75"                          # SETITEMS -> three-key envelope
    p += b"\x5d\x28"                      # ast EMPTY_LIST MARK
    p += pickle_short("renpy.ast") + pickle_short("Say") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"          # NEWOBJ + state dict
    p += pickle_short("who") + b"\x4e"
    p += pickle_short("what")
    p += b"\x8d" + struct.pack("<Q", len(long_what)) + long_what  # BINUNICODE8
    p += pickle_short("next") + b"\x4e"
    p += b"\x75\x86\x62"
    p += pickle_short("renpy.ast") + pickle_short("PyCode") + b"\x93"
    p += b"\x29\x81\x4e\x7d\x28"
    p += pickle_short("filename") + pickle_short("game/deep.rpy")
    p += pickle_short("line") + pickle_int1(1)
    deep_bytes = b"\x00" * 300
    p += pickle_short("source")
    p += b"\x96" + struct.pack("<Q", len(deep_bytes)) + deep_bytes  # BYTEARRAY8
    p += b"\x75\x86\x62"                  # SETITEMS, TUPLE2, BUILD
    p += b"\x65"                          # APPENDS -> ast list
    p += b"\x86."                         # TUPLE2 (envelope, ast) STOP
    frame_len = len(p) - 11               # after PROTO(2) + FRAME opcode(1) + length(8)
    p[3:11] = struct.pack("<Q", frame_len)
    return wrap_rpc2(bytes(p))


def java_block_after(source, marker):
    start = source.index(marker)
    opening = source.index("{", start + len(marker))
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"unterminated Java block after {marker!r}")


def write_split_apk(path: Path, entries):
    """Create a small independent APK-shaped ZIP for split-set contracts."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


class TestGlossary(unittest.TestCase):
    def _run_java(self, class_name: str, source: str):
        if class_name == "GlossaryValidatorHarness":
            stubs = []
            native_sources = [
                FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyTextValidator.java",
                FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyGlossaryValidator.java",
            ]
        else:
            stub_names = (
                "android/content/Context.java",
                "android/content/ContentResolver.java",
                "android/content/ContentValues.java",
                "android/content/Intent.java",
                "android/content/IntentSender.java",
                "android/content/BroadcastReceiver.java",
                "android/content/IntentFilter.java",
                "android/content/pm/PackageManager.java",
                "android/content/pm/ResolveInfo.java",
                "android/content/pm/ApplicationInfo.java",
                "android/content/pm/ActivityInfo.java",
                "android/content/pm/PackageInstaller.java",
                "android/net/Uri.java",
                "android/os/Build.java",
                "android/os/Environment.java",
                "android/os/ParcelFileDescriptor.java",
                "android/os/Parcelable.java",
                "android/provider/MediaStore.java",
                "android/database/Cursor.java",
                "com/getcapacitor/JSObject.java",
                "com/getcapacitor/PluginCall.java",
                "com/getcapacitor/JSArray.java",
                "org/json/JSONArray.java",
                "org/json/JSONObject.java",
            )
            stubs = [FAST_SCAN / "stubs" / name for name in stub_names]
            native_sources = [
                FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyTextValidator.java",
                FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyGlossaryValidator.java",
                FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "TranslationProjectSupport.java",
            ]
        with tempfile.TemporaryDirectory(prefix="glossary-contract-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / f"{class_name}.java"
            classes = temporary_path / "classes"
            harness_path.write_text(source, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", "",
                 *map(str, stubs), *map(str, native_sources),
                 str(harness_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            if compile_result.returncode != 0:
                return compile_result
            return subprocess.run(
                [str(JAVA), "-cp", str(classes), class_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )

    def test_glossary_validator_requires_target_term(self):
        source = r'''
import com.slgtranslator.app.RenpyGlossaryValidator;
import com.slgtranslator.app.RenpyTextValidator.ValidationResult;
import java.util.*;

public final class GlossaryValidatorHarness {
    public static void main(String[] args) {
        List<RenpyGlossaryValidator.GlossaryTerm> terms = new ArrayList<>();
        terms.add(new RenpyGlossaryValidator.GlossaryTerm(
                "Dad", "\u8001\u7238", RenpyGlossaryValidator.MatchMode.WHOLE_WORD, null));
        ValidationResult missing = RenpyGlossaryValidator.validate(
                "The Dad smiled", "\u7238\u7238\u7b11\u4e86", terms);
        ValidationResult present = RenpyGlossaryValidator.validate(
                "The Dad smiled", "\u8001\u7238\u7b11\u4e86", terms);
        ValidationResult noHit = RenpyGlossaryValidator.validate(
                "Hello there", "Hi", terms);
        System.out.println("MISSING " + missing.valid + " " + missing.codes);
        System.out.println("PRESENT " + present.valid + " " + present.codes);
        System.out.println("NOHIT " + noHit.valid + " " + noHit.codes);
    }
}
'''
        result = self._run_java("GlossaryValidatorHarness", source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MISSING false [glossary_term_missing:Dad]", result.stdout)
        self.assertIn("PRESENT true []", result.stdout)
        self.assertIn("NOHIT true []", result.stdout)

    def test_project_schema_accepts_optional_glossary_and_rejects_invalid_entry(self):
        source = r'''
import com.slgtranslator.app.TranslationProjectSupport;

public final class GlossarySchemaHarness {
    public static void main(String[] args) {
        String base = "{\"schemaVersion\":1,\"sourceLang\":\"en\",\"targetLang\":\"zh\","
                + "\"projectFingerprint\":\"fp1\",\"adapterId\":\"renpy\","
                + "\"sourceVersion\":\"v1\",\"records\":[{"
                + "\"recordId\":\"r1\",\"sourceOwner\":\"base\","
                + "\"sourcePath\":\"game/script.rpyc\",\"resourceType\":\"DIALOGUE\","
                + "\"sourceKey\":\"line-1\",\"sourceText\":\"The Dad smiled\","
                + "\"translation\":\"\u8001\u7238\u7b11\u4e86\",\"validation\":\"APPROVED\"}]}";
        String valid = base.replace("\"records\":", "\"glossary\":[{\"source\":\"Dad\",\"target\":\"\u8001\u7238\",\"matchMode\":\"whole-word\"}],\"records\":");
        TranslationProjectSupport.ValidatedProject parsed =
                TranslationProjectSupport.validateProjectJson(valid);
        System.out.println("VALID " + parsed.recordCount);

        String invalid = base.replace("\"records\":", "\"glossary\":[{\"source\":\"Dad\",\"target\":\"\u8001\u7238\",\"matchMode\":\"context\"}],\"records\":");
        try {
            TranslationProjectSupport.validateProjectJson(invalid);
            System.out.println("INVALID accepted");
        } catch (RuntimeException error) {
            System.out.println("INVALID " + error.getMessage());
        }
    }
}
'''
        result = self._run_java("GlossarySchemaHarness", source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VALID 1", result.stdout)
        self.assertIn("INVALID translation_export_invalid_glossary", result.stdout)
    def assert_installed_app_copy_contract(self, source):
        self.assertRegex(source, r"COPY_BUFFER_SIZE\s*=\s*1024\s*\*\s*1024\s*;")
        self.assertRegex(source, r"byte\[\]\s+buffer\s*=\s*new byte\[COPY_BUFFER_SIZE\]")
        self.assertRegex(
            source,
            r"while\s*\(\(count\s*=\s*input\.read\(buffer\)\)\s*!=\s*-1\)\s*"
            r"\{\s*output\.write\(buffer,\s*0,\s*count\);\s*\}",
        )

        partial_creation = (
            'partial = new File(directory, output.getName() + "." '
            '+ UUID.randomUUID().toString() + ".partial");'
        )
        self.assertIn(partial_creation, source)
        self.assertRegex(
            source,
            r"if\s*\(partial\.exists\(\)\s*&&\s*!partial\.delete\(\)\)\s*"
            r'\{\s*throw new IOException\("stale partial"\);\s*\}',
        )
        self.assertRegex(
            source,
            r"(?s)finally\s*\{.*?if\s*\(partial\s*!=\s*null\s*&&\s*partial\.exists\(\)\)\s*"
            r"\{\s*partial\.delete\(\);\s*\}",
        )
        self.assertIn("for (File pending : partials)", source)
        self.assertRegex(source, r"output\.flush\(\);\s*output\.getFD\(\)\.sync\(\);")

        rename = "if (!partial.renameTo(output))"
        self.assertIn(rename, source)
        self.assertLess(source.index(partial_creation), source.index(rename))
        self.assertIn('throw new IOException("atomic rename")', source)
        self.assertRegex(
            source,
            r"catch\s*\(IOException error\)\s*\{\s*"
            r'call\.reject\("Could not copy the app APK\. Free storage space and try again\."\);',
        )

        self.assertIn('MessageDigest.getInstance("SHA-256")', source)
        self.assertIn(
            'String identity = packageName + "/" + source.lastModified() + "/" + source.length();',
            source,
        )
        self.assertIn('new File(directory, fingerprint(packageName, source) + ".apk")', source)

        self.assertLess(source.index("partial = null;"), source.index("cleanOldApks(directory, output);"))
        cleanup = java_block_after(source, "private static void cleanOldApks(")
        self.assertIn('endsWith(".apk")', cleanup)
        self.assertNotIn('endsWith(".partial")', cleanup)

        selection_start = source.index("int splitCount =")
        result_chain = re.search(
            r"call\.resolve\(new JSObject\(\)(.*?)\);",
            source[selection_start:],
            re.DOTALL,
        )
        self.assertIsNotNone(result_chain, "selection must resolve a structured installed-app result")
        result = result_chain.group(1)
        for field in (
            '.put("uri", Uri.fromFile(output).toString())',
            '.put("name", label + ".apk")',
            '.put("packageName", packageName)',
            '.put("source", "installed")',
            '.put("splitApk", splitCount > 0)',
            '.put("splitCount", splitCount)',
        ):
            self.assertIn(field, result)

        self.assertNotRegex(
            source,
            r"call\.reject\([^;]*(?:sourceDir|getAbsolutePath\(\)|getPath\(\))",
        )
        self.assertNotRegex(
            source,
            r"(?:System\.(?:out|err)|printStackTrace|Log\.)[^;]*"
            r"(?:sourceDir|getAbsolutePath\(\)|getPath\(\))",
        )

    def assert_installed_app_privacy_contract(self, source):
        listing = java_block_after(source, "private static void listInstalledAppsOnWorker(")
        launcher_iteration = java_block_after(
            listing,
            "for (ResolveInfo resolveInfo : launchers)",
        )
        self.assertRegex(
            launcher_iteration,
            r"packageName\.equals\(context\.getPackageName\(\)\)\s*\|\|\s*"
            r"unique\.containsKey\(packageName\)",
        )
        self.assertIn("unique.put(packageName,", launcher_iteration)
        self.assertLess(
            launcher_iteration.index("unique.containsKey(packageName)"),
            launcher_iteration.index("unique.put(packageName,"),
        )

        comparator = java_block_after(listing, "public int compare(AppEntry left, AppEntry right)")
        self.assertIn("left.label.compareToIgnoreCase(right.label)", comparator)
        self.assertNotIn("left.label.compareTo(right.label)", comparator)

        serialization = java_block_after(listing, "for (AppEntry app : apps)")
        list_fields = re.findall(r'\.put\("([^"]+)"\s*,', serialization)
        self.assertEqual(list_fields, ["label", "packageName"])
        self.assertNotRegex(serialization, r'"(?:uri|path|sourceDir|sourcePath)"')

        selection = java_block_after(source, "private static void copySelectedApp(")
        self.assertLess(
            selection.index("isLauncherPackage(packageManager, packageName)"),
            selection.index("packageManager.getApplicationInfo(packageName, 0)"),
        )
        validator = java_block_after(source, "private static boolean isLauncherPackage(")
        self.assertIn("queryLauncherApps(packageManager)", validator)
        query = java_block_after(source, "private static List<ResolveInfo> queryLauncherApps(")
        self.assertRegex(query, r"new Intent\(Intent\.ACTION_MAIN\)")
        self.assertRegex(query, r"intent\.addCategory\(Intent\.CATEGORY_LAUNCHER\)")
        self.assertRegex(query, r"packageManager\.queryIntentActivities\(intent,\s*0\)")

        success = selection[selection.index("call.resolve(new JSObject()") :]
        success = success[:success.index("));") + 3]
        success_fields = re.findall(r'\.put\("([^"]+)"\s*,', success)
        self.assertEqual(
            success_fields,
            [
                "uri", "baseUri", "splitUris", "splitNames", "apkSet",
                "name", "packageName", "versionCode", "source", "splitApk",
                "splitCount",
            ],
        )
        self.assertNotRegex(success, r'"(?:path|sourceDir|sourcePath)"')

    def test_scanner_uses_central_directory_and_bounded_async_copy(self):
        self.assertTrue(SCANNER.exists(), "FastApkScanner.java must exist")
        source = SCANNER.read_text("utf-8")
        for token in (
            "new Thread",
            "new ZipFile",
            "SCAN_TIMEOUT_MS = 60_000L",
            "temp.delete()",
            "MAX_CACHE_ENTRIES = 2",
            "MAX_CACHED_APK_ENTRIES = 50_000",
            '"packageName"',
            '"scanDurationMs"',
            '"cacheHit"',
        ):
            self.assertIn(token, source)
        self.assertNotIn("ZipInputStream", source)
        self.assertIn("catch (Throwable error)", source)

    def test_scan_cache_skips_oversized_metadata_results(self):
        source = SCANNER.read_text("utf-8")
        self.assertIn("MAX_CACHE_ENTRIES = 2", source)
        self.assertIn("MAX_CACHED_APK_ENTRIES", source)
        self.assertIn("clearCache", source)
        self.assertIn("cacheStats", source)

    def test_renpy_scripts_bypass_filename_heuristics_and_keep_supported_types(self):
        source = SCANNER.read_text("utf-8")
        self.assertIn('"rpym", "rpymc", "rpy", "rpyc"', source)
        self.assertIn(
            "if (!isRenPyScriptExtension(extension) && "
            "!Boolean.TRUE.equals(likelyText.invoke(plugin, name)))",
            source,
        )
        self.assertIn(
            "String fileType = normalizeRenPyFileType(extension, detectedType);",
            source,
        )

        harness = r"""
import com.slgtranslator.app.FastApkScanner;
import java.lang.reflect.Method;

public final class RenPyExtensionHarness {
    public static void main(String[] args) throws Exception {
        Method isRenPy = FastApkScanner.class.getDeclaredMethod(
            "isRenPyScriptExtension", String.class
        );
        isRenPy.setAccessible(true);
        Method normalize = FastApkScanner.class.getDeclaredMethod(
            "normalizeRenPyFileType", String.class, String.class
        );
        normalize.setAccessible(true);
        for (String extension : new String[] {"rpy", "rpyc", "rpym", "rpymc"}) {
            require((Boolean) isRenPy.invoke(null, extension), extension + " must bypass filename filtering");
        }
        require(!(Boolean) isRenPy.invoke(null, "json"), "json must retain the existing filename heuristic");
        require("rpy".equals(normalize.invoke(null, "rpym", "text")), "rpym must enter the rpy pipeline");
        require("rpyc".equals(normalize.invoke(null, "rpymc", "text")), "rpymc must enter the rpyc pipeline");
        require("rpyc".equals(normalize.invoke(null, "rpyc", "rpyc")), "rpyc must remain rpyc");
        require("text".equals(normalize.invoke(null, "txt", "text")), "non-RenPy types must be unchanged");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-extension-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenPyExtensionHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
               [
                   str(JAVAC),
                   "-source", "8", "-target", "8", "-encoding", "UTF-8",
                   "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "RenPyExtensionHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_scanner_uses_archive_package_manager_identity_over_manifest_heuristic(self):
        """The APK package identity must come from PackageManager, not string guesses."""
        harness = r'''
import android.content.Context;
import android.content.pm.PackageManager;
import com.slgtranslator.app.FastApkScanner;
import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class ArchivePackageIdentityHarness {
    public static void main(String[] args) throws Exception {
        File apk = new File(args[0]);
        try (ZipOutputStream output = new ZipOutputStream(Files.newOutputStream(apk.toPath()))) {
            output.putNextEntry(new ZipEntry("AndroidManifest.xml"));
            output.write(new byte[] {1, 2, 3, 4});
            output.closeEntry();
        }

        Method scan = FastApkScanner.class.getDeclaredMethod(
                "enumerateCentralDirectory", File.class, Object.class, long.class, Context.class,
                boolean.class);
        scan.setAccessible(true);
        Object result = scan.invoke(null, apk, new HeuristicPlugin(),
                System.currentTimeMillis() + 60_000L, new ArchiveContext(), false);
        Field packageName = result.getClass().getDeclaredField("packageName");
        packageName.setAccessible(true);
        require("com.yishijietiantang.com".equals(packageName.get(result)),
                "archive package identity was not used: " + packageName.get(result));
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static final class HeuristicPlugin {
        private boolean isLikelyTextFile(String name) { return false; }
        private String detectFileType(String name, String extension) { return "text"; }
        private String extractPackageNameFromManifest(byte[] bytes) { return "androidx.startup"; }
    }

    private static final class ArchiveContext extends Context {
        @Override public PackageManager getPackageManager() { return new ArchivePackageManager(); }
    }

    public static final class ArchivePackageManager extends PackageManager {
        public Object getPackageArchiveInfo(String path, int flags) {
            return new ArchivePackageInfo();
        }
    }

    public static final class ArchivePackageInfo {
        public String packageName = "com.yishijietiantang.com";
        public long versionCode = 17L;
    }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="archive-package-identity-test-") as temporary:
            temporary_path = Path(temporary)
            apk_path = temporary_path / "target.apk"
            harness_path = temporary_path / "ArchivePackageIdentityHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            completed = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "ArchivePackageIdentityHarness", str(apk_path)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", "replace"),
            )

    def test_scanner_settles_plugin_call_without_lossy_handler_handoff(self):
        source = SCANNER.read_text("utf-8")
        scan_async = source[
            source.index("public static void scanAsync(") :
            source.index("private static JSObject scan(")
        ]
        self.assertIn("call.resolve(response)", scan_async)
        self.assertIn("call.reject(rejection)", scan_async)
        self.assertNotIn("mainHandler.post", scan_async)
        self.assertNotIn("new Handler(Looper.getMainLooper())", source)

    def test_native_back_handler_is_injected_once_and_delegates_default_back(self):
        handler = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "WorkshopBackHandler.java"
        self.assertTrue(handler.exists(), "WorkshopBackHandler.java must exist")
        source = handler.read_text("utf-8")
        for token in (
            "OnBackPressedCallback",
            "getOnBackPressedDispatcher().addCallback",
            "evaluateJavascript",
            "window.__slgHandleAndroidBack",
            "setEnabled(false)",
            "getOnBackPressedDispatcher().onBackPressed()",
            "setEnabled(true)",
            "activity.runOnUiThread",
        ):
            self.assertIn(token, source)
        builder = BUILDER.read_text("utf-8")
        self.assertIn("BACK_HANDLER_METHOD", builder)
        self.assertIn("enableWorkshopBackHandling", builder)
        self.assertIn("WorkshopBackHandler;->enable", builder)

    def test_back_handler_capacitor_invokes_match_real_base_dex_abi(self):
        self.assertTrue(CAPACITOR_DEX.exists(), "real Capacitor classes3.dex is required")
        self.assertTrue(DEXDUMP.exists(), "Capacitor ABI verification requires dexdump.exe")
        builder = BUILDER.read_text("utf-8")
        method_start = builder.index('BACK_HANDLER_METHOD = """')
        method_end = builder.index('"""', method_start + len('BACK_HANDLER_METHOD = """'))
        method = builder[method_start:method_end]
        invokes = re.findall(
            r"invoke-virtual\s+\{[^}]+\},\s+"
            r"(Lcom/getcapacitor/[^;]+;)->([^\s(]+)(\([^\s]+)",
            method,
        )
        self.assertGreaterEqual(len(invokes), 3)

        completed = subprocess.run(
            [str(DEXDUMP), str(CAPACITOR_DEX.relative_to(ROOT))],
            check=True,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        dump = completed.stdout
        for owner, name, descriptor in invokes:
            marker = f"Class descriptor  : '{owner}'"
            start = dump.index(marker)
            end = dump.find("\nClass #", start)
            class_block = dump[start:end if end >= 0 else len(dump)]
            methods = {
                (method_name, method_type)
                for method_name, method_type in re.findall(
                    r"name\s+: '([^']+)'\s+type\s+: '(\([^']+)'",
                    class_block,
                )
            }
            self.assertIn(
                (name, descriptor),
                methods,
                f"{owner}->{name}{descriptor} is absent from real Capacitor ABI",
            )

    def test_native_back_handler_releases_callbacks_and_guards_async_lifecycle(self):
        handler = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "WorkshopBackHandler.java"
        source = handler.read_text("utf-8")
        self.assertRegex(
            source,
            r"Map<ComponentActivity,\s*WeakReference<OnBackPressedCallback>>",
        )

        harness = r"""
import android.webkit.ValueCallback;
import android.webkit.WebView;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.OnBackPressedDispatcher;
import androidx.lifecycle.Lifecycle;
import androidx.lifecycle.LifecycleOwner;
import com.slgtranslator.app.WorkshopBackHandler;

public final class WorkshopBackHandlerHarness {
    public static void main(String[] args) {
        liveFalseDelegatesOnce();
        liveTrueIsConsumed();
        destroyedBeforeJavascriptResultDoesNothing();
        stoppedBeforeJavascriptResultDoesNothing();
        enableIsIdempotent();
    }

    private static void liveFalseDelegatesOnce() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.webView.reply("false");
        require(fixture.dispatcher.defaultBackCount == 1, "live false must delegate once");
    }

    private static void liveTrueIsConsumed() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.webView.reply("true");
        require(fixture.dispatcher.defaultBackCount == 0, "true must consume back");
    }

    private static void destroyedBeforeJavascriptResultDoesNothing() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.activity.destroyed = true;
        fixture.webView.reply("false");
        require(fixture.dispatcher.defaultBackCount == 0, "destroyed activity must not delegate");
    }

    private static void stoppedBeforeJavascriptResultDoesNothing() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        fixture.dispatcher.callback.handleOnBackPressed();
        fixture.activity.getLifecycle().setCurrentState(Lifecycle.State.CREATED);
        fixture.webView.reply("false");
        require(fixture.dispatcher.defaultBackCount == 0, "stopped activity must not delegate");
    }

    private static void enableIsIdempotent() {
        Fixture fixture = new Fixture();
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        WorkshopBackHandler.enable(fixture.activity, fixture.webView);
        require(fixture.dispatcher.addCount == 1, "enable must install exactly once");
    }

    private static final class Fixture {
        final RecordingDispatcher dispatcher = new RecordingDispatcher();
        final TestActivity activity = new TestActivity(dispatcher);
        final DeferredWebView webView = new DeferredWebView();
    }

    private static final class TestActivity extends ComponentActivity {
        final RecordingDispatcher dispatcher;
        boolean destroyed;

        TestActivity(RecordingDispatcher dispatcher) { this.dispatcher = dispatcher; }
        @Override public void runOnUiThread(Runnable action) { action.run(); }
        @Override public boolean isDestroyed() { return destroyed; }
        @Override public OnBackPressedDispatcher getOnBackPressedDispatcher() { return dispatcher; }
    }

    private static final class RecordingDispatcher extends OnBackPressedDispatcher {
        OnBackPressedCallback callback;
        int addCount;
        int defaultBackCount;

        @Override public void addCallback(LifecycleOwner owner, OnBackPressedCallback callback) {
            this.callback = callback;
            addCount++;
        }
        @Override public void onBackPressed() { defaultBackCount++; }
    }

    private static final class DeferredWebView extends WebView {
        ValueCallback<String> callback;
        @Override public void evaluateJavascript(String script, ValueCallback<String> callback) {
            this.callback = callback;
        }
        void reply(String value) {
            ValueCallback<String> pending = callback;
            callback = null;
            pending.onReceiveValue(value);
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="back-handler-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "WorkshopBackHandlerHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    str(handler),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "WorkshopBackHandlerHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_scanner_prefers_seekable_descriptor_for_multi_gigabyte_apks(self):
        self.assertTrue(SCANNER.exists(), "FastApkScanner.java must exist")
        source = SCANNER.read_text("utf-8")
        for token in (
            "openFileDescriptor",
            '"/proc/self/fd/"',
            "ParcelFileDescriptor",
            "scanSeekableDescriptor",
        ):
            self.assertIn(token, source)

    def test_split_apk_set_scans_assets_and_installs_in_one_session(self):
        """Base and each split stay independent while the bridge carries one set."""
        apk_set = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledApkSet.java"
        installer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "PackageInstallerSupport.java"
        workshop = ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py"

        with tempfile.TemporaryDirectory(prefix="split-apk-contract-") as temporary:
            directory = Path(temporary)
            base = directory / "base.apk"
            split_a = directory / "split_a.apk"
            split_b = directory / "split_b.apk"
            write_split_apk(base, {
                "AndroidManifest.xml": b"package=com.example.renpy versionCode=17",
                "assets/game/main.rpyc": b"base-script",
            })
            write_split_apk(split_a, {"assets/game/chapter.rpyc": b"chapter-script"})
            write_split_apk(split_b, {"assets/fonts/game.ttf": b"font-bytes"})

            # The fixture itself proves the test is exercising three ZIP central
            # directories rather than a byte-concatenated pseudo-APK.
            with zipfile.ZipFile(base) as archive:
                self.assertIn("AndroidManifest.xml", archive.namelist())
            with zipfile.ZipFile(split_a) as archive:
                self.assertEqual(archive.read("assets/game/chapter.rpyc"), b"chapter-script")
            with zipfile.ZipFile(split_b) as archive:
                self.assertEqual(archive.read("assets/fonts/game.ttf"), b"font-bytes")

        self.assertTrue(apk_set.exists(), "InstalledApkSet.java must be created")
        model = apk_set.read_text("utf-8")
        for token in (
            "public final File baseApk",
            "public final List<File> splitApks",
            "public final String packageName",
            "public final long versionCode",
            "Collections.unmodifiableList",
        ):
            self.assertIn(token, model)

        scanner = SCANNER.read_text("utf-8")
        for token in (
            "scanApkSet",
            "splitUris",
            'put("sourceApk"',
            'put("apkRole"',
            "new ZipFile",
            "RenpyResourceLimits.checkPath",
        ):
            self.assertIn(token, scanner)
        self.assertNotIn("concatenate", scanner.lower())
        self.assertNotIn("appendApkBytes", scanner)

        installer_source = installer.read_text("utf-8")
        for token in (
            "installApkSet(Context context, InstalledApkSet apkSet, PluginCall call)",
            'writeApk(session, apkSet.baseApk, "base.apk")',
            'session.openWrite(entryName',
            "splitEntryName",
            "validateApkSet",
            "abandonSession(sessionId)",
        ):
            self.assertIn(token, installer_source)

        ui = workshop.read_text("utf-8")
        for token in (
            "splitUris",
            "baseUri",
            "splitCount",
            "sourceApk",
            "session",
        ):
            self.assertIn(token, ui)
        self.assertIn("当前只检查了基础 APK", ui)
        self.assertIn("已合并读取基础 APK 与全部 split 资源", ui)

    def test_split_apk_set_is_immutable_and_rejects_duplicate_or_missing_parts(self):
        model = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledApkSet.java").read_text("utf-8")
        for token in (
            "Collections.unmodifiableList",
            "IllegalArgumentException",
            "baseApk.equals(splitApk)",
            "copiedSplits.contains",
            "splitName metadata is invalid",
        ):
            self.assertIn(token, model)
        self.assertRegex(model, r"new ArrayList(?:<[^>]*>)?\s*\(")
        self.assertNotIn("File[] allApks", model)
        self.assertNotIn("merge", model.lower())

    def test_split_scanning_and_reading_fail_closed_instead_of_base_only_fallback(self):
        scanner = SCANNER.read_text("utf-8")
        installer = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "PackageInstallerSupport.java").read_text("utf-8")
        for source in (scanner, installer):
            self.assertRegex(source, r"(?i)(fail.?closed|reject|throw new (?:IOException|IllegalArgumentException))")
        self.assertIn("split metadata", scanner.lower())
        self.assertIn("signature", installer.lower())
        self.assertIn("versionCode", installer)
        self.assertIn("splitName", installer)

    def test_split_scan_uses_split_template_and_merges_all_font_preflights(self):
        scanner = SCANNER.read_text("utf-8")
        for token in (
            "List<RenpyFontSupport.FontReport> fontReports",
            "mergeFontReports",
            "mergeFontReportsForApkSet",
            "missingAcrossSet",
            "bestCompatibility",
            "current.compatibility",
            "current.compatibilityReport.templatePath",
            "split metadata packageName mismatch",
            "split metadata versionCode mismatch",
            "split metadata splitName mismatch",
            "getPackageArchiveInfo",
        ):
            self.assertIn(token, scanner)
        self.assertIn("fontReports.add", scanner)
        self.assertIn("fontReports", scanner[scanner.index("scanApkSet"):])

    def test_split_ui_preserves_collection_metadata_through_scan_read_compile_and_install(self):
        ui = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        for token in (
            "window.__slgSelectionMeta?.splitUris",
            "readRenpyTexts({uri:(window.__slgSelectionMeta?.uri||n),splitUris",
            "buildPatchedApk({uri:(window.__slgSelectionMeta?.uri||n),",
            "splitUris:window.__slgSelectionMeta?.splitUris||[]",
            "compileTranslationsIntoApk(",
            "baseUri:(window.__slgSelectionMeta?.baseUri||window.__slgSelectionMeta?.uri||n)",
            "installApk({uri:e,baseUri:e,",
            "splitNames:window.__slgSelectionMeta?.splitNames||[]",
            "splitCount",
        ):
            self.assertIn(token, ui)

    def test_patch_build_excludes_all_renpy_translation_loose_files(self):
        ui = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        self.assertIn(r"String(_x.path).replace(/\\\\/g,`/`).toLowerCase()", ui)
        self.assertIn("!_p.includes(`/x-tl/`)", ui)
        generated = ROOT / "apk-work" / "ui-redesign" / "generated" / "index-CJtfdHOF.js"
        self.assertTrue(generated.is_file(), "generated workshop JS must exist")
        bundled = generated.read_text("utf-8")
        self.assertIn(r"String(_x.path).replace(/\\/g,`/`).toLowerCase()", bundled)
        self.assertIn("!_p.includes(`/x-tl/`)", bundled)

    def test_single_apk_uri_materialization_allows_stale_source_name(self):
        """A content URI hash filename must not look like a missing split."""
        scanner = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java").read_text("utf-8")
        self.assertIn(
            "boolean allowSingleBaseNameDrift = apkSet.splitApks.isEmpty();",
            scanner,
        )
        self.assertIn(
            "&& !allowSingleBaseNameDrift",
            scanner,
        )
        self.assertIn(
            '"split metadata sourceApk is not part of the selected set"',
            scanner,
        )

    def test_split_archive_parser_limit_does_not_block_split_metadata_validation(self):
        """Standalone split parsing may fail on Android, but the selected set remains usable."""
        harness = r"""
import android.content.Context;
import android.content.pm.PackageManager;
import com.slgtranslator.app.FastApkScanner;
import com.slgtranslator.app.InstalledApkSet;
import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;

public final class SplitParserLimitHarness {
    public static final class ArchiveInfo {
        public String packageName = "com.example.game";
        public int versionCode = 17;
        public String[] splitNames = new String[0];
        public long getLongVersionCode() { return versionCode; }
    }

    public static final class TestPackageManager extends PackageManager {
        public ArchiveInfo getPackageArchiveInfo(String path, int flags) {
            if (path.endsWith("split.apk")) {
                throw new IllegalArgumentException(
                        "Expected base APK, but found split config.arm64_v8a");
            }
            return new ArchiveInfo();
        }
    }

    public static final class TestContext extends Context {
        private final PackageManager packageManager = new TestPackageManager();
        @Override public PackageManager getPackageManager() { return packageManager; }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File base = new File(root, "base.apk");
        File split = new File(root, "split.apk");
        require(base.createNewFile() && split.createNewFile(), "fixture files must be created");
        InstalledApkSet set = new InstalledApkSet(
                base, Arrays.asList(split), "com.example.game", 17,
                Arrays.asList("config.arm64_v8a"));
        Method validator = FastApkScanner.class.getDeclaredMethod(
                "validateApkSetMetadata", Context.class, InstalledApkSet.class);
        validator.setAccessible(true);
        try {
            validator.invoke(null, new TestContext(), set);
        } catch (InvocationTargetException error) {
            throw new AssertionError("known split parser limitation must be tolerated",
                    error.getCause());
        }
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="split-parser-limit-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SplitParserLimitHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            fixture.mkdir()
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SplitParserLimitHarness", str(fixture)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_translation_project_schema_export_and_import_validation(self):
        harness = r"""
import com.slgtranslator.app.TranslationProjectSupport;

public final class TranslationProjectHarness {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        String current = "[{\"recordId\":\"r1\",\"sourceText\":\"Hello %s\"}]";
        String valid = "{\"schemaVersion\":1,\"sourceLang\":\"en\",\"targetLang\":\"zh\","
                + "\"projectFingerprint\":\"fp1\","
                + "\"adapterId\":\"renpy\",\"sourceVersion\":\"v1\",\"records\":[{"
                + "\"recordId\":\"r1\",\"sourceOwner\":\"base\","
                + "\"sourcePath\":\"assets/game/script.rpyc\",\"resourceType\":\"DIALOGUE\","
                + "\"sourceKey\":\"line-1\",\"sourceText\":\"Hello %s\","
                + "\"translation\":\"你好 %s\",\"validation\":\"APPROVED\"}]}";
        TranslationProjectSupport.ValidatedProject parsed =
                TranslationProjectSupport.validateProjectJson(valid);
        require(parsed.recordCount == 1, "one record must validate");
        TranslationProjectSupport.ImportResult imported =
                TranslationProjectSupport.validateImport(valid, "fp1", "renpy", "v1",
                        "en", "zh", current);
        require(imported.acceptedCount == 1 && imported.reviewCount == 0,
                "matching record must import automatically");

        String wrongLang = valid.replace("\"targetLang\":\"zh\"", "\"targetLang\":\"ja\"");
        TranslationProjectSupport.ImportResult mismatchedLang =
                TranslationProjectSupport.validateImport(wrongLang, "fp1", "renpy", "v1",
                        "en", "zh", current);
        require(mismatchedLang.acceptedCount == 0 && mismatchedLang.reviewCount == 1,
                "cross-language project must never auto-import");

        String changed = valid.replace("Hello %s", "Hello %d");
        TranslationProjectSupport.ImportResult stale =
                TranslationProjectSupport.validateImport(changed, "fp1", "renpy", "v1",
                        "en", "zh", current);
        require(stale.acceptedCount == 0 && stale.reviewCount == 1,
                "changed source text must require review");

        String brokenPlaceholder = valid.replace("你好 %s", "你好");
        TranslationProjectSupport.ImportResult invalid =
                TranslationProjectSupport.validateImport(brokenPlaceholder, "fp1", "renpy", "v1",
                        "en", "zh", current);
        require(invalid.acceptedCount == 0 && invalid.reviewCount == 1,
                "placeholder mismatch must not auto-import");

        String empty = "{\"schemaVersion\":1,\"sourceLang\":\"en\",\"targetLang\":\"zh\","
                + "\"projectFingerprint\":\"fp1\",\"adapterId\":\"renpy\","
                + "\"sourceVersion\":\"v1\",\"records\":[]}";
        require(TranslationProjectSupport.validateImport(empty, "fp1", "renpy", "v1",
                "en", "zh", current).reasonCode.equals("translation_export_empty"),
                "empty project must be rejected before any record work");
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-project-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationProjectHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "TranslationProjectHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_installed_split_names_come_from_manifest_metadata_not_file_names(self):
        source = INSTALLED_APPS.read_text("utf-8")
        model = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledApkSet.java").read_text("utf-8")
        for token in (
            "splitNames",
            "getPackageArchiveInfo",
            "splitNamesFromPackageInfo",
            "splitName metadata is unavailable",
            "splitName mismatch",
        ):
            self.assertIn(token, source + model)
        self.assertNotIn("String splitName = safeSplitName(splitSource, index);", source)
        self.assertNotIn("value = splitApk.getName();", model)

    def test_build_pipeline_patches_only_the_entrypoint_and_adds_helper_dex(self):
        self.assertTrue(BUILDER.exists(), "build_fast_scanner.py must exist")
        source = BUILDER.read_text("utf-8")
        for token in (
            "listApkEntries",
            "FastApkScanner;->scanAsync",
            ".annotation runtime Lcom/getcapacitor/PluginMethod;",
            "classes6.dex",
            "classes7.dex",
            "apktool_3.0.2.jar",
            "d8.bat",
        ):
            self.assertIn(token, source)

    def test_installed_app_source_is_private_launcher_only(self):
        self.assertTrue(INSTALLED_APPS.exists(), "InstalledAppSource.java must exist")
        source = INSTALLED_APPS.read_text("utf-8")
        for token in (
            "Intent.ACTION_MAIN",
            "Intent.CATEGORY_LAUNCHER",
            "queryIntentActivities",
            "context.getPackageName()",
            "sourceDir",
            "splitSourceDirs",
            'installedApksDir(context)',
            "getExternalFilesDir(null)",
            '"installed-apks"',
            'put("source", "installed")',
            'put("splitApk", splitCount > 0)',
        ):
            self.assertIn(token, source)
        self.assertNotIn("QUERY_ALL_PACKAGES", source)
        self.assert_installed_app_copy_contract(source)
        self.assert_installed_app_privacy_contract(source)

        builder = BUILDER.read_text("utf-8")
        for token in (
            "SOURCE_SOURCES",
            "*map(str, SOURCE_SOURCES)",
            "listInstalledApps",
            "InstalledAppSource;->listInstalledApps",
            "selectInstalledApp",
            "InstalledAppSource;->selectInstalledApp",
            "listSaveGameApps",
            "InstalledAppSource;->listSaveGameApps",
        ):
            self.assertIn(token, builder)
        self.assertIn("bridge_counts == [0] * len(INSTALLED_APP_METHODS)", builder)
        self.assertIn("bridge_counts != [1] * len(INSTALLED_APP_METHODS)", builder)
        self.assertIn("patched.count(signature) != 1 or patched.count(delegate) != 1", builder)
        self.assertIn("Expected exactly one listApkEntries method", builder)
        self.assertEqual(builder.count('".method public final listInstalledApps('), 2)
        self.assertEqual(builder.count('".method public final selectInstalledApp('), 2)
        self.assertEqual(builder.count('".method public final listSaveGameApps('), 2)

    def test_save_game_list_scans_renpy_save_dirs_without_all_apps(self):
        source = INSTALLED_APPS.read_text("utf-8")
        self.assertIn("public static void listSaveGameApps(", source)
        listing = java_block_after(source, "private static void listSaveGameAppsOnWorker(")
        self.assertIn('new File(android.os.Environment.getExternalStorageDirectory(), "Documents")', listing)
        self.assertIn('new File(documents, "RenPy_Saves")', listing)
        self.assertIn('packageName.contains(".")', listing)
        self.assertNotIn("queryLauncherApps", listing)
        self.assertNotIn("queryIntentActivities", listing)
        self.assertNotIn("QUERY_ALL_PACKAGES", source)
        builder = BUILDER.read_text("utf-8")
        self.assertIn(".method public final listSaveGameApps(Lcom/getcapacitor/PluginCall;)V", builder)
        self.assertIn("Lcom/slgtranslator/app/InstalledAppSource;->listSaveGameApps", builder)

        # Execute the worker against a temporary shared-storage root.  The
        # repository stubs do not retain JSObject values, so this fixture uses
        # equivalent test-only Capacitor/Environment stubs and compiles the
        # actual InstalledAppSource.java unchanged.
        custom_stubs = {
            "android/os/Environment.java": r'''
package android.os;
import java.io.File;
public final class Environment {
    public static File getExternalStorageDirectory() {
        return new File(System.getProperty("test.external.root"));
    }
}
''',
            "com/getcapacitor/JSObject.java": r'''
package com.getcapacitor;
import java.util.LinkedHashMap;
import java.util.Map;
public class JSObject {
    public final Map<String,Object> values = new LinkedHashMap<>();
    public JSObject put(String key, Object value) { values.put(key, value); return this; }
}
''',
            "com/getcapacitor/JSArray.java": r'''
package com.getcapacitor;
import java.util.ArrayList;
import java.util.List;
public class JSArray {
    public final List<Object> values = new ArrayList<>();
    public void put(Object value) { values.add(value); }
    public int length() { return values.size(); }
}
''',
            "com/getcapacitor/PluginCall.java": r'''
package com.getcapacitor;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
public class PluginCall {
    public JSObject resolved;
    public String rejected;
    private final CountDownLatch done = new CountDownLatch(1);
    public String getString(String key) { return null; }
    public JSArray getArray(String key) { return null; }
    public void resolve(JSObject value) { resolved = value; done.countDown(); }
    public void reject(String message) { rejected = message; done.countDown(); }
    public boolean await() throws InterruptedException { return done.await(5, TimeUnit.SECONDS); }
}
''',
        }
        harness = r'''
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.InstalledAppSource;
import java.io.File;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

public final class SaveGameListHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File saves = new File(root, "Documents/RenPy_Saves");
        require(new File(saves, "zitao.mbml").mkdirs(), "create first save directory");
        require(new File(saves, "cim.isekai.game").mkdirs(), "create second save directory");
        require(new File(saves, "README").mkdirs(), "create non-package directory");
        require(new File(saves, "ignored.game").createNewFile(), "create non-directory package-shaped entry");

        TestPackageManager packageManager = new TestPackageManager();
        packageManager.labels.put("zitao.mbml", "Game One");
        packageManager.labels.put("cim.isekai.game", "Game Two");
        TestContext context = new TestContext(packageManager, "host.translator");
        PluginCall call = new PluginCall();
        InstalledAppSource.listSaveGameApps(context, call);
        require(call.await(), "save-game worker must settle");
        require(call.rejected == null, "save-game worker must resolve: " + call.rejected);
        JSArray apps = (JSArray) call.resolved.values.get("apps");
        require(apps != null && apps.length() == 2, "only two save directories should be returned");
        Set<String> packages = new HashSet<>();
        for (Object value : apps.values) {
            packages.add(String.valueOf(((JSObject) value).values.get("packageName")));
        }
        require(packages.contains("zitao.mbml") && packages.contains("cim.isekai.game"), "returned package names: " + packages);
        System.out.println("save-game-packages=" + packages);
        System.exit(0);
    }

    private static final class TestContext extends Context {
        private final PackageManager packageManager;
        private final String packageName;
        TestContext(PackageManager packageManager, String packageName) {
            this.packageManager = packageManager;
            this.packageName = packageName;
        }
        @Override public PackageManager getPackageManager() { return packageManager; }
        @Override public String getPackageName() { return packageName; }
    }

    private static final class TestPackageManager extends PackageManager {
        final Map<String,String> labels = new HashMap<>();
        @Override public ApplicationInfo getApplicationInfo(String packageName, int flags) throws NameNotFoundException {
            if (!labels.containsKey(packageName)) throw new NameNotFoundException();
            ApplicationInfo info = new ApplicationInfo();
            info.packageName = packageName;
            return info;
        }
        @Override public CharSequence getApplicationLabel(ApplicationInfo info) { return labels.get(info.packageName); }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
'''
        with tempfile.TemporaryDirectory(prefix="save-game-list-test-") as temporary:
            temporary_path = Path(temporary)
            external_root = temporary_path / "external"
            external_root.mkdir()
            classes = temporary_path / "classes"
            classes.mkdir()
            source_paths = []
            for relative, content in custom_stubs.items():
                path = temporary_path / "custom-stubs" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                source_paths.append(path)
            harness_path = temporary_path / "SaveGameListHarness.java"
            harness_path.write_text(harness, encoding="utf-8")
            repository_stubs = [
                path for path in sorted((FAST_SCAN / "stubs").rglob("*.java"))
                if path.name not in {"Environment.java", "JSObject.java", "JSArray.java", "PluginCall.java"}
            ]
            compile_result = subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, repository_stubs), *map(str, source_paths),
                    str(INSTALLED_APPS), str(FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstalledApkSet.java"),
                    str(harness_path),
                ],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(
                [
                    str(JAVA), f"-Dtest.external.root={external_root}",
                    "-cp", str(classes), "SaveGameListHarness", str(external_root),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertIn("zitao.mbml", result.stdout)
            self.assertIn("cim.isekai.game", result.stdout)

    def test_installed_app_contract_detects_copy_buffer_regression(self):
        source = INSTALLED_APPS.read_text("utf-8")
        broken = source.replace("1024 * 1024", "8192", 1)
        self.assertNotEqual(source, broken, "controlled mutation must alter the buffer constant")
        with self.assertRaises(AssertionError):
            self.assert_installed_app_copy_contract(broken)

    def test_installed_app_privacy_contract_detects_controlled_regressions(self):
        source = INSTALLED_APPS.read_text("utf-8")
        mutations = (
            source.replace(
                "packageName.equals(context.getPackageName()) || ",
                "",
                1,
            ),
            source.replace("compareToIgnoreCase", "compareTo", 1),
            source.replace(
                '.put("packageName", app.packageName)',
                '.put("packageName", app.packageName).put("path", app.packageName)',
                1,
            ),
        )
        for broken in mutations:
            self.assertNotEqual(source, broken, "controlled mutation must alter production source")
            with self.assertRaises(AssertionError):
                self.assert_installed_app_privacy_contract(broken)

    def test_installed_app_requests_are_serialized_and_cache_retains_two_finals(self):
        source = INSTALLED_APPS.read_text("utf-8")
        self.assertIn("Executors.newSingleThreadExecutor", source)
        self.assertIn('return new Thread(runnable, "installed-app-worker")', source)
        listing = java_block_after(source, "public static void listInstalledApps(")
        selection = java_block_after(source, "public static void selectInstalledApp(")
        self.assertIn("WORKER.execute(new Runnable()", listing)
        self.assertIn("WORKER.execute(new Runnable()", selection)
        self.assertNotIn("new Thread", listing)
        self.assertNotIn("new Thread", selection)
        self.assertIn("UUID.randomUUID().toString()", source)

        cleanup = java_block_after(source, "private static void cleanOldApks(")
        self.assertNotIn('endsWith(".partial")', cleanup)
        self.assertIn("finals.size()", cleanup)
        self.assertIn("index >= 2", cleanup)
        self.assertRegex(
            cleanup,
            r"if\s*\(index\s*>=\s*2\s*&&\s*!file\.equals\(keep\)\)\s*"
            r"\{\s*file\.delete\(\);",
        )
        self.assertIn("markNewest(directory, output);", source)
        recency = java_block_after(source, "private static void markNewest(")
        self.assertIn("Math.max(System.currentTimeMillis(), newest + 1)", recency)
        self.assertIn("if (!output.setLastModified(timestamp))", recency)
        stale_cleanup = source.index("cleanStalePartials(directory);")
        request_partial = source.index("UUID.randomUUID().toString()")
        self.assertLess(stale_cleanup, request_partial)
        self.assertLess(source.index("partial = null;"), source.index("cleanOldApks(directory, output);"))

    def test_cache_cleanup_removes_interrupted_partial_and_keeps_recent_results(self):
        if not JAVA.exists() or not JAVAC.exists():
            self.skipTest("JDK is not present for executable cache ownership test")
        harness = r"""
import com.slgtranslator.app.InstalledAppSource;
import java.io.File;
import java.lang.reflect.Method;

public final class CacheOwnershipHarness {
    public static void main(String[] args) throws Exception {
        File directory = new File(args[0]);
        File first = touch(directory, "first.apk", 1000L);
        File stalePartial = touch(directory, "interrupted.partial", 1500L);
        Method staleCleanup = InstalledAppSource.class.getDeclaredMethod("cleanStalePartials", File.class);
        staleCleanup.setAccessible(true);
        Method cleanup = InstalledAppSource.class.getDeclaredMethod("cleanOldApks", File.class, File.class);
        cleanup.setAccessible(true);

        File second = touch(directory, "second.apk", 2000L);
        staleCleanup.invoke(null, directory);
        require(!stalePartial.exists(), "a new serialized copy must remove interrupted partials");
        cleanup.invoke(null, directory, second);
        require(first.isFile(), "the previous returned URI must survive the second selection");
        require(second.isFile(), "the current returned URI must survive cleanup");

        File third = touch(directory, "third.apk", 3000L);
        cleanup.invoke(null, directory, third);
        require(!first.exists(), "only finals older than current+previous should be pruned");
        require(second.isFile() && third.isFile(), "current and previous finals must remain");
    }

    private static File touch(File directory, String name, long modified) throws Exception {
        File file = new File(directory, name);
        require(file.createNewFile(), "fixture already exists: " + name);
        require(file.setLastModified(modified), "cannot set fixture timestamp: " + name);
        return file;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="installed-cache-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CacheOwnershipHarness.java"
            classes = temporary_path / "classes"
            cache = temporary_path / "cache"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            cache.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    str(INSTALLED_APPS),
                    str(INSTALLED_APK_SET),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CacheOwnershipHarness", str(cache)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_installed_split_selection_preserves_manifest_split_names(self):
        """Execute the installed-app copy path with two manifest-declared splits."""
        if not JAVA.exists() or not JAVAC.exists():
            self.skipTest("JDK is not present for executable split ownership test")
        custom_stubs = {
            "android/content/Context.java": r'''
package android.content;
import android.content.pm.PackageManager;
import java.io.File;
public class Context {
    public PackageManager getPackageManager() { return null; }
    public String getPackageName() { return null; }
    public File getExternalFilesDir(String type) { return null; }
    public File getFilesDir() { return null; }
}
''',
            "android/content/pm/ApplicationInfo.java": r'''
package android.content.pm;
public class ApplicationInfo {
    public String packageName;
    public String sourceDir;
    public String[] splitSourceDirs;
    public String[] splitNames;
}
''',
            "android/content/pm/PackageInfo.java": r'''
package android.content.pm;
public class PackageInfo {
    public String packageName;
    public int versionCode;
    public String[] splitNames;
    public long getLongVersionCode() { return versionCode; }
}
''',
            "android/content/pm/PackageManager.java": r'''
package android.content.pm;
import android.content.Intent;
import java.util.List;
public class PackageManager {
    public List<ResolveInfo> queryIntentActivities(Intent intent, int flags) { return null; }
    public ApplicationInfo getApplicationInfo(String packageName, int flags) throws NameNotFoundException { return null; }
    public CharSequence getApplicationLabel(ApplicationInfo info) { return null; }
    public PackageInfo getPackageArchiveInfo(String path, int flags) { return null; }
    public static class NameNotFoundException extends Exception {}
}
''',
            "android/net/Uri.java": r'''
package android.net;
import android.os.Parcelable;
import java.io.File;
public class Uri implements Parcelable {
    private final String value;
    private Uri(String value) { this.value = value; }
    public static Uri parse(String value) { return new Uri(value); }
    public String getPath() { return value.startsWith("file://") ? value.substring(7) : value; }
    public static Uri fromFile(File file) { return new Uri("file://" + file.getAbsolutePath()); }
    public String toString() { return value; }
}
''',
            "com/getcapacitor/JSObject.java": r'''
package com.getcapacitor;
import java.util.LinkedHashMap;
import java.util.Map;
public class JSObject {
    public final Map<String,Object> values = new LinkedHashMap<>();
    public JSObject put(String key, Object value) { values.put(key, value); return this; }
}
''',
            "com/getcapacitor/JSArray.java": r'''
package com.getcapacitor;
import java.util.ArrayList;
import java.util.List;
public class JSArray {
    public final List<Object> values = new ArrayList<>();
    public void put(Object value) { values.add(value); }
    public int length() { return values.size(); }
    public Object opt(int index) { return index < values.size() ? values.get(index) : null; }
}
''',
            "com/getcapacitor/PluginCall.java": r'''
package com.getcapacitor;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
public class PluginCall {
    public JSObject resolved;
    public String rejected;
    public String packageName;
    private final CountDownLatch done = new CountDownLatch(1);
    public String getString(String key) { return "packageName".equals(key) ? packageName : null; }
    public JSArray getArray(String key) { return null; }
    public void resolve(JSObject value) { resolved = value; done.countDown(); }
    public void reject(String message) { rejected = message; done.countDown(); }
    public boolean await() throws InterruptedException { return done.await(5, TimeUnit.SECONDS); }
}
''',
        }
        harness = r'''
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.InstalledAppSource;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.Collections;

public final class InstalledSplitSelectionHarness {
    public static void main(String[] args) throws Exception {
        int exit = 0;
        try {
            run(args);
        } catch (Throwable error) {
            error.printStackTrace();
            exit = 1;
        }
        System.exit(exit);
    }

    private static void run(String[] args) throws Exception {
        File root = new File(args[0]);
        File base = write(root, "base.apk", "base");
        File splitA = write(root, "arbitrary-a.apk", "split-a");
        File splitB = write(root, "arbitrary-b.apk", "split-b");

        ApplicationInfo app = new ApplicationInfo();
        app.packageName = "com.example.game";
        app.sourceDir = base.getAbsolutePath();
        app.splitSourceDirs = new String[] {splitA.getAbsolutePath(), splitB.getAbsolutePath()};
        app.splitNames = new String[] {"feature_a", "feature_b"};
        TestPackageManager packageManager = new TestPackageManager(app);
        TestContext context = new TestContext(packageManager, root, "com.slgtranslator.app");
        PluginCall call = new PluginCall();
        InstalledAppSource.selectInstalledApp(context, callWithPackage(call, "com.example.game"));
        require(call.await(), "selection worker must settle");
        require(call.rejected == null, "split selection must resolve: " + call.rejected);
        require(call.resolved != null, "split selection result is missing");
        require(((Number) call.resolved.values.get("splitCount")).intValue() == 2,
                "both splits must be returned");
        JSArray names = (JSArray) call.resolved.values.get("splitNames");
        require(names != null && names.values.equals(Arrays.asList("feature_a", "feature_b")),
                "manifest split names must stay ordered: " + (names == null ? null : names.values));
        File copied = new File(root, "installed-apks");
        require(hasSuffix(copied, "-feature_a"), "feature_a private copy is missing");
        require(hasSuffix(copied, "-feature_b"), "feature_b private copy is missing");
        System.out.println("split-names=" + names.values);
    }

    private static PluginCall callWithPackage(PluginCall call, String packageName) {
        call.packageName = packageName;
        return call;
    }

    private static File write(File root, String name, String value) throws Exception {
        File file = new File(root, name);
        Files.write(file.toPath(), value.getBytes(StandardCharsets.UTF_8));
        return file;
    }

    private static boolean hasSuffix(File directory, String suffix) {
        File[] files = directory.listFiles();
        if (files == null) return false;
        for (File file : files) if (file.getName().endsWith(suffix)) return true;
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static final class TestContext extends Context {
        private final PackageManager packageManager;
        private final File root;
        private final String packageName;
        TestContext(PackageManager packageManager, File root, String packageName) {
            this.packageManager = packageManager;
            this.root = root;
            this.packageName = packageName;
        }
        @Override public PackageManager getPackageManager() { return packageManager; }
        @Override public File getExternalFilesDir(String type) { return root; }
        @Override public File getFilesDir() { return root; }
        @Override public String getPackageName() { return packageName; }
    }

    private static final class TestPackageManager extends PackageManager {
        private final ApplicationInfo app;
        TestPackageManager(ApplicationInfo app) { this.app = app; }
        @Override public java.util.List<ResolveInfo> queryIntentActivities(Intent intent, int flags) {
            ResolveInfo result = new ResolveInfo();
            result.activityInfo = new ActivityInfo();
            result.activityInfo.applicationInfo = app;
            return Collections.singletonList(result);
        }
        @Override public ApplicationInfo getApplicationInfo(String packageName, int flags) {
            return app;
        }
        @Override public CharSequence getApplicationLabel(ApplicationInfo info) { return "Fixture Game"; }
        @Override public PackageInfo getPackageArchiveInfo(String path, int flags) {
            PackageInfo info = new PackageInfo();
            info.packageName = app.packageName;
            info.versionCode = 17;
            return info;
        }
    }
}
'''
        with tempfile.TemporaryDirectory(prefix="installed-split-selection-") as temporary:
            temporary_path = Path(temporary)
            classes = temporary_path / "classes"
            root = temporary_path / "fixture"
            classes.mkdir()
            root.mkdir()
            source_paths = []
            for relative, content in custom_stubs.items():
                path = temporary_path / "custom-stubs" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                source_paths.append(path)
            harness_path = temporary_path / "InstalledSplitSelectionHarness.java"
            harness_path.write_text(harness, encoding="utf-8")
            excluded = {
                "Context.java", "ApplicationInfo.java", "PackageManager.java",
                "JSObject.java", "JSArray.java", "PluginCall.java", "Uri.java",
            }
            repository_stubs = [
                path for path in sorted((FAST_SCAN / "stubs").rglob("*.java"))
                if path.name not in excluded
            ]
            compile_result = subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, repository_stubs), *map(str, source_paths),
                    str(INSTALLED_APPS), str(INSTALLED_APK_SET), str(harness_path),
                ],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "InstalledSplitSelectionHarness", str(root)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("split-names=[feature_a, feature_b]", result.stdout)

    def test_split_installer_validates_metadata_abandons_write_failure_and_preserves_order(self):
        """Execute split installer validation, session abort and write order."""
        custom_stubs = {
            "android/content/Context.java": r'''
package android.content;
import android.content.pm.PackageManager;
import java.io.File;
public class Context {
    public static final int RECEIVER_NOT_EXPORTED = 0x4;
    public static final int RECEIVER_EXPORTED = 0x2;
    public PackageManager getPackageManager() { return null; }
    public String getPackageName() { return null; }
    public Context getApplicationContext() { return this; }
    public BroadcastReceiver lastReceiver;
    public Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter) { lastReceiver = receiver; return null; }
    public Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter, int flags) { lastReceiver = receiver; return null; }
    public void unregisterReceiver(BroadcastReceiver receiver) {}
    public void startActivity(Intent intent) {}
}
''',
            "android/content/Intent.java": r'''
package android.content;

import android.net.Uri;
import android.os.Parcelable;
import java.util.LinkedHashMap;
import java.util.Map;

public class Intent {
    public static final String ACTION_MAIN = "android.intent.action.MAIN";
    public static final String ACTION_SEND = "android.intent.action.SEND";
    public static final String CATEGORY_LAUNCHER = "android.intent.category.LAUNCHER";
    public static final String EXTRA_STREAM = "android.intent.extra.STREAM";
    public static final String EXTRA_INTENT = "android.intent.extra.INTENT";
    public static final int FLAG_GRANT_READ_URI_PERMISSION = 0x00000001;
    public static final int FLAG_ACTIVITY_NEW_TASK = 0x10000000;

    private final Map<String, Object> extras = new LinkedHashMap<>();

    public Intent(String action) {}
    public Intent addCategory(String category) { return this; }
    public Intent setData(Uri uri) { return this; }
    public Intent setPackage(String packageName) { return this; }
    public Intent addFlags(int flags) { return this; }
    public Intent setAction(String action) { return this; }
    public Intent setType(String type) { return this; }
    public Intent putExtra(String name, String value) { extras.put(name, value); return this; }
    public Intent putExtra(String name, int value) { extras.put(name, value); return this; }
    public Intent putExtra(String name, Parcelable value) { extras.put(name, value); return this; }
    public static Intent createChooser(Intent target, CharSequence title) { return target; }
    public String getStringExtra(String name) { return null; }
    public String getAction() { return null; }
    public int getIntExtra(String name, int defaultValue) {
        Object value = extras.get(name);
        return value instanceof Integer ? ((Integer) value).intValue() : defaultValue;
    }
    public Parcelable getParcelableExtra(String name) { return null; }
}
''',
            "android/content/pm/PackageManager.java": r'''
package android.content.pm;
public class PackageManager {
    public PackageInstaller getPackageInstaller() { return null; }
    public PackageInfo getPackageArchiveInfo(String path, int flags) { return null; }
}
''',
            "android/content/pm/PackageInfo.java": r'''
package android.content.pm;
public class PackageInfo {
    public String packageName;
    public String[] splitNames;
    public Object[] signatures;
    public long versionCode;
    public long getLongVersionCode() { return versionCode; }
}
''',
            "android/content/pm/PackageInstaller.java": r'''
package android.content.pm;
import android.content.IntentSender;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
public class PackageInstaller {
    public static final int MODE_FULL_INSTALL = 1;
    public static final String ACTION_PACKAGE_INSTALLED = "android.content.pm.action.PACKAGE_INSTALLED";
    public static final String EXTRA_SESSION_ID = "android.content.pm.extra.SESSION_ID";
    public static final String EXTRA_STATUS = "android.content.pm.extra.STATUS";
    public static final int STATUS_PENDING_USER_ACTION = -1;
    public static final int STATUS_SUCCESS = 0;
    public static final int STATUS_FAILURE = 1;
    public final List<String> writes = new ArrayList<>();
    public boolean failWrite;
    public boolean committed;
    public boolean closed;
    public int createCount;
    public int abandonedSession = -1;
    public Session session;

    public int createSession(SessionParams params) {
        createCount++;
        session = new Session(this);
        return 42;
    }
    public Session openSession(int sessionId) { return session; }
    public void abandonSession(int sessionId) { abandonedSession = sessionId; }

    public static class SessionParams {
        public static final int MODE_FULL_INSTALL = 1;
        public SessionParams(int mode) {}
        public void setAppPackageName(String packageName) {}
    }
    public static class Session {
        private final PackageInstaller owner;
        Session(PackageInstaller owner) { this.owner = owner; }
        public OutputStream openWrite(final String name, long offsetBytes, long lengthBytes) {
            if (owner.failWrite) throw new IllegalStateException("fixture write failure");
            owner.writes.add(name);
            return new ByteArrayOutputStream();
        }
        public void fsync(OutputStream out) throws IOException {}
        public void commit(IntentSender statusReceiver) { owner.committed = true; }
        public void close() { owner.closed = true; }
    }
}
''',
            "android/app/PendingIntent.java": r'''
package android.app;
import android.content.Context;
import android.content.Intent;
import android.content.IntentSender;
public class PendingIntent {
    public static final int FLAG_MUTABLE = 0x02000000;
    private final IntentSender sender = new IntentSender();
    public static PendingIntent getBroadcast(Context context, int requestCode, Intent intent, int flags) {
        return new PendingIntent();
    }
    public IntentSender getIntentSender() { return sender; }
}
''',
            "com/getcapacitor/JSObject.java": r'''
package com.getcapacitor;
import java.util.LinkedHashMap;
import java.util.Map;
public class JSObject {
    public final Map<String,Object> values = new LinkedHashMap<>();
    public JSObject put(String key, Object value) { values.put(key, value); return this; }
}
''',
            "com/getcapacitor/JSArray.java": r'''
package com.getcapacitor;
public class JSArray {
    public int length() { return 0; }
    public Object opt(int index) { return null; }
}
''',
            "com/getcapacitor/PluginCall.java": r'''
package com.getcapacitor;
public class PluginCall {
    public String rejected;
    public JSObject lastResolved;
    public void resolve(JSObject value) { lastResolved = value; }
    public void reject(String message) { rejected = message; }
    public String getString(String key) { return null; }
    public JSArray getArray(String key) { return null; }
}
''',
        }
        harness = r'''
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.InstalledApkSet;
import com.slgtranslator.app.PackageInstallerSupport;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;

public final class SplitInstallerHarness {
    private static final String PACKAGE = "com.example.game";

    public static void main(String[] args) throws Exception {
        int exit = 0;
        try {
            run(new File(args[0]));
        } catch (Throwable error) {
            error.printStackTrace();
            exit = 1;
        }
        System.exit(exit);
    }

    private static void run(File root) throws Exception {
        File base = write(root, "base.apk");
        File splitA = write(root, "split-a.apk");
        File splitB = write(root, "split-b.apk");
        InstalledApkSet valid = newSet(base, splitA, splitB,
                "feature_a.apk", "feature_b.apk");

        TestPackageManager validManager = new TestPackageManager();
        TestContext validContext = new TestContext(validManager);
        PluginCall validCall = new PluginCall();
        PackageInstallerSupport.installApkSet(validContext, valid, validCall);
        require(validManager.installer.committed, "valid set must commit one session");
        require(validManager.installer.abandonedSession == -1, "valid session must not be abandoned");
        require(validManager.installer.writes.equals(Arrays.asList(
                "base.apk", "feature_a.apk", "feature_b.apk")),
                "write order must be base then declared splits: " + validManager.installer.writes);

        fireSuccess(validContext);
        require(validCall.lastResolved != null, "success status must resolve the call");
        require(Boolean.TRUE.equals(validCall.lastResolved.values.get("installed")),
                "installed must be true on success");
        require(Boolean.FALSE.equals(validCall.lastResolved.values.get("staticAsserts")),
                "staticAsserts must default to false with no caller evidence");
        require(validCall.lastResolved.values.get("splitCount") != null,
                "success result must include splitCount");

        TestContext trueContext = new TestContext(validManager);
        PluginCall trueCall = new PluginCall();
        PackageInstallerSupport.installApkSet(trueContext, valid, trueCall,
                new PackageInstallerSupport.StaticEvidence(true));
        fireSuccess(trueContext);
        require(Boolean.TRUE.equals(trueCall.lastResolved.values.get("staticAsserts")),
                "staticAsserts must reflect true caller evidence");
        require(Boolean.TRUE.equals(trueCall.lastResolved.values.get("installed")),
                "installed must stay independent of staticAsserts");

        TestContext falseContext = new TestContext(validManager);
        PluginCall falseCall = new PluginCall();
        PackageInstallerSupport.installApkSet(falseContext, valid, falseCall,
                new PackageInstallerSupport.StaticEvidence(false));
        fireSuccess(falseContext);
        require(Boolean.FALSE.equals(falseCall.lastResolved.values.get("staticAsserts")),
                "staticAsserts must reflect false caller evidence");
        require(Boolean.TRUE.equals(falseCall.lastResolved.values.get("installed")),
                "installed must stay true even when static asserts fail");

        expectRejectedBeforeSession("package", valid, new TestPackageManager(Mode.PACKAGE));
        expectRejectedBeforeSession("version", valid, new TestPackageManager(Mode.VERSION));
        expectRejectedBeforeSession("signature", valid, new TestPackageManager(Mode.SIGNATURE));
        expectRejectedBeforeSession("split", valid, new TestPackageManager(Mode.SPLIT));

        TestPackageManager writeFailure = new TestPackageManager();
        writeFailure.installer.failWrite = true;
        PluginCall failedCall = new PluginCall();
        PackageInstallerSupport.installApkSet(new TestContext(writeFailure), valid, failedCall);
        require(!writeFailure.installer.committed, "write failure must not commit");
        require(writeFailure.installer.abandonedSession == 42,
                "write failure must abandon the opened session");
        require(failedCall.rejected != null, "write failure must reject the call");

        boolean duplicateRejected = false;
        try {
            newSet(base, splitA, splitB, "feature_a.apk", "feature_a.apk");
        } catch (IllegalArgumentException expected) {
            duplicateRejected = true;
        }
        require(duplicateRejected, "duplicate split names must be rejected before installation");
        System.out.println("writes=" + validManager.installer.writes + ", abandoned="
                + writeFailure.installer.abandonedSession);
    }

    private static void expectRejectedBeforeSession(String label, InstalledApkSet set,
                                                     TestPackageManager manager) {
        PluginCall call = new PluginCall();
        PackageInstallerSupport.installApkSet(new TestContext(manager), set, call);
        require(!manager.installer.committed, label + " mismatch must not commit");
        require(manager.installer.createCount == 0,
                label + " mismatch must be validated before session creation");
        require(manager.installer.abandonedSession == -1,
                label + " mismatch must not create a session to abandon");
        require(call.rejected != null, label + " mismatch must reject the call");
    }

    private static void fireSuccess(TestContext context) {
        context.lastReceiver.onReceive(context, new Intent(
                "android.content.pm.action.PACKAGE_INSTALLED")
                .putExtra(PackageInstaller.EXTRA_SESSION_ID, 42)
                .putExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_SUCCESS));
    }

    private static InstalledApkSet newSet(File base, File splitA, File splitB,
                                           String nameA, String nameB) {
        return new InstalledApkSet(base, Arrays.asList(splitA, splitB), PACKAGE, 17,
                Arrays.asList(nameA, nameB));
    }

    private static File write(File root, String name) throws Exception {
        File file = new File(root, name);
        Files.write(file.toPath(), name.getBytes(StandardCharsets.UTF_8));
        return file;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private enum Mode { NONE, PACKAGE, VERSION, SIGNATURE, SPLIT }

    public static final class TestContext extends Context {
        private final TestPackageManager manager;
        TestContext(TestPackageManager manager) { this.manager = manager; }
        @Override public PackageManager getPackageManager() { return manager; }
        @Override public String getPackageName() { return "com.slgtranslator.app"; }
        @Override public Context getApplicationContext() { return this; }
    }

    public static final class TestPackageManager extends PackageManager {
        final PackageInstaller installer = new PackageInstaller();
        private final Mode mode;
        TestPackageManager() { this(Mode.NONE); }
        TestPackageManager(Mode mode) { this.mode = mode; }
        @Override public PackageInstaller getPackageInstaller() { return installer; }
        @Override public PackageInfo getPackageArchiveInfo(String path, int flags) {
            PackageInfo info = new PackageInfo();
            info.packageName = mode == Mode.PACKAGE && path.endsWith("split-b.apk")
                    ? "com.other.game" : PACKAGE;
            info.versionCode = mode == Mode.VERSION && path.endsWith("split-b.apk") ? 18 : 17;
            String split = path.endsWith("split-a.apk") ? "feature_a"
                    : path.endsWith("split-b.apk") ? "feature_b" : null;
            if (mode == Mode.SPLIT && path.endsWith("split-b.apk")) split = "wrong_name";
            info.splitNames = split == null ? new String[0] : new String[] {split};
            info.signatures = new Object[] {
                    mode == Mode.SIGNATURE && path.endsWith("split-b.apk") ? "other" : "same"
            };
            return info;
        }
    }
}
'''
        with tempfile.TemporaryDirectory(prefix="split-installer-test-") as temporary:
            temporary_path = Path(temporary)
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            classes.mkdir()
            fixture.mkdir()
            source_paths = []
            for relative, content in custom_stubs.items():
                path = temporary_path / "custom-stubs" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                source_paths.append(path)
            harness_path = temporary_path / "SplitInstallerHarness.java"
            harness_path.write_text(harness, encoding="utf-8")
            excluded = {
                "Context.java", "PackageManager.java", "PackageInstaller.java",
                "JSObject.java", "JSArray.java", "PluginCall.java", "PendingIntent.java",
                "Intent.java",
            }
            repository_stubs = [
                path for path in sorted((FAST_SCAN / "stubs").rglob("*.java"))
                if path.name not in excluded
            ]
            compile_result = subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, repository_stubs), *map(str, source_paths),
                    str(INSTALLED_APK_SET),
                    str(FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "PackageInstallerSupport.java"),
                    str(harness_path),
                ],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "SplitInstallerHarness", str(fixture)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("base.apk", result.stdout)

    def test_manifest_pipeline_adds_launcher_queries_without_broad_permission(self):
        builder = BUILDER.read_text("utf-8")
        workshop = WORKSHOP_BUILDER.read_text("utf-8")
        for token in (
            "patch_launcher_queries",
            'android.intent.action.MAIN',
            'android.intent.category.LAUNCHER',
            'GENERATED / "AndroidManifest.xml"',
        ):
            self.assertIn(token, builder)
        self.assertNotIn("QUERY_ALL_PACKAGES", builder)
        self.assertIn('"AndroidManifest.xml": FAST_SCAN_GENERATED / "AndroidManifest.xml"', workshop)

    def test_generated_dex_has_unique_installed_app_bridge(self):
        classes6 = GENERATED / "classes6.dex"
        classes7 = GENERATED / "classes7.dex"
        if not classes6.exists() or not classes7.exists():
            if os.environ.get("REQUIRE_FAST_SCAN_ARTIFACTS") == "1":
                self.fail("required generated DEX files are missing; run build_fast_scanner.py")
            self.skipTest("generated DEX files are not present; run build_fast_scanner.py first")
        self.assertTrue(DEXDUMP.exists(), "generated DEX verification requires dexdump.exe")

        def dump(path, disassemble=False):
            completed = subprocess.run(
                [
                    str(DEXDUMP),
                    *(["-d"] if disassemble else []),
                    str(path.relative_to(ROOT)),
                ],
                check=True,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            return completed.stdout

        plugin_dump = dump(classes6)
        plugin_code = re.sub(r"\s+", "", dump(classes6, disassemble=True))
        helper_dump = dump(classes7)
        helper_code = re.sub(r"\s+", "", dump(classes7, disassemble=True))
        self.assertEqual(plugin_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'selectInstalledApp'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'listSaveGameApps'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'enableWorkshopBackHandling'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'listSaveArchives'"), 1)
        self.assertEqual(plugin_dump.count("name          : 'importSaveBackup'"), 1)
        self.assertIn(
            "Lcom/getcapacitor/Plugin;.getActivity:()"
            "Landroidx/appcompat/app/AppCompatActivity;",
            plugin_code,
        )
        self.assertNotIn(
            "Lcom/getcapacitor/Plugin;.getActivity:()Landroid/app/Activity;",
            plugin_code,
        )
        self.assertEqual(
            helper_dump.count("Class descriptor  : 'Lcom/slgtranslator/app/InstalledAppSource;'"),
            1,
        )
        self.assertEqual(helper_dump.count("name          : 'listInstalledApps'"), 1)
        self.assertEqual(helper_dump.count("name          : 'selectInstalledApp'"), 1)
        self.assertEqual(helper_dump.count("name          : 'listSaveGameApps'"), 1)
        self.assertEqual(
            helper_dump.count("Class descriptor  : 'Lcom/slgtranslator/app/WorkshopBackHandler;'"),
            1,
        )

        self.assertEqual(helper_dump.count("name          : 'enable'"), 1)
        self.assertEqual(helper_dump.count("name          : 'delegateDefaultBack'"), 1)

        actual_methods = set()
        for base_dex in sorted((ROOT / "apk-work" / "extracted").glob("classes*.dex")):
            base_dump = dump(base_dex)
            for block in re.split(r"(?=Class #\d+\s+-)", base_dump):
                owner_match = re.search(r"Class descriptor\s+: '([^']+)'", block)
                if not owner_match:
                    continue
                owner = owner_match.group(1)
                for name, descriptor in re.findall(
                    r"name\s+: '([^']+)'\s+type\s+: '(\([^']+)'",
                    block,
                ):
                    actual_methods.add((owner, name, descriptor))

        # Only inspect code introduced by the back-handler feature.  classes7.dex
        # also contains the older scanner implementation, whose JSArray calls may
        # legally resolve through its org.json superclass and are unrelated here.
        plugin_method = re.search(
            r"com\.slgtranslator\.app\.FileManagerPlugin\."
            r"enableWorkshopBackHandling:.*?(?=catches:)",
            plugin_code,
        )
        self.assertIsNotNone(plugin_method)
        external_invokes = set(
            re.findall(
                r"invoke-(?:virtual|interface|static|direct)(?:/range)?"
                r"\{[^}]*\},"
                r"(Lcom/getcapacitor/[^;]+;)\.([^:]+):(.+?)//method@",
                plugin_method.group(0),
            )
        )
        external_invokes.update(
            re.findall(
                r"invoke-(?:virtual|interface|static|direct)(?:/range)?"
                r"\{[^}]*\},"
                r"(Landroidx/(?:activity|lifecycle)/[^;]+;)"
                r"\.([^:]+):(.+?)//method@",
                helper_code,
            )
        )
        scanner_method = re.search(
            r"com\.slgtranslator\.app\.FastApkScanner\.scanAsync:.*?(?=catches:)",
            helper_code,
        )
        self.assertIsNotNone(scanner_method)
        external_invokes.update(
            re.findall(
                r"invoke-(?:virtual|interface|static|direct)(?:/range)?"
                r"\{[^}]*\},(Lcom/getcapacitor/[^;]+;)"
                r"\.([^:]+):(.+?)//method@",
                scanner_method.group(0),
            )
        )
        self.assertTrue(external_invokes)
        platform_inherited = {
            ("Landroidx/activity/ComponentActivity;", "isDestroyed", "()Z"),
            ("Landroidx/activity/ComponentActivity;", "isFinishing", "()Z"),
        }
        for target in sorted(external_invokes):
            if target in platform_inherited:
                continue
            self.assertIn(
                target,
                actual_methods,
                f"generated external invoke is absent from real base ABI: {target}",
            )

    def test_task16_release_artifacts_and_unsupported_gate_are_pinned(self):
        """Release docs and the built helper must expose the Task 16 gates."""
        self.assertTrue(COMPATIBILITY_MATRIX.exists(), "Task 16 compatibility matrix is missing")
        self.assertTrue(RELEASE_CHECKLIST.exists(), "Task 16 release checklist is missing")
        matrix = COMPATIBILITY_MATRIX.read_text("utf-8")
        checklist = RELEASE_CHECKLIST.read_text("utf-8")
        for token in (
            "supportLevel", "activationStrategy", "templatePath", "missing",
            "font result", "build allowed", "install success",
            "startup translation observed", "not-run", "UNSUPPORTED",
            "RPA-1", "RPA-2", "RPA-3", "base + split", "rejected",
        ):
            self.assertIn(token, matrix)
        for token in (
            "python -m unittest discover -s . -p 'test_*.py' -v",
            "python build_workshop_apk.py", "RenpyPatchValidator", "missing == 0",
            "rejected == 0", "EXTRACT_ONLY", "UNSUPPORTED", "old save",
        ):
            self.assertIn(token, checklist)

        builder = BUILDER.read_text("utf-8")
        self.assertIn("d8.args", builder)
        self.assertIn('"@" + str(d8_args)', builder)
        classes6 = GENERATED / "classes6.dex"
        classes7 = GENERATED / "classes7.dex"
        if not classes6.exists() or not classes7.exists():
            self.skipTest("generated DEX artifacts are not present; run build_fast_scanner.py first")
        self.assertTrue(DEXDUMP.exists(), "Task 16 artifact gate requires dexdump.exe")
        dump = subprocess.run(
            [str(DEXDUMP), str(classes7.relative_to(ROOT))],
            check=True,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        ).stdout
        for class_name in (
            "FastApkScanner", "InstalledApkSet", "InstalledAppSource",
            "PackageInstallerSupport", "RenpyPatchValidator", "RenpyPreflight",
        ):
            self.assertIn(class_name, dump)


    def test_language_menu_support_rewrites_expendable_slot(self):
        support = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "LanguageMenuSupport.java"
        self.assertTrue(support.exists(), "LanguageMenuSupport.java must exist")
        source = support.read_text("utf-8")
        for token in (
            "injectTranslatorMenu",
            "rewriteButton",
            "rewriteApkMenu",
            'Language(\\"',
            "translatorLang",
            "\\u7ffb\\u8bd1\\u6587\\u672c",
            "0x95",
            "STATUS_ALREADY",
            "menuHasLanguage",
            'result.put("ready"',
            "STATUS_ALREADY",
            "menuHasLanguage",
            'result.put("ready"',
            "RpycStreamValidator.requireValid(rewritten",
            "!menuHasLanguage(rewritten, translatorLang)",
        ):
            self.assertIn(token, source)
        self.assertNotIn("spliceButton", source)
        builder = BUILDER.read_text("utf-8")
        for token in (
            "INJECT_MENU_SIGNATURE",
            "LanguageMenuSupport;->injectTranslatorMenu",
        ):
            self.assertIn(token, builder)

    def test_language_menu_support_resolves_content_uri_and_is_idempotent(self):
        """A DocumentsUI content URI must become the writable menu-injected APK copy."""
        fixture = build_underscore_menu_fixture_rpyc()
        custom_stubs = {
            "android/net/Uri.java": r'''
package android.net;
import android.os.Parcelable;
import java.io.File;
public class Uri implements Parcelable {
    private final String value;
    private Uri(String value) { this.value = value; }
    public static Uri parse(String value) { return new Uri(value); }
    public String getPath() {
        return value.startsWith("file://") ? value.substring("file://".length()) : value;
    }
    public static Uri fromFile(File file) { return new Uri("file://" + file.getAbsolutePath()); }
    public String toString() { return value; }
}
''',
            "android/content/ContentResolver.java": r'''
package android.content;
import android.net.Uri;
import java.io.InputStream;
public class ContentResolver {
    public InputStream openInputStream(Uri uri) { return null; }
}
''',
            "android/content/Context.java": r'''
package android.content;
import java.io.File;
public class Context {
    public ContentResolver getContentResolver() { return null; }
    public File getCacheDir() { return null; }
    public File getFilesDir() { return null; }
    public File getExternalFilesDir(String type) { return null; }
}
''',
            "com/getcapacitor/JSObject.java": r'''
package com.getcapacitor;
import java.util.LinkedHashMap;
import java.util.Map;
public class JSObject {
    public final Map<String,Object> values = new LinkedHashMap<>();
    public JSObject put(String key, Object value) { values.put(key, value); return this; }
}
''',
            "com/getcapacitor/PluginCall.java": r'''
package com.getcapacitor;
public class PluginCall {
    public String getString(String key) { return null; }
    public void resolve(JSObject value) {}
    public void reject(String message) {}
}
''',
        }
        harness = r'''
package com.slgtranslator.app;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipFile;

public final class ContentUriMenuHarness {
    private static final String SOURCE_URI = "content://fixture/menu.apk";

    public static void main(String[] args) throws Exception {
        byte[] source = Files.readAllBytes(Paths.get(args[0]));
        File root = new File(args[1]);
        root.mkdirs();
        File external = new File(root, "external");
        File internal = new File(root, "internal");
        external.mkdirs();
        internal.mkdirs();
        TestContext context = new TestContext(internal, external, source);

        TestCall first = new TestCall(SOURCE_URI);
        LanguageMenuSupport.injectTranslatorMenu(context, null, first);
        require(first.await(), "first call timed out");
        require(first.rejected == null, "content URI must resolve: " + first.rejected);
        require(first.resolved != null, "content URI call must resolve");
        String resolvedUri = String.valueOf(first.resolved.values.get("resolvedApkUri"));
        require(resolvedUri.startsWith("file://"), "resolved URI must be file://: " + resolvedUri);
        File resolved = new File(Uri.parse(resolvedUri).getPath());
        require(resolved.isFile(), "resolved copy must exist: " + resolved);
        require(resolved.getCanonicalPath().startsWith(external.getCanonicalPath() + File.separator),
                "resolved copy must prefer external files: " + resolved);
        require(Boolean.TRUE.equals(first.resolved.values.get("changed")), "first call must report changed");
        require(Boolean.TRUE.equals(first.resolved.values.get("ready")), "first call must be ready");
        require(LanguageMenuSupport.menuHasLanguage(Files.readAllBytes(resolved.toPath()), "slgtranslated"),
                "resolved copy must contain the injected language");
        try (ZipFile zip = new ZipFile(resolved)) {
            require(zip.getEntry("assets/game/fixture.rpyc") != null, "rewritten APK must remain a readable ZIP");
        }

        TestCall second = new TestCall(resolvedUri);
        LanguageMenuSupport.injectTranslatorMenu(context, null, second);
        require(second.await(), "second call timed out");
        require(second.rejected == null, "resolved URI must remain idempotent: " + second.rejected);
        require(Boolean.TRUE.equals(second.resolved.values.get("ready")), "second call must remain ready");
        require(Boolean.FALSE.equals(second.resolved.values.get("changed")), "second call must not rewrite again");
        require(LanguageMenuSupport.menuHasLanguage(Files.readAllBytes(resolved.toPath()), "slgtranslated"),
                "idempotent call must preserve the injected language");
        System.out.println("resolved=" + resolvedUri);
    }

    private static final class TestContext extends Context {
        private final File internal;
        private final File external;
        private final TestResolver resolver;
        TestContext(File internal, File external, byte[] source) {
            this.internal = internal;
            this.external = external;
            this.resolver = new TestResolver(source);
        }
        @Override public ContentResolver getContentResolver() { return resolver; }
        @Override public File getCacheDir() { return internal; }
        @Override public File getFilesDir() { return internal; }
        @Override public File getExternalFilesDir(String type) { return external; }
    }

    private static final class TestResolver extends ContentResolver {
        private final byte[] source;
        TestResolver(byte[] source) { this.source = source; }
        @Override public InputStream openInputStream(Uri uri) {
            if (!SOURCE_URI.equals(uri.toString())) throw new IllegalArgumentException("unexpected URI");
            return new ByteArrayInputStream(source);
        }
    }

    private static final class TestCall extends PluginCall {
        private final String apkUri;
        private final CountDownLatch done = new CountDownLatch(1);
        JSObject resolved;
        String rejected;
        TestCall(String apkUri) { this.apkUri = apkUri; }
        @Override public String getString(String key) {
            if ("apkUri".equals(key)) return apkUri;
            if ("gameTargetLang".equals(key)) return "schinese";
            if ("translatorLang".equals(key)) return "slgtranslated";
            return null;
        }
        @Override public void resolve(JSObject value) { resolved = value; done.countDown(); }
        @Override public void reject(String message) { rejected = message; done.countDown(); }
        boolean await() throws InterruptedException { return done.await(10, TimeUnit.SECONDS); }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
'''
        with tempfile.TemporaryDirectory(prefix="content-uri-menu-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_apk = temporary_path / "source.apk"
            with zipfile.ZipFile(fixture_apk, "w") as archive:
                archive.writestr("assets/game/fixture.rpyc", fixture)
            classes = temporary_path / "classes"
            classes.mkdir()
            harness_path = temporary_path / "ContentUriMenuHarness.java"
            harness_path.write_text(harness, encoding="utf-8")
            source_paths = []
            for relative, content in custom_stubs.items():
                path = temporary_path / "custom-stubs" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                source_paths.append(path)
            repository_stubs = [FAST_SCAN / "stubs" / "android/os/Parcelable.java"]
            compile_result = subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, repository_stubs), *map(str, source_paths),
                    str(FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "LanguageMenuSupport.java"),
                    str(FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycStreamValidator.java"),
                    str(harness_path),
                ],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(
                [str(JAVA), "-cp", os.pathsep.join([str(classes), third_party_classpath()]),
                 "com.slgtranslator.app.ContentUriMenuHarness", str(fixture_apk),
                 str(temporary_path / "app-files")],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_emits_selectable_and_always_on_artifacts(self):
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.InflaterInputStream;

public final class TranslationCompilerActivationHarness {
    public static void main(String[] args) throws Exception {
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 7;
        meta.key = "unlocked";
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"same old", "same new"});
        pairs.add(new String[]{"second old", "second new"});

        TranslationCompiler.TranslationArtifact selectable =
                TranslationCompiler.compileTranslationArtifact("selectable", pairs, meta);
        require("selectable".equals(selectable.activationMode), "selectable activation mode");
        require("slgtranslated".equals(selectable.translatorLanguage), "selectable language");
        require("assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc".equals(
                selectable.compiledPath), "selectable path");
        require("game/tl/slgtranslated/translations.rpy".equals(
                selectable.runtimeFilename), "selectable runtime filename");
        require(!hasNullTranslateStringLanguage(inflateSlot(selectable.rpyc)),
                "selectable TranslateString language must be a string");

        TranslationCompiler.TranslationArtifact alwaysOn =
                TranslationCompiler.compileTranslationArtifact("always_on", pairs, meta);
        require("always_on".equals(alwaysOn.activationMode), "always-on activation mode");
        require(alwaysOn.translatorLanguage == null, "always-on language must be null");
        require("assets/x-game/x-tl/x-None/x-slgtranslator-translations.rpyc".equals(
                alwaysOn.compiledPath), "always-on path");
        require("game/tl/None/slgtranslator-translations.rpy".equals(
                alwaysOn.runtimeFilename), "always-on runtime filename");
        require(hasNullTranslateStringLanguage(inflateSlot(alwaysOn.rpyc)),
                "always-on TranslateString language must be pickle NONE");
        RenpyPatchValidator.Result alwaysOnValidation = RenpyPatchValidator.validateCompiledRpyc(
                alwaysOn.rpyc, 7, "unlocked", null, pairs.size());
        require(alwaysOnValidation.valid,
                "always-on NONE language must pass the structural validator: "
                        + alwaysOnValidation.code);
    }

    private static byte[] inflateSlot(byte[] rpyc) throws Exception {
        int pos = "RENPY RPC2".length();
        while (pos + 12 <= rpyc.length) {
            int id = le(rpyc, pos);
            int offset = le(rpyc, pos + 4);
            int length = le(rpyc, pos + 8);
            if (id == 2) {
                InflaterInputStream in = new InflaterInputStream(
                        new ByteArrayInputStream(rpyc, offset, length));
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buffer = new byte[1024];
                int read;
                while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
                return out.toByteArray();
            }
            if (id == 0) break;
            pos += 12;
        }
        throw new AssertionError("RPC2 slot 2 missing");
    }

    private static boolean hasNullTranslateStringLanguage(byte[] pickle) {
        byte[] key = new byte[]{(byte) 0x8c, 8, 'l', 'a', 'n', 'g', 'u', 'a', 'g', 'e'};
        for (int i = 0; i + key.length + 1 < pickle.length; i++) {
            boolean match = true;
            for (int j = 0; j < key.length; j++) {
                if (pickle[i + j] != key[j]) {
                    match = false;
                    break;
                }
            }
            if (match) return (pickle[i + key.length] & 0xff) == 0x4e;
        }
        throw new AssertionError("TranslateString language key missing");
    }

    private static int le(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-activation-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerActivationHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerActivationHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_dialogue_rewriter_rewrites_say_what_only(self):
        """Always-on fallback must rewrite serialized Say.what dialogue text."""
        rewriter = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycDialoguePatcher.java"
        self.assertTrue(rewriter.is_file(), "dialogue patcher regression path is missing")
        fixture = build_adjacent_dialogue_speaker_fixture_rpyc()
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class RpycDialoguePatcherHarness {
    public static void main(String[] args) throws Exception {
        byte[] source = Files.readAllBytes(Paths.get(args[0]));
        Map<String, String> translations = new LinkedHashMap<>();
        translations.put("First adjacent line", "第一句");
        translations.put("Second adjacent line", "第二句");
        byte[] rewritten = RpycDialoguePatcher.rewriteSayTexts(source, translations);
        require(rewritten != null, "rewriter must return a changed RPYC");
        if (args.length > 1) {
            Files.write(Paths.get(args[1]), rewritten);
        }
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                rewritten, "game/speakers.rpyc", false);
        for (RenpyTextRecord record : records) {
            System.err.println("RECORD=" + record.kind + "|" + record.speaker + "|" + record.text);
        }
        require(find(records, "第一句", "alice"), "first Say.what must be translated");
        require(find(records, "第二句", ""), "second Say.what must be translated");
        require(!find(records, "First adjacent line", "alice"),
                "old dialogue text must not remain in the first Say node");
    }

    private static boolean find(List<RenpyTextRecord> records, String text, String speaker) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)
                    && record.kind == RenpyTextRecord.Kind.DIALOGUE
                    && speaker.equals(record.speaker)) {
                return true;
            }
        }
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="rpyc-dialogue-patcher-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "RpycDialoguePatcherHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, sorted((FAST_SCAN / "stubs").rglob("*.java"))),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            rewritten_path = ROOT / "apk-work" / "ui-redesign" / "qa" / "tmp" / "rpyc-dialogue-rewritten.rpyc"
            rewritten_path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RpycDialoguePatcherHarness", str(fixture_path),
                 str(rewritten_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_translation_compiler_handles_large_real_file_pair_counts(self):
        """A real Ren'Py file can contain thousands of strings; validation must not desynchronize."""
        harness = r"""
package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.List;

public final class TranslationCompilerLargeArtifactHarness {
    public static void main(String[] args) throws Exception {
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 7;
        meta.key = "unlocked";
        List<String[]> pairs = new ArrayList<>();
        for (int i = 0; i < 2624; i++) {
            pairs.add(new String[]{
                    "source line " + i + " with enough words to exercise the compiler",
                    "translated line " + i + " with enough words to exercise the compiler"
            });
        }
        TranslationCompiler.TranslationArtifact artifact =
                TranslationCompiler.compileTranslationArtifact("always_on", pairs, meta);
        require(artifact.rpyc.length > 0, "large artifact must be non-empty");
        RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                artifact.rpyc, 7, "unlocked", null, pairs.size());
        require(validation.valid && validation.decodedPairCount == pairs.size(),
                "large artifact must validate: " + validation.code + ": " + validation.message);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-large-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerLargeArtifactHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerLargeArtifactHarness"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_pending_entry_store_is_file_backed(self):
        store_source = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "PendingApkEntryStore.java"
        self.assertTrue(store_source.is_file(), "PendingApkEntryStore.java must exist")
        source = store_source.read_text("utf-8")
        for token in (
            "openPayload",
            "inMemoryPayloadBytes",
            "replace",
            "FileOutputStream",
            "close()",
        ):
            self.assertIn(token, source)

        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;

public final class PendingApkEntryStoreHarness {
    public static void main(String[] args) throws Exception {
        File directory = new File(args[0]);
        PendingApkEntryStore store = new PendingApkEntryStore(directory);
        for (int i = 0; i < 24; i++) {
            store.add("generated/" + i, "runtime/" + i, new byte[8 * 1024 * 1024]);
        }
        require(store.size() == 24, "all entries must be indexed");
        require(store.inMemoryPayloadBytes() == 0, "payloads must be file-backed after add");
        try (InputStream input = store.openPayload(0)) {
            require(input.read() == 0, "payload must be readable");
        }
        store.replace(0, new byte[]{7, 8, 9});
        try (InputStream input = store.openPayload(0)) {
            require(input.read() == 7 && input.read() == 8 && input.read() == 9,
                    "replace must update the file-backed payload");
        }
        store.close();
        require(!directory.exists(), "close must remove the temporary store");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="pending-entry-store-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "PendingApkEntryStoreHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.PendingApkEntryStoreHarness",
                 str(temporary_path / "store")],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_handles_large_protocol2_artifacts(self):
        """The legacy-compatible writer must validate thousands of BINUNICODE values."""
        harness = r"""
package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.List;

public final class TranslationCompilerLargeProtocol2Harness {
    public static void main(String[] args) throws Exception {
        List<String[]> pairs = new ArrayList<>();
        for (int i = 0; i < 2624; i++) {
            pairs.add(new String[]{
                    "source line " + i + " with enough words to exercise the compiler",
                    "translated line " + i + " with enough words to exercise the compiler"
            });
        }
        byte[] template = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                pairs.subList(0, 1), 17, "fixture-key");
        RpycCompatibility.Report report = RpycCompatibility.inspect(
                TranslationCompilerTestSupport.rpc2(template));
        require(report.isProtocol2WriterCompatible(),
                "fixture must select protocol 2: " + report.reason);
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 17;
        meta.key = "fixture-key";
        meta.compatibility = report;
        TranslationCompiler.TranslationArtifact artifact =
                TranslationCompiler.compileTranslationArtifact("always_on", pairs, meta);
        RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                artifact.rpyc, 17, "fixture-key", null, pairs.size());
        require(validation.valid && validation.decodedPairCount == pairs.size(),
                "large protocol-2 artifact must validate: "
                        + validation.code + ": " + validation.message);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        support = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.DeflaterOutputStream;

final class TranslationCompilerTestSupport {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    static byte[] rpc2(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        byte[] slot = compressed.toByteArray();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int dataStart = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            writeIntLe(out, id);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot);
        out.write(slot);
        return out.toByteArray();
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-large-protocol2-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerLargeProtocol2Harness.java"
            support_path = temporary_path / "TranslationCompilerTestSupport.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            support_path.write_text(support, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(support_path), str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerLargeProtocol2Harness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_replays_current_device_xnone_outputs(self):
        """Every validator-safe file from the current real-device run must compile independently."""
        fixture = (ROOT / "apk-work" / "ui-redesign" / "qa"
                   / "device-run-20260808-xnone" / "x-v0.1")
        if not fixture.is_dir():
            self.skipTest("current real-device x-None output is not available")
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.zip.DeflaterOutputStream;

public final class TranslationCompilerCurrentDeviceHarness {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    public static void main(String[] args) throws Exception {
        Path root = Paths.get(args[0]);
        byte[] template = rpc2(RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                java.util.Collections.singletonList(new String[]{"template", "模板"}),
                7, "unlocked"));
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 7;
        meta.key = "unlocked";
        meta.compatibility = RpycCompatibility.inspect(template);
        int files = 0;
        int pairs = 0;
        List<String[]> allPairs = new ArrayList<>();
        try (java.util.stream.Stream<Path> paths = Files.list(root)) {
            for (Path path : (Iterable<Path>) paths.filter(p -> p.toString().endsWith(".rpy"))
                    .sorted(Comparator.comparing(Path::toString))::iterator) {
                List<String[]> safe = new ArrayList<>();
                String content = new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
                for (String[] pair : TranslationCompiler.parseTranslationRpy(content)) {
                    if (RenpyTextValidator.validate(pair[0], pair[1]).valid) {
                        safe.add(pair);
                    }
                }
                if (safe.isEmpty()) continue;
                allPairs.addAll(safe);
                try {
                    TranslationCompiler.TranslationArtifact artifact =
                            TranslationCompiler.compileTranslationArtifact("always_on", safe, meta);
                    RenpyPatchValidator.Result result = RenpyPatchValidator.validateCompiledRpyc(
                            artifact.rpyc, 7, "unlocked", null, safe.size());
                    require(result.valid && result.decodedPairCount == safe.size(),
                            "validation failed: " + result.code + ": " + result.message);
                } catch (Throwable error) {
                    System.err.println("FAILED_FILE=" + path + " PAIRS=" + safe.size());
                    error.printStackTrace();
                    throw error;
                }
                files++;
                pairs += safe.size();
            }
        }
        require(files == 9, "expected nine current device script outputs, got " + files);
        require(pairs > 8000, "expected current device corpus pairs, got " + pairs);
        try {
            TranslationCompiler.TranslationArtifact aggregate =
                    TranslationCompiler.compileTranslationArtifact("always_on", allPairs, meta);
            RenpyPatchValidator.Result result = RenpyPatchValidator.validateCompiledRpyc(
                    aggregate.rpyc, 7, "unlocked", null, allPairs.size());
            require(result.valid && result.decodedPairCount == allPairs.size(),
                    "aggregate validation failed: " + result.code + ": " + result.message);
        } catch (Throwable error) {
            System.err.println("FAILED_AGGREGATE PAIRS=" + allPairs.size());
            error.printStackTrace();
            throw error;
        }
        System.out.println("files=" + files + " pairs=" + pairs);
    }

    private static byte[] rpc2(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        byte[] slot = compressed.toByteArray();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int dataStart = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            writeIntLe(out, id);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot);
        out.write(slot);
        return out.toByteArray();
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-current-device-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerCurrentDeviceHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerCurrentDeviceHarness",
                 str(fixture)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_handles_real_device_mojibake_pairs(self):
        """The protocol-2 writer must validate the real 2624-pair device corpus."""
        fixture = Path(
            r"D:\renpy-device-output2\SLG-Translator-Output\assets\x-game\x-tl"
            r"\x-chinese\x-script\x-v0.1\x-chapter6.rpy"
        )
        if not fixture.is_file():
            self.skipTest("pulled second device translation output is not available")
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.DeflaterOutputStream;

public final class TranslationCompilerRealDeviceHarness {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    public static void main(String[] args) throws Exception {
        String content = new String(Files.readAllBytes(Paths.get(args[0])),
                StandardCharsets.UTF_8);
        List<String[]> pairs = TranslationCompiler.parseTranslationRpy(content);
        require(pairs.size() == 2624, "expected 2624 pairs, got " + pairs.size());
        List<String[]> normalizedPairs = new ArrayList<>();
        for (String[] pair : pairs) {
            String restored = restoreTokenCasing(pair[0], pair[1]);
            if (restored != null) {
                normalizedPairs.add(new String[]{pair[0], restored});
            }
        }
        require(normalizedPairs.size() > 2000,
                "placeholder-safe device corpus must retain most pairs: " + normalizedPairs.size());

        byte[] template = rpc2(RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                pairs.subList(0, 1), 7, "unlocked"));
        RpycCompatibility.Report report = RpycCompatibility.inspect(template);
        require(report.isProtocol2WriterCompatible(),
                "fixture compatibility must select protocol 2: " + report.reason);
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 7;
        meta.key = "unlocked";
        meta.compatibility = report;
        TranslationCompiler.TranslationArtifact artifact =
                TranslationCompiler.compileTranslationArtifact("always_on", normalizedPairs, meta);
        require(artifact.rpyc.length > 0, "real device artifact must be non-empty");
        System.out.println("pairs=" + normalizedPairs.size() + " rpyc=" + artifact.rpyc.length);
    }

    private static String restoreTokenCasing(String oldText, String newText) {
        Matcher oldMatcher = TOKEN.matcher(oldText == null ? "" : oldText);
        Matcher newMatcher = TOKEN.matcher(newText == null ? "" : newText);
        List<String> oldTokens = new ArrayList<>();
        while (oldMatcher.find()) oldTokens.add(oldMatcher.group());
        List<String> newTokens = new ArrayList<>();
        while (newMatcher.find()) newTokens.add(newMatcher.group());
        if (oldTokens.size() != newTokens.size()) return null;
        StringBuilder out = new StringBuilder(newText == null ? "" : newText);
        for (int i = newTokens.size() - 1; i >= 0; i--) {
            int start = out.lastIndexOf(newTokens.get(i));
            if (start < 0) return null;
            out.replace(start, start + newTokens.get(i).length(), oldTokens.get(i));
        }
        return out.toString();
    }

    private static byte[] rpc2(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        byte[] slot = compressed.toByteArray();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int dataStart = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            writeIntLe(out, id);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot);
        out.write(slot);
        return out.toByteArray();
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static final Pattern TOKEN = Pattern.compile(
            "\\{\\{|\\[\\[|\\{[^}]*\\}|\\[[^]]*\\]|%\\d*\\$?[sdif]|\\$[A-Za-z_][A-Za-z0-9_]*");
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-real-device-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerRealDeviceHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerRealDeviceHarness",
                 str(fixture)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_rpyc_extractor_handles_real_device_chapter6_source(self):
        """The real chapter-six source RPYC must be readable before compilation."""
        fixture = Path(r"D:\renpy-device-output2\ch6-source.rpyc")
        if not fixture.is_file():
            self.skipTest("pulled real chapter-six source RPYC is not available")
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public final class RealDeviceChapter6SourceHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        RpycCompatibility.Report report = RpycCompatibility.inspect(bytes);
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        if (texts.isEmpty()) {
            throw new AssertionError("chapter-six source must expose dialogue text; support="
                    + report.generationSupport + " reason=" + report.reason);
        }
        System.out.println("support=" + report.generationSupport + " texts=" + texts.size());
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="real-device-chapter6-rpyc-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RealDeviceChapter6SourceHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RealDeviceChapter6SourceHarness", str(fixture)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_handles_validator_safe_device_outputs_in_one_bucket(self):
        """Every validator-safe file in one real bucket must compile independently."""
        fixture = Path(r"D:\renpy-device-output2\SLG-Translator-Output")
        if not fixture.is_dir():
            self.skipTest("pulled second device translation output is not available")
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;
import java.util.zip.DeflaterOutputStream;

public final class TranslationCompilerAllDeviceOutputsHarness {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    public static void main(String[] args) throws Exception {
        List<String[]> allSafePairs = new ArrayList<>();
        List<List<String[]>> units = new ArrayList<>();
        int files = 0;
        int rejected = 0;
        try (Stream<Path> paths = Files.walk(Paths.get(args[0]))) {
            for (Path path : (Iterable<Path>) paths::iterator) {
                if (!path.toString().endsWith(".rpy")) continue;
                String normalizedPath = path.toString().replace('\\', '/').toLowerCase();
                if (!normalizedPath.contains("/x-tl/x-none/")) continue;
                files++;
                String content = new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
                List<String[]> filePairs = new ArrayList<>();
                for (String[] pair : TranslationCompiler.parseTranslationRpy(content)) {
                    RenpyTextValidator.ValidationResult validation =
                            RenpyTextValidator.validate(pair[0], pair[1]);
                    if (validation.valid) {
                        filePairs.add(pair);
                        allSafePairs.add(pair);
                    } else {
                        rejected++;
                    }
                }
                if (!filePairs.isEmpty()) {
                    units.add(filePairs);
                }
            }
        }
        require(files >= 100, "expected the complete device output set, files=" + files);
        require(units.size() >= 100, "expected validator-safe pairs in most device files, units=" + units.size());
        require(allSafePairs.size() > 5000,
                "expected thousands of validator-safe pairs, pairs=" + allSafePairs.size());
        byte[] template = rpc2(RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                allSafePairs.subList(0, 1), 7, "unlocked"));
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 7;
        meta.key = "unlocked";
        meta.compatibility = RpycCompatibility.inspect(template);
        int compiledFiles = 0;
        int compiledPairs = 0;
        for (List<String[]> filePairs : units) {
            TranslationCompiler.TranslationArtifact artifact =
                    TranslationCompiler.compileTranslationArtifact("always_on", filePairs, meta);
            RenpyPatchValidator.Result result = RenpyPatchValidator.validateCompiledRpyc(
                    artifact.rpyc, 7, "unlocked", null, filePairs.size());
            require(result.valid && result.decodedPairCount == filePairs.size(),
                    "safe device file must validate: " + result.code + ": " + result.message);
            compiledFiles++;
            compiledPairs += filePairs.size();
        }
        require(compiledFiles == units.size(), "all safe device files must compile independently");
        System.out.println("files=" + files + " units=" + units.size()
                + " pairs=" + compiledPairs + " rejected=" + rejected);
    }

    private static byte[] rpc2(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        byte[] slot = compressed.toByteArray();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int dataStart = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            writeIntLe(out, id);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot);
        out.write(slot);
        return out.toByteArray();
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-all-device-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerAllDeviceOutputsHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerAllDeviceOutputsHarness",
                 str(fixture)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_uses_requested_item_paths_and_activation_bucket(self):
        """The native compiler must ignore foreign language buckets in the current request."""
        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import org.json.JSONObject;

public final class TranslationCompilerRequestedPathHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File apk = new File(root, "fixture.apk");
        File cache = new File(root, "cache");
        File external = new File(root, "external");
        cache.mkdirs();
        external.mkdirs();

        byte[] pickle = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                Arrays.<String[]>asList(new String[]{"Hello", "Hello"}), 17, "fixture-key");
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/x-game/x-script.rpyc", deflate(pickle));
            put(out, "assets/fonts/cjk.ttf", "CJK");
            put(out, "assets/x-game/x-tl/x-chinese/x-style.rpyc",
                    "line_break east_asian text_font");
        }
        TranslationCompiler.TemplateMeta detected = TranslationCompiler.readTemplateMeta(apk);
        require(detected.compatibility != null && detected.compatibility.canGenerate(),
                "fixture template must reach compiler: "
                        + (detected.compatibility == null ? "null" : detected.compatibility.reason));

        File requested = new File(external,
                "SLG-Translator-Output/assets/x-game/x-tl/x-None/current.rpy");
        requested.getParentFile().mkdirs();
        Files.write(requested.toPath(), (
                "translate None strings:\n"
                + "    old \"Hello\"\n"
                + "    new \"translated\"\n").getBytes(StandardCharsets.UTF_8));

        File foreign = new File(external,
                "SLG-Translator-Output/assets/x-game/x-tl/x-english/foreign.rpy");
        foreign.getParentFile().mkdirs();
        Files.write(foreign.toPath(), (
                "translate english strings:\n"
                + "    old \"Hello\"\n"
                + "    new \"foreign\"\n").getBytes(StandardCharsets.UTF_8));

        File sameBucketConflict = new File(external,
                "SLG-Translator-Output/assets/x-game/x-tl/x-None/second.rpy");
        sameBucketConflict.getParentFile().mkdirs();
        Files.write(sameBucketConflict.toPath(), (
                "translate None strings:\n"
                + "    old \"Hello\"\n"
                + "    new \"second translation\"\n").getBytes(StandardCharsets.UTF_8));

        RequestedItems items = new RequestedItems(
                "assets/x-game/x-tl/x-None/current.rpy",
                "assets/x-game/x-tl/x-english/foreign.rpy",
                "assets/x-game/x-tl/x-None/second.rpy");
        TestCall call = new TestCall(apk.getAbsolutePath(), items);
        TranslationCompiler.compileTranslationsIntoApk(
                new TestContext(cache, external), call);
        require(call.rejected == null,
                "current request must compile with cross-file collision fallback: " + call.rejected);
        require(call.resolved != null, "current request must resolve a compile result");
        try (ZipFile zip = new ZipFile(apk)) {
            int generated = 0;
            java.util.Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                String name = entries.nextElement().getName();
                if (name.startsWith("assets/x-game/x-tl/x-None/x-slgtranslator-")
                        && name.endsWith(".rpyc")) {
                    generated++;
                }
            }
            require(generated == 2,
                    "cross-file conflict must produce one compiled artifact per source file: "
                            + generated);
        }
    }

    private static byte[] deflate(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        return compressed.toByteArray();
    }

    private static void put(ZipOutputStream out, String name, String body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body.getBytes(StandardCharsets.UTF_8));
        out.closeEntry();
    }

    private static void put(ZipOutputStream out, String name, byte[] body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body);
        out.closeEntry();
    }

    private static final class TestContext extends Context {
        private final File cache;
        private final File external;

        TestContext(File cache, File external) {
            this.cache = cache;
            this.external = external;
        }

        @Override public File getCacheDir() { return cache; }
        @Override public File getFilesDir() { return cache; }
        @Override public File getExternalFilesDir(String type) { return external; }
    }

    private static final class TestCall extends PluginCall {
        private final String apkUri;
        private final JSArray items;
        String rejected;
        JSObject resolved;

        TestCall(String apkUri, JSArray items) {
            this.apkUri = apkUri;
            this.items = items;
        }

        @Override public String getString(String key) {
            if ("apkUri".equals(key)) return apkUri;
            if ("activationMode".equals(key)) return "always_on";
            return null;
        }

        @Override public JSArray getArray(String key) {
            return "items".equals(key) ? items : null;
        }

        @Override public void resolve(JSObject value) { resolved = value; }
        @Override public void reject(String message) { rejected = message; }
    }

    private static final class RequestedItems extends JSArray {
        private final JSONObject[] items;

        RequestedItems(String... paths) {
            items = new JSONObject[paths.length];
            for (int i = 0; i < paths.length; i++) {
                items[i] = new PathItem(paths[i]);
            }
        }

        @Override public int length() { return items.length; }
        @Override public Object opt(int index) {
            return index >= 0 && index < items.length ? items[index] : null;
        }
    }

    private static final class PathItem extends JSONObject {
        private final String path;

        PathItem(String path) { this.path = path; }

        @Override public String optString(String key, String fallback) {
            return "path".equals(key) ? path : fallback;
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        typeface_stub = r"""
package android.graphics;
public class Typeface {
    public static Typeface createFromFile(String path) { return new Typeface(); }
}
"""
        paint_stub = r"""
package android.graphics;
public class Paint {
    public Typeface setTypeface(Typeface value) { return value; }
    public boolean hasGlyph(String value) { return value != null && !value.isEmpty(); }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-requested-path-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerRequestedPathHarness.java"
            classes = temporary_path / "classes"
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            harness_path.write_text(harness, "utf-8")
            (graphics_dir / "Typeface.java").write_text(typeface_stub, "utf-8")
            (graphics_dir / "Paint.java").write_text(paint_stub, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), str(graphics_dir / "Typeface.java"),
                    str(graphics_dir / "Paint.java"),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerRequestedPathHarness",
                 str(temporary_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_always_on_rewrites_source_dialogue_entries(self):
        """Always-on compilation must replace source RPYC Say.what values in place."""
        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.List;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import org.json.JSONObject;

public final class TranslationCompilerDialogueHarness {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File apk = new File(root, "fixture.apk");
        File cache = new File(root, "cache");
        File external = new File(root, "external");
        cache.mkdirs();
        external.mkdirs();

        byte[] template = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/template.rpy",
                Arrays.<String[]>asList(new String[]{"Hello", "Hello"}), 17, "fixture-key");
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/x-game/x-template.rpyc", rpc2(template));
            put(out, "assets/z-source.rpyc", sayRpyc());
            put(out, "assets/fonts/cjk.ttf", "CJK");
            put(out, "assets/x-game/x-tl/x-chinese/x-style.rpyc",
                    "line_break east_asian text_font");
        }

        File generated = new File(external,
                "SLG-Translator-Output/assets/x-game/x-tl/x-None/x-chapter.rpy");
        generated.getParentFile().mkdirs();
        Files.write(generated.toPath(), (
                "# Source: assets/z-source.rpyc\n"
                + "translate None strings:\n"
                + "    old \"First adjacent line\"\n"
                + "    new \"第一句\"\n\n"
                + "    old \"Second adjacent line\"\n"
                + "    new \"第二句\"\n").getBytes(StandardCharsets.UTF_8));

        RequestedItems items = new RequestedItems(
                "assets/x-game/x-tl/x-None/x-chapter.rpy");
        TestCall call = new TestCall(apk.getAbsolutePath(), items);
        TranslationCompiler.compileTranslationsIntoApk(
                new TestContext(cache, external), call);
        require(call.rejected == null, "always-on dialogue compile rejected: " + call.rejected);
        require(call.resolved != null, "always-on dialogue compile must resolve");

        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry source = zip.getEntry("assets/z-source.rpyc");
            require(source != null, "original source RPYC must remain at the same APK path");
            List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                    zip.getInputStream(source).readAllBytes(),
                    "assets/z-source.rpyc", false);
            require(find(records, "第一句", "alice"),
                    "always-on output must rewrite the first source dialogue");
            require(find(records, "第二句", ""),
                    "always-on output must rewrite the second source dialogue");
            require(zip.getEntry("assets/x-game/x-tl/x-None/x-slgtranslator-translations.rpyc") != null,
                    "always-on translation artifact must still be emitted for UI strings");
        }
    }

    private static boolean find(List<RenpyTextRecord> records, String text, String speaker) {
        for (RenpyTextRecord record : records) {
            if (record.kind == RenpyTextRecord.Kind.DIALOGUE
                    && text.equals(record.text) && speaker.equals(record.speaker)) {
                return true;
            }
        }
        return false;
    }

    private static byte[] sayRpyc() throws Exception {
        ByteArrayOutputStream pickle = new ByteArrayOutputStream();
        pickle.write(new byte[]{(byte) 0x80, 0x02, 0x5d, 0x28});
        sayObject(pickle, 31, "alice", "First adjacent line");
        sayObject(pickle, 32, "", "Second adjacent line");
        pickle.write(0x65);
        pickle.write(0x2e);
        return rpc2(pickle.toByteArray());
    }

    private static void sayObject(ByteArrayOutputStream out, int line,
                                  String speaker, String text) {
        writeString(out, "renpy.ast");
        writeString(out, "Say");
        out.write(0x93);
        out.write(0x29);
        out.write(0x81);
        out.write(0x4e);
        out.write(0x7d);
        out.write(0x28);
        writeString(out, "linenumber");
        out.write(0x4b);
        out.write(line);
        writeString(out, "filename");
        writeString(out, "game/speakers.rpy");
        if (speaker != null && !speaker.isEmpty()) {
            writeString(out, "who");
            writeString(out, speaker);
        }
        writeString(out, "what");
        writeString(out, text);
        out.write(0x75);
        out.write(0x86);
        out.write(0x62);
    }

    private static void writeString(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        out.write(0x8c);
        out.write(bytes.length);
        out.write(bytes, 0, bytes.length);
    }

    private static byte[] rpc2(byte[] pickle) throws Exception {
        byte[] slot = deflate(pickle);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int dataStart = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            writeIntLe(out, id);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot);
        out.write(slot);
        return out.toByteArray();
    }

    private static byte[] deflate(byte[] data) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(out)) {
            stream.write(data);
        }
        return out.toByteArray();
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static void put(ZipOutputStream out, String name, String body) throws Exception {
        put(out, name, body.getBytes(StandardCharsets.UTF_8));
    }

    private static void put(ZipOutputStream out, String name, byte[] body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body);
        out.closeEntry();
    }

    private static final class TestContext extends Context {
        private final File cache;
        private final File external;

        TestContext(File cache, File external) {
            this.cache = cache;
            this.external = external;
        }

        @Override public File getCacheDir() { return cache; }
        @Override public File getFilesDir() { return cache; }
        @Override public File getExternalFilesDir(String type) { return external; }
    }

    private static final class TestCall extends PluginCall {
        private final String apkUri;
        private final JSArray items;
        String rejected;
        JSObject resolved;

        TestCall(String apkUri, JSArray items) {
            this.apkUri = apkUri;
            this.items = items;
        }

        @Override public String getString(String key) {
            if ("apkUri".equals(key)) return apkUri;
            if ("activationMode".equals(key)) return "always_on";
            return null;
        }

        @Override public JSArray getArray(String key) {
            return "items".equals(key) ? items : null;
        }

        @Override public void resolve(JSObject value) { resolved = value; }
        @Override public void reject(String message) { rejected = message; }
    }

    private static final class RequestedItems extends JSArray {
        private final JSONObject[] items;

        RequestedItems(String... paths) {
            items = new JSONObject[paths.length];
            for (int i = 0; i < paths.length; i++) {
                items[i] = new PathItem(paths[i]);
            }
        }

        @Override public int length() { return items.length; }
        @Override public Object opt(int index) {
            return index >= 0 && index < items.length ? items[index] : null;
        }
    }

    private static final class PathItem extends JSONObject {
        private final String path;

        PathItem(String path) { this.path = path; }

        @Override public String optString(String key, String fallback) {
            return "path".equals(key) ? path : fallback;
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        typeface_stub = r"""
package android.graphics;
public class Typeface {
    public static Typeface createFromFile(String path) { return new Typeface(); }
}
"""
        paint_stub = r"""
package android.graphics;
public class Paint {
    public Typeface setTypeface(Typeface value) { return value; }
    public boolean hasGlyph(String value) { return value != null && !value.isEmpty(); }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-dialogue-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerDialogueHarness.java"
            classes = temporary_path / "classes"
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            harness_path.write_text(harness, "utf-8")
            (graphics_dir / "Typeface.java").write_text(typeface_stub, "utf-8")
            (graphics_dir / "Paint.java").write_text(paint_stub, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), str(graphics_dir / "Typeface.java"),
                    str(graphics_dir / "Paint.java"),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerDialogueHarness",
                 str(temporary_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_translation_compiler_skips_existing_always_on_translation_keys(self):
        """Always-on output must not duplicate old keys already registered by tl/None."""
        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.List;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import org.json.JSONObject;

public final class TranslationCompilerExistingNoneHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File apk = new File(root, "fixture.apk");
        File cache = new File(root, "cache");
        File external = new File(root, "external");
        cache.mkdirs();
        external.mkdirs();

        byte[] template = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/script.rpy",
                Arrays.<String[]>asList(new String[]{"Template", "Template"}), 17, "fixture-key");
        byte[] existingNone = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, null, "game/tl/None/common.rpym",
                Arrays.<String[]>asList(new String[]{"Change", "Change"}), 17, "fixture-key");
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/x-game/x-script.rpyc", deflate(template));
            put(out, "assets/x-game/x-tl/x-None/x-common.rpymc", deflate(existingNone));
            put(out, "assets/fonts/cjk.ttf", "CJK");
        }

        File requested = new File(external,
                "SLG-Translator-Output/assets/x-game/x-tl/x-None/current.rpy");
        requested.getParentFile().mkdirs();
        Files.write(requested.toPath(), (
                "translate None strings:\n"
                + "    old \"Change\"\n"
                + "    new \"??\"\n"
                + "\n"
                + "    old \"Fresh\"\n"
                + "    new \"???\"\n").getBytes(StandardCharsets.UTF_8));

        TestCall call = new TestCall(apk.getAbsolutePath(),
                new RequestedItems("assets/x-game/x-tl/x-None/current.rpy"));
        TranslationCompiler.compileTranslationsIntoApk(
                new TestContext(cache, external), call);
        require(call.rejected == null,
                "existing tl/None key must not reject compilation: " + call.rejected);
        require(call.resolved != null,
                "compiler must resolve after filtering existing key");

        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry generated = zip.getEntry(
                    "assets/x-game/x-tl/x-None/x-slgtranslator-translations.rpyc");
            require(generated != null, "always-on compiled artifact missing");
            byte[] compiled = zip.getInputStream(generated).readAllBytes();
            byte[] pickle = inflateSlot(compiled);
            require(!containsUtf8(pickle, "Change"),
                    "existing tl/None old key must be excluded from always-on artifact");
            require(containsUtf8(pickle, "Fresh"),
                    "new always-on key must remain in compiled artifact");
        }
    }

    private static byte[] inflateSlot(byte[] rpyc) throws Exception {
        int pos = "RENPY RPC2".length();
        while (pos + 12 <= rpyc.length) {
            int id = le(rpyc, pos);
            int offset = le(rpyc, pos + 4);
            int length = le(rpyc, pos + 8);
            if (id == 2) {
                java.util.zip.InflaterInputStream in =
                        new java.util.zip.InflaterInputStream(
                                new java.io.ByteArrayInputStream(rpyc, offset, length));
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buffer = new byte[1024];
                int read;
                while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
                return out.toByteArray();
            }
            if (id == 0) break;
            pos += 12;
        }
        throw new AssertionError("RPC2 slot 2 missing");
    }

    private static boolean containsUtf8(byte[] data, String value) {
        byte[] expected = value.getBytes(StandardCharsets.UTF_8);
        for (int i = 0; i + expected.length <= data.length; i++) {
            boolean match = true;
            for (int j = 0; j < expected.length; j++) {
                if (data[i + j] != expected[j]) {
                    match = false;
                    break;
                }
            }
            if (match) return true;
        }
        return false;
    }

    private static int le(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static byte[] deflate(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        return compressed.toByteArray();
    }

    private static void put(ZipOutputStream out, String name, String body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body.getBytes(StandardCharsets.UTF_8));
        out.closeEntry();
    }

    private static void put(ZipOutputStream out, String name, byte[] body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body);
        out.closeEntry();
    }

    private static final class TestContext extends Context {
        private final File cache;
        private final File external;

        TestContext(File cache, File external) {
            this.cache = cache;
            this.external = external;
        }

        @Override public File getCacheDir() { return cache; }
        @Override public File getFilesDir() { return cache; }
        @Override public File getExternalFilesDir(String type) { return external; }
    }

    private static final class TestCall extends PluginCall {
        private final String apkUri;
        private final JSArray items;
        String rejected;
        JSObject resolved;

        TestCall(String apkUri, JSArray items) {
            this.apkUri = apkUri;
            this.items = items;
        }

        @Override public String getString(String key) {
            if ("apkUri".equals(key)) return apkUri;
            if ("activationMode".equals(key)) return "always_on";
            return null;
        }

        @Override public JSArray getArray(String key) {
            return "items".equals(key) ? items : null;
        }

        @Override public void resolve(JSObject value) { resolved = value; }
        @Override public void reject(String message) { rejected = message; }
    }

    private static final class RequestedItems extends JSArray {
        private final JSONObject[] items;

        RequestedItems(String... paths) {
            items = new JSONObject[paths.length];
            for (int i = 0; i < paths.length; i++) {
                items[i] = new PathItem(paths[i]);
            }
        }

        @Override public int length() { return items.length; }
        @Override public Object opt(int index) {
            return index >= 0 && index < items.length ? items[index] : null;
        }
    }

    private static final class PathItem extends JSONObject {
        private final String path;

        PathItem(String path) { this.path = path; }

        @Override public String optString(String key, String fallback) {
            return "path".equals(key) ? path : fallback;
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        typeface_stub = r"""
package android.graphics;
public class Typeface {
    public static Typeface createFromFile(String path) { return new Typeface(); }
}
"""
        paint_stub = r"""
package android.graphics;
public class Paint {
    public Typeface setTypeface(Typeface value) { return value; }
    public boolean hasGlyph(String value) { return value != null && !value.isEmpty(); }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-existing-none-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationCompilerExistingNoneHarness.java"
            classes = temporary_path / "classes"
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            harness_path.write_text(harness, "utf-8")
            (graphics_dir / "Typeface.java").write_text(typeface_stub, "utf-8")
            (graphics_dir / "Paint.java").write_text(paint_stub, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), str(graphics_dir / "Typeface.java"),
                    str(graphics_dir / "Paint.java"),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerExistingNoneHarness",
                 str(temporary_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_protocol2_always_on_artifact_uses_none_without_changing_selectable_language(self):
        """A verified protocol-2 template keeps always-on nullable and selectable named."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.InflaterInputStream;

public final class Protocol2ActivationHarness {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    public static void main(String[] args) throws Exception {
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"same old", "same new"});

        byte[] template = rpc2(RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                pairs, 17, "fixture-key"));
        RpycCompatibility.Report report = RpycCompatibility.inspect(template);
        require(report.isProtocol2WriterVerified(),
                "fixture must be recognized as the verified protocol-2 shape: " + report.reason);

        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 17;
        meta.key = "fixture-key";
        meta.compatibility = report;

        TranslationCompiler.TranslationArtifact selectable =
                TranslationCompiler.compileTranslationArtifact("selectable", pairs, meta);
        require(RpycCompatibility.inspect(selectable.rpyc).isProtocol2WriterVerified(),
                "selectable artifact must use the verified protocol-2 writer");
        require("slgtranslated".equals(selectable.translatorLanguage),
                "selectable artifact must remain slgtranslated");
        require(selectable.compiledPath.contains("tl/x-slgtranslated/"),
                "selectable output path must remain in the slgtranslated bucket");
        require(selectable.runtimeFilename.contains("tl/slgtranslated/"),
                "selectable runtime path must remain slgtranslated");
        require(hasLanguageString(inflateSlot(selectable.rpyc), "slgtranslated"),
                "selectable pickle language must remain a string");

        TranslationCompiler.TranslationArtifact alwaysOn =
                TranslationCompiler.compileTranslationArtifact("always_on", pairs, meta);
        require(RpycCompatibility.inspect(alwaysOn.rpyc).isProtocol2WriterVerified(),
                "always-on artifact must use the verified protocol-2 writer");
        require(alwaysOn.translatorLanguage == null,
                "always-on compiler language must be null");
        require(alwaysOn.compiledPath.contains("tl/x-None/"),
                "always-on output path must include tl/None");
        require(alwaysOn.runtimeFilename.contains("tl/None/"),
                "always-on runtime path must include tl/None");
        require(hasNoneLanguage(inflateSlot(alwaysOn.rpyc)),
                "always-on pickle language must be NONE");
        RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                alwaysOn.rpyc, 17, "fixture-key", null, pairs.size());
        require(validation.valid, "always-on protocol-2 artifact must validate: " + validation.code);
    }

    private static byte[] rpc2(byte[] pickle) throws Exception {
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        DeflaterOutputStream deflated = new DeflaterOutputStream(raw);
        deflated.write(pickle);
        deflated.finish();
        deflated.close();
        byte[] slot = raw.toByteArray();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int dataStart = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            le(out, id);
            le(out, dataStart);
            le(out, slot.length);
            dataStart += slot.length;
        }
        le(out, 0);
        le(out, 0);
        le(out, 0);
        out.write(slot);
        out.write(slot);
        return out.toByteArray();
    }

    private static byte[] inflateSlot(byte[] rpyc) throws Exception {
        int pos = MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            int id = le(rpyc, pos);
            int offset = le(rpyc, pos + 4);
            int length = le(rpyc, pos + 8);
            if (id == 2) {
                InflaterInputStream in = new InflaterInputStream(
                        new ByteArrayInputStream(rpyc, offset, length));
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buffer = new byte[1024];
                int read;
                while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
                return out.toByteArray();
            }
            if (id == 0) break;
            pos += 12;
        }
        throw new AssertionError("RPC2 slot 2 missing");
    }

    private static boolean hasNoneLanguage(byte[] pickle) {
        byte[] key = bin("language");
        for (int i = 0; i + key.length < pickle.length; i++) {
            if (matches(pickle, i, key) && pickle[i + key.length] == 0x4e) return true;
        }
        return false;
    }

    private static boolean hasLanguageString(byte[] pickle, String expected) {
        byte[] key = bin("language");
        byte[] value = bin(expected);
        for (int i = 0; i + key.length + value.length <= pickle.length; i++) {
            if (matches(pickle, i, key) && matches(pickle, i + key.length, value)) return true;
        }
        return false;
    }

    private static byte[] bin(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x58);
        le(out, bytes.length);
        out.write(bytes, 0, bytes.length);
        return out.toByteArray();
    }

    private static boolean matches(byte[] data, int offset, byte[] expected) {
        if (offset < 0 || expected.length > data.length - offset) return false;
        for (int i = 0; i < expected.length; i++) {
            if (data[offset + i] != expected[i]) return false;
        }
        return true;
    }

    private static void le(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static int le(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="protocol2-activation-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "Protocol2ActivationHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.Protocol2ActivationHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_workshop_patch_propagates_activation_mode_and_guidance(self):
        ui_redesign = ROOT / "apk-work" / "ui-redesign"
        sys.path.insert(0, str(ui_redesign))
        from patch_workshop_ui import patch_assets
        from test_workshop_patch import extract_js_function

        base_assets = ROOT / "_trash" / "uncertain" / "extracted" / "assets" / "public" / "assets"
        js, _ = patch_assets(
            (base_assets / "index-CJtfdHOF.js").read_text("utf-8"),
            (base_assets / "index-C044IUg3.css").read_text("utf-8"),
        )
        for token in (
            "window.__slgActivationMode",
            "activationMode:window.__slgActivationMode||'always_on'",
            "window.__slgCompiledPath",
            "window.__slgFontReport",
            "window.__slgFontWarning",
            "window.__slgCompileFailed",
            "fontWarning",
            "always_on",
        ):
            self.assertIn(token, js)

        render_runtime = extract_js_function(js, "function renderStateBody(state,payload)")
        behavior_contract = r'''
function check(condition,label){if(!condition)throw new Error(label)}
globalThis.window=globalThis;
let installButton=null;
function textNode(tag,cls,text){return{tag,cls,text:text||``,children:[],append(...children){this.children.push(...children)}}}
function actionButton(label,handler,secondary=false){return{tag:`button`,label,handler,secondary,children:[]}}
function fileRow(){return textNode(`div`,`file-row`,`file`)}
function detailToggle(raw){return textNode(`div`,`details`,raw)}
function savePatchedApk(){} function triggerReactButton(){} function clickReact(){}
function collect(node,out=[]){if(!node)return out;if(node.tag===`button`)out.push(node);for(const child of node.children||[])collect(child,out);return out}
function visibleText(node,out=[]){if(!node)return out;if(node.text)out.push(String(node.text));for(const child of node.children||[])visibleText(child,out);return out}
const selectable=renderStateBody(`completed`,{fileName:`fixture.apk`,patchedApkPath:`/tmp/fixture-patched-signed.apk`,activationMode:`selectable`,renpyLang:``,renpyMenuType:`renpy`});
const selectableText=visibleText(selectable).join(`\n`);
check(selectableText.includes(`\u8bf7\u8fdb\u5165\u6e38\u620f\u8bbe\u7f6e`)&&selectableText.includes(`\u7ffb\u8bd1\u6587\u672c`)&&selectableText.includes(`\u5207\u56de\u539f\u6587`),`selectable guidance is rendered`);
const alwaysOn=renderStateBody(`completed`,{fileName:`fixture.apk`,patchedApkPath:`/tmp/fixture-patched-signed.apk`,activationMode:`always_on`,renpyLang:``,renpyMenuType:`none`});
const alwaysOnText=visibleText(alwaysOn).join(`\n`);
check(alwaysOnText.includes(`\u542f\u52a8\u65f6\u9ed8\u8ba4\u542f\u7528`)&&alwaysOnText.includes(`\u6e38\u620f\u5185\u4e0d\u80fd\u5207\u56de\u539f\u6587`),`always-on guidance is rendered`);
'''
        result = subprocess.run(
            ["node", "-e", render_runtime + behavior_contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_template_meta_prefers_game_script_over_common_and_tl(self):
        harness = r"""
package com.slgtranslator.app;

import java.io.File;

public final class TemplateMetaHarness {
    public static void main(String[] args) throws Exception {
        TranslationCompiler.TemplateMeta meta =
                TranslationCompiler.readTemplateMeta(new File(args[0]));
        require(meta.version == 2, "game template version");
        require("game-key".equals(meta.key), "game template key");
        require("assets/x-game/x-script.rpyc".equals(meta.sourcePath),
                "game script must win regardless of ZIP order: " + meta.sourcePath);
        require("game-script".equals(meta.selectionReason), "game script selection reason");
        TranslationCompiler.TemplateMeta bounded =
                TranslationCompiler.readTemplateMeta(new File(args[2]));
        require(bounded.version == 7, "negative-length payload version");
        require("bounded-key".equals(bounded.key), "negative-length payload key");
        require(TranslationCompiler.templatePriority("assets/x-game/x-script.rpyc") == 0,
                "game script priority");
        require(TranslationCompiler.templatePriority("assets/x-game/x-tl/x-english/ui.rpyc") == 10,
                "game tl priority");
        require(TranslationCompiler.templatePriority("assets/x-renpy/x-common/common.rpyc") == 100,
                "common priority");
        require(TranslationCompiler.templatePriority("not-assets.txt") == Integer.MAX_VALUE,
                "unusable priority");
        try {
            TranslationCompiler.readTemplateMeta(new File(args[1]));
            throw new AssertionError("inconsistent highest-priority templates must be rejected");
        } catch (java.io.IOException expected) {
            require(expected.getMessage().contains("version/key"),
                    "conflict diagnostic must name version/key");
            require(expected.getMessage().contains("assets/x-game/x-a.rpyc")
                            && expected.getMessage().contains("assets/x-game/x-b.rpyc"),
                    "conflict diagnostic must list candidate paths");
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="template-meta-test-") as temporary:
            temporary_path = Path(temporary)
            apk_path = temporary_path / "fixture.apk"
            conflict_path = temporary_path / "conflict.apk"
            negative_length_path = temporary_path / "negative-length.apk"
            harness_path = temporary_path / "TemplateMetaHarness.java"
            classes = temporary_path / "classes"
            with zipfile.ZipFile(apk_path, "w") as archive:
                archive.writestr("assets/x-renpy/x-common/common.rpyc",
                                 build_template_meta_fixture(1, "common-key"))
                archive.writestr("assets/x-game/x-tl/x-english/ui.rpyc",
                                 build_template_meta_fixture(2, "game-key"))
                archive.writestr("assets/x-game/x-script.rpyc",
                                 build_template_meta_fixture(2, "game-key"))
            with zipfile.ZipFile(conflict_path, "w") as archive:
                archive.writestr("assets/x-game/x-a.rpyc",
                                 build_template_meta_fixture(2, "game-key"))
                archive.writestr("assets/x-game/x-b.rpyc",
                                 build_template_meta_fixture(3, "other-key"))
            with zipfile.ZipFile(negative_length_path, "w") as archive:
                archive.writestr(
                    "assets/x-game/x-script.rpyc",
                    build_template_meta_negative_length_fixture(7, "bounded-key"),
                )
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                "com.slgtranslator.app.TemplateMetaHarness", str(apk_path),
                str(conflict_path), str(negative_length_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_compatibility_separates_modern_legacy_and_unknown_generation(self):
        scanner_source = SCANNER.read_text("utf-8")
        for token in (
            "RpycCompatibility.inspect",
            'supportLevel',
            'compatibilityReason',
            '"extract_only"',
        ):
            self.assertIn(token, scanner_source)
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public final class RpycCompatibilityHarness {
    public static void main(String[] args) throws Exception {
        RpycCompatibility.Report modern =
                RpycCompatibility.inspect(Files.readAllBytes(Paths.get(args[0])));
        require("rpc2".equals(modern.container), "modern container");
        require(modern.preferredSlot == 2, "modern preferred slot");
        require(modern.pickleProtocol == 2, "modern protocol");
        require(modern.usesBuiltins && !modern.usesPy2Builtins, "modern builtins");
        require(modern.generationSupport == RpycCompatibility.GenerationSupport.MODERN_SUPPORTED,
                "modern support");
        require(modern.canGenerate(), "real modern golden must stay writable");

        byte[] legacyBytes = Files.readAllBytes(Paths.get(args[1]));
        RpycCompatibility.Report legacy = RpycCompatibility.inspect(legacyBytes);
        require("legacy-zlib".equals(legacy.container), "legacy container");
        require(legacy.preferredSlot == 1, "legacy preferred slot");
        require(legacy.pickleProtocol == 2, "legacy protocol");
        require(!legacy.usesBuiltins && legacy.usesPy2Builtins, "legacy builtins");
        require(legacy.generationSupport == RpycCompatibility.GenerationSupport.LEGACY_EXTRACT_ONLY,
                "legacy support");
        require("legacy_pickle_writer_required".equals(legacy.reason), "legacy reason");
        List<String> extracted = RpycTextExtractor.extractTexts(legacyBytes);
        require(extracted.contains("Hello, world!"), "extractor must still read legacy RPYC");

        RpycCompatibility.Report supportedLegacy =
                RpycCompatibility.inspect(Files.readAllBytes(Paths.get(args[3])));
        require(supportedLegacy.generationSupport
                        == RpycCompatibility.GenerationSupport.LEGACY_PROTOCOL2_SUPPORTED,
                "standard legacy Ren'Py AST must be writable: " + supportedLegacy.reason);
        require(supportedLegacy.canGenerate(),
                "standard legacy target must allow generation: " + supportedLegacy.reason);
        require(supportedLegacy.isProtocol2WriterCompatible(),
                "standard legacy target must select the protocol-2 writer");

        RpycCompatibility.Report unknown =
                RpycCompatibility.inspect(Files.readAllBytes(Paths.get(args[2])));
        require(unknown.generationSupport == RpycCompatibility.GenerationSupport.UNKNOWN_EXTRACT_ONLY,
                "unknown support");
        require("unknown_pickle_globals".equals(unknown.reason), "unknown reason");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpyc-compatibility-test-") as temporary:
            temporary_path = Path(temporary)
            modern_path = temporary_path / "modern.rpyc"
            legacy_path = temporary_path / "legacy.rpyc"
            supported_legacy_path = temporary_path / "supported-legacy.rpyc"
            unknown_path = temporary_path / "unknown.rpyc"
            harness_path = temporary_path / "RpycCompatibilityHarness.java"
            classes = temporary_path / "classes"
            modern_path.write_bytes(build_compatibility_rpc2_fixture())
            legacy_path.write_bytes(build_compatibility_legacy_fixture())
            supported_legacy_path.write_bytes(build_compatibility_legacy_engine_fixture())
            unknown_path.write_bytes(build_compatibility_unknown_fixture())
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RpycCompatibilityHarness",
                 str(modern_path), str(legacy_path), str(unknown_path),
                 str(supported_legacy_path)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)

    def test_modern_envelope_gate_requires_root_keys_and_real_renpy_ast_global(self):
        scanner_source = SCANNER.read_text("utf-8")
        self.assertIn('"compatibilityDialect"', scanner_source)
        self.assertIn('.put("dialect", report.rpyc.dialect', scanner_source)
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.zip.DeflaterOutputStream;

public final class ModernEnvelopeGateHarness {
    private static RpycCompatibility.Report inspect(String path) throws Exception {
        return RpycCompatibility.inspect(Files.readAllBytes(Paths.get(path)));
    }

    private static byte[] deflate(byte[] value) throws Exception {
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        DeflaterOutputStream out = new DeflaterOutputStream(raw);
        out.write(value); out.finish(); out.close();
        return raw.toByteArray();
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        RpycCompatibility.Report golden = inspect(args[0]);
        require(golden.pickleProtocol == 2, "golden encoding fact must stay protocol 2");
        require(golden.dialect == RpycCompatibility.ModernDialect.MODERN_ENVELOPE_VERIFIED,
                "golden dialect: " + golden.dialect + " reason=" + golden.reason);
        require(golden.isModernEnvelopeVerified(), "golden modern envelope");
        require(golden.canGenerate(), "golden remains writable");

        RpycCompatibility.Report global = inspect(args[1]);
        require(global.dialect == RpycCompatibility.ModernDialect.MODERN_ENVELOPE_VERIFIED,
                "GLOBAL renpy.ast must verify: " + global.dialect);
        require(global.isModernEnvelopeVerified() && global.canGenerate(),
                "GLOBAL modern envelope must generate");

        RpycCompatibility.Report bare = inspect(args[2]);
        require(bare.dialect == RpycCompatibility.ModernDialect.MODERN_GENERIC,
                "bare builtins dialect: " + bare.dialect);
        require(!bare.isModernEnvelopeVerified() && !bare.canGenerate(),
                "bare builtins must be extract-only");

        RpycCompatibility.Report decoy = inspect(args[3]);
        require(decoy.dialect == RpycCompatibility.ModernDialect.MODERN_GENERIC,
                "decoy dialect: " + decoy.dialect);
        require(!decoy.isModernEnvelopeVerified() && !decoy.canGenerate(),
                "decoy strings must not verify");

        RpycCompatibility.Report nested = inspect(args[4]);
        require(nested.dialect == RpycCompatibility.ModernDialect.MODERN_GENERIC,
                "nested dialect: " + nested.dialect);
        require(!nested.isModernEnvelopeVerified() && !nested.canGenerate(),
                "nested three-key dict must not verify root envelope");

        RpycCompatibility.Report pseudo = inspect(args[5]);
        require(pseudo.dialect == RpycCompatibility.ModernDialect.MODERN_GENERIC,
                "pseudo STACK_GLOBAL dialect: " + pseudo.dialect);
        require(!pseudo.isModernEnvelopeVerified() && !pseudo.canGenerate(),
                "pseudo STACK_GLOBAL must not verify");

        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"old", "new"});
        byte[] protocol2 = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                pairs, 17, "key");
        RpycCompatibility.Report legacy = RpycCompatibility.inspect(deflate(protocol2));
        require(legacy.dialect == RpycCompatibility.ModernDialect.LEGACY_PROTOCOL2,
                "protocol2 dialect: " + legacy.dialect);
        require(legacy.isProtocol2WriterVerified() && legacy.canGenerate(),
                "verified protocol2 writer must be preserved");

        RenpyCompatibilityReport report = new RenpyCompatibilityReport(
                RenpyCompatibilityReport.SupportLevel.SAFE,
                RenpyCompatibilityReport.ActivationStrategy.SELECTABLE_LANGUAGE,
                "game/script.rpyc", golden, 0, 0, Collections.<String>emptyList(),
                "renpy", null, 0, 0, 0, Collections.<RenpyCompatibilityReport.Issue>emptyList());
        require(report.toSanitizedJson().contains(
                "\"dialect\":\"MODERN_ENVELOPE_VERIFIED\""),
                "sanitized report must expose dialect: " + report.toSanitizedJson());

        RenpyCompatibilityReport blocked = RenpyPreflight.inspect(null,
                new RenpyPreflight.SourceSet("game/script.rpyc", bare, 0, 0,
                        Collections.<String>emptyList(), "renpy", null, 0, 0, 0));
        require(blocked.supportLevel == RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY,
                "MODERN_GENERIC preflight must be extract-only: " + blocked.supportLevel);
        require(blocked.toSanitizedJson().contains("\"dialect\":\"MODERN_GENERIC\""),
                "blocked report must expose generic dialect");
    }
}
"""
        fixtures = (
            wrap_rpc2(__import__("base64").b64decode(MODERN_PICKLE_GOLDEN_B64)),
            build_modern_global_envelope_fixture(),
            build_modern_bare_builtins_fixture(),
            build_modern_decoy_fields_fixture(),
            build_modern_nested_three_key_fixture(),
            build_modern_pseudo_stack_global_fixture(),
        )
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="modern-envelope-gate-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_paths = []
            for index, fixture in enumerate(fixtures):
                path = temporary_path / f"fixture-{index}.rpyc"
                path.write_bytes(fixture)
                fixture_paths.append(path)
            harness_path = temporary_path / "ModernEnvelopeGateHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.ModernEnvelopeGateHarness", *map(str, fixture_paths)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)

    def test_modern_envelope_accepts_dict_subclass_setitem_targets(self):
        # Real 8.4 serializes dict subclasses (renpy.revertable.RevertableDict)
        # as NEWOBJ instance + SETITEM/SETITEMS directly on the OBJECT. The
        # structural verifier must not reject those as invalid_setitem or
        # setitems_without_dict.
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;

public final class RevertableDictEnvelopeHarness {
    public static void main(String[] args) throws Exception {
        RpycCompatibility.Report report = RpycCompatibility.inspect(
                Files.readAllBytes(Paths.get(args[0])));
        require(report.dialect == RpycCompatibility.ModernDialect.MODERN_ENVELOPE_VERIFIED,
                "dict-subclass payload must verify: " + report.dialect
                        + " reason=" + report.reason);
        require(report.isModernEnvelopeVerified() && report.canGenerate(),
                "dict-subclass payload must remain writable");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        fixture = build_modern_revertable_dict_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="revertable-dict-envelope-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            fixture_path.write_bytes(fixture)
            harness_path = temporary_path / "RevertableDictEnvelopeHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RevertableDictEnvelopeHarness", str(fixture_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)

    def test_modern_envelope_frame_length_low_byte_does_not_break_global_scan(self):
        # Real 8.4 FRAME (0x95) lengths are arbitrary 8-byte values; when the
        # low byte collides with a payload opcode (0x8e BINBYTES8), the
        # global-name scan must skip the frame instead of misreading the
        # length bytes as a huge payload and bailing to UNKNOWN.
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;

public final class FrameCollisionHarness {
    public static void main(String[] args) throws Exception {
        RpycCompatibility.Report report = RpycCompatibility.inspect(
                Files.readAllBytes(Paths.get(args[0])));
        require(report.dialect == RpycCompatibility.ModernDialect.MODERN_ENVELOPE_VERIFIED,
                "frame-collision payload must verify: " + report.dialect
                        + " reason=" + report.reason);
        require(report.isModernEnvelopeVerified() && report.canGenerate(),
                "frame-collision payload must remain writable");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        fixture = build_modern_frame_collision_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="frame-collision-envelope-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            fixture_path.write_bytes(fixture)
            harness_path = temporary_path / "FrameCollisionHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.FrameCollisionHarness", str(fixture_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)

    def test_compiled_rpyc_validator_rejects_corrupt_or_mismatched_outputs(self):
        harness = r"""
package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.List;

public final class RenpyPatchValidatorHarness {
    public static void main(String[] args) {
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 7;
        meta.key = "unlocked";
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"old one", "new one"});
        pairs.add(new String[]{"old two", "new two"});
        byte[] valid = TranslationCompiler.compileRpyc(
                "slgtranslated", "game/tl/slgtranslated/translations.rpy", pairs, meta);

        RenpyPatchValidator.Result ok = RenpyPatchValidator.validateCompiledRpyc(
                valid, 7, "unlocked", "slgtranslated", 2);
        require(ok.valid && ok.decodedPairCount == 2, "normal output must validate");

        byte[] range = valid.clone();
        putLe(range, 10 + 12 + 8, 0x7fffffff);
        requireCode(range, "renpy_slot_range");

        byte[] zlib = valid.clone();
        int slotOffset = le(zlib, 10 + 12 + 4);
        zlib[slotOffset] = 0;
        requireCode(zlib, "renpy_zlib_truncated");

        requireCode(valid, 999, "unlocked", "slgtranslated", 2, "renpy_version_mismatch");
        requireCode(valid, 7, "unlocked", "wrong", 2, "renpy_language_mismatch");
        requireCode(valid, 7, "unlocked", "slgtranslated", 3, "renpy_pair_count");
    }

    private static void requireCode(byte[] rpyc, String code) {
        requireCode(rpyc, 7, "unlocked", "slgtranslated", 2, code);
    }

    private static void requireCode(byte[] rpyc, int version, String key,
                                    String language, int pairs, String code) {
        RenpyPatchValidator.Result result = RenpyPatchValidator.validateCompiledRpyc(
                rpyc, version, key, language, pairs);
        require(!result.valid && code.equals(result.code),
                "expected " + code + " but got " + result.code);
    }

    private static int le(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static void putLe(byte[] data, int pos, int value) {
        data[pos] = (byte) value;
        data[pos + 1] = (byte) (value >>> 8);
        data[pos + 2] = (byte) (value >>> 16);
        data[pos + 3] = (byte) (value >>> 24);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpyc-validator-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenpyPatchValidatorHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RenpyPatchValidatorHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_84_default_omission_extracts_dialogue(self):
        """8.4-style default-omission Say (who=None) must still extract what."""
        fixture = build_84_default_omission_fixture_rpyc()
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public final class DefaultOmissionExtractMain {
    public static void main(String[] args) throws Exception {
        byte[] rpyc = Files.readAllBytes(Paths.get(args[0]));
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                rpyc, "game/fixture.rpy", false);
        for (RenpyTextRecord record : records) {
            System.err.println("RECORD=" + record.kind + "|" + record.speaker + "|" + record.text);
        }
        require(findDialogue(records, "省略默认字段后的对话"),
                "default-omission Say must still extract its what value");
    }

    private static boolean findDialogue(List<RenpyTextRecord> records, String text) {
        for (RenpyTextRecord record : records) {
            if (record.kind == RenpyTextRecord.Kind.DIALOGUE
                    && text.equals(record.text)) {
                return true;
            }
        }
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="84-default-omission-extract-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "DefaultOmissionExtractMain.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.DefaultOmissionExtractMain", str(fixture_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr + run_result.stdout)

    def test_84_compile_path_rereads(self):
        """Envelope-verified 8.4 fixture passes the hardened gate and the real
        writer path (compile -> validate -> re-read) closes on it."""
        fixture = build_84_default_omission_fixture_rpyc()
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

public final class Compile84Main {
    public static void main(String[] args) throws Exception {
        byte[] fixture = Files.readAllBytes(Paths.get(args[0]));
        RpycCompatibility.Report compat = RpycCompatibility.inspect(fixture);
        // RpycCompatibility.inspect runs ModernEnvelopeReader internally and only
        // sets MODERN_ENVELOPE_VERIFIED when the envelope verifies, so this is the
        // same dual gate the plan's Compile84Main checks explicitly.
        if (!compat.canGenerate()
                || !compat.isModernEnvelopeVerified()) {
            System.out.println("GATE_BLOCKED " + compat.dialect);
            return;
        }
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 123;
        meta.key = "unlocked";
        meta.compatibility = compat;
        List<String[]> pairs = new ArrayList<String[]>();
        pairs.add(new String[]{"省略默认字段后的对话", "Dialogue (CN)"});
        byte[] rpyc = TranslationCompiler.compileRpyc("zh", "script.rpyc", pairs, meta);
        RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                rpyc, 123, "unlocked", "zh", 1);
        System.out.println("COMPILE " + validation.valid + " " + validation.code);
        RpycCompatibility.Report reread = RpycCompatibility.inspect(rpyc);
        System.out.println("REREAD " + reread.canGenerate());
        System.out.println("PAIR " + validation.decodedPairCount);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="84-compile-path-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "Compile84Main.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.Compile84Main", str(fixture_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr + run_result.stdout)
            out = run_result.stdout
            self.assertNotIn("GATE_BLOCKED", out,
                    "envelope-verified 8.4 fixture must pass the hardened gate")
            self.assertIn("COMPILE true ok", out,
                    "real writer path passes RenpyPatchValidator")
            self.assertIn("REREAD true", out,
                    "compiled output re-parses via inspect")
            self.assertIn("PAIR 1", out,
                    "translation pair present in compiled output")

    def test_deep_proto45_walk_sees_dialogue(self):
        """Deep protocol-4 payload (FRAME/BINUNICODE8/BYTEARRAY8) must not
        desynchronize walk: the long-string dialogue is still extracted."""
        fixture = build_deep_proto45_fixture_rpyc()
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public final class DeepProto45ExtractMain {
    public static void main(String[] args) throws Exception {
        byte[] rpyc = Files.readAllBytes(Paths.get(args[0]));
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                rpyc, "game/deep.rpy", false);
        for (RenpyTextRecord record : records) {
            System.err.println("RECORD=" + record.kind + "|" + record.speaker + "|" + record.text);
        }
        require(findDialogue(records, "DEEP_PROTO45_LONG_WHAT_TEXT"),
                "deep BYTEARRAY8/FRAME dialogue must survive walk");
    }

    private static boolean findDialogue(List<RenpyTextRecord> records, String text) {
        for (RenpyTextRecord record : records) {
            if (record.kind == RenpyTextRecord.Kind.DIALOGUE
                    && text.equals(record.text)) {
                return true;
            }
        }
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
""".replace("DEEP_PROTO45_LONG_WHAT_TEXT", DEEP_PROTO45_LONG_WHAT)
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="deep-proto45-walk-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "DeepProto45ExtractMain.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.DeepProto45ExtractMain", str(fixture_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr + run_result.stdout)

    def test_walk_malformed_lengths_fail_closed(self):
        """Crafted/truncated pickle length fields must make walk() return null
        instead of throwing AIOOBE or looping forever. Valid streams must
        still walk (regression guard for the bounds hardening)."""
        harness = r"""
package com.slgtranslator.app;

public final class WalkMalformedMain {
    public static void main(String[] args) {
        require(walkOf(new byte[]{(byte) 0x8d}) == null,
                "truncated stream right after BINUNICODE8 opcode");
        require(walkOf(new byte[]{(byte) 0x8d, 0x01, 0x02, 0x03}) == null,
                "BINUNICODE8 with fewer than 8 length bytes");
        require(walkOf(new byte[]{(byte) 0x8d,
                (byte) 0xF8, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF,
                0x00, 0x00, 0x00, 0x00}) == null,
                "BINUNICODE8 length with low 32 bits -8 must not loop");
        require(walkOf(new byte[]{(byte) 0x58,
                (byte) 0xFC, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF}) == null,
                "BINUNICODE length -4 must not loop");
        require(walkOf(new byte[]{(byte) 0x4b, 0x01}) != null,
                "valid BININT1 stream must still walk");
        require(walkOf(new byte[]{(byte) 0x8d,
                0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                'a', 'b', 'c'}) != null,
                "valid BINUNICODE8 stream must still walk");
        System.err.println("WALK_MALFORMED_OK");
    }

    private static java.util.List<int[]> walkOf(byte[] data) {
        return LanguageMenuSupport.walk(data);
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="walk-malformed-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "WalkMalformedMain.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.WalkMalformedMain"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=120,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr + run_result.stdout)

    def test_rpyc_stream_validator_and_detailed_rewrite_contract(self):
        """The production strict-stream validator catches the exact FRAME/memo
        corruption classes that crashed Ren'Py, and rewriteSayTextsDetailed
        reports matched/missed exact-old keys."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.Deflater;
import java.util.zip.Inflater;

public final class RpycStreamValidatorHarness {
    public static void main(String[] args) throws Exception {
        // 1. Valid FRAME stream (frame length == distance to EOF).
        byte[] frameOk = {(byte) 0x80, 0x05, (byte) 0x95, 1, 0, 0, 0, 0, 0, 0, 0,
                (byte) 0x2e};
        require(RpycStreamValidator.validate(frameOk) == null,
                "valid FRAME stream must pass");

        // 2. FRAME with stale length must be rejected (the 8.5 crash class).
        byte[] frameBad = Arrays.copyOf(frameOk, frameOk.length);
        frameBad[3] = 7;
        require(RpycStreamValidator.CODE_FRAME_LENGTH.equals(
                RpycStreamValidator.validate(frameBad)), "stale FRAME length must fail");

        // 3. BINGET beyond the memo must be rejected.
        require(RpycStreamValidator.CODE_MEMO_REFERENCE.equals(
                RpycStreamValidator.validate(new byte[]{(byte) 0x68, 0x05})),
                "BINGET beyond memo must fail");

        // 4. BINPUT followed by its own BINGET is valid.
        require(RpycStreamValidator.validate(
                new byte[]{(byte) 0x71, 0x00, (byte) 0x68, 0x00}) == null,
                "BINPUT/BINGET round-trip must pass");

        // 5. Truncated streams fail closed.
        require(RpycStreamValidator.CODE_TRUNCATED.equals(
                RpycStreamValidator.validate(new byte[]{(byte) 0x8d})),
                "truncated stream must fail");

        // 6. End-to-end: rewrite a protocol-5 FRAME-wrapped Say.what and
        //    validate the rewritten stream, then corrupt a FRAME length and
        //    confirm the validator rejects it.
        byte[] rpyc = wrapRpc2(frameSay());
        Map<String, String> translations = new LinkedHashMap<>();
        translations.put("Hello", "\u4f60\u597d");
        translations.put("Missing", "\u4e0d\u5b58\u5728");
        RpycDialoguePatcher.RewriteOutcome outcome =
                RpycDialoguePatcher.rewriteSayTextsDetailed(rpyc, translations);
        require(outcome != null, "FRAME-wrapped Say must be rewritten");
        require(outcome.matchedCount == 1, "exactly one key must match");
        require(outcome.missedOldTexts.size() == 1
                        && "Missing".equals(outcome.missedOldTexts.get(0)),
                "non-matching key must be reported");
        byte[] rewrittenPickle = slotPickle(outcome.bytes);
        require(rewrittenPickle != null, "rewritten slot pickle must be readable");
        require(RpycStreamValidator.validate(rewrittenPickle) == null,
                "rewritten FRAME stream must pass strict validation");
        int frame = indexOf(rewrittenPickle, (byte) 0x95);
        require(frame >= 0, "rewritten stream must keep its FRAME opcode");
        byte[] corrupted = Arrays.copyOf(rewrittenPickle, rewrittenPickle.length);
        corrupted[frame + 1] += 7;
        require(RpycStreamValidator.CODE_FRAME_LENGTH.equals(
                RpycStreamValidator.validate(corrupted)),
                "corrupted FRAME length must be detected");
        System.err.println("STREAM_VALIDATOR_OK");

        // 7. Dotted Say text: ".Hello" must match the extracted key "Hello".
        byte[] rpycDotted = wrapRpc2(frameSayDotted());
        Map<String, String> dottedTranslations = new LinkedHashMap<>();
        dottedTranslations.put("Hello", "\u4f60\u597d");
        RpycDialoguePatcher.RewriteOutcome dotted =
                RpycDialoguePatcher.rewriteSayTextsDetailed(rpycDotted, dottedTranslations);
        require(dotted != null, "dotted Say must be rewritten");
        require(dotted.matchedCount == 1, "dotted key must match exactly once");
        require(dotted.missedOldTexts.isEmpty(), "dotted key must not be reported missed");
        byte[] dottedPickle = slotPickle(dotted.bytes);
        require(RpycStreamValidator.validate(dottedPickle) == null,
                "dotted rewrite must stay valid");
        System.err.println("DOTTED_SAY_OK");
    }

    /** Protocol-5 pickle: PROTO, FRAME(len patched later), 'what', 'Hello', STOP. */
    private static byte[] frameSay() {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x80);
        out.write(0x05);
        out.write(0x95);
        for (int i = 0; i < 8; i++) {
            out.write(0);
        }
        writeShortUnicode(out, "what");
        writeShortUnicode(out, "Hello");
        out.write(0x2e);
        return out.toByteArray();
    }

    /** Protocol-5 pickle whose Say.what keeps a leading '.' text marker. */
    private static byte[] frameSayDotted() {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x80);
        out.write(0x05);
        out.write(0x95);
        for (int i = 0; i < 8; i++) {
            out.write(0);
        }
        writeShortUnicode(out, "what");
        writeShortUnicode(out, ".Hello");
        out.write(0x2e);
        return out.toByteArray();
    }

    private static void writeShortUnicode(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        out.write(0x8c);
        out.write(bytes.length);
        out.write(bytes, 0, bytes.length);
    }

    /** Wraps a pickle payload as a single-slot RPC2 container. */
    private static byte[] wrapRpc2(byte[] pickle) throws Exception {
        byte[] payload = deflate(pickle);
        int dataStart = 10 + 24;
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write("RENPY RPC2".getBytes(StandardCharsets.US_ASCII));
        writeIntLe(out, 1);
        writeIntLe(out, dataStart);
        writeIntLe(out, payload.length);
        for (int i = 0; i < 3; i++) {
            writeIntLe(out, 0);
        }
        out.write(payload);
        return out.toByteArray();
    }

    private static byte[] slotPickle(byte[] rpyc) throws Exception {
        int pos = "RENPY RPC2".length();
        while (pos + 12 <= rpyc.length) {
            int id = le(rpyc, pos);
            int offset = le(rpyc, pos + 4);
            int length = le(rpyc, pos + 8);
            pos += 12;
            if (id == 0) {
                return null;
            }
            if (id == 1 && offset >= 0 && length > 0 && offset + length <= rpyc.length) {
                return inflate(Arrays.copyOfRange(rpyc, offset, offset + length));
            }
        }
        return null;
    }

    private static int indexOf(byte[] data, byte wanted) {
        for (int i = 0; i < data.length; i++) {
            if (data[i] == wanted) {
                return i;
            }
        }
        return -1;
    }

    private static byte[] deflate(byte[] data) throws Exception {
        Deflater deflater = new Deflater();
        deflater.setInput(data);
        deflater.finish();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        while (!deflater.finished()) {
            out.write(buffer, 0, deflater.deflate(buffer));
        }
        deflater.end();
        return out.toByteArray();
    }

    private static byte[] inflate(byte[] data) throws Exception {
        Inflater inflater = new Inflater();
        inflater.setInput(data);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        while (!inflater.finished()) {
            int count = inflater.inflate(buffer);
            if (count == 0 && inflater.needsInput()) {
                break;
            }
            out.write(buffer, 0, count);
        }
        inflater.end();
        return out.toByteArray();
    }

    private static int le(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpyc-stream-validator-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RpycStreamValidatorHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RpycStreamValidatorHarness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=120,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr + run_result.stdout)

    def test_deep_proto45_compile_path_roundtrip(self):
        """The deep-payload fixture passes the hardened gate and its translation
        pair survives the real writer path with a clean re-read."""
        fixture = build_deep_proto45_fixture_rpyc()
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

public final class CompileDeepMain {
    public static void main(String[] args) throws Exception {
        byte[] fixture = Files.readAllBytes(Paths.get(args[0]));
        RpycCompatibility.Report compat = RpycCompatibility.inspect(fixture);
        if (!compat.canGenerate()
                || !compat.isModernEnvelopeVerified()) {
            System.out.println("GATE_BLOCKED " + compat.dialect);
            return;
        }
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 17;
        meta.key = "unlocked";
        meta.compatibility = compat;
        List<String[]> pairs = new ArrayList<String[]>();
        pairs.add(new String[]{"DEEP_PROTO45_LONG_WHAT_TEXT", "Deep payload (CN)"});
        byte[] rpyc = TranslationCompiler.compileRpyc("zh", "script.rpyc", pairs, meta);
        RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                rpyc, 17, "unlocked", "zh", 1);
        System.out.println("COMPILE " + validation.valid + " " + validation.code);
        RpycCompatibility.Report reread = RpycCompatibility.inspect(rpyc);
        System.out.println("REREAD " + reread.canGenerate());
        System.out.println("PAIR " + validation.decodedPairCount);
    }
}
""".replace("DEEP_PROTO45_LONG_WHAT_TEXT", DEEP_PROTO45_LONG_WHAT)
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="deep-proto45-compile-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "CompileDeepMain.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.CompileDeepMain", str(fixture_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr + run_result.stdout)
            out = run_result.stdout
            self.assertNotIn("GATE_BLOCKED", out,
                    "deep-payload fixture must pass the hardened gate")
            self.assertIn("COMPILE true ok", out,
                    "deep payload compiles through real writer path")
            self.assertIn("REREAD true", out,
                    "deep-payload output re-parses")
            self.assertIn("PAIR 1", out,
                    "translation pair survives rebuild")

    def test_renpy_resource_limits_reject_bombs_and_invalid_ranges(self):
        limits_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                         / "RenpyResourceLimits.java")
        for path in (
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpaArchive.java",
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java",
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java",
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "TranslationCompiler.java",
        ):
            self.assertTrue(path.exists())
        source = limits_source.read_text("utf-8") if limits_source.exists() else ""
        for token in (
            "MAX_SINGLE_SCRIPT_COMPRESSED",
            "MAX_SINGLE_SCRIPT_INFLATED",
            "MAX_TOTAL_SCRIPT_INFLATED",
            "MAX_RPA_ENTRIES",
            "MAX_TEXT_RECORDS",
            "MAX_TEXT_LENGTH",
            "MAX_INFLATE_RATIO",
            "renpy_limit_compressed",
            "renpy_limit_inflated",
            "renpy_limit_ratio",
            "renpy_limit_entries",
            "renpy_invalid_range",
        ):
            self.assertIn(token, source)

        harness = r"""
package com.slgtranslator.app;

public final class RenpyResourceLimitsHarness {
    public static void main(String[] args) throws Exception {
        require(RenpyResourceLimits.MAX_SINGLE_SCRIPT_COMPRESSED == 64L * 1024 * 1024,
                "compressed limit");
        require(RenpyResourceLimits.MAX_SINGLE_SCRIPT_INFLATED == 256L * 1024 * 1024,
                "inflated limit");
        require(RenpyResourceLimits.MAX_TOTAL_SCRIPT_INFLATED == 1024L * 1024 * 1024,
                "total inflated limit");
        require(RenpyResourceLimits.MAX_RPA_ENTRIES == 200000, "entry limit");
        require(RenpyResourceLimits.MAX_TEXT_RECORDS == 1000000, "record limit");
        require(RenpyResourceLimits.MAX_TEXT_LENGTH == 1000000, "text limit");
        require(RenpyResourceLimits.MAX_INFLATE_RATIO == 200, "ratio limit");

        expect("renpy_limit_compressed", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkCompressed(
                        RenpyResourceLimits.MAX_SINGLE_SCRIPT_COMPRESSED + 1);
            }
        });
        expect("renpy_limit_inflated", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkInflated(
                        RenpyResourceLimits.MAX_SINGLE_SCRIPT_INFLATED + 1);
            }
        });
        expect("renpy_limit_ratio", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkInflateRatio(1, 201);
            }
        });
        expect("renpy_limit_entries", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkEntryCount(
                        RenpyResourceLimits.MAX_RPA_ENTRIES + 1L);
            }
        });
        expect("renpy_invalid_range", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkRange(-1, 1, 10);
            }
        });
        expect("renpy_invalid_range", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkRange(Long.MAX_VALUE, 2, Long.MAX_VALUE);
            }
        });
        expect("renpy_invalid_range", new Action() {
            public void run() throws Exception {
                RenpyResourceLimits.checkPath("../escape.rpyc");
            }
        });
        RenpyResourceLimits.checkRange(9, 1, 10);
        RenpyResourceLimits.checkPath("game/chapter1.rpyc");
    }

    private interface Action {
        void run() throws Exception;
    }

    private static void expect(String code, Action action) throws Exception {
        try {
            action.run();
            throw new AssertionError("expected " + code);
        } catch (RenpyResourceLimits.LimitException expected) {
            require(code.equals(expected.code),
                    "expected " + code + " but got " + expected.code);
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-resource-limits-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenpyResourceLimitsHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RenpyResourceLimitsHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_renpy_font_report_detects_missing_translation_glyphs(self):
        """Exercise real APK enumeration and glyph selection through Android stubs."""
        self.assertTrue(FONT_SUPPORT.exists(), "RenpyFontSupport.java must exist")
        source = FONT_SUPPORT.read_text("utf-8")
        for token in (
            "public static FontReport inspect(",
            "Typeface.createFromFile",
            "Paint.hasGlyph",
            "MAX_FONT_ENTRIES",
            "MAX_FONT_BYTES",
            "MAX_TOTAL_FONT_BYTES",
            "createTempFile",
            "delete()",
            "hasChineseStyleBucket",
            "hasEastAsianLineBreakEvidence",
        ):
            self.assertIn(token, source)
        self.assertNotRegex(source, r"/system/fonts|systemFont|sans-serif")

        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import android.graphics.Paint;
import android.graphics.Typeface;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class RenpyFontSupportHarness {
    public static void main(String[] args) throws Exception {
        File apk = new File(args[0]);
        File cache = new File(args[1]);
        cache.mkdirs();
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/fonts/latin.ttf", "LATIN");
            put(out, "assets/fonts/cjk.ttf", "CJK");
            put(out, "../escape.ttf", "CJK");
            put(out, "assets/fonts/ignored.txt", "CJK");
            put(out, "assets/x-game/x-tl/x-chinese/x-style.rpyc",
                    "line_break east_asian text_font");
        }

        Set<Integer> required = new HashSet<>(Arrays.asList(
                (int) '中', (int) '文', (int) '界'));
        RenpyFontSupport.FontReport report = RenpyFontSupport.inspect(
                new TestContext(cache), apk, required);
        require(report.candidateFonts.size() == 2, "only safe font entries are candidates");
        require(report.candidateFonts.contains("assets/fonts/latin.ttf"), "latin candidate");
        require(report.candidateFonts.contains("assets/fonts/cjk.ttf"), "cjk candidate");
        require("assets/fonts/cjk.ttf".equals(report.bestFontPath), "highest coverage font wins");
        require(report.requiredCount == 3, "required count");
        require(report.coveredCount == 2, "covered count");
        require(report.missingCodePoints.contains((int) '界'), "missing glyph is reported");
        require(report.missingCodePoints.size() == 1, "only one glyph is missing");
        require(report.hasChineseStyleBucket, "Chinese translate style is detected");
        require(report.hasEastAsianLineBreakEvidence, "East Asian line-break evidence is detected");
        require(report.warnings.contains("font_preflight_multiple_candidates_best_coverage_selected"),
                "multiple candidates produce an explicit selection warning");
        require(!Files.list(cache.toPath()).findAny().isPresent(), "temporary font copies are cleaned up");
    }

    private static void put(ZipOutputStream out, String name, String body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body.getBytes(StandardCharsets.UTF_8));
        out.closeEntry();
    }

    private static final class TestContext extends Context {
        private final File cache;
        TestContext(File cache) { this.cache = cache; }
        @Override public File getCacheDir() { return cache; }
        @Override public File getFilesDir() { return cache; }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}

final class FontHarnessTypefaceMarker {}
"""
        typeface_stub = r"""
package android.graphics;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

public class Typeface {
    final String marker;
    private Typeface(String marker) { this.marker = marker; }
    public static Typeface createFromFile(String path) throws RuntimeException {
        try {
            return new Typeface(new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8));
        } catch (Exception error) {
            throw new RuntimeException(error);
        }
    }
}
"""
        paint_stub = r"""
package android.graphics;

public class Paint {
    private Typeface typeface;
    public Typeface setTypeface(Typeface value) { this.typeface = value; return value; }
    public boolean hasGlyph(String value) {
        if (value == null || value.isEmpty() || typeface == null) return false;
        int codePoint = value.codePointAt(0);
        if (typeface.marker.startsWith("LATIN")) return codePoint < 128;
        return codePoint < 128 || codePoint == '中' || codePoint == '文' || codePoint == '日';
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-font-support-test-") as temporary:
            temporary_path = Path(temporary)
            apk_path = temporary_path / "fixture.apk"
            cache_path = temporary_path / "cache"
            harness_path = temporary_path / "RenpyFontSupportHarness.java"
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(typeface_stub, "utf-8")
            (graphics_dir / "Paint.java").write_text(paint_stub, "utf-8")
            harness_path.write_text(harness, "utf-8")
            classes = temporary_path / "classes"
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    str(graphics_dir / "Typeface.java"),
                    str(graphics_dir / "Paint.java"),
                    str(FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyResourceLimits.java"),
                    str(FONT_SUPPORT),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RenpyFontSupportHarness",
                 str(apk_path), str(cache_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_renpy_font_preflight_capacity_covers_large_translation_sets(self):
        source = FONT_SUPPORT.read_text("utf-8")
        marker = "MAX_REQUIRED_CODE_POINTS ="
        line = next(line for line in source.splitlines() if marker in line)
        limit = int(line.split("=", 1)[1].split(";", 1)[0].strip())
        self.assertGreaterEqual(limit, 2048)

    def test_real_wca_font_preflight_does_not_trust_android_fallback(self):
        """The WCA font really lacks 欢 even when Paint.hasGlyph reports fallback support."""
        sample = ROOT / "apk-work" / "samples" / "renpy-modern" / "worlds-crossing-academy.apk"
        self.assertTrue(sample.is_file(), "real WCA sample APK is required for this regression")
        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import java.io.File;
import java.util.Collections;
import java.util.List;

public final class RealWcaFontFallbackHarness {
    public static void main(String[] args) throws Exception {
        File cache = new File(args[1]);
        if (!cache.mkdirs() && !cache.isDirectory()) {
            throw new AssertionError("cache directory unavailable");
        }
        RenpyFontSupport.FontReport report = RenpyFontSupport.inspect(
                new TestContext(cache), new File(args[0]),
                Collections.singleton((int) '\u6b22'));
        require(report.requiredCount == 1, "required count: " + report.requiredCount);
        require(report.coveredCount == 0,
                "WCA NotoSansJP must not be promoted by Android fallback: "
                        + report.coveredCount + " best=" + report.bestFontPath);
        require(report.missingCodePoints.contains((int) '\u6b22'),
                "missing U+6B22 must be reported: " + report.missingCodePoints);
        require(!report.isComplete(), "WCA missing glyph must block font preflight");
        require(!hasUnexpectedTempFiles(cache), "temporary font copies must be cleaned up");
    }

    private static boolean hasUnexpectedTempFiles(File cache) {
        File[] files = cache.listFiles();
        return files != null && files.length != 0;
    }

    private static final class TestContext extends Context {
        private final File cache;
        TestContext(File cache) { this.cache = cache; }
        @Override public File getCacheDir() { return cache; }
        @Override public File getFilesDir() { return cache; }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        typeface_stub = r"""
package android.graphics;

public class Typeface {
    public static Typeface createFromFile(String path) { return new Typeface(); }
}
"""
        paint_stub = r"""
package android.graphics;

public class Paint {
    public Typeface setTypeface(Typeface value) { return value; }
    public boolean hasGlyph(String value) {
        // Simulate Android resolving a missing glyph through a system fallback font.
        return value != null && !value.isEmpty();
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="real-wca-font-fallback-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RealWcaFontFallbackHarness.java"
            graphics_dir = temporary_path / "android" / "graphics"
            classes = temporary_path / "classes"
            graphics_dir.mkdir(parents=True)
            classes.mkdir()
            (graphics_dir / "Typeface.java").write_text(typeface_stub, "utf-8")
            (graphics_dir / "Paint.java").write_text(paint_stub, "utf-8")
            harness_path.write_text(harness, "utf-8")
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, sorted((FAST_SCAN / "stubs").rglob("*.java"))),
                    str(graphics_dir / "Typeface.java"), str(graphics_dir / "Paint.java"),
                    str(FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyResourceLimits.java"),
                    str(FONT_SUPPORT), str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RealWcaFontFallbackHarness",
                 str(sample), str(temporary_path / "cache")],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_bundled_cjk_font_is_packaged_for_runtime_fallback(self):
        """The translator APK must carry a CJK font that includes the WCA missing glyph."""
        builder = BUILDER.read_text("utf-8")
        workshop_builder = (ROOT / "apk-work" / "ui-redesign" / "build_workshop_apk.py").read_text(
            "utf-8"
        )
        for source in (builder, workshop_builder):
            self.assertIn("NotoSansSC-Regular.ttf", source)
            self.assertIn("assets/slg/fonts", source)
        bundled = FAST_SCAN / "assets" / "slg" / "fonts" / "NotoSansSC-Regular.ttf"
        self.assertTrue(bundled.is_file(), "bundled CJK font must exist in the native build tree")
        self.assertGreater(bundled.stat().st_size, 1_000_000)
        from fontTools.ttLib import TTFont
        font = TTFont(str(bundled), lazy=True)
        try:
            code_points = set()
            for table in font["cmap"].tables:
                code_points.update(table.cmap.keys())
            self.assertIn(ord("欢"), code_points)
        finally:
            font.close()

    def test_translation_compiler_selects_bundled_font_for_wca_missing_glyph(self):
        """A real WCA missing glyph must select the translator's bundled CJK font."""
        sample = ROOT / "apk-work" / "samples" / "renpy-modern" / "worlds-crossing-academy.apk"
        bundled = FAST_SCAN / "assets" / "slg" / "fonts" / "NotoSansSC-Regular.ttf"
        self.assertTrue(sample.is_file(), "real WCA sample APK is required for this regression")
        self.assertTrue(bundled.is_file(), "bundled CJK font is required for this regression")
        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.Collections;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class BundledFontSelectionHarness {
    public static void main(String[] args) throws Exception {
        File appApk = new File(args[1]);
        File font = new File(args[2]);
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(appApk));
             FileInputStream input = new FileInputStream(font)) {
            out.putNextEntry(new ZipEntry("assets/slg/fonts/NotoSansSC-Regular.ttf"));
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) out.write(buffer, 0, read);
            out.closeEntry();
        }

        Set<Integer> required = Collections.singleton((int) '\u6b22');
        TranslationCompiler.FontSelection selection = TranslationCompiler.selectFont(
                new TestContext(appApk), new File(args[0]), required);
        require(selection.bundledFallback, "WCA must choose bundled fallback");
        require("assets/x-game/x-slg-fonts/x-NotoSansSC-Regular.ttf".equals(
                selection.apkPath), "stable fallback APK path: " + selection.apkPath);
        require(selection.fontBytes.length == font.length(),
                "selected bundled font bytes must be copied into the target build");
    }

    private static final class TestContext extends Context {
        private final File appApk;
        TestContext(File appApk) { this.appApk = appApk; }
        @Override public String getPackageName() { return "com.slgtranslator.app"; }
        @Override public PackageManager getPackageManager() {
            return new PackageManager() {
                @Override public ApplicationInfo getApplicationInfo(String packageName, int flags) {
                    ApplicationInfo info = new ApplicationInfo();
                    info.packageName = packageName;
                    info.sourceDir = appApk.getAbsolutePath();
                    return info;
                }
            };
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="bundled-font-selection-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "BundledFontSelectionHarness.java"
            classes = temporary_path / "classes"
            classes.mkdir()
            harness_path.write_text(harness, "utf-8")
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, sorted((FAST_SCAN / "stubs").rglob("*.java"))),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.BundledFontSelectionHarness",
                 str(sample), str(temporary_path / "translator.apk"), str(bundled)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_font_preflight_reports_specific_error_code_to_bridge(self):
        font_source = FONT_SUPPORT.read_text("utf-8")
        scanner_source = SCANNER.read_text("utf-8")
        compiler_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                           / "TranslationCompiler.java").read_text("utf-8")
        self.assertIn("public String failureCode()", font_source)
        self.assertIn('font_preflight_total_size_limit', font_source)
        self.assertIn('result.put("code"', scanner_source)
        self.assertIn("fontFailureCode", compiler_source)

    def test_code_points_of_translations_excludes_private_use_area(self):
        """PUA glyphs copied from source icon fonts must not gate the text font."""
        harness = r"""
import com.slgtranslator.app.RenpyFontSupport;
import java.util.Arrays;
import java.util.Set;

public final class PuaFontGateHarness {
    public static void main(String[] args) {
        Set<Integer> required = RenpyFontSupport.codePointsOfTranslations(
                Arrays.asList("\u754c\uff0c\u597d", "\uE5E5\uE000\uF8FF"));
        require(required.contains((int) '\u754c'), "CJK glyph must be required");
        require(required.contains((int) '\uff0c'), "full-width comma must be required");
        require(!required.contains(0xE5E5), "PUA U+E5E5 must be excluded");
        require(!required.contains(0xE000), "PUA U+E000 must be excluded");
        require(!required.contains(0xF8FF), "PUA U+F8FF must be excluded");
        require(required.size() == 3, "unexpected required set: " + required);
        System.out.println("pua-font-gate-ok");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="pua-font-gate-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "PuaFontGateHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", os.pathsep.join([str(classes), third_party_classpath()]),
                 "PuaFontGateHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_translation_font_gate_adds_accepted_codepoints_outside_baseline(self):
        """An accepted translation glyph must enter the final gate, not baseline only."""
        compiler = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                    / "TranslationCompiler.java")
        source = compiler.read_text("utf-8")
        self.assertLess(source.index("baselineReport.isComplete()"),
                        source.index("codePointsOfTranslations(allTranslations)"))
        self.assertLess(source.index("codePointsOfTranslations(allTranslations)"),
                        source.index("if (!fontReport.isComplete())"))

        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.zip.DeflaterOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class TranslationFontGateHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File apk = new File(root, "fixture.apk");
        File cache = new File(root, "cache");
        File external = new File(root, "external");
        cache.mkdirs();
        external.mkdirs();

        byte[] pickle = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                Arrays.<String[]>asList(new String[]{"Hello", "Hello"}), 17, "fixture-key");
        byte[] template = deflate(pickle);
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/x-game/x-script.rpyc", template);
            put(out, "assets/fonts/cjk.ttf", "BASELINE_CJK");
            put(out, "assets/x-game/x-tl/x-chinese/x-style.rpyc",
                    "line_break east_asian text_font");
        }
        TranslationCompiler.TemplateMeta detected = TranslationCompiler.readTemplateMeta(apk);
        require(detected.compatibility != null && detected.compatibility.canGenerate(),
                "fixture template must reach the compile path: "
                        + (detected.compatibility == null ? "null" : detected.compatibility.reason)
                        + " protocol=" + (detected.compatibility == null
                        ? -1 : detected.compatibility.pickleProtocol)
                        + " builtins=" + (detected.compatibility != null
                        && detected.compatibility.usesBuiltins));

        Set<Integer> baseline = RenpyFontSupport.defaultRequiredCodePoints();
        require(!baseline.contains((int) '界'),
                "fixture character must be absent from fixed baseline");
        TestContext context = new TestContext(cache, external);
        RenpyFontSupport.FontReport baselineReport = RenpyFontSupport.inspect(
                context, apk, baseline);
        require(baselineReport.isComplete(),
                "baseline preflight must pass before the accepted translation is considered: "
                        + baselineReport.missingCodePoints);

        Set<Integer> finalRequired = new LinkedHashSet<>(baseline);
        finalRequired.addAll(RenpyFontSupport.codePointsOfTranslations(
                Arrays.asList("界")));
        require(finalRequired.contains((int) '界'),
                "accepted translation code point must be in final required set");
        RenpyFontSupport.FontReport finalReport = RenpyFontSupport.inspect(
                context, apk, finalRequired);
        require(finalReport.missingCodePoints.contains((int) '界'),
                "final report must expose missing accepted translation glyph");
        require(!finalReport.isComplete(), "missing accepted glyph must fail closed");

        File output = new File(external, "SLG-Translator-Output/x-tl/x-slgtranslated");
        output.mkdirs();
        File translation = new File(output, "translations.rpy");
        java.nio.file.Files.write(translation.toPath(), (
                "translate slgtranslated strings:\n"
                + "    old \"Hello\"\n"
                + "    new \"界\"\n").getBytes(StandardCharsets.UTF_8));

        require(TranslationCompiler.parseTranslationRpy(
                new String(java.nio.file.Files.readAllBytes(translation.toPath()),
                        StandardCharsets.UTF_8)).size() == 1,
                "fixture translation must be accepted by the production parser");

        TestCall call = new TestCall(apk.getAbsolutePath());
        TranslationCompiler.compileTranslationsIntoApk(context, call);
        require(call.rejected != null && call.rejected.contains(
                        "renpy_font_missing_glyphs: missingCodePoints="),
                "final translation gate must reject the accepted translation: " + call.rejected);
        require(call.rejected.contains(String.valueOf((int) '界')),
                "rejection must include missingCodePoints for 界: " + call.rejected);
        require(call.resolved == null, "blocked final gate must not resolve a compile result");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void put(ZipOutputStream out, String name, String body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body.getBytes(StandardCharsets.UTF_8));
        out.closeEntry();
    }

    private static void put(ZipOutputStream out, String name, byte[] body) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        out.write(body);
        out.closeEntry();
    }

    private static byte[] deflate(byte[] pickle) throws Exception {
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(compressed)) {
            stream.write(pickle);
        }
        return compressed.toByteArray();
    }

    private static final class TestContext extends Context {
        private final File cache;
        private final File external;

        TestContext(File cache, File external) {
            this.cache = cache;
            this.external = external;
        }

        @Override public File getCacheDir() { return cache; }
        @Override public File getFilesDir() { return cache; }
        @Override public File getExternalFilesDir(String type) { return external; }
    }

    private static final class TestCall extends PluginCall {
        private final String apkUri;
        String rejected;
        JSObject resolved;

        TestCall(String apkUri) { this.apkUri = apkUri; }

        @Override public String getString(String key) {
            if ("apkUri".equals(key)) return apkUri;
            if ("activationMode".equals(key)) return "selectable";
            return null;
        }

        @Override public void resolve(JSObject value) { resolved = value; }
        @Override public void reject(String message) { rejected = message; }
    }
}

final class TranslationFontGateHarnessMarker {}
"""
        typeface_stub = r"""
package android.graphics;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

public class Typeface {
    final String marker;
    private Typeface(String marker) { this.marker = marker; }
    public static Typeface createFromFile(String path) throws RuntimeException {
        try {
            return new Typeface(new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8));
        } catch (Exception error) {
            throw new RuntimeException(error);
        }
    }
}
"""
        paint_stub = r"""
package android.graphics;

public class Paint {
    private Typeface typeface;
    public Typeface setTypeface(Typeface value) { this.typeface = value; return value; }
    public boolean hasGlyph(String value) {
        if (value == null || value.isEmpty() || typeface == null) return false;
        int codePoint = value.codePointAt(0);
        return codePoint < 128 || codePoint != '界';
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-translation-font-gate-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationFontGateHarness.java"
            classes = temporary_path / "classes"
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(typeface_stub, "utf-8")
            (graphics_dir / "Paint.java").write_text(paint_stub, "utf-8")
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            try:
                subprocess.run(
                    [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                     "-d", str(classes), "-classpath", third_party_classpath(),
                     *map(str, stubs), str(graphics_dir / "Typeface.java"),
                     str(graphics_dir / "Paint.java"),
                     *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                     str(harness_path)],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as error:
                self.fail(error.stderr.decode("utf-8", errors="replace"))
            try:
                subprocess.run(
                    [str(JAVA), "-cp", str(classes),
                     "com.slgtranslator.app.TranslationFontGateHarness", str(temporary_path)],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as error:
                self.fail(error.stderr.decode("utf-8", errors="replace"))

    def test_renpy_style_font_rewrite_rebuilds_rpc2_and_supports_schinese(self):
        """A real RPC2/pickle fixture must rewrite only a font value, not bytes."""
        compiler = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "TranslationCompiler.java"
        source = compiler.read_text("utf-8")
        self.assertIn("cloneChineseStyleRpyc(File apk, String bestFontPath)", source)
        self.assertIn("x-schinese", source)
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import java.util.zip.InflaterInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.zip.DeflaterOutputStream;

public final class RenpyStyleFontHarness {
    private static final byte[] MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);

    public static void main(String[] args) throws Exception {
        byte[] pickle = concat(concat(concat(concat(concat(
                new byte[]{(byte) 0x80, 2}, shortString("text_font")), shortString("old.ttf")),
                shortString("style_name")), shortString("dialogue")),
                concat(shortString("schinese"), new byte[]{(byte) 0x2e}));
        byte[] fixture = rpc2(pickle);
        byte[] rewritten = TranslationCompiler.rewriteChineseStyleFont(
                fixture, "fonts/best.ttf");
        require(rewritten != null, "safe font rewrite must change the fixture");
        require(rewritten.length != fixture.length, "RPC2 payload must be rebuilt");
        require(rewritten[0] == 'R' && rewritten[9] == '2', "RPC2 magic survives");
        byte[] inflated = inflate(slot(rewritten, 1));
        String text = new String(inflated, StandardCharsets.UTF_8);
        require(text.contains("fonts/best.ttf"), "best font Ren'Py path is applied");
        require(!text.contains("old.ttf"), "old font reference is removed");
        require(inflated[inflated.length - 1] == (byte) 0x2e, "pickle STOP survives");

        String actualSource = "\n\ngui.text_font = \"tl/chinese/chinafont.ttf\"\n"
                + "\ngui.name_text_font = \"tl/chinese/SCJSSHT.otf\"\n"
                + "\ngui.interface_text_font = \"tl/chinese/FZLB.ttf\"\n"
                + "\ngui.button_text_font = gui.interface_text_font\n"
                + "\ngui.choice_button_text_font = gui.text_font\n"
                + "\ngui.system_font = \"tl/chinese/FZLB.ttf\"\n";
        byte[] actualPickle = concat(
                concat(concat(new byte[]{(byte) 0x80, 2}, binUnicode(actualSource)),
                        binUnicode("game/tl/chinese/style.rpy")),
                concat(binUnicode("chinese"), new byte[]{(byte) 0x2e}));
        byte[] actualFixture = rpc2(actualPickle);
        byte[] actualFontRewrite = TranslationCompiler.rewriteChineseStyleFont(
                actualFixture, "fonts/best.ttf");
        require(actualFontRewrite != null,
                "real x-style source string must be safely rewritten");
        String actualText = new String(inflate(slot(actualFontRewrite, 1)),
                StandardCharsets.UTF_8);
        require(actualText.contains("gui.text_font = \"fonts/best.ttf\""),
                "real source string must replace the text font path: " + actualText);
        require(actualText.contains("gui.button_text_font = gui.interface_text_font"),
                "non-path font assignments must remain intact");
        require(!actualText.contains("tl/chinese/chinafont.ttf")
                        && !actualText.contains("tl/chinese/SCJSSHT.otf")
                        && !actualText.contains("tl/chinese/FZLB.ttf"),
                "all Chinese source font paths must be replaced");

        byte[] actualLanguageRewrite = TranslationCompiler.rewriteRpycLanguage(
                actualFontRewrite, "chinese", "slgtranslated");
        require(actualLanguageRewrite != null,
                "real x-style metadata must support language rewriting");
        String actualLanguageText = new String(inflate(slot(actualLanguageRewrite, 1)),
                StandardCharsets.UTF_8);
        require(actualLanguageText.contains("slgtranslated"),
                "real x-style language value must be rewritten");
        require(actualLanguageText.contains("game/tl/slgtranslated/style.rpy"),
                "real x-style source filename must be rewritten");

        String translatorRuntimeFont = TranslationCompiler.translatorFontPath(
                "assets/x-game/x-AlimamaShuHeiTi-Bold.otf");
        require("tl/slgtranslated/AlimamaShuHeiTi-Bold.otf".equals(translatorRuntimeFont),
                "translator style must use a language-bucket font path: " + translatorRuntimeFont);
        String translatorAssetFont = TranslationCompiler.translatorFontAssetPath(
                "assets/x-game/x-AlimamaShuHeiTi-Bold.otf");
        require("assets/x-game/x-tl/x-slgtranslated/x-AlimamaShuHeiTi-Bold.otf".equals(
                        translatorAssetFont),
                "translator font asset must be copied into the active language bucket: "
                        + translatorAssetFont);

        File apk = new File(args[0]);
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/x-game/x-tl/x-schinese/x-style.rpyc", fixture);
        }
        byte[] cloned = TranslationCompiler.cloneChineseStyleRpyc(apk, "fonts/best.ttf");
        require(cloned != null, "schinese style bucket must be cloneable");
        require(new String(inflate(slot(cloned, 1)), StandardCharsets.UTF_8)
                        .contains("fonts/best.ttf"),
                "schinese clone must apply the best font");

        File actualApk = new File(args[0] + ".actual");
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(actualApk))) {
            put(out, "assets/x-game/x-tl/x-chinese/x-style.rpyc", actualFixture);
        }
        byte[] actualClone = TranslationCompiler.cloneChineseStyleRpyc(actualApk,
                "fonts/best.ttf");
        require(actualClone != null,
                "real x-style Chinese bucket must be cloneable");
        String actualCloneText = new String(inflate(slot(actualClone, 1)),
                StandardCharsets.UTF_8);
        require(actualCloneText.contains("fonts/best.ttf"),
                "real Chinese clone must apply the best font");
        require(actualCloneText.contains("slgtranslated"),
                "real Chinese clone must select the translator language");

        byte[] unsafe = concat(MAGIC, new byte[]{1, 2, 3});
        require(TranslationCompiler.rewriteChineseStyleFont(unsafe, "fonts/best.ttf") == null,
                "unknown pickle must be rejected, not binary-replaced");
    }

    private static byte[] shortString(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        return concat(new byte[]{(byte) 0x8c, (byte) bytes.length}, bytes);
    }

    private static byte[] binUnicode(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x58);
        putInt(out, bytes.length);
        out.write(bytes, 0, bytes.length);
        return out.toByteArray();
    }

    private static byte[] rpc2(byte[] pickle) throws Exception {
        byte[] compressed = deflate(pickle);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(MAGIC);
        int start = MAGIC.length + 3 * 12;
        for (int id = 1; id <= 2; id++) {
            putInt(out, id); putInt(out, start); putInt(out, compressed.length);
            start += compressed.length;
        }
        putInt(out, 0); putInt(out, 0); putInt(out, 0);
        out.write(compressed); out.write(compressed); out.write(new byte[16]);
        return out.toByteArray();
    }

    private static byte[] slot(byte[] rpyc, int wanted) {
        int pos = MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            int id = le(rpyc, pos), offset = le(rpyc, pos + 4), length = le(rpyc, pos + 8);
            if (id == 0) return null;
            if (id == wanted) {
                require(offset >= 0 && length >= 0 && offset + length <= rpyc.length,
                        "slot bounds");
                return slice(rpyc, offset, length);
            }
            pos += 12;
        }
        return null;
    }

    private static byte[] inflate(byte[] data) throws Exception {
        try (InflaterInputStream in = new InflaterInputStream(new ByteArrayInputStream(data));
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[256]; int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            return out.toByteArray();
        }
    }

    private static byte[] deflate(byte[] data) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(out)) {
            stream.write(data);
        }
        return out.toByteArray();
    }

    private static void put(ZipOutputStream out, String name, byte[] data) throws Exception {
        out.putNextEntry(new ZipEntry(name)); out.write(data); out.closeEntry();
    }
    private static void putInt(ByteArrayOutputStream out, int value) {
        out.write(value); out.write(value >>> 8); out.write(value >>> 16); out.write(value >>> 24);
    }
    private static int le(byte[] data, int pos) {
        return (data[pos] & 255) | ((data[pos + 1] & 255) << 8)
                | ((data[pos + 2] & 255) << 16) | ((data[pos + 3] & 255) << 24);
    }
    private static byte[] slice(byte[] data, int start, int length) {
        byte[] out = new byte[length]; System.arraycopy(data, start, out, 0, length); return out;
    }
    private static byte[] concat(byte[] a, byte[] b) {
        byte[] out = new byte[a.length + b.length]; System.arraycopy(a, 0, out, 0, a.length);
        System.arraycopy(b, 0, out, a.length, b.length); return out;
    }
    private static byte[] concat(byte[] a, byte[] b, byte[] c) { return concat(concat(a, b), c); }
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-style-font-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenpyStyleFontHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(), *map(str, stubs),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                subprocess.run(
                    [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.RenpyStyleFontHarness",
                     str(temporary_path / "fixture.apk")],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as error:
                self.fail(error.stderr.decode("utf-8", errors="replace"))

    def test_renpy_always_on_theme_font_rewrite_handles_wca_dialogue_style(self):
        """The real WCA theme must expose a CJK font to ordinary Say dialogue."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.zip.InflaterInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class RenpyAlwaysOnThemeFontHarness {
    private static final String THEME = "assets/x-renpy/x-common/x-00themes.rpyc";
    private static final String GUI = "assets/x-game/x-gui.rpyc";

    public static void main(String[] args) throws Exception {
        byte[] original;
        try (ZipFile zip = new ZipFile(new File(args[0]))) {
            ZipEntry entry = zip.getEntry(THEME);
            require(entry != null, "real WCA theme entry is missing");
            try (InputStream input = zip.getInputStream(entry)) {
                original = input.readAllBytes();
            }
        }

        Method rewrite = TranslationCompiler.class.getDeclaredMethod(
                "rewriteAlwaysOnThemeFont", byte[].class, String.class);
        rewrite.setAccessible(true);
        byte[] rewritten = (byte[]) rewrite.invoke(
                null, original, "NotoSansJP-Regular.ttf");
        require(rewritten != null,
                "always-on must rewrite the ordinary dialogue style in the real WCA theme");

        int targetAssignments = 0;
        int oldAssignments = 0;
        int dialogueStyleAssignments = 0;
        for (int slot = 1; slot <= 2; slot++) {
            String text = new String(inflate(slot(rewritten, slot)), StandardCharsets.UTF_8);
            targetAssignments += count(text,
                    "regular_font = \"NotoSansJP-Regular.ttf\"");
            oldAssignments += count(text, "style.say_dialogue.font = regular_font");
            dialogueStyleAssignments += count(text, "style.say_dialogue.font = regular_font");
        }
        require(targetAssignments == 2,
            "both WCA RPC2 slots must use the CJK font: " + targetAssignments);
        require(oldAssignments == 2,
                "ordinary dialogue style must still use the regular_font variable");
        require(dialogueStyleAssignments == 2,
                "both WCA RPC2 slots must retain the dialogue style assignment");
        String firstSlot = new String(inflate(slot(rewritten, 1)), StandardCharsets.UTF_8);
        require(!firstSlot.contains(
                        "regular_font = \"_theme_awt/Quicksand-Regular.ttf\""),
                "ordinary dialogue must not retain the Quicksand regular_font default");
        require("NotoSansJP-Regular.ttf".equals(TranslationCompiler.alwaysOnFontPath(
                        "assets/x-game/x-NotoSansJP-Regular.ttf")),
                "APK x- prefix must be removed from the logical runtime font path");

        File storeDirectory = new File(args[0] + ".pending");
        java.util.ArrayList<String[]> pending = new java.util.ArrayList<>();
        try (PendingApkEntryStore store = new PendingApkEntryStore(storeDirectory)) {
            Method append = TranslationCompiler.class.getDeclaredMethod(
                    "appendAlwaysOnThemeFontEntry", File.class, String.class,
                    java.util.List.class, PendingApkEntryStore.class);
            append.setAccessible(true);
            append.invoke(null, new File(args[0]),
                    "assets/x-game/x-NotoSansJP-Regular.ttf", pending, store);
            require(pending.size() == 1,
                    "always-on production path must stage exactly one WCA theme entry");
            require(THEME.equals(pending.get(0)[0]),
                    "staged theme path: " + pending.get(0)[0]);
            String staged = new String(inflate(slot(storePayload(store, 0), 1)),
                    StandardCharsets.UTF_8);
            require(staged.contains("regular_font = \"NotoSansJP-Regular.ttf\""),
                    "staged production payload must contain the CJK regular font");

            Method appendGui = TranslationCompiler.class.getDeclaredMethod(
                    "appendAlwaysOnGuiFontEntry", File.class, String.class,
                    java.util.List.class, PendingApkEntryStore.class);
            appendGui.setAccessible(true);
            appendGui.invoke(null, new File(args[0]),
                    "assets/x-game/x-NotoSansJP-Regular.ttf", pending, store);
            require(pending.size() == 2,
                    "always-on production path must stage theme and GUI font entries");
            require(GUI.equals(pending.get(1)[0]),
                    "staged GUI path: " + pending.get(1)[0]);
            String stagedGui = new String(inflate(slot(storePayload(store, 1), 1)),
                    StandardCharsets.UTF_8);
            require(stagedGui.contains("NotoSansJP-Regular.ttf"),
                    "staged GUI payload must contain the CJK text font");
            require(!stagedGui.contains("RedRose-Regular.ttf"),
                    "staged GUI payload must not retain the RedRose text font");
        }
    }

    private static byte[] slot(byte[] rpyc, int wanted) {
        int pos = 10;
        while (pos + 12 <= rpyc.length) {
            int id = le(rpyc, pos);
            int offset = le(rpyc, pos + 4);
            int length = le(rpyc, pos + 8);
            if (id == 0) return null;
            if (id == wanted) return slice(rpyc, offset, length);
            pos += 12;
        }
        return null;
    }

    private static byte[] inflate(byte[] compressed) throws Exception {
        try (InflaterInputStream input = new InflaterInputStream(
                new ByteArrayInputStream(compressed));
             java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) {
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    private static byte[] storePayload(PendingApkEntryStore store, int index) throws Exception {
        try (InputStream input = store.openPayload(index);
             java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) {
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    private static int count(String value, String needle) {
        int total = 0;
        int from = 0;
        while ((from = value.indexOf(needle, from)) >= 0) {
            total++;
            from += needle.length();
        }
        return total;
    }

    private static int le(byte[] data, int pos) {
        return (data[pos] & 255) | ((data[pos + 1] & 255) << 8)
                | ((data[pos + 2] & 255) << 16) | ((data[pos + 3] & 255) << 24);
    }

    private static byte[] slice(byte[] data, int offset, int length) {
        require(offset >= 0 && length >= 0 && offset + length <= data.length,
                "RPYC slot is out of bounds");
        byte[] result = new byte[length];
        System.arraycopy(data, offset, result, 0, length);
        return result;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        sample = ROOT / "apk-work" / "samples" / "renpy-modern" / "worlds-crossing-academy.apk"
        self.assertTrue(sample.is_file(), "real WCA sample APK is required for this regression")
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-always-on-theme-font-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenpyAlwaysOnThemeFontHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RenpyAlwaysOnThemeFontHarness", str(sample)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_renpy_font_rewrite_refreshes_pycode_and_pyexpr_hashcodes(self):
        """Real WCA font rewrites must refresh PyExpr and PyCode state hashes."""
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class RenpyFontHashHarness {
    public static void main(String[] args) throws Exception {
        File apk = new File(args[0]);
        byte[] gui = readEntry(apk, "assets/x-game/x-gui.rpyc");
        byte[] rewrittenGui = TranslationCompiler.rewriteChineseStyleFont(
                gui, "NotoSansJP-Regular.ttf");
        require(rewrittenGui != null, "real WCA GUI font rewrite must change the sample");

        byte[] theme = readEntry(apk, "assets/x-renpy/x-common/x-00themes.rpyc");
        java.lang.reflect.Method themeRewrite =
                TranslationCompiler.class.getDeclaredMethod(
                        "rewriteAlwaysOnThemeFont", byte[].class, String.class);
        themeRewrite.setAccessible(true);
        byte[] rewrittenTheme = (byte[]) themeRewrite.invoke(
                null, theme, "NotoSansJP-Regular.ttf");
        require(rewrittenTheme != null, "real WCA theme font rewrite must change the sample");

        System.out.println("GUI=" + Base64.getEncoder().encodeToString(rewrittenGui));
        System.out.println("THEME=" + Base64.getEncoder().encodeToString(rewrittenTheme));
    }

    private static byte[] readEntry(File apk, String name) throws Exception {
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(name);
            require(entry != null, "missing WCA entry: " + name);
            try (InputStream input = zip.getInputStream(entry);
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int read;
                while ((read = input.read(buffer)) != -1) {
                    output.write(buffer, 0, read);
                }
                return output.toByteArray();
            }
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        compiler = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "TranslationCompiler.java"
        self.assertIn("rewriteAlwaysOnThemeFont", compiler.read_text("utf-8"))
        sample = ROOT / "apk-work" / "samples" / "renpy-modern" / "worlds-crossing-academy.apk"
        self.assertTrue(sample.is_file(), "real WCA sample APK is required for this regression")
        with tempfile.TemporaryDirectory(prefix="renpy-font-hash-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenpyFontHashHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, sorted((FAST_SCAN / "stubs").rglob("*.java"))),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RenpyFontHashHarness", str(sample)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stderr or result.stdout,
            )

        outputs = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                outputs[key] = __import__("base64").b64decode(value)

        self.assertIn("GUI", outputs)
        self.assertIn("THEME", outputs)
        expected_gui_hash = 0xD8220EBF

        def integer(opcode):
            if opcode[0].name in {
                "BININT", "BININT1", "BININT2", "LONG1", "LONG4", "INT", "LONG"
            }:
                return int(opcode[1])
            return None

        def skip_memoize(ops, index):
            while index < len(ops) and ops[index][0].name == "MEMOIZE":
                index += 1
            return index

        def parse_pyexpr_state(ops, source_index):
            index = skip_memoize(ops, source_index + 1)
            self.assertLess(index + 5, len(ops))
            hash_index = index + 3
            self.assertEqual(ops[index + 4][0].name, "BININT1")
            self.assertEqual(ops[index + 5][0].name, "TUPLE")
            return integer(ops[hash_index]), index + 5

        def parse_pycode_state(ops, source_index):
            index = skip_memoize(ops, source_index + 1)
            self.assertLess(index + 8, len(ops))
            self.assertEqual(ops[index + 2][0].name, "TUPLE2")
            index = skip_memoize(ops, index + 3)
            hash_index = index + 2
            self.assertEqual(ops[index + 4][0].name, "TUPLE")
            return integer(ops[hash_index]), index + 4

        def find_string_ops(payload, predicate):
            return [
                index
                for index, operation in enumerate(pickletools.genops(payload))
                if isinstance(operation[1], str) and predicate(operation[1])
            ]

        def inflate_slots(rpyc):
            return [
                zlib.decompress(rpyc[offset:offset + length])
                for _slot_id, offset, length in rpc2_slots(rpyc)
            ]

        gui_slots = inflate_slots(outputs["GUI"])
        self.assertGreaterEqual(len(gui_slots), 2)
        for payload in gui_slots:
            ops = list(pickletools.genops(payload))
            source_indices = find_string_ops(
                payload,
                lambda value: value == '"NotoSansJP-Regular.ttf"',
            )
            self.assertGreaterEqual(len(source_indices), 1)
            for source_index in source_indices:
                pyexpr_hash, pyexpr_end = parse_pyexpr_state(ops, source_index)
                self.assertEqual(pyexpr_hash, expected_gui_hash)
                reduce_index = next(
                    index for index in range(pyexpr_end + 1, min(len(ops), pyexpr_end + 5))
                    if ops[index][0].name == "REDUCE"
                )
                outer_index = skip_memoize(ops, reduce_index + 1)
                self.assertEqual(ops[outer_index + 2][0].name, "TUPLE2")
                self.assertEqual(ops[outer_index + 4][0].name, "BINGET")
                self.assertEqual(ops[outer_index + 5][0].name, "BININT1")
                self.assertEqual(integer(ops[outer_index + 6]), expected_gui_hash)
                self.assertEqual(ops[outer_index + 7][0].name, "BININT1")
                self.assertEqual(ops[outer_index + 8][0].name, "TUPLE")

        theme_slots = inflate_slots(outputs["THEME"])
        self.assertGreaterEqual(len(theme_slots), 2)
        for payload in theme_slots:
            ops = list(pickletools.genops(payload))
            source_indices = find_string_ops(
                payload,
                lambda value: 'regular_font = "NotoSansJP-Regular.ttf"' in value,
            )
            self.assertGreaterEqual(len(source_indices), 1)
            for source_index in source_indices:
                source = ops[source_index][1]
                self.assertNotIn('regular_font = "_theme_awt/Quicksand-Regular.ttf"', source)
                theme_hash, _ = parse_pycode_state(ops, source_index)
                self.assertEqual(theme_hash, self._fnv32(source))

    @staticmethod
    def _fnv32(value):
        result = 0x811C9DC5
        for character in value:
            result ^= ord(character)
            result = (result * 0x01000193) & 0xFFFFFFFF
        return result

    def test_renpy_font_preflight_is_before_first_model_call_and_read_bridge_returns_gate(self):
        scanner = SCANNER.read_text("utf-8")
        self.assertIn("fontPreflight(Context context, File apk)", scanner)
        self.assertIn('result.put("fontReport"', scanner)
        self.assertIn('result.put("fontGate"', scanner)
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        self.assertIn("__slgFontPreflightReport", source)
        self.assertIn("__slgFontPreflightBlocked", source)
        generated_marker = "__slgFontPreflightBlocked"
        self.assertLess(source.index(generated_marker), source.index("async function Vo"))
        self.assertIn("defaultRequiredCodePoints", scanner)
        compiler = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                    / "TranslationCompiler.java").read_text("utf-8")
        self.assertIn("baselineReport.isComplete()", compiler)
        self.assertIn("String failureCode = fontFailureCode(baselineReport)", compiler)
        self.assertIn('call.reject(failureCode + ": baseline missingCodePoints="', compiler)
        self.assertIn("codePointsOfTranslations(allTranslations)", compiler)

    def test_font_preflight_state_resets_when_scan_selection_starts(self):
        """A second APK must not inherit the first APK's successful preflight."""
        import patch_workshop_ui as patcher

        patched = patcher.patch_scan_flow(
            ",xe=async()=>{legacyScanFlow},Se=async()=>{legacyNextFlow}"
        )
        scan_start = patched.index("scanSelectedApk=async(")
        scan_state = patched[scan_start:scan_start + 900]
        for token in (
            "window.__slgFontPreflightDone=false",
            "window.__slgFontPreflightBlocked=false",
            "window.__slgFontPreflightReport=null",
        ):
            self.assertIn(token, scan_state)
        self.assertLess(
            scan_state.index("window.__slgFontPreflightDone=false"),
            scan_state.index("window.__slgSelectionMeta=Object.assign"),
        )

    def test_always_on_dialogue_patch_skips_screen_and_framework_sources(self):
        """Screen/style/gui files must never be dialogue-patched in place."""
        harness = r"""
package com.slgtranslator.app;

public final class DialoguePatchableHarness {
    public static void main(String[] args) {
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-screens.rpyc"),
                "screens must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-screens.rpymc"),
                "screens rpymc must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-renpy/x-common/x-00themes.rpyc"),
                "framework themes must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-renpy/x-common/x-_layout/x-screen_main_menu.rpymc"),
                "framework layout must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-gui/x-atl_text_tag.rpyc"),
                "gui must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-options.rpyc"),
                "options must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-affection_map_screen.rpyc"),
                "map screen must be excluded");
        require(TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-script.rpyc"),
                "dialogue script must be patchable");
        require(TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-quest files/x-S2E6/x-S2E6.rpyc"),
                "quest dialogue must be patchable");
        require(TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-gamevar.rpyc"),
                "gamevar is not a screen file and stays patchable");
        require(!TranslationCompiler.isDialoguePatchableSource(null), "null must be excluded");
        require(!TranslationCompiler.isDialoguePatchableSource("assets/x-game/x-screens.txt"), "non-rpyc must be excluded");
        System.out.println("dialogue-patchable-ok");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="dialogue-patchable-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "DialoguePatchableHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", os.pathsep.join([str(classes), third_party_classpath()]),
                 "com.slgtranslator.app.DialoguePatchableHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_font_preflight_missing_glyphs_warn_and_defer_to_compile_bundle(self):
        """Missing baseline glyphs must not hard-block: the compile step bundles a font."""
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        start = source.index("let _fontTarget=ae.find")
        end = source.index("window.__slgFontPreflightDone=true", start)
        block = source[start:end]
        self.assertIn("window.__slgFontPreflightBlocked=!_fr?.fontReport||((_fr?.fontReport?.warnings||[]).some", block)
        self.assertNotIn("_fr?.fontGate===`blocked`", block)
        self.assertIn("编译阶段将尝试注入内置中文字体", block)

    def test_font_preflight_selects_rpymc_and_blocks_without_a_compiled_target(self):
        """The preflight target matrix must include RPYMC and fail closed when empty."""
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        start = source.index("let _fontTarget=ae.find")
        end = source.index("window.__slgFontPreflightDone=true", start)
        block = source[start:end]
        self.assertIn("fileType===`rpyc`", block)
        self.assertIn("fileType===`rpymc`", block)
        self.assertIn(r"/\\.rp(?:y|ym)c$/i", block)
        no_target = block.index("if(!_fontTarget)")
        self.assertIn("__slgFontPreflightBlocked=true", block[no_target:])
        self.assertIn("ce(!1);return", block[no_target:])
        self.assertIn("没有可检查的 Ren'Py 编译脚本", block[no_target:])
        self.assertNotIn("__slgFontPreflightDone=true", block[no_target:])
        self.assertLess(no_target, block.index("readRenpyTexts"))

    def test_renpy_preflight_reports_safe_warning_and_extract_only(self):
        """The single preflight entry point must classify the three plan snapshots."""
        harness = r"""
import com.slgtranslator.app.RenpyCompatibilityReport;
import com.slgtranslator.app.RenpyPreflight;
import com.slgtranslator.app.RpycCompatibility;
import com.slgtranslator.app.RpycPickleWriter;
import com.slgtranslator.app.EngineCapabilities;
import com.slgtranslator.app.RenpyEngineAdapter;
import java.io.ByteArrayOutputStream;
import java.util.Arrays;
import java.util.Collections;
import java.util.zip.DeflaterOutputStream;

public final class RenpyPreflightHarness {
    private static byte[] compressed(String module) throws Exception {
        byte[] pickle = ("\u0080\u0002c" + module + "\nstr\n.").getBytes("ISO-8859-1");
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(output)) {
            stream.write(pickle);
        }
        return output.toByteArray();
    }

    private static byte[] deflate(byte[] raw) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (DeflaterOutputStream stream = new DeflaterOutputStream(output)) {
            stream.write(raw);
        }
        return output.toByteArray();
    }

    private static byte[] modernPickle() throws Exception {
        return deflate(RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY3_MODERN, "schinese", "game/x-script.rpyc",
                Collections.<String[]>emptyList(), 17, "test-key"));
    }

    private static RenpyPreflight.SourceSet source(String menu, RpycCompatibility.Report rpyc) {
        return new RenpyPreflight.SourceSet(
                "assets/x-game/x-script.rpyc",
                rpyc,
                2, 1, Arrays.asList("english", "schinese"), menu,
                null, 7, 10, 1);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        RpycCompatibility.Report modernReport = RpycCompatibility.inspect(modernPickle());
        RenpyCompatibilityReport safe = RenpyPreflight.inspect(null, source("standard", modernReport));
        require(safe.supportLevel == RenpyCompatibilityReport.SupportLevel.SAFE, "modern standard menu must be SAFE");
        require(safe.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.SELECTABLE_LANGUAGE,
                "modern standard menu must be selectable");

        RenpyCompatibilityReport warning = RenpyPreflight.inspect(null, source("none", modernReport));
        require(warning.supportLevel == RenpyCompatibilityReport.SupportLevel.WARNING, "no menu must be WARNING");
        require(warning.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.ALWAYS_ON,
                "no menu must be always-on");

        RenpyCompatibilityReport legacy = RenpyPreflight.inspect(null, source("standard",
                RpycCompatibility.inspect(compressed("__builtin__"))));
        require(legacy.supportLevel == RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY,
                "python2 writer gap must be extract-only");
        require(legacy.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.NONE,
                "extract-only must not activate a writer strategy");
        require(legacy.issues.size() > 0, "legacy report must carry a stable issue");
        EngineCapabilities safeCaps = safe.capabilities();
        require(safeCaps.workflow == EngineCapabilities.Workflow.PATCHABLE_VERIFIED,
                "SAFE must remain patchable verified");
        require(safeCaps.canTranslate && safeCaps.canWritePatch,
                "SAFE must translate and write");
        require(safeCaps.canValidateRuntime,
                "SAFE selectable-language patch must allow runtime validation");
        EngineCapabilities warningCaps = warning.capabilities();
        require(warningCaps.canValidateRuntime,
                "WARNING always-on patch must allow runtime validation");
        EngineCapabilities legacyCaps = legacy.capabilities();
        require(legacyCaps.workflow == EngineCapabilities.Workflow.TRANSLATABLE_NO_PATCH,
                "EXTRACT_ONLY must become translatable without patch");
        require(legacyCaps.canExtractStructured && legacyCaps.canTranslate,
                "EXTRACT_ONLY must allow structured translation");
        require(!legacyCaps.canWritePatch && !legacyCaps.canActivate,
                "EXTRACT_ONLY must keep writer and activation disabled");
        require(!legacyCaps.canValidateRuntime,
                "EXTRACT_ONLY must not allow runtime validation");
        require(!legacy.isTranslationBlocked() && legacy.isWriterBlocked(),
                "translation and writer gates must be independent");
        RenpyEngineAdapter adapter = RenpyEngineAdapter.INSTANCE;
        require("renpy".equals(adapter.adapterId()), "adapter id must be stable");
        require("renpy-rpyc-existing".equals(adapter.writer().writerId()),
                "writer id must describe the existing backend");
        require(adapter.writer().supports(safe.rpyc), "safe report must use existing writer");
        require(adapter.writer().supports(warning.rpyc), "warning report keeps existing writer");
        require(!adapter.writer().supports(legacy.rpyc), "legacy report must not gain a writer");
        require(adapter.capabilities(legacy).workflow
                        == EngineCapabilities.Workflow.TRANSLATABLE_NO_PATCH,
                "adapter must expose export-only workflow");
        RenpyCompatibilityReport unsupported = RenpyPreflight.inspect(null, null);
        require(unsupported.supportLevel == RenpyCompatibilityReport.SupportLevel.UNSUPPORTED,
                "missing source set must be unsupported");
        require(unsupported.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.NONE,
                "unsupported source set must not select an activation strategy");
        require(unsupported.capabilities().workflow == EngineCapabilities.Workflow.UNSUPPORTED,
                "unsupported workflow must stay unsupported");
        require(unsupported.isTranslationBlocked() && unsupported.isWriterBlocked(),
                "unsupported must block every downstream capability");
        require(unsupported.issues.size() == 1
                        && "renpy_preflight_missing_source".equals(unsupported.issues.get(0).code),
                "missing source set must expose one stable issue code");
        require(unsupported.isBlocked(), "unsupported report must be blocked");
        int extractionCalls = 0, modelCalls = 0, buildCalls = 0;
        if (!unsupported.isBlocked()) {
            extractionCalls++;
            modelCalls++;
            buildCalls++;
        }
        require(extractionCalls == 0 && modelCalls == 0 && buildCalls == 0,
                "unsupported snapshot must not permit extract/model/build actions");
        String sanitized = safe.toSanitizedJson();
        require(sanitized.contains("templatePath"), "sanitized report must contain diagnostics");
        require(!sanitized.contains("apiKey") && !sanitized.contains("apkBytes")
                && !sanitized.contains("fullScript"), "sanitized report must not contain secrets or APK contents");
        String unsupportedJson = unsupported.toSanitizedJson();
        require(unsupportedJson.contains("renpy_preflight_missing_source")
                        && unsupportedJson.contains("UNSUPPORTED")
                        && unsupportedJson.contains("NONE"),
                "unsupported JSON must preserve only the stable gate diagnostics");
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-preflight-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RenpyPreflightHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(), *map(str, stubs),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "RenpyPreflightHarness"],
                check=True,
            )

    def test_runtime_validation_classifies_install_launch_and_text_evidence(self):
        """Runtime evidence must map to one stable status without guessing runtime rendering."""
        harness = r"""
import com.slgtranslator.app.RuntimeValidationSupport;

public final class RuntimeValidationHarness {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void expect(String code, String display, RuntimeValidationSupport.Evidence evidence) {
        RuntimeValidationSupport.Status status = RuntimeValidationSupport.classify(evidence);
        require(code.equals(status.code), "expected " + code + " got " + status.code);
        require(display.equals(status.display), "expected display " + display + " got " + status.display);
    }

    public static void main(String[] args) {
        expect("NOT_INSTALLED", "安装未成功", new RuntimeValidationSupport.Evidence(false, false, false, null));
        expect("PATCH_NOT_APPLIED", "未生效（入口缺失）", new RuntimeValidationSupport.Evidence(true, false, false, null));
        expect("LAUNCH_FAILED", "启动失败", new RuntimeValidationSupport.Evidence(true, true, false, null));
        expect("STRING_MISMATCH", "label 失效（文本未出现）", new RuntimeValidationSupport.Evidence(true, true, true, false));
        expect("ACTIVE", "汉化生效", new RuntimeValidationSupport.Evidence(true, true, true, true));
        expect("PENDING_CONFIRM", "待确认", new RuntimeValidationSupport.Evidence(true, true, true, null));
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="runtime-validation-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "RuntimeValidationHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(), *map(str, stubs),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "RuntimeValidationHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_evidence_manifest_join_requires_exact_hashes_and_distinct_fingerprints(self):
        """Verified levels must come from complete, hash-bound evidence records."""
        harness = r'''
package com.slgtranslator.app;

public final class EvidenceManifestJoinHarness {
    private static final String APK_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private static final String RPYC_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static String sample(String id, String fingerprint, String level,
                                 boolean launched) {
        return new StringBuilder()
                .append("{\"sampleId\":\"").append(id).append("\",")
                .append("\"engine\":{\"renpyVersion\":\"8.5.3\",")
                .append("\"versionEvidence\":{\"sourceApkEntry\":\"assets/version.txt\",")
                .append("\"value\":\"8.5.3\"},")
                .append("\"structuralDialect\":\"MODERN_ENVELOPE_VERIFIED\"},")
                .append("\"package\":{\"sourceApk\":{\"sha256\":\"").append(APK_SHA).append("\"}},")
                .append("\"objectGraph\":{\"extractedArtifact\":{\"sha256\":\"").append(RPYC_SHA).append("\"},")
                .append("\"objectGraphFingerprint\":\"").append(fingerprint).append("\"},")
                .append("\"structuralVerification\":{\"status\":\"passed\",")
                .append("\"compiledTranslationValidated\":true,\"independentReread\":\"passed\"},")
                .append("\"runtimeVerification\":{\"install\":\"passed\",")
                .append("\"launch\":\"").append(launched ? "passed" : "pending").append("\",")
                .append("\"processAlive\":true,\"rpycLoadErrors\":0,")
                .append("\"fatalExceptions\":0,\"tracebacks\":0,")
                .append("\"localizedDialogueVisualConfirmation\":{\"status\":\"confirmed\"}},")
                .append("\"verificationLevel\":\"").append(level).append("\"}")
                .toString();
    }

    private static String sampleWithoutVersionEvidence(String id, String fingerprint,
                                                        String level) {
        return new StringBuilder()
                .append("{\"sampleId\":\"").append(id).append("\",")
                .append("\"engine\":{\"structuralDialect\":\"MODERN_ENVELOPE_VERIFIED\"},")
                .append("\"package\":{\"sourceApk\":{\"sha256\":\"").append(APK_SHA).append("\"}},")
                .append("\"objectGraph\":{\"extractedArtifact\":{\"sha256\":\"").append(RPYC_SHA).append("\"},")
                .append("\"objectGraphFingerprint\":\"").append(fingerprint).append("\"},")
                .append("\"structuralVerification\":{\"status\":\"passed\",")
                .append("\"compiledTranslationValidated\":true,\"independentReread\":\"passed\"},")
                .append("\"runtimeVerification\":{\"install\":\"passed\",\"launch\":\"passed\",")
                .append("\"processAlive\":true,\"rpycLoadErrors\":0,\"fatalExceptions\":0,")
                .append("\"tracebacks\":0,")
                .append("\"localizedDialogueVisualConfirmation\":{\"status\":\"confirmed\"}},")
                .append("\"verificationLevel\":\"").append(level).append("\"}")
                .toString();
    }

    private static String manifest(String... samples) {
        StringBuilder out = new StringBuilder("{\"schemaVersion\":1,\"samples\":[");
        for (int i = 0; i < samples.length; i++) {
            if (i > 0) out.append(',');
            out.append(samples[i]);
        }
        return out.append("]}").toString();
    }

    public static void main(String[] args) {
        String one = manifest(sample("wca", "fp-1", "modern_85_sample_verified", true));
        RenpyVerificationEvidence.Result verified = RenpyVerificationEvidence.join(
                one, APK_SHA, RPYC_SHA, "fp-1", "MODERN_ENVELOPE_VERIFIED");
        require("modern_85_sample_verified".equals(verified.level),
                "complete sample must verify: " + verified.level);

        RenpyVerificationEvidence.Result hashMismatch = RenpyVerificationEvidence.join(
                one, APK_SHA, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
                "fp-1", "MODERN_ENVELOPE_VERIFIED");
        require("sample_pending".equals(hashMismatch.level),
                "artifact hash mismatch must fail closed: " + hashMismatch.reason);

        String second = sample("wca-2", "fp-2", "modern_85_sample_verified", true);
        RenpyVerificationEvidence.Result dialect = RenpyVerificationEvidence.join(
                manifest(sample("wca", "fp-1", "modern_85_sample_verified", true), second),
                APK_SHA, RPYC_SHA, "fp-1", "MODERN_ENVELOPE_VERIFIED");
        require("modern_85_dialect_verified".equals(dialect.level),
                "two distinct fingerprints must verify dialect: " + dialect.level);

        RenpyVerificationEvidence.Result duplicate = RenpyVerificationEvidence.join(
                manifest(sample("wca", "fp-1", "modern_85_sample_verified", true),
                        sample("wca-copy", "fp-1", "modern_85_sample_verified", true)),
                APK_SHA, RPYC_SHA, "fp-1", "MODERN_ENVELOPE_VERIFIED");
        require("modern_85_sample_verified".equals(duplicate.level),
                "same fingerprint must not promote dialect: " + duplicate.level);

        String incomplete = manifest(sample("wca", "fp-1", "modern_85_sample_verified", false));
        RenpyVerificationEvidence.Result pending = RenpyVerificationEvidence.join(
                incomplete, APK_SHA, RPYC_SHA, "fp-1", "MODERN_ENVELOPE_VERIFIED");
        require("sample_pending".equals(pending.level),
                "missing runtime launch evidence must fail closed: " + pending.reason);

        String missingVersion = manifest(sampleWithoutVersionEvidence(
                "wca-no-version", "fp-version", "modern_85_sample_verified"));
        RenpyVerificationEvidence.Result missingVersionResult = RenpyVerificationEvidence.join(
                missingVersion, APK_SHA, RPYC_SHA, "fp-version", "MODERN_ENVELOPE_VERIFIED");
        require("sample_pending".equals(missingVersionResult.level),
                "missing Ren'Py version source must fail closed: " + missingVersionResult.reason);
        System.out.println("OK");
    }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-evidence-join-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "EvidenceManifestJoinHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.EvidenceManifestJoinHarness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertEqual(run_result.stdout.strip(), "OK")

    def test_verification_level_stays_separate_from_structural_dialect_in_reports(self):
        """External evidence level must travel through preflight without changing dialect."""
        scanner_source = SCANNER.read_text("utf-8")
        for token in (
            '"verificationLevel"',
            'report.verificationLevel',
            'RenpyVerificationEvidence.PENDING_LEVEL',
        ):
            self.assertIn(token, scanner_source)
        harness = r'''
package com.slgtranslator.app;

import java.util.Collections;

public final class VerificationLevelReportHarness {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        RpycCompatibility.Report rpyc = new RpycCompatibility.Report(
                "rpc2", 2, 5, true, false,
                RpycCompatibility.GenerationSupport.MODERN_SUPPORTED,
                "modern_envelope_verified",
                RpycCompatibility.ModernDialect.MODERN_ENVELOPE_VERIFIED);
        RenpyPreflight.SourceSet source = new RenpyPreflight.SourceSet(
                "game/script.rpyc", rpyc, 0, 0, Collections.<String>emptyList(),
                "renpy", null, 0, 0, 0, "modern_85_sample_verified");
        RenpyCompatibilityReport report = RenpyPreflight.inspect(null, source);
        require("modern_85_sample_verified".equals(report.verificationLevel),
                "verification level must survive preflight: " + report.verificationLevel);
        String json = report.toSanitizedJson();
        require(json.contains("\"verificationLevel\":\"modern_85_sample_verified\""),
                "report JSON must expose verification level: " + json);
        require(json.contains("\"dialect\":\"MODERN_ENVELOPE_VERIFIED\""),
                "report JSON must retain structural dialect: " + json);
        require(!json.contains("\"dialect\":\"modern_85_sample_verified\""),
                "verification level must not replace structural dialect: " + json);
        System.out.println("OK");
    }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="renpy-verification-report-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "VerificationLevelReportHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.VerificationLevelReportHarness"],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertEqual(run_result.stdout.strip(), "OK")

    def test_launch_probe_resolves_intent_and_reports_launch_outcome(self):
        """Launch probe must resolve intent purely and report startActivity outcome honestly."""
        harness = r"""
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import com.slgtranslator.app.RuntimeValidationSupport;
import com.slgtranslator.app.RuntimeValidationSupport.ContextLike;
import com.slgtranslator.app.RuntimeValidationSupport.LaunchResult;

public final class LaunchProbeHarness {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static ContextLike fake(final boolean resolvable) {
        return new ContextLike() {
            @Override public Intent getLaunchIntentForPackage(String packageName) {
                return resolvable ? new Intent("android.intent.action.MAIN") : null;
            }
        };
    }

    public static void main(String[] args) {
        require(!RuntimeValidationSupport.resolveLaunchable(null, "game"),
                "null context must not resolve");
        require(!RuntimeValidationSupport.resolveLaunchable(fake(false), "game"),
                "unresolvable package must not resolve");
        require(RuntimeValidationSupport.resolveLaunchable(fake(true), "game"),
                "resolvable package must resolve");
        require(!RuntimeValidationSupport.resolveLaunchable(fake(true), null),
                "null package must not resolve");
        require(!RuntimeValidationSupport.resolveLaunchable(fake(true), ""),
                "blank package must not resolve");
        require(!RuntimeValidationSupport.resolveLaunchable(fake(true), "   "),
                "whitespace package must not resolve");

        LaunchResult missing = RuntimeValidationSupport.launchGame(
                new TestContext(new TestPackageManager(false)), "game");
        require(!missing.resolved && !missing.started,
                "missing launch intent must be (false,false)");

        LaunchResult launched = RuntimeValidationSupport.launchGame(
                new TestContext(new TestPackageManager(true)), "game");
        require(launched.resolved && launched.started,
                "launchable game must be (true,true)");

        TestContext throwing = new TestContext(new TestPackageManager(true));
        throwing.failStart = true;
        LaunchResult failed = RuntimeValidationSupport.launchGame(throwing, "game");
        require(failed.resolved && !failed.started,
                "startActivity exception must be (true,false)");

        LaunchResult badArgs = RuntimeValidationSupport.launchGame(
                new TestContext(new TestPackageManager(true)), "  ");
        require(!badArgs.resolved && !badArgs.started,
                "blank package must be (false,false)");
    }

    public static final class TestPackageManager extends PackageManager {
        private final boolean resolvable;
        TestPackageManager(boolean resolvable) { this.resolvable = resolvable; }
        @Override public Intent getLaunchIntentForPackage(String packageName) {
            return resolvable ? new Intent("android.intent.action.MAIN") : null;
        }
    }

    public static final class TestContext extends Context {
        private final TestPackageManager manager;
        boolean failStart;
        TestContext(TestPackageManager manager) { this.manager = manager; }
        @Override public PackageManager getPackageManager() { return manager; }
        @Override public String getPackageName() { return "com.slgtranslator.app"; }
        @Override public void startActivity(Intent intent) {
            if (failStart) throw new IllegalStateException("fixture launch failure");
        }
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="launch-probe-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "LaunchProbeHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(), *map(str, stubs),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "LaunchProbeHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_engine_capability_js_fallback_defaults_can_validate_runtime_false(self):
        """JS capability fallback must default canValidateRuntime false; native scan overrides it."""
        ui_redesign = ROOT / "apk-work" / "ui-redesign"
        sys.path.insert(0, str(ui_redesign))
        from patch_workshop_ui import engine_capability_runtime, terminate_top_level_iife
        runtime = terminate_top_level_iife(engine_capability_runtime)
        contract = r'''
globalThis.window = globalThis;
function check(condition,label){if(!condition)throw new Error(label)}
const patchable = window.resolveEngineCapabilities({compatibilityReport:{supportLevel:'SAFE'}});
check(patchable.canValidateRuntime === false, 'patchable fallback must default canValidateRuntime false');
const extract = window.resolveEngineCapabilities({compatibilityReport:{supportLevel:'EXTRACT_ONLY'}});
check(extract.canValidateRuntime === false, 'extract fallback must default canValidateRuntime false');
const unsupported = window.resolveEngineCapabilities({});
check(unsupported.canValidateRuntime === false, 'unsupported fallback must default canValidateRuntime false');
const suppliedDefault = window.resolveEngineCapabilities({capabilities:{canWritePatch:true,canActivate:true}});
check(suppliedDefault.canValidateRuntime === false, 'supplied caps must default canValidateRuntime false');
const suppliedTrue = window.resolveEngineCapabilities({capabilities:{canWritePatch:true,canActivate:true,canValidateRuntime:true}});
check(suppliedTrue.canValidateRuntime === true, 'native scan must override canValidateRuntime to true');
'''
        result = subprocess.run(
            ["node", "-e", runtime + "\n" + contract],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_renpy_compatibility_report_ui_order_fields_and_sanitized_export(self):
        """The UI must persist fixed diagnostics before either model branch and export only metadata."""
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        for field in (
            "compatibilityReport", "supportLevel", "activationStrategy", "templatePath",
            "rpaCount", "splitCount", "languageBuckets", "menuType", "font",
            "uniqueTextCount", "occurrenceCount", "collisionCount", "issues",
        ):
            self.assertIn(field, source)
        self.assertIn("__slgRenpyCompatibilityReport", source)
        self.assertIn("__slgAccumulateRenpyCompatibility", source)
        self.assertIn("sanitizedJson", source)
        self.assertIn("Ren'Py 兼容性预检", source)
        report_pos = source.index("__slgRenpyCompatibilityReport")
        model_pos = source.index("async function Vo")
        self.assertLess(report_pos, model_pos)
        self.assertNotIn("apiKey", source[source.index("sanitizedJson"):source.index("sanitizedJson") + 1200])
        self.assertNotIn("apkBytes", source[source.index("sanitizedJson"):source.index("sanitizedJson") + 1200])
        self.assertNotIn("fullScript", source[source.index("sanitizedJson"):source.index("sanitizedJson") + 1200])

    def test_renpy_compatibility_runtime_survives_non_callable_existing_renderer(self):
        """A stale or host-provided renderer must not prevent the workshop UI from booting."""
        import json
        import patch_workshop_ui as patcher

        node_script = f"""
const runtime = {json.dumps(patcher.compatibility_report_runtime)};
globalThis.window = globalThis;
globalThis.document = undefined;
Object.defineProperty(globalThis, "__slgRenderRenpyCompatibilityReport", {{
  value: {{}}, writable: false, configurable: false
}});
globalThis.__slgRenpyCompatibilityReport = {{supportLevel: `SAFE`, issues: []}};
eval(runtime);
process.stdout.write("BOOT_OK");
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "BOOT_OK")

    def test_renpy_compatibility_runtime_isolates_diagnostic_render_failure(self):
        """A diagnostic DOM failure must not abort the main workshop runtime."""
        import json
        import patch_workshop_ui as patcher

        node_script = f"""
const runtime = {json.dumps(patcher.compatibility_report_runtime)};
globalThis.window = globalThis;
globalThis.document = {{querySelector: () => {{ throw new TypeError("dom failure"); }}}};
globalThis.__slgRenpyCompatibilityReport = {{supportLevel: `SAFE`, issues: []}};
eval(runtime);
process.stdout.write("BOOT_OK");
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "BOOT_OK")

    def test_scanner_exposes_capabilities_fingerprint_and_stable_record_identity(self):
        scanner = SCANNER.read_text("utf-8")
        for token in (
            'put("adapterId", "renpy")', 'put("workflow"', 'put("capabilities"',
            'put("projectFingerprint"', 'put("recordSchemaVersion", 1)',
            'put("recordId"', 'put("sourceOwner"', 'put("translationGate"',
        ):
            self.assertIn(token, scanner)
        self.assertIn('return "extract_only";', scanner,
                      "legacy compatibilityGate must remain for old frontends")

        harness = r"""
package com.slgtranslator.app;

public final class ScannerIdentityHarness {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        RenpyTextRecord record = new RenpyTextRecord(
                "Hello %s", RenpyTextRecord.Kind.DIALOGUE, "", "line-1",
                "assets/game/script.rpyc", 12, 3, true);
        String first = FastApkScanner.recordId("renpy", "base", record);
        String second = FastApkScanner.recordId("renpy", "base", record);
        String split = FastApkScanner.recordId("renpy", "split:config.arm64_v8a", record);
        require(first.equals(second), "same record input must produce a stable id");
        require(!first.equals(split), "source owner must be part of record identity");
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="scanner-identity-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "ScannerIdentityHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.ScannerIdentityHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_renpy_extract_only_allows_model_and_blocks_writer_boundary(self):
        """EXTRACT_ONLY may extract and translate, but must stop before writer actions."""
        import patch_workshop_ui as patcher
        from test_workshop_patch import extract_js_expression

        base_assets = ROOT / "_trash" / "uncertain" / "extracted" / "assets" / "public" / "assets"
        js, _ = patcher.patch_assets(
            (base_assets / "index-CJtfdHOF.js").read_text("utf-8"),
            (base_assets / "index-C044IUg3.css").read_text("utf-8"),
        )
        ce_expression = extract_js_expression(js, "Ce=async()=>")
        self.assertTrue(ce_expression.startswith("Ce=async()=>"))
        node_script = f"""
globalThis.window=globalThis;
let extractionCalls=0,modelCalls=0,compileCalls=0,buildCalls=0,installCalls=0,exportCalls=0;
let n=`fixture.apk`,ae=[{{fileType:`rpyc`,name:`script.rpyc`}}],te=`api-key`,oe=false,fe=()=>{{}};
let x=`openai`,_e=[{{id:`openai`,baseURL:`https://api.openai.com/v1`}}],re=``,m=null;
let g=`en`,y=`zh`,S=`gpt-test`,ps=20,_mode=`resume`,vo={{}},cacheIndex={{}},_dirty={{}},bo=false;
const ds={{rpyc:`RPYC`}};
function U(value){{return String(value)}}
async function Co(){{}}
async function wo(){{}}
async function runFileTasksParallel(items,fn){{for(let i=0;i<items.length;i++){{const failure=await fn(items[i],i);if(failure)return failure}}return ``}}
function ke(){{return[{{text:`Hello`,keyPath:`script.rpyc::0`}}]}}
function rpycContentFromRecords(){{return``}}
async function Lo(){{await globalThis.Vo();return{{translations:new Map([[`script.rpyc::0`,`你好`],[`Hello`,`你好`]]),successCount:1}}}}
function ns(){{return true}}
function rs(){{return{{outputPath:`tl/zh/script.rpy`,content:`translated`}}}}
async function Ne(){{}}
function isProviderNetworkFailure(){{return false}}
function O(){{}}
function ce(){{}}
function ue(){{}}
function w(){{}}
let he={{current:[]}};
globalThis.__slgResetTranslationCollisionReport=()=>{{}};
globalThis.__slgResetTranslationCoverage=()=>{{}};
globalThis.__slgRecordTranslationCandidates=()=>{{}};
globalThis.__slgRecordValidatorApprovedTranslations=()=>{{}};
window.__slgSelectionMeta={{source:`file`}};
window.__slgRenpyMenuType=`renpy`;
window.__slgFontPreflightDone=true;
window.__slgRenpyCompatibilityPreflightDone=true;
window.__slgRenpyCompatibilityGate=`extract_only`;
window.__slgRenpyCompatibilityReport={{supportLevel:`EXTRACT_ONLY`,issues:[{{code:`renpy_python2_writer_unavailable`}}]}};
window.__slgEngineCapabilities={{canExtractStructured:true,canTranslate:true,canWritePatch:false,canActivate:false}};
window.__slgRenpyCompatibilityBlocked=true;
window.__slgEngineWorkflow=`TRANSLATABLE_NO_PATCH`;
globalThis.__slgTranslationAwaitingExport=false;
const E={{
  readRenpyTexts:async()=>{{extractionCalls++;return{{renpyRecords:[{{text:`Hello`}}],fontReport:{{missingCodePoints:[],coveredCount:1,requiredCount:1}}}}}},
  compileTranslationsIntoApk:async()=>{{compileCalls++}},
  buildPatchedApk:async()=>{{buildCalls++}},
  installApk:async()=>{{installCalls++}},
  exportTranslationProject:async()=>{{exportCalls++}}
}};
globalThis.Vo=async()=>{{modelCalls++;return new Map([[0,`你好`]])}};
const Ce={ce_expression[3:]};
(async()=>{{
  await Ce();
  if(window.__slgRenpyCompatibilityBlocked)throw new Error(`extract-only+translate must clear the old early-return flag`);
  if(extractionCalls<=0)throw new Error(`extract-only must still extract`);
  if(modelCalls<=0)throw new Error(`extract-only must reach the selected model`);
  if(compileCalls!==0||buildCalls!==0||installCalls!==0)throw new Error(`writer boundary must stop compile, build and install`);
  if(exportCalls!==0)throw new Error(`writer-boundary task must not fabricate an export before project assembly exists`);
}})().catch(error=>{{console.error(error);process.exit(1)}});
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_renpy_unsupported_snapshot_blocks_generated_extract_model_and_build(self):
        """Execute the generated Ce gate with an unsupported report and count downstream calls."""
        import patch_workshop_ui as patcher
        from test_workshop_patch import extract_js_expression

        base_assets = ROOT / "_trash" / "uncertain" / "extracted" / "assets" / "public" / "assets"
        js, _ = patcher.patch_assets(
            (base_assets / "index-CJtfdHOF.js").read_text("utf-8"),
            (base_assets / "index-C044IUg3.css").read_text("utf-8"),
        )
        ce_expression = extract_js_expression(js, "Ce=async()=>")
        self.assertTrue(ce_expression.startswith("Ce=async()=>"))
        node_script = f"""
globalThis.window=globalThis;
        let extractionCalls=0,modelCalls=0,buildCalls=0,ceCalls=0,ceLast=null;
let n=`fixture.apk`,ae=[{{fileType:`rpyc`,name:`script.rpyc`}}],te=`api-key`,oe=false;
function O(){{}};
        function ce(value){{ceCalls++;ceLast=value;}}
globalThis.__slgResetTranslationCollisionReport=()=>{{}};
globalThis.__slgResetTranslationCoverage=()=>{{}};
window.__slgSelectionMeta={{source:`file`}};
window.__slgRenpyMenuType=`renpy`;
window.__slgFontPreflightDone=true;
window.__slgRenpyCompatibilityPreflightDone=false;
window.__slgRenpyCompatibilityGate=`blocked`;
window.__slgRenpyCompatibilityReport={{supportLevel:`UNSUPPORTED`,activationStrategy:`NONE`,issues:[{{code:`renpy_preflight_missing_source`}}]}};
globalThis.__slgRenderRenpyCompatibilityReport=()=>{{}};
const E={{readRenpyTexts:async()=>{{extractionCalls++}},buildPatchedApk:async()=>{{buildCalls++}}}};
const Ce={ce_expression[3:]};
(async()=>{{
  await Ce();
          if(extractionCalls!==0||modelCalls!==0||buildCalls!==0||ceCalls!==1||ceLast!==false){{
    throw new Error(JSON.stringify({{extractionCalls,modelCalls,buildCalls,ceCalls,ceLast}}));
  }}
}})().catch(error=>{{console.error(error);process.exit(1)}});
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_renpy_compatibility_accumulate_uses_all_read_records(self):
        """Two extraction batches must aggregate to 3 unique, 4 occurrences, 1 collision."""
        import patch_workshop_ui as patcher

        node_script = f"""
const runtime={json.dumps(patcher.compatibility_report_runtime)};
globalThis.__slgRenpyCompatibilityReport={{supportLevel:`SAFE`,activationStrategy:`SELECTABLE_LANGUAGE`,templatePath:`assets/x-game/x-script.rpyc`,rpyc:null,rpaCount:0,splitCount:0,languageBuckets:[],menuType:`renpy`,font:null,uniqueTextCount:0,occurrenceCount:0,collisionCount:0,issues:[]}};
eval(runtime);
globalThis.__slgAccumulateRenpyCompatibility([
  {{text:`A`,speaker:`s1`,identifier:`i1`,kind:`DIALOGUE`,sourcePath:`game/one.rpyc`}},
  {{text:`B`,speaker:`s2`,identifier:`i2`,kind:`DIALOGUE`,sourcePath:`game/two.rpyc`}}
]);
globalThis.__slgAccumulateRenpyCompatibility([
  {{text:`A`,speaker:`s3`,identifier:`i3`,kind:`DIALOGUE`,sourcePath:`game/three.rpyc`}},
  {{text:`C`,speaker:`s4`,identifier:`i4`,kind:`DIALOGUE`,sourcePath:`game/four.rpyc`}}
]);
const report=globalThis.__slgRenpyCompatibilityReport;
if(report.uniqueTextCount!==3||report.occurrenceCount!==4||report.collisionCount!==1){{
  throw new Error(JSON.stringify(report));
}}
process.stdout.write(JSON.stringify({{unique:report.uniqueTextCount,occurrences:report.occurrenceCount,collisions:report.collisionCount}}));
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(json.loads(result.stdout), {"unique": 3, "occurrences": 4, "collisions": 1})

    def test_rpa_archive_lists_and_reads_rpyc_entries(self):
        rpa3 = build_rpa3_fixture()
        rpa2 = build_rpa2_fixture()
        rpi, rpa1 = build_rpa1_fixture()
        harness = r"""
import com.slgtranslator.app.RpaArchive;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public final class RpaHarness {
    public static void main(String[] args) throws Exception {
        byte[] rpa3 = Files.readAllBytes(Paths.get(args[0]));
        List<String> names3 = RpaArchive.listEntries(rpa3, "game/archive.rpa");
        require(names3.contains("game/chapter1.rpyc"), "RPA-3 must list rpyc");
        require(!names3.contains("game/notes.txt"), "RPA-3 must not list non-script");
        byte[] content3 = RpaArchive.readEntry(rpa3, "game/archive.rpa", "game/chapter1.rpyc");
        require(RpycTextExtractor.extractTexts(content3).contains("Hello, world!"), "RPA-3 content must extract");
        require(RpaArchive.virtualName("game/archive.rpa", "game/chapter1.rpyc").equals("game/archive.rpa!/game/chapter1.rpyc"), "virtual name");
        String[] split = RpaArchive.splitVirtual("game/archive.rpa!/game/chapter1.rpyc");
        require(split.length == 2 && split[0].equals("game/archive.rpa") && split[1].equals("game/chapter1.rpyc"), "virtual split");

        byte[] rpa2 = Files.readAllBytes(Paths.get(args[1]));
        List<String> names2 = RpaArchive.listEntries(rpa2, "game/archive2.rpa");
        require(names2.contains("game/chapter1.rpyc"), "RPA-2 must list rpyc");
        byte[] content2 = RpaArchive.readEntry(rpa2, "game/archive2.rpa", "game/chapter1.rpyc");
        require(RpycTextExtractor.extractTexts(content2).contains("Hello, world!"), "RPA-2 content must extract");

        byte[] rpi = Files.readAllBytes(Paths.get(args[2]));
        byte[] rpa1 = Files.readAllBytes(Paths.get(args[3]));
        List<String> names1 = RpaArchive.listEntries(rpi, "game/archive1.rpi");
        require(names1.contains("game/chapter1.rpyc"), "RPA-1 must list rpyc");
        byte[] content1 = RpaArchive.readEntry(rpa1, "game/archive1.rpa", "game/chapter1.rpyc", rpi);
        require(RpycTextExtractor.extractTexts(content1).contains("Hello, world!"), "RPA-1 content must extract");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpa-test-") as temporary:
            temporary_path = Path(temporary)
            rpa3_path = temporary_path / "archive3.rpa"
            rpa2_path = temporary_path / "archive2.rpa"
            rpi_path = temporary_path / "archive1.rpi"
            rpa1_path = temporary_path / "archive1.rpa"
            harness_path = temporary_path / "RpaHarness.java"
            classes = temporary_path / "classes"
            rpa3_path.write_bytes(rpa3)
            rpa2_path.write_bytes(rpa2)
            rpi_path.write_bytes(rpi)
            rpa1_path.write_bytes(rpa1)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "RpaHarness", str(rpa3_path), str(rpa2_path), str(rpi_path), str(rpa1_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpa3_writer_rebuilds_list_of_tuples_and_rereads_independently(self):
        """RPA-3 rebuild must preserve untouched bytes and produce a readable index."""
        writer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpaArchiveWriter.java"
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;

public final class RpaWriterHarness {
    public static void main(String[] args) throws Exception {
        byte[] original = Files.readAllBytes(Paths.get(args[0]));
        Map<String, byte[]> replacements = new LinkedHashMap<>();
        replacements.put("game/chapter1.rpyc", "patched-rpyc".getBytes("UTF-8"));
        File output = new File(args[1]);
        File sourceFile = new File(args[0]);
        try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
            RpaArchiveWriter.rebuildSelfIndexed(source, output, replacements, false);
        }
        byte[] rebuilt = Files.readAllBytes(output.toPath());
        if (rebuilt.length <= 34 || !new String(rebuilt, 0, 8, "US-ASCII").equals("RPA-3.0 ")) {
            throw new AssertionError("RPA-3 header missing");
        }
        byte[] patched = RpaArchive.readEntry(rebuilt, "game/archive.rpa", "game/chapter1.rpyc");
        if (!new String(patched, "UTF-8").equals("patched-rpyc")) {
            throw new AssertionError("patched entry was not readable");
        }
        byte[] notes = RpaArchive.readEntry(rebuilt, "game/archive.rpa", "game/notes.txt");
        if (!new String(notes, "UTF-8").equals("ignore")) {
            throw new AssertionError("untouched entry changed");
        }
        if (!java.util.Arrays.equals(original, Files.readAllBytes(sourceFile.toPath()))) {
            throw new AssertionError("source archive was modified");
        }
    }
}
        """
        rpa = build_rpa3_fixture()
        self.assertTrue(writer.exists(), "RpaArchiveWriter.java must be created")
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpa-writer-test-") as temporary:
            temporary_path = Path(temporary)
            source_path = temporary_path / "source.rpa"
            output_path = temporary_path / "rebuilt.rpa"
            source_path.write_bytes(rpa)
            harness_path = temporary_path / "RpaWriterHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.RpaWriterHarness",
                 str(source_path), str(output_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0,
                             run_result.stderr or run_result.stdout)

            rebuilt = output_path.read_bytes()
            self.assertEqual(rebuilt[:8], b"RPA-3.0 ")
            index_offset = int(rebuilt[8:24].decode("ascii"), 16)
            key = int(rebuilt[25:33].decode("ascii"), 16)
            import zlib
            index = pickle.loads(zlib.decompress(rebuilt[index_offset:]))
            self.assertEqual(set(index), {"game/chapter1.rpyc", "game/notes.txt"})
            for value in index.values():
                self.assertIsInstance(value, list)
                self.assertEqual(len(value), 1)
                self.assertIsInstance(value[0], tuple)
                self.assertEqual(len(value[0]), 3)
                self.assertIsInstance(value[0][2], bytes)
                self.assertEqual(value[0][2], b"")
            for name, value in index.items():
                stored_offset, stored_length, _ = value[0]
                decoded_offset = stored_offset ^ key
                decoded_length = stored_length ^ key
                payload = b"patched-rpyc" if name == "game/chapter1.rpyc" else b"ignore"
                self.assertEqual(decoded_length, len(payload))
                self.assertEqual(rebuilt[decoded_offset:decoded_offset + decoded_length], payload)

    def test_rpa_index_dialect_pins_py2_vs_py3(self):
        """RPA index string opcodes are explicit and independently pickle-readable."""
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;

public final class RpaDialectHarness {
    public static void main(String[] args) throws Exception {
        byte[] sourceBytes = Files.readAllBytes(Paths.get(args[0]));
        File sourceFile = new File(args[0]);
        Map<String, byte[]> replacements = new LinkedHashMap<>();
        try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
            RpaArchiveWriter.rebuildSelfIndexed(source, new File(args[1]), replacements, true);
        }
        try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
            RpaArchiveWriter.rebuildSelfIndexed(source, new File(args[2]), replacements, false);
        }
        if (sourceBytes.length == 0) throw new AssertionError("source fixture missing");
    }
}
"""
        rpa = build_rpa3_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpa-dialect-test-") as temporary:
            temporary_path = Path(temporary)
            source_path = temporary_path / "source.rpa"
            py2_path = temporary_path / "py2.rpa"
            py3_path = temporary_path / "py3.rpa"
            harness_path = temporary_path / "RpaDialectHarness.java"
            classes = temporary_path / "classes"
            source_path.write_bytes(rpa)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.RpaDialectHarness",
                 str(source_path), str(py2_path), str(py3_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr or run_result.stdout)

            def read_index(path):
                data = path.read_bytes()
                offset = int(data[8:24].decode("ascii"), 16)
                return data, pickle.loads(zlib.decompress(data[offset:]))

            import zlib
            py2_bytes, py2_index = read_index(py2_path)
            py3_bytes, py3_index = read_index(py3_path)
            self.assertEqual(py2_index.keys(), py3_index.keys())
            self.assertTrue(py2_bytes.startswith(b"RPA-3.0 "))
            self.assertTrue(py3_bytes.startswith(b"RPA-3.0 "))
            self.assertIn(b"\x58", zlib.decompress(py2_bytes[int(py2_bytes[8:24].decode("ascii"), 16):]))
            self.assertNotIn(b"\x8c", zlib.decompress(py2_bytes[int(py2_bytes[8:24].decode("ascii"), 16):]))
            self.assertIn(b"\x8c", zlib.decompress(py3_bytes[int(py3_bytes[8:24].decode("ascii"), 16):]))

    def test_rpa_writer_roundtrip_supports_unsigned_xor_coordinates(self):
        """RPA-3 XOR values above signed int range remain independently readable."""
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.file.Files;
import java.util.LinkedHashMap;

public final class RpaHighCoordinateHarness {
    public static void main(String[] args) throws Exception {
        File sourceFile = new File(args[0]);
        try (RandomAccessFile source = new RandomAccessFile(sourceFile, "r")) {
            RpaArchiveWriter.rebuildSelfIndexed(source, new File(args[1]),
                    new LinkedHashMap<String, byte[]>(), false);
        }
        require(RpaArchive.listEntryLocations(Files.readAllBytes(new File(args[1]).toPath()),
                "archive.rpa").size() == 2, "high-coordinate index must remain readable");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpa = build_rpa3_fixture(key=0xF0F0F0F0)
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpa-high-coordinate-test-") as temporary:
            temporary_path = Path(temporary)
            source_path = temporary_path / "source.rpa"
            output_path = temporary_path / "rebuilt.rpa"
            harness_path = temporary_path / "RpaHighCoordinateHarness.java"
            classes = temporary_path / "classes"
            source_path.write_bytes(rpa)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.RpaHighCoordinateHarness",
                 str(source_path), str(output_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr or run_result.stdout)

            rebuilt = output_path.read_bytes()
            index_offset = int(rebuilt[8:24].decode("ascii"), 16)
            key = int(rebuilt[25:33].decode("ascii"), 16)
            import zlib
            index = pickle.loads(zlib.decompress(rebuilt[index_offset:]))
            expected = {
                "game/chapter1.rpyc": build_menu_fixture_rpyc(),
                "game/notes.txt": b"ignore",
            }
            for name, value in index.items():
                decoded_offset, decoded_length, trailer = value[0]
                self.assertEqual(trailer, b"")
                decoded_offset ^= key
                decoded_length ^= key
                self.assertEqual(decoded_length, len(expected[name]))
                self.assertEqual(rebuilt[decoded_offset:decoded_offset + decoded_length], expected[name])

    def test_rpa_writer_roundtrip_rpa2_and_rpa1(self):
        """RPA-2 and separate RPA-1 index/data pairs rebuild and reread."""
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;

public final class RpaLegacyWriterHarness {
    public static void main(String[] args) throws Exception {
        File rpa2Source = new File(args[0]);
        File rpa2Target = new File(args[1]);
        Map<String, byte[]> replacements = new LinkedHashMap<>();
        replacements.put("game/chapter1.rpyc", "rpa2-patched".getBytes("UTF-8"));
        try (RandomAccessFile source = new RandomAccessFile(rpa2Source, "r")) {
            RpaArchiveWriter.rebuildSelfIndexed(source, rpa2Target, replacements, false);
        }
        require(new String(RpaArchive.readEntry(Files.readAllBytes(rpa2Target.toPath()),
                "game/archive2.rpa", "game/chapter1.rpyc"), "UTF-8").equals("rpa2-patched"),
                "RPA-2 replacement");

        File rpa1Source = new File(args[2]);
        File rpi1Source = new File(args[3]);
        File rpa1Target = new File(args[4]);
        File rpi1Target = new File(args[5]);
        try (RandomAccessFile source = new RandomAccessFile(rpa1Source, "r")) {
            RpaArchiveWriter.rebuildRpa1(source, Files.readAllBytes(rpi1Source.toPath()),
                    rpa1Target, rpi1Target, replacements, true);
        }
        byte[] rebuiltRpa1 = Files.readAllBytes(rpa1Target.toPath());
        byte[] rebuiltRpi1 = Files.readAllBytes(rpi1Target.toPath());
        require(new String(RpaArchive.readEntry(rebuiltRpa1, "game/archive1.rpa",
                "game/chapter1.rpyc", rebuiltRpi1), "UTF-8").equals("rpa2-patched"),
                "RPA-1 replacement");
        require(new String(RpaArchive.readEntry(rebuiltRpa1, "game/archive1.rpa",
                "game/notes.txt", rebuiltRpi1), "UTF-8").equals("ignore"),
                "RPA-1 untouched entry");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpa2 = build_rpa2_fixture()
        rpi1, rpa1 = build_rpa1_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="rpa-legacy-writer-test-") as temporary:
            temporary_path = Path(temporary)
            paths = [temporary_path / name for name in
                     ("source2.rpa", "rebuilt2.rpa", "source1.rpa", "source1.rpi",
                      "rebuilt1.rpa", "rebuilt1.rpi")]
            paths[0].write_bytes(rpa2)
            paths[2].write_bytes(rpa1)
            paths[3].write_bytes(rpi1)
            harness_path = temporary_path / "RpaLegacyWriterHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.RpaLegacyWriterHarness",
                 *(str(path) for path in paths)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr or run_result.stdout)

    def test_translation_compiler_rebuilds_virtual_rpa_source(self):
        """Always-on source paths inside RPA archives must rebuild the archive entry."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

public final class TranslationCompilerRpaHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File sourceRpa = new File(args[1]);
        File apk = new File(root, "fixture.apk");
        File generated = new File(root, "generated.rpy");
        File storeDirectory = new File(root, "pending");
        generated.getParentFile().mkdirs();
        Files.write(generated.toPath(),
                "# Source: assets/game/archive.rpa!/game/chapter1.rpyc\n"
                        .getBytes("UTF-8"));
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            out.putNextEntry(new ZipEntry("assets/game/archive.rpa"));
            try (FileInputStream in = new FileInputStream(sourceRpa)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            }
            out.closeEntry();
        }

        Class<?> unitClass = Class.forName("com.slgtranslator.app.TranslationCompiler$TranslationUnit");
        Constructor<?> unitConstructor = unitClass.getDeclaredConstructor(File.class, List.class);
        unitConstructor.setAccessible(true);
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"Hello, world!", "你好世界"});
        Object unit = unitConstructor.newInstance(generated, pairs);
        List<Object> units = new ArrayList<>();
        units.add(unit);
        List<String[]> pending = new ArrayList<>();
        PendingApkEntryStore store = new PendingApkEntryStore(storeDirectory);
        try {
            Method append = TranslationCompiler.class.getDeclaredMethod(
                    "appendAlwaysOnDialogueEntries", File.class, List.class, List.class,
                    PendingApkEntryStore.class, boolean.class,
                    TranslationCompiler.DialogueRewriteStats.class);
            append.setAccessible(true);
            append.invoke(null, apk, units, pending, store, false, null);
            require(pending.size() == 1, "RPA rebuild must register one archive replacement");
            require("assets/game/archive.rpa".equals(pending.get(0)[0]), "archive replacement path");
            require("assets/game/archive.rpa".equals(store.apkName(0)), "stored archive path");

            byte[] rebuilt = readAll(store.openPayload(0));
            byte[] patched = RpaArchive.readEntry(rebuilt, "archive.rpa", "game/chapter1.rpyc");
            require(RpycTextExtractor.extractTexts(patched).contains("你好世界"),
                    "rebuilt archive must contain translated RPYC");
            byte[] notes = RpaArchive.readEntry(rebuilt, "archive.rpa", "game/notes.txt");
            require("ignore".equals(new String(notes, "UTF-8")), "untouched archive entry preserved");
            require(new ZipFile(apk).getEntry("assets/game/archive.rpa") != null,
                    "source APK archive must remain present");
        } finally {
            store.close();
        }
    }

    private static byte[] readAll(java.io.InputStream in) throws Exception {
        try (java.io.InputStream input = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) out.write(buffer, 0, count);
            return out.toByteArray();
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpa = build_rpa3_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-rpa-test-") as temporary:
            temporary_path = Path(temporary)
            rpa_path = temporary_path / "source.rpa"
            harness_path = temporary_path / "TranslationCompilerRpaHarness.java"
            classes = temporary_path / "classes"
            rpa_path.write_bytes(rpa)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(
                "package android.graphics; public class Typeface { public static Typeface createFromFile(String p) { return new Typeface(); } }",
                "utf-8")
            (graphics_dir / "Paint.java").write_text(
                "package android.graphics; public class Paint { public Typeface setTypeface(Typeface v) { return v; } public boolean hasGlyph(String v) { return v != null; } }",
                "utf-8")
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), str(graphics_dir / "Typeface.java"), str(graphics_dir / "Paint.java"),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.TranslationCompilerRpaHarness",
                 str(temporary_path), str(rpa_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr or run_result.stdout)

    def test_translation_compiler_exports_independent_rpa_mod(self):
        """RPA mod export exposes the requested public reflection contract."""
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

public final class TranslationCompilerRpaModExportHarness {
    public static void main(String[] args) throws Exception {
        File apk = new File(args[0]);
        File output = new File(args[1]);
        File generated = new File(output.getParentFile(), "generated.rpy");
        Files.write(generated.toPath(),
                "# Source: assets/game/archive.rpa!/game/chapter1.rpyc\n".getBytes("UTF-8"));

        Class<?> compiler = Class.forName("com.slgtranslator.app.TranslationCompiler");
        Method export = compiler.getMethod("exportRpaMod", File.class, List.class,
                File.class, boolean.class);
        Class<?> unitClass = Class.forName(
                "com.slgtranslator.app.TranslationCompiler$TranslationUnit");
        Constructor<?> unitConstructor = unitClass.getDeclaredConstructor(File.class, List.class);
        unitConstructor.setAccessible(true);
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"Hello, world!", "你好世界"});
        List<Object> units = new ArrayList<>();
        units.add(unitConstructor.newInstance(generated, pairs));
        byte[] sourceBytes = Files.readAllBytes(apk.toPath());
        export.invoke(null, apk, units, output, false);
        File exported = new File(output, "assets/game/archive.rpa");
        require(exported.isFile(), "export must preserve the APK relative archive path");
        byte[] rebuilt = Files.readAllBytes(exported.toPath());
        byte[] patched = RpaArchive.readEntry(rebuilt, "archive.rpa", "game/chapter1.rpyc");
        require(RpycTextExtractor.extractTexts(patched).contains("你好世界"),
                "exported archive must be independently readable");
        byte[] notes = RpaArchive.readEntry(rebuilt, "archive.rpa", "game/notes.txt");
        require("ignore".equals(new String(notes, "UTF-8")),
                "untouched archive entry must remain unchanged");
        require(java.util.Arrays.equals(sourceBytes, Files.readAllBytes(apk.toPath())),
                "source APK must remain byte-identical");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpa = build_rpa3_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-rpa-mod-red-") as temporary:
            temporary_path = Path(temporary)
            apk_path = temporary_path / "fixture.apk"
            output_path = temporary_path / "mod"
            harness_path = temporary_path / "TranslationCompilerRpaModExportHarness.java"
            classes = temporary_path / "classes"
            with zipfile.ZipFile(apk_path, "w") as archive:
                archive.writestr("assets/game/archive.rpa", rpa)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(
                "package android.graphics; public class Typeface { public static Typeface createFromFile(String p) { return new Typeface(); } }",
                "utf-8")
            (graphics_dir / "Paint.java").write_text(
                "package android.graphics; public class Paint { public Typeface setTypeface(Typeface v) { return v; } public boolean hasGlyph(String v) { return v != null; } }",
                "utf-8")
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), str(graphics_dir / "Typeface.java"),
                 str(graphics_dir / "Paint.java"),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerRpaModExportHarness",
                 str(apk_path), str(output_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0,
                             run_result.stderr or run_result.stdout)

    def test_translation_compiler_exports_directory_rpa_matrix(self):
        """Directory exports cover RPA-1 companions and empty replacement cleanup."""
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class TranslationCompilerRpaDirectoryExportHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File sourceRpa = new File(args[1]);
        File sourceRpi = new File(args[2]);
        File sourceDir = new File(root, "source-dir");
        File archive = new File(sourceDir, "assets/game/archive.rpa");
        File rpi = new File(sourceDir, "assets/game/archive.rpi");
        require(archive.getParentFile().mkdirs(), "create source archive directory");
        Files.copy(sourceRpa.toPath(), archive.toPath());
        Files.copy(sourceRpi.toPath(), rpi.toPath());
        byte[] sourceArchiveBytes = Files.readAllBytes(archive.toPath());
        byte[] sourceRpiBytes = Files.readAllBytes(rpi.toPath());

        Class<?> unitClass = Class.forName(
                "com.slgtranslator.app.TranslationCompiler$TranslationUnit");
        Constructor<?> unitConstructor = unitClass.getDeclaredConstructor(File.class, List.class);
        unitConstructor.setAccessible(true);
        Method export = TranslationCompiler.class.getMethod("exportRpaMod", File.class,
                List.class, File.class, boolean.class);

        File translated = new File(root, "translated.rpy");
        Files.write(translated.toPath(),
                "# Source: assets/game/archive.rpa!/game/chapter1.rpyc\n".getBytes("UTF-8"));
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"Hello, world!", "目录翻译"});
        List<Object> translatedUnits = new ArrayList<>();
        translatedUnits.add(unitConstructor.newInstance(translated, pairs));
        File output = new File(root, "mod");
        export.invoke(null, sourceDir, translatedUnits, output, false);
        File exportedRpa = new File(output, "assets/game/archive.rpa");
        File exportedRpi = new File(output, "assets/game/archive.rpi");
        require(exportedRpa.isFile(), "directory export must produce RPA");
        require(exportedRpi.isFile(), "directory RPA-1 export must produce RPI");
        byte[] rebuiltRpa = Files.readAllBytes(exportedRpa.toPath());
        byte[] rebuiltRpi = Files.readAllBytes(exportedRpi.toPath());
        byte[] patched = RpaArchive.readEntry(rebuiltRpa, "archive.rpa",
                "game/chapter1.rpyc", rebuiltRpi);
        require(RpycTextExtractor.extractTexts(patched).contains("目录翻译"),
                "directory RPA-1 export must be independently readable");
        require("ignore".equals(new String(RpaArchive.readEntry(rebuiltRpa, "archive.rpa",
                "game/notes.txt", rebuiltRpi), "UTF-8")),
                "directory RPA-1 notes must remain unchanged");
        require(Arrays.equals(sourceArchiveBytes, Files.readAllBytes(archive.toPath())),
                "directory RPA source must remain unchanged");
        require(Arrays.equals(sourceRpiBytes, Files.readAllBytes(rpi.toPath())),
                "directory RPI source must remain unchanged");

        File emptyOutput = new File(root, "empty-mod");
        List<Object> emptyUnits = new ArrayList<>();
        emptyUnits.add(unitConstructor.newInstance(translated, new ArrayList<String[]>()));
        export.invoke(null, sourceDir, emptyUnits, emptyOutput, false);
        require(!new File(emptyOutput, "assets/game/archive.rpa").exists(),
                "empty export must not produce RPA");
        require(!new File(emptyOutput, "assets/game/archive.rpi").exists(),
                "empty export must not produce RPI");
        require(!new File(emptyOutput, ".rpa-export-work").exists(),
                "empty export must clean its work directory");
        require(!new File(output, ".rpa-export-work").exists(),
                "successful export must clean its work directory");

        // A later target failure must not leave an earlier archive committed.
        File secondArchive = new File(sourceDir, "assets/game/archive2.rpa");
        File secondRpi = new File(sourceDir, "assets/game/archive2.rpi");
        Files.copy(sourceRpa.toPath(), secondArchive.toPath());
        Files.copy(sourceRpi.toPath(), secondRpi.toPath());
        File translatedSecond = new File(root, "translated-second.rpy");
        Files.write(translatedSecond.toPath(),
                "# Source: assets/game/archive2.rpa!/game/chapter1.rpyc\n".getBytes("UTF-8"));
        List<Object> partialUnits = new ArrayList<>();
        partialUnits.add(unitConstructor.newInstance(translated, pairs));
        partialUnits.add(unitConstructor.newInstance(translatedSecond, pairs));
        File partialOutput = new File(root, "partial-mod");
        File blockedTarget = new File(partialOutput, "assets/game/archive2.rpa");
        require(blockedTarget.mkdirs(), "create blocked output target");
        boolean partialFailed = false;
        try {
            export.invoke(null, sourceDir, partialUnits, partialOutput, false);
        } catch (java.lang.reflect.InvocationTargetException error) {
            partialFailed = error.getCause() instanceof java.io.IOException;
        }
        require(partialFailed, "export must report a later target failure");
        require(!new File(partialOutput, "assets/game/archive.rpa").exists(),
                "failed export must roll back earlier archive output");
        require(blockedTarget.isDirectory(), "blocked target must remain untouched");
        require(!new File(partialOutput, ".rpa-export-work").exists(),
                "failed export must clean its work directory");

        // A pre-existing workspace symlink must be rejected before writing outside outputDir.
        File symlinkOutput = new File(root, "symlink-mod");
        File symlinkOutside = new File(root, "symlink-outside");
        require(symlinkOutput.mkdirs(), "create symlink output directory");
        require(symlinkOutside.mkdirs(), "create symlink outside directory");
        File workspaceLink = new File(symlinkOutput, ".rpa-export-work");
        boolean symlinkCreated = false;
        try {
            Files.createSymbolicLink(workspaceLink.toPath(), symlinkOutside.toPath());
            symlinkCreated = true;
        } catch (UnsupportedOperationException | SecurityException | java.io.IOException ignored) {
            System.out.println("SYMLINK_TEST_SKIPPED");
        }
        if (symlinkCreated) {
            boolean symlinkRejected = false;
            try {
                export.invoke(null, sourceDir, translatedUnits, symlinkOutput, false);
            } catch (java.lang.reflect.InvocationTargetException error) {
                symlinkRejected = error.getCause() instanceof java.io.IOException;
            }
            require(symlinkRejected, "export must reject a workspace symlink");
            require(Files.isSymbolicLink(workspaceLink.toPath()),
                    "rejected workspace symlink must remain untouched");
            require(symlinkOutside.listFiles() == null || symlinkOutside.listFiles().length == 0,
                    "workspace symlink target must remain empty");
            Files.deleteIfExists(workspaceLink.toPath());
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpi, rpa = build_rpa1_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-rpa-dir-red-") as temporary:
            temporary_path = Path(temporary)
            rpa_path = temporary_path / "source.rpa"
            rpi_path = temporary_path / "source.rpi"
            harness_path = temporary_path / "TranslationCompilerRpaDirectoryExportHarness.java"
            classes = temporary_path / "classes"
            rpa_path.write_bytes(rpa)
            rpi_path.write_bytes(rpi)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(
                "package android.graphics; public class Typeface { public static Typeface createFromFile(String p) { return new Typeface(); } }",
                "utf-8")
            (graphics_dir / "Paint.java").write_text(
                "package android.graphics; public class Paint { public Typeface setTypeface(Typeface v) { return v; } public boolean hasGlyph(String v) { return v != null; } }",
                "utf-8")
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), str(graphics_dir / "Typeface.java"),
                 str(graphics_dir / "Paint.java"),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationCompilerRpaDirectoryExportHarness",
                 str(temporary_path), str(rpa_path), str(rpi_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0,
                             run_result.stderr or run_result.stdout)

    def test_translation_compiler_rebuilds_multiple_virtual_entries_once_per_archive(self):
        """Multiple translated scripts in one RPA share one rebuilt APK entry."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class TranslationCompilerMultiRpaHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File sourceRpa = new File(args[1]);
        File apk = new File(root, "fixture.apk");
        File generatedOne = new File(root, "one.rpy");
        File generatedTwo = new File(root, "two.rpy");
        File storeDirectory = new File(root, "pending");
        Files.write(generatedOne.toPath(),
                "# Source: assets/game/archive.rpa!/game/chapter1.rpyc\n".getBytes("UTF-8"));
        Files.write(generatedTwo.toPath(),
                "# Source: assets/game/archive.rpa!/game/chapter2.rpyc\n".getBytes("UTF-8"));
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            out.putNextEntry(new ZipEntry("assets/game/archive.rpa"));
            try (FileInputStream in = new FileInputStream(sourceRpa)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            }
            out.closeEntry();
        }

        Class<?> unitClass = Class.forName("com.slgtranslator.app.TranslationCompiler$TranslationUnit");
        Constructor<?> unitConstructor = unitClass.getDeclaredConstructor(File.class, List.class);
        unitConstructor.setAccessible(true);
        List<String[]> pairsOne = new ArrayList<>();
        pairsOne.add(new String[]{"Hello, world!", "你好世界"});
        List<String[]> pairsTwo = new ArrayList<>();
        pairsTwo.add(new String[]{"Hello, world!", "第二句"});
        List<Object> units = new ArrayList<>();
        units.add(unitConstructor.newInstance(generatedOne, pairsOne));
        units.add(unitConstructor.newInstance(generatedTwo, pairsTwo));
        List<String[]> pending = new ArrayList<>();
        PendingApkEntryStore store = new PendingApkEntryStore(storeDirectory);
        try {
            Method append = TranslationCompiler.class.getDeclaredMethod(
                    "appendAlwaysOnDialogueEntries", File.class, List.class, List.class,
                    PendingApkEntryStore.class, boolean.class,
                    TranslationCompiler.DialogueRewriteStats.class);
            append.setAccessible(true);
            append.invoke(null, apk, units, pending, store, false, null);
            require(pending.size() == 1, "one archive must register one replacement");
            require(store.size() == 1, "one archive payload must be stored once");
            byte[] rebuilt = readAll(store.openPayload(0));
            byte[] first = RpaArchive.readEntry(rebuilt, "archive.rpa", "game/chapter1.rpyc");
            byte[] second = RpaArchive.readEntry(rebuilt, "archive.rpa", "game/chapter2.rpyc");
            require(RpycTextExtractor.extractTexts(first).contains("你好世界"),
                    "first virtual entry must be rewritten");
            require(RpycTextExtractor.extractTexts(second).contains("第二句"),
                    "second virtual entry must be rewritten");
        } finally {
            store.close();
        }
    }

    private static byte[] readAll(java.io.InputStream in) throws Exception {
        try (java.io.InputStream input = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) out.write(buffer, 0, count);
            return out.toByteArray();
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpa = build_rpa3_fixture(entries=(
            ("game/chapter1.rpyc", build_menu_fixture_rpyc()),
            ("game/chapter2.rpyc", build_menu_fixture_rpyc()),
            ("game/notes.txt", b"ignore"),
        ))
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-multi-rpa-test-") as temporary:
            temporary_path = Path(temporary)
            source_path = temporary_path / "source.rpa"
            harness_path = temporary_path / "TranslationCompilerMultiRpaHarness.java"
            classes = temporary_path / "classes"
            source_path.write_bytes(rpa)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(
                "package android.graphics; public class Typeface { public static Typeface createFromFile(String p) { return new Typeface(); } }",
                "utf-8")
            (graphics_dir / "Paint.java").write_text(
                "package android.graphics; public class Paint { public Typeface setTypeface(Typeface v) { return v; } public boolean hasGlyph(String v) { return v != null; } }",
                "utf-8")
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), str(graphics_dir / "Typeface.java"), str(graphics_dir / "Paint.java"),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.TranslationCompilerMultiRpaHarness",
                 str(temporary_path), str(source_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr or run_result.stdout)

    def test_translation_compiler_rebuilds_rpa1_companion_pair(self):
        """RPA-1 compilation replaces both the data archive and its .rpi index."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class TranslationCompilerRpa1Harness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File sourceRpa = new File(args[1]);
        File sourceRpi = new File(args[2]);
        File apk = new File(root, "fixture.apk");
        File generated = new File(root, "generated.rpy");
        File storeDirectory = new File(root, "pending");
        Files.write(generated.toPath(),
                "# Source: assets/game/archive.rpa!/game/chapter1.rpyc\n".getBytes("UTF-8"));
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            copy(out, "assets/game/archive.rpa", sourceRpa);
            copy(out, "assets/game/archive.rpi", sourceRpi);
        }

        Class<?> unitClass = Class.forName("com.slgtranslator.app.TranslationCompiler$TranslationUnit");
        Constructor<?> unitConstructor = unitClass.getDeclaredConstructor(File.class, List.class);
        unitConstructor.setAccessible(true);
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"Hello, world!", "你好世界"});
        List<Object> units = new ArrayList<>();
        units.add(unitConstructor.newInstance(generated, pairs));
        List<String[]> pending = new ArrayList<>();
        PendingApkEntryStore store = new PendingApkEntryStore(storeDirectory);
        try {
            Method append = TranslationCompiler.class.getDeclaredMethod(
                    "appendAlwaysOnDialogueEntries", File.class, List.class, List.class,
                    PendingApkEntryStore.class, boolean.class,
                    TranslationCompiler.DialogueRewriteStats.class);
            append.setAccessible(true);
            append.invoke(null, apk, units, pending, store, false, null);
            require(pending.size() == 2, "RPA-1 must register data and index replacements");
            int rpaIndex = find(store, "assets/game/archive.rpa");
            int rpiIndex = find(store, "assets/game/archive.rpi");
            byte[] rebuiltRpa = readAll(store.openPayload(rpaIndex));
            byte[] rebuiltRpi = readAll(store.openPayload(rpiIndex));
            byte[] patched = RpaArchive.readEntry(rebuiltRpa, "archive.rpa",
                    "game/chapter1.rpyc", rebuiltRpi);
            require(RpycTextExtractor.extractTexts(patched).contains("你好世界"),
                    "RPA-1 data archive must contain translated RPYC");
            require("ignore".equals(new String(RpaArchive.readEntry(rebuiltRpa, "archive.rpa",
                    "game/notes.txt", rebuiltRpi), "UTF-8")),
                    "RPA-1 untouched entry must remain readable");
        } finally {
            store.close();
        }
    }

    private static void copy(ZipOutputStream out, String name, File source) throws Exception {
        out.putNextEntry(new ZipEntry(name));
        try (FileInputStream in = new FileInputStream(source)) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
        }
        out.closeEntry();
    }

    private static int find(PendingApkEntryStore store, String name) throws Exception {
        for (int i = 0; i < store.size(); i++) if (name.equals(store.apkName(i))) return i;
        throw new AssertionError("pending entry missing: " + name);
    }

    private static byte[] readAll(java.io.InputStream in) throws Exception {
        try (java.io.InputStream input = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) out.write(buffer, 0, count);
            return out.toByteArray();
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        rpi, rpa = build_rpa1_fixture()
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-compiler-rpa1-test-") as temporary:
            temporary_path = Path(temporary)
            rpa_path = temporary_path / "source.rpa"
            rpi_path = temporary_path / "source.rpi"
            harness_path = temporary_path / "TranslationCompilerRpa1Harness.java"
            classes = temporary_path / "classes"
            rpa_path.write_bytes(rpa)
            rpi_path.write_bytes(rpi)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            graphics_dir = temporary_path / "android" / "graphics"
            graphics_dir.mkdir(parents=True)
            (graphics_dir / "Typeface.java").write_text(
                "package android.graphics; public class Typeface { public static Typeface createFromFile(String p) { return new Typeface(); } }",
                "utf-8")
            (graphics_dir / "Paint.java").write_text(
                "package android.graphics; public class Paint { public Typeface setTypeface(Typeface v) { return v; } public boolean hasGlyph(String v) { return v != null; } }",
                "utf-8")
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), str(graphics_dir / "Typeface.java"), str(graphics_dir / "Paint.java"),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))), str(harness_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.TranslationCompilerRpa1Harness",
                 str(temporary_path), str(rpa_path), str(rpi_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr or run_result.stdout)

    def test_legacy_zlib_rpyc_falls_back_to_slot_one(self):
        fixture = build_legacy_rpyc_fixture()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public final class LegacyRpycHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        require(texts.contains("Hello, world!"), "legacy rpyc dialogue must extract");
        require(texts.contains("First choice"), "legacy rpyc menu label must extract");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="legacy-rpyc-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "legacy.rpyc"
            harness_path = temporary_path / "LegacyRpycHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "LegacyRpycHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_local_translation_exposes_idle_release_path_for_all_engines(self):
        mlkit_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                        / "MlKitTranslator.java").read_text("utf-8")
        llm_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                      / "LocalLlmEngine.java").read_text("utf-8")
        support_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                          / "LocalTranslationSupport.java").read_text("utf-8")
        builder = BUILDER.read_text("utf-8")
        self.assertIn("public static void releaseSharedTranslator()", mlkit_source)
        self.assertIn("public static void releaseLoadedModelForIdle()", llm_source)
        self.assertIn("public static void releaseLocalResources(Context context, PluginCall call)", support_source)
        translate_method = support_source.split(
            "public static void translateLocal(Context context, PluginCall call)", 1
        )[1].split("public static void releaseLocalResources", 1)[0]
        self.assertNotIn(
            "} finally {",
            translate_method,
            "the native bridge must keep the translator alive across WebView batches",
        )
        self.assertIn("releaseLocalResources(context, null)", translate_method)
        self.assertIn("releaseLocalResources", builder)

    def test_local_translation_release_path_is_bridge_safe(self):
        support_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                          / "LocalTranslationSupport.java").read_text("utf-8")
        self.assertIn("if (call != null)", support_source)
        self.assertIn("MlKitTranslator.releaseSharedTranslator()", support_source)
        self.assertIn("LocalLlmEngine.releaseLoadedModelForIdle()", support_source)

    def test_local_translation_release_bridge_is_added_to_file_manager(self):
        builder = BUILDER.read_text("utf-8")
        self.assertIn("localRelease", builder)
        self.assertIn("LocalTranslationSupport;->releaseLocalResources", builder)

    def test_local_translation_ensure_unique_key_paths(self):
        """Future `LocalTranslationSupport.ensureUniqueKeyPaths` helper.

        The Ren'Py record path (FastApkScanner.renpyRecordJson) emits records
        with a ``recordId`` but no ``keyPath``.  Downstream consumers that key
        translations by ``keyPath`` collapse every empty path onto one entry,
        so this helper must re-key records with non-empty, unique key paths
        while preserving already-distinct ones.  This harness references the
        not-yet-existing helper, so it is expected to FAIL (RED) at compile
        time until the helper is implemented.
        """
        harness = r"""
package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class EnsureUniqueKeyPathHarness {
    public static void main(String[] args) {
        List<LocalTranslationSupport.TextItem> items = new ArrayList<>();
        items.add(new LocalTranslationSupport.TextItem("", "A"));
        items.add(new LocalTranslationSupport.TextItem("", "B"));
        items.add(new LocalTranslationSupport.TextItem("keep/me", "C"));
        items.add(new LocalTranslationSupport.TextItem("keep/me", "D"));

        List<LocalTranslationSupport.TextItem> result =
                LocalTranslationSupport.ensureUniqueKeyPaths(items);

        require(result.size() == items.size(), "every input item must be preserved");

        Set<String> seen = new HashSet<>();
        for (LocalTranslationSupport.TextItem item : result) {
            require(item.keyPath != null && item.keyPath.length() > 0,
                    "key path must be non-empty: " + item.text);
            require(seen.add(item.keyPath),
                    "key path must be unique (duplicate: " + item.keyPath + ")");
            require(item.text != null && item.text.length() > 0,
                    "text must be preserved: " + item.keyPath);
        }

        // Distinct existing keys must be preserved verbatim.
        boolean keptDistinct = false;
        for (LocalTranslationSupport.TextItem item : result) {
            if ("C".equals(item.text)) {
                keptDistinct = "keep/me".equals(item.keyPath);
            }
        }
        require(keptDistinct, "a distinct key path must be preserved unchanged");

        System.out.println("OK " + result.size());
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="ensure-unique-key-path-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "EnsureUniqueKeyPathHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes),
                 "-classpath", third_party_classpath(),
                 *map(str, stubs),
                 *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(
                compile_result.returncode, 0,
                "LocalTranslationSupport.ensureUniqueKeyPaths must exist and compile: "
                + (compile_result.stderr or "")[-3000:],
            )
            run_result = subprocess.run(
                [str(JAVA), "-cp", os.pathsep.join([str(classes), third_party_classpath()]),
                 "com.slgtranslator.app.EnsureUniqueKeyPathHarness"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stdout + run_result.stderr)
            self.assertIn("OK 4", run_result.stdout)

    def test_local_llm_placeholder_guard_preserves_markup_and_format(self):
        mlkit_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                        / "MlKitTranslator.java").read_text("utf-8")
        self.assertIn("LocalLlmEngine.protectPlaceholders", mlkit_source,
                      "ML Kit must protect Ren'Py placeholders before translation")
        self.assertIn("LocalLlmEngine.restorePlaceholders", mlkit_source,
                      "ML Kit must restore Ren'Py placeholders before validation")
        harness = r"""
import com.slgtranslator.app.LocalLlmEngine;
import com.slgtranslator.app.RenpyTextValidator;

public final class PlaceholderHarness {
    public static void main(String[] args) {
        String original = "{b}Hello{/b} [name]! Score: %s / %1$d";
        LocalLlmEngine.PlaceholderGuard guard = LocalLlmEngine.protectPlaceholders(original);
        String modelOutput = guard.protectedText.replace("Hello", "\u4f60\u597d");
        String restored = LocalLlmEngine.restorePlaceholders(modelOutput, guard);
        String expected = "{b}\u4f60\u597d{/b} [name]! Score: %s / %1$d";
        require(expected.equals(restored), "markup/interpolation must round-trip: " + restored);

        String format = "Score: %s / %d";
        LocalLlmEngine.PlaceholderGuard formatGuard = LocalLlmEngine.protectPlaceholders(format);
        String formatRestored = LocalLlmEngine.restorePlaceholders(formatGuard.protectedText, formatGuard);
        require(format.equals(formatRestored), "format placeholders must round-trip");

        String mangled = formatGuard.protectedText.replace("__SLGPH0__", "");
        require(LocalLlmEngine.restorePlaceholders(mangled, formatGuard) == null, "missing sentinel must reject");
        String extra = formatGuard.protectedText + " __SLGPH2__";
        require(LocalLlmEngine.restorePlaceholders(extra, formatGuard) == null, "extra sentinel must reject");
        String duplicate = formatGuard.protectedText.replace("__SLGPH1__", "__SLGPH0__");
        require(LocalLlmEngine.restorePlaceholders(duplicate, formatGuard) == null, "duplicate sentinel must reject");
        String reordered = "__SLGPH1__ and __SLGPH0__";
        require(LocalLlmEngine.restorePlaceholders(reordered, formatGuard) == null, "reordered sentinel must reject");
        require(LocalLlmEngine.restorePlaceholders("bad __SLGPH0__", new LocalLlmEngine.PlaceholderGuard("bad", new String[0])) == null,
                "unrestored sentinel must reject");
        String replacementChars = "{tag=$1\\\\x} and %s";
        LocalLlmEngine.PlaceholderGuard replacementGuard = LocalLlmEngine.protectPlaceholders(replacementChars);
        require(replacementChars.equals(LocalLlmEngine.restorePlaceholders(replacementGuard.protectedText, replacementGuard)),
                "placeholder replacement characters must round-trip");

        require(RenpyTextValidator.validate(original, expected).valid, "valid Ren'Py text must pass");
        require(RenpyTextValidator.validate("{b}{i}x{/b}{/i}", "{b}{i}x{/b}{/i}").valid,
                "faithful reproduction of source misnesting must pass (source-game markup)");
        require(RenpyTextValidator.validate("{b}x{/b}", "{b}{i}x{/b}{/i}").codes.contains("tag_misnested"),
                "crossed markup must be diagnosed");
        require(RenpyTextValidator.validate("Hello [name]", "Hello [other]").codes.contains("interpolation_changed"),
                "changed interpolation must be diagnosed");
        require(RenpyTextValidator.validate("Score %s", "Score %d").codes.contains("printf_changed"),
                "changed printf must be diagnosed");
        require(RenpyTextValidator.validate("__SLGPH0__ __SLGPH1__", "__SLGPH0__").codes.contains("sentinel_missing"),
                "missing validator sentinel must be diagnosed");
        require(RenpyTextValidator.validate("__SLGPH0__ __SLGPH1__", "__SLGPH0__ __SLGPH2__").codes.contains("sentinel_extra"),
                "extra validator sentinel must be diagnosed");
        require(RenpyTextValidator.validate("__SLGPH0__ __SLGPH1__", "__SLGPH1__ __SLGPH0__").codes.contains("sentinel_reordered"),
                "reordered validator sentinel must be diagnosed");
        require(RenpyTextValidator.validate("Hello", "Hello __SLGPH0__").codes.contains("unrestored_sentinel"),
                "unrestored validator sentinel must be diagnosed");
        require(RenpyTextValidator.validate("{font=DejaVuSans.ttf}x{/font}", "{font=DejaVuSans.ttf}中{/font}").valid,
                "font markup must round-trip");
        require(RenpyTextValidator.validate("{b}x{/b}", "{b}x").codes.contains("tag_unbalanced"),
                "unbalanced markup must be diagnosed");
        require(RenpyTextValidator.validate("Hello", "").codes.contains("empty_translation"),
                "empty translation must be diagnosed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="placeholder-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "PlaceholderHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", os.pathsep.join([str(classes), third_party_classpath()]), "PlaceholderHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_mlkit_translates_placeholder_fragments_and_retries_normalized_text(self):
        mlkit_source = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                        / "MlKitTranslator.java").read_text("utf-8")
        self.assertIn("translateProtectedText", mlkit_source,
                      "ML Kit must translate ordinary fragments without sending placeholder sentinels")
        self.assertIn("normalizeForMlKit", mlkit_source,
                      "ML Kit must retry text with repeated punctuation in a normalized form")
        self.assertIn("isNonTranslatableProtectedText", mlkit_source,
                      "ML Kit must accept unchanged numbers and punctuation as safe source text")
        harness = r"""
package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.List;

public final class MlKitFragmentHarness {
    public static void main(String[] args) throws Exception {
        final List<String> requests = new ArrayList<>();
        LocalLlmEngine.PlaceholderGuard guard = LocalLlmEngine.protectPlaceholders(
                "(Behind you, [mc]!)");
        String protectedResult = MlKitTranslator.translateProtectedText(
                guard.protectedText,
                new MlKitTranslator.SegmentTranslator() {
                    @Override
                    public String translate(String text) {
                        requests.add(text);
                        if (text.equals("(Behind you,")) {
                            return "(在你身后，";
                        }
                        return text;
                    }
                });
        require(!requests.stream().anyMatch(value -> value.contains("__SLGPH")),
                "placeholder sentinels must never be sent to ML Kit: " + requests);
        String restored = LocalLlmEngine.restorePlaceholders(protectedResult, guard);
        require("(在你身后， [mc]!)".equals(restored),
                "placeholder must be restored after fragment translation: " + restored);

        final List<String> retryRequests = new ArrayList<>();
        String wait = "Wait... Your face looks familiar.";
        String waitResult = MlKitTranslator.translateProtectedText(
                LocalLlmEngine.protectPlaceholders(wait).protectedText,
                new MlKitTranslator.SegmentTranslator() {
                    @Override
                    public String translate(String text) {
                        retryRequests.add(text);
                        if (text.equals("Wait... Your face looks familiar.")) {
                            return text;
                        }
                        if (text.equals("Wait. Your face looks familiar.")) {
                            return "等等。你的脸看起来很熟悉。";
                        }
                        return text;
                    }
                });
        require(retryRequests.size() == 2, "ellipsis text must be retried once: " + retryRequests);
        require("Wait. Your face looks familiar.".equals(retryRequests.get(1)),
                "retry must normalize repeated dots: " + retryRequests);
        require("等等。你的脸看起来很熟悉。".equals(waitResult),
                "normalized retry result must be returned: " + waitResult);

        String digits = MlKitTranslator.translateProtectedText("60", text -> {
            throw new AssertionError("digits must not invoke ML Kit");
        });
        require("60".equals(digits), "digits must remain safe unchanged text");
        require(MlKitTranslator.isNonTranslatableProtectedText("60"),
                "digits must be classified as non-translatable protected text");

        LocalLlmEngine.PlaceholderGuard onlyPlaceholder =
                LocalLlmEngine.protectPlaceholders("[mc]{p=2}{nw}");
        String onlyPlaceholderResult = MlKitTranslator.translateProtectedText(
                onlyPlaceholder.protectedText, text -> {
                    throw new AssertionError("placeholder-only text must not invoke ML Kit");
                });
        require(onlyPlaceholder.protectedText.equals(onlyPlaceholderResult),
                "placeholder-only text must preserve sentinels");
        require(MlKitTranslator.isNonTranslatableProtectedText(onlyPlaceholder.protectedText),
                "placeholder-only text must be classified as non-translatable");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="mlkit-fragment-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "MlKitFragmentHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", os.pathsep.join([str(classes), third_party_classpath()]),
                 "com.slgtranslator.app.MlKitFragmentHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_fast_scanner_wires_rpa_virtual_entries(self):
        scanner = SCANNER.read_text("utf-8")
        self.assertIn("RpaArchive.listEntries", scanner)
        self.assertIn("RpaArchive.readEntry", scanner)
        self.assertIn("\"!/\"", scanner)

    def test_language_menu_injects_underscore_labels_after_language_action(self):
        fixture = build_underscore_menu_fixture_rpyc()
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;

public final class UnderscoreMenuHarness {
    public static void main(String[] args) throws Exception {
        byte[] input = Files.readAllBytes(Paths.get(args[0]));
        byte[] output = LanguageMenuSupport.injectMenu(input, "schinese", "slgtranslated");
        if (output == null) {
            throw new AssertionError("injectMenu returned null for _() language buttons");
        }
        if (!LanguageMenuSupport.menuHasLanguage(output, "slgtranslated")) {
            throw new AssertionError("slgtranslated language entry was not written");
        }
        Files.write(Paths.get(args[1]), output);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        import zlib
        with tempfile.TemporaryDirectory(prefix="underscore-menu-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            output_path = temporary_path / "injected.rpyc"
            harness_path = temporary_path / "UnderscoreMenuHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.UnderscoreMenuHarness",
                 str(fixture_path), str(output_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            data = output_path.read_bytes()
            pos = len(RPC2_MAGIC)
            texts = b""
            while pos + 12 <= len(data):
                sid, off, ln = struct.unpack_from("<III", data, pos)
                if sid == 0:
                    break
                texts += zlib.decompress(data[off:off + ln])
                pos += 12
            self.assertIn(b'Language("slgtranslated")', texts)
            self.assertIn('_("翻译文本")'.encode("utf-8"), texts)
            self.assertIn(b'Language("TraditionalChinese")', texts)
            self.assertIn('_("繁體中文")'.encode("utf-8"), texts)
            for slot_id, offset, length in rpc2_slots(data):
                payload = zlib.decompress(data[offset:offset + length])
                memo_indices = [
                    argument
                    for opcode, argument, _ in pickletools.genops(payload)
                    if opcode.name in {"BINPUT", "LONG_BINPUT"}
                ]
                self.assertTrue(memo_indices, f"slot {slot_id} must contain memo writes")
                self.assertLess(
                    max(memo_indices),
                    len(payload),
                    f"slot {slot_id} contains an unbounded memo index",
                )

    def test_language_menu_injects_default_language_with_parenthesized_labels(self):
        fixture = build_default_language_menu_fixture_rpyc()
        import zlib
        harness = r"""
package com.slgtranslator.app;

import java.nio.file.Files;
import java.nio.file.Paths;

public final class DefaultLanguageMenuHarness {
    public static void main(String[] args) throws Exception {
        byte[] input = Files.readAllBytes(Paths.get(args[0]));
        byte[] output = LanguageMenuSupport.injectMenu(input, "chinese", "slgtranslated");
        if (output == null) {
            throw new AssertionError("injectMenu returned null for Language(None) menu");
        }
        if (!LanguageMenuSupport.menuHasLanguage(output, "slgtranslated")) {
            throw new AssertionError("slgtranslated language entry was not written");
        }
        Files.write(Paths.get(args[1]), output);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="default-language-menu-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            output_path = temporary_path / "injected.rpyc"
            harness_path = temporary_path / "DefaultLanguageMenuHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            completed = subprocess.run(
                [
                    str(JAVA),
                    "-cp", str(classes),
                    "com.slgtranslator.app.DefaultLanguageMenuHarness",
                    str(fixture_path),
                    str(output_path),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", "replace"),
            )
            data = output_path.read_bytes()
            pos = len(RPC2_MAGIC)
            texts = b""
            while pos + 12 <= len(data):
                sid, off, ln = struct.unpack_from("<III", data, pos)
                if sid == 0:
                    break
                texts += zlib.decompress(data[off:off + ln])
                pos += 12
            self.assertIn(b'Language("slgtranslated")', texts)
            self.assertIn('("翻译文本")'.encode("utf-8"), texts)
            self.assertEqual(2, texts.count(b"Language(None)"))
            self.assertEqual(2, texts.count(b'Language("chinese")'))
            self.assertEqual(2, texts.count('("简体中文")'.encode("utf-8")))

    def test_rpyc_text_extractor_registers_structural_reading_bridge(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        self.assertTrue(extractor.exists(), "RpycTextExtractor.java must exist")
        source = extractor.read_text("utf-8")
        for token in (
            "extractTexts", "walk", "MEMOIZE", "BINGET", "what", "caption",
            "SHORT_BINUNICODE", "BINUNICODE",
        ):
            self.assertIn(token, source)
        scanner = SCANNER.read_text("utf-8")
        for token in (
            "readRenpyTexts",
            "RpycTextExtractor.extractRecords",
            "renpyRecords.put(renpyRecordJson(record, sourceOwner))",
        ):
            self.assertIn(token, scanner)
        builder = BUILDER.read_text("utf-8")
        for token in ("READ_TEXTS_SIGNATURE", "FastApkScanner;->readRenpyTexts"):
            self.assertIn(token, builder)

    def test_streaming_extractor_handles_large_repetitive_rpyc_under_small_heap(self):
        scanner = SCANNER.read_text("utf-8")
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycStreamingExtractor.java"
        self.assertIn("RpycStreamingExtractor.extractRecords", scanner)
        self.assertTrue(extractor.exists(), "RpycStreamingExtractor.java must exist")
        source = extractor.read_text("utf-8")
        self.assertIn("InputStream", source)
        self.assertNotIn("List<int[]> ops", source)
        slot_source = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycSlotSource.java"
        self.assertTrue(slot_source.exists(), "RpycSlotSource.java must exist")
        self.assertIn("openInflatedSlot", slot_source.read_text("utf-8"))

    def test_rpyc_extractor_keeps_menu_choices_and_single_token_labels(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        for token in (
            "itemsMode", "afterTuple3", "isChoiceLabel", "0x87", "TUPLE3",
            "items\".equals(lastKey)", 
        ):
            self.assertIn(token, source)

    def test_translation_compiler_preflights_rewrite_storage(self):
        source = (
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
            / "TranslationCompiler.java"
        ).read_text("utf-8")
        for token in (
            "android.os.StatFs",
            "getAvailableBytes()",
            "translation_storage_insufficient",
            "pruneStaleBuildCopies",
        ):
            self.assertIn(token, source)
        self.assertLess(
            source.index("translation_storage_insufficient"),
            source.index("rewriteApkWithEntries"),
        )
        scanner = SCANNER.read_text("utf-8")
        for token in (
            "RpycTextExtractor.extractRecords",
            'renpyRecords.put(renpyRecordJson(record, sourceOwner))',
        ):
            self.assertIn(token, scanner)

        fixture = build_menu_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class MenuExtractorHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("Hello, world!"), "dialogue must be extracted");
        require(set.contains("First choice"), "first menu label must be extracted");
        require(set.contains("Start"), "_() marked screen text must be extracted");
        require(set.contains("Sky"), "Character name must be extracted");
        require(set.contains("Second{#x}"), "tagged menu label must be extracted");
        require(set.contains("$1100"), "money menu label must be extracted");
        require(set.contains("Fine"), "single-token capitalized label must be extracted");
        require(!set.contains("statement_start"), "attr key must not be treated as a label");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="menu-extractor-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "MenuExtractorHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "MenuExtractorHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_translation_compiler_storage_preflight_prunes_stale_build_material(self):
        harness = r"""
package com.slgtranslator.app;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Method;

public final class TranslationStoragePreflightHarness {
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File installed = new File(root, "installed-apks");
        require(installed.mkdirs(), "installed-apks directory must be created");
        File source = new File(installed, "current.apk");
        File staleApk = new File(installed, "old.apk");
        File staleTemp = new File(installed, "old.apk.tl.tmp");
        File stalePartial = new File(installed, "old.partial");
        write(source, 4096);
        write(staleApk, 2048);
        write(staleTemp, 128);
        write(stalePartial, 128);

        File output = new File(root, "SLG-Translator-Output/current.rpy");
        write(output, 64);
        File storeDirectory = new File(root, "cache/slg-pending-apk");
        PendingApkEntryStore store = new PendingApkEntryStore(storeDirectory);
        store.add("generated.rpyc", "game/generated.rpy", new byte[1234]);
        require(store.totalPayloadBytes() == 1234, "payload size must be accounted");

        Method preflight = TranslationCompiler.class.getDeclaredMethod(
                "preflightRewriteStorage", File.class, PendingApkEntryStore.class);
        preflight.setAccessible(true);
        preflight.invoke(null, source, store);

        require(source.isFile(), "current source APK must be kept");
        require(!staleApk.exists(), "stale APK copy must be pruned");
        require(!staleTemp.exists(), "stale .tl.tmp must be pruned");
        require(!stalePartial.exists(), "stale .partial must be pruned");
        require(output.isFile(), "translation output must be untouched");
        store.close();
    }

    private static void write(File file, int size) throws Exception {
        File parent = file.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new AssertionError("cannot create " + parent);
        }
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(new byte[size]);
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="translation-storage-preflight-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "TranslationStoragePreflightHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.TranslationStoragePreflightHarness", str(temporary_path)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_processed_apk_source_is_rejected_before_scan_and_compile(self):
        compiler = (
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
            / "TranslationCompiler.java"
        ).read_text("utf-8")
        scanner = (
            FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
            / "FastApkScanner.java"
        ).read_text("utf-8")
        self.assertIn("translation_source_already_processed", compiler)
        self.assertIn("assertPristineSource", compiler)
        self.assertIn("TranslationCompiler.assertPristineSource(apk)", scanner)
        self.assertLess(
            scanner.index("TranslationCompiler.assertPristineSource(apk)"),
            scanner.index("Enumeration<? extends ZipEntry> enumeration"),
            "scan must reject processed APKs before enumerating/translating entries",
        )

    def test_rpyc_extractor_extracts_source_call_argument_texts(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        self.assertIn("collectSourceCallRecords", source)

        fixture = build_source_call_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class SourceCallHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("Hello, world!"), "dialogue must still be extracted");
        require(set.contains("Hello there."), "phone message text must be extracted");
        require(set.contains("Music Volume"), "preference label must be extracted");
        require(set.contains("Auto-Forward Time"), "slider preference label must be extracted");
        require(!set.contains("sender"), "variable argument must not be extracted");
        require(!set.contains("message_text"), "variable argument must not be extracted");
        require(!set.contains("images/ch2ep1_1042.jpg"), "path argument must not be extracted");
        require(!set.contains("aine_dm"), "channel argument must not be extracted");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="source-call-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "SourceCallHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SourceCallHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_old_only_mode_skips_translated_what_and_new(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        self.assertIn("onlyOld", source)

        fixture = build_translate_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class OldOnlyHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes, true);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("English original"), "old key must be extracted");
        require(!set.contains("English dialogue"), "translated what must not be extracted");
        require(!set.contains("English screen text"), "screen text must not be extracted");
        require(!set.contains("\u4e2d\u6587\u539f\u6587"), "new value must not be extracted");
        // Full mode keeps dialogue and screen text as before.
        List<String> full = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> fullSet = new java.util.HashSet<>(full);
        require(fullSet.contains("English dialogue"), "full mode keeps dialogue");
        require(fullSet.contains("English screen text"), "full mode keeps screen text");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="old-only-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "OldOnlyHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "OldOnlyHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_returns_structured_records_without_breaking_text_api(self):
        record_model = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RenpyTextRecord.java"
        self.assertTrue(record_model.exists(), "RenpyTextRecord.java must exist")
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        for token in ("extractRecords", "RenpyTextRecord", "sourcePath", "occurrence"):
            self.assertIn(token, source)
        scanner = SCANNER.read_text("utf-8")
        for token in (
            '"renpyRecords"',
            'result.put("content", content)',
            'content = "";',
        ):
            self.assertIn(token, scanner)

        fixture = build_structured_records_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class StructuredRecordsHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        String sourcePath = "assets/x-game/archive.rpa!/game/chapter1.rpyc";
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(bytes, sourcePath, false);
        require(find(records, "Hello, world!", RenpyTextRecord.Kind.DIALOGUE, sourcePath, 1, "Narrator"),
                "dialogue record must keep kind/sourcePath/occurrence/speaker");
        require(find(records, "A quiet line.", RenpyTextRecord.Kind.DIALOGUE, sourcePath, 1, ""),
                "dialogue without who must not inherit a stale speaker");
        require(find(records, "A structurally unowned line.", RenpyTextRecord.Kind.DIALOGUE,
                sourcePath, 1, ""),
                "dialogue after another structural field must not inherit a stale speaker");
        require(!find(records, "not a source call", RenpyTextRecord.Kind.UI_STRING,
                sourcePath, 1, ""),
                "literal marked-call text inside what must not be rescanned as source");
        require(find(records, "First choice", RenpyTextRecord.Kind.MENU, sourcePath, 1, ""),
                "menu label must be a structured menu record");
        require(find(records, "Second{#x}", RenpyTextRecord.Kind.MENU, sourcePath, 1, ""),
                "tagged menu label must keep its exact text key");
        require(find(records, "Start", RenpyTextRecord.Kind.UI_STRING, sourcePath, 1, ""),
                "_() text must be a structured UI string");
        require(find(records, "Repeat me", RenpyTextRecord.Kind.UI_STRING, sourcePath, 1, ""),
                "first repeated heuristic record must keep occurrence 1");
        require(find(records, "Repeat me", RenpyTextRecord.Kind.UI_STRING, sourcePath, 2, ""),
                "repeated heuristic text must produce a second occurrence");
        require(find(records, "Shared hint", RenpyTextRecord.Kind.UI_STRING, sourcePath, 1, ""),
                "UI heuristic text must survive even when another heuristic kind reuses it");
        require(find(records, "Shared hint", RenpyTextRecord.Kind.CUSTOM_STATEMENT, sourcePath, 2, ""),
                "same heuristic text under a different kind must remain distinct and increment occurrence");
        require(find(records, "Sky", RenpyTextRecord.Kind.CHARACTER_NAME, sourcePath, 1, ""),
                "Character() name must be a structured name record");
        require(find(records, "Save{#menu}", RenpyTextRecord.Kind.TRANSLATION_OLD, sourcePath, 1, ""),
                "old translation key must be structured without losing tags");

        List<RenpyTextRecord> oldOnly = RpycTextExtractor.extractRecords(bytes, sourcePath, true);
        require(oldOnly.size() == 1, "old-only mode must keep only TRANSLATION_OLD records");
        RenpyTextRecord only = oldOnly.get(0);
        require("Save{#menu}".equals(only.text), "old-only mode keeps the old key");
        require(only.kind == RenpyTextRecord.Kind.TRANSLATION_OLD, "old-only mode kind must be TRANSLATION_OLD");
        require(sourcePath.equals(only.sourcePath), "old-only mode keeps the virtual source path");

        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("Hello, world!"), "legacy text API keeps dialogue");
        require(set.contains("First choice"), "legacy text API keeps menu labels");
        require(set.contains("Second{#x}"), "legacy text API keeps exact tagged keys");
        require(set.contains("Start"), "legacy text API keeps UI strings");
        require(set.contains("Sky"), "legacy text API keeps character names");
        require(set.contains("Save{#menu}"), "legacy text API keeps old translation keys");
    }

    private static boolean find(List<RenpyTextRecord> records, String text, RenpyTextRecord.Kind kind,
                                String sourcePath, int occurrence, String speaker) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)
                    && kind == record.kind
                    && sourcePath.equals(record.sourcePath)
                    && record.occurrence == occurrence
                    && speaker.equals(record.speaker)) {
                require("".equals(record.identifier), "identifier must stay empty when unavailable");
                return true;
            }
        }
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="structured-records-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "StructuredRecordsHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "StructuredRecordsHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_does_not_leak_speaker_between_adjacent_dialogue_nodes(self):
        fixture = build_adjacent_dialogue_speaker_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class AdjacentDialogueSpeakerHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                bytes, "game/speakers.rpyc", false);
        require(find(records, "First adjacent line", "alice", 31),
                "first adjacent dialogue must retain alice");
        require(find(records, "Second adjacent line", "", 32),
                "second adjacent dialogue without who must have an empty speaker");
    }

    private static boolean find(List<RenpyTextRecord> records, String text,
                                String speaker, int sourceLine) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)
                    && record.kind == RenpyTextRecord.Kind.DIALOGUE
                    && speaker.equals(record.speaker)
                    && record.sourceLine == sourceLine) {
                return true;
            }
        }
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="adjacent-dialogue-speaker-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "AdjacentDialogueSpeakerHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "AdjacentDialogueSpeakerHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_dialogue_id_mode_preserves_context_specific_translations(self):
        model = DIALOGUE_TRANSLATION.read_text("utf-8")
        writer = PICKLE_WRITER.read_text("utf-8")
        extractor = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                     / "RpycTextExtractor.java").read_text("utf-8")
        ui = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        for token in (
            "public final String identifier",
            "public final String speakerExpression",
            "public final String oldText",
            "public final String newText",
            "public final int sourceLine",
            "withNewText",
        ):
            self.assertIn(token, model)
        for token in (
            "extractDialogueTranslations",
            "TranslateSay",
            "isSafeIdentifier",
            "dialogue ID writer is not verified",
            "buildDialogueTranslationRpyc",
            "TranslateString",
        ):
            self.assertIn(token, extractor + writer)
        for token in (
            "__slgDialogueIdMode=false",
            "default_global_string_map",
            "identifier_reused_for_multiple_old",
            "__slgSetDialogueIdMode",
            "__slgRegisterDialogueRecords",
            "dialogueIdMode:!!window.__slgDialogueIdMode",
            "dialogueTranslations:window.__slgDialogueIdTranslations||[]",
        ):
            self.assertIn(token, ui)

        fixture = build_dialogue_id_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RenpyDialogueTranslation;
import com.slgtranslator.app.RpycPickleWriter;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

public final class DialogueIdHarness {
    public static void main(String[] args) throws Exception {
        byte[] fixture = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        String source = "assets/x-game/game/dialogue.rpyc";
        List<RenpyDialogueTranslation> extracted =
                RpycTextExtractor.extractDialogueTranslations(fixture, source);
        require(extracted.size() == 2, "two existing dialogue IDs must be recovered");
        require("dialogue-a".equals(extracted.get(0).identifier), "first ID must be preserved");
        require("dialogue-b".equals(extracted.get(1).identifier), "second ID must be preserved");
        require("Fine.".equals(extracted.get(0).oldText)
                && "Fine.".equals(extracted.get(1).oldText),
                "same old text must remain in both contexts");
        require(extracted.get(0).sourceLine == 10 && extracted.get(1).sourceLine == 20,
                "source lines must be read only from serialized linenumber fields");

        List<RenpyDialogueTranslation> translated = new ArrayList<>();
        translated.add(extracted.get(0).withNewText("很好。"));
        translated.add(extracted.get(1).withNewText("行。"));
        List<String[]> strings = new ArrayList<>();
        strings.add(new String[]{"Continue", "继续"});
        require(RpycPickleWriter.isDialogueIdWriterVerified(
                RpycPickleWriter.Dialect.PY3_MODERN, 17),
                "the fixture-verified modern AST must be enabled");
        require(!RpycPickleWriter.isDialogueIdWriterVerified(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, 17),
                "protocol-2 dialogue AST must remain extract-only");
        byte[] pickle = RpycPickleWriter.buildDialogueTranslationPickle(
                RpycPickleWriter.Dialect.PY3_MODERN, "slgtranslated", "game/dialogue.rpy",
                translated, strings, 17, "dialogue-key");
        String raw = new String(pickle, StandardCharsets.UTF_8);
        require(raw.contains("TranslateSay"), "advanced artifact must contain TranslateSay");
        require(raw.contains("dialogue-a") && raw.contains("dialogue-b"),
                "advanced artifact must retain both identifiers");
        require(raw.contains("很好。") && raw.contains("行。"),
                "advanced artifact must retain context-specific translations");
        require(raw.contains("TranslateString") && raw.contains("Continue") && raw.contains("继续"),
                "menus and UI strings must remain in the mixed string map");

        List<RenpyDialogueTranslation> written =
                RpycTextExtractor.extractDialogueTranslations(
                        RpycPickleWriter.buildDialogueTranslationRpyc(
                                RpycPickleWriter.Dialect.PY3_MODERN, "slgtranslated",
                                "game/dialogue.rpy", translated, strings, 17, "dialogue-key"),
                        source);
        require(written.size() == 2, "writer output must remain dialogue-ID addressable");
        require("dialogue-a".equals(written.get(0).identifier)
                && "dialogue-b".equals(written.get(1).identifier),
                "writer must not merge equal old strings by text");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="dialogue-id-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "DialogueIdHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "DialogueIdHarness", str(fixture_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

        runtime_start = ui.index("dialogue_id_runtime = r'''")
        runtime_end = ui.index("'''", runtime_start + len("dialogue_id_runtime = r'''"))
        runtime = ui[runtime_start + len("dialogue_id_runtime = r'''"):runtime_end]
        node_script = runtime + r"""
globalThis.__slgDialogueIdCapability={extractorVerified:true,writerVerified:true,astVersionVerified:true,rollbackValidated:true};
__slgRegisterDialogueRecords([
  {kind:`DIALOGUE`,identifier:`dialogue-a`,text:`Fine.`,coverageCertain:true},
  {kind:`DIALOGUE`,identifier:`dialogue-b`,text:`Fine.`,coverageCertain:true}
]);
let status=__slgPrepareDialogueIdMode(true,[{identifier:`dialogue-a`,oldText:`Fine.`,newText:`很好。`}]);
if(!status.enabled||status.contextCount!==2)throw new Error(JSON.stringify(status));
__slgRegisterDialogueRecords([{kind:`DIALOGUE`,identifier:`dialogue-a`,text:`Other`,coverageCertain:true}]);
if(__slgDialogueIdMode||__slgDialogueIdStatus.reason!==`identifier_reused_for_multiple_old`){throw new Error(`identifier collision was not fail-closed`)}
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dialogue_id_safety_and_ast_matrix_fails_closed_before_translate_say(self):
        harness = r"""
package com.slgtranslator.app;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public final class DialogueIdSafetyHarness {
    private static RenpyDialogueTranslation valid(String id, String oldText) {
        return new RenpyDialogueTranslation(id, "Alice", oldText, "new-" + oldText,
                "game/dialogue.rpy", 1);
    }

    private static void rejectIdentifier(String id) {
        try {
            valid(id, "old");
            throw new AssertionError("unsafe identifier was accepted: " + id);
        } catch (IllegalArgumentException expected) {
            // Fail closed before a writer can receive the identifier.
        }
    }

    private static void rejectAdvanced(RpycPickleWriter.Dialect dialect, int version) {
        List<RenpyDialogueTranslation> dialogue = new ArrayList<>();
        dialogue.add(valid("dialogue-safe", "old"));
        List<String[]> strings = new ArrayList<>();
        strings.add(new String[]{"Menu", "菜单"});
        try {
            byte[] output = RpycPickleWriter.buildDialogueTranslationPickle(
                    dialect, "slgtranslated", "game/dialogue.rpy", dialogue,
                    strings, version, "dialogue-key");
            String raw = new String(output, StandardCharsets.UTF_8);
            throw new AssertionError("unverified target emitted TranslateSay: "
                    + dialect + "/" + version + " raw=" + raw);
        } catch (IllegalArgumentException expected) {
            // Protocol 2 and non-17 modern ASTs remain extract-only.
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        rejectIdentifier(null);
        rejectIdentifier("");
        rejectIdentifier(" dialogue-safe");
        rejectIdentifier("dialogue-safe ");
        rejectIdentifier("dialogue();");
        rejectIdentifier(new String(new char[257]).replace('\0', 'x'));

        require(RpycPickleWriter.isDialogueIdWriterVerified(
                RpycPickleWriter.Dialect.PY3_MODERN, 17),
                "only modern AST 17 is fixture verified");
        require(!RpycPickleWriter.isDialogueIdWriterVerified(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, 17),
                "protocol 2 must remain extract-only");
        require(!RpycPickleWriter.isDialogueIdWriterVerified(
                RpycPickleWriter.Dialect.PY3_MODERN, 16),
                "modern AST 16 must remain extract-only");
        require(!RpycPickleWriter.isDialogueIdWriterVerified(
                RpycPickleWriter.Dialect.PY3_MODERN, 18),
                "modern AST 18 must remain extract-only");

        List<RenpyDialogueTranslation> mixedDialogue = new ArrayList<>();
        mixedDialogue.add(valid("dialogue-a", "Fine."));
        List<String[]> mixedStrings = new ArrayList<>();
        mixedStrings.add(new String[]{"First choice", "第一个选项"});
        mixedStrings.add(new String[]{"Alice", "爱丽丝"});
        mixedStrings.add(new String[]{"Settings", "设置"});
        String mixedRaw = new String(RpycPickleWriter.buildDialogueTranslationPickle(
                RpycPickleWriter.Dialect.PY3_MODERN, "slgtranslated",
                "game/dialogue.rpy", mixedDialogue, mixedStrings, 17, "dialogue-key"),
                StandardCharsets.UTF_8);
        require(mixedRaw.contains("TranslateSay") && mixedRaw.contains("dialogue-a"),
                "verified dialogue must remain context-specific");
        require(mixedRaw.contains("TranslateString")
                && mixedRaw.contains("First choice") && mixedRaw.contains("第一个选项")
                && mixedRaw.contains("Alice") && mixedRaw.contains("爱丽丝")
                && mixedRaw.contains("Settings") && mixedRaw.contains("设置"),
                "menu, character and marked UI strings must stay in the global map");

        rejectAdvanced(RpycPickleWriter.Dialect.PY2_PROTOCOL_2, 17);
        rejectAdvanced(RpycPickleWriter.Dialect.PY3_MODERN, 16);
        rejectAdvanced(RpycPickleWriter.Dialect.PY3_MODERN, 18);

        List<RenpyDialogueTranslation> duplicate = new ArrayList<>();
        duplicate.add(valid("same-id", "old-a"));
        duplicate.add(valid("same-id", "old-b"));
        try {
            RpycPickleWriter.buildDialogueTranslationPickle(
                    RpycPickleWriter.Dialect.PY3_MODERN, "slgtranslated",
                    "game/dialogue.rpy", duplicate, new ArrayList<String[]>(),
                    17, "dialogue-key");
            throw new AssertionError("duplicate ID mapped to different old text emitted TranslateSay");
        } catch (IllegalArgumentException expected) {
            // A collision must fall back to the global string-map path.
        }
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="dialogue-id-safety-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "DialogueIdSafetyHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs), str(DIALOGUE_TRANSLATION), str(PICKLE_WRITER),
                    str(harness_path),
                ],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.DialogueIdSafetyHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_matches_official_marked_string_forms(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        for token in ("extractRecords", "coverageCertain", "identifier"):
            self.assertIn(token, source)

        fixture = build_official_marked_string_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class OfficialMarkedStringHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        String sourcePath = "assets/x-game/game/official_marked_strings.rpyc";
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(bytes, sourcePath, false);
        require(records.size() == 5, "official forms must yield five visible records: " + records.size());
        require(find(records, "single", "", sourcePath, 1), "_('single') must be extracted");
        require(find(records, "double", "", sourcePath, 1), "__(\"double\") must be extracted");
        require(find(records, "multi\nline", "", sourcePath, 1), "triple-quoted ___() text must be extracted");
        require(find(records, "raw text", "", sourcePath, 1), "raw-string _() text must be extracted");
        require(find(records, "Continue", "menu-context", sourcePath, 1), "_p() must keep visible text tied to its context");
        require(!containsText(records, "menu-context"), "_p context must not become visible text");
        require(!containsText(records, "_('single')"), "source code must not leak as extracted text");

        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.size() == 5, "legacy text API must keep five visible strings");
        require(set.contains("single"), "legacy text API keeps single-quoted text");
        require(set.contains("double"), "legacy text API keeps double-quoted text");
        require(set.contains("multi\nline"), "legacy text API keeps triple-quoted text");
        require(set.contains("raw text"), "legacy text API keeps raw-string text");
        require(set.contains("Continue"), "legacy text API keeps _p visible text");
        require(!set.contains("menu-context"), "legacy text API must not include _p context");
    }

    private static boolean find(List<RenpyTextRecord> records, String text, String identifier,
                                String sourcePath, int occurrence) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)
                    && record.kind == RenpyTextRecord.Kind.UI_STRING
                    && identifier.equals(record.identifier)
                    && sourcePath.equals(record.sourcePath)
                    && record.occurrence == occurrence) {
                require("".equals(record.speaker), "marked-string helper records must not invent speakers");
                require(!record.coverageCertain, "marked-string helper coverage must stay conservative");
                return true;
            }
        }
        return false;
    }

    private static boolean containsText(List<RenpyTextRecord> records, String text) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)) {
                return true;
            }
        }
        return false;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="official-marked-string-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "OfficialMarkedStringHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "OfficialMarkedStringHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_preserves_exact_marked_string_keys_and_dynamic_uncertainty(self):
        fixture = build_marked_string_exact_key_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class ExactMarkedKeyHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                bytes, "assets/x-game/game/exact_keys.rpyc", false);
        require(find(records, "Save{#slot}", "", 1), "{#slot} key must stay exact");
        require(find(records, "Save{#menu}", "", 1), "{#menu} key must stay exact");
        require(!containsText(records, "dynamic_label"), "dynamic expression source must not become text");
        require(countUnknown(records) >= 2, "dynamic marked-string forms must leave uncertainty diagnostics");

        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("Save{#slot}"), "legacy text API keeps Save{#slot}");
        require(set.contains("Save{#menu}"), "legacy text API keeps Save{#menu}");
        require(!set.contains("dynamic_label"), "legacy text API must not leak dynamic expressions");
    }

    private static boolean find(List<RenpyTextRecord> records, String text, String identifier, int occurrence) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)
                    && record.kind == RenpyTextRecord.Kind.UI_STRING
                    && identifier.equals(record.identifier)
                    && record.occurrence == occurrence) {
                require(!record.coverageCertain, "marked-string helper coverage must stay conservative");
                return true;
            }
        }
        return false;
    }

    private static boolean containsText(List<RenpyTextRecord> records, String text) {
        for (RenpyTextRecord record : records) {
            if (text.equals(record.text)) {
                return true;
            }
        }
        return false;
    }

    private static int countUnknown(List<RenpyTextRecord> records) {
        int count = 0;
        for (RenpyTextRecord record : records) {
            if (record.kind == RenpyTextRecord.Kind.UNKNOWN && !record.coverageCertain) {
                count++;
                require(record.text.isEmpty(), "uncertain diagnostics must not inject visible text");
            }
        }
        return count;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="exact-marked-key-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "ExactMarkedKeyHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "ExactMarkedKeyHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_accepts_legal_prefixes_and_keeps_triple_quote_boundaries(self):
        fixture = build_marked_string_prefix_boundary_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class PrefixBoundaryHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<RenpyTextRecord> records = RpycTextExtractor.extractRecords(
                bytes, "assets/x-game/game/prefix_boundaries.rpyc", false);
        Set<String> texts = new HashSet<>();
        int unknown = 0;
        for (RenpyTextRecord record : records) {
            if (record.kind == RenpyTextRecord.Kind.UNKNOWN) {
                unknown++;
                require(!record.coverageCertain, "diagnostics must be uncertain");
                require(record.text.isEmpty(), "diagnostics must not inject source text");
            } else {
                texts.add(record.text);
            }
        }
        require(texts.contains("unicode"), "u prefix must be accepted");
        require(texts.contains("binary"), "b prefix must be accepted");
        require(texts.contains("unicode raw"), "ur prefix must be accepted");
        require(texts.contains("binary raw"), "rb prefix must be accepted");
        require(texts.contains("single triple"), "single triple quote must close exactly");
        require(texts.contains("double triple"), "double triple quote must close exactly");
        require(texts.contains("first"), "triple quote must not swallow the following call");
        require(texts.contains("after"), "call after a triple-quoted string must be scanned");
        require(!texts.contains("invalid prefix"), "illegal prefix must not become text");
        require(!texts.contains("not a call"), "nested call text inside a quoted source must be ignored");
        require(unknown >= 2, "illegal/dynamic forms must leave uncertainty diagnostics");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="prefix-boundary-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "PrefixBoundaryHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "PrefixBoundaryHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_keeps_renpy_markup_dialogue(self):
        """Dialogue containing Ren'Py markup tags like {/i} and {/b} must
        not be rejected as file paths.  The '/' inside markup tags is not
        a path separator."""
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        self.assertIn("pathCheck", source, "isUserText must strip markup before path check")

        fixture = build_markup_fixture_rpyc()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class MarkupExtractorHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        java.util.Set<String> set = new java.util.HashSet<>(texts);
        require(set.contains("I like you a lot. You are good at causing some {i}activity{/i} inside me."),
                "italic markup dialogue must be extracted");
        require(set.contains("No, {b}kill{/b} her..."),
                "bold markup dialogue must be extracted");
        require(!set.contains("images/scenes/ch1ep1_001.png"),
                "real file path must still be filtered");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="markup-extractor-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "MarkupExtractorHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "MarkupExtractorHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_extractor_accepts_padding_after_zlib_stream(self):
        """Real Ren'Py RPC2 slots may include alignment bytes after zlib EOF."""
        fixture = build_rpc2_fixture_with_zlib_padding()
        harness = r"""
import com.slgtranslator.app.RpycTextExtractor;
import java.nio.file.Files;
import java.util.List;

public final class ZlibPaddingHarness {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        List<String> texts = RpycTextExtractor.extractTexts(bytes);
        require(texts.contains("No, {b}kill{/b} her..."),
                "alignment bytes after zlib EOF must not discard the slot");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="zlib-padding-test-") as temporary:
            temporary_path = Path(temporary)
            fixture_path = temporary_path / "fixture.rpyc"
            harness_path = temporary_path / "ZlibPaddingHarness.java"
            classes = temporary_path / "classes"
            fixture_path.write_bytes(fixture)
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes), "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "ZlibPaddingHarness", str(fixture_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_fast_scanner_reads_translation_entries_in_old_only_mode(self):
        scanner = SCANNER.read_text("utf-8")
        self.assertIn("RpycTextExtractor.extractRecords", scanner)
        self.assertIn("translationBucket", scanner)
        self.assertIn("String lower = entryName.toLowerCase(Locale.ROOT);", scanner)
        self.assertIn('lower.contains("/x-tl/")', scanner)
        self.assertIn('lower.contains("/tl/")', scanner)

    def test_cleanup_storage_keeps_newest_patch_and_selection_source(self):
        cleanup = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "CleanupSupport.java"
        self.assertTrue(cleanup.exists(), "CleanupSupport.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in (
            "CLEANUP_SIGNATURE", "CLEANUP_DELEGATE", "CleanupSupport;->cleanupStorage",
        ):
            self.assertIn(token, builder)
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.CleanupSupport;
import java.io.File;

public final class CleanupHarness {
    static final class FakeContext extends Context {
        File external;
        @Override public File getExternalFilesDir(String type) { return external; }
    }
    static final class CapturingCall extends PluginCall {
        String keepUri;
        String rejected;
        @Override public String getString(String key) {
            return "keepUri".equals(key) ? keepUri : null;
        }
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
    }

    public static void main(String[] args) throws Exception {
        File base = new File(args[0]);
        File installed = new File(base, "installed-apks"); installed.mkdirs();
        File keep = new File(installed, "keep.apk"); require(keep.createNewFile(), "create keep");
        File staleSource = new File(installed, "stale.apk"); require(staleSource.createNewFile(), "create stale");
        File output = new File(base, "SLG-Translator-Output"); output.mkdirs();
        File patchOld = new File(output, "patch-old.apk"); require(patchOld.createNewFile(), "create old patch");
        patchOld.setLastModified(1000L);
        File patchNew = new File(output, "patch-new.apk"); require(patchNew.createNewFile(), "create new patch");
        patchNew.setLastModified(3000L);
        FakeContext context = new FakeContext();
        context.external = base;
        CapturingCall call = new CapturingCall();
        call.keepUri = keep.toURI().toString();
        CleanupSupport.cleanupStorage(context, call);
        require(call.rejected == null, "cleanup must resolve: " + call.rejected);
        require(!staleSource.exists(), "stale installed copy must be deleted");
        require(keep.exists(), "current selection source must be kept");
        require(!patchOld.exists(), "old patch must be deleted");
        require(patchNew.exists(), "newest patch must be kept");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="cleanup-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CleanupHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            fixture.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CleanupHarness", str(fixture)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_cleanup_storage_deletes_other_games_patch_by_package(self):
        """Patch APKs whose package differs from the selected game are
        deleted (their patches are already installed); the selected game's
        own patch is kept."""
        cleanup = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "CleanupSupport.java"
        source = cleanup.read_text("utf-8")
        self.assertIn("packageName", source)
        self.assertIn("packageNameOf", source)
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.CleanupSupport;
import java.io.File;

public final class CleanupPackageHarness {
    static final class FakeContext extends Context {
        File external;
        @Override public File getExternalFilesDir(String type) { return external; }
    }
    static final class CapturingCall extends PluginCall {
        String keepUri, packageName;
        String rejected;
        @Override public String getString(String key) {
            if ("keepUri".equals(key)) return keepUri;
            if ("packageName".equals(key)) return packageName;
            return null;
        }
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
    }
    public static void main(String[] args) throws Exception {
        File base = new File(args[0]);
        File installed = new File(base, "installed-apks"); installed.mkdirs();
        File keep = new File(installed, "keep.apk"); require(keep.createNewFile(), "create keep");
        File output = new File(base, "SLG-Translator-Output"); output.mkdirs();
        File patchOther = new File(output, "patch-other.apk");
        writeManifest(patchOther, "com.other.game");
        File patchCurrent = new File(output, "patch-current.apk");
        writeManifest(patchCurrent, "com.current.game");
        FakeContext context = new FakeContext();
        context.external = base;
        CapturingCall call = new CapturingCall();
        call.keepUri = keep.toURI().toString();
        call.packageName = "com.current.game";
        CleanupSupport.cleanupStorage(context, call);
        require(call.rejected == null, "cleanup must resolve: " + call.rejected);
        require(!patchOther.exists(), "other game patch must be deleted");
        require(patchCurrent.exists(), "current game patch must be kept");
        require(keep.exists(), "current selection source must be kept");
    }
    static void writeManifest(File apk, String pkg) throws Exception {
        java.util.zip.ZipOutputStream out = new java.util.zip.ZipOutputStream(new java.io.FileOutputStream(apk));
        out.putNextEntry(new java.util.zip.ZipEntry("AndroidManifest.xml"));
        byte[] pkgBytes = pkg.getBytes("UTF-16LE");
        out.write(new byte[]{1, 0, 2, 0});
        out.write(pkgBytes);
        out.write(new byte[]{0, 0});
        out.close();
    }
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="cleanup-pkg-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CleanupPackageHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            fixture.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CleanupPackageHarness", str(fixture)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


    def test_cleanup_storage_removes_interrupted_partials_in_installed_apks(self):
        """Cleanup must remove .partial/.tmp leftovers inside installed-apks."""
        cleanup = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "CleanupSupport.java"
        self.assertTrue(cleanup.exists(), "CleanupSupport.java must exist")
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.CleanupSupport;
import java.io.File;

public final class CleanupPartialHarness {
    static final class FakeContext extends Context {
        File external;
        @Override public File getExternalFilesDir(String type) { return external; }
    }
    static final class CapturingCall extends PluginCall {
        String keepUri;
        String rejected;
        @Override public String getString(String key) {
            return "keepUri".equals(key) ? keepUri : null;
        }
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
    }

    public static void main(String[] args) throws Exception {
        File base = new File(args[0]);
        File installed = new File(base, "installed-apks"); installed.mkdirs();
        File keep = new File(installed, "keep.apk"); require(keep.createNewFile(), "create keep");
        File stalePartial = new File(installed, "keep.apk.uuid.partial"); require(stalePartial.createNewFile(), "create partial");
        File staleTmp = new File(installed, "stale.tmp"); require(staleTmp.createNewFile(), "create tmp");
        File output = new File(base, "SLG-Translator-Output"); output.mkdirs();
        FakeContext context = new FakeContext();
        context.external = base;
        CapturingCall call = new CapturingCall();
        call.keepUri = keep.toURI().toString();
        CleanupSupport.cleanupStorage(context, call);
        require(call.rejected == null, "cleanup must resolve: " + call.rejected);
        require(keep.exists(), "current selection source must be kept");
        require(!stalePartial.exists(), "interrupted partial copy must be removed");
        require(!staleTmp.exists(), "interrupted tmp file must be removed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="cleanup-partial-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CleanupPartialHarness.java"
            classes = temporary_path / "classes"
            fixture = temporary_path / "fixture"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            fixture.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "CleanupPartialHarness", str(fixture)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_rpyc_protocol_escapes_backslashes_before_newlines(self):
        """The WebView RPYC bridge must preserve literal backslash-n and newlines."""
        patch_source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        self.assertIn("rpycContentFromRecords", patch_source)
        self.assertIn('e=e.replace(/\\\\/g,"\\\\\\\\")', patch_source)
        self.assertIn('replace(/\\n/g,"\\\\n")', patch_source)

    def test_save_patched_apk_failure_cleans_media_store_entry(self):
        """A failed MediaStore copy must remove the half-written download row."""
        install = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstallSupport.java"
        self.assertTrue(install.exists(), "InstallSupport.java must exist")
        harness = r"""
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.InstallSupport;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

public final class InstallSaveFailureHarness {
    static final class FakeUri extends Uri {}
    static final class FakeResolver extends ContentResolver {
        int deleteCalls = 0;
        @Override public Uri insert(Uri uri, ContentValues values) { return new FakeUri(); }
        @Override public OutputStream openOutputStream(Uri uri) {
            return new OutputStream() {
                @Override public void write(int b) throws IOException { throw new IOException("disk full"); }
            };
        }
        @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
            deleteCalls++;
            return 1;
        }
    }
    static final class FakeContext extends Context {
        final File filesDir;
        FakeContext(File filesDir) { this.filesDir = filesDir; }
        @Override public File getFilesDir() { return filesDir; }
        FakeResolver resolver;
        @Override public ContentResolver getContentResolver() { return resolver; }
    }
    static final class CapturingCall extends PluginCall {
        String rejected;
        @Override public void resolve(JSObject value) {}
        @Override public void reject(String message) { rejected = message; }
        String requestedPath;
        @Override public String getString(String key) {
            return "path".equals(key) ? requestedPath : null;
        }
    }

    public static void main(String[] args) throws Exception {
        File filesDir = new File(args[0]);
        require(filesDir.mkdirs() || filesDir.isDirectory(), "create files dir");
        File output = new File(filesDir, "SLG-Translator-Output");
        require(output.mkdirs() || output.isDirectory(), "create output dir");
        File source = new File(output, "media-failure-patched-signed.apk");
        try (FileOutputStream out = new FileOutputStream(source)) {
            out.write(new byte[131072]);
        }
        FakeContext context = new FakeContext(filesDir);
        context.resolver = new FakeResolver();
        CapturingCall call = new CapturingCall();
        call.requestedPath = source.getAbsolutePath();
        InstallSupport.savePatchedApkToDownloads(context, call);
        require(call.rejected != null, "copy failure must reject the call");
        require(context.resolver.deleteCalls >= 1, "failed media store copy must delete the inserted row");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="install-save-failure-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "InstallSaveFailureHarness.java"
            classes = temporary_path / "classes"
            files_dir = temporary_path / "files"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "InstallSaveFailureHarness", str(files_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_save_resolver_rejects_external_source_and_accepts_output_source(self):
        """Save resolver must only return canonical patched files in app output."""
        install = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstallSupport.java"
        self.assertTrue(install.exists(), "InstallSupport.java must exist")
        harness = r"""
package com.slgtranslator.app;

import android.content.Context;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public final class InstallResolverSafetyHarness {
    static final class FakeContext extends Context {
        final File filesDir;
        FakeContext(File filesDir) { this.filesDir = filesDir; }
        @Override public File getFilesDir() { return filesDir; }
    }

    public static void main(String[] args) throws Exception {
        File filesDir = new File(args[0]);
        require(filesDir.mkdirs() || filesDir.isDirectory(), "create files dir");
        File output = new File(filesDir, "SLG-Translator-Output");
        require(output.mkdirs() || output.isDirectory(), "create output dir");
        File external = new File(filesDir.getParentFile(), "arbitrary-source.apk");
        File valid = new File(output, "valid-patched-signed.apk");
        write(external, "external");

        require(InstallSupport.resolvePatchFile(new FakeContext(filesDir),
                external.getAbsolutePath()) == null,
                "arbitrary external source must be rejected");
        write(valid, "valid");
        File resolved = InstallSupport.resolvePatchFile(new FakeContext(filesDir),
                valid.getAbsolutePath());
        require(resolved != null, "valid output source must resolve");
        require(resolved.getCanonicalFile().equals(valid.getCanonicalFile()),
                "valid output source must resolve to itself");
    }

    private static void write(File file, String contents) throws Exception {
        Files.write(file.toPath(), contents.getBytes(StandardCharsets.UTF_8));
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="install-resolver-safety-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "InstallResolverSafetyHarness.java"
            classes = temporary_path / "classes"
            files_dir = temporary_path / "files"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [
                    str(JAVA), "-cp", str(classes),
                    "com.slgtranslator.app.InstallResolverSafetyHarness", str(files_dir),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_package_installer_session_bridge_is_injected(self):
        """installApk must delegate to PackageInstallerSupport.installViaSession
        so multi-GB patched APKs install without OPPO FileProvider corruption."""
        support = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "PackageInstallerSupport.java"
        self.assertTrue(support.exists(), "PackageInstallerSupport.java must exist")
        source = support.read_text("utf-8")
        for token in ("installViaSession", "PackageInstaller.SessionParams", "MODE_FULL_INSTALL",
                      "session.openWrite", "session.commit", "ACTION_PACKAGE_INSTALLED"):
            self.assertIn(token, source)
        self.assertIn("PendingIntent.getBroadcast(context, 0, broadcast, PendingIntent.FLAG_MUTABLE);", source)
        self.assertNotIn("PendingIntent.getBroadcast(context, 0, broadcast, 0);", source)
        commit_index = source.index("session.commit(sender);")
        close_index = source.index("session.close();")
        self.assertLess(commit_index, close_index, "session must be committed before it is closed")
        self.assertIn("installer.abandonSession(sessionId)", source)
        self.assertIn("STATUS_PENDING_USER_ACTION", source)
        self.assertIn("intent.getParcelableExtra(Intent.EXTRA_INTENT)", source)
        self.assertIn("Intent.FLAG_ACTIVITY_NEW_TASK", source)
        self.assertIn("ctx.startActivity(confirm)", source)
        self.assertIn("Context.RECEIVER_NOT_EXPORTED", source)
        self.assertNotIn("PendingIntent.FLAG_IMMUTABLE", source)
        self.assertEqual(source.count("appContext.registerReceiver(receiver, filter);"), 1)
        self.assertIn("appContext.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);", source)
        builder = BUILDER.read_text("utf-8")
        self.assertIn("INSTALL_APK_SIGNATURE", builder)
        self.assertIn("INSTALL_APK_PATTERN", builder)
        self.assertIn("PackageInstallerSupport;->installViaSession", builder)
        self.assertIn("installViaSession(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V", builder)


    def test_save_transfer_copies_and_counts_files(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in (
            "SAVE_BACKUP_SIGNATURE", "SAVE_RESTORE_SIGNATURE", "SAVE_LIST_SIGNATURE",
            "SaveTransfer;->backupSaves", "SaveTransfer;->restoreSaves", "SaveTransfer;->listSaveBackups",
        ):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import java.io.File;
import java.lang.reflect.Method;

public final class SaveTransferHarness {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        File dest = new File(args[1]);
        File nested = new File(source, "game"); nested.mkdirs();
        File slot = new File(source, "auto-1.save"); require(slot.createNewFile(), "create save");
        File inner = new File(nested, "meta.bin"); require(inner.createNewFile(), "create meta");
        Method copyTree = SaveTransfer.class.getDeclaredMethod("copyTree", File.class, File.class);
        copyTree.setAccessible(true);
        Method countFiles = SaveTransfer.class.getDeclaredMethod("countFiles", File.class);
        countFiles.setAccessible(true);
        int copied = (Integer) copyTree.invoke(null, source, dest);
        require(copied == 2, "two files must be copied: " + copied);
        require(new File(dest, "auto-1.save").isFile(), "save slot copied");
        require(new File(dest, "game/meta.bin").isFile(), "nested file copied");
        require((Integer) countFiles.invoke(null, dest) == 2, "count must match");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-transfer-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveTransferHarness.java"
            classes = temporary_path / "classes"
            source_dir = temporary_path / "source"
            dest_dir = temporary_path / "dest"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            source_dir.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveTransferHarness", str(source_dir), str(dest_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


    def test_save_export_zips_directory_and_counts_files(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in ("SAVE_EXPORT_SIGNATURE", "SaveTransfer;->exportSavesToDownloads"):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import java.io.File;
import java.lang.reflect.Method;
import java.util.zip.ZipFile;

public final class SaveExportHarness {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        File zip = new File(args[1]);
        File nested = new File(source, "game"); nested.mkdirs();
        File slot = new File(source, "auto-1.save"); require(slot.createNewFile(), "create save");
        File inner = new File(nested, "meta.bin"); require(inner.createNewFile(), "create meta");
        Method zipTree = SaveTransfer.class.getDeclaredMethod("zipDirectory", File.class, File.class);
        zipTree.setAccessible(true);
        int zipped = (Integer) zipTree.invoke(null, source, zip);
        require(zipped == 2, "two files must be zipped: " + zipped);
        try (ZipFile archive = new ZipFile(zip)) {
            require(archive.getEntry("auto-1.save") != null, "save slot zipped");
            require(archive.getEntry("game/meta.bin") != null, "nested file zipped");
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-export-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveExportHarness.java"
            classes = temporary_path / "classes"
            source_dir = temporary_path / "source"
            zip_file = temporary_path / "backup.zip"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            source_dir.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveExportHarness", str(source_dir), str(zip_file)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_translation_project_bridge_contract(self):
        builder = BUILDER.read_text("utf-8")
        for token in (
            "TRANSLATION_PROJECT_EXPORT_SIGNATURE",
            "TranslationProjectSupport;->exportTranslationProject",
            "TRANSLATION_PROJECT_IMPORT_SIGNATURE",
            "TranslationProjectSupport;->importTranslationProject",
        ):
            self.assertIn(token, builder)

    def test_delete_patched_apk_bridge_contract(self):
        """deletePatchedApk must be a unique FileManager bridge to InstallSupport."""
        builder = BUILDER.read_text("utf-8")
        signature = ".method public final deletePatchedApk(Lcom/getcapacitor/PluginCall;)V"
        delegate = "Lcom/slgtranslator/app/InstallSupport;->deletePatchedApk"
        method = """.method public final deletePatchedApk(Lcom/getcapacitor/PluginCall;)V
    .annotation runtime Lcom/getcapacitor/PluginMethod;
    .end annotation

    .locals 1
    .param p1, "call"    # Lcom/getcapacitor/PluginCall;

    invoke-virtual {p0}, Lcom/slgtranslator/app/FileManagerPlugin;->getContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0, p1}, Lcom/slgtranslator/app/InstallSupport;->deletePatchedApk(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V
    return-void
.end method"""
        for token in (
            "DELETE_PATCHES_SIGNATURE",
            "DELETE_PATCHES_DELEGATE",
            "DELETE_PATCHES_METHOD",
            signature,
            delegate,
            ".annotation runtime Lcom/getcapacitor/PluginMethod;",
            "FileManagerPlugin;->getContext()Landroid/content/Context;",
            "InstallSupport;->deletePatchedApk(Landroid/content/Context;Lcom/getcapacitor/PluginCall;)V",
        ):
            self.assertIn(token, builder)
        self.assertEqual(builder.count(signature), 2)
        self.assertEqual(builder.count(method), 1)
        self.assertIn("delete_patched_apk_count", builder)

        classes6 = GENERATED / "classes6.dex"
        self.assertTrue(classes6.is_file(), "generated classes6.dex must exist; run build_fast_scanner.py")
        self.assertTrue(DEXDUMP.is_file(), "generated DEX verification requires dexdump.exe")
        dump = subprocess.run(
            [str(DEXDUMP), str(classes6.relative_to(ROOT))],
            check=True,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        ).stdout
        file_manager = re.search(
            r"Class descriptor\s+: 'Lcom/slgtranslator/app/FileManagerPlugin;'.*?(?=\n\s+Class #|\Z)",
            dump,
            re.S,
        )
        self.assertIsNotNone(file_manager, "generated FileManagerPlugin class must exist")
        self.assertEqual(
            len(re.findall(
                r"name\s+: 'deletePatchedApk'\s+type\s+: '\(Lcom/getcapacitor/PluginCall;\)V'",
                file_manager.group(0),
            )),
            1,
        )

    def test_save_share_backup_bridge_contract(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in ("SAVE_SHARE_SIGNATURE", "SaveTransfer;->shareSaveBackup"):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import android.content.Context;
import com.getcapacitor.PluginCall;
import java.lang.reflect.Method;

public final class SaveShareHarness {
    public static void main(String[] args) throws Exception {
        Method share = SaveTransfer.class.getDeclaredMethod("shareSaveBackup", Context.class, PluginCall.class);
        require(share != null, "shareSaveBackup bridge method must exist");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-share-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveShareHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveShareHarness"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_save_import_extracts_shared_archive_safely(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        source = transfer.read_text("utf-8")
        for token in (
            "listSaveArchives", "importSaveBackup", "collectArchives", "extractZip",
            "packageFromName", "Environment.getExternalStoragePublicDirectory",
            "name.contains(\"..\")", "canonicalTarget.getPath().startsWith(rootPrefix)",
            "deleteSaveArchive", "invalid save archive path",
        ):
            self.assertIn(token, source)
        builder = BUILDER.read_text("utf-8")
        for token in (
            "SAVE_ARCHIVES_SIGNATURE", "SAVE_IMPORT_SIGNATURE",
            "SaveTransfer;->listSaveArchives", "SaveTransfer;->importSaveBackup",
            "SAVE_ARCHIVE_DELETE_SIGNATURE", "SaveTransfer;->deleteSaveArchive",
        ):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class SaveImportHarness {
    public static void main(String[] args) throws Exception {
        File zipFile = new File(args[0]);
        File dest = new File(args[1]);
        File unsafeZip = new File(args[2]);
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(zipFile))) {
            write(zip, "com.example.game/auto-1.save", "slot");
            write(zip, "com.example.game/game/meta.bin", "meta");
        }
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(unsafeZip))) {
            write(zip, "../evil.txt", "bad");
        }
        Method extract = SaveTransfer.class.getDeclaredMethod("extractZip", File.class, File.class);
        extract.setAccessible(true);
        int count = (Integer) extract.invoke(null, zipFile, dest);
        require(count == 2, "extracted file count");
        require(new File(dest, "auto-1.save").isFile(), "root stripped");
        require(new File(dest, "game/meta.bin").isFile(), "nested preserved");
        File unsafeDest = new File(dest, "unsafe");
        try {
            extract.invoke(null, unsafeZip, unsafeDest);
            require(false, "unsafe zip must be rejected");
        } catch (InvocationTargetException error) {
            require(error.getCause() instanceof IOException, "unsafe zip rejection reason");
        }
        Method packageName = SaveTransfer.class.getDeclaredMethod("packageFromName", String.class);
        packageName.setAccessible(true);
        Object parsed = packageName.invoke(null, "com.example.game-20260805-120000.zip");
        require("com.example.game".equals(parsed), "package parsed from shared archive name");
        Object shared = packageName.invoke(null, "com.example.game-20260805-120000-20260806-130000.zip");
        require("com.example.game".equals(shared), "package parsed from shared backup name with two stamps");
        Object renamed = packageName.invoke(null, "renamed.zip");
        require(renamed == null, "renamed archive falls back to manual game selection");
    }

    private static void write(ZipOutputStream zip, String name, String content) throws Exception {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes("UTF-8"));
        zip.closeEntry();
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-import-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveImportHarness.java"
            classes = temporary_path / "classes"
            zip_file = temporary_path / "shared.zip"
            dest_dir = temporary_path / "dest"
            unsafe_zip = temporary_path / "unsafe.zip"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveImportHarness", str(zip_file), str(dest_dir), str(unsafe_zip)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


    def test_delete_backup_removes_directory_tree(self):
        transfer = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "SaveTransfer.java"
        self.assertTrue(transfer.exists(), "SaveTransfer.java must exist")
        builder = BUILDER.read_text("utf-8")
        for token in ("SAVE_DELETE_SIGNATURE", "SaveTransfer;->deleteBackup"):
            self.assertIn(token, builder)
        harness = r"""
import com.slgtranslator.app.SaveTransfer;
import android.content.Context;
import com.getcapacitor.PluginCall;
import java.io.File;
import java.lang.reflect.Method;

public final class SaveDeleteHarness {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]);
        File dest = new File(args[1]);
        File nested = new File(source, "game"); nested.mkdirs();
        File slot = new File(source, "auto-1.save"); require(slot.createNewFile(), "create save");
        File inner = new File(nested, "meta.bin"); require(inner.createNewFile(), "create meta");
        Method copyTree = SaveTransfer.class.getDeclaredMethod("copyTree", File.class, File.class);
        copyTree.setAccessible(true);
        Method deleteTree = SaveTransfer.class.getDeclaredMethod("deleteTree", File.class);
        deleteTree.setAccessible(true);
        require(SaveTransfer.class.getDeclaredMethod("deleteBackup", Context.class, PluginCall.class) != null,
            "deleteBackup bridge method must exist");
        int copied = (Integer) copyTree.invoke(null, source, dest);
        require(copied == 2, "two files must be copied: " + copied);
        int deleted = (Integer) deleteTree.invoke(null, dest);
        require(deleted == 2, "two files must be deleted: " + deleted);
        require(!dest.exists(), "backup directory must be removed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="save-delete-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "SaveDeleteHarness.java"
            classes = temporary_path / "classes"
            source_dir = temporary_path / "source"
            dest_dir = temporary_path / "dest"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            source_dir.mkdir()
            subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath",
                    third_party_classpath(),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "SaveDeleteHarness", str(source_dir), str(dest_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_install_delete_safety(self):
        """Only generated patched APKs under the app output directory may be deleted."""
        install = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "InstallSupport.java"
        self.assertTrue(install.exists(), "InstallSupport.java must exist")
        harness = r"""
import android.content.Context;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import com.slgtranslator.app.InstallSupport;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public final class InstallDeleteSafetyHarness {
    static final class FakeContext extends Context {
        final File filesDir;
        FakeContext(File filesDir) { this.filesDir = filesDir; }
        @Override public File getFilesDir() { return filesDir; }
    }

    static final class CapturingCall extends PluginCall {
        String requestedPath;
        String rejected;
        JSObject resolved;
        @Override public String getString(String key) {
            return "path".equals(key) ? requestedPath : null;
        }
        @Override public void resolve(JSObject value) {
            resolved = value;
        }
        @Override public void reject(String message) { rejected = message; }
    }

    public static void main(String[] args) throws Exception {
        File filesDir = new File(args[0]);
        require(filesDir.mkdirs(), "create files dir");
        File output = new File(filesDir, "SLG-Translator-Output");
        require(output.mkdirs(), "create output dir");
        File valid = new File(output, "game-patched-signed.apk");
        File sibling = new File(filesDir, "user-patched-signed.apk");
        File wrongSuffix = new File(output, "notes.apk");
        File directory = new File(output, "folder-patched-signed.apk");
        File symlinkTarget = new File(output, "symlink-target.apk");
        File symlink = new File(output, "link-patched-signed.apk");
        write(valid, "valid");
        write(sibling, "sibling");
        write(wrongSuffix, "wrong suffix");
        require(directory.mkdirs(), "create directory candidate");
        write(symlinkTarget, "symlink target");
        SymlinkAttempt fileSymlink = tryCreateSymbolicLink(
                symlink.toPath(), symlinkTarget.toPath());

        FakeContext context = new FakeContext(filesDir);
        CapturingCall validCall = call(valid.getAbsolutePath());
        InstallSupport.deletePatchedApk(context, validCall);
        require(!valid.exists(), "valid patched APK must be deleted");
        require(validCall.rejected == null, "valid file must not reject: " + validCall.rejected);
        require(validCall.resolved != null,
                "valid deletion must resolve with a result object");
        require(Boolean.TRUE.equals(validCall.resolved.get("deleted")),
                "valid deletion must resolve with deleted=true");

        assertRejected(context, sibling.getAbsolutePath(), sibling, "sibling");
        assertRejected(context, wrongSuffix.getAbsolutePath(), wrongSuffix, "wrong suffix");
        assertRejected(context, directory.getAbsolutePath(), directory, "directory");
        assertRejected(context,
                new File(output, ".." + File.separator + sibling.getName()).getAbsolutePath(),
                sibling, "absolute .. traversal");
        assertRejected(context, "SLG-Translator-Output" + File.separator + valid.getName(),
                null, "relative path");
        assertRejected(context, "content://com.example.documents/document/1", null,
                "content URI");
        assertRejected(context, new File(output, "missing-patched-signed.apk").getAbsolutePath(),
                null, "missing path");
        StringBuilder symlinkSkipReason = new StringBuilder();
        if (fileSymlink.available) {
            assertRejected(context, symlink.getAbsolutePath(), symlink, "symlink");
            require(symlink.exists(), "symlink must remain unchanged");
            require(symlinkTarget.exists(), "symlink target must remain unchanged");
        } else {
            symlinkSkipReason.append("file symlink: ").append(fileSymlink.reason);
        }

        File linkedFilesDir = new File(filesDir.getParentFile(), "linked-files");
        File linkedOutputTarget = new File(filesDir.getParentFile(), "linked-output-target");
        File linkedOutput = new File(linkedFilesDir, "SLG-Translator-Output");
        File linkedCandidate = new File(linkedOutput, "linked-patched-signed.apk");
        SymlinkAttempt outputSymlink = new SymlinkAttempt(false,
                "could not create linked output directories");
        if ((linkedFilesDir.isDirectory() || linkedFilesDir.mkdirs())
                && (linkedOutputTarget.isDirectory() || linkedOutputTarget.mkdirs())) {
            outputSymlink = tryCreateSymbolicLink(linkedOutput.toPath(), linkedOutputTarget.toPath());
        }
        if (outputSymlink.available) {
            write(linkedCandidate, "linked output");
            assertRejected(new FakeContext(linkedFilesDir), linkedCandidate.getAbsolutePath(),
                    linkedCandidate, "symlinked output directory");
            require(linkedCandidate.exists(), "symlinked output candidate must remain unchanged");
        } else {
            if (symlinkSkipReason.length() > 0) symlinkSkipReason.append("; ");
            symlinkSkipReason.append("symlinked output directory: ").append(outputSymlink.reason);
        }
        if (symlinkSkipReason.length() == 0) {
            System.out.println("SYMLINK_CHECK_ENABLED");
        } else {
            System.out.println("SYMLINK_CHECK_SKIPPED: " + symlinkSkipReason);
        }
    }

    private static CapturingCall call(String path) {
        CapturingCall call = new CapturingCall();
        call.requestedPath = path;
        return call;
    }

    private static void assertRejected(Context context, String path, File unchanged,
                                       String label) throws Exception {
        boolean regularFile = unchanged != null && unchanged.isFile();
        byte[] before = regularFile ? Files.readAllBytes(unchanged.toPath()) : null;
        CapturingCall call = call(path);
        InstallSupport.deletePatchedApk(context, call);
        require(call.rejected != null, label + " must reject");
        require(call.resolved == null, label + " must not resolve");
        if (unchanged != null) {
            require(unchanged.exists(), label + " must remain unchanged");
            if (regularFile) {
                require(unchanged.isFile(), label + " must remain a regular file");
                require(java.util.Arrays.equals(before, Files.readAllBytes(unchanged.toPath())),
                        label + " contents must remain unchanged");
            } else {
                require(unchanged.isDirectory(), label + " must remain a directory");
            }
        }
    }

    static final class SymlinkAttempt {
        final boolean available;
        final String reason;
        SymlinkAttempt(boolean available, String reason) {
            this.available = available;
            this.reason = reason;
        }
    }

    private static SymlinkAttempt tryCreateSymbolicLink(Path link, Path target) {
        try {
            Files.createSymbolicLink(link, target);
            return new SymlinkAttempt(true, "");
        } catch (UnsupportedOperationException unavailable) {
            return new SymlinkAttempt(false, unavailable.toString());
        } catch (java.io.IOException unavailable) {
            return new SymlinkAttempt(false, unavailable.toString());
        } catch (SecurityException unavailable) {
            return new SymlinkAttempt(false, unavailable.toString());
        }
    }

    private static void write(File file, String contents) throws Exception {
        Files.write(file.toPath(), contents.getBytes(StandardCharsets.UTF_8));
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="install-delete-safety-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "InstallDeleteSafetyHarness.java"
            classes = temporary_path / "classes"
            files_dir = temporary_path / "files"
            js_object_stub = temporary_path / "custom-stubs" / "com" / "getcapacitor" / "JSObject.java"
            js_object_stub.parent.mkdir(parents=True)
            js_object_stub.write_text(
                """package com.getcapacitor;

import java.util.HashMap;
import java.util.Map;

public class JSObject {
    private final Map<String, Object> values = new HashMap<>();
    public JSObject put(String key, Object value) { values.put(key, value); return this; }
    public JSObject put(String key, String value) { values.put(key, value); return this; }
    public JSObject put(String key, long value) { values.put(key, value); return this; }
    public JSObject put(String key, int value) { values.put(key, value); return this; }
    public JSObject put(String key, boolean value) { values.put(key, value); return this; }
    public Object get(String key) { return values.get(key); }
}
""",
                "utf-8",
            )
            stubs = [
                path for path in sorted((FAST_SCAN / "stubs").rglob("*.java"))
                if not path.as_posix().endswith("/com/getcapacitor/JSObject.java")
            ]
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            compile_result = subprocess.run(
                [
                    str(JAVAC),
                    "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-d", str(classes),
                    "-classpath", third_party_classpath(),
                    str(js_object_stub),
                    *map(str, stubs),
                    *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                    str(harness_path),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(
                compile_result.returncode,
                0,
                compile_result.stderr.decode("utf-8", "replace"),
            )
            run_result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "InstallDeleteSafetyHarness", str(files_dir)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(run_result.returncode, 0,
                             run_result.stderr)
            if "SYMLINK_CHECK_SKIPPED:" in run_result.stdout:
                self.skipTest(run_result.stdout.strip())
            self.assertIn("SYMLINK_CHECK_ENABLED", run_result.stdout,
                          run_result.stdout + run_result.stderr)

    def test_protocol2_writer_uses_only_python2_compatible_opcodes(self):
        """Protocol-2 output is checked by an independent, non-executing reader."""
        harness = r"""
package com.slgtranslator.app;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.io.ByteArrayOutputStream;
import java.util.zip.DeflaterOutputStream;

public final class Protocol2WriterHarness {
    public static void main(String[] args) {
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"Hello", "你好"});
        pairs.add(new String[]{"Fine.", "很好。"});
        byte[] pickle = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2,
                "slgtranslated", "game/tl/slgtranslated/translations.rpy",
                pairs, 17, "fixture-key");
        try {
            ByteArrayOutputStream raw = new ByteArrayOutputStream();
            DeflaterOutputStream deflated = new DeflaterOutputStream(raw);
            deflated.write(pickle); deflated.finish(); deflated.close();
            RenpyPatchValidator.Result validation = RenpyPatchValidator.validateCompiledRpyc(
                    raw.toByteArray(), 17, "fixture-key", "slgtranslated", pairs.size());
            if (!validation.valid) throw new AssertionError(validation.code + ": " + validation.message);
        } catch (Exception error) {
            throw new AssertionError("protocol-2 fixture must pass the structural validator", error);
        }
        System.out.print(Base64.getEncoder().encodeToString(pickle));
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="protocol2-writer-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "Protocol2WriterHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.Protocol2WriterHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            pickle = __import__("base64").b64decode(result.stdout.strip())

        self.assertEqual(pickle[:2], b"\x80\x02")
        self.assertEqual(pickle[-1:], b".")
        strings = []
        globals_seen = []
        opcodes = []
        position = 0
        while position < len(pickle):
            opcode = pickle[position]
            opcodes.append(opcode)
            position += 1
            if opcode == 0x80:  # PROTO
                self.assertEqual(pickle[position], 2)
                position += 1
            elif opcode == 0x63:  # GLOBAL: module\\nname\\n
                end = pickle.index(b"\n", position)
                module = pickle[position:end]
                end2 = pickle.index(b"\n", end + 1)
                name = pickle[end + 1:end2]
                self.assertNotEqual(module, b"builtins")
                self.assertIn(module, (b"__builtin__", b"collections", b"renpy.ast"))
                globals_seen.append((module.decode("ascii"), name.decode("ascii")))
                position = end2 + 1
            elif opcode == 0x58:  # BINUNICODE
                length = struct.unpack_from("<I", pickle, position)[0]
                position += 4
                payload = pickle[position:position + length]
                self.assertEqual(len(payload), length)
                strings.append(payload.decode("utf-8"))
                position += length
            elif opcode == 0x71:  # BINPUT
                position += 1
            elif opcode == 0x72:  # LONG_BINPUT
                position += 4
            elif opcode == 0x4a:  # BININT
                position += 4
            elif opcode == 0x4b:  # BININT1
                position += 1
            elif opcode == 0x4d:  # BININT2
                position += 2
            elif opcode in (0x28, 0x29, 0x2e, 0x4e, 0x52, 0x5d, 0x62, 0x65,
                            0x75, 0x7d, 0x81, 0x85, 0x86, 0x87):
                pass
            else:
                self.fail("protocol-2 reader saw unsupported opcode 0x%02x" % opcode)
        self.assertNotIn(0x8c, opcodes, "SHORT_BINUNICODE is Python 3 only")
        self.assertNotIn(0x93, opcodes, "STACK_GLOBAL is Python 3 only")
        self.assertIn(b"__builtin__", pickle)
        self.assertNotIn(b"builtins", pickle)
        self.assertIn(("__builtin__", "list"), globals_seen)
        self.assertIn(("renpy.ast", "Init"), globals_seen)
        self.assertIn(("renpy.ast", "TranslateString"), globals_seen)
        self.assertIn(("renpy.ast", "Return"), globals_seen)
        for expected in ("version", "key", "fixture-key", "language", "slgtranslated",
                         "old", "new", "Hello", "你好", "Fine.", "很好。",
                         "newloc", "priority"):
            self.assertIn(expected, strings, "restricted reader must recover %s" % expected)

    def test_modern_writer_is_byte_stable_with_existing_translation_pickle(self):
        """Modern output must match the pre-Task-13 byte-for-byte golden."""
        compiler = (FAST_SCAN / "src" / "com" / "slgtranslator" / "app"
                    / "TranslationCompiler.java")
        self.assertIn("RpycPickleWriter.Dialect.PY3_MODERN", compiler.read_text("utf-8"))
        harness = r"""
package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.List;
import java.util.Base64;

public final class ModernWriterHarness {
    public static void main(String[] args) {
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"Hello", "你好"});
        byte[] delegated = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY3_MODERN, "slgtranslated", "game/t.rpy",
                pairs, 17, "fixture-key");
        System.out.println(Base64.getEncoder().encodeToString(delegated));
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="modern-writer-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "ModernWriterHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), str(DIALOGUE_TRANSLATION), str(PICKLE_WRITER), str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            output = subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.ModernWriterHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ).stdout.splitlines()
        modern = __import__("base64").b64decode(output[0])
        golden = __import__("base64").b64decode(MODERN_PICKLE_GOLDEN_B64)
        self.assertEqual(modern, golden)
        self.assertIn(b"builtins", modern)
        self.assertNotIn(b"__builtin__", modern)
        self.assertIn(b"\x93", modern, "modern output must retain STACK_GLOBAL")
        self.assertIn(b"\x8c", modern, "modern output must retain SHORT_BINUNICODE")

    def test_modern_envelope_gate_rejects_decoys_and_pseudo_stack_global(self):
        """Modern generation requires a real top-level envelope and legal stack globals."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.zip.DeflaterOutputStream;

public final class ModernEnvelopeGateHarness {
    private static byte[] deflate(byte[] value) throws Exception {
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        DeflaterOutputStream out = new DeflaterOutputStream(raw);
        out.write(value); out.finish(); out.close();
        return raw.toByteArray();
    }

    private static byte[] shortString(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x8c); out.write(bytes.length); out.write(bytes, 0, bytes.length);
        return out.toByteArray();
    }

    private static byte[] join(byte[]... parts) {
        int length = 0;
        for (byte[] part : parts) length += part.length;
        byte[] result = new byte[length];
        int offset = 0;
        for (byte[] part : parts) {
            System.arraycopy(part, 0, result, offset, part.length);
            offset += part.length;
        }
        return result;
    }

    private static void requireBlocked(String label, byte[] pickle) throws Exception {
        RpycCompatibility.Report report = RpycCompatibility.inspect(deflate(pickle));
        if (report.canGenerate() || report.isModernEnvelopeVerified()) {
            throw new AssertionError(label + " was promoted: " + report.reason);
        }
        if (report.dialect != RpycCompatibility.ModernDialect.MODERN_GENERIC) {
            throw new AssertionError(label + " dialect mismatch: " + report.dialect);
        }
    }

    public static void main(String[] args) throws Exception {
        byte[] golden = Base64.getDecoder().decode(args[0]);
        RpycCompatibility.Report verified = RpycCompatibility.inspect(deflate(golden));
        if (!verified.isModernEnvelopeVerified() || !verified.canGenerate()) {
            throw new AssertionError("modern golden must pass: " + verified.reason);
        }

        byte[] decoy = join(
                new byte[]{(byte) 0x80, 4, (byte) 0x7d, (byte) 0x28},
                shortString("payload"), shortString("builtins"),
                new byte[]{(byte) 0x75, (byte) 0x2e});
        requireBlocked("decoy strings", decoy);

        byte[] pseudoStackGlobal = join(
                new byte[]{(byte) 0x80, 4},
                shortString("builtins"), shortString("renpy.ast"),
                new byte[]{(byte) 0x4b, 1, (byte) 0x93, (byte) 0x2e});
        requireBlocked("pseudo STACK_GLOBAL", pseudoStackGlobal);

        byte[] nestedThreeKeys = join(
                new byte[]{(byte) 0x80, 4, (byte) 0x7d, (byte) 0x28},
                shortString("nested"), new byte[]{(byte) 0x7d, (byte) 0x28},
                shortString("version"), new byte[]{(byte) 0x4b, 1},
                shortString("key"), shortString("k"),
                shortString("deferred_parse_errors"), shortString("builtins"),
                new byte[]{(byte) 0x75, (byte) 0x73, (byte) 0x75, (byte) 0x2e});
        requireBlocked("nested three-key envelope", nestedThreeKeys);
        System.out.println("OK");
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="modern-envelope-gate-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "ModernEnvelopeGateHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.ModernEnvelopeGateHarness",
                 MODERN_PICKLE_GOLDEN_B64],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        self.assertEqual(result.stdout.strip(), "OK")

    def test_protocol2_generation_support_matrix_is_verified_or_extract_only(self):
        """Only a verified protocol-2 shape may leave the legacy extract-only state."""
        compatibility = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycCompatibility.java"
        self.assertIn("canGenerate", compatibility.read_text("utf-8"))
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.zip.DeflaterOutputStream;

public final class CompatibilityMatrixHarness {
    private static byte[] deflate(byte[] value) throws Exception {
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        DeflaterOutputStream out = new DeflaterOutputStream(raw);
        out.write(value); out.finish(); out.close();
        return raw.toByteArray();
    }
    public static void main(String[] args) throws Exception {
        List<String[]> pairs = new ArrayList<>();
        pairs.add(new String[]{"old", "new"});
        byte[] verified = RpycPickleWriter.buildTranslationPickle(
                RpycPickleWriter.Dialect.PY2_PROTOCOL_2, "slgtranslated", "game/t.rpy",
                pairs, 17, "key");
        RpycCompatibility.Report legacy = RpycCompatibility.inspect(deflate(verified));
        if (!legacy.canGenerate() || !legacy.isProtocol2WriterVerified()
                || legacy.generationSupport
                != RpycCompatibility.GenerationSupport.MODERN_SUPPORTED) {
            throw new AssertionError("verified protocol2 must be writable: " + legacy.reason);
        }
        TranslationCompiler.TemplateMeta meta = new TranslationCompiler.TemplateMeta();
        meta.version = 17;
        meta.key = "key";
        meta.compatibility = legacy;
        byte[] compiled = TranslationCompiler.compileRpyc(
                "slgtranslated", "game/t.rpy", pairs, meta);
        RpycCompatibility.Report compiledReport = RpycCompatibility.inspect(compiled);
        if (!compiledReport.isProtocol2WriterVerified()) {
            throw new AssertionError("compiler must select protocol2 for verified Python2 targets");
        }
        byte[] unknown = new byte[]{(byte) 0x80, 2, (byte) 0x2e};
        RpycCompatibility.Report unknownReport = RpycCompatibility.inspect(deflate(unknown));
        if (unknownReport.canGenerate()
                || unknownReport.generationSupport
                != RpycCompatibility.GenerationSupport.UNKNOWN_EXTRACT_ONLY) {
            throw new AssertionError("unknown pickle must remain extract-only");
        }
        byte[] unverifiedPy2 = concat(
                new byte[]{(byte) 0x80, 2, (byte) 0x63},
                "__builtin__\nunsupported\n.".getBytes("US-ASCII"));
        RpycCompatibility.Report legacyOnly = RpycCompatibility.inspect(deflate(unverifiedPy2));
        if (legacyOnly.canGenerate()
                || legacyOnly.generationSupport
                != RpycCompatibility.GenerationSupport.LEGACY_EXTRACT_ONLY) {
            throw new AssertionError("unverified Python2 pickle must remain extract-only");
        }
        System.out.print(Base64.getEncoder().encodeToString(verified));
    }

    private static byte[] concat(byte[] left, byte[] right) {
        byte[] result = new byte[left.length + right.length];
        System.arraycopy(left, 0, result, 0, left.length);
        System.arraycopy(right, 0, result, left.length, right.length);
        return result;
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="compatibility-matrix-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "CompatibilityMatrixHarness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.CompatibilityMatrixHarness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

    def test_protocol2_adversarial_object_graph_stays_extract_only(self):
        """Names/opcodes alone must not promote a malformed protocol-2 graph."""
        harness = r"""
package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.DeflaterOutputStream;

public final class AdversarialProtocol2Harness {
    private static byte[] bin(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x58); out.write(bytes.length); out.write(0); out.write(0); out.write(0);
        out.write(bytes, 0, bytes.length);
        return out.toByteArray();
    }

    private static byte[] global(String module, String name) {
        byte[] value = (module + "\n" + name + "\n").getBytes(StandardCharsets.US_ASCII);
        byte[] result = new byte[value.length + 1];
        result[0] = 0x63;
        System.arraycopy(value, 0, result, 1, value.length);
        return result;
    }

    private static byte[] join(byte[]... parts) {
        int length = 0;
        for (byte[] part : parts) length += part.length;
        byte[] result = new byte[length];
        int offset = 0;
        for (byte[] part : parts) {
            System.arraycopy(part, 0, result, offset, part.length);
            offset += part.length;
        }
        return result;
    }

    private static byte[] deflate(byte[] value) throws Exception {
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        DeflaterOutputStream out = new DeflaterOutputStream(raw);
        out.write(value); out.finish(); out.close();
        return raw.toByteArray();
    }

    public static void main(String[] args) throws Exception {
        // It contains every recognizable version/key/global name, but omits
        // the required values and object graph ordering. It must not generate.
        byte[] malformed = join(
                new byte[]{(byte) 0x80, 2, (byte) 0x7d, (byte) 0x28},
                bin("version"), bin("key"),
                global("collections", "defaultdict"),
                global("__builtin__", "list"),
                global("renpy.ast", "Init"),
                global("renpy.ast", "TranslateString"),
                global("renpy.ast", "Return"),
                new byte[]{(byte) 0x2e});
        RpycCompatibility.Report report = RpycCompatibility.inspect(deflate(malformed));
        if (report.canGenerate()
                || report.generationSupport
                != RpycCompatibility.GenerationSupport.LEGACY_EXTRACT_ONLY) {
            throw new AssertionError("malformed protocol2 graph was promoted: " + report.reason);
        }
    }
}
"""
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="adversarial-protocol2-test-") as temporary:
            temporary_path = Path(temporary)
            harness_path = temporary_path / "AdversarialProtocol2Harness.java"
            classes = temporary_path / "classes"
            harness_path.write_text(harness, "utf-8")
            classes.mkdir()
            subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs), *map(str, sorted((FAST_SCAN / "src").rglob("*.java"))),
                 str(harness_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.AdversarialProtocol2Harness"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )


if __name__ == "__main__":
    unittest.main()
