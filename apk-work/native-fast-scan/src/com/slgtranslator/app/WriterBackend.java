package com.slgtranslator.app;

/** Describes an existing writer without implementing a new output backend. */
public interface WriterBackend<W> {
    String writerId();
    boolean supports(W report);
}
