package com.slgtranslator.app;

/**
 * Immutable capability description for one detected translation engine.
 * Translation and patch activation are intentionally separate capabilities.
 */
public final class EngineCapabilities {
    public enum Workflow {
        PATCHABLE_VERIFIED,
        PATCHABLE_EXPERIMENTAL,
        TRANSLATABLE_NO_PATCH,
        EXTRACTABLE_ONLY,
        UNSUPPORTED
    }

    public final boolean canDetect;
    public final boolean canExtractStructured;
    public final boolean canTranslate;
    public final boolean canWritePatch;
    public final boolean canActivate;
    public final boolean canValidateRuntime;
    public final Workflow workflow;

    private EngineCapabilities(boolean detect, boolean extract, boolean translate,
            boolean write, boolean activate, boolean validateRuntime, Workflow workflow) {
        this.canDetect = detect;
        this.canExtractStructured = extract;
        this.canTranslate = translate;
        this.canWritePatch = write;
        this.canActivate = activate;
        this.canValidateRuntime = validateRuntime;
        this.workflow = workflow == null ? Workflow.UNSUPPORTED : workflow;
    }

    public static EngineCapabilities forRenpy(
            RenpyCompatibilityReport.SupportLevel level,
            RenpyCompatibilityReport.ActivationStrategy activation,
            boolean writerAvailable) {
        if (level == RenpyCompatibilityReport.SupportLevel.SAFE
                || level == RenpyCompatibilityReport.SupportLevel.WARNING) {
            boolean canWrite = writerAvailable;
            return new EngineCapabilities(true, true, true, canWrite,
                    canWrite && activation != RenpyCompatibilityReport.ActivationStrategy.NONE,
                    canWrite && activation != RenpyCompatibilityReport.ActivationStrategy.NONE,
                    canWrite ? Workflow.PATCHABLE_VERIFIED
                            : Workflow.TRANSLATABLE_NO_PATCH);
        }
        if (level == RenpyCompatibilityReport.SupportLevel.EXTRACT_ONLY) {
            return new EngineCapabilities(true, true, true, false, false, false,
                    Workflow.TRANSLATABLE_NO_PATCH);
        }
        return new EngineCapabilities(level != null, false, false, false, false, false,
                Workflow.UNSUPPORTED);
    }
}
