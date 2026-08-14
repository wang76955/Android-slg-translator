package com.slgtranslator.app;

import java.util.ArrayList;
import java.util.List;

/**
 * Byte-level integrity checks for rewritten pickle streams. This is the
 * production counterpart of the acceptance harness's strict pickle checker:
 * FRAME lengths, memo references and payload bounds must be exact before a
 * rewritten artifact is allowed into an APK.
 *
 * <p>The checks are deliberately independent from the writer code path: any
 * length-changing rewrite must satisfy them, otherwise the build fails
 * closed instead of shipping an APK that Ren'Py's strict unpickler rejects
 * at startup ({@code invalid load key} / memo desyncs).</p>
 */
public final class RpycStreamValidator {

    public static final String CODE_TRUNCATED = "renpy_pickle_truncated";
    public static final String CODE_FRAME_LENGTH = "renpy_pickle_frame_length";
    public static final String CODE_MEMO_REFERENCE = "renpy_pickle_memo_reference";

    private RpycStreamValidator() {
    }

    /**
     * Returns {@code null} when the stream is structurally sound, otherwise
     * a stable failure code from {@code CODE_*}.
     */
    public static String validate(byte[] pickle) {
        if (pickle == null || pickle.length == 0) {
            return CODE_TRUNCATED;
        }
        List<int[]> ops = LanguageMenuSupport.walk(pickle);
        if (ops == null) {
            return CODE_TRUNCATED;
        }
        List<Integer> frameStarts = new ArrayList<>();
        int memoCount = 0;
        for (int[] op : ops) {
            int code = op[0];
            if (code == 0x94) { // MEMOIZE
                memoCount++;
            } else if (code == 0x71 || code == 0x72) { // BINPUT / LONG_BINPUT
                int index = memoIndex(pickle, op, code);
                if (index < 0) {
                    return CODE_MEMO_REFERENCE;
                }
                if (index + 1 > memoCount) {
                    memoCount = index + 1;
                }
            } else if (code == 0x68 || code == 0x6a) { // BINGET / LONG_BINGET
                int index = memoIndex(pickle, op, code);
                if (index < 0 || index >= memoCount) {
                    return CODE_MEMO_REFERENCE;
                }
            } else if (code == 0x95) { // FRAME
                frameStarts.add(op[1]);
            }
        }
        for (int f = 0; f < frameStarts.size(); f++) {
            int start = frameStarts.get(f);
            int contentStart = start + 9;
            int end = (f + 1 < frameStarts.size()) ? frameStarts.get(f + 1) : pickle.length;
            if (end < contentStart) {
                return CODE_FRAME_LENGTH;
            }
            long expected = end - contentStart;
            if (le64(pickle, start + 1) != expected) {
                return CODE_FRAME_LENGTH;
            }
        }
        return null;
    }

    /** Throws when the rewritten stream fails strict validation. */
    public static void requireValid(byte[] pickle, String label) throws java.io.IOException {
        String code = validate(pickle);
        if (code != null) {
            throw new java.io.IOException(label + ": " + code);
        }
    }

    private static int memoIndex(byte[] data, int[] op, int code) {
        if (op[2] - op[1] < 2) {
            return -1;
        }
        if (code == 0x71 || code == 0x68) {
            return data[op[1] + 1] & 0xff;
        }
        if (op[2] - op[1] < 5) {
            return -1;
        }
        return le32(data, op[1] + 1);
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
