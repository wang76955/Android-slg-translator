package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

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
}
