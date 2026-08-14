package com.slgtranslator.app;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/** Immutable structural result from {@link ModernEnvelopeReader}. */
public final class ModernEnvelopeInspection {
    public final boolean isVerified;
    public final RpycCompatibility.ModernDialect dialect;
    public final int pickleProtocol;
    public final Set<String> rootKeys;
    public final boolean sawRenpyAstGlobal;
    public final String rootShape;
    public final int frameCount;
    public final int memoizeCount;
    public final int newObjectCount;
    public final int setItemCount;
    public final int setItemsCount;
    public final int stackGlobalCount;
    public final boolean sawObjectSetItems;
    public final String reason;

    ModernEnvelopeInspection(boolean isVerified,
                             RpycCompatibility.ModernDialect dialect,
                             int pickleProtocol,
                             Set<String> rootKeys,
                             boolean sawRenpyAstGlobal,
                             String rootShape,
                             int frameCount,
                             int memoizeCount,
                             int newObjectCount,
                             int setItemCount,
                             int setItemsCount,
                             int stackGlobalCount,
                             boolean sawObjectSetItems,
                             String reason) {
        this.isVerified = isVerified;
        this.dialect = dialect;
        this.pickleProtocol = pickleProtocol;
        this.rootKeys = rootKeys == null
                ? Collections.<String>emptySet()
                : Collections.unmodifiableSet(new LinkedHashSet<>(rootKeys));
        this.sawRenpyAstGlobal = sawRenpyAstGlobal;
        this.rootShape = rootShape == null ? "unknown" : rootShape;
        this.frameCount = Math.max(0, frameCount);
        this.memoizeCount = Math.max(0, memoizeCount);
        this.newObjectCount = Math.max(0, newObjectCount);
        this.setItemCount = Math.max(0, setItemCount);
        this.setItemsCount = Math.max(0, setItemsCount);
        this.stackGlobalCount = Math.max(0, stackGlobalCount);
        this.sawObjectSetItems = sawObjectSetItems;
        this.reason = reason == null ? "" : reason;
    }

    static ModernEnvelopeInspection generic(String reason) {
        return new ModernEnvelopeInspection(false,
                RpycCompatibility.ModernDialect.MODERN_GENERIC,
                -1, Collections.<String>emptySet(), false, "unknown",
                0, 0, 0, 0, 0, 0, false, reason);
    }
}
