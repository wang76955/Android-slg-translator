package com.slgtranslator.app;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Bounded, non-executing verifier for modern Ren'Py pickle envelopes.
 *
 * <p>This parser consumes the opcode stream with a symbolic stack. It never
 * imports a GLOBAL target or instantiates a Python object. The modern writer
 * gate requires the first object to be a three-key dict, at least one legal
 * {@code renpy.ast} global to be consumed, and an exact STOP/EOF boundary.</p>
 */
public final class ModernEnvelopeReader {
    private static final int MAX_STRING_BYTES = 16 * 1024 * 1024;
    private static final int MAX_CONTAINER_ITEMS = 1_000_000;

    private ModernEnvelopeReader() {
    }

    public static ModernEnvelopeInspection inspect(byte[] pickle) {
        if (pickle == null || pickle.length < 3) {
            return ModernEnvelopeInspection.generic("missing_pickle");
        }
        try {
            return new Parser(pickle).parse();
        } catch (FormatException error) {
            return ModernEnvelopeInspection.generic(error.code);
        }
    }

    private static final class Parser {
        private final byte[] data;
        private final List<Value> stack = new ArrayList<>();
        private final Map<Integer, Value> memo = new LinkedHashMap<>();
        private int position;
        private int protocol = -1;
        private Value firstObject;
        private Value envelope;
        private boolean sawRenpyAstGlobal;
        private int frameCount;
        private int memoizeCount;
        private int newObjectCount;
        private int setItemCount;
        private int setItemsCount;
        private int stackGlobalCount;
        private boolean sawObjectSetItems;

        Parser(byte[] data) {
            this.data = data;
        }

        ModernEnvelopeInspection parse() throws FormatException {
            expect(0x80); // PROTO
            protocol = next();
            if (protocol < 2 || protocol > 5) throw fail("unsupported_protocol");

            boolean stopped = false;
            while (position < data.length) {
                int opcode = next();
                switch (opcode) {
                    case 0x2e: // STOP
                        if (!stack.isEmpty() && !hasMark() && stack.size() == 1) {
                            Value result = stack.remove(0);
                            stopped = true;
                            if (position != data.length) throw fail("trailing_bytes_after_stop");
                            if (envelope == null || !sawRenpyAstGlobal
                                    || !containsIdentity(result, firstObject)) {
                                throw fail("modern_envelope_shape");
                            }
                            return new ModernEnvelopeInspection(
                                    true,
                                    RpycCompatibility.ModernDialect.MODERN_ENVELOPE_VERIFIED,
                                    protocol,
                                    envelope.map.keySet(),
                                    true,
                                    shape(result),
                                    frameCount,
                                    memoizeCount,
                                    newObjectCount,
                                    setItemCount,
                                    setItemsCount,
                                    stackGlobalCount,
                                    sawObjectSetItems,
                                    "verified");
                        }
                        throw fail("stop_stack_shape");
                    case 0x28: // MARK
                        push(Value.mark());
                        break;
                    case 0x80: // nested PROTO is not valid
                        throw fail("nested_proto");
                    case 0x95: // FRAME
                        frameCount++;
                        long frameLength = readLe64();
                        if (frameLength < 0 || frameLength > data.length - position) {
                            throw fail("invalid_frame_length");
                        }
                        break;
                    case 0x7d: // EMPTY_DICT
                        push(Value.dict());
                        break;
                    case 0x5d: // EMPTY_LIST
                        push(Value.list());
                        break;
                    case 0x29: // EMPTY_TUPLE
                        push(Value.tuple(Collections.<Value>emptyList()));
                        break;
                    case 0x8f: // EMPTY_SET
                        push(Value.set());
                        break;
                    case 0x4e: // NONE
                        push(Value.opaque(ValueKind.NONE));
                        break;
                    case 0x88: // NEWTRUE
                    case 0x89: // NEWFALSE
                        push(Value.opaque(ValueKind.BOOLEAN));
                        break;
                    case 0x4b: // BININT1
                        next();
                        push(Value.opaque(ValueKind.INTEGER));
                        break;
                    case 0x4d: // BININT2
                        readBytes(2);
                        push(Value.opaque(ValueKind.INTEGER));
                        break;
                    case 0x4a: // BININT
                        readBytes(4);
                        push(Value.opaque(ValueKind.INTEGER));
                        break;
                    case 0x8a: // LONG1
                        skipSizedBytes(next(), 1);
                        push(Value.opaque(ValueKind.INTEGER));
                        break;
                    case 0x8b: // LONG4
                        skipSizedBytes(readLe32(), 1);
                        push(Value.opaque(ValueKind.INTEGER));
                        break;
                    case 0x46: // FLOAT
                        readAsciiLine();
                        push(Value.opaque(ValueKind.FLOAT));
                        break;
                    case 0x47: // BINFLOAT
                        readBytes(8);
                        push(Value.opaque(ValueKind.FLOAT));
                        break;
                    case 0x8c: // SHORT_BINUNICODE
                        push(Value.string(readUtf8(next())));
                        break;
                    case 0x58: // BINUNICODE
                        push(Value.string(readUtf8(readLe32())));
                        break;
                    case 0x8d: // BINUNICODE8
                        push(Value.string(readUtf8(readLe64AsInt())));
                        break;
                    case 0x55: // SHORT_BINSTRING
                        push(Value.string(readUtf8(next())));
                        break;
                    case 0x54: // BINSTRING
                        push(Value.string(readUtf8(readLe32())));
                        break;
                    case 0x42: // SHORT_BINBYTES
                        push(Value.opaque(ValueKind.BYTES));
                        skipBytes(next());
                        break;
                    case 0x43: // BINBYTES
                        push(Value.opaque(ValueKind.BYTES));
                        skipBytes(readLe32());
                        break;
                    case 0x8e: // BINBYTES8
                    case 0x96: // BYTEARRAY8
                        push(Value.opaque(ValueKind.BYTES));
                        skipBytes(readLe64AsInt());
                        break;
                    case 0x63: // GLOBAL
                        readGlobal();
                        break;
                    case 0x93: // STACK_GLOBAL
                        stackGlobalCount++;
                        readStackGlobal();
                        break;
                    case 0x85: // TUPLE1
                        makeTuple(1);
                        break;
                    case 0x86: // TUPLE2
                        makeTuple(2);
                        break;
                    case 0x87: // TUPLE3
                        makeTuple(3);
                        break;
                    case 0x74: // TUPLE from MARK
                        makeTupleFromMark();
                        break;
                    case 0x75: // SETITEMS
                        setItemsCount++;
                        setItems();
                        break;
                    case 0x73: // SETITEM
                        setItemCount++;
                        setItem();
                        break;
                    case 0x65: // APPENDS
                        appends();
                        break;
                    case 0x61: // APPEND
                        append();
                        break;
                    case 0x6c: // LIST from MARK
                        makeListFromMark();
                        break;
                    case 0x90: // ADDITEMS
                        addItems();
                        break;
                    case 0x52: // REDUCE
                        reduce();
                        break;
                    case 0x81: // NEWOBJ
                        newObjectCount++;
                        newObject();
                        break;
                    case 0x92: // NEWOBJ_EX
                        newObjectEx();
                        break;
                    case 0x62: // BUILD
                        build();
                        break;
                    case 0x94: // MEMOIZE
                        memoizeCount++;
                        memo.put(memo.size(), peek());
                        break;
                    case 0x70: // PUT
                        memo.put(readDecimalLine(), peek());
                        break;
                    case 0x71: // BINPUT
                        memo.put(next(), peek());
                        break;
                    case 0x72: // LONG_BINPUT
                        memo.put(readLe32(), peek());
                        break;
                    case 0x67: // GET
                        push(memo.get(readDecimalLine()));
                        break;
                    case 0x68: // BINGET
                        push(memo.get(next()));
                        break;
                    case 0x6a: // LONG_BINGET
                        push(memo.get(readLe32()));
                        break;
                    case 0x30: // POP
                        pop();
                        break;
                    case 0x31: // POP_MARK
                        popMark();
                        break;
                    case 0x32: // DUP
                        push(peek());
                        break;
                    case 0x82: // EXT1
                        next();
                        push(Value.opaque(ValueKind.EXTENSION));
                        break;
                    case 0x83: // EXT2
                        readBytes(2);
                        push(Value.opaque(ValueKind.EXTENSION));
                        break;
                    case 0x84: // EXT4
                        readBytes(4);
                        push(Value.opaque(ValueKind.EXTENSION));
                        break;
                    default:
                        throw fail("unsupported_opcode_" + Integer.toHexString(opcode));
                }
            }
            if (!stopped) throw fail("missing_stop");
            throw fail("unreachable");
        }

        private void readGlobal() throws FormatException {
            String module = readAsciiLine();
            String name = readAsciiLine();
            if (module.isEmpty() || name.isEmpty()) throw fail("empty_global");
            push(Value.global(module, name));
            if ("renpy.ast".equals(module)) sawRenpyAstGlobal = true;
        }

        private void readStackGlobal() throws FormatException {
            Value name = pop();
            Value module = pop();
            if (module.kind != ValueKind.STRING || name.kind != ValueKind.STRING
                    || module.text == null || name.text == null
                    || module.text.isEmpty() || name.text.isEmpty()) {
                throw fail("invalid_stack_global");
            }
            push(Value.global(module.text, name.text));
            if ("renpy.ast".equals(module.text)) sawRenpyAstGlobal = true;
        }

        private void setItems() throws FormatException {
            int mark = lastMark();
            if (mark == 0) {
                throw fail("setitems_without_dict");
            }
            Value target = stack.get(mark - 1);
            // Real 8.4 pickles dict subclasses (renpy.revertable.RevertableDict)
            // as NEWOBJ instance + SETITEMS applied directly to the OBJECT.
            // CPython's SETITEMS uses PyObject_SetItem on the value below the
            // MARK, so a dict-subclass instance is a legitimate target.
            if (target.kind != ValueKind.DICT && target.kind != ValueKind.OBJECT) {
                throw fail("setitems_without_dict");
            }
            if (target.kind == ValueKind.OBJECT) sawObjectSetItems = true;
            int count = stack.size() - mark - 1;
            if ((count & 1) != 0 || count > MAX_CONTAINER_ITEMS * 2) {
                throw fail("invalid_setitems_count");
            }
            for (int index = mark + 1; index < stack.size(); index += 2) {
                Value key = stack.get(index);
                if (key.kind != ValueKind.STRING || key.text == null
                        || target.map.containsKey(key.text)) {
                    throw fail("invalid_dict_key");
                }
                target.map.put(key.text, stack.get(index + 1));
            }
            removeFrom(mark);
            updateEnvelopeCandidate(target);
        }

        private void setItem() throws FormatException {
            Value value = pop();
            Value key = pop();
            Value target = pop();
            // Same dict-subclass allowance as setItems(): real 8.4 can apply a
            // single SETITEM directly to a RevertableDict instance.
            if ((target.kind != ValueKind.DICT && target.kind != ValueKind.OBJECT)
                    || key.kind != ValueKind.STRING
                    || key.text == null || target.map.containsKey(key.text)) {
                throw fail("invalid_setitem");
            }
            target.map.put(key.text, value);
            if (target.kind == ValueKind.OBJECT) sawObjectSetItems = true;
            push(target);
            updateEnvelopeCandidate(target);
        }

        private void updateEnvelopeCandidate(Value target) throws FormatException {
            if (target != firstObject) return;
            if (target.map.size() == 3
                    && target.map.keySet().contains("version")
                    && target.map.keySet().contains("key")
                    && target.map.keySet().contains("deferred_parse_errors")) {
                envelope = target;
            } else if (envelope == target) {
                throw fail("root_envelope_changed");
            }
        }

        private void appends() throws FormatException {
            int mark = lastMark();
            if (mark == 0 || stack.get(mark - 1).kind != ValueKind.LIST) {
                throw fail("appends_without_list");
            }
            Value target = stack.get(mark - 1);
            if (stack.size() - mark - 1 > MAX_CONTAINER_ITEMS) {
                throw fail("append_count_limit");
            }
            for (int index = mark + 1; index < stack.size(); index++) {
                target.items.add(stack.get(index));
            }
            removeFrom(mark);
        }

        private void append() throws FormatException {
            Value value = pop();
            Value target = pop();
            if (target.kind != ValueKind.LIST) throw fail("append_without_list");
            target.items.add(value);
            push(target);
        }

        private void addItems() throws FormatException {
            int mark = lastMark();
            if (mark == 0 || stack.get(mark - 1).kind != ValueKind.SET) {
                throw fail("additems_without_set");
            }
            Value target = stack.get(mark - 1);
            for (int index = mark + 1; index < stack.size(); index++) {
                target.items.add(stack.get(index));
            }
            removeFrom(mark);
        }

        private void makeTuple(int count) throws FormatException {
            if (stack.size() < count) throw fail("tuple_stack_underflow");
            List<Value> values = new ArrayList<>(stack.subList(stack.size() - count, stack.size()));
            removeLast(count);
            push(Value.tuple(values));
        }

        private void makeTupleFromMark() throws FormatException {
            int mark = lastMark();
            List<Value> values = valuesAfter(mark);
            removeFrom(mark);
            push(Value.tuple(values));
        }

        private void makeListFromMark() throws FormatException {
            int mark = lastMark();
            List<Value> values = valuesAfter(mark);
            removeFrom(mark);
            push(Value.list(values));
        }

        private void reduce() throws FormatException {
            Value args = pop();
            Value callable = pop();
            if (args.kind != ValueKind.TUPLE || callable.kind != ValueKind.GLOBAL) {
                throw fail("invalid_reduce");
            }
            push(Value.opaque(ValueKind.OBJECT));
        }

        private void newObject() throws FormatException {
            Value args = pop();
            Value callable = pop();
            if (args.kind != ValueKind.TUPLE || callable.kind != ValueKind.GLOBAL) {
                throw fail("invalid_newobj");
            }
            push(Value.opaque(ValueKind.OBJECT));
        }

        private void newObjectEx() throws FormatException {
            Value kwargs = pop();
            Value args = pop();
            Value callable = pop();
            if (kwargs.kind != ValueKind.DICT || args.kind != ValueKind.TUPLE
                    || callable.kind != ValueKind.GLOBAL) {
                throw fail("invalid_newobj_ex");
            }
            push(Value.opaque(ValueKind.OBJECT));
        }

        private void build() throws FormatException {
            Value state = pop();
            Value object = pop();
            if (object.kind != ValueKind.OBJECT && object.kind != ValueKind.GLOBAL) {
                throw fail("invalid_build");
            }
            if (state.kind == ValueKind.MARK) throw fail("invalid_build_state");
            push(object);
        }

        private List<Value> valuesAfter(int mark) throws FormatException {
            if (mark < 0) throw fail("missing_mark");
            if (stack.size() - mark - 1 > MAX_CONTAINER_ITEMS) {
                throw fail("container_item_limit");
            }
            return new ArrayList<>(stack.subList(mark + 1, stack.size()));
        }

        private int lastMark() throws FormatException {
            for (int index = stack.size() - 1; index >= 0; index--) {
                if (stack.get(index).kind == ValueKind.MARK) return index;
            }
            throw fail("missing_mark");
        }

        private boolean hasMark() {
            for (Value value : stack) {
                if (value.kind == ValueKind.MARK) return true;
            }
            return false;
        }

        private void popMark() throws FormatException {
            removeFrom(lastMark());
        }

        private void removeFrom(int index) {
            stack.subList(index, stack.size()).clear();
        }

        private void removeLast(int count) {
            stack.subList(stack.size() - count, stack.size()).clear();
        }

        private void push(Value value) throws FormatException {
            if (value == null) throw fail("missing_memo_value");
            if (firstObject == null && value.kind != ValueKind.MARK) firstObject = value;
            stack.add(value);
        }

        private Value peek() throws FormatException {
            if (stack.isEmpty()) throw fail("stack_underflow");
            return stack.get(stack.size() - 1);
        }

        private Value pop() throws FormatException {
            Value value = peek();
            stack.remove(stack.size() - 1);
            if (value.kind == ValueKind.MARK) throw fail("unexpected_mark");
            return value;
        }

        private int readDecimalLine() throws FormatException {
            String value = readAsciiLine();
            try {
                return Integer.parseInt(value);
            } catch (NumberFormatException error) {
                throw fail("invalid_memo_index");
            }
        }

        private String readAsciiLine() throws FormatException {
            int start = position;
            while (position < data.length && data[position] != '\n') position++;
            if (position >= data.length) throw fail("unterminated_ascii_line");
            String value = new String(data, start, position - start, StandardCharsets.US_ASCII);
            position++;
            return value;
        }

        private String readUtf8(int length) throws FormatException {
            if (length < 0 || length > MAX_STRING_BYTES || length > data.length - position) {
                throw fail("invalid_string_length");
            }
            try {
                CharBuffer chars = StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(data, position, length));
                position += length;
                return chars.toString();
            } catch (CharacterCodingException error) {
                throw fail("invalid_utf8");
            }
        }

        private long readLe64() throws FormatException {
            if (position + 8 > data.length) throw fail("truncated_u64");
            long value = 0L;
            for (int index = 0; index < 8; index++) {
                value |= ((long) data[position + index] & 0xffL) << (index * 8);
            }
            position += 8;
            return value;
        }

        private int readLe64AsInt() throws FormatException {
            long value = readLe64();
            if (value < 0 || value > Integer.MAX_VALUE) throw fail("oversized_payload");
            return (int) value;
        }

        private int readLe32() throws FormatException {
            if (position + 4 > data.length) throw fail("truncated_u32");
            int value = (data[position] & 0xff)
                    | ((data[position + 1] & 0xff) << 8)
                    | ((data[position + 2] & 0xff) << 16)
                    | ((data[position + 3] & 0xff) << 24);
            position += 4;
            return value;
        }

        private void skipSizedBytes(int length, int ignored) throws FormatException {
            if (length < 0) throw fail("negative_payload_length");
            skipBytes(length);
        }

        private void skipBytes(int length) throws FormatException {
            if (length < 0 || length > MAX_STRING_BYTES * 4 || length > data.length - position) {
                throw fail("invalid_payload_length");
            }
            position += length;
        }

        private void readBytes(int count) throws FormatException {
            if (count < 0 || count > data.length - position) throw fail("truncated_bytes");
            position += count;
        }

        private void expect(int expected) throws FormatException {
            if (next() != expected) throw fail("unexpected_opcode");
        }

        private int next() throws FormatException {
            if (position >= data.length) throw fail("truncated_opcode");
            return data[position++] & 0xff;
        }

        private FormatException fail(String code) {
            return new FormatException(code);
        }

        private boolean containsIdentity(Value root, Value target) {
            return containsIdentity(root, target, new IdentityHashMap<Value, Boolean>());
        }

        private boolean containsIdentity(Value value, Value target,
                                         IdentityHashMap<Value, Boolean> seen) {
            if (value == target) return true;
            if (value == null || seen.put(value, Boolean.TRUE) != null) return false;
            for (Value child : value.items) {
                if (containsIdentity(child, target, seen)) return true;
            }
            for (Value child : value.map.values()) {
                if (containsIdentity(child, target, seen)) return true;
            }
            return false;
        }

        private String shape(Value value) {
            if (value == null) return "unknown";
            if (value.kind == ValueKind.TUPLE) {
                StringBuilder result = new StringBuilder("tuple(");
                for (int index = 0; index < value.items.size(); index++) {
                    if (index > 0) result.append(',');
                    result.append(shapeName(value.items.get(index)));
                }
                return result.append(')').toString();
            }
            return shapeName(value);
        }

        private String shapeName(Value value) {
            if (value == null || value.kind == null) return "unknown";
            return value.kind.name().toLowerCase(java.util.Locale.ROOT);
        }
    }

    private enum ValueKind {
        MARK,
        STRING,
        INTEGER,
        NONE,
        BOOLEAN,
        FLOAT,
        BYTES,
        GLOBAL,
        DICT,
        LIST,
        SET,
        TUPLE,
        OBJECT,
        EXTENSION
    }

    private static final class Value {
        final ValueKind kind;
        final String text;
        final Map<String, Value> map;
        final List<Value> items;

        private Value(ValueKind kind, String text, Map<String, Value> map, List<Value> items) {
            this.kind = kind;
            this.text = text;
            this.map = map == null ? new LinkedHashMap<String, Value>() : map;
            this.items = items == null ? new ArrayList<Value>() : items;
        }

        static Value mark() { return new Value(ValueKind.MARK, null, null, null); }
        static Value string(String value) { return new Value(ValueKind.STRING, value, null, null); }
        static Value global(String module, String name) {
            return new Value(ValueKind.GLOBAL, module + "\n" + name, null, null);
        }
        static Value opaque(ValueKind kind) { return new Value(kind, null, null, null); }
        static Value dict() { return new Value(ValueKind.DICT, null, null, null); }
        static Value list() { return new Value(ValueKind.LIST, null, null, null); }
        static Value list(List<Value> values) {
            return new Value(ValueKind.LIST, null, null, new ArrayList<>(values));
        }
        static Value set() { return new Value(ValueKind.SET, null, null, null); }
        static Value tuple(List<Value> values) {
            return new Value(ValueKind.TUPLE, null, null, new ArrayList<>(values));
        }
    }

    private static final class FormatException extends Exception {
        final String code;

        FormatException(String code) {
            this.code = code;
        }
    }
}
