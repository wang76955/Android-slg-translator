package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.zip.DataFormatException;
import java.util.zip.Inflater;

/**
 * Validates the small RPYC/pickle subset emitted by TranslationCompiler.
 *
 * <p>The validator is intentionally a structural reader. It never invokes a
 * pickle interpreter and never deserializes arbitrary Java or Python objects.
 * A generated resource must pass this check before it is merged into an APK.</p>
 */
public final class RenpyPatchValidator {

    private static final byte[] RPC2_MAGIC = "RENPY RPC2".getBytes(StandardCharsets.US_ASCII);
    public static final class Result {
        public final boolean valid;
        public final String code;
        public final String message;
        public final int decodedPairCount;

        Result(boolean valid, String code, String message, int decodedPairCount) {
            this.valid = valid;
            this.code = code;
            this.message = message;
            this.decodedPairCount = decodedPairCount;
        }
    }

    private enum Pending {
        NONE,
        VERSION,
        KEY,
        LANGUAGE,
        OLD,
        NEW
    }

    private static final class PayloadResult {
        final byte[] pickle;
        final String code;
        final String message;

        PayloadResult(byte[] pickle, String code, String message) {
            this.pickle = pickle;
            this.code = code;
            this.message = message;
        }
    }

    private static final class InflateResult {
        final byte[] data;
        final boolean valid;

        InflateResult(byte[] data, boolean valid) {
            this.data = data;
            this.valid = valid;
        }
    }

    private static final class Slot {
        final long offset;
        final long length;
        final byte[] pickle;

        Slot(long offset, long length, byte[] pickle) {
            this.offset = offset;
            this.length = length;
            this.pickle = pickle;
        }
    }

    private RenpyPatchValidator() {
    }

    public static Result validateCompiledRpyc(
            byte[] rpyc,
            int expectedVersion,
            String expectedKey,
            String expectedLanguage,
            int expectedPairCount) {
        if (rpyc == null || rpyc.length == 0) {
            return invalid("renpy_invalid_rpyc", "RPYC 为空", 0);
        }
        if (expectedPairCount < 0) {
            return invalid("renpy_pair_count", "映射数量不能为负数", 0);
        }

        PayloadResult payload = readPayload(rpyc);
        if (payload.pickle == null) {
            return invalid(payload.code, payload.message, 0);
        }
        List<int[]> ops = LanguageMenuSupport.walk(payload.pickle);
        if (ops == null || ops.isEmpty()) {
            return invalid("renpy_pickle_structure", "pickle 结构不是当前 writer 支持的子集", 0);
        }

        int version = Integer.MIN_VALUE;
        String key = null;
        int languageCount = 0;
        int pairCount = 0;
        String pendingOld = null;
        Pending pending = Pending.NONE;

        for (int i = 0; i < ops.size(); i++) {
            int code = ops.get(i)[0];
            String value = LanguageMenuSupport.stringPayload(payload.pickle, ops, i);
            if (value != null) {
                if (pending == Pending.KEY) {
                    key = value;
                    pending = Pending.NONE;
                    continue;
                }
                if (pending == Pending.LANGUAGE) {
                    languageCount++;
                    if (expectedLanguage == null || !expectedLanguage.equals(value)) {
                        return invalid("renpy_language_mismatch",
                                "TranslateString.language 与预期不一致", pairCount);
                    }
                    pending = Pending.NONE;
                    continue;
                }
                if (pending == Pending.OLD) {
                    pendingOld = value;
                    pending = Pending.NONE;
                    continue;
                }
                if (pending == Pending.NEW) {
                    if (pendingOld == null) {
                        return invalid("renpy_pair_value", "new 缺少对应的 old", pairCount);
                    }
                    pairCount++;
                    pendingOld = null;
                    pending = Pending.NONE;
                    continue;
                }
                if (pending == Pending.VERSION) {
                    return invalid("renpy_pickle_structure", "version 不是整数", pairCount);
                }
                if (pending != Pending.NONE) {
                    return invalid("renpy_pickle_structure", "pickle 字段值缺失", pairCount);
                }
                if ("version".equals(value)) {
                    pending = Pending.VERSION;
                } else if ("key".equals(value)) {
                    pending = Pending.KEY;
                } else if ("language".equals(value)) {
                    pending = Pending.LANGUAGE;
                } else if ("old".equals(value)) {
                    if (pendingOld != null) {
                        return invalid("renpy_pair_value", "old 缺少对应的 new", pairCount);
                    }
                    pending = Pending.OLD;
                } else if ("new".equals(value)) {
                    if (pendingOld == null) {
                        return invalid("renpy_pair_value", "new 缺少对应的 old", pairCount);
                    }
                    pending = Pending.NEW;
                }
                continue;
            }

            if (code == 0x4e) { // NONE
                if (pending == Pending.LANGUAGE) {
                    languageCount++;
                    if (expectedLanguage != null) {
                        return invalid("renpy_language_mismatch",
                                "TranslateString.language 应为 NONE", pairCount);
                    }
                    pending = Pending.NONE;
                    continue;
                }
                if (pending == Pending.OLD || pending == Pending.NEW) {
                    return invalid("renpy_pair_value", "old/new 不能为 NONE", pairCount);
                }
                if (pending != Pending.NONE) {
                    return invalid("renpy_pickle_structure", "pickle 字段值不能为 NONE", pairCount);
                }
            } else if (pending == Pending.VERSION && isIntegerOpcode(code)) {
                Integer decoded = integerValue(payload.pickle, ops, i);
                if (decoded == null) {
                    return invalid("renpy_pickle_structure", "version 整数损坏", pairCount);
                }
                version = decoded;
                pending = Pending.NONE;
            } else if (pending != Pending.NONE) {
                return invalid("renpy_pickle_structure", "pickle 字段值缺失", pairCount);
            }
        }

        if (pending != Pending.NONE || pendingOld != null) {
            return invalid("renpy_pickle_structure", "pickle 字段未闭合", pairCount);
        }
        if (version != expectedVersion) {
            return invalid("renpy_version_mismatch", "data.version 与模板不一致", pairCount);
        }
        if (expectedKey == null ? key != null : !expectedKey.equals(key)) {
            return invalid("renpy_key_mismatch", "data.key 与模板不一致", pairCount);
        }
        if (pairCount != expectedPairCount) {
            return invalid("renpy_pair_count", "TranslateString 数量与预期不一致", pairCount);
        }
        if (languageCount != expectedPairCount) {
            return invalid("renpy_language_mismatch", "TranslateString.language 数量不一致", pairCount);
        }
        return new Result(true, "ok", "", pairCount);
    }

    private static PayloadResult readPayload(byte[] rpyc) {
        if (!startsWith(rpyc, RPC2_MAGIC)) {
            InflateResult legacy = inflate(rpyc, 0, rpyc.length);
            return legacy.valid
                    ? new PayloadResult(legacy.data, "", "")
                    : new PayloadResult(null, "renpy_zlib_truncated", "legacy RPYC 的 zlib 数据不完整");
        }
        if (rpyc.length < RPC2_MAGIC.length + 12) {
            return new PayloadResult(null, "renpy_slot_range", "RPC2 槽位表不完整");
        }
        Slot slot1 = null;
        Slot slot2 = null;
        boolean terminated = false;
        int pos = RPC2_MAGIC.length;
        while (pos + 12 <= rpyc.length) {
            long id = le32Unsigned(rpyc, pos);
            long offset = le32Unsigned(rpyc, pos + 4);
            long length = le32Unsigned(rpyc, pos + 8);
            pos += 12;
            if (id == 0) {
                terminated = true;
                break;
            }
            if (offset > rpyc.length || length == 0 || length > rpyc.length - offset) {
                return new PayloadResult(null, "renpy_slot_range", "RPC2 槽位 offset/length 越界");
            }
            InflateResult inflated = inflate(rpyc, (int) offset, (int) length);
            if (!inflated.valid) {
                return new PayloadResult(null, "renpy_zlib_truncated", "RPC2 槽位 zlib 数据不完整");
            }
            if (id == 1) {
                slot1 = new Slot(offset, length, inflated.data);
            } else if (id == 2) {
                slot2 = new Slot(offset, length, inflated.data);
            }
        }
        if (!terminated) {
            return new PayloadResult(null, "renpy_slot_range", "RPC2 槽位表没有结束标记");
        }
        Slot selected = slot2 != null ? slot2 : slot1;
        if (selected == null) {
            return new PayloadResult(null, "renpy_slot_range", "RPC2 缺少槽 2/槽 1");
        }
        return new PayloadResult(selected.pickle, "", "");
    }

    private static InflateResult inflate(byte[] data, int offset, int length) {
        RenpyResourceLimits.checkCompressed(length);
        Inflater inflater = new Inflater();
        inflater.setInput(data, offset, length);
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int total = 0;
            while (!inflater.finished()) {
                int count = inflater.inflate(buffer);
                if (count > 0) {
                    total += count;
                    RenpyResourceLimits.checkInflated(total);
                    RenpyResourceLimits.checkInflateRatio(length, total);
                    out.write(buffer, 0, count);
                    continue;
                }
                if (inflater.needsDictionary() || inflater.needsInput()) {
                    return new InflateResult(null, false);
                }
                return new InflateResult(null, false);
            }
            if (inflater.getRemaining() != 0) {
                return new InflateResult(null, false);
            }
            return new InflateResult(out.toByteArray(), true);
        } catch (DataFormatException e) {
            return new InflateResult(null, false);
        } finally {
            inflater.end();
        }
    }

    private static boolean isIntegerOpcode(int code) {
        return code == 0x4a || code == 0x4b || code == 0x4d;
    }

    private static Integer integerValue(byte[] data, List<int[]> ops, int index) {
        int position = ops.get(index)[1];
        if (position < 0 || position >= data.length) {
            return null;
        }
        int code = data[position] & 0xff;
        if (code == 0x4b && position + 1 < data.length) {
            return data[position + 1] & 0xff;
        }
        if (code == 0x4d && position + 2 < data.length) {
            return (data[position + 1] & 0xff) | ((data[position + 2] & 0xff) << 8);
        }
        if (code == 0x4a && position + 4 < data.length) {
            return le32(data, position + 1);
        }
        return null;
    }

    private static Result invalid(String code, String message, int decodedPairCount) {
        return new Result(false, code, message, decodedPairCount);
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
