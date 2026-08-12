package com.slgtranslator.app;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Streaming opcode reader for one RPYC slot. It deliberately avoids the
 * materialized opcode list used by the legacy small-input compatibility path.
 */
public final class RpycStreamingExtractor {
    private static final int MAX_LINE_BYTES = 4096;

    private RpycStreamingExtractor() {
    }

    public static List<RenpyTextRecord> extractRecords(
            RpycSlotSource source, String sourcePath, boolean onlyOld) throws IOException {
        RpycTextExtractor.ExtractState state = new RpycTextExtractor.ExtractState(sourcePath, onlyOld);
        InputStream input = source.openInflatedSlot(2);
        if (input == null) {
            input = source.openInflatedSlot(1);
        }
        if (input == null) {
            return state.records;
        }
        try (InputStream stream = input) {
            readPickle(stream, state);
        }
        for (String choice : state.choices) {
            state.addRecord(choice, RenpyTextRecord.Kind.MENU, "", true);
        }
        return state.records;
    }

    private static void readPickle(InputStream input, RpycTextExtractor.ExtractState state)
            throws IOException {
        Map<Integer, String> memo = new HashMap<>();
        int memoTrack = 0;
        while (true) {
            int code = input.read();
            if (code < 0 || code == 0x2e) {
                return;
            }
            switch (code) {
                case 0x80: // PROTO
                    readFully(input, 1);
                    break;
                case 0x95: // FRAME
                    readFully(input, 8);
                    break;
                case 0x81: // NEWOBJ
                    state.beginObject();
                    break;
                case 0x4b: // BININT1
                    state.consumeInteger(readUnsignedByte(input));
                    break;
                case 0x4d: // BININT2
                    state.consumeInteger(readUnsignedShort(input));
                    break;
                case 0x4a: // BININT
                    state.consumeInteger(readInt(input));
                    break;
                case 0x8c: // SHORT_BINUNICODE
                    state.consumeString(readString(input, readUnsignedByte(input)));
                    break;
                case 0x58: { // BINUNICODE
                    int length = readInt(input);
                    if (length < 0) {
                        throw new IOException("renpy_invalid_range: negative BINUNICODE length");
                    }
                    state.consumeString(readString(input, length));
                    break;
                }
                case 0x68: { // BINGET
                    String value = memo.get(readUnsignedByte(input));
                    if (value != null) {
                        state.consumeString(value);
                    }
                    break;
                }
                case 0x6a: { // LONG_BINGET
                    String value = memo.get(readInt(input));
                    if (value != null) {
                        state.consumeString(value);
                    }
                    break;
                }
                case 0x71: // BINPUT
                    if (state.lastString != null) {
                        memo.put(readUnsignedByte(input), state.lastString);
                    } else {
                        readFully(input, 1);
                    }
                    break;
                case 0x72: // LONG_BINPUT
                    if (state.lastString != null) {
                        memo.put(readInt(input), state.lastString);
                    } else {
                        readFully(input, 4);
                    }
                    break;
                case 0x94: // MEMOIZE
                    if (state.lastString != null) {
                        memo.put(memoTrack, state.lastString);
                    }
                    memoTrack++;
                    break;
                case 0x75: // SETITEMS
                case 0x65: // APPENDS
                case 0x61: // APPEND
                case 0x73: // SETITEM
                case 0x31: // POP_MARK
                    state.lastKey = null;
                    break;
                case 0x62: // BUILD
                    state.lastKey = null;
                    state.pyCodeObject = false;
                    break;
                case 0x87: // TUPLE3
                    state.afterTuple3 = true;
                    break;
                case 0x4e: // NONE
                case 0x28: // MARK
                case 0x29: // EMPTY_TUPLE
                case 0x30: // POP
                case 0x32: // DUP
                case 0x52: // REDUCE
                case 0x5d: // EMPTY_LIST
                case 0x7d: // EMPTY_DICT
                case 0x64: // DICT
                case 0x6c: // LIST
                case 0x6f: // OBJ
                case 0x74: // TUPLE
                case 0x85: // TUPLE1
                case 0x86: // TUPLE2
                case 0x88: // NEWTRUE
                case 0x89: // NEWFALSE
                case 0x8f: // EMPTY_SET
                case 0x90: // ADDITEMS
                case 0x91: // FROZENSET
                case 0x92: // NEWOBJ_EX
                case 0x93: // STACK_GLOBAL
                case 0x51: // BINPERSID
                    break;
                case 0x63: // GLOBAL
                case 0x69: // INST
                    readLine(input);
                    readLine(input);
                    break;
                case 0x49: // INT
                case 0x4c: // LONG
                case 0x53: // STRING
                case 0x56: // UNICODE
                case 0x46: // FLOAT
                case 0x67: // GET
                case 0x70: // PUT
                case 0x50: // PERSID
                    readLine(input);
                    break;
                case 0x54: // BINSTRING
                case 0x42: // BINBYTES
                case 0x8b: // LONG4
                    skipLengthPayload(input, readInt(input));
                    break;
                case 0x55: // SHORT_BINSTRING
                case 0x43: // SHORT_BINBYTES
                case 0x8a: // LONG1
                    skipLengthPayload(input, readUnsignedByte(input));
                    break;
                case 0x8d: // BINUNICODE8
                case 0x8e: // BINBYTES8
                case 0x96: // BYTEARRAY8
                    skipLengthPayload(input, readLong(input));
                    break;
                case 0x47: // BINFLOAT
                    readFully(input, 8);
                    break;
                case 0x82: // EXT1
                    readFully(input, 1);
                    break;
                case 0x83: // EXT2
                    readFully(input, 2);
                    break;
                case 0x84: // EXT4
                    readFully(input, 4);
                    break;
                default:
                    throw new IOException(String.format(
                            "renpy_pickle_unknown_opcode: 0x%02x", code));
            }
            RenpyResourceLimits.checkInterrupted();
        }
    }

    private static String readString(InputStream input, int length) throws IOException {
        RenpyResourceLimits.checkTextLength(length);
        byte[] value = new byte[length];
        readFully(input, value, 0, length);
        return new String(value, StandardCharsets.UTF_8);
    }

    private static void skipLengthPayload(InputStream input, long length) throws IOException {
        if (length < 0) {
            throw new IOException("renpy_invalid_range: negative pickle payload length");
        }
        long remaining = length;
        byte[] buffer = new byte[8192];
        while (remaining > 0) {
            int wanted = (int) Math.min((long) buffer.length, remaining);
            int read = input.read(buffer, 0, wanted);
            if (read < 0) {
                throw new IOException("renpy_pickle_truncated: payload ended early");
            }
            remaining -= read;
        }
    }

    private static String readLine(InputStream input) throws IOException {
        byte[] buffer = new byte[MAX_LINE_BYTES];
        int length = 0;
        while (length < buffer.length) {
            int value = input.read();
            if (value < 0 || value == '\n') {
                return new String(buffer, 0, length, StandardCharsets.US_ASCII);
            }
            buffer[length++] = (byte) value;
        }
        throw new IOException("renpy_pickle_line_limit: pickle line is too long");
    }

    private static int readUnsignedByte(InputStream input) throws IOException {
        int value = input.read();
        if (value < 0) {
            throw new IOException("renpy_pickle_truncated: missing byte");
        }
        return value & 0xff;
    }

    private static int readUnsignedShort(InputStream input) throws IOException {
        return readUnsignedByte(input) | (readUnsignedByte(input) << 8);
    }

    private static int readInt(InputStream input) throws IOException {
        return readUnsignedByte(input)
                | (readUnsignedByte(input) << 8)
                | (readUnsignedByte(input) << 16)
                | (readUnsignedByte(input) << 24);
    }

    private static long readLong(InputStream input) throws IOException {
        long value = 0;
        for (int shift = 0; shift < 64; shift += 8) {
            value |= ((long) readUnsignedByte(input)) << shift;
        }
        return value;
    }

    private static void readFully(InputStream input, int length) throws IOException {
        if (length < 0) {
            throw new IOException("renpy_invalid_range: negative read length");
        }
        byte[] buffer = new byte[Math.min(length, 8192)];
        int remaining = length;
        while (remaining > 0) {
            int read = input.read(buffer, 0, Math.min(buffer.length, remaining));
            if (read < 0) {
                throw new IOException("renpy_pickle_truncated: missing payload");
            }
            remaining -= read;
        }
    }

    private static void readFully(InputStream input, byte[] buffer, int offset, int length)
            throws IOException {
        int remaining = length;
        int position = offset;
        while (remaining > 0) {
            int read = input.read(buffer, position, remaining);
            if (read < 0) {
                throw new IOException("renpy_pickle_truncated: missing string payload");
            }
            position += read;
            remaining -= read;
        }
    }
}
