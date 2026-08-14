package com.slgtranslator.app;

/** Capability view of the already verified Ren'Py RPYC writer. */
public final class RenpyRpycWriter implements WriterBackend<RpycCompatibility.Report> {
    public static final RenpyRpycWriter INSTANCE = new RenpyRpycWriter();

    private RenpyRpycWriter() {}

    @Override
    public String writerId() {
        return "renpy-rpyc-existing";
    }

    @Override
    public boolean supports(RpycCompatibility.Report report) {
        return report != null && report.canGenerate();
    }
}
