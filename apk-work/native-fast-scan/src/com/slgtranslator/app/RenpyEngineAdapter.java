package com.slgtranslator.app;

/** Adapter for the existing Ren'Py detection and RPYC writer path. */
public final class RenpyEngineAdapter implements
        EngineAdapter<RenpyCompatibilityReport, RpycCompatibility.Report> {
    public static final RenpyEngineAdapter INSTANCE = new RenpyEngineAdapter();

    private RenpyEngineAdapter() {}

    @Override
    public String adapterId() {
        return "renpy";
    }

    @Override
    public WriterBackend<RpycCompatibility.Report> writer() {
        return RenpyRpycWriter.INSTANCE;
    }

    @Override
    public EngineCapabilities capabilities(RenpyCompatibilityReport report) {
        if (report == null) {
            return EngineCapabilities.forRenpy(null,
                    RenpyCompatibilityReport.ActivationStrategy.NONE, false);
        }
        return EngineCapabilities.forRenpy(report.supportLevel, report.activationStrategy,
                writer().supports(report.rpyc));
    }
}
