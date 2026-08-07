import re
import os
import json
import subprocess
import tempfile
import unittest
import struct
from pathlib import Path
import io
import zipfile


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
GENERATED = FAST_SCAN / "generated"
DEXDUMP = ROOT / ".tools" / "android-15" / "dexdump.exe"
CAPACITOR_DEX = ROOT / "apk-work" / "extracted" / "classes3.dex"
JAVA_HOME = ROOT / ".tools" / "jdk-17" / "jdk-17.0.19+10"
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"

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


def build_rpa3_fixture() -> bytes:
    import pickle
    import zlib
    key = 0x42424242
    content = build_menu_fixture_rpyc()
    header_len = 34
    body = bytearray()
    index = {}
    for name, data in (("game/chapter1.rpyc", content), ("game/notes.txt", b"ignore")):
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
    import zlib
    p = bytearray(b"\x80\x02")
    p += pickle_short("builtins") + pickle_short("list") + b"\x93"
    p += pickle_short("what") + pickle_short("Hello, world!") + b"\x2e"
    slot = zlib.compress(bytes(p))
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


def build_compatibility_unknown_fixture() -> bytes:
    import zlib
    p = bytearray(b"\x80\x05cmystery\nThing\n.")
    return zlib.compress(bytes(p))


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


class FastApkScannerContractTest(unittest.TestCase):
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
            "MAX_CACHE_ENTRIES = 4",
            '"packageName"',
            '"scanDurationMs"',
            '"cacheHit"',
        ):
            self.assertIn(token, source)
        self.assertNotIn("ZipInputStream", source)
        self.assertIn("catch (Throwable error)", source)

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
        ):
            self.assertIn(token, source)
        self.assertNotIn("spliceButton", source)
        builder = BUILDER.read_text("utf-8")
        for token in (
            "INJECT_MENU_SIGNATURE",
            "LanguageMenuSupport;->injectTranslatorMenu",
        ):
            self.assertIn(token, builder)

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

    def test_workshop_patch_propagates_activation_mode_and_guidance(self):
        patcher = ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py"
        source = patcher.read_text("utf-8")
        for token in (
            "window.__slgActivationMode",
            "activationMode:window.__slgActivationMode||'always_on'",
            "window.__slgCompiledPath",
            "window.__slgFontReport",
            "window.__slgFontWarning",
            "window.__slgCompileFailed",
            "fontWarning",
            "always_on",
            r"\u8bf7\u5728\u6e38\u620f\u8bbe\u7f6e\u4e2d\u9009\u62e9\u7ffb\u8bd1\u6587\u672c",
            r"\u6b64\u6e38\u620f\u4e0d\u652f\u6301\u53ef\u9760\u7684\u8bed\u8a00\u83dc\u5355\u6ce8\u5165\uff0c\u4e2d\u6587\u7ffb\u8bd1\u5c06\u5728\u542f\u52a8\u65f6\u9ed8\u8ba4\u542f\u7528\uff0c\u6e38\u620f\u5185\u4e0d\u80fd\u5207\u56de\u539f\u6587",
        ):
            self.assertIn(token, source)

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
                 "com.slgtranslator.app.TemplateMetaHarness", str(apk_path), str(conflict_path)],
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
            unknown_path = temporary_path / "unknown.rpyc"
            harness_path = temporary_path / "RpycCompatibilityHarness.java"
            classes = temporary_path / "classes"
            modern_path.write_bytes(build_compatibility_rpc2_fixture())
            legacy_path.write_bytes(build_compatibility_legacy_fixture())
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
            subprocess.run(
                [str(JAVA), "-cp", str(classes),
                 "com.slgtranslator.app.RpycCompatibilityHarness",
                 str(modern_path), str(legacy_path), str(unknown_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

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

        File apk = new File(args[0]);
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
            put(out, "assets/x-game/x-tl/x-schinese/x-style.rpyc", fixture);
        }
        byte[] cloned = TranslationCompiler.cloneChineseStyleRpyc(apk, "fonts/best.ttf");
        require(cloned != null, "schinese style bucket must be cloneable");
        require(new String(inflate(slot(cloned, 1)), StandardCharsets.UTF_8)
                        .contains("fonts/best.ttf"),
                "schinese clone must apply the best font");

        byte[] unsafe = concat(MAGIC, new byte[]{1, 2, 3});
        require(TranslationCompiler.rewriteChineseStyleFont(unsafe, "fonts/best.ttf") == null,
                "unknown pickle must be rejected, not binary-replaced");
    }

    private static byte[] shortString(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        return concat(new byte[]{(byte) 0x8c, (byte) bytes.length}, bytes);
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
            subprocess.run(
                [str(JAVA), "-cp", str(classes), "com.slgtranslator.app.RenpyStyleFontHarness",
                 str(temporary_path / "fixture.apk")],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

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
        self.assertIn("renpy_font_missing_glyphs: baseline", compiler)
        self.assertIn("codePointsOfTranslations(merged.values())", compiler)

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
import java.io.ByteArrayOutputStream;
import java.util.Arrays;
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

    private static RenpyPreflight.SourceSet source(String menu, String module) throws Exception {
        return new RenpyPreflight.SourceSet(
                "assets/x-game/x-script.rpyc",
                RpycCompatibility.inspect(compressed(module)),
                2, 1, Arrays.asList("english", "schinese"), menu,
                null, 7, 10, 1);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        RenpyCompatibilityReport safe = RenpyPreflight.inspect(null, source("standard", "builtins"));
        require(safe.supportLevel == RenpyCompatibilityReport.SupportLevel.SAFE, "modern standard menu must be SAFE");
        require(safe.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.SELECTABLE_LANGUAGE,
                "modern standard menu must be selectable");

        RenpyCompatibilityReport warning = RenpyPreflight.inspect(null, source("none", "builtins"));
        require(warning.supportLevel == RenpyCompatibilityReport.SupportLevel.WARNING, "no menu must be WARNING");
        require(warning.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.ALWAYS_ON,
                "no menu must be always-on");

        RenpyCompatibilityReport legacy = RenpyPreflight.inspect(null, source("standard", "__builtin__"));
        require(legacy.supportLevel == RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY,
                "python2 writer gap must be extract-only");
        require(legacy.activationStrategy == RenpyCompatibilityReport.ActivationStrategy.NONE,
                "extract-only must not activate a writer strategy");
        require(legacy.issues.size() > 0, "legacy report must carry a stable issue");
        String sanitized = safe.toSanitizedJson();
        require(sanitized.contains("templatePath"), "sanitized report must contain diagnostics");
        require(!sanitized.contains("apiKey") && !sanitized.contains("apkBytes")
                && !sanitized.contains("fullScript"), "sanitized report must not contain secrets or APK contents");
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
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

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

    def test_renpy_extract_only_compatibility_gate_blocks_before_model(self):
        """EXTRACT_ONLY must fail closed before either model branch, not merely change the label."""
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        start = source.index("if(window.__slgRenpyMenuType===`renpy`&&!window.__slgRenpyCompatibilityPreflightDone)")
        end = source.index("window.__slgRenpyCompatibilityPreflightDone=true", start)
        block = source[start:end]
        self.assertIn("_cr.supportLevel===`EXTRACT_ONLY`", block)
        self.assertIn("window.__slgRenpyCompatibilityGate===`extract_only`", block)
        self.assertIn("ce(!1);return", block)
        blocked_branch = block.index("if(window.__slgRenpyCompatibilityBlocked)")
        self.assertLess(block.index("EXTRACT_ONLY"), blocked_branch)
        self.assertLess(source.index("__slgRenpyCompatibilityPreflightDone"), source.index("async function Vo"))

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

    def test_local_llm_placeholder_guard_preserves_markup_and_format(self):
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
        require(RenpyTextValidator.validate("{b}{i}x{/b}{/i}", "{b}{i}x{/b}{/i}").codes.contains("tag_misnested"),
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
        for token in ("readRenpyTexts", "RpycTextExtractor.extractRecords", "RPYC_STRING\\t"):
            self.assertIn(token, scanner)
        builder = BUILDER.read_text("utf-8")
        for token in ("READ_TEXTS_SIGNATURE", "FastApkScanner;->readRenpyTexts"):
            self.assertIn(token, builder)

    def test_rpyc_extractor_keeps_menu_choices_and_single_token_labels(self):
        extractor = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "RpycTextExtractor.java"
        source = extractor.read_text("utf-8")
        for token in (
            "itemsMode", "afterTuple3", "isChoiceLabel", "0x87", "TUPLE3",
            "items\".equals(lastKey)", 
        ):
            self.assertIn(token, source)
        scanner = SCANNER.read_text("utf-8")
        for token in ('replace("\\n", "\\\\n")', 'RPYC_STRING\\t'):
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
        for token in ('"renpyRecords"', 'result.put("content", content)', 'RPYC_STRING\\t'):
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
        """The RPYC_STRING bridge must not conflate literal backslash-n with a real newline."""
        scanner = FAST_SCAN / "src" / "com" / "slgtranslator" / "app" / "FastApkScanner.java"
        source = scanner.read_text("utf-8")
        escape_start = source.index("String escaped = text.replace")
        escape_block = source[escape_start:escape_start + 500]
        backslash_idx = escape_block.index('text.replace("\\\\", "\\\\\\\\")')
        newline_idx = escape_block.index('.replace("\\n", "\\\\n")')
        self.assertLess(backslash_idx, newline_idx, "backslash must be escaped before newline")

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
        File source = new File(args[0]);
        try (FileOutputStream out = new FileOutputStream(source)) {
            out.write(new byte[131072]);
        }
        FakeContext context = new FakeContext();
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
            source = temporary_path / "patch.apk"
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
                [str(JAVA), "-cp", str(classes), "InstallSaveFailureHarness", str(source)],
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
