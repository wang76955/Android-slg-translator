package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.zip.InflaterInputStream;

/**
 * Read-only capability inspection for Ren'Py compiled scripts.
 *
 * <p>This class deliberately does not execute pickle data, instantiate a
 * Python/Ren'Py class, or deserialize an arbitrary Java object. It only reads
 * the RPYC container, the pickle protocol byte, and the small set of global
 * module names that the local writer knows how to emit.</p>
 */
public final class RpycCompatibility {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    public enum ModernDialect {
        MODERN_ENVELOPE_VERIFIED,
        MODERN_GENERIC,
        LEGACY_PROTOCOL2,
        UNKNOWN
    }

    public enum GenerationSupport {
        MODERN_SUPPORTED,
        /** A standard Ren'Py Python 2 template can use the bounded protocol-2 writer. */
        LEGACY_PROTOCOL2_SUPPORTED,
        LEGACY_EXTRACT_ONLY,
        UNKNOWN_EXTRACT_ONLY
    }

    public static final class Report {
        public final String container;
        public final int preferredSlot;
        public final int pickleProtocol;
        public final boolean usesBuiltins;
        public final boolean usesPy2Builtins;
        public final GenerationSupport generationSupport;
        public final String reason;
        public final ModernDialect dialect;

        Report(String container, int preferredSlot, int pickleProtocol,
               boolean usesBuiltins, boolean usesPy2Builtins,
               GenerationSupport generationSupport, String reason,
               ModernDialect dialect) {
            this.container = container;
            this.preferredSlot = preferredSlot;
            this.pickleProtocol = pickleProtocol;
            this.usesBuiltins = usesBuiltins;
            this.usesPy2Builtins = usesPy2Builtins;
            this.generationSupport = generationSupport;
            this.reason = reason;
            this.dialect = dialect;
        }

        /** True only when the local writer has a verified dialect for this report. */
        public boolean canGenerate() {
            return isModernEnvelopeVerified() || isProtocol2WriterCompatible();
        }

        /** True only when the complete modern top-level envelope is verified. */
        public boolean isModernEnvelopeVerified() {
            return dialect == ModernDialect.MODERN_ENVELOPE_VERIFIED;
        }

        /** True only for the structurally verified Python 2 protocol-2 shape. */
        public boolean isProtocol2WriterVerified() {
            return dialect == ModernDialect.LEGACY_PROTOCOL2
                    && "legacy_protocol2_writer_verified".equals(reason)
                    && pickleProtocol == 2 && usesPy2Builtins && !usesBuiltins;
        }

        /** True when generated translation files must use the Python 2 protocol-2 dialect. */
        public boolean isProtocol2WriterCompatible() {
            return isProtocol2WriterVerified()
                    || (dialect == ModernDialect.LEGACY_PROTOCOL2
                    && generationSupport == GenerationSupport.LEGACY_PROTOCOL2_SUPPORTED);
        }
    }

    private RpycCompatibility() {
    }

    /**
     * Inspects one RPYC byte array without invoking a pickle interpreter.
     * Slot 2 is preferred for RPC2 because it is the current compiled payload;
     * slot 1 is retained for old containers and for incomplete RPC2 files.
     */
    public static Report inspect(byte[] rpyc) {
        if (rpyc == null || rpyc.length == 0) {
            return invalid("legacy-zlib", 1);
        }

        boolean rpc2 = startsWith(rpyc, RPC2_MAGIC);
        String container = rpc2 ? "rpc2" : "legacy-zlib";
        int preferredSlot = rpc2 ? 2 : 1;
        byte[] pickle = null;
        if (rpc2) {
            pickle = inflateRpc2Slot(rpyc, 2);
            if (pickle == null) {
                preferredSlot = 1;
                pickle = inflateRpc2Slot(rpyc, 1);
            }
        } else {
            pickle = inflate(rpyc, 0, rpyc.length);
        }
        if (pickle == null || pickle.length == 0) {
            return invalid(container, preferredSlot);
        }

        int protocol = pickleProtocol(pickle);
        boolean usesBuiltins = containsGlobalName(pickle, "builtins");
        boolean usesPy2Builtins = containsGlobalName(pickle, "__builtin__");
        GenerationSupport support;
        String reason;
        ModernDialect dialect;
        if (isVerifiedProtocol2(pickle, protocol, usesBuiltins, usesPy2Builtins)) {
            support = GenerationSupport.MODERN_SUPPORTED;
            reason = "legacy_protocol2_writer_verified";
            dialect = ModernDialect.LEGACY_PROTOCOL2;
        } else if (protocol == 2 && usesPy2Builtins && !usesBuiltins
                && hasLegacyScriptEnvelope(pickle)) {
            // A real legacy Ren'Py template does not have to match the small
            // translation fixture emitted by our writer. It only needs the
            // standard AST roots that the generated TranslateString document
            // will instantiate. Keep malformed/minimal Python 2 pickles
            // extract-only and select the bounded protocol-2 writer here.
            support = GenerationSupport.LEGACY_PROTOCOL2_SUPPORTED;
            reason = "legacy_protocol2_engine_compatible";
            dialect = ModernDialect.LEGACY_PROTOCOL2;
        } else if (usesPy2Builtins) {
            support = GenerationSupport.LEGACY_EXTRACT_ONLY;
            reason = "legacy_pickle_writer_required";
            dialect = ModernDialect.UNKNOWN;
        } else if (usesBuiltins) {
            ModernEnvelopeInspection inspection = ModernEnvelopeReader.inspect(pickle);
            boolean verified = inspection.isVerified;
            support = verified ? GenerationSupport.MODERN_SUPPORTED
                    : GenerationSupport.UNKNOWN_EXTRACT_ONLY;
            reason = verified ? "modern_envelope_verified"
                    : "modern_envelope_unverified:" + inspection.reason;
            dialect = verified ? ModernDialect.MODERN_ENVELOPE_VERIFIED
                    : ModernDialect.MODERN_GENERIC;
        } else {
            support = GenerationSupport.UNKNOWN_EXTRACT_ONLY;
            reason = "unknown_pickle_globals";
            dialect = ModernDialect.UNKNOWN;
        }
        return new Report(container, preferredSlot, protocol, usesBuiltins,
                usesPy2Builtins, support, reason, dialect);
    }

    /**
     * Verifies the complete object graph emitted by the restricted Python 2
     * writer. This reader is deliberately grammar-based: it consumes every
     * opcode and field in order, never imports or executes a GLOBAL target,
     * and only returns true at an exact STOP/EOF boundary.
     */
    private static boolean isVerifiedProtocol2(byte[] pickle, int protocol,
                                               boolean usesBuiltins,
                                               boolean usesPy2Builtins) {
        if (protocol != 2 || usesBuiltins || !usesPy2Builtins) {
            return false;
        }
        return new Protocol2Reader(pickle).verify();
    }

    private static final class Protocol2Reader {
        private static final int MAGIC = 1784316460;
        private static final int MAX_STRING_BYTES = 16 * 1024 * 1024;
        private final byte[] data;
        private int position;
        private String filename;
        private int translationCount;

        Protocol2Reader(byte[] data) {
            this.data = data;
        }

        boolean verify() {
            try {
                expect(0x80); // PROTO
                expectByte(2);
                expect(0x7d); // top-level EMPTY_DICT
                expect(0x28); // top-level MARK
                expectField("version");
                readInteger();
                expectField("key");
                readString();
                expectField("deferred_parse_errors");
                expectGlobal("collections", "defaultdict");
                expectGlobal("__builtin__", "list");
                expect(0x85); // TUPLE1
                expect(0x52); // REDUCE
                expect(0x75); // SETITEMS

                expect(0x5d); // stmts EMPTY_LIST
                expect(0x28); // stmts MARK
                parseInit();
                parseReturn();
                expect(0x65); // APPENDS stmts
                expect(0x86); // TUPLE2 (data, stmts)
                expect(0x2e); // STOP
                return position == data.length && translationCount >= 0;
            } catch (Protocol2FormatException error) {
                return false;
            }
        }

        private void parseInit() throws Protocol2FormatException {
            expectGlobal("renpy.ast", "Init");
            expect(0x29); // EMPTY_TUPLE
            expect(0x81); // NEWOBJ
            expect(0x4e); // self argument
            expect(0x7d); // state EMPTY_DICT
            expect(0x28); // state MARK
            expectField("linenumber");
            if (readInteger() != 1) {
                throw new Protocol2FormatException();
            }
            expectField("filename");
            filename = readString();
            expectField("name");
            if (!filename.equals(readString())) {
                throw new Protocol2FormatException();
            }
            if (readInteger() != MAGIC || readInteger() != 1416) {
                throw new Protocol2FormatException();
            }
            expect(0x87); // TUPLE3 name
            expectField("next");
            expect(0x4e); // NONE
            expectField("block");
            expect(0x5d); // block EMPTY_LIST
            expect(0x28); // block MARK
            int expectedLine = 3;
            int expectedSerial = 1417;
            while (peek() == 0x63) { // only TranslateString may follow
                parseTranslateString(expectedLine, expectedSerial);
                expectedLine += 2;
                expectedSerial++;
                translationCount++;
            }
            expect(0x65); // APPENDS block
            expectField("priority");
            if (readInteger() != 0) {
                throw new Protocol2FormatException();
            }
            expect(0x75); // SETITEMS state
            expect(0x86); // TUPLE2 state
            expect(0x62); // BUILD Init
        }

        private void parseTranslateString(int expectedLine, int expectedSerial)
                throws Protocol2FormatException {
            expectGlobal("renpy.ast", "TranslateString");
            expect(0x29); // EMPTY_TUPLE
            expect(0x81); // NEWOBJ
            expect(0x4e); // self argument
            expect(0x7d); // state EMPTY_DICT
            expect(0x28); // state MARK
            expectField("linenumber");
            if (readInteger() != expectedLine) {
                throw new Protocol2FormatException();
            }
            expectField("filename");
            if (!filename.equals(readString())) {
                throw new Protocol2FormatException();
            }
            expectField("name");
            if (!filename.equals(readString())) {
                throw new Protocol2FormatException();
            }
            if (readInteger() != MAGIC || readInteger() != expectedSerial) {
                throw new Protocol2FormatException();
            }
            expect(0x87); // TUPLE3 name
            expectField("next");
            expect(0x4e); // NONE
            expectField("language");
            if (peek() == 0x4e) {
                expect(0x4e);
            } else {
                readString();
            }
            expectField("old");
            readString();
            expectField("new");
            readString();
            expectField("newloc");
            if (!filename.equals(readString())) {
                throw new Protocol2FormatException();
            }
            if (readInteger() != expectedLine) {
                throw new Protocol2FormatException();
            }
            expect(0x86); // TUPLE2 newloc/line
            expect(0x75); // SETITEMS state
            expect(0x86); // TUPLE2 state
            expect(0x62); // BUILD TranslateString
        }

        private void parseReturn() throws Protocol2FormatException {
            expectGlobal("renpy.ast", "Return");
            expect(0x29); // EMPTY_TUPLE
            expect(0x81); // NEWOBJ
            expect(0x4e); // self argument
            expect(0x7d); // state EMPTY_DICT
            expect(0x28); // state MARK
            expectField("linenumber");
            if (readInteger() != 3 + translationCount * 2) {
                throw new Protocol2FormatException();
            }
            expectField("filename");
            if (!filename.equals(readString())) {
                throw new Protocol2FormatException();
            }
            expectField("expression");
            expect(0x4e); // NONE
            expectField("name");
            if (!filename.equals(readString())) {
                throw new Protocol2FormatException();
            }
            if (readInteger() != MAGIC || readInteger() != 1417 + translationCount) {
                throw new Protocol2FormatException();
            }
            expect(0x87); // TUPLE3 name
            expectField("next");
            expect(0x4e); // NONE
            expect(0x75); // SETITEMS state
            expect(0x86); // TUPLE2 state
            expect(0x62); // BUILD Return
        }

        private void expectField(String field) throws Protocol2FormatException {
            if (!field.equals(readString())) {
                throw new Protocol2FormatException();
            }
        }

        private void expectGlobal(String module, String name) throws Protocol2FormatException {
            expect(0x63); // GLOBAL; only compare bytes, never execute it
            expectAsciiLine(module);
            expectAsciiLine(name);
        }

        private String readString() throws Protocol2FormatException {
            expect(0x58); // protocol-2 BINUNICODE only
            if (position + 4 > data.length) {
                throw new Protocol2FormatException();
            }
            int length = le32(data, position);
            position += 4;
            if (length < 0 || length > MAX_STRING_BYTES || length > data.length - position) {
                throw new Protocol2FormatException();
            }
            try {
                CharBuffer decoded = StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(data, position, length));
                position += length;
                return decoded.toString();
            } catch (CharacterCodingException error) {
                throw new Protocol2FormatException();
            }
        }

        private int readInteger() throws Protocol2FormatException {
            int opcode = next();
            if (opcode == 0x4b) { // BININT1
                return next();
            }
            if (opcode == 0x4d) { // BININT2
                int low = next();
                int high = next();
                return (short) (low | (high << 8));
            }
            if (opcode == 0x4a) { // BININT
                if (position + 4 > data.length) {
                    throw new Protocol2FormatException();
                }
                int value = le32(data, position);
                position += 4;
                return value;
            }
            throw new Protocol2FormatException();
        }

        private void expectAsciiLine(String expected) throws Protocol2FormatException {
            byte[] bytes = expected.getBytes(StandardCharsets.US_ASCII);
            if (position + bytes.length + 1 > data.length) {
                throw new Protocol2FormatException();
            }
            for (byte value : bytes) {
                if (data[position++] != value) {
                    throw new Protocol2FormatException();
                }
            }
            if (data[position++] != '\n') {
                throw new Protocol2FormatException();
            }
        }

        private int peek() throws Protocol2FormatException {
            if (position >= data.length) {
                throw new Protocol2FormatException();
            }
            return data[position] & 0xff;
        }

        private int next() throws Protocol2FormatException {
            int value = peek();
            position++;
            return value;
        }

        private void expect(int opcode) throws Protocol2FormatException {
            if (next() != opcode) {
                throw new Protocol2FormatException();
            }
        }

        private void expectByte(int value) throws Protocol2FormatException {
            if (next() != value) {
                throw new Protocol2FormatException();
            }
        }
    }

    private static final class Protocol2FormatException extends Exception {
    }

    private static Report invalid(String container, int preferredSlot) {
        return new Report(container, preferredSlot, -1, false, false,
                GenerationSupport.UNKNOWN_EXTRACT_ONLY, "invalid_rpyc",
                ModernDialect.UNKNOWN);
    }

    private static int pickleProtocol(byte[] pickle) {
        if (pickle.length >= 2 && (pickle[0] & 0xff) == 0x80) {
            int protocol = pickle[1] & 0xff;
            if (protocol <= 5) {
                return protocol;
            }
        }
        return -1;
    }

    /**
     * Finds module names in GLOBAL and STACK_GLOBAL-compatible string tokens.
     * The writer uses SHORT_BINUNICODE for modern pickle streams, while old
     * Python 2 files commonly use the GLOBAL opcode followed by a line.
     */
    private static boolean containsGlobalName(byte[] pickle, String module) {
        byte[] token = module.getBytes(StandardCharsets.US_ASCII);
        for (int i = 0; i < pickle.length; i++) {
            int opcode = pickle[i] & 0xff;
            if (opcode == 0x95) { // FRAME: skip the 8-byte frame length. Its low
                // byte can collide with a payload opcode (e.g. 0x8e BINBYTES8)
                // and previously made the scan misread the length as a huge
                // payload, bailing with a false negative.
                if (i + 9 > pickle.length) return false;
                i += 8;
                continue;
            }
            if (opcode == 0x63) { // GLOBAL: module\\nname\\n
                int start = i + 1;
                int end = lineEnd(pickle, start);
                if (end > start && equalsAscii(pickle, start, end, token)) {
                    return true;
                }
                i = end;
                continue;
            }
            int payloadStart = -1;
            int payloadLength = -1;
            if (opcode == 0x8c || opcode == 0x55) { // SHORT_BINUNICODE/SHORT_BINSTRING
                if (i + 2 > pickle.length) return false;
                payloadStart = i + 2;
                payloadLength = pickle[i + 1] & 0xff;
            } else if (opcode == 0x58 || opcode == 0x54 || opcode == 0x42) {
                // BINUNICODE/BINSTRING/BINBYTES
                if (i + 5 > pickle.length) return false;
                payloadStart = i + 5;
                payloadLength = le32(pickle, i + 1);
            } else if (opcode == 0x8d || opcode == 0x8e || opcode == 0x96) {
                // BINUNICODE8/BINBYTES8/BYTEARRAY8
                if (i + 9 > pickle.length) return false;
                long length = le64(pickle, i + 1);
                if (length < 0 || length > Integer.MAX_VALUE) return false;
                payloadStart = i + 9;
                payloadLength = (int) length;
            }
            if (payloadStart >= 0) {
                if (payloadLength < 0 || payloadStart > pickle.length
                        || payloadLength > pickle.length - payloadStart) {
                    return false;
                }
                if ((opcode == 0x8c || opcode == 0x58 || opcode == 0x8d || opcode == 0x55
                        || opcode == 0x54)
                        && equalsAscii(pickle, payloadStart, payloadStart + payloadLength, token)) {
                    return true;
                }
                i = payloadStart + payloadLength - 1;
            }
        }
        return false;
    }

    private static boolean containsGlobalPair(byte[] pickle, String module, String name) {
        return findGlobalPair(pickle, module, name, 0) >= 0;
    }

    /**
     * Checks the non-executing envelope emitted by a real legacy Ren'Py
     * compiler. This is deliberately stricter than checking global names:
     * malformed streams that merely mention Init/Return must stay blocked.
     */
    private static boolean hasLegacyScriptEnvelope(byte[] pickle) {
        int version = findStringToken(pickle, "version", 0);
        int key = findStringToken(pickle, "key", version + 1);
        int deferred = findStringToken(pickle, "deferred_parse_errors", key + 1);
        int defaultdict = findGlobalPair(pickle, "collections", "defaultdict", deferred + 1);
        int list = findGlobalPair(pickle, "__builtin__", "list", defaultdict + 1);
        int scriptList = findOpcode(pickle, 0x5d, list + 1); // EMPTY_LIST (stmts)
        int init = findGlobalPair(pickle, "renpy.ast", "Init", scriptList + 1);
        int ret = findGlobalPair(pickle, "renpy.ast", "Return", init + 1);
        return version >= 0 && key > version && deferred > key
                && defaultdict > deferred && list > defaultdict
                && scriptList > list && init > scriptList && ret > init;
    }

    private static int findStringToken(byte[] pickle, String value, int from) {
        byte[] expected = value.getBytes(StandardCharsets.UTF_8);
        for (int i = Math.max(0, from); i < pickle.length; i++) {
            int opcode = pickle[i] & 0xff;
            int start;
            int length;
            if (opcode == 0x58) { // BINUNICODE
                if (i + 5 > pickle.length) continue;
                length = le32(pickle, i + 1);
                start = i + 5;
            } else if (opcode == 0x8c) { // SHORT_BINUNICODE
                if (i + 2 > pickle.length) continue;
                length = pickle[i + 1] & 0xff;
                start = i + 2;
            } else if (opcode == 0x55) { // BINSTRING
                if (i + 5 > pickle.length) continue;
                length = le32(pickle, i + 1);
                start = i + 5;
            } else {
                continue;
            }
            if (length < 0 || start > pickle.length || length > pickle.length - start) {
                continue;
            }
            if (equalsBytes(pickle, start, length, expected)) return i;
            i = start + length - 1;
        }
        return -1;
    }

    private static int findOpcode(byte[] pickle, int wanted, int from) {
        for (int i = Math.max(0, from); i < pickle.length; i++) {
            if ((pickle[i] & 0xff) == wanted) return i;
        }
        return -1;
    }

    private static int findGlobalPair(byte[] pickle, String module, String name, int from) {
        byte[] moduleBytes = module.getBytes(StandardCharsets.US_ASCII);
        byte[] nameBytes = name.getBytes(StandardCharsets.US_ASCII);
        for (int i = Math.max(0, from); i < pickle.length; i++) {
            if ((pickle[i] & 0xff) != 0x63) { // GLOBAL: module\nname\n
                continue;
            }
            int moduleStart = i + 1;
            int moduleEnd = lineEnd(pickle, moduleStart);
            if (moduleEnd >= pickle.length || !equalsAscii(pickle, moduleStart, moduleEnd, moduleBytes)) {
                i = moduleEnd;
                continue;
            }
            int nameStart = moduleEnd + 1;
            int nameEnd = lineEnd(pickle, nameStart);
            if (nameEnd < pickle.length && equalsAscii(pickle, nameStart, nameEnd, nameBytes)) {
                return i;
            }
            i = nameEnd;
        }
        return -1;
    }

    private static boolean equalsBytes(byte[] data, int start, int length, byte[] expected) {
        if (length != expected.length || start < 0 || start > data.length
                || length > data.length - start) {
            return false;
        }
        for (int i = 0; i < length; i++) {
            if (data[start + i] != expected[i]) return false;
        }
        return true;
    }

    private static int lineEnd(byte[] data, int start) {
        int end = start;
        while (end < data.length && data[end] != '\n') {
            end++;
        }
        return end;
    }

    private static boolean equalsAscii(byte[] data, int start, int end, byte[] expected) {
        if (end - start != expected.length) {
            return false;
        }
        for (int i = 0; i < expected.length; i++) {
            if (data[start + i] != expected[i]) {
                return false;
            }
        }
        return true;
    }

    private static byte[] inflateRpc2Slot(byte[] rpyc, int wantedSlot) {
        int pos = RPC2_MAGIC.length;
        while (pos >= 0 && pos + 12 <= rpyc.length) {
            long id = le32Unsigned(rpyc, pos);
            long offset = le32Unsigned(rpyc, pos + 4);
            long length = le32Unsigned(rpyc, pos + 8);
            if (id == 0) {
                return null;
            }
            if (id == wantedSlot) {
                if (offset > rpyc.length || length > rpyc.length - offset) {
                    return null;
                }
                return inflate(rpyc, (int) offset, (int) length);
            }
            pos += 12;
        }
        return null;
    }

    private static byte[] inflate(byte[] data, int offset, int length) {
        if (offset < 0 || length < 0 || offset > data.length
                || length > data.length - offset) {
            return null;
        }
        try {
            RenpyResourceLimits.checkCompressed(length);
        } catch (RenpyResourceLimits.LimitException e) {
            return null;
        }
        try (InputStream input = new InflaterInputStream(
                    new ByteArrayInputStream(data, offset, length));
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            long total = 0;
            while ((count = input.read(buffer)) != -1) {
                RenpyResourceLimits.checkInterrupted();
                total += count;
                RenpyResourceLimits.checkInflated(total);
                RenpyResourceLimits.checkInflateRatio(length, total);
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        } catch (RenpyResourceLimits.LimitException e) {
            return null;
        } catch (IOException e) {
            return null;
        }
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private static long le32Unsigned(byte[] data, int pos) {
        return (data[pos] & 0xffL)
                | ((data[pos + 1] & 0xffL) << 8)
                | ((data[pos + 2] & 0xffL) << 16)
                | ((data[pos + 3] & 0xffL) << 24);
    }

    private static int le32(byte[] data, int pos) {
        return (data[pos] & 0xff)
                | ((data[pos + 1] & 0xff) << 8)
                | ((data[pos + 2] & 0xff) << 16)
                | ((data[pos + 3] & 0xff) << 24);
    }

    private static long le64(byte[] data, int pos) {
        return (data[pos] & 0xffL)
                | ((data[pos + 1] & 0xffL) << 8)
                | ((data[pos + 2] & 0xffL) << 16)
                | ((data[pos + 3] & 0xffL) << 24)
                | ((data[pos + 4] & 0xffL) << 32)
                | ((data[pos + 5] & 0xffL) << 40)
                | ((data[pos + 6] & 0xffL) << 48)
                | ((data[pos + 7] & 0xffL) << 56);
    }
}
