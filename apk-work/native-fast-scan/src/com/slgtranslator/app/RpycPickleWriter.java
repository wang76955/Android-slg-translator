package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.DeflaterOutputStream;

/**
 * Writes the small, deliberately bounded pickle subset used by translation
 * RPYC files.  It never serializes arbitrary Java objects and it has an
 * explicit dialect so a Python 2 target cannot accidentally receive a
 * Python 3 opcode stream.
 */
public final class RpycPickleWriter {

    public enum Dialect {
        PY2_PROTOCOL_2,
        PY3_MODERN
    }

    private static final int MAX_PAIRS = 100_000;
    private static final int MAX_STRING_BYTES = 16 * 1024 * 1024;
    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    /** The only TranslateSay shape verified by the Task 15 fixture. */
    public static final int VERIFIED_DIALOGUE_AST_VERSION = 17;

    private RpycPickleWriter() {
    }

    public static byte[] buildTranslationPickle(
            Dialect dialect, String language, String filename,
            List<String[]> pairs, int version, String key) {
        validateInput(dialect, language, filename, pairs, version, key);
        ByteArrayOutputStream out = new ByteArrayOutputStream(4096);
        out.write(0x80); // PROTO
        out.write(0x02);

        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "version");
        writeInt(out, version);
        writeString(out, dialect, "key");
        writeString(out, dialect, key);
        writeString(out, dialect, "deferred_parse_errors");
        writeGlobal(out, dialect, "collections", "defaultdict");
        writeGlobal(out, dialect,
                dialect == Dialect.PY2_PROTOCOL_2 ? "__builtin__" : "builtins", "list");
        out.write(0x85); // TUPLE1
        out.write(0x52); // REDUCE
        out.write(0x75); // SETITEMS

        out.write(0x5d); // EMPTY_LIST (stmts)
        out.write(0x28); // MARK

        writeGlobal(out, dialect, "renpy.ast", "Init");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x81); // NEWOBJ
        out.write(0x4e); // NONE
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "linenumber");
        writeInt(out, 1);
        writeString(out, dialect, "filename");
        writeString(out, dialect, filename);
        writeString(out, dialect, "name");
        writeString(out, dialect, filename);
        writeInt(out, 1784316460);
        writeInt(out, 1416);
        out.write(0x87); // TUPLE3 (name)
        writeString(out, dialect, "next");
        out.write(0x4e); // NONE
        writeString(out, dialect, "block");
        out.write(0x5d); // EMPTY_LIST
        out.write(0x28); // MARK

        int line = 3;
        int serial = 1417;
        for (String[] pair : pairs) {
            writeGlobal(out, dialect, "renpy.ast", "TranslateString");
            out.write(0x29); // EMPTY_TUPLE
            out.write(0x81); // NEWOBJ
            out.write(0x4e); // NONE
            out.write(0x7d); // EMPTY_DICT
            out.write(0x28); // MARK
            writeString(out, dialect, "linenumber");
            writeInt(out, line);
            writeString(out, dialect, "filename");
            writeString(out, dialect, filename);
            writeString(out, dialect, "name");
            writeString(out, dialect, filename);
            writeInt(out, 1784316460);
            writeInt(out, serial++);
            out.write(0x87); // TUPLE3 (name)
            writeString(out, dialect, "next");
            out.write(0x4e); // NONE
            writeString(out, dialect, "language");
            writeNullableString(out, dialect, language);
            writeString(out, dialect, "old");
            writeString(out, dialect, pair[0]);
            writeString(out, dialect, "new");
            writeString(out, dialect, pair[1]);
            writeString(out, dialect, "newloc");
            writeString(out, dialect, filename);
            writeInt(out, line);
            out.write(0x86); // TUPLE2
            out.write(0x75); // SETITEMS
            out.write(0x86); // TUPLE2 state
            out.write(0x62); // BUILD
            if (line > Integer.MAX_VALUE - 2) {
                throw new IllegalArgumentException("translation line number overflow");
            }
            line += 2;
        }
        out.write(0x65); // APPENDS
        writeString(out, dialect, "priority");
        out.write(0x4b); // BININT1
        out.write(0);
        out.write(0x75); // SETITEMS
        out.write(0x86); // TUPLE2
        out.write(0x62); // BUILD

        writeGlobal(out, dialect, "renpy.ast", "Return");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x81); // NEWOBJ
        out.write(0x4e); // NONE
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "linenumber");
        writeInt(out, line);
        writeString(out, dialect, "filename");
        writeString(out, dialect, filename);
        writeString(out, dialect, "expression");
        out.write(0x4e); // NONE
        writeString(out, dialect, "name");
        writeString(out, dialect, filename);
        writeInt(out, 1784316460);
        writeInt(out, serial);
        out.write(0x87); // TUPLE3 (name)
        writeString(out, dialect, "next");
        out.write(0x4e); // NONE
        out.write(0x75); // SETITEMS
        out.write(0x86); // TUPLE2
        out.write(0x62); // BUILD
        out.write(0x65); // APPENDS stmts
        out.write(0x86); // TUPLE2 (data, stmts)
        out.write(0x2e); // STOP
        return out.toByteArray();
    }

    /**
     * Returns whether this writer has a fixture-verified TranslateSay shape
     * for the requested target.  Protocol 2 deliberately remains string-map
     * only until a Python 2 TranslateSay fixture is independently verified.
     */
    public static boolean isDialogueIdWriterVerified(Dialect dialect, int targetVersion) {
        return dialect == Dialect.PY3_MODERN
                && targetVersion == VERIFIED_DIALOGUE_AST_VERSION;
    }

    /**
     * Writes a mixed advanced-mode translation pickle: verified
     * TranslateSay nodes for context-specific dialogue, followed by ordinary
     * TranslateString nodes for menus, names and marked UI strings.
     *
     * This method is intentionally separate from buildTranslationPickle so
     * the default global string-map artifact remains byte-for-byte stable.
     */
    public static byte[] buildDialogueTranslationPickle(
            Dialect dialect, String language, String filename,
            List<RenpyDialogueTranslation> dialoguePairs,
            List<String[]> stringPairs, int version, String key) {
        validateAdvancedInput(dialect, language, filename, dialoguePairs,
                stringPairs, version, key);
        ByteArrayOutputStream out = new ByteArrayOutputStream(4096);
        writeTranslationDocumentStart(out, dialect, version, key);

        writeGlobal(out, dialect, "renpy.ast", "Init");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x81); // NEWOBJ
        out.write(0x4e); // NONE
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "linenumber");
        writeInt(out, 1);
        writeString(out, dialect, "filename");
        writeString(out, dialect, filename);
        writeString(out, dialect, "name");
        writeString(out, dialect, filename);
        writeInt(out, 1784316460);
        writeInt(out, 1416);
        out.write(0x87); // TUPLE3
        writeString(out, dialect, "next");
        out.write(0x4e); // NONE
        writeString(out, dialect, "block");
        out.write(0x5d); // EMPTY_LIST
        out.write(0x28); // MARK

        int line = 3;
        int serial = 1417;
        for (RenpyDialogueTranslation dialogue : dialoguePairs) {
            writeDialogueNode(out, dialect, language, filename, dialogue, line, serial++);
            line = nextLine(line);
        }
        for (String[] pair : stringPairs) {
            writeTranslationStringNode(out, dialect, language, filename,
                    pair[0], pair[1], line, serial++);
            line = nextLine(line);
        }

        out.write(0x65); // APPENDS
        writeString(out, dialect, "priority");
        out.write(0x4b); // BININT1
        out.write(0);
        out.write(0x75); // SETITEMS
        out.write(0x86); // TUPLE2
        out.write(0x62); // BUILD

        writeGlobal(out, dialect, "renpy.ast", "Return");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x81); // NEWOBJ
        out.write(0x4e); // NONE
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "linenumber");
        writeInt(out, line);
        writeString(out, dialect, "filename");
        writeString(out, dialect, filename);
        writeString(out, dialect, "expression");
        out.write(0x4e); // NONE
        writeString(out, dialect, "name");
        writeString(out, dialect, filename);
        writeInt(out, 1784316460);
        writeInt(out, serial);
        out.write(0x87); // TUPLE3
        writeString(out, dialect, "next");
        out.write(0x4e); // NONE
        out.write(0x75); // SETITEMS
        out.write(0x86); // TUPLE2
        out.write(0x62); // BUILD
        out.write(0x65); // APPENDS stmts
        out.write(0x86); // TUPLE2 (data, stmts)
        out.write(0x2e); // STOP
        return out.toByteArray();
    }

    /** Wraps the verified advanced pickle in the minimal two-slot RPC2 container. */
    public static byte[] buildDialogueTranslationRpyc(
            Dialect dialect, String language, String filename,
            List<RenpyDialogueTranslation> dialoguePairs,
            List<String[]> stringPairs, int version, String key) {
        byte[] pickle = buildDialogueTranslationPickle(
                dialect, language, filename, dialoguePairs, stringPairs, version, key);
        byte[] slot = deflate(pickle);
        ByteArrayOutputStream out = new ByteArrayOutputStream(
                RPC2_MAGIC.length + 36 + slot.length * 2);
        out.write(RPC2_MAGIC, 0, RPC2_MAGIC.length);
        int dataStart = RPC2_MAGIC.length + 3 * 12;
        for (int slotId = 1; slotId <= 2; slotId++) {
            writeIntLe(out, slotId);
            writeIntLe(out, dataStart);
            writeIntLe(out, slot.length);
            dataStart += slot.length;
        }
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        writeIntLe(out, 0);
        out.write(slot, 0, slot.length);
        out.write(slot, 0, slot.length);
        return out.toByteArray();
    }

    private static void validateAdvancedInput(
            Dialect dialect, String language, String filename,
            List<RenpyDialogueTranslation> dialoguePairs,
            List<String[]> stringPairs, int version, String key) {
        if (!isDialogueIdWriterVerified(dialect, version)) {
            throw new IllegalArgumentException(
                    "dialogue ID writer is not verified for target AST version " + version);
        }
        if (dialoguePairs == null || stringPairs == null) {
            throw new IllegalArgumentException("advanced translation lists must not be null");
        }
        validateInput(dialect, language, filename, stringPairs, version, key);
        if (dialoguePairs.size() > MAX_PAIRS
                || dialoguePairs.size() + stringPairs.size() > MAX_PAIRS) {
            throw new IllegalArgumentException("too many advanced translation pairs");
        }
        Set<String> identifiers = new HashSet<>();
        for (RenpyDialogueTranslation dialogue : dialoguePairs) {
            if (dialogue == null || !dialogue.isUsableForAdvancedMode()) {
                throw new IllegalArgumentException(
                        "dialogue entry lacks a verified identifier or translation");
            }
            if (!identifiers.add(dialogue.identifier)) {
                throw new IllegalArgumentException(
                        "duplicate dialogue identifier: " + dialogue.identifier);
            }
            validateString(dialogue.identifier, "identifier");
            validateString(dialogue.speakerExpression, "speakerExpression");
            validateString(dialogue.oldText, "old");
            validateString(dialogue.newText, "new");
        }
    }

    private static void writeTranslationDocumentStart(ByteArrayOutputStream out,
                                                       Dialect dialect,
                                                       int version, String key) {
        out.write(0x80); // PROTO
        out.write(0x02);
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "version");
        writeInt(out, version);
        writeString(out, dialect, "key");
        writeString(out, dialect, key);
        writeString(out, dialect, "deferred_parse_errors");
        writeGlobal(out, dialect, "collections", "defaultdict");
        writeGlobal(out, dialect, "builtins", "list");
        out.write(0x85); // TUPLE1
        out.write(0x52); // REDUCE
        out.write(0x75); // SETITEMS
        out.write(0x5d); // EMPTY_LIST (stmts)
        out.write(0x28); // MARK
    }

    private static void writeDialogueNode(ByteArrayOutputStream out, Dialect dialect,
                                           String language, String filename,
                                           RenpyDialogueTranslation dialogue,
                                           int line, int serial) {
        writeGlobal(out, dialect, "renpy.ast", "TranslateSay");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x81); // NEWOBJ
        out.write(0x4e); // NONE
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "linenumber");
        writeInt(out, line);
        writeString(out, dialect, "filename");
        writeString(out, dialect, filename);
        writeString(out, dialect, "name");
        writeString(out, dialect, filename);
        writeInt(out, 1784316460);
        writeInt(out, serial);
        out.write(0x87); // TUPLE3
        writeString(out, dialect, "next");
        out.write(0x4e); // NONE
        writeString(out, dialect, "language");
        writeNullableString(out, dialect, language);
        writeString(out, dialect, "identifier");
        writeString(out, dialect, dialogue.identifier);
        writeString(out, dialect, "who");
        writeNullableString(out, dialect,
                dialogue.speakerExpression.isEmpty() ? null : dialogue.speakerExpression);
        writeString(out, dialect, "what");
        writeString(out, dialect, dialogue.oldText);
        writeString(out, dialect, "new");
        writeString(out, dialect, dialogue.newText);
        writeString(out, dialect, "newloc");
        writeString(out, dialect, filename);
        writeInt(out, line);
        out.write(0x86); // TUPLE2
        out.write(0x75); // SETITEMS
        out.write(0x86); // TUPLE2 state
        out.write(0x62); // BUILD
    }

    private static void writeTranslationStringNode(ByteArrayOutputStream out,
                                                    Dialect dialect, String language,
                                                    String filename, String oldText,
                                                    String newText, int line, int serial) {
        writeGlobal(out, dialect, "renpy.ast", "TranslateString");
        out.write(0x29); // EMPTY_TUPLE
        out.write(0x81); // NEWOBJ
        out.write(0x4e); // NONE
        out.write(0x7d); // EMPTY_DICT
        out.write(0x28); // MARK
        writeString(out, dialect, "linenumber");
        writeInt(out, line);
        writeString(out, dialect, "filename");
        writeString(out, dialect, filename);
        writeString(out, dialect, "name");
        writeString(out, dialect, filename);
        writeInt(out, 1784316460);
        writeInt(out, serial);
        out.write(0x87); // TUPLE3
        writeString(out, dialect, "next");
        out.write(0x4e); // NONE
        writeString(out, dialect, "language");
        writeNullableString(out, dialect, language);
        writeString(out, dialect, "old");
        writeString(out, dialect, oldText);
        writeString(out, dialect, "new");
        writeString(out, dialect, newText);
        writeString(out, dialect, "newloc");
        writeString(out, dialect, filename);
        writeInt(out, line);
        out.write(0x86); // TUPLE2
        out.write(0x75); // SETITEMS
        out.write(0x86); // TUPLE2 state
        out.write(0x62); // BUILD
    }

    private static int nextLine(int line) {
        if (line > Integer.MAX_VALUE - 2) {
            throw new IllegalArgumentException("translation line number overflow");
        }
        return line + 2;
    }

    private static void validateInput(Dialect dialect, String language, String filename,
                                      List<String[]> pairs, int version, String key) {
        if (dialect == null || filename == null || key == null
                || pairs == null) {
            throw new IllegalArgumentException("writer inputs must not be null");
        }
        if (pairs.size() > MAX_PAIRS) {
            throw new IllegalArgumentException("too many translation pairs");
        }
        if (language != null) {
            validateString(language, "language");
        }
        validateString(filename, "filename");
        validateString(key, "key");
        for (String[] pair : pairs) {
            if (pair == null || pair.length != 2 || pair[0] == null || pair[1] == null) {
                throw new IllegalArgumentException("each translation pair must contain two strings");
            }
            validateString(pair[0], "old");
            validateString(pair[1], "new");
        }
        // version is an int by design; the check documents that no wider or
        // arbitrary numeric object can enter the protocol-2 stream.
        if (version == Integer.MIN_VALUE) {
            throw new IllegalArgumentException("unsupported version sentinel");
        }
    }

    private static void validateString(String value, String field) {
        if (value.getBytes(StandardCharsets.UTF_8).length > MAX_STRING_BYTES) {
            throw new IllegalArgumentException(field + " is too large");
        }
    }

    private static void writeGlobal(ByteArrayOutputStream out, Dialect dialect,
                                    String module, String name) {
        if (dialect == Dialect.PY2_PROTOCOL_2) {
            out.write(0x63); // GLOBAL: module\nname\n
            writeAsciiLine(out, module);
            writeAsciiLine(out, name);
            return;
        }
        writeString(out, dialect, module);
        writeString(out, dialect, name);
        out.write(0x93); // STACK_GLOBAL
    }

    private static void writeAsciiLine(ByteArrayOutputStream out, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.US_ASCII);
        out.write(bytes, 0, bytes.length);
        out.write('\n');
    }

    private static void writeString(ByteArrayOutputStream out, Dialect dialect, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        if (dialect == Dialect.PY2_PROTOCOL_2) {
            out.write(0x58); // BINUNICODE, supported by Python 2 protocol 2
            writeIntLe(out, bytes.length);
        } else if (bytes.length <= 255) {
            out.write(0x8c); // SHORT_BINUNICODE
            out.write(bytes.length);
        } else {
            out.write(0x58); // BINUNICODE
            writeIntLe(out, bytes.length);
        }
        out.write(bytes, 0, bytes.length);
    }

    private static void writeNullableString(ByteArrayOutputStream out, Dialect dialect,
                                             String value) {
        if (value == null) {
            out.write(0x4e); // NONE
        } else {
            writeString(out, dialect, value);
        }
    }

    private static void writeInt(ByteArrayOutputStream out, int value) {
        if (value >= 0 && value <= 0xff) {
            out.write(0x4b); // BININT1
            out.write(value);
        } else if (value >= -0x8000 && value <= 0x7fff) {
            out.write(0x4d); // BININT2
            out.write(value & 0xff);
            out.write((value >>> 8) & 0xff);
        } else {
            out.write(0x4a); // BININT
            writeIntLe(out, value);
        }
    }

    private static void writeIntLe(ByteArrayOutputStream out, int value) {
        out.write(value & 0xff);
        out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff);
        out.write((value >>> 24) & 0xff);
    }

    private static byte[] deflate(byte[] data) {
        try {
            ByteArrayOutputStream raw = new ByteArrayOutputStream();
            try (DeflaterOutputStream compressed = new DeflaterOutputStream(raw)) {
                compressed.write(data, 0, data.length);
            }
            return raw.toByteArray();
        } catch (java.io.IOException error) {
            throw new IllegalStateException("failed to deflate advanced translation pickle", error);
        }
    }
}
