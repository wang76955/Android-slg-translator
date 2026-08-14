package com.slgtranslator.app;

/** Minimal adapter contract shared by engine-specific capability wrappers. */
public interface EngineAdapter<I, W> {
    String adapterId();
    EngineCapabilities capabilities(I report);
    WriterBackend<W> writer();
}
