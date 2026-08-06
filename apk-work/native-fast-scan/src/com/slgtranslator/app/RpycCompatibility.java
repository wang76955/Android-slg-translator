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
        if (usesPy2Builtins) {
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
