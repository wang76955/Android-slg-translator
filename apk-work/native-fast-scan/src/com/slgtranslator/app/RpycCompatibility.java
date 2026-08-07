package com.slgtranslator.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
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
    public enum GenerationSupport {
        MODERN_SUPPORTED,
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

        Report(String container, int preferredSlot, int pickleProtocol,
               boolean usesBuiltins, boolean usesPy2Builtins,
               GenerationSupport generationSupport, String reason) {
            this.container = container;
            this.preferredSlot = preferredSlot;
            this.pickleProtocol = pickleProtocol;
            this.usesBuiltins = usesBuiltins;
            this.usesPy2Builtins = usesPy2Builtins;
            this.generationSupport = generationSupport;
            this.reason = reason;
        }

        /** True only when the local writer has a verified dialect for this report. */
        public boolean canGenerate() {
            return generationSupport == GenerationSupport.MODERN_SUPPORTED
                    || generationSupport == GenerationSupport.LEGACY_PROTOCOL2_SUPPORTED;
        }

        /** True only for the structurally verified Python 2 protocol-2 shape. */
        public boolean isProtocol2WriterVerified() {
            return "legacy_protocol2_writer_verified".equals(reason)
                    && pickleProtocol == 2 && usesPy2Builtins && !usesBuiltins;
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
        if (isVerifiedProtocol2(pickle, protocol, usesBuiltins, usesPy2Builtins)) {
            // RenpyPreflight's existing public gate uses MODERN_SUPPORTED to
            // mean that a verified local writer exists. The report's explicit
            // dialect predicate keeps that gate compatible without allowing
            // unknown Python 2 structures through.
            support = GenerationSupport.MODERN_SUPPORTED;
            reason = "legacy_protocol2_writer_verified";
        } else if (usesPy2Builtins) {
            support = GenerationSupport.LEGACY_EXTRACT_ONLY;
            reason = "legacy_pickle_writer_required";
        } else if (usesBuiltins) {
            support = GenerationSupport.MODERN_SUPPORTED;
            reason = "modern_writer_supported";
        } else {
            support = GenerationSupport.UNKNOWN_EXTRACT_ONLY;
            reason = "unknown_pickle_globals";
        }
        return new Report(container, preferredSlot, protocol, usesBuiltins,
                usesPy2Builtins, support, reason);
    }

    /**
     * Verifies exactly the opcode/global subset emitted by RpycPickleWriter's
     * Python 2 dialect. This is a structural check only: GLOBAL targets are
     * recorded as names and are never imported or executed.
     */
    private static boolean isVerifiedProtocol2(byte[] pickle, int protocol,
                                               boolean usesBuiltins,
                                               boolean usesPy2Builtins) {
        if (protocol != 2 || usesBuiltins || !usesPy2Builtins) {
            return false;
        }
        boolean collections = false;
        boolean builtinList = false;
        boolean init = false;
        boolean translate = false;
        boolean ret = false;
        int pos = 0;
        while (pos < pickle.length) {
            int opcode = pickle[pos++] & 0xff;
            switch (opcode) {
                case 0x80: // PROTO
                    if (pos >= pickle.length || (pickle[pos++] & 0xff) != 2) {
                        return false;
                    }
                    break;
                case 0x63: { // GLOBAL: module\nname\n
                    int moduleEnd = lineEnd(pickle, pos);
                    if (moduleEnd >= pickle.length) {
                        return false;
                    }
                    int nameStart = moduleEnd + 1;
                    int nameEnd = lineEnd(pickle, nameStart);
                    if (nameEnd >= pickle.length) {
                        return false;
                    }
                    boolean isCollections = equalsAscii(pickle, pos, moduleEnd,
                            "collections".getBytes(StandardCharsets.US_ASCII));
                    boolean isPy2Builtins = equalsAscii(pickle, pos, moduleEnd,
                            "__builtin__".getBytes(StandardCharsets.US_ASCII));
                    boolean isRenpyAst = equalsAscii(pickle, pos, moduleEnd,
                            "renpy.ast".getBytes(StandardCharsets.US_ASCII));
                    if (isCollections) {
                        if (!equalsAscii(pickle, nameStart, nameEnd,
                                "defaultdict".getBytes(StandardCharsets.US_ASCII))) {
                            return false;
                        }
                        collections = true;
                    } else if (isPy2Builtins) {
                        if (!equalsAscii(pickle, nameStart, nameEnd,
                                "list".getBytes(StandardCharsets.US_ASCII))) {
                            return false;
                        }
                        builtinList = true;
                    } else if (isRenpyAst) {
                        if (equalsAscii(pickle, nameStart, nameEnd,
                                "Init".getBytes(StandardCharsets.US_ASCII))) {
                            init = true;
                        } else if (equalsAscii(pickle, nameStart, nameEnd,
                                "TranslateString".getBytes(StandardCharsets.US_ASCII))) {
                            translate = true;
                        } else if (equalsAscii(pickle, nameStart, nameEnd,
                                "Return".getBytes(StandardCharsets.US_ASCII))) {
                            ret = true;
                        } else {
                            return false;
                        }
                    } else {
                        return false;
                    }
                    pos = nameEnd + 1;
                    break;
                }
                case 0x58: // BINUNICODE
                    if (pos + 4 > pickle.length) {
                        return false;
                    }
                    int length = le32(pickle, pos);
                    if (length < 0 || length > pickle.length - pos - 4) {
                        return false;
                    }
                    pos += 4 + length;
                    break;
                case 0x4a: // BININT
                    if (pos + 4 > pickle.length) return false;
                    pos += 4;
                    break;
                case 0x4b: // BININT1
                    if (pos >= pickle.length) return false;
                    pos++;
                    break;
                case 0x4d: // BININT2
                    if (pos + 2 > pickle.length) return false;
                    pos += 2;
                    break;
                case 0x28: case 0x29: case 0x2e: case 0x4e:
                case 0x52: case 0x5d: case 0x62: case 0x65:
                case 0x75: case 0x7d: case 0x81: case 0x85:
                case 0x86: case 0x87:
                    break;
                default:
                    // In particular reject SHORT_BINUNICODE, STACK_GLOBAL,
                    // protocol-3 globals, and every unknown extension opcode.
                    return false;
            }
        }
        return collections && builtinList && init && translate && ret;
    }

    private static Report invalid(String container, int preferredSlot) {
        return new Report(container, preferredSlot, -1, false, false,
                GenerationSupport.UNKNOWN_EXTRACT_ONLY, "invalid_rpyc");
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
            if (opcode == 0x63) { // GLOBAL: module\\nname\\n
                int start = i + 1;
                int end = lineEnd(pickle, start);
                if (end > start && equalsAscii(pickle, start, end, token)) {
                    return true;
                }
                i = end;
                continue;
            }
            if (opcode == 0x8c && i + 2 + token.length <= pickle.length
                    && (pickle[i + 1] & 0xff) == token.length
                    && equalsAscii(pickle, i + 2, i + 2 + token.length, token)) {
                return true;
            }
            if (opcode == 0x58 && i + 5 + token.length <= pickle.length
                    && le32(pickle, i + 1) == token.length
                    && equalsAscii(pickle, i + 5, i + 5 + token.length, token)) {
                return true;
            }
            if (opcode == 0x55 && i + 2 + token.length <= pickle.length
                    && (pickle[i + 1] & 0xff) == token.length
                    && equalsAscii(pickle, i + 2, i + 2 + token.length, token)) {
                return true;
            }
        }
        return false;
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
}
