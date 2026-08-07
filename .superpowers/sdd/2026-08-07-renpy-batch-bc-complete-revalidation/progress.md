# SDD ledger — plan: 2026-08-07-renpy-batch-bc-complete-revalidation

## Execution constraints

- All implementation and review subagents are capped at `gpt-5.6-luna`.
- Work is being performed in the existing shared checkout because the project depends on existing untracked APK/test fixtures.
- Preserve the four pre-staged user documents and all unrelated untracked files.
- Use explicit task paths and `git commit --only`; never use broad add/reset/clean/checkout operations.

## Task status

| Task | Status | Implementer | Reviewer | Notes |
|---|---|---|---|---|
| 0 | DONE | Task 0 implementation subagent | self-audit complete | Baseline captured; evidence ledger initialized; TDD RED/GREEN recorded; full regression and path audit complete. |
| 1 | DONE | Task 1 implementation subagent | independent scoped review passed | `bffc701` implementation; `0da088b` classification-evidence remediation; 26 records and stable extractor verified by focused tests. |
| 2 | DONE | Task 2 implementation subagent | independent scoped review passed | `1684a05` initial state-cluster alignment; `7880e62` runtime/language hardening; `f22bad5` report-artifact cleanup. Five-state group, runtime bridge, recovery/session, language guidance and extractor boundary checks passed. |
| 3 | DONE | Task 3 implementation subagent | independent scoped review passed after three fix rounds | `a5bfcae` initial; `a4f4654`, `b7775b0`, and `0b5744c` fix rounds; SourceSet, retry/watchdog, epoch, deadline, modal/back, extractor, restore, and split-tuple behavior verified. Node-only evidence; native/device and real split-APK gates remain open. |
| 4 | DONE | Task 4 implementation subagents | independent scoped review passed after three fix rounds | `8153593` initial; `5796ec4` end-to-end provider/batch/controller/package evidence; `2871bc4` and `01ea7179` exact RED evidence corrections. Four network-stop tests plus four performance tests passed; Node-only evidence boundary remains explicit. |
| 5 | NOT-RUN | — | — | — |
| 6 | NOT-RUN | — | — | — |
| 7 | NOT-RUN | — | — | — |
| 8 | NOT-RUN | — | — | — |
| 9 | NOT-RUN | — | — | — |
| 10 | NOT-RUN | — | — | — |
| 11 | NOT-RUN | — | — | — |
| 12 | NOT-RUN | — | — | — |
| 13 | NOT-RUN | — | — | — |
| 14 | NOT-RUN | — | — | — |
| 15 | NOT-RUN | — | — | — |
| 16 | NOT-RUN | — | — | — |
| 17 | NOT-RUN | — | — | — |
| 18 | NOT-RUN | — | — | — |
| 19 | NOT-RUN | — | — | — |
| 20 | NOT-RUN | — | — | — |
| 21 | NOT-RUN | — | — | — |
| 22 | NOT-RUN | — | — | — |
| 23 | NOT-RUN | — | — | — |

## Review rounds

| Task | Review status | Evidence |
|---|---|---|
| 0 | Approved after two scoped fix rounds | `d38b551..d3c56b8`, `d3c56b8..3631ce6`, `3631ce6..ecc5e6f`; final focused assertion, hash, protected-stage and diff checks passed. |
| 1 | Approved after one scoped fix round | `ecc5e6f..bffc701`; `bffc701..0da088b`; focused extractor/syntax tests and 26-row inventory checks passed; no Critical/Important findings remain. |
| 2 | Approved after one scoped fix round plus final artifact cleanup review | `7517acb..1684a05`; `1684a05..7880e62`; `1684a05..f22bad5`; five-state group, runtime Node fixture, three language branches, session deletion and regex tests passed; no Critical/Important findings remain. |
| 3 | Approved after three scoped fix rounds | `3df1369..a5bfcae` initial review; `a5bfcae..a4f4654` fixed SourceSet/retry/deadline/epoch/extractor/inventory issues; `a4f4654..b7775b0` fixed persisted SourceSet and lexical comment/regex issues; `b7775b0..0b5744c` fixed atomic split metadata merge. Final 17-test focused run, `py_compile`, diff checks, and protected-stage audit passed; no Critical/Important findings remain. |
| 4 | Approved after three scoped fix rounds | `5487cf9..8153593` initial review found P1 harness/package-gate and P2 evidence gaps; `8153593..5796ec4` fixed complete provider→batch→outer-controller/package path and exact RED records; `5796ec4..2871bc4` corrected WSP-04 code point; `2871bc4..01ea7179` corrected literal escaped evidence. Final 8-test network/performance run and exact parent-runner byte comparison passed; no Critical/Important findings remain. |

## Task 0 execution ledger

| Milestone | Status | Evidence |
|---|---|---|
| Source APK SHA256, HEAD, and status captured | PASS | `docs/qa/renpy-revalidation-baseline.md` |
| Python/Java/Node/Android toolchain probe captured | PASS | `docs/qa/renpy-revalidation-baseline.md` |
| Complete unittest baseline captured | PASS | `167 tests; 25 failures; 1 error; 1 skipped` in baseline document |
| TDD RED: explicit-status assertion fails for empty ledger | PASS | `0 not greater than or equal to 11` |
| Evidence rows T6–T16 initialized | PASS | `docs/qa/renpy-batch-bc-evidence.md` |
| TDD GREEN and final self-audit | PASS | Targeted test passed; full regression recorded; only explicit Task 0 paths are staged for the commit |

## Fix round 1

| Item | Status | Evidence |
|---|---|---|
| Fixed-table evidence parser | PASS | Exactly nine columns, 11 rows, IDs T6–T16, and status column 6 restricted to PASS/FAIL/NOT-RUN |
| Future PASS/FAIL compatibility | PASS | Temporary T6=PASS and T7=FAIL targeted run passed; ledger restored to NOT-RUN |
| Failure/error inventory | PASS | 25 failures + 1 error with focus commands, first diagnostics, and classifications in baseline document |
| APK provenance gate | PASS | Repository, fixed commit, raw URL, local path, SHA256, and stop-on-mismatch rule recorded |
| Phase 0 scope ruling | PASS | Authority design §5.1 explicitly permits only the non-product evidence-schema assertion |
| Fix-round verification | PASS_WITH_CONCERNS | Workshop: 49 tests, 25 failures, 1 error; discover: 168 tests, 25 failures, 1 error, 1 skipped |

## Fix round 2

| Item | Status | Evidence |
|---|---|---|
| Candidate classifications qualified | PASS | Baseline Category column and adjacent explanation now state preliminary observation and Phase 1 root-cause confirmation pending |
| C2/C6 non-exclusion clarified | PASS | Baseline says no C2/C6 candidate labels were assigned, not that either category is absent |
| Failure evidence preserved | PASS | All 26 names, focus commands, and first diagnostics retained; bundle dumps remain omitted |
| Documentation verification | PASS_WITH_CONCERNS | Markdown/report checks and `git diff --check` required; full suite not rerun per scoped request |
