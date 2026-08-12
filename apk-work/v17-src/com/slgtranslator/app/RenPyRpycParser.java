package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.zip.DataFormatException;
import java.util.zip.Inflater;

/** Protocol-aware Ren'Py RPC2 and pickle string extractor. */
public final class RenPyRpycParser {
    public static final RenPyRpycParser INSTANCE = new RenPyRpycParser();

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    private static final int MAX_STRING_BYTES = 8 * 1024 * 1024;
    private static final int MAX_INFLATED_BYTES = 128 * 1024 * 1024;

    private RenPyRpycParser() {}

    public String parseRpyc(byte[] data) {
        LinkedHashSet<String> strings = new LinkedHashSet<>();
        List<String> diagnostics = new ArrayList<>();
        int protocol = -1;
        int slots = 0;
        boolean structured = false;

        try {
            List<byte[]> payloads = extractPayloads(data, diagnostics);
            slots = payloads.size();
            for (byte[] payload : payloads) {
                PickleResult result = parsePickle(payload);
                protocol = Math.max(protocol, result.protocol);
                strings.addAll(result.strings);
                structured |= result.validOpcodes > 0;
                diagnostics.add("payload=" + payload.length + ",opcodes=" + result.validOpcodes
                        + ",invalid=" + result.invalidOpcodes);
            }
        } catch (Exception error) {
            diagnostics.add("structured_error=" + safeMessage(error));
        }

        if (!structured || strings.isEmpty()) {
            int before = strings.size();
            fallbackScan(data, strings);
            diagnostics.add("fallback_added=" + (strings.size() - before));
        }

        StringBuilder output = new StringBuilder();
        output.append("RPYC_DIAG\tformat=")
                .append(startsWith(data, RPC2_MAGIC) ? "RPC2" : "raw")
                .append(",protocol=").append(protocol)
                .append(",slots=").append(slots)
                .append(",strings=").append(strings.size())
                .append('\n');
        for (String diagnostic : diagnostics) {
            output.append("RPYC_DIAG\t").append(diagnostic).append('\n');
        }
        for (String value : strings) {
            String normalized = normalize(value);
            if (!normalized.isEmpty()) {
                output.append("RPYC_STRING\t").append(normalized).append('\n');
            }
        }
        return output.toString();
    }

    private static List<byte[]> extractPayloads(byte[] data, List<String> diagnostics)
            throws DataFormatException {
        List<byte[]> payloads = new ArrayList<>();
        if (!startsWith(data, RPC2_MAGIC)) {
            payloads.add(data);
            diagnostics.add("raw_payload=1");
            return payloads;
        }

        int table = RPC2_MAGIC.length;
        int records = 0;
        while (table + 12 <= data.length && records < 4096) {
            long slot = u32(data, table);
            long offset = u32(data, table + 4);
            long length = u32(data, table + 8);
            table += 12;
            records++;
            if (slot == 0) break;
            if (offset < 0 || length <= 0 || offset + length > data.length) {
                diagnostics.add("invalid_slot=" + slot + ",offset=" + offset + ",length=" + length);
                continue;
            }
            byte[] compressed = slice(data, (int) offset, (int) length);
            try {
                byte[] inflated = inflate(compressed);
                payloads.add(inflated);
                diagnostics.add("slot=" + slot + ",compressed=" + length + ",inflated=" + inflated.length);
            } catch (DataFormatException error) {
                diagnostics.add("slot_error=" + slot + ":" + safeMessage(error));
            }
        }
        if (payloads.isEmpty()) throw new DataFormatException("RPC2 contained no readable slots");
        return payloads;
    }

    private static PickleResult parsePickle(byte[] data) {
        PickleResult result = new PickleResult();
        int index = 0;
        while (index < data.length) {
            int opcode = data[index] & 0xff;
            int start = index++;
            try {
                switch (opcode) {
                    case 0x80: // PROTO
                        require(data, index, 1);
                        result.protocol = Math.max(result.protocol, data[index] & 0xff);
                        index += 1;
                        break;
                    case 0x95: // FRAME
                        require(data, index, 8);
                        index += 8;
                        break;
                    case 'X': // BINUNICODE
                        index = readSizedString(data, index, 4, StandardCharsets.UTF_8, result);
                        break;
                    case 0x8c: // SHORT_BINUNICODE
                        index = readSizedString(data, index, 1, StandardCharsets.UTF_8, result);
                        break;
                    case 0x8d: // BINUNICODE8
                        index = readSizedString(data, index, 8, StandardCharsets.UTF_8, result);
                        break;
                    case 'U': // SHORT_BINSTRING
                        index = readSizedString(data, index, 1, StandardCharsets.ISO_8859_1, result);
                        break;
                    case 'T': // BINSTRING
                        index = readSizedString(data, index, 4, StandardCharsets.ISO_8859_1, result);
                        break;
                    case 'S': // STRING
                        Line line = readLine(data, index);
                        addString(result.strings, unquote(new String(data, index, line.end - index,
                                StandardCharsets.ISO_8859_1)));
                        index = line.next;
                        break;
                    case 'V': // UNICODE
                        line = readLine(data, index);
                        addString(result.strings, decodeRawUnicode(data, index, line.end - index));
                        index = line.next;
                        break;
                    case 'B': // BINBYTES
                        index = skipSized(data, index, 4);
                        break;
                    case 'C': // SHORT_BINBYTES
                        index = skipSized(data, index, 1);
                        break;
                    case 0x8e: // BINBYTES8
                    case 0x96: // BYTEARRAY8
                        index = skipSized(data, index, 8);
                        break;
                    case 'F': case 'I': case 'L': case 'P': case 'g': case 'p':
                        index = readLine(data, index).next;
                        break;
                    case 'c': case 'i': // GLOBAL / INST: module and name
                        index = readLine(data, index).next;
                        index = readLine(data, index).next;
                        break;
                    case 'G':
                        require(data, index, 8); index += 8; break;
                    case 'J': case 'j': case 'r': case 0x84:
                        require(data, index, 4); index += 4; break;
                    case 'M': case 0x83:
                        require(data, index, 2); index += 2; break;
                    case 'K': case 'h': case 'q': case 0x82:
                        require(data, index, 1); index += 1; break;
                    case 0x8a: // LONG1
                        require(data, index, 1);
                        index = checkedAdvance(data, index + 1, data[index] & 0xff);
                        break;
                    case 0x8b: // LONG4
                        require(data, index, 4);
                        long longLength = u32(data, index);
                        index = checkedAdvance(data, index + 4, checkedLength(longLength));
                        break;
                    default:
                        if (!isArgumentlessOpcode(opcode)) throw new PickleException("unknown opcode 0x"
                                + Integer.toHexString(opcode) + " at " + start);
                }
                result.validOpcodes++;
            } catch (PickleException error) {
                result.invalidOpcodes++;
                // Resynchronize one byte after the candidate instead of trusting a bogus length.
                index = start + 1;
            }
        }
        return result;
    }

    private static boolean isArgumentlessOpcode(int opcode) {
        switch (opcode) {
            case '(': case '.': case '0': case '1': case '2': case 'N': case 'Q':
            case 'R': case 'a': case 'b': case 'd': case '}': case 'e': case 'l':
            case ']': case 'o': case 's': case 't': case ')': case 'u': case 0x81:
            case 0x85: case 0x86: case 0x87: case 0x88: case 0x89: case 0x8f:
            case 0x90: case 0x91: case 0x92: case 0x93: case 0x94: case 0x97:
            case 0x98:
                return true;
            default:
                return false;
        }
    }

    private static int readSizedString(byte[] data, int lengthOffset, int width,
                                       Charset charset, PickleResult result) throws PickleException {
        long length = readLength(data, lengthOffset, width);
        int size = checkedLength(length);
        int valueOffset = lengthOffset + width;
        require(data, valueOffset, size);
        addString(result.strings, new String(data, valueOffset, size, charset));
        return valueOffset + size;
    }

    private static int skipSized(byte[] data, int lengthOffset, int width) throws PickleException {
        long length = readLength(data, lengthOffset, width);
        int size = checkedLength(length);
        return checkedAdvance(data, lengthOffset + width, size);
    }

    private static long readLength(byte[] data, int offset, int width) throws PickleException {
        require(data, offset, width);
        if (width == 1) return data[offset] & 0xffL;
        if (width == 4) return u32(data, offset);
        long value = 0;
        for (int i = 0; i < 8; i++) {
            int part = data[offset + i] & 0xff;
            if (i >= 4 && part != 0) throw new PickleException("64-bit length too large");
            value |= (long) part << (8 * i);
        }
        return value;
    }

    private static void fallbackScan(byte[] data, LinkedHashSet<String> output) {
        for (int index = 0; index < data.length; index++) {
            int opcode = data[index] & 0xff;
            int width = opcode == 'X' ? 4 : opcode == 0x8c || opcode == 'U' ? 1 : 0;
            if (width == 0) continue;
            try {
                long length = readLength(data, index + 1, width);
                int size = checkedLength(length);
                int valueOffset = index + 1 + width;
                require(data, valueOffset, size);
                String value = new String(data, valueOffset, size,
                        opcode == 'U' ? StandardCharsets.ISO_8859_1 : StandardCharsets.UTF_8);
                addString(output, value);
                index = valueOffset + size - 1;
            } catch (PickleException ignored) {
                // Keep scanning from the next byte.
            }
        }
    }

    private static void addString(LinkedHashSet<String> output, String value) {
        if (value == null) return;
        String normalized = normalize(value);
        if (!normalized.isEmpty()) output.add(normalized);
    }

    private static String normalize(String value) {
        return value.replace("\r\n", "\\n").replace('\r', '\n').replace("\n", "\\n").trim();
    }

    private static String unquote(String value) {
        String trimmed = value.trim();
        if (trimmed.length() >= 2) {
            char first = trimmed.charAt(0);
            char last = trimmed.charAt(trimmed.length() - 1);
            if ((first == '\'' && last == '\'') || (first == '"' && last == '"')) {
                trimmed = trimmed.substring(1, trimmed.length() - 1);
            }
        }
        return trimmed.replace("\\n", "\n").replace("\\r", "\r")
                .replace("\\t", "\t").replace("\\\"", "\"").replace("\\'", "'")
                .replace("\\\\", "\\");
    }

    private static String decodeRawUnicode(byte[] data, int offset, int length) {
        String raw = new String(data, offset, length, StandardCharsets.ISO_8859_1);
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (c == '\\' && i + 5 < raw.length() && raw.charAt(i + 1) == 'u') {
                try {
                    out.append((char) Integer.parseInt(raw.substring(i + 2, i + 6), 16));
                    i += 5;
                    continue;
                } catch (NumberFormatException ignored) {}
            }
            out.append(c);
        }
        return out.toString();
    }

    private static byte[] inflate(byte[] input) throws DataFormatException {
        Inflater inflater = new Inflater();
        inflater.setInput(input);
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        try {
            while (!inflater.finished()) {
                int count = inflater.inflate(buffer);
                if (count > 0) {
                    output.write(buffer, 0, count);
                    if (output.size() > MAX_INFLATED_BYTES) {
                        throw new DataFormatException("inflated payload exceeds safety limit");
                    }
                } else if (inflater.needsDictionary()) {
                    throw new DataFormatException("zlib dictionary required");
                } else if (inflater.needsInput()) {
                    break;
                } else {
                    throw new DataFormatException("zlib stream made no progress");
                }
            }
            return output.toByteArray();
        } finally {
            inflater.end();
        }
    }

    private static int checkedLength(long length) throws PickleException {
        if (length < 0 || length > MAX_STRING_BYTES) throw new PickleException("invalid length " + length);
        return (int) length;
    }

    private static int checkedAdvance(byte[] data, int offset, int amount) throws PickleException {
        require(data, offset, amount);
        return offset + amount;
    }

    private static void require(byte[] data, int offset, int amount) throws PickleException {
        if (offset < 0 || amount < 0 || offset > data.length - amount) {
            throw new PickleException("out of bounds");
        }
    }

    private static long u32(byte[] data, int offset) {
        return (data[offset] & 0xffL) | ((data[offset + 1] & 0xffL) << 8)
                | ((data[offset + 2] & 0xffL) << 16) | ((data[offset + 3] & 0xffL) << 24);
    }

    private static byte[] slice(byte[] data, int offset, int length) {
        byte[] result = new byte[length];
        System.arraycopy(data, offset, result, 0, length);
        return result;
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data == null || data.length < prefix.length) return false;
        for (int i = 0; i < prefix.length; i++) if (data[i] != prefix[i]) return false;
        return true;
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? error.getClass().getSimpleName() : message.replace('\n', ' ');
    }

    private static final class PickleResult {
        final LinkedHashSet<String> strings = new LinkedHashSet<>();
        int protocol = -1;
        int validOpcodes;
        int invalidOpcodes;
    }

    private static final class Line {
        final int end;
        final int next;
        Line(int end, int next) { this.end = end; this.next = next; }
    }

    private static Line readLine(byte[] data, int offset) throws PickleException {
        for (int i = offset; i < data.length; i++) {
            if (data[i] == '\n') return new Line(i, i + 1);
        }
        throw new PickleException("unterminated line");
    }

    private static final class PickleException extends Exception {
        PickleException(String message) { super(message); }
    }
}
