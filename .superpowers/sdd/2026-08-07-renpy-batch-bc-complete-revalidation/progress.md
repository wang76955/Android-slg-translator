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
| 1 | NOT-RUN | — | — | — |
| 2 | NOT-RUN | — | — | — |
| 3 | NOT-RUN | — | — | — |
| 4 | NOT-RUN | — | — | — |
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

No task review has run yet.

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
